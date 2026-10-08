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
| `kind` | `body`, `clothing`, `hair`, `face`, `accessory`, `item`, `prop` or `animation`; equal to the folder under `assets/` |
| `slot` | The cosmetic slot the asset fills (table below); `""` for a kind that fills none |
| `title`, `notes` | Optional strings |
| `source.service` | Who made it: `meshy`, `quaternius`, `own`, ... |
| `source.plan` | The plan or terms it was made under: `pro-monthly`, `standard-free`, ... Free-plan AI output is refused |
| `source.model_version` | The generator's model version; required when `ai_generated` is true, else may be `""` |
| `source.task_ids` | The generator's task ids (generation, rig, animation); at least one when `ai_generated` is true |
| `source.generated_at` | A TOML date or date-time: when it was generated or downloaded |
| `source.url` | Optional: the page it came from |
| `[[raw]]` | One or more: `file` (a path relative to the raw folder, `/` separators, no `..`) and `sha256` (64 lowercase hex digits) |
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
| `body`, `item`, `prop`, `animation` | `""` |

Sets are saved presets of pieces, not assets, so they have no manifest. The slot names follow the character contract
(`contract/`, issue #4); if the contract renames a slot, `tools/runner/commands/_manifest.py` follows it.

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
