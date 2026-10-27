---
name: broll-format
description: Recreate a viral b-roll format (text-over-b-roll reels like "Sometimes I forget how blessed I am", "laugh at your mistakes", "who wrote the rules?") from the user's own b-roll library using a Gemini clip index. Use when the user says make format #N, recreate this reel with my broll, b-roll video, annotate/index my broll, or adds a new format.
---

# B-roll format

Text-over-b-roll reels: the reference's cut points, text timing and music are kept; the user's own clips and words replace the picture and copy. Storyboard first, render only after approval.

These videos use the reference's native look (small white outlined text), not `brand-sheet.md`. The brand-sheet gate does not apply here.

## Pieces

| Path | What |
| --- | --- |
| `formats/<id>-<name>/format.json` | One format: reference video, duration, text style, `lines` (timed text with ref copy + guide), `shots` (timed slots with a brief) |
| `formats/<id>-<name>/brief.txt` | The format book's notes (text hook, caption, b-roll guidance) |
| `broll-index/clips/*.json` | Gemini annotation per clip: summary, camera, quality, tags, `moments[]` with start/end, action, emotion, `good_for`, score |
| `videos/<slug>/plan.json` | The edit: format id, text per line, clip + in-point per shot, caption |
| `videos/<slug>/index.html` | Generated HyperFrames root (own project; assets in `videos/<slug>/assets/`) |
| `storyboards/<slug>.md` | Review doc: reference frame vs pick per shot |

b-roll lives at `BROLL_ROOT` (default `/Users/aaron/Documents/Broll`). Clip paths in plans and the index are relative to it. Never modify it.

## Index the library

Needs `GEMINI_API_KEY` in `.env` (`GEMINI_MODEL` optional, default `gemini-3.8-flash`). Proxies (360p) are cached in `.broll-cache/`; originals are never uploaded.

```bash
tools/broll.sh annotate --pilot 30        # stratified sample, check quality first
tools/broll.sh annotate --folder SelfShots
tools/broll.sh annotate --all             # skips clips already indexed and unchanged
tools/broll.sh search --stats
```

After a pilot, read 3–5 clip JSONs against the footage (grab a frame at a moment's start) and report whether timestamps and descriptions hold up before indexing the rest.

## Make a video

1. `tools/broll.sh new <format-id> <slug>` scaffolds `videos/<slug>/plan.json` with the reference text and each shot's brief.
2. Draft the lines: read `brief.txt` and the line `guide`s. Adapt to the user's life and to what the index actually has (e.g. climbing, NYC, cooking, apartments). Keep the reference's rhythm and length: each line must be readable in its slot (about 3 words per second at most). Keep lines marked verbatim.
3. Pick shots. For each shot slot, search with words from the line and the brief:

   ```bash
   tools/broll.sh search "eating bowl spoon" --creator --min-score 3 --min-len 2.7
   tools/broll.sh search --clip "SelfShots/Eating/IMG_5177.MOV"
   ```

   - The moment must be at least the slot length (×`speed`). Set `in` to where the action reads best, not always the moment start.
   - Match the brief's camera grammar (selfie vs tripod vs filmed-by-friend) and the line's literal meaning first, mood second.
   - Don't reuse a clip in one video unless the format repeats a shot. Vary locations across adjacent shots.
   - `speed` 0.5 only for 120fps slow-mo sources or a clip too short at real time.
   - Write a one-line `note` per shot: why this moment.
4. `tools/broll.sh storyboard <slug>` validates and writes `storyboards/<slug>.md`. Look at the pick frames yourself; swap weak ones.
5. **Stop.** Give the user the storyboard path, the lines, and any slot the library could not fill well (suggest what to film).

## After approval

```bash
tools/broll.sh compose <slug>
npx hyperframes check videos/<slug> --json
npx hyperframes snapshot videos/<slug> --at <mid of each shot> --against <format reference> --describe false
npx hyperframes render videos/<slug> -o exports/<slug>.mp4
```

Look at the `pair-*.jpg` sheets (render | reference): text size, weight, position and wrap should match the reference. Fix style in the format's `text` block (or a line's `y`), recompose, re-snapshot. Render only when the pairs match.

## Notes from the user

"Swap shot 3", "make line 2 punchier": edit `plan.json`, re-run `storyboard`, and if already composed, `compose` + snapshot the changed seconds. Don't silently re-export.

## Add a format

1. Copy the reference into `references/viral-formats/ref-format-<id>.mp4`; save the docx text as `brief.txt`.
2. Cut points: `ffmpeg -i ref.mp4 -vf "select='gt(scene,0.25)',showinfo" -an -f null - 2>&1 | grep pts_time`. Use the video stream duration, not the container's.
3. Text changes usually land on cuts; confirm on a 4 fps strip of the text band. One `line` can span several `shots` (a montage).
4. Measure text: y centre, size, weight, manual line breaks (`\n`). Write each shot's brief from the reference frame.
