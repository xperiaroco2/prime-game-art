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
| `godot/ship/` | `ship.gd`: assembly, headless check and walk, night shots | EXTERIOR lane |
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

## Running it

```
tools/run.sh ship                       # the check and plan.txt
tools/run.sh ship --build               # one GLB per piece (about 1 min); --only ids
tools/run.sh ship --godot --walk DIR    # headless: sizes, colliders, the capsule walk into DIR/walk.json
tools/run.sh ship --shoot DIR           # off-screen night shots, compare_top.png (plan-3 left), sheet.png
```

Runs over 180 s go to the background with their log (CLAUDE.md, "Shell"). Step 1's greybox (2026-10-22): 21 pieces,
40 placements, 4004 triangles, glTF-Validator clean; Godot sizes equal Blender's, 16 colliders; the walk reaches all
14 points in 18.8 s.
