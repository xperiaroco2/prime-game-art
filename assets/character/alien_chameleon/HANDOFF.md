# alien_chameleon: handoff to the game (art #393)

The base alien for M8 (prime-game#1095, the engineer's pick of 2026-11-24: the recovered chameleon, body A): the
chameleon man of art #196 rebuilt from the review page "Alien Bodies A: Step 1" (2026-10-28, recovered after the D:
loss, `docs/research/2026-11-18-d-loss.md`), one skinned mesh on the art contract's humanoid skeleton (59 bones: the
contract's 56 and three crest springs under `Head`) with its locomotion clips, the approved static look (art #196) as
a shader, the ragdoll data and the game's sockets. It replaces slice_m1 as the game's character.

Rest height 1.938 m to the crest, feet at 0.000 m, eyes at 1.702 m, the `Head`
joint at 1.508 m, `Hips` at 0.870 m. Not scaled: art #196 sized body A to its 1.95 m cap.
slice_m1 was scaled so its eyes are at 1.60 m (the game's camera); here the eyes are 10 cm higher and the crest
passes the game's 1.8 m capsule by 14 cm. The game decides: its camera and capsule follow these numbers, or
it scales the model by 0.940 at import (eyes at 1.60 m, the crest at 1.82 m; the sockets and the
ragdoll are in the bones' frames and scale with it).

## Known deviations

- An older build than art #196's last polish (the walk hop, the crouch plant and the hands of art PRs #369, #371,
  #373): those builds were lost with D: and come back after M8.
- The look lacks what was lost with D: the stripes and colour accents (only the base teal is left), the thin parts'
  translucency (crest, gills, lips), the iris ring and the eye controller (the eyes do not look around or blink).
- No `Carry_Upper`, `Pickup_One`, `Putdown_One`, `Pickup_Package` or `Putdown_Package` (the engineer, 2026-11-24:
  skipped in M8). The game plays the base clip instead: the character holds an item with no arm pose of its own.
- The locomotion clips cover their own speeds at rate 1.0 (the table below), not the game's assumed ones.

## What to copy where

| From (this folder) | To (prime-game) | Bytes |
|---|---|---|
| `export/alien_chameleon.glb` | `assets/characters/alien_chameleon/alien_chameleon.glb` | 9,375,908 |
| `export/alien_chameleon.ragdoll.json` | `assets/characters/alien_chameleon/alien_chameleon.ragdoll.json` | 10,547 |
| `export/look/alien_chameleon_look.json` | `assets/characters/alien_chameleon/look/alien_chameleon_look.json` | 479 |
| `export/look/alien_chameleon_mask.png` | `assets/characters/alien_chameleon/look/alien_chameleon_mask.png` | 508,668 |
| `export/look/alien_chameleon_mask.png.import` | `assets/characters/alien_chameleon/look/alien_chameleon_mask.png.import` | 254 |
| `export/look/alien_dress.gd` | `assets/characters/alien_chameleon/look/alien_dress.gd` | 2,886 |
| `export/look/alien_static.gd` | `assets/characters/alien_chameleon/look/alien_static.gd` | 15,727 |
| `export/look/alien_static.gdshader` | `assets/characters/alien_chameleon/look/alien_static.gdshader` | 24,089 |
| `export/look/alien_static_288.gdshader` | `assets/characters/alien_chameleon/look/alien_static_288.gdshader` | 2,540 |

The GLB through LFS with its `.import` committed (prime-game `docs/ARCHITECTURE.md` 11.1 and 11.2); the mask keeps
the shipped `.import` (lossless, mipmaps, never VRAM-compressed: it is data, not colour, docs/godot.md "The colour
slots' masks"); the scripts and shaders as they are (their preloads are relative to `look/`). `package.json` lists
every file with its SHA-256; the credit draft is manifest.toml's `credit` (`public_repo_ok = true`,
`ai_generated = true`).

## Import settings (Godot 4.7.2)

- `animation/fps = 24` (the clips' key rate);
- the AnimationPlayer node's `optimizer/enabled = false`;
- clips named `*_Loop` import looping (LINEAR) without the suffix: the game sees the Godot names below.

## The look

The GLB's own materials are a fallback. The approved look is `look/alien_static.gdshader` on both surfaces:

```gdscript
const AlienDress = preload("res://assets/characters/alien_chameleon/look/alien_dress.gd")
var mats := AlienDress.dress_from(model, "res://assets/characters/alien_chameleon/look/alien_chameleon_look.json")
AlienDress.AlienStatic.set_skin(mats, Color("e98a8c"))  # optional: a player's skin colour (sRGB)
```

`dress_from` swaps the materials of `*_static_skin` (the head) and `*_body_skin` (the body) for ShaderMaterials with
the look file's inputs (the base skin, the mask, the constant detail maps and the shader's levers, exactly as the
review page's shots). Without a pick the skin is the build's own teal.

## Sizes

- GLB 9.38 MB: one mesh of 2 surfaces on one skeleton of 59 bones, 6 embedded images (2048 px at most);
- in place: no root motion; the game moves the body (play a move clip at speed / its `speed_m_s`).

## The game's bones on this skeleton

The game is wired to slice_m1's Ultimate Modular names (prime-game `character_set.gd` `NEEDED_BONES`,
`character_rig.gd` `CARRY_ROOT`); this skeleton has the contract's names, matched by the humanoid profile (the
ragdoll's table: the rig's `Torso` is the `Chest` profile, its `Chest` the `UpperChest`):

| slice_m1 | alien_chameleon |
|---|---|
| `Hips` | `Hips` |
| `Torso` | `Chest` |
| `Chest` | `UpperChest` |
| `Wrist.R` | `RightHand` |

So `NEEDED_BONES` becomes `Hips, Chest, UpperChest, RightHand` and `CARRY_ROOT` `Chest`.

## Sockets

The game's three sockets (`character_rig.gd` `SOCKETS`), each a point in its bone's frame
(`tools/runner/commands/_alien_package.py` `sockets`): Belt and Carry are slice_m1's points (measured in #1050) carried
onto this body by its proportions; Hand is this body's own, in its relaxed idle hand (it has no grip pose: the item
stands in the curled fingers, not in a closed fist):

