# glTF export and the Godot 4.7.2 import check

An assembled character (`tools/run.py assemble <recipe> --blend`, `docs/assembly.md`) reaches Godot the way the game
needs it: every part a separate skinned mesh on one Skeleton3D, the pack's 24 animations playing. Art #18 built three
commands for that; together they are the export step of `docs/pipeline.md` (step 10) plus a check in the game's engine.

```
tools/run.py export <character.blend> [...] [--out DIR]          GLB with fixed options; glTF-Validator report.json
tools/run.py godot-check <glb> [...] [--out DIR] [--strict-contract] [--humanoid]
                                                                  import headless in godot/; assertions; report.json
tools/run.py frames <glb> [--clips A,B] [--compare all|A,B|''] [--video A,B] [--blend FILE] [--out DIR]
                  [--face CLIP [--face-beside PNG --face-rects 'x,y,w,h;...']]
                                                                  Godot-rendered frame sheets (off-screen window)
tools/run.py showroom [<glb>] [--variants a,b] [--clip Idle] [--hdri HDR] [--beside PNG [--beside-rects ...]]
                  [--out DIR] | --write-presets            look variants, face and body sheets, GPU ms (off-screen)
```

A full run for one character: `assemble --modes none --blend` about 9 s, `export` about 8 s, `godot-check` about 3 s
(10 s for four), `frames` with all 24 sheets, the comparison of all 24 clips and six clips 90 to 110 s.
`godot-check` and `frames` share `godot/import/`: run one at a time (each removes the GLBs an earlier run left there).

## export

`tools/blender/export_glb.py` opens the saved character in background Blender, asserts it is one (one armature, every
mesh parented to it with one Armature modifier, no action assigned), resets every pose bone to the rest pose and runs
Blender's glTF exporter with `EXPORT_OPTIONS`, every option the output depends on passed explicitly so that a changed
Blender default cannot change the file. It writes `<out>/<id>/<id>.glb` and `<id>.export.json` (what Blender exported,
in glTF axes: bones with parents and rest heads, parts, actions with frame ranges, bounds, height, the options, the
Blender and exporter versions, and each action's **seam**: the largest joint distance and bone rotation between its
first and its last frame, which tells a closed cycle from an open one, see frames). The command then reads the GLB's JSON chunk and checks it against that description
(`_export.check`: one skin of every bone, one skinned mesh node per part, every action an animation of its own length
animating every bone, the armature the only root, no cameras, lights or images) and runs the pinned glTF-Validator
(`gltf_validator --stdout --all`; `--all` only prints every message to stderr, the JSON report holds them
either way) into `<out>/<id>/report.json`; a check problem or a validator error fails the
command, warnings are listed (grouped by code).

### The export options

