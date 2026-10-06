# Clip edits (art #33)

The clip edits turn a retargeted clip into one the game can play: they cut a loop at its best seam, take the travel
out, straighten the heading, rescale a turn, trim, retime, reverse, mirror left and right, warp the stride to a speed
with the feet planted, lift a clip out of the floor, and turn the arms out of the legs or the hands apart. The code is
in two modules:

- `tools/blender/anim_edit_math.py`: the pure math (standard library only), with unit tests in
  `tools/tests/test_anim_edit_math.py`;
- `tools/blender/anim_edit.py`: the Blender side, with tests on the real pack and UAL clips in
  `tools/tests/test_anim_edit_blender.py` (skipped without Blender or the raw files).

The animation set (`anim-set`, `tools/blender/anim_sets/`) runs the edits from a settings file; this page describes the
edits themselves. It is to be folded into `docs/animations.md` as "Clip edits".

## The model

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

### Rig facts the edits rely on

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

## The ops

A settings file gives each clip a list of steps, `{op = "...", ...}`; any step may add `body = "men"` or `"women"`
and is then skipped on the other body type. Times are seconds in the clip as it stands at that step.
`anim_edit_math.check_steps(steps)` returns the errors of a list of steps (the runner and the tests share it);
`anim_edit_math.OPS` is the schema (each parameter's type, whether it is required, and its default).

| op | Parameters | What it does | Reports |
|---|---|---|---|
| `trim` | `start_s` (0), `end_s` (omitted: to the end) | keeps [start, end], a whole number of frames resampled from start; the result is not a closed loop | frames, seconds |
| `retime` | exactly one of `seconds`, `rate`, `speed_m_s`; `natural_m_s` | resamples to a new length, rounded to whole frames (a closed loop stays closed: its period scales). For `speed_m_s` the rate is speed / natural, where natural is `natural_m_s`, else the travel speed an earlier `cycle`, `in_place` or `stride` step measured, else the feet's in-place ground speed | rate, rate_eff, seconds, frames, natural_m_s and natural_from |
| `reverse` | none | the frames in reverse order | none |
| `cycle` | `min_s`, `max_s`, `within` = [a_s, b_s], `max_raw_seam_deg` (15) | picks the frame pair (i, j) whose poses differ least (2.1 below), cuts i..j and closes the loop: each channel's residual (frame j against frame i) is spread linearly over the cycle, rotations by slerp, so the last frame equals the first and the travel is taken out linearly. Fails when the raw seam of the body bones at the best pair exceeds `max_raw_seam_deg` | i_s, j_s, cycle_s, raw_seam_deg and its bone, finger_seam_deg, cost, travel_m, speed_m_s, yaw_drift_deg |
| `in_place` | `mode` = `linear` or `path`, `smooth_s` (0.6) | takes the Body's horizontal travel out by moving Root. `linear`: first to last in proportion to time. `path`: the Body's path low-passed by a centred moving average of `smooth_s` (its ends extended by point reflection), so a one-shot keeps its sway and stays over its start | travel_m, speed_m_s (the moving part), max_offset_m, travel_after_m |
| `heading` | `travel` = forward, back, left or right; or `facing` = start, end or mean | one constant turn about the world vertical through the first frame's Body. `travel` puts the least-squares direction of the Body's path on that axis; `facing` puts the Body's facing at the start, the end or on average on -Y | turned_deg, travel_dir_deg (before and after), facing_mean_deg, crab_deg (facing against travel) |
| `turn` | `total_deg` | rescales the clip's own turn: each frame turns Root about the Body's vertical by (total / net - 1)(yaw(t) - yaw(0)), so the planted feet turn in place | net_before_deg, net_after_deg, peak_before_deg |
| `mirror` | none | left-right mirror (2.3) | rest_error_mm, rest_error_deg, asymmetry_mm |
| `stride` | `speed_m_s`; `cadence` (steps/s) or `rate`; `plant` (true); `natural_m_s`; `warn` ([0.6, 1.6]); `fail` ([0.4, 2.5]) | stride warping of an in-place loop (2.2) | rate, scale, natural_m_s, natural_cadence, cadence, step_m, cycle_s, ground_axis, ik_miss_contact_mm, ik_miss_mm, knee_past_straight_deg, fit (ok, warn, fail), ground_speed_after_m_s, slide_mean_cm_s, slide_max_cm_s |
| `floor` | `mode` = `lift` or `hips`, `from_s` (0), `to_s` (the end), `fade_s` (0.2), `min_depth_cm` (0.3) | per frame, the posed meshes' lowest vertex below the floor (deeper than `min_depth_cm`) inside the window gives a lift profile: a running max over +-2 frames, smoothed over +-2 frames, held at the window's edges and faded to 0 over `fade_s` outside it. `lift` moves Root (everything: lying, crawling). `hips` moves Body and re-solves the legs to their feet, up to three rounds; it measures without the shoes, which a lift of the hips cannot move | lowest_before_cm, lowest_after_cm, max_lift_cm, window_s; for `hips` also shoes_lowest_after_cm |
| `arm_offset` | `abduct_deg` (a number or `"auto"`), `max_deg` (12), `margin_cm` (0.3) | turns each upper arm away from the body about the chest's forward axis at the shoulder joint, by one angle on every frame (only UpperArm's basis changes, so the arm below follows). `auto` finds the smallest angle (bisection to 0.5 degrees) at which no hand vertex is inside the legs (`hands_in_legs`), on the frames that were inside and their neighbours, then adds the angle that moves the hand `margin_cm` further | deg, found, hands_in_legs before and after (cm), frames in the legs before and after |
| `hand_spacing` | `min_gap_cm` or `gap_m`; `at` = all, end or mean; `deg` (a number or `"auto"`); `max_deg` (25) | turns each upper arm about the world vertical at its shoulder, the hands moving apart symmetrically (a negative angle brings them together). `min_gap_cm`: no hand inside the other and at least that gap between their closest vertices (on every frame, at the end, or on average). `gap_m`: the closest distance between the two hands' vertices at `at` (all: the smallest) reaches the gap, searched in [-max_deg, max_deg] | deg, found, gap before and after (cm), hands_in_each_other before and after (cm), min_gap_after_cm |

