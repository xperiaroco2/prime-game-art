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
| Meshy text to motion (art #25's crawl, art #33's batch 5, art #66's batch 6 of re-rolls, private raw files): `tm`, twelve FBX clips, one per file | 12 clips | SMPL-H, 52 bones with fingers, retargeted with `smpl_um.toml` ("Text to motion") | owned output of the Pro plan (`public_repo_ok = true`, `ai_generated = true`) | [`batches/2026-10-b4-animations.toml`](../batches/2026-10-b4-animations.toml), [`batches/2026-10-b5-anim-mvp.toml`](../batches/2026-10-b5-anim-mvp.toml), [`batches/2026-10-b6-anim-rerolls.toml`](../batches/2026-10-b6-anim-rerolls.toml) |

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
adds). Every clip also reports its one-frame pops (`pops`: [bone, frame, degrees], `rc.pops`; the runner warns), a bone
snapping between two held poses (art #33). No add-on: `tools/blender/retarget_core.py`.

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
   pitched about its pivot until its toe is no lower than the rest sole, while the pivot is near the floor (fully
   from 2 cm below its rest height to 20 cm above it, fading out over the next 10 cm above and the next 4 cm below:
   a pivot well below the floor is an in-place jump without its rise, which the clamp leaves alone;
   `anim_math.floor_clamp_weight`). Until art #33 the clamp switched off at once 2 cm below, so a foot hovering on
   that line flicked between clamped and free: UAL's Jump_Loop pitched its right foot 53 degrees and back in one
   frame, four times a loop (twice on the women); with the fade its largest frame step is 2.7 degrees. The report's `ik_miss_mm` says how far a leg fell short of its goal: a few mm in walks; 4 to 5.5 cm at the
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
   goes 1 cm under the floor), Death01 (no more than 3 cm deeper into the floor than UAL's own mannequin, scaled) and
   Jump_Loop (in place, its right foot on the clamp's old 2 cm line: neither it nor the walk has a one-frame pop).

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
`tm:turn-left-90`, `tm:shove-stumble`, `tm:package-lift`, `tm:rollup-to-all-fours`, `tm:getup-from-all-fours`, and
batch 6's re-rolls (art #66) `tm:backward-run`, `tm:strafe-left-r2`, `tm:rollup-to-all-fours-r2`, `tm:crawl-r2`; no
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

Batch 6's re-rolls (art #66, measured on 2026-10-08 with `anim-review clips` and the set's build reports, men / women;
no in-place), each against the fault it was asked to fix:

| Clip (re-roll of) | Travel | Heading and turn | Floor (lowest vertex) | Other |
|---|---|---|---|---|
| backward-run (backward-jog) | 1.4 / 1.5 m/s back (the old 0.31); its best 1 s cut 2.03 / 2.16 m/s at 2.0 steps/s | 5.5 degrees off straight back (the old 7); faces within 7 | -2.2 / -1.7 cm lowest, up to 3.0 / 5.7 | no loop (seam 43); its best cut's raw seam 24.1 / 28.0 (right upper arm); the stride grows 1.13 / 1.07x at 4 steps/s (the old 7-8x); hands into the legs 6.8 / 8.0 cm, the torso 4.3 / 0.2 |
| strafe-left-r2 (strafe-left) | 1.3 m/s on the feet, 3.1 / 3.4 m/s in its best cut | **50 degrees left of forward (40 forward of sideways; the old 17); the body turns towards its travel: after the heading the hips face 77.5 degrees and the head 63.7 off the aim (the old 19.5 and -15.9)** | -1.7 / -1.3 lowest; up to 16 cm in flight | no strafe: a run turned to the left; the best cut's raw seam 9.0 / 8.7; **hands 11.4 / 8.1 cm into the torso** (the old 2.3 / 4.2) |
| rollup-to-all-fours-r2 (rollup-to-all-fours) | 0.07 m/s | **rolls backwards over its head (2.2-2.8 s)**, not onto the stomach | **floats the whole clip: 4.4 / 18.4 cm at best, up to 32.5 / 34.7** (the old 7.8 / 13.7) | lies still to 1.8 s; ends on hands and knees; after the settle each frame's lowest vertex at most 6.0 / 6.7 cm up (the old 10.9 / 7.9) |
| crawl-r2 (crawl) | 0.42 / 0.46 m/s; its best cut 0.64 / 0.69 | 0.6 degrees off straight (the old 19) | -1.1 / -2.4 lowest, up to 6.0 / 5.4; the cut floats 1.5 / 0.8 cm (the old 5.1 / 3.3) | no loop (seam 31), its best cut (1.2 s from 0.6 s) 19.1 (left upper arm; the old 26.4); no hand in the torso |

The clip edits' `floor` lift pushes a clip up out of the floor; the rollup, the getup and the start of the crawl need
the opposite, a settle down onto the floor (the lowest vertex of the lying, kneeling or standing frames brought to 0).

**Gotchas.** Every file's action is called "Base Layer" (`load_glb`'s naming would make every clip "Base Layer"), so
the names come from the `clips` table and the loader renames the actions `SMPLH|<clip>`. Later imports name the
armature `Reference.001` and the action `....001`: the loader takes the objects and the action that import created.
Frames start at 1 (`anim_offset=1.0`); the bake starts at 0, so a clip of N frames bakes N - 1 intervals.
`use_custom_props=False` silences the importer's "Short" property warnings. The empties are deleted (they hang the
spheres' grouping, nothing deforms with them).

## Clip edits (art #33)

The clip edits turn a retargeted clip into one the game can play: they cut a loop at its best seam, take the travel
out, straighten the heading, rescale a turn, trim, retime, reverse, mirror left and right, warp the stride to a speed
with the feet planted, lift a clip out of the floor, turn the arms out of the legs or the hands apart, hold a box by
its sides, and lean the upper body forward. The code is in two modules:

- `tools/blender/anim_edit_math.py`: the pure math (standard library only), with unit tests in
  `tools/tests/test_anim_edit_math.py` (`test_anim_edit_settle.py`, `test_anim_edit_lean.py`,
  `test_anim_edit_grip.py`);
- `tools/blender/anim_edit.py`: the Blender side, with tests on the real pack and UAL clips in
  `tools/tests/test_anim_edit_blender.py` (skipped without Blender or the raw files).

An animation set ("Animation sets" below; `anim-set`, `tools/blender/anim_sets/`) runs the edits from a settings
file; this section describes the edits themselves.

### The model

The edits work on our rig after the retarget, so one tool set serves the pack's clips, UAL1, UAL2 and Meshy text to
motion. A clip is a `Frames` object:

- `rig`: the donor's `rc.Rig`;
- `basis`: one `{bone: basis Matrix}` per frame on the 30 fps grid, every bone of the rig;
- `fps` (30), `loop` (a closed loop: its last frame equals its first) and `info` (the step reports in `info["steps"]`,
  and the latest measured speed and travel in `info["speed_m_s"]` and `info["travel_m"]`).

A `Frames` comes from any sampler (`rc.Sampler`, `anim_libs.InPlace`, a layered sampler) at integer frames, so the
pack's 24 fps keys are sampled on the 30 fps grid. Armature-space poses come from `rc.fk`; a changed pose goes back to
a basis through the parent's pose (only the bones an edit changes get a new basis, so the bones below them follow);
`to_action` bakes the frames with `rc.bake`.

#### Rig facts the edits rely on

On a pack original after `rc.add_toes` (64 bones):

- **Root carries everything:** `Body` (legs and spine), the IK feet `Foot.L/R` and the knee poles `PT.L/R`. A
  whole-character move (in place, heading, turn, lift) is a change of Root's pose alone.
- **The feet are IK targets in Root space.** Moving a foot means re-solving `UpperLeg` and `LowerLeg` (children of
  `Body`) with the two-bone IK. The shin's end is `P[LowerLeg] @ (rest[LowerLeg]^-1 @ rest[Foot])`; after the IK the
  foot goes to the shin's end and keeps its rotation.
- **The toes** are children of the feet and follow them.
- **World axes:** front -Y, left +X, up +Z, floor z = 0.
- **Armature axes are not world axes:** the armature has a world scale of 100 and its RootNode a -90 degree turn about
  X. Every edit converts through `rig.W` and `rig.Wi` (`rc.rot` for rotations).
- **Contacts** use the review's rule: a `Foot.*` pivot within 2 cm of its own lowest height in the clip
  (`anim_math.CONTACT_WINDOW_M`).
- **Facing** is the `Body` bone's horizontal forward axis plus its hip line turned 90 degrees, so it holds while the
  body bends forward on all fours and while it lies on its back.

### The ops

