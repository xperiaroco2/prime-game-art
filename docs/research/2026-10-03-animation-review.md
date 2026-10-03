# The animations judged in motion: the pack's 24 against the Universal Animation Library (art #20, 2026-10-03)

The Ultimate Modular pack's own actions against Quaternius' Universal Animation Library Standard (UAL1) retargeted onto
our skeleton, every clip played on an unmodified pack character of each body type (men: `Business Man.glb`, women:
`Suit.glb`), measured, and looked at as 12-frame front and side strips, looping clips and side-by-side pairs. The
method and the commands are in [../animations.md](../animations.md); the pictures and clips are outside git in
`D:/prime-art-raw/review/stage1/20/` (`strips/`, `clips/`, `pairs/`, `sheets/`, `metrics.json`, `inventory.json`).

## Summary

- **UAL retargets cleanly onto both bodies.** The source rest lands on the target rest (0.002 mm, 0 degrees); walks,
  runs, crouches and idles keep their feet on the floor (lowest vertex -0.1 to -0.8 cm) with little sliding (UAL
  Walk_Loop 2.4 cm/s mean on the men against 12.0 for the pack's Walk); fingers curl the right way and point
  (Interact), and the same motion plays on both bodies, scaled to their legs.
- **UAL is the better base for almost every need the game has**: its locomotion matches the game's speeds (Jog
  5.95 m/s and Sprint 9.0 m/s in place on the men, 6.4 and 9.7 on the women, against the game's 4.5 and 7.0 m/s:
  0.70x to 0.77x playback), while the pack's Run would need 1.5x (men) to 1.8x (women) for walking and 2.3x to 2.9x for sprinting.
  The pack's Walk has stiff "swimming" arms with flat hands; its idles look stiff.
- **The pack keeps a few clips UAL lacks:** Wave (open five-finger hand), Sword_Slash (the best knife swing), Run_Back
  (the only backward locomotion), HitRecieve_2 (a clear hit read) and the cartoony Death.
- **Gaps in both free sets:** carrying the two-handed package, crawling and the downed state, getting up, strafes and
  backward walking, a floor pickup, emotes beyond a wave and a dance, and the first-person arm set. The free UAL2
  Standard (CC0, same rig) has a carry walk and idle, a knockback and a lying pose; UAL1 Pro ($9.99 or more) adds
  crawling, 8-direction locomotion and emotes.
