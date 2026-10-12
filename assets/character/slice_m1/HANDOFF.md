# slice_m1: handoff to the game (art #42 part C)

The slice character for M6.2: cast `m1` in the clay look with the clay face kit, the textures baked and embedded,
carrying 25 clips of the MVP animation set on the same skeleton. **Not approved yet**: the game takes it once
manifest.toml's approval fields are set (the engineer approves the look on the review page).

## Known deviations

`godot-check --strict-contract --humanoid --textured` passes every check but these
(the contract v1 body gates):

- `contract_height` fail: 1.986 m to the top (contract v1: 1.7 to 1.8 m)
- `contract_eye_height` warn: eyes at 1.722 m (contract v1: 1.6 +- 0.08 m)

The clay look's head is 1.3 times the pack's, with hair on top, so the body is taller than the contract's 1.70 to
1.80 m and the eyes sit above the camera's 1.6 m. **Open: the engineer decides** (art PR #139, docs/godot.md "Open: the
height"): widen the contract's window for the clay look (a contract change), scale the export, or let the game scale
the body. Do not import before the decision; this section is rewritten with it.

## What to copy where

| From (this folder) | To (prime-game) | Size | LFS |
|---|---|---|---|
| `export/slice_m1.glb` | `assets/characters/slice_m1/slice_m1.glb` | 7.45 MB | yes (one object) |

The path is prime-game's `docs/ARCHITECTURE.md` section 11.1 (`assets/characters/<id>/<id>.glb`, `<id>` the manifest's
`id`); the PR shape is its section 11.2: the GLB through LFS, its `.import` committed, `docs/credits/slice_m1.md`
and `tools/run.sh credits`. `package.json` lists the file with its SHA-256; the credit draft is the manifest's
`credit` (`public_repo_ok = true`, `ai_generated = true`) and the per-clip table below (the Meshy clips are owned
output of the Pro plan, `ai_generated = true`).

**The game's import check.** `tools/assets/asset_contract.json` (section 11.3) still lists `Knockdown`, `Crawl` and
`Getup_Fours`, the slice's provisional list; this GLB leaves them out on purpose (the knockdown is a ragdoll,
prime-game#522 and art #115). The import PR edits the contract's clip list to the clips below that the avatar maps.

One GLB holds the body and the clips: the contract (docs/contract.md, "Animation") wants one shared library on the
contract skeleton, and the slice has one body, so the clips ride with it; the game can save the AnimationPlayer's
library as a `.res` and share it once a second body arrives.

## Import settings (Godot 4.7.2)

