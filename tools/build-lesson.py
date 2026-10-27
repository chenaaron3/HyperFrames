#!/usr/bin/env python3
"""Tighten IMG_5304 and write the Graph Paper Lesson composition."""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "raw-footage" / "IMG_5304.MOV"
TRANSCRIPT = ROOT / "raw-footage" / "IMG_5304.json"
PROXY = ROOT / "assets" / "talking-head.mp4"
POSTER = ROOT / "assets" / "poster.jpg"
PICTURE = ROOT / "compositions" / "picture.html"
CAPTIONS = ROOT / "compositions" / "captions.html"
INDEX = ROOT / "index.html"

TAIL = 121.55
DROP_WOULD = (82.55, 83.05)


def sh(cmd):
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def silences():
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-i", str(SRC),
            "-af", "silencedetect=noise=-35dB:d=0.15",
            "-f", "null", "-",
        ],
        text=True, capture_output=True,
    )
    found = []
    start = None
    for line in proc.stderr.splitlines():
        if "silence_start:" in line:
            start = float(line.split("silence_start:")[1].split()[0])
        elif "silence_duration:" in line and start is not None:
            dur = float(line.split("silence_duration:")[1].strip())
            found.append((start, start + dur, dur))
            start = None
    return found


def keep_ranges(gaps):
    drops = []
    for start, end, dur in gaps:
        if dur > 0.15:
            drops.append((start + 0.15, end))
    drops.append(DROP_WOULD)
    drops.append((TAIL, 10_000))
    drops.sort()
    merged = []
    for start, end in drops:
        if not merged or start > merged[-1][1] + 0.001:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    keeps = []
    cursor = 0.0
    for start, end in merged:
        if start > cursor + 0.02:
            keeps.append((round(cursor, 3), round(min(start, TAIL), 3)))
        cursor = max(cursor, end)
        if cursor >= TAIL:
            break
    if cursor < TAIL - 0.02:
        keeps.append((round(cursor, 3), TAIL))
    return [(a, b) for a, b in keeps if b - a > 0.04]


def src_to_edit(t, keeps):
    """Map a source time onto the cut. A time inside a dropped gap lands on the join."""
    out = 0.0
    for a, b in keeps:
        if t < a:
            return out
        if t <= b:
            return out + (t - a)
        out += b - a
    return out


def in_keep(t, keeps):
    return any(a - 0.02 <= t <= b + 0.02 for a, b in keeps)


def load_words():
    data = json.loads(TRANSCRIPT.read_text())
    words = []
    for item in data["transcription"]:
        text = item["text"].strip()
        if not text:
            continue
        words.append({"src": item["offsets"]["from"] / 1000, "text": text})
    for i, word in enumerate(words):
        nxt = words[i + 1]["text"].lower() if i + 1 < len(words) else ""
        token = word["text"]
        low = token.lower().strip(",.")
        if low == "cloud":
            token = "Claude's" if token.lower().endswith("'s") or "cloud's" in token.lower() else "Claude"
        elif low == "cloud's":
            token = "Claude's"
        elif low == "lock-in":
            token = "lock it"
        elif low == "code" and i > 0 and words[i - 1]["text"].startswith("Claude"):
            token = "Code"
        elif low == "the" and nxt.startswith("lock"):
            token = "they"
        word["text"] = token
    return words


def encode(keeps):
    expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in keeps)
    fc = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"fps=30,select='{expr}',setpts=N/FRAME_RATE/TB[v];"
        f"[0:a]aformat=sample_fmts=fltp:channel_layouts=stereo,aresample=48000,"
        f"aselect='{expr}',asetpts=N/SR/TB[a]"
    )
    script = ROOT / "assets" / "cut-filter.txt"
    script.write_text(fc)
    PROXY.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-i", str(SRC),
            "-filter_complex_script", str(script),
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart",
            str(PROXY),
        ],
        check=True,
    )
    probe = sh([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(PROXY),
    ]).stdout.strip()
    poster_src = 20.0
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-ss", str(poster_src),
            "-i", str(SRC), "-frames:v", "1", "-vf", "scale=540:-1",
            str(POSTER),
        ],
        check=True, capture_output=True,
    )
    return float(probe)


