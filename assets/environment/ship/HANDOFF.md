# The ship: handoff to the game

The empty ship of art#263 (a wide metal manta at night: the hall with the gills on its back wall, the plain throat and
its ramp, two corridors, two lens tip rooms, the vault) as the game's package, for prime-game#1225 (the engine) and
#1285 (boot into it). Written by `tools/run.sh ship --export <raw>/ship/v5/export/v2` (art#335's export, re-run with
the gills at gills step 13, `docs/ship.md` "The export"); the files and their hashes are in `manifest.toml` and the
package's `package.json`. The GLBs are not committed here: the package lives in the raw folder until approved (the
engineer's look yes on the gills is pending).

## Files (the game's tree)

| Path | What |
|---|---|
| `assets/environment/ship/<piece>.glb` | the 159 pieces, each with a minimal `.import` (11.2); colliders are the GLBs' `-col` trimesh hints |
| `assets/environment/ship/metal.gdshader`, `night_sky.gdshader` | the shared metal and the star sky (art shaders shipped as files) |
| `assets/environment/ship/console_metal.gdshader` | the gills' bronze (the stations' shared bronze: a copy of the start console's shader) |
| `assets/environment/ship/materials/*.tres` | one `metal_<name>.tres` per shared metal, `night_sky.tres`, `night_env.tres` |
| `levels/ship/ship.tscn` | the level: `Ship` > `Pieces`, `Environment`, `Lights`, `Probes`, `Ground`, `Stations`, `Markers` |
| `package.json` | every file with SHA-256 and bytes, the spots, the spawn, the questions |

172 files, 9.6 MB (v1: 182 files, 24.0 MB). Copy only the files `package.json` lists: the export folder also holds
the art check's own `_check/`, `project.godot`, `lib/`, `.godot/` and the `.uid` files Godot writes, none of them for
the game. The old throat vents' two normal maps (3.8 MB each, byte-identical copies) are gone with them: the gills
use no texture, so there is nothing to share. Against v1: the throat's vent pieces and its wall's extras
(`th_cables`, `th_channel`, `th_clip_h`, ...) and the hall's old side ceiling, panel and rim pieces left with the
gills' move (steps 8-9); `station_vent_e` and `station_vent_w` are the gills now. No GDScript: the look the art sets
by code is saved in the scene as overrides inside the pieces' instances (each piece an editable instance, 11.2's rule).

## Placement

The scene's origin is the ship's plan origin on the ground (the clearing's ground piece at y 0); Godot x = plan x,
z = plan y, +Z aft; the deck is at y 1.2 m. `metadata/size_m` is the plan's width and length with the nozzles;
`metadata/deck_h` the deck. `Markers/Spawn` stands at the ramp's foot ([0.0, 0.0, -14.0]), turned
180.0 degrees: its +Z (aft) looks up the ramp into the ship.

## Station spots (`Stations`, Marker3D: origin on the deck, +Z the spot's normal into the room)

| Node | Spot | Package | at (x, y, z) | yaw (deg) |
|---|---|---|---|---|
| `Console` | `console` (hall) | `start_console` | (0.0, 1.2, 0.6) | 180.0 |
| `VentE` | `vent_e` (hall, back wall) | `ship:station_vent_e` | (1.6305, 1.2, 3.2475) | -155.914 |
| `VentW` | `vent_w` (hall, back wall) | `ship:station_vent_w` | (-1.6305, 1.2, 3.2475) | 155.914 |
| `SocketE` | `socket_e` (hall) | `crystal_socket` | (2.9339, 1.2, 2.3119) | -132.751 |
| `SocketW` | `socket_w` (hall) | `crystal_socket` | (-2.9339, 1.2, 2.3119) | 132.751 |
| `SocketFE` | `socket_fe` (hall) | `crystal_socket` | (3.4261, 1.2, -2.3578) | -60.256 |
| `SocketFW` | `socket_fw` (hall) | `crystal_socket` | (-3.4261, 1.2, -2.3578) | 60.256 |
| `BreakerE` | `breaker_e` (corridor_e) | `breaker_board` | (6.6638, 1.2, -0.9019) | -8.662 |
| `BreakerW` | `breaker_w` (corridor_w) | `breaker_board` | (-6.6638, 1.2, -0.9019) | 8.662 |
| `RenewerE` | `renewer_e` (tip_e) | `crystal_charger` | (10.2686, 1.2, 3.2369) | 173.517 |
| `RenewerW` | `renewer_w` (tip_w) | `crystal_charger` | (-10.2686, 1.2, 3.2369) | -173.517 |

The vents moved from the throat's walls ((+-2.409, -4.7912), v1) to the hall's back wall either side of the vault's
door; the back sockets moved one wall chord out (from (+-1.8, 3.112)). The throat is plain wall now: no station there.
Each package's own `HANDOFF.md` "Placement" holds its offset from the spot (the breaker board 0.07 m out along +Z;
the energy crystal at the socket's `crystal_anchor`). The gills are in the scene already (`Pieces/station_vent_e_*`,
`station_vent_w_*`), calm.

## The gills (VentE, VentW): pieces and the controller

Each unit is one GLB (`station_vent_<e|w>`, about 1.6 m wide, deck to the rim's underside, its well 0.45 m into the
wall). Its leaves, by name (`<id>` is `station_vent_e` or `station_vent_w`):

