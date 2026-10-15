"""The merged shell (#107): a room's static kit pieces drawn as one mesh per class and material instead of one
instance per piece (docs/house.md "Draw calls").

`merge(items, out)` reads each piece's GLB (the kit's: one visual node per piece, primitives with POSITION, NORMAL,
TEXCOORD_0, TEXCOORD_1 and COLOR_0; collider nodes `-convcolonly` / `-colonly` / `-col` are skipped), moves its
visual primitives by the piece's transform in the room (the scene's own `Transform3D` text, so the merged mesh sits
exactly where the instances drew) and writes one GLB: a node `merged_<class>` per class (`floor`, `ceiling`, `shell`:
the bake treats floors and ceilings apart, `zone_build.gd`), each a mesh with one primitive per material (the kit's
material names kept, so the export's set material and `plan_at` find them; a name whose prop GLBs give it
different values gets one primitive per variant, `material_key`). UV0 (the kit's box projection) and the
vertex colours (the paint and layer) are copied unchanged: the look is the instances'. UV2 (the lightmap UV) is
repacked: each piece's own UV2 island set, scaled to metres by its `uv2_per_m` (the kit's `pieces.json`), is
shelf-packed with a GAP between pieces into one square of side S metres, so the merged mesh has one uniform density
`uv2_per_m = 1 / S` (in the node's `extras` and the returned record): a bake gives it `texel * S` texels.
Pure Python, standard library only."""

from __future__ import annotations

import json
import math
import re
import struct
from pathlib import Path

COLLIDER = ("-convcolonly", "-colonly", "-col")
GAP_M = 0.25  # metres between two pieces' UV2 islands in the packed atlas (two texels at the Low preset's 8/m)
_FMT = {5126: ("f", 4), 5123: ("H", 2), 5125: ("I", 4), 5121: ("B", 1)}
_N = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def rows_of(transform: str) -> list[list[float]]:
    """A scene's `Transform3D(...)` text (basis by rows, then the origin) as a 3 x 4 row matrix."""
    v = [float(x) for x in transform[transform.index("(") + 1:transform.rindex(")")].split(",")]
    if len(v) != 12:
        raise ValueError(f"not a Transform3D: {transform}")
    return [[v[0], v[1], v[2], v[9]], [v[3], v[4], v[5], v[10]], [v[6], v[7], v[8], v[11]]]


def _mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(3)) + (a[i][3] if j == 3 else 0) for j in range(4)] for i in range(3)]


def _node_rows(n: dict) -> list[list[float]]:
    if "matrix" in n:
        m = n["matrix"]  # column-major 4 x 4
        return [[m[0 + i], m[4 + i], m[8 + i], m[12 + i]] for i in range(3)]
    x, y, z, w = n.get("rotation", [0, 0, 0, 1])
    sx, sy, sz = n.get("scale", [1, 1, 1])
    tx, ty, tz = n.get("translation", [0, 0, 0])
    r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return [[r[i][0] * sx, r[i][1] * sy, r[i][2] * sz, (tx, ty, tz)[i]] for i in range(3)]


def _read(j: dict, binary: bytes, acc: int) -> list[tuple]:
    a = j["accessors"][acc]
    v = j["bufferViews"][a["bufferView"]]
    code, size = _FMT[a["componentType"]]
    n = _N[a["type"]]
    stride = v.get("byteStride", size * n)
    base = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    out = []
    for i in range(a["count"]):
        out.append(struct.unpack_from(f"<{n}{code}", binary, base + i * stride))
    if a.get("normalized"):
        top = float((1 << (8 * size)) - 1)
        out = [tuple(c / top for c in t) for t in out]
    return out


def read_glb(path: Path) -> tuple[dict, bytes]:
    b = Path(path).read_bytes()
    if b[:4] != b"glTF":
        raise ValueError(f"{path}: not a GLB")
    n = struct.unpack("<I", b[12:16])[0]
    rest = b[20 + n:]
    return json.loads(b[20:20 + n]), rest[8:8 + struct.unpack("<I", rest[:4])[0]]