def groups_for(words, keeps):
    spoken = []
    for word in words:
        if word["src"] >= DROP_WOULD[0] and word["src"] < DROP_WOULD[1]:
            continue
        if word["src"] < 9.1:
            continue
        if not in_keep(word["src"], keeps):
            continue
        edit = src_to_edit(word["src"], keeps)
        spoken.append({**word, "edit": edit})
    groups = []
    cur = []
    for word in spoken:
        if cur:
            gap = word["edit"] - cur[-1]["edit"]
            prev = cur[-1]["text"]
            if len(cur) >= 3 or gap > 0.55 or prev[-1:] in ".?!,":
                groups.append(cur)
                cur = []
        cur.append(word)
    if cur:
        groups.append(cur)
    out = []
    for i, group in enumerate(groups):
        start = group[0]["edit"]
        if i + 1 < len(groups):
            end = groups[i + 1][0]["edit"]
        else:
            end = group[-1]["edit"] + 0.45
        if end < start + 0.22:
            end = start + 0.22
        text = " ".join(re.sub(r"[.,!?]", "", w["text"]) for w in group)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out.append({"start": start, "end": end, "text": text})
    return out


def place(start, zones):
    for a, b, name in zones:
        if a <= start < b:
            return name
    return "chest"


def html_escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


PAPER_CSS = """
    #root { position: absolute; inset: 0; overflow: hidden; background: #111; }
    #face-rig { position: absolute; inset: 0; z-index: 1; }
    #talk { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; object-fit: cover; }
    .paper {
      position: absolute; left: 0; top: 0; width: 1080px; z-index: 2;
      background-color: #E7DFD2;
      background-image:
        linear-gradient(#D4CBBC 1px, transparent 1px),
        linear-gradient(90deg, #D4CBBC 1px, transparent 1px);
      background-size: 48px 48px;
      overflow: hidden;
    }
    .paper.split { height: 883px; }
    .paper.full { height: 1920px; }
    .step {
      position: absolute; left: 64px; right: 64px; top: 168px;
      text-align: center; font-family: "Archivo Black", sans-serif;
      font-size: 54px; line-height: 1.15; color: #1C1C1C;
    }
    .paper.full .step { top: 220px; }
    .rust { color: #C4513A; }
    .stage { position: absolute; left: 0; right: 0; top: 300px; bottom: 40px; }
    .paper.full .stage { top: 380px; }
    .label {
      font-family: Inter, sans-serif; font-weight: 700; font-size: 32px;
      color: #1C1C1C; text-align: center;
    }
    .label.rust { color: #C4513A; }
    .card, .bubble, .pill {
      position: absolute; z-index: 4; background: #fff;
      box-shadow: 0 18px 50px rgba(28, 28, 28, 0.16);
    }
    .card {
      left: 70px; top: 200px; width: 940px; border-radius: 28px;
      padding: 36px 40px 40px; font-family: Inter, sans-serif; color: #1C1C1C;
    }
    .dots { display: flex; gap: 10px; margin-bottom: 18px; }
    .dots i { width: 16px; height: 16px; border-radius: 50%; display: block; }
    .dots i:nth-child(1) { background: #E25B45; }
    .dots i:nth-child(2) { background: #E6B325; }
    .dots i:nth-child(3) { background: #3FA36A; }
    .card h2 { font-size: 40px; font-weight: 700; margin: 8px 0 22px; }
    .card p { font-size: 32px; line-height: 1.35; margin: 0 0 14px; }
    .mark { background: #F6E27A; padding: 0 6px; }
    .hook {
      position: absolute; z-index: 5; left: 48px; right: 48px; top: 188px;
      text-align: center; font-family: "Archivo Black", sans-serif;
      font-size: 78px; line-height: 1.05; color: #fff;
      -webkit-text-stroke: 10px #000; paint-order: stroke fill;
    }
    .row { display: flex; justify-content: center; gap: 28px; align-items: flex-end; }
    .phone {
      width: 200px; height: 320px; background: #fff; border: 4px solid #1C1C1C;
      border-radius: 22px; overflow: hidden; box-shadow: 0 8px 0 rgba(28,28,28,0.06);
    }
    .phone img { width: 100%; height: 100%; object-fit: cover; }
    .phone .blank { height: 100%; background: #F6F1E8; }
    .folder {
      width: 280px; height: 200px; margin: 0 auto; position: relative;
    }
    .folder .tab {
      width: 110px; height: 28px; background: #7EB6E8; border: 4px solid #1C1C1C;
      border-bottom: 0; border-radius: 10px 10px 0 0; margin-left: 18px;
    }
    .folder .body {
      height: 160px; background: #7EB6E8; border: 4px solid #1C1C1C; border-radius: 8px 18px 18px 18px;
    }
    .folder.sm { width: 210px; height: 150px; }
    .folder.sm .body { height: 112px; }
    .menu {
      width: 640px; margin: 20px auto 0; background: #fff; border-radius: 20px;
      padding: 22px 28px; font-family: Inter, sans-serif; font-size: 32px;
      box-shadow: 0 12px 30px rgba(28,28,28,0.08);
    }
    .menu .on { background: #F3F0EA; border-radius: 10px; padding: 8px 12px; font-weight: 700; }
    .icons { display: flex; justify-content: center; gap: 80px; margin-top: 40px; }
    .icon { width: 280px; text-align: center; }
    .swatch {
      height: 150px; border: 4px solid #1C1C1C; border-radius: 18px; background: #fff;
      margin-bottom: 16px;
    }
    .board {
      width: 760px; margin: 10px auto; background: #1C1C1C; color: #fff;
      border-radius: 24px; padding: 36px 40px; font-family: Inter, sans-serif;
    }
    .board div { font-size: 34px; padding: 14px 0; border-bottom: 2px solid #333; }
    .bubble { left: 90px; top: 250px; width: 900px; border-radius: 28px; padding: 28px 36px; }
    .bubble .me { text-align: right; font-family: Inter, sans-serif; font-size: 30px; color: #666; }
    .bubble .reply { font-family: Inter, sans-serif; font-size: 36px; font-weight: 700; margin-top: 12px; }
    .star { color: #C4513A; }
    .pill {
      left: 140px; top: 220px; width: 800px; height: 96px; border-radius: 48px;
      display: flex; align-items: center; justify-content: space-between; padding: 0 28px;
      font-family: "Archivo Black", sans-serif; font-size: 36px;
    }
    .pill .go { width: 64px; height: 64px; border-radius: 50%; background: #1C1C1C; color: #fff;
      display: flex; align-items: center; justify-content: center; font-size: 28px; }
    .rec { position: absolute; top: 16px; left: 16px; background: #E25B45; color: #fff;
      font-family: Inter, sans-serif; font-weight: 700; font-size: 28px; padding: 4px 8px; border-radius: 6px; }
    .laptop { width: 760px; margin: 0 auto; }
"""


