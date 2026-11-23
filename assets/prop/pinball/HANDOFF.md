# The lobby's pinball machine: handoff

The lobby's playable pinball machine (art #374), the art for prime-game's greybox `levels/lobby/lobby.tscn` `Pinball`
and its table contract (`scenes/pinball/pinball_table.tscn`, `PinballTableSpec`). The engineer approved the look on
2026-11-23 without copper (his pick B): the dark rails with teal edges, every trim the hall's cold steel. This package carries the art only. The table's physics, the
flippers' input, the score and the display's text stay the game's.

## Files

| File | What |
|---|---|
| `export/pinball.glb` | The cabinet: one mesh `pinball` (36,680 triangles, 7 materials, textures embedded; no copper: `pinball_steel` trims), its origin on the floor under the footprint's middle, the player on -Z. Three empties at the greybox's roles: `TableMount`, `CloseUp` and `Display` |
| `export/pinball_table.glb` | The table's art in the contract's frame, one mesh per contract body, named as the node it dresses: `WallLeft`, `WallRight`, `WallTop`, `InlaneLeft`, `InlaneRight`, `FlipperLeft`, `FlipperRight`, `Bumper`, `Kicker`, `Target`. Also `Playfield` (the night Earth art), `Glass` and the markers `BallStart` and `Drain`. 4,408 triangles; each flipper's pivot is at its origin |
| `source/pinball.blend` | The Blender build |
| `report.json` | Triangles by part and material, the markers' transforms, the measured sizes, glTF-Validator, the clearances in the hall |

## In the game

- **Place:** the cabinet's origin at (18, 0, 3.44) in the lobby, unrotated. Its front then stands 38 cm from the
  greybox's `PinballSpot` (18, 0, 2.2). It clears the east wall, its pilasters and door D2 by at least 1.5 m
  (`report.json` `clearances_m`).
- **Markers** (cm in the cabinet's frame; each basis as rows):
  - `TableMount` (0, 99.36, -10.93): the table node goes here. Its basis is 180 degrees about y, so the flippers'
    end faces the player, then the 6.5 degree tilt. The game's flat physics table is drawn tilted.
  - `CloseUp` (0, 228.36, -140.93): the camera, 1.29 m above `TableMount` and 1.30 m toward the player, pitched
    37 degrees down, fov 50. That is the greybox's place after the engineer's M8 review. The pitch is 37 rather than
    the greybox's 42 because the cabinet's screen stands higher than the greybox's `Display`: at 42 the top line
    left the frame.
  - `Display` (0, 162, 57.6): the three Label3D lines (best and owner, score, balls). It sits on the backbox's
    66 x 38 cm screen with its +Z toward the player.
- **Sizes:** the playfield is exactly the contract's 72 x 130 cm. Its front edge is 92 cm above the floor and its far
  edge 106.7 cm. The backbox top is at 1.9 m. The cabinet is 90.1 x 172.6 cm.
- **Swap:** the game's table keeps its bodies and colliders. Each body's greybox mesh is replaced by the mesh of the
  same name from `pinball_table.glb`, at the same transform. `Playfield` and `Glass` are drawn only. The glass is
  clear, so it needs no collision beyond the contract's.
- **Collision for the cabinet:** none is made here. A box of 90 x 190 x 173 cm, or the body and backbox as two
  boxes, fits it.
- **Light:** the cyan rings and lines are emissive (2.2). The cabinet adds no light of its own.

## Provenance

`manifest.toml`: built from code in headless Blender (`tools/blender/pinball_build.py`) from its drawing
(`tools/blender/pinball_dims.toml`). The drawing is fitted to the concept `lobby/pinball/ref/concept_p2.png`, our own
OpenAI generation used only as a reference; no part of the model was generated. The playfield and side art are cut
from NASA's Black Marble (credit "Earth imagery: NASA", `sources/nasa_earth_lobby.toml`). Own work; public repo ok.
