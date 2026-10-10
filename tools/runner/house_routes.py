"""The design doc's routes for the house walk (art #78): `layouts/house/routes.toml` turned into capsule walks for
godot/house/walk.gd, and the walked times judged against the doc's (docs/house.md, "Routes").

Pure Python, standard library only."""
from __future__ import annotations

import math
import tomllib
from pathlib import Path

from . import house_layout as hl

FILE = "routes.toml"
SLACK_S = 10.0  # a route's walk gives up after twice the doc's time plus this


def load(folder: Path) -> dict:
    """routes.toml of the layout folder; {} when there is none."""
    path = Path(folder) / FILE
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def problems(data: dict, spec: dict) -> list[str]:
    """Each route's points: a known level for every plain point, a known flight for every stairs step."""
    out = []
    levels = {lv["level"]: lv for lv in data["levels"]}
    stairs = {st["id"] for lv in data["levels"] for st in lv.get("stairs", [])}
    for r in spec.get("routes", []):
        for i, p in enumerate(r["points"]):
            where = f"route {r['id']} point {i + 1}"
            if p[0] == "stairs":
                if p[1] not in stairs or p[2] not in ("up", "down"):
                    out.append(f"{where}: no flight {p[1]!r} {p[2]!r}")
            elif p[0] not in levels:
                out.append(f"{where}: no level {p[0]!r}")
        if r["points"][0][0] == "stairs" or r["points"][-1][0] == "stairs":
            out.append(f"route {r['id']}: starts or ends on a flight")
    return out


def walks(data: dict, request: dict, spec: dict) -> list[dict]:
    """The routes as walk.gd walks: points [x, height, z], the speed, a time limit and the doc's figures. A point with
    no floor (the yard; #81a builds its ground) gets a pad in the request, like a walk's end."""
    levels = {lv["level"]: lv["floor_y"] for lv in data["levels"]}
    by_name = {lv["level"]: lv for lv in data["levels"]}
    flights = {w["name"]: w["points"] for w in request["walks"] if w["kind"] == "stairs"}
    speed = float(spec.get("speed", 4.5))
    out = []
    for r in spec.get("routes", []):
        pts = []
        for p in r["points"]:
            if p[0] == "stairs":
                up = flights[f"{p[1]}:up"][1:-1]  # foot to top, without the walk's own approach and exit
                pts += [list(q) for q in (up if p[2] == "up" else up[::-1])]
            else:
                pts.append([float(p[1]), levels[p[0]], float(p[2])])
                floored = any(r.get("floor") and hl.inside(r["rect"], p[1], p[2]) for r in by_name[p[0]]["rooms"])
                if not floored and pts[-1] not in request["pads"]:
                    request["pads"].append(pts[-1])
        out.append({"name": f"route:{r['id']}", "kind": "route", "points": pts, "speed": speed,
                    "max_s": 2 * float(r["doc_s"]) + SLACK_S, "doc_s": float(r["doc_s"]), "doc_m": float(r["doc_m"])})
    return out


def plan_metres(points: list) -> float:
    """The waypoints' length on the floor plan (the flights by their run, without the climb)."""
    return sum(math.hypot(b[0] - a[0], b[2] - a[2]) for a, b in zip(points, points[1:]))


def judge(walk: dict, result: dict, tolerance_s: float) -> dict:
    """The walked route against the doc: `pass` when it arrives (the walk fails otherwise); `time_ok` when its time is
    within the tolerance of the doc's (reported, not failed: the doc's lengths are straight lines through doors and 6 m
    a level, and a miss is a layout question for the engineer, docs/house.md "Routes")."""
    delta = round(result["seconds"] - walk["doc_s"], 2)
    return {"doc_s": walk["doc_s"], "doc_m": walk["doc_m"], "plan_m": round(plan_metres(walk["points"]), 2),
            "delta_s": delta, "time_ok": abs(delta) <= tolerance_s, "pass": bool(result["arrived"])}
