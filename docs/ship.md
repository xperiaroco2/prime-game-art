# The ship

The aliens' ship, a wide metal manta (art #263; prime-game `docs/design/estate-map.md` section 5a; the approved 2D in
prime-game-design `ideas/ship-components/2d/`; since version 2, the mirrored layout of 2026-10-22, 5a wins over
`plan-3.jpg` for the geometry and the 2D sheets still set the look; see "Version 2" below). Step 1 is the
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
| `tools/tests/test_ship_*.py` | fast: `test_ship_layout.py`, `test_ship_interior.py`, `test_ship_hull_detail.py`, `test_ship_exterior.py`, `test_ship_clearing.py`; heavy (Blender): `test_ship_build.py` | either lane adds its own file |

Raw output (never in git): `<raw>/ship/v2/` (the layout's `raw_dir`; v1's in `<raw>/ship/v1/`) with `pieces/` (GLBs, `build_report.json`, validator `reports/`),
`plan/` (`plan.txt`), `shots/` (the views, `compare_*.png` with the 2D left, among them `compare_top.png` against
plan-3, `sheet.png`, `lights.json`), `walk/` (`check.json`, `walkthrough.mp4`), `logs/`, `notes/` (the workflow's
handoff notes).

## Coordinates and numbers

Plan coordinates from the ship's centre in metres: x east, y south, h up from the ground. The Blender builders write
plan coordinates, the harness turns them into Blender's (x, -y, h), and the glTF (Y up) holds Godot's (x, h, y). A
placement `[piece, [x, y, h], yaw]` puts a piece's local origin there, turned by yaw degrees about the vertical
(Godot's rotation y); the tip-room pieces are built facing east and placed at yaw 180 for the west room.

| What | Number (ship.toml) | Why |
|---|---|---|
| Footprint | the hull J: span 30.0 m (`width_m`, `span_max_m`), 18.91 m long with the nozzle pods (`length_m` 18.9, `length_max_m` 19.4; `ship_layout.lengths()`), 21.70 m from the ramp's foot (-9.9) to the nozzle tips; `ship --check` prints the current ones | the engineer's pick J (art #263 comment 6340589162; "Rebuild B") |
| Deck | floor at h 0.6 on landing legs (launch 3; was 1.0), slabs 0.25, walls 0.2 | the ramp meets the ground; a thinner hull |
| Hall | circle r 4.0 at (0, -1) (rebuild C; v2 (0, 0), v1 r 3.4); the rim 2.75 m round its front (rebuild C); 3.2 m to the ceiling's rim, 3.8 m to its apex (faceted, 16 sides, the four diagonal pairs of facets made one flat chord each for the vents and sockets) | 5a mirrored: round, 8 m across |
| Throat (rebuild C; v2's mouth passage x -1.3..1.3, y -4.6..-3.9) | the funnel from the mouth (x +-1.65 at y -7.1, J's nose edge; 5a: y -8) to the hall's vertices (+-2.915, -3.852); open to the sky forward of y -5.476, a 2.3 m ceiling aft of it | the only way in or out (5a's side hatch is dropped, see below) |
| Ramp | 3.3 m wide (the mouth), hinge (0, -7.1) at the deck, foot (0, -9.9) on the ground: 12.1 deg, 2.86 m long (rebuild C; v2 2.6 m from (0, -4.6)) | north at the centre |
| Corridors | `strip` rooms on the axes from the hall's centre (0, -1) to the tip rooms' (+-8.3, 3.0): 9.214 m, 25.73 deg; floor 3.708..8.219 along the axis (4.51 m), 3 m wide, straight, 2.4 m high (walls vertical to 1.45, then chamfered) | 5a mirrored: straight, about 3 m wide; rebuild A: on the diagonal |
| Tip rooms | circles r 1.8 at (+-8.3, 3.0) (rebuild C), the outer wall at +-10.1; 2.5 m to the rim, 2.8 m apex; no window since rebuild A (13 plain wall facets round the outer side) | 5a mirrored: 3.6 m across |
| Stations (not built) | console (0, 0) clear floor; vents on the throat's slanted walls (+-2.175, -5.751); sockets (+-1.800, 2.512) and the front two on the hall's flats (+-3.426, -2.958); breaker boards (+-6.030, 0.241) on the corridors' front wall; renewers (+-9.922, 3.781) on the tip rooms' outer wall, the player at (+-8.751, 3.217) | 5a mirrored; as built in "Rebuild C" |
| Player | capsule r 0.4, 1.8 m; every room keeps 0.5 m above it | the game's capsule |

The check holds: the footprint within 0.5 m; corridors `corridor_width_m` (3) +- 0.1 m wide and over 2.5 m long; the
tip rooms' outer wall at `tip_outer_m` (10.1) +- 0.05; the station spots (`check_spots`, "Version 2" below); clear heights over the capsule and margin; exactly one room with an exit, the ramp's hinge on its north
edge, the ramp as wide as the mouth and under 30 deg; every room reachable from the hall and linked rooms meeting;
every poly room convex, its points with a positive signed area in plan (x, y) (`check_polys`); every capsule walk
point on the deck on a room's floor with the capsule's radius round it (`check_walk`); every room's sampled outer
surface inside the hull J with 0.15 m of skin (`hull_skin`: `ship_hull_shape.clearance` on the checked layout's own
rooms, each sampled on its own); every room's outer wall and every placed piece inside the hull outline (the ramp may
stand outside); no piece defined twice or never placed.

**One entrance; the side hatch is dropped.** estate-map 5a lists a side hatch at (-12.5, 1) as a second way out. The
engineer's step-1 rule (art#263: the mouth ramp is the only way in or out, no side hatch, no doors) wins over that text:
ship.toml has no hatch, and `check` and `test_a_second_exit_is_refused` demand exactly one exit. If the hatch comes
back, both change with it. The corridors also run straight (5a: "curve with the wing"): numbers, not curvature.

**Wall stations and the corridor's slant.** The check places a breaker board in plan only; the corridor wall is
vertical to 1.45 m and then slants in (v2: half width 1.15 m at the 2.4 m ceiling, from 1.5 at the wall), so a station
taller than about 1.5 m at the wall meets the slant. The console at (0, 1) straddles the hall's plain disc (v2: r 1.176)
and its first grate ring (r 1.294). Step 2 accounts for both.

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
use absolute heights (deck at ship.toml `floor_h`, 0.6), so a placement's h is an offset (the clips' heights); a piece built at plan
angle 0 (its room toward -x) standing at angle a gets yaw -a; in a tip room turned by r, yaw r - a.

