"""The House packages' game-facing contract (#107): what the game reads in each committed room scene, so a draw-call
change (the merged shell, the batched dressing) can prove it touched only visual meshes of static pieces.

A room scene's contract is every real node (a `[node]` section with a type or an instance: the root and its metadata,
`Name`, `Shell`'s kit instances with their `metadata/surface`, `Dressing`, `Detail`, `Fixtures`' lights, `Doors`,
`Stations`, `Markers`, `Placeholders`) with all its properties, and every collider those instances bring from their
GLBs (`-convcolonly`, `-colonly`, `-col` nodes: the node, its shape kind, its transform in the GLB and its geometry's
hash, under the instance's own transform). Left out, because they only change what is drawn:
- override sections of an instanced GLB's children (no type, no instance) that set only visual properties
  (`VISUAL`: material overrides, instance shader parameters, `visible`);
- nodes named `merged_*` or `batch_*` (MERGED) and every override section under one: the merged shell's and the
  batched dressing's meshes, their shadow proxies (`*_shadow`, #185) and their `cast_shadow` overrides.
Pure Python, standard library only."""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VISUAL = ("surface_material_override/", "instance_shader_parameters/", "visible")
MERGED = ("merged_", "batch_")
COLLIDERS = {"-convcolonly": "convex", "-colonly": "trimesh", "-col": "trimesh_child"}
_HEAD = re.compile(r'^\[node (.*)\]$')
_ATTR = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|ExtResource\("[^"]*"\)|\[[^\]]*\]|\S+)')


def parse_tscn(text: str) -> tuple[dict, list[dict]]:
    """(ext_resource id -> path, the node sections in order: {"attrs": {...}, "props": [(key, raw value)]})."""
    ext, nodes, cur = {}, [], None
    for line in text.splitlines():
        if line.startswith("[ext_resource"):
            a = dict((k, v.strip('"')) for k, v in _ATTR.findall(line[1:-1]))
            ext[a["id"]] = a["path"]
            cur = None
        elif line.startswith("[node "):
            cur = {"attrs": dict(_ATTR.findall(_HEAD.match(line).group(1))), "props": []}
            nodes.append(cur)
        elif line.startswith("["):
            cur = None
        elif cur is not None and " = " in line:
            k, v = line.split(" = ", 1)
            cur["props"].append((k, v))
    return ext, nodes


def _path(attrs: dict) -> str:
    name = attrs["name"].strip('"')
    parent = attrs.get("parent", "").strip('"')
    return name if parent in ("", ".") else f"{parent}/{name}"


def glb_json(path: Path) -> tuple[dict, bytes]:
    b = Path(path).read_bytes()
    if b[:4] != b"glTF":
        raise ValueError(f"{path}: not a GLB (an LFS pointer?)")
    n = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + n])
    rest = b[20 + n:]
    binary = rest[8:8 + struct.unpack("<I", rest[:4])[0]] if len(rest) >= 8 else b""
    return j, binary


def colliders(path: Path) -> list[str]:
    """One line per collider node of a GLB: its node path, shape kind, local TRS chain and geometry hash."""
    j, binary = glb_json(path)
    parent = {c: i for i, n in enumerate(j["nodes"]) for c in n.get("children", [])}
    out = []
    for i, n in enumerate(j["nodes"]):
        kind = next((k for s, k in COLLIDERS.items() if n.get("name", "").endswith(s)), None)
        if kind is None or "mesh" not in n:
            continue
        chain, k = [], i
        while k is not None:
            nd = j["nodes"][k]
            chain.append(f'{nd.get("name")}:{json.dumps({t: nd[t] for t in ("matrix", "translation", "rotation", "scale") if t in nd}, sort_keys=True)}')
            k = parent.get(k)
        h = hashlib.sha256()
        for p in j["meshes"][n["mesh"]]["primitives"]:
            for acc in [p["attributes"]["POSITION"]] + ([p["indices"]] if "indices" in p else []):
                a = j["accessors"][acc]
                v = j["bufferViews"][a["bufferView"]]
                start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
                h.update(binary[start:start + v["byteLength"] - a.get("byteOffset", 0)])
        out.append(f"{kind} {' < '.join(chain)} {h.hexdigest()[:16]}")
    return sorted(out)


def scene_contract(text: str, resolve) -> dict:
    """{"nodes": [line], "colliders": [line]} of one room scene; resolve(res path) -> a local GLB path or None."""
    ext, nodes = parse_tscn(text)
    out_nodes, out_cols = [], []
    for nd in nodes:
        a = nd["attrs"]
        path = _path(a)
        if any(part.startswith(MERGED) for part in path.split("/")):  # #185: a proxy's or merged mesh's overrides too
            continue
        real = "type" in a or "instance" in a
        props = [(k, v) for k, v in nd["props"] if not k.startswith(VISUAL)]
        if not real and not props:
            continue
        inst = ext.get(re.sub(r'ExtResource\("([^"]*)"\)', r"\1", a.get("instance", "")), "")
        head = f'{path} type={a.get("type", "")} instance={inst} groups={a.get("groups", "")}'
        out_nodes.append(head + "".join(f" {k}={v}" for k, v in props))
        if inst.endswith(".glb"):
            glb = resolve(inst)
            if glb is None:
                out_cols.append(f"{path} ? {inst}")
                continue
            xf = dict(nd["props"]).get("transform", "")
            out_cols += [f"{path} {xf} {c}" for c in colliders(glb)]
    return {"nodes": out_nodes, "colliders": out_cols}


def _sha(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def committed_resolver(root: Path = ROOT):
    """res://<game path> -> the committed file with the SHA-256 a package.json lists for that game path."""
    by_sha: dict[str, Path] = {}
    for f in (root / "assets").rglob("export/**/*.glb"):
        by_sha.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), f)
    game: dict[str, str] = {}
    for pj in (root / "assets").glob("*/*/package.json"):
        files = json.loads(pj.read_text(encoding="utf-8")).get("files", {})
        if isinstance(files, dict):  # the House packages' {game path: sha256} (a character's is a list)
            game.update(files)
    return lambda res: by_sha.get(game.get(res.removeprefix("res://"), ""))


def snapshot(root: Path = ROOT, full: bool = False) -> dict:
    """Per committed package (the room set's folder) and scene: node and collider counts and hashes, per top group
    too (Shell, Dressing, ...), so a failure names where it changed. full: the lines themselves."""
    resolve = committed_resolver(root)
    out: dict = {}
    for f in sorted((root / "assets" / "room").glob("*/export/**/*.tscn")):
        c = scene_contract(f.read_text(encoding="utf-8"), resolve)
        groups: dict = {}
        for kind in ("nodes", "colliders"):
            for line in c[kind]:
                g = line.split(" ", 1)[0].split("/", 1)[0]
                groups.setdefault(g, {}).setdefault(kind, []).append(line)
        rec = {"nodes": len(c["nodes"]), "colliders": len(c["colliders"]),
               "sha": _sha(c["nodes"] + c["colliders"]),
               "groups": {g: {k: [len(v), _sha(v)[:16]] for k, v in d.items()} for g, d in sorted(groups.items())}}
        if full:
            rec["lines"] = c
        out.setdefault(f.relative_to(root / "assets" / "room").parts[0], {})[f.name] = rec
    return out


if __name__ == "__main__":  # write the pinned snapshot: $PYTHON_BIN -m runner.house_contract <out.json>
    import sys
    Path(sys.argv[1]).write_text(json.dumps(snapshot(), indent=1, sort_keys=True) + "\n", encoding="utf-8",
                                 newline="\n")
