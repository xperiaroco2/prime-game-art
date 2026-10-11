# House package P2, the shell and the ground floor: the game-side handoff (art #124, prime-game #523)

For the game's own import task, after P1 (the kit). Nothing here is copied before the approval fields of this
manifest and of `assets/prop/house_props/manifest.toml` are set (the engineer's look approval on the art PR).

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| P1 (`assets/kit/house_kit/HANDOFF.md`) | `assets/environment/house_kit/` (P2's rooms use 20 of its pieces) |
| `assets/prop/house_props/export/library/*.glb` (66), `task/*.glb` (4) | `assets/environment/house_props/<file>.glb` (flat) |
| `assets/room/house_ground/export/<room>.tscn` (15) | the content of `levels/house/rooms/<room>.tscn` (G3 below) |

`package.json` beside this file lists the package's 105 game paths with their SHA-256 (the copies must hash the
same), its rooms (game node, level, kit and prop counts), the placeholders and the questions. The 15 rooms: `wc`,
`pantry`, `dining_room`, `living_room`, `stairs`, `kitchen`, `hallway`, `terrace`, `yard`, `street`, `path`,
`driveway`, `photo_zone`, `chill_zone`, `outdoor_stairs` (the ground floor without the garage, the greenhouse and the
garden). Each scene keeps the game room's root name, origin, `metadata/size_m`, `Name` label, `Doors`, `Stations`
and `Markers`, and adds `Shell` (kit instances, walkable ones with `metadata/surface`), `Dressing`, `Fixtures`
(lamps) and `Placeholders`. Then the game's `check` (commit the `.import` files it writes), `credits`, the import
check (11.3) locally with LFS content, `load`, `playcheck`, `perf` and `shot`.

## Credits
The drafts are `D:/prime-art-raw/house/export/credits/house_kit.md` and `house_props.md` (the game's
`docs/credits/<id>.md` format): own work, the props made from CC0 packs named per file in the props manifest,
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
