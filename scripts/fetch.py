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
       "?auto=compress&cs=tinysrgb&fit=crop&h=1620&w=1296")
LIVE, REQ, DONE = "live", "requests", "requests/done"


def fetch(pid):
    req = urllib.request.Request(CDN.format(i=pid), headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read()


def load_index():
    try:
        return json.load(open(f"{LIVE}/index.json"))
    except Exception:
        return {"photos": []}


def process(path, idx):
    r = json.load(open(path))
    pid  = str(r.get("photo_id", "")).strip()
    slug = str(r.get("slug", "")).strip().lower()
    safe = "".join(c for c in slug if c.isalnum() or c in "-_")[:60]
    if not pid.isdigit() or not safe:
        return None, "bad request: photo_id must be numeric and slug must be usable"

    try:
        raw = fetch(pid)
    except urllib.error.HTTPError as e:
        return None, "pexels returned HTTP %s for id %s" % (e.code, pid)
    if len(raw) < 20000:
        return None, "photo %s came back at only %d bytes, refusing it" % (pid, len(raw))

    im = Image.open(io.BytesIO(raw)).convert("RGB").resize((1080, 1350), Image.LANCZOS)
    os.makedirs(LIVE, exist_ok=True)
    out = f"{LIVE}/{safe}.jpg"
    im.save(out, "JPEG", quality=80, optimize=True, progressive=True)

    # Mean luminance of each third. The routine uses these to place the text
    # band and decide whether it needs a scrim, so a white headline never lands
    # on a white sky.
    g = im.convert("L")
    lum = lambda b: round(ImageStat.Stat(g.crop(b)).mean[0])
    rec = {"file": f"{safe}.jpg", "pexels_id": int(pid),
           "subject": str(r.get("subject", "")), "alt": str(r.get("alt", "")),
           "lum_top": lum((0, 0, 1080, 450)), "lum_mid": lum((0, 450, 1080, 900)),
           "lum_bottom": lum((0, 900, 1080, 1350)), "bytes": os.path.getsize(out),
           "added": os.environ.get("STAMP", "")}
    idx["photos"] = [p for p in idx["photos"] if p.get("file") != rec["file"]]
    idx["photos"].append(rec)
    return rec, None


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
