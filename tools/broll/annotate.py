#!/usr/bin/env python3
"""Annotate b-roll clips with Gemini and write one JSON per clip to broll-index/clips/.

  tools/broll.sh annotate --pilot 30          # stratified sample across folders
  tools/broll.sh annotate --folder SelfShots  # one subtree
  tools/broll.sh annotate --all               # everything not yet indexed
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BROLL_ROOT, CACHE_DIR, INDEX_DIR, file_fingerprint, index_path, list_clips, probe  # noqa: E402

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
PROXY_DIR = CACHE_DIR / "proxies"
INLINE_LIMIT = 18 * 1024 * 1024


class People(BaseModel):
    count: int = Field(description="People clearly visible at any point")
    creator_visible: bool = Field(description="The person filming / the main recurring subject is on screen (selfie, mirror, tripod or filmed by a friend)")
    description: str = Field(description="Who is on screen, clothing, what they look like, relationship if obvious (friends, date, crowd)")


class Camera(BaseModel):
    style: Literal["selfie", "mirror_selfie", "tripod_static", "filmed_by_friend", "pov_first_person", "handheld_cinematic", "gimbal", "other"]
    framing: Literal["extreme_close", "close", "medium", "wide", "extreme_wide"]
    movement: str = Field(description="static, pan, tilt up, walking, tracking, shaky…")
    angle: str = Field(description="eye level, low angle looking up, high angle, top-down…")


class Quality(BaseModel):
    usable: bool
    stability: Literal["locked", "steady", "handheld", "shaky"]
    exposure: Literal["good", "dark", "blown_out", "mixed"]
    issues: str = Field(description="Blur, lens smudge, accidental frames, finger over lens, empty if none")


class Moment(BaseModel):
    start: float = Field(description="Seconds from clip start")
    end: float = Field(description="Seconds from clip start")
    action: str = Field(description="Literal description of what happens in this span")
    emotion: str = Field(description="Facial expression / feeling conveyed, e.g. big laugh, calm, focused, embarrassed")
    good_for: list[str] = Field(description="Short on-screen-text ideas this span could illustrate, e.g. 'roof over my head', 'food on my plate', 'laugh at your mistakes', 'studying', 'flopping onto bed', 'working a corporate job'")
    score: int = Field(description="1-5: how strong this span is as a standalone 1-4s b-roll shot")


class Annotation(BaseModel):
    summary: str = Field(description="One or two sentences: what this clip is")
    location: str = Field(description="Specific place type: bedroom, kitchen, gym, subway car, city street, restaurant, park…")
    setting: Literal["indoor", "outdoor", "vehicle", "mixed"]
    time_of_day: Literal["day", "golden_hour", "night", "indoor_unknown"]
    weather: str = Field(description="sunny, overcast, rain, snow, n/a")
    people: People
    camera: Camera
    quality: Quality
    mood: list[str]
    energy: Literal["low", "medium", "high"]
    tags: list[str] = Field(description="10-20 lowercase search tags: objects, activities, places, emotions")
    moments: list[Moment] = Field(description="Distinct usable spans, 1-8s each, in time order, covering the best parts of the clip")


PROMPT = """You are logging b-roll for a short-form video editor (9:16 Instagram Reels / TikTok).
The footage belongs to one creator, who appears in most clips (selfies, tripod shots, or filmed by friends).
The folder path is a hint from the creator about the content: {folder}
Clip duration: {duration:.2f}s.

