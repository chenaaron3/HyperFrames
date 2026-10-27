#!/usr/bin/env python3
"""Search the b-roll index for moments.

  tools/broll.sh search "laughing friends restaurant"
  tools/broll.sh search "eating bowl" --camera selfie --min-score 3 --min-len 2.5
  tools/broll.sh search --clip SelfShots/Eating/IMG_1234.MOV   # dump one clip
  tools/broll.sh search --stats                                # what's indexed
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_index  # noqa: E402

STOP = {"a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "my", "is", "with", "for"}


def words(text):
    return [w for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in STOP]


def stem(w):
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def score_moment(query, clip, m):
    q = {stem(w) for w in words(query)}
    if not q:
        return 0.0
    fields = [
        (" ".join(m["good_for"]), 3.0),
        (m["action"] + " " + m["emotion"], 2.0),
        (" ".join(clip["tags"]), 1.5),
        (clip["summary"] + " " + clip["location"] + " " + " ".join(clip["mood"]), 1.0),
        (clip["folder"].replace("/", " "), 1.0),
    ]
    hits = 0.0
    for text, weight in fields:
        have = {stem(w) for w in words(text)}
        hits += weight * len(q & have)
    return hits / len(q) + 0.25 * m["score"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--folder", help="only clips under this folder prefix")
    ap.add_argument("--camera", help="camera style contains (selfie, tripod, friend, pov…)")
    ap.add_argument("--setting", choices=["indoor", "outdoor", "vehicle", "mixed"])
    ap.add_argument("--time", dest="time_of_day", choices=["day", "golden_hour", "night", "indoor_unknown"])
    ap.add_argument("--creator", action="store_true", help="creator visible on screen")
    ap.add_argument("--min-score", type=int, default=1)
    ap.add_argument("--min-len", type=float, default=0.0, help="moment length in seconds")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--clip", help="print one clip's full annotation")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    index = load_index()
    if not index:
        sys.exit("broll-index is empty. Run tools/broll.sh annotate first.")

    if args.clip:
        print(json.dumps(index[args.clip], indent=2, ensure_ascii=False))
        return

    if args.stats:
        folders = Counter(c["folder"] for c in index.values())
        moments = sum(len(c["moments"]) for c in index.values())
        print(f"{len(index)} clips, {moments} moments")
        for f, n in sorted(folders.items()):
            print(f"  {n:4d}  {f}")
        return

    rows = []
    for clip in index.values():
        if args.folder and not clip["folder"].startswith(args.folder.rstrip("/")):
            continue
        if args.camera and args.camera not in clip["camera"]["style"]:
            continue
        if args.setting and clip["setting"] != args.setting:
            continue
        if args.time_of_day and clip["time_of_day"] != args.time_of_day:
            continue
        if args.creator and not clip["people"]["creator_visible"]:
            continue
        if not clip["quality"]["usable"]:
            continue
        for m in clip["moments"]:
            if m["score"] < args.min_score or (m["end"] - m["start"]) < args.min_len:
                continue
            s = score_moment(args.query, clip, m) if args.query else m["score"]
            rows.append((s, clip, m))
    rows.sort(key=lambda r: -r[0])
    rows = rows[: args.limit]

    if args.json:
        print(json.dumps([{"rank": round(s, 2), "path": c["path"], **m} for s, c, m in rows], indent=2, ensure_ascii=False))
        return
    for s, c, m in rows:
        print(
            f"{s:5.2f}  {c['path']}  [{m['start']:.1f}-{m['end']:.1f}] q{m['score']}  "
            f"{c['camera']['style']}/{c['camera']['framing']}  {m['action']} | {m['emotion']} | {', '.join(m['good_for'][:4])}"
        )


if __name__ == "__main__":
    main()
