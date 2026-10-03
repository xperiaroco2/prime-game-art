# The trust model: the art manager merges and decides what does not need the engineer

- Date: 2026-10-03
- Status: accepted (the engineer in chat with the art manager session, 2026-10-03; recorded on #16:
  https://github.com/xperiaroco2/prime-game-art/issues/16#issuecomment-5972512323)
- Supersedes: "only the engineer merges into `main`" and "a per-batch yes for paid generation and downloads" in the
  foundation ADR (`2026-10-02-art-repo-foundation.md`) and the first `CLAUDE.md`.

## Context
Until wave 1 of stage 1, every art PR waited for the engineer to merge it. The engineer said he merged them all
without reading them, because he fully trusts the agents' work. The wait cost him attention and gave no extra check.
What he wants from the process:
- he is asked about the decisions that really need him;
- he hears what happens;
- the work does not stop for decisions the agent can judge better itself.

## Decision
1. **The art manager merges art PRs into `main`** with `gh pr merge` once a PR passes the gate:
   - fresh-context reviews leave no open blocker or major (skeptics may refute a finding, with the reason in the PR);
   - `verify` is green on the merged tree. When several PRs land together, they are trial-merged in a scratch
     worktree first.

   Nobody pushes to `main` directly; the pre-push hook still refuses it. Each merge goes into the next report on the
   plan issue.
2. **The manager decides alone**:
   - technical matters, including tools, pipeline, order and housekeeping (worktrees, branches);
   - small matters;
   - matters that are easy to change later;
   - matters where the better option does not depend on the engineer's taste.

   It records each decision with a short reason in the plan issue's report, and the engineer can overrule any of them.
3. **The manager stops and asks**, in one batched message with options and a recommendation, about:
   - look and taste (with the designer);
   - money: purchases, subscriptions, paid generation beyond the plan's credits;
   - licences outside the allowlist;
   - game-design rules;
   - large or hard-to-reverse changes:
     - the character contract once assets exist;
     - deleting raw files;
     - anything destructive to git history;
   - new dependencies or installs;
   - anything in the game repo, whose `main` stays human-merged.
4. **Workflows (agents)** for the stage's tasks start without a separate yes while the account's weekly usage stays
   below 85%. Every launch and its cost goes into the reports.
5. **The standing permissions** from the kickoff stay in force:
   - Meshy generation within the plan's credits;
   - free downloads from official sources.

   Batch files keep their `approval_ref`; the spend is reported.

## Consequences
- Fewer stops for the engineer: one batched question round per wave, mostly taste.
- The gate replaces the human merge. A bad merge is undone by a revert PR the manager opens and reports; history is
  never rewritten.
- The game repo is unchanged. Approved assets still reach it only through a game-repo PR by the game's own workflow,
  which humans merge.
- The first decisions under this model are the wave 1 questions the manager answered itself (questions 4 to 12 and 14
  of the wave 1 review page). They are listed on #16.
