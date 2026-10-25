# The ship's crystal socket: handoff to the game

The wall socket that holds one energy crystal (art#263's stations), four of them on the hall's walls. Not yet approved
by the engineer: the look is in review (the PR's open questions: MOUNT 140 or 120, the pull-out, moving claws).

## Files

| File | What |
|---|---|
| `export/crystal_socket.glb` | One mesh `crystal_socket` in five surfaces (`socket_bronze`, `socket_graphite`, `socket_cyan`, `socket_amber`, `socket_lamp`), the triangles in `report.json`; convex colliders `crystal_socket_col0..4-convcolonly` (Godot makes them static bodies; none round the lamp's dome, none in the crystal's room); the empty `crystal_anchor`. Front +Z (out of the wall), Y up, metres. Origin on the wall's face at the hall's floor level, under the crystal's axis. Its materials are a plain-PBR fallback of the charged state (the lamp unlit) |
| `export/socket.gd` | The look: `apply(model)` puts the materials on by their glTF names and adds the lamp's red light; `set_state(look, state)`; `seat_crystal(crystal_look)` |
| `export/socket_metal.gdshader` | The bronze and graphite: the start console's `console_metal.gdshader`, unchanged |
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
**The pull-out is straight out along the anchor's +Z**: nothing of the socket is in the way (checked in 2 cm steps to
30 cm). After `Crystal.apply(crystal)`, call `Socket.seat_crystal(crystal_look)`: the crystal's own light then skips the
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
(`look["lamp_light"]`, an OmniLight3D at the dome, 1.6 m range, no shadow). The strips and the amber windows stay lit
in every state. The claws are fixed (whether they move is still open).

## Height

MOUNT is one number, `[mount] h` in `tools/blender/socket_dims.toml`; the engineer may still lower it to 120 cm.
A rebuild moves the whole socket and the anchor with it; the placement above does not change.
