# The ship's crystal charger: handoff to the game

The charger where a player recharges a spent energy crystal (art#263's stations), one on each lens room's aft wall:
a squat stepped bronze dome on four long legs like the ship's landing legs (the engineer's pick of 2026-10-25,
prime-game#1095 comment 6401197371). Not yet approved by the engineer: the look is in review (the PR's open
questions).

## Files

| File | What |
|---|---|
| `export/crystal_charger.glb` | The body `crystal_charger` (one mesh: `charger_bronze`, `charger_graphite`, `charger_amber`, `charger_cyan`, `charger_steel` for the legs' piston rods) and its leaves: `carrier` (the bronze cup under the crystal, its cyan ring), `track_ring` (bronze, the cyan channel, the inner prong pair and their electrodes), `button` (`charger_lens`), the empty `crystal_anchor` under `carrier`. Convex colliders `crystal_charger_col0..6-convcolonly` (the base, the two outer prongs, the four legs; Godot makes them static bodies) and `track_ring_col0..1-convcolonly` (the inner prongs, turning with the ring). Front +Z (out of the wall), Y up, metres. Origin on the floor at the wall's face under the crystal's axis. Its materials are a plain-PBR fallback |
| `export/charger.gd` | The look and the moving parts: `apply(model)`, `set_state`, `set_carrier`, `set_ring`, `set_pressed`, `seat_crystal` |
| `export/console_metal.gdshader` | The bronze and graphite: the start console's shader, the same file (keep one copy beside both scripts) |
| `source/crystal_charger.blend` | The built model (rebuilt from code: `tools/blender/charger_run.py`) |
| `report.json` | Size, triangles per object, pivots, the anchor, colliders, the clearance checks, glTF-Validator, GPU cost |

## Placement: the two spots

`layouts/ship/ship.toml` `[[stations.spot]]` `renewer_e`, `renewer_w`: `at` is the point on the lens room's wall
(plan x, y; Godot x, z), on a vertex of its 12-sided wall, and `normal` the direction into the room. Put the charger's
origin at `(at.x, floor_h, at.y)` (the deck, `floor_h` 1.2 m) and turn it `rotation.y = atan2(normal.x, normal.y)`:

| Spot | at | normal | yaw (deg) |
|---|---|---|---|
| `renewer_e` | (10.2686, 3.2369) | (0.1129, -0.9936) | 173.52 |
| `renewer_w` | (-10.2686, 3.2369) | (-0.1129, -0.9936) | -173.52 |

The charger is round and stands clear of the wall: the crystal's axis is 53.5 cm out, the base's widest circle
(Ø 100.4) 2.3 cm off the wall's two facets (they fold 10.98 degrees toward the room either side of the vertex), the
back legs' pads 3.4 cm. It reaches 105.3 cm into the room (the front pads), more than the spot's `depth_m` 0.9: a
player at the button stands about 1.45 m out and still has 2.17 m of free floor behind (the layout's `pass_m` 1.6).

## The leaves

| Node | Pivot (model frame, m) | Moves |
|---|---|---|
| `carrier` | (0, 0.974, 0.535): the middle of the cup's rim, on the crystal's axis | up `RISE` 0.06 and round its Y axis: `set_carrier(look, rise01, angle)` |
| `crystal_anchor` | under `carrier`, 2.3 cm below its rim, in the cup's pit: the crystal's tip | parent the crystal here with an identity transform (`seat_crystal`) |
| `track_ring` | (0, 0.94, 0.535): the deck on the crystal's axis | round its Y axis: `set_ring(look, angle)`; 0 = the inner prongs left and right |
| `button` | (0, 0.759, 0.9907): the lens's face | 1 cm in along -Z: `set_pressed(look, on)` |

The outer prongs and the legs are part of the body. The lightning (arcs from the inner prongs' electrodes into the
crystal while it charges) and the crystal's glow are the game's.

## The crystal

```gdscript
const Charger = preload("charger.gd")
const Crystal = preload("crystal.gd")
var look: Dictionary = Charger.apply(charger)
var crystal_look: Dictionary = Crystal.apply(crystal)
Charger.seat_crystal(look, crystal, crystal_look)  # on the anchor; its light skips the charger
Charger.set_state(look, "charging")                # then each frame: set_carrier(look, rise01, a), set_ring(look, b)
Charger.set_state(look, "charged")                 # the carrier back down, the cyan full
Charger.set_state(look, "idle")                    # no crystal or not charging
```

The charger's meshes draw on render layer 20 alone (`charger.gd` `CHARGER_LAYER`): `seat_crystal` leaves that layer out
of the crystal's light's cull mask, which a few centimetres away burns the bronze white. The socket uses the same
layer for the same reason; keep layer 20 free for these, or change both. While charging, the charger's own soft cyan
light (`look["glow"]`) lights the deck and prongs instead.
