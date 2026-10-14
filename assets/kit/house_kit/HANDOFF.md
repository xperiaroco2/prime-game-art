# House package P1, the kit: the game-side handoff (art #124, prime-game #523)

For the game's own import task. Nothing here is copied before the manifest's approval fields are set (the engineer's
look approval on the art PR; ARCHITECTURE 11.2 takes an art asset only then). They are set: P1 is approved
and merged (#125, 2026-10-11).

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| `assets/kit/house_kit/export/<piece>.glb` (121) | `assets/environment/house_kit/<piece>.glb` |
| `assets/kit/house_kit/export/textures/set_d.png`, `set_n0.png`, `set_n1.png` | `assets/environment/house_kit/set_d.png`, `set_n0.png`, `set_n1.png` |

`package.json` beside this file lists the 124 game paths with their SHA-256 (the copies must hash the same), the
pieces' footstep surfaces (`surfaces`) and the questions below. Then run the game's `check` and commit the `.import`
files it writes (ARCHITECTURE 11.2: GLBs `nodes/root_type=""`, `root_scale=1.0`, `apply_root_scale=true`,
`animation/import=true`; PNGs `compress/mode=2`), `credits`, and the import check (11.3) locally with LFS content.

## The engineer's paints of 2026-10-14 (#152)

The ceiling is warm sand `#d8c7b4` (the kit's `ceiling` role; it was slate `#3c4652`): the 12 pieces that carry
it change bytes under the same names: `ceiling_1x1`, `ceiling_2x2`, the board and lino floors (`floor_boards_1x1`,
`floor_boards_2x1`, `floor_boards_2x2`, `floor_boards_2x2_hatch`, `floor_lino_1x1`, `floor_lino_2x2`; their
undersides are the ceilings below), `roof_flat_1x1`, `roof_flat_2x2`, `slab_edge_1m`, `slab_edge_2m`. `kit_set.tres`
carries the new wall paints. P1's `package.json` now also lists `kit_set.gdshader` and `kit_set.tres`.

## The WC's and the pantry's paints (#158)

`kit_set.tres` now carries the WC's soft blue-grey (#CFD5D3) and the pantry's pale sage (#D3D6C3) beside the
other rooms' paints; no kit piece changed. Copy it over the game's `house_kit/kit_set.tres`.

## The bathroom's paint (#162)

`kit_set.tres` now carries the bathroom's pale green-grey (#D8DFD6) beside the other rooms' paints; no kit
piece changed. Copy it over the game's `house_kit/kit_set.tres`.

## The kids' room's paint (#166)

`kit_set.tres` now carries the kids' room's pale sky blue (#C9D7DE) beside the other rooms' paints; no kit
piece changed. Copy it over the game's `house_kit/kit_set.tres`.

## The attic's paint (#168)

`kit_set.tres` now carries the attic's warm white (#ECE7DE, its knee walls and gables) beside the other rooms'
paints; no kit piece changed. Copy it over the game's `house_kit/kit_set.tres`.


## Credits
The entry is `CREDITS.md` beside this file (the game's `docs/credits/<id>.md` format; copy it to
`docs/credits/house_kit.md`): own work, plus the three textures made from ambientCG CC0 maps, `ai_generated = false`,
`public_repo_ok = true`. Its `Source` line names this manifest and the approval PR (#125); then `tools\run.cmd credits`.

## Questions still open on prime-game #523
- G3/G11: the kit is a set, one folder with a GLB per piece, not 11.1's `<id>/<id>.glb`.
- Kit look: the GLBs carry vertex-colour materials; the textured look needs the art's `kit_set.gdshader` with the
  shared `set_d`/`set_n0`/`set_n1` textures. A shader is not data under `assets/`: who owns it on the game side?
- Surfaces: the kit's GLBs carry no `surface`; a game-side wrapper of a piece (`levels/kit/`) takes it from
  `package.json`'s `surfaces` (23 walkable pieces).
- Imports: the export's minimal `.import` files are not committed here; the game's editor writes its own on the first
  import (with uids): commit those.

## Art defaults (the game may change any)
- 1 unit = 1 m, +Y up, pieces on the 1 m grid with their pivot at a corner on the floor (`docs/kit.md`).
- Colliders are each GLB's own `-convcolonly` shapes: a `StaticBody3D` on layer 1 after import.
- The kit keeps a second UV set for a later lightmap bake (#83); no lightmaps ship yet.
