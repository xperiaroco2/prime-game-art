# The lobby hall

The lobby's hall (art #356): a 40 x 40 m hall with a bowed window to the night Earth, a ribbed vault, an entrance arch
with a short closed corridor, four sealed doors and art #263's ship standing on a floor ring. Step 1 is the grey massing
with the ship in place, built the way the ship was built (a layout file, a plain-Python check, one GLB per piece from
headless Blender, a Godot import with a capsule walk, off-screen review shots); later steps add the materials, the
window's Earth and the light on top.

## Files

| Path | What |
|---|---|
| `layouts/lobby/hall.toml` | Every number: the hall, the window, the arch, the doors, the floor ring and spawns, the ship's placement and dropped pieces, the hall's pieces and placements, the review views, the walk and the blocks |
| `tools/runner/lobby_layout.py` | Load, the check, the ship's footprint, the text plan (plain Python) |
| `tools/runner/commands/lobby.py` | The `lobby` command |
| `tools/blender/lobby_build.py` | The shell builder, one GLB per piece (headless Blender) |
| `godot/lobby/hall.gd` | The Godot side: import check, walk and blocks (headless); the shots (off-screen window) |
| `tools/tests/test_lobby_layout.py` | Fast tests of the check |

The source: the engineer's approved drawing `D:/prime-game-design/ideas/lobby-station/hall/drawing/drawing.js` (its
`H` object and rows table) and concepts `a_entrance.jpg` (A) and `c_back.jpg` (C) beside it; the ship's placement from
the engineer's decision of 2026-10-30 (art#356 comment 6522500716).

## Coordinates and numbers

The game's frame, `levels/lobby/lobby.tscn` (prime-game): x east, z south, y up, the floor at y 0. `hall.toml` holds
Godot's own coordinates; the Blender builder writes the lobby frame and turns it into Blender's (x, -z, y), so the GLB
holds the lobby frame again.

| What | Number | From |
|---|---|---|
| Hall | the straight walls' inner faces x -20..20, z -30..10 (40 x 40 m) | H.x0, x1, zN, zS |
| Window | the south wall, an arc through (+-20, 10) and (0, 16): radius 36.333 m, centre z -20.333; sill 0.5, transom 3, 6 panes even along the arc's angle (7 mullions) | H.bulge, sill, transom, panes |
| Walls, vault | walls and window 12 m; the vault a segmental arc across the hall (x) from 12 at the walls to 15 at x 0 (radius 68.17 m); ribs at z -24, -18, -12, -6, 0, 6 over the side walls' pilasters, hanging 0.5 m | H.wall, apex, ribs |
| North pilasters | x -18, -6, 6, 18 | drawing.js northWall() |
| Arch | 6 x 6 m in the north wall's middle; the corridor x -3..3, z -38..-30, its end closed by a wall and a sealed door slab | H.arch |
| Doors | 3 x 4.5 m, the red lamp's centre at 5.1 m: D1 west wall z 2, D2 east wall z 2, D3 and D4 north wall x -11 and 11; each a slab 0.15 m inside the wall's inner face | H.door, H.doors |
| Floor | one level, 2 m plates (the plates follow the arc), the ring r 15 round the ship's middle | H.tile, H.ring |
| Spawns | ten at z 0, x -9..9 step 2 | H.spawns |
| Ship | plan origin at (0, 0, -17), nose north: lobby x = plan x, lobby z = plan y - 17, lobby y = plan h; nose z -24.10, the pods' ends z -2.04 (the mid pod), middle z -13.07, half span 13.05 | the engineer, 2026-10-30 |

Numbers not in the drawing, ours (blockout): the pilasters 0.8 x 0.6 m (the drawing's glyph is 1.2 m wide, which puts
the pilaster at z 0 0.1 m into D1 and D2); the walls 0.5 m thick; the door's frame 0.3 m, its slab 0.2 m; the window's
mullions 0.5 m, bars 0.3 m; the arch's frame 0.6 m; the corridor's walls and ceiling 0.3 m; the vault's cross-section
(the drawing's long section draws the vault rising along z "as a polyline"; the ribs run across the hall over the
pilasters, so the vault here is a barrel across x with its crown along the hall).

