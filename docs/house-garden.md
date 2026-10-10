# The garden and the greenhouse

Art #80 (map #73) lays out the garden (32 x 28 m at (46, 2)) and the greenhouse (16 x 12 m at (58, 6)) as data and a
seeded generator, beside #81a's plot (`docs/house-outdoor.md`) and #75a's layout engine (`docs/house.md`). Every
size, kind, paint and position is a reversible default of the house plan's questions (Q15 ground A, Q19 garden A: a
cottage garden): edit the data and rerun.

| File | What |
|---|---|
| `layouts/house/outdoor/garden.toml` | The garden's rect, the path network and its ends, the clearances, the fixed props, the scatter rules and seed, the greenhouse's glass roof, the herb route |
| `layouts/house/dressing/greenhouse.toml` | The greenhouse's props and fixtures (the house's dressing format: five herb beds, the herb board, bench, shelves, pots; strings and bulbs) |
| `layouts/house/outdoor/plot.toml` | Registers each garden path as a ground `[[zones]]` line of the same id, paint, line and width, so #81a paints it (the test compares them) |
| `tools/runner/house_garden.py` | Load, the checks, the scatter, the network and the route, the glass roof and its gables' rule, the plan, `garden.json` |
| `tools/runner/commands/garden.py` | The `garden` command |
| `tools/runner/house_garden_scene.py`, `godot/garden/proof.gd` | The Godot proof's request and scene (below, "The proof") |
| `tools/tests/test_house_garden_scene.py` | The proof's request: stand-ins replaced, everything placed, every path walked, the rays, the pictures |
| `tools/tests/test_house_garden.py` | The checks, the inventory counts, the seed, the clearances, the route, the roof, the rules on made-up cases |
| `props/plants.toml` | The plants (below): the dressing library's mapping format, built by `props-library --library props/plants.toml` |
| `tools/blender/plant_geom.py`, `plant_build.py` | The plant builders (pure Python, registered in `prop_geom`) and the build entry the mapping file's `script` names |
| `tools/tests/test_house_plants.py` | Every placed plant has a build, budgets and sizes, a tree's head room and trunk collider |

Coordinates are the design doc's: x east, y south, metres; Godot x = x, z = y.

## The command

```
tools/run.sh garden [--check] [--out DIR] [--proof [DIR]] [--kit DIR] [--roof-kit DIR] [--plants DIR]
```

Pure Python, a few seconds, no lock. `--check` only validates. Otherwise it writes into `--out` (default
`<raw>/house/80/build`) `garden.json` (the scatter's plants with kind, scale and yaw; the fixed props; the glass roof's
placements; the gables' gaps; the herb route; the counts) and `plan.png` (top-down, 20 px per metre: paths, the
greenhouse pale, blockers grey, trees, bushes green, flower beds pink, props magenta, lights orange, flat props lilac,
the herb route white). It fails on any problem. `--proof` then runs the Godot proof (below).

## The rules

