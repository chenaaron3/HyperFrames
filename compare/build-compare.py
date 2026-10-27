#!/usr/bin/env python3
"""Build the registry-vs-custom comparison in compare/.

Three columns per segment: registry piece as installed, the same piece
recolored to brand-sheet.md, and the custom kit component. Every column plays
the same footage window; only the custom column carries the voice.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMP = HERE / "compositions"
DEMO_IN = 14.2  # demo window start in the edited talking-head.mp4

PAPER = "#F4F3F0"
GRID = "#E4E1DB"
INK = "#141414"
RUST = "#B8452F"

# (name, compare start, length, footage window start in demo-local seconds)
SEGMENTS = [
    ("badge", 0.0, 3.0, 0.0),
    ("title", 3.0, 2.6, 1.2),
    ("proof", 5.6, 2.4, 2.6),
    ("window", 8.0, 2.4, 4.0),
    ("tree", 10.4, 6.75, 10.9),
    ("captions", 17.15, 5.6, 0.0),
]
TOTAL = 22.75
SEG = {s[0]: s for s in SEGMENTS}

NAMES = {
    "badge": ("badge-pop", "badge-pop", "section-badge"),
    "title": ("bottom-up-letters", "bottom-up-letters", "stacked-title"),
    "proof": ("strikethrough-replace", "strikethrough-replace", "proof-label"),
    "window": ("browser-device-stage", "browser-device-stage", "app-window"),
    "tree": ("flowchart-vertical", "flowchart-vertical", "folder-tree"),
    "captions": ("caption-highlight", "caption-highlight", "demo captions"),
}
COLS = ["REGISTRY · OUT OF THE BOX", "REGISTRY · BRANDED", "CUSTOM KIT"]
PANEL_X = [75, 690, 1305]

CAP_WORDS = [
    (0.302, "Okay,"), (0.426, "first"), (0.856, "you"), (1.176, "do"), (1.256, "need"),
    (1.566, "Claude"), (1.976, "Code"), (2.466, "but"), (2.858, "use"), (3.078, "it"),
    (3.238, "in"), (3.398, "the"), (3.638, "browser."), (4.254, "Download"), (4.714, "the"),
    (4.884, "desktop"),
]
CAP_GROUPS = [(0, 1), (2, 4), (5, 6), (7, 9), (10, 12), (13, 14), (15, 15)]
CAP_LEN = SEG["captions"][2]


def words_with_ends():
    out = []
    for i, (t, w) in enumerate(CAP_WORDS):
        end = CAP_WORDS[i + 1][0] if i + 1 < len(CAP_WORDS) else CAP_LEN - 0.2
        out.append({"text": w, "start": t, "end": round(end, 3)})
    return out


# ---------------------------------------------------------------- bds copies
def build_bds():
    src = (COMP / "components" / "browser-device-stage.html").read_text()
    for key, brand in (("bds-stock", False), ("bds-brand", True)):
        s = src.replace("browser-device-stage", key)
        rid = key + "-root"
        s = s.replace('id="root"', f'id="{rid}"').replace("#root", "#" + rid)
        s = s.replace('getElementById("root")', f'getElementById("{rid}")')
        s = s.replace('data-duration="5"', 'data-duration="1.75"')
        s = s.replace('data-composition-duration="5"', 'data-composition-duration="1.75"')
        if brand:
            s = s.replace("background: var(--bg, transparent);", "background: transparent;", 1)
        (COMP / f"{key}.html").write_text(s)


# ------------------------------------------------------------ caption copies
CAP_HL = """<template>
  <style>
    #__P__-root { position: absolute; inset: 0; pointer-events: none; }
    #__P__-root .__P__-group {
      position: absolute; __POS__; left: 0; width: 100%;
      display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: center;
      gap: 8px; padding: 0 100px; box-sizing: border-box; opacity: 0; visibility: hidden;
    }
    #__P__-root .__P__-word {
      font-family: __FONT__; font-weight: __WEIGHT__; font-size: __SIZE__px; text-transform: __CASE__;
      color: #ffffff; display: inline-block; letter-spacing: __TRACK__; line-height: 1;
      position: relative; padding: 6px 12px 8px;
      text-shadow: 0 6px 18px rgba(0, 0, 0, 0.45); transform-origin: 50% 58%;
    }
    #__P__-root .__P__-bg {
      position: absolute; inset: 0; background: __BG__; border-radius: 10px;
      box-shadow: __BGSHADOW__; opacity: 0; transform: scaleX(0); transform-origin: 0% 50%; z-index: -1;
    }
    #__P__-root .__P__-text { position: relative; z-index: 1; }
  </style>
  <div id="__P__-root" data-composition-id="__P__" data-start="0" data-duration="__LEN__" data-width="1080" data-height="1920">
    <div id="__P__-container"></div>
  </div>
  <script>
    (function () {
      var _c = document.createElement("canvas").getContext("2d");
      function fit(text, base, weight, family, maxW) {
        var size = base, min = Math.floor(base * 0.45);
        while (size > min) { _c.font = weight + " " + size + "px " + family; if (_c.measureText(text).width <= maxW) return size; size -= 2; }
        return min;
      }
      var WORDS = __WORDS__;
      var RAW = __GROUPS__;
      var UPPER = __UPPER__;
      var GROUPS = RAW.map(function (p, gi) {
        var next = gi + 1 < RAW.length ? WORDS[RAW[gi + 1][0]].start : __LEN__;
        return { ws: p[0], we: p[1], start: WORDS[p[0]].start, end: Math.min(WORDS[p[1]].end + 0.5, next - 0.05) };
      });
      var box = document.getElementById("__P__-container");
      var tl = gsap.timeline({ paused: true });
      GROUPS.forEach(function (g, gi) {
        var ws = WORDS.slice(g.ws, g.we + 1);
        var grp = document.createElement("div");
        grp.className = "__P__-group"; grp.id = "__P__-g" + gi;
        var label = ws.map(function (w) { return UPPER ? w.text.toUpperCase() : w.text; }).join(" ");
        var size = fit(label, __SIZE__, "__WEIGHT__", "__FITFONT__", 880);
        ws.forEach(function (w, i) {
          var wi = g.ws + i;
          var el = document.createElement("span"); el.className = "__P__-word"; el.id = "__P__-w" + wi; el.style.fontSize = size + "px";
          var bg = document.createElement("span"); bg.className = "__P__-bg"; bg.id = "__P__-b" + wi;
          var tx = document.createElement("span"); tx.className = "__P__-text"; tx.textContent = UPPER ? w.text.toUpperCase() : w.text;
          el.appendChild(bg); el.appendChild(tx); grp.appendChild(el);
        });
        box.appendChild(grp);
        tl.set(grp, { visibility: "visible" }, g.start);
        tl.fromTo(grp, { opacity: 0 }, { opacity: 1, duration: 0.12, ease: "power2.out" }, g.start);
        ws.forEach(function (w, i) {
          var wi = g.ws + i;
          var bg = document.getElementById("__P__-b" + wi), el = document.getElementById("__P__-w" + wi);
          tl.to(bg, { opacity: 1, scaleX: 1, duration: 0.15, ease: "power2.out" }, w.start);
          tl.to(el, { filter: "brightness(1.05)", duration: 0.08, ease: "power2.out" }, w.start);
          tl.to(el, { filter: "brightness(1)", duration: 0.16, ease: "power2.out" }, w.start + 0.08);
          tl.to(bg, { opacity: 0, scaleX: 1.02, duration: 0.1, ease: "power2.in" }, w.end);
          tl.set(bg, { scaleX: 0 }, w.end + 0.1);
        });
        tl.to(grp, { opacity: 0, duration: 0.1, ease: "power2.in" }, g.end - 0.1);
        tl.set(grp, { opacity: 0, visibility: "hidden" }, g.end);
      });
      window.__timelines["__P__"] = tl;
    })();
  </script>
