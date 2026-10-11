# House package P1, the kit: the game-side handoff (art #124, prime-game #523)

For the game's own import task. Nothing here is copied before the manifest's approval fields are set (the engineer's
look approval on the art PR; ARCHITECTURE 11.2 takes an art asset only then).

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| `assets/kit/house_kit/export/<piece>.glb` (121) | `assets/environment/house_kit/<piece>.glb` |
| `assets/kit/house_kit/export/textures/set_d.png`, `set_n0.png`, `set_n1.png` | `assets/environment/house_kit/set_d.png`, `set_n0.png`, `set_n1.png` |

`package.json` beside this file lists the 124 game paths with their SHA-256 (the copies must hash the same), the
pieces' footstep surfaces (`surfaces`) and the questions below. Then run the game's `check` and commit the `.import`
files it writes (ARCHITECTURE 11.2: GLBs `nodes/root_type=""`, `root_scale=1.0`, `apply_root_scale=true`,
`animation/import=true`; PNGs `compress/mode=2`), `credits`, and the import check (11.3) locally with LFS content.

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
