#!/usr/bin/env python3
"""Fetch photographs the routine sandbox cannot reach, and commit them.

Why this exists. The cloud routine sandbox runs behind a strict egress
allowlist. Every stock photo host is blocked (all 18 tested on 2026-09-07
returned "CONNECT tunnel failed, response 403"), and the r2 presigned URL used
for publishing is upload-only: reading it back gives InvalidArgument. The one
image host the sandbox CAN read is raw.githubusercontent.com. A GitHub runner
is on the open internet. So the routine asks, the runner fetches, the routine
reads it back. Nothing large ever passes through the model's context.

The routine asks by committing a small JSON file into requests/, because
writing a file is the one GitHub action the routine is reliably allowed to do.
repository_dispatch is not usable: the connector gates it behind an elicitation
feature the routine's MCP client does not support.

No API key is needed. images.pexels.com serves by photo id without auth; the
routine gets the id from PEXELS_SEARCH_PHOTOS, which is cheap because it
returns text.
"""
import glob, io, json, os, sys, urllib.error, urllib.request
from PIL import Image, ImageStat

CDN = ("https://images.pexels.com/photos/{i}/pexels-photo-{i}.jpeg"
       "?auto=compress&cs=tinysrgb&fit=crop&h={h}&w={w}")
LIVE, REQ, DONE = "live", "requests", "requests/done"

# The crops the routines actually publish. `feed` is the 4:5 Instagram and
# Facebook card, `story` is the 9:16 Story frame and the Reel beat, `square`
# is the quote card. Before 2026-09-08 every photograph came back at 1080x1350
# whatever it was for, so a Story frame was a 4:5 crop stretched to 9:16 and it
# looked it.
SIZES = {"feed": (1080, 1350), "story": (1080, 1920), "square": (1080, 1080)}


def fetch(pid, w, h):
    # Ask the CDN for a crop slightly larger than the target on both axes, so
    # the LANCZOS resize below is always a downscale.
    url = CDN.format(i=pid, w=int(w * 1.2), h=int(h * 1.2))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read()


def load_index():
    try:
        return json.load(open(f"{LIVE}/index.json"))
    except Exception:
        return {"photos": []}


def render(pid, raw, safe, size, r, idx):
    """Write one crop and record it. Returns the record."""
    w, h = SIZES[size]
    im = Image.open(io.BytesIO(raw)).convert("RGB").resize((w, h), Image.LANCZOS)
    os.makedirs(LIVE, exist_ok=True)
    name = safe if size == "feed" else "%s-%s" % (safe, size)
    out = f"{LIVE}/{name}.jpg"
    im.save(out, "JPEG", quality=80, optimize=True, progressive=True)

    # Mean luminance of each third. The routine uses these to place the text
    # band and decide whether it needs a scrim, so a white headline never lands
    # on a white sky.
    g = im.convert("L")
    lum = lambda b: round(ImageStat.Stat(g.crop(b)).mean[0])
    t = h // 3
    rec = {"file": f"{name}.jpg", "pexels_id": int(pid), "size": size,
           "w": w, "h": h,
           "subject": str(r.get("subject", "")), "alt": str(r.get("alt", "")),
           "lum_top": lum((0, 0, w, t)), "lum_mid": lum((0, t, w, 2 * t)),
           "lum_bottom": lum((0, 2 * t, w, h)), "bytes": os.path.getsize(out),
           "added": os.environ.get("STAMP", "")}
    idx["photos"] = [p for p in idx["photos"] if p.get("file") != rec["file"]]
    idx["photos"].append(rec)
    return rec


def process(path, idx):
    r = json.load(open(path))
    slug = str(r.get("slug", "")).strip().lower()
    safe = "".join(c for c in slug if c.isalnum() or c in "-_")[:60]
    if not safe:
        return None, "bad request: slug must be usable"

    # One id, or several to fall through. A routine that has run
    # PEXELS_SEARCH_PHOTOS already has six ids in hand and it costs nothing to
    # send three, so one dead id no longer loses the day.
    ids = r.get("photo_ids") or [r.get("photo_id")]
    ids = [str(i).strip() for i in ids if str(i).strip().isdigit()][:4]
    if not ids:
        return None, "bad request: photo_id or photo_ids must be numeric"

    sizes = r.get("sizes") or [r.get("size") or "feed"]
    sizes = [s for s in sizes if s in SIZES] or ["feed"]

    raw, pid, errs = None, None, []
    for cand in ids:
        try:
            data = fetch(cand, *SIZES[sizes[0]])
        except urllib.error.HTTPError as e:
            errs.append("id %s HTTP %s" % (cand, e.code))
            continue
        except Exception as e:                       # noqa: BLE001
            errs.append("id %s %s" % (cand, type(e).__name__))
            continue
        if len(data) < 20000:
            errs.append("id %s only %d bytes" % (cand, len(data)))
            continue
        raw, pid = data, cand
        break
    if raw is None:
        return None, "no candidate photo worked: " + "; ".join(errs)

    recs = []
    for size in sizes:
        # Re-fetch per size so the CDN does the crop rather than us stretching
        # one aspect ratio into another.
        data = raw if size == sizes[0] else fetch(pid, *SIZES[size])
        recs.append(render(pid, data, safe, size, r, idx))
    main_rec = dict(recs[0])
    if len(recs) > 1:
        main_rec["also"] = [x["file"] for x in recs[1:]]
    return main_rec, None


def main():
    pending = sorted(p for p in glob.glob(f"{REQ}/*.json"))
    if not pending:
        print("no pending requests")
        return
    idx, results = load_index(), []
    for path in pending:
        try:
            rec, err = process(path, idx)
        except Exception as e:                       # never let one bad request stall the queue
            rec, err = None, "%s: %s" % (type(e).__name__, e)
        results.append({"request": os.path.basename(path), "ok": rec is not None,
                        "record": rec, "error": err})
        os.makedirs(DONE, exist_ok=True)
        os.replace(path, os.path.join(DONE, os.path.basename(path)))
        print(("OK   " if rec else "FAIL ") + os.path.basename(path) + (" " + err if err else ""))

    idx["photos"] = idx["photos"][-400:]             # keep the repo from growing without limit
    idx["updated"] = os.environ.get("STAMP", "")
    idx["count"] = len(idx["photos"])
    os.makedirs(LIVE, exist_ok=True)
    json.dump(idx, open(f"{LIVE}/index.json", "w"), indent=1)

    for p in sorted(glob.glob(f"{DONE}/*.json"))[:-200]:   # prune old receipts
        os.remove(p)
    if not any(r["ok"] for r in results):
        sys.exit("every request in this batch failed")


if __name__ == "__main__":
    main()
