---
name: copy
description: >-
  Break one edited reference into a clip note (named animations and a contact
  sheet per move) and a style sheet distilled from that note. Use when the
  user supplies a reference clip, pastes a video link to study, or asks for
  clip notes, an animation breakdown, contact sheets, or to copy a style.
  Does not write brand-sheet.md and does not render.
---

# Copy

One reference video in. Two files out: a clip note, and a style sheet remix can read.

You choose the animation boundaries by looking. The tools only sample a window and dedupe a span you already named. Do not write a detector that picks the first or last frame.

## Boundaries

For each animation, from the source frames:

- **A** — first frame the graphic comes in
- **B** — first frame it is holding
- **C** — first frame it animates out
- **D** — last frame of that out

The sheet is **A−1 through B+1**, then **C through D+1**. A−1 is the frame before this graphic. D+1 is the frame after it is gone. Leave out the long hold between B+1 and C.

If the graphic is already up on the first frame of the clip, there is no A−1. Start at that frame. If it is still up on the last frame, there is no out. Say so. Do not invent one.

The out is this graphic leaving. One frame of the next shot is enough to show a hard cut. Do not keep going into the next animation.

## Tools

Both live in `.cursor/skills/copy/scripts/frames.py`.

**Sample** at most 12 frames, every frame. That is about 0.4s. The cells have to be large enough to read. A longer sheet gets refused.

```bash
python3 .cursor/skills/copy/scripts/frames.py sample \
  --video "references/<file>.mp4" \
  --start 27.20 --end 27.53 \
  --output /tmp/clip-sample.jpg
```

Open the jpg. The number under a cell is the source time. If the frame before the move is not in the sheet, slide earlier and sample again. If the move has not arrived, or has not settled, or has not left, slide later. Do not lock a time off a sheet you cannot read.

**Dedupe** only after those times are chosen. `--region` is `x,y,w,h` as fractions of the frame, and it must cover this graphic, not the person. Full frame only when the move replaces the whole picture.

```bash
python3 .cursor/skills/copy/scripts/frames.py dedupe \
  --video "references/<file>.mp4" \
  --in 27.30:27.47 --out 27.87:27.93 \
  --region 0,0,1,0.32 \
  --output references/clip-notes/comps/<letter>/<move>.jpg
```

Consecutive frames whose region does not change become one cell. `x3` under a cell means three source frames. That is the timing. A `x1` cell is a single frame. The long middle hold is not in the command, so it is not in the sheet.

Omit `--out` when the move never leaves.

## Steps

1. Get the video into `references/` if it is not there. A link only if the user pasted it: `tools/download-ref.sh "<url>"`. Never overwrite `raw-footage/` or an existing reference file. Transcribe with `tools/transcribe.sh`.
2. Split the transcript into sentences. Under each sentence, name every composable graphic. One name, one in, one out. A caption pill is one example per video, not a sheet on every line.
3. For each name, sample a window of at most 12 frames. Look at the sheet. Slide it until A−1, B+1, C, and D+1 are all on sheets you can read.
4. Write those times down from the numbers printed under the cells.
5. Run dedupe on those two spans. Set `--region` to where that graphic sits.
6. Look at the deduped sheet before linking it. Fix the times and run dedupe again if any check fails:
   - First cell is the frame before **this** graphic, not the previous graphic sitting there.
   - The in shows this graphic arriving.
   - The out shows this graphic gone, not the next graphic playing out.
   - Repeated pictures inside the in or the out carry an `xN` that matches the run.
   - A type-on that collapsed into one cell means the region was too big or `--threshold` was too high. Tighten it and run dedupe again.
7. Write `references/clip-notes/<stem>.md`. Sheets go in `references/clip-notes/comps/<letter>/`.
8. Read `.cursor/skills/pipeline/style-sheet.md`. Write `references/styles/<stem>.md` with `role: reference` and `status: draft`. Fill it only from this note and the frames you looked at. One Moves row per named animation, same name, sheet linked. If you did not read a color off a frame, describe it. Do not invent a hex.
9. Stop. Tell the user both paths. Do not write `brand-sheet.md`, remix, or render.

When the user accepts the style, set `status: accepted` and stop, unless that same message already asks to remix.

A clip note that already exists, with no style sheet, gets step 8 only. Re-watch a move whose sheet fails the checks in step 6.

## Note

```markdown
# <stem>

Source: `<file>` · <duration> · <w>×<h> · <fps>

Grids read left to right, top to bottom. `xN` is how many source frames that picture stands for.

## 0:00.0–0:03.2

> <sentence>

**Green title** — In: hard cut to a full green field, the line already set. Out: hard cut back to the talking head.

![Green title](comps/<letter>/green-title.jpg)

*in 0.00–0.03s · out 0.77–0.87s*
```

The caption under the image is the two spans you passed to dedupe, or `holds to the end of the clip` when there is no out.

## Do not

- Guess the boundary from a pixel score. If you cannot see it, sample a tighter window.
- Compare the whole frame when the person is in it. Their movement is not the animation.
- Collapse across the gap between the in and the out.
- Change `brand-sheet.md` or render a final from this skill.
