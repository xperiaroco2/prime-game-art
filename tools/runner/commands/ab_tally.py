"""`ab-tally <judge.json>...`: the counts and the stop rule of the art critic's Sonnet/Opus A/B (#46).

Each file is one judged lab round: the `ab_record` that `tools/workflows/art-lab-round.js` returns with a control
critic, saved by the manager as `<out_dir>/ab-judge.json`, its `cost_usd` filled from `tools/run.sh cost`. Its shape
and the stop rule are in docs/decisions/2026-10-08-art-critic-model-ab.md. The command only reads; the verdict is
advice for the engineer (prime-game#302).

Per side (the trial critic and the Opus control): remarks, valid (and serious valid), invalid, unsure, the invalid
share, the valid remarks of the other side it has no pair for (its misses, and the serious ones), and the $ when the
records give it; then the stop rule: continue, stop (keep the control), or after AB_ROUNDS rounds keep one model.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

from .. import common

NAME = "ab-tally"
HELP = "count the art critic A/B's judged rounds (ab-judge.json files) per side and evaluate the ADR's stop rule"

SCHEMA = "art-critic-ab/1"
VERDICTS = ("valid", "invalid", "unsure")
SEVERITIES = ("serious", "minor")
ROLES = ("trial", "control")
LABELS = ("A", "B")

# The stop rule (docs/decisions/2026-10-08-art-critic-model-ab.md), fixed before the first trial round.
AB_ROUNDS = 6  # judged rounds before the final verdict
AB_STOP_EXTRA_MISSES = 2  # stop early once the trial missed this many more serious valid remarks than the control
AB_KEEP_EXTRA_MISSES = 1  # after AB_ROUNDS: keep the trial with at most this many more serious misses,
AB_VALID_RATIO = 0.8  # at least this share of the control's valid remarks,
AB_INVALID_POINTS = 15.0  # and an invalid share at most this many points over the control's


@dataclass
class Side:
    model: str
    remarks: int = 0
    valid: int = 0
    serious_valid: int = 0
    invalid: int = 0
    unsure: int = 0
    unjudged: int = 0
    missed: int = 0  # valid remarks of the other side without a pair on this side
    missed_serious: int = 0
    costs: list[float] = field(default_factory=list)

    @property
    def invalid_share(self) -> float:
        """Invalid remarks in percent of all remarks (0 without remarks)."""
        return 100.0 * self.invalid / self.remarks if self.remarks else 0.0


@dataclass
class Tally:
    rounds: list[int]
    sides: dict[str, Side]
    judge_model: str
    judge_costs: list[float] = field(default_factory=list)

    @property
    def extra_misses(self) -> int:
        """The trial's serious misses minus the control's."""
        return self.sides["trial"].missed_serious - self.sides["control"].missed_serious


def load(path: Path) -> dict:
    """One judged round, checked; common.Failure names the file and what is wrong."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise common.Failure(f"ab-tally: cannot read {path}: {error}") from error
    try:
        check(record)
    except ValueError as error:
        raise common.Failure(f"ab-tally: {path}: {error}") from error
    return record


def check(record: dict) -> None:
    """Raises ValueError when the record does not have the ADR's shape."""
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise ValueError(f"not an A/B record (schema must be {SCHEMA!r})")
    if not isinstance(record.get("round"), int) or isinstance(record["round"], bool) or record["round"] < 1:
        raise ValueError("round must be an integer from 1")
    labels = record.get("labels")
    if not isinstance(labels, dict) or set(labels) != set(LABELS) or sorted(labels.values()) != sorted(ROLES):
        raise ValueError("labels must map A and B to trial and control, one each")
    models = record.get("models")
    if not isinstance(models, dict) or not all(isinstance(models.get(k), str) for k in (*ROLES, "judge")):
        raise ValueError("models must name the trial, control and judge models")
    remarks = record.get("remarks")
    if not isinstance(remarks, list):
        raise ValueError("remarks must be a list")
    ids: dict[str, str] = {}
    for remark in remarks:
        if not isinstance(remark, dict) or not isinstance(remark.get("id"), str) or remark["id"] in ids:
            raise ValueError(f"every remark needs a unique string id: {remark!r}")
        if remark.get("side") not in LABELS or remark.get("verdict") not in VERDICTS \
                or remark.get("severity") not in SEVERITIES:
            raise ValueError(f"remark {remark['id']}: side A|B, verdict {'|'.join(VERDICTS)} and severity "
                             f"{'|'.join(SEVERITIES)} are required")
        ids[remark["id"]] = remark["side"]
    pairs = record.get("pairs")
    if not isinstance(pairs, list):
        raise ValueError("pairs must be a list")
    seen: set[str] = set()
    for pair in pairs:
        a, b = (pair.get("a"), pair.get("b")) if isinstance(pair, dict) else (None, None)
        if ids.get(a) != "A" or ids.get(b) != "B" or a in seen or b in seen:
            raise ValueError(f"pair {pair!r}: a must be an A remark and b a B remark, each in one pair at most")
        seen.update((a, b))
    cost = record.get("cost_usd")
    if cost is not None and (not isinstance(cost, dict) or any(
            k not in (*ROLES, "judge") or not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0
            for k, v in cost.items())):
        raise ValueError("cost_usd must be null or an object of trial, control and judge dollars")