</template>
"""


def build_captions():
    words = words_with_ends()
    common = {"__WORDS__": json.dumps(words), "__GROUPS__": json.dumps([list(g) for g in CAP_GROUPS]), "__LEN__": str(CAP_LEN)}
    variants = {
        "cap-stock": {
            "__POS__": "bottom: 140px", "__FONT__": '"Montserrat", sans-serif', "__FITFONT__": "Montserrat",
            "__WEIGHT__": "800", "__SIZE__": "80", "__CASE__": "uppercase", "__UPPER__": "true", "__TRACK__": "0.02em",
            "__BG__": "linear-gradient(135deg, #ff1745 0%, #df1238 100%)", "__BGSHADOW__": "0 12px 30px rgba(229, 20, 58, 0.32)",
        },
        "cap-brand": {
            "__POS__": "top: 1050px", "__FONT__": '"Inter", sans-serif', "__FITFONT__": "Inter",
            "__WEIGHT__": "700", "__SIZE__": "54", "__CASE__": "none", "__UPPER__": "false", "__TRACK__": "-0.01em",
            "__BG__": RUST, "__BGSHADOW__": "0 10px 26px rgba(184, 69, 47, 0.3)",
        },
    }
    for key, v in variants.items():
        s = CAP_HL.replace("__P__", key)
        for k, val in {**common, **v}.items():
            s = s.replace(k, val)
        (COMP / f"{key}.html").write_text(s)

    # custom: same treatment as compositions/demo-captions.html
    caps, tw = [], []
    for n, (a, b) in enumerate(CAP_GROUPS):
        start = words[a]["start"]
        end = words[CAP_GROUPS[n + 1][0]]["start"] if n + 1 < len(CAP_GROUPS) else CAP_LEN - 0.2
        inner = "".join(f"<i>{(' ' if k else '') + w['text']}</i>" for k, w in enumerate(words[a:b + 1]))
        caps.append(f'    <div id="cc-{n}" class="clip cc-cap" data-start="{start:.3f}" data-duration="{end - start:.3f}" data-track-index="0">{inner}</div>')
        tw.append(f'      tl.fromTo("#cc-{n} i", {{ opacity: 0, y: 10, filter: "blur(6px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.16, stagger: 0.06, ease: "power3.out" }}, {start:.3f});')
    s = f"""<template>
  <style>
    #cc-root {{ position: absolute; inset: 0; pointer-events: none; }}
    .cc-cap {{
      position: absolute; left: 0; top: 1050px; width: 1080px; text-align: center; padding: 0 80px; box-sizing: border-box;
      font-family: "Inter", sans-serif; font-weight: 700; font-size: 54px; line-height: 1.1; letter-spacing: -0.01em;
      color: #FFFFFF; text-shadow: 0 2px 12px rgba(0, 0, 0, 0.45), 0 0 2px rgba(0, 0, 0, 0.25);
    }}
    .cc-cap i {{ display: inline-block; font-style: normal; white-space: pre; }}
  </style>
  <div id="cc-root" data-composition-id="cap-custom" data-start="0" data-duration="{CAP_LEN}" data-width="1080" data-height="1920">
{chr(10).join(caps)}
  </div>
  <script>
    (function () {{
      var tl = gsap.timeline({{ paused: true }});
{chr(10).join(tw)}
      window.__timelines["cap-custom"] = tl;
    }})();
  </script>
