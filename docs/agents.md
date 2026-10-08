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
1. **No idle gap over 4 minutes inside an agent** (the cache rewrites).
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
   - Each role gets only the tools it needs, through the lean agent types of #44. Until #44 lands, critics, reviewers
     and verifiers are Sonnet agents with the call bound in their prompt.
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
8. **Estimate and measure.**
   - Before a launch, the manager estimates the agents, calls and % of the week.
   - A launch over about 5% of the week stops after its first phase (the engineer, prime-game#302). The manager reports
     the measured cost and asks the engineer before the next phase.
   - The 85% line in CLAUDE.md ("Decisions") still applies on top.
   - After a run, the launch report gives each agent's calls, its average and peak context, and its rewrites after
     gaps. Two ways to get them:
     - the scripts in `D:/prime-art-raw/manager/cost/`: `$PYTHON_BIN cost_ctx.py <session-id-prefix>...`, also
       `cost_tok.py`, `cost_cw.py` and `cost_bash.py`;
     - `tools/run.sh metrics` run read-only in a checkout of the game repo.
