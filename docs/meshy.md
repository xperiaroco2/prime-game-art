# Meshy client

`tools/run.py meshy` (`tools\run.cmd meshy` on Windows) runs the engineer's approved generation batches against the
Meshy API without a human at the keyboard, downloads every result into the raw folder and records each generation.
`tools/run.py raw-backup` copies chosen results to the OneDrive backup. Code: `tools/runner/commands/meshy.py`,
`_meshy_api.py` (HTTP, key, polling), `_meshy_batch.py` (batch files, prices), `_meshy_run.py` (the run) and
`raw_backup.py`; tests: `tools/tests/test_meshy_*.py` (a fake transport, no network).

## Commands

| Command | Network | What it does |
|---|---|---|
| `meshy estimate <batch>` | none | Credits per stage, per item and in total, the approved cap and whether the approval is complete |
| `meshy run <batch> [item ...] [--retry-failed]` | spends credits | Refuses a batch without approval or over its cap; then submits, polls, downloads and records each item |
| `meshy balance` | read only | The account's credit balance (spends nothing) |
| `meshy status <batch>` | none | Each item's state from its `generation.json`; flags downloaded files that went missing |
| `raw-backup <batch> [item ...]` | none | Copies finished items (files, `generation.json`, `log.csv`) to `common.raw_backup_dir()`, sha256-checked |

`<batch>` is a path (`batches/2026-10-b1-bodies.toml`) or a bare id (`2026-10-b1-bodies`).

## The key

The client reads `MESHY_API_KEY` with `common.env` (the process environment, else the Windows user environment, so no
restart is needed after setting it). The key goes only into the `Authorization: Bearer` header of api.meshy.ai calls;
result downloads are signed asset links and get no key. Every error message and log line passes through `redact`, a
failed command's message is redacted once more, and no exception chain or traceback leaves the command. A missing
key fails with these steps for the engineer:

1. Sign in at meshy.ai on the paid plan and open <https://www.meshy.ai/developers>, API Keys.
2. Create a key (a monthly credit limit on the key is a good second cap) and copy it; never paste it into chat or a file.
3. PowerShell: `[Environment]::SetEnvironmentVariable("MESHY_API_KEY", "<the key>", "User")`.
4. `tools\run.cmd meshy balance` must print the balance.

## Batch files

`batches/<id>.toml` is committed: prompts and parameters are durable knowledge, and the file is what the engineer
approved. Changing a prompt or a parameter needs a new approval.

| Key | Meaning |
|---|---|
| `id` | Equals the file name; lower-case letters, digits, `.`, `_`, `-` |
| `purpose` | One sentence on why the batch exists |
| `plan`, `terms_url` | The Meshy plan and terms the generations fall under; copied into every `generation.json` |
| `credit_cap` | The most credits the approval covers |
| `approved_by`, `approved_at`, `approval_ref` | Who approved, the date (`YYYY-MM-DD`) and a `https://github.com/` link to the yes |
| `[variants.<name>]` | Shared settings of a variant: `prompt`, optional `preview`/`refine` tables |
| `[defaults.text_to_3d.preview]`, `[defaults.text_to_3d.refine]` | Request parameters for every text-to-3D item |
| `[defaults.rig.params]`, `[defaults.animate.params]` | Request parameters for every rig or animation item |
| `[[items]]` | `id`, `variant`, `kind` and the kind's settings, below |

Item kinds (merged: defaults, then the variant, then the item):

- `text_to_3d`: `prompt` (or the variant's), `preview` and `refine` tables of API parameters, `texture` (default
  true; false skips the refine, but Meshy rigs textured models only). Stages: preview, then refine.
- `rig`: `source`, an earlier textured `text_to_3d` item; `params` such as `height_meters`. The runner sends the
  source's refine task id as `input_task_id`.
- `animate`: `source`, an earlier `rig` item; `params.action_ids`, 1 to 10 ids from the animation library. The
  runner sends the source's rig task id as `rig_task_id`.

The runner fills in `mode`, `prompt`, `preview_task_id`, `input_task_id` and `rig_task_id`; a batch may not set them.
Prompts are at most 800 characters. An example with every kind:

```toml
[[items]]
id = "v1-1"
variant = "v1"
kind = "text_to_3d"

[[items]]
id = "v1-1-rig"
kind = "rig"
source = "v1-1"
params = { height_meters = 1.75 }

[[items]]
id = "v1-1-anim"
kind = "animate"
source = "v1-1-rig"
params = { action_ids = [1, 2] }
```

