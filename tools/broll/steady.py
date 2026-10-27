"""Search moments and keep only the steady ones.

    steady.py "reading a book" --len 1.2 [--folder X] [--limit 8]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import load_index
from search import score_moment
from shake import motion, verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--len", type=float, default=1.5)
    ap.add_argument("--folder", default="")
    ap.add_argument("--creator", action="store_true")
    ap.add_argument("--limit", type=int, default=8)
    a = ap.parse_args()
    ranked = []
    for clip in load_index().values():
        if not clip["path"].startswith(a.folder) or not clip["quality"]["usable"]:
            continue
        if a.creator and not clip["people"]["creator_visible"]:
            continue
        for m in clip["moments"]:
            if clip["duration"] - m["start"] < a.len:
                continue
            ranked.append((score_moment(a.query, clip, m), clip, m))
    ranked.sort(key=lambda r: -r[0])
    shown = 0
    for s, clip, m in ranked[:40]:
        t = max(0.0, min(m["start"] + max(0.0, (m["end"] - m["start"] - a.len) / 2), clip["duration"] - a.len - 0.05))
        v = verdict(*motion(clip["path"], t, a.len))
        if v != "ok":
            continue
        print(f"{s:5.1f}  {clip['path']}@{t:.2f}  {m['action'][:90]}")
        shown += 1
        if shown >= a.limit:
            break


if __name__ == "__main__":
    main()
