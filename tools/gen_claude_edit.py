#!/usr/bin/env python3
"""Claude-edit look: cut dead air, then compose like the three references."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path("/Users/aaron/Documents/projects/aieditor")
FFMPEG = "ffmpeg"

FIXES = {
    "cloud": "Claude",
    "cloud's": "Claude's",
    "lock-in": "lock it",
    "coming": "combing",
}
SKIP_CAP = {
    "", "um", "uh", "uh,", "um,", "okay,", "okay",
    "a", "an", "the", "to", "and", "of", "in", "it", "is", "i",
    "my", "me", "you", "that", "this", "but", "so", "as", "or",
    "on", "for", "at", "with", "be", "was", "are",
}


def run(cmd):
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def load_words(stem: str) -> list[dict]:
    data = json.loads((ROOT / "raw-footage" / f"{stem}.json").read_text())
    out = []
    for s in data.get("transcription") or []:
        raw = (s.get("text") or "").strip()
        if not raw:
            continue
        text = FIXES.get(raw, FIXES.get(raw.lower(), raw))
        if text.lower().startswith("claude"):
            text = "Claude" + text[6:]
        off = s.get("offsets") or {}
        a = off.get("from", 0) / 1000.0
        b = off.get("to", 0) / 1000.0
        if b <= a:
            b = a + 0.16
        out.append({"text": text, "start": a, "end": b})
    return out


def detect_silence(src: Path) -> list[tuple[float, float]]:
    proc = subprocess.run(
        [FFMPEG, "-i", str(src), "-af", "silencedetect=noise=-32dB:d=0.18", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    err = proc.stderr
    starts, pairs = [], []
    for line in err.splitlines():
        if "silence_start:" in line:
            starts.append(float(line.split("silence_start:")[1].strip()))
        elif "silence_end:" in line:
            end = float(line.split("silence_end:")[1].split("|")[0].strip())
            if starts:
                pairs.append((starts.pop(0), end))
    return pairs


def probe_dur(src: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
        text=True,
    )
    return float(out.strip())


def speech_ranges(silences, duration, min_sil=0.20, handle=0.05) -> list[tuple[float, float]]:
    drops = [(a, b) for a, b in silences if (b - a) >= min_sil]
    keeps = []
    t = 0.0
    for a, b in drops:
        if a - handle > t:
            keeps.append((max(0.0, t), min(duration, a + handle)))
        t = b - handle
    if t < duration - 0.04:
        keeps.append((max(0.0, t), duration))
    merged = []
    for a, b in keeps:
        if b - a < 0.10:
            continue
        if merged and a - merged[-1][1] < 0.04:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged or [(0.0, duration)]


def to_edit(t: float, ranges) -> float:
    acc = 0.0
    for a, b in ranges:
        if t < a:
            return acc
        if t <= b:
            return acc + (t - a)
        acc += b - a
    return acc


def cut_proxy(src: Path, dest: Path, ranges) -> float:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / f".cut-{dest.stem}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    parts = []
    for i, (a, b) in enumerate(ranges):
        part = tmp / f"p{i:03d}.mp4"
        dur = b - a
        fade = min(0.012, dur / 3)
        run(
            [
                FFMPEG, "-y", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
                "-vf", "fps=30,format=yuv420p",
                "-af", f"afade=t=in:d={fade:.3f},afade=t=out:st={max(0, dur-fade):.3f}:d={fade:.3f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-g", "30",
                "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                str(part),
            ]
        )
        parts.append(part)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(dest)])
    shutil.rmtree(tmp)
    return probe_dur(dest)


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def find_phrase(words, phrase: list[str]) -> float | None:
    keys = [norm(p) for p in phrase]
    n = len(keys)
    for i in range(len(words) - n + 1):
        if [norm(words[i + j]["text"]) for j in range(n)] == keys:
            return words[i]["start"]
    return None


INDEX_CSS = """
      #root { position: absolute; inset: 0; overflow: hidden; background: #111; }
      #cam { position: absolute; inset: 0; width: 1080px; height: 1920px; z-index: 1; overflow: hidden; }
      #talk {
        position: absolute; left: 0; top: 0; width: 1080px; height: 1920px;
        object-fit: cover; object-position: 50% 40%;
      }
      .layer { position: absolute; inset: 0; pointer-events: none; z-index: 4; }
      .box { position: absolute; left: 0; width: 1080px; text-align: center; white-space: nowrap; }
      .hook { top: 200px; }
      .hook-row { display: flex; justify-content: center; align-items: center; gap: 18px; }
      .hook-top {
        font-family: Poppins, Montserrat, sans-serif; font-weight: 800;
        font-size: 78px; letter-spacing: 0.01em; color: #141414; line-height: 1;
        white-space: nowrap;
      }
      .hook-dot { display: block; width: 32px; height: 32px; border-radius: 50%; background: #141414; flex: 0 0 32px; }
      .hook-sub {
        margin-top: 8px;
        font-family: "Playfair Display", "EB Garamond", serif; font-style: italic;
        font-weight: 500; font-size: 42px; color: #6B6458; white-space: nowrap;
      }
      .lock {
        top: 220px; padding: 0 48px;
        font-family: Poppins, Montserrat, sans-serif; font-weight: 700;
        font-size: 78px; letter-spacing: 0.04em; color: #E8D4A0; line-height: 1.05;
        white-space: nowrap;
        text-shadow: 0 2px 18px rgba(20,20,20,0.18);
      }
      .lock.lg { font-size: 92px; letter-spacing: 0.03em; }
      .lock-sub {
        top: 324px;
        font-family: "Playfair Display", "EB Garamond", serif; font-style: italic;
        font-weight: 500; font-size: 40px; color: #E8D4A0; white-space: nowrap;
      }
      .notes {
        left: 130px; top: 72px; width: 820px; background: #fff;
        border-radius: 28px; box-shadow: 0 22px 56px rgba(20,20,20,0.16);
        text-align: left; overflow: hidden;
      }
      .notes.pad { border-radius: 8px 8px 18px 18px; background: #FFFEF8; }
      .notes-head {
        height: 38px; display: flex; justify-content: center; align-items: center; gap: 10px;
        background: #fff;
      }
      .notes-date {
        font-family: Inter, sans-serif; font-size: 18px; color: #9a9a9a; letter-spacing: 0.01em;
      }
      .notes-dot { width: 9px; height: 9px; border-radius: 50%; background: #1a1a1a; }
      .notes-title {
        font-family: Inter, sans-serif; font-weight: 700; font-size: 34px; color: #1a1a1a;
        padding: 8px 34px 8px; white-space: nowrap;
      }
      .notes-row {
        font-family: Inter, sans-serif; font-weight: 500; font-size: 28px; color: #222;
        padding: 12px 34px; border-top: 1px solid #efe6dc; display: flex; align-items: center; gap: 14px;
        white-space: nowrap;
      }
      .chk {
        width: 26px; height: 26px; border-radius: 50%; background: #F0C033; color: #fff;
        font-size: 16px; line-height: 26px; text-align: center; flex: 0 0 26px; font-weight: 700;
      }
      .chk.boxy { border-radius: 6px; background: #3B82F6; }
      .notes-foot {
        font-family: Inter, sans-serif; font-weight: 600; font-size: 28px; color: #1a1a1a;
        padding: 14px 34px 20px; white-space: nowrap;
      }
      .aside {
        position: absolute; left: 200px; top: 500px; width: 780px; text-align: right;
        font-family: "Playfair Display", serif; font-style: italic; font-size: 36px; color: #E8D4A0;
        white-space: nowrap; text-shadow: 0 2px 14px rgba(20,20,20,0.2);
      }
      .ios {
        left: 70px; top: 86px; width: 940px; background: #fff; border-radius: 34px;
        box-shadow: 0 18px 48px rgba(20,20,20,0.16);
        padding: 22px 26px 24px; display: flex; gap: 18px; text-align: left;
      }
      .play {
        flex: 0 0 58px; width: 58px; height: 58px; border-radius: 50%; background: #FF4D2E;
        position: relative; margin-top: 8px;
      }
      .play:after {
        content: ""; position: absolute; left: 22px; top: 16px;
        border-style: solid; border-width: 13px 0 13px 20px;
        border-color: transparent transparent transparent #fff;
      }
      .ios-meta { display: flex; justify-content: space-between; width: 780px; font-family: Inter, sans-serif; font-size: 20px; color: #8a8a8a; letter-spacing: 0.04em; }
      .ios h3 { margin: 4px 0 4px; font-family: Inter, sans-serif; font-weight: 700; font-size: 34px; color: #111; white-space: nowrap; }
      .ios p { margin: 0; font-family: Inter, sans-serif; font-size: 24px; color: #444; white-space: nowrap; }
      .xmark { top: 200px; }
      .xmark svg { width: 140px; height: 140px; }
      .phones-img {
        position: absolute; left: 0; top: 0; width: 1080px; height: 1920px;
      }
      .cap { position: absolute; left: 0; width: 1080px; top: 1280px; text-align: center; }
      .cap-text {
        font-family: "Playfair Display", "EB Garamond", serif;
        font-weight: 500; font-style: normal; font-size: 64px; color: #fff;
        letter-spacing: 0; white-space: nowrap;
        text-shadow: 0 2px 16px rgba(0,0,0,0.35);
      }
"""


def tween(sel, start, dur, y=12, inn=0.38, out=0.20):
    return (
        f'      tl.fromTo("{sel}", {{opacity:0, y:{y}}}, {{opacity:1, y:0, duration:{inn}, ease:"expo.out"}}, {start:.3f});\n'
        f'      tl.to("{sel}", {{opacity:0, duration:{out}, ease:"power2.in"}}, {start+dur-out:.3f});\n'
    )


def build(spec: dict) -> None:
    slug = spec["slug"]
    dest = ROOT / "videos" / slug
    saved_cut = None
    prev = dest / "assets" / "talk.mp4"
    if prev.exists():
        saved_cut = Path("/tmp") / f"aieditor-cut-{slug}.mp4"
        shutil.copy2(prev, saved_cut)
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "assets" / "sfx").mkdir(parents=True)
    (dest / "assets" / "stills").mkdir(parents=True)
    (dest / "compositions").mkdir()
    shutil.copy2(ROOT / "hyperframes.json", dest / "hyperframes.json")
    for sfx in ("whoosh-short.mp3", "pop.mp3"):
        shutil.copy2(ROOT / "assets" / "sfx" / sfx, dest / "assets" / "sfx" / sfx)
    for still in ("p1.jpg", "p2.jpg", "p3.jpg", "p4.jpg", "phones-row.png"):
        src_still = ROOT / "assets" / "stills" / still
        if src_still.exists():
            shutil.copy2(src_still, dest / "assets" / "stills" / still)

    src = ROOT / "assets" / "talks" / f'{spec["src"]}.mp4'
    words_src = load_words(spec["stem"])
    sil = detect_silence(src)
    dur_src = probe_dur(src)
    ranges = speech_ranges(sil, dur_src)
    cut = dest / "assets" / "talk.mp4"
    if saved_cut and saved_cut.exists():
        shutil.copy2(saved_cut, cut)
        duration = probe_dur(cut)
    else:
        duration = cut_proxy(src, cut, ranges)
    duration = min(duration, spec.get("max_dur", duration))

    def snap_src(t):
        for a, b in ranges:
            if a - 0.15 <= t <= b + 0.15:
                return min(max(t, a), b)
        best = ranges[0][0]
        dist = abs(t - best)
        for a, b in ranges:
            for x in (a, b):
                if abs(t - x) < dist:
                    best, dist = x, abs(t - x)
        return best

    words = []
    for w in words_src:
        a = snap_src(w["start"])
        b = snap_src(w["end"])
        e = {
            "text": w["text"],
            "start": round(to_edit(a, ranges), 3),
            "end": round(to_edit(max(b, a + 0.12), ranges), 3),
        }
        if e["end"] <= e["start"]:
            e["end"] = e["start"] + 0.18
        if 0 <= e["start"] < duration:
            words.append(e)

    def phrase_time(phrase):
        t = find_phrase(words_src, phrase)
        if t is not None:
            mapped = to_edit(snap_src(t), ranges)
            if 0 <= mapped < duration:
                return mapped
        return find_phrase(words, phrase)

    hook_dur = spec.get("hook_dur", 2.55)
    caps = []
    last_start = -1
    for i, w in enumerate(words):
        if w["start"] < hook_dur:
            continue
        raw = w["text"].strip(".,!?")
        if raw.lower() in SKIP_CAP:
            continue
        if last_start >= 0 and w["start"] - last_start < 0.10:
            continue
        nxt = words[i + 1]["start"] if i + 1 < len(words) else w["end"] + 0.28
        dur = max(0.34, min(0.70, nxt - w["start"] - 0.02))
        caps.append({"id": f"c{len(caps)}", "text": raw, "start": w["start"], "dur": dur})
        last_start = w["start"]

    gfx_html, gfx_js, sfx = [], [], []
    sfx.append(
        '      <audio id="sfx-hook" src="assets/sfx/whoosh-short.mp3" data-start="0.12" data-duration="0.5" data-volume="0.15" data-track-index="10"></audio>\n'
    )

    gfx_html.append(
        f'      <div id="hook" class="clip" data-start="0.10" data-duration="{hook_dur:.3f}" data-track-index="2" data-layout-allow-overflow="true">'
        f'<div class="box hook" id="hook-in" data-layout-allow-overlap="true">'
        f'<div class="hook-row"><div class="hook-dot"></div><div class="hook-top">CLAUDE EDITED</div></div>'
        f'<div class="hook-sub">this entire video</div></div></div>\n'
    )
    gfx_js.append(tween("#hook-in", 0.10, hook_dur, y=8, inn=0.46, out=0.24))

    track = 3
    graphics = spec["graphics"]
    occupied = [(0.10, hook_dur)]
    for i, g in enumerate(graphics):
        if "match" in g:
            t = phrase_time(g["match"])
            if t is None:
                start = g.get("fallback", max(hook_dur + 0.4, duration * (i + 1) / (len(graphics) + 1)))
                print(f"  fallback {g.get('text') or g['kind']} @ {start:.2f}")
            else:
                start = max(hook_dur + 0.08, t + g.get("off", 0))
        elif "from_end" in g:
            start = max(hook_dur + 0.2, duration - g["from_end"])
        else:
            start = g["start"]
        du = g["dur"]
        gid = f"g{i}"
        kind = g["kind"]
        if start >= duration - 0.35:
            start = max(hook_dur + 0.2, duration - du - 0.2)
        if start + du > duration:
            du = max(1.15, duration - start - 0.05)
        for a, b in occupied:
            if start < b + 0.22 and start + du > a:
                start = b + 0.28
        if start + du > duration:
            du = max(1.1, duration - start - 0.05)
        occupied.append((start, start + du))
        style = g.get("style", "ios")
        if kind == "lock":
            cls = "box lock" + (" lg" if g.get("lg") else "")
            sub = (
                f'<div class="box lock-sub" id="{gid}-sub">{esc(g["sub"])}</div>'
                if g.get("sub")
                else ""
            )
            gfx_html.append(
                f'      <div id="{gid}" class="clip" data-start="{start:.3f}" data-duration="{du:.3f}" data-track-index="{track}" data-layout-allow-overflow="true">'
                f'<div class="{cls}" id="{gid}-in">{esc(g["text"])}</div>{sub}</div>\n'
            )
            gfx_js.append(tween(f"#{gid}-in", start, du, y=14))
            if g.get("sub"):
                gfx_js.append(tween(f"#{gid}-sub", start + 0.12, du - 0.12, y=8, inn=0.32))
        elif kind == "notes":
            chk = "chk boxy" if style == "pad" else "chk"
            rows = "".join(
                f'<div class="notes-row"><span class="{chk}">✓</span>{esc(item)}</div>'
                for item in g["items"]
            )
            head = (
                '<div class="notes-head"><span class="notes-dot"></span><span class="notes-dot"></span>'
                '<span class="notes-dot"></span><span class="notes-dot"></span><span class="notes-dot"></span></div>'
                if style == "pad"
                else '<div class="notes-head"><div class="notes-date">October 26, 2026 at 12:16 PM</div></div>'
            )
            foot = f'<div class="notes-foot">{esc(g.get("foot", "All done by Claude."))}</div>'
            aside = (
                f'<div class="aside" id="{gid}-as">{esc(g.get("aside", "like this one!"))}</div>'
                if g.get("aside")
                else ""
            )
            ncls = "notes pad" if style == "pad" else "notes"
            gfx_html.append(
                f'      <div id="{gid}" class="clip" data-start="{start:.3f}" data-duration="{du:.3f}" data-track-index="{track}" data-layout-allow-overflow="true">'
                f'<div class="{ncls}" id="{gid}-in">{head}'
                f'<div class="notes-title">{esc(g["title"])}</div>{rows}{foot}</div>{aside}</div>\n'
            )
            gfx_js.append(tween(f"#{gid}-in", start, du, y=18, inn=0.48))
            if g.get("aside"):
                gfx_js.append(tween(f"#{gid}-as", start + 0.35, du - 0.35, y=8, inn=0.3))
        elif kind == "ios":
            gfx_html.append(
                f'      <div id="{gid}" class="clip" data-start="{start:.3f}" data-duration="{du:.3f}" data-track-index="{track}" data-layout-allow-overflow="true">'
                f'<div class="ios" id="{gid}-in"><div class="play"></div><div><div class="ios-meta"><span>CLAUDE</span><span>now</span></div>'
                f'<h3>{esc(g["title"])}</h3><p>{esc(g["body"])}</p></div></div></div>\n'
            )
            gfx_js.append(tween(f"#{gid}-in", start, du, y=16, inn=0.42))
        elif kind == "phones":
            gfx_html.append(
                f'      <div id="{gid}" class="clip" data-start="{start:.3f}" data-duration="{du:.3f}" data-track-index="{track}" data-layout-allow-overflow="true">'
                f'<img class="phones-img" id="{gid}-in" src="assets/stills/phones-row.png" width="1080" height="1920" alt=""/></div>\n'
            )
            gfx_js.append(tween(f"#{gid}-in", start, du, y=20, inn=0.5))
        elif kind == "xmark":
            svg = (
                f'<div class="box xmark" id="{gid}-in"><svg viewBox="0 0 120 120" fill="none">'
                '<rect x="16" y="30" width="88" height="54" rx="6" stroke="#141414" stroke-width="5"/>'
                '<path d="M40 88h40v8H40z" fill="#141414"/>'
                '<path d="M36 38l48 40M84 38L36 78" stroke="#141414" stroke-width="7" stroke-linecap="round"/>'
                "</svg></div>"
            )
            gfx_html.append(
                f'      <div id="{gid}" class="clip" data-start="{start:.3f}" data-duration="{du:.3f}" data-track-index="{track}" data-layout-allow-overflow="true">{svg}</div>\n'
            )
            gfx_js.append(tween(f"#{gid}-in", start, du, y=10))
        if kind in ("lock", "notes", "ios", "phones"):
            sfx.append(
                f'      <audio id="sfx-{gid}" src="assets/sfx/pop.mp3" data-start="{start:.3f}" data-duration="0.35" data-volume="0.16" data-track-index="11"></audio>\n'
            )
        track = 4 if track == 3 else 3

    cap_html, cap_js = [], []
    for c in caps:
        fade = min(0.06, c["dur"] * 0.22)
        cap_html.append(
            f'      <div id="{c["id"]}" class="clip cap" data-start="{c["start"]:.3f}" data-duration="{c["dur"]:.3f}" data-track-index="8" data-layout-allow-overflow="true">'
            f'<div class="cap-text">{esc(c["text"])}</div></div>\n'
        )
        cap_js.append(
            f'      tl.fromTo("#{c["id"]} .cap-text", {{opacity:0}}, {{opacity:1, duration:{fade:.3f}, ease:"power2.out"}}, {c["start"]:.3f});\n'
            f'      tl.to("#{c["id"]} .cap-text", {{opacity:0, duration:{fade:.3f}, ease:"power2.in"}}, {c["start"]+c["dur"]-fade:.3f});\n'
        )

    (dest / "index.html").write_text(
        f"""<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>{INDEX_CSS}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{duration:.3f}" data-width="1080" data-height="1920" data-fps="30">
      <div id="cam">
        <video id="talk" class="clip" src="assets/talk.mp4" data-start="0" data-duration="{duration:.3f}" data-track-index="0" data-has-audio="true" data-fade-out="0.25" playsinline></video>
      </div>
      <div class="layer">
{''.join(gfx_html)}{''.join(cap_html)}      </div>
{''.join(sfx)}    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      tl.set({{}}, {{}}, {duration:.3f});
{''.join(gfx_js)}{''.join(cap_js)}      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
    )

    (ROOT / "storyboards" / f"{slug}.md").write_text(
        f"""# {slug} — v3

Source: raw-footage/{spec['stem']}.MOV
Brand: Claude Edit (reference look)
Status: review

## Across the video
- Runtime: cut dead air → {duration:.1f}s
- Full-bleed picture; type over the frame
- Hook: Poppins 800 + Playfair italic
- Captions: one word, Playfair, on the chest
- Graphics: notes / iOS banner / cream lockups
- Music: none
"""
    )
    print(f"{slug}: {dur_src:.1f}s → {duration:.1f}s  caps={len(caps)}  segs={len(ranges)}")


SPECS = [
    {
        "slug": "own-editor-v1",
        "stem": "IMG_5346",
        "src": "5346",
        "max_dur": 38,
        "graphics": [
            {"kind": "lock", "match": ["hours"], "text": "HOURS", "dur": 1.8, "lg": True},
            {"kind": "lock", "match": ["flop"], "text": "FLOP", "dur": 1.7},
            {"kind": "notes", "match": ["decided"], "dur": 3.8,
             "title": "Claude's edit list",
             "items": ["Cut the hours", "Keep the thinking", "Place edits on words"],
             "aside": "like this one!"},
            {"kind": "lock", "match": ["on", "words"], "text": "ON WORDS", "dur": 2.2, "lg": True},
            {"kind": "ios", "match": ["fun"], "dur": 3.0,
             "title": "Your video is ready!", "body": "Edits done. Tap to watch & post.", "off": -0.15},
        ],
    },
    {
        "slug": "clone-effect-v1",
        "stem": "IMG_5352",
        "src": "5352",
        "max_dur": 36,
        "graphics": [
            {"kind": "lock", "match": ["super", "hard"], "text": "SUPER HARD", "dur": 1.8},
            {"kind": "lock", "match": ["really", "easy"], "text": "REALLY EASY", "dur": 2.0, "lg": True},
            {"kind": "notes", "match": ["simple"], "dur": 4.0, "style": "pad",
             "title": "Claude's edit list",
             "items": ["Tripod, wide scene", "Cut out the extras", "Overlay the clips"],
             "aside": "like this one!"},
            {"kind": "lock", "match": ["that's", "how"], "text": "THAT'S THE EFFECT", "dur": 2.2},
        ],
    },
    {
        "slug": "five-minutes-v1",
        "stem": "IMG_5355",
        "src": "5355",
        "max_dur": 42,
        "graphics": [
            {"kind": "lock", "match": ["hours"], "text": "HOURS EDITING", "dur": 2.0},
            {"kind": "lock", "match": ["minutes"], "text": "5 MINUTES", "sub": "to record, that's it", "dur": 2.4, "lg": True},
            {"kind": "notes", "match": ["process"], "dur": 4.0,
             "title": "Claude's edit list",
             "items": ["Upload the day", "Tell it the vision", "Place the clips"],
             "aside": "like this one!"},
            {"kind": "phones", "match": ["upload"], "dur": 3.2,
             "stills": ["p1.jpg", "p3.jpg", "p2.jpg"]},
            {"kind": "ios", "from_end": 4.2, "dur": 3.2,
             "title": "Your video is ready!", "body": "Edits done. Tap to watch & post."},
            {"kind": "lock", "match": ["ton", "of", "time"], "text": "A TON OF TIME", "dur": 2.2, "fallback": 36.5},
        ],
    },
    {
        "slug": "build-editor-v1",
        "stem": "IMG_5304",
        "src": "5304",
        "max_dur": 46,
        "graphics": [
            {"kind": "lock", "match": ["Claude", "code"], "text": "CLAUDE CODE", "dur": 2.1, "lg": True},
            {"kind": "xmark", "match": ["browser"], "dur": 1.8},
            {"kind": "lock", "match": ["desktop"], "text": "DESKTOP APP", "dur": 2.0},
            {"kind": "notes", "match": ["three"], "dur": 4.2, "style": "pad",
             "title": "Claude's edit list",
             "items": ["Raw footage", "References", "Exports"],
             "aside": "like this one!"},
            {"kind": "lock", "match": ["folder"], "text": "ONE FOLDER", "dur": 1.8},
            {"kind": "ios", "from_end": 4.0, "dur": 3.0,
             "title": "Your video is ready!", "body": "Cuts, captions, and the storyboard."},
        ],
    },
]


if __name__ == "__main__":
    for spec in SPECS:
        build(spec)
