---
name: apply
description: >-
  Apply the approved brand sheet to a raw video and write a storyboard in
  clip-note shape: each sentence, the move, and the reference contact sheet.
  After the user accepts the board, build it on their footage, add our
  contact sheets, and iterate. Export only when asked. Use when the user
  drops raw footage, says edit this, cut this, apply, or gives a note like
  make the hook bigger.
---

# Apply

Approved brand plus raw footage in. A storyboard out, then a cut, then an export when they ask.

## Preconditions

1. `brand-sheet.md` is `status: approved` (`role` may be absent on an older sheet). If it is missing or `draft`, stop. Remix first (`.cursor/skills/remix/SKILL.md`).
2. List `raw-footage/`. If it is empty, ask them to drop files there.
3. Read the brand sheet. Follow it. Moves come from its Moves table.

## Pass 1 — storyboard

1. Transcribe each new clip (skip if `raw-footage/<stem>.words.json` is newer than the media):

   ```bash
   tools/transcribe.sh "raw-footage/<file>"
   ```

2. Watch the transcript plus a few ffmpeg frame grabs. Decide the cut: drop vocalized pauses (`um` / `uh`), dead air, and false starts. Keep the successful take. Pick the hook. Optional alt intro. Caption chunks follow the brand. Music and SFX stay inside the brand. Do not download a track they did not supply.

3. For each sentence on the cut, pick the moves that land on those words. One name from the Moves table, one in, one out. A caption move is described once under Across the video, then named on the line, not given a new sheet every sentence.

4. Write `storyboards/<slug>-vN.md`. Each move links the reference contact sheet from the brand table. The image is the reference, so the line under it says `reference sheet`.

5. Stop. Tell them the path. Do not compose, snapshot, or render.

```markdown
# <Working title> — vN

Source: raw-footage/<file>
Brand: <sheet name>
Status: review

## Across the video
- Runtime in / out
- Hook choice (and alt intro if any)
- Caption style
- Music (source + target loudness vs voice)

## 0:00.0–0:03.2 — Keep

> <sentence on the cut>

**Green title** — Lands on "<word>". Hard cut already set. Gone before the next sentence.

![Green title](../references/clip-notes/comps/<letter>/green-title.jpg)

*reference sheet*
```

Rate every sentence Keep, Maybe, or Drop.

## Pass 2 — build after they accept the board

Read `/hyperframes` first, then `/hyperframes-cli`, `/hyperframes-registry`, and `/media-use`.

1. Copy or proxy the approved footage into `assets/`. Never overwrite `raw-footage/`.
2. Author the cut in HyperFrames. Talking-head `<video>`, captions, music `<audio>`, moves from the brand, punch-ins as seekable GSAP. Entrances land on the word the storyboard names.
3. `npm run check`. Fix errors.
4. Snapshot the seconds you touched and look at the frames.
5. Render a review cut at draft quality to `storyboards/frames/<slug>/review.mp4`. Keep it out of `exports/`. Read `/hyperframes-cli` for the render command.
6. For each move, dedupe our in and out with `.cursor/skills/copy/scripts/frames.py`. Same rules as copy: region on the graphic, not the person. Write `storyboards/frames/<slug>/<move>.jpg`.
7. Add that sheet under the reference sheet. The line under it is the spans you passed to dedupe, prefixed `ours`.
8. Stop. Do not copy anything into `exports/`.

## Notes

"Make the hook bigger" and any other note: change the storyboard sentence, change the composition, snapshot the changed seconds, rebuild the ours sheets for the moves that changed, stop. Do not export a new final as part of the note.

## Export

Only when they ask. Render at delivery quality and copy the MP4 to `exports/<slug>-vN.mp4`. If the composition changed since the review cut, render again before copying.
