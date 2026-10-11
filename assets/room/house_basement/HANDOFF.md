# House package P3, the basement: the game-side handoff (art #126, prime-game #523)

For the game's own import task, after P1 (the kit) and P2 (the ground floor). Nothing here is copied before the
approval fields of this manifest and of `assets/prop/house_props/manifest.toml` are set (the engineer's look approval
on the art PR).

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| P1 (`assets/kit/house_kit/HANDOFF.md`) | `assets/environment/house_kit/` (P3's rooms use 9 of its pieces) |
| `assets/prop/house_props/export/library/*.glb` (32 of them), `task/*.glb` (15), as `package.json` lists | `assets/environment/house_props/<file>.glb` (flat) |
| `assets/room/house_basement/export/<room>.tscn` (8) | the content of `levels/house/rooms/<room>.tscn` (G3 below) |

`package.json` beside this file lists the package's 67 game paths with their SHA-256 (the copies must hash the same),
its rooms (game node, level, kit and prop counts) and the questions. The 8 rooms: `storage`, `darkroom`, `corridor`,
`boiler_room`, `generator_hall`, `pump_room`, `switch_room`, `passage`. Each scene keeps the game room's root name,
origin, `metadata/size_m`, `Name` label, `Doors`, `Stations` and `Markers`, and adds `Shell` (kit instances, walkable
ones with `metadata/surface`), `Dressing` and `Fixtures` (lamps). Then the game's `check` (commit the `.import` files
it writes), `credits`, the import check (11.3) locally with LFS content, `load`, `playcheck`, `perf` and `shot`.

## Names in the flat props folder
Seven props have a namesake in the library: `boiler`, `cable_drum`, `enlarger`, `pump`, `switchboard`, `tray_table`,
`water_tank`. The export resolves a prop id through `house.toml`'s `prop_dirs` in order (the task props first), so
every package ships the task prop under that name (`task/<id>.glb` here) and never the library's; one game file
`assets/environment/house_props/<id>.glb` per id, the same bytes in every package (`package.json`'s SHA-256).

## Credits
The drafts are `D:/prime-art-raw/house/export/credits/house_kit.md` and `house_props.md` (the game's
`docs/credits/<id>.md` format): own work, the props made from CC0 packs named per file in the props manifest,
`ai_generated = false`, `public_repo_ok = true`. The room scenes are scenes under `levels/`, not assets.

## Questions still open on prime-game #523
- G3: the room scenes are written as `levels/house/rooms/<room>.tscn`; the game's workflow swaps them into its
  greybox rooms (`Body`/`Looks` out, `Shell`/`Dressing`/`Fixtures` in).
- G11: the props are a set, one flat folder with a GLB per prop.
- G1/G2 (art task A4): the known differences to the game's greybox rooms are in `mapping.md`; P3's `storage` is one
  of them (its `Package07`).
- Lights: every fixture is a real-time `OmniLight3D` without shadows (55 in this package); the bake comes later
  (#83, G6).

## Art defaults (the game may change any)
- Colliders are the GLBs' own `-convcolonly` shapes (`StaticBody3D`, layer 1).
- Footsteps: the floors carry `concrete`; the pallets (low props the footstep ray meets first) carry `wood`.
- The art's package check (`house --export --package 3`) is green: 8 scenes load with their root and `size_m`, 7/7
  capsule walks arrive, of the 4448 rays down 4422 hit `concrete`, 22 `wood` (pallets) and 4 `none`: the plinth of
  `boiler_1` under the boiler's body, where no player stands (the 0.4 m player capsule keeps its centre at least
  0.89 m from the boiler's axis, past the plinth's corners at 0.85 m, so the game's footstep ray never meets the
  boiler; it carries no surface).
