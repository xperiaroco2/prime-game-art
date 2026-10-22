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

### Step 2b-1: polish and the face rig (art #196, 2026-10-22)

`$PYTHON_BIN tools/blender/alien_pilot_run.py --out <raw>/.../pilot3d/step2b --rig --prev ".../step2a/{head}/v2/views"`
builds both heads (the compare sheet's middle row is the `--prev` build) and rigs them; `--only-rig` rigs the
existing build. The polish in `alien_pilot_head.py`:
- **Chameleon lips** (`lip_tube`): two rolled tubes along the lip line (its height and depth even quartics fitted to
  the bins; radius 0.3 mouth units tapering to a fifth at the corners; the front at the measured protrusion), every
  lip vertex moved to its point on the tube's circle, fading out toward the skin, behind the tube and past the
  corners; the slit's edge moves with the lips. Meshy's creases are in the baked textures too: `flatten_lips` makes
  the normal map flat and the colour the lips' median over the same weights (rasterised in UV space).
- **Chameleon side view:** the lids' outer corner opens (`lid_corner_outer`: upper 6, lower -32 degrees against the
  inner corner's -12 and -14), so the side shows the eye white as in the 2D.
- **Axolotl front** (`pale_front`): a positional two-tone mask over the ramp (the object-space normal facing the front,
  0.35 to 0.8, times the height below the eyes) mixes toward the 2D's near-white mint, the source's luminance keeping
  the freckles; a band round the lip line stays teal.
- **Axolotl eyes:** a tiny white cap (`catch_light`, 10 degrees) on each bead, its UVs on the eye texture's glint, so
  the eyes read alive and `godot-check`'s `eye_pupils` finds near-white vertices.
- `build.json`'s `lids`: each lid's `lid_mesh` parameters, which the rig rebuilds.

`alien_pilot_rig.py` (headless, through `tools/runner/blender.py`) adds the face rig to `<head>_rig.glb`:
- **Bones** under `Head` (the contract's `Head`, `Jaw`, `LeftEye`, `RightEye` names): `LipUpper`, `LipLower` (under
  the Jaw), `Left/RightLipCorner`, `Left/RightBrowInner` and `BrowOuter`, `Left/RightLidUpper` and `LidLower` at the
  eye centres; 16 bones. The axolotl adds a three-bone chain per gill stalk (`LeftGill1_1`..`_3`, root to tip from the
  `pivots` extras) for 2b-2's `SpringBoneSimulator3D`: 34 bones.
- **Weights by position**, not heat: the Jaw below the lip line inside an ellipsoid round the chin, the lip bones on
  their own side of the line, the corners round the corners, the brows above the eyes, the rest on `Head`; the eyes,
  lids and mouth cup rigid; the gills blended along their chain.
- **Blend shapes**, the same name on every mesh they move (Godot imports glTF morph targets as blend shapes; the GLB
  has no animations, so `godot-check`'s animation checks fail by design): `blink_L`, `blink_R` (the upper lid
  rebuilt stretched to the lower lid's edge, a spherical shell, so nothing pokes through) with the corrective
  `blink_arc_L/R` (a blend shape moves in a straight line, so a half blink would cut through the eyeball: drive
  `blink_arc_*` at 4t(1-t) with `blink_*` at t); `smile`, `sad`, `angry`, `surprised` (mouth O) and `talk` (open):
  bone poses (`POSES`) baked into the skin and mouth, each with its own lids rebuilt at other edge angles and tilted
  round the gaze.
- **Review:** `<head>_rig_1280.png`: the 2D expression sheet's six cells above the 3D's six at the same 3/4 view, then
  the blink strip (open, half, closed), the side and front at rest and a bone check (the jaw open, the gills bent); the lids get planar UVs (Godot
  generates tangents for blend shapes and errors on a mesh without UVs);
  `<head>_godot.png` is the rigged GLB in the off-screen Godot window; `rig.json` (bones, weights per bone, shape keys,
  the largest skin shift per expression).

**2b-1b (the rig's second pass):** `alien_pilot_run.py --out .../step2b --only-rig --rig-tag v2` rigs the 2b-1 build
into `<head>/v2/` (the sheet and Godot shot copied up as `<head>_rig_1280_v2.png`, `<head>_godot_v2.png`; the summary
`run_summary_v2.json`); `--grid` writes only the variant grids, `<head>_grid_lips.png` and `<head>_grid_expr.png`.
- **Chameleon lips (`build_lips`):** a wireframe close-up showed the "stitches" were the slit's cut row, a jagged row
  of folded triangles in the decimated lining, which also read as teeth with the mouth open. The lip zone is now a
  separate swept mesh: per lip 48 quad rings of 24 round an elliptic core along the fitted lip line (denser at the
  corners, tapering and tucking into the cheeks there, a pole closing each end), the upper and lower lip kissing at
  the line, in the lips' sampled colour. The skin inside a lip's ellipse is drawn into it (a smooth remap of 1.6
  ellipse radii onto 0.8), then the faces wholly inside, those drawn into both lips and those spanning the line are
  deleted: the open mouth shows the dark cup and the tongue. The lip mesh is weighted by tube (its upper lip's
  bottom ring lies on the line, and a height test split it vertex by vertex into a row of teeth); the skin round the
  slit by the side the cut puts it on (`slit_sides`: connected pieces near the line, the corners left out), else
  the lip it was drawn into. `clear_lining` deletes the lining behind the slit on both heads. Grid picked: radius
  0.42 mouth units, fullness (depth over height) 1.2.
- **Expressions:** `RIGCFG[head]["amount"]` scales every bone move, jaw angle and corrective of a pose, `"lid"` the
  lids where they need their own factor (his heavy lids cover the iris past 1; her small lids need 2 to show). Picked
  from the 3-amount grid per expression: chameleon 1.75 throughout; axolotl smile 2.2, sad and angry 2.5, surprised
  1.75, talk 2.5. Correctives added to the posed shapes: the smile's cheeks lifted and puffed, the angry knit between
  the brows. The O pulls the corners in by 0.28 half widths per amount and forward. The axolotl's brows weigh a wider
  area (1.5 eye radii) and move in larger units (2.2 eye radii). The mouth cup and tongue take the face's weights
  (corners, lips, jaw), so no cup shows at a moved corner.
- **Blink:** the closed eye is flattened along the gaze (chameleon 0.3, axolotl 0.6 of its front bulge; the eyeballs
  get `blink_L/R` too), so the closed lid sits close over the eye instead of reading as a ball.

### Step 2b-2: mouth leftovers, the shared body, living gills (art #196)

`alien_pilot_run.py --src-dir <step2b> --out <step2c> --only-rig` rigs step 2b's head builds into a new folder;
`--grid-mouth` writes `<head>_grid_mouth.png` (rows: GRID_MOUTH's variants; columns: rest and smile in 3/4, talk and
surprised from the front); `--only-char --char <alien_body.blend>` welds the rig onto the body; `--sheet` adds the
Godot sheets.
- **Surprised O:** a corrective on the posed shape squeezes every point round the mouth toward the midline by `o` of
  its distance (a Gaussian round the mouth, the face's front only) and puckers it forward: a small round O, corners
  in. Picked from the grid: `o` 0.6 for both.
- **Tongue:** lifted in talk by `tongue` mouth units (up, half as much forward; half of it in the O): chameleon 0.35,
  axolotl 0.3. The axolotl's head build has no tongue; the rig adds hers (`add_tongue`) as the build makes his.
- **Lips:** the axolotl gets her own swept band (`lips` radius 0.24, flush: `prot` 0, the skin drawn in from
  `draw` 2.4 ellipse radii so her painted band hides under it). The flank away from the line runs out into the skin
  as a tail (`blend`, chameleon 0.7, axolotl 0.5) and the lips take the skin's roughness: a soft crease instead of a
  tube glued on. The chameleon's lip moves are smoothed along each tube (`tube_smooth` 30 passes) against the corner
  kink; not for the axolotl (it pulled her tubes off her skin in the smile). The slit past the lip corners is
  weighted as on the line, so the open mouth no longer parts it into flaps.
- **The shared body** (`tools/blender/alien_pilot_char.py`): the parts kit's body (`M15/b/s/cage/build/
  alien_body.blend`: `Body` on `CharacterArmature`, the contract skeleton and the clips, the open 48-vertex neck ring
  at z 1.39). The head turns to -Y and scales so its eyes sit at the skeleton's eye joints (1.608 m); its neck's
  waist (the narrowest slab below the face) sits on the ring's axis 8 mm above the ring; the skin below is cut off and
  the 5 cm above the cut morphs onto the ring's ellipse; skin and body are joined (the skin active, its blend shapes
  kept) and bridged (`bridge_loops`), custom normals cleared, all smooth. The face bones join the body's armature
  under its `Head` (the body's `Jaw`, `LeftEye`, `RightEye` replaced by the head's); the head's skin takes `Neck`
  weight from the ring's 0.7 at the cut to 0 at 7 cm. The body's plain material takes the neck's colour (the game
  replaces it by name). One GLB per character, `<head>_char.glb`, with the body's clips; `char.json` holds the fit.
- **Living gills:** `godot/alien/pilot_gills.gd` (`docs/godot.md`, "The pilot's living gills").

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
