# Meshy's animations on our characters, and a toe bone for the Ultimate Modular feet (art #25, 2026-10-03)

The engineer, after the tests of wave 1: "the feet are broken again". The Ultimate Modular rig has no toe bone, so each
shoe is one rigid piece: at push-off a retargeted clip tips the whole shoe onto its toe (UAL Walk_Loop, side view in
`D:/prime-art-raw/review/stage1/20/`), and the pack's own feet, placed apart from the legs (children of `Root`), lift
and turn sideways in its Walk (m1_rex in art #18's Godot frames). The engineer decided to give the rig a toe bone and to
try Meshy's animations (its library and its text to motion) on our characters for about 60 credits (chat with the art
manager, 2026-10-03, [art #16](https://github.com/xperiaroco2/prime-game-art/issues/16#issuecomment-5971404896)).

Pictures and clips are outside git in `D:/prime-art-raw/review/stage1/25/` (`feet/`, `strips/`, `clips/`,
`metrics/`, `rig_inputs/`). The method is in [../animations.md](../animations.md) (the retarget, the review, the feet
step) and [../meshy.md](../meshy.md) (the client, batch 4).

## Summary

- **Toe bones: done.** Every assembled character, and the review's donors, now have `Toe.L` and `Toe.R` (children of
  the feet, at the ball of each shoe; 64 bones in all). UAL's toes (`ball_l`, `ball_r`) drive them. At push-off the
  shoe now bends at the ball instead of standing on its tip: with the heel lifted 20 degrees and the tip on the
  floor, the front of a rigid shoe points 12 to 19 degrees into the floor, a shoe with toe bones -2 to -5 (level);
  the heel rises 19 to 48 degrees before the front leaves level, against 10 to 12 for a rigid shoe (table below). The
  pack's own 24 actions key no toe and play exactly as before (every vertex of the pack's Walk within 0.01 mm); the
  export and the Godot 4.7.2 check pass with 64 bones.
- **Meshy: not run in this session.** The client, the batch (59 of the 60 credits) and the rig inputs are ready and
  checked (`meshy estimate`: approval complete, inputs ready); the balance is 374. The batch needs one command,
  `tools/run.py meshy run 2026-10-b4-animations man-rig` and then without the item, once the engineer confirms the
  spend directly (see "What is left"). Meshy's skeleton, both comparisons and the per-need choice between Meshy and
  UAL therefore wait for that run; the recommendation below says what is decided without it.

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

## Meshy: the plan (batch 4, ready, not run)

`batches/2026-10-b4-animations.toml`, estimated with `tools/run.py meshy estimate 2026-10-b4-animations`:

| Item | What | Credits |
|---|---|---|
| `man-rig` | m1_rex (men, 1.97 m) as a static textured GLB facing +Z (`meshy rig-input`: 6458 triangles, 462 KB, its 14 flat colours baked into a 32 px palette PNG, also sent as `texture_image_url`); returns Meshy's basic walking and running too | 5 |
| `woman-rig` | w1_ivy (women, 1.85 m), the same (8318 triangles, 601 KB) | 5 |
| `man-library` | 16 Run Fast (sprint, the feet), 544 Walk Backward, 577 Idle Step Turn Left, 178 Hit Reaction, 187 Knock Down, 340 Crawl and Look Back, 372 Prone Reach Help, 551 Carry Heavy Object Walk, 317 Shrug, 409 Finger Wag No | 30 |
| `woman-library` | 1 Walking Woman, 16 Run Fast | 6 |
| `crawl-motion` | text to motion, prime, 4 s: a forward crawl on hands and knees while hurt, a loopable cycle (no game or character named) | 10 |
| `man-crawl` | the crawl animated on the man's rig (`motion_task_id`) | 3 |
| | **total** (cap 60) | **59** |

