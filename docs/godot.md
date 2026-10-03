# glTF export and the Godot 4.7.2 import check

An assembled character (`tools/run.py assemble <recipe> --blend`, `docs/assembly.md`) reaches Godot the way the game
needs it: every part a separate skinned mesh on one Skeleton3D, the pack's 24 animations playing. Art #18 built three
commands for that; together they are the export step of `docs/pipeline.md` (step 10) plus a check in the game's engine.

```
tools/run.py export <character.blend> [...] [--out DIR]          GLB with fixed options; glTF-Validator report.json
tools/run.py godot-check <glb> [...] [--out DIR] [--strict-contract] [--humanoid]
                                                                  import headless in godot/; assertions; report.json
tools/run.py frames <glb> [--clips A,B] [--compare all|A,B|''] [--video A,B] [--blend FILE] [--out DIR]
                                                                  Godot-rendered frame sheets (off-screen window)
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
| `export_morph`, `export_cameras`, `export_lights` | off | No shape keys; a character carries no camera or light |
| `export_materials` `EXPORT`, `export_image_format` `NONE`, `export_vertex_color` `NONE` | | Flat colours: one base colour per material, no textures, no vertex colours |
| `export_texcoords` on, `export_normals` on, `export_tangents` off | | The pack's UVs are kept for a later palette texture; no normal maps |
| Draco, meshopt, gltfpack, GPU instances, extras, attributes | off | Godot cannot read Draco or meshopt; nothing else is needed |

Measured (2026-10-03, Blender 5.2.2, exporter 5.2.40): m1_rex 1.85 MB, m2_walt 2.04 MB, w1_ivy 2.03 MB, w2_nova
2.04 MB (the contract allows 5 MB); 62 joints, 24 animations of 186 channels (62 bones x translation, rotation,
scale), 8 parts (9 for m2_walt with his moustache), 11 to 17 materials. glTF-Validator 2.0.0-dev.3.10: 0 errors;
one warning per part, `NODE_SKINNED_MESH_NON_ROOT` ("parent transforms will not affect a skinned mesh"): the parts are
children of the armature node, whose transform is the identity (the saved file applies every transform), so it changes
nothing; infos `UNUSED_OBJECT` for the UVs no texture uses.

## The Godot project: `godot/`

A minimal Godot 4.7.2 project at the repo root (`config/features` 4.7, Forward Plus like the game), separate from
`tools/godot/`, which stays the headless contract project with its one dump script. `godot/import/` (ignored) receives
the GLBs the commands import; `godot/.godot/` (ignored) is Godot's cache. Committed: `project.godot`,
`lib/character.gd` (shared helpers, loaded with `preload` because a `-s` script has no global class cache),
`check/inspect.gd`, `frames/frames.gd` and the `.gd.uid` files Godot 4.7 writes beside scripts (the game commits
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
MeshInstance3D (its skeleton, Skin binds that do not resolve, surfaces, vertices, materials, its rest-pose bounds),
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
| `facing_plus_z` | the eyes are at least 5 cm in front of the Head joint, the shoes reach further forward than back from the ankles, the left wrist is at +X |
| `flat_colours` | no surface has an albedo texture |
| `godot_output` | no ERROR line in Godot's import and inspection output (warnings are listed) |
| `contract_height`, `contract_eye_height` | the contract v1 body gates (height 1.70 to 1.80 m to the top, eyes 1.6 +- 0.08 m): **warnings** unless `--strict-contract` |
| `loop_modes` | **warning** while a cycle (`Idle*`, `Walk*`, `Run*`) imports with loop_mode NONE; names the open cycles |
| `expectations`, `pack_floor` | only for a GLB without its `<stem>.export.json`: a **warning** that parts, bones and animations then come from the GLB itself (what it already lacks is not caught; no rest joints, hierarchy or Blender height), and a failure below the Ultimate Modular rig's 62 bones and 24 actions |

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

## frames

`frames/frames.gd` runs in a real window off-screen, like the game's `tools\run.cmd shot` (`--position
-30000,-30000 --resolution 480x600`; never headless and never minimized, where Godot does not draw and
`RenderingServer.frame_post_draw` never fires). The engineer's kickoff of 2026-10-03 allows this; CLAUDE.md still
says Godot runs only headless (a manager follow-up). Per animation:

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

**Measured** on whole frames (2026-10-03, every clip of m1_rex and w1_ivy, 62 joints and 124 axis points): Godot and
Blender agree within 0.017 mm everywhere. Before the optimizer was turned off they differed by up to 16.7 mm (m1_rex
Run, a hand) and by 3.65 degrees on m1_rex's Roll `Foot.L`, which the joint-only comparison of the time could not see.
The poses in the comparison images match.

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

## Findings for later tasks

- **Loop modes**: Godot imports all 24 animations with loop_mode NONE (the glTF names carry no `-loop` suffix): in the
  game the idles, Walk and Run would play once and stop. The game's import sets their loop mode (per-animation
  `settings/loop_mode` in `_subresources`) or the names get a loop suffix: the contract v2 decides.
- **Open cycles**: `Run`, `Run_Left` and `Run_Right` (both body types) end one frame before their first pose comes
  round; looped at the length of their keys they skip a step at every repeat. Their loop length in the game is
  (last frame + 1) / 24 s: 0.833 s for the men, 1.042 s for the women.
- **The game's import options**: `animation/fps = 24` and the AnimationPlayer's `optimizer/enabled = false` (above).

- **The women's clips are 25 % longer** than the men's of the same name, in the pack's own files (Walk 1.67 s against
  1.33 s, Run 1.00 s against 0.79 s, Idle 2.08 s against 1.67 s): the women walk and run more slowly at the same game
  speed (art #20, the animations).
- **Materials**: the pack's materials are metallic 0.4, roughness 0.42 (from its FBX conversion); under the game's
  lights flat faces will glint. The palette step should set its own values.
- **The women's Idle and Wave stance**: one foot turned inward, identical in Blender and Godot: the pack's pose.
- **Godot gotchas**: in a `-s` SceneTree script `root.get_viewport()` is null at start (use `root`, a Window, as the
  viewport); a script error inside a coroutine does not quit, so every script has a watchdog and validates its input
  (a relative spec path, read as nothing, left the window open until the watchdog); `bake_mesh_from_current_skeleton_pose()` fails headless.
