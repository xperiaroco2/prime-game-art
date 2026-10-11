# House package P2, the shell and the ground floor: the game-side handoff (art #124, prime-game #523)

For the game's own import task, after P1 (the kit). Nothing here is copied before the approval fields of this
manifest and of `assets/prop/house_props/manifest.toml` are set (the engineer's look approval on the art PR).

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| P1 (`assets/kit/house_kit/HANDOFF.md`) | `assets/environment/house_kit/` (P2's rooms use 20 of its pieces) |
| `assets/kit/house_kit/export/kit_set.gdshader`, `kit_set.tres` (#132) | `assets/environment/house_kit/` (beside the kit's textures) |
| `assets/prop/house_props/export/library/*.glb` (66), `task/*.glb` (4) | `assets/environment/house_props/<file>.glb` (flat) |
| `assets/room/house_ground/export/<room>.tscn` (15) | the content of `levels/house/rooms/<room>.tscn` (G3 below) |

`package.json` beside this file lists the package's 107 game paths with their SHA-256 (the copies must hash the
same), its rooms (game node, level, kit and prop counts), the placeholders and the questions. The 15 rooms: `wc`,
`pantry`, `dining_room`, `living_room`, `stairs`, `kitchen`, `hallway`, `terrace`, `yard`, `street`, `path`,
`driveway`, `photo_zone`, `chill_zone`, `outdoor_stairs` (the ground floor without the garage, the greenhouse and the
garden). Each scene keeps the game room's root name, origin, `metadata/size_m`, `Name` label, `Doors`, `Stations`
and `Markers`, and adds `Shell` (kit instances, walkable ones with `metadata/surface`), `Dressing`, `Fixtures`
(lamps) and `Placeholders`. Then the game's `check` (commit the `.import` files it writes), `credits`, the import
check (11.3) locally with LFS content, `load`, `playcheck`, `perf` and `shot`.

## Wall paints and the kit's look (#132)
Every kit instance under `Shell` overrides its meshes' set surfaces (`surface_material_override/<i>`) with
`res://assets/environment/house_kit/kit_set.tres`: the art's `kit_set.gdshader`, the kit's `set_d`, `set_n0`
and `set_n1` textures and the House's wall paints (`layouts/house/house.toml` `[wall_paint]`). Each such mesh
also sets `instance_shader_parameters/plan_at`, its place and turn in the house plan, so the shader paints by
the plan wherever the game puts the House. Nothing to run: copy the two files with the kit and load the scene
(the root's `metadata/wall_paint` stays as a note). Painted here: the kitchen, hallway, living and dining rooms and the stairs, teal #3a6264 (the kit's
own plaster, so the colour stays and the textures are new).

## Credits
The entries are `assets/kit/house_kit/CREDITS.md` and `assets/prop/house_props/CREDITS.md` in this repo (the game's
`docs/credits/<id>.md` format; copy them to `docs/credits/house_kit.md` and `house_props.md`): own work, the props made
from CC0 packs named per file in the props manifest,
`ai_generated = false`, `public_repo_ok = true`. The room scenes are scenes under `levels/`, not assets: no credits
entry unless the game wants one.

## Questions still open on prime-game #523
- G3: the room scenes are written as `levels/house/rooms/<room>.tscn` (11.1 keeps `assets/` data only); the game's
  workflow swaps them into its greybox rooms (`Body`/`Looks` out, `Shell`/`Dressing`/`Fixtures` in).
- G11: the props are a set, one flat folder with a GLB per prop.
- G1/G2 (art task A4): the six known differences to the game's greybox rooms (`mapping.md`: attic, roof, garage
  Door3, landing Door6, study Door1, storage Package07) are all in later packages; P2's rooms match the greybox.
- Lights: every fixture is a real-time `OmniLight3D` without shadows (77 in this package); the bake comes later
  (#83, G6).
- The outdoor rooms (`yard`, `street`, `path`, `driveway`, `photo_zone`, `chill_zone`) carry only their markers and
  lamps here: their ground, fence and props are the plot, package 7.

## Art defaults (the game may change any)
- `door_leaf` has no GLB yet: each door leaf is a sized `Marker3D` under `Placeholders` (never CSG).
- Colliders are the GLBs' own `-convcolonly` shapes (`StaticBody3D`, layer 1); rugs have none, so the floor tiles
  at least half under a rug carry `carpet`.
- The art's package check (`house --export --package 2`) is green: every scene loads with its root and `size_m`,
  10/10 capsule walks arrive, none of the 25536 rays down hits a shell collider without a surface (80 hit nothing).
