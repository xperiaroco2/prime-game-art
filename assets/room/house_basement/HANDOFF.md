# House package P3, the basement: the game-side handoff (art #126, prime-game #523)

For the game's own import task, after P1 (the kit) and P2 (the ground floor). Nothing here is copied before the
approval fields of this manifest and of `assets/prop/house_props/manifest.toml` are set (the engineer's look approval
on the art PR). P3 was approved and merged in #127 (2026-10-11); #150 re-exported it, so they wait again (below).

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| P1 (`assets/kit/house_kit/HANDOFF.md`) | `assets/environment/house_kit/` (P3's rooms use 9 of its pieces) |
| `assets/kit/house_kit/export/kit_set.gdshader`, `kit_set.tres` (#132) | `assets/environment/house_kit/` (beside the kit's textures) |
| `assets/prop/house_props/export/library/*.glb` (85 of them), `task/*.glb` (15), as `package.json` lists | `assets/environment/house_props/<file>.glb` (flat) |
| `assets/prop/house_props/export/fine/high/*.png`, `fine/low/*.png` (6 each, #147, #150) | `assets/environment/house_props/fine/high/`, `fine/low/` |
| `assets/prop/house_props/export/prop_fine.gdshader`, `prop_fine_high.tres`, `prop_fine_low.tres` (#147) | `assets/environment/house_props/` |
| `assets/room/house_basement/export/<room>.tscn` (8) | the content of `levels/house/rooms/<room>.tscn` (G3 below) |

`package.json` beside this file lists the package's 137 game paths with their SHA-256 (the copies must hash the same),
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

## Wall paints and the kit's look (#132)
Every kit instance under `Shell` overrides its meshes' set surfaces (`surface_material_override/<i>`) with
`res://assets/environment/house_kit/kit_set.tres`: the art's `kit_set.gdshader`, the kit's `set_d`, `set_n0`
and `set_n1` textures and the House's wall paints (`layouts/house/house.toml` `[wall_paint]`). Each such mesh
also sets `instance_shader_parameters/plan_at`, its place and turn in the house plan, so the shader paints by
the plan wherever the game puts the House. Nothing to run: copy the two files with the kit and load the scene
(the root's `metadata/wall_paint` stays as a note). No basement room has a paint (it keeps the kit's concrete); the material gives the kit's textured
look.

## The rebuilt props, the fine pack and the Detail node (#150)
P3 is re-exported for #150: its scenes place the rebuilt sideboard (`docs/props.md`, the living room's pieces;
same file names, new bytes) and override their `kit_fine` surfaces with
`res://assets/environment/house_props/prop_fine_high.tres`, so the package lists the fine pack (the 6 PNGs per
tier, the shader, the two `.tres`; one copy per game, P2's `HANDOFF.md`). Every room also gains #147's `Detail`
node beside `Dressing` and `Fixtures` (empty here until a room's detail pass). The approval fields wait for the
engineer's yes.

## The engineer's paints of 2026-10-14 (#152)

Only `package.json` changed: the shared `kit_set.tres` carries the new wall paints and the rebuilt kit pieces of the
warm sand ceiling hash anew; this package's scenes are unchanged.

## The WC's and the pantry's paints (#158)

Only `package.json` changed: the shared `kit_set.tres` carries the WC's and the pantry's paints and hashes anew;
this package's scenes are unchanged.

## The bathroom's paint (#162)

Only `package.json` changed: the shared `kit_set.tres` carries the bathroom's paint and hashes anew; this
package's scenes are unchanged.

## The kids' room's paint (#166)

Only `package.json` changed: the shared `kit_set.tres` carries the kids' room's paint and hashes anew; this
package's scenes are unchanged.

## The attic's paint (#168)

Only `package.json` changed: the shared `kit_set.tres` carries the attic's paint and hashes anew; this
package's scenes are unchanged.

## The storage, the darkroom and the corridor dressed (#170)

P3 is re-exported for #170: `storage.tscn`, `darkroom.tscn` and `corridor.tscn` change (the other five scenes keep
their bytes). The three rooms are dressed by hand (`layouts/house/dressing/storage.toml`, `darkroom.toml`,
`corridor.toml`) as clean, well-organised working rooms with library v12's 32 basement props (`docs/props.md`, the
basement's pieces): steel shelving, the buns' bread rack, a delivery pallet with its pallet jack, a workbench, a step
ladder, a delivery trolley, floor markings and signs in the storage; a lab sink, a chemicals shelf, a light table and
drying lines of prints in the darkroom; rubber matting, work hooks, a fire extinguisher and a fuse box in the
corridor. The storage's twelve bare bulbs are `fluorescent_tube` fixtures now (`layouts/house/lights.toml`). Copy the
new props with the others `package.json` lists; every station, spawn and marker keeps its place.


## Credits
The entries are `assets/kit/house_kit/CREDITS.md` and `assets/prop/house_props/CREDITS.md` in this repo (the game's
`docs/credits/<id>.md` format; copy them to `docs/credits/house_kit.md` and `house_props.md`): own work, the props made from CC0 packs named per file in the props manifest,
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
  capsule walks arrive, of the 4448 rays down 4434 hit `concrete`, 10 `wood` (pallets) and 4 `none`: the plinth of
  `boiler_1` under the boiler's body, where no player stands (the 0.4 m player capsule keeps its centre at least
  0.89 m from the boiler's axis, past the plinth's corners at 0.85 m, so the game's footstep ray never meets the
  boiler; it carries no surface).
