# Meshy's animations on our characters, and a toe bone for the Ultimate Modular feet (art #25, 2026-10-03)

The engineer, after the tests of wave 1: "the feet are broken again". The Ultimate Modular rig has no toe bone, so each
shoe is one rigid piece: at push-off a retargeted clip tips the whole shoe onto its toe (UAL Walk_Loop, side view in
`D:/prime-art-raw/review/stage1/20/`), and the pack's own feet, placed apart from the legs (children of `Root`), lift
and turn sideways in its Walk (m1_rex in art #18's Godot frames). The engineer decided to give the rig a toe bone and to
try Meshy's animations (its library and its text to motion) on our characters for about 60 credits (chat with the art
manager, 2026-10-03, [art #16](https://github.com/xperiaroco2/prime-game-art/issues/16#issuecomment-5971404896)).

Pictures and clips are outside git in `D:/prime-art-raw/review/stage1/25/` (`feet/`, `pairs/`, `strips/`, `clips/`,
`metrics/`, `metrics.md`, `rig_inputs/`). The method is in [../animations.md](../animations.md) (the retarget, the
review, the feet step, the Meshy libraries) and [../meshy.md](../meshy.md) (the client, batch 4's run).

## Summary

- **Toe bones: done.** Every assembled character, and the review's donors, now have `Toe.L` and `Toe.R` (children of
  the feet, at the ball of each shoe; 64 bones in all). UAL's toes (`ball_l`, `ball_r`) and Meshy's (`LeftToeBase`,
  `RightToeBase`) drive them. At push-off the shoe now bends at the ball instead of standing on its tip: with the heel
  lifted 20 degrees and the tip on the floor, the front of a rigid shoe points 12 to 24 degrees into the floor, a shoe
  with toe bones -5 to +1 (level). The pack's own 24 actions key no toe and play exactly as before.
- **Meshy: run.** Batch 4 spent 59 credits (balance 374 -> 315): rigs of m1_rex and w1_ivy, ten library actions on the
  man, two on the woman, one text-to-motion crawl. **Meshy's skeleton has 24 bones, no fingers and one toe per foot**
  (report below).
- **Comparison (a) against (b).** Our retarget onto the Ultimate Modular rig with the toe bones (b) reproduces what
  Meshy's own rig and weights do with the same clip on our mesh (a): the same motion in the pairs, except the upper
  arms, which our rest alignment hangs 5 to 6 degrees closer to the body (below). **On sliding the two are about
  equal.** Measured at the same point on the same mesh (m1_rex), the sole's contact patch slides 4.7 cm/s (median) in
  Meshy's walk on its own rig and 5.6 after our retarget, 4.9 and 4.6 in the backward walk; at the same heel point (our
  foot pivot's rest position, carried by Meshy's foot bone) (b) is only modestly steadier, 3.3/8.8 cm/s mean/max
  against 4.1/20.2. Our retarget follows Meshy's foot, so it cannot plant a heel that Meshy never plants: Meshy's walk
  has no flat stance on either rig (its sole is within 1.5 cm of its lowest point for 2 to 5 of 26 to 32 frames a
  foot; UAL Walk_Loop's for 27 of 41). What the retarget does change is the toe: the front of the shoe stays level at
  push-off instead of tipping into the floor (the backward walk: 7 degrees against 23). The bone-slide column of the
  tables below is not an (a)-against-(b) measure: it reads Meshy's ankle (14 cm up) on (a) and our heel pivot (2.3 cm
  up) on (b); it compares (b) with UAL and the pack, which it reads at the same point. Meshy's forward walks and runs
  float: its walk never comes closer than 0.7 to 0.9 cm to the
  floor on the man, and on the woman's rig its locomotion hangs 1.7 to 7.5 cm above it (Run Fast 7.5 cm), on its own
  rig as on ours: in stance Meshy's feet stay pitched heel-up, so the heel never comes down. The hands have no
  fingers on Meshy's rig: every hand is a flat paddle, and 409 Finger Wag No wags
  the whole hand.
- **Per game need: UAL stays for locomotion; Meshy fills four gaps, but only privately.** UAL1's walk, jog and sprint
  with the toe bones measure as well as Meshy's, stand flat on the floor and are CC0. Meshy's library has what UAL and
  the pack lack, each with work left: a backward walk that slides far less than the pack's Run_Back (3.1 against 33.4
  cm/s at the heel pivot) but sinks its sole into the floor (down to 1.9 cm, more than 1 cm for 6 of 26 frames); a two-step turn in place whose feet stay
  below the floor (down to 1.3 cm, more than 1 cm for 15 of 30 frames) and slide; a face-down downed idle that reaches for help; and a hands-and-knees crawl that
  does not loop (it ends 74 degrees from its start, with a look back inside) and hovers 3 to 5 cm above the floor, so
  it needs a loop cut and a floor fix before it can serve as a downed crawl. Meshy does not say where its library motions come from, so they
  stay private (`public_repo_ok = false`) and cannot enter the public game repo as they are. That is a licence and
  money question for the engineer (below); the UAL1 Pro question still stands for a public-safe crawl and strafes.

## The toe bones

`tools/blender/um/toes.py`, called by the assembler for every character (`build_character`, after the parts are
fitted) and by the retarget and the review for a pack original:

- **Where:** the ball of the foot at 68% of the shoe's length from its back, measured along the foot's forward axis on
  the shoe's vertices weighted to that foot; the bone's head 5 mm above the sole there (the bend axis of a real
  shoe), its tail at the shoe's tip, the foot's axes (X to the character's left: the toe pitches about X).
- **Weights:** every part's foot weights are split over the ball with a smoothstep 5 cm wide (2.5 cm each side):
  behind it the foot keeps its weight, in front the toe takes it, the sum unchanged. m1_rex: 208 shoe vertices
  reweighted; w1_ivy: 386.
- **The pack's actions:** none keys a toe, so a toe stays at rest under its foot and every vertex moves as before.
  The export writes 24 animations of 62 tracks each (1488 in Godot): the toes carry no track and rest in Godot too.
- **The retarget:** `ual_um.toml` maps `ball_l`/`ball_r` onto the toes. A mapped toe takes the source toe's world
  rotation, so it stays level while the heel rises; after the leg IK the bones below each foot are re-attached to it,
  and each toe's tip gets the same floor clamp the rigid foot has (pitched up about the ball until its tip is no lower
  than the rest sole, while the foot is near the floor). `ual_um_rigid.toml` keeps the toes at rest: the shoes of art
  #20 and #24, for the comparison.