- **To fix on any chosen clip:** a floor clamp for lying clips (UAL Death01 sinks 22 cm, the pack's Death 6.5 to
  8 cm), guard fists inside the big stylized heads (UAL punches 3.5 to 8 cm), forearm twist over 60 degrees in a few UAL
  clips (no twist bones), and playback rates matched to the game's speeds.

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
ground speed is the treadmill speed of an in-place clip; foot slide is the foot bone's contact velocity against it;
lowest is the lowest vertex (the floor is 0); hands are the deepest hand vertex inside the torso's or the head's convex
hull; the seam compares the last frame with the first (a clean loop is about one frame step); past straight is the
knee or elbow bent backwards in its hinge plane; finger curl is the mean phalanx rotation per hand (UAL keeps loose
fists, about 78 degrees, in most clips; the pack's fists are 101 degrees, its open hands 0 to 6).

| Source | Clip | Loop | s (men / women) | Ground m/s | Foot slide mean/max cm/s (men; women) | Lowest cm | Hands in torso; head cm | Seam deg (x frame step) | Past straight knee/elbow deg | Forearm twist deg | Finger curl deg | Visual verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pack | Death | no | 1.03 / 1.33 | 0.22 / 0.20 | 40.3/63.3; 32.3/53.3 | -6.5 / -8.0 | 0.0; 0.0 / 0.0; 0.0 | 95.1 / 94.8 | 0.0/0.0 / 0.0/0.0 | 26.5 / 26.5 | 0.0-1.8 | Sits back and falls flat on the back, arms splayed into a T on the floor; cartoony, readable. Slides back 68 cm and sinks 6.5/8.0 cm into the floor: needs the floor clamp |
| pack | Gun_Shoot | no | 0.60 / 0.73 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.2 | 0.0; 0.0 / 0.0; 0.0 | 0.2 / 0.2 | 0.0/0.0 / 0.0/0.0 | 0.5 / 0.5 | 1.8-41.0 | Arm straight out, small recoil. Not needed (no guns) |
| pack | HitRecieve | no | 0.53 / 0.70 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.2 | 0.0; 0.0 / 0.0; 0.0 | 1.7 / 0.3 | 0.0/0.0 / 0.0/0.0 | 0.0 / 0.0 | 0.0-1.8 | Small flinch with a hand to the thigh; weak read at distance |
| pack | HitRecieve_2 | no | 0.53 / 0.70 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.2 | 0.0; 0.0 / 0.0; 0.0 | 0.9 / 0.1 | 0.0/0.0 / 0.0/0.0 | 0.0 / 0.0 | 0.0-1.8 | Head snaps back, torso arches: a clear hit read |
| pack | Idle | yes | 1.67 / 2.07 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.3 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.1) / 0.0 (x0.0) | 0.0/0.0 / 0.0/0.0 | 0.0 / 0.0 | 0.0-6.4 | Stiff stance, elbows out, open flat hands; the motion is fine, the frozen frame looks twisted (known) |
| pack | Idle_Gun | yes | 1.67 / 2.07 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.3 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.0) / 0.0 (x0.1) | 0.0/0.0 / 0.0/0.0 | 0.0 / 0.0 | 5.2-40.5 | One hand held forward, near static. Not needed |
| pack | Idle_Gun_Pointing | yes | 1.67 / 2.07 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.3 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.1) / 0.0 (x0.1) | 0.0/0.0 / 0.0/0.0 | 0.0 / 0.0 | 5.2-41.0 | Arm straight forward pointing; a static pointing pose |
| pack | Idle_Gun_Shoot | no | 0.67 / 0.83 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.2 | 0.0; 0.0 / 0.0; 0.0 | 0.1 / 0.0 | 0.0/0.0 / 0.0/0.0 | 0.3 / 0.3 | 5.3-41.0 | Pointing pose with recoil. Not needed |
| pack | Idle_Neutral | yes | 1.67 / 2.07 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.1 / -0.2 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.2) / 0.0 (x0.4) | 0.0/0.0 / 0.0/0.0 | 0.0 / 0.0 | 0.0-1.8 | Upright, arms down, almost still: the neutral pose; good base for overlays |
| pack | Idle_Sword | yes | 1.67 / 2.07 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.3 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.1) / 0.0 (x0.1) | 0.0/0.0 / 0.0/0.0 | 0.0 / 0.0 | 5.2-101.2 | Static guard with a fist: a one-handed hold candidate |
| pack | Interact | no | 1.27 / 1.60 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.3 / -0.3 | 0.0; 0.0 / 0.0; 0.0 | 0.5 / 0.0 | 0.0/0.0 / 0.0/0.0 | 1.3 / 1.3 | 1.8-5.4 | Raises the right palm forward and back: a vague touch; UAL Interact reads better |
| pack | Kick_Left | no | 0.93 / 1.17 | 0.07 / 0.06 | 48.7/223.6; 44.2/228.5 | -1.6 / -0.9 | 0.0; 0.0 / 0.0; 0.0 | 2.1 / 0.1 | 0.0/0.0 / 0.0/0.0 | 1.0 / 1.0 | 101.2-101.2 | Front kick with flailing arms; cartoony; feet slide (max 2.2 m/s). Not needed |
| pack | Kick_Right | no | 0.93 / 1.17 | 0.07 / 0.06 | 48.7/223.6; 44.2/228.5 | -1.6 / -0.9 | 0.0; 0.0 / 0.0; 0.0 | 2.1 / 0.1 | 0.0/0.0 / 0.0/0.0 | 1.0 / 1.0 | 101.2-101.2 | Mirror of Kick_Left. Not needed |
| pack | Punch_Left | no | 0.83 / 1.03 | 0.00 / 0.00 | 1.6/17.7; 1.8/21.6 | -0.2 / -0.3 | 0.0; 0.0 / 0.0; 0.0 | 0.0 / 1.8 | 0.0/0.0 / 0.0/0.0 | 1.0 / 1.0 | 101.2-101.2 | Hook-like punch with a raised elbow; ok. Not needed (no fists in the rules) |
| pack | Punch_Right | no | 0.83 / 1.03 | 0.00 / 0.00 | 1.6/17.7; 1.8/21.6 | -0.2 / -0.3 | 0.0; 0.0 / 0.0; 0.0 | 0.0 / 1.8 | 0.0/0.0 / 0.0/0.0 | 1.0 / 1.0 | 101.2-101.2 | Mirror of Punch_Left |
| pack | Roll | no | 1.33 / 1.67 | 1.12 / 0.99 | 129.0/354.6; 103.0/298.9 | -19.4 / -9.2 | 0.0; 5.7 / 0.0; 2.3 | 1.9 / 1.9 | 0.0/0.0 / 0.0/0.0 | 31.8 / 34.4 | 0.0-101.2 | Dive roll on the spot (no root motion) and up; sinks 19/9 cm; a stunt. Not needed |
| pack | Run | yes | 0.80 / 1.00 | 3.09 / 2.45 | 33.1/84.0; 30.5/97.4 | -0.3 / -0.3 | 0.0; 0.0 / 0.0; 0.0 | 18.4 (x1.0) / 12.5 (x0.8) | 0.0/0.0 / 0.0/0.0 | 1.8 / 1.8 | 101.2-101.2 | Solid run with pumping arms (men), lighter arms (women); seam ok. Ground 3.1/2.5 m/s: 1.5x/1.8x needed for the game's 4.5 m/s |
| pack | Run_Back | yes | 0.83 / 1.03 | 3.09 / 2.46 | 33.4/84.0; 30.2/77.1 | -0.3 / -0.3 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.0) / 1.6 (x0.1) | 0.0/0.0 / 0.0/0.0 | 1.8 / 1.8 | 101.2-101.2 | Backward run, readable: the only backward locomotion in the two sets |
| pack | Run_Left | yes | 0.80 / 1.00 | 3.09 / 2.45 | 33.1/84.0; 30.5/97.4 | -0.3 / -0.2 | 0.0; 0.0 / 0.0; 0.0 | 18.4 (x1.0) / 12.5 (x0.8) | 0.0/0.0 / 0.0/0.0 | 1.8 / 1.8 | 101.2-101.2 | The run turned 90 degrees, not a side-step strafe: the body faces the movement |
| pack | Run_Right | yes | 0.80 / 1.00 | 3.09 / 2.45 | 33.1/84.0; 30.5/97.4 | -0.3 / -0.2 | 0.0; 0.0 / 0.0; 0.0 | 18.5 (x1.0) / 12.5 (x0.8) | 0.0/0.0 / 0.0/0.0 | 1.8 / 1.8 | 101.2-101.2 | As Run_Left, mirrored |
| pack | Run_Shoot | yes | 0.83 / 1.03 | 3.09 / 2.45 | 33.1/84.0; 30.5/97.4 | -0.3 / -0.3 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.0) / 2.5 (x0.2) | 0.0/0.0 / 0.0/0.0 | 1.8 / 1.8 | 101.2-101.2 | Run with the right arm pointing forward |
| pack | Sword_Slash | no | 1.00 / 1.30 | 0.00 / 0.00 | 18.9/107.9; 15.2/93.4 | -0.4 / -0.5 | 0.0; 0.0 / 0.0; 0.0 | 0.4 / 0.0 | 0.0/0.0 / 0.0/0.0 | 0.3 / 0.3 | 2.8-101.2 | One-handed horizontal slash, readable: the best knife swing of both sets; feet slide (max 1.1/0.9 m/s): pin them |
| pack | Walk | yes | 1.33 / 1.67 | 1.37 / 1.10 | 12.0/23.7; 9.8/22.6 | -1.6 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0/0.0 / 0.0/0.0 | 5.0 / 5.2 | 4.0-4.1 | Stiff 'swimming' arms: flat open hands swinging far back and front; 1.37/1.10 m/s |
| pack | Wave | no | 1.67 / 2.07 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.3 / -0.3 | 0.0; 0.0 / 0.0; 0.0 | 0.0 / 1.6 | 0.0/0.0 / 0.0/0.0 | 0.8 / 0.8 | 1.1-6.0 | Raises the right arm and waves an open five-finger hand: good on both bodies |
| ual | A_TPose | no | 2.50 / 2.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.1 / -0.2 | 0.0; 0.0 / 0.0; 0.0 | 0.0 / 0.0 | 0.0/0.0 / 0.0/0.0 | 0.0 / 0.0 | 0.0-0.0 | The rest pose exactly: the retarget's rest check in motion |
| ual | Crouch_Fwd_Loop | yes | 2.00 / 2.00 | 0.75 / 0.80 | 15.6/67.9; 16.9/71.9 | -0.5 / -0.5 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0/0.0 / 0.0/0.0 | 24.5 / 24.5 | 19.2-21.8 | Deep sneaking crouch walk, natural; toes kept out of the floor. The game has no crouch yet |
| ual | Crouch_Idle_Loop | yes | 2.93 / 2.93 | 0.00 / 0.00 | 0.3/0.5; 0.3/0.6 | -0.5 / -0.5 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.2) / 0.0 (x0.1) | 0.0/0.0 / 0.0/0.0 | 24.5 / 24.5 | 19.2-26.9 | Deep crouch idle, natural |
| ual | Dance_Loop | yes | 1.00 / 1.00 | 0.00 / 0.00 | 0.1/0.8; 0.1/1.1 | -0.2 / -0.3 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0/0.0 / 0.0/0.0 | 1.2 / 1.2 | 77.9-77.9 | Small bouncing groove with fists: a simple dance emote |
| ual | Death01 | no | 2.40 / 2.40 | 0.00 / 0.00 | 4.3/89.8; 3.9/97.7 | -21.8 / -20.6 | 0.0; 0.0 / 0.0; 0.0 | 134.3 / 134.3 | 0.0/5.3 / 0.1/4.7 | 83.8 / 83.8 | 4.4-77.9 | Staggers, buckles and falls on the back, 2.4 s: the best canned knockdown; sinks 22/21 cm while lying (bigger head and torso than UAL's): needs the floor clamp |
| ual | Driving_Loop | yes | 1.67 / 1.67 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.5 | 0.0; 0.0 / 0.0; 0.0 | 0.1 (x0.3) / 0.1 (x0.3) | 0.0/0.0 / 0.0/0.0 | 59.9 / 59.9 | 77.9-77.9 | Seated steering. Not needed |
| ual | Fixing_Kneeling | no | 5.20 / 5.20 | 0.00 / 0.00 | 0.2/9.9; 0.2/10.7 | -3.2 / -3.4 | 0.0; 0.0 / 0.0; 0.0 | 0.9 / 0.9 | 0.0/0.0 / 0.0/0.0 | 80.9 / 80.9 | 17.8-77.9 | Kneels, works with both hands at the floor, stands up (5.2 s): fits floor tasks and raising a downed player; knee 3 cm into the floor |
| ual | Hit_Chest | no | 0.33 / 0.33 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 14.5 / 14.8 | 0.0/0.0 / 0.0/0.0 | 0.9 / 0.9 | 54.3-77.9 | Short knock back from the chest (0.33 s): subtle |
| ual | Hit_Head | no | 0.43 / 0.43 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 13.7 / 13.7 | 0.0/0.0 / 0.0/0.0 | 0.9 / 0.9 | 54.1-77.9 | Short head knock (0.43 s): subtle |
| ual | Idle_Loop | yes | 2.50 / 2.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 0.4 (x0.9) / 0.4 (x0.9) | 0.0/0.0 / 0.0/0.0 | 0.9 / 0.9 | 77.9-77.9 | Relaxed staggered stance, loose fists, breathing: natural and the same on both bodies |
| ual | Idle_Talking_Loop | yes | 2.93 / 2.93 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.4 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0/0.0 / 0.0/0.0 | 52.2 / 52.2 | 11.7-58.6 | Hands gesture in front of the chest with open, moving fingers: made for proximity voice |
| ual | Idle_Torch_Loop | yes | 1.27 / 1.27 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.1) / 0.0 (x0.1) | 0.0/0.0 / 0.0/0.0 | 28.0 / 28.0 | 55.2-77.9 | Holds an item forward in the right hand: a one-handed hold pose |
| ual | Interact | no | 2.00 / 2.00 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 0.0 / 0.0 | 0.0/0.0 / 0.0/0.0 | 60.6 / 60.6 | 59.2-77.9 | Reaches forward and presses with the index finger: the best interact; forearm twist 61 degrees |
| ual | Jog_Fwd_Loop | yes | 0.93 / 0.93 | 5.95 / 6.42 | 5.7/12.0; 5.8/8.1 | -0.1 / 0.0 | 0.0; 0.0 / 0.0; 0.0 | 0.7 (x0.0) / 0.7 (x0.0) | 0.0/0.0 / 0.0/0.0 | 3.9 / 3.9 | 77.9-77.9 | Long-stride run with a flight phase, clean loop, feet clean: 5.95/6.42 m/s in place (the game walks at 4.5) |
| ual | Jump_Land | no | 1.27 / 1.27 | 0.00 / 0.00 | 0.4/8.4; 0.3/2.1 | -0.5 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 95.6 / 95.6 | 0.0/0.0 / 0.0/0.0 | 27.7 / 27.7 | 12.9-77.9 | Absorbs the landing in a crouch and stands: good |
| ual | Jump_Loop | yes | 2.50 / 2.50 | 0.00 / 0.00 | 0.7/1.8; 0.7/1.9 | -20.2 / -19.4 | 0.0; 0.0 / 0.0; 0.0 | 0.1 (x0.1) / 0.0 (x0.0) | 0.0/0.0 / 0.0/0.0 | 27.7 / 27.7 | 12.9-23.0 | Airborne pose, arms out; in place the feet hang 20 cm below the floor (the game's jump lifts the body) |
| ual | Jump_Start | no | 1.33 / 1.33 | 0.05 / 0.03 | 22.9/171.0; 25.8/184.3 | -21.8 / -20.6 | 0.0; 0.0 / 0.0; 0.0 | 107.6 / 95.6 | 0.0/0.0 / 0.0/0.0 | 27.7 / 27.7 | 12.9-77.9 | Crouch, push off, airborne pose: good; feet below the floor once airborne (in place) |
| ual | PickUp_Table | no | 0.83 / 0.83 | 0.00 / 0.00 | 0.1/0.6; 0.3/1.8 | -0.6 / -0.9 | 0.0; 0.0 / 0.0; 0.0 | 0.0 / 0.0 | 0.0/0.0 / 0.0/0.0 | 0.9 / 0.9 | 25.4-77.9 | Reaches to waist height and brings the item to the chest: a table pickup, not a floor pickup |
| ual | Pistol_Aim_Down | no | 0.17 / 0.17 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.4 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 0.0 / 0.0 | 0.0/0.0 / 0.0/0.0 | 78.1 / 78.1 | 40.2-54.0 | Single aim pose (0.17 s), two-hand grip, index finger extended. Not needed |
| ual | Pistol_Aim_Neutral | no | 0.17 / 0.17 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.4 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 0.1 / 0.0 | 0.0/0.0 / 0.0/0.0 | 78.1 / 78.1 | 40.2-54.0 | Single aim pose. Not needed |
| ual | Pistol_Aim_Up | no | 0.17 / 0.17 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.4 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 0.0 / 0.0 | 0.0/0.0 / 0.0/0.0 | 80.6 / 80.6 | 40.2-54.0 | Single aim pose. Not needed |
| ual | Pistol_Idle_Loop | yes | 1.67 / 1.67 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.4 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.1) / 0.0 (x0.1) | 0.0/0.0 / 0.0/0.0 | 81.6 / 81.6 | 40.2-54.0 | Two-handed grip at chest height (the hands overlap): nearest to a two-hand hold, but not a carry |
| ual | Pistol_Reload | no | 1.67 / 1.67 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.4 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 0.1 / 0.0 | 0.0/0.0 / 0.0/0.0 | 97.1 / 97.1 | 8.7-54.0 | Hands meet and part; forearm twist 97 degrees. Not needed |
| ual | Pistol_Shoot | no | 0.63 / 0.63 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.4 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 0.1 / 0.0 | 0.0/0.0 / 0.0/0.0 | 78.1 / 78.1 | 40.2-54.0 | Recoil from the grip. Not needed |
| ual | Punch_Cross | no | 1.00 / 1.00 | 0.00 / 0.00 | 1.4/48.0; 0.3/8.5 | -0.3 / -0.7 | 0.0; 5.2 / 0.0; 3.5 | 0.0 / 0.0 | 0.0/18.6 / 0.0/17.4 | 11.0 / 11.0 | 77.9-77.9 | Clean guard and straight cross; guard fists 5/3.5 cm inside the big head |
| ual | Punch_Jab | no | 0.87 / 0.87 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.9 | 0.0; 7.9 / 0.0; 6.3 | 0.0 / 0.0 | 0.0/0.0 / 0.0/0.0 | 35.4 / 35.4 | 77.9-77.9 | Clean jab; guard fists 8/6 cm inside the big head |
| ual | Push_Loop | yes | 2.67 / 2.67 | 0.29 / 0.31 | 4.2/25.5; 4.1/27.5 | -0.8 / -0.5 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0/0.0 / 0.0/0.0 | 30.0 / 30.0 | 25.7-25.7 | Leans and pushes a heavy object step by step: the pusher of the game's push |
| ual | Roll | no | 1.47 / 1.47 | 0.00 / 0.00 | 3.6/15.1; 3.8/16.3 | -19.0 / -10.9 | 0.9; 1.2 / 0.8; 0.5 | 97.9 / 94.2 | 0.0/56.3 / 0.0/60.4 | 58.8 / 58.8 | 4.3-77.9 | Dive roll; in place it flies back and forth, legs short by up to 23 cm. Use the root-motion file or skip |
| ual | Sitting_Enter | no | 1.30 / 1.30 | 0.00 / 0.00 | 2.7/55.1; 2.8/57.3 | -0.5 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 88.7 / 85.5 | 0.0/0.0 / 0.0/0.0 | 59.2 / 59.2 | 0.0-77.9 | Sits onto a chair height cleanly. Not needed now |
| ual | Sitting_Exit | no | 1.03 / 1.03 | 0.00 / 0.00 | 3.8/80.1; 4.0/83.0 | -0.5 / -0.8 | 0.8; 0.0 / 1.1; 0.0 | 88.7 / 85.5 | 0.0/0.0 / 0.0/0.0 | 96.8 / 96.8 | 3.6-77.9 | Stands up from a chair cleanly |
| ual | Sitting_Idle_Loop | yes | 1.67 / 1.67 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.7 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.2) / 0.0 (x0.2) | 0.0/0.0 / 0.0/0.0 | 58.9 / 58.9 | 3.1-15.2 | Seated idle, needs a seat |
| ual | Sitting_Talking_Loop | yes | 2.93 / 2.93 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.7 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0/0.0 / 0.0/0.0 | 76.6 / 76.6 | 11.7-58.6 | Seated talking with gestures |
| ual | Spell_Simple_Enter | no | 0.53 / 0.53 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.9 | 0.0; 0.0 / 0.0; 0.0 | 115.8 / 115.8 | 0.0/0.0 / 0.0/0.0 | 23.2 / 23.2 | 14.5-77.9 | Raises an open hand forward: usable as a 'stop' gesture start |
| ual | Spell_Simple_Exit | no | 0.43 / 0.43 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.9 | 0.0; 0.0 / 0.0; 0.0 | 115.8 / 115.8 | 0.0/0.0 / 0.0/0.0 | 23.2 / 23.2 | 14.5-77.9 | Lowers the raised hand |
| ual | Spell_Simple_Idle_Loop | yes | 2.10 / 2.10 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.1) / 0.1 (x0.1) | 0.0/0.0 / 0.0/0.0 | 23.2 / 23.2 | 14.5-21.3 | Holds the open hand out: a 'stop' or 'hold on' gesture |
| ual | Spell_Simple_Shoot | no | 0.50 / 0.50 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.5 / -0.8 | 0.0; 0.0 / 0.0; 0.0 | 0.1 / 0.1 | 0.0/0.0 / 0.0/0.0 | 34.4 / 34.4 | 14.5-25.0 | A push of the open hand |
| ual | Sprint_Loop | yes | 0.67 / 0.67 | 9.04 / 9.72 | 0.0/0.0; 0.0/0.0 | -0.1 / 0.0 | 0.0; 0.0 / 0.0; 0.0 | 0.7 (x0.0) / 0.6 (x0.0) | 0.0/0.0 / 0.0/0.0 | 3.9 / 3.9 | 77.9-77.9 | Strong forward-leaning sprint, clean: 9.0/9.7 m/s in place (the game sprints at 7.0) |
| ual | Swim_Fwd_Loop | yes | 1.33 / 1.33 | 0.06 / 0.68 | 93.0/126.8; 118.7/196.5 | -66.0 / -60.8 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0/0.0 / 0.0/0.0 | 74.2 / 74.2 | 8.3-8.3 | Swimming under the floor line. Not needed |
| ual | Swim_Idle_Loop | yes | 3.33 / 3.33 | 0.54 / 0.58 | 9.5/13.3; 10.1/14.5 | -148.7 / -157.8 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0/0.0 / 0.0/0.0 | 3.8 / 3.8 | 5.9-12.6 | Treading water under the floor line. Not needed |
| ual | Sword_Attack | no | 1.53 / 1.53 | 0.00 / 0.00 | 58.6/695.6; 50.4/738.7 | -0.3 / -0.4 | 0.0; 0.0 / 0.0; 0.0 | 0.0 / 0.0 | 0.0/30.6 / 0.0/31.8 | 25.2 / 25.2 | 17.9-77.9 | Big wind-up and a 1.5 m lunge: too heavy for a knife |
| ual | Sword_Idle | yes | 1.67 / 1.67 | 0.00 / 0.00 | 0.0/0.0; 0.0/0.0 | -0.2 / -0.5 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0/0.0 / 0.0/0.0 | 14.1 / 14.1 | 17.9-77.9 | Crouched fighting stance |
| ual | Walk_Formal_Loop | yes | 1.33 / 1.33 | 1.01 / 1.08 | 2.4/19.1; 2.6/21.0 | -0.2 / -0.2 | 0.0; 0.0 / 0.0; 0.0 | 1.2 (x0.1) / 1.2 (x0.1) | 0.0/0.0 / 0.0/0.0 | 0.3 / 0.3 | 77.9-77.9 | Upright walk, arms close: neat; 1.0/1.1 m/s |
| ual | Walk_Loop | yes | 1.33 / 1.33 | 1.00 / 1.08 | 2.4/19.2; 2.6/21.0 | -0.1 / -0.2 | 0.0; 0.0 / 0.0; 0.0 | 0.0 (x0.0) / 0.0 (x0.0) | 0.0/0.0 / 0.0/0.0 | 2.1 / 2.1 | 77.9-77.9 | Natural walk, relaxed fists, heel strike and toe-off on the floor: 1.0/1.1 m/s |

