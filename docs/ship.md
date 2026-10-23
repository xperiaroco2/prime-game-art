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

Raw output (never in git): `<raw>/ship/v3/` (the layout's `raw_dir`; v2's in `<raw>/ship/v2/`, v1's in `<raw>/ship/v1/`) with `pieces/` (GLBs, `build_report.json`, validator `reports/`),
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
| Footprint | the hull P, live since lens step 2: span 26.11 m, 22.1 m long with the nozzle pods (blockout6 measured 22.15); `[hull] shape = "P"`, its rows `ship_hull_shape.outline_rows("P")` | the manager's pick P under the engineer's standing instruction (art#263 comment 6344490367) |
| Deck | floor at h 0.6 on landing legs (launch 3; was 1.0), slabs 0.25, walls 0.2 | the ramp meets the ground; a thinner hull |
| Hall | circle r 4.0 at (0, -0.4) (rebuild E; C (0, -1), v2 (0, 0), v1 r 3.4); 3.2 m to the ceiling's rim all round (rebuild E; C had 2.75 m round its front), 3.8 m to its apex (faceted, 16 sides, the four diagonal pairs of facets made one flat chord each for the vents and sockets) | 5a mirrored: round, 8 m across |
| Throat (rebuild C; v2's mouth passage x -1.3..1.3, y -4.6..-3.9) | the funnel from the mouth (x +-1.65 at y -7.1, J's nose edge; 5a: y -8) to the hall's vertices (+-2.915, -3.252), 4.051 m walls in five modules of 0.810 (rebuild E); open to the sky forward of y -5.561 (the walls there are the hull's jambs, `skin_cheeks`), a 2.3 m ceiling aft of it | the only way in or out (5a's side hatch is dropped, see below) |
| Ramp | 3.3 m wide (the mouth), hinge (0, -7.1) at the deck, foot (0, -9.9) on the ground: 12.1 deg, 2.86 m long (rebuild C; v2 2.6 m from (0, -4.6)) | north at the centre |
| Corridors | `strip` rooms on the axes from the hall's centre (0, -0.4) to the lens rooms' (+-10.5, 1.2) (lens step 1): 10.621 m, 8.66 deg aft; floor 3.708..9.298 along the axis (5.59 m), 3 m wide, straight, 2.4 m high (walls vertical to 1.45, then chamfered) | 5a mirrored: straight, about 3 m wide |
| Lens rooms (ids `tip_e`, `tip_w`) | circles r 2.0 at (+-10.5, 1.2), the outer wall at +-12.5; the ceiling slants down outward (P's: clear 2.4455 at the corridor's wall face, 2.3545 at the outer one; `clear_h` 2.35, `clear_h_in` 2.45); the window band -65..+45 deg round the outward axis, + aft, sill 1.0, head 2.2 (`band`); one round roof window, the oculus (`oculus`, 1.4 m clear, 32 sides; details 1, was three 0.9 x 0.7 m) | P's lens (art#263 comment 6344490367) |
| Stations (not built) | console (0, 0.6) clear floor; vents on the throat's slanted walls (+-2.409, -4.791); sockets (+-1.800, 3.112) and the front two on the hall's flats (+-3.426, -2.358); breaker boards (+-6.664, -0.902) in the middle of the corridors' front wall; renewers (+-10.269, 3.237) on the lens rooms' aft wall (a vertex, 87.82 deg aft of the axis), the player at (+-10.415, 1.945) | lens step 1; the vents as in "Rebuild F" |
| Vault (lens step 1) | `rect` x +-0.9, y 3.85..5.85 (1.8 x 2 m clear), `closed`: its shut door (1 m) in the hall's back wall at (0, 3.6), no exit, no link, not walkable floor (`check_closed`); ceiling 2.3 m at the door, 1.6 at the back (`clear_h_back`) | a shell only: no item, card or lock |
| Player | capsule r 0.4, 1.8 m; every room keeps 0.5 m above it | the game's capsule |

The check holds: the footprint within 0.5 m; corridors `corridor_width_m` (3) +- 0.1 m wide and over 2.5 m long; the
tip rooms' outer wall at `tip_outer_m` (12.5) +- 0.05; the station spots (`check_spots`, "Version 2" below); clear heights over the capsule and margin; exactly one room with an exit, the ramp's hinge on its north
edge, the ramp as wide as the mouth and under 30 deg; every room reachable from the hall and linked rooms meeting;
every poly room convex, its points with a positive signed area in plan (x, y) (`check_polys`); every capsule walk
point on the deck on a room's floor with the capsule's radius round it (`check_walk`); every room's sampled outer
surface inside the live hull (P) with 0.15 m of skin (`hull_skin`: `ship_hull_shape.clearance` on the checked layout's own
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
tools/run.sh ship --motion DIR          # step 2: the vents' moving parts on their GLBs off-screen: numbers, MP4, sheets
```

Runs over 180 s go to the background with their log (CLAUDE.md, "Shell"). A snapshot of the whole after launch
2's join (2026-10-22; superseded: `ship --check` prints the current pieces and placements, 157 and 1226 at aa561f1): 139 pieces, 1094 placements (the clearing's 162 pines, 26 bushes, 6 logs, 5 stumps, 160 tufts and 8
party-light posts among them), 59310 triangles per piece set, glTF-Validator clean; extent 26.46 x 13.9 m;
`--godot`: Godot sizes equal Blender's, 105 colliders, the capsule walk reaches all 14 points (18.8 s);
`--walk`: the 1280x720 walk-through, 89.5 s, 2149 frames, 12.8 MB (rendered in 313 s); `--shoot`: 14 views and
their compare sheets, 415..620 draw calls inside the tip rooms, 1740..2032 outside. Times: `--build` about 2 min,
`--godot --walk DIR --shoot DIR` about 10 min.

## The exterior (EXTERIOR lane)

The outside is the hull P (`ship_hull_shape.py`, plain Python; variant P is live, J and the blockouts' variants stay
for reference) built by `ship_hull_j.py` as
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
- **Lamp groups** scale per room: `hall_lamp` 0.7, `corr_lamp` 2.6 (three ceiling lamps a corridor), `tip_lamp` 2.4
  (the lens rooms' group `tip`: the room's omni and the cool fill by the window; the group's scale, not the
  `tip_lamp` piece, which details 2 stopped placing), `out_lamp` 2.5 (warm camp lights at the treeline, x +-27, and
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
  checked by `test_ship_layout`). `[hull] shape = "P"` names the variant (J's numbers here are rebuild B's);
  `ship --check` runs `clearance` too (`ship_layout.hull_skin`): least skin 0.150 m (the throat, hull P), no poke.
- **The skin** is `ship_hull_j.py` (builder `j_skin`, pieces `skin_top`, `skin_belly`, `skin_mouth`): each face cut in
  its own plane into plates (rows 1.3 m wide along the facet's span direction, cut every 1.8 m, staggered like
  brickwork), each plate v1's `_plate` (inset 0.022, chamfer 0.014 deep) in one of v1's silvers by a hash, the top
  and the belly alike, the dark `ext_seam` under-skin 0.025 inside. A cut plate thinner than 3 cm (2 area / perimeter)
  is laid flush, with no inset, so every piece of every facet is plated and only the neighbours' chamfers draw its
  seam. (Until the belly fix of 2026-10-22 the belly drew every third plate in `leg_metal` and left the slivers open;
  the side view showed both as black patches and streaks, "camouflage". `test_ship_hull_detail` now holds the outside
  to the silvers and every facet's plates to its whole area.) Flat shaded. `ship.gd`'s METALS are the
  night build's again (brush 0.6, grime), with no scratches and no shader seam grid (the seams are geometry).
- **Gone:** the lead blades, the stripes, the tip windows' glass and frames, the pod housing (J's stern face holds the
  pods), `skin_brow`. The canopies are J's (0.95 x 1.35 at (+-2.25, -3.6), 0.85 high since details 1) on `ship_hull_shape.heights`.
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

Superseded by rebuild E and F (below): the table holds C's numbers as built then (hall (0, -1), the low front rim,
the throat's corners at y -3.852, four modules), kept as history.

| What | Built (rebuild C) |
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
- **The detail views** `detail_floor` and `detail_cables` look into the corridors from the hall's centre at (0, -1)
  (superseded: rebuild E moved them 0.6 m forward with the inside, from (0, -0.4)).

## Rebuild E: the hall's full rim and the inside 0.4 m forward (2026-10-22)
The engineer kept the hall's ceiling at full height (art#263 comment 6342342554): C's 2.75 m front rim
(`front_clear_h`, `front_from_deg`) and its fold piece `hall_ceil_step` are gone; the hall's rim is 3.2 m all round.
- **The shift.** The inside moves forward of step A (hall (0, 0), tips (+-8.3, 4.0)) only as far as the hall's whole
  wall top keeps 0.15 m of skin under J: s = 0.40 m (searched in 0.05 m steps, rounded down). At s 0.45 the hall's rim
  over the throat's opening (where the hall's ceiling meets the throat's header) keeps 0.139 m, under the 0.15; at
  0.40 it keeps 0.165 m and the wall top elsewhere 0.177 m (the least at the throat's corners).
- **Built:** hall (0, -0.4); tip rooms (+-8.3, 3.6); corridor axes (0, -0.4) to (+-8.3, 3.6) (the same 9.214 m and
  25.73 deg). The throat keeps its mouth at the nose edge (x +-1.65, y -7.1); its corners move to (+-2.915, -3.252) on
  the hall's same vertices (-44.38 / -135.62 deg), so its walls are 4.051 m (C 3.485): five modules of 0.810. Its
  roof starts at y -5.561, the first module line aft of y -5.77, where J's top first gives 0.15 m over the roof.
- **Spots:** console (0, 0.6); sockets (+-1.800, 3.112) and (+-3.426, -2.358); breakers (+-6.030, 0.841); renewers
  (+-9.922, 4.381); the vents' asked (+-2.3, -5.8) snapped 0.211 m onto the longer walls: (+-2.099, -5.734), normal
  (-+0.950, 0.312) (superseded by rebuild F: (+-2.409, -4.791), off the jamb).
- **J's underside.** C's belly ring under the hall is removed: on step A's ring the hall's slab keeps 0.18 m. The
  tip rooms' ring stays, moved to (+-8.3, 3.6) (`belly_also` holds (x, y, r) rings): without it their slab fronts
  keep 0.10 m. J's outline, span, length, nose and top are unchanged.
- **The skin check** (`ship_hull_shape._room_points`) samples the hall's rim over the throat's opening ("hall rim")
  and the wall's ends at the opening's corners. D's skip of hall wall samples by the throat's corners is narrowed to
  the slab bottom: that point is the edge of the throat's open underside (the "belly" cutter's back plane runs
  through the hall's corners, 0.014 m from it). The wall above it is checked (its top keeps 0.152 m there).
  `ship --check` prints each room's least skin: hall 0.152, throat 0.150, corridors 0.180, tip rooms 0.180. Behind
  the tip rooms 2.1 m of hull is left in plan (the least margin, 1.25 m, is on their lead side).
- **The pale boards beside the mouth** were the throat's wall modules forward of the roof line (`th_wall_low`,
  `th_wall_mid`: interior silver, flat tops at 2.05 m, standing free under the open notch), not the cheeks. Forward
  of the roof line those modules are gone; `skin_cheeks` (`j_cheeks`) now also builds the jambs: each wall there is
  a solid in the wall's thickness from the slab up to J's top over it, its inner face in the hull's plates
  (`hull_silver`, `ext_silver_b/c`), its sloped top and front edge in `hull_silver`. The amber floor lights stay
  (two a side, at 1/5 and 4/5 of the wall).

## Rebuild F: the hole at the mouth's corners, the vents, the floor's bar (2026-10-22)
- **The hole.** J's notch is cut `WALL` beyond the throat's walls up to J's top; at the roof line its back face (the
  lintel) closes it only above the throat's roof (`TH_TOP`), and the covered part behind closes only its own profile.
  Between that profile's chamfer and the notch's side, under the lintel, the hull's hollow stood open: sky and pines
  showed through its one-sided skin at both upper corners of the mouth. `skin_cheeks` now carries `jamb_cap`
  (`ship_hull_j.jamb_caps`, `hull_dark`, both windings): a cap per side 1 cm aft of the roof line (behind the arch's
  face and the lintel), from the slab up under the lintel, from the walls' inner face out past the notch's side, its
  inner edge on the throat's inner profile. Close-ups: the views `in_mouth_ne`, `in_mouth_nw` (from the ramp),
  `in_mouth_ne_side`, `in_mouth_nw_side` (at an angle) and `out_mouth_top` (the notch from above).
- **The dark band across the throat's floor** was J's belly: it rises over the deck forward of the hall (0.78 m at
  the roof line), and its front facet crossed the throat's floor from the roof line to y -5.33 as a bar with sloped
  ends (the side planes' cut). `ship_hull_shape._throat_surface` cuts every hull face inside the throat's covered part
  (between the walls' outer faces, roof line to the hall's corners, slab to roof) with no faces of its own; the
  room's floor slab is the underside there. View: `in_throat_floor`.
- **The vents** stood on the jamb's hull plates (s 1.44 from the mouth; the wall modules start at s 1.62). They are on
  the line between modules 2 and 3 (3/5 of the wall from the mouth): (+-2.409, -4.791), normal (-+0.950, 0.312), so
  their 1.6 m plain band lies on two plain modules (`th_wall_mid`; module 3 lost its cable bay, module 4 keeps it).
  Module 2's centre alone would leave 0.4 m of the band on the jamb.
- **New checks.** A plain wall piece's face lies under every point of a wall spot's band (`plain` boxes in
  interior.toml: `th_wall_mid`, `cor_wall_board`, `hall_panel_flat_socket`, `tip_panel_a/b`); `check_walk` samples
  every deck segment of the walk every 0.25 m with the capsule's footprint on the rooms' floors. The throat joint's
  slab skip is the thin zone's width (`WALL + 0.12`).

## Lens step 1: the lens rooms, the corridors and the vault (2026-10-22)

The approved layout (art#263 comment 6344490367; hull P of `tools/blender/ship_hull_blockout.py`, the manager's pick
under the engineer's standing instruction): the nose, mouth, throat, vents, hall, console and the four sockets as
built; new lens rooms, longer corridors, a closed vault. `[hull] pending` stays until step 2 builds P as the live hull:
J's own rooms are pinned in `ship_hull_shape.J_ROOMS`, so J and the blockouts build as before, and
`test_the_lens_rooms_and_the_vault_are_ps` holds the layout's rooms equal to P's design numbers (`RAY_TIP`,
`RAY_ROOM_R`, `RAY_CLEAR_*`, `RAY_PANELS`, `VAULT`, the band's `SILL`/`HEAD`), whose blockout measured 0.15 m of skin
round the rooms and 0.18 m round the vault.

| What | Built |
|---|---|
| Lens rooms | r 2.0 (vertex radius 2.05) at (+-10.5, 1.2), 12 wall facets of 21.95 deg (vertex 0 on the axis), the door's chord over +-48.27 deg from the back (half width 1.53); walls 2.35 m; the ceiling `tip_clear(t)` = 2.35 + 0.1 (2.2 - t) / 4.4 along the axis, a coffered plane in cells round the roof windows, four ribs across the axis (u -1.0, -0.55, 0.825, 1.8) with cyan strips, a fascia over the walls; the lamp ring r 0.32 (was 0.42) at the centre, raised 0.05 m up the slant |
| Window band | facets 3..7 of the east room: -65.86..43.91 deg round the outward axis (the asked -65..+45 snapped to the vertices), + aft, the west room mirrored; per facet `tip_window_a/b` (low wall and panel, sill ledge, header to 2.35, trim), `tip_glass` 6 cm behind the face, `tip_sill_strip`; `tip_mullion` at the four inner vertices, pilasters at the band's ends; P's trail fin hides its band from +45.0 deg (blockout6 `hidden_deg`): the aft edge at 43.91 is 1.1 deg short of it |
| Roof windows | three, 0.9 along x 0.7 across, centres (0.35, -+0.8) and (1.3, 0) from the room's centre along/across the axis: a frame 6 cm wide, a dark well up to 0.26 m over the ceiling, the glass at 0.24 m |
| Door and pilasters | `tip_portal` and `tip_pilaster` 2.428 m (the slant at the door's chord); trunks 2.40 m at the fore vertices (-87.82, -109.77 deg), none within 25 deg of the renewer |
| Corridors | five modules of 1.038 m from u 3.918 to 9.107; arches at 4.150 and 8.875; four ceiling ribs; the breaker board's plain wall at u 5.612..7.412 |
| Hall | the corridors' openings at +-8.66 deg (+-13.84..31.16); the front socket's flat chord from the throat's corner to the opening (30.54 deg, `_sockf`, its plain panel 1.72 m: the spot 0.045 m off its middle); a side facet 31.16..48.23 (`_side`); the back socket's flat 48.23..77.5 unchanged; the vault's door 77.5..102.5 (`hall_door`, a flat chord at apothem 3.981 over the two back facets, which keep their ceiling panels and rim plates); no hall trunk (the back's at 90 deg was the last) |
| Vault | `vault_shell` at (0, 3.85): walls with the corridors' panels (kick, lower panel, belt at 1.4, upper panel), the door's lining, the ceiling 2.3 m at the door to 1.6 at the back (heights over 1.5 m scaled to it), two ribs, a lamp fixture (no light: the door is shut); `hall_door` 1.0 x 2.1 m, its leaf closed with two raised panels, a handle and an amber lamp |
| Light, walk, views | corridor lamps at u 4.9, 6.51, 8.12; the lens lamp at its centre, h 2.85, the cool fill 1.3 m out on the axis; walk points at u 3.0 and 0.5 m past the lens centres; views `in_corridor_*` toward the lenses, `in_tip_*` toward the windows, `in_lens_roof_e` up, `in_vault_door` |

Left for step 2 (the hull lane): P as the live hull round these rooms (the window band's and roof windows' openings
through it, the legs' clear zones), then drop `pending`; the walk-through video's keys (`test_the_walk_video_keys`
skips while pending).

## Lens step 2: the hull P built (2026-10-22)

P (art#263 comment 6344879087) is the live hull: `[hull] shape = "P"`, `pending` gone, so `ship --check` runs the
footprint, skin and inside-the-hull tests again and no ship test skips.

- **The shape** (`ship_hull_shape.py`, the section at its end; `DEFAULT = "P"`): the UNION of five convex parts
  (`p_parts`, `p_facets`): the body (the hump over the hall from J's own top, the nose, the vault, the tail), two fins
  (a ridge 3.30 m over each corridor, 1.85 / 2.05 m half wide, the thin diamond edges) and two lenses (48 sides, rim
  r 2.55, the top plane 0.275 m over the slanted ceiling, `P_PROFILE`). `skin(p)` is the best part's plane distance (a
  lower bound of the union's), then J's notch cutters; `heights` the union's highest top and lowest bottom;
  `surface()` every part's facets outside the other parts (a face on another part's boundary kept once, `EPS`), split
  only where a region really meets it (`_meets`), J's throat cuts, then the openings (`p_openings`): the window band
  as wedges between the rim's vertices from r 2.13 (the room wall's outer face is 2.21) out, sill 1.596 to head 2.804,
  and three roof windows per lens (0.9 x 0.7, P's outlines) from 0.245 m over the ceiling up (the wells' tops 0.26);
  the cutters' own faces close every cut (the band's sill, head and ends, the roof windows' sides), plated like the
  hull. Faces thinner than 0.1 mm (hull artefacts) are dropped. 507 facets, 1140 faces (lens step 3).
- **The corrections.** The tail tapers to the pods: the stern face `P_STERN` is 2.75 m half wide at most and sloped
  (the blockout's stood 4.0 m with near-vertical sides behind the hall), the fins' trail corners come in to
  (+-3.3, 12.3). The fins' roots on the rim sit at -72 and +50 deg round the lens's axis, 6.1 deg past the band's
  ends (-65.86..+43.91), and the fins' edges come down to h 1.35 there (`P_LENS_EDGE`, under the 1.6 sill): no point
  just outside the band (sill to head, -72..+48 deg) lies inside the hull.
- **The skin check** (`_room_points`) samples the lens rooms' slanted ceilings (`ceiling = "slant"`, along the axis
  from the hall's centre) and the closed vault (walls, its roof falling from 2.3 to 1.6, slab). Least skin: hall
  0.152, throat 0.150, corridors 0.180, lens rooms 0.171 (0.155 before lens step 3's 4 cm lift), vault 0.180.
- **Plating:** `ship_hull_j.py` (name kept) plates P's faces as it plated J's: all silver, every sliver laid flush.
- **The edge light** (`edge_light`, `ship_hull_shape.p_edge_line`): a dark channel (lips 14 mm proud, 8 cm high) with
  a cool-white glow 3.5 cm high set 8 mm in, along each fin's lead edge from the nose (not across the mouth), round
  the lens rim at h 1.35 under the band and along the trail edge into the outer pod. `glow_edge` lights at
  `l = 0.12` (a faint glow on the ground).
- **Frames:** `lens_frames`: the band's sill and head bars on the rim, two end posts, four mullions in the reveal at
  the room's inner window vertices; a raised 5 cm frame round each roof window.
- **Pods:** 2.84 / 3.24 m across (`P_PODS`, `p_pods`), the noses at y 9.6 inside the tail, the ends at 14.7 / 15.0;
  the bell is an open ring into a nozzle 1.15 m deep (`NOZZLE`), the glowing inner ring 0.3 m in, `glow_pod` at
  `l = 0.15`.
- **Legs:** front (+-4.6, -3.4), fin (+-9.0, 4.6) (J's (+-11.6, 4.4) lies outside P), stern (+-5.0, 8.6); mounts at
  P's lowest belly over the mount's box + 0.1 (0.64, 0.44, 1.17). Ground lamps 0.9 m past the feet.
- **The vault:** its door is a closed sliding hatch (stepped frame, cyan header strip, two recessed panels, a groove,
  a cyan edge strip, a card reader with a small dim light); a dim warm lamp (`corr`, 0.1) under its fixture.
- **Views:** `out_lens_e`, `out_lens_roof_e`, `out_tail`; `detail_floor` and `detail_cables` and the walk video's
  corridor and lens keys on the 8.66 deg axes.

## Lens step 3: the plates in rows (polish, 2026-10-22)
The hull P's shape is kept; its surface was messy: every facet plated in its own frame, so the union's sliver facets
fanned their seams out round the fins' roots, and the lens's 48 rim facets read as slats (a corrugated tank).
- **Plates by zone, not by facet** (`ship_hull_j.cells`, `skin_pieces`). Every face is in one zone with one seam
  family. Plan: global planes, rows span-wise (constant plan y; a face looking fore or aft: constant h), the plates'
  ends on constant x (a face looking sideways: constant h), brickwork. Lens (a face within the rim's radius of a
  lens's centre): the rim and the under faces in three bands (seams at h 1.35 under the edge light and 2.8 at the
  band's head) with radial seams every 36 deg, staggered by 18 per band; the top and bottom discs, the sill and the
  head in a ring of 36 deg sectors outside a ten-gon of apothem 1.5 m, rows along the lens's axis inside it. The west
  lens is the east's mirror.
- **Seams only where meant** (`Edges`, `seams`, `lay_seams`). A piece's edge is a seam (v1's inset and chamfer) where a
  seam plane cut it, where the face ends (an opening, a cut) or where the next face bends away by more than
  `CREASE` (plan 20 deg, lens 30 deg); across a shallower facet edge it is laid flush with no chamfer, so a plate goes
  on over the next facet and no seam follows a sliver. A plate's pieces share one silver (`cell_mat`, by its cell).
- **The lens shaded smooth.** The lens's plates are their own parts with `smooth_deg` 30 (`ship_build.make`: sharp
  over it), so the rim reads as wide curved plates; at 40 the rim's top chamfer (33.7 deg) smoothed into the flat top
  and blotched it. The body and the fins stay faceted.
- **The lens's top 4 cm up** (`P_TOP_LIFT`): the fin's ridge (3.30 at the lens's centre) stood 2.5 cm proud of the old
  top, a ledge across the roof. Lowering the ridge instead cost the corridors 3 cm of skin (0.180 -> 0.152).
- **The edge light**: the glow 6 cm high (`EDGE_GLOW` 0.03), strength 16, in 4 m pieces (`EDGE_CHUNK`): Godot puts one
  strip light per piece, so they stand along the edge and pool faintly on the ground (`glow_edge` l 0.6); one merged
  mesh had put its one light in the ship's middle.

## The light layer (outside at night, 2026-10-22)
The engineer approved the lens ship and the manager's light plan; the inside's lamps and energies are unchanged.
Raw output: `<raw>/ship/v4/light/` (shots), `light-before/` (the same views before), `logs/`, `notes/light.md`.
- **The edge light** stays a continuous cool-white line. Its strip lights (`glow_edge`, one per 4 m piece) stood at
  their pieces' AABB centres, up to 1.8 m high over the fins, and left small bright hot spots on the silver near the
  edge. They now light only the inside layer (`[light.mats]` `cull = "inside"`, read by `ship.gd _dress`): the lens
  rooms keep the light that came in through their windows. The pool on the ground under the edge is six cool spots
  (`edge` lamps, `edge_lamp` 0.8): under each lead edge, lens rim and trail edge, 0.8 m outside it, under the edge's
  height, pointing down (55 deg), so the fins above lie outside their cones.
- **Spots:** a lamp row's 11th number is a spot angle in degrees: `ship.gd` makes a `SpotLight3D` pointing straight down.
- **Navigation lamps** (`nav_red`, `nav_green`, `nav_white`; `ship_hull_detail.nav_lamp`): a round silver housing, a dark
  bezel and a glowing lens (`glow_nav_*`). Port red on the west lens rim's forward facet (-48.75 deg plan, under the
  edge light at h 1.13), starboard green on the east's, white on the tail's top centre (y 11.2). Each has a tiny
  unshadowed omni 0.45 m out (`nav`, `nav_tail`; range 1.0, `nav_lamp` 0.05: more painted a coloured blob on the rim).
  `ship.gd`'s `nav_blink` (default true, the game) flashes the white lamp 0.12 s once a second and pulses red and green
  0.55..1.0 over 2 s, lights and lenses together; the shoot and video requests send `"nav_blink": false` (a static glow).
- **Landing lights** (`landing_lamp`): a silver housing with a warm lens under the belly by each of the six legs,
  0.8 m inboard of the mount, on the belly's bottom (`ship_hull_shape.heights`); each a warm spot (`land`, 65..75 deg,
  range 4, `land_lamp` 1.6). They replace the three orange belly pools.
- **Windows:** unchanged. From outside the band shows the lit lens room and the roof windows its warm floor; a
  glass shader with a warm glow seen only from outside (a pane's normal away from its lens's centre) was tried and
  showed no glow in the shots, so it was dropped (open: the west band reads dark at a grazing angle in `out_far`).
- **Engine rings:** `glow_pod` `e` 0.6 (the bands clipped pale cyan-white in out_back).
- **Views:** `out_far` (the first sight from the clearing's edge by the path, 26 m, eye height); `top_full` and
  `top_full_day` (the whole ship from straight above, orthographic, 27 m high, south up; the day shot swaps in a sun
  and a pale sky after the night shots). `tools/tests/test_ship_light.py` checks the lamps' placement.

## Details 1: the oculus, the cockpits, the band's glow (2026-10-22)
The engineer's pick (art#263 comments 6347287605, 6347388160). Raw output: `<raw>/ship/v4/details1/` (shots),
`logs/`, `notes/details1.md`.
- **The oculus.** Each lens room's three square roof windows are one round window, `oculus = {d = 1.4, sides = 32}`
  in ship.toml: 1.4 m clear, centred on the room. `ship_hull_shape.p_openings` cuts it from the layout as a 32-sided
  prism (side k's normal at k 360/32 deg from the lens's axis) 2.5 cm outside the clear radius (`P_OCULUS_R` 0.725,
  the well's lining), its floor 0.245 m over the slanted ceiling and parallel to it; the cutter's own sides close the
  cut. Inside (`ship_interior.tip_ceiling`): the slab round it (per side a sector clipped to the room), face panels in
  eight sectors, the well's dark lining (`OC_WELL` 0.70..0.735: 1 cm into the hull's cut, up to 0.26 m) and the
  glass at 0.24, all on the slant. Outside (`lens_frames`): a thick silver ring frame (`ext_silver_b`) from a lip
  1 cm over the cut's edge and 4 cm into it, 20 cm out over the plates, its crown 8.5 cm proud. The ceiling's ribs
  moved outside the ring (`TIP_RIBS`, x +-1.12 and +-1.55).
- **The light ring.** The centre's lamp ring piece (`tip_lamp_ring`) is gone; tip_ceiling's light ring is in its
  style round the oculus: a silver beam (r 0.71..0.99) under the ceiling, a lip round the opening, the warm band
  (`int_lamp`) on the beam's whole underside, the six `tip_lamp` fixtures under it at `R_TIP_RING` 0.86. The room's
  omni (`tip`, h 2.85) is unchanged, so the light level holds: in_tip_e's mean luminance 94.6 before, 100.6 after.
- **The cockpits** (`ship_hull_detail.cockpit`, the canopies' `glow` part). The glass is lighter (`glass_canopy`,
  alpha 0.28, no warm tint) and 0.85 m high (was 0.75). Under it: the warm floor in rings 8 cm over the deck (one fan's
  chords dipped under the convex hull), a warm glow ring at the glass's foot, a pilot's seat facing forward (-y):
  pedestal, pan 0.5 m wide 0.17 m up, a back and headrest 0.61 m long reclined 40 deg, two armrests (`ext_seat`, a
  less metallic silver that catches the glow; dark pads `ext_frame`), and a console 0.5 m ahead with a sloped face,
  a shelf, two grips and three cyan screens (`ext_screen`, `[light.mats]` e 2.0, l 0). Every vertex stays 2 cm
  under the glass (`glass_h`, test). Outside only, as before.
- **The band's glow.** A faint warm emissive pane in each lens band's reveal (`band_glow`, r 2.32, sill to head,
  `ext_window_glow`: alpha 0.18, emission 3.0, `l` 0), ONE-SIDED: a library material's `"cull": True` sets Blender's
  backface culling, so the glTF is not double-sided and Godot culls its back; it faces out, so the room does not see
  it. The band now reads warm in out_far.
- **Small fixes.** The tail nav light moved to h 4.715 (0.45 m out, as the other two). `ship.gd _day` hides the moon
  and the key and leaves the sun unshadowed (a clean day). `[shots] day_views` are shot by day after the night's
  views (`out_canopy_e_day`). New views: `in_oculus_e`, `out_oculus_e`, `out_canopy_top`, `out_canopy_e`.

## Details 2: the light ring, the portholes and the hull's fittings (2026-10-22)
The engineer agreed to the manager's detail plan (art#263): the shape, the rooms, the lights and the look stay; detail
only. Raw output: `<raw>/ship/v4/details2/` (shots, `walk/`), `logs/`, `notes/details2.md`.
- **The light ring** (`ship_interior.tip_ceiling`): a slim warm strip (`OC_STRIP` 7 cm, `int_lamp`) centred at
  `R_TIP_RING` 0.84 in a dark channel (`int_dark`, 12 cm) under a thinner silver beam (8 cm deep, r 0.71..0.97) with a
  rim on its outer edge and the lip round the oculus (11 cm), in the corridor ribs' style. The six `tip_lamp` fixtures
  are merged into the strip (the piece is no longer placed). in_tip_e's mean luminance (Rec. 709, 0-255) 100.0 before,
  100.3 after; the room's omni is unchanged. The ceiling's fascia now reaches `OC_FASCIA` (10 cm) down the walls all
  round the slant (it had 1.3 cm at the corridor's side).
- **The fittings** (`tools/blender/ship_hull_fittings.py`, each piece in the plan frame at the origin; every fitting
  sits on one facet of the live hull, its normal from `heights`' slope):
  - `portholes`: three a side on the tail's flank (the steep face between the body's top and the fin's) at y 5.6,
    6.8, 8.0, where the flank is midway down; at least 2.6 m in plan from any room's sampled surface (the vault's
    roof the nearest), clear of the lens rims and the pods' noses. A bright silver crown 4.5 cm proud on a darker
    flange, a dark bezel and opaque dark glass (`ext_porthole`, a faint warm emission (0.07; details 3: 0.05 round
    a warm core), `[light.mats]` l 0): it glows a
    little at night and never reads as a hole.
  - `tail_vents`: two grilles (0.7 x 0.42 m, six slats tilted 35 deg in a dark well, a silver frame) at (+-1.15, 8.55)
    on the tail's top, ahead of the pods.
  - `hump_sensors`: an antenna mast (0.75 m, two collars, a dark cap; a cross-spar read as a cross) at (0, -1.6) and a
    dark glossy sensor dome (r 0.16 on a silver collar) at (0, -2.9), on the hump's centre line behind the canopies.
  - `service_hatches`: inset outlines (a dark groove 2 cm wide, 3 mm proud), a handle notch with a silver grip and
    four bolts: 0.9 x 0.6 m on each fin's top at (+-5.6, 4.4) (clear of the fin's plate seams), 0.8 x 0.55 on the
    belly at (0, 8.6).
  - `hazard_stripes` (outside): yellow parallelograms at 45 deg every 0.2 m on a dark strip along both ramp rails'
    tops (mirrored slant) and across the mouth's floor edge at the hinge (11 cm deep, over the throat floor's rim).
- **Tests:** `test_ship_fittings.py` (the portholes' sides, flatness, distance from the rooms, the pods and the lenses;
  the vents', mast's, dome's and hatches' spots; the stripes' counts and places). `test_ship_interior` asserts the
  slab overlaps the well's lining, probes r 0.85, the strip's width and the fascia's foot; `test_ship_exterior`
  checks ship.toml's views and day views together for duplicate names.
- **Views:** `out_portholes_e`, `out_vents`, `out_mast`, `out_hatch_e`, `out_ramp_stripes`, `out_lens_under_e`.
- **Not done: the lens's underside bulge.** Under each lens the barrel's lower part (r 2.55 to h 1.0, then 2.47 at
  0.5, 2.3 at the belly) stands below the fin's underside near the fin's roots (the fin's edge there is 1.15 at its
  bottom). Tapering the lens's lower profile is not possible: the room's bottom corner (r 2.21, h 0.35) keeps 0.162 m
  of skin against the present chamfer, and a taper from h 1.2 leaves about 0.11. The blend needs a fairing, a sixth
  convex part per side between the lens's lower barrel and the fin's underside round each root, with its plating and
  the edge light checked; a step of its own.

## Details 3: the fairings under the lenses, the portholes' glow (2026-10-22)
The shape, the rooms, the inside, the lights and the look stay. Raw output: `<raw>/ship/v4/details3/` (shots, `walk/`),
`<raw>/ship/v4/logs/`, `<raw>/ship/v4/notes/details3.md`.
- **The fairings** (`ship_hull_shape.p_fairings`, `P_FAIR = (60, 3.0)`): under each fin root the lens's lower barrel
  stood out of the fin's underside (0.1 to 1 m past the fin within 30 deg of the root: a can under the fin). Four
  more convex parts of the union, `fair_lead_e`, `fair_trail_e` and their mirrors: the convex hull of the lens's low
  barrel (every profile level from the fin edge's bottom, h 1.15, down to the belly) from the root to 60 deg past it,
  and the fin edge's bottom line from the root to 3.0 m along it. Their outer faces fall from the edge's bottom to
  the barrel, so the barrel runs on into the fin's underside as one surface (no seam of its own: the union's
  surface and plating take it in, `skin_pieces`), and end flush on the edge 3 m from the root. Every point lies on
  the lens's or the fin's skin and the union only grows, so no room's skin can thin (not tested: it could not fail);
  nothing reaches inside, the footprint rows skip them (they lie under the fin and lens in plan). They stay 0.14 m
  and more under the edge's mid line, so the edge light runs on above them as it was.
  `tools/tests/test_ship_fairing.py`: the four parts and their mirror, their points on the lens and fin (the far one
  on the fin's skin within 1 mm), a grid finding points inside the fairing and the lens, the fairing and the fin, and
  its own new volume; neither a grid point nor a hull point standing more than `MAX_OUT` 0.45 m out of the lens, fin
  and body; the barrel past the roots standing 5 mm out at most; every point 0.14 m under the edge's mid line (the
  edge light).
- **The portholes' glow:** `ext_porthole` at 0.2 over the whole glass read as flat brown discs; now the glass is
  0.05 and a warm core (`porthole_core`, 0.55 of the glass, 4 mm over it, `ext_porthole_core` 0.6, l 0) averages
  about 0.2. From out_portholes_e the core read as a flat amber disc in a dark ring (a bullseye). Superseded by 3b's
  glow bands (below): `porthole_core` and `ext_porthole_core` are gone.
- **D2's minors:** the porthole test holds the 2.6 m to the rooms (it asserted > 1.0) and 1 m in 3D (height
  included) from every pod's barrel. `tip_lamp = 2.4` in ship.toml stays: it is the lens rooms' lamp group (`tip`, the
  room's omni and its cool fill), not the removed `tip_lamp` piece; removing it would dim the frozen lens rooms; its
  comment and "Lamp groups" above say so now.
- **Views:** `out_fair_lead_e`, `out_fair_trail_e` and the west's (from the side), each with `_below` (from the
  ground under the fin).
- **Details 3b (fixes):** raw output `<raw>/ship/v4/details3b/` (shots, `walk/`), `<raw>/ship/v4/notes/details3b.md`.
  - *The portholes' glow* (`ship_hull_fittings.glow_bands`, `PORT_GLOW = (20, 0.45, 0.03, 1.6)`): the glass's face
    is 20 flat concentric rings 2 mm over the dark glass body (`ext_porthole`, 0.05), each its own material
    `ext_porthole__gNN`, the emission log-linear in (r / glass)^1.6 from 0.45 at the centre to 0.03 at the rim (each
    ring about 15 % under the next in; 3c: 16 bands, 5 mm; see below): a soft warm falloff, no disc and no ring edge. D3's warm core read as an
    amber bullseye. The rings are open faces (closed rings' coincident walls sparkled as dotted circles). Their
    `[light.mats]` entry is `ext_porthole`'s: `ship.gd` looks a material up by its name, else by its part before `__`.
  - *The fairings plated flat:* a face on a fairing's own facet (`ship_hull_shape.p_fair_face`: its plane and normal,
    and on no lens facet) is plated in the plan zone like the fins (`ship_hull_j.cells`); in the lens zone it was
    shaded smooth into the barrel up to 30 deg: a dark smear across several plates with a zig-zag lower edge.
  - *The jambs' top* (`j_cheeks`): the jamb face's plates lay their top edge flush (`lay_seams`; their insets chewed
    the edge against the sky into steps) and the top strip runs `JAMB_OUT` 3.5 cm past the wall's outer face over the
    skin's seam groove (the dark band), `JAMB_LIFT` 4 mm over the skin, 33 samples along the slope.
  - *Seam corners* (`lay_seams`): a seam ending on a flush edge slides its corner along that edge, and the pieces on
    both sides of a facet fold end at one point on it; the exact inset's `INSET / sin` slide per facet differed and
    left hairline black wedges past the groove (by the fin hatch). Hull-wide. (3b slid `INSET` whatever the angle; 3c
    below keeps the groove's width.)
  - *Tests:* `test_ship_fairing.py` asserts a fairing stands at most `MAX_OUT` 0.45 m out of the lens, fin and body
    (grid) and its far point lies on the fin's skin (within 1 mm); the "no room loses skin" claim is dropped (the
    union only grows, so it could not fail).
- **Details 3c (review fixes):** raw output `<raw>/ship/v4/details3c/`, `<raw>/ship/v4/notes/details3c.md`.
  - *Seam corners* (`ship_hull_j.corner_slides`): every seam corner on a flush edge wants the slide `INSET / sin` of
    its angle (up to `SLIDE_MAX` 3 `INSET`), and the corners at one point sliding one way (both sides of a fold) take
    the largest of theirs, so the groove stays `INSET` wide at an acute corner (3b's `INSET` tapered it to
    `INSET * sin`: 186 corners of 25 to 155 deg under 0.9 `INSET`) and the pieces still end at one point.
    (3d below: one cap per group.)
  - *The portholes' glow, cheaper* (`PORT_GLOW = (16, 0.45, 0.03, 1.6)`, `PORT_SEG` 24, `PORT_LIFT` 5 mm): 16
    bands of 24 segments (the glass disc keeps 48), each band one equal step of (r / glass)^1.6, so each glows about
    16 % under the next in, wide at the centre and narrow at the rim; the mean glow stays 0.132. The portholes piece
    went from 15,804 triangles and 24 surfaces to 9,036 and 20. 8 bands (6,732 triangles, 12 surfaces; 29 % steps)
    showed their rings in out_portholes_e. The bands lie 5 mm over the glass's face (3b: 2 mm) against far-view
    z-fighting.
  - *Tests:* `test_ship_light.py` asserts every `__` material has its family's `[light.mats]` row with `l` 0 (and
    `ship.gd` looks the family up); `test_ship_fairing.py` also checks each fairing's own points against `MAX_OUT`.
- **Details 3d (review fix):** raw output `<raw>/ship/v4/details3d/`, `<raw>/ship/v4/notes/details3d.md`.
  - *Seam corners, one cap per group* (`ship_hull_j._slide_cap`, `corner_slides`): 3c shared a group's slide, but
    `lay_seams` still capped each piece at `CORNER_CAP` 0.3 of its shorter edge, so on short edges a group's corners
    stopped at different points: 450 groups ended over 0.1 mm apart (worst 6.5 cm), the black wedges at seam corners.
    Now a group's slide is the largest wanted, capped at its members' smallest `_slide_cap`: `CORNER_CAP` of the
    flush edge, and the slide's part along the seam (`s * |cos|`) at most `SEAM_CAP` 0.6 of the seam edge (with the
    seam's other corner at 0.3 at most, no plate folds over); `lay_seams` does not cap a slid corner again. 0 groups
    over 0.1 mm apart. The cost: 23 corners of 25 to 155 deg between edges of 0.25 m and more (in a group with a
    short member) keep a groove under 0.9 `INSET` (narrowest 0.275 `INSET`); capping by the shorter edge outright
    pinched 186.
  - *Tests:* `test_ship_hull_detail.py` asserts every corner lies on its flush edge, every group (short edges
    included) meets within 0.1 mm, each groove is its slide times sin with the slide within `SLIDE_MAX` and its
    `_slide_cap`, and counts the limits: at most 25 narrow wide corners, none under 0.25 `INSET`; the near-straight or
    needle corners (sin under 1 / `SLIDE_MAX`, 362) and the corners their group's cap stops short (747).


## Station 1: the throat vents (step 2, 2026-10-23)
The first station (art #263, the design session's item 1, comment 6361476098): `station_vent_e` and `station_vent_w`
(`tools/blender/ship_interior_vent.py`, interior lane pieces placed by `ship_interior_place.py`, so `interior.toml`
lists them with their `spot` and `unit`). Raw output: `<raw>/ship/v4/vents/` (`pieces/`, `motion/`, `shots/`,
`logs/`), the notes in `<raw>/ship/v4/notes/vents*.md`.
- **The shape** (the engineer's pick, vent-v2 "box"; reworked in builder step 2 after the manager compared step 1's
  plain grey cabinet with it): a heavy machined box (1.11 m wide, its front 0.48 m out) and a column (0.46 m) on the
  hall's side, both with deep double chamfers (45 deg, 4.4 cm, then a second facet) and 45 deg corner cuts, and a
  groove (1.4 cm wide, 1.2 cm deep) round each front face with the thin `int_cyan` strips lying in it. The gill
  grille takes the whole front inside the frame: its opening 0.17..1.79 m (the top is where the wall's chamfer meets
  the well's back, `cv` 0.2 m), no blank panel; seven gill slats, each a blade with a round 18 mm nose round its
  hinge, swept down and out to a 5 mm tail, bowed 8 mm across its chord and its tail 1 cm along u, shaded smooth up
  to 40 deg (`smooth_deg`). The column holds the palm scanner for a four-fingered hand (a thumb and three fingers, a
  cyan outline on a dark pad sunk in a faceted bezel, centre 1.105 m), the light bar above it (glass 1.325..1.765 m)
  with its green band near the top and the white marker, and the problem lamp near its head: a red dome beacon
  (r 2.6 cm) on a red band, a metal collar and an octagonal base (on its front at 1.855 m: the chamfer leaves no
  room on top). Metals are the hall's own (`cor_wall_*`): the frame `int_silver_a` (tone a's panels), the column
  `int_silver_b` (the wall body), the slats, bezels and collar `int_silver_c` (the belts' and lips' trim). The heat
  is a saturated orange (`int_halo__vent_heat`, emission (1, 0.3, 0.02)) and the lamp a deep red
  (`glow_nav_red__vent_lamp`, (1, 0.015, 0.01)), each with its own `[light.mats]` entry, so AgX keeps them orange and
  red at night (the library strengths washed them to tan and pink). About 3,600 triangles a vent.
- **Room made for it:** the throat's floor light at 4/5 of each wall (`ship_interior_place.py`) moved 0.36 m toward
  the hall (its 0.7 m bar now 4 cm clear of the column); at its old place the bar ran 32 cm under the column's foot.
- **On the wall:** the piece's frame is the spot's (u along the wall, v out of it, h absolute); the backs follow the
  throat wall's profile 2 cm inside it (vertical to 1.45 m, then the chamfer), so the box reaches 2.08 m and the
  column 2.0 m without cutting the chamfer. `ship --check` (`ship_layout.check_units`) holds every station piece
  (a piece with a `spot`) to its spot (placed once, at the spot, its +v on the normal) and its `unit` box inside the
  plain band, the depth and under the room's clear height; `test_ship_vent.py` holds the builder's vertices inside
  the box and behind nothing of the wall.
- **Moving parts** (docs/props.md "Conventions"): the harness (`ship_build.rig`) gives a part with `origin` its own
  object origin (and a part with `parent` its parent). Each slat is a leaf `<id>_slat<k>` (k 1..7 from the top), its
  origin on its hinge (the nose's axis, 9 mm under the slat's top, along x); it opens with
  `rotation.x = -OPEN_RAD * t` (55 deg from its shut 22 deg: 77 deg from hanging; shut, each tail hangs in front of
  the next nose, 8 cm out). The marker `<id>_marker` has its origin at its rest point, the glass's bottom; it slides with
  `position.y = rest + MARK_TRAVEL * t` (0.41 m). Both pieces drive the same way (the west one mirrors x only).
- **Glows the game drives** (their own materials, copies of the library ones; `[light.mats]` by family, l 0):
  `int_halo__vent_heat`, `glow_nav_green__vent_band`, `glow_nav_white__vent_marker`, `int_cyan__vent_hand`,
  `glow_nav_red__vent_lamp`. Colliders: `<id>_col0-convcolonly` (the box), `<id>_col1-convcolonly` (the column); the
  open slats stay inside the frame's depth (0.49 m), so they have none.
- **The motion proof** (`ship --motion DIR`, `godot/ship/vent_motion.gd` in the off-screen window on the imported
  GLBs): every leaf found by its name, two convex colliders; per slat (the count from the request) at 11 steps 0..1 its
  cross-sections' convex hulls against the next slat's (`Geometry2D.intersect_polygons`; a curved gill is not
  star-shaped round its centre, its hull is a safe outline) and its vertices inside the opening, in front of the heat panel
  and within the depth; the upper edge's drift from 0 to 1 (at most 1.2 cm: the edge's own thickness turning) and the
  tip's swing; the marker inside the glass at 0, 0.5 and 1. Then `vent_motion.mp4` (10 s, 1280x720: shut, open,
  breathing, slam shut; the marker up and down), `states_sheet.png`, `sides_sheet.png` (8 sides) and
  `closeups_sheet.png` (on a replica of the throat wall's profile).
- **In place:** `ship --shoot DIR --views in_vent_` shoots the vents at the ship's night look (the throat from the
  hall and the ramp, each vent from 2 m and 4 m), `--views cu_vent_` their edges against the real wall and floor
  close up (`--views` keeps the views whose names start with a prefix; no plan, day views or compares).
- **Way A (art#263 comment 6363433518; builder steps vents-a1 to a3), the current build.** The body (frame, copper
  hinge caps, column, light bar, palm scanner, lamp, feet) is Meshy's multi-image-to-3D model of the concept's body
  views (batch `2026-10-23-ship-vent-a-body`, 35 credits), cleaned, fitted and baked onto 4,000 triangles by
  `tools/blender/ship_vent_a.py` (`<raw>/ship/v4/vents-a/body4k/`), then finished without a new generation by
  `ship_vent_a_finish.py` (`body4k_r2/`: its light-blue texels outside the well repainted bronze, its bronze graded
  toward front_ortho's frame bronze) and `ship_vent_a_sides.py` (`body4k_r4/`: the box's outer side and back, by face
  direction, set to the body's bronze median with the bronze's lightness spread).
  The harness imports the body (a part with `glb`); the lamp, band and hand are the body's surfaces
  `vent_a_body__lamp`, `__band`, `__hand` (each piece starts without materials, so the west copy keeps those names).
  **The blades (step 3)**: one rigid Meshy blade, seven copies. Two procedural tries read from the front as thin
  brown strips, so the blade is an image-to-3D model (item `blade1`, 30 credits) of our own isolated blade shot (an
  edit of the concept at medium, batch `2026-10-23-ship-vent-blade-img`, item `bfront` of three framings, $0.10),
  cleaned by `ship_vent_a_blade.py` (`<raw>/ship/v4/vents-a/blade_r4/`): oriented by its principal axes (the thick
  edge to the wall, the flat side down), its arch cut to 2 cm (front_ortho), the length on the caps' span, the section
  scaled so the calm tip stands 26.5 cm out of the pivot (19 cm past the frame) and the slices' front height is two
  thirds of the 15 cm pitch (squashed 0.92 in h), decimated to 500 triangles and baked, its albedo graded to the
  body's bronze. Its `blade.json` gives the builder its box about the pivot and the seams straight from the front:
  calm 4.7 cm, closed 1.9 cm at `CLOSED_DEG` 33 (36.5 left 7.5 mm, but the bottom blade's tip then dipped below the
  frame's bottom; the first cut of two blades is at 58). A blade part carries `rot_u` (the harness turns the GLB about
  u before placing it) and `hull`, its box's corners for the plain-Python checks; the harness shares the first copy's
  material. The well's glows are two panels on its back,
  `int_cyan__vent_cool` (calm) in front of `int_halo__vent_heat` (the problem: the game hides `cool`). The spots
  `vent_e`/`vent_w` have their own `depth_m = 0.6` (the engineer, comment 6363588759), the units
  `[-0.80, 0.80, -0.01, 0.60, -0.02, 1.82]`. The motion proof for way A: the body's three driven surfaces, each blade's
  origin on its pivot (at most 2 mm), the root's ring round the axis fixed (its chord over the turn plus 4 mm, at least
  1.2 cm), the tip's swing at least 4 cm. Review:
  `ship_vent_a_sheet.py` (the concept's views beside neutral and warm EEVEE, `--game` a last row from the motion
  run's `state_<n>.png`); pieces in `<raw>/ship/v4/vents-a/pieces`, never the layout's `raw_dir`. `ship.gd`'s
  `--vent-states` dims `body:__lamp` calm (a dim entry `<part>:<material suffix>` dims only those surfaces). Not
  yet: the steam.
