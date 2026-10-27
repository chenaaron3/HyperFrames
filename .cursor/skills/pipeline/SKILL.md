---
name: pipeline
description: >-
  Run the local edit pipeline: copy a reference into a clip note and style
  sheet, remix accepted styles into brand-sheet.md, then apply that brand to
  raw footage. Use when the user says pipeline, run the whole process, or
  hands over a reference and raw footage together. Copy, remix, and apply
  can also be run on their own. Stop after copy, after the draft brand, and
  after the storyboard. Do not export until they ask.
---

# Pipeline

Four skills. This one only routes. Read the stage skill and follow it.

| Stage | Skill | Writes | Stops |
| --- | --- | --- | --- |
| Copy | `.cursor/skills/copy/SKILL.md` | Clip note + `references/styles/<stem>.md` | Style is `draft`. Wait for acceptance. |
| Remix | `.cursor/skills/remix/SKILL.md` | `brand-sheet.md` | Brand is `draft`. Wait for approval. |
| Apply | `.cursor/skills/apply/SKILL.md` | `storyboards/<slug>-vN.md` | Board is in review. Wait before building. |

A viral text-over-b-roll reel from the b-roll library is `.cursor/skills/broll-format/SKILL.md`, not this pipeline.

## Which stage

Run the stage they named.

- A reference video, a clip-note request, or "copy this" → copy.
- Accepted style sheets, or "remix" / "make it ours" / "lock the style" → remix.
- Raw footage, "edit this", "apply", or a note on a cut ("make the hook bigger") → apply.
- "Pipeline", or a reference and raw footage in one ask → start at the first stage that has no output yet.

If they paste links and ask for a brand before any style sheet exists, copy each video and stop. Do not remix in that turn.

## Gates

Do not cross a gate in the same turn you produce it.

Their message can cross a gate that already exists. "These styles are good, remix" accepts the drafts and remixes. "Brand approved, apply this footage" approves and starts the storyboard. "Board is right, build it" starts the cut. "Export" writes `exports/`.

Saying "pipeline" or "go" does not cross a gate.

- Copy never writes `brand-sheet.md` and never renders.
- Remix never starts a storyboard.
- Apply never builds the composition until they accept the board, and never writes `exports/` until they ask.
