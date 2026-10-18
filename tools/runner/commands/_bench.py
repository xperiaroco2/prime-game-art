"""The plain-Python half of `bench` (art #212): the copy counts, the variants, the spec for godot/bench/bench.gd, what a
GLB holds (face morphs, triangles, the shadow part) and the Markdown report. No Godot or Blender here, so the tests
run everywhere (docs/godot.md, "Bench")."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

from .. import common

OUT = common.OUT / "bench"
SCRIPT = "res://bench/bench.gd"
WINDOW = (1920, 1080)
FOV_DEG = 75.0  # Camera3D.fov, vertical (Godot's default keep_height); about 106 degrees across at 16:9
SHADOW_PART = "bench_shadow"  # the low-poly shadow caster bench_proxy.py adds
FRAMES = 300
WARMUP = 120
SETTLE = 30
MAX_COPIES = 64
SHEET_CELL = (424, 240)  # three across: a 1272 px sheet, the agents' size
SHEET_COLS = 3
HAND_LOD_M = 10.0  # the suggested LOD2 distance (contract [lods])
BUDGET_MS = 4.0  # the characters' share of the GPU frame at 20 bodies the measurement is held to (#212)


def parse_copies(text: str) -> list[int]:
    """'10,20' -> [10, 20]: distinct positive counts up to MAX_COPIES, in the given order."""
    out: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit() or not 1 <= int(part) <= MAX_COPIES:
            raise ValueError(f"copies: {part!r} is not a count from 1 to {MAX_COPIES}")
        if int(part) not in out:
            out.append(int(part))
    if not out:
        raise ValueError("copies: give at least one count, e.g. 10,20")
    return out


def glb_json(path: Path) -> dict[str, Any]:
    """The JSON chunk of a GLB."""
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise ValueError(f"{path.name} is not a GLB")
    length, kind = struct.unpack_from("<I4s", data, 12)
    if kind != b"JSON":
        raise ValueError(f"{path.name}: the first chunk is not JSON")
    return json.loads(data[20:20 + length])


def describe(gltf: dict[str, Any], shadow_part: str = SHADOW_PART) -> dict[str, Any]:
    """What the bench needs from a GLB: the most face morphs on one mesh, the triangles of every mesh but the shadow
    part (the character) and of the shadow part, and whether the shadow part is there."""
    accessors = gltf.get("accessors", [])
    morphs, character, shadow, has_shadow = 0, 0, 0, False
    for mesh in gltf.get("meshes", []):
        name = mesh.get("name", "")
        tris = 0
        for prim in mesh.get("primitives", []):
            morphs = max(morphs, len(prim.get("targets", [])))
            if "indices" in prim:
                tris += accessors[prim["indices"]]["count"] // 3
            else:
                tris += accessors[prim["attributes"]["POSITION"]]["count"] // 3
        if shadow_part in name:
            shadow, has_shadow = shadow + tris, True
        else:
            character += tris
    return {"morphs": morphs, "triangles": character, "shadow_triangles": shadow, "shadow_part": has_shadow}


def variants(glbs: list[dict[str, Any]], copies: list[int]) -> list[dict[str, Any]]:
    """The measured variants: first the empty stage (the scene's own cost), then per GLB and copy count the automatic
    LOD on ("auto") and off ("off"), each with full-mesh shadows and, when the GLB has the shadow part, the shadow
    proxy; with the shadow part also "hand" (the part as a hand-made LOD2 beyond HAND_LOD_M, full shadows). Grouped
    by GLB and count, the order bench.gd loads them in."""
    if not glbs:
        raise ValueError("no GLB to measure")
    out = [{"id": "empty", "glb": glbs[0]["id"], "copies": 0, "lod": "auto", "shadow": "full"}]
    for g in glbs:
        for n in copies:
            pairs = [("auto", "full"), ("off", "full")]
            if g["shadow_part"]:
                pairs = [("auto", "full"), ("auto", "proxy"), ("off", "full"), ("off", "proxy"), ("hand", "full")]
            for lod, shadow in pairs:
                out.append({"id": f"{g['id']}_x{n}_{lod}_{shadow}", "glb": g["id"], "copies": n, "lod": lod,
                            "shadow": shadow})
    return out


def spec(glbs: list[dict[str, Any]], copies: list[int], clip: str = "Idle", frames: int = FRAMES,
         warmup: int = WARMUP, settle: int = SETTLE, hand_lod_m: float = HAND_LOD_M) -> dict[str, Any]:
    """The spec bench.gd reads. Each GLB: its res:// path and its face morph count."""
    if frames < 1 or warmup < 0 or settle < 0:
        raise ValueError("frames must be at least 1, warmup and settle at least 0")
    return {"glbs": {g["id"]: {"res": g["res"], "morphs": g["morphs"]} for g in glbs},
            "variants": variants(glbs, copies), "clip": clip, "frames": frames, "warmup_frames": warmup,
            "settle_frames": settle, "fov_deg": FOV_DEG, "shadow_part": SHADOW_PART,
            "hand_lod_m": hand_lod_m, "sheet_cell": list(SHEET_CELL), "sheet_cols": SHEET_COLS}


def vram_import(text: str, normal: bool) -> str:
    """An extracted texture's .import text set to VRAM Compressed with mipmaps (normal: as a normal map), what the game
    imports characters with. Godot's scene import extracts a GLB's images as Lossless and switches them to VRAM only
    when the editor sees them used in 3D, which a headless import never does."""
    want = {"compress/mode": "2", "mipmaps/generate": "true", "compress/normal_map": "1" if normal else "0"}
    lines, seen = [], set()
    for line in text.splitlines():
        key = line.split("=", 1)[0]
        if key in want:
            line = f"{key}={want[key]}"
            seen.add(key)
        lines.append(line)
    if "[params]" not in lines:
        lines.append("[params]")
    at = lines.index("[params]") + 1
    lines[at:at] = [f"{k}={v}" for k, v in want.items() if k not in seen]
    return "\n".join(lines) + "\n"


def derive(record: dict[str, Any]) -> dict[str, Any]:
    """Adds to each row its characters' share: gpu_ms and cpu_ms minus the empty stage's (`char_gpu_ms`,
    `char_cpu_ms`); and to each group its buffer and video memory growth (`buffer_mb_added`, `video_mb_added`)."""
    rows = record.get("rows", [])
    empty = next((r for r in rows if r.get("copies") == 0), None)
    for r in rows:
        if empty is not None:
            r["char_gpu_ms"] = round(r["gpu_ms"] - empty["gpu_ms"], 3)
            r["char_cpu_ms"] = round(r["cpu_ms"] - empty["cpu_ms"], 3)
    for g in record.get("groups", []):
        before, after = g.get("memory_before", {}), g.get("memory_after", {})
        for key in ("buffer_mb", "video_mb", "texture_mb"):
            if key in before and key in after:
                g[key.replace("_mb", "_mb_added")] = round(after[key] - before[key], 2)
    return record


def verdict(record: dict[str, Any], glbs: list[dict[str, Any]], copies: int, budget_ms: float = BUDGET_MS) -> list[str]:
    """One line per GLB: its best variant's characters' GPU share at `copies` bodies against budget_ms."""
    out = []
    for g in glbs:
        rows = [r for r in record.get("rows", []) if r.get("glb") == g["id"] and r.get("copies") == copies
                and "char_gpu_ms" in r]
        if not rows:
            continue
        best = min(rows, key=lambda r: r["char_gpu_ms"])
        word = "within" if best["char_gpu_ms"] <= budget_ms else "OVER"
        out.append(f"{g['id']} ({g['triangles']:,} tris, {g['morphs']} morphs): {int(copies)} bodies cost "
                   f"{best['char_gpu_ms']:.2f} ms GPU at best ({best['id']}), {word} the {budget_ms:g} ms budget")
    return out


def report(record: dict[str, Any], glbs: list[dict[str, Any]], budget_ms: float = BUDGET_MS) -> list[str]:
    """The Markdown report: the machine, the GLBs, the timing table, the memory per group, the verdicts."""
    lines = [f"# bench: {', '.join(g['id'] for g in glbs)}", "",
             f"- adapter: {record.get('adapter', '?')} ({record.get('adapter_vendor', '?')}); renderer "
             f"{record.get('renderer', '?')}; Godot {record.get('godot', '?')}",
             f"- window {'x'.join(map(str, record.get('window', [])))}, vertical FOV {record.get('fov_deg', '?')} deg, "
             f"{int(record.get('frames', 0))} measured frames per variant (median; p95 beside it)",
             "- stage: ground, procedural sky, AgX, SSAO; a directional light with 4 shadow splits and a shadowed "
             "omni lamp (cube) at the ring's centre; every face morph weighted 0.05", "",
             "| GLB | triangles | shadow part | face morphs | MB |", "|---|---|---|---|---|"]
    for g in glbs:
        lines.append(f"| {g['id']} | {g['triangles']:,} | {g['shadow_triangles']:,} | {g['morphs']} | {g['mb']:.1f} |")
    lines += ["", "| variant | copies | LOD | shadows | GPU ms | p95 | chars GPU ms | CPU ms | chars CPU ms | "
                  "primitives | draw calls | video MB | buffer MB |", "|" + "---|" * 13]
    for r in record.get("rows", []):
        lines.append(f"| {r['id']} | {int(r['copies'])} | {r['lod']} | {r['shadow']} | "
                     f"{r['gpu_ms']:.2f} | {r.get('gpu_ms_p95', 0):.2f} | {r.get('char_gpu_ms', 0):.2f} | "
                     f"{r['cpu_ms']:.2f} | {r.get('char_cpu_ms', 0):.2f} | {r['primitives']:,} | {r['draw_calls']:,} | "
                     f"{r['video_mb']:.1f} | {r['buffer_mb']:.1f} |")
    lines += ["", "| loaded | buffer MB added | video MB added | texture MB added |", "|---|---|---|---|"]
    for g in record.get("groups", []):
        lines.append(f"| {g['key']} | {g.get('buffer_mb_added', 0):.2f} | {g.get('video_mb_added', 0):.2f} | "
                     f"{g.get('texture_mb_added', 0):.2f} |")
    counts = sorted({r["copies"] for r in record.get("rows", []) if r.get("copies")})
    verdicts = [line for n in counts for line in verdict(record, glbs, n, budget_ms)]
    if verdicts:
        lines += [""] + [f"- {line}" for line in verdicts]
    return lines
