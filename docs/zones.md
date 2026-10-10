# The chill zone and the photo gazebo: layout data

Art #81b (map #73) lays out the yard's two social zones as data, `layouts/house/outdoor/zones/chill.toml` and
`photo.toml`, read and checked by `tools/runner/house_zones.py` (pure Python; tests `test_house_zones.py`). The plot's
ground, fence and street are #81a's (`tools/runner/house_outdoor.py`), the house shell #75a's; this module touches
neither. Every number is the engineer's to change (the plan's sizes are his draft).

## The data

- Plan metres: x east, y south (the plot is 80 x 60 m, the street at y 60); Godot puts a plan point (x, y) at
  (x, height, y). `yaw` turns a prop's front (+Z) about +Y: 90 faces east, 180 north, -90 west; `face = [x, y]` turns
  it towards a point.
- `rect = [x, y, w, d]`: the zone (inventory.md section 4). `[[items]]`: `id`, `src` (`zones` or `tasks`: the prop
  specs, which give the size; `#87` and other packages: a placeholder with its own `size` until that package lands),
  `at`, `yaw` or `face`, `y` (a height, as on the gazebo's deck), `station` (the game marker, checked against the
  design doc's point).
- The photo zone adds `[opening]` (the walking approach through its low railing, 4 m at x 14, y 9..13),
  `[railing]` and `[gazebo]` (the kit's gazebo: centre, yaw, the post radius and heights). `gazebo_edge = k` hangs a
  strand between posts k and k+1 (0 is the open entrance, 3 the back).
- `[[views]]`: the review's eye points (1.6 m, from the walking approach) and where they look; the first is the walk
  check's start.

## The checks (`house_zones.check`)

Every piece's ground footprint inside the zone; the stations at the design doc's points (Grill (8, 50), Speaker
(12, 55), PoseScreen (9, 11)); the opening 4 m; the light fixtures' counts (inventory.md section 8: photo 4 strands
and 6 lanterns, chill 3 and 6); no two footprints on the same ground and none in the railing or the gazebo's posts and
rails (a pole set blocks only its poles, a hung strand nothing); a free walk for a 0.35 m-radius player from the first
view to within reach of every station. `placements(zone)` lists every piece (props, the kit's gazebo pieces and the zone railing's modules) with
its Godot position and yaw for the assembly.

## Defaults used (the engineer's questions)

- Q17, the gazebo's look: default A, a hexagonal timber pavilion (the kit's) with string lights, a painted backdrop
  (ink blue, a low sun, gold and teal bands) and the pose screen. Adult, not childish: no fairground stripes.
- The gazebo's own entrance is the kit's open sector (2.54 m clear between posts); the plan's 4 m opening is the
  zone's railing gap at x 14, which faces it.

## The command and the review assembly

```
tools/run.sh zones [--shoot DIR]
```

`zones` loads and checks both zones (pure Python, a second). `--shoot DIR` then assembles them for review: it stages
the zone props (`<raw>/props/zones/v1`), the task props (`<raw>/props/task/v1`: the grill, the speaker, the pose
screen) and the kit's gazebo and railing pieces (`<raw>/<kit_dir>` from `layouts/house/house.toml`) into
`godot/import/`, imports them headless and runs `godot/house/zones.gd` in a window placed off-screen (Godot takes the
heavy-run lock). The request (`commands/zones.py request()`, written to `tools/out/zones/request.json`) holds every
piece of `placements()` with its scene, or its `size` for a placeholder (#87's dressing: a grey box with its id), the
light sockets of every fixture (`light_<k>` from the props' builders), the views and the line-up.

- **Railing**: `railing_pieces(zone)` runs the kit's `railing_gazebo_2m`, then `_1m`, along each side of the zone's
  rectangle (local +X along the run, the module's post at its start), the opening left out; a `railing_gazebo_post`
  closes each run's free end (a corner is closed by the next run's first post).
- **Dusk, for review only** (not the game's lighting): a procedural dusk sky, a low cool sun from the west, a grass
  stand-in plane (#81a builds the ground), the kit's `set` pack on every `kit_set` surface, a warm omni light just under
  every fixture socket (`LIGHTS` in `commands/zones.py`: colour, energy, range per fixture) and the bulbs' emission
  raised three times.
- **Frames** into `DIR` (1600 x 900 each): every zone's `[[views]]` at 1.6 m (`<zone>_<view>.png`), `gazebo_pose`
  (the gazebo with the pose screen from its entrance), `photo_high` and `chill_high` (each zone from 6 m), `lineup`
  (the zone props in a row beside a 1.8 m capsule, with a key light); `sheet.png` (two to a row, 1280 px wide) and
  `zones.json` (draw calls and primitives per frame, the instance, light and proxy counts).
