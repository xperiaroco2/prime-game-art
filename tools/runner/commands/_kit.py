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
    lines = ["| piece | kind | triangles (budget) | size x, y, z (m) | colliders (glass) | nodes |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        size = ", ".join(f"{v:g}" for v in r["size_m"])
        extra = ", ".join(n.removeprefix(r["id"] + "_") for n in r["nodes"][1:]) or "-"
        lines.append(f"| {r['id']} | {r['kind']} | {r['triangles']} ({budgets[r['kind']]}) | {size} | "
                     f"{r['colliders']} ({r['glass_colliders']}) | {extra} |")
    return "\n".join(lines) + "\n"
