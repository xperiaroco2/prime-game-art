"""Helpers for the export command: reading a GLB's JSON chunk, checking an exported character against what Blender
said it exported, and the pinned glTF-Validator (docs/godot.md). Pure standard library."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

from .. import common

SCRIPT = "export_glb.py"
GLB_MAGIC = b"glTF"
JSON_CHUNK = 0x4E4F534A
PNG_MAGIC = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
JPEG_MAGIC = bytes([0xFF, 0xD8])
OUT = common.OUT / "export"
# An animation's last key is at its frame range's end over the fps; the exporter writes times as 32-bit floats.
DURATION_TOLERANCE_S = 1e-3


def glb_json(path: Path) -> dict[str, Any]:
    """The JSON chunk of a GLB file."""
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != GLB_MAGIC:
        raise common.Failure(f"{path} is not a GLB file")
    length, kind = struct.unpack("<II", data[12:20])
    if kind != JSON_CHUNK:
        raise common.Failure(f"{path}: the first chunk is not JSON")
    return json.loads(data[20 : 20 + length])


def summarize(gltf: dict[str, Any]) -> dict[str, Any]:
    """What a glTF holds, by name: root nodes, mesh nodes (with their skin), skins (with joint names), animations (with
    their duration), materials, and the things a character must not carry (cameras, lights, images)."""
    nodes = gltf.get("nodes", [])
    accessors = gltf.get("accessors", [])
    scene = gltf.get("scenes", [{}])[gltf.get("scene", 0)] if gltf.get("scenes") else {}
    animations = {}
    for anim in gltf.get("animations", []):
        ends = [accessors[s["input"]].get("max", [0.0])[0] for s in anim.get("samplers", [])]
        targets = {nodes[c["target"]["node"]].get("name", "") for c in anim.get("channels", []) if "node" in c["target"]}
        animations[anim.get("name", "")] = {"duration_s": max(ends, default=0.0), "channels": len(anim.get("channels", [])),
                                            "nodes": len(targets)}
    return {
        "generator": gltf.get("asset", {}).get("generator", ""),
        "roots": [nodes[i].get("name", "") for i in scene.get("nodes", [])],
        "meshes": {n.get("name", ""): n.get("skin") for n in nodes if "mesh" in n},
        "skins": [[nodes[j].get("name", "") for j in s.get("joints", [])] for s in gltf.get("skins", [])],
        "animations": animations,
        "animation_names": [a.get("name", "") for a in gltf.get("animations", [])],
        "materials": [m.get("name", "") for m in gltf.get("materials", [])],
        "cameras": len(gltf.get("cameras", [])),
        "lights": len(gltf.get("extensions", {}).get("KHR_lights_punctual", {}).get("lights", [])),
        "images": len(gltf.get("images", [])),
        "extensions": gltf.get("extensionsUsed", []),
    }


def check(info: dict[str, Any], summary: dict[str, Any], textured: bool = False) -> list[str]:
    """Problems with an exported character: info is what export_glb.py says it exported (the .export.json), summary
    the GLB's own content (summarize()). Empty when the GLB holds one skin of every bone, one skinned mesh node per
    part, every action as its own animation under its own name with its own length, and nothing else."""
    problems: list[str] = []
    parts, bones, actions = set(info["parts"]), list(info["bones"]), info["actions"]
    if len(summary["skins"]) != 1:
        problems.append(f"{len(summary['skins'])} skins, not 1")
    elif sorted(summary["skins"][0]) != sorted(bones):  # the exporter orders joints by hierarchy, not by bone order
        missing = sorted(set(bones) - set(summary["skins"][0]))
        extra = sorted(set(summary["skins"][0]) - set(bones))
        problems.append(f"the skin's {len(summary['skins'][0])} joints differ from the armature's {len(bones)} bones "
                        f"(missing {missing}, extra {extra})")
    if set(summary["meshes"]) != parts:
        problems.append(f"mesh nodes {sorted(summary['meshes'])}, parts {sorted(parts)}")
    unskinned = sorted(name for name, skin in summary["meshes"].items() if skin is None)
    if unskinned:
        problems.append(f"mesh nodes without a skin: {', '.join(unskinned)}")
    if summary["roots"] != [info["armature"]]:
        problems.append(f"root nodes {summary['roots']}, not just the armature {info['armature']}")
    names = summary["animation_names"]
    if len(names) != len(set(names)):
        problems.append("two animations share a name")
    if set(names) != set(actions):
        problems.append(f"animations {sorted(set(names) - set(actions))} are not actions; actions "
                        f"{sorted(set(actions) - set(names))} were not exported")
    fps = info.get("fps", 24)
    for name, (start, end) in actions.items():
        anim = summary["animations"].get(name)
        if anim is None:
            continue
        want = (end - start) / fps
        if abs(anim["duration_s"] - want) > DURATION_TOLERANCE_S:
            problems.append(f"{name}: {anim['duration_s']:.4f} s long, the action is {want:.4f} s ({start} to {end} at {fps} fps)")
        if anim["nodes"] != len(bones):
            problems.append(f"{name}: animates {anim['nodes']} of the {len(bones)} bones")
    for kind in ("cameras", "lights") + (() if textured else ("images",)):
        if summary[kind]:
            problems.append(f"{summary[kind]} {kind}")
    return problems


def validate(glb: Path, report: Path, timeout: float = 300) -> dict[str, Any]:
    """Runs the pinned glTF-Validator on glb, writes its JSON report to report and returns it."""
    result = common.run([common.gltf_validator_bin(), "--stdout", "--all", glb], timeout)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        tail = "\n".join(((result.stdout or "") + (result.stderr or "")).splitlines()[-20:])
        raise common.Failure(f"glTF-Validator wrote no JSON report (exit code {result.returncode}):\n{tail}") from exc
    report.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data


SEVERITIES = {0: "error", 1: "warning", 2: "info", 3: "hint"}


def verdict(report: dict[str, Any]) -> tuple[bool, str]:
    """Whether the validator's report passes (no error; a report without counts fails) and its summary line."""
    counts = report.get("issues", {})
    line = (f"glTF-Validator {report.get('validatorVersion', '?')}: {counts.get('numErrors', '?')} errors, "
            f"{counts.get('numWarnings', '?')} warnings, {counts.get('numInfos', '?')} infos, {counts.get('numHints', '?')} hints")
    return counts.get("numErrors", 1) == 0, line


