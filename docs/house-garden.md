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
| `tools/tests/test_house_garden.py` | The checks, the inventory counts, the seed, the clearances, the route, the roof, the rules on made-up cases |
| `props/plants.toml` | The plants (below): the dressing library's mapping format, built by `props-library --library props/plants.toml` |
| `tools/blender/plant_geom.py`, `plant_build.py` | The plant builders (pure Python, registered in `prop_geom`) and the build entry the mapping file's `script` names |
| `tools/tests/test_house_plants.py` | Every placed plant has a build, budgets and sizes, a tree's head room and trunk collider |

Coordinates are the design doc's: x east, y south, metres; Godot x = x, z = y.

## The command

```
tools/run.sh garden [--check] [--out DIR]
```

Pure Python, a few seconds, no lock. `--check` only validates. Otherwise it writes into `--out` (default
`<raw>/house/80/build`) `garden.json` (the scatter's plants with kind, scale and yaw; the fixed props; the glass roof's
placements; the gables' gaps; the herb route; the counts) and `plan.png` (top-down, 20 px per metre: paths, the
greenhouse pale, blockers grey, trees, bushes green, flower beds pink, props magenta, lights orange, flat props lilac,
the herb route white). It fails on any problem.

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

## Open

- The Godot proof's ray test (#80 step 3) confirms the closed gables on the colliders.
- The plants' look (crowns, forms, paints) is the engineer's: the line-up sheets go to review with the garden's.
- The garden's fixtures hang the greenhouse's bulbs and strings from the walls' top until the roof has tie beams.
