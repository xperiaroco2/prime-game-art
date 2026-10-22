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

The worked geometry (inside lane, step 2, from hall_in-3, corridor.jpg and materials-3): the hall's wall facets fold
up to a raised diamond (`pyramid`, ridge 0.1 m proud) inside four chamfered corner plates, the upper panel split on its
diagonal; the hall's plain vertices and the tip rooms' carry cable trunks (`trunk`: posts 0.2 m proud, 0.52 m wide,
with `trunk_cables`, five cables r 18..32 mm, and bolted `trunk_clip` frames); the corridors' rib frames stand 0.18 m
into the corridor (2.14 m clear at the floor) with a stepped inner rim carrying the cyan strip; the cable bays at
1.1..1.45 m are 0.24 m deep with four cables r 26..32 mm behind bolted clip frames; grate modules sit in a bevelled
5 cm rim with hex bolts; the amber floor strips are 0.7 m (corridors) with a frosted halo (`int_halo`, glows, lights
nothing), the hall's ring 0.12 m wide; the tip windows' mullions are 0.17 m bevelled frames, sill 0.2 m, header 0.2 m.

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

`tools/blender/ship_hull.py`, `ship_hull_skin.py` and `ship_hull_detail.py` build the outside as a kit, each piece
its own GLB (`layouts/ship/exterior.toml`): the skin (body, three wing sections and the tip fairing per side, each with
a darker underside), the cyan wing stripes, lead blades and seam lines, the inset hatches with their scratches, the
tip windows' frames, the cockpit canopies (fairing, tinted glass, warm glow; outside only, the hall's ceiling closes
them off), the mouth frame and its amber lights, the ramp and its edge strips, three long nozzle pods with their cyan
rings and the middle pod's housing, eight landing legs and twelve amber ground lamps; the clearing's ground, pines
and rocks. Every skin face is cut into plates of about 1.5 m, each with a 2.2 cm chamfer sinking 1.4 cm into a dark
seam (real bevels, not a texture).

### The hull skin (hull lane, step 1)

One continuous faceted surface from the centre to the tips (`ship_hull_skin.py`; the old drum, nose, wing, pod,
blade, nozzle-mount and bubble builders were retired in step 2). The half-span is lofted through sections across x, each the
same loop of 14 (y, h) points (lead edge, two upper-front slope points, the eave, two ridge points, the rear eave, two
upper-rear points, trail edge, lower rear, two belly points, lower front), so the facets run as long creases from the
body to the tips; past the tip room's centre (x 10.75) the tip fairing is a revolve whose +-90 deg profiles equal the
loft's last section. The rooms give the inside: `clearance()` lists room points outside a section (the hall's wall at
h 4.4, the corridors' top corners (1.45, 3.85), the tip room's wall top (r 2.25, 3.8) and dome), and the fast test
keeps it empty for every variant.

The silhouette grid (`tools/blender/ship_hull_grid.py`, headless Workbench with the rooms as an orange ghost): the
variants of `VARIANTS` in front, side, top and three-quarter views under the approved 2D and the Meshy silhouette
reference (batch `2026-10-22-ship-hull-ref`, 20 credits, a multi-image-to-3D of turnaround.jpg's four views, scaled to
a 26.5 m span; never shipped). Variant F was picked (`<raw>/ship/v1/grid/hull2/grid.png`, rows 2D, ref, B, D, E, F).

| What | Number (plan m), variant F | Why |
|---|---|---|
| Lead edge | (1.5, -6.3) -> (4.0, -5.5) -> (8.0, -4.1) -> (10.75, -3.0); h 1.1 -> 1.2 at x 6 -> 1.38 | the blades well ahead of the corridor ridge |
| Trail edge | (0, 5.0) -> (3.0, 5.15) -> (8.0, 5.0) -> (10.75, 4.9); the body's stern edge h 2.45 | the blades well behind it |
| Swept tip | round the tip centre (dx, dy): (2.1, -2.2), (2.47, -0.6), (2.48, 5.9), (1.2, 5.4); edge h 1.38 (under the sill) | turnaround top's tips swept back, outside the window's 65 deg |
| Ridge | spine h 6.05 over the hall's middle (x < 0.9), the hall's eave r 3.72 at h 4.75, the wing's eave 0.12 m outside the corridor walls at h 3.95 (4.75 at the hall), ridge 4.15, the tip fairing's eave (2.28, 4.02) and crown 4.42 | sloping down outward; the rooms inside |
| Belly | keel h 0.35 under the hall and the mouth, 0.6 under the wings | the belly slopes up toward the edges |
| Mouth | the opening's face cut between x -1.3 and 1.3 (h 0.95..3.65 at y -4.6) under a brow 0.55 m forward at h 3.92 | a notched recess in a low nose |
| Window | the fairing's band r 2.41, h 1.5..3.4 within 65 deg of the tip's axis left open | the frame and the interior's glass fill it |
| Bubbles | (+-1.9, -3.75) at h 4.15, on the forward body over the mouth | two eyes over the mouth |
| Footprint | 26.46 x 13.90 m (`ship --check`); ship.toml [hull] rows from `ship_hull_skin.outline()` | the numbers hold; nothing bent |

Where the interior forces the silhouette thicker than the 2D: scaled to the same span, the Meshy reference's wing is
about 1 m thick and its body about 2.5 m, while the rooms need 0.6 to 4.4 m at the tips (tip room apex 4.2 over a
1.0 m deck) and to 5.0 under the hall's apex. The skin slopes and thins everywhere the rooms allow, but from the front
the wings stay a thick wedge with the tip fairings at their ends.

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

### The hull's details (hull lane, step 2)

