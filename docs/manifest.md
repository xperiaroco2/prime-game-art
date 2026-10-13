# The asset manifest

Every asset in this repository lives in `assets/<kind>/<id>/` with a `manifest.toml` beside its `source/` and
`export/` folders. The manifest is the asset's provenance and licence record: where it came from, which raw files it was
made from, which tools touched it, what licence applies, whether it may ever reach the public game repo and who approved
it. `tools/run.py manifest-check` validates every manifest; `verify` runs it.

Raw generations and downloads never enter git (they live in `D:/prime-art-raw`); the manifest records their paths
relative to that folder and their SHA-256, so a raw file can be found and checked later.

## Example

```toml
id = "top_waders"                    # = the folder name: lowercase letters, digits, underscores
kind = "clothing"                    # = the parent folder: assets/clothing/
slot = "top"
title = "Waders top"                 # optional
tools = ["meshy-6", "blender 5.2.2"]
licence = "owned-paid-output"
licence_url = "https://www.meshy.ai/terms-of-use"
public_repo_ok = true
ai_generated = true
approved_by = ["xperiaroco2"]
approved_at = 2026-10-10
approval_pr = "https://github.com/xperiaroco2/prime-game-art/pull/12"

[source]
service = "meshy"
plan = "pro-monthly"
model_version = "meshy-6"
task_ids = ["0199a1b2-0000-7000-8000-000000000002"]
generated_at = 2026-10-04T19:20:00Z
url = "https://www.meshy.ai"         # optional

[[raw]]
file = "2026-10-04-batch-2/top_waders.glb"
sha256 = "<64 lowercase hex digits>"
```

TOML puts every key after a `[table]` header into that table, so the top-level keys come first.

## Fields

