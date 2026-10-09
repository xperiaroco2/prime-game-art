# Procedural props: the House map's task stations

The House map (request #73) needs props where the five task chains happen (design doc §6; the plan's
`inventory.md` §7) and a few room-defining pieces no pack has. Art #82 builds them as repo code in the House kit's
way (`docs/kit.md`): a spec (`props/tasks.toml`), a pure-Python geometry module (`tools/blender/props_task.py`), a
headless Blender builder (`props_task_build.py`, which reuses the kit's `kit_build.py` for objects, materials and the
export) and the `props` command. The GLBs stay in the raw folder (`D:/prime-art-raw/props/task/v1/`) until the
engineer approves the look; then they come into the repo with their manifests.

## The command

```
tools/run.sh props [--spec props/tasks.toml] [--out DIR] [--only id,...] [--no-build] [--no-godot] [--review DIR]
```

| Option | What it does |
|---|---|
| (none) | Checks the spec and every prop's geometry, builds every prop in headless Blender, checks every GLB (glTF-Validator, nodes, UV2, vertex colours, the game surface's material) and imports them all into `godot/` headless (the kit's `godot/check/kit.gd`) |
| `--out` | Output folder (default `<raw>/props/task/v<version>`) |
| `--only` | Only these props |
| `--no-build` | Checks the GLBs already in `--out` |
| `--no-godot` | Skips the Godot import |
| `--review DIR` | Also renders the line-up sheets `lineup_<group>.png` (1280 px wide: each prop from the front and from 3/4, orthographic, with a 1.8 m grey capsule; Workbench with the vertex paint) and `switch_8m.png` (the post switch on and off from 8 m at a 1.6 m eye, 75 degree field of view) |

It takes the heavy-run lock (Blender, Godot): run it in the background with its log under `tools/out/` and check it
with `tools/run.sh wait`. It writes into `--out`: `<id>.glb`, `textures/`, `build.json`, `reports/<id>.json`,
`godot.json` and the prop table `props.md` / `props.json` (chain, station, room, count, triangles against the
budget, size, colliders, game surface, extra nodes).

## The spec: `props/tasks.toml`

Every value is the engineer's to change (sizes, paints, mounts), as data:

- `kit`: the kit whose materials, packs and roles the props use (`kits/house.json`); a prop role may not redefine a
  kit role.
- `budget_tris`: `hero` 4,000 (task-critical pieces players use) and `room` 1,500 (room-defining), the plan's
  `look.md` §6.
- `materials.surface_game`: the game's writable surface, a material of its own that only the boards and the computer
  use.
- `roles`: the prop paints (a material and a hex colour each).
- `[[props]]`: `id`, `type` (the builder), `kind` (the budget), `w`, `d`, `h` (the built bounds, width along X,
  depth along Z, height along Y, within 1 cm), `chain`, `station` (the game's marker under `Stations`), `room`,
  `count`, and per type: `mount` (`wall`, `floor`, `post`, `stand`, `table`), `surface`, `nodes`, `board`, `style`,
  `plan_size` (the plan's size where a stand or fitting adds to it) and `notes`.

## Conventions

- **Pivot and front**: the pivot is on the floor at the game's marker (a table-top prop's on the desk top), the
  footprint centred on it; the one front faces +Z. Godot's axes, metres.
- **Paint and materials**: as the kit's (`docs/kit.md`, "Paint"): one role per face, sRGB-encoded vertex colours,
  materials named `kit_<name>-vcol` (kit v2: plaster, wood and concrete export as one `kit_set-vcol`, the vertex
  colour's alpha picking the layer); the game surface is `surface_game-vcol`.
- **Game surface**: one flat quad facing +Z with UV0 0..1 over it (u along +X, v up), on the `surface_game`
  material, so the game can draw icons and text on it: the order board, the herb board, the pose screen, the photo
  board and the computer's screen.
- **Moving parts** are leaves with their hinge as origin and their collider parented to them: the freezer's, the
  grill's and the toy chest's `<id>_lid`.
- **States** are separate meshes the game shows or hides: a switch's `<id>_on` (lever up, green lamp, green knob)
  and `<id>_off` (lever down, red lamp, red knob); the printer's `<id>_photo` (the print in the output tray). The
  switch's state must read from 8 m (#82b), where its 0.3 x 0.45 m box is about 17 x 26 px at 720 px: the lamp is a
  window across the box's whole top (0.24 m) and the lever's crossbar is as wide, so the state reads as a band of
  colour at the top (on) or at the top and the foot (off). The lamps are paint, not emissive: in a dark room the game
  may give `<id>_on`'s `lamp_green` and `<id>_off`'s `lamp_red` faces an emissive override.
- **Collision**: closed convex boxes or prisms, `<id>_col<k>-convcolonly`, roughly the prop's volume (a table blocks
  sight under it); checked in Godot by one ray per collider.
- **The clay look**: every box over a few centimetres has chamfered edges (`cbox`), cylinders and lathed shapes are
  8 to 12 sided with chamfered rims, and the detail is hand-placed parts (louvres, gauges, bolts, tape, labels).
  One paint per face: there is no edge-wear or dirt vertex-colour pass yet (the house plan's look.md section 5); it is
  left to the clay look (#42a), so the kit and the props wear the same way.

## The checks

1. **Spec** (`props_task.check_spec`, `check_prop`): ids unique, roles on known materials, every prop's bounds equal
   its `w`, `d`, `h`, its lowest point on the floor and its footprint centred, within the budget, colliders not
   flat, UV2 on every face inside 0..1, a game surface exactly where `surface = true`, the `nodes` present.
2. **GLB** (the kit's `_kit.check_glb` and `props.check_surface_material`): every mesh node has UV0, UV2, COLOR_0
   and normals, every collider its node, at most the exported materials (`set`, `metal`, `glass`,
   `surface_game`), all `-vcol`; glTF-Validator has no errors.
3. **Godot** (`godot/check/kit.gd`, `_kit.evaluate`): bounds equal the spec's within 2 mm, the triangle count, UV2
   and sRGB vertex colours on every surface, one closed convex body per collider, and a ray hits each.
