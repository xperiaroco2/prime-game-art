# House package P6, the garage: the game-side handoff (art #79, prime-game #523)

For the game's own import task, after P1 (the kit) and P2 (the ground floor: the yard the side door opens onto). The
car repair chain (M7; the game's car repair ADR, RD2 and R5) plays here. Nothing here is copied before the approval
fields of this manifest and of `assets/prop/house_props/manifest.toml` are set.

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| P1 (`assets/kit/house_kit/HANDOFF.md`) | `assets/environment/house_kit/` (P6's room uses 7 of its pieces: the concrete floor, the storey walls, `garage_door_8m` for the gates) |
| `assets/kit/house_kit/export/kit_set.gdshader`, `kit_set.tres` (#132) | `assets/environment/house_kit/` (beside the kit's textures) |
| `assets/prop/house_props/export/library/*.glb` (21 of them), `task/workbench.glb`, as `package.json` lists | `assets/environment/house_props/<file>.glb` (flat) |
| `assets/prop/house_props/export/fine/high/*.png`, `fine/low/*.png` (6 each) | `assets/environment/house_props/fine/high/`, `fine/low/` |
| `assets/prop/house_props/export/prop_fine.gdshader`, `prop_fine_high.tres`, `prop_fine_low.tres` | `assets/environment/house_props/` |
| `assets/room/house_garage/export/garage.tscn` | the content of `levels/house/rooms/garage.tscn` (G3 below) |

`package.json` beside this file lists the package's 50 game paths with their SHA-256 (22 prop GLBs, the fine pack's 12
PNGs, shader and two materials, 12 kit files, 1 scene; the copies must hash the same). The scene keeps the game room's
root name `Garage`, origin, `metadata/size_m`, `Name` label, `Doors`, `Stations` (`Workbench`, `CarLift`,
`LiftPanel`) and `Markers`, and adds `Shell` (kit instances, the floor with `metadata/surface` `concrete`),
`Dressing` (25 props), `Detail` and `Fixtures` (6 fluorescent tubes, real-time `OmniLight3D` without shadows).

## The car on its lift: what the game moves
Coordinates are the room's (metres, +Y up); the car faces north (-Z), on `CarLift` (10, 0, 7).
- `Dressing/lift_posts_1` (`lift_posts.glb`): the two posts and the power unit. Static; never moved.
- `Dressing/lift_arms_1` (`lift_arms.glb`, at y 0.04): the two carriages and four arms with their pads.
- `Dressing/garage_car_1` (`garage_car.glb`, at y 0): the hatchback, resting on the pads (sills at 0.16 m).
- The drop and the raise: move `lift_arms_1` and `garage_car_1` together along +Y by the same amount. Lowered is the
  scene's pose; raised is +1.24 m (`lift_raise_m` in `layouts/house/dressing/garage.toml`): the sills' underside at
  1.40 m (RD2), the roof at 2.72 m under the 3.0 m ceiling. A lying player fits under the raised car; the posts and
  carriages stand clear of the space between the arms.
- Colliders: the car's two boxes (the body from the sills up and the cabin, layer 1) block movement and line-of-sight raycasts; the arms'
  colliders are the two carriages beside the posts; the posts' colliders are the posts and the power unit. They move
  with their nodes if the game makes the two moving pieces `AnimatableBody3D` (they import as `StaticBody3D`).
- `Dressing/floor_lift_zone_1`: the floor's yellow-and-black markings round the lift (a floor marking, no collider).

## The lift panel and its blind side
`Dressing/lift_panel_1` (`lift_panel.glb`) stands at (3, 0, 11.6), its front facing south to the `LiftPanel` marker
(3, 0, 12), about 5 m from the car (RD2). Between it and the car stand `tyre_rack_1` (2.9, 0, 11.0) and two
`steel_cupboard` (4.6 and 5.85, 0, 11.05), 2 m tall: from the panel's eye points (the marker and a half ring of
0.75 m round it, eyes at 1.0, 1.3 and 1.6 m) no ray reaches the space under the car (84 points, heights 0.15 to
1.25 m; `tools/tests/test_props_garage.py`; without the cupboards 1753 of the rays reach). The game's R5 places the
panel's interaction on the pedestal.

## The part picture
`Dressing/part_picture_1` (`part_picture.glb`) hangs on the east wall at (17.9, 1.3, 6.5), facing west into the room.
The game fills the frame's picture surface: in the prop's own frame (its front +Z) x -0.40..0.40, y 0.05..0.58,
z 0.024 (`prop_geom.part_surface`): the white panel under the yellow PART NEEDED header.

## The workbench and the doors
The `Workbench` station (16, 0, 3) keeps the task prop `workbench` (the delivery drop-off and the motor oil) 1.1 m
east of it under the east window; nothing stands within 0.3 m of any station or spawn. The gates (`Door2`, an 8 m
`garage_door_8m` to the driveway, closed kit leaf), the side door to the yard (`Door1`) and the back door to the
outdoor stairs (`Door3`) are as `layouts/house/ground.toml` has them; the dressing keeps the walks from each to the
car, the workbench and the panel clear (the art's capsule check and walk).

## Wall paint and the kit's look (#132)
Every kit instance under `Shell` overrides its meshes' set surfaces with
`res://assets/environment/house_kit/kit_set.tres` and sets `instance_shader_parameters/plan_at`, as in the other
packages. The garage is painted a neutral concrete grey `#8f897d` (`[wall_paint]`); nothing to run.

## Credits
The entries are `assets/kit/house_kit/CREDITS.md` and `assets/prop/house_props/CREDITS.md` in this repo (copy them to
the game's `docs/credits/house_kit.md` and `house_props.md`): own work, every P6 prop procedural,
`ai_generated = false`, `public_repo_ok = true`. The room scene is a scene under `levels/`, not an asset.

## Questions still open on prime-game #523
- G3: the room scene is written as `levels/house/rooms/garage.tscn`; the game's workflow swaps it into its greybox
  room (`Body`/`Looks` out, `Shell`/`Dressing`/`Fixtures` in).
- G11: the props are a set, one flat folder with a GLB per prop.
- Lights: 6 real-time `OmniLight3D` without shadows; the bake comes later (#83, G6).

## Art defaults (the game may change any)
- Colliders are the GLBs' own `-convcolonly` shapes (`StaticBody3D`, layer 1).
- Footsteps: the floor carries `concrete` (1008 of 1008 rays down hit it).
- The art's package check (`house --export --package 6`) is green: the scene loads headless with its root and
  `size_m`; 183 layer-1 bodies; the walks out of the garage (side door, back door) are walked with P2 and the plot.
- The garage's draw calls in the art's walk: 303 (126 the dressing's), 103716 primitives in view.
