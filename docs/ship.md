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
| Footprint | 27.5 x 14.3 m (the lens tips' blades at x +-13.75, `span_max_m` 27.5; ramp foot -7.4 to nozzle tips 6.9 y) | 5a: about 26 x 14; manager update 2: the span up to about 27.5 |
| Deck | floor at h 0.6 on landing legs (launch 3; was 1.0), slabs 0.25, walls 0.2 | the ramp meets the ground; a thinner hull |
| Hall | circle r 3.4 at (0, 0); 3.2 m to the ceiling's rim, 3.8 m to its apex (faceted, 16 sides; launch 3, was 3.4 / 4.0) | console (0, 1) with room round it |
| Mouth | x -1.3..1.3, y -4.6..-3.3, 2.4 m high | the only way in or out (5a's side hatch is dropped, see below) |
| Ramp | 2.6 m wide, hinge (0, -4.6) at the deck, foot (0, -7.4) on the ground: 12.1 deg, a long plane | north at the centre |
| Corridors | y -1.25..1.25 (2.5 m), x 3.3..9.1 each side, 2.4 m high (walls vertical to 1.45, then chamfered) | 5a: about 2.5 m wide |
| Tip rooms | circles r 2.05 at (+-10.75, 0); 2.5 m to the rim, 2.8 m apex (launch 3, was 2.8 / 3.2); window +-65 deg outward, sill 1.0 (join 3, was 0.45), head 2.2 over the deck | panel (-10.5, 0), renewer (12, 0); the lens's window band starts 1.33 m over the deck |
| Stations (not built) | console (0, 1); vents (+-5, -1), sockets (+-8, -1) at the north corridor wall; panel (-10.5, 0); renewer (12, 0) | 5a |
| Player | capsule r 0.4, 1.8 m; every room keeps 0.5 m above it | the game's capsule |

The check holds: the footprint within 0.5 m; corridors 2.5 +- 0.1 m wide and over 4 m long; the tip rooms spanning
the width; clear heights over the capsule and margin; exactly one room with an exit, the ramp's hinge on its north
edge, the ramp as wide as the mouth and under 30 deg; no window is an exit; every room reachable from the hall and
linked rooms meeting; each station spot inside its room by its footprint (0.35 m; a wall unit 0.5 m deep stands
against its wall, within 0.6 m), 1.2 m free beside the corridor stations; every room's outer wall and every placed
piece inside the hull outline (the ramp may stand outside); no piece defined twice or never placed.

**One entrance; the side hatch is dropped.** estate-map 5a lists a side hatch at (-12.5, 1) as a second way out. The
engineer's step-1 rule (art#263: the mouth ramp is the only way in or out, no side hatch, no doors) wins over that text:
ship.toml has no hatch, and `check` and `test_a_second_exit_is_refused` demand exactly one exit. If the hatch comes
back, both change with it. The corridors also run straight (5a: "curve with the wing"): numbers, not curvature.

**Wall stations and the corridor's slant.** The check places a vent or socket in plan only; the corridor wall is
vertical to 1.45 m and then slants in (half width 0.9 m at the ceiling), so a station taller than about 1.5 m at
u 1.0 meets the slant. The console at (0, 1) straddles the hall's plain disc (r 1.0) and its first grate ring (r 1.1).
Step 2 accounts for both.

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
- tip rooms: polygon on radius 2.1, eight window segments over +-65 deg (sill 1.0, head 2.2 since launch 3), three wall facets a
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
tools/run.sh ship --godot --walk DIR    # headless: sizes, colliders, the capsule walk into DIR/check.json, then DIR/walkthrough.mp4
tools/run.sh ship --shoot DIR           # off-screen night shots, compare_top.png (plan-3 left), sheet.png
```

Runs over 180 s go to the background with their log (CLAUDE.md, "Shell"). The whole after launch 2's join
(2026-10-22): 139 pieces, 1094 placements (the clearing's 162 pines, 26 bushes, 6 logs, 5 stumps, 160 tufts and 8
party-light posts among them), 59310 triangles per piece set, glTF-Validator clean; extent 26.46 x 13.9 m;
`--godot`: Godot sizes equal Blender's, 105 colliders, the capsule walk reaches all 14 points (18.8 s);
`--walk`: the 1280x720 walk-through, 89.5 s, 2149 frames, 12.8 MB (rendered in 313 s); `--shoot`: 14 views and
their compare sheets, 415..620 draw calls inside the tip rooms, 1740..2032 outside. Times: `--build` about 2 min,
`--godot --walk DIR --shoot DIR` about 10 min.

## The exterior (EXTERIOR lane)

`tools/blender/ship_hull.py`, `ship_hull_skin.py` and `ship_hull_detail.py` build the outside as a kit, each piece
its own GLB (`layouts/ship/exterior.toml`): the skin (body, three wing sections and the tip fairing per side, each with
a darker underside), the cyan wing stripes, lead blades and seam lines, the inset hatches with their scratches, the
tip windows' frames, the cockpit canopies (fairing, tinted glass, warm glow; outside only, the hall's ceiling closes
them off), the mouth frame and its amber lights, the ramp and its edge strips, three long nozzle pods with their cyan
rings and the middle pod's housing, six landing legs and twelve amber ground lamps; the clearing's ground, pines
and rocks. Every skin face is cut into plates of about 1.5 m, each with a 2.2 cm chamfer sinking 1.4 cm into a dark
seam (real bevels, not a texture).

### The hull skin (hull lane; launch 3: the lower deck and the lens tips)

One continuous faceted surface from the centre to the tips (`ship_hull_skin.py`). The half-span is lofted through
sections across x, each the same loop of 14 (y, h) points (lead edge, two upper-front slope points, the eave, two ridge
points, the rear eave, two upper-rear points, trail edge, lower rear, two belly points, lower front), so the facets run
as long creases from the body to the tips; past the tip room's centre (x 10.75) the tip fairing is a lens revolved
round the room's centre whose +-90 deg profiles equal the loft's last section. The heights come from ship.toml (the
skin and `ship_interior.py` read `[deck]` and the rooms). `clearance()` lists room points outside a section (the hall's
wall top and dome, the corridors' chamfered top corners and slab, the tip room's wall top and crown) and `steep()` the
outside faces within 25 deg of vertical (manager update 2: none); the fast tests keep both empty.

The silhouette grid (`tools/blender/ship_hull_grid.py`, headless Workbench with the rooms as an orange ghost): the
variants in front, side, top and three-quarter views under the approved 2D and the Meshy silhouette reference (batch
`2026-10-22-ship-hull-ref`, 20 credits, a multi-image-to-3D of turnaround.jpg's four views, scaled to the 27.5 m span;
never shipped). Launch 3's grid: `<raw>/ship/v1/grid/hull31/grid.png` (rows 2D, ref, G, H, I, J); J is placed: the
most swept tips (the turnaround top's) and the spine standing clearest over the wings from the front. The front of
every variant is still a flat wide plate with the lens ends: the tip rooms (0.3 to 3.65 m) set the tips' depth.

| What | Number (plan m), variant J | Why |
|---|---|---|
| Lead edge | (1.5, -6.5) -> (4.0, -5.4) -> (8.0, -3.9) -> (10.75, -3.0); blade h 0.9 -> 0.95 at x 4 -> 1.2 at x 8 -> 1.6 | low at the body, rising to the tips |
| Trail edge | (0, 5.0) -> (3.0, 5.2) -> (8.0, 5.4) -> (10.75, 5.4); the stern's edge h 2.2 under the housing | the blades behind the corridors |
| Crest | spine h 4.9 over the hall's middle (x < 0.9), 4.3 at the hall's rim (x 3.72), 3.75 at x 5.5, 3.62 at the tip | falls from the spine to the tips |
| Eave | the hall's r 3.84 at h 4.1; the wing's 0.15 m outside the corridor walls (y 1.6) at max(3.08, crest - 0.45) | the rooms inside |
| Belly | h 0.3 under every room (the slabs' bottoms 0.35), the lower facets rising to the blade | the belly rises toward the edges |
| Lens tip | blade r 3.0 at h 1.7 in the window's direction (1.6 at +-90 deg), lower and upper faces 25 deg off vertical to (2.39, 0.45) and the eave (2.24, 3.2), crown (1.0, 3.62) to 3.65 | a sharp blade 0.7 m past the room's wall at about its mid-height; span 27.5 |
| Swept tip | round the tip centre (dx, dy): (2.25, -2.05), (2.9, -0.9), (3.0, 0), (2.95, 1.0), (2.75, 3.0), (1.8, 6.4) | the turnaround top's swept tips |
| Window | the band from 15 % to 85 % of the upper face (h 1.93..2.98) within 65 deg of the tip's axis left open | a slanted band; the inside's glass stands behind it |
| Mouth | the opening (h 0.55..3.15 at y -4.6) under a brow 1.0 m forward at h 3.45, the brow's top leaning back to (−4.2, 4.3) | a notch cut into the low ray nose |
| Footprint | 27.5 x 14.3 m (`ship --check`); ship.toml [hull] rows from `ship_hull_skin.outline()` | span_max_m 27.5 |

**Winding.** Plan coordinates are left-handed (x east, y south, h up); the harness's (x, -y, h) mirrors them, which
flips every winding set in plan coordinates with `ship_lib.orient`. `ship_hull.py` reverses its open (`solid=False`)
parts once at the end (`_outward`); a lane that orients open parts must do the same, or they come out inside-out
(Blender exports double-sided materials, so they still show, lit from the wrong side).

**The night look** (`godot/ship/ship.gd`): a star sky with a moon (`night_sky.gdshader`), moonlight (ship.toml
`[light]`) with a cool shadowed key from the north-west (`key_dir_deg` [-38, -140], `key_energy` 0.55, hull 3-2: the silver catches light from the hero, front and side cameras), one shared triplanar metal shader by glTF material name (`metal.gdshader`: grain, fine seams, scratches,
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
| Canopies | flush in the forward hull (hull 3-2): faceted glass ellipse 1.15 x 1.5 at (+-2.3, -2.75), 14 sides, 3 rings, 0.85 high, its base on the skin (`skin_h` + 0.02); four frame ribs; a low teardrop plate 1.14x round it (0.03 over the skin); a lit floor, a seat and a desk under the glass (tops below 0.62) |
| Nozzle pods | outer r 1.05 at (+-2.75, h 2.15) from y 3.5, 3.6 long; middle r 1.2 at h 2.45 from y 3.9, 4.0 long (0.8 longer, 0.3 higher); a 12-sided panelled barrel with two raised rib rings and six stringers (tube relief), a collar, the bell; per pod ten cyan segments, a cyan end ring 0.99 r (proud of the bell) and a second band 1.04 r 0.8 m ahead (`pod_ring`) |
| Pod housing | from y 3.7 (top 4.75, the hall's eave) to 6.4 (top 3.9), half-width 1.55, sides into the skin or onto the pod's axis |
| Lead blades | 0.24 x 0.12 cyan bars (hull 3-2; 0.13 x 0.07 read thin) on the lead edge (section point 0) from x 2.0 to the swept tip point |
| Seam lines | 0.025 cyan bars on the front eave crease from x 4 to 9 and the rear eave from x 5 to 8 |
| Hatches | six per side, a bevelled frame round a recessed plate; a latch at the outer end (a dark well, a chrome lever on two posts) and a hinge rod along the inner edge (the two slots read as a face); 40 seeded scratches per side (ext_chrome, 0.18..0.68 m) |
| Legs | six (hull 3-2): `leg_front` at (+-5.0, -3.6), `leg_rear` at (+-6.5, 3.6), `leg_stern` at (+-1.8, 4.2), each mounted 0.12 into the skin's underside (top 0.74 / 0.75 / 1.21), feet out past the edges (reach 2.0 / 2.2 / 1.6); struts r 0.17 / 0.14, knee drum r 0.22, twin pistons, a foot plate r 0.5 with three toes. The 0.6 deck keeps them short |
| Mouth portal | a chamfered frame from the inside's opening (half width 1.25, the mouth's clear_h, 0.3 x 0.35 chamfers) out to half width 1.62 and clear_h + 0.4, 0.3 deep, over the skin's hole; a chrome lip; amber strips on the jambs and the head |
| Tip windows | `tip_window`: tinted glass on the lens's slanted band (profile points 4..5, h 1.93..2.98) within the window's half angle, sill and head bars along it, two jambs and three mullions up the slope (replaces the vertical ring) |
| Stripes | twelve chunky cyan bars per wing from x 2.6 to 10.2, each wrapping the lead edge: down the lower facet (8..92 %) and a third of the way up the upper slope |
| Ramp light | a continuous amber strip inside each rail and a cross strip at the foot |
| Ground lamps | r 0.2 amber pucks 0.9 m out past each of the six legs' feet along the leg ((+-6.08, -6.29), (+-7.65, 6.48), (+-2.29, 6.65); hull 3-3) and at (+-1.75, -5.9 / -7.25) by the ramp |

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
  and the glass 1.5 cm inside the band (`tip_glass_e`/`_w`). Before, the glass stood upright in the wall and its
  lower half showed the lens's lower face and its cyan blade. Eye height (1.65 m over the deck) looks through the
  band (the test keeps lower edge < 2.25 < upper edge).
- **One per side**: the well is sampled at the hull's own angles (10 deg steps, the swept tip's outline points) plus
  the room's window vertices, from the placed variant (`DEFAULT`), so it meets the band's hole edge exactly; the
  lens is not symmetric (toward the swept tip's rear the blade reaches r 5.3, the band's lower edge r 4.85), so the
  west room (turned 180) reads the profile at the mirrored angle. A change to the skin moves the well with it on the
  next `--build --only tip_well_e,tip_well_w,tip_glass_e,tip_glass_w`.
- **The views**: `in_hall_out` from y 1.0 at fov 60 (the mouth fills the frame, hall_out-2), the tip views level at
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
- The tip windows: the hull's `tip_window` glass and the well's `tip_glass_e`/`_w` 1.5 cm apart (double tint from
  inside); the clearing through the band is dim. The party string is not in the hall-out view.
- The detail_seam close-up's hatches read as faces (dot pairs); the legs are small and hidden from the front.
