# The House dressing library

Art #87 (map request #73) makes one shared library of generic props (furniture, dressing, light fixtures, outdoor
things) so that every room package places furniture instead of making it. Task props (#82a, #82b), the car and its
lift (#79), vegetation (#80), the gazebo (#81b) and kit pieces are made elsewhere; `[skip]` in the mapping file names
who makes each. The plan is `D:/prime-art-raw/research/2026-10-10-house-plan/` (`props.md`, `inventory.md` §9,
`look.md` §5 and §6). The GLBs stay in the raw folder (`D:/prime-art-raw/props/library/v1/`) until the engineer
approves the look on a review page; then they come into the repo under `assets/prop/<id>/` with their manifests.

## The mapping file: `props/library.toml`

The library is data: a paint, a size, a source file or a shape changes without a code change.

| Field | What |
|---|---|
| `[materials]` | Library material name to the kit's material (`kits/house.json`). The **one place** that names materials: when kit v2 (#86) merges plaster, wood and concrete into one `set` material, re-point the lines here. At most `max_materials` (6) targets; a target the kit lacks must be in `new_materials` (`emissive`). |
| `[budgets]` | Triangles by class, `[min, max]` (`look.md` §6): `dressing` 150 to 600, `room` 400 to 1,500, `fixture` 100 to 400, `vehicle` 400 to 3,000 (the parked cars). |
| `[roles]` | The props' paints: a library material and an sRGB hex (the D1 palette, `look.md` §7). A prop may also name the kit's roles (`trim`, `fence`, `lino`, `glass` ...). |
| `[skip]` | Inventory ids this library does not make, with the package that does. |
| `[[prop]]` | One prop: `id`, `name`, `class`, `size_m` (the inventory's L x W x H: along X, along Z, up), `count` (placements), `route` (`pack` or `proc`), `roles`, `pivot`, `collision`. |
| pack props | `source` (a `sources/<id>.toml` record), `files` (relative to `<raw>/env`; several are stacked, the next on top of the one before), `src_size` and `src_triangles` (measured from the glTF), `yaw_deg` (a turn about +Y that brings the front to +Z), `scale` (uniform), `stretch` (fit the box per axis), `decimate` (the source is over the class's budget), `pack_size_m` (the part the pack supplies when `extras` add the rest), `extras` (procedural additions such as a wall mirror). |
| proc props | `shape` (a builder) and `params`. Generic builders cover most furniture: `cabinet` (doors, drawers, plinth or legs, top, cornice, sink), `table` (legs, top, shelf), `shelving` (shelves, items), `bench` (back, slats, cushion); the rest are one builder per prop. |

## Conventions

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

## Scale: why many props are procedural

The plan expected about 80 pack props. Fitting the packs to the inventory's real sizes showed that the rounded toy
families (KayKit, Tiny Treats) are chunky: their counters, cabinets, wardrobes and benches are low and deep, and a
fit distorts them by more than 1.5 times between axes. Simple boxy furniture is cheap and exact as a procedural
build in the kit's materials, so version 1 has 32 pack props and 77 procedural ones. The check (`_props.check`):

- without `stretch`, the uniformly scaled source is within 10 % of the inventory size on every axis;
- with `stretch`, the largest axis factor over the smallest is at most 1.5;
- a source over its class's budget needs `decimate = true`; every source is CC0 with `public_repo_ok = true`.

## The command

```
tools/run.sh props [--measure] [--table FILE]
```

It checks the mapping file (no raw file needed); `--measure` reads every pack file in `<raw>/env` again (a pure
Python glTF reader: the accessors' bounds through the node transforms, the triangles) and compares them with the
record; `--table` writes the prop table as markdown. The tests are `tools/tests/test_props_library.py`.
