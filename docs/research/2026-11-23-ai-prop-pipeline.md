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
| A7 → A29 (rounds 5-11) | the same, to the 10k budget (inner wall 3.62 cm, a faceted handle, bolder panels), one profile-shaped foam, fitted colours | 0 | 9,930 | 23 … best 26 |

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

## Rounds 5-11: towards the rubric's pass (the engineer's "take it to a pass", 2026-11-23)
Pipeline A went from 23 to a best of 26 of 45 (round 11, `a29`: 9,930 triangles). The two critics of rounds 8-11 gave:
- round 8: 23 and 26;
- round 9: 22 and 22;
- round 10: 25 and 23;
- round 11: 26 and 23.

No round passed (every item at 4 or more). The loop stopped there, past the rubric's 5-round rule.

What moved the scores, and what did not:
- **Measurement beat eyeballing.** A Godot probe (`godot/mug_lab/_probe.gd`) reads HSV profiles across the beer and
  the head in the concept and in a render:
  - concept beer: s 0.9-1.0, v 0.31-0.96; ours: s 0.45, v about 0.8 flat;
  - concept head: s 0.25-0.35, shading from v 1.0 to v 0.7; ours: s 0.05.

  Fitting the shaders to those numbers was the first change the critics called better on most items (round 10, six
  items better pairwise).
- **Calibrate the rubric on the concept.** Scored as a render, the concept got 4-5 on every item but style (2,
  "photoreal, not cartoon"). Item 8 is now anchored to the approved concept.
- **Critic noise is about ±3 points.** Two critics on the same renders differ by up to 3, and some praise what the next
  round's critic blames (the head's overhang, its cell texture). Use pairwise verdicts and two critics; require the
  pass twice.
- **Godot traps:**
  - an imported mesh's automatic LODs collapsed the shader-shaped foam's canonical rings into a cone (LOD off for
    such meshes);
  - Vulkan's NDC y and SCREEN_UV y point the same way;
  - points returned through int-parameter shader functions came out wrong in 4.7.2 (use plain locals);
  - AgX washes a bright amber out (keep the beer darker);
  - glass on a dark stage reads as grey plastic until a reflection probe and a lit background give it something to
    show.
- **The remaining gap** is the same in every critique: the glass reads plastic (the handle, the empty glass), the
  head's dome sits on a band, and the half-state foam reads as a faceted disc. Screen-space refraction and procedural
  foam seem to top out here. The proposed next step is baked glass: Cycles renders the glass's light and refraction
  into textures, and only the beer, the level and the foam stay live in Godot.

## Rounds 12-14: baked glass and an Opus critic (the director's choice, 2026-11-23)
- **Baked glass** (`tools/blender/mug_lab_bake.py`, `mug_lab_run.py --bake`):
  - Real refraction depends on the view, so it stays live. Cycles bakes what does not: R the thickness (inside
    AO, 2.5 cm), G the edges (bevel normal against face normal), B a glossy bake of a drawn studio (an equirect
    image: a warm ring, a softbox toward the holder, a cold window, a strip).
  - The three go into one 1024² map on the glass's own UVs, carried in the GLB as its base colour and read by
    `glass.gdshader`.
  - Cost: 3-4 minutes of Cycles on the CPU per mug.
  - **Correction (the package check, after round 14): the bake never reached the shader in rounds 12-14.** The
    boolean union of the handle left the glass mesh an empty first material slot, every face used it, and the GLB's
    glass had no material, so `mug_look.gd` found no map and `baked` stayed 0. The critics of rounds 12-14 judged the
    shader edits of those rounds without the bake. The build now keeps one slot (`mug_lab_build.py`,
    `mug_lab_bake.py`), and the bake itself is still untested.
- **Two Opus critics a round**, absolute and pairwise against the last round.
  - Opus names defects with pixel positions and rarely flip-flops.
  - Two Opus critics still differ by up to 4 points (27 and 23 on round 13).
- **Scores** stayed in a band:
  - round 12: 26 and 26;
  - round 13: 27 and 23;
  - round 14: 25 and 27.

  With both models the loop plateaued at 25-27 of 45 without a bake; whether the bake lifts the ceiling is open.
  The director's rule applies: stop, and put the best mug (round 14, `b35`) to the engineer's own look. From here the
  rubric is advice.
- **Still named by both critics:**
  - the beer reads orange, not a light golden lager, with bubbles like dust;
  - the empty glass reads as smoked chrome;
  - the base reads milky;
  - the head reads bun-like;
  - the handle is plainer than the concept's.
- **Budget:** the judged round-14 mug was 10,370 triangles; the packaged build is trimmed to 9,954.
- **The package check also caught the Grip's frame** built column by column in Blender: its +Y ran along +x. The
  glTF exporter changes the basis of a node's axes as it does positions, so the frame is now `G2B @ M_godot @ G2B^-1`.
- **Packaged on the research branch only** (`assets/prop/mug_research`, `tools/blender/mug_lab_package.py --check`):
  M8 ships the art lane's mug (`assets/prop/mug`). The engineer found the research mug "more or less fine".
- **The next technique, if he wants more:** two-layer glass with a separate back-wall pass, and the liquid drawn to its
  own buffer. That is days of work.

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
