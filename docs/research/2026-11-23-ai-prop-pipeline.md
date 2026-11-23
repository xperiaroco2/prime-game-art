# AI-only props at release quality: three pipelines on the beer stein (research, 2026-11-23)

The question (the engineer, via the director): how can agents, with no human artist, make Steam-quality props right
the first time? Proven on one prop: the beer stein, concept 3 (art#392). The proposal that follows from it is the
draft ADR `docs/decisions/2026-11-23-hero-prop-pipeline.md`. The review page (private):
https://claude.ai/artifact/8JSFkeqdCA2EQuhnnDc2vU.

## The trials
Every trial is rendered by `tools/blender/mug_lab_run.py --tag <tag>` through `godot/mug_lab/shots.gd` in an
off-screen window, on a lookdev stage: a dark steel bar top, a wall with light strips, a warm key, a cold rim and a
procedural reflection room (`studio_sky.gdshader`). The views are 3/4 on the bar, side, top, a close-up, and first
person at the viewmodel's 50 degree lens (the hand's grip pose is separate work). Each state is shot full, half and
empty, with a 3 s drink clip. The raw output is under `<raw>/research/mug-lab/<tag>/`.

| Trial | How | Meshy | Triangles | Critic (of 45) |
|---|---|---|---|---|
| baseline | the rough build on `feat/lobby-furniture` (`mug3`), standard materials | - | 1,680 | 16 |
| B1 | Meshy 7.1 image to 3D from the concept, textured PBR, as it comes (`mug_lab_ai.py --mode plain`: turned, scaled to 18.2 cm tall and 9 cm across) | 30 | 7,958 | 21 |
| C1, C2 | Meshy 7.1 shape only (quad remesh), cut at the rim, a wall grown inward by Solidify, the lab's beer and foam inside, the lab's shaders (`--mode hybrid`); C2 with round 4's shaders | 20 | 19,556 | 20, 23 |
| A2 → A6 | the stein from code (`mug_lab_build.py`, `mug_lab.toml`): 12 pillow panels with arched ends, a heavy foot, a swept D handle, one boolean union; the lab's shaders (`godot/mug_lab/`) | 0 | 18,410 | 21, 22, -, 23 |

The batch: `batches/2026-11-23-research-mug-image-to-3d.toml`, approved in chat and recorded on art#392. It spent 50
credits; the balance is now 6,740.

## The look: what each shader does
- `beer.gdshader`: the beer is opaque and is cut at `level` with `discard`. With cull disabled, its back faces show
  through the cut and are drawn as the flat surface (the liquid-in-a-mesh trick). The colour runs from deep at the
  edges to bright where the beer faces the viewer, with a lit band under the surface. Bubbles rise in columns. The
  bottom is lit, so the heavy base does not read as a brown slab.
- `foam.gdshader`: one canonical mesh (`foam_unit`: UV.x is the dome's share, UV.y the side's). The vertex stage
  builds the foam from the fill: a side from the level to `top`, swelling to the rim's outer radius once it passes
  the rim, and a cushion dome of height `dome_h`. Lumps, a ragged lower edge, Worley bubble cells and crevice shading
  break up the surface. Round 1's separate head and layer read as a lid on a strip.
- `glass.gdshader`: the only transparent surface, with ALPHA 1 and `depth_draw_always` (only the nearest surface
  shows). It draws:
  - the screen behind, shifted by the view-space normal (refraction);
  - a white Fresnel edge;
  - matcap-like studio reflections in view space, so every facet catches light from any side;
  - crease lines from `fwidth(NORMAL)`;
  - a faked far wall where the depth buffer says the inside is empty (the handle and the empty glass read as black
    plastic without it);
  - lacing rings and drips on the body only, between the foam and where the head was.
- `mug_look.gd`: `apply(model, levels)` and `set_fill(look, f)`. The crown goes with the first sip (f 1 to 0.86),
  then the layer thins, and lacing appears as the level drops.

## The critic loop
- The rubric is `docs/research/2026-11-23-prop-critic-rubric.md`: 9 items scored 0-5 with written anchors. The pass
  is every item at 4 or more and no blocker.
- The critic is a fresh Sonnet agent per judgement. It gets the rubric, the concept and the renders, never the code;
  from round 2 it also gets the last round's renders for a pairwise verdict.
- Seven judgements: 82-96k tokens and 30-40 s each.

What it showed:
- Independent critics named the same blockers (the foam as a lid, the beer as a block, the dark handle). The loop
  finds real faults.
- Critics misread stylised detail: round 2's regular lacing rings were called moire. The builder must look too.
  Pairwise verdicts were more informative than absolute scores, which move in whole points and lag behind visible
  gains.
- No trial passed. A climbed 21 → 22 → 23 in three judged rounds (round 3's A4 was not judged). The remaining
  blockers are the same in A6 and C2:
  - the foam still reads smooth;
  - the glass reads thin (C's thicker wall is the one thing it does better);
  - the beer lacks depth.

## Findings that change how we work
1. The demo look came from the materials and the lighting, not the mesh: the same sizes went from 16 to 23 points
   mostly through shaders.
2. AI generators give a strong silhouette fast (Meshy 7.1: 2-3 minutes, 20-30 credits). They paint transparency
   onto an opaque shell, and give no parts for states. For glass and liquids, use them as a reference or a blockout
   at most.
3. The free open generators are out of reach on this machine:
   - TRELLIS.2's official space refuses anonymous runs (ZeroGPU quota);
   - local generation needs an NVIDIA GPU with 16-24 GB, and this machine has an AMD Radeon 860M;
   - Hunyuan3D's licence excludes the EU, UK and South Korea.
4. First person: screen-space refraction needs the viewmodel in the main viewport. The game's hands draw in a
   transparent SubViewport today (`assets/body/fp_hands/HANDOFF.md`), where the glass would see nothing behind it.
5. GPU: the full first-person frame, 1280x720, costs 5.0 ms on the Radeon 860M (the whole stage, not the mug alone).

## Next, for the mug (if the engineer takes pipeline A)
- A thick wall as in C: the inner wall deeper and the glass edge visible.
- Foam with larger bubbles and shadowed crevices.
- Beer with a darker edge and a brighter core.
- The lookdev stage lit as the real lobby.
- A reduction pass toward a hero budget (proposed 10k at LOD0).
- Then the art lane's grip pose, and Gate 5.

## Sources
The web research reports are in the shared notes, `research-ai-3d/generators.md` and
`research-ai-3d/shaders-critic-style.md`:
- the generators: versions, credits and licences;
- Godot's liquid-in-mesh shader (CC0), the Half-Life: Alyx bottle shader write-up, BlenderGym's critic agreement
  figures;
- the style-guide contents.

No public technical write-up of Deep Rock Galactic's mugs was found; only techniques were taken from public sources.
