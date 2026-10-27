#!/usr/bin/env python3
"""Turn a b-roll plan into a storyboard, then into a HyperFrames project.

  tools/broll.sh new 15 blessed-v1        # scaffold videos/blessed-v1/plan.json from format #15
  tools/broll.sh storyboard blessed-v1    # validate + storyboards/blessed-v1.md with frames
  tools/broll.sh compose blessed-v1       # cut shots, pull music, write videos/blessed-v1/index.html

plan.json:
  {
    "format": "15",
    "title": "...",
    "lines":  { "l1": "on-screen text (\\n for a manual break)", ... },
    "shots":  { "s1": { "clip": "SelfShots/Walking/IMG_1.MOV", "in": 3.2, "speed": 1.0, "note": "why" }, ... },
    "caption": "post caption"
  }
`speed` < 1 slows the source down (0.5 = half speed). Missing lines fall back to the format's reference text.
"""

import argparse
import html
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BROLL_ROOT, ROOT, STORYBOARDS_DIR, VIDEOS_DIR, load_format, load_index, probe  # noqa: E402
from shake import motion, verdict  # noqa: E402

W, H, FPS = 1080, 1920, 30
HDR_TRANSFERS = {"arib-std-b67", "smpte2084"}
MIN_TEXT_PX = 46


def sh(cmd):
    subprocess.run(cmd, check=True)


def plan_path(slug):
    return VIDEOS_DIR / slug / "plan.json"


def load_plan(slug):
    p = plan_path(slug)
    if not p.exists():
        sys.exit(f"missing {p.relative_to(ROOT)}; run: tools/broll.sh new <format> {slug}")
    plan = json.loads(p.read_text())
    fmt = load_format(plan["format"])
    fmt["text"] = {**fmt["text"], **plan.get("text", {})}
    return plan, fmt


def resolved_lines(plan, fmt):
    out = []
    for line in fmt["lines"]:
        text = plan.get("lines", {}).get(line["id"]) or line["ref"]
        y = plan.get("textY") or plan.get("lineY", {}).get(line["id"]) or line.get("y", fmt["text"]["y"])
        out.append({**line, "text": text, "y": y})
    return out


def validate(plan, fmt):
    errors = []
    probes = {}
    for shot in fmt["shots"]:
        pick = plan.get("shots", {}).get(shot["id"])
        if not pick or not pick.get("clip"):
            errors.append(f"{shot['id']}: no clip picked")
            continue
        src = BROLL_ROOT / pick["clip"]
        if not src.exists():
            errors.append(f"{shot['id']}: clip not found {pick['clip']}")
            continue
        meta = probes.setdefault(pick["clip"], probe(src))
        need = (shot["end"] - shot["start"]) * pick.get("speed", 1.0)
        if pick.get("in", 0) + need > meta["duration"] + 0.01:
            errors.append(
                f"{shot['id']}: {pick['clip']} is {meta['duration']:.2f}s; in {pick.get('in', 0):.2f} + {need:.2f}s runs past the end"
            )
    return errors, probes


def grab(src, t, out, vf):
    out.parent.mkdir(parents=True, exist_ok=True)
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", "-vf", vf, "-q:v", "3", str(out)])


def cmd_new(args):
    fmt = load_format(args.format)
    p = plan_path(args.slug)
    if p.exists() and not args.force:
        sys.exit(f"{p.relative_to(ROOT)} exists (use --force)")
    p.parent.mkdir(parents=True, exist_ok=True)
    plan = {
        "format": fmt["id"],
        "title": fmt["name"],
        "lines": {l["id"]: l["ref"] for l in fmt["lines"]},
        "shots": {s["id"]: {"clip": "", "in": 0.0, "speed": 1.0, "note": s["brief"]} for s in fmt["shots"]},
        "caption": "",
    }
    p.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {p.relative_to(ROOT)}")


