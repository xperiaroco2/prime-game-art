# The breaker board: handoff to the game

The ship's breaker board, the shells (art#263's stations): an octagonal bronze board 1.6 m wide on a graphite wall
plate, its frame from 0.52 to 1.314 m over the floor, the red problem beacon's top at 1.404 m, 0.31 m deep with every
shell closed. Four bays, left to right red, yellow, green, blue (centres at u -0.504, -0.168, 0.168, 0.504 m): in
each a crystal core glowing cyan behind an enamel shell on a bottom hinge, a lamp over it, cyan strips either side;
two cable loops under the frame into the wall (lowest at 0.178 m). Built from code: `tools/blender/board_run.py`
(the sizes in `tools/blender/board_dims.toml`, from the drawing in cm, prime-game-design 6b0e83e).

## Files

| File | What |
|---|---|
| `export/breaker_board.glb` | The nodes below; the plain-PBR fallback (all on) |
| `export/board.gd` | The look: `apply(model)` puts the materials on and adds the beacon's light; the states |
| `export/board_metal.gdshader` | Bronze and graphite with the bright chamfered edges (UV0 u) |
| `export/board_core.gdshader` | The crystal cores' glow (kin to the energy crystal's core) |
| `source/breaker_board.blend` | The Blender model |

Keep the three look files together (`board.gd` preloads the shaders by relative path).

## Nodes

| Node | What |
|---|---|
| `board_body` | Everything fixed: plate, border, panel, bays, hinge brackets, holders, lamp rings, beacon collar, strips, cables. Colliders `board_col0` (the board, 0.28 deep), `board_col1`, `board_col2` (the cable loops), `board_col3` (the beacon) |
| `shell_red`, `shell_yellow`, `shell_green`, `shell_blue` | The four leaves. Origin on the hinge axis: (u, 0.677, 0.25) in the board's frame (glTF: x across, y up, +z out of the wall). Rotation about local **X**: 0 closed (on), **+110 degrees tripped** (the top falls forward and down, out to 0.61 m from the wall, its lowest point 0.539 m over the floor). Each has its convex collider `shell_<colour>_col` as its child, so it turns with it |
| `core_<colour>` | The fixed crystal core behind each shell (material `board_core`; `board.gd` gives each its own copy) |
| `lamp_<colour>` | The lamp's lens over each bay (`board_lamp`, each its own copy) |
| `beacon` | The red dome (`board_beacon`) |

## States (`board.gd`)

```gdscript
const Board = preload("board.gd")
var look: Dictionary = Board.apply(model)   # all on: shells closed, lamps green, beacon off
Board.set_shell(look, 1, 1.0)    # the yellow shell tripped (0..1 turns it on its hinge; the player lifts it back to 0)
Board.set_on(look, 1, false)     # its lamp dark; set_lamp(look, i, 1) yellow while switching on, 2 green
Board.set_problem(look, true)    # the beacon and its red light: on while any shell is tripped
Board.set_core(look, 1, 1.0)     # a core's glow (1 full, the default)
```

The build turns every shell through its whole trip in tenths: no triangle crosses the body, a core, a lamp or a
neighbour (`report.json` `sweep_check`). The sparks, the arcs and the smoke at a tripped core are the game's: their
point is the core's centre, (u, 0.872, 0.18).

## Placement

On both breaker spots (`layouts/ship/ship.toml` `[[stations.spot]]`): u 0 on the spot, its h 0 on the deck
(floor_h 1.2), turned about Y so its +Z is the spot's normal, and **moved 0.07 m out along the normal** from the
spot's `at` (`report.json` `placement`, `mount_d_cm`). The spot's `at` lies on the corridor wall's face plane (its
seams), and the wall's pillow panels stand 4.4 to 7.0 cm proud of it inside the board's outline: the plate's back
rests on their crowns, and the graphite mount block behind it (and the cable clamps) reaches 0.075 m back, 0.005 m
into the wall's body, so no gap shows. The wall stands vertical to 1.45 m over the deck; the beacon's top is at
1.404 (measured by rays on the built ship, board-2).

| Spot | Plan (x, y) | Normal | Yaw (deg) |
|---|---|---|---|
| `breaker_e` | (6.6638, -0.9019) | (-0.1506, 0.9886) | -8.66 |
| `breaker_w` | (-6.6638, -0.9019) | (0.1506, 0.9886) | 8.66 |

Step 1's "beacon inside the wall" was its review scene, not the ship: it stood the board on a ship build made
before the raise (deck at 0.6 m), 0.6 m above that deck. The review now uses a raised build and refuses one whose
deck is not `floor_h`.
