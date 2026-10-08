# The relaxed idle in the MVP set (art #49), 2026-10-08

The engineer's notes (2026-10-07): the feet straight, and the idle relaxed. UAL's Idle_Loop, the MVP set's standing
base, turns the right foot 44 degrees out and stands tense: fists, a wide staggered stance, the head down. The lab
worked out a relaxed idle on a copy of the set (round D: `raw:research/2026-10-05-faces/lab/clay_d/clay_idle.py`,
`README_idle.txt`, `raw:research/2026-10-07-clay-d/anim/relax_edit.json`; the final verifier's `repo_edits` in
`raw:manager/stage1/roundd_final.json`). This note records the port into the repo's clip edits
(`tools/blender/anim_edit.py`, docs/animations.md, "The relaxed idle") and the set (`tools/blender/anim_sets/mvp.toml`),
and what it measures.

Everything below was run on 2026-10-08 in background Blender 5.2.2 and Godot 4.7.2 on both body types (the men's donor
`Business Man.glb`, the women's `Suit.glb`, with the toe bones). Outputs, outside git:

- the set: `raw:anim-sets/mvp-49/<body>/` (`anim_mvp_<body>.blend`, `.glb`, `build_report.json`, `godot-check/`); the
  same build with the lab's arm values, for the comparison: `raw:anim-sets/mvp-49-lab-params/<body>/`; the set before,
  as main builds it: `raw:anim-sets/mvp/<body>/` (art #33);
- the review: `raw:review/stage1/49/` (`before/` and `after/`: `anim-review clips` strips, MP4s and measures of the ten
  edited clips and the three layers over the idle; `before_after/`: each strip before over after; `frames/<body>/`:
  Godot's frames of Idle, Pickup_One and Knockdown with the Blender comparison and Idle's clip; `compare/`: the
  joint comparison with the lab's set; `tools/`: the two scripts that made `compare/` and `before_after/`);
- round 2 (the reviews' fixes, "Round 2" below): the set `raw:anim-sets/mvp-49-r5/<body>/`; the review
  `raw:review/stage1/49/after-r5/` (the eight changed one-shots), `before-package/` (main's package clips),
  `before_after_r5/` (main over round 2), `frames-r5/<body>/` (Godot), `compare/r5_vs_lab_<body>.json`; the
  intermediate builds `mvp-49-r2` to `mvp-49-r4` are superseded;
- round 3 ("Round 3" below): the set `raw:anim-sets/mvp-49-r7/<body>/`; the review `raw:review/stage1/49/after-r7/`
  (the nine changed one-shots), `before_after_r7/` (main over round 3), `frames-r7/<body>/` (Godot); `mvp-49-r6`,
  `after-r6/` and `frames-r6/` are a superseded build, still recentred (below).

## Summary

- **The feet.** The right foot turns from 43.66 degrees out to +3.66 (the left stays at -5.68), on every frame of the
  idle and the talk, both bodies. The ankles stay on the feet: the shin's end within 0.003 mm of its IK foot (round C's
  swivel left it 7 to 14 cm off).
- **The stance.** Ankles 47.69 to 27.47 cm apart (men; hip joints 23.47) and 45.37 to 22.85 cm (women; 18.85); the
  right foot's stagger 45.73 to 5.56 cm (men) and 46.46 to 4.46 cm (women). The feet stay planted (0.00 mm of
  travel); the Body rises 2.939 cm (men) and 3.071 cm (women) so the legs keep their extension.
- **The pose.** The shoulders 6 degrees down (the shoulder joint over the clavicle's root 3.51 to 2.91 cm, men; 3.13
  to 2.53, women); the head level (pitch -14.93..-10.46 to -2.22..+2.25 degrees; the talk -17.08..-7.12 to
  -4.25..+5.71); open hands (Middle2 78.0 to 20.0 degrees, Thumb3 86.8 to 12.0; the talk capped at 1.5 times the idle's
  curl, its largest Middle2 78.0 to 30.0), the thumb turned 22.33 (men) and 22.00 degrees (women) in beside the index.
- **The women's arms** (open hands are longer than fists): `arm_offset auto` on the relaxed hands finds **4.16
  degrees** (the hands 2.9 cm in the thighs on all 77 frames to 0), pinned, on top of art #33's 2.66; 0 on the men and
  on both bodies' talk. The lab used 6.0 on both, checked on its w1 only.
- **The port matches the lab.** Built with the lab's arm values, the set's every joint (bone head and tail) is within
  **0.38 mm** of the lab's relaxed set on every frame of all 28 clips, both bodies; the 18 clips neither edits are
  identical (0.0000 mm). The final set differs from it only in the women's arms (the pinned 4.16 against 6.0 on the
  idle and the clips that meet it, none against 6.0 on the talk: the fingertips 8.8 to 22.3 mm).
- **The clips that meet the idle.** At all fourteen touching ends (Pickup_One, Putdown_One, Pickup_Package and
  Putdown_Package both ends; Jump_Start, Knockdown, Raise_In the start; Getup_Back, Jump_Land, Raise_Out the end) both
  feet are **0.000 cm and 0.00 degrees** from the idle's first frame relative to Root, their toes at its bend, and
  (but on the package clips, whose arms keep their hold) the curled fingers at its curl, both bodies. The head, the
  arms and the Body are not matched: the Body stays 0 to 9.8 cm from the idle's (the jump 22.7 to 26.6 cm), the upper
  body up to 68.6 degrees (Jump_Land's left upper arm), so the game's crossfade still moves them.
- **The game's checks pass.** `anim-set` builds, exports and checks both bodies (28 animations, 12 loops LINEAR,
  glTF-Validator 0 errors, godot-check as before: only `facing_plus_z` cannot tell on the pack donor). Godot plays
  Idle, Pickup_One and Knockdown within 0.054 mm of Blender.
- **New measured side effects** (the lab's set has them too): in the pickup and the put-down the hands reach into the
  legs, and Raise_In's kneeling knee goes 0.1 (men) and 0.9 cm (women) deeper into the floor ("Open points").
- **Round 2** (the three fresh reviews): idle_ends no longer slides a planted foot along the floor (Getup_Back's left
  foot, the women's Raise_In) nor sinks one into it (Raise_In, Raise_Out), and the package clips meet the idle's legs
  too (feet and legs only). See "Round 2".
- **Round 3** (the re-reviews): the touching ends are matched in the game's frame, not relative to each clip's Root,
  and the set no longer recentres them away; the package clips hold their feet at the idle's instead of hopping. See
  "Round 3": the Root-relative "0.000 cm" above hid up to 11.8 cm and 19.8 degrees in the game's frame.

## The edits

The ops (docs/animations.md, "The ops" and "The relaxed idle") and their settings in `mvp.toml`:

| Clip | Steps after its art #33 steps |
|---|---|
| Idle_Loop | `foot_turn {bone = "Foot.R", toe_in_deg = 40}`, `stance {out_cm = 2}`, `shoulders {drop_deg = 6}`, `head_level {target_deg = 0, neck_share = 0.4}`, `hands_relax {curl_deg = Index 16/22/12, Middle 20/26/14, Ring 26/30/16, Pinky 32/34/18, Thumb 12/12}`, `thumb_in {beside = "Index3", side_cm = 1.6, max_deg = 40}`, women `arm_offset {abduct_deg = 4.16}` |
| Talk_Upper_Loop | the same without the arm offset; `hands_relax` with `cap = 1.5`; `thumb_in {from_clip = "Idle_Loop"}` |
| Pickup_One, Putdown_One | `idle_ends {at = "both", from_clip = "Idle_Loop"}` (Putdown_One now made from its source: the pickup's steps, reversed) |
| Jump_Start, Knockdown, Raise_In | `idle_ends {at = "start", ...}` |
| Getup_Back, Jump_Land, Raise_Out | `idle_ends {at = "end", ...}` |
| Pickup_Package (round 2) | `idle_ends {at = "both", from_clip = "Idle_Loop", upper = false}`; Putdown_Package, its reverse, carries it |

Each op adds a constant to the clip's own pose on every frame (the breathing, the sway and the talk's nods keep their
motion). Its numbers, from `build_report.json` (men / women):

| Op | Idle | Talk |
|---|---|---|
| foot_turn | right foot +43.66 to +3.66; the leg swivelled -38.7 degrees about its hip-ankle line; ankle gap 0.0033 / 0.0015 mm | the same |
| stance | Body up 2.939 / 3.071 cm; ankle gap 0.001 / 0.0018 mm | Body up 2.944 / 3.077 cm |
| shoulders | 6.0 degrees; the shoulder joint 0.6 cm lower | the same |
| head_level | +12.71 degrees: Neck 5.084, Head 7.626 | +12.822: Neck 5.129, Head 7.693 |
| hands_relax | every joint at its curl | each joint at most 1.5 times its curl |
| thumb_in | 22.33 / 22.00 degrees (the tip 5.99 / 5.78 cm from its goal before) | the idle's turn |
| arm_offset (auto, women) | 4.16 degrees: hands in the thighs 2.9 cm to 0 | 0 (none needed) |

`idle_ends` on the eight clips: the right foot turned 39.8 to 40.2 degrees and moved 23.4 to 24.0 cm (women 24.1 to
24.7), the left moved 20.7 to 21.1 cm (women 22.6 to 23.1); the right thigh's roll matched to the idle's (-21 to -39
degrees); the knees out at most 25 degrees in the deep bends; the Body's lift cut by up to 26.9 mm (Raise_Out, women)
where a leg would not reach.

| Clip | Feet at the touching end | Fade window (frames) |
|---|---|---|
| Pickup_One, Putdown_One | planted all through, both ends | none: the idle's stance all through |
| Jump_Start | planted to frame 1, then faded | 1 to 8 |
| Knockdown | faded as the feet leave | L 15 to 23, R 15 to 23 (women R 14 to 22) |
| Raise_In | the left foot, planted all through (it settles 1.2 / 2.1 cm after the first frame), steps 4 cm high; the right faded | L step 10 to 18, R 2 to 10 (women 3 to 11) |
| Getup_Back | faded in the air, before the foot lands | L 16 to 24, R 31 to 39 |
| Pickup_Package (both ends) | faded and lifted on the step's arc (the feet shuffle 3 to 18 mm a frame, under 2 cm high) | start L 3 to 11, R 2 to 10; end L 0 to 8, R 5 to 13 (women 11 to 19) |
| Jump_Land | held all through (the landing plants on the last frames) | none |
| Raise_Out | the left foot, planted all through, steps 4 cm high; the right faded | L step 0 to 8, R 8 to 16 (women 9 to 17) |

The windows are round 2's. Round 1 counted a foot as planted while it stayed within 1.5 cm of the touching frame, which
faded Getup_Back's creeping left foot along the floor over frames 31 to 39 and the women's settling Raise_In foot over
1 to 9.

## Measured

### The feet, before and after (`raw:review/stage1/49/compare/`, every frame)

Before is the set main builds (art #33); after round 1's set. Yaw out against the aim relative to the rest pose
(degrees, + toe out; the first frame, and the range over the clip): the rest pose's own Foot-to-Toe line is 15.94
degrees out on the men and 10.72 on the women (`feet.rest_yaw_out_deg` in the build report), so the joint line of the
relaxed right foot is about 19.6 / 14.4 degrees out against the aim; the code review's estimate from the foot mesh is
about 8 / 11 degrees. Ankle gap: the largest distance between a shin's end and its IK foot over the clip, measured on
the saved .blend's baked actions (the build report's `feet` measures the unbaked frames and reads up to 0.005 mm
lower). The touching ends themselves are in the next paragraph.

| Clip (men) | Right foot yaw before | after | Ankle gap before (mm) | after |
|---|---|---|---|---|
| Idle_Loop | 43.66 | 3.66 | 0.0068 | 0.003 |
| Talk_Upper_Loop | 43.66 | 3.66 | 0.0067 | 0.0028 |
| Pickup_One | 43.66 | 3.66 | 0.092 | 0.008 |
| Putdown_One | 43.66 | 3.66 | 1.31 | 0.008 |
| Jump_Start | 43.67 (24.3 to 52.1) | 3.66 (3.64 to 28.1) | 7.96 | 0.010 |
| Knockdown | 43.94 (38.2 to 62.0) | 3.66 (3.66 to 62.0) | 5.73 | 2.90 |
| Raise_In | 43.66 (to 142.5, kneeling) | 3.66 (to 142.5) | 2.00 | 0.009 |
| Getup_Back | 20.75 (6.78 to 43.66) | 20.75 (3.10 to 20.75) | 0.0076 | 0.0075 |
| Jump_Land | 46.68 (43.08 to 46.68) | 6.68 (3.08 to 6.68) | 3.54 | 0.008 |
| Raise_Out | 142.45 (43.61 to 142.45) | 142.45 (3.66 to 142.45) | 1.74 | 0.007 |

The women's idle and talk read the same; their one-shots' ranges follow their own motion (Jump_Start 3.22 to 27.33
after; Knockdown's ankle gap 5.84 to 2.84 mm, its largest on frames idle_ends leaves alone). The gaps before are art #33's trims and retimes (resampled IK legs);
idle_ends' IK closes them on every frame it touches.

At the touching ends, before (each clip against main's idle) and after (against the relaxed idle): the feet 0 to 2.19
cm and 0 to 4.4 degrees apart before, 0.000 cm and 0.00 degrees after; the fingers up to 81.7 degrees apart before
(Jump_Start's open hand against the fist), 0.00 after. Against the relaxed idle the unedited clips would have met it
with the right foot 40 degrees and 24 cm off.

### The loops, the layers and the pops

- **Loops closed:** the idle's and the talk's last frame is their first (0.0000 mm, every bone). The step onto the
  first frame is 1.51 (men) and 1.52 (women) median frame steps (before 1.33 and 1.37), which the build warns about
  above 1.5: it is the fingertips, whose open fingers carry the wrist's motion further out; without the fingers it is
  0.94 and 1.05 (before 0.90 and 1.00), the body's own seam. Not a pop.
- **No one-frame pops** in the idle, the talk and the layers. The edited one-shots have the same pops as before, at
  the same frames (art #33's: Jump_Start's 10 / 11 at its first frames, Raise_Out's toe at frame 9, the women's
  Jump_Land foot at frame 0); none is new.
- **The layers over the idle** (`anim-review clips`, `Idle_Loop|Talk_Upper_Loop`, `|Carry_Upper_Loop`,
  `|Push_Upper_Loop`): no hand in the torso, the head, the other hand or the legs, before or after; the lowest vertex
  -0.6 to -0.2 cm (men) and -0.9 to -0.2 cm (women).

### The review's measures (`anim-review clips`, `raw:review/stage1/49/{before,after}/metrics/`)

| Clip | Hands in the legs, cm (men / women), before -> after | Lowest vertex, cm (men / women) | Right knee's largest bend, deg (men) |
|---|---|---|---|
| Idle_Loop | 0 / 0 -> 0 / 0 | -0.6 / -0.9 -> -0.2 / -0.2 | 20.1 -> 15.3 |
| Talk_Upper_Loop | 0 / 0 -> 0 / 0 | -0.5 / -0.8 -> -0.2 / -0.2 | 19.1 -> 14.3 |
| Pickup_One | 0.2 / 2.5 -> **4.8 / 5.7** | -0.3 / -0.5 -> -0.4 / -0.3 | 93.8 -> 61.3 |
| Putdown_One | 0.3 / 3.6 -> **4.9 / 6.0** | -0.3 / -0.5 -> -0.4 / -0.3 | 94.5 -> 62.0 |
| Jump_Start | 0 / 6.7 -> 1.9 / 5.3 | -1.9 / -2.3 -> -1.9 / -2.1 | 110.2 -> 108.4 |
| Jump_Land | 3.6 / 7.5 -> 1.6 / 3.0 | -0.5 / -0.5 -> -0.8 / -1.0 | 125.2 -> 140.1 |
| Knockdown | 0 / 6.1 -> 0 / 2.1 | -0.9 / -0.8 -> -0.4 / -0.3 | 118.0 -> 110.4 |
| Raise_In | 0 / 5.2 -> 0.1 / 6.6 | -6.2 / -5.6 -> -6.6 / -6.5 | 87.2 -> 87.0 |
| Raise_Out | 3.0 / 7.0 -> 2.9 / 7.1 | -4.5 / -3.7 -> -4.5 / -3.7 | 89.3 -> 89.2 |
| Getup_Back | 0 / 2.8 -> 0 / 3.9 | 0.0 -> 0.0 | 110.4 -> 112.8 |

### Against the lab's relaxed set (`compare/`)

`raw:review/stage1/49/tools/compare_sets.py` appends the sets' armatures and actions into one Blender scene (the
donors' rests agree to 0.0 mm; every file's armature is the identity) and compares every bone's head and tail on every
frame:

- **with the lab's arm values** (`mvp-49-lab-params`): every clip within 0.38 mm of the lab's (the largest: men's
  Raise_In, LowerLeg.R at frame 15; the women's Raise_In 0.17, Knockdown 0.22 / 0.24, Raise_Out 0.23 / 0.19,
  everything else under 0.03 mm),
  heads and tails alike; the 18 clips neither set edits 0.0000 mm. In the raise the lab's set leaves its ankle 0.38 mm
  off the foot where the repo's IK closes it to 0.009 mm: the same 0.38 mm at the knee;
- **round 1's final set**: the men's identical to the above; the women's differ by the arm offsets only (the fingertips
  8.8 to 19.0 mm off on the idle and the clips that meet it, 22.3 mm on the talk);
- **round 2** (`compare/r5_vs_lab_<body>.json`): 20 (men) and 16 (women) of the 28 clips within 0.5 mm; the rest
  differ where round 2 fixed the lab's defects (Getup_Back's left foot 21 to 23 cm, Raise_In and Raise_Out 4.4 to 22
  cm, Knockdown's right knee 8.6 cm from a fade one frame later, the package clips, which the lab left alone) and by
  the women's arm offset.

The stance's feet in the build report (`feet_m`) are the clip's positions before the set recentres it on the origin:
the lab's figures (`README_idle.txt`) are the same points after it.

### Godot (`frames/<body>/`)

Godot's frames of Idle, Pickup_One and Knockdown (off-screen window, Vulkan forward+) agree with Blender within 0.022,
0.054 and 0.017 mm (men) and 0.014, 0.054 and 0.017 mm (women) at 64 joints and 128 axis points; Idle's clip is in
`frames/<body>/clips/Idle.mp4`.

## Round 2: the reviews' fixes

Three fresh reviews (code, motion, docs) of round 1 found two majors in idle_ends on frames the touching-end measures
did not check, and the issue's Putdown_Package unmet. Round 2 (the set `mvp-49-r5`):

- **Planted means slow and low.** `planted_until` now asks for under `plant_speed_cm` (1.0) a frame along the floor
  and under `plant_rise_cm` (1.5) above the touching frame; a flat foot that creeps (Getup_Back, 3 to 4 mm a frame)
  or settles (Raise_In, 1.2 / 2.1 cm) is planted, and its fade falls where it moves by itself (Getup_Back's left foot
  in the air, frames 16 to 24) or it steps (the women's Raise_In, like the men's).
- **The floor.** No edited Foot or Toe head goes lower than both its own height before the edit and the idle's
  standing height (raised up to 21.3 mm, the women's Raise_In); a step lifts off that floor. The toes take the
  idle's bend as a change at the touching frame, like the feet.
- **A shuffle is lifted.** A fade whose foot stays under 2 cm off the floor (the package clips) lifts it on the
  step's arc, so the fade does not slide it.
- **The package clips** take `idle_ends {at = "both", upper = false}` on Pickup_Package (Putdown_Package reverses it):
  the issue lists Putdown_Package, the manager decided on a feet-only blend (2026-10-08), and both ends meet the
  idle's legs (the carry plays over the idle). Their arms keep the hold.

Measured on the saved sets (main / round 1 / round 2; the lowest Toe joint, cm, and its frames under 0; the feet's
horizontal motion while within 1 cm of their lowest height, mm in all and the most in one frame; the largest shin
acceleration, mm per frame squared):

| Clip | Body | Lowest toe joint | On-floor foot motion | Shin acceleration |
|---|---|---|---|---|
| Getup_Back | men | 1.03 / 1.03 / 1.03 | 76, 10 / **264, 39** / 84, 18 | 76 / 76 / 76 |
| Getup_Back | women | 1.21 / 1.21 / 1.21 | 80, 11 / **287, 43** / 89, 20 | 84 / 84 / 84 |
| Raise_In | men | 0.14 / **-0.83 (11)** / 0.14 | 6, 4 / 15, 9 / 22, 9 | 77 / 99 / 77 |
| Raise_In | women | 0.10 / **-1.70 (6)** / 0.10 | 5, 4 / **107, 41** / 26, 10 | 78 / 151 / **147** |
| Raise_Out | men | 0.46 / **-0.57 (10)** / 0.46 | 6, 4 / 15, 9 / 20, 9 | 55 / 61 / 43 |
| Raise_Out | women | 0.38 / **-0.96 (11)** / 0.38 | 6, 5 / 15, 10 / 23, 10 | 59 / 88 / 50 |
| Jump_Land | women | 0.04 / -0.02 (1) / 0.04 | 4, 1 / 4, 1 / 4, 1 | 193 / 134 / 134 |
| Knockdown | men | 0.36 / 0.38 / 0.39 | 6, 2 / 6, 2 / 6, 2 | 208 / 251 / **247** |
| Knockdown | women | 0.20 / 0.22 / 0.22 | 4, 1 / 4, 1 / 6, 2 | 226 / 297 / **297** |
| Pickup_Package | men | 1.77 / - / 0.46 | 231, 39 / - / 87, 9 | 17 / - / 59 |
| Pickup_Package | women | 0.31 / - / 0.41 | 64, 17 / - / 114, 10 | 19 / - / 52 |

The rest of the on-floor motion after round 2 is the steps' first and last frames (Raise_In, Raise_Out: the foot
under 1 cm up) and Getup_Back's landing frame. The idle_ends report's `floor` finds no foot below its floor and no
slide of a foot the clip keeps still, on every clip. The lowest vertex: Pickup_Package 0.0 to -0.08 cm (men) and
-0.27 to -0.57 cm (women); the bent toes of the package clip went 2.8 / 4.4 cm into the floor before the toes took
the idle's change. At the fourteen touching ends both feet stay 0.000 cm and 0.00 degrees from the idle's, the toes
0.00 degrees; the ankle gaps 0.002 to 0.011 mm (Knockdown's 2.9 mm on the frames idle_ends leaves alone); the
one-frame pops as main's (the men's Jump_Start trades one first-frame pop for another, LowerLeg.R at frame 0).

## Round 3: the game's frame and the held shuffle

Re-reviews of round 2 (code, motion) found two majors in the package clips, both hidden by the touching-end measure,
which was relative to each clip's Root. Round 3 (the set `mvp-49-r8`):

- **The game's frame.** The game plays the clips in place with no root motion (`contract.toml`, `[animation]
  in_place`), so its crossfade blends Root too, and a foot matched relative to the clip's Root moves with it. Art
  #33's `heading facing = "mean"` leaves the package clips' Root turned 19.84 degrees from the idle's: their feet kept
  that turn (the right foot 23.5 degrees out against the aim where the idle's is 3.66, the left -25.5 against -5.68)
  and, in the saved set, stood 1.1 to 11.8 cm from the idle's. `idle_ends` now matches the feet in armature space
  (`match = "set"`, the default) and then sets Root to the idle's on every frame, the bones under it keeping their
  poses (Root carries no weights), so the crossfade blends no Root turn either (with the turn left in Root, Godot's
  per-bone blend swung a foot 0.5 to 2.0 cm off its straight path halfway through it). Getup_Back keeps `match = "root"`: its whole body stands
  up 17 cm (men) and 27 cm (women) from where the idle stands.
- **The set's recentring.** `anim-set` recentres every clip after its edits, a one-shot on its first frame's Body, and
  the idle that `idle_ends` reads is already recentred: recentring a matched clip moved its feet off the idle's again,
  by its own shift (1.5 to 7.3 cm). This is also why round 2's UAL clips met the idle 0.2 to 6 cm off in the saved set
  (Jump_Start 5.9 cm) where the build report said 0.000. A clip that `idle_ends` placed (`placed_by`) is no longer
  recentred, and Putdown_Package, made `from` Pickup_Package, keeps the mark.
- **Held, not hopped.** Between the package clips' two ends both feet only shuffle (3 to 39 mm a frame, under 2.3 cm
  high). Round 2 faded each out and back in with overlapping windows and lifted both on the step's arc at once: the
  character rose 4 to 6.6 cm off the floor for about 0.2 s as it squatted. A foot that only shuffles between two ends
  that meet the idle is now held at the idle's on every frame (`hold`: windows L 3 to 8, R 2 to 13, women R 2 to 19),
  its toes at the idle's bend; the squat happens in the idle's stance, knees out (as the pickups').
- **Never both feet in the air.** A lift that has both feet over 1 cm up on a common frame is dropped (steps keep
  theirs first, then the earlier), and a step picks its window off the other foot's lift. The report's `air` checks the
  result on the lowest vertex: no set-matched clip has an airborne frame.
- **A leg that cannot reach.** In the game's frame the men's Pickup_Package starts 1.4 cm higher than the idle (art
  #33's floor lift); with the idle's lift cut to 0 its right leg still fell 3.9 mm short, and the IK pulled the foot off
  the idle's. The Body now goes down up to 2 cm where a leg would not reach even unlifted (`body_down_mm_max`), and its feet
  meet the idle's exactly.

Measured on the saved sets (`raw:anim-sets/<set>/<body>/anim_mvp_<body>.blend`, armature space: the game's frame):

| | main | round 2 (`mvp-49-r5`) | round 3 (`mvp-49-r8`) |
|---|---|---|---|
| Package ends (4): feet from the idle's, cm (men / women) | 9.0 to 22.0 / 8.8 to 22.0 | 1.1 to 11.8 / 1.1 to 11.6 | **0.00 / 0.00** |
| Package ends: the feet's turn against the idle's, degrees | 3.0 to 29.9 | 19.84 | **0.00** (first-frame yaw R +3.66, L -5.68, as the idle's) |
| Package ends: Root against the idle's | 4.0 to 7.3 cm, 19.84 deg | the same | **0.00 cm, 0.00 deg** |
| Package: a foot halfway through Godot's crossfade, off the straight blend, cm | 0.13 to 1.97 | 0.46 to 0.77 | **0.00** |
| Package: lowest Foot or Toe joint, its highest frame, cm (men / women) | 3.76 / - | **6.59 / 5.83** (both feet lifted) | 0.46 / 0.41 (the idle's toe height on every frame) |
| UAL clips' touching ends (9): feet from the idle's, cm | 0.2 to 5.9 (and up to 2.1 cm high) | 0.2 to 5.9 | **0.00** |
| Getup_Back's end (`match = "root"`): the whole body from the idle's, cm | 17.2 / 26.8 | 17.2 / 26.8 | 17.2 / 26.8 |

The build reports agree: at the thirteen set-matched ends `set_foot_*` is 0.000 cm and 0.00 degrees and `root_cm` 0; no
`airborne_frames` and no `foot_pulled` on a set-matched clip (the women's Getup_Back, matched relative to Root, has
one frame, 22, where its lowest vertex rises just over 1 cm); the ankle gaps 0.002 to 0.011 mm (Knockdown's 2.9 mm
on the frames it leaves alone). The one-frame pops are as round 2's.

## Open points

- **The package clips' body.** The feet now stand on the idle's in the game's frame (round 3), but the Body is not
  matched: it stands 3.6 to 12.1 cm from the idle's at the touching ends, and Putdown_Package starts (Pickup_Package
  ends) with the package held, the Body 4.8 cm (men) and 6.0 cm (women) lower and the knees bent about 40 degrees
  against the idle's 11, so the crossfade raises the body. The squat happens in the idle's narrow stance with the
  knees out. The package clips stay art #33's stopgap.
- **The yaw's reference.** "+3.66" is against the rest pose; the right foot's Foot-to-Toe line stands about 19.6 /
  14.4 degrees out against the aim, the left about 10.3 / 5.0 (the mesh: about 8 / 11 against -1.5 / +1.8, the code
  review's estimate). Whether the right foot reads straight beside the left is the engineer's call; `toe_in_deg` can
  be set per body.
- **The pickup in the narrow stance.** Planted all through in the idle's stance, Pickup_One and Putdown_One bend over
  straighter legs (the right knee 94 to 61 degrees) with the knees out, and the reaching hand goes into the leg: 4.8 to
  4.9 cm (men) and 5.7 to 6.0 cm (women), from 0.2 to 3.6 cm before. The lab's set has the same; for the designer
  (round D's open problem: the knees-out crouch), with the measure.
- **The women's arm offset** is 4.16 degrees by the donor's auto search; the lab's 6.0 was checked on its w1 (2.99 cm
  in the thighs without it). Worth a check on the cast's clothes at the next cast build; raising it is a one-line edit.
- **The women's arms at the touching ends** stay 2.66 degrees from the idle's (art #33's arm offset is the idle's alone,
  before and after this change).
- **Raise_In and Raise_Out** take a 4 cm high step of the left foot (it is planted all through the clip, and the
  clip's other end meets the kneeling work). In Raise_In the kneeling knee goes deeper into the floor: the lowest
  vertex -6.2 to -6.3 cm (men) and -5.6 to -6.5 cm (women). The women's Raise_In right shin accelerates 147 mm per
  frame squared at frame 7 (main 78), inside its fade where the thigh's roll (-39 degrees) and the knee's swing out
  meet; Knockdown's shins 247 / 297 (main 208 / 226). No one-frame pop is flagged; worth a look in the strips.
- **The review's other increases** (`anim-review clips`, hands in the legs, cm, main to round 2): Raise_In women 5.2
  to 7.3, Getup_Back women 2.8 to 3.9, Jump_Start men 0 to 1.9; decreases: Jump_Land 3.6 / 7.5 to 1.6 / 3.1,
  Knockdown women 6.1 to 2.1, Pickup_Package women 7.0 to 4.2.
  Its sole-sliding mean rises in Raise_In and Raise_Out (50 to 82 cm/s, men; 56 to 89, women): the 4 cm steps,
  which its contact window counts as on the floor; and in the women's Getup_Back (largest 62 to 147 cm/s, the left
  foot's landing).
- **Getup_Back** stands up with its whole body 17 cm (men) and 27 cm (women) from where the idle stands (art #33's
  recentring of its first, lying frame; `match = "root"` keeps its feet under it). The game plays clips in place with
  no root motion (`contract.toml`), so the crossfade into the idle moves the whole character that far. It needs the
  get-up's travel handled (root motion, or the get-up placed by its end); not in this issue.
- **The other neighbours.** A clip placed by `idle_ends` keeps its pre-recentring position at its other end, which
  meets a clip the set still recentres: the kneeling seams between the raise's clips (`Raise_Work_Loop` is a loop, centred over its cycle) and the jump's air
loop. Feet at the crossfade, cm, main / round 2 / round 3: Raise_In into Raise_Work_Loop 5.3 / 5.3 / 4.6 (men) and
7.1 / 7.1 / **9.7** (women); Raise_Work_Loop into Raise_Out 3.1 / 3.1 / 4.6 (men) and 2.8 / 2.8 / **9.7** (women);
Jump_Start into Jump_Air_Loop and Jump_Air_Loop into Jump_Land change by under 5 cm, the feet in the air. The women's
kneeling seams are worse: the next step is to place the work loop in its source's frame as well (a set option to
leave a clip unrecentred), so the three raise clips keep their source's continuity.
- **Knockdown's ankle** keeps a 2.9 mm gap on frames idle_ends leaves alone (main's set: 5.7 mm), from art #33's
  resampling of its IK legs.
- **The idle's loop step** of 1.51 / 1.52 median frame steps is the fingertips' (above); the build's warning stays.
