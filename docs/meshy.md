# Meshy client

`tools/run.py meshy` (`tools\run.cmd meshy` on Windows) runs the engineer's approved generation batches against the
Meshy API without a human at the keyboard, downloads every result into the raw folder and records each generation.
Since art #25 the client also rigs local GLBs, makes text-to-motion clips and lists the animation library.
`tools/run.py raw-backup` copies chosen results to the OneDrive backup. Code: `tools/runner/commands/meshy.py`,
`_meshy_api.py` (HTTP, key, polling), `_meshy_batch.py` (batch files, prices), `_meshy_inputs.py` (image inputs),
`_meshy_run.py` (the run), `raw_backup.py` and `tools/blender/meshy_rig_input.py` (rig inputs); tests: `tools/tests/test_meshy_*.py` (a fake transport, no network).

## Commands

| Command | Network | What it does |
|---|---|---|
| `meshy estimate <batch>` | none | Credits per stage, per item and in total, the approved cap, whether the approval is complete, and each input file's size and sha256 (or why it is not ready) |
| `meshy run <batch> [item ...] [--retry-failed]` | spends credits | Refuses a batch without approval or over its cap; then submits, polls, downloads and records each item |
| `meshy balance` | read only | The account's credit balance (spends nothing) |
| `meshy status <batch>` | none | Each item's state from its `generation.json`; flags downloaded files that went missing |
| `meshy library [--search S] [--category C] [--out FILE]` | read only | The animation library's listing (free), saved as Meshy sent it with the time and the query to `<raw>/meshy/animation-library-<date>.json`; prints the count per category |
| `meshy rig-input <character.blend> ... --out DIR` | none | A saved character (`assemble --blend`) as a rig input: a static textured GLB facing +Z, its palette PNG and a JSON note; prints the sha256 values to pin (below) |
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

`batches/<id>.toml` is committed: prompts and parameters are durable knowledge, and the file is what was approved.
Changing a prompt or a parameter needs a new approval.

**Since 2026-10-03 the approval can be the standing permission.** The engineer's kickoff of stage 1 allows Meshy
generation within the plan's credits without a separate yes per batch (`docs/decisions/2026-10-03-trust-model.md`).
A batch under it records that permission and nothing more:
- `approved_by` names the engineer, as the giver of the permission;
- `approval_ref` links its record, https://github.com/xperiaroco2/prime-game-art/issues/16 (the kickoff in the body)
  or the chat yes recorded on #16 for a specific trial;
- `credit_cap` stays within the balance `meshy balance` shows at launch;
- the spend goes into the next report on the plan issue.

A batch beyond the plan's credits, or one the engineer wants to see first, needs his own yes linked in
`approval_ref`. The client's message "must link to the engineer's yes" (`_meshy_batch.py`) predates this; a
follow-up updates it.

| Key | Meaning |
|---|---|
| `id` | Equals the file name; lower-case letters, digits, `.`, `_`, `-` |
| `purpose` | One sentence on why the batch exists |
| `plan`, `terms_url` | The Meshy plan and terms the generations fall under; copied into every `generation.json` |
| `licence` | The licence of the outputs under that plan and those terms, as the asset manifest records it; copied into every `generation.json` |
| `credit_cap` | The most credits the approval covers |
| `approved_by`, `approved_at`, `approval_ref` | Who approved, the date (`YYYY-MM-DD`) and a `https://github.com/` link to the yes |
| `[variants.<name>]` | Shared settings of a variant: `prompt`, optional `preview`/`refine` tables |
| `[defaults.text_to_3d.preview]`, `[defaults.text_to_3d.refine]` | Request parameters for every text-to-3D item |
| `[defaults.<kind>.params]` | Request parameters for every item of another kind (`rig`, `animate`, `text_to_image`, `image_to_image`, `image_to_3d`, `multi_image_to_3d`, `remesh`) |
| `[[items]]` | `id`, `variant`, `kind` and the kind's settings, below; any other key is an error |

Item kinds (merged: defaults, then the variant, then the item):

