# OpenAI image client

`tools/run.py openai-images` (`tools\run.cmd openai-images` on Windows) runs approved image batches against the
OpenAI Images API: generations from text and edits from our own reference images (renders painted over, crops of
earlier sheets). Each image is saved as a PNG in the raw folder with a `generation.json` and a `log.csv` row, like a
Meshy run. Code: `tools/runner/commands/openai_images.py` (the command), `_openai_api.py` (HTTP, the key, multipart
by hand, retries), `_openai_batch.py` (batch files, prices, the estimate), `_openai_run.py` (the run); tests:
`tools/tests/test_openai_images.py` (a fake transport, no network).

## The decision (2026-10-20)

The engineer, 2026-10-20 (#196, comment 6291187194; xperiaroco2/prime-game#1095, comments 6290907395 and 6291051168):
the art track generates images through the OpenAI API instead of Meshy, **medium** quality for exploration and many
variants, **high** for focused work on one piece. Meshy stays for 3D, rigging, retexture and motion
(`docs/meshy.md`). It is a standing permission (`CLAUDE.md`, "Paid services and downloads"): a batch needs no
separate yes when it stays within its `cost_cap_usd`; its spend goes into the plan issue's reports. OpenAI image
generation beyond the prepaid balance he funds, on another model, or above a batch's `cost_cap_usd` needs his own yes
linked in `approval_ref` (and, for another model, a change to `MODELS` in `_openai_batch.py`).

## Commands

| Command | Network | What it does |
|---|---|---|
| `openai-images estimate <batch>` | none | Per item the kind, quality, size, `n`, inputs and the estimated tokens (text in, image in, image out) and $; the total against the cap; whether the approval is complete; each input file's size and sha256 (or why it is not ready) |
| `openai-images run <batch> [item ...] [--retry-failed]` | spends money | Refuses a batch without approval or over its cap; checks every input file; then one request per item, in file order, the dollar cap checked before each |
| `openai-images status <batch>` | none | Each item's state and $ from its `generation.json`; flags saved images that went missing |

OpenAI offers no balance endpoint for a project key (the costs API needs an admin key), so there is no `balance`:
the engineer sees the prepaid balance on the platform's billing page. `raw-backup` takes Meshy batches only so far.

## The key

`OPENAI_API_KEY`, read with `common.env` (the process environment, else the Windows user environment; no restart
after setting it), exactly as `MESHY_API_KEY` is. The key goes only into the `Authorization: Bearer` header of
api.openai.com calls: never into a request body, `generation.json`, `log.csv`, a log line or an error message
(every message passes through `redact`, the command redacts a failure once more and lets no traceback out). `redact`
also scrubs anything shaped like an OpenAI key, `sk-` and 4 or more of `A-Za-z0-9_*-` after a word boundary, so the
masked form OpenAI's own 401 message shows (`sk-proj-****...abcd`) never reaches a log either. A
missing key fails with the engineer's steps (top up, create a key, `[Environment]::SetEnvironmentVariable(
"OPENAI_API_KEY", "<the key>", "User")`). The batch files never name the variable.

## Batch files

`batches/<id>.toml`, committed, the schema of a Meshy batch (`docs/meshy.md`) with dollars instead of credits.
`service = "openai-images"` marks it: `meshy` refuses such a batch and this client every other.

| Key | Meaning |
|---|---|
| `id` | Equals the file name; lower-case letters, digits, `.`, `_`, `-` |
| `service` | `"openai-images"` (required) |
| `purpose` | One sentence on why the batch exists |
| `plan`, `terms_url`, `licence` | The account (prepaid API balance), the terms (`https://openai.com/policies/services-agreement/`) and the outputs' licence: OpenAI assigns the customer all its rights in the Output (Services Agreement 4.1, read 2026-10-20); copied into every `generation.json` |
| `cost_cap_usd` | The most dollars the approval covers (a positive number) |
| `approved_by`, `approved_at`, `approval_ref` | Who, the date, and a `https://github.com/` link (the decision's comment for the standing permission) |
| `model` | `gpt-image-2.5-sunburst`, the model the standing permission names (`gpt-image-2.5-flare`, speed first at the same rates, is refused: another model needs the engineer's yes and a code change) |
| `quality` | **Required, no default**: `"medium"` (exploration and many variants) or `"high"` (focused work on one piece); an item may set its own |
| `[defaults]` | `size` (required somewhere), `n` (1 to 10, default 1), `background` (`auto`, `opaque`, `transparent`), `moderation` (`auto`, `low`; generations only) |
| `[variants.<name>]` | A shared `prompt` and any of the `[defaults]` keys |
| `[[items]]` | `id`, `kind`, `variant`, `prompt`, `images` and any of the `[defaults]` keys or `quality`; any other key is an error |

Merged: `[defaults]`, then the variant, then the item. Kinds:

- `generate`: `POST /v1/images/generations`, JSON `{model, prompt, size, quality, n, output_format = "png"}`. No
  `images`.
- `edit`: `POST /v1/images/edits`, multipart/form-data: the text fields `model`, `prompt`, `size`, `quality`, `n`,
  `output_format`, then each reference as an `image[]` file part (1 to 16 images, each PNG or JPEG under 50 MB).
  `images` takes the Meshy forms: `{ file = "raw:...", provenance = "...", sha256 = "..." }` (sha256 pinned: the run
  refuses a file that changed) or `{ from = "<earlier item>", pick = n }` (that item's saved `image-<n>.png`, checked
  against its `generation.json`; without `pick` all of its images).

`size` is `WIDTHxHEIGHT`: both edges multiples of 16, the long edge at most 3 times the short one and at most 3840,
655,360 to 8,294,400 pixels (`1024x1024`, `1536x1024`, `1024x1536` are the usual ones; above `2560x1440` is
experimental). `auto` is refused, since the estimate needs the size. `mask` and `input_fidelity` (to be omitted for
the gpt-image-2 family) are not supported; the prompt is at most 32,000 characters; never name a game, a film or a
character in a prompt.

## Prices and the estimate

$ per 1M tokens (the model page, read 2026-10-20): text input 5, image input 8, image output 30. Text
output is not billed; the client prices every output token at the image rate, an upper bound. The cost of a request
is computed from its answer's `usage` (`input_tokens_details.text_tokens` and `image_tokens`, `output_tokens`).

The docs give no token table for GPT Image 2.5 (only a calculator), so the estimate rests on measurements:

| What | Measured | Source |
|---|---|---|
| Output, medium, 1536x1024 | 343 image tokens (about $0.010) | design manager's test, prime-game#1095 |
| Output, high, 1536x1024 | 1,372 image tokens (about $0.041) | the same |
| Input, one 380x960 PNG reference | 416 image tokens | the edit test below |
| Input, a 1,104-character prompt | 278 text tokens | the edit test below |

The estimate per request: output tokens scaled by the pixel count from 1536x1024, times `n`; per reference image
the measured 416 tokens scaled by its pixel count from 380x960 (364,800 pixels), at least 416; the prompt's
characters / 3; all of it **times 2** (`ESTIMATE_MARGIN`). A local reference's size is read from its PNG header
(`IHDR`) or JPEG header (the first start-of-frame segment), locally, without decoding it; a file whose header cannot
be read counts 1,500 tokens (`UNREAD_INPUT_TOKENS`; the run refuses such a file anyway). A `from` input counts the
source item's size, once with `pick` and `n` times without it (all its images are sent). A 1536x1024 reference so
estimates at 1,794 tokens before the margin; whether OpenAI scales large references down first is not measured, so a
large one may be over-estimated, the safe side. The medium 1536x1024 edit with the one 380x960 reference estimates at
$0.031 and cost $0.015. Change the table in `_openai_batch.py` when a run measures something new.

## A run

`openai-images run` checks the approval and the estimate against `cost_cap_usd` before reading the key, takes the
batch's lock (`<raw>/<batch id>/run.lock`, made exclusively: a second run of the same batch is refused, since both
would check the cap against the same spend; a run that was killed leaves it behind, to be deleted by hand once no run
of the batch is going), then checks every local input file of the items it may send. Then, one item at a time:

1. A `done` item is skipped; a `failed` one unless `--retry-failed`; an item whose `from` items are not done waits.
2. **The dollar cap before every request, and again before each of its HTTP attempts**: what the batch has spent
   plus this request's estimate must stay within `cost_cap_usd`; else the run stops before sending (`CapReached`).
   The spend is summed over every `*/generation.json` in the batch folder, an item since renamed or dropped from the
   batch file included: each priced request's cost, plus the estimate of each request without a price that was not
   surely refused (lost, unreadable, still out when a run was killed), which may have been billed.
3. `generation.json` gets the request (fields, a note per image part, never the key) with `outcome: sent` **before**
   the call, so a run killed mid-request leaves it counted as maybe billed (`unsure`).
4. The call: a 160 s socket timeout per HTTP attempt (under the 170 s a tool call may block; with retries a request
   can take longer, which is why runs go to the background). Resent only when OpenAI surely refused it, as the Meshy
   client does: a 429 that is not `insufficient_quota` (no balance), or a 503 carrying `Retry-After`; up to 4 times,
   2, 4, 8, 16 s apart (`Retry-After` when sent, at most 60 s). Everything else that may have been served and billed
   is **unsure** and never resent: a lost connection, a timeout, any other 5xx (a 502, 504 or 524 from a proxy can
   come after the image was made) and a 2xx that cannot be read (not JSON, no `data`, no or bad base64). The item
   fails "request unsure", its estimate stays counted, and the run stops; check the usage page, then
   `--retry-failed`.
5. HTTP 400, 404, 409, 413, 415 or 422 (a bad field, `moderation_blocked`) fail that item alone at $0 and the run goes
   on; 401, 403 and the rest stop the run.
6. Each `data[i].b64_json` is decoded, checked to be a PNG and saved as `image-<i>.png` through a `.part` file,
   before the answer is priced; then `generation.json` gets the usage, the billed tokens, `cost_usd`, the seconds,
   `x-request-id`, the answer's fields (without the image data) and the files' sizes, sha256 and pixel sizes; a row
   goes to `log.csv`. An answer without a `usage` block keeps its images and is counted at its estimate
   (`priced_from: "estimate"`, else `"usage"`). Whatever fails after the request went out, the item never stays
   `running`: it is marked failed with the request counted as maybe billed.

A medium request takes 20 to 30 s, high about 50 s (the docs: complex prompts up to 2 minutes). A batch of more than
a few items runs in the background (`> tools/out/<log> 2>&1; echo "exit=$?" >> <log>`, checked with
`tools/run.sh wait <log>`); the runner prints one progress line per item (`[n/N] <item>`, the request with its
estimate, each saved image, the item's tokens, $ and seconds, the batch's spend against the cap).

## The raw folder

```
<raw>/<batch id>/log.csv
<raw>/<batch id>/<item id>/generation.json
<raw>/<batch id>/<item id>/image-<n>.png
```

`generation.json`: `batch`, `batch_file`, `service`, `item`, `variant`, `kind`, `prompt`, `model`, `quality`,
`size`, `n`, `estimated_usd`, `prices_per_million`, `plan`, `terms_url`, `licence`, `ai_generated` (true), `approval`
(by, at, ref, cost_cap_usd), `status` (`running`, `done`, `failed`), `error`, `started_at`, `finished_at`, `cost_usd`,
`inputs` (each reference's `file` or `from`/`pick`, `path`, `media_type`, `bytes`, `sha256`, `provenance`),
`requests` (per attempt: `sent_at`, `endpoint`, `request`, `estimated_usd`, `estimated_tokens`, `outcome` (`sent`,
`answered`, `error`, `unsure`), `status`, `finished_at`, `seconds`, `attempts`, `request_id`, `usage`,
`priced_from`, `billed_tokens`, `cost_usd`, `answer`) and `files` (`name`, `bytes`, `sha256`, `width`, `height`).

`log.csv` columns: `time, item, variant, kind, status, model, quality, size, images, input_tokens, output_tokens,
cost_usd, seconds, request_id, files`; `images` is the number of reference images the request sends (a `from`
without `pick` counts all its source's images), `files` the number it saved.

`<raw>/<batch id>/run.lock` exists only while a run holds the batch.

An asset made from these images records (`docs/manifest.md`) `ai_generated = true`, the model as
`source.model_version` and the requests' `request_id`s as `source.task_ids`, with the batch file as its record.

## The API as read on 2026-10-20

From developers.openai.com (the image generation guide, the Python reference of `images.edit`, the model page of
`gpt-image-2.5-sunburst`): models `gpt-image-2.5-sunburst` and `gpt-image-2.5-flare` (snapshots `-2026-09-08`), on
`/v1/images/generations`, `/v1/images/edits` and `/v1/batch`; quality `low`, `medium`, `high`, `xhigh`, `max`, `auto`
(this client sends only medium and high); `output_format` `png` (default), `jpeg`, `webp`; `background`; `n` 1 to
10; an edit takes up to 16 images (`image[]` parts in multipart), each under 50 MB, and an optional PNG `mask`
applied to the first; GPT image models always answer with base64. Default rate limits (Build tier): 250,000 tokens
and 20 images a minute. The Batch API halves the output price ($15/M) for jobs that may wait up to a day; not used
yet.

## The first edit test, batch 2026-10-20-openai-edits-test (art #196)

One edit at medium, 1536x1024, of `raw:research/2026-10-19-parts-kit/face-crops/m2_pout.png` (380x960, our own Meshy
generation, sha256 `cfa6b635...38ee47`) with the prompt of batch `2026-10-20-alien-face-sheets-2` item mp1 (the pout
mouth's six talk shapes on one 3x2 sheet). Measured: 278 text and 416 image input tokens, 343 output tokens,
**$0.0150**, **19.5 s**, one attempt (`req_ac89184bc5054d279760942c2ccf376c`). Meshy's mp1 of the same prompt and
reference cost 12 credits.

The output keeps the reference's look: the same teal head with its curled crest, the half-closed bored eyes under
the coral lid rims, the two nostril slits, the pale muzzle and the glossy red lips, in the same soft vinyl-toy
rendering, all six heads consistent. The six shapes read in order (rest, M, small, A with teeth and tongue, E, a
round O kiss). Unlike Meshy's sheet it frames the heads larger and cuts them at the neck (Meshy kept the reference's
whole bust), and its rest panel shows a slight gap between the lips. Saved in
`D:/prime-art-raw/2026-10-20-openai-edits-test/mp1/image-0.png`.

## Batch 2026-10-21-alien-mouth-views (art #196 M19)

Edits of mp1's rest and A panels (a 720 px mouth crop and the 512 px head panel as references) into an isolated lip
sculpture, three views stacked in rows on one 1024x1536 sheet (rows keep the views consistent; they are cut apart for
Meshy). Measured: medium, n = 3, two references: 894 to 945 text and 6,144 image input tokens, 1,029 output tokens
(343 per image, the same as one medium 1536x1024), **$0.085** a request, 23 to 30 s; high, n = 1, the picked image and
one crop as references: 298 to 315 text and 2,560 image input tokens, 1,372 output tokens, **$0.063**, about 33 s. The
batch: **$0.2956** of its $3 cap (`req_85f6e47a...`, `req_bfbca41c...`, `req_e5cc1b93...`, `req_26ad9708...`). All
six medium sheets were clean and close to mp1's lips; the high redraws kept the picks almost exactly, a little
crisper. The images: `D:/prime-art-raw/2026-10-21-alien-mouth-views/`.

## Batch 2026-10-21-alien-mouth-views-2 (art #196 M20)

The hybrid pout's other closed shapes, M (pressed) and small (slightly parted), as the same isolated lip sculpture as
M19's `rest-h`: edits with that sheet first ("keep everything, change only the shape") and mp1's M or small panel (a
720 px mouth crop) second, so the three closed pieces share the lips, the light and the scale. Medium, n = 3:
$0.0969 and $0.0972 (921 to 969 text, 7,680 image input and 1,029 output tokens; the estimate's 2x margin said $0.104);
high redraws of the picks (m-m 0, small-m 0), n = 1: $0.0632 and $0.0633. **$0.3205** of the $2 cap. All six medium
sheets kept the rest sheet's layout and look; M came out slimmer than mp1's M (the prompt asked for "a little
flatter"), so the fit stretches it (`docs/godot.md`, M20).


## Batch 2026-10-22-alien-roster-r1 (art #196, roster round 1)

Direction D's roster as 2D concepts (the engineer's yes, comment 6326683249): edits at medium, 2560x1440, n = 4 each,
with our own approved images as style references (u1's front, rf2, el2): **l1** ten heads (five men, five women) on
the one body, front; **l2** the same ten heads in 3/4, an edit of the picked l1 image; **o1** rf2's head on the body in
ten present-day outfits; **c1** the strongest head (a crop of l2) in eight skin colours. Measured: three references
and a 3,000-character prompt, 3,088 text and 12,416 image input tokens; 1,911 output tokens for four 2560x1440 images
(about 478 each, 1.4 times a medium 1536x1024); $0.086 to $0.172 a request, 26 to 33 s. **$0.4884** of the $6 cap.
The styles held from the first request (smooth toy look, one body); an edit of one picked image (l2) gives four near
copies, so variety comes from the generation before it. Images: `D:/prime-art-raw/2026-10-22-alien-roster-r1/`;
sheets and handoff: `D:/prime-art-raw/research/2026-10-22-roster/`.

## Batch 2026-10-22-alien-roster-r2 (art #196, roster round 2)

The ten head concepts of the design research (`D:/prime-art-raw/research/2026-10-22-roster/design/`), one edit per
head at medium, 1024x1280, n = 3, under the standing permission: heads 1 and 3 from their round-1 crops plus rf2, the
eight new heads with rf2 as a style reference only (the prompt says what the reference is for). Measured: one
reference and a 1,900-character prompt, 1,400 to 1,590 text and 3,072 image input tokens, 1,133 output tokens for
three 1024x1280 images (about 378 each); $0.066 a request, $0.085 with two references, 21 to 24 s. **$0.6999** of the
$5 cap. A style reference used only for finish and light held the look without copying its face; framing (one bust
edge) did not follow the prompt reliably. Images: `D:/prime-art-raw/2026-10-22-alien-roster-r2/`; JPEGs, overview and
handoff: `D:/prime-art-raw/research/2026-10-22-roster/design/`.

## Batch 2026-10-22-alien-roster-r3 (art #196, roster round 3)

Two new candidates for each of round 2's four rejected heads and redraws of h06 (wrap-around eyes) and h08 (the real
axolotl's feathery gills and bead eyes), medium, 1024x1280, n = 3, under the standing permission; the batch file is
generated from `D:/prime-art-raw/research/2026-10-22-roster/design/r3/concepts_r3.src.json`. 12 requests (two revised
prompts after the first look): $0.066 to $0.068 with one reference, $0.097 to $0.098 with two; **$0.8645** of the $5 cap. Unless
the prompt says "solid dark, no whites" and describes a non-human mouth, the model gives every head the same human
eye and small lips. Images: `D:/prime-art-raw/2026-10-22-alien-roster-r3/`; JPEGs, overview and handoff: `.../design/r3/`.

## Batch 2026-10-22-alien-roster-r3b (art #196, roster round 3b)

Four new alien women for the slots W7 and W10, each prompt writing the eye (solid glossy dark, no white) and the
mouth (beak, lipless slit, crease, seam) as non-human, two revised after a look, and h08b (round 2's h08-2 with only its
gills made feathery), medium, 1024x1280, n = 3, under the standing permission; the batch file is generated from
`D:/prime-art-raw/research/2026-10-22-roster/design/r3b/concepts_r3b.src.json`. 7 requests: $0.067 to $0.068 with one
reference, $0.097 with two; **$0.5044** of the $3 cap. No head came out the stock alien-woman face; "no lips" alone
still gave a small round mouth pouting human lips, while "flat, flush with the face, nothing pushed forward, no pout"
held. Images: `D:/prime-art-raw/2026-10-22-alien-roster-r3b/`; JPEGs, overview and handoff: `.../design/r3b/`.

## Batch 2026-10-22-alien-roster-r4 (art #196, roster round 4)

A new ten heads (five men, five women), each built from one real animal read up first (shoebill, humphead wrasse, stag
beetle, triceratops, gharial; moth, eyelash viper, seahorse, cassowary, lionfish), medium, 1024x1280, n = 3, rf2 as
the style reference, round 3's lead, framing sentence and style tail; the batch file is generated from
`D:/prime-art-raw/research/2026-10-22-roster/design/r4/concepts_r4.src.json`. 13 requests (three revised prompts after
the first look), $0.067 to $0.068 each. Writing the animal's own eye and mouth into the prompt held for most heads, but
the model still slides back to a human face where the animal's feature can sit on one: a forehead hump becomes a quiff
over pouting lips, a beetle's shell a visor over a human chin, a moth the classic big black alien eyes. Images:
`D:/prime-art-raw/2026-10-22-alien-roster-r4/`; JPEGs, overview and handoff: `.../design/r4/`.
