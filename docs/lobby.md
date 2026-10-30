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
| Spawns | ten at z 0, x -9..9 step 2 | H.spawns |
| Ship | plan origin at (0, 0, -17), nose north: lobby x = plan x, lobby z = plan y - 17, lobby y = plan h; nose z -24.10, the pods' ends z -2.04 (the mid pod), middle z -13.07, half span 13.05 | the engineer, 2026-10-30 |

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
tools/run.sh lobby --earth-tex                 # step 3b: NASA's maps -> <raw>/<[earth] tex_dir>, 4096 x 2048 JPEGs
tools/run.sh lobby --earth-grid <raw>/lobby/hall/v5/grid    # step 3b: the Earth variants E1-E3
tools/run.sh lobby --light-grid <raw>/lobby/hall/v6/grid    # step 4: the light moods L1-L3
tools/run.sh lobby --video <raw>/lobby/hall/v6/walk         # step 4: the eye-height walk-through MP4
tools/run.sh lobby --distance-grid <raw>/lobby/hall/v7/dgrid    # step 4c: the Earth's distances from three positions
tools/run.sh lobby --earth-video <raw>/lobby/hall/v7/earth-video  # step 4c: one 15 s MP4 per distance
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

## Open problems

- (Step 4b, before the jaw nose) The ramp stand-in: down, its foot at z -29.6, 0.4 m from the north wall and in the arch's mouth; the 1.35 m beside it is
  narrower than the 1.36 m capsule, so the walk crosses its foot. The ship's closed state (ramp up) is art #263's to make.
- The spawns are 2.04 m from the engine pods (the rule's 2 m): from a spawn the pods fill the view (`spawn_eye`).
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
