# The House map outside the house: plot, fence, street, stairs, sky

Art #81 (parts a and c; part b, the chill zone and the gazebo, follows) builds what lies outside the house's walls as
layout data and a generator, like the house itself (#75a, `docs/house.md`). Every size, paint and position is a
reversible default of the house plan's questions (Q4 gate widths, Q14 sky, Q15 ground, Q16 street): edit the data
and rerun.

| File | What |
|---|---|
| `layouts/house/outdoor/plot.toml` | The plot polygon, the ground's area and cell, the floor holes, the fence pieces and openings, the paints and zones, the kerb, the outdoor stairs, the props and the clearances |
| `layouts/house/outdoor/sky.toml` | The sky's colour stops, clouds and stars; the backdrop's centre, fog start and flats |
| `tools/runner/house_outdoor.py` | Load, plan (fence, stairs, props), the ground and flat meshes, a standard-library GLB writer, `write` |
| `tools/runner/house_sky.py` | A standard-library PNG writer and reader, periodic value noise, the sky panorama, the flats' textures |
| `tools/runner/commands/outdoor.py` | The `outdoor` command |
| `tools/tests/test_house_outdoor.py` | The fence closure, the holes, the stairs, the props, the sky's seam and colours, the GLB |

Coordinates are the design doc's (x east, y south, metres, origin at the plot's north-west corner); Godot's x = x,
z = y; a kit piece is placed by its pivot `at` (Godot x, height, z) and `yaw` (degrees about +Y), the layout
engine's convention.

## The command

```
tools/run.sh outdoor [--check] [--out DIR] [--layouts DIR]
```

Pure Python, about 5 s, no lock. `--check` only validates. Otherwise it writes into `--out` (default
`<raw>/house/81/build`): `outdoor.json` (the fence, stair and railing placements, the openings, the stairs' walk
points, the props, the lights, the summary), `outdoor.glb` (the meshes `ground-col`, `skirt`, `kerb-col`),
`backdrop.glb` (one ring mesh per flat, its textures embedded), `sky.png`, `flat_<id>.png` and `flat_<id>_emit.png`,
and `plan.png` (top-down, 14 px per metre: paints, holes grey, fence white, openings green, stairs blue, lights orange,
other props magenta). It fails on any problem.

## What it builds

- **Fence**: the plot's edges are walked so the outside is on each piece's +Z; each edge is filled with `fence_2m`
  modules (a `fence_1m` where a stretch is odd) round the openings; every module's post gets a `fence_post_cap`; the
  8 m gates stand between two `gate_post`s. The plan records each edge's spans, and `fence_openings` lists what is not
  fence: the test asserts that only the wicket's leaf (x 29.35 to 30.65) and the gates' leaves (x 60.1 to 67.9) are
  open on y 60 (Q4 default: wicket 2 m on x 30, gates 8 m on x 64). 280 m: 136 modules.
- **Ground**: one flat sheet at y 0 of 1 m cells over the plot and the street; each cell takes the paint of the last
  zone holding its centre (rects, or polylines with a width for worn tracks); its corners take the paint times value
  noise (`vary`, `scale_m`), with unshared corners, so zone edges stay sharp. No cell lies under a floor another
  package lays at y 0 (the house, the terrace, the garage, the greenhouse) or over the stairwell, so nothing
  z-fights (the test cross-checks the layout engine's floors when `layouts/house/ground.toml` is present). Paths, the
  driveway, the pavement and the street are paints of the same sheet. A coarse `skirt` in the `beyond` paint reaches
  out to the flats; the kerb is a box strip on the ground with a gap at the driveway. COLOR_0 holds sRGB paint and
  the material is `outdoor_ground-vcol` (the kit's `-vcol` rule, `docs/kit.md`); UV2 maps the area once for a bake.
  `-col` nodes get Godot's trimesh collision.
- **Outdoor stairs**: a U in the 4 x 4 m stairwell at (62, 29): `stairs_outdoor_half` from the entry edge down 1.6 m
  to `stairs_outdoor_landing` on the far edge, a second half flight back under the entry side down to the passage
  floor (-3.2); `railing_balcony_2m` on every hole edge but the entry, closed by a `railing_balcony_post`. `entry`
  `N` (from the garden, default) or `S` (from the garage's back door). The walk points go from the yard to the
  passage. The passage's ceiling needs the same hole in the layout engine's slab (#75a).
- **Props**: placements by id, centre and yaw with box sizes until the dressing library (#87) supplies them; refused
  when off the ground, across the fence, in a hole, in a clearance (the wicket's and gates' approaches, the path) or
  on another prop.
- **Sky**: a 1024 x 512 equirectangular panorama (row 0 the zenith): colour stops by elevation mixed in linear light
  (top #2d2a55, middle #7a4f86, a low narrow peach band #e0906c, a dark ground below), soft clouds from periodic value
  noise (no seam where u wraps; the test measures the wrap step against the inner steps), faint stars above 30
  degrees; no sun disc.
- **Backdrop**: at most 6 flats; here 3 rings round (40, 33): a tree line at 56 m, hills at 64 m, a haze at 70 m, each
  an RGBA silhouette (values deepening with height) and an emission texture of lit windows; the materials are unlit
  (`KHR_materials_unlit`), the tree line and hills alpha-masked, the haze blended. The scene that places them sets
  `gi_mode` disabled (the flats stay out of the bake) and the fog starts at 35 m.

## Open

The Godot import, the walks (the perimeter, the wicket, the gates, the stairs down to the passage) and the dusk
shots are #81's next steps; the house is a grey block there until the layout engine is on `main`.