def issues(report: dict[str, Any]) -> dict[str, list[str]]:
    """The validator's messages by severity, one line per code with its count and pointers:
    {"error": [...], "warning": [...], "info": [...], "hint": [...]}."""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for msg in report.get("issues", {}).get("messages", []):
        key = (SEVERITIES.get(msg.get("severity"), "info"), str(msg.get("code")))
        grouped.setdefault(key, []).append(msg)
    out: dict[str, list[str]] = {name: [] for name in SEVERITIES.values()}
    for (severity, code), msgs in grouped.items():
        pointers = ", ".join(str(m.get("pointer", "")) for m in msgs[:4]) + (", ..." if len(msgs) > 4 else "")
        out[severity].append(f"{code} x{len(msgs)}: {msgs[0].get('message')} ({pointers})")
    return out


def glb_chunks(path: Path) -> tuple[dict[str, Any], bytes]:
    """The JSON and the binary chunk of a GLB file."""
    data = path.read_bytes()
    gltf = glb_json(path)
    length = struct.unpack("<I", data[12:16])[0]
    start = 20 + length
    binary = data[start + 8 : start + 8 + struct.unpack("<I", data[start : start + 4])[0]] if len(data) > start + 8 else b""
    return gltf, binary


def image_size(blob: bytes) -> tuple[int, int]:
    """Width and height of a PNG or JPEG image; (0, 0) when neither."""
    if blob[:8] == PNG_MAGIC and len(blob) >= 24:
        return struct.unpack(">II", blob[16:24])
    if blob[:2] == JPEG_MAGIC:
        i = 2
        while i + 9 < len(blob):
            if blob[i] != 0xFF:
                i += 1
                continue
            marker, size = blob[i + 1], struct.unpack(">H", blob[i + 2 : i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", blob[i + 5 : i + 9])
                return w, h
            i += 2 + size
    return 0, 0


def textured_audit(path: Path) -> dict[str, Any]:
    """A textured character as its GLB holds it: the images (mime, bytes, size), each material's base colour and
    normal textures (image indices), and per mesh node its surfaces with their material and whether they carry
    TEXCOORD_0 and TANGENT."""
    gltf, binary = glb_chunks(path)
    views = gltf.get("bufferViews", [])
    images = []
    for im in gltf.get("images", []):
        if "bufferView" in im:
            v = views[im["bufferView"]]
            blob = binary[v.get("byteOffset", 0) : v.get("byteOffset", 0) + v["byteLength"]]
        else:
            blob = b""
        w, h = image_size(blob)
        images.append({"name": im.get("name", ""), "mime": im.get("mimeType", ""), "bytes": len(blob), "px": [w, h]})
    textures = gltf.get("textures", [])

    def source(ref: dict[str, Any] | None) -> int | None:
        return textures[ref["index"]].get("source") if ref else None

    materials = [{"name": m.get("name", ""), "base": source(m.get("pbrMetallicRoughness", {}).get("baseColorTexture")),
                  "normal": source(m.get("normalTexture"))} for m in gltf.get("materials", [])]
    meshes = {}
    for node in gltf.get("nodes", []):
        if "mesh" not in node:
            continue
        surfaces = []
        for prim in gltf["meshes"][node["mesh"]]["primitives"]:
            at = prim.get("attributes", {})
            surfaces.append({"material": prim.get("material"), "uv": "TEXCOORD_0" in at, "tangent": "TANGENT" in at,
                             "targets": len(prim.get("targets", []))})
        meshes[node.get("name", "")] = surfaces
    return {"images": images, "materials": materials, "meshes": meshes,
            "surfaces": sum(len(s) for s in meshes.values()),
            "image_bytes": sum(i["bytes"] for i in images)}


def textured_check(audit: dict[str, Any], surfaces_cap: int, max_px: int) -> list[str]:
    """Problems with a textured character: no texture at all, an image that is not PNG or JPEG or is larger than
    max_px on a side, a textured material without a normal map, a normal-mapped surface without UVs or tangents, more
    surfaces than surfaces_cap."""
    problems: list[str] = []
    if not any(m["base"] is not None for m in audit["materials"]):
        problems.append("no material has a base colour texture")
    for im in audit["images"]:
        if not all(im["px"]):
            problems.append(f"image {im['name']}: not a PNG or JPEG")
        elif max(im["px"]) > max_px:
            problems.append(f"image {im['name']}: {im['px'][0]} x {im['px'][1]} px, over {max_px}")
    for m in audit["materials"]:
        if m["base"] is not None and m["normal"] is None:
            problems.append(f"material {m['name']}: a base colour texture without a normal map")
    mats = audit["materials"]
    for name, surfaces in sorted(audit["meshes"].items()):
        for i, s in enumerate(surfaces):
            mat = mats[s["material"]] if s["material"] is not None else None
            if mat and mat["normal"] is not None and not (s["uv"] and s["tangent"]):
                problems.append(f"{name} surface {i} ({mat['name']}): normal-mapped without UVs and tangents")
    if audit["surfaces"] > surfaces_cap:
        problems.append(f"{audit['surfaces']} surfaces, over the contract's cap of {surfaces_cap}")
    return problems