`ship_hull_detail.py`; every detail reads the skin's top (`skin_h`: the loop's upper points of the two loft stations
round |x|, linear between them as the loft's faces are), so it follows the skin if the variant changes.
`tools/blender/ship_hull_look.py` is the cheap check of shape: the exterior's built pieces in headless Workbench, the
2D crops over front, side, back and top, then a three-quarter and close-ups of a canopy, the pods and a leg (one
1280 px sheet; log `LOOK sheet`).

| Detail | Numbers (plan metres) |
|---|---|
| Two tones | the skin loop's faces 9..13 (trail edge, belly, lower lead facet) in `ext_silver_c`/`leg_metal`; the tip's profile faces 0..2 likewise |
| Canopies | glass ellipse 1.1 x 1.4 at (+-2.5, -2.7), either side of the spine, 0.95 high, four frame ribs; a deck plane fitted to the skin (least squares in x and y, tilt cap 34 deg, raised 0.05 over the skin under the glass); the fairing's teardrop 1.14x, stretched 1.6x backward, collar 0.06 into the skin; mean collar 0.43 m (2.2 m with a deck flat across x: two barrels from the front) |
| Nozzle pods | outer r 1.05 at (+-2.75, h 2.15) from y 3.5, 3.6 long; middle r 1.2 at h 2.45 from y 3.9, 4.0 long; a 12-sided panelled barrel, a collar, the bell, ten cyan segments and a band per pod (`pod_ring`) |
| Pod housing | from y 3.7 (top 4.75, the hall's eave) to 6.4 (top 3.9), half-width 1.55, sides into the skin or onto the pod's axis |
| Lead blades | 0.07 x 0.05 cyan bars on the lead edge (section point 0) from x 2.0 to the swept tip point (13.23, 5.9) |
| Seam lines | 0.025 cyan bars on the front eave crease from x 4 to 9 and the rear eave from x 5 to 8 |
| Hatches | six per side, 1.4..2.4 x 1.0..1.4, a bevelled frame round a recessed plate with two slots; 40 seeded scratches per side (ext_chrome, 0.18..0.68 m) |
| Legs | mount 0.8 x 0.6, knee (0.75, h 0.36), struts r 0.15/0.12, twin pistons, a foot plate r 0.55 with three toes at x 1.0 |
| Ramp light | a continuous amber strip inside each rail and a cross strip at the foot |
| Ground lamps | r 0.2 amber pucks 1.75 m out from each leg's mount and at (+-1.75, -5.9 / -7.25) by the ramp |

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

## The inside's light, room by room (inside lane, launch 2)

The join's numbers left the hall washed out (a white blob on the centre disc) and the corridors and tip rooms nearly
black. Three grid runs on the six interior views (`<raw>/ship/v1/grid_in{,2,3}/{hall,corridor,tip}.png`, each beside
its 2D sheet; script `<raw>/ship/v1/logs/in_grid.py`) found the causes and the numbers:

- **The metal only mirrored.** At metallic 0.7..0.8 the lamps hardly lit the silver diffusely: the windowless rooms
  mirrored their own dark, the hall mirrored its strips. `[light.mats]` sets `int_silver_*` to metallic 0.45, value
  x0.55, roughness +0.25; the grates metallic 0.6, value x1.2.
- **White strips.** Emission near 1 loses its hue under AgX: cyan (0.05, 0.8, 1.0) at x0.05 of its glTF strength and
  amber (1.0, 0.42, 0.06) at x0.08 stay saturated. Each emissive material's cell lights scale separately (`l`): cyan
  0.3 (at 1.5 they washed the hall's walls white-blue), amber 5 (the floor strips' warm pools), the lamp ring and
  lamps 0 (they glow, they light nothing).
- **The centre disc's blob** was light, not the disc: the eight hall lamps and the lamp ring's cells all met over the
  centre, and so did the hall's sixteen amber floor arcs' cell lights. The hall's lamps now hang by the wall (r 3.0,
  h 4.2, range 3.2, out of the disc's reach), the ring lights nothing, the amber cells reach half as far (`rr` 0.5:
  tight pools), the disc (`int_plate`) value x0.2, roughness +0.45.
- **Lamp groups** scale per room: `hall_lamp` 0.7, `corr_lamp` 2.0 (three ceiling lamps a corridor), `tip_lamp` 2.4
  (the ring lamp and a moonlight fill by the window), `out_lamp` 2.5 (warm camp lights at the treeline, x +-27, and
  in front of the ramp, for the windows and the ramp's view); `sky_horizon` 5 lifts the horizon behind the trees.
- The lamp ring has an emissive underside band (`lamp_ring`'s `band`): the thick warm ring of hall_in-3.

`ship.gd` `_look` applies `[light.mats]` (keys `v`, `r`, `m`, `c`, `e`, `a`, `l`, `rr`); a material without an entry keeps
the join's `int_value`, `int_rough_add` and `emission_scale`.

## Open problems (after step 1)

- **The hull's thickness** (after the hull lane's step 1): the skin is now one continuous faceted surface (variant
  F), but the rooms' heights keep the wings about 3.5 m deep and the tips 3.8 m tall, so from the front it is a thick
  wedge, not the turnaround's thin plate. Only a lower deck and rooms, or a wider span with blades beyond the tip
  rooms, would thin it; both change the numbers.
- The hall is still the brightest room (its lamp ring's cells); the corridors and tip rooms read at night.
- The pines are layered cones; the ground is flat and empty (no grass tint, needles, dirt by the ramp).
- The ramp reads dark from the hero view; the ground lamps glow but light nothing yet (no Godot lights: step 3).
- The interior has no UVs: the brushed grain is geometry and the triplanar shader only on the hull's metals.
- Triangles: the grates are about 60% of the 126k placed inside; measure with `bench` before the game takes it.
