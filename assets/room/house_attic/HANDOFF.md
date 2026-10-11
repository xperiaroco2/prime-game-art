# House package P5, the attic and the free roof: the game-side handoff (art #126, prime-game #523)

For the game's own import task, after P1 (the kit), P2 and P4 (the floor under the hatch). Nothing here is copied
before the approval fields of this manifest and of `assets/prop/house_props/manifest.toml` are set (the engineer's
look approval on the art PR).

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| P1 (`assets/kit/house_kit/HANDOFF.md`) | `assets/environment/house_kit/` (P5's room uses 27 of its pieces: floor, knee walls, gables, the pitched roof, chimneys, vents, the dormer, the hatch ladder and the dormer stair) |
| `assets/kit/house_kit/export/kit_set.gdshader`, `kit_set.tres` (#132) | `assets/environment/house_kit/` (beside the kit's textures) |
| `assets/prop/house_props/export/library/*.glb` (11), as `package.json` lists | `assets/environment/house_props/<file>.glb` (flat) |
| `assets/room/house_attic/export/attic.tscn` | the content of `levels/house/rooms/attic.tscn` (G3 below) |

`package.json` beside this file lists the package's 44 game paths with their SHA-256 (the copies must hash the same),
its room, the placeholders and the questions. The free roof is part of the attic's scene: its pitched pieces, chimneys
and dormer sit under `Shell`. Then the game's `check`, `credits`, the import check (11.3), `load`, `playcheck`, `perf`
and `shot`.

## Wall paints and the kit's look (#132)
Every kit instance under `Shell` overrides its meshes' set surfaces (`surface_material_override/<i>`) with
`res://assets/environment/house_kit/kit_set.tres`: the art's `kit_set.gdshader`, the kit's `set_d`, `set_n0`
and `set_n1` textures and the House's wall paints (`layouts/house/house.toml` `[wall_paint]`). Each such mesh
also sets `instance_shader_parameters/plan_at`, its place and turn in the house plan, so the shader paints by
the plan wherever the game puts the House. Nothing to run: copy the two files with the kit and load the scene
(the root's `metadata/wall_paint` stays as a note). The attic has no paint; the material gives the kit's textured look.

## Credits
As P2: the drafts `D:/prime-art-raw/house/export/credits/house_kit.md` and `house_props.md`; own work, the props from
CC0 packs named per file in the props manifest, `ai_generated = false`, `public_repo_ok = true`.

## Questions still open on prime-game #523
- G3 and G11 as in P2.
- G1/G2 (art task A4): the attic and the roof are among the known differences to the game's greybox (`mapping.md`).
- The free roof's own items (its loot crate) stand on the slopes and are not exported yet.
- Lights: 8 real-time `OmniLight3D` without shadows; the bake comes later (#83, G6).

## Art defaults (the game may change any)
- `mannequin` and `rocking_horse` (hero props) have no GLB yet: each is a sized `Marker3D` under `Placeholders`.
- Colliders are the GLBs' own `-convcolonly` shapes (`StaticBody3D`, layer 1); picture frames and rugs have none.
- Footsteps: the boards, the hatch ladder and the dormer stair `wood`, the floor under the rugs and the rolled carpets
  `carpet`; the pitched roof, the chimneys' tops and the dormer `concrete` (the game has no tile sound).
- The art's package check (`house --export --package 5`) is green: the scene loads with its root and `size_m`; the
  attic's 1920 rays down hit 1857 `wood` and 59 `carpet`, nothing without a surface; the roof's 2288 rays down from
  over the ridge hit 2100 `concrete` and miss 188, all past the eaves and the gables (no floor there). The hatch
  ladder's walk needs the floor under it (P4) and the dormer's climb-out has no walk in the check yet.
