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


def _trim_bg(im: Image.Image, threshold: int = 28) -> Image.Image:
    """Knock out near-white / near-black studio backdrop via corner flood."""
    im = im.convert("RGBA")
    w, h = im.size
    pix = im.load()
    for start in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
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


def _lift(im: Image.Image, dy: int) -> Image.Image:
    canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
    canvas.paste(im, (0, -dy), im)
    return canvas


def _tilt(im: Image.Image, deg: float) -> Image.Image:
    return im.rotate(deg, resample=Image.Resampling.BICUBIC, expand=False)


def _tint(im: Image.Image, rgba: tuple[int, int, int, int]) -> Image.Image:
    overlay = Image.new("RGBA", im.size, rgba)
    return Image.alpha_composite(im, Image.composite(overlay, Image.new("RGBA", im.size), im.split()[3]))


def _save(name: str, im: Image.Image) -> None:
    dest = OUT / f"{name}.webp"
    im.save(dest, "WEBP", quality=90, method=4)
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

    frames = {
        "clip_idle_0": poses["idle"],
        "clip_idle_1": poses["blink"],
        "clip_boop_0": _squash(poses["idle"], 0.88),
        "clip_boop_1": _lift(poses["jump"], 18),
        "clip_boop_2": _squash(poses["idle"], 0.94),
        "clip_wag_0": _tilt(poses["happy_wag"], -8),
        "clip_wag_1": _tilt(poses["happy_wag"], 8),
        "clip_wag_2": _tilt(poses["happy_wag"], -6),
        "clip_wag_3": _tilt(poses["happy_wag"], 6),
        "clip_jump_0": _squash(poses["idle"], 0.9),
        "clip_jump_1": _lift(poses["jump"], 24),
        "clip_jump_2": _squash(poses["idle"], 0.95),
        "clip_think_0": poses["think"],
        "clip_sleep_0": ImageEnhance.Brightness(poses["sleep"]).enhance(0.85),
        "clip_alert_0": poses["surprised"],
        "clip_error_0": _tint(poses["sleep"], (180, 40, 40, 80)),
    }
    for name, img in frames.items():
        _save(name, img)


if __name__ == "__main__":
    main()
