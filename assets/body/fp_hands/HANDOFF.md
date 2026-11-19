# The first-person hands: handoff to the game (xperiaroco2/prime-game#1587)

Concept A, "the hand as on the character" (the engineer's pick, 2026-11-10): the alien's own forearms and hands at
true size, the striped sleeve. He rejected the first build (2026-11-11: a broken, twisted wrist, the crystal burning
the hands white, a strange hold) and picked the way games draw first-person hands: a viewmodel on its own camera,
each key pose matched to an approved target frame. Built by `tools/blender/fp_hands_run.py --tag n1 --asset
assets/body/fp_hands` (2026-11-19, on the detailed hand m28) from `tools/blender/fp_hands.toml` and the fitted poses `tools/blender/fp_hands_fit.json`
(art#136; `docs/animations.md`, "The first-person hands"). Not approved yet: the look is shown at the next review.

## Files
- `export/fp_hands.glb`: one skinned scene, 7.1 MB.
  - `FPRig` (Skeleton3D after import): root bone `View` at the eye; per side `Shoulder`, `UpperArm`, `LowerArm`,
    `Hand` and the finger bones under their character names (`RightHand`, `LeftIndexProximal`, ...); `Crystal`.
  - `FPArms`: the skin of both forearms and hands, the detailed hand m28 (95,160 triangles for the two), one morph
    target `fist`, one material (the colour slot below). No sleeves yet: the bare arm first; each outfit's sleeve is
    laid on later.
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
    `light_cull_mask`), and add one fill light on that layer alone (its values under "The colour slot and the
    light" below);
  - the crystal's own light (`crystal.gd`'s `omni`) stays off the hands' layer, so its glow lights the room and
    never burns the hands white (the engineer's complaint of 2026-11-11).
- `PhotoLayers.LIVE_AVATAR`: if the game's photo rule needs the hands on that layer as well, add it next to the
  hands' own layer.

## The colour slot and the light
- The skin (`FPArms`' one material) has a **neutral grey** base colour texture (the palm and fingertips lighter, the
  knuckles a touch deeper, the creases and occlusion darker; its brightest texel 1.0, the back of the hand 0.72 of
  the colour in linear light, 0.86 in sRGB) and a **white** base colour factor. Colour it as the player is coloured:
  `material.albedo_color = original_albedo_color * body_colour` (prime-game's `CharacterRig.set_tint`; the original
  is white, so `albedo_color = body_colour`). Use a duplicate of the material per player.
- **The default body colour** (when no colour is picked): **sRGB 0.40 0.86 0.80** (`fp_hands.toml [look] body_srgb`): `albedo_color = Color(0.40, 0.86, 0.80)`.
- **The hands' fill light** (a `DirectionalLight3D` under the hands' camera, on the hands' layer alone, no shadow):
  energy **0.3**, colour **(1.0, 0.93, 0.85)** (warm white), `rotation_degrees` **(-50, -90, 0)** under the
  hands' camera (from the right side, a little above).
- **The hands' camera's environment**: a duplicate of the level's `Environment` with the background clear and
  transparent, SSR, SSAO, SSIL, SDFGI and fog off, and `ambient_light_energy` at **0.8** of the level's.
- Picked by numbers from a grid of 28 looks against concept A's punch frame (the hand's teal pixels): the fist reads
  hue 180, saturation 0.47, value p10/p50/p90 0.38/0.56/0.60 (the concept: 181, 0.43, 0.35/0.55/0.61; the old baked
  teal: 187, 0.42, 0.46/0.63/0.67). The look waits for the engineer's eye.

## Clips (the AnimationPlayer's names in Godot)
| Clip | Length | Loop | What |
|---|---|---|---|
| `Idle` | 3.0 s | yes | the right hand low in the lower right corner, breathing (the target frame `idle`) |
| `Run` | 0.917 s | yes | the run's bob and swing, two steps a loop (the character's Jog cycle); the hand open and relaxed as in `Idle` (no fist) |
| `Punch` | 0.5 s | no | a straight right punch; contact at **0.15 s** (the target frame `punch`); starts and ends in `Idle`'s pose |
| `Crystal_Idle` | 3.0 s | yes | the crystal carried with both hands from its sides, like a box (the engineer's pick of 2026-11-12): both palms on its flanks at one height under the skirt, the fingers round its back (see "The hold") |
| `Crystal_Run` | 0.917 s | yes | the same, with the run's bob and swing |
| `Crystal_Hit` | 0.5 s | no | a two-handed diagonal swing, the cap leading: drawn down to the lower left (0.09 s), across and up to the contact at **0.18 s** with the cap and loop at the upper right (74 % across, 46 % down; the frame's middle clear), a short follow-through and back; starts and ends in `Crystal_Idle`'s pose (since run n5) |

- The hits last 0.5 s, the GDD's rate (one swing each 0.5 s), so a held button can chain them.
- The left arm rests below the frame in the clips without the crystal.
- The `fist` morph has a track in every clip: in `Punch` it rises to 1 by 0.06 s, holds to 0.32 s and is 0 again
  at 0.5 s; every other clip holds 0. Godot plays it with the clip.
- The run's speed: the clip is one character Jog cycle; scale its speed by the player's speed if the steps should match.

## The hold (run n4, 2026-11-19)
- The hold the engineer approved on the detailed hand m27 (run s3), unchanged on m28: both hands on the crystal's
  flanks at one height, the fingers round its back, the cap and its loop in view above the hands.
- Tried and reverted (run n2): seating the palm closer and turning the thumb to the crystal's front read better by
  the numbers, but the thumb's turn went to its range's edge and the ring and little fingers to their curl limit, and
  from the eye the fingers twisted into a knot (the engineer, 2026-11-19: the hold looked better before).
- Still open, waiting for the engineer: the palm stands a little off the faceted flank.

## What the game side builds (not done here)
- Instance `fp_hands.glb` under the camera; switch clips by state (idle or run, crystal held or not), blend the
  switches (about 0.15 s) and play the hits on the left mouse button.
- The held crystal: instance the energy crystal's package under `CrystalSocket` with its `crystal.gd` look; hide it
  when no crystal is held.
- The look waits for the engineer's yes at the next review; see the PR.
