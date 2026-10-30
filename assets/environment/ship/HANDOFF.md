# The ship: handoff to the game

The empty ship of art#263 (a wide metal manta at night: the hall, the throat and its ramp, two corridors, two lens tip
rooms, the vault; the throat walls with the gill set) as the game's package, for prime-game#1225 (the engine) and #1285 (boot into it). Written by
`tools/run.sh ship --out <raw>/ship/v5/lobby/pieces --export <raw>/ship/v5/export/v3` (2026-10-30, main at ca23058d) (art#335, `docs/ship.md` "The export"); the files and their
hashes are in `manifest.toml` and the package's `package.json`. The GLBs are not committed here: the package lives in
the raw folder until approved.

## Files (the game's tree)

| Path | What |
|---|---|
| `assets/environment/ship/<piece>.glb` | the 189 pieces, each with a minimal `.import` (11.2); colliders are the GLBs' `-col` trimesh hints |
| `assets/environment/ship/*.gdshader` | the shared metal, the star sky, the lens bronze (`console_metal`) and the charger's traces, arcs and conduits (art shaders shipped as files) |
| `assets/environment/ship/materials/*.tres` | one `metal_<name>.tres` per shared metal, `night_sky.tres`, `night_env.tres` |
| `levels/ship/ship.tscn` | the level: `Ship` > `Pieces`, `Environment`, `Lights`, `Probes`, `Clearing` (`Pieces`, `Lights`, `Ground`), `Stations`, `Markers` |
| `package.json` | every file with SHA-256 and bytes, the spots, the spawn, the questions |

205 files, 12.1 MB. Copy only the files `package.json` lists: the export folder also holds the art check's own
`_check/`, `project.godot`, `lib/`, `.godot/` and the `.uid` files Godot writes, none of them for the game. No GDScript: the look the art sets by code is saved in the scene as
overrides inside the pieces' instances (each piece an editable instance, 11.2's rule).

## The lobby: the ship without the clearing (art#356)

Everything round the ship that is not the ship is one node, `Ship/Clearing`:

- `Clearing/Pieces`: 534 placements of 34 pieces (the ground, pines, bushes, ferns, moss, litter, logs,
  stumps, rocks, the dirt patch and path, the ground lamps, the party posts and string);
- `Clearing/Lights`: 41 lights (the ground lamps' pools, the party string, the treeline camp lights and the lamp in
  front of the ramp, the pines' fill, and the glow cells only the party bulbs light);
- `Clearing/Ground`: the world boundary at y 0 (a `StaticBody3D`, layer 1).

The lobby instances `ship.tscn` and frees the node (`$Ship/Clearing.queue_free()`, or deletes it in an inherited
scene). Hiding it is not enough: `Clearing/Ground`'s collider stays on. The ship itself (hull, legs, ramp, entry
tunnel) stays under `Pieces`, and its own outside light (the landing and edge spots, the rim, the key, the tail lamp)
under `Lights`. The landing legs' feet stand at y 0: the lobby's floor goes there. `package.json` "clearing" lists the
node and its pieces. The closed state (the ramp raised, the mouth shut) is not in this package yet: its look waits for
the engineer's pick (art#263); until then the lobby shows the open ship.

## Placement

The scene's origin is the ship's plan origin on the ground (the clearing's ground piece at y 0; without the clearing, the legs' feet); Godot x = plan x,
z = plan y, +Z aft; the deck is at y 1.2 m. `metadata/size_m` is the plan's width and length with the nozzles;
`metadata/deck_h` the deck. `Markers/Spawn` stands at the ramp's foot ([0.0, 0.0, -14.0]), turned
180.0 degrees: its +Z (aft) looks up the ramp into the ship.

## Station spots (`Stations`, Marker3D: origin on the deck, +Z the spot's normal into the room)

| Node | Spot | Package | at (x, y, z) | yaw (deg) |
|---|---|---|---|---|
| `Console` | `console` (hall) | `start_console` | (0.0, 1.2, 0.6) | 180.0 |
| `VentE` | `vent_e` (throat) | `ship:th_wall_e` | (2.409, 1.2, -4.7912) | -71.802 |
| `VentW` | `vent_w` (throat) | `ship:th_wall_w` | (-2.409, 1.2, -4.7912) | 71.802 |
| `SocketE` | `socket_e` (hall) | `crystal_socket` | (1.8, 1.2, 3.112) | -152.864 |
| `SocketW` | `socket_w` (hall) | `crystal_socket` | (-1.8, 1.2, 3.112) | 152.864 |
| `SocketFE` | `socket_fe` (hall) | `crystal_socket` | (3.4261, 1.2, -2.3578) | -60.256 |
| `SocketFW` | `socket_fw` (hall) | `crystal_socket` | (-3.4261, 1.2, -2.3578) | 60.256 |
| `BreakerE` | `breaker_e` (corridor_e) | `breaker_board` | (6.6638, 1.2, -0.9019) | -8.662 |
| `BreakerW` | `breaker_w` (corridor_w) | `breaker_board` | (-6.6638, 1.2, -0.9019) | 8.662 |
| `RenewerE` | `renewer_e` (tip_e) | `crystal_charger` | (10.2686, 1.2, 3.2369) | 173.517 |
| `RenewerW` | `renewer_w` (tip_w) | `crystal_charger` | (-10.2686, 1.2, 3.2369) | -173.517 |