## A run

`meshy run` checks the approval fields, their shape and the estimate against `credit_cap` before it reads the key,
then goes through the items in file order, one at a time:

1. A `done` item is skipped. A `failed` item is skipped unless `--retry-failed` (which keeps its succeeded stages
   and resubmits only the failed one). A rig or animation whose source is not done waits.
2. Before submitting, it stops if the credits already spent in this batch (the sum of `consumed_credits`) plus the
   item's estimate would pass the cap, or if the live balance is below the item's estimate.
3. Each stage is submitted, its task id written to `generation.json` at once, then polled: 5 s, growing 1.5 times
   to at most 60 s, for at most 45 min. A rerun after an interruption polls the recorded task id instead of paying
   again.
4. Every result URL of each stage's task (`model_urls`, `texture_urls`, `thumbnail_url`, `result`, ...) is downloaded
   through a `.part` file as `<stage>-<file name>` (for example `refine-model.glb`, `refine-texture_0.png`).
5. `generation.json` gets the files with their sizes and sha256, the balance after and `status: done`; a row goes to
   `log.csv`.

Network failures and HTTP 429 or 5xx are retried with a growing pause (`Retry-After` when Meshy sends it), except a
submit: after a lost answer or a 5xx the task may exist and cost credits, so the item is marked failed with
"submit unsure" and the run stops. Check the Meshy dashboard, then rerun with `--retry-failed` if no task was made.
A submit Meshy definitely refused for that item alone (HTTP 400, 404, 409 or 422, for example a rig whose pose
estimate failed) creates no task and costs nothing: the item is marked failed with "refused" and the run goes on to
the next item. 401 (bad key), 402 (not enough credits) and a 429 that outlasts the retries stop the run, since every
item would hit them.

Items run one after another, so a batch takes the sum of its tasks' times (not measured yet: no live run so far);
Meshy's queue limit, 10 tasks on Pro, would allow parallel items later.

## The raw folder

`<raw>` is `common.raw_dir()` (`D:/prime-art-raw`, outside git; `ART_RAW_DIR` overrides).

```
<raw>/<batch id>/log.csv
<raw>/<batch id>/<item id>/generation.json
<raw>/<batch id>/<item id>/<stage>-<file>
```

`generation.json`: `batch`, `batch_file`, `item`, `variant`, `kind`, `prompt`, `source`, `model_version`,
`parameters` (per stage), `estimated_credits`, `plan`, `terms_url`, `approval` (by, at, ref, credit_cap), `status`
(`running`, `done`, `failed`), `error`, `started_at`, `finished_at` (UTC), `balance_before`, `balance_after`, `tasks`
(per stage: `id`, `request`, `submitted_at`, `polled_at`, `status`, `progress`, Meshy's `created_at`, `started_at`,
`finished_at` in ms, `consumed_credits`, `task_error`) and `files` (`name`, `stage`, `bytes`, `sha256`). Signed URLs
are not stored: they expire.

`log.csv` columns: `time, item, variant, kind, status, model, tasks, credits, balance_before, balance_after, files`.

Meshy keeps API results for 3 days on non-Enterprise plans, so a run downloads at once; an item interrupted between
a finished task and its downloads must be rerun within those days.

## The Meshy API as read on 2026-10-02

Sources: docs.meshy.ai (`/en/api/text-to-3d`, `/rigging-and-animation`, `/animation`, `/balance`, `/pricing`,
`/errors`, `/rate-limits`, `/quick-start`, `/asset-retention`) and Meshy's credits guide (2026-07-30,
meshy.ai/tutorials/meshy-credits-guide). Re-read them before changing the client or the prices in `_meshy_batch.py`.

Base `https://api.meshy.ai`, header `Authorization: Bearer <key>`. Tasks go `PENDING`, `IN_PROGRESS`, then
`SUCCEEDED`, `FAILED` or `CANCELED`; times are milliseconds since the epoch; `consumed_credits` is 0 for a failed task.

