# The animations judged in motion: the pack's 24 against the Universal Animation Library (art #20, 2026-10-03; UAL2, art #24)

The Ultimate Modular pack's own actions against Quaternius' Universal Animation Library Standard (UAL1) retargeted onto
our skeleton, every clip played on an unmodified pack character of each body type (men: `Business Man.glb`, women:
`Suit.glb`), measured, and looked at as 12-frame front and side strips, looping clips and side-by-side pairs. The
method and the commands are in [../animations.md](../animations.md); the pictures and clips are outside git in
`D:/prime-art-raw/review/stage1/20/` (`strips/`, `clips/`, `pairs/`, `rates/`, `sheets/`, `metrics.json`,
`inventory.json`). The numbers below are from the run after the review fixes of the PR (the hips anchor, the hand
measures, the game's speeds). The second library, **UAL2 Standard**, was judged with the same tools in art #24: see
"UAL2 Standard (art #24)" below; its pictures and clips are in `D:/prime-art-raw/review/stage1/24/`. The needs table, the
gaps and the recommendation below include it.

## Summary

- **UAL retargets cleanly onto both bodies.** The rest check passes (0.003 mm, 0 degrees); walks, runs, crouches and
  idles keep their feet on the floor (lowest vertex -0.1 to -0.8 cm) with little sliding (UAL Walk_Loop 2.4 cm/s mean
  on the men against 12.0 for the pack's Walk); a fall stays near the floor (Death01 -4.9/-3.4 cm, less than UAL's own
  mannequin); fingers curl the right way and point (Interact), and the same motion plays on both bodies, scaled to
  their legs.
- **UAL is the better base for almost every need the game has**, but **no clip in either set fits the game's 4.5 m/s
  "walk" as it stands**. Matched to the ground on a treadmill, UAL's Jog plays at 0.81x (men) or 0.76x (women): 1.6 to
  1.7 steps a second with 2.6 to 2.8 m steps, a slow-motion bound, where a real run at 4.5 m/s takes about 2.7 to
  2.9 steps a second. A Walk_Loop and Jog blend at 1.0x is better (2.0 steps/s, 2.3 m steps); the pack's Run at 1.5x
  to 1.8x whirls (3.7 steps/s, 1.2 m steps). The sprint fits better: Sprint_Loop at 0.82x/0.76x (2.3 to 2.5 steps/s).
  The way out is shortening UAL's strides at a natural cadence (see "Locomotion at the game's speeds"). The pack's
  Walk has stiff "swimming" arms with flat hands; its idles look stiff.
- **The pack keeps a few clips UAL lacks:** Wave (open five-finger hand), Sword_Slash (the best knife swing), Run_Back
  (the only backward locomotion), HitRecieve_2 (a clear hit read) and the cartoony Death.
- **Gaps in both free sets of art #20:** carrying the two-handed package, crawling and the downed state, getting up,
  strafes and backward walking, a floor pickup, emotes beyond a wave and a dance, and the first-person arm set.
- **UAL2 Standard (art #24, free, CC0, UAL1's rig exactly) fills four of them and part of a fifth:** the carry
  (Walk_Carry_Loop, and its upper body layered over the idle and over the game's walk), the lying pose and the get-up
  after a revive (LayToIdle) and a thumbs-up (Yes); the floor pickup and put-down (Farm_Harvest, Farm_PlantSeed) only
  for one-handed items: both reach the floor with the right hand while the left rests on the knee, so the two-handed
  package needs a two-hand arm layer over the bend. Plus folded arms and a head-shake idle, a big knockdown (Hit_Knockback) and a throw for later (OverhandThrow). It has **no** idle
  carry, wave or crawl (the itch.io previews name IDLE_CARRY and WAVE, which the Standard files do not hold), and its
  knockback is a knockdown, not a push. **Still gaps:** crawling, strafes and backpedal, turning in place, being pushed
  (a stagger), picking up and putting down the package with both hands, most emotes (clap, cheer, shrug, laugh) and the first-person arm set. UAL1 Pro ($9.99 or more) itemises
  crawling and 8-direction locomotion.
- **To fix on any chosen clip:** stride length at the game's speeds; hand spacing for the big Ultimate Modular hands
  (Idle_Talking_Loop's hands pass 2.2 cm into each other, the pistol grip 2.3 cm); the women's arms (their fists press
  1 to 5 cm into the thighs in UAL's idles, walks and Interact, and their hands overlap in Push_Loop and the jab:
  UAL's arm poses come from a wider-shouldered body); a small floor clamp for lying clips (UAL Death01 5/3 cm, the
  pack's Death 6.5 to 8 cm); guard fists inside the big stylized heads (UAL punches 3.5 to 8 cm); forearm twist over
  60 degrees in a few UAL clips (no twist bones).

## Inventory

| Source | Clips | Facts (measured by `anim-review inventory`) |
|---|---|---|
| Ultimate Modular Men | 24 actions, 24 fps keys | Identical in 10 of the 11 files; `Adventurer.glb`'s 24 all differ (that character is bound 180 degrees off). Lengths 0.54 s (HitRecieve) to 1.67 s (Idle, Wave) |
| Ultimate Modular Women | the same 24 names | Identical in all 10 files; other motions than the men's (pose differences of 9 degrees in Idle_Neutral to 145 in the kicks) and 25% longer (Idle 2.08 s, Walk 1.67 s) |
| UAL1 Standard, `UAL1_Standard.glb` | 43 clips at 30 fps, 65 bones | Root motion disabled (the root never moves; the pelvis travels in Death01 0.46 m, the sitting clips 0.25 m); 19 clips named `_Loop` (and Sword_Idle loops); 0.17 s (the three pistol aims) to 5.2 s (Fixing_Kneeling) |
| UAL1 Standard, `UAL1_Standard_RM.glb` | the same 43 | Root motion in 10 clips: Crouch_Fwd_Loop 0.75 m/s, Death01 0.27 m/s, Jog_Fwd_Loop 5.36 m/s, Push_Loop 0.3 m/s, Roll 3.4 m/s, Sprint_Loop 8.25 m/s, Swim_Fwd_Loop 2.17 m/s, Sword_Attack 0.98 m/s, Walk_Formal_Loop 0.97 m/s, Walk_Loop 0.97 m/s |

Licences: both packs and UAL are CC0 1.0 (UAL: the zip's `License.txt`; record
`sources/quaternius_ual1_standard.toml`; the packs' records come with #17). The itch.io page counts 45 free UAL
animations; the files hold 43.

## Measures and verdicts per clip

Both body types on one row (men / women). Definitions in [../animations.md](../animations.md#measures-anim_metricspy-anim_mathpy):
ground speed is the treadmill speed of an in-place clip; foot slide is the foot bone's contact velocity against it
(`-` where fewer than 4 contact velocities back it); lowest is the lowest vertex (the floor is 0); hands are the
deepest hand vertex inside the torso's or the head's convex hull, behind the other hand's faces, or behind the legs'
faces (a hand resting on a thigh reads 1 to 2 cm); the seam compares the last frame with the first (a clean loop is
about one frame step); past straight is the knee bent backwards in its hinge plane (elbows are left out: see the
notes); finger curl is the mean phalanx rotation per hand (UAL keeps loose fists, about 78 degrees, in most clips;
the pack's fists are 101 degrees, its open hands 0 to 6).

| Source | Clip | Loop | s (men / women) | Ground m/s | Foot slide mean/max cm/s (men; women) | Lowest cm | Hands in torso/head/other hand/legs cm (men; women) | Seam deg (x frame step) | Knee past straight deg | Forearm twist deg | Finger curl deg | Visual verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pack | Death | no | 1.03 / 1.33 | 0.22 / 0.20 | 40.3/63.3; 32.3/53.3 | -6.5 / -8.0 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.8 | 95.1 / 94.8 | 0.0 / 0.0 | 26.5 / 26.5 | 0.0-1.8 | Sits back and falls flat on the back, arms splayed into a T on the floor; cartoony, readable. Slides back 68 cm and sinks 6.5/8.0 cm into the floor: needs the floor clamp |
| pack | Gun_Shoot | no | 0.60 / 0.73 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.2 / 0.2 | 0.0 / 0.0 | 0.5 / 0.5 | 0.0-41.0 | Arm straight out, small recoil. Not needed (no guns) |
| pack | HitRecieve | no | 0.53 / 0.70 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/2.5 | 1.7 / 0.3 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0-1.8 | Small flinch with a hand to the thigh; weak read at distance |
| pack | HitRecieve_2 | no | 0.53 / 0.70 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/1.1 | 0.9 / 0.1 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0-1.8 | Head snaps back, torso arches: a clear hit read |
| pack | Idle | yes | 1.67 / 2.07 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.3 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/1.3 | 0.0 (x0.1) / 0.0 (x0.0) | 0.0 / 0.0 | 0.0 / 0.0 | 0.0-6.4 | Stiff stance, elbows out, open flat hands; the motion is fine, the frozen frame looks twisted (known) |
| pack | Idle_Gun | yes | 1.67 / 2.07 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.3 | 0.0/0.0/0.0/0.1; 0.0/0.0/0.0/1.3 | 0.0 (x0.0) / 0.0 (x0.1) | 0.0 / 0.0 | 0.0 / 0.0 | 5.2-40.5 | One hand held forward, near static. Not needed |
| pack | Idle_Gun_Pointing | yes | 1.67 / 2.07 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.3 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/1.3 | 0.0 (x0.1) / 0.0 (x0.1) | 0.0 / 0.0 | 0.0 / 0.0 | 5.2-41.0 | Arm straight forward pointing; a static pointing pose |
| pack | Idle_Gun_Shoot | no | 0.67 / 0.83 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.6 | 0.1 / 0.0 | 0.0 / 0.0 | 0.3 / 0.3 | 5.3-41.0 | Pointing pose with recoil. Not needed |
| pack | Idle_Neutral | yes | 1.67 / 2.07 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.1 / -0.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 (x0.2) / 0.0 (x0.4) | 0.0 / 0.0 | 0.0 / 0.0 | 0.0-1.8 | Upright, arms down, almost still: the neutral pose; good base for overlays |
| pack | Idle_Sword | yes | 1.67 / 2.07 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.3 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/1.3 | 0.0 (x0.1) / 0.0 (x0.1) | 0.0 / 0.0 | 0.0 / 0.0 | 5.2-101.2 | Static guard with a fist: a one-handed hold candidate |
| pack | Interact | no | 1.27 / 1.60 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.3 / -0.3 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.5 / 0.0 | 0.0 / 0.0 | 1.3 / 1.3 | 0.0-5.4 | Raises the right palm forward and back: a vague touch; UAL Interact reads better |
| pack | Kick_Left | no | 0.93 / 1.17 | 0.07 / 0.06 | 48.7/223.6; 44.2/228.5 | -1.6 / -0.9 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 2.1 / 0.1 | 0.0 / 0.0 | 1.0 / 1.0 | 101.2-101.2 | Front kick with flailing arms; cartoony; feet slide (max 2.2 m/s). Not needed |
| pack | Kick_Right | no | 0.93 / 1.17 | 0.07 / 0.06 | 48.7/223.6; 44.2/228.5 | -1.6 / -0.9 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 2.1 / 0.1 | 0.0 / 0.0 | 1.0 / 1.0 | 101.2-101.2 | Mirror of Kick_Left. Not needed |
| pack | Punch_Left | no | 0.83 / 1.03 | 0.00 / 0.00 | 1.6/17.7; 1.8/21.6 | -0.2 / -0.3 | 0.0/0.0/0.6/0.0; 0.0/0.0/1.7/0.0 | 0.0 / 1.8 | 0.0 / 0.0 | 1.0 / 1.0 | 101.2-101.2 | Hook-like punch with a raised elbow; ok. Not needed (no fists in the rules) |
| pack | Punch_Right | no | 0.83 / 1.03 | 0.00 / 0.00 | 1.6/17.7; 1.8/21.6 | -0.2 / -0.3 | 0.0/0.0/0.7/0.0; 0.0/0.0/1.7/0.0 | 0.0 / 1.8 | 0.0 / 0.0 | 1.0 / 1.0 | 101.2-101.2 | Mirror of Punch_Left |
| pack | Roll | no | 1.33 / 1.67 | 1.12 / 0.99 | 129.0/354.6; 103.0/298.9 | -19.4 / -9.2 | 0.0/5.7/0.0/1.4; 0.0/2.3/0.0/4.7 | 1.9 / 1.9 | 0.0 / 0.0 | 31.8 / 34.4 | 0.0-101.2 | Dive roll on the spot (no root motion) and up; sinks 19/9 cm; a stunt. Not needed |
| pack | Run | yes | 0.80 / 1.00 | 3.09 / 2.45 | 33.1/84.0; 30.5/97.4 | -0.3 / -0.3 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 18.4 (x1.0) / 12.5 (x0.8) | 0.0 / 0.0 | 1.8 / 1.8 | 101.2-101.2 | Solid run with pumping arms (men), lighter arms (women); seam ok. Ground 3.1/2.5 m/s: 1.5x/1.8x needed for the game's 4.5 m/s |
| pack | Run_Back | yes | 0.83 / 1.03 | 3.09 / 2.46 | 33.4/84.0; 30.2/77.1 | -0.3 / -0.3 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 (x0.0) / 1.6 (x0.1) | 0.0 / 0.0 | 1.8 / 1.8 | 101.2-101.2 | Backward run, readable: the only backward locomotion in the two sets |
| pack | Run_Left | yes | 0.80 / 1.00 | 3.09 / 2.45 | 33.1/84.0; 30.5/97.4 | -0.3 / -0.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.2 | 18.4 (x1.0) / 12.5 (x0.8) | 0.0 / 0.0 | 1.8 / 1.8 | 101.2-101.2 | The run turned 90 degrees, not a side-step strafe: the body faces the movement |
| pack | Run_Right | yes | 0.80 / 1.00 | 3.09 / 2.45 | 33.1/84.0; 30.5/97.4 | -0.3 / -0.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.3 | 18.5 (x1.0) / 12.5 (x0.8) | 0.0 / 0.0 | 1.8 / 1.8 | 101.2-101.2 | As Run_Left, mirrored |
| pack | Run_Shoot | yes | 0.83 / 1.03 | 3.09 / 2.45 | 33.1/84.0; 30.5/97.4 | -0.3 / -0.3 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.7/0.0 | 0.0 (x0.0) / 2.5 (x0.2) | 0.0 / 0.0 | 1.8 / 1.8 | 101.2-101.2 | Run with the right arm pointing forward |
| pack | Sword_Slash | no | 1.00 / 1.30 | 0.00 / 0.00 | 18.9/107.9; 15.2/93.4 | -0.4 / -0.5 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/2.7 | 0.4 / 0.0 | 0.0 / 0.0 | 0.3 / 0.3 | 2.8-101.2 | One-handed horizontal slash, readable: the best knife swing of both sets; feet slide (max 1.1/0.9 m/s): pin them |
| pack | Walk | yes | 1.33 / 1.67 | 1.37 / 1.10 | 12.0/23.7; 9.8/22.6 | -1.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/3.7 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0 / 0.0 | 5.0 / 5.2 | 2.2-4.1 | Stiff 'swimming' arms: flat open hands swinging far back and front; 1.37/1.10 m/s; the women's hands brush 3.7 cm into the thighs |
| pack | Wave | no | 1.67 / 2.07 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.3 / -0.3 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.9 | 0.0 / 1.6 | 0.0 / 0.0 | 0.8 / 0.8 | 1.1-6.0 | Raises the right arm and waves an open five-finger hand: good on both bodies |
| ual | A_TPose | no | 2.50 / 2.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.1 / -0.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0-0.0 | The rest pose exactly: the retarget's rest check in motion |
| ual | Crouch_Fwd_Loop | yes | 2.00 / 2.00 | 0.75 / 0.80 | 15.6/67.9; 16.9/71.9 | -0.7 / -0.8 | 0.0/0.0/0.0/7.9; 0.0/0.0/0.0/6.9 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0 / 0.0 | 24.5 / 24.5 | 19.2-21.8 | Deep sneaking crouch walk, natural; toes kept out of the floor; hands 7 to 8 cm into the thighs at the deepest crouch. The game has no crouch yet |
| ual | Crouch_Idle_Loop | yes | 2.93 / 2.93 | 0.00 / 0.00 | 0.3/0.5; 0.3/0.6 | -0.7 / -0.8 | 0.0/0.0/0.0/0.2; 0.0/0.0/0.0/2.1 | 0.0 (x0.2) / 0.0 (x0.1) | 0.0 / 0.0 | 24.5 / 24.5 | 19.2-26.9 | Deep crouch idle, natural |
| ual | Dance_Loop | yes | 1.00 / 1.00 | 0.00 / 0.00 | 0.0/0.6; 0.0/0.1 | -0.2 / -0.3 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0 / 0.0 | 1.2 / 1.2 | 77.9-77.9 | Small bouncing groove with fists: a simple dance emote |
| ual | Death01 | no | 2.40 / 2.40 | 0.00 / 0.00 | 4.3/89.8; 3.9/97.7 | -4.9 / -3.4 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/5.3 | 134.3 / 134.3 | 0.0 / 0.0 | 83.8 / 83.8 | 4.4-77.9 | Staggers, buckles and falls on the back, 2.4 s: the best canned knockdown. Goes 4.9/3.4 cm into the floor while lying, less than UAL's own mannequin scaled to the body (8.3/9.0 cm): a small floor clamp; the women's hand presses 5 cm into the thigh in the fall |
| ual | Driving_Loop | yes | 1.67 / 1.67 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.4 / -0.5 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.1 (x0.3) / 0.1 (x0.3) | 0.0 / 0.0 | 59.9 / 59.9 | 77.9-77.9 | Seated steering. Not needed |
| ual | Fixing_Kneeling | no | 5.20 / 5.20 | 0.00 / 0.00 | 0.2/9.9; 0.2/10.7 | -4.6 / -6.0 | 0.0/0.0/0.0/3.0; 0.0/0.0/0.0/6.9 | 0.9 / 0.9 | 0.0 / 0.0 | 80.9 / 80.9 | 17.8-77.9 | Kneels, works with both hands at the floor, stands up (5.2 s): fits floor tasks and raising a downed player; knee 4.6/6.0 cm into the floor (UAL's own mannequin 4.0/4.3), hands on the thighs while kneeling |
| ual | Hit_Chest | no | 0.33 / 0.33 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.7 | 13.5 / 13.5 | 0.0 / 0.0 | 0.9 / 0.9 | 54.3-77.9 | Short knock back from the chest (0.33 s): subtle |
| ual | Hit_Head | no | 0.43 / 0.43 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.7 / -1.0 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/1.0 | 13.7 / 13.7 | 0.0 / 0.0 | 0.9 / 0.9 | 54.1-77.9 | Short head knock (0.43 s): subtle |
| ual | Idle_Loop | yes | 2.50 / 2.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/1.3 | 0.4 (x0.6) / 0.4 (x0.7) | 0.0 / 0.0 | 0.9 / 0.9 | 77.9-77.9 | Relaxed staggered stance, loose fists, breathing: natural; the same wide stance on both bodies (a look point for the women, who also touch the thighs with the fists, 1.3 cm) |
| ual | Idle_Talking_Loop | yes | 2.93 / 2.93 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.7 | 0.0/0.0/2.2/0.0; 0.0/0.0/2.2/0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0 / 0.0 | 52.2 / 52.2 | 11.7-58.6 | Hands gesture in front of the chest with open, moving fingers: made for proximity voice, but the big hands pass 2.2 cm into each other on both bodies: needs a hand-spacing offset |
| ual | Idle_Torch_Loop | yes | 1.27 / 1.27 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/1.3 | 0.0 (x0.1) / 0.0 (x0.1) | 0.0 / 0.0 | 28.0 / 28.0 | 55.2-77.9 | Holds an item forward in the right hand: a one-handed hold pose |
| ual | Interact | no | 2.00 / 2.00 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.9 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/4.9 | 0.0 / 0.0 | 0.0 / 0.0 | 60.6 / 60.6 | 59.2-77.9 | Reaches forward and presses with the index finger: the best interact; forearm twist 61 degrees; on the women the fist digs 4.9 cm into the thigh at the start and the end |
| ual | Jog_Fwd_Loop | yes | 0.93 / 0.93 | 5.95 / 6.42 | 5.7/12.0; 5.8/8.1 | -0.1 / 0.0 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.7 (x0.0) / 0.7 (x0.0) | 0.0 / 0.0 | 3.9 / 3.9 | 77.9-77.9 | Long-stride run with a flight phase, clean loop, feet clean: 5.95/6.42 m/s in place, 5.54/5.96 by root motion. At the game's 4.5 m/s it plays at 0.81x/0.76x: 1.74/1.62 steps/s with 2.6/2.8 m steps, a slow-motion bound (see the game's speeds) |
| ual | Jump_Land | no | 1.27 / 1.27 | 0.00 / 0.00 | 0.4/8.4; 0.3/2.1 | -0.6 / -0.8 | 0.0/0.0/0.0/4.5; 0.0/0.0/0.0/5.9 | 95.6 / 95.6 | 0.0 / 0.0 | 27.7 / 27.7 | 12.9-77.9 | Absorbs the landing in a crouch and stands: good; the hands touch the thighs in the crouch (4.5/5.9 cm) |
| ual | Jump_Loop | yes | 2.50 / 2.50 | 0.00 / 0.00 | 0.6/1.9; 0.6/2.0 | -18.3 / -17.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.1 (x0.1) / 0.0 (x0.1) | 0.0 / 0.0 | 27.7 / 27.7 | 12.9-23.0 | Airborne pose, arms out; in place the feet hang 17 to 18 cm below the floor (the game's jump lifts the body) |
| ual | Jump_Start | no | 1.33 / 1.33 | 0.05 / 0.06 | 29.6/167.1; 23.1/150.4 | -2.2 / -16.0 | 0.0/0.0/0.0/1.0; 0.0/0.0/0.0/6.6 | 109.4 / 109.1 | 0.0 / 0.0 | 27.7 / 27.7 | 12.9-77.9 | Crouch, push off, airborne pose: good; in place the feet go below the floor once airborne (2/16 cm; the game's jump lifts the body) |
| ual | PickUp_Table | no | 0.83 / 0.83 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/2.1 | 0.0 / 0.0 | 0.0 / 0.0 | 0.9 / 0.9 | 25.4-77.9 | Reaches to waist height and brings the item to the chest: a table pickup, not a floor pickup |
| ual | Pistol_Aim_Down | no | 0.17 / 0.17 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/2.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 78.1 / 78.1 | 40.2-54.0 | Single aim pose (0.17 s), two-hand grip, index finger extended. Not needed |
| ual | Pistol_Aim_Neutral | no | 0.17 / 0.17 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/1.9/0.0; 0.0/0.0/0.0/0.0 | 0.1 / 0.0 | 0.0 / 0.0 | 78.1 / 78.1 | 40.2-54.0 | Single aim pose. Not needed |
| ual | Pistol_Aim_Up | no | 0.17 / 0.17 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/2.1/0.0; 0.0/0.0/0.0/0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 80.6 / 80.6 | 40.2-54.0 | Single aim pose. Not needed |
| ual | Pistol_Idle_Loop | yes | 1.67 / 1.67 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/2.3/0.0; 0.0/0.0/0.0/0.0 | 0.0 (x0.1) / 0.0 (x0.1) | 0.0 / 0.0 | 81.6 / 81.6 | 40.2-54.0 | Two-handed grip at chest height; the men's hands pass 2.3 cm into each other: nearest to a two-hand hold, but not a carry |
| ual | Pistol_Reload | no | 1.67 / 1.67 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/2.3/0.0; 0.0/0.0/1.1/0.0 | 0.1 / 0.0 | 0.0 / 0.0 | 97.1 / 97.1 | 8.7-54.0 | Hands meet and part; forearm twist 97 degrees. Not needed |
| ual | Pistol_Shoot | no | 0.63 / 0.63 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/2.3/0.0; 0.0/0.0/0.0/0.0 | 0.1 / 0.0 | 0.0 / 0.0 | 78.1 / 78.1 | 40.2-54.0 | Recoil from the grip. Not needed |
| ual | Punch_Cross | no | 1.00 / 1.00 | 0.00 / 0.00 | 1.5/48.0; 0.3/8.5 | -0.4 / -0.7 | 0.0/5.2/0.0/0.0; 0.0/3.5/1.6/0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 11.0 / 11.0 | 77.9-77.9 | Clean guard and straight cross; guard fists 5/3.5 cm inside the big head |
| ual | Punch_Jab | no | 0.87 / 0.87 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.8 | 0.0/7.9/0.0/0.0; 0.0/6.3/6.4/0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 35.4 / 35.4 | 77.9-77.9 | Clean jab; guard fists 8/6 cm inside the big head, the women's fists 6.4 cm into each other |
| ual | Push_Loop | yes | 2.67 / 2.67 | 0.29 / 0.31 | 4.2/25.5; 4.1/27.5 | -0.8 / -0.6 | 0.0/0.0/0.0/0.0; 0.0/0.0/6.1/0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0 / 0.0 | 30.0 / 30.0 | 25.7-25.7 | Leans and pushes a heavy object step by step: the pusher of the game's push; the women's hands overlap 6.1 cm (narrower shoulders) |
| ual | Roll | no | 1.47 / 1.47 | 0.00 / 0.00 | 3.6/15.1; 3.8/16.3 | -3.1 / -1.9 | 0.9/1.2/0.0/6.7; 0.8/0.5/0.0/7.6 | 113.4 / 106.2 | 0.0 / 0.0 | 58.8 / 58.8 | 4.3-77.9 | Dive roll; in place it flies back and forth, legs short by up to 6 cm (23 cm before the hips fix). Use the root-motion file or skip |
| ual | Sitting_Enter | no | 1.30 / 1.30 | 0.00 / 0.00 | 2.7/55.1; 2.8/57.3 | -0.6 / -0.8 | 0.0/0.0/0.0/1.2; 0.0/0.0/1.8/7.2 | 92.2 / 88.8 | 0.0 / 0.0 | 59.2 / 59.2 | 0.0-77.9 | Sits onto a chair height cleanly. Not needed now |
| ual | Sitting_Exit | no | 1.03 / 1.03 | 0.00 / 0.00 | 3.8/80.1; 4.0/83.0 | -0.6 / -0.8 | 0.8/0.0/2.3/0.1; 0.8/0.0/2.1/6.4 | 92.2 / 88.8 | 0.0 / 0.0 | 96.8 / 96.8 | 3.6-77.9 | Stands up from a chair cleanly |
| ual | Sitting_Idle_Loop | yes | 1.67 / 1.67 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.7 | 0.0/0.0/0.0/0.0; 0.0/0.0/1.3/2.0 | 0.0 (x0.2) / 0.0 (x0.2) | 0.0 / 0.0 | 58.9 / 58.9 | 3.1-15.2 | Seated idle, needs a seat |
| ual | Sitting_Talking_Loop | yes | 2.93 / 2.93 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.7 | 0.0/0.0/2.3/0.0; 0.0/0.0/2.1/0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0 / 0.0 | 76.6 / 76.6 | 11.7-58.6 | Seated talking with gestures |
| ual | Spell_Simple_Enter | no | 0.53 / 0.53 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 115.8 / 115.8 | 0.0 / 0.0 | 23.2 / 23.2 | 14.5-77.9 | Raises an open hand forward: usable as a 'stop' gesture start |
| ual | Spell_Simple_Exit | no | 0.43 / 0.43 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 115.8 / 115.8 | 0.0 / 0.0 | 23.2 / 23.2 | 14.5-77.9 | Lowers the raised hand |
| ual | Spell_Simple_Idle_Loop | yes | 2.10 / 2.10 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 (x0.1) / 0.1 (x0.1) | 0.0 / 0.0 | 23.2 / 23.2 | 14.5-21.3 | Holds the open hand out: a 'stop' or 'hold on' gesture |
| ual | Spell_Simple_Shoot | no | 0.50 / 0.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.9 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.1 / 0.1 | 0.0 / 0.0 | 34.4 / 34.4 | 14.5-25.0 | A push of the open hand |
| ual | Sprint_Loop | yes | 0.67 / 0.67 | 9.04 / 9.72 | -; - | -0.1 / 0.0 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.7 (x0.0) / 0.6 (x0.0) | 0.0 / 0.0 | 3.9 / 3.9 | 77.9-77.9 | Strong forward-leaning sprint, clean: 9.0/9.7 m/s in place, 8.53/9.18 by root motion. At the game's 7.0 m/s it plays at 0.82x/0.76x: 2.46/2.29 steps/s with 2.8/3.1 m steps |
| ual | Swim_Fwd_Loop | yes | 1.33 / 1.33 | 0.08 / 0.78 | 107.6/146.8; - | -66.0 / -68.8 | 0.0/0.0/2.3/0.0; 0.0/0.0/2.1/0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0 / 0.0 | 74.2 / 74.2 | 8.3-8.3 | Swimming under the floor line. Not needed |
| ual | Swim_Idle_Loop | yes | 3.33 / 3.33 | 0.54 / 0.58 | 9.5/13.3; 10.2/14.5 | -148.7 / -157.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0 / 0.0 | 3.8 / 3.8 | 5.9-12.6 | Treading water under the floor line. Not needed |
| ual | Sword_Attack | no | 1.53 / 1.53 | 0.00 / 0.00 | 58.6/695.6; 50.4/738.7 | -0.4 / -0.7 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 25.2 / 25.2 | 17.9-77.9 | Big wind-up and a 1.5 m lunge: too heavy for a knife |
| ual | Sword_Idle | yes | 1.67 / 1.67 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.3 / -0.4 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0 / 0.0 | 14.1 / 14.1 | 17.9-77.9 | Crouched fighting stance |
| ual | Walk_Formal_Loop | yes | 1.33 / 1.33 | 1.01 / 1.08 | 2.4/19.1; 2.6/21.0 | -0.2 / -0.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/3.2 | 1.2 (x0.1) / 1.2 (x0.1) | 0.0 / 0.0 | 0.3 / 0.3 | 77.9-77.9 | Upright walk, arms close: neat; 1.0/1.1 m/s; on the women the fists press 3.2 cm into the thighs |
| ual | Walk_Loop | yes | 1.33 / 1.33 | 1.00 / 1.08 | 2.4/19.2; 2.6/21.0 | -0.1 / -0.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/3.3 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0 / 0.0 | 2.1 / 2.1 | 77.9-77.9 | Natural walk, relaxed fists, heel strike and toe-off on the floor: 1.0/1.1 m/s; on the women the swinging fists press up to 3.3 cm into the thighs |

Notes on the measures: the elbow "past straight" measure stays in `metrics.json` only: a straight arm in UAL's
punches and lunge read 17 to 32 degrees (the Roll 56 to 60) because the fixed hinge axis tilts with upper-arm twist;
the strips show straight, unbroken arms. Sprint_Loop's slide rests on a single velocity sample (5 contact frames in a
0.67 s cycle), so it is shown as `-`; its in-place ground speed is 6% above the root-motion file's (9.04 against
8.53 m/s scaled to the men), Jog's 7% (5.95 against 5.54); the game's speeds below use the root-motion speeds. The
slide numbers compare clips with each other (a per-stance linear fit reads 1.2 to 1.9 times higher). Sole sliding (in
`metrics.json`) also counts the toe of the toe-less target foot dragged at toe-off and is not used for verdicts.
In-place jumps and the swims go below the floor by design. Before the hips fix of this PR, Death01 read -21.8/-20.6 cm,
Roll -19.0/-10.9 and Jump_Start -21.8/-20.6: those depths were the retarget's, not the clips'.

## Locomotion at the game's speeds

`anim-review rates` plays the candidates side by side on a treadmill moving at the game's speed (`rates/<body>/`:
`walk_4.5.mp4`, `sprint_7.0.mp4`, strips and `rates.json`), each at the rate that keeps its feet on the ground: UAL
clips by their root-motion speed scaled to the body (Jog 5.54/5.96 m/s, Sprint 8.53/9.18, Walk 1.01/1.08), the pack's
Run by its feet (3.09/2.45). A blend is cycle-synced (both clips lined up on the left heel strike) and weighted so its
stride over its cycle gives the speed. Men / women:

| Game speed | Clip | Rate | Steps/s | Step m | Verdict |
|---|---|---|---|---|---|
| walk 4.5 m/s | UAL Jog_Fwd_Loop | 0.81 / 0.76 | 1.74 / 1.62 | 2.59 / 2.78 | Long bounds at a cadence below an ordinary walk's (about 1.7 to 2.0 steps/s): reads as slow motion |
| walk 4.5 m/s | blend Walk_Loop 0.17/0.23 + Jog 0.83/0.77 | 1.0 | 2.00 / 1.95 | 2.26 / 2.31 | The best of the three: a light run, still long steps for its cadence |
| walk 4.5 m/s | pack Run | 1.45 / 1.83 | 3.67 | 1.22 / 1.23 | Fast short steps, a cartoon whirl; the arms pump too fast |
| sprint 7.0 m/s | UAL Sprint_Loop | 0.82 / 0.76 | 2.46 / 2.29 | 2.84 / 3.06 | Usable: a sprinter's long stride, slightly slow |
| sprint 7.0 m/s | blend Jog 0.43/0.60 + Sprint 0.57/0.40 | 1.0 | 2.56 / 2.42 | 2.73 / 2.89 | As good as Sprint_Loop alone, a little quicker |
| sprint 7.0 m/s | pack Run | 2.26 / 2.85 | 5.72 / 5.71 | 1.22 / 1.23 | Far too fast: not usable |

A run at 4.5 m/s takes about 2.7 to 2.9 steps a second (160 to 175 a minute) with steps of about 1.6 m; a sprint at
7.0 m/s about 3.2 with 2.2 m steps. UAL's clips are mocap of faster runs (5.5 and 8.5 m/s at the mannequin's size),
so slowing them down keeps their long strides. **Options for the walk:** (a) stride warping in the retarget: play
the Jog at about 1.3x for a natural 2.8 steps/s and scale the feet's horizontal travel to the 1.6 m step (the leg IK
already pins the feet; about 1 day, then judged on the same treadmill); (b) the Walk/Jog blend at 1.0x as it is;
(c) ask whether 4.5 m/s is the game's walk or its jog (a walk is about 1.4 m/s; the pack and UAL walks are 1.0 to
1.4 m/s). Recommendation: (a), with (b) as the fallback until it lands; (c) goes to the engineer with the other game
questions. The sprint can use Sprint_Loop at 0.82x/0.76x or the blend as they are.

## UAL2 Standard (art #24)

The free Universal Animation Library 2 Standard (Quaternius, CC0 1.0; record
[`sources/quaternius_ual2_standard.toml`](../../sources/quaternius_ual2_standard.toml)) through the same retarget and
review, as one more source (`tools/run.py retarget --library ual2`, `anim-review <step> --sources ual2`; the method in
[../animations.md](../animations.md#sources-clip-keys-and-layers-art-24)). Outputs in
`D:/prime-art-raw/review/stage1/24/`: `inventory.json`, `metrics.json` and `metrics.md`, `strips/` and `clips/` (88:
43 clips per body type and the layered carry idle), `pairs/` (10 per body type), `rates/` (the carry at the game's
walk), `sheets/` (15) and `mannequins/` (the Female Mannequin check).

### Inventory and rig

| Fact | Measured |
|---|---|
| Clips | 43 in both GLBs (`A_TPose` included; the itch.io page counts 42), 30 fps, 0.43 s (Sword_Regular_A) to 4.33 s (Sword_Heavy_Combo); 12 named `_Loop` (the review loops those). None shares a name with UAL1's except A_TPose |
| Root motion | In place, no clip moves its root. `UAL2_Standard_RM.glb` moves it in 17: Walk_Carry_Loop 0.65 m/s, Zombie_Walk_Fwd_Loop 1.05, Hit_Knockback 3.0 m back in 0.83 s, ClimbUp_1m 1.68 m forward and 1.0 m up, the slides 4.0 to 4.8 m/s, the sword, shield and melee clips 0.05 to 5.3 m |
| What it has | the carry walk; a knockdown (Hit_Knockback) and lying to standing (LayToIdle); idles and gestures (Idle_FoldArms_Loop, Idle_No_Loop, Yes, Idle_TalkingPhone_Loop, Idle_Rail_Loop and _Call, Idle_Lantern_Loop); tasks (Chest_Open, Consume, Farm_Harvest, Farm_PlantSeed, Farm_Watering, TreeChopping_Loop); OverhandThrow; ClimbUp_1m; a ninja jump; a floor slide; sword, shield and melee clips (15); zombie clips (3) |
| What it lacks | an idle carry, a wave, a lying face-up loop, a crawl, strafes (the itch.io previews show IDLE_CARRY, WAVE and LAYFACEUP; the Standard files hold none of them: they belong to the 130+ of the $14.99 Source tier, which the page does not itemise) |
| Rig | UAL1's exactly (`inventory.json`, `rig_vs_ual`): the same 65 bone names and parents, rest positions 0.0 mm and rotations 0.0 degrees apart, the same mannequin mesh (8,546 vertices). UAL1's bone map serves unchanged; no second map |

Retarget (`retarget --library ual2 --floor`): rest check 0.0031 mm (men) and 0.0012 mm (women), 0 degrees; translation
scale 1.034/1.113 as for UAL1; 43 clips baked in 60 s per body type. Legs short of the source's ankle path by more than
1 cm in Walk_Carry_Loop (11.9/9.7 mm), Yes (12.8/13.6), LayToIdle (42/47, the sit-up), Hit_Knockback (29/37, in the
air), the slides (24 to 28), Shield_Dash (36/34) and Sword_Regular_C and the combo (47 to 66). Lowest vertex: LayToIdle
4.0/4.1 cm into the floor in the crouch of the get-up, about 0.8 s in (UAL's own mannequin scaled: 10.0/10.7; its
first, lying frame is clean at +0.6/-1.0 cm), Farm_PlantSeed 6.5/7.4 (the kneeling
knee; own mannequin 6.7/7.2), the floor slides 2.2 to 6.3, Shield_Dash 2.5/3.4, the sword combos 2.7 to 3.2,
Hit_Knockback 0.9/1.0; every other clip within 2.6 cm.

### Measures and verdicts per clip

The columns of the art #20 table (men / women; the knee "past straight" column is 0.0 everywhere and left out). The
layered row is UAL1's Idle_Loop under UAL2's carry upper body (`ual:Idle_Loop|ual2:Walk_Carry_Loop`).

| Source | Clip | Loop | s | Ground m/s | Foot slide mean/max cm/s (men; women) | Lowest cm | Hands in torso/head/other hand/legs cm (men; women) | Seam deg (x frame step) | Forearm twist deg | Finger curl deg | Visual verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ual2 | A_TPose | no | 2.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.1 / -0.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0-0.0 | The rest pose: the rest check in motion |
| ual2 | Chest_Open | no | 1.37 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.0/1.0; 0.0/0.0/0.0/7.5 | 0.0 / 0.0 | 55.4 / 55.4 | 16.1-77.9 | Bends and lifts a lid at knee height with the right hand (1.37 s): a use on a low object; the women's left fist presses 7.5 cm into the thigh while bending |
| ual2 | ClimbUp_1m | no | 0.67 | - / - | -; - | 1.0 / 1.2 | 0.0/0.0/0.0/5.1; 0.0/0.0/0.0/5.1 | 0.0 / 0.0 | 41.3 / 41.3 | 3.6-77.9 | Climbs onto a 1 m ledge (root motion 1.68 m forward, 1.0 m up); in place the body rises off the floor. The game has a 1 m jump and no climb: not needed now |
| ual2 | Consume | no | 1.33 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.9 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 / 0.0 | 95.7 / 95.7 | 15.7-77.9 | Brings the right hand to the mouth (eat or drink); forearm twist 96 degrees. Not needed |
| ual2 | Farm_Harvest | no | 2.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.0/0.4; 0.0/0.0/0.0/3.3 | 0.0 / 0.0 | 12.0 / 12.0 | 0.0-77.9 | Bends deep, reaches the floor with the right hand (the left stays on the knee), pulls up and stands (2.5 s): **a one-handed floor pickup** art #20 lacked (the knife; not the two-handed package as it stands); long for a game action (cut or retime to about 1 s); the women's fists touch the thighs (3.3 cm) while bending |
| ual2 | Farm_PlantSeed | no | 2.77 | 0.00 / 0.00 | 3.6/55.2; 4.0/71.1 | -6.5 / -7.4 | 0.0/0.0/0.0/3.4; 0.0/0.0/0.0/5.0 | 0.0 / 0.0 | 30.3 / 30.3 | 49.1-77.9 | Kneels on one knee, places something on the floor with the right hand (the left rests on the knee) and stands (2.77 s): **a one-handed put-down** art #20 lacked; the knee goes 6.5/7.4 cm into the floor as on UAL's own mannequin (6.7/7.2): the knee pad, a floor clamp or accepted; the women's hand rests on the thigh (5.0 cm) |
| ual2 | Farm_Watering | no | 3.80 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/1.8 | 0.0 / 0.0 | 14.0 / 14.0 | 77.9-77.9 | Pours from a can in the right hand (3.8 s). Not needed |
| ual2 | Hit_Knockback | no | 0.83 | - / - | -; - | -0.9 / -1.0 | 0.0/0.0/0.0/1.3; 0.0/0.0/0.0/7.2 | 164.5 / 164.5 | 11.1 / 11.1 | 20.2-77.9 | A blast hit: starts crouched, is launched up and back and lands flat on the back (0.83 s; root motion 3.0 m back at 3.6 m/s). **A knockdown, not a push**: an alternative to Death01; its last pose is 1.5 cm and 10 degrees from LayToIdle's first. It starts in a deep crouch, not standing (a blend from the idle or walk into its first frame is needed), throws the whole body clear of the floor (the lowest vertex up to 61.6/67.3 cm) and ends hovering 2.8/2.4 cm above the floor (a settle onto the floor or into LayToIdle's first frame). Read in motion it looks like an explosion, a weak match for a knife hit where the player falls where they stand. Lowest -0.9/-1.0 cm (the first, crouched frame); the women's fist goes 7.2 cm into the thigh in the air |
| ual2 | Idle_FoldArms_Loop | yes | 2.50 | 0.00 / 0.00 | 0.6/4.6; 0.6/4.6 | -0.6 / -0.8 | 3.4/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.5 (x0.7) / 0.5 (x0.7) | 24.7 / 24.7 | 77.9-77.9 | Arms folded across the chest, the weight shifting: **a clear idle emote**; the men's big hands press 3.4 cm into the chest |
| ual2 | Idle_Lantern_Loop | yes | 2.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.5 | 0.2 (x0.4) / 0.2 (x0.4) | 0.9 / 0.9 | 77.9-77.9 | Holds the right arm straight forward with a fist (a lantern): stiffer than UAL1's Idle_Torch_Loop; not better for a one-handed hold |
| ual2 | Idle_No_Loop | yes | 2.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/1.3 | 0.2 (x0.1) / 0.2 (x0.1) | 0.9 / 0.9 | 77.9-77.9 | Head lowered and shaking slowly: a 'no' or a dejected idle, subtle at distance |
| ual2 | Idle_Rail_Call | no | 2.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.3 / -0.4 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.9 / 0.9 | 70.2 / 70.2 | 32.0-77.9 | Leans on an unseen rail and calls out with a hand at the face: needs a rail. Not needed |
| ual2 | Idle_Rail_Loop | yes | 2.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.3 / -0.4 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 (x0.2) / 0.0 (x0.2) | 0.9 / 0.9 | 77.9-77.9 | Leans forward on an unseen rail. Not needed |
| ual2 | Idle_Shield_Break | no | 1.07 | 0.00 / 0.00 | 0.4/3.2; 0.4/3.1 | -0.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 / 0.0 | 6.3 / 6.3 | 77.9-77.9 | A shield guard breaking. Not needed |
| ual2 | Idle_Shield_Loop | yes | 2.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.4 (x0.6) / 0.4 (x0.6) | 0.9 / 0.9 | 77.9-77.9 | A shield guard idle. Not needed |
| ual2 | Idle_TalkingPhone_Loop | yes | 2.93 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.7 | 0.0/5.0/0.0/0.0; 0.0/7.6/0.0/0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 52.2 / 52.2 | 14.9-58.6 | Talks on a phone: the left hand at the ear, the right gesturing; the phone hand goes 5.0/7.6 cm into the big head. A phone call, not proximity voice: Idle_Talking_Loop stays the talking clip |
| ual2 | LayToIdle | no | 1.53 | 0.01 / 0.01 | 7.5/55.6; 7.8/58.1 | -4.0 / -4.1 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/2.8 | 94.2 / 94.2 | 84.4 / 84.4 | 6.0-77.9 | Lying on the back, sits up, crouches and stands (1.53 s): **the get-up after a revive** art #20 lacked, and its first frame is **the lying pose** for the downed state, clean on the floor (+0.6/-1.0 cm); 4.0/4.1 cm into the floor in the crouch of the get-up, about 0.8 s in (UAL's own mannequin 10.0/10.7); the legs fall 4.2/4.7 cm short of the source at the sit-up |
| ual2 | Melee_Hook | no | 0.47 | 0.30 / 0.43 | 74.2/305.4; 68.4/320.9 | -1.2 / -1.3 | 4.4/9.9/0.0/0.7; 0.0/8.7/1.6/0.1 | 108.5 / 108.5 | 48.1 / 48.1 | 77.9-77.9 | A lunging hook punch from a boxing guard (0.47 s); guard fists 9.9/8.7 cm inside the big head. Too big for the knife |
| ual2 | Melee_Hook_Rec | no | 0.60 | 0.92 / 0.99 | 65.9/150.7; 71.6/165.7 | -0.8 / -0.7 | 0.0/3.8/0.9/0.0; 0.0/2.7/6.2/0.0 | 108.5 / 108.5 | 1.0 / 1.0 | 77.9-77.9 | The hook's recovery to the guard (0.6 s). Not needed |
| ual2 | NinjaJump_Idle_Loop | yes | 2.00 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | 41.6 / 50.1 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 (x0.1) / 0.0 (x0.1) | 27.7 / 27.7 | 23.0-77.9 | An airborne tuck; in place it floats 42/50 cm above the floor. UAL1's jump set stays |
| ual2 | NinjaJump_Land | no | 1.27 | 0.00 / 0.00 | 0.2/1.7; 0.3/1.8 | -0.6 / -0.8 | 0.0/0.0/0.0/3.8; 0.0/0.0/0.0/5.1 | 133.5 / 136.1 | 27.7 / 27.7 | 23.0-77.9 | A crouched landing from the tuck. UAL1's Jump_Land stays |
| ual2 | NinjaJump_Start | no | 0.97 | - / - | -; - | -2.2 / -2.6 | 0.0/0.0/0.0/1.0; 0.0/0.0/0.0/5.4 | 92.3 / 92.3 | 27.7 / 27.7 | 23.0-77.9 | A crouched launch into the tuck. Not needed |
| ual2 | OverhandThrow | no | 1.33 | 0.00 / 0.00 | 23.9/243.5; 26.6/269.7 | -0.9 / -1.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/4.2 | 59.9 / 59.9 | 31.9 / 31.9 | 6.9-77.9 | A full overhand throw with a step (1.33 s): **the throw for later** (#37); the front foot slides during the step (max 2.4/2.7 m/s) |
| ual2 | Shield_Dash | no | 1.10 | 0.00 / 0.00 | 52.6/309.3; 61.5/321.4 | -2.5 / -3.4 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/4.7 | 91.6 / 91.6 | 66.4 / 66.4 | 77.9-77.9 | A shield charge (1.0 m root motion). Not needed |
| ual2 | Shield_OneShot | no | 0.83 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.9 | 0.0 / 0.0 | 0.9 / 0.9 | 77.9-77.9 | A shield bash. Not needed |
| ual2 | Slide_Exit | no | 0.50 | 4.04 / 4.32 | 168.9/302.9; 181.2/323.0 | -3.6 / -4.4 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 134.8 / 134.8 | 47.7 / 47.7 | 0.0-77.9 | Gets up from a floor slide. Not needed |
| ual2 | Slide_Loop | yes | 2.00 | 0.00 / 0.00 | 5.8/11.7; 6.3/12.3 | 1.6 / -0.6 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 13.8 / 13.8 | 16.8-77.9 | A floor slide (root motion 4.5 m/s). Not needed |
| ual2 | Slide_Start | no | 0.83 | 0.78 / 0.78 | -; 265.7/1043.9 | -2.2 / -6.3 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 134.8 / 134.8 | 19.1 / 19.1 | 0.0-77.9 | Drops into a floor slide. Not needed |
| ual2 | Sword_Block | no | 1.23 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.4 / -0.6 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.5 | 0.0 / 0.0 | 10.9 / 10.9 | 17.1-77.9 | A sword block. Not needed |
| ual2 | Sword_Dash | no | 1.57 | 0.00 / 0.00 | 88.5/956.3; 91.2/991.8 | -0.9 / -1.4 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/3.3 | 0.0 / 0.0 | 18.9 / 18.9 | 5.0-77.9 | Sword combat with deep lunges; too big for the knife. Not needed (feet slide up to 9.6 m/s in the dash) |
| ual2 | Sword_Heavy_Combo | no | 4.33 | 0.05 / 0.06 | 98.7/983.1; 91.7/1055.1 | -3.2 / -2.7 | 0.0/0.0/0.0/6.4; 0.0/0.0/0.0/8.0 | 44.3 / 44.3 | 117.5 / 117.5 | 10.4-77.9 | Sword combat with deep lunges; too big for the knife. Not needed |
| ual2 | Sword_Regular_A | no | 0.43 | 0.80 / 0.86 | 186.6/651.9; 196.9/687.4 | -0.9 / -1.3 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/3.3 | 134.3 / 134.3 | 109.2 / 109.2 | 25.0-77.9 | A crouch and a rising slash into a deep lunge (0.43 s). Sword combat with deep lunges; too big for the knife. Not needed |
| ual2 | Sword_Regular_A_Rec | no | 0.97 | 0.24 / 0.26 | 23.9/73.4; 24.2/77.9 | -1.0 / -1.4 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/3.1 | 134.3 / 134.3 | 31.1 / 31.1 | 25.0-77.9 | Recovery of Sword_Regular_A. Not needed |
| ual2 | Sword_Regular_B | no | 0.53 | 0.18 / 0.19 | 34.3/94.4; 35.1/89.3 | -0.9 / -1.4 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.9 | 140.7 / 140.7 | 25.0 / 25.0 | 5.0-77.9 | A downward diagonal slash into a deep lunge (0.53 s). Sword combat with deep lunges; too big for the knife. Not needed |
| ual2 | Sword_Regular_B_Rec | no | 1.03 | 0.41 / 0.44 | 36.1/67.1; 37.7/69.8 | -0.6 / -0.8 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 124.9 / 121.0 | 2.1 / 2.1 | 8.3-77.9 | Recovery of Sword_Regular_B. Not needed |
| ual2 | Sword_Regular_C | no | 2.00 | 0.14 / 0.19 | 52.9/364.5; 53.2/369.3 | -3.0 / -3.1 | 0.0/0.0/0.0/1.3; 0.0/0.0/0.0/3.7 | 115.5 / 113.6 | 93.1 / 93.1 | 5.0-77.9 | Sword combat with deep lunges; too big for the knife. Not needed |
| ual2 | Sword_Regular_Combo | no | 3.00 | 0.07 / 0.08 | 65.1/578.8; 68.8/609.4 | -3.0 / -3.1 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/3.6 | 22.2 / 22.2 | 109.2 / 109.2 | 5.0-77.9 | Sword combat with deep lunges; too big for the knife. Not needed |
| ual2 | TreeChopping_Loop | yes | 0.97 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.3 / -0.6 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 51.5 / 51.5 | 40.1-77.9 | Two-handed chopping. Not needed |
| ual2 | Walk_Carry_Loop | yes | 2.00 | 0.67 / 0.72 | 1.1/28.0; 1.2/29.9 | -0.7 / -0.5 | 0.0/0.0/0.7/0.0; 0.0/0.0/1.1/0.0 | 0.1 (x0.0) / 0.0 (x0.0) | 37.0 / 37.0 | 24.8-24.8 | Walks with both hands cupped palms up at the belly, the upper body leaning back (a heavy box), 0.67/0.72 m/s; clean loop, feet clean, the hands touch (0.7/1.1 cm). **The carry** art #20 lacked; at the game's 4.5 m/s its upper body plays over the walk (`carry_4.5`) |
| ual2 | Yes | no | 2.50 | 0.00 / 0.00 | 0.3/3.3; 0.3/3.5 | -0.7 / -1.0 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/0.8 | 0.2 / 0.2 | 2.5 / 2.5 | 77.9-77.9 | A thumbs-up held out with the right arm (2.5 s): **an emote** art #20 listed as a gap |
| ual2 | Zombie_Idle_Loop | yes | 1.33 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.3 / -0.5 | 0.0/0.0/0.0/4.9; 0.0/0.0/0.0/6.3 | 1.3 (x0.9) / 1.3 (x0.9) | 32.3 / 32.3 | 25.7-41.7 | Zombie idle. Not needed |
| ual2 | Zombie_Scratch | no | 1.80 | 0.00 / 0.00 | 11.9/151.7; 12.8/164.0 | -0.9 / -0.8 | 0.0/0.0/0.0/5.2; 0.0/0.0/0.0/6.8 | 0.0 / 0.0 | 41.7 / 41.7 | 34.0-59.6 | Zombie scratch. Not needed |
| ual2 | Zombie_Walk_Fwd_Loop | yes | 1.33 | 1.00 / 1.08 | 73.8/316.8; 87.1/340.7 | -1.6 / -2.2 | 0.0/0.0/0.0/0.0; 0.0/0.0/0.0/3.4 | 0.0 (x0.0) / 0.1 (x0.0) | 61.9 / 61.9 | 41.7-41.7 | Zombie shuffle, 1.0/1.1 m/s, the feet slide (74/87 cm/s mean). Not needed |
| layer | Idle_Loop + Walk_Carry_Loop upper body | yes | 2.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.6 / -0.8 | 0.0/0.0/0.8/0.0; 0.0/0.0/1.1/0.0 | 0.2 (x0.3) / 0.2 (x0.3) | 37.0 / 37.0 | 24.8-24.8 | UAL1 Idle_Loop's legs under Walk_Carry_Loop's upper body: **the carry idle** (UAL2 Standard has none); a clean loop (seam 0.2 degrees, x0.3), the hands touch 0.8/1.1 cm, the women's fists clear the thighs |

### Side by side with art #20's choices

`pairs/<body>/<name>.png` and `.mp4`, each UAL2 clip against the best clip art #20 chose for the need (or the nearest
it named where the need was a gap). Looked at in the strips; verdicts on both bodies:

| Pair | Clips | Verdict |
|---|---|---|
| `ual2_carry` | UAL2 Walk_Carry_Loop, UAL1 Idle_Loop + Walk_Carry_Loop upper body, UAL1 Pistol_Idle_Loop | **UAL2 fills the carry.** Both carry clips hold the package low in the middle with both hands, palms up, as the game's first-person hand does; Pistol_Idle_Loop (art #20's nearest) holds a grip at the chest. The walk leans back as under a heavy box (a look point if the package is light); the layered idle keeps the idle's stance and loops cleanly |
| `ual2_pushed` | UAL2 Hit_Knockback, UAL1 Hit_Chest, pack HitRecieve_2 | **Not a push.** Hit_Knockback launches the body and lays it flat; for being pushed, art #20's Hit_Chest stays the nearest and the stagger remains a gap |
| `ual2_knockdown` | UAL2 Hit_Knockback, UAL1 Death01, pack Death | A third knockdown: the fastest and most readable at distance (0.83 s, airborne, 3 m back with root motion), against Death01's natural 2.4 s stagger and the pack's cartoony sit-back. It chains into the downed pose (below), but it starts crouched (a blend-in from the idle or walk), launches the body 62/67 cm into the air and ends 2.8/2.4 cm above the floor: it reads as a blast, not as falling where one stands. An option for the look question beside Death01 retimed and exaggerated, not ahead of it |
| `ual2_downed` | UAL2 LayToIdle, UAL1 Death01 | **UAL2 fills the get-up and the lying pose**: LayToIdle starts lying on the back, arms by the sides, and stands up through a sit-up and a crouch in 1.53 s, where art #20 had only Death01's last frame and no get-up |
| `ual2_gestures` | UAL2 Yes, Idle_FoldArms_Loop, Idle_No_Loop, pack Wave | **Two new emotes read well**: the thumbs-up (Yes) and the folded arms; the head shake is subtle. The pack's Wave stays the wave |
| `ual2_talking` | UAL2 Idle_TalkingPhone_Loop, UAL1 Idle_Talking_Loop | A phone call (hand at the ear, 5 to 8 cm into the big head); Idle_Talking_Loop stays the talking clip |
| `ual2_pickup` | UAL2 Farm_Harvest, Farm_PlantSeed, UAL1 PickUp_Table | **UAL2 fills the floor pickup and the put-down for one-handed items only**: a deep bend to the floor and a one-knee kneel to place, against PickUp_Table's waist-height reach, but in both the right hand alone reaches the floor while the left rests on the knee. The Delivery package is two-handed (`mvp-rules.md:87-93`): for it the bend needs a two-hand arm pose layered on top (the carry's upper body blended in at the bottom of the bend) or our own clip. Both are long for a key press (2.5 and 2.8 s): cut or retime to about 1 s |
| `ual2_use` | UAL2 Chest_Open, UAL1 Interact | Chest_Open is a use on something low (a lid at knee height); Interact stays the use |
| `ual2_hold` | UAL2 Idle_Lantern_Loop, UAL1 Idle_Torch_Loop | The lantern arm is held straight out: no better than the torch hold |
| `ual2_knife` | UAL2 Melee_Hook, Sword_Regular_A, pack Sword_Slash | Both UAL2 swings are lunging combat moves (deep stances, 0.43 to 0.47 s); the pack's Sword_Slash stays the knife |

### The carry at the game's walk

The package is carried at the normal 4.5 m/s (no carry slowdown in the rules), and Walk_Carry_Loop walks at 0.67/0.72 m/s
by root motion: at 4.5 m/s it would play at 6.7x/6.2x. The `carry_4.5` treadmill row (`rates/<body>/carry_4.5.*`) plays
its upper body (Torso down) as a layer over art #20's walk blend instead, one carry loop per stride lined up on the left
heel strike, beside the blend alone: the legs are the blend's (Walk 0.17/0.23 + Jog 0.83/0.77, 1.0x, 2.00/1.95 steps/s,
2.26/2.31 m steps) and the arms stay forward and cupped at the belly. It reads as running with the package; the
upright torso of the run replaces the walk's lean back. A layer like this is what the game would play (an upper-body
filter in Godot's AnimationTree); the same layer over Idle_Loop is the carry idle (the layered row above).

### Knocked down, downed, raised: do the clips join?

Source poses compared on UAL's own rig (`chain_check.py` in the review folder; the retarget maps each frame alone):

| From the last frame of | To LayToIdle's first frame |
|---|---|
| UAL2 Hit_Knockback | pelvis 1.5 cm and 10 degrees apart, the head the same way; the largest differences are the fingers (60 to 66 degrees, open hands against loose fists): a short cross-fade joins them |
| UAL1 Death01 | pelvis 31 cm and 16 degrees apart, the head the same way; the arms differ by up to 129 degrees (Death01 lies with the arms out): a longer blend with a root shift |

So UAL2 gives a matching set: Hit_Knockback to fall, LayToIdle's first frame held while downed, LayToIdle to stand up
after a revive. Hit_Knockback still needs a blend-in (it starts crouched) and ends 2.8/2.4 cm above the floor, which
the cross-fade into LayToIdle's first frame (+0.6/-1.0 cm) settles; Death01 retimed joins LayToIdle with the longer
blend and root shift above. The crawl between them is still missing.

### The Female Mannequin (report only)

UAL2's `Mannequin_F` has UAL1's rig with the same leg and spine bones (0 mm apart); only the arms differ: shoulder joints
30.3 cm apart against 38.4, the upper arm 5.3 cm shorter, the clavicles turned 9 degrees. Its mesh is 180.8 cm tall
(the male 182.9) with hips 36.8 cm wide against 33.3. It has no clips of its own (its README: retarget the library's).
Played with UAL's own local tracks (`mannequins/mannequins.json`, `mannequins_front.png`):

| Clip | Feet apart (both mannequins) | Male mannequin: hands into the thighs / smallest gap | Female Mannequin: hands into the thighs / smallest gap | Our women (Suit, art #20) |
|---|---|---|---|---|
| Idle_Loop | 35.7 cm | 0.0 / 3.1 cm | 3.1 / 0.1 cm | 1.3 cm |
| Walk_Loop | 18.2 cm (mean) | 0.0 / 5.0 cm | 3.1 / 0.1 cm | 3.3 cm |
| Walk_Formal_Loop | 18.2 cm (mean) | 0.0 / 5.9 cm | 3.5 / 0.1 cm | 3.2 cm |
| Interact | 35.7 cm | 0.0 / 0.6 cm | 3.5 / 0.1 cm | 4.9 cm |

**It does not help the women's stance or arms.** Its legs are the male mannequin's, so it stands just as wide; and
Quaternius' own female presses her fists 3 to 3.5 cm into her thighs in the same clips. That confirms art #20's
diagnosis (the arm motion comes from a wider-shouldered body; narrower shoulders bring the fists onto the thighs) and
leaves its options as they were: an arm offset for the women (a), a narrower stance (b), or the pack's women's idles
(c). Nothing is adopted.

## What the game needs, and the best clip for each

Read from the game repo (read only, 2026-10-03). The game has no crouch, no guns and no fists in its rules.

| Need | Where the game says so | Best clip | Source | State |
|---|---|---|---|---|
| Walk at 4.5 m/s (the lobby and the round) | `content/modes/base_mode.tres:325` `walk_speed_mps = 4.5`; `docs/decisions/2026-10-01-vision-revision-1.md:109` (the living walk, sprint, jump) | Walk_Loop and Jog_Fwd_Loop, cycle-synced, at 1.0x (2.0 steps/s) for now; Jog_Fwd_Loop at 0.81x/0.76x is a slow-motion bound (see "Locomotion at the game's speeds") | UAL | stride warping to build |
| Sprint at 7.0 m/s | `base_mode.tres:326`; `docs/decisions/2026-09-29-mvp-rules.md:101` | Sprint_Loop at 0.82x (men) or 0.76x (women), or blended with Jog at 1.0x | UAL | ready |
| Moving sideways and backwards (first person, free movement; remote bodies are drawn from interpolated positions) | `client/player/player_controller.gd`; `docs/decisions/2026-10-01-m4-first-person-client.md:130-134` | Run_Back for backwards; no side-step strafe in either set (the pack's Run_Left/Right turn the whole body) | pack | **gap** |
| Jump (1.0 m) | `base_mode.tres:329` `jump_height_m = 1.0`; `mvp-rules.md:101` | Jump_Start, Jump_Loop, Jump_Land (in place; the jump physics lifts the body) | UAL | ready |
| Idle | every phase | Idle_Loop (relaxed, the same on both bodies) | UAL | ready |
| Talking by proximity voice | `docs/GDD.md:23` (fun before any match: customization, gestures and proximity voice) | Idle_Talking_Loop (open, moving fingers); its hands pass 2.2 cm into each other | UAL | hand spacing to fix |
| Use, pick up, put down (left mouse, E, Q) | `docs/decisions/2026-10-01-m4-first-person-client.md:81-83`; `mvp-rules.md:90-93` (a key places the item on the ground in front) | Interact (press with the index finger); PickUp_Table (waist height); **Farm_Harvest (floor pickup) and Farm_PlantSeed (put-down), UAL2, one-handed** | UAL / UAL2 | one-handed items: retime to about 1 s (2.5 and 2.8 s now); the two-handed package: **partial** (a two-hand layer over the bend, or our own) |
| Carry the two-handed package | `mvp-rules.md:88-89`; `client/player/first_person_hand.gd:4-10` (held low in the middle with both hands) | **UAL2 Walk_Carry_Loop's upper body, layered over Idle_Loop (idle) and over the walk blend (moving; `carry_4.5`)**; the hands touch (0.7 to 1.1 cm) | UAL2 | the layer to build in Godot; hand spacing to the package's width |
| Hold an item one-handed, the belt item visible | `mvp-rules.md:86-92` | Idle_Torch_Loop as an upper-body hold; the pack's Idle_Sword | UAL / pack | upper-body layer to build |
| Use the knife (narrow, short hit zone, 1.5 m) | `mvp-rules.md:122-127`; `content/items/knife.tres:23` | Sword_Slash (pin the feet); UAL Punch_Jab as a quick stab | pack | fix the feet |
| Being hit | `mvp-rules.md:100-101` (a hit spends stamina) | HitRecieve_2; Hit_Chest and Hit_Head are subtle | pack / UAL | ready |
| Pushing | `mvp-rules.md:108-118` | Push_Loop as an upper-body overlay for the pusher (the women's hands overlap) | UAL | partial |
| Being pushed | `mvp-rules.md:108-118` | Hit_Chest's knock back is the nearest (0.33 s); no stagger in any set (UAL2's Hit_Knockback is a knockdown) | UAL | **gap** |
| Remote bodies look up and down (head pitch, clamped to ±89 degrees) | `client/player/remote_player_body.gd:125-134` (the pitch on the head); `docs/decisions/2026-10-01-m4-first-person-client.md` (the clamp) | none needed as a clip: the pitch can drive `Neck`/`Head` (and part of `Chest`) at run time, or an additive aim pose pair (up, down) is keyed | - | a contract and Godot question |
| Turning in place (an idle body changing its yaw) | `remote_player_body.gd:125-129` (the yaw on the body) | none in either set; feet slide on the spot without one | - | **gap** |
| Swapping the hand item with the belt | `mvp-rules.md:86-96` ("a key swaps hand and belt") | none; the rules ask for no gesture, a draw or holster clip is a nice-to-have | - | optional |
| Throwing | `mvp-rules.md` ("physics throwing comes later (#37)") | OverhandThrow (a full overhand throw with a step) | UAL2 | later |
| Knocked down: falls where they stand (canned, no ragdoll) | `mvp-rules.md:134-138`; #165 "Q8 read back: falls and knockdowns are canned animations, no ragdoll" | Death01 (a stagger and a fall on the back); UAL2 Hit_Knockback (a blast launch onto the back, 0.83 s, joins LayToIdle); the pack's Death is the cartoony alternative | UAL / UAL2 / pack | needs the floor clamp; the look is a question |
| Downed: lying and crawling at 1.0 m/s, giving up | `mvp-rules.md:134-146`; `base_mode.tres:331` `crawl_speed_mps = 1.0`; `client/player/player_controller.gd:8-9` | lying: LayToIdle's first frame (on the back, arms by the sides); crawling: none | UAL2 | crawling: **gap** |
| Raising a downed player (hold E) and standing up after a revive | `mvp-rules.md:139-142` | Fixing_Kneeling for the raiser; LayToIdle for the get-up (1.53 s) | UAL / UAL2 | ready |
| Dead body stays where it fell | `mvp-rules.md:147-148` | the knockdown's last frame (Hit_Knockback's hovers 2.8/2.4 cm above the floor: settle it, or hold LayToIdle's first frame) | - | ready |
| Gestures with five fingers, emotes | #165 H6 (b) "players must be able to make hand gestures"; `GDD.md:23` | Wave (pack), Dance_Loop, Interact's pointing finger, Spell_Simple_Idle_Loop as "stop"; **UAL2 Yes (thumbs-up), Idle_FoldArms_Loop, Idle_No_Loop** | pack / UAL / UAL2 | clap, cheer, shrug, facepalm, laugh: **gap** |
| First-person hands, forearms in the sleeves of the top | #165 Q10 (b); T18 | none: a first-person clip set on the arms (idle sway, walk bob, use, knife, hold, carry, pick up) | - | **gap** |

## Gaps and options

Money options are questions for the engineer; nothing was bought or downloaded.

| Gap | Free official CC0 source | Paid (one-off, CC0) | Our own in Blender |
|---|---|---|---|
| Carry the package (idle and walk) | **Filled (art #24)**: UAL2 Standard's Walk_Carry_Loop, its upper body layered over Idle_Loop and the walk ([quaternius.itch.io/universal-animation-library-2](https://quaternius.itch.io/universal-animation-library-2), CC0; the Standard files hold no `IDLE_CARRY`) | - | the layer in Godot and a hand-spacing offset: 0.5 day |
| Downed: lying, crawling, getting up | **Lying and getting up filled (art #24)**: UAL2 Standard's LayToIdle (its first frame lies; it stands up in 1.53 s); crawling: none | **UAL1 Pro** $9.99 or more: "crawling" among 120+ clips ([quaternius.itch.io/universal-animation-library](https://quaternius.itch.io/universal-animation-library)) | crawl cycle 2 to 3 days |
| Strafes and backwards walk and jog | - | UAL1 Pro: "Locomotion in 8 directions" | side-steps and backpedal from Jog and Walk with the leg IK: 2 days |
| Turning in place | - | not itemised on the UAL1 Pro page | a stepping turn keyed on Idle_Loop: 0.5 to 1 day |
| Being pushed (a stagger) | none: UAL2 Standard's Hit_Knockback is a knockdown (art #24) | - | a short stagger from Hit_Chest and a side-step: 0.5 day |
| Stride length at the game's 4.5 m/s | - | - | stride warping in the retarget (see "Locomotion at the game's speeds"): about 1 day |
| Floor pickup and put-down | **One-handed items filled (art #24)**: UAL2 Standard's Farm_Harvest and Farm_PlantSeed, retimed to about 1 s; **the two-handed package: partial** (both clips reach down with the right hand only) | - | the retime: 2 hours; a two-hand pickup and put-down for the package (the carry's upper body blended in at the bottom of Farm_Harvest's bend, or keyed on it): 0.5 to 1 day |
| Emotes and five-finger gestures | UAL2 Standard (art #24): Yes (thumbs-up), Idle_FoldArms_Loop, Idle_No_Loop; no wave (the pack's Wave serves) | UAL1 Pro: "emotes" (not itemised) | hand-keyed on the five-finger chains: 2 to 4 hours each, about 2 days for the four left (clap, cheer, shrug, laugh) |
| Throwing (later, #37) | **UAL2 Standard**: OverhandThrow | - | - |
| First-person arm set | - | - | 3 to 4 days (same retarget and measures) |
| Source files to edit clips | - | UAL1 Source $14.99 or more; UAL2 Source $14.99 or more (`.blend` and 130+ animations in all, not itemised; the page's previews show IDLE_CARRY, WAVE and LAYFACEUP) | - |

Prices read on the official itch.io pages on 2026-10-03; quaternius.com lists the same tiers without prices.

**What UAL2 changes for the money question of art #20 (UAL1 Pro):** of the three things UAL1 Pro was weighed for,
the emotes are now partly covered for free (a thumbs-up, folded arms and a head shake from UAL2, the pack's wave, UAL1's
dance), and the Pro page does not itemise its emotes anyway. **Crawling and the strafes and backpedal are still
needed**: UAL2 Standard has neither, and they are the two largest pieces of our own work left (a crawl cycle 2 to 3
days, side-steps and backpedal 2 days, against $9.99 one-off). UAL2 Source does not itemise a crawl or strafes either.

## Recommendation

1. **Take UAL as the animation base for both body types**: Idle_Loop, Walk_Loop, Jog_Fwd_Loop (the game's walk),
   Sprint_Loop, Jump_Start/Loop/Land, Interact, PickUp_Table, Fixing_Kneeling (tasks and raising), Idle_Talking_Loop,
   Death01 (knockdown), Hit_Chest, Push_Loop, Dance_Loop. Keep from the pack: Wave, Sword_Slash (the knife), Run_Back,
   HitRecieve_2. Drop the pack's Walk, Run, idles and kicks.
2. **Fix before export:** stride warping for the 4.5 m/s locomotion (until then the cycle-synced Walk/Jog blend);
   hand spacing for the two-hand poses (Idle_Talking_Loop, a carry); an arm offset for the women (the upper arms a few
   degrees out, so the fists clear the thighs and the hands clear each other); a small floor clamp for lying frames
   (lift the body by its deepest vertex while no foot carries it: about 5 cm now, not 22); pinned feet for
   Sword_Slash; the guard fists pushed forward if a punch is ever used; and a check of the wrist at 60 to 97 degrees
   of forearm twist in game (or a twist bone in the contract v2).
3. **Close the gaps in this order:** UAL2 Standard (art #24) closed the carry (Walk_Carry_Loop's upper body as a
   layer over the idle and the walk), the lying pose and the get-up (LayToIdle) and a thumbs-up (Yes), and the floor
   pickup and put-down for one-handed items (Farm_Harvest, Farm_PlantSeed, retimed); its rig is UAL1's and the tools
   run on it unchanged. Left: the crawl and the strafes and backpedal (UAL1 Pro, $9.99, or 4 to 5 days of our own),
   being pushed (our own stagger, 0.5 day), the package's two-handed pickup and put-down (a two-hand layer over
   Farm_Harvest's bend, 0.5 to 1 day), turning in place, the remaining emotes, the first-person arm set.
4. **Speeds:** for 4.5 m/s the cycle-synced Walk_Loop/Jog blend at 1.0x until stride warping lands (not the Jog at
   0.81x/0.76x: a slow-motion bound); for 7.0 m/s Sprint_Loop at 0.82x (men) or 0.76x (women), or its blend with the
   Jog. The rates come from UAL's root-motion speeds scaled to each body (Jog 5.54/5.96 m/s, Sprint 8.53/9.18).
5. **Look questions for @SwiftySinister** (with the engineer): the knockdown (UAL Death01, the pack's Death,
   Death01 retimed and exaggerated, or UAL2 Hit_Knockback; the last two side by side: Hit_Knockback joins
   LayToIdle with a short cross-fade but starts crouched, launches the body 62/67 cm into the air and ends
   2.8/2.4 cm above the floor, a blast rather than a fall where one stands), the overall feel (UAL's natural mocap against the pack's cartoony stiffness), and
   **the women's stance**: UAL gives the women the same wide, turned-out stance as the men (`strips/women/ual_Idle_Loop.png`
   against the men's); options are to keep it, narrow it with a hip and foot offset on the women's clips (about
   0.5 day), or play the pack's women's idles (other motions, stiffer).

## Reproduce

```
tools/run.py retarget --body men --floor
tools/run.py retarget --body women --floor
tools/run.py anim-review all --out D:/prime-art-raw/review/stage1/20 --jobs 4
```
The full review makes 134 measured clips (strips and MP4s), 28 side-by-side pairs, 4 treadmill rows (2 per body
type) and 23 review sheets with 8 Blender processes. UAL2 (art #24):
```
tools/run.py retarget --library ual2 --body men --floor
tools/run.py retarget --library ual2 --body women --floor
tools/run.py anim-review all --sources ual2 --out D:/prime-art-raw/review/stage1/24 --jobs 4
tools/run.py anim-review clips --clips "ual:Idle_Loop|ual2:Walk_Carry_Loop" --out D:/prime-art-raw/review/stage1/24
tools/run.py anim-review table --out D:/prime-art-raw/review/stage1/24
```
86 UAL2 clips and 2 layered carry idles measured (strips and MP4s), 20 pairs, 2 treadmill rows and 15 sheets.