- `text_to_3d`: `prompt` (or the variant's), `preview` and `refine` tables of API parameters, `texture` (default
  true; false skips the refine, but Meshy rigs textured models only). Stages: preview, then refine.
- `rig`: `source`, an earlier item with a textured model (below), or `model`, a local GLB (art #25), with an
  optional `texture`, its UV-unwrapped base colour as a PNG: tables like an image input,
  `{ file = "raw:...", provenance = "...", sha256 = "..." }`. `params`: `height_meters` (default 1.7). The runner
  sends the source's final model task id (a text-to-3D's refine) as `input_task_id`, or the GLB as a data URI in
  `model_url` (`data:application/octet-stream;base64,...`, the media type the remesh docs ask for; the rigging docs
  name none) and the PNG in `texture_image_url`. A model must be a binary glTF (its first bytes `glTF`) of at most
  20 MB (this client's limit; the docs state none).
- `animate`: `source`, an earlier `rig` item; `params.action_ids`, 1 to 10 unique ids from the animation library, or
  `motion`, an earlier `text_to_motion` item (exactly one of them; the docs: `action_id`, `action_ids` or
  `motion_task_id`). The runner sends the source's rig task id as `rig_task_id` and the motion item's task id as
  `motion_task_id`; `params.post_process` (`operation_type`, `fps`) is passed as it is.
- `text_to_motion` (art #25): `prompt` (at most 400 characters; never a game or a character), `params.duration`
  (required, 2 to 10 s in 0.5 s steps) and `params.mode` (`prime`, the default, 10 credits, an FBX clip; `swift`, 3
  credits, a BVH clip). The clip is downloaded at once (Meshy keeps it 3 days); an `animate` item puts it on a rig.
- `text_to_image`: `prompt` (or the variant's); `params`: `ai_model` (required), `generate_multi_view`,
  `pose_mode`, `aspect_ratio` (not with `generate_multi_view`), `remove_background`. Makes one image, or three with
  `generate_multi_view = true`.
- `image_to_image`: `prompt`, `images` (1 to 5 reference images); `params` as for `text_to_image`.
- `image_to_3d`: `images` (exactly one); `params`: the text-to-3D style options `ai_model`, `model_type`,
  `should_remesh`, `topology`, `target_polycount`, `pose_mode`, `should_texture` (default true), `enable_pbr`,
  `texture_prompt`, `texture_resolution`, `target_formats`, ... No `prompt`: the image is the prompt.
- `multi_image_to_3d`: `images` (1 to 4; the first is the front view); `params` as for `image_to_3d` (no
  `meshy-t2`).
- `remesh`: `source`, an earlier `text_to_3d`, `image_to_3d` or `multi_image_to_3d` item; `params`: `topology`,
  `target_polycount`, `target_formats`. A text-to-3D or image-to-3D source goes by task id (the refine of a textured
  text-to-3D); a multi-image-to-3D source, which the remesh docs do not list, goes as its downloaded GLB.

A `rig` takes any earlier item that makes a textured model: `text_to_3d` (textured), `image_to_3d` and
`multi_image_to_3d` (unless `should_texture = false`); the runner sends the task that made the source's final
model as `input_task_id`. A rig of a `remesh` is refused: the docs list no `texture_urls` for a remesh result and
do not say whether the texture survives, so rig the remesh's source until a live run shows it does. An item without `variant` takes its source's or its first `from`
input's.

### Image inputs

`images` is a list of inputs, each a table:

- A local file: `{ file = "raw:mannequin/lanky/front.png", provenance = "own work: Blender render of our mannequin",
  sha256 = "..." }`. `file` is `raw:<path>` under the raw folder, an absolute path, or a path relative to the
  repository root. PNG or JPEG (checked by its first bytes, and the extension must match), at most 20 MB.
  `provenance` is required: where the image comes from, in words; never a screenshot of another game and never a
  personal photo. `sha256` is optional: when set, the run refuses a file that changed since the approval;
  `meshy estimate` prints each file's current sha256 to copy in.
- Another item's output: `{ from = "<item id>" }` takes every image of an earlier `text_to_image` or
  `image_to_image` item, in Meshy's order; `{ from = "<item id>", pick = n }` takes image `n`, a 0-based index into
  that item's `image_urls` (0, 1 or 2 of a multi-view set). An `image_to_3d` from a multi-view item needs a `pick`.

Every input is sent as a base64 data URI (`data:image/png;base64,...`), which every image endpoint accepts. A `from`
input sends the source's downloaded file, after checking it still matches the sha256 in the source's
`generation.json`; an item waits until all its sources are done. `generation.json` keeps each input's `file` or
`from` and `pick`, its `path`, `media_type`, `bytes`, `sha256` and `provenance` (for a `from` input: the batch, item,
task and image it came from), and the recorded request carries a short note instead of each data URI.

The runner fills in `mode`, `prompt`, `preview_task_id`, `input_task_id`, `rig_task_id`, `motion_task_id`, `model_url`,
`texture_image_url` (of a rig), `image_url`, `image_urls` and `reference_image_urls`; a batch may not set them. `texture_image_url` and `texture_image_urls` are
not supported yet (they would need an input of their own). The `params` of an image-mode kind may hold only the
parameters the docs list for it (`KNOWN_PARAMS` in `_meshy_batch.py`, from the sections below; since art #25 also
`rig`, `animate` and `text_to_motion`): Meshy may ignore an
unknown key, so a misspelt one would pay for a generation without its setting. Text-to-3D prompts and `texture_prompt` are at most 800
characters; the image docs state no prompt limit.

`batches/example-image-modes.toml` shows every image kind and input form: a multi-view concept from text, a concept
from our mannequin renders, a body from every view and one from a picked view, a prop, a remesh and a rig.
A `batches/example-*.toml` file is never approved and `meshy run` refuses it; copy it to a new batch for approval.

An example with the text-to-3D kinds:

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
then that every local input file of the items it may submit exists, is a PNG or JPEG of at most 20 MB and matches
its pinned sha256 (nothing is submitted otherwise), then goes through the items in file order, one at a time:

1. A `done` item is skipped. A `failed` item is skipped unless `--retry-failed` (which keeps its succeeded stages
   and resubmits only the failed one). An item whose `source` or `from` items are not all done waits. An input that
   cannot be sent at submit time (a source image edited since its download, fewer images than `pick` needs) fails
   that item with "inputs" and costs nothing.
2. Before submitting, it stops if the credits already spent in this batch (the sum of `consumed_credits`; a task
   still in flight counts at least at its stage's estimate) plus the item's estimate would pass the cap, or if the live balance is below the item's estimate.
3. Each stage is submitted, its task id written to `generation.json` at once, then polled: 5 s, growing 1.5 times
   to at most 60 s, for at most 45 min. A rerun after an interruption polls the recorded task id instead of paying
   again.
4. Every result URL of each stage's task (`model_urls`, `texture_urls`, `thumbnail_url`, `thumbnail_urls`,
   `image_urls`, `result`, ...) is downloaded through a `.part` file as `<stage>-<file name>` (for example
   `refine-model.glb`, `refine-texture_0.png`); when two files share a name, as the images of a multi-view set
   (all `image.png`), the key path names them: `text_to_image-image_urls.0.png`, `...1.png`, `...2.png`. Each
   download is logged, and an image item's log ends with the `pick` index of each image.
5. `generation.json` gets the files with their result key, sizes and sha256, the balance after and
   `status: done`; a row goes to `log.csv`.

Network failures and HTTP 429 or 5xx are retried with a growing pause (`Retry-After` when Meshy sends it), except a
submit: after a lost answer or a 5xx the task may exist and cost credits, so the item is marked failed with
"submit unsure" and the run stops. Check the Meshy dashboard, then rerun with `--retry-failed` if no task was made.
A submit Meshy definitely refused for that item alone (HTTP 400, 404, 409, 413 or 422, for example a rig whose
pose estimate failed or a request too large) creates no task and costs nothing: the item is marked failed with "refused" and the run goes on to
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
`parameters` (per stage), `estimated_credits`, `plan`, `terms_url`, `licence`, `approval` (by, at, ref, credit_cap),
`status` (`running`, `done`, `failed`), `error`, `started_at`, `finished_at` (UTC), `balance_before`,
`balance_after`, `inputs` (image modes, above), `tasks` (per stage: `id`, `request`, `estimated_credits`, `submitted_at`, `polled_at`, `status`,
`progress`, Meshy's `created_at`, `started_at`, `finished_at` in ms, `consumed_credits`, `task_error`),
`previous_tasks` (failed tasks a `--retry-failed` replaced, each with its `stage`) and `files` (`name`, `stage`,
`key`, the result field it came from such as `image_urls.1` or `model_urls.glb`, `bytes`, `sha256`). Signed URLs are not stored: they expire.

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

Output licence (<https://www.meshy.ai/terms-of-use>, "Last Updated: September 19, 2026", read 2026-10-02): section
3.2 says a paid plan's customer owns its Customer Output, and Meshy keeps a non-exclusive, royalty-free, worldwide
licence to use it to provide the service. A free plan's output is owned by Meshy and offered under CC BY 4.0 with
credit to Meshy. Section 3.3: whatever is posted to Meshy's community page falls under CC0 (3D models) or
CC BY-NC 4.0 (other uploads), so nothing of ours is posted there. The batch's `licence` records this per batch; reread
the terms when the plan changes or before a batch whose terms date is older than the page's.

Account (the credits guide and the quick start): the API needs a paid plan (free accounts cannot create keys) and
draws from the same credit balance as the web app. The guide says API generations always come textured and cost 30
credits, with no mesh-only option; the API pricing page lists the preview (20 on meshy-7.1) and the refine (10)
separately. Both give 30 for a textured meshy-7.1 generation, which is what `meshy estimate` charges. Neither page
mentions a test key that spends nothing, so the tests use a fake transport and no live call submits a task.

## The image modes as read on 2026-10-03

Sources: docs.meshy.ai `/en/api/text-to-image`, `/image-to-image`, `/image-to-3d`, `/multi-image-to-3d`,
`/remesh`, `/rigging-and-animation` and `/pricing`; help.meshy.ai "How to Use Meshy Image to 3D" for the size limit.
Every create answers `{"result": "<task id>"}`; every task is read with `GET <path>/<id>` and has `status`,
`progress`, `created_at`, `started_at`, `finished_at`, `expires_at`, `consumed_credits`, `task_error` and
`preceding_tasks`. Image inputs are `.jpg`, `.jpeg` or `.png`, as a public URL or a base64 data URI; the API pages
give no size limit, the web app takes at most 20 MB, which the client applies.

| Use | Endpoint | Credits |
|---|---|---|
| Text to image | `POST /openapi/v1/text-to-image` | per image: `nano-banana` 3, `nano-banana-2` 6, `nano-banana-pro`, `gpt-image-2`, `gpt-image-2-5-flare`, `gpt-image-2-5-sunburst` 9 |
| Image to image | `POST /openapi/v1/image-to-image` | per image: `nano-banana` 3, `nano-banana-2` 6, `nano-banana-pro` 9, the three `gpt-image-*` 12 |
| Image to 3D | `POST /openapi/v1/image-to-3d` | mesh: meshy-7.1 and meshy-6 20, meshy-6-lite and meshy-t2 5 (+5 for `geometry_resolution` 2k or 4k on meshy-7.1); texture: +10 at 2k or 4k, +15 at 8k (meshy-6-lite: 2k only) |
| Multi-image to 3D | `POST /openapi/v1/multi-image-to-3d` | as image to 3D (models meshy-6-lite, meshy-6, meshy-7.1; `geometry_resolution` standard or 2k, 2k on meshy-7.1 or `latest` only) |
| Remesh | `POST /openapi/v1/remesh` | 5 |

Text to image: `ai_model` (required, the six above), `prompt` (required), `generate_multi_view` (default false),
`pose_mode` (`a-pose`, `t-pose`; omitted: no pose preset), `aspect_ratio` (`1:1` default, `16:9`, `9:16`, `4:3`,
`3:4`; `3:2` and `2:3` on the GPT models; not with `generate_multi_view`), `remove_background` (default false; a
transparent PNG). The result is `image_urls`: one image, or "three image URLs representing different viewing angles"
with `generate_multi_view`. The docs' example names the file `image.png`. A three-view set is one charge: batch
`2026-10-b2-image-routes` (2026-10-03) paid 9 credits per set on nano-banana-pro and gpt-image-2 (`consumed_credits`),
so `meshy estimate` prices it once. Which angle each of the
three images shows is not documented either: look at the downloaded images before writing a `pick`.

Image to image: `ai_model` (required, the six above), `prompt` (required), `reference_image_urls` (1 to 5 images) or
`input_task_id` (a succeeded text-to-image or image-to-image task, which wins when both are set),
`generate_multi_view`, `aspect_ratio`, `remove_background`. The result is `image_urls`. This client sends
`reference_image_urls` only (data URIs), so every input has a file and a sha256 on our side.

Image to 3D: `image_url` or `input_task_id` (a succeeded text-to-image or image-to-image task); `ai_model`
(`meshy-6-lite`, `meshy-6`, `meshy-7.1`, `latest`; `meshy-t2` for `model_type: "smart-topology"`), `model_type`
(`standard`, `smart-topology`, `lowpoly` deprecated until 2026-10-30), `geometry_resolution` (`standard`, `2k`,
`4k`), `should_texture` (default true), `enable_pbr` (default false), `texture_resolution` (`2k` default, `4k`,
`8k`), `texture_prompt` (at most 800 characters), `texture_image_url`, `should_remesh` (default false on Meshy 6 and
7), `topology` (`triangle` default, `quad`), `target_polycount` (100 to 300,000 when remeshing, default 30,000;
100 to 15,000 for smart topology, default 4,000), `pose_mode` (`a-pose`, `t-pose`, empty), `image_enhancement`
(default true), `remove_lighting` (default true), `save_pre_remeshed_model` (default false), `target_formats`
(`glb`, `obj`, `fbx`, `stl`, `usdz`, `3mf`; default all but 3mf), `symmetry_mode` (deprecated), `moderation`. The
result: `model_urls` (`glb`, `fbx`, `obj`, `usdz`, `mtl`, `stl`, `3mf`, `pre_remeshed_glb`), `texture_urls`
(`base_color` and, with PBR, `metallic`, `normal`, `roughness`, `emission`), `thumbnail_url`,
`alpha_thumbnail_url` and `thumbnail_urls` (front, right, back, left).

Multi-image to 3D: `image_urls` (1 to 4 images of one object, the first is the front view) or `input_task_id` (a
succeeded image task, multi-view included); the image-to-3D options except `meshy-t2`, plus `texture_image_urls` (1
to 4 texture guides, meshy-7.1 only). The result is as for image to 3D.

Remesh: `input_task_id` (a succeeded text-to-3D preview or refine, image-to-3D or retexture task) or `model_url` (a
public URL or a data URI with the media type `application/octet-stream`; `.glb`, `.gltf`, `.obj`, `.fbx`, `.stl`);
`target_formats` (default `["glb"]`; `glb`, `fbx`, `obj`, `usdz`, `blend`, `stl`, `3mf`), `topology` (`triangle`
default, `quad`), `target_polycount` (100 to 300,000, default 30,000); `resize_height`, `origin_at` and
`convert_format_only` are deprecated. The result: `model_urls`, `thumbnail_url`, `alpha_thumbnail_url`.

Rigging's `input_task_id` is "the input task that needs to be rigged": any task with a textured humanoid model (at
most 300,000 faces), so a rig follows any textured model item (not a remesh, above); `model_url` takes a textured humanoid GLB facing +Z.

## Rig inputs from our characters (`meshy rig-input`, art #25)

Meshy rigs "textured humanoid GLB files" whose face points to +Z. Our characters are flat material colours with no
UVs, so `tools/blender/meshy_rig_input.py` (background Blender) makes the rig input from a saved character:

1. opens `blend/<id>.blend`, puts the armature in its rest pose (the T-pose) and joins the parts' rest shapes into one
   static mesh (no armature, no actions, no toe bones: Meshy builds its own skeleton);
2. bakes every material's viewport colour into one 8 px cell of a palette PNG (`<id>_texture.png`, 32 px for 14
   colours, sRGB) and gives every face of that material UVs at its cell's centre, with one material sampling the PNG
   (closest-pixel);
3. exports `<id>.glb` with Blender's glTF exporter (+Y up: Blender's front -Y becomes glTF's +Z) and writes `<id>.json`
   (triangles, height, bytes, the colours per material).

The palette is for the rig input only; nothing of ours changes. `render` of the GLB shows the colours from the texture
(`D:/prime-art-raw/review/stage1/25/rig_inputs/`). `rig-input` reads the GLB's JSON chunk afterwards and refuses
anything but one node with one mesh. The "Icosphere" that appears beside every import of a Meshy output (and of the
pack files) in Blender is the glTF importer's own bone display shape: neither the rig inputs (1 node, 1 mesh) nor
Meshy's GLBs (the 24 bones, the armature node and one mesh: 26 nodes) contain one, so nothing of it reached Meshy.

## Animation as read on 2026-10-03 (art #25)

Sources: docs.meshy.ai `/en/api/rigging-and-animation`, `/animation`, `/animation-library`, `/text-to-motion` and the
web guide `/en/webapp/guides/3d-model/rigging`.

| Use | Endpoint | Credits |
|---|---|---|
| Rigging | `POST /openapi/v1/rigging`: `input_task_id`, or `model_url` ("a publicly accessible URL or Data URI"; "textured humanoid GLB files"; the face toward +Z), `height_meters` (default 1.7), `texture_image_url` (the UV-unwrapped base colour, PNG, URL or data URI); at most 300,000 faces by task id | 5 per successful task |
| Animation | `POST /openapi/v1/animations`: `rig_task_id` and exactly one of `action_id`, `action_ids` (1 to 10 unique) or `motion_task_id` (a succeeded text-to-motion task; "requires a biped rig"); optional `post_process` `{operation_type: change_fps, fbx2usdz or extract_armature, fps: 24, 25, 30 or 60}` | 3 per action; a motion clip "the same 3-credit base" |
| Text to motion | `POST /openapi/v1/text-to-motion`: `prompt` (at most 400 characters), `duration` (required, 2 to 10 s in 0.5 s steps), `mode` (`prime` default, `swift`); `GET /openapi/v1/text-to-motion/<id>` | prime 10 (FBX), swift 3 (BVH) |
| Animation library | `GET /openapi/v1/animations/library` | 0 |

Results: a rig task's `result` holds `rigged_character_glb_url`, `rigged_character_fbx_url` and `basic_animations`
(walking and running, GLB and FBX, with and without the armature); an animation's `result` holds `animation_glb_url`
and `animation_fbx_url` ("with `action_ids`, ... one merged file ... every requested action as a separate clip") and the
post-processed files; a text-to-motion task's `result` holds `motion_url`, `motion_format` (`fbx` or `bvh`),
`duration_ms` and `mode`, kept "3 days after the task finishes". A failed pose estimate of a rig is HTTP 422. The docs
name no skeleton (bones, count, fingers, toes); the web guide calls the rig "Mixamo-compatible".

The library listing answered on 2026-10-03 with a list of 678 actions, each `action_id`, `name`, `key` (the docs'
name), `category`, `sub_category` and `preview_url` (the docs page lists 591, ids 0 to 590; ids from 591 on repeat
earlier names).

## Batch 4, 2026-10-b4-animations (art #25)

Meshy's animations on our own characters: rigs of m1_rex and w1_ivy from `meshy rig-input` (pinned by sha256), ten
library actions on the man (the sprint for the feet, then backwards, a turn in place, a hit, a knock-down, a crawl, the
downed state, a two-handed carry, a shrug and a finger wag), a walk (1 Walking Woman) and the sprint (16 Run Fast) on
the woman, and one prime text-to-motion crawl while downed, animated on the man: 59 credits, cap 60, approved by the
engineer for "about 60 credits" ([art #16](https://github.com/xperiaroco2/prime-game-art/issues/16#issuecomment-5971404896))
and confirmed by the engineer in chat before the run ([recorded on art #16](https://github.com/xperiaroco2/prime-game-art/issues/16#issuecomment-5972512323),
the batch's `approval_ref`). The action ids and names are in the batch file. The trial and its findings:
[research/2026-10-03-meshy-animations.md](research/2026-10-03-meshy-animations.md).

**A manifest that uses a batch-4 clip** (library or text to motion) records `licence = "restricted"`,
`public_repo_ok = false`, `ai_generated = true` (a boolean: for the library clips the conservative value, since Meshy
does not disclose how they were made; say so in `notes`), `source.model_version = "undisclosed"` and the animate task
ids. The research page has the reasons.

**Run** on 2026-10-03, 18:57 to 19:00 UTC, by the art manager (`meshy run 2026-10-b4-animations`, the man's rig first):
balance **374 before, 315 after: 59 credits**, every task charged as estimated (`log.csv` and each item's
`generation.json` in `raw:2026-10-b4-animations/`; copies in `OneDrive/prime-art-raw/`, `raw-backup`: 23 files).

| Item | Task | Credits | Balance | Files |
|---|---|---|---|---|
| `man-rig` | rig `01a10320-b412-7299-ad68-92890c4e6853` | 5 | 374 -> 369 | rigged GLB and FBX, walking and running with skin (GLB, FBX) and as armature-only GLBs |
| `woman-rig` | rig `01a10321-dc82-74b0-bbbf-d0c66d2f5d58` | 5 | 369 -> 364 | the same |
| `man-library` | animate `01a10322-3570-7439-bd87-2597a408f49c` | 30 | 364 -> 334 | `animate-merged_animations.glb`/`.fbx`: the ten actions as clips |
| `woman-library` | animate `01a10322-a5d5-7169-8499-c1c522bc8ac9` | 6 | 334 -> 328 | the same with two |
| `crawl-motion` | text to motion `01a10322-c879-7192-a408-0a474c65fc6c` | 10 | 328 -> 318 | `text_to_motion-clip.fbx` (16.8 MB, prime, 4 s) |
| `man-crawl` | animate `01a10323-3b62-7512-80e2-9ebfde356052` | 3 | 318 -> 315 | the crawl on the man's rig, GLB and FBX |

What came back (read in Blender and from the GLBs' JSON): the rigged character is our mesh merged into one object
(`char1`, the same 6458 and 8318 triangles, the palette texture kept) skinned to Meshy's 24-bone rig (the skeleton:
the research page), at most 4 influences a vertex, the armature at a world scale of 0.01 and facing -Y like ours. The
basic walking (32 frames at 30 fps) and running (20) are in place; of the library clips, Carry Heavy Object Walk, Crawl
and Look Back, Walk Backward, Hit Reaction and Knock Down travel with the hips (the review takes the travel out of the
loops), the rest stay in place. The review reads them as two libraries (`meshy`, `meshyw` in
`tools/blender/anim_review.toml`; docs/animations.md).

## The first batch, 2026-10-b1-bodies

Twelve text-to-3D items: four tries each of V1 (average, slightly lanky, separate eyeballs), V2 (bigger head, wider
shoulders, shorter legs, separate eyeballs) and V3 (V1 with eyes and mouth painted on). meshy-7.1 pinned rather than
`latest`, so a rerun matches; T-pose; remeshed to 7000 triangles; base colour texture at 2K without PBR maps;
`symmetry_mode = "on"` kept as the record of the intent although the docs say it no longer has an effect (the prompt
says "symmetrical"). `texture_prompt` is unset. The prompts are 306 to 318 characters, under the 800 limit, so none
was shortened. Estimate 360 credits, cap 360: the engineer approved "about 360 credits" (prime-game#165), and a
failed task costs nothing, so the cap stops the run only when Meshy charges more than the estimate.
