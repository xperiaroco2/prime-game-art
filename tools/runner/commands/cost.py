"""`cost [--since ISO] [--session PREFIX...] [--project DIR] [--json FILE]`: what each agent of this checkout cost (#55).

Reads the Claude Code transcripts of this checkout (docs/agents.md, rule 8): the project folder
`~/.claude/projects/<key>/`, where <key> is the main checkout's path with every character other than a letter or digit
replaced by "-" (C:\\prime-game-art -> C--prime-game-art, D:\\prime-game-art -> D--prime-game-art). A session started
with its cwd in a worktree at `<main>-wt/<name>` has its own folder, `<key>-wt-<name>` (C--prime-game-art-wt-60): those
are read too, and an API call found in two folders counts once (per session, agent and message id). CLAUDE_CONFIG_DIR
moves `~/.claude`; --project names one folder outright.

In that folder, `<session>.jsonl` is a main session and `<session>/subagents/**/agent-<id>.jsonl` its subagents, each
with `agent-<id>.meta.json` (agentType, description). An assistant line carries `message.id`, `message.model` and
`message.usage`; one API call writes several lines with the same id, so usage is taken per id (the largest value of each
field). Claude Code's own `<synthetic>` lines are no API calls.

One row per agent (the main session is an agent too):
- label: the meta's description, else its agentType; a main session's custom title, else "main";
- model, and calls (API calls);
- context: a call's prompt, input + cache writes + cache reads; the first call's, the average and the peak;
- rewrites: calls that wrote REWRITE_MIN or more cache tokens after a gap since the previous call longer than those
  tokens' cache life (the prompt cache had expired, so the whole context was written again). The usage tells 5-minute
  from 1-hour writes (`cache_creation.ephemeral_1h_input_tokens`): a 1-hour write counts only after a gap over
  CACHE_TTL_1H, since a 1-hour cache outlives a shorter one;
- list $: the calls' tokens at the API list price (PRICES).

Then a total, and the whole as JSON in tools/out/cost/cost.json. Only reads transcripts; writes only that JSON.
The approach and the prices follow prime-game's tools/runner/metrics.py (copied, not imported: two repos).
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .. import common

NAME = "cost"
HELP = "per-agent calls, context, cache rewrites after idle gaps and list $ from this checkout's Claude Code transcripts"

# USD per million tokens at the API list price: input, 5-minute cache write, 1-hour cache write, cache read, output.
# Source: platform.claude.com/docs/en/about-claude/pricing, read 2026-10-02 (copied from prime-game's metrics.py). A
# model missing here is weighed at the first row's prices and named in the output.
PRICES = {
    "claude-opus-5-5": (4.0, 5.0, 8.0, 0.20, 20.0),
    "claude-sonnet-5-5": (2.0, 2.5, 4.0, 0.20, 10.0),
    "claude-haiku-4-5": (1.0, 1.25, 2.0, 0.10, 5.0),
}
CACHE_TTL = 300  # a prompt cache's life, in seconds: a longer gap before a call means its context is written again
CACHE_TTL_1H = 3600  # the life of a 1-hour cache write (main sessions use them)
REWRITE_MIN = 50_000  # cache-write tokens of one call that count as a rewrite after such a gap
DEFAULT_JSON = common.OUT / "cost" / "cost.json"
SYNTHETIC = "<synthetic>"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--since", metavar="ISO", help="only API calls at or after this time (UTC unless it has a zone)")
    parser.add_argument("--session", nargs="+", default=[], metavar="PREFIX", help="only sessions whose id starts so")
    parser.add_argument("--project", type=Path, metavar="DIR", help="the transcript folder (default: derived)")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON, metavar="FILE", help="where to write the JSON")


def run(args: argparse.Namespace) -> int:
    candidates = [args.project] if args.project else project_folders(main_checkout())
    folders = [f for f in candidates if f.is_dir()]
    if not folders:
        raise common.Failure(f"no transcript folder at {candidates[0]}; name it with --project")
    since = parse_time(args.since) if args.since else None
    report = collect(folders, args.session, since)
    if not report["agents"]:
        where = ", ".join(str(f) for f in folders)
        common.say(f"cost: no API calls in {where}" + (f" since {args.since}" if args.since else ""))
    for line in render(report):
        common.say(line)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    common.say(f"cost: wrote {args.json}")
    return 0


# --- where the transcripts are ------------------------------------------------------------------------------------


def main_checkout(root: Path = common.ROOT) -> Path:
    """The main checkout: the parent of git's common dir, the same from every worktree; else this checkout."""
    try:
        res = common.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], timeout=30, cwd=root)
    except (common.Failure, OSError):
        return root
    lines = [line for line in res.stdout.splitlines() if line.strip()]
    if res.returncode == 0 and lines:
        return Path(lines[-1].strip()).parent
    return root