- `animation/fps = 30` (the set's rate; at another rate Godot resamples the clips);
- the AnimationPlayer node's `optimizer/enabled = false` (with the optimizer the joints drift up to 17 mm);
- clips named `*_Loop` import looping (LINEAR) without the suffix: the game sees the Godot names below.

## Sizes

- GLB 7.45 MB, 6 parts on one skeleton of 64 bones,
  10 embedded images (4.44 MB), height 1.9864 m;
- in place: no root motion; the game moves the body (the locomotion clips' `speed_m_s` is the ground speed at rate
  1.0: play at speed / speed_m_s).

## Clips

| Godot name | Set name | Loop | Layer | s | Source | Licence | ai_generated | Serves |
|---|---|---|---|---|---|---|---|---|
| `Idle` | `Idle_Loop` | LINEAR | full | 2.533 | `ual:Idle_Loop` | CC0-1.0 | false | Idle, standing; the base under the carry, talk and push layers |
| `Turn_Left` | `Turn_Left` | none | full | 1.2 | `tm:turn-left-90` | owned-paid-output | true | Turn in place, 90 degrees to the left (lower body while the yaw follows the mouse) |
| `Turn_Right` | `Turn_Right` | none | full | 1.2 | `tm:turn-left-90 (from Turn_Left)` | owned-paid-output | true | Turn in place, 90 degrees to the right |
| `Jog_Fwd` | `Jog_Fwd_Loop` | LINEAR | full | 0.7 | `ual:Jog_Fwd_Loop` | CC0-1.0 | false | Move forward at 4.5 m/s (the walk) |
| `Jog_Bwd` | `Jog_Bwd_Loop` | LINEAR | full | 0.7 | `ual:Jog_Fwd_Loop` | CC0-1.0 | false | Move backward at 4.5 m/s; Sprint backward at 7.0 m/s |
| `Strafe_Left` | `Strafe_Left_Loop` | LINEAR | full | 0.5 | `tm:strafe-left` | owned-paid-output | true | Strafe left at 4.5 m/s; Sprint to the left at 7.0 m/s |
| `Strafe_Right` | `Strafe_Right_Loop` | LINEAR | full | 0.5 | `tm:strafe-left (from Strafe_Left_Loop)` | owned-paid-output | true | Strafe right at 4.5 m/s; Sprint to the right at 7.0 m/s |
| `Sprint_Fwd` | `Sprint_Fwd_Loop` | LINEAR | full | 0.8 | `ual:Sprint_Loop` | CC0-1.0 | false | Sprint forward at 7.0 m/s |
| `Crouch_Idle` | `Crouch_Idle_Loop` | LINEAR | full | 2.933 | `ual:Crouch_Idle_Loop` | CC0-1.0 | false | Crouch idle (new: the game has no crouch yet) |
| `Crouch_Fwd` | `Crouch_Fwd_Loop` | LINEAR | full | 2.0 | `ual:Crouch_Fwd_Loop` | CC0-1.0 | false | Crouch walk forward (the game plays it at its own speed / 0.75) |
| `Jump_Start` | `Jump_Start` | none | full | 0.267 | `ual:Jump_Start` | CC0-1.0 | false | Jump: the take-off |
| `Jump_Air` | `Jump_Air_Loop` | LINEAR | full | 2.5 | `ual:Jump_Loop` | CC0-1.0 | false | Jump: airborne, and falling off a ledge |
| `Jump_Land` | `Jump_Land` | none | full | 0.3 | `ual:Jump_Land` | CC0-1.0 | false | Jump: the landing (upper body while moving, full standing) |
| `Shove_Stumble` | `Shove_Stumble` | none | full | 0.7 | `tm:shove-stumble` | owned-paid-output | true | Being pushed: the stumble (the game moves the body) |
| `Push_Upper` | `Push_Upper_Loop` | LINEAR | upper | 2.667 | `ual:Push_Loop` | CC0-1.0 | false | Pushing someone (upper body, low weight) |
| `Knife_Swing` | `Knife_Swing` | none | upper | 0.467 | `pack:Sword_Slash` | CC0-1.0 | false | Use the knife: the swing (upper body) |
| `Carry_Upper` | `Carry_Upper_Loop` | LINEAR | upper | 2.0 | `ual2:Walk_Carry_Loop` | CC0-1.0 | false | Carry the package (upper body over the idle and the locomotion) |
| `Pickup_One` | `Pickup_One` | none | full | 0.9 | `ual2:Farm_Harvest` | CC0-1.0 | false | Pick up a one-handed item from the floor (full standing, upper body moving) |
| `Putdown_One` | `Putdown_One` | none | full | 0.8 | `ual2:Farm_Harvest` | CC0-1.0 | false | Put a one-handed item down in front |
| `Pickup_Package` | `Pickup_Package` | none | full | 1.0 | `tm:package-lift` | owned-paid-output | true | Pick up the package with both hands |
| `Putdown_Package` | `Putdown_Package` | none | full | 1.0 | `tm:package-lift (from Pickup_Package)` | owned-paid-output | true | Put the package down with both hands |
| `Raise_In` | `Raise_In` | none | full | 0.6 | `ual:Fixing_Kneeling` | CC0-1.0 | false | Raise a downed player: kneel down |
| `Raise_Work` | `Raise_Work_Loop` | LINEAR | full | 1.0 | `ual:Fixing_Kneeling` | CC0-1.0 | false | Raise a downed player: the work, looped for the 3 s |
| `Raise_Out` | `Raise_Out` | none | full | 0.6 | `ual:Fixing_Kneeling` | CC0-1.0 | false | Raise a downed player: stand up again |
| `Talk_Upper` | `Talk_Upper_Loop` | LINEAR | upper | 2.933 | `ual:Idle_Talking_Loop` | CC0-1.0 | false | Talking by proximity voice (upper body, low weight) |

Upper-body layers (`layer = upper`: carry, push, talk, knife) export every bone; the game masks them with the bone
filter `Torso` and every bone below it, over the idle or the locomotion (carry idle = Idle + Carry_Upper; carry walk =
Jog_Fwd + Carry_Upper).

## Left off

- `Jog_Bwd_TTM_Loop`: a review candidate the set does not export (export = false)
- `Jog_Bwd_R2_Loop`: a review candidate the set does not export (export = false)
- `Strafe_Left_R2_Loop`: a review candidate the set does not export (export = false)
- `Knockdown`: the knockdown's fall: the ragdoll task (#115) decides falls
- `Crawl_Start`: downed: from lying on the back onto all fours, after the fall (#115)
- `Crawl_Start_R2`: a review candidate the set does not export (export = false)
- `Crawl_Loop`: downed: the crawl after the fall (#115)
- `Crawl_R2_Loop`: a review candidate the set does not export (export = false)
- `Getup_Back`: the get-up after a revive, from lying on the back (#115)
- `Getup_Fours`: the get-up after a revive, from all fours (#115)
