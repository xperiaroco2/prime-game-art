# An A/B of Sonnet against Opus for the art critic

- Date: 2026-10-08
- Status: accepted for trial (#46). The A/B itself is the engineer's decision 3 of 2026-10-07 on prime-game#302
  ([comment 6038401263](https://github.com/xperiaroco2/prime-game/issues/302#issuecomment-6038401263): "A Sonnet A/B on
  code-reviewer, the publisher and the art critic, with the findings' quality checked"). The design below (pairs, the
  judge, the number of rounds and the stop rule) is the art manager's under the trust model; its numbers are
  proposals the engineer may change before the first trial round.
- Builds on: prime-game's [code reviewer A/B ADR](https://github.com/xperiaroco2/prime-game/blob/main/docs/decisions/2026-10-07-code-reviewer-model-ab.md)
  (the method, adapted here) and its [model-guard ADR](https://github.com/xperiaroco2/prime-game/blob/main/docs/decisions/2026-09-28-model-guard-no-fable-in-shared-config.md)
  (no shared script names a default model; the manager passes it per launch); `docs/agents.md` rule 7.

## Context
The art critic is the read-only agent at the end of a lab round (`tools/workflows/art-lab-round.js`): from the
builder's handoff note and one contact sheet of about 1280 px it ranks the variants and recommends one, so the
engineer judges a ranked shortlist. Until #51 such critics ran on Opus; since the cost rules of 2026-10-08 the
template runs one Sonnet critic, and nobody has checked that its remarks are as good. prime-game#535 measures the same
question for its code reviewer; this is the art half.

Art rounds differ from code reviews in two ways that shape the numbers below. They are fewer: a few lab rounds a week
in a stage, against about 25 code reviews a day. And they are costlier per trial: both extra agents (the control
critic and the judge) run on Opus and look at an image.

## Decision

### 1. The critic's model is a per-launch arg
`art-lab-round.js` takes `critic_model` (`opus`, `sonnet` or `haiku`, the shared list of prime-game's model guard) and
refuses to run without it: the shared script names no default critic model. The manager passes it on every launch.
The builder's Opus and the judge's Opus are fixed roles, not a default of the role under trial. The `art-reader`
type's `model: sonnet` is overridden per call.

### 2. Pairs on the same round
On a trial round the manager also passes `control_model: 'opus'` and `round: <n>`. A control critic then runs beside
the trial critic: the same prompt (only the ranking file's name differs), the same handoff note, the same contact
sheet, in parallel. Both critiques are returned and both go to the engineer as usual (the review page shows both
rankings), so no round is critiqued worse than an all-Opus one. Each critic now also returns its remarks: every problem
it sees, one per item, with the variant and a severity (serious when the engineer would reject the variant for it or it
decides the ranking, else minor).

### 3. A blind judge on Opus
After both critics, one read-only judge (`art-reader` on Opus, effort high, at most 30 tool calls) reads the brief, the
handoff note and the contact sheet (a full-resolution crop of one variant when a remark turns on a detail) and both
critiques inline as JSON, labelled A and B. It rules each remark valid, invalid or unsure, gives the severity it would
give, and pairs the A and B remarks that name the same problem in the same variant.
- **Blind.** The judge is told no model, no round number and no role. The trial critique is A on odd rounds and B on
  even ones, so a position bias of the judge falls on both sides equally. Its prompt forbids reading the ranking files
  and `docs/decisions` (this file states the parity rule).
- **On Opus, read-only.** `workflow-check` refuses an `art-reader` on Opus; the judge's call carries the documented
  exemption `/* opus-reader: <reason> */` (docs/agents.md), rather than a writer's tools. The critics' call carries
  `/* per-launch-model: <reason> */`, as its model is not a literal.
- **The judge saves nothing, nor does the script.** The script returns `ab_record`; the manager (or a writer step)
  saves it as `<out_dir>/ab-judge.json` and fills `cost_usd` from `tools/run.sh cost` (the agents' labels are
  `critic A`, `critic B` and `judge`; `labels` maps A and B to trial and control).
- **The human review.** When the engineer or the designer reviews a trial round anyway, the judge still runs, so all
  rounds are judged the same way; the human picks go beside the tally in the report, not into it.

### 4. The record (`ab-judge.json`, schema `art-critic-ab/1`)
```json
{
  "schema": "art-critic-ab/1",
  "round": 1,
  "labels": {"A": "trial", "B": "control"},
  "models": {"trial": "sonnet", "control": "opus", "judge": "opus"},
  "recommendations": {"A": "...", "B": "..."},
  "remarks": [
    {"id": "A1", "side": "A", "variant": "v2", "text": "the hands clip the hips", "critic_severity": "serious",
     "verdict": "valid", "severity": "serious", "reason": "visible in the front view", "judged": true}
  ],
  "pairs": [{"a": "A1", "b": "B3"}],
  "cost_usd": {"trial": 0.45, "control": 1.1, "judge": 1.5}
}
```
`verdict` is `valid`, `invalid` or `unsure`; `severity` (the judge's) is `serious` or `minor`; a remark the judge left
out comes back `unsure` with `judged: false`. Each remark is in one pair at most, `a` from A and `b` from B.
`cost_usd` is `null` until the manager fills it; any of its three keys may be missing.

### 5. Counts per side: `tools/run.sh ab-tally <judge.json>...`
Per side (trial and control): remarks, valid (and serious valid), invalid, unsure, the invalid share (invalid of all
remarks), the misses (the other side's valid remarks without a pair; and the serious ones), the $ of each critic and
of the judge (total and per round, with how many rounds had it), and the stop rule's verdict. It refuses records of
mixed model pairs, repeated round numbers or another shape. Its constants are the numbers below.

### 6. Rounds and the stop rule, fixed before the first trial round
The unit is a judged round. The trial runs on the next **six** lab rounds whose brief has at least three variants
(fewer variants give too few remarks), numbered 1 to 6 by the manager; a round without a saved judge record does not
count and its number is used again.
- **Stop early**, and keep Opus for the critic, once the trial critic missed **two more** serious valid remarks than
  the control missed of the trial's (the misses count both ways, so the noise between two critics does not fall on
  Sonnet alone).
- **After six judged rounds**, keep the trial model when it missed at most **one** more serious valid remark than the
  control, found at least **80%** as many valid remarks, and its invalid share is at most **15 points** over the
  control's; otherwise keep Opus.
- **Why six, not prime-game's ten.** A lab round ranks four to eight variants, and a critic gives a remark or more per
  variant, so one round holds several times the findings of one code review (about five, 0.37 of them blockers or
  majors). Six rounds should give some 40 remarks per side and about ten serious ones (an estimate; the before numbers
  check it), more than the four serious findings per side of prime-game's ten runs. Ten art rounds would stretch the
  trial over two or three weeks of stage work, and at about $2.5 extra per round (below) cost about $25. The two-miss
  stop and the keep bars are prime-game's, so the two halves report on one scale.
- If the six rounds hold fewer than six serious valid remarks on the control's side, the tally says little either way:
  the manager reports that beside the verdict and the engineer may extend the trial.

### 7. Cost (estimates until the before numbers)
Per trial round, on top of a round with one critic: the Opus control (about $1: up to 20 calls, the lean type's base
context of about 18k tokens, one contact sheet) and the Opus judge (about $1.5: it reads both critiques and may crop a
variant), about $2.5 a round, about $15 for six: about 0.65% of a week at prime-game's $23 per 1%. The saving if
Sonnet is kept is about half of an Opus critic per round (prime-game's audit: Sonnet's writes and output cost half of
Opus's). Both get measured: the before numbers below, then each trial round's `cost_usd`.

### 8. Where the result goes
The manager posts the `ab-tally` table and verdict, with the before numbers, on prime-game#302 for the engineer's
decision, and links it on #46. The verdict is advice. A keep makes `critic_model: 'sonnet'` the manager's launch
habit for lab rounds (still passed per launch, never a script default); a stop or a drop makes it `'opus'`.

## Not done yet
- **The before numbers.** The Opus critic's $ per round and its remarks per round, measured on the desktop that holds
  the raw folder and the past rounds' transcripts: `tools/run.sh cost` over the sessions of past lab rounds with an
  Opus critic, and their ranking notes counted. They go into #46 before the first trial round.
- **The trial rounds** themselves (on the desktop, with the raw folder), the six `ab-judge.json` records, and the
  report on prime-game#302.

## Alternatives
- **Halves (some rounds Sonnet only, some Opus only):** no pairs, so the rounds differ in content, and the Sonnet
  half goes without an Opus critique.
- **The human review as the only judge:** it does not happen on every round, and it ranks variants rather than
  ruling each remark.
- **A judge with writer tools that saves its own JSON:** more tools than a read-only role needs (rule 3); the record
  is returned and saved by the manager instead.
- **The judge on Sonnet:** it would judge its own model.
- **Count remarks without a judge:** more remarks is not better remarks.

## Consequences
- During the trial each round runs two agents more (the control and the judge) and costs about $2.5 more.
- The critic's result now carries `remarks`, which also gives every later round a count of its remarks.
- The judge is Opus judging Opus against Sonnet; the blinding and the alternating labels limit, not remove, the bias.
- `workflow-check` has two more narrow exemptions, each a comment with its reason right before the call (docs/agents.md).