The numbers (version 2 rebuilt for the hull variant J, rebuild A of 2026-10-22; `ship_interior.py` holds them):
- hall: 16 facets' look, every vertex on the circle 4.078 (inner faces at about 4.0), rim 3.2 m, apex 3.8 m
  (ship.toml `clear_h`, `apex_h`); the segments round the ring (`hall_segments`, counter-clockwise from the mouth):
  the mouth's opening -112.5..-67.5 deg, the vent's flat chord -67.5..-22.5, one facet -22.5..3.23 (25.7 deg), the
  corridor's opening 3.23..48.23 (centred on the corridor's axis, 25.73 deg), the socket's flat chord 48.23..77.5
  (2.06 m, apothem 3.946, all plain: too narrow for the diamond side panels), two back facets 77.5..90..102.5
  (12.5 deg each, the back's one cable trunk at 90), then the west half mirrored. Each opening is two facets' chord
  (3.768, half width 1.561) framed by a portal 0.15 m deep; each flat a plain centre panel (`hall_panel_flat`, the
  vents' 1.6 m between two diamond panels; `hall_panel_flat_socket`); a piece per facet width (`_side`, `_back`,
  `_socket` for the wall panels, rim plates and ceiling panels; `phi_deg` their half angle). Floor: plain disc
  r 1.176, eight radial grate sectors r 1.294 to 2.941 between wedge spokes, the amber ring at r 3.035 on the 16-gon's
  old spacing (a 5 cm light in a 9 cm halo, 3 cm in 6 cm on the four arcs by the mouth), solid plates from r 3.129 to
  the walls: a rim plate per facet, a threshold per opening, a flat plate per chord (a fast test holds one per
  segment). Ceiling: one conical panel per (sub-)facet in a pale lit steel (`int_ceil_a`/`_b`, metallic 0.3), ribs
  with cyan strips at every vertex, the lamp ring (eight lamps) at r 1.471.
- corridors: one profile, 3 m wide, vertical to 1.45 m (cable bay 1.1 to 1.45 m), slanted in to 2.3 m wide at the
  2.4 m ceiling (`clear_h`); straight along the axis from the hall's centre to the tip room's (25.73 deg off the x
  axis, 9.214 m centre to centre); four modules of 1.026 m from u 3.918 (hall portal) to 8.024 (tip portal); the back
  (south) wall a cable bay per module; the front (north) wall a bay from 3.918 to 5.071, the breaker board's plain
  wall 5.071 to 6.871 (the spot's 1.6 m and 0.1 a side), a bay from 6.871 to 8.024; cyan arches at u 4.15 and 7.792,
  ceiling ribs at 5.06, 5.97 and 6.88. A front-wall piece is turned by -25.73 deg in the east and +25.73 in the west
  (the mirror image). The mouth passage is one module of 0.682 m with an arch at the ramp hinge.
- tip rooms: polygon on radius 1.85 round (+-8.3, 4.0), turned so the door faces the hall along the axis (room yaw
  -25.73 east, 180 + 25.73 west); 13 wall facets of 19.11 deg round the outer side (no window: the engineer,
  2026-10-22), the corridor chord over +-55.8 deg from the back (1.04 from the centre, half width 1.53); rim 2.5 m,
  apex 2.8 m; pilasters at the door's edges, cable trunks (flat, 0.09 m proud) at the two vertices nearest the door
  each side, the outer side plain facets (the renewer's); radial grate floor with amber spokes, solid plates 0.3 m wide
  to the walls (at the door two slivers and the portal's plate: `tip_rim_polys`, a test holds them simple); ribbed
  ceiling with cyan strips and a six-lamp ring.
- details: three crushed cup models (four placed, off every station spot; the hall's red cup on the grate inside
  the amber ring, in from the mouth's threshold), a cable coil in the east corridor, two repair plates on the rim.

Materials `int_*` (the library in `ship_interior.py` sets metallic 0.7 to 0.8; at night ship.toml `[light.mats]`
overrides them in Godot: the silvers 0.45 so the lamps light them, the plate 0.3, the grate 0.6): two silver
tones alternating per panel, a darker trim silver, grate and floor plate metal, dark recesses, emissive cyan, amber and
warm lamp, glass, three cable colours, the cup's red and white. No textures or UVs yet (seams, folds, bevels and
scratches are geometry).

The lane's own look check (no Godot): `ship_interior_render.py` in headless Blender through `runner.blender`
imports each GLB once, instances it at every placement, lights it with `[light]` and a moon and writes Eevee views
and `compare.png` (the 2D left, the render right). Interior pieces build with `ship --build --only <their ids>
--out <raw>/ship/v2/pieces_int`, then their GLBs and report entries are copied into `pieces/` (one build report for
the Godot run).

The worked geometry (inside lane, step 2, from hall_in-3, corridor.jpg and materials-3): the hall's wall facets fold
up to a raised diamond (`pyramid`, ridge 0.1 m proud) inside four chamfered corner plates, the upper panel split on its
diagonal; the hall's plain vertices and the tip rooms' carry cable trunks (`trunk`: posts 0.2 m proud, 0.52 m wide,
with `trunk_cables`, five cables r 18..32 mm, and bolted `trunk_clip` frames); the corridors' rib frames stand 0.18 m
into the corridor (2.14 m clear at the floor) with a stepped inner rim carrying the cyan strip; the cable bays at
1.1..1.45 m are 0.24 m deep with four cables r 26..32 mm behind bolted clip frames; grate modules sit in a bevelled
5 cm rim with hex bolts; the amber floor strips are 0.7 m (corridors) with a frosted halo (`int_halo`, glows, lights
nothing), the hall's ring 0.12 m wide. (v2's tip windows, their mullions and shutters are gone since rebuild A.)

## Running it

```
tools/run.sh ship                       # the check and plan.txt
tools/run.sh ship --build               # one GLB per piece (about 1 min); --only ids
tools/run.sh ship --godot --walk DIR    # headless: sizes, colliders, the capsule walk into DIR/check.json, then DIR/walkthrough.mp4
tools/run.sh ship --shoot DIR           # off-screen night shots, compare_top.png (plan-3 left), sheet.png
```

Runs over 180 s go to the background with their log (CLAUDE.md, "Shell"). A snapshot of the whole after launch
2's join (2026-10-22; superseded: `ship --check` prints the current pieces and placements, 157 and 1226 at aa561f1): 139 pieces, 1094 placements (the clearing's 162 pines, 26 bushes, 6 logs, 5 stumps, 160 tufts and 8
party-light posts among them), 59310 triangles per piece set, glTF-Validator clean; extent 26.46 x 13.9 m;
`--godot`: Godot sizes equal Blender's, 105 colliders, the capsule walk reaches all 14 points (18.8 s);
`--walk`: the 1280x720 walk-through, 89.5 s, 2149 frames, 12.8 MB (rendered in 313 s); `--shoot`: 14 views and
their compare sheets, 415..620 draw calls inside the tip rooms, 1740..2032 outside. Times: `--build` about 2 min,
`--godot --walk DIR --shoot DIR` about 10 min.

## The exterior (EXTERIOR lane)

The outside is the hull J (`ship_hull_shape.py`, plain Python; only variant J is live) built by `ship_hull_j.py` as
four pieces in the plan frame at the origin: `skin_top`, `skin_belly`, `skin_mouth` (the throat's notch: its cut side
faces in dark plates) and `skin_cheeks` (the throat walls' outer faces under the rising belly, in the same dark plates,
so each side of the mouth reads as one face up to the nose's slope). Every face is cut into plates in its own plane
(a 2.2 cm chamfer sinking 1.4 cm into a dark under-skin). `ship_hull_detail.py` adds the cockpit canopies (fairing,
glass, glow; outside only) and the three nozzle pods with their cyan rings; `ship_hull.py` the ramp, its lights and
the six landing legs (`leg`: `rise` lifts a mount's top where the belly climbs over it, the front pair); the clearing
is below. "Rebuild B" and "Rebuild C" at the end hold J's numbers and the notch.

**History.** Before rebuild B the outside was a kit on other shapes, all retired and no longer built: launch 3's
lofted lower deck with lens tips and cyan blades (`ship_hull_skin.py`), v2's smooth skin with stripes, seam lines,
hatches, pod housings and the tip windows' glass and frames, and the tip windows' view and shutters (`--shutters`,
removed in rebuild D). The blockout variants A to L stay in `ship_hull_shape.VARIANTS` for the blockout sheets
(`ship_hull_blockout.py`); a Meshy hull (batch `2026-10-22-ship-hull-meshy`) was stopped. The PRs of art #263 and
git history hold their numbers.

### The clearing and the outside light (hull lane, step 3)

`ship_hull_clearing.py`; every clearing piece stands outside the hull and collides with nothing. The placements were
seeded once (seed 263) and are plain data in `exterior.toml`; each stands on the ground piece's own facets
(`ground_h`: the triangle under the point; 0 inside r 16). `tools/tests/test_ship_clearing.py` keeps the path clear,
the party string over head height, the clearing on the ground and the walk's outside points free.

| Piece | Numbers (plan metres) |
|---|---|
| Dirt patch | an irregular blob about 15 x 11 round the ship (radius capped at 15.6, inside the ground's flat 16 m), 0.006 over the ground |
| Dirt path | `PATH`: from the ramp's foot (0, -9.6) north-west to the treeline (-26.5, -32.5), 2.0 wide at the ramp narrowing to 1.3; 0.012 over the ground (0.05 beyond r 16) |
| Tufts | `tuft_a`, `tuft_b` (green), `tuft_dry`: 9..14 blades 0.18..0.5 high; 160 placed at r 3..30, none within 1.2 of the path or on the ramp |
| Bushes | `bush_s/m/l` (spread 0.8, 1.3, 2.0): 5..8 lumps in two greens; 26 at r 14..30, outside the ship's ellipse |
| Logs, stumps | `log_a` 3.5 x r 0.24, `log_b` 4.5 x r 0.3, cut ends and two stubs; 6 logs at r 12..22, 5 stumps at r 11..24 |
| Pines | `pine2` for every kind (hull 3-3): a leaning tapered trunk (r 0.024 x height + 0.12) with four root flares and dead stubs below `bare` x height (0.12..0.3), 9 + height/3.5 layers of 5..7 branches, each a bark stalk (over 0.9 m), a drooping needle spindle and two side sprays (about 2700 triangles for a 19 m pine); `pine_a/b/c/s` (15, 11, 19, 5.5 m, the old ring) and `pine_d/e/f/g` (17, 23, 9, 13 m), 162 in all, none within 3 of the path |
| Ground cover | (hull 3-3) `moss_a/b` (2.6, 1.5) and `litter` (2.2, needle brown): low mounds, rim 0.03 under the ground, crown 0.05..0.12; `fern_a/b` (0.7, 1.05): 7..10 arching fronds of leaflet pairs; 34 mounds and 70 ferns at r 11..40, outside the ship's 15 x 9.5 ellipse, 1.2..1.3 off the path, ferns out of the front view's cone (seed 2633) |
| Rock piles, long logs | (hull 3-3) `rock_pile_a/b` (1.4, 0.85): one boulder and four smaller, half sunk; `log_c` 7 x r 0.36; 6 piles, 3 more `rock_b`, 3 long logs and 11 more bushes at r 13..36 |
| Party lights | eight 2.7 m posts 1.6 off the path's centre on alternating sides (the first west) at arc fractions 0.2..0.76 (nearer, a post stood in the front shot); the string sags 0.45 per span, a bulb every 0.6 (one in four amber) |

The outside light: lamp rows in `ship.toml` [light] by group (each scaled by `<group>_lamp`): `pool` (the twelve
ground lamps at h 0.3, range 3.5, and three under the belly at h 0.35, range 6; amber, shadowed so they never light a
room), `party` (one per span at 2.1 over the ground, range 5, warm), `rim` (two cool omnis behind the ship, (+-14, 22,
h 13), range 34). The moon and the groups' numbers come from one grid (`<raw>/ship/v1/grid_out/grid.png`, script
`<raw>/ship/v1/logs/hull3_grid.py`, the four outside views): A, the old moon (1.3 from the north-east, pitch -38),
lit the top plates flat white; C (0.45, pitch -20) left the hull black from the front; D (0.9, pitch -48) whitened the
top and the back again; B is kept: moon 0.6 at pitch -30, yaw 35 (from behind the ship, south-east), pool 1.6, party
1.3, rim 1.2. The old `out` lamp in front of the ramp went from 2.5 at y -16 to 1.0 at y -12.5 (an orange blob in the
front shot's foreground), and the ground is a dark green-brown (0.05, 0.062, 0.035).

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
| `hull_rough_add` (the hull silvers: the moonlit white plates) | +0.12 (hull 3-2; was 0.22) | 0 |

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

## Strip lights in place and the small details (inside lane, step 3)

- **The warm spot on the hall's disc** was every amber strip's light in one place. `_dress` put each emissive cell's
  omni light at its mesh's AABB through `mi.global_transform`, which here gave the piece's own frame, so all sixteen
  floor arcs (and every corridor floor strip) lit from the hall's centre. `_placed` now composes the transform up the
  parents: 122 cells, the 96 largest get a light, none within 2.2 m of the hall's centre. Every shoot writes
  `lights.json` beside its shots (the cells' count, each light's position, energy, range and colour).
- With the lights on their strips the old numbers washed the rooms teal and white; one grid
  (`<raw>/ship/v1/grid_in6/grid.png`, script `<raw>/ship/v1/logs/in3_grid.py`, five views x six variants) picked
  variant H, written as the interior materials' own numbers so the hull's strip lights keep theirs: `int_cyan` `l`
  0.04, `int_amber` `e` 0.14 `l` 2.0 (the strips pass the glow threshold and stay amber), the hall ring's own
  material `int_amber_ring` `e` 0.14 `l` 0.8 `rr` 0.3, `int_halo` `e` 0.5.
- The details, each its own piece: `cup_a`..`cup_c` (16 oz, scale 1.25, crushed, lying), `spill_a` and `spill_c` (a
  1.5 mm glossy film running from the mouth; each placed with its cup's position and yaw), `cable_coil` (3.5 turns of
  blue cable and a plug, by the east corridor's south bay), `floor_patch_a`/`_b` (bolted repair plates on the hall's
  rim floor) and `rim_bolts` (hex bolts down every rim plate's seam). The layout test keeps every cup, spill, coil
  and patch outside a station's clearance + 0.4 m.

## The mouth, the tip windows, the hall's cap and the light (inside lane, launch 3 step 1)

- **The mouth** has its own portal, arch and upper walls on `MOUTH_PROF`: the mouth room's full 2.5 m width and
  clear height, the walls vertical to 0.35 m under its ceiling, only the top corners chamfered (the corridors'
  profile, vertical to 1.25 m and 1.8 m wide at the top, narrowed the view out of the hall to about 1.6 m;
  hall_out-2). The pieces: `mouth_portal`, `mouth_portal_strip_l`/`_r`, `mouth_arch`, `mouth_arch_strip_l`/`_r`;
  `mouth_wall_up` and `mouth_ceil` take `prof = "mouth"`.
- **The tip window**: three thin mullions (10 cm deep face, 4.4 cm inner rib; `MULLIONS` = vertices 2, 4, 6 of the
  eight segments), four panes of two facets (tip-3; were seven of 17 cm). The test allows at most four.
- **The hall's cap**: the lamp ring closes on a faceted cone (16 facets) rising 0.34 m into the roof, eight ribs
  under it and a lamp lens at its top, lit by its own short lamp (`[0, 0, 4.2]`, range 1.3 m: the cone, not the
  floor). The tip rooms' rings get the same cap, scaled.
- **The cups**: scale 1.5 (18 cm), two on the hall's grate ring at (1.05, -1.95) and (-1.55, -0.75) in sight of both
  hall views, their spills 1.6x and 1.4x; the third stays in the west corridor.
- **The light** (one grid, `<raw>/ship/v1/grid_in31/grid.png`, script `<raw>/ship/v1/logs/in31_grid.py`, four
  variants x five inside views; variant C without its stronger `out_lamp`): the corridor lamps warm-white
  (1.0, 0.95, 0.88) at `corr_lamp` 2.6, `int_cyan` `l` 0 (glows only: 0.04 still washed the corridors teal), four
  `fill` lamps (`fill_lamp` 1.0) at x +-23 on the pines the tip windows look at (range 9.5 m: off the wing tips),
  `sky_horizon` 10 (was 5).

## The tip window's well (inside lane, launch 3 step 2)

- **The glass sits in the lens's band.** The tip room's opening in its wall (sill 1.0, head 2.2 over the deck, the
  rooms' numbers; join 3 raised the sill from 0.45: the well's sill slope filled the lower half of the opening) is lined out to the hull lens's slanted window band (`ship_hull_skin.tip_profile`, points 4 and 5:
  about h 1.93 to 2.98 m, r 2.9 to 2.35 m at the axis): a sill rising outward from the wall to the band's lower
  edge, a soffit to its upper edge, two jambs at +-65 deg, slim frame bars along both edges, the three mullions'
  frames on round the well (sill, glass, soffit) and a thin cyan glow line over the lower bar (`tip_well_e`/`_w`),
  and (until polish 4) the glass 1.5 cm inside the band (`tip_glass_e`/`_w`; now one pane, the hull's). Before, the glass stood upright in the wall and its
  lower half showed the lens's lower face and its cyan blade. Eye height (1.65 m over the deck) looks through the
  band (the test keeps lower edge < 2.25 < upper edge).
- **One per side**: the well is sampled at the hull's own angles (10 deg steps, the swept tip's outline points) plus
  the room's window vertices, from the placed variant (`DEFAULT`), so it meets the band's hole edge exactly; the
  lens is not symmetric (toward the swept tip's rear the blade reaches r 5.3, the band's lower edge r 4.85), so the
  west room (turned 180) reads the profile at the mirrored angle. A change to the skin moves the well with it on the
  next `--build --only tip_well_e,tip_well_w,window_frame_e,window_frame_w`.
- **The views**: `in_hall_out` from the hall's centre (y 0) at fov 52 (polish 4; was y 1.0, fov 60), the tip views level at
  2.25 m toward the band (`exterior.toml` `[shots]`).

## Launch 3's numbers and open problems (join 3)

What bent in launch 3 and why (manager update 2; ship.toml, `ship_hull_skin.py`):

| What | Was | Now | Why |
|---|---|---|---|
| Deck floor | 1.0 | 0.6 | a thinner hull; the ramp still meets the ground (12.1 deg) |
| Corridor clear | 2.6 | 2.4 | 0.6 m over the 1.8 m capsule (the rule keeps 0.5) |
| Tip room clear / apex | 2.8 / 3.2 | 2.5 / 2.8 | 0.7 m over the capsule |
| Hall clear / apex | 3.4 / 4.0 | 3.2 / 3.8 | the spine stays the thick part (crest 4.9) |
| Tip window sill | 0.45 | 1.0 | the lens's band starts 1.33 m up: a low sill left the well's slope filling half the opening |
| Span | 26.46 | 27.5 | the lens tips' blades at x +-13.75 (`span_max_m`); the plan's x positions inside are unchanged |
| Outside faces | vertical walls | every face >= 25 deg off vertical (`steep()`, tested) | manager update 2 |
| Pieces | 139 | 159 (83395 tris) | the lens skin, re-seated details, branched pines and ground cover |

Open problems after launch 3:

- **The silhouette is still not the turnaround's manta** (the night's serious problem). From the side the lens tip
  reads as a glazed drum: the 2.5 m tip room inside a lens only 0.7 m deeper than its wall leaves the lower face at
  the 25 deg minimum and the blade at mid-height. From the front at eye height the wings are a level plate, where the
  2D's wings rise in a V to the tips (dihedral) on chunky legs. Both need a hull decision, not tuning: lower tip rooms
  (2.3 m clear is the capsule rule's floor), wings with a dihedral (the corridor floor stays level, so the skin rises
  over it), or the tip rooms pulled in toward the body. The front review shot was raised to the turnaround's view
  (eye h 5.6) in join 3, which shows the upper slopes but does not change the shape.
- Outside: 1.95M..2.49M primitives and 3367..3822 draw calls per view with the branched pines: a pine LOD or an
  impostor ring before the game (`bench`).
- 26 small strip cells get no light (`MAX_LIGHTS` 96); the interior has no UVs (grain is geometry; the triplanar
  shader only on the hull's metals); the grates are about 60 % of the inside's triangles.
- The tip windows' double glass and the party string's absence from the hall-out view: fixed in polish 4 (below).
- The detail_seam close-up's hatches read as faces (dot pairs); the legs are small and hidden from the front.

## Polish 4 (launch 4): the critic's third-round items that are not the silhouette

| What | Was | Now | Why |
|---|---|---|---|
| Hall centre disc | plain plate (`int_plate`) | a slotted grating in four quarters round a bolted 0.265 m hub over a warm `int_halo` glow layer (`floor_disc` `grate`) | it read as a black hole; hall_in-3's disc is a lit grating |
| Tip glass | the hull's `tip_window` (`glass_tint`, alpha 0.6 brown) and the well's `tip_glass_e`/`_w` | one pane, the hull's, `glass_window` (alpha 0.12 cool; Godot alpha 0.05) | the doubled tint dimmed the clearing to orange |
| Tip ceiling lamp ring | R 0.6 | R 0.42 (`R_TIP_RING`; facets, ribs and the six lamps follow) | the pale cog read oversized from the room |
| Window-view fill lights | x +-23, range 9.5, `fill_lamp` 1.0 | x +-31, range 12, `fill_lamp` 2.0 | the pines stand at r 33+: the old lights never reached them |
| Mouth arch | inset 0.18 | inset 0.08 (`cor_arch` `inset`) | the opening as wide as the mouth allows (+-1.25) |
| Party posts | the first post alone at (-3.82, -15.51) | a gate pair (2.6, -14.6) and (-3.0, -15.0), the string across the path, then on (`GATE`) | the lone post read as a stick in the front and hero shots; the string now falls in the hall-out view |
| Ground specular | 0.5 (Godot default) | 0.1 (`[light.mats]` `s`, `ext_ground`, `ext_dirt`, `ext_path`) | the dirt mirrored the bright horizon at grazing angles: snow-white through the mouth |
| Hero fill | none | a `key` lamp (-11, -13, 9 m), range 40, cool, `key_lamp` 1.0 | the hull's far side and the ground were a black pool |
| Ground cover | - | five pieces in the hero's west foreground, three under the east wing | dark patches in the hero view |
| Cups | scale 1.5 | 1.8, spills 2.2 / 2.0; cup_a (0.75, -3.0) in hall-out's foreground, cup_c (-1.05, -0.45) in hall-in's | read as a red mark |
| Nozzles | segments only, winding mirrored (culled) | a 0.5..0.72 r cyan inner ring 3 cm proud of the bell's rear cap (ln + 0.4, which hides the throat and the old segments), oriented rearward | black holes |

The light numbers come from one grid (`grid_p4/grid.png`: key 0 / 0.6 / 1.0 / 1.6, fill 1 / 1.5 / 2 / 3, ground
specular 0.5 / 0.1 / 0.1 / 0): C taken (key 1.0, fill 2.0, specular 0.1).

## After the night (join 4): open problems and the silhouette question

Join 4 ran the whole on polish 4's tree: `ship --check --build --godot --shoot shots4 --walk walk4`: 27.50 x 14.30 m,
157 pieces (the well's two tip panes gone), 1226 placements, 92,035 triangles, glTF-Validator clean, 125 colliders,
the walk 14/14, 14 shots and compare sheets, walkthrough.mp4 1280x720, 89.5 s, 13.1 MB. Nothing broke.

**The silhouette question (the engineer's; not chosen here).** The 2D (turnaround front and side) ends each wing in a
thin blade that rises toward the tip. One deck with a walkable round room at the tip fights that in these numbers
(the 2D's are read off turnaround.jpg's front view at its 27.5 m span, so they are about):

| What | Now (ship.toml, `ship_hull_skin.py`) | The 2D, about | What sets ours |
|---|---|---|---|
| Tip room | r 2.05 at x +-10.75 (x 8.7..12.8), floor h 0.6, rim 3.1, apex 3.4 abs | a thin wing there | 5a: panel (-10.5, 0), renewer (12, 0); corridors across the whole width |
| Hull depth at x 10.75 | 3.35 m (belly 0.3 to the lens crown 3.65) | 1.0..1.5 m | slab 0.25 + clear 2.5..2.8 + roof; the floor is 2.3 clear (1.8 capsule + 0.5) + slab + roof, about 2.8 m |
| Tip blade | x +-13.75 at h 1.7, 0.7 m past the room's wall | x +-13.75, a blade about 1 m deep | the lens's faces at the 25 deg minimum off vertical |
| Rise to the tip (dihedral) | lead blade h 0.9 at the body -> 1.6 at x 10.75 (+0.7 m) | the tip's underside about 2.5..3 m over the root's (about 12 deg) | the corridor and the tip room floors level at 0.6 (one deck) |
| Spine / tip depth | 4.9 / 3.65: the tips 75 % of the spine | the tips a small fraction of the body | the tip room's head room |

The numbers in the way are the tip room's centre (x 10.75) and its clear height (2.5 m, the rule's floor 2.3) on a
level deck. The levers, each with its cost: lower the tip rooms to 2.3 clear (saves 0.2 m of the about 2 m too deep); move the
tip rooms toward the body (the 5a panel and renewer spots move with them, the outer wing becomes an empty blade); a
dihedral skin over level rooms (the tips get taller, not thinner); a floor that rises with the wing (steps or a slope
into the tip rooms: no longer one level deck); or keep the deep tips and accept a heavier manta than the 2D.

Other open problems after the night:

- Outside 3423..3827 draw calls and 2.0M..2.5M primitives per view (the branched pines); inside 984..3328 (the hall the most):
  a pine LOD or impostor ring and `bench` before the game.
- The tip window shows the moonlit pines but no warm party glow (the string is north-west, outside the windows' +-65
  deg); the tip ceiling's cog still reads pale; the gate string crosses the front shot under the ramp's foot.
- 26 small strip cells unlit (`MAX_LIGHTS` 96); no interior UVs; the seam close-up's hatches read as faces; the legs
  small and hidden from the front.
- No fresh-context review of launch 4's diff ran inside the workflow (no agent tool): the manager runs one.

## Version 2: the mirrored layout (layout step, 2026-10-22)

The engineer changed the geometry (prime-game `docs/design/estate-map.md` section 5a in xperiaroco2/prime-game#1293;
prime-game-design `ideas/ship-components/2d/README.md`, "The layout mirrored"): a round hall 8 m across, two straight
corridors 3 m wide, two round tip rooms 3.6 m across at x +-8.3 with the outer wall at +-10.1, and every station
hanging flat on a plain wall. The look of v1's inside stays (materials, night light, ribs, cable bays, amber floor
strips, cyan arches, the tip window, the closed hall ceiling with its lamp ring); the rooms are refitted. Raw output:
`<raw>/ship/v2` (`raw_dir`; v1 stays in `<raw>/ship/v1`).

**The plain wall spots** (`[stations]`, `ship_layout.check_spots`). A wall spot is the point `at` on the wall's face
and the `normal` into the room. The check holds: the point on its room's wall; a band `plain_width_m` (1.6) wide and
0.3 m deep in front of it free of every piece with a `foot` (a plan box in the piece's own frame, written by
`ship_interior_place.py` for the trunks, trunk cables and clips, pilasters, the corridors' cable bays and clips and the
arches); the player's stand (`depth_m` 0.5, the renewers' 0.9, plus the capsule's radius out from the wall) inside
the room; and `pass_m` (1.6) of free floor behind the player, the capsule's width inside the rooms, crossing no floor
spot. The console is a floor spot: 0.35 m of clear floor round (0, 1).

**How the generator keeps them plain** (`ship_interior.py`, `ship_interior_place.py`):
- The hall: the 16-gon keeps its facets and ribs, but at the four spots (45 deg, read from ship.toml as `FLATS`) the two
  facets meet in one flat chord (`hall_panel_flat`, 3.12 m wide at apothem 3.768, with a soffit up to the ceiling's
  rim, as an opening's), and the vertex between them gets no cable trunk. The spot sits on the chord at (+-2.66,
  +-2.66) (5a: about (+-2.6, +-2.6)); a 16-gon vertex sits at 45 deg, so a facet there would put a trunk in the spot.
- The corridors: 3 modules of 1.064 m portal to portal (`N_MOD` 3; x 3.918..7.111); on the front wall (y < 0) the
  modules over a breaker board's span get `cor_wall_mid` (a plain strip) in place of the cable bay, the cables and
  the clips; the cyan arches stand at x +-4.15 and +-6.4, off the board.
- The tip rooms: R_TIP 1.85, the door chord 55.8 deg for the 3 m corridor, three wall facets of 19.7 deg each side;
  the window side holds no trunk, so the renewer stands before the window (sill 1.0: the window is seen above it).

**The lanes' files** (two builder lanes on one branch):
- INSIDE: `tools/blender/ship_interior*.py`, `layouts/ship/interior.toml` (generated: its look and details),
  `ship.toml` `[light]`, `godot/ship/`; the tip windows' shutter and button.
- HULL: `tools/blender/ship_hull*.py`, `layouts/ship/exterior.toml`, `ship.toml` `[hull]`: the smooth skin and the new
  silhouette (the tips at about +-13.75 past the tip rooms).
- Shared, changed by either only with a note: `ship.toml` `[size]`, `[deck]`, `[[rooms]]`, `[stations]`, `[walk]`,
  `[shots]`, `tools/runner/ship_layout.py`, `tools/runner/commands/ship.py`, the tests.

The layout step moved the stern pods' noses 0.35 m back (y 3.85 and 4.25, lengths 3.25 and 3.65, the nozzle tips
where they were): the r 4.0 hall's back wall reached into them.

## The inside refit to version 2 (inside lane, step 1)

- The hall's floor and lamp ring scale with the hall (`K_HALL` = 4.0 / 3.4): the lit grating disc r 1.176, the grate
  ring 1.294..2.941, the amber ring 3.035, the rim plates from 3.129 (origin 3.529), the lamp ring and the ceiling's
  inner edge 1.47. The tip floor: disc 0.55, grate from 0.62, the strips at 1.08.
- Each vent and socket chord (`hall_panel_flat`, builder `flat_panel`): a plain centre panel 1.6 m wide (no relief, no
  trunk; `[stations] plain_width_m`) between two 0.76 m diamond panels; no floor marking at the spots.
- **The tip windows' shutter.** A blast shutter in the window's 20 cm reveal: one ribbed panel per window segment
  (`tip_shutter`, 8 a room, each its own placement, origin on the segment's centre line, its mid-plane 0.1 m behind
  the wall face), guides in `tip_shutter_track` (the head's rail, the sill's slot). Closed it fills the segment from
  the sill to the head; open it is lowered `SHUTTER_DROP` (1.17 m) into the low wall, its cyan top edge in the
  sill's slot. The move is a straight drop (Godot `position.y`). `interior.toml` places the panels open (`place`)
  and lists the closed pose as `shutter_closed`; `ship --shutters closed` (`ship_layout.pose`) swaps them in. The
  button `tip_shutter_button` (a plate, an amber push button in a cyan ring) sits on the first wall facet north of
  each window, 1.15 m over the deck, 1.7 m off the window's axis: off the renewer's band. Not wired (the game
  track). Neither the shutter nor the button stands in front of the wall face, so they carry no `foot`. A first
  try with 24 turning louvre blades read as bars across the window when open.
- Party cups: as before, plus one on the east window's sill (north end).

## The inside, step 2 (inside lane, v2)

- **The tip well on the smooth skin.** `_well_rows` reads `ship_hull_smooth` (the hull lane's skin): the band's
  lower edge is the sill ring `pod_r(SILL - 0.05)`, its upper edge the head ring `pod_r(HEAD + 0.05)`, each at the
  skin's own height (`heights()`) at the hull's own angles (`RAY` steps, plus the room's facet angles), so the well
  meets the hole's edge on every rebuild. `test_the_window_well_meets_the_skin_band` holds it: the band outside the
  room wall, open (head over sill by 0.3 m or more), its head over eye height, the sill rising outward.
- **The closed shutter's tone** (`SHUTTER_TONES`, `SHUTTER_TONE`): one grid run (`SHIP_SHUTTER_GRID=1` regenerates
  `interior.toml` with the east room's closed panels in four tones, two segments each; never committed;
  `ship --shoot DIR --shutters closed`). Tone `d`, a dark grate-steel body under bright silver slats, reads as a
  shutter; the old pale silver (`a`) read as a flat wall. The open pose is unchanged.
- **The button** is 12 x 20 cm (a plate, a cyan ring r 4.2 cm round an amber push button r 3 cm, two dark label
  bars): the 7 cm plate did not read from the room's middle.
- **Render layers** (`godot/ship/ship.gd`): the outside lane's pieces draw on layer 2 (`OUTSIDE_LAYER`; the request's
  `outside` list from `ship.py`), and every strip light made from an inside emissive cell lights only layer 1: the
  smooth skin sits close over the ceilings and the strips' unshadowed lights made cyan blots on its top.
- **The outside metals** (`METALS` in `ship.gd`, the engineer: smooth like a ray, a clean soft sheen): no seam grid,
  no scratches, a trace of grime, a softer brush (grain 0.4) on `hull_silver`, `ext_silver_b`, `ext_silver_c`;
  no seams or scratches on `hull_dark`, `ext_frame`, `leg_metal`.
- `ship_layout.check` counts a piece placed only in the closed pose (`shutter_closed`) as placed.

## Rebuild A: the diagonal corridors for the hull J (2026-10-22)

The engineer picked the grey blockout J (`tools/blender/ship_hull_blockout.py`: F's outline, span 30 m, length
18.9 m with the nozzles, wing tips rounded in plan with r 1.5 m; art#263 comment 6340589162) and changed the inside
for it: the tip rooms at (+-8.3, 4.0), the corridors straight and diagonal from the hall's wall to each tip room's
wall, no tip windows; the hall's look frozen. What rebuild A changed:

| What | Number |
|---|---|
| Tip rooms | r 1.8 at (+-8.3, 4.0) (was (+-8.3, 0)), outer wall at x +-10.1, heights as before; no window |
| Corridors | ship.toml shape `strip`: `axis` [[0, 0], [+-8.3, 4.0]] (25.73 deg, 9.214 m), floor `along` 3.708..8.219 (4.51 m; v2 3.6 m), `width` 3.0 |
| Hall openings | the corridors' at +-25.73 deg from east (v2: 0 and 180); the mouth's unchanged |
| Sockets | moved back off the corridor openings: (+-1.800, 3.512), normal (-+0.456, -0.890) (v2 (+-2.664, 2.664)): 1.21 m |
| Breakers | on the front wall, u 5.971: (+-6.030, 1.241), normal (-+0.434, 0.901) (v2 (+-5.25, -1.5)) |
| Renewers | before the plain outer wall on the axis: (+-9.922, 4.781), the player at (+-8.751, 4.217) (v2 (+-10.1, 0)) |
| Vents, console | unchanged |
| Size | `[size]` J's: width and span 30.0, length 18.9 with the nozzles (max 19.4) |

(Undone by rebuild B, below.) `[hull] pending` (the hull lane's v2 skin still stood round the old tip rooms): `ship --check` skips the footprint
and the rooms' and pieces' inside-the-hull tests and prints the skip; the tests that need J's skin (the footprint,
a piece outside the hull, the walk-through's keys, the skin's span) skip with the same reason. The tip rooms keep a
legacy `window` key that only the v2 hull skin reads (`ship_hull_skin`, `ship_hull_smooth`); `ship_hull_blockout.py`
still reads the old corridor keys (`x`). Step B (the hull lane) builds J round the moved rooms, then drops `pending`
and the legacy key. The inside's light: the corridor lamps at u 4.6, 5.97 and 7.35 on the axis, the tip lamp at the
room's centre, the old window's cool moonlight kept as a fill 1.3 m out on the axis (2.0 m up). ship.toml's `in_`
views win over the exterior's of the same name (`ship.py` `shot_views`), so the inside views follow the rooms.

## Version 2 joined (join step, 2026-10-22)

The two lanes' work, run as one whole on `feat/ship-mirror-263`:

| What | Number |
|---|---|
| Hall | round, r 4.0 at (0, 0), about 50 m2; 16 facets, the four 45 deg pairs merged into flat chords 3.12 m wide (apothem 3.768); ceiling 3.2 at the wall, 3.8 at the lamp ring |
| Mouth | y -4.6..-3.9, the ramp from the north: the only way in or out |
| Corridors | straight, x +-3.7..+-7.3 (where the circles cross y +-1.5), y -1.5..1.5 (3 m), 2.4 m clear; 3 modules, arches at x +-4.15 and +-6.4 |
| Tip rooms | round, r 1.8 (wall facets at 1.85) at (+-8.3, 0), outer wall +-10.1; 2.5 m at the wall, 2.8 m at the centre; the curved window on the outer side, sill 1.0 m |
| Wing | low to x 11 (edge 1.0..1.1 m), curling up past x 12 to the tips at about +-13.75 (3.8 m high), 0.93 m thick at x 11.5, 0.67 m at 12.5 |
| Wall spots | vents (+-2.664, -2.664), sockets (+-2.664, 2.664) on the hall's flat chords; breakers (+-5.25, -1.5) on each corridor's front wall; renewers on the window wall (+-10.1, 0), the player at (+-8.8, 0); each a 1.6 m plain band, 1.6 m pass behind the player; the console's clear floor round (0, 1) |
| Heights | unchanged from v1 (deck 0.6; the 1.8 m capsule with 0.5 m or more over it everywhere) |
| Pieces | 151 GLBs, 1089 placements, 97,444 triangles per piece set, glTF-Validator clean; extent 27.50 x 14.49 m |
| Godot | sizes equal Blender's, 145 colliders; the capsule walk reaches all 14 points, both tip rooms included (16.6 s) |
| Walk-through | 1280x720, 89.5 s, 2149 frames, 13.1 MB (rendered in 364 s) |
| Draw calls | tip rooms about 1,120, corridors 1,390..1,590, hall 2,890, outside 3,020..3,430 (the pines) |

**The shutter** (inside lane, step 1 and 2): eight slatted panels per tip window, each its own model
(`tip_shutter`, tone `d`), dropping 1.17 m into the low wall when open; the closed pose in `interior.toml`'s
`shutter_closed`, shot with `ship --shoot DIR --shutters closed`; a 12 x 20 cm wall button
(`tip_shutter_button`) on the first facet north of each window, 1.7 m off the window's axis, off the renewer's band.
Not wired: the game track wires the button.

**The smooth skin** (hull lane): one continuous height field cut into a few large pieces (top, brow, belly, mouth),
no seam grid, no scratches, no hatches; the seams stay only at the canopy rims, the mouth, the ramp and the nozzle
housings; the outside metals in `godot/ship/ship.gd` `METALS` (seams 0, scratches 0, grime 0.05, grain 0.4). The join
step lit the curled tips' outer faces, which read black in the side view (the moon from above and the hero-side key
reach neither): two `flank` lamps in `ship.toml` `[light]` at (+-16.5, 1.0), 1.4 m up, range 9, `flank_lamp` 1.6,
lighting only the outside layer (`light_cull_mask` = `OUTSIDE_LAYER` in `ship.gd`, so no light leaks through the tip
rooms' walls onto their floors), and made `ext_silver_c` (belly, brow, mouth) take diffuse light (metallic 0.6 ->
0.35, roughness 0.4 -> 0.5, grey 0.56 -> 0.62). The curl now reads as dark blue-grey metal.

**Open problems** (worst first):
- The skin reads like draped cloth up close: wavy shading streaks on the tip pods' fronts and the wings, folds from
  the mouth's corners, a small horn on the spine between the canopies (the height field: the pods' sqrt fall-off, the
  0.9 m edge fade, 0.18 m stations; not the shader). Options in "The view from the tip window" above.
- Inside draw calls rose against v1 (tip rooms about 1,120, was 415..620; the hall 2,890): more, smaller pieces and
  the outside drawn behind the walls. Batching or merging per room is the game's import question.
- The tip pods still read as bulges from the top; the open window shows the curled wing tip as a pale triangle.
- The closed shutter reads fairly light under the room's lamps; a darker slat material is the next knob.
- Stale GLBs in `<raw>/ship/v2/pieces` (`tip_louvre*`, `tip_shutter_ta..td`): unplaced, harmless.

## Rebuild B: the hull J (hull lane, 2026-10-22)

The engineer's decisions: the hull is variant J of the blockouts (F's outline, span 30 m, length 18.9 m with the
nozzles, the wing tips rounded in plan, radius 1.5 m, edge 0.3 m), built faithfully: flat wings, no upcurl, the rooms
hidden (no domes, pods or bulges), no tip windows; the two canopies and the three nozzle pods as in J; the night
build's plated, faceted brushed silver with no scratches ("smooth like a ray" meant the shape, not a glossy material);
no outside light strips; the inside (rebuild A) frozen; the clearing only scaled.

- **The shape** is `tools/blender/ship_hull_shape.py`, plain Python: the blockouts' variants and design points (moved
  out of `ship_hull_blockout.py`, which imports them and now reads the corridors' `axis`/`along` keys), a convex hull
  of them (`facets()`, 111 facets for J), the mouth recess cut as four convex pieces per facet plus the recess's own
  faces (`surface()`, 126 faces), `skin(p)` (a point's distance to the outside), `clearance()` (every room's sampled
  walls, roofs and slabs against SKIN 0.15 m), `heights(x, y)` and `outline_rows()` (ship.toml's `[hull]` rows,
  checked by `test_ship_layout`). `[hull] shape = "J"` names the variant; `ship --check` runs `clearance` too
  (`ship_layout.hull_skin`): least skin 0.16 m, no poke.
- **The skin** is `ship_hull_j.py` (builder `j_skin`, pieces `skin_top`, `skin_belly`, `skin_mouth`): each face cut in
  its own plane into plates (rows 1.3 m wide along the facet's span direction, cut every 1.8 m, staggered like
  brickwork; slivers under 3 cm stay open as seams), each plate v1's `_plate` (inset 0.022, chamfer 0.014 deep) in
  one of v1's silvers by a hash, the dark `ext_seam` under-skin 0.025 inside. Flat shaded. `ship.gd`'s METALS are the
  night build's again (brush 0.6, grime), with no scratches and no shader seam grid (the seams are geometry).
- **Gone:** the lead blades, the stripes, the tip windows' glass and frames, the pod housing (J's stern face holds the
  pods), `skin_brow`. The canopies are J's (0.95 x 1.35 at (+-2.25, -3.6), 0.75 high) on `ship_hull_shape.heights`.
  The pods keep their style, placed so their rear ends are J's (y 11.0 and 11.8: J's y less `pod_tail_m`).
