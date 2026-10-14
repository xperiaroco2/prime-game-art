# verify runs what a change needs; the full suite runs at night

- Status: accepted (the policy: the engineer, 2026-10-14, chat; the mechanism: the art manager, #159)
- Issue: #159

## Context

`verify` ran `selftest` (unittest discovery over `tools/tests`: 1,248 tests in 108 files, serially in one process),
then `manifest-check`, and held the heavy-run lock for the whole run. It took 10-18 minutes, and every task ran it two
or three times (the builder, the fixer, the manager before a merge). Most of that time is the character pipeline's
Blender and Godot tests (animations, retargeting, faces, assembly, export), which a House room never touches, and the
lock kept every other Blender or Godot job waiting meanwhile.

Measured on the desktop (2026-10-14, each file alone and serially, `tools/tests/timings.json`): 717 s in all; the 20
heavy files 465 s, the 88 fast files 251 s, of which `test_kit_spec.py` alone is 109 s and `test_house_clutter.py`
59 s.

## Decision

1. **Two classes of test file, read from the file.** A test file is *heavy* when it, or a `tools/tests/_*.py` helper
   it imports, looks the Blender or Godot binary up (the skip condition's `tool_path(pins.BLENDER_ENV, ...)`,
   `have(pins.GODOT_ENV, ...)`, `tool_path("GODOT_BIN", ...)`) or starts one (`blender_bin(`, `godot_bin(`,
   `blender.run_script(`); every other file is *fast* (`_testrun.HEAVY_MARKERS`). No hand-kept list. Each run checks
   the split: `common.run` touches the file named by `ART_HEAVY_PROBE` when it starts Blender or Godot, and a fast
   file that does is red. `test_verify_affected.py` checks the split against `timings.json`'s measured starts.
2. **One process per file.** Fast files run in parallel (half the CPUs, slowest first by `timings.json`), then the
   heavy files one at a time inside the heavy-run lock, held only for that part. A red fast file stops the run before
   the heavy part; the red files' output is printed at the end with the slowest files and the totals. A test is
   never skipped that would have run; a heavy file is only not selected.
3. **`verify` = the affected run** (the task gate): every fast file, the heavy files the change needs, then
   `manifest-check`. The change is `git diff --name-only <base>...HEAD` plus the staged, unstaged and untracked files
   (`--base`, default `origin/main`). `tools/tests/areas.toml` maps paths to heavy files:
   - a changed heavy test file runs itself;
   - a path in an area runs that area's heavy test files (the `tests` patterns);
   - a shared path (the runner core `common.py`, `cli.py`, `pins.py`, `blender.py`, `tools/run.*`, the test
     helpers and fixtures, the test runner itself, `areas.toml`, `godot/project.godot`, `godot/addons`, `godot/lib`)
     runs the full suite;
   - a light path (docs, manifests, source records, workflows) needs no heavy file;
   - a path in none of them runs the full suite. `test_verify_affected.py` fails while any tracked file is unmapped,
     a heavy test file is in no area's `tests`, or a pattern matches nothing, so the map cannot drift silently.

   `verify` prints the heavy files it chose and the first reason for each.
4. **`verify --full` = the night run**: every test file (parallel fast, then heavy) and `manifest-check`. The
   procedure is the runner command `nightly`: it fetches `origin/main`, creates or moves the dedicated worktree
   `<main checkout>-wt/nightly` (`D:/prime-game-art-wt/nightly`; never the main checkout or a task worktree, and it
   refuses local edits there), runs `verify --full` in it with the log in `tools/out/nightly/<date>.log` and appends a
   one-line summary (green or red, minutes, the red step and files) to `tools/out/nightly/summary.log`. A red run
   opens the issue "nightly: verify --full is red on main" (or comments on it while it is open) with the red files and
   the log's tail; it becomes the morning's fix task. A green run files nothing. Who triggers it: the art manager,
   once a night, in the background (`tools/run.sh nightly > tools/out/nightly/run.log 2>&1`); a scheduled trigger
   may call the same command later. `selftest` keeps its meaning (every test file, `-p` narrows it) on the same
   runner; `--write-timings` refreshes `timings.json`.
5. **No GitHub CI** (the engineer: "if it runs locally, why GitHub"): the heavy tests need Blender, Godot and the raw
   folder, which only the desktop has.

## Consequences

- Measured on this branch (#159): `verify --full` 592 s, green (the fast part 8 files at a time, about 120 s; the
  heavy part about 470 s), against 10-18 minutes before. `verify` against `origin/main` with this change's own diff
  selects the full suite (it changes `common.py`); `verify --base HEAD` with docs-only changes: 117 s, green (no heavy
  file). A House change (`layouts/`, `props/`, `tools/runner/house_*.py`) selects only `test_house_export.py`
  (14 s): about 2.5 minutes. The fast part's floor is `test_kit_spec.py` (about 115 s).
- A character-pipeline regression that a House task cannot cause is found by the night run, not by the task gate; a
  regression the map misses is found the next morning at the latest.
- New source paths need an entry in `areas.toml` (the test names them); a new heavy test file is found by its
  text and must match an area's `tests` pattern (the test names it).
