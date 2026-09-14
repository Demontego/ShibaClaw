"""Punch logo background and emit widget mood sprites."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "shibaclaw_256.png"
OUT = ROOT / "android" / "app" / "src" / "main" / "res" / "drawable"


def _flood_transparent(im: Image.Image, threshold: int = 18) -> Image.Image:
    im = im.convert("RGBA")
    w, h = im.size
    pix = im.load()
    start = (0, 0)
    r0, g0, b0, _ = pix[start]
    stack = [start]
    seen = {start}
    while stack:
        x, y = stack.pop()
        r, g, b, a = pix[x, y]
        if a == 0:
            continue
        if abs(r - r0) > threshold or abs(g - g0) > threshold or abs(b - b0) > threshold:
            continue
        pix[x, y] = (0, 0, 0, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen:
                seen.add((nx, ny))
                stack.append((nx, ny))
    return im


def _pad(im: Image.Image, px: int = 18) -> Image.Image:
    canvas = Image.new("RGBA", (im.width + px * 2, im.height + px * 2), (0, 0, 0, 0))
    canvas.paste(im, (px, px), im)
    return canvas


def _gold_glow(im: Image.Image) -> Image.Image:
    glow = im.filter(ImageFilter.GaussianBlur(8))
    overlay = Image.new("RGBA", im.size, (232, 163, 23, 0))
    alpha = glow.split()[3]
    gold = Image.new("RGBA", im.size, (232, 163, 23, 140))
    overlay.paste(gold, mask=alpha)
    out = Image.alpha_composite(overlay, im)
    return out


def _sleep(im: Image.Image) -> Image.Image:
    dark = ImageEnhance.Brightness(im).enhance(0.62)
    return dark


def _alert(im: Image.Image) -> Image.Image:
    ring = im.copy()
    draw = ImageDraw.Draw(ring)
    w, h = im.size
    draw.ellipse((6, 6, w - 7, h - 7), outline=(245, 201, 74, 220), width=5)
    return Image.alpha_composite(im, ring)


def _error(im: Image.Image) -> Image.Image:
    tint = Image.new("RGBA", im.size, (180, 40, 40, 70))
    return Image.alpha_composite(im, tint)


def _boop(im: Image.Image) -> Image.Image:
    squeezed = im.resize((im.width, int(im.height * 0.92)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
    canvas.paste(squeezed, (0, im.height - squeezed.height), squeezed)
    return canvas


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}")
    OUT.mkdir(parents=True, exist_ok=True)
    idle = _pad(_flood_transparent(Image.open(SRC)))
    variants = {
        "shiba_idle.png": idle,
        "shiba_think.png": _gold_glow(idle),
        "shiba_sleep.png": _sleep(idle),
        "shiba_alert.png": _alert(idle),
        "shiba_error.png": _error(im=idle),
        "shiba_boop.png": _boop(idle),
    }
    for name, img in variants.items():
        dest = OUT / name
        img.save(dest, "PNG")
        print(dest)


if __name__ == "__main__":
    main()
