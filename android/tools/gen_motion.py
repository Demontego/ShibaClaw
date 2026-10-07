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


def smooth(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


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


def sway(n: int = 16) -> list[tuple]:
    poses = []
    for i in range(n):
        t = i / (n - 1)
        angle = math.sin(t * math.tau) * 7.0
        poses.append((angle, 1, 1, 0, 0))
    return poses


def bow(n: int = 14) -> list[tuple]:
    poses = []
    for i in range(n):
        t = i / (n - 1)
        u = math.sin(t * math.pi)
        poses.append((u * 11, 1 + u * 0.04, 1 - u * 0.07, 0, u * 3))
    return poses


def hop(n: int = 16) -> list[tuple]:
    poses = []
    for i in range(n):
        t = i / (n - 1)
        if t < 0.2:
            u = smooth(t / 0.2)
            poses.append((0, 1 + 0.05 * u, 1 - 0.07 * u, 0, 0))
        elif t < 0.78:
            u = math.sin(((t - 0.2) / 0.58) * math.pi)
            poses.append((0, 1.05 - 0.06 * u, 0.93 + 0.08 * u, 0, -20 * u))
        else:
            u = smooth((t - 0.78) / 0.22)
            poses.append((0, 1.05 - 0.05 * u, 0.93 + 0.07 * u, 0, 0))
    return poses


def breathe(n: int = 14) -> list[tuple]:
    poses = []
    for i in range(n):
        t = i / (n - 1)
        u = math.sin(t * math.pi)
        poses.append((0, 1 - 0.02 * u, 1 + 0.045 * u, 0, -3 * u))
    return poses


def loop(src: Image.Image, anchor: tuple[float, float], prefix: str, poses: list[tuple]) -> None:
    for i, (angle, sx, sy, ox, oy) in enumerate(poses):
        save(render(src, anchor, angle, sx, sy, ox, oy), f"{prefix}_{i}.webp")


def stroll(n: int = 16) -> list[tuple]:
    poses = []
    for i in range(n):
        t = i / n
        step = math.sin(t * math.tau * 2)
        poses.append((math.sin(t * math.tau) * 4, 1, 1, math.sin(t * math.tau) * 10, -5 * abs(step)))
    return poses


def sleep_breath(n: int = 12) -> list[tuple]:
    poses = []
    for i in range(n):
        u = math.sin((i / n) * math.tau)
        poses.append((0, 1 - 0.012 * u, 1 + 0.03 * u, 0, 0))
    return poses


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
    print("wrote clips")


if __name__ == "__main__":
    main()
