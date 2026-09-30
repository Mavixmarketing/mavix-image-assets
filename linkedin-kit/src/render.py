#!/usr/bin/env python3
"""Render the day's LinkedIn creative for both accounts from one JSON file.

    python3 render.py post.json [upload_url]

post.json: {"farhan": {"format": ..., "d": {...}}, "nasir": {...}, ...captions...}
Formats rendered here: take, myth, carousel, tweet (card only), stat, bars.
meme and poll need nothing rendered; the relay handles them.
Prints one line per account, then either BUNDLE OK or the problems to fix.
"""
import json, os, re, sys, shutil, subprocess, tarfile, glob, time
from pathlib import Path

KIT = Path(__file__).resolve().parent
OUT = Path("/tmp/lk/out")
CHROME = next((p for p in ["/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
                           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"] if os.path.exists(p)), None)
STILL = {"take", "myth", "carousel", "tweet"}
MOTION = {"stat", "bars"}
NONE = {"meme", "poll"}


def sandbox_env():
    """Point HyperFrames at the sandbox's own chromium and ffmpeg (no downloads needed)."""
    if not os.path.exists("/opt/pw-browsers"):
        return
    b = Path("/tmp/lk/bin"); b.mkdir(parents=True, exist_ok=True)
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        os.environ["HYPERFRAMES_FFMPEG_PATH"] = ff
        (b / "ffmpeg").unlink(missing_ok=True); (b / "ffmpeg").symlink_to(ff)
    except Exception:
        pass
    fp = next(iter(glob.glob(str(KIT / "node_modules/@ffprobe-installer/linux-x64/ffprobe"))), None)
    if fp:
        os.chmod(fp, 0o755); (b / "ffprobe").unlink(missing_ok=True); (b / "ffprobe").symlink_to(fp)
    hs = glob.glob("/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell")
    os.environ["PRODUCER_HEADLESS_SHELL_PATH"] = hs[0] if hs else CHROME
    os.environ["HYPERFRAMES_BROWSER_PATH"] = CHROME
    os.environ["PATH"] = f"{b}:{os.environ['PATH']}"


def check_captions(post):
    p = []
    for a in ("farhan", "nasir"):
        s = post.get(a) or {}
        c = s.get("caption", "")
        if not c: p.append(f"{a}: caption missing")
        if "\u2014" in c or "\u2013" in c: p.append(f"{a}: caption has an em or en dash")
        if len(c) > 2800: p.append(f"{a}: caption over 2800 characters")
        if c and len(c.strip().splitlines()[0]) > 150: p.append(f"{a}: first line over 150 characters, make the hook shorter")
        if len(re.findall(r"#[A-Za-z]\w+", c)) > 4: p.append(f"{a}: more than 4 hashtags")
        if re.search(r"https?://", c): p.append(f"{a}: no links in the caption")
        if re.search(r"\b(like|follow|share|repost|tag)\b[^.?!]{0,30}\b(this|me|us|someone|a friend)\b", c, re.I):
            p.append(f"{a}: caption asks for likes/follows/shares/tags, remove that")
        if len(s.get("first_comment", "")) > 160: p.append(f"{a}: first_comment too long")
    if post.get("farhan", {}).get("caption", "")[:60] == post.get("nasir", {}).get("caption", "")[:60]:
        p.append("nasir caption starts the same as farhan's, write it differently")
    return p


def page(tpl, data, dst):
    html = (KIT / tpl).read_text().replace("/*DATA*/", "window.D=" + json.dumps(data, ensure_ascii=False) + ";")
    dst.write_text(html)
    return dst


def shoot(browser, html, png, extra_js=None):
    pg = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
    pg.goto(html.as_uri())
    pg.wait_for_function("window.__done === true", timeout=20000)
    if extra_js:
        pg.evaluate(extra_js)
    probs = pg.evaluate("window.__overflow")
    info = pg.evaluate("window.__info || null")
    pg.screenshot(path=str(png), full_page=False)
    pg.close()
    return probs, info


def render_account(browser, acct, spec, work):
    fmt, d = spec["format"], dict(spec.get("d") or {})
    d["acct"] = acct
    out = OUT / acct
    out.mkdir(parents=True, exist_ok=True)
    probs, files = [], []
    if fmt in NONE:
        return [], [], None
    if fmt in ("take", "myth", "tweet"):
        png = out / f"{fmt}.png"
        p, info = shoot(browser, page(f"{fmt}.html", d, work / f"{acct}-{fmt}.html"), png)
        probs += p
        files.append(png.name)
        if fmt == "tweet":
            (out / "hole.json").write_text(json.dumps(info))
            files.append("hole.json")
        return probs, files, png
    if fmt == "carousel":
        slides = d.get("slides") or []
        if not 4 <= len(slides) <= 8:
            probs.append(f"carousel needs 4 to 8 middle slides, got {len(slides)}")
        n = len(slides) + 2
        pngs = []
        for i in range(n):
            dd = dict(d, i=i, n=n)
            png = work / f"{acct}-c{i:02d}.png"
            p, _ = shoot(browser, page("carousel.html", dd, work / f"{acct}-c{i}.html"), png)
            probs += [f"slide {i + 1}: {x}" for x in p]
            pngs.append(png)
        from PIL import Image
        ims = [Image.open(x).convert("RGB") for x in pngs]
        ims[0].save(out / "carousel.pdf", save_all=True, append_images=ims[1:], resolution=144)
        shutil.copy(pngs[0], out / "cover.png")
        files += ["carousel.pdf", "cover.png"]
        return probs, files, out / "cover.png"
    if fmt in MOTION:
        proj = work / f"{acct}-{fmt}"
        if proj.exists():
            shutil.rmtree(proj)
        shutil.copytree(KIT / "hf", proj, ignore=shutil.ignore_patterns("*.html"))
        for f in ["base.css", "base.js", "farhan.jpg", "nasir.jpg"]:
            shutil.copy(KIT / f, proj / f)
        if not (proj / "fonts").exists():
            shutil.copytree(KIT / "fonts", proj / "fonts")
        page(f"hf/{fmt}.html", d, proj / "index.html")
        poster = out / "poster.png"
        # the final frame, checked for overflow before spending time on a render
        p, _ = shoot(browser, proj / "index.html", poster,
                     "(() => { const t = window.__timelines && window.__timelines.main; if (t) t.seek(t.duration()); })()")
        probs += p
        if probs:
            return probs, files, poster
        env = dict(os.environ)
        cmd = ["npx", "--no-install", "hyperframes", "render", str(proj), "--quality", "looks",
               "--output", str(out / f"{fmt}.mp4")]
        r = subprocess.run(cmd, cwd=str(KIT), env=env, capture_output=True, text=True, timeout=600)
        mp4 = out / f"{fmt}.mp4"
        if r.returncode != 0 or not mp4.exists() or mp4.stat().st_size < 20000:
            # fall back to the final frame as a still image rather than losing the day
            print(f"  {acct}: video render failed, shipping the final frame as an image. "
                  f"{(r.stderr or r.stdout)[-300:]}", file=sys.stderr)
            files.append("poster.png")
            (out / "fallback.txt").write_text("video failed")
        else:
            files += [mp4.name, "poster.png"]
        return probs, files, poster
    return [f"unknown format {fmt}"], [], None


def main():
    post = json.loads(Path(sys.argv[1]).read_text())
    sandbox_env()
    upload = sys.argv[2] if len(sys.argv) > 2 else None
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    work = Path("/tmp/lk/work")
    work.mkdir(parents=True, exist_ok=True)
    for f in ["base.css", "base.js", "farhan.jpg", "nasir.jpg"]:
        shutil.copy(KIT / f, work / f)
    if not (work / "fonts").exists():
        shutil.copytree(KIT / "fonts", work / "fonts")
    from playwright.sync_api import sync_playwright
    problems, previews, manifest = [], [], {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--allow-file-access-from-files"])
        for acct in ("farhan", "nasir"):
            spec = post.get(acct)
            if not spec:
                problems.append(f"{acct}: missing"); continue
            t = time.time()
            try:
                p, files, prev = render_account(browser, acct, spec, work)
            except Exception as ex:
                p, files, prev = [f"render error: {str(ex)[:200]}"], [], None
            problems += [f"{acct} {spec['format']}: {x}" for x in p]
            manifest[acct] = {"format": spec["format"], "files": files}
            if prev:
                previews.append(prev)
            print(f"{acct}: {spec['format']} -> {', '.join(files) or 'nothing to render'} ({time.time() - t:.0f}s)")
        browser.close()
    problems += check_captions(post)
    if problems:
        print("FIX THESE, then run again:\n  " + "\n  ".join(problems))
        sys.exit(1)
    # one small side-by-side preview for a single look
    from PIL import Image
    if previews:
        ims = [Image.open(x).convert("RGB").resize((432, 540)) for x in previews]
        sheet = Image.new("RGB", (432 * len(ims) + 12 * (len(ims) - 1), 540), "white")
        for i, im in enumerate(ims):
            sheet.paste(im, (i * 444, 0))
        sheet.save("/tmp/lk/preview.jpg", quality=80)
    (OUT / "post.json").write_text(json.dumps(post, ensure_ascii=False))
    (OUT / "manifest.json").write_text(json.dumps(manifest))
    with tarfile.open("/tmp/lk/bundle.tgz", "w:gz") as tf:
        tf.add(OUT, arcname="out")
    size = os.path.getsize("/tmp/lk/bundle.tgz")
    if upload:
        r = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "-X", "PUT",
                            "-H", "Content-Type: application/gzip", "--data-binary", "@/tmp/lk/bundle.tgz", upload],
                           capture_output=True, text=True)
        if r.stdout.strip() != "200":
            print(f"UPLOAD FAILED http {r.stdout.strip()} {r.stderr[-200:]}"); sys.exit(1)
    print(f"BUNDLE OK {size // 1024}KB{' uploaded' if upload else ''}. Preview: /tmp/lk/preview.jpg")


if __name__ == "__main__":
    main()
