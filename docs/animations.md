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

`tools/run.py retarget [--body men|women] [--clips A,B|all] [--out DIR] [--blend] [--floor] [--no-ik]` bakes UAL clips
onto the body type's donor character (`tools/blender/anim_review.toml`) in background Blender and writes
`retarget_report.json` (with `--blend` also the character with the baked actions `UAL|<clip>`; with `--floor` each
clip's lowest vertex on the target and on UAL's own mannequin scaled to the target, which tells how deep a clip goes
into the floor by itself and how much the retarget adds). No add-on: `tools/blender/retarget_core.py`.

1. **Sampling.** Actions are read from their fcurves (Blender 5's layered actions: `action.layers`, channel bags per
   slot) and posed by our own forward kinematics, `pose = pose[parent] @ (rest[parent]^-1 @ rest) @ basis`, so a
   source never needs the depsgraph.
2. **Rotations.** Each mapped target bone takes its source bone's world-space rotation change from rest:
   `target_world = source_world @ source_rest_world^-1 @ target_rest_world`. Both rests are T-poses facing -Y, but not
   identical ones, and each target bone keeps its own rest offset in every clip: measured as joint-to-joint
   directions, the upper arms agree within 0.2 degrees, the forearms, thighs, shins and spine within 2 to 8 (the target
   forearm rests bent 7 degrees forward), the neck 11, the fingers 6 to 13 and the **thumbs about 20** (so our thumbs
   stay more spread than UAL's). No per-chain rest alignment is done; it is an open fix if a grip looks wrong.
   Unmapped target bones keep their rest relative to the parent.
3. **Translation**, scaled by the **hip-joint height ratio** (the mean rest height of the thighs; 1.034 for the men,
   1.113 for the women), the leg length that sets stride and height; positions scale about each rig's own origin.
   `root` moves `Root` by the source root's displacement from rest. `Body` (which carries the legs) is **carried in
   the source pelvis's frame**: its rest position, scaled to the source's size and expressed in the pelvis's rest
   frame, goes wherever the posed pelvis takes it. The two rigs put their pelvis pivots in different places (UAL's
   pelvis head is 5 cm behind its hip joints, the Ultimate Modular `Body` head 10 cm below its own), so moving `Body`
   by the pelvis head's displacement alone swung the hip joints about the wrong pivot once the pelvis turned: before
   this fix Death01 went 22 cm into the floor where UAL's own mannequin goes 8 cm.
4. **Feet.** A target foot follows its lower leg (`[follow]` in the map), and a **two-bone IK** per leg places its
   pivot where the source foot carries it: the target pivot's rest position, scaled to the source's size and pinned
   to the source foot, so heel and toe roll transfer. Then the **toe lift**: the rigid target foot (no toe bone) is
   pitched about its pivot until its toe is no lower than the rest sole, while the pivot is near the floor (fully up
   to 20 cm above its rest height, fading out over 10 cm; never when the pivot is below the floor, as in in-place
   jumps). The report's `ik_miss_mm` says how far a leg fell short of its goal: a few mm in walks; 6 to 9 cm at the
   push-off of Jog and Sprint, where the target leg locks straight (the heel pivot sits farther from the hip than
   the source's ankle once the foot points down); rolls and swims far more.
5. **Bake.** One key per source frame (30 fps) on every target bone, quaternions kept on one hemisphere.
6. **Checks.** The **rest check** retargets the source rest and compares it with the target rest: 0.003 mm and 0
   degrees on both bodies (`retarget` fails above 0.01 mm or 0.01 degrees). It is a sanity check of the pipeline (the
   translations, the anchors, the IK and the bone order), not proof that the rests agree: the rotation formula returns
   the target rest for any source rest by construction, and the rest differences of step 2 pass through untouched.
   `test_retarget_blender.py` also bakes Walk_Loop (its legs reach the source's ankle path within 10 mm and no vertex
   goes 1 cm under the floor) and Death01 (no more than 3 cm deeper into the floor than UAL's own mannequin, scaled).

### The bone map

`tools/blender/retarget_maps/ual_um.toml`, checked by `tools/blender/retarget_map.py` (every bone of both rigs
accounted for exactly once; unknown keys refused):

| Key | Meaning |
|---|---|
| `[bones]` | `source = "target"`: rotation transfer (51 pairs) |
| `root`, `hips` | `[source, target]` pairs whose translation transfers: `root` by displacement, `hips` carried in the source bone's frame |
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
| `pairs` | for each `[[pairs]]` entry of `anim_review.toml`: the pack clip and its UAL counterparts side by side, a strip (front and side rows at the same fractions of each clip; each side cell framed on its own clip) and a looping MP4 (`pairs/<body>/<pack clip>.*`) |
| `rates` | locomotion at the game's speeds: each `[[rates]]` row (the game's walk 4.5 m/s, sprint 7.0 m/s) plays its clips side by side on a **treadmill** (light stripes on the floor moving at the row's speed), each at the rate that keeps its feet on it: UAL clips by their root-motion speed (`UAL1_Standard_RM.glb`, scaled to the body), pack clips by their feet's ground speed; `blend:A+B` is a blend of two UAL clips lined up on the left heel strike (cycle-synced) and weighted so that its stride over its cycle gives the speed. An MP4, a strip of 8 moments 0.1 s apart and `rates.json` (rate, cadence in steps/s, step length) per body type (`rates/<body>/`) |
| `sheets` | review sheets: each clip's men and women strips stacked, three clips a sheet (`sheets/`) |
| `table` | `metrics.json` (all measures) and `metrics.md` (a row per body type and clip) |

`clips` takes `--no-video` and `--no-strips` (measures only: about two minutes for all 134). A run with `--clips`
replaces only those clips' measures (its `metrics/<body>_part_c*.json` sort after the full run's and win in
`table`); a run with all clips replaces every measure of the body type. Only the **latest** partial run is kept: a
second `--clips` run deletes the first one's files, so the first run's clips fall back to the full run's measures.

Pictures: Workbench, flat material colours, specular off, neutral grey background, a dark floor slab whose top is
z = 0 (a line in the horizontal views), orthographic cameras, labels as text objects; videos are driven by a
frame-change handler that poses the characters, so each character can loop its own clip.

### Measures (`tools/blender/anim_metrics.py`, `anim_math.py`)

| Measure | Definition |
|---|---|
| Foot sliding | The foot bone (its pivot) is in contact while within 2 cm of its lowest height in the clip; the horizontal contact speed (central differences) gives the **ground speed** (the median contact velocity: the treadmill speed of an in-place clip) and the **slide** (contact velocity minus ground velocity: mean and max, cm/s). The table prints `-` when fewer than 4 contact velocities back it (Sprint_Loop has one). The numbers compare clips with each other: they depend on the 2 cm window and on the median as the ground estimate (a per-stance linear fit, as a reviewer measured it, reads 1.2 to 1.9 times higher), and because contact is relative to each foot's own lowest point, feet that never touch the floor (the airborne jump, the swims) still count as "in contact". The in-place ground speed of UAL's runs is 6 to 7% above the root-motion file's, which is the speed the `rates` step uses |
| Sole sliding (JSON only) | The same with the lowest shoe vertex against the floor; noisy on these toe-less feet (it counts the toe dragged by the toe lift) |
| Lowest vertex | The lowest vertex of all parts per frame (cm; the floor is 0): its minimum is how far anything goes below the floor |
| Hands in torso / head | The deepest hand vertex inside the convex hull of the torso vertices (`Body` to `Chest`) or of the head (cm) |
| Hands in the other hand / legs | The deepest vertex of one hand behind the faces of the other hand, and of either hand behind the faces of the legs (`UpperLeg`, `LowerLeg`), cm. Tested on the whole posed mesh less the querying hand's own faces (a BVH), counting only square-on hits (the vertex lies within about 45 degrees of the nearest face's inward normal), so concave hands and open cuts do not give false depths. A hand resting on a thigh reads 1 to 2 cm (the hand presses into the trouser surface) |
| Loop seam | The largest local bone rotation between the last and the first frame, also as a multiple of the median frame step (about 1 or less loops cleanly) |
| Past straight | Knees: the bend about the hinge axis carried by the upper bone (about X); its most negative value. Elbows are measured the same way (about -Z/+Z from the T-pose) but kept in the JSON only: without twist bones, upper-arm twist tilts the fixed hinge axis and a straight arm reads 17 to 32 degrees "past straight" |
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
