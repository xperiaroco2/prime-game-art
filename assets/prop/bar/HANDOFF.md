# The lobby's bar: handoff to the game (art#389)

Built from code (`tools/blender/lobby_furniture_build.py --piece bar` from its drawing `tools/blender/bar_dims.toml`), build `v6`, packed unchanged. Not approved yet.

## Files

| File | What |
|---|---|
| `export/bar.glb` | One scene, 6,608 triangles, 7 materials, 3 textures embedded, 573 KB. SHA-256 `fad27ccad47c6a30ac8c98d3569d575a9dc42828a03a83ed44ecf80175e73d25` |
| `package.json` | The meshes, markers, origin and placement, for code |
| `report.json` | Triangles per mesh and material, bounds, glTF-Validator (0 errors, 0 warnings), the clearances in the hall, the markers as Godot placed them |

## Nodes

Units metres, +Y up, the player side +Z. The GLB's root nodes:

- `bar` (MeshInstance3D, 6,608 triangles): the whole bar: the stone top, the shell, the steel sweep and the tap, the light lines, the plinth's glow;
- `TapSpot` (Node3D, a marker) at (0, 0, 1.5): where a player stands to draw a beer, on the floor 1.5 m out from the tap (the greybox's `Tap`, group `spawn_tap`).
- `TapSpout` (Node3D, a marker) at (0, 1.355, 0.425): the tap's spout, where the beer leaves it.

**Origin:** on the floor under the piece's middle.

## In the lobby

It replaces the greybox levels/lobby/lobby.tscn `Bar` (StaticBody3D at (-17, 0, -13), its box 1 x 1.1 x 6 m centred at (0.5, 0.55, 3) inside it: the floor's middle at (-16.5, 0, -10)) and the marker `Tap` at (-15, 0, -10).

- Place the GLB's root at (-16.5, 0, -10) in the hall, turned 90 degrees about +Y: `Transform3D(0, 0, -1, 0, 1, 0, 1, 0, 0, -16.5, 0, -10)`.
- Its markers then land at (the hall's frame, m): `TapSpot` (-15, 0, -10); `TapSpout` (-16.075, 1.355, -10).
- Collision: the greybox's box (1 x 1.1 x 6 m) still fits the counter; the tap reaches 1.6 m.
- The `Tap` marker (group `spawn_tap`) stays where it is: the GLB's `TapSpot` lands on it.

No label, no text, no copper. The look is approved: do not restyle it in the game.
