# The House map as data

The House map (map request #73, design doc `docs/design/house-map.md` in the game repo) is assembled from layout
data, not hand-placed scenes, so the layout can change after playtests. Art #75 built the layout engine and the shell;
later packages add dressing data (`layouts/house/dressing/`, #75b) and only regenerate.

## Files

| File | What |
|---|---|
| `layouts/house/house.toml` | Settings: the kit spec, the kit folder under the raw folder (`kit_dir`, the one setting to switch kit v1 to v2), the `res://` paths of the pieces and scenes, the level order |
| `layouts/house/{basement,ground,upper,attic,roof}.toml` | One level each: `floor_y`, the default wall family, the house `footprint`; `[[rooms]]`, `[[doors]]`, `[[windows]]`, `[[holes]]`, `[[stairs]]`, `[[placeholders]]` |
| `tools/runner/house_layout.py` | Load, validate, plan (choose the pieces), write the scenes |
| `tools/runner/commands/house.py` | The `house` command |
| `tools/tests/test_house_layout.py` | The rules, the plan's conventions, the design doc's 35 rooms and the game's greybox marker names |

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
- The pitched roof, gable windows, chimneys and the front porch wait for kit v2 (#86, #74b): named `Placeholders`
  markers in the attic, roof and path scenes (`size` in metres for the review box).
- The main stairs' foot (not in the doc): the 6 m flight fills the 6 m stairs room, so its foot sits against the
  hallway wall and a 1.4 m capsule cannot step onto it from the doc's door at (32, 36). A second door from the hallway
  at (27, 36) opens straight onto the foot, marked `placeholder` (the game's greybox has no marker for it: the
  greybox check skips placeholder doors). Options: a U-turn of two half flights, or a 5 m steeper flight (kit v2).
