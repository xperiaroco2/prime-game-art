# Headless Blender: probe and review sheets

Blender 5.2.2 LTS (pinned in `tools/runner/pins.py`) runs only in the background, never with a window, through
`tools/runner/blender.py`:
`blender -b --factory-startup --python-exit-code 1 --python tools/blender/<script>.py -- <args>`, with a hard timeout.
A Python error inside the script fails the command and prints the end of Blender's output, traceback included.
`probe` and `render` write to `tools/out/`; `mannequin` and `stylize-quaternius` write to the raw folder
(`D:/prime-art-raw/mannequin/` and `restyled/`; batch 2's `stylized/` came from the old stylize step) by default. None
of it is ever committed.

## Commands

| Command | What it does |
|---|---|
| `probe [--out DIR] [--no-fixtures]` | Writes `tools/out/probe/report.json`, `workbench.png` and `eevee.png`, then builds the fixtures |
| `render <model> [--out DIR] [--cell 512] [--no-outline]` | Renders an 8-view review sheet and `stats.json` into `tools/out/renders/<stem>_<extension>/` |
| `render <model> --anim <action> [--frames 8]` | Also an animation contact sheet of that action, seen from the front |
| `mannequin [--preset base\|lanky\|bighead\|all] [--out DIR] [--size 1024] [--cell 512] [--no-refs] [--no-sheet]` | Builds our own low-poly base body by script: a GLB, a `.blend`, reference images and the review sheet per preset ([below](#the-mannequin)) |
| `stylize-quaternius [--source GLTF] [--preset base\|lanky\|bighead\|all] [--out DIR] [--triangles 6000] [--cell 512] [--no-gates]` | Restyles the CC0 Quaternius male into our base body: a GLB and a working `.blend` with the profile's bones, the gates (sheet, `check`, close-ups, poses, the 20 m line-up, the defect check) and `info.json` per preset ([below](#the-restyled-base-body)) |

Windows: `tools\run.cmd probe`, `tools\run.cmd render tools/out/fixtures/humanoid.glb`. Git Bash: `tools/run.sh ...`.
`render` reads GLB, glTF, FBX, OBJ and `.blend` (cameras and lights in a `.blend` are dropped; hidden objects are
ignored). A relative model path is tried from the current folder, then from the repository root. The default
output folder carries the extension (`humanoid_glb/`, `humanoid_fbx/`), so two formats of one model never overwrite
each other's sheets.

## The review sheet

`sheet.png` is 4 x 2 square cells of `--cell` pixels (2048 x 1024 at the default 512), made for reading on a phone:

| | | | |
|---|---|---|---|
| 0 FRONT | 45 | 90 LEFT | 135 |
| 180 BACK | 225 | 270 RIGHT | 315 |

- Orthographic Workbench renders (studio light, cavity, a thin dark outline) on a neutral light-grey background. The
  outline is only a review aid that separates overlapping parts; the game's look has none by default
  (`docs/pipeline.md`), so `--no-outline` renders without it to compare.
- The front comes first. The model's front is +Z in glTF, which is -Y in Blender; the camera then turns
  counter-clockwise seen from above, so 90 shows the model's own left side and 270 its right.
- Every cell has the same scale and centre: the scale fits the model's height or its widest horizontal extent (the
  bounding box diagonal), whichever is larger, with an 8 percent margin, below a label band at the top of the cell.
  A model that looks small in one view is small, not zoomed out.
- A faint grey line marks z = 0, the floor; feet should stand on it.
- Colours: when any visible material has an image texture with pixels, Workbench uses texture colours (Meshy GLBs);
  otherwise material colours. Before rendering, each material's plain Principled base colour is copied into its
  viewport colour, which is what Workbench reads (the FBX and OBJ importers leave it grey).
- A caption in small type at the top right, in the label band of the 135 cell, names the model file and gives its
  triangles, height and colour mode, so a sheet forwarded to a phone says what it shows. Labels and caption are drawn
  with a 5 x 7 bitmap font in upper case; at small cells a label shrinks to its angle and text that does not fit is
  cut with `..` (at `--cell 64` the caption has no room).
- The single views are kept in `views/` (`0_000_front.png` ... `7_315.png`).

`stats.json` holds: `triangles` and `vertices` (of the deformed meshes), `objects` (visible ones), `meshes`,
`materials`, `textured_materials`, `armatures`, `bones`, `actions`, `bounding_box` (`min`, `max`, `size` in metres,
world space), `height`, `feet_at_zero` (the lowest point within 1 cm of z = 0), `color_type` (`TEXTURE` or `MATERIAL`),
`cell`, `views`, `outline`, `sheet` and, with `--anim`, `anim` (the action, its frame range, the sampled frames, the
sheet path).

### Animation contact sheet

`--anim <action>` plays that action on every armature (other NLA tracks muted) and renders `--frames` evenly spaced
whole frames from the first to the last key (fewer when the clip is shorter), each labelled with its frame number, front
view, into `anim_<action>.png` (4 columns, as many rows as needed; the frames go into `anim_<action>/`). File and folder
names use the action name made file-safe: every run of characters other than letters, digits, `.`, `_` and `-` becomes
`_`, so Mixamo's `Armature|mixamo.com|Layer0` gives `anim_Armature_mixamo.com_Layer0.png`; `stats.json` and the error
messages keep the real name. One scale fits the model over all sampled frames. The first and last frames of a looping
clip show the same pose. An unknown action fails with the list of actions the model has.

## The mannequin

`mannequin` (`tools/blender/mannequin.py`) is our own base body, built from nothing but script. It is one of two
zero-credit routes to the base body compared with Meshy's image route (art #5, art #11), and its renders are the
reference images sent to Meshy for image-to-image and multi-image-to-3D. Every shape is a loft of elliptical rings,
closed at both ends by triangle fans (no n-gons), with a simple UV strip per shell; nothing is traced or copied from
any model or screenshot.

- An egg-shaped bald head (a round crown, widest a little above the middle, narrower at the jaw) with a long simple
  nose and small ears, and **no eyes or mouth**: they are changeable slots (`eyes`, `mouth`). The nose starts as a
  tall narrow bridge, points mostly forward and tapers: pointing down with a round tip, its shaded underside read as a
  small open mouth in the front reference.
- Slightly lanky adult proportions, scaled last so the top of the head is at exactly 1.75 m; the eyes' height
  (`eye_height` in `info.json`) lands near 1.6 m.
- A T-pose: the arms horizontal at shoulder height, the palms down, the thumbs pointing forward (`pose` in
  `info.json`, measured on the mesh; a test holds it).
- The forearms and shins taper and end inside the palm or the foot, so the wrists and ankles show no cuff or ring that
  image-to-3D could copy as a band.
- Five separate fingers per hand, each a three-segment loft (so a rig can bend it later) with a rounded tip, slightly
  spread.
- Bare feet, the soles at z = 0, with five simple toes (the big toe on the inside).
- Three objects: `Body` (skin), `Shirt` (a plain t-shirt with short sleeves) and `Shorts`, each with one flat
  material. The clothing is a separate closed shell over the body, so it can be swapped.
- About 3,400 triangles and no armature: a blockout and a reference, not yet a rigged body.

| Preset | What it changes |
|---|---|
| `base` | Near-human and slightly lanky: long limbs, narrow shoulders, a head a little big for the body |
| `lanky` | Thinner limbs (84 percent) and torso (90 percent), a 30 percent longer neck, longer legs and arms, a slightly longer nose |
| `bighead` | A 20 percent bigger head and a longer nose on the base body; the body gets shorter so the figure stays 1.75 m, which puts the eyes near 1.58 m |

Per preset, `<out>/<preset>/` (default `D:/prime-art-raw/mannequin/<preset>/`) holds:

| File | What |
|---|---|
| `mannequin_<preset>.glb`, `.blend` | The model; the `.blend` opens in Blender for a hand edit (a re-run overwrites it and keeps no `.blend1`) |
| `refs/front.png`, `side.png`, `back.png` | Reference images for Meshy: orthographic, `--size` pixels square (1024), a pure white background, the same scale and centre in every view, the body filling the frame (a 3 percent margin), Workbench's soft default studio light without shadows, specular, cavity, outline or text. `side` shows the model's left |
| `refs_flat/...` | The same three views unlit: flat colour only |
| `sheet/sheet.png`, `sheet/stats.json` | The 8-view review sheet through `render` |
| `info.json` | Height, lowest point, eye height, the measured pose, triangles, vertices and shells per object, and per reference view its corner colours and the box of non-white pixels (so a test can prove the background is white and the frame is filled) |

The reference images come from `tools/blender/refs.py`, which any Blender script can use.

## The restyled base body

`stylize-quaternius` (`tools/blender/stylize_quaternius.py`, art #14) restyles the CC0 Quaternius male of the Universal
Base Characters (`D:/prime-art-raw/quaternius/Universal_Base_Characters/Universal Base Characters[Standard]/Base
Characters/Godot - UE/Superhero_Male_FullBody.gltf`: 12,566 triangles, 1.82 m, 65 bones with five-finger chains) into
our base body. The batch 2 review (art #5) chose the route: the Quaternius body is the rig, weight and topology donor,
and mannequin-lanky ([above](#the-mannequin)) is the look target. The build starts from the source glTF rather than
batch 2's `quaternius_base.glb` (the same rig, weights and topology, but already decimated: decimating twice loses the
finger and joint loops). The runner writes a plan (`build/plan.json`, from `tools/runner/commands/_stylize.py`) that
names every bone in the rig's own names through `contract/bone_maps/quaternius.toml`, so the Blender script holds no
vendor names. In order:

1. Import with the vertices merged at UV seams and no bone display shape; delete the eyes, the eyebrows and any mesh
   not skinned to the armature, remembering where the eyes were. The body mesh is renamed `Body` (the source calls it
   `SuperHero_Male`).
2. A soft body. The trunk (hips to neck) and every upper arm, forearm, thigh, shin and the neck get a smooth surface
   around their axis, fitted by least squares to their own vertices (harmonics up to the second around the axis,
   quadratic along the trunk, a straight taper along a limb), and every vertex moves towards it by its weight:
   the pecs, abs, shoulder blades, V-taper, biceps and calves go. Vertices only move towards or away from the axis,
   and the blend fades out at the joints, so the shoulder, elbow, hip and knee loops and the finger roots keep their
   places. Then normal-only Taubin smoothing on the trunk (vertices move along their normals, so no loop slides), and
   plain Laplacian smoothing flattens the source's bulge at the groin.
3. The head. Everything above a cut that rises from the chin at the front to the skull's base at the back moves onto
   an egg (radial projection): the mannequin's head profile (a round crown, the widest part a little above the middle,
   narrower at the jaw), fitted to the source's temples and brow, its lower end leaning a little forward. That flattens
   the lips, the mouth, the nasolabial folds, the brow ridge and the cheek planes: a blank face. The surface is then
   relaxed on the egg (smooth, project back, 25 times) to spread the eyelids' and lips' dense rings; the mouth (the
   lips and the pocket of skin inside them, which fold up on the egg) is laid flat inside its own rim (Tutte's
   embedding: inside a convex rim no triangle folds). The ears ride on the egg, are rounded off and pulled in; between
   the egg and the neck a membrane (positions filled in harmonically) replaces the jaw line. A cone nose is pulled out
   of the face: the vertices inside an ellipse around the root (just under the eyes) become a cone pointing forward
   and a little down, a tall narrow root tapering to a round tip. The egg, ears and nose are weighted to the head bone
   alone (the source's mouth leaned on the neck and came back as a dent once the bones changed), and the membrane's
   weights are filled in harmonically down to the neck's.
4. The proportions, in pose mode: every trunk and limb bone is scaled across its length (slimmer), and the upper arms,
   forearms, thighs, shins and neck along it (longer); the shoulders get narrower. No bone inherits its parent's scale
   meanwhile, so a child moves to its parent's new end without stretching: the hands and feet are never stretched. The
   neck is turned upright (the source's leans forward 17 degrees) and the head turned back, so it sits over the neck.
   The head's scale is solved (a few evaluations of the posed skin) so that in the finished figure the skin the head
   bone moves at least half is the preset's size against the source's at the same height. The posed skin is applied
   and the pose becomes the rest (`pose.armature_apply`).
5. Normalized: the mesh and every bone scaled to 1.75 m, the soles at z = 0 and centred on the origin. The normalized
   skin is saved (`build/normalized.npy`); every preset has the source's topology up to here, so a preset other than
   base is measured against base vertex by vertex.
6. `Jaw`, `LeftEye` and `RightEye` are added under the head bone, unweighted, pointing forward: the eyes at the
   source's eye centres (moved with the head), the jaw in front of and above the head joint.
7. One palette material: the briefs are cut into the mesh along a waist plane 12.5 cm above the crotch and, per leg,
   a leg-opening plane 2.5 cm below it that rises 28 degrees towards the hip; every face gets UVs in the centre of its
   colour's cell of a 16 x 16 px palette image (4 x 4 cells, closest-pixel sampling, packed into the GLB). The material
   is matte (roughness 1, no metal, in the viewport too). The cells are placeholders until the shared game palette
   exists.
8. Collapse decimation, symmetric in X, to `--triangles` (6,000, the contract's body target). A protect group (inverted
   on the modifier, so collapsing its edges costs more) holds the finger roots, the shoulder, elbow, hip and knee loops
   and the briefs' border. The weights are cleaned to the contract: at most four per vertex, none under 0.01,
   normalized.
9. Saved as `build/stage_<preset>.blend` with the rig's own names. The runner then runs `rename-bones --map quaternius`
   on it twice: `restyled_<preset>.glb` and the working copy `restyled_<preset>.blend` (no `.blend1`), both with the
   profile's 56 bones.

The export check reads the GLB's own JSON (no Blender) and fails when any node with a mesh is not `Body`
(`_stylize.ALLOWED_MESHES`; the clothing pieces join it when the cut-piece tool exists). The batch 2 review's "stray
Icosphere" was Blender's importer, not the files: imported without `disable_bone_shape`, a glTF gets a hidden 42-vertex
icosphere as the bones' display shape. `contract_io.load_model` now sets it, so `rename-bones` never saves one into a
`.blend`.

| Preset | Across (trunk, arms, legs) | Along (upper arm, forearm, thigh, shin, neck) | Head against the source |
|---|---|---|---|
| `base` | 0.82 to 0.94, 0.8 and 0.76, 0.8 | 1.08, 1.1, 1.1, 1.12, 1.5 | 1.125 |
| `lanky` | 0.78 to 0.92, 0.7 and 0.68, 0.7 | 1.2, 1.22, 1.22, 1.24, 1.75 | 1.1 |
| `bighead` | as base | as base; the neck 1.3 | 1.25 |

The along factors are before the figure is scaled back to 1.75 m: lanky's limbs end about 4 percent longer for its
height than base's (its hands and feet about 7 percent smaller), its neck 9 percent; bighead's head is 11 percent
bigger than base's. The head is measured as the vertical extent of the skin the head bone
moves at least half, as a fraction of the height (the source's: 0.128).

### The gates

After the build, per preset (`tools/runner/commands/stylize_quaternius.py`), all into
`D:/prime-art-raw/restyled/<preset>/` (`--out`), none of it committed:

| File | What |
|---|---|
| `sheet/sheet.png` | The 8-view review sheet ([above](#the-review-sheet)) |
| `check/report.json` | `check --kind body` on the renamed GLB: it must pass (no failure; warnings allowed) |
| `closeups/head.png` | Front, left, three-quarter and back in colour; front and left in clay; front and left in wireframe |
| `closeups/hands.png` | Per hand: from above in colour and in wireframe, from the front and from below (the palm) in clay |
| `poses.png` | Fist, point, wave, thumbs up, knee bend, sit and arms down: each a full figure (three-quarter front) and a close look at the joint or hand it tests, in clay. The poses turn bones about world axes (`tools/blender/restyle_gates.py`), so they hold for any rig with the profile's names |
| `lineup.png`, `lineup_x4.png` | Front and side at 40 px per metre (a 1.75 m figure is 70 px, about what a 1080p screen shows at 20 m), no outline, next to mannequin-lanky and batch 2's quaternius-base; the copy is enlarged 4 times with labels. With `--preset all` the root also gets one line-up of every preset |
| `info.json` | The build's numbers, the measurements and the defect check below |

The verdict (`_stylize.gate_failures`, every rule tested without Blender) fails the command when the GLB holds
another mesh or a second material, the contract check fails, the height is not 1.75 m on the ground with the soles
centred, the eyes are outside 1.55 to 1.65 m, the head is more than 2 percent off its target, there are more than 10
percent over the triangle target, any open or non-manifold edge remains (welded at 0.01 mm), or a hand's fingers are
not five separate parts. The finger check counts the connected parts of the skin that the fingers' free segments move
most (each finger's middle and end, the thumb's last two; the web joins the first segments in a real hand too): five
parts, one finger each. The slices across each hand 1 to 12 cm from the fingertips are recorded too, but cannot gate:
on this hand the thumb starts behind the knuckles, so no slice crosses five fingers (the batch 2 review saw four on
quaternius-base as well).

A preset other than base must also differ from base: its vertices at least 10.5 mm (median) from base's, three times
batch 2's 3.5 mm, compared vertex by vertex before decimation (`shift_from_base`); lanky's neck, upper arm, forearm,
thigh and shin at least 3 percent longer for the height than base's; bighead's head at least 7 percent bigger.
(`measure.surface_from_base`, each vertex's distance from base's surface, is recorded for comparison: it misses limbs
that only grew longer, which slide along their own surface.)

A run of all three presets with every gate takes about 70 seconds on this PC; `--no-gates` builds only (about 8
seconds a preset). `selftest` runs the build on the box fixture and, when the source is in the raw folder, every preset
with every gate.

## The fixture

`tools/blender/make_fixture.py` builds a stand-in humanoid by script into `tools/out/fixtures/`: `humanoid.glb` and
`humanoid_textured.glb` (the shirt carries a packed checker image). It is 1.75 m tall from z = 0, faces -Y, stands in
an A-pose, has 17 bones (hips, spine, chest, neck, head and per side upper_arm, forearm, hand, thigh, shin, foot with
`.L`/`.R`), five materials, a red nose that marks the front, and one action, `Wave`, that raises the right arm over
24 frames. `probe` builds both; the tests build their own copies under `tools/out/tests/blender/`.

## What the probe found (2026-10-02, this PC)

- Blender 5.2.2 LTS, build d13f752e3b9c, Python 3.13.13; numpy 2.3.4 imports.
- If EEVEE fails on another PC, `probe` still exits 0: a Python error is recorded in `renders.eevee`, and so is a
  crash of Blender itself, because the report is written before the EEVEE render with EEVEE marked `attempted`.
- **EEVEE renders in background mode here.** The first EEVEE frame took about 17 s (shader compilation), later ones
  about 0.2 s. Workbench takes about 1 s. Cycles can be selected too.
- In background mode the `render.engine` enum lists only `BLENDER_EEVEE`, yet `BLENDER_WORKBENCH` and `CYCLES` can be
  set: the probe reports both the listed and the settable engines.
- The glTF exporter has 110 properties, the importer 20. `export_format` is a dynamic enum whose items RNA cannot list
  without an operator instance; the probe reads them from the operator class (`GLB`, `GLTF_SEPARATE`; default `GLB`).
  Defaults worth knowing: `export_yup` true, `export_apply` false (modifiers are not applied), `export_animations`
  true, `export_animation_mode` `ACTIONS`, `export_image_format` `AUTO`, `export_skins` true.
- The glTF importer adds a hidden icosphere as the bone display shape unless `disable_bone_shape` is set; `render`,
  `stylize-quaternius` and every contract script (`contract_io.load_model`) set it, so object counts are the model's
  own and no `.blend` saved from an import carries it.
- The FBX and OBJ importers are available (`import_scene.fbx`, `wm.obj_import`). An FBX round trip adds leaf bones
  (17 become 22) unless the exporter's `add_leaf_bones` is off.

The full lists are in `tools/out/probe/report.json` after `probe`.