def cmd_autopick(args):
    """Fill empty shot slots with the best-ranked unused moment; keep alternates for review."""
    from search import score_moment

    plan, fmt = load_plan(args.slug)
    index = load_index()
    lines = {l["id"]: l for l in resolved_lines(plan, fmt)}
    used = {p["clip"] for p in plan["shots"].values() if p.get("clip")}
    used_folders = []
    for shot in fmt["shots"]:
        pick = plan["shots"].setdefault(shot["id"], {"clip": "", "in": 0.0, "speed": 1.0, "note": shot.get("brief", "")})
        failed = pick.get("motion", {}).get("verdict", "ok") != "ok" and not pick.get("allowMotion")
        if pick.get("clip") and not args.force and not failed:
            continue
        if failed:
            used.discard(pick["clip"])
            pick.pop("motion", None)
        need = shot["end"] - shot["start"]
        line_text = lines[shot["line"]]["text"] if shot.get("line") in lines else ""
        query = " ".join(filter(None, [pick.get("query"), shot.get("brief", "").split("(ref:")[0], line_text]))
        wants_creator = any(w in query.lower() for w in ("selfie", "smil", "laugh", "creator", "me ", "eating", "walking"))
        ranked = []
        for clip in index.values():
            if clip["path"] in used or not clip["quality"]["usable"]:
                continue
            if args.exclude and any(clip["path"].startswith(x) for x in args.exclude):
                continue
            for m in clip["moments"]:
                if m["end"] - m["start"] < need - 0.05 and clip["duration"] - m["start"] < need:
                    continue
                s = score_moment(query, clip, m)
                if wants_creator and clip["people"]["creator_visible"]:
                    s += 0.5
                if used_folders and clip["folder"] == used_folders[-1]:
                    s -= 0.4
                ranked.append((s, clip, m))
        ranked.sort(key=lambda r: -r[0])
        chosen = None
        for rank, (_, clip, m) in enumerate(ranked[:25]):
            if clip["quality"]["stability"] == "shaky":
                continue
            t_in = max(0.0, min(m["start"] + max(0.0, (m["end"] - m["start"] - need) / 2), clip["duration"] - need - 0.05))
            if verdict(*motion(clip["path"], t_in, need)) == "ok":
                chosen = (rank, clip, m, t_in)
                break
        if not chosen:
            print(f"{shot['id']}: no steady moment long enough", file=sys.stderr)
            continue
        rank, clip, m, t_in = chosen
        ranked = ranked[rank:]
        pick.update(clip=clip["path"], speed=1.0, note=f"{m['action']} ({m['emotion']})")
        pick["in"] = round(t_in, 2)
        pick["alts"] = [f"{c['path']} @{mm['start']:.1f}-{mm['end']:.1f}: {mm['action'][:70]}" for _, c, mm in ranked[1:6]]
        used.add(clip["path"])
        used_folders.append(clip["folder"])
        print(f"{shot['id']} <- {clip['path']} @{t_in:.1f}  {m['action'][:70]}", file=sys.stderr)
    plan_path(args.slug).write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")