The library listing (`meshy library`, free, 2026-10-03) holds 678 actions (BodyMovements 158, DailyActions 157,
Dancing 33, Fighting 154, WalkAndRun 176; the docs page lists 591, the rest repeat earlier names under new ids), saved
to `D:/prime-art-raw/2026-10-b4-animations/animation-library.json`. It has no side-step strafe (only strafes with a gun
or a bow, and backward diagonal runs), a backward walk, two crawls (one looking back, one backwards), turns in place,
knock-downs and get-ups, a two-handed heavy carry, and many gestures (shrug, finger wag, cheers, waves, thumbs-up
seated). The picks cover the feet (the sprint; the rig's free walk and run) and the gaps of art #20 and #24.

The rig inputs were looked at (`D:/prime-art-raw/review/stage1/25/rig_inputs/m1_rex/sheet.png`: T-pose, the face to
the front, colours from the texture).

## Meshy's skeleton

Not known yet: the docs name no bones, no bone count and nothing about fingers or toes (read 2026-10-03: the rigging,
animation and text-to-motion pages, and the web guide, which calls the result "Mixamo-compatible"), and no rig has been
made. The contract's `contract/bone_maps/meshy.toml` (art #4) holds the guess, unconfirmed: Mixamo names without a
prefix (`Hips`, `Spine`, `Spine01`, `Spine02`, `Neck`, `Head`, `LeftShoulder`, `LeftArm`, `LeftForeArm`, `LeftHand`,
`LeftHandThumb1..3` and four fingers `1..3`, `LeftUpLeg`, `LeftLeg`, `LeftFoot`, `LeftToeBase`, and the right side),
which would mean five-finger hands with three bones each and one toe per foot. After `man-rig` runs,
`tools/run.py check --map meshy <rigged GLB>` lists every bone the guess does not map as extra and `render` counts the
bones; the report then gives the names, the count, the fingers and the toes, fixes `meshy.toml` (a shared contract
file: through the manager) and writes `tools/blender/retarget_maps/meshy_um.toml` and `meshy_um_rigid.toml` from it.

## What is left (after the run)

1. `tools/run.py meshy run 2026-10-b4-animations man-rig`, look at the rig (`render` of its GLB), then the rest:
   `tools/run.py meshy run 2026-10-b4-animations`; the balance before and after (`meshy balance`); `raw-backup` of the
   chosen originals.
2. The skeleton report (above) and the bone map `meshy_um.toml` (the same rest compensation and hips scaling: the map
   names Meshy's hips, hip joints and feet; a Meshy toe drives our `Toe`; finger phalanges by anatomy, as for UAL).
3. Comparison (b): add `[libraries.meshy]` to `tools/blender/anim_review.toml` (`file` = the man's library GLB, `rm`
   the same, `map = "meshy_um.toml"`, `rigid_map = "meshy_um_rigid.toml"`), a `[[feet]]` row with the Meshy walk, run
   and sprint, and pairs of each Meshy clip with the best UAL1, UAL2 or pack clip for the same need; then `anim-review
   clips`, `pairs` and `feet` into `D:/prime-art-raw/review/stage1/25/`.
4. Comparison (a), Meshy's own animated GLB (its rig and weights on our mesh): `tools/run.py render <animation.glb>
   --anim <action> --frames 12` for the frames, beside (b).

## Licences

- **The rig inputs** are our own work from CC0 parts (Quaternius Ultimate Modular, our face kit).
- **Meshy outputs on the Pro plan** (rigs, animated GLBs, text-to-motion clips) are owned by us (Meshy Terms of Use
  3.2, updated 2026-09-19); Meshy keeps a licence to provide the service. Text-to-motion clips are `ai_generated =
  true`.
- **The library motions:** Meshy does not disclose where its 678 library clips come from (motion capture, purchased
  libraries or generation). Ownership of the output under 3.2 says we own what the service produced for us, but not
  that the underlying motion is free of third-party rights. So for the art repo's rules: library clips stay **private
  raw files** (`D:/prime-art-raw/2026-10-b4-animations/`, never in git), `public_repo_ok = false` in any manifest
  that uses one, and `ai_generated` recorded as unknown, until Meshy states their provenance. The public game repo
  takes none of them in that state; a clip we retarget and then key by hand is still derived from it.

## Recommendation per game need

From art #20's and #24's needs table; "Meshy" needs the run.

| Need | Now | After the Meshy run |
|---|---|---|
| Walk 4.5 m/s, sprint 7.0 m/s | UAL Walk_Loop/Jog blend and Sprint_Loop, **with the toe bones** (the feet fix is ours, not the source's) | compare Meshy's walk, run and Run Fast on the feet measures; keep UAL unless Meshy's feet are clearly better (UAL is CC0 and public-safe) |
| Moving sideways and backwards | Run_Back (pack) | Walk Backward (Meshy) for backwards, private only; a side-step strafe is in neither (UAL1 Pro or our own) |
| Turning in place | gap | Idle Step Turn Left (Meshy), mirrored for the right |
| Being pushed | Hit_Chest (UAL) | Hit Reaction (Meshy) |
| Knocked down, downed, crawling | Death01, Hit_Knockback, LayToIdle (UAL, UAL2); crawl: gap | Knock Down, Prone Reach Help, Crawl and Look Back (Meshy) and the text-to-motion crawl |
| Carry the package | UAL2 Walk_Carry_Loop's upper body | Carry Heavy Object Walk (Meshy) against it |
| Gestures, emotes | pack Wave, UAL Dance_Loop, UAL2 Yes and folded arms | Shrug, Finger Wag No (Meshy): the fingers are the test |
| Everything else (idle, jump, use, talk, knife, hit) | as art #20 and #24 recommend | unchanged |

**The UAL1 Pro money question still stands** for the side-step strafes (no Meshy library clip is a plain strafe) and
for a clean, public-safe crawl; Meshy's library is private-only while its provenance is undisclosed, so for anything
that may go public UAL1 Pro (CC0, $9.99) remains the cheaper safe source for crawling and 8-direction locomotion.
