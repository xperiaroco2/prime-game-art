# The animation MVP (art #33), 2026-10-06

The game needs 35 animation entries (the list: raw `manager/stage1/faces-research.json`, key `animation`). This
note records what the MVP set builds for each need, from which source and with which edits, what the measures and the
review say, and what is left for hand keys, for a re-roll and for the game. The tools: the SMPL-H retarget of Meshy
text to motion, the clip edits and the animation sets (all in `docs/animations.md`); the settings:
`tools/blender/anim_sets/mvp.toml`.

Everything below was run on 2026-10-06 in background Blender 5.2.2 and Godot 4.7.2 on both body types (the men's
donor `Business Man.glb`, the women's `Suit.glb`, with the toe bones). Outputs, outside git:

- the set: `raw:anim-sets/mvp/<body>/` (`anim_mvp_<body>.blend`, `.glb`, `.export.json`, `build_report.json`,
  `build.md`, `godot-check/report.json`);
- the review: `raw:review/stage1/33/` (`strips/`, `clips/` MP4s, `pairs/`, `rates/`, `sheets/`, `metrics.md`,
  `frames/<body>/` for Godot's own frames and clips, `joins_<body>.json`).

## Summary

- **28 clips per body type ship in the GLB** (12 loops, 16 one-shots), and one more is built for review only (Meshy's
  backward jog, which fails). Both GLBs pass glTF-Validator and the set's Godot checks (godot-check's facing check
  cannot tell on the pack donor: below). Godot plays them within 0.07 mm of Blender. Every loop's last frame is its
  first by construction; the real seam, the step from the last distinct frame onto the first, is at most 1.4 median
  frame steps, except the reversed jog's 1.6.
- **The review's verdicts** over the 35 needs (after the fresh reviews, below):
  - **pass:** 5 (idle, pushing, knife, the one-handed put-down, talking);
  - **pass with a note:** 8 (forward, sprint, turn, jump, being pushed, carry, the one-handed pick-up, knockdown);
  - **stopgap:** 8 (the backward jog, the strafes, the 7.0 m/s sideways and backward sprint, the package pick-up and
    put-down, the crawl start, the crawl and the raise);
  - **the stand-up** (need 25) passes from the back and is a stopgap from all fours;
  - **none by design:** 13 (hand keys, procedural, no reaction by the rules, or after the MVP);
  - **fail:** Meshy's backward jog, a review-only candidate.
- **Fixes after the fresh reviews** (code, motion, Godot, docs; the PR lists every finding):
  - **The crawl's ankles tore** 15 cm mid-cycle: the `cycle` cut closed the IK feet and the legs separately. It now
    solves the legs again on every frame (the gap 152/157 mm to 0, IK miss 0.0 mm).
  - **The sprint's feet ran 7.46 and 7.33 m/s** on a 7.0 m/s ground. It is stride-warped now: the planted feet at
    exactly 7.0 m/s, slide 0.0 on contact, the reviewed cadence kept.
  - **The knockdown's lying frames floated** 2.0-4.5 cm (the held downed pose 2.2 cm up). A settle from the frame after
    the impact puts them on the floor (lowest 0.0, at most 1.4 cm in the first lying frames).
  - **The strafe's turned body** (hips 19.5 degrees towards the travel, head 15.9 the other way) is now measured and
    warned by the build, graded a stopgap and put to the engineer; the crawl's skating hands are recorded.
- **Two fixes came out of the motion review:**
  - **The push layer had its hands over the head** over the idle and the jog: Push_Loop leans 46 degrees with the
    hips, and the game's layer from Torso drops the hips. A new `lean` edit puts 30 degrees into Torso. The hands are
    now in front of the face, a push.
  - **The settled roll-up and get-up from all fours** read as what they are on both bodies, so they ship as flagged
    stopgaps (`Crawl_Start`, `Getup_Fours`) instead of review-only candidates. The downed chain now has every clip.
- **Meshy:** batch 5 spent 70 of the 70 approved credits (balance 315 to 245); the 30-credit reserve is untouched.
  Four clips are re-roll candidates; the reserve covers the first three (below).
- **For the engineer:** sideways at 7.0 m/s comes out at 6.2 steps/s, likely a whirl (separate bakes recommended),
  plus four taste questions (below).

## The set

29 clips per body type: 28 exported (12 loops, 16 one-shots) and one review candidate. `tools/run.py anim-set` builds
both body types in 1.5 to 2 minutes each, then exports and checks them:

| Check | Men | Women |
|---|---|---|
| build: every clip as long as its frames, every loop closed and in place | ok | ok |
| save: transforms applied, poses before and after | 0.0013 mm | 0.004 mm |
| export: 28 animations, one skin of 64 joints, 4 skinned parts; glTF-Validator | 0 errors (2.51 MB) | 0 errors (2.47 MB) |
| export: every loop closed (export.json seams; 0 by construction) | all 0.0 mm, 0.0 deg | all 0.0 mm, 0.0 deg |
| the real seam: the step onto the first frame against the median step (build report `seam_step_ratio`) | 0.49 to 1.37; Jog_Bwd 1.61 | 0.46 to 1.37; Jog_Bwd 1.59 |
| hips and head facing of the locomotion loops (build warning over 5 degrees) | strafes 19.5 / -15.9; crawl -4.7 / -7.8; the rest 0 | the same |
| godot-check: 64 bones, every track resolves (1652), lengths, rest joints within 0.01 mm | pass | pass |
| godot-check: the 12 `_Loop` clips import LINEAR without the suffix, the 16 one-shots play once | pass | pass |
| Godot `frames` against Blender (the sample below; 64 joints and 128 axis points at 8 times) | within 0.017 mm | within 0.030 mm |

godot-check's `facing_plus_z` cannot tell on the pack donor (its parts are not named by role: no `_eyes` or `_shoes`
part); the set's command reports it as a warning, but a standalone `godot-check` of these GLBs exits 1 on it. The
donor's rest faces -Y in Blender, +Z in glTF (Godot's rest joints: Toe.L ahead of Foot.L, Wrist.L at +X). A later
task that runs godot-check on a set GLB needs the toe-bone fallback in `facing_plus_z` (not done here).

