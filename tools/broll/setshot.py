#!/usr/bin/env python3
"""Set shots in a plan: setshot.py <slug> <shot>=<clip>@<in>[x<speed>] ..."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import VIDEOS_DIR  # noqa: E402

slug, *pairs = sys.argv[1:]
path = VIDEOS_DIR / slug / "plan.json"
plan = json.loads(path.read_text())
for pair in pairs:
    sid, rest = pair.split("=", 1)
    clip, _, tail = rest.rpartition("@")
    speed = 1.0
    if "x" in tail:
        tail, speed = tail.split("x")
        speed = float(speed)
    shot = plan["shots"][sid]
    shot.update(clip=clip, speed=speed)
    shot["in"] = float(tail)
    shot.pop("alts", None)
    shot["note"] = "hand pick"
path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
print(f"updated {len(pairs)} shots in {slug}")
