# Headless Blender: probe and review sheets

Blender 5.2.2 LTS (pinned in `tools/runner/pins.py`) runs only in the background, never with a window, through
`tools/runner/blender.py`:
`blender -b --factory-startup --python-exit-code 1 --python tools/blender/<script>.py -- <args>`, with a hard timeout.
A Python error inside the script fails the command and prints the end of Blender's output, traceback included.
`probe` and `render` write to `tools/out/`; `mannequin` and `stylize-quaternius` write to the raw folder
(`D:/prime-art-raw/mannequin/` and `stylized/`) by default. None of it is ever committed.

## Commands

| Command | What it does |
|---|---|
| `probe [--out DIR] [--no-fixtures]` | Writes `tools/out/probe/report.json`, `workbench.png` and `eevee.png`, then builds the fixtures |
| `render <model> [--out DIR] [--cell 512] [--no-outline]` | Renders an 8-view review sheet and `stats.json` into `tools/out/renders/<stem>_<extension>/` |
| `render <model> --anim <action> [--frames 8]` | Also an animation contact sheet of that action, seen from the front |
| `mannequin [--preset base\|lanky\|bighead\|all] [--out DIR] [--size 1024] [--cell 512] [--no-refs] [--no-sheet]` | Builds our own low-poly base body by script: a GLB, a `.blend`, reference images and the review sheet per preset ([below](#the-mannequin)) |
| `stylize-quaternius [--source GLTF] [--preset base\|lanky\|bighead\|all] [--out DIR] [--triangles 7500] [--cell 512] [--no-sheet] [--no-check]` | Stylizes the CC0 Quaternius male toward our direction: a GLB, `info.json`, the review sheet and a `check` report per preset ([below](#the-stylized-quaternius-body)) |

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
  nose and small ears, and **no eyes or mouth**: they are changeable slots (`eyes`, `mouth`).
- Slightly lanky adult proportions, scaled last so the top of the head is at exactly 1.75 m; the eyes' height
  (`eye_height` in `info.json`) lands near 1.6 m.
- A T-pose: the arms horizontal at shoulder height, the palms down, the thumbs pointing forward.
- Five separate fingers per hand, each a three-segment loft (four rings, so a rig can bend it later), slightly spread.
- Bare feet, the soles at z = 0, with five simple toes (the big toe on the inside).
- Three objects: `Body` (skin), `Shirt` (a plain t-shirt with short sleeves) and `Shorts`, each with one flat
  material. The clothing is a separate closed shell over the body, so it can be swapped.
- About 3,000 triangles and no armature: a blockout and a reference, not yet a rigged body.

| Preset | What it changes |
|---|---|
| `base` | Near-human and slightly lanky: long limbs, narrow shoulders, a head a little big for the body |
| `lanky` | Thinner limbs (84 percent) and torso (90 percent), a 30 percent longer neck, longer legs and arms, a slightly longer nose |
| `bighead` | A 20 percent bigger head and a longer nose on the base body; the body gets shorter so the figure stays 1.75 m, which puts the eyes near 1.58 m |

Per preset, `<out>/<preset>/` (default `D:/prime-art-raw/mannequin/<preset>/`) holds:

| File | What |
|---|---|
| `mannequin_<preset>.glb`, `.blend` | The model; the `.blend` opens in Blender for a hand edit |
| `refs/front.png`, `side.png`, `back.png` | Reference images for Meshy: orthographic, `--size` pixels square (1024), a pure white background, the same scale and centre in every view, the body filling the frame (a 3 percent margin), Workbench's soft default studio light without shadows, specular, cavity, outline or text. `side` shows the model's left |
| `refs_flat/...` | The same three views unlit: flat colour only |
| `sheet/sheet.png`, `sheet/stats.json` | The 8-view review sheet through `render` |
| `info.json` | Height, lowest point, eye height, triangles, vertices and shells per object, and per reference view its corner colours and the box of non-white pixels (so a test can prove the background is white and the frame is filled) |

The reference images come from `tools/blender/refs.py`, which any Blender script can use.

## The stylized Quaternius body

`stylize-quaternius` (`tools/blender/stylize_quaternius.py`) takes the CC0 Quaternius male of the Universal Base
Characters (`D:/prime-art-raw/quaternius/Universal_Base_Characters/Universal Base Characters[Standard]/Base
Characters/Godot - UE/Superhero_Male_FullBody.gltf`: 12,566 triangles in the body, 1.82 m, 65 bones) toward our
direction. The runner writes a plan (`plan.json`, from `tools/runner/commands/_stylize.py`) that names every bone in
the rig's own names through `contract/bone_maps/quaternius.toml`, so the Blender script holds no vendor names. In
order:

1. Import with the vertices merged at UV seams and no bone display shape; delete `Icosphere`, `Eyes` and `Eyebrows`,
   remembering where the eyes were.
2. Reshape as an armature would: every slimmed bone scales its vertices across the bone (its length and the joints
   stay); the head bone scales its vertices uniformly about the neck joint. The weights blend both, so the neck and
   the joints stay smooth.
3. A blank face: the eye sockets, the lips and the inside of the mouth are smoothed flat (plain Laplacian smoothing,
   which fills dents).
4. A longer nose: the nose tip (the front-most centre-line vertex under the eyes) and its surroundings are pulled
   forward and a little down with a smooth falloff.
5. Softer muscles: Taubin smoothing, which does not shrink the mesh, on the torso, shoulders, arms, legs and neck by
   weight; the hands, feet and head keep their detail.
6. Mesh and bones scaled to 1.75 m; the head bone grows with the head.
7. One flat skin material and flat shorts. The texture's dark-grey faces give the shorts' waist and hem heights; the
   mesh is cut along those two horizontal planes and every face between them becomes the shorts, so the edges are
   straight instead of following the texture's ragged triangles. Textures, vertex colours and the old materials go.
8. Collapse decimation, symmetric in X, to `--triangles` (7,500: within the issue's 7,000 to 9,000 and under the
   contract's body cap of 8,000). The shorts' border is a protected vertex group (inverted on the modifier, so
   collapsing its edges costs more) and stays straight. Then the weights are cleaned to the contract: at most four
   per vertex, none under 0.01, normalized.
9. Export as GLB, re-import it and probe the rig: each finger chain's proximal bone, the head, a forearm and a shin
   are turned and the vertices that move are counted. A probe bone that moves nothing fails the command.

| Preset | Torso, arms, legs | Shoulders, neck | Head | Nose | Smoothing |
|---|---|---|---|---|---|
| `base` | 83, 83, 84 percent | 85, 90 percent | 112 percent | 3.0 cm longer | 30 iterations |
| `lanky` | 80 percent | 82, 85 percent | 110 percent | 3.6 cm longer | 34 iterations |
| `bighead` | 85 percent | 87, 90 percent | 115 percent | 4.5 cm longer | 30 iterations |

The three stay inside the issue's ranges (15 to 20 percent slimmer, a 10 to 15 percent bigger head), so they differ
only a little; a test holds them there.

Per preset, `<out>/<preset>/` (default `D:/prime-art-raw/stylized/<preset>/`) holds `quaternius_<preset>.glb`,
`plan.json`, `info.json` (what was dropped, the eye and nose positions, the triangles before and after, the shorts
band, the protected border vertices before and after decimation, the cleaned weights, the bones, the materials and the
probe), `sheet/` (the review sheet) and `check/report.json` (`check --kind body --map quaternius`). The check fails
only on `missing_bones` (the rig has no `Jaw`, `LeftEye` or `RightEye`; they are added in Blender later) and warns
about the triangles (above the body target of 6,000), the two materials, the dropped end bones and the eye height;
the command prints the check's exit code and still exits 0 for that known case, but fails on any other failed check
(or on `missing_bones` naming another bone).

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
- The glTF importer adds a hidden icosphere as the bone display shape unless `disable_bone_shape` is set; `render`
  sets it, so object counts are the model's own.
- The FBX and OBJ importers are available (`import_scene.fbx`, `wm.obj_import`). An FBX round trip adds leaf bones
  (17 become 22) unless the exporter's `add_leaf_bones` is off.

The full lists are in `tools/out/probe/report.json` after `probe`.