def folder(extra=""):
    return f'<div class="folder {extra}"><div class="tab"></div><div class="body"></div></div>'


def paper(pid, start, dur, kind, inner):
    return (
        f'<div id="{pid}" class="clip paper {kind}" data-start="{start:.3f}" '
        f'data-duration="{dur:.3f}" data-track-index="2">{inner}</div>'
    )


def step(num, rest):
    return f'<div class="step"><span class="rust">Step {num}.</span> {html_escape(rest)}</div>'


def build_graphics(m, dur):
    def t(src):
        return src_to_edit(src, m["keeps"])

    spans = {
        "s1": (t(20.0), t(26.3)),
        "folder": (t(26.3), t(31.4)),
        "tree": (t(31.4), t(40.7)),
        "local": (t(40.7), t(50.2)),
        "tools": (t(50.2), t(58.1)),
        "mimic": (t(58.1), t(67.1)),
        "own": (t(67.1), t(72.2)),
        "style": (t(72.2), t(79.8)),
        "film": (t(79.8), t(83.1)),
        "drop": (t(83.1), t(91.7)),
        "cuts": (t(91.7), t(96.3)),
        "board": (t(96.3), t(99.2)),
        "fix": (t(99.2), t(105.7)),
        "flow": (t(105.7), t(110.2)),
        "mix": (t(110.2), t(119.6)),
        "cta": (t(119.6), dur),
        "hook": (0.12, t(12.8)),
    }

    def block(key):
        a, b = spans[key]
        return a, max(0.2, b - a)

    bits = []
    a, d = block("hook")
    bits.append(
        f'<div id="hook" class="clip hook" data-start="{a:.3f}" data-duration="{d:.3f}" '
        f'data-track-index="5" data-layout-allow-overlap="true" data-var-text="hook">'
        f'Everyone is editing<br>their videos with Claude Code</div>'
    )
    a, d = block("s1")
    bits.append(paper("g-s1", a, d, "split", step(1, "On the desktop") + """
      <div class="stage"><div class="row" style="align-items:center;gap:40px;margin-top:40px">
        <div><div class="swatch" style="width:220px;display:flex;align-items:center;justify-content:center;font-family:Inter,sans-serif;font-size:28px;text-decoration:line-through">Browser</div></div>
        <div class="rust" style="font-family:'Archivo Black',sans-serif;font-size:64px">↓</div>
        <div><div class="swatch" style="width:220px;background:#C4513A;color:#fff;display:flex;align-items:center;justify-content:center;font-family:Inter,sans-serif;font-weight:700;font-size:28px">Desktop</div></div>
      </div></div>"""))
    a, d = block("folder")
    bits.append(paper("g-folder", a, d, "split", step(1, "On the desktop") + f"""
      <div class="stage">{folder()}<div class="label" style="margin-top:18px">AI Video Editor</div></div>"""))
    a, d = block("tree")
    bits.append(paper("g-tree", a, d, "full", step(1, "On the desktop") + f"""
      <div class="stage">
        {folder()}
        <div class="label" style="margin:8px 0 28px">AI Video Editor</div>
        <div class="row">
          <div>{folder("sm")}<div class="label" id="lab-raw">Raw footage</div></div>
          <div>{folder("sm")}<div class="label" id="lab-ref">References</div></div>
          <div>{folder("sm")}<div class="label rust" id="lab-exp">Exports</div></div>
        </div>
      </div>"""))
    a, d = block("local")
    bits.append(paper("g-local", a, d, "split", step(2, "Point it at the folder") + """
      <div class="stage"><div class="menu">
        <div style="color:#888;font-size:26px;margin-bottom:8px">Local</div>
        <div class="on">This computer</div>
        <div style="padding:8px 12px">Cloud</div>
      </div></div>"""))
    a, d = block("tools")
    bits.append(f'''<div id="g-tools" class="clip card" data-start="{a:.3f}" data-duration="{d:.3f}" data-track-index="3">
      <div class="dots"><i></i><i></i><i></i></div>
      <h2>Install these tools</h2>
      <p>Give Claude the links on screen.</p>
      <p>Install each one, then say when they're ready.</p>
    </div>''')
    a, d = block("mimic")
    bits.append(paper("g-mimic", a, d, "split", step(3, "Lock the style") + """
      <div class="stage"><div class="row">
        <div class="phone"><div class="blank"></div></div>
        <div class="phone"><div class="blank"></div></div>
        <div class="phone"><div class="blank"></div></div>
      </div><div class="label" style="margin-top:16px">3 to 5 videos</div></div>"""))
    a, d = block("own")
    bits.append(paper("g-own", a, d, "split", step(3, "Lock the style") + """
      <div class="stage"><div class="row"><div class="phone"><img src="assets/poster.jpg" alt=""></div></div>
      <div class="label" style="margin-top:16px">your own</div></div>"""))
    a, d = block("style")
    bits.append(f'''<div id="g-style" class="clip card" data-start="{a:.3f}" data-duration="{d:.3f}" data-track-index="3">
      <div class="dots"><i></i><i></i><i></i></div>
      <h2>Learn this style</h2>
      <p class="mark">Paste 3 to 5 video links.</p>
      <p>Study what they share. Write a brand sheet I can review.</p>
    </div>''')
    a, d = block("film")
    bits.append(paper("g-film", a, d, "split", step(4, "Film, then hand it over") + """
      <div class="stage"><div class="row" style="align-items:center">
        <div class="phone" style="position:relative"><img src="assets/poster.jpg" alt=""><div class="rec">REC</div></div>
        """ + folder() + """
      </div><div class="label" style="margin-top:12px">Raw footage</div></div>"""))
    a, d = block("drop")
    bits.append(f'''<div id="g-drop" class="clip card" data-start="{a:.3f}" data-duration="{d:.3f}" data-track-index="3">
      <div class="dots"><i></i><i></i><i></i></div>
      <h2>Edit this video</h2>
      <p>The footage is in <span class="mark">raw footage</span>.</p>
      <p>Follow the brand sheet. Show a storyboard first.</p>
    </div>''')
    a, d = block("cuts")
    bits.append(paper("g-cuts", a, d, "split", step(4, "Film, then hand it over") + """
      <div class="stage"><div class="icons">
        <div class="icon"><div class="swatch"></div><div class="label">Cuts</div></div>
        <div class="icon"><div class="swatch" style="background:#C4513A"></div><div class="label rust">Captions</div></div>
      </div></div>"""))
    a, d = block("board")
    bits.append(paper("g-board", a, d, "full", """
      <div class="stage"><div class="board">
        <div>1 &nbsp; Hook</div><div>2 &nbsp; The folder</div><div>3 &nbsp; The style</div><div>4 &nbsp; The edit</div>
      </div><div class="label" style="color:#1C1C1C;margin-top:28px">for your review</div></div>"""))
    a, d = block("fix")
    bits.append(f'''<div id="g-fix" class="clip bubble" data-start="{a:.3f}" data-duration="{d:.3f}" data-track-index="3">
      <div class="me">Make the hook bigger</div>
      <div class="reply"><span class="star">✱</span> Done. The hook is bigger.</div>
    </div>''')
    a, d = block("flow")
    bits.append(paper("g-flow", a, d, "full", f"""
      <div class="stage" style="text-align:center">
        {folder()}
        <div class="label" style="margin:10px 0 36px">AI Video Editor</div>
        <div class="row" style="gap:18px">
          <div class="label rust">Step 1.<br>Desktop</div>
          <div class="label rust">Step 2.<br>Folder</div>
          <div class="label rust">Step 3.<br>Style</div>
          <div class="label rust">Step 4.<br>Film</div>
        </div>
      </div>"""))
    a, d = block("mix")
    bits.append(paper("g-mix", a, d, "full", """
      <div class="stage"><div class="laptop">
        <svg viewBox="0 0 760 460" width="760" height="460">
          <rect x="80" y="20" width="600" height="380" rx="16" fill="#fff" stroke="#1C1C1C" stroke-width="6"/>
          <rect x="110" y="52" width="540" height="300" rx="8" fill="#E7DFD2"/>
          <rect x="250" y="120" width="260" height="160" rx="12" fill="none" stroke="#1C1C1C" stroke-width="4"/>
          <circle cx="380" cy="190" r="28" fill="none" stroke="#1C1C1C" stroke-width="4"/>
          <rect x="40" y="400" width="680" height="22" rx="6" fill="#fff" stroke="#1C1C1C" stroke-width="6"/>
        </svg>
      </div></div>"""))
    a, d = block("cta")
    bits.append(f'''<div id="g-cta" class="clip pill" data-start="{a:.3f}" data-duration="{d:.3f}" data-track-index="3">
      <span class="star">✱</span><span>MOTION</span><span class="go">→</span>
    </div>''')

    ticks = []
    for i, key in enumerate(("s1", "local", "mimic", "film"), start=1):
        start = spans[key][0]
        ticks.append(
            f'<audio id="tick-{i}" class="clip" src="assets/sfx/click-soft.mp3" '
            f'data-start="{start:.3f}" data-duration="0.37" data-volume="0.28" data-track-index="6"></audio>'
        )
    zones = [
        (0, spans["s1"][0], "chest"),
        (spans["s1"][0], spans["tree"][0], "seam"),
        (spans["tree"][0], spans["local"][0], "paper"),
        (spans["local"][0], spans["tools"][0], "seam"),
        (spans["tools"][0], spans["mimic"][0], "chest"),
        (spans["mimic"][0], spans["style"][0], "seam"),
        (spans["style"][0], spans["film"][0], "chest"),
        (spans["film"][0], spans["drop"][0], "seam"),
        (spans["drop"][0], spans["cuts"][0], "chest"),
        (spans["cuts"][0], spans["board"][0], "seam"),
        (spans["board"][0], spans["fix"][0], "paper"),
        (spans["fix"][0], spans["flow"][0], "chest"),
        (spans["flow"][0], spans["cta"][0], "paper"),
        (spans["cta"][0], dur + 1, "chest"),
    ]
    return "\n".join(bits + ticks), zones, spans


