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
  there: `gable_gaps` lists each gable and slope with no rafter within 6 cm (a slit between the gable's top and the
  pane, open to a level ray). Tonight both gables have one open slope (x 58 south, x 74 north): see Open.

## Open

- The gables' slits (above): kit v2 needs a closing rafter (for instance a `glass_roof_2x2` variant with a rafter at
  both ends, or a rafter piece); the Godot proof's ray test (#80 step 2/3) confirms it on the colliders.
- The plants (3 tree species, 4 shrubs, 6 flowers, the hedge) are boxes of their `size` until this package's builder
  makes them; a tree's canopy must start over 2.2 m, as it may hang over a path.
- The garden's fixtures hang the greenhouse's bulbs and strings from the walls' top until the roof has tie beams.
