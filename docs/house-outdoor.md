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
tools/run.sh outdoor [--check] [--out DIR] [--layouts DIR] [--proof [DIR]] [--kit DIR]
```

Pure Python, about 5 s, no lock. `--check` only validates. Otherwise it writes into `--out` (default
`<raw>/house/81/build`): `outdoor.json` (the fence, stair and railing placements, the openings, the stairs' walk
points, the props, the lights, the summary), `outdoor.glb` (the meshes `ground-col`, `skirt`, `kerb-col`),
`backdrop.glb` (one ring mesh per flat, its textures embedded), `sky.png`, `flat_<id>.png`,
and `plan.png` (top-down, 14 px per metre: paints, holes grey, fence white, openings green, stairs blue, lights orange,
other props magenta). It fails on any problem.

`--proof` (Godot, a few minutes, takes the heavy-run lock) then checks the build in Godot; see "The proof".

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
  driveway, the pavement and the street are paints of the same sheet; the garden's paths are `[[zones]]` lines
  registered from `layouts/house/outdoor/garden.toml` (#80, `docs/house-garden.md`). A coarse `skirt` in the `beyond` paint reaches
  out to the flats; the kerb is a box strip on the ground with a gap at the driveway. COLOR_0 holds sRGB paint and
  the material is `outdoor_ground-vcol` (the kit's `-vcol` rule, `docs/kit.md`); UV2 maps the area once for a bake.
  `-col` nodes get Godot's trimesh collision.
- **Outdoor stairs**: a U in the 4 x 4 m stairwell: `stairs_outdoor_half` from the entry edge down 1.6 m
  to `stairs_outdoor_landing` on the far edge, a second half flight back under the entry side down to the passage
  floor (-3.2); `railing_balcony_2m` on every hole edge but the entry, closed by a `railing_balcony_post`. The
  stairwell's rect and `entry` (`N` from the garden or `S` from the garage's back door) have one owner, the house
  layout's `layouts/house/ground.toml` (the hole and the flights `outdoor_stairs` that the house walk and the
  basement passage use, art #78): `house_outdoor.load` reads the hole's rect and the upper flight's `climb`; `[stairs]`
  in `plot.toml` keeps the drop and the pieces. Today (62, 28), entered from the south (`docs/house.md`, the
  basement). The walk points go from the entry to the passage; the scene's stand-in pit walls and its two stairs
  views follow the entry.
- **Props**: placements by id, centre and yaw with box sizes until the dressing library (#87) supplies them; refused
  when off the ground, across the fence, in a hole, in a clearance (the wicket's and gates' approaches, the path) or
  on another prop.
- **Sky**: a 1024 x 512 equirectangular panorama (row 0 the zenith): colour stops by elevation mixed in linear light
  (top #2d2a55, middle #7a4f86, a low narrow peach band #e0906c, a dark ground below), soft clouds from periodic value
  noise (no seam where u wraps; the test measures the wrap step against the inner steps), faint stars above 30
  degrees; no sun disc.
- **Backdrop**: at most 6 flats; here 3 rings round (40, 33): a tree line at 56 m, hills at 64 m, a haze at 70 m, each
  an RGBA silhouette (values deepening with height) with its lit windows painted in, opaque (an emission texture on
  the unlit material showed no window in Godot's pictures); the materials are unlit
  (`KHR_materials_unlit`), the tree line and hills alpha-masked, the haze blended. The scene that places them sets
  `gi_mode` disabled (the flats stay out of the bake) and the fog starts at 35 m.

## The proof

`outdoor --proof [DIR]` (default `<raw>/review/house/81`) runs glTF-Validator on `outdoor.glb` and `backdrop.glb`
(reports beside them, `<name>.validator.json`), stages them and the house kit's pieces it places (`--kit`, default
`<raw>/kits/house/v<version>`, now v3, as `res://import/kit_<id>.glb`) into `godot/import/`, imports them headless and runs
`godot/outdoor/proof.gd` in a window off-screen with the request of `tools/runner/house_outdoor_scene.py`:

- the scene: the placed fence, gates, caps, stairs and rails with the kit's `set` pack (`godot/kit/kit_materials.gd`),
  the ground and kerb with their `-col` colliders, the flats with `gi_mode` disabled and no shadows, `sky.png` as a
  `PanoramaSkyMaterial`, depth fog from the backdrop's `fog_start_m` to 180 m in the sky's mean horizon colour, warm
  stand-in lamps at the lit props (#83 owns the light design), the props as boxes of their `size`, and grey stand-in
  blocks for the house, the terrace slab, the garage and the greenhouse; under the stairs a temporary pad at -3.2 m
  (8 x 6 m at (58, 28)) and the stairwell's walls with a lintel over the passage door, until the layout engine (#75a)
  builds the passage;
- the walks: a capsule 0.8 m wide and 1.8 m tall with gravity walks round the inside of the fence (1 m in), through the
  wicket and the gates onto the pavement and down the outdoor stairs onto the pad; four controls walk out across the
  fence away from the openings and must stop;
- the pictures: 360-degree strips (four 90-degree views) from the yard and the street, the street, the wicket, the gates
  from outside and inside, the stairs from the garden and from the passage, two lookouts 9 m up for the seam between
  the skirt and the flats, and an aerial view; `sheet.png` 1280 px wide (the strips, then rows of three), each picture
  full size beside it, and `proof.json` (the walks, and per picture its lit-window pixels: every 2nd pixel of every
  2nd row that changes when the flats' textures swap to copies with the windows painted dark).

It fails on a validator error, a Godot import error, a walk that ends the wrong way or a lookout without a lit window.

## Open

The house, the terrace, the garage and the greenhouse are grey blocks in the proof until the layout engine (#75a) and
their packages are on `main`; then the proof places their builds and drops the pad under the stairs.
