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

## The free hand at rest (run p1, 2026-11-19; not in this asset yet)
- The engineer's reference for `Idle` and `Run` (specs/fp_hand_dims.toml `[reference.card] rest`): long, nearly
  straight fingers with a soft curl, a little spread, the thumb swung clearly out from the index and the lowest digit.
- Run p1 starts the grip from Quaternius UAL1's Idle (CC0) and fits it by eye beside the reference
  (`fp_hands.toml [grips.rest]`), on the hand m29: the thumb's weights eased (the crease at its joints gone) and its
  web to the palm rounded (the dimple softer in Blender, still a dark notch in Godot's close-up). Open on m29: the
  hold's thumb fit went to its search's edge (curl x2.5, n6 x0.6) and the thumbs stand out from the crystal's flanks
  in Crystal_Idle; until that is fixed the asset's files here stay run n6's, and the engineer picks the hand's place
  in the frame (the current lower right, or lower centre nearer the reference) on p1's page.

## Round 2 (run p2, 2026-11-19; not in this asset yet)
- The golden-frame check (`fp_hands.toml [golden]`, `tools/blender/fp_golden.py`): every run shoots eye stills
  (`frames/stills/`: the hold, the punch's contact at 0.15 s, idle, run) and diffs them against run n6's, shot again
  from n6's GLB (`<raw>/2026-11-11-fp-hands/golden/n6/`, SHA-256 in the toml), inside each frame's hand box; the hold
  and the punch's contact fail the run past 1 % of the box changed by more than 0.1. n6's own frames against the
  re-shoot: 0.0. p1's hold: 6.1 % (mean 6.9 of 255), a fail: the hold's thumbs moved.
- The hold restored: `[poses.crystal] thumb_pin` keeps n6's thumb fit (turn [-15, 10], curl x0.6); m29's eased
  weights had moved the fit's own search to [75, 30] and x2.5.
- The dark notch in the thumb's web was the normal map's bake: the cage stood 2 mm out with 5 mm rays, and in the
  narrow crotch its points lay inside the index, whose surface the rays hit (gone with the normal map off in Godot,
  not with back faces drawn: `frames/closeup_web*.png`). m30 bakes 1 mm out with 2 mm rays; `web_mm` back to 5.
- The free hand's place and turn from the reference: `[poses.idle]` (the back turned to the eye as if looking 50
  degrees down, the fingers toward the upper left), `[grips.rest]` a curl cascade 5/10/15. The corner place stays in
  the toml as a comment for the engineer's choice.

## Four digits (run f1 on the hand m40, 2026-11-20; not in this asset yet)
- The engineer's final word of 2026-11-20: three fingers and a thumb. `specs/fp_hand_dims.toml` m40: index, middle,
  ring 37 / 38 / 35 mm wide (m30: 47.5 / 45 / 39), the middle the longest (to u 208), index and ring 97 mm knuckle
  to tip. Measured: the palm within the spec at every station (u 88: v_max 49.6 against 49, m30 54.2; u 98: 49.3
  against 47.5), the fingers within 1 mm; off spec as before, the fist's thumb at u 138.6 (spec 157; m30 142.6).
  The model: `<raw>/2026-11-18-fp-hand-model/m40/`.
- Ported from the five-digit branch: the thumb's phalanges 5 mm out (`apart_out_mm`), its proximal phalanx's waist
  (2 mm) and wrinkles over its last joint, each crease carved on its own digit only and faded in round it, the
  wrist's line shallower and wider; `fp_hands_run.py --rest-grid` (with a cropped sheet, `grid_crop.png`); the
  back and palm close-ups without the normal map; `[poses.idle] keep = true`.
- Close-ups m30 against m40 (runs f1m30 and f1, `frames/closeup_*.png`): the fingers apart with gaps, the web's
  notch gone, the palm's saw-tooth creases gone. Still there: a crumpled patch on the palm side at the index's root.
- The rest pose (grids `<raw>/2026-11-11-fp-hands/f1r1`-`f1r3`): past about 0.42 m the arm does not reach the low
  centre (0.5 m: 62 mm short) and the wrist's bend limit turns the hand upright; tip 40 bunches the fingers; the
  thumb shows only rolled and swung away from the palm. Picked f1r3 J, the lower right corner; the low centre
  (f1r3 F) stays in the toml as a comment with its own thumb. From the eye the corner hand is about 13 % of the
  frame's width against the reference's 25 %.
- Reach at the pick (the corner): Punch 30.5 mm out of reach, Run 0.0 (the low centre on m30: Punch 45.6, Run 7.0).
- The golden check fails where the hand changed, as expected (not re-taken): hold 5.3 % of its box (mean 5.6),
  punch_hit 12.8 % (mean 8.4), against 1 %. The hold's fit still ends on its search's edge (palm roll 45).
- Next: refit the punch and the hold to m40; the engineer picks the place (page `tools/out/hand-four-f1/`).

## The rest hand laid down (run f2 on m40, 2026-11-20; not in this asset yet)
- f1's corner hand stood upright and read as a "stop" palm or a wave. Grids f2r1-f2r4 (`<raw>/2026-11-11-fp-hands/`,
  the reference first) with two new cell keys in `fp_hands_run.py --rest-grid`: `bend` (the viewmodel's forearm in
  line with the hand, no reach limit) and `pitch` (the still looking down, the hands in the body's space or carried by
  the camera; review shots only, `shots.gd`).
