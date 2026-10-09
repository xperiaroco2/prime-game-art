# Headless Blender: probe and review sheets

Blender 5.2.2 LTS (pinned in `tools/runner/pins.py`) runs only in the background, never with a window, through
`tools/runner/blender.py`:
`blender -b --factory-startup --python-exit-code 1 --python tools/blender/<script>.py -- <args>`, with a hard timeout.
A Python error inside the script fails the command and prints the end of Blender's output, traceback included.
Everything these commands write goes to `tools/out/` and is never committed.

## The heavy-run lock: one Blender or Godot process at a time

Several workflows may run at once on the shared PC, but their Blender and Godot processes take turns (the engineer,
2026-10-09: one Blender batch at a time). What is locked: every process `common.run` starts whose executable's name
begins with `blender` or `godot` (`blender.py`, `godot-check`, `frames`, `contract`, and lab scripts that import the
runner). It first takes an OS file lock, `<raw>/locks/heavy.lock`, shared by every checkout and worktree on the
machine; inside one runner process a thread lock first serializes its threads, so `anim-review --jobs` and
`anim-set` run their Blenders one after another. The OS releases the file lock when its holder exits or dies, so a
killed run or a power cut leaves no stale lock; but a killed runner can leave its Blender or Godot child running as
an orphan, which the lock no longer counts (look for leftover processes after a stopped run).

- A waiting run prints `heavy-run lock: waiting for <holder>` to stderr once (the holder is in `heavy.lock.holder`) and
  fails after 2 hours (`ART_HEAVY_LOCK_WAIT`, seconds). The process timeout counts from the process's start.
- `verify` and `selftest` hold the lock for their whole run: their Blender tests do not take it again
  (`ART_HEAVY_LOCK_HELD` in the children's environment), and the wait for it is outside their timeouts. A long bake
  elsewhere delays a `verify`; a `verify` delays the bakes queued behind it.
- `doctor`'s version probes never wait for it. Not locked: `frames --video`'s ffmpeg and the game repo's own tools.
- `ART_HEAVY_LOCK=off` turns it off; `ART_HEAVY_LOCK=<path>` moves it; with no raw folder (the laptop's raw-free lane)
  there is no lock.

## Commands

| Command | What it does |
|---|---|
| `probe [--out DIR] [--no-fixtures]` | Writes `tools/out/probe/report.json`, `workbench.png` and `eevee.png`, then builds the fixtures |
| `render <model> [--out DIR] [--cell 512] [--no-outline]` | Renders an 8-view review sheet and `stats.json` into `tools/out/renders/<stem>_<extension>/` |
| `render <model> --anim <action> [--frames 8]` | Also an animation contact sheet of that action, seen from the front |
| `render <model> --pose <action>` | The eight views posed at that action's first frame (to compare two models in the same pose); `stats.json` records `pose` |

Windows: `tools\run.cmd probe`, `tools\run.cmd render tools/out/fixtures/humanoid.glb`. Git Bash: `tools/run.sh ...`.

Other commands drive Blender through their own scripts and pages:
- `assemble` (the `tools/blender/um/` package): `docs/assembly.md`;
- `catalogue`: `docs/catalogue.md`;
- `faces`: `docs/faces.md`;
- `retarget` and `anim-review`: `docs/animations.md`;
- `export`: `docs/godot.md`.
- `kit` (`tools/blender/kit_build.py` with the pure-Python geometry `kit_geom.py`, one GLB per piece): `docs/kit.md`.

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
