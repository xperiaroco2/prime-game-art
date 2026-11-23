# The lobby's match console: handoff to the game (art#391)

Built from code (`tools/blender/lobby_furniture_build.py --piece match_console` from its drawing `tools/blender/match_console_dims.toml`), build `v6`, packed unchanged. Not approved yet.

## Files

| File | What |
|---|---|
| `export/match_console.glb` | One scene, 5,632 triangles, 7 materials, 3 textures embedded, 380 KB. SHA-256 `8e21d94543abc5106ae217aa3d31d3549eddad81fa5a0bfbf5b22bda3a836c9a` |
| `package.json` | The meshes, markers, origin and placement, for code |
| `report.json` | Triangles per mesh and material, bounds, glTF-Validator (0 errors, 0 warnings), the clearances in the hall, the markers as Godot placed them |

## Nodes

Units metres, +Y up, the player side +Z. The GLB's root nodes:

- `match_console` (MeshInstance3D, 5,604 triangles): the monolith: body, facets, steel lines, base plate and its light ring;
- `ConsoleScreen` (MeshInstance3D, 28 triangles): the screen's surface: the game draws the match's screen on it (its material `match_console_screen` is a dark stand-in);
- `Screen` (Node3D, a marker) at (0, 1.15, 0.162): the screen's centre on its face (the greybox's `Screen` is at (0, 1.15, 0.16); here z 0.162, the built screen's face).

**Origin:** on the floor under the piece's middle.

## In the lobby

It replaces the greybox levels/lobby/match_console.tscn (StaticBody3D `MatchConsole`, its box 1.2 x 1.6 x 0.3 m, `Screen` at (0, 1.15, 0.16)), instanced in levels/lobby/lobby.tscn as `MatchConsole` at (-7, 0, 7.2) turned 180 degrees.

- Place the GLB's root at (-7, 0, 7.2) in the hall, turned 180 degrees about +Y: `Transform3D(-1, 0, 0, 0, 1, 0, 0, 0, -1, -7, 0, 7.2)`.
- Its markers then land at (the hall's frame, m): `Screen` (-7, 1.15, 7.038).
- Collision: the greybox's box (1.2 x 1.6 x 0.3 m) covers the monolith's body; the round base plate (1.56 m across, a few cm high) stays walkable.
- `match_console.tscn` already stands at this transform in `lobby.tscn`: put the GLB in place of its `Mesh`, keep `Shape`, and move `Screen` to the GLB's `Screen` (z 0.162 instead of 0.16).

No label, no text, no copper. The look is approved: do not restyle it in the game.
