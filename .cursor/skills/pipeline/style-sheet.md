# Style sheet

Copy and remix both write this shape. Copy writes one file per reference at `references/styles/<stem>.md`. Remix writes the brand at `brand-sheet.md`.

Status values:

- A reference style is `draft` until the user accepts it, then `accepted`.
- The brand is `draft` until the user approves it, then `approved`. Set `approvedAt` to that date.

Sheet links:

- From `references/styles/<stem>.md`: `../clip-notes/comps/<letter>/<move>.jpg`
- From `brand-sheet.md`: `references/clip-notes/comps/<letter>/<move>.jpg`

Use the same move name as the clip note. In and Out describe the move (hard cut, 8-frame pop, type-on). They are not transcript timestamps. When, on a reference, is when that video uses the move. When, on the brand, is when we use it.

```markdown
---
status: draft
role: reference
sources:
  - references/clip-notes/<stem>.md
video: references/<file>.mp4
---

# <Name>

## Promise
One sentence. On a reference, what this video feels like. On the brand, what a finished video of ours should feel like.

## Frame
Aspect, fps, safe margins.

## Palette
| Role | Hex | Use |
| --- | --- | --- |
| <role> | <#hex> | <where it goes> |

## Type
| Role | Face | Weight | Size at 1080 |
| --- | --- | --- | --- |
| <role> | <face> | <weight> | <size> |

## Captions
Face, size, case, words per card, fill, stroke, position, highlight rules.

## Picture
When to cut, when to punch in, zoom, b-roll versus talking head.

## Moves
| Move | What it is | In | Out | When | Sheet |
| --- | --- | --- | --- | --- | --- |
| <same name as the clip note> | <what the graphic is> | <how it arrives> | <how it leaves> | <when it is used> | [<name>](../clip-notes/comps/<letter>/<move>.jpg) |

## Sound
Music bed versus voice, SFX, silence.

## Decisions
4 bullets. Choices the edit keeps making.

## Do not
Hard no's.
```

On the brand, drop `video:` and list the reference style files under `sources:`. Set `role: brand`. Point Sheet at `references/clip-notes/...`.
