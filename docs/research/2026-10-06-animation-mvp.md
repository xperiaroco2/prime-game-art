# The animation MVP (art #33), 2026-10-06

The game needs 35 animation entries (the list: raw `manager/stage1/faces-research.json`, key `animation`). This
note records what the MVP set builds for each need, from which source and with which edits, what the measures say,
and what is left for hand keys, for a re-roll and for the game. The tools: the SMPL-H retarget of Meshy text to
motion, the clip edits and the animation sets (all in `docs/animations.md`); the settings:
`tools/blender/anim_sets/mvp.toml`.

Everything below was run on 2026-10-06 in background Blender 5.2.2 and Godot 4.7.2 on both body types (the men's
donor `Business Man.glb`, the women's `Suit.glb`, with the toe bones). Outputs, outside git:

- the set: `raw:anim-sets/mvp/<body>/` (`anim_mvp_<body>.blend`, `.glb`, `.export.json`, `build_report.json`,
  `build.md`, `godot-check/report.json`);
- the review: `raw:review/stage1/33/` (`strips/`, `clips/` MP4s, `pairs/`, `rates/`, `sheets/`, `metrics.md`,
  `frames/<body>/` for Godot's own frames, `joins.json`).

## The set

29 clips per body type, 26 exported (three are review candidates), 12 of them loops. `tools/run.py anim-set` builds
both body types in 1.5 to 2 minutes each, then exports and checks them:

| Check | Men | Women |
|---|---|---|
| build: every clip as long as its frames, every loop closed and in place | ok | ok |
| save: transforms applied, poses before and after | 0.0013 mm | 0.004 mm |
| export: 26 animations, one skin of 64 joints, 4 skinned parts; glTF-Validator | 0 errors | 0 errors |
| export: every loop closed (export.json seams) | all 0.0 mm, 0.0 deg | all 0.0 mm, 0.0 deg |
| godot-check: 64 bones, every track resolves (1534), lengths, rest joints within 0.01 mm | pass | pass |
| godot-check: the 12 `_Loop` clips import LINEAR without the suffix, the 14 one-shots play once | pass | pass |
| Godot `frames` against Blender (Jog_Fwd, Strafe_Left, Knockdown, Crawl, Carry_Upper, and Idle on the women; 64 joints and 128 axis points at 8 times) | within 0.017 mm | within 0.030 mm |

godot-check's `facing_plus_z` cannot tell on the pack donor (its parts are not named by role: no `_eyes` or `_shoes`
part); the set's command reports it as a warning. The donor's rest faces -Y in Blender, +Z in glTF.

**Godot's loop names** (measured): Godot 4.7.2's importer gives `Idle_Loop` the loop mode LINEAR and the name `Idle`.
The game sees `Idle`, `Jog_Fwd`, `Jog_Bwd`, `Strafe_Left`, `Strafe_Right`, `Sprint_Fwd`, `Jump_Air`, `Push_Upper`,
`Carry_Upper`, `Crawl`, `Raise_Work` and `Talk_Upper`; the one-shots keep their names. godot-check and frames now
expect these names and import a set at its own 30 fps.

## Per need

Status: **ok** (the measures pass; judge the motion in the review), **stopgap** (usable, a known defect), **re-roll**
(a Meshy clip that does not clean up), **none** (no clip by design). Times in seconds; "w" is the women only.

| No. | Need | Clip (game name) | Source | Edits | Status | Left for keys or the game |
|---|---|---|---|---|---|---|
| 1 | Idle | `Idle_Loop` (Idle) | UAL Idle_Loop | w: arm out 2.66 deg (hands 1.32 cm in the thighs to 0) | ok | the base under the carry, talk and push layers |
| 2 | Forward 4.5 m/s | `Jog_Fwd_Loop` | UAL Jog_Fwd_Loop | stride to 4.5 m/s at 2.86 steps/s (1.575 m steps; feet scale 0.567 men, 0.525 women: under the 0.6 warn mark) | ok | rate 1.0 at 4.5 m/s |
| 3 | Backward 4.5 | `Jog_Bwd_Loop` | UAL Jog_Fwd_Loop | the warped jog, reversed | stopgap | a forward run played backwards; Meshy's backward jog is a re-roll (below) |
| 4 | Strafe left and right 4.5 | `Strafe_Left_Loop`, `Strafe_Right_Loop` | TTM strafe-left | heading to +X (73 to 90 deg), cycle 1.83-2.57 s (seam 10.1 deg), stride at 4.0 steps/s (1.125 m, scale 1.25 men, 1.16 women); right = mirror | ok | a crossing gallop; diagonals blend in the game |
| 5 | Sprint forward 7.0 | `Sprint_Fwd_Loop` | UAL Sprint_Loop | retime by its root-motion speed (x0.82 men, x0.76 women) | ok | rate 1.0 at 7.0 m/s |
| 6 | Sprint back and sideways 7.0 | `Jog_Bwd_Loop`, `Strafe_*_Loop` at 1.556 | as 3 and 4 | none | stopgap | 4.4 steps/s backward and **6.2 steps/s sideways**: a whirl (engineer's question below) |
| 7 | Turn in place | `Turn_Left`, `Turn_Right` | TTM turn-left-90 | facing to the start, trim 0.13-1.73, turn 112.7 to 90 deg, retime 1.2 s; w: arms out 5.6 deg; right = mirror | ok | the pivot foot measures 18-20 cm/s mean (the raw clip 8-9 over 3 s with its still frames) |
| 8 | Head pitch | none | | | none | procedural |
| 9 | Jump | `Jump_Start`, `Jump_Air_Loop`, `Jump_Land` | UAL Jump_Start, Jump_Loop, Jump_Land | start: trim 0.03-0.40, retime 0.25 (0.267: whole frames); land: trim 0-0.5, retime 0.3 | ok | in place: the game lifts the body (the air loop's feet hang 17-18 cm under the floor) |
| 10 | Being pushed | `Shove_Stumble` | TTM shove-stumble | trim 0.37-1.83, facing to the start, in place along its path, arms out 12 deg | ok | its feet travel 1.06 (men) and 1.15 m/s (women), half the push speed of 2.25 m/s |
| 11 | Pushing | `Push_Upper_Loop` (upper) | UAL Push_Loop | w: hands apart 4.3 deg (6.09 cm inside each other to a 1.28 cm gap); men already 1.08 cm apart | ok | upper body, low weight |
| 12 | One-handed item | none | | | none | grip keys |
| 13 | Knife swing | `Knife_Swing` (upper) | pack Sword_Slash | retime 0.45 (0.467) | ok | upper body on Swung; women's source is 1.3 s, so 2.8x faster |
| 14 | Being hit | none | | | none | no reaction, by the rules |
| 15 | Carry | `Carry_Upper_Loop` (upper) | UAL2 Walk_Carry_Loop | hands apart to a 0.40 m mean gap: 28.7 deg men, 29.8 women (from touching) | ok | the arms open wide: judge in the pair; upper body over the idle and the locomotion |
| 16 | Pick up one-handed | `Pickup_One` | UAL2 Farm_Harvest | trim 0.13-2.13, retime 0.9 | ok | the hand is lowest at about 0.45 s |
| 17 | Put down one-handed | `Putdown_One` | Pickup_One | reverse, retime 0.8 | ok | |
| 18 | Pick up the package | `Pickup_Package` | TTM package-lift | trim 0.1-1.5, facing to the mean, retime 1.0, floor lift (toes 2.8/1.9 cm), hands apart to 0.40 m at the end (18.5/22.9 deg) | ok | ends with the hands at the hips, the carry holds them higher: a join (below) |
| 19 | Put the package down | `Putdown_Package` | Pickup_Package | reverse | ok | |
| 20 | Swap items | none | | | none | hand keys |
| 21 | Knocked down | `Knockdown` | UAL Death01 | floor lift from 1.2 s (4.86/3.44 cm), trim 0-2.0, retime 1.33 | ok | ends lying 0.48 m from where it started: the game moves the body there |
| 22 | Lying still | Knockdown's last pose | | | none | the breathing loop is hand keys |
| 23 | Crawl start | (`Crawl_Start`, review only) | TTM rollup-to-all-fours | settle, trim 0.4-2.4, facing to the end, retime 1.5 | review, or re-roll | floated 8 to 14 cm; after the settle it rolls on the floor and ends on all fours in the `mvp_downed` pair, its hands short of the floor (our shorter arms): export it if the review accepts it |
| 24 | Crawl 1.0 | `Crawl_Loop` (Crawl) | TTM crawl (batch 4) | heading forward, cycle 0.93-1.87 s over a **26-degree raw seam** (left wrist), settle (4.9/3.0 cm down), retime to 1.0 m/s | stopgap | the clip does not repeat; the hands hover 7-8 cm (our arms are 0.71 of SMPL-H's); re-roll |
| 25 | Stand up | `Getup_Back`; (`Getup_Fours`, review only) | UAL2 LayToIdle; TTM getup-from-all-fours | back: floor lift (toes 4 cm); fours: trim 0.27-2.0, facing to the start, in place, retime 1.5, settle | ok; review for fours | the get-up from all fours floated 6-13 cm; after the settle it reads as a get-up in the pair but lifts off 4.5 cm mid-rise |
| 26 | Raise | `Raise_In`, `Raise_Work_Loop`, `Raise_Out` | UAL Fixing_Kneeling | hips floor clamp (the knee 4.65 to 0.6 cm), trims 0-0.8 and 4.2-5.0 retimed to 0.6; the loop: cycle 2.9-3.9 s over a **27-degree raw seam** (right forearm) | stopgap | the kneeling foot's toes stay 2.7-6.2 cm under the floor (a hips lift cannot move them); the work does not repeat |
| 27 | Giving up | Knockdown's last pose | | | none | hold the pose |
| 28 | Talking | `Talk_Upper_Loop` (upper) | UAL Idle_Talking_Loop | hands apart 9.0 deg men, 12.5 women (2.2 cm inside each other to 1.2 cm apart) | ok | upper body, low weight |
| 29 | Face | none | | | none | procedural |
| 30-34 | Gestures | none | | | none | after the MVP |
| 35 | First-person arms | none | | | none | the game side |

The women's arms on the idle and the three layers over it: hands in the legs 0.0 cm on `mvp:Idle_Loop` and on
`Idle_Loop|Push_Upper_Loop`, `|Talk_Upper_Loop`, `|Carry_Upper_Loop` (both bodies); hands in each other 0.0 on all of
them. The women's push and talk needed no arm offset of their own (the search found 0 degrees).

## Measures

From `raw:review/stage1/33/metrics.md` (anim-review clips, `--sources mvp`): every set loop's seam is 0.0 to 0.1
degrees (x0.0 to x0.1 of a frame step), against 23 to 59 degrees in the raw text-to-motion clips. On the treadmill
(`rates/<body>/rates.json`), every set locomotion clip plays at rate 1.0 at its speed with its feet at the ground's
speed: the jog and the strafes 4.50 m/s, the sprint 7.46 (men) and 7.33 m/s (women) by the feet against 7.0 by root
motion.

| Clip | Body | Lowest cm | Foot slide mean/max cm/s | Hands in legs cm | Verdict |
|---|---|---|---|---|---|
| Jog_Fwd_Loop, Jog_Bwd_Loop | m / w | -1.0 / -1.2 | in place (stride: 0.0 on contact) | 0 / 0 | pass |
| Strafe_*_Loop | m / w | -1.4 / -0.8 | in place (stride: 0.0 on contact; IK misses 150/109 mm in flight) | 0 / 0 | pass; the flight legs fall short |
| Sprint_Fwd_Loop | m / w | -1.4 / -1.5 | 43.6 / 84.7 (men) | 0 / 0 | the toe dip and the UAL sprint's own slide |
| Turn_Left, Turn_Right | m / w | -0.3 / -0.4 | 19.7 / 147 and 17.6 / 152 | 0 / 0 | the pivot over the 12 cm/s mark |
| Knockdown | m / w | -0.9 / -0.8 | 7.6 / 129 and 2.2 / 28 | 0 / 6.1 | pass on the floor; the women's hands brush the thighs in the fall |
| Shove_Stumble | m / w | -1.2 / -0.5 | 37.7 / 79 and 39.2 / 75 | 0 / 4.5 | the stumble's steps slide in place: the game moves the body |
| Crawl_Loop | m / w | 0.0 / 0.0 | (knees and hands: no foot measure) | 0 / 0 | settled; hands hover |
| Raise_In, Raise_Out | m / w | -6.2, -4.5 / -5.6, -3.7 | under 1.2 mean | 0, 3.0 / 5.2, 7.0 | the kneeling foot's toes (above) |
| Pickup_Package | m / w | 0.0 / -0.3 | 17 / 122 and 18 / 133 | 1.7 / 7.0 | the squat's shuffle |
| Getup_Back | m / w | 0.0 / 0.0 | 6.1 / 39 and 7.0 / 42 | 0 / 2.8 | pass |
| Jump_Air_Loop | m / w | -18.3 / -17.2 | 0.6 / 1.9 | 0 / 0 | exempt (in place) |

Stride warping (build reports): the jog at 4.5 m/s plays 28 frames as 21 (rate 1.381 after closing the open source
cycle), its planted feet at exactly 4.50 m/s, IK miss 0.0 mm, the knee never past straight. The strafe at 4.0 steps/s:
IK miss 0.0 mm on contact frames, 150 (men) and 109 mm (women) in flight. At the design's 2.9 steps/s the strafe's
steps had to grow 1.74x (men) and its legs missed by 66 mm on contact and 465 mm in flight. Meshy's backward jog fails
the stride: scale 7.1 (men) and 6.6 (women), IK misses of 487 and 734 mm on contact, its planted feet sliding 62 and
174 cm/s.

## Joins

Reported, not graded (`raw:review/stage1/33/joins_<body>.json`): from the last frame of one clip to the first of
the next in the saved set, the Body (pelvis) distance and the largest world rotation of an upper-body bone other
than the fingers (the fingers differ by the source's hand shape: SMPL-H's constant relaxed curl against UAL's fist).
A turn ends 90 degrees round, so its join to the idle reads the body's yaw; the game turns the body with it.

| From -> to | Pelvis cm (men / women) | Upper body deg (men / women), the worst bone |
|---|---|---|
| Knockdown to Getup_Back | 48.1 / 59.7 | 178.4 / 178.4, LowerArm.L |
| Knockdown to Crawl_Loop | 57.2 / 65.0 | 180.0 / 180.0, Shoulder.L |
| Crawl_Loop to Getup_Back | 30.7 / 24.1 | 176.8 / 176.8, Shoulder.R |
| Pickup_Package to Carry_Upper_Loop | 3.3 / 4.5 | 96.6 / 95.3, LowerArm.L |
| Carry_Upper_Loop to Putdown_Package | 2.3 / 3.4 | 96.6 / 95.3, LowerArm.L |
| Idle_Loop to Jog_Fwd_Loop | 6.9 / 8.0 | 90.8 / 90.4, UpperArm.R |
| Jump_Start to Jump_Air_Loop | 13.9 / 12.4 | 35.5 / 35.5, LowerArm.R |
| Jump_Air_Loop to Jump_Land | 4.6 / 4.2 | 13.9 / 13.9, Head |
| Raise_In to Raise_Work_Loop | 5.3 / 7.1 | 64.8 / 64.8, Wrist.R |
| Raise_Work_Loop to Raise_Out | 1.0 / 0.5 | 51.1 / 51.1, Wrist.R |
| Idle_Loop to Turn_Left | 3.9 / 3.7 | 49.3 / 50.6, LowerArm.L |
| Turn_Left to Idle_Loop | 11.2 / 17.2 | 135.7 / 137.1, LowerArm.L |
| Pickup_One to Idle_Loop | 4.3 / 4.5 | 18.4 / 18.4, Head |
| Idle_Loop to Pickup_Package | 3.5 / 2.1 | 30.0 / 30.0, Shoulder.L |
| Shove_Stumble to Idle_Loop | 4.3 / 4.5 | 40.0 / 40.0, Shoulder.L |

The downed chain does not join: Knockdown ends on the back 48 (men) and 60 cm (women) from where the crawl and
the get-up stand (both start over the origin), and the crawl is on all fours (the missing roll-up, a re-roll). The
package lift ends with the forearms 95 to 97 degrees from the carry's: the game blends them, or the lift's end
moves up to the carry's hold (a hand-keyed end pose).

## Re-roll candidates (the 30-credit reserve)

The manager runs a re-roll batch; no prompt names a game or a character. In order of need:

1. **rollup-to-all-fours** (need 23, no alternative). Measured: the source floats on its own mannequin (3-17 cm);
   on our rig the lowest vertex is 7.8 cm (men) to 13.7 cm (women) above the floor at best, and it ends on all fours
   with the wrists 23-28 cm up and the pelvis at 0.60 m (the crawl's 0.44-0.54). A settle brings the lowest vertex to
   the floor, but the hands never reach it. Prompt: "A person lies flat on their back on the ground, the back, head,
   arms and legs all resting on the ground. Slowly, as if hurt, they roll over onto their side and then onto their
   stomach, staying low against the ground, then push up onto hands and knees: palms flat on the ground under the
   shoulders, knees and shins on the ground under the hips. They stay there on all fours, head hanging low, breathing
   heavily."
2. **crawl** (need 24, a stopgap exists). Measured: no cycle of 0.5 to 3 s repeats: the best cut (0.93 s) has a raw
   seam of 26.4 degrees in the left wrist, longer cuts 37 to 40; it heads 20 degrees off straight and floats 3 to 5 cm.
   Prompt: "A hurt person crawls forward on hands and knees in a perfectly straight line at a slow, steady pace, palms
   flat on the ground under the shoulders, knees on the ground under the hips, body low, head up looking ahead, the
   hands and knees moving in an even alternating rhythm. A repeating crawl cycle of about one second that starts and
   ends in the same pose, no looking around, no turning."
3. **backward-jog** (need 3, the reversed jog is a stopgap). Measured: 1.25 m in 3.97 s (0.31 m/s; its best cycle
   0.56-0.70 m/s), steps of 0.09-0.30 m; stride warping to 4.5 m/s needs 6.6-7.1x the step length (the stride's fail
   limit is 2.5x). Prompt: "A person runs backwards fast in a straight line, covering about four metres every second,
   with long backward strides and a short flight phase between steps, pushing off the balls of the feet, knees bent,
   torso leaning slightly forward, chest and head facing straight ahead, arms bent and pumping. An even, repeating
   running cycle that starts and ends in the same pose."
4. **getup-from-all-fours** (need 25's crawl case; LayToIdle covers the back). Measured: floats 6-13 cm (its standing
   pelvis 1.09 m against 0.97); after the settle the lowest vertex reaches the floor but lifts 4.5 cm mid-rise.
   Prompt: "A person kneels on hands and knees on the ground, palms flat and knees and shins resting on the ground.
   Tired and a little hurt, they push up with the arms, bring one foot forward flat on the ground, stand up and end
   standing relaxed with both feet flat on the ground and the arms at the sides, about one and a half seconds."

## Questions for the engineer and the designer

- **Sideways and backward at 7.0 m/s.** At the decided 1.556x the strafe runs 6.2 steps/s and the backward jog 4.4:
  likely a whirl. Options: separate 7.0 m/s bakes (one more settings entry each, stride to 1.6-2.2 m steps), or a
  forward-only sprint. Recommendation: separate bakes once the strafe and the backward clip are approved.
- **The strafe's cadence.** 4.0 steps/s at 4.5 m/s (the design said 2.9): the legs stay within reach. Judge it on the
  treadmill (`rates/<body>/mvp_strafe_left_4.5.mp4`).
- **The carry's arms** open 29 to 30 degrees for a 0.40 m gap: judge it in `pairs/<body>/mvp_package.mp4`.
- **The shove's speed**: retime it to 2.25 m/s (0.69 s) so its steps match the push, or keep 1.47 s.

## Deviations from the design

- `Jog_Bwd_Loop` is the warped forward jog reversed (the design's review candidate), and Meshy's backward jog is the
  review candidate `Jog_Bwd_TTM_Loop`: its stride fails as predicted.
- The strafe runs at 4.0 steps/s, not 2.9 (the IK misses above).
- The crawl and the raise loop are closed over raw seams of 26 and 27 degrees (`max_raw_seam_deg = 30`), flagged as
  stopgaps: no cut stays under 15.
- New in the build: open source loops are closed, and every clip is recentred over the origin (docs/animations.md).
- New edit: `floor {mode = "settle"}` for clips that float (the crawl, the roll-up, the get-up).
- The roll-up and the get-up from all fours are built but not exported: the settle makes both read plausibly in the
  `mvp_downed` pair; the review decides between exporting them (`export = true`) and a re-roll.
