# prime-game-art

The private art repository of prime-game (a first-person multiplayer social deduction game in Godot 4.7.2, public repo
xperiaroco2/prime-game). Here agents turn raw 3D generations and downloads into checked, approved character, clothing,
accessory, prop and animation assets: a headless Blender pipeline, review sheets, provenance manifests. The plan and
the engineer's decisions: xperiaroco2/prime-game#165; the pipeline: `docs/pipeline.md`; the foundation ADR:
`docs/decisions/2026-10-02-art-repo-foundation.md`. The engineer (xperiaroco2) writes no code and approves; the designer
(@SwiftySinister) approves the look. Agents write everything else and verify it from the command line.

## Rules
- **Paid services and downloads need the engineer's yes for each batch.** No generation on a paid service (Meshy or any
  other) and no download from the internet without it; the yes (prompts, count, credits) is recorded in the batch file
  and on the issue. Reading web documentation is fine. Nothing is installed without the engineer's yes.
- **No Godot or Blender window.** Blender runs only as `blender -b` through `tools/runner/blender.py`; Godot only with
  `--headless`, and pictures come from the game's `tools\run.cmd shot`.
- **Every source and asset has its licence recorded** in its `manifest.toml` (`docs/manifest.md`): licence, licence URL,
  `public_repo_ok`, `ai_generated`. Never free-plan AI output, Mixamo, store packs (Synty, Fab, Unity Asset Store),
  ActorCore or Rokoko raw files, or non-commercial data in anything that may go public.
- **Raw generations and downloads live in `D:/prime-art-raw`**, copies of chosen originals in `OneDrive/prime-art-raw`;
  never in git (`raw/` is ignored). Manifests record their relative paths and SHA-256.
- **Review images go to the engineer through private artifact pages**, never committed. Committed files are sources,
  approved exports, manifests and reports.
- **The Meshy key comes from `MESHY_API_KEY`** (the user environment) and is never printed, logged or committed. Agents
  never enter keys, passwords or payment details anywhere; the engineer buys plans and sets keys.
- **AI rules:** never name How to Fish or any other game or character in a prompt and never upload their screenshots;
  no personal photos; `ai_generated` is recorded per asset.
- **Git:** only the engineer merges into `main`. Push task branches only (`git push -u origin <branch>`); no push to
  `main` and no force push by hand (the pre-push hook refuses a push to or a deletion of `main`); no `git stash`
  (set work aside with a WIP commit). Agents never close issues.
- **English and small steps:** the repo is English (code, docs, commits, issues, PRs); Conventional Commits, one
  logical change per commit; commits made by an agent end with its `Co-Authored-By` trailer.
- **Game code is never touched from here.** Approved assets enter xperiaroco2/prime-game through a game-repo PR under
  the character contract (`contract/`, `docs/contract.md`), by the game's own task workflow.
- **Verify before claiming.** Never say something works unless you ran it; show the command and its result. Check the
  environment live (`doctor`, `pins`) rather than trusting docs or memory; fix a doc that is wrong.
- **No secrets in git** (tokens, keys, passwords). This is a hobby project: protections prevent accidents, not attacks.

## Layout
| Path | What |
|---|---|
| `assets/<kind>/<id>/` | One asset: `manifest.toml`, `source/` (.blend), `export/` (.glb), `report.json` |
| `batches/` | Generation batch files with the engineer's recorded yes (`docs/meshy.md`) |
| `contract/` | The character contract: skeleton, slots, sockets, budgets (`docs/contract.md`) |
| `docs/` | `pipeline.md`, `manifest.md`, `blender.md`, `meshy.md`, `contract.md`; `decisions/` (ADRs), `research/` |
| `tools/run.py`, `run.cmd`, `run.sh` | The runner; commands are modules in `tools/runner/commands/` |
| `tools/runner/` | `cli.py`, `common.py`, `pins.py` (tool versions and paths), `blender.py` (headless Blender) |
| `tools/blender/` | Scripts that run inside Blender (`docs/blender.md`) |
| `tools/godot/` | The headless Godot project that generates the contract |
| `tools/githooks/` | `pre-push`; `doctor` sets `core.hooksPath` to it |
| `tools/tests/` | unittest tests, `test_<area>_*.py`; a test needing Blender or Godot skips when it is missing |
| `tools/out/` | Runner output and temporary files (ignored) |

Git LFS stores every binary (`.gitattributes`). All of the account's repos share 10 GiB of LFS storage: commit only
approved exports and the sources they need.

## Commands
Windows: `tools\run.cmd <command>`. Git Bash: `tools/run.sh <command>`. Python 3.11+, standard library only.

| Command | What it does |
|---|---|
| `doctor [--quick]` | Checks Python, git, Git LFS, the hooks path (sets it), Blender, glTF-Validator, Godot, the raw folders, `gh`, `MESHY_API_KEY` (yes/no). Run it first in every session |
| `verify` | `selftest`, then `manifest-check`: the definition-of-done gate |
| `selftest [-v] [-p PATTERN]` | unittest discovery over `tools/tests` |
| `manifest-check [--hashes] [--root DIR]` | Validates every `assets/**/manifest.toml`; `--hashes` re-hashes the raw files |
| `pins [--get NAME]` | Pinned tool versions and paths |
| `probe`, `render` | Headless Blender: probe a model; 8-view review sheets (#2, `docs/blender.md`) |
| `meshy`, `raw-backup` | The Meshy client for approved batches; copy chosen raw files to OneDrive (#3, `docs/meshy.md`) |
| `contract`, `check`, `rename-bones` | Generate the contract from Godot; check a model against it; rename a rig's bones (#4, `docs/contract.md`) |

Logs and reports go to `tools/out/`. Temporary files go there or to your scratchpad, nowhere else.

## Shell
PowerShell 5.1 is the primary shell; the Bash tool is Git Bash. In Git Bash `python` may be a Store stub: use
`$PYTHON_BIN`. Multi-line commit messages and PR bodies go through a file (`git commit -F`, `gh pr create
--body-file`). Use absolute paths; with worktrees, `git -C <path>`.

## Definition of done
1. `tools/run.py verify` is green; paste its tail. Red: stop and report.
2. A fresh-context review of the diff; fix the findings or list them in the PR.
3. Docs updated if durable knowledge changed (`docs/`, an ADR for a decision).
4. A PR into `main` (or a stacked PR into its parent branch) with the linked issue, a summary, the verification
   commands and their output, and review images as private artifact links; a handoff comment on the issue.
5. Only the engineer merges into `main`. Agents never close issues.

## Stop and ask the engineer before
- Any generation, download, install, purchase or subscription (see Rules).
- Adding a dependency (the runner is standard library only) or changing the character contract once assets exist.
- Anything destructive to git history or to the raw folder; anything about the look (with the designer), money or
  licences outside the allowlist.
- Batch such questions into one message, with options and a recommendation.
