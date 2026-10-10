"""Helpers of `kit` (docs/kit.md): the kit spec's pure checks, the GLB checks, the Godot assertions and the piece
table. Standard library only; the geometry is tools/blender/kit_geom.py (imported from there, it needs no Blender)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from .. import common

SPEC = common.ROOT / "kits" / "house.json"
SCRIPT = "kit_build.py"
CHECK = "res://check/kit.gd"
PROOF = "res://kit/proof.gd"
BOUNDS_TOLERANCE_M = 0.002  # Godot's imported bounds equal the spec's geometry
RAY_LEAD_M = 0.5  # every collider is probed by a ray that starts this far outside it
MAN = ("clay-42a", "export", "m1", "m1.glb")  # the clay man for scale in the proof (<raw>/...); a capsule without it
# The proof's line-up (art #86): every piece in one group by its kind; the view pitch in degrees (8 front, 90 from
# above; the roofs at 50 so the slopes show). A kind in no group goes to "other".
LINEUP_GROUPS = (
    ("walls", ("wall",), 8.0),
    ("corners, ends, pillars, chimney, trim", ("corner", "pillar", "chimney", "trim"), 8.0),
    ("floors", ("floor",), 90.0),
    ("roofs", ("roof",), 50.0),
    ("dormer", ("dormer",), 12.0),
    ("glass", ("glass",), 8.0),
    ("stairs, ladder, railings", ("stairs", "ladder", "railing"), 8.0),
    ("fences, gates, garage, porch", ("fence", "gate", "garage", "porch"), 8.0),
    ("gazebo", ("gazebo",), 30.0),
)


def geom():
    """tools/blender/kit_geom.py as a module (it is plain Python)."""
    name = "kit_geom"
    if name in sys.modules:
        return sys.modules[name]
    path = common.ROOT / "tools" / "blender" / "kit_geom.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def lineup_groups(pieces: list[dict[str, Any]]) -> list[list]:
    """LINEUP_GROUPS filled with the pieces' ids in spec order; empty groups dropped, unknown kinds in "other"."""
    known = {k for _, kinds, _ in LINEUP_GROUPS for k in kinds}
    groups = [[title, [p["id"] for p in pieces if p["kind"] in kinds], pitch] for title, kinds, pitch in LINEUP_GROUPS]
    groups.append(["other", [p["id"] for p in pieces if p["kind"] not in known], 8.0])
    return [g for g in groups if g[1]]


def default_out(spec: dict[str, Any]) -> Path:
    return common.raw_dir() / "kits" / spec["kit"] / f"v{spec['version']}"


def rays(described: dict[str, Any]) -> list[list[list[float]]]:
    """One ray per collider: from outside it, along its thinnest axis, to the centroid of its points (inside every
    convex hull). A closed collider that Godot built blocks it."""
    out = []
    for c in described["colliders"]:
        pts = c["points"]
        centre = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        axis = min(range(3), key=lambda i: hi[i] - lo[i])
        start = list(centre)
        start[axis] = lo[axis] - RAY_LEAD_M
        out.append([[round(v, 5) for v in start], [round(v, 5) for v in centre]])
    return out


def check_glb(gltf: dict[str, Any], described: dict[str, Any], max_materials: int) -> list[str]:
    """The exported file holds the piece: its mesh nodes with UV2 (TEXCOORD_1) and vertex colours, one node per
    collider, at most the kit's materials, each named `<name>-vcol`."""
    pid = described["id"]
    problems = []
    nodes = {n.get("name"): n for n in gltf.get("nodes", [])}
    for m in described["meshes"]:
        node = nodes.get(m["name"])
        if node is None or "mesh" not in node:
            problems.append(f"{pid}: no mesh node {m['name']}")
            continue
        for prim in gltf["meshes"][node["mesh"]]["primitives"]:
            missing = [a for a in ("TEXCOORD_0", "TEXCOORD_1", "COLOR_0", "NORMAL") if a not in prim["attributes"]]
            if missing:
                problems.append(f"{pid}: {m['name']} lacks {', '.join(missing)}")
    for c in described["colliders"]:
        if c["name"] not in nodes:
            problems.append(f"{pid}: no collider node {c['name']}")
    if len(gltf.get("materials", [])) > max_materials:
        problems.append(f"{pid}: {len(gltf['materials'])} materials, the kit has {max_materials}")
    for mat in gltf.get("materials", []):
        if not str(mat.get("name", "")).endswith("-vcol"):
            problems.append(f"{pid}: material {mat.get('name')} lacks the -vcol suffix (sRGB vertex paint in Godot)")
    return problems


