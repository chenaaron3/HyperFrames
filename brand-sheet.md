---
status: approved
approvedAt: 2026-10-24
sources:
  - references/frames/ref-premium-*.png (3 user-supplied reels, frames sampled in the player; the files could not be downloaded without an Instagram login)
  - references/ref-01-ai-video-editor-guide.mp4 (split-screen lesson grammar)
---

# Studio Desk

## Promise
A talking head that feels shot in a studio: the room stays real, product UI and titles live in the space around and behind the speaker, and every element arrives on the word that names it.

## Frame
1080×1920 @ 30fps. Side margin 64px. Nothing that must be read sits below y 1690 (Reel UI) or above y 140. The face (eyes to chin) is never covered by a graphic in front of the speaker.

## Palette
Measured by eye from the reference frames, then set as ours. Treat these hex values as fixed.

| Role | Hex | Use |
| --- | --- | --- |
| Paper | `#F4F3F0` | Split-frame and full-frame ground |
| Grid | `#E4E1DB` | 1px square grid on paper, 56px cells |
| Card | `#FFFFFF` | Cards, chips, windows |
| Window | `#F7F5F0` | App-window body and sidebar tint |
| Ink | `#141414` | Titles, body text on light |
| Muted | `#8A8780` | Secondary text, skeleton lines |
| Rust | `#B8452F` | The one accent: numbers, labels, ribbons, active state |
| Night | `#121212` at 88% | Dark chips and the timer pill |

Rust is the only accent. No second hue, no gradients behind type.

## Type
| Role | Face | Weight | Size at 1080 |
| --- | --- | --- | --- |
| Display (titles, lockups) | Outfit (bundled; Bricolage Grotesque once font files are added) | 800 | 120–180px, tight tracking (−2%) |
| Accent word | EB Garamond Italic (bundled) | 600 | 0.55× the display size |
| UI and body | Inter (bundled; Manrope once font files are added) | 600 / 700 | 30–40px |
| Labels, numbers, timers | IBM Plex Mono | 500 | 24–30px, caps, +12% tracking |
| Captions | Inter (bundled; Manrope once font files are added) | 700 | 52px |

All four are Google Fonts. Fonts are guesses at the reference's class, not matches to it.

## Captions
Sentence case, one to four words, the words being said right now. White, no stroke, soft drop shadow (0 2px 12px at 45% black). No karaoke, no per-word color, no punctuation unless the word needs it.

- Full face: centered at y ≈ 1060 (upper chest).
- Split frame: on the paper just above the seam, in Rust.
- Captions step aside (or hide) while a lockup holds the same line.

## Picture
The room stays. Layouts:

1. **Full face.** The default. Components sit behind the head (via the person cutout) or in front of the chest.
2. **Split.** Paper on the top ~46%, the face cropped below. Used for app windows and diagrams.
3. **Full paper.** Only for a document or a recap the viewer has to read.

Camera, all done in post on the one locked take:

- Slow push-in across a sentence: scale 1.00 → 1.06, `sine.inOut`.
- Accent push on a key word: 1.00 → 1.10 over 0.35s, `power3.out`, then hold.
- Never above 1.12. Past that the 1080 source goes soft.
- Layout changes move rather than cut: the split slides the paper in from the top (0.5s, `power3.inOut`) while the face moves down with it.

Remove any pause longer than about 0.15 seconds. Leave the performance alone otherwise.

## Motion
Every component is from the kit (`compositions/kit/`) and has an entrance, a hold, and an exit.

- Entrances land on the spoken word, not the start of the beat. Parts arrive staggered 50–80ms apart.
- Ease: `expo.out` or `power3.out` for arrivals (0.45–0.7s). `power3.inOut` for panels and layout moves. `power2.in` for exits (0.25–0.35s).
- At most a 4% overshoot on scale. Opacity and color never overshoot.
- Fast moves (over ~1,200 px/s) get motion blur; the speaker never does.
- One hero component on screen at a time, plus at most one chip.

The kit:

| Component | What it is |
| --- | --- |
| Section badge | Rust square with a mono number, then a tracked mono label (`01 FOLDER`) |
| Title lockup | Display word, an accent-word ribbon in Rust, a mono episode ticket |
| Stacked title | Ink display word over a Rust display word |
| App window | Traffic lights, sidebar, prompt field that types, soft shadow |
| Stat card | White card, mono caps label, big Rust number, small note |
| Timer chip | Night pill with a Rust progress ring and mono digits |
| Checklist | Night glass rows; the active row sharp and in front, the others blurred behind |
| Card fan | Three white cards fanned with Rust mono numbers |
| Document card | White sheet of grey and Rust skeleton lines |
| Proof label | Tracked mono line over a Rust block word (`WHAT IT SENT BACK` / `AFTER`) |

## Depth
The speaker is cut out of the background on every frame. Layers, back to front:

1. The room (background plate).
2. Behind-head components: titles, windows, card fans.
3. The speaker.
4. Front components: chips, the checklist, proof labels, at chest height.
5. Captions.

A behind-head component may cover the hair and shoulders. It is placed so the face is never in front of nothing.

## Sound
Voice is the mix, around −14 LUFS. Each kit component carries one sound: a soft whoosh on panels and windows, a tick on badges and chips, a key press while a prompt types. Sounds sit 14–18 dB under the voice. A music bed is optional: only licensed, and 18 dB under the voice.

## Why it reads as ours
- One accent (Rust) on warm paper, never a second hue.
- Graphics live behind the speaker, so the frame has depth without a green screen.
- Titles are a display word plus an italic accent word on a Rust ribbon.
- Everything lands on the word that names it, and everything leaves.

## Do not
- Copy the reference's series name, episode format, icons, calendar art, or comment keywords.
- Recreate any real app's interface pixel-for-pixel. Windows are generic.
- Push past 1.12 scale, shake, glitch, chromatic split, or speed-ramp.
- Cover the face with a front component.
- Use music we do not have rights to.
