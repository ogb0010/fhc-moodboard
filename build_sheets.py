"""Contact sheets (5x4, 300px thumbs, numbered) + README.md for every image folder."""
import pathlib, re
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = pathlib.Path(__file__).parent
FOLDERS = ["gen-x-soft-club", "area-tech", "editorials_layouts"]
EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
COLS, ROWS, T, PER = 5, 4, 300, 20
MAX_BYTES = 2_000_000
Image.MAX_IMAGE_PIXELS = None
font = ImageFont.load_default(size=22)


def natural(p):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


def thumb(path):
    try:
        im = Image.open(path)
        im.seek(0)
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((T, T))
        return im
    except Exception as e:
        print("  unreadable:", path.name, e)
        return None


def sheet(files, start, out):
    W, H = COLS * T, ROWS * T
    canvas = Image.new("RGB", (W, H), (24, 24, 24))
    d = ImageDraw.Draw(canvas)
    for i, f in enumerate(files):
        x, y = (i % COLS) * T, (i // COLS) * T
        im = thumb(f)
        if im:
            canvas.paste(im, (x + (T - im.width) // 2, y + (T - im.height) // 2))
        label = str(start + i)
        w = d.textlength(label, font=font)
        d.rectangle([x, y, x + w + 12, y + 28], fill=(0, 0, 0))
        d.text((x + 6, y + 2), label, fill=(255, 255, 255), font=font)
    for q in (88, 80, 72, 64, 55, 45):
        canvas.save(out, "JPEG", quality=q, optimize=True)
        if out.stat().st_size < MAX_BYTES:
            break
    return out.stat().st_size


(ROOT / "contact-sheets").mkdir(exist_ok=True)
readme = ["# fhc-moodboard", "",
          "Reference images for the album rollout (espionage / agency style, HUD layouts). "
          "Numbers on each contact sheet map to the full-size filenames listed below.", ""]
summary = []
body = []
for folder in FOLDERS:
    d = ROOT / folder
    if not d.is_dir():
        continue
    files = sorted((p for p in d.iterdir() if p.suffix.lower() in EXTS), key=natural)
    summary.append(f"- [`{folder}/`](#{folder.replace('_','_')}) — {len(files)} images")
    body += [f"## {folder}", "", f"{len(files)} images in `{folder}/`.", ""]
    print(folder, len(files), flush=True)
    for s in range(0, len(files), PER):
        chunk = files[s:s + PER]
        n = s // PER + 1
        name = f"{folder}_{n:02d}.jpg"
        size = sheet(chunk, s + 1, ROOT / "contact-sheets" / name)
        print(f"  {name} {size/1024:.0f} KB", flush=True)
        body += [f"### `contact-sheets/{name}` (#{s+1}–{s+len(chunk)})", "",
                 f"![{name}](contact-sheets/{name})", "",
                 "| # | File |", "|---|------|"]
        body += [f"| {s+i+1} | [`{f.name}`]({folder}/{f.name.replace(' ', '%20')}) |" for i, f in enumerate(chunk)]
        body.append("")
(ROOT / "README.md").write_text("\n".join(readme + summary + [""] + body) + "\n")
