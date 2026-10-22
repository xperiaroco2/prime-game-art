# The art pipeline

From a raw generation or download to an approved asset in the game. Based on section 2 of the wave 1 report
(`docs/research/2026-10-02-wave-1/report.md`), updated with the engineer's answers on xperiaroco2/prime-game#165
(2026-10-02). Where the report and this page differ, this page wins; where #165 and this page differ, fix this page.

## Since 2026-10-18: Meshy generates the character forms

The engineer chose Meshy as the 3D generator after the three-generator showcase of the alien base character
(`docs/decisions/2026-10-18-meshy-generator.md`, art#196, #203). Where it differs from the sections below, this
section wins:
1. **Concepts:** GPT Image through Meshy's API (`gpt-image-2-5-sunburst`, text to image or image to image),
   turnaround views of one part or character at a time. nano-banana-pro is set aside.
2. **3D:** Meshy multi-image to 3D (`meshy-7.1`) from the chosen concept's views. Tripo is out (its content filter
   refuses unclothed multi-view input) and Rodin was not chosen; any other generator needs the engineer's yes.
3. **Finish:** agents in headless Blender by route R3: keep the sculpt's own surface, collapse decimate to the budget,
   our clay material, bead eyes, the game skeleton and weights, face morphs on the template head
   (`docs/decisions/2026-10-18-faces-as-morphs.md`); then `export`, `godot-check` and `frames`.

Every step runs through a Meshy batch file (`docs/meshy.md`), and every such asset records `ai_generated = true`.

### The roster pilot's heads, step 2a (art #196, 2026-10-22)

The pilot (the chameleon man and the axolotl woman) takes Meshy's raw multi-image heads (step 1:
`batches/2026-10-22-alien-pilot-3d.toml`) to game parts in headless Blender, no paid generation:
`$PYTHON_BIN tools/blender/alien_pilot_run.py [--heads chameleon,axolotl] [--smooth ITER,FACTOR]` runs
`tools/blender/alien_pilot_head.py` per head (through `tools/runner/blender.py`), glTF-Validator on both GLBs and
one Godot picture per head in the off-screen window (`godot/alien/pilot_shots.gd` through `_godot.window()`);
`tools/run.sh godot-check <glb>` runs separately. Output: `<raw>/research/2026-10-22-roster/design/pilot3d/step2a/<head>/`.

What the build does (pure geometry in `alien_pilot_geom.py`, tested by `tools/tests/test_alien_pilot_geom.py`):
- **Eyes found from the texture:** the painted sclera (chameleon) or black bead (axolotl) pixels' faces, clustered per
  side, a sphere fitted to them, made symmetric. New eyeballs (`eye_L`, `eye_R`, a generated 256 px texture with iris,
  pupil and catch light) and solid shell lids (`lid_upper_*`, `lid_lower_*`) at the 2D's rest opening, every eye part's
  origin at its eye's centre; the skin's faces inside a ball are deleted.
- **Lip parting:** the lip line is the deepest valley of the front profile between the lips, tracked bin by bin from
  the middle to the corners; a one-row slit is cut along it, its edges rolled back as a lining (the mouth material)
  into an open mouth cup (`mouth_cup`, its inside facing the slit) and, for the chameleon (his 2D shows one), a
  `tongue`. The lower lip sits behind the upper one, so the valley is shallow: the threshold is 1.5 % of the eye radius.