def _close(a: list[float], b: list[float], tol: float) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def evaluate(dump: dict[str, Any], described: dict[str, Any]) -> list[str]:
    """Godot's import of one piece against its spec geometry."""
    pid = described["id"]
    if "error" in dump:
        return [f"{pid}: {dump['error']}"]
    problems = []
    names = {m["name"] for m in dump["meshes"]}
    for m in described["meshes"]:
        if m["name"] not in names:
            problems.append(f"{pid}: Godot has no mesh {m['name']}")
    tris = sum(m["triangles"] for m in dump["meshes"])
    if tris != described["triangles"]:
        problems.append(f"{pid}: Godot has {tris} triangles, the spec {described['triangles']}")
    for m in dump["meshes"]:
        for s in m["surfaces"]:
            if not s["uv2"]:
                problems.append(f"{pid}: {m['name']} surface {s['material']} has no UV2")
            if not s["color"] or not s["vertex_colour_albedo"] or not s.get("vertex_colour_srgb"):
                problems.append(f"{pid}: {m['name']} surface {s['material']} does not paint with its sRGB vertex colours")
    if len(dump["bodies"]) != len(described["colliders"]):
        problems.append(f"{pid}: {len(dump['bodies'])} static bodies, the spec has {len(described['colliders'])} colliders")
    for b in dump["bodies"]:
        if not b["shapes"] or any(s["class"] != "ConvexPolygonShape3D" or s["points"] < 4 for s in b["shapes"]):
            problems.append(f"{pid}: body {b['name']} has no closed convex shape ({b['shapes']})")
    want = described["bounds_m"]
    got = dump["bounds"]
    if not (_close(got["min"], want["min"], BOUNDS_TOLERANCE_M) and _close(got["max"], want["max"], BOUNDS_TOLERANCE_M)):
        problems.append(f"{pid}: Godot bounds {got} differ from the spec's {want} (size, pivot or Y up)")
    missed = [i for i, h in enumerate(dump["hits"]) if h is None]
    if missed:
        problems.append(f"{pid}: rays through colliders {missed} hit nothing (collision not closed or missing)")
    return problems


def table_md(rows: list[dict[str, Any]], budgets: dict[str, int]) -> str:
    lines = ["UV2: each piece's own lightmap UV; texels/m = the mesh's lightmap size (Godot's lightmap_size_hint) times "
             "the UV2 column (UV units per metre); the hint for 10 texels/m is 10 / UV2.", "",
             "| piece | kind | triangles (budget) | size x, y, z (m) | colliders (glass) | UV2 per m (hint for 10 px/m) | nodes |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        size = ", ".join(f"{v:g}" for v in r["size_m"])
        extra = ", ".join(n.removeprefix(r["id"] + "_") for n in r["nodes"][1:]) or "-"
        uv2 = r.get("uv2_per_m", 0.0)
        hint = f"{10 / uv2:.0f}" if uv2 else "-"
        lines.append(f"| {r['id']} | {r['kind']} | {r['triangles']} ({budgets[r['kind']]}) | {size} | "
                     f"{r['colliders']} ({r['glass_colliders']}) | {uv2:.3f} ({hint}) | {extra} |")
    return "\n".join(lines) + "\n"
