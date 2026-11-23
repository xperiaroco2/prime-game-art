# The M8 beer mug: handoff to the game (art#392)

The lobby bar's mug of beer, held in the right hand: concept 3, a faceted glass stein, kept by the engineer for M8 as
it stands (the director's relay of 2026-11-23). The art for prime-game's held items `mug` and `mug_empty`; the
first-person grip is in the hands' package (`assets/body/fp_hands/`, clips `Mug_Idle` and `Mug_Run`, node
`MugSocket`).

## Files

| File | What |
|---|---|
| `export/mug.glb` | One scene, 1,680 triangles, three materials (`mug_glass`, alpha blend; `mug_beer`, alpha blend; `mug_foam`), no textures, 64 KB. SHA-256 `5ce7f2784d89828fca15301c9945181a0737b8eeac6a2bd7ee5bc3af168f375f` |
| `report.json` | glTF-Validator and the Godot import check of the GLB, the nodes and the `Grip` frame as Godot reads them |

No `.blend`: the mug is built from code (`mug()` in `tools/blender/lobby_furniture_build.py` with
`tools/blender/mug_dims.toml`, on the branch `feat/lobby-furniture` at 9a3bf4d2, reaching `main` later).

## The contract (all four questions answered yes by the game's session)

- **One GLB for both kinds.** Nodes, as Godot imports them (checked headless, `report.json` `godot`):
  - `Mug` (MeshInstance3D): the glass body and its handle, always shown;
  - `Beer` (MeshInstance3D): the beer and its foam head; **hide it for `mug_empty`** (the drink just empties it);
  - `Grip` (Node3D, a marker): the handle's upright bar.
- **Units and axes:** metres, +Y up, **the handle on +X**; seen from +Z the handle is on the right.
- **Origin:** the centre of the base's underside (y 0), so the mug stands on the bar, a table or the floor as placed.
- **Size:** the glass 0.15 m tall and 0.09 m across (outer radius 0.0455 m); the foam rises to 0.182 m inside `Beer`;
  the handle reaches x 0.081 m, its opening about 2.1 cm wide (from the glass at x 0.0455 to the bar's inner face
  at x 0.066) between y 0.035 and 0.125.
- **`Grip`:** at **(0.074, 0.08, 0)**, rotated 90 degrees about +Y: its **+Y runs up the handle**, its **-Z points
  from the handle toward the mug's axis** (-X of the mug: the palm faces the mug), its +X along the mug's -Z. Read
  back from the GLB (`report.json` `gltf.grip`) and from Godot's import (`report.json` `godot.grip`).
- **Placing it in a hand:** instance the GLB under the socket and set its transform to
  `Grip.transform.affine_inverse()`, so `Grip` lands on the socket:
  - first person: under the hands' `MugSocket` (`fp_hands.glb`), on the hands' render layer, no shadow; the socket's
    own scale (1.3) draws the mug bigger in first person, like `CrystalSocket` the crystal; keep that scale on the
    socket as imported and give the mug only `Grip.transform.affine_inverse()` (never reset the socket's scale or
    apply 1.3 to the mug again); play `Mug_Idle` or `Mug_Run` while a `mug` or `mug_empty` is held;
  - other players: under `Socket_HandR` (the art contract, `contract/contract.toml`) at true size; the body's clips
    do not change for it in M8.
- **Budget:** 1,680 triangles with the beer, no textures (10 players may each hold one). No label, no text.
- No drinking motion: a new visible animation waits for the engineer's yes; until then the drink hides `Beer`.

## Look notes for the game

- The glass is alpha-blended (`mug_glass`, alpha 0.14); the beer's body too (alpha 0.94). Sorting against other
  transparent things in the bar is the game's renderer's.