Steps raise `anim_edit.EditError` on a failure (an unknown op, a bad parameter, a window outside the clip, a cycle
whose raw seam is too large, a stride on a clip that is not an in-place loop); `apply` names the failing step. A
stride's `fit` of `warn` or `fail` is reported, not raised.

### 2.1 The cycle cut

Each frame gives a feature vector: every non-finger bone's local quaternion (on the first frame's hemisphere, times 2:
about radians), the Body's height and each foot's position relative to the Body (both over 0.2 m, so 20 cm count like
a radian). `best_cycle` minimises the squared feature distance plus that of the velocities (central differences over
0.1 s) over the pairs i < j inside `within` with j - i between `min_s` and `max_s`. The raw seam (the largest body
bone rotation between frame j and frame i) guards the closing: closing spreads any residual, so without the guard it
would hide a bad cut.

### 2.2 Stride warping

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

### 2.3 The mirror

- **Pairs:** `X.L` and `X.R` swap (arms, fingers, legs, feet, toes, poles); the centre bones map to themselves.
- **Reflection:** `S = rig.Wi @ diag(-1, 1, 1, 1) @ rig.W` reflects world X in armature space (computed, not assumed).
- **Formula:** `P'[b] = S @ P[m(b)] @ C[b]`, with the constant correction `C[b] = (S @ rest[m(b)])^-1 @ rest[b]` from
  the rest.
- **Properties:** it assumes nothing about bone rolls; it is exact at rest by construction; `P'` is a proper rotation
  (det +1); mirroring twice gives the pose back (`S S = I`, `C[m(b)] C[b] = I`).
- Bones that never move (their basis location stays within 0.1 mm on both sides) keep their rest offset: the rig's
  small asymmetry (0.06 mm on the Walk, 0.3 mm on Punch_Right) is reported as `asymmetry_mm`, not keyed.