| Field | Rule |
|---|---|
| `id` | Lowercase letters, digits and underscores; equal to the asset's folder name |
| `kind` | `body`, `character` (an assembled game character: body, outfit, face and clips in one GLB, art #42), `clothing`, `hair`, `face`, `accessory`, `item`, `prop`, `animation`, `kit` (a modular kit's pieces), `room` (room scenes) or `environment` (an outdoor or garden package); equal to the folder under `assets/` |
| `slot` | The cosmetic slot the asset fills (table below); `""` for a kind that fills none |
| `title`, `notes` | Optional strings |
| `source.service` | Who made it: `meshy`, `quaternius`, `own`, ... |
| `source.plan` | The plan or terms it was made under: `pro-monthly`, `standard-free`, ... Free-plan AI output is refused |
| `source.model_version` | The generator's model version; required when `ai_generated` is true, else may be `""` |
| `source.task_ids` | The generator's task ids (generation, rig, animation); at least one when `ai_generated` is true |
| `source.generated_at` | A TOML date or date-time: when it was generated or downloaded |
| `source.url` | Optional: the page it came from |
| `[[raw]]` | One or more: `file` (a path relative to the raw folder, `/` separators, no `..`) and `sha256` (64 lowercase hex digits); a set manifest may leave it out (its `[[files]]` are its raw files) |
| `[[files]]` | Only in a set manifest (below): one table per shipped file |
| `tools` | A non-empty list: the generator and every tool that changed the asset, with versions |
| `licence` | `CC0-1.0`, `CC-BY-4.0`, `owned-paid-output`, `own-work` or `restricted` (private only: Mixamo, store packs, raw library motions, anything unclear) |
| `licence_url` | An http(s) URL to the licence or the terms that applied on `generated_at` |
| `credit` | The attribution line; required for `CC-BY-4.0` |
| `public_repo_ok` | `true` only if the asset may enter the public game repo; never with `restricted` |
| `ai_generated` | `true` for any AI generator's output |
| `approved_by` | GitHub logins of the approvers: the engineer for the look (he acts as the designer; earlier manifests may also list `SwiftySinister`), and for what he decided (taste, money, licences); `[]` until approved. The tech approval is the approving PR's merge after the gate (the trust model, `docs/decisions/2026-10-03-trust-model.md`) |
| `approved_at` | A TOML date or date-time; `""` until approved |
| `approval_pr` | The art-repo pull request URL that approved it; `""` until approved |

Approval is all or nothing: `approved_by`, `approved_at` and `approval_pr` are set together, in the approving PR,
after the look is approved and before the merge. The game repo takes an asset only with all three set.

Unknown keys are refused, so a typo cannot hide a missing field.

## Slots

| Kind | Slots |
|---|---|
| `clothing` | `top`, `bottom`, `shoes` |
| `hair` | `hair_or_hat` (a hairstyle; a hat takes the same slot) |
| `face` | `eyes`, `mouth` (changeable like the hairstyle) |
| `accessory` | `hair_or_hat` (a hat), `face_accessory`, `back_item` |
| `body`, `character`, `item`, `prop`, `animation`, `kit`, `room`, `environment` | `""` |

A character's outfit sets are saved presets of pieces, not assets, so they have no manifest. The slot names follow the
character contract (`contract/`, issue #4); if the contract renames a slot, `tools/runner/commands/_manifest.py` follows
it.

## Set manifests

A package of many files built together (the House's kit, its props, its garden, its plot; #118) has one manifest for
the whole set rather than one per piece. Its kind is `kit`, `room`, `environment` or `prop`; a character kind cannot be
a set. Each shipped file gets a `[[files]]` table:

```toml
[[files]]
name = "library/armchair.glb"            # its path inside the set's export/ folder
file = "props/library/v1/armchair.glb"   # where it was built, relative to the raw folder
sha256 = "<64 lowercase hex digits>"
source = "kaykit_furniture_bits"          # only for a file made from a pack: its source record
from = ["env/kaykit/furniture-bits/.../armchair_pillows.gltf"]  # that record's [[raw]] files it was made from
```

| Field | Rule |
|---|---|
| `name` | A relative path inside the set's `export/` folder; each name once |
| `file` | A relative path inside the raw folder; each file once |
| `sha256` | 64 lowercase hex digits |
| `source` | Optional: the id of a source record, `sources/<id>.toml`, that must exist; needed with `from` |
| `from` | Optional: the raw files of that record the file was made from, each listed in the record's `[[raw]]` |

The set's own top-level `licence` covers the files without a `source` (for the art's own work, `own-work`); a file
with a `source` also carries its record's licence, so a set with `public_repo_ok = true` may name only records that are
public themselves. `manifest-check --hashes` re-hashes every `file` in the raw folder and every `name` already in
`export/`; a set is built in the raw folder first and its exports are committed once approved.

The House's sets (written for #118 from the 2026-10-10 builds; a rebuild changes their hashes):

| Manifest | Files |
|---|---|
| `assets/kit/house_kit/` | the kit v3b's 121 GLBs (with the greenhouse's 5 glass roof pieces, byte-identical in `house/80/kit`) and the shared texture set `textures/set_d.png`, `set_n0.png`, `set_n1.png`, made from 6 ambientCG maps |
| `assets/prop/house_props/` | `library/` 133 (30 from CC0 packs, named by `source` and `from`; #147 rebuilt the kitchen's in C2-white and added `backsplash_l`, `backsplash_r`), `task/` 34, `zones/` 9 GLBs; they use the kit's texture set, the world look's props also the fine pack (#147): `fine/high/` and `fine/low/` `fine_d.png`, `fine_n0.png`, `fine_n1.png`, made from 4 ambientCG maps, with `prop_fine.gdshader`, `prop_fine_high.tres`, `prop_fine_low.tres` |
| `assets/environment/house_garden/` | the 14 garden plants of `house/80/plants` |
| `assets/environment/house_outdoor/` | `outdoor.glb`, `backdrop.glb` (the flats embedded) and `sky.png` of `house/81/build` |
| `assets/room/house_ground/` | package P2's 15 room scenes (`<room>.tscn`, the game's `levels/house/rooms/`) of `house/export/v4/p2` (#124; re-exported for #147) |
| `assets/room/house_basement/` | package P3's 8 room scenes of `house/export/v3/p3` (#126) |
| `assets/room/house_attic/` | package P5's room scene, the attic with the free roof, of `house/export/v3/p5` (#126) |
| `assets/room/house_upper/` | package P4's 7 room scenes, the second floor with the balcony and its external stairs, of `house/export/v3/p4` (#129) |
| `assets/room/house_plot/` | package P7's plot scene `outdoor.tscn` (the game's `levels/house/`) and the greenhouse and garden room scenes of `house/export/v3/p7` (#128) |

A set's `export/` folder holds its committed files under their manifest names, which need not be the game's paths:
the kit's textures are `textures/set_*.png` and the props `library/`, `task/` and `zones/` here, all flat in the game's
`assets/environment/house_kit/` and `house_props/` (the package's `package.json` and the set's `HANDOFF.md` map them;
`house --package-sheet` stages them by SHA-256). Only what an approved package needs is committed: P1 the whole kit, P2
its 70 props (#124; 72 since #147's two backsplash runs: 68 library, 4 task), P3 and P5 the 34 more they use (#126), P4 10 more (#129), P7 32 more (#128). P1 to P5 and P7 are approved and merged, their manifests' approval fields set: P1 and P2 in #125, P3 and P5
in #127, P4 in #130, P7 (with the props, the outdoor and garden sets) in #131. #147 changed P2 and the props (the C2-white kitchen, the fine pack): their
approval fields are empty again until the engineer approves its sheet. A prop id names one game file: the export takes it from
`house.toml`'s `prop_dirs` in order (the task props first), so of the ids both `task/` and `library/` hold (`boiler`,
`pump`, ...) only the task prop ships. P7 (#128) adds the zones' props, and 17 basenames repeat between `task/`,
`library/` and `zones/`: the first source in `prop_dirs`, then `[export.plot]` `prop_src`'s other folders, that holds
`<id>.glb` ships it as `<id>.glb` (the names P2, P3 and P5 shipped), any other source's as `<id>_<source>.glb`
(`birdbath_library.glb`, `deckchair_zones.glb`; `house_export_plot.game_name`, tested over all raw props). Room scenes (`room`) get one set per package. Own work is `own-work` with
`public_repo_ok = true` and goes to the game under the game's terms (the engineer's E1, 2026-10-11): the game repo is
public with no licence file, so all rights reserved, and `licence_url` points to it
(`https://github.com/xperiaroco2/prime-game`), not to this private repo.

## Clips

A `character` or `animation` manifest lists the clips its export carries, one `[[clips]]` table each, because one
GLB mixes sources (art #42 part C, `assets/character/slice_m1/`: Quaternius CC0 clips and Meshy text-to-motion):

```toml
[[clips]]
name = "Pickup_Package"                       # the action and glTF animation name
loop = false
source = "tm:package-lift"                    # the clip key it is built from (through `from`)
record = "batches/2026-10-b5-anim-mvp.toml"   # a source record id, or the Meshy batch file
licence = "owned-paid-output"
licence_url = "https://www.meshy.ai/terms-of-use"
public_repo_ok = true
ai_generated = true
task_id = "01a110b7-..."                      # required for an AI-generated clip
```

Names are listed once; a record that is not a `batches/` file must be a source record; a `public_repo_ok` asset
carries only public clips (a private clip stays out of the export and is listed in `notes`), and an AI-generated clip
makes the asset `ai_generated`. The asset's own `licence` covers the art's own work (`own-work`, the game's terms).

## Credits for the game

The game takes an asset with `docs/credits/<id>.md` in its own format (its `docs/ARCHITECTURE.md` section 11.2, example
`docs/credits/kenney_chair.md`): `Files`, `Author`, `Source` (the art manifest, or the download page with the file's
SHA-256), `License` with its URL, `AI generated` and `Public repo OK`. `house --export` drafts them into the raw
folder, `house/export/credits/<id>.md`; an approved set commits its entry as `CREDITS.md` beside its manifest (the
House's: `assets/kit/house_kit/`, `assets/prop/house_props/`, `assets/environment/house_outdoor/` and
`house_garden/`), and the game's own task workflow copies it into its PR as `docs/credits/<id>.md`.

## Source records

A pack or library that assets are made from (a download, not an asset itself) has a source record,
`sources/<id>.toml`: its page, its licence and every raw file it brought, hashed. An asset made from it names the
same raw files in its own manifest. `manifest-check` validates every source record beside the manifests.

```toml
id = "quaternius_ultimate_modular_men"   # = the file name without .toml
title = "Ultimate Modular Men Pack"
author = "Quaternius"
url = "https://quaternius.com/packs/ultimatemodularcharacters.html"
licence = "CC0-1.0"
licence_url = "https://creativecommons.org/publicdomain/zero/1.0/"
public_repo_ok = true
ai_generated = false
downloaded_at = 2026-10-03
notes = "..."                              # optional

[[raw]]
file = "refs/Ultimate Modular Men Pack-glb.zip"
sha256 = "<64 lowercase hex digits>"

[[raw]]
file = "refs/Ultimate_Modular_Men_Pack/Adventurer.glb"
sha256 = "<64 lowercase hex digits>"
```

| Field | Rule |
|---|---|
| `id` | Lowercase letters, digits and underscores; equal to the file name |
| `title`, `author` | Non-empty strings: the pack's name and its maker |
| `url` | The http(s) page it was downloaded from (the official page, not a mirror) |
| `licence`, `licence_url`, `credit`, `public_repo_ok`, `ai_generated` | As for assets (above); `credit` is required for `CC-BY-4.0` |
| `downloaded_at` | A TOML date or date-time |
| `notes` | Optional string |
| `[[raw]]` | One or more, as for assets: the downloaded archive and every file unpacked from it that is used, each listed once |

## Commands

- `tools/run.py manifest-check`: every manifest under `assets/`, every `assets/<kind>/<id>/` folder without one, and
  every source record in `sources/`.
- `tools/run.py manifest-check --hashes`: also re-hashes each `[[raw]]` file of the manifests and source records in the
  raw folder (`ART_RAW_DIR`, default `D:/prime-art-raw`). Only on the engineer's PC, where the raw folder exists.
- `tools/run.py manifest-check --root <dir>`: checks another tree; the tests use the fixtures in
  `tools/tests/fixtures/manifest/` (`pass` and `fail`).