- Found: leaning the fingers away from the eye (lean 40-60) foreshortens them into a fist; at 165-175 degrees they
  bunch into a pinch; the spread turns the fingers toward the index, so a hand set at 150 degrees shows its fingers at
  about 110 in the picture. The thumb shows below the palm only turned the other way ([20, 5, 10] / [30, -30]).
- Picked f2r4 F (`[poses.idle]`, `[grips.rest]`): low, a little right of the middle (place [56, 94, 0.48]), the back
  to the eye, bend [0, 0], spread 50. From the eye (`frames/stills/idle.png`, `run.png`): no longer a stop palm, the
  thumb out below with a gap, but the fingers rise about 70 degrees off horizontal and stand one behind the other
  (the ring finger mostly hidden); the long forearm lies across the lower right.
- Looking down 30 degrees (f2r4 I-K): with the hands in the body's space the camera sees the back from above, nearest
  the reference, but the hand rises into the middle of the frame and the forearm's cut end shows (the viewmodel has no
  upper arm); with the hands on the camera the hand is the level one over the floor.
- Reach: Punch 0.0 mm, Run 0.0 (f1: Punch 30.5); with `bend` the arm is not reach-checked at those keys. Golden (not
  re-taken): hold 5.3 % of its box (mean 5.6), punch_hit 11.7 % (mean 7.7), against 1 %. The hold's fit still ends on
  its search's edges (palm roll 45, Little curl 2.5).
- Page `tools/out/hand-four-f2/` (unpublished). Next: lower the fingers' rise (the spread's turn compensated, or the
  fingers' own side angle) and fan them; refit the punch and the hold to m40.

## Only the right hand at rest, the crystal raised (runs f5 and f6 on m40, 2026-11-20; not in this asset yet)
- f5 (the engineer: one hand, never two; first-person hands static in the frame as in flat shooters, VR games no
  reference): the idle pose places the right hand alone (rest grid f4r2 D); the left stays parked below the frame.
- f6 (the M8 review's answer 1, prime-game#1095: keep the m27 grip, raise the crystal in the frame): `[poses.crystal]`
  set from the eye, the cap point at 54 % down (was 64.5 %), the same lean and distance (grid
  `<raw>/2026-11-11-fp-hands/g1raise`: d64 is the old hold exactly, d58, d54, d50). The palms 87 % down (were 99 %),
  both seated (2.4 mm deepest), in reach; the hold's fit is m27's (roll 45, thumb [-15, 10] x0.6, curls
  0.95/1.1/1.1).
- The hold's fit skips a digit the model does not have (m40's `Little` carries no skin): it no longer curls to its
  search's edge and warns. The roll 45 on its edge stays, as on the approved n4.
- The fist (grid `<raw>/2026-11-18-fp-hand-model/g40a`: the thumb's turn [-20..-30, 50..60], its curl, more
  untangle and smoothing rounds): no variant measurably better than m40's own (about 280 crumpled vertices smoothed
  in each; the fist 152 x 139 x 126 mm against 156 x 140 x 125). The fist's thumb reaches u 138.5 against the spec's
  157 whatever its pose: the open thumb is on spec (tip u 134.6 against 135), so a longer reach needs a longer thumb,
  a change to the look that waits for the engineer.
- Golden (not re-taken, waits for the engineer's yes): hold 65 % of its box changed (the crystal raised), punch_hit
  3.5 % (the m40 hand). Every other check of f6 passes; glTF-Validator 0 errors.

## What the game side builds (not done here)
- Instance `fp_hands.glb` under the camera; switch clips by state (idle or run, crystal held or not), blend the
  switches (about 0.15 s) and play the hits on the left mouse button.
- The held crystal: instance the energy crystal's package under `CrystalSocket` with its `crystal.gd` look; hide it
  when no crystal is held.
- The look waits for the engineer's yes at the next review; see the PR.
