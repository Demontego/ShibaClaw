"""Build widget clips from sprite_src.

Every frame shares one stage: the sit is scaled to leave headroom, then
motion is eased so a clip starts and ends on that sit.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "sprite_src"
OUT = ROOT / "app" / "src" / "main" / "res" / "drawable-nodpi"
BASE = 0.90


def feet(src: Image.Image) -> tuple[float, float]:
    box = src.getchannel("A").getbbox()
    if not box:
        return src.width / 2, src.height - 1
    return (box[0] + box[2]) / 2, box[3] - 1


def render(
    src: Image.Image,
    anchor: tuple[float, float],
    angle: float = 0,
    sx: float = 1,
    sy: float = 1,
    ox: float = 0,
    oy: float = 0,
) -> Image.Image:
    sx *= BASE
    sy *= BASE
    ax, ay = anchor
    rad = math.radians(angle)
    cos, sin = math.cos(rad), math.sin(rad)
    a = cos / sx
    b = sin / sx
    d = -sin / sy
    e = cos / sy
    c = ax - a * (ax + ox) - b * (ay + oy)
    f = ay - d * (ax + ox) - e * (ay + oy)
    return src.transform(
        src.size,
        Image.Transform.AFFINE,
        (a, b, c, d, e, f),
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )


def save(im: Image.Image, name: str) -> None:
    im.save(OUT / name, "WEBP", quality=82, method=6, alpha_quality=90)


def fit_existing(src: Image.Image, anchor: tuple[float, float], name: str) -> None:
    if name.startswith(("clip_sway_", "clip_bow_", "clip_hop_", "clip_breathe_")):
        return
    save(render(src, anchor), name)


def sequence(src: Image.Image, anchor: tuple[float, float], prefix: str, poses: list[tuple]) -> None:
    for i, (angle, sx, sy, ox, oy) in enumerate(poses):
        if i in (0, len(poses) - 1):
            frame = render(src, anchor)
        else:
            frame = render(src, anchor, angle, sx, sy, ox, oy)
        save(frame, f"{prefix}_{i}.webp")


def arc(n: int) -> list[float]:
    return [math.sin((i / (n - 1)) * math.pi) for i in range(n)]


def sway(n: int = 8) -> list[tuple]:
    return [(8 * u, 1, 1, 2 * u, -4 * u) for u in arc(n)]


def bow(n: int = 8) -> list[tuple]:
    return [(13 * u, 1 + 0.03 * u, 1 - 0.07 * u, 0, 8 * u) for u in arc(n)]


def hop(n: int = 8) -> list[tuple]:
    # Squat, leave, hang in the headroom, land. Ends are replaced by the sit.
    lift = (0, 6, -14, -26, -24, -8, 7, 0)
    squash = (0, 0.07, -0.02, 0, 0, 0.02, 0.08, 0)
    poses = []
    for i in range(n):
        s = squash[i]
        poses.append((0, 1 + s, 1 - s, 0, lift[i]))
    return poses


def breathe(n: int = 8) -> list[tuple]:
    return [(0, 1 - 0.03 * u, 1 + 0.055 * u, 0, -5 * u) for u in arc(n)]


def loop(src: Image.Image, anchor: tuple[float, float], prefix: str, poses: list[tuple]) -> None:
    for i, (angle, sx, sy, ox, oy) in enumerate(poses):
        save(render(src, anchor, angle, sx, sy, ox, oy), f"{prefix}_{i}.webp")


def stroll(n: int = 8) -> list[tuple]:
    poses = []
    for i in range(n):
        t = i / n
        rock = math.sin(t * math.tau)
        step = abs(math.sin(t * math.tau * 2))
        poses.append((rock * 7, 1 + 0.02 * abs(rock), 1 - 0.04 * step, rock * 3, -10 * step))
    return poses


def sleep_breath(n: int = 8) -> list[tuple]:
    poses = []
    for i in range(n):
        u = math.sin((i / n) * math.tau)
        inhale = max(u, 0)
        poses.append((u * 2, 1 - 0.02 * inhale, 1 + 0.05 * inhale, 0, -3 * inhale))
    return poses


def wipe(prefix: str, keep: int) -> None:
    for path in OUT.glob(f"{prefix}_*.webp"):
        idx = int(path.stem.rsplit("_", 1)[-1])
        if idx >= keep:
            path.unlink()


def main() -> None:
    idle = Image.open(SRC / "clip_idle_0.webp").convert("RGBA")
    anchor = feet(idle)
    for path in sorted(SRC.glob("clip_*.webp")):
        im = Image.open(path).convert("RGBA")
        fit_existing(im, feet(im), path.name)
    sequence(idle, anchor, "clip_sway", sway())
    sequence(idle, anchor, "clip_bow", bow())
    sequence(idle, anchor, "clip_hop", hop())
    sequence(idle, anchor, "clip_breathe", breathe())
    loop(idle, anchor, "clip_walk", stroll())
    sleep = Image.open(SRC / "clip_sleep_0.webp").convert("RGBA")
    loop(sleep, feet(sleep), "clip_sleep", sleep_breath())
    for prefix in ("clip_sway", "clip_bow", "clip_hop", "clip_breathe", "clip_walk", "clip_sleep"):
        wipe(prefix, 8)
    print("wrote clips")


if __name__ == "__main__":
    main()
