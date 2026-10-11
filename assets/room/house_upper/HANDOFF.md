# House package P4, the second floor: the game-side handoff (art #129, prime-game #523)

For the game's own import task, after P1 (the kit) and P2 (the ground floor: the main stairs and the terrace the
balcony stairs land beside). Nothing here is copied before the approval fields of this manifest and of
`assets/prop/house_props/manifest.toml` are set (the engineer's look approval on the art PR).

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| P1 (`assets/kit/house_kit/HANDOFF.md`) | `assets/environment/house_kit/` (P4's rooms use 16 of its pieces: the boards and lino floors, the storey walls, the balcony's railings and the external stairs' flight and landing) |
| `assets/prop/house_props/export/library/*.glb` (52 of them), `task/*.glb` (3), as `package.json` lists | `assets/environment/house_props/<file>.glb` (flat) |
| `assets/room/house_upper/export/<room>.tscn` (7) | the content of `levels/house/rooms/<room>.tscn` (G3 below) |

`package.json` beside this file lists the package's 81 game paths with their SHA-256 (the copies must hash the same),
its rooms (game node, level, kit and prop counts) and the questions. The 7 rooms: `bedroom`, `kids_room`, `landing`,
`study`, `bathroom`, `guest_room`, `balcony` (with the external stairs down to the yard). Each scene keeps the game
room's root name, origin, `metadata/size_m`, `Name` label, `Doors`, `Stations` and `Markers`, and adds `Shell` (kit
instances, walkable ones with `metadata/surface`), `Dressing` and `Fixtures` (lamps). Then the game's `check` (commit
the `.import` files it writes), `credits`, the import check (11.3) locally with LFS content, `load`, `playcheck`,
`perf` and `shot`.

## Names in the flat props folder
One prop has a namesake in the library: `toy_chest`. As in P3, the export resolves a prop id through `house.toml`'s
`prop_dirs` in order (the task props first), so the package ships `task/toy_chest.glb` under that name and never the
library's; one game file `assets/environment/house_props/<id>.glb` per id, the same bytes in every package.

## Credits
As P2: the drafts `D:/prime-art-raw/house/export/credits/house_kit.md` and `house_props.md`; own work, the props from
CC0 packs named per file in the props manifest, `ai_generated = false`, `public_repo_ok = true`.

## The balcony loop (Q6, answered)
The engineer, 2026-10-11: the loop stays **as built**. The design doc's loop (dining room, main stairs, landing,
balcony, external stairs, terrace, dining room) is 46 m and 10.2 s there; as built it is **62.6 m in plan, about
13.9 s at 4.5 m/s** (the main stairs' U-turn, the straight balcony flight landing north on the yard). The game may tune
it later (a U-turn flight would give about 12.1 to 12.5 s, docs/house.md "The second floor").

## Questions still open on prime-game #523
- G3 and G11 as in P2.
- G1/G2 (art task A4): `landing` Door6 and `study` Door1 are among the known differences to the game's greybox
  (`mapping.md`); the game's spawn zone marker Zone03 (the landing) is not carried by the art room yet.
- Lights: every fixture is a real-time `OmniLight3D` without shadows (20 in this package); the bake comes later
  (#83, G6).

## Art defaults (the game may change any)
- Colliders are the GLBs' own `-convcolonly` shapes (`StaticBody3D`, layer 1); picture frames and rugs have none.
- Footsteps: the boards `wood`, the bathroom's lino and the balcony's external stairs `concrete`, the floor under the
  rugs `carpet`.
- The art's package check (`house --export --package 4`) is green: 7 scenes load with their root and `size_m`, the
  6/6 capsule walks inside the package arrive (each room's door to the landing), of the 2040 rays down 1655 hit `wood`,
  160 `carpet`, 136 `concrete` and 1 the bean bag in `kids_room` (a prop, no surface: the game's default). The main
  stairs, the balcony stairs and the balcony loop leave the package (P2's rooms and the yard): the art's whole-house
  walk (`house --walk`, 2026-10-11) walks them, all arriving: the main stairs up 3.85 s and down 3.2 s, the balcony
  stairs up 3.17 s and down 2.58 s, the loop 13.85 s (21/21 points). The hatch ladder up to the attic is P5's piece
  and has no capsule walk yet (a ladder is not a flight).
