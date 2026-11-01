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
| `godot/lobby/hall.gd` | The Godot side: import check, walk and blocks (headless); the shots, the light rig (step 4) and the walk-through's frames (off-screen window) |
| `tools/tests/test_lobby_layout.py` | Fast tests of the check |
| `tools/blender/lobby_earth_tex.py` | Step 3b: NASA's Earth maps scaled to game textures (headless Blender) |
| `godot/lobby/earth_sky.gdshader` | Step 3b: the night Earth, its atmosphere rim and the stars as a sky shader (the game's file) |
| `godot/lobby/earth_object.gdshader` | Step 4c: the Earth as an object, a sphere at a finite distance traced per pixel on a back-faced shell (the game's file) |
| `godot/lobby/window_glass.gdshader` | Step 3b: the window's glass, a faint tint and a grazing reflection (the game's file) |
| `tools/runner/lobby_export.py`, `tools/runner/commands/_lobby_export.py` | Step 5b: the package's writer (plain Python) and its Godot parts (`lobby --export`) |
| `godot/lobby/export_scene.gd`, `godot/lobby/export_check.gd` | Step 5b: the scene saved for the game; the package's check, run in the export folder |
| `assets/environment/lobby/` | Step 5b: the package's `manifest.toml`, `package.json`, `report.json` and `HANDOFF.md` (the binaries stay in the raw folder until approved) |
| `sources/nasa_earth_lobby.toml` | Step 3b: the Earth's source record (`NASA-PD`, credit "Earth imagery: NASA") |

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
| Spawns | ten at z 0, x -9..9 step 2 (since step 5a z 2.5) | H.spawns |
| Ship | step 1: plan origin at (0, 0, -17), nose north: lobby x = plan x, lobby z = plan y - 17, lobby y = plan h; nose z -24.10, the pods' ends z -2.04 (the mid pod), middle z -13.07, half span 13.05. Since step 5a: origin z -14.5, the closed nose z -26.99 (`hall.toml` holds the truth) | the engineer, 2026-10-30 |

Numbers not in the drawing, ours (blockout): the pilasters 0.8 x 0.6 m (the drawing's glyph is 1.2 m wide, which puts
the pilaster at z 0 0.1 m into D1 and D2); the walls 0.5 m thick; the door's frame 0.3 m, its slab 0.2 m; the window's
mullions 0.5 m (0.4 m since step 2b), bars 0.3 m; the arch's frame 0.6 m; the corridor's walls and ceiling 0.3 m; the vault's cross-section
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
its outline. The text plan goes to `<raw>/<raw_dir>/plan/plan.txt` (`raw_dir` in `hall.toml`: step 1 `lobby/hall/v1`, step 2 `lobby/hall/v2`, step 2b `lobby/hall/v3`, step 2c `lobby/hall/v4`, step 3 `lobby/hall/v5`, step 4 `lobby/hall/v6`, step 4c `lobby/hall/v7`).

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
tools/run.sh lobby --shoot <raw>/lobby/hall/v4/shots    # also closeups.png (step 2c)
tools/run.sh lobby --grid <raw>/lobby/hall/v4/grid    # the colour schemes' taste grid
tools/run.sh lobby --earth-tex                 # step 3b: NASA's maps -> <raw>/<[earth] tex_dir>, 4096 x 2048 JPEGs; 5a4: + the caps
tools/run.sh lobby --earth-grid <raw>/lobby/hall/v5/grid    # step 3b: the Earth variants E1-E3
tools/run.sh lobby --light-grid <raw>/lobby/hall/v6/grid    # step 4: the light moods L1-L3
tools/run.sh lobby --video <raw>/lobby/hall/v6/walk         # step 4: the eye-height walk-through MP4
tools/run.sh lobby --distance-grid <raw>/lobby/hall/v7/dgrid    # step 4c: the Earth's distances from three positions
tools/run.sh lobby --earth-video <raw>/lobby/hall/v7/earth-video  # step 4c: one 15 s MP4 per distance
tools/run.sh lobby --ship-grid <raw>/lobby/hall/v9/sgrid           # step 5a2: the ship's light sets K1-K3
tools/run.sh lobby --snow-grid <raw>/lobby/hall/v13/snow-grid      # step 5a6: the snow strengths N1-N3
tools/run.sh lobby --earth-video <raw>/lobby/hall/v13/earth-video --distance D2   # step 5a6: one distance only
tools/run.sh lobby --earth-route <raw>/lobby/hall/v14/earth-route --no-video   # step 5a7: the route's stills sheet
tools/run.sh lobby --earth-route <raw>/lobby/hall/v14/route-F48 --distance F48 # step 5a7: one distance's walk MP4
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

Step 2's look (replaced by step 2b's schemes, below): the wall-and-floor metal was one switch, `[look] variant`: each metal's colour is the variant's `base`
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

## Step 2b: relief and colour schemes

The engineer on step 2 (2026-10-30): the hall looked "monotone, a bit soulless"; of the three metals he liked V3 (cool
blue-grey) best and wanted more colours to try. Step 2b removes the monotony with real relief and makes the look a
scheme. No number of the layout moved except the window's mullions (0.5 to 0.4 m, ours). The raw output is
`<raw>/lobby/hall/v3/` (v1 and v2 stay).

The relief (`lobby_build.py`, its constants at the top of the pieces):

- `walls`: each panel in two or three depths, chosen per panel by a steady hash (`pick`): a raised inner plate, a frame
  round a recessed centre (`lobby_inset`), plain with two bolt rows, or plain with two raised ribs; each panel in one of
  three tones (`lobby_panel`, `lobby_panel2`, `lobby_panel3`: lightness 1.0, 0.9, 1.1, roughness 0.46, 0.62, 0.54). A
  vertical conduit on brackets beside every other pilaster (floor to the cornice, cornice to the frieze). The frieze: a
  recessed channel at 9.7-10.85 m with two lips, two conduits and blocks about twice the old brackets (0.18 x 0.95 m) at
  varied spacing (1.1, 1.9, 1.4, 2.5, 1.2, 2.1 m, cycled). Each pilaster carries a bolted face plate (4.8-6.9 m) and a
  plate above the cornice. Beside D1 and D2 the pilaster at z 0 steps back from the door's frame below the cornice (it
  hid the frame's jamb); its position did not move.