def visual(path: Path) -> list[dict]:
    """The visual primitives of a GLB in its scene's frame: {"node", "material" (dict), "pos", "nrm", "uv0", "uv1",
    "col", "idx"}; collider nodes skipped."""
    j, binary = read_glb(path)
    mats = j.get("materials", [])
    parent = {c: i for i, n in enumerate(j["nodes"]) for c in n.get("children", [])}
    out = []
    for i, n in enumerate(j["nodes"]):
        if "mesh" not in n or n.get("name", "").endswith(COLLIDER):
            continue
        m, k = _node_rows(n), parent.get(i)
        while k is not None:
            m = _mul(_node_rows(j["nodes"][k]), m)
            k = parent.get(k)
        for p in j["meshes"][n["mesh"]]["primitives"]:
            at = p["attributes"]
            pos = _read(j, binary, at["POSITION"])
            prim = {"node": n.get("name"), "material": mats[p["material"]] if "material" in p else {"name": "default"},
                    "pos": [_apply(m, v) for v in pos],
                    "nrm": [_rot(m, v) for v in _read(j, binary, at["NORMAL"])] if "NORMAL" in at else None,
                    "uv0": _read(j, binary, at["TEXCOORD_0"]) if "TEXCOORD_0" in at else None,
                    "uv1": _read(j, binary, at["TEXCOORD_1"]) if "TEXCOORD_1" in at else None,
                    "col": _read(j, binary, at["COLOR_0"]) if "COLOR_0" in at else None,
                    "idx": [t[0] for t in _read(j, binary, p["indices"])] if "indices" in p else list(range(len(pos)))}
            out.append(prim)
    return out


def _apply(m, v) -> tuple:
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] + m[i][3] for i in range(3))


def _rot(m, v) -> tuple:
    r = [m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3)]
    s = math.sqrt(sum(c * c for c in r)) or 1.0
    return tuple(c / s for c in r)


def pack(sizes: list[tuple[float, float]], gap: float = GAP_M) -> tuple[list[tuple[float, float]], float]:
    """Shelf-pack rectangles (w, h in metres) tallest first into a square: (each one's corner, the square's side)."""
    order = sorted(range(len(sizes)), key=lambda i: (-sizes[i][1], -sizes[i][0]))
    area = sum((w + gap) * (h + gap) for w, h in sizes)
    width = max([math.sqrt(area) * 1.05] + [w + gap for w, _ in sizes])
    at: list = [None] * len(sizes)
    x = y = shelf = 0.0
    for i in order:
        w, h = sizes[i]
        if x > 0 and x + w + gap > width:
            x, y, shelf = 0.0, y + shelf, 0.0
        at[i] = (x + gap / 2, y + gap / 2)
        x += w + gap
        shelf = max(shelf, h + gap)
    return at, max(width, y + shelf)


_CENTRES: dict = {}  # a GLB's visual bounding box centre in its own frame, read once per run


def centre(glb: Path, transform: str) -> tuple[float, float, float]:
    """The centre of a piece's (or prop's) visual bounding box where the scene's transform puts it."""
    key = str(glb)
    if key not in _CENTRES:
        pos = [v for p in visual(Path(glb)) for v in p["pos"]] or [(0.0, 0.0, 0.0)]
        _CENTRES[key] = tuple((min(v[i] for v in pos) + max(v[i] for v in pos)) / 2 for i in range(3))
    return _apply(rows_of(transform), _CENTRES[key])


def cell_of(x: float, z: float, size: float | None) -> str:
    """The grid cell (#185) a point of the room's floor plan falls in: "" for no grid (size None: the room is one
    cell), else `c<i>_<k>` (x and z cell indices; a negative index as `n<i>`, no "-": Godot reads `-col` as a hint)."""
    if not size:
        return ""
    def idx(v: float) -> str:
        i = math.floor(v / size + 1e-9)
        return str(i) if i >= 0 else f"n{-i}"
    return f"c{idx(x)}_{idx(z)}"