Notes on the measures: a straight arm in UAL's punches and lunge reads 17 to 32 degrees "past straight" (the Roll 56
to 60 while tumbling) because the forearm's bend plane differs from the upper arm's hinge axis without twist bones;
the strips show straight, unbroken arms. Sole sliding (in `metrics.json`) also counts the toe of the toe-less target foot dragged at toe-off and is not
used for verdicts. In-place jumps and the swims go below the floor by design.

## What the game needs, and the best clip for each

Read from the game repo (read only, 2026-10-03). The game has no crouch, no guns and no fists in its rules.

| Need | Where the game says so | Best clip | Source | State |
|---|---|---|---|---|
| Walk at 4.5 m/s (the lobby and the round) | `content/modes/base_mode.tres:325` `walk_speed_mps = 4.5`; `docs/decisions/2026-10-01-vision-revision-1.md:109` (the living walk, sprint, jump) | Jog_Fwd_Loop at about 0.76x (men) or 0.70x (women); Walk_Loop for slow moves (1.0 m/s), blended by speed | UAL | ready |
| Sprint at 7.0 m/s | `base_mode.tres:326`; `docs/decisions/2026-09-29-mvp-rules.md:101` | Sprint_Loop at about 0.77x (men) or 0.72x (women) | UAL | ready |
| Moving sideways and backwards (first person, free movement; remote bodies are drawn from interpolated positions) | `client/player/player_controller.gd`; `docs/decisions/2026-10-01-m4-first-person-client.md:130-134` | Run_Back for backwards; no side-step strafe in either set (the pack's Run_Left/Right turn the whole body) | pack | **gap** |
| Jump (1.0 m) | `base_mode.tres:329` `jump_height_m = 1.0`; `mvp-rules.md:101` | Jump_Start, Jump_Loop, Jump_Land (in place; the jump physics lifts the body) | UAL | ready |
| Idle | every phase | Idle_Loop (relaxed, the same on both bodies) | UAL | ready |
| Talking by proximity voice | `docs/GDD.md:23` (fun before any match: customization, gestures and proximity voice) | Idle_Talking_Loop (open, moving fingers) | UAL | ready |
| Use, pick up, put down (left mouse, E, Q) | `docs/decisions/2026-10-01-m4-first-person-client.md:81-83`; `mvp-rules.md:90-93` (a key places the item on the ground in front) | Interact (press with the index finger); PickUp_Table (waist height) | UAL | floor pickup and put-down: **gap** |
| Carry the two-handed package | `mvp-rules.md:88-89`; `client/player/first_person_hand.gd:4-10` (held low in the middle with both hands) | none in either set; Pistol_Idle_Loop is the nearest two-hand pose | - | **gap** |
| Hold an item one-handed, the belt item visible | `mvp-rules.md:86-92` | Idle_Torch_Loop as an upper-body hold; the pack's Idle_Sword | UAL / pack | upper-body layer to build |
| Use the knife (narrow, short hit zone, 1.5 m) | `mvp-rules.md:122-127`; `content/items/knife.tres:23` | Sword_Slash (pin the feet); UAL Punch_Jab as a quick stab | pack | fix the feet |
| Being hit | `mvp-rules.md:100-101` (a hit spends stamina) | HitRecieve_2; Hit_Chest and Hit_Head are subtle | pack / UAL | ready |
| Pushing and being pushed | `mvp-rules.md:108-118` | Push_Loop as an upper-body overlay for the pusher; nothing for the pushed | UAL | partial |
| Knocked down: falls where they stand (canned, no ragdoll) | `mvp-rules.md:134-138`; #165 "Q8 read back: falls and knockdowns are canned animations, no ragdoll" | Death01 (a stagger and a fall on the back); the pack's Death is the cartoony alternative | UAL / pack | needs the floor clamp; the look is a question |
| Downed: lying and crawling at 1.0 m/s, giving up | `mvp-rules.md:134-146`; `base_mode.tres:331` `crawl_speed_mps = 1.0`; `client/player/player_controller.gd:8-9` | none (Death01's last frame as a still) | - | **gap** |
| Raising a downed player (hold E) and standing up after a revive | `mvp-rules.md:139-142` | Fixing_Kneeling for the raiser; no get-up from lying | UAL | get-up: **gap** |
| Dead body stays where it fell | `mvp-rules.md:147-148` | the knockdown's last frame | - | ready |
| Gestures with five fingers, emotes | #165 H6 (b) "players must be able to make hand gestures"; `GDD.md:23` | Wave (pack), Dance_Loop, Interact's pointing finger, Spell_Simple_Idle_Loop as "stop" | pack / UAL | thumbs up, clap, cheer, shrug, facepalm, laugh: **gap** |
| First-person hands, forearms in the sleeves of the top | #165 Q10 (b); T18 | none: a first-person clip set on the arms (idle sway, walk bob, use, knife, hold, carry, pick up) | - | **gap** |

## Gaps and options

Money options are questions for the engineer; nothing was bought or downloaded.

| Gap | Free official CC0 source | Paid (one-off, CC0) | Our own in Blender |
|---|---|---|---|
| Carry the package (idle and walk) | **UAL2 Standard**, free: `IDLE_CARRY`, `WALK_CARRY` ([quaternius.itch.io/universal-animation-library-2](https://quaternius.itch.io/universal-animation-library-2), CC0, 42 free animations, the same universal rig) | - | a two-hand upper-body pose layered over the locomotion: 0.5 day |
| Downed: lying, crawling, getting up | UAL2 Standard: `LAYFACEUP` (lying), `KNOCKBACK` | **UAL1 Pro** $9.99 or more: "crawling" among 120+ clips ([quaternius.itch.io/universal-animation-library](https://quaternius.itch.io/universal-animation-library)) | crawl cycle 2 to 3 days; get-up from Death01 in reverse plus Fixing_Kneeling's stand: 1 day |
| Strafes and backwards walk and jog | - | UAL1 Pro: "Locomotion in 8 directions" | side-steps and backpedal from Jog and Walk with the leg IK: 2 days |
| Floor pickup and put-down | - | UAL1 Pro (not itemised on the page) | cut from Fixing_Kneeling's kneel: 0.5 day |
| Emotes and five-finger gestures | UAL2 Standard: `WAVE` | UAL1 Pro: "emotes" (not itemised) | hand-keyed on the five-finger chains: 2 to 4 hours each, about 3 days for six |
| First-person arm set | - | - | 3 to 4 days (same retarget and measures) |
| Source files to edit clips | - | UAL1 Source $14.99 or more; UAL2 Source $14.99 or more (`.blend`) | - |

Prices read on the official itch.io pages on 2026-10-03; quaternius.com lists the same tiers without prices.

## Recommendation

1. **Take UAL as the animation base for both body types**: Idle_Loop, Walk_Loop, Jog_Fwd_Loop (the game's walk),
   Sprint_Loop, Jump_Start/Loop/Land, Interact, PickUp_Table, Fixing_Kneeling (tasks and raising), Idle_Talking_Loop,
   Death01 (knockdown), Hit_Chest, Push_Loop, Dance_Loop. Keep from the pack: Wave, Sword_Slash (the knife), Run_Back,
   HitRecieve_2. Drop the pack's Walk, Run, idles and kicks.
2. **Fix before export:** a floor clamp for lying frames (lift the body by its deepest vertex while no foot carries
   it), pinned feet for Sword_Slash, the guard fists pushed forward if a punch is ever used, and a check of the wrist
   at 60 to 97 degrees of forearm twist in game (or a twist bone in the contract v2).
3. **Close the gaps in this order:** the carry (UAL2 Standard, free), the downed state (lying from UAL2 Standard, crawl
   and get-up), strafes, emotes, the first-person arm set. The retarget tool and the review run on UAL2 unchanged if
   its rig matches (to be checked on the file).
4. **Speeds:** play Jog at about 0.76x (men) or 0.70x (women) for 4.5 m/s and Sprint at about 0.77x or 0.72x for
   7.0 m/s (the in-place ground speeds above, which grow with each body's leg length; UAL's root-motion file gives 5.36 and 8.25 m/s on its own rig, 5.54 and 8.53 scaled to the men).

## Reproduce

```
tools/run.py retarget --body men --clips Walk_Loop,A_TPose
tools/run.py retarget --body women --clips Walk_Loop,A_TPose
tools/run.py anim-review all --out D:/prime-art-raw/review/stage1/20 --jobs 4
```
The full review makes 134 measured clips (strips and MP4s), 28 side-by-side pairs and 23 review sheets with 8 Blender
processes.
