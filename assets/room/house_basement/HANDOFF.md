# House package P3, the basement: the game-side handoff (art #126, prime-game #523)

For the game's own import task, after P1 (the kit) and P2 (the ground floor). Nothing here is copied before the
approval fields of this manifest and of `assets/prop/house_props/manifest.toml` are set (the engineer's look approval
on the art PR). P3 was approved and merged in #127 (2026-10-11); #150 re-exported it, so they wait again (below).

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| P1 (`assets/kit/house_kit/HANDOFF.md`) | `assets/environment/house_kit/` (P3's rooms use 9 of its pieces) |
| `assets/kit/house_kit/export/kit_set.gdshader`, `kit_set.tres` (#132) | `assets/environment/house_kit/` (beside the kit's textures) |
| `assets/prop/house_props/export/library/*.glb` (113 of them), `task/*.glb` (15), as `package.json` lists | `assets/environment/house_props/<file>.glb` (flat) |
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

## The plant rooms, the passage and the darkroom's island dressed (#172)

P3 is re-exported for #172: `generator_hall.tscn`, `boiler_room.tscn`, `pump_room.tscn`, `switch_room.tscn`,
`passage.tscn` and `darkroom.tscn` change (`storage.tscn` and `corridor.tscn` keep their bytes). The five plant rooms
are dressed by hand (`layouts/house/dressing/<room>.toml`) as clean, well-kept plant rooms with library v13's 39
props (`docs/props.md`, the plant rooms' pieces): cable trays, isolators, a control desk with screens, fuel drums on
spill bunds, a fire point, a tool chest, spares shelving, a check board and keep-clear floor blocks round the
generator in the hall; a wall boiler, a hot-water cylinder, lagged pipes, a valve board, a pressure vessel, a water
softener and a mop sink in the boiler room; two pump sets on plinths, a sump cover, a hose reel and a rota chart in
the pump room; electrical cabinets, a meter board, a rubber mat, a first-aid box and a lectern with the logbook in
the switch room; safety and door signs (the detail layer) throughout. The darkroom gains a central work island (a
developing bench and a print table with stools). The boiler room's two and the switch room's one bare bulbs are
`fluorescent_tube` fixtures now (`layouts/house/lights.toml`). The package lists 113 library props (85 before):
the derelict pieces these rooms placed (pipe runs, jerrycans, barrels, crates, cardboard boxes, metal shelving) are
gone from them. Every station, spawn and marker keeps its place.


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

## Merged shell (#107, #185)

Draw calls, not the look. Each room's own static kit pieces of a class (floors, ceilings, the rest of the shell) are
drawn by one merged mesh per material, `Shell/merged_<class>` (`house_kit/merged/<class>_m_<level>_<room>.glb`, the
kit's set material on its `kit_set` surfaces with `plan_at` at the room's origin), and each room's static dressing by
one mesh per group, `Dressing/batch_dressing`, `Detail/batch_detail`, `Fixtures/batch_fixtures`
(`house_props/merged/batch_*.glb`, the fine material on its `kit_fine` surfaces; a preset hiding `Detail` hides its
batch too). Here: 16 merged shell meshes and 24 batches, committed in `export/merged/`
(copy them to `assets/environment/house_kit/merged/` and `assets/environment/house_props/merged/`, as
`package.json` lists them).
- Every piece and prop instance is still there with its name, transform, colliders and metadata (`surface`,
  `station`, `prop`); only its own mesh node carries `visible = false`. `test_house_contract` checks every
  game-facing node and collider of this package against main's export (layouts/house/export_contract.json): unchanged.
- Never merged: the pieces the game moves or opens (house.toml `[merge] keep`: gates, wicket, garage door, glass door,
  the attic ladder and hatch boards), task stations and `[merge] keep_props` (the garage's car, lift arms and lift
  panel). A game-side script that moves another prop must move it out of its batch (ask the art side).
- Numbers: the export sheet's storage views draw 61 and 57 calls before, 21 and 19 after; the bake review's cameras (`house --bake --count`): baked 431/171/316 -> 224/101/183 and High 2,719/1,018/1,630 -> 440/193/349 (storage, generator hall, seam); storage stays over the budget (many shelves of distinct materials).
- Shadow proxies (#185): each merged shell and batch with two or more shadow-casting surfaces has a twin,
  `<its node>_shadow` (`merged/<its file>_shadow.glb`, one node `shadow`: the same geometry as one surface
  per cull mode, no material), instanced beside it with `cast_shadow = SHADOWS_ONLY`; the merged mesh's own
  nodes get `cast_shadow = OFF`. A shadowed lamp then draws one surface per proxy into each cube face, not one
  per material. Here: 24 proxies, committed in `export/merged/` and copied beside their merged files as
  `package.json` lists them; a proxy in `Detail` hides with it. Baked and High draw calls are unchanged; the bake review's cameras, High's shadow draw calls 2,566/1,375/2,402 -> 1,196/688/1,116 (storage, generator hall, seam).
  The look is unchanged (mean dL* at most 0.001 per frame). Uniform grid cells of 2-4 m were tried and not
  taken: they multiply the draw calls for at most 5 % fewer shadow draw calls (docs/house.md "Draw calls").
