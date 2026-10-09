"""Helpers of `props` (docs/props.md): the dressing library's mapping file (props/library.toml), a glTF/GLB reader
that measures a pack model's bounds and triangles without Blender, and the library's pure checks (ids, classes,
budgets, sources and their licences, the scale of every pack prop against its inventory size). Standard library
only."""

from __future__ import annotations

import json
import math
import struct
import tomllib
from pathlib import Path
from typing import Any

from .. import common

LIBRARY = common.ROOT / "props" / "library.toml"
SOURCES = common.ROOT / "sources"
ROUTES = ("pack", "proc")
PIVOTS = ("floor", "wall", "ceiling")
COLLISIONS = ("box", "hull", "boxes", "none")
SCALE_TOLERANCE = 0.10  # a pack prop's scaled box against its inventory size, per axis (props.md §5)
STRETCH_LIMIT = 1.5  # with stretch = true the builder fits per axis: the largest axis factor over the smallest


def load(path: Path = LIBRARY) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


def default_out(lib: dict[str, Any]) -> Path:
    return common.raw_dir() / lib["out"]


def env_dir() -> Path:
    return common.raw_dir() / "env"


# --- glTF -------------------------------------------------------------------------------------------------------

def read_gltf_bytes(data: bytes) -> dict[str, Any]:
    """The JSON of a .glb or .gltf file's bytes."""
    if data[:4] == b"glTF":
        length, ctype = struct.unpack_from("<II", data, 12)
        if ctype != 0x4E4F534A:
            raise ValueError("the first GLB chunk is not JSON")
        return json.loads(data[20:20 + length].decode("utf-8"))
    return json.loads(data.decode("utf-8"))


def read_gltf(path: Path) -> dict[str, Any]:
    return read_gltf_bytes(path.read_bytes())


def _mat_mul(a: list[float], b: list[float]) -> list[float]:
    """4x4 column-major (glTF) product a * b."""
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def node_matrix(node: dict[str, Any]) -> list[float]:
    if "matrix" in node:
        return [float(v) for v in node["matrix"]]
    tx, ty, tz = node.get("translation", [0.0, 0.0, 0.0])
    x, y, z, w = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
    sx, sy, sz = node.get("scale", [1.0, 1.0, 1.0])
    r = [1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w),
         2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w),
         2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)]
    return [r[0] * sx, r[1] * sx, r[2] * sx, 0.0, r[3] * sy, r[4] * sy, r[5] * sy, 0.0,
            r[6] * sz, r[7] * sz, r[8] * sz, 0.0, tx, ty, tz, 1.0]