| Use | Endpoint | Credits |
|---|---|---|
| Text-to-3D preview (the mesh) | `POST /openapi/v2/text-to-3d` with `mode: "preview"`; answer `{"result": "<task id>"}` | meshy-7.1 and meshy-6: 20; meshy-6-lite and meshy-t2: 5; +5 for `geometry_resolution` 2k or 4k (meshy-7.1) |
| Text-to-3D refine (the texture) | `POST /openapi/v2/text-to-3d` with `mode: "refine"`, `preview_task_id` | 2k or 4k texture: 10; 8k: 15 |
| Text-to-3D task | `GET /openapi/v2/text-to-3d/<id>` | 0 |
| Rigging | `POST /openapi/v1/rigging` (`input_task_id` or `model_url`, `height_meters` default 1.7); `GET /openapi/v1/rigging/<id>` | 5 |
| Animation | `POST /openapi/v1/animations` (`rig_task_id`, `action_id` or `action_ids` 1 to 10, optional `post_process`); `GET /openapi/v1/animations/<id>` | 3 per action |
| Animation library | `GET /openapi/v1/animations/library` (`search`, `category`) | 0 |
| Balance | `GET /openapi/v1/balance`, answer `{"balance": <n>}` | 0 |

Preview parameters this client uses: `prompt` (at most 800 characters), `ai_model` (`meshy-6-lite`, `meshy-6`,
`meshy-7.1`, `latest` = meshy-7.1; `meshy-t2` for `model_type: "smart-topology"`), `model_type` (`standard`,
`smart-topology`; `lowpoly` is deprecated and retires on 2026-10-30), `should_remesh` (default false on Meshy 6 and
7: without it `topology` and `target_polycount` do not apply), `topology` (`triangle`, `quad`), `target_polycount`
(100 to 300,000 when remeshing), `pose_mode` (`t-pose`, `a-pose`, empty), `symmetry_mode` (deprecated: "no
functional impact"), `target_formats` (`glb`, `obj`, `fbx`, `stl`, `usdz`, `3mf`). Refine: `enable_pbr` (default
false: base colour only, no metallic, roughness or normal maps), `texture_resolution` (`2k`, `4k`, `8k`),
`texture_prompt` (optional, at most 800 characters), `remove_lighting` (default true), `ai_model`, `target_formats`.

Result fields: `model_urls` (`glb`, `fbx`, `obj`, `mtl`, `usdz`, `stl`), `texture_urls` (a list of `base_color` and,
with PBR, `metallic`, `normal`, `roughness`, `emission`), `thumbnail_url`; a rig task's `result` has
`rigged_character_glb_url`, `rigged_character_fbx_url` and `basic_animations` (walking and running GLB/FBX); an
animation's `result` has `animation_glb_url`, `animation_fbx_url` and post-processed files. All are signed links that
expire. Rigging takes textured humanoid GLB models only (at most 300,000 faces, facing +Z); a failed pose estimate is
HTTP 422.

Errors: 400 bad input, 401 bad key, 402 not enough credits, 404, 409 wrong state, 422, 429 (a request-rate hit
carries `Retry-After`; a queue hit, `NoMoreConcurrentTasks` or `NoMorePendingTasks`, does not), 5xx. Pro allows 20
requests per second and 10 queued tasks.

Account (the credits guide and the quick start): the API needs a paid plan (free accounts cannot create keys) and
draws from the same credit balance as the web app. The guide says API generations always come textured and cost 30
credits, with no mesh-only option; the API pricing page lists the preview (20 on meshy-7.1) and the refine (10)
separately. Both give 30 for a textured meshy-7.1 generation, which is what `meshy estimate` charges. Neither page
mentions a test key that spends nothing, so the tests use a fake transport and no live call submits a task.

## The first batch, 2026-10-b1-bodies

Twelve text-to-3D items: four tries each of V1 (average, slightly lanky, separate eyeballs), V2 (bigger head, wider
shoulders, shorter legs, separate eyeballs) and V3 (V1 with eyes and mouth painted on). meshy-7.1 pinned rather than
`latest`, so a rerun matches; T-pose; remeshed to 7000 triangles; base colour texture at 2K without PBR maps;
`symmetry_mode = "on"` kept as the record of the intent although the docs say it no longer has an effect (the prompt
says "symmetrical"). `texture_prompt` is unset. The prompts are 306 to 318 characters, under the 800 limit, so none
was shortened. Estimate 360 credits, cap 360: the engineer approved "about 360 credits" (prime-game#165), and a
failed task costs nothing, so the cap stops the run only when Meshy charges more than the estimate.
