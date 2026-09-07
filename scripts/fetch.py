#!/usr/bin/env python3
"""Fetch one photograph by Pexels id, normalise it, and write it into the repo.

Why this exists. The cloud routine sandbox has a strict egress allowlist:
images.pexels.com is blocked, every other stock host is blocked, and the r2
presigned URL used for publishing is upload-only. The only image host the
sandbox CAN read is raw.githubusercontent.com. A GitHub Action runs on the open
internet, so it fetches the photograph and commits it, and the routine reads it
back from raw. Nothing large ever passes through the model's context.

No API key is needed: images.pexels.com serves by photo id without auth. The
routine gets the id from PEXELS_SEARCH_PHOTOS over Composio, which is cheap
because it returns text.
"""
import json, os, sys, urllib.request, io
from PIL import Image, ImageStat

CDN = ("https://images.pexels.com/photos/{i}/pexels-photo-{i}.jpeg"
       "?auto=compress&cs=tinysrgb&fit=crop&h=1620&w=1296")

def fetch(pid):
    req = urllib.request.Request(CDN.format(i=pid), headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read()

def main():
    pid  = str(os.environ["PHOTO_ID"]).strip()
    slug = os.environ["SLUG"].strip().lower()
    alt  = os.environ.get("ALT", "").strip()
    subj = os.environ.get("SUBJECT", "").strip()
    if not pid.isdigit():
        sys.exit("PHOTO_ID must be numeric, got %r" % pid)
    safe = "".join(c for c in slug if c.isalnum() or c in "-_")[:60]
    if not safe:
        sys.exit("SLUG produced an empty filename")

    raw = fetch(pid)
    if len(raw) < 20000:
        sys.exit("photo %s came back at only %d bytes, refusing it" % (pid, len(raw)))

    im = Image.open(io.BytesIO(raw)).convert("RGB").resize((1080, 1350), Image.LANCZOS)
    os.makedirs("live", exist_ok=True)
    path = "live/%s.jpg" % safe
    im.save(path, "JPEG", quality=80, optimize=True, progressive=True)

    # Mean luminance of each third. The routine uses these to decide whether the
    # text band needs a scrim, so a white headline never lands on a white sky.
    g = im.convert("L")
    lum = lambda box: round(ImageStat.Stat(g.crop(box)).mean[0])
    rec = {"file": "%s.jpg" % safe, "pexels_id": int(pid), "subject": subj, "alt": alt,
           "lum_top": lum((0, 0, 1080, 450)), "lum_mid": lum((0, 450, 1080, 900)),
           "lum_bottom": lum((0, 900, 1080, 1350)), "bytes": os.path.getsize(path)}

    idx = {"photos": []}
    if os.path.exists("live/index.json"):
        try: idx = json.load(open("live/index.json"))
        except Exception: pass
    idx["photos"] = [p for p in idx.get("photos", []) if p.get("file") != rec["file"]]
    idx["photos"].append(rec)
    idx["photos"] = idx["photos"][-400:]          # keep the repo from growing forever
    idx["updated"] = os.environ.get("STAMP", "")
    json.dump(idx, open("live/index.json", "w"), indent=1)

    print(json.dumps(rec))

if __name__ == "__main__":
    main()
