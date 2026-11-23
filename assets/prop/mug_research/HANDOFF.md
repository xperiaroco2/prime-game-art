# The research mug of beer: handoff

**On the research branch only.** M8 ships the art lane's mug (`assets/prop/mug`, tag `lobby/furniture/mug3`), and this
package does not replace it; no PR goes to the game for it.

This is the AI-art pipeline research's round-14 mug (art#392 follow-up), concept 3, the faceted glass stein. The engineer
found it "more or less fine" (2026-11-23; the review page https://claude.ai/artifact/8JSFkeqdCA2EQuhnnDc2vU). It is
packaged as the pipeline's worked example, under the same contract as the art lane's mug (the director's notes,
`art-mug-392/contract.md`), so it can stand in for it if the engineer later chooses. Out of scope: the right hand's grip
pose (`MugSocket` and the clips in `fp_hands.glb`, the art lane) and any drinking motion.

## Files

| File | What |
|---|---|
| `export/mug.glb` | Meshes `Mug` (the glass and the handle), `Beer` (a node holding `Liquid` and `Foam`), the `Grip` marker. The triangles are in `report.json` (under the held-prop budget of 10,000). Origin at the middle of the base's underside, +Y up, the handle on +X, the holder's side +Z. Its materials are plain fallbacks; the look below replaces them |
| `export/mug_look.gd` | `apply(model, levels)` puts the look on an imported `mug.glb` and returns it; `set_fill(look, f)` sets the state (below). It preloads the three shaders from its own folder |
| `export/glass.gdshader` | The glass, the only transparent surface. It refracts what is behind it (the screen texture), with panel lenses, edge darkening, studio reflections and lacing rings left as the level drops |
| `export/beer.gdshader` | The beer, opaque, cut at the fill level (the cut opens the cylinder and its back faces draw the surface), with rising bubbles |
| `export/foam.gdshader` | The foam, one volume: its vertex stage shapes the canonical `Foam` mesh from the fill (the head over the rim when full, a layer on the beer when drinking) |
| `source/mug.blend` | The build (`tools/blender/mug_lab_build.py`, `mug_lab.toml`) |

## In the game

- **Size:** real size, no scaling. The glass is 15 cm tall and 9.1 cm across, and the foam head rises to 18.2 cm. The
  handle reaches 8.4 cm on +X.
- **Placing:** by `Grip` alone, as the contract says.
  - `Grip` sits at (7.45, 8.0, 0) cm on the handle's upright bar. Its +Y runs up the bar and its -Z points toward the
    mug's axis (`report.json` `package_check`).
  - The mug's transform under a socket is `Grip.transform.affine_inverse()`.
- **The look:**
  ```gdscript
  const MugLook = preload("res://assets/props/mug_research/mug_look.gd")
  var look: Dictionary = MugLook.apply(mug_instance, {"floor": 2.2, "full": 12.6, "rim": 15.0, "inner_r": 3.62, "rim_r": 4.5, "head_top": 18.2})
  MugLook.set_fill(look, 1.0)   # full
  ```
  The levels are centimetres from `report.json` (`mesh.levels_cm`). Every `apply` makes the mug its own materials.
- **States:** `set_fill(look, f)`, with `f` from 1 (full) to 0 (empty); tween `f` to drink.
  - **1:** the head stands over the rim.
  - **0.68-1:** the head settles into the glass over the first third of a drink.
  - **Below that:** a foam layer of 0.9-1.5 cm rides the beer and thins as the level drops, and lacing rings appear on
    the glass above it.
  - **0:** `Beer` is hidden and only the lacing remains; this is the `mug_empty` item.
- **First person:** the glass refracts the screen behind it, so it shows the room only when it draws in the same
  viewport as the room.
  - The hands draw today in a transparent SubViewport, and there the glass would show nothing behind it.
  - Draw the held mug in the main viewport, with a viewmodel FOV shader. The director noted this for Code after M8.
- **Import:** turn LOD generation off for the `Foam` mesh (the import's per-mesh `generate_lods`).
  - It is a canonical unit whose shader shapes it, and generated LODs collapse it into a cone.
  - `apply()` also sets its `lod_bias` to 128 and a custom AABB.
- **Shadows:** on (the default).
- **Collision:** none made here. A cylinder of 4.6 cm radius and 15 cm height fits the glass. The handle is not
  needed for a drop.
- **Cost:** `report.json` gives the GPU time of a full first-person frame of the review stage at 1280x720 on the
  review machine's Radeon 860M. The bubbles and the foam's Worley cells are per-pixel noise, cheap at the mug's
  size on screen.

## What the critics still named (advice, not a gate)

The rubric (`docs/research/2026-11-23-prop-critic-rubric.md`) did not pass. Two Opus critics scored round 14 at 25 and
27 of 45, with 4 for the first-person read. Still named:
- the beer reads orange rather than a light golden lager, with bubbles like dust;
- the empty glass reads dark, like smoked chrome;
- the base reads milky;
- the head reads bun-like;
- the handle is plainer than the concept's (no thumb rest).
