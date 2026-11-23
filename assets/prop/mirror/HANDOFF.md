# The lobby's mirror: handoff to the game (art#390)

Built from code (`tools/blender/lobby_furniture_build.py --piece mirror` from its drawing `tools/blender/mirror_dims.toml`), build `v6`, packed unchanged. Not approved yet.

## Files

| File | What |
|---|---|
| `export/mirror.glb` | One scene, 1,088 triangles, 4 materials, 0 textures embedded, 58 KB. SHA-256 `c03caf1a484a2093a85786519709c94f2e84eeeb9fe0856dc95d550ecab4c2d9` |
| `package.json` | The meshes, markers, origin and placement, for code |
| `report.json` | Triangles per mesh and material, bounds, glTF-Validator (0 errors, 0 warnings), the clearances in the hall, the markers as Godot placed them |

## Nodes

Units metres, +Y up, the player side +Z. The GLB's root nodes:

- `mirror` (MeshInstance3D, 1,076 triangles): the frame (style `frame`, the engineer's pick C): the back plate, the wide rounded steel frame with its cyan line, the light bar over the glass;
- `MirrorGlass` (MeshInstance3D, 12 triangles): the glass, 2 x 2.5 m: the game draws the reflection on it (its material `mirror_glass` is a bright stand-in);
- `MirrorFace` (Node3D, a marker) at (0, 1.25, 0.09): the glass's centre on its face, 1.25 m up.

**Origin:** on the floor at the glass's middle, on the wall's face.

## In the lobby

It replaces the greybox levels/lobby/lobby.tscn `Mirror` (StaticBody3D at (-20, 0, 7), its box 0.2 x 2.5 x 2 m centred at (0.1, 1.25, 1): the glass on the west wall at x -20..-19.8, z 7..9) and the markers `MirrorPlace1..3` at (-19.2, 0, 7.2), (-19.2, 0, 8), (-19.2, 0, 8.8).

- Place the GLB's root at (-19.86, 0, 8) in the hall, turned 90 degrees about +Y: `Transform3D(0, 0, -1, 0, 1, 0, 1, 0, 0, -19.86, 0, 8)`.
- Its markers then land at (the hall's frame, m): `MirrorFace` (-19.77, 1.25, 8).
- Collision: the greybox's box reaches x -19.8 and z 7..9, 2.5 m up; the mirror reaches x -19.72 (0.14 m out from its origin on the wall's panels) and z 6.9..9.1, 2.67 m up: a box 0.28 x 2.67 x 2.21 m centred at (-19.86, 1.335, 8) holds it from the wall to the frame's front.
- The players' places in front: (-19.2, 0, 7.2), (-19.2, 0, 8), (-19.2, 0, 8.8) (the greybox's `MirrorPlace1..3`).

No label, no text, no copper. The look is approved: do not restyle it in the game.
