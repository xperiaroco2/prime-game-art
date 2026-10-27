# The ship: handoff to the game

The empty ship of art#263 (a wide metal manta at night: the hall, the throat and its ramp, two corridors, two lens tip
rooms, the vault) as the game's package, for prime-game#1225 (the engine) and #1285 (boot into it). Written by
`tools/run.sh ship --export <raw>/ship/v5/export/v1` (art#335, `docs/ship.md` "The export"); the files and their
hashes are in `manifest.toml` and the package's `package.json`. The GLBs are not committed here: the package lives in
the raw folder until approved.

## Files (the game's tree)

| Path | What |
|---|---|
| `assets/environment/ship/<piece>.glb` | the 168 pieces, each with a minimal `.import` (11.2); colliders are the GLBs' `-col` trimesh hints |
| `assets/environment/ship/metal.gdshader`, `night_sky.gdshader` | the shared metal and the star sky (art shaders shipped as files) |
| `assets/environment/ship/materials/*.tres` | one `metal_<name>.tres` per shared metal, `night_sky.tres`, `night_env.tres` |
| `assets/environment/ship/station_vent_*_vent_a_normal.png` | the vents' normal maps (their GLBs' import extracts them too) |
| `levels/ship/ship.tscn` | the level: `Ship` > `Pieces`, `Environment`, `Lights`, `Probes`, `Ground`, `Stations`, `Markers` |
| `package.json` | every file with SHA-256 and bytes, the spots, the spawn, the questions |

182 files, 24.0 MB. No GDScript: the look the art sets by code is saved in the scene as
overrides inside the pieces' instances (each piece an editable instance, 11.2's rule).

## Placement

The scene's origin is the ship's plan origin on the ground (the clearing's ground piece at y 0); Godot x = plan x,
z = plan y, +Z aft; the deck is at y 1.2 m. `metadata/size_m` is the plan's width and length with the nozzles;
`metadata/deck_h` the deck. `Markers/Spawn` stands at the ramp's foot ([0.0, 0.0, -14.0]), turned
180.0 degrees: facing the mouth.

## Station spots (`Stations`, Marker3D: origin on the deck, +Z the spot's normal into the room)

| Node | Spot | Package | at (x, y, z) | yaw (deg) |
|---|---|---|---|---|
| `Console` | `console` (hall) | `start_console` | (0.0, 1.2, 0.6) | 180.0 |
| `VentE` | `vent_e` (throat) | `ship:station_vent_e` | (2.409, 1.2, -4.7912) | -71.802 |
| `VentW` | `vent_w` (throat) | `ship:station_vent_w` | (-2.409, 1.2, -4.7912) | 71.802 |
| `SocketE` | `socket_e` (hall) | `crystal_socket` | (1.8, 1.2, 3.112) | -152.864 |
| `SocketW` | `socket_w` (hall) | `crystal_socket` | (-1.8, 1.2, 3.112) | 152.864 |
| `SocketFE` | `socket_fe` (hall) | `crystal_socket` | (3.4261, 1.2, -2.3578) | -60.256 |
| `SocketFW` | `socket_fw` (hall) | `crystal_socket` | (-3.4261, 1.2, -2.3578) | 60.256 |
| `BreakerE` | `breaker_e` (corridor_e) | `breaker_board` | (6.6638, 1.2, -0.9019) | -8.662 |
| `BreakerW` | `breaker_w` (corridor_w) | `breaker_board` | (-6.6638, 1.2, -0.9019) | 8.662 |
| `RenewerE` | `renewer_e` (tip_e) | `crystal_charger` | (10.2686, 1.2, 3.2369) | 173.517 |
| `RenewerW` | `renewer_w` (tip_w) | `crystal_charger` | (-10.2686, 1.2, 3.2369) | -173.517 |

Each package's own `HANDOFF.md` "Placement" holds its offset from the spot (the breaker board 0.07 m out along +Z;
the energy crystal at the socket's `crystal_anchor`). The vents are in the scene already (`Pieces/station_vent_e_*`,
`station_vent_w_*`), calm.

## Lights and environment

`Environment/WorldEnvironment` uses `night_env.tres` (AgX at the layout's exposure, glow, SSAO, SSIL, a thin fog,
the star sky with the moon). `Lights` holds 142: the moon and the cool key (directional, shadows), the layout's 57
lamps (omni or spot, most with shadows) and 83 omni lights of the glowing cells (no shadows); under each vent's glow
panels three well lights (12, inside `Pieces`). One reflection probe per room (`Probes`, update once). The nav
lamps hold their static glow (no blink).

## Cost in a player's view (1920x1080, this PC's GPU, Forward Plus, the art's night look)

| View | Draw calls | Primitives | GPU ms |
|---|---|---|---|
| `in_hall` | 3602 | 2,025,543 | 5.03 |
| `in_tip_e` | 1030 | 1,180,781 | 4.55 |
| `out_hero` | 3947 | 2,313,291 | 3.8 |

`in_hall` is a player's eye in the hall (1.6 m over the deck), `in_tip_e` in a tip room, `out_hero` the outside from
above. Every piece is its own instance (1092), so the hall draws about 3600 calls: merging or batching the static
pieces, as the House does, is the first lever if the game's budget needs it.

## The check (art side)

Headless load of the package as its own project; every piece's bounds within 6.0 mm of Blender's;
665 layer-1 bodies; the capsule walk from `Markers/Spawn` into both tip rooms and back
(14/14 points, 23.0 s); the three views
above beside `ship --shoot`'s: mean difference 0.0, 0.0, 0.0 of 255 (the look unchanged).

## Open questions for the game side

- S1: Stations holds Marker3D spots only (+Z the spot's normal into the room, origin on the deck at the wall's face or the console's middle): the station packages (start_console, crystal_socket with energy_crystal at its crystal_anchor, breaker_board, crystal_charger) get their look from their own GDScript (apply()), which an asset may not carry (11.1), so the game's station scenes instance them at the markers. Each package's HANDOFF.md 'Placement' holds its own offset (the breaker board 0.07 m out along the normal).
- S2: the throat vents (VentE, VentW) are part of the ship: the pieces station_vent_e and station_vent_w under Pieces, calm (the heat panel hidden). Their states (slats, the heat and cool panels and their well lights) are art code today (godot/ship/vent_anim.gd, vent_glow.gd): the game's vent station drives the nodes by name.
- S3: the look the art sets by code is baked into the scene as overrides inside each piece's instance (the glTF materials' night values, the outside pieces' render layer 2, the vents' well lights), every piece an editable instance; the shared metal is metal.gdshader with one .tres per metal. The shaders are art code shipped as files (as the House's kit_set.gdshader): who owns them?
- S4: the nav lamps' blink (red, green and the white tail flash) is a script in the art's shots; the scene holds their static glow. The game adds the blink if it wants it.
- S5: the strip lights are many OmniLight3D nodes (no shadows) under Lights, placed per glowing cell by the art's look; a baked light or fewer lights is the game's call against its budget (HANDOFF 'Cost').
- S6: the pieces' colliders are the GLBs' own -col trimesh hints (StaticBody3D on layer 1); the game's `colliders` writes its wrappers on import (11.2).
- Imports: each GLB's .import holds only 11.2's options; the game's editor regenerates the .import files (and the uids) on its first import: commit the regenerated ones.
