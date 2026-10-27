# AI Video Editor

A local Cursor workspace that cuts, captions, and scores talking-head footage. Open **this folder** in Cursor (`Documents/projects/aieditor`), not the talking-head-2 repo.

## Layout

```
raw-footage/       drop camera originals
references/        style examples, clip notes, and one style sheet per reference
exports/           finished MP4s
storyboards/       review docs before a render
brand-sheet.md     your brand — must be approved before a cut
```

## First session

1. Open this folder in Cursor.
2. Drop a reference (or paste a link) and say **copy this**.
3. Accept the style sheet it writes.
4. Say **remix** to turn the accepted styles into your brand sheet. Approve it.
5. Drop footage in `raw-footage/` and say **apply**.
6. Review the storyboard. Talk to it like an editor (“make the hook bigger”).
7. When the board is right, tell it to build. When that cut looks right, tell it to export. The MP4 lands in `exports/`.

Say **pipeline** to run those stages in order. It still stops at each review.

## Tools already on this machine

FFmpeg, yt-dlp, whisper.cpp (`tools/models/ggml-base.en.bin`), HyperFrames, Remotion.

```bash
tools/check.sh
```
# HyperFrames