def cells(items: list[dict], size: float | None) -> list[tuple[str, list[dict]]]:
    """items (merge's: "glb", "transform") split into the grid cells of `size` metres (#185) by the centre of each one's
    visual bounding box, in the scene's (the room's) frame: [(cell, its items)] sorted by cell; one ("", items) for
    size None. A room-sized merged mesh enters every cube face of every shadowing lamp near any part of the room and
    its bounds pull it into views of the neighbours; a cell's mesh stays local."""
    if not size:
        return [("", list(items))]
    out: dict = {}
    for it in items:
        x, _, z = centre(it["glb"], it["transform"])
        out.setdefault(cell_of(x, z, size), []).append(it)
    return sorted(out.items())


def material_key(material: dict) -> str:
    """A material's values without its name (base colour, emission and its strength, roughness, metallic, alpha mode,
    every extension): two prop GLBs may give one name different values (#184's review: a red safelight and a bare
    bulb both `kit_emissive-vcol`), so the merge groups surfaces by name and these values. Refuses a texture: the
    merged GLB carries no images."""
    def textured(v) -> bool:
        return isinstance(v, dict) and ("index" in v or any(textured(x) for x in v.values()))
    if textured({k: v for k, v in material.items() if k != "name"}):
        raise ValueError(f"material {material.get('name')!r} has a texture; the merged GLB carries no images")
    return json.dumps({k: v for k, v in material.items() if k != "name"}, sort_keys=True, separators=(",", ":"))


def variant_name(name: str, keys: list, key: str) -> str:
    """The merged surface's material name: the source name for its first variant, `<name>__<n>` before the Godot hint
    suffix (`kit_emissive__1-vcol`, so Godot still reads `-vcol`) for the n-th further one. Appends key to keys."""
    keys.append(key)
    n = len(keys) - 1
    if n == 0:
        return name
    base, dash, hint = name.partition("-")
    return f"{base}__{n}{dash}{hint}"