- `door`: three nested stepped frame bands (0.16, 0.14, 0.12 m; fronts 0.26, 0.17, 0.08 m), the leaves recessed (0.27 m
  behind the wall's face), a lintel box (0.86 m tall, 0.3 m deep) carrying the red lamp at 5.1 m and the strip, and over
  it a panel with a grille up to the panels' top row (7.1 m): the wall above a door is no longer bare.
- `arch`: three stepped bands (0.4, 0.33, 0.27 m; fronts 0.42, 0.28, 0.14 m), a lintel box at 7.0-7.78 m (across the
  cornice's ends) with the strip and a bolt row; the corridor's ceiling ribs midway between its frames (a 1 m rhythm), a
  light strip along its ceiling, and the shut door at its end hazard-striped like the hall's.
- `vault`: the ribs thicker (a 1.24 m flange over the panels' ends and the chamfered 0.8 m body, still hanging `rib_d`),
  lighter panels (`lobby_vault`, lightness 1.12) in two depths, dark battens over every seam (the white hairlines were
  the panels' bevel sides catching the sky at grazing angles), the shell behind matte and dark (`lobby_grout`), the
  lunettes in `lobby_vault`; nine pendant lamp housings (dome shades on rods, 3 x 3 at x -10, 0, 10 and z -21, -9, 3,
  the shade's bottom at 9.6 m) with a lens (`lobby_lens`, not emissive: the lights are step 4's).
- Light strips (pilasters, doors, arch, corridor): each seated in a dark channel with lips, only the strip's front face
  emissive (no side or back faces: the reddish smears beside the corridor's strips are gone), emission 1.8 (was 2.4).
- `floor`: plates in three tones (`lobby_floor`, `2`, `3`: lightness 1.0, 0.96, 1.035, roughness 0.15, 0.19, 0.12),
  2 cm edge bevels, 1.2 cm seams.
- `window_frame`: mullions 0.4 m wide and 0.6 m deep with a 0.24 m cap on their inner face, the transom and head bars
  0.62 m deep, a sill ledge 0.55 m into the hall just under the sill (its top stays 0.5 m; the transom stays at 3 m).

The look is a scheme: `[look] scheme` in `hall.toml` picks one of `[look.schemes]` (default S1). A scheme gives five
sRGB colours by role, `panel` (wall and vault panels), `frame` (pilasters, ribs, the wall behind), `trim` (bands,
cornices, door and arch frames, bolts, the lamp shades), `floor` and `accent` (the strips and the ring), with the
metallic of the metals and of the trim. `[look] mats` lists each scheme material as [role, lightness, roughness,
emission]; `lobby_layout.look_materials()` resolves a scheme into colours, and both the builder (into the GLBs) and
`hall.gd` (in the shots and the grid) use that table. The hazard stripes, the red lamps, the seams, the lens and the
glass are fixed in every scheme. Until step 2c `hall.gd` also gave the non-emissive scheme materials a fine-noise
grain: one seamless noise as a subtle normal map (scale 0.25) and as a roughness map (0.8-1 of the roughness), world
triplanar, generated at run time; the GLBs carried plain colours (step 2c moved the metal surface into the GLBs).

| Scheme | panel | frame | trim | accent |
|---|---|---|---|---|
| S1 | cool blue-grey | dark graphite | graphite | warm orange (the current direction) |
| S2 | off-white | dark graphite | mid grey | cyan |
| S3 | deep navy | darker navy | brushed brass (metallic 0.9) | warm white |
| S4 | teal-grey | dark teal-grey | copper (0.85) | copper orange |
| S5 | graphite | near black | signal red | orange |
| S6 | warm bronze-grey | dark bronze | light bronze | cool white |

`lobby --grid DIR` shoots `corner_nw` and `door_d3` once per scheme into `grid.png` (1280 px, a row each, labelled) and
`<scheme>_<view>.png` at 1920 x 1080.

Measured (step 2b, S1):

| Piece | Triangles | Objects | Materials |
|---|---|---|---|
| floor | 5232 | 6 | lobby_floor, lobby_floor2, lobby_floor3, lobby_grout, lobby_ring |
| walls | 23744 | 10 | lobby_wall, lobby_panel, lobby_panel2, lobby_panel3, lobby_inset, lobby_pilaster, lobby_trim, lobby_rib, lobby_dark, lobby_strip |
| vault | 15880 | 6 | lobby_grout, lobby_vault, lobby_panel3, lobby_rib, lobby_trim, lobby_lens |
| window_frame | 1272 | 2 | lobby_trim, lobby_pilaster |
| window_glass | 68 | 1 | lobby_glass |
| arch | 1974 | 14 | lobby_wall, lobby_trim, lobby_pilaster, lobby_panel, lobby_floor, lobby_floor2, lobby_floor3, lobby_grout, lobby_rib, lobby_dark, lobby_strip, lobby_hazard, lobby_lamp |
| door (x4) | 720 | 8 | lobby_trim, lobby_pilaster, lobby_panel3, lobby_dark, lobby_hazard, lobby_lamp, lobby_strip |

48890 triangles in the 7 GLBs (51050 with the four doors placed), glTF-Validator clean. `--godot`: 37 pieces at
Blender's sizes, 60 colliders; the walk 22/22, 178.1 m in 60.2 s; the blocks hold (D1-D4 0.41 m, the corridor's end
0.90 m short of their walls; the doors' leaves sit deeper now). Shots: 24-210 draw calls, 28-93k primitives.

## Step 2c: S4 and the surfaces at release quality

The engineer picked S4 (2026-10-30): two-tone teal-grey with copper accents, now `[look] scheme = "S4"`. A critic warned
that S4 may turn green under the Earth's blue light later, so step 2c keeps its teal on the grey side: panel
(0.35, 0.42, 0.42), frame (0.25, 0.3, 0.31), floor (0.27, 0.31, 0.315), a spread under 0.1 per colour (a fast test holds
it). No layout number moved except the mullions' width (0.4 to 0.5 m, ours). The raw output is `<raw>/lobby/hall/v4/`
(v1-v3 stay).

The second critic's findings on 2b, each fixed (`lobby_build.py`):

1. Frames, pilasters and the arch were one flat black slab. S4's frame is a mid graphite-teal (above), clearly lighter
   than black. Every band of the door and arch frames (`framed`) has a 4.5 cm bevel on its outer front edge, so the three
   steps catch the light. Eight bays carry one unique detail each (`GREEBLES`; none twice on a wall, none on the north
   wall with its doors): a service hatch (a frame, a recessed door, hinges, a handle, a label plate), a pipe junction
   (two risers with copper flanges, a valve box with a red wheel, a riser to the cornice, a branch into the wall), a fire
   point (a red cabinet, `lobby_signal`, with a dark glass front, a sign, a terminal with keys beside it), and a cable
   tray under the cornice broken by a junction box with the cables dropping into it. The old small service box is left
   out of those bays.
2. The fine-noise grain read as orange peel and left a noisy hot spot on the floor. It is replaced by a brushed and
   scratched micro-surface: a shared, tiling 1024 px pair of maps generated in the build (`metal_images`, numpy in
   Blender), a normal map (streaks along u, about 260 fine scratches) and a roughness multiplier (0.78-1: soft blotches,
   the streaks, the scratches rougher), 1.5 m a repeat. Every non-emissive material but the glass and the lens uses
   them at its own roughness and metallic (`metal_maps`: the maps' G and B times the material's numbers, which the
   glTF exporter writes as the factors); the floor at normal strength 0.35, so it stays polished and clean (roughness
   0.12-0.19 over its three tones). UVs are box-projected (`box_uvs`); every 2 m cell gets a steady offset and a
   90-degree turn of the brushing, so neighbouring plates differ. Per-panel variation stays the three panel tones.
3. The lunettes (over the window's head and over the north wall) are panelled: 2 m columns like the vault's, bevelled
   panels in rows whose tops follow the vault's curve (`lunette_column`), a batten on each seam, a copper trim along the
   curve and, over the window's head, a copper band (0.36 m tall, 0.42 m deep); the face behind is dark (`lobby_grout`).
   The pendant lamps have real shades: a rolled rim, a reflective inside (`lobby_reflector`) up to a dark socket and a
   bulb in the recess (`lobby_lens`, not emissive until step 4).
4. The ribs are an I-section (`sweep`): the 1.24 m top flange over the panels' ends, a 0.4 m web, a 0.8 m bottom flange
   with chamfers, still hanging `rib_d`; a copper collar 1.3 m from each wall and a corbel from each pilaster's capital up
   under the rib. Cover strips (0.09 m, the frame's material) over the joints between each pilaster and its panels
   close the light vertical seam beside it (not beside D1's and D2's frames, where the pilaster steps back).
5. Doors: each leaf is bevelled at the centre seam (a V-groove between the leaves), its striped field sits inside a
   raised 0.12 m border; a copper lip round the opening covers the leaves' edges; a threshold plate. The red lamp
   (still at 5.1 m) sits in a housing: a back plate, cheeks, a sloped hood, a bottom lip and a cage of three bars. The
   lintel box has a chamfered lower edge and a grille either side of the lamp. Hazard stripes stay yellow-black.
6. Pilasters: a chamfered base (a plinth with cut corners, 0.4 m, and a sloped step into the shaft up to 0.62 m) and a
   mid-height band at 4.56-4.76 m on the panels' row seam. The window's mullions are sturdier: 0.5 m wide with a stepped
   cap and nose (0.34 and 0.14 m) 0.56 m into the hall, a shoe on the sill (0.45 m tall) and a collar at the transom;
   still 6 panes, sill 0.5 m, transom 3 m.

The fine metal surface is now in the GLBs' materials, so the game gets the same look: `--shoot` shows the GLBs as they
are (no material step in `hall.gd`); `--grid` recolours copies of the imported materials, keeping their maps. A new
review view `door_d1` shows D1 and the pilaster stepped back beside it; `[review] closeups` lists one close-up per fix,
which `--shoot` writes into `closeups.png` (two a row).

Measured (step 2c, S4):

| Piece | Triangles | Objects | Materials | GLB |
|---|---|---|---|---|
| floor | 5232 | 6 | lobby_floor, lobby_floor2, lobby_floor3, lobby_grout, lobby_ring | 2.9 MB |
| walls | 28216 | 11 | lobby_wall, lobby_panel, lobby_panel2, lobby_panel3, lobby_inset, lobby_pilaster, lobby_rib, lobby_trim, lobby_dark, lobby_strip, lobby_signal | 4.6 MB |
| vault | 22348 | 8 | lobby_grout, lobby_vault, lobby_panel3, lobby_rib, lobby_trim, lobby_dark, lobby_lens, lobby_reflector | 4.2 MB |
| window_frame | 1524 | 2 | lobby_trim, lobby_pilaster | 2.5 MB |
| window_glass | 68 | 1 | lobby_glass | 0.01 MB |
| arch | 2682 | 14 | lobby_wall, lobby_trim, lobby_pilaster, lobby_panel, lobby_floor, lobby_floor2, lobby_floor3, lobby_grout, lobby_rib, lobby_dark, lobby_strip, lobby_hazard, lobby_lamp | 2.6 MB |
| door (x4) | 1266 | 8 | lobby_trim, lobby_pilaster, lobby_panel3, lobby_dark, lobby_hazard, lobby_lamp, lobby_strip | 2.5 MB |

Every GLB but the glass embeds the same two maps (1024 x 1024 PNG: normal 1.7 MB, roughness 0.7 MB; also in
`<raw>/lobby/hall/v4/pieces/textures/`); a game import shares them once. 61336 triangles in the 7 GLBs (65134 with the
four doors placed; 2b: 48890 and 51050), glTF-Validator clean (0 errors; warnings only for tangents on the unmapped
emissive surfaces). `--godot`: 37 pieces at Blender's sizes, 60 colliders; the walk 22/22, 178.1 m in 60.2 s; the
blocks hold (D1-D4 0.44 m, the corridor's end 0.91 m short of their walls). Shots: 25-204 draw calls, 34-106k
primitives.

## Step 3: less copper, light wear, the critic's details (the Earth stopped)

The engineer on step 2c (2026-10-30): S4 stays; less copper; light wear; then the window's Earth with these fixes.
The raw output is `<raw>/lobby/hall/v5/` (v1-v4 stay).

**The Earth is stopped, not built.** The brief named NASA's free imagery (Black Marble, Blue Marble). NASA's media
are "generally not subject to copyright in the United States" (https://www.nasa.gov/nasa-brand-center/images-and-media/),
with conditions (no implied endorsement, no NASA insignia), but that is not one of the licences this repo allows
(`docs/manifest.md`: `CC0-1.0`, `CC-BY-4.0`, `owned-paid-output`, `own-work`, `restricted`), and a licence outside
the allowlist is the engineer's call (`CLAUDE.md`, "Decisions"). Nothing was downloaded; no source record, no sky
shader, no Earth grid (E1-E3) yet. The window still shows step 1's dark blue placeholder.

Less copper (`lobby_build.py`, `hall.toml`):

- A new material `lobby_metal`: the frame colour at 0.78, the scheme's metallic, roughness 0.4: the dark
  graphite-teal metal. The door frames' inner and outer bands, the threshold, the lamp housings, the lintels'
  grilles and bolts, the arch's portal bands and the corridor's nested frames, the pilasters' plinths, capitals, face
  plates and upper plates are in it, and so are the walls' skirting, cornice, frieze lips, vents and the bays'
  frames (`wall_trim`).
- Copper is left as thin edges and small accents: the outer band's bevel of each door and of the arch (`framed(...,
  edges=)`), the door's lip round the leaves, a 3 cm band on top of each plinth, a 3 cm lip under each capital, the
  pilasters' mid and cornice bands, the lunettes' trim, the window frame, the pendants' rims, the ring's inlays.
- S4's copper desaturated: `trim` (0.68, 0.45, 0.35) (was (0.74, 0.43, 0.28)), roughness 0.42 times a blotchier map
  (`lobby_metal_r2`, 0.6-1: `ROUGH2`).

Light wear, all in the GLBs' own materials (the game gets it):

- Every mapped material's colour is its factor times a shared grime map (`lobby_metal_g`, 0.86-1: soft blotches and
  dark specks), the exporter writing the factor and the texture (a Mix node, Multiply).
- A scuff map (`lobby_metal_s`, 0.5-1: rubbed patches and scratches) instead on the hazard stripes (scuffed doors),
  the worn floor and the worn edges (`SCUFFED`).
- Edge wear: about 55 % (`WEAR_SHARE`, a steady hash of the face's centre) of the narrow faces (at most 6 cm wide, at
  least 12 cm long: bevels, chamfers, lips, the stripes' sides) of `lobby_metal`, `lobby_pilaster` and `lobby_hazard`
  move into `lobby_worn`, bare brushed steel (`merged`, `worn`); smooth parts never.
- The floor within 3.4 m of a door's or the arch's middle: 8 plates in 10 are `lobby_floor_worn` (the floor colour
  at 0.94, roughness 0.3, the scuff map). No rust anywhere.

The critic's details:

- Pendants: 40 segments, smooth shading (`Part.smooth`, sharp edges over 35 deg kept, `make`), a dark metal shade
  with a copper rim, a cable from a ceiling canopy, a grip; heights 9.6 m -0.7/0/+0.6 by a steady pick (`PENDANT_DY`).
- The floor: a flush hex bolt head 0.1 m in from each plate's corners; service plates (one in 29 full plates: a dark
  metal plate 4 mm lower with 8 bolts and a lifting slot); a yellow keep-clear box before each door (side and front
  lines, a hatched band; `KEEP`); the ring 1.06 m wide (was 0.34): a dark metal band, two copper inlays 0.36 m off
  its radius, the dark channel and the accent line, dark seams at its edges (`RING_W`).
- The ceiling lighter: `lobby_vault` 1.24 (was 1.12), `lobby_rib` 1.22 (was 1.12).
- The lunettes' rows hang from the vault's curve at a steady 1.7 m, their seams parallel to the curve and level from
  column to column, the last row down to the bottom (`lunette_column`).
- Two close-ups: `c_door_floor` and `c_ring`.

Measured (step 3, S4):

| Piece | Triangles | Objects | GLB |
|---|---|---|---|
| floor | 15032 | 11 | 5.2 MB |
| walls | 28728 | 14 | 6.4 MB |
| vault | 37438 | 10 | 6.5 MB |
| window_frame | 1524 | 2 | 3.6 MB |
| window_glass | 68 | 1 | 0.01 MB |
| arch | 2682 | 17 | 4.4 MB |
| door (x4) | 1266 | 11 | 4.3 MB |

86738 triangles in the 7 GLBs (90536 with the four doors placed; 2c: 61336), glTF-Validator clean (0 errors). The
pendants are most of the vault's growth (6 x about 2.4k). Five shared maps, 1024 px PNGs (normal 1.7 MB, roughness
0.7, copper roughness 0.7, grime 0.3, scuff 0.7 MB), each GLB embedding the ones its materials use.

## Step 3b: the night Earth and the window frame

The engineer's decision (2026-10-30, art #356): the Earth comes from NASA's imagery; he added US government public
domain (NASA) to the allowlist as `NASA-PD`, with the credit line "Earth imagery: NASA", no NASA logos and no implied
endorsement (`docs/decisions/2026-10-30-nasa-public-domain.md`, `docs/manifest.md`).

- The sources (`sources/nasa_earth_lobby.toml`), from NASA's image server eoimages.gsfc.nasa.gov, kept as downloaded in
  `<raw>/lobby/hall/earth-src/`: Black Marble 2016 at 3 km (`BlackMarble_2016_3km.jpg`, 13500 x 6750, 8.1 MB), Blue
  Marble Next Generation, December 2004 with bathymetry (`world.topo.bathy.200412.3x5400x2700.jpg`, 5400 x 2700,
  2.6 MB), the Blue Marble clouds (`cloud_combined_8192.tif`, 8192 x 4096, 35.9 MB).
- `lobby --earth-tex` scales them in headless Blender (the Standard view, no look) to `[earth] size`, 4096 x 2048
  JPEGs at quality 92: `<raw>/lobby/hall/v5/earth/earth_night.jpg`, `earth_day.jpg`, `earth_clouds.jpg`.
- `godot/lobby/earth_sky.gdshader`, a sky shader: the planet a unit sphere along `earth_dir` at the distance that
  gives it `earth_radius_deg`; each ray that hits it reads the maps at the hit's latitude and longitude, turned so that
  `subpoint` faces the eye with north up. The night map's lights (its luminance over a threshold) turn warm orange
  (`lights_rgb`, `lights_energy`), its dark land and sea stay (`base_energy`), the day map lit by a faint moon
  (`moon_rgb`, `moon_energy`), the clouds dim the lights and glow faintly; with `sun_energy` the sunward side gets the
  day map and white clouds. The atmosphere: a thin bright blue rim at the limb (`rim_width_deg`), a little haze inside,
  a faint halo outside; toward the sun the rim turns to `dawn_rgb`. Stars: two layers of at most one star per cell of a
  cube-face grid, faded near the rim. A sky is at infinity: no parallax as the player walks. The radiance cubemap
  pass draws the review light's neutral grey sky, so the reflections and the hall's look do not change.
- `godot/lobby/window_glass.gdshader` on the `lobby_glass` surfaces: a faint tint (`glass_rgb`, `glass_alpha`) and the
  sky's reflection, stronger at grazing angles.
- `[earth]` in `hall.toml`: `variant` (the one switch, default E1; E2 since step 4, the engineer's pick), the maps, the shared `[earth.look]` and three
  variants: E1 a huge Earth (radius 48 deg, its centre 22 deg below the horizon to the south) whose limb arcs across the
  upper window; E2 the same with the sun 1.5 deg behind the limb on the east side (azimuth 30, elevation 14; the left as the spawns face the window): a
  thin dawn glow on that side of the rim; E3 a disc of 13 deg in the window's middle with more stars. The check refuses
  an unknown variant, a texture over 4096 x 2048, a grid view that is no view and angles out of range.
- `lobby --earth-grid DIR`: the variants in `[earth] grid`'s views (`spawn_eye`, `corner_nw`), `grid.png` and each
  frame at full size (`E1_spawn_eye.png` ...).
- The window frame (the engineer's "less copper"): the sill, transom, head, mullions, caps, shoes and collars in
  `lobby_metal`, the dark graphite-teal; copper only as a thin edge: a 3 cm lip along the sill's ledge and the
  transom's and the head's hall-side edges, and the mullions' 14 cm cap noses (`window_copper`). window_frame 2628
  triangles (step 3: 1524).

## Step 4: the hall's light

The drawing's words: "warm hanging lamps under the vault, orange strips on the pilasters, the Earth's cold light from
the window; darker in game than on the concept". The engineer's Earth pick (2026-10-30): **E2**, the dawn glow on the
limb, now `[earth] variant`; scheme S4 stays; no geometry moved (`raw_dir` `lobby/hall/v6`, the pieces rebuilt
unchanged, 87842 triangles).

`[light]` in `hall.toml`: `mood`, the one switch (the shots, the video and the game: default **L1**), and three moods
with the same keys (`lobby_layout.LIGHT_KEYS`; the check refuses a mood with other keys or numbers out of range).
`hall.gd` `_apply_light` builds the rig per mood (the review light's two directionals are gone when a mood is set):

| Light | Count | Shadows | Where |
|---|---|---|---|
| SpotLight3D, warm, straight down | 9 | yes (blur 1.5, atlas 4096, 4 per quadrant) | 3 cm under each pendant's lens; the lens's height read from the vault's `lobby_lens` mesh |
| OmniLight3D, orange | 16 | no | 0.35 m before each pilaster's strip (12 side, 4 north), y 3.2 |
| OmniLight3D, red | 4 | no | 0.4 m before each door lamp, y 5.1 |
| OmniLight3D, warm | 2 | no | the corridor, (0, 5, -32.5) and (0, 5, -36) |
| DirectionalLight3D, cold (the Earth) | 1 | yes (80 m) | from the window: azimuth 0, elevation 2 |
| DirectionalLight3D, warm (E2's dawn) | 1 | no | azimuth 30 (the dawn's side), elevation 4 |
| ReflectionProbe | 2 | probe shadows on | the hall (42 x 16.5 x 48 m, box-projected, not interior: it sees the Earth) and the corridor (interior) |

The lenses glow (`bulb_emit`, the pendant colour); the strips' and the ring's glTF emission times `strip_emit`, the
door lamps' times `door_emit`. The environment: AgX at `exposure`, a flat ambient colour (`ambient_rgb`,
`ambient_energy`; the probes take the same colour: a probe's default ambient is its own dark capture, which ignored
the ambient in the first grids), glow (screen blend, `glow_*`), SSAO (`ssao_intensity`), the step 2 SSR. The Earth's
sky shader draws the Earth in the radiance pass too (`cubemap_earth`), so the probes and the polished floor reflect
it; the window's glass casts no shadow. The top shot gets a plain dark background (an ortho camera streaked the sky).

| | L1 balanced (default) | L2 darker, moodier | L3 brighter, warmer |
|---|---|---|---|
| exposure | 1.1 | 1.0 | 1.15 |
| ambient | 0.16 (0.42, 0.5, 0.7) | 0.07 | 0.3 (0.66, 0.58, 0.5) |
| pendants: energy, half angle, range | 14, 48 deg, 18 m | 11, 36 deg, 16 m | 18, 55 deg, 20 m |
| bulbs' emission | 10 | 8 | 12 |
| strips: energy, range, emission | 1.5, 6 m, x1.0 | 0.7, 4 m, x0.7 | 2.4, 7 m, x1.4 |
| door lamps: energy, range | 0.8, 4.5 m | 0.6, 4 m | 1.0, 5 m |
| corridor | 2.0, 7 m | 1.4, 6 m | 2.6, 8 m |
| Earth light; dawn | 0.8; 0.2 | 0.6; 0.14 | 0.8; 0.24 |
| probes | 0.8 | 0.5 | 1.0 |
| glow: intensity, bloom, threshold | 0.6, 0.05, 1.0 | 0.7, 0.04, 1.0 | 1.0, 0.15, 0.9 |
| SSAO | 1.6 | 2.2 | 1.4 |
| GPU ms (corner_nw / spawn_eye / c_back) | 2.78 / 1.99 / 2.98 | 2.65 / 1.93 / 2.58 | 2.89 / 2.08 / 2.96 |
| draw calls (same three) | 776 / 85 / 706 | 776 / 85 / 706 | 776 / 85 / 706 |

The cost: 1920 x 1080 in the off-screen window, each shot's median GPU time over 16 frames
(`viewport_get_measured_render_time_gpu`, on this PC's GPU), the draw calls and primitives as Godot counts them
(shadow passes included); the moods differ by energies only, so their counts match. `lobby --shoot` (L1): 23 shots,
1.5-3.0 ms. The walk (`--godot`) still passes: 22/22, 178.1 m, 5 blocks hold.

`lobby --light-grid DIR`: the moods in `[light] grid`'s views (`corner_nw`, `spawn_eye`, `c_back`), `grid.png` and
each frame at full size (`L1_corner_nw.png` ...). Grid 1 and 2 (`<raw>/lobby/hall/v6/logs/grid1.log`, `grid2.log`)
barely changed with the ambient: the probes' own ambient replaced it; grid 3 is the one shown.

`lobby --video DIR`: `[video]`'s keys (eye, look, seconds) through a Catmull-Rom path, 1280 x 720 at 24 fps, from the
corridor's shut end through the arch, round the ship's east side, to the spawn line, a turn to the window and the
Earth (44.2 s); `hall.gd` renders the frames off-screen (mode `video`), headless Blender encodes them with the ship's
`tools/blender/ship_video.py` (only run, never changed) under `max_mb` into `DIR/walkthrough.mp4`, and the frames are
deleted.
Step 4's run (L1, E2): `<raw>/lobby/hall/v6/walk/walkthrough.mp4`, 1061 frames, 44.2 s, 12.7 MB, rendered in 185 s,
the GPU's median 1.58 ms a frame at 1280 x 720.

## Step 4b: L3, the critic's light fixes

The engineer's mood pick (2026-10-30): **L3**, now `[light] mood`. A fresh critic's findings on L3, fixed in L3 only (L1
and L2 keep step 4's look: the new lights off, the ship's glow as built, the Earth shadow's blur at Godot's 1.0). New
keys in every mood:

| Key | What | L3 (step 4 -> 4b) |
|---|---|---|
| `glow_threshold`, `glow_bloom`, `glow_intensity` | the environment's glow | 0.9 -> **1.2**, 0.15 -> **0**, 1.0 -> **0.5** |
| `glow_hdr_scale`, `glow_cap` | the glow's HDR bleed and luminance cap | 2.0 (Godot's) -> **1.5**, 12 -> **6** |
| `ship_emit` | the ship's glow surfaces' emission (every emissive `BaseMaterial3D` on a `ship_` piece, a per-instance override made by `hall.gd`'s `_emit`; art #263's files and materials untouched) | 1 -> **0.3** |
| `fill_rgb`, `fill_energy`, `fill_range`, `fill_angle` | an unshadowed warm SpotLight3D 0.6 m over each pendant's lens pointing up: the shade's spill on the vault, ribs and lunettes | **3.0**, 12 m, 75 deg |
| `pendant_specular` | the pendants' spots' specular (the ship's silver top's hot spots) | 0.5 -> **0.3** |
| `strip_specular`, `strip_size` | the pilaster omnis' specular (longer streaks on the polished floor) and light size | 0.5 -> **1.5**, **0** |
| `earth_soft`, `earth_shadow` | the Earth light's shadow blur (PCF) and opacity: the ship's shadow on the north wall and doors | 1.0 -> **3.0**, 1 -> **0.55** |
| `window_rgb`, `window_energy`, `window_range` | three unshadowed cold spots inside the glass (`[light] window`, y 4 m, `window_tilt` 50 deg down, 35 deg half angle): the cool sheen on the floor near the window | **3.0**, 16 m |

Changed numbers too: `door_energy` 1.0 -> 1.4 and `door_range` 5 -> 7 m (the red reaches wider on the wall);
`earth_energy` 0.8 -> 0.7 (at 1.0 the ship's south-facing aft panel between the pods went white).

The glow alone (T1, threshold 1.5, the ship as built) kept the engine rings and the wing strip blown: their emission is
far over any threshold, so the per-instance `ship_emit` was needed (T3's 0.3). The grid (`lobby --light-grid`, three
`[light.trials]` over L3 in `corner_nw`, `spawn_eye`, `c_back`; `<raw>/lobby/hall/v6/grid-4b/grid.png`) also showed two
dead ends: a strip `light_size` of 0.8 m draws its specular as a disc (a hot half-moon at a pilaster's foot), and the
Earth's soft shadow as an angular size (PCSS) cost about 1.4 ms (4.3 ms against 2.9); a PCF blur does the door's
shadow at step 4's cost.

`lobby --shoot` (L3, step 4b; `<raw>/lobby/hall/v6/shots-4b/`): 23 shots, GPU 1.6-3.5 ms (`corner_nw` 3.12, `spawn_eye`
2.25, `c_back` 3.20 against step 4's L3 2.89 / 2.08 / 2.96: the 12 new unshadowed spots cost about 0.2 ms); draw calls
unchanged (776 / 85 / 706).

## Step 4c: the Earth as an object, the closed ship

The engineer (2026-10-30, after the walk-through): the Earth behaved like a picture glued to the eye, small from the
glass and huge from far back: the sky shader draws it at infinity, so its angular size stays while the window's
changes. It is now a real sphere at a finite distance south of the window.

- `godot/lobby/earth_object.gdshader`: the planet's centre, radius and a fixed map frame (the spawn's view of it), the
  same maps, city lights, clouds, rim and dawn as the sky shader; each pixel traces the ray from the camera to the
  sphere. The mesh is a shell `[earth] shell` (1.35) times the planet's radius drawn by its back faces only
  (`cull_front`), so it lies far beyond the hall, never cuts its geometry and leaves room for the rim's halo; it
  writes no depth and blends with premultiplied alpha over the sky. The rim's angular width scales with the planet's
  angular size (a shell of fixed metres). The camera's far plane goes past the shell (D3: 1903 m).
- The sky (`draw_earth` 0) keeps the stars at infinity in the view and still draws E2's Earth at infinity in its
  cubemap pass, so the probes and the floor's reflections show it as before.
- `[earth] distance` the one switch (default **D2**), `[earth.distances]` the distance from `[earth] eye` (the spawn
  (0, 1.65, 0)) to the planet's centre along E2's centre; the radius gives E2's 48 deg from there
  (`lobby_layout.earth_object`). The check refuses a planet within 1 m of the hall's box.

| | distance to the centre | radius | from the glass (z 14.5) | parallax over x -10..10 | GPU ms (glass / back / side) |
|---|---|---|---|---|---|
| D1 near | 70 m | 52.0 m | fills the frame, cities as blobs | about 16 deg | 1.71 / 2.67 / 2.45 |
| D2 middle | 250 m | 185.8 m | a big disc, the limb in the panes | about 4.6 deg | 1.70 / 2.67 / 2.45 |
| D3 far | 900 m | 668.8 m | close to step 4b's | about 1.3 deg | 1.69 / 2.68 / 2.45 |

The centres: D1 (0, -24.6, 64.9), D2 (0, -92.0, 231.8), D3 (0, -335.5, 834.5). `lobby --distance-grid DIR`: the three
from `[earth] distance_views` (1.5 m from the glass, backed off to z -2, to the side at x -10), `grid.png`. `lobby
--earth-video DIR`: per distance `earth_<id>.mp4` along `[earth] video_keys` (1.5 m from the glass at x 0, back to
z -2, then sideways x -10..10 at z 2, looking at the window): 1280 x 720, 15.2 s, about 5 MB each, GPU median
0.84 ms. `lobby --shoot` (L3, E2, D2): 23 shots, `corner_nw` 3.23, `spawn_eye` 2.42, `c_back` 3.26 ms against step
4b's 3.11 / 2.34 / 3.19 in the same session (the jaw pieces and the Earth object, about +0.1 ms).

The closed ship. Art #263's package (`<raw>/ship/v5/export/v4`, its `ship.tscn` with the jaw nose) was measured
first: `lobby --check` joins every vertex of the shut jaws (`jaw_lower`, `jaw_upper`, `jaw_root` from the package's
GLBs, `lobby_layout.glb_points`) to the footprint (`closed_footprint`). The pointed nose reaches plan y -12.49, lobby
z **-29.49**: **0.51 m** from the north wall (the rule's 3 m), in front of the arch (its tip 1.4 m wide); D3 and D4
6.49 m (were 8.83); W, E 6.95, the window 12.04, D1 and D2 14.58 m and the spawns 2.04 m unchanged; and the ring,
centred on the longer ship's middle (z -15.76), leaves the floor. So the package instance stays off (`[ship.package]
use = false`, its numbers printed each check) until the engineer moves the ship or the rule. Step 4b's ramp stand-in
reached z -29.6, as far. Since the merged ship layout has the jaws instead of the ramp, the lobby places the pieces
the package was built from (`[ship] pieces_dir` `ship/v5/nose/b4/pieces`, the jaws built shut, no stand-in), so the
shots and the walk show the closed nose; step 4b's per-piece `ship_emit` keeps working. The walk (`--godot`) passes
with the jaws' colliders: 22/22, 178.1 m, 5 blocks hold.

## Step 5a: the ship 2.5 m south, the package's ship in the hall

The engineer (2026-10-30, art#356 comment 6536044954): the ship's plan origin 2.5 m toward the window, the spawns with
it, the Earth at D2, and the package's closed ship in the hall.

- `[ship] origin` (0, 0, -14.5), `[floor] spawns_z` 2.5 (still facing the window). `lobby --check`: the closed ship's
  nose at z **-26.99**, aft (the engine pods) z **0.46**; north wall **3.01 m**, W and E 6.95, the window 9.54, D1 and
  D2 13.22, D3 and D4 8.28 m (rule 3 m); the spawns **2.04 m** (rule 2 m). The rules are unchanged.
- `[ship.package] use = true`: the check holds the closed footprint (the shut jaws' vertices joined) to the rules,
  and the floor ring (r 15, built by `--build` into the floor piece) is centred on its middle, z **-13.26** (z -28.26
  .. 1.74; the spawns at z 2.5 now stand 0.76 m outside the ring).
- The instance: `lobby` copies the files the package's `package.json` lists from `<raw>/ship/v5/export/v4` into
  `godot/import/ship_pkg/` (ignored by git; only changed files written), its text files' `res://assets/` and
  `res://levels/` rewritten under `res://import/ship_pkg/`; the package is only read. `hall.gd` `_ship_package`
  instances `levels/ship/ship.tscn` at the origin under the key `ship_pkg` (so `_emit` scales its glows by
  `ship_emit`), frees `[ship.package] free`, plays `Nose/AnimationPlayer` "close" and seeks to its end (jaws at
  0 deg). Freed: `Clearing` (with its ground collider), `Environment` (the night clearing's WorldEnvironment fights the
  hall's AgX, exposure and glow) and the two `DirectionalLight3D` under `Lights` (the moon and the cool key: two more
  shadowed suns lighting the hall's walls and casting two more ship shadows against the Earth's light). Kept: the 105
  other lamps (scaled by the mood's new `ship_lights`) and the 7 interior reflection probes (inside the hull).
- `--godot`: the hall's 7 pieces at Blender's sizes, the package's 704 colliders, the jaws `{jaw_lower 0, jaw_upper
  0}`, the walk 22/22 (179.9 m), and 6 blocks hold; the new `nose_shut` block walks from z -29 into the shut nose and
  stops at z -25.17, short of the mouth (the lower jaw's hinge, z -22.6), where an open ramp would carry it aboard.
  A `SCRIPT ERROR` in hall.gd now fails `--godot` and `--shoot` (a missing piece once left the walk without a ship).
- The light grid (`[light.trials]` T1-T4, `<raw>/lobby/hall/v8/lgrid/grid.png`): the package's lamps (x1, x0.35, off)
  fill the nozzles cyan and cost about 0.45 ms; neither they nor a weaker window spill or pendant specular change the
  hull's near-white sides and aft panel. L3 takes `ship_lights` 0 (the nozzles dark inside, as in 4c).

GPU ms (L3, E2, D2, `lobby --shoot`): `corner_nw` 3.49, `spawn_eye` 2.42, `c_back` 3.56 against step 4c's 3.23 /
2.42 / 3.26 (the package's whole ship, interior included: about 3200 draw calls in the ship's views); with the
package's lamps on 3.98 / 2.89 / 4.23.

## Step 5a2: the ship's own light

The package's ship (art #263's silver `metal.gdshader`, base about 0.83, metallic 0.6, approved on the ship) read as a
flat cream-white under the hall's L3, its panel seams lost and hot spots on its top; in its own night scene it reads as
cool brushed silver with visible seams (`<raw>/ship/v5/export/v4/_check/shots/out_hero.png`). Fixed on the hall's side
only, per instance in `hall.gd`; the package's files and materials are never changed.

- The cause (`lobby --ship-grid`, `<raw>/lobby/hall/v9/sdiag/`, one input taken off the ship at a time; the hull's mean
  sRGB luminance in fixed crops): the hall's **warm pendants**. Without them the top (`ship_top`) goes from **0.50**
  (rgb 0.60, 0.48, 0.40: cream) to **0.27** (neutral), the whole ship from the corner (`corner_nw`) from 0.53 to 0.22.
  The hall's ambient carries the sides (`a_entrance` flank 0.23 -> 0.10 without it), the Earth's light the aft panel
  (`spawn_ship` 0.67 -> 0.48); the probes' reflections change nothing (0.49 -> 0.49). The target's wing top reads
  **0.69** (rgb 0.64, 0.69, 0.77: cool), its shaded side 0.45.
- `[light.ship]`: the ship's meshes draw on render layer 11 (`GeometryInstance3D.layers`, set when the instance is
  placed). Per set: `pendant_k` (the hall's pendants and their upward fill skip the ship by their cull mask, still
  casting its shadow through `shadow_caster_mask`; an unshadowed copy of each at this share, its specular
  `pendant_specular`, lights it), `earth_k` (the same for the Earth's light), `own_probe` (the hall's probes skip the
  ship by their reflection mask; a probe of its own, box `probe`, captures the hall without the ship and gives its
  ambient), and `key_*` and `rim_*`: unshadowed directionals on the ship alone, the ship scene's own cool key
  (-140 deg, 38 deg up) and its moon (35 deg, 30 deg up, the Earth's side) as the rim. `set` is the one switch (K1).
- The grid (`lobby --ship-grid DIR`, `<raw>/lobby/hall/v9/sgrid/grid.png`; views `a_entrance`, `c_back`,
  `corner_nw`, `spawn_ship` and the new close-up `ship_top`), the hall's own L3 unchanged:

  | set | what | top | flank | corner | aft | GPU ms (A / C / corner / spawn / top) |
  |---|---|---|---|---|---|---|
  | step 5a | the hall's light | 0.50 warm | 0.21 | 0.53 | 0.67 | 4.06 / 3.46 / 3.37 / 3.51 / 3.51 |
  | K1 | the ship's own night: key 0.55, moon 0.6, pendants x0.15, ambient 0.12 cool | 0.55 cool | 0.31 | 0.48 | 0.64 | 4.13 / 3.56 / 3.62 / 3.51 / 3.81 |
  | K2 | warmer: pendants x0.4, key 0.45, a warm grey ambient 0.15 | 0.57 neutral | 0.26 | 0.54 | 0.52 | 4.01 / 3.62 / 3.65 / 3.60 / 3.50 |
  | K3 | darker: pendants x0.1, key 0.35, ambient 0.07 | 0.49 cool | 0.20 | 0.41 | 0.44 | 3.85 / 3.52 / 3.49 / 3.45 / 3.53 |

  (Crops at 1920x1080: `ship_top` 300,300-1600,900; `a_entrance` 300,420-1000,620; `corner_nw` 400,470-1100,560;
  `spawn_ship` 800,560-1150,640. The target: 980,490-1230,560 and 760,440-1000,520.) The sets cost about 0.1-0.3 ms
  (nine unshadowed spot copies, one more probe, two directionals).
- K1 as the default (`lobby --godot --shoot --video`, `<raw>/lobby/hall/v9/`): the walk 22/22 (179.9 m), 6 blocks
  hold; GPU `corner_nw` 3.78, `spawn_eye` 2.39, `c_back` 3.78 ms against step 5a's 3.49 / 2.42 / 3.56. The ship still
  casts its shadows (the floor under it). The hall's walls, floor and vault are as in step 5a (L3).

## Step 5a3: the critic's findings on v9

A fresh critic judged v9 not ready. Fixed on the hall's side (`<raw>/lobby/hall/v10/`); the package's files and
materials untouched. Numbers: mean sRGB luminance (sd) of fixed crops at 1920x1080, v9 -> v10 (`lobby --shoot`).

- **The north wall's three "trees"** (`c_back`, x 590/960/1320, y 290): not the package (the Clearing is freed
  before the instance enters the tree, and no other package node is left). The Earth's light, 2 deg up from the
  south and shadowed, laid each column of three hanging lamps (x -10, 0, 10; z -21, -9, 3) onto the upper panels,
  stacked by distance into a soft fir tree. `hall.gd` `_fixtures`: the vault's meshes hanging below `[light]
  fixtures_below` (11 m: shades, lenses, cords, copper rims; the vault's meshes are split by material) cast no shadow;
  their own spots hang under the lenses and the fills are unshadowed, so nothing else is lost; none found fails the run.
  A `shadow_caster_mask` on the Earth's DirectionalLight3D did not take in Godot 4.7.2 (the first grid: tree/neighbour
  0.81 unchanged). The tree/neighbour panel ratio: left **0.81 -> 0.96**, right **0.83 -> 1.02**.
  `_ship_package` now also fails a run when a top-level node of the package is not in `[ship.package] keep` (Lights,
  Probes, Pieces, Nose, Stations, Markers) or a WorldEnvironment, Camera3D, DirectionalLight3D, GPUParticles3D or
  Decal is left.
- **The ship's lilac-white** (K1 of 5a2): `[light.ship]` K1 is now neutral silver: a neutral key (0.4), a grey
  ambient (0.08), the pendants x0.25, a back light from the north (`back_*`, 0.5, 30 deg up) and a warm bounce from
  below (`bounce_*`, copper, 0.22, 40 deg below); K2 warmer, K3 cooler. `ship_top` rgb **(0.52, 0.55, 0.63) ->
  (0.58, 0.57, 0.58)** (blue minus red 0.11 -> 0.00), L 0.55 -> 0.57; `a_entrance` flank (0.24, 0.25, 0.31) ->
  (0.31, 0.29, 0.29). The grid `<raw>/lobby/hall/v10/sgrid/grid.png`:

  | set | top L (rgb) | flank | corner | aft | GPU ms (A / C / corner / spawn / top) |
  |---|---|---|---|---|---|
  | K1 | 0.57 (0.58, 0.57, 0.58) | 0.35 | 0.56 | 0.65 | 4.10 / 3.55 / 3.68 / 3.93 / 3.79 |
  | K2 | 0.59 (0.63, 0.58, 0.57) | 0.30 | 0.59 | 0.48 | 3.82 / 3.57 / 3.57 / 3.54 / 3.51 |
  | K3 | 0.58 (0.58, 0.58, 0.61) | 0.29 | 0.57 | 0.44 | 3.83 / 3.60 / 3.56 / 3.70 / 3.50 |

- **Hull and north wall the same value** (`c_back`): the back light outlines the hull, and `[light] wash`, a negative
  unshadowed spot off the ship's layer, takes a little cool light off the north wall behind it. Hull/wall: the wing
  over the wall above it **0.525/0.334 = 1.57 -> 0.503/0.256 = 1.96**, the deck over the wall behind it **0.553/0.399
  = 1.39 -> 0.772/0.267 = 2.89**.
- **The Earth from the far side** (`a_entrance`, `corner_nw`): the window shows the high north at a slant (mu 0.5-0.6
  there as head-on, so not the limb; the maps are magnified, not minified). `earth_object.gdshader` reads the maps
  `soft_lod` mips softer, with less cloud and city contrast, where mu * cos(latitude) is low. The crops' sd: a_entrance
  **0.127 -> 0.116**, corner_nw **0.177 -> 0.174**: a small change, not fixed (open problems).
- **Floor glare**: the Earth's light specular 0.15 and the window spill's 0.1 (`[light] earth_specular`,
  `window_specular`; Godot's 0.5), L3's `strip_specular` 1.5 -> 0.9. `spawn_eye`'s seam (940,740-980,1080) **0.531 ->
  0.302**; `a_entrance` x1280 **0.816 -> 0.700**; `corner_nw` x1480 **0.741 -> 0.613**; `a_entrance` x690 (warm)
  **0.809 -> 0.814**: unchanged, so a reflection (kept), not a light's specular.
- K1 (`lobby --godot --shoot`): walk 22/22 (179.9 m), 6 blocks hold; GPU `corner_nw` 3.68, `spawn_eye` 2.42, `c_back`
  3.71 ms (5a2: 3.78 / 2.39 / 3.78).

## Step 5a4: the Earth's cap, the ship's back light and bounce

Raw `lobby/hall/v11`. Numbers: mean sRGB luminance (sd) of fixed crops at 1920x1080, v10 -> v11 (`lobby --shoot`);
blobs: warm bright components (L > 0.45, R > 1.3 B), their area in px.

- **The Earth's cap** (`[earth.cap]`): the 4096 x 2048 maps give 11.4 px a degree, about 0.28 m a texel on the 185.8 m
  globe, magnified several times from the hall. `lobby --earth-tex` now also cuts the box lat -8..82, lon -48..72
  (E2's subpoint [36, 12] and the 42 deg seen round it from D2, 56 deg of longitude, and a margin) from the NASA sources
  at their full resolution: `earth_night_cap.jpg` 4096 x 3072 (34 px a degree; Black Marble's 37.5) and
  `earth_clouds_cap.jpg` 2730 x 2048 (22.75, the cloud map's own); no new download. `earth_object.gdshader` reads them
  inside the box, the global maps outside, faded over `fade_deg` 3. The cities as points: a light below `city_ref` 0.7 is
  dimmed as lum^`city_gamma` 1.8 (the halos go, the cores stay); where `soft` (a slant) the cities dim by `slant_dim`
  0.6 below the glow's bloom and the moonlit clouds by `cloud_calm` 0.45; `soft_lod` 2.5 -> 1.5, the cities never
  blurred. The clouds load as L8.
  - spawn_eye (x620-1300, y330-700): sd 0.186 -> 0.171, blob area mean 16.6 -> 6.2 px, p90 24 -> 11.
  - a_entrance (x1250-1750, y340-400): sd 0.116 -> 0.114, blob area mean 5.6 -> 3.4 px, p90 11 -> 7.
  - corner_nw (x1180-1500, y360-590): sd 0.174 -> 0.141, blob area mean 10.5 -> 5.8 px, p90 16 -> 11, max 468 -> 155;
    but it looks the same at full size (the same cloud streaks and glowing dots): the part seen there is not soft
    (no change from `slant_dim`) and seems to lie outside the box. Open.
  - Memory (runtime ImageTextures with mipmaps, RGBA8 on the GPU): night and day 4096 x 2048 43 MB each, clouds L8 11 MB,
    night cap 64 MB, clouds cap L8 7 MB: about 168 MiB. With the game's VRAM-compressed import (BC1, 0.5 B a pixel;
    BC4 for the clouds) about 37 MiB. GPU: spawn_eye 2.42 -> 2.43 ms, corner_nw 3.68 -> 3.69 ms.
- **The ship's light** (K1): `back_energy` 0.5 -> 0.25: the deck's middle in c_back (x840-1080, y420-470) 0.899 ->
  0.799. `bounce_energy` 0.22 -> 0.1: the undersides in a_entrance (x1200-1700, y600-680) 0.458 -> 0.407, rgb (0.54,
  0.44, 0.38) -> (0.48, 0.39, 0.34), R/B 1.42 -> 1.41; (x900-1700, y600-700) 0.396 -> 0.370, R/B 1.50 -> 1.42. K3's
  bounce 0.12 -> 0.06 (the cooler set stays below K1).

## Step 5a5: the Earth from the hall's corner

The engineer (2026-10-31): the ship's light stays K1; before the game package the Earth seen from the hall's corner
must read as the Earth, not as a noisy photo. Raw `lobby/hall/v12` (the pieces copied from v11, unchanged). Nothing
else in the hall changed.

- **What corner_nw sees** (`earth_object.gdshader` `debug_mode` 1: the cap's weight red, `soft` green, latitude lines
  white, longitude lines cyan; and the same trace in Python, `test_corner_nw_sees_the_cap`): its window crop (x1180-1500,
  y360-590) shows Europe at lat 43-61, lon -6..24, mu 0.35-0.88, wholly inside the cap (lat -8..82, lon -48..72) and
  head-on enough; spawn_eye sees the same region (lat 42-70). So step 5a4's guess (outside the cap, a slant) was wrong.
- **The glow is not the cause**: L3 with `glow_intensity` 0 changed the crop's numbers by under 1% (blob mean 3.76 ->
  3.74 px, sd 0.142 -> 0.142).
- **The cause**: the white streaks were the day map under the moon, Blue Marble's December: snow over the north and
  the Alps at value ~1, moonlit as brightly as the clouds (with `moon_energy` 0 they vanish); the orange dots were each
  city's own halo in Black Marble, lifted over the glow's threshold by `lights_energy`.
- **The fix** (`[earth.look]`, shader uniforms whose defaults draw step 5a4): `moon_knee` 6 compresses the moonlit day
  map as day x (1 + 0.1 k) / (1 + k day): the snow x0.23, the sea (~0.1) kept, so the sea stays blue from the spawn;
  `cloud_energy` 0.16 -> 0.05 (the night clouds dark) and `cloud_shade` 0.5 -> 0.6; `cloud_city` 0.3 (the clouds lit
  faintly from the cities below); `city_gamma` 1.8 -> 2.6 (halos down, cores kept: points); `light_cap` 2 (a city
  pixel's brightest channel); `halo_energy` 0.08 (a soft small halo of the cities' own, the night map `halo_bias` 2.5
  mips softer); `haze_energy` 0.05, (1 - mu)^4 (a little atmosphere at grazing angles). Six trial sets in grids
  (`<raw>/lobby/hall/v12/debug1..3/`); stronger haze (0.15) washed the spawn's coastlines, a bigger halo (0.35) grew
  the blobs (8 px).

Numbers v11 -> v12 (`lobby --shoot`, 1920 x 1080; L mean sRGB luminance and its sd; speckle the sd of L minus its 5 x 5
mean; cloud px B >= R and L > 0.15; blobs warm bright components L > 0.45, R > 1.3 B):

| crop | L | sd | speckle | cloud px share / L | blobs | blob mean / p90 / max px |
|---|---|---|---|---|---|---|
| corner_nw (x1180-1500, y360-590) | 0.100 -> 0.082 | 0.141 -> 0.108 | 0.078 -> 0.061 | 0.077 / 0.209 -> 0.008 / 0.183 | 575 -> 394 | 3.8 / 7 / 113 -> 3.1 / 6 / 39 |
| a_entrance (x1250-1750, y340-400) | 0.165 -> 0.106 | 0.114 -> 0.069 | 0.038 -> 0.029 | 0.502 / 0.251 -> 0.133 / 0.174 | 62 -> 42 | 2.6 / 5 / 12 -> 2.1 / 4 / 7 |
| spawn_eye (x620-1300, y330-700) | 0.141 -> 0.118 | 0.171 -> 0.152 | 0.063 -> 0.050 | 0.220 / 0.281 -> 0.118 / 0.314 | 1335 -> 985 | 4.0 / 7 / 833 -> 3.0 / 6 / 64 |

From the spawn the limb, the dawn glow, the blue sea and the coastlines stay as approved; the cities are finer (Paris a
point, not a blob). GPU in the same shots: spawn_eye 2.43 -> 2.85, corner_nw 3.66 -> 4.28 ms, but the machine was shared
(the trial grids gave 2.45-2.76 ms for spawn_eye across sets); two more texture reads per pixel (the halo) are the
real cost, to be measured on a quiet machine.

## Step 5a6: less snow

The engineer (2026-10-31), from corner_nw: tone the snow down further. Raw `lobby/hall/v13` (the pieces copied from
v12, unchanged). Only the Earth's moonlit land changed: E2 at D2, the limb, the dawn glow, the cities, the clouds and
the hall are as in step 5a5.

- **Two shader knobs** (`earth_object.gdshader`, defaults off = step 5a5): `snow_cut` takes the day map's white (its
  least channel, linear, over `snow_lo` 0.12 .. `snow_hi` 0.4: snow and ice, not the dark land, the deserts or the sea)
  toward `snow_rgb`, a dark winter land, before the moon lights it; `moon_land` dims the moonlight on land, the sea
  told by its blue over red (`smoothstep(1.6, 3.0, b / r)`), so the sea and the coastlines keep theirs. `debug_mode` 2
  paints the snow mask red and the sea mask green.
- **Three strengths** (`[earth.snow]` in `hall.toml`, each a few `[earth.look]` keys over it; `lobby --snow-grid DIR`
  shoots them in corner_nw, a_entrance and spawn_eye): N1 `snow_cut` 0.5 (a bit less), N2 0.85 (barely visible), N3
  1.0 with `moon_land` 0.85 (no snow, the land almost unlit). **`set = "N2"`** is the one switch (the default).
- `lobby --earth-video DIR --distance D2` renders one distance's video.

Numbers (`lobby --shoot` / the grid, 1920 x 1080; snow px: the crop's share of bright non-city pixels, sRGB L > 0.12 and
R < 1.1 B, the moonlit clouds included, which no set changes; blue px: B > 1.4 R, L > 0.03, the moonlit sea):

| crop | v12 | N1 | N2 | N3 |
|---|---|---|---|---|
| corner_nw snow px / L | 0.056 / 0.082 | 0.036 / 0.081 | 0.021 / 0.080 | 0.010 / 0.061 |
| a_entrance snow px / L | 0.449 / 0.106 | 0.375 / 0.103 | 0.210 / 0.095 | 0.020 / 0.060 |
| spawn_eye snow px / L / blue px | 0.210 / 0.118 / 0.458 | 0.203 / 0.117 / 0.458 | 0.174 / 0.115 / 0.458 | 0.115 / 0.098 / 0.467 |

From the spawn N1 and N2 keep step 5a5's look (L and the blue sea's share unchanged); N3 darkens the land there too.
In corner_nw the grey patches that stay even in N3 are the moonlit clouds (`cloud_energy` 0.05), not snow.

## Step 5a7: the Earth far away

The engineer (2026-10-31) rejected the near Earth: at D2 (a sphere of 185.8 m, 250 m from the spawn's eye, its near
side about 64 m behind the glass) the planet changed scale with the viewpoint, a whole arc from the spawn, its surface
filling the window from the north-west corner. His pick: a planet far away, as from orbit: the same planet, angular
size, horizon height and direction from every point of the hall, the window only framing a different part of it.
Raw `lobby/hall/v14` (the pieces copied from v13, unchanged).

- **The far mode** (`earth_object.gdshader` `far_mode`, `far_eye`): every ray starts at `far_eye` (`[earth] far_eye`,
  the spawn's eye (0, 1.65, 2.5), spawn_eye's place) whatever the camera's place, and `vertex()` moves the shell by
  (camera - `far_eye`), so it covers the same directions from everywhere: the planet sits at infinity, no far plane or
  precision change (the shell stays 250 m round the eye; the far plane as D2's, 601 m). The ray's direction is the
  camera's own. Every look setting stays (the cap, `[earth.look]`, the snow set N2, the dawn glow, E2's frame); the
  sky's cubemap pass still draws E2 at infinity for the probes and reflections.
- **Two far distances** in `[earth.distances]` (`far = true`; `distance_m` only sizes the shell): **F48** D2's sphere
  (E2's 48 deg), so from the spawn it is D2 as approved; **F36** a radius for 36 deg at the same centre, its sun
  turned toward the centre so it stays 1.5 deg behind the smaller limb (the dawn glow kept; `lobby_layout.earth_object`
  gives the object its own `sun_dir`). **`distance = "F48"`** the default for now; D1-D3 stay for comparison.
- **The route** (`[earth.route]`, `lobby --earth-route DIR [--distance ID] [--no-video]`): a 30.1 s walk at 1.6 m
  looking at the window, round the ship's west side to the north-west corner (-17, -27), back to the glass at (6, 13),
  along it to (16, 10), round the east side to the arch's mouth (0, -28.3); one `route_<id>.mp4` per distance (the
  [video] size and fps, 1280 x 720). Stills from `points` into `grid.png`, a row per point (spawn, corner_nw, glass,
  arch) and a column per distance (the grid's `rows = "views"`), and `parallax.json`: the pair `par_spawn` (0, 2.5) and
  `par_glass` (16, 10) look in one direction (due south, 15 deg up) with the hall hidden; hall.gd scans the limb's row
  per 32 px column and the runner turns the rows' difference into degrees.

| | the limb across the hall (par_spawn vs par_glass) | GPU ms spawn / corner_nw / glass / arch |
|---|---|---|
| D2 | median 3.33 deg, max 12.0 deg (60 columns) | 2.59 / 3.72 / 1.98 / 3.90 |
| F48 | 0.000 / 0.000 deg (60 columns) | 2.59 / 3.96 / 1.98 / 3.93 |
| F36 | 0.000 / 0.000 deg (46 columns) | 2.37 / 3.72 / 1.95 / 3.90 |

From the spawn F48 draws D2's picture. F36 sits lower: from the spawn its limb arcs inside the window's upper panes,
from corner_nw its horizon shows in the window's slit (F48 there shows only the surface and cities). From the arch's
mouth at eye height the ship's nose, 1.3 m ahead, hides the window for every distance.

## The export (step 5b)

```
tools/run.sh lobby --export <raw>/lobby/hall/v15/export/v2 [--no-compare]
```

The engineer's last pick first (2026-10-31): `[earth] distance = "F36"`; raw `lobby/hall/v15` (the pieces copied
from v14, unchanged; `lobby --shoot <raw>/lobby/hall/v15/shots` the references). Then the game-ready package, made
the way the ship's is (`docs/ship.md` "The export"), shaped like the game's tree:

- `assets/environment/lobby/`: the hall's 7 GLBs, each once, with a minimal `.import`; the Earth's five JPEGs under
  `earth/` (the maps 4096 x 2048, the caps 4096 x 3072 and 2730 x 2048: 8.3 MB, imported VRAM compressed with
  mipmaps, about 57 MB of video memory); `earth_sky`, `earth_object` and `window_glass.gdshader`;
  `materials/lobby_env.tres`, `earth_object.tres`, `window_glass.tres`.
- `levels/lobby/lobby_hall.tscn`: `LobbyHall` > `Hall`, `Ship`, `Earth`, `Environment`, `Lights`, `Probes`,
  `Markers` (`Spawn0..9`, yaw 180: forward at the window). `Ship` instances the ship package's
  `res://levels/ship/ship.tscn`; the package is never copied into the lobby's files.
- `package.json`: the files with SHA-256 and bytes, the spawns, the ship package (its raw folder and version), the
  Earth (variant, distance, snow, credit, source) and the questions.

How: `godot/lobby/export_scene.gd` extends `hall.gd` and runs its assembly (`_environment`, `_build` with the ship
package, `_glass`, `_apply_light`) headless, the pieces and the ship instanced in edit state (`hall.gd` `_gen`), then
packs the tree with every instance editable (1066, the ship's own pieces too), so what `hall.gd` sets by code is saved
as overrides: the glass, the lamps' shadow flags, the glow surfaces (the ship's at `ship_emit`), the ship's render
layer 11 on its 1677 drawn meshes, its hidden lamps. A packed scene keeps no removal, so the nodes `[ship.package]
free` names are switched off instead (`hall.gd` `_hide_freed`, `_drop`): hidden and disabled (the clearing's ground
collider leaves the world), and the ship's `WorldEnvironment` gets the hall's environment (null is no override, and
the clearing's night environment beside the hall's took over the whole picture: `spawn_eye` 59.5 of 255 off in the
first run). The Earth's textures are staged into `godot/import/lobby_earth/` with the package's import options and
loaded by `hall.gd` from `res://` there. `lobby_export.relocate` moves the paths (the ship's to its own game paths),
`leftovers` refuses an art path, a script, a sub-resource path or a path outside the two packages.

The check (`_lobby_export.py`, `godot/lobby/export_check.gd`), on the export folder as its own Godot project with the
ship package's 204 files copied beside the lobby's: the import; each hall GLB's bounds against Blender's (0.01 m) and
its colliders; the tree (the root, its groups, no script, the spawns' places and facing, the ship's scene path and
place, `Clearing` off, no foreign environment or sun, the jaws shut, every drawn ship mesh on layer 11, colliders on,
the Earth in far mode with the package's textures); the 1.36 m capsule through `[walk]`'s points on the exported
scene; then, unless `--no-compare`, `spawn_eye`, `corner_nw` and `c_back` from the package in an off-screen window
beside `--shoot`'s (`<raw_dir>/shots`): the mean difference (at most 2.0 of 255) and the share of pixels off by more
than 16. `DIR/_check/report.json`; `assets/environment/lobby/` commits its copy, the manifest, `package.json` and
`HANDOFF.md`.

Results (v15/export/v2): 19 files, 38.5 MB (the GLBs 29.8 MB, each embedding its copy of the metal set); the 7 GLBs
within 0.0 mm of Blender's; 60 lights, 3 probes, 10 spawns; the ship 704 colliders on, 1677 meshes on layer 11, no lamp
on, jaws 0/0; the walk 22/22 points in 60.8 s, lowest 0.00 m. The views (mean of 255, pixels off > 16, draw calls, GPU
ms against `--shoot`'s): `spawn_eye` 0.07, 0.00%, 74, 2.65 (2.79); `corner_nw` 0.74, 0.95%, 3199, 3.54 (3.67);
`c_back` **3.16**, 5.05%, 2684, 3.51 (3.50): over the rule, so the command still fails. In `c_back` the package is
brighter in the upper half (walls near the window about +10 bluish, the hull +17/+10/+4 warm, the floor equal); not
timing (a 60-frame warm-up changed nothing) and not the project settings (the same as the art project's).

## Step 5c: the Earth lowered

```
tools/run.sh lobby --earth-route <raw>/lobby/hall/v16/earth-route
```

The engineer (2026-10-31): backing away from the window there was no sky, only the Earth; on a station the horizon is
below eye level, the planet fills the lower part of the view and black sky with stars shows above it. F36's limb topped
out at +14.2 deg above the eye's horizontal (traced from `far_eye`; not the 24 deg first guessed). `[earth.distances]`
H1, H2 and H3 are F36 turned down about the eye (`lobby_layout.earth_drop`, `pitch_down`) so the limb's highest point
sits at `limb_deg` +4, -2 and -8 deg (measured 4.05, -2.03, -8.10); the size (36 deg), the far mode, the look (cap,
`[earth.look]`, snow N2) and the sun's angle behind the limb (the dawn glow) are kept, and the sky's cubemap Earth and
its sun turn with it (`earth_request`). `earth_object` reports `limb_deg`. The route compares F36, H1, H2, H3 and has a
`far_back` point (x -12, z -20); there the ship's nose hides most of the window, so `corner_nw` (z -27) is the deep view.

Default `[earth] distance = "H1"`: from every point of the route the window shows black sky with stars above the
planet, and the dawn glow stays on the limb. H2 leaves the spawn a sliver over the sill and H3 nothing: with the planet
at infinity its horizon has one elevation from everywhere, and the sill is 4.7 deg below the spawn's eye, so a limb
low enough for sky from deep in the hall cannot also fill the window's lower half from the spawn (that needs about
+20 deg, which closes the sky from the back: the engineer's call, or a lower sill).

The export's `c_back` (`lobby --export`, still 3.15 of 255 off `--shoot`'s): `export_scene.gd` now loads the saved
scene back and compares every node's stored properties (resources one level deep) with the assembled tree
(`export.json` `roundtrip`): no difference, so the pack loses nothing; the GLBs' import options match the art
project's but for the animation fps. What is left is the scene at run time: the ship package's freed nodes are only
hidden in the package (`Clearing`, its `Environment` with a second `WorldEnvironment`, its sun) and the probes capture
at load rather than after `hall.gd`'s assembly. Next: free those nodes in `export_check.gd` before the views and
compare again.

## Step 5c2: the level script

```
tools/run.sh lobby --export <raw>/lobby/hall/v16/export2 --no-compare
```

The package's one script, `levels/lobby/lobby_hall.gd` on the root `LobbyHall` (source `godot/lobby/lobby_hall.gd`, no
`res://` path in it): a saved scene still keeps the ship package's `Clearing`, its `Environment` (the second
`WorldEnvironment`) and the suns under `Ship/Lights` switched off (step 5b), and on `_ready` the script frees them (its
exported `ship_free`, the paths `export_scene.gd` takes from the nodes `hall.gd` `_drop` switched off), as the art's
assembly and the ship package's HANDOFF S7 do; one frame later it takes every `ReflectionProbe` of the level (the
hall's 3, `probe_ship` and the ship package's) out of the tree and puts it back in its place, so each `UPDATE_ONCE`
probe captures again without them. The jaw nose, layer 11 and the glow scaling stay overrides in the scene; the
switched-off state stays too, so the scene without the script draws nearly the same. It sets the root's metadata
`ship_freed` and `probes_recaptured` (the check reads them). `export_scene.gd` attaches the script after the assembly
(its `_ready` runs only in the game and the check); `lobby_export.leftovers` allows exactly that script once, in the
scene, and refuses any other; `package.json` names it (`level_script`).

The check (`export_check.gd check`) reads the tree after the script's `_ready` and three frames: `Ship/Clearing` and
`Ship/Environment` gone, no `WorldEnvironment` and no `DirectionalLight3D` left in the ship, `ship_freed` equal to
`ship_free`'s length, every probe recaptured, the root's script the level script and no other script. The views
(`lobby --export DIR` without `--no-compare`) run the script too: whether it closes `c_back`'s 3.15 is for that window
run to show (not run in step 5c2: no window while the engineer plays).

## Follow-up #366: the review's minors

The review of #364 (comment 6550662374), raw `lobby/hall/v17` (the pieces copied unchanged from v16):

- A far distance's centre is placed, and turned down, from `far_eye` (the spawn's eye, z 2.5), the point
  `earth_object.gdshader` traces every ray from, no longer from `eye` (z 0): H1's limb is 4.00 deg above the spawn's
  eye (was 4.05: the same picture, 0.05 deg), H2 -2.00, H3 -8.00, F36 14.00 (was 14.17); F48 and F36 sit 2.5 m south of
  D2's centre. The sky's cubemap Earth (a direction) now agrees with the object exactly from the spawn.
- `earth_problems` refuses a `limb_deg` more than `LIMB_TOL` (0.2 deg) off the limb as traced (`limb_top`), e.g. a
  centre off south turned down about the east-west axis.
- `glb_points` refuses a node with children or a matrix, positions that are not plain float VEC3, and any extension in
  `extensionsUsed` but the material and light ones (`GLB_LOOK_EXT`: the ship's jaw pieces use
  `KHR_materials_emissive_strength`, which leaves the vertices alone).
- `hull_outline` puts `tools/blender` on `sys.path` only for its import; `_lobby_export.ship_copy` refreshes the check's
  copy of the ship package by SHA-256 (a `.import` only when missing: Godot's import rewrites it).
- `lobby_hall.gd` returns after its frame's await when the level has left the tree.
- `test_the_far_earth` keeps its shader source pins as a guard; `test_the_far_earth_traced` checks the far mode's trace
  in numbers (H1's limb hit at 3.95 deg, missed at 4.05, from any camera place).
- `lobby --check`'s and `--shoot`'s request files make `tools/out/lobby` (a fresh worktree has none).

## Open problems

- Step 5b/5c: `c_back` from the package is 3.15 of 255 off `--shoot`'s (step 5c: not the pack; step 5c2: the level
  script frees the ship's switched-off nodes, the window comparison still to run); the cause is to find before the package
  goes to the game. The hall's GLBs each embed the metal texture set (about 4 MB each): one shared set would save
  about 24 MB.

- Step 5a7: F36 picked (2026-10-31). From the arch's mouth the ship hides the window.
- Step 5a3: the back light leaves a hot spot on the deck's middle in `c_back` (0.77; `back_energy` 0.5 is the
  knob), and the warm bounce reads copper-orange on the undersides in `a_entrance` (`bounce_energy` 0.22).
- Step 5a5: corner_nw's Earth fixed by the night look (snow under the moon, the cities' halos); the GPU cost of the
  halo's two texture reads is to be measured on a quiet machine. Step 5a6: the snow down to N2; what grey stays in
  corner_nw is the moonlit clouds (a further step would lower `cloud_energy` there).
- (Step 4b, before the jaw nose) The ramp stand-in: down, its foot at z -29.6, 0.4 m from the north wall and in the arch's mouth; the 1.35 m beside it is
  narrower than the 1.36 m capsule, so the walk crosses its foot. The ship's closed state (ramp up) is art #263's to make.
- The spawns are 2.04 m from the engine pods (the rule's 2 m): from a spawn the pods fill the view (`spawn_eye`).
- Step 5a: the package's ship reads near white all over under the hall's light (its hull material is far lighter than
  the pieces' GLBs of step 4c: `a_entrance`, `c_back`, `top`, `c_ring`); its lamps and the window spill are not the
  cause (the grid). Next: the ship on its own render layer with the pendants and the Earth light culled from it, or
  a per-instance albedo scale in hall.gd. The aft panel and the silver top's hot spots stay with it.
- Step 5a: the spawns (z 2.5) stand 0.76 m outside the re-centred floor ring.
- Concept C drew a two-pod ship; ours has three pods, so C's back view differs there.
- Concept A's camera cannot be matched with the ship 7 m north (see above); A shows the ship's nose close up.
- The pilaster width (0.8 m, not the drawing's 1.2 m glyph) and the vault's cross-section are our readings of the
  drawing.
- Step 4b (L3): the ship's south-facing aft panel between the engine pods still reads near white from the window's
  side (`c_back`, `spawn_ship`); lowering the Earth light to 0.7 did not change it, so its source (the probe's
  reflection of the window or the panel's own material) is still to find.
- Step 4's light: the ship's silver top takes hot spots under the six pendants 4 m above it; the vault and its ribs
  stay dark (the pendants shine down, only the ambient reaches up); in L1 the west wall away from its strips reads
  dark; the pendants' pools on the polished floor show little at eye height (mostly specular), clearly from above.
- The lunettes' two end columns (where the vault meets the side walls) stay unpanelled: a dark wedge (`c_lunette`).
- The vault and its I-section ribs still read dark under the review light (no light from below until step 4); the
  collars and corbels show mostly as copper glints.
- S4's teal is checked only under the review light; the Earth's blue light (step 3) may push it green.
- The vault's inner panels' bevels still catch small glints at grazing angles (`rib`).
- Step 4c: the closed jaw nose stands 0.51 m from the north wall in the arch's mouth (rule 3 m); the ship's place or
  the rule is the engineer's call (moving the ship 2.5 m south puts the pods' ends past the spawns at z 0).
- Step 4c, D1: from the glass the 4096 x 2048 maps are magnified (cities as soft blobs); walking east the sun (at
  infinity, 1.5 deg behind the limb at the spawn) comes out from behind the near globe as an orange ball.
