---
name: remix
description: >-
  Remix one or more accepted reference style sheets into brand-sheet.md in
  the same shape: our palette, type, captions, and the moves we keep. Use
  when the user says remix, make it ours, lock the style, or brand sheet,
  and style sheets already exist. Writes status draft and stops. Does not
  start a storyboard.
---

# Remix

Reference style sheets in. One brand out. The shape is `.cursor/skills/pipeline/style-sheet.md`.

## Inputs

Use the files the user named. Naming a `draft` accepts it: set `status: accepted` on that file, then mix.

If they did not name files, use every `references/styles/*.md` with `status: accepted`.

If none are accepted and they did not name one, stop. A pasted link or a video with no style sheet is copy's job (`.cursor/skills/copy/SKILL.md`). Do that and stop. Do not invent a brand from the video.

One accepted style is enough.

## Write the brand

1. Read each style sheet and the clip note it cites. Open the contact sheets for the moves you might keep.
2. Replace `brand-sheet.md`. Set `role: brand` and `status: draft`. `sources:` lists the style files. No `video:` key.
3. Invent a name. Generalize across the sources. No creator names, no "copied from", no catchphrase kept as ours.
4. Keep a move when it can recur. Drop one-off gags. Same move name as the clip note, so the reference sheet still matches. When is our rule. Sheet links are `references/clip-notes/...`.
5. Palette and type are ours. Shared choices can be kept. A hex you did not see stays out.
6. Decisions are four choices, not adjectives. Do not lists the hard no's, including their series names, icons, and music we do not have rights to.
7. Stop. Show the sheet. Do not write a storyboard.

When they approve, set `status: approved` and `approvedAt` to that date. Do not start apply unless that same message asks for it.

## Revise

A correction they state ("the accent is blue") edits `brand-sheet.md` in place. An already `approved` sheet stays `approved`.

A new mix from reference styles always writes `status: draft`, replacing the previous brand text.
