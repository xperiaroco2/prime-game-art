# Headless Blender: probe and review sheets

Blender 5.2.2 LTS (pinned in `tools/runner/pins.py`) runs only in the background, never with a window, through
`tools/runner/blender.py`:
`blender -b --factory-startup --python-exit-code 1 --python tools/blender/<script>.py -- <args>`, with a hard timeout.
A Python error inside the script fails the command and prints the end of Blender's output, traceback included.
Everything these commands write goes to `tools/out/` and is never committed.

## Commands

| Command | What it does |
|---|---|
| `probe [--out DIR] [--no-fixtures]` | Writes `tools/out/probe/report.json`, `workbench.png` and `eevee.png`, then builds the fixtures |
| `render <model> [--out DIR] [--cell 512]` | Renders an 8-view review sheet and `stats.json` into `tools/out/renders/<model name>/` |
| `render <model> --anim <action> [--frames 8]` | Also an animation contact sheet of that action, seen from the front |

Windows: `tools\run.cmd probe`, `tools\run.cmd render tools/out/fixtures/humanoid.glb`. Git Bash: `tools/run.sh ...`.
`render` reads GLB, glTF, FBX, OBJ and `.blend` (cameras and lights in a `.blend` are dropped; hidden objects are
ignored). A relative model path is tried from the current folder, then from the repository root.

## The review sheet

`sheet.png` is 4 x 2 square cells of `--cell` pixels (2048 x 1024 at the default 512), made for reading on a phone:

| | | | |
|---|---|---|---|
| 0 FRONT | 45 | 90 LEFT | 135 |
| 180 BACK | 225 | 270 RIGHT | 315 |

- Orthographic Workbench renders (studio light, cavity, a thin dark outline) on a neutral light-grey background.
- The front comes first. The model's front is +Z in glTF, which is -Y in Blender; the camera then turns
  counter-clockwise seen from above, so 90 shows the model's own left side and 270 its right.
- Every cell has the same scale and centre: the scale fits the model's height or its widest horizontal extent (the
  bounding box diagonal), whichever is larger, with an 8 percent margin, below a label band at the top of the cell.
  A model that looks small in one view is small, not zoomed out.
- A faint grey line marks z = 0, the floor; feet should stand on it.
- Colours: when any visible material has an image texture with pixels, Workbench uses texture colours (Meshy GLBs);
  otherwise material colours. Before rendering, each material's plain Principled base colour is copied into its
  viewport colour, which is what Workbench reads (the FBX and OBJ importers leave it grey).
- The single views are kept in `views/` (`0_000_front.png` ... `7_315.png`).

`stats.json` holds: `triangles` and `vertices` (of the deformed meshes), `objects`, `meshes`, `materials`,
`textured_materials`, `armatures`, `bones`, `actions`, `bounding_box` (`min`, `max`, `size` in metres, world space),
`height`, `feet_at_zero` (the lowest point within 1 cm of z = 0), `color_type` (`TEXTURE` or `MATERIAL`), `cell`,
`views`, `sheet` and, with `--anim`, `anim` (the action, its frame range, the sampled frames, the sheet path).

### Animation contact sheet

`--anim <action>` plays that action on every armature (other NLA tracks muted) and renders `--frames` evenly spaced
frames from the first to the last key, front view, into `anim_<action>.png` (4 columns, as many rows as needed; the
frames go into `anim_<action>/`). File and folder names use the action name made file-safe: every run of characters
other than letters, digits, `.`, `_` and `-` becomes `_`, so Mixamo's `Armature|mixamo.com|Layer0` gives
`anim_Armature_mixamo.com_Layer0.png`; `stats.json` and the error messages keep the real name. One scale fits the model over all sampled frames. The first and last frames of a
looping clip show the same pose. An unknown action fails with the list of actions the model has.

## The fixture

`tools/blender/make_fixture.py` builds a stand-in humanoid by script into `tools/out/fixtures/`: `humanoid.glb` and
`humanoid_textured.glb` (the shirt carries a packed checker image). It is 1.75 m tall from z = 0, faces -Y, stands in
an A-pose, has 17 bones (hips, spine, chest, neck, head and per side upper_arm, forearm, hand, thigh, shin, foot with
`.L`/`.R`), five materials, a red nose that marks the front, and one action, `Wave`, that raises the right arm over
24 frames. `probe` builds both; the tests build their own copies under `tools/out/tests/blender/`.

## What the probe found (2026-10-02, this PC)

- Blender 5.2.2 LTS, build d13f752e3b9c, Python 3.13.13; numpy 2.3.4 imports.
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
