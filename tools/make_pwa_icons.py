"""Generate the PWA icon set without any third-party dependency.

Draws the HisabSetu mic mark with signed-distance fields and supersampled
coverage, then writes PNGs using only zlib + struct (no Pillow in this project).

    python tools/make_pwa_icons.py

Outputs (static/icons/):
    icon-192.png, icon-512.png        purpose "any"     (rounded square, gradient)
    maskable-512.png                  purpose "maskable" (full bleed, safe zone)
    apple-touch-icon.png              180x180 for iOS
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "static" / "icons"

TOP = (0x14, 0x90, 0x6C)      # gradient start
BOTTOM = (0x06, 0x40, 0x2F)   # gradient end
WHITE = (0xFF, 0xFF, 0xFF)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def _sd_round_rect(x: float, y: float, cx: float, cy: float,
                   hw: float, hh: float, r: float) -> float:
    qx = abs(x - cx) - (hw - r)
    qy = abs(y - cy) - (hh - r)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    inside = min(max(qx, qy), 0.0)
    return outside + inside - r


def _sd_segment(x: float, y: float, ax: float, ay: float,
                bx: float, by: float, half: float) -> float:
    px, py = x - ax, y - ay
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    t = 0.0 if denom == 0 else _clamp((px * dx + py * dy) / denom)
    return math.hypot(px - dx * t, py - dy * t) - half


def _cover(sd: float, px: float) -> float:
    """Antialiased coverage from a signed distance and the pixel size."""
    return _clamp(0.5 - sd / px)


def _mic_mark(x: float, y: float, s: float) -> float:
    """White mic glyph coverage at unit coordinates (0..1), scaled by s."""
    # capsule body
    d = _sd_round_rect(x, y, 0.5 * s + (1 - s) / 2, 0.40 * s + (1 - s) / 2,
                       0.095 * s, 0.145 * s, 0.095 * s)
    # cradle: bottom half of a ring under the capsule
    cx = 0.5 * s + (1 - s) / 2
    cy = 0.40 * s + (1 - s) / 2
    ring = abs(math.hypot(x - cx, y - cy) - 0.185 * s) - 0.019 * s
    d = min(d, max(ring, cy - y))
    # stem + base
    d = min(d, _sd_segment(x, y, cx, 0.60 * s + (1 - s) / 2,
                           cx, 0.685 * s + (1 - s) / 2, 0.0185 * s))
    d = min(d, _sd_segment(x, y, 0.5 - 0.085 * s, 0.685 * s + (1 - s) / 2,
                           0.5 + 0.085 * s, 0.685 * s + (1 - s) / 2, 0.0185 * s))
    return d


def render(size: int, maskable: bool) -> bytes:
    ss = 3  # supersampling factor
    n = size * ss
    px = 1.0 / n
    rows: list[bytearray] = []

    radius = 0.0 if maskable else 0.21 * n
    glyph_scale = 0.62 if maskable else 1.0

    for yy in range(size):
        row = bytearray()
        for xx in range(size):
            r_acc = g_acc = b_acc = a_acc = 0.0
            for sy in range(ss):
                for sx in range(ss):
                    u = (xx * ss + sx + 0.5) / n
                    v = (yy * ss + sy + 0.5) / n
                    if maskable:
                        bg_cov = 1.0
                    else:
                        bg_sd = _sd_round_rect(u, v, 0.5, 0.5, 0.5, 0.5, radius / n)
                        bg_cov = _cover(bg_sd, px)
                    if bg_cov <= 0.0:
                        continue
                    t = _clamp((u + v) / 2.0)
                    cr = TOP[0] + (BOTTOM[0] - TOP[0]) * t
                    cg = TOP[1] + (BOTTOM[1] - TOP[1]) * t
                    cb = TOP[2] + (BOTTOM[2] - TOP[2]) * t
                    mark = _cover(_mic_mark(u, v, glyph_scale), px)
                    cr += (WHITE[0] - cr) * mark
                    cg += (WHITE[1] - cg) * mark
                    cb += (WHITE[2] - cb) * mark
                    r_acc += cr * bg_cov
                    g_acc += cg * bg_cov
                    b_acc += cb * bg_cov
                    a_acc += bg_cov
            samples = ss * ss
            alpha = a_acc / samples
            if alpha <= 0.0:
                row += bytes((0, 0, 0, 0))
            else:
                row += bytes((
                    int(round(r_acc / a_acc)),
                    int(round(g_acc / a_acc)),
                    int(round(b_acc / a_acc)),
                    int(round(alpha * 255)),
                ))
        rows.append(row)

    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    return _png(size, size, raw)


def _png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = [
        ("icon-192.png", 192, False),
        ("icon-512.png", 512, False),
        ("maskable-512.png", 512, True),
        ("apple-touch-icon.png", 180, False),
    ]
    for name, size, maskable in targets:
        data = render(size, maskable)
        (OUT_DIR / name).write_bytes(data)
        print(f"wrote {OUT_DIR / name} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
