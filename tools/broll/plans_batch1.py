"""Batch 1 plans: lines adapted for Aaron + per-shot search hints."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PLANS = {
    "blessed-v1": {
        "format": "easy-15",
        "textY": 0.5,
        "lines": {},
        "queries": {
            "s1": "walking selfie street sunny city",
            "s2": "looking up buildings sky skyscrapers",
            "s3": "eating pizza plate food",
            "s4": "friends laughing together group",
            "s5": "climbing bouldering wall send",
            "s6": "smiling selfie outdoors happy",
        },
        "caption": "Some days in this city are loud and hard. But I have a roof over my head, food on my plate, people who show up for me, and a body that still lets me climb. That's a lot. 🤍",
    },
    "complain-v1": {
        "format": "easy-10",
        "textY": 0.5,
        "lines": {"l2": "you complain about the subway\nbecause you can go anywhere"},
        "queries": {
            "s1": "working laptop desk tired",
            "s2": "subway train commute riding",
            "s3": "eating meal table food",
            "s4": "climbing bouldering resting tired",
            "s5": "cooking kitchen washing",
            "s6": "morning routine bathroom getting ready",
            "s7": "friends laughing hanging out",
            "s8": "selfie outdoors reflective calm",
        },
        "caption": "Striving for more but forgetting what you once wished for is a vicious cycle.",
    },
    "effort-v1": {
        "format": "opinion-20",
        "textY": 0.5,
        "lines": {},
        "queries": {
            "s1": "standing home apartment tired contemplative",
            "s2": "working laptop desk focused",
            "s3": "climbing bouldering attempt hard move",
            "s4": "walking park trees outdoors",
            "s5": "climbing wall reaching hold",
            "s6": "walking chinatown street city",
            "s7": "friends talking conversation laughing",
            "s8": "friends outdoors rain walking",
            "s9": "cooking kitchen preparing food",
            "s10": "hangboard training grip",
            "s11": "working laptop typing",
        },
        "caption": "The struggle is the point.",
    },
    "silent-flexes-v1": {
        "format": "opinion-22",
        "textY": 0.5,
        "lines": {"l5": "admitting when you're wrong", "l6": "being kind to strangers", "l8": "keeping promises", "l9": "walking away from disrespect", "l10": "being financially responsible", "l11": "knowing when to rest", "l12": "always learning", "l13": "not oversharing", "l14": "being happy for others"},
        "queries": {
            "s1": "walking selfie street morning",
            "s2": "walking sidewalk city sunny",
            "s3": "subway exiting train station",
            "s4": "bathroom morning routine mirror",
            "s5": "working laptop desk",
            "s6": "coffee making kitchen close",
            "s7": "skyline sunset city view",
            "s8": "sitting alone bench park",
            "s9": "climbing bouldering gym",
            "s10": "walking coffee street",
            "s11": "restaurant ordering counter food",
            "s12": "lying couch bed resting relaxing",
            "s13": "apartment window light calm",
            "s14": "kitchen drinking water",
            "s15": "smiling selfie calm",
        },
        "caption": "None of these get likes. All of them change your life.",
    },
    "do-it-scared-v1": {
        "format": "opinion-11",
        "textY": 0.5,
        "lines": {},
        "queries": {
            "s1": "subway selfie window pensive",
            "s2": "climbing overhang hard scary move",
            "s3": "walking alone park smiling",
            "s4": "rain umbrella walking uncertain",
            "s5": "subway train commute",
            "s6": "running walking away path park",
        },
        "caption": "Stop waiting for the perfect time.",
    },
    "alone-v1": {
        "format": "relatable-21",
        "textY": 0.5,
        "lines": {"l2": "Aren't you afraid of being\ndependent on others for the rest\nof your life??"},
        "queries": {
            "s1": "cafe drink sitting alone table",
            "s2": "walking street alone city",
            "s3": "rain umbrella standing street",
            "s4": "eating alone restaurant meal",
            "s5": "subway coffee selfie",
        },
        "caption": "Table for one, every time.",
    },
}


def main():
    only = sys.argv[1:] or list(PLANS)
    for slug in only:
        spec = PLANS[slug]
        subprocess.run([str(ROOT / "tools/broll.sh"), "new", spec["format"], slug, "--force"], check=True)
        path = ROOT / "videos" / slug / "plan.json"
        plan = json.loads(path.read_text())
        plan["lines"].update(spec["lines"])
        plan["textY"] = spec.get("textY")
        plan["caption"] = spec["caption"]
        for sid, q in spec["queries"].items():
            plan["shots"][sid]["query"] = q
        path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
        subprocess.run([str(ROOT / "tools/broll.sh"), "autopick", slug], check=True)
        subprocess.run([str(ROOT / "tools/broll.sh"), "storyboard", slug], check=True)


if __name__ == "__main__":
    main()
