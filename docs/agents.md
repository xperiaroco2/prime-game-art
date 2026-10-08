# Agents and workflows: the cost rules

Measured on 2026-10-08 (#51): both art tracks spent a Max week in about two days. The cache works (95.7% of input
tokens are cache reads), but agents carry too much context for too long. Each rule below names the cost it removes.
Every workflow prompt carries the rules that apply to its agents; the manager checks a script against this page before
a launch.

## Where the money went (2026-10-06 to 2026-10-08)
- **Full cache rewrites after idle gaps: ~25%.**
  - A subagent's prompt cache lives 5 minutes. After a longer gap, the next call writes the whole context again, at 12x
    the price of reading it.
  - There were 211 such rewrites of 150k+ tokens, after foreground bakes of 5-9 minutes and 600 s timeouts.
- **Long agents: 48%.** The 17 agents with 150 or more calls averaged 400-560k context per call and peaked at 890k.
- **Base context: ~16%.** The system prompt, tool definitions (including browser and docs MCP tools) and the brief come
  to a median of 59k tokens per agent, carried on every call.
- **Tool outputs: ~18%.** Bash logs (3.7M tokens), whole-file reads (2.7M), images (3.3M), Godot and Blender logs
  (2.1M), all carried on every later call.

## The rules
1. **No gap over 4 minutes between an agent's calls.** No tool call blocks over 240 s.
   - Any run that can pass 240 s goes to the background with its log in `tools/out/` or the scratchpad (see CLAUDE.md,
     "Shell").
   - The agent polls it with one short call at most every 200 s.
   - No `sleep` or `timeout` over 200 s. No Monitor or wait tool that holds the agent idle longer.
2. **Short agents.**
   - A builder step is at most about 60 calls.
   - Past about 150k context, or at the step's end, the agent writes a handoff note (done, next, files, open problems)
     and stops. A fresh agent continues from the note.
   - No agent grows past about 300k.
3. **Lean briefs and lean agent types.**
   - A brief gives the goal, the files to touch and the acceptance checks. It does not paste history; the agent reads
     only what it needs.
   - Builders get only the tools their role needs (#44).
4. **Quiet tools.**
   - A run prints a summary of 5-10 lines (pass or fail, the key numbers, the paths of the log and outputs). The full
     log goes to a file.
   - The agent greps or tails the log only when the summary shows a failure.
   - Read large files by line range.
5. **Small images, read once.**
   - Review images are downscaled contact sheets: one sheet per question, not one frame per call.
   - Full-size frames are for the review page, not for the agent.
6. **Grids instead of trial and error.**
   - When a parameter is tuned (a size, an offset, an angle), one script run renders and measures a grid of variants,
     with one table and one sheet.
   - The agent picks from the grid; it does not nudge, render and look again in a loop.
7. **Roles and models.**
   - Builders run on Opus at high effort, not xhigh. Critics, judges, reviewers and verifiers run on Sonnet.
   - A lab round keeps one Sonnet critic. From a short brief and the contact sheet, it ranks the variants and gives the
     engineer a recommendation, so he judges a ranked shortlist, not raw output.
   - Fixers get only the blocker and major findings. A revision covers only the judged winners.
8. **Estimate and measure.**
   - Before a launch: the expected agents, calls and % of the week. A launch over about 5% of the week stops after its
     first phase.
   - After a run, the launch report gives each agent's calls, average and peak context, and rewrites after gaps. Use the
     scripts in `D:/prime-art-raw/manager/cost/` (pass session id prefixes), or `tools/run.sh metrics` in the game repo.
