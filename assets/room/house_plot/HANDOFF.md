# House package P7, the outdoor: the game-side handoff (art #128, prime-game #523)

For the game's own import task, after P1 (the kit) and P2 (the outdoor rooms' markers and lamps: yard, street, path,
driveway). Nothing here is copied before the approval fields of this manifest, of
`assets/environment/house_outdoor/manifest.toml`, `assets/environment/house_garden/manifest.toml` and of
`assets/prop/house_props/manifest.toml` (P7's 32 props) are set (the engineer's look approval on the art PR). They are set:
P7 is approved and merged (#131, 2026-10-12).

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| P1 (`assets/kit/house_kit/HANDOFF.md`) | `assets/environment/house_kit/` (P7 uses 29 of its GLBs and the 3 shared textures: the fence and its gates, the outdoor stairs and rails, the greenhouse's glass roof, the gazebo and the zones' railings) |
| `assets/kit/house_kit/export/kit_set.gdshader`, `kit_set.tres` (#132) | `assets/environment/house_kit/` (beside the kit's textures) |
| `assets/environment/house_outdoor/export/*` (3) | `assets/environment/house_outdoor/` |
| `assets/environment/house_garden/export/*.glb` (14) | `assets/environment/house_garden/` |
| `assets/prop/house_props/export/{library,task,zones}/*.glb` (20, 7 and 9), as `package.json` lists | `assets/environment/house_props/<game name>` (flat; the naming rule below) |
| `assets/room/house_plot/export/outdoor.tscn` | `levels/house/outdoor.tscn` (new: the plot round the house) |
| `assets/room/house_plot/export/greenhouse.tscn`, `garden.tscn` | the content of `levels/house/rooms/greenhouse.tscn`, `garden.tscn` (G3) |

`package.json` beside this file lists the package's 90 game paths with their SHA-256 (the copies must hash the same).
Then the game's `check`, `credits`, the import check (11.3), `load`, `playcheck`, `perf` and `shot`.

## The props' game names (one rule for every package)
The game folder `house_props/` is flat, and 17 basenames repeat between the art's prop sources (`task`, `library`,
`zones`). The first source in `layouts/house/house.toml`'s `prop_dirs` (task, library), then `[export.plot]`
`prop_src`'s other folders (zones), that holds `<id>.glb` ships it as `<id>.glb`; any other source's file ships as
`<id>_<source>.glb`. P2, P3 and P5 resolved every id through `prop_dirs` in the same order, so their paths stay as they
are. P7 ships `birdbath_library.glb` (the task `birdbath.glb` keeps its name) and `bean_bag_zones.glb`,
`cooler_box_zones.glb`, `deckchair_zones.glb`, `fire_pit_zones.glb`, `lantern_zones.glb`, `photo_backdrop_zones.glb`,
`tripod_camera_zones.glb`. The rule: `tools/runner/house_export_plot.py` `game_name`; its tests:
`tools/tests/test_house_export_plot.py` (a fixture, and every raw prop of all sources gets a unique game name while
the first source's names do not change).

## The plot scene
`outdoor.tscn` (root `Outdoor`, plan coordinates: x east, z south, the ground's top at y 0): `Ground` (`outdoor.glb`
as editable children: `ground_grass`, `ground_concrete` and `kerb`, each with `metadata/surface`), `Backdrop`
(`backdrop.glb`, the flats embedded), `Shell` (417 kit pieces) and `Dressing` (203 props and plants). No lights:
P2's outdoor rooms and P7's garden and greenhouse carry the plot's lamps. No placeholders.

## Wall paints and the kit's look (#132)
Every kit instance under the rooms' and the plot's `Shell` overrides its meshes' set surfaces
(`surface_material_override/<i>`) with `res://assets/environment/house_kit/kit_set.tres`: the art's
`kit_set.gdshader`, the kit's `set_d`, `set_n0` and `set_n1` textures and the House's wall paints. Each such mesh also
sets `instance_shader_parameters/plan_at`, its place and turn in the house plan (the plot stands at the plan's origin).
Nothing to run: copy the two files with the kit and load the scenes. P7 has no painted room; the material gives the
kit's textured look (390 set surfaces, the package check finds none without it).

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

## The task props in the world look (#82)

The task props of task v3 are built on the fine pack. `greenhouse.tscn` and `outdoor.tscn` (the yard's `bbq_grill`,
`pose_screen` and `garden_dropoff`) override their `kit_fine` surfaces with
`res://assets/environment/house_props/prop_fine_high.tres`, as the room scenes of P2-P5 do; `package.json` now lists
the fine pack (`prop_fine.gdshader`, `prop_fine_high.tres`, `prop_fine_low.tres` and the 12 PNGs under `fine/`), the
same build and hashes as P2's and P8's (`assets/prop/house_props/HANDOFF.md`). The task props' GLBs hash anew.


## Credits
`CREDITS.md` beside `assets/environment/house_outdoor/manifest.toml` and `assets/environment/house_garden/manifest.toml`
(own work), and `assets/prop/house_props/CREDITS.md` (own work and CC0 packs, named per file in the props manifest);
`ai_generated = false`, `public_repo_ok = true`.

## Questions still open on prime-game #523
- G3 and G11 as in P2.
- The game's greybox has three provisional `spawn_zone` markers (Zone01 in the yard, Zone02 in the garden); the art's
  rooms do not carry them yet (`mapping.md`'s known differences).
- Lights: the garden's and the greenhouse's 24 real-time `OmniLight3D` without shadows; the bake comes later (#83).
- The sky (`sky.png`) ships; the plot scene sets no environment (the game's level owns it).

## Art defaults (the game may change any)
- Colliders are the GLBs' own `-convcolonly` shapes (`StaticBody3D`, layer 1).
- Footsteps: grass, worn grass, soil and the ground beyond the fence `grass`; gravel, paving, the drive, the pavement
  and the street `concrete`, the kerb `concrete`; the outdoor stairs `concrete`, the gazebo's deck `wood`; the
  stepping stones, the fire pit and the watering can `concrete` (low props a player stands on).
- The art's package check (`house --export --package 7`) is green: the two rooms load with their root and `size_m`;
  the plot's 21120 rays down every 0.5 m over the ground (80 x 66 m) hit 13036 `grass`, 4376 `concrete`, 84 `wood`
  (the gazebo), 3624 `hole` (rays that meet nothing inside the ground's holes: the footprints of the house,
  the terrace, the garage and the outdoor stairs' opening, where other packages lay their floors; the greenhouse's
  hole is filled by its own room scene); no ray meets a surface-less collider.

## Merged shell (#107)

Draw calls, not the look. Each room's own static kit pieces of a class (floors, ceilings, the rest of the shell) are
drawn by one merged mesh per material, `Shell/merged_<class>` (`house_kit/merged/<class>_m_<level>_<room>.glb`, the
kit's set material on its `kit_set` surfaces with `plan_at` at the room's origin), and each room's static dressing by
one mesh per group, `Dressing/batch_dressing`, `Detail/batch_detail`, `Fixtures/batch_fixtures`
(`house_props/merged/batch_*.glb`, the fine material on its `kit_fine` surfaces; a preset hiding `Detail` hides its
batch too). Here: 2 merged shell meshes and 2 batches, committed in `export/merged/`
(copy them to `assets/environment/house_kit/merged/` and `assets/environment/house_props/merged/`, as
`package.json` lists them).
- Every piece and prop instance is still there with its name, transform, colliders and metadata (`surface`,
  `station`, `prop`); only its own mesh node carries `visible = false`. `test_house_contract` checks every
  game-facing node and collider of this package against main's export (layouts/house/export_contract.json): unchanged.
- Never merged: the pieces the game moves or opens (house.toml `[merge] keep`: gates, wicket, garage door, glass door,
  the attic ladder and hatch boards), task stations and `[merge] keep_props` (the garage's car, lift arms and lift
  panel). A game-side script that moves another prop must move it out of its batch (ask the art side).
- Numbers: this package has no export-sheet or bake-review view of its own; its rooms draw one mesh per class and material.