| Option | Value | Why |
|---|---|---|
| `export_format` | `GLB` | One binary file: the contract's glTF 2.0, one LFS object per character |
| `use_active_scene` | on | The saved file holds one scene, the character's |
| `export_yup` | on | +Y up, front +Z (the contract's axes; Blender's +Z up, front -Y converted) |
| `export_apply` | off | The parts carry only their Armature modifier; applying it would bake the rest pose into the vertices and drop nothing useful |
| `export_skins`, `export_influence_nb` 4, `export_all_influences` off | | Skinning with 4 influences: the parts have at most 4 (measured), Godot's default too, so nothing is lost |
| `export_def_bones` | off: all 62 bones | Every pack bone is a deform bone anyway; keeping all bones keeps every action's tracks resolvable and leaves the bone set to the contract v2 (`Body`, `PT.L`, `PT.R` carry tracks) |
| `export_rest_position_armature`, `export_reset_pose_bones` | on | The skin's inverse bind matrices come from the rest pose (the T-pose); each action is sampled from the rest pose, so a channel one action does not key is at rest, not where the last action left it |
| `export_leaf_bone`, `export_hierarchy_flatten_bones`, `export_armature_object_remove` | off | The rig's own hierarchy, no added end bones; the armature stays a node (see the validator warning below) |
| `export_animations`, `export_animation_mode` `ACTIONS` | | Every action as its own glTF animation under its own name (`CharacterArmature|Wave`, ...; the saved file holds only the body type's 24) |
| `export_force_sampling`, `export_frame_step` 1, `export_sampling_interpolation_fallback` `LINEAR` | | Every frame sampled (24 fps), linear between samples: what the pack's actions are |
| `export_optimize_animation_size` | on | Drops only duplicate keys: the poses on the pack's frames are unchanged (checked: identical joint positions with it off; the file is 1.85 MB instead of 3.03 MB for m1_rex) |
| `export_frame_range`, `export_anim_slide_to_zero`, `export_bake_animation`, `export_current_frame` | off | Each action's own range (all start at 0); no baked object animation |
| `export_morph`, `export_cameras`, `export_lights` | off | The pack characters have no shape keys (the textured export keeps the face morphs, below); a character carries no camera or light |
| `export_materials` `EXPORT`, `export_image_format` `NONE`, `export_vertex_color` `NONE` | | Flat colours: one base colour per material, no textures, no vertex colours |
| `export_texcoords` on, `export_normals` on, `export_tangents` off | | The pack's UVs are kept for a later palette texture; no normal maps |
| Draco, meshopt, gltfpack, GPU instances, extras, attributes | off | Godot cannot read Draco or meshopt; nothing else is needed |

Measured (2026-10-03, Blender 5.2.2, exporter 5.2.40): m1_rex 1.85 MB, m2_walt 2.04 MB, w1_ivy 2.03 MB, w2_nova
2.04 MB (the contract then allowed 5 MB; raised to 40 MB by the character-budgets ADR); 62 joints, 24 animations of
186 channels (62 bones x translation, rotation, scale), 8 parts (9 for m2_walt with his moustache), 11 to 17
materials. glTF-Validator 2.0.0-dev.3.10: 0 errors;
one warning per part, `NODE_SKINNED_MESH_NON_ROOT` ("parent transforms will not affect a skinned mesh"): the parts are
children of the armature node, whose transform is the identity (the saved file applies every transform), so it changes
nothing; infos `UNUSED_OBJECT` for the UVs no texture uses.

## Textured export (`export --textured`, `godot-check --textured`)

The clay look's baked characters (`assemble --look clay --bake --blend`, `docs/assembly.md`, "The clay look") carry
textures, so their export and check differ from the flat-colour pack look's:

- `export --textured` puts `TEXTURED_OPTIONS` (`export_glb.py`) on top of the options above: `export_image_format`
  `AUTO` (the baked PNGs embedded as PNG), `export_tangents` on (the normal maps need them), `export_morph`,
  `export_morph_normal` and `export_morph_tangent` on with `export_try_sparse_sk` off (the face kit's shape keys, art
  #42 part B), `export_vertex_color` `MATERIAL`. A part whose one material takes its base colour straight from a
  colour attribute (the clay eyes' `fb_eye`: whites and pupils) gets those flat colours as a palette texture
  `<material>_palette` (16 px per colour, nearest filtering, a power-of-two side) on a new UV map in place of the
  attribute (`palette_part`): Godot 4.7.2's importer turns on "vertex colour as albedo" only after a mesh's first
  surface (docs/kit.md, "Paint"), so the one-surface eyes drew plain white (art #42); the palette needs no normal map.
  A part without any UV map (a glossy part that samples no texture)
  gets a spherical one, since Godot cannot make tangents for blend shapes without UVs; a TANGENT the exporter writes
  that is not a unit vector (a glTF-Validator error, seen on single vertices of the lab's cast) is replaced by a unit
  one perpendicular to the normal. The export check then allows images, and the command writes
  `<out>/<id>/<id>.textures.json` (`_export.textured_audit`: every image's mime, bytes and size, each material's base
  colour and normal textures, each surface's UVs and tangents) and fails on `_export.textured_check`: no base colour
  texture at all, an image that is not PNG or JPEG or is over the contract's `texture_character_px` (2048), a textured
  material without a normal map (a `_palette` image and a material only the `_eyes` part uses aside, as in
  godot-check's `normal_maps`; #210), a normal-mapped surface without UVs or tangents, more surfaces than the
  contract's `surfaces_per_character_cap` (8).
- `godot-check --textured` replaces `flat_colours` with `textured` (some surface has an albedo texture), `normal_maps`
  (every textured surface but the `_eyes` part's has a normal map), `eye_pupils` (the `_eyes` part as Godot draws it,
  `inspect.gd`'s albedo at each vertex from the colour, the vertex colours if used as albedo and the texture at the
  UV: at least 2 % near-white and 2 % near-black vertices, else the eyes have lost their pupils), `texture_size` (no
  albedo or normal texture side over `texture_character_px`) and `surfaces_cap` (the surfaces within
  `surfaces_per_character_cap`); `inspect.gd` reports each material's `albedo_px`, `normal_mapped` and `normal_px`.
  Every other check is the same.

Measured on 2026-10-09 (`recipes/clay_round_d.json`): m1 8 surfaces, 12 images 4.41 MB, GLB 6.12 MB; w1 7
surfaces, 10 images 3.46 MB, GLB 5.13 MB; every map at most 1024 px (the cap then); validator 0 errors; godot-check
passes with the contract warnings (heights 1.962 and 1.912 m with the x1.3 clay head) and the loop-mode warning.

## The Godot project: `godot/`

A minimal Godot 4.7.2 project at the repo root (`config/features` 4.7, Forward Plus like the game), separate from
`tools/godot/`, which stays the headless contract project with its one dump script. `godot/import/` (ignored) receives
the GLBs the commands import; `godot/.godot/` (ignored) is Godot's cache. Committed: `project.godot`,
`lib/character.gd` (shared helpers, loaded with `preload` because a `-s` script has no global class cache),
`check/inspect.gd`, `frames/frames.gd`, `check/kit.gd` (the headless import check of the kit's pieces) and
`kit/proof.gd` (the kit's test room, walks and shots in the off-screen window; `docs/kit.md`), and the `.gd.uid` files Godot 4.7 writes beside scripts (the game commits
them too).

Importing: `_godot.stage()` copies the GLB into `godot/import/` and writes a minimal `.import` file (`[remap]
importer="scene"` and our options only; Godot fills in every other option with its default and adds the uid), then
`godot --headless --path godot --import`. Two options are set:

- **`animation/fps = 24`**: Godot's editor import resamples a glTF animation at `animation/fps` (default 30), and the
  pack's actions are 24 fps. At 30 the joints on the pack's own frames were up to 7.6 mm from Blender's (m1_rex's Walk).
- **`optimizer/enabled = false` on the AnimationPlayer node** (`_subresources` `nodes` / `PATH:AnimationPlayer`,
  `_godot.PLAYER_OPTIONS`): the importer's animation optimizer (on by default) drops keys it finds linearly
  interpolable within its velocity and angle errors. With it, joints were up to 16.7 mm from Blender's (m1_rex's Run,
  the left hand at frame 17) and 4.5 mm in Walk; without it every joint and axis point of all 24 clips of m1_rex and
  w1_ivy is within 0.017 mm (the JSON's rounding). The optimizer is an option of the AnimationPlayer node, not of the
  animations (`_subresources` `animations` has no optimizer).

The game's import of these characters needs both settings, or accepts the error: input for the contract v2.
`godot-check` and `frames` first remove every GLB an earlier run left in `godot/import/` (`_godot.clear_staged`), so
`--import` imports only this run's files; Godot's import lines go to the GLB whose `res://import/<stem>.glb` they name,
and a line that names no staged file counts against every GLB of the run (`_godot.lines_for`).

## godot-check

`check/inspect.gd` (headless, `-s`) instantiates the imported scene, waits one frame (the meshes register their skins
when the tree runs) and describes it: every Skeleton3D (bones, parents, rest joints in world space), every
MeshInstance3D (its skeleton, Skin binds that do not resolve, surfaces, vertices, materials, its rest-pose bounds
and, per bone, the rest-pose bounds of the vertices whose heaviest bone is that bone: `bone_bounds`),
every AnimationPlayer (each animation's length, tracks by type, tracks that do not resolve, and how far the bones move
between the poses at 0, 1/3 and 2/3 of its length), and optionally every joint at requested times. The vertices are
skinned on the CPU exactly as Godot's renderer does it (bone global pose x the Skin's bind pose, weighted):
`MeshInstance3D.bake_mesh_from_current_skeleton_pose()` fails headless ("The source mesh must have a valid skin": the
dummy rendering server keeps no skeletons). The assertions are pure Python (`_godot.evaluate`), so the tests run them
without Godot:

| Check | Passes when |
|---|---|
| `one_skeleton` | exactly one Skeleton3D |
| `skeleton_bones`, `bone_hierarchy` | its bones are the rig's 62 (names and count) under their rig parents |
| `rest_joints` | its rest joints are within 1 mm of Blender's bone heads (measured: 0.01 mm) |
| `parts_separate` | one MeshInstance3D per part, named as the parts |
| `parts_skinned` | each has a Skin bound to that Skeleton3D and every bind names a bone |
| `one_animation_player`, `animations`, `animation_lengths` | one AnimationPlayer with every action, each as long as the action (1 ms) |
| `tracks_resolve` | every track's node and bone exist, and Godot printed no "couldn't resolve track" |
| `animations_move` | in every animation some bone turns 0.5 degrees or moves 2 mm between the three samples |
| `size_kept` | the rest-pose height equals Blender's within 2 mm |
| `feet_at_zero` | the lowest skinned vertex is within the contract's `feet_tolerance_m` (0.01 m) of y = 0 |
| `facing_plus_z` | the eyes are at least 5 cm in front of the Head joint, the shoes reach further forward than back from the ankles, the left wrist is at +X; a barefoot body without a `_shoes` part (the alien, art #196/#207) is measured by its feet instead: the `bone_bounds` of the Foot and Toe bones on every part but the eyes (the vertices whose heaviest bone is a Foot or Toe bone) |
| `flat_colours` | no surface has an albedo texture (with `--textured`: the textured checks instead, "Textured export" above) |
| `godot_output` | no ERROR line in Godot's import and inspection output (warnings are listed) |
| `contract_height`, `contract_eye_height` | the contract v1 body gates (height 1.70 to 1.80 m to the top, 1.90 m with `--textured`, the plasticine look; eyes 1.6 +- 0.08 m): **warnings** unless `--strict-contract` |
| `loop_modes` | **warning** while a cycle (`Idle*`, `Walk*`, `Run*`) imports with loop_mode NONE; names the open cycles |
| `loop_suffix` | an action named as a loop (`_Loop`, art #33) imports with loop_mode LINEAR under its name without the suffix (`Idle_Loop` becomes `Idle`); `animations` and `animation_lengths` compare Godot's names |
| `expectations`, `pack_floor` | only for a GLB without its `<stem>.export.json`: a **warning** that parts, bones and animations then come from the GLB itself (what it already lacks is not caught; no rest joints, hierarchy or Blender height; the clip names are taken as Godot gives them, a `_Loop` suffix dropped and checked by `loop_suffix`), and a failure below the Ultimate Modular rig's 62 bones and 24 actions |

The contract v1 gates are warnings by default because contract v1 was written for the earlier single base body: every
final-test character is taller (m1_rex 1.967 m with his hair, m2_walt 1.858, w1_ivy 1.845, w2_nova 1.844; without hair
1.765 to 1.827 m) and their eyes sit at 1.69 to 1.70 m, above the game's 1.6 m camera height. The contract v2 decides
(scale the characters at export, or move the camera and the capsule). `--strict-contract` applies the contract's own
severities (height fails, eyes warn).

Output: `<out>/<stem>/report.json` (`passed`, every check with its status and detail, Godot's noteworthy lines, per
part vertices, binds, rest bounds and materials, per animation length, loop mode, tracks, position tracks and motion) and `inspect.json` (the raw
description); exit 1 when any check fails. On 2026-10-03 all four final-test characters passed every check (with the
two contract warnings and the loop-mode warning each): 62 bones, 8 or 9 parts with 62 binds each, 24 animations of 62 tracks each (Godot's
`remove_immutable_tracks` drops the constant ones: 7 position and 55 rotation tracks remain in Death), 1488 tracks
resolved, the least motion 1.8 degrees (the women's Idle_Neutral).

## The off-screen window

Pictures need a real window: headless or minimized, Godot draws nothing and `RenderingServer.frame_post_draw` never
fires. The engineer's kickoff of 2026-10-03 allows a window off-screen, never on it. `--position -30000,-30000` does
not keep it off: Godot 4.7.2's `DisplayServerWindows::_create_window` (`platform/windows/display_server_windows.cpp`)
takes the primary screen when the requested rect is on no screen, then clamps a windowed window's position into that
screen's usable area, so every review window used to open at the top-left corner at its full size (#214; measured
before the fix: `frames` 496x639 for 2.0 s, `showroom` 656x839 then 1936x1119 for 3.0 s, `zones --shoot` 1616x939
for 3.6 s). Only a runtime `DisplayServer.window_set_position` skips the clamp. So:

- every window run goes through `_godot.window(args, (w, h), timeout)`: `--position 30000,30000 --resolution 1x1`
  and `PRIME_WINDOW=<w>x<h>` in the environment; the project starts its window borderless and unfocused (`[display]`
  `window/size/borderless` and `window/size/no_focus` in `godot/project.godot`, `godot/ragdoll/project.godot` and the
  House export and review folders' generated `project.godot`), so it is one pixel that takes no focus, and the clamp
  (`wpos.clamp(srect.position, srect.position + srect.size - p_rect.size / 3)`, a third of one pixel being 0) puts it
  at the usable area's far corner, (2560, 1392) here: just past the screen's right edge;
- each window script calls `godot/lib/offscreen.gd` `place()` first in `_initialize` (`const Offscreen =
  preload("res://lib/offscreen.gd")`): it moves the window to -30000,-30000, then grows it to `PRIME_WINDOW`, and
  prints `OFFSCREEN window <x>,<y> <w>x<h> screens <rects> ticks <ms>`; `report()` prints the line again after a later
  resize (the showroom's timing size). `window()` copies the helper into another project's `lib/` (the ragdoll proof,
  the House export and review folders);
- the runner refuses the run (`common.Failure`) when no OFFSCREEN line came or a reported window meets a screen
  (`_godot.offscreen_problems`, `tools/tests/test_godot_offscreen.py`), after writing the run's whole output to the
  caller's log (`window(..., log=)`, else `tools/out/godot-window/<time>-<pid>.log`); a non-zero exit with no OFFSCREEN
  line is reported as the script failing before it placed its window, exit code first. A test fails a runner that
  passes `--position` or `--resolution` itself or a window script that never calls `place()`.

Measured after the fix with a 5 ms window watcher around `frames`, `showroom` and `zones --shoot` (#214): no Godot
window on the screen at any time, and every picture pixel-identical to the one shot before the fix (same sizes, no
channel differs). The pixel waits past the right edge about 1 s, from Godot showing it to the script's
`_initialize`. Tried and not used: a 1x1 start without `--position` (Godot centres it: one pixel mid-screen for 1 s);
a start at -30000,-30000 (clamped to the corner 0,0: one pixel for 0.6 s); without `borderless` (Windows keeps a
title bar: 136x103 for 0.6 s); a minimized start restored after the move (20 ms of one pixel, but `SW_SHOWMINIMIZED`
activates the window and takes the focus). With a second monitor right of (or below) the primary one, the start pixel
would sit on that monitor's edge for that second; `offscreen_problems` still checks every screen.

The start pixel's place depends on the taskbar, since the clamp uses the usable area (the screen minus the taskbar):
measured only with the taskbar at the bottom, (2560, 1392). By the same arithmetic, not measured: with the taskbar on
the right edge the pixel's column is the usable area's right edge, over the taskbar (2560 minus its width), and only
its row (1440, the screen's bottom edge) keeps it off; with the taskbar on the left or the top it opens at (2560, 1440).
If a Windows build treats that row differently, the pixel would sit on screen over the taskbar for about 1 s.

The editor bake (`house --bake`, `addons/lmbake`) is the exception. The editor ignores the project's window settings
and has a minimum size (1024x600 times the editor scale), so by the source its main window opens clamped to the
screen's bottom-right corner, about a third of it on screen, for the editor's start-up (seconds), until the plugin's
`_enter_tree` moves it off-screen with `place(Vector2i.ZERO, false)` (only the off-screen part is checked: at 125 %
scaling and over the minimum height exceeds 720 px) and prints the OFFSCREEN line. The editor runs with
`--single-window`: its dialogs (the LightmapGI file dialog the plugin answers, the bake and import progress) are drawn
inside that main window. Without it each would be a native window, which Godot's `Window::_popup_base` re-centres on
the primary screen when its rect touches no screen, and the OFFSCREEN line covers only the main window. Uncertain
until a night bake is watched (it runs only at night, `house_bake.editor_allowed`): how much of the main window shows
during the start-up and for how long; that every dialog of the bake stays embedded with `--single-window` (a native
dialog would not show in the OFFSCREEN line, so the runner cannot catch it); and that the bake still succeeds in an
embedded dialog.

## frames

`frames/frames.gd` runs in a real window off-screen (480x600, "The off-screen window"). The
window plays no sound (`--audio-driver Dummy`, art #69): with no audio output device, WASAPI would log an ERROR. Per
animation:

- **times**: 8 evenly spaced whole frames (12 for locomotion, `Walk*` and `Run*`), on the pack's 24 fps frames where
  the export's samples are exact (so "evenly" means rounded to whole frames); a loop (the idles and the locomotion) is
  cut into equal parts of its cycle, a one-off runs from its first frame to its last (`_frames.times`, `_frames.cycle`).
  A closed loop's last key repeats its first, so its cycle is its keys' length. An **open** loop's last key does not
  (seam over 0.5 mm or 0.5 degrees in `export.json`): its first pose comes round one frame after its last key, so its
  cycle is one frame longer. The pack's `Run`, `Run_Left` and `Run_Right` are open (men 103 mm / 18.4 degrees, women
  75 mm / 12.5 degrees between the last key and the first): 20 frames, 0.83 s for the men and 25 frames, 1.04 s for
  the women, not the 0.79 s and 1.00 s of their keys; every other cycle closes exactly. The sheet title gives the
  cycle and says when it is open; `frames` warns about each open cycle;
- **camera**: one fixed orthographic camera, 35 degrees from the front toward the character's left and 8 degrees up,
  sized to the skinned vertices at every sample time with a 10 % margin (so a fall stays in frame);
- **light**: a neutral grey background and floor at y = 0, a key light with soft shadows, fill and rim lights,
  ambient light, linear tone mapping; specular only 0.15 on the key light (the pack's materials are metallic 0.4,
  roughness 0.42, and full-strength highlights turned single flat faces white);
- **capture**: seek with update, two process frames, `frame_post_draw`, the viewport image; a label (clip, frame,
  seconds) is drawn into each frame; the frames are scaled to 320 x 400 cells in a sheet of up to 6 columns under a
  title band (a 2D SubViewport); `sheets/<clip>.png`.

`frames.json` records the window, each clip's camera (centre, axes, orthographic size), times and, at each time,
every joint's world position and every bone's two **axis points** (`<bone>+x`, `<bone>+y`: 10 cm from the joint along
world +X and +Y in the rest pose, carried by the bone's pose, `Character.axis_points`): they turn with the bone, so the
comparison sees the rotation of a bone no other joint shows (17 leaves: `Head` carries the face, `Foot` the shoes, the
fingertips). `--compare` (default `all`: every rendered clip; `''` for none) keeps those frames at full size and runs
`tools/blender/compare_frames.py`: the character `.blend` (named by the export) posed at the same times from the rest
pose (an action leaves the channels it does not key where the last action put them: without the reset the Wave's feet
were 35 cm off), rendered with Workbench (`um/render.py`) through the same camera (Godot's orthographic size is the
vertical extent, Blender's `ortho_scale` with a vertical sensor fit), composed with Godot's frames above Blender's
(`compare/<clip>.png`), and every joint and axis point compared (`compare/compare.json`; one more than 1 mm off, about
0.6 degrees on the 10 cm lever, fails the command). `--video` writes every frame of one cycle (a closed loop frames 0
to last - 1, an open loop and a one-off frames 0 to last) and `tools/blender/encode_clips.py` encodes it with
Blender's FFmpeg as H.264 in MP4 (480 x 600, 24 fps, constant quality, the cycle three times) into `clips/<clip>.mp4`.
`--face CLIP` adds `sheets/face.png`: close-ups of the head (every skinned vertex above the Head bone's origin less
4 cm) at the clip's first frame, front and three-quarter from the character's right (yaw -35 degrees, as the faces
sheets), cells of 316 x 395 px; `--face-beside` puts crops of an approved sheet (`--face-rects`, pixels) to their left,
for the faces gate's before/after (docs/faces.md). `slice` runs it with the first review clip.

**Measured** on whole frames (2026-10-03, every clip of m1_rex and w1_ivy, 62 joints and 124 axis points): Godot and
Blender agree within 0.017 mm everywhere. Before the optimizer was turned off they differed by up to 16.7 mm (m1_rex
Run, a hand) and by 3.65 degrees on m1_rex's Roll `Foot.L`, which the joint-only comparison of the time could not see.
The poses in the comparison images match.

## Showroom and recommended look settings (`showroom`, art #140)

The frames stand above is a **measuring stand**: linear tonemapper, no reflected light (no glint in an eye, no sheen
on the clay), a flat colour ambient, no SSAO, simple shadows. It shows poses and seams honestly and stays as it is.
The showroom asks the other question: how close can the game's renderer bring a character to its Blender renders?
`tools/run.py showroom [<glb>]` (default the approved slice character m1) stages the GLB like `frames` and runs
`godot/showroom/showroom.gd` in an off-screen window (640 x 800, "The off-screen window", never headless). The
studio: the frames stand's grey background and floor, Poly Haven's CC0 `studio_small_09` HDRI from the raw folder
(`sources/polyhaven_hdris_2k.toml`; missing: a ProceduralSky) as a `PanoramaSkyMaterial` that lights and reflects
but is not seen, a key light with shadows, a fill and a rim light (the stand's three directions), and a perspective
camera with a 22 degree lens fitted to the head (front and three-quarter) or the whole body.

Each **variant** of the ladder (`_showroom.VARIANTS`, `--grid ladder`, the default; at most eight variants in one grid, each sets every key) adds to the one before it (since step 3; `--grid tune`, `--grid warm` and `--grid expose` are steps 2 and 3's tuning grids, below):

| # | Variant | What it changes |
|---|---|---|
| 1 | frames stand | the stand as is: linear, colour ambient 0.55, no reflections, key 1.05 with specular 0.15 |
| 2 | AgX | the AgX tonemapper, exposure 1.2; nothing else |
| 3 | AgX + sky + catch | the studio sky as reflections and half the ambient (sky contribution 0.5; the other half a dark warm colour (1.0, 0.8, 0.62) at energy 0.12: step 3's grid, below), the fill 0.12 (the stand's 0.35), exposure 0.9 (step 3's exposure grid, below), key 2.0 with specular 0.6, the clay's specular (`metallic_specular` of the `_clay` materials) 0.1 instead of Godot's 0.5, and a **catch light** for the eyes' glint: an `OmniLight3D` on the camera, up-left of the view at (-0.25, 0.3, 0), `light_size` 0.06 (a small spherical area light), energy 0.6, specular 16, no attenuation, and a cull mask of render layer 20 alone, on which the showroom also puts the meshes with an `_eye` material: it lights the eyes and nothing else; the eye materials at roughness 0.05 (exported 0.17), so the glint is a small sharp dot (step 2's grid, below) |
| 4 | + SSAO | radius 0.6, intensity 1.5, light affect 0.2 |
| 5 | + soft shadows | the key light's angular size 1.5 degrees (PCSS), soft shadow filter quality high, blur 1.0 |
| 6 | + SSS clay | subsurface scattering on the materials whose name ends in `_clay`, strength 0.25, skin mode on the head; quality medium |

It writes `face.png` (the approved Blender sheet's crops first, `--beside`, then per variant front and 3/4, 256 x 320
cells in 4 columns, or 208 x 260 in 6 for more than 14 shots), `look.md` beside an approved sheet (the numeric check below), `change.md` for a grid whose variants name a `parent` (step 3, below), `body.png` (per variant the full body), `shots/` at window size, `showroom.json` and `gpu_ms.md`: the GPU time
per variant (`RenderingServer.viewport_get_measured_render_time_gpu`, as in art #137's bake shots) with the window
resized to 1920 x 1080 and the full body framed, after a 120-frame warm-up, averaged over 30 drawn frames after 6
settling frames, three rounds in turn, the median round kept. `--write-presets` writes
`godot/showroom/look_presets.json` from `_showroom.PRESETS` (a test keeps them equal).

**The look per graphics preset: approved.** The engineer approved it on 2026-10-13 (art PR #148, issue #140) as the
game's recommended look: Low = ladder variant 3, Medium = 4, High = 5, Ultra = 6, all at exposure 0.9. Step 2's tuning
grid (below) set the clay's specular to 0.1 and the eyes' glint, step 3's the sky's ambient share, the fill and the
exposure (0.9). `godot/showroom/look_presets.json` says so in its `status` (`_showroom.STATUS`); the game side copies
it (this repo does not touch the game). **Still open:** the hair is 5 to 7 L* darker than Blender's, and the
game-side wiring is untested.

**Light D (2026-10-19, art #196, [the engineer's choice](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6272668389)):**
the characters' lights are the approved stage's with a stronger key and a back rim, the same in every preset (the
shared `lights` block of `look_presets.json`, `_showroom.LOOK_LIGHTS`). Each directional light now carries its
position: `at` and `look_at` (0, 0.9, 0), placed with `look_at_from_position` in the character's model space (origin
at its feet, front +Z; only the direction counts, so the game turns the set with the character or the camera):

| Light | `at` | Energy | Specular | Shadow |
|---|---|---|---|---|
| key | (-2.0, 3.2, 3.0) | 3.0 (was 2.0) | 0.6 | yes |
| fill | (3.0, 1.6, 2.0) | 0.12 | 0 | no |
| back (named `rim` before light D) | (0.5, 2.5, -3.0) | 0.30 | 0 | no |
| rim (new) | (0.7, 1.6, -2.8) | 3.0 | 0.5 | no |

The alien proofs' stage (`second_test.gd` and the scripts on it, `face_proof.gd`) reads these lights from
`look_presets.json` through `godot/showroom/look_lights.gd`, so every later proof renders under the approved lights.
The showroom's own ladder and grids keep their measured variants (key 1.05 to 3.0, no rim). Light D's tuning grid
toward the paintover rf2's thinner, crisper rim (`D:/prime-art-raw/review/char/alien-parts-kit/lightD/grid.png` with
`zoom.png`, `final.png`) tried the skin shader's fresnel glow sharper, Godot's rim term, the rim light further behind
and stronger, and its specular up: a rim specular of 1.0 laid a white sheen on the crest's top that rf2 does not have,
so the lights stay exactly D and only the skin's own rim changed (`alien.gd` `SKIN`: `rim_value` 0.2 to 0.6,
`rim_tint` 0.6 to 0.3), a lighter edge along the head's right contour.

Every preset uses AgX, the
sky as ambient and reflections and the catch light; each turns on everything the one below does. The shadow filter is the project setting
`rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality`, whose values are Godot's
`RenderingServer.ShadowQuality`: 0 hard, 1 very low, 2 low, 3 medium, 4 high, 5 ultra (`_showroom.SHADOW_FILTER`).
Low uses 2, the level of the showroom's variants 1 to 4; High uses 4, the level of variant 5's soft shadows; Ultra
stays at 4, since ultra (5) has not been measured.

| Preset | Adds | Shadows | SSAO | SSS on clay | MSAA |
|---|---|---|---|---|---|
| Low | AgX, sky ambient and reflections, catch light | 2048, filter 2 (low) | off | off | off |
| Medium | SSAO | 4096, filter 3 (medium) | half size, low | off | 2x |
| High | soft shadows | 4096, filter 4 (high), key angular 1.5 degrees | full size, medium | off | 4x |
| Ultra | SSS on the clay | 4096, filter 4 (high), key angular 1.5 degrees | full size, high | quality medium, strength 0.25 | 4x |

**Measured** (2026-10-13, the ladder with step 3's recommendation and exposure 0.9, slice_m1 at Idle 0.00 s, NVIDIA
GeForce RTX 4060, vulkan forward_plus, Godot 4.7.2; the GPU time of the whole frame with one character, the floor and
the sky; `D:/prime-art-raw/review/char/140c/ladder-exposure/`):

| Variant | Effects | GPU ms (1920x1080) | Step ms |
|---|---|---:|---:|
| 1 frames stand | linear | 0.76 |  |
| 2 AgX | agx | 0.78 | +0.02 |
| 3 AgX+sky+catch | reflections, catch_light, agx | 0.96 | +0.19 |
| 4 +SSAO | reflections, catch_light, ssao, agx | 1.62 | +0.66 |
| 5 +soft shadows | reflections, catch_light, ssao, soft_shadows, agx | 3.52 | +1.89 |
| 6 +SSS clay | reflections, catch_light, ssao, soft_shadows, sss, agx | 3.91 | +0.40 |

The steps move between runs by a few tenths of a ms (an earlier run had SSAO at +0.31 and SSS at -0.19); soft
shadows (PCSS) are the one step that stands out every time.

What the sheets showed in step 1 (history; the first grid, before the engineer looks): AgX alone (2) keeps the stand's colours and rolls
off the highlights; the sky-lit variants (3 to 6) add a soft sheen to the clay and the pupils but look **washed out**
next to the Blender face (pale hair, little key-light shading on the face): the first run (ambient energy 1.0, key 1.05)
was paler than the second (0.4, key 2.0), but at sky contribution 1.0 Godot ignores the ambient energy, so the
stronger key made the difference (step 2, below). The eyes' glint: the second run's catch light (a directional light, energy 0.1, specular 4.0) left none, since a
sun's highlight on roughness 0.17 is under a pixel; one grid of the area light (size 0.1, 0.2, 0.35 by energy 0.3,
1.0) chose size 0.2 at energy 0.3, a clear glint on the pupil (energy 1.0 blows out the whites); it costs no
measurable GPU time. SSAO darkens
the hair roots a little; soft shadows (PCSS) cost about 2 ms at 1920 x 1080 and change little on a face; SSS on the
clay costs nothing measurable and is barely visible. Step 2's grid below found the main cause, the clay's specular; the ambient's strength it did not test (below).


### Step 2: the tuning grid and the numeric check (2026-10-13, history)

`showroom --grid tune --beside <approved sheet>` (`_showroom.TUNING`) renders eight variants on step 1's variant 4
(sky-lit, SSAO, hard shadows), each named by what it changes; T2 to T6 add up, T7 and T8 branch off T6. Beside an
approved sheet the command also writes `look.md`: per face shot, the warm pixels (hue 20 to 85 degrees, chroma 5 or
more: not the grey background, the eye whites or the olive shirt) split into hair (L* under 50, or under 65 with chroma
over 18) and skin; the skin's mean L* and chroma, its shading (L* p90 - p10: how much the key light models the face),
the hair's mean L*, averaged over front and 3/4, and the distance (the sum of the absolute differences from the
approved Blender crops). A guide beside the eye: framing and pose differ a little. Sheets and tables:
`D:/prime-art-raw/review/char/140b/tune/` (the approved sheet's copy beside it, `approved_r4_noses_cast.png`).

| Shots | skin L* | skin C* | shade (L* p90-p10) | hair L* | distance | GPU ms |
|---|---:|---:|---:|---:|---:|---:|
| Blender (approved) | 66.7 | 12.8 | 23.8 | 28.6 | 0 | |
| T1 base (4 +SSAO) | 75.9 (+9.2) | 10.7 (-2.1) | 16.9 (-6.9) | 33.0 (+4.4) | 22.6 | 1.76 |
| T2 ambient 0.15 (no effect: below) | 75.9 (+9.2) | 10.7 (-2.1) | 16.9 (-6.9) | 33.0 (+4.4) | 22.6 | 1.85 |
| T3 +clay spec 0.1 | 75.7 (+9.0) | 11.3 (-1.5) | 16.3 (-7.5) | 25.2 (-3.4) | **21.4** | 1.95 |
| T4 +key 4000K x3 | 81.1 (+14.4) | 10.3 (-2.5) | 11.7 (-12.1) | 30.9 (+2.3) | 31.3 | 1.98 |
| T5 +AgX contrast 1.6 | 83.5 (+16.8) | 10.1 (-2.7) | 11.4 (-12.4) | 27.2 (-1.4) | 33.3 | 2.00 |
| T6 +eye glint | 83.4 (+16.7) | 10.2 (-2.6) | 11.4 (-12.4) | 27.2 (-1.4) | 33.1 | 2.01 |
| T7 T6+warm ambient | 82.4 (+15.7) | 12.2 (-0.6) | 11.2 (-12.6) | 26.2 (-2.4) | 31.3 | 2.00 |
| T8 T6 sky refl. off | 83.3 (+16.6) | 10.2 (-2.6) | 11.1 (-12.7) | 27.1 (-1.5) | 33.4 | 1.98 |

What it shows:
- **T2 tested nothing: the sky's ambient strength is still untested.** Godot uses `ambient_light_energy` (and
  `ambient_light_color`) only while `ambient_light_sky_contribution` is below 1.0 (the `Environment` class reference);
  steps 1 and 2 left it at 1.0, so the sky's ambient is the sky's own radiance and the energy 0.4 or 0.15 never
  reached it. T1's and T2's shots differ only in their labels (under 1 % of the pixels, all in the label strip at
  the top). The only variant that lowered the sky's share is T7 (contribution 0.4). Turning the sky reflections off
  (T8) changes half the pixels by about 1.5 of 255 and no number by more than 0.3. The pale hair comes from the
  clay's **specular** at Godot's default 0.5: the key light's sheen on the roughness-0.8 clay. At 0.1 (T3) the hair
  drops from L* 33.0 to 25.2 (Blender 28.6) and reads as dark rich brown.
- **A stronger, warmer key makes it worse.** 4000 K at energy 3.0 (T4) brightens the face (+5 L*) and flattens it
  (shading 16.3 to 11.7: the lit side rolls off into AgX's shoulder); the hair turns orange-red. AgX contrast 1.6 (T5)
  brightens further. A warm ambient (T7) brings the skin's chroma to Blender's (12.2 against 12.8) but not its shading.
- **The eye glint** (T6: eye roughness 0.05, catch light 0.06 m at energy 0.6) is a small sharp dot on the pupil like
  the Blender sheet's, where step 1's (0.2 m, energy 0.3, roughness 0.17) was a soft blob; it moves no face number and
  costs no measurable time.
- **Recommended: T3 with T6's eye glint**, now the ladder's base (variants 3 to 6, the presets): the smallest distance
  (21.4) and the hair within 3.4 L* of Blender, with the glint. The ladder rerun with it measures variant 4 at 21.4 and
  variant 5 (soft shadows) at 15.9, the closest: PCSS's soft terminator gives the face its shading back (19.6).
- **Left open** (step 3 took it up, below): the face was about 7 to 9 L* brighter and its shading 4 to 7 lower than
  Blender's. The levers this grid did not try: the sky's ambient lower (`ambient_light_sky_contribution` under 1.0 with a dark ambient colour, or the
  sky's `energy_multiplier`), the exposure down (about 0.8), the fill light weaker, the key from further to the side, the key's
  specular (0.6) lower.

### Step 3: the sky's ambient for real, the fill, exposure with a warm key (2026-10-13)

`showroom --grid warm --beside <approved sheet>` (`_showroom.WARM`) renders eight variants on step 2's ladder
variant 5 (soft shadows, SSAO, the clay's specular 0.1, the eye glint: the closest measured, 15.9), each named by what
it changes and naming its `parent`. For such a grid the command also writes `change.md`: per variant and per shot
the share of pixels (below the label strip) whose channels differ by more than 2 of 255 from its parent's, in the two
face shots counted over the parent's skin pixels alone (`_showroom.skin_pixels`, the pixels the numeric check calls
skin), in the body shot over all. A variant whose face skin changes under 0.5 % in both face shots does **not reach
the face**: "the body only" when the body shot changes, else **a no-op**; either is reported as such, not as a finding
(step 2's T2 was a no-op). The shots are reported apart because the body shot's floor and background change with
settings that miss the face (W2 below: 89 % of the body shot, 0.1 % of the face's skin). Sheets and tables:
`D:/prime-art-raw/review/char/140c/warm/`; the ladder rerun with W3 and W4: `.../140c/ladder/`.

| Shots | skin L* | skin C* | shade | hair L* | distance | face skin changed (front, 3/4) vs parent | GPU ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| Blender (approved) | 66.7 | 12.8 | 23.8 | 28.6 | 0 | | |
| W1 base: 5 soft shadows | 73.7 (+7.0) | 11.7 (-1.1) | 19.6 (-4.2) | 25.0 (-3.6) | 15.9 | | 3.63 |
| W2 sky energy x0.5 | 73.7 (+7.0) | 11.7 (-1.1) | 19.6 (-4.2) | 25.0 (-3.6) | 15.9 | 0.0 %, 0.1 % (W1): **not the face** | 3.63 |
| W3 sky share 0.5, warm amb. | 69.7 (+3.0) | 13.1 (+0.3) | 22.2 (-1.6) | 22.9 (-5.7) | **10.6** | 100 %, 100 % (W1) | 3.62 |
| W4 fill 0.12 | 72.8 (+6.1) | 11.9 (-0.9) | 20.5 (-3.3) | 24.4 (-4.2) | 14.5 | 52.1 %, 16.4 % (W1) | 3.63 |
| W5 exp. 0.8, key 4000K x2.5 | 76.2 (+9.5) | 10.8 (-2.0) | 13.2 (-10.6) | 26.6 (-2.0) | 24.1 | 100 %, 100 % (W1) | 3.63 |
| W6 W3+W4+W5 | 74.8 (+8.1) | 12.4 (-0.4) | 10.0 (-13.8) | 26.7 (-1.9) | 24.2 | 100 %, 100 % (W5) | 3.62 |
| W7 W6 sky share 0.25 | 74.7 (+8.0) | 13.2 (+0.4) | 8.2 (-15.6) | 26.8 (-1.8) | 25.8 | 99.7 %, 100 % (W6) | 3.62 |
| W8 W6 Low: hard, no SSAO | 74.8 (+8.1) | 12.9 (+0.1) | 10.0 (-13.8) | 26.2 (-2.4) | 24.4 | 13.6 %, 9.1 % (W6) | 0.92 |

What it shows:
- **W2 does not reach the face.** The sky's `energy_multiplier` at 0.5 changes 89 % of the body shot's pixels
  but 0.0 and 0.1 % of the face's skin, and no face number: for the face it is a no-op, not
  a finding. Why the multiplier misses the face's skin while halving the sky's share (W3) darkens it by 4 L* this grid
  does not show. Every other variant reaches the face.
- **The sky's ambient share is the lever** (W3): `ambient_light_sky_contribution` 0.5 with a dark warm colour
  (1.0, 0.8, 0.62) at energy 0.12 brings the skin 4 L* darker, its chroma to Blender's and its shading up by 2.6. A
  weaker fill (W4, 0.35 to 0.12) adds a little shading.
- **W5 changed two things at once and its numbers miss the face** (corrected after the review of #148). It lowered
  the exposure to 0.8 *and* raised the key from 2.0 to 2.5 with a 4000 K colour, so it tested no lever alone; and the
  warm key tints the floor, which the check's tone split then counts as skin (the exposure grid below: 2.5 times the
  base's skin samples, most in the shot's lower half). So W5 to W8's skin L* and shading are not the face's; the
  earlier reading "a brighter key flattens the face even with the exposure down" was that artefact and is withdrawn.
  `look.md` now adds the same measures on the base's skin pixels (`_showroom.masked_measures`): there W5 is 2.2 L*
  bright with its chroma +5.6 (the key's orange), W8 0.6 L* dark with chroma +9.6.
- **Hard shadows and no SSAO** (W8) cost 2.7 ms less.
- **Recommended after this grid: W3 with W4** (sky share 0.5, dark warm ambient 0.12, fill 0.12), the ladder's base
  (variants 3 to 6) since; the exposure grid below adds exposure 0.9. The ladder rerun with W3 and W4 at exposure 1.0
  (history, `.../140c/ladder/look.md`):

| Ladder variant | skin L* | skin C* | shade | hair L* | distance | GPU ms |
|---|---:|---:|---:|---:|---:|---:|
| 3 AgX+sky+catch (Low) | 72.2 (+5.5) | 12.6 (-0.2) | 20.1 (-3.7) | 22.6 (-6.0) | 15.4 | 0.95 |
| 4 +SSAO (Medium) | 71.8 (+5.1) | 12.6 (-0.2) | 20.6 (-3.2) | 22.4 (-6.2) | 14.7 | 1.64 |
| 5 +soft shadows (High) | 69.8 (+3.1) | 13.0 (+0.2) | 24.7 (+0.9) | 22.6 (-6.0) | 10.2 | 3.53 |
| 6 +SSS clay (Ultra) | 70.0 (+3.3) | 12.9 (+0.1) | 23.0 (-0.8) | 24.5 (-4.1) | 8.3 | 3.86 |

### Step 3: the exposure alone and the warm key's colour alone (2026-10-13, after the review of #148)

`showroom --grid expose --beside <approved sheet>` (`_showroom.EXPOSE`) takes the levers W5 mixed apart, on the
recommendation above (ladder variant 5, High, at exposure 1.0): the exposure alone at 0.9, 0.8 and 0.7; the 4000 K
key's colour alone at the key's energy 2.0; that key with exposure 0.8 and 0.7; and the key at 2.5 with exposure 0.8
(W5's levers on this base: it measures as W6, as it should). Each variant changes one setting against its parent; all
reach the face (`change.md`: 70 to 100 % of the face's skin). `look.md` measures them twice: by the tone split as
before, and on X1's skin pixels (the same camera and pose), which the warm key's floor and the darker exposures'
shaded skin cannot move between the skin and the floor or hair. Sheets and tables:
`D:/prime-art-raw/review/char/140c/expose/`.

| Shots | skin L* | skin C* | shade | hair L* | distance | on X1's skin: L*, C*, shade | skin distance |
|---|---:|---:|---:|---:|---:|---|---:|
| Blender (approved) | 66.7 | 12.8 | 23.8 | 28.6 | 0 | 66.7, 12.8, 23.8 | 0 |
| X1 base: 5 (High) | 69.8 (+3.1) | 13.0 (+0.2) | 24.7 (+0.9) | 22.6 (-6.0) | 10.2 | +3.1, +0.2, +0.9 | 4.2 |
| X2 exposure 0.9 | 68.7 (+2.0) | 13.2 (+0.4) | 23.3 (-0.5) | 22.0 (-6.6) | **9.5** | +1.1, +0.6, +1.5 | **3.2** |
| X3 exposure 0.8 | 68.1 (+1.4) | 13.4 (+0.6) | 21.4 (-2.4) | 21.9 (-6.7) | 11.1 | -1.0, +1.0, +2.5 | 4.5 |
| X4 exposure 0.7 | 67.2 (+0.5) | 13.6 (+0.8) | 18.4 (-5.4) | 21.5 (-7.1) | 13.8 | -3.6, +1.4, +3.1 | 8.1 |
| X5 key 4000K (x2.0) | *74.9* | *12.1* | *15.7* | 26.1 (-2.5) | *19.5* | -0.3, **+8.6**, -1.9 | 10.8 |
| X6 X5 exposure 0.8 | *72.8* | *12.0* | *8.3* | 26.3 (-2.3) | *24.7* | -4.6, +9.9, -0.7 | 15.2 |
| X7 X5 exposure 0.7 | *71.4* | *11.7* | *5.4* | 26.8 (-1.8) | *26.0* | -7.3, +10.5, -0.2 | 18.0 |
| X8 X6 key x2.5 | *74.8* | *12.4* | *10.0* | 26.7 (-1.9) | *24.2* | -2.4, +9.6, +1.2 | 13.2 |

The GPU time is the base's in every row (3.59 to 3.66 ms). In italics: the tone split's numbers with the warm floor
counted as skin, not the face's.

What it shows:
- **The exposure is a lever, and 0.9 is enough.** Exposure alone darkens the skin as expected (on X1's skin: 2, 4 and
  7 L* for 0.9, 0.8 and 0.7). 0.9 (X2) is the closest in both measures (9.5 against 10.2; 3.2 against 4.2); on X1's
  skin 0.8 and 0.7 overshoot below Blender's, and they darken the hair further. The tone split reads their shading
  as lower, but it also counts fewer skin pixels (X4's front shot 3318 against X1's 4665, likely the shaded skin
  turning "hair"); on X1's skin the shading rises a little.
- **The 4000 K key's colour turns the skin orange**, whatever the exposure: chroma 8.6 to 10.5 over Blender's on X1's
  skin, the floor and shirt tinted with it (`face.png`). A key that warm is out; its strength (X8 against X6: 2.0 to
  2.5) adds 2 L* and a little shading. The hair is closest under it (26 to 27 L*), which points at the hair's own
  colour rather than the light.
- **Recommended: X2, exposure 0.9**, now in the ladder (variants 3 to 6) and the presets (`tonemap_exposure`). The
  ladder rerun with it (`D:/prime-art-raw/review/char/140c/ladder-exposure/look.md`):

| Ladder variant | skin L* | skin C* | shade | hair L* | distance | GPU ms |
|---|---:|---:|---:|---:|---:|---:|
| 3 AgX+sky+catch (Low) | 70.7 (+4.0) | 12.9 (+0.1) | 20.4 (-3.4) | 21.4 (-7.2) | 14.7 | 0.96 |
| 4 +SSAO (Medium) | 70.5 (+3.8) | 12.9 (+0.1) | 20.5 (-3.3) | 21.4 (-7.2) | 14.4 | 1.62 |
| 5 +soft shadows (High) | 68.7 (+2.0) | 13.2 (+0.4) | 23.3 (-0.5) | 22.0 (-6.6) | **9.5** | 3.52 |
| 6 +SSS clay (Ultra) | 68.9 (+2.2) | 13.1 (+0.3) | 22.0 (-1.8) | 23.6 (-5.0) | 9.3 | 3.91 |

  **High** (variant 5, 3.5 ms at 1920 x 1080 with one character) is the closest a High preset can afford: the skin 2
  L* brighter than Blender's, its chroma and shading matched. **Low** (variant 3, under 1 ms) is the cheapest
  acceptable: 14.7, the face 4 L* bright and a little flatter. Ultra's SSS lifts the hair (9.3).
- **Still open:** the hair is 5 to 7 L* darker than Blender's; its lever is the hair's own colour or specular, not
  the light. The key from further to the side and its specular are untried; so is a key warmer than white but under
  4000 K's orange (4500 to 5500 K). The tone split's numbers are unreliable for any variant that tints the floor or
  darkens the face much; the measure on the base's skin pixels is the cross-check, itself a guide (it keeps pixels
  that a variant moves into shadow, so it reads W3's shading as +9.2 where the split reads -1.6).

The engineer approved these settings per graphics preset on 2026-10-13 (art PR #148, issue #140);
`look_presets.json`'s `status` says so. The hair and the game-side wiring above stay open.

## The SkeletonProfileHumanoid trial (`godot-check --humanoid`)

Input for the contract v2, not adopted. The character is imported again with a BoneMap
(`godot/import/um_humanoid_bone_map.tres`, written from `_humanoid.BONE_MAP`) on its Skeleton3D through the importer's
`retarget/bone_map` option, twice (`_humanoid.VARIANTS`): as `<id>_humanoid.glb` with
**`retarget/remove_tracks/unimportant_positions = false`** (the result), and as `<id>_humanoid_defaults.glb` with every
retarget option at its default (for comparison). The other retarget options stay at their defaults in both (bone
renamer on, the skeleton renamed `GeneralSkeleton`, rest fixer on with its `overwrite_axis` and
`normalize_position_tracks` defaults). Mapped: 51 of the profile's 56 bones (Root, Hips, Spine = Abdomen, Chest =
Torso, UpperChest = Chest, Neck, Head; per side Shoulder, UpperArm, LowerArm, Hand = Wrist, the thumb's Metacarpal,
Proximal and Distal = Thumb1 to 3, and Index, Middle, Ring, Little = Pinky joints 2 to 4 as Proximal, Intermediate,
Distal; UpperLeg, LowerLeg, Foot). The fingers' first joint (`Index1` starts 2.8 cm from the wrist, at the thumb's
base) is a metacarpal the profile has only for the thumb. Unmapped rig bones: `Body`, `PT.L`, `PT.R`, and `Index1`,
`Middle1`, `Ring1`, `Pinky1` per hand (11). Profile bones without a rig bone: `LeftEye`, `RightEye`, `Jaw`,
`LeftToes`, `RightToes`.

Result (m1_rex and w1_ivy, 2026-10-03): **the humanoid import works with `unimportant_positions` off.** One skeleton
of 62 bones, every part still skinned to it, 24 animations whose tracks resolve and move, height, feet and facing
unchanged, and every mapped joint within 0.01 mm of the plain import at the compared poses of Idle, Walk and Wave.
With Godot's defaults the locomotion breaks: `unimportant_positions` drops the position tracks of every mapped bone
but the root and the hips, while the pack moves the feet and the shoulders with position keys (Walk's position tracks:
`Body`, `Foot.L/R`, `Shoulder.L/R`, `PT.L/R`), so the mapped feet end up 52 cm (m1_rex) and 54 cm (w1_ivy) from the
plain import's, twisted and off the ground (`humanoid/m1_rex_humanoid_defaults_Walk.png` on the review page). Caveat:
keeping those position tracks is exact here because the trial retargets onto the same rig; on a skeleton with other
proportions the feet's absolute positions would not fit (the reason Godot drops them by default). That trade-off is the
contract v2's.

## The slice character (`slice`, art #42 part C)

The game's first character (prime-game M6.2/M7, prime-game#522): one cast member of `recipes/clay_cast_e.json` in the
clay look with the clay face kit and its baked textures, carrying the MVP animation set's exported clips for its body
type, in place, in **one GLB** (body, skeleton and clips: prime-game `docs/ARCHITECTURE.md` section 11.1 takes a
character as `assets/characters/<id>/<id>.glb`; the contract wants one clip library on the contract skeleton, and the
slice has one body). Settings: `recipes/slice_character.toml` (the cast id, the recipe, the set, the review clips and
`eye_height_m`, the `exclude` table with a reason per clip). One command:

```
tools/run.py anim-set --set mvp --body men --out <raw>/anim-sets/slice-42c        # once per body type, if not built
tools/run.py slice [--cast m1] --anim-set <raw>/anim-sets/slice-42c --asset assets/character/slice_m1 --review <raw>/review/char/42d
```

`slice --own-proportions` (art #207) is for a character whose skeleton has the contract's names, parents and
T-pose but its own proportions, so its rest differs from the set's donor on purpose (the alien base character's by up to
214 mm, art #196). The rest difference is then only reported (`rest_max_mm`, `rest_worst` in `<id>.actions.json`), and
the clips' `Root` and `Hips` location keys (and the armature object's, if keyed) scale by the character's leg length
over the donor's: per leg the thigh (`UpperLeg` to `LowerLeg` head), the shin (`LowerLeg` to `Foot`) and the ankle's
height, averaged over both legs (`leg_m`: `[donor, character]` in metres; `leg_scale` = character / donor). That keeps
the stride and the hips' bob in proportion to the legs that carry them. Every other key carries over unchanged: the
rotations are bone-local, and the location and scale keys that the retarget writes on every bone are left as they are
(a clip that moves another bone's location moves it by the donor's distance). Since a bone-local rotation turns a bone
the same about its own axes on both rigs, the pose differs wherever the rest orientations differ: the largest
difference outside the toes (the shorter angle, 0 to 180 degrees, `slice_math.turn_deg`) is reported on every run (`rest_turn_max_deg`, `rest_turn_worst`; #210). The
`eye_height_m` scale comes after the leg scale. With `--asset`, HANDOFF.md's size note records the flag, the rest
differences, `leg_m` and `leg_scale` from `<id>.actions.json`. The rules are plain Python in
`tools/blender/slice_math.py` (tests: `test_slice_proportions.py`). Feet can still slide a little where a clip's foot
placement depends on more than the leg length (a different hip width or foot length).

`slice` assembles the cast member (`assemble --look clay --bake`; `--blend` reuses a saved one), puts the set's clips
on its armature in Blender (`tools/blender/slice_actions.py`; it refuses a rest pose that differs from the set's by
more than 2 mm, the toes excepted, unless `--own-proportions`, above; then it scales the rig, the parts with their shape keys
and the clips' location keys uniformly about the floor so the
eyes' rest centre is at `eye_height_m`, 1.60 m: the engineer's `eyes16`, 2026-10-12),
exports with `export --textured`, runs `godot-check --strict-contract --humanoid --textured`, `frames` of the review
clips with the Blender comparison and an 8-view turnaround, and with `--asset` writes the asset folder:
`export/slice_<cast>.glb`, `manifest.toml` (kind `character`, one `[[clips]]` table per clip with its source, licence,
`public_repo_ok` and `ai_generated`; a clip whose source is not `public_repo_ok` stays out and is listed),
`package.json` (the file, its bytes and SHA-256, the game folder) and `HANDOFF.md` (what to copy where, the import
settings, the clip table with the avatar states each clip serves, sizes, what was left off). `--cast` builds another
member with the same settings. The approval fields stay empty until the engineer approves the look.

Measured (m1, 2026-10-12): 7.45 MB GLB (10 embedded images, 4.44 MB), 6 parts on one skeleton of 64 bones, 9392
triangles, 25 clips at 30 fps; glTF-Validator 0 errors (6 `NODE_SKINNED_MESH_NON_ROOT` warnings, as every export);
`frames` within 0.022 mm of Blender. Left off: `Knockdown`, `Crawl_Start`, `Crawl_Loop`, `Getup_Back`, `Getup_Fours`
(the knockdown is a ragdoll: prime-game#522, art #115) and the set's review-only clips (`export = false`).

**The height.** Built at the pack's size, m1 stood 1.986 m with the eyes at 1.722 m (the clay look's head is 1.3
times the pack's, with hair on top). The engineer chose `eyes16` (2026-10-12): `slice` scales the character so the
eyes are at 1.60 m (about 1.845 m tall), and the contract's plasticine window is 1.70 to 1.90 m
(`plasticine_height_max_m`, docs/contract.md); `godot-check --textured` applies it.

## The ragdoll (`ragdoll`, art #115)

The knockdown is a ragdoll (docs/contract.md, "Ragdoll"). `tools/run.py ragdoll <glb> [--out DIR] [--asset DIR]
[--fall] [--shots DIR]`:
- measures the ragdoll data from the GLB in plain Python (`tools/runner/commands/_ragdoll.py`, about 0.3 s): the
  GLB's joint nodes are Godot's bone frames, so the shapes need no axis conversion and no Blender run. Each body's
  shape is fitted to the vertices its bone (or a follower, `FIT`) weights most: a box, or a capsule along the bone's
  Y whose radius is about the 85th percentile of their distances. It checks the schema and values (`check`, `shapes_in_bounds`) and writes
  `tools/out/ragdoll/<stem>/<stem>.ragdoll.json`;
- `--asset DIR` writes `export/<id>.ragdoll.json` into the character's asset folder, lists it in `package.json` and
  puts the "Ragdoll (art #115)" section in `HANDOFF.md` (replacing an earlier one). `slice --asset` does the same;
- `--fall` runs the proof headless; `--shots DIR` runs it in an off-screen window ("The off-screen window") and
  copies `fall_sheet.png` (8 moments x front and side, 1280x400), `shapes_sheet.png` (the bodies over the standing
  character, 640x400) and `fall.json` into DIR. Both run `--fixed-fps 60`.

**`godot/ragdoll/`** is its own Godot project: the game runs Jolt Physics, and the art project `godot/` uses the
default engine, which a shared change would alter. It carries the game's physics layer names. Godot's scan of
`godot/` skips a folder holding a `project.godot`; its `.godot/` and `import/` are ignored.
- `builder.gd` is the reference builder the game copies. `build(skeleton, data)` adds a PhysicalBoneSimulator3D and
  one PhysicalBone3D per body (their own joints off); `start(sim, data, velocity)` starts the simulation from the
  current pose, gives every body the avatar's velocity, and one physics frame later links the bodies with Joint3D
  nodes (ConeTwist, Hinge, Pin; the twist axis along the bone). The rig's feet hang from `Root`, not from the lower
  legs, so PhysicalBone3D's own joints could not link them. `stop(sim)` ends it (a revive).
- `fall.gd` stages a floor (layer `world`) and a player box (layer `living_players`) in the fall path, pauses `Idle`
  at 0 s, starts the fall at 3 m/s forwards, and asserts: no NaN; in the fall no joint more than 25 degrees past its
  limit or 40 mm apart; over the last 0.5 s at rest no joint more than 12 degrees past or 25 mm apart; no body
  faster than 12 m/s after 0.5 s; at rest by 3.5 s, lying below 0.45 m and not through the floor (so the player box
  was passed through); every body on layer 3 with mask 1; a hat on `Head` and the package on the chest
  (BoneAttachment3D sockets) within 2 mm of their simulated bones.

Measured on slice_m1 (Jolt, 2026-10-14): at rest from about 1.7 s, the worst joint about 21 degrees past its limit
in the fall (the feet, dragged along the floor), at rest 6 to 12 degrees (it varies with the landing) and the
ankles about 20 mm apart; the sockets within 0.01 mm. Tuned with one grid of 11 settings: 2 kg feet and 1 kg hands
(the mass taken from the trunk), `angular_damp` 6, 40 degree ankle cones and 30 degree spine cones; a hinge ankle and
lighter feet did worse. The BoneAttachment3Ds update on the same `skeleton_updated` signal after a script's handler:
compared inside the handler they lag one update (about 0.1 m at the fall's speed); `fall.gd` compares them after the
frame. Outside that signal `get_bone_global_pose` returns the animation pose, not the simulated one.

## Bench (`bench`, art #212)

`tools/run.py bench [GLB ...] [--proxy-from BLEND] [--copies 10,20]` measures what a character costs in Godot 4.7.2,
the measurement behind the character budgets (docs/contract.md, `docs/decisions/2026-10-18-character-budgets.md`).
`godot/bench/bench.gd` stands N copies of each GLB in a meeting ring (1.3 m apart, at least 2.2 m radius), each playing
its idle clip from its own offset with every face morph weighted 0.05 (the worst case: Godot blends only non-zero
weights), and looks at them from 2.5 m behind the ring at eye height (1.6 m, vertical FOV 75 degrees). The ring is
small: its far side is 7.1 m from the camera at 10 copies and 10.9 m at 20, so no body stands beyond the contract's
10 m LOD2 at 10 copies and 5 of 20 do at 20 (each row's `beyond` column counts them, camera to each copy's origin). The stage: a ground plane, a procedural sky, AgX, SSAO, a directional light with 4 shadow splits
(max distance 60 m) and a shadowed omni lamp (cube shadows, range 9 m) at the ring's centre. The window is 1920x1080,
off-screen (opened through `_godot.window()` and moved by `Offscreen.place()` first, "The off-screen window"; never
headless, never minimized), vsync off.

Per GLB and copy count it loads the copies, warms up (120 frames: the GPU clocks up and the pipelines compile), shoots
the view for the sheet, then measures each variant over 300 frames after 30 settle frames: the median GPU and CPU ms
of the viewport (`viewport_get_measured_render_time_gpu/cpu`, as `showroom`; the CPU ms is the rendering's only), the
median process ms (`Performance.TIME_PROCESS`: the animation players and the skeleton poses, which the render CPU ms
leaves out) and whole frame ms (between two `frame_post_draw`s), the p95 GPU ms, and the frame's primitives, draw
calls and objects and the video, texture and buffer memory (`Performance` monitors). The process and frame ms came
after the measurement of 2026-10-18 (`docs/decisions/2026-10-18-character-budgets.md`), whose table has neither. The variants:

| Variant | What |
|---|---|
| `empty` | the stage without characters: subtracted from every row as `chars GPU ms` / `chars CPU ms` |
| `auto_full` | the importer's automatic LODs (the viewport's `mesh_lod_threshold` 1.0), every mesh casts shadows |
| `auto_proxy` | the drawn meshes cast no shadow; the GLB's `bench_shadow` part casts alone (`SHADOWS_ONLY`) |
| `off_full`, `off_proxy` | the same with `mesh_lod_threshold` 0: always LOD0 |
| `hand_full` | `bench_shadow` drawn as a hand-made LOD2 from `--hand-lod-m` (default: the contract's LOD2 `from_m`, 10 m) on, the full meshes before it (visibility ranges); it switches only the bodies in the `beyond` column |

The proxy variants need a part whose name holds `bench_shadow`; without it a GLB gets `auto_full` and `off_full` only.
Godot extracts a GLB's textures as Lossless and only the editor turns them to VRAM Compressed on first use, so the
command sets the extracted textures' `.import` to VRAM Compressed with mipmaps (normal maps as normal maps) and imports
again, as the game has them. The GLBs are staged as `bench_<stem>.glb`, so these settings never reach the textures
another command (godot-check, frames) extracts from the same GLB. Memory per group (`buffer MB added` and so on) is the growth from loading the GLB and its
copies; a GLB's mesh data (its morphs) is counted once, in the first group that loads it.

`--proxy-from <character.blend>` first makes the stand-in in headless Blender (`tools/blender/bench_proxy.py`): the
largest skinned mesh subdivided once and decimated to `--tris` (40,000) for the whole character with its weights
interpolated and limited to 4; a copy decimated to `--shadow-tris` (7,000) as `bench_shadow`; the head (vertices whose
largest weight is on Head, Jaw or an eye bone) split off as its own mesh with `--morphs` (0, 32, 64) seeded random
1 to 3 mm bumps; each image swapped for its own 2048 bake beside the .blend, matched by stem (`alien_body_col` takes
`alien_body_col_2048.png`; an image without one is kept and listed in `proxy.json`). Each
morph count is saved as `proxy_m<N>.blend` and exported with `export --textured`.

Out folder (default `tools/out/bench/run/`): `bench.json` (every row and group, the adapter, the GLBs), `bench.md` (the
tables and one verdict line per GLB and count: the default setup's (`auto_full`) `chars GPU ms` against
`--budget-ms`, 4 ms, with the worst variant named beside it),
`sheet.png` (one shot per GLB and count, 1272 px), `shots/`, `godot.log`; with `--proxy-from` also `proxy/` and `glb/`.
A full run with `--proxy-from` (Blender, three exports, 31 variants) took about 2 minutes on the RTX 4060 machine;
start it in the background all the same.

## The alien's plasticine skin (`godot/alien_look/`, art #196)
The skin material for the plasticine alien in Godot 4.7.2, chosen in art #196 (steps G3 and G3b) by off-screen
renders beside the approved target frames (f2a for the face at 0.6 m, f1a for the body at 3 m) under the approved look
(exposure 0.9, no saturation adjustment).

- `alien_clay.gdshaderinc` is the shared body: the baked base colour and normal (the 2048 game sheets at a clay
  strength), plus a tiling micro-detail normal and height (fingerprint whorls and smudges, 1024, one tile per 7 cm of
  skin) added to the baked normal in the sheet's UV space, so the pattern stays on the skin when the body bends. The
  height darkens and roughens the grooves. Roughness about 0.55, a low specular, a light rim and Godot's subsurface
  scattering in skin mode. The eyes never use it: they keep a `StandardMaterial3D` at roughness 0.3 with a clear coat.
- `alien_clay_mix.gdshader` (option C2, **the recommended one**) breaks the tile's repetition with a second rotated,
  rescaled sample blended by a low-frequency noise mask, at the same contrast. 10 characters cost 1.257 ms of GPU
  against 1.255 ms for the single tile (RTX 4060, 1920x1080).
- `alien_clay.gdshader` (option C) is the single tile. `alien_clay_tri.gdshader` (option D, triplanar in model space)
  was measured and set aside: Godot skins before `vertex()`, so its pattern slides where the body bends, and it costs
  more (0.67 against 0.58 ms for 10).
- `alien_clay_cal.gdshader` is calibration only: a linear colour matrix on the base colour. `look.gd`'s calibration
  mode finds the matrix that matches each region (teal, mint, coral) to f2a's lit half, and that correction is then
  baked into the base colour sheets, so the game's look values stay as approved.
- `look.gd` is the proof script, with six modes: `shots` (a present-day room box, the material options and clay
  strengths), `bench`, `grid` (the micro-detail's gain), `calib`, `cells` (one pixel under several overrides) and
  `sheets_b` (the before/after sheets). It is research tooling, not a runner command yet: a run goes through
  `_godot.window()` like every other window run (its header gives the arguments and the spec).

Clay strength 2 is the closest to f2a; at 3 m the strengths cannot be told apart. The look still needs the engineer's
yes; the game repo takes the material only through a game-repo PR under the character contract.

## The alien parts kit (`godot/alien/`, art #196, step S3)
The parts-kit alien (not plasticine: a smooth, soft-matte designer-toy look) as one GLB from
`tools/blender/alien_assemble.py`: the body and head welded into one skinned mesh, every eye design, mouth piece and
crest a named node under the socket nodes (`Eye_L`, `Eye_R`, `Mouth`, `Crest`) that are children of the Head joint, so
Godot imports them under a `BoneAttachment3D` and three.js under the Head bone. One variant of each kind is shown at
a time, by visibility.

- `alien_hue.gdshader`: the hue and its light tint are `instance uniform`s (one material for every hue mesh of all
  characters), set **linear** from the script: no `source_color` hint on an instance uniform. The masks are in `UV2`
  (glTF `TEXCOORD_1`): `UV2.x` the light mask, `1 - UV2.y` the accent mask. **The glTF exporter flips V**
  (v_gltf = 1 - v_blender) and Godot keeps glTF's V, so any mask written into a Blender UV's v must be flipped back in
  the shader (unflipped, the whole body rendered in the accent colour with hue-coloured knees).
- `alien.gd`: the controller (`preload`, no class cache in a `-s` script): the material swap by the material's
  name `alien_hue`; eye, mouth and crest swaps; hues; blink by the lid nodes' local X rotation; talk from an
  `AudioEffectSpectrumAnalyzer` on the speaker's own bus. `get_magnitude_for_frequency_range` defaults to the band's
  **maximum** bin, so a band reads its strongest harmonic: on a vowel-like test voice the 150-1000 / 1000-4000 Hz ratio
  was A 1.8, E 3.5, O 6.3 (as a harmonic model predicts), so one ratio cannot tell A from E (A's second formant,
  about 1150 Hz, is in the high band); E takes a second ratio, 1800-4000 against 1000-1800 Hz.
- `proof.gd`: the off-screen proof (turntables, Idle and Walk, blink, talk, variants, hues, draw calls). No runner
  command calls it yet: run it by hand through `_godot.window()` with `--audio-driver Dummy` (the Dummy driver still mixes, so the analyzer sees the signal) and
  the Master bus muted. `make_test_speech.py` writes its test WAV (standard library).
- **The face materials (S5, art #196):** the first test's eyes (a cold white, roughness 0.12, a 6-degree pupil) and
  glossy orange lips read "so-so, creepy"; the stage-1 human faces' materials (`faces/clay_kit.json`, docs/faces.md)
  replace them. `alien.gd` swaps them by the imported material's name (`set_face_look("s5")`, the default; `"first"`
  keeps the imported ones for before/after sheets):
  - `alien_eye.gdshader` on `alien_eye_<design>`: no texture, all from the ball's model space (centred, +Z the pupil
    axis): a warm off-white (sRGB 0.95, 0.93, 0.86), shaded toward a warm tint (never grey) in the corners and under
    the lids (the lid edges are instance uniforms that `_apply_lids` sets from the lid rotations, edge = -rotation.x,
    so the shadow follows the blink), a dark iris with a darker edge ring (bored: 25 degrees, a near-black brown), a near-black
    pupil (bored 11.5, manic 12 degrees), and **one painted catch light** on the pupil, up and toward the viewer's
    left, as emission (no extra light or render layer; it moves with the eye, as a toy's painted glint). Roughness
    0.38, so the key light gives a broad sheen and no second hard glint.
  - **The eyes' rest look:** the sockets point 8 degrees outward (S2a's sphere fit), so the pupils diverged (wall-eyed).
    `_apply_lids` sets each ball's rotation to 11.5 degrees inward about the socket's up axis (absolute, so a GLB whose
    balls already carry it is unchanged; `aim_in_deg`): the eyes meet about 1.2 m ahead.
  - Lips, inner cup and teeth: `StandardMaterial3D`s with wrapped diffuse and **culling off** (the imported materials
    are double-sided; culled, the inner cup vanished and the open mouths showed the skin): lips sRGB (0.76, 0.45, 0.40; S9: (0.82, 0.44, 0.37) in `alien_lip.gdshader`)
    roughness 0.6 specular 0.3; the cup a dark plum (0.25, 0.11, 0.14), roughness 0.9; teeth ivory (0.96, 0.95, 0.90).
  - The lid shells take the lips' material: the chosen eye sheets (batch `2026-10-19-alien-face-sheets`, `eb1` and
    `em1`) draw the lids as soft coral domes the colour of the lips, not skin with a coral rim.
  - `tools/blender/alien_parts.py` builds the same look into the eye texture (rest lids, 512 px) and the plain
    materials, for Blender and the three.js page.
  - `face_proof.gd`: the proof under the approved showroom look (`look_presets.json`, Medium: AgX 0.9, the studio sky
    half the ambient and the reflections, key 2.0, fill 0.12, rim 0.3, SSAO): first test against S5 for all four
    eye/mouth combinations, the eyes close, blink, the twelve mouth pieces, the hues and a tuning grid. Run it like
    `proof.gd` (no audio).
- **The mouths from 2D (step S6):** `tools/blender/alien_mouths.py` rebuilds both mouth designs' six pieces by
  measuring their GPT talk-shape sheets (per pixel column the lip edges, the opening, tongue and teeth; method in its
  docstring) on the assembled character, and writes the GLB again. The overbite's two teeth are now inside each
  overbite piece (none in M), so `mouth_overbite_teeth` is gone; `alien.gd` still shows it with the overbite pieces when an older GLB has it.
  The same script cuts the six panels' mouths into a 3 x 2 atlas (`mouth_flip_<design>.png`, alpha blended) and adds
  one face shell per shape, `mouthflip_<design>_<shape>`: the flipbook test. `alien.gd`'s `set_mouth_mode("3d" |
  "flip")` picks which the talk driver shows. `mouths.gd` is its off-screen proof (window 448 x 300): each shape as the
  sheet's panel, the 3D piece and the flip shell at the same orthographic framing, both at 35 degrees, and both
  talking side by side.
  - The head is rigid and its lower face shorter and narrower than the sheets' (their jaw drops and cheeks stretch in
    A, E and O), so the script squeezes a shape below the seam to stay above the chin (`CHIN_Z`) and in x to stay
    within `FACE_FILL` of the face: the open shapes are flatter and narrower than their panels.
- **The second test (step S7):** two bodies from one cage, `tools/blender/alien_cage.py` (a few hundred quads fitted
  to u1 by measurement, Catmull-Clark level 2; method in its docstring): **cage** (no `--target`) and **wrap**
  (`--target <b3d1.glb>`: the same cage shrink-wrapped onto the Meshy faceless body shape, used as a target only).
  In S7 both kept S1c's hands at a standard wrist ring; since S8 the hands are built in the cage (below), and
  4 digits (three fingers and a thumb) and 3-toe paddles stay. The pipeline, all headless Blender: `alien_parts.py` (head and face parts) → `alien_cage.py` (body) →
  `alien_assemble.py` (weld, masks, sockets, GLB) → `alien_mouths.py` (the S6 mouths on the assembled character, the
  final GLB with `character.json`). `alien_cage_review.py` renders the review sheets that put u1, the first test and the
  new bodies side by side (turntables, silhouettes, Walk, feet, welds). What S7 put into Blender, so the GLB (and three.js) shows what Godot shows:
  - the lid shells in the lips' material with a **rolled rim** (`alien_parts_geom.lid_shell(bead=...)`, `LID_BEAD`);
  - the eyeballs turned 11.5 degrees inward in the GLB (`alien_assemble.EYE_AIM_IN`; `alien.gd` sets the same
    rotation absolutely, so nothing doubles);
  - a fuller lower face: `alien_parts.CHIN_SCULPT` moves the chin 15 mm down and 13 mm forward (a smooth local
    sculpt, no jaw bone; it fades out under the mouth line and before the neck), and `alien_mouths.CHIN_Z` follows,
    so A, E and O lost most of their squeeze;
  - smooth lips: the open rings keep only the low Fourier harmonics of their path and width, the skin points and
    normals under every lip are smoothed (the decimated head's facets rippled them), and a closed mouth's lip ends
    meet and tuck into the skin (`CORNER`).
  - `second_test.gd`: the off-screen proof of the first test and both bodies side by side under the showroom look
    (`face_proof.gd`'s stage): turntables at 3 m and 1 m, Idle and Walk, the Walk's feet from the side, every eye
    and mouth combination at 0.6 m, crests, blink, the twelve mouth pieces front and three-quarter, the hues. Spec
    `{"scenes": {"first", "cage", "wrap"}, "out", "hdri"}`.
  - **For three.js:** the GLB's lids, lips, cup, teeth and tongue are plain Principled materials that look as in
    Godot. The page must add (1) the hue shader on the material named `alien_hue` (a plain teal stand-in): the hue
    and its light tint mixed by `TEXCOORD_1.x`, the accent by **`1 - TEXCOORD_1.y`** (the V flip above); (2) the eye
    look: the GLB's eyeballs carry a 512 px texture drawn at the rest lids (`alien_eye_<design>`), so the lid shadow
    on the white does not follow a blink and the catch light is painted; Godot's `alien_eye.gdshader` computes both.
- **The polish step (S8):** the engineer chose the **cage** body (the wrap stays an option only).
  - **Hands in the cage:** `alien_cage.py` continues the arm past the wrist into `HAND`'s rings (rotated octagons, so
    the knuckle ring's end splits into three quads) and extrudes the Index, Middle and Ring fingers and the thumb as
    square tubes along the contract's hand bones (`tube()`, `FINGER_RINGS`, `THUMB_RINGS`: a loop either side of every
    knuckle, a smaller ring and a cap at the tip). No S1c or Quaternius hand mesh is left, and `wrist_ring.json` is no
    longer written. The hand's weights are set per cage loop and **interpolated by the subdivision** (vertex groups on
    the cage object; the Mirror modifier flips `Left*` to `Right*`); the rest of the body keeps S1c's transferred
    weights, scaled by what the hand's leave. The deform layer must exist before the first `bm.verts.new`: adding it
    later frees every `BMVert` reference.
  - **Neck:** `alien_parts.NECK_DROP` (22 mm) seats the head lower on the unchanged ring (`neck_ring.json` did not
    move), `fill_neck` fills the Meshy stalk toward the ring's size (`NECK_FILL`), the Neck weight reaches
    `NECK_BLEND` up the stalk, and `smooth_collar` relaxes the weld band. `CHIN_SCULPT` goes 20 mm forward.
  - **Mouths:** `alien_mouths.SHAPE_SCALE` (S8: A 0.80, E 0.88, O 0.94; S8b: A 0.77, E 0.82; S9: A 0.72) shrinks the open shapes, which were measured to
    the sheets' wider faces; `--parts-report` takes `CHIN_Z` from the parts' sculpted chin.
  - `alien_cage_review.py --detail <character.blend>` renders the left hand at 0.5 m (rest, a fist, a relaxed curl,
    Walk, Talk, Idle) and the neck from the side and back (rest, Idle, turned, nodding) as `hands_<tag>.png` and
    `neck_<tag>.png`. `second_test.gd` takes `"order"` from its spec (S8: `["s7", "s8"]`); `alien.gd` has
    `face_material()` and `face_surface_counts()` for the proofs.
- **S8b, the collar and the hand:**
  - **The neck ring has 48 vertices** in the build: `alien_parts_geom.densify_ring` doubles S1's 24-vertex
    `neck_ring.json` (`loop` on its exact ellipse, `loop_below` by four-point midpoints) when `alien_parts.py` and
    `alien_cage.py` load it, and `alien_cage.py` writes the 48-vertex ring into its `--out`, which the assembler reads.
    The head's loft and the body's subdivided end now meet one to one with plain quads. S1's 48-to-24 triangle zip
    (alternating triangles and quads) was the pleated collar. S1's file itself is unchanged.
  - The assembler **fairs the neck** across the weld (`alien_assemble.NECK_FAIR`, replacing `NECK_SMOOTH`): each
    vertex's radius from the ring's axis, in ellipse units, becomes a Gaussian average by angle (20 degrees) and
    height (6 mm), full from z 1.36 to 1.418 m and easing out by 1.345 and 1.445; the jaw (radius over 1.22) is left
    alone. `weld.neck_fair` in the build report gives the ripple in the full zone (S8b: 2.24 mm before, 0.78 after).
  - **The hand:** each finger ring's place along its bones is pulled toward the knuckle by `FINGER_K` (0.82), so the
    mesh is shorter than the bones (the skeleton and clips are unchanged); the fingers thicker (`FINGER_R`) with
    softer distal weights (the tip rings partly on the Intermediate bone, so the tip does not fold when the distal
    pivot lies beyond the mesh); the palm wider. The thumb leaves the palm's front side quad as a mound and follows a
    curve out and forward (`THUMB_OUT`, `THUMB_LEN`, `THUMB_DIR`), off its bones' downward line; its root ring is
    flattened to the quad's height (`tube()` takes a per-axis scale). `cage.json` lists `hand_folds_over_60` with
    their places. The review's fist (`alien_cage_review.curl`) swings the thumb about the hand's long axis.
  - **Leftovers:** `alien_face.py` holds the face constants (materials, visemes, eye aim, blink), read by
    `alien_parts.py` and `alien_assemble.py`; `tools/tests/test_alien_face_constants.py` checks `alien.gd`'s copies.
    `alien_mouths.RING_SIDE` shrinks an open ring's lift and width where the skin turns away from the front, A and E
    are narrower (`SHAPE_SCALE` 0.77, 0.82), and `TONGUE_SHAPE` makes the tongue narrower, domed and grooved. A fourth
    small toe ring rounds the tips (`TOE`); `BELLY_HALF_W` is u1's wider oval with a softer edge; `CHIN_SCULPT` 26 mm.
  - `second_test.gd` draws `faces.png` for every character of its order (it had matched only `first` and `cage`, so
    an S8 order made no image and the sheet failed with `Out of bounds get index '0'`), refuses an empty sheet, and
    adds `neck_hands.png`: the neck at 0.5 m from the side, back and three-quarter back in Idle and Talk, and the left
    hand in Idle and Walk, one block per character.
- **S9, the quality pass** (the target: the GPT paintover `rf2` of batch `2026-10-19-alien-release-look`, drawn over
  S8b's Godot render at the `hero_face_34` framing):
  - **The crest** (`alien_parts.crest_blade`, `CREST_BLADE`): the Meshy horn, which curled forward and to one side,
    is gone; the skull is cut below it and one back-swept blade grows out of it: sections along a Bezier spine, below
    the cut the skull's own (rays), above it the skull's outline at the cut scaled by a width and a depth taper and
    blended in from the skull's slope, so the forehead and the back of the head run on into the blade. A voxel union
    (0.004 Meshy units), a fillet, a Taubin relax, then everything below the crown is projected back onto the Meshy
    surface (the face is exact). The crown above the eyes is lowered (`crown_k` 0.8: rf2's head is shorter above the
    eyes). The crest's coral tip is gone (all hue). Tried and dropped: an elliptic blade on a cut dome (a ledge at
    the cut), the skull's section blended into the ellipse (a waist or a forehead ridge). The head is decimated to
    `TRIS` 22,000 (S8b: 10,000; the decimation's mean deviation 0.03 mm, max 1.6 mm).
  - **The surface** (`alien_hue.gdshader`, every term a uniform set from `alien.gd`'s `SKIN`): the hue deepens
    (`deep_mul`, darker and bluer) toward the top of the head (`deep_top`, by model-space height) and the back
    (`deep_back`, by the model-space normal) away from the light mask; the pale tint warms toward the face
    (`face_warm`); baked AO from the vertex colour (`ao_albedo`, `ao_light`); a model-space value-noise micro normal
    (`grain`, 500 per m, faded out from 0.8 to 2.5 m so it never shimmers far away; `alien_grain.gdshaderinc`);
    screen-space SSS (`sss`); a fresnel edge glow toward the pale tint (`rim_glow`). The teal is deeper and bluer
    (sRGB 0.11, 0.48, 0.51; pale 0.86, 0.92, 0.81), sampled against rf2. The masks are softer: the face mask's upper
    edge is higher between the eyes and fades over 6 cm (`alien_parts.MASK_FACE`), the belly's edge over 4 cm
    (`BELLY_SOFT`), the knuckle spots smaller and on the back of the hand only (`KNUCKLE["dorsal"]`, by the T-pose
    normal).
  - **Baked AO** (`tools/blender/alien_ao.py`, a step after `alien_mouths.py`): Cycles bakes AO (6 cm, 96 samples)
    into a float colour attribute `ao` on `Body` in the rest pose with the default face shown (bored rest lids, frog
    rest; other parts hidden), lifted by a floor of 0.18 and smoothed once; exported as glTF `COLOR_0`
    (`export_vertex_color="ACTIVE"`). The baked face is the default one: other eyes and mouths get the same skin AO.
  - **Lips and lid domes** take `alien_lip.gdshader` (S5's colour, roughness and specular, both sides, wrapped
    diffuse) with a soft clear coat (`LIP_LOOK` `sheen`) and a fainter grain; the lip colour is rf2's warmer coral
    (0.82, 0.44, 0.37). The bored eye's catch light sits below the rest lid's edge and is crisper (`EYE_LOOK`).
  - `hero_shots.gd`: the hero stills, `beside.png` (render | target) and `grid_<name>.png`, a tuning grid of shader
    variants (`"variants"`: per-variant `skin`, `lip`, `eye` uniforms and `hue`) after the target, with an optional
    plain backdrop like the paintover's (`"bg"`).
  - **For three.js** (beyond S7's list): the page's hue shader must (1) multiply the albedo by `mix(1, COLOR_0.r,
    0.5)` (`ao_albedo`; a plain material with vertex colours already multiplies it fully), (2) add the gradient: `c =
    mix(hue, hue * (0.55, 0.72, 0.78), deep)` before the pale mix, with `deep = clamp(0.6 * smoothstep(1.50, 1.85, y)
    + 1.0 * smoothstep(-0.3, 0.9, -n.z) * smoothstep(1.0, 1.4, y), 0, 1) * (1 - light)` in model space (y up, the
    character facing +z), and the pale tint times `mix(1, (1.06, 1.0, 0.90), 0.6 * smoothstep(1.38, 1.50, y))`; (3)
    the grain: the same value noise (`alien_grain.gdshaderinc`) on `position * 500` perturbing the normal by 0.12,
    faded out from 0.8 to 2.5 m; (4) a fresnel emission `mix(c, pale, 0.5) * (1 - n.v)^3 * 0.3`; (5) the lips' clear
    coat 0.08 at roughness 0.7; (6) Godot's own rim (`rim_value` 0.2, tinted 0.6 toward the albedo; 0.6 tinted 0.3 since light D's grid,
    below) and screen-space
    subsurface (`sss` 0.3) have no three.js equivalent: a wrapped diffuse comes closest. The light mask
    (`TEXCOORD_1`) and the AO (`COLOR_0`) are baked, so S9c's throat panel and jaw lift need nothing on the page.
- **S9b, the neck and the rest pose:**
  - **The neck** (`tools/blender/alien_neck.py`, run by `alien_assemble.py` after the weld): the engineer found S9's
    neck crooked. Measured: per angle around the ring's axis the radius had a plateau below the weld and a second
    fast drop above it (a pinch and a step at the nape), the throat dipped 4 mm at the weld, the Head bone held 0.34
    of the weld ring and the shoulders up to 0.88 of the neck's sides, so Idle, turns and nods bent the weld band
    into a lump. `loft()` replaces the radius between `LOW_Z` (the shoulders) and `TOP_Z` (under the jaw, 1.418 m at
    the front, to the nape, 1.444 m at the back) by a monotone cubic Hermite through both anchors' radius and slope
    (Fritsch-Carlson limits: never below its ends, so no pinch), vertices moving radially only (the ring stays one
    ring; `neck_ring.json` unchanged). `column_weights()` makes the column's weights a smooth field of height: the
    lower bones fade out over 1.318-1.372 m, the Head fades in from 3 cm below to 2.2 cm above the upper anchor, the
    Neck takes the rest (now up to 1.0), then six neighbour-average passes. `neck_shots.gd` judges it: before |
    after | references at 0.5 m (`beside.png`), seven poses (rest, Walk, turns of 40 degrees, nods of 25 down and 20
    up, spread 35/65 over Neck and Head) in profile and the three-quarter back (`motion.png`), 1 m views (`far.png`).
  - **The rest pose for the skin shader:** in Godot `VERTEX` and `NORMAL` in `vertex()` are already skinned, so S9's
    gradient and grain swam in motion. `alien_ao.py` writes the rest position and normal z in two UV layers,
    `rest_xy` and `rest_zn` (glTF axes; `TEXCOORD_2` = (x, y), `TEXCOORD_3` = (z, normal z + 2), V stored flipped for
    the exporter); Godot imports `TEXCOORD_2`/`TEXCOORD_3` as `CUSTOM0` (RGBA float, checked headless by
    `alien/rest_check.gd`: equal to the rest `VERTEX` within 3e-8 m). `alien_hue.gdshader` reads them when
    `CUSTOM0.w > 0.5` and falls back to `VERTEX` for a part without them. Proof: `neck_shots.gd`'s `swim.png` (the
    upper arm in two Walk frames, the camera in the arm bone's frame, the grain exaggerated): the fine pattern's
    correlation between the frames is 0.02 for S9 and 0.49 for S9b (the rest is the light's change). three.js needs
    none of this: its `position` attribute is the rest pose (skinning comes after `begin_vertex`).
- **S9c, the neck's shape and its pale front:** in profile S9b's neck was still a cone (68 mm behind the ring's axis
  at the shoulders, 35 mm at the nape); rf2 and u1 have a longer column with near-parallel front and back lines.
  - `alien_neck.column()` (after `loft()`) re-lofts each angle through a shape-preserving cubic (PCHIP: no overshoot,
    a zero slope where the nape turns) through four points: the shoulders' surface (`COL_LOW`, with its slope), the
    column's foot (`COL_FOOT`, back 1.36 m) and head, and the skull or the jaw (the first height where the surface
    stands `COL_JOIN` out of the column, with its slope). `COL_R` holds the column's radius per angle (the back 46.5
    to 45 mm, the sides 48 to 46 mm); the front keeps S9b's straight throat (the column fades in over 25 to 60
    degrees). Measured on the result: the back holds 45.0 to 46.6 mm from 1.36 to 1.48 m (S9b: 55 to 35), the sides
    46 to 50 mm from 1.37 to 1.46 m, at most 11.2 mm moved (9.8 mm outward at the nape). The weights are S9b's.
  - `alien_neck.throat_panel()` lightens the light mask (`masks` u) over the front half of the neck: by angle around
    the axis (pale to 88 degrees, soft by 14), from the belly panel (1.30 to 1.345 m) up to the jaw (the top lower at
    the side, so it ends at the jaw's corner), plus the jaw's underside (a downward normal, within 55 to 82 degrees,
    so none shows from behind); max with the old mask, then five neighbour passes. The edge runs down the side of the
    neck, and the throat runs on into the pale chin.
  - `alien_ao.py`'s `JAW_LIFT` lifts the baked AO by 0.7 toward 1 over the front of the neck and the jaw's underside
    (mean 0.915 to 0.967): S9's grey band under the jaw goes.
  - Test: `tools/tests/test_alien_neck.py` (the cubic's no-overshoot and the column, with stub Blender modules).
- **S9d, the pale panel's edge, the single-sided skin and the lighting question:**
  - S9c's panel in profile had a bulging top edge behind the jaw (its jaw term followed the voxel head's normals), a
    pale wedge at the jaw's corner from behind, and at the shoulders it met the belly panel's narrow x half width
    (about 15 % of the chest's depth in profile) with a step. `alien_neck.throat_panel()` is now a cut in profile:
    pale in front of one line `y_e(z)` (`panel_line()`): the front `PANEL["depth"]` (0.40) of the trunk's depth (its
    front and back at x = 0, measured per centimetre on the mesh) up the chest, the ring's axis down the side of the
    neck, and under the jaw a shape-preserving cubic up to the head mask's own edge under the eye (y -0.026 at z
    1.535), so the line runs from the neck's side diagonally up to the cheek, as in u1's side view. A cap on |x|
    (`PANEL["cap"]`, 0.115 m on the chest, in to 0.068 at the neck's foot) keeps teal sides in front view and teal
    shoulders; the arms and hands (their weights) stay out. It only lightens; five neighbour passes inside it. The cap
    was chosen on a variant grid (0.100, 0.115, 0.130 m; `alien_assemble.py --panel JSON` merges a variant's settings
    into `PANEL`). In the Idle pose the arm hides the chest's side in profile, so the cap sets the front view and the
    depth the trapezius and the neck. Test: `test_alien_neck.py` (`panel_line()`: one line, no step, never moving
    back under the jaw).
  - The `Body` material is exported single-sided (`use_backface_culling`, glTF `doubleSided` false): three.js drew the
    back faces of surfaces inside the skin as pale blotches (the manager's finding). Godot's `alien_hue.gdshader`
    culls back faces already. `alien_assemble.drop_interior()` deletes the faces above z 1.40 from which no ray of
    48 over the outward hemisphere leaves the skin; S9d found one (0.01 cm2) at the head. On the body the same test
    took real skin in the tight folds of the armpits and the crotch, so it stays off there.
  - `neck_shots.gd` spec `"torso"`: the upper body at 1.5 m from the front, three-quarter, side and three-quarter
    back, beside u1's views. `hero_shots.gd` spec `"lights"`: the stage's directional lights replaced per variant,
    face and body shots, `light_sheet.png` (the lighting question; `look_presets.json` stays as approved). The
    engineer chose D (2026-10-19; "Light D" above): the stage now takes its lights from `look_presets.json`; a tuning
    variant may carry its own `lights`, and spec `grid_zoom` adds `zoom_<name>.png`, one part of every shot.
- **M2, the texture UV and the detail normal map** (the modern-look plan: a texture set instead of a smooth
  subdivision cage). Three steps after `alien_ao.py`, all headless Blender; the pure parts and settings are in
  `alien_detail_geom.py` (test `tools/tests/test_alien_detail_geom.py`):
  - `alien_uv.py --character <ao/build/alien_character.blend> --out <uv>` writes a texture UV into `Body`'s first UV
    layer `UVMap`, so it is **glTF `TEXCOORD_0`**. It held nothing used before. `masks` (TEXCOORD_1), `COLOR_0` and
    `rest_xy`/`rest_zn` (TEXCOORD_2/3) are untouched.
    - Islands come from the dominant bone's part (`part_of_bone`), with neighbour-majority passes and strays merged.
    - The torso is split front and back down the flanks, under the arms.
    - Each hand is split into palm and back by its smoothed T-pose normal. A raw normal left folding flaps: 26
      overlapping faces.
    - Each foot loses its sole.
    - Tube parts get one lengthwise cut where the angle around their axis wraps: the head up the nape and along the
      crest blade's back edge, the arms underneath, the legs on the inner side, the foot up the heel.
    - Then a minimum-stretch unwrap, the same texel density per island times `DENSITY` (head 1.75, hands 1.45), and
      a pack with a 24 px margin at 4K.
    - Measured (`uv/build_report.json`): 15 islands, 0 overlapping or flipped faces, stretch p5-p95 within 0.78-1.18
      (head) and 0.97-1.03 (limbs). At 4K: head 38 px/cm, hands 31.5, torso and arms 21.7, legs 19.6.
    - An angle-based unwrap crushed the feet (stretch 0.03) and folded the thumbs.
  - `alien_detail.py --stage high` subdivides a copy (`Body_high`, rest pose) three times to 1.9 million quads. Then
    it moves the copy along its normals by `CREASES`: Ricker profiles, a valley with shoulders and zero net volume,
    each at most `MAX_DISP_MM`.
    - The creases: finger joints (at the mesh's own joints, `FINGER_K`), wrists, elbows, knees, armpits, the neck, a
      fold above and below each eye socket, a groove under the rest mouth and round its corners, the philtrum,
      nasolabial lines, the
      belly's centre line.
    - Each crease is placed by bone planes, rings or curves in the rest pose. It is faded by side (normal) and by
      bone-weight attributes written before subdividing.
    - The fine grain (`GRAIN`: Voronoi pores and a noise peel, the face stronger by the Head weight) is a Bump on the
      copy's material. Cycles bakes shading normals, so it reaches the map without polygons.
    - The copy also stores its mean curvature as the colour `curv`.
  - `--stage bake` uses Cycles, selected to active onto `UVMap` (cage 2 mm, ray 4 mm, 16 px extend margin). It
    writes `normal.png` (4K tangent space, OpenGL +Y), and at 2K `ao.png` (5 cm, with the default face),
    `curvature.png` (0.5 flat) and `thickness.png` (AO from inside with the copy's normals flipped: white thick, dark
    thin within 6 cm). Each map gets a `_1k` preview.
  - `--stage export` puts `normal.png` on `alien_hue` through a Normal Map node, so glTF gets `normalTexture`
    (texCoord 0), with tangents exported.
  - `alien_detail_review.py` renders the review: the same Eevee skin with and without the normal map beside rf2,
    as `face.png`, `body.png` and `close.png`.
  - The shaders do not sample the map yet: that is M5 (Godot) and the three.js page.
- **M3a, the authored 4K texture set** (`tools/blender/alien_texture.py`; the formulas and settings in
  `alien_texture_geom.py`, test `tools/tests/test_alien_texture_geom.py`; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M3a/`). Four headless stages, each reading the one before:
  - `--stage cage` (from M2's `high/alien_high.blend`): the explicit bake cage of PR #231's minor 6. Body's copy,
    each vertex moved out along its normal by `cage_offset()`: 40 % of the distance to the low mesh's next surface
    along that normal, within 0.3 to 2 mm (M2's uniform 2 mm started rays inside the next finger in the webs). It
    rebakes `bake/normal.png` (4K) and `ao.png` (2K) through it and copies M2's curvature and thickness. Measured
    (`bake/cage_report.json`, `cage_compare.png`): texels tilted over 60 degrees 11,128 to 3,725; only 9,135 texels
    changed by over 0.05, all at the webs; the AO's mean is unchanged. A three-stroke mark at each hand's thumb root
    remains (a low-mesh fold, not a ray miss); it does not show in the renders.
  - `--stage fields` (from M2's `export/alien_character.blend`): per-vertex fields of the rest pose (the T-zone, the
    mouth's rim, the flush round the mouth and cheeks, the warm thin parts: fingers, crest, neck; the S9 shader's
    `deep` gradient and face warmth; the light mask smoothed over the head and neck by `smooth_light()`, which removes
    the pale specks along the throat panel's edge behind the jaw), three noises in rest object space (blotch 11 cm,
    hue 29 cm, fine 3 mm), the masks' accent and M2's maps, baked by Cycles EMIT onto `UVMap` at 4K as five RGB
    fields (`fields/*.npy`, float16), plus `pore.npy`, the pores of the normal map (its divergence).
  - `--stage compose`: `textures/albedo.png` (sRGB), `orm.png` (glTF's packing: R occlusion = the AO, G roughness,
    B metallic 0) and `sss.png` (2K grey, white = thin: the subsurface mask for the Godot shader, M5), each with a
    `_1k` preview; the UV gaps are filled by push-pull, so far mip levels never bleed black. `--variants FILE --vout
    DIR` (FILE: a JSON file, an object of name: settings, each merged over the settings) writes a tuning grid's
    variants instead, each at `--size` into `DIR/<name>/` (the grids `g1` to `g4` were composed at `--size 2048`).
    - Albedo (linear, `albedo()`): the kit's flat look first (teal and pale by the light mask, the `deep` gradient,
      the face warmth, the accent with its edge narrowed to smoothstep 0.2 to 0.8, so no grey band round the knuckle
      spots), then a warm/cool hue drift (6 %) and soft blotches (5 %), the curvature cavity (concave up to 20 %
      darker and bluer, convex up to 10 % lighter in its own hue; a mix toward the pale washed the thin fingers out
      to grey), the thin parts' warmth (a multiply toward more red and green, so the teal stays saturated), the flush
      (10 %, on the pale), half the AO.
    - Roughness (`roughness()`): 0.52, convex down to 0.38, creases up 0.06, the T-zone -0.06, the mouth's rim -0.16,
      a fine noise of 0.015.
    - Tuned on grids (`M3a/variants/g1` to `g4`, rf2 first): stronger cavity and pore darkening drew M2's creases as
      dark lines (an older, wrinkled face); roughness 0.55 read matte beside rf2's sheen, 0.48 with a T-zone of -0.14
      laid a wet patch on the forehead, and a pore-scale roughness noise of 0.05 made the highlight sparkle.
  - `--stage export`: the other meshes on `alien_hue` (the alternative crests `crest_antennae`, `crest_fins`) move
    to an untextured copy, `alien_hue_part`, since their UVs are not Body's (`alien.gd`'s `HUE_MATERIALS` swaps both
    for the shader). The copy's image and Normal Map nodes are removed (`strip_images()`): kept, M2's 4K normal map
    went into the GLB a second time (14.3 MB) as the crests' `normalTexture`, sampled through their own UVs. `alien_hue` takes the set on `UVMap` (Base Color from the albedo; Separate Color of the ORM
    into Roughness and Metallic, and R into the `glTF Material Output` group's Occlusion), so the GLB has
    `baseColorTexture`, `metallicRoughnessTexture` and `occlusionTexture` on one ORM image, and `normalTexture`.
    `export/alien_character.glb` (34.9 MB: the normal map 16.1, the ORM 7.7, the albedo 3.5, the two mouth atlases
    0.6) with its `.blend`, `character.json` (`note_m3a_textures`), the mouth atlases and `alien_skin_sss.png`. The
    stage then reads the GLB's JSON and fails when any material but `alien_hue` and the flipbook mouths
    (`alien_mouth_flip_*`) references an image (`alien_texture_geom.unexpected_images()`).
  - `COLOR_0` (the vertex AO) is still exported because `alien_hue.gdshader` reads it; a plain glTF viewer multiplies
    it into the albedo on top of the half AO already in it. The albedo is the teal hue's only: the other hues need
    M5's shader to tint (or one albedo per hue).
  - `alien_texture_review.py` renders the review under light D in Blender (Eevee, AgX): the four suns of
    `look_presets.json` turned into Blender's axes, each at 2.5 times its Godot energy (Lambert's 1 / pi; at 1 the
    face read grey, at pi the teal washed out), M2's look beside M3a's (`face.png`, `close.png`, `body.png` in
    `M3a/sheets/`); `--grid DIR --names a,b --shots ...` renders a tuning grid's variants.
  - To rebuild: each stage in background Blender through the runner, `tools/runner/blender.py`'s
    `run_script("alien_texture.py", ["--stage", <cage|fields|compose|export>, "--out", <M3a>, "--m2", <M2>, ...])`
    (`--m2` is required; `export` also takes `--kit <the kit's export folder>`), in that order (about 90 s, 32 s,
    15 s and 10 s: start each in the background with its log under `tools/out/`), then `alien_texture_review.py`
    the same way; the normal map changes only with the high copy (M2's `--stage high`).

## Findings for later tasks

- **Toe bones (art #25):** assembled characters have 64 bones since art #25 (`Toe.L`, `Toe.R`). The export and
  `godot-check` pass unchanged (2026-10-03, m1_rex and w1_ivy: one skin of 64 joints, 64 binds per part, every check
  ok); the 24 pack animations still hold 62 tracks each (1488 in all): the toes have no track and rest under the feet.

- **Loop modes**: Godot imports the pack's 24 animations with loop_mode NONE (their glTF names carry no loop suffix):
  in the game the idles, Walk and Run would play once and stop. The game's import sets their loop mode (per-animation
  `settings/loop_mode` in `_subresources`) or the names get a loop suffix: the contract v2 decides. An animation set
  (art #33, `docs/animations.md`) already names its loops `<Name>_Loop`: Godot 4.7.2 imports them LINEAR as `<Name>`
  (measured), and `godot-check` asserts it (`loop_suffix`).
- **Open cycles**: `Run`, `Run_Left` and `Run_Right` (both body types) end one frame before their first pose comes
  round; looped at the length of their keys they skip a step at every repeat. Their loop length in the game is
  (last frame + 1) / 24 s: 0.833 s for the men, 1.042 s for the women.
- **The game's import options**: the AnimationPlayer's `optimizer/enabled = false` (above), and `animation/fps` at the
  rate the GLB was baked at, which its `.export.json` records: 24 for the pack's own clips, **30 for an animation set**
  (art #33). `godot-check`, `frames` and `--humanoid` import a GLB at that rate (`_godot.import_params`). Godot
  resamples every track at `animation/fps`: a 30 fps set imported at 24 would lose up to about 20 degrees on the
  fastest joints (the jump's take-off, estimated from the GLB's keys, art #33's review).

- **The women's clips are 25 % longer** than the men's of the same name, in the pack's own files (Walk 1.67 s against
  1.33 s, Run 1.00 s against 0.79 s, Idle 2.08 s against 1.67 s): the women walk and run more slowly at the same game
  speed (art #20, the animations).
- **Materials**: the pack's materials are metallic 0.4, roughness 0.42 (from its FBX conversion); under the game's
  lights flat faces will glint. The palette step should set its own values.
- **The women's Idle and Wave stance**: one foot turned inward, identical in Blender and Godot: the pack's pose.
- **Godot gotchas**: in a `-s` SceneTree script `root.get_viewport()` is null at start (use `root`, a Window, as the
  viewport); a script error inside a coroutine does not quit, so every script has a watchdog and validates its input
  (a relative spec path, read as nothing, left the window open until the watchdog); `bake_mesh_from_current_skeleton_pose()` fails headless.
