# House package P5, the attic and the free roof: the game-side handoff (art #126, prime-game #523)

For the game's own import task, after P1 (the kit), P2 and P4 (the floor under the hatch). Nothing here is copied
before the approval fields of this manifest and of `assets/prop/house_props/manifest.toml` are set (the engineer's
look approval on the art PR). P5 was approved and merged in #127 (2026-10-11); #150 re-exported it, so they wait again (below).

## What to copy where (ARCHITECTURE 11.1)
| From this repo | To the game repo |
|---|---|
| P1 (`assets/kit/house_kit/HANDOFF.md`) | `assets/environment/house_kit/` (P5's room uses 27 of its pieces: floor, knee walls, gables, the pitched roof, chimneys, vents, the dormer, the hatch ladder and the dormer stair) |
| `assets/kit/house_kit/export/kit_set.gdshader`, `kit_set.tres` (#132) | `assets/environment/house_kit/` (beside the kit's textures) |
| `assets/prop/house_props/export/library/*.glb` (24), as `package.json` lists | `assets/environment/house_props/<file>.glb` (flat) |
| `assets/prop/house_props/export/fine/high/*.png`, `fine/low/*.png` (6 each, #147, #150) | `assets/environment/house_props/fine/high/`, `fine/low/` |
| `assets/prop/house_props/export/prop_fine.gdshader`, `prop_fine_high.tres`, `prop_fine_low.tres` (#147) | `assets/environment/house_props/` |
| `assets/room/house_attic/export/attic.tscn` | the content of `levels/house/rooms/attic.tscn` (G3 below) |

`package.json` beside this file lists the package's 72 game paths with their SHA-256 (the copies must hash the same),
its room, the placeholders and the questions. The free roof is part of the attic's scene: its pitched pieces, chimneys
and dormer sit under `Shell`. Then the game's `check`, `credits`, the import check (11.3), `load`, `playcheck`, `perf`
and `shot`.

## Wall paints and the kit's look (#132)
Every kit instance under `Shell` overrides its meshes' set surfaces (`surface_material_override/<i>`) with
`res://assets/environment/house_kit/kit_set.tres`: the art's `kit_set.gdshader`, the kit's `set_d`, `set_n0`
and `set_n1` textures and the House's wall paints (`layouts/house/house.toml` `[wall_paint]`). Each such mesh
also sets `instance_shader_parameters/plan_at`, its place and turn in the house plan, so the shader paints by
the plan wherever the game puts the House. Nothing to run: copy the two files with the kit and load the scene
(the root's `metadata/wall_paint` stays as a note). The attic's knee walls and gables carry a warm white (`#ece7de`, #168) under the warm sand roof.

## The rebuilt props, the fine pack and the Detail node (#150)
P5 is re-exported for #150: its scenes place the rebuilt rug (`docs/props.md`, the living room's pieces;
same file names, new bytes) and override their `kit_fine` surfaces with
`res://assets/environment/house_props/prop_fine_high.tres`, so the package lists the fine pack (the 6 PNGs per
tier, the shader, the two `.tres`; one copy per game, P2's `HANDOFF.md`). Every room also gains #147's `Detail`
node beside `Dressing` and `Fixtures` (empty here until a room's detail pass). The approval fields wait for the
engineer's yes.

## The engineer's paints of 2026-10-14 (#152)

Only `package.json` changed: the shared `kit_set.tres` carries the new wall paints and the rebuilt kit pieces of the
warm sand ceiling hash anew; this package's scenes are unchanged.

## The WC's and the pantry's paints (#158)

Only `package.json` changed: the shared `kit_set.tres` carries the WC's and the pantry's paints and hashes anew;
this package's scenes are unchanged.

## The bathroom's paint (#162)

Only `package.json` changed: the shared `kit_set.tres` carries the bathroom's paint and hashes anew; this
package's scenes are unchanged.

## The kids' room's paint (#166)

Only `package.json` changed: the shared `kit_set.tres` carries the kids' room's paint and hashes anew; this
package's scenes are unchanged.

## The attic, a well-kept family attic (#168)

The attic (63 items, 24 different props; main had 44 and 11) is dressed as a well-kept family attic on a new warm
white paint: steel shelving runs and a back-to-back island loaded with labelled boxes and plastic crates, a sofa and
a dresser under dust sheets, a white wardrobe, suitcases, a rolled rug, holiday decorations, the rocking horse and a
dress form, framed pictures leaning on the knee wall, a city bike, sports kit and the game's own burger-stall sign,
retired delivery bag and generator part. Changed: `attic.tscn` and `package.json` (14 new props in `house_props`:
`attic_shelving`, `attic_shelving_b`, `storage_box`, `storage_crate`, `sheeted_sofa`, `sheeted_dresser`,
`leaning_frames`, `holiday_decor`, `rocking_horse`, `mannequin`, `sports_kit`, `burger_sign`, `delivery_bag`,
`generator_part`; `old_wardrobe`, `sheeted_furniture`, `old_bicycle` and `trunk` rebuilt, same names; `cardboard_box`,
`crate` and `picture_frame` leave the package; the shared `kit_set.tres` carries the new paint). The twelve hiding
spots, the pick-ups, the clear areas and the free roof's items stay. Draw calls on the package sheet, before/after:
from the north wall 54/69, from the west gable 52/68,
from the hatch 32/41, toward the dormer 45/58, the roof from the dormer 38/44, from the lookout 54/64. Re-exported
into `<raw>/review/house/168/export/p5`, then `p5b` for the gables' paint band (`attic.tscn` the same bytes;
`package.json` names the new `kit_set.tres` hash).

## Credits
As P2: the entries `assets/kit/house_kit/CREDITS.md` and `assets/prop/house_props/CREDITS.md` (copy them to
`docs/credits/house_kit.md` and `house_props.md`); own work, the props from
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

## Merged shell (#107)

Draw calls, not the look. Each room's own static kit pieces of a class (floors, ceilings, the rest of the shell) are
drawn by one merged mesh per material, `Shell/merged_<class>` (`house_kit/merged/<class>_m_<level>_<room>.glb`, the
kit's set material on its `kit_set` surfaces with `plan_at` at the room's origin), and each room's static dressing by
one mesh per group, `Dressing/batch_dressing`, `Detail/batch_detail`, `Fixtures/batch_fixtures`
(`house_props/merged/batch_*.glb`, the fine material on its `kit_fine` surfaces; a preset hiding `Detail` hides its
batch too). Here: 2 merged shell meshes and 1 batches, committed in `export/merged/`
(copy them to `assets/environment/house_kit/merged/` and `assets/environment/house_props/merged/`, as
`package.json` lists them).
- Every piece and prop instance is still there with its name, transform, colliders and metadata (`surface`,
  `station`, `prop`); only its own mesh node carries `visible = false`. `test_house_contract` checks every
  game-facing node and collider of this package against main's export (layouts/house/export_contract.json): unchanged.
- Never merged: the pieces the game moves or opens (house.toml `[merge] keep`: gates, wicket, garage door, glass door,
  the attic ladder and hatch boards), task stations and `[merge] keep_props` (the garage's car, lift arms and lift
  panel). A game-side script that moves another prop must move it out of its batch (ask the art side).
- Numbers: the export sheet's attic views draw 66 and 68 calls before, 15 and 15 after.