def project_key(checkout: Path | str) -> str:
    """Claude Code's folder name for a working directory: C:\\prime-game-art -> C--prime-game-art."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(checkout))


def claude_home() -> Path:
    configured = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return Path(configured) if configured else Path.home() / ".claude"


def project_folder(checkout: Path, home: Path | None = None) -> Path:
    return (home or claude_home()) / "projects" / project_key(checkout)


def project_folders(checkout: Path, home: Path | None = None) -> list[Path]:
    """The main checkout's transcript folder, then its worktrees' existing `<key>-wt-<name>` folders, each once."""
    main = project_folder(checkout, home)
    worktrees = sorted(p for p in main.parent.glob(f"{main.name}-wt-*") if p.is_dir()) if main.parent.is_dir() else []
    return list(dict.fromkeys([main, *worktrees]))


# --- reading ------------------------------------------------------------------------------------------------------


def parse_time(text: str) -> float:
    """ISO 8601 ('2026-10-08T11:00:00Z', '2026-10-08') as epoch seconds; a time without a zone is UTC."""
    try:
        moment = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise common.Failure(f"not an ISO 8601 time: {text!r} (for example 2026-10-08T11:00:00Z)") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def iso(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_transcript(path: Path) -> tuple[list[dict], str | None]:
    """The transcript's API calls in order (one per message id, with its first and last line's time) and its custom
    title, if any. Unreadable lines are skipped."""
    calls: dict[str, dict] = {}
    title = None
    with path.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            if d.get("type") == "custom-title" and d.get("customTitle"):
                title = str(d["customTitle"])
            m = d.get("message")
            if d.get("type") != "assistant" or not isinstance(m, dict) or m.get("model") == SYNTHETIC:
                continue
            try:
                t = parse_time(str(d.get("timestamp")))
            except common.Failure:
                continue
            mid = str(m.get("id") or d.get("requestId") or d.get("uuid"))
            u = m.get("usage") if isinstance(m.get("usage"), dict) else {}
            call = calls.get(mid)
            if call is None:
                call = calls[mid] = {"id": mid, "model": m.get("model"), "t0": t, "t1": t, "input": 0, "write": 0,
                                     "write_1h": 0, "read": 0, "output": 0}
            call["t0"], call["t1"] = min(call["t0"], t), max(call["t1"], t)
            for key, field in (("input", "input_tokens"), ("write", "cache_creation_input_tokens"),
                               ("read", "cache_read_input_tokens"), ("output", "output_tokens")):
                call[key] = max(call[key], int(u.get(field) or 0))
            cache = u.get("cache_creation")
            if isinstance(cache, dict):
                call["write_1h"] = max(call["write_1h"], int(cache.get("ephemeral_1h_input_tokens") or 0))
    return sorted(calls.values(), key=lambda c: c["t0"]), title


def read_meta(agent_file: Path) -> dict:
    meta = agent_file.with_name(agent_file.name.removesuffix(".jsonl") + ".meta.json")
    try:
        value = json.loads(meta.read_text(encoding="utf-8")) if meta.is_file() else {}
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


# --- weighing -----------------------------------------------------------------------------------------------------


def price_of(model: str | None) -> tuple[tuple[float, ...], bool]:
    """(prices, known). Model IDs may carry a date suffix (claude-haiku-4-5-20251001)."""
    for name, price in PRICES.items():
        if (model or "").startswith(name):
            return price, True
    return next(iter(PRICES.values())), False


def usd_of(call: dict) -> float:
    """One API call's tokens at its model's list price."""
    price, _known = price_of(call["model"])
    one_hour = min(call["write_1h"], call["write"])
    return (call["input"] * price[0] + (call["write"] - one_hour) * price[1] + one_hour * price[2]
            + call["read"] * price[3] + call["output"] * price[4]) / 1e6


def expired_write(call: dict, gap: float) -> int:
    """The cache tokens a call wrote because its cache had expired after a gap of `gap` seconds: its 5-minute writes
    after a gap over CACHE_TTL, all its writes after one over CACHE_TTL_1H."""
    if gap > CACHE_TTL_1H:
        return call["write"]
    if gap > CACHE_TTL:
        return call["write"] - min(call["write_1h"], call["write"])
    return 0


def context(call: dict) -> int:
    """The call's prompt: input, cache writes and cache reads."""
    return call["input"] + call["write"] + call["read"]


def agent_row(calls: list[dict], since: float | None = None) -> dict:
    """One agent's figures over its calls at or after `since`; a gap is measured from the previous call, in the
    window or not."""
    kept, rewrites, rewrite_tokens = [], 0, 0
    for i, call in enumerate(calls):
        if since is not None and call["t0"] < since:
            continue
        kept.append(call)
        written = expired_write(call, call["t0"] - calls[i - 1]["t1"]) if i else 0
        if written >= REWRITE_MIN:
            rewrites += 1
            rewrite_tokens += written
    contexts = [context(c) for c in kept]
    models = Counter(str(c["model"]) for c in kept)
    return {
        "model": models.most_common(1)[0][0] if models else None,
        "calls": len(kept),
        "first_context": contexts[0] if contexts else 0,
        "avg_context": round(sum(contexts) / len(contexts)) if contexts else 0,
        "peak_context": max(contexts, default=0),
        "rewrites": rewrites,
        "rewrite_tokens": rewrite_tokens,
        "usd": round(sum(usd_of(c) for c in kept), 6),
        "start": iso(kept[0]["t0"]) if kept else None,
        "end": iso(kept[-1]["t1"]) if kept else None,
        "unpriced": sorted({str(c["model"]) for c in kept if not price_of(c["model"])[1]}),
    }


