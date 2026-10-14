# House package P8, the task props: the game-side handoff (art #82, prime-game #523)

For the game's own import task, after P1 (the kit). P8 is the House's 34 task-station props on their own: the five
task chains' 22 props (design doc §6) and the 12 room-defining pieces of `props/tasks.toml`, with the world look's fine
pack they use. It has no room scenes: the room packages (P2 to P5, P7) place these props; P8 lets the game import and
wire the task props (stations, states, writable surfaces) before or without the rooms. Nothing here is copied before
the approval fields of `manifest.toml` beside this file are set (approved under the engineer's blanket yes of
2026-10-14 in PR #174).

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| `assets/prop/house_props/export/task/*.glb` (34) | `assets/environment/house_props/<id>.glb` (flat) |
| `assets/prop/house_props/export/fine/high/*.png`, `fine/low/*.png` (6 each) | `assets/environment/house_props/fine/high/`, `fine/low/` |
| `assets/prop/house_props/export/prop_fine.gdshader`, `prop_fine_high.tres`, `prop_fine_low.tres` | `assets/environment/house_props/` |

`package.json` beside this file lists the package's 49 game paths with their SHA-256 (34 GLBs, the fine pack's 12 PNGs,
the shader and two materials); the copies must hash the same. The fine pack is the same build every package ships
(P2's bytes): copy it once. The names are the same game files the room packages use: a room package and P8 never
disagree on `assets/environment/house_props/<id>.glb` (`boiler`, `pump`, `birdbath`, `toy_chest`: the task prop ships
under the id, a library namesake as `<id>_library.glb`). Then the game's `check` (commit the `.import` files it
writes), `credits` and the import check (11.3) locally with LFS content.

## The world look (#82)
The 22 task-chain props are built on the fine pack (`docs/props.md`, "The task props in the world look"): their
`kit_fine` surfaces take `res://assets/environment/house_props/prop_fine_high.tres` (or `prop_fine_low.tres`: the game
swaps the tier per graphics preset, as in P2's `HANDOFF.md`). A room scene of P2-P5 or P7 already overrides them; a
scene the game builds itself must set `surface_material_override` on those surfaces the same way. The 12 room-defining
props (boiler, pump, water_tank, switchboard, cable_drum, enlarger, tray_table, toy_chest, utility_pole, birdbath,
bulkhead_stairs, music_speaker) keep the kit's paint and need no material.

## The props: stations, states and named surfaces
Sizes in metres (width, depth, height), the station marker under the room's `Stations`, and the nodes the game drives.

| Chain | Prop | Station (room) | Size | Nodes the game uses |
|---|---|---|---|---|
| delivery | `delivery_box_stack` | Boxes (storage) | 1.2 x 1.0 x 1.3 | |
| delivery | `wine_rack`, `wine_rack_freestanding` | WineRack (storage) | 2.0 x 0.4 / 0.7 x 2.0 | |
| delivery | `dining_table` | DiningTable (dining_room) | 3.0 x 1.2 x 0.76 | |
| delivery | `terrace_table` | TerraceTable (terrace) | 1.6 x 0.9 x 0.75 | |
| delivery | `garden_dropoff` | GardenDropOff (garden) | 1.6 x 0.7 x 0.9 | |
| delivery | `workbench` | Workbench (garage) | 2.2 x 0.8 x 0.95 | |
| burgers | `order_board` | OrderBoard (kitchen) | 1.74 x 0.5 x 2.1 | the writable surface (below) |
| burgers | `assembly_island` | OrderBoard (kitchen) | 2.4 x 1.0 x 0.9 | |
| burgers | `bun_shelf` | Buns (storage) | 2.0 x 0.5 x 2.0 | |
| burgers | `meat_freezer` | Meat (storage) | 1.8 x 0.8 x 0.9 | `meat_freezer_lid` (opens) |
| burgers | `bbq_grill` | Grill (chill_zone) | 1.2 x 0.6 x 1.0 | `bbq_grill_lid` (opens) |
| burgers | `herb_bed` | HerbBeds (greenhouse) | 3.0 x 1.2 x 0.5 | |
| burgers | `herb_board` | HerbBoard (greenhouse) | 1.94 x 0.5 x 2.2 | the writable surface |
| generator | `generator` | Generator (generator_hall) | 2.4 x 1.1 x 1.5 | `generator_on`, `generator_off` (states) |
| generator | `wall_switch` | SwitchA-D (storage, boiler_room, pump_room, switch_room) | 0.3 x 0.15 x 1.55 | `wall_switch_on`, `wall_switch_off` |
| generator | `wall_switch_post` | the same: the box on a floor post, for markers 1.5 to 2 m from a wall | 0.4 x 0.4 x 1.6 | `wall_switch_post_on`, `wall_switch_post_off` |
| photo | `pose_screen` | PoseScreen (photo_zone) | 2.14 x 0.6 x 2.2 | the writable surface |
| photo | `computer_set` | Printer (study) | 0.6 x 0.5 x 0.42 | the writable surface (its screen) |
| photo | `photo_printer` | Printer (study) | 0.5 x 0.4 x 0.3 | `photo_printer_photo` (the print, shown when done) |
| photo | `photo_board` | PhotoBoard (darkroom) | 3.14 x 0.5 x 2.3 | the writable surface |
| car repair | `car_parts_shelf` | PartsShelf (storage) | 2.0 x 0.5 x 2.0 | |

- **States: two state meshes in one GLB.** The generator and both switches carry `<id>_on` (signal green: the switch's
  lamp and lever up, the generator's status bar and beacon lit) and `<id>_off` (signal red). Both are visible in the
  GLB; the game shows the one for the current state and hides the other. Each reads from 3 m in front, and the post
  switch from 8 m.
- **Writable surfaces.** The order board, the herb board, the pose screen, the photo board and the computer's screen
  hold one flat quad facing the prop's front (+Z) on the material `surface_game`, UV0 over the whole quad: the game
  replaces that material with its own drawing (the order, the herbs, the pose, the photos, the photo to print).
- Pivots and colliders as `props/tasks.toml` defines them (unchanged by #82): the front faces +Z; the floor props'
  pivot on the floor; the wall switch's box at 1.1 m on a back plate with a conduit down to its floor pivot. Colliders
  are convex nodes `<id>_col<k>-convcolonly` (the kit's convention, `docs/kit.md`); the lids, the state meshes and the
  print have none of their own.

## Open questions
- G3 and G11 as in P2 (`package.json` `questions`).
- The state meshes are shown and hidden by name; if the game prefers two GLBs per state, the art side can split them.
