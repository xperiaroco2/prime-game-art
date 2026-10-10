# The House map as data

The House map (map request #73, design doc `docs/design/house-map.md` in the game repo) is assembled from layout
data, not hand-placed scenes, so the layout can change after playtests. Art #75 built the layout engine and the shell;
later packages add dressing data (`layouts/house/dressing/`, #75b) and only regenerate.

## Files

| File | What |
|---|---|
| `layouts/house/house.toml` | Settings: the kit spec, the kit folder under the raw folder (`kit_dir`: `kits/house/v2`; v1 and v2 share the piece ids, so it is the one setting that switches kits), the `res://` paths of the pieces and scenes, the level order |
| `layouts/house/{basement,ground,upper,attic,roof}.toml` | One level each: `floor_y`, the default wall family, the house `footprint`; `[[rooms]]`, `[[doors]]`, `[[windows]]`, `[[holes]]`, `[[stairs]]` (a U-turn lists its lower half and landing in `below`), `[[pieces]]` (one free kit piece each: `piece`, `room`, `at` = [x, h, y] of its pivot, `turn`; the porch and the chimneys), `[[roofs]]` (a pitched roof from the kit over a room: `room`, `rect`, `gables`, optional `h`; the attic's), `[[placeholders]]` |
| `tools/runner/house_layout.py` | Load, validate, plan (choose the pieces), write the scenes |
| `tools/runner/commands/house.py` | The `house` command |
| `tools/tests/test_house_layout.py` | The rules, the plan's conventions, the design doc's 35 rooms and the game's greybox marker names |
| `layouts/house/dressing/<room>.toml` | One room's props and light fixtures (#75b); the ground floor's eight rooms |
| `tools/runner/house_dressing.py` | The dressing: catalogue, checks (bounds, overlaps, stations, the capsule's paths), scene nodes |
| `tools/tests/test_house_dressing.py` | The dressing's rules, and the ground floor against the plan's inventory and the stations |

Coordinates are the design doc's: metres, x east, y south, origin at the plot's north-west corner; a `rect` is
`[x, y, width, depth]` from its north-west corner. Godot's x = x and z = y; heights in a room are above its level's
`floor_y` (basement -3.2, ground 0, second floor 3.2, attic and roof deck 6.4).

- **Rooms**: `id` (the game's file name), `node` (the game's node name), `title` (the doc's), `rect`, `kind`: `room`
  (walls and floor), `open` (floor, railing or parapet, no walls: the terrace, the balcony, the roof deck) or `area`
  (no geometry yet: the yard, the garden and the other outdoor zones, built by #80 and #81); `floor` (boards, lino,
  concrete, roof), `walls` (a family other than the level's: `glass` for the greenhouse), `stations` and `markers`
  (the game's greybox `Stations` and `Markers`, room-local Godot x, height, z).
- **Doors**: `at` (the centre, whole metres), the `rooms` it joins, `names` (the game's `Doors` marker per room),
  `kind` (`door`, `glass`, `gate8` for the garage door, `gap` for a marker without a wall piece: fence gates, stair
  tops), `leaf` (`none`, `ajar`: a static leaf as dressing, `kit`: the piece has its own leaf).
- **Windows**: `at` and the `room` whose exterior wall holds it.
- **Holes**: a floor opening `rect` (with `railing = true` on its free edges) or a hatch `tile` (the kit's hatch floor).
- **Stairs**: the kit `piece`, its footprint `rect`, the foot's height `y` and the `climb` direction (N, S, E, W).

## The command

```
tools/run.sh house [--check] [--out DIR] [--layouts DIR] [--walk DIR]
```

It validates the layout, then writes into `--out` (default `godot/import/house/`, ignored, `res://import/house`) one
scene per room (`<level>/<room>.tscn`, origin at the room's north-west corner like the game's greybox rooms), one per
level (`<level>.tscn`: the rooms at their positions, the stairs and railings) and `house.tscn`; the plan goes to
`tools/out/house/plan.json`. Pure Python, a second; the scenes instance the kit GLBs at
`res://import/kit_<id>.glb`, where the `kit` command puts them.

`--walk DIR` then stages the pieces the scenes use from `<raw>/<kit_dir>` as `godot/import/kit_<id>.glb`, imports
them headless and runs `godot/house/walk.gd` in a window placed off-screen (pictures need one; Godot and its import
take the heavy-run lock). The request (`house_layout.walk_request`, written to `tools/out/house/walk_request.json`):

- every open doorway (kinds `door`, `glass`, `gate8`; not those whose kit piece holds a closed leaf, `leaf = "kit"`:
  the garage gate, the greenhouse door) of the ground and upper floors, crossed from its first room into its
  second, 1 m either side of the wall line, by a capsule 1.36 m wide and 1.8 m tall at 3 m/s (the kit's door is
  exactly 1.4 m clear: a 1.4 m capsule touches both jambs and jams, so the walk keeps 2 cm a side);
- every flight (`stairs_main`, `stairs_basement`, `stairs_balcony`) up and down, from 1 m before its foot to up to
  1 m past its top (less where the room there is short: the pantry's landing);
- a 3 x 3 m pad under each walk end that has no floor (the yard; #81a builds the real ground);
- a control: the 1.5 m capsule must stop at the first door (the colliders are there).

A walk arrives when it gets within 0.3 m of its last point at that point's height (0.15 m); it gives up after 30
ticks without moving. Into `DIR`: `walk.json` (each walk's end, time and verdict; draw calls, objects and primitives
per view; mesh instance and body counts), the eye-height stills (1.6 m), `aerial.png`, `plan_ground.png` (the ground
floor from above, the other levels and the ceilings hidden, a label per room), `sheet.png` (1280 px wide) and
`exterior.png` (the four sides at dusk from 1.7 m eye height outside the plot, 1280 px wide; the kit's own colours, the
`[[placeholders]]` as see-through orange boxes of their `size`, from the marker up). The lamps
(one warm omni per room, no shadows) and the dusk sky only light the shell for review; they are not the house's light.

## Dressing (#75b)

One file per room in `layouts/house/dressing/<room>.toml` (`room` = its id): `[[props]]` and `[[fixtures]]` (the light
fixtures' meshes; their lights are #83's), each with `id`, `at` = [x, h, z] room-local like the stations, at the
prop's pivot (`floor`: the footprint's centre; `wall`: the back's bottom centre on the wall's face, 0.1 m off the grid
line; `ceiling`: the top's centre, `h` 3.0 under the slab), `face` (N, E, S, W: where the front, +Z, looks; default
S) or `yaw` (degrees, Godot's Y rotation), and optionally `station` (the prop belongs to that station's set),
`outside = true` (on the facade), `size`/`pivot`/`collision` (an id no catalogue has: the door leaves), `note`.
Sizes and pivots come from the catalogues in `house.toml`'s `prop_specs` (the task props, `props/tasks.toml`; the
dressing library, `props/library.toml`; `--props-spec` adds one, e.g. a library not yet on main); the GLBs from its
`prop_dirs` under the raw folder, staged by `--walk` as `res://import/prop_<id>.glb`. A prop with no GLB yet becomes a
named `CSGBox3D` of its size (colliding unless `collision = "none"`, `metadata/placeholder`). The room scene gets
`Dressing` and `Fixtures` groups, each node with `metadata/prop` (and `metadata/station`).

The `house` command checks the dressing after the layout and fails on a problem (`tools/out/house/dressing.json`):
- every id known, the footprint inside the room's wall faces (open edges: the rect), a wall prop's back on a wall
  face and not on a door opening, no two solid props overlapping (solid: a collider, spanning 0.3 to 1.8 m);
- no solid prop within 1 m of a station marker unless it is that station's, none within 0.5 m of a spawn marker;
- the 1.36 m capsule on a 0.1 m grid (walls 0.2 m with the doors' 1.4 m openings, floor holes and stairs as
  obstacles) reaches from the room's first door, with the props in place, every door (0.8 m in), stair foot, flight
  top, station (within 2 m) and spawn marker (within 1 m) that it reaches in the empty room. What the empty room
  itself does not reach is a note: the pantry stairs' top landing (1 m deep).

With a dressing, `--walk` also lights and shoots it (`house_dressing.review_request`): a c2 stand-in omni light (no
shadows) at every light fixture replaces the shell's one centre lamp in those rooms (real-time review light; the bake
is #83's); one shot per dressed room from its deepest door, 0.3 m in, at 1.6 m eye height (`room_<id>.png`); the
kitchen's order board from 4 m in front (`kitchen_order_board.png`); and the package colours (`SWATCHES`: cardboard
#a8855e, white, cyan, purple, terracotta, mustard, look.md section 4) as 0.25 m cubes on the assembly island
(`swatches.png`), each front face sampled and logged as `swatch <name>: #paint (L*, C*, h) reads #seen (...; hue
shift)`. `rooms.png` (1280 px) holds the plan, the order board, the swatches and the room shots; the log and
`walk.json` `rooms` give per room the view's draw calls and primitives and the dressing's meshes and triangles.

Defaults used (questions.md): Q9 B, the leaves of the front and terrace doors stand open against a jamb as
placeholder boxes without collision until a leaf prop exists; Q11 A, no per-room wall colour (the kit's #3a6264);
Q21 B, the inventory's props and counts for every room. Notes from the game's greybox: spawn marker Circle01 lies
under the dining table and Circle02 0.2 m from the terrace table.

## The rules (`validate`)

- Rooms on whole metres; no two rooms with floors overlap at one height (an open room may hold a room: the roof deck
  holds the attic, and its floor skips the attic's cells); a level's `footprint` is tiled exactly by its rooms.
- Door and window centres on whole metres, on a wall of their rooms; an opening's 2 m module (8 m for the garage
  door) lies inside one wall run, so no door is within 1 m of a corner, and no wall meets it; windows only on
  exterior walls of their own room.
- Each flight's rise ends at a level's floor; its top edge lies on a hole's edge with the hole over its top metre (the
  stairs, the pantry stairs, the attic ladder) or on the edge of a floor it stays outside (the balcony stairs).

## The plan

- **Walls** come from the room rectangles: a unit edge with one walled room is exterior (the `_ext` piece, its
  exterior side out), with two it is interior (`_int`), owned by the first room in the file. A run is a straight line
  of edges with one class and owner; it gets a door or window module at each opening's centre, then 2 m and 1 m
  fillers. Pieces run along local +X with their exterior at +Z (docs/kit.md), so the pivot sits at whichever end
  that direction starts from.
- **Corners**: where exactly two perpendicular edges meet, the corner filler fills the notch in the quadrant opposite
  them (`_corner_ext` outside the walled rooms, `_corner_int` inside); a free wall end gets the end cap.
- **Floors**: per room on its own 2 m grid, 2 x 2 tiles, then 2 x 1 both ways, then 1 x 1, round holes; the hatch is
  the kit's hatch tile. A floor slab's underside is the ceiling of the level below, so no ceiling pieces are placed.
- **Railings and parapets**: an open room's edges without a wall get railings (`railing = "balcony"`) or a parapet with
  its four corners (`"parapet"`); a hole's free edges get railings; stair tops and gap doors stay open.

## Defaults used (questions in the plan's `questions.md`; the engineer may change any as data)

- Q5, the pantry stairs: a straight flight north to south with a 1 m top landing (the pantry floor y 24..25): hole
  x 26..28, y 25..30, foot in storage at y 31, 1 m from the parts shelf at (27, 32). Marked `placeholder`; the option
  is a U-turn of two half flights.
- Q6: the balcony stairs run straight north, the foot on the yard at y 15.
- Q7 B: 16 windows on the ground floor, 16 on the second floor, 4 knee windows in the attic, 5 in the garage.
- Q9 B: leaves standing ajar at the front door, the terrace door and the garage side door; the greenhouse door is
  the kit's own leaf; open doorways elsewhere.
- The attic hatch: the kit's hatch tile puts the hole's centre on whole metres, at (28, 29) instead of the doc's
  (28, 28.5).
- The study door is at (34, 28) as on the plan (the game's greybox has it at (34, 25)).
- The front porch and the two chimneys are kit v2 pieces (`[[pieces]]`): one `porch_2x2` from x 29 on the front
  wall, so its posts (x 29.12 and 30.88) leave 1.64 m clear round the front door at x 30, its lamp socket for the porch
  lamp (#74b); the chimneys centred on the doc's points (22, 42) and (38, 24.5).
- The attic's pitched roof is kit v2's (`[[roofs]]` in `attic.toml`, `pitched_roof` in the engine): the placements of
  `kit_geom.attic_roof` over the attic's 20 x 14 m (docs/kit.md, "Pitched roofs"), pivoted on the knee walls' top
  (2.2 m), the eaves on y 26 and 40 and the ridge on y 33; with `gables = true` the gable walls on x 20 and 40, per
  slope row (2, 2, 2 and 1 m from each eave) a `gable_tri_*` over `gable_band_*` of the row's length, so their tops
  follow the roof's line. Every height comes from the kit's spec, so the roof follows the kit's pitch: tonight 0.7 per
  metre (Q2 option A, the ridge 7.1 m over the attic floor), because kit v2 is built at 0.7; Q2's default B (0.35) is a
  kit rebuild with `gable_rise_per_m` 0.35 and needs no layout edit. The two gable windows stay named `Placeholders`
  markers: the kit has no gable window piece.
- The main stairs (not the doc's straight flight): a 6 m flight fills the 6 m stairs room, so its foot sits against
  the hallway wall, and a capsule stepping onto it from a door hits the door's head (2.15 m). Instead a U-turn of the
  kit's two half flights (`below` in the stairs entry: the lower half and the landing): up west from the room's open
  half at x 30 to a 1 x 4 m landing at 1.6 m on the west wall, then up east to the upper landing at x 30, all under
  the doc's hole (26, 30, 4 x 6). Marked `placeholder`; the outdoor (concrete) pieces stand in until kit v2 has
  indoor ones. Option: a 5 m steeper straight flight with a 1 m foot landing (kit v2).

## Light (#83a)

`layouts/house/lights.toml` is the light kit as data; `tools/runner/house_lights.py` places it and `house` writes it
with the shell (the fixtures and the summary to `tools/out/house/lights.json`). Every number is taste data: change it
and regenerate.

- **Types** (`[types.<id>]`, the 16 fixtures of the plan's `inventory.md` §8): `mount` (`ceiling`: a grid under the
  ceiling; `wall`: spaced along the walls 0.15 m in, 1.2 m clear of the room's doors; `floor`: a grid 0.6 m in from
  the walls), `h` (the light's height over the room's floor), `light` (`omni`, or `spot` pointing down with `angle`),
  `energy`, `range`, `color` (a name in `[colors]`; c2, the lab's lamp colour, unless the type or the room says
  otherwise) and `glow` (may get the cheap real-time glow).
- **Fixtures** (`[rooms.<id>]`: type = count; 191 in all): positions are generated per room; `place = "perimeter"`
  spaces a room's ceiling and floor fixtures 2 m in along its edges (the yard, which holds the house); a room's
  `color` recolours its types without a colour (the greenhouse's green cold).
- **Moon spots** (`[moon]`): bake-only cool spots, one per `every` windows of a level, outside the window, aimed in.
- **Zones** (`[zones.<id>]`): the separate LightmapGI bakes (basement, ground, upper with the attic, outbuildings,
  roof, yard); each room is in exactly one; `texel_high` and `texel_low` are the lightmap texels per metre of the
  presets.
- **Bake** (`[bake]`): the LightmapGI settings every zone shares (quality, bounces, the bounce energy at most 1.5,
  denoiser, interior).
- **Presets** (`[presets.high]`, `[presets.low]`): the lightmap resolution, the real-time glow count (the nearest
  fixtures with `glow`), SSAO, shadowed spots, fog (`look.md` §4.5 of the plan).

Every light is `light_bake_mode` Static (baked; not drawn in real time where a lightmap covers it); no shadows. The
`house` command writes `lights/<level>.tscn` (a level's lights in plot coordinates) and `zones/<zone>.tscn` (the
zone's room scenes, the level pieces standing in them, its lights, and as `Above` the next level's rooms over it: the
floor slabs that are the zone's ceiling; where the zone's rooms lie under the yard, which the generator gives no
floor, `Above` also holds `Cover_<n>`: bake-only concrete floor tiles at the next level's height, so a basement room
outside the ground floor's footprint does not bake under open sky). A bake needs the editor (below).

### Baking a zone

Godot 4.7.2 bakes a LightmapGI only in the editor, with a window:
- `LightmapGI.bake()` is not exposed to scripts (the bake lives in the C++ editor plugin);
- a `--headless` editor has no GPU device and reports that lightmap baking is not supported;
- an exported project cannot bake.

So there is no stock headless route (Q22 option C; a forum answer for 4.5.1 says the same:
https://forum.godotengine.org/t/is-it-possible-to-bake-lightmapgi-node-using-headless-godot-editor/129607). The only
route without a window would be a custom engine build that exposes `bake()`, which is installing a tool: the
engineer's yes.

#83a proved the route in a raw lab project (`D:/prime-art-raw/house/83a/godot`); #83 moved it into this repo as
`house --bake` (`tools/runner/house_bake.py` the pure parts, `tools/runner/commands/_house_bake.py` the driver,
`godot/house/zone_build.gd`, `godot/house/bake_shots.gd`, the `godot/addons/lmbake` editor plugin):

```
tools/run.sh house --bake ZONES [--preset high|low] [--grid] [--merge] [--no-bake] [--review DIR]
```

1. `house` writes the zone scenes into `godot/import/house` (so `--bake` refuses `--out`); the kit and prop GLBs the
   zone scenes instance are staged and imported: the kit with `meshes/light_baking=1` (its own UV2 is kept), the
   props with `light_baking=2` and a 0.2 m texel (Godot unwraps their UV2).
2. `zone_build.gd` (headless) flattens a zone into `res://import/house/bake/<zone>_<tag>.scn` with a LightmapGI from
   `[bake]`; a kit mesh's `lightmap_size_hint` is texel / `uv2_per_m` (the kit's `pieces.json`), so the presets
   differ only in the texel. `Above` (the zone's ceiling) bakes its floor slabs at the full texel and its other
   pieces at a tenth (they only occlude). `--merge` welds each room level's floor tiles of one kind into one mesh and
   unwraps it (one lightmap island per floor instead of one per tile). Meshes without UV2 stay Dynamic.
3. The editor bakes it: Godot opens the project with the `lmbake` plugin (`-- lmbake=<scene>`; without that argument
   the plugin does nothing) in a 1280x720 window at `-30000,-30000` (off-screen, never minimized); the plugin presses
   the LightmapGI's bake button, answers the file dialog, saves and quits. `house --bake` refuses this step outside
   00:00-08:00 local unless the manager wrote a daytime grant (`<raw>/research/2026-10-06-locations/lab/
   editor_window.txt`, `until YYYY-MM-DD HH:MM`, the lab runner's rule); agents never write that file.
   `--no-bake` stops after step 2 and runs by day.
4. With `--review DIR`, `bake_shots.gd` (an off-screen window) shoots each zone's real-time row (the first scene
   without its lightmap, the lights dynamic) and its baked rows from two E1 cameras (a room corner at 1.6 m across to
   three quarters of the room) and one seam camera (level along the first room's middle line from 1 m inside its north
   wall: ceiling and floor tiles in frame, never inside a wall); into `DIR`: the frames, `sheet.png` (about 1280 px
   across), `measures.json` and `numbers.md` (L* mean, the share under L* 20, C* p90 per frame, as the house lab
   measures; each baked row's L* against real time). Zones with review rooms: ground, basement, upper.
5. `--grid` bakes a zone once per variant: texel 8 / 12 / 16 per m x the denoiser on / off x bounce energy 1.0 / 1.5,
   tags `t<texel>_d<0|1>_e<energy x 10>` (`_m` with `--merge`). Twelve variants of the ground floor are about 12
   editor runs of 21-22 s plus the builds: well under half an hour.

Every Godot run takes the heavy-run lock (`common.heavy_lock`), one at a time; a run that waits for it is normal. The
whole command can pass 180 s: an agent starts it in the background with its log under `tools/out/`. Bakes are night
jobs: a zone is prepared by day (`--no-bake`) and baked in the next night run.

### The numbers of #83a

From `D:/prime-art-raw/review/house/83a/numbers.md` (2026-10-10, bare rooms of #75a, kit v2, RTX 4060, quality high,
3 bounces, denoiser on, bounce energy 1.5):

| zone | preset | texel/m | meshes | lights | M texels | bake s (editor run s) | lightmap MB |
|---|---|---|---|---|---|---|---|
| basement | high | 8 | 948 | 55 | 0.77 | 4.6 (22) | 1.9 |
| basement | low | 4 | 948 | 55 | 0.20 | 4.0 (21) | 1.2 |
| ground | high | 8 | 478 | 34 | 0.40 | 4.3 (21) | 1.7 |
| ground | low | 4 | 478 | 34 | 0.10 | 4.2 (21) | 0.9 |

- A bake takes seconds and is not texel-bound (the editor's start dominates); overlapping geometry is the slow case
  (63-577 s when every piece stood at the origin). The six zones together: about 9 MB High, 5 MB Low.
- One bake per zone works; two zones side by side at the stairs showed no visible jump, but one of that row's cameras
  stood inside a wall, so the zone seam is not yet called clean.
- 3-4 fixtures reach a camera inside one zone (at most 4), 7-10 at a seam of two zones: the High preset's real-time
  glow can stay at the nearest 4. Draw calls: 19 (basement) and 31 (ground) per frame in bare rooms, 54 with two zones.
- The verdict: GO for one bake per zone at night; NOT YET for the look: the baked rooms are flatter than real time
  (the lamps' ceiling pools are lost), with per-tile seams on the modular ceilings and floors and diagonal triangle
  blotches on the floors. The kit gives every face its own UV2 island (`docs/kit.md`): at 8 texels per m a 2 m floor
  tile's top face gets about 16 texels across, so each tile bakes and filters on its own. #83's grid (`--grid`, and
  `--merge` for one island per floor) measures which of texel, denoiser, bounce energy and merged floors close the
  gap.
