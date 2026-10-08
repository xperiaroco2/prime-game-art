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
  joint comparison with the lab's set; `tools/`: the two scripts that made `compare/` and `before_after/`).

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
- **The clips that meet the idle.** At all ten touching ends (Pickup_One and Putdown_One both ends; Jump_Start,
  Knockdown, Raise_In the start; Getup_Back, Jump_Land, Raise_Out the end) both feet are **0.000 cm and 0.00 degrees**
  from the idle's first frame relative to Root, and the curled fingers at the idle's curl, both bodies.
- **The game's checks pass.** `anim-set` builds, exports and checks both bodies (28 animations, 12 loops LINEAR,
  glTF-Validator 0 errors, godot-check as before: only `facing_plus_z` cannot tell on the pack donor). Godot plays
  Idle, Pickup_One and Knockdown within 0.054 mm of Blender.
- **New measured side effects** (the lab's set has them too): in the pickup and the put-down the hands reach into the
  legs, and Raise_In's kneeling knee goes 0.4 (men) and 0.9 cm (women) deeper into the floor ("Open points").

## The edits

The ops (docs/animations.md, "The ops" and "The relaxed idle") and their settings in `mvp.toml`:

| Clip | Steps after its art #33 steps |
|---|---|
| Idle_Loop | `foot_turn {bone = "Foot.R", toe_in_deg = 40}`, `stance {out_cm = 2}`, `shoulders {drop_deg = 6}`, `head_level {target_deg = 0, neck_share = 0.4}`, `hands_relax {curl_deg = Index 16/22/12, Middle 20/26/14, Ring 26/30/16, Pinky 32/34/18, Thumb 12/12}`, `thumb_in {beside = "Index3", side_cm = 1.6, max_deg = 40}`, women `arm_offset {abduct_deg = 4.16}` |
| Talk_Upper_Loop | the same without the arm offset; `hands_relax` with `cap = 1.5`; `thumb_in {from_clip = "Idle_Loop"}` |
| Pickup_One, Putdown_One | `idle_ends {at = "both", from_clip = "Idle_Loop"}` (Putdown_One now made from its source: the pickup's steps, reversed) |
| Jump_Start, Knockdown, Raise_In | `idle_ends {at = "start", ...}` |
| Getup_Back, Jump_Land, Raise_Out | `idle_ends {at = "end", ...}` |

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
| Knockdown | faded as the feet leave | L 15 to 23, R 14 to 22 |
| Raise_In | men: the left foot, planted all through, steps 4 cm high; the right faded; women: both faded | L step 10 to 18, R 2 to 10; women L 1 to 9, R 3 to 11 |
| Getup_Back | faded in as the feet plant | 31 to 39 (women L 32 to 40) |
| Jump_Land | held all through (the landing plants on the last frames) | none |
| Raise_Out | the left foot, planted all through, steps 4 cm high; the right faded | L step 0 to 8, R 9 to 17 |

## Measured

### The feet, before and after (`raw:review/stage1/49/compare/`, every frame)

Before is the set main builds (art #33); after the final set. Yaw out against the aim relative to rest (degrees, +
toe out; the first frame, and the range over the clip); ankle gap: the largest distance between a shin's end and its
IK foot over the clip. The touching ends themselves are in the next paragraph.

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
- **the final set**: the men's identical to the above; the women's differ by the arm offsets only (the fingertips 8.8
  to 19.0 mm off on the idle and the clips that meet it, 22.3 mm on the talk).

The stance's feet in the build report (`feet_m`) are the clip's positions before the set recentres it on the origin:
the lab's figures (`README_idle.txt`) are the same points after it.

### Godot (`frames/<body>/`)

Godot's frames of Idle, Pickup_One and Knockdown (off-screen window, Vulkan forward+) agree with Blender within 0.022,
0.054 and 0.017 mm (men) and 0.014, 0.054 and 0.017 mm (women) at 64 joints and 128 axis points; Idle's clip is in
`frames/<body>/clips/Idle.mp4`.

## Open points

- **The issue's clip list differs from round D's.** The issue (#49) names seven standing one-shots: Jump_Start,
  Jump_Land, Knockdown, Pickup_One, Putdown_One, Putdown_Package and Raise_In (round C's list: their first frame turns
  the right foot over 30 degrees out). Round D, which this port follows, blends the eight clips whose end meets the idle
  (adding Getup_Back and Raise_Out, leaving out Putdown_Package). The package clips are unchanged: Pickup_Package
  starts with the right foot 22.8 degrees out and the ankles 41 / 38 cm apart, Putdown_Package starts holding the
  package with the right foot 40.7 degrees out (56 / 54 cm), and ends as Pickup_Package starts. In the game both meet
  the idle's legs (the standing end, and the holding end under the carry layer), so a crossfade there still turns the
  right foot 19 to 37 degrees. A feet-only `idle_ends` (the upper body holds the package) would fix it; a decision.
- **The pickup in the narrow stance.** Planted all through in the idle's stance, Pickup_One and Putdown_One bend over
  straighter legs (the right knee 94 to 61 degrees) with the knees out, and the reaching hand goes into the leg: 4.8 to
  4.9 cm (men) and 5.7 to 6.0 cm (women), from 0.2 to 3.6 cm before. The lab's set has the same; for the designer
  (round D's open problem: the knees-out crouch), with the measure.
- **The women's arm offset** is 4.16 degrees by the donor's auto search; the lab's 6.0 was checked on its w1 (2.99 cm
  in the thighs without it). Worth a check on the cast's clothes at the next cast build; raising it is a one-line edit.
- **The women's arms at the touching ends** stay 2.66 degrees from the idle's (art #33's arm offset is the idle's alone,
  before and after this change).
- **Raise_Out and the men's Raise_In** take a 4 cm high step of the left foot (it is planted all through the clip, and
  the clip's other end meets the kneeling work). In Raise_In the kneeling knee goes deeper into the floor: the lowest
  vertex -6.2 to -6.6 cm (men) and -5.6 to -6.5 cm (women).
- **Getup_Back** ends with Root 17 cm (men) and 27 cm (women) from the idle's (round C's property, unchanged): whether
  the game moves the body by root motion decides that crossfade.
- **Knockdown's ankle** keeps a 2.9 mm gap on frames idle_ends leaves alone (main's set: 5.7 mm), from art #33's
  resampling of its IK legs.
- **The idle's loop step** of 1.51 / 1.52 median frame steps is the fingertips' (above); the build's warning stays.