### Rigid shoes against toe bones (UAL1, retargeted onto the review donors)

`tools/run.py anim-review feet --out D:/prime-art-raw/review/stage1/25` (the `[[feet]]` row `ual_locomotion`): each
clip retargeted twice onto the same donor, rigid shoes over toe bones; a side close-up following the right shoe (12
frames, `feet/<body>/ual_locomotion_ual_<clip>.png`) and a looping side-by-side MP4 (`.mp4`). Measures from three sole
vertices per shoe (under the foot pivot, under the ball, the tip), while the tip is within 1 cm of the floor.

| Body | Clip | Front of the shoe at a 20 deg heel lift (deg into the floor): rigid -> toes | Heel lift with the front level (deg) | Bend at the ball in contact (deg) | Lowest vertex (cm) | Foot sliding (cm/s, mean) |
|---|---|---|---|---|---|---|
| men | Walk_Loop | 12.3 -> -2.4 | 9.8 -> 47.6 | 46.5 -> 69.1 | -0.1 -> -1.1 | 2.4 (unchanged) |
| men | Jog_Fwd_Loop | - -> -4.7 | 10.9 -> 19.3 | 46.2 -> 47.4 | -0.1 -> -0.7 | 5.7 |
| men | Sprint_Loop | 18.9 -> -4.6 | 12.1 -> 21.9 | 46.1 -> 55.2 | -0.1 -> -0.7 | - |
| women | Walk_Loop | 16.2 -> -1.9 | 11.8 -> 38.1 | 9.7 -> 41.2 | -0.2 -> -0.9 | 2.6 |
| women | Jog_Fwd_Loop | - -> -4.3 | 11.1 -> 19.6 | 9.9 -> 24.7 | 0.0 -> -0.6 | 5.8 |
| women | Sprint_Loop | - -> -4.2 | 10.9 -> 24.2 | 9.8 -> 29.1 | 0.0 -> -0.6 | - |

`-`: no contact sample at a 15 to 25 degree heel lift (a rigid shoe passes it between two frames at 30 fps), or too
few contact velocities for the sliding. The men's rigid shoe already "bends" 46 degrees: Business Man's shoe is
weighted to the shin behind the pivot, so its heel follows the ankle; the women's Suit shoe does not (10 degrees).

Read in the close-ups: at push-off the rigid shoe stands on its tip with the whole sole off the floor; with the toe
bones the front lies on the floor and the shoe bends at the ball, and the toe leaves the floor last, pointing down,
as a foot does. Costs: the sole under the ball dips 0.6 to 1.1 cm below the floor for a frame or two where the blend
zone bends (linear blend skinning; UAL's own mannequin goes 2.7 cm under the floor in Walk_Loop); the foot pivot's
path, so the sliding, does not change. A per-vertex floor clamp would remove the dip if it shows in game.

### For the contract v2

- The rig grows from the pack's 62 bones to 64: `Toe.L` and `Toe.R`, children of `Foot.L` and `Foot.R`, deforming.
  The pack's own 24 actions never animate them (no tracks), so a game clip set that mixes pack clips (Wave,
  Sword_Slash, Run_Back, HitRecieve_2) with retargeted ones must let a toe without a track rest under its foot, which
  Godot does (a missing track leaves the bone at its rest).
- Clips from any source with toes (UAL1, UAL2, Meshy once mapped) drive them; a source without toes leaves them at
  rest, which is the rigid shoe of before.
- Godot's `SkeletonProfileHumanoid` has `LeftToes` and `RightToes`: the humanoid bone map of the contract can map the
  toes (a shared-file change, listed for the manager).
- Every part keeps 64 vertex groups (the pack's 62 and the toes); the face parts keep one (`Head`).

## Meshy: the run (batch 4)

`batches/2026-10-b4-animations.toml`, run by the art manager on 2026-10-03 (18:57 to 19:00 UTC) after the engineer's
yes in chat: **374 credits before, 315 after, 59 spent**, each task charged as estimated (`meshy estimate`: 59 of the
cap of 60). Task ids, files and the balance after each item are in [../meshy.md](../meshy.md) and each item's
`generation.json`; the originals are in `D:/prime-art-raw/2026-10-b4-animations/` and copied to
`OneDrive/prime-art-raw/` (`raw-backup`, 23 files).

| Item | Task id | Credits | What came back |
|---|---|---|---|
| `man-rig` | `01a10320-b412-7299-ad68-92890c4e6853` | 5 | m1_rex rigged; Meshy's walking (32 frames) and running (20), in place |
| `woman-rig` | `01a10321-dc82-74b0-bbbf-d0c66d2f5d58` | 5 | w1_ivy rigged; the same walking and running |
| `man-library` | `01a10322-3570-7439-bd87-2597a408f49c` | 30 | 16 Run Fast, 544 Walk Backward, 577 Idle Step Turn Left, 178 Hit Reaction, 187 Knock Down, 340 Crawl and Look Back, 372 Prone Reach Help, 551 Carry Heavy Object Walk, 317 Shrug, 409 Finger Wag No |
| `woman-library` | `01a10322-a5d5-7169-8499-c1c522bc8ac9` | 6 | 1 Walking Woman, 16 Run Fast |
| `crawl-motion` | `01a10322-c879-7192-a408-0a474c65fc6c` | 10 | the text-to-motion crawl, prime, 4 s, an FBX on an SMPL-H skeleton |
| `man-crawl` | `01a10323-3b62-7512-80e2-9ebfde356052` | 3 | that crawl on the man's rig |

The "stray Icosphere" seen beside every Meshy output in Blender is the glTF importer's own bone display shape: the rig
inputs hold one node and one mesh, Meshy's GLBs the 24 bones, the armature and one mesh (read from the GLBs' JSON), so
nothing of the pack's Icosphere reached Meshy. `meshy rig-input` now checks that its GLB holds one mesh and nothing
else.

## Meshy's skeleton

Read from every GLB of the batch (both rigs, all files: the same 24 names and parents) and checked with
`tools/run.py check --kind body --map meshy` on the man's rigged GLB.