## The check

`lobby_layout.check`: the hall's box and the arc through its three points; the vault's arc from the walls' top to the
apex; sill < transom < wall; the ribs in order with their pilasters on the side walls; the north pilasters on their
wall and clear of the arch; the arch's size and frame within the wall; each door on the N, W or E wall, at least 1 m
from a corner, 0.1 m clear of every pilaster, the arch's frame and the other doors, its lamp between its head and the
wall's top; every placement names a piece; the spawns and walk points on the floor with the capsule's radius, no walk
point under the ship; the views' eyes inside. The ship: its footprint is the convex hull of the hull's outline
(`ship_hull_shape.outline("P")`), each placed pod's bounds and the tail (the `skin_top` piece's bounds aft of the
outline, as wide as the pods) from art #263's `build_report.json`, moved by the origin; it keeps at least 2 m to every
spawn and 3 m to every wall, the window and every door's opening, and the floor ring reaches no more than 1 m inside
its outline. The text plan goes to `<raw>/<raw_dir>/plan/plan.txt` (`raw_dir` in `hall.toml`: step 1 `lobby/hall/v1`, step 2 `lobby/hall/v2`).

Measured (step 1): the spawns 2.04 m from the ship (the mid pod's end); the ship 6.95 m from the west and east walls,
5.90 m from the north wall, 12.04 m from the window; D1/D2 14.58 m, D3/D4 8.83 m.

## The ship in the lobby

Art #263 owns the ship; the lobby never rebuilds or copies its builders. `lobby` reads `layouts/ship` through
`ship_layout.load()` and places the built pieces from `<raw>/ship/v5/pieces/` (`[ship] pieces_dir`): the exterior lane
only (`lanes`), 40 placements. The interior is left out in step 1 (it shows only through the canopies' glass).

The ship's closed state (ramp up) does not exist yet: the ramp is placed as it is, down, as a stand-in (`stand_in`),
and is not in the footprint.

The forest clearing is dropped (`[ship] drop`): `ground`, the pines `pine_a`..`pine_g` and `pine_s`, the rocks
`rock_a`..`rock_c`, `rock_pile_a`, `rock_pile_b`, `ground_lamp`, `dirt_patch`, `dirt_path`, the tufts `tuft_a`,
`tuft_b`, `tuft_dry`, the bushes `bush_s`, `bush_m`, `bush_l`, the logs `log_a`..`log_c`, `stump`, `party_post`,
`party_lights`, `fern_a`, `fern_b`, `moss_a`, `moss_b`, `litter` (34 pieces). The check refuses a dropped id that is no
ship piece.

## The pieces

`floor` (the slab, the plates, the ring), `walls` (west, east and north with their openings, the pilasters), `vault`
(the shell, the lunettes over the north wall and the window's head, the ribs), `window_frame` (sill, transom, head, 7
mullions), `window_glass`, `arch` (the portal's frame, the corridor, its floor and closed end), `door` (slab, frame, red
lamp; built facing +z, the command places it on its wall: N yaw 0, W 90, E -90). Every piece but the vault collides
(`-col` meshes: trimesh static bodies). Step 1: 7 GLBs, 5860 triangles, glTF-Validator clean.

## Running it

```
tools/run.sh lobby --check                     # the check and the text plan
tools/run.sh lobby --build                     # the GLBs into <raw>/<raw_dir>/pieces with glTF-Validator
tools/run.sh lobby --godot                     # headless import, sizes, colliders, the walk and the blocks
tools/run.sh lobby --shoot <raw>/lobby/hall/v2/shots
tools/run.sh lobby --grid <raw>/lobby/hall/v2/grid    # the metal variants' taste grid
```

`--build`, `--godot` and `--shoot` are heavy runs (Blender, Godot; one at a time): agents start them in the background.

`--godot`: every piece imports at Blender's size (0.01 m), every colliding piece has colliders, the capsule walk (1.36 m wide,
r 0.68, 1.8 m tall: the house walk's) arrives: from the spawns round the ship's east side, over the ramp's foot into the corridor's
end, back out, up to D4 and D3, round the west side to D1, across to D2 (step 1: 22/22 points, 178.1 m in 59.7 s, lowest
0.000 m). The blocks walk into each door and the corridor's end and must stop on the hall's side (step 1: the doors
0.53 m short of the wall's face, the corridor's end 0.80 m short of its wall).

`--shoot DIR`: 1920 x 1080 shots under a neutral review light (a grey ambient, a grey sky used only for reflections,
two directional lights without shadows, SSAO) with the dark blue placeholder behind the window; `a_entrance.png`,
`c_back.png`, `spawn_eye.png`, `top.png` (the vault hidden), `compare_a_entrance.png` and `compare_c_back.png` (the
concept left, the shot right) and `sheet.png` (1280 px).

The cameras, estimated from the concepts: A at eye height, about 80 deg across; its doors D1 and D2 at the frame's
edges put A's camera at about z -23 in the drawn hall, where the moved ship's nose now stands, so A stands at the north
wall's foot west of the ramp (-5, 1.7, -29.3). C from the window's bulge (0, 5, 14) at about 5 m, about 60 deg across.

## Step 2: shell and materials

Step 2 turns the grey massing into the station hall's shell, the look of concepts A and C: no number the layout held
moved (the engineer approved step 1's proportions on 2026-10-30). The raw output is `<raw>/lobby/hall/v2/` (`raw_dir`);
v1 stays as it was.

What each piece carries now (ours, not the drawing's; the bands and sizes are constants at the top of the pieces in
`lobby_build.py`):

- `walls`: the wall behind (`lobby_wall`, the seams' dark) with bevelled plates in front, 7 cm proud, 6 cm gaps, at
  most 2.1 m wide, in rows 0.32-2.35, 2.41-4.6, 4.66-7.1 m under a cornice at 7.2-7.7 m and 7.8-9.85, 9.91-11.5 m above
  it, cut round the doors (their frames and lamps up to 5.6 m) and the arch (its frames and strip up to 7.8 m); a
  chamfered base trim (0.3 m), a crown band at 11.55-12 m; each pilaster a shaft with chamfered front corners, a plinth,
  a capital and a band at the cornice, and one slim vertical orange strip (2.0-4.4 m, emissive, in a dark housing) on
  its face; every third bay a louvred vent in its lowest row, every fourth a small service box with an amber
  indicator; two conduits on brackets at 10.1 and 10.4 m along the side walls.
- `vault`: the shell (`lobby_wall`) with bevelled infill panels (2 m across, two per rib span, hanging 0.1 m), the ribs
  with chamfered lower edges (still hanging `rib_d` 0.5 m) and a spine beam along the crown between them.
- `floor`: 2 m plates with 1.6 cm seams and 1 cm bevels over the dark slab (`lobby_grout`), polished (the variant's
  `floor_roughness`); the ring as an amber line (12 cm, a little emissive) inlaid in a dark 34 cm channel.
- `door`: two leaves with yellow-black hazard stripes at 45 deg, mirrored so they meet in chevrons, two nested
  chamfered frame bands (0.22 and 0.2 m), the red lamp's housing and lens at 5.1 m and an orange strip above it.
- `arch`: the portal's two chamfered bands (0.6 and 0.4 m) with an orange strip over them; down the corridor three
  nested chamfered frames (z -32, -34, -36) with orange strips on their jambs, panelled walls, floor plates, and at the
  end a shut plain door (two leaves with raised ribs, its frames, a red lamp and a strip).
- `window_frame`: the same bars and mullions in the trim and pilaster metals.

Materials are a library of 14 by name: 7 metals (`lobby_panel`, `lobby_pilaster`, `lobby_trim`, `lobby_vault`,
`lobby_rib`, `lobby_floor`, `lobby_wall`) and 7 fixed (`lobby_grout`, `lobby_dark`, `lobby_ring`, `lobby_strip`,
`lobby_lamp`, `lobby_hazard`, `lobby_glass`). Each piece is merged into one object per material (and per collision), so
a piece draws in one call per material. The metals are plain metallic-roughness colours, no textures: the ship's
`metal.gdshader` was not used, its scratches and grime are wrong for a clean hall and its fine seams would fight the
geometry's own.

The wall-and-floor metal is one switch, `[look] variant` in `hall.toml`: each metal's colour is the variant's `base`
(sRGB) times its lightness in `[look] metals`; the builder writes the chosen variant into the GLBs and `hall.gd`
applies it to the hall's metal surfaces (by their glTF material's name) when it shoots. `lobby --grid DIR` shoots the
layout's `[review] grid` views once per variant into `grid.png`, a row each, labelled: V1 dark gunmetal, V2 warm dark
bronze-grey, V3 cool blue-grey (metallic 0.5, roughness 0.42, the floor 0.2). The pieces are built with V1 until the
engineer picks. The review light gained screen-space reflections for the polished floor; real lights are step 4.

Measured (step 2):

| Piece | Triangles | Materials |
|---|---|---|
| floor | 5232 | lobby_floor, lobby_grout, lobby_ring |
| walls | 7764 | lobby_wall, lobby_panel, lobby_pilaster, lobby_trim, lobby_rib, lobby_dark, lobby_strip |
| vault | 6048 | lobby_wall, lobby_vault, lobby_rib |
| window_frame | 912 | lobby_trim, lobby_pilaster |
| window_glass | 68 | lobby_glass |
| arch | 980 | lobby_wall, lobby_trim, lobby_pilaster, lobby_panel, lobby_floor, lobby_grout, lobby_dark, lobby_strip, lobby_lamp |
| door (x4) | 412 | lobby_trim, lobby_pilaster, lobby_dark, lobby_hazard, lobby_lamp, lobby_strip |

21416 triangles in the 7 GLBs (22652 with the four doors placed), glTF-Validator clean. `--godot`: 37 pieces import at
Blender's sizes, 60 colliders; the walk 22/22 points, 178.1 m in 59.7 s; the blocks hold (D1, D2 0.53 m, D3, D4 0.55
m, the corridor's end 0.90 m short of their walls). Shots: 18-201 draw calls, 10-65k primitives (`corner_nw` 201 with
the ship).

The views (`[review] views`): the spawns face the window (+z), so `spawn_eye` looks at the window and `spawn_ship`
toward the ship; `door_d3`, `arch` (from 6 m), `rib`, `floor_ring` are the close-ups.

## Open problems

- The ramp stand-in: down, its foot at z -29.6, 0.4 m from the north wall and in the arch's mouth; the 1.35 m beside it is
  narrower than the 1.36 m capsule, so the walk crosses its foot. The ship's closed state (ramp up) is art #263's to make.
- The spawns are 2.04 m from the engine pods (the rule's 2 m): from a spawn the pods fill the view (`spawn_eye`).
- Concept C drew a two-pod ship; ours has three pods, so C's back view differs there.
- Concept A's camera cannot be matched with the ship 7 m north (see above); A shows the ship's nose close up.
- The pilaster width (0.8 m, not the drawing's 1.2 m glyph) and the vault's cross-section are our readings of the
  drawing.
- No Earth and no light design yet (later steps); the review light is not the game's, and the vault reads dark under it.
- D1's and D2's frames: the pilasters at z 0 stand 0.1 m from their openings, so the frames' north jambs run into
  those pilasters (the pilasters cover them).
- Above each door, between its strip (5.6 m) and the cornice (7.2 m), the wall is bare (the concepts show it so).
