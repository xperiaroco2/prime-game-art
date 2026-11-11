# The first-person hands: handoff to the game (xperiaroco2/prime-game#1587)

Concept A, "the hand as on the character" (the engineer's pick, 2026-11-10): the alien's own forearms and hands at
true size, the striped sleeve, posed in the camera's space. Built by `tools/blender/fp_hands_run.py --asset
assets/body/fp_hands` from `tools/blender/fp_hands.toml` (art#136; `docs/animations.md`, "The first-person hands").
Not approved yet: the look is shown at the next review.

## Files
- `export/fp_hands.glb`: one skinned scene, 1.7 MB.
  - `FPRig` (Skeleton3D after import): root bone `View` at the eye; per side `Shoulder`, `UpperArm`, `LowerArm`,
    `Hand` and the finger bones under their character names (`RightHand`, `LeftIndexProximal`, ...); `Crystal`.
  - `FPArms`: the skin of both forearms and hands (6,898 triangles), one morph target `fist`.
  - `FPSleeves`: the striped sleeves from the shoulder joints to the cuffs (2,028 triangles).
  - `CrystalSocket`: a node on the `Crystal` bone; Godot imports it as a `BoneAttachment3D` with the `CrystalSocket`
    child. The energy crystal's origin (its tip) goes there with no offset.
- `source/fp_hands.blend`: the build, for edits.

## Scale and placement
- Metres, true size: the arms keep the character's lengths (upper arm 24.9 cm, forearm 22.1 cm, the hand 21 cm to the
  fingertips).
- The GLB's root is the eye: add the scene as a child of the player's `Camera3D` with an identity transform. Its axes
  are the camera's (x right, y up, -z forward). The shots used the game's lens (75 degrees vertical) at 16:9.
- Every live avatar part goes on `PhotoLayers.LIVE_AVATAR` (the game's rule for the hands), so put the hands' meshes
  and the held crystal there too.

## Clips (the AnimationPlayer's names in Godot)
| Clip | Length | Loop | What |
|---|---|---|---|
| `Idle` | 3.0 s | yes | the right hand low in the lower right corner, breathing |
| `Run` | 0.917 s | yes | the run's bob and swing, two steps a loop (the character's Jog cycle) |
| `Punch` | 0.5 s | no | a right jab; contact at **0.15 s**; starts and ends in `Idle`'s pose |
| `Crystal_Idle` | 3.0 s | yes | the crystal held with both hands, low in the middle |
| `Crystal_Run` | 0.917 s | yes | the same, with the run's bob and swing |
| `Crystal_Hit` | 0.5 s | no | a two-handed diagonal swing, cap first; contact at **0.18 s**; starts and ends in `Crystal_Idle`'s pose |

- The hits last 0.5 s, the GDD's rate (one swing each 0.5 s), so a held button can chain them.
- The left arm rests below the frame in the clips without the crystal.
- The `fist` morph is keyed in every clip (1 through the punch, 0 elsewhere); the importer plays it with the clip.
- The run's speed: the clip is one character Jog cycle; scale its speed by the player's speed if the steps should match.

## What the game side builds (not done here)
- Instance `fp_hands.glb` under the camera; switch clips by state (idle or run, crystal held or not), blend the
  switches (about 0.15 s) and play the hits on the left mouse button.
- The held crystal: instance the energy crystal's package under `CrystalSocket` with its `crystal.gd` look; hide it
  when no crystal is held.
- The skin's colour is the axolotl's body paint baked into its texture; a player's own colour pick is not applied yet.
- Open look questions (the coordinator's review): the crystal's own light on the sleeves, the punch's arm, the sway's
  size; see the PR.
