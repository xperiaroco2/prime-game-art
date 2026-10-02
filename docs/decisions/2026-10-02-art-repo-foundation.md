# The art repository's foundation and the character contract

- **Status:** Accepted for this repository's own tooling (sections 1 to 6: layout, runner, hooks, raw folders,
  manifest, approval). **Proposed** for the character contract (section 7) until the body variants are chosen.
- **Date:** 2026-10-02
- **Deciders:** the engineer (answers on xperiaroco2/prime-game#165); technical choices by the art department's manager
  session under the engineer's delegation, announced on #165 and revertible. The look is decided with the designer.

## Context
prime-game (public, Godot 4.7.2) needs third-person bodies for up to 10 players, first-person arms, clothing,
accessories, props and animations, made by agents and AI generators and approved by humans who write no code. The wave
1 research (`docs/research/2026-10-02-wave-1/`) found that Godot 4.7.2 needs no addon for this, that AI generators make
good raw bodies, rigid accessories and props but no clothing that fits another body, and that raw files and unclear
licences must never reach the public game repo, because Git LFS history cannot be cleaned short of deleting a repo and
all the account's repos share 10 GiB. The engineer then chose How to Fish's characters as the direction, five fingers,
clothing in pieces, eyes and mouth as slots, animations only and first-person hands with forearms in sleeves
(`docs/pipeline.md`), and created this private repository.

What goes wrong without these rules, concretely: an agent generates on the paid Meshy plan without a yes and spends the
month's credits; a raw 30 MB GLB is committed and eats LFS quota forever; an asset of unknown licence is copied into
the public game repo; an agent pushes to `main` here, which GitHub Free cannot protect on a private repository.

## Decision

1. **Layout.** `assets/<kind>/<id>/{manifest.toml, source/, export/, report.json}`; `batches/` for generation batch
   files with the engineer's recorded yes; `contract/` for the character contract; `docs/` with `decisions/` and
   `research/`; `tools/` for the runner, Blender scripts, the headless Godot project, hooks and tests; `tools/out/`
   ignored. Review renders are never committed: the engineer sees them on private artifact pages.
2. **Runner.** `tools/run.py` (with `run.cmd` and `run.sh`), Python 3.11+ and the standard library only. Each command
   is a module in `tools/runner/commands/` found at start, so parallel tasks add commands without touching shared
   files. Tool versions and paths live in `tools/runner/pins.py`: Blender 5.2.2 LTS (portable zip, SHA-256 from the
   official file), Khronos glTF-Validator 2.0.0-dev.3.10, the game's Godot 4.7.2; each path has an environment
   override. Blender runs only as `blender -b --factory-startup --python-exit-code 1` through
   `tools/runner/blender.py`; Godot only headless. `doctor` checks the PC and prints a fix for each failure; `verify`
   (`selftest`, then `manifest-check`) is the definition-of-done gate.
3. **Hooks.** `tools/githooks/pre-push` refuses a push to `main` and a deletion of `main`, then runs `git lfs pre-push`
   (a custom `core.hooksPath` switches off the hooks Git LFS installs). `doctor` sets `core.hooksPath` to
   `tools/githooks`; the setting is repository-wide, shared by every worktree. Only the engineer merges into `main`, on
   GitHub. GitHub Pro (server-side protection) is a money option, not taken.
4. **Raw folders.** Raw generations and downloads live in `D:/prime-art-raw` (`ART_RAW_DIR`), chosen originals are
   copied to `%OneDrive%/prime-art-raw` (`ART_RAW_BACKUP_DIR`); never in git (`raw/` is ignored as a safety net).
5. **Manifest.** Every asset has a `manifest.toml` (`docs/manifest.md`) with its source (service, plan, model version,
   task ids, generation date), the raw files' paths and SHA-256, the tools, the licence and its URL,
   `public_repo_ok`, `ai_generated` and the approval (`approved_by`, `approved_at`, `approval_pr`, all or nothing).
   `manifest-check` validates every manifest in `verify`. Only CC0, CC BY with credit, owned paid output and our own
   work may be marked `public_repo_ok`; free-plan AI output is refused.
6. **Paid services, AI and approval.** Each generation batch runs only after the engineer's yes to its prompts, count
   and credits, recorded in the batch file and on the issue; the Meshy key comes from `MESHY_API_KEY` and is never
   printed, logged or committed. Prompts never name other games or characters and never upload their screenshots; no
   personal photos. An asset is approved by a PR here: the designer approves the look, the engineer the tech, the
   engineer merges. Approved assets enter the game through a game-repo PR by the game's own workflow; this repo never
   edits game code.
7. **The character contract (Proposed).** One shared humanoid skeleton with the bone names of Godot's
   `SkeletonProfileHumanoid` (generated from the pinned Godot, never typed), five-finger chains, T-pose rest, glTF Y-up,
   1 unit = 1 m, front +Z, feet at 0, about 1.75 m tall. One neutral body in v1, modelled in segments. Cosmetic slots:
   clothing pieces `top`, `bottom`, `shoes` (skinned, weights transferred from the body), `head` (a hat or a hairstyle),
   `eyes` and `mouth` (changeable like the hairstyle), `face_acc` and `back` (rigid on sockets); sets are saved presets
   of pieces. Every piece is recoloured from one shared palette. Motion is baked animations only (falls and knockdowns
   included, no ragdoll). First-person view: hands with forearms in the sleeves of the player's top, running off the
   screen edge, plus the player's shadow. Budgets, sockets and the exact slot list live in `contract/` (#4) and become
   Accepted with the first approved body; the game-side half becomes an ADR in the game repo.

## Alternatives
- **Art in the public game repo:** rejected; raw and restricted files would enter LFS history for good.
- **One runner file with every command:** rejected; four parallel tasks would conflict on it.
- **GitHub Pro for branch protection:** a money option; the local hook covers accidents, which is the goal here.
- **Raw files in LFS:** rejected; the 10 GiB account quota cannot be freed.
- **Whole-outfit sets instead of pieces; a ragdoll on falls; floating first-person hands:** each considered on #165
  and declined by the engineer.

## Consequences
- A new command is a new module plus its tests; `verify` and `selftest` pick up every task's tests.
- A worktree whose branch predates `tools/githooks/` has no pre-push hook while `core.hooksPath` points there (git
  skips a missing hook), so pushes from it neither guard `main` nor upload LFS objects until it rebases onto this
  foundation.
- Hard to revert once assets exist: the bone names, axes and slot names. Easy to revert: the generator, budgets,
  palette and pins.
