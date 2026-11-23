# Hero props: code-built shape, a shader library and a critic loop (draft)

**Status:** proposed, a draft for the engineer (2026-11-23). Not in force: choosing a pipeline and its tools is his
decision (CLAUDE.md, "Decisions"). Research: the AI-art pipeline lane, art#392 follow-up; the evidence is
`docs/research/2026-11-23-ai-prop-pipeline.md` and its review page.

## Context
The engineer: everything we make looks like a demo, not a release, and he is tired of redoing the same prop. He asked
how AI tools alone, with no human artist, can make Steam-quality props right the first time, proven on one prop: the
beer stein (concept 3, art#392).

What the research found:
1. **The gap is the look, not the mesh.** The rough build had the right sizes but flat standard materials: clear
   glass read as a grey film, the beer as an orange block, the foam as a lid. A critic scored it 16 of 45. Glass,
   liquid and foam in a real-time game come from shaders written for them, as in every game that does them well.
2. **AI mesh generators make good silhouettes, not usable glass.** Meshy 7.1 (image to 3D from the concept, 30
   credits, about 3 minutes) gave the best facet read in a still, but painted the beer onto the outside of an opaque
   shell, made the handle grey plastic, and gave one mesh with no beer or foam to move: no half, empty or drinking
   state is possible (critic: 21 of 45, item 7 at 1). Its shape-only model (20 credits) took more cleanup than the
   lathe-like stein is worth: a crumpled base and a wall that had to be grown by script (20 of 45). For opaque,
   organic or complex props a generated mesh is a fast blockout; for glass and liquids it is a reference at most.
3. **The free generators are out of reach here.** The official TRELLIS.2 space refuses anonymous runs (ZeroGPU
   quota). Local runs need an NVIDIA GPU with 16-24 GB, and this machine has an AMD Radeon 860M. Hunyuan3D's licence
   excludes the EU, UK and South Korea.
4. **An independent critic finds the same faults a person would.** Four critics, each fresh, named the same
   blockers without seeing each other's notes. But a critic misreads stylised features: it took the foam's lacing
   rings for moire. Scores move in whole points and lag behind visible gains. The builder must look too, and a
   pairwise judgement against the last round is more useful than an absolute score.
5. **The loop plateaus without new technique.** Eleven rounds took the stein from 16 to 26 of 45, then it held at
   22-26. Two critics on the same renders differ by up to 3 points. What moved the scores was measurement: the
   concept's colours read by a script, then fitted. The pass (every item at 4) was not reached with screen-space
   glass and procedural foam.

## Decision (proposed)
Every hero prop (held items, then weapons) goes through one pipeline, inside the existing Gates 0-5
(`docs/decisions/2026-10-31-asset-pipeline-gates.md`):

1. **Concept** (Gate 0): OpenAI images as now, judged by the engineer.
2. **Spec** (Gate 1): `<prop>_dims.toml`, sizes in cm against the contract, the states the game needs (full, half,
   empty; charged, spent; ...).
3. **Shape**:
   - from code in headless Blender (lathe, sweep, panels, booleans) for hard-surface and turned shapes: exact
     sizes, clean topology, separate parts for every state;
   - or from Meshy (shape only, 20 credits) as a blockout for organic or complex shapes, then cleaned by script
     (remesh, decimate, rebuild the parts that move).
4. **Look**: a shared Godot material library (`godot/materials/`, growing from the mug lab's glass, beer and foam):
   shaders for glass, liquids, foam, painted and bare metals, plastics, emissive parts, each with a few uniforms and
   no per-prop code. States are uniforms (a fill level, a charge), never separate models.
5. **Lookdev stage**: one Godot scene per map's light (lobby, ship) with the review views: 3/4 on its surface, side,
   top, a close-up, first person at the viewmodel lens, each state, and a short clip of any change of state.
6. **Calibration and measurement**: before the loop, a critic scores the approved concept itself, and the rubric is
   fixed until the concept passes. A script measures the concept's colours and values per material
   (`godot/mug_lab/_probe.gd`), and the look is fitted to those numbers before any critic sees it.
7. **Bake what does not depend on the view**: Cycles bakes the thickness, edges and studio light of glass-like
   materials into one map (`tools/blender/mug_lab_bake.py`); live shaders keep the states and the refraction.
8. **Critic loop**: two fresh Opus critics a round, scored absolute and pairwise, with the rubric (`docs/research/2026-11-23-prop-critic-rubric.md`), the
   concept and the renders, never the code. From round 2, pairwise against the last round. Measurable items (sizes,
   triangles, levels) go to scripts. At most 5 rounds; a round that scores lower is reverted.
9. **The engineer's look** (Gate 5) on a private page, with the clip. The rubric advises him and does not gate:
   after 14 rounds the stein plateaued at 25-27 of 45 with every judge tried (the bake, by a material-slot bug, was
   never in the judged renders; its effect is untested).
10. **A package check before any handoff**: the game's own load of the package folder, headless, checks the nodes,
   the marker frames, the states and the triangles (`godot/mug_lab/package_check.gd`). It caught two bugs that
   fourteen rounds of renders and critics did not: a glass mesh without a material and a turned marker frame.

## Consequences
- No new tool or service. Meshy stays under the existing standing permission for blockouts and textures of opaque
  props; OpenAI images stay for concepts.
- The material library becomes the style's backbone: a second glass prop starts from the mug's glass, not from zero.
- Budgets: a held prop has up to 10k triangles (the director took the recommendation, 2026-11-23). The mug lab's
  stein went from 18.4k to 9.9k: the glass 7.1k, the beer 0.6k, the foam 2.2k. Godot's automatic import LODs serve
  other players' copies, but a mesh that a shader shapes (the foam) needs LOD generation off.
- First person: glass refraction reads the screen behind it, so it works only when the viewmodel draws in the main
  viewport (a FOV-correcting viewmodel shader). The hands today draw in a transparent SubViewport, where the glass
  would show nothing behind it. That is a game-side choice (prime-game), to settle with Code before the mug ships.
- Cost per hero prop, measured on the mug: 4 Sonnet critic runs of about 85-95k tokens each, Meshy 0-50 credits, and
  the builder's own session.

## Options not taken
- **AI mesh with its textures straight into the game:** the fastest still, but no states and no material control;
  for glass and liquids it fails the rubric's material items.
- **Local open-source generators** (TRELLIS.2, Hunyuan3D): no suitable GPU here; Hunyuan's licence excludes the EU,
  UK and South Korea.
- **A human artist:** outside the brief.