def tally(records: list[dict]) -> Tally:
    """The totals of judged rounds of one pair of models."""
    if not records:
        raise common.Failure("ab-tally: no judged rounds")
    pairs = {(r["models"]["trial"], r["models"]["control"]) for r in records}
    if len(pairs) > 1:
        raise common.Failure(f"ab-tally: the rounds mix pairs of models {sorted(pairs)}; tally one pair at a time")
    rounds = [r["round"] for r in records]
    if len(set(rounds)) < len(rounds):
        raise common.Failure(f"ab-tally: a round number repeats: {sorted(rounds)}")
    trial_model, control_model = pairs.pop()
    result = Tally(sorted(rounds), {"trial": Side(trial_model), "control": Side(control_model)},
                   records[0]["models"]["judge"])
    for record in records:
        role_of = record["labels"]
        paired = {p["a"] for p in record["pairs"]} | {p["b"] for p in record["pairs"]}
        for remark in record["remarks"]:
            side = result.sides[role_of[remark["side"]]]
            other = result.sides["control" if role_of[remark["side"]] == "trial" else "trial"]
            side.remarks += 1
            side.unjudged += remark.get("judged") is False
            if remark["verdict"] == "valid":
                side.valid += 1
                side.serious_valid += remark["severity"] == "serious"
                if remark["id"] not in paired:
                    other.missed += 1
                    other.missed_serious += remark["severity"] == "serious"
            elif remark["verdict"] == "invalid":
                side.invalid += 1
            else:
                side.unsure += 1
        cost = record.get("cost_usd") or {}
        for role in ROLES:
            if role in cost:
                result.sides[role].costs.append(float(cost[role]))
        if "judge" in cost:
            result.judge_costs.append(float(cost["judge"]))
    return result


def verdict(t: Tally) -> str:
    """The stop rule's advice."""
    trial, control = t.sides["trial"], t.sides["control"]
    n = len(t.rounds)
    if t.extra_misses >= AB_STOP_EXTRA_MISSES:
        return (f"stop: keep {control.model} (after {n} round(s) the {trial.model} critic missed {t.extra_misses} more "
                f"serious valid remarks than the {control.model} control; the limit is {AB_STOP_EXTRA_MISSES})")
    if n < AB_ROUNDS:
        return f"continue ({n} of {AB_ROUNDS} rounds)"
    reasons = []
    if t.extra_misses > AB_KEEP_EXTRA_MISSES:
        reasons.append(f"{t.extra_misses} more serious misses (at most {AB_KEEP_EXTRA_MISSES})")
    if trial.valid < AB_VALID_RATIO * control.valid:
        reasons.append(f"{trial.valid} valid remarks against {control.valid} (at least {AB_VALID_RATIO:.0%})")
    if trial.invalid_share > control.invalid_share + AB_INVALID_POINTS:
        reasons.append(f"invalid share {trial.invalid_share:.1f}% against {control.invalid_share:.1f}% "
                       f"(at most {AB_INVALID_POINTS:.0f} points over)")
    if reasons:
        return f"after {n} rounds: keep {control.model} ({'; '.join(reasons)})"
    return f"after {n} rounds: keep {trial.model} (every bar of the stop rule met)"


def dollars(costs: list[float], rounds: int) -> str:
    if not costs:
        return "-"
    note = "" if len(costs) == rounds else f" ({len(costs)} of {rounds} rounds)"
    return f"${sum(costs):.2f}, ${sum(costs) / len(costs):.2f}/round{note}"


def report(t: Tally) -> list[str]:
    n = len(t.rounds)
    lines = [f"ab-tally: {n} judged round(s) {t.rounds}: trial {t.sides['trial'].model} against control "
             f"{t.sides['control'].model}, judge {t.judge_model}"]
    head = f"{'side':8} {'model':7} {'remarks':>7} {'valid':>5} {'serious':>7} {'invalid':>7} {'unsure':>6} " \
           f"{'invalid%':>8} {'missed':>6} {'missed serious':>14}  $"
    lines.append(head)
    for role in ROLES:
        s = t.sides[role]
        lines.append(f"{role:8} {s.model:7} {s.remarks:>7} {s.valid:>5} {s.serious_valid:>7} {s.invalid:>7} "
                     f"{s.unsure:>6} {s.invalid_share:>7.1f}% {s.missed:>6} {s.missed_serious:>14}  "
                     f"{dollars(s.costs, n)}")
    lines.append(f"{'judge':8} {t.judge_model:7} ".ljust(len(head) - 1) + dollars(t.judge_costs, n))
    unjudged = sum(s.unjudged for s in t.sides.values())
    if unjudged:
        lines.append(f"ab-tally: {unjudged} remark(s) had no verdict from the judge and count as unsure")
    lines.append("missed: the other side's valid remarks without a pair on this side")
    lines.append(f"verdict: {verdict(t)}")
    return lines


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("records", nargs="+", type=Path, metavar="judge.json",
                        help="the judged rounds (each a saved ab_record of art-lab-round.js)")


def run(args: argparse.Namespace) -> int:
    for line in report(tally([load(path) for path in args.records])):
        common.say(line)
    return 0
