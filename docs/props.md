# Props of the House map

Two procedural prop sets share `props/` and this page: the task-station props (`props/tasks.toml`, the `props`
command, art #82) and the dressing library (`props/library.toml`, the `props-library` command, art #87). The
library's `tools/blender/prop_lib.py` is meant as the shared prop helper (materials, paint by role, pivot, UV2,
collision, one GLB per prop); the task props keep their own `props_task.py` for now.

## World look rules

The House's look is C2-white from the kitchen pilot (ADR `docs/decisions/2026-10-13-house-world-look.md`, #143).
Every room's props follow these rules; the numbers are data in `props/library.toml` and `props-library` checks them.

1. **Not plasticine, never worn.** Only the characters are plasticine. The world is a present-day, well-made home:
   no wear, chips, dirt or grime. Richness comes from parts, materials and density, not damage.
2. **Real parts, one style per room** (`[style]`): bodies, fronts, plinths, tops and hardware are separate parts;
   bevels of 10 mm on bodies and slabs and 3 mm on fronts and small parts; one bar handle (7 mm round bar on two
   30 mm standoffs), one plinth (0.1 m, set back 75 mm) and one worktop line (0.9 m, 30 mm thick) per room; a soft
   shade toward the floor (x0.82 at the floor, none from 0.25 m up).
