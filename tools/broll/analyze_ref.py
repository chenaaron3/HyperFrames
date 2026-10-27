#!/usr/bin/env python3
"""Analyze format-book references with Gemini + ffmpeg and draft formats/<id>/format.json.

  tools/broll.sh analyze-refs                       # every reference in the book
  tools/broll.sh analyze-refs --only advice-3 easy-15
  tools/broll.sh analyze-refs --draft-only          # re-draft format.json from saved analyses

Writes references/viral-formats/<id>.mp4, <id>.analysis.json, and formats/<id>/{format.json,brief.txt}.
"""

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import FORMATS_DIR, ROOT  # noqa: E402

BOOK = Path(os.environ.get("FORMAT_BOOK", "/Users/aaron/Downloads/100 Viral Formats (Format Book)"))
REF_DIR = ROOT / "references" / "viral-formats"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
CATEGORIES = {"Easy to use format": "easy", "Advice": "advice", "Opinion": "opinion", "Relatable": "relatable", "Storytelling": "story"}


class TextLine(BaseModel):
    start: float
    end: float
    text: str = Field(description="Exact on-screen text, preserving case, punctuation, emoji and manual line breaks as \\n")
    y_center: float = Field(description="Vertical centre of the text block as a fraction of frame height (0 top, 1 bottom)")
    style: Literal["plain_white_outline", "plain_white_shadow", "white_box_black_text", "black_box_white_text", "other"]


class Shot(BaseModel):
    start: float
    end: float
    description: str = Field(description="What is shown: subject, action, place")
    camera: str = Field(description="selfie / tripod / filmed by friend / POV / mirror / top-down …")
    requirement: str = Field(description="What b-roll the creator must have to recreate this shot, generalized (e.g. 'eating a meal, selfie', 'laughing with friends')")


class RefAnalysis(BaseModel):
    kind: Literal["broll_with_text", "talking_head", "voiceover_over_broll", "skit_acting", "photo_slideshow", "screen_recording", "other"]
    creator_speaks: bool = Field(description="A person talks (to camera or voiceover) and the words matter")
    audio: str = Field(description="music only / speech / music + speech / ambient")
    summary: str
    special_requirements: list[str] = Field(description="Hard-to-substitute needs: props, specific people, old photos of younger self, car, pets, specific location, a specific stunt. Empty if generic lifestyle b-roll works.")
    text_lines: list[TextLine]
    shots: list[Shot]
    reusable_with_generic_broll: bool = Field(description="Could someone recreate this using only their own existing lifestyle b-roll plus new on-screen text (no speaking, no new filming)?")
    reuse_notes: str


PROMPT = """You are auditing a viral short-form video format so it can be recreated with another creator's existing b-roll library.
The creator's library: about 600 vertical iPhone clips of a young man in New York: walking (1st and 3rd person), subway,
eating, cooking, working on a laptop, morning routine, chilling at home, climbing gym (bouldering, hangboard, shoes),
apartment tours, Central Park / Chinatown / Dumbo / Upper East Side cinematic shots, rainy day with friends, Brooklyn at night.

The format book's notes for this video:
---
{brief}
---

Watch the video. Report every on-screen text line with accurate start/end seconds and its exact wording, every shot (cut to cut)
with what it shows, and whether this format can be recreated purely with existing b-roll + new text (no talking, no new filming)."""


def docx_text(path):
    return subprocess.run(["textutil", "-convert", "txt", "-stdout", str(path)], capture_output=True, text=True).stdout


def find_refs():
    refs = []
    for cat_dir, prefix in CATEGORIES.items():
        base = BOOK / cat_dir
        if not base.exists():
            continue
        for d in sorted(base.iterdir()):
            if not d.is_dir():
                continue
            num = re.sub(r"\D", "", d.name)
            vids = [p for p in d.iterdir() if p.suffix.lower() in (".mp4", ".mov")]
            docs = [p for p in d.iterdir() if p.suffix.lower() == ".docx"]
            if not vids:
                continue
            refs.append({
                "id": f"{prefix}-{num}",
                "category": cat_dir,
                "video": vids[0],
                "docx": docs[0] if docs else None,
                "extra_audio": [str(p) for p in d.iterdir() if p.suffix.lower() in (".mp3", ".m4a", ".wav")],
            })
    return refs


def stream_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration,width,height", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    s = json.loads(out)["streams"][0]
    return float(s["duration"]), s["width"], s["height"]


def scene_cuts(path, thresh=0.25):
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-vf", f"select='gt(scene,{thresh})',showinfo", "-an", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    return [round(float(t), 3) for t in re.findall(r"pts_time:([0-9.]+)", err)]


