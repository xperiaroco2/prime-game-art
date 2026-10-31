# The asset pipeline's gates: concept, spec, motion, detail, defect hunt, his look

- Date: 2026-10-31
- Status: accepted (the engineer, 2026-10-31 ~12:00 UTC, in chat with the art manager, on the findings page
  https://claude.ai/artifact/4yo3JCyWzoKgG4bb4UTVZJ ; his yes recorded on
  [#196, comment 6543365574](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6543365574); the
  proposal and its summary:
  [#196, comment 6542991280](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6542991280)).
- Applies to every new character part, garment and hero prop from now on (for a prop that no body wears, Gate 0 is
  the concept and Gate 1 the drawing, as for the crystal); it adds gates to the steps in
  `docs/pipeline.md` and does not replace the release-quality ADR (`2026-10-17-release-quality.md`) or the trust model.

## Context

Her dungarees took about 40 builder steps (art #196: C1 to C1k, E1 to E1m, M2a to M2m; briefs and handoffs in
`D:/prime-art-raw/manager/clothes/`), and the result still missed the concept: the bib sat too low, it bent and the
straps slid on it in motion. The retrospective (the research report, summarised on #196 c6542991280) found seven
root causes:
1. **The concept was never turned into measured targets on the body.** E1i's bib raise lived only in a command-line
   argument (`clothes_top.flat_bib`, `--bib-raise dz,b0,b1`, off by default; `e1i-handoff.md`), and M2 lost it. The
   concept puts the bib top at 0.70 of the waistband-to-shoulder span; d79 had 0.38 (`m2m-handoff.md`).
2. **Each image or 3D step copied the one before it**, not the concept: the s2 turnaround dropped the bib under her
   bust, and Meshy copied the turnaround.
3. **The clothes were made before the bodies were final.** Refitting a garment onto a changed body bent her bib
   (D3's bodies came after C1's dress).
4. **Meshy output is a fused figure, not a garment**: a dressed statue whose cloth has to be cut off a body.
5. **Motion was checked late and on stills**, and the MP4s went unwatched (about 40 "not viewed" in the handoffs). The bib
   motion step (M2m) measured the straps sliding 16 to 72 mm on the bib across 9 clips only at the end.
6. **The checks measured the easy things** (triangles, pokes, gaps), not what the engineer judges: the silhouette
   against the concept, the sizes, the motion.
7. **Steps were loops of small fixes** on one kind of defect instead of a change of route: M2c to M2h each
   cleaned up the Meshy dungarees' leftovers and shards, M2e to M2l came back to the turn-ups, cuffs and ankle, and
   E1j to E1j3 polished the sneaker.

## Decision

Every asset passes six gates in order; a gate is passed only when its checks are green and, where named, the engineer
has said yes. Nothing from a later gate starts before the earlier one passes.

- **Gate 0: the concept on the frozen body.** The body and its skeleton are frozen before any garment work starts.
  The concept is drawn onto renders of that final body (gpt-image, flat light), with an automatic check that the body
  stayed hers (her outline and proportions unchanged under the garment). The engineer approves the design once.
- **Gate 1: the spec and its drawing.** One `<asset>_dims.toml` per asset, generalising the crystal's
  `tools/blender/crystal_dims.toml` and the bodies' `tools/blender/body_dims/*.toml`: every size in cm and as a ratio
  to the body's landmarks (collarbone, armpit, bust peak, waist, crotch, knee, ankle), the panels, thicknesses and
  hardware, which view wins where the concept's views disagree, and the behaviour (what stays flat, what bends, what
  moves with what). A drawing script draws it over the concept and over the body. The engineer approves it once. Every
  later brief cites the spec and its tolerances; no target lives only in a script argument.
- **Gate 2: a rough build judged in motion first.** A plain material, skinned, playing the game's clips in the
  game's look. Automatic numbers: a silhouette overlay per view against the concept (the overlap and a mm error
  table), every spec number measured on the build within its tolerance, slip at the joins per clip, the flatness of
  stiff panels, stretch, pokes. His page: concept, drawing and build at one scale from the front, side and back, and a
  front close-up Walk and Jog video. He approves the shape and the motion before any texture.
- **Gate 3: detail** (texture, stitching, hardware). Gate 2's numbers are re-run after each step and must not move.
- **Gate 4: the defect hunt.** Close-ups and a fresh critic given the spec and the concept (never an intermediate
  image), and the numbers table. No sheet or video counts as checked until someone has viewed it.
- **Gate 5: his look, then the PR.**

The rules around the gates:
- **Two steps on one kind of defect mean a change of route** (regenerate it, or build it in code), not a third fix.
- **An intermediate image is shown to the engineer only at full size, with the concept overlaid and measured
  callouts.**
- **A garment is made per body**, never refitted from another body.
- **His taste words become a written behaviour rule** in the spec (for example "the bib stays flat and the straps
  stay glued to it"), confirmed with a picture before building.

Which tool for what:
- **gpt-image:** concepts, and translating a concept onto the body (Gate 0); never a source of measurements.
- **Meshy:** soft organic forms (trouser folds, soft props) or retexturing our own mesh; always on the final body,
  and measured at Gate 2 before money is spent on cleanup.
- **Code (headless Blender):** flat, structural, measured parts: bibs, straps, bands, cuffs, shoes, props from
  drawings.
- **Tools in hand:** Blender's cloth simulation, Data Transfer and Surface Deform; ours: `body_dims_*`, `body_fit_*`,
  the `*_drawing.py` scripts, `clothes_measure.py`, `clothes_proof.py`, `frames`, `showroom`.
- **To write:** the spec format and its drawing script, a silhouette overlap check, general slip, flatness and
  stretch numbers, a review page template. Nothing to buy or install.

## Consequences

- The engineer looks three times per asset (Gate 0's design, Gate 1's spec, Gate 2's shape and motion) before his
  final look at Gate 5; no texture or polish reaches him before the shape moves right.
- Work on a garment waits for its body to be frozen: for her dungarees, the body comes first (the Walk hop, the hand
  and wrist, the finger poses), the dungarees' spec and drawing in parallel, then the build on the frozen body.
- Briefs get longer by one line (the spec and its tolerances) and shorter by the history they no longer paste; the
  manager's brief rules are in `docs/agents.md` ("Briefs under the asset gates").
- Critics get the spec and the concept, so their findings are measured against the target, not against the last step.
- The checks still to write (the silhouette overlap, slip, flatness and stretch, the review page template) are
  written before the first asset reaches Gate 2 (for her dungarees, before their build); Gate 2 does not pass
  without them.
- `docs/pipeline.md` ("Since 2026-10-31: the asset gates") places the gates in the pipeline and describes the spec
  file.
