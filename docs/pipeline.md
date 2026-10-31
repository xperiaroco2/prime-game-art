# The art pipeline

From a raw generation or download to an approved asset in the game. Based on section 2 of the wave 1 report
(`docs/research/2026-10-02-wave-1/report.md`), updated with the engineer's answers on xperiaroco2/prime-game#165
(2026-10-02). Where the report and this page differ, this page wins; where #165 and this page differ, fix this page.

## Since 2026-10-31: the asset gates

Every new character part, garment and hero prop passes six gates in order
(`docs/decisions/2026-10-31-asset-pipeline-gates.md`, the engineer's yes of 2026-10-31 on #196). They wrap the steps
below; where they differ, this section wins:

| Gate | What | Where it sits in the steps below | Who says yes |
|---|---|---|---|
| 0 | The concept on the frozen body (gpt-image onto renders of the final body, flat light; a check that the body stayed hers) | before step 1, through its own image batch (`approval_ref`, `cost_cap_usd`); the body and skeleton are frozen first | the engineer, once |
| 1 | The spec and its drawing: `<asset>_dims.toml`, drawn over the concept and the body | before step 2 (generation) or a code build | the engineer, once |
| 2 | A rough build in motion: plain material, skinned, the game's clips and look; silhouette overlay, spec numbers, slip, flatness, stretch, pokes; a front close-up Walk and Jog video | after steps 3 to 7 (import, check, rig, weights): a rough export run through `frames` early, outside the step numbering; before step 8 | the engineer: shape and motion |
| 3 | Detail: texture, stitching, hardware; Gate 2's numbers re-run each step and unchanged | step 8 for texture; stitching and hardware are geometry steps of their own | its checks |
| 4 | The defect hunt: close-ups, a fresh critic given the spec and the concept, the numbers table; every sheet and video viewed | after steps 10 and 11 | its checks |
| 5 | His look, then the PR | step 12 | the engineer |

Which tool makes what: gpt-image the concepts and their translation onto the body, never measurements; Meshy the soft
organic forms (trouser folds, soft props) or a retexture of our mesh, always on the final body; code the flat,
structural, measured parts (bibs, straps, bands, cuffs, shoes, props from drawings). A garment is made per body, never
refitted from another. Two steps on one kind of defect mean a change of route. The manager's brief rules are in
`docs/agents.md` ("Briefs under the asset gates").

### The spec file: `<asset>_dims.toml`

One TOML file per asset is the source every brief, build script, check and critic cites. It generalises two
precedents: the energy crystal's engineering drawing, `tools/blender/crystal_dims.toml` with `crystal_drawing.py`
(`docs/props.md`, "A hero prop from code: the ship engine's energy crystal"), and the bodies' dims tables,
`tools/blender/body_dims/A.toml` and `B.toml` (`docs/clothes.md`, "Bodies by drawing"). It holds:
- **Its source:** the approved concept's path and the body it is drawn on, where each number was read (view and pixel
  rows) and the scale (cm per px).
- **Sizes:** every size in cm, and for a garment also as a ratio to the body's landmarks (collarbone, armpit, bust
  peak, waist, crotch, knee, ankle; the body table's own landmarks), so a size can be checked on the body it was made
  for.
- **Parts:** the panels, their thicknesses and edges, and the hardware (buttons, buckles, loops), each with its place.
- **Tolerances:** per number, how far the build may be off; the Gate 2 and Gate 3 checks read them.
- **Which view wins** where the concept's views disagree, written beside the numbers it affects (as the crystal's file
  does for its band and windows).
- **Behaviour:** what stays flat, what bends, what moves with what (for example a bib that stays flat with straps glued
  to it); the engineer's taste words become these rules, confirmed with a picture before the build.

A drawing script (`<asset>_drawing.py`, like `crystal_drawing.py` and `body_drawing.py`) draws the numbers over the
concept and over the body; the engineer approves that drawing once (Gate 1). After that a change to a target is a
change to the file, never a script argument or a brief alone.

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

### The roster pilot's static premium heads (art #196, 2026-10-22)

The engineer's goal after the rigged faces (2026-10-22): the chameleon man and the axolotl woman as **static** heads
(no blink, talk or expressions, no face rig) with premium materials and a skin colour the player can change. The
rigged builds looked wrong where lips and lids were cut out of Meshy's fused sculpt and glued back, so this route does
**no surgery**: Meshy's own sculpt, decimated, keeps its sculpted lids, lips, gills and painted eyes.
`$PYTHON_BIN tools/blender/alien_static_run.py [--heads chameleon,axolotl] [--no-build] [--no-shots]` runs
`tools/blender/alien_static_head.py` per head (through `tools/runner/blender.py`), glTF-Validator on both GLBs and the
Godot sheets (`godot/alien/static_shots.gd` through `_godot.window()`); `tools/run.sh godot-check --textured <glb>`
runs separately. Output: `<raw>/research/2026-10-22-roster/design/pilot3d/static/<head>/`, about 3 minutes a head.