def frames_gray(path, w=360, h=640):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def frame_at(path, t):
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True,
    ).stdout
    return np.asarray(Image.open(io.BytesIO(out)).convert("RGB")).astype(int)


def measure_text(path, t, y_hint):
    """Find the white text block nearest y_hint; return (y_center_frac, line_px_height_frac, n_lines)."""
    a = frame_at(path, t)
    h = a.shape[0]
    white = a.min(axis=2) > 232
    rows = white.sum(axis=1)
    idx = np.where(rows > a.shape[1] * 0.02)[0]
    if len(idx) == 0:
        return None
    bands, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > 4:
            bands.append((s, p))
            s = i
        p = i
    bands.append((s, p))
    bands = [b for b in bands if 0.008 * h <= b[1] - b[0] <= 0.06 * h]
    if not bands:
        return None
    target = y_hint * h
    best = min(bands, key=lambda b: abs((b[0] + b[1]) / 2 - target))
    group = [best]
    for b in sorted(bands, key=lambda b: abs((b[0] + b[1]) / 2 - (best[0] + best[1]) / 2)):
        if b is best:
            continue
        if min(abs(b[0] - g[1]) for g in group) < 0.035 * h or min(abs(g[0] - b[1]) for g in group) < 0.035 * h:
            group.append(b)
    top, bottom = min(g[0] for g in group), max(g[1] for g in group)
    glyph = float(np.median([g[1] - g[0] for g in group]))
    return (top + bottom) / 2 / h, glyph / h, len(group)


def ask_gemini(client, video: Path, brief: str):
    from google.genai import types

    data = video.read_bytes()
    uploaded = None
    if len(data) <= 18 * 1024 * 1024:
        part = types.Part(inline_data=types.Blob(data=data, mime_type="video/mp4"), video_metadata=types.VideoMetadata(fps=4))
    else:
        uploaded = client.files.upload(file=str(video), config={"mime_type": "video/mp4"})
        while uploaded.state.name == "PROCESSING":
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)
        part = types.Part(file_data=types.FileData(file_uri=uploaded.uri, mime_type="video/mp4"), video_metadata=types.VideoMetadata(fps=4))
    try:
        for attempt in range(5):
            try:
                resp = client.models.generate_content(
                    model=MODEL,
                    contents=[types.Content(role="user", parts=[part, types.Part(text=PROMPT.format(brief=brief[:6000]))])],
                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RefAnalysis, temperature=0.1),
                )
                return resp.parsed.model_dump()
            except Exception as exc:
                if attempt == 4:
                    raise
                time.sleep(5 * 2 ** attempt)
                print(f"  retry: {exc}", file=sys.stderr)
    finally:
        if uploaded is not None:
            client.files.delete(name=uploaded.name)


def snap(t, cuts, text_events):
    for events, tol in ((cuts, 0.4), (text_events, 0.15)):
        near = [e for e in events if abs(e - t) <= tol]
        if near:
            return min(near, key=lambda e: abs(e - t))
    return t


def text_change_events(path):
    fr = frames_gray(path)
    white = fr.min(axis=3) > 230
    diffs = np.array([(white[i] ^ white[i - 1]).sum() for i in range(1, len(white))])
    med = np.median(diffs) if len(diffs) else 0
    return [round(i / 30, 3) for i, d in enumerate(diffs, start=1) if d > max(400, 6 * med)]


