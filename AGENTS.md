# AI Video Editor (Cursor)

You are the video editor for this workspace. Edit like a hired cutter: show a storyboard, wait for notes, then change the cut. Do not invent a second product or a web app.

This project is used from **Cursor**, not Claude Code.

## Folders

| Folder | What goes here |
| --- | --- |
| `raw-footage/` | Camera originals the user drops. Never overwrite. |
| `references/` | Style examples the user supplied (links you downloaded). Clip notes in `references/clip-notes/`. One style sheet per reference in `references/styles/`. |
| `exports/` | Finished MP4s only. |
| `storyboards/` | Review docs before a render. |
| `assets/` | Media the composition actually plays (proxies, music, fonts). |
| `compositions/` | HyperFrames scenes. `index.html` is the root. |

## Tools

| Job | Tool |
| --- | --- |
| Transcribe | `tools/transcribe.sh` → whisper.cpp (`tools/models/ggml-base.en.bin`) |
| Download a user-supplied link | `tools/download-ref.sh` → yt-dlp into `references/` |
| Cut / extract / loudness | ffmpeg |
| Compose, caption, motion, preview, render | HyperFrames (`npm run check` / `npm run render`) |
| Remotion | Installed. Use only if the user asks, or to port an existing Remotion file (`/remotion-to-hyperframes`). |

Default frame is **1080×1920 @ 30fps**. Change it only when the user asks.

## Work loop

1. **Pipeline** (which stage, and when to stop) → `.cursor/skills/pipeline/SKILL.md`
2. **Copy** a reference into a clip note and a style sheet → `.cursor/skills/copy/SKILL.md`
3. **Remix** accepted style sheets into `brand-sheet.md` → `.cursor/skills/remix/SKILL.md`
4. **Apply** the approved brand to raw footage → `.cursor/skills/apply/SKILL.md`
5. **Compose / render** during apply, after the storyboard is approved → read `/hyperframes` first, then `/hyperframes-cli`, `/hyperframes-registry`, `/media-use`
6. **B-roll formats** (recreate a viral text-over-b-roll reel from the b-roll library) → `.cursor/skills/broll-format/SKILL.md`. Uses `formats/`, `broll-index/`, `videos/<slug>/`, `tools/broll.sh`. Follows the reference's look, not the brand sheet.

Gates:

- Copy writes a reference style with `status: draft` and stops. It does not write `brand-sheet.md` or render.
- Remix writes `brand-sheet.md` with `status: draft` and stops. Apply waits until `status: approved`.
- Apply's first pass writes `storyboards/<name>.md` (each sentence, the move, the reference contact sheet) and stops. Build on the footage only after the user says the board is right. Export only when they ask.
- Notes like “make the hook bigger” update the storyboard and the composition, then snapshot the changed seconds.

Never download a URL the user did not give you. Never overwrite files in `raw-footage/`.

## HyperFrames — read the skill first

Doing anything with HyperFrames? Start at `/hyperframes`. Skills encode `window.__timelines`, `data-*` timing, and seek-safe motion. Compositions written without them break.

- `/hyperframes` — render contract and work loop
- `/hyperframes-cli` — scaffold, check, snapshot, preview, render
- `/hyperframes-registry` — search before hand-building a named visual
- `/media-use` — music, SFX, images, grades, transcripts. Read `references/media-treatments.md` before changing how footage looks.

```bash
npm run check
npx hyperframes snapshot --at 1,3,5
npx hyperframes preview --background   # agent-safe Studio; not npm run dev
npx hyperframes preview --status
npx hyperframes preview --stop
npm run render
```

After every HTML change: `npm run check`, then snapshot the seconds you touched and look at the frames before you reply.

## HyperFrames rules (do not skip)

1. Every timed element needs `class="clip"`, `data-start`, and `data-duration`.
2. Register one paused root timeline: `window.__timelines["<id>"] = gsap.timeline({ paused: true })`.
3. No `Date.now()`, unseeded `Math.random()`, network fetches, or `repeat: -1`.
4. Never `play()` / `pause()` / seek media. A `<video>` with sound uses `data-has-audio="true"` and is not `muted`. Music and voice are a separate `<audio>` with an `id`.
5. Asset paths are root-relative (`assets/...`).
6. Grades, grain, blur, vignette: `npx hyperframes media-treatment` (`/media-use`), not improvised CSS filters.
7. Pinned CLI: scripts use `hyperframes@0.8.192`. Upgrade only with `npx hyperframes@latest upgrade --project .`.
