# House package P2, the shell and the ground floor: the game-side handoff (art #124, prime-game #523)

For the game's own import task, after P1 (the kit). Nothing here is copied before the approval fields of this
manifest and of `assets/prop/house_props/manifest.toml` are set (the engineer's look approval on the art PR). P2 was approved and merged
(#125, 2026-10-11); #147 changed it (the C2-white kitchen, the fine pack, the Detail node, below), so both
manifests' approval fields are empty again until the engineer approves #147's sheet.

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| P1 (`assets/kit/house_kit/HANDOFF.md`) | `assets/environment/house_kit/` (P2's rooms use 17 of its pieces) |
| `assets/kit/house_kit/export/kit_set.gdshader`, `kit_set.tres` (#132) | `assets/environment/house_kit/` (beside the kit's textures) |
| `assets/prop/house_props/export/library/*.glb` (68), `task/*.glb` (4) | `assets/environment/house_props/<file>.glb` (flat) |
| `assets/prop/house_props/export/fine/high/*.png`, `fine/low/*.png` (3 each, #147) | `assets/environment/house_props/fine/high/`, `fine/low/` |
| `assets/prop/house_props/export/prop_fine.gdshader`, `prop_fine_high.tres`, `prop_fine_low.tres` (#147) | `assets/environment/house_props/` |
| `assets/room/house_ground/export/<room>.tscn` (15) | the content of `levels/house/rooms/<room>.tscn` (G3 below) |

`package.json` beside this file lists the package's 118 game paths with their SHA-256 (the copies must hash the
same), its rooms (game node, level, kit and prop counts), the placeholders and the questions. The 15 rooms: `wc`,
`pantry`, `dining_room`, `living_room`, `stairs`, `kitchen`, `hallway`, `terrace`, `yard`, `street`, `path`,
`driveway`, `photo_zone`, `chill_zone`, `outdoor_stairs` (the ground floor without the garage, the greenhouse and the
garden). Each scene keeps the game room's root name, origin, `metadata/size_m`, `Name` label, `Doors`, `Stations`
and `Markers`, and adds `Shell` (kit instances, walkable ones with `metadata/surface`), `Dressing`, `Detail` (#147),
`Fixtures` (lamps) and `Placeholders`. Then the game's `check` (commit the `.import` files it writes), `credits`, the import
check (11.3) locally with LFS content, `load`, `playcheck`, `perf` and `shot`.

## Wall paints and the kit's look (#132)
Every kit instance under `Shell` overrides its meshes' set surfaces (`surface_material_override/<i>`) with
`res://assets/environment/house_kit/kit_set.tres`: the art's `kit_set.gdshader`, the kit's `set_d`, `set_n0`
and `set_n1` textures and the House's wall paints (`layouts/house/house.toml` `[wall_paint]`). Each such mesh
also sets `instance_shader_parameters/plan_at`, its place and turn in the house plan, so the shader paints by
the plan wherever the game puts the House. Nothing to run: copy the two files with the kit and load the scene
(the root's `metadata/wall_paint` stays as a note). Painted here: the kitchen, hallway, living and dining rooms and the stairs, teal #3a6264 (the kit's
own plaster, so the colour stays and the textures are new).

## The C2-white kitchen, the fine pack and the Detail node (#147)
- **What changed.** The kitchen's props are rebuilt in the House's world look (C2-white, art #143, the ADR
  `docs/decisions/2026-10-13-house-world-look.md`): `fridge`, `stove`, `kitchen_counter`, `kitchen_sink`,
  `kitchen_upper`, `assembly_island`, `order_board` replace their old GLBs (same file names), and two new
  `backsplash_l.glb`, `backsplash_r.glb` (tiled strips with a steel cap) stand on the kitchen's north-wall worktop runs.
  The pantry's shelves are `kitchen_upper` too, so the pantry shows the new cabinet. The kitchen's clutter was
  re-seeded (2 items fewer).
- **The fine material.** The rebuilt props carry a `kit_fine` material: vertex colour paint, the alpha picks one of
  the fine layers (wood fronts, worktop wood, stone, tile; enamel, steel, chrome, gloss, paint). The room scenes
  already override every `kit_fine` surface (`surface_material_override/<i>`) with
  `res://assets/environment/house_props/prop_fine_high.tres`: `prop_fine.gdshader` with the shared `fine_d`, `fine_n0`,
  `fine_n1` textures. A game-side wrapper of a prop applies `kit_fine` -> that material by name, as with the kit's
  `set`. Import the PNGs VRAM compressed with mipmaps (`compress/mode=2`, `mipmaps/generate=true`; the shader reads
  them `filter_linear_mipmap_anisotropic`, the normal maps as plain data).
- **Tier per preset (a proposal; the game decides).** High and Ultra: `prop_fine_high.tres` (1024 px, 3 PNGs 7.2 MB on
  disk). Low and Medium: `prop_fine_low.tres` (512 px, 1.8 MB), swapped on the overrides when the preset loads (or
  set the high resource's three textures and `layer_gain` from the low one: the gain differs per tier).
- **The Detail node.** Each room's `detail`-layer props (`props/library.toml` `[layers]`: the clutter) sit under
  `Detail` beside `Dressing` and `Fixtures`; base props stay in `Dressing`. Proposal for #140 item 4: Low hides
  `Detail` (`visible = false`, its colliders off), Medium and up show it. Task stations, fixtures and the shell never sit there.
- **LFS.** #147 adds 9.8 MB of LFS objects: the 9 GLBs (0.84 MB, the 7 replaced weighed 0.43 MB) and the 6 PNGs
  (8.96 MB).

## Credits
The entries are `assets/kit/house_kit/CREDITS.md` and `assets/prop/house_props/CREDITS.md` in this repo (the game's
`docs/credits/<id>.md` format; copy them to `docs/credits/house_kit.md` and `house_props.md`): own work, the props made
from CC0 packs named per file in the props manifest, the fine pack from four ambientCG CC0 maps (#147),
`ai_generated = false`, `public_repo_ok = true`. The room scenes are scenes under `levels/`, not assets: no credits
entry unless the game wants one.

## Questions still open on prime-game #523
- G3: the room scenes are written as `levels/house/rooms/<room>.tscn` (11.1 keeps `assets/` data only); the game's
  workflow swaps them into its greybox rooms (`Body`/`Looks` out, `Shell`/`Dressing`/`Fixtures` in).
- G11: the props are a set, one flat folder with a GLB per prop.
- G1/G2 (art task A4): the six known differences to the game's greybox rooms (`mapping.md`: attic, roof, garage
  Door3, landing Door6, study Door1, storage Package07) are all in later packages; P2's rooms match the greybox.
- Lights: every fixture is a real-time `OmniLight3D` without shadows (77 in this package); the bake comes later
  (#83, G6).
- The outdoor rooms (`yard`, `street`, `path`, `driveway`, `photo_zone`, `chill_zone`) carry only their markers and
  lamps here: their ground, fence and props are the plot, package 7.

## Art defaults (the game may change any)
- `door_leaf` has no GLB yet: each door leaf is a sized `Marker3D` under `Placeholders` (never CSG).
- Colliders are the GLBs' own `-convcolonly` shapes (`StaticBody3D`, layer 1); rugs have none, so the floor tiles
  at least half under a rug carry `carpet`.
- The art's package check (`house --export --package 2`) is green: every scene loads with its root and `size_m`,
  10/10 capsule walks arrive, none of the 25536 rays down hits a shell collider without a surface (80 hit nothing).
