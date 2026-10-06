# Animations: the retarget and the review in motion

Our characters are built on the Quaternius **Ultimate Modular** Men and Women packs (CC0, xperiaroco2/prime-game#165):
one 62-bone armature, `CharacterArmature`, and 24 actions per body type, plus our toe bones `Toe.L` and `Toe.R` (art #25,
"The toe bones" below: 64 bones). This page covers how other clips get onto
that armature (the **retarget**) and how clips are judged (the **review**): always in motion, from frame strips and
looping clips plus measures, never from one frozen frame. The findings of the first review (art #20) and of the
second library (UAL2, art #24) are in [research/2026-10-03-animation-review.md](research/2026-10-03-animation-review.md);
the toe bones and the Meshy trial (art #25) in [research/2026-10-03-meshy-animations.md](research/2026-10-03-meshy-animations.md).

## Sources

| Source | Clips | Rig | Licence | Record |
|---|---|---|---|---|
| Ultimate Modular Men, any file but `Adventurer.glb` (the review uses `Business Man.glb`) | 24 actions | `CharacterArmature`, 62 bones | CC0 1.0 | #17's `sources/` |
| Ultimate Modular Women, any file (the review uses `Suit.glb`) | 24 actions, other motions than the men's | the same 62 bones | CC0 1.0 | #17's `sources/` |
| Universal Animation Library Standard (UAL1): `UAL1_Standard.glb` (in place) and `UAL1_Standard_RM.glb` (root motion) | 43 clips each | 65 bones, Unreal-mannequin names | CC0 1.0 | [`sources/quaternius_ual1_standard.toml`](../sources/quaternius_ual1_standard.toml) |
| Universal Animation Library 2 Standard (UAL2, art #24): `UAL2_Standard.glb` and `UAL2_Standard_RM.glb`, and a Female Mannequin without clips | 43 clips each, other motions than UAL1's | UAL1's rig exactly (the same 65 bones, parents and rest) | CC0 1.0 | [`sources/quaternius_ual2_standard.toml`](../sources/quaternius_ual2_standard.toml) |
| Meshy (art #25, batch 4, private raw files): `meshy`, Meshy's rig of m1_rex with its walking and running, ten library actions and the text-to-motion crawl; `meshyw`, its rig of w1_ivy with its walking, running, Walking Woman and Run Fast | 13 and 4 clips | Meshy's auto-rig, 24 bones, no fingers ([the research page](research/2026-10-03-meshy-animations.md)) | owned output of the Pro plan; the library motions' provenance is undisclosed: private only | [`batches/2026-10-b4-animations.toml`](../batches/2026-10-b4-animations.toml) |

Measured by `anim-review inventory` (2026-10-03): the 24 actions have the same keyframes in every file of a body type,
except the men's `Adventurer.glb`, whose 24 all differ (that character is bound 180 degrees off). The women's
versions of the same names are other motions (their poses differ by 9 to 145 degrees) and 25% longer (Idle 2.08 s
against 1.67 s). UAL is authored at 30 fps; its clips import to whole frames only when the scene runs at 30 fps.

## The two rigs

- **Ultimate Modular** (`CharacterArmature`, under the importer's `RootNode`, world scale 100): `Root` > `Body`
  (carries the legs: `UpperLeg`, `LowerLeg`) > `Hips` > `Abdomen` > `Torso` > `Chest` > `Neck` > `Head`, and
  `Shoulder`, `UpperArm`, `LowerArm`, `Wrist` per side. The **feet are children of `Root`**, not of the lower legs
  (baked IK targets), with `PT.L`/`PT.R` knee pole targets that deform nothing; a foot's pivot sits at the heel, 2 cm
  above the floor. **The pack has no toe bone**; ours, `Toe.L`/`Toe.R`, are added below each foot (next section). Fingers: `Index1` to `Index4` (and `Middle`, `Ring`, `Pinky`), where `1` is the
  metacarpal (its head at the wrist, 12 cm long) and `2` to `4` the phalanges; `Thumb1` to `Thumb3`.
- **UAL** (`Armature`, identity world matrix; UAL1 and UAL2 alike: `anim-review inventory` compares UAL2's rig with
  UAL1's, `rig_vs_ual` in `inventory.json`: the same names and parents, 0 mm and 0 degrees apart at rest): `root` >
  `pelvis` > `spine_01` to `spine_03` > `neck_01` > `Head`; `clavicle`, `upperarm`, `lowerarm`, `hand`; fingers `_01` to
  `_03` are phalanges (no finger metacarpals) plus `_04_leaf` ends; `thigh` > `calf` > `foot` > `ball` (toes). Both rigs
  rest in a T-pose, palms down, facing -Y.

## The toe bones (art #25)

The pack's shoes are rigid: each is weighted to its foot (and partly to the shin at the ankle), so a clip that rolls
over the toes tips the whole shoe onto its tip. `tools/blender/um/toes.py` adds `Toe.L` and `Toe.R`: children of the
feet, the head at the ball of the shoe (68% of its length from its back, along the foot's forward axis, 5 mm above
the sole), the tail at its tip, the foot's axes; every part's foot weights are split over the ball with a smoothstep
5 cm wide. The assembler adds them to every character (`build_character`; the saved file has 64 bones and every pack
part 64 vertex groups), the retarget to a pack original that a map with toes targets, and the review to its donors
(`toe_bones = true` in the settings). None of the pack's 24 actions keys a toe, so they play exactly as before (every
vertex of the pack's Walk within 0.01 mm: `test_anim_toes.py`); the export writes no toe track for them, and in Godot
the toes rest under the feet.

**For the contract v2:** two more deforming bones that the pack's own actions never animate; any clip with toes
(UAL1, UAL2, Meshy once mapped) bends the shoe, any clip without leaves it rigid. `SkeletonProfileHumanoid` has
`LeftToes`/`RightToes` for them.

## The retarget

`tools/run.py retarget [--body men|women] [--library ual|ual2] [--clips A,B|all] [--out DIR] [--blend] [--floor]
[--no-ik]` bakes the clips of a library (UAL1 by default, `--library ual2` for UAL2: its actions are named `UAL2|<clip>`
and its default output is `tools/out/retarget/ual2/<body>`) onto the body type's donor character
(`tools/blender/anim_review.toml`) in background Blender and writes `retarget_report.json` (with `--blend` also the
character with the baked actions `<label>|<clip>`, `UAL|`, `UAL2|` or `Meshy|`, saved as `<target>_<label>.blend` in lower case; with `--floor` each clip's lowest vertex on the target and on UAL's own
mannequin scaled to the target, which tells how deep a clip goes into the floor by itself and how much the retarget
adds). No add-on: `tools/blender/retarget_core.py`.

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
   jumps). The report's `ik_miss_mm` says how far a leg fell short of its goal: a few mm in walks; 4 to 5.5 cm at the
   push-off of Sprint and Jog, where the target leg locks straight (the heel pivot sits farther from the hip than
   the source's ankle once the foot points down); 2 to 6 cm in the falls, rolls, jumps and swims (before the hips fix
   the rolls missed by 23 to 25 cm).
   **Toes (art #25):** a mapped toe takes the source toe's world rotation, so it stays level while the heel rises and
   the shoe bends at the ball; after the IK the bones below each foot are re-attached to it, and each toe's tip gets
   the floor clamp too (pitched about the ball). With the toes the foot's own clamp holds the front of the foot's
   part of the sole (the ball), not the tip. The sole under the ball dips 0.6 to 1.1 cm below the floor for a frame
   or two in the walks (the bend of the blend zone; UAL's own mannequin goes 2.7 cm under in Walk_Loop).
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
| `[unused]` | source bones with no target (the leaves, `ball_leaf`) |
| `[source_rig]`, `[target_rig]` | the full bone lists, read from the files |

UAL2 takes this map unchanged: its rig is UAL1's (above), so no second map is needed.

Two more keys since art #25: **`root` may be left out** (a source with no root bone, Meshy's: our `Root` rests in
`[rest]` and `Body`, carried by the source hips, takes the travel), and **`[align]`** lists target bones whose rest
direction (towards their mapped child) is turned onto the source bone's before the transfer, for rests that differ
more than a motion can carry. The rest check then leaves the aligned bones and everything below them out and reports
the angles (`aligned_deg`).

**Meshy** (`meshy_um.toml`, `meshy_um_rigid.toml`): `Hips` -> `Body` (no root), `Spine02`, `Spine01`, `Spine` ->
`Abdomen`, `Torso`, `Chest`, `neck` -> `Neck`, `Head`, the shoulders, arms, forearms and hands, `Left/RightUpLeg`,
`Leg`, `Foot` (the IK legs, as for UAL) and `Left/RightToeBase` -> `Toe.L`/`Toe.R`; `head_end` and `headfront` unused;
every finger of ours at rest (Meshy's rig has none). `[align]` turns `UpperArm.L`/`.R`: Meshy placed its upper arms
14.2 to 14.9 degrees (the man's rig) and 9.5 to 10.4 (the woman's) below our mesh's T-pose arms, so without it an arm
hanging at the side on Meshy's rig would stand that far out on ours. `retarget --library meshy|meshyw` uses it; the
rest check is 0.002 mm and 0 degrees outside the arms. UAL's toes, `ball_l` and
`ball_r`, drive `Toe.L` and `Toe.R` (art #25). `ual_um_rigid.toml` is the same map with the toes unused and the toe
bones at rest: the rigid shoes of art #20 and #24, which the review's `feet` step shows beside the toe bones. A
library on another rig (Meshy's) names its own map in the review settings: `[libraries.<key>]` `map` and
`rigid_map`, files in `tools/blender/retarget_maps/` (checked to exist).

Fingers map by anatomy, not by number: UAL `index_01..03` (phalanges) go to `Index2..4`, and `Index1` (the
metacarpal) stays at rest; thumbs map 1:1. Hand close-ups confirmed curls bend the right way and pointing works.

## Text to motion: the SMPL-H retarget (art #33)

Meshy's text to motion returns each clip as an FBX on an **SMPL-H skeleton** (batch 4's crawl, batch 5's seven items:
`raw:2026-10-b4-animations/crawl-motion/`, `raw:2026-10-b5-anim-mvp/<item>/text_to_motion-clip.fbx`). They go straight
onto our rig with `tools/blender/retarget_maps/smpl_um.toml`: no Meshy rig and no animate step in between.

**The files** (all eight alike): FBX 7700; the armature `Reference` (top level, world rotation X +90, scale 0.01) with
52 bones in quaternions; a grey mannequin skinned to it (`arm`, `body`, `head`, `leg`, spheres `qiu_L1..6`,
`qiu_R1..6`) and three empties (`body.001`, `qiu_L`, `qiu_R`). One action, `Reference|SMPLH_Animation|Base Layer`,
keyed on frames 1 to N (N = 120, 90 or 75: 3.97, 2.97 or 2.47 s at 30 fps). Every bone keys location, rotation and
scale, but only `Pelvis`'s location moves and every scale is 1. The character faces -Y with its left at +X, as ours:
no axis flip. The bone tree: `Pelvis` (the top bone, no root) > `L_Hip` > `L_Knee` > `L_Ankle` > `L_Foot` (the ball,
14 cm in front of the ankle), `Spine1` > `Spine2` > `Spine3` > `Neck` > `Head`, `Spine3` > `L_Collar` > `L_Shoulder`
(the upper arm) > `L_Elbow` > `L_Wrist`; fingers `Index`, `Middle`, `Ring`, `Pinky` 1 to 3 (phalanges, 1 at the
knuckle) and `Thumb` 1 to 3 (1 the metacarpal); the right side alike. No leaf or end bones.

**The loader** (`tools/blender/retarget_smpl.py`) sets the scene to 30 fps and calls `import_scene.fbx` with explicit
options (`use_anim`, `anim_offset=1.0`, `ignore_leaf_bones=False`, `automatic_bone_orientation=False`,
`use_custom_props=False`, `global_scale=1.0`, `axis_forward='-Z'`, `axis_up='Y'`); the scene stays at 30 fps. It
deletes the empties, unassigns the action and resets the pose.

**The floor shift.** The file's rest is centred on the pelvis (pelvis -0.19 m, hip joints -0.28, ankles -1.056, the
mannequin's soles at **-1.161 in all eight files**) while its animation stands on z = 0 (a standing frame's lowest
vertex is 0.0001 to 0.0076 m). Given that rest unchanged, the height ratio, the hip anchor and the foot anchors are
garbage (a hip "height" of -0.28 m). So the loader lifts the armature by the rest's depth below the floor (1.161 m;
the meshes are its children and follow), and every sampler of the file takes the same lift back out of `Pelvis`'s
basis location (`anim_libs.Shifted`; `InPlace` builds on it): the offset `rot(rest[Pelvis])^-1 @ (Wi.to_3x3() @ (0, 0,
h))`, the formula `InPlace` uses for its drift. The rest then stands on the floor (its lowest vertex 0.000 mm) and the
motion keeps the file's world poses (turn-left-90 at frame 45: 0.0002 mm from a plain import). A `Rig` caches the
armature's matrix, so it is built after the shift. The retarget report records `floor_shift_m` (1.161).

**The scaling origin.** `retarget_core.Retargeter` scales positions about the floor point under each rig's origin
(z = 0), not about the origin itself, which the shift puts 1.161 m up. For every rig whose origin is on the floor
(UAL1, UAL2, Meshy's) this changes nothing: UAL1 onto the men still checks 0.0031 mm and Death01 still reaches -4.9 cm.

**The map** (52 pairs, all checked by `retarget_map.py`), against UAL's and Meshy's:

| | UAL (`ual_um.toml`) | Meshy (`meshy_um.toml`) | SMPL-H (`smpl_um.toml`) |
|---|---|---|---|
| File | GLB, in place plus an RM file | GLB, auto-rig | FBX, one clip per file |
| Rest | T-pose on z = 0 | T-pose on z = 0 | T-pose centred on the pelvis: the floor shift |
| Root | `root` -> `Root` | none (`Hips` carries it) | none: `Pelvis` -> `Body` carries the travel, `Root` at rest |
| Spine | pelvis, spine_01..03 | Hips, Spine02, Spine01, Spine | `Pelvis`, `Spine1`, `Spine2`, `Spine3`, `Neck`, `Head` -> `Body`, `Abdomen`, `Torso`, `Chest`, `Neck`, `Head`; `Hips` at rest |
| Arms | clavicle, upperarm, lowerarm, hand | Shoulder, Arm, ForeArm, Hand, `[align]` (10-15 degrees) | `L_Collar`, `L_Shoulder`, `L_Elbow`, `L_Wrist` -> `Shoulder.L`, `UpperArm.L`, `LowerArm.L`, `Wrist.L`; no `[align]` (2.6 degrees apart) |
| Legs (IK) | thigh, calf, foot | UpLeg, Leg, Foot | `L_Hip`, `L_Knee`, `L_Ankle` (`source_foot`, an ankle joint) |
| Toes | `ball_l` | `LeftToeBase` | `L_Foot` (the ball) -> `Toe.L` |
| Fingers | `_01..03` -> `2..4`, thumbs 1:1 | none (rest) | `L_Index1..3` -> `Index2..4.L` (and Middle, Ring, Pinky), thumbs 1:1; the metacarpals at rest |
| `[unused]` | the leaves | head_end, headfront | none |

**The fingers never move** in a text-to-motion clip: every joint holds SMPL-H's mean relaxed hand, on our phalanges a
constant 31.4 degrees per joint on average (index 25/44/13, middle 31/41/20, ring 38/40/25, pinky 46/32/22, thumb
52/29/35), where UAL's loose fist curls 78. The hand shape therefore changes when the game blends a text-to-motion clip
with a UAL clip; if that reads badly, keeping the fingers at rest is the alternative map.

**Proportions.** SMPL-H's hip joints stand 0.880 m up after the shift: a translation scale of **1.0953** (men, hip
joints 0.964 m) and **1.178** (women, 1.037 m). Our arms are short for that scale: shoulder to wrist 0.417 m (men) and
0.453 m (women), **0.71 of SMPL-H's 0.538 m scaled**; its shoulders are 0.331 m apart against 0.305 and 0.235. Arms
transfer by rotation, so a planted hand (on all fours) hovers about 7 to 8 cm higher on ours than on SMPL-H scaled,
and hanging hands come into the thighs: the women's 5.3 to 7.5 cm (the turn, the lift, the shove, the rollup, the
getup), the men's 6.5 and 6.7 in the shove and the getup.

**The library** (`tools/blender/anim_review.toml`, `[libraries.tm]`): `format = "smplh_fbx"`, `file` the rig (the crawl;
every file has the same rest, checked within 1 mm), `label = "TTM"`, `map = "smpl_um.toml"`, `own` (the SMPL-H
mannequin plays `tm_own:<clip>`), `in_place` (the travelling clips, for the review's lanes) and a `[libraries.tm.clips]`
table: clip name (the batch item's id) = its file. Clip keys are `tm:crawl`, `tm:backward-jog`, `tm:strafe-left`,
`tm:turn-left-90`, `tm:shove-stumble`, `tm:package-lift`, `tm:rollup-to-all-fours`, `tm:getup-from-all-fours`; no
raw clip loops, so `[loops]` has no `tm`. `anim_libs.load` dispatches on `format`; the runner refuses an unknown
format, a missing `clips` table and clip files that are no raw-relative FBX; `anim-review` checks every file before
Blender starts.

`tools/run.py retarget --library tm --body men|women [--clips crawl,backward-jog] [--floor] [--blend]` writes
`tools/out/retarget/tm/<body>/` with actions `TTM|<clip>`. Measured on 2026-10-06: the rest check 0.0008 mm (men) and
0.002 mm (women), 0 degrees, no aligned bone; the IK misses and the lowest vertex per clip, men / women:

| Clip | IK miss mm | Lowest cm (source's own mesh, scaled) |
|---|---|---|
| crawl | 0 / 0 | -0.6 (-0.8) / 1.7 (-0.9) |
| backward-jog | 0 / 0 | -2.5 (0.0) / -2.3 (0.0) |
| strafe-left | 16.1 / 9.9 | -1.8 (0.0) / -1.0 (0.0) |
| turn-left-90 | 16.4 / 10.4 | -0.3 (0.0) / -0.4 (0.0) |
| shove-stumble | 6.3 / 4.2 | -1.2 (0.0) / -0.4 (0.0) |
| package-lift | 0 / 0 | -2.8 (0.0) / -1.9 (0.0) |
| rollup-to-all-fours | 29.9 / 24.9 | **7.8** (-3.0) / **13.7** (-3.3) |
| getup-from-all-fours | 10.6 / 11.5 | **5.9** (-2.9) / **8.4** (-3.2) |

The turn's misses are its stepping leg standing nearly straight (a median of 5.2 mm short on the men, 16.4 mm where
its heel starts to rise and our leg locks, as at UAL's push-offs); the pivot foot is exact. The rollup and the getup
never touch the floor on ours: the source floats too (the next table), and our short arms cannot reach where its hands
dip. `test_retarget_smpl_blender.py` checks the shift, the rest on both bodies, the crawl's 119 frames and the turn.

**The raw motion** on our rig (no in-place; measured on 2026-10-06, men; the women's alike, scaled): what a clip
needs before it is used (art #33's clip edits).

| Clip | Travel | Heading and turn | Floor (lowest vertex per frame) | Other |
|---|---|---|---|---|
| crawl | 3.54 m, 0.89 m/s | 19 degrees left of straight | floats: median 6.5 cm, 15 cm at the start; -0.6 cm lowest | no loop (seam 59 degrees); hands 7-8 cm higher than SMPL-H's |
| backward-jog | 1.25 m back, 0.31 m/s | 7 degrees off straight back; facing within 8 | the men's toes 1.5 cm under the floor on the median frame (-2.5 lowest; the women's 0.0 and -2.3) | a jog almost in place: steps of 0.09-0.30 m; no loop (seam 23) |
| strafe-left | 9.6 m, 2.42 m/s | 73 degrees (17 forward of sideways); the facing drifts 8 | -1.8 lowest; up to 10 cm in its flight phases | a gallop of long and short steps; no loop (seam 49); hands 2.3 cm into the torso (women 4.2) |
| turn-left-90 | 0.12 m | turns 109 degrees net (peak 116), not 90 | on the floor (-0.3 to 0.9 cm) | still to 0.13 s; one step of the left foot |
| shove-stumble | 1.37 m back, 7 degrees off | facing steady | -0.8 to 4.2 cm | steps back 0.4-1.4 s, still from 1.5 s; hands into the legs 6.5 cm (women 7.2) |
| package-lift | in place | twists 32 degrees in the bend, ends 14 turned | toes -2.8 cm in the squat | squats wide; holds with the hands forward from 1.4 s |
| rollup-to-all-fours | 0.12 m | rolls over (the pelvis turns 180 degrees) | **floats the whole clip: median 15.6 cm, 7.8 to 31**; ends on all fours 13 cm up | starts lying, rolls over 1.1-1.6 s |
| getup-from-all-fours | 0.66 m | ends facing 17 degrees left of its start | **floats: starts 10 cm up on all fours, ends standing 13 cm up** (the source's pelvis 1.09 m against 0.97 standing) | on all fours to 0.55 s, rises 0.7-1.75 s |

The clip edits' `floor` lift pushes a clip up out of the floor; the rollup, the getup and the start of the crawl need
the opposite, a settle down onto the floor (the lowest vertex of the lying, kneeling or standing frames brought to 0).

**Gotchas.** Every file's action is called "Base Layer" (`load_glb`'s naming would make every clip "Base Layer"), so
the names come from the `clips` table and the loader renames the actions `SMPLH|<clip>`. Later imports name the
armature `Reference.001` and the action `....001`: the loader takes the objects and the action that import created.
Frames start at 1 (`anim_offset=1.0`); the bake starts at 0, so a clip of N frames bakes N - 1 intervals.
`use_custom_props=False` silences the importer's "Short" property warnings. The empties are deleted (they hang the
spheres' grouping, nothing deforms with them).

## The review

`tools/run.py anim-review <step> [--body men|women|both] [--clips pack:Walk,ual:Walk_Loop|all] [--sources ual2]
[--jobs N] [--out DIR]` (default output `tools/out/anim-review`; the review of art #20 went to
`D:/prime-art-raw/review/stage1/20/`, that of UAL2 (art #24) to `D:/prime-art-raw/review/stage1/24/`, outside git).
Steps, or `all` in this order:

| Step | Makes |
|---|---|
| `inventory` | `inventory.json`: every pack file's actions (lengths, identical across files or not), the men against the women, UAL's clips in both files with root motion per clip |
| `clips` | per body type and clip, on the unmodified donor character: measures (`metrics/<body>_c<n>.json`), a 12-frame strip with a front and a right-side row (`strips/<body>/<source>_<clip>.png`) and a looping 480x480 H.264 clip at 30 fps (`clips/<body>/...mp4`); `--jobs` Blender processes per body type |
| `pairs` | for each `[[pairs]]` entry of `anim_review.toml`: its clips side by side (the pack clip and its UAL counterparts, or any clip keys: see "Sources, clip keys and layers"), a strip (front and side rows at the same fractions of each clip; each side cell framed on its own clip) and a looping MP4 (`pairs/<body>/<pack clip or name>.*`) |
| `feet` | (art #25) for each `[[feet]]` row of the settings, each clip retargeted twice onto the same donor, with the library's `rigid_map` (rigid shoes) and its `map` (toe bones): a side close-up that follows the right shoe, 12 frames over one cycle (rigid on top), a looping side-by-side MP4 of whole cycles and both lanes' measures (`feet/<body>/<row>_<clip>.png`, `.mp4`, `<row>.json`) |
| `rates` | locomotion at the game's speeds: each `[[rates]]` row (the game's walk 4.5 m/s, sprint 7.0 m/s, and since art #24 the walk with the package: UAL2's carry as an upper-body layer) plays its clips side by side on a **treadmill** (light stripes on the floor moving at the row's speed), each at the rate that keeps its feet on it: library clips by their root-motion speed (each library's `_RM` file, `UAL1_Standard_RM.glb` or `UAL2_Standard_RM.glb`, scaled to the body), pack clips by their feet's ground speed; `blend:A+B` is a blend of two UAL clips lined up on the left heel strike (cycle-synced) and weighted so that its stride over its cycle gives the speed. An MP4, a strip of 8 moments 0.1 s apart and `rates.json` (rate, cadence in steps/s, step length) per body type (`rates/<body>/`) |
| `sheets` | review sheets: each clip's men and women strips stacked, three clips a sheet (`sheets/`) |
| `table` | `metrics.json` (all measures) and `metrics.md` (a row per body type and clip) |

`clips` takes `--no-video` and `--no-strips` (measures only: about two minutes for all 134). A run with `--clips`
replaces only those clips' measures (its `metrics/<body>_part_c*.json` sort after the full run's and win in
`table`); a run with all clips replaces every measure of the body type and also measures the layered clips named in
the settings' `[layer] clips` (since art #24: the carry idle `ual:Idle_Loop|ual2:Walk_Carry_Loop`), so they survive any
rerun. Only the **latest** partial run is kept: a second `--clips` run deletes the first one's files, so the first
run's clips fall back to the full run's measures.

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
| Toe (art #25, JSON) | Three sole vertices per shoe tracked through the clip (under the foot pivot, under the ball, the tip), while the tip is within 1 cm of the floor (or of its own lowest point in a clip whose tips never come down to the floor): `front_pitch_at_20_deg_lift` (the mean pitch of the front of the shoe into the floor at a heel lift of 15 to 25 degrees: about the lift for a rigid shoe, near 0 for a bending one), `heel_lift_front_level_max_deg` (how far the heel rises while the front stays within 10 degrees of level), `bend_in_contact_max_deg`, `tip_lowest_cm`. The sole sets of the other measures include the toe bones |

### Sources, clip keys and layers (art #24)

The review settings (`tools/blender/anim_review.toml`) name UAL1 (`ual`, `ual_rm`) and further libraries on its rig
under `[libraries.<key>]` (`file`, `rm`, `label`; UAL2 is `ual2`). Every library is one more source of clips, handled
like UAL1 by every step. Clip keys (`tools/blender/anim_keys.py`):

| Key | Meaning |
|---|---|
| `pack:<clip>`, `ual:<clip>`, `ual2:<clip>` | a pack action, a UAL1 clip, a UAL2 clip (retargeted) |
| `<library>_own:<clip>` | (art #25) the clip on the library's **own GLB**: Meshy's rig and weights on our mesh (comparison (a)), the bones renamed to ours through the map and the palette turned into flat colours (`anim_libs.own_character`); the settings' `own` names the character |
| `<library>_rigid:<clip>` | (art #25) the clip retargeted with the library's `rigid_map` (the toe bones at rest) |
| `<base>\|<upper>` | a **layered** clip: the base clip's hips and legs under the upper clip's `[layer] upper` bone (`Torso`) and every bone below it (spine, head, arms, fingers), the way an engine layers an upper-body clip with a bone filter; the upper clip is time-scaled to a whole number of its loops per base loop |
| `blend:<A>+<B>` | (rates only) a cycle-synced blend of two library clips; a name without a source is UAL1's; `\|<upper>` adds an upper-body layer, one upper loop per stride, lined up on the left heel strike |

A library entry may also take (art #25, `tools/blender/anim_libs.py`): `extra` (more GLBs on the same rig whose
actions join it; the load fails when a rest head differs by more than 1 mm), `rename` (action -> clip name), `skip`
(actions left out), `in_place` (clips whose hips' horizontal travel from the first to the last frame is taken out in
proportion to time), `own` (the character name of `<library>_own:` clips); `rm` is needed only on UAL's rig. A pair
or a `[[feet]]` row may keep to one body type (`body`); a `[[feet]]` row's `sets` are lists of any clip keys shown top
to bottom (a lane per key: the strip spans each clip's own length), its `clips` the rigid shoes over the toe bones as
before. The shoes in the close-ups are the vertices weighted most to a foot or a toe, so a merged mesh works.

`--sources ual2` (comma-separated; `pack`, `ual`, `ual2`, `meshy`, `meshyw`; a variant counts as its library) limits `clips` to those sources' clips and `pairs` and `rates`
to the rows that play one; its measures go to `metrics/<body>_s<sources>_c*.json`. `table` merges a full run's
`<body>_c*.json`, then the source runs' files (oldest first, so of two runs over overlapping sources such as `ual2`
and `ual,ual2` the later one wins), then a partial run's `<body>_part_c*.json`, each replacing the earlier measures of
the same clips; a source run deletes the body type's partial files, like a full run. `[[pairs]]` takes
either `pack` and `ual` (a pack clip against UAL1 clips, named after the pack clip, as in art #20) or `name` and
`clips` (any keys, layered ones included, and an optional `note`). `inventory.json` lists `libraries` and each
library's clips in place and with root motion (`ual2`, `ual2_rm`). A `rates` run with `--sources` replaces its
selected rows in `rates/<body>/rates.json` and keeps the other rows of an earlier run there.

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
- Add the toe bones before a character is placed or posed (`retarget_core.add_toes` right after `load_glb`): they are
  made in edit mode on the rest pose, from the shoe's rest vertices.
- Meshy's GLBs name their actions `Armature|walking_man|baselayer` (`load_glb` takes the middle part) and carry a
  one-frame bind pose `clip0` (skipped); the `Icosphere` beside each import is the glTF importer's own bone shape.
- Meshy's walk floats 0.7 to 1 cm above the floor (its feet never reach it); the toe measures then count contact from
  the tips' own lowest point. Meshy's rig has no fingers: the finger curl reads 0 on its own rig.
- The foot slide reads each rig's foot bone: on an own-rig lane (`<library>_own:`) that is the source's ankle (Meshy's
  `RightFoot`, 14 cm up), on our rig the heel pivot (2.3 cm up). Compare own-rig lanes with retargeted ones only at
  the same point (the sole's contact patch, or the pivot carried by the source's foot): art #25's 6.1 against 3.3 cm/s
  was the point, not the retarget (the research page).
- The side view (`anim_render.VIEWS["side"]`) looks at the character's right side; a label meant to stay readable in a
  side-view video goes at a lane's edge, not over the legs.