def write_html(dur, caption_groups, graphic_html, zones):
    picture = f"""<template>
  <style>{PAPER_CSS}</style>
  <div id="root" data-composition-id="picture" data-width="1080" data-height="1920" data-layout-allow-overlap="true">
    <div id="face-rig" data-layout-allow-overflow="true">
      <video id="talk" class="clip" src="assets/talking-head.mp4" data-start="0" data-duration="{dur:.3f}" data-track-index="0" data-has-audio="true" playsinline></video>
    </div>
    {graphic_html}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    const rig = "#face-rig";
    const zones = {json.dumps([[round(a, 3), round(b, 3), name] for a, b, name in zones])};
    zones.forEach(([a, b, name]) => {{
      const y = name === "seam" ? 140 : 0;
      const scale = name === "seam" ? 1.08 : 1;
      tl.set(rig, {{ y, scale, transformOrigin: "50% 42%" }}, a);
    }});
    tl.fromTo("#hook", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.2, ease: "power2.out" }}, 0.12);
    window.__timelines["picture"] = tl;
  </script>
</template>
"""
    caps = []
    tweens = []
    for i, group in enumerate(caption_groups):
        start = max(0.12, group["start"])
        dur_g = max(0.2, group["end"] - start)
        kind = place(start, zones)
        caps.append(
            f'<div id="cap-{i}" class="clip cap cap-{kind}" data-start="{start:.3f}" '
            f'data-duration="{dur_g:.3f}" data-track-index="0" data-layout-allow-overlap="true">'
            f'<div class="cap-text">{html_escape(group["text"])}</div></div>'
        )
        tweens.append(
            f'tl.fromTo("#cap-{i} .cap-text", {{opacity:0}}, {{opacity:1, duration:0.06, ease:"power2.out"}}, {start:.3f});'
            f'tl.to("#cap-{i} .cap-text", {{opacity:0, duration:0.06, ease:"power2.in"}}, {(start + dur_g - 0.06):.3f});'
        )
    captions = f"""<template>
  <style>
    #root {{ position: absolute; inset: 0; overflow: visible; }}
    .cap {{
      position: absolute; left: 0; width: 1080px; text-align: center;
      font-family: "Archivo Black", sans-serif; font-size: 64px; line-height: 1.05;
      color: #fff; padding: 0 64px;
      -webkit-text-stroke: 8px #000; paint-order: stroke fill;
      text-shadow: 0 2px 0 #000, 0 -2px 0 #000, 2px 0 0 #000, -2px 0 0 #000;
    }}
    .cap-chest {{ top: 1340px; }}
    .cap-seam {{ top: 820px; }}
    .cap-paper {{ top: 1280px; }}
    .cap-text {{ display: inline; }}
  </style>
  <div id="root" data-composition-id="captions" data-width="1080" data-height="1920" data-layout-allow-overlap="true">
    {''.join(caps)}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    {''.join(tweens)}
    window.__timelines["captions"] = tl;
  </script>
</template>
"""
    index = f"""<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      #picture {{ z-index: 1; }}
      #captions {{ z-index: 8; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{dur:.3f}" data-width="1080" data-height="1920">
      <div id="picture" data-composition-id="picture" data-composition-src="compositions/picture.html" data-start="0" data-duration="{dur:.3f}" data-track-index="0" data-track-kind="graphics" data-width="1080" data-height="1920"></div>
      <div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="{dur:.3f}" data-track-index="1" data-track-kind="captions" data-width="1080" data-height="1920"></div>
    </div>
    <script>
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
"""
    PICTURE.write_text(picture)
    CAPTIONS.write_text(captions)
    INDEX.write_text(index)


def main():
    gaps = silences()
    keeps = keep_ranges(gaps)
    print(f"keeps {len(keeps)} source-span {keeps[0][0]}-{keeps[-1][1]}")
    words = load_words()
    if PROXY.exists() and PROXY.stat().st_size > 1_000_000:
        dur = float(sh([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(PROXY),
        ]).stdout.strip())
        print(f"proxy reused {dur:.2f}s")
    else:
        print("encoding proxy…")
        dur = encode(keeps)
        print(f"proxy {dur:.2f}s")
    mapped = {"keeps": keeps}
    graphic_html, zones, spans = build_graphics(mapped, dur)
    caps = groups_for(words, keeps)
    print(f"captions {len(caps)}")
    for group in caps[:8]:
        print(f"  {group['start']:.2f} {group['text']}")
    write_html(dur, caps, graphic_html, zones)
    print("wrote compositions")


if __name__ == "__main__":
    main()