TOKEN_KEYS = ("input", "write", "write_1h", "read", "output")


def merge_calls(into: dict[str, dict], calls: list[dict]) -> None:
    """Adds a transcript's calls to `into` (message id -> call); a call seen before keeps its widest times and the
    largest value of each token field."""
    for call in calls:
        have = into.get(call["id"])
        if have is None:
            into[call["id"]] = dict(call)
            continue
        have["t0"], have["t1"] = min(have["t0"], call["t0"]), max(have["t1"], call["t1"])
        for key in TOKEN_KEYS:
            have[key] = max(have[key], call[key])


def collect(folders: list[Path] | Path, prefixes: list[str], since: float | None) -> dict:
    """Every agent of the folders' sessions (filtered by id prefix) with calls in the window, and the total. A session
    or subagent found in several folders is one agent, its calls merged by message id."""
    folders = [folders] if isinstance(folders, Path) else list(dict.fromkeys(folders))
    found: dict[tuple[str, str], dict] = {}  # (session, agent) -> label, type and calls by message id

    def add(sid: str, agent: str, label: str, kind: str, calls: list[dict]) -> None:
        entry = found.setdefault((sid, agent), {"label": label, "type": kind, "calls": {}})
        if entry["label"] in ("main", "?") and label not in ("main", "?"):
            entry["label"] = label
        merge_calls(entry["calls"], calls)

    for folder in folders:
        names = {p.stem for p in folder.glob("*.jsonl")} | {
            p.name for p in folder.iterdir() if p.is_dir() and (p / "subagents").is_dir()
        }
        for sid in sorted(names):
            if prefixes and not any(sid.startswith(p) for p in prefixes):
                continue
            main = folder / f"{sid}.jsonl"
            if main.is_file():
                calls, title = read_transcript(main)
                add(sid, "main", title or "main", "main", calls)
            subagents = folder / sid / "subagents"
            for path in sorted(subagents.rglob("agent-*.jsonl")) if subagents.is_dir() else []:
                meta = read_meta(path)
                kind = str(meta.get("agentType") or "?")
                calls, _title = read_transcript(path)
                add(sid, path.stem.removeprefix("agent-"), str(meta.get("description") or kind), kind, calls)
    agents = [
        {"session": sid, "agent": agent, "label": e["label"], "type": e["type"],
         **agent_row(sorted(e["calls"].values(), key=lambda c: c["t0"]), since)}
        for (sid, agent), e in found.items()
    ]
    agents = [a for a in agents if a["calls"]]
    agents.sort(key=lambda a: (a["session"], a["start"] or ""))
    total = {
        "agents": len(agents),
        "calls": sum(a["calls"] for a in agents),
        "rewrites": sum(a["rewrites"] for a in agents),
        "rewrite_tokens": sum(a["rewrite_tokens"] for a in agents),
        "usd": round(sum(a["usd"] for a in agents), 6),
        "unpriced": sorted({m for a in agents for m in a["unpriced"]}),
    }
    return {"folders": [str(f) for f in folders], "since": iso(since), "agents": agents, "total": total}


# --- printing -----------------------------------------------------------------------------------------------------


def tokens(n: float) -> str:
    return f"{n / 1e6:.2f}M" if n >= 1e6 else f"{n / 1e3:.0f}k"


def money(v: float) -> str:
    return f"${v:,.0f}" if v >= 10 else f"${v:.2f}"


def render(report: dict) -> list[str]:
    head = ("session", "label", "model", "calls", "first", "avg", "peak", "rewrites", "list $")
    rows = [
        (a["session"][:8], a["label"][:40], str(a["model"]).removeprefix("claude-"), str(a["calls"]),
         tokens(a["first_context"]), tokens(a["avg_context"]), tokens(a["peak_context"]), str(a["rewrites"]),
         money(a["usd"]))
        for a in report["agents"]
    ]
    widths = [max([len(head[i]), *(len(r[i]) for r in rows)]) for i in range(len(head))]
    right = {3, 4, 5, 6, 7, 8}

    def line(cells: tuple[str, ...]) -> str:
        return "  ".join(c.rjust(w) if i in right else c.ljust(w) for i, (c, w) in enumerate(zip(cells, widths)))

    t = report["total"]
    out = [line(head), *(line(r) for r in rows)] if rows else []
    out.append(
        f"total: {t['agents']} agents, {t['calls']} calls, {t['rewrites']} rewrites after gaps over {CACHE_TTL} s "
        f"({tokens(t['rewrite_tokens'])} tokens), {money(t['usd'])} at list prices"
    )
    if t["unpriced"]:
        out.append(f"cost: models without a price, weighed as {next(iter(PRICES))}: {', '.join(t['unpriced'])}")
    return out