- **24 bones**, `Hips` at the top (no root bone; the hips' location keys carry the travel):

  ```
  Hips
  ├─ Spine02 ─ Spine01 ─ Spine ─┬─ neck ─ Head ─┬─ head_end
  │                             │               └─ headfront
  │                             ├─ LeftShoulder ─ LeftArm ─ LeftForeArm ─ LeftHand
  │                             └─ RightShoulder ─ RightArm ─ RightForeArm ─ RightHand
  ├─ LeftUpLeg ─ LeftLeg ─ LeftFoot ─ LeftToeBase
  └─ RightUpLeg ─ RightLeg ─ RightFoot ─ RightToeBase
  ```

- **Fingers: none.** Each hand is one bone (`LeftHand`); the fingers are weighted to it and never bend. A library clip
  with finger motion (409 Finger Wag No) arrives without it.
- **Toes: one per foot**, `LeftToeBase`, its head at the ball (the man: 4 cm above the floor, 13 cm ahead of the
  ankle), no toe end bone. `LeftFoot` is an ankle bone (its head 14 cm above the floor, pointing down to the ball).
- **Rest:** the pose it was rigged in, our T-pose, facing -Y in Blender (+Z in glTF), the armature at a world scale of
  0.01 (centimetres). The joints are placed by Meshy's estimate, not ours: against the review donors the upper arms
  rest 14.2 to 14.9 degrees (the man) and 9.5 to 10.4 (the woman) below the mesh's arms, its clavicles lie flat where
  ours rise 31 to 35 degrees, its thighs splay 5 degrees out, its spine is within 1 to 9 degrees of ours.
- **Weights:** at most 4 influences a vertex, every vertex weighted; 3539 of the man's 13,659 vertices carry an
  influence below 0.01 (`check`'s warning). The parts arrive merged into one mesh (`char1`) with one textured material
  (our palette).
- **The contract's guess** (`contract/bone_maps/meshy.toml`, art #4, unconfirmed) was Mixamo names with five-finger
  hands; `check --map meshy` refutes it: extra bones `head_end`, `headfront`, `neck` (lower case), no fingers or eyes,
  and the spine the other way round (`Spine02` is the lowest, `Spine` the highest). The corrected map is a request to
  the manager (a shared contract file).
- **Text to motion** returns an FBX on an **SMPL-H** skeleton (52 bones: `Pelvis`, `L_Hip`, ..., three bones per
  finger), 120 frames at 30 fps, with a mannequin of spheres; Meshy's animate task puts it on the rig (fingers lost).

Our bone map, `tools/blender/retarget_maps/meshy_um.toml` (and `meshy_um_rigid.toml` with the toes at rest): `Hips` ->
`Body` (no root: our `Root` rests), the spine, neck, head, shoulders, arms and legs one to one, `LeftToeBase` ->
`Toe.L`, every finger of ours at rest (a relaxed flat hand), the upper arms aligned to Meshy's rest (`[align]`, so an
arm that hangs at the side on Meshy's rig hangs at the side on ours). Rest check: 0.002 mm and 0 degrees outside the
aligned arms. `retarget --library meshy` and `--library meshyw` bake its clips onto either donor.

## The clips, as seen in the strips and the clips

| Clip (`meshy:`, `meshyw:`) | Length | What it is |
|---|---|---|
| Walking, Running (each rig's) | 1.03 s, 0.63 s, loops | a natural walk at 1.5 m/s with arms a little away from the body; a jog at 5.6 m/s |
| RunFast (16) | 0.47 s, loop | a sprinter's dash: the body leans 40 to 50 degrees forward, the legs reach far back; 6.4 m/s (the game's sprint is 7.0) |
| Walking_Woman (1) | 0.97 s, loop | a walk with a sway of the hips |
| Walk_Backward (544) | 0.87 s, loop | a cautious backward walk, arms out in front, 1.2 m/s of travel (taken out in the review) |
| Idle_Step_Turn_Left (577) | 1.0 s | two steps that turn the body 90 degrees to the left |
| Hit_Reaction (178) | 1.63 s | struck from the side: a stagger 0.94 m sideways with the arms up (taken out in the review) |
| Knock_Down (187) | 2.5 s | thrown up and back, a half somersault, landing on the back 0.8 m behind; cartoon-strong |
| Prone_Reach_Help (372) | 18.4 s, loop | lying face down, the head turned, one arm reaching up twice for help |
| Crawl_and_Look_Back (340) | 6.9 s | a hands-and-knees crawl, head up, with a look back over the shoulder; 3.3 m of travel (taken out) |
| Crawl_Prompt (text to motion) | 3.97 s | a low hands-and-knees crawl, heading 20 degrees to the right of straight ahead; asked to loop, its ends are 59 degrees apart (7 times a frame step) |
| Carry_Heavy_Object_Walk (551) | 6.5 s, loop | a slow waddle leaning back with the arms wide around a big box, 0.3 m/s |
| Shrug (317) | 1.97 s | both shoulders and palms up |
| Finger_Wag_No (409) | 5.0 s | a "no" with the whole flat hand (no fingers) and a head shake |

## Comparison (a) and (b): the feet first

Each set plays, top to bottom: (a) the clip on Meshy's own rig and weights (m1_rex or w1_ivy as Meshy rigged them), (b)
the same clip retargeted onto the review donor's rig with the toe bones (Business Man, Suit), and the best UAL1 or pack
clip for the need (with the toe bones). `tools/run.py anim-review feet --only meshy_feet_men,meshy_feet_women` (close-ups
of the right shoe from its side, `feet/<body>/meshy_feet_<body>_<clip>.png` and `.mp4`). The sliding is the foot
bone's (on Meshy's rig its ankle, 14 cm up, on ours the heel pivot, 2.3 cm up: compare (b) with UAL and the pack,
not (a) with (b); the same-point measures are in the first bullet below), `-` with fewer than 4 contact velocities (the runs touch down
for a frame or two); the toe measures count contact within 1 cm of the floor, or of the tips' own lowest point when a
clip never reaches the floor (Meshy's), `-` without a sample at a 15 to 25 degree heel lift.

| Body | Need | Lane | Front of the shoe at a 20 deg heel lift (deg into the floor) | Heel lift, front level (deg) | Tip lowest (cm) | Foot slide mean/max (cm/s) | Lowest vertex (cm) |
|---|---|---|---|---|---|---|---|
| men | walk | (a) Meshy's rig Walking | - | - | 0.7 | 6.1/39.6 | 0.7 |
| men | walk | (b) Meshy, man's rig Walking | 0.7 | 32.3 | 1.1 | 3.3/8.7 | 0.9 |
| men | walk | UAL1 Walk_Loop | -2.4 | 47.6 | 0.3 | 2.4/19.2 | -1.1 |
| men | run | (a) Meshy's rig Running | - | - | 0.6 | - | 0.6 |
| men | run | (b) Meshy, man's rig Running | -1.0 | 24.2 | 1.0 | - | 0.4 |
| men | run | UAL1 Jog_Fwd_Loop | -4.7 | 19.3 | 0.3 | 5.7/12.0 | -0.7 |
| men | sprint | (a) Meshy's rig RunFast | 14.1 | - | 1.2 | - | 1.2 |
| men | sprint | (b) Meshy, man's rig RunFast | - | - | 1.2 | - | 1.1 |
| men | sprint | UAL1 Sprint_Loop | -4.6 | 21.9 | 0.3 | - | -0.7 |
| men | backwards | (a) Meshy's rig Walk_Backward | 22.7 | 25.7 | -1.7 | 11.1/77.9 | -1.9 |
| men | backwards | (b) Meshy, man's rig Walk_Backward | 7.4 | 21.8 | 0.3 | 3.1/12.0 | -1.9 |
| men | backwards | pack Run_Back | 21.3 | 7.5 | 0.2 | 33.4/84.0 | -0.3 |
| women | walk | (a) Meshy's woman rig Walking_Woman | -4.3 | 27.8 | 8.6 | 7.6/41.9 | 2.4 |
| women | walk | (b) Meshy, woman's rig Walking_Woman | 32.9 | 26.4 | 7.9 | 5.1/17.6 | 2.6 |
| women | walk | (b) Meshy, man's rig Walking | 0.3 | 39.8 | 3.4 | 3.4/9.5 | 2.7 |
| women | walk | UAL1 Walk_Loop | -1.9 | 38.1 | 0.3 | 2.6/21.0 | -0.9 |
| women | run | (a) Meshy's woman rig Running | - | -7.1 | 8.3 | - | 2.4 |
| women | run | (b) Meshy, woman's rig Running | - | 4.3 | 8.0 | - | 2.6 |
| women | run | UAL1 Jog_Fwd_Loop | -4.3 | 19.6 | 0.3 | 5.8/8.1 | -0.6 |
| women | sprint | (a) Meshy's woman rig RunFast | - | 3.6 | 8.5 | - | 7.5 |
| women | sprint | (b) Meshy, woman's rig RunFast | - | - | 7.8 | - | 7.5 |
| women | sprint | UAL1 Sprint_Loop | -4.2 | 24.2 | 0.3 | - | -0.6 |
| women | backwards | (b) Meshy, man's rig Walk_Backward | 17.2 | 27.2 | 0.3 | 3.5/11.3 | -1.8 |
| women | backwards | pack Run_Back | - | 8.9 | 0.2 | 30.2/77.1 | -0.3 |

Read in the close-ups and the measures:

- **The toes of (b) are better than (a); the sliding is about the same.** After our retarget Meshy's walk keeps the
  front of the shoe level at push-off (0.7 degrees at a 20 degree heel lift; UAL's -2.4); on its own rig the backward
  walk pushes the front of the shoe 23 degrees into the floor, retargeted 7. The sliding was measured again during the
  review at the same point on both, because the column above reads different bones: with the sole's contact patch (the
  vertices within 3 mm of each shoe's lowest point, followed from frame to frame, less the ground speed, contact within
  2.5 cm of the floor) on the same mesh, m1_rex, Meshy's walk slides 4.7/14.0/61.7 cm/s (median/mean/max) on its own
  rig and 5.6/16.5/85.3 after our retarget (5.6/16.4/85.3 on Business Man), the backward walk 4.9 and 4.6 (median);
  with the heel point (our pivot's rest position carried by Meshy's `LeftFoot`, resampled to 30 fps) 4.1/20.2 (a)
  against 3.3/8.8 (b) mean/max, where the IK capping overstretched legs may account for (b)'s lower peaks. Meshy's walk
  has no planted stance on either rig: with a 1.5 cm contact window its sole touches for 2 to 5 of 26 to 32 frames a
  foot, UAL Walk_Loop's for 27 of 41 (median slide 1.3 cm/s). Neither the stance nor the sliding can be fixed by
  following Meshy's foot more closely; a fix would plant the heel (below).
- **Meshy's forward walks and runs float: their feet never come flat.** (The backward walk, the turn, the hit and the
  lying clips go into the floor instead: table below.) The man's walk and runs never come closer than 0.4 to 1.2 cm to
  the floor, on Meshy's rig as on ours; on the woman's rig 1.7 to 7.5 cm (Run Fast 7.5 cm, on its own rig too), and on
  the women's donor every forward Meshy walk and run, the man's included, 2 to 3 cm (the woman's Run Fast 7.5). The cause is in the
  clips: in stance Meshy's foot stays pitched heel-up and its toe bent 10 to 17 degrees back against it (Walking on the
  man's rig, Walking Woman on the woman's, sampled every 3 frames), so the heel never comes down; our retarget follows
  Meshy's foot, so the heel pivot of the women's donor stands about 4 cm above its rest height in stance (6.2 to 6.6 cm
  against 2.3). The tip measures of the woman's-rig clips are therefore taken in the air (their tips never come lower
  than 8 cm) and are not comparable. A fix would be ours (a foot-flat correction or a floor clamp of the heel in the
  retarget, or the game's foot IK); UAL's clips do not need one.
- **The pack's Run_Back slides** 33 cm/s and tips its rigid toe 21 degrees into the floor; Meshy's Walk_Backward slides
  far less (3.1 cm/s, the same heel pivot) and keeps the toe at 7 degrees, but its sole goes down to 1.9 cm into the floor,
  more than 1 cm for 6 of 26 frames (the source's own depth: `retarget --floor` reads -1.9 cm on Meshy's mesh too).

The toe bones on Meshy's clips (`anim-review feet --only meshy_toes`, `feet/men/meshy_toes_meshy_*.png`): rigid shoes
on top, toe bones below.

| Clip (men) | Front at a 20 deg lift: rigid -> toes | Heel lift, front level: rigid -> toes | Bend in contact: rigid -> toes | Tip lowest cm: rigid -> toes |
|---|---|---|---|---|
| meshy:Walking | 24.2 -> 0.7 | - -> 32.3 | 46.2 -> 52.4 | 0.3 -> 1.1 |
| meshy:RunFast | - -> - | - -> - | 45.2 -> 45.6 | 0.8 -> 1.2 |

## Comparison (a) and (b): every clip, with art #20's measures

`tools/run.py anim-review clips --sources meshy,meshyw` (b, both libraries on both donors: the man's library clips on
the women's donor too), `clips --body men --clips meshy_own:...` and `--body women --clips meshyw_own:...` (a), with the
best UAL1, UAL2 and pack clips of each need measured in the same run; `pairs --sources meshy,meshyw` for the side by
side (`pairs/<body>/meshy_<body>_<need>.png`, `.mp4`); the table is `metrics.md` (75 clips). The rows here are the
Meshy clips and the clip each one competes with.

| Body | Need | Clip | s | Loop | Ground m/s | Foot slide mean/max cm/s | Lowest vertex min cm (frames under -1 cm) | Front at 20 deg lift | Hands in torso/head/other hand/legs cm | Seam deg (x step) | Forearm twist deg |
|---|---|---|---|---|---|---|---|---|---|---|---|
| men | walk | (a) Meshy's rig Walking | 1.03 | yes | 1.52 | 6.1/39.6 | 0.7 (0) | - | 0.0/0.0/0.0/0.7 | 0.0 (0.0) | 15.0 |
| men | walk | (b) Meshy, man's rig Walking | 1.03 | yes | 1.58 | 3.3/8.7 | 0.9 (0) | 0.7 | 0.0/0.0/0.0/0.9 | 0.0 (0.0) | 15.8 |
| men | walk | UAL1 Walk_Loop | 1.33 | yes | 1.00 | 2.4/19.2 | -1.1 (1) | -2.4 | 0.0/0.0/0.0/0.0 | 0.0 (0.0) | 2.1 |
| women | walk | (a) Meshy's woman rig Walking_Woman | 0.97 | yes | 1.57 | 7.6/41.9 | 2.4 (0) | -4.3 | 0.0/0.0/0.0/6.3 | 0.0 (0.0) | 58.0 |
| women | walk | (b) Meshy, woman's rig Walking_Woman | 0.97 | yes | 1.68 | 5.1/17.6 | 2.6 (0) | 32.9 | 0.0/0.0/0.0/6.1 | 0.0 (0.0) | 57.6 |
| women | walk | (a) Meshy's woman rig Walking | 1.03 | yes | 1.56 | 6.6/22.4 | 1.7 (0) | -0.1 | 0.0/0.0/0.0/2.6 | 0.0 (0.0) | 13.1 |
| women | walk | (b) Meshy, woman's rig Walking | 1.03 | yes | 1.66 | 7.9/17.6 | 2.0 (0) | 7.8 | 0.0/0.0/0.0/5.3 | 0.0 (0.0) | 12.9 |
| women | walk | (b) Meshy, man's rig Walking | 1.03 | yes | 1.70 | 3.4/9.5 | 2.7 (0) | 0.3 | 0.0/0.0/0.0/3.9 | 0.0 (0.0) | 15.8 |
| women | walk | UAL1 Walk_Loop | 1.33 | yes | 1.08 | 2.6/21.0 | -0.9 (0) | -1.9 | 0.0/0.0/0.0/3.3 | 0.0 (0.0) | 2.1 |
| men | run | (a) Meshy's rig Running | 0.63 | yes | 5.44 | - | 0.6 (0) | - | 0.0/0.0/0.0/0.0 | 0.1 (0.0) | 22.5 |
| men | run | (b) Meshy, man's rig Running | 0.63 | yes | 5.59 | - | 0.4 (0) | -1.0 | 0.0/0.0/0.0/0.0 | 0.0 (0.0) | 24.4 |
| men | run | UAL1 Jog_Fwd_Loop | 0.93 | yes | 5.95 | 5.7/12.0 | -0.7 (0) | -4.7 | 0.0/0.0/0.0/0.0 | 0.7 (0.0) | 3.9 |
| women | run | (a) Meshy's woman rig Running | 0.63 | yes | 5.76 | - | 2.4 (0) | - | 0.0/0.0/0.0/0.0 | 0.0 (0.0) | 25.5 |
| women | run | (b) Meshy, woman's rig Running | 0.63 | yes | 5.98 | - | 2.6 (0) | - | 0.0/0.0/0.0/0.0 | 0.0 (0.0) | 25.3 |
| women | run | UAL1 Jog_Fwd_Loop | 0.93 | yes | 6.42 | 5.8/8.1 | -0.6 (0) | -4.3 | 0.0/0.0/0.0/0.0 | 0.7 (0.0) | 3.9 |
| men | sprint | (a) Meshy's rig RunFast | 0.47 | yes | 6.09 | - | 1.2 (0) | 14.1 | 0.0/0.0/0.0/0.0 | 12.2 (0.4) | 17.5 |
| men | sprint | (b) Meshy, man's rig RunFast | 0.47 | yes | 6.41 | - | 1.1 (0) | - | 0.0/0.0/0.0/0.0 | 11.7 (0.3) | 17.0 |
| men | sprint | UAL1 Sprint_Loop | 0.67 | yes | 9.04 | - | -0.7 (0) | -4.6 | 0.0/0.0/0.0/0.0 | 0.7 (0.0) | 3.9 |
| women | sprint | (a) Meshy's woman rig RunFast | 0.47 | yes | 6.40 | - | 7.5 (0) | - | 0.0/0.0/0.0/0.0 | 12.2 (0.4) | 19.1 |
| women | sprint | (b) Meshy, woman's rig RunFast | 0.47 | yes | 7.16 | - | 7.5 (0) | - | 0.0/0.0/0.0/0.0 | 11.2 (0.3) | 19.4 |
| women | sprint | UAL1 Sprint_Loop | 0.67 | yes | 9.72 | - | -0.6 (0) | -4.2 | 0.0/0.0/0.0/0.0 | 0.6 (0.0) | 3.9 |
| men | backwards | (a) Meshy's rig Walk_Backward | 0.87 | yes | 1.40 | 11.1/77.9 | -1.9 (8) | 22.7 | 0.0/0.0/0.0/0.0 | 6.1 (0.7) | 27.0 |
| men | backwards | (b) Meshy, man's rig Walk_Backward | 0.87 | yes | 1.40 | 3.1/12.0 | -1.9 (6) | 7.4 | 0.0/0.0/0.0/0.0 | 8.7 (0.9) | 26.8 |
| men | backwards | pack Run_Back | 0.83 | yes | 3.09 | 33.4/84.0 | -0.3 (0) | 21.3 | 0.0/0.0/0.0/0.0 | 0.0 (0.0) | 1.8 |
| women | backwards | (b) Meshy, man's rig Walk_Backward | 0.87 | yes | 1.51 | 3.5/11.3 | -1.8 (6) | 17.2 | 0.0/0.0/0.0/0.0 | 8.7 (0.9) | 26.8 |
| women | backwards | pack Run_Back | 1.03 | yes | 2.46 | 30.2/77.1 | -0.3 (0) | - | 0.0/0.0/0.0/0.0 | 1.6 (0.1) | 1.8 |
| men | turn in place | (a) Meshy's rig Idle_Step_Turn_Left | 1.00 | no | 0.02 | 15.9/85.5 | -1.6 (31) | - | 0.0/0.0/0.0/0.0 | 86.8 (23.1) | 32.1 |
| men | turn in place | (b) Meshy, man's rig Idle_Step_Turn_Left | 1.00 | no | 0.02 | 12.3/83.3 | -1.3 (15) | - | 0.0/0.0/0.0/0.0 | 86.8 (17.2) | 33.6 |
| men | turn in place | UAL1 Idle_Loop | 2.50 | yes | 0.00 | 0.0/0.0 | -0.6 (0) | - | 0.0/0.0/0.0/0.0 | 0.4 (0.6) | 0.9 |
| women | turn in place | (b) Meshy, man's rig Idle_Step_Turn_Left | 1.00 | no | 0.03 | 12.6/84.8 | -1.7 (18) | - | 0.0/0.0/0.0/1.0 | 86.8 (17.2) | 33.6 |
| men | pushed | (a) Meshy's rig Hit_Reaction | 1.63 | no | 0.60 | 7.7/80.2 | -3.9 (46) | 19.5 | 0.0/0.0/0.0/0.0 | 0.6 (0.1) | 48.2 |
| men | pushed | (b) Meshy, man's rig Hit_Reaction | 1.63 | no | 0.61 | 7.5/79.1 | -3.4 (46) | 19.6 | 0.0/0.0/0.0/0.0 | 0.6 (0.1) | 48.0 |
| men | pushed | UAL2 Hit_Knockback | 0.83 | no | - | - | -0.9 (0) | - | 0.0/0.0/0.0/1.3 | 164.5 (6.1) | 11.1 |
| men | pushed | UAL1 Hit_Chest | 0.33 | no | 0.00 | 0.0/0.0 | -0.6 (0) | - | 0.0/0.0/0.0/0.0 | 13.5 (1.6) | 0.9 |
| women | pushed | (b) Meshy, man's rig Hit_Reaction | 1.63 | no | 0.66 | 8.0/78.3 | -3.7 (46) | - | 0.0/0.0/0.0/0.0 | 0.6 (0.1) | 48.0 |
| women | pushed | UAL2 Hit_Knockback | 0.83 | no | - | - | -1.0 (1) | - | 0.0/0.0/0.0/7.2 | 164.5 (6.1) | 11.1 |
| men | knocked down | (a) Meshy's rig Knock_Down | 2.50 | no | 0.11 | 17.5/25.2 | -5.1 (34) | - | 0.0/2.3/2.1/0.0 | 96.0 (8.0) | 68.9 |
| men | knocked down | (b) Meshy, man's rig Knock_Down | 2.50 | no | 0.06 | 11.5/25.3 | -2.8 (5) | - | 0.0/6.9/2.2/0.0 | 96.1 (7.9) | 70.0 |
| men | knocked down | UAL1 Death01 | 2.40 | no | 0.00 | 4.3/89.8 | -4.9 (2) | - | 0.0/0.0/0.0/0.0 | 134.3 (20.8) | 83.8 |
| women | knocked down | (b) Meshy, man's rig Knock_Down | 2.50 | no | 0.06 | 14.1/32.6 | -3.0 (5) | - | 0.0/2.9/2.0/0.0 | 96.1 (7.9) | 70.0 |
| women | knocked down | UAL1 Death01 | 2.40 | no | 0.00 | 3.9/97.7 | -3.4 (2) | - | 0.0/0.0/0.0/5.3 | 134.3 (19.5) | 83.8 |
| men | downed | (a) Meshy's rig Prone_Reach_Help | 18.40 | yes | 0.00 | 0.6/9.6 | -4.8 (159) | - | 0.0/0.0/0.0/0.0 | 0.1 (0.1) | 37.7 |
| men | downed | (b) Meshy, man's rig Prone_Reach_Help | 18.40 | yes | 0.00 | 0.5/5.1 | -5.4 (432) | - | 0.0/4.1/0.9/0.0 | 0.1 (0.1) | 36.4 |
| men | downed | UAL2 LayToIdle | 1.53 | no | 0.01 | 7.5/55.6 | -4.0 (30) | - | 0.0/0.0/0.0/0.0 | 94.2 (6.1) | 84.4 |
| women | downed | (b) Meshy, man's rig Prone_Reach_Help | 18.40 | yes | 0.00 | 0.4/4.4 | -3.1 (553) | - | 0.0/0.0/1.2/0.0 | 0.1 (0.1) | 36.4 |
| women | downed | UAL2 LayToIdle | 1.53 | no | 0.01 | 7.8/58.1 | -4.1 (31) | - | 0.0/0.0/0.0/2.8 | 94.2 (6.1) | 84.4 |
| men | crawl | (a) Meshy's rig Crawl_and_Look_Back | 6.90 | no | 0.81 | 28.1/74.9 | 3.2 (0) | - | 0.0/0.0/0.0/0.0 | 74.0 (7.8) | 108.4 |
| men | crawl | (b) Meshy, man's rig Crawl_and_Look_Back | 6.90 | no | 0.63 | 29.8/101.2 | 3.4 (0) | - | 0.0/0.0/0.2/0.0 | 74.0 (8.1) | 117.1 |
| men | crawl | (a) Meshy's rig Crawl_Prompt | 3.97 | no | 0.47 | 68.7/117.7 | 2.7 (0) | - | 0.0/0.0/2.3/0.0 | 58.9 (7.1) | 0.0 |
| men | crawl | (b) Meshy, man's rig Crawl_Prompt | 3.97 | no | 0.75 | 51.4/102.7 | -0.4 (0) | - | 0.0/0.0/2.3/0.0 | 58.9 (7.1) | 0.0 |
| women | crawl | (b) Meshy, man's rig Crawl_and_Look_Back | 6.90 | no | 0.51 | 28.6/68.4 | 4.8 (0) | - | 0.0/0.0/0.0/0.0 | 74.0 (8.1) | 117.1 |
| women | crawl | (b) Meshy, man's rig Crawl_Prompt | 3.97 | no | 0.89 | 55.4/110.6 | 3.4 (0) | - | 0.0/0.0/1.9/0.0 | 58.9 (7.3) | 0.0 |
| men | carry | (a) Meshy's rig Carry_Heavy_Object_Walk | 6.50 | yes | 0.33 | 5.5/99.3 | -2.3 (15) | 22.7 | 0.0/0.0/0.0/0.0 | 0.0 (0.0) | 58.2 |
| men | carry | (b) Meshy, man's rig Carry_Heavy_Object_Walk | 6.50 | yes | 0.34 | 7.9/167.9 | -0.6 (0) | 20.5 | 0.0/0.0/0.0/0.0 | 0.0 (0.0) | 63.2 |
| men | carry | UAL2 Walk_Carry_Loop | 2.00 | yes | 0.67 | 1.1/28.0 | -1.1 (1) | -2.4 | 0.0/0.0/0.7/0.0 | 0.1 (0.0) | 37.0 |
| women | carry | (b) Meshy, man's rig Carry_Heavy_Object_Walk | 6.50 | yes | 0.37 | 7.8/130.3 | -0.6 (0) | 23.6 | 0.0/0.0/0.0/0.0 | 0.0 (0.0) | 63.2 |
| women | carry | UAL2 Walk_Carry_Loop | 2.00 | yes | 0.72 | 1.2/29.9 | -0.8 (0) | -1.6 | 0.0/0.0/1.1/0.0 | 0.0 (0.0) | 37.0 |
| men | gestures | (a) Meshy's rig Shrug | 1.97 | no | 0.00 | 0.3/1.1 | -2.5 (60) | - | 0.0/0.0/0.0/0.0 | 0.8 (0.3) | 82.1 |
| men | gestures | (b) Meshy, man's rig Shrug | 1.97 | no | 0.00 | 0.3/1.0 | -2.3 (60) | - | 0.0/0.0/0.0/0.0 | 0.8 (0.3) | 77.8 |
| men | gestures | (a) Meshy's rig Finger_Wag_No | 5.00 | no | 0.00 | 1.2/4.4 | -3.0 (151) | - | 0.0/0.0/0.0/0.0 | 0.0 (0.0) | 74.3 |
| men | gestures | (b) Meshy, man's rig Finger_Wag_No | 5.00 | no | 0.00 | 1.2/3.6 | -3.1 (151) | - | 0.0/0.0/0.0/0.0 | 0.0 (0.0) | 76.6 |
| men | gestures | UAL2 Yes | 2.50 | no | 0.00 | 0.3/3.3 | -0.7 (0) | - | 0.0/0.0/0.0/0.0 | 0.2 (0.1) | 2.5 |
| men | gestures | UAL2 Idle_No_Loop | 2.50 | yes | 0.00 | 0.0/0.0 | -0.6 (0) | - | 0.0/0.0/0.0/0.0 | 0.2 (0.1) | 0.9 |
| women | gestures | (b) Meshy, man's rig Shrug | 1.97 | no | 0.00 | 0.3/1.1 | -2.5 (60) | - | 0.0/0.0/0.0/0.0 | 0.8 (0.3) | 77.8 |
| women | gestures | (b) Meshy, man's rig Finger_Wag_No | 5.00 | no | 0.00 | 1.3/3.9 | -3.1 (151) | - | 0.0/0.0/0.0/0.0 | 0.0 (0.0) | 76.6 |

- **(a) against (b), pose for pose:** the pairs show the same motion; the retarget changes the feet (above) and the
  arms (aligned to Meshy's rest, the same hang as on its own rig), nothing else. The (a) and (b) numbers differ where
  the rigs differ: the feet (IK), the depth into the floor of lying clips (our hips scaled to our legs: Prone Reach Help
  goes 5.4 cm into the floor on our man, 4.8 on its own rig; UAL2's LayToIdle 4.0).
- **Hands.** No hand goes into the torso in any Meshy clip; Knock_Down puts a hand into the head during the somersault
  (on the man 2.3 cm on Meshy's rig, 6.9 cm after the retarget). Without fingers the hands are flat in every clip; our retarget keeps our
  fingers relaxed at rest, so (b) looks the same as (a). The forearm twist reaches 108 to 117 degrees in Crawl and
  Look Back and 74 to 82 in Shrug and Finger Wag No (no twist bones on either rig: the wrist wraps), against 37 for
  UAL2's carry. Finger Wag No fails the finger test: the gesture is a wagging flat hand.
- **Loops.** Meshy's walking, running, Run Fast, Walk Backward, Walking Woman, the carry walk and the prone idle end
  where they start (0 to 0.9 times a frame step); the text-to-motion crawl does not (7 times), although the prompt
  asked for a loop.

## Licences

- **The rig inputs** are our own work from CC0 parts (Quaternius Ultimate Modular, our face kit).
- **Meshy's outputs on the Pro plan** (the rigs, the animated GLBs and FBXs, the text-to-motion clip) are owned by us
  (Meshy Terms of Use 3.2, updated 2026-09-19); Meshy keeps a licence to provide the service. Every one is recorded in
  its `generation.json` (plan, terms URL, licence line, task ids, sha256 per file).
- **Text to motion is `ai_generated = true`.** Its raw FBX is on an SMPL-H skeleton, the body model of the research
  motion datasets; Meshy does not say what its model was trained on. Ownership of the output does not tell whether
  the training data allowed commercial use, so the clip is treated like the library clips below until Meshy says.
- **The library motions' provenance is not disclosed** (motion capture of its own, bought libraries, or generation):
  ownership of the output under 3.2 says the output is ours, not that the motion underneath is free of third-party
  rights, and bought motion libraries usually allow use inside a game but not redistribution of the raw files. So
  for the art repo's rules: **`public_repo_ok = false`** for every manifest that uses a Meshy library clip or the
  text-to-motion clip, `ai_generated = true` for the text-to-motion clip and unknown (recorded as such) for the library
  clips, and the raw files stay private (`D:/prime-art-raw/2026-10-b4-animations/` and OneDrive, never in git). A clip
  we retarget, clean up or key by hand from one of them is still derived from it. **The game repo is public**, so in
  this state no Meshy clip can enter it; the question for the engineer is below.

## Recommendation per game need

From art #20's and #24's needs table. "Private" means usable only if the engineer decides how a
`public_repo_ok = false` clip may reach the game (below).

| Need | Recommendation | Meshy's clip, as tried |
|---|---|---|
| Walk 4.5 m/s | **UAL1** Walk_Loop/Jog_Fwd_Loop blend with the toe bones (CC0) | Walking: natural; after our retarget the front of the shoe stays level, but the heel never plants (no flat stance) and it floats 0.9 cm; private |
| Sprint 7.0 m/s | **UAL1** Sprint_Loop (and the Jog blend) with the toe bones | Run Fast: a sprinter's dash with a 40 to 50 degree lean, 6.4 m/s; a look choice (designer) and private |
| Moving backwards | **pack** Run_Back for now; **Meshy** Walk_Backward if private clips are allowed (slide 3.1 against 33.4 cm/s, front of the shoe 7 against 21 degrees) | the best backward clip we have; its sole sinks down to 1.9 cm, more than 1 cm for 6 of 26 frames (a floor clamp in the retarget would take it out) |
| Moving sideways | gap (no clean strafe in UAL1, UAL2, the pack or Meshy's library) | none in the library |
| Turning in place | **Meshy** Idle_Step_Turn_Left (mirrored for the right) if private clips are allowed; else turn the idle in the engine | a readable two-step 90 degree turn, but the feet stay below the floor (down to 1.3 cm, more than 1 cm for 15 of 30 frames) and slide (12 cm/s mean): it needs a floor fix |
| Being pushed | **UAL2** Hit_Knockback / **UAL1** Hit_Chest (as art #24) | Hit Reaction: a readable sideways stagger; private |
| Knocked down | **UAL1** Death01 (as art #20) | Knock Down: a cartoon somersault; a look choice and private |
| Downed (lying, waiting for a revive) | **Meshy** Prone_Reach_Help if private clips are allowed (the only downed idle); **UAL2** LayToIdle for the get-up | face down, reaching for help; UAL2's get-up starts on the back, so the two do not join without a turn-over |
| Crawling while downed | no ready clip. **UAL1 Pro** for a public-safe crawl; **Meshy** Crawl_and_Look_Back only if private clips are allowed and after a loop cut (it does not loop: 74 degree seam, 8 frame steps, a look back inside its 6.9 s) and a floor fix (hands and knees hover 3 to 5 cm) | both Meshy crawls need work: the library crawl reads better in motion, the text-to-motion crawl heads 20 degrees off and does not loop either (59 degree seam); not worth more credits |
| Carrying the package | **UAL2** Walk_Carry_Loop's upper body (as art #24): the package is small, held close | Carry Heavy Object Walk is a wide box and a waddle: another prop |
| Gestures, emotes | **UAL2** Yes, folded arms, No and the **pack** Wave (as art #24) | Shrug works without fingers (private); Finger Wag No fails without fingers |
| Everything else (idle, jump, use, talk, knife, hit) | as art #20 and #24 recommend | not tried |

**Meshy for animation, overall:** worth it for gaps only, not for locomotion. The clips themselves are good motion
capture quality apart from the feet (heel up in stance, floating); Meshy's own rig tips the shoe into the floor where
our toe bones keep it level, slides about as much as our retarget, and has no fingers, so whatever we take from Meshy we take as a clip and retarget onto our rig, which this task now does
(`meshy_um.toml`). Text to motion gave a usable but crooked crawl for 13 credits; the library is the better buy.

**The UAL1 Pro money question still stands**: Meshy's library can fill the backward walk, the turn, the downed idle
and (after a loop cut and a floor fix) the crawl only privately, and fills no strafe at all; UAL1 Pro (CC0, $9.99, per art #20's research) remains the
cheap public-safe source for crawling and 8-direction locomotion.

## Questions for the engineer (licence and money)

1. **May a Meshy library clip reach the game, and how?** The game repo is public; the clips are `public_repo_ok =
   false` while Meshy does not disclose their source. Options: (a) no: Meshy stays for props, the gaps go to UAL1 Pro
   and our own keys; (b) ask Meshy support in writing whether library animations may be redistributed in a public
   repository (the engineer writes, or allows the manager to draft it); (c) keep such clips out of the public repo (a
   private asset pack the game loads). **Recommendation: (b) first, and (a) meanwhile**: nothing waits on Meshy, and
   UAL1 Pro answers the crawl publicly.
2. **UAL1 Pro ($9.99)** for a public-safe crawl and strafes: recommended (unchanged since art #20).
3. **The look** (with the designer): Run Fast's sprinter's lean and Knock Down's somersault are style choices; neither
   is recommended for the game's tone without the designer's eye (both are private anyway).

## Reproduce

```
tools/run.py retarget --library meshy --body men --clips Walking,RunFast --floor
tools/run.py anim-review clips --sources meshy,meshyw --out D:/prime-art-raw/review/stage1/25
tools/run.py anim-review clips --body men --clips meshy_own:Walking,...,ual:Walk_Loop,... --out D:/prime-art-raw/review/stage1/25
tools/run.py anim-review clips --body women --clips meshyw_own:Walking,...,ual:Walk_Loop,... --out D:/prime-art-raw/review/stage1/25
tools/run.py anim-review pairs --sources meshy,meshyw --out D:/prime-art-raw/review/stage1/25
tools/run.py anim-review feet --only meshy_feet_men,meshy_feet_women,meshy_toes --out D:/prime-art-raw/review/stage1/25
tools/run.py anim-review table --out D:/prime-art-raw/review/stage1/25
```

The own-rig runs list every clip of the rig (men: `meshy_own:` Walking, Running, RunFast, Walk_Backward,
Idle_Step_Turn_Left, Hit_Reaction, Knock_Down, Prone_Reach_Help, Crawl_and_Look_Back, Crawl_Prompt,
Carry_Heavy_Object_Walk, Shrug, Finger_Wag_No; women: `meshyw_own:` Walking, Running, RunFast, Walking_Woman) and the
best clips of the needs (`ual:Walk_Loop`, `ual:Jog_Fwd_Loop`, `ual:Sprint_Loop`, `pack:Run_Back`, `ual:Idle_Loop`,
`ual2:Hit_Knockback`, `ual:Hit_Chest`, `ual:Death01`, `ual2:LayToIdle`, `ual2:Walk_Carry_Loop`, `ual2:Yes`,
`ual2:Idle_No_Loop`). The measures of art #25's first run (UAL with the toe bones) are in the same folder's
`feet/<body>/ual_locomotion.json`.