Describe what is literally visible and happening. Be concrete: actions, objects, places, expressions.
Then split the clip into distinct usable moments with accurate start/end seconds (never beyond {duration:.2f}).
For each moment, list on-screen text ideas it could illustrate in emotional/lifestyle reels
(gratitude lists, "laugh at…" lists, milestone/judgment lists, relatable memes). Score honestly; shaky,
blurry or accidental frames score 1-2."""


def make_proxy(src: Path, fp: str) -> Path:
    PROXY_DIR.mkdir(parents=True, exist_ok=True)
    out = PROXY_DIR / f"{fp}.mp4"
    if out.exists() and out.stat().st_size > 0:
        return out
    tmp = out.with_suffix(".tmp.mp4")
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y", "-hwaccel", "videotoolbox", "-i", str(src),
            "-vf", "scale='if(gt(iw,ih),-2,360)':'if(gt(iw,ih),360,-2)',fps=10",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ac", "1", "-b:a", "48k", "-movflags", "+faststart", str(tmp),
        ],
        check=True,
    )
    tmp.rename(out)
    return out


def ask_gemini(client, proxy: Path, prompt: str, duration: float):
    from google.genai import types

    fps = 2 if duration <= 60 else 1
    if proxy.stat().st_size <= INLINE_LIMIT:
        video = types.Part(
            inline_data=types.Blob(data=proxy.read_bytes(), mime_type="video/mp4"),
            video_metadata=types.VideoMetadata(fps=fps),
        )
        uploaded = None
    else:
        uploaded = client.files.upload(file=str(proxy), config={"mime_type": "video/mp4"})
        while uploaded.state.name == "PROCESSING":
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)
        video = types.Part(
            file_data=types.FileData(file_uri=uploaded.uri, mime_type="video/mp4"),
            video_metadata=types.VideoMetadata(fps=fps),
        )
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=[types.Content(role="user", parts=[video, types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Annotation,
                temperature=0.2,
            ),
        )
    finally:
        if uploaded is not None:
            client.files.delete(name=uploaded.name)
    usage = resp.usage_metadata
    return resp.parsed, {
        "input_tokens": getattr(usage, "prompt_token_count", 0) or 0,
        "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
    }


def annotate_one(client, rel: str, force: bool):
    src = BROLL_ROOT / rel
    out = index_path(rel)
    fp = file_fingerprint(src)
    if out.exists() and not force:
        if json.loads(out.read_text()).get("fingerprint") == fp:
            return rel, "skip", None
    meta = probe(src)
    if meta["duration"] < 0.5:
        return rel, "skip (too short)", None
    proxy = make_proxy(src, fp)
    folder = str(Path(rel).parent)
    prompt = PROMPT.format(folder=folder, duration=meta["duration"])
    for attempt in range(5):
        try:
            ann, usage = ask_gemini(client, proxy, prompt, meta["duration"])
            break
        except Exception as exc:  # rate limits and transient 5xx
            if attempt == 4:
                raise
            wait = 2 ** attempt * 5
            print(f"  retry {rel} in {wait}s: {exc}", file=sys.stderr)
            time.sleep(wait)
    data = ann.model_dump()
    for m in data["moments"]:
        m["start"] = round(max(0.0, min(m["start"], meta["duration"])), 2)
        m["end"] = round(max(m["start"], min(m["end"], meta["duration"])), 2)
    record = {
        "path": rel,
        "folder": folder,
        "fingerprint": fp,
        **meta,
        "model": MODEL,
        "annotatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **data,
    }
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    return rel, "ok", usage


def pilot_sample(clips, n, seed=7):
    by_folder = defaultdict(list)
    for rel in clips:
        by_folder["/".join(Path(rel).parts[:2])].append(rel)
    rng = random.Random(seed)
    for items in by_folder.values():
        rng.shuffle(items)
    folders = sorted(by_folder)
    picked = []
    while len(picked) < n and any(by_folder.values()):
        for f in folders:
            if by_folder[f] and len(picked) < n:
                picked.append(by_folder[f].pop())
    return sorted(picked)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pilot", type=int, metavar="N", help="stratified sample of N clips across folders")
    g.add_argument("--folder", help="annotate clips under this folder (relative to BROLL_ROOT)")
    g.add_argument("--clip", action="append", help="annotate specific clip(s), relative path")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-annotate even if indexed")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true", help="list the clips, do nothing")
    args = ap.parse_args()

    clips = list_clips()
    if args.pilot:
        todo = pilot_sample(clips, args.pilot)
    elif args.folder:
        prefix = args.folder.rstrip("/") + "/"
        todo = [c for c in clips if c.startswith(prefix)]
    elif args.clip:
        todo = args.clip
    else:
        todo = clips

    if args.dry_run:
        print("\n".join(todo))
        print(f"{len(todo)} clips", file=sys.stderr)
        return

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is not set. Add it to .env (GEMINI_API_KEY=...).")
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    print(f"model {MODEL}, {len(todo)} clips, {args.workers} workers", file=sys.stderr)
    tokens_in = tokens_out = done = failed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(annotate_one, client, rel, args.force): rel for rel in todo}
        for fut in as_completed(futures):
            rel = futures[fut]
            try:
                _, status, usage = fut.result()
            except Exception as exc:
                failed += 1
                print(f"FAIL {rel}: {exc}", file=sys.stderr)
                continue
            done += 1
            if usage:
                tokens_in += usage["input_tokens"]
                tokens_out += usage["output_tokens"]
            print(f"[{done + failed}/{len(todo)}] {status} {rel}", file=sys.stderr)
    print(f"done {done}, failed {failed}, tokens in {tokens_in:,} out {tokens_out:,}", file=sys.stderr)


if __name__ == "__main__":
    main()