- **Paths**: polylines 1.4 m wide (the plan's rule); no solid prop's footprint enters one (flat ones such as the
  stepping stones may, hung ones over 1.8 m too); every `[[ends]]` node (the kitchen side door, the greenhouse door,
  the drop-off, the outdoor stairs' entry) lies on the network, and the paths join into one.
- **Scatter**: candidates on one dense Poisson disc (0.4 m, seeded), shuffled per kind; kinds in file order (trees,
  flower beds, bushes) take candidates whose footprint circle (`radius`: a tree's trunk and low skirt, not its canopy)
  stays in the garden, `margin` off the paths' edges, the props, the greenhouse (plus its wall), the plot's holes and
  floors and the clearances (the drop-off's 1 m, the stairs' entry), `spacing` from its own kind. Each plant takes a
  kind (cycled: 3 fruit trees, 4 shrubs, 6 flowers), a scale and a yaw. Same seed, same garden.
- **Herb route** (design doc section 7: kitchen -> herb board -> bed -> kitchen, 94 m, 20.9 s at 4.5 m/s): its
  waypoints in straight segments, on the paths in the garden; its time within `tol_s` (1 s) of the doc's. Tonight
  95.0 m, 21.1 s.
- **Greenhouse roof**: kit v2's glass pieces (`glass_roof_eave_2m`, `glass_roof_2x2`, `glass_roof_ridge_2m`, glass
  gable triangles over bands) laid by `kit_geom.attic_roof`'s pattern on the glass walls' top (2.4 m); the ridge at
  2.4 + 6 x the kit's pitch. A bay's rafter is at its own start, so a gable is closed only on the slope whose bays begin
  there; the bay whose far end meets a gable (x 58 on the south slope, x 74 on the north) is the `_end` variant
  (`glass_roof_2x2_end`, `glass_roof_eave_2m_end`: `"+x"` in `ends`, a second rafter at its far end). `gable_gaps`
  lists each gable and slope with no rafter within 6 cm (a slit between the gable's top and the pane, open to a level
  ray); the test asserts none is left.

## The plants

`props/plants.toml` holds the plants the dressing library leaves to this package (`[skip]` in `props/library.toml`)
in the library's format (`docs/props.md`), one GLB per kind named `<scatter id>_<kind>` (`garden_tree_apple`,
`bush_lavender`, `flower_bed_tulip` ...) and `hedge`. Its `script = "plant_build.py"` makes `props-library` build it
with the plant builders; the library's checks, Godot import and line-up sheets run unchanged:

```
tools/run.sh props-library --library props/plants.toml --build --out D:/prime-art-raw/house/80/plants --sheets DIR
```

Solid clay lumps in the leaf paints (two tones a plant), no alpha cards: 430 to 980 triangles (vegetation 400 to
1,500). Trees keep the inventory's 3 x 3 x 7 m box: a trunk, three branches and a crown of blobs from `canopy_bottom`
(2.9 m, so 2.32 m at the garden's 0.8 scale) up, `crown` round (apple), upright (pear) or spread (plum), fruit on the
crown's lower half; they collide with the trunk only (`collision = "boxes"`: the builder's boxes), so the crown hangs
over the paths. Bushes are a mound with a `form` (boxwood mound, hydrangea heads, lavender spikes, currant berries);
flower beds a brick edge, soil, leaf mounds and 12 to 18 flowers (`form` cup, spike, disc or ball); the hedge a soft
core with leafy lumps and flat ends, so 2 m segments tile.

## The proof

`garden --proof [DIR]` (default `<raw>/review/house/80`; a few minutes, takes the heavy-run lock) rebuilds the plot
with the garden's paths (`house_outdoor.write` into `<raw>/house/80/outdoor`) and the house scenes
(`godot/import/house`, as `house` does), stages the kit v2 pieces (`--kit`, default `<raw>/kits/house/v2`; the
`glass_roof_*` pieces from `--roof-kit`, default `<raw>/house/80/kit`, until the end bays are in the kit's build on
main), the dressing's and the garden's props (`prop_dirs`; the hedge from `--plants`) and the plants
(`plant_<id>_<kind>`), imports them headless and runs `godot/garden/proof.gd` (it extends the outdoor proof,
`docs/house-outdoor.md`) in a window off-screen with the request of `house_garden_scene.py`:

- the scene: the outdoor proof's plot, sky, backdrop and fog without the grey stand-ins of the house, the garage, the
  terrace and the greenhouse; `house.tscn` (the greenhouse's glass walls and dressing); the glass roof from
  `garden.json`, the garden's props and the scatter's plants as the garden's layer: each GLB one MultiMesh per mesh
  over all its placements (a mesh's glass surfaces a MultiMesh of their own that casts no shadow), with each placement's colliders (a tree's trunk) as a body of its own; stand-in lamps at the post lamps, path lights and
  strings and two in the greenhouse (#83 owns the light design);
- the ray test: every roof mesh gets a trimesh collider on its own layer; rays go straight up from 2.45 m on a 0.5 m
  grid over the greenhouse and along both gables 5 cm in (each hit is that row's roof height), and level from the
  middle out through each gable every 0.25 m up to 10 cm under that height, which must hit within 0.35 m of the
  gable; a control up from outside must hit nothing;
- the walks: a 0.8 m capsule along every garden path and the herb route from the kitchen with the doors' leaves open;
- the pictures at dusk: the garden from the drop-off, the paths at 1.6 m, the greenhouse from the path and inside
  (the five beds and the board), under the west gable, the lawn, a top-down; `sheet.png` 1280 px wide in rows of
  three, each picture full size beside it; `proof.json` with the walks, the rays and each view's draw calls,
  primitives and objects, all and the garden layer's (the difference when the layer is hidden; shadow passes
  included). It fails on a walk that stops, a ray miss, an import error or a view where the garden layer takes 150
  draw calls or more (packages.md #80: under 150 with MultiMesh).

## Open

- The plants' look (crowns, forms, paints) is the engineer's: the line-up sheets go to review with the garden's.
- The garden's fixtures hang the greenhouse's bulbs and strings from the walls' top until the roof has tie beams.
