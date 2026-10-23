# The ship engine's energy crystal: handoff

The cartridge of the ship's engine (xperiaroco2/prime-game#1033, comment 6361383461; art#263): a spent crystal is
pulled from its wall socket, recharged at a charger and put back. Out of scope here: the sockets, the chargers, the
lightning and any behaviour; they are built later to fit this crystal.

## Files

| File | What |
|---|---|
| `export/energy_crystal.glb` | One mesh, five surfaces (`crystal_shell`, `crystal_core`, `crystal_bronze`, `crystal_graphite`, `crystal_light`), the triangles in `report.json` (the `hero` class: at most 4,000), front +Z, origin at the crystal's tip, its lowest point, under its middle. Its materials are a plain-PBR fallback of the charged state. UV0 is data, not a layout: u = 1 on the chamfered edges, v = a random value per facet |
| `export/crystal.gd` | `apply(model)`: puts the look on the imported model by its surface names and adds a small cyan OmniLight3D inside; returns the look. `set_charge(look, c)`: 1 charged, 0 spent, values between fade. It preloads the three shaders from its own folder |
| `export/crystal_shell.gdshader` | The crystal: charged a translucent cyan gem glowing facet by facet, the edges a pale line; spent a matte grey stone, opaque |
| `export/crystal_core.gdshader` | The glowing core inside the crystal, seen through the charged shell; dark when spent |
| `export/crystal_metal.gdshader` | The cap's bronze and graphite: a faint grain, bright worn edges |
| `source/energy_crystal.blend` | The model with the Blender look; the node group `crystal_charge` switches both states (1 charged, 0 spent) |

## In the game

- Size: real size, no scaling: 0.352 m tall with the loop, 12.0 cm across the crystal's corners (10.4 cm across its
  flats), 13.1 to 13.4 cm across the cap's band (16 sides), 14.0 cm across the claws.
- States: `set_charge(look, 1.0)` charged, `0.0` spent; a charge animation can tween it. A slow shimmer runs while
  charged (`pulse` on both crystal shaders, 0.05; 0 stops it).
- Light: charged, the crystal lights about 1.6 m around it in cyan (the OmniLight3D, no shadows); spent, the light is
  off and the cap's windows keep 22 % of their glow.
- The shell is alpha-blended with a depth prepass (its spent state writes depth like an opaque mesh).
- Collision: none made here; a capsule of 7 cm radius and 0.35 m fits it.
- The socket and charger: the band is the cap's widest part (13.4 cm); the two claws on the crystal's side corners
  reach 14.0 cm.
- Cost: the hand view drew in about 1 ms of GPU (1280x720, this PC; `report.json`).

## Provenance

`manifest.toml`: built from code in Blender (`tools/blender/crystal_build.py`), no generator, own work; the concept
from prime-game-design (`ideas/ship-components/cartridge-v2`). Public repo ok.
