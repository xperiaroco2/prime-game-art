# Modular kits: the House kit

The House map (map request #73) is assembled from modular shell pieces: walls, floors, roofs, stairs, railings,
fences, gates and glass walls on one grid. Art #74 built the first kit, the **House kit**, as repo code: a spec
(`kits/house.json`), a pure-Python geometry module, a headless Blender builder, and the `kit` command that builds one
GLB per piece and checks every piece in glTF-Validator and Godot. Art #86 made **version 2** (below): 105 pieces
(v1's 71 with their ids kept, 34 more), the pitched and glass roofs, the porch, the pillar, the chimney, the gazebo,
and look.md section 5's material plan (one `set` material for plaster, wood and concrete). The GLBs stay in the raw
folder (`D:/prime-art-raw/kits/house/v<version>/`; v1 is kept untouched in `v1/`, v2 builds into `v2/`) until the
engineer approves the kit's look on a review page; then they come into the repo with their manifests.

## The command

```
tools/run.sh kit [--spec kits/house.json] [--out DIR] [--only id,...] [--no-build] [--no-godot] [--proof DIR]
```

| Option | What it does |
|---|---|
| (none) | Checks the spec (with the seam and closure checks), builds every piece in headless Blender (`tools/blender/kit_build.py`), checks every GLB and imports them all into `godot/` headless (`godot/check/kit.gd`); about 5 minutes, plus any wait for the heavy-run lock |
| `--out` | Output folder (default `<raw>/kits/<kit>/v<version>`, now `D:/prime-art-raw/kits/house/v2`) |
| `--only` | Only these pieces (`--proof` needs the whole kit) |
| `--no-build` | Checks the GLBs already in `--out` (about 1 minute with Godot) |
| `--no-godot` | Skips the Godot import (and the proof) |
| `--proof DIR` | Also shows every piece in a line-up by kind and assembles a test room, a corridor, a stair flight, the porch, an attic roof and the gazebo in an off-screen Godot window, walks them, casts rays up the roofs and shoots them into `DIR` (below) |

Run it in the background (`> tools/out/kit/run.log 2>&1; echo "exit=$?" >> ...`, then `tools/run.sh wait`). It
writes into `--out`: `<id>.glb` per piece, `textures/` (the detail and normal PNGs), `build.json` (what Blender
exported), `reports/<id>.json` (glTF-Validator), `godot.json` (Godot's measures) and the piece table `pieces.md` /
`pieces.json` (triangles against the budget, size, colliders, UV2 density, nodes). It fails when any check finds a
problem.

**UV2 density** (the table's "UV2 per m" column, `uv2_per_m`): the UV2 units per metre of a piece's smallest-scaled
mesh. A LightmapGI bake gives it `lightmap_size_hint x uv2_per_m` texels per metre, so the hint for 10 texels/m is
`10 / uv2_per_m` (the number in brackets). No bake runs here (it is editor-only); the map's bake (#83a) sets the hints
and must check that Godot's "static lightmaps" import keeps the kit's UV2 rather than re-unwrapping it.

## The spec: `kits/house.json`

- `grid`: the engineer's grid of #73: whole metres, 1 m and 2 m wall modules, floor to floor 3.2 m (a 0.2 m slab and
  a 3.0 m storey wall), attic knee walls 2.2 m, walls 0.2 m thick, interior doors 1.4 x 2.15 m, windows 1.0 x 1.2 m
  on a 0.9 m sill, the 8 m gates, a 0.3 m roof slab, a 1.0 m parapet, gables at 0.7 m rise per metre (35 deg), glass
  walls 2.4 m, the fence 1.8 m. A size that does not work is proposed to the engineer in the PR; it is never changed
  silently. v2 adds `pitched_roof_t_m` (0.2). `gable_rise_per_m` is the one pitch number every gable, pitched and
  glass roof piece reads (`kit_geom.pitch`): changing it (Q2 of the house plan's questions) rebuilds them all.
- `budget_tris`: triangles per kind of piece (wall 400, corner 60, floor 120, roof 200, stairs 2500, ladder 600,
  railing 1500, fence 1200, gate 4000, glass 600, garage 600; v2: pillar 60, porch 400, chimney 200, trim 120,
  gazebo 1200). Version 2's 105 pieces hold 4,194 triangles. Version 1's 71 pieces hold 3,772 triangles in all; the
  most is the driveway gates (570). The locations' minimum-spec budgets (`docs/research/2026-10-06-locations.md`, "Godot
  budgets") allow 400k visible world triangles and 6 world materials: a whole storey of these pieces stays a small
  part of the triangles, and the kit uses 5 materials.
- `materials`: five (plaster, wood, concrete, metal, glass). The first three take a detail texture made from an
  ambientCG CC0 map (`sources/ambientcg_materials_2k.toml`): grey, linear mean 0.92, 512 px, with its normal map.
  A material with `pack` is exported as its pack (below); v2 exports three materials: `set`, metal, glass.
- `packs`: `set` packs `layers` plaster, wood and concrete into one material (look.md section 5).
- `roles`: the paints, each a material and a hex colour; the house lab's look v1 round 3 (#41: wall `#3a6264`,
  exterior `#4f6a72`, ceiling `#3c4652`, trims `#3d2a1e`, boards `#534941` ...).
- `pieces`: one entry per piece: `id`, `type` (the builder), `kind` (the budget) and its sizes.

## Conventions

- **Axes and pivot**: Godot's (metres, +Y up). A wall runs along +X from its pivot, the grid node, centred on the grid
  line, its exterior side at +Z; a floor spans +X/+Z from the pivot with its top at y 0; a flight climbs along +X.
  Pieces placed on grid nodes meet without gaps; faces that would lie in one plane where pieces meet are left out
  (the corner and end pieces close a wall run).
- **Leaves** (the wicket, the driveway gates, the greenhouse door, the garage door) are separate mesh nodes with their
  hinge as origin, their collider parented to them, so the game can swing them.
- **Collision**: every piece has simple convex colliders, nodes named `<id>_col<k>-convcolonly` (Godot imports each
  as a `StaticBody3D` with a `ConvexPolygonShape3D` and no mesh); glass panes are `<id>_glass<k>-convcolonly`, a
  separate group the game may keep out of line-of-sight rays. A flight's walkable collider is a ramp through its
  nosings.
- **UV0**: box projection in metres (one texture tile per metre). **UV2** (the lightmap UV, `TEXCOORD_1`): one island
  per face, shelf-packed into the unit square at one scale with a margin, so LightmapGI can bake the pieces.

## Version 2 conventions (art #86)

- **Pitched roofs**: the attic's roof is panels (`roof_pitched_2x2`, `_2x1`), the eave, verges, corners, the ridge and
  its ends. Their pivot is the eave wall's grid node at the knee wall's top; the panels climb `gable_rise_per_m` per
  metre along +Z; the ridge's pivot is the gables' apex (y = rise x run). The roof's underside sits `rise x 0.1 + 0.02`
  under the gables' top line, so the slab covers the knee and the gable tops. `kit_geom.attic_roof(spec, x, z)` lists
  the placements (id, degrees about +Y, offset) for a span; the far slope is the near one turned 180 degrees. The glass
  roof (`glass_roof_*`, `glass_gable_*`) follows the same pivots on the glass walls' top.
- **Gazebo**: six 60-degree deck sectors round its centre (sector 0 `gazebo_sector_open`, the entrance), six roof
  sectors and the finial, all pivoted at the centre; `kit_geom.gazebo()` lists them.
- **Porch** (`porch_2x2`): x along the exterior wall from its grid node, out along +Z from the wall's face; its
  `sockets.lamp` is where a porch lamp hangs. **Pillar** (`pillar_concrete`, 0.4 m): centred on its grid node.
  **Chimney**, **cornice bracket**, **post cap**, **gate post**, **slab edges** (`slab_edge_2m/1m`, closing a slab's free
  edge such as a stairwell's) and the glass nodes (`glass_corner/end/post`) are documented in their builders.

## Materials: the `set` pack and its shader (v2)

Plaster, wood and concrete share one material, `kit_set-vcol` (look.md section 5: fewer materials, one shader). The
vertex colour's alpha picks the layer: 1.0 plaster, 0.75 wood, 0.5 concrete (`kit_geom.layer_alpha`); Blender
exports `COLOR_0` as VEC4 with that alpha. `kit_build.py` exports the pack plain white and writes three textures:
`textures/set_d.png` (RGB: the three layers' grey detail, sRGB), `set_n0.png` (RG: plaster's normal XY, BA: wood's)
and `set_n1.png` (RG: concrete's). In Godot, `godot/kit/kit_set.gdshader` reads them: layer = round((1 - alpha) x 4),
albedo = the linearised paint x the layer's detail channel, the layer's normal XY (Godot rebuilds Z), and per-layer
roughness and normal strength from the spec's materials. It is opaque. `godot/kit/kit_materials.gd` builds the
ShaderMaterial (`make(textures_dir, {roughness, normal_strength})`) and puts it on every surface whose material is
named `kit_set` (`apply(node, mat)`); the proof and the layout engine (#75a) use it. Without it the pack shows plain
paint (Godot's StandardMaterial3D from the GLB). Metal and glass stay their own materials.

## Paint: vertex colours and the `-vcol` suffix

The paint is the vertex colour (`COLOR_0`), multiplied into the material's white-times-detail base colour, so five
materials serve every paint. Godot 4.7.2's glTF importer sets a material's "vertex colour as albedo" only after it
has handled the primitive's material (`gltf_document.cpp`: the flag at line 1632 comes after the material at line
1460), so the first primitive of each mesh drew without its paint (Godot's master has fixed the order). The kit works
around it: each material is named `kit_<name>-vcol`; Godot's scene importer strips the suffix and turns on vertex
colour as albedo **and** sRGB vertex colours for that material. COLOR_0 therefore holds **sRGB-encoded** paint
(`kit_geom.role_colour`: the role's hex, divided in linear by the detail texture's mean, encoded back), not the
glTF spec's linear colours: Godot shows the paint right; other viewers show it lighter.

## The checks

1. **Spec** (`kit_geom.check_spec`, `check_piece`): the grid adds up, ids are unique, sizes are whole metres and wall
   lengths a module, every piece is within its budget, has colliders that are not flat, and UV2 on every face inside
   0..1; its extent fits its module.
2. **GLB** (`_kit.check_glb`): every mesh node has `TEXCOORD_0`, `TEXCOORD_1`, `COLOR_0` and `NORMAL`, every collider
   its node, at most the kit's materials, each with the `-vcol` suffix; glTF-Validator has no errors. Its 98 warnings
   are all `MESH_PRIMITIVE_GENERATED_TANGENT_SPACE`: the kit exports no tangents and Godot makes them on import
   (`meshes/ensure_tangents`); harmless.
3. **Godot** (`godot/check/kit.gd`, `_kit.evaluate`): the imported bounds equal the spec's within 2 mm (size, pivot,
   Y up), the triangle count is the spec's, every surface has UV2 and paints with its sRGB vertex colours, one static
   body with a closed convex shape per collider, and one ray per collider, from 0.5 m outside along its thinnest axis
   to its centre, hits it.
4. **Seams and closure** (v2; run when `kit` builds every piece, `kit_geom.seam_problems`, `closure_problems`,
   `gazebo_problems`): a copy of every run, floor and roof module snapped onto its neighbour leaves no faces back to
   back (coplanar overlap); the attic roof over 20 x 14 m closes (a ray up from every 0.25 m point inside the walls
   hits it) and its underside stays under the gables' top; the gazebo's roof closes over its deck.

## The proof: `--proof DIR`

`godot/kit/proof.gd` runs in a window placed off-screen (`--position -30000,-30000`, 1600 x 900, the Dummy audio
driver), never on screen and never headless. It instances the pieces into a test house: a 6 x 4 m room (x 0..6,
z 0..4) with exterior walls and windows south and east and an interior wall with the 1.4 m door at z 4, a 2 m
corridor (z 4..6), `stairs_main` from x 6 to 12 up to a landing (x 12..16) at 3.2 m, the upper storey's walls and
the ceilings, four warm omni lamps (the house lab's lamp colour c2) and the house lab r3_v1 environment (filmic
tonemap, exposure 1.5, saturation 1.35, SSAO, the sky colours, depth fog). It uses SDFGI instead of a baked
LightmapGI (a bake cannot run from a script), so it checks the real-time look only.

Walks: a capsule of radius 0.4 m (a player carrying a package, 0.8 m wide) walks from the room through the door,
along the corridor and up the flight to the landing and must arrive; a control of radius 0.75 m (1.5 m wide) must
stop at the door. Shots at eye height 1.6 m: `room_corner`, `room_window`, `room_door`, `corridor`, `stairs_up`,
`stairs_down`.

v2 adds: the **line-up** by kind (`_kit.LINEUP_GROUPS`), one orthographic frame per group, `lineup_<n>.png`: walls;
corners, ends, pillars, chimney and trim; floors (from above); roofs (50 degrees up, so the slopes show); glass; stairs,
ladder and railings; fences, gates, garage and porch; the gazebo; each piece with its id, a 5 m bar of 1 m blocks and
the clay man for scale (`<raw>/clay-42a/export/m1/m1.glb`, loaded at run time; a 1.8 m capsule without it). The
**assemblies** (west of the house): `porch` (the porch on a 6 m exterior wall), `attic_out` and `attic_in` (knee walls,
gables and the pitched roof of `attic_roof(spec, 4, 4)` over a 4 x 4 m floor) and `gazebo`. **Rays**: from 1 m above
the floor, every 0.25 m, straight up through the attic and the gazebo, must hit their roofs. All pieces use the `set`
shader. `sheet.png` (1280 px wide, rows of three): the eight line-up frames, the four assemblies, `room_corner`,
`corridor` and `stairs_up`; `proof.json` holds the walks and the rays.
