# The ship

The aliens' ship, a wide metal manta (art #263; prime-game `docs/design/estate-map.md` section 5a; the approved 2D in
prime-game-design `ideas/ship-components/2d/`, whose top view `plan-3.jpg` is the source of truth). Step 1 is the
**empty** ship: hull outside, the central hall, both wing corridors with their round tip rooms, one entrance (the
mouth ramp), no stations of any kind, worked out to release quality. Every object is its own model (one GLB),
placed by a placements file, so a piece the engineer dislikes is replaced alone.

## The engineer's rule

Build the inside from the numbers, not from the pictures' curvature: the pictures give the look, the plan gives the
arrangement, the numbers give the sizes. A gentle curve is fine only where the numbers still hold.

## Files

| Path | What | Owner after step 1 |
|---|---|---|
| `layouts/ship/ship.toml` | every number: rooms, heights, the ramp, the station spots, the hull sections, review light, walk, views | shared (additions only) |
| `layouts/ship/interior.toml` | the interior pieces and their placements | INTERIOR lane |
| `layouts/ship/exterior.toml` | the exterior pieces and their placements | EXTERIOR lane |
| `tools/runner/ship_layout.py` | load and check the layout (plain Python), the text plan | shared, frozen |
| `tools/runner/commands/ship.py` | the command: check, build, godot (core, frozen); shoot and walk | core shared; `shoot`, `walk_request`, `VIEW_SIZE`: EXTERIOR |
| `tools/blender/ship_lib.py` | the material library and mesh helpers | shared, frozen (additions only) |
| `tools/blender/ship_build.py` | the build harness: one GLB per piece, `build_report.json` | shared, frozen (additions only) |
| `tools/blender/ship_interior*.py` | the interior builders | INTERIOR lane |
| `tools/blender/ship_hull*.py` | the exterior builders | EXTERIOR lane |
| `godot/ship/` | `ship.gd`: assembly, headless check and walk, night shots, the walk-through frames | EXTERIOR lane |
| `tools/blender/ship_video.py` | encodes the walk-through MP4 under its size cap | EXTERIOR lane |
| `tools/tests/test_ship_*.py` | `test_ship_layout.py` (fast), `test_ship_build.py` (heavy: Blender) | either lane adds its own file |