Each package's own `HANDOFF.md` "Placement" holds its offset from the spot (the breaker board 0.07 m out along +Z;
the energy crystal at the socket's `crystal_anchor`). The vents are the throat walls in the scene (`Pieces/th_wall_e_*`,
`th_wall_w_*`) with the gill set: five static glowing slits, the turn bars and a button per wall (the engineer's pick,
2026-10-30); `godot/ship/gill_set.gd` in the art repo is the reference driver for the game's vent station.

## Lights and environment

`Environment/WorldEnvironment` uses `night_env.tres` (AgX at the layout's exposure, glow, SSAO, SSIL, a thin fog,
the star sky with the moon). `Lights` holds 103: the moon and the cool key (directional, shadows), the ship's own lamps
of the layout (omni or spot, most with shadows) and the omni lights of the glowing cells (61 in all with the
clearing's, no shadows); `Clearing/Lights` the clearing's 41. One reflection probe per room (`Probes`, update once). The nav
lamps hold their static glow (no blink).

## Cost in a player's view (1920x1080, this PC's GPU, Forward Plus, the art's night look)

| View | Draw calls | Primitives | GPU ms |
|---|---|---|---|
| `in_hall` | 4336 | 2,106,100 | 4.95 |
| `in_tip_e` | 1228 | 1,194,499 | 4.42 |
| `out_hero` | 4950 | 2,405,533 | 3.71 |

`in_hall` is a player's eye in the hall (1.6 m over the deck), `in_tip_e` in a tip room, `out_hero` the outside from
above. Every piece is its own instance (1056), so the hall draws about 4300 calls: merging or batching the static
pieces, as the House does, is the first lever if the game's budget needs it.

## The check (art side)

Headless load of the package as its own project; every piece's bounds within 0.0 mm of Blender's;
694 layer-1 bodies; `Clearing` holds exactly the layout's 534 clearing placements, `Pieces` none of them; the capsule walk from `Markers/Spawn` into both tip rooms and back
(18/18 points, 24.0 s); the three views
above beside `ship --shoot`'s: mean difference 0.003, 0.002, 0.003 of 255 (the look unchanged).

## Open questions for the game side

- S1: Stations holds Marker3D spots only (+Z the spot's normal into the room, origin on the deck at the wall's face or the console's middle): the station packages (start_console, crystal_socket with energy_crystal at its crystal_anchor, breaker_board, crystal_charger) get their look from their own GDScript (apply()), which an asset may not carry (11.1), so the game's station scenes instance them at the markers. Each package's HANDOFF.md 'Placement' holds its own offset (the breaker board 0.07 m out along the normal).
- S2: the throat vents (VentE, VentW) are part of the ship: since the clean throat (2026-10-29) the spots lie on the walls th_wall_e and th_wall_w under Pieces, which carry the gill set (five static glowing slits, the turn bars and a button per wall; the engineer's pick, 2026-10-30); godot/ship/gill_set.gd is the art's reference driver for the game's vent station.
- S3: the look the art sets by code is baked into the scene as overrides inside each piece's instance (the glTF materials' night values, the outside pieces' render layer 2, the vents' well lights), every piece an editable instance; the shared metal is metal.gdshader with one .tres per metal. The shaders are art code shipped as files (as the House's kit_set.gdshader): who owns them?
- S4: the nav lamps' blink (red, green and the white tail flash) is a script in the art's shots; the scene holds their static glow. The game adds the blink if it wants it.
- S5: the strip lights are many OmniLight3D nodes (no shadows) under Lights, placed per glowing cell by the art's look; a baked light or fewer lights is the game's call against its budget (HANDOFF 'Cost').
- S6: the pieces' colliders are the GLBs' own -col trimesh hints (StaticBody3D on layer 1); the game's `colliders` writes its wrappers on import (11.2).
- S7: the clearing round the ship (the ground and its world boundary, the pines, bushes, ferns, moss, litter, logs, rocks, the ground lamps, the party string and the lamps that light only them) is the one node Clearing (Clearing/Pieces, Clearing/Lights, Clearing/Ground); the lobby (art#356) shows the ship docked without it: free the node (queue_free(), or delete it in an inherited scene); hiding it leaves Ground's collider on. The ship itself (hull, legs, ramp, entry tunnel, its landing and edge lights, the rim and key) stays under Pieces and Lights. A closed state (the ramp raised, the mouth shut) waits for the engineer's pick of its look.
- Imports: each GLB's .import holds only 11.2's options; the game's editor regenerates the .import files (and the uids) on its first import: commit the regenerated ones.
