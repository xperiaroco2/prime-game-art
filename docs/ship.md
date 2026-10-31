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
| `tools/runner/ship_export.py`, `tools/runner/commands/_ship_export.py`, `godot/ship/export_scene.gd`, `godot/ship/export_check.gd` | the game's package (`--export`, art #335; "The export" below) | shared |
| `tools/blender/ship_video.py` | encodes the walk-through MP4 under its size cap | EXTERIOR lane |
| `tools/tests/test_ship_*.py` | fast: `test_ship_layout.py`, `test_ship_interior.py`, `test_ship_hull_detail.py`, `test_ship_exterior.py`, `test_ship_clearing.py`; heavy (Blender): `test_ship_build.py` | either lane adds its own file |

Raw output (never in git): `<raw>/ship/v5/` (the layout's `raw_dir` since the stations' fix pass, art#263: its `pieces/` the current build, deck at `floor_h` 1.2, byte for byte the vents' `<raw>/ship/v4/vents-b/pieces_b5b`; `<raw>/ship/v3/pieces/` predate the deck's raise, deck 0.6; v2's in `<raw>/ship/v2/`, v1's in `<raw>/ship/v1/`) with `pieces/` (GLBs, `build_report.json`, validator `reports/`),
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
| Deck | floor at h 1.2 on standing legs (the raise, 2026-10-23; launch 3: 0.6, before it 1.0), slabs 0.25, walls 0.2; the builders work in the design frame (deck 0.6) and the build lifts every piece but the grounded ones by `lift_m` 0.6 (see "Raised 0.6 m") | the belly clears the ground; the inside unchanged |
| Hall | circle r 4.0 at (0, -0.4) (rebuild E; C (0, -1), v2 (0, 0), v1 r 3.4); 3.2 m to the ceiling's rim all round (rebuild E; C had 2.75 m round its front), 3.8 m to its apex (faceted, 16 sides, the four diagonal pairs of facets made one flat chord each for the vents and sockets) | 5a mirrored: round, 8 m across |
| Throat (rebuild C; v2's mouth passage x -1.3..1.3, y -4.6..-3.9) | the funnel from the mouth (x +-1.65 at y -7.1, J's nose edge; 5a: y -8) to the hall's vertices (+-2.915, -3.252), 4.051 m walls in five modules of 0.810 (rebuild E); open to the sky forward of y -5.561 (the walls there are the hull's jambs, `skin_cheeks`), a 2.3 m ceiling aft of it; since the raise's step 2 the entry tunnel (`tunnel_y` -8.1) runs the mouth 1 m on past the nose and its hood roofs the notch (see "Raised 0.6 m") | the only way in or out (5a's side hatch is dropped, see below) |
| Ramp | 3.3 m wide (the mouth), hinge (0, -8.1) at the tunnel's front, foot (0, -12.6) on the ground: 14.9 deg, 4.66 m long (the raise, step 2; step 1 hinge -7.1, foot -11.6; rebuild C: foot -9.9, 12.1 deg, 2.86 m; v2 2.6 m from (0, -4.6)) | north at the centre |
| Corridors | `strip` rooms on the axes from the hall's centre (0, -0.4) to the lens rooms' (+-10.5, 1.2) (lens step 1): 10.621 m, 8.66 deg aft; floor 3.708..9.298 along the axis (5.59 m), 3 m wide, straight, 2.4 m high (walls vertical to 1.45, then chamfered) | 5a mirrored: straight, about 3 m wide |
| Lens rooms (ids `tip_e`, `tip_w`) | circles r 2.0 at (+-10.5, 1.2), the outer wall at +-12.5; the ceiling slants down outward (P's: clear 2.4455 at the corridor's wall face, 2.3545 at the outer one; `clear_h` 2.35, `clear_h_in` 2.45); the window band -65..+45 deg round the outward axis, + aft, sill 1.0, head 2.2 (`band`); one round roof window, the oculus (`oculus`, 1.4 m clear, 32 sides; details 1, was three 0.9 x 0.7 m) | P's lens (art#263 comment 6344490367) |
| Stations (not built) | console (0, 0.6) clear floor; vents on the throat's slanted walls (+-2.409, -4.791); sockets (+-1.800, 3.112) and the front two on the hall's flats (+-3.426, -2.358); breaker boards (+-6.664, -0.902) in the middle of the corridors' front wall; renewers (+-10.269, 3.237) on the lens rooms' aft wall (a vertex, 87.82 deg aft of the axis), the player at (+-10.433, 1.793) (the fix pass: `depth_m` 1.053, the crystal charger's reach; was 0.9, the player at (+-10.415, 1.945), inside its front pads) | lens step 1; the vents as in "Rebuild F" |
| Vault (lens step 1) | `rect` x +-0.9, y 3.85..5.85 (1.8 x 2 m clear), `closed`: its shut door (1 m) in the hall's back wall at (0, 3.6), no exit, no link, not walkable floor (`check_closed`); ceiling 2.3 m at the door, 1.6 at the back (`clear_h_back`) | a shell only: no item, card or lock |
| Player | capsule r 0.4, 1.8 m; every room keeps 0.5 m above it | the game's capsule |

The check holds: the footprint within 0.5 m; corridors `corridor_width_m` (3) +- 0.1 m wide and over 2.5 m long; the
tip rooms' outer wall at `tip_outer_m` (12.5) +- 0.05; the station spots (`check_spots`, "Version 2" below); clear heights over the capsule and margin; exactly one room with an exit, the ramp's hinge on its north
edge, the ramp as wide as the mouth and under 30 deg; every room reachable from the hall and linked rooms meeting;
every poly room convex, its points with a positive signed area in plan (x, y) (`check_polys`); every capsule walk
point on the deck on a room's floor with the capsule's radius round it (`check_walk`); every room's sampled outer
surface inside the live hull (P) with 0.15 m of skin (`hull_skin`: `ship_hull_shape.clearance` on the checked layout's own
rooms, each sampled on its own); every room's outer wall and every placed piece inside the hull outline (a piece marked `outside` may
stand outside: the ramp, the legs, the clearing, the entry tunnel `mouth_tunnel` and `mouth_tunnel_in`; the exit room's tunnel floor, `tunnel_y`, is the one floor past the outline, `ship_layout.tunnel`); no piece defined twice or never placed.

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
Godot's importer gives it a static body with its trimesh (one-sided: solids face out); a piece whose builder returns
its own simple colliders (parts named `*-convcolonly` or `*-colonly`: a static body, no mesh, e.g. the workshop robot's
sphere) keeps its other parts visual only, and Blender's bounds leave those colliders out as Godot's do. Materials come only from
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
tools/run.sh ship --jaw-video DIR       # the jaw nose opening at night from a still 3/4 front camera: DIR/open.mp4
tools/run.sh ship --vent-anim DIR       # the east vent's animation in place at night from the player's eye: MP4, key sheet
tools/run.sh ship --charger-cycle DIR   # the east crystal charger's cycle at night from the player's eye: cycle.mp4, key sheet
tools/run.sh ship --play [DIR]          # the engineer's own walk (an on-screen window; agents run --play-test DIR)
```

Runs over 180 s go to the background with their log (CLAUDE.md, "Shell"). A snapshot of the whole after launch
2's join (2026-10-22; superseded: `ship --check` prints the current pieces and placements, 157 and 1226 at aa561f1): 139 pieces, 1094 placements (the clearing's 162 pines, 26 bushes, 6 logs, 5 stumps, 160 tufts and 8
party-light posts among them), 59310 triangles per piece set, glTF-Validator clean; extent 26.46 x 13.9 m;
`--godot`: Godot sizes equal Blender's, 105 colliders, the capsule walk reaches all 14 points (18.8 s);
`--walk`: the 1280x720 walk-through, 89.5 s, 2149 frames, 12.8 MB (rendered in 313 s); `--shoot`: 14 views and
their compare sheets, 415..620 draw calls inside the tip rooms, 1740..2032 outside. Times: `--build` about 2 min,
`--godot --walk DIR --shoot DIR` about 10 min.

### Walking it yourself (`--play`)

`ship --play [DIR]` is the engineer's: it opens a 1600x900 window on the screen with the built ship at the shoot's
night look and a first-person capsule of the game's size (ship.toml `[player]`) at the ramp's foot, facing the ship
(`godot/ship/player.gd`). Keys: W A S D walk, Shift run, Space jump, the mouse looks, F flies through walls (Q down,
E up), P or F12 saves a screenshot, F11 full screen, H the help, Esc frees the mouse (a click takes it back), Ctrl+Q
quits. The top-left corner shows the plan position (x, y, h as ship.toml writes them) and the facing, so a
screenshot says where it was taken; each one is `DIR/shot_<time>_<n>.png` with a line in `DIR/shots.txt` (position,
eye height, look direction). DIR defaults to `<raw>/<raw_dir>/play`. `--out` picks the pieces folder, as for the
other modes: a piece set built from `main` with `ship --build --out <folder>` walks the ship without a branch's
changes. Agents never open it on the screen (CLAUDE.md): `ship --play-test DIR` runs the same scene off-screen, walks
the capsule forward 2 s, saves one shot and `DIR/play.json`, and fails when it did not move 1 m on the floor.

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
ground lamps at h 0.3, range 3.5, the ramp's four of them at x +-3.7 and range 1.9 since fix 2, and three under the belly at h 0.35, range 6; amber, shadowed so they never light a
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
arches); the player's stand (`depth_m` 0.5, the renewers' 1.053, the crystal charger's reach, plus the capsule's radius out from the wall) inside
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
- **Navigation lamps** (`nav_red`, `nav_green`, `nav_white`; `ship_hull_detail.nav_lamp`; since fix 2 only the white
  tail lamp is built: the red and green rows are commented out as NAV SIDE, the engineer's "not needed yet"): a round silver housing, a dark
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

## Raised 0.6 m (2026-10-23)

The engineer (chat, 2026-10-23): "Піднімай на 0,6 м, витягни вхід і виправ ті два баги" (raise it 0.6 m, extend the
entrance, fix the two bugs). Step 1 of the raise:

| What | Before | Now |
|---|---|---|
| Deck (`[deck] floor_h`) | 0.6 | 1.2; `lift_m` 0.6 |
| The design frame | the builders' heights were the real ones | `ship_hull_shape.FLOOR`, `ship_interior.FLOOR` and the lifted `ship_hull` builders use `floor_h - lift_m` (0.6); `ship_build.lifted` raises each built piece by `lift_m` unless its record says `grounded = true` (the clearing, the ramp, `ramp_lights`, `hazard_stripes`, the legs, the ground lamps: built at the real heights) |
| Belly, brow (`[hull] bottom_h`, `brow_h`) | 0.17, 4.3 | 0.77, 4.9; the footprint rows' heights are `outline_rows()` + `LIFT` |
| Ramp | foot (0, -9.9): 12.1 deg, 2.86 m | foot (0, -11.6): 14.9 deg, 4.66 m (the hinge and the mouth unchanged in this step) |
| Legs (`leg`) | a long splayed leg lying almost flat (reach 1.6..2.2) | a standing oleo leg: a yoke and pin under the mount box, a sleeve (r 0.15), a collar, the chrome piston, a fork, two side braces, the ankle's knuckle and a flat 1.2 m footpad with a hub and four ribs; tops 1.24 (front, rise 0.25), 1.04 (rear), 1.77 (stern), reach 0.5, 0.4, 0.6; the same six spots |
| Lamps | | the inside's, the landing, edge, nav and flank lights +0.6; the ground lamps 0.9 m past the new feet, the ramp's pair at y -9.3 and -11.0 |
| Walk, views | | the deck points at 1.2 (the lens and hall checks at 1.6), the ramp's foot -11.6, start and end -13.0; every inside and detail view +0.6; the walk-through's deck keys 2.85 |

Step 2 of the raise:

| What | Step 1 | Now |
|---|---|---|
| The mouth | the throat's front edge at J's nose edge, y -7.1, open to the sky forward of the roof line (-5.561) | the entry tunnel 1 m past the nose: `[[rooms]] throat` `tunnel_y = -8.1` (the room's polygon unchanged; `ship_layout.tunnel` adds the floor x +-1.65, y -8.1..-7.1 to `room_margin` and makes its front the exit edge); the hull's footprint keeps its lead edge at -7.1 and the tunnel's piece `mouth_tunnel` is `outside` (the only hull piece past it) |
| `mouth_tunnel` (`ship_hull_j.py`) | | inside: the throat's profile (vertical to 1.45, the chamfer 0.55 in, the 2.3 m ceiling) from -8.1 back to 4 cm past the roof line, walls in the jambs' plates, plated chamfers and ceiling, a cyan strip on each bend, frame ribs at the front and the nose, a grated floor, two amber floor lights; outside: a hood, the profile offset 0.25 m (roof at `TH_TOP` + 0.15), plated silver, cut by the nose where its top rises over it; inside the notch a fill at the nose's top + 12 mm closes the notch (bug 2: the lintel and jamb ends no longer stand out); a dark portal frame and a chrome lip at the front |
| Ramp | hinge -7.1, foot -11.6 | hinge -8.1, foot -12.6 (14.9 deg, 4.66 m); its ground lamps and pools at y -10.3 and -12.0; the walk from y -14.0 |
| Legs | a dark mount box hanging 0.12 m under the belly; sleeve r 0.15, piston 0.085 | a faceted fairing (8 sides, r 0.62 inside the skin to 0.36 at a dark frame lip, smooth hull silver); sleeve 0.19, collar 0.23, piston 0.11, fork 0.145, braces 0.06 |
| Bug 1 (the throat's slanted wall and brace against the hall's panel, the black slot above) | | step 3, closed: the throat's last upper-wall module ended square at the hall's vertex (+-2.915, -3.252) while its chamfer leans 0.55 in; the hall's flat panel there stands vertical to 3.2 m, so a pocket stood open up to the hall's ceiling. That module is now `th_wall_up_end_e`/`_w` (`cor_wall_up` with `end`, `ship_interior.th_end_cut`): its chamfer and panel are cut 1 cm inside the hall face of the throat ceiling's header (`TH_HEAD_D` 0.2 hall-ward of the corner sub-facet's chord), so the lean runs into the header; on the two corner sub-facets the header carries a trim (`int_silver_c`) along the seam and a raised panel (`int_silver_a`) above it |

Step 3 of the raise:

| What | Step 2 | Now |
|---|---|---|
| The tunnel's light | one piece in the outside lane (render layer 2): the inside's strip lights did not reach its inner faces, darker than the throat | two pieces of `mouth_tunnel` (`args.part`): `mouth_tunnel_in` (walls, chamfers, ceiling, ribs, strips, slab, grate, floor lights) has `layer = "inside"` in exterior.toml, so `ship.py` leaves it out of the request's `outside` list and it draws on the inside's layer; `mouth_tunnel` (`part = "hood"`: the hood, the undersides, the fill, the portal, the lip) stays outside |
| The notch's fill | cells of about 5 x 15 cm, each left out where the hood stood over it, else lifted to 2 mm under the hood: rows of bands from above, a stair edge on the chamfers | one connected grid a side (60 x 28), every vertex at the nose's top + 12 mm (`TUN_FILL`) or 3 cm under the hood (`TUN_SINK`), whichever is higher (the widening over the jambs to past the notch side made a saw edge on the nose and did not close bug 2: dropped) |

`ship --shoot DIR --views FILE` shoots only a JSON list of views (and the plan views): a review's own sheet.

## Fix 2: the engineer's walk (2026-10-23)

The engineer walked the raised ship (`ship --play`, his shots in `<raw>/ship/v3/play/`, 15-16..15-19) and listed
fixes. Steps 1 to 3 of the fix round (items 1, 2, 4, 5, 6; item 3, the cockpit canopies, waits for his word):

| Item | Cause | Now |
|---|---|---|
| 1. The ramp's ground lamps | the four stood at x +-1.75, 0.1 m past the ramp's edge (half width 1.65), their pools (range 3.5) over its edge | 3.7 m out (`ground_lamp` and their `pool` rows, y -10.3 and -12.0), range 1.9: no pool reaches the ramp; `test_ship_light` keeps every pool and fixture clear of it |
| 2. The red and green nav lamps | "not needed yet" | off: their placements, `[[pieces]]` and `nav` light rows are commented out, marked NAV SIDE in `exterior.toml` and `ship.toml`; uncomment the three blocks to bring them back (`test_ship_light` keeps them on or off together; the white tail lamp stays) |
| 4. Broken plates and gaps along the seams by the lens rooms | (a) every plate's chamfer and the dark under-skin sank along its own face's normal (`lay_seams`, `j_skin`), so on a valley fold the sunk outlines parted into a slot (1201 shared plate corners over 3 mm apart); (b), the visible one in shots 010..013: the fairings under the lenses were plated by `_plan_cells`, whose seam family follows each facet's normal (rows of constant y, or h where a facet looks fore or aft; ends of constant x, or h or y where it looks sideways), so round a fairing's bend the family switched from facet to facet: seams stopped on a fold and restarted offset on the next facet, their chamfers lit pale by the moon | (a) `ship_hull_j.miter` and `skin_miters`: a point on a fold sinks along the faces' mean normal scaled so its own plane sinks by the depth (two faces: the exact miter; three: the point under all three), plates and under-skin alike: 42 corners over 3 mm left (folds over 120 degrees, capped at `MITER_MAX` 2); (b) `_fair_cells`: a fairing face is cut by the lens rim's lowest band's radial planes (`LENS_SECTOR` from the lens's axis, the west mirrored), one family for every facet, so each seam meets itself on every fold and runs on up into the rim; seam ends on a flush fairing fold with nothing beyond: 44 before, 14 after. Step 3, the diagonal body seam beside the trailing fairings (s010/s012 close-ups), which turned from a dark groove to a pale chamfer and jumped sideways half-way: the hull's surface splits a facet into coplanar fragments (the union of its convex parts), and each fragment was plated on its own, so a plate's thin fragment along the seam was a sliver laid flush (no chamfer on that side: the dark stretch) and the seam's corners slid along the fragments' edges (the zig-zag). `skin_pieces` now merges a plate's pieces on coplanar faces where their union is convex (`merge_coplanar`, `skin_faces`), splits every piece edge at the surface corners inside it (`Edges.split`, so an edge whose neighbour changes along it is flagged per stretch) and drops corners on straight runs (`_straighten`); a seam corner may slide `FIXED_CAP` 0.8 of a flush edge whose other corner stays put. Pieces 3674 to 1895, slivers on a seam 687 to 263, seam corners tapering the groove (the test's narrow count) 23 to 1, seam ends on a fold with nothing beyond 145 to 82 (39 by the fairings: the zone boundaries, lens rim to fairing to plan, where the seam families differ) |
| 5. The engine nozzles change as the camera turns | `ship_hull._lathe_y` capped every end ring off the axis: the bell's lip ring and the throat's mouth were two flat discs in one plane (ln + 0.4) over the whole nozzle, `ext_frame` (brushed) and `ext_nozzle_inner` z-fighting, so the dish showed wedges of either disc's triangles and the frame's moving highlight. The A/B ruled out SSIL, SSAO and the shadows (step 1) and the throat's own material: roughness 0.6/0.75 or metallic 0.3 changed under 1/255 per pixel, smooth normals 0.04/255 | `_lathe_y(caps=False)`: the bell, the throat and the inner light ring open; the band round the bell a ring outside the nozzle's wall (it was a solid disc 16 cm in); the throat shaded smooth up to `THROAT_SMOOTH_DEG` 30 (its radial facets 11.25 apart, its wall/floor crease kept). The three nozzles now read the same from shots 004..009: the dark cup, the cyan ring 0.3 m down and the core glow (the cup reads teal in its own ring's light: a look change for the engineer) |
| 6. The dark triangle on the nose by each canopy fairing | the jamb caps (`jamb_caps`, `hull_dark`, rebuild F) reach up to `TH_TOP` + 0.03 out past the notch's side, where the roof line falls under it (3.03 m at x 2.30, 2.97 m at the cap's outer edge): the cap's upper outer corner stood up to 8 cm out of the roof's plates | the cap's top stays `CAP_SKIN` (`DEPTH` + 2 mm) under every roof face over its line (`_roof_planes`), both sides. Step 3, the smaller wedge left in the corner: the jamb's top (`j_cheeks`, `jamb_edge`) paired its inner and outer samples square to the wall, so its aft end stopped (`WALL` + `JAMB_OUT`) * d[0] / d[1] = 7.7 cm forward of the roof line at its outer corner, and through that open triangle the eye looked down onto the cap. Both of the top's edges now run on to `JAMB_END` (`SLIDE_MAX` * `INSET` + 6 mm) aft of the roof line and end in a 2 cm face looking aft; with `Edges.split` the notch side's seam now stops at the roof line instead of running on 36 cm aft as an open groove (the dark dash seen from the ground at the ramp). No dark hole from the close-ups, shots 016 and 018, from above or from the ground, both sides |

`ship --shoot DIR --views FILE`: a row's optional 6th element, `{"ssil": false}`, `{"ssao": false}`, `{"glow": false}`
or `{"shadows": false}` (the moon's and the key's), switches that part of the night look off for that one shot,
and `{"mats": {"<glTF material>": {"roughness": r, "metallic": m, "specular": s}}}` sets those values on a glTF
material (not the `METALS`) for that shot (`ship.gd _ab`): one run holds an A/B. The fix round's views (every walk shot at its exact eye and look, fov 75,
narrow close-ups, the nose and the ramp's lamps) are `<raw>/ship/v4/fix2/views.json`, written from `shots.txt` by
`<raw>/ship/v4/fix2/mkviews.py`.

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
- **Way A (art#263 comment 6363433518; builder steps vents-a1 to a3), archived** (vents-b3: way B replaced it; its scripts `ship_vent_a*.py` are kept for the record, and `ship_vent_a_sheet.py` still draws way B's sheets). The body (frame, copper
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
  `vent_e`/`vent_w` have their own `depth_m = 0.6` (the engineer, comment 6363588759), the units (way A's, as
  history; vents-b4 recessed them 8 cm, `[-0.80, 0.80, -0.09, 0.52, -0.02, 1.85]`: the depth stays the budget from the
  wall's face and `test_ship_vent` asserts the unit's depth plus `RECESS` within it; the current unit, b5 on:
  `[-0.80, 0.80, -0.01, 0.50, -0.02, 1.85]`, so 0.6 is the spot's budget and the unit is 0.50 deep)
  `[-0.80, 0.80, -0.01, 0.60, -0.02, 1.82]` (way A's, history). The motion proof for way A: the body's three driven surfaces, each blade's
  origin on its pivot (at most 2 mm), the root's ring round the axis fixed (its chord over the turn plus 4 mm, at least
  1.2 cm), the tip's swing at least 4 cm. Review:
  `ship_vent_a_sheet.py` (the concept's views beside neutral and warm EEVEE, `--game` a last row from the motion
  run's `state_<n>.png`); pieces in `<raw>/ship/v4/vents-a/pieces`, never the layout's `raw_dir`. `ship.gd`'s
  `--vent-states` dims the lamp piece and `slat*:__vent_seam` calm (a dim entry `<part>:<material suffix>` dims only
  those surfaces). Not yet: the steam.
- **The look step** (vents-a4, the engineer's yes of 2026-10-23, art#263 c6374327838): the calm pose tilted 22 deg tip
  down (`blade_r5`, the broad upper facet to the front; closed 11 deg further, each blade's lower-edge seam strip
  `int_halo__vent_seam` lit with the heat). `ship_vent_a_bronze.py` (`--in body4k_r4 --out body4k_r6`) replaces
  Meshy's baked albedo with one polished bronze: a Cycles-baked edge mask (the Bevel node's normal against the true
  normal, `BEVEL_R` 6 mm) lerps `BRONZE` to `EDGE`, a 5 cm occlusion darkens the recesses, the well is darker, Meshy's
  normal map stays; and it measures the painted lights into `lights.json` (cyan islands from the emission map and the
  albedo; the cut `__lamp`, `__band`, `__hand` faces, which turn a dark glass). The builder lays a clean emissive
  piece over each (`lights()`): `strip1..7` (`glow_cyan__vent_strip`, one per place), `lamp` (a red dome),
  `bar_hot`/`bar`/`band`/`bar_top` (white-hot, amber, the green band; behind the marker), `screen` and `hand` (the
  outline of a thumb and three fingers of one length, `hand_outline()`). Without the raw `lights.json` (the
  pure-Python tests) there are no light pieces.
- **The raise** (2026-10-23): the vents are built in the design frame (`FLOOR` 0.6) and lifted by `ship_build.lifted`
  like every piece; it lifts a GLB part's `offset`, `origin` and `hull` too, and the motion request adds `lift_m`.
- **Way B (vents-b1, 2026-10-24; art#263 c6374327838: the frame still read crumpled with the clean bronze), the
  current build.** The body and the blade are built in Blender from the concept's views and the comment's numbers by
  `tools/blender/ship_vent_b.py` (`blender -b --python ship_vent_b.py -- --out <raw>/ship/v4/vents-b/b1 [--guide
  <way A body.glb>]`); way A's Meshy body is only the to-scale guide (`--guide` prints its box). No textures: every
  shape is a flat-faceted solid (`solid()`: a convex profile extruded with 45 deg chamfer steps on its ends), the
  chamfer faces a lighter polished bronze (`vent_b_edge`) over the body's `vent_b_bronze`, the caps `vent_b_copper`,
  the rails, sockets and strip slots `vent_b_dark`, the well's inner lip `vent_b_well`. The frame is a ring of nine
  panels (4 mm apart) round the octagonal opening (`OUTER`, `OPEN`; b3's numbers, history: u -0.56..0.388, h
  0.304..1.408; the current ones are in "Way B step 5" below) and an inner lip ring 2 cm lower; a chamfered header sill under the opening's top (h 1.335..1.412: no glow over the top
  blade, as front_closed; the glows and `OPEN_H` stop at 1.33); behind it the box's back slab (the well's back, b3/b4 v 0.115, b5 0.088) and its roof (the top 1.608, its back on
  the wall's slant); the foot and the plinth; two dark cap rails in the well with seven copper caps each (a socket, a
  chamfered disc, a boss). The column (b3's numbers, history: vents-b4 put the scanner centre at 1.20, dropped the
  column's top by `COL_DROP` 0.198 and set it 8 cm into the wall): plinth, foot, shaft, a front panel, the bar's housing
  round its glass (h 0.622..1.548, the green band 1.41..1.464), the lower strip's bezel, the scanner's octagonal bezel
  (21 x 25 cm, the centre 1.398) with its screen 1.5 cm sunk, the head and the lamp's stepped collar (the dome's top 1.841, its back
  2 cm clear of the wall's slant). The game's surfaces keep way A's names (`vent_a_body__band`, `__hand`, `__lamp`, a
  dark glass each); `lights.json` gives `lights()` the seven strips, the lamp, the band and the screen, and the hand
  fills its screen (4 mm in, centred). The blade: one claw section (`SECTION`, 17 points, the calm pose 22 deg tip
  down: a round nose, a broad convex top in four facets, the lit front lip `int_halo__vent_seam`, a nearly flat
  underside; 8.5 cm thick at the root, 4.5 cm at 0.2 m), extruded along the caps' span (-0.441..0.281), bowed 1.4 cm
  up in the middle, its ends chamfered 1.2 cm; 438 triangles. `blade.json`: calm seam 4.6 cm straight from the front,
  closed 6 mm at `CLOSED_DEG` 9, the first cut between two neighbours at 55 deg. The calm tips stand 0.594 out
  (17.9 cm past the frame). About 5,800 body triangles; a vent with its seven blades, light pieces and colliders
  about 9,600. `ship_vent_a_sheet.py` serves both ways (the close-ups re-aimed on the raised column, the seams dark
  calm) and `motion_request`'s close-ups are re-aimed on the built body.
- **Way B, the look polish (vents-b2, 2026-10-24)** (`<raw>/ship/v4/vents-b/b2`, the pieces in `pieces_b2`):
  - *The glow.* The calm well wall (`int_cyan__vent_cool`, 0/0.42/1) at strength 3 (was 1.8; 5 washed white in
    EEVEE), Godot `e` 1.0; the frame's strips 3.5. Each
    glow panel carries its own well lights (`godot/ship/vent_glow.gd`, used by `ship.gd` and `vent_motion.gd`;
    the game copies it): three OmniLights up the opening, 7.5 cm in front of the panel, children of `<id>_cool`
    (cyan, energy 0.9, range 1.1 m) and `<id>_heat` (orange, 0.7, 0.9 m), no shadows; `[light] vent_well_scale`
    scales them. They light the blades' undersides (`vent_b_under`, less metal so they take the light), the noses and
    the frame's inner lip. The states: calm hides `heat`, the problem hides `cool` (`VENT_STATES` "show"/"hide";
    `ship.gd` hides `heat` by default, so `--play` and `--video` are calm). The Blender sheet puts point lights at
    the same places (`WELL`).
  - *The blade.* A thicker, hooked claw (`SECTION`, 22 points): the upper face rises to a crest 8 cm out and curves
    over in seven facets to a tip that curls back under itself, a concave underside; 10.5 cm thick at the root, 9.6
    at 0.1 m, 6 at 0.2 m; a shallow crease at the middle (the concept's two halves); 656 triangles. Its reach (0.264)
    and 11 cm seen from the front are kept: the calm seam 4.0 cm, closed 6 mm at 8.9 deg (`CLOSED_DEG` stays 9), the
    first cut at 46.4 deg.
  - *The colour.* A deeper, browner bronze (`vent_b_bronze` 0.15/0.08/0.032, metallic 0.8; Godot `v` 1.5, it read
    near black at night), the polished chamfers (`vent_b_edge`, Godot `v` 1.2) kept, a darker `vent_b_tarnish` on the recesses (the frame panels' gaps, the column panel's sides,
    the back slab's sides). The lamp a deep red (emission 0.8/0/0, strength 0.5: AgX turns a
    stronger red salmon; Godot `e` 2.4, just past the glow threshold (3.5 read pink when lit)), the bar's amber
    1/0.36/0, its band 0/1/0.08.
  - *The screen.* The dark screen piece is the bezel's octagon 1.5 mm in (`lights.json` `hand.poly`), 1 mm off the
    body's screen face (b1's rectangle's corners cut through the bezel and flickered); the hand shrinks until its
    outline sits 4 mm inside the octagon.
- **Way B step 3 (vents-b3, 2026-10-24)** (`<raw>/ship/v4/vents-b/b3`, the pieces in `pieces_b3`;
  a fresh critic's findings on b2):
  - *The blade stands open.* A swept wedge (`SECTION`, 29 points, 750 triangles): 8.6 cm thick at the root, the upper
    face sweeping down to a 2.8 cm tip 4 cm under the pivot, a shallow concave underside, no crease (its rings read
    as a hard split line), shaded smooth under 35 deg (`SMOOTH_DEG`; b2's polished facet bands are gone). Calm seam
    5.4 cm straight from the front (b2 4.0), shut `CLOSED_DEG` 20 deg below calm (b2 9) with a 1.8 cm overlap
    (`SHUT_SEAM` -1 cm is reached at 18.1 deg), the first cut 57 deg below calm; reach 0.257 (0.262 at most turned).
  - *The frame is heavier.* The face at 0.44 (was 0.415) with 2.4 cm chamfers (was 1 cm), the header 14 cm deep
    (was 9.2), the shoulder 4 cm deeper and 3 cm higher (`BOX_TOP` 1.64), the feet 5 cm higher and 3 cm prouder,
    the scanner's bezel 22.4 x 28.4 cm (was 21 x 25). The calm blades project 14.7 cm past the frame's face.
  - *The colour.* A dark patinated bronze (`vent_b_bronze` 0.085/0.052/0.024, every other frame panel and the
    shoulder `vent_b_bronze2`, Godot `v` 1.55 for both), duller chamfers (`vent_b_edge` 0.42/0.26/0.11, roughness
    0.30, Godot `v` 1.0: no blown highlights), an olive `vent_b_tarnish`. Saturated cyan (0/0.62/1) strips, hand and
    well lights; the well lights' range 0.75 m (b2 1.1 hazed the wall above); the heat and seams a deep red-orange
    (1/0.10..0.13/0). The glow panels end 3 cm under the top blade's root (b2's showed as a cyan plate over it), the
    header sill is dark tarnish.
  - *Defects.* The hand: a bolder neon line on a matte black screen. The lamp dome: 6 rings of 32, shaded smooth.
    The calm seams: `ship --shoot` kept their orange colour (`dim` only scales the glow); `VENT_STATES` now has a
    `"dark"` key (glow off, `VentAnim.SEAM_DARK`), and the Blender sheet darkens their base colour calm. The
    controller and `ship --motion` were already dark.
  - *Code.* `ship_interior_vent.lights()` raises when `lights.json` is missing beside the body.
- **Way B step 4 (vents-b4, 2026-10-24)** (`<raw>/ship/v4/vents-b/b4`, the pieces in `pieces_b4`; its recess and
  flat wall plates undone in step 5;
  the engineer: "set them a little deeper into the wall", the scanner lower, the hand redrawn):
  - *The recess.* The whole vent sits `RECESS` 8 cm into the throat wall (`ship_interior_vent.RECESS`, one source:
    `recess_m` on the vents' spots in ship.toml; `ship --check` lets a station's unit back that far behind the face,
    the unit is now v -0.09..0.52). The frame's sides run back to `FRAME_BACK` 0.07 (b3's started at the well's back,
    11.5 cm out, and left a floating shadow line), so they reach 1 cm into the wall's plate. The two plain modules
    behind each vent (`ship_interior_place.TH_PLAIN`) have a flat plate 2 cm proud instead of the pillow panel
    (`th_wall_low_flat_a/b`, `th_wall_mid` with `flat`; the pillow's 7 cm ridge would stand in the well): the
    vent's solids pass through the plate and the wall's face, which stay hidden inside them, so there is no hole to
    cut, no coplanar face and no gap. Colliders move with the piece. A grid of 0 / 5 / 8 / 10 cm from the eye
    (`sheets/b4/recess_grid.png`): 8 cm reads built in with the frame's 2.4 cm chamfer and most of its side panel
    kept; 10 cm starts to swallow the side panel at arm's length.
  - *The scanner.* Its centre at chest height, `SCAN_H` 1.20 (b3 1.398; `--scan-h` builds others, 1.15 was the
    grid's other value). The column's top drops with it (`COL_DROP` 0.198): the bar's glass top (1.35, its foot
    stays at 0.622 over the lower strip), the panel, the shaft (now under the bend, a plain block), the head and the
    lamp (its dome top 1.64, level with the box's shoulder). `COL_TOP` 1.642.
  - *The hand.* Redrawn as one even stroke round a smooth silhouette: `_hand_field` is a signed distance (a palm with
    0.30 heel corners, three capsule fingers of one length with U crotches, a thumb out at 48 deg filleted into the
    palm by a smooth union `HAND_K` 0.20), `hand_outline` walks its zero line and keeps a point every 7 deg of turn,
    `hand_stroke` offsets each point `HAND_W`/2 both ways along the field's normal (even width; every curve's
    radius is over it, so neither side folds). Its box was 80 % of the screen's height (b4, b5; b5b: 70 %, see below),
    centred, 1 cm inside the octagon. b3's mitred ribbon read ugly.
- **Way B step 5 (vents-b5, 2026-10-24)** (`<raw>/ship/v4/vents-b/b5`, the pieces in `pieces_b5`; superseded by b5b
  below, whose changes are listed after this step; the engineer's notes on step 4):
  - *Back on the wall.* `recess_m` 0 on the vents' spots (`RECESS` 0; the engineer did not mean the 8 cm recess), the
    unit v -0.01..0.50. The two plain modules behind each vent are the pillow panels again (as b3; the flat plates
    were only there for the recess). Each frame panel's back now stands `FRAME_BACK` (6 mm) off the wall at its
    highest point (b3's started at the well's back and floated, b4's 7 cm out): the panels below the bend sit on the
    wall and sink into the pillow, the two over the bend stop on the slanted wall.
  - *The blades inside the frame.* The calm blades' tips stand `TIP_BACK` 3 cm behind the frame's face, level with
    the inner lip (b3 and b4: 14.7 cm past it): the hinge line `PIVOT_V` = face - `TIP_BACK` - 0.257 = 0.153 (b4
    0.33), the well's back `WELL_V` = `PIVOT_V` - `WELL_GAP` 0.065 = 0.088 (b4 0.115), the cap rails and copper
    caps set back with the hinge. The shut bottom blade's tip falls to 0.238, so the opening's floor is
    `OPEN_FLOOR` 0.22 (b4 0.304) and `ship --motion` now holds the blades over it (b4 allowed 10 cm under it). At the
    widest (the cough, calm + 10 deg) the tips stay 2.4 cm behind the face (the hull; 2.5 cm on the mesh). b5 claimed
    the motion proof held the blades behind the face too, but its depth limit was still the unit's 0.50 (the column's
    foot, 6 cm past the face): that came in b5c, see the motion result below. The grid
    (`sheets/b5/blade_depth_grid.png`): 0, 3 and 6 cm; `ship_vent_b.py --tip-back` and the review's `tip_back`
    build the others.
  - *A wider column.* The box's opening, blades and right side moved `BOX_DU` 4 cm along the wall (its left edge and
    foot stay, the left frame panels 4 cm narrower), so the column runs 0.426..0.80 (b4 0.466..0.80; the shaft
    0.435..0.795, the panel 0.44..0.79, the foot, its step and the head with them); the bar and its lower strip
    `BAR_DU` 4 cm along, the scanner's centre `SCAN_U` 0.660 (b4 0.685; still 1.20 high): its bezel 1.5 cm from the
    bar's housing and 1.8 cm inside the panel's edge (b4 1.7 cm over it). The lamp is centred on the head, its
    collar `LAMP_R` 0.086 (b4 0.078). The unit stays inside the 1.6 m plain band.
  - *The hand.* Human finger lengths: index, middle, ring tips `HAND_TIPS` 1.60, 1.80, 1.70 (b4 one length, 1.705;
    the palm's width 1), narrower fingers (`HAND_FR` 0.11) with wider U gaps (`HAND_GAP` 0.17), so the dark gap
    inside the stroke is 0.085 of the palm (b4 0.04) and reads at 2 m; the thumb `HAND_THUMB` a little lower and
    shorter, its fillet `HAND_K` 0.28 (0.20 folded the stroke's outer side).
- **Way B step 5b (vents-b5b, 2026-10-24), the current build** (`<raw>/ship/v4/vents-b/b5b`, the pieces in
  `pieces_b5b`; the manager's three findings on b5; PR #318):
  - *Clean bezel corners.* `ring()` built the bezel and the bar's and lower strip's housings as eight panels, each
    chamfered all round, with chamfers wider than the frame, so the front faces crossed into spikes at the corners. New
    `bezel()` in `ship_vent_b.py`: each of the three is one closed solid between two octagons, the outer and inner
    chamfers apart, straight mitres at the shared corners, a flat front face (asserted). Bezel outer 1.2 cm, inner
    0.4 cm; bar housing 0.85 / 0.3; lower strip 0.6 / 0.3. The body is 5,548 triangles (b5 5,836). The frame's nine
    panels and the well lip keep `ring()` (real gaps between panels).
  - *Hand at 70 %.* `HAND_FILL` 0.70 (b4, b5: 80 %, where the ring finger's tip ran into the octagon's top right
    corner and the hand read off-centre): the box is centred on the screen octagon's box, margins 2.37 cm left and
    right, 3.43 cm top and bottom; finger lengths and thumb unchanged. `test_light_pieces` holds the margins and the
    fill.
  - *Mirror normals.* On the west (mirrored) vent `ship_build.import_glb` mirrored with a negative scale and
    `flip_normals()`, which reverses the corners but not the stored custom normals, so the blades showed facets. The
    corner normals are now read per (face, vertex), turned by the placement and set back after the flip; the west
    blades are as smooth as the east. The blade GLB is still `b3/blade.glb`.
  - *Result.* `ship --motion` on the pieces (`motion_b5b`): 528 frames, 0 cuts, 0 outside, 0 past the depth, least
    clearance 0.0509 m. Check at the time: the blades inside the opening and under the unit's depth only; the new face
    check (b5c, below) passes on the same pieces (`motion_b5c`).
- **The animation (vents-anim1, 2026-10-24; the engineer: "make the vents, try to animate them"; beauty over
  motion).** `godot/ship/vent_anim.gd`, the controller the game copies: a Node per vent (`setup(root, id,
  mark_travel)` after the scene's materials are set; `_process` steps it, `manual = true` and `step(dt)` for a
  proof). It takes each driven surface's material as a copy (a surface override) and drives the seven blades
  (`rotation.x = -deg_to_rad(angle)`, the angle in degrees of opening from shut, calm `CALM_DEG` 20 since vents-b3, was 9), the marker, the
  cool and heat panels with their well lights, the seams, the lamp, the bar and its band. **Inputs:** `problem: bool`
  and `hold: 0..1`; the signal `fixed` at the cough (the game clears `problem`; the controller re-arms only once it
  has been false for a step; `fixed` needs hold 1.0 held about 0.64 s). **States:**
  - *CALM*: the blades breathe, each breath closing from calm by `BREATH_DEG` 5 (vents-b3; was 3.2) and opening back every
    `BREATH_PERIOD_S` 3.6 s, each blade `BREATH_WAVE` 0.07 of a breath behind the one above (a soft wave down); calm
    stays the widest pose (the settled look), the cyan eases by up to `BREATH_GLOW` 0.35 as they close.
  - *SLAM* (`problem` set): shut in `SLAM_S` 0.16 s (cubic ease-in), `SLAM_STAGGER_S` 0.012 s a blade, then rebounds
    off the stop (`BOUNCE_DEG` 3, vents-b3; was 1.8, `BOUNCE_HALF_S` 0.085, `BOUNCE_DECAY_S` 0.11; never below shut); the heat panel
    with a flash (`FLASH_GAIN` 2.6, falling over `FLASH_DECAY_S` 0.3), the seams lit, the lamp pulsing
    (`LAMP_LOW` 0.35..1 at `LAMP_PULSE_HZ` 1.3; calm `LAMP_CALM` 0.1), the bar from `BAR_CALM` 0.6 to 1.
  - *SHUT*: a barely seen heat tremble (`TREMBLE_DEG` 0.22 at `TREMBLE_HZ` 7); `hold` (followed with
    `HOLD_FOLLOW_S` 0.12) lifts the marker and opens the blades toward calm in `HOLD_STEPS` 6 clicks (each moves in its
    last `STEP_MOVE` 35 %); over `HEAT_FADE` 0.15..0.95 of the hold the cool panel shows, its colour and its lights
    from the heat's orange to cyan; the band brightens by up to `BAND_GAIN` 1.6 near the top. `problem` cleared
    without a hold: *OPEN*, shut to calm over `OPEN_S` 1.2 s.
  - *COUGH* (hold 1): kicks past calm and snaps back three times (`COUGH`, [s, deg] keys: 10, 6.5, 3.5 deg over
    0.58 s, smoothstep between keys, `COUGH_STAGGER_S` 0.015 a blade), a cyan puff (`PUFF_GAIN` 2.4 over
    `PUFF_DECAY_S` 0.55), then CALM, the breath easing in over `BREATH_IN_S` 1.6 s, the marker sinking back
    (`MARKER_RETURN_S` 0.5). The top blade dips instead (`COUGH_TOP` -0.2) and never rises above calm: its crest
    stands under the header sill (1.4 mm a degree; a 10 deg kick cut it by 1.5 cm in the first clip).
  - *The demo* (`VentAnim.demo(s)`: calm to 6 s, the problem, the hold 8..13 s, the cough, calm to 22 s) drives both
    proofs. `ship --motion DIR` now runs it on the vent alone (the 22 s `vent_motion.mp4`) and checks every frame:
    each blade's sections against the next (the penetration depth; the least clearance on every other frame) and its
    vertices against the opening (since b5c also behind the frame's face plus 5 mm, `v_front`, over every frame; the
    unit's depth `v_max` is the separate "past the depth" count); `motion.json` `clip`, `clip_closeups.png` (the widest, the
    slam, the bounce, a breath). First result (b3, history): 0 penetration, 0 outside, 0 past the depth, least
    clearance 1.5 cm, the blades 0..19 deg. The b4 clip (`<raw>/ship/v4/vents-b/motion_b4`): 0 penetration, 0 outside,
    0 past the depth, least clearance 5.1 cm, the blades 0..30 deg (calm 20, the cough's kick 10 above it; the top
    blade never above calm). The b5b clip (`motion_b5b`): the same, least clearance 0.0509 m. The face check (b5c,
    `motion_b5c`, the b5b pieces): 0 outside including the face plane; as a control, with `v_front` set 4 cm inside
    the face the same run fails with 0.0150 m outside, so the farthest tip is 2.5 cm behind the face. `ship --vent-anim DIR` (ship.gd mode `vent_anim`) renders it on the whole ship at night
    from about 3 m across the throat at the player's eye (`VENT_ANIM` in `ship.py`), 1280x720, and shoots the demo's
    key moments again with their labels into `keys/` and `keys_sheet.png`.

## The export (art #335)

```
tools/run.sh ship --export DIR [--no-compare]
```

writes the ship's game-ready package (for prime-game#1225 and #1285) from `layouts/ship/` and the built pieces
(`<raw>/ship/v5/pieces`) into `DIR` (the raw folder's `ship/v5/export/v<n>/`, never git), shaped like the game's tree
(its ARCHITECTURE 11.1), as the House's export (`docs/house.md` "The export"):

- `assets/environment/ship/`: the pieces' GLBs (189 at v3, 2026-10-30), each with a minimal `.import` (11.2's options); `metal.gdshader`
  and `night_sky.gdshader` (copies of `godot/ship/`'s), `console_metal.gdshader` (`godot/console/`'s, the lens
  bronze's shader); `materials/metal_<name>.tres` (one per shared metal of
  `ship.gd` METALS), `night_sky.tres`, `night_env.tres` (the night environment: AgX, glow, SSAO, SSIL, fog, the star
  sky); the vents' normal maps the GLBs' import extracts (`station_vent_<e|w>_vent_a_normal.png`). Data only.
- `levels/ship/ship.tscn`: root `Ship` (`metadata/size_m` the plan's width and length, `deck_h`), `Pieces` (the ship's
  placements as GLB instances), `Environment` (the WorldEnvironment), `Lights` (the moon, the key, the layout's lamps
  and the glow cells' omni lights, as `ship.gd` places them), `Probes` (one reflection probe per room), `Clearing`
  (art #356, below: the clearing's pieces, its lights and `Ground`, the world boundary, which `ship.gd` names
  `Ground` so the export finds it by name), `Nose` (art #263: the jaw's pieces and their `AnimationPlayer`, "The jaw
  nose" below), `Stations` (one `Marker3D` per `[[stations.spot]]`: `Console`, `VentE`, `VentW`,
  `SocketE`, `SocketW`, `SocketFE`, `SocketFW`, `BreakerE`, `BreakerW`, `RenewerE`, `RenewerW`; on the deck, +Z the
  spot's normal, the console turned 180 degrees; `metadata/spot`, `package`, `kind`) and `Markers/Spawn` (the walk's
  first point at the ramp's foot, facing the ship).
- `package.json`: every file with its SHA-256 and bytes, the station spots, the spawn and the open questions.

How the scene is made: `godot/ship/export_scene.gd` extends `ship.gd` and runs its own assembly (`_environment`,
`_build`, `_dress`, `_probes`) headless in `godot/`, then packs the tree. Each piece is instantiated in edit state, so
the pack saves only what the look changed inside it, as overrides on editable instances (the game's 11.2 rule): every
glTF material's night value (`[light.mats]`, changed in place by `ship.gd`) as a copy on its surface, the metals,
the outside pieces' render layer 2, the vents' heat panel hidden and their well lights. Without the edit state the
pack saved every mesh and shape of every instance (a 14 MB scene); with it the scene is about 0.8 MB. A vec3
`source_color` uniform set from a `Vector3` saves as null, so the metals' and the sky's are stored as the `Color`
that renders the same (its sRGB). `ship_export.relocate` moves the art project's `res://` paths to the package's and
drops the uids; `leftovers` refuses an art path, a script or a sub-resource path. The glow omnis' `pieces` metadata
(ship.gd's bookkeeping) is removed before the save. The nav lamps keep their static
glow (the blink is the shots' script).

The check, on the package opened as its own Godot project (`godot/ship/export_check.gd`, copied to `DIR/_check/`):
the headless import and load; each piece's bounds against Blender's `build_report.json` (0.01 m); a layer-1 collider
on every colliding piece; no script on any node; the station spots; the 1.36 m capsule from `Markers/Spawn` through
`[walk]`'s points (both tip rooms and back) on the exported scene. Then, unless `--no-compare`, `ship --shoot` of
`out_hero`, `in_hall` and `in_tip_e` into `DIR/_check/ref/` (kept when newer than the build) and the same views from
the package in an off-screen window: the mean absolute difference (0..255, at most 2.0) and the share of pixels off
by more than 16, with each view's draw calls, primitives and GPU ms. `DIR/_check/report.json` holds the numbers;
`assets/environment/ship/` commits the manifest (the files' hashes), `report.json` and `HANDOFF.md`, not the GLBs.

### The lobby: the Clearing node and the closed nose (art #356, 2026-10-30)

The lobby hall instances the package and never forks it; it shows the ship docked and closed (the engineer's word),
without the clearing. So the export puts the clearing under one node, `Ship/Clearing`:

- `Clearing/Pieces`: every placement of a piece whose builder is in `ship_layout.CLEARING_BUILDERS` (the ground, the
  rocks and rock piles, the pines, tufts, bushes, ferns, moss and litter, logs, stumps, the dirt patch and path, the
  ground lamps, the party posts and string; `ship_layout.clearing_ids`), moved there from `Pieces` by
  `export_scene.gd` `_clearing`; still editable instances.
- `Clearing/Lights`: the lamp rows of the groups `ship_layout.CLEARING_LAMPS` (`pool`: the ground lamps' pools, `party`,
  `out`: the treeline camp lights and the lamp in front of the ramp, `fill`: the pines' moonlight) and the glow cells'
  omni lights that only clearing pieces lit (the party bulbs); `ship.gd` marks them (metadata `clearing`, removed
  before the save) from the request's `clearing` and `clearing_lamps`.
- `Clearing/Ground`: the world boundary (it was `Ship/Ground`).

The ship's own outside light (the landing and edge spots on the ground, the rim, the key, the tail lamp) stays under
`Lights`. The lobby frees the node; hiding it leaves `Ground`'s collider on. There is no root script (the package
carries none), so the switch is the node. The export's check (`_ship_export.clearing_problems`) refuses a `Clearing`
that differs from the layout's clearing placements, a clearing piece under `Pieces` or a ship piece under
`Clearing`; `tools/tests/test_ship_lobby.py` keeps the builder list complete (every `ship_hull_clearing` builder),
the clearing outside, grounded and collision-free, and the clearing lamps outside the hull or on the ground.

**The closed nose** blockouts of art #356 (rounds 1 and 2 in `<raw>/ship/v5/lobby/closed-1/`, `closed-2/`) were all
rejected (the nose itself read as a box bolted onto the manta) and are removed; the jaw nose below replaces them, and
its closed pose is the lobby's docked ship.

### The jaw nose (art #263: b3's look, approved 2026-10-30; b4 finished it for the package)

The engineer's redesign (#263 c6524257765; concepts `<raw>/2026-10-30-ship-nose-concepts/`, 6 and 1 closed, 2 open):
the hull's own surface runs forward into a flat, pointed prow that opens like a jaw. Built by
`tools/blender/ship_hull_jaw.py` from ship.toml `[jaw]`. Blockout b1 (solid convex wedges) was rejected for holes
when closed (the passage's sides lay outside the prow where the upper hull's sides lean in), the old tunnel showing
and parts read as thick blocks; b2 rebuilds every moving part as a thin shell (`SHELL` 4 cm) following the prow's outer
surface, plated outside like the hull (`ship_hull_j.plates`/`lay`, the dark under-skin), finished inside. b2's lower
part read as a heavy wedge under the nose from the 3/4 front (tall flat side skirts, big flat lower front faces, a
vertical crease where the jaw met the hull); b3 (a grid of three shape variants, `<raw>/ship/v5/nose/b3/var/`) widens
the seam to (+-3.5, -8.1) and adds a chine under it staggered aft of the hinge line, (+-3.4, -7.6, 1.9), so the sides
under the seam face down and read as the hull's underside; the lower hull's aft points follow the hull's own bottom at
y -4.6 (1.52 .. 1.72 m at x 3 .. 4.5), a keel point (0, -10.0, 1.5) splits the lower front into facets, and the rails
are 0.45 m (`[jaw] rail`), so the skirts over them are short.

The prow is two convex outer hulls: O_U (the seam outline at `seam_h` 2.75 with the front edge (+-0.7, `tip_y`
-12.492) and the rear corners (+-4.5, -5.0), and the `top` points, which lie 2 cm under the hull's top along y -4.6, so
the top grows out of the hull with no step) and O_L (the seam outline and the `belly` points: the hull's flat bottom,
0.77, run on forward, the chine, the hull's bottom at y -4.6 and the keel point). Three pieces (all `grounded`, `collide`, `outside`):

- `jaw_lower`, placed at `lower_hinge` (0, -8.1, 1.2), the ramp's hinge: the shell of O_L forward of the hinge line
  and under the rail plane (the deck's plane + `[jaw] rail` 0.45, default `RAIL` 0.30): the belly, the low side rails (their tops `glow_cyan`),
  the deck plate in the deck's plane (flush with the floor at the hinge), a bulkhead under it, ribs and amber lit
  edges (`nocol`). The underside (the plates and under-skin of the faces looking down, built closed), the tip's
  seam rim and the deck plate's underside and edges (`lower_deck_edge`) are `nocol` too: open they lie under the
  deck; near the tip only the deck's top face collides (a test holds every collider face there fronting up). The deck plate runs
  3 mm inside the skin, and the inner faces are clipped under the deck, only on the front and belly faces; on the
  sides, which face down too since b3, that let the deck and the throat show through. Its aft face under the hinge leans forward `V_DEG` 36 (the swing is 34.37), so it never swings
  into the root; closed this leaves a V-shaped hinge groove under the belly, closed at its top.
- `jaw_upper`, placed at `upper_hinge` (0, -4.6, 4.88), on its rear line on the hull's top: the shell of O_U and the
  skirts (O_L over the rail plane forward of the hinge line, their lower edges `glow_cyan`), a ceiling plate (the
  roof's underside, `roof_h` 3.51 at the hinge line falling to the seam at the tip) with two cyan bars under its
  sides, a bulkhead over the seam just forward of the portal, and the cyan mouth line (`seam_glow`): closed, the
  parting runs from the tip along the seam and down along the rails' tops, and aft of the hinge line along the seam
  until it meets the hull's lead edge (y -6.2).
- `jaw_root` (plan origin, fixed): the shell of O_L aft of the hinge line; the front bulkhead (y -8.1 .. -8.05) round
  the throat's opening (the tunnel's profile), a lit lip round it; the hood over the tunnel's chamfers and ceiling and
  the lid at the seam beside it (inside the prow; they close the tunnel's outside, which has no faces of its own).

The pieces are built closed, each one's origin its hinge; a pose turns them about Godot's x (+ lifts the front):
`lower_deg` closed 0, half -17.18, open -34.37 (closed the deck rises 19.44 deg to the seam at the tip; open it lies on
the ground at the ramp's 14.93 deg, the tip at y -12.6), `upper_deg` 0, 1.5, 3.0. `[jaw] pose` (default `open`) is what
the game, `--godot`, the walk and the export get: a jaw piece's placement row in a request carries the angle as a 4th
element (`ship.places`), which `ship.gd` and `export_scene.gd` apply. `ship_layout.check_jaw` holds the lower hinge on
the ramp's, the open deck on the ground at the ramp's slope (under 30 deg) and the head room over it (`jaw_numbers`;
wants the capsule and margin 2.3). `test_ship_jaw.py` also checks, on flat skins (`ship_hull_jaw.PLATED = False`; the
plates sink inside the skin): closed, no ray from a ring of outside points (and from under and over the nose) reaches
the throat or the closed mouth; in six steps of the swing no piece's edge passes through another's face; open, nothing
stands in the walkway; the deck in its plane. The clearing lamp in front of the old ramp moved to (0, -20, 0.5),
range 4.5 (it lit the closed jaw as a gold slab). A lamp in the mouth for the open ramp was tried and dropped: even
shadowed it lit the ground under the closed prow through the one-sided shells; the open mouth glows from its lip, the
ceiling's bars and the rails' edges. The jaws replace the ramp, its lights, its hazard stripes and the entry tunnel's hood
(`mouth_tunnel_in`, the tunnel's inside, stays). The [ramp] numbers stay as the open jaw's.

**The shells' winding (b4).** `ship_build.make` mirrors the plan's y into Blender, which turns a face's winding over.
The jaw's shells are open meshes (`solid` False, so no normal recalculation), wound counter-clockwise about their
outward side in the plan frame, so b2 and b3 came out facing inward. The materials are double-sided and the look
never showed it, but Godot's trimesh colliders are one-sided: the capsule fell through the deck from above, and the
deck plate's underside, which then fronted up, caught it at the tip (the open walk stopped at y -12.65; found by
probing the capsule's contacts headless, every one of them the ground's with the deck in reach, and by a capsule that
fell through the deck from above until the deck shape's `backface_collision` was on). `ship_hull_jaw._front`
reverses the shells' faces in `jaw_lower`, `jaw_upper` and `jaw_root`; `front_normal(q)` gives a face's
Blender/Godot front in the plan frame (the tests use it). The walk's outside points stand on the ground 0.6 m in
front of the open tip (y -13.2, then -14), on the centre line: `ship --godot` walks 18/18.

**In the package** (`ship --export`, art #335 above): `Ship/Nose` holds the three jaw pieces, named by their ids
(`jaw_lower`, `jaw_upper`, `jaw_root`; moved out of `Pieces` by `export_scene.gd` `_nose`), saved in `[jaw] pose`
(open), and `Nose/AnimationPlayer` with `open` (closed to open, `ship.NOSE_SECONDS` 2.5 s: `JAW_VIDEO`'s swing after
the seam lights, each key eased in and out), `close` (the same keys backwards) and `RESET` (the open pose), value
tracks on each moving jaw's `rotation:x` (`ship.nose_request`). No script: the lobby plays `close` and seeks to its
end (HANDOFF). The jaws' colliders are children of their pieces and turn with them. The check
(`_ship_export.nose_problems`, read by `export_check.gd` `_nose`) refuses a Nose without its three pieces or the
three clips, a saved pose that is not open, a clip whose end pose is wrong or an `open` that is not 2.5 s; Pieces
must hold exactly the layout's placements but the clearing's and the Nose's (`clearing_problems`). The seam's cyan
line keeps its static glow (the video's seam fade is not in the clips).

**The defect hunt (b4)** at full size, closed, half and open from the six cameras, inside, the close set and three
in-between poses of the swing (`views/swing.json`: 0.25, 0.6, 0.9 of the open angles, each from the 3/4 front, the
hinges' side and under the prow; a view's `{"jaw": "0.6"}` is that share of the open pose): see
`<raw>/ship/v5/notes/nose-b4.md`. `test_ship_jaw.py` keeps the swing's interpenetration check (six steps).

Views: a `ship --shoot DIR --views FILE` row whose 6th element is `{"jaw": "closed"}` (or `half`, `open`, or a share
of the open pose such as `"0.25"`) shows that pose (`ship.gd` `_jaw_pose`); `{"solo": true}` alone just makes a review sheet. Either way the sheet holds the
file's views alone, `NOSE_SHEET_W` (1600) px wide. `ship --jaw-video DIR` renders the opening (`JAW_VIDEO`: a still
3/4 front camera at eye height, 6.5 s at 30 fps: closed, the seam lights, the lower jaw lowers to the ground, the
upper lifts) into `DIR/open.mp4`. Round b1's views, sheets and video: `<raw>/ship/v5/nose/b1/` (its pieces in
`b1/pieces`, a copy of `v5/pieces` with the jaws built); b2's in `<raw>/ship/v5/nose/b2/` (`views/close.json`: the
close-ups); b3's in `<raw>/ship/v5/nose/b3/` (`var/A..C`: the shape grid); b4's in `<raw>/ship/v5/nose/b4/` (`pieces/`, the
final; `closed/`, `open/`, `half/`, `swing/`, `inside/`, `close/`; `compare.png`: main's ship before the jaw, the
jaw closed and open, side and 3/4); the package `<raw>/ship/v5/export/v4`.

## Lens room C, step 1: the charger's alcove and the east lounge (2026-10-28)

The engineer's look C for the lens rooms (prime-game#1095, 2026-10-27: "the charger in the wall and a lounge corner"),
built from the design's cm drawing (prime-game-design `ideas/ship-components/lens-room/drawing/drawing.js`; the concept
`c_lounge.jpg`). Static decor, `tools/blender/ship_interior_lens.py`; placed by `ship_interior_place.py`; checked by
`tools/tests/test_ship_lens.py`. (History, step 1's plan: the charger unit itself, a faceted pedestal under the
unchanged head, came in step 2: `assets/prop/crystal_charger`, `tools/blender/charger_*.py`.)

The bronze (jambs, conduits, sofa, table, lamp, plant pot) is the stations' shared bronze: `lens_bronze`,
`lens_bronze2` and `lens_edge` in `ship_interior_lens.py`, which `godot/ship/ship.gd` swaps by name (`LENS_BRONZE`)
for `godot/console/console_metal.gdshader`. (Built on the gills branch with its `gill_*` materials; those were
rejected, and the lens rooms came to `main` with the same values under their own names.) `ship --export` ships
it: `tools/runner/ship_export.py` `SHADERS` maps each art shader's path in the `godot/` project to its file beside the
pieces (`console/console_metal.gdshader` -> `assets/environment/ship/console_metal.gdshader`), and `leftovers()`
refuses any `res://` path outside the package.

**The alcove (both rooms, `lens_alcove`, a collider; `lens_conduits_e`/`_w`, none).** On each renewer spot's vertex
(87.82 deg aft of the room's outward axis), in the charger's frame (`charger_dims.toml`: u across, d out of the wall
from the vertex, h up; cm), the piece's origin the vertex on the deck:

| Part | Numbers (cm) |
|---|---|
| Back panel | graphite, a chord at d 10 across u +-46, h 0..200; a raised plate +-40, h 10..188 |
| Opening | u +-46 at the back (d 10), +-50 at the front (d 46), top 200, its top corners cut (+-50, 182) -> (+-34, 200) |
| Jambs | bronze, u +-50..60, face d 46, h 0..200, a 1 cm face plate; the lintel u +-60, h 200..226, d 0..46 |
| Warm strips | on each cheek (d 22..34, h 104..196), under the head (u +-26, h 194..198), on the lintel (u +-14, h 210..214) |
| Conduits | four, Ø 11, axes at u +-68, d 21; the lower leaves the jamb's outer face at h 92 and turns down (r 8) into the deck; the upper leaves at 170 and turns up into the ceiling; a 3 cm cyan core on the room side |
| Collars | Ø 14 x 4 at the jamb's face and on the straight runs at h 40 and 210; flanges Ø 16 x 3 at the deck and the ceiling |

The ceiling slants, so the two sides' conduits reach it at different heights: one piece per room (the east room's +u
runs toward the door, 2.414 m; the west room's, turned not mirrored, outward, 2.383 m). The two facets behind the
alcove are `tip_panel_plain` (flat plates, no diamond: the back panel stands 10 cm off the vertex and the diamonds'
relief stood 17 cm). `renewer_e`/`_w` `depth_m` is 0.70 (the charger's reach from the vertex; the crystal's axis moves to
d 38, the charger step's), so the player stands at (+-10.393, 2.144); the walk goes there and back in both rooms
(18 points, was 14).

**The east lounge (tip_e only; tip_w waits for the engineer's pick).** theta from the room's outward axis, + aft.

| Part | Numbers (cm, d from a facet's face) |
|---|---|
| Sofa | six modules, one per facet, theta -109.77..+21.95, each ending on its vertices' bisectors (3 mm joints, the cushions 1 cm) |
| Spine | bronze, d 0..18, h 0..88, a bright edge strip under its top |
| Back cushion | d 18..32, h 44..80, its top 4 back; terracotta |
| Base | `lounge_sofa_base`, the collider: d 18..76, h 10..30 over a graphite toe recess d 18..72, h 0..10; the warm strip on the recess at h 7..9 |
| Seat cushion | d 32..76, h 30..44; terracotta, the third module charcoal |
| Arms | 14 wide, h 30..58 on the base, d 18..76, at both ends |
| Table | `lounge_table`, the collider: Ø 56, h 48 at (10.297, 0.375) (theta -112.5, r 85): a plinth with a warm ring, a 12-sided drum, the top with a warm edge ring and a graphite inset; two cans |
| On the spine | the lamp Ø 18 x 36 at (11.706, -0.307), the speaker 34 x 22 x 16 at (12.183, 0.254), the plant (pot Ø 16 x 14, blades to 40) at (12.414, 0.954), each at d 9, facing its facet |
| Pillows | two throw pillows (c_lounge), on the second (terracotta) and fifth (charcoal) modules |

The lounge's facets change round it: their panels' diamonds start at 0.92 m (`tip_panel_low_a`/`_b`, above the
spine), their windows' sill is a flush 3 cm trim (`tip_window_lounge_a`/`_b`, `tip_sill_strip_lounge`: the 16 cm
ledge stood over the spine where the lamp, the speaker and the plant stand), and the two cable trunks at -109.77 and
-87.82 are gone (the concept has none; they stood through the spine). The floor lights at r 108 keep at least 8 cm
from every footprint, and the line from the door to the charger's stand keeps a capsule's radius from the sofa and the
table (`test_ship_lens`). The warm strips are `int_amber__lens` (`[light.mats]` l 0: they glow and light nothing).

## Lens room C, step 2: the charger's pedestal in its alcove, the look fixes (2026-10-28)

- **The charger** (`assets/prop/crystal_charger`, `docs/props.md`): the dome on legs is replaced by the drawing's
  faceted pedestal; the crystal's axis is at d 38, the unit reaches 70 cm (the spots' `depth_m` 0.70), 0.65 cm
  inside the opening's cheeks, its back on the back panel. `test_ship_layout` reads the charger's report again.
- **The conduits** (deviation from the drawing): their axis moves from d 21 to **d 38** (the tubes' front at 43.5,
  2.5 behind the jambs' face line at 46), so head-on from 2.5 m they stand beside the jambs instead of behind them;
  u ±68, the elbows and the collars are unchanged. The cyan core is Ø 4.4 (the drawing's 3) on its own
  `int_cyan__lens_core` (e 0.45, `l` 0: glows, lights nothing; `int_cyan` stays 0.05).
- **The cushions**: `lens_cushion_red` a deeper terracotta (0.17, 0.036, 0.020; was 0.30, 0.075, 0.045, salmon under
  the warm light), roughness 0.92; `cushion_block` rounds their edges (r 3 on the back, 4 on the seat, half that
  underneath) and crowns their tops (0.8 and 1.2 cm over a plateau a third of the way in); the heights at the middle
  are the drawing's (80, 44). The charcoal module and pillows are unchanged.
- **The review with the charger**: `ship --shoot DIR --charger` places the charger's GLB and a crystal on
  `renewer_e`/`_w` (review only; the package keeps the spots as markers), and a `--views` JSON row may carry a
  reference image's path as its 6th element, shot and compared side by side (`compare_<view>.png`). Shots:
  `<raw>/ship/v5/lens-c/r3/` (pieces `lens-c/pieces-r3`).

## Lens room C, step 3: the look fixes before the review (2026-10-28)

- **The "double charger"** in step 2's `lc_w_door` was the review sheet, not the scene: the sheet put `lc_e_door`
  and `lc_w_door` edge to edge, and the two rooms are mirror images, so the east shot's charger at its right edge
  met the west shot's at its left (the "dark wedge" was the cell join). The single shot shows one charger. Review
  sheets now keep gutters between cells.
- **The alcove's back panel** (`lens_graphite`, `lens_graphite2`): metallic 0.55 at roughness 0.38 mirrored the
  room's reflection probe and read light grey. Now the drawing's graphite: dark grey, metallic 0.12, roughness 0.66
  (the plate 0.7). The sofa's toe and fill and the table's inset share it. (Since the charger traces the panel is
  `lens_panel`, navy, and the plate is gone.)
- **The cushions**: `lens_cushion_red` (0.075, 0.015, 0.010), darker and browner (step 2's 0.17 read orange-salmon).
- **The charger**: the pedestal's detail and darker plates (`docs/props.md`, build `lens2`).
- **`ship --shoot --charger`** runs `godot/charger/room.gd` (ship.gd plus `charger.gd` and `crystal.gd`): the charger
  in its game look, idle, the crystal seated and spent (`"charge": 0.0`; a row's own dict can say otherwise). Before,
  the charger wore its GLB's plain fallback and ship.gd's pass made strip lights of its emissive strips. A full
  crystal's light floods the lens room cyan (`r4-charged/`): an open question for the crystal's light in this room.
- Shots: `<raw>/ship/v5/lens-c/r4/` (pieces `lens-c/pieces-r4`).

## The charger's cycle in lens room C (2026-10-28)

`ship --charger-cycle DIR` (`godot/charger/cycle.gd`, extending `charger/room.gd` in ship.gd's off-screen "shoot"
mode) films one full cycle of the east charger at night: the eye at the player's 1.6 m, 1.5 m in front of the
charger's front (2.2 m out of `renewer_e`'s vertex), fov 60, so the whole charger and the alcove are in the frame.
A fixed clock (`step(dt)` at 1/30 s; every value a pure function of the time, eased, never linear) drives only what
the charger and the crystal have: `set_state` (idle 0..5.9 s, charging to 17.0, charged to 20.3, idle), `set_pressed`
(5.6..6.3 s, eased in by a share of its `TRAVEL`), `set_carrier` (rise 6.4..7.6, 4 whole turns 6.9..15.6 with eased
speed, down 15.8..17.0), `set_ring` (3 turns the other way) and crystal.gd's `set_charge` (0 to 1, 7.4..15.4). Two
stand-ins, as the game has no hand: the crystal's way into the cup and out (an eased Bezier from above the player,
its last leg down the axis). Since the charger zap the electricity runs too (below).
Output: `cycle.mp4` (1280x720, 30 fps, 24 s, under `max_mb` 15), `keys/` and `keys_sheet.png` (fourteen labelled beats, `cycle.gd` `KEYS`, since
the traces) in `<raw>/ship/v5/charger-cycle/` (`--out` names the pieces: a set built from this tree with `ship --build --out DIR`; lens-c-main's `lens_alcove` predates the traces and films a pale panel, art#263 cycle2). The frames take
about 4 min. `cycle.json`'s `trace_surfaces` counts the traces the east charger drives (3).
Since zap-4 (the manager, 2026-10-28) a second camera films every frame again about 1.0 m from the crystal (1.4 m out
of the vertex, eye 1.5 m, `CHARGER_CYCLE["close"]`): `close/cycle.mp4` and `close/keys_sheet.png`, for the
engineer; the frames take about twice as long. `zoom_sheet.png` crops four charging frames of the 2.2 m camera
(9.6, 11.4, 13.2, 14.6 s; `cycle.gd` `ZOOM`) to 320x180 px round the crystal, scaled 2x, to judge the electricity at
the player's distance.

## The charger traces on the alcove's back panel (2026-10-28)

The engineer's pick for both lens rooms (prime-game#1095 c6468773545; the concept
`<raw>/ship/v5/charger-traces/concept/a_circuit.jpg`): glowing cyan circuit traces on the back panel, lit by the charge.
- **The panel** (`back`, d 0..10, u +-46, h 0..200) is `lens_panel`, a matte dark navy (#0b1a2e, roughness 0.82). The
  graphite plate on it (`back_plate`) went: the traces run edge to edge.
- **The traces** (`ship_interior_lens.py` `TRACE`, `trace_layout()`, `trace_parts()`; material `lens_trace`, no
  collider of their own beyond the piece's `-col`): lines 1.2 cm wide, orthogonal with 45-degree bends, mirrored left
  to right (one centre line on the axis). Trunks run from an outer end to the ring behind the crystal (centre u 0, h
  115, radius 18 to the line's middle, a 1.5 cm line): the centre line and two lines from under the head strip, two
  lines from hollow dots (Ø 4) beside the centre line, and the low conduit's line from the side edge at h 92 (behind
  the pedestal, then up the gap between the outer prong and the cheek, into the ring's side). Branches end on the top
  lane's trunk at 45 degrees: one down from the lintel and the high conduit's pair from the side edge at h 167 and 173.
  Each kind sits a hair proud of the panel (branch 0.6 mm, trunk 0.8, dots 1.0, ring 1.2), so a branch's end tucks
  under its trunk and a trunk's under the ring; nothing is coplanar.
- **The fill coordinate**: each corner's UV x runs 0 at the line's outer end to 1 at the ring (a trunk: its arc length
  over its length; a branch reaches its trunk's value at the junction, so the fronts meet there); UV y (Godot's, after
  the glTF exporter's v -> 1 - v) is the line's metres per unit of fill, -1 on the ring.
- **The look** (`godot/charger/traces.gdshader`, emission only: no strip light, it lights nothing). ship.gd swaps
  every `lens_trace` surface for one idle copy (`TRACE_MAT`); `godot/charger/traces.gd`'s `bind(look, scene)` gives
  the traces near a charger's crystal (`PANEL_REACH` 1.2 m) their own copy in its charger.gd look, `set_panel(look,
  fill, flare, lit)` drives it (not in charger.gd: its copy ships in `assets/prop/crystal_charger`, the panel is the
  ship's): idle every line at 13 % and the ring at 18 % (full: emission 1.3 of (0, 0.6, 1); 3.0 and 1.5 read pale under AgX); charging a full cyan behind the front at the charge fraction, dim
  ahead, a small white-cyan head on it, the ring building to 35 %; full the ring flares (`flare`, a 0.3 s pulse,
  white-cyan) and everything holds full; `lit` 1 -> 0 fades it back to dim. The cycle drives them (`cycle.gd` `FLARE` 15.4..15.7 s, `FADE` 0.5 s from the crystal leaving the
  cup); `--shoot --charger` sets the fill from a view's state and charge.
- **The export** ships the shader as `assets/environment/ship/charger_traces.gdshader` (`ship_export.SHADERS`).
- Tests: `test_ship_charger_traces.py` (mirrored, orthogonal and 45 degrees, apart and inside the panel, the ring on
  the crystal's axis, the fill 0..1 and the junctions, faces toward the room, the export's shader).
- Output: `<raw>/ship/v5/charger-traces/` (`pieces/`: lens-c-main's with the new `lens_alcove`; `cycle/`).

## The charger's electricity (2026-10-28)

The engineer on the cycle (prime-game#1095): "no effects at all ... some electricity there". `godot/charger/zap.gd`
is the reference the game copies (not in charger.gd, whose copy ships byte-equal in `assets/prop/crystal_charger`):
`bind(look, ship, crystal)` after `Charger.apply` and `seat_crystal`, then `step(look, dt, charge, flash, lit)` each
frame. Everything follows the charger look's state and the charge:
- **Arcs** from the four electrodes (two per inner prong: `charger_dims.toml` `[inner] electrodes`, placed as
  `charger_build.build_electrodes` does, on the track ring) into the crystal: each leaves its electrode's surface and
  lands on the crystal's surface (a radius profile by height from its meshes), the tip pair 4.5 cm below its electrode
  (level, 2.5 cm long, they read as nothing from 2 m), the low pair 9 cm above, jittered up and down and round the
  axis. Ribbons 4 cm wide (the tip pair; 3 the low; zap-4: 2.2 cm still read as fine squiggles from 2.2 m), a white
  core of 40 % of that, a blue haze round it. A bolt is midpoint displacement (16 segments, the ends fixed)
  with 0..2 fading branches; the shapes re-roll every 50..80 ms from a seeded generator and are rebuilt every frame on
  the electrodes' and the crystal's current places, so they follow the turning ring and the rising, turning crystal.
  The low pair skips about half its ticks, the tip pair a tenth (the flicker). Drawn as camera-facing ribbons
  (`godot/charger/arc.gdshader`: unshaded, additive, a white-cyan core over a cyan halo, HDR for the glow) in one
  `ImmediateMesh` under the charger's root.
- **Wrap arcs and halo loops** (zap-3, zap-4/5; the engineer: "lightning, white, around the crystal, spinning"): from
  every electrode a wrap arc leaps into the air round the crystal (1.5..2.3 times its radius) and runs 1.2..3 rad round
  it the ring's way; each tick 3..5 halo loops (8 in the flash) leave the crystal's surface, arch out to 2..3.4 times
  its radius, tilted up to 12 cm, jagged by 1.4 cm and 1.8 cm, and land again 1.2..2.6 rad round, most with a fork
  off the apex into the air (2.5..5 cm), and the whole cage turns round the axis at 9 rad/s between re-rolls,
  so it spins; a crawler runs between two surface points of the tip pair. Glints (6..10 per tick, 70 in the flash)
  orbit the crystal the ring's way and spiral out, a 2.4 cm head with a 0.7 rad trail.
- **Lights**: one small `OmniLight3D` per arc at its hit (range 0.32 m, 0.45..0.7 flickering, a near-white blue
  (0.78, 0.88, 1): zap-4, the old cyan (0.45, 0.82, 1) times the bronze's orange is olive; 0.8 washed the inner prongs
  to chrome).
- **Sparks** at the hits each tick (2..5) and now and then at an electrode: short streaks (0.15..0.4 s, gravity,
  drag) simulated in `step` on the caller's dt (not GPUParticles3D), so the fixed-clock cycle draws the same frames
  every run.
- **The flash** (`flash` 0..1, `cycle.gd` `FLASH` 15.4..15.62 s, with the ring's flare): every arc on, 2.2 times
  wider, four branches each, re-rolled every 30 ms, a burst of 60 sparks, the lights to 2.4 over 0.6 m. Then quiet.
- **Gating**: arcs only while the state is "charging" and 0 < charge < 1, or during the flash (still "charging");
  never idle or charged.
- **The conduits** (`lens_conduits_e/w`, material `int_cyan__lens_core`): the cores' UV x runs 0 where a conduit
  leaves the jamb to 1 at the deck or the ceiling, UV y (Godot) is the run's length (`ship_interior_lens.py`
  `core_uvs`). `bind` puts one `godot/charger/conduit.gdshader` copy on the cores near the crystal (`CONDUIT_REACH`
  1.2 m), its base the surface's own glow: while the arcs run, the base dims to 40 % and near-white bands (22 cm,
  0.6 m apart, 1.1 m/s, energy 9; zap-4: 12 cm at 5 over the full base did not read) run from the deck and the
  ceiling into the jambs; once full the core glows steady a little brighter; `lit` (the traces' fade) brings
  it back to the base.
- **The export** ships `charger_arc.gdshader` and `charger_conduit.gdshader` (`ship_export.SHADERS`) beside the
  pieces for the game's copy of zap.gd; the ship scene itself does not use them.
- `cycle.json` adds `conduit_surfaces` (1), `arc_frames` and `arc_ends_off` (frames whose arc ends left an electrode
  or the crystal's surface: 0; the runner fails the run on any; the start lies on an electrode by zap.gd's
  construction, so only the hits are a real check). Keys: "4 charging: the arcs" (12.6 s) and "5 full: the big flash" (15.5 s).
- Tests: `test_ship_charger_zap.py` (the electrodes are the build's, the ends, the gating, the flash inside
  "charging", the conduits' UV, the shaders shipped).
- Output: `<raw>/ship/v5/charger-zap/` (`pieces/`: charger-traces' with the new `lens_conduits_e/w`; `cycle/`).

## The west lens room's workshop (steps 1 to 4, 2026-10-29)

The engineer's pick for the west lens room (prime-game#1095: "visually I like the robot repair the most"), built as
decor from the design's cm drawing (`<raw>/ship/v5/workshop/drawing/index.html`) and its concept `w_c_bot.jpg`
(painted on the east room; tip_w is its mirror, the charger left of the door). Nothing moves and nothing is a
station; only the light lives. Builders: `tools/blender/ship_interior_workshop.py` (registered in
`ship_interior.MODULES`); placements: `ship_interior_place.py` (the drawing's east angles mirrored, `a_w = -a_e`);
tests: `tools/tests/test_ship_workshop.py`.

| Piece | What | Placed | Triangles |
|---|---|---|---|
| `ws_bench_open_top`, `ws_bench_open_low` (colliders) | a bench module per facet -109.77..-21.95 (east), each with one drawer out (step 3; the closed `ws_bench` is no longer placed): a flush matte graphite kick plinth h 0..9 (step 3: the fronts' feet stayed dark), graphite carcass (face d 50), two drawer fronts (h 10..45, 47..82; an olive graphite frame `ws_bronze2`, step 4) each with a chamfered raised panel (`ws_olive`, a dark olive bronze, step 4: the neutral bronze read warm brown under the floor lights) and a lit green pull, the green strip under the top's overhang, the dark bronze top d 0..55 to h 90 (continuous across modules) with a glossy bronze nosing, a graphite work mat; `open` leaves a drawer's bay (graphite back, two stiles) | 4 facets | 240 / 228 |
| `ws_drawer_eyes`, `ws_drawer_parts_a`, `ws_drawer_parts_b`, `ws_drawer_limbs` | a drawer pulled out 25 cm on its tray, a dark foam insert 14 cm under its top (the parts trays' a mid grey `ws_foam2`, step 4: on the dark foam their bronze parts did not read), a green rim line round the walls' insides: 20 spare eyes (D8, a cyan iris, a dark pupil) sunk in cut-outs (a 32.9, top); loose parts (gears, pistons, a board with a cyan light, a spare claw, a cable coil; a 54.9 low, 76.8 top); four spare arms (shoulder, ivory upper arm and forearm, dark elbow hinge, small claw) in a row (a 98.8, low) | 1 each | see the handoff |
| `ws_cabinet` (collider) | the cradles' cabinet module, as the bench: toe, graphite body, one drawer front with its panel, pull, strip, the top d 0..59 to h 55 with its nosing (the drawing's 60 reached 1 mm over the floor light's bar on the middle vertex) | 2 facets | 172 |
| `ws_cradle` | a graphite bowl D54 x 18 with a groove and a chamfered lip, the bed D44 with a padded dark cushion (a fat rolled edge, a dished middle with six sunk tuft buttons, a stitched groove), the green ring on the lip | 2 | 5328 |
| `ws_sleeper_a`, `_b` | a small robot D28 in its cradle's dip: the main robot's family: an ivory shell band and two closed side shells on 2 mm seams round a dark core, one small layered eye (graphite bezel, dark glass lens D8) shut as a dim green arc, an antenna with a green bead; tilted face-up 22 deg, each rolled and turned its own way | 1 each | 10168 |
| `ws_robot_body` (collider) | the main robot's dark core (flat mechanism plates at y +-0.205) and its thin ivory shell band (the sphere D60 at h 145 between the side shells) in four panels with 6 mm seams, a dark liner inside; its collider the drawing's sphere D60 as one convex 16 x 8 polyhedron (`col-convcolonly`, 224 triangles; the shells' own trimesh was 9.2k), the visible parts no collider | 1 | 9216 + 224 |
| `ws_robot` | the layered eye D16 toward the room (a proud dark bronze bezel, a bronze trim ring, a dark glass dome, a teal iris in five 3.6 mm bands on one level from the deep rim to a bright inner ring (step 4: step 3's three bands at three lifts showed as rings), a dark limbal ring round the pupil, one small soft glint), the crown and its knob ball, the two thin side shells (step 3: 28 deg caps, 0.7 of step 2's, ivory outside, a matte graphite liner inside) standing 2.5 cm off the body (step 4: 5 cm read as headphones from the front) on two graphite hinge arms each and swung 30 deg on back hinges (`ROBOT` panel, lift, open, hinge; `shell_xf`), in each bay a gear train of three with hub caps, two pistons in mounts, a board with chips and a cyan light, a silver motor, two cable loops and three cables hanging under the body to loose plugs (four colours), two arms below the body (shoulder ball in a collar, ivory upper arm, graphite elbow hinge, ivory forearm, wrist ring, a claw of three two-segment fingers) hanging to h 95; every bay part stays inside the shells' sphere | 1 | 27932 |
| `ws_rail` | the bronze box rail 10 x 8 from h 214 on the arc r 105 over a_w 25..110, glossy side lips, end stops, three hangers (5 x 2 bars, 16..18 cm showing) into the slanted ceiling (theta -100, -67.5, -35 east) with plates; step 2 lowered it 14 cm from the drawing's 228 so the hangers show; it clears the 1.8 m capsule by 34 cm | 1 (room frame) | 1896 |
| `ws_hoist` | a chunky chamfered bronze carriage (30 x 17 x 12) with inset end panels, cheeks rising over the rail and two wheels riding its top on axles, a graphite motor drum with cooling fins and a green status light on its room side, a short thick steel rod (D4.4) with bronze collars, the claw: a bronze hub (h 183..188) and three two-segment fingers on graphite knuckles whose pads grip the crown's knob ball (down to h 176.6) | 1 | 4540 |
| `ws_rug` | dark green pile D66 x 1.1 with a rolled edge and a darker border band, at r 1.10 on a_w 67.5 (the drawing's D80 at r 0.95 covered the floor lights' bars; D66 fits between them with 2.1 cm to spare; the check asks 8 mm and more of every floor item, the cabinet the closest at 9 mm) | 1 | 1152 |
| `ws_lamp` | the articulated lamp on the bench (a_w 100): bronze base D18, turntable, twin arms through graphite hubs, the shade at h 140 aimed at the robot's open bays, its green lens | 1 | 2016 |

About 122.5k triangles placed (step 1: 68.6k, step 2: 100.5k). The bench's facets take the lounge's wall pieces (`tip_panel_low_*`: the relief over
h 0.92; `tip_window_lounge_*`: a flush 3 cm sill), the cabinet's keep the plain window facets. The door side's last
two cable trunks (`tip_trunk*`) stood on the bench's vertices and went with it; the pieces are gone from the layout.

**Light** (step 2: step 1's broad green washes flooded the walls and ceiling). The walls and ceiling keep the ship's
neutral silver under the tip room's own lamp and its fill (a neutral cool grey, 0.62/0.70/0.86; step 1's mint is
gone). The acid green only pools, the `shop` lamp group (`ship.toml`, `shop_lamp` 1.0): three short omnis before the
bench fronts (r 1.30, h 0.80, range 0.75, energy 1.8 since step 4 so the olive fronts stay olive under the floor lights: the strips' light on the drawers and the floor before them; step 2's first
try, spots straight down on the bench, painted green blobs on the mat), a spot over each cradle (34 deg, range 0.95),
the bench lamp's spot aimed at the robot's bays (24 deg, a near-white work light (step 3: green there tinted the bays); a lamp row's index 11 is a spot's aim
point [x, y, h], `godot/ship/ship.gd`), a little omni in each open drawer (range 0.42; step 4: the two parts trays' paler, 0.6/1.0/0.45 at 0.6); the bays light themselves
(their cyan boards; omnis there washed the shells' insides green).
The strips, pulls, rims, the drawers' liners, the lamp's lens and the sleepers' eye arcs are `ws_green__*` glows
(`[light.mats]`, `l` 0: they light nothing); the eyes' and the bays' cyan `ws_cyan__*`, the eye's highlight
`ws_glint`. The cabinetry's dark olive bronze `ws_bronze` and its near-graphite second tone `ws_bronze2` are the
stations' bronze shader with darker colours (`ship.gd` `LENS_BRONZE`; step 1's lens bronze read orange plastic under
the floor lights).

**Checks** (`test_ship_workshop.py`): the robot, cradles and lamp at the drawing's tip_w points; the bench and
cabinet on their facets, their heights and depths; the robot's sphere D60 at h 145, its eye toward the room, the
hands at h 95, the claw 176.6..188 on the knob; the shells open 30..40 deg, the bays' mechanism inside the shells'
sphere, the arms and loose cables below the body; the rail 15 cm and more under the ceiling, over the capsule, and
clear of the oculus's light ring;
every vertex of every piece inside tip_w's facet planes; the bench, cabinet and rug clear of the eight floor lights' bars by 8 mm and more (the open drawers float
over two bars' outer ends at h 10+, never over their middles); the door-to-charger path clear by the capsule's
radius; everything past a_w -24 (the alcove spans -105..-70); the colliders.

Shots and sheets: `<raw>/ship/v5/workshop/` (`pieces/`, `shots1/` .. `shots4/`, `sheets/`, `grids/`, `views2.json` ..
`views5.json`; step 4's `ws_hoist_wheels` shows the wheels on the rail from the window side); handoffs
`<raw>/ship/v5/notes/workshop-1.md` .. `workshop-4.md`. Steps 2 and 3 were tuned by grids
(`grids/`; step 3's shells: 0.8 / 0.7 of step 2's on back hinges, 0.7 on front hinges, picked 0.7 back, `robot3_grid_*.png`): the robot's shells (panel/open 40/30, 40/36, 37/42; picked 40/36, set to 32 in the room: at 36 the dark insides read as two black ears from the bench; front hinges tried, they hid the bays) in headless Blender, the light (the
shop lamps' level 1.0/1.6/0.7 and the fill's colour, from the concept camera) in Godot.

## The throat's gills (pilot, 2026-10-28)

**Parked since 2026-10-29**: the throat is shown without its gills (the engineer: the slits come back as hinged
gill covers), so `th_gills_e` and `th_gills_w` are out of the layout and the throat's walls are the clean throat's
(below, "The clean throat"). The builder, `gill_row.gd` and `--gill-anim` stay as they were; their tests skip.

The throat's wall modules and vent cabinets gave way to one gills piece per side (`th_gills_e`, `th_gills_w`, mirrored;
`tools/blender/ship_interior_gills.py`): a plinth 0-60 cm with its cyan line, then a clean band on the throat's own
profile (vertical to 1.45 m, leaning 0.55 m in to 2.30 m) from the roof line (s 1.62) to the hall corner (s 4.05),
its top 3 cm into the ceiling; the plinth and its line run on under the ramp roof from the mouth's corner (s 0.02),
as the approved concept `<raw>/ship/v5/gills-throat/concept/side_right.jpg` draws one plinth, and so does the band
(step 4): its mouth part (`band_mouth`, s 0.02-1.62, the plinth's top to the bend, where the tunnel's chamfer leans
over it) lies 3 mm in front of the jambs, so one clean band runs from the ramp roof's edge to the hall's corner. The
throat's ceiling keeps only its two middle panels: the corner wedges' panels hung 3 cm under the ceiling by the hall's
corners. Step 5 (the engineer: "around the gills textures climb onto textures"): the header under the hall's rim stops
at the throat's ceiling; by the corners only an 8 mm skin on its hall face (`TH_SKIN`) still closes the chamfer's
triangle from the hall, behind the band, whose lean now runs on to that face (the full 20 cm drop stood over the band
as a dark slanted block). A cornice (6 cm, 2.2 cm proud, `int_silver_c`) runs along the band's top under the ceiling;
the plinth's line is 2.4 cm at emission 0.4 (was 1.2 cm at 0.12). The mouth's column (the tunnel's wall forward of the
nose, `mouth_tunnel_in`) is the band's metal with the plinth, kick and line run on to the tunnel's front; the jambs'
inner faces start at the bend (below it the band and plinth are the wall) and the tunnel's 10 cm hull-silver strip
under the bend is gone, so each surface there is one piece. Five slits (s 1.95-3.43,
37 cm apart) are true crescents after the concept (step 3): both arcs through the same tips 1.20 m apart up the band,
the outer arc sagging 0.27 toward the mouth, the inner 0.06 (21 cm wide at the middle, about 1/6 of the chord), a
thick bevelled rim (5 cm, 2.2 cm proud) on the convex side. Each recess (13 cm) holds a glowing back and 36 fine
filaments radiating from the outer arc's centre (step 4: 3 mm ribs 2.2 cm off the back, emission 0.3 over the back's
0.15; step 3's 6 mm blades 7.5 cm deep at 0.6 read as pale blue-white sawteeth). Two dark shutter leaves close over it, meeting on the crescent's
middle line, each meeting edge a thin light line (a fault: red); they slide 12.3 cm apart along the wall through
slots in the recess walls into pockets under the band. Sliding along u is the same move on both planes of the 1.45
bend, so each leaf is one rigid node; the leaves are built open, so the GLB's rest is the calm glowing row. (Hinged
lips, step 2, hid the filaments: the calm row read as thin scratches.) Neighbouring slits' open leaves stay 2 cm
clear of each other's crescents, which caps the crescent at about 21 cm. The button (s 3.72, h 1.15): a dark dome
13 cm across, rough enough (0.38) to show no blocky reflections, in a bright cyan ring, in a 24 cm octagonal recess.
The vent stations' spots stay at design's 3/5 of the wall (`ship.toml`); the export's vent package is the gills piece
(`ship:th_gills_<side>`).

Step 6 (the corner, the cornice, the mist): one clean column (`corner-col`, `int_silver_a`) stands at the band's hall
end from the floor to past the ceiling, in the band's frame: its hall face lies 2.6 cm hall-ward of the header clip
(`COL_PROUD`, 1.6 cm past the header's hall face), its throat edge vertical to the bend at u 3.80 (the button stays in
view) and leaning to u 3.58 at the ceiling, so from the throat the corner reads as the concept's single column. The
throat ceiling's corner trims (`throat_ceil`, `TH_GILLS_COLUMN`) are gone: the column covers that seat from both sides,
and from the throat the trim hung past the column's edge as a slanted strip ending in the air. The cornice is
`hull_silver` (3.2 cm proud) over a 1.4 cm dark shadow line (`cornice_gap`): the three `int_silver_*` share one look
in `ship.toml`, so `int_silver_a` would not have read lighter. The band's mouth part lies flush with the band
(`MOUTH_W` 0, its top 2 mm under the bend where the jambs start): its 3 mm end step read as a dashed light line at the
roof line. The filament blades taper to their inner end (their square ends read as steps at the leaf's edge). In
`gill_row.gd` the slit's light and mist were placed 0.3 m behind the wall: the throat is the GLB's +z (the band leans
to +z), not -z. Both now stand in front of the slit, the lights at a third of their old energy (`LIGHT_ENERGY`, range
0.8 m; at the old values the whole band went cyan) and the mist a soft additive puff 22 cm out and 20 cm toward the
mouth (`MIST`, `MIST_OUT`). The matched camera for design's concept is `gill_view(2.25, 1.23, 4.3, 0, 0)` at a 52 degree
vertical field of view: level, as the concept's verticals are, the band's top and the floor line at its heights.
Step 6b: the mist from a three-way grid (`<raw>/ship/v5/gills-throat/sheets/mist_grid_6b.png`; a view's gills pose
takes `"mist": {"k": strength factor, "w", "h": puff size factors}`): the pick is 0.6 open (calm 0.375, gasp 0.49) on a
0.68 x 1.04 m puff swaying slower. From 2.5 m it reads as a soft puff on the mouth side of each open slit, not a fog
wall, and the band stays its metal. It is still an additive billboard, with no volumetrics.

- `godot/ship/gill_row.gd` drives a row: calm and open (leaves open, cyan, a soft additive mist toward the mouth), gasp
  (60 % open, red-orange), shut (closed, dim cyan line) and fault (closed, red line), and the button ring's white
  flash; `ship.gd` takes a per-view pose (`{"gills": {"e": {"slits": {"3": "gasp", "2": "fault"}}}}`).
- `ship --gill-anim DIR`: the 6 s proof (shut, gasp, shut, open with an overshoot, settle) as `gill_anim.mp4`,
  off-screen; with `--gill-demo row` the 10 s row demo (`gill_row.gd` `play_row`) as `gill_row.mp4`: the breath runs
  1-2-3-4-5-4-3-2..., each shut slit it reaches gasps, a press during a shut slit's gasp opens it (the ring flashes
  white), all five open -> the exhale.
- A `--views` file's 6th element may be a dict with a pose and a `"ref"` image path: the shot is also saved beside
  the reference as `compare_<view>.png`.
- Tests: `tools/tests/test_ship_gills.py` (numbers, mirror, placement, corners, band to ceiling, plinth); skipped
  while the gills are parked.

### The clean throat (step B, 2026-10-29)

The engineer approved step A's proposal ("fold at 2.10"; the drawing `<raw>/ship/v5/gills-throat/clean/drawing/
throat_clean.png`) and asked to see the throat whole without the gills. `tools/blender/ship_interior_throat.py`:

- **Profile.** ship.toml throat `chamfer = [2.10, 0.25]`: the walls stand vertical to 2.10, then a 25 cm cove leans in
  to the flat ceiling at 2.30. 2.14 is the highest fold the hull allows with 0.25 in: the roof's outer corner keeps
  15 cm of skin at s 1.78. `tunnel_chamfer = [1.45, 0.55]` keeps the entry tunnel and its hood (`mouth_tunnel`, the
  notch jamb's clip) as they were, and the parked throat vents read it too (`S.TUN_BEND`, `S.TUN_IN`). The hull's
  throat sample (`ship_hull_shape.chamfer_outer`) derives the cove's outer face from the profile; it used to be a
  hard-coded 0.17. `ship --check`: least skin 0.150.
- **Walls** `th_wall_e` and `th_wall_w` (mirrored, a collider each; frame as the gills'). Each is one flat panel
  (`int_silver_b`) from the ramp frame to the hall jamb (s 1.668-3.88) and from the plinth to the fold. Below it are
  the plinth (0-0.60, 3 cm proud) and its cyan line (2.4 cm) from s 0.02. Above it are a dark 1.4 cm line at the fold
  and the cove in the lighter `hull_silver`, cut on the header's plane at the hall end and on the frame's plane at the
  ramp end (cut square to the wall, its top had begun 6.8 cm aft of the frame). Under the tunnel the band reaches only
  the tunnel's bend (1.45). Each wall is 58 triangles, with no seams, slits or button.
- **Ramp frame** `th_frame` (hall-relative, replacing the roof line's `th_arch`). It is the plane y -5.60 .. -5.515
  over the roof line. On each side one solid fills the step from the tunnel's profile to the room's, with an 8 cm
  trim inside the tunnel's walls and leans; it runs 2 cm into the walls and up into the ceiling. A bar across the
  ceiling sits 5 mm under it, so the 2.30 head room holds.
- **Hall jambs** `th_jambs` (hall-relative, colliders, replacing the hall pilasters and their strips at the corners
  K). Each jamb runs from the deck to the rim (3.20). Its end face is square to the wall at s 3.88, 13.1 cm deep. Its
  front is the corner sub-facet's chord, and a reveal square to that chord runs through the header's depth. Its hall
  face stands 1.6 cm proud of the header's. Beside it, `drop` carries the header's throat face down from the ceiling
  to the cove, between the jamb's front corner and the cove's top line (s 3.73), so the cove's end has a face and no
  gap opens under the header. The wall, plinth, line and cove all end on the jamb.
- **Ceiling** `throat_ceil`. One flat body between the coves' tops from the roof line (inside the frame), a 2 mm dark
  spine from the frame's aft face, and the header from 2.30 to the rim. The skin under the ceiling (`TH_SKIN`), the
  corner trims and panels, the middle panels, `th_end_cut` and the old end modules' branch are gone.
- The station spots `vent_e` and `vent_w` stay. Their 1.6 m band lies on the walls from s 1.63, 4 cm under the frame's
  trim, where the panel runs on behind it. The export names `ship:th_wall_<side>` for them, with no vent hardware.
- Shots, close-ups, sheets: `<raw>/ship/v5/gills-throat/clean/` (`pieces/`, `shots/`, `shots/close/`, `sheets/`);
  handoff `<raw>/ship/v5/notes/gills-throat-clean-b.md`. Tests: `tools/tests/test_ship_throat.py`.

### The gill cover pilot (2026-10-29, dropped)
Design's hinged gill covers (`ideas/ship-components/gill-covers/`) were piloted (one, then five a side) and dropped the
same day: the engineer found a cover that opens "like a little cabinet" ugly. The cover module, `gill_cover.gd`,
`--cover-anim` and their tests are gone (handoffs `<raw>/ship/v5/notes/gills-covers-1.md`, `gills-covers-2.md`). Kept:
`ship_build.py`'s `"nocol": True` part flag (decor on a colliding piece gets no `-col` collider).

### The gill set (2026-10-29)
The engineer's final pick: prime-game-design `ideas/ship-components/slits-lamps/set_plate.jpg`. On the clean throat's
east wall and, since step 6, its mirror on the west (`GILL_SIDES` in ship_interior_throat.py):
- **Build** (`tools/blender/ship_interior_gillset.py`, parts of `th_wall_e`, all decor with `nocol`, nothing moves):
  - five crescent niches at the old slots (s 1.95/2.32/2.69/3.06/3.43 = each crescent's middle), both arcs bulging toward
    the mouth; chords 1.18/1.08/0.98/0.89/0.80 m, bottoms 0.80 -> 0.84, leaning back 3-7 deg (a shear: the top toward
    the hall). Each is a smooth scoop 6.5 cm deep cut into the band (one band column per slit), in three glowing parts:
    `gill<k>_scoop` (the mouth-side half, dim), `gill<k>_glow`, `gill<k>_edge` (the hall-side lip, bright);
  - a turn bar over each slit: `gill<k>_bar` (a bevelled frame of the band's metal, 4 mm proud) and `gill<k>_bar_glow`
    (14 x 3 cm, 2 mm off the wall);
  - `groove` / `groove_glow`: a cubic Bezier round the set's mouth side from under the fold (s 1.93, h 2.06) to under
    slits 1-2 (s 2.50, h 0.68), two bevelled lips with a thin glow strip between, tapering at both ends; 5 cm clear of
    every hole (a grid search, `clearances()`);
  - the button at s 3.72, h 1.15 (step 3: larger): an octagonal bezel of the band's metal (corner r 0.11), the cyan
    ring (`btn_ring`, r 0.05..0.078), the dark dome (r 0.05); 5.3 cm clear of slit 5's hole, 5 cm from the jamb.
  - Materials `int_cyan__gset_*` (their GLB colour the shut red) and `int_cyan__cover_btn`, rows in `[light.mats]`
    with `l = 0` (they light nothing through ship.gd's strip lights).
- **Controller** `godot/ship/gill_set.gd` (the game copies it): `setup(piece)`, `step(delta)`, `press()` (flips the slit
  under the white bar: "open" / "shut"), `pose(open, at)`, `reset()`, `info()`. A niche eases red -> cyan in 0.25 s; the
  bars are red over shut slits, cyan over open ones, and ONE white bar runs 1-2-3-4-5-4-3-2, 0.6 s a step (`STEP_S`),
  over open slits too. An open slit puffs steam (a one-shot GPUParticles3D); with all five open a big cloud emits and
  stays. Each niche has a shadowless omni 16 cm in front of it with no specular (the glow on the wall). `time_scale`
  scales the steam (the proof sets it from the real frame time so the MP4 runs at its own clock).
- **Proof**: `ship --out <pieces> --gill-set DIR` (ship.gd mode `gill_set`, off-screen): the 14 s demo (presses at 0.9,
  2.1, 3.3 (shuts slit 4 again), 5.1, 6.3, 7.5, 8.1 s; all open from 8.1 s) from `concept` (square-on, 2.4 m out, the
  wall from frame to jamb as in set_plate.jpg) and `close` (1.5 m from slot 3); `DIR/<cam>.mp4`, `DIR/<cam>/keys_sheet.png`,
  `stills/<cam>_{shut,mid,open}.png`, the posed views and close-ups (`GILL_VIEWS` in ship.py: square_on, from_mouth,
  from_hall, cu_*; `concept_wide` is the clean throat's old wall_square_on) and `sheet.png` beside set_plate.jpg.
  Outputs: `<raw>/ship/v5/gills-throat/set/`; handoff `<raw>/ship/v5/notes/gills-set-1.md`. Tests:
  `tools/tests/test_ship_gillset.py`.
- **Step 2, the look pass**: `ship --gill-set DIR --gill-grid` renders gill_set.gd's LOOK variants (`GILL_GRID` in
  ship.py) posed on the concept camera beside set_plate.jpg (`DIR/grid_sheet.png`). Variants: the bands brighter
  ("next"), darker ("dark"), and a single gradient over the niche (a shader: bright at the hole's edge, dark at the
  bottom; "grad", "grad_tight", "grad_soft"). The pick is "dark", now LOOK's defaults: niche albedo 0.015, scoop 0.03,
  glow 0.15, the hall-side lip 1.0 (dark inside, a saturated rim); the gradient read as a pale lit dish. Bars 0.8 and
  the groove 0.8 with their base a tenth of the glow (saturated, not white-washed; the runner white 1.8), the niche
  omnis 0.12, the groove's glow 15 mm wide. The all-open cloud comes from five small emitters at the slits (0.42 m
  quads), not one box over the set. The throat's four floor lights are `th_light` pieces in `int_amber_throat`
  (`[light.mats]` l 0: their lens glows, they light nothing), so no amber pool reaches the set's plinth; `int_amber`
  is untouched. Handoff `<raw>/ship/v5/notes/gills-set-2.md`.
- **Step 3, a short look pass** (the manager's notes on step 2: the open niche dull teal, the cyan bars pale, the wall
  flat and dark, the all-open cloud a curtain, the button small). The grid (`GILL_GRID`, poses per variant, all open
  too) settled LOOK's new knobs: `cyan` (0.0, 0.7, 1.0) for every cyan glow, and once open the niche's energies x
  `cyan_scoop` 3, `cyan_glow` 5, `cyan_edge` 2 (red keeps 0.03 / 0.15 / 1.0), the bars x `cyan_bar` 0.85, the groove 0.7,
  the button ring `btn` 1.0. AgX greys a bright cyan toward white far sooner than red (its luminance is about twice
  red's), so a deeper cyan at middle energies stays saturated where brighter ones ("halo") went white; a negative red
  (past the gamut) did nothing. The bars, groove and ring are matte (no specular: the reflections greyed them). An open
  niche spills a soft cyan haze onto the wall on its mouth side (an additive sprite, `spill` 0.3, 1.6 x its width,
  7 cm toward the mouth; its omni x `cyan_light` 1.6 and moved there too). `warm` 2.5: a shadowless warm spot
  (1.0, 0.64, 0.38) 2 m out at slot 3's height, a 38 deg soft cone at the band, warms the wall without pools on the
  plinth. The all-open cloud (`cloud` 0.3) leaves each slit toward the mouth and sinks (`drift` 1.6), a light haze
  with the slits readable (the grid holds the cloud about 2.5 s; at 0.6 the MP4's 6 s build veiled the slits again). Handoff `<raw>/ship/v5/notes/gills-set-3.md`.
- **Step 4, the engineer's notes and his walk** (supersedes the build numbers above; his `--play` shots
  `<raw>/ship/v5/play/`):
  - *Slits*: "at a bigger angle, more open". The picture's crescents, measured in its pixels: outer arc sag 0.31 of the
    chord, inner 0.14, width 0.17 (0.29 with the soft shoulder round the cut). A 3-variant overlay on set_plate.jpg
    (sags 0.30/0.33/0.36 of the chord) picked the middle one: `SAG_O, SAG_I` 0.40, 0.156 per 1.2 m (0.33 and 0.13 of the
    chord, width 0.2 of the height; with the lip it reads as the picture's cut and shoulder). Chords 1.08/0.99/0.90/
    0.82/0.74 (still shrinking), middles s 2.074/2.438/2.801/3.164/3.526, bottoms 0.82 -> 0.86, leans 3-7 deg. The
    picture is not to scale: its spacing is 0.41 of slit 1's height, ours 0.34 (the groove's sweep needs s 1.72-2.07).
  - *A real cut* ("on the concept they are cut out of the wall"): 15 cm deep (`DEPTH`), the section `PROFILE` from the
    mouth-side rim: `gill<k>_lip` (a bevel of the wall's metal, catches light), `gill<k>_edge` (the thin rim at its
    foot, the only glow in the GLB, so `--play` shows a dark cut with a red line), `gill<k>_glow` (the inner wall's
    fall, dark) and `gill<k>_scoop` (the floor, the back wall and the overhang's underside: the hall-side rim overhangs
    the floor by `UNDER` 5 cm at the middle, easing to nothing at the tips). gill_set.gd drives edge/glow/scoop as
    before (the lip stays metal). The fatter cuts nest, so the band is a scanline mesh: one strip per pair of the
    slits' row heights (`rim_levels()`), each slit's rim carrying them all (no T-junctions).
  - *Groove*: traced from the picture relative to slit 1 (its top end 0.14 of the chord over slit 1's top tip, the
    widest point 0.59 left of the tips at mid-height, a long flat tail 0.16 under the bottom tip, ending under slit 2),
    rebuilt as two cubic segments meeting at the widest point (`GROOVE`, 7 points), horizontally x 0.85; leftmost edge
    s 1.72, 10 cm clear of every cut.
  - *Button* (s 3.86, h 1.15): a 1.2 cm ring (r 0.060..0.072), a dark dome r 0.06, an octagonal bezel (corner r 0.11)
    with a 9 mm 45 deg outer bevel, a flat face and a round inner bevel whose foot the ring runs under (no slivers).
  - *Bars*: 12 x 1.4 cm glow in a 14 x 3 cm frame (14 x 3 in 18 x 6 before).
  - *No pillar*: the free-standing hall jambs are gone (`th_jambs` keeps only the header's drop); each wall runs on to
    the hall's corner K (`JAMB_U` = `WALL_LEN` - 4 mm) and ends in `end_frame` (`FRAME_MAT`, a 45 deg bevel from s 3.98 to
    3.6 cm proud, then flat to the end), the deck to the fold. `interior.toml`'s plain spot runs to 4.047.
  - Outputs `<raw>/ship/v5/gills-throat/set4/` (pieces in `set4/pieces`); handoff `<raw>/ship/v5/notes/gills-set-4.md`.
- **Step 5, his walk's doorway joins and the gill set in `--play`** (his shots `<raw>/ship/v5/play/` 004-007):
  - *One frame per corridor portal.* The hall pilasters at the corridor openings' edges doubled the portal's jamb and
    strip, the portal's 10 cm band ran 4 cm past the chord into the next facet (its diamond panel), and a cyan arch
    stood 0.38 m behind the portal. Now: no hall pilasters at all (`ship_interior_place` raises if a hall opening's
    edge has no frame; the mouth's edges are the throat's corners), `hall_portal`'s band 6 cm (`rim` = HCH - COR_HALF -
    2 mm, bevel 12 mm) so it ends at the facets' vertex in a bevelled reveal, its strip `hall_portal_strip_l`/`_r`
    centred on it (`at_in`/`at_out` 17/42 mm; the tip portals keep `portal_strip_l`/`_r`), and the corridor's arches
    only at the tip end (`ARCH_X[1:]`; the ceiling ribs keep their spacing; step 6 fixed the tip doors the same way).
  - *The gill set in `--play`.* `ship.gd`'s play mode puts `gill_set.gd` on the placed `th_wall_e` (the white bar
    runs, the niches glow); `player.gd` emits `used` on E (when not flying) and shows a centred "[E] press" hint while
    ship.gd's `can_use` is true: the eye within `REACH_M` 1.6 m of the button's middle, in front of the wall, the look
    within `AIM_DEG` 14 deg of it. A press flips the slit under the white bar (puff, the all-open cloud).
    `--play-test` now also stands the capsule 0.9 m in front of the button, looks at it, sends a real E key event and
    fails unless exactly that slit opened (`play.json` `press`, a second shot with the hint).
  - Outputs `<raw>/ship/v5/gills-throat/set5/` (pieces in `set5/pieces`, `play/` the views from his positions and
    both portals each way, `play_before_after.png`); handoff `<raw>/ship/v5/notes/ship-step5.md`.
- **Step 6, the lens-room doors, the corner flats, the west gill set and the glow's balance** (2026-10-30):
  - *One frame per lens-room door* (as step 5's hall portals). At each corridor-to-lens-room door a `tip_pilaster` and
    its strip stood on the portal's jamb, the portal's 10 cm band ran 7 cm past the door's chord (TIP_CHORD_H 1.53 against
    the corridor's 1.50) into the next wall facet, and a `cor_arch` with its strips stood 0.38 m beside it. Now: no
    pilaster on the door's vertices (the window band's end pilasters stay), no `cor_arch` anywhere (the pieces
    `cor_arch`, `arch_strip_l`/`_r` and the old `portal_strip_l`/`_r` dropped; the ceiling ribs keep `ARCH_X`'s
    spacing), and `tip_portal` frames its own jambs: `narrow` 3 cm (its opening steps 3 cm inside the corridor's walls,
    its foot on the deck), `rim` TIP_CHORD_H - COR_HALF - 2 mm, so a 5.8 cm band with a 12 mm bevel ends at the facets'
    vertex; its strip `tip_portal_strip_l`/`_r` centred on it (`at_in`/`at_out` -13.5/11.5 mm from the corridor's
    profile).
  - *The corner flats beside the throat's end frames* (`hall_panel_flat_sockf`, the `socket_fe`/`socket_fw` station
    spots): `flat_panel`'s `clad` puts the plain and upper zones in the end frame's metal (`int_silver_c`), the same
    flat faces, so the station spot stays plain (`ship` check green), and a soft warm lamp hangs 0.9 m before each
    (ship.toml `lamps`, "hall" group, 0.9 / range 2.2, 2 m over the deck; 0.35 left it a dark slab); step 7 replaced both: a matte clad and an aimed spot).
  - *The west wall's gill set*: `ship_interior_throat.GILL_SIDES` ("e", "w"): `th_wall_w` is `th_wall_e` mirrored in
    x, every part (slits, groove, bars, button; the groove sweeps round the mouth side, the button at the hall end).
    `ship.gd` puts a `gill_set.gd` on each placed wall (`gill_walls()`), in `--play` (each its own row and button; E
    presses the wall whose button is in reach) and in `--gill-set` (both driven alike). `--play-test` presses each
    wall's button in turn with a real E key event and fails unless that wall's slit under its white bar opened and the
    other wall's row kept its own one open slit (three shots). `ship.gill_view(..., side="w")` mirrors a view; the
    `--gill-set` views add the west wall's (`w_*`), the posed east concept views (`e_concept_*`), the row of all five
    square on (`row_shut`, `row_open`, `w_row_*`) and both walls from the throat's middle (`mouth_both`, `hall_both`);
    `ship.gill_set(..., only=[...])` renders named views only (no demo, no videos).
  - *The glow's balance* (the engineer: slits 1 and 2 "super"; on 3-5 the glowing rim read as a hair line in a big
    unlit lip, 5 the worst): from slit 3 on (`BALANCE_FROM`) each slit has its own section (`profile_of`): the rim
    keeps slit 2's absolute width x (chord 2 / chord) ** `GLOW_K`, the lip gives up the room (lip + rim stay 0.16 of
    the crescent: inner wall, floor and overhang unchanged), the lip's depth scales with its width (its bevel's angle
    kept) and the rim keeps slit 2's 10.5 mm drop, so as it widens it lies flatter and faces the room. A row at
    `GLOW_K` 0 / 0.5 / 1 changed too little (`set6/glow_var/variants_open.png`); the pick 1.6: rim 11.0 / 10.1 / 11.7 /
    13.6 / 16.0 mm, lip 24.2 / 22.1 / 17.6 / 13.1 / 8.0 mm. Seen from the concept camera, slits 4-5 still show their
    dark hall-side wall (the perspective: the bright inner wall faces the hall).
  - Outputs `<raw>/ship/v5/gills-throat/set6/` (pieces in `set6/pieces`, `views/stills`, `doors_before`,
    `doors_after`, `doors_before_after.png`, `sheet.png`, `play_test/`); handoff `<raw>/ship/v5/notes/ship-step6.md`.
- **Step 7, the corner flats lit and the final proof** (2026-10-30; the engineer approved the set on both walls, the
  doors and the portals as of step 6, "Так, доводь"):
  - *The corner flats' clad*: `int_silver_c__clad` (ship_interior.py), the end frame's metal a hair warmer
    (0.42, 0.41, 0.395), metallic 0.2, roughness 0.62, with its own `[light.mats]` row (v 0.9, m 0.2; without it the
    family's `int_silver_c` row, m 0.45, would win through `_entry`). `int_silver_c` itself is unchanged. Step 6's
    omni (0.9, range 2.2, 0.9 m out) lit only the flat's foot; now a soft warm spot per flat, 1.6 m out along its
    normal and 2.6 m over the deck (ship.toml `lamps`, "hall", 2.4, range 3.6, 45 deg, aimed at the flat's middle
    (+-3.4376, -2.3137, 2.6)). The flat's mean in `clad_hall` 36 -> 80 (0..255; the gill wall beside it 88).
    `CLAD_VIEWS` in ship.py (`clad_throat`, `clad_hall`, `w_*`: eye height 1.6 m, from the throat by its hall end and
    2.4 m before the flat; `play003` and `w_play003`: his `--play` shot 003's place and look, fov 75, and its mirror) are among the `--gill-set` views.
  - *The proof's third camera*: `GILL_SET["both"]` ("both", as `mouth_both`: 0.3 m in from the mouth's corners, eye
    1.6 m, looking up the throat) films both rows running the demo, so `--gill-set` writes `concept.mp4`,
    `close.mp4` and `both.mp4`. The sheet stays `GILL_SHEET`: set_plate | east concept mid; west concept mid | both
    walls from the mouth.
  - *As built* (both walls; the west is the east's mirror in x, `GILL_SIDES`; s along the wall from the mouth's
    corner, h over the deck): five crescent cuts 15 cm deep, middles s 2.074 / 2.438 / 2.801 / 3.164 / 3.526, chords
    1.08 / 0.99 / 0.90 / 0.82 / 0.74 m, bottoms 0.827 -> 0.867, leaning back 3 -> 7 deg; the glowing rim 11.0 / 10.1 /
    11.7 / 13.6 / 16.0 mm, the lip 24.2 / 22.1 / 17.6 / 13.1 / 8.0 mm (`GLOW_K` 1.6 from slit 3); a turn bar over each
    slit; the groove round the mouth side; the button at s 3.86, h 1.15; no pillar, the wall runs to the hall's corner
    in `end_frame`; one frame per corridor portal and lens-room door. In `--play` each wall has its own
    `gill_set.gd` and E presses the wall whose button is in reach. Tests: `test_ship_gillset.py` (the mirror, the rim
    and lip widths as built, the clad and its spots, the cameras), `test_ship_throat.py`, `test_ship_gills.py`.
  - Outputs `<raw>/ship/v5/gills-throat/set7/` (pieces in `set7/pieces`: set6's with `hall_panel_flat_sockf`
    rebuilt; `clad_before_after.png` (rows clad_throat, w_clad_throat, clad_hall, w_clad_hall; left step 6, right
    step 7), `gill_set/` (the three MP4s, the stills, `sheet.png`), `play_test/`); handoff
    `<raw>/ship/v5/notes/ship-step7.md`.

## The stern polish n1 (2026-11-01)

The lobby's players see the stern up close from the spawn (`<raw>/lobby/hall/v15/shots/spawn_ship.png`). n1
rebuilds the three nozzle pods and the stern legs, keeping every radius, length and placement
(`tools/blender/ship_hull_detail.py` `nozzle_pod`/`pod_ring`, `ship_hull.py` `_leg_heavy`):

| Part | Now |
|---|---|
| Segments | `POD_SEGS` 64 (was 32), the bell, housing, collar, fairing and spinner shaded smooth under 40 deg |
| Bell | a solid ring with bevelled lips; a continuous light ring 1.6 cm into its lip (the ten gapped lip segments are gone), its plane at length + `LIP` 0.45 (the ring at + 0.434: `hull.pod_tail_m`) |
| Accents | the housing round the bell's base carries a light strip in a groove; the barrel's strip sits between two trim lips |
| Throat | two stepped rings (the first with a light ring), a deep wall, a floor in four emissive bands (`glow_pod_dim/_mid/_warm/_hot`) round a pointed spinner with a hot tip and twelve twisted stator vanes |
| Hull join | a fairing where each pod leaves the hull (args `mount`), six stringers, one collar; the middle pod carries two bolted beams (args `bridges`, `bridge_y`) over its contact with each outer pod, so no collar or fairing crosses another pod in the open |
| Stern legs | `leg_stern` args `heavy = true`: same pad (r 0.6), a thicker 16-sided oleo, two side dampers, a torque link, a hydraulic line, eight ribs and bolt heads |

**Why the bells were black in the lobby:** their throat was the dark `ext_nozzle_inner`; the teal seen in
`ship --shoot` came from `ship.gd`'s run-time glow-cell omni lights (`_dress`: one omni per cell of emissive
surface, `glow_pod` with `l` 0.15). The package keeps those lights under `Lights`, but the lobby zeroes the ship's
lights (`ship_lights`), so the throat went black. The glow now lives in the pieces' own emissive materials, which
ship into the package unchanged; their `[light.mats]` rows carry `l = 0.0` (they light nothing, so the look is the
same with the ship's lights on or off) and `e` scales them in Godot.

Cost: about 12k triangles a pod with its lights (was about 1.6k); the ship 313k.

## Polish n2: the nose, the hall's bays, the underbody (2026-11-01)
A fresh critic's findings on the b4 package (art #263); note `D:/prime-art-raw/ship/v5/notes/polish-n2.md`.
- **The closed nose's glare** was no leak: `test_ship_jaw` casts its seal rays and the closed jaws are shut. `ship.gd`
  `_dress` makes the glow cells' lights in the saved pose (open), so a closed view left the deck tip's cyan light
  (lights.json `(0, 0.48, -12.07)`) 0.5 m over the path in front of the shut nose. `_jaw_bind` keeps a cell lit
  only by one jaw piece in that jaw's frame and `_jaw_turn` moves it with the jaw. In the package,
  `export_scene.gd` reparents each such light under its jaw piece (under `Nose`), so the game's `Nose` clips carry it,
  and strips the binding's metas.
- **The mouth ceiling's bars** are `glow_cyan__jaw_ceil` (half glow_cyan's strength, light `l` 0.3): the clamp's
  2.4 clipped the throat's ceiling white.
- **The hall's flats** (`flat_panel`) and the vault door wall's sides are relief bays (`ship_interior.relief`): a
  silver frame 35 mm proud with corner bolts round three panels 20 mm proud over a dark back, seams 14 mm; the field
  stays flat for a station. The kick plate and belt are kept.
- **The vault door**: a lit frame edge all round the opening and a centred light line down the leaf between four
  panels (`int_cyan__door`, e 0.35, a short light `l` 0.25 on the leaf), a reader with a bezel, a dark screen, a lit
  bar and three keys.
- **The lens rooms' centre disc** is `int_plate__tip` (matte, darker); the hall's disc keeps `int_plate`.
- **The underbody**: `belly_lights`, cyan lines (`glow_cyan__belly`, glow only) in a dark channel 4-10 mm under the
  hull's bottom, along the belly at x +-2.2, spanwise under each corridor and a ring under each lens; a step is left
  out where the bottom rises over 1.5 cm. `metal.gdshader` keeps a third of the brushed grain on faces looking down
  (its 1.3/m streak noise read as long streaks on the belly's big plates).
- **The deck's hazard bands**: a dark band 12 cm wide, 13 cm in from each deck edge, yellow bars slanted every 0.2 m
  (`deck_hazard`, `deck_hazard_dark`, no collision); the ribs stop 0.3 m from the edges.
- **Measured, no change**: the deck's top meets the mouth floor at the hinge at 1.200 m (the floor_h; the deck plane
  through the hinge, ship_hull_jaw.cuts), so the ramp lip does not float; the canopies stand over the roof by design
  (the approved spine bumps) and already have a fairing ring and a rim lip over the glass's foot.
- **Not done**: the oculus at 64 sides doubled the hull plating's capped seam corners (727 against the 600 bound of
  `test_the_seam_corners_end_on_their_fold_and_keep_the_groove`): `sides` is also the hull's cut prism, so the visible
  rings need their own count (a next step).