def _apply(m: list[float], p: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(m[r] * p[0] + m[4 + r] * p[1] + m[8 + r] * p[2] + m[12 + r] for r in range(3))


def measure(gltf: dict[str, Any]) -> dict[str, Any]:
    """World bounds (from the accessors' min/max through the node transforms), triangles, meshes and materials of
    the default scene."""
    nodes, meshes, acc = gltf.get("nodes", []), gltf.get("meshes", []), gltf.get("accessors", [])
    scenes = gltf.get("scenes", [{"nodes": list(range(len(nodes)))}])
    roots = scenes[gltf.get("scene", 0)].get("nodes", [])
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    tris = prims = 0
    stack = [(i, [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]) for i in roots]
    while stack:
        i, parent = stack.pop()
        node = nodes[i]
        m = _mat_mul(parent, node_matrix(node))
        if "mesh" in node:
            for prim in meshes[node["mesh"]]["primitives"]:
                a = acc[prim["attributes"]["POSITION"]]
                if "min" not in a or prim.get("mode", 4) != 4:
                    continue
                prims += 1
                count = acc[prim["indices"]]["count"] if "indices" in prim else a["count"]
                tris += count // 3
                for cx in (a["min"][0], a["max"][0]):
                    for cy in (a["min"][1], a["max"][1]):
                        for cz in (a["min"][2], a["max"][2]):
                            p = _apply(m, (cx, cy, cz))
                            for k in range(3):
                                lo[k], hi[k] = min(lo[k], p[k]), max(hi[k], p[k])
        stack += [(c, m) for c in node.get("children", [])]
    if not prims:
        return {"min": [0.0] * 3, "max": [0.0] * 3, "size": [0.0] * 3, "triangles": 0, "primitives": 0,
                "materials": len(gltf.get("materials", []))}
    return {"min": [round(v, 4) for v in lo], "max": [round(v, 4) for v in hi],
            "size": [round(hi[k] - lo[k], 4) for k in range(3)], "triangles": tris, "primitives": prims,
            "materials": len(gltf.get("materials", []))}


def measure_file(path: Path) -> dict[str, Any]:
    return measure(read_gltf(path))


# --- the library ------------------------------------------------------------------------------------------------

def size_xyz(size_m: list[float]) -> list[float]:
    """The inventory's L x W x H (along X, along Z, up) as glTF X, Y, Z."""
    return [size_m[0], size_m[2], size_m[1]]


def yawed(size: list[float], yaw_deg: float) -> list[float]:
    """A glTF X, Y, Z box size after a turn about +Y by a multiple of 90 degrees."""
    q = int(round(yaw_deg / 90.0)) % 4
    return [size[2], size[1], size[0]] if q % 2 else list(size)


def scaled_size(p: dict[str, Any]) -> list[float]:
    """The pack prop's box after its uniform scale and yaw, glTF X, Y, Z."""
    s = p.get("scale", 1.0)
    return [round(v * s, 4) for v in yawed(p["src_size"], p.get("yaw_deg", 0.0))]


def sources_index(folder: Path = SOURCES) -> dict[str, dict[str, Any]]:
    out = {}
    for f in sorted(folder.glob("*.toml")):
        with open(f, "rb") as fh:
            rec = tomllib.load(fh)
        out[rec.get("id", f.stem)] = rec
    return out


def check(lib: dict[str, Any], sources: dict[str, dict[str, Any]], kit_spec: dict[str, Any] | None = None
          ) -> list[str]:
    """Every problem of the mapping file, as text; empty when clean. Pure: reads no raw file."""
    problems: list[str] = []
    budgets = lib.get("budgets", {})
    materials = lib.get("materials", {})
    if len(set(materials.values())) > lib.get("max_materials", 6):
        problems.append(f"materials: {len(set(materials.values()))} targets, at most {lib.get('max_materials', 6)}")
    if kit_spec is not None:
        kit_mats = set(kit_spec.get("materials", {})) | set(lib.get("new_materials", []))
        for name, target in materials.items():
            if target not in kit_mats:
                problems.append(f"materials: {name} -> {target} is neither a kit material nor in new_materials")
    roles = dict(lib.get("roles", {}))
    if kit_spec is not None:
        for name, r in kit_spec.get("roles", {}).items():
            roles.setdefault(name, r)
    for name, r in lib.get("roles", {}).items():
        if r.get("material") not in materials:
            problems.append(f"role {name}: material {r.get('material')!r} is not in [materials]")
        hx = r.get("hex", "")
        if not (len(hx) == 7 and hx.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in hx[1:])):
            problems.append(f"role {name}: hex {hx!r} is not #rrggbb")
    seen: set[str] = set()
    skip = lib.get("skip", {})
    for p in lib.get("prop", []):
        pid = p.get("id", "?")
        where = f"prop {pid}"
        if pid in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(pid)
        if pid in skip:
            problems.append(f"{where}: also listed in [skip]")
        if p.get("class") not in budgets:
            problems.append(f"{where}: class {p.get('class')!r} has no budget")
        if p.get("route") not in ROUTES:
            problems.append(f"{where}: route {p.get('route')!r} is not one of {ROUTES}")
        if p.get("pivot", "floor") not in PIVOTS:
            problems.append(f"{where}: pivot {p.get('pivot')!r} is not one of {PIVOTS}")
        if p.get("collision") not in COLLISIONS:
            problems.append(f"{where}: collision {p.get('collision')!r} is not one of {COLLISIONS}")
        size = p.get("size_m", [])
        if len(size) != 3 or min(size, default=0) <= 0:
            problems.append(f"{where}: size_m must be three positive metres (L x W x H)")
            continue
        if not p.get("roles"):
            problems.append(f"{where}: no paint roles")
        for r in p.get("roles", []):
            if r not in roles:
                problems.append(f"{where}: role {r!r} is neither the library's nor the kit's")
        lo_hi = budgets.get(p.get("class"), [0, 0])
        if p.get("budget", lo_hi[1]) > lo_hi[1]:
            problems.append(f"{where}: budget {p['budget']} over the class's {lo_hi[1]}")
        if p.get("route") == "pack":
            src = p.get("source", "")
            rec = sources.get(src)
            if rec is None:
                problems.append(f"{where}: source {src!r} has no record in sources/")
            else:
                if rec.get("public_repo_ok") is not True:
                    problems.append(f"{where}: source {src} is not public_repo_ok")
                if rec.get("licence") not in lib.get("licences", ["CC0-1.0"]):
                    problems.append(f"{where}: source {src} licence {rec.get('licence')!r} is not allowed")
            if not p.get("files"):
                problems.append(f"{where}: a pack prop needs files (relative to <raw>/env)")
            if len(p.get("src_size", [])) != 3:
                problems.append(f"{where}: no measured src_size (run `props --measure`)")
                continue
            want = size_xyz(p.get("pack_size_m", size))
            src = yawed(p["src_size"], p.get("yaw_deg", 0.0))
            if min(src) <= 0:
                problems.append(f"{where}: a flat source ({src}); make it procedural")
                continue
            if p.get("stretch"):
                ratios = [want[k] / src[k] for k in range(3)]
                if max(ratios) / min(ratios) > STRETCH_LIMIT:
                    problems.append(f"{where}: stretching the source to its size distorts it "
                                    f"{max(ratios) / min(ratios):.2f}x (at most {STRETCH_LIMIT}); pick another file "
                                    "or make it procedural")
            else:
                got = scaled_size(p)
                for k, axis in enumerate("XYZ"):
                    if abs(got[k] - want[k]) > SCALE_TOLERANCE * want[k] + 0.01:
                        problems.append(f"{where}: scaled {axis} {got[k]:.3f} m against {want[k]:.3f} m "
                                        f"(more than {SCALE_TOLERANCE:.0%} off; fix scale or yaw_deg, or stretch)")
            if p.get("src_triangles", 0) > lo_hi[1] and not p.get("decimate"):
                problems.append(f"{where}: the source has {p['src_triangles']} triangles, over the class's "
                                f"{lo_hi[1]}; set decimate = true")
        elif p.get("route") == "proc":
            if not p.get("shape"):
                problems.append(f"{where}: a procedural prop needs a shape")
            for k in ("source", "files", "scale", "stretch", "decimate"):
                if k in p:
                    problems.append(f"{where}: {k} belongs to pack props")
    for pid in skip:
        if not isinstance(skip[pid], str) or not skip[pid]:
            problems.append(f"skip {pid}: give the reason and who makes it")
    return problems