- **Legs** at J's spots off the corridors and the tip rooms: front (+-4.6, -3.4), wing (+-11.6, 4.4), stern
  (+-5.0, 8.6); `top` = J's lowest belly under the mount + 0.1 (0.6, 0.63, 0.52); the six ground lamps 0.9 m past
  their feet. The flank lamps moved to (+-17.0, 6.0) beyond J's tips.
- **The clearing** is scaled by `ship_hull.CLEARING_K` 1.25 round the centre (the ground's radii and flat 20 m, the
  dirt patch, the path past its first point, the gate posts, every clearing placement, its height again on the
  ground's facets).
- **Views:** the turnaround views backed off and widened for the 30 m span; `detail_seam` on the plated east wing,
  `detail_floor` and `detail_cables` in the diagonal east corridor; the walk video's corridor and tip-room keys turned
  onto the diagonal axes. The exterior's `in_*` rows stay overridden by ship.toml's.

## Rebuild C: the inside 1 m forward and the throat (2026-10-22)

The engineer's pick "A" (prime-game PR #1314; art#263 comments 6341012901, 6341202614, 6341553197). The hull J's
silhouette, span, length and nose do not change: `ship_hull_shape.design_points` no longer reads the rooms (the hall's
and tip rooms' belly rings, the old mouth corner and TIP_X are pinned numbers), so moving the rooms moves nothing
outside but the mouth notch. Two things had to give, both measured with `ship_hull_shape.clearance`:
- **The belly.** With J's belly pinned, the moved tip rooms' slabs poked 0.27 m out of the rising belly at their front.
  J's rule is a flat belly under every room, so `belly_also` adds the belly rings at the moved rooms too (the old ones
  stay): the plan outline rows, span, length, nose and top are unchanged (test_ship_layout holds the rows); only the
  underside's front facets differ (117 facets, was 111).
- **The hall's front rim.** J's lead edge leaves no 0.15 m skin over a 3.2 m rim 1 m further forward (at -30 deg the
  hall wall's top had 0.02 m). The rim is 2.75 m (`front_clear_h`) from -15.11 deg round the front to -164.89
  (`front_from_deg`): the throat's four sub-facets and the front sockets' flats; their ceiling panels run from the lamp
  ring (unchanged) down to the low rim, with a fold (`hall_ceil_step`) at -15.11 / -164.89 where it meets the full rim.

| What | Built |
|---|---|
| Hall | (0, -1), r 4.0; the throat's opening -135.62..-44.38 deg from its centre (four sub-facets of 22.81 deg), the front sockets' flats -44.38..-15.11 (29.27 deg, the back sockets' width), one front facet -15.11..3.23 to each corridor |
| Tip rooms, corridors | (+-8.3, 3.0); axes (0, -1) to (+-8.3, 3.0), the same 9.214 m and 25.73 deg; about 1 m of hull behind the tip rooms |
| Throat | ship.toml room `throat` (shape `poly`): mouth x +-1.65 at y -7.1, the walls straight to the hall's vertices (+-2.915, -3.852), 3.485 m long, four modules of 0.871; walls vertical to 1.45 m, then 0.55 m in to the 2.3 m ceiling (2.9 m over the ground: the capsule and its margin); roof from y -5.476 aft (0.15 m of hull over it there; forward of it the nose is too low: an open notch) |
| Notch | `ship_hull_shape.cutters`: "notch" (between the walls' outer faces, forward of y -5.476, all heights) and "belly" (between them, aft to the hall's corners, below the slab); the lintel over the roof line stays; `skin_cheeks` (`ship_hull_j.j_cheeks`) plates the walls' outer faces where the belly rises over the deck |
| Ramp | hinge (0, -7.1), foot (0, -9.9), 3.3 m wide, 12.1 deg |
| Spots | console (0, 0); vents on the throat's walls (+-2.175, -5.751), asked (+-2.3, -5.8), snapped 0.134 m; sockets (+-1.800, 2.512) and the front two (+-3.426, -2.958), asked (+-3.5, -3.0), snapped 0.085 m onto their flat; breakers (+-6.030, 0.241); renewers (+-9.922, 3.781) |

The interior generator works round the hall's centre (`ship_interior.HALL_C`): the builders are unchanged in their
frames, `ship_interior_place.put` adds HALL_C to every placement; the throat's floor (`throat_floor`: plates either
side of a grate strip, the dark slab) and ceiling (`throat_ceil`: the flat ceiling between the chamfers and the header
under the low rim) are built in hall-relative plan coordinates; its walls are the corridors' modules (`th_*`, prof
`throat`): plain (`cor_wall_mid`) over the vent's 1.6 m band, a cable bay in the last module, chamfers under the roof.
The v2 mouth passage's pieces, the mouth frame and lights are gone.


## Rebuild D: the review's findings and the throat's look (2026-10-22)

- **The skin check reads the layout it is given.** `ship_layout.hull_skin(layout)` passes the layout's rooms to
  `ship_hull_shape.clearance(name, rooms)`; for J, `interior_points` samples the hall, the throat, both corridors and
  both tip rooms each on its own (it read ship.toml once and mirrored the east rooms, so a west room could poke out
  unseen). Round walls every 2.5 deg on the polygon circumscribed about them (a wall face between two samples lies
  inside them), straight walls every 0.15 m with both ends; the tip walls at the slab, mid-wall and rim (the old
  window's sill and head heights stay for the blockouts only). The hall's wall within 0.25 m of the throat's corners
  is the throat wall's joint (its outer face is the notch's cut) and is not sampled. The least skin is 0.150 m.
- **New checks.** `check_polys` (a poly room convex, its points with a positive signed area in plan (x, y), the order
  `poly_edges` reads as inward on the left) and `check_walk` (every walk point on the deck on a room's floor with the
  capsule's radius round it). `--shutters` and `ship_layout.pose` are gone; the reflection probes no longer read the
  retired `window` key (every room but the throat stays an interior probe at `probe_intensity` 0.15, the tip rooms
  too, as in step C's shots).
- **The saw-toothed floor seam** by the throat was the throat's sub-facet half angle with the wrong sign
  (`ship_interior_place.PHI_THROAT` -11.41): the hall's rim plates and low ceiling panels over the throat's four
  sub-facets were built inside out. With +11.41 the rim plates run from the amber ring to the sub-facets' chords,
  where the throat's floor plates start.
- **The cheeks** (`skin_cheeks`) are in the mouth's dark plates (`skin_mouth`'s `hull_dark`), so each side of the
  mouth reads as one dark face, cut face and cheek, up to the nose's slope.
- **The throat's arch** (`th_arch`): the corridors' arch (band, stepped rim, cyan strips) at the roof line (its
  mid-plane 0.1 m aft of y -5.476), over the ceiling and both chamfers only: the vents' plain walls stand below it.
  The throat's cable bay is the module by the hall (C); it has no ceiling ribs.
- **The front legs' mounts** rise 0.25 m more (`leg` arg `rise`): the belly over them climbs to 1.05 m, over the
  mount's old top (1.02).
- **The detail views** `detail_floor` and `detail_cables` look into the corridors from the hall's centre at (0, -1).
