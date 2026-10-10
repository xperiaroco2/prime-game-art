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
| `layouts/house/routes.toml` | The design doc's routes (§7) as waypoints for the walk, with the doc's lengths and times (#78; "Routes" below) |
| `layouts/house/basement_review.toml` | The basement's review pictures: lamp stand-ins per fixture id, exposure, ambient, the shots and the far edge's L* (#78) |
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
tools/run.sh house [--check] [--out DIR] [--layouts DIR] [--walk DIR] [--basement DIR]
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
- a 3 x 3 m pad under each walk end that has no floor (the yard; #81a builds the real ground), cut back from the
  holes of its level (`house_layout.clip_pad`: a pad over the outdoor stairwell jammed the climb);
- a control: the 1.5 m capsule must stop at the first door (the colliders are there);
- every `[[loops]]` entry of a level (a design-doc route as `points` = [x, height, y], heights absolute): walked at its
  `speed` (the game's 4.5 m/s) for at most 40 s and timed against the doc's `doc_s` (`within_1s` in `walk.json`;
  `house_layout.loop_length` gives its plan length beforehand). The one loop is the second floor's (#76, below);
- the design doc's routes from `layouts/house/routes.toml` ("Routes" under the basement below), at their own speed.

A walk arrives when it gets within 0.3 m of its last point at that point's height (0.15 m); it gives up after 30
ticks without moving. Into `DIR`: `walk.json` (each walk's end, time and verdict; draw calls, objects and primitives
per view; mesh instance and body counts), the eye-height stills (1.6 m), `aerial.png`, `plan_ground.png` (the ground
floor from above, the other levels and the ceilings hidden, a label per room), `sheet.png` (1280 px wide) and
`exterior.png` (the four sides at dusk from 1.7 m eye height outside the plot, 1280 px wide; the kit's own colours, the
`[[placeholders]]` as see-through orange boxes of their `size`, from the marker up). The lamps
(one warm omni per room, no shadows) and the dusk sky only light the shell for review; they are not the house's light.

`--basement DIR` stages and imports the same way, then runs `godot/house/basement.gd` off-screen for the basement's
review (#78; "The basement" below). With `--walk` in the same run it goes after the walk and shows its route times.

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
  itself does not reach is a note: the pantry stairs' top (its target, half a metre past the top, lies within the
  capsule's radius of the stairwell's railing; the walk climbs it).

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

### The second floor (#76)

Seven files (`bedroom`, `kids_room`, `landing`, `study`, `bathroom`, `guest_room`, `balcony`) with the inventory's
props and fixtures (`tools/tests/test_house_upper.py`). The study's `Printer` station (40, 29) is the desk with the
computer set and the photo printer on its top (h 0.75) and the chair, all tagged `station = "Printer"`. The balcony's
sitting set stands at its west end and the pots on the north rail, so a 2.3 m lane runs from the landing door to the
external stairs' top. Defaults: Q21 B (the inventory's counts; the rocking horse is hero class and not made; a second
nightstand in the guest room so each table lamp has one), Q6 (the straight flight, its foot on the yard at y 15).

The doc's loop (dining room, stairs, landing, balcony, external stairs, terrace, dining room: 46 m, 10.2 s) is
`[[loops]]` in `upper.toml`. As built it is 62.6 m in plan (`house_layout.loop_length`), about 13.9 s at 4.5 m/s:
the main stairs' U-turn adds about 4 m, the route passes south of the dining set, and the straight balcony flight lands
north on the yard, so the route steps off its foot and goes back south round its west side, under the balcony (the east
side is too narrow for the 0.68 m capsule beside the terrace's corner planter). Q6's U-turn option (two runs in the
same 2 x 6 m rect, the foot on the terrace under the balcony) is an estimate, not walked: 54.3 to 56.1 m with
`loop_length` for a half-landing at y 18.5 or 17.6 (12.1 to 12.5 s), still over the doc's 10.2 s; the engineer decides.

The walk's second-floor proof is `upper.png` (1280 px): `plan_upper.png` (the second floor from above, the attic and
roof hidden, a label per room) beside `balcony_loop.png` (the loop's waypoints as a ribbon over the same top-down,
orange on the ground, cyan upstairs, the walked seconds in its title), then the upper rooms' `room_<id>.png` and the
balcony stairs. `rooms.png` keeps the ground floor's rooms.
## The basement (#78)

Eight dressed rooms (`layouts/house/dressing/{storage,darkroom,corridor,boiler_room,generator_hall,pump_room,
switch_room,passage}.toml`): 147 props, among them every station's task prop and #82's room props (boiler, pump,
water tank, three switchboards, three cable drums, two enlargers, two tray tables), and the inventory's 55 light
fixtures (meshes only; #83a lights them). Kit pillars are `[[pieces]]` in `basement.toml`; the dressing check counts
them as obstacles (`house_dressing.PIECE_HALF`).

`tools/runner/house_basement.py` (run by `house`, rows in `tools/out/house/basement.json`; tests
`tools/tests/test_house_basement.py`) checks the level design on the plan at eye height (1.6 m):
- the intended dead ends (the darkroom, the boiler, pump and switch rooms) have exactly one door and no stairs;
- each switch is in sight from every door of its room (no prop taller than the switch box's 1.1 m on the line);
- the generator hall's sight lines from the passage door (1 m in) to the other four doors, the generator and the
  four corners, and from each door to the generator; pillars and props taller than 1.6 m block. Tonight's clearances:
  corridor door 2.29 m, boiler room door 0.94, pump room door 1.75, switch room door 2.0, generator 5.11, corners
  1.24 (NW), 3.08 (NE), 0.8 (SW), 3.12 (SE); from the doors to the generator 1.52 to 4.8 m.

Routes (`layouts/house/routes.toml`, walked by `house --walk` at the doc's 4.5 m/s; 2026-10-10, walk5, on main
with the second floor and the light kit, the pantry stairs a U, the garage's back door at (65, 34)); every route
arrives and is within the 1 s tolerance:
- wine (storage's wine rack -> pantry stairs -> dining table, the end at (33.3, 27), the capsule's front 2 m from the
  table; the doc 26 m, 5.9 s): 6.47 s (+0.57 s), 27.97 m on the plan.
- garage (storage's boxes -> hall -> passage -> outdoor stairs -> workbench; 60 m, 13.4 s): 13.42 s (+0.02 s),
  59.14 m.
- switches D -> B -> C -> A (105 m, 23.4 s): 23.67 s (+0.27 s), 108.4 m.

The doc counts a change of level as 6 m in a straight line; the walk climbs the real flights: the pantry U is about
11 m of stairs and its landing turn, the outdoor U about 8.4 m a level, and each 1.4 m door is 1 m of straight
approach. The routes still fit because the walk's speed is over the plan and the flights' runs are short on it. The
manager waives the wine time if a later change puts it over 1 s while it still arrives (the U stairs' real path);
garage and switches must stay within 1 s. The waypoints are not bent to fit.

Review pictures (`house --basement DIR`, `godot/house/basement.gd`, settings in `layouts/house/basement_review.toml`):
a real-time omni at each of the 55 fixtures by its id (cool pendants and cage lamps, warm bare bulbs, red
safelights: Q23 B), a faint cool ambient and one fixed exposure for the zone (Q24 A); nothing baked and not the light
pass (#83a). A shot per room from 0.3 m inside a door at 1.6 m, the hall from the passage and from the switch room,
the basement from above with labels and the last walk's route times (`tools/out/house/routes.json`), and the median
L* of each shot and of the hall's far (west) wall from the passage door, which must stay above 12 (2026-10-10: 42.4).
Rooms outside the house's footprint (the generator hall, the pump and switch rooms, the passage) have no slab over them
yet (no layout level is there; the yard's ground, #81a, has to close it), so their shots look up into black.

Defaults used (for the engineer; data, easy to change):
- The hall's pillars: 4, not the inventory's 8 (an 8 m grid does not fit 18 x 20 m), at (44, 26), (54, 26), (44, 38)
  and (54, 38): a 10 x 12 m grid 4 m off the walls, the best of a grid search for the longest clear sight lines.
  Storage keeps 4 at (19, 23), (25, 23), (19, 28), (22, 25.5) (the fourth moved off the pantry stairwell).
- The outdoor stairs (`outdoor_stairs` in `ground.toml`, a placeholder): a U of two `stairs_outdoor_half` and the
  landing in a 4 x 4 m stairwell at (62, 28), entered from the south 2 m from the garage's back door (65, 34; the doc's (63, 34), moved 2 m east so the
  garage route does not walk back west): down
  north to the landing on the passage's north wall, then down south to the passage, the foot at (63, 32). The doc's
  stairwell at (62, 29) leaves 1 m between the foot and a passage wall whichever way it is entered, too narrow for
  the 1.36 m capsule; the zone keeps the doc's rect. This file owns the stairwell: #81's outdoor plot
  (`layouts/house/outdoor/plot.toml` `[stairs]`) no longer holds a rect or entry of its own (it had (62, 29) from the
  north) and reads the hole's rect and the upper flight's climb from here (`house_outdoor.house_stairs`), so the
  yard's U, its railings and pit stand-ins sit where the walk climbs. The passage has no slab over it (the yard is not a floor): the
  yard's ground (#81a) must close it round the stairwell.
- Switches on a wall in sight from the door: A on storage's west wall, B on the boiler room's west wall, C and D on
  the east walls; a cage lamp over each switch (its pool is #83a's); the generator's front 0.65 m south of its
  marker; the darkroom's photo board faces its door.

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

- Q5, the pantry stairs: the option, a U of the kit's two half flights (art #78), in a 4 x 4 m stairwell in the
  pantry's north-west corner (hole x 24..28, y 24..28): the foot in storage at (25, 28), up north to the 4 x 1 m
  landing on the north wall, up south to the top at (27, 28) and the pantry's 2 m landing (y 28..30). Marked
  `placeholder`. The default, a straight flight with a 1 m top landing, did not let the 1.36 m capsule turn (the wine
  route jammed); a straight flight climbing south hit the capsule's head on the north wall's slab edge. The pantry's
  two jar shelves moved off the stairwell to the east and north walls.
- Q6: the balcony stairs run straight north, the foot on the yard at y 15.
- Q7 B: 16 windows on the ground floor, 16 on the second floor, 4 knee windows in the attic, 5 in the garage.
- Q9 B: leaves standing ajar at the front door, the terrace door and the garage side door; the greenhouse door is
  the kit's own leaf; open doorways elsewhere.
- The attic hatch: the kit's hatch tile puts the hole's centre on whole metres, at (28, 29) instead of the doc's
  (28, 28.5). Its ladder climbs south (#76): the foot on the landing at y 28.3; climbing north put the foot 0.3 m
  from the stairwell (y 30), where no one can stand.
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

The route used (#83a spike, raw project `D:/prime-art-raw/house/83a/godot`):
1. `house --out <project>/import/house` writes the zone scenes; the kit v2 GLBs are imported with
   `meshes/light_baking=1` so the kit's UV2 is kept.
2. `zone_build.gd` (headless) flattens a zone into one scene with a LightmapGI from `[bake]`; each mesh's
   `lightmap_size_hint` is the zone's texel per metre times its UV2 extent, so High and Low differ only in the texel.
3. The editor bakes it: the lab's `lmbake` plugin, started by `labrun.py godot ... --window 1280x720 -- --editor`
   (an off-screen window, never minimized). `labrun.py` refuses an editor run outside 00:00-08:00 local unless the
   manager wrote a daytime grant (`editor_window.txt`); agents never write that file.
4. Every lab Godot run starts inside the art runner's heavy-run lock (`common.heavy_lock`), one at a time.

Bakes are therefore night jobs: a zone is prepared by day and baked in the next night run.