3. **Materials: the fine pack.** Opaque paints sit on one shared material, `fine`, each role on a layer (`[fine]`):
   textured wood fronts (Wood092), worktop wood (Wood049), stone (Concrete034) and tile (Tiles107); flat enamel,
   warm steel, chrome, dark gloss and paint; the living room's soft goods (#150): textured fabric (Fabric036, linen
   upholstery), weave (Fabric061, cushions and throws) and carpet (Carpet016, rugs). Glass is `glass_tint`. A new
   paint is a role with a `layer` and a hex; a new texture is a `[fine]` layer from a recorded CC0 source, appended
   at the end so the built GLBs keep their layer indices (at most 8 textured layers: a textured layer's slot is its
   place among the textured ones; `fine_d.png` and `fine_d1.png` hold four slots' detail each, `fine_n0.png` to
   `fine_n3.png` two slots' normals each, and a build writes only the files its slots need). A prop has at most two
   surfaces (fine, glass).
4. **Shared textures, two tiers.** The GLB has no textures; Godot maps `kit_fine` to one ShaderMaterial with one
   texture set per tier (High 1024 px, Low 512 px, from the same sources), VRAM-compressed on import.
5. **Classes.** `hero` (1,200 to 4,000 triangles) for the pieces players look at up close (appliances, a room's
   centre piece); `room` (400 to 1,500) for the rest of the furniture; `clutter` for the small things.
6. **Base and detail layers** (`layer`, default by class in `[layers]`): the base layer alone makes the room read
   clean on Low; small props and fine decor are `detail` (clutter by default), which High and Ultra add. A detail
   prop has no collider.
7. **Shared builders** (`prop_geom.py`, "the world look"): `Style` (from `[style]`), `front` (a bevelled door or
   drawer front, raised panel or framed glass, with its handle and hinges), `bar_handle`, `plinth`, `worktop`,
   `backsplash`, `burner` and `burner_grate`, `tap`, `rslab` (soft vertical edges). Fronts and handles stay inside
   `size_m`; a builder may name its own collider boxes (the stove's body and hood leave the gap over the hob open).
   The kitchen's `kitchen_counter` (with `sink`), `kitchen_upper`, `stove`, `fridge` and the backsplash runs
   (`backsplash_l`, `backsplash_r`: shape `backsplash`, wall pivot, no collider) are built from them; so are the
   task props `assembly_island` and `order_board` (`props/tasks.toml`, `look = "fine"`). The living room's pieces
   (#150) add upholstered seats with cushions (`sofa`, its armchair variant), shelving with books (`bookcase`), a
   mantel surround with a stone hearth (`mantel_fireplace`), a TV unit with its TV (`tv_unit`), `coffee_table`,
   `sideboard` (the sideboard and the dresser), `side_table` and `carpet_rug`, and six clutter-class detail props for
   the living room's detail layer: `living_tray`, `magazine_fan`, `mantel_clock`, `standing_frame`, `throw_basket`,
   `candle_pair` (12 to 400 triangles each, no collider). Round 2 adds 16 more: five pieces of wall art drawn
   procedurally (`art_abstract`, `art_city`, `art_burger`, `art_photos`, `art_score`), ten detail props (`board_games`,
   `candle_jars`, `coffee_books`, `deco_bowl`, `deco_vase`, `game_console`, `laptop`, `side_lamp`, `slippers`,
   `table_plant`) and `floor_plant` (its pot the only collider): 22 new living-room props and 10 rebuilt ones.
8. **Route.** Hard-surface props are code (the shared builders, `prop_geom.py`'s `Style`). Meshy only for organic
   one-offs (food, soft goods, plants) at a hero budget, as a recorded batch (`docs/meshy.md`).

## Procedural props: the House map's task stations

The House map (request #73) needs props where the five task chains happen (design doc §6; the plan's
`inventory.md` §7) and a few room-defining pieces no pack has. Art #82 builds them as repo code in the House kit's
way (`docs/kit.md`): a spec (`props/tasks.toml`), a pure-Python geometry module (`tools/blender/props_task.py`), a
headless Blender builder (`props_task_build.py`, which reuses the kit's `kit_build.py` for objects, materials and the
export) and the `props` command. The GLBs stay in the raw folder (`D:/prime-art-raw/props/task/v1/`) until the
engineer approves the look; then they come into the repo with their manifests.

### The command

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

### The spec: `props/tasks.toml`

Every value is the engineer's to change (sizes, paints, mounts), as data:

- `kit`: the kit whose materials, packs and roles the props use (`kits/house.json`); a prop role may not redefine a
  kit role.
- `budget_tris`: `hero` 4,000 (task-critical pieces players use) and `room` 1,500 (room-defining), the plan's
  `look.md` §6.
- `materials.surface_game`: the game's writable surface, a material of its own that only the boards and the computer
  use.
- `roles`: the prop paints (a material and a hex colour each).
- `library`: the dressing library (`props/library.toml`) whose fine pack, fine-pack paints and `[style]` join the
  spec, for the props in the world look ("World look rules"); a fine paint may not share a name with a kit or prop
  role.
- `[[props]]`: `id`, `type` (the builder), `kind` (the budget), `w`, `d`, `h` (the built bounds, width along X,
  depth along Z, height along Y, within 1 cm), `chain`, `station` (the game's marker under `Stations`), `room`,
  `count`, and per type: `mount` (`wall`, `floor`, `post`, `stand`, `table`), `surface`, `nodes`, `board`, `style`,
  `plan_size` (the plan's size where a stand or fitting adds to it) and `notes`; `look = "fine"` builds the prop
  with its type's fine builder (`props_task.FINE_BUILDERS`: `board` on a stand, `island`) on the library's fine pack,
  and `check_spec` refuses it for a type without one or a spec without `library`.

### Conventions

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

### The checks

1. **Spec** (`props_task.check_spec`, `check_prop`): ids unique, roles on known materials, every prop's bounds equal
   its `w`, `d`, `h`, its lowest point on the floor and its footprint centred, within the budget, colliders not
   flat, UV2 on every face inside 0..1, a game surface exactly where `surface = true`, the `nodes` present.
2. **GLB** (the kit's `_kit.check_glb` and `props.check_surface_material`): every mesh node has UV0, UV2, COLOR_0
   and normals, every collider its node, at most the exported materials (`set`, `metal`, `glass`,
   `surface_game`), all `-vcol`; glTF-Validator has no errors.
3. **Godot** (`godot/check/kit.gd`, `_kit.evaluate`): bounds equal the spec's within 2 mm, the triangle count, UV2
   and sRGB vertex colours on every surface, one closed convex body per collider, and a ray hits each.

## The zone props: `props/zones.toml`

Art #81b adds the chill zone's and the photo gazebo's props as a second spec beside `tasks.toml`, built by the same
command: `tools/run.sh props --spec props/zones.toml [--review DIR]`. Their builders are in
`tools/blender/props_zone.py` (registered into `props_task.BUILDERS`); the spec's `out_dir = "zones"` sends the GLBs
to `D:/prime-art-raw/props/zones/v1/`, and its `label` heads the line-up sheet `lineup_zones.png`.

- Props: `deckchair`, `fire_pit`, `bean_bag`, `cooler_box`, `photo_backdrop`, `tripod_camera`, `lantern`, and two
  string-light sets: `string_lights_set` (a 5 m strand between two weighted poles, for open ground) and
  `string_lights_gazebo` (a strand hung between two of the kit gazebo's posts).
- Budgets add `dressing` 600 and `fixture` 400 triangles (the plan's `look.md` section 6).
- **Light fixtures** carry their bulbs (and the fire pit its embers) on an `emissive` material (`kit_emissive-vcol`,
  emission lamp c2 `#ffd9ad`; the vertex colour keeps each bulb's tint) and name their light anchors as sockets
  `light_<k>` in `build.json`'s describe output: the assembly puts the baked light there. Lights are fixtures, never
  free-floating lights (the plan's inventory section 8).
- `mount = "hang"`: a strand hung from two hooks has its pivot in the middle of the hook line and hangs below it
  (y from -h to 0); the floor check becomes "the highest point at y 0".
- The builders aim at the spec's bounds and `props_zone.fit` absorbs the rest (bars' slant, lathe facets) by at most
  6 % per axis; a bigger miss fails the build.
- A zone prop has `chain = "zone"` and `station = "-"`; the stations themselves (the grill, the speaker, the pose
  screen) stay in `tasks.toml`. Where they stand is the zones' layout data (`docs/zones.md`).

## The House dressing library

Art #87 (map request #73) makes one shared library of generic props (furniture, dressing, light fixtures, outdoor
things) so that every room package places furniture instead of making it. Task props (#82a, #82b), the car and its
lift (#79), vegetation (#80), the gazebo (#81b) and kit pieces are made elsewhere; `[skip]` in the mapping file names
who makes each. The plan is `D:/prime-art-raw/research/2026-10-10-house-plan/` (`props.md`, `inventory.md` §9,
`look.md` §5 and §6). The GLBs stay in the raw folder (`D:/prime-art-raw/props/library/v3/`; v2 is v3 before #152's cream sofa and armchairs, v1 the version-1 build, #150) until the engineer
approves the look on a review page; then they come into the repo under `assets/prop/<id>/` with their manifests.

### The mapping file: `props/library.toml`

The library is data: a paint, a size, a source file or a shape changes without a code change.

| Field | What |
|---|---|
| `[materials]` | Library material name to the kit's material (`kits/house.json`). The **one place** that names materials: when kit v2 (#86) merges plaster, wood and concrete into one `set` material, re-point the lines here. At most `max_materials` (8) targets; a target the kit lacks must be in `new_materials` (`emissive`, `fine`, `glass_tint`). |
| `[material_props]` | Roughness, metallic and alpha of a new material that is no kit material (`glass_tint`). |
| `[budgets]` | Triangles by class, `[min, max]` (`look.md` §6): `dressing` 150 to 600, `room` 400 to 1,500, `fixture` 100 to 400, `vehicle` 400 to 3,000 (the parked cars), `clutter` 12 to 400 (the small lived-in props of #104: books, cups, plates, bottles, pots, papers, frames' kin, baskets, shoes, toys; all `collision = "none"`, batch 3, placed by `house --clutter`, docs/house.md "Clutter"), `hero` 1,200 to 4,000 (the pieces players look at up close: the stove, the fridge). |
| `[layers]` | The layer by preset (`base` or `detail`) per class, and the `default`: `clutter` is `detail`. A prop's own `layer` overrides it; a detail prop must have `collision = "none"`. |
| `[style]` | The world look's measures (bevels, segments, the handle, front gap and thickness, plinth, worktop line, `floor_shade`) and the direction's `paints`; the shared builders read them ("World look rules"). |
| `[fine]` | The fine pack: `source` (the CC0 record of its textures), `tiers` (px per tier, High over Low) and `layers` in order (at most 16, at most 8 of them textured; a new layer goes at the end): a textured layer has `source`, `roughness`, `normal_strength`; a flat one `metallic` and `roughness`. |
| `[roles]` | The props' paints: a library material and an sRGB hex (the D1 palette, `look.md` §7). A role on the fine pack also names its `layer`. A prop may also name the kit's roles (`trim`, `fence`, `lino`, `glass` ...). |
| `[skip]` | Inventory ids this library does not make, with the package that does. |
| `script` | The Blender build script (default `prop_build.py`); another mapping file in this format names its own, such as `props/plants.toml`'s `plant_build.py` (the garden's plants, `docs/house-garden.md`). |
| `[[prop]]` | One prop: `id`, `batch` (the build order: 1 indoor furniture and dressing, 2 outdoor, fixtures and vehicles), `name`, `class`, `size_m` (the inventory's L x W x H: along X, along Z, up), `count` (placements), `route` (`pack` or `proc`), `roles`, `pivot`, `collision`, optional `layer` and `built_size_m` (the built box when fixed parts reach past the inventory's: the stove's hood, the sink's tap; the size checks use it). |
| pack props | `source` (a `sources/<id>.toml` record), `files` (relative to `<raw>/env`; several are stacked, the next on top of the one before), `src_size` and `src_triangles` (measured from the glTF), `yaw_deg` (a turn about +Y that brings the front to +Z), `scale` (uniform), `stretch` (fit the box per axis), `decimate` (the source is over the class's budget), `pack_size_m` (the part the pack supplies when `extras` add the rest), `extras` (procedural additions such as a wall mirror), `paint` (the roles of the source's colour clusters, dark to light, when the luminance order paints a prop wrong). |
| proc props | `shape` (a builder) and `params`. Generic builders cover most furniture: `cabinet` (doors, drawers, plinth or legs, top, cornice, sink), `table` (legs, top, shelf), `shelving` (shelves, items), `bench` (back, slats, cushion); the rest are one builder per prop. |

### Conventions

- **Axes**: Godot's, metres, +Y up; the front faces **+Z**.
- **Pivot**: `floor` at the footprint's centre on y = 0; `wall` with the back on the wall plane z = 0, centred on X,
  the bottom at y = 0 (the layout gives the height); `ceiling` with the top at y = 0, centred on X and Z.
- **Paint**: the kit's route (`docs/kit.md`, "Paint"): the pack's own material and atlas are dropped; the source's
  colours are clustered into as many groups as the prop has roles; the clusters, dark to light, take the roles, dark
  to light; the paint is written as sRGB vertex colours on `-vcol` materials.
- **Collision**: `box` (one box), `boxes` (several, for an L shape), `hull` (one convex hull) or `none` (rugs,
  decals, small fixtures above head height); closed, it stops line-of-sight rays, as the kit's check proves.
- **UV0** in metres for the detail textures; **UV2** packed for the lightmap bake, as the kit does.
- **Fixtures** carry their bulb as an `emissive` part; the light itself is a Godot node the map places.

### Scale: why many props are procedural

The plan expected about 80 pack props. Fitting the packs to the inventory's real sizes showed that the rounded toy
families (KayKit, Tiny Treats) are chunky: their counters, cabinets, wardrobes and benches are low and deep, and a
fit distorts them by more than 1.5 times between axes. Simple boxy furniture is cheap and exact as a procedural
build in the kit's materials, so version 1 has 32 pack props and 99 procedural ones (77 at first, then the
clutter of art #104 and its story pieces: `laundry_basket`, `drying_rack`, `open_box`, `radiator`,
`laundry_pile`, `boots`, `toy_spill`; docs/house.md "Fill"). The check (`_props.check`):

- without `stretch`, the uniformly scaled source is within 10 % of the inventory size on every axis;
- with `stretch`, the largest axis factor over the smallest is at most 1.5;
- a source over its class's budget needs `decimate = true`; every source is CC0 with `public_repo_ok = true`.

### The build

`tools/run.sh props-library --build [--batch 1|2] [--only id,...]` builds the props in one headless Blender run
(`tools/blender/prop_build.py`) into the mapping file's `out`, `D:/prime-art-raw/props/library/v3/`: one `<id>.glb` per prop, `textures/`
(the kit's detail maps), `build.json` (what each GLB holds; batches accumulate) and `props.md` (the build table); then
it checks every GLB: the mesh and collider nodes, UV2 and vertex colours, at most `max_materials` materials all named
`-vcol`, glTF-Validator, the class's maximum triangles, a collider unless `none`, a fixture's light anchor. Under the
class's minimum is a note, not a problem: simple props are cheap. `--no-blender` checks the files already built.

The code is in three files:

| File | What |
|---|---|
| `tools/blender/prop_geom.py` | Pure Python (tested without Blender, `tools/tests/test_props_geom.py`): the primitives (a soft box with 4 mm chamfers, cylinders and frustums, tubes, ellipsoids, beams and rods at any angle, slabs, lofts), one builder per `shape`, the pack paint (k-means of the faces' colours, dark to light onto the roles, dark to light), the pivot, the collider and the light anchor, the description the export uses. |
| `tools/blender/prop_lib.py` | **The shared Blender helper for props** (the task props of #82 use it too): the materials (`materials`), a pack file's import with its face colours and the decimation (`import_pack`), one prop's export (`export_prop`). |
| `tools/blender/prop_build.py` | The entry the runner calls; a prop that fails is recorded in `build.json` with its error and the run goes on. |

Every builder works in the floor frame (x across L, y up to H, z across W, the front at +z) and takes the prop's roles
by position (`R[0]` the body, the last one usually the hardware); `finish` then moves it to its pivot. A pack prop's
files are stacked, turned by `yaw_deg`, scaled (`scale`, or fitted per axis with `stretch` to `size_m` or
`pack_size_m`), decimated to 85 % of the class's maximum when `decimate` is set, and painted; `extras` (`wall_mirror`,
`hood`) add procedural parts around it. Every GLB carries:

- one mesh `<id>` with UV0 (metres) and UV2 (one island per face, margin 2 % of the prop's size), sRGB vertex colours;
- its colliders `<id>_col<n>-convcolonly` (closed convex: a box, or the hull of the mesh);
- a fixture's `LightAnchor` empty at the centre of its emissive faces, where the map puts its light;
- materials `kit_<name>-vcol`; the emissive one glows in the prop's emissive paint (`bulb`, `tube`, `safelight`).
  Kit v2 (#86) packs plaster, wood and concrete into one `kit_set-vcol` material (the layer in the vertex colour's
  alpha): `prop_geom.lib_spec` carries the kit's `packs`, so props export the same materials as the kit pieces, and
  the build's `textures/` holds the packed `set_d.png`, `set_n0.png` and `set_n1.png` for Godot's set shader.

### The Godot check and the line-up sheets

After the GLB checks, `--build` (also with `--no-blender`) imports every prop into `godot/` as `prop_<id>` and runs
the kit's headless describer (`godot/check/kit.gd`) on them: the mesh, its triangles, UV2, sRGB vertex colours, one
static body per collider with a closed convex shape that stops a ray (the collider's points are read from the GLB),
the bounds against the size and the pivot (`floor`: the base's centre at the origin; `wall`: the back's bottom centre,
the prop in +Z; `ceiling`: the top's centre) and Y up, and the `LightAnchor` of a fixture where `build.json` put it
(no other prop has one). The describer's output goes to `<out>/godot.json`. `--no-godot` skips it.

`--sheets DIR` then shoots the line-up from an off-screen Godot window (`godot/props/lineup.gd`): the props in
library order cut into 4 sheets (`_props.sheet_plan`), on each sheet tallest first in rows of 7, each row beside a
1.8 m capsule and labelled with the ids, shot orthographic from the front-right and above, the kit's set shader on
the `kit_set` surfaces and a small warm light at each LightAnchor. Out: `DIR/lineup_<n>.png` (1280 px wide) and
`DIR/lineup.json` (the rows and the anchors Godot found). Review pictures only: the raw GLBs are not committed.
The line-up puts the fine pack's ShaderMaterial (`godot/props/prop_materials.gd`, the High tier) on the `kit_fine`
surfaces.

`--fine-compare DIR` (with `--build`) runs `godot/props/fine_check.gd` headless on the built props: per prop its
surfaces, images and texture bytes, that every `kit_fine` surface gets the same shared texture resources, and the
fine textures' memory per tier (BPTC with mipmaps); DIR holds GLBs to measure against (the kitchen pilot's), compared
prop by prop. Out: `<out>/fine_check.json`.

### The command

```
tools/run.sh props-library [--measure] [--table FILE] [--build [--batch N] [--only IDS] [--out DIR] [--no-blender]
                  [--no-godot] [--sheets DIR] [--fine-compare DIR]]
```

It checks the mapping file (no raw file needed); `--measure` reads every pack file in `<raw>/env` again (a pure
Python glTF reader: the accessors' bounds through the node transforms, the triangles) and compares them with the
record; `--table` writes the prop table as markdown. The tests are `tools/tests/test_props_library.py`,
`test_props_geom.py` and `test_props_godot.py`.
