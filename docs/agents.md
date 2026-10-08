# Agents and workflows: the cost rules

Measured on 2026-10-08 (#51): both art tracks spent a Max week in about two days. The cache works (95.7% of input
tokens are cache reads), but agents carry too much context for too long. Every workflow prompt carries the rules that
apply to its agents; the manager checks a script against this page before a launch.

## Where the money went (2026-10-06 to 2026-10-08)
The drivers overlap: a long agent pays every one of the others on every call.
- **Full cache rewrites after idle gaps: ~25%.**
  - A subagent's prompt cache lives 5 minutes. After a longer gap, the next call writes the whole context again, at
    12.5x the price of reading it.
  - There were 211 such rewrites of 150k+ tokens, after foreground bakes of 5-9 minutes and 600 s timeouts.
- **Long agents: 48%.** The 17 agents with 150 or more calls averaged 400-560k context per call and peaked at 890k.
- **Base context: ~16%.** The system prompt, tool definitions (including browser and docs MCP tools) and the brief come
  to a median of 59k tokens per agent, carried on every call.
- **Tool outputs: ~18%.** Bash logs (3.7M tokens), whole-file reads (2.7M), images (3.3M), Godot and Blender logs
  (2.1M), all carried on every later call.
- **Scripts the agent wrote: ~6%.** Write, Edit and Bash inputs (3.9M tokens), also carried.

## The rules
1. **No idle gap inside an agent near the 5-minute cache life** (the cache rewrites).
   - The waiting rule in CLAUDE.md ("Shell") applies: no tool call blocks over 180 s, and a long run goes to the
     background.
   - The agent checks a background run with one short call, with gaps of at most 180 s.
   - No Monitor or wait tool may hold the agent idle longer than that.
