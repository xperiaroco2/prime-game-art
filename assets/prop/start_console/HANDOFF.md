# The start console: handoff to the game

The ship engine's start console (art#263's stations): a round bronze and graphite pedestal, 1.2 m across and 1.1 m
tall, with the orange start button at hip height (its centre 0.814 m over the floor: the drawing's 0.854, lowered
4 cm on the engineer's review so its collar clears the joint under the rim), three stage strips on the rim, two cyan
strips either side of the button, the hologram emitter on top, and over it the hologram of the ship, made from the
built hull's own mesh at 1:16.3 (1.6 m across, its hall's disc 1.457 m over the floor, leaning 12 degrees nose down
toward the button). Built from code: `tools/blender/console_run.py` (the sizes in
`tools/blender/console_dims.toml`, the drawing in cm by `console_drawing.py`).

## Files

| File | What |
|---|---|
| `export/start_console.glb` | One mesh, thirteen surfaces by material name; the plain-PBR fallback (idle) |
| `export/console.gd` | The look: `apply(model)` puts the materials on and adds two small lights; the states |
| `export/console_metal.gdshader` | Bronze and graphite with the bright chamfered edges (UV0 u) |
| `export/console_signal.gdshader` | The stage strips and the order lamps (their index in UV0 v) |
| `export/console_holo.gdshader` | The hologram's lines and shell, the light column and the spin-up's parts (turbines, wiring, ring, countdown): additive, both sides, no depth write |
| `source/start_console.blend` | The Blender look (node group `console_state`) |

Keep the four look files together (they preload each other by relative path).

## Placement

On the ship's console spot (`layouts/ship/ship.toml` `[[stations.spot]]` "console": plan (0, 0.6), 1 m aft of the
hall's centre) on the deck, 1.2 m over the ground, turned 180 degrees about Y in the ship's frame, so its front (glTF
+Z, the button) faces the mouth (-Z) and the hologram's nose points the way the ship's does. Origin on the floor under
the console's middle. A collider: a cylinder of radius 0.6 m and 1.1 m tall (the hologram has none). The ship's
layout gives a floor station a 0.35 m footprint radius; this console's plinth is 0.6 m (the drawing's 1.2 m), so
its clear floor is the ship lane's to check.

## States

```gdscript
const Console = preload("res://.../console.gd")
var look: Dictionary = Console.apply(model)
Console.set_state(look, "idle")   # the button glowing, the first strip green (passed 1, no lamp lit)
Console.set_lit(look, 5)          # the order playing: lamp 5 bright, the others dimmed; set_lit(look, -1) stops
Console.set_passed(look, 2)       # a stage passed: two strips green (0..3)
```

The lamps: 0..3 the west wing from the hall outward (red, yellow, green, blue), 4..7 the east wing the same; a
breaker on a side's board maps to that wing's lamp of its colour. Animation (the order's timing, a pulse on the lit
lamp, the hologram's turn or flicker) is the game's: the look holds only the values.

## The engine's spin-up (art#263, step 1)

Four parts on the hologram, all values on the same mesh (prime-game#1095 comment 6392050112; GDD section 8):
the **turbines** (the three pods' lines and a fan at each pod's front), the **wiring** (a point at each station's
real place, `layouts/ship/ship.toml`'s spots, with a line to the turbines along the hall's wall and aft), the **charge
ring** (three stages of dashes round the hologram's hall disc, upright, so it reads from the throat and the
corridors) and the **countdown** (two seven-segment digits over the hologram, turned to each player's eye).

```gdscript
var look: Dictionary = Console.apply(model)   # apply() once the model is in the tree: its clock starts there
Console.set_calling(look, true)                # before the start: the turbines pulse orange every CALL_PERIOD (3 s)
var ph: float = Console.call_phase(look)       #   and the button glows; 0..1, 0 = the pulse's onset (the beep)
Console.set_calling(look, false)               # the start pressed
Console.set_spin(look, 1.2)                    # the fans, turns per second (each broken station halves it)
Console.set_charge(look, 0.4)                  # 0..1: the three strips fill as ONE bar (stage k is a third), the ring too
Console.set_station(look, "vent_e", "ok")      # the line lit and flowing toward the turbines
Console.set_station(look, "breaker_w", "broken", 2.5)  # blinks red 2.5 times a second (the first to blow fastest)
Console.set_countdown(look, 8.4)               # the nearest failure's seconds (rounded up); -1 hides it
Console.set_station(look, "breaker_w", "fixed")        # the line flashes back bright, then reads ok
Console.reset_spinup(look)                     # a new round: all at rest, the clock from 0
```

- Stations (`Console.STATIONS`): `socket_w`, `socket_e`, `socket_fw`, `socket_fe`, `breaker_w`, `breaker_e`,
  `vent_w`, `vent_e`. States: `off` (before the start: the point dim, the line still), `ok`, `broken`, `fixed`.
- Time: the spin-up's shaders read the console's own clock, a tween bound to the console (no `_process`); the game
  reads it with `Console.clock(look)`, the call's phase with `call_phase`. `set_clock(look, t)` stops it and sets it
  (recordings, tests). The fans keep their angle through a change of rate.
- The countdown turns orange in its last 5 s and red in its last 3, each second ticking; the game feeds it the nearest
  failure's own timer (the placeholders 10 s and 30 s), as often as it likes.
- What the look does not do: the timers, which station fails, the sound. The game calls the beep at `call_phase` 0.
- `set_state`, `set_passed` and `set_lit` work as before (`set_passed(n)` fills the strips to n thirds; it leaves the
  ring alone).