</template>
"""
    (COMP / "cap-custom.html").write_text(s)


# --------------------------------------------------------------- root build
class Root:
    def __init__(self):
        self.panels = [[], [], []]
        self.labels = []
        self.tw = []
        self.uid = 0

    def nid(self, p):
        self.uid += 1
        return f"{p}{self.uid}"

    def video(self, c, seg, src="assets/talking-head.mp4", cls="z-base", track=0, audio=False, wrap=None):
        name, start, length, w = SEG[seg]
        vid = self.nid("v")
        attrs = 'data-has-audio="true"' if audio else "muted"
        tag = (f'<video id="{vid}" class="clip fill {cls}" src="{src}" data-start="{start}" data-duration="{length}" '
               f'data-media-start="{DEMO_IN + w:.3f}" data-track-index="{track}" {attrs} playsinline></video>')
        if wrap:
            tag = f'<div class="{wrap}">{tag}</div>'
        self.panels[c].append(tag)

    def mount(self, c, comp_id, src, start, dur, vars_=None, cls="z-front", style="position:absolute;inset:0;", track=3):
        hid = self.nid("m")
        vv = f" data-variable-values='{json.dumps(vars_)}'" if vars_ else ""
        self.panels[c].append(
            f'<div id="{hid}" class="{cls}" style="{style}" data-composition-id="{comp_id}" data-composition-src="{src}" '
            f'data-start="{start}" data-duration="{dur}" data-track-index="{track}" data-width="1080" data-height="1920"{vv}></div>')

    def clip(self, c, cid, start, dur, cls, inner, track=2, style=""):
        st = f' style="{style}"' if style else ""
        self.panels[c].append(f'<div id="{cid}" class="clip {cls}"{st} data-start="{start}" data-duration="{dur}" data-track-index="{track}">{inner}</div>')


def build_root():
    r = Root()
    T = lambda seg, local: round(SEG[seg][1] + local, 3)

    # base footage + cutouts
    for seg in SEG:
        for c in range(3):
            r.video(c, seg, audio=(c == 2), wrap="split-cam" if seg == "tree" else None)
            if seg in ("title", "window"):
                r.video(c, seg, src="assets/depth/speaker.webm", cls="z-cut", track=5)

    # 1. badge ---------------------------------------------------------------
    s, d = T("badge", 0.3), 2.7
    for c in (0, 1):
        cid = f"bp{c}"
        r.clip(c, cid, s, d, "z-front bp-wrap", (
            '<div class="hf-transition-badge-pop"><button class="hf-transition-badge-button" type="button" aria-label="Notifications">'
            '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 8a6 6 0 10-12 0c0 7-3 7-3 7h18s-3 0-3-7" /><path d="M10 20a2 2 0 004 0" /></svg>'
            '</button><span class="hf-transition-badge-count">01</span></div>'))
        base = s - 0.35
        r.tw += [
            f"tl.fromTo('#{cid} .hf-transition-badge-button', {{ y: 18, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.34, ease: 'power2.out' }}, {base + 0.35:.3f});",
            f"tl.fromTo('#{cid} .hf-transition-badge-count', {{ scale: 0, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.42, ease: 'back.out(2.4)' }}, {base + 0.7:.3f});",
            f"tl.to('#{cid} .hf-transition-badge-count', {{ scale: 1.18, duration: 0.12, yoyo: true, repeat: 1, ease: 'power1.inOut' }}, {base + 1.15:.3f});",
        ]
    r.mount(2, "section-badge", "compositions/kit/section-badge.html", s, d, {"num": "01", "label": "ON THE DESKTOP", "out": 2.3})

    # 2. title ---------------------------------------------------------------
    s, d = T("title", 0.3), 2.0
    claude, code = T("title", 0.366), T("title", 0.776)
    for c in (0, 1):
        cid = f"bu{c}"
        r.clip(c, cid, s, d, "z-behind bu-wrap",
               '<div class="bu-l1"><span class="hf-bottom-up-letters">Claude</span></div>'
               '<div class="bu-l2"><span class="hf-bottom-up-letters">Code</span></div>')
        for line, at, travel in (("bu-l1", claude - 0.05, 0.85 * 210), ("bu-l2", code, 0.85 * 250)):
            r.tw.append(f"tl.fromTo('#{cid} .{line} .hf-bottom-up-letters-char', {{ opacity: 0, y: {travel:.1f} }}, {{ opacity: 1, y: 0, duration: 0.48, ease: 'back.out(1.7)', stagger: 0.025 }}, {at:.3f});")
    r.mount(2, "stacked-title", "compositions/kit/stacked-title.html", s, d,
            {"line1": "Claude", "line2": "Code", "at2": round(code - s, 3), "top": 250, "out": 1.65}, cls="z-behind")

    # 3. proof ---------------------------------------------------------------
    s, d = T("proof", 0.25), 1.6
    strike = T("proof", 1.038)
    for c in (0, 1):
        cid = f"st{c}"
        r.clip(c, cid, s, d, "z-front st-wrap",
               '<div class="hf-catalog-strikethrough-replace"><span>Browser</span><i></i><strong>Desktop</strong></div>')
        r.tw += [
            f"tl.fromTo('#{cid} .hf-catalog-strikethrough-replace i', {{ '--hf-strike-progress': 0 }}, {{ '--hf-strike-progress': 1, duration: 0.28, ease: 'power2.out' }}, {strike:.3f});",
            f"tl.fromTo('#{cid} .hf-catalog-strikethrough-replace strong', {{ '--hf-replace-opacity': 0, y: 14 }}, {{ '--hf-replace-opacity': 1, y: 0, duration: 0.3, ease: 'power2.out' }}, {strike + 0.24:.3f});",
        ]
    r.mount(2, "proof-label", "compositions/kit/proof-label.html", s, d,
            {"kicker": "NOT IN THE", "word": "BROWSER", "strikeAt": round(strike - s, 3), "top": 1390, "out": 1.28})

    # 4. window --------------------------------------------------------------
    s, d = T("window", 0.25), 1.75
    box = "position:absolute;left:0;top:300px;width:1080px;height:700px;"
    bds_vars = {"chrome": "window", "title": "DESKTOP APP", "exit": "up"}
    r.mount(0, "bds-stock", "compositions/bds-stock.html", s, d, bds_vars, cls="z-behind", style=box)
    brand_tokens = (f"--fg:{INK};--surface:#FFFFFF;--border:#D9D5CC;--muted:#8A8780;--brand:{RUST};"
                    "--font-body:Inter,sans-serif;--font-mono:'IBM Plex Mono',monospace;")
    r.mount(1, "bds-brand", "compositions/bds-brand.html", s, d, bds_vars, cls="z-behind", style=box + brand_tokens)
    r.mount(2, "app-window", "compositions/kit/app-window.html", s, d,
            {"title": "DESKTOP APP", "head": "Ready when you are", "prompt": "Open my folder", "typeAt": 0.7, "top": 300, "out": 1.36},
            cls="z-behind")

    # 5. tree ----------------------------------------------------------------
    s, d = T("tree", 0), SEG["tree"][2]
    branch, a1, a2, a3 = (T("tree", x) for x in (1.157, 2.05, 3.336, 5.907))
    nodes = [("fc-n1", 300, "Raw footage"), ("fc-n2", 720, "References"), ("fc-n3", 1140, "Exports")]
    for c in (0, 1):
        cid = f"fc{c}"
        paths = "".join(
            f'<path class="fc-connector" d="M 720 210 L 720 360 L {x} 360 L {x} 530" fill="none" stroke-width="4" />' if x != 720 else
            '<path class="fc-connector" d="M 720 210 L 720 530" fill="none" stroke-width="4" />'
            for _, x, _ in nodes)
        divs = '<div class="fc-node fc-root" style="left:720px;top:180px">AI Video</div>' + "".join(
            f'<div class="fc-node {n}" style="left:{x}px;top:560px">{t}</div>' for n, x, t in nodes)
        r.clip(c, cid, s, d, "z-paper fc-wrap",
               f'<div class="fc-canvas"><svg class="fc-svg" width="1440" height="1180" viewBox="0 0 1440 1180">{paths}</svg>{divs}</div>')
        r.tw += [
            f"tl.fromTo('#{cid} .fc-node', {{ xPercent: -50, yPercent: -50, scale: 0 }}, {{ xPercent: -50, yPercent: -50, scale: 0, duration: 0.01 }}, {s:.3f});",
            f"tl.to('#{cid} .fc-root', {{ scale: 1, duration: 0.4, ease: 'power2.out' }}, {s:.3f});",
            f"tl.fromTo('#{cid} .fc-connector', {{ strokeDashoffset: 1000 }}, {{ strokeDashoffset: 0, duration: 0.5, ease: 'none' }}, {branch:.3f});",
        ]
        for (n, _, _), at in zip(nodes, (a1, a2, a3)):
            r.tw.append(f"tl.to('#{cid} .{n}', {{ scale: 1, duration: 0.4, ease: 'back.out(1.7)' }}, {at:.3f});")
    r.clip(2, "paper2", s, d, "z-paper paper-grid", "")
    r.mount(2, "folder-tree", "compositions/kit/folder-tree.html", s, d, {
        "root": "AI Video", "labelAt": 0.15, "branchAt": round(branch - s, 3), "c1": "Raw footage", "c2": "References",
        "c3": "Exports", "at1": round(a1 - s, 3), "at2": round(a2 - s, 3), "at3": round(a3 - s, 3), "out": 99}, cls="z-front")

    # 6. captions ------------------------------------------------------------
    s, d = T("captions", 0), CAP_LEN
    for c, key in enumerate(("cap-stock", "cap-brand", "cap-custom")):
        r.mount(c, key, f"compositions/{key}.html", s, d, cls="z-cap", track=7)

    # labels -----------------------------------------------------------------
    for c in range(3):
        r.labels.append(f'<div class="col-title" style="left:{PANEL_X[c]}px">{COLS[c]}</div>')
        for seg, (_, start, length, _) in zip(SEG, SEGMENTS):
            r.labels.append(f'<div id="lb-{seg}-{c}" class="clip col-name" style="left:{PANEL_X[c]}px" data-start="{start}" '
                            f'data-duration="{length}" data-track-index="{20 + c}">{NAMES[seg][c]}</div>')

    panels = "\n".join(
        f'      <div class="panel" style="left:{PANEL_X[c]}px"><div class="stage">\n        ' + "\n        ".join(r.panels[c]) + "\n      </div></div>"
        for c in range(3))
    script = "\n      ".join(r.tw)
    html = ROOT_TMPL.replace("__TOTAL__", str(TOTAL)).replace("__LABELS__", "\n      ".join(r.labels)) \
        .replace("__PANELS__", panels).replace("__TWEENS__", script) \
        .replace("__PAPER__", PAPER).replace("__GRID__", GRID).replace("__INK__", INK).replace("__RUST__", RUST)
    (HERE / "index.html").write_text(html)


ROOT_TMPL = """<!doctype html>
<html lang="en" data-resolution="landscape">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      #compare { position: absolute; inset: 0; overflow: hidden; background: #1B1B1A; font-family: "Inter", sans-serif; }
      .col-title { position: absolute; top: 18px; width: 540px; font-family: "IBM Plex Mono", monospace; font-weight: 600; font-size: 18px; letter-spacing: 0.14em; color: #8A8780; }
      .col-name { position: absolute; top: 46px; width: 540px; font-family: "Inter", sans-serif; font-weight: 700; font-size: 30px; color: #F4F3F0; }
      .panel { position: absolute; top: 100px; width: 540px; height: 960px; overflow: hidden; border-radius: 18px; background: #000; }
      .stage { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; transform: scale(0.5); transform-origin: 0 0; }
      .fill { position: absolute; inset: 0; width: 1080px; height: 1920px; object-fit: cover; }
      .split-cam { position: absolute; inset: 0; transform: translateY(150px) scale(1.08); transform-origin: 50% 40%; z-index: 1; }
      .z-base { z-index: 1; } .z-paper { z-index: 2; } .z-behind { z-index: 3; } .z-cut { z-index: 4; }
      .z-front { z-index: 5; } .z-cap { z-index: 6; }

      /* badge-pop, as installed */
      .bp-wrap { position: absolute; left: 64px; top: 168px; }
      .hf-transition-badge-pop { --hf-badge-pop-accent: #ef4444; --hf-badge-pop-surface: #ffffff; --hf-badge-pop-border: #e4e4e7; --hf-badge-pop-ink: #18181b; position: relative; display: inline-grid; place-items: center; font-family: Inter, system-ui, sans-serif; }
      .hf-transition-badge-button { display: grid; place-items: center; width: 76px; height: 76px; border: 1px solid var(--hf-badge-pop-border); border-radius: 22px; background: var(--hf-badge-pop-surface); color: var(--hf-badge-pop-ink); box-shadow: 0 20px 58px rgba(0, 0, 0, 0.12); }
      .hf-transition-badge-button svg { width: 30px; height: 30px; fill: none; stroke: currentColor; stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; }
      .hf-transition-badge-count { position: absolute; right: -8px; top: -8px; display: grid; place-items: center; min-width: 30px; height: 30px; padding: 0 8px; border: 3px solid var(--hf-badge-pop-surface); border-radius: 999px; background: var(--hf-badge-pop-accent); color: #ffffff; font-size: 13px; font-weight: 900; transform-origin: center; }
      #bp1 .hf-transition-badge-pop { --hf-badge-pop-accent: __RUST__ !important; --hf-badge-pop-surface: #ffffff !important; --hf-badge-pop-border: __GRID__ !important; --hf-badge-pop-ink: __INK__ !important; }
      #bp1 .hf-transition-badge-count { font-family: "IBM Plex Mono", monospace; }

      /* bottom-up-letters, as installed (the primitive ships no type style) */
      .hf-bottom-up-letters { display: inline-block; }
      .hf-bottom-up-letters-char { display: inline-block; opacity: 0; }
      .bu-wrap { position: absolute; left: 0; top: 250px; width: 1080px; text-align: center; line-height: 0.92; }
      .bu-l1 { font-size: 210px; } .bu-l2 { font-size: 250px; }
      #bu0 { font-family: "Inter", sans-serif; font-weight: 800; color: #FFFFFF; }
      #bu1 { font-family: "Outfit", sans-serif; font-weight: 800; letter-spacing: -0.02em; color: __INK__; }
      #bu1 .bu-l2 { color: __RUST__; }

      /* strikethrough-replace, as installed */
      .st-wrap { position: absolute; left: 0; top: 1390px; width: 1080px; text-align: center; }
      .hf-catalog-strikethrough-replace { color: #18181b; font-family: Inter, system-ui, sans-serif; font-weight: 900; letter-spacing: -0.04em; position: relative; display: inline-grid; grid-auto-flow: column; gap: 18px; align-items: center; font-size: 58px; }
      .hf-catalog-strikethrough-replace i { position: absolute; left: 0; width: 48%; height: 6px; border-radius: 999px; background: #ef4444; transform: scaleX(var(--hf-strike-progress, 1)); transform-origin: left center; }
      .hf-catalog-strikethrough-replace strong { opacity: var(--hf-replace-opacity, 1); }
      #st1 .hf-catalog-strikethrough-replace { font-family: "Outfit", sans-serif; font-weight: 800; letter-spacing: -0.02em; font-size: 92px; color: __INK__; }
      #st1 .hf-catalog-strikethrough-replace i { background: __RUST__; height: 10px; }
      #st1 .hf-catalog-strikethrough-replace strong { color: __RUST__; }

      /* flowchart-vertical, node and connector styles as installed */
      .fc-wrap { position: absolute; left: 0; top: 0; width: 1080px; height: 883px; overflow: hidden; }
      #fc0 { background-color: #ffffff; background-image: radial-gradient(#e5e5e5 1px, transparent 1px); background-size: 20px 20px; }
      .fc-canvas { position: absolute; left: 0; top: 0; width: 1440px; height: 1180px; transform: scale(0.75); transform-origin: 0 0; font-family: "Inter", sans-serif; }
      .fc-svg { position: absolute; left: 0; top: 0; z-index: 5; }
      .fc-connector { stroke: #333; stroke-dasharray: 1000; stroke-dashoffset: 1000; }
      .fc-node { position: absolute; padding: 16px 24px; border-radius: 12px; font-size: 18px; font-weight: 500; color: #333; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); white-space: nowrap; z-index: 10; }
      #fc0 .fc-root { background: #e8d44d; } #fc0 .fc-n1 { background: #c2e8a0; } #fc0 .fc-n2 { background: #f5c5a3; } #fc0 .fc-n3 { background: #d4c5f9; }
      #fc1, .paper-grid { background-color: __PAPER__; background-image: linear-gradient(__GRID__ 1px, transparent 1px), linear-gradient(90deg, __GRID__ 1px, transparent 1px); background-size: 56px 56px; }
      .paper-grid { position: absolute; left: 0; top: 0; width: 1080px; height: 883px; }
      #fc1 .fc-connector { stroke: __RUST__; }
      #fc1 .fc-node { background: #FFFFFF; color: __INK__; font-weight: 700; }
      #fc1 .fc-root { background: __INK__; color: #FFFFFF; } #fc1 .fc-n3 { background: __RUST__; color: #FFFFFF; }
    </style>
  </head>
  <body>
    <div id="compare" data-composition-id="compare" data-start="0" data-duration="__TOTAL__" data-width="1920" data-height="1080">
      __LABELS__
__PANELS__
    </div>
    <script>
      (function () {
        document.querySelectorAll(".hf-bottom-up-letters").forEach(function (el) {
          var text = el.textContent || "";
          el.textContent = "";
          Array.from(text).forEach(function (ch) {
            var span = document.createElement("span");
            span.className = "hf-bottom-up-letters-char";
            span.textContent = ch === " " ? "\\u00a0" : ch;
            el.appendChild(span);
          });
        });
      })();
      const tl = gsap.timeline({ paused: true });
      __TWEENS__
      tl.set({}, {}, __TOTAL__);
      window.__timelines["compare"] = tl;
    </script>
  </body>
</html>
"""

if __name__ == "__main__":
    build_bds()
    build_captions()
    build_root()
    print("compare/index.html written")
