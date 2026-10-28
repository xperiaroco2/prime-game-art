# prime-game-art

The private art repository of prime-game (a first-person multiplayer social deduction game in Godot 4.7.2, public repo
xperiaroco2/prime-game). Here agents turn raw 3D generations and downloads into checked, approved character, clothing,
accessory, prop and animation assets: a headless Blender pipeline, review sheets, provenance manifests. The plan and
the engineer's decisions: xperiaroco2/prime-game#165 and the stage plan issues here (stage 1: #16); the pipeline:
`docs/pipeline.md`; the foundation ADR: `docs/decisions/2026-10-02-art-repo-foundation.md`; the trust model:
`docs/decisions/2026-10-03-trust-model.md`. The engineer (xperiaroco2) writes no code. He decides taste, money and
large or hard-to-reverse questions (the full list is under "Decisions" below) and trusts the art manager with
the rest. He also acts as the designer and approves the look (the designer @SwiftySinister is not active; the trust
model's amendment of 2026-10-08). Agents write everything else, verify it from the command line, and the art manager merges it.

## Rules
- **Paid services and downloads.** Three standing permissions from the engineer need no separate yes:
  - Meshy generation within the plan's credits (2026-10-03);
  - free downloads from official sources (2026-10-03);
  - OpenAI image generation with `gpt-image-2.5-sunburst` from `OPENAI_API_KEY`, within a batch's `cost_cap_usd`:
    medium for exploration and many variants, high for focused work on one piece (2026-10-20,
    [#196, comment 6291187194](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6291187194);
    xperiaroco2/prime-game#1095; `docs/openai-images.md`).

  Every Meshy or OpenAI batch still has a batch file with its `approval_ref`, and the spend goes into the plan issue's
  reports. These still need the engineer's yes: purchases, subscriptions, paid generation beyond the plan's credits,
  OpenAI image generation beyond the prepaid balance he funds, on another model, or above a batch's `cost_cap_usd`,
  generation on any other paid service, any other download (mirrors, re-uploads, unofficial sources), and
  installing anything. Reading web documentation is fine.
- **No Godot or Blender window on screen.**
  - Blender runs only as `blender -b` through `tools/runner/blender.py`.
  - Godot checks run with `--headless`.
  - Godot pictures come from a window kept off-screen, never minimized, never headless (a headless Godot draws
    nothing). `--position -30000,-30000` alone does not do it: Godot 4.7.2 on Windows clamps a new window into the
    primary screen (#214). Every window run goes through `_godot.window()`: one borderless, unfocused pixel that the
    clamp leaves just past the screen's right edge, which `godot/lib/offscreen.gd` moves off-screen before growing
    it; the runner refuses a run whose script did not report its window off every screen (`docs/godot.md`, "The
    off-screen window").
- **Every source and asset has its licence recorded**:
  - a downloaded pack or library in `sources/<id>.toml`;
  - an asset in its `manifest.toml` (`docs/manifest.md`).

  Each record holds the licence, the licence URL, `public_repo_ok` and `ai_generated`. Never put any of these in
  anything that may go public: free-plan AI output, Mixamo, store packs (Synty, Fab, Unity Asset Store), ActorCore or
  Rokoko raw files, or non-commercial data.
- **Raw generations and downloads live in `D:/prime-art-raw`**, copies of chosen originals in `OneDrive/prime-art-raw`;
  never in git (`raw/` is ignored). Manifests and source records hold their relative paths and SHA-256.
- **Review images go to the engineer through private artifact pages**, never committed. Committed files are sources,
  approved exports, manifests and reports.
- **The Meshy key comes from `MESHY_API_KEY`** (the user environment) and is never printed, logged or committed. Agents
  never enter keys, passwords or payment details anywhere; the engineer buys plans and sets keys.
- **The OpenAI key comes from `OPENAI_API_KEY`** (the user environment; a prepaid balance) and is never printed,
  logged or committed, like the Meshy key.
- **Release quality, one piece at a time** (the engineer, 2026-10-17, #196): what is made from now on is meant for the
  final release, or close to it; no throwaway breadth. Characters: one base character first, then interchangeable
  parts (eyes, mouths, noses, hairstyles, skin colours, outfits), one part at a time, each polished until nothing about
  it looks dumb or ugly, and judged alone. No invented names, personas, backstories or per-character gags unless he
  asks. Variant grids stay for tuning a parameter, never for making many whole characters at once
  (`docs/decisions/2026-10-17-release-quality.md`).
- **AI rules:** never name How to Fish or any other game or character in a prompt and never upload their screenshots;
  no personal photos; `ai_generated` is recorded per asset.
- **Git:**
  - The art manager merges task PRs into `main` with `gh pr merge` after the gate in the definition of done.
  - Task branches are pushed with `git push -u origin <branch>`; nobody pushes to `main` directly.
  - No force push by hand. The pre-push hook refuses a push to `main` or a deletion of it.
  - No `git stash`: set work aside with a WIP commit.
  - Agents do not close issues by hand; a merged PR's `Closes #n` closes its issue.
- **English and small steps:** the repo is English (code, docs, commits, issues, PRs); Conventional Commits, one
  logical change per commit; commits made by an agent end with its `Co-Authored-By` trailer.
- **Game code is never touched from here.** Approved assets enter xperiaroco2/prime-game through a game-repo PR under
  the character contract (`contract/`, `docs/contract.md`), by the game's own task workflow; the game repo's `main` is
  merged by humans.
- **Verify before claiming.** Never say something works unless you ran it; show the command and its result. Check the
  environment live (`doctor`, `pins`) rather than trusting docs or memory; fix a doc that is wrong.
- **No secrets in git** (tokens, keys, passwords). This is a hobby project: protections prevent accidents, not attacks.

## Layout
| Path | What |
|---|---|
| `assets/<kind>/<id>/` | One asset: `manifest.toml`, `source/` (.blend), `export/` (.glb), `report.json` |
| `batches/` | Meshy and OpenAI image batch files with their recorded approval (`docs/meshy.md`, `docs/openai-images.md`) |
| `catalogue/` | The parts catalogue of the Ultimate Modular packs with compatibility rules, regenerated by `catalogue` (`docs/catalogue.md`) |
| `contract/` | The character contract: skeleton, slots, sockets, budgets (`docs/contract.md`); `bone_maps/` |
| `.claude/agents/` | Lean workflow agent types `art-reader` and `art-writer` (`docs/agents.md`, #44) |
| `docs/` | `agents.md` (cost rules), `pipeline.md`, `assembly.md`, `godot.md`, `catalogue.md`, `faces.md`, `kit.md`, `house.md`, `house-outdoor.md`, `house-garden.md`, `ship.md`, `props.md`, `animations.md`, `manifest.md`, `blender.md`, `meshy.md`, `openai-images.md`, `contract.md`; `decisions/` (ADRs), `research/` |
| `kits/` | Modular kit specs (`house.json`): the grid, budgets, materials, paints and pieces the `kit` command builds (`docs/kit.md`) |
| `layouts/` | Map layouts as data: `ship/` (the empty ship: numbers, the interior and exterior lanes' pieces and placements, `docs/ship.md`), `house/` (the House map's levels: rooms, doors, windows, holes, stairs; `house.toml` holds the kit path), turned into Godot scenes by `house` (`docs/house.md`) |
| `props/` | Prop specs: `library.toml`, the House dressing library's mapping file (per prop its pack source or procedural shape, size, paints, pivot, collision; the `props-library` command checks and builds it), and `tasks.toml`, the task-station props the `props` command builds (`docs/props.md`) |
| `faces/` | The face kit's style families (`styles.json`), review settings and review heads (`docs/faces.md`) |
| `godot/` | The Godot 4.7.2 import-check project for `godot-check`, `frames`, `showroom`, `kit`, `props` and `props-library` (`props/lineup.gd`: the dressing library's line-up; `ragdoll/`: the ragdoll proof with `builder.gd`, the reference builder the game copies, #115); `import/` and `.godot/` ignored; one run at a time (`docs/godot.md`); `plush/`: the vault plush's material and review shots, art #297; `crystal/`: the energy crystal's look (`crystal.gd`, two states by one charge) and review shots, art #263 |
| `recipes/` | Character recipes for the assembler (`docs/assembly.md`) |
| `sources/` | Source records of downloaded packs and libraries: licence, page, raw paths and hashes (`docs/manifest.md`) |
| `tools/run.py`, `run.cmd`, `run.sh` | The runner; commands are modules in `tools/runner/commands/` |
| `tools/runner/` | `cli.py`, `common.py`, `pins.py` (tool versions and paths), `blender.py` (headless Blender) |
| `tools/blender/` | Scripts that run inside Blender (`docs/blender.md`): `um/` (the Ultimate Modular assembler, `docs/assembly.md`), `retarget*.py` with `retarget_maps/` (bone maps), `anim_*.py` with `anim_review.toml`, `anim_edit*.py` (the clip edits), `anim_set*.py` with `anim_sets/` (animation sets: the MVP, `docs/animations.md`), `catalogue*.py`, `faces_*.py`, `kit_build.py` and `kit_geom.py` (`docs/kit.md`), `props_task*.py` (the task props), `prop_geom.py`, `prop_lib.py` (the shared prop helper) and `prop_build.py` (the dressing library; `docs/props.md`), `plush_*.py` (the vault plush, a hero prop from a concept: clean, mouth, paint, bake, with `plush_run.py` the plain-Python driver; `docs/props.md`), `crystal_build.py` (the ship engine's energy crystal, a hero prop built from code from its drawing `crystal_dims.toml`, drawn by `crystal_drawing.py`, with `crystal_run.py` the driver; `docs/props.md`), `export_glb.py` |
| `tools/workflows/` | Workflow script templates: `art-lab-round.js` (a lab round: builder steps and one critic on the per-launch `critic_model`; with `control_model`, the A/B's control critic and blind judge), checked by `workflow-check` (`docs/agents.md`) |
| `tools/godot/` | The headless Godot project that generates the contract |
| `tools/githooks/` | `pre-push`; `doctor` sets `core.hooksPath` to it |
| `tools/tests/` | unittest tests, `test_<area>_*.py`; a test needing Blender, Godot or the raw files skips when they are missing |
| `tools/out/` | Runner output and temporary files (ignored) |

Git LFS stores every binary (`.gitattributes`). All of the account's repos share 10 GiB of LFS storage: commit only
approved exports and the sources they need.

## Commands
Windows: `tools\run.cmd <command>`. Git Bash: `tools/run.sh <command>`. Python 3.11+, standard library only.

| Command | What it does |
|---|---|
| `doctor [--quick]` | Checks Python, git, Git LFS, the hooks path (sets it), Blender, glTF-Validator, Godot, the raw folders, `gh`, `MESHY_API_KEY` (yes/no). Run it first in every session |
| `verify [--full] [--base REF] [-j N]` | The definition-of-done gate: every fast test file (no Blender, no Godot) in parallel, the heavy test files the change needs against `--base` (default `origin/main`; `tools/tests/areas.toml`, the full suite when a shared module changed), then `manifest-check`; prints the heavy files it chose and why. `--full`: every test file, the night run on `main` (`docs/decisions/2026-10-14-verify-affected.md`) |
| `selftest [-v] [-p PATTERN] [-j N] [--write-timings]` | Every test file under `tools/tests` (or those matching `-p`), each in its own process: fast files in parallel, then heavy files one at a time inside the heavy-run lock; `--write-timings` rewrites `tools/tests/timings.json` |
| `manifest-check [--hashes] [--root DIR]` | Validates every `assets/**/manifest.toml` and `sources/*.toml`; `--hashes` re-hashes the raw files |
| `pins [--get NAME]` | Pinned tool versions and paths |
| `probe`, `render` | Headless Blender: probe a model; 8-view review sheets and animation contact sheets (`docs/blender.md`) |
| `assemble <recipe> [--ids] [--modes] [--out] [--blend] [--res] [--compare] [--look] [--bake] [--clay-lib]` | Assembles Ultimate Modular characters from a recipe: renders, `build_report.json`, one clean `.blend` per character; `--look clay` the clay look, `--bake` its textures from the per-piece clay library (`docs/assembly.md`) |
| `export <character.blend>... [--out DIR] [--textured]` | GLB with fixed options from saved characters; glTF-Validator `report.json`; `--textured` for baked clay characters (`docs/godot.md`) |
| `godot-check <glb>... [--strict-contract] [--humanoid] [--textured]` | Imports into `godot/` headless and asserts the skeleton, separate skinned parts, animations, size, feet, facing and loop modes; `--textured`: textures, normal maps, sizes, surfaces (`docs/godot.md`) |
| `frames <glb> [--clips] [--compare] [--video] [--blend]` | Godot-rendered motion frame sheets in an off-screen window; a Blender comparison of joints and bone rotations; MP4 clips (`docs/godot.md`) |
| `slice [--cast ID] [--anim-set DIR] [--blend] [--asset DIR] [--review DIR] [--no-frames] [--own-proportions]` | The game's slice character (#42 part C): a clay cast member with the MVP set's clips minus the knockdown, one textured GLB, `godot-check --strict-contract --humanoid --textured`, `frames`, a turnaround; `--asset` writes its asset folder (manifest with per-clip provenance, `package.json`, `HANDOFF.md`); `--own-proportions` takes a skeleton with its own proportions, its root and hip keys scaled to the leg length (`docs/godot.md`) |
| `showroom [<glb>] [--grid ladder\|tune\|warm\|expose] [--variants] [--beside PNG] [--write-presets]` | The look question (art #140): a character under up to eight Godot look variants (the ladder: the frames stand, AgX, sky light and reflections with an eye catch light, SSAO, soft shadows, SSS on the clay; `--grid tune`, `--grid warm`, `--grid expose`: steps 2 and 3's tuning grids) in an off-screen window: face and body sheets beside the approved Blender face, GPU ms per variant, each variant's pixel change against its parent (`change.md`), a numeric check of the faces against Blender (`look.md`); `--write-presets` writes the recommended look per graphics preset, `godot/showroom/look_presets.json` (`docs/godot.md`) |
| `bench [<glb>...] [--proxy-from BLEND] [--copies 10,20] [--frames N] [--budget-ms MS]` | What a character costs (art #212): N copies in a meeting ring playing their idle, a directional light with 4 shadow splits and a shadowed omni lamp, 1920x1080 in an off-screen Godot window; per variant (automatic LOD on/off, full-mesh shadows or a shadow proxy, a hand-made LOD2, one GLB per face-morph count) the median GPU and render CPU ms, process and frame ms, primitives, draw calls, memory and the bodies beyond the LOD2 distance; `bench.json`, `bench.md`, `sheet.png`; `--proxy-from` first makes a 40k stand-in with 0/32/64 head morphs in headless Blender (`docs/godot.md`) |
| `outdoor [--check] [--out DIR] [--proof [DIR]]` | The House map's plot from `layouts/house/outdoor/`: fence, ground, street, outdoor stairs, props, sky and backdrop flats; plan, GLBs and PNGs into `<raw>/house/81/build`; `--proof`: glTF-Validator, then Godot off-screen walks (fence, wicket, gates, stairs) and a review sheet (`docs/house-outdoor.md`) |
| `catalogue [--check] [--renders ...]` | The parts catalogue and compatibility rules, `catalogue/ultimate_modular.json`; `--check` regenerates and compares (`docs/catalogue.md`) |
| `faces [--families] [--expressions] [--sheets] [--check] [--kit-check [N]]` | The face kit's style families rendered as review sheets; `--kit-check`: the clay face kit's check on N random faces per body type, non-zero on a failure (`docs/faces.md`) |
| `kit [--only] [--no-build] [--no-godot] [--proof DIR]` | Builds a modular kit (`kits/house.json`) as one GLB per piece in headless Blender into `<raw>/kits/`, checks each (grid, budgets, glTF-Validator, Godot import, collision); `--proof` walks and shoots a test room off-screen (`docs/kit.md`) |
| `house [--check] [--clutter] [--out DIR] [--walk DIR] [--export DIR] [--bake ZONES [--count DIR]] [--no-merge] [--cell M\|room]` | Checks the House layout (`layouts/house/*.toml`: grid, openings, corners, footprints, stairs and holes) and writes one Godot scene per room and level and `house.tscn` from the kit; `--clutter` regenerates the rooms' seeded clutter blocks first; `--walk` walks a 1.36 m capsule through every door and flight off-screen and shoots the review sheet; `--export` writes the game-ready package (GLBs, one scene per game room, `package.json`) into DIR, loads it headless, `--sheet` shoots three rooms from it off-screen; `--bake` bakes a zone's light in an off-screen editor window (night only), `--count DIR` instead counts each review view's draw calls against the budget; the scenes draw each room's shell merged and its static dressing batched, `--no-merge` draws every piece on its own, `--cell` splits them into grid cells (tried, not used); `--walk` also counts each view's draw calls against the budget (`docs/house.md`) |
| `attic [--json PATH] [--shoot DIR] [--stair DIR] [--kit DIR]` | Checks the House attic's old things and hiding spots (pick-up reach and line of sight), the dormer's climb-out and the free roof's items and lookout view (`layouts/house/dressing/attic_roof/`; `docs/house.md`); `--shoot` renders them at dusk off-screen; `--stair DIR` shoots the attic stair's proof (#183) |
| `garden [--check] [--out DIR] [--proof [DIR]]` | The garden and the greenhouse roof from `layouts/house/outdoor/garden.toml`: path network, fixed props, seeded scatter (trees, bushes, flower beds), the glass roof's pieces and gable rafters, the herb route against the design doc; `garden.json` and a plan into `<raw>/house/80/build`; `--proof`: the walks, the glass roof's ray test and the dusk sheet in Godot off-screen (`docs/house-garden.md`) |
| `ship [--check] [--build [--only IDS] [--out DIR]] [--godot] [--walk DIR [--no-video]] [--shoot DIR [--views FILE|PREFIXES]] [--motion DIR] [--vent-anim DIR] [--charger-cycle DIR] [--export DIR [--no-compare]] [--play [DIR]] [--play-test DIR]` | The empty ship, a wide metal manta (art #263; since v2 the mirrored layout: round hall, two straight corridors, two round tip rooms): checks `layouts/ship/` (footprint, corridor width, the tip rooms' outer wall, floor and plain wall station spots with their pass behind, every room and piece inside the hull, head room, one entrance) and writes a text plan; `--build` one GLB per piece (interior and exterior lanes, a shared material library) in headless Blender into `<raw>/ship/v2/pieces/` (the layout's `raw_dir`) with glTF-Validator; `--godot` the headless import (sizes against Blender's, colliders) and a capsule walk from the ramp into both tip rooms and back; `--walk DIR` that walk into DIR, then an eye-height walk-through video (1280x720, about 90 s, under 15 MB) from an off-screen window; `--shoot DIR` the night shots, the plan view beside plan-3 and a sheet off-screen (`--views`: a JSON file of views, or name prefixes); `--motion DIR` the stations' moving parts (the vents: slats and marker driven on their GLBs, checked by numbers, an MP4 and sheets) off-screen; `--vent-anim DIR` the vents' animation (`godot/ship/vent_anim.gd`'s demo) in place at night, an MP4 and a key-frame sheet, off-screen; `--charger-cycle DIR` the east crystal charger's cycle (idle, the crystal in, the button, charging, charged, out) at night from the player's eye, `cycle.mp4` and a key sheet, off-screen; `--export DIR` the game-ready package (art #335: `assets/environment/ship/`, `levels/ship/ship.tscn` with the station spots and the spawn, `package.json`), its headless load, sizes and walk, and three views beside `--shoot`'s by numbers; `--play [DIR]` the engineer's first-person walk in an on-screen window, P a screenshot with its position (agents run only `--play-test DIR`, off-screen) (`docs/ship.md`) |
| `zones [--shoot DIR]` | Checks the yard's chill zone and photo gazebo (`layouts/house/outdoor/zones/*.toml`: stations, opening, fixtures, overlaps, walk); `--shoot` assembles them at dusk off-screen and shoots the review frames and sheet (`docs/zones.md`) |
| `props [--only] [--no-build] [--no-godot] [--review DIR]` | Builds the House map's procedural props (`props/tasks.toml`: task stations, room-defining pieces) as one GLB each into `<raw>/props/task/`, checks each (size, pivot, budget, game surface, glTF-Validator, Godot import, collision); `--review` renders the line-up sheets (`docs/props.md`) |
| `props-library [--measure] [--table FILE] [--build] [--batch N] [--only IDS] [--no-godot] [--sheets DIR] [--fine-compare DIR]` | Checks the dressing library's mapping file (`props/library.toml`): classes, budgets, paints, licences, each pack prop's scale against its inventory size; `--measure` re-reads the pack files; `--build` makes one GLB per prop in headless Blender into `<raw>/props/library/v3/` and checks them, then Godot's headless import (sizes, pivots, collision, light anchors); `--sheets` adds the line-up sheets from an off-screen window; `--fine-compare` measures the fine pack's shared textures and surfaces against other GLBs (`docs/props.md`) |
| `ragdoll <glb> [--out DIR] [--asset DIR] [--fall] [--shots DIR]` | A character's ragdoll data from its GLB (plain Python): 16 bodies with shapes, masses and joints, and the `downed` layer rule; `--asset` writes it into the character package (`export/<id>.ragdoll.json`, `package.json`, `HANDOFF.md`); `--fall` is the Godot 4.7.2 Jolt proof, run headless (`godot/ragdoll/`); `--shots DIR` produces the fall and shapes sheets from an off-screen window (`docs/godot.md`, `docs/contract.md`) |
| `retarget [--body] [--library ual2\|tm] [--clips] [--blend] [--floor]` | Bakes Universal Animation Library (UAL1, UAL2) and Meshy text-to-motion (`tm`) clips onto a body type's Ultimate Modular armature (`docs/animations.md`) |
| `anim-review <inventory\|clips\|pairs\|rates\|sheets\|table\|all> [--body] [--sources] [--clips]` | Judges animations in motion: inventory, measures, strips, MP4 clips, side-by-side pairs, the game's speeds (`rates`), sheets, table (`docs/animations.md`) |
| `anim-set [--set mvp] [--body] [--clips] [--out] [--no-export] [--no-godot]` | Builds an animation set per body type from its settings (sources, clip edits, loops, layers): `.blend`, GLB, godot-check and the set's checks into `<raw>/anim-sets/<set>/` (`docs/animations.md`) |
| `nightly [--worktree DIR] [--no-issue]` | The night run (the art manager, each night, in the background): fetches `origin/main` into the dedicated worktree `<main checkout>-wt/nightly` (created if missing), runs `verify --full` there with the log in `tools/out/nightly/<date>.log`, appends a one-line summary to `tools/out/nightly/summary.log`; red: opens or comments on the issue "nightly: verify --full is red on main" (`docs/decisions/2026-10-14-verify-affected.md`) |
| `workflow-check <script.js>...` | Refuses a workflow script that breaks the cost rules (LF, `meta`, `node --check`, `agentType`, effort, models, `BOUNDS`, the 180 s wait rule); the manager runs it before every launch (`docs/agents.md`) |
| `wait <log> [--max S]` | Waits at most 170 s (the default and maximum `--max`) for a background run's last log line `exit=<n>`; prints its `verify:` lines or last 8 lines and returns n, 124 while it runs (`docs/agents.md`, rule 1) |
| `ab-tally <judge.json>...` | Counts the art critic's Sonnet/Opus A/B: per side the valid (and serious), invalid and unsure remarks, the misses and the $, and the stop rule's verdict (`docs/decisions/2026-10-08-art-critic-model-ab.md`) |
| `cost [--since ISO] [--session PREFIX...] [--project DIR]` | Per-agent calls, context, cache rewrites after idle gaps and list $ from this checkout's Claude Code transcripts; `tools/out/cost/cost.json` (`docs/agents.md`, rule 8) |
| `meshy`, `raw-backup` | The Meshy client for approved batches; copy chosen raw files to OneDrive (`docs/meshy.md`) |
| `openai-images <estimate\|run\|status> <batch>` | OpenAI image batches (`gpt-image-2.5-sunburst`, medium or high): `estimate` the tokens and $ (no network), `run` generations and edits within the batch's `cost_cap_usd`, checked before every request, each image a PNG in `<raw>/<batch id>/<item>/` with `generation.json` and a `log.csv` row; `status` (`docs/openai-images.md`) |
| `contract`, `check`, `rename-bones` | Generate the contract from Godot; check a model against it; rename a rig's bones (`docs/contract.md`) |

Logs and reports go to `tools/out/`. Temporary files go there or to your scratchpad, nowhere else.

## Shell
PowerShell 5.1 is the primary shell; the Bash tool is Git Bash. In Git Bash `python` may be a Store stub: use
`$PYTHON_BIN`. Multi-line commit messages and PR bodies go through a file (`git commit -F`, `gh pr create
--body-file`). Use absolute paths; with worktrees, `git -C <path>`.

**No tool call of a workflow agent or subagent blocks over 180 s** (#43, #51). After 5 idle minutes the agent's
prompt cache expires, and the next call re-writes the whole context; that was about a quarter of a week's cost. The
180 s leave a margin for the overhead around a call, measured at about 94 s (p95) under load in prime-game#555. In the Bash
tool, start any run that can pass 180 s (Blender, Godot, `verify`, `meshy run`, other `tools/run.sh` commands) in the
background (`run_in_background`, `> <log> 2>&1` under `tools/out/` or the scratchpad, then `echo "exit=$?" >> <log>`);
it notifies on exit, or check its log with short calls, with gaps of at most 180 s. No `tail -f`, and no
`until ...; sleep` loop or `timeout` longer than 180 s; never start a second run while one is running. Every workflow
prompt carries this rule.

## Agent cost
An agent's cost grows with its context times its calls (`docs/agents.md`, #51). Workflows and their agents follow
these rules:
- no idle gap inside an agent near the 5-minute cache life (waits of at most 180 s);
- builder steps of about 60 calls, ending in a handoff note;
- lean briefs, and only the tools a role needs: every agent passes `agentType` `art-reader` or `art-writer` unless it needs a tool neither has (#44);
- quiet runs: the full log goes to a file, the agent reads its tail;
- contact sheets of about 1280 px for agents;
- variant grids instead of nudge-and-look loops;
- Opus at high effort only for builders of code, IK or geometry; Sonnet for critics, verifiers and read-only research;
- every launch is estimated beforehand and measured afterwards.

## Definition of done
1. `tools/run.py verify` (the affected run) is green; paste its tail. Red: stop and report. The full suite
   (`verify --full`) runs nightly on `main` (`nightly`); a red night run opens an issue that becomes a fix task.
2. A fresh-context review of the diff; fix the findings or list them in the PR.
3. Docs updated if durable knowledge changed (`docs/`, an ADR for a decision).
4. A PR into `main` (or a stacked PR into its parent branch) with:
   - the linked issue and a summary;
   - the verification commands and their output;
   - review images as private artifact links;
   - a handoff comment on the issue.
5. The art manager merges it with `gh pr merge` once:
   - the fresh reviews leave no open blocker or major;
   - `verify` is green on the merged tree (a trial merge when several PRs land together).

   The merge goes into the next report on the plan issue.

## Decisions: who decides (`docs/decisions/2026-10-03-trust-model.md`)
The art manager decides alone, and reports on the plan issue, what does not need the engineer:
- small matters;
- matters that are easy to change later;
- matters where the better option does not depend on his taste.

The list below always wins over this one.

It runs workflows for the stage's tasks while the account's weekly usage stays below 85%, counting a launch's
expected cost, and reports each launch and its cost. At 85% it launches nothing more, reports and asks. Every launch
is estimated before it starts; a launch over about 5% of the week stops after its first phase for a check
(xperiaroco2/prime-game#302).

Stop and ask the engineer, in one batched message with options and a recommendation, before:
- anything about the look or taste (the engineer approves the look);
- money: purchases, subscriptions, paid generation beyond the plan's credits;
- licences outside the allowlist; game-design rules;
- large or hard-to-reverse changes:
  - the character contract once assets exist;
  - deleting, moving or overwriting raw files (anything destructive to the raw folder);
  - anything destructive to git history;
- adding a dependency (the runner is standard library only) or installing a tool;
- anything in the game repo;
- loosening a rule in this file, the list above, the merge gate, the git hooks or the trust model itself.
  Tightening them needs no yes.

## Manager rules (one set for every prime-game track)
A manager session of this repo follows `D:\prime-game\docs\MANAGERS.md` (prime-game's main checkout beside this one;
missing or unreadable: https://github.com/xperiaroco2/prime-game/blob/main/docs/MANAGERS.md). Read it whole at the
session's start, before anything else, and again after a change to it reaches prime-game's `main`. It holds the mode
and effort, the kickoff (no "ultracode"), the "For you:" block, the keep-alive, when to hand over and the handover
comment with the ready kickoff the engineer pastes, and every launch's estimate with the check after a large
launch's first phase (§9); where this file differs on those, it wins.
Track: art. Plan issue: the current stage's `plan:` issue in this repo; the context: the app's context usage.