A settings file gives each clip a list of steps, `{op = "...", ...}`; any step may add `body = "men"` or `"women"`
and is then skipped on the other body type. Times are seconds in the clip as it stands at that step.
`anim_edit_math.check_steps(steps)` returns the errors of a list of steps (the runner and the tests share it);
`anim_edit_math.OPS` is the schema (each parameter's type, whether it is required, and its default).

| op | Parameters | What it does | Reports |
|---|---|---|---|
| `trim` | `start_s` (0), `end_s` (omitted: to the end) | keeps [start, end], a whole number of frames resampled from start; the result is not a closed loop | frames, seconds |
| `retime` | exactly one of `seconds`, `rate`, `speed_m_s`; `natural_m_s` | resamples to a new length, rounded to whole frames (a closed loop stays closed: its period scales). For `speed_m_s` the rate is speed / natural, where natural is `natural_m_s`, else the travel speed an earlier `cycle`, `in_place` or `stride` step measured, else the feet's in-place ground speed | rate, rate_eff, seconds, frames, natural_m_s and natural_from |
| `reverse` | none | the frames in reverse order | none |
| `cycle` | `min_s`, `max_s`, `within` = [a_s, b_s], `max_raw_seam_deg` (15) | picks the frame pair (i, j) whose poses differ least ("The cycle cut" below), cuts i..j and closes the loop: each channel's residual (frame j against frame i) is spread linearly over the cycle, rotations by slerp, so the last frame equals the first and the travel is taken out linearly. Fails when the raw seam of the body bones at the best pair exceeds `max_raw_seam_deg` | i_s, j_s, cycle_s, raw_seam_deg and its bone, finger_seam_deg, cost, travel_m, speed_m_s, yaw_drift_deg |
| `in_place` | `mode` = `linear` or `path`, `smooth_s` (0.6) | takes the Body's horizontal travel out by moving Root. `linear`: first to last in proportion to time. `path`: the Body's path low-passed by a centred moving average of `smooth_s` (its ends extended by point reflection), so a one-shot keeps its sway and stays over its start | travel_m, speed_m_s (the moving part), max_offset_m, travel_after_m |
| `heading` | `travel` = forward, back, left or right; or `facing` = start, end or mean | one constant turn about the world vertical through the first frame's Body. `travel` puts the least-squares direction of the Body's path on that axis; `facing` puts the Body's facing at the start, the end or on average on -Y | turned_deg, travel_dir_deg (before and after), facing_mean_deg, crab_deg (facing against travel) |
| `turn` | `total_deg` | rescales the clip's own turn: each frame turns Root about the Body's vertical by (total / net - 1)(yaw(t) - yaw(0)), so the planted feet turn in place | net_before_deg, net_after_deg, peak_before_deg |
| `mirror` | none | left-right mirror ("The mirror" below) | rest_error_mm, rest_error_deg, asymmetry_mm |
| `stride` | `speed_m_s`; `cadence` (steps/s) or `rate`; `plant` (true); `natural_m_s`; `warn` ([0.6, 1.6]); `fail` ([0.4, 2.5]) | stride warping of an in-place loop ("Stride warping" below) | rate, scale, natural_m_s, natural_cadence, cadence, step_m, cycle_s, ground_axis, ik_miss_contact_mm, ik_miss_mm, knee_past_straight_deg, fit (ok, warn, fail), ground_speed_after_m_s, slide_mean_cm_s, slide_max_cm_s |
| `floor` | `mode` = `lift`, `hips` or `settle`, `from_s` (0), `to_s` (the end), `fade_s` (0.2), `min_depth_cm` (0.3) | per frame, the posed meshes' lowest vertex below the floor (deeper than `min_depth_cm`) inside the window gives a lift profile: a running max over +-2 frames, smoothed over +-2 frames, held at the window's edges and faded to 0 over `fade_s` outside it. `lift` moves Root (everything: lying, crawling). `hips` moves Body and re-solves the legs to their feet, up to three rounds; it measures without the shoes, which a lift of the hips cannot move. `settle` (art #33) does the opposite for a clip that floats (Meshy's crawl, roll-up and get-up): the heights of the lowest vertex above the floor as a running min over +-2 frames, smoothed and faded the same way, move Root down, so no frame goes under the floor (`anim_edit_math.settle_profile`) | lowest_before_cm, lowest_after_cm, max_lift_cm, window_s; for `hips` also shoes_lowest_after_cm; for `settle` max_drop_cm and highest_low_after_cm |
| `arm_offset` | `abduct_deg` (a number or `"auto"`), `max_deg` (12), `margin_cm` (0.3), `axis` (`out`; art #70: `swing`) | turns each upper arm away from the body about the chest's forward axis at the shoulder joint, by one angle on every frame (only UpperArm's basis changes, so the arm below follows); with `axis = "swing"`, about the chest's left-right axis instead, a positive angle swinging both hands forward and a negative one back (the crouch, whose hands go into the thighs from the front or behind, where turning them out does not help). `auto` finds the smallest angle (bisection to 0.5 degrees, up to `max_deg`) at which no hand vertex is inside the legs (`hands_in_legs`), on the frames that were inside and their neighbours, then adds the angle that moves the hand `margin_cm` further; `out` searches outwards only (0 to `max_deg`), a swing both ways (0 to `max_deg` forward and back, art #69) and keeps the smaller angle, forward on a tie | deg, axis, found, hands_in_legs before and after (cm), frames in the legs before and after |
| `hand_spacing` | `min_gap_cm` or `gap_m`; `at` = all, end or mean; `deg` (a number or `"auto"`); `max_deg` (25) | turns each upper arm about the world vertical at its shoulder, the hands moving apart symmetrically (a negative angle brings them together). `min_gap_cm`: no hand inside the other and at least that gap between their closest vertices (on every frame, at the end, or on average). `gap_m`: the closest distance between the two hands' vertices at `at` (all: the smallest) reaches the gap, searched in [-max_deg, max_deg] | deg, found, gap before and after (cm), hands_in_each_other before and after (cm), min_gap_after_cm |
| `side_grip` (art #65) | `gap_m`; `tilt_deg` (0), `forearm_share` (0.5), `from_s` (0), `fade_s` (0), `max_deg` (40), `tol_cm` (0.3) | both hands hold a box by its sides, on every frame from `from_s` (faded in by a smoothstep over the `fade_s` before it): each upper arm turns at the shoulder about the axis across its shoulder-wrist line and the line from the other wrist (the hand moves straight away from the other: about the vertical for arms held forward, out to the side for hanging ones), by one angle for both found per frame by a secant search, so the closest distance between the hands' vertices is `gap_m` (within `tol_cm`); then each palm faces the other hand: the forearm rolls about the elbow-wrist line by `forearm_share` of the roll that points the palm (`anim_edit_math.palm_normal`: the wrist, the middle, index and pinky knuckles) at the horizontal line to the other wrist turned up by `tilt_deg` (`grip_goal`, `roll_angle`), and the hand turns at the wrist by the shortest turn that finishes it (a bent wrist cannot face it by a roll alone) | frames, frames_full, not_found, deg, gap_before_cm and gap_after_cm, hands_in_each_other_after_cm, hands_in_torso_before_cm and after, roll_deg, palm_up_before_deg and after (the palm normal's angle over the horizontal), palm_aim_err_deg, hand_height_m, hand_height_diff_cm, hand_forward_m (each min, mean, max over the full-weight frames), first and last (frame 0 at full weight and the last frame: gap_cm, deg, w, hand_height_m and hand_forward_m per hand), hands_lowest_s and hands_lowest_m |
| `upper_match` (art #65) | `from_clip`; `frame` (0), `at` (`end`), `fade_s` (0.3), `base_clip` (none) | the upper layer's bones (the set's `upper` and every bone below it) go to `from_clip`'s frame `frame` at one end of a one-shot: each bone's basis rotation slerps and its location lerps to the other clip's, fully on the touching frame (the last for `end`, the first for `start`) and faded to the clip's own by a smoothstep over the `fade_s` before it (`anim_edit_math.end_weights`), so the game's crossfade into that clip as an upper layer moves no hand; with `base_clip` (the clip the game plays under it as the lower layer: the idle) the bones that carry the upper layer (the `upper` bone's parents under Root: Body, Hips, Abdomen) go the same way to `base_clip`'s first frame in armature space (the set's frame), less its stance lift, which `idle_ends` adds back; `idle_ends` after it puts the legs back on the feet; run it before `side_grip`, which then holds the grip on the faded frames (Pickup_Package's end takes Carry_Upper_Loop's first frame over Idle_Loop's) | from_clip, frame, at, fade_s, base_clip, carried_by, body_move_cm (how far the touching frame's Body moved), frames_faded, bones, max_turn_deg and max_turn_bone (the largest basis turn on the touching frame), wrist_move_cm per hand (how far the touching frame's wrists moved: the jump taken out) |
| `lean` | `deg`; `bone` (`Torso`; a spine bone between Body and Head: Hips, Abdomen, Torso, Chest or Neck) | turns that bone forward by `deg` about the body's left-right axis through its head, on every frame; the bones below follow, the legs and the IK feet stay. For an upper-body layer whose source leans with the hips: the game's layer starts at `Torso`, so the hips' lean is lost over an upright base (UAL Push_Loop's hands go up over the head) | bone, deg, tilt_before_deg and tilt_after_deg (the mean forward tilt of the line from the bone to Head), head_forward_cm |
| `foot_turn` (art #49) | `bone` (`Foot.L` or `Foot.R`), `toe_in_deg` | turns the foot toe-in about the world vertical through its head (the ankle) on every frame; its leg swivels with it about the hip-ankle line (the knee follows the toe) and is re-solved by the two-bone IK, so the shin's end stays on the foot | bone, toe_in_deg, yaw_out_before_deg and yaw_out_after_deg (first, min, max), swivel_deg, ik_miss_mm, ankle_gap_mm_max |
| `stance` (art #49) | `out_cm` (2.0), `keep` (`leg_extension_f0`, the only choice) | the feet about hip width and planted: each foot moves (its rotation kept) to one point for the whole clip, its own hip joint at the first frame plus the rest pose's hip-to-ankle offset plus `out_cm` outwards (along X: the set's clips face -Y); the Body rises by the one constant that keeps the legs' mean hip-to-ankle distance at the first frame; each leg is re-solved per frame by the two-bone IK, the knee towards the foot's own forward | out_cm, body_lift_cm, feet_m, width_cm and stagger_cm (before, after), hip_width_cm, ankle_gap_mm_max |
| `shoulders` (art #49) | `drop_deg` | both clavicles (`Shoulder.L/R`) turned down about the chest's forward axis through their heads | drop_deg, shoulder_rise_cm (the shoulder joint over the clavicle's root, first frame, before and after) |
| `head_level` (art #49) | `target_deg` (0), `neck_share` (0.4) | one constant pitch, `target_deg` minus the clip's mean head pitch, `neck_share` of it on `Neck` and the rest on `Head`, about the head's horizontal left-right axis (+ raises the face); the nods keep their motion | fix_deg, neck_deg, head_deg, pitch_before_deg, pitch_after_deg |
| `hands_relax` (art #49) | `curl_deg` (a table: `Index`, `Middle`, `Ring`, `Pinky` = 3 angles for segments 2-4, `Thumb` = 2 for segments 2-3), `cap` (> 0) | each curled finger bone keeps the axis of its own rotation and takes the table's angle; with `cap`, its own angle up to `cap` times the table's (a gesture stays, a fist goes). The metacarpals (segment 1) are untouched | cap, bones, curl_before_deg and curl_after_deg per segment |
| `thumb_in` (art #49) | `beside` (`Index3` or `Index4`), `side_cm` (1.6), `max_deg` (40), `frame` (0), or `from_clip` alone | Thumb1 turned by one constant per side on every frame: the shortest turn about its head that points the thumb's tip (Thumb3's head plus 0.9 of the Thumb2-Thumb3 segment) at a point `side_cm` beside the `beside` joint, found on `frame`; with `from_clip`, the turn that clip's `thumb_in` found | per side turn_deg, wanted_deg, quaternion_wxyz, tip_to_goal_cm_before; or from_clip |
| `idle_ends` (art #49) | `at` (`start`, `end` or `both`), `from_clip` (the idle), `upper` (true; false: the feet and legs only), `fade_frames` (8), `plant_speed_cm` (1.0), `plant_rise_cm` (1.5), `step_cm` (4.0), `knees_out_deg` (25), `knees_out_from_deg` (25), `knees_out_full_deg` (75), `match` (`set`; `root`) | blends the relaxed idle into a one-shot's ends that meet it ("The relaxed idle" below) | at, upper, match, lift_cm, upper_delta_deg, ends (per end and foot: planted_to, mode, window, move_cm, turn_deg; a held foot's shuffle_rise_cm and shuffle_moves_cm; lift_dropped), touching (the feet, their toes, the Body and the upper body against the idle, before and after: relative to Root and in the set's frame, `set_*`, with the Root's own offset, root_cm and root_turn_deg), leg_twist_deg, ankle_gap_mm_max, knee_out_deg_max, lift_cut_mm_max, foot_pulled_mm_max, body_down_mm_max, step_lift_cm, reroot (moved_cm_max, turned_deg_max), floor (per foot: below_mm_max, raised_mm_max, slide_mm_max, slide_frame), air (hop_cm_max, hop_frame, airborne_frames) |

Steps raise `anim_edit.EditError` on a failure (an unknown op, a bad parameter, a window outside the clip, a cycle
whose raw seam is too large, a stride on a clip that is not an in-place loop); `apply` names the failing step. A
stride's `fit` of `warn` or `fail` is reported, not raised.

#### The cycle cut

Each frame gives a feature vector: every non-finger bone's local quaternion (on the first frame's hemisphere, times 2:
about radians), the Body's height and each foot's position relative to the Body (both over 0.2 m, so 20 cm count like
a radian). `best_cycle` minimises the squared feature distance plus that of the velocities (central differences over
0.1 s) over the pairs i < j inside `within` with j - i between `min_s` and `max_s`. The raw seam (the largest body
bone rotation between frame j and frame i) guards the closing: closing spreads any residual, so without the guard it
would hide a bad cut.

Closing blends every channel by itself: the IK feet (children of Root) by location, the legs under Body by rotation.
Between the cut's ends the shin's end therefore parts from its Foot bone (15 cm mid-cycle on the crawl's 26-degree
cut, which tore the exported ankle), so the cycle solves both legs again on every frame to the closed feet and reports
the gap it mended (`leg_gap_before_mm`) and the IK miss (`ik_miss_mm`: where a closed foot is out of the leg's reach,
the foot goes to the shin's end).

#### Stride warping

The input is an in-place loop. Its natural ground speed `v0` is the median contact velocity of the feet (the
treadmill speed under it, `anim_math.foot_sliding`'s rule) or `natural_m_s`; its natural cadence `c0` is the contact
windows of both feet per cycle over the cycle's length.

1. **Rate.** `r = cadence / c0` (or the given rate), rounded so the cycle is a whole number of frames: `r_eff`.
2. **Scale.** `s = speed / (r_eff * v0)`.
3. **Ground axis.** `d`, the direction of the median contact velocity (backwards under a forward run, sideways under a
   strafe).
4. **Foot targets.** After the retime, each foot pivot's horizontal offset from the Body, `o`, becomes
   `o + (s - 1)(o.d)d`; its height and rotation are unchanged, so the toes and the retarget's toe lift hold.
5. **Plant** (`plant = true`). In each contact window the foot's horizontal track becomes a straight line at exactly
   the ground's velocity (`speed` along `d`), anchored at the window's middle; the two frames before and after the
   window blend towards the line by 2/3 and 1/3.
6. **IK.** UpperLeg and LowerLeg are re-solved with the two-bone IK. The knee bends in its current plane: the knee's
   offset from the leg's current hip-ankle line, plus a small pull to the front for a straight leg (the offset from
   the line to the new goal would turn a straight stance leg's knee backwards when the stride shortens). The miss is
   recorded on contact frames and on all frames.

The clip then plays at 1.0x at `speed`, its planted feet move at exactly `speed`, and the arms swing at the new
cadence. The fit is `warn` outside [0.6, 1.6] and `fail` outside [0.4, 2.5] by default.

Measured on UAL's Jog_Fwd_Loop at 4.5 m/s and cadence 2.8 (`tools/out/tests/anim_edit/edits.json` and the review
renders):

| Body | v0 (m/s) | c0 (steps/s) | r_eff | s | Cadence | Step | IK miss (contact / all) | Knee past straight | Feet after |
|---|---|---|---|---|---|---|---|---|---|
| men | 5.95 | 2.14 | 1.333 (28 to 21 frames) | 0.567 (warn) | 2.86 steps/s | 1.575 m | 0.0 / 0.0 mm | 0.0 deg | 4.50 m/s, slide 0.0 cm/s |
| women | 6.42 | 2.14 | 1.333 | 0.525 (warn) | 2.86 steps/s | 1.575 m | 0.0 / 0.0 mm | 0.0 deg | 4.50 m/s, slide 0.0 cm/s |

The Jog itself lands in `warn` (its steps shrink to 0.53 to 0.57 of their length); the stance legs bend more than in
the original, which the treadmill review judges.

#### The mirror

- **Pairs:** `X.L` and `X.R` swap (arms, fingers, legs, feet, toes, poles); the centre bones map to themselves.
- **Reflection:** `S = rig.Wi @ diag(-1, 1, 1, 1) @ rig.W` reflects world X in armature space (computed, not assumed).
- **Formula:** `P'[b] = S @ P[m(b)] @ C[b]`, with the constant correction `C[b] = (S @ rest[m(b)])^-1 @ rest[b]` from
  the rest.
- **Properties:** it assumes nothing about bone rolls; it is exact at rest by construction; `P'` is a proper rotation
  (det +1); mirroring twice gives the pose back (`S S = I`, `C[m(b)] C[b] = I`).
- Bones that never move (their basis location stays within 0.1 mm on both sides) keep their rest offset: the rig's
  small asymmetry (0.06 mm on the Walk, 0.3 mm on Punch_Right) is reported as `asymmetry_mm`, not keyed.

#### Resampling

Trim, retime and stride sample frames at fractional times by a Catmull-Rom spline through the four neighbouring frames
(wrapped over a closed loop's seam): locations and scales per component, rotations on the quaternion components
aligned to one hemisphere and normalised. A UAL Walk_Loop retimed to 1.25x and back stays within 0.02 degrees on the
upper body and 1.3 degrees on the legs (the IK bends sharply at a foot plant); the toe bones flick up to 28 degrees a
frame where the retarget's floor clamp lifts them, which no resampling keeps (5 degrees after the round trip).

#### The relaxed idle (art #49)

The engineer's notes (2026-10-07): the feet straight and the idle relaxed. UAL's Idle_Loop turns the right foot 44
degrees out and stands tense: fists (Middle2 78 degrees), a wide staggered stance (ankles 47.7 cm apart, the right
foot 45.7 cm behind the left: men), the head 10 to 15 degrees down. The lab worked the edit out on a copy of the set (round D:
`D:/prime-art-raw/research/2026-10-05-faces/lab/clay_d/clay_idle.py` and `README_idle.txt`); these ops are its port.
Built with the lab's values, round 1 matched the lab's relaxed set within 0.4 mm at every joint on every frame; round 2
fixed what the reviews found in the lab's idle_ends (a creeping foot slid, a settling foot sunk, the package clips left
out), and the set pins the women's arm offset that `auto` finds instead of the lab's
([research/2026-10-08-relaxed-idle.md](research/2026-10-08-relaxed-idle.md)).

- **Constant offsets.** Every op adds a constant to the clip's own pose on every frame, so the breathing, the sway and
  the talk's nods keep their motion; a loop stays closed. The ops work in world space through `rig.W`, on an
  `_Pose` (one frame's basis, its poses by `rc.fk`, a bone moved by a world transform).
- **The feet's IK.** `foot_turn`, `stance` and `idle_ends` keep each shin's end (the rest Foot head carried by
  `LowerLeg`) on its IK foot: 0.001 to 0.05 mm. Round C's swivel about the hip and `LowerLeg`'s tail (an 8 mm bone at
  the knee) turned the shin about the thigh and left the ankle 7 to 14 cm off; `foot_turn` swivels about the hip and
  the shin's end instead, then solves the IK. The build report's `feet` (below) measures every clip.
- **The idle and the clips that meet it.** `apply` keeps a clip's first frame as it stood before its first relaxed-idle
  op (`info["relax_base"]`, anim_edit_math.RELAX_OPS) and `stance` its lift (`info["stance_lift_m"]`). `idle_ends`
  reads both from the idle (`from_clip`, a clip built earlier in the set: `Target.clips`) and, at the clip's touching
  frame:
  - the upper body takes the idle's own change (each basis rotation of `Shoulder`, `UpperArm`, `Neck`, `Head` and
    `Thumb1`, relax base to relaxed) and the curled fingers go to the idle's curl, in full at the touching frame and
    faded out over `fade_frames` (a smoothstep); `upper = false` leaves them alone (the package clips: the arms keep
    their hold);
  - each foot goes where the idle has it (the right foot's turn included; its toes bent as the idle's: the package
    clip's toes, bent 20 to 42 degrees, went 4.4 cm into the floor on the idle's lower feet). By default (`match =
    "set"`) that is in the set's frame, armature space: the game plays the clips in place with no root motion
    (`contract/contract.toml`, `[animation] in_place`), so a crossfade blends Root too, and a foot matched relative to
    a Root that stands or turns off the idle's moves with it (round 2: the package clips' Root, turned 19.8 degrees by
    art #33's `heading facing = "mean"`, turned both feet 19.8 degrees and the right one 8 to 12 cm at every
    crossfade; the UAL clips' Root stands 0.2 to 6 cm off the idle's while their Body stands within 0.4 cm). With
    `"set"` Root itself then goes to the idle's on every frame and the bones under it keep their poses (Root carries
    no weights: `contract.toml`), so the crossfade, which blends each bone relative to its parent, blends no Root
    turn into the feet (`reroot`: how far Root moved and turned). `match = "root"` matches relative to the clip's
    Root, for a clip whose whole body ends off the idle's (Getup_Back stands up
    17 cm, men, and 27 cm, women, from where the idle stands: its feet in the set's frame would be that far from
    under it). The foot is held while
    the clip keeps it planted (`anim_edit_math.planted_until`: under `plant_speed_cm` a frame along the floor and under
    `plant_rise_cm` above its height at the touching frame; a flat foot that creeps along the floor or settles onto it
    is planted), then faded out over up to `fade_frames`; a foot that only shuffles along the floor through its fade
    (rising under half of `step_cm`) is lifted on the step's arc so the fade does not slide it (`lifted`), one that
    leaves the floor by itself is not; held to the other end when fewer than 2 frames would be left (the landing); a
    foot planted all through a clip whose other end meets another clip takes a `step_cm` high step over
    `fade_frames` where the other foot moves least (Raise_In and Raise_Out, the left foot), off the frames where the
    other foot is lifted;
  - between two ends that meet the idle, a foot that only shuffles along the floor (it moves after the start's
    planted frames and before the end's, rising under half of `step_cm`) is held at the idle's on every frame, its
    toes at the idle's bend (`hold`; its shuffle is dropped). Round 2 faded both package feet out and back in with
    overlapping windows and lifted both on the step's arc at once: the character hopped 4 to 6.6 cm off the floor
    for about 0.2 s while it squatted;
  - never both feet in the air: a lift that has both feet over `AIR_M` (1 cm) up on a common frame is dropped, steps
    keeping theirs first, then the earlier lift (`lift_dropped`: that foot fades along the floor). The report's `air`
    checks the result on the character's lowest vertex (a kneeling knee holds it as well as a sole): the frames where
    the clip had it within 1 cm of the floor and the edit has not (`airborne_frames`), and how much higher it is than
    in the clip (`hop_cm_max`);
  - the floor: the correction is the touching frame's, so a foot that settles after it would sink (Raise_In's toes
    went 1.7 cm into the floor); no edited Foot or Toe head goes lower than both its own height before the edit and
    the idle's standing height (the foot is raised: `floor.raised_mm_max`), and a step lifts off that floor. The
    report's `floor` measures what is left: how far a foot sinks below it, and how far the edit slides a foot the clip
    keeps still (under 5 mm a frame) while it stands (within 0.5 cm of the idle's standing height);
  - the Body rises by the idle's lift times the feet's mean weight, cut where a leg would not reach (`REACH` 0.999),
    and goes down up to `BODY_DOWN` (2 cm) where a leg would not reach even unlifted (`body_down_mm_max`; round 3:
    the men's Pickup_Package starts 1.4 cm higher than the idle, and its right foot was pulled 3.9 mm off the
    idle's);
  - the legs are solved again: the knee towards the foot's forward at full weight and the clip's own knee at 0, the
    thigh's and the shin's roll matched to the idle's at the touching frame (`leg_twist_deg`; UAL's turned-out right
    thigh would twist at the crossfade otherwise), and in a deep bend the knee swings out (0 at `knees_out_from_deg`
    of knee bend, `knees_out_deg` at `knees_out_full_deg`: the narrow stance crouched knock-kneed).

  The pure part is `anim_edit_math.idle_end_weights` and `end_mix` (a clip whose both ends meet the idle moves from
  the start's numbers to the end's along the clip). A loop is refused. With `match = "set"` the clip is marked
  `info["placed_by"]`: the set does not recentre it (below), and any later op but `reverse` and `retime`
  (`KEEP_PLACE`) clears the mark. Only the feet, the Body's lift and the fingers
  are matched at the touching frame: the head and the arms keep the clip's own pose plus the idle's change, so the
  game's crossfade still moves them (Jump_Land's left upper arm ends 68 degrees from the idle's).
- **In the set** (`mvp.toml`): Idle_Loop and Talk_Upper_Loop take `foot_turn`, `stance`, `shoulders`, `head_level`,
  `hands_relax` (the talk with `cap = 1.5`) and `thumb_in` (the talk with the idle's turn: `from_clip`); the women's
  idle then a second `arm_offset`, found by `auto` on the open hands (they are longer than fists: 2.9 cm in the thighs
  to 0 at 4.16 degrees; 0 on the men and on both bodies' talk) and pinned. The crouch loops (art #70) take the open
  hands and the idle's thumb turn only (no stance, foot turn or head level on a crouch); their hands go into the
  thighs from in front or behind, so their `arm_offset` swings the arms (`axis = "swing"`, found by one grid): the
  women's crouch idle forward 20 degrees; the crouch walk back 35 on both bodies, then the women's arms out 12 by a
  second, women-only `arm_offset` (art #69's grid). The eight one-shots that start or end in the idle pose end with
  `idle_ends`; Pickup_Package with `idle_ends {at = "both", upper = false}` (both ends meet the idle's legs: the carry
  plays over the idle; both feet only shuffle between them, so they are held), which Putdown_Package, its reverse,
  carries; Getup_Back with `match = "root"`. Putdown_One is made from its source with the pickup's steps reversed, not
  `from = "Pickup_One"`, which would blend the idle into it twice. Carry_Upper_Loop and Push_Upper_Loop are left
  alone: they play over the edited idle (art #65 gives the carry nearly straight fingers by `hands_relax`, for its
  side grip).

### The pure and the Blender side

| `anim_edit_math.py` (stdlib) | `anim_edit.py` (Blender) |
|---|---|
| `OPS`, `check_steps`, `params`; time maps (`trim_times`, `retime_count`, `retime_times`, `split_index`, `catmull_rom`, `neighbours`); quaternions (`q_mul`, `q_conj`, `q_slerp`, `q_hemi`, `q_axis_angle`, `q_rotate`); `best_cycle`, `central_diff`, `close_vectors`, `close_quats`; `linear_drift`, `moving_average`, `path_offsets`, `moving_speed`; `lsq_direction`, `yaw_of`, `signed_angle_2d`, `facing_yaw`, `unwrap`, `circular_mean`, `turn_correction`; `contact_mask`, `contact_windows`, `contact_velocities`, `ground_velocity`, `natural_cadence`, `stride_rate`, `stride_scale`, `stride_fit`, `scale_offset`, `plant`; `two_bone_ik`; `floor_profile`; `search_angle`, `secant`; the side grip (art #65): `palm_normal`, `grip_goal`, `roll_angle`, `grip_weights`, `spread`, `end_weights` (`upper_match`'s fade); `mirror_name`, `mirror_pairs`, `mirror_correction`, `mirror_pose` (4x4 lists); the relaxed idle (art #49): `RELAX_OPS`, `FINGER_SEGMENTS`, `curl_errors`, `from_clips` (the clips a list of steps reads: every `from_clip` and `base_clip`), `smoothstep`, `finger_curls`, `curl_goal`, `stance_targets`, `stance_lift`, `pitch_of`, `head_fix`, `yaw_out`, `knees_out`, `reach_lift`, `planted_until`, `AIR_M`, `KEEP_PLACE`, `idle_end_weights`, `end_mix` | `Frames`, `Target`, `apply`, `EditError`, `OPS` (op name to function); Root and Body moves in world space; the leg IK as rotations; the mirror with mathutils; the posed-mesh measures (the lowest vertex through `anim_metrics.world_points`, the hands through `anim_metrics.Measure`'s sets and surfaces); the relaxed idle's ops on an `_Pose` in world space, `feet_numbers`; the side grip's measures (art #65): `hands_at` (the grip on one frame as the game plays it) and `grip_ends` (`hands_at` on a built clip's first and last frames, against a reference pose: `anim_set.grip_check`) |

### The API

```python
import anim_edit as ae

target = ae.Target(char)          # char: rc.load_glb(...) of the donor, after rc.add_toes(char)
frames = ae.Frames.from_action(action, target.rig, loop=True)   # or Frames.from_sampler(sampler, rig, loop)
out = ae.apply(frames, steps, target, "women")   # steps: a list of {op = ..., ...}; raises ae.EditError
out.info["steps"]                 # one report per step, {"op": ..., ...}; skipped steps {"op", "skipped": "body men"}
out.to_action(char["arm"], "Idle_Loop")
target.upper_bones()              # the upper-body layer's bones: Torso and every bone below it
target.clips = {"Idle_Loop": idle}   # the clips a step's from_clip reads (anim_set.build_clips sets it)
ae.feet_numbers(frames)           # the feet's yaw out, the ankle gap, the stance (art #49)
```

`Target` exposes `rig`, `legs` (the three bones of each leg), `upper = "Torso"`, `clips` (the clips built so far,
which a step's `from_clip` reads; `anim_set.build_clips` sets it), `measure` (an
`anim_metrics.Measure` built on first use, in the rest pose), `pose(basis)` and `lowest()`. The edits leave the
target in its rest pose.

An example of a set's clip entries:

```toml
[[clips]]
name = "Jog_Fwd_Loop"
source = "ual:Jog_Fwd_Loop"
loop = true
edits = [ { op = "stride", speed_m_s = 4.5, cadence = 2.8 } ]

[[clips]]
name = "Idle_Loop"
source = "ual:Idle_Loop"
loop = true
edits = [ { op = "arm_offset", abduct_deg = 2.7, body = "women" } ]   # art #33's, before the relaxed idle (#49)

[[clips]]
name = "Knockdown"
source = "ual:Death01"
edits = [ { op = "floor", mode = "lift", from_s = 1.2 }, { op = "trim", start_s = 0.0, end_s = 2.0 },
          { op = "retime", seconds = 1.35 } ]
```

### Measured on the real clips

Background Blender, the pack originals with the toe bones and UAL1 retargeted with `ual_um.toml`; review renders in
`raw:review/stage1/33/tools/` (outside git).

| Clip and steps | Result |
|---|---|
| men, UAL Death01: floor lift from 1.2 s | lowest -4.86 cm (the impact at 1.2 s) to 0.0; the lying frames lie 2.2 cm above the floor already (a lift does not lower them) |
| men, UAL Fixing_Kneeling: floor hips | lowest without the shoes -4.65 to -0.64 cm (the knee rests on the floor); the kneeling foot's toes reach -6.95 cm, which a lift of the hips cannot move |
| men, Fixing_Kneeling: cycle 1.0-2.0 s within 1.0-4.2 | fails: the best cut (2.9-3.9 s) has a raw seam of 26.8 degrees in the right forearm; the work is not periodic |
| women, UAL Idle_Loop: arm_offset auto | 2.66 degrees: hands in the thighs 1.32 cm (42 frames) to 0 |
| women, UAL Push_Loop: hand_spacing min_gap_cm 1.0 | 4.3 degrees: the hands 6.09 cm inside each other to a 1.28 cm gap |
| men, UAL Push_Loop: hand_spacing min_gap_cm 1.0 | 0 degrees: a 1.08 cm gap already |
| women, UAL Push_Loop: lean 30 | the spine's tilt 46.5 to 76.5 degrees, the head 8.2 cm forward, the feet still; layered over the idle the hands come down from over the head to in front of the face |
| men, pack Punch_Right: mirror | a left punch; rest error 0.0002 mm |
| men, UAL Jump_Start: trim 0.03-0.40, retime 0.25 | 8 frames, 0.267 s: a retime rounds to whole frames (rate 1.375 for 1.467) |
| men / women, UAL Idle_Loop: the MVP's relaxed steps (art #49) | the right foot 43.66 to 3.66 degrees out (the left -5.68 kept); the ankles 47.7 to 27.5 / 45.4 to 22.9 cm apart, the stagger 45.7 to 5.6 / 46.5 to 4.5 cm, the Body 2.94 / 3.07 cm up; the head's pitch -14.9..-10.5 to -2.2..+2.3; Middle2 78 to 20 degrees, the thumb turned 22.3 / 22.0; every ankle within 0.003 mm of its foot; the loop closed, no pop |
| women, the relaxed idle: arm_offset auto (art #49) | 4.16 degrees: the open hands 2.9 cm in the thighs (77 frames) to 0; the men and both talks 0 |
| the ten clips that meet the idle: idle_ends (art #49) | both feet 0.000 cm and 0.00 degrees from the idle's first frame in the game's frame (armature space), Root at the idle's, the toes at its bend, at the thirteen set-matched touching ends (round 3; round 2's Root-relative match left them 0.2 to 11.8 cm and up to 19.8 degrees off in the saved set), Getup_Back relative to its Root (its whole body 17 / 27 cm off); the fingers at its curl (but on the package clips: `upper = false`); the package clips' feet held at the idle's (round 2 lifted both 4 to 6.6 cm at once), no airborne frame on a set-matched clip; ankle gaps 0.002 to 0.011 mm on every frame it weighs (Jump_Start's 8 mm before), Knockdown's 2.9 mm on the frames it leaves alone (art #33's resampling, 5.7 mm before); no foot below its floor, none slid where the clip keeps it still (round 2: round 1 slid Getup_Back's left foot 21 to 23 cm and sank Raise_In's toes 1.7 cm) |

### Gotchas of the edits

- **Auto searches are slow.** `arm_offset` and `hand_spacing` with `auto` pose the meshes and build BVH trees per
  frame and trial angle (20 to 90 s a clip). Pin the found angle in the settings once the review accepts it.
- **A retime rounds to whole frames.** Short clips feel it most (Jump_Start: 0.267 s for 0.25).
- **`retime` by speed after `stride`** uses the stride's speed (the clip then plays at that speed at 1.0x).
- **The pack's 24 fps keys** land between the 30 fps frames: `Frames.from_sampler` reads a pack clip as samples on
  the 30 fps grid, not as its keys.

## Animation sets (art #33)

An animation set is the list of clips one GLB carries for the game, each built from a source clip by the clip edits
above, so every clip is reproducible from its settings by one command. The MVP set is
`tools/blender/anim_sets/mvp.toml`; its per-need table, measures and open points are in
[`research/2026-10-06-animation-mvp.md`](research/2026-10-06-animation-mvp.md).

`tools/run.py anim-set [--set mvp] [--body men|women|both] [--clips A,B|all] [--out DIR] [--no-export] [--no-godot]`
builds each body type in its own background Blender run (`tools/blender/anim_set.py`), then exports and checks it.
Output goes to `<raw>/anim-sets/<set>/<body>/` (outside git): `anim_mvp_<body>.blend`, `.glb`, `.export.json`,
glTF-Validator's `report.json`, `build_report.json`, `build.md` and `godot-check/report.json`. A run with `--clips`
builds those clips (and the clips they are made `from`) and checks them, without saving or exporting; its
`build_report.json` and `build.md` go to `<out>/<body>/partial/`, so the full build's reports stay with its `.blend`.

### The settings

A set names itself in the review settings' `[sets]` (`mvp = "anim_sets/mvp.toml"`). Its keys are `title`, `fps` (30,
the edits' grid), `stem` (the file names) and `upper` (the upper-body layer's top bone, `Torso`), then one
`[[clips]]` table per clip:

| Key | Meaning |
|---|---|
| `name` | the action and glTF animation name, `[A-Za-z0-9_]+`, unique; it ends in `_Loop` exactly when the clip loops |
| `source` or `from` | a clip key (`pack:Sword_Slash`, `ual:Jog_Fwd_Loop`, `ual2:Walk_Carry_Loop`, `tm:strafe-left`) or an earlier clip of the set as it stands after its edits |
| `loop` | the clip loops: its source loops or a `cycle` step closes it (the build refuses anything else) |
| `edits` | the steps of "Clip edits", in order; a step with `body = "men"` or `"women"` runs on that body type only; a step's `from_clip` (art #49) names an earlier clip of the set, which is built first (`anim_set_cfg.closure`) |
| `needs` | the game's needs the clip serves: `need` (text), `no` (its number in the needs list), `layer` (`full` or `upper`), `speed_m_s` and `rate` (the game plays the clip at `rate` when moving at `speed_m_s`) |
| `speed_m_s` | the clip's ground speed at rate 1.0; the review's treadmill and the game divide their speed by it |
| `export` | `false` for a review candidate that is built, but not written to the GLB: `Jog_Bwd_TTM_Loop`, and art #66's re-rolls `Jog_Bwd_R2_Loop`, `Strafe_Left_R2_Loop`, `Crawl_Start_R2` and `Crawl_R2_Loop` beside the stopgaps they may replace once the engineer has judged them (the `anim-review` pairs `a7_*`) |
| `place_after` | an earlier clip of the set that this clip plays after (art #49): instead of being recentred, the clip is moved along the floor so its first frame's feet stand where that clip's last frame has them (the mean of the two Foot heads' offsets, in the set's frame); the report's `placed_by` is `place_after` and `place_after` gives the clip, `moved_m` and the seam left (`feet_seam_cm`: each foot and the mean offset). That clip is built first (`anim_set_cfg.closure`) |
| `note` | free text |

`tools/blender/anim_set_cfg.py` reads and checks a set (pure Python: the runner, the tests and Blender share it): the
names and the loop suffix, one `source` (a single clip of a known source) or an earlier `from`, an earlier
`place_after`, the edits through `anim_edit_math.check_steps`, a need's layer, rate and body, and that a need's speed
is the clip's speed times its rate (within 1 %). Angles found by an `auto` search are pinned in the settings, so a
build is quick and reproducible.

A set's sources are taken **with their travel**: a library's `in_place` list is for the review's lanes only, since
`heading {travel = ...}` and `cycle` read the travel.

### The build and the save

`anim_set.build_clips(set_cfg, char, names, body, resolve)` builds clips on a donor (the pack original with the toe
bones, as the review sets it up): each source is resolved by `resolve` (the review's `clips_for`, retargeting a library
with its map), sampled into `Frames`, run through `anim_edit.apply` and reported (`info["report"]`: frames, seconds,
loop, needs, speed, every step's report, the travel and heading left, the lowest vertex, and since art #49 the `feet`:
`anim_edit.feet_numbers`, each foot's yaw out against the aim relative to the rest pose at the first frame and its range
(`rest_yaw_out_deg`: the rest pose's own Foot-to-Toe line, 15.94 degrees out on the men's right foot and 10.72 on the
women's; the line's yaw against the aim is their sum),
the largest gap between a shin's end and its IK foot, and the ankles' width and stagger at the first frame). Two rules
hold for every clip:

- **A looping source is closed first.** UAL's loops are open cycles (their first pose comes round one frame after
  their last key; the men's Idle_Loop ends 4 mm from its start at the hands, the Jog 0.78 degrees): a source whose
  last frame is further than 0.5 mm or 0.5 degrees from its first gets its first frame appended when that seam is at
  least half a median frame step, else its last frame becomes its first (the Sprint's 4.6 mm against 191 mm steps).
  Every loop of the set then exports closed (seam 0), and Godot plays it without a hitch.
- **A clip stands over the origin**, where the game's body is: a loop's Body is centred on it over the cycle, a
  one-shot's first frame stands on it (`recentred_m`). A cycle cut from a travelling clip otherwise plays where it was
  cut (the strafe 4.9 m to the left, the crawl 1 m ahead). A one-shot that ends elsewhere (Knockdown: 0.48 m) leaves
  that offset to the game, which moves the body when the clip ends. A clip that `idle_ends` placed in the idle's frame
  (`match = "set"`: `placed_by` in its report, carried to a clip made `from` it) is left where it is: recentring it
  moved its feet 1.5 to 7.3 cm off the idle's again (art #49, round 3). A clip that plays between such clips is
  placed by its neighbour with `place_after` instead: Raise_Work_Loop, cut from the same kneeling source, stands where
  Raise_In leaves the feet (Raise_In and Raise_Out hold them at the idle's), and so meets Raise_Out too.

The command bakes the
exported clips under their own names and saves the donor as a character the export accepts: one armature, its meshes
parented to it with one Armature modifier each, no RootNode, no empty and no assigned action, every transform applied
(the location keys times the armature's world scale of 100, as `um/blendfile.save_character` does; a few poses agree
before and after within 0.1 mm), a scene at 30 fps over the longest clip.

### The checks

| Where | Check |
|---|---|
| the build | every clip built, as long as its frames over 30; every loop closed and in place (its Body travels under 5 cm from its first frame to its last) |
| the export (`export`'s checks, then the set's) | every exported clip an action of its frames, nothing else, 30 fps; every loop's last frame its first within 0.5 mm and 0.5 degrees (`export.json` seams) |
| Godot (`godot-check`, then the set's) | every animation under the name Godot gives it, as long as built, looping (LINEAR) exactly when the set says so; 64 bones; every track resolves |
| the grip (reported per clip, `grip_ends`; judged in the review) | a one-shot with a `side_grip` (its own or from the clip it is made `from`): on its exported first and last frames, after every edit, the hands' closest gap, their depth in each other and in the torso, each palm's angle over the horizontal and off the line to the other wrist, each wrist's height and forward (`anim_edit.grip_ends`); with an `upper_match` and an `idle_ends`, also the pose the game crossfades to there (`ref`: the idle's first frame with the matched clip's upper layer over it) and each end's wrists' distance from it (`to_ref_cm`) |
| warnings (printed, judged in the review) | a `stride` fit of `warn` or `fail`, an `auto` search that found no angle, a lowest vertex under -1.2 cm, a locomotion loop (one with a `speed_m_s`) whose hips or head face more than 5 degrees off the aim on average (`facing_mean_deg`, `head_facing_mean_deg`: the strafe's 19.5 and -15.9), a loop whose step from its last distinct frame onto its first is over 1.5 median frame steps (`seam_step_ratio`; the export's seam is 0 by construction, so it says nothing about a pop), a bone that snaps in one frame between two held poses (`pop_count`, `pops`: a rotation of at least 20 degrees in one frame step whose neighbouring steps are both under a third of it, `anim_math.one_frame_pops`; a loop's steps wrap round). The floor clamp's flick of Jump_Air_Loop's right foot (53 degrees and back, art #33) is what it catches; `retarget` reports the same per clip and warns |

**Godot's loop names.** Godot's scene importer gives an animation whose name ends in `_Loop` (also `-loop`, `_cycle`,
`-cycle`, any case) the loop mode LINEAR and drops the suffix: the game sees `Idle`, `Jog_Fwd`, `Strafe_Left`,
`Crawl`, `Raise_Work` and so on, and one-shots keep their names. `godot-check` and `frames` expect these names
(`_godot.godot_name`), fail when a clip named as a loop imports playing once, and import a GLB at the fps its
`.export.json` records (30 for a set; Godot would resample a set imported at the pack's 24).

**Upper-body layers** (`layer = "upper"`: the push, the talk, the carry, the knife) export all 64 bones; the game masks
them with the set's bone filter, `Torso` and every bone below it (`build_report.json` lists them as `upper_bones`). A
layer keeps nothing of its source's hips: a source that leans with the hips (the push) needs a `lean` on `Torso`, and
its full-body clip then bends further than the source (the push 76 degrees), so it is played as a layer only. Judge a
layer in the review over the bases the game puts under it (`Idle_Loop|Push_Upper_Loop`, `Jog_Fwd_Loop|...`), not alone.

### In the review

`anim-review` plays a set's clips as `mvp:<clip>`, built in the review's own Blender process from the same settings
(`anim_review.clips_for` calls `anim_set.build_clips`), so a review shows exactly what the command builds; `--sources
mvp` selects them. On the treadmill (`rates`) a set's clip plays at the row's speed over its `speed_m_s`, as the game
plays it, with the feet's measured ground speed reported beside it; a row's `direction` (`forward`, `back`, `left`,
`right`) moves the stripes along the clip's ground axis.

### The alien's clip edits (art #196, A1)

The shared alien body carries UAL1's clips copied key for key onto the contract skeleton (`alien_body.py`, step 7),
not the MVP set's: the edits above work on the Ultimate Modular rig (`Root`, `Body`, the IK feet) and do not apply.
`tools/blender/alien_clip_edit.py` does the few the bare alien needs on its own actions, by name, from
`tools/blender/anim_sets/alien.toml` (`[defaults]` and `[clips.<name>]`; not an anim-set file, and `mvp.toml` is
untouched); `alien_char_build.py --clip-edits` runs it before the export:

| key | What it does |
|---|---|
| `finger_cap_deg`, `thumb_cap_deg` | every finger joint's turn from its straight rest capped to the angle, its axis kept (`hands_relax` with `cap`): fists open to a relaxed hand, small gestures stay |
| `abduct_deg` | each upper arm turned out about the body's forward axis in its rest frame, one angle on every key (`arm_offset`): the hands off a body thinner than the clip's |
| `swing_deg` | the same about the left-right axis, + the hands forward |
| `head_up_deg` (A2) | Neck and Head turned half each about the left-right axis, + the face up |
| `lean_deg` (A2) | Spine turned about the left-right axis, + the trunk forward |
| `chest_up_deg` (A3) | Spine and Chest turned half each about the left-right axis, + the chest up (the trunk more upright) |
| `repeat` (A3) | a loop's cycle played this many times in one longer loop (every key copied, shifted by the cycle) |
| `sway_cm`, `sway_counter_deg` (A3) | the Hips moved sideways by up to this, once to each side over the loop (a sine: the seam clean), the legs solved per frame as for `hips_up_cm`; the Spine rolled against it, the Head back by half |
| `cut_straight_deg`, `cut_gap` (A2) | a one-shot's frames after the first on which both knees bend under the angle dropped, the later keys moved so `cut_gap` frames join the two sides (Jump_Start's in-place push-off, which read as a snap to a straight stand between the crouch and the tuck) |
| `hips_up_cm`, `knees_in_deg` (A2) | the Hips raised and both legs solved again on every frame (`two_bone`: the feet kept in the world, the knee in the plane of the clip's own, turned `knees_in_deg` toward the middle) |
| `floor` | `true`: the Hips lifted on the frames whose skin goes under the floor (`floor` `lift`: running max over +-`floor_reach` frames, default 2, smoothed over as many; a `*_Loop` clip wraps around its seam, A2; `floor_reach` 0, A3: each frame its own need, the Hips keyed on every frame; B1, art #196: `alien.toml`'s `[defaults]` set 0 for every lifted clip, since reach 2 carried the leg fit's 3 cm heel-strike sink into the planted frames and floated her Walk up to 21 mm, a hop at each step; the report's `floated_frames` counts the frames the lift put over 5 mm that were on the floor, `lowest_before_mm` / `lowest_after_mm` give the series); a clip still under -0.5 cm after it fails the build (A2). With the sneakers, `clothes_dress.py --sole-floor alien` (the default) puts every ground clip (these and every clip the toml does not list: the loco set's derived actions) on the floor with the soles measured, at the foot: each foot under the floor raised by its own need and its leg solved again, the Hips untouched (`alien_clip_edit.sole_floor`, B1b; `docs/clothes.md`): the sole dips up to 19 mm under the floor at heel strike, and B1's Hips lift by that need jerked the Hips 18.6 mm in a frame. `floor_feet = true` (B1b, `[defaults]`) sends the bare build's own `floor` through the same pass at the foot (`alien_clip_edit.feet_floor`: each foot raised by its own need, the leg solved again, the Hips untouched; what a straight leg cannot reach goes to the Hips at reach 0, `hips_fallback_cm`), so the bare heel-strike sink no longer jerks the Hips (the chameleon's Walk step 18.6 -> 9.7 mm). B1e: in a clip with no flight (`alien_contact.can_fly` false: the walk, the crouches, the idles, the talk) a frame with both feet up has both feet lowered by the lower foot's height over 0.5 mm, the legs solved again and the Hips untouched (`alien_clip_edit.foot_plant`; one amount for both feet, so the paths stay smooth where the lower foot changes sides): the crouch's trailing foot rose onto its toe before the front foot landed, both shoes 10-23 mm up for about 10 frames on both characters; now 0 floated frames, the shoes' highest low 1.4 mm (hers) and 0.5 mm (his), the Hips step unchanged. The report has `max_lower_cm` and `floated_after`. B1i (the hop review): the crouch run can fly (`alien_contact.FLIGHT`: its source leaves the ground, his shoes 19 mm up), so it is no longer lowered (B1e landed its trailing toe while it still moved: a skid, and her Foot 1 cm short of its place). B1i also lowered a frame only where its lower foot moved as a planted one, within 2 mm a frame of the clip's stance motion (`plant_standing`: the median velocity of the standing feet's contact patches; the clips play in place, so a planted foot travels back at the ground speed); that guard kept 17 Crouch_Fwd frames per character up, the float back (hers 22.6 mm). B1j tracks each patch by its own points (`patch_velocity`: the patch's points followed to the frames around it; the patch centre slid along the toe as the foot rolled), and the crouch's lower foot still moves 30-53 mm a frame off the ground on its lift-off frames: it hovers 9-19 mm through its stance and lifts off while the other foot is still up, so the guard would keep 11 of 22 frames up. B1j drops the guard (`PLANT_GUARD = False`): the crouch lands as in B1e, and the report measures what it costs, `plant_slide_mm` (the lowered foot's largest slide a frame) and `plant_moving_frames` (the lowered frames over 2 mm). B1k plants each foot on its own instead (`alien_clip_edit.plant_offsets`; the guard and B1e's one amount for both feet, `foot_plant`, are gone): its stance runs are the frames it is the lower foot or within 1.5 mm of the floor (`foot_stances`); in a run with a frame over 0.5 mm its sole is put on the floor on every frame, and on each step touching a lowered frame its drift off the ground's travel (`patch_steps`, the patch's own points, less `ground_step`, the lower foot's median step) is held back from the run's first frame on, so the foot lands where the clip puts it and stands still through its lift-off until the other foot is down; the offset eases in over 2 frames before the landing and out over 2 after the lift-off (a raised cosine), never under the floor; the other foot keeps its height and place. A foot already on the floor is left as the clip has it. A run whose hold would pass 15 cm (`PLANT_HOLD_MAX_M`) is the clip's own slide, not a lift-off's drag: it is lowered without a hold and listed in `plant_unheld_runs` (the `Crouch_Fwd__ual` crouch slides 13 cm a frame on the floor; holding it put her Foot 17 cm out of reach). B1l (the review of B1k): a 2-frame ease-out made his 108 mm hold catch up 27, 54 and 27 mm a frame just after the lift-off, a few mm over the floor, where `plant_slide_mm` does not look; the hold (x, y) now eases out over as many frames as keep each step within 10 mm (`PLANT_EASE_STEP_M`, `ease_weights`: a raised cosine, or a straight ramp where the swing to the next landing is too short for one), never past the foot's next landing, and the height still over 2 frames; the report's `plant_ease_step_mm` is the largest step an ease adds to a swing frame (the crouch: 54 -> 9.8 mm his, 35.7 -> 9.8 mm hers, a ramp over the 10-frame swing). A foot's stance runs 4 frames apart or less are one (`merge_runs`): the hold carries across the gap (B1k dropped a 1-frame gap's hold to 0 and back, a 90 mm pop), the gap's frames at their own height. On a run's frames already on the floor after its last lowered frame the hold stays constant (by design): there the foot moves as the clip has it, the clip's own slide on the floor (`floor_slide_mm`). The report: `plant_hold_mm`, `plant_frames`, `plant_slide_mm` and `plant_moving_frames` (measured after the pass on the lowered feet standing on the floor) and `floor_slide_mm` (every foot on the floor, the clip's own: the Walk's heel strike slides 30 to 54 mm a frame in the source, not touched). A re-solved Foot over 0.5 cm from its place (`ANKLE_MISS_FAIL_CM`) and a clip still under -0.5 cm fail the build in this branch too. `"ground"` (A3): a one-shot whose tuck leaves the floor in place: the frames up to the push-off (the cut's last kept frame) lifted onto the floor, the lift faded out over `cut_gap` frames, the tuck not lifted; those ground frames fail the build under -0.5 cm. `false`: neither lifted nor checked (Jump_Air, held off the floor by the game) |

Measured (A1, `<raw>/research/2026-10-22-roster/design/pilot3d/anim_bare/a1/`): the finger curl 87 to 22 degrees
at most; the lowest vertex -1.3 (stand), -8.2 (crouch), -12.7 (jump take-off) to 0.0 cm; the head and the springs
judged in `after/judgement.md`. The pure maths is tested in `tools/tests/test_alien_clip_edit.py`.

A2 (`anim_bare/a2/`): only the clips listed under `[clips.*]` are edited (`[defaults]` applies to those alone; an
unlisted clip stays as the body carries it). Per clip hands: Idle and Talk 22 degrees (relaxed), Walk 30, Jog and
Sprint 50 with the thumb at 30 (loose fists); the run arms out 6 (Walk 8) so the hands stop crossing the groin;
Sprint leans 4. UAL1 and UAL2 hold no other crouch or sneak, so the crouch loops are edited: the hips up 10 cm with
the feet kept, the knees in 12, the arms swung forward 12 and in to 2, the face up 10. Jump_Start drops its push-off
frames (the knees bend 113 degrees crouched, 43-69 at the push-off, 86 and more in the tuck: `cut_straight_deg` 75) and has no floor
lift (its sink is the in-place tuck; the lift floated its crouch 10 cm). The leg solve replaces the legs' rotation
channels whole, one linear key per frame: inserting keys beside the clip's own left 3 frames of 4 unsolved (the feet
rose with the hips). The axolotl's gills on the body: `alien_char_build.py` raises their `zeta` to 0.55 in
`<head>_char_lively.json` (`GILL_ZETA_ON_BODY`; 0.28 jittered 205-267 deg/s in the jog and sprint); the busts' lively.json
is untouched.

A3 (`anim_bare/a3/`): the minors of PR #315's review. The legs' solve reads the UpperLeg's parent from the rig and
measures the feet on the re-evaluated rig afterwards (`ankle_miss_max_cm`, 0.0 on every solved clip; over 0.5 cm
fails the build). `floor = false` on Jump_Start had hidden its ground crouch 5.63 cm under the floor; `"ground"`
puts it on the floor (0.0) and leaves the tuck where the game lifts it (-12.6 cm in place, as A2). The crouch pair was
rebuilt from a variant grid (`tools/blender/alien_clip_grid.py`, `a3/crouch_grid/grid.json` and `grid.png`: 18
variants on top of A2's edit, measured): hips 22 cm, chest up 20, knees in 20, head up 10, `floor_reach` 0 (the face
64 cm over the front knee against A2's 40, the trunk 35-36 degrees from vertical against 48-50; the planted foot's
float 2.95 cm to 0.0). Idle: UAL's 2.5 s cycle three times (7.5 s), a 3 cm weight shift with a 2 degree spine
counter. Jump_Start's crouch goes into the tuck over 4 frames (`cut_gap` 6 leaves the 4-frame gap whole; A2 3).
Jump_Air's arms 30 degrees down and 8 forward, its fingers 30; Talk_Upper's hands 34 (thumb 24), arms out 5.

### The alien locomotion clip tool (art #196, option A)
`alien_stride.py`, `alien_ttm.py` and `alien_loco.py` run Blender or Godot for minutes: an agent starts each with
`run_in_background` and a log, and checks it with `tools/run.sh wait <log>` (the 180 s rule, `docs/agents.md`).

The stride warp above (`stride_warp`) works on the UM rig only (Root, Body, the IK feet). The alien's clips live on the
contract skeleton (Root, Hips, LeftUpperLeg ... LeftToes), so its own tool is `tools/blender/alien_stride_math.py` (pure,
no bpy: FK from the rest matrices and the pose basis, the edits, the measures) and `tools/blender/alien_stride.py`
(Blender: reads an action into the plain clip form, writes an edit back as a new action keyed on every frame, the
proof sheet). It reuses `anim_edit_math` (contact masks and windows, ground velocity, cadence, retime count and
Catmull-Rom sampling, `stride_scale`, `scale_offset`, the loop closing, `mirror_correction`/`mirror_pose`) and
`alien_clip_edit.two_bone`. The ops:
- `measure(skel, clip)`: the ground velocity under the planted feet, v0 (the body's speed over the ground, m/s), the
  contact windows per foot (the ankle or the toes within 2 cm of their lowest **and** moving with the ground within
  max(0.35 m/s, 35 %), breaks of up to 2 frames filled), c0 (steps/s), the stride (m/step), the feet's slide
  (`foot_slide_mm`: over each contact the point on the ground, the ankle and then the toes through the roll,
  against the ground's line) and the seam; `game_table` puts the game's speeds against them.
- `stride(skel, clip, cadence= | rate=, speed= | scale=)`: retimed to a cadence (whole frames on the clip's grid), the
  stride scaled (the hips' travel and each ankle's offset from the hips along the travel axis; `speed` picks the
  scale that covers it at rate 1), each contact re-planted (`plant_foot`: the point on the ground moves with the
  ground, handed from the ankle to the toes as the foot rolls), the legs solved again with `two_bone`, the foot keeping
  its world rotation. Bound: a planted foot slides at most `SLIDE_BOUND_MM` = 5 mm over a contact.
- `cycle(skel, clip, foot=)`: a `*_Loop` keeps its length, its seam spread over it (`close_quats`, `close_vectors`),
  started on the foot's first contact frame; any other clip is cut at the best pair (best_cycle's cost) whose start is
  a contact of that foot, the seam reported in degrees before closing.
- `arm_swing(clip, k)`: UpperArm, LowerArm and Hand per side slerped toward their own mean over the loop (1 unchanged,
  0 still).
- `mirror(skel, clip)`: the contract's side rule (`Left<X>` <-> `Right<X>`, a clip name's Left and Right swapped), each
  bone from its partner reflected on X; twice gives the clip back.

`$PYTHON_BIN tools/blender/alien_stride.py --blend <char.blend>... --out <dir> [--measure] [--proof] [--check]`: the
measures (`measure.json`), the proof (Jog_Fwd_Loop at the footstep beat and 4.5 m/s, arm swing 0.75, `proof.json`,
`proof_sheet.png`) and the FK and read-back check (`check.json`, `tools/tests/test_alien_stride_blender.py`).

Measured on the R2b build (2026-10-26; both characters carry the same clips; 24 fps, as the GLB plays them):

| Clip | v0 m/s | c0 steps/s | stride m | cycle s | foot slide mm (L/R) |
|---|---|---|---|---|---|
| Idle_Loop | 0.0001 | - (planted) | - | 7.5 | drift 2.0/2.6 |
| Walk_Loop | 0.834 | 1.50 | 0.556 | 1.333 | 20/24 |
| Jog_Fwd_Loop | 5.147 | 2.18 | 2.359 | 0.917 (seam 3.1 deg) | 17/20 |
| Sprint_Fwd_Loop | 7.801 | 3.00 | 2.600 | 0.667 | 11/0 |
| Crouch_Fwd_Loop | 0.639 | 1.00 | 0.639 | 2.0 | 66/33 |

At the game's speeds (rate = speed / v0, the cadence seen = rate x c0): walk 4.5 on Jog_Fwd rate 0.87, 1.91 steps/s
(0.52 s a step, the footstep beat 0.45); sprint 7.0 rate 0.90, 2.69 (0.37 s, beat 0.32); crouch 2.0 rate 3.13, 3.13;
crouch run 2.8 rate 4.39 (over the game's 4.0 clamp), 4.39; the sneak 2.0 on Jog_Fwd rate 0.39, 0.85 steps/s. The
proof: Jog_Fwd's seam closed (3.1 deg), started on the left contact, cadence 2.22 asked (22 frames stay 22 at 24 fps:
21 would be 2.29), stride x 0.878, v0 5.13 -> 4.50 (rate 1.00 at 4.5 m/s), foot slide 17/19 -> 0/0 mm, arms' swing
x 0.75.

#### Text to motion onto the alien (option A step 2)
`tools/blender/retarget_maps/smpl_contract.toml` maps Meshy text to motion's SMPL-H rig onto the contract skeleton
(Pelvis -> Hips, Spine1..3 -> Spine, Chest, UpperChest, the phalanges 1:1 with Pinky -> Little, L_Foot -> LeftToes;
Root and the face bones at rest). **No FK leg mode was needed**: `retarget_core.Retargeter`'s leg solve works on
armature-space poses and turns them back into each bone's basis under its own parent, so the contract's FK feet only
need `[follow]` to name the foot's own parent (the lower leg). Checked on the alien: the source rest gives the target
rest exactly (`rest_check` 0.001 mm, 0 deg), the ankles miss their goals by at most 16 mm over the ten clips.

`$PYTHON_BIN tools/blender/alien_ttm.py --blend <char.blend> --raw D:/prime-art-raw --out <dir> [--items a,b]
[--no-sheets]` bakes each FBX (`ITEMS`: the seven clips of `batches/2026-10-25-alien-locomotion-ttm.toml` and three
baseline rows of batches 5 and 6) at the character's fps as `CharacterArmature|TM_<item>`, cuts its loop
(`cycle`, bounds from the clip's own cadence: one cycle of two steps) as `CharacterArmature|TM_<item>_Loop`, mirrors
the best left strafe (and the best new one) into a right one, and writes `candidates.json` (per candidate v0, c0,
stride, the travel direction against the hips' mean facing, their yaw wobble, the cut's seam, foot slide, the floor,
the hands against the torso, the hips' height; faults and a ranking per slot by `alien_ttm_math.faults`), one
8-frame sheet per candidate (side view, strafes from the front, the camera following the hips), `overview.png` and
`<char>_ttm.blend`. Two corrections it makes, both measured in the report:
- the floor: the retarget scales the source by the hip height and the alien's ankles sit lower over its soles than the
  scaled source's, so its planted feet hovered 4-37 mm; each bake and each loop is lowered so its planted level (the
  10th percentile of each frame's lowest sole point) is the floor (`floor_fit`, `hover_before_fit_mm`);
- the loop closing (`alien_stride_math._close`) keeps the hips' travel in armature space: a Blender bone's Y axis
  runs along it, so the alien's Hips carry forward travel on their basis z; read as the floor's axes, a cut loop of a
  forward or backward run lost its travel (step 1's loops were in place, so its numbers stand).

### The alien's locomotion set (art #196, option A steps 3 and 4b)
`tools/blender/anim_sets/alien_loco.toml` is the set as data: per game clip (`avatar_clips.gd`'s names: `Jog_Fwd`,
`Sprint_Fwd`, `Jog_Bwd`, `Strafe_Left`, `Strafe_Right`, `Crouch_Fwd`, plus `Walk` and a new `Crouch_Run`) its source
(the build's UAL clip or a step 2 loop `TM_<item>_Loop`) or the clip it mirrors, the speeds its stride is fitted to
at rate 1.0, a retime to a frame count, the arm swing (`arm_swing`, or `arms_from` another made clip: its swing on a
pose blended toward its mean, for a clip whose hands clamp at the belt), `max_scale` (the stride scaled at most this
much, the rest of the speed in a higher cadence: `alien_loco_math.capped_rate`), `bend_min_deg` (a knee bend floor on
the swing frames: `stride` draws the ankle toward the hip, no locked knee at a kick) and the game speeds it is played
at; `[[grid]]` makes a clip's
variants (arm swing x frames) and picks the default by the numbers (`alien_loco_math.pick_default`: the cadence
nearest the game's footstep beat with the planted feet within 5 mm; ties to `default_arm_swing`). Every loop starts on
the left foot's contact. A clip's action is `CharacterArmature|<name>_Loop` (Godot imports it as `<name>`, looping;
a game clip replaces the build's action of that name); variants and alternatives are `<name>__<variant>`, a second
speed `__s<speed x 10>`. The strafes under the game's names are fitted to the side cap, 3.0 m/s (since step 4b), and
`Jog_Bwd` with the back diagonals to the back cap, 2.0 m/s (since F1, the engineer's pick of 2026-10-26; "F1" below),
with `Strafe_*__s45` and `Jog_Bwd__s25` beside them for review; the shuffle strafe is dropped (a squat and a split at both speeds). `alien_loco_math` also holds the game's footstep clock
(`footstep_interval`, `footstep_cadence.gd`'s), the rates at the game's speeds against its 0.25-4.0 clamp
(`play_rows`), the stride flag (scaled over 2x either way) and the reels' plan and timelines.

`$PYTHON_BIN tools/blender/alien_loco.py --raw D:/prime-art-raw [--chars chameleon,axolotl]` (about 2 min) opens each
R2b character, appends step 2's loops, makes the set (`_make`: cycle, in place, stride, arms, mirror; the cut in place
comes before the stride since step 4b, so the stride plants the feet in the frame its measure was made for), writes
the actions,
exports one GLB with `export_glb.py`'s textured options (no morph targets, as the character build), runs
glTF-Validator and writes `loco.json` (per clip the edits' reports, the numbers before and after, the rates) into
`<raw>/research/2026-10-22-roster/design/pilot3d/anim_bare/<out>/build/<char>/` (`[set] out`, `loco/f3` now), with
the build's support files
copied beside the GLB. Then `tools/run.sh godot-check <glb> --profile alien --strict-contract --textured`.
`--build DIR --out DIR` (T1, art #196) take another character build and output under `raw_base` for one run, the
set file unchanged (`alien_loco_math.with_paths`; a new build into the set's own `out` is refused, and so is an out
whose character folder already holds a GLB): the new bodies' build `r2c/build` (the chameleon on M2c's body, the
axolotl on M1f's) into `loco/t1`, `... alien_loco.py --raw D:/prime-art-raw --build r2c/build --out loco/t1`. On T1
the chameleon's set is made (31 clips; Jog_Fwd v0 5.44 m/s, Sprint_Fwd 8.34, f3's 5.15 and 7.80 on the taller body).
The axolotl's is not: on M1f's body her Jog_Fwd and Sprint_Fwd touch the floor for 2 frames a step (a toe within
2 cm of its lowest), so `measure` finds no ground velocity (v0 0, c0 None) and `stride` divided by zero (since R1 the set skips such a clip instead: `SKIP <clip>: speed ... asked, but the measure found no ground velocity`, `skipped` in its `loco.json` row, and so every clip made from it; `alien_loco_math.unmeasured`). The build's
floor edit lifts those clips 4.4 and 5.2 cm (the S4b body's 2.7 and 3.6). M1f's legs are shorter than S4b's, not
longer (T2: 0.774 m against 0.845; thigh 0.255 m against 0.323, shin 0.420 against 0.403, the foot 3.6 cm shorter, the
bones' rest orientations equal), so the same bone-local rotations sweep her feet on another arc: the jog's planted
toes rise 4.6 cm over the stance (S4b's 1.4 cm).

`alien_char_run.py --leg-fit` (T2, art #196; `alien_char_build.py --leg-fit <S4b body.blend>`,
`tools/blender/alien_leg_fit.py`) fits the clips to a body with its own leg proportions before the clip edits:
every action's Root and Hips location keys scale by the body's leg length over S4b's rig (`alien_char_geom.leg_fit`,
slice `--own-proportions`' rule; 0.917 on M1f), then per frame the Hips move along the world's up so the feet's
lowest point (each Foot and Toes head, each toe tip) is as high as on S4b's rig playing the clip as made. The build
records `leg_fit` in its char.json and `alien_loco.py` gives the loops it appends (`TM_`, `MC_`, made on the S4b rig)
the same fit; a build without the flag is unchanged (r2b, r2c, f3, the chameleon's loco t1). On T2 (`r2e/build`,
`loco/t2b`; `r2d` and `loco/t2` hold the scale-only try, which still divided by zero) the axolotl's set is made, 31
clips, glTF-Validator 0 errors, but its numbers are not sane yet: the Sprint_Fwd source measures 4.60 m/s (S4b's
7.80), so its stride scales 1.52 and its feet slide 67 mm; Jog_Fwd 4.63 m/s (5.15) slides 17 mm (f3: 0). Matching
the lowest point's height is not enough: the horizontal sweep differs too. The next step is the feet themselves: the
ankles and toes on S4b's trajectories scaled by the leg ratio, the legs solved by two-bone IK (`alien_clip_edit.two_bone`).

`alien_char_run.py --leg-fit --leg-ik` (T3; `alien_char_build.py --leg-fit-mode ik`) is that step, in place of the
lowest-point match: after the scale, per frame each ankle's target is its own rest place plus S4b's ankle move from
its rest, scaled by the leg ratio (`alien_char_geom.foot_target`: a planted foot stays planted, the stance width is
the body's own), the foot's world turn S4b's, the thigh and shin solved to it with the knee in the clip's own bending
plane (`alien_char_geom.reach_knee`), the UpperLeg, LowerLeg and Foot rotations keyed on every frame; the Toes and
the Hips keep the clip's (scaled) keys. The build's char.json records `leg_fit.mode` and `alien_loco.py` applies the
same mode to the loops it appends. Per action the report gives the ankles' worst miss, the frames out of reach, the
knee's largest per-frame change beside S4b's own (a pop), the knee flips and the feet's lowest point against S4b's.
`alien_char_build.py`'s default mode (`lowest`) is T2's, so r2e and loco/t2b rebuild as they were; since B1c (art #196) `alien_char_run.py --leg-fit` uses `ik` (`--leg-fit-lowest` for T2's), because with no Hips lift left to hide it the lowest-point match dips her Walk's Hips 22.6 mm in a frame at heel strike (the lowest point jumps between heel and toe), while the IK keeps the clip's own bob (step 9.3 mm, knee pops equal to S4b's). With `ik` a clip's `leg_fit_bob` (`alien.toml`, per clip, 1.0 when absent) scales the Hips' bob about its mean before the legs are solved (`alien_char_geom.bob_offsets`), so the feet keep their paths and the knees take it; the report's `foot_match.<clip>.bob` gives the factor and the Hips' largest step before and after. Jog_Fwd 0.84 and Sprint_Fwd 0.88 bring her runs from the library's 70.8 / 64.3 mm per frame to about B1's 60 / 57; the Walk keeps 1.0. A build without `--leg-fit` (the chameleon) never reads it. Since B1d the IK solves each action twice: copying S4b's ankle path left her 3.6 cm shorter foot's toe higher than S4b's on a heel-up stance (her Crouch_Fwd and Crouch_Run shoes 29-32 mm off the floor where the chameleon's are 19), so after the first solve each ankle target moves by `alien_char_geom.sole_dz` until the foot's lowest bone point (its Foot and Toes heads, its Toes tail) rises from its rest height as S4b's does, scaled; a flat foot moves nothing, and the report's `foot_match.<clip>.sole_dz_mm` gives the move's range. Her crouches came to 22.6 / 23.3 mm, the Walk's highest planted shoe from 2.7 to 1.3 mm, the Hips untouched.

The contact proof: `alien_contact_measure.py` (Blender, through `tools/runner/blender.py`) writes per clip and frame the Hips' height and each skinned mesh's lowest point of a character blend; `alien_contact.py OUT.md LABEL=bare.json,stage.json,...` turns them into the contact table (per stage the ground's min and max, the frames floated over 5 mm outside real flight, the frames under -2 mm, the Hips' largest step). A walk, a crouch, an idle or the talk (`NO_FLIGHT`) has no flight, so a frame with both feet up counts as floated there; the bare body's lowest marks flight only in the runs and jumps.

A build made with the first, scale-only leg fit (commit `ba1f4233`: `r2d`, behind `loco/t2`) mixes methods when
`alien_loco.py` is re-run on it at a later commit: its char.json's `leg_fit` has no `mode` and no `foot_match`, so the
loops `alien_loco.py` appends get the default `lowest` fit (the scale and the foot match) while the build's own actions
kept the scale alone. Do not re-run the loco set on such a build: rebuild the character (`alien_char_run.py --leg-fit`,
into a new build folder) and run the loco set on that. Since F1 (art #196) the donor's world frame is built from its
saved transforms (`matrix_basis` and the parent chain, `alien_char_geom.chain_world`) and checked after linking, and
the report records it (`donor_matrix_world`). A headless Blender probe (F1) showed the old read was wrong: on
an appended, unlinked object `matrix_world` reads the identity (a parented, turned and scaled test rig: 0.75 off the
file's; now 1.2e-7); S4b's rig is the identity in its file, so the builds made so far are unchanged.
`tools/blender/alien_body_clips.py --char <c> --rows r2b=loco/f3/build,<tag>=<loco>/build --out <dir>` shoots the
full-body clip frames of one character's builds side by side (`godot/alien/body_clips.gd` in the off-screen window,
the game look of `char_shots.gd`, a floor, the camera following the Hips): a row per build, six clips (idle, walk,
Jog_Fwd, Crouch_Fwd, Jump_Start at its take-off, Strafe_Left), `body_clips_<c>.jpg` and its `.json` (per cell the
clip's time and the Hips' height).
`... alien_loco.py --raw D:/prime-art-raw --reels [--only NAME,...] [--char axolotl]` runs `godot/alien/treadmill_reels.gd` in the
off-screen window on the chameleon (`--char`: another character, into `<out>/reels/<char>/`): the character held in place (the hips' travel per loop taken off its node), the
floor's stripes moving at the slot's speed against the travel, the clip at rate = speed / v0, a disc under each foot
at its contact and a timeline of the game's footstep beat (white ticks, the clip's own contacts as yellow ticks
under them, so a footstep clock that does not match the feet shows) beside each foot's contacts (left blue, right
orange); one 1280x720 MP4 per slot (a clip with a speed variant as a pair), one 8-frame sheet per slot, the jog grid's
2x3 sheet and `Idle_to_Jog_Fwd` with the game's 0.15 s cross-fade (its sheet: 8 frames from 0.25 s before the switch
to 0.8 s after), into `<out>/reels/`.

The honest numbers (step 4b; `loco.json` per clip and the `CLIP` lines): `measure`'s foot slide counts a foot as down
by a speed tolerance that grows with the clip's speed and fills short gaps, so on a sideways or backward clip a low
swing can join a contact (step 3's 6691 mm and 1313 mm). `alien_stride_math.honest_slide` takes a foot point (ankle,
toes) as planted only by its height (within 1 cm of its lowest) and its speed against the ground (under 0.5 m/s),
no gap filling: `drift_mm` in each planted run, and `skate_m_s`, the fastest a point within 1 cm of the floor moves
(a heel or toe that skims the floor; a touch-down frame also counts, so read it beside the reel). `knee_bend` gives
each leg's least knee bend (all frames and swing frames), `hand_clearance` each hand's least distance from the
torso's axis (a hand into the belly comes close). `play_rows` gives per game speed the step interval beside the
footstep beat: the interval the game's footsteps should use is the clip's step interval at that speed.

Two fixes in `alien_stride_math` found here, both for loops that travel (step 2's root-motion bakes; the UAL loops are
in place, so steps 1's numbers stand): `cycle` turning a loop to start on the contact now carries the frames from before
the start (and, at start 0, the end frame) a loop's travel on, where they went back to the start; `stride`'s end frame
plants the feet a loop's travel on, where the legs reached back a whole loop at the seam.

### The clothed alien's two bodies (art #196, clothes step 2)
The aliens are always clothed (the route of the engineer's yes to step 2, 2026-10-28, art #196 comment
6469797321): our own body stays the functional base, Meshy makes only the clothes, and each garment is fitted once on
the base body and carried to the female variant. The base is S4b's cage body (`D:/prime-art-raw/review/char/alien-parts-kit/S4b/build/alien_body.blend`,
`tools/blender/alien_cage.py --target`), the body under both characters of `loco/f3`.
- **Four digits.** The engineer, 2026-10-28 (comment 6467823137): three fingers and a thumb, never a fifth. The cage
  body already builds that hand (`alien_cage.py`'s `FINGERS = ("Index", "Middle", "Ring")`: three finger tubes and a
  thumb on one surface with the arm; the Little groups present and empty, 0 vertices). `[kinds.alien]` lists
  `fingers_unweighted = ["Little"]` again (`docs/contract.md`; the ADR
  `2026-10-19-alien-overlaid-face-four-fingers.md`, amendment of 2026-10-28).
- **The female variant** is the same mesh with only vertex positions moved: `tools/blender/alien_body_female.py`
  (headless Blender) applies `alien_female_geom.py`'s fields from a target file (`alien_female_targets/<name>.toml`,
  every nested key checked) and proves the result on the saved file: the vertex, edge and face counts and the hashes
  of the faces' and edges' vertex indices, the weights and the UVs equal the base's; `female.json` holds the
  per-vertex delta report and the half widths and depths per height. The fields (each a product of
  `(1 - t^2)^2` kernels, exactly 0 outside its box, scaled by the vertex's weight on the trunk and upper-leg bones):
  two soft chest rounds pushed forward on the front half (no nipples), the hips' sides out linearly in x, two seat
  rounds pushed back on the back half, the waist's sides in; nothing above 1.25 m or below 0.70 m moves, so the
  height, neck, arms, hands, legs below the thigh and feet are the base's. f1 (`body_f1`, under
  `<raw>/research/2026-10-22-roster/design/pilot3d/clothes/a/`): 1,044 of 9,814 vertices moved, at most 21.8 mm;
  half width at 0.86 m 135 -> 157 mm, the seat 13 mm further back at 0.86 m, the waist at 1.00 m 106 -> 96 mm, the
  chest 12 mm further forward on the midline at 1.14 m (20 mm at the rounds' centres).

      blender -b --factory-startup --python tools/blender/alien_body_female.py -- --body <S4b alien_body.blend>           --target tools/blender/alien_female_targets/f1.toml --out <dir>

  A character on it: `alien_char_run.py --body <dir>/alien_body.blend` (the legs are the base's, so no `--leg-fit`).
- **The weld's seam.** In close-ups the bridge between the body's neck ring and the head's cut (`alien_char_build.py`:
  24 ring vertices zipped to the head's cut loop over 8 mm) read as a thin sewn line with a dent at each ring vertex.
  Since this step the build smooths the vertices round it after it closes (`alien_char_geom.taubin`, 12 Taubin steps,
  each move scaled by `seam_weight`: 1 at the bridge's middle height, 0 at 22 mm below and 16 mm above; only within
  1.5 ring radii of the neck's axis); char.json's `seam_smooth` records it, `--no-seam-smooth` builds as before.
- **Close-ups.** `tools/blender/alien_closeups.py --blend <char>_char.blend --tag <t> --out <dir>` (headless Blender,
  Workbench) shoots `neck_<t>.png` (the joint at 1.9 m, lens 70, and 0.8 m, lens 50; 3/4 front, side, 3/4 back of the
  character's left; Idle and the head turned 40 degrees; texture colours beside a flat colour with cavity) and
  `hands_<t>.png` (the left hand at 0.45 m from outside and the front in Idle, Jog_Fwd, Jump_Start and Talk_Upper, at
  each clip's first and middle frame).
- **The game build** is f3's: `alien_char_run.py --heads <c> --tag <tag>/build --no-shots --clip-edits
  tools/blender/anim_sets/alien.toml --lively <c>=<lively>/v9_r2c_n4 (axolotl: axolotl_v9_r2c_n4) [--body <female>]`,
  then `alien_loco.py --raw D:/prime-art-raw --build ../<tag>/build --out ../<loco>` (paths under the set's
  `raw_base`), then `godot-check <glb> --profile alien --strict-contract --textured`.

### 100STYLE onto the alien, and the orientation warp (art #196, the strafe pilot)
The strafe pilot's mocap source is 100STYLE (`sources/100style.toml`: CC BY 4.0, the credit line there; one 1.47 GB
zip of BVH takes, 60 fps, a 23-joint skeleton in centimetres, extracted under `<raw>/downloads/100style/extracted/`).
Its Neutral style ("Normal walking") gives the backward run (BR), the sidestep run (SR), the forward run (FR, the
speed and sanity reference) and the backward walk (BW). `tools/blender/retarget_maps/100style_contract.toml` maps it
onto the contract skeleton (FK legs as `smpl_contract.toml`; Chest, Chest2, Chest4 -> Spine, Chest, UpperChest,
Chest3 unused; Collar/Shoulder/Elbow/Wrist -> Shoulder/UpperArm/LowerArm/Hand; Hip/Knee/Ankle/Toe -> UpperLeg/
LowerLeg/Foot/Toes; fingers, Jaw and eyes at rest): the source rest gives the target rest exactly (rest check 0.001 mm,
0 deg; both rests are T-poses facing the front, so no `[align]`).

`$PYTHON_BIN tools/blender/alien_mocap.py --raw D:/prime-art-raw [--char chameleon] [--clips Neutral_BR,...]`
(about 2 min) imports each take with Blender's own BVH importer (bundled `io_anim_bvh`: scale 0.01, the file's +Z
front onto -Y, quaternions; the rig lifted onto the floor for the retarget as `retarget_smpl` does), picks the
steadiest 3 s window inside the take's `Frame_Cuts.csv` range (`pick_window`: the travel straight, the hips' facing
against it near the clip's own: BR 180, SR 90, FR 0, BW 180 degrees), bakes it at the character's 24 fps, puts its
planted level on the floor, turns it to face -Y, cuts one loop from a left contact (`cycle`) and takes it in place
(`in_place`). Into `<raw>/research/2026-10-22-roster/design/pilot3d/anim_bare/loco/p1/`: `mocap.json` (per clip the
window, the rest check, the numbers), `chameleon_char_100s.blend` (actions `CharacterArmature|MC_<clip>`, the faced
window, and `CharacterArmature|MC_<clip>_Loop`; the axolotl shares the skeleton) and `check_sheet.png` (the 100STYLE
skeleton as sticks above the alien, BR from the side and SR from the front, the same moments). The takes run slowly
on the alien (loop v0: BR 0.90, SR 1.24, FR 1.60, BW 0.65 m/s), so the game's speeds need the stride and cadence
of `stride`.

`alien_stride_math.orient_warp(skel, clip, hip_yaw, travel_deg=0, split=ORIENT_SPLIT, feet_yaw=None)` turns the Hips
by `hip_yaw` degrees about the vertical (positive: toward the left, +X), counter-twists Spine, Chest, UpperChest and
Neck by `split` (0.2, 0.25, 0.3, 0.25: the shares of the yaw turned back, so the head keeps its world rotation), and
re-plants each ankle on the clip's own track turned by `travel_deg` (0 keeps the travel; a forward run into a left
strafe is 90), shifted by one constant per foot that keeps it under its turned hip joint (a constant keeps a planted
foot planted), the leg solved again with `two_bone`, the foot turned by `feet_yaw` (default the hips'). Zero and zero
give the clip back; `hip_yaw = travel_deg = d` with `split=()` turns the whole clip (how `alien_mocap.py` faces a
take). Tests: `tools/tests/test_alien_stride_orient.py`.

### The side, diagonal and back clips (art #196, the strafe pilot P2)
P2 rebuilt the strafes and the back run from step 4b's text-to-motion clips into a forward run turned toward the
travel and a mocap backpedal, all through `anim_sets/alien_loco.toml` and `alien_loco.py` (out: `loco/p2`). The set
file's new keys:
- `[set] mocap`: a second source blend, P1's `loco/p1/chameleon_char_100s.blend`; its `MC_<style>_<take>_Loop`
  actions are read like the `ttm` blend's `TM_` loops;
- `from`: a made clip of the set as the source (the approved `Jog_Fwd`: its 22-frame cycle, its arms), not cut again;
- `orient = { hips, travel, split? }`: `alien_loco_math.orient`, `orient_warp` with **absolute** headings (degrees, 0
  at the aim, positive toward the left): a clip whose head looks more than 0.5 degrees off the aim is first turned
  whole onto it (a 100STYLE take's head, hips and travel each sit 15-30 degrees apart), then its hips' mean heading
  goes to `hips` and its feet's travel to `travel`. After the stride the planted feet's measured travel is set
  exactly by `trim_travel` (the feet's tracks alone turned: they roll heel to toe along their own heading, which
  pulled the measured travel 5 degrees toward the hips). The side runs' `split` puts more of the twist into the neck
  and head (Spine 0.1, Chest 0.15, UpperChest 0.15, Neck 0.35, Head 0.25): with the hips at 60 the upper chest is 36
  toward the travel, so the arms swing with the turned body, and the head stays on the aim;
- `cadence`: the steps per second the loop is retimed to before the stride takes the rest of the speed (the backpedal:
  4.0, short quick steps);
- `lean_deg`: the trunk leant forward (`LEAN_SPLIT`, Spine 0.4, Chest 0.35, UpperChest 0.25; the backpedal: 8, the
  take ran upright; 6/10/14 tried: the hanging hands come closer to the belly as it leans);
- `head_level`: `alien_stride_math.level_head`, the neck and head lifted by one constant so the head's mean front
  pitch over the loop is this many degrees (the crouch: -5, the take looked 48 down; the backpedal: -10, from 34
  down);
- `[[reel]]`: the reels by hand (`alien_loco_math.reel_plan(jobs, reels)`): per entry its `views` (one reel each,
  `<name>__<view>`: `front`, `three_quarter` from the front left, `back`, `side` from the character's left), its
  clips with a speed, an optional `travel` (the stripes' heading: the game's pure side clip carried along a
  diagonal shows its skate) and `label`; `video = false` gives a sheet of four phases per clip in `cols` columns.
  Without `[[reel]]` the old automatic plan runs.

`alien_stride_math.facing(skel, clip)` reports per clip (`loco.json`'s `facing`, the build log's `CLIP` lines) the
hips' and the head's mean heading, the head's swing about it, the head's and the upper chest's front pitch, and
`travel_heading_deg` the planted feet's travel. `pitch(skel, clip, deg, split)` leans a chain about the left-right
axis (positive: the front down). Tests: `tools/tests/test_alien_stride_p2.py`.

The clips (game names; `__` names are review variants):
- `Strafe_Left` / `Strafe_Right` (mirror): `Jog_Fwd` turned to a 90 degree travel with the hips at 60, fitted to 3.0
  m/s at rate 1 (the same 22-frame cycle: stride 0.69); `Strafe_Left__h45`, `__h60`, `__h75` the hip grid;
  `Strafe_Left__100s` the mocap side run with its hips turned to 60 too (4 steps/s); `Strafe_Left__s4b` step 4b's;
- `Jog_Fwd_Left` / `Jog_Fwd_Right`: `Jog_Fwd` turned to a 45 degree travel, hips 35, at 3.5 m/s (the speed ellipse
  through 4.5 ahead and 3.0 aside at 45 degrees);
- `Jog_Bwd`: the 100STYLE Neutral BR at 4 steps/s and 2.5 m/s, its head and travel set straight, its head lifted to
  -10; `Jog_Bwd__c20`, `__c25`, `__c30` the back cap's grid (2.0, 2.5, 3.0 m/s, all at 4 steps/s, the stride 1.7,
  2.1, 2.5x the take's, its trunk leant 8 degrees); `Jog_Bwd__s4b` step 4b's; `Jog_Bwd_Left` / `Jog_Bwd_Right`: the backpedal toward the back
  left with the hips at -45 (turned away from the travel), 2.5 m/s;
- `Crouch_Fwd`, `Crouch_Run`: their heads lifted (`head_level -5`); `Crouch_Run__s4b` the before.
The other plain 100STYLE styles' BR takes run no clearly faster than Neutral at a plain look (a root-speed scan of
seven: 0.6-1.1 m/s; the faster ones are the "big steps", "bent forward" and "checking behind" styles), so P2 keeps
Neutral.

### The critic's fixes (art #196, the strafe pilot P3)
P3 answers P2's fresh critic (out: `loco/p3`; P2's clips stay in the set as `<name>__p2`, the reels' before rows).
New set keys, read by `alien_loco._make` in this order after the stride (tests: `tools/tests/test_alien_stride_p3.py`):
- `widen_m`: `stride`'s ankle widening across the travel (each ankle that far outward on every frame);
- `lift_m`, `bob_m`, `flight_m`: `alien_stride_math.lift_hips`: the Hips raised (`lift_m` > 0: straighter legs) or
  lowered on the **kept** feet, less `bob_m` on the single-support frames (a raised cosine: the hips dip at
  mid-stance), each leg solved again on its own ankle and foot rotation; then the whole body raised by `flight_m`
  over the handover frames (both feet down or both up), a short hop with both feet off the floor;
- `arms_from.phase`: the donor's swing sampled that fraction of its loop later (0.5: a backpedal's arm swings against
  its own leg, as in a forward run);
- `arms_in_deg`: `arms_in`, each upper arm turned toward the body about the chest's front axis (a flaring elbow in);
- `pin = true`: `pin_feet`, the planted feet pinned by `honest_slide`'s own test (within 1 cm of the lowest, under
  0.5 m/s against the ground): the foot held flat while its heel and toe are both down, then the point that is down
  kept where it landed, carried by the ground, fading out over two frames (the stride's own contact test differs:
  the backpedal's left foot still drifted 16-21 mm); when the point that is down switches inside a run (ankle to
  toe or back), the new one starts where the previous frame's correction put it (`_pin_run`, P5), so the correction
  never jumps (before P5 each point started at its own uncorrected place and the correction fell to 0 at the switch;
  on the set's game backpedal clips the switch frames carried under 0.2 mm, so their P5 build equals P4's; only P3's
  before rows `Jog_Bwd__p3` and `Jog_Bwd_Left__p3` moved, at most 3.4 mm in `measure`'s toe slide);
- `orient = { whole = true, travel = T }`: the clip turned as a whole until its feet travel along `T` (default 0), its
  pose in its own space unchanged (the crouch take ran 13.6 degrees off the aim).

`loco.json` adds per clip `airborne_frames` (neither foot down by the honest test), `legs_m` (`leg_spacing`: the
ankles' and knees' least signed room along the hips' axis, the ankles' room across the travel where they pass) and
`elbow_deg` (`elbow_bend`: mean, least, most).

The clips after P3 (`Strafe_Left__100s` and the hip grid dropped: h60 is `Strafe_Left`):
- `Strafe_Left` / `Strafe_Right`: hips 5 cm up (3 and 4 cm left the deeper knee at 40 and 35 degrees), ankles 3 cm
  wider, arms 14 degrees in;
- `Jog_Fwd_Left` / `Jog_Fwd_Right`: hips 3 cm up, arms 14 degrees in;
- `Jog_Bwd` (= `__c25`), `__c20`, `__c30`: 3.4 steps/s (a 14-frame cycle, the back family's), the stride 1.94, 2.43,
  2.91x the take's; hips 3 cm down with a 3 cm dip and a 2 cm flight; pinned feet; `Jog_Fwd`'s arms at half swing,
  half a loop on. The take's small steps (0.30 m) leave no way to keep both the critic's cadence (about 3.3) and a
  stride under 2.0x above 2.0 m/s: only `__c20` meets both;
- `Jog_Bwd_Left` / `Jog_Bwd_Right`: the same, with the side runs' twist split (the chest turns with the hips) and 3
  cm wider ankles;
- `Crouch_Fwd`, `Crouch_Run`: turned back as a whole (`travel = -2.0`: the feet at -2.5 and the head at +3.0; after
  the head lift the take's head looks 5.5 degrees left of its feet, which no whole turn removes).

### The backpedal's arms and even steps (art #196, the strafe pilot P4)
P4 answers the manager's look at P3's backpedal (out: `loco/p4`; P3's back clips stay as `Jog_Bwd__p3` and
`Jog_Bwd_Left__p3`, the reels' before rows). Two new set keys (`alien_loco_math.P4_KEYS`; tests:
`tools/tests/test_alien_stride_p4.py`):
- `even_steps = true`: `alien_stride_math.even_steps`, right after the source's cycle is cut in place: the loop
  retimed by a smooth warp (frame u samples u - a sin^2(pi u / T), a = T/2 less the other foot's contact start, kept
  monotonic: |a| < T / pi, else refused) so the other foot lands half a cycle on. The backpedal take's steps were 7
  and 9 of its 16 frames, 6 and 8 of the 14-frame game loop; now 8 and 8, so 7 and 7;
- `arms_carry = { side_m, front_m, dz_m, swing_m, rise, out_deg }`: `arms_carry`, last before the clip is put in
  place: each wrist (the Hand bone's head) put on a target in the trunk's frame (the UpperChest's front laid level,
  world up): the Spine's head (the waist) + `side_m` outward + `front_m` forward + `dz_m` up, swung +-`swing_m`
  forward (and `rise` times that up) against the same-side ankle's fore-aft place under the hips; the arm solved as
  two bones with its own lengths, the elbow in the plane through shoulder, wrist and a pole pointing back and
  `out_deg` outward; the hand keeps its pose on the forearm (`arms_from`'s, Jog_Fwd's hands).
  `arm_carriage` measures it (`loco.json`'s `arms_m`): per side the elbow bend, the hand's least distance from the
  torso axis, its least distance from the midline plane, the wrist's height over and place in front of the waist,
  the elbow's least distance from the torso axis.

Tuned on P2's dump in plain Python (two grids, 32 and 16 tries, about 15 s each): side 0.15-0.21, front 0.10-0.18,
dz -0.02-0.04, swing 0.04-0.07, out 10-25. The hand's distance from the torso axis is less than hypot(side, front):
the trunk leans 8 degrees, the axis passes in front of the waist; dz sets the elbow (-0.02: about 84, 0.04: about
102); `out_deg` moves only the elbow (10: 0.22 m from the axis, 25: 0.26). Picked: side 0.20, front 0.17, dz 0.01,
swing 0.05, rise 0.35, out 12 on `Jog_Bwd` (`__c20`, `__c25`, `__c30`) and `Jog_Bwd_Left`: hands 0.246/0.237 m from
the torso axis (P3: 0.386/0.372), elbows 89/87 deg (least 85/84), 0.20 m from the midline, the wrists -0.7 to +2.4 cm
about the waist and 0.12-0.21 m in front of it, the elbows 0.23/0.22 m from the axis (P3: 0.33/0.30).

The stride's factor reads higher after the warp (c25 2.43 -> 2.69x, c20 1.94 -> 2.15x, c30 2.91 -> 3.23x): the
warped take's measured speed is lower; the step on the floor is the same (speed / cadence, 0.735 m at 2.5 m/s). The
strafe's swing shin crossing the stance leg from the front is left as it is: the legs travel along the picture plane
there and overlap at passing whatever the track (P3's 3 cm wider ankles are kept).

### The back cap at 2.0 and the follow-ups (art #196, F1)
The engineer picked the back cap **2.0 m/s** (2026-10-26) from P5's grid (2.0, 2.5, 3.0 m/s: the take's stride
stretched 2.15, 2.69, 3.23x after the warp); the side cap stays 3.0. `Jog_Bwd` and the back diagonals `Jog_Bwd_Left` /
`Jog_Bwd_Right` are fitted to 2.0 (their other settings P4's); the grid clips `Jog_Bwd__c20`, `__c25`, `__c30` and
their reel `Jog_Bwd_caps` are dropped (out: `loco/f1`; the reels' before rows, `Jog_Bwd__p3` and `Jog_Bwd_Left__p3`,
stay at P3's 2.5). The clips at 2.0 (`loco.json`, the chameleon; the axolotl shares the skeleton):

| Clip | Steps/s | Step | Stride x the take's | Planted drift (honest, L / R) | Least knee bend (all / swing) | Hands from the torso axis |
|---|---|---|---|---|---|---|
| `Jog_Bwd` | 3.43 (14 frames, rate 1.14) | 0.58 m | 2.15 (warn: over 2x) | 0.0 / 0.3 mm | 33 / 37 deg | 0.25 / 0.24 m |
| `Jog_Bwd_Left` (`_Right` its mirror) | 3.43 | 0.58 m | 2.04 (warn) | 0.0 / 0.0 mm | 34 / 37 deg | 0.24 / 0.25 m |

The stride stays over 2x at the cap: the take's own steps are small (0.30 m); 2.0 is the least stretched of the
grid, and the slide stays inside the 5 mm bound.

`max_scale` holds after the retime's whole-frame rounding (PR #326's follow-up): `capped_rate` takes the loop's frame
intervals and floors a rounded count that would stretch the stride past the cap (`Jog_Bwd__s4b`: its capped rate
1.3075 rounded to 26/20 = 1.3 and its scale to 1.509, over its 1.5; now 26/19, 1.433), and `alien_loco` refuses a
stride over its `max_scale` (`check_max_scale`). Step 4b's `arms_from = { clip = "Jog_Fwd", k = 0.75 }` (on
`Strafe_Left__s4b` and `Jog_Bwd__s4b`) scales a donor whose swing is already its grid's pick 0.75 of the take's, so
those arms swing 0.75 x 0.75 = 0.56 of the take's own. Step 4b's slides stand over the 5 mm bound (`SLIDE_BOUND_MM`,
"The alien locomotion clip tool"): `honest_slide`'s planted drift on `Strafe_Left__s4b` is 6.2 / 5.6 mm and on
`Jog_Bwd__s4b` 7.7 / 16.5 mm (F1's build; 4b read about 6 and 12-18); both are kept as step 4b's record only, no reel
plays them, and the game's clips since P3 are pinned (`pin`: 0.0-0.3 mm at F1).

### The strafe's shin crossing, a review grid (art #196, F2)
In the strafe's reels the swing shin briefly passes behind the stance leg. F2 measured it (per frame of the 22-frame
cycle, in the hips' frame: the swing ankle's and the swing shin's midpoint's distance along the hips' left-right axis
from the stance shin at the same height, + on the swing leg's own side; joint centres against the bone's line, so 0
means the meshes still touch, the limbs having thickness; not `loco.json`'s `legs_m`, which measures ankle against
ankle; the measurement was a plain-Python pass over the GLB, not committed) and built four review variants of
`Strafe_Left`, each one setting changed, beside it (out: `loco/f2`; the reels `Strafe_F2_<variant>__three_quarter`
and `__back`, Strafe_Left above the variant). They await the engineer's look; `Strafe_Left` / `Strafe_Right` and
every other game clip are unchanged (their `loco.json` reports and GLB animation bytes equal `loco/f1`'s):

| Clip | Change | Ankle / shin least | Frames under 0 / under 3 cm | Least knee bend L / R | Planted drift L / R | Hips / head |
|---|---|---|---|---|---|---|
| `Strafe_Left` | (widen 0.03, hips 60) | -8.4 / -0.7 cm | 7 / 8 (frames 4-11) | 30.4 / 19.7 deg | 0.6 / 0.9 mm | 60.0 / 0.2 |
| `Strafe_Left__w07` | `widen_m` 0.07 | -2.8 / +3.4 cm | 4 / 6 | 27.9 / 19.6 | 0.6 / 0.9 | 60.0 / 0.2 |
| `Strafe_Left__w09` | `widen_m` 0.09 | 0.0 / +5.4 cm | 0 / 5 | 26.1 / 18.7 | 0.6 / 0.9 | 60.0 / 0.2 |
| `Strafe_Left__h65` | hips 65 | -2.9 / +3.3 cm | 6 / 6 | 30.4 / 21.1 | 0.5 / 0.8 | 65.0 / 0.2 |
| `Strafe_Left__h70` | hips 70 | +2.9 / +7.4 cm | 0 / 1 | 30.3 / 22.4 | 0.4 / 0.7 | 70.0 / 0.2 |

Tried on a dump in plain Python and not built: `widen_m` 0.05 (-5.6 / +1.3 cm), hips 55 (-13.7 / -4.4 cm: more
crossing), `lift_m` 0.03 (the crossing unchanged, the knees deeper) and `bend_min_deg` 30 (no change: the floor does
not bite). The builder's pick is `__w09`: it keeps the engineer's hips at 60 and brings the swing ankle's centre from 8.4 cm past
the stance shin to its line (0.0 cm), so the meshes still graze; `__h70` is the only one with clearance (+2.9 cm) but
moves the hips toward the 75 he passed over. In F2's reels the tuck shows in column 5 (the older reels: column 6);
the enlarged column sheets `Strafe_F2_col5.png` and `col6.png` were cut by hand from the reels. The engineer took
`__w09` for the game (2026-10-27): F3 below.

### The strafe at `widen_m` 0.09 (art #196, F3)
`Strafe_Left` takes `widen_m` 0.09 (hips 60, the rest of P3's settings unchanged; `Strafe_Right` mirrors it). P3's
strafe stays beside it as the review variant `Strafe_Left__w03` (`loco.json` report and GLB animation bytes equal to
`loco/f2`'s `Strafe_Left`); F2's four variants and their reels are dropped. Out: `loco/f3`; the reels
`Strafe_F3__three_quarter` and `__back` (`Strafe_Left__w03` above `Strafe_Left`) on both characters (the axolotl's in
`reels/axolotl/`). Every other game clip's `loco.json` report and GLB animation bytes equal `loco/f2`'s, and the
strafes' speed, rate, cycle, stride and contacts did not move (3.0 m/s, rate 1.014, 22 frames, 0.917 s, contacts
left 0 / right 11, step 0.452 s). The strafe at 0.09 (F2's measure, on a dump of F3's build):

| Clip | Ankle / shin least | Frames under 0 / under 3 cm | Least knee bend L / R | Planted drift L / R | `legs_m` ankle / knee / pass |
|---|---|---|---|---|---|
| `Strafe_Left` (0.09) | 0.0 / +5.4 cm | 0 / 5 (frames 5, 7-10) | 26.1 / 18.7 deg | 0.6 / 0.9 mm | -0.046 / 0.122 / 0.352 m |
| `Strafe_Left__w03` | -8.4 / -0.7 cm | 7 / 8 (frames 4-11) | 30.4 / 19.7 deg | 0.6 / 0.9 mm | -0.149 / 0.087 / 0.232 m |
| `Jog_Fwd_Left` / `_Right` | +8.7 / +11.8 cm | 0 / 0 | 27.2 / 20.6 deg | 0.2 / 0.3 mm | 0.061 / 0.152 / 0.218 m |

The forward diagonals do not cross: at 45 degrees of travel the swing ankle stays 8.7 cm or more outside the stance
shin (they have no `widen_m`), so they stay as they are.

### The head follows the aim (art #196, H1)
So players can nod yes and shake no without a microphone, the alien's trunk, neck and head bones turn toward the
player's aim on top of any clip; the head's mesh stays as it is (no face rig). `godot/alien/head_look.gd` is the
reference `SkeletonModifier3D` the game copies (a child of the character's `Skeleton3D`; Godot runs every modifier
after the `AnimationMixer`, so it works over Idle, the jogs and the strafes alike):
- inputs `aim_yaw` (radians, the aim relative to the body, + to the character's left) and `aim_pitch` (+ up);
- clamps `yaw_limit_deg` 70, `pitch_down_deg` 35, `pitch_up_deg` 40 (H1's recommendation for both aliens: at 50 down
  the face hides under the crown from the front and the jaw sinks into the chest, worst at full yaw and on the jog's
  forward lean; R1 had proposed 50);
- the split `yaw_split` Spine 15 / Chest 20 / UpperChest 20 / Neck 25 / Head 20 and `pitch_split` Chest 10 /
  UpperChest 20 / Neck 35 / Head 35 (H1's "trunk" split; R1's Spine 10 / Chest 15 / UpperChest 15 / Neck 25 / Head 35
  and UpperChest 15 / Neck 35 / Head 50 put more twist into the neck's skin); shares are normalised, missing bones
  skipped; each bone of the chain takes its share as a turn about skeleton space's up and the yawed right axis, so
  the head bone ends turned by exactly the aim (on the rest pose; on a clip, the clip's own facing turned by it);
- `smoothing_s` 0.05: the applied angles close 63 % of their gap in that time (a 2 Hz nod keeps about 85 % of its
  amplitude); `snap()` jumps to the target;
- `body_follow(body_yaw, aim_world_yaw, dead_zone = DEAD_ZONE)` (static): the body-lag rule: the body keeps its yaw
  while the aim is within the dead zone and turns to keep the aim on its edge beyond it; `aim_yaw` is then the aim
  relative to that body. `DEAD_ZONE` is 45 degrees, the engineer's pick (2026-10-26; the shots' `lag_dz60` stays as
  a comparison).

The pitch turns about the yawed body's right axis (skeleton space's right turned by the yaw), not the head bone's own
right axis: on a clip that tilts the head, the nod stays level with the body. Fed without `body_follow`, an aim
relative to the body that crosses +-180 degrees jumps from +PI to -PI, and the clamped head swings from +70 to -70 in
one go.

What the game needs: the pitch is already in the network pose (`pose.pitch`, today put on a `Head` node, not on the
skeleton): feed it to `aim_pitch`. The yaw relative to the body only exists with a dead zone: today the whole body
turns with the mouse (`rotate_y`), so the relative yaw is always 0 and a "no" shake spins the whole body; with
`body_follow` the body's yaw and the aim's yaw become two numbers to sync.

`$PYTHON_BIN tools/blender/alien_headlook_run.py --check` runs `godot/alien/head_look_check.gd` headless on both
characters (F3's build, `loco/f3`): the head bone's facing within 1 degree of the asked yaw and pitch
inside the clamps, at the clamps beyond them, the Neck turned by `aim_turn` of its cumulative share of the split
(summed in the check from the skeleton's parents), a fresh modifier's default clamps (yaw 100, pitch -80 give 70,
-35), no drift over 10 frames, on Idle and Jog_Fwd the clip's facing turned by the aim, the smoothing, `body_follow`'s
cases and its default dead zone (the constant, and a call without the third argument: aim 60 gives 15, F2)
(`HEADLOOK` lines, exit 1 on a failure); `tools/tests/test_alien_headlook_godot.py`
runs it (heavy; the area `alien_headlook`). The shots' labels print `target()`, the clamped angles. `... --shots [--chars]
[--no-video]` runs `godot/alien/head_look_shots.gd` in the off-screen window (`--fixed-fps 24`) into
`<raw>/research/2026-10-22-roster/design/pilot3d/anim_bare/headlook/<char>/`: `grid_{Idle,Jog_Fwd}.png` (yaw
-70..+70 x pitch +40/0/-50, three-quarter), `extremes_{r1,trunk,rec}.png` (the clamps' corners and edges close from
the front and the side under R1's split, the trunk split, and the recommendation), and the reels (MP4 in `mp4/`
plus an 8-frame sheet): `nod_<clip>` and `shake_<clip>` on Idle, Jog_Fwd and Strafe_Left, `lag_dz45` and `lag_dz60`.

### The photo poses (art #196)

The photo task's poses (prime-game `docs/GDD.md` section 8 "Photo") on the alien: **held poses in two layers**, so any
legs pose goes with any arms pose (6 x 8 = 48 pairs).

- **Names.** `CharacterArmature|PoseLegs_<Name>_Loop` (Stand, OneLeg, Squat, Kneel, Lunge, Sit) and
  `CharacterArmature|PoseArms_<Name>_Loop` (HandsOnHips, Plane, Flex, Heart, FingerUp, HandsBehindHead, PalmsOut,
  Victory; p3: Victory replaced the Salute, the engineer's call; prime-game's GDD section 8 and the design repo's pose
  sheet still say "salute"), plus the hip hand's per-legs variants `CharacterArmature|PoseArms_<Arms>__<Legs>_Loop` (below); Godot
  keeps the names (`pose_layers.gd` strips the prefix and `_Loop`). Each clip is a loop of identical
  keys (the game holds it) keying only its own layer's bones.
- **The bone split** (`alien_pose_math.owner`): the legs own `Root`, `Hips` (translation and rotation), `Spine` and
  both legs to the toes; the arms own `Chest` and everything under it (neck, head, shoulders, arms, fingers). A pair
  is the legs' channels plus the arms', nothing else; no per-pair corrective clip, with one exception (round 2, the
  manager's decision): the hip hand. No hip grip both cleared a raised thigh (Sit, Squat, Kneel, OneLeg: 5-8 cm
  into it on six grips, s5) and still sat on the waist on Stand, so an arm with `clear = ["thigh_{side}"]` (the hip
  hand of HandsOnHips, FingerUp; p3: always, `per_legs`, below) gets a per-legs variant `PoseArms_<Arms>__<Legs>` (Godot name) wherever
  the shared clip's hand goes into that thigh beyond the hand limit: solved over those legs, the wrist moved along
  the arm's `clear_dir` (chest axes; default up the chest, s7: back along the hip's side and a little up, [0, -1,
  0.2]) until the hand clears the thigh, then touched onto the waist again (`Model.variants`). `pose_layers.gd`
  plays the variant with those legs when the character has it; `poses()` does not list variants; the game copies
  this rule. A variant's palm-to-waist distance has its own, looser limit, `variant_mark_cm` (10 cm: the hand rides
  off the waist to clear; review 2 found Sit's 23 cm read no failure under the old "reported, not limited"); a
  variant beyond it is a named failure. An arm's `variant` table (TOML) overrides its settings in its variants only
  (for example the fingers level). **Round 3 (the manager's decision): on `[thigh_hand]`'s legs (Squat, Sit) the
  variant rests the hand on the top of its thigh by the hip crease** (`Model._arm_thigh`): the wrist starts over the
  thigh's top skin `along` of the way from the hip to the knee (Squat 0.25; Sit 0.55: its crease is under the belly,
  and nearer the hip the hand went 5 to 6 cm into it), the fingers along the thigh turned out by `fingers_add`, the
  palm down, the elbow out and back ([1, -0.8, 0]), then touched onto the thigh's skin. Such a pair is measured as a
  contact with the thigh (the gap within `contact_gap_cm`, the hand's through into the thigh and the torso within
  `through_hand_cm`) in place of the waist's mark and the torso contact. **s11: also OneLeg and Kneel, one side
  each** (`sides`: OneLeg's raised right thigh, Kneel's raised left one, `alien_pose_math.thigh_side`; `along` 0.45):
  their waist variants (`clear_dir`) still went 1.1 to 1.7 cm into the belly (s10's 4 failing pairs); the other hand
  stays on the waist. The thigh hand's grip is `flat` (s10's `relaxed` read as a pinch on the thigh).
- **p3: the hand shapes, the Victory and the fist akimbo** (the engineer's look at p2: the salute out, "hands on
  hips like just arms", "fingers a mess"; numbers in `tools/out/poses/p3/grid*.log`, pictures in
  `anim_bare/poses/p3/q1/`):
  - **One hand-shape library**, `[grips]`: `fist` (the fingers curled tight, the thumb over the index), `point` (the
    index straight, the rest the fist), `flat` (the fingers together, slightly curved, the thumb alongside),
    `heart`; no per-pose finger values. `ThumbTurn` [roll, swing] turns the thumb's base about its length and toward
    the palm before its curl (a curl alone turns it about one axis, p1); the left hand's values, the right's mirrored.
    The thumbs come from a search on both dumps for the turn and curl that put the thumb's tip on its target (the
    fist: 1.6 cm off the index's and middle's middle bones on the palm's side, reached within 0.3 cm, its bones 2.5 cm
    clear of the fingers' bones). Plane, PalmsOut, HandsBehindHead: flat; Flex, Victory, the hip hands: fist;
    FingerUp's raised hand: point; Heart: heart.
  - **A straight wrist**: `fingers_dir = "forearm"` lays the hand along its forearm (the fists of Victory and the
    akimbo).
  - **Victory**: FK, both arms up in a wide V (`upper` [0.6, 0.2, 1.0], the elbows nearly straight; q2: a little
    forward, so the side outline shows the arms in front of the crest, not hidden behind it), fists, the
    shoulders shrugged a little (`shoulder` [0, -12, 0]). The arms cannot lift the whole fist over the crest: its
    lowest skin stays 18 to 24 cm under the head's top on every V tried (`gridBC.log`), 17 to 26 cm outside it; the
    fists' tops reach the head's top (q4, `tools/out/poses/p3/q4/victory.log`: 1.2 cm under it on Stand, 0.5 cm over
    on Sit, the inner skin 20 cm outside the head's side), so "the hands above the head" reads as level with the crown.
  - **The fist akimbo** (HandsOnHips and FingerUp's hip hand, one arm): the wrist goal at the waist's side, out and a
    little up (`offset` [0.9, -0.2, 0.6] since q3; q1 [0.9, -0.1, 0.6]; q2: 0.3 sat by the hip bone, not above it), the
    elbow wide and back ([1.0, -0.7, 0.15] since q3; q1 [1.0, -0.4, 0.1]: 22 cm out of the shoulder, 5 to 10 cm behind
    it), the fist's skin (`touch_by` the whole hand) touched onto the torso at 0.5 cm
    (variants 0.8), `passes` 16 (the clear-then-touch loop settles later than 9). `per_legs = true`: a variant on
    every legs pose but the reference, since the shared clip's fist went into the waist or off it wherever the legs
    lean the Spine; `[thigh_hand]` has no legs any more (the fists stay on the waist over Squat's and Sit's thighs).
    A mark contact with `by = "knuckles"` measures the four base knuckles' centre (a fist's palm centre stands a
    fist's depth off the waist), with its own `mark_cm` (9 cm: the knuckles sit about 2 cm off the skin and the fist
    rides above the waist's mark, which is at the Spine's height; read 5.7 to 8.5 cm in q1, 6.3 on Lunge and 7.1 on
    Stand since q3) and, since q4, `legs_mark_cm` for the legs poses whose `legs_variant` lifts the fist (below).
- **p3 q2: arms that keep their meaning in the world, OneLeg's knee, the fist's thumb** (pictures in
  `anim_bare/poses/p3/q2/`, numbers in `tools/out/poses/p3/q2/grid2.log`):
  - **`spine.level`** (a legs pose's setting): the Spine counter-turned that part of the way to a chest upright in
    the world. The arms' directions are in the chest's axes, so on a leaning legs pose every arm leaned with it
    (Plane tilted on Squat and Lunge, the raised arms crooked). Levelled in the legs layer (the Spine is the legs'),
    so every arms pose keeps its world meaning with no per-legs arms variants: Lunge 1.0 (was 6 degrees forward and
    4 rolled), OneLeg 1.0 (3 rolled), Squat 0.7 (10 forward to 3: fully upright left FingerUp's centre of mass 1.0 cm
    inside the feet, at the limit); Kneel's chest is already upright; Sit keeps its 6 degrees back (sitting, the
    lean reads natural and opens the arms).
  - **OneLeg**: the raised knee forward and a little out (6 cm), the foot by the inside of the standing knee (10 cm
    to its side, 14 cm in front); it hung low across the standing shin.
  - **The fist** (q2 only; q3's below) `[90, 60, 20]` (the base knuckle bent most; `[86, 100, 70]` curled the long finger tubes into
    closed rings) and the thumb's base turned in, the rest nearly straight (`Thumb` [40, 10, 0], `ThumbTurn` [20,
    45]): across the front of the curled fingers (the searched thumb hooked into an "O"). q2's flat hand's `spread`
    -10 was meant to draw the fingers together (it did on one hand only; q3's `mirror`, below).
  - **`close_hands_<char>.png`** (`pose_shots.gd`): one hand per arms pose on Stand, front and three-quarter
    (HandsBehindHead from behind), the hand-shape library's judge.
- **p3 q3: the critic's ranking fixed** (a fresh critic ranked the 48 pairs of the q2 build: 11 good, 33 weak, 4
  ugly; variant grids in `anim_bare/poses/p3/q3/`, numbers in `tools/out/poses/p3/q3/`):
  - **Plane level**: one `both` arm, the wings level (`upper` [1.0, -0.4, 0.04]); the old bank (13 degrees, one arm
    up and one down) read as a droop on every legs pose, worst on Sit and Squat (ugly on Sit).
  - **Heart**: the wrists 0.75 hand lengths lower and further forward (`offset` [0.4, 1.3, -0.5]): the heart in front
    of the chest, not at the chin. The `heart` grip: the index curled into the lobes, the other three fingers a fist
    behind it, the thumbs pointing down and in to the tip (a search of 36 turns and curls, `thumb.log`: the straight
    thumbs stood 10 cm apart). Two pinched fists at the chin were ugly on OneLeg and Kneel.
  - **The fist** `[100, 100, 30]`, the thumb `[40, 40, 30]` turned `[30, 60]`: the base and middle knuckles fully
    bent and the thumb over the fingers' front (q2's left a ring and the thumb standing out as a nub).
  - **`spread` mirrored per hand** (`_fingers`): the left hand's sign was the right's, so q2's -10 drew the right
    hand's fingers together and the left's apart (PalmsOut's "claw"). A grip's `mirror = true` makes one sign mean
    together on both hands (`flat`, `behind`: 18; the library is the brief's four shapes and this fifth); a flag, so `--check` still composes older builds' `pose_data.json`
    as built (the first q3 verify went red on s11's right fingers); the test checks the index and little tips mirror.
  - **`behind`**, the HandsBehindHead grip: the flat hand's fingers curled round the skull (`[35, 45, 30]`) and drawn
    together; the back view showed a blob of spread fingers.
  - **The akimbo**: the elbows further back (`elbow` [1.0, -0.7, 0.15]: the akimbo reads from the side), and
    **`legs_variant`** (an arm's settings for one legs pose's variant, on top of `variant`): the fist up the waist's
    side where the thighs rise to it (Squat 1.1, Sit, OneLeg and Kneel 1.0 hand lengths up, was 0.6; Sit's lift
    1.0, 1.15 and 1.3 read 10.9, 13.7 and 16.4 cm, `tools/out/poses/p3/q4/marks.log`): on Sit and
    Squat the fists had landed on the thighs (Sit+HandsOnHips ugly), on OneLeg and Kneel on the raised knee. The
    knuckles stand 10.9 to 12.7 cm from the waist's mark there. q3 set one `mark_cm` 13 for every legs pose; q4
    (review 1: a fist 4 cm up or on the ribs passed on Stand) makes the limit per legs pose: `mark_cm` 9 (Stand 7.1,
    Lunge 6.3) and `legs_mark_cm` Sit, OneLeg and Kneel 12 (10.9), Squat 13.5 (12.7). A contact's own limit wins
    outright over `variant_mark_cm` (it was the larger of the two, 10 cm on Stand's variant).
  - **Flex**: the upper arms more out and the forearms leaning out (`upper` [1.0, 0.45, 0.15], `lower` [0.3, 0.2,
    1.0]): in 3/4 the near fist sat on the cheek.
- **The check composes from the build's own data.** The build writes `build/<char>/pose_data.json` (the TOML as
  solved); `alien_poses_run.py --check` composes the Blender reference from it and prints a `NOTE` when the TOML has
  changed since, so editing the TOML without a rebuild no longer turns verify red (round 2's red verify).
- **Data plus a solver.** `tools/blender/anim_sets/alien_poses.toml` holds the poses (authored directions, contact
  goals on landmarks, grips); `alien_pose_math.py` (no bpy) solves them per character on its own rest skeleton (two-bone
  IK, feet planted flat, the kneeling knee and the seat fitted to the floor, hands touched onto the skin). New bodies
  on the same skeleton: re-run `$PYTHON_BIN tools/blender/alien_poses.py --raw D:/prime-art-raw --step <new> --glb
  --masks` (background, about 25 min for both), then `alien_poses_run.py --step <new> --check --shots`.
- **Measures and limits** (every pair, both characters, `build/<char>/poses.json`): the lowest skin point within
  0.5 cm of the floor; a planted foot without `foot_pitch` flat (its heel's and ball's lowest skin both within 1 cm
  of the floor); the centre of mass at least 1 cm inside the support area for Stand, OneLeg, Squat, Lunge, Kneel;
  skin through skin (`alien_pose_math.through_depth`, the bone tubes as the proxy) at most 1.5 cm, and at most
  0.5 cm for a hand or forearm; a contact's gap at most 1 cm; a hand on a landmark (`mark`: the hip hand of
  HandsOnHips, FingerUp and Salute on the waist's side) has its palm's centre within 6 cm of it (the landmark rides
  on the Spine), so "touching the body" alone (the belly's front) no longer passes. A goal arm's `touch_by` names
  the skin that touches (the palm's bone: the thumb kept off the body).
  - **What the through check reads.** A hand or forearm: its raw depth (its proxy reads 0.0 cm on the rest skin),
    counted only where its skin is within `TOUCH_CM` (0.5 cm) of the other group's (round 3): a depth with a skin
    gap is the tube's bulge beyond the skin (HandsBehindHead's hands read 0.5-0.7 cm into the skull's tube with a
    1 cm gap to its skin) and goes into `proxy_cm` instead. `proxy_cm` has its own limit, `proxy_hand_cm` (1.5 cm;
    s11 at most 0.74): a hand deep in a volume with no vertex of its skin near reads there and fails (review 3;
    test `test_a_hand_pushed_into_the_head_fails`: a hand 3 cm deeper into the skull fails either way).
    **Not measured** (`through_pairs`): an arm into a shin, an upper arm into its thigh, a hand or forearm into the
    other side's thigh (Flex, Heart, Plane over Squat, Sit, Kneel); these are judged on the close-ups (review 3).
    A one-off sweep of those pairs over Squat, Sit and Kneel with all eight arms on both characters (s11's dumps)
    read at most 0.27 cm (the hip hand on Sit's thigh touching the shin by the knee), nothing over a limit.
    A thigh (beyond its groin's 30 %), an upper arm (its elbow half) and a shin (beyond its knee's 30 %: the knee's
    back folds into the thigh's end in every bent knee, 3.2-5.8 cm there and 0 beyond on all six legs poses, s5's
    calibration): only the depth beyond the same point's at rest, so the groin, armpit and knee skin the tubes share at rest reads 0 and a thigh pressed into the
    belly (Squat, Sit, Kneel's front leg) or a calf into its thigh (`shin>thigh`) reads what it adds. Into a thigh
    the hip third is skipped (the buttock skin skinning folds into the pelvis; a hand there is the torso's check).
    A thigh into the torso reads the belly's tubes (Spine and up), not the Hips tube: the pelvis is the thigh's own
    joint, and its flare read 5.4 cm on OneLeg's straight standing leg and 4.5 cm on Kneel's (s5).
    `proxy_rest_cm` in `poses.json` is this same check on the rest pose. It reads 0.0 everywhere (the thighs, upper
    arms and shins by construction, the hands and forearms because no hand is near a body in the rest T pose), so it
    says nothing about the proxy's error where a hand touches: the evidence for that is the slice count below.
  - **The hip hand was really inside** (the fix round's measure, not the proxy): its 2.3 cm into the torso grew to
    3.1 and 3.2 cm with 16 and 32 tube slices instead of 8: the curled fingers inside the waist, the palm's skin
    0.24 cm off it (the touch solve reads the palm's bone, `touch_by`). Round 2 (s6 grid, plain Python on the s5
    dumps): the fingers turned out with the belly (`fingers_dir` [0.5, 0.8, -0.4]) and the palm 0.8 cm off the
    waist take it to 0.44 cm on Stand, the contact 0.94 cm, the palm's centre 5.7 cm from the waist mark (so
    `mark_cm` 6). Round 2, s7 (a Blender close-up grid of five grips, `tools/out/poses/s7/grid1`, `grid2`): s6's
    turned-out fingers read as a limp hand hanging off the waist, so the hand now lies on the waist's side with the
    fingers forward and a little down (`fingers_dir` [0.1, 0.9, -0.45], the palm 0.5 cm off, the elbow wide [1,
    -0.6, 0]): the palm's centre 4.0 cm from the mark on Stand, but the fingertips meet the belly's forward bulge
    (hand>torso about 1.9 cm, the same with 16 and 24 tube slices: real, not the proxy). Every grip that kept the
    fingers forward read 1.9 to 5.8 cm; a grip that cleared it hung off the waist. The pictures were judged better
    than the number; the number stays a reported failure.
    Review 2 (fix2, plain-Python grid on the s5 dumps, `fingers_dir` x `curl` x `gap_cm`): the curl changes nothing;
    the fingers turned out with the belly's curve, `fingers_dir` [0.6, 0.7, -0.35] (about 40 degrees out from
    straight forward, still pointing forward and down), take Stand's hand>torso from 1.94 cm to under 0.3 (no
    failure), the palm 5.0 cm from the mark, the contact 0.55 cm; Lunge then needs no variant. The variants keep
    `clear_dir` [0, -1, 0.2] and their level fingers: OneLeg about 1.2 cm into the belly, Kneel within the limits,
    Squat (about 4 cm in, the palm 12 cm from the mark) and Sit (the hand on the thigh, 13-15 cm from the mark) were
    failures; no grip or clear direction tried put Squat's or Sit's hand on the hip. Round 3 rests it on the thigh
    instead (above; grid on the s7 dumps, `along` x `fingers_add` x `elbow`, both characters read alike: the same
    body): Squat and Sit then clear the thigh and the torso, the gap to the thigh 0.2 to 0.4 cm.
    s11 (critic 3: the hand limp, the fingers dangling off the waist; plain-Python grid on the s10 dumps, with
    the middle fingertip's gap to the torso and the wrist's bend as measures): the
    curl does change the look, if not the through: `grips.hip` [36, 46, 32] (was [8, 10, 6]) wraps the fingers
    round the waist, the fingertip 5.2 cm off it (was 11.3), no through; turning `fingers_dir` forward instead put
    the hand 1.1 to 4.1 cm into the belly. The elbows back (`elbow` [0.8, -1.3, 0], was [1, -0.6, 0]) straighten the
    wrist (the hand to the forearm 67 degrees, was 89) and part the side outline from Salute's. The palm stays about
    5 cm from the waist's mark: the palm's centre sits inside the hand, 1.5 to 2 cm off its skin, and a higher or
    lower wrist read 5.4 to 7.5 cm (the mark limit stays 6 cm).
    p1 (the manager: the s11 wrap read as small fists beside the hips from the front; Blender grid of curl x
    `fingers_dir` on the s11 dumps, `tools/out/poses/p1/grid`): the curl again changes no number; the fingers turned
    down ([0.4, 0.7, -0.6]) put the palm flat on the waist's side, fingers together and forward-down, with a slight
    curl (`grips.hip` [14, 18, 12], no spread), but at `gap_cm` 0.5 went 1.3 cm into the waist ([0.25, 0.6, -0.75]:
    2.0); at 1.5 cm off the skin Stand reads no through, the contact 0.8 cm, the mark 5.3 cm (2.5 cm: the mark 6.3,
    a failure). The thumb is not behind the waist yet: its curl turns it about one axis only.
    p2 (the review of #342: p1's grid tested Stand only, and its build failed three Lunge pairs on both
    characters): Lunge's HandsOnHips is a per-legs variant (the shared clip's hand goes into the front thigh), at
    `variant.gap_cm` 0.5 its hands 0.68 and 0.84 cm into the waist. A grid of the variants' gap on both p1 dumps,
    front and three-quarter close-ups of Lunge+HandsOnHips (`tools/out/poses/p2/grid`): 0.5 through 0.68/0.84,
    0.8 through 0.37/0.40 (contact 0.46/0.37), 1.0 no through (contact 0.63), 1.2 a 1.03 cm gap; the close-ups
    differ by millimetres. Kept: 0.8, the value checked on every legs pose (the other variants' waist side, OneLeg's
    left and Kneel's right hand, reads 0.81). FingerUp's and Salute's hip hand has no Lunge variant: at `gap_cm`
    1.5 the shared clip reads a 1.06 cm gap on Lunge (the limit 1.0). 1.4 passes every legs pose (Stand 0.83,
    Lunge 0.97, OneLeg 0.78); 1.3 goes 0.54 cm into the waist on OneLeg and 1.45 reads 1.02 on Lunge, a narrow
    window that a change to this hand must re-measure on Lunge and OneLeg.
- **The back of the skull** (`head_back`, round 2, s7): the landmark is the head's back at HEAD_BACK_UP (0.6) of the
  way from the Head bone up to the eyes, not at the eyes' height: there the chameleon's crest put the wrists 32 cm
  behind the head and the arms nearly straight, the elbows forward along the face ("head in hands"). At the skull
  the wrists sit 0.34 m from the shoulder of a 0.49 m arm, so the elbow pole (`elbow` [1, -0.6, 0.2]) takes the
  elbows out to the sides. Round 3 (s7's front read "hands over the ears": the elbows at neck height, the forearms
  rising by the cheeks): with the wrists at the skull's back the arm's reach leaves the elbow nowhere to go by its
  pole (grid: three poles moved it under 1 cm), so the shoulders shrug up (`shoulder` [0, -30, 0]): the chameleon's
  elbows 7 cm under the eyes (were 14), 27 cm out, 6 cm behind the Head bone, the hands 0.5 cm into the skull at
  most; the wrists higher went into the crest (2 to 12 cm). **Per-character settings**: a `[chars.<char>]` table in
  the TOML is merged over the shared data for that character (`alien_pose_math.for_char`; the drivers pass the
  character); the axolotl's wider, lower-eyed head takes the wrists further out and back, a smaller shrug and the
  elbow pole back (`[chars.axolotl.arms.HandsBehindHead.both]`: its forearms otherwise cut the head 3 to 5 cm).
- **PalmsOut** (round 3: s7's hands beside the head, fingers spread, read "hands up"): FK with the elbows bent
  and low, the forearms up and forward, the wrists at about the shoulders' height, the palms to the camera and the
  `palm` grip (fingers together, a soft curl). s11: the arms further forward (`upper` [0.6, 0.6, -0.6], `lower`
  [0.25, 0.7, 0.7]; s10's [0.65, 0.35, -0.7] / [0.3, 0.45, 0.85]) so the side outline parts from Heart's.
- **Sit** (round 3: the thighs' front 2.99 cm into the belly): the pelvis rolled back 10 degrees (was 4) and the
  feet 0.92 leg forward (was 0.78): the knees 7 cm lower, the head 5 cm behind the hips, thigh>torso 1.28 cm.
- **The Heart** (s7): the hands one hand length in front of the chest's front (`offset` fwd 1.0, was 1.9: from the
  side the arms read straight out, a sleepwalker), the elbows out and down ([1, -0.3, -0.3]), so the front outline
  has its elbow wings and the side view stays compact. s11 (critic 3: a guard from the side): the elbows lifted to
  about the hands' height ([1, -0.1, 0.05]). p1 (the manager: from the front a flat T; a grid of five elbows on both
  characters, front, left and three-quarter): the elbows down and out ([1, -0.2, -0.6]), the forearms rising to the
  hands as in the reference; [0.6, -0.1, -1.0] (the elbows at the sides) read as a boxer's guard from the side.
  Flex's upper arms go more forward ([0.9, 0.7, 0.12]) and Salute's elbow clearly forward ([0.5, 1.2, -0.1]): the
  side outlines apart (the table below).
  - **The layers' limit.** The arms are solved once over `reference_legs` (Stand), so an arm cannot make room for
    a raised thigh: the shared hip hand goes 7 to 8 cm into it on Sit, Squat and Kneel's front leg, OneLeg's raised
    one included, on every offset and finger direction tried (`tools/out/poses/fix/hipgrid_c.log`, s5's six
    grips): hence the per-legs variants above.
- **The silhouette table** (`silhouettes_<char>.json`): per facing (front, left, right, back), for pairs that differ
  only in the legs or only in the arms, 1 - IoU of the outlines from one camera fixed on the Root's ground spot (not
  re-aligned per pose: where Sit, Kneel and Lunge move the feet and hips, a legs difference includes that shift); the least over the other part
  is what the photographer can still tell apart. Below 0.10 is a finding. The table is measured on Blender workbench
  masks (lens 100 mm, one fixed frame for every pair); the review pictures are Godot renders whose camera centre
  follows each pose (`pose_shots.gd`): the numbers and the pictures' outlines are not the same camera. Left vs
  mirrored right: orthographically a left outline is the mirror of the right one, so only perspective and the
  pose's own lopsidedness separate them; measured in s11 (chameleon / axolotl), 0.066 / 0.085 on the least lopsided
  pairs (Stand+Salute, Stand+FingerUp) and up to 0.33 / 0.38 (Kneel+Plane). The TOML's `lopsided` list only labels
  these pairs in the table; **it is not a check**, nothing fails on it, and a limit would not separate the lists
  (the unlisted Squat+Plane, its banked arms, reads 0.18 / 0.21): that line of the table is informative, not a goal.
  s11's table (both characters): every arms pair 0.10 or more apart from the front and the back (the least 0.108
  chameleon, 0.116 axolotl); from the sides the least are HandsOnHips/Salute 0.061 left (on Squat, where both near
  hands rest on the thigh and the saluting hand is behind the head) and HandsOnHips/HandsBehindHead 0.079 right
  (chameleon; s10: 0.054 and 0.061), Flex/Salute 0.089 left and nothing under 0.10 right (axolotl). From a side only
  the near arm and what stands out past the body read: two poses with the same near arm (the hip hand) differ only
  by the far hand. **A note to the design, not a rule** (round 3): the weakest arms pairs as the two sides of one
  outline seen from the left or right (under 0.10 in s11's chameleon table): (HandsOnHips, Salute), (HandsOnHips,
  HandsBehindHead), (HandsOnHips, Plane), (Flex, Salute), (Plane, HandsBehindHead), (Heart, HandsBehindHead), (Flex,
  Heart); a silhouette list may prefer the front or back for them. The game avoids no pair and no facing: every one
  of the 48 pairs is meant to look good (round 3); legs: Stand/OneLeg from the sides (0.21 to 0.26) is fine; the hip
  hand on Squat, Sit and the raised thigh of OneLeg and Kneel rests on the thigh (above).
- **What the layers freeze.** `owner()` gives every bone that is not the legs' to the arms, so the arms clip keys
  Jaw, the eyes and the crest at rest and the game's `Blend2` filter takes the whole Chest subtree: a face or crest
  layer of the game must sit after the pose's tree (or the pose's arms filter must drop those bones) to move during
  a pose.
- **The GLB.** On top of `loco/f3`'s `<char>_char.blend`: the 37 f3 clips unchanged (F-curve hash and GLB key bytes,
  `clips_proof.json`), 24 pose clips added (14 poses, 10 hip-hand variants). `godot-check --profile alien --strict-contract --textured` passes:
  `held_poses_hold` checks that the `PoseLegs_`/`PoseArms_` clips keep every bone still (they are exempt from
  `animations_move`).
- **The game side.** `godot/alien/pose_layers.gd` (the reference the game copies): an `AnimationTree` beside the
  character's `AnimationPlayer` with one `Blend2` (legs in, arms blend, the filter on `Chest` and its descendants,
  amount 1); `play_pair(legs, arms)`, `stop()`. `godot/alien/pose_layers_check.gd` (`alien_poses_run.py --check`,
  test `test_alien_poses_godot`): all 48 pairs within 0.0002 cm of the Blender-composed pose (tolerance 0.5 cm), and
  every bone's world turn from its rest within 0.5 degrees of the reference's (`max_err_deg` 0.0 is float32
  `get_angle`'s floor, about 0.04 degrees, not a proof of identical keys; `turns`: pose * rest^-1 in glTF axes,
  free of how the exporter orients the bones' own axes; a leaf's roll keeps its head in place, round 1's minor 8), held
  (0 cm after 0.7 s), `stop()` gives the skeleton back. The game's rules: the pose holds while the player stands;
  turning on the spot keeps it (the node turns, the clips stay); a step drops it (`stop()`, then locomotion).
- **The head look during a pose** (measured at yaw +-70, the contact in its target bone's frame, cm, chameleon /
  axolotl; s11's `layers_<char>.json`): with head_look.gd's defaults (yaw into Spine, Chest, UpperChest too) the
  hands on the hips slide 10.9 to 11.8 (both), the hands behind the head 9.6 to 10.0 / 9.6 to 10.6, the salute's
  fingertip 12.1 / 10.1; with only Neck and Head turning (0.4 / 0.6) the hip hands stay (0.0) but the head leaves the
  hands behind it (20.6 to 21.4 / 20.5 to 22.6) and the salute's fingertip (24.8 to 25.5 / 20.5 to 21.1). `OneLeg+Plane LeftHand~Hips` in
  `pose_layers_check.gd`'s list is a control, not a contact: a free hand, it slides 43.6 cm at the default split and
  0 with Neck and Head only, so the probe is shown to read a slide. The heart's
  fingertips never part (0.0). **Recommendation:** during a pose the game sets the head look's split to Neck and Head
  only (its defaults stay for locomotion), and for HandsBehindHead it turns the look off (the Salute, measured
  above, is gone since p3)
  (`influence = 0`): the outline the photographer matches is the pose's own.

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
| `tm:<clip>`, `tm_own:<clip>` | (art #33) a Meshy text-to-motion clip retargeted from SMPL-H, named by its batch item id; `tm_own:` plays it on SMPL-H's own mannequin ("Text to motion: the SMPL-H retarget" above) |
| `<set>:<clip>` | (art #33) a clip of an animation set (`mvp:Jog_Fwd_Loop`), built in the review's process from the set's settings ("Animation sets" above); the settings' `[sets]` names the sets |
| `<base>\|<upper>` | a **layered** clip: the base clip's hips and legs under the upper clip's `[layer] upper` bone (`Torso`) and every bone below it (spine, head, arms, fingers), the way an engine layers an upper-body clip with a bone filter; the upper clip is time-scaled to a whole number of its loops per base loop |
| `blend:<A>+<B>` | (rates only) a cycle-synced blend of two library clips; a name without a source is UAL1's; `\|<upper>` adds an upper-body layer, one upper loop per stride, lined up on the left heel strike |

A library entry may also take (art #25, `tools/blender/anim_libs.py`): `extra` (more GLBs on the same rig whose
actions join it; the load fails when a rest head differs by more than 1 mm), `rename` (action -> clip name), `skip`
(actions left out), `in_place` (clips whose hips' horizontal travel from the first to the last frame is taken out in
proportion to time), `own` (the character name of `<library>_own:` clips), `format` (`glb`, the default, or
`smplh_fbx` with a `clips` table of name = raw-relative FBX, art #33: "Text to motion" above); `rm` is needed only on
UAL's rig. A pair
or a `[[feet]]` row may keep to one body type (`body`); a `[[feet]]` row's `sets` are lists of any clip keys shown top
to bottom (a lane per key: the strip spans each clip's own length), its `clips` the rigid shoes over the toe bones as
before. The shoes in the close-ups are the vertices weighted most to a foot or a toe, so a merged mesh works.

`--sources ual2` (comma-separated; `pack`, `ual`, `ual2`, `meshy`, `meshyw`, `tm`, or a set such as `mvp`; a variant counts as its library) limits `clips` to those sources' clips and `pairs` and `rates`
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