def remeasure(lib: dict[str, Any], env: Path) -> tuple[list[str], int]:
    """Measures every pack prop's files again; the problems where the record differs, and how many were found."""
    problems, found = [], 0
    for p in lib.get("prop", []):
        if p.get("route") != "pack":
            continue
        paths = [env / f for f in p.get("files", [])]
        missing = [f.as_posix() for f in paths if not f.is_file()]
        if missing:
            problems.append(f"prop {p['id']}: missing {', '.join(missing)}")
            continue
        found += 1
        ms = [measure_file(f) for f in paths]
        size = [max(m["size"][0] for m in ms), sum(m["size"][1] for m in ms), max(m["size"][2] for m in ms)]
        tris = sum(m["triangles"] for m in ms)
        if any(abs(size[k] - p["src_size"][k]) > 0.002 for k in range(3)) or tris != p.get("src_triangles"):
            problems.append(f"prop {p['id']}: measured {[round(v, 4) for v in size]} / {tris} triangles, recorded "
                            f"{p['src_size']} / {p.get('src_triangles')}")
    return problems, found


def table_md(lib: dict[str, Any]) -> str:
    rows = ["| id | class | route | size (m) | source | scale | roles |", "|---|---|---|---|---|---:|---|"]
    for p in lib.get("prop", []):
        src = p.get("source", "") + (" " + ", ".join(Path(f).stem for f in p.get("files", [])) if p.get("files") else "")
        rows.append(f"| {p['id']} | {p['class']} | {p['route']} | {'x'.join(str(v) for v in p['size_m'])} | "
                    f"{src or p.get('shape', '')} | {p.get('scale', '')} | {', '.join(p.get('roles', []))} |")
    return "\n".join(rows) + "\n"
