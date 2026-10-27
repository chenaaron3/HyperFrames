"""Shared paths and helpers for the b-roll tools."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX_DIR = ROOT / "broll-index" / "clips"
CACHE_DIR = ROOT / ".broll-cache"
FORMATS_DIR = ROOT / "formats"
VIDEOS_DIR = ROOT / "videos"
STORYBOARDS_DIR = ROOT / "storyboards"

VIDEO_EXTS = {".mov", ".mp4", ".m4v"}


def load_env():
    env_file = ROOT / ".env"
    if env_file.exists():
        for raw in env_file.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_env()

BROLL_ROOT = Path(os.environ.get("BROLL_ROOT", "/Users/aaron/Documents/Broll"))


def list_clips():
    return sorted(
        p.relative_to(BROLL_ROOT).as_posix()
        for p in BROLL_ROOT.rglob("*")
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS and not p.name.startswith(".")
    )


def clip_key(rel):
    return rel.replace("/", "__")


def index_path(rel):
    return INDEX_DIR / f"{clip_key(rel)}.json"


def load_index():
    out = {}
    for f in sorted(INDEX_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        out[data["path"]] = data
    return out


def probe(path):
    """Display-oriented width/height (rotation applied), fps, duration."""
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate:stream_side_data=rotation:format=duration",
            "-of", "json", str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    info = json.loads(proc.stdout)
    stream = info["streams"][0]
    w, h = stream["width"], stream["height"]
    rotation = 0
    for side in stream.get("side_data_list", []):
        if "rotation" in side:
            rotation = int(side["rotation"])
    if abs(rotation) in (90, 270):
        w, h = h, w
    num, den = stream["r_frame_rate"].split("/")
    return {
        "width": w,
        "height": h,
        "fps": round(int(num) / int(den), 3),
        "duration": round(float(info["format"]["duration"]), 3),
    }


def file_fingerprint(path):
    st = Path(path).stat()
    return hashlib.sha1(f"{path}:{st.st_size}:{int(st.st_mtime)}".encode()).hexdigest()[:16]


def load_format(fmt_id):
    for d in sorted(FORMATS_DIR.iterdir()):
        f = d / "format.json"
        if f.exists():
            data = json.loads(f.read_text())
            if data["id"] == str(fmt_id) or d.name == str(fmt_id):
                data["_dir"] = d
                return data
    raise SystemExit(f"no format '{fmt_id}' in formats/")