def merge(items: list[dict], out: Path, gap: float = GAP_M) -> dict:
    """items: {"glb": path, "transform": the scene's Transform3D text, "class": "floor" | "ceiling" | "shell",
    "uv2_per_m": the piece's UV2 density, None for a piece without UV2}. Writes out (a GLB) and returns {"classes": {class: {"uv2_per_m",
    "materials", "vertices", "triangles", "pieces"}}}."""
    cache: dict = {}
    by_class: dict = {}
    for it in items:
        if it["glb"] not in cache:
            cache[it["glb"]] = visual(it["glb"])
        by_class.setdefault(it["class"], []).append(it)
    record: dict = {"classes": {}}
    nodes, meshes, materials, accessors, views, blob = [], [], [], [], [], bytearray()
    mat_index: dict = {}
    variant: dict = {}  # material key -> its surface's material name (one per distinct material, across classes)
    variants: dict = {}  # a source material name -> its variants' keys in first-seen order

    def put(data: bytes, comp: int, kind: str, count: int, target: int | None, minmax=None) -> int:
        while len(blob) % 4:
            blob.append(0)
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data),
                      **({"target": target} if target else {})})
        blob.extend(data)
        acc = {"bufferView": len(views) - 1, "componentType": comp, "count": count, "type": kind}
        if minmax:
            acc["min"], acc["max"] = minmax
        accessors.append(acc)
        return len(accessors) - 1

    for cls in sorted(by_class):
        its = by_class[cls]
        # UV2: each piece's islands' box, in metres at its density, packed into one square
        # (a class with a piece lacking UV2, such as a prop Godot unwraps on import, gets no TEXCOORD_1 at all)
        has_uv2 = all(p["uv1"] for it in its for p in cache[it["glb"]])
        boxes = []
        for it in its:
            uv = [t for p in cache[it["glb"]] if p["uv1"] for t in p["uv1"]] or [(0.0, 0.0), (1.0, 1.0)]
            u0, v0 = min(t[0] for t in uv), min(t[1] for t in uv)
            u1, v1 = max(t[0] for t in uv), max(t[1] for t in uv)
            per = it.get("uv2_per_m") or 1.0
            boxes.append((u0, v0, (u1 - u0) / per, (v1 - v0) / per))
        corners, side = pack([(b[2], b[3]) for b in boxes], gap)
        groups: dict = {}
        for it, box, corner in zip(its, boxes, corners):
            m = rows_of(it["transform"])
            k = 1.0 / (it.get("uv2_per_m") or 1.0)
            for p in cache[it["glb"]]:
                key = material_key(p["material"])
                if key not in variant:
                    variant[key] = variant_name(p["material"]["name"], variants.setdefault(p["material"]["name"], []),
                                                key)
                name = variant[key]
                g = groups.setdefault(name, {"material": {**p["material"], "name": name}, "key": key, "pos": [],
                                             "nrm": [], "uv0": [], "uv1": [], "col": [], "idx": []})
                if material_key(g["material"]) != key or g["material"]["name"] != name:  # (the review of #184)
                    raise ValueError(f"{it['glb']}: material {p['material']['name']!r} differs within its surface")
                base = len(g["pos"])
                g["pos"] += [_apply(m, v) for v in p["pos"]]
                g["nrm"] += [_rot(m, v) for v in (p["nrm"] or [(0, 1, 0)] * len(p["pos"]))]
                g["uv0"] += p["uv0"] or [(0, 0)] * len(p["pos"])
                g["uv1"] += [((corner[0] + (t[0] - box[0]) * k) / side, (corner[1] + (t[1] - box[1]) * k) / side)
                             for t in (p["uv1"] or [(box[0], box[1])] * len(p["pos"]))]
                g["col"] += p["col"] or [(1, 1, 1, 1)] * len(p["pos"])
                g["idx"] += [base + i for i in p["idx"]]
        prims = []
        rec = {"uv2_per_m": 1.0 / side if has_uv2 else None, "materials": [], "vertices": 0, "triangles": 0,
               "pieces": len(its)}
        for name in sorted(groups):
            g = groups[name]
            if name not in mat_index:
                mat_index[name] = len(materials)
                materials.append(g["material"])
            n = len(g["pos"])
            lo = [min(v[i] for v in g["pos"]) for i in range(3)]
            hi = [max(v[i] for v in g["pos"]) for i in range(3)]
            big = n > 65535
            att = {
                "POSITION": put(struct.pack(f"<{3 * n}f", *[c for v in g["pos"] for c in v]), 5126, "VEC3", n, 34962,
                                (lo, hi)),
                "NORMAL": put(struct.pack(f"<{3 * n}f", *[c for v in g["nrm"] for c in v]), 5126, "VEC3", n, 34962),
                "TEXCOORD_0": put(struct.pack(f"<{2 * n}f", *[c for v in g["uv0"] for c in v]), 5126, "VEC2", n,
                                  34962),
                "COLOR_0": put(struct.pack(f"<{4 * n}H", *[max(0, min(65535, round(c * 65535))) for v in g["col"]
                                                            for c in v]), 5123, "VEC4", n, 34962),
            }
            if has_uv2:
                att["TEXCOORD_1"] = put(struct.pack(f"<{2 * n}f", *[c for v in g["uv1"] for c in v]), 5126, "VEC2", n,
                                        34962)
            acc = accessors[att["COLOR_0"]]
            acc["normalized"] = True
            idx = put(struct.pack(f"<{len(g['idx'])}{'I' if big else 'H'}", *g["idx"]), 5125 if big else 5123,
                      "SCALAR", len(g["idx"]), 34963)
            prims.append({"attributes": att, "indices": idx, "material": mat_index[name]})
            rec["materials"].append(name)
            rec["vertices"] += n
            rec["triangles"] += len(g["idx"]) // 3
        meshes.append({"name": f"merged_{cls}", "primitives": prims})
        nodes.append({"name": f"merged_{cls}", "mesh": len(meshes) - 1,
                      **({"extras": {"uv2_per_m": rec["uv2_per_m"]}} if has_uv2 else {})})
        record["classes"][cls] = rec
    gltf = {"asset": {"version": "2.0", "generator": "prime-game-art house_merge (#107)"},
            "scene": 0, "scenes": [{"name": "Scene", "nodes": list(range(len(nodes)))}],
            "nodes": nodes, "meshes": meshes, "materials": materials, "accessors": accessors,
            "bufferViews": views, "buffers": [{"byteLength": len(blob)}]}
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    blob += b"\0" * (-len(blob) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(blob), 0x004E4942) + bytes(blob)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body)
    return record
