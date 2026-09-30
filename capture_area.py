"""Screenshot area.tech and each project from /projects (1440x900)."""
import hashlib, pathlib
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).parent / "area-tech"
OUT.mkdir(exist_ok=True)
MAX_SLICES = 40


def shot(pg, name):
    data = pg.screenshot()
    (OUT / name).write_bytes(data)
    print("  ", name, f"{len(data)//1024} KB", flush=True)
    return hashlib.md5(data).hexdigest()


def capture(pg, label):
    pg.wait_for_timeout(5000)
    h0 = shot(pg, f"{label}_00_top.png")
    # moving visuals? take 2 more frames a few seconds apart, keep if they differ
    seen, n = {h0}, 1
    for _ in range(2):
        pg.wait_for_timeout(3000)
        h = shot(pg, f"{label}_frame{n}.png")
        if h in seen:
            (OUT / f"{label}_frame{n}.png").unlink()
        else:
            seen.add(h); n += 1
    # scroll through the rest of a long page, one viewport at a time
    total = pg.evaluate("document.documentElement.scrollHeight")
    y, i = 900, 1
    while y < total and i <= MAX_SLICES:
        pg.evaluate(f"window.scrollTo(0,{y})")
        pg.wait_for_timeout(1200)
        shot(pg, f"{label}_{i:02d}_scroll.png")
        total = pg.evaluate("document.documentElement.scrollHeight")
        y += 900; i += 1
    pg.evaluate("window.scrollTo(0,0)")


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.goto("https://www.area.tech", wait_until="domcontentloaded")
    print("home")
    capture(pg, "home")
    pg.goto("https://www.area.tech/projects", wait_until="domcontentloaded")
    pg.wait_for_timeout(5000)
    names = pg.evaluate("[...document.querySelectorAll('p')].map(e=>e.textContent.trim()).slice(0,-1)")
    urls = []
    for i, n in enumerate(names):
        pg.goto("https://www.area.tech/projects", wait_until="domcontentloaded")
        pg.wait_for_timeout(3000)
        pg.get_by_text(n, exact=True).first.click()
        pg.wait_for_timeout(1500)
        urls.append(pg.url)
    print(urls)
    for u in urls:
        slug = u.rstrip("/").rsplit("/", 1)[-1]
        print(slug, u)
        pg.goto(u, wait_until="domcontentloaded")
        capture(pg, slug)
    b.close()
