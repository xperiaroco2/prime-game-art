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

No preset uses TAA. TAA on top of High's and Ultra's MSAA 4x is a proposal, not approved and not in `PRESETS` or
`look_presets.json`: see "The alien parts kit", M5, "TAA (a proposal)".

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

## The alien pilot's static heads (`godot/alien/alien_static*`, art #196)
One material for a whole static head (Meshy's sculpt with its painted eyes; `docs/pipeline.md`, "The roster
pilot's static premium heads"):
- `alien_static.gdshader`: `albedo_tex` (sRGB), `normal_tex`, `mask_tex` (linear: R the skin tint mask, G roughness,
  B the subsurface and sheen weight), `diffuse_burley` (Test D's finding: the lambert wrap flattened the shading),
  `sss_mode_skin`, the sheen as Godot's rim. **The skin colour:** `skin_color` against `base_skin` (the albedo's own
  skin teal, the GLB's `base_skin_srgb` extra): every masked texel's hue is turned by the two colours' hue difference
  and its saturation and value scaled by their ratios, so the shade, the light and the pale front's two-tone stay;
  `skin_color == base_skin` is the identity. Hue turning moves the pale front with it (mint under a yellow skin turns
  a pale pink cream).
- `alien_static.gd` (`preload`, no class cache in a `-s` script): `apply(root, mask, base_skin)` swaps every surface
  material whose name ends in `_static_skin` for the ShaderMaterial (keeping the imported albedo and normal textures)
  and returns the materials; `set_skin(mats, color)`; `PALETTE`, the curated skin colours after the build's teal.
  The mask PNG travels beside the GLB (`<head>_mask.png`); the proof loads it with `Image.load_from_file`.
- `static_shots.gd`: the review sheets in an off-screen window under the showroom's ladder step 6 (the studio HDRI,
  AgX 0.9, key 2.0 with 1.5 degree soft shadows, fill 0.12, rim 0.3, SSAO, SSS medium), plus the tone grid
  (`TONES`: the showroom's AgX 0.9, AgX 0.65, AgX 0.65 with the environment's saturation 1.35, linear 0.6) measured
  against the 2D front (median teal and pale skin, `colour.json`); the closest is the pick for `views_pick.png` and
  `colours.png`.
- **Round 2, "alive" (static_v2, 2026-10-22):** the engineer read the #288 heads as vinyl toys or statues. The shader
  gained levers, each off at its default (in round 2 the defaults were still the #288 material; since round 3 they are
  not, see round 5 below, and the GLB's own material carries clearcoat, sheen and specular extensions since round
  3): `detail_tex` (`<head>_detail.png`, linear RGBA from the dense original: R the cavity, G the thinness,
  B the flush region of lips and lids, A the eyes' limbal ring; `apply(root, mask, base_skin, detail)`),
  `transmission` (`BACKLIGHT` on the thin parts in the skin's own colour, saturated), `micro_strength`,
  `micro_scale`, `rough_breakup` (a fine grain: a bump from 3D value noise in object space, faded with distance and
  with the pixel footprint, so it never aliases), `cavity` and `flush` (creases deeper and more saturated, never
  grey; lips and lids a little flushed), `fuzz` (a lighter, more saturated sheen at grazing angles), `eye_coat`,
  `eye_under_rough`, `limbal` (a wet clear coat over a softer iris, the limbal ring darker). The normal map is applied
  by hand (Godot's own `NORMAL_MAP` maths) so the grain can bend the result. `debug_mode` 1, 2, 3: grey with the
  normal map, grey geometry only, the albedo alone: tells a geometry fault from a normal-bake or an albedo-bake fault.
- `static_alive.gd`: review sheets from a JSON job (heads, sheets, rows of cells: head, shader parameters, debug
  mode, tone, a framing by target, yaw and width; optional GPU ms) in an off-screen window, written and run by
  `tools/blender/alien_static_review.py <seams|grid|final|gate>` (`docs/pipeline.md`).
- **Round 3 (static_v3, 2026-10-22):** the alive read moved into the textures (`docs/pipeline.md`), so the shader's
  `cavity`, `flush` and `micro_strength` stay off in the pick. New: `plain_tex` and `alive_mix` (1 = the GLB's albedo;
  0 the albedo without the baked layers, above 1 extrapolated; `apply(root, mask, base_skin, detail, plain)`) for the
  review grid. The pick (`alien_static_review.py` `PICK`) also lowers `specular_level` on the skin.
- **Round 4 (static_v4, 2026-10-22):** the shader and the pick are unchanged; the fixes are in the baked textures
  (`docs/pipeline.md`). The review's middle seams row is round 3 under the same pick.
- **Round 5 (static_v5, 2026-10-22):** round 3 dropped `sss_mode_skin` from the shader's render mode, so its defaults
  are not the #288 material. `alien_static_288.gdshader` is the merged #288 shader kept byte for byte (`7c2bac4`);
  `apply(..., shader)` takes it (`AlienStatic.SHADER_288`), and `static_alive.gd` gives it to a head with
  `"shader": "288"` (no detail or plain texture, no parameters, no debug view). #288's debug-view cells use the
  current shader on a `"grey_only"` head (the debug modes do not depend on the material). A head on the current
  shader without its detail or plain texture is an error (it was a silent white default); each head resets its own
  last parameters.
- **Lively (2026-10-23, the liveliness proof):** the static chameleon looks at a target, turns its head, its crest
  springs and its chest breathes, with no face rig and no cut in the sculpt. `$PYTHON_BIN
  tools/blender/alien_lively_run.py [--no-build] [--seconds 20]` (in the background) writes into
  `<raw>/research/2026-10-22-roster/design/pilot3d/lively/`:
  - `alien_lively_build.py` (headless Blender for numpy and its BVH; the merged GLB's bytes are kept, never
    re-exported): every eye texel gets its 3D point (a UV rasterizer); texels the lids leave open (a ray from outside
    the eye sphere meets an eye triangle first) are pupil, iris (warm, saturated) or sclera; the iris and pupil are
    caps on the build's eye sphere, fitted by least squares on their open edges; the iris colour is a radial profile
    of 8 medians. `chameleon_sclera.png` is the albedo with the painted irises filled from the sclera around them
    (push-pull); the pupil is darker than value 0.12 (0.22 took the iris's dark inner ring). The lid clamp: per eye the gaze offsets that keep the rest's open share of the iris and pupil discs,
    reduced to an ellipse's four limits (`lively.json` `limits_deg`; the chameleon's heavy lids leave no room up).
    The skin (`alien_lively_geom.add_skin`): Chest at the bust's base, Neck and Head through the neck's waist (weights
    by height, the chin and face rigid), Crest1-3 along the crest (weights only in the crest blade).
    `chameleon_lively.glb`: glTF-Validator 0 errors.
  - `alien_static.gdshader` `gaze_on` (0 by default: the merged look untouched): the eye texels from `sclera_tex`
    and a procedural iris (profile, crisp pupil, `limbal_ring`, `catch_light`) on each eye sphere at `gaze_l`/`gaze_r`,
    computed from the skinned vertex position, so the iris rides the head.
  - `alien_lively.gd`: the controller (`step(dt)` advances the skeleton by hand): eyes lead (critically damped at
    9 Hz, clamped by the lids, capped at 25 degrees), the head follows (1.6 Hz; yaw 35, pitch 20, 40 % in Neck), a
    4.4 s breath (the chest's scale, the Neck's inverse so the head keeps its
    size, a 0.6 degree nod). The crest is an under-damped spring (2.2 Hz, damping 0.3) pulled back by the head's
    turn speed, the same as the web port's: a SpringBoneSimulator3D on Crest1-3 under the manual skeleton advance
    showed no measurable swing (0.0 degrees over the whole video) in the first proof.
  - `lively_shots.gd`: `sheet.jpg` (row 1: merged head at rest, lively at rest, with the catch light, a head turn, the
    crest's largest swing; row 2: the eyes alone left, right, up, down, near), `lively.mp4` (20 s, 1280x720, a target
    ball's path), `shots.json`.
  - `web/lively.js`: the browser port (three.js 0.160, `onBeforeCompile` on the GLB's material, the same maths; the
    crest spring included), with `chameleon_lively.glb`, `lively.json`,
    `chameleon_sclera.png` and a test page.

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
  - **The hand:** each finger ring's place along its bones is pulled toward the knuckle by `FINGER_K` (S9: 0.82; M7:
    0.984, never above 1: `--digits` refuses it), so the mesh's joints sit at or before the bones' (the skeleton and
    clips are unchanged); the cage writes its digits into `Body["prime_digits"]`, and `alien_detail.py`'s finger
    joint planes take `FINGER_K` from there (M9); the fingers (`FINGER_R`) with
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
    into a float colour attribute `ao` on `Body` in the rest pose, lifted by a floor of 0.18 and smoothed once;
    exported as glTF `COLOR_0` (`export_vertex_color="ACTIVE"`). S9 baked it with the default face shown; since M7 no
    mouth piece and since M9 no part at all (`SHOWN = ()` here, in `alien_detail.py` and `alien_texture.py`): the
    skin's AO is the Body's own shape, the same under every eye and mouth design, whose shade on the skin is its
    per-design contact channel (M6c).
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
    writes `normal.png` (4K tangent space, OpenGL +Y), and at 2K `ao.png` (5 cm, no part shown since M9),
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
    along that normal, within 0.3 to 2 mm and never past half that distance (M2's uniform 2 mm started rays inside the next finger in the webs). It
    rebakes `bake/normal.png` (4K) and `ao.png` (2K) through it and copies M2's curvature and thickness. Measured
    (`bake/cage_report.json`, `cage_compare.png`): texels tilted over 60 degrees 11,128 to 3,725; only 9,135 texels
    changed by over 0.05, all at the webs; the AO's mean is unchanged. A three-stroke mark at each hand's thumb root
    remains (a low-mesh fold, not a ray miss); it does not show in the renders.
    - The half-gap cap came after the shipped bake (PR #233's review). On Body 2 vertices have a clearance under
      0.6 mm, so 22 offsets change (by at most 0.28 mm, with the smoothing). The rebake through the capped cage
      (`M3a/bake_cage_r2/`) differs from the shipped `bake/` in 217 of 16.8 million normal texels by over 0.05
      (tilted over 60 degrees: 3,629 against 3,725) and in 9 AO texels. The textures and the GLB still use `bake/`;
      the next compose takes the capped bake.
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
    (`--m2` is required; `compose` and `export` need `--set m3a`, `export` also takes `--kit <the kit's export
    folder>`), in that order (about 90 s, 32 s, 15 s and 10 s: start each in the background with its log under
    `tools/out/`), then `alien_texture_review.py` the same way; the normal map changes only with the high copy (M2's
    `--stage high`).
  - `--set m3a|m3c` names the texture set (`alien_texture_geom.SETS`: its settings, `character.json`'s note and the
    images' names); there is no default. `compose` refuses an `--out` whose `textures/settings.json` records other
    settings, and `export` one whose textures were composed with other settings than the set's, unless `--force` (a
    key missing from an older `settings.json` counts as its M3A value). So M3a's recipe can no longer write M3c's
    look into `M3a/`.
- **M3c, the texture set tuned toward rf2** (the same scripts; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M3c/`, M3a's files untouched). Beside rf2 (showroom v26) M3a's face
  read yellow-olive, a dark ring sat round the eye sockets, its roughness of about 0.5 drew M2's pores as a glossy
  orange peel at 0.6 m, and the knee and knuckle spots were crisp coral discs (stickers).
  - `alien_texture_geom.M3A` keeps the shipped M3a settings; `TEX` is M3A with `M3C`'s changes over it (the reasons
    in its comment): the texture's own pale `pale_srgb` (0.81, 0.94, 0.82), mint (green well above red, blue about
    red; the kit's `PALE_SRGB` stays the kit's), the face warmth without its blue cut; the AO lifted to its contact
    shade (`contact_ao()`: ao / 0.55, clipped) fully round the eyes and 0.45 everywhere, the sockets' cavity
    darkening off, 0.4 of the AO in the albedo, and the ORM's R the same lifted AO; roughness 0.66 (convex 0.06
    glossier, no T-zone, the lips' surroundings 0.14 glossier); the accent over the kit's soft edge, blurred
    (`accent_blur` 32 texels at 4K, a normalised three-box blur over the covered texels, `blur()`), full from 0.6 of
    the blurred mask, 0.85 at its peak, its chroma kept 0.6 through the edge (`keep_chroma()`: teal and coral mixed
    half and half are a dusty grey). The teal (`hue_sat` 1.15) and the dome's depth are M3a's.
  - The blur runs in UV space, within each UV island: a spot that a `UVMap` seam cuts (the far knee's) still ends
    hard at the seam. The fix for later is a blur on the mesh, the accent averaged over vertex neighbours in the
    `fields` stage (as `smooth_light()`), with its passes matched to the 32 texels and the spots judged again.
  - The fields gained `socket` (in pass `e`, where M3a had a constant): the skin within 14 mm (`SOCKET_MM`) of each
    eye's parts' box, by the distance to the box (full within 7 mm; an ellipsoid round the box reached less far at
    its corners, the outer lid corners).
  - Chosen on two grids, rf2 in the first column (`M3c/variants/g1`: the pale's hue, the AO, the accent; `g2`: the
    roughness 0.66 against 0.72; `grid.json` names the columns). A cooler pale (blue above red) read cyan, a creamier
    one yellow again; 0.72 read flat and chalky beside rf2's soft sheen; a blur of 24 texels with the full edge erased
    the small knuckle spots, hence the edge remap at 0.6.
  - Rebuild: `--stage fields` with `--bake <M3a/bake_cage_r2>` (the capped cage's bake; `--bake` defaults to
    `<out>/bake`), then `compose --set m3c`, then `export --set m3c` with the same `--bake` (character.json's
    `note_m3c_textures`, the normal image's name). `alien_texture_review.py --before-tex <M3a/textures>
    --before-normal <M3a/bake/normal.png> --labels m3a,m3c` puts M3a on the left of the sheets instead of M2's look;
    its shots gained `near` (the face at 3/4 from 0.6 m, 70 mm) and `knee`. About 30 s, 20 s, 10 s and 10 s.
- **M2b, the sculpt softened toward rf2** (the engineer on v27: "under the neck something like a scar"; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M2b/`, M2/M3a/M3c untouched).
  - The scar: where the jaw's underside folds into the throat, the low mesh (an irregular triangulation) subdivides
    into a crumpled crease in the high copy. The normal map draws it faintly; M3c's cavity tint from the curvature bake
    draws it as a ragged dark double line (`tools/out`'s diagnosis: present with the normal map off, absent on a plain
    clay, so the texture; present in the high copy's own `curv` colour and its clay, so the sculpt). The neck rings
    (`neck_front`, `neck_back`) added stripes beside it in the curvature, the AO and the albedo.
  - `alien_detail_geom.SCULPTS` holds the sculpts (`sculpt(name, extra)`: CREASES, GRAIN, `SOFTEN`, `CURVATURE` with
    changes; an unknown key is an error). `m2` is M2's, unchanged. `m2b`: no neck rings, the brow folds (`lid_fold`)
    0.22 mm deep and 3 mm wide (0.70 and 1.5), softer folds under the eyes and creases under the mouth (the groove
    round the mouth's corners 0.15 mm, was 0.40: at 0.28 it read as a short cut beside the chin), the pores
    0.7 mm across and 0.016 mm deep at 0.45 on the face (1.1, 0.045 and 1.0), the peel 0.022 mm; `soften`: under the
    jaw (the head and neck from 3 mm under the rest mouth to 4 cm under the Neck joint) the high copy relaxed along
    its normals, 300 Laplacian passes weighted by its curvature grown over 24 edges, at most 1.8 mm (the capped cage's
    rays reach 2 mm inside); the curvature colour smoothed 6 passes, and 120 more where `soften` worked.
  - Chosen on two sculpt grids (`M2b/variants/g1`, `g2`, rf2 first; rows face34, `chin` (under the chin at 3/4 from
    below, 0.4 m), `close04` (the face at 3/4 from 0.4 m), `face_close`) with one normal map per variant over M3c's
    texture without its cavity tint (`variants/base`). Relaxing only the curvature's thin band (g1, up to 20 passes)
    moved the fold under 0.5 mm and kept the crumple.
  - Rebuild (each through `tools/runner/blender.py` in the background): `alien_detail.py --stage high --sculpt m2b
    --character <M2/uv/build/alien_character.blend> --out <M2b>`, `--stage bake --cage capped --out <M2b>` (all four
    maps through M3a's capped cage), then `alien_texture.py --stage fields --out <M2b> --m2 <M2> --bake <M2b/bake>`,
    `compose --set m3c --out <M2b> --m2 <M2>`, `export --set m3c ... --kit <M2/export> --bake <M2b/bake>`;
    `alien_texture_review.py ... --tex <M2b/textures> --normal <M2b/bake/normal.png> --before-tex <M3c/textures>
    --before-normal <M3a/bake_cage_r2/normal.png> --labels m3c,m2b` adds `compare.png` (rf2 | M3c | M2b: face34,
    chin, close04, neck_back34, body). A sculpt grid: `alien_detail.py --stage grid --variants <json> --vout <dir>`,
    then `alien_texture_review.py --grid <dir>` (a variant folder with `normal.png` alone swaps only the normal map).
- **M4, the modern eyes** (output under `D:/prime-art-raw/review/char/alien-parts-kit/M4/`). The designs, the lid
  shells and the blink by lid rotation are unchanged; what is new is per pixel in Godot, plus one small strip per lid:
  - `alien_eye.gdshader` (`cornea` 1; 0 keeps S9's painted eye for before/after sheets) draws a **cornea**: a sphere
    through the limbus ring (`limbus_deg`, bored 27, manic 21) rising `bulge` 0.12 radii above the ball. It is
    optical only: the lower lids' inner radius (1.012 r) leaves no room for a mesh bulge, so the ball stays a sphere.
    Per pixel the camera ray (in the ball's model space) meets that sphere, is refracted (`ior` 1.336) and followed to
    the iris plane `iris_depth` 0.05 below the limbus plane: the iris and pupil sit behind the cornea and shift as the
    view turns. Their plane radii are solved (`front_rho`) so that seen along the axis they cover `iris_deg` and
    `pupil_deg` as S9 did. The lights see the cornea's normal at `cornea_normal` (bored 0.4; manic 0.15 with a soft
    edge of 8 degrees: more drew a ring round the dot pupil) and `cornea_roughness` 0.14 (0.03: a hard second dot;
    0.06: a mottled softbox). The **catch light** reflects a view-space light (`catch_dir`, from the viewer's left,
    a little below on the bored eye and above on the manic one) on the full cornea normal; the normal it is compared
    with is 70 % a fixed one (`catch_anchor_deg`: the cornea's normal toward that ball point; `catch_follow` 0.3), so
    it moves a little as the view turns and stays by the pupil in the proof's views (the rim hid a purely view-space
    one at rest). Bored (5, -10): low left by the pupil, just under the rim with the lids at rest; manic (4.5, 4.5):
    up and left, S9's place. The cornea's edge fades over `limbus_soft_deg` inside `limbus_deg` (bored 1, manic 8):
    the iris' soft edge must end before it (`iris_deg + edge_deg <= limbus_deg - limbus_soft_deg`, tested), or the
    white paints over the iris' rim (bored 3 did).
  - The **iris** (bored): fine radial fibres (0.12), a faint lighter ring round the pupil, the darker limbal ring and
    a warm glow in its lower half on the ball's +X side (the viewer's right with the eye facing the camera, across the
    pupil from the catch light), all kept small so the iris still reads as S9's dark brown.
  - The **lid shadow**: S9's broad shading under each lid edge, plus a narrow contact band (`contact_deg` 3.5) that
    also feeds `AO` and dims the specular, clear coat and catch light; both follow the lid edges (`upper_edge_deg`,
    `lower_edge_deg`, set by `alien.gd` from the lid rotations). The contact band starts where the rolled rim stops
    hiding the ball, `upper_reach_deg` and `lower_reach_deg` beyond each edge (`alien.gd` `EYE_LOOK`: bored 4.3 and
    2.0, manic 3.7 and 1.8, `alien_eyes_geom.rim_reach`, tested); at the edge itself it lay under the rim, unseen.
    Its darkness `contact_dark` is 0.3 (0.45 read as a grey band once the band showed). The elevation both shadows
    use is measured in the lids' frame: the ball is turned inward from its lids (`alien.gd` `aim_in_deg`, passed as
    the instance uniform `aim_deg`), and S9's elevation about the ball's own axis, clamped at its side meridian,
    jumped to +-90 degrees there; in a turned view the contact shadow drew that as a crisp line and a dark grey
    wedge between ball and lid (the review's "shelf"; S9's eye, `cornea` 0, keeps its own elevation). The **white** falls toward the warm `shade` where it
    turns from the view (`edge_falloff` 0.2; 0.35 bared the pale socket skin behind the ball's edge in a turned view)
    and has a wet clear coat (`wet` 0.5, roughness 0.3; 0.22 drew a small second glint beside the catch light).
  - The **wet line**: `tools/blender/alien_eyes.py` (pure parts in `alien_eyes_geom.py`, test
    `tools/tests/test_alien_eyes_geom.py`) hangs a strip `eye_<design>_wet_<upper|lower>_<side>` (576 triangles:
    48 x 6 quads; 4 strips, +2,304 triangles per character; material `alien_wet`) under each lid as a child with an
    identity transform, so it turns with the lid: on the ball from `WET["beyond_deg"]` 1.5 beyond the rolled rim's
    reach to the reach (3 segments, v 0 to 0.5), then on under the rim to the lid's edge (3 segments), rising evenly
    to `fill` 0.1 of the way to the lid's inner surface. `alien_wet.gdshader` draws it as a half-transparent glossy
    film on the ball's part, faded at the corners, at the ball's side, out just under the rim (`rim_v` 0.5, the
    rim's reach on every lid: `alien_eyes_geom.rim_v`, tested) and where the view grazes it (`dot(NORMAL, VIEW)`
    0.1 to 0.45). The first M4 strip rose under the rim to `fill` 0.7 of the gap, a wall that a turned view saw as a
    light line on a grey shelf between ball and lid (art PR #235's review; in the proof's grids `wet` `alpha_max` 0
    took the line away, the eye's `edge_falloff` 0 did nothing, and the grey wedge was the contact shadow's
    elevation, above). UV v is flipped by the exporter. `alien.gd` turns its
    shadow off and fades it out as the lid edges close (`WET_OPEN_DEG`, the instance uniform `open`).
  - `alien_eyes.py --kit <M3a/export> --out <M4> --eye-images <S9/parts/export>` also gives the eyeball materials a
    clear coat (glTF `KHR_materials_clearcoat`) and puts the 512 px eye textures back: M3a's GLB had lost them (the
    image files were not beside its .blend), so plain viewers drew white balls. After the export it runs M3a's image
    check (`alien_texture_geom.unexpected_images`; `alien_eye_` is an allowed prefix) and fails on any other material
    with an image. It writes `M4/export/` (GLB 35.1 MB, glTF-Validator 0 errors) with `character.json` (`nodes.eyes.<design>.<side>.wet_upper/wet_lower`,
    `note_m4_eyes`).
  - `eye_shots.gd`: the proof: per design the face at 1.2 m (three-quarter and front) and 0.4 m, a blink strip
    (open, rest, half, closed) and its zoom, the parallax sheet (three yaws, S9's eye above M4's), before | after |
    target sheets from an earlier run's folder (`"before"`; `"eye": {"cornea": 0}` renders S9's eye from the same
    script), and a tuning grid of eye and wet uniforms (`"grid_zoom"` crops each shot, `"grid_only"` skips the rest).
    It has no runner command; a driver stages the GLB, imports and opens the off-screen window:

    ```python
    _godot.clear_staged({"alien_m4"})
    res = _godot.stage(glb, "alien_m4")  # res://import/alien_m4/...glb
    _godot.import_project()
    spec = {"scenes": {"hero": res}, "out": OUT, "bg": [0.5, 0.505, 0.525],
            "hdri": "D:/prime-art-raw/env/polyhaven/studio_small_09/studio_small_09_2k.hdr",
            "rf2": RF2_PNG, "rf2_eye": [0.17, 0.26, 0.67, 0.76], "before": BEFORE_DIR_OR_EMPTY,
            "variants": [], "grid_name": "tune", "grid_lids": "rest", "grid_yaw": 18.0}
    # spec.json written to OUT
    code, text = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/eye_shots.gd", "--",
                                (OUT / "spec.json").as_posix()], (1536, 1536), 170, log=OUT / "window.log")
    ```

    A full run takes about 2 minutes (one Godot run at a time).
- **M5, the skin shader on its texture set** (output under `D:/prime-art-raw/review/char/alien-parts-kit/M5/`):
  - **The kit:** `alien_eyes.py --kit <M3c/export> --out <M5> --eye-images <S9/parts/export> --sss-orm`: M4's eyes
    on M3c's kit, so one GLB carries M3c's albedo and ORM, the capped cage's normal map and the M4 eyes.
    - `--sss-orm` writes `M5/textures/orm_sss.png`: M3c's ORM with R (occlusion) and G (roughness) unchanged
      (checked to the bit) and the 2K SSS mask (`alien_skin_sss.png`) upscaled into B
      (`alien_eyes_geom.UPSCALE2_TAPS`, bilinear at the quarter texels), and puts it on `alien_hue`.
    - B is glTF's metallic channel, unused. Separate Color's B drives Metallic through a multiply by 0, so the
      exporter writes `metallicFactor` 0 (plain viewers stay non-metal) and still copies the PNG's bytes. An
      unlinked Metallic made it rebuild the image without B.
    - The mask is linear like the rest of the ORM. The first M5 put it in the albedo's alpha, which is sampled as sRGB
      and which Godot's importer treats as alpha (`fix_alpha_border`).
    - `alien_hue` gets the custom property `prime_sss = "orm_b"`, exported as glTF `extras` (the export turns
      `export_extras` on; the crest and lid nodes' own custom properties come along as node extras).
    - The build checks the GLB (`alien_eyes_geom.sss_orm_problems`): metallicRoughness and occlusion are that very
      PNG, `metallicFactor` is 0 and the extras are there. `character.json` gets `note_m5_sss`.
    - `export/alien_character.glb` 35.5 MB. glTF-Validator: 0 errors, 1 warning (`NODE_SKINNED_MESH_NON_ROOT`).
      About 40 s of headless Blender. `M5/textures/albedo_sss.png` is the first M5's, unused now.
  - **The shader:** `alien_hue.gdshader` `textured` (off by default). `alien.gd` makes a second skin material,
    `_textured_material()`, only for a surface whose imported hue material carries `SSS_MARKER` (Godot imports
    glTF material extras as the material's `"extras"` metadata) and an `albedo_texture`.
    - **A kit without the marker keeps the procedural skin**, its look before M5: M3a, M3c and M4 have an albedo
      texture but no mask. The first M5 put them on the textured path, which read mask 1.0 from their RGB albedo: SSS
      0.48 everywhere and a warm transmittance band.
    - Proof: M4's kit under the merged `eye_shots.gd` with M4 final's spec (`M5/godot/m4_check/`) matches
      `M4/godot/final/` to the pixel: 11 of 16 PNGs byte-identical, the other 5 with a mean difference of 0.0.
    - The textured material takes the albedo, the ORM (`roughness_texture`, the same image as `ao_texture`) and the
      normal texture from the imported `StandardMaterial3D` and sets `SKIN` then `SKIN_TEX`. `skin_material()`
      returns it; the crests' `alien_hue_part` keeps the procedural path (`procedural_material()`).
    - Albedo: sRGB, RGB only, saturation scaled about its luminance (`tex_sat` on the hue, `tex_pale_sat` on the
      light mask), the hue parts' value by `tex_value`.
    - AO: the ORM's R into `AO`. `COLOR_0` is not read on this path, so the AO is not doubled (the albedo already
      carries 0.4 of it). Roughness: the ORM's G plus `roughness_add`.
    - Normal map: `NORMAL_MAP` at `normal_depth`, times `normal_pale` on the light mask. Godot rebuilds Z, so an
      RG-compressed import works. No procedural grain on this path.
    - SSS: `sss + sss_thin * mask` (the ORM's B), and a warm transmittance (`transmit`, depth
      `transmit_depth * mask`).
    - **Godot divides by `SSS_TRANSMITTANCE_DEPTH`.** A shader that writes any transmittance built-in must write a
      depth above 0 on every path. The first M5 shader wrote it only in one branch: the other path's depth stayed 0
      and every skin, textured or not, rendered black (NaN).
    - **Other hues** (coral, violet) take the procedural path's flat colour (`flat_colour()`, shared by both paths),
      darkened by `tint_ao_albedo` (0.15) of the texture's AO, with its AO at `tint_ao` (0.35) and on the direct
      light at `tint_ao_light` (0.25). They keep the texture's roughness and normal map. Teal takes the texture as is
      (`distance(hue, tex_hue)` 0).
    - A re-tint of the teal texture by its luminance was tried and dropped. It drew dark smudges where the texture's
      blurred accent passed the vertex mask, and grey rings round the knee spots.
  - **The crests:** on a textured kit `_material` (the procedural skin of the crests) also gets `SKIN_TEX_SHARED`:
    the teal's saturation and value (the procedural path applies `tex_sat`, `tex_pale_sat` and `tex_value` to the
    teal; identity at their defaults of 1), the specular, the rim, no glow and the dome's SSS. `m5_shots.gd` `crest`
    shows each crest on the textured head.
  - **The older tuning tools** on a textured kit: `hero_shots.gd`'s variants go to `skin_material()`, the textured
    one, where SKIN's `grain` and `ao_albedo` do nothing (tune them on an untextured kit or through
    `procedural_material()`); a variant's `hue` reaches the crests too. `neck_shots.gd`'s swim test sets the grain on
    `procedural_material()`: on a textured kit only the crests have it.
  - **The tuning** (`SKIN_TEX`, chosen on grids in `M5/godot/g1`..`g3`, rf2 first):
    - Under AgX the texture's teal washed out to a light cyan: `tex_sat` 1.45 and `tex_value` 0.72 give rf2's deeper
      teal, and `tex_pale_sat` 1.3 its mint.
    - SKIN's SSS 0.3 and fresnel glow made a waxy, hazy skin with no form. Now the SSS is 0.08, plus 0.4 on the
      mask's thin parts, the glow is off, and the rim is 0.35.
    - Specular 0.5 and roughness 0.08 lower: rf2's soft sheen on the dome.
    - Normal map 0.7, and 0.35 of that on the pale: the creases under the mouth and on the throat read as wrinkles at
      0.4 m.
  - **TAA (a proposal, not approved):** TAA on top of High's and Ultra's MSAA 4x would smooth the lid domes' sheen
    and the normal map, which sparkle under MSAA alone at 0.4 m. The approved presets do not use it (the table
    above); M5's `clips` render under TAA as a proof-only setting. Measured on the M5 alien (`m5_shots.gd` "taa", one
    1536 x 1536 frame, RTX 4060, GPU ms, median of 40 frames):

    | Shot (two runs) | MSAA 2x (Medium) | MSAA 4x (High, Ultra) | MSAA 4x + TAA | TAA alone |
    |---|---|---|---|---|
    | Face, 0.4 m | 2.48, 2.46 | 2.86, 2.80 | 3.78, 3.68 | 2.22, 2.22 |
    | Body, 3 m | 1.59, 1.59 | 1.87, 1.86 | 2.34, 2.33 | 1.56, 1.56 |

    MSAA 4x + TAA costs about 0.9 ms more than MSAA 4x on the close face and 0.5 ms on the body (`M5/godot/final/
    motion` and `final/taa2`). Not measured yet, so
    a later task before any approval: a House view with several characters and the first-person camera in motion
    (TAA's ghosting and blur when the camera turns), and the cost at 1920 x 1080 with the map's own draw load.
  - **`m5_shots.gd`**, the proof (it extends `hero_shots.gd`; its header lists the modes):
    - `hero`: the face at rf2's framing;
    - `turntable`: a 3840 x 1920 sheet with rf2, 8 angles and the hero face;
    - `close`: the face from 0.4 m (fov 50);
    - `compare`: before (S9d's procedural kit) | M5 | rf2 or u1;
    - `crest`: each crest on the textured head;
    - `grid`: a tuning grid (`grid_view` face or close);
    - `room`: four characters on the stand at game distance, the camera at 1.6 m, fov 70;
    - `taa`: the measurement above;
    - `clips`: every frame of Idle and Walk at 30 fps for `encode_clips.py`, under TAA with spec `taa` (proof-only).

    It has no runner command. The driver (`MODES` such as `"hero,turntable,close,compare,crest"`, then
    `"room,taa,clips"` with `EXTRA = {"bg": [0.5, 0.505, 0.525], "taa": true}`; the watchdog is 280 s, so two runs):

    ```python
    K = Path("D:/prime-art-raw/review/char/alien-parts-kit")
    _godot.clear_staged({"alien_m5", "alien_s9d"})
    hero = _godot.stage(K / "M5/export/alien_character.glb", "alien_m5")
    before = _godot.stage(K / "S9d/export/cage/alien_character.glb", "alien_s9d")
    _godot.import_project()
    spec = {"scenes": {"hero": hero, "before": before}, "out": OUT.as_posix(), "modes": MODES.split(","),
            "hdri": "D:/prime-art-raw/env/polyhaven/studio_small_09/studio_small_09_2k.hdr",
            "beside": RF2_PNG, "body_ref": U1_PNG, "face": {"dist": 1.1, "dy": 0.03}, "bg": [0.5, 0.505, 0.525]}
    spec.update(EXTRA)
    # spec.json written to OUT
    code, text = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                "res://alien/m5_shots.gd", "--", (OUT / "spec.json").as_posix()], (1536, 1536), 600,
                               log=OUT / "window.log")
    ```
  - **The coral and violet patches:** the dark grey patch on the outer thigh by the hanging fist and on the jaw stay
    after the AO terms were lowered (`tint_ao*`) and with the normal map off (`M5/godot/ao1`, `ao2`: no visible
    change). They are not the texture's AO or normal on the tinted path; open (the fist's shadow and SSAO on the light
    hues, or M3c's data under the fist), for the AO bake without the arms.
  - **`godot-check --textured`** on the M5 GLB. It passes the skeleton, the separate parts, the 10 animations (lengths,
    tracks, motion, loops), the feet at 0, the height (1.806 m), `textured` (17 of 64 surfaces) and 0 import errors.
    It fails only rules written for the Ultimate Modular characters, as M3a and M4 did:
    - `parts_skinned`: the crests and eye parts are rigid under the Head;
    - `facing_plus_z` and `eye_pupils`: no `_eyes` part, and not the UM's bone names;
    - `normal_maps`: the flipbook mouths and eyeballs have no normal map;
    - `texture_size`: 4096 px against 2048;
    - `surfaces_cap`: 64 surfaces against 8;
    - `pack_floor`: 56 bones and 10 clips against the UM rig's 62 and 24.

- **M6, the eyes and lips sized, rounded and integrated** (output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M6/`). The engineer on M5 (2026-10-19): the eyes too big, their
  corners very sharp from the front, and the lids and lips "from another universe" (they stood out from the head).
  The parts stay overlaid parts (no mesh deformation); the skeleton and the blink by lid rotation are unchanged.
  - **The build:** `tools/blender/alien_m6.py --kit <M5/export> --out <M6> --skin-tex <a set's textures/>
    [--skin-normal <normal.png>] [--eye-scale K] [--eye-sink M] [--corner JSON] [--export-name NAME]` opens M5's
    kit and writes `<out>/<export-name>/` (GLB, .blend, `character.json` with `m6` and `note_m6`). The skin's set
    is an argument: `albedo.png`, `orm.png` and the 2K `sss.png` of a `textures/` folder (M3c's, or M2b's
    recomposed one), the SSS mask put into the ORM's B again (`alien_eyes.sss_into_orm`). The image check and the
    SSS route check run on the GLB as in M4 and M5. The pure parts and settings are in `alien_lids_geom.py` (test
    `tools/tests/test_alien_lids_geom.py`). About 2 to 3 minutes of headless Blender (the parts' AO bake is most of
    it; `--no-bake` for a geometry check). The armature must go back to POSE before the export: left in REST (for
    the bakes), the exporter wrote every clip as the rest pose.
  - **The corners** (`alien_lids_geom.CORNER`, `alien_parts_geom.lid_shell(corner=...)`): S7's rolled rim kept its
    full swell out to the hinge poles, so the upper lid's rim stuck out 0.1 r past the dome's outline at both
    corners, a point from the front. Now the swell tapers to nothing from 35 degrees of latitude to the pole, and
    the edges bend toward each other there (the upper lid's down by 10 degrees, the lower lid's up by 5, fading out
    toward the shell's back), so the lids meet in a soft almond. 32 rows across the lid (S7: 20). The middle of each
    lid keeps S7's rim, so `EYE_LOOK`'s `*_reach_deg` hold. The wet strips are rebuilt on the same rims
    (`alien_eyes.wet_strip(corner=...)`). Chosen on `M6/grids/g1/grid_corners.png` (S7, 6/3 degrees from 45, 10/5
    from 35: rest, closed, open and the face).
  - **The size:** the ball, lids and wet strips scaled by `EYE_SCALE` 0.95 about the socket (the ball's centre) and
    moved `EYE_SINK` 2 mm back along the socket's axis. With the corners' 0.1 r points gone, the upper lid's
    outline is about 0.87 of M5's width. Smaller units opened a gap between the dome's silhouette and the socket's
    skin at the inner upper corner, a dark line (86 % a crescent; 90 % with a 5 mm sink still a line at 0.4 m; the
    sink does not close a sideways gap; `M6/grids/g4`); at 95 % it is a thin contact
    line. Going smaller needs the socket's skin to follow (or a flared dome back), a later step. The iris and pupil
    keep their angles (`IRIS_SCALE` 1: 90 % read the same at 1.2 m, and rf2's iris is large). Chosen on
    `M6/grids/g2` to `g4` (`grid_size.png`: 100, 93, 86 %, iris 90 %, then sizes with sinks of 0 to 5 mm).
  - **The lips and lid domes** (`alien_lip.gdshader`, `alien.gd` `LIP_LOOK`, `LID_LOOK`; S9's look is
    `LIP_LOOK_M5`, `alien.gd` `lip_look = "m5"`, for before sheets; every new term is off at its default):
    - each lid shell and 3D mouth piece carries its own baked AO (Cycles, 2 cm, 64 samples, floor 0.3, glTF
      `COLOR_0`; each eye design's four lids with its balls and the skin, each mouth piece alone with the skin); the
      shader moves the coral toward a deeper one (`deep`) over `ao_range`, so the lip line, the mouth's corners, the
      rim's underside, the lower lids and where a part meets the skin are deeper and the rolls stay light (plain
      viewers multiply the grey into the base colour);
    - rf2's coral: sRGB (0.78, 0.35, 0.31), deep (0.56, 0.18, 0.17); M5's (0.82, 0.44, 0.37) read pale salmon
      under AgX, a deeper orange (0.76, 0.33, 0.25) read orange, a pinker one pink;
    - a soft colour drift (`drift` 0.06, 2.5 cm blotches), the grain finer and a little stronger (0.08 at 600 per m),
      the skin's SSS (0.25) and transmittance (0.2), Godot's rim (0.35, as the skin's);
    - roughness 0.55 with a soft clear coat (0.06) on the lips; the lid domes 0.64 with none (their sheen read
      plastic beside the skin's satin, and sparkled).
    - Chosen on `M6/grids/g2` and `g3` (`grid_look*.png`, `zoom_look.png`, rf2 first).
    - Gated like the SSS and contact terms: `alien.gd` takes `LIP_LOOK` and `LID_LOOK` only for a kit whose imported
      `alien_lip` (the lips' and the lid domes' one material) carries `PART_AO_MARKER` (glTF extras
      `{"prime_part_ao": "color0_r"}`, set by `alien_m6.py` after the bake); an older kit (M5 and before) keeps
      `LIP_LOOK_M5` under the default `lip_look` (test `test_part_ao_marker_matches_the_build`).
  - **The skin's contact shade:** per Body vertex the distance to the nearest rest lid or rest lip (both designs),
    1 at contact to 0 at 7 mm (`CONTACT`), smoothed, in a fifth UV layer `contact` (glTF `TEXCOORD_4`, Godot
    `CUSTOM1.x`). `alien_hue.gdshader` (textured path) darkens and warms the albedo toward `contact_tint` and lowers
    AO by `contact_ao` there; `alien.gd` sets it (`SKIN_CONTACT`) only for a kit whose hue material carries
    `CONTACT_MARKER_M6` (glTF extras `{"prime_contact": "custom1_x"}`). M3c's texture already holds a contact AO round
    the sockets, so the term is subtle (the grid's "contact off" barely differs).
  - **The kits:** `M6/export/` (M3c's set and M3a's capped-cage normal map, 36.2 MB) and `M6/export_m2b/` (M2b's
    recomposed set, `--skin-tex M2b/textures --skin-normal M2b/bake/normal.png`, 29.4 MB; its composed ORM in
    `M6/skin_export_m2b/`). The rebuild of each is `blender.run_script("alien_m6.py", ["--kit", <M5/export>, "--out",
    <M6>, "--export-name", <name>, "--skin-tex", <set>/textures, "--skin-normal", <normal.png>])` (about 3 min, in the
    background); glTF-Validator 0 errors, 1 warning (`NODE_SKINNED_MESH_NON_ROOT`) on both. Sheets in
    `M6/godot/final/` and `final_m2b/`, grids in `M6/grids/`, JPEGs in `M6/showroom/`.
  - **`m6_shots.gd`**, the proof (modes `size`, `corners`, `look`, `final`; its header lists them; `size` and the
    spec's `scale`/`sink` scale the units at run time for the grids). Driven like `m5_shots.gd` (stage the kits,
    `_godot.window(...)` with `res://alien/m6_shots.gd`), with `"scenes": {"hero", "before"}` and
    `"corner_scenes"`. `final` writes `cmp.png` (M5 | M6 | rf2 at rf2's framing, the front at 1.2 m and the close
    face), `blink_<design>.png`, `designs.png` and `mouths.png`.
  - **For three.js:** the lids and lips are the GLB's `alien_lip` (Principled) with `COLOR_0` (the AO). The page's
    material for them: `MeshPhysicalMaterial` with `vertexColors` off and an `onBeforeCompile` that mixes
    `deep` (0.56, 0.18, 0.17) into `albedo` (0.78, 0.35, 0.31) by `1 - smoothstep(0.45, 0.95, color.r)` (sRGB values,
    converted to linear), `roughness` 0.55 and `clearcoat` 0.06 at 0.5 on the lips, 0.64 and no clear coat on the
    lid domes (nodes `eye_*_lid_*`), `sheen` none; the drift is optional; the AO into `aoMap`-like
    `ambientOcclusion` (`reflectedLight.indirectDiffuse *= mix(1, color.r, 0.5)`). The skin's contact field is in
    `texcoord_4` (`TEXCOORD_4`): `diffuseColor.rgb *= mix(vec3(1), vec3(0.80, 0.66, 0.62), texcoord_4.x)`. M6c splits it per
    design (below).
- **M6c, the grain back and one contact channel per design** (output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M6c/`). The engineer on v28's release candidate (`M6/export_m2b`):
  the skin "smooth again, without any texture" beside v27's "M3c + M4"; with the overbite mouth black shades where
  the frog lips sit; the manic eyes without their "shell".
  - **What flattened the grain:** M2b's normal map. Measured on the face (the face field of the fields, eroded; the
    RMS of the map minus its 3-texel box blur): the normal map's x/y 0.0118 against M2's 0.0215 (55 %); the albedo
    (0.0057 against 0.0056) and the ORM (R 0.0090, G 0.0030 both) did not change: the grain is a bump on the high
    copy, never in the curvature or the AO the texture is composed from. In Godot (light D, the same camera) the lit
    luminance's fine grain on the forehead at 0.4 m fell to a third (0.00125 against 0.00396).
  - **The sculpt `m6c`** (`alien_detail_geom.SCULPTS`): M2b's creases, jaw relax and curvature smoothing with M2's
    grain (pores 1.1 mm and 0.045 mm deep, peel 0.06 mm, face 1.0). Its normal map's face energy is M2's (0.0215);
    in Godot the forehead's grain is v27's (0.00395 against 0.00396 at 0.4 m); the softer brow keeps less there
    (0.0028 against 0.0032). Its curvature bake is M2b's byte for byte, so M2b's composed set (`M2b/textures`) is
    the skin's albedo and ORM unchanged; only the normal map is new (`M6c/bake/normal.png`).
  - **One contact channel per design:** `alien_m6.py` writes the field per design into two UV layers
    (`alien_lids_geom.CONTACT_UVS`): `contact` = glTF `TEXCOORD_4` (u bored, v manic) and `contact_mouth` =
    `TEXCOORD_5` (u frog, v overbite); v is stored flipped (the exporter writes 1 - v). Godot 4.7.2 imports both as
    `CUSTOM1` (RGBA_FLOAT: x bored, y manic, z frog, w overbite; measured maxima 1.00, 1.00, 0.96, 0.97).
    `alien_hue.gdshader` takes the max of `CUSTOM1 * contact_pick`; `alien.gd` sets `contact_pick` from
    `CONTACT_CHANNEL` in `set_eyes()` and `set_mouth_design()` on a kit with `CONTACT_MARKER`
    (`{"prime_contact": "custom1_designs"}`). M6's kits (`CONTACT_MARKER_M6`, `custom1_x`) keep their one field: the
    shader's default pick is x alone. Proof `M6c/godot/r3/channels.png` (the shade drawn black): every channel at
    once (M6) puts a black band above the overbite lips where the frog lips sit and above the manic lids where the
    bored domes sit; the picked channels do not.
  - **The manic eyes:** the M6 kit's manic lids, wet strips and cornea are all there and seal in the blink
    (`r2/blink_manic.png`); what flattened them in Godot was the bored domes' contact shade, a dark halo round the
    smaller manic lids, gone with the per-design channel. They keep M6's rounded corners, so they lack v27's corner
    wings (the "very sharp corners" of UPDATE 4).
  - **The build:** `alien_m6.py --kit <M5/export> --out <M6c> --skin-tex <M2b/textures> --skin-normal
    <M6c/bake/normal.png>` after `alien_detail.py --stage high --sculpt m6c --character <M2/uv/build/
    alien_character.blend> --out <M6c>` and `--stage bake --cage capped --out <M6c>` (each through
    `tools/runner/blender.py` in the background; about 2, 2 and 3 minutes). GLB 34.4 MB, glTF-Validator 0 errors.
  - **`m6c_shots.gd`**, the proof (spec `"kits"`: key, res, look, label, the hero last; modes `cmp`, `designs`
    (with `hues.png`: teal, coral, violet), `contact`, `channels`, `blink`, `manic`; its header lists the sheets).
  - **For three.js:** GLTFLoader keeps the two layers as the attributes `texcoord_4` (bored, manic) and `texcoord_5`
    (frog, overbite); the shade's field is `max(max(t4.x * pick.x, t4.y * pick.y), max(t5.x * pick.z, t5.y *
    pick.w))` with `pick` 1 on the shown eye design's and mouth's channels (`CONTACT_CHANNEL`).
- **M8, the lips shaped like lips** (output under `D:/prime-art-raw/review/char/alien-parts-kit/M8/`). The engineer
  (2026-10-20): the lips were "two sausages, the same thickness end to end"; the sheets (mf1, mo1) and rf2 show each
  lip narrow at the corners, full in the middle and narrow again.
  - **The profile** (`tools/blender/alien_lips_geom.py`, plain Python, `LIP_SHAPE`; `LIP_SHAPE_M6C` = `{"w": 0}` is the
    old lips exactly): along each closed lip (rest, M, small) the half-height is `centre * full * (upper | lower) *
    taper(s)`, `taper(s) = corner + (1 - corner) * (1 - |s|^pw)` (s from -1 to 1 corner to corner: a pointed lens), the
    upper lip times 0.82 and the lower 1.12, the upper lip's top edge dipping at the centre by `bow` of its height
    (a soft bow, two small peaks at s = +-0.2); the lip line (the upper lip's bottom, the lower lip's top) stays where
    the sheet measured it, so the phases keep their openings. The open rings (A, E, O) take the same profile round
    the ring with their inner edge (the opening) kept, weighted by `ring` (A 1, E 1, O 0.35: the pucker stays round).
    The constant depth `DEPTH_C` falls to `depth_corner` (0.25) at the corners, so the ends sink into the skin as
    points (S7's corner join and tuck still apply). The section (`section()`, `alien_mouths.lip_tube`): a
    superellipse front (`square` 0.85, a flatter cushion) with its swell moved toward the lip line (`lean` 0.3), so
    both lips are fullest where they meet and the line reads as a crease. The dark cup of an open ring and the dark
    between the overbite's teeth end under the new lips' axes (a thin corner no longer bares them).
  - **`alien_mouths.py`**: `build_piece(..., lips=, name=)` takes the shape; `shape_frames()` and `face_width()` are
    main's measuring steps as functions; `--lips JSON|m6c`; `main()` runs only as a script. The same sheets, stations
    and sheet-to-head mapping as S9: rebuilt with `m6c` on M6c's kit every piece is the old one to 0.0 mm.
  - **`alien_m8.py`** (the kit step): opens a kit (`--kit <M6c/export>`), rebuilds the twelve 3D mouth pieces in place
    (the same objects, names, parent on the Mouth socket, materials; only the meshes change, so `alien.gd`'s talk and
    blink logic is untouched; the flipbook shells, the eyes, the Body's mesh and skin AO are not touched), rebakes
    the mouth pieces' AO (`alien_m6.bake_parts_ao(body, eyes=False, pieces=...)`, the lids' AO kept), recomputes
    Body's contact channels (`alien_m6.contact_field`: the eye channels come out as before, frog 414/25 and overbite
    340/91 touched/full vertices against 421/22 and 354/93), exports with M6's options. `--grid SPEC` adds variant
    pieces `lipvar_<variant>_<design>_<shape>` (the grid kit only). About 25 s (60 s with the grid).
  - **Chosen on** `M8/grids/g1/grid_a.png`, `grid_b.png` (`m8_shots.gd` mode `grid`: the references, then per variant
    frog rest from the front and at 3/4 at 0.4 m, 3/4 at 1.2 m, frog A, overbite rest): the M6c lips (c0) and
    corner {0.35, 0.15} x full {1.0, 1.2} x bow {0.15, 0.30}; the pick is c8 (0.15, 1.2, 0.30): the fine corners and
    the bow of the sheets, without losing the lips' size at 1.2 m.
  - **On M6c's skin** the thinner lips bare a dark edge above the upper lip and at the corners: M6c's skin AO was
    baked with frog rest on the face (M7's finding), so the skin under the old, bigger piece is nearly black. M7's
    mouth-free AO removes it (`M8/godot/on_m7/`: the same lips on M7's kit, no dark edge).
  - **`m8_shots.gd`**, the proof (modes `grid`, `phases`: per design a row per shape, the sheet's panel then before
    and after from the front, at 3/4 and in profile; `talk`; `cmp` as `m6c_shots.gd`; M8b's `wgrid`, below).
  - **M8b, the width** (the manager on M8, with UPDATE 9's target, m2's first head: a compact mouth). `LIP_SHAPE`'s
    `width` scales every x of a piece (lips, cup, tongue, teeth) about the face's centre line (`scale_x`, applied
    in `build_piece` before anything is laid on the skin), heights kept: all six phases of both designs narrow alike
    and their corners are ray-cast onto the skin where they now sit. Chosen on `M8/wgrid/shots/wgrid.png` (`m8_shots.gd`
    mode `wgrid`: m2's first and third heads, mf1 rest and A, mo1 rest; then a row per kit, each width a kit of its
    own with its own contact channels: frog rest from the front and at 3/4 at 0.4 m and 1.2 m, overbite rest, frog A)
    from 1.0, 0.85, 0.72 and 0.62: **0.72**. At 1.0 the corners reach the narrow lower face's silhouette from the front
    and wrap round the jaw at 3/4; at 0.85 the far corner still nearly does; at 0.72 both corners sit in the face's
    front with skin beyond them, as on m2's broad face, and the mouth still reads at 1.2 m; 0.62 reads as a pucker
    and crowds the overbite's teeth. Frog rest is 81.7 mm wide (was 113.4), 0.57 of the face's silhouette at the
    socket (0.143 m). m2's own lips are wide against its broad face (about 0.8 of it at their row), so "compact"
    here is the corners inside the face, not a measured share. The flipbook shells (the 2D fallback) keep the
    sheet's width.
  - **The thin outline round the mouth** (M8 on M7's kit, `m8m7-close_front.jpg`): the detail sculpt's `lip_groove`,
    cut round frog rest's box (the old, wide piece) below the mouth and round its corners; the normal map and the
    texture's cavity tint (the curvature bake) drew it on the bare skin once the lips were thinner. The sculpt
    `m8b` (`alien_detail_geom.SCULPTS`) is `m6c` with the groove's depth 0; the skin carries no mouth's mark, as its
    AO since M7, and each mouth's shade on the skin is its contact channel. The texture's soft mouth-rim gloss and
    flush (`alien_texture.py` fields), the philtrum and the nasolabial lines still follow frog rest's box, now the
    narrower one. Proof `M8/godot/outline/`: the same 0.72 lips on M7's skin (with the groove) and on M8b's; the
    difference of the close front and 3/4 frames (`outline_diff.png`, x12) is the groove's crescent under the lower
    lip and round the old corners, at most 15 of 255 in the lit frame, plus the moved nasolabial lines; nothing of
    it is left on M8b's skin.
  - **The build (M8b):** M7's chain from the mouths step on M7's cage and assembly (`M7/s/asm`), the sculpt `m8b`,
    then `alien_m6.py --export-name kit6` and `alien_m8.py --kit <M8/kit6> --out <M8> --export-name export`
    (`tools/out/m8/go8.sh chain`, about 9 minutes in the background). `alien_m8.py` then moves no vertex (0.0 mm:
    the chain's mouths step already built the 0.72 lips); the mouth contact is frog 277/19 and overbite 238/57
    touched/full vertices (the narrower footprint). GLB 34.1 MB, glTF-Validator 0 errors, `godot-check --textured`
    as M7's kit (14 ok, the same seven pack-contract failures).
  - **Open:** with every x scaled, the open phases are narrower than the sheets' (frog and overbite A read taller
    than wide, closer to an "oh"); a per-shape width weight (as `ring`) would widen A and E again if wanted.

- **M7, the mouth's black strip and the longer, slimmer digits** (output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M7/`). The engineer on v29: a black wedge beside and above the
  overlaid mouth pieces (frog A and O, overbite rest's far corner, A and O), and fingers and toes "like sausages".
  - **The cause of the strip:** the Body has no mouth slit (a front-ray height field round the `Mouth` socket: the
    deepest groove is 1.7 mm, the soft groove under the mouth). The skin's AO was baked with the default face shown,
    and that face includes `mouth_frog_rest`, the widest piece (x -60..56 mm). The skin under it baked almost black
    (front view, the loops under frog rest: `ao.png` 0.03-0.09, ORM R 0.05-0.14, `COLOR_0` 0.33-0.55 against
    0.87, 0.96 and 0.88 elsewhere); every smaller piece bares that skin.
  - **The fix:** the three AO bakes show the eyes alone, `SHOWN = ("eye_bored_",)` in `alien_ao.py`,
    `alien_detail.py` and `alien_texture.py` (`test_alien_digits` holds it). The lips' own shade on the skin stays
    M6c's per-design contact field (`TEXCOORD_5`), which follows the mouth shown. The skin geometry and the mouth
    pieces are unchanged. Measured in Godot (light D, `cmp.png`'s close 3/4): the rest mouth's surroundings did not
    change (the mean luminance below the lower lip 187.0 before, 187.1 after; the corner 195.8 both).
  - **The digits:** `alien_cage.py --digits JSON` overrides `DIGITS` (`FINGER_K`, `FINGER_R`, `TIP_BACK`,
    `THUMB_R`, `THUMB_LEN`, `TOE_LEN`, `TOE_THICK`, `TOE_MID`) for a variant; `cage.json` records them. The thumb's
    root rings keep `THUMB_R0` (S9's 0.0215) and `thumb_thin()` slims it from t 0.2 to 0.56; the toes' first ring
    takes half the thinning (`toe_ring()`), so the roots do not fold. A 3 x 3 grid (length x 1.0, 1.1, 1.2 on
    `FINGER_K`, `THUMB_LEN`, `TOE_LEN`; thickness x 1.0, 0.9, 0.8 on `FINGER_R`, `THUMB_R`, `TOE_THICK`) picked
    **L1.2 T0.8**: `FINGER_K` 0.984 (the mesh's joints nearly at the bones'), `FINGER_R` 0.01664, `THUMB_R` 0.0172,
    `THUMB_LEN` 0.0744, `TOE_LEN` 1.2, `TOE_THICK` 0.8. Still three fingers and a thumb with round tips; the fist
    closes without tearing; `hand_max_fold_deg` 155.9 (S9: 148.0, at the same thumb-root vertex). The knuckle accents
    (`alien_assemble.KNUCKLE`, spheres at the Proximal heads) now reach the slimmer fingers' backs: they show as
    small coral patches, stronger on the index and ring than on the middle.
  - **The chain, once:** cage, assemble, mouths, AO (S9's drivers), then `alien_uv.py`, `alien_detail.py --stage
    high --sculpt m6c`, `--stage bake --cage capped`, `--stage export --kit <s/ao/export>`, `alien_texture.py
    --stage fields|compose|export --set m3c` on that bake, `alien_eyes.py --sss-orm`, `alien_m6.py --skin-tex
    <m3/textures> --skin-normal <m2/bake/normal.png>` into `M7/export/` (about 7 minutes in all). GLB 34.1 MB,
    glTF-Validator 0 errors, `godot-check --textured` as M6c's (14 ok, the same seven pack-contract failures).
  - **`m7_shots.gd`**, the proof (spec `"kits"` as `m6c_shots.gd`): `digits` (frames aimed on the bones, spec
    `"marks"` draws the aim points: the rest-pose open hand, `alien_cage_review.curl`'s fist, Idle, Sprint, the
    planted foot in Walk, the hand at 3.5 m), `mouths` (`mouths_<design>.png`: six shapes, before above after,
    front, both 3/4, profile, from below at 0.4 m and 3/4 at 1.2 m; `mouths_clips.png`: Talk and Walk), `body`, and
    m6c's `cmp`, `designs`, `contact`. Split the modes across runs (the watchdog).
  - **For three.js:** no material, node, attribute or layout change; the Body's `UVMap`, textures and `COLOR_0` are
    regenerated (no dark band under the mouth in `COLOR_0` either), so the page takes the M7 kit folder as it took
    M6c's.
- **M9, one standard eye mount: smaller eyes nested in the sockets** (output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M9/`). The engineer (2026-10-20): the eyes too big, bulging out
  "like a crab's"; in the liked 2D part sheet e2 (`D:/prime-art-raw/2026-10-17-alien-2d-parts1/e2/`, 8 eye designs
  on our head) the ball's front sits about flush with the face, the eyes stay inside the head's front silhouette, the
  lids are slim shells and a soft rim surrounds each socket. The skin must not depend on any eye design.
  - **Measured on M7's kit:** S9's ball radius 42.4 mm (M7 drew it at 0.95), the lid shells reach 1.23 r; the ball
    centres at x = +-76 mm, so the lids reached x = 128 mm against the head's half width of 99 mm at the eyes' height
    (2.5 cm outside the front silhouette), and the ball's front stood 3 cm before the face's midline. S9's socket
    bowl hugs the full-size ball (the skin within 0.9 to 1.0 r of its centre): M6's dark line came from scaling the
    eye alone (the bowl stayed full size).
  - **The mount** (`alien_lids_geom.SOCKET`, `tools/blender/alien_socket.py`): every eye part (both designs' balls,
    lids and wet strips) and the `Eye_<side>` node are scaled by `scale` about the old ball centre C and moved by
    `eye_offset` (`sink` back along the socket's axis, `inward` toward the midline); the Body's skin follows: within
    `inner` (1.3 old radii) exactly, so the bowl hugs the smaller lids as it hugged the full-size ones, then a
    smootherstep fade to `outer` (2.0) that forms the socket's slope, and a soft rim (`rim` 0.8 mm at 1.1 new lid
    radii, the socket's front half). Refused: a face folding over on visible skin, the Mouth's or the crest's skin
    moving over 0.2 mm, the designs' balls not on their socket. `Body["prime_socket"]` records it (glTF extras on the
    Body node); `alien_m6.py` then rebuilds the lids at the mounted size (`eye_scale` 1, no sink). Any later eye
    design authored in the socket's frame at S9's size and scaled by `scale` lands on the same mount.
  - **The chain:** a stage between `alien_mouths.py` and `alien_ao.py` (`alien_socket.py --character
    <mouths/build/alien_character.blend> --out <s/socket>`), so the AO, the texture UV, the detail sculpt's eye folds
    (they hang on the ball's box) and the bake all see the new sockets. `alien_m6.py --socket JSON` applies a variant
    to a finished kit without one (the grid: M7's `m5/export` kit, its texture moved with the skin).
  - **The grid** (`M9/godot/grid/eyes.png`, `M9/showroom/m9grid-eyes.jpg`; e2's heads 1 and 4 first, then M7): scale
    0.82 and 0.76 against sinks of 15 to 25 mm, inward 19 or 16 mm, a steeper socket (`outer` 1.7, rim 1.2 mm);
    front and 3/4 at 0.4 m and 1.2 m. The 0.70 cells and a 2.4 `outer` were refused by the checks (a fold at the
    inner corner; the mouth's skin moved 5 to 8 mm). **The pick: 0.82, 20 mm back, 19 mm inward**: e2's eyes are
    large (the lid about 0.43 of the head's width at the eyes) and reach the head's edge; 0.82 keeps that size inside
    the silhouette (2.2 mm in) with the ball's front 8 mm before the skin beside it (M7: 30 mm); 0.76 read small
    beside e2, and the 25 mm sink at 0.82 folded the inner corner.
  - **The skin's AO (brief UPDATE 8):** the three bakes show no part (`SHOWN = ()`); M3c's socket field in
    `alien_texture.py` takes the mount's box (the ball's x `MOUNT_OUT` 1.23), not a design's lids.
  - **`m9_shots.gd`**: `eyes` (a row per kit and design: front and 3/4 at 0.4 m and 1.2 m, spec `e2` and `e2_crops`
    as the first row), `socket` (the left socket close: front, outer side, above, below), `blink`, and m6c's and
    m7's `designs`, `contact`, `body`; spec `eye_views` replaces the four eye views (M9b's lid grid).
- **M9b, the eyes finished on the merged lips** (brief UPDATE 11; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M9/`: the kit `export/`, the intermediates `b/`, M9's first kit kept
  in `export_m9a/`). Three changes, then the chain once on M8b's lips.
  - **Slim lid shells** (`alien_lids_geom.LIDS`, `slim`, `set_lids`): a lid keeps its inner radius (the ball's
    clearance, the wet strip, the blink: the closed upper lid still slides over the lower, its inner radius above the
    lower's outer) and its thickness (`rho_out - rho_in`) is multiplied by `thin`, its rolled rim's swell (`LID_BEAD`)
    by `rim`. `alien_m6.py` rebuilds the shells and wet strips with it on a mounted kit (S9's shells on an older kit;
    `--lids JSON` for a grid); `alien.gd` `EYE_LOOK`'s `*_reach_deg` are the slimmed rims' reach
    (`alien_eyes_geom.rim_reach`: bored 2.36 / 1.0, manic 2.19 / 0.93 degrees; S9's 4.3 / 2.0 and 3.7 / 1.8).
    **The grid** (`M9/b/godot/lgrid/lids.png` and `lgrid2/socket.png`, JPEGs `M9/showroom/m9b-lids4.jpg` and
    `m9b-lids_close.jpg`): S9's domes, thin x rim 0.6 x 0.6, 0.45 x 0.55, 0.45 x 0.8, 0.3 x 0.45, 0.3 x 0.7, both
    designs, front and 3/4 at 0.4 m and the socket close. **The pick: thin 0.3, rim 0.7**: the upper lid's edge at
    1.15 ball radii (S9's 1.23), its rim half as thick as S9's, the shell 0.7 mm; the thinnest cells read thinnest,
    and of those 0.7's roll still shows as a soft ring round the manic eye as in e2's fourth head, where 0.45 left a
    hard edge.
  - **The pale round the eye** (the teal band on M9's socket slope): the mount had pulled the vertices carrying the
    crown's teal (light 0 in the `masks` UV, once hidden under S9's big lids) down beside the smaller eye, and on the
    slope, which faces down, they shaded to a dark band like heavy eye shadow. `alien_socket.py` (`raise_light`) now
    raises the `masks` light, never lowers it, to `alien_lids_geom.eye_light`: full within `SOCKET` `light_in` (1.4
    new ball radii) of the new centre, none past `light_out` (1.95), on skin whose normal faces the socket's way
    (cosine from -0.3, full at 0.4: the temples and the head's sides keep their teal). The texture's pale and `deep`,
    and Godot's `UV2.x`, follow. The first try (1.6 / 2.3, `M9/b/godot/try1/`) pushed the crown far up and laid the
    slope's ripples bare: the warp packs the old socket's skin into a narrower slope, and its undulations showed on
    the pale as two or three arcs above each eye. So `alien_socket.py` (`smooth_slope`) also runs `SOCKET` `smooth`
    (30) Taubin passes (lambda 0.5, mu -0.53) over the slope above each eye before the rim is raised
    (`alien_lids_geom.smooth_band`: from `inner` to 0.85 of the way to `outer`, from 0.2 old radii below the eye's
    centre up; a pass over the nose bridge folded faces there, so it stays out). On the kit: 1480 vertices smoothed,
    0.49 mm on average; 2063 vertices made paler; still no fold and the mouth's skin unmoved.
  - **The mouth mount** (PR #242's review minor 2): `alien_lips_geom.MOUTH_MOUNT` and `mouth_mount()`, a constant box
    on the `Mouth` node (M8b's frog rest box, centred on the midline: centre 2.7 mm below and 3.8 mm behind the node,
    half width 41.4 mm, half height 20.8 mm, front 19.8 mm before it). `alien_detail.py`'s philtrum and nasolabial
    lines and `alien_texture.py`'s mouth rim, flush and cheek patches hang on it, never on a mouth piece's box.
  - **The chain** (the documented one from here; driver `tools/out/m9b/go.sh all`, about 15 minutes): cage, asm,
    mouths (M8's default lips, width 0.72), socket (the mount and the pale), ao (no part), uv, high with the sculpt
    `m8b` (never `m6c`: it brings back the groove round the mouth), the capped-cage bake, export, M3c's fields,
    compose and export, `alien_eyes.py --sss-orm`, `alien_m6.py` (the slim lids), glTF-Validator.
  - **The kit:** `M9/export/alien_character.glb`, 34.5 MB, glTF-Validator 0 errors (1 warning,
    `NODE_SKINNED_MESH_NON_ROOT`); `godot-check --textured` 14 ok and the same seven pack-contract failures as M7.
    Proofs in `M9/godot/final/` (M8 | M9 | M9b, every run logged `OFFSCREEN`): `eyes.png` (e2's heads 1 and 4
    first), `s/` socket and blinks (open, rest, half, closed: both designs seal), `d/` designs, hues, contact, body,
    `m/` and `p/` the six mouth shapes of both mouths and the talking frames (the mouths read as M8b's), `frames/`
    Idle, Walk and Talk_Upper; JPEGs `M9/showroom/m9b-*.jpg`.
  - **Open:** the pale's edge toward the crown keeps the texture's frayed light-mask edge (as elsewhere on the face);
    on the socket's outer side, which faces away, a teal crescent stays (the facing rule keeps the head's sides teal);
    the closed manic lids keep a faint darker patch at the upper inner corner (as on M9's kit).
- **M10, smaller eyes and plumper lips on M8b's unchanged skull** (brief UPDATE 12; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M10/`). **M9's and M9b's socket stage is rejected:** on v30 the
  engineer found the re-sculpted skull looked as if "half the head was removed", with giant dents. He had only asked
  for the eyes a little smaller and the lips a little plumper.
  - **The socket stage is off.** `alien_socket.py` refuses to run without `--opt-in-rejected-m9`, and so does
    `alien_m6.py --socket`; the code stays for reference. The chain is M9b's without the stage: cage, asm, mouths
    (M8b's lips, width 0.72), ao (no part, UPDATE 8), uv, high (`m8b`), the capped bake, export, M3c's fields (the
    mouth mount), compose and export, `alien_eyes.py --sss-orm`, `alien_m6.py`, glTF-Validator (driver
    `tools/out/m10/go.sh chain`, about 25 minutes, most of it the bake). Without the mount, `alien_texture.py`'s
    socket field (`MOUNT_OUT` x the ball's box) takes S9's full-size ball, which is about M8b's lid box. The digits
    (M7), the mouth mount (M9b) and the contact channels need nothing else.
  - **Proof that the skull is M8b's:** the Body's 24417 rest vertices of the chain's kit against `M8/export`: a
    largest move of 0.0 mm (none over 0.01 mm), and the Eye, Mouth and Crest nodes unmoved
    (`tools/out/m10/cmp_body.py`, `M10/b/cmp_m8b_base.json`). Every grid cell shares that Body: `alien_m6.py` and
    `alien_m8.py` move only the parts.
  - **The eye unit** is scaled about its socket only, as M6 did (`--eye-scale`; 100, 92 and 86 % of M8b's 0.95 are
    0.95, 0.874 and 0.817, with M6's 2 mm sink). S9's lids are kept. **The flare** (`alien_lids_geom.FLARE_OFF`,
    `flare_base`, `flare_at`, `lid_gap`, `auto_flare`) closes the gap that opens between the smaller dome and the
    socket skin, which is never moved. The shell's outer surface swells by `amount` ball radii over a ramp that
    starts 5 degrees before the elevation where the dome turns away from a front view and rises over 50 degrees.
    The rim, the bead, the wet strip, the inner surface (the blink's seal) and the rim reach are unchanged.
    `alien_m6.py --flare auto` (M10's default; since M10b the default is `off`, the collar fills the gap) measures,
    per design, lid and side, the skin's distance outside the dome per 10-degree latitude band, and takes the smallest
    amount (0.0025 r steps) that leaves every band at least 0.004 r into the skin (the larger side's). The skin meets M8b's domes 70 to 180 degrees behind the edge. Before the
    flare, the widest band gaps were 0.6 to 1.1 mm already at 100 % (the corners and the lower lids) and 3.4 to
    4.4 mm at 92 %, 6.1 to 7.0 mm at 86 %. The amounts are in each kit's `character.json` (`m6.flare`). A first ramp
    from 25 degrees swelled the dome's visible top, and the eyes did not read smaller (`M10/godot/grid_try1/`).
  - **The lips' plumpness** (`alien_lips_geom.LIP_SHAPE` `plump`, 1.0 = M8b's): both lips' thickness times it on
    top of `full`, closed tubes and open rings alike. The depth follows the thickness (`DEPTH_A`), so the volume grows
    with it; the bow, the tapered corners and the lip line are kept (`alien_m8.py --lips '{"plump": 1.15}'`).
  - **The lid marker** (PR #243's review minor 1): `alien_m6.py` writes `prime_lids` on `alien_lip` (glTF extras,
    JSON: the lid setting and each design's rim reaches in degrees). `alien.gd` takes the eye shader's
    `*_reach_deg` from it; a kit without it keeps `EYE_LOOK`'s, S9's again (bored 4.3 / 2.0, manic 3.7 / 1.8).
  - **`m10_shots.gd`**: `grid` (m9's `eyes` under a reference row from spec `refs`: e2's heads 1 and 4, m2's
    first and third), `head` (the whole-head gate: the first kit against each other kit, front, 3/4, profile and
    top: with every part, in one plain grey material with no part, and unshaded white for the silhouette, each with
    its difference x4 and PROOF lines with the changed shares), `socket`, `blink`, `mouths`, `designs`, `contact`,
    `body`.
  - **The grid** (`M10/grid/<cell>/`, 18 kits: `e100|e92|e86` x `p100|p115|p130` x `w72|w80`; sheets
    `M10/godot/grid/grid_e100.png`, `grid_e92.png`, `grid_e86.png`, `grid_manic.png`, `grid_w80.png`, every tile
    labelled in Ukrainian, for example "очі 86 %, губи +15 %, ширина 0.72"). **The recommendation: eyes 86 %, lips
    +15 %, width 0.72**, built as `M10/export/`. At 92 % the change hardly reads at 1.2 m; at 86 % the eyes read
    smaller from the front and the head's outline shows beside them. +15 % reads a little plumper, with the bow and
    the fine corners kept; +30 % is clearly heavier. 0.80 is close to M9's first width, and M8b's 0.72 was approved.
  - **The gate** (`M10/godot/head/head.png`, M8b against the pick): the plain-grey skull with no part changes 0.0000
    of the pixels in all four views, and the silhouette 0 of about 190000 covered pixels; with the parts, 4.2 %
    (front), 3.2 % (3/4), 1.8 % (profile) and 1.6 % (top) change, all of it on the eyes and lips.
  - **The kit:** `M10/export/alien_character.glb`, glTF-Validator 0 errors (1 warning `NODE_SKINNED_MESH_NON_ROOT`);
    `godot-check --textured` 14 ok and the same seven pack-contract failures as M8b (`M10/godot_check.log`).
  - **Open: the flare shows at 0.4 m.** `M10/godot/socket/` and `blink/`: where the swell begins, a soft shoulder
    shows behind the dome. A notch shows at the eye's corners, where the upper and lower lids swell by different
    amounts (bored 0.18 / 0.25 r, manic 0.20 / 0.26 r at 86 %). On the closed lids a darker band shows where the
    swell rotates into view. The next step: one amount per design for both lids, and a longer, gentler ramp
    (`FLARE_SIL` width 80 to 100). If that is not enough, a separate socket collar part per side, or the flare
    faded toward the hinge poles.
- **M10b, the engineer's numbers, the socket collar and the thumb** (brief UPDATE 13 to 15; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M10b/`). The skull stays M8b's: the pick's Body against `M8/export`
  moves 0.0 mm (`M10b/export/cmp_m8b.json`).
  - **The thumb at rest read swollen** (`alien_thumb.py`, its docstring has the measurements). The mesh's thumb points
    forward along the hand, 5 to 7 cm off its bones, which run down from the wrist; the cage weighted its rings by
    segment, so the clips' thumb turns swung each ring about a far pivot and stretched the tube (Idle: edges up to
    2.2 times, the thumb 10 % larger; Walk 23 %). M7's longer thumb lengthened the lever. M10b first put each thumb
    vertex's thumb weight 0.7 on the Metacarpal and 0.3 on the Hand: no swelling, but a straight bar in fists (PR
    #245's review). Now (`--thumb blend`, the default) each thumb vertex's weight is split by its position along the
    thumb (projected on the mesh thumb's root-to-tip axis, never by the distance to the far bones): 0.6 on the Hand, a
    Proximal share rising to 0.2 over u 0.1 to 0.6, a Distal share rising to 0.2 over u 0.6 to 1, the rest on the
    Metacarpal. The shares change slowly along the tube, so rings move alike. The left thumb against rest (its
    largest distance from its centre in the Hand's frame, eight phases per clip): Idle 1.026, Walk 1.029; the fist
    bends 22 degrees (the rigid split: 6), a grip 13 (3). The cage's segment weights are kept in point attributes
    `prime_cage_*` (never exported) and `alien_texture.group_weights` reads them, so a re-texture keeps the warm
    thumb tip. The mesh, skeleton and clips are unchanged. Proofs: `M10b/godot/hands_fix/hands_fix.png` (Blender:
    rows M6c, M7, M10b's rigid split, the blend; Idle, Walk, Talk, fist, grip; `measure.log` has the numbers) and
    `M10b/godot/hands_fix/godot/` (Godot: open, fist, Idle, Sprint, Walk).
  - **`alien_m6.py`'s defaults build the pick:** `--flare off --collar on` (no collar on a full-size unit,
    `--eye-scale` 0.95); `--collar on` with a flare is refused before the kit is opened.
  - **One flare per design** (`alien_m6.flares`: both lids take the larger amount; `FLARE_SIL` width 90): the corner
    notch is gone, but at 80 % the flare still stands out as flanges at the eye corners (`M10b/godot/sock80/`).
  - **The socket collar** (`alien_lids_geom.COLLAR`, `collar_gaps`, `collar_smooth`, `collar_section`;
    `alien_m6.py --collar on --flare off`): per design and side `eye_<design>_lid_collar_<side>`, a sibling of the
    ball (shown with its design; `_lid_` gives it the lids' material in `alien.gd`), static. It covers, as a front
    view sees it (rays down the eye's axis onto the Body), the crater M8b's larger dome covered and the smaller one
    leaves bare, as a flat elliptic tube from 3.5 mm inside the dome's outline to 0.8 mm into the skin, with an even
    3 mm rim where no crater shows. Its AO bakes with its design's lids and the contact channels include it. Tries
    in `M10b/godot/sockc3` to `sockc8`: following the deep crater gave fins at the temple, no rim gave a lopsided
    disc, a ring ending at the outline left a dark slit at the lids' corners. 100 % is M8b's unit and needs neither.
  - **The grid** (`M10b/grid/<cell>/`, 27 kits: `e100|e90|e80` (`--eye-scale` 0.95 / 0.855 / 0.76) x
    `p100|p85|p75` (plump 1.0 / 0.85 / 0.75) x `w72|w80|w86`; sheets `M10b/godot/grid/grid_e<eye>_w<width>.png`, one
    per eye size and width, plus `grid_manic.png`; labels in Ukrainian). The skin maps are the same for every cell.
    **The recommendation: eyes 80 %, lips -15 %, width 0.80**, built as `M10b/export/`.
  - **The gate** (`M10b/godot/head/head.png`, M8b against the pick and against `e80_p75_w86`): the plain-grey skull
    with no part changes 0.0000 of the pixels in the front, 3/4 and profile views; in the top view 0.0049 and 730
    silhouette pixels, all of them the thumbs (M10b's rigid thumb in Idle, before the review's blend). With the parts: 4.5 / 3.9 / 2.3 / 3.3 %.
  - **The kit:** glTF-Validator 0 errors (1 warning `NODE_SKINNED_MESH_NON_ROOT`); `godot-check --textured` 14 ok and
    the same seven pack-contract failures as M10 (surfaces 68: the four collars).
  - **Open:** at 0.4 m the collar still shows a small tab below the eye from 3/4 and from below, and the crater
    behind its top shows from above (`M10b/godot/socket/`).
- **M10c, the socket collar as skin** (brief UPDATE 16 and 18; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M10c/`). On M10b's sheets the 90 and 80 % eyes did not read smaller:
  the coral collar filled the gap with more coral, so the coral round each eye stayed as large as at 100 %, and from
  3/4 it read as a stacked ring with a tab under the eye. The skull and the skin mesh are unchanged (the gate below).
  - **The skin collar** (`alien_m6.py --collar skin`, the default; `--collar on` keeps M10b's coral ring;
    `--collar-opts` JSON over `alien_lids_geom.COLLAR_SKIN`): per design and side `eye_<design>_collar_<side>` (no
    `_lid_` in the name: `alien.gd` would give a `_lid_` surface the lids' coral), a static sibling of the ball in the
    Body's material `alien_hue`, so `alien.gd` gives it the textured skin and its hue like the Body. Its section per
    azimuth bin (`fillet_section`) runs from 1.5 mm out on the face and 0.3 mm under it, tangent to the skin at the edge
    of the crater M8b's dome covered as a front view sees it, to 3 mm inside the dome's outline and 4 mm behind its
    equator (inside the ball too: the lids' rounded corners leave the shell open at the poles). The crater is measured
    without M10b's sphere limit (`collar_gaps` with `sphere` off, down to 0.9 ball radii behind): the brow above the
    eye lies 16 to 29 mm behind the outline, a dark trench without it. A crater narrower than 4 mm draws the section
    into the dome (`shrink_mm`), so where the skin falls away at the temple no strip lies on the dome's side.
  - **Seamless with the skin:** per vertex the Body's `UVMap`, `masks`, `rest_xy`, `rest_zn` and point AO are sampled
    (barycentric, `BodySampler`) on the skin at the crater's edge (`uv_pull` 1: the old crater's dark bottom never
    reaches it); the normals are the skin's at the edge, blended halfway toward the fillet's own at the dome
    (`geom_end` 0.5, custom normals); `contact_field` writes the lids' contact into its `contact` and `contact_mouth`
    layers as it does for the Body (with `--collar skin` the Body's own field no longer counts the collar; M10b's
    coral ring, `--collar on`, still counts). The GLB primitive has the Body's attributes but the skin weights:
    `COLOR_0`, `NORMAL`, `TANGENT`, `TEXCOORD_0` to `TEXCOORD_5`, and since M11 `TEXCOORD_6` (the later mouths'
    contact, 0 on the collar; an M10c kit's collar lacks it, and the page must read 0 there).
  - **The join, chosen on a grid of eleven variants** on `e80_p85_w80` (`M10c/try/`, sheets `M10c/godot/try*/`):
    the normal blend (0, 0.5, 1) and the UV pull hardly showed; what mattered was the reach (M10b's sphere limit left
    the brow trench), where the inner end sits (at the equator it showed through the lids' open corners as a dark
    seam) and the ends of the covered arc (wider smoothing or a gap minimum gave cracks and fins down the dome's
    side; the shrink removed them).
  - **The grid** (`M10c/grid/<cell>/`, the 27 cells under M10b's names, every one rebuilt with the blended thumb of
    PR #245's review fix; the 100 % row is M8b's unit with no collar): sheets `M10c/godot/grid/grid_e<eye>_w<width>.png`
    and `grid_manic.png` (M10b's layout and Ukrainian labels). **The pick stays eyes 80 %, lips -15 %, width 0.80**,
    built as `M10c/export/`. At 80 % and 90 % the eyes now read smaller, from the front and at 1.2 m.
  - **The gate** (`M10c/godot/head/head.png`, M8b against the pick and against `e80_p75_w86`): the Body's rest
    vertices against `M8/export` move 0.0 mm (`M10c/export/cmp_m8b.json`); the plain-grey skull with no part changes
    0.0000 of the pixels in the front, 3/4 and profile views, and the silhouette 0 px; in the top view 0.0048 and 485
    px, all of them the thumbs in Idle (the blended thumb). With the parts: 4.9 / 4.1 / 2.2 / 3.3 %.
  - **The kit:** glTF-Validator 0 errors (1 warning `NODE_SKINNED_MESH_NON_ROOT`); `godot-check --textured` the same
    seven pack-contract failures as M10 and 21 of 68 surfaces textured (the four collars now take the skin's maps).
    No Body vertex carries more than four weight groups after `alien_thumb` (counted in Blender on the pick).
  - **Open:** from straight above, a nub of skin a few millimetres long still shows at the top of the bored dome's
    temple side (`M10c/godot/socket/`, third column); from 3/4 at 0.4 m the far eye's nose side shows the skin
    bridge to the nose where M8b's dome sat.
- **M12, the red pout mouth mp1** (brief UPDATE 16 and 17; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M12/`): a third mouth design, `pout`, beside frog and overbite, from
  the sheet `D:/prime-art-raw/2026-10-20-alien-face-sheets-2/mp1/` (six shapes, the panel order rest, M, small, A, E,
  O). Built on M10b's pick (`M10b/export`); the Body, the skull, the eyes and the other mouths are untouched.
  - **Measuring (`alien_mouths.py`):** the same panels, stations and sheet-to-head mapping as frog and overbite, with
    a design's own pixel classes and scales. mp1's red lips have blue about green, which the coral lip class half
    called tongue (`PALETTE`: the lip/tongue split at B - G -0.008); its dark-red inside grades into the lips, so in A
    and E a lip pixel needs R >= 0.50 (`PALETTE_SHAPE`; at 0.30 the openings measured half their size and the lips too
    tall; the closed shapes and O keep 0.30). `SHAPE_SCALE_DESIGN` (A 0.95, E 0.90, O 0.94: the sheet's A and E are
    about as wide as rest). Two ring rules for the pout only: `CUP_IN` (the dark cup ends 0.6 of the lip's half width
    inside its axis) and `CORNER_CLOSE` (in A and E the lips move into the opening toward the corners, up to their
    half width from |cos| 0.55 to 0.92): the sheet's E runs out in a long thin dark slit between thin rims, which read
    as black flaps at 0.4 m (M13 removed `CORNER_CLOSE`, off since M12b, and M12's `ring`/`ring_corner`: the
    designed rings replaced them). Frog and overbite measure and build exactly as before (every new table is per design).
  - **The lips (`alien_lips_geom.LIP_SHAPE_POUT`):** the sheet's thickness per lip (upper 0.95, lower 1.10: the lower
    the bigger cushion; the frog's upper is 0.82), ends a little rounder than the frog's (corner 0.18, pw 2.0), the open
    rings' own corner 0.45 (`ring_corner`), a soft bow (0.25, side peaks 0.15: at 0.45 / 0.40 the upper lip read as
    four lumps), M8's section, depth_corner 0.35; `size` (new: the whole mouth, x and height, about the face's centre
    line and the socket's height, `scale_size`) 0.95 and `plump` 1.15. The rest piece is 77.8 x 51.4 mm (frog at M10b:
    about 91 mm wide).
  - **The grid** (`M12/godot/grid4/grid.png`, JPEG `showroom/m12-grid.jpg`; the grid kit `M12/grid_export/` with
    `lipvar_<variant>_pout_<shape>` nodes): size 0.85 / 0.95 / 1.05 x fullness 1.00 / +15 %, each rest front and 3/4 at
    0.4 m, 3/4 at 1.2 m, A at 3/4, O, under the sheet's rest, A, O, E and m2's second head. **Pick 0.95, +15 %**: the
    closest to the sheet's and m2's compact full pout; 0.85 reads small at 1.2 m, 1.05 brings A's lower lip near the
    chin.
  - **`alien_m12.py`** (the kit step; about 50 s): opens a kit, builds the six `mouth_pout_<shape>` on the Mouth socket
    (`--lips` merges over `LIP_SHAPE_POUT`, `--grid` adds variants), their material `alien_lip_pout` (a copy of
    `alien_lip`: deep red, roughness 0.32, a clear coat), bakes their AO (`alien_m6.bake_parts_ao`, each piece alone
    with the skin), writes the pout's skin contact into Body's **seventh UV layer** `contact_mouth2`
    (`alien_lips_geom.CONTACT_UV_MOUTH2`: glTF `TEXCOORD_6`, u pout, v free for the next mouth; Godot `CUSTOM2`; v stored
    flipped), marks `alien_hue` with `{"prime_contact_mouth2": "custom2_xy"}` and exports. Contact: 347 touched / 136 full
    vertices. It refuses a Body without exactly the six layers of `alien_m6` (the new one must be the seventh), so it
    runs last: `alien_m6.py` and `alien_m8.py` on an M12 kit stop at their own layer check.
  - **Godot (`alien.gd`):** `MOUTH_DESIGNS` frog, overbite, pout; `show_mouth` skips a design the kit lacks (the pout has
    no flipbook shells and shows its 3D pieces in both modes); `LIP_LOOK_POUT` on `alien_lip_pout` (albedo sRGB (0.72,
    0.18, 0.18), deep (0.42, 0.05, 0.07), roughness 0.30, specular 0.55, clear coat 0.55 at 0.12: the wet highlight);
    `CONTACT_CHANNEL2` {pout: 0} picks `contact_pick2` (`alien_hue.gdshader`: the max also over `CUSTOM2.xy`, off by
    default).
  - **The talk style (`alien_talk.gd`):** a phase line (`LINE`, 5.3 s: words of 1-3 phases, syllables 40-260 ms, word
    gaps 60-200 ms, two sentence pauses) and per design `STYLES`: frog and overbite keep their snapped talk; the pout
    follows 25 ms late, merges phases under 70 ms, shows A and E under 85 ms half open (`small`), shows M in gaps
    under 120 ms, its lower lip springs after every change of shape (1.4 mm x the change in openness, 6.5 Hz, 140 ms
    decay) and its lips purse between words (pucker 0.8 over gaps from 100 ms). The motion is two instance uniforms of
    `alien_lip.gdshader` on the shown piece (`lip_drop` moves the part below the seam down; `pucker` narrows x by 14 %
    and moves the centre 3 mm forward; both 0 by default). `alien.gd` `talk_at(t_ms, line)` renders any moment,
    `play_line(line)` drives it in time.
  - **`m12_shots.gd`**, the proof (modes `grid`, `phases` with `noblack.png`, `talk` (pout and frog), `video` (the line
    at 30 fps during Talk_Upper, 3/4 at 0.6 m and front at 0.45 m; `encode_clips.py` makes the MP4s), `clips`, `hues`,
    `head` with a mouth per kit).
  - **The gate** (`M12/godot/final/head.png`): M10b (frog) against M12 with frog changes 0.0000 in all four views (with
    parts, the plain-grey skull, the silhouette); against M12 with the pout 2.06 / 2.07 / 1.27 / 0.69 % (front / 3/4 /
    profile / top), all of it at the mouth, the skull 0.0000 and 0 silhouette pixels. The Body against `M8/export`:
    `M12/export/cmp_m8b.json`.
  - **Open after M12** (fixed by M12b below): O kept a small slit, not the sheet's round hole; A's lips were a little
    crumpled at 3/4 with a small dark notch at the far corner; the flipbook test has no pout atlas.
- **M12b, the pout's open shapes** (brief UPDATE 19; output under `D:/prime-art-raw/review/char/alien-parts-kit/M12b/`):
  A and E looked crumpled and torn (rims waving round the opening, the roll's thickness changing along it, a ragged
  inner edge, the far side folding at 3/4), E's corners were sharp spikes, O a puckered slit, and the upper lip's bow
  read as two balls. The pout only; frog and overbite build exactly as before (every new key is in
  `LIP_SHAPE_POUT`), and the size 0.95 / plump 1.15 pick is kept.
  - **Designed rings (`alien_lips_geom.ring_param`, `LIP_SHAPE_POUT["ring_param"]`):** the open shapes no longer trace
    the sheet's contours (their low-passed waves were the crumpling and E's long thin slit made the spikes). From the
    panel's measured scalars (`alien_mouths.ring_measure`: the lips' outer centre and half width, the opening's centre
    and half height, each lip's thickness at the centre) the opening is a superellipse (A n 2.1, E 2.0) of the measured
    half height and the outer half width less the corners' thickness, and the lips an even roll laid off its edge
    along its normal: the measured mean thickness times full x plump and upper/lower, blended round the ring, tapering
    to `corner` of it at the corners (A 0.68, E 0.60, exponent 2.5), the bow (0.12) on the upper lip's top. An
    outward offset of a convex curve never folds, so the corners are round (the outline's sharpest turn is the bow's
    notch). In the build: no low pass, the depth from the width without the bow, the corners tucked 35 % of their
    depth into the skin with half the constant depth (`tuck`, `depth_corner`), the cheek-side shrink milder
    (`side_keep` 0.85), `CORNER_CLOSE` off, A 4 % wider (`wide`). **`n_flat` 1:** a ring stands out along the mouth's
    mean skin normal, not each point's own: the philtrum's and chin's slopes tilted the top and bottom of the ring
    toward each other and closed O's hole to a slit (measured: 0.4 mm from the centre at the bottom).
  - **O:** a round hole of 0.30 of the half width (`hole`) in an even ring (`corner` 1.0, `thick` 0.9), the sheet's
    M-shaped top (bow 0.30), and its dark cup lifted along the mean normal to 0.85 of the lips' axis depth
    (`cup_throat`; `cup_lift` is the same as a share of the push): the cup on the skin left a 20 mm tunnel whose lit
    inner wall read as a pale triangle in the hole. The cup's rim stays inside the lips.
  - **The bow (rest, M, small):** 0.14 over `bow_w` 0.16, side peaks 0.10 (M12: 0.25 / 0.10 / 0.15), and `bow_flat` 1:
    the tube's depth comes from the lip without the bow (`flat_bow`), so the bow notches the outline only and the upper
    lip's front is one continuous roll.
  - **Grids** (`M12b/godot/g1..g5/vgrid.png`; JPEGs `showroom/m12b-vgrid_*.jpg`): g1 corner 0.60 / 0.75 x n 2.0 / 2.5
    (all far better than M12; 2.5 boxy), g2 + O's hole, g3 `n_flat` 0 / 0.5 / 1.0 (only 1.0 opens O), g4 O's hole, bow
    and `cup_lift`, g5 `cup_throat` 0.6 / 0.85 with hole 0.26 / 0.30.
  - **`m12_shots.gd`:** modes `vgrid` (a reference row of the sheet's mouths, then the hero's own pieces and each
    `lipvar_` variant at spec `vgrid` views, 0.4 m) and `compare` (`compare_closed.png`, `compare_open.png`: per shape
    the sheet's mouth, then the first kit's pout above the hero's, front / 3/4 / profile at 0.4 m and 3/4 at 1.2 m).
  - **The talk style** (`alien_talk.gd`) is unchanged; the MP4s are re-rendered on the new pieces.
- **M13, the fangs mouth mg2 and the pout's talk fixes** (brief UPDATE 20 and 21; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M13/`): a fourth mouth design, `fangs`, from the sheet
  `D:/prime-art-raw/2026-10-20-alien-face-sheets-2/mg2/` (rest, M, small, A, E, O), and PR #246's review minors.
  Built on M10c's pick (`M10c/export`); the Body, the skull, the eyes and the frog and overbite are untouched.
  - **One mouth step (`alien_m12.py`):** one run adds every new mouth onto a kit (`--designs pout,fangs`, the
    default), so the chain is eyes -> mouths: `run_script("alien_m12.py", ["--kit", <eyes kit>/export, "--out", <dir>,
    "--orm-sss", <its skin_pick_eyes/textures/orm_sss.png>])`. It refuses a Body without exactly alien_m6's six UV
    layers (an M12 or M13 kit is fine: it drops its own seventh layer first). `--lips`, `--lips-fangs` and `--fang`
    merge over the designs' shapes; `--grid` takes `"design"`.
  - **The lips (`alien_lips_geom.LIP_SHAPE_FANGS`):** the kit's coral `alien_lip`; thin rolls (upper and lower 0.80 of
    the measured centre, plump 1.4), round soft ends (corner 0.30), almost no bow (0.05: a flat calm line), the sheet's
    width (the rest piece about 105 mm wide, the frog's about 91); A, E and O designed rings as the pout's (UPDATE 19),
    A 0.95 and E 0.90 of the panel. Measuring: the fangs cross the lips in every panel, so their columns (3 px wider)
    are refilled from the clean columns beside them (`alien_mouths.FILL_TEETH`, `fill_teeth`).
  - **The fangs (`alien_fangs_geom.py`, `alien_mouths.build_fangs`):** two blunt ivory cones per piece, 20 mm long
    (30 % of it a root hidden behind the lower lip), 13 mm wide at the base, a round tip of half that, a slight curve
    toward the centre line, the section a little flattened. They stand on the built lips (`fang_roots`): closed shapes
    at 0.72 of the lips' half width on the lower lip's top (the crease), A and E at 0.80 of the opening's half width on
    the lower lip's inner edge, O on the cheek 2 mm past the pursed ring, 0.40 of its half height below its centre. The
    axis stands 0.70 of the fang's depth in front of the lips' front at each height (a ray cast on the piece's lip
    faces; the opening bridged) and is smoothed, so the fang rises from behind the lower lip and stands before the upper
    lip; O's is one straight line moved forward until it clears (a smoothed axis kinked where the ring ends). Grids:
    `M13/godot/gf1/vgrid.png` (length 16 / 19 / 22 mm x place 0.62 / 0.72), `go1/vgrid.png` (O's place). Material
    `alien_fang` (Blender: a copy of `alien_lip`, ivory; Godot `FANG_LOOK` on the lips' shader).
  - **The jaw weight (`alien_m12.jaw_weights`, COLOR_0.g; COLOR_0.a since M13b):** 1 on the lower lip, the tongue and
    the fangs, 0 on the upper lip; round an open ring a smooth step at the opening's centre height; times a falloff
    to 0.3 at the corners. COLOR_0.r stays the baked AO.
    `PART_AO_MARKER` goes on the new materials only when the AO was baked.
  - **Godot (`alien.gd`):** `MOUTH_DESIGNS` + fangs, `CONTACT_CHANNEL2` {pout: 0, fangs: 1} (TEXCOORD_6's v, CUSTOM2.y),
    `FANG_LOOK`, `MOVING_DESIGNS` (pout, fangs): their cup and tongue take `alien_mouth_part.gdshader`, so with the lips
    and fangs (`alien_lip.gdshader`) everything of the shown piece moves on `alien_mouth_motion.gdshaderinc`
    (`lip_drop`, `pucker`, `jaw_thrust` times the jaw weight, COLOR_0.a since M13b). The motion is the s5 look's; `set_mouth_motion` skips
    otherwise. `listen()` ends a playing line.
  - **The talk (`alien_talk.gd`):** the bounce uses the signed change in openness (a closing presses the lower lip up,
    an opening sags it) and a closed shape only ever presses; `LINE` (5.3 s) now triggers every rule (two merged
    flickers, a 75 ms E shown half open). The fangs' style: a 40 ms lag, `rise` (A, E and O after a closed shape show
    small for 60 ms: a heavier jaw), `thrust` (the lower jaw 2.2 mm forward on A and E over 120 ms), a bounce of half
    the pout's, no pucker. `godot/alien/talk_check.gd` runs `styled()`/`sample()` headless and
    `tools/tests/test_alien_talk_godot.py` checks each rule (heavy: it needs Godot).
  - **`m12_shots.gd`:** spec `design` (the design every mode shows), `talk_also`, `hero_label`.
- **M11, the lashes eyes el2 and the collar minors** (brief UPDATE 21; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M11/`). The female look of the sheet
  `D:/prime-art-raw/2026-10-20-alien-face-sheets-2/el2/`: black, glossy, curled upper lashes, bolder and longer toward
  the temple, the outer ones winging out past the corner, a dark lash line; none on the lower lid.
  - **The collar minors (PR #247's review):** the skin collar's section starts on the skin the ray hit (`h_hit`; a hit
    over 4 mm from the smoothed `h_edge` keeps the smoothed start, `far_bins` in the report), so it no longer floats or
    sinks where the brow trench's depth changes; `UVMap` runs along the section (`COLLAR_SKIN` `uv_run` 1,
    `section_run`: the skin's UV gradient outward from the edge, measured over `uv_probe_mm`, times the arc length,
    mirrored onto the face outside the edge), so its triangles have UV area and defined tangents; the collar carries the
    Body's seventh layer `contact_mouth2` (`TEXCOORD_6`) at 0.
  - **The lashes (`alien_lashes.py`, the kit step; `alien_lashes_geom.py`, the plain geometry):** per design and side
    `eye_<design>_lashes_<side>`, one mesh, a child of `eye_<design>_lid_upper_<side>` with an identity local transform,
    so it turns with the lid in every blink and lid state and shows with its design; built in the lid's frame from the
    kit's own lids (`character.json` `m6`: the lid setting and corners) at the ball's radius, so it fits every eye size
    (every length is a share of r). Each lash roots on the rolled rim (`root_a_deg` from the outer surface, sunk `sink`),
    leaves `lift_deg` above the radial and bends up by `curl_deg` toward its tip, splays toward its side (`fan_deg`), a
    tapered, slightly flat tube with a round tip; `count` lashes from `t_in_deg` to `t_out_deg` of latitude, closer and
    longer toward the temple, the last `wing` longer still (`wing_len`) and swept out (`wing_sweep_deg`). The liner is a
    lens hugging `liner_deg` of the roll from `liner_t_in_deg` to the last lash. `design_lift_deg` gives a design its
    own lift: the manic lids rest 50 degrees up. Material `alien_lash` (Principled near black, roughness 0.28, coat
    0.6; extras `prime_lashes`). The step checks both designs in every lid state (open, rest, half, closed) for lash
    vertices inside the skin (Body and collars), the ball and the lids, and refuses a clipping kit; `--grid` adds
    `lashvar_<variant>_<design>_<side>` nodes.
  - **The pick, on five grids beside el2** (`M11/godot/g1..g5/lgrid_<design>.png`, JPEGs `M11/showroom/`): g1's thin
    lashes over the whole edge (nine, 0.02 to 0.04 r) were hardly visible from the front, since they pointed at the
    camera; el2's lashes sit on the outer half and wing out. Pick: seven lashes from latitude 0 to 74 degrees, 0.35 to
    0.80 r long, 0.075 to 0.11 r at the root (tip 0.25), lift 30 and curl 75 toward the tip (`curl_pow` 2.2: a hook in
    profile), the last two 1.4 times longer and swept 45 degrees out; the liner 0.03 r thick at the roll's front (60
    degrees; at 40 and 0.05 r it read as a cable on the lid from close up). The manic lids rest 50 degrees up: with the
    bored lift their lashes lay along the dome like a fringe, so `design_lift_deg` manic is 0 (g4; below 0 they tangled
    in profile). No variant clips in any lid state.
  - **Godot (`alien.gd`):** `set_lashes(on)` (default off: the same eyes serve both looks), `has_lashes()`;
    `alien_lash` gets `LASH_LOOK` (a StandardMaterial3D: near black, roughness 0.32, specular 0.55, clear coat 0.6 at
    0.15). `m11_shots.gd`: `lgrid`, `lviews`, `lblink`, `lsizes`, `lmouths`, `lhues`, `lgame` (3.5 m and a shimmer
    measure), `lvideo`, `head`, `socket`.
  - **The kit** (`M11/export/` = M10c's pick e80_p85_w80 rebuilt with the fixed collar (`M11/e80_eyes`), M10c's lips
    (`e80_lips`), the pout (`alien_m12.py`, `e80_base`), then `alien_lashes.py`; `e90_lashes/` and `e100_lashes/` the
    same at 90 and 100 %; drivers `tools/out/m11/chain.sh`, `lashes.sh`, `final.sh`): glTF-Validator 0 errors (1
    warning `NODE_SKINNED_MESH_NON_ROOT`), `godot-check --textured` the same seven pack-contract failures, the Body
    against `M8/export` 0.0 mm. After merging M13 (#248), `M11/export/` is rebuilt as `e80_lips` -> `alien_m12.py`
    (pout and fangs, `M11/e80_mouths`) -> `alien_lashes.py`, so it carries the lashes and all four mouths; the lashes
    step still finds no clipping. `alien.gd` keeps both: `alien_lash` in `setup()`'s face materials beside
    `EXTRA_FACE` and the moving cups and tongues (`MOVING_PARTS`). The check (`M11/godot/merge/`, a temporary script,
    not kept): lashes on, bored and manic with the pout and the fangs; in a blink's closed hold while talking each
    lash set keeps its upper lid's transform (0 rotation, 0 offset), and both mouths walk the line's pieces.
  - **The gate** (`M11/godot/final/gate/head.png`): the kit with the lashes off against `e80_base` changes 0.0000 in
    all four views (with parts, the plain-grey skull, 0 silhouette px); on, 0.31 / 0.28 / 0.14 / 0.24 % (front / 3/4
    / profile / top), the lashes alone. The collar fix against M10c (`collar/head.png`): 0.20 / 0.13 / 0.03 / 0.08 %,
    at the collar; the skull 0.0000.
  - **Open:** at 3.5 m (FOV 70, 1536 px) the lashes are under a pixel thick and draw as a broken dark line at the
    outer corners (`lgame.png`); the mean frame-to-frame change round the eyes in Idle with a blink rises from 0.0094
    to 0.0121 with them. From straight above, the bored dome's temple-side nub of M10c is still there
    (`collar/socket.png`).
- **M11b, PR #249's review fixes and the lashes' look** (brief UPDATE 23; output under `M11/godot/m11b/`, JPEGs
  `M11/showroom/m11b-*.jpg`; drivers `tools/out/m11/m11b.sh`, `g.sh` with `grid6..8.json`).
  - **The game distance (the major):** the liner is its own node, `eye_<design>_liner_<side>` (a sibling of the tubes
    under the upper lid, the same material; `character.json` `nodes.lash_liners`). `alien.gd` gives each tube mesh a
    visibility range (`LASH_FADE_M` 3.0, `LASH_FADE_MARGIN_M` 0.6, fade SELF, Forward+; the other renderers cut them)
    and keeps the liner at every distance, so past about 3 m the lashes read as one dark line along the lid. At 3.5 m
    the modelled liner covered about one pixel and broke into dashes, so it takes its own shader,
    `alien_liner.gdshader` (`alien_lash_liner`, `LASH_LOOK`): where its band (`band_m` 4 mm) would cover fewer than
    `LINER_MIN_PX` 2 pixels, each vertex moves out along its normal by 0.55 of the missing width (at most 4 mm), so it
    stays one unbroken line; below about 2.4 m nothing moves. The liner casts no shadow: a light's shadow camera
    stands far away, and the growth there ballooned the band into a shadow over the whole face (the first try).
    `m11_shots.gd` `lfade`: both designs from 1.2 to 4.5 m; `lgame` also measures Idle without the blink at 3.5 and
    3.0 m (the line's own crawl apart from the lid's motion).
  - **The look (grids g6 to g8 beside el2):** thickness x curl (g6), lean x curl (g7), manic's lift x lean (g8). Pick:
    root width 0.12 to 0.19 r (`flat` 0.6), curl 160 degrees evenly (`curl_pow` 1) from a lift of 10, every lash
    leaning toward the temple (`fan_bias_deg` 45, 0.3 to 1 of it inner to outer), the liner 0.06 r over 130 degrees
    of the roll and 1.8 times as thick at the outer end (`liner_out`). The thin wires and the comb in profile are gone:
    the lashes curl back over the lid. A design's own keys go in `design` (`for_design`): manic leaves 30 degrees below
    the radial, leans 25 and ends at 66 degrees, so its lashes stand out of the dome's outline as in el2's wide panel.
  - **The clip check** also counts edges through the skin, the ball and the lower lid (`edge_crossings`,
    `ball_edges`) and refuses a set nearer the skin than `CLEAR_MM` 0.5; it names the nearest vertex
    (`skin_least_u`, `skin_least_vi`). Manic's last lash root touched the skin with the lid open at 74 degrees; at 66
    every set keeps 10 mm (the search reach) from the skin in every lid state.
  - `alien_lash` is one-sided (`use_backface_culling`: glTF `doubleSided` false).
  - **The collar (minors 1, 2, 5):** a bin whose UV probe fails takes the last good bin's gradient, wrapping round the
    ring (`alien_lids_geom.last_good_cyclic`; the right collars' first bins took zeros); a far bin's start runs
    linearly between the nearest good bins' offsets from the smoothed edge (`cyclic_fill`), so a far run meets its
    neighbours with no step (`start_step_mm_max` in the report); a test reads the kit's collars from the GLB
    (`TEXCOORD_6` all 0, the Body's attribute set). The bored dome's nub from above stays: it is not the boundary step.
  - **Proofs** (kits `M11/b80_*`, `b90_*`, `b100_*`: the fixed collar, the lips, main's `alien_m12.py` with M13b's
    fangs, then the lashes; `M11/export` the 80 % pick): the gate with the lashes off 0.0000 in all four views; on
    0.42 / 0.41 / 0.22 / 0.44 %, lash pixels only, the skull 0.0000. The shimmer at 3.5 m (Idle with a blink) 0.00941
    off, 0.01125 on (M11: 0.0121); Idle alone 0.00726 / 0.00765, the line's own crawl +5 %. Closed, the curled lashes
    point up from the lid's line (blink frames), where el2's hang down: open.
- **M13b, the fangs mouth mg2 brought to the sheet** (brief UPDATE 22; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M13b/`): M13's lips read as thin flat double sticks with pointed
  corners at 3/4, its fangs as small pins hanging in front of the lip (floating on the cheeks in O, jumping sideways
  between shapes), A as a flat box. Built on M10c's pick like M13; the frog, overbite and pout pieces are unchanged.
  - **The lips (`alien_lips_geom.LIP_SHAPE_FANGS`):** soft rolled lips: the sheet's crease measures low (the upper lip
    about 15 px, the lower 4.5 px at the centre), so the factors are against that: upper 0.55, lower 1.45, plump 1.25
    (the upper a thin roll, the lower the fuller cushion); `lower_fwd` (new) puts the lower lip 1.5 mm further
    forward; `downturn` (new, closed shapes: both lips and the line between them `downturn` x |s|^2.5 lower toward the
    corners) 4 mm, mg2's grumpy-cute line; width 0.85 (about 89 mm, M13's 105) so the fangs stand just inside the
    corners; rounder, deeper-tucked ends (corner 0.60, depth_corner 0.20, and the new per-shape `corner_share` 0.22,
    `corner_tuck` 1.4 over `alien_mouths.CORNER`). The rings take their own `upper`/`lower` (A and E 0.62 / 1.15, O
    0.62 / 1.30); A is a real jaw drop (`open` 1.25, `drop` 1.15, an even roll all round, ring corner 0.85,
    `SHAPE_SCALE_DESIGN` A 1.08), E 0.95. The fangs' rings stand on the face's centre line (A's measured centre was 3.5
    mm aside). Grids `M13b/godot/g1..g5/vgrid.png` (lip fullness x fang size, corners, width, fang curve, O).
  - **The fangs (`alien_fangs_geom.FANG`, M13b's `FANG_M13B` over M13's):** 25 mm long, 15 mm at the base, the tip 0.42
    of that, a convex taper (pw 1.3), leaning a little outward (curve -0.08: mg2's tips lean out), 15 % of the length
    a root in the lower lip. **One place:** `x_m` 34 mm from the face's centre line in rest, M, small, A and E, so they
    only move with the jaw (A's and E's roots `ring_drop` 0.40 / 0.25 of the ring's half height below its centre, on
    the lower lip in the opening's corner); O's attached to the pursed ring's sides (`o_in` 0.6 of the base radius
    inside its edge, `o_drop` 0.80). The axis keeps the nearest lip's front above and below the lips (`keep_front`; the
    skin's bent the tip back toward the philtrum, a flat top from the front), sunk `sink` 1.0 behind the lower lip's
    front at the root and standing `out` 0.50 in front of the upper lip over `blend` 0.30 of the length.
  - **The tongue:** A and E build a designed tongue in the designed opening (`ring_param` `tongue` (width share, height
    share): A 0.72 / 0.80, E 0.80 / 0.70; `alien_mouths.build_tongue_ring`); the measured one was a small blob in A and
    ragged in E (the refilled fang columns broke its run). The measured route smooths its base for the fangs.
  - **The fangs' look (`alien.gd FANG_LOOK`):** a creamier ivory with a warmer, deeper root over a wider AO range, more
    AO occlusion, warm SSS and transmittance (0.35 / 0.40, colour (1.0, 0.80, 0.56), depth 6 mm) through the thin tip.
  - **The jaw weight moved to COLOR_0's alpha** (PR #248's review minor 4; `alien_m12.jaw_weights`): the colour is the
    grey AO again, so a viewer that uses vertex colour as albedo does not tint the mouths; the pieces are opaque. The
    shaders read `COLOR.a` (`alien_mouth_motion.gdshaderinc`, `alien_lip.gdshader`, `alien_mouth_part.gdshader`); an
    M13 kit (the weight in g, alpha 1) moves its whole piece, so rebuild it. Every pout and fangs piece in the kit gets
    the weight, not only the run's (minor 3), and the fangs take the corner falloff per vertex like the lip under them
    (minor 6).
  - **The talk (`alien_talk.gd thrust_at`):** the jaw thrust eases in from the start of a chain of touching A/E runs
    (after the rise), holds through it (A -> E no longer snaps to 0) and eases out after (PR #248's minor 2).
  - **Tests:** `godot/alien/parse_check.gd` + `tools/tests/test_alien_parse_godot.py` (heavy, area `alien_parse`):
    every `godot/alien` shader parses in the dummy renderer (a broken one logs `SHADER ERROR` and lists no uniforms)
    and `alien.gd`/`alien_talk.gd` reload (minor 7). `m12_shots.gd` vgrid views take an optional distance.
- **M14, the tongue mouth mt2** (brief UPDATE 25; output under `D:/prime-art-raw/review/char/alien-parts-kit/M14/`): a
  fifth mouth design, `tongue`, from the sheet `D:/prime-art-raw/2026-10-20-alien-face-sheets-2/mt2/` (rest with the
  tongue out at one corner, M with its tip between pressed lips, small resting on the lower lip, A lolling out of the
  dropped jaw, E out of one corner, O with its tip out of the round opening). Built on M10c's pick by the same mouth
  step (`alien_m12.py`, `--designs pout,fangs,tongue`, the default); the Body, the skull, the eyes and the other
  mouths are untouched.
  - **The contact layout:** `TEXCOORD_6` is full (pout, fangs), so the tongue's skin contact is Body's **eighth and
    last** UV layer `contact_mouth3` (`alien_lips_geom.CONTACT_UV_MOUTH3`, glTF **`TEXCOORD_7`**: u tongue, v 0; v
    stored flipped like every layer). Godot imports `TEXCOORD_6` and `TEXCOORD_7` together as `CUSTOM2` (xy, zw), so
    the tongue's channel is `CUSTOM2.z` (`alien_hue.gdshader` `contact_pick3`, `alien.gd CONTACT_CHANNEL3`). The mouth
    step rewrites both layers in that order; the contact counts only the rest piece's lip faces (the tongue hanging in
    front of the chin is no lip contact). Blender allows eight UV layers, so a sixth mouth needs a shared channel.
    M11's collar (`alien_m6.py`) carries six UV layers (`TEXCOORD_0..5`), so it has neither `TEXCOORD_6` nor
    `TEXCOORD_7` (no tongue contact on the collar, as wanted). **Unchecked (PR #251's review):** on a mesh with
    `TEXCOORD_6` but no `TEXCOORD_7`, `CUSTOM2.z` is taken as 0 but `CUSTOM2.w` may read 1 (a default alpha), not 0.
    Harmless today (`w` is never picked); a sixth mouth in `TEXCOORD_7`'s v must first check that every surface it
    shades carries `TEXCOORD_7` (or use another channel), else it shades there at full contact
    (`alien_hue.gdshader`'s comment says the same).
  - **Measuring:** the tongue covers the lower lip in every panel, so the columns where its lip pixels below the tongue
    are fewer than half the usual lower-lip thickness are refilled from the clean columns beside them
    (`alien_mouths.FILL_TONGUE`, `tongue_cover`, then `fill_teeth`). M's lips are pressed shut (the sheet's seam);
    the open closed-form pieces (rest, small) have the dark between the lips, stopping short of the corners (on the
    skin it showed as a dark dot past each tucked corner).
  - **The lips (`alien_lips_geom.LIP_SHAPE_TONGUE`):** the kit's coral `alien_lip`, full soft rolls (upper 0.85, lower
    1.10, plump 1.20), round tucked corners, a soft bow, width 0.90; A, E and O designed rings as the pout's and the
    fangs' (O a fuller ring with a bigger hole: hole 0.36, thick 1.15).
  - **The tongue (`alien_tongue_geom.TONGUE`, `alien_mouths.build_tongue_out`):** one size in every shape (39 mm wide,
    7.5 mm thick, the root 0.68 of the width: a spatula, widest at 0.75 of its length; a soft centre groove; a thin
    round tip). Per shape it is only placed (`shapes`: x as a share of the lips' half width, `inside`, `wrap`, `hang`,
    `slant`, `roll`): the nearest lower-lip section gives the lip's roll (its axis, depth and half height, an
    ellipse); the spine runs from inside the mouth (its root `dip` 7 mm lower, into the dark) onto the roll's top,
    wraps over its front by `wrap` degrees, hangs `hang` further, leaning `slant` sideways and twisting `roll`; a
    station below the lip stays its half thickness plus 1.2 mm in front of the chin. `drape` then lifts the sections
    where the underside would cut the real lip (a downward ray per underside vertex, smoothed round each section and
    along the tongue: column by column it crumpled the root). Grid `M14/godot/g1/vgrid.png` (width 32 / 36 / 40 mm,
    shorter hangs): the sheet's tongue is about 0.42 of the rest mouth's width, so 39 mm, with the shorter hangs for A,
    E and O. Material `alien_tongue_pink` (Godot `TONGUE_LOOK` on the lips' shader: a saturated soft pink, a deeper
    rose in the AO, a soft wet sheen).
  - **The teeth (`alien_tongue_geom.TEETH`, `build_teeth`):** three blunt cream teeth, uneven in size and tilt: two
    upper ones either side of a gap and one lower one on the left, each a rounded box (a superellipsoid) tucked 3 mm
    into its lip's inner edge, its front half the lip's depth in front of the lip's axis (set back, the AO bake made
    it black), its visible height at most 0.55 of the opening; in rest, small, A and E (O's hole and M none).
    Material `alien_tooth` (`TOOTH_LOOK` over `FANG_LOOK`). Its jaw weight: the upper teeth 0, the lower ones the
    lips' corner falloff (`alien_m12.py jaw_weights`, `env(x)`: 1 up to `JAW["from"]` of the lips' half width, down
    to `JAW["corner"]` at the corners).
  - **The talk (`alien_talk.gd` `STYLES["tongue"]`):** loose and floppy: a 35 ms lag, merged flickers and half-open
    quick A/E as the pout's, every second styled run 25 ms late with the run before it holding on (`lopside_ms`), a
    slow soft lower-lip bounce (1.2 mm, 4.5 Hz, 170 ms), and `flop` (`flop_at`): after each change of shape the
    tongue's tip holds 45 ms, then moves `amp` (3.5 mm) x the signed change in openness x cos(2 pi 4 Hz dt) x
    exp(-dt / 220 ms) (an opening leaves the tip up, then it swings down past and settles) and sways 1.5 mm to the
    left on one run and the right on the next. `alien_mouth_motion.gdshaderinc` moves the tongue by the instance
    uniform `tongue_flop` times its flop weight (`TEXCOORD_1`'s u: 0 up to the lip's top, rising to 1 at the tip,
    Godot `UV2.x`) times the material's `flop_mask` (1 only on `alien_tongue_pink`).
  - **PR #250's review minors:** `alien.gd` warns when a talking piece's COLOR_0 alpha is 1 everywhere (an M13 kit);
    `fang_roots` moved to `alien_fangs_geom` and `test_one_fang_place` tests it; `parse_check.gd broken` parses a
    deliberately broken shader (`test_a_broken_shader_is_caught`); the M13 line names the jaw weight's alpha. The
    fangs' 3/4 lip tail past the fang is not changed (see `handoff-M14.md`).
  - **M14b (PR #251's review):** the tongue's tip was knife-thin in profile (its half thickness fell by
    `c ** 0.5 * (1 - 0.45 q)` over the tip): now `TONGUE["tip"]` (`c ** 0.25 * (1 - 0.2 q)`, never below 0.5 of the
    half thickness before the last station, never thicker than wide; `test_tip_plump_in_profile`), and the tongue
    10 mm thick (grids `M14/godot/g2`-`g4`: 7.5 mm read as a strap in profile, 11 mm as a sausage), its underside
    0.75 of its top. The groove 0.70 of the half thickness where it hangs, 0.45 of that up to the lip's top
    (`groove_root`: deep there it notched the root's top edge). Per shape a width share (`shapes[...]["w"]`: O 0.75,
    narrower than its ring's hole; `shape_params`). `drape`: the section's two side vertices take their neighbours'
    lift (the side stayed down while top and underside rose: the 3/4 view's white rim), 10 smoothing passes, and the
    sides aimed 0.5 mm into the lip (`TONGUE["drape"]["sink"]` = `clear` + 0.5 mm). The teeth per shape
    (`TEETH["per_shape"]`, `teeth_for`): A has the sheet's two lower teeth at the opening's lower left (the one at
    -24 mm sat in the ring's side, out of sight), further forward and tucked deeper. `TONGUE_LOOK` a deeper salmon
    pink (albedo (0.80, 0.33, 0.36), deep (0.52, 0.12, 0.17); the first read as pale bubblegum beside the sheet).
    `has_jaw_weight` runs in debug builds only and is cached per mesh; `parse_check.gd` tests it on made meshes
    (`test_jaw_weight_check`), and `test_alien_m12.py` checks the tongue's contact wiring (`CONTACT_CHANNEL3`,
    `contact_pick3`, `CUSTOM2.zw`).
- **M16, the pout at rest, mirrored and relaxed** (brief UPDATE 29, the engineer on showroom v35: the red pout looked
  asymmetric and squeezed at rest; output under `D:/prime-art-raw/review/char/alien-parts-kit/M16/`, the kit on M10c's
  pick with every mouth). Only the pout's closed pieces (rest, M, small) change; A, E, O, the talk, the frog, fangs and
  tongue are as before.
  - **The cause:** the closed pieces are traced per column off the mp1 sheet. The sheet's darkest row per column (the
    lip line, `measure_panel`) jumped 4.4 mm just right of the centre (a shadow under the bow), the drawn mouth sat
    1 px (0.9 mm) off the face's centre, and the skin under the lips differs by up to 0.4 mm side to side. The kit's
    rest piece was 4.1 mm off its mirror (M 1.7, small 2.6). Not the talk: at rest `alien_talk.gd` gives no drop or
    pucker, and `alien.gd` clears the uniforms when a line ends.
  - **The fix** (`LIP_SHAPE_POUT` `mirror` 1, `seam_fit` 3; a lip shape without them builds as before):
    `alien_lips_geom.rest_stations` mirrors the stations about the face's centre line (`mirror_stations`: x symmetric
    round the panel's `hc`, each edge the mean of its own and its mirror station's) and fits the lip line with an even
    polynomial (`even_fit`, c0 + c1 s^2 + c2 s^4); `alien_mouths.mirrored` averages each tube station's skin point,
    normal, depth and height with its mirror's, so the tube's later passes (smoothing, corners) keep the piece an
    exact mirror (0.0001 mm).
  - **The rest's shape:** a thinner upper lip over a bigger lower cushion (`upper` 0.85, `lower` 1.20; M12b 0.95 /
    1.10) and a soft crease (`lean` 0.10: at 0.25 both lips swelled toward the line and read pressed together).
    Corners as M12b (`corner` 0.18). The open rings keep M12b's values (`_POUT_RING`: `upper`, `lower`, and a ring's
    own `lean`, which `build_piece` now reads).
  - **Grids** (`M16/godot/g1`, `g2`, `vgrid.png`; rest front / 3/4 / profile at 0.4 m, 3/4 at 1.2 m): g1 fullness
    (`plump` 1.15 / 1.30) x corners (tight 0.18; mid 0.32 with `corner_join` 0.70, `corner_tuck` 0.75; soft 0.45 with
    0.55 / 0.60). Mid and soft ends went blunt like sausages, 1.30 heavy. g2 on tight corners: `lean` 0.10, the
    lips' balance 0.85 / 1.20, both, both at `plump` 1.25, both with corner 0.24. Pick: both at 1.15.
  - **Tests:** `test_alien_lips_geom.py` `RestStationsTest` (plain Python); `test_alien_pout_rest_blender.py`
    (`tools/blender/alien_pout_check.py`: the closed pieces built from the current code on M10c's kit, and the M16
    kit's own, mirrored within 0.1 mm); `test_alien_pout_rest_godot.py` (`godot/alien/pout_rest_check.gd`, headless:
    the M16 kit's closed pieces, unskinned meshes under the rigid Mouth socket, mirrored within 0.1 mm, rest shown
    with `lip_drop`, `pucker`, `jaw_thrust` 0, the talk at rest the rest piece without drop or pucker). Area
    `alien_pout` in `areas.toml`.

- **M16b, the pout's bow and tucked corners back** (brief UPDATE 30, PR #252's review: M16's front read as a smooth
  oval with round corners; output under `D:/prime-art-raw/review/char/alien-parts-kit/M16b/`, the kit on M10c's pick
  with every mouth). M16's mirrored, relaxed rest is kept; the closed pieces (rest, M, small) take the pick together.
  - **The bow:** `bow` 0.30 over a narrower `bow_w` 0.12, side peaks `bow_peak` 0.40 at `bow_at` 0.22 (M16: 0.14,
    0.16, 0.10, 0.24), so the upper lip's top draws mp1's double-peaked M. It notches the outline only (`bow_flat` 1).
  - **The corners:** `corner` 0.12 (M16 0.18) and the lip shape's own corner rule over `alien_mouths.CORNER`: the last
    `corner_share` 0.18 of the stations join 0.95 (`corner_join`) and sink 1.1 of their depth (`corner_tuck`), so the
    ends tuck into the skin as points instead of round ends.
  - **Grids** (`M16b/godot/g1/vgrid.png`, `M16b/godot/g2/vgrid.png`; rest front / 3/4 / profile at 0.4 m, 3/4 at 1.2 m,
    mp1's rest the first row, M16 the second): g1 `bow` 0.30 / 0.45 x `bow_peak` 0.20 / 0.40, two with tucked corners
    (`corner_tuck` 1.3 over 0.20); at 0.45 the upper lip read as two lumps at 3/4. g2: 0.30 / 0.40 and 0.36 / 0.50, each
    plain and tucked, and 0.30 / 0.40 with the softer tuck (1.1 over 0.18, join 0.95). 1.3 over 0.20 narrowed the mouth;
    0.36 / 0.50 began to lump. Pick: 0.30 / 0.40 with the softer tuck.
  - **The open rings** keep M12b's bow shape: `ring_param` reads a ring's own `bow_w`, `bow_peak`, `bow_at`
    (`_POUT_RING`), and a mirrored lip shape's rings sit on the face's centre line as the fangs' do (A and O were 0.4
    and 0.6 mm aside).
  - **Small's parting:** `rest_stations` fits only the lip line's middle; an open station keeps its measured gap round
    it (M16's fit smoothed it away), a closed station's lips meet on it.
  - **Tests:** `RestStationsTest.test_open_stations_keep_their_gap`; `PoutShapeTest` (the bow, the tucked corners, the
    rings' own bow); `test_alien_pout_rest_blender.py` also checks A, E, O centred within 0.1 mm, and both heavy pout
    tests read the M16b kit. Area `alien_pout` also covers `alien_m12.py`, `alien_m6.py`, `alien.gd`, `alien_talk.gd`.
- **M16c, the pout's fixes** (brief UPDATE 36, PR #254's review minors 1, 3, 5; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M16c/`, the kit on M15's head: the chain's `mouthsk` and `lashes`
  stages on `M15/b/lips`, `handoff-M15.md`).
  - **The validator error:** M16b's and M15's kits failed glTF-Validator (`ACCESSOR_VECTOR3_NON_UNIT`, a zero tangent
    on `mouth_pout_O`'s dark cup): one fan triangle of 0.006 mm^2, two rim points 0.06 mm apart where the skin's
    normal turns fast near the cup's centre. A pout ring sets `cup_even`: the rim resampled at even angles round the
    centre (`alien_lips_geom.star_resample`) and every cup point lifted along the mouth's mean normal `n0`. The heavy
    `test_alien_pout_rest_blender.py` validates the kit's GLB (0 errors).
  - **Small's parting:** a closed piece's open stations (without each end's `parting_dark` 0.2) get a thin dark
    strip on the skin behind the lips, lip axis to axis, mirrored, one closed station past either end of the gap.
    The sheet's traced gap was 4 stations wide, so small also gets a designed parting (`parting` {"small": (6 px,
    0.55)}, `alien_lips_geom.parted`). Still not seen from the front at 0.4 m: the lips' rolled fronts cover the gap
    (as before M16c); showing it needs the lips' sections or a wider gap, not done.
  - **The corners:** a lip shape's own thinnest end (`min_b`, 0.6 mm; `alien_mouths.MIN_B` 1.1 mm rounded the ends to
    caps) and `corner_over` (the ends meet toward the lower lip by half of it, the lower end sinks 1 + over of its
    depth, the upper 1 - over / 2: the upper lip's end overhangs the lower's, as on mp1). Grids
    (`M16c/godot/g1/vgrid.png` .. `g3/vgrid.png`, row 1 mp1's rest, row 2 M15's kit): g1 `corner_share` 0.18 / 0.26 x
    `corner` 0.12 / 0.06 (hardly visible alone: the end's depth kept the cap round); g2 `depth_corner` 0.15 / 0.05,
    `corner_over` 0.5, `pw` 1.5; g3 around the best (over 0.5 / 0.8, `pw` 2 / 1.75 / 1.5, share 0.26 / 0.30). Pick:
    `corner` 0.06, `min_b` 0.0006, `depth_corner` 0.05, `pw` 1.75, `corner_share` 0.26, `corner_over` 0.8 (pw 1.5
    thinned the whole lip; share 0.30 shortened the full part). The open rings read their own `ring_param` and do not
    change (A 76.2 x 73.9, E 89.2 x 58.5, O 66.4 x 60.7 mm).
- **M16d, the pout's rest slimmed to mp1's measured proportions** (brief UPDATE 37 and 39; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M16d/`, the kit on M15's head as M16c). The engineer: the rest looked
  "stung by a wasp", swollen; mp1's sheet reads slim and elegant.
  - **Measured** (`tools/blender/alien_mouth_measure.py`, plain Python, mp1's box documented there: the red lip
    mask of a front image; per column the lips' top and bottom,
    the lip line the darkest row of the middle half; at the centre each lip's height over the mouth's width W; the
    corner length: from each tip to where the lips' height first reaches half the centre's, over W / 2; the tip:
    the height 1/8 W in from the tip over the centre's; in profile the lips' stand-off beyond the line from the skin
    just above them to just below, over W). mp1's rest: upper 0.30, lower 0.30, both 0.61, lower / upper 1.00, corner
    0.28, tip 0.43, W 3.8 nostril spacings, W / the face's width at the lip line 0.58. M16c: upper 0.27, lower 0.42,
    both 0.68, lower / upper 1.57, corner 0.11, tip 0.69, stand-off 0.36: the lower lip a balloon, blunt ends, a beak
    in profile. The width against the nose already matched (3.8); against our narrower jaw it is 0.67-0.76, so the
    width stays (1.12 in g1 filled the jaw edge to edge). The sheet has no profile: a soft half-round cushion stands
    off about half its height, so the target was about 0.15-0.20.
  - **The pick** (`LIP_SHAPE_POUT`, rest, M and small): upper 1.10, lower 1.00, plump 1.00, `depth` 0.5 and `depth_l`
    0.75 (new: the closed tubes' forward radius, `alien_lips_geom.depth_factor`), `pw` 1.3, `corner_share` 0.32,
    `corner_tuck` 0.7, `min_b` 0.8 mm, `corner_over` 0.6, `closed` ("rest",) (`rest_stations` closes every station of
    the shape: rest's traced 1-2 px gap notched the lip line either side of the centre, and its dark strip goes with
    it). Ours now: upper 0.30, lower 0.29, both 0.59, lower / upper 0.97, corner 0.29-0.30, tip 0.40-0.42, stand-off
    0.21: these within 5 % of mp1's, except two: the width against the face (0.67-0.69 against mp1's 0.58, our jaw
    is narrower) and the stand-off (0.21, a shade above the inferred 0.15-0.20). The open rings read their own `plump` 1.15 (`_POUT_RING`), so A, E, O keep their
    lips (A 76.2 x 73.9, E 89.2 x 58.5, O 66.4 x 60.7 mm).
  - **Grids** (`M16d/godot/g1/vgrid.png` .. `g5/vgrid.png`; row 1 mp1, row 2 the kit; rest front / 3/4 / profile at
    0.4 m, front and 3/4 at 1.2 m): g1 fullness, balance, depth and width; g2 depth 0.6 with the taper (`pw` 1.3 / 1.0,
    tuck, share); g3 the heights round it (upper 1.10 / 1.15, lower 0.95, plump 1.05, `depth_l`); g4 the pick on rest,
    M and small; g5 depth 0.5 / 0.6, `depth_l` 0.70 / 0.75, the ends' `min_b` and `corner_over`.
- **M16e, the pout's profile and the open shapes** (brief UPDATE 41, PR #258's review; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M16d/`, the kit on M17's head, sheets in `M16d/godot/m16e/`, grids
  `M16d/godot/e1..e3/vgrid.png`, M16d's kit kept in `M16d/export_old/`).
  - **Major 1, the profile:** M16d's shallow tubes (`depth` 0.5, `depth_l` 0.75 at the same height) were flat blades
    in profile: the upper lip curled to a point, the lower hung as a narrow tongue with a sharp downward tip. Two new
    closed-lip keys (`alien_mouths.build_piece`): `sink`, the share of a tube's depth inside the skin (default
    `SINK` 0.30), so a rounder tube sits deeper and stands off no further; `tube_n_flat`, each station's normal
    blended toward the mouth's mean normal along the lip line (the skin under the lower lip faces down toward the
    chin, and the tube's section followed it). e1 (depth 0.8-1.0, sink 0.30-0.55, `tube_n_flat` 0.6 / 1.0,
    `square` 1.0, `lean` 0.2): depth 0.9 turns both lips into round cushions; sink 0.5 brings the stand-off from
    0.31 to 0.28 of the width; `tube_n_flat` 0.6 turns the lower lip forward and keeps the front ratios (1.0 made the
    upper lip 0.34 and the lower 0.27 of the width). e2: the lower lip 1.05 (the round tube measured it 0.93 of the
    upper), sink 0.6 (no visible gain). **Pick:** `depth` 0.9, `depth_l` 1.0, `sink` 0.5, `tube_n_flat` 0.6, `lower`
    1.05: front upper 0.30, lower 0.30 of the width as M16d (rest 40 / 40 px at 0.4 m), stand-off 0.28 (round
    cushions now; M16's 0.36 was a swollen pair).
  - **Major 2, the talk's jump:** measured on the front cells (px at 0.4 m at the lips' centre, the tongue left out
    by `r > b + 85`), M16d's rings were no thicker than the rest: A 34 / 38, E 29 / 34, O 29 / 43 px against rest
    40 / 40. The jump was the rest's blades against the rings' round rolls (major 1 fixes it) and the rings' thick
    round corners against the rest's fine points. e2 (ring `plump` 1.0 / 0.9, the rest's balance) and e3 (plump 1.0
    with each ring's own upper / lower, A's and E's `corner` 0.50 / 0.45 and 0.40 / 0.35, A's `wide` 1.0). **Pick:**
    `_POUT_RING` plump 1.0; A upper 1.15, lower 1.20, corner 0.40, wide 1.0; E upper 1.15, lower 1.25, corner 0.35;
    O upper 1.10, lower 1.10 (each ring's lips a little under the rest's: an open lip stretches thinner).
  - **Minors:** `alien_mouth_measure.py` committed (PR #258 minor 3); small's parting eases each lip's seam overlap out
    over the first 3 px of the gap (`alien_lips_geom.parted`'s `overlap`; the slit's ends stepped 3 px, minor 5);
    `corner_tuck` bounded 0.5-1.2 in `test_alien_m12.py` (minor 7).
- **M15, the eye socket rebuilt for the 80 % eye** (brief UPDATE 26; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M15/`). The engineer's pick `e80_p85_w80` showed "weird things" in the
  sockets (M10c's skin collar filling the gap between the 80 % eye and the socket sculpted for S9's big eye) and eyes
  "squeezed out of the skull, like a crab's"; he wants them deeper in the head, symmetric, as in e2 / el2.
  - **Measured on M11's kit:** the ball's front stood 30 mm before the face beside it and 17 mm before the nose
    bridge in profile; the lids reached x = 112 mm against a head about 99 mm half wide (outside the front
    silhouette); the old crater's floor sat 42 mm behind the eye's centre, the brow over it 22 mm behind; each eye
    looked 7.9 degrees outward.
  - **`tools/blender/alien_socket_fit.py`** (plain geometry and the why in `alien_fit_geom.py`, `FIT`): per side the
    eye unit is scaled to 0.76 of S9's (the 80 % eye), turned straight ahead (`toe` 1), sunk `sink` along its axis and
    moved `inward` 19 mm; the Body's old crater (within `free_r` 1.5 old ball radii, never lower than `free_below`
    65 mm under the old centre, never the mouth's or crest's skin) is replaced by the fairest surface that meets the
    untouched face with its slope (least squares on the uniform Laplacian, CGLS); then the skin that the socket's
    sphere (the slim lids' reach 1.151 r plus a 0.6 mm gap) opens is laid onto the sphere's far side by its angle from
    the front pole (the opening's edge is the smooth crossing curve per azimuth, so a skin wall along the axis at the
    temple leaves no saw), and the edge is rounded (24 Taubin passes over an 8 mm band, the skin kept outside the
    sphere). Unlike M9 the face never follows the eye back: the crater is filled, nothing sinks. Checks: no folded
    edge on the seen skin (one the input had is not counted), the mouth's and crest's skin unmoved, every ball on its
    node. `--debug` saves a folding variant for a look, never a kit.
  - **The marker:** `Body["prime_socket"]` (`alien_socket.MARKER`) with `"route": "m15"`, so `alien_m6.py` scales no
    eye again and builds the slim lids (`alien_lids_geom.LIDS`, M9b's t30r70) the socket was cut for; with k 1 no
    collar is built (pass `--collar off --flare off` anyway). The texture's socket field and the detail sculpt's lid
    folds read the placed ball, so in the S chain (`mouths -> fit -> ao -> ...`) they follow the new socket.
  - **The balls' aim:** `alien.gd aim_in_deg` 11.5 undid S2a's sockets' 8 degrees outward plus 3.5 of convergence;
    M15's units already look straight, so 11.5 made them cross-eyed. `alien_m6.py` writes the units' own outward look
    (`splay_deg`, from the `Eye_<side>` axes: 7.9 on older kits, 0 on M15's) into alien_lip's `prime_lids`; with it
    `alien.gd` turns the balls in by `AIM_CONVERGE_DEG` 3.5 plus `splay_deg`; a kit without it keeps 11.5 (an older
    kit rebuilt with this `alien_m6.py` measures 7.93, so 11.43: within a tenth of a degree, not identical).
  - **Two routes:** `--character` is the S chain's stage (the final kit: AO, UV, sculpt, bake and textures all see the
    new socket); `--kit` runs on a finished kit (M10's `m5/export`) for the depth grid, where the skin's maps stay
    M10's (the UVs ride with the vertices), so only the shape is new.
  - **Proofs:** `godot/alien/m15_shots.gd` "depth" (the reference row of e2 and el2, then per kit bored, manic and
    bored with the skin plain grey, front / 3/4 / profile at 0.4 m and 3/4 at 1.2 m) and m10_shots.gd's "head" gate.
    Tests: `tools/tests/test_alien_fit_geom.py` (its numpy checks run in background Blender's Python).
  - **M15b** (brief UPDATE 32-33, PR #253's fresh review): `origin/main` merged (the tongue mouth, M16's pout) and the
    kit rebuilt with every mouth.
    - **The GLB's rest aim:** the assembler turns each ball `EYE_AIM_IN` 11.5 in against S2a's sockets; the fit
      straightened the unit and kept that turn, so Blender and three.js showed the eyes crossed (only Godot, which sets
      the turn absolutely, was right). The fit now sets each ball's rest turn to `alien_face.EYE_AIM_CONVERGE` 3.5 plus
      its unit's remaining outward look (`rest_aim`, reported as `ball_aim_in_deg` [before, after]), the same as
      `alien.gd rest_aim_deg()`; `test_alien_face_constants` checks the constant against `AIM_CONVERGE_DEG`.
    - **Mirrored sockets:** S2a's two sockets differ by about 0.3 mm; the fit places both new units from their
      mirrored mean (centre, axis, ball radius), so the two spheres and cuts are mirrors (each unit still moves from
      its own centre and turns by its own axis).
    - **The lashes on this socket:** `alien_lashes_geom.SOCKET_LASHES["m15"]` (`liner_t_in_deg` -42, `sink` 0.003) goes
      under any `--lashes` spec when the Body's `prime_socket` route is `m15` (`alien_lashes.py socket_route()`; the
      report's `socket_route`): with `LASHES`' defaults the liner's inner end came within 0.12 mm of the socket skin and
      a lash root touched the slim lower lid in bored's half state. Older kits build as before. (M17b and M17c below
      give manic its own inner end on the 108 % unit; bored keeps -42.)
    - **alien.gd:** `_has_splay` (not a negative `_splay_deg`), `setup()` resets the lids' reaches and the splay for
      each kit; `alien_fit_geom.set_fit` range-checks every key. Tests: `test_alien_splay.py` (fast: the formula, the
      marker, the fallback, the reset, the fit's rest), `test_alien_lashes.py` (the socket defaults).
  - **M17, the socket's edge and the lids' AO** (brief UPDATE 36; output under `.../alien-parts-kit/M17/`):
    - **The pale ring round each eye at game distance** had two causes. The fit's rounded edge stood 0.6 mm from the
      lid as a convex lip facing the key light (plain grey shows it too), and the free skin kept the old crater's
      paint masks, so a pale band ran between the crown's teal and the lid. The fit now lowers the edge onto the lids
      (`FIT["rim_drop"]` 4 mm, `alien_fit_geom.rim_drop`: the face less than 4 mm over the socket's sphere is drawn
      onto it, its height h -> h * smoothstep(0, 4 mm, h), monotone along each ray, so the skin meets the lid's
      surface tangentially and the lid reads tucked under the skin; nothing farther moves, nothing outside the free
      area) and fills the free skin's `masks` from the face round it (`FIT["mask_fill"]`, `fill_masks`: fair_fill on
      the values), so the texture's teal reaches the upper lid as on the face beside it. The masks did most of it; a grid
      of 0 / 4 / 7 / 10 mm (`M17/grid/`, the late route on M10's kit) narrowed the lip a little more with each step,
      but from 7 mm the manic lash line's end came within 0.24 mm of the drawn-in skin (`alien_lashes.py` needs
      0.5): the pick is 4 mm (least lash-skin gap 0.5 mm).
    - **The light diagonal band on the manic closed lid:** the lids' AO was baked with the skin at the rest pose and
      rides on the lid; manic's upper lid rests 50 degrees open (rolled under the tight socket's brow) and closes at
      -12, so the rest pose's socket shade crossed the closed lid as a band. `alien_m6.bake_parts_ao` now bakes a
      design's lids per `LID_AO` (`--lid-ao`): `rest` (before), `states` (the pick: the lids posed as `alien_lashes.py`
      poses them at open, rest, half and closed, each vertex its least occluded value, so only the always-hidden rim
      stays deep) or `free` (no skin: even, but the lid's edge loses its seat). `alien_m8.py`/`alien_m12.py` keep the
      lids' AO. Tests: `test_alien_lid_ao.py` (fast), `test_alien_fit_geom.py` (the drop, the defaults).
    - **Proofs:** `godot/alien/m17_shots.gd` "rim" (per kit: bored's socket at 0.4 m, manic closed, bored 3/4 and
      manic front at 1.2 m, the 3.5 m crops of both designs with and without lashes; a kit's `hue` overrides the skin
      material's uniforms for a contact variant).
  - **M17b, the eyes 8 % bigger in the same socket** (brief UPDATE 40; output under `.../alien-parts-kit/M17b/`):
    - **Why:** the engineer on M17: the eyes are well set, but "a huge cavity shows". The socket's sphere is cut for
      the slim lids' largest reach (the upper lid's rolled rim, 1.151 r, + 0.6 mm), while the lower lid reaches only
      1.048 r, so a 4 mm deep gap ran round the lower half of the eye and read as a hollow at 0.4 m.
    - **How:** `FIT["unit"]` scales the eye unit (balls, lids, wet strips; the slim lids, lashes and liner are built on
      the scaled ball, the blink's angles do not change) over `eye_scale`, and `FIT["follow"]` sets how much of that
      growth the socket's sphere follows (`alien_fit_geom.socket_radius`; 0: the socket as M15 cut it). The rolled
      rim fades to nothing at the corners (`alien_lids_geom.CORNER`), so only the upper rim's middle reaches past the
      sphere, and it sweeps the front of the opening.
    - **The grid** (`M17b/grid/`, the late route on M10's kit; sheets `M17b/showroom/m17b-size_*.jpg`,
      `m17b-size2_*.jpg`): 100 / 105 / 110 % in the same socket, 105 % with the socket following, then 108 %. With
      the socket following, 105 % looks like 100 % (the gap grows with the eye). In the same socket the lower gap is
      4.0 / 2.3 / 1.3 / 0.6 mm at 100 / 105 / 108 / 110 %. 105 % still shows the lit lip and the groove; from 108 % the
      gap reads as a shadowed crease under the lid. **Pick: 108 %, follow 0** (`FIT` defaults).
    - **The lashes on the bigger unit:** with the liner's inner end at -42 degrees, the liner went 1 to 2.5 mm into the
      brow's skin with manic's lid open and at rest. M17b shortened it to -20 for both designs (no clip in any state
      at 108 and 110 %), which left a bare pale lid corner at the inner end and broke the 3.5 m lash line into dashes.
    - **M17c, the liner per design** (brief UPDATE 43, PR #259's review): bored never needed the change (0.87 to 3.39
      mm in every state at -42), so `SOCKET_LASHES["m15"]` keeps -42, and its `design` entry gives manic its own
      `MANIC_LINER_T_IN_DEG` (`merged()` is shallow: the entry carries manic's whole `LASHES["design"]` keys). The
      grid at 108 % (`M17b/grid/u108M36`, `M30`, `M25`, lashes only; least lash or liner gap to the skin over open,
      rest, half and closed): -36 cuts 1.4 mm into the brow with manic open; -30 clears it by 1.38 mm (rest 2.4);
      -25 by 3.89 mm. **Pick: -30**, the longest that clears 0.5 mm. Manic's lid rests 50 degrees up, and on the
      108 % unit its 0.06 r liner broke into dashes at 3.5 m with every inner end (`u108T075`, `u108T090`):
      `MANIC_LINER` 0.09 r reads as one dark line as in M17 (0.075 still broke); the least skin gap does not change.
    - **PR #257's review minors:** `rim_drop`'s reach limits (45 degrees past the crossing curve, 1.6 R) fade over
      their last 15 degrees and 0.2 R instead of cutting (`rim_drop_weight`), and `rim_drop_steps` counts the edges
      where a drawn-in point meets the fixed face inside the band. The stage refuses a count above 0 (M15's socket: 0).
      `fill_masks` runs `FIT["fill_iters"]` iterations.

- **M21, the eyes' last flaws at game distance** (brief UPDATE 45, PR #259's review; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M21/`, kit `M21/export/` = M17c's with the closed lashes). Each flaw was
  isolated first in the off-screen window (`godot/alien/m21_shots.gd` "diag": per variant hidden parts, face-material
  or skin uniforms, a per-mesh LOD bias or the viewport's LOD threshold, at 3.5 m and 0.4 m; `M21/diag/d1` to `d11`):
  - **The blotchy upper lids at 3.5 m: Godot's automatic mesh LODs.** A LOD keeps the mesh's vertex data and drops
    triangles (a coarser index list over the same vertices). On the thin lid shells the few kept triangles spread the
    baked AO (COLOR_0, which `LIP_LOOK` turns into the deeper coral) and the normals over large spans, so the shading
    came out in patches. With the LODs off (the viewport's threshold 0, or a high LOD bias on the eye parts) the lids
    are even in every state; with the AO off they are even too, but flat up close. `alien.gd` gives every `eye_*` mesh
    `lod_bias` `EYE_LOD_BIAS` (100): full detail at every distance. The cost (M21b, counted from the kit's GLB): the
    shown design's eye parts are 20,008 triangles for both eyes (lids 11,880, liners 2,344, wet lines 2,304, lash
    tubes 1,848, balls 1,632), all kept at 3.5 m; the tubes fade out by 3 m, so 18,160 are drawn there.
  - **The pale line under the eyes at 3.5 m: the lids' screen-space SSS.** At 3.5 m the lower lid is 2 to 4 px tall,
    and Godot's SSS blur mixed its light with the white's and the pale skin's into a beige band (rows of
    `c7a392`-like pixels where the coral should be). With the lid's `sss` 0 the band is coral; the wet line, the
    lid's rim and specular, the transmittance, the skin's contact and normal map changed nothing. `alien_lip.gdshader`
    has `sss_fade` (view distances in m; the default never, so the lips, pout and fangs keep theirs), and `LID_LOOK`
    fades the lids' SSS out between 1.5 and 3 m: up close it is still the lid's soft edge.
  - **Manic's closed "zipper"** had two causes:
    - **Up close:** the lash sets are rigid children of the upper lid, so the open curl rode into the closed state.
      Manic's lashes (leaving 30 degrees below the radial, curled 160) dipped under the closed line and hooked back up
      over the lid, teeth above and below in turn; bored's stood over the line as a comb. Each tube set now has a
      shape key `closed` (`alien_lashes_geom.CLOSED`, a glTF morph target; the tubes get a UV map so Godot can make
      its tangents): the same tubes with the lift -30 and the curl 60, laid down and out from the line over the lower
      lid. `alien.gd` weighs it with `lash_closed_weight` (a smoothstep of the upper lid's angle from "half" to
      "closed"), so open, rest and half keep their lashes and the blink morphs into the closed ones. The clip check
      poses the key at every state (`alien_lashes.shaped`). Grid (`M21/grid/shots*/lclosed.png`): curl 100 / 60 / 30
      and the lift -10 to -40; 100 still hooked, -10 hooked again, 30 read as straight spikes.
      M21b (brief UPDATE 46): closed, the outer lashes still fanned up and out at the corner, the wing curling back
      up. `CLOSED` also sets the wing per design (`wing_lift_deg` -35, `wing_sweep_deg` 15, `fan_bias_deg` bored 20,
      manic 10): the closed wing runs out level, each tip further out and lower than the last (tested). Only the
      morph target changes; the open tubes are byte-equal. Grids `M21b/grid/shots*/lclosed.png` (`lclosed_fov` 20
      frames the corner, `lclosed_far` adds 3.5 m): the wing lift alone (-20 / -35 / -50) left the fan; -50 with no
      sweep bunched the wing into one dark wedge.
    - **At 3.5 m:** the liner's clear coat put single white pixels along the closed line. `alien_liner.gdshader`
      fades its specular and clear coat out between `gloss_fade`'s 2 and 3 m, as the tubes fade.

- **M19, the AI mouth route test** (brief UPDATE 38; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M19/`): GPT Image views of mp1's lips (`batches/2026-10-21-alien-mouth-views.toml`)
  -> Meshy multi-image 3D (`batches/2026-10-21-alien-mouth-3d.toml`) -> `tools/blender/alien_mouth_fit.py`, which
  writes a grid kit (`M19/kit/`, M15's head) with `lipvar_aia_pout_<shape>` and `lipvar_aib_pout_<shape>` beside our
  pieces (and `--also m16c=<blend>`'s as `lipvar_m16c_*`), shown by `m12_shots.gd`'s `vgrid`
  (`M19/godot/rest/vgrid.png`, `M19/godot/A/vgrid.png`). The geometry is `alien_mouth_fit_geom.py` (tested):
  - **(a) the AI mesh:** scaled uniformly to our piece's lip width, centred, its lip line on ours (`seam_z`), then
    **seated with its flat back 4 mm under the skin** at the lip line's centre (`FIT["seat"]`; aligning its front on
    ours left a box-like wall in profile), collapse-decimated to `FIT["budget_tris"]` (6k), its -x half mirrored, the
    back vertices pushed under the skin and curved in toward the centre (`taper_back`) and smoothed. On A the form's
    own floor (faces seen from the front, deeper than 45 % of its depth, inside the opening's box) is removed and our
    A piece's cup and tongue are joined in behind it. Our materials, parts AO and jaw weights (`alien_m12.jaw_weights`).
  - **(b) our tubes on the AI form:** a copy of our piece whose lip vertices facing forward and outside the skin
    shrink-wrap to the nearest surface point of (a), three rounds with a relax between. Projection along the normals
    folded more.
  - **Gotchas:** a `bpy` vertex-group reference dangles once a modifier is applied (use its name); an imported mesh
    keeps faces selected (clear the selection before a selection-based delete); work in the Mouth socket's space (it
    leans about 14 degrees), where our pieces' coordinates already are.
  - The variants keep the Body's contact layers, which come from our `mouth_pout_rest`; a route that ships an AI form
    must rebuild them from it (M20 does).
- **M20, the hybrid pout** (brief UPDATE 42, the engineer's pick: art#196 comment 6319459349; output under
  `D:/prime-art-raw/review/char/alien-parts-kit/M20/`): the pout's **closed shapes rest, M and small are AI forms**
  (M19's route (a)), the open shapes A, E, O ours. M and small came from `batches/2026-10-21-alien-mouth-views-2.toml`
  (edits of M19's rest sheet with mp1's M or small panel, so the three closed pieces share the lips, light and scale)
  and `batches/2026-10-21-alien-mouth-3d-2.toml`; rest is M19's `rest3d`. The kit is the chain's `mouthsk` and
  `lashes` on `M17/b/lips`, then `alien_mouth_fit.py --replace` into `M20/export/`:
  - each form scaled to our piece's lip width (rest 77.6, M 76.4, small 72.3 mm, measured off mp1 by `alien_mouths`),
    its box's middle on the middle of **our visible lips** (`FIT["closed_align"]` "centre": the lip vertices in front
    of the skin; `seam_z` on the whole parametric rest found the groove 5 mm low, among the parts tucked under the
    skin, and on small the parting's ends 10 mm low), then **stretched toward mp1's fullness** (`FIT["z_scale"]` rest
    1.10, M 1.40, small 1.30 about the line, the depth half as much, and the lower lip 1.12 below its own line,
    `stretch_below`): the AI views drew each lip slimmer than mp1 (front upper / lower over the width rest 0.28 /
    0.23, M 0.21 / 0.15, small 0.27 / 0.20 against mp1's 0.30 / 0.30, 0.29 / 0.28, 0.33 / 0.37); after it 0.30 /
    0.28, 0.28 / 0.25, 0.33 / 0.33;
  - decimated to 6k triangles and mirrored (a second pass when the mirror passed the budget: about 5.85k), the back
    under the skin with the thin ends 1.5 mm deeper (`corner_sink`, the glossy rim at the corners), small's parting
    (front-seen faces deeper than 55 % of the form, within 12 % of the height of its lip line, the middle half)
    painted `alien_mouth_inner`;
  - one closed piece each (no upper and lower tube): the jaw weight in `COLOR_0.a` is 1 below the form's own lip
    line (`lip_line`: per column the deepest front in a band round the centre's groove, mirrored and smoothed), 0
    above, a 1.5 mm smoothstep across it and `alien_m12.JAW`'s falloff to the corners (`jaw_closed`); the skin's pout
    contact (`TEXCOORD_6.u`) rebuilt from the new rest (`alien_m12.mouth2_contact`); parts AO baked per piece;
  - provenance per piece in `character.json` `m20.shapes.<shape>.provenance` (`ai_generated` true, `meshy-7.1`, the
    task id, batch file, the GLB's sha256 and the inputs' provenance); the kit is not an asset yet, so no manifest;
  - the open rings already sat at the AI rest's lip heights (front, px at 0.4 m: A 35 / 37, E 30 / 32, O 30 / 37
    against the rest's 40 / 37); A's and E's corners taper further (`ring_param` corner 0.28 / 0.30, M16e 0.40 /
    0.35) toward the AI rest's fine points.
- **M20b** (brief UPDATE 44, PR #260's review; output `M20b/`, the kit on M17c's eyes: `mouthsk` and `lashes` on
  `M17b/b/lips`, then the fit into `M20b/export/`):
  - **the seam down the lower lip:** the forms are mirrored at full resolution, then decimated with the modifier's X
    symmetry and mirrored once more (decimating first cut a ragged row of slivers along x = 0); each form is first
    put on its own best mirror plane (`best_plane`, `to_plane`; the three AI forms' best plane is the box's centre,
    mean mirror distance 0.13-0.17 mm, so the 4-5 mm of `mirror_mm_before` are a few outliers at the back, not a
    misplaced plane); the band |x| < 2 mm (6 passes) and the lip line's band (+-1.2 mm, 2 passes) smoothed in depth
    only (`smooth_bands`), so the silhouette, the bow's dip and the line's height stay;
  - **the skin contact:** `alien_m12.contact_field` measured a skin point under the lips 3-4 mm from the form's back
    (it goes under the skin), so `full` was 0; `closed_contact` counts a skin point inside the form as touching it
    and an outside one `contact_margin` (M20b 5 mm) closer (`contact_distance`; 0: full 29, 2.5 mm: 52, 3.5 mm:
    61, 5 mm: 72; M20c's 2 mm and M20d's 5 mm again below);
  - **rest -> A:** A's and E's rings carry the rest's two-peak bow (bow 0.30, bow_w 0.12, side peaks 0.40 at 0.22)
    and stand back to the AI rest's stand-off (`ring_param` `push`, `push_lo`, read by `alien_mouths`' rings: the
    lips' front ahead of the skin at the centre, upper / lower, A 16.6 / 14.0 mm, E 16.5 / 13.8, the AI rest 16.0 /
    14.3; M20's A 19.6 / 20.5); the pick of a stand-off (0, 0.5, 1 of the gap) x bow (M12b's, between, the rest's)
    grid, `M20b/godot/grid/vgrid.png`;
  - M a little wider and flatter in depth (`FIT["xy_scale"]` M 1.04 / 0.92; in front mp1's M is as wide as its
    rest and 0.92 of its height, which M20's already was); the heavy pout tests read `M20b/export` (the hybrid
    pieces mirrored, the GLB validated, the contact's `full`).
- **M20c** (brief UPDATE 47, PR #260's last review minors 1-5; output `M20c/`, the same chain as M20b into
  `M20c/export/`):
  - **the dimple at the top of the lower lip's centre:** `fill_cleft` skipped a vertex deeper than `cleft_most`
    (2 mm); for rest and M it now comes forward by 2 mm (`clamp`; rest 42 vertices, M 14), small keeps the skip (its
    parting);
  - **the skin contact:** `closed_contact` keeps a touching skin point (raw contact at least `contact_keep`, under the
    form or within `contact_margin` of it) at 1 after the smoothing, which had lightened the band under the lower lip;
    `contact_margin` 2 mm (with the keep: 5 mm full 156, 3.5 mm 135, 2 mm **124**; M20b 72);
  - **rest -> A/E/O:** mp1's open shapes measured on the sheet (`tools/out/m20c/openmeas.py` in the worktree: the
    lip mask without the pink tongue, at the centre, each over the lips' width W: upper lip / opening height / lower
    lip / opening width): mp1 A 0.30 / 0.39 / 0.31 / 0.68, E 0.21 / 0.21 / 0.22 / 0.78, O 0.34 / 0.20 / 0.38 / 0.23;
    M20b A 0.30 / 0.44 / 0.32 / 0.87, E 0.20 / 0.23 / 0.22 / 0.85, O 0.27 / 0.28 / 0.35 / 0.38. The rolls' front
    heights already matched; the openings were too wide (A corner 0.53, E 0.57), A's too tall (open 0.88), O's hole
    too big (hole 0.18). What read thin at 3/4 was the rolls' depth: `ring_param` `depth` (alien_mouths, a ring's own
    roll depth) 1.3, pushed back so the front stands where the AI rest's does (16.0 / 15.4 mm ahead of the skin; O
    25.5 / 27.9 as M20b's). Grids `M20c/godot/grid1/vgrid.png` (depth 1.0 / 1.3 / 1.6 x stand-off 0 / -1.5 / -3 mm)
    and `grid/vgrid.png` (depth 1.0 / 1.15 / 1.3 at the rest's stand-off). After, at 0.4 m: A 0.30 / 0.39 / 0.32 /
    0.76, E 0.21 / 0.23 / 0.22 / 0.78, O 0.32 / 0.15 / 0.40 / 0.29.
- **M20d** (brief UPDATE 49, PR #262's fresh review; output `M20d/`, the same chain into `M20d/export/` on `main`
  after PR #261, so the kit carries M21b's eyes and lashes; gate against `M21b/final/export/`):
  - **the skin contact:** M20c's 2 mm `contact_margin` narrowed the halo (`touched` 329 -> 308) and the skin under
    the lower lip got 3-6 brighter at 3/4. `contact_margin` is 5 mm again with `contact_keep` (touched 329, full
    155). Judged by the skin's measured brightness under the lower lip (the mean of r, g, b, 1-12 px under the lips'
    lowest pixel over the middle 70 % of their columns, the rest at 3/4 0.4 m in `compare_closed.png`): M20b 182.5,
    M20c 185.9, M20d **180.4**, rising evenly away from the lip (no darker ring);
  - **the dimple:** after `fill_cleft`'s clamp, `smooth_centre` lays the lower lip's front within +-2 mm of x = 0
    onto the even curve through its front at +-2 and +-3.5 mm at the same height (`centre_target`, forward only, at
    most 2 mm, only vertices the front ray meets), rest and M (small keeps its parting). M20c's rest still had a
    1 mm notch at x = 0 in the top few mm under the lip line (3 mm under it: x = 0 11.5 mm behind the front, +-1 mm
    10.3, +-2 mm 9.6); after, 10.3 / 9.9 / 9.5, within 0.4 mm of the curve. A smooth 1 mm valley over +-4 mm stays
    (the AI form's), and with the highlights either side it still reads as two soft lobes in front; a +-4 / 6 mm
    band changed nothing seen at 0.4 m. `fit.json` records each shape's `centre` (moves, `kink_mm` before and after);
  - **O's hole:** `hole` 0.23 measures 0.21 of W tall (mp1 0.20; M20c 0.15). Its width stays 0.34 (mp1's round hole
    0.23): a round ring's hole projects wider than tall on the face. A/E/O at 0.4 m (as M20c's table): A 0.30 /
    0.39 / 0.32 / 0.76, E 0.22 / 0.23 / 0.22 / 0.78, O 0.30 / 0.21 / 0.37 / 0.34;
  - the heavy pout tests read `M20d/export`: the contact (`full` >= 140, `touched` >= 329), the dimple from
    `fit.json`, and the open rings' lip depth at the centre (`alien_pout_check.py` `rolls`, M20b's depth 1.0: A
    19.4, E 17.1, O 20.1 mm; at least A 23, E 20.5, O 24).
- **Test D, one material** (brief UPDATE 53; output `D:/prime-art-raw/review/char/alien-parts-kit/TD/`, handoff
  `handoff-TD.md`): can today's parts kit read as one painted head by material and light alone? No geometry changed.
  - `alien_hue.gdshader` gained `pale_value` and `pale_mul` (linear), both mixed in by the light mask on both paths, so
    the face, throat and belly darken and tint while the dome's teal stays; identity at the defaults (1.0, (1, 1, 1)),
    so the shipped look is unchanged (test `test_pale_terms_are_identity_and_on_the_light_mask`).
  - `td_shots.gd`, the proof: looks (skin uniforms, face material uniforms in sRGB, light energies, angular size,
    blur and position, the environment's ambient, SSAO and exposure, and the diffuse mode: the skin, lip and mouth
    part shaders recompiled from `diffuse_lambert_wrap` to `diffuse_burley`) as a grid (skins x lights x lips, the
    pout at rest from the front at 0.4 m and 3/4 at 1.2 m, `grid.json` with the mouth's box per cell) and as view
    rows beside the 2D sheets. The cells are measured with the step back's `scripts/measure.py` (median luminance,
    saturation, spread round the mouth).
  - Measured round the mouth, front at 0.4 m (2D: skin 122-154, sat 0.14-0.23, sd 36-45, darkest 10 % 86-95; lips
    90-135, sd 28-32, sat 0.48-0.56, hue 6-13): today skin 195 / 0.096 / 16 / 173, lips 117 / 18 / 0.57 / 6; the
    pick skin 131 / 0.183 / 34 / 78, lips 111 / 31 / 0.56 / 11. The biggest single lever for form was the diffuse:
    the lambert wrap on the skin flattened the shading (sd 16 -> 22-24 with burley at the same light); more skin
    sheen (roughness down, specular up) lowered the spread (the sky's reflection fills the shadow side). The spread
    stays below the 2D's 36 on this flat lower face: the rest is form (Test B), not material.
  - The pick is not in `alien.gd` or `look_presets.json`: the look needs the engineer's yes (the values are in the
    handoff and `TD/final/spec.json`).

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
