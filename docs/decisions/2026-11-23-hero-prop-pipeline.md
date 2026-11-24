# Hero props: code-built shape, a material library and a critic loop

**Status:** accepted. The engineer, 2026-11-24, in chat, relayed by the director: asked "do we adopt the research's
approach for hero props after M8?", he answered "Так, приймаємо" ("yes, we adopt it"). The yes covers this record and
its companion, the style guide (`docs/research/2026-11-23-prop-style-guide.md`, v1), and stands the research's
technical choices of the night of 2026-11-23. It applies to hero props after M8: M8 ships the art lane's mug
(`assets/prop/mug`) as it is. Research: the AI-art pipeline lane, art#392 follow-up; the evidence is
`docs/research/2026-11-23-ai-prop-pipeline.md` and its review page.

The lab's code (`tools/blender/mug_lab_*.py`, `prop_lab_*.py`, `godot/mug_lab/`) and the research mug's package (`assets/prop/mug_research`) stay on the research branch `claude/research-ai-3d-pipeline-0ebca6` (commit cbaa94c6); paths to them below point there. They come to `main` with the first hero prop built this way, after M8.

## Context
The engineer: everything we make looks like a demo, not a release, and he is tired of redoing the same prop. He asked
how AI tools alone, with no human artist, can make Steam-quality props right the first time, proven on one prop: the
beer stein (concept 3, art#392).

What the research found:
1. **The gap was the shape and the look together; neither alone moved it.** The art lane's first mug was a plain
   cylinder with flat materials. The research mug has a code-built form with real detail (pillow panels with arched
   ends, a heavy faceted foot, a swept D handle) and written shaders. A 2x2 split on one stage, two Opus critics each,
   items 1-6, 8 and 9 (of 40), shows how the two combine:

   | | Plain materials | Our shaders |
   |---|---|---|
   | First mug's shape | 16.5 | 18.5 |
   | Research mug's shape | 16.5 | 23.5 |

   The detailed shape alone gained nothing, because flat alpha glass hides its panels (the critics did not see
   them). The shaders alone gained 2. Together they gained 7. The engineer's reading holds: the form matters, and it
   pays off only when the materials show it.
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

6. **The same holds for an opaque hard-surface prop.** A crew work light (trial 2): built from code with the style
   guide's library baked in Cycles, it scored 19, then 23 of 40 after one round of fixes. Meshy's textured model as it
   comes scored 15.5. Its shape with the library's materials scored 15 with flat shading and 15 with smooth. The
   generator's triangle soup shows facets on every curve, carries off-palette colours and does not unwrap for a bake.
   Its preview is a good one-minute blockout for the code build.

## Decision
Every hero prop (held items, then weapons) goes through one pipeline, inside the existing Gates 0-5
(`docs/decisions/2026-10-31-asset-pipeline-gates.md`):

1. **Concept** (Gate 0): OpenAI images as now, judged by the engineer.
2. **Spec** (Gate 1): `<prop>_dims.toml`, sizes in cm against the contract, the states the game needs (full, half,
   empty; charged, spent; ...).
3. **Shape**:
   - from code in headless Blender (lathe, sweep, panels, booleans) for hard-surface and turned shapes: exact
     sizes, clean topology, separate parts for every state;
   - Meshy (a text or image preview, about 20 credits) is the blockout and the reference for the layout, not the
     game mesh. Its triangle soup shades faceted, and it neither bakes nor carries the palette (trial 2). For truly
     organic shapes (a plush, a creature) a generated mesh is remeshed and cleaned by script, as the vault plush was.
4. **Look**: two shared libraries, both from the style guide (`docs/research/2026-11-23-prop-style-guide.md`):
   - for opaque parts, Blender node materials by class (painted metal, frame, steel, rubber, lens, energy,
     emitter) with edge wear and AO, baked in Cycles to base, metal-rough and emission (`tools/blender/prop_lab_light.py`);
   - for glass, liquids and foam, Godot shaders (`godot/materials/`, growing from the mug lab's), each with a few
     uniforms and no per-prop code.

   States are uniforms (a fill level, a charge), never separate models.
5. **Lookdev stage**: one Godot scene per map's light (lobby, ship) with the review views: 3/4 on its surface, side,
   top, a close-up, first person at the viewmodel lens, each state, and a short clip of any change of state.
6. **Calibration and measurement**: before the loop, a critic scores the approved concept itself, and the rubric is
   fixed until the concept passes. A script measures the concept's colours and values per material
   (`godot/mug_lab/_probe.gd`), and the look is fitted to those numbers before any critic sees it.
7. **Bake what does not depend on the view**: opaque props bake their library materials (AO, edge wear) to
   textures. Glass may bake its thickness, edges and studio light into one map (`tools/blender/mug_lab_bake.py`), but
   on the stein that gained about half a point, within the critics' spread; live shaders keep the states and the
   refraction.
8. **Critic loop**: two fresh Opus critics a round, scored absolute and pairwise, with the rubric (`docs/research/2026-11-23-prop-critic-rubric.md`), the
   concept and the renders, never the code. From round 2, pairwise against the last round. Measurable items (sizes,
   triangles, levels) go to scripts. At most 5 rounds; a round that scores lower is reverted.
9. **The engineer's look** (Gate 5) on a private page, with the clip. The rubric advises him and does not gate:
   after 14 rounds the stein plateaued at 25-27 of 45 with every judge tried, and two rounds of baked glass held at
   26-27.
10. **A package check before any handoff**: the game's own load of the package folder, headless, checks the nodes,
   the marker frames, the states and the triangles (`godot/mug_lab/package_check.gd`). It caught two bugs that
   fourteen rounds of renders and critics did not: a glass mesh without a material and a turned marker frame.

## Process
**One hero prop, one session.** A hero prop (anything held in first person, anything the player inspects up close,
later every weapon) gets a session of its own. That session works on that one prop through Gates 0-5 with the critic
loop and the package check, and does nothing else. The throughput lane (the art lane) does not build hero props
between other tasks; its job for them is packaging and integration: the contract with Code, the hand poses, the
import, the game-repo PR.

Why:
- **The two mugs show the gap.** The research mug was one session's only task. Its shape has pillow panels with
  arched ends, a heavy faceted foot and a swept D handle, and its look has states and measured colours. The art
  lane's first mug was one task among the bar, the mirror, the console and the hall: a plain cylinder with flat
  materials, scored 16 of 45.
- **The loop needs continuity.** The critic loop needs a builder that keeps the prop's whole history: what was tried,
  what the critics flip-flopped on, which bug hid what. A lane that switches between many tasks loses it.
- **The package check belongs to the prop's session.** It caught bugs in this research that fourteen rounds of renders
  missed; it must run before any handoff.

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
- Cost per hero prop, measured on the mug and the light: two Opus critic runs a round of about 85-95k tokens each,
  Meshy 0-30 credits for a blockout, and the builder's own session.

## Options not taken
- **AI mesh with its textures straight into the game:** the fastest still, but no states and no material control;
  for glass and liquids it fails the rubric's material items.
- **Local open-source generators** (TRELLIS.2, Hunyuan3D): no suitable GPU here; Hunyuan's licence excludes the EU,
  UK and South Korea.
- **A human artist:** outside the brief.
