# The prop critic's rubric (research draft, 2026-11-23)

A fresh agent with no stake in the build judges review renders against this rubric, the approved concept and the
spec. It never sees the build's code or the builder's notes, only the pictures, the concept, the spec's numbers and
this page. Built for the beer stein (art#392) in the AI-art pipeline research; meant for every hero prop.

## What the critic gets
- The approved concept image (the target look).
- The renders, each named: the 3/4 view on the bar, straight side, top, a close-up, first person (full, half,
  empty) and the drink clip's frames.
- The spec's few numbers that bind (sizes, the handle side, the fill levels).
- For a round after the first: the previous round's renders beside this round's, for a pairwise judgement.

## Scores
Each item 0-5. Anchors: **5** release art in a well-reviewed Steam game; **4** good, one small thing a player might
notice up close; **3** reads correctly but looks cheap or unfinished (a demo); **2** a clear defect or a wrong read;
**1** broken; **0** missing.

| # | Item | What a 5 looks like | Typical 2-3 |
|---|---|---|---|
| 1 | Silhouette and proportion | Matches the concept's shape language and the spec's sizes; reads as the object from every view; parts in proportion | Wrong proportions, a stubby or spindly handle, a missing signature feature |
| 2 | Primary material read (here: glass) | Instantly thick clear glass: refraction, darker edges, crisp highlights along facets | Looks like plastic, frosted, or a flat grey film |
| 3 | Secondary material read (here: beer) | Instantly liquid: depth colour (deep at the edges, bright through the middle), life (bubbles), a surface | A solid orange block; flat colour; no surface |
| 4 | Detail material (here: foam) | Soft, bubbly, volumetric, an irregular natural edge | A smooth white cap; a plastic lid |
| 5 | Construction and defects | Nothing crooked, floating, intersecting, z-fighting or seamed; no shading artefacts | Visible gaps, a crooked part, faceting where it should be smooth, flicker |
| 6 | First-person read | Within a second at hand distance it reads as the object, at the right size in the hand | Too big or small; unreadable against the room |
| 7 | States (here: full, half, empty, drinking) | Each state reads; the change between them is believable (the level goes down, the foam rides on it, the empty glass is still glass) | A state reads wrong; the foam floats or vanishes oddly |
| 8 | Style fit | The house style: stylised adult cartoon, clean bold readable shapes, crisp bevels, rich materials; sits in the dark teal-grey steel lobby | Photoreal clutter, toy-like, or clashing colours |
| 9 | Release polish | A Steam player would take it for finished release art | Reads as a prototype or a demo |

**Pass:** every item at 4 or more, and no blocker. A blocker is any defect a player would notice in normal play.

## What the critic returns (JSON)
```json
{"scores": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0, "9": 0},
 "blockers": ["..."],
 "fixes": [{"rank": 1, "image": "q34_full", "where": "the handle's top", "what": "...", "why": "..."}],
 "unsure": ["..."],
 "verdict": "pass | fail"}
```
- At most 6 fixes, the most valuable first, each concrete (what to change, where in which image).
- Reasoning before the scores; no praise padding; "unsure" for what the image does not show clearly rather than a
  guessed defect.

## Pairwise rounds
From round 2 on the critic also answers, per item: is round N better, worse or the same as round N-1? The images go
in both orders (two critic calls); a change counts as better only when both orders agree. Measurable items (sizes,
triangle counts, the fill levels, overlap with the concept's silhouette) go to scripts, not to the critic.

## Stop rule
Stop when the pass holds in two critics in a row, or after 5 rounds; then the engineer's look (Gate 5). A round that
scores lower than the one before is reverted, not built on.