| Socket | Bone | Point | Fitted carrying | How |
|---|---|---|---|---|
| `Hand` | `RightHand` | `Vector3(-0.0262, 0.1645, 0.0123)` | false | the middle finger's curl centre at the Idle's first frame (the alien has no grip pose) |
| `Belt` | `Hips` | `Vector3(0.1810, 0.0455, -0.0533)` | false | +5.3 cm off the trunk's left side, -5.8 cm against its middle in depth |
| `Carry` | `UpperChest` | `Vector3(0.0147, -0.3519, 0.4038)` | true | +40.8 cm in front of the trunk's front |

There is no `Carry_Upper`, so the Carry socket cannot be fitted on the carry pose: fit it on the Idle (the art's
proof does) or skip the carry layer.

## Clips

The clips the game plays (8 of its 8 base clips are here):

| Godot name | Set name | Loop | s | m/s at rate 1 | Serves |
|---|---|---|---|---|---|
| `Crouch_Fwd` | `Crouch_Fwd_Loop` | LINEAR | 0.875 | 2.07 | crouch, moving (the game assumes 0.75 m/s) |
| `Crouch_Idle` | `Crouch_Idle_Loop` | LINEAR | 2.917 | - | crouch, standing |
| `Idle` | `Idle_Loop` | LINEAR | 7.500 | - | standing; the base under the talk layer |
| `Jog_Bwd` | `Jog_Bwd_Loop` | LINEAR | 0.583 | 2.00 | move backward (the game assumes 4.5 m/s) |
| `Jog_Fwd` | `Jog_Fwd_Loop` | LINEAR | 0.917 | 4.74 | move forward (the game assumes 4.5 m/s at rate 1.0) |
| `Sprint_Fwd` | `Sprint_Fwd_Loop` | LINEAR | 0.667 | 7.00 | sprint forward (the game assumes 7.0 m/s) |
| `Strafe_Left` | `Strafe_Left_Loop` | LINEAR | 0.917 | 3.17 | move left (the game assumes 4.5 m/s) |
| `Strafe_Right` | `Strafe_Right_Loop` | LINEAR | 0.917 | 3.26 | move right (the game assumes 4.5 m/s) |

Beside them (not played by the game yet):

| Godot name | Set name | Loop | s | m/s at rate 1 | Serves |
|---|---|---|---|---|---|
| `Crouch_Run` | `Crouch_Run_Loop` | LINEAR | 0.667 | 2.89 | not played by the game yet |
| `Jog_Bwd_Left` | `Jog_Bwd_Left_Loop` | LINEAR | 0.583 | 2.00 | not played by the game yet |
| `Jog_Bwd_Right` | `Jog_Bwd_Right_Loop` | LINEAR | 0.583 | 2.00 | not played by the game yet |
| `Jog_Fwd_Left` | `Jog_Fwd_Left_Loop` | LINEAR | 0.917 | 3.80 | not played by the game yet |
| `Jog_Fwd_Right` | `Jog_Fwd_Right_Loop` | LINEAR | 0.917 | 3.88 | not played by the game yet |
| `Jump_Air` | `Jump_Air_Loop` | LINEAR | 2.500 | - | not played by the game yet |
| `Jump_Land` | `Jump_Land` | none | 1.250 | - | not played by the game yet |
| `Jump_Start` | `Jump_Start` | none | 1.333 | 1.53 | not played by the game yet |
| `Talk_Upper` | `Talk_Upper_Loop` | LINEAR | 2.917 | - | not played by the game yet |
| `Walk` | `Walk_Loop` | LINEAR | 1.333 | 0.90 | not played by the game yet |

