#!/usr/bin/env python3
"""Camera-shake score for a clip span: jitter of the global frame-to-frame motion.

  shake.py <clip-rel-path> <in> <dur>

Smooth pans and walks change velocity slowly and score low; handheld wobble scores high.
Score is mean |change in velocity| in px/frame at 1080 wide.
"""

import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BROLL_ROOT  # noqa: E402

W, H = 270, 480
SHAKY = 8.0


def _frames(src, t_in, dur):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t_in:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
         "-vf", f"fps=30,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)


def _shift(a, b, win):
    fa, fb = np.fft.fft2(a * win), np.fft.fft2(b * win)
    r = fa * np.conj(fb)
    r /= np.abs(r) + 1e-6
    c = np.fft.ifft2(r).real
    y, x = np.unravel_index(np.argmax(c), c.shape)

    def sub(m, p, z):
        d = m - 2 * z + p
        return 0.0 if abs(d) < 1e-9 else 0.5 * (m - p) / d

    dx = sub(c[y, (x - 1) % W], c[y, (x + 1) % W], c[y, x])
    dy = sub(c[(y - 1) % H, x], c[(y + 1) % H, x], c[y, x])
    if y > H // 2:
        y -= H
    if x > W // 2:
        x -= W
    return x + dx, y + dy


FAST = 22.0


def motion(rel, t_in, dur):
    """(median pan speed, jitter) in px/frame at 1080 wide."""
    fr = _frames(BROLL_ROOT / rel, t_in, dur)
    if len(fr) < 4:
        return 0.0, 0.0
    win = np.outer(np.hanning(H), np.hanning(W)).astype(np.float32)
    v = np.array([_shift(fr[i], fr[i - 1], win) for i in range(1, len(fr))], dtype=np.float32) * 1080 / W
    speed = float(np.median(np.linalg.norm(v, axis=1)))
    jitter = float(np.mean(np.linalg.norm(np.diff(v, axis=0), axis=1)))
    return round(speed, 1), round(jitter, 2)


def verdict(speed, jitter):
    if speed > FAST:
        return "fast pan"
    if jitter > SHAKY:
        return "shaky"
    return "ok"


if __name__ == "__main__":
    rel, t_in, dur = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    s, j = motion(rel, t_in, dur)
    print(f"speed {s} jitter {j} -> {verdict(s, j)}")