- **Colour:** the skin and gills are decimated to the budget, unwrapped into one atlas and baked (2048 px colour and
  tangent normal) from the raw model with a palette ramp: Meshy's luminance mapped to the 2D's teal and mint (medians of
  the turnaround's saturated and light pixels); the chameleon's crest stripes are painted in during the bake. Reshapes
  come after the bake, so the texture follows them.
- **Chameleon:** the skull widened above the mouth (10 %), larger bulging eyes, thicker and wider lips (no vertical push
  at the lip line), and the crest-root ledge above each eye smoothed in a soft region (`smooth_grid.png`: the region's
  weights and three strengths, both sides). **Axolotl:** the six gill stalks cut off outside the head's ellipsoid, their
  holes filled, fanned 12 degrees out (pivots at their roots, see below); the raised rim
  around each eye softened.
- `<head>.glb`, `<head>_lod1.glb` (skin and gills at 35 %), `<head>.blend`, `build.json` (eye fits, lip line, palette,
  tri counts), `<head>_compare.png` (2D on top: front, side, back and the expression sheet's 3/4 cell; the new 3D
  below) and `<head>_godot.png`.

The second pass (`--tag v2`, the manager's notes on the first sheets) builds into `<head>/v2/` and copies
`<head>_compare_1280_v2.png` (three rows: the 2D, the first build, this build) and `<head>_godot_v2.png` up:
- **One mesh per part kind** (every build, with or without `--tag`): `<head>_skin` (skin and lip lining), `<head>_eyes` (no normal map needed: the `_eyes`
  rule), `<head>_lids`, `<head>_mouth` (cup and tongue), `<head>_gills`; the pieces' pivots (eye centres, gill roots)
  are the custom property `pivots`, exported as glTF extras for step 2b's bones. Six surfaces or fewer, within the
  contract's cap of 8.
- **Lips:** a volume-keeping Laplacian smooth (`lip_smooth`) on the raw model and the work mesh before the cut, so the
  normal bake does not bring Meshy's lumps back; the mouth cup is narrower (`cup_x`), further back, and every cup or
  tongue vertex outside the skin is pushed just inside it. The axolotl's line comes from the texture
  (`lip_from = "texture"`: the darkest front faces per bin, continuous, within 0.9 of the eyes' spacing) and her lips
  part at rest by `lip_gap`, so the dark lining shows as her smile line.
- **Lids:** a rolled half-circle rim at the free edge; the lower lids' free edge now comes first (it was at their
  root); the chameleon's upper lid at 10 degrees covers the iris's top as in the 2D.
- **Colour and review light:** the ramp's teal is the brighter half of the 2D's saturated pixels (saturation x1.2), its
  light stop the brightest third of the 2D's light pixels (the pale front). The review renders' exposure is set so the
  3D front's median foreground brightness matches the 2D front's, on the 2D's grey (`review_exposure` in
  `build.json`).
- `build.json`'s `gill_length_bins`: each stalk's vertices per tenth of its length (the fewest decides whether a
  spring-bone bend needs a retopology).

The heads are not rigged yet (step 2b: the shared neck, face bones or shape keys, spring bones on the gills), so
`godot-check`'s skeleton, parts and animation checks fail on them by design; its import and texture checks apply.

### T1, the socketed head (art #196, 2026-10-22)

The test of "a head with recesses and separate pieces swapped whole". Step 1 (`batches/2026-10-22-alien-t1-sockets-2d.toml`,
`-3d.toml`) made a chameleon head with empty eye sockets and a mouth dish and, apart, four mouths, three eyes and a
brow in Meshy. Step 2 seats them in headless Blender, no paid generation:
`blender.run_script("alien_t1_kit.py", ["--raw", "<raw>/2026-10-22-alien-t1-sockets-3d", "--out", DIR, ...])`
(`tools/blender/alien_t1_kit.py`; the pure parts in `alien_t1_geom.py`, tested by `tools/tests/test_alien_t1_geom.py`).
- **Measure:** a front depth map of the head (rays along +Y) minus its blurred envelope gives the recesses; per side
  the socket's centre and rim and a sphere fitted to its bowl; the dish is the recess on the muzzle's front (the crease
  under the chin is deeper but far back, so the search keeps to the front 0.15).
- **Eyes:** a clean ball per socket (the bowl's sphere x `--eye-k`), a generated 1024 px texture (white, brown iris,
  pupil, a catch light), its origin at its centre so it turns for gaze. The lids are built here, not Meshy's: per side
  three shells (open, half, closed), each an upper and a lower lid hinged on the eye's side axis (a straight edge from
  the front; they meet at the corners), thicker at the rolled free edge.
- **Mouths and brows:** Meshy's meshes decimated, scaled (mouths x `--mouth-w` the dish's width, the O 0.8 of that;
  brows 1.5 eyeball radii), turned to the skin's normal, sunk 35-40 % of their depth, then every back vertex (back
  half, facing +Y) still in front of the skin is pulled just behind it (`seat_y`), so no gap shows; the log prints each
  piece's remaining float gap. The O's back ball is cut off at 42 % of its depth and a dark throat disc closes its hole.
  Brows come in three seated poses per side (sad, raised, angry) rather than one moved brow, so an expression is only a
  set of visible nodes.
