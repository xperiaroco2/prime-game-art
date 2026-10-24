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
| `export/start_console.glb` | One mesh, nine surfaces by material name; the plain-PBR fallback (idle) |
| `export/console.gd` | The look: `apply(model)` puts the materials on and adds two small lights; the states |
| `export/console_metal.gdshader` | Bronze and graphite with the bright chamfered edges (UV0 u) |
| `export/console_signal.gdshader` | The stage strips and the order lamps (their index in UV0 v) |
| `export/console_holo.gdshader` | The hologram's lines and shell and the light column: additive, both sides, no depth write |
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
