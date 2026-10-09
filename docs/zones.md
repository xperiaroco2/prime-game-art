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
view to within reach of every station. `placements(zone)` lists every piece (props and the kit's gazebo pieces) with
its Godot position and yaw for the assembly.

## Defaults used (the engineer's questions)

- Q17, the gazebo's look: default A, a hexagonal timber pavilion (the kit's) with string lights, a painted backdrop
  (ink blue, a low sun, gold and teal bands) and the pose screen. Adult, not childish: no fairground stripes.
- The gazebo's own entrance is the kit's open sector (2.54 m clear between posts); the plan's 4 m opening is the
  zone's railing gap at x 14, which faces it.
