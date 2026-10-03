# Animations: the retarget and the review in motion

Our characters are built on the Quaternius **Ultimate Modular** Men and Women packs (CC0, xperiaroco2/prime-game#165):
one 62-bone armature, `CharacterArmature`, and 24 actions per body type. This page covers how other clips get onto
that armature (the **retarget**) and how clips are judged (the **review**): always in motion, from frame strips and
looping clips plus measures, never from one frozen frame. The findings of the first review (art #20) are in
[research/2026-10-03-animation-review.md](research/2026-10-03-animation-review.md).

## Sources

| Source | Clips | Rig | Licence | Record |
|---|---|---|---|---|
| Ultimate Modular Men, any file but `Adventurer.glb` (the review uses `Business Man.glb`) | 24 actions | `CharacterArmature`, 62 bones | CC0 1.0 | #17's `sources/` |
| Ultimate Modular Women, any file (the review uses `Suit.glb`) | 24 actions, other motions than the men's | the same 62 bones | CC0 1.0 | #17's `sources/` |
| Universal Animation Library Standard (UAL1): `UAL1_Standard.glb` (in place) and `UAL1_Standard_RM.glb` (root motion) | 43 clips each | 65 bones, Unreal-mannequin names | CC0 1.0 | [`sources/quaternius_ual1_standard.toml`](../sources/quaternius_ual1_standard.toml) |

Measured by `anim-review inventory` (2026-10-03): the 24 actions have the same keyframes in every file of a body type,
except the men's `Adventurer.glb`, whose 24 all differ (that character is bound 180 degrees off). The women's
versions of the same names are other motions (their poses differ by 9 to 145 degrees) and 25% longer (Idle 2.08 s
against 1.67 s). UAL is authored at 30 fps; its clips import to whole frames only when the scene runs at 30 fps.

## The two rigs

- **Ultimate Modular** (`CharacterArmature`, under the importer's `RootNode`, world scale 100): `Root` > `Body`
  (carries the legs: `UpperLeg`, `LowerLeg`) > `Hips` > `Abdomen` > `Torso` > `Chest` > `Neck` > `Head`, and
  `Shoulder`, `UpperArm`, `LowerArm`, `Wrist` per side. The **feet are children of `Root`**, not of the lower legs
  (baked IK targets), with `PT.L`/`PT.R` knee pole targets that deform nothing; a foot's pivot sits at the heel, 2 cm
  above the floor. **No toe bone.** Fingers: `Index1` to `Index4` (and `Middle`, `Ring`, `Pinky`), where `1` is the
  metacarpal (its head at the wrist, 12 cm long) and `2` to `4` the phalanges; `Thumb1` to `Thumb3`.
- **UAL** (`Armature`, identity world matrix): `root` > `pelvis` > `spine_01` to `spine_03` > `neck_01` > `Head`;
  `clavicle`, `upperarm`, `lowerarm`, `hand`; fingers `_01` to `_03` are phalanges (no finger metacarpals) plus
  `_04_leaf` ends; `thigh` > `calf` > `foot` > `ball` (toes). Both rigs rest in a T-pose, palms down, facing -Y.

## The retarget

`tools/run.py retarget [--body men|women] [--clips A,B|all] [--out DIR] [--blend] [--no-ik]` bakes UAL clips onto the
body type's donor character (`tools/blender/anim_review.toml`) in background Blender and writes `retarget_report.json`
(with `--blend` also the character with the baked actions `UAL|<clip>`). No add-on: `tools/blender/retarget_core.py`.

1. **Sampling.** Actions are read from their fcurves (Blender 5's layered actions: `action.layers`, channel bags per
   slot) and posed by our own forward kinematics, `pose = pose[parent] @ (rest[parent]^-1 @ rest) @ basis`, so a
   source never needs the depsgraph.
2. **Rotations.** Each mapped target bone takes its source bone's world-space rotation change from rest:
   `target_world = source_world @ source_rest_world^-1 @ target_rest_world`. Both rests are T-poses facing -Y, so no
   pose alignment is needed; unmapped target bones keep their rest relative to the parent.
3. **Translation.** `root` and `pelvis` move `Root` and `Body` by the source's displacement from rest, scaled by the
   **hip-joint height ratio** (the mean rest height of the thighs; 1.034 for the men, 1.113 for the women), which is
   the leg length that sets stride and height.
4. **Feet.** A target foot follows its lower leg (`[follow]` in the map), and a **two-bone IK** per leg places its
   pivot where the source foot carries it: the target pivot's rest position, scaled to the source's size and pinned
   to the source foot, so heel and toe roll transfer. Then the **toe lift**: the rigid target foot (no toe bone) is
   pitched about its pivot until its toe is no lower than the rest sole, while the pivot is near the floor (fully up
   to 20 cm above its rest height, fading out over 10 cm; never when the pivot is below the floor, as in in-place
   jumps). The report's `ik_miss_mm` says how far a leg fell short of its goal (a few mm in walks; rolls and kneels
   reach further than the target's legs).
5. **Bake.** One key per source frame (30 fps) on every target bone, quaternions kept on one hemisphere.
6. **Proof.** The source rest must land on the target rest: 0.002 mm and 0 degrees on both bodies (`retarget` fails
   above 0.01 mm or 0.01 degrees; `test_retarget_blender.py` checks it and a walk).

### The bone map

`tools/blender/retarget_maps/ual_um.toml`, checked by `tools/blender/retarget_map.py` (every bone of both rigs
accounted for exactly once; unknown keys refused):

| Key | Meaning |
|---|---|
| `[bones]` | `source = "target"`: rotation transfer (51 pairs) |
| `root`, `hips` | `[source, target]` pairs whose translation transfers |
| `[height]` | the hip joints of each rig: the translation scale |
| `[follow]` | target bones carried by another target bone instead of their parent (the feet by the lower legs) |
| `[[legs]]` | `target = [upper, lower, foot]`, `source_foot`: the IK chains |
| `[rest]` | target bones kept at rest (the finger metacarpals, `Hips`, `PT.L`, `PT.R`) |
| `[unused]` | source bones with no target (the leaves, `ball`, `ball_leaf`) |
| `[source_rig]`, `[target_rig]` | the full bone lists, read from the files |

Fingers map by anatomy, not by number: UAL `index_01..03` (phalanges) go to `Index2..4`, and `Index1` (the
metacarpal) stays at rest; thumbs map 1:1. Hand close-ups confirmed curls bend the right way and pointing works.

## The review

`tools/run.py anim-review <step> [--body men|women|both] [--clips pack:Walk,ual:Walk_Loop|all] [--jobs N] [--out DIR]`
(default output `tools/out/anim-review`; the review of art #20 went to `D:/prime-art-raw/review/stage1/20/`, outside
git). Steps, or `all` in this order:

| Step | Makes |
|---|---|
| `inventory` | `inventory.json`: every pack file's actions (lengths, identical across files or not), the men against the women, UAL's clips in both files with root motion per clip |
| `clips` | per body type and clip, on the unmodified donor character: measures (`metrics/<body>_c<n>.json`), a 12-frame strip with a front and a right-side row (`strips/<body>/<source>_<clip>.png`) and a looping 480x480 H.264 clip at 30 fps (`clips/<body>/...mp4`); `--jobs` Blender processes per body type |
| `pairs` | for each `[[pairs]]` entry of `anim_review.toml`: the pack clip and its UAL counterparts side by side, a strip (front and side rows at the same fractions of each clip) and a looping MP4 (`pairs/<body>/<pack clip>.*`) |
| `sheets` | review sheets: each clip's men and women strips stacked, three clips a sheet (`sheets/`) |
| `table` | `metrics.json` (all measures) and `metrics.md` (the table below) |

Pictures: Workbench, flat material colours, specular off, neutral grey background, a dark floor slab whose top is
z = 0 (a line in the horizontal views), orthographic cameras, labels as text objects; videos are driven by a
frame-change handler that poses the characters, so each character can loop its own clip.

### Measures (`tools/blender/anim_metrics.py`, `anim_math.py`)

| Measure | Definition |
|---|---|
| Foot sliding | The foot bone (its pivot) is in contact while within 2 cm of its lowest height in the clip; the horizontal contact speed (central differences) gives the **ground speed** (the median contact velocity: the treadmill speed of an in-place clip, the speed a game must move the body at for no skating) and the **slide** (contact velocity minus ground velocity: mean and max, cm/s) |
| Sole sliding (JSON only) | The same with the lowest shoe vertex against the floor; noisy on these toe-less feet (it counts the toe dragged by the toe lift) |
| Lowest vertex | The lowest vertex of all parts per frame (cm; the floor is 0): its minimum is how far anything goes below the floor |
| Hands in torso / head | The deepest hand vertex inside the convex hull of the torso vertices (`Body` to `Chest`) or of the head (cm) |
| Loop seam | The largest local bone rotation between the last and the first frame, also as a multiple of the median frame step (about 1 or less loops cleanly) |
| Past straight | Knees and elbows: the bend about the hinge axis carried by the upper bone (knees about X, elbows about -Z/+Z from the T-pose); its most negative value |
| Forearm twist | The twist of the wrist against the lower arm about the bone axis, from rest (no twist bones: large values wrap the wrist) |
| Finger curl | The mean rotation of the 12 phalanx joints per hand (min-max over the clip) and the largest single joint |
| Root motion | Hips and root travel over the clip; in place under 5 cm |

## Gotchas

- Import at 30 fps (`scene.render.fps` before the import): UAL's clips then land on whole frames.
- Each import adds the file's actions again with `.001` suffixes: take the actions created by that import
  (`retarget_core.load_glb`), and reset every pose bone before applying one.
- Blender 5 has no `action.fcurves`: read and write through `bpy_extras.anim_utils.action_get_channelbag_for_slot`
  and `action.layers[0].strips[0].channelbags`.
- Save images and render outputs to absolute paths in background Blender.
- In-place UAL jumps (`Jump_Start`, `Jump_Loop`) have no vertical root motion: their feet hang below the floor; the
  game's jump physics lifts the body. Judge them in the root-motion file or in game.
- The single frozen frames of the pack's Idle and Walk look twisted; the motion does not (the engineer's note).