def analyze(client, ref, force):
    REF_DIR.mkdir(parents=True, exist_ok=True)
    mp4 = REF_DIR / f"{ref['id']}.mp4"
    if not mp4.exists():
        if ref["video"].suffix.lower() == ".mp4":
            shutil.copy2(ref["video"], mp4)
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ref["video"]), "-c:v", "libx264", "-crf", "18", "-c:a", "aac", str(mp4)], check=True)
    out = REF_DIR / f"{ref['id']}.analysis.json"
    if out.exists() and not force:
        return json.loads(out.read_text())
    brief = docx_text(ref["docx"]) if ref["docx"] else ""
    duration, w, h = stream_duration(mp4)
    result = {
        "id": ref["id"],
        "category": ref["category"],
        "source": str(ref["video"]),
        "brief": brief,
        "extra_audio": ref["extra_audio"],
        "duration": round(duration, 3),
        "width": w,
        "height": h,
        "cuts": scene_cuts(mp4),
        "text_events": text_change_events(mp4),
        "model": MODEL,
        "gemini": ask_gemini(client, mp4, brief),
    }
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def draft_format(a):
    g = a["gemini"]
    dur = a["duration"]
    mp4 = REF_DIR / f"{a['id']}.mp4"
    bounds = [0.0] + [c for c in a["cuts"] if 0.2 < c < dur - 0.2] + [dur]
    shots = []
    for i in range(len(bounds) - 1):
        s, e = bounds[i], bounds[i + 1]
        if e - s < 0.15:
            continue
        mid = (s + e) / 2
        gs = min(g["shots"], key=lambda x: 0 if x["start"] <= mid < x["end"] else min(abs(x["start"] - mid), abs(x["end"] - mid))) if g["shots"] else None
        shots.append({
            "id": f"s{len(shots) + 1}",
            "start": round(s, 3),
            "end": round(e, 3),
            "brief": f"{gs['requirement']} (ref: {gs['description']}; {gs['camera']})" if gs else "",
        })

    lines = []
    for tl in sorted(g["text_lines"], key=lambda x: x["start"]):
        s = round(max(0.0, snap(tl["start"], a["cuts"], a["text_events"])), 3)
        e = round(min(dur, snap(tl["end"], a["cuts"], a["text_events"])), 3)
        if s < 0.2:
            s = 0.0
        if dur - e < 0.3:
            e = dur
        if e - s < 0.2:
            continue
        m = measure_text(mp4, (s + e) / 2, tl["y_center"])
        y = round(m[0], 3) if m and abs(m[0] - tl["y_center"]) < 0.12 else round(tl["y_center"], 3)
        size = None
        if m:
            size = round(m[1] * 1920 / 0.8)
        lines.append({"id": f"l{len(lines) + 1}", "start": s, "end": e, "ref": tl["text"], "y": y, "measuredSize": size, "style": tl["style"], "guide": ""})

    for i in range(1, len(lines)):
        prev = lines[i - 1]
        stacked = abs(lines[i]["y"] - prev["y"]) > 0.05 and lines[i]["end"] <= prev["end"] + 0.05
        if lines[i]["start"] < prev["end"] and not stacked:
            prev["end"] = lines[i]["start"]

    for sh in shots:
        mid = (sh["start"] + sh["end"]) / 2
        cover = [l for l in lines if l["start"] <= mid < l["end"]]
        sh["line"] = cover[0]["id"] if cover else None

    sizes = [l["measuredSize"] for l in lines if l["measuredSize"]]
    base = int(np.median(sizes)) if sizes else 44
    styles = [l["style"] for l in lines]
    style = max(set(styles), key=styles.count) if styles else "plain_white_outline"
    return {
        "id": a["id"],
        "name": (g["text_lines"][0]["text"].replace("\n", " ")[:60] if g["text_lines"] else g["summary"][:60]),
        "reference": f"references/viral-formats/{a['id']}.mp4",
        "source": a["source"],
        "duration": dur,
        "music": {"from": "reference", "title": (re.search(r"Music:\s*\n?\s*(.+)", a["brief"]) or [None, "original audio"])[1].strip()},
        "text": {"y": lines[0]["y"] if lines else 0.5, "size": max(46, min(64, base)), "weight": 700, "lineHeight": 1.4, "maxWidth": 900,
                 "style": "box" if style == "white_box_black_text" else "outline"},
        "lines": lines,
        "shots": shots,
        "audit": {
            "kind": g["kind"],
            "creatorSpeaks": g["creator_speaks"],
            "audio": g["audio"],
            "special": g["special_requirements"],
            "reusable": g["reusable_with_generic_broll"],
            "notes": g["reuse_notes"],
            "summary": g["summary"],
        },
        "caption": {"ref": "", "guide": ""},
        "draft": True,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--draft-only", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    refs = find_refs()
    if args.only:
        refs = [r for r in refs if r["id"] in args.only]
    analyses = []
    if args.draft_only:
        analyses = [json.loads((REF_DIR / f"{r['id']}.analysis.json").read_text()) for r in refs if (REF_DIR / f"{r['id']}.analysis.json").exists()]
    else:
        from google import genai

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(analyze, client, r, args.force): r["id"] for r in refs}
            for f in as_completed(futs):
                try:
                    analyses.append(f.result())
                    print(f"ok {futs[f]}", file=sys.stderr)
                except Exception as exc:
                    print(f"FAIL {futs[f]}: {exc}", file=sys.stderr)

    for a in sorted(analyses, key=lambda x: x["id"]):
        d = FORMATS_DIR / a["id"]
        d.mkdir(parents=True, exist_ok=True)
        fmt_file = d / "format.json"
        if fmt_file.exists() and not json.loads(fmt_file.read_text()).get("draft"):
            continue
        fmt_file.write_text(json.dumps(draft_format(a), indent=2, ensure_ascii=False) + "\n")
        (d / "brief.txt").write_text(a["brief"])
    print(f"{len(analyses)} analyses", file=sys.stderr)


if __name__ == "__main__":
    main()