def contact_sheet(slug, fmt, frames_dir):
    tiles = []
    for shot in fmt["shots"]:
        a, b = frames_dir / f"{shot['id']}-ref.jpg", frames_dir / f"{shot['id']}.jpg"
        if a.exists() and b.exists():
            tiles.append((shot["id"], a, b))
    if not tiles:
        return
    inputs, filters = [], []
    for i, (sid, a, b) in enumerate(tiles):
        inputs += ["-i", str(a), "-i", str(b)]
        filters.append(f"[{2 * i}][{2 * i + 1}]hstack=2,drawtext=text='{sid}':x=8:y=8:fontsize=28:fontcolor=yellow:box=1:boxcolor=black[t{i}]")
    cols = min(4, len(tiles))
    rows = -(-len(tiles) // cols)
    pad = rows * cols - len(tiles)
    names = "".join(f"[t{i}]" for i in range(len(tiles)))
    if pad:
        filters.append(f"color=black:s={W // 2}x{H // 4}:d=1[blank]")
        filters.append("[blank]split=" + str(pad) + "".join(f"[b{j}]" for j in range(pad)))
        names += "".join(f"[b{j}]" for j in range(pad))
    layout = "|".join(f"{(i % cols) * (W // 2)}_{(i // cols) * (H // 4)}" for i in range(rows * cols))
    if rows * cols == 1:
        filters.append("[t0]null[out]")
    else:
        filters.append(f"{names}xstack=inputs={rows * cols}:layout={layout}[out]")
    sh(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[out]", "-frames:v", "1", "-q:v", "4", str(frames_dir / "sheet.jpg")])


def cmd_storyboard(args):
    plan, fmt = load_plan(args.slug)
    errors, probes = validate(plan, fmt)
    if errors:
        sys.exit("plan errors:\n  " + "\n  ".join(errors))
    index = load_index()
    lines = {l["id"]: l for l in resolved_lines(plan, fmt)}
    frames_dir = STORYBOARDS_DIR / "frames" / args.slug
    ref = ROOT / fmt["reference"]
    cover = f"scale={W // 4}:{H // 4}:force_original_aspect_ratio=increase,crop={W // 4}:{H // 4}"

    rows = []
    for shot in fmt["shots"]:
        pick = plan["shots"][shot["id"]]
        dur = shot["end"] - shot["start"]
        speed = pick.get("speed", 1.0)
        mid_src = pick.get("in", 0) + dur * speed / 2
        grab(ref, shot["start"] + dur / 2, frames_dir / f"{shot['id']}-ref.jpg", cover)
        grab(BROLL_ROOT / pick["clip"], mid_src, frames_dir / f"{shot['id']}.jpg", cover)
        ann = index.get(pick["clip"], {})
        pan, jitter = motion(pick["clip"], pick.get("in", 0), dur * speed)
        steady = verdict(pan, jitter)
        pick["motion"] = {"speed": pan, "jitter": jitter, "verdict": steady}
        if steady != "ok":
            print(f"WARNING {shot['id']}: {steady} (speed {pan}, jitter {jitter})", file=sys.stderr)
        rows.append(
            f"| {shot['id']} | {shot['start']:.2f}–{shot['end']:.2f} ({dur:.2f}s) "
            f"| ![ref](frames/{args.slug}/{shot['id']}-ref.jpg) | ![pick](frames/{args.slug}/{shot['id']}.jpg) "
            f"| {html.escape(lines[shot['line']]['text']).replace(chr(10), '<br>')} "
            f"| `{pick['clip']}` @ {pick.get('in', 0):.2f}s{'' if speed == 1 else f' ×{speed}'}<br>{html.escape(ann.get('summary', 'not indexed'))} "
            f"| {html.escape(pick.get('note', ''))} | {steady} ({pan}/{jitter}) |"
        )

    md = [
        f"# {plan.get('title', fmt['name'])} ({args.slug})",
        "",
        f"Format: #{fmt['id']} {fmt['name']} (`{fmt['reference']}`)",
        "Style: reference-native text (not the Studio Desk sheet)",
        "Status: review",
        "",
        "## Across the video",
        "",
        f"- Runtime: {fmt['duration']:.2f}s at {W}×{H} @ {FPS}fps, cut points copied from the reference",
        f"- Music: audio lifted from the reference ({fmt['music'].get('title', 'original audio')})",
        f"- Text: white, thin dark outline, Montserrat {fmt['text']['weight']}, {fmt['text']['size']}px, centred at y≈{fmt['text']['y']:.0%}",
        "",
        "## Lines",
        "",
        "| # | Time | Text |",
        "| --- | --- | --- |",
    ]
    for l in lines.values():
        md.append(f"| {l['id']} | {l['start']:.2f}–{l['end']:.2f} | {html.escape(l['text']).replace(chr(10), '<br>')} |")
    md += [
        "",
        "## Shots",
        "",
        "| # | Time | Reference | Pick | Text | Source | Why | Motion (speed/jitter) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        *rows,
        "",
        "## Post caption",
        "",
        plan.get("caption") or "_(none yet)_",
        "",
    ]
    out = STORYBOARDS_DIR / f"{args.slug}.md"
    out.write_text("\n".join(md))
    plan_path(args.slug).write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    contact_sheet(args.slug, fmt, frames_dir)
    print(f"wrote {out.relative_to(ROOT)}")


def cut_shot(src, t_in, dur, speed, out, transfer):
    frames = round(dur * FPS)
    vf = []
    if transfer in HDR_TRANSFERS:
        vf.append("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
    vf += [
        f"setpts=(PTS-STARTPTS)/{speed}",
        f"fps={FPS}",
        f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos",
        f"crop={W}:{H}",
        "setsar=1",
        "format=yuv420p",
    ]
    sh([
        "ffmpeg", "-v", "error", "-y", "-ss", f"{t_in:.3f}", "-i", str(src),
        "-t", f"{dur * speed + 0.5:.3f}", "-vf", ",".join(vf), "-frames:v", str(frames),
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-g", "15",
        "-movflags", "+faststart", str(out),
    ])


def color_transfer(src):
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer", "-of", "csv=p=0", str(src)],
        capture_output=True, text=True,
    )
    return proc.stdout.strip()


def line_html(l, fmt):
    text = html.escape(l["text"]).replace("\n", "<br>")
    top = round(l["y"] * H)
    return (
        f'      <div id="{l["id"]}" class="clip line" style="top: {top}px" data-start="{l["start"]:.3f}" '
        f'data-duration="{l["end"] - l["start"]:.3f}" data-track-index="2"><span>{text}</span></div>'
    )


def cmd_compose(args):
    plan, fmt = load_plan(args.slug)
    errors, _ = validate(plan, fmt)
    for shot in fmt["shots"]:
        pick = plan["shots"][shot["id"]]
        if pick.get("allowMotion"):
            continue
        v = verdict(*motion(pick["clip"], pick.get("in", 0), (shot["end"] - shot["start"]) * pick.get("speed", 1.0)))
        if v != "ok":
            errors.append(f"{shot['id']}: {v} ({pick['clip']} @ {pick.get('in', 0)}); repick or set allowMotion")
    if errors:
        sys.exit("plan errors:\n  " + "\n  ".join(errors))
    proj = VIDEOS_DIR / args.slug
    assets = proj / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    shots_html = []
    for i, shot in enumerate(fmt["shots"]):
        pick = plan["shots"][shot["id"]]
        src = BROLL_ROOT / pick["clip"]
        dur = shot["end"] - shot["start"]
        out = assets / f"{shot['id']}.mp4"
        cut_shot(src, pick.get("in", 0), dur, pick.get("speed", 1.0), out, color_transfer(src))
        print(f"cut {shot['id']} <- {pick['clip']} @ {pick.get('in', 0):.2f}", file=sys.stderr)
        shots_html.append(
            f'      <video id="v-{shot["id"]}" class="clip shot" src="assets/{shot["id"]}.mp4" data-start="{shot["start"]:.3f}" '
            f'data-duration="{dur:.3f}" data-track-index="{i % 2}" muted playsinline></video>'
        )

    duration = fmt["duration"]
    music = assets / "music.m4a"
    sh([
        "ffmpeg", "-v", "error", "-y", "-i", str(ROOT / fmt["reference"]), "-vn", "-t", f"{duration:.3f}",
        "-af", f"afade=t=out:st={duration - 0.3:.3f}:d=0.3", "-c:a", "aac", "-b:a", "192k", str(music),
    ])

    t = fmt["text"]
    lines_html = [line_html(l, fmt) for l in resolved_lines(plan, fmt)]
    doc = f"""<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      #root {{ position: absolute; inset: 0; overflow: hidden; background: #000; }}
      .shot {{ position: absolute; inset: 0; width: {W}px; height: {H}px; object-fit: cover; z-index: 1; }}
      .line {{ position: absolute; left: 0; width: {W}px; z-index: 3; display: flex; justify-content: center; transform: translateY(-50%); }}
      .line span {{
        max-width: {t["maxWidth"]}px;
        text-align: center;
        font-family: "Montserrat", sans-serif;
        font-weight: {t["weight"]};
        font-size: {max(t["size"], MIN_TEXT_PX)}px;
        line-height: {t["lineHeight"]};
        letter-spacing: -0.01em;
        color: #fff;
        text-shadow: -2px 0 0 rgba(0,0,0,.75), 2px 0 0 rgba(0,0,0,.75), 0 -2px 0 rgba(0,0,0,.75), 0 2px 0 rgba(0,0,0,.75), 0 0 10px rgba(0,0,0,.35);
      }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{duration:.3f}" data-width="{W}" data-height="{H}" data-fps="{FPS}">
{chr(10).join(shots_html)}
{chr(10).join(lines_html)}
      <audio id="music" src="assets/music.m4a" data-start="0" data-duration="{duration:.3f}" data-volume="1" data-track-index="4"></audio>
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      tl.set({{}}, {{}}, {duration:.3f});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
    (proj / "index.html").write_text(doc)
    print(f"wrote {(proj / 'index.html').relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new")
    p.add_argument("format")
    p.add_argument("slug")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_new)
    p = sub.add_parser("autopick")
    p.add_argument("slug")
    p.add_argument("--force", action="store_true", help="re-pick slots that already have a clip")
    p.add_argument("--exclude", nargs="*", help="clip path prefixes to avoid")
    p.set_defaults(fn=cmd_autopick)
    for name, fn in (("storyboard", cmd_storyboard), ("compose", cmd_compose)):
        p = sub.add_parser(name)
        p.add_argument("slug")
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