- **Output:** the expressions front and three-quarter, close-ups of the mouth seam and the socket,
  `step2_compare.jpg` (`--ref-approved`, `--ref-h2`: the 2D rows on top), `t1_chameleon_kit.glb` (the head and every
  piece as separate nodes parented to it; glTF has no hidden flag, so the rest set is marked in each node's extras
  `prime_visible_rest`) and `t1_expressions.json` (each expression's nodes and gaze turn). `--grid` renders a mouth
  width x eyeball scale grid instead.

## Since 2026-10-03: the character base and who decides

The direction below changed on 2026-10-03 (xperiaroco2/prime-game#165, stage 1 plan #16). Where they differ, this
section wins:
- **Characters are assembled, not generated.** The base is Quaternius' Ultimate Modular Men and Women (CC0): one
  armature with five-finger chains, plus the toe bones being added in #25. The player chooses a body type. Tops, bottoms and
  shoes are per body type; heads, hair, hats, accessories and our face parts are shared.
- **The character route:**
  - `assemble` builds characters from recipes (`docs/assembly.md`);
  - `catalogue` holds the parts and their compatibility rules (`docs/catalogue.md`);
  - `faces` holds our eyes, brows and mouths (`docs/faces.md`);
  - `retarget` and `anim-review` bake and judge the clips (`docs/animations.md`);
  - `export`, `godot-check` and `frames` carry a character into Godot 4.7.2 (`docs/godot.md`).
- **Meshy makes items and props only.** It is also tried for animations (#25); characters do not come from it.
  (Replaced on 2026-10-18: Meshy now generates the character forms, see the section above.)
- **Who decides:** the trust model (`docs/decisions/2026-10-03-trust-model.md`).
  - The engineer, who acts as the designer, decides taste; the engineer alone decides money and large or hard-to-reverse
    changes.
  - The art manager decides the rest and merges PRs into `main` after the gate.
  - Meshy within the plan's credits and free official downloads run under standing permissions.

## Direction (the engineer's decisions, 2026-10-02)

| Topic | Decision |
|---|---|
| Look | Orient on How to Fish's characters (near-human proportions, flat colours, soft light), then **generate variants and compare**: V1 like How to Fish, V2 a little more cartoony, V3 a painted face, V4 the CC0 Quaternius base for comparison. The best variant becomes the style reference; there is no separate style sheet. The report's "squishy toy crew" with mitten hands is withdrawn |
| Hands | **Five fingers**, so players can make hand gestures. If a generator's rig has no finger bones, agents add them in headless Blender; AccuRIG is the fallback |
| Body | **One neutral body in v1**, about 1.75 m (eyes near the game's 1.6 m), modelled in segments so clothing can replace parts. Variety comes from clothing, hair, face and skin colour |
| Clothing | **Pieces in v1:** `top`, `bottom`, `shoes` (skinned, weights transferred from the body), plus a hat or hair (`hair_or_hat`), a face accessory (`face_accessory`) and a back item (`back_item`), rigid on sockets. **Sets are saved presets of pieces**, not separate meshes |
| Face | **Eyes and mouth are changeable slots, like the hairstyle** (`eyes`, `mouth`). Since 2026-10-18 they are morphs on one template head, with eyeballs, teeth and tusks as separate meshes (`docs/decisions/2026-10-18-faces-as-morphs.md`) |
| Colour | Every piece is **recoloured from one shared palette**; flat colours with no textures, soft light and shadows, no outline by default (compared in renders) |
| Motion | **Animations only.** Falls and knockdowns are canned animations; no ragdoll and no physical wobble (changed 2026-10-11 for the knockdown: it is a ragdoll, every other state a clip; `docs/contract.md`, art #115) |
| First person | **Hands with forearms in the sleeves of your top**, running off the screen edge, plus your own shadow; never floating hands. A true first-person body may come later |
| Names | A player's name shows only when you aim at them up close. A game rule, built in the game repo; the engineer, as the designer, may object on #165 |
| AI rules | Never name How to Fish or any other game or character in a prompt, never upload their screenshots, no personal photos; `ai_generated` recorded per asset; never free-plan output |
| Raw files | `D:/prime-art-raw` on the engineer's PC; chosen originals copied to `OneDrive/prime-art-raw`; never in git |
| Who generates | An agent, through the Meshy API, from the start; each batch only after the engineer's yes to its prompts, count and credits (since 2026-10-03: the standing permission within the plan's credits, see the section above). The engineer buys the plan (Meshy Pro, monthly, from 2026-10-02; a paid monthly plan bought on 2026-10-17; Meshy's top subscription, chosen on 2026-10-18, from the day it starts) and sets `MESHY_API_KEY`; agents never enter keys or payment details |

The look is decided by the engineer, who acts as the designer (@SwiftySinister is not active); the art track proposes and renders,
it does not choose.

## Steps

```
[agent, one batch at a time; Meshy within the plan's credits under the standing permission, approval_ref in batches/]
 1 batch        prompts, count and credits written in a batch file with its approval_ref
 2 generate     Meshy API (characters since 2026-10-18: GPT Image concepts, then meshy-7.1 multi-image to 3D, about
                35 credits per model; other assets: text or image to 3D, about 30 credits): T-pose, five spread fingers,
                6,000-8,000 faces per body, accessories and props smaller; no game or character names in prompts.
                Files -> D:/prime-art-raw/<batch>/ with a log row per task; chosen originals -> OneDrive (raw-backup)
[agent, this repo, blender -b --factory-startup --python-exit-code 1, never a window]
 3 import       GLB in; assert the pinned Blender (5.2.2); every operator must finish
 4 check        triangles, vertices, n-gons, loose and degenerate parts, non-manifold, UVs, applied transforms,
                height, feet at 0, front -Y in Blender (+Z in glTF); budgets from the contract
 5 decimate     only if over budget, then check again
 6 rig          rename bones to the contract's humanoid names (generated by the pinned Godot), add missing bones
                (fingers included) unweighted or weighted, A-pose to T-pose applied as rest if needed
 7 weights      4 influences, normalized, none below 0.01; clothing pieces get weights transferred from the body
 8 palette      drop the AI texture; per-face colour snapped to the shared palette; face decals by hand
 9 animations   bake each source clip onto the contract rig (the knockdown is a ragdoll, not a clip: #115); fix contacts
                (hands meet, reach the head); retime for feel; first-person arm clips for the hands-in-sleeves view
10 export       export: fixed glTF export options; Khronos glTF-Validator (pinned) -> report.json; a non-zero exit
                fails; then godot-check (headless import into godot/) and frames (off-screen Godot sheets)
11 render       8 views at 45 degrees in a 4x2 sheet with a caption; 8-frame sheets per clip; a lit hero image;
                variants side by side. Shown to the engineer as a private artifact page, never committed
[the engineer for the look; the art manager merges after the gate]
12 approve      a PR in this repo: the engineer approves the look on the review page; the art manager merges after
                the gate (trust model); the manifest gets approved_by, approved_at, approval_pr (docs/manifest.md)
[agent, game repo xperiaroco2/prime-game, its own task workflow]
13 bring in     the approved .glb (LFS), its .import, and a credits entry with the public provenance fields
14 check        the game's tools\run.cmd check and its asset tests
15 snapshot     tools\run.cmd shot at 2, 10 and 20 m, lit and dim; images in the PR
16 merge        a human merges
```

Commands by step:
- steps 1 and 2: `meshy` and `raw-backup` (`docs/meshy.md`);
- steps 3 and 11: `probe` and `render` (`docs/blender.md`);
- steps 4 and 6: `contract`, `check` and `rename-bones` (`docs/contract.md`);
- step 9: `retarget` and `anim-review` (`docs/animations.md`);
- step 10: `export`, `godot-check` and `frames` (`docs/godot.md`);
- every step: `manifest-check`, for the manifests and `sources/` records.

The Quaternius characters come from `assemble` (`docs/assembly.md`) with parts from `catalogue` (`docs/catalogue.md`)
and faces from `faces` (`docs/faces.md`); the generated characters since 2026-10-18 follow the section at the top.
Decimation, weight transfer and the palette recolour are later issues.

## What is committed
Per asset, `assets/<kind>/<id>/`: `manifest.toml`, `source/` (the working .blend), `export/` (the .glb), `report.json`.
Never: raw generations or downloads, review renders, keys. Every binary goes through Git LFS; the account's repos share
10 GiB, so drafts stay in the raw folder.

## Licences
Allowed into the public game repo (`public_repo_ok = true`): CC0, CC BY with credit, owned paid output (a paid
Meshy plan's output: "owned, all rights reserved"; terms reread when the plan changes, `docs/meshy.md`), our own
work. Private only (`restricted`): Mixamo, store packs, raw Meshy library motions, anything unclear. Never: free-plan AI output, non-commercial data.

## Open (decided later, on #165)
- The final budgets and socket positions, measured on the first approved body (the contract, #4).
- Whether Meshy's auto-rig has finger bones (the first rigged body settles it).
- The talking mouth waits for voice playback in the game (an engine request).
