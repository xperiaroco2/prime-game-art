# The first-person hands: handoff to the game (xperiaroco2/prime-game#1587)

Concept A, "the hand as on the character" (the engineer's pick, 2026-11-10): the alien's own forearms and hands at
true size, the striped sleeve. He rejected the first build (2026-11-11: a broken, twisted wrist, the crystal burning
the hands white, a strange hold) and picked the way games draw first-person hands: a viewmodel on its own camera,
each key pose matched to an approved target frame. Built by `tools/blender/fp_hands_run.py --asset
assets/body/fp_hands` from `tools/blender/fp_hands.toml` and the fitted poses `tools/blender/fp_hands_fit.json`
(art#136; `docs/animations.md`, "The first-person hands"). Not approved yet: the look is shown at the next review.

## Files
- `export/fp_hands.glb`: one skinned scene, 1.7 MB.
  - `FPRig` (Skeleton3D after import): root bone `View` at the eye; per side `Shoulder`, `UpperArm`, `LowerArm`,
    `Hand` and the finger bones under their character names (`RightHand`, `LeftIndexProximal`, ...); `Crystal`.
  - `FPArms`: the skin of both forearms and hands (6,898 triangles), one morph target `fist`.
  - `FPSleeves`: the striped sleeves from a little above the elbows to the cuffs (no upper arm: a viewmodel).
  - `CrystalSocket`: a node on the `Crystal` bone; Godot imports it as a `BoneAttachment3D` with the `CrystalSocket`
    child. The energy crystal's origin (its tip) goes there with no offset.
- `source/fp_hands.blend`: the build, for edits.

## Scale and placement: a viewmodel
- Metres, true size: the arms keep the character's lengths (upper arm 24.9 cm, forearm 22.1 cm, the hand 21 cm to the
  fingertips).
- The hands are drawn by their own camera, as first-person games draw them (the shots do exactly this,
  `godot/fp_hands/shots.gd`):
  - a second `Camera3D` with a **50 degree** vertical field of view (`[view] fov_deg`), its transform the player
    camera's every frame, in a transparent `SubViewport` the size of the screen laid over it (or the projection
    trick of a viewmodel shader with the same 50 degrees);
  - the GLB's root under that camera with an identity transform; its axes are the camera's (x right, y up, -z
    forward);
  - the hands and the held crystal on their own render layer (the shots use layer 20), which the player camera's
    cull mask leaves out and the hands' camera alone draws; they cast no shadow;
  - a camera draws only the lights on its layers: put the level's lights on the hands' layer too (`layers` and
    `light_cull_mask`), and add one soft fill light on that layer alone (the shots: a directional light, energy
    0.35, warm white, from the upper left);
  - the crystal's own light (`crystal.gd`'s `omni`) stays off the hands' layer, so its glow lights the room and
    never burns the hands white (the engineer's complaint of 2026-11-11).
- `PhotoLayers.LIVE_AVATAR`: if the game's photo rule needs the hands on that layer as well, add it next to the
  hands' own layer.

## Clips (the AnimationPlayer's names in Godot)
| Clip | Length | Loop | What |
|---|---|---|---|
| `Idle` | 3.0 s | yes | the right hand low in the lower right corner, breathing (the target frame `idle`) |
| `Run` | 0.917 s | yes | the run's bob and swing, two steps a loop (the character's Jog cycle) |
| `Punch` | 0.5 s | no | a straight right punch; contact at **0.15 s** (the target frame `punch`); starts and ends in `Idle`'s pose |
| `Crystal_Idle` | 3.0 s | yes | the crystal held with both hands: the right on the cap, the left under its body (the target frame `hold`) |
| `Crystal_Run` | 0.917 s | yes | the same, with the run's bob and swing |
| `Crystal_Hit` | 0.5 s | no | a two-handed swing across, the point leading; contact at **0.18 s** (the target frame `crystal_hit`); starts and ends in `Crystal_Idle`'s pose |

- The hits last 0.5 s, the GDD's rate (one swing each 0.5 s), so a held button can chain them.
- The left arm rests below the frame in the clips without the crystal.
- The `fist` morph has a track in every clip: in `Punch` it rises to 1 by 0.06 s, holds to 0.32 s and is 0 again
  at 0.5 s; every other clip holds 0. Godot plays it with the clip.
- The run's speed: the clip is one character Jog cycle; scale its speed by the player's speed if the steps should match.

## What the game side builds (not done here)
- Instance `fp_hands.glb` under the camera; switch clips by state (idle or run, crystal held or not), blend the
  switches (about 0.15 s) and play the hits on the left mouse button.
- The held crystal: instance the energy crystal's package under `CrystalSocket` with its `crystal.gd` look; hide it
  when no crystal is held.
- The skin's colour is the axolotl's body paint baked into its texture; a player's own colour pick is not applied yet.
- The look waits for the engineer's yes at the next review; see the PR.