The rebuild on the PR's head (the set as it ships) gave the same checks on both bodies; the numbers in this note are
from it.

**Godot's loop names** (measured): Godot 4.7.2's importer gives `Idle_Loop` the loop mode LINEAR and the name `Idle`.
The game sees `Idle`, `Jog_Fwd`, `Jog_Bwd`, `Strafe_Left`, `Strafe_Right`, `Sprint_Fwd`, `Jump_Air`, `Push_Upper`,
`Carry_Upper`, `Crawl`, `Raise_Work` and `Talk_Upper`; the one-shots keep their names. godot-check and frames now
expect these names and import a set at its own 30 fps.

**Godot frames** (`tools/run.py frames <glb> --clips ... --video ...`, an off-screen window,
`raw:review/stage1/33/frames/<body>/`): Godot 4.7.2's own frame sheets and looping MP4s of a sample, each compared
with Blender's pose at 8 times.

- **Men:** Jog_Fwd, Strafe_Left, Turn_Left, Shove_Stumble, Crawl_Start, Crawl, Getup_Fours, Carry_Upper, Push_Upper
  and Knockdown, all within 0.014 to 0.017 mm.
- **Women:** Idle, Jog_Fwd, Strafe_Right, Turn_Right, Shove_Stumble, Crawl_Start, Getup_Fours, Carry_Upper and
  Push_Upper, within 0.014 to 0.030 mm (the idle's fingers).
- **After the fixes** (the rebuilt GLBs): Crawl, Knockdown, Sprint_Fwd, Raise_Work and Strafe_Left on both bodies,
  within 0.010 to 0.024 mm, except Raise_Work's kneeling foot at 0.064 (men) and 0.068 mm (women). The worst over
  every clip run is therefore 0.068 mm, all far inside the 1 mm tolerance.

The carry walk is UAL2's Walk_Carry_Loop, played whole as `Carry_Upper`; in the game only its upper body plays.

## Per need

Verdicts:

- **pass:** the measures pass and the motion reads right in the review;
- **pass, note:** usable as it is, with a point to judge or a defect too small to fix now;
- **stopgap:** shipped with a known defect, to replace later;
- **fail:** not usable;
- **none:** no clip by design.

Times are in seconds; "w" means the women only. The last column holds what is left for hand keys or for the game
(see "For the game" below).

| No. | Need | Clip (game name) | Source | Edits | Verdict | Left for keys or the game |
|---|---|---|---|---|---|---|
| 1 | Idle | `Idle_Loop` (Idle) | UAL Idle_Loop | w: arm out 2.66 deg (hands 1.32 cm in the thighs to 0) | pass | the base under the carry, talk and push layers |
| 2 | Forward 4.5 m/s | `Jog_Fwd_Loop` | UAL Jog_Fwd_Loop | stride to 4.5 m/s at 2.86 steps/s (1.575 m steps; feet scale 0.567 men, 0.525 women: under the 0.6 warn mark) | pass, note: long, low strides; the planted feet at exactly 4.50 m/s | BlendSpace2D forward, rate speed / 4.5 |
| 3 | Backward 4.5 | `Jog_Bwd_Loop` | UAL Jog_Fwd_Loop | the warped jog, reversed | stopgap: a forward run played backwards, the body leaning forward | BlendSpace2D back; Meshy's backward jog is a re-roll |
| 4 | Strafe left and right 4.5 | `Strafe_Left_Loop`, `Strafe_Right_Loop` | TTM strafe-left | heading to +X (73 to 90 deg), cycle 1.83-2.57 s (seam 10.1 deg), stride at 4.0 steps/s (1.125 m, scale 1.25 men, 1.16 women); right = mirror | stopgap: a crossing gallop at 4 steps/s; **the hips face 19.5 degrees towards the travel and the head 15.9 the other way** (the source's own twist: no heading fixes both); the flight legs fall 150/109 mm short of their targets | BlendSpace2D left and right; the engineer's question (below); a re-roll candidate |
| 5 | Sprint forward 7.0 | `Sprint_Fwd_Loop` | UAL Sprint_Loop | **stride to 7.0 m/s** at the reviewed cadence (rate 0.833 men, 0.769 women: 2.5 and 2.31 steps/s of 2.8 and 3.03 m; scale 0.93/0.94, fit ok) | pass, note: the planted feet at exactly 7.0 m/s (they ran 7.46 and 7.33 when retimed by root motion); the toes dip 1.35/1.47 cm (the known toe dip) | rate 1.0 at 7.0 m/s |
| 6 | Sprint back and sideways 7.0 | `Jog_Bwd_Loop`, `Strafe_*_Loop` at 1.556 | as 3 and 4 | none | stopgap: 4.4 steps/s backward; **6.2 steps/s sideways**, a whirl | the engineer's question below |
| 7 | Turn in place | `Turn_Left`, `Turn_Right` | TTM turn-left-90 | facing to the start, trim 0.13-1.73, turn 112.7 to 90 deg, retime 1.2 s; w: arms out 5.6 deg; right = mirror | pass, note: two clear steps; the pivot foot slides 18-20 cm/s mean (147-152 max) | the lower-body turn logic (below) |
| 8 | Head pitch | none | | | none | procedural |
| 9 | Jump | `Jump_Start`, `Jump_Air_Loop`, `Jump_Land` | UAL Jump_Start, Jump_Loop, Jump_Land | start: trim 0.03-0.40, retime 0.25 (0.267: whole frames); land: trim 0-0.5, retime 0.3 | pass, note: the start opens in a crouch and the landing ends in one; the take-off's toes dip 1.9 (men) and 2.3 cm (women) for 4 frames, past the design's -2 cm line on the women (resampling loses the retarget's toe clamp); the air loop's right foot snapped 53-55 degrees and back in one frame (4 times a loop on the men, twice on the women) until the floor clamp was made to fade (131c347): now one held pose, its largest frame step 2.6/2.9 degrees; w: hands 7.5 cm in the thighs at the landing | the game blends in and out, and lifts the body (the clips are in place; the air loop's lowest vertex is 5.3/5.5 cm under the floor line, which the lift hides) |
| 10 | Being pushed | `Shove_Stumble` | TTM shove-stumble | trim 0.37-1.83, retime 0.7 s (art #65: the engineer's 0.69 s, whole frames), facing to the start, in place along its path, arms out 12 deg | pass, note: the arms fly forward, two steps back, a crouch; w: hands 4.5 cm in the thighs at the crouch | contact detection; its feet travel 1.06 (men) and 1.15 m/s (women), half the push speed of 2.25 |
| 11 | Pushing | `Push_Upper_Loop` (upper) | UAL Push_Loop | w: hands apart 4.3 deg (6.09 cm inside each other to a 1.28 cm gap); **lean 30 deg from Torso** (new) | pass after the lean: over the idle and the jog it leans into the push, palms forward at face height | upper layer at a low weight while in contact; the full-body clip bends 76 deg: a layer only |
| 12 | One-handed item | none | | | none | grip keys |
| 13 | Knife swing | `Knife_Swing` (upper) | pack Sword_Slash | retime 0.45 (0.467) | pass | upper layer on Swung (a OneShot); the women's source is 1.3 s, so 2.8x faster |
| 14 | Being hit | none | | | none | no reaction, by the rules |
| 15 | Carry | `Carry_Upper_Loop` (upper) | UAL2 Walk_Carry_Loop | art #65: fingers nearly straight, `side_grip` 0.45 m (the palms facing, 44.7-45.3 cm on every frame); art #33: hands apart to a 0.40 m mean gap, 28.7 deg men, 29.8 women (from touching) | pass, note: the forearms open wide with the palms up, a tray under the box (wrists 0.59-0.65 m apart); the game's package is 0.45 m, so a side grip would need `gap_m = 0.45` (the designer's call) | upper layer over the idle and the locomotion; CARRY_POINT moves to the hands |
| 16 | Pick up one-handed | `Pickup_One` | UAL2 Farm_Harvest | trim 0.13-2.13, retime 0.9 | pass, note: w: the hand 2.5 cm past the thigh at the bottom | the hand is lowest at about 0.45 s: attach the item there |
| 17 | Put down one-handed | `Putdown_One` | Pickup_One | reverse, retime 0.8 | pass | since art #49 made from UAL2 Farm_Harvest with the pickup's steps reversed, then idle_ends ([2026-10-08-relaxed-idle.md](2026-10-08-relaxed-idle.md)) |
| 18 | Pick up the package | `Pickup_Package` | TTM package-lift | trim 0.1-1.5, facing to the mean, retime 1.0, floor lift (toes 2.8/1.9 cm), art #65: `side_grip` 0.45 m from the hands' lowest point (0.43 s), faded in over 0.3 s; art #33: hands apart to 0.40 m at the end (18.5/22.9 deg) | stopgap: a wide squat whose feet shuffle 17-18 cm/s (past the 12 cm/s mark); it ends with the hands beside the thighs, 0.40 m apart, where the carry holds them higher (w: 7.0 cm in the legs), so it does not end holding a package | blend into the carry layer (forearms 95-97 deg apart), or a hand-keyed end pose |
| 19 | Put the package down | `Putdown_Package` | Pickup_Package | reverse | stopgap: the pick-up reversed, so it starts from the hands-by-the-thighs pose, not from the carry's hold, and shuffles as the pick-up does | as 18: an end pose up to the carry's hold mends both |
| 20 | Swap items | none | | | none | hand keys |
| 21 | Knocked down | `Knockdown` | UAL Death01 | floor lift from 1.2 s (4.86/3.44 cm), trim 0-2.0, retime 1.33, **settle from 0.83 s** (the lying frames 2.2-3.7 cm down) | pass, note: lies on the floor (lowest 0.0, the first lying frames at most 1.4 cm up); w: the hands brush the thighs 6.1 cm in the fall | ends lying 0.48 m behind where it started: the game moves the body there |
| 22 | Lying still | Knockdown's last pose | | | none | the breathing loop is hand keys |
| 23 | Crawl start | `Crawl_Start` (exported now) | TTM rollup-to-all-fours | settle, trim 0.4-2.4, facing to the end, retime 1.5 | stopgap: rolls over onto all fours on the floor; the hands stay short of it, and the source floated 8 to 14 cm | re-roll 1; the lying heading is the knockdown's turned round (the joins) |
| 24 | Crawl 1.0 | `Crawl_Loop` (Crawl) | TTM crawl (batch 4) | heading forward, cycle 0.93-1.87 s over a **26-degree raw seam** (left wrist), settle (4.9/3.0 cm down), retime to 1.0 m/s | stopgap: reads as a crawl on the treadmill; the cycle now keeps the shins on the feet (the ankles tore 15 cm before the fix); the hands hover 7-8 cm (our arms are 0.71 of SMPL-H's) and **skate**: at 1.0 m/s a planted hand should move 1.0 m/s under the body, but the wrists sweep only 17-25 cm a cycle (about 65-95 cm/s of slide); the body faces 4.7 degrees off | a re-roll (the engineer's yes: batch 4); the body turns toward its velocity |
| 25 | Stand up | `Getup_Back`; `Getup_Fours` (exported now) | UAL2 LayToIdle; TTM getup-from-all-fours | back: floor lift (toes 4 cm); fours: trim 0.27-2.0, facing to the start, in place, retime 1.5, settle | back: pass; fours: stopgap (it lifts off 4.5 cm mid-rise; hands 6.7/7.4 cm in the thighs as it rises; it ends with the hips 20 degrees left, 33 from the idle's) | Getup_Back when the player never crawled, Getup_Fours after a crawl |
| 26 | Raise | `Raise_In`, `Raise_Work_Loop`, `Raise_Out` | UAL Fixing_Kneeling | hips floor clamp (the knee 4.65 to 0.6 cm), trims 0-0.8 and 4.2-5.0 retimed to 0.6; the loop: cycle 2.9-3.9 s over a **27-degree raw seam** (right forearm) | stopgap: reads as kneeling over a body; the kneeling foot's toes 2.7-6.2 cm under the floor | hand keys for the toes and a calmer work loop |
| 27 | Giving up | Knockdown's last pose | | | none | hold the pose |
| 28 | Talking | `Talk_Upper_Loop` (upper) | UAL Idle_Talking_Loop | hands apart 9.0 deg men, 12.5 women (2.2 cm inside each other to 1.2 cm apart) | pass | upper layer at a low weight |
| 29 | Face | none | | | none | procedural |
| 30-34 | Gestures | none | | | none | after the MVP |
| 35 | First-person arms | none | | | none | the game side |

Review only: `Jog_Bwd_TTM_Loop` (Meshy's backward jog stride-warped to 4.5 m/s): **fail**, its legs split (scale 7.1
men, 6.6 women; IK misses of 487 and 734 mm on contact).

The women's arms on the idle and the three layers over it: hands in the legs 0.0 cm on `mvp:Idle_Loop` and on
`Idle_Loop|Push_Upper_Loop`, `|Talk_Upper_Loop`, `|Carry_Upper_Loop` (both bodies); hands in each other 0.0 on all of
them. The women's push and talk needed no arm offset of their own (the search found 0 degrees).

## What the review looked at

What was looked at:

- all 11 review sheets: every set clip's strips, men and women, front and side;
- the pairs: men downed, package, pushed, knockdown, raise and jump; women downed, turn and layers (after the lean);
- the treadmill rows:
  - men: walk, back 4.5 and 7.0, strafe left 4.5 and 7.0, sprint, crawl, carry 4.5 and push 2.25;
  - women: crawl, strafe right 4.5, carry 4.5 and carry 7.0;
- the push layer before and after the lean, over the idle and over the jog;
- Godot's sheets of Crawl_Start, Push_Upper and Turn_Left (men).

The other rows and pairs are the same clips at another rate, or on the other body type, and were not each opened.

After the fresh reviews' fixes (the publisher's pass on the rebuilt set): Godot's own sheets of Crawl (men and women),
Knockdown and Sprint_Fwd (men), the strips and sheets of every rebuilt clip, and the treadmill rows and pairs those
fixes change (listed in the PR). The crawl's shins now stay on the feet through the loop, the knockdown lies on the
floor, and the sprint reads as before with its feet planted.

After the motion re-review's air-loop finding (the floor clamp's fade): the men's `strips/men/mvp_Jump_Air_Loop.png`
(the right foot keeps one flat pose through the loop, where it pointed its toe down from 0.23 to 0.91 s before) and
Godot's own sheet of `Jump_Air` (women; the same pose at all 8 times, where it flipped between f29 and f30), with
Godot and Blender within 0.017 mm (men) and 0.014 mm (women) on `Jump_Air` and `Jump_Start`. The rebuilt pair
`pairs/<body>/mvp_jump.mp4` and Godot's `frames/<body>/clips/Jump_Air.mp4` were rendered, not watched. The airborne
right foot now sits level (the clamp holds most of it) where the source points it about 50 degrees down; the game lifts
the body, so it reads as a foot held flat in the air.

- **The push layer** (`Idle_Loop|Push_Upper_Loop`) raised both hands over the head, palms forward, on both bodies, as
  "hands up" rather than a push. UAL Push_Loop leans the whole body about 46 degrees from the feet and holds the arms
  forward along it. The game's upper-body layer starts at Torso, so over an upright base the arms point up. With
  `lean {deg = 30}` the spine tilts 30 degrees more (men 45.8 to 75.8 measured on the full clip; the head 10.5 cm
  forward, women 8.2), and over the idle and the jog the upper body leans into the push with the palms at face height.
- **The roll-up and the get-up from all fours** read as a roll onto all fours and a tired get-up on both bodies after
  the settle, so they ship as stopgaps. The settle leaves the roll-up's hands short of the floor, and the lowest vertex
  of the settled source lifts off up to 10.9 (men) and 7.9 cm (women) between its floor contacts.
- **Meshy's backward jog warped to 4.5 m/s** splits the legs: it fails, as the measures said.
- **The strafe** reads as a quick sideways gallop with crossing steps. At 7.0 m/s (x1.556) it becomes a fast
  shuffle: the engineer's question below.
- **Two treadmill rows were added** (`anim_review.toml`):
  - `mvp_carry_7.0`, the carry layer over the sprint: the package hold stays steady over the sprint on both bodies;
  - `mvp_push_2.25`, the leant push layer over the jog at the push speed: the body leans into the push and the legs
    stride on. The jog at 0.5x is a slow, long-striding run (1.43 steps/s of 1.57 m), so a walk at the push speed
    would read better under the push, a game-side choice once a walk is in a set.

## Measures

From `raw:review/stage1/33/metrics.md` (anim-review clips, `--sources mvp`): every set loop's seam is 0.0 to 0.1
degrees (x0.0 to x0.1 of a frame step), against 23 to 59 degrees in the raw text-to-motion clips. On the treadmill
(`rates/<body>/rates.json`), every set locomotion clip plays at rate 1.0 at its speed with its feet at the ground's
speed: the jog and the strafes 4.50 m/s, the sprint 7.0 (stride-warped; it ran 7.46 and 7.33 m/s by the feet when it
was retimed by root motion). A loop's last frame is its first by construction, so the seam that matters is the step
onto the first frame: the build reports it against the median frame step (0.5 to 1.4; the reversed jog 1.6).
Measures that pass "a lowest vertex" or "a slide" below are graded against the design's lines (floor -1.2 cm for
locomotion and -1.0 cm lying, kneeling or crawling, fail under -2; foot slide 12 cm/s for a standing one-shot); a
clip past a line is a stopgap or a note, as the per-need table says.

**One-frame pops** (the set build's check since art #33's last review, `pops` in `build_report.json`: a bone rotating at
least 20 degrees in one frame step while both neighbouring steps are under a third of it). The motion review found
the first by eye: the floor clamp switched off at once 2 cm under the foot's rest pivot, so Jump_Air_Loop's right
foot, hovering on that line, flicked 53 (men) and 55 degrees (women) and back. The clamp now fades out over the next
4 cm (131c347) and the loop has none. What the check still lists on the rebuilt set:

| Clip | Pops (men / women) | What they are |
|---|---|---|
| Jog_Fwd_Loop, Jog_Bwd_Loop | 3 / 3: Foot.L 49.9/47.3 and 42.4/42.9 deg, Toe.L 36.4 | the source's heel strike and toe-off (UAL's Jog moves the foot 38 degrees in one frame on its own rig), 1.333x faster after the stride warp; the right foot's falls between two frames of the warped grid, so only the left one counts |
| Sprint_Fwd_Loop | 4 / 2: Toe.L 24.9/23.1 deg, LowerLeg 20.5-23.6 | the same, at the sprint's rate |
| Jump_Start | 10 / 11: Toe.L 64.4/55.2 deg at frame 2, both thighs 45-49 deg on the first step | the take-off at 1.48x the source's speed: the push-off's first step, and the toe clamp letting go as the ball leaves the floor; the game blends into it |
| Jump_Land (women) | 1: Foot.R 20.5 deg on the first step | the impact |
| Raise_Out | 1 / 1: Toe.R 138.1/118.8 deg at frame 9 | **a defect**: the kneeling foot's toe points straight down, where the toe clamp's pitch plane (the toe's own horizontal direction) turns round, so the clamp lifts the tip on the other side; it flips back as the foot leaves the floor. Not fixed here (see "Left for our own keys") |
| Jog_Bwd_TTM_Loop (review only, women) | 1: UpperLeg.R 51.1 deg | the failing 7x stride |

| Clip | Body | Lowest cm | Foot slide mean/max cm/s | Hands in legs cm | Verdict |
|---|---|---|---|---|---|
| Jog_Fwd_Loop, Jog_Bwd_Loop | m / w | -1.0 / -1.2 | in place (stride: 0.0 on contact) | 0 / 0 | pass |
| Strafe_*_Loop | m / w | -1.4 / -0.8 | in place (stride: 0.0 on contact; IK misses 150/109 mm in flight) | 0 / 0 | stopgap: hips 19.5 and head -15.9 degrees off the aim; the flight legs fall short |
| Sprint_Fwd_Loop | m / w | -1.4 / -1.5 | in place (stride: 0.0 on contact at 7.0 m/s; IK misses 29/37 mm in flight) | 0 / 0 | pass, note: the toe dip |
| Turn_Left, Turn_Right | m / w | -0.3 / -0.4 | 19.7 / 147 and 17.6 / 152 | 0 / 0 | the pivot over the 12 cm/s mark |
| Knockdown | m / w | -0.9 / -0.8 | 7.6 / 129 and 2.2 / 28 | 0 / 6.1 | on the floor: the lying frames settled (lowest 0.0, the first ones at most 1.4 cm up, the held last pose on it); the women's hands brush the thighs in the fall |
| Shove_Stumble | m / w | -1.2 / -0.5 | 37.7 / 79 and 39.2 / 75 | 0 / 4.5 | the stumble's steps slide in place: the game moves the body |
| Push_Upper_Loop (lean 30) | m / w | -1.8 / -1.7 | (an upper layer) | 0 / 0 | over the idle: -0.6 / -0.9, hands 0 in the legs and in each other |
| Crawl_Start | m / w | 0.0 / 0.0 | 44.6 / 72 (men) | 0.4 / 7.5 | on the floor after the settle; travels 1.17 / 0.57 m/s as it rolls |
| Crawl_Loop | m / w | 0.0 / 0.0 | (knees and hands: no foot measure; the hands skate about 65-95 cm/s, the art #33 motion review's probe) | 0 / 0 | stopgap: settled; the shins on the feet; hands hover and skate |
| Getup_Fours | m / w | 0.0 / 0.0 | 13.3 / 45 and 18.0 / 48 | 6.7 / 7.4 | on the floor; lifts off 4.5 cm mid-rise |
| Raise_In, Raise_Out, Raise_Work_Loop | m / w | -6.2, -4.5, -2.7 / -5.6, -3.7, -3.0 | under 1.2 mean | 0, 3.0 / 5.2, 7.0 | stopgap: the kneeling foot's toes, past the -2 cm line; Raise_Out's right toe flips 138/119 degrees in one frame as the knee leaves the floor (the build's pop check) |
| Pickup_Package, Putdown_Package | m / w | 0.0 / -0.3 | 17 / 122 and 18 / 133 | 1.7 / 7.0 | stopgap: the squat's shuffle past 12 cm/s; the end (start) pose does not hold a package |
| Jump_Start | m / w | -1.9 / -2.3 | (in place) | 0 / 0 | the take-off's toe dip, 4 frames; past -2 cm on the women |
| Getup_Back | m / w | 0.0 / 0.0 | 6.1 / 39 and 7.0 / 42 | 0 / 2.8 | pass |
| Jump_Air_Loop | m / w | -5.3 / -5.5 | 0.6 / 1.9 | 0 / 0 | exempt (in place); no pop since the floor clamp fades (was -18.3 / -17.2 with the right toe flicking down) |

Stride warping (build reports): the jog at 4.5 m/s plays 28 frames as 21 (rate 1.333), its planted feet at exactly
4.50 m/s, IK miss 0.0 mm, the knee never past straight; its feet scale (0.567 men, 0.525 women) is under the warn mark
of 0.6, a deviation the treadmill judged acceptable. The sprint at 7.0 m/s: rate 0.833 (men) and 0.769 (women), 2.5 and
2.31 steps/s of 2.8 and 3.03 m, scale 0.93 and 0.94 (fit ok), IK miss 0.0 mm on contact and 29/37 mm in flight.
The strafe at 4.0 steps/s: IK miss 0.0 mm on contact frames, 150 (men) and 109 mm (women) in flight. At the design's 2.9 steps/s the strafe's
steps had to grow 1.74x (men) and its legs missed by 66 mm on contact and 465 mm in flight. Meshy's backward jog fails
the stride: scale 7.1 (men) and 6.6 (women), IK misses of 487 and 734 mm on contact, its planted feet sliding 62 and
174 cm/s.

## Joins

Reported, not graded (`raw:review/stage1/33/joins_<body>.json`, measured on the rebuilt set): from the last frame of
one clip to the first of the next in the saved set, the Body (pelvis) distance and the largest world rotation of an
upper-body bone other than the fingers (the fingers differ by the source's hand shape: SMPL-H's constant relaxed curl
against UAL's fist); the change of the hip line's yaw (signed, positive to the left: a standing body's turn); for the
lying clips also the angle between the two poses' horizontal directions from the pelvis to the head (it means nothing
for a standing pose, whose pelvis-to-head line is nearly vertical). A turn ends 90 degrees round, so its join to the
idle reads the body's yaw; the game turns the body with it.

| From -> to | Pelvis cm (men / women) | Upper body deg (men / women), the worst bone | Hips yaw deg | Lying heading deg |
|---|---|---|---|---|
| Knockdown to Getup_Back | 48.1 / 59.7 | 178.4 / 178.4, LowerArm.L | 1.8 | 0.5 / 1.4 |
| Knockdown to Crawl_Start | 55.9 / 64.5 | 172.6 / 172.6, Shoulder.L | 171.9 | **161.5 / 162.3** |
| Crawl_Start to Crawl_Loop | 16.6 / 12.4 | 88.2 / 88.1, Wrist.R | -0.6 | 17.9 / 18.0 |
| Crawl_Loop to Getup_Fours | 6.5 / 6.2 | 77.9 / 77.8, Wrist.R | 16.9 | 4.8 / 5.5 |
| Getup_Fours to Idle_Loop | 3.7 / 3.8 | 80.9 / 79.7, Wrist.R | **-33.5** | (standing) |
| Getup_Back to Idle_Loop | 17.2 / 26.8 | 7.0 / 7.2 | 0.0 | (standing) |
| Pickup_Package to Carry_Upper_Loop | 3.3 / 4.5 | 96.6 / 95.3, LowerArm.L | 6.2 | |
| Carry_Upper_Loop to Putdown_Package | 2.3 / 3.4 | 96.6 / 95.3, LowerArm.L | -6.2 | |
| Idle_Loop to Jog_Fwd_Loop | 6.9 / 8.0 | 90.8 / 90.4, UpperArm.R | 12.8 | |
| Jump_Start to Jump_Air_Loop | 13.9 / 12.4 | 35.5 / 35.5, LowerArm.R | 8.1 | |
| Jump_Air_Loop to Jump_Land | 4.6 / 4.2 | 13.9 / 13.9, Head | -1.1 | |
| Raise_In to Raise_Work_Loop | 5.3 / 7.1 | 64.8 / 64.8, Wrist.R | -0.2 | |
| Raise_Work_Loop to Raise_Out | 1.0 / 0.5 | 51.1 / 51.1, Wrist.R | 0.2 | |
| Idle_Loop to Turn_Left | 3.9 / 3.7 | 49.3 / 50.6, LowerArm.L | 13.6 | |
| Turn_Left to Idle_Loop | 11.2 / 17.2 | 135.7 / 137.1, LowerArm.L | -103.7 (the turn) | |
| Pickup_One to Idle_Loop | 4.3 / 4.5 | 18.4 / 18.4, Head | -2.1 | |
| Idle_Loop to Pickup_Package | 3.5 / 2.1 | 30.0 / 30.0, Shoulder.L | -3.9 | |
| Shove_Stumble to Idle_Loop | 4.3 / 4.5 | 40.0 / 40.0, Shoulder.L | -12.0 | |

The idle stands with its hips 13 degrees right (UAL's stance), which is in most standing joins above.

- **Getup_Fours ends with the hips 20 degrees left**, 33.5 degrees from the idle's: the game blends that turn, or
  the clip gets a `heading {facing = "end"}` once its stopgap is judged.
- **The downed chain** joins within 4 to 17 cm from the roll-up on: Crawl_Start, then Crawl_Loop, then Getup_Fours,
  then the idle. The break is the knockdown.
  - Death01 falls backwards and lies with its head behind where it stood, 48 to 60 cm away.
  - The roll-up starts lying with its head the other way (161 to 162 degrees round), since it then crawls forward
    over its head.
  - So when the knockdown ends, the game should move the body to where the knockdown's pelvis lies and turn it about
    180 degrees, to face where the head points. The roll-up then starts within about 18 degrees of the lying pose.
  - Getup_Back starts in the knockdown's own heading (0.5 to 1.4 degrees).
- **The package lift** ends with the forearms 95 to 97 degrees from the carry's. The game blends them, or the lift's
  end moves up to the carry's hold (a hand-keyed end pose).

## For the game

These points go to xperiaroco2/prime-game through its own task workflow, once the engineer approves the motion. The
clips go in as assets with manifests in a later PR.

- **Locomotion: a BlendSpace2D.**
  - The points are `Idle` (0, 0), `Jog_Fwd` (0, 1), `Jog_Bwd` (0, -1), `Strafe_Left` (-1, 0) and `Strafe_Right`
    (1, 0), with the time scale at speed / 4.5.
  - The diagonals blend between the points. The remote body has 8 directions and changes velocity instantly, so the
    blend position needs a short smoothing (about 0.1 s) or the legs pop.
  - Sprint: `Sprint_Fwd` at rate 1.0 at 7.0 m/s. Backward and sideways run the 4.5 clips at x1.556 until the
    engineer decides (below).
  - The strafes run with the hips 19.5 degrees towards the travel and the head 15.9 degrees the other way (the
    remote body turns only its head's pitch): until a re-roll, a strafing remote player looks turned off its aim.
- **Import**: the set's GLB at `animation/fps = 30` (it is baked at 30; at Godot's resampling to 24 the fastest joints
  lose up to about 20 degrees) with the AnimationPlayer's optimizer off (`docs/godot.md`).
- **Upper-body layers: an AnimationTree Blend2 with a bone filter.**
  - The filter is `Torso` and every bone below it; `build_report.json` lists them as `upper_bones`.
  - `Carry_Upper` runs at weight 1 while the package is held. Move `CARRY_POINT` from 0.72 m out to the clip's hands,
    about 0.3 m in front of the belly, through a contract socket.
  - `Push_Upper` runs at a low weight (about 0.3 to 0.5) while two bodies are in contact. `Talk_Upper` runs at a low
    weight while the player speaks.
  - `Knife_Swing` is a OneShot through the same filter on `Swung`.
  - The layers export every bone. The game masks them; never play `Push_Upper` on the full body, it bends 76 degrees.
- **Contact detection** (game side; the snapshot has no push flag): infer a push from two bodies in contact.
  - The pushed body plays `Shove_Stumble` once when contact starts and moves at the push speed (2.25 m/s). The clip's
    feet travel about 1.1 m/s, so its steps slide at that speed.
  - The pusher gets the push layer.
- **Lower-body turn logic.**
  - While standing, the lower body holds its yaw as the look turns. When the difference passes about 60 to 90
    degrees, it plays `Turn_Left` or `Turn_Right` (90 degrees, 1.2 s) and turns the body's yaw with the clip.
  - The clip ends 90 degrees round with the pelvis 11 to 17 cm off, so the game takes the clip's last facing as the
    new yaw.
  - The upper body and the head follow the look; the head pitch is procedural.
- **Jump.** Play `Jump_Start` (0.27 s) on take-off, `Jump_Air` while airborne and `Jump_Land` (0.3 s) on landing. All
  three are in place: the game lifts the body, and blends into the take-off's opening crouch and out of the landing's
  closing one.
- **Downed.**
  - `Knockdown` (1.33 s) plays on KnockedDown. The game then moves the body by the clip's 0.48 m offset and turns it
    round, as in the joins above.
  - The last pose holds while lying (giving up as well). `Crawl_Start` plays on the first move, then `Crawl` at rate
    speed / 1.0, the body turning toward its velocity. The stopgap crawl's hands skate on the ground (they sweep
    about 20 cm a cycle while the body moves 1.1 m).
  - On Revived: `Getup_Back` if the player never crawled, `Getup_Fours` after a crawl. Both blend out once the player
    moves.
- **Raise.** RaiseStarted plays `Raise_In`, then `Raise_Work` loops; RaiseStopped plays `Raise_Out`.
- **Items.**
  - ItemPickedUp plays `Pickup_One` or `Pickup_Package`; ItemPlaced plays `Putdown_One` or `Putdown_Package`.
  - The one-handed item attaches at about 0.45 s, the lowest point of the hand.
  - `Pickup_Package` blends into the carry layer.

## Left for our own keys

These are outside this task, in order of need:

- the downed breathing loop (on Knockdown's last pose);
- the right-hand grip and the swap (belt draw);
- the raise: the kneeling foot's toes out of the floor, and a calmer work loop (a ping-pong of the kneeling work, or
  keys) in place of the 27-degree seam; Raise_Out's toe flip (138/119 degrees in one frame) goes with the toes, or with
  a retarget fix: the toe clamp pitching about the foot's own side-to-side axis instead of the plane of the toe's
  horizontal direction, which turns round when the toe points straight down (it changes every clip's toes a little,
  so it is a task of its own);
- the package lift's end pose up to the carry's hold (it also mends the put-down, its reverse), and its feet's shuffle;
- the women's hands on Jump_Land (7.3 cm in the thighs), Pickup_One (2.5 cm), Pickup_Package (7.0 cm), Knockdown's
  fall (6.1 cm) and Getup_Fours's rise (7.4 cm): the 12-degree arm offset did not clear the first two;
- the toe dips the resampling leaves (Jump_Start 1.9/2.3 cm, the strafes and the sprint about 1.4): the retarget's toe
  lift run again after a retime, trim or stride;
- the gestures after the MVP, and the first-person arms (the game side).

## Meshy spend

| Batch | What | Credits | Balance |
|---|---|---|---|
| 2026-10-b5-anim-mvp (this task) | seven prime text-to-motion clips, 10 credits each, every task charged as estimated (`log.csv`, each item's `generation.json`; tasks in `docs/meshy.md`) | 70 of the approved 70 | 315 before, 245 after |
| 2026-10-b4-animations (art #25, reused) | the prime text-to-motion crawl (`crawl-motion`), part of that batch's 59 | 10 | 328 to 318 on 2026-10-03 |
| Re-roll reserve (approved with batch 5) | not spent | 0 of 30 | |

The MVP's motion cost 80 credits of text to motion in all: 70 here and batch 4's crawl. The reserve was approved for
re-generating a batch-5 clip that fails review: it covers three of the batch-5 candidates below (the roll-up, the
backward jog, then the strafe or the get-up). Batch 4's crawl is not a batch-5 clip, and the approval said it would be
cleaned up for free, so its re-roll needs the engineer's yes (10 credits) or the manager's recorded reading that it
counts under the reserve.

## Re-roll candidates

The manager runs a re-roll batch; no prompt names a game or a character. In order of need:

1. **rollup-to-all-fours** (need 23; a stopgap ships). Measured:
   - the source floats on its own mannequin (3-17 cm);
   - on our rig the lowest vertex is 7.8 cm (men) to 13.7 cm (women) above the floor at best;
   - it ends on all fours with the wrists 23-28 cm up and the pelvis at 0.60 m (the crawl's 0.44-0.54);
   - the settle brings the lowest vertex to the floor, but the hands never reach it.

   Prompt: "A person lies flat on their back on the ground, the back, head, arms and legs all resting on the ground.
   Slowly, as if hurt, they roll over onto their side and then onto their stomach, staying low against the ground,
   then push up onto hands and knees: palms flat on the ground under the shoulders, knees and shins on the ground under
   the hips. They stay there on all fours, head hanging low, breathing heavily."
2. **crawl** (need 24, batch 4: the engineer's yes; a stopgap ships). Measured:
   - no cycle of 0.5 to 3 s repeats: the best cut (0.93 s) has a raw seam of 26.4 degrees in the left wrist, and
     longer cuts 37 to 40;
   - it heads 20 degrees off straight and floats 3 to 5 cm;
   - its hands skate: the wrists sweep 17-25 cm a cycle while the body crawls 1.1 m.

   Prompt: "A hurt person crawls forward on hands and knees in a perfectly straight line at a slow, steady pace, palms
   flat on the ground under the shoulders, knees on the ground under the hips, body low, head up looking ahead, the
   hands and knees moving in an even alternating rhythm; each hand stays planted on the ground until it lifts for the
   next reach. A repeating crawl cycle of about one second that starts and ends in the same pose, no looking around,
   no turning."
3. **backward-jog** (need 3; the reversed jog is a stopgap). Measured:
   - 1.25 m in 3.97 s (0.31 m/s; its best cycle 0.56-0.70 m/s), steps of 0.09-0.30 m;
   - stride warping to 4.5 m/s needs 6.6-7.1x the step length, against the stride's fail limit of 2.5x.

   Prompt: "A person runs backwards fast in a straight line, covering about four metres every second, with long
   backward strides and a short flight phase between steps, pushing off the balls of the feet, knees bent, torso
   leaning slightly forward, chest and head facing straight ahead, arms bent and pumping. An even, repeating running
   cycle that starts and ends in the same pose."
4. **getup-from-all-fours** (need 25's crawl case; a stopgap ships, so this one only if the review rejects it).
   Measured:
   - it floats 6-13 cm (its standing pelvis 1.09 m against 0.97);
   - after the settle the lowest vertex reaches the floor but lifts 4.5 cm mid-rise.

   Prompt: "A person kneels on hands and knees on the ground, palms flat and knees and shins resting on the ground.
   Tired and a little hurt, they push up with the arms, bring one foot forward flat on the ground, stand up and end
   standing relaxed with both feet flat on the ground and the arms at the sides, about one and a half seconds."

5. **strafe-left** (need 4; a stopgap ships). Measured: it runs 17 degrees forward of sideways; turned so it
   travels sideways, its hips face 19.5 degrees towards the travel and its head 15.9 the other way, 35 apart, so no
   single turn puts both on the aim; a crossing gallop of long and short steps.

   Prompt: "A person runs sideways to their left in a straight line at a steady running pace, chest, hips and head
   facing straight ahead the whole time, moving directly sideways: the left foot steps out to the left and the right
   foot closes up beside it without crossing, a short flight phase between steps, arms bent and relaxed. An even,
   repeating side-stepping cycle that starts and ends in the same pose."

## Questions for the engineer and the designer

- **The strafe's turned body** (look at `rates/<body>/mvp_strafe_left_4.5.mp4` and `Strafe_Left.mp4` in
  `frames/<body>/clips/`). Its hips face 19.5 degrees towards the travel and its head 15.9 the other way.
  - Options: (a) ship it as the stopgap it is; (b) turn it so the head faces the aim (the travel then runs 16 degrees
    off sideways and the hips 35 degrees off); (c) re-roll it from the reserve with the prompt above.
  - Recommendation: (a) for the first playable, (c) with the reserve's third slot.
- **The crawl's re-roll** is batch 4's clip, outside the reserve's approval: 10 credits with your yes, or wait.

- **Sideways and backward at 7.0 m/s.** At the decided 1.556x the strafe runs 6.2 steps/s and the backward jog 4.4:
  likely a whirl.
  - Options: separate 7.0 m/s bakes (one more settings entry each, stride to 1.6-2.2 m steps), or a forward-only
    sprint.
  - Recommendation: separate bakes once the strafe and the backward clip are approved.
- **The strafe's cadence.** It runs 4.0 steps/s at 4.5 m/s (the design said 2.9), which keeps the legs within reach.
  Judge it on the treadmill (`rates/<body>/mvp_strafe_left_4.5.mp4`).
- **The carry's arms** open 29 to 30 degrees for a 0.40 m gap between the hands, a tray under the box: judge it in
  `pairs/<body>/mvp_package.mp4`. The game's package is 0.45 m; a side grip would set the gap to 0.45 (the designer's
  call). Decided (art #65): a side grip at 0.45 m, the lift and the put-down ending and starting in it.
- **The package pick-up and put-down** ship as stopgaps (the end pose does not hold a package): blend into the carry
  in the game, or hand-key an end pose (recommended, small).
- **The shove's speed.** Retime it to 2.25 m/s (0.69 s) so its steps match the push, or keep 1.47 s? Decided (art
  #65): 0.69 s, built as 0.7 s (21 frames at 30 fps).
- **The push's lean** (new): 30 degrees from Torso, judge it in `pairs/<body>/mvp_layers.mp4`. More lean lowers the
  hands toward the chest, less brings them up toward the head.
- **The stopgaps in the downed chain** (the roll-up, the crawl, the get-up from all fours): ship them for the first
  playable, or wait for the re-roll?

## Deviations from the design

- `Jog_Bwd_Loop` is the warped forward jog reversed (the design's review candidate), and Meshy's backward jog is the
  review candidate `Jog_Bwd_TTM_Loop`: its stride fails as predicted.
- The strafe runs at 4.0 steps/s, not 2.9 (the IK misses above), with 1.12 m steps against the design's 1.5-1.7 m.
- The sprint is stride-warped to 7.0 m/s instead of retimed by its root motion (its feet ran 6-7 % fast).
- The knockdown gets a settle on its lying frames after the lift (the lift alone left them 2-4.5 cm up).
- The `cycle` cut solves the legs again after closing (the crawl's ankles tore 15 cm without it).
- The crawl and the raise loop are closed over raw seams of 26 and 27 degrees (`max_raw_seam_deg = 30`), flagged as
  stopgaps: no cut stays under 15.
- New in the build: open source loops are closed, and every clip is recentred over the origin (docs/animations.md).
- New edits: `floor {mode = "settle"}` for clips that float (the crawl, the roll-up, the get-up), and `lean` for an
  upper layer whose source leans with the hips (the push).
- The roll-up and the get-up from all fours ship as flagged stopgaps after the review, not as review candidates, and
  stay re-roll candidates.
