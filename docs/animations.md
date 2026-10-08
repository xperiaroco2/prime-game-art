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
| Meshy text to motion (art #25's crawl, art #33's batch 5, private raw files): `tm`, eight FBX clips, one per file | 8 clips | SMPL-H, 52 bones with fingers, retargeted with `smpl_um.toml` ("Text to motion") | owned output of the Pro plan (`public_repo_ok = true`, `ai_generated = true`) | [`batches/2026-10-b4-animations.toml`](../batches/2026-10-b4-animations.toml), [`batches/2026-10-b5-anim-mvp.toml`](../batches/2026-10-b5-anim-mvp.toml) |

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

## Clip edits (art #33)

The clip edits turn a retargeted clip into one the game can play: they cut a loop at its best seam, take the travel
out, straighten the heading, rescale a turn, trim, retime, reverse, mirror left and right, warp the stride to a speed
with the feet planted, lift a clip out of the floor, turn the arms out of the legs or the hands apart, hold a box by its sides, and lean
the upper body forward. The code is in two modules:

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
| `arm_offset` | `abduct_deg` (a number or `"auto"`), `max_deg` (12), `margin_cm` (0.3) | turns each upper arm away from the body about the chest's forward axis at the shoulder joint, by one angle on every frame (only UpperArm's basis changes, so the arm below follows). `auto` finds the smallest angle (bisection to 0.5 degrees) at which no hand vertex is inside the legs (`hands_in_legs`), on the frames that were inside and their neighbours, then adds the angle that moves the hand `margin_cm` further | deg, found, hands_in_legs before and after (cm), frames in the legs before and after |
| `hand_spacing` | `min_gap_cm` or `gap_m`; `at` = all, end or mean; `deg` (a number or `"auto"`); `max_deg` (25) | turns each upper arm about the world vertical at its shoulder, the hands moving apart symmetrically (a negative angle brings them together). `min_gap_cm`: no hand inside the other and at least that gap between their closest vertices (on every frame, at the end, or on average). `gap_m`: the closest distance between the two hands' vertices at `at` (all: the smallest) reaches the gap, searched in [-max_deg, max_deg] | deg, found, gap before and after (cm), hands_in_each_other before and after (cm), min_gap_after_cm |
| `side_grip` (art #65) | `gap_m`; `tilt_deg` (0), `forearm_share` (0.5), `from_s` (0), `fade_s` (0), `max_deg` (40), `tol_cm` (0.3) | both hands hold a box by its sides, on every frame from `from_s` (faded in by a smoothstep over the `fade_s` before it): each upper arm turns at the shoulder about the axis across its shoulder-wrist line and the line from the other wrist (the hand moves straight away from the other: about the vertical for arms held forward, out to the side for hanging ones), by one angle for both found per frame by a secant search, so the closest distance between the hands' vertices is `gap_m` (within `tol_cm`); then each palm faces the other hand: the forearm rolls about the elbow-wrist line by `forearm_share` of the roll that points the palm (`anim_edit_math.palm_normal`: the wrist, the middle, index and pinky knuckles) at the horizontal line to the other wrist turned up by `tilt_deg` (`grip_goal`, `roll_angle`), and the hand turns at the wrist by the shortest turn that finishes it (a bent wrist cannot face it by a roll alone) | frames, frames_full, not_found, deg, gap_before_cm and gap_after_cm, hands_in_each_other_after_cm, hands_in_torso_before_cm and after, roll_deg, palm_up_before_deg and after (the palm normal's angle over the horizontal), palm_aim_err_deg, hand_height_m, hand_height_diff_cm, hand_forward_m (each min, mean, max over the full-weight frames), first and last (frame 0 at full weight and the last frame: gap_cm, deg, w, hand_height_m and hand_forward_m per hand), hands_lowest_s and hands_lowest_m |
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
  idle then a second `arm_offset`, found by `auto` on the open hands (they are longer than fists: 2.9 cm in the
  thighs to 0 at 4.16 degrees; 0 on the men and on both bodies' talk) and pinned. The eight one-shots that start or
  end in the idle pose end with `idle_ends`; Pickup_Package with `idle_ends {at = "both", upper = false}` (both ends
  meet the idle's legs: the carry plays over the idle; both feet only shuffle between them, so they are held), which
  Putdown_Package, its reverse, carries; Getup_Back with `match = "root"`. Putdown_One is
  made from its source with the pickup's steps reversed, not `from = "Pickup_One"`, which would blend the idle into it
  twice. Carry_Upper_Loop and Push_Upper_Loop are left alone: they play over the edited idle (art #65 gives the carry
  nearly straight fingers by `hands_relax`, for its side grip).

### The pure and the Blender side

| `anim_edit_math.py` (stdlib) | `anim_edit.py` (Blender) |
|---|---|
| `OPS`, `check_steps`, `params`; time maps (`trim_times`, `retime_count`, `retime_times`, `split_index`, `catmull_rom`, `neighbours`); quaternions (`q_mul`, `q_conj`, `q_slerp`, `q_hemi`, `q_axis_angle`, `q_rotate`); `best_cycle`, `central_diff`, `close_vectors`, `close_quats`; `linear_drift`, `moving_average`, `path_offsets`, `moving_speed`; `lsq_direction`, `yaw_of`, `signed_angle_2d`, `facing_yaw`, `unwrap`, `circular_mean`, `turn_correction`; `contact_mask`, `contact_windows`, `contact_velocities`, `ground_velocity`, `natural_cadence`, `stride_rate`, `stride_scale`, `stride_fit`, `scale_offset`, `plant`; `two_bone_ik`; `floor_profile`; `search_angle`, `secant`; the side grip (art #65): `palm_normal`, `grip_goal`, `roll_angle`, `grip_weights`, `spread`; `mirror_name`, `mirror_pairs`, `mirror_correction`, `mirror_pose` (4x4 lists); the relaxed idle (art #49): `RELAX_OPS`, `FINGER_SEGMENTS`, `curl_errors`, `from_clips`, `smoothstep`, `finger_curls`, `curl_goal`, `stance_targets`, `stance_lift`, `pitch_of`, `head_fix`, `yaw_out`, `knees_out`, `reach_lift`, `planted_until`, `AIR_M`, `KEEP_PLACE`, `idle_end_weights`, `end_mix` | `Frames`, `Target`, `apply`, `EditError`, `OPS` (op name to function); Root and Body moves in world space; the leg IK as rotations; the mirror with mathutils; the posed-mesh measures (the lowest vertex through `anim_metrics.world_points`, the hands through `anim_metrics.Measure`'s sets and surfaces); the relaxed idle's ops on an `_Pose` in world space, `feet_numbers` |

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
| `export` | `false` for a review candidate that is built, but not written to the GLB |
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
