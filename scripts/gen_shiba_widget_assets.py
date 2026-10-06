"""Turn key poses in assets/shiba_pet into widget clip WebP frames."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "shiba_pet"
OUT = ROOT / "android" / "app" / "src" / "main" / "res" / "drawable-nodpi"
LEGACY = ROOT / "android" / "app" / "src" / "main" / "res" / "drawable"
SIZE = 320


def _load(name: str) -> Image.Image:
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        path = SRC / f"{name}{ext}"
        if path.exists():
            return Image.open(path).convert("RGBA")
    raise SystemExit(f"missing pose {name} in {SRC}")


def _chroma(r: int, g: int, b: int) -> int:
    return max(r, g, b) - min(r, g, b)


def _touches_empty(pix, x: int, y: int, w: int, h: int) -> bool:
    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
        if not (0 <= nx < w and 0 <= ny < h) or pix[nx, ny][3] == 0:
            return True
    return False


def _restore_holes(im: Image.Image, original: Image.Image) -> None:
    """Transparent pixels sealed inside the pet are knockout leaks, not backdrop."""
    w, h = im.size
    pix = im.load()
    orig = original.load()
    seen: set[tuple[int, int]] = set()
    stack = [(x, y) for x in range(w) for y in (0, h - 1) if pix[x, y][3] == 0]
    stack += [(x, y) for y in range(h) for x in (0, w - 1) if pix[x, y][3] == 0]
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h) or pix[x, y][3]:
            continue
        seen.add((x, y))
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    for y in range(h):
        for x in range(w):
            if pix[x, y][3] == 0 and (x, y) not in seen:
                r, g, b, _ = orig[x, y]
                pix[x, y] = (r, g, b, 255)


def _drop_specks(im: Image.Image, min_size: int = 2000) -> None:
    w, h = im.size
    pix = im.load()
    seen = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if seen[y][x] or pix[x, y][3] == 0:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            cells = [(x, y)]
            while stack:
                cx, cy = stack.pop()
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and pix[nx, ny][3]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
                        cells.append((nx, ny))
            if len(cells) < min_size:
                for cx, cy in cells:
                    pix[cx, cy] = (0, 0, 0, 0)


def _trim_bg(im: Image.Image, threshold: int = 48) -> Image.Image:
    """Knock out the gray studio backdrop, then peel the leftover fringe."""
    im = im.convert("RGBA")
    original = im.copy()
    w, h = im.size
    pix = im.load()
    corners = ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))
    r0 = sum(pix[p][0] for p in corners) // 4
    g0 = sum(pix[p][1] for p in corners) // 4
    b0 = sum(pix[p][2] for p in corners) // 4

    def is_bg(r: int, g: int, b: int, a: int) -> bool:
        if a == 0 or _chroma(r, g, b) > 10:
            return False
        near_bg = abs(r - r0) <= threshold and abs(g - g0) <= threshold and abs(b - b0) <= threshold
        # White squares of a baked-in checkerboard are brighter than the backdrop.
        near_white = (r + g + b) // 3 >= 210 and _chroma(r, g, b) <= 8
        return near_bg or near_white

    stack: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for x in range(w):
        stack.extend(((x, 0), (x, h - 1)))
    for y in range(h):
        stack.extend(((0, y), (w - 1, y)))
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h):
            continue
        r, g, b, a = pix[x, y]
        if not is_bg(r, g, b, a):
            continue
        seen.add((x, y))
        pix[x, y] = (0, 0, 0, 0)
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    for _ in range(12):
        kill = [
            (x, y)
            for y in range(h)
            for x in range(w)
            if pix[x, y][3]
            and _chroma(*pix[x, y][:3]) <= 8
            and _touches_empty(pix, x, y, w, h)
        ]
        if not kill:
            break
        for x, y in kill:
            pix[x, y] = (0, 0, 0, 0)

    _restore_holes(im, original)
    _drop_specks(im)

    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    return im


def _fit(im: Image.Image) -> Image.Image:
    im = ImageOps.contain(im, (SIZE, SIZE), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(im, ((SIZE - im.width) // 2, SIZE - im.height), im)
    return canvas


def _squash(im: Image.Image, y_scale: float) -> Image.Image:
    h = max(1, int(im.height * y_scale))
    squeezed = im.resize((im.width, h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
    canvas.paste(squeezed, (0, im.height - h), squeezed)
    return canvas


def _move(im: Image.Image, dy: int = 0, dx: int = 0) -> Image.Image:
    canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
    canvas.paste(im, (dx, -dy), im)
    return canvas


def _frame(im: Image.Image, y_scale: float = 1.0, dy: int = 0, dx: int = 0, deg: float = 0) -> Image.Image:
    out = _squash(im, y_scale) if y_scale != 1 else im
    if deg:
        out = _tilt(out, deg)
    if dy or dx:
        out = _move(out, dy, dx)
    return out


def _tilt(im: Image.Image, deg: float) -> Image.Image:
    return im.rotate(deg, resample=Image.Resampling.BICUBIC, expand=False)


def _tint(im: Image.Image, rgba: tuple[int, int, int, int]) -> Image.Image:
    overlay = Image.new("RGBA", im.size, rgba)
    return Image.alpha_composite(im, Image.composite(overlay, Image.new("RGBA", im.size), im.split()[3]))


def _save(name: str, im: Image.Image) -> None:
    dest = OUT / f"{name}.webp"
    im.save(dest, "WEBP", lossless=True, quality=100, method=4)
    print(dest)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    poses = {n: _fit(_trim_bg(_load(n))) for n in (
        "idle", "blink", "happy_wag", "jump", "think", "sleep", "surprised",
    )}

    # Mood still-drawables (chat avatar + notification icon)
    stills = {
        "shiba_idle": poses["idle"],
        "shiba_think": poses["think"],
        "shiba_sleep": poses["sleep"],
        "shiba_alert": poses["surprised"],
        "shiba_error": _tint(poses["sleep"], (180, 40, 40, 70)),
        "shiba_boop": _squash(poses["idle"], 0.9),
    }
    for name, img in stills.items():
        # Keep PNG in drawable for adaptive icon / smallIcon compatibility
        dest = LEGACY / f"{name}.png"
        img.save(dest, "PNG")
        print(dest)

    blink = Image.blend(poses["idle"], poses["blink"], 0.5)
    frames: dict[str, Image.Image] = {
        "clip_idle_0": poses["idle"],
        "clip_idle_1": blink,
        "clip_idle_2": poses["blink"],
        "clip_idle_3": blink,
    }
    boop = (
        ("idle", 0.94, 0),
        ("idle", 0.86, 0),
        ("idle", 0.80, 2),
        ("jump", 1.0, 10),
        ("jump", 1.0, 20),
        ("jump", 1.0, 12),
        ("idle", 0.88, 0),
        ("idle", 0.97, 0),
    )
    for i, (pose, scale, dy) in enumerate(boop):
        frames[f"clip_boop_{i}"] = _frame(poses[pose], scale, dy)
    wag = ((-2, -1), (-5, -3), (-8, -4), (-6, -3), (-3, -1), (2, 1), (5, 3), (8, 4), (6, 3), (3, 1))
    for i, (deg, dx) in enumerate(wag):
        frames[f"clip_wag_{i}"] = _frame(poses["happy_wag"], deg=deg, dx=dx)
    jump = (
        ("idle", 0.94, 0),
        ("idle", 0.86, 0),
        ("jump", 1.0, 8),
        ("jump", 1.0, 18),
        ("jump", 1.0, 28),
        ("jump", 1.0, 34),
        ("jump", 1.0, 22),
        ("jump", 1.0, 10),
        ("idle", 0.90, 0),
        ("idle", 0.98, 0),
    )
    for i, (pose, scale, dy) in enumerate(jump):
        frames[f"clip_jump_{i}"] = _frame(poses[pose], scale, dy)
    frames["clip_think_0"] = poses["think"]
    frames["clip_sleep_0"] = ImageEnhance.Brightness(poses["sleep"]).enhance(0.85)
    frames["clip_alert_0"] = poses["surprised"]
    frames["clip_error_0"] = _tint(poses["sleep"], (180, 40, 40, 80))
    for old in OUT.glob("clip_*.webp"):
        old.unlink()
    for name, img in frames.items():
        _save(name, img)


if __name__ == "__main__":
    main()
