# The ship's crystal socket: handoff to the game

The wall socket that holds one energy crystal (art#263's stations), four of them on the hall's walls. Not yet approved
by the engineer: the look is in review (the PR's open questions: MOUNT 140 or 120, the claws' opening angle).

## Files

| File | What |
|---|---|
| `export/crystal_socket.glb` | The body `crystal_socket` in six surfaces (`socket_bronze`, `socket_graphite`, `socket_cyan`, `socket_amber`, `socket_lamp`, `socket_bay`: the bay's floor) and the two claws `claw_r`, `claw_l` (bronze), each its own node with its origin on its hinge; the triangles in `report.json`; convex colliders `crystal_socket_col0..4-convcolonly` on the body and `crystal_socket_col5` / `col6-convcolonly` under `claw_r` / `claw_l` (they turn with them; Godot makes them static bodies; none round the lamp's dome, none in the crystal's room); the empty `crystal_anchor`. Front +Z (out of the wall), Y up, metres. Origin on the wall's face at the hall's floor level, under the crystal's axis. Its materials are a plain-PBR fallback of the charged state (the lamp unlit) |
| `export/socket.gd` | The look: `apply(model)` puts the materials on by their glTF names and adds the lamp's red light; `set_state(look, state)`; `set_claws(look, open01)`; `seat_crystal(crystal_look)` |
| `export/socket_metal.gdshader` | The bronze and graphite: the start console's `console_metal.gdshader` (the shared station metal; its socket-3 parameters default to the console's look, `socket.gd` `BRONZE_FINISH` sets the socket's) |
| `export/socket_bay.gdshader` | The bay's floor: dark, glowing cyan round a charged crystal (`set_state`) |
| `source/crystal_socket.blend` | The built model (rebuilt from code: `tools/blender/socket_run.py`) |
| `report.json` | Size, triangles, the anchor, colliders, the build's checks against the crystal, glTF-Validator |

## Placement: the four spots

`layouts/ship/ship.toml` `[[stations.spot]]` `socket_e`, `socket_w`, `socket_fe`, `socket_fw`: each `at` is the point
on the wall's face (plan x, y; Godot x, z) and `normal` the direction into the room. Put the socket's origin at
`(at.x, floor_h, at.y)` (the deck, `floor_h` 1.2 m) and turn it `rotation.y = atan2(normal.x, normal.y)`, so its +Z
is the normal:

| Spot | at | normal | yaw (deg) |
|---|---|---|---|
| `socket_e` | (1.800, 3.112) | (-0.4561, -0.8899) | -152.9 |
| `socket_w` | (-1.800, 3.112) | (0.4561, -0.8899) | 152.9 |
| `socket_fe` | (3.4261, -2.3578) | (-0.8682, 0.4961) | -60.3 |
| `socket_fw` | (-3.4261, -2.3578) | (0.8682, 0.4961) | 60.3 |

The back plate lies flat on the wall's face (0 to 6.7 cm); the claws' tips are 22.2 cm out.

## The crystal: `crystal_anchor`

`crystal_anchor` is the crystal's pivot: `energy_crystal.glb`'s origin is its tip, so the anchor sits at the tip, on
the crystal's axis 17 cm out of the wall, at MOUNT - 17.45 cm (MOUNT, the crystal's middle, 140 cm above the floor:
the anchor at 1.2255 m). It has no rotation: parent the crystal there with an identity transform and it stands in the
socket, its front +Z out of the hall's wall, its tip on the collar and its cap between the claws (0.3 mm clear a side).
**The pull-out is straight out along the anchor's +Z**: nothing of the socket is in the way (checked in 2 cm steps out
to 30 cm, with the claws closed and open). `Socket.PULL_CM` (15 cm) is how far out the crystal must slide to be free
of the socket. After `Crystal.apply(crystal)`, call `Socket.seat_crystal(crystal_look)`: the crystal's own light then skips the
socket (the socket's meshes draw on render layer 20 alone, `socket.gd` `SOCKET_LAYER`; the crystal's light leaves that
layer out of its cull mask), which it otherwise burns white-cyan. Keep render layer 20 free for this, or change
`SOCKET_LAYER`.

## The states

```gdscript
const Socket = preload("socket.gd")
var look: Dictionary = Socket.apply(socket)
Socket.set_state(look, "charged")   # a charged crystal in it: the red lamp off
Socket.set_state(look, "spent")     # a spent crystal (Crystal.set_charge(crystal_look, 0.0)): the lamp lit red
Socket.set_state(look, "empty")     # no crystal: the lamp lit red
```

The lamp is the `socket_lamp` surface: `set_state` sets its emission (`look["lamp"]`) and its light
(`look["lamp_light"]`, an OmniLight3D at the dome, 1.6 m range, no shadow). The bay's floor (`look["bay"]`) glows
cyan round the crystal in "charged" and is dark in "spent" and "empty" (the crystal's own light skips the socket, so
the socket carries its glow). The strips and the amber windows stay lit in every state.

## The claws

```gdscript
Socket.set_claws(look, 1.0)   # open: each claw turned Socket.CLAW_OPEN_DEG (25) up and outward round its hinge
Socket.set_claws(look, 0.0)   # closed on the crystal's cap
```

`claw_r` and `claw_l` turn round their own local Z (the wall's normal): `claw_r` +angle, `claw_l` -angle, rotation 0
closed. Their hinges sit on the neck block at u +-5.37 cm, h 162.79 cm (the drawing's HINGE, prime-game-design
1df9a42) at MOUNT 140; like every height of the socket they move with `[mount] h`. The game animates `open01` and plays the sounds; the drawing's timing: open in 0.25 s with a metal sound
as the crystal is pulled, closed in 0.15 s with a click as a charged one is seated. The drawing's 35 degrees was a
placeholder: each claw's jaw finger (beside the cap, behind the arm) cuts the bay's lip past 28 degrees
(`report.json` `checks.swing_clear_deg`), so the built opening is 25; the crystal slides out between the open claws
with nothing in its way.

## Height

MOUNT is one number, `[mount] h` in `tools/blender/socket_dims.toml`; the engineer may still lower it to 120 cm.
A rebuild moves the whole socket and the anchor with it; the placement above does not change.
