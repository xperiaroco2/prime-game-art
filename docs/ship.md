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
| `tools/tests/test_ship_*.py` | fast: `test_ship_layout.py`, `test_ship_interior.py`, `test_ship_hull_skin.py`, `test_ship_hull_detail.py`, `test_ship_exterior.py`, `test_ship_clearing.py`; heavy (Blender): `test_ship_build.py` | either lane adds its own file |

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
| Footprint | 27.5 m wide (the lens tips' blades at x +-13.75, `span_max_m` 27.5); two lengths (`ship_layout.lengths()`, as built): the hull body 12.9 m (lead edge y -6.5 to the trail 6.4: the swept tips and the pod housing; no ramp, no nozzle pods), 14.8 m with the nozzle pods (lead edge to the nozzle tips at 8.34), the one `ship --check` holds to 14, up to `length_max_m` 15; overall 15.7 m from the ramp's foot (-7.4) to the nozzle tips | 5a: about 26 x 14; manager update 2: the span up to about 27.5; the manager (art #263): the length counts the nozzles, up to 15 m, as how far they stick out is open (2D README) |
| Deck | floor at h 0.6 on landing legs (launch 3; was 1.0), slabs 0.25, walls 0.2 | the ramp meets the ground; a thinner hull |
| Hall | circle r 4.0 at (0, 0) (v2; v1 3.4); 3.2 m to the ceiling's rim, 3.8 m to its apex (faceted, 16 sides, the four diagonal pairs of facets made one flat chord each for the vents and sockets) | 5a mirrored: round, 8 m across |
| Mouth | x -1.3..1.3, y -4.6..-3.9 (v2), 2.4 m high | the only way in or out (5a's side hatch is dropped, see below) |
| Ramp | 2.6 m wide, hinge (0, -4.6) at the deck, foot (0, -7.4) on the ground: 12.1 deg, a long plane | north at the centre |
| Corridors | y -1.5..1.5 (3 m, v2), x 3.7..7.3 each side (the hall's and the tip room's circles at y +-1.5), straight, 2.4 m high (walls vertical to 1.45, then chamfered) | 5a mirrored: straight, about 3 m wide |
| Tip rooms | circles r 1.8 at (+-8.3, 0), the outer wall at +-10.1 (v2; v1 r 2.05 at +-10.75); 2.5 m to the rim, 2.8 m apex; window +-65 deg outward, sill 1.0, head 2.2 over the deck | 5a mirrored: 3.6 m across |
| Stations (not built) | console (0, 1) clear floor; vents at (+-2.66, -2.66) and sockets at (+-2.66, 2.66) on the hall's flat chords; breaker boards at (+-5.25, -1.5) on the corridors' front wall; renewers before the tip windows (wall +-10.1, 0.9 m deep: the player at (+-8.8, 0)) | 5a mirrored, "Version 2" below |
| Player | capsule r 0.4, 1.8 m; every room keeps 0.5 m above it | the game's capsule |

The check holds: the footprint within 0.5 m; corridors `corridor_width_m` (3) +- 0.1 m wide and over 2.5 m long; the
tip rooms' outer wall at `tip_outer_m` (10.1) +- 0.05; the station spots (`check_spots`, "Version 2" below); clear heights over the capsule and margin; exactly one room with an exit, the ramp's hinge on its north
edge, the ramp as wide as the mouth and under 30 deg; no window is an exit; every room reachable from the hall and
linked rooms meeting; every room's outer wall and every placed
piece inside the hull outline (the ramp may stand outside); no piece defined twice or never placed.

**One entrance; the side hatch is dropped.** estate-map 5a lists a side hatch at (-12.5, 1) as a second way out. The
engineer's step-1 rule (art#263: the mouth ramp is the only way in or out, no side hatch, no doors) wins over that text:
ship.toml has no hatch, and `check` and `test_a_second_exit_is_refused` demand exactly one exit. If the hatch comes
back, both change with it. The corridors also run straight (5a: "curve with the wing"): numbers, not curvature.

**Wall stations and the corridor's slant.** The check places a breaker board in plan only; the corridor wall is
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
use absolute heights (deck at ship.toml `floor_h`, 0.6), so a placement's h is an offset (the clips' heights); a piece built at plan
angle 0 (its room toward -x) standing at angle a gets yaw -a; in a tip room turned by r, yaw r - a.

The numbers (step 1, art #263):
- hall: 16 facets, inner faces at apothem 3.4 (vertices at 3.467), rim 3.2 m, apex 3.8 m (ship.toml `clear_h`, `apex_h`); the three openings
  (corridors east and west, the mouth north) are two facets wide, framed by a portal on their chord (x 3.203, half
  width 1.327) 0.15 m deep; floor: plain disc r 1.0, eight radial grate sectors r 1.1 to 2.5 between wedge spokes,
  the amber ring at r 2.58, solid plates to the walls; ceiling: 16 facet panels, ribs with cyan strips, the lamp
  ring (eight lamps) at r 1.25.
- corridors: one profile, 2.5 m wide, vertical to 1.45 m (cable channel 1.1 to 1.45 m), slanted in to 1.8 m wide at
  the 2.4 m ceiling (`clear_h`); five modules of 1.117 m from x 3.353 (hall portal) to 8.936 (tip portal); arches at the first
  three module joints only, none near the vent and socket spots (x 5 and 8). The mouth passage is one module of
  1.247 m with an arch at the ramp hinge.
- tip rooms: polygon on radius 2.1, eight window segments over +-65 deg (sill 1.0, head 2.2 since launch 3), three wall facets a
  side, the corridor chord over +-37.6 deg (half width 1.281); rim 2.5 m, apex 2.8 m; radial grate floor with amber
  spokes; ribbed ceiling with cyan strips and a six-lamp ring.
- details: three crushed cup models (five placed, off every station spot), two scratch decal clusters (geometry
  0.6 mm proud of flat panel faces, eight placed).

Materials `int_*` (the library in `ship_interior.py` sets metallic 0.7 to 0.8; at night ship.toml `[light.mats]`
overrides them in Godot: the silvers 0.45 so the lamps light them, the plate 0.3, the grate 0.6): two silver
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
tools/run.sh ship --shoot DIR --shutters closed   # the same with the tip windows' shutters closed (default open)
```

Runs over 180 s go to the background with their log (CLAUDE.md, "Shell"). A snapshot of the whole after launch
2's join (2026-10-22; superseded: `ship --check` prints the current pieces and placements, 157 and 1226 at aa561f1): 139 pieces, 1094 placements (the clearing's 162 pines, 26 bushes, 6 logs, 5 stumps, 160 tufts and 8
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
| Footprint | 27.5 m wide; hull body 12.9 m long, 15.7 m from the ramp's foot to the nozzle tips (`ship --check` prints both); ship.toml [hull] rows from `ship_hull_skin.outline()`, `trail_y` and `pod_tail_m` held to the builders by `test_ship_hull_detail.py` | span_max_m 27.5, length_max_m 15 (with the nozzles) |

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

### The smooth skin (v2 hull lane, step 1)

`tools/blender/ship_hull_smooth.py` replaces the faceted, plated skin outside (the engineer after the night build:
smooth like a ray, no plate grid, no seams, no scratches). The skin is four large pieces, shaded smooth
(`smooth: True` on a part, honoured by `ship_build.make`): `skin_top` (silver; the tip windows' bands open),
`skin_belly` (the darker underside; open under the nose's recess), `skin_brow` (the nose's underside over the mouth)
and `skin_mouth` (the recess's back wall with the opening and its two side walls). The top and the belly are height
fields over one plan outline and meet at its blade edge: the wing (a camber from the lead edge's height to the trail
edge's, plus and minus a half-thickness times a rounded chord profile) smooth-maxed with the rooms (the hall's dome and
the spine, the corridors' round tube, the tip rooms' pods with a steep outer face in the window's sector, the nose over
the mouth, the belly under every slab), the rooms fading to the camber within 0.9 m of the outline. The mesh: x
stations across the body, a polar patch round each tip room's centre (rays every 5 deg; the window's band is the
rings from the head to the sill within its 65 deg), 16.7k triangles in all.

The grid (`ship_hull_smooth_grid.py`, `--solid` for the opaque shading; `<raw>/ship/v2/grid/smooth2/grid.png`,
variants K, L, M, N under turnaround's views): L is placed, the highest curl (the tips at h 4.0) and the most swept
tips, the closest to turnaround's front V and top. Its nose was cut from -8.4 to -6.15: the 14 +- 0.5 m length with
the nozzles (`ship --check`; the nozzle tips sit at y 8.33). ship.toml `[hull]` rows come from `outline_rows()`
(`test_ship_hull_smooth.py`).

| What | Number (plan m), variant L |
|---|---|
| Lead edge | (0, -6.15) nose point -> (4, -5.15) -> (8.3, -3.75) -> (11, -1.5) -> tip (13.75, 1.8) |
| Trail edge | (0, 5.8) -> (3.2, 5.1) -> (8.3, 4.3) -> (11, 3.4) -> tip (13.75, 2.2) |
| Edge height (the curl) | 0.95 at the body, 1.2 at x 8.3, 1.55 at 10.1, 2.45 at 12, 4.0 at the tip; the stern's trail +1.4 |
| Outer wing | 1.44 m thick at x 11.5, 0.51 at 12.5, 0 at the tip |
| Pods | shoulder 3.3 at r 1.95 round (+-8.3, 0), crown 3.6; window band r 2.39..2.73 (h 2.85..1.55) |
| Nose / mouth | the brow's edge h 3.45 over \|x\| < 1.62, back on the wing's line by 2.6; its underside >= 3.27 over the mouth |
| Spine | 5.11 over the hall's middle |

The old `ship_hull_skin.py` stays only for the inside's `tip_well` (`tip_profile`); no placed piece uses its builders.

### The details on the smooth skin (v2 hull lane, step 2)

`ship_hull_detail.py` reads the smooth skin: `skin_h(x, y)` is `ship_hull_smooth.heights(x, y, L)[0]` inside the
outline, so every detail follows the skin if its variant changes. The engineer after the night build: smooth like a
ray, no panel tiles, seam grid, scratches or hatches. So the hatches, seam lines and scratches are gone (pieces and
builders), and nothing outside is plated any more (`ship_hull._skin` is no longer called by a placed piece): the
canopy fairings, pod shells and the housing are single smooth-shaded parts, the mouth portal one `ext_frame` part.
The hull silvers keep their names (`hull_silver`, `ext_silver_b`, `ext_silver_c`); the metal shader's seams and
scratches for them are set in `godot/ship/ship.gd` METALS (the inside lane's file). `ship_hull_look.py` (below) is
the shape check: `D:/prime-art-raw/ship/v2/look_hull2/look.png`.

| Detail | v2 numbers (plan metres) |
|---|---|
| Canopies | as v1's position (+-2.3, -2.75), 1.15 x 1.5, 0.85 high, base `skin_h` + 0.02; now 28 sides x 5 rings, smooth glass; a smooth collar (`ext_silver_b`) and the dark rim lip |
| Nozzle pods | as placed (outer r 1.05 x 3.25 from y 3.85, middle r 1.2 x 3.65 from y 4.25); smooth 32-sided shell with a round nose (1.5 m), one dark collar, the bell; `pod_ring` unchanged but 32-sided |
| Pod housing | smooth, 13 rows x 9 columns, from y 4.25 (out of the hall's r 4.2; its front rises out of the skin) to 6.4, half-width 1.55, top 4.75 -> 3.9 |
| Lead blades | 0.24 x 0.12 cyan bars along `lead(x)` at the edge's height `edge_h(x)[0]`, 0.02 forward, from x 2.7 to 13.6 (the curled tip) |
| Stripes | `smooth_stripes`: 12 bars per wing from x 3.0 to 10.4, 0.3 wide, slanted 0.42 m across, each wrapping the lead edge from 0.25 m under (belly) to 0.6 m over (top), 0.035 proud |
| Tip windows | `smooth_window`: glass on the skin's open band (rings `pod_r(HEAD + 0.05)` 2.40 .. `pod_r(SILL - 0.05)` 2.74 round (+-8.3, 0), +-65 deg), head and sill bars, two jambs and three mullions 0.03 m proud |
| Legs | as placed; the mount box reaches 0.42 over `top` into the skin; top 0.6 / 0.72 / 0.6 (the smooth belly under each mount: 0.50..0.76 / 0.62..0.88 / 0.30..1.00) |

### The hull's details (v1, hull lane step 2)

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