The speeds are measured on the GLB (the median speed of a foot's ball while it stands). The game's `AvatarClips`
assumes 4.5 m/s for the jog, back and strafes, 7.0 for the sprint and 0.75 for the crouch: with these clips the
strafes and the back jog would slide unless the game divides by their own speeds.

Dropped from the source GLB: 19 review variants (`Crouch_Fwd__p2_Loop`, `Crouch_Fwd__ual_Loop`, `Crouch_Run__p2_Loop`, `Crouch_Run__s4b_Loop`, `Jog_Bwd__p2_Loop`, `Jog_Bwd__p3_Loop`, `Jog_Bwd__s4b_Loop`, `Jog_Bwd_Left__p2_Loop`, `Jog_Bwd_Left__p3_Loop`, `Jog_Fwd__arm100_f21_Loop`, `Jog_Fwd__arm100_f22_Loop`, `Jog_Fwd__arm60_f21_Loop`, `Jog_Fwd__arm60_f22_Loop`, `Jog_Fwd__arm75_f21_Loop`, `Jog_Fwd__arm75_f22_Loop`, `Jog_Fwd_Left__p2_Loop`, `Strafe_Left__p2_Loop`, `Strafe_Left__s4b_Loop`, `Strafe_Left__w03_Loop`).

## Ragdoll (art #115)

The knockdown is a ragdoll (prime-game PR #754, KE7); the knockdown, downed and get-up clips are gone. `export/alien_chameleon.ragdoll.json`
holds the ragdoll data: 16 bodies, each on one bone of this GLB's skeleton, with its shape and offset in the
bone's rest frame, its mass (70 kg in all) and its joint to its physical parent (type, limits,
anchor). The game builds the bones from it at spawn with art's reference builder, `godot/ragdoll/builder.gd` (copy it
as it is): `build(skeleton, data)` adds a `PhysicalBoneSimulator3D` with one `PhysicalBone3D` per body;
`start(sim, data, velocity)` at the knockdown starts the simulation from the current (standing) pose with the avatar's
velocity and links the bodies with `Joint3D` nodes; `stop(sim)` at a revive. The parts are on layer 3
(`downed`) with mask 1 (`world`): never players,
another ragdoll or itself. Bones without a body follow their parent (fingers the hand, toes the foot, the shoulders
and upper chest the chest); the sockets' `BoneAttachment3D`s follow the simulated bones with no change. On the contract's skeleton each foot
is its lower leg's child, and every joint links a body to its physical parent.
Proven on Jolt Physics, the game's engine: `tools/run.py ragdoll <glb> --fall`.

| Bone | Profile | Physical parent | Shape | kg | Joint |
|---|---|---|---|---|---|
| `Hips` | Hips | - | box | 9.94 | root |
| `Spine` | Spine | Hips | box | 8.16 | cone |
| `Chest` | Chest | Spine | box | 13.55 | cone |
| `Neck` | Neck | Chest | capsule | 5.67 | cone |
| `LeftUpperArm` | LeftUpperArm | Chest | capsule | 1.96 | cone |
| `LeftLowerArm` | LeftLowerArm | LeftUpperArm | capsule | 1.12 | hinge |
| `LeftHand` | LeftHand | LeftLowerArm | box | 1.00 | cone |
| `LeftUpperLeg` | LeftUpperLeg | Hips | capsule | 7.00 | cone |
| `LeftLowerLeg` | LeftLowerLeg | LeftUpperLeg | capsule | 3.25 | hinge |
| `LeftFoot` | LeftFoot | LeftLowerLeg | box | 2.00 | cone |
| `RightUpperArm` | RightUpperArm | Chest | capsule | 1.96 | cone |
| `RightLowerArm` | RightLowerArm | RightUpperArm | capsule | 1.12 | hinge |
| `RightHand` | RightHand | RightLowerArm | box | 1.00 | cone |
| `RightUpperLeg` | RightUpperLeg | Hips | capsule | 7.00 | cone |
| `RightLowerLeg` | RightLowerLeg | RightUpperLeg | capsule | 3.25 | hinge |
| `RightFoot` | RightFoot | RightLowerLeg | box | 2.00 | cone |
