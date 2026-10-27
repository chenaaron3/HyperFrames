#!/usr/bin/env python3
"""Sample a window, or dedupe a span the model already bounded.

sample  — every frame in a time window, labeled with its source time.
dedupe  — collapse consecutive frames whose graphic region does not change,
          and stamp ×N (how many source frames that cell stands for).

Neither command decides where an animation starts or ends.
"""

import argparse
import subprocess
import sys
from pathlib import Path

FONT = {
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "001", "001", "001"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
    ".": ["000", "000", "000", "000", "010"],
    "x": ["000", "101", "010", "101", "000"],
    " ": ["000", "000", "000", "000", "000"],
}


def fps_of(video):
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "csv=p=0", video,
        ],
        text=True,
    ).strip()
    num, den = out.split("/")
    return float(num) / float(den)


def frame_index(t, fps):
    return int(round(t * fps))


def decode(video, f0, f1, cell):
    h = int(round(cell * 16 / 9))
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", video,
        "-vf", f"select='between(n,{f0},{f1})',scale={cell}:{h}",
        "-vsync", "vfr", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    raw = subprocess.check_output(cmd)
    n = cell * h * 3
    frames = [raw[i * n:(i + 1) * n] for i in range(len(raw) // n)]
    return frames, cell, h


def parse_region(text):
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4:
        raise SystemExit("--region must be x,y,w,h as fractions of the frame")
    return tuple(parts)


def region_diff(a, b, w, h, region):
    """How much the graphic changed. Uses the hottest block in the region,
    so a new letter counts even when the rest of the rectangle is still."""
    x, y, rw, rh = region
    x0, y0 = int(x * w), int(y * h)
    x1, y1 = max(x0 + 1, int((x + rw) * w)), max(y0 + 1, int((y + rh) * h))
    block = 12
    hottest = 0.0
    for by in range(y0, y1, block):
        for bx in range(x0, x1, block):
            total = 0
            count = 0
            for yy in range(by, min(by + block, y1), 2):
                row = yy * w
                for xx in range(bx, min(bx + block, x1), 2):
                    p = (row + xx) * 3
                    total += abs(a[p] - b[p]) + abs(a[p + 1] - b[p + 1]) + abs(a[p + 2] - b[p + 2])
                    count += 1
            if count:
                hottest = max(hottest, total / (count * 3))
    return hottest


def stamp(canvas, mw, label, x, y, scale=2):
    for ci, ch in enumerate(label):
        glyph = FONT.get(ch)
        if glyph is None:
            continue
        ox = x + ci * 4 * scale
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit != "1":
                    continue
                for sy in range(scale):
                    for sx in range(scale):
                        px = ox + gx * scale + sx
                        py = y + gy * scale + sy
                        if 0 <= px < mw and 0 <= py < len(canvas) // (mw * 3):
                            i = (py * mw + px) * 3
                            canvas[i:i + 3] = b"\xff\xff\x00"


def write_jpg(canvas, mw, mh, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    ppm = dest.with_suffix(".ppm")
    ppm.write_bytes(f"P6\n{mw} {mh}\n255\n".encode() + bytes(canvas))
    try:
        subprocess.check_call(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(ppm), str(dest)]
        )
    finally:
        ppm.unlink(missing_ok=True)


def tile(cells, labels, cell_w, cell_h):
    n = len(cells)
    cols = 3 if n <= 6 else 4 if n <= 12 else 6 if n <= 24 else 8
    rows = (n + cols - 1) // cols
    pad = 3
    bar = 16
    mw = cols * cell_w + (cols + 1) * pad
    mh = rows * (cell_h + bar) + (rows + 1) * pad
    canvas = bytearray([18, 18, 18]) * (mw * mh)
    for i, fr in enumerate(cells):
        r, c = divmod(i, cols)
        x0 = pad + c * (cell_w + pad)
        y0 = pad + r * (cell_h + bar + pad)
        for y in range(cell_h):
            dst = ((y0 + y) * mw + x0) * 3
            canvas[dst:dst + cell_w * 3] = fr[y * cell_w * 3:(y + 1) * cell_w * 3]
        stamp(canvas, mw, labels[i], x0 + 2, y0 + cell_h + 2)
    return canvas, mw, mh


def cmd_sample(args):
    fps = fps_of(args.video)
    f0 = frame_index(args.start, fps)
    f1 = frame_index(args.end, fps)
    if f1 < f0:
        raise SystemExit("--end is before --start")
    step = args.step
    wanted = list(range(f0, f1 + 1, step))
    if len(wanted) > 12:
        raise SystemExit(
            f"{len(wanted)} frames. A sample is 12 frames at most, so each cell stays readable. "
            "Shorten the window. If the boundary is not in it, slide the window and sample again."
        )
    frames, w, h = decode(args.video, f0, f1, 220)
    picked = []
    labels = []
    for i, fr in enumerate(frames):
        if i % step:
            continue
        n = f0 + i
        picked.append(fr)
        labels.append(f"{n / fps:.2f}")
    canvas, mw, mh = tile(picked, labels, w, h)
    write_jpg(canvas, mw, mh, Path(args.output))
    print(f"frames {f0}-{f0 + len(frames) - 1} step {step} shown {len(picked)} fps {fps:.3f}")
    print(" ".join(labels))


def spans_of(text):
    """'27.30:27.47' -> (start, end) seconds, inclusive."""
    a, b = text.split(":")
    return float(a), float(b)


def cmd_dedupe(args):
    fps = fps_of(args.video)
    region = parse_region(args.region)
    groups_out = []  # (frame_bytes, count, time)

    def take(span):
        t0, t1 = spans_of(span)
        f0, f1 = frame_index(t0, fps), frame_index(t1, fps)
        frames, w, h = decode(args.video, f0, f1, 170)
        run = None
        grouped = []
        for i, fr in enumerate(frames):
            if run is None:
                run = [fr, 1, (f0 + i) / fps]
                continue
            if region_diff(run[0], fr, w, h, region) < args.threshold:
                run[1] += 1
            else:
                grouped.append(tuple(run))
                run = [fr, 1, (f0 + i) / fps]
        if run:
            grouped.append(tuple(run))
        return grouped, w, h

    inn, w, h = take(args.in_span)
    out = []
    if args.out:
        out, w, h = take(args.out)
    cells = [g[0] for g in inn + out]
    labels = [f"x{g[1]}" for g in inn + out]
    canvas, mw, mh = tile(cells, labels, w, h)
    write_jpg(canvas, mw, mh, Path(args.output))

    def fmt(groups):
        return " ".join(f"{g[2]:.2f}x{g[1]}" for g in groups)

    print(f"in {fmt(inn)}")
    if out:
        print(f"out {fmt(out)}")
    src_in = sum(g[1] for g in inn)
    src_out = sum(g[1] for g in out)
    print(f"cells {len(cells)} source {src_in + src_out} fps {fps:.3f}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sample", help="every frame in a window, labeled with its time")
    s.add_argument("--video", required=True)
    s.add_argument("--start", type=float, required=True)
    s.add_argument("--end", type=float, required=True)
    s.add_argument("--step", type=int, default=1, help="keep every Nth frame; use 1 to pick a boundary")
    s.add_argument("--output", required=True)
    s.set_defaults(func=cmd_sample)

    d = sub.add_parser("dedupe", help="collapse a span whose boundaries you already chose")
    d.add_argument("--video", required=True)
    d.add_argument("--in", dest="in_span", required=True, help="start:end seconds, inclusive")
    d.add_argument("--out", help="start:end seconds, inclusive. Omit if the move never leaves")
    d.add_argument("--region", default="0,0,1,1", help="x,y,w,h fractions. Limit this to the graphic")
    d.add_argument("--threshold", type=float, default=22.0, help="hottest block in the region below this is a duplicate")
    d.add_argument("--output", required=True)
    d.set_defaults(func=cmd_dedupe)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