- **Geometry:** the dense original (`multi_image_to_3d-pre_remeshed_model.glb`, one closed shell, the same frame as the
  textured remesh) decimated symmetrically to 32k (chameleon) and 40k (axolotl) triangles, LOD1 at 45 % (14.4k,
  18k). The chameleon's crest-root ledge is smoothed in step 2a's soft region after the bakes (smoothing before them
  left the colour bake's rays short of the source: black patches).
- **Maps** (a new smart UV atlas): `<head>_albedo.png` sRGB (baked at 4096, saved at 2048 for the contract's `texture_size`), `<head>_normal.png` 2048 tangent (from the dense
  original; flattened on the painted eyes and the ledge), `<head>_mask.png` 2048 linear: **R the skin tint mask**
  (1 skin, 0 the painted eyes: inside each eye's fitted sphere, the texels that are not teal), G roughness (skin 0.42,
  lips 0.28, eyes 0.04 for a wet glint, gills 0.5), B the subsurface and sheen weight. The albedo is Meshy's texture
  through step 2a's palette ramp (and the chameleon's crest stripes), its saturation then matched to the 2D front's
  teal and pale medians; the eyes keep Meshy's own paint (sclera cleaned toward white, iris a little richer).
- **The GLB** has one material `<head>_static_skin` (albedo, roughness from the mask's G, normal) that any glTF viewer
  shows; extras `base_skin_srgb` (the albedo's skin teal) and `tint_mask`. In Godot `godot/alien/alien_static.gd`
  swaps it for the tint ShaderMaterial (`docs/godot.md`, "The alien pilot's static heads").
- **Sheets:** `<head>_base_choice.png` (the 2D front, side, back and roster image; this build; step 2a's v2, Workbench),
  `godot/views.png` (front, 3/4, side, back, face close-up under the showroom's AgX), `godot/strip.png` and
  `colour.json` (the 2D, Blender, then the tone variants, measured), `godot/views_pick.png`, `godot/colours.png`.
- **The pale fault:** the albedo matches the 2D (teal saturation 0.54 against the 2D's 0.54 on the axolotl after the
  match; Blender's Standard view of it 0.43, the 2D's own front render 0.46 to 0.55). Godot's showroom AgX at exposure
  0.9 drops the rendered teal's saturation to 0.31 to 0.35 and lifts the skin into AgX's shoulder, where it washes
  toward white: the same albedo reads pale. Step 2a's palette stops, taken from the 2D's brighter pixels, also gave a
  less saturated teal (0.47) than the 2D's. `strip.png` measures AgX 0.65 with the environment's saturation 1.35
  closest to the 2D for both heads; it is a look change for the engineer (`look_presets.json` is untouched).
- **Round 2 (static_v2, 2026-10-22; output `<raw>/.../pilot3d/static_v2/<head>/`, `static/` kept as it was).** The
  engineer's close-ups showed grey spiky streaks and a bright jagged line along the axolotl's lip edge and sharp
  streaks and a notch at the chameleon's lid rim. The `debug_mode` views (`docs/godot.md`) put the streaks in the
  geometry: the plain decimation left long sliver triangles along the lips and rims, whose smooth vertex normals
  fan out (the normal map hides them only partly, and a viewer without the bake's tangents not at all). Fixes at the
  source: the decimation keeps more of the budget on the lips and the lid rims (a "keep" vertex group, weight
  `1 - 0.9 * keep`; Blender's collapse adds `length * (2 - w1 - w2) * factor` to an edge's cost and a weight of 0
  all but freezes it, so the factor is searched per head for about 2.4 times the plain decimation's vertex share
  there, `build.json` `keep_search`); the bakes' cage and ray shorter (0.008 / 0.03: #288's reached across the lip
  slit); kept denser, the dense original's own jagged lip-skin crease showed more, so the lips (only) are relaxed
  locally (a weighted Smooth, 0.6 x 5) and their normal-map detail flattened; relaxing the lid rims too made the
  chameleon's lids read heavier in the whole-head gate, so the rims keep only the density and a rougher mask;
  zero-area triangles dissolved; the GLBs carry their tangents (`export_tangents`, so a glTF viewer shades
  with the bake's MikkTSpace frame; `alien_static_run.py` `fix_tangents` repairs the few zero tangents a no-area UV
  triangle gets); the lid rims rougher in the mask. New map: `<head>_detail.png` (cavity and inside occlusion baked
  from the dense original, the flush region, the limbal ring). The albedo is downsampled in linear light; the sclera
  cleaned further toward white. Review: `$PYTHON_BIN tools/blender/alien_static_review.py <seams|grid|gate>` and,
  in round 2 only, `ladder` (the cumulative levers A..F with GPU ms; round 3 replaced it with `final`): seams before
  and after under the full material and the three debug views, the "alive" levers' variant grid, the whole-head gate
  against #288.
- **Round 3 (static_v3, 2026-10-22; output `<raw>/.../pilot3d/static_v3/<name>/`, `static/` and `static_v2/` kept).**
  The manager's verdict on round 2: an orange-peel grain over both heads, the axolotl's upper-lip spike, the
  chameleon's lids heavier and lower than #288's, and a material that barely moved (still vinyl), judged in a browser
  as well as in Godot. Fixes:
  - **Orange peel:** the normal map and the cavity and thinness bakes come from a smoothed copy of the dense original
    (`DENSE_SMOOTH`, a Laplacian relax 0.5 x 24): the short rays of round 2 picked up its millimetre noise. The
    decimation still takes the original's shape. The shader's micro grain stays off.
  - **Lip spike:** a convex vertex near the lips or lid rims that is a local outlier, standing out of its
    neighbours' plane by more than `DESPIKE[0]` (0.08) of its mean edge length and more than `DESPIKE[1]` (3) times
    its neighbours' own median (so a smoothly rounded lip, whose neighbours stand out alike, is never touched), moves
    to its neighbours' mean (concave points, the lip slit, are never touched; `build.json` `despiked`), and the lips'
    normal detail is fully flat (0.8 in round 2).
  - **Chameleon lids:** `RIMS` per head; the chameleon's default decimates the lid rims plainly (#288's lids), and
    `--rims on` builds the named alternative `chameleon_heavylid` (the denser rims keep the dense original's heavier
    lids). `alien_static_compare.py lids` renders the dense original beside #288, round 2 and both builds in grey.
  - **Alive in the textures** (`alive`, strength `--alive`, so it shows in a browser's glTF viewer as well): the
    axolotl's teal crown and cheeks from the 2D, a gentle hue and value drift over big areas, a coloured cavity in
    the creases (deeper, more saturated, a little bluer; never grey), a warmer, more saturated flush on the lips,
    lids, nostrils and the thin parts' roots (gills, crest); the roughness gets the same drift and rougher creases
    on a satin skin (0.5). `<name>_albedo_plain.png` (without the layers) feeds Godot's `alive_mix` grid only.
  - **glTF extensions** on the exported material: `KHR_materials_clearcoat` on the eyes (`<name>_coat.png`, R),
    `KHR_materials_sheen` on the skin, `KHR_materials_specular` lowered (`SPEC_LEVEL`, `SHEEN`). Godot's importer
    ignores the three; the head's ShaderMaterial does the same in Godot.

  Review: `alien_static_review.py <seams|grid|final|gate>` (seams with #288, round 2 and round 3 rows; the
  levers' decisive grid; the before/after under AgX 0.65 + saturation 1.35 and the showroom's AgX 0.9; the gate),
  `alien_static_compare.py <lids|web>` (the browser-like render: Blender's glTF import, Cycles, the studio HDRI only,
  the Standard view transform).
- **Round 4 (static_v4, 2026-10-22; output `<raw>/.../pilot3d/static_v4/<head>/`, the earlier folders kept).** The
  manager's verdict on round 3: the orange peel, the axolotl's teal crown and the cleaner lips stay; the chameleon
  read a dark ring round both eyes (bruises or bags, heavier lids than #288's), the axolotl dirty greenish blotches
  (forehead, back, shoulder, a band at the lip corner), and a small bump stayed on the upper lip's border. Fixes:
  - **Chameleon eyes:** `LID_FLUSH` and `RIM_ROUGH` per head (the chameleon 0: no lid flush, no rougher rim band),
    and no crease colour within `EYE_CLEAR` (1.9 to 2.4 eye radii) of its eyes. `chameleon_heavylid` is dropped:
    its lid geometry was the default's, the heavier read was shading. **The main cause was the colour bake:** with
    round 2's short cage and ray (0.008 / 0.03) Meshy's painted iris landed higher on the eyeball, so the upper lid
    cut the iris; `COLOUR_CAGE` per head gives the chameleon's colour bakes #288's 0.015 / 0.05 back (the seams
    sheet's albedo column shows it; the normal, cavity and thinness bakes keep the short ones; `--colour-cage`).
  - **No dirty colour:** the large-scale hue and value drift is gone (from the roughness as well). The crease is
    narrow only: the cavity below its own skin neighbourhood's mean (a normalised box blur, `CREASE_K`), from the
    90th to the 99.5th percentile, so eye sockets and wide hollows never count. Every colour the layers add is the
    skin's own teal: the flush moves toward it, the crease toward a darker teal of the same hue; no hue shift and
    no saturation boost (a saturated pale skin read green-grey).
  - **Lip border:** within the lips' region and `LIP_GAP` above the slit, a low vertex standing out of the
    smoothed dense original moves inward onto it (`lip_snap`; outward parts only, so the border's crease keeps its
    depth), then onto a copy of the low mesh relaxed in that band (`LIP_RELAX`), since the bump is in the smoothed
    original too (`build.json` `lip_snap`).

  Review as round 3; the seams sheet's middle row is round 3 (under its pick), `lids` shows round 3 beside this one.
- **Round 5 (static_v5, 2026-10-22; output `<raw>/.../pilot3d/static_v5/<head>/`, the earlier folders kept).** The
  review's major: since round 3 the shader has no `sss_mode_skin`, so its defaults are not the #288 material, and
  every "#288" cell of rounds 3 and 4 showed the old heads under the changed shader. The merged #288 shader is kept
  byte for byte as `godot/alien/alien_static_288.gdshader` (from `7c2bac4`); `alien_static_review.py` gives it to
  every #288 cell in the full material (`head_entry(..., "288")`), with #288's own defaults, so every before/after and
  gate is against #288's true look. Fixes:
  - **Chameleon eye fringe:** with the long colour ray, texels on the eyeball just under the upper lid took the lid's
    teal (round 4's gate, side view). `EYE_FRINGE` per head: a teal texel inside the eye sphere that lies on the
    eyeball (its distance to the eye's centre within 0.03 eye radii of its clean eye neighbours' own) and near them
    in the texture takes the eye's own colour from its nearest clean eye texels, so the eye keeps its white and iris
    up to the lid line (`build.json` `eye_fringe`; the new `eyes` sheet: the eye from the side, its albedo, at 3/4).
  - **Pure formulas tested:** `smoothstep`, the sRGB conversions, `eye_dist`, `ellipsoid_w`, `keep_weights`, the
    alive layers' colour (`alive_colour`) and `fix_tangents` (now honouring `byteStride`) live in
    `tools/blender/alien_static_geom.py` (standard library only; `xp=numpy` in Blender), tested by
    `tools/tests/test_alien_static_geom.py` (with a GLB round trip, tight and interleaved).
  - **Loud failures:** a build on the current shader without its detail or plain texture stops the review (it was a
    silent white default).

  **Run them in the background.** `alien_static_run.py` (Blender up to 2400 s a head), `alien_static_review.py`
  (an off-screen Godot window up to 900 s) and `alien_static_compare.py` (Blender up to 3000 s) all pass the 180 s
  a workflow agent's call may block: start each with its log in a file (`> <log> 2>&1; echo "exit=$?" >> <log>`)
  and check it with `tools/run.sh wait <log>` (`CLAUDE.md`, "Shell").

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
- **Step 3c, no recesses** (`--fill --eye-scale 0.75 --lids upper --repaint --bare SHEET`): the texture's old socket
  rims and mouth hollow are painted over with the skin around them (a harmonic fill of the vertex colours on the
  seam-welded mesh, the dish's core held at the chin's pale mint, drawn back into the 4k atlas; the normal map
  flattened there; new PNGs in `--out`); the fill also lifts the sockets' undercut walls and relaxes the moved skin
  outward (a crease along the old rim showed otherwise); the eye is a ball in the skin with the upper lid only (a lower
  lid only for the blink, `alien_t1_geom.lid_parts`), the lids wearing the head's texture at their nearest skin
  point; `--bare` renders the filled head without pieces beside Meshy's, plain grey, and the labelled sheet.
- **Step 3d, a smooth muzzle** (step 3c's flags plus `--muzzle --tag 3d`): the head's built-in lips and the slit
  between them are gone. In the radial map from inside the head the muzzle region (`muzzle_region`: the dish's
  centre, 0.62 x its lip width, 1.05 x its lip height, its front only) is replaced by a thin plate through the skin around it
  (`thin_plate_fill`, a dense least-squared-Laplacian solve), the front vertices there, the slit's walls too, move
  along their rays onto it and are relaxed over it (the slit's folds spread out); the repaint covers the muzzle with
  the pale mint. The same mouth pieces are then seated on the smooth skin.

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
