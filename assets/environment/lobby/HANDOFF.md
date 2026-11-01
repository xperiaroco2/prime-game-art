# The lobby hall: handoff to the game

The lobby's hall of art#356 (a 40 x 40 m hall with a bowed window to the night Earth, a ribbed vault, the entrance
arch, four sealed doors, art#263's ship docked on a floor ring) as the game's package. Written by
`tools/run.sh lobby --export <raw>/lobby/hall/v18/export` (2026-11-01, branch fix/lobby-cback-366, steps 5b-5c2 and
follow-up #366;
`docs/lobby.md` "The export"); the files and their hashes are in `manifest.toml` and `package.json`, the check's
numbers in `report.json`. The binaries are not committed here: the package lives in the raw folder until approved (as
the ship's).

The engineer's picks it carries: the colour scheme S4, the light L3, the ship light K1, the closed jaw-nose ship from
the ship package at plan origin (0, 0, -14.5), the spawns at z 2.5 facing the window, the Earth E2 with the snow set
N2, at infinity at F36 (2026-10-31), lowered to H1 (2026-11-01: the limb's top about 4 deg above the spawn's eye, so
black sky shows above the planet from everywhere in the hall).

## Files (the game's tree)

| Path | What |
|---|---|
| `assets/environment/lobby/<piece>.glb` | the hall's 7 pieces, each once (`floor`, `walls`, `vault`, `window_frame`, `window_glass`, `arch`, `door`, the door placed four times), each with a minimal `.import` (11.2); colliders are the GLBs' `-col` trimesh hints (every piece but the vault) |
| `assets/environment/lobby/earth/*.jpg` | the Earth's game textures: `earth_night`, `earth_day`, `earth_clouds` 4096 x 2048, the regional caps `earth_night_cap` 4096 x 3072 and `earth_clouds_cap` 2730 x 2048; 8.3 MB of JPEG, imported VRAM compressed (high quality: BC7 on desktop) with mipmaps, about 57 MB of video memory |
| `assets/environment/lobby/*.gdshader` | `earth_sky` (the stars; the Earth at infinity in the sky's cubemap pass for probes and reflections), `earth_object` (the planet, far mode), `window_glass` (art shaders shipped as files) |
| `assets/environment/lobby/materials/*.tres` | `lobby_env.tres` (the environment: AgX, exposure, glow, SSR, SSAO, the ambient and the Earth sky), `earth_object.tres`, `window_glass.tres` |
| `levels/lobby/lobby_hall.tscn` | the level (below), 0.43 MB |
| `levels/lobby/lobby_hall.gd` | the level's root script: frees the ship instance's switched-off nodes on `_ready`, then recaptures the probes |
| `package.json` | every file with SHA-256 and bytes, the spawns, the ship package it needs, the Earth, the questions |

20 files, 38.5 MB (the GLBs 29.8 MB: each embeds its copy of the hall's metal texture set, about 4 MB). Copy only the
files `package.json` lists: the export folder also holds the art check's `_check/`, `project.godot`, `lib/`,
`.godot/` and a copy of the ship package for the check, none of them this package's. One GDScript, the level's root
script.

## The level

`LobbyHall` (metadata `size_m` (40, 40), `camera_far_m`, `credit`, `ship_scene`, `art_issue`):

- `Hall`: the pieces as editable instances at their placements (the doors on their walls); the glass, the hanging
  lamps' shadow flags and the glow surfaces (lenses, strips, ring, door lamps) are overrides inside them.
- `Ship`: an instance of the ship package's `res://levels/ship/ship.tscn` at (0, 0, -14.5), nose north, never a copy.
  The lobby needs the ship package (`assets/environment/ship/HANDOFF.md`) at its own paths. Inside it, by overrides:
  `Clearing` hidden and disabled (its `Ground` world boundary leaves the physics world), `Environment` hidden and its
  `WorldEnvironment` given the hall's `lobby_env.tres` (a cleared environment does not survive a save, and two
  environments fight), the moon and the cool key under `Lights` hidden, the ship's 105 lamps hidden (L3:
  `ship_lights` 0), the jaw nose shut (`jaw_lower`, `jaw_upper` at 0 deg; `Nose/AnimationPlayer` is never played),
  every drawn mesh on render layer 11 and the ship's glow surfaces at 0.3 of their own (`ship_emit`). On `_ready` the
  root script `lobby_hall.gd` frees the nodes in its `ship_free` list (`Ship/Clearing`, `Ship/Environment` and the two
  suns, which the ship package names `Lights/@DirectionalLight3D@3` and `@4`), then takes every reflection probe out of
  the tree and back one frame later so each captures without them (the check: 4 nodes freed, 10 of 10 probes
  recaptured). The 704 ship colliders stay on.
- `Earth/EarthObject`: the planet, a back-faced sphere shell (`earth_object.tres`, far mode): every ray starts at the
  spawn's eye (0, 1.65, 2.5) and the shader moves the shell with the camera, so the planet is **at infinity**: the
  same size, horizon and direction from everywhere in the hall. Never parent it to anything that moves or scale it;
  the camera's far plane must reach `camera_far_m`.
- `Environment/WorldEnvironment`: `lobby_env.tres`.
- `Lights`: the L3 rig: six shadowed pendant spots and their up-fills, the pilaster strips', doors' and corridor's
  omnis, the Earth sun (shadowed) and the dawn sun, the window's cold spill spots, the north wall's negative wash, and
  K1's ship-only lights (pendant copies at 0.04 and Earth copies at 0.35 of their lamps, key, rim, back and bounce suns on layer 11 only). 60 lights.
- `Probes`: the hall's reflection probes and the ship's own (`probe_ship`, reflecting only layer 11); the ship package
  keeps its 7 interior probes.
- `Markers/Spawn0` .. `Spawn9`: `Marker3D` at x -9 .. 9 step 2, y 0, z 2.5, yaw 180: each marker's forward (-Z)
  points south (+Z) at the window. Metadata `index`.

## The game's lobby

prime-game's greybox `levels/lobby/lobby.tscn` uses the same frame (x east, z south, y up, floor y 0). Swap it for an
inherited scene of `levels/lobby/lobby_hall.tscn` (or instance it as the level's child) and keep the game's own nodes
(spawning, UI, the start logic) beside it; take the spawn points from `Markers/Spawn0..9` (their transforms). The
game's player camera needs `near` 0.05 and `far` at least `camera_far_m`; player models stay off render layer 11 (the
ship's own light set) unless they should take the ship's light.

## Light and cost

- The art's shots use a positional shadow atlas of 4096 with all four quadrants subdivided 4 (the pendants' shadowed
  spots); set it in the game's project settings or the viewport.
- GPU ms at 1920 x 1080 from the package (median of 16 frames; `lobby --shoot`'s in brackets): `spawn_eye` 2.65
  (2.79), 74 draw calls; `corner_nw` 3.54 (3.67), 3199 draw calls; `c_back` 3.51 (3.50), 2684 draw calls. The views
  that see the ship draw its whole interior behind the shut nose and the closed doors (most of the 2700-3200 draw
  calls).

## Credit

"Earth imagery: NASA" (NASA-PD, `sources/nasa_earth_lobby.toml`) in the game's credits. The hall is our own work.

## Open questions for the game

- The package ship's interior is drawn behind the closed doors and the shut nose; an occluder or hiding the ship's
  inside pieces in the lobby is the game's call.
- The spawns stand 0.76 m outside the floor ring (r 15 round the closed ship's middle, z -13.26); the ring is an inlay
  only.
- The views' comparison with `lobby --shoot` (the 2.0 rule, mean difference of 255): `c_back` 1.907 (1.52% of the
  pixels off by more than 16), `corner_nw` 0.002, `spawn_eye` 0.003. Step 5b's 3.16 on `c_back` was the shots' fault
  (follow-up #366, `docs/lobby.md`): their ship-only pendant and Earth copies sat at the floor's centre; placed as
  here, K1's pendant share went 0.25 -> 0.04 to keep the approved look.
- The ship package names its two suns `@DirectionalLight3D@3` and `@4`; if art#263 renames them, `ship_free` must
  follow (the check fails on a sun left over).
- The Earth's textures are compressed (BC7); the art's shots load them uncompressed.