- `<id>_cover1..4`: the four bronze ribs, each turning about its vertical axis through its origin, at most 4 deg
  either way (the builder's clearance is tested there); `<id>_flank<k>`, `flank<k>b` (the ribs' lit flanks) and
  `lip<k>` are their children.
- `<id>_cool`: the calm glow, with its children `cool2..24` (the bands up the well), `slots6`, `slots7`, the floor
  strips `floor1..5`, `floor21..25`, `floor31..35` (hidden: the old steps) and `spill1..5` (the soft floor pools), and the well lights
  `cool_gap<k>_light1..5`, `_foot`, `_slot` (OmniLight3D). `<id>_heat` (hidden) holds the red's material and its twin
  lights; the controller turns the cool red band by band, so the heat stays hidden.
- `<id>_seam1..5`: the slots' red seams (hidden calm); `<id>_bar`, `bar_green` (the green band), `bar_top`,
  `bar_frame`: the hold bar; `<id>_lamp`: the lamp dome; the casing (`body`, `well`, `sill`, `hood`, `soffit`,
  `fixed`, `crown5`, `upper`, `screen`, `hand`, `bezel`, `column_strip`, ...) is static.

`godot/ship/vent_anim.gd` (art code, about 700 lines; its header is the API) is the controller the game copies, one per
unit, added as the unit root's child: `setup(unit_root, "station_vent_e")`, or set `vent_id` and let `_ready` find
the parent.

- **Inputs, each frame:** `problem: bool` (the unit is broken), `hold: float 0..1` (the scanner hold's progress while
  a palm is on it, 0 without; send exactly 1.0 at the top), `release()` once when the palm leaves. The order: set
  `problem` and `hold`, call `release()` if the palm left this frame, then `step(dt)` (or let `_process` run).
- **Signals:** `fixed` (released with the marker in the green band, 0.808..0.923 of the bar, both ends in: the exhale
  plays, the game clears `problem`), `too_early` (below it: the game plays its "try again"), `missed` (past it, below
  the top: a cough, still broken), `thrown` (the marker reached the top, 0.995: `hold` at 1.0 for about 0.2-0.3 s; the
  game throws the player back; a `release()` after it is ignored).
- The release is judged on the marker of the last step with a palm (`judged`), so the order of the game's calls in the
  frame the palm leaves does not matter. `hold` falling to 0 with no `release()` judges nothing. After `fixed` the
  unit re-arms only once `problem` has been false; after a release or `thrown` a new hold starts only once `hold` has
  been back to 0. `restore(unit_root)` puts the scene's materials and panels back.
- **Lights:** the gills' meshes are on render layer 4 (`VENT_LAYER`, 1 << 3); every inside light lights it except the
  doorways' red-orange floor-strip lights within 1.6 m of a unit (so calm reads cyan only). The scene's cull masks
  hold this; the game's own lights need the same rule.

## Lights and environment

`Environment/WorldEnvironment` uses `night_env.tres` (AgX at the layout's exposure, glow, SSAO, SSIL, a thin fog,
the star sky with the moon). `Lights` holds 142: the moon and the cool key (directional, shadows), the layout's lamps
(omni or spot, most with shadows) and the glowing cells' omni lights (no shadows); inside the two gills units 130
more well lights (no shadows, inside `Pieces`), 272 in all. One reflection probe per room (`Probes`, update once).
The nav lamps hold their static glow (no blink).

## Cost in a player's view (1920x1080, this PC's GPU, Forward Plus, the art's night look)

| View | Draw calls | Primitives | GPU ms |
|---|---|---|---|
| `in_hall` | 4262 | 2,086,841 | 4.96 |
| `in_tip_e` | 1030 | 1,180,781 | 4.31 |
| `out_hero` | 3950 | 2,258,243 | 3.66 |

`in_hall` is a player's eye in the hall (1.6 m over the deck), `in_tip_e` in a tip room, `out_hero` the outside from
above. Every piece is its own instance (1088), so the hall draws about 4300 calls (v1 3602: the gills' many glow
parts and lights); merging or batching the static pieces, as the House does, is the first lever if the game's budget
needs it.

## The check (art side)

Headless load of the package as its own project; every piece's bounds within 0.01 mm of Blender's; 653 layer-1
bodies; the capsule walk from `Markers/Spawn` into both tip rooms and back (14/14 points, 23.0 s); the three views
above beside `ship --shoot`'s: mean difference 0.0, 0.0, 0.0 of 255 (the look unchanged).

## Open questions for the game side

`package.json` "questions" S1-S6 and the imports note, in short:

- S1: Stations holds Marker3D spots only; the station packages (start_console, crystal_socket with energy_crystal,
  breaker_board, crystal_charger) get their look from their own GDScript, so the game's station scenes instance them
  at the markers.
- S2: the gills are part of the ship (above); their states are art code (`vent_anim.gd`, `vent_glow.gd`) the game's
  vent station copies and drives by name, with the strip lights' layer rule.
- S3: the look the art sets by code is baked as overrides inside each piece's instance; the shaders
  (`metal.gdshader`, `night_sky.gdshader`, `console_metal.gdshader`) are art code shipped as files: who owns them?
- S4: the nav lamps' blink is the art's shots' script; the scene holds their static glow.
- S5: the strip lights are many OmniLight3D nodes; a baked light or fewer lights is the game's call (see "Cost").
- S6: the pieces' colliders are the GLBs' own `-col` trimesh hints (StaticBody3D on layer 1).
- Imports: each GLB's `.import` holds only 11.2's options; the game's editor regenerates them on its first import.