Raw output (never in git): `<raw>/ship/v1/` with `pieces/` (GLBs, `build_report.json`, validator `reports/`),
`plan/` (`plan.txt`, `plan_vs_plan-3.png`), `shots/`, `walk/`, `logs/`, `notes/` (the workflow's handoff notes).

## Coordinates and numbers

Plan coordinates from the ship's centre in metres: x east, y south, h up from the ground. The Blender builders write
plan coordinates, the harness turns them into Blender's (x, -y, h), and the glTF (Y up) holds Godot's (x, h, y). A
placement `[piece, [x, y, h], yaw]` puts a piece's local origin there, turned by yaw degrees about the vertical
(Godot's rotation y); the tip-room pieces are built facing east and placed at yaw 180 for the west room.

| What | Number (ship.toml) | Why |
|---|---|---|
| Footprint | 26.1 x 13.9 m (hull and tip shells x; ramp foot -7.0 to nozzle tips 6.9 y) | 5a: about 26 x 14 |
| Deck | floor at h 1.0 on landing legs, slabs 0.25, walls 0.2 | the ramp meets the ground |
| Hall | circle r 3.4 at (0, 0); 3.4 m to the ceiling's rim, 4.0 m to its apex (faceted, 16 sides) | console (0, 1) with room round it |
| Mouth | x -1.3..1.3, y -4.6..-3.3, 2.6 m high | the only way in or out |
| Ramp | 2.6 m wide, hinge (0, -4.6) at the deck, foot (0, -7.0) on the ground: 22.6 deg | north at the centre |
| Corridors | y -1.25..1.25 (2.5 m), x 3.3..9.1 each side, 2.6 m high | 5a: about 2.5 m wide |
| Tip rooms | circles r 2.05 at (+-10.75, 0); 2.8 m to the rim, 3.2 m apex; window +-65 deg outward, sill 0.5, head 2.4 | panel (-10.5, 0), renewer (12, 0) |
| Stations (not built) | console (0, 1); vents (+-5, -1), sockets (+-8, -1) at the north corridor wall; panel (-10.5, 0); renewer (12, 0) | 5a |
| Player | capsule r 0.4, 1.8 m; every room keeps 0.5 m above it | the game's capsule |

The check holds: the footprint within 0.5 m; corridors 2.5 +- 0.1 m wide and over 4 m long; the tip rooms spanning
the width; clear heights over the capsule and margin; exactly one room with an exit, the ramp's hinge on its north
edge, the ramp as wide as the mouth and under 30 deg; no window is an exit; every room reachable from the hall and
linked rooms meeting; each station spot inside its room by its footprint (0.35 m; a wall unit 0.5 m deep stands
against its wall, within 0.6 m), 1.2 m free beside the corridor stations; every room's outer wall and every placed
piece inside the hull outline (the ramp may stand outside); no piece defined twice or never placed.

## Pieces

A piece is a builder function in its lane's module, `builder(args, layout) -> [parts]`; a part is
`ship_lib.part(name, verts, faces, material, solid)`. Solid parts are closed and get their normals recomputed outward;
open shells (the hull) orient their faces with `ship_lib.orient`. A piece with `collide = true` gets `-col` meshes, so
Godot's importer gives it a static body with its trimesh (one-sided: solids face out). Materials come only from
`ship_lib.MATERIALS` (a lane adds new entries, never changes one).

The hull is lofted from `[hull] core` and `plate` rows. The core covers the hall and corridors and is open at its
ends (inside the tip shells) and on its lower front over the mouth; the thin plates (top below the deck) run under
and round the tip rooms. Seen from inside, every hull face is a back face and is culled, so the rooms' own walls show.

## The interior kit

`layouts/ship/interior.toml` is GENERATED: `$PYTHON_BIN tools/blender/ship_interior_place.py` writes it from the
numbers at the top of `tools/blender/ship_interior.py` (`--check` compares; the fast test
`test_ship_interior.py` fails when the file is stale). Edit the numbers or the generator, never the file. The builders
use absolute heights (deck at h 1.0), so a placement's h is an offset (the clips' heights); a piece built at plan
angle 0 (its room toward -x) standing at angle a gets yaw -a; in a tip room turned by r, yaw r - a.

The numbers (step 1, art #263):
- hall: 16 facets, inner faces at apothem 3.4 (vertices at 3.467), rim 3.4 m, apex 4.0 m; the three openings
  (corridors east and west, the mouth north) are two facets wide, framed by a portal on their chord (x 3.203, half
  width 1.327) 0.15 m deep; floor: plain disc r 1.0, eight radial grate sectors r 1.1 to 2.5 between wedge spokes,
  the amber ring at r 2.58, solid plates to the walls; ceiling: 16 facet panels, ribs with cyan strips, the lamp
  ring (eight lamps) at r 1.25.
- corridors: one profile, 2.5 m wide, vertical to 1.45 m (cable channel 1.1 to 1.45 m), slanted in to 1.8 m wide at
  the 2.6 m ceiling; five modules of 1.117 m from x 3.353 (hall portal) to 8.936 (tip portal); arches at the first
  three module joints only, none near the vent and socket spots (x 5 and 8). The mouth passage is one module of
  1.247 m with an arch at the ramp hinge.
- tip rooms: polygon on radius 2.1, eight window segments over +-65 deg (sill 0.5, head 2.4), three wall facets a
  side, the corridor chord over +-37.6 deg (half width 1.281); rim 2.8 m, apex 3.2 m; radial grate floor with amber
  spokes; ribbed ceiling with cyan strips and a six-lamp ring.
- details: three crushed cup models (five placed, off every station spot), two scratch decal clusters (geometry
  0.6 mm proud of flat panel faces, eight placed).

Materials `int_*` (metallic 0.7 to 0.8 so the silver reads under lamps at night, not only in reflections): two silver
tones alternating per panel, a darker trim silver, grate and floor plate metal, dark recesses, emissive cyan, amber and
warm lamp, glass, three cable colours, the cup's red and white. No textures or UVs yet (seams, folds, bevels and
scratches are geometry).

The lane's own look check (no Godot): `ship_interior_render.py` in headless Blender through `runner.blender`
imports each GLB once, instances it at every placement, lights it with `[light]` and a moon and writes Eevee views
and `compare.png` (the 2D left, the render right). Interior pieces build with `ship --build --only <their ids>
--out <raw>/ship/v1/pieces_int`, then their GLBs and report entries are copied into `pieces/` (one build report for
the Godot run).

## Running it

```
tools/run.sh ship                       # the check and plan.txt
tools/run.sh ship --build               # one GLB per piece (about 1 min); --only ids
tools/run.sh ship --godot --walk DIR    # headless: sizes, colliders, the capsule walk into DIR/walk.json
tools/run.sh ship --shoot DIR           # off-screen night shots, compare_top.png (plan-3 left), sheet.png
```

Runs over 180 s go to the background with their log (CLAUDE.md, "Shell"). The whole of step 1 (the join, 2026-10-22):
105 pieces (70 interior, 35 exterior and clearing), 789 placements, 35558 triangles per piece set (about 126k placed
inside), glTF-Validator clean; `--godot`: Godot sizes equal Blender's, 88 colliders, the capsule walk reaches all 14
points; `--walk` adds the 1280x720 walk-through (about 90 s, under 15 MB); `--shoot` makes 14 views and their
compare sheets. Full run of `--godot --walk DIR --shoot DIR`: about 15 min.

## The exterior (EXTERIOR lane)

`tools/blender/ship_hull.py` builds the outside as a kit, each piece its own GLB (`layouts/ship/exterior.toml`): the
drum over the hall, the nose over the mouth, the nozzle mount, three wing sections per side, the knife-edge blades
along the wing chines, the tip pods and their window frames, the cockpit bubbles (collar, tinted glass, warm glow;
outside only, the hall's ceiling closes them off), the mouth frame and its amber lights, the ramp and its lights,
three nozzles with their cyan rings, eight landing legs, the cyan wing stripes; the clearing's ground, pines and
rocks. Every skin face is cut into plates of about 1.5 m, each with a 2.2 cm chamfer sinking 1.4 cm into a dark seam
(real bevels, not a texture).

| What | Number (plan m) | Why |
|---|---|---|
| Wing | belly h 0.6, crest h 4.0 (corridor ceilings top out at 3.85); half-width 1.6 by the corridors, 2.3 at the pods | hugs the corridors |
| Chines | lead (1.5, -6.2) -> (9.0, -3.0) -> (10.75, -2.5); trail (3.3, 5.0) -> (9.0, 2.9) -> (10.75, 2.5); h 1.4 -> 2.0 | the manta's raised tips |
| Blades | along each chine, 0.3 m sunk into the hull; lead reaches 0.75 m forward at the root, 0.95 mid-wing, 0 at x 10.2; trail 0.5 m back; 0.12 m thick to a 2 cm edge | the thin edge a 3.4 m deep wing cannot have |
| Pods | profile (r, h) (2.25, 0.6) (2.41, 1.5) (2.5, 2.0) (2.36, 3.4) (2.3, 4.0) (1.3, 4.45) (0, 4.6); window band h 1.5..3.4 within 65 deg | round the tip rooms; width 26.5 m |
| Drum | (3.85, 0.6) (3.95, 1.4) (3.95, 4.0) (3.9, 4.75) (3.0, 5.15) (1.5, 5.45) (0, 5.55) | over the hall's ceiling |
| Bubbles | (+-2.4, -3.55) at h 3.55, collar r 0.8 (8 cm outside the hall's wall) | outside only |
| Legs | (+-2.0, -2.9), (+-7.2, -1.2), (+-7.2, 1.3), (+-2.2, 3.9); 0.6 m to the belly | the floor on legs |
| Clearing | flat within 16 m (h 0), rolling beyond; pines 30..46 m, young pines and rocks 13..27 m, none within 3.5 m of an outside camera's line | seen through the tip windows |

Where the interior forces the silhouette thicker than the 2D: the wings are 3.4 m deep everywhere (belly 0.6 to crest
4.0) and the tips are 4.6 m round pods, against the turnaround's thin blades; the blades along the chines give back
the sharp edge, and the front view still reads as a long low body.

**Winding.** Plan coordinates are left-handed (x east, y south, h up); the harness's (x, -y, h) mirrors them, which
flips every winding set in plan coordinates with `ship_lib.orient`. `ship_hull.py` reverses its open (`solid=False`)
parts once at the end (`_outward`); a lane that orients open parts must do the same, or they come out inside-out
(Blender exports double-sided materials, so they still show, lit from the wrong side).

**The night look** (`godot/ship/ship.gd`): a star sky with a moon (`night_sky.gdshader`), moonlight (ship.toml
`[light]`), one shared triplanar metal shader by glTF material name (`metal.gdshader`: grain, fine seams, scratches,
grime), an OmniLight per 1.6 m cell of emissive surfaces (at most 96: the strips and lamps light the ship), a
ReflectionProbe per room, AgX, SSAO 0.6 / 1.5 (look_presets High), SSIL, glow, a thin blue fog.

**Review.** `ship --shoot DIR`: the views of exterior.toml `[shots]` (each with its 2D sheet, `compare_<view>.png`
with the sheet left) and ship.toml's others, the plan view against plan-3, `sheet.png`; it shoots whatever pieces
are built and names the missing ones. `ship --walk DIR`: the headless capsule walk (`check.json`), then the
walk-through `DIR/walkthrough.mp4`: a camera at eye height (1.65 m over the floor) through exterior.toml `[video]`
keys (cubic in time) from outside, up the ramp, the hall, both corridors and tip rooms and back out, 1280x720 at 24
fps in the off-screen window (ship.gd mode `video`, one PNG per frame), encoded by `tools/blender/ship_video.py`
(encode_clips.py's route at an average bit rate that fits `max_mb`, 15 MB: constant quality made 20 MB even at its lowest), then the frames are deleted;
`--no-video` skips it.

## The night look's numbers (the join step)

The first whole shots washed the inside out: the walls glowed beige-white and the cyan and amber strips rendered
white. Lowering the lamps, the ambient and the exposure barely changed it (look grid 1, `<raw>/ship/v1/grid/grid.png`):
the interior's metal (metallic 0.7) mirrored the emissive strips and lamps (glTF strength 8..12) through the rooms'
reflection probes. Grid 2 (`grid2.png`, variant H) fixed it; the numbers live in ship.toml `[light]` and ship.gd
reads them with `_lk(key, old value)`:

| Key | Value | Was |
|---|---|---|
| `ambient_energy` | 0.12 | 0.9 |
| `exposure` (AgX) | 1.0 | 1.2 |
| `emission_scale` (every emissive material) | 0.12 | 1 |
| `strip_light_scale` (the OmniLight per emissive cell, from the unscaled strength) | 1.5 | 1 |
| `strip_whiten` | 0 | 0.15 |
| `lamp_scale` (ship.toml's lamps) | 0.25 | 1 |
| `probe_intensity` (the windowless rooms' probes) | 0.15 | 1 |
| `int_value`, `int_rough_add` (the `int_silver_*` metals) | 0.55, +0.25 | 1, 0 |
| `hull_rough_add` (the hull silvers: the moonlit white plates) | +0.22 | 0 |

A look grid: a scratch script that loads the layout, overrides `[light]` per variant, calls `ship.shoot` on a few
views and tiles them with `house_bake_props.sheet` (`<raw>/ship/v1/logs/join_grid.py`).

## Open problems (after step 1)

- **The hull does not read as the manta yet** (the manager's note after the first shots): from the front and in the
  hero view it reads as a box body with a drum over the hall and two drum pods at the tips, not one continuous,
  faceted surface thinning toward sharp swept tips (turnaround.jpg, hero.jpg). The interior's numbers stay; the
  skin around them needs a rebuild: one grid of 3 or 4 silhouette variants (front, side, top, three-quarter), then
  the chosen one detailed. Not a small change; the next step's first job.
- The hall is still the brightest room (its lamp ring's cells); the corridors and tip rooms read at night.
- The pines are layered cones; the ground is flat and empty (no grass tint, needles, dirt by the ramp).
- The nozzles sit flush in a box mount (out_back); the ramp reads dark from the hero view.
- The interior has no UVs: the brushed grain is geometry and the triplanar shader only on the hull's metals.
- Triangles: the grates are about 60% of the 126k placed inside; measure with `bench` before the game takes it.