2. **Short agents** (the long agents).
   - A builder step ends at about 60 calls (this replaces the 120 calls of #51's first levers), or earlier at the
     step's natural end.
   - The agent then writes a handoff note (done, next, files, open problems) and stops. A fresh agent continues from
     the note.
   - Workflow scripts split builds into such steps.
3. **Lean briefs and tools** (the base context).
   - A brief gives the goal, the files to touch and the acceptance checks. It does not paste history; the agent reads
     only what it needs.
   - Each role gets only the tools it needs, through the lean agent types below.
4. **Quiet runs** (the tool outputs).
   - A run writes its full output to a log and shows only its end: `<command> > <log> 2>&1; echo "exit=$?" >> <log>;
     tail -n 8 <log>`.
   - The agent greps the log only when the end shows a failure.
   - Large files are read by line range.
   - The runner keeps its own output short: `tools/runner` prints only the tail of a failing Blender run.
5. **Small images, read once** (the tool outputs).
   - Review images for agents are contact sheets of at most about 1280 px on the long side: one sheet per question, not
     one frame per call.
   - A full-resolution crop is fine when a detail needs it.
   - Full-size frames are for the review page.
6. **Grids instead of trial and error** (the long agents).
   - When a parameter is tuned (a size, an offset, an angle), one script run renders and measures a grid of variants,
     with one table and one sheet.
   - The agent picks from the grid; it does not nudge, render and look again in a loop.
7. **Roles and models.**
   - Opus at high effort, not xhigh, runs only builders that write code, IK or Blender geometry.
   - Sonnet runs critics, judges, reviewers, verifiers and research that only reads.
   - A lab round (a research iteration outside git, in `D:/prime-art-raw/research/`) keeps one Sonnet critic. From a
     short brief and the contact sheet, it ranks the variants and gives the engineer a recommendation, so he judges a
     ranked shortlist, not raw output.
   - Fixers get only the blocker and major findings. A revision covers only the judged winners.
8. **Check, estimate and measure.**
   - Before every launch, the manager runs `tools/run.sh workflow-check <script.js>...` on the workflow script; a
     refused script is fixed first (see "Checking a workflow script" below).
   - Before a launch, the manager estimates the agents, calls and % of the week.
   - A launch over about 5% of the week stops after its first phase (the engineer, prime-game#302). The manager reports
     the measured cost and asks the engineer before the next phase.
   - The 85% line in CLAUDE.md ("Decisions") still applies on top.
   - After a run, the launch report gives each agent's calls, its average and peak context, and its rewrites after
     gaps. Two ways to get them:
     - the scripts in `D:/prime-art-raw/manager/cost/`: `$PYTHON_BIN cost_ctx.py <session-id-prefix>...`, also
       `cost_tok.py`, `cost_cw.py` and `cost_bash.py`;
     - `tools/run.sh metrics` run read-only in a checkout of the game repo.

## Checking a workflow script (#56)
`workflow-check <script.js>...` refuses a script, one line per refusal (`<file>:<line>: <reason>`), when:
- its line endings are not LF (a CRLF script is refused at resume);
- it does not start with `export const meta = {...}`, or `meta` is not a pure literal (strings, numbers, `true`,
  `false`, `null`, arrays and objects of them);
- `node --check` fails on it. The check parses a module copy under `tools/out/workflow-check/`, with the body after
  `meta` wrapped in an async function (top-level `await` and `return`) on the same line, so line numbers match. It is
  skipped with a note when node is missing;
- an `agent(` call has no `agentType: 'art-reader' | 'art-writer'` in its options, unless a
  `/* general-agent: <reason> */` comment comes right before the call (or its `await`);
- an effort is `xhigh` or `max`, or an agent's `model` or `effort` is not a string literal;
- an `art-reader` call has `model: 'opus'`;
- an agent prompt has no `BOUNDS: at most N tool calls` with N <= 60, written in one string literal (N not in a
  `${...}`). The prompt's text includes the strings of the consts and functions it names;
- the script never states the 180 s wait rule (a string with "no tool call blocks over 180 s");
- it calls `Date.now()`, `Math.random()` or `new Date()` (a resumed script must replay the same way).

The options of an `agent(` call are an object literal or a const bound to one; `...SPREAD` of such a const is read too.

`tools/workflows/art-lab-round.js` is the template for a lab round (rule 7). Its args are `brief`, `lab_dir`,
`out_dir` and `steps` (1 to 4). The builder (`art-writer`, Opus, high effort) works in steps of at most 60 calls; each
step writes `handoff-step-<n>.md` in `out_dir`, and the next step reads only that note. The last step renders
`contact-sheet.png` (about 1280 px). One critic (`art-reader`, Sonnet) ranks the variants from that sheet, writes
`ranking.md` and recommends one. A lab round copies the template, edits the brief and limits, and passes
`workflow-check`. `tools/tests/test_workflow_check_scripts.py` holds a fixture per refusal
(`tools/tests/fixtures/workflows/`).

## Agent types (#44)
`.claude/agents/` holds two lean types. A general workflow agent carries every tool of the session: the desktop,
browser, docs and connector tools and the skill listing. Its first call measured 54.6k tokens on 2026-10-08 (a Sonnet
probe in this repo). A typed agent carries only its allowlist. prime-game-ui's types of the same shape start at about
18k.

| Type | Model | Tools | For |
|---|---|---|---|
| `art-reader` | Sonnet | Read, Grep, Glob, Bash, PowerShell, WebFetch, WebSearch, TaskStop | Critics, judges, reviewers, verifiers, read-only research |
| `art-writer` | Opus | The reader's tools, plus Edit and Write | Builders (code, Blender scripts, IK, geometry), fixers, publishers |

- **Every agent of an art workflow passes `agentType`:** `art-reader` or `art-writer`. The only exception is an agent
  that needs a tool neither type has; the launch report gives the reason.
- **A launch's `model` and `effort` still win per call.**
  - Builders of code, IK or geometry keep Opus at high effort.
  - A writer that only fixes docs or publishes a PR is launched with `model: 'sonnet'`.
- **Review pages are published by the manager.** Neither type has the Artifact tool; the manager adds the links to the
  PR.
- **Neither type has Agent, Skill or NotebookEdit.** When a prompt names a skill, the agent reads its `SKILL.md` by
  path.
- **Neither type sets `permissionMode`.** A subagent runs in the session's mode, so the types only narrow what a
  general agent can do.
- **Monitor is left out on purpose.** A long run is checked with short calls (rule 1).
- **A session sees a new `.claude/agents/` folder only after a restart.** It sees a new file in an existing folder
  within seconds.
- `tools/tests/test_agents_types.py` checks the files.