### Resampling

Trim, retime and stride sample frames at fractional times by a Catmull-Rom spline through the four neighbouring frames
(wrapped over a closed loop's seam): locations and scales per component, rotations on the quaternion components
aligned to one hemisphere and normalised. A UAL Walk_Loop retimed to 1.25x and back stays within 0.02 degrees on the
upper body and 1.3 degrees on the legs (the IK bends sharply at a foot plant); the toe bones flick up to 28 degrees a
frame where the retarget's floor clamp lifts them, which no resampling keeps (5 degrees after the round trip).

## The pure and the Blender side

| `anim_edit_math.py` (stdlib) | `anim_edit.py` (Blender) |
|---|---|
| `OPS`, `check_steps`, `params`; time maps (`trim_times`, `retime_count`, `retime_times`, `split_index`, `catmull_rom`, `neighbours`); quaternions (`q_mul`, `q_conj`, `q_slerp`, `q_hemi`, `q_axis_angle`, `q_rotate`); `best_cycle`, `central_diff`, `close_vectors`, `close_quats`; `linear_drift`, `moving_average`, `path_offsets`, `moving_speed`; `lsq_direction`, `yaw_of`, `signed_angle_2d`, `facing_yaw`, `unwrap`, `circular_mean`, `turn_correction`; `contact_mask`, `contact_windows`, `contact_velocities`, `ground_velocity`, `natural_cadence`, `stride_rate`, `stride_scale`, `stride_fit`, `scale_offset`, `plant`; `two_bone_ik`; `floor_profile`; `search_angle`; `mirror_name`, `mirror_pairs`, `mirror_correction`, `mirror_pose` (4x4 lists) | `Frames`, `Target`, `apply`, `EditError`, `OPS` (op name to function); Root and Body moves in world space; the leg IK as rotations; the mirror with mathutils; the posed-mesh measures (the lowest vertex through `anim_metrics.world_points`, the hands through `anim_metrics.Measure`'s sets and surfaces) |

## The API

```python
import anim_edit as ae

target = ae.Target(char)          # char: rc.load_glb(...) of the donor, after rc.add_toes(char)
frames = ae.Frames.from_action(action, target.rig, loop=True)   # or Frames.from_sampler(sampler, rig, loop)
out = ae.apply(frames, steps, target, "women")   # steps: a list of {op = ..., ...}; raises ae.EditError
out.info["steps"]                 # one report per step, {"op": ..., ...}; skipped steps {"op", "skipped": "body men"}
out.to_action(char["arm"], "Idle_Loop")
target.upper_bones()              # the upper-body layer's bones: Torso and every bone below it
```

`Target` exposes `rig`, `legs` (the three bones of each leg), `upper = "Torso"`, `measure` (an
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
edits = [ { op = "arm_offset", abduct_deg = 2.7, body = "women" } ]   # found by "auto": 2.66 degrees

[[clips]]
name = "Knockdown"
source = "ual:Death01"
edits = [ { op = "floor", mode = "lift", from_s = 1.2 }, { op = "trim", start_s = 0.0, end_s = 2.0 },
          { op = "retime", seconds = 1.35 } ]
```

## Measured on the real clips

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
| men, pack Punch_Right: mirror | a left punch; rest error 0.0002 mm |
| men, UAL Jump_Start: trim 0.03-0.40, retime 0.25 | 8 frames, 0.267 s: a retime rounds to whole frames (rate 1.375 for 1.467) |

## Gotchas

- **Auto searches are slow.** `arm_offset` and `hand_spacing` with `auto` pose the meshes and build BVH trees per
  frame and trial angle (20 to 90 s a clip). Pin the found angle in the settings once the review accepts it.
- **A retime rounds to whole frames.** Short clips feel it most (Jump_Start: 0.267 s for 0.25).
- **`retime` by speed after `stride`** uses the stride's speed (the clip then plays at that speed at 1.0x).
- **The pack's 24 fps keys** land between the 30 fps frames: `Frames.from_sampler` reads a pack clip as samples on
  the 30 fps grid, not as its keys.
