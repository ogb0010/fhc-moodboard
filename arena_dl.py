#!/usr/bin/env python3
"""Download images from an Are.na channel.

Usage: python3 arena_dl.py SLUG [LIMIT] [TOKEN]
  LIMIT = total images wanted in the folder (reruns only fetch the new ones).
  TOKEN = optional Are.na access token (sent to api.are.na only).
  --manifest = don't download image files; only write manifest.json
               (id, title, image URL, source URL per block).
Every run also updates manifest.json for the blocks it saw.
"""
import json, pathlib, re, sys, time
import requests

BASE = pathlib.Path(__file__).resolve().parent
PER = 20
MIN_BYTES = 500
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
EXTS = ("jpg", "jpeg", "png", "gif", "webp")


def get(url, headers, tries=6, validate=None, **kw):
    for attempt in range(tries):
        wait = min(4 * 2 ** attempt, 60)
        try:
            r = requests.get(url, headers=headers, timeout=60, **kw)
            if r.status_code == 404:
                return r
            if r.status_code in (401, 403) and "api.are.na" in url:
                raise SystemExit(f"{r.status_code} from Are.na: private channel? pass an access token.")
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"status {r.status_code}")
            r.raise_for_status()
            if validate and not validate(r):
                raise requests.HTTPError(f"bad content ({len(r.content)} bytes)")
            return r
        except requests.RequestException as e:
            if attempt == tries - 1:
                break
            print(f"  problem ({e}), retry in {wait}s", flush=True)
            time.sleep(wait)
    return None


def image_url(b):
    im = b.get("image") or {}
    for k in ("original", "large", "display"):
        u = (im.get(k) or {}).get("url")
        if u:
            return u


def write_galleries():
    """README.md per channel (thumbnail grid hotlinked from Are.na) + index."""
    index = ["# Are.na moodboards", ""]
    for d in sorted(BASE.iterdir()):
        mp = d / "manifest.json"
        if not mp.is_file():
            continue
        items = json.loads(mp.read_text())
        lines = [f"# {d.name}", "",
                 f"{len(items)} images · [channel on Are.na](https://www.are.na/channel/{d.name})", ""]
        for m in items:
            title = (m.get("title") or "untitled").replace('"', "'")
            lines.append(f'<a href="{m["arena_url"]}"><img src="{m["image_url"]}" '
                         f'width="200" title="{title}"></a>')
        (d / "README.md").write_text("\n".join(lines) + "\n")
        index.append(f"- [{d.name}]({d.name}/README.md): {len(items)} images")
    (BASE / "README.md").write_text("\n".join(index) + "\n")


def main():
    manifest_only = "--manifest" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--manifest"]
    if not args:
        raise SystemExit(__doc__)
    slug = args[0]
    limit = int(args[1]) if len(args) > 1 else None
    token = args[2] if len(args) > 2 else None
    api_h = {"User-Agent": UA}
    if token:
        api_h["Authorization"] = f"Bearer {token}"
    img_h = {"User-Agent": UA, "Accept": "image/*,*/*;q=0.8"}  # never the token

    out = BASE / slug
    out.mkdir(exist_ok=True)
    notes_path = out / "non_image_blocks.json"
    try:
        notes = {n["id"]: n for n in json.loads(notes_path.read_text())}
    except Exception:
        notes = {}

    man_path = out / "manifest.json"
    try:
        manifest = {m["id"]: m for m in json.loads(man_path.read_text())}
    except Exception:
        manifest = {}
    count = new = failed = 0
    page = 1
    done = limit is not None and limit <= 0
    while not done:
        print(f"Fetching page {page}...", flush=True)
        r = get(f"https://api.are.na/v2/channels/{slug}/contents", api_h,
                params={"per": PER, "page": page})
        if r is None:
            raise SystemExit("Could not reach Are.na after retries; try again shortly.")
        if r.status_code == 404:
            raise SystemExit(f"Channel '{slug}' not found (or private: pass a token).")
        blocks = r.json().get("contents", [])
        if not blocks:
            break
        for b in blocks:
            img = image_url(b)
            if not img:
                notes[b["id"]] = {"id": b["id"], "class": b.get("class"),
                                  "title": b.get("title"), "content": b.get("content"),
                                  "source": (b.get("source") or {}).get("url")}
                continue
            if limit is not None and count >= limit:
                done = True
                break
            title = re.sub(r"[^\w\-]+", "_", b.get("title") or "untitled")[:50]
            ext = img.split("?")[0].rsplit(".", 1)[-1].lower()[:4]
            if ext not in EXTS:
                ext = "jpg"
            path = out / f"{b['id']}_{title}.{ext}"
            manifest[b["id"]] = {"id": b["id"], "title": b.get("title"),
                                 "file": path.name, "image_url": img,
                                 "source_url": (b.get("source") or {}).get("url"),
                                 "arena_url": f"https://www.are.na/block/{b['id']}"}
            if manifest_only:
                count += 1
                continue
            if path.exists() and path.stat().st_size > MIN_BYTES:
                count += 1
                print(f"  skip (exists) {path.name}", flush=True)
                continue
            resp = get(img, img_h, validate=lambda x: len(x.content) > MIN_BYTES)
            if resp is None or resp.status_code == 404:
                failed += 1
                print(f"  FAILED block {b['id']} {img}", flush=True)
                continue
            path.write_bytes(resp.content)
            count += 1
            new += 1
            print(f"  [{count}] saved {path.name} ({len(resp.content)/1024:.0f} KB)", flush=True)
        if limit is not None and count >= limit:
            done = True
        page += 1

    notes_path.write_text(json.dumps(list(notes.values()), indent=2, ensure_ascii=False))
    man_path.write_text(json.dumps(list(manifest.values()), indent=2, ensure_ascii=False))
    write_galleries()
    empty = [p for p in out.iterdir() if p.is_file() and p.stat().st_size == 0]
    print(f"\nDone: {count} images in {out} ({new} new, {failed} failed, "
          f"{len(empty)} empty files, {len(notes)} non-image blocks)")


if __name__ == "__main__":
    main()
