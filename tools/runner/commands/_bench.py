"""The plain-Python half of `bench` (art #212): the copy counts, the variants, the spec for godot/bench/bench.gd, what a
GLB holds (face morphs, triangles, the shadow part) and the Markdown report. No Godot or Blender here, so the tests
run everywhere (docs/godot.md, "Bench")."""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Any

from .. import common
from . import _contract

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
BUDGET_MS = 4.0  # the characters' share of the GPU frame at 20 bodies the measurement is held to (#212)
# The meeting ring bench.gd stands the copies in, seen from behind it at eye height
RING = {"spacing_m": 1.3, "min_m": 2.2, "camera_back_m": 2.5, "eye_m": 1.6}


def ring_distances(copies: int, ring: dict[str, float] = RING) -> list[float]:
    """Each copy's distance from the camera (to its origin), as bench.gd places them: a ring of radius
    max(min_m, copies * spacing_m / 2 pi), the camera camera_back_m behind it at eye_m."""
    r = max(ring["min_m"], copies * ring["spacing_m"] / math.tau)
    out = []
    for i in range(copies):
        a = math.tau * i / copies
        across, depth = math.sin(a) * r, r + ring["camera_back_m"] - math.cos(a) * r
        out.append(math.sqrt(across ** 2 + ring["eye_m"] ** 2 + depth ** 2))
    return out


def beyond(copies: int, far_m: float, ring: dict[str, float] = RING) -> int:
    """How many of the copies stand farther than far_m from the camera."""
    return sum(d > far_m for d in ring_distances(copies, ring))


def contract_hand_lod_m(contract: dict[str, Any] | None = None) -> float:
    """Where the contract's LOD2 starts (`[[lods.levels]]` LOD2's `from_m`): the 'hand' variant's distance."""
    contract = contract if contract is not None else _contract.load_contract()
    for level in contract.get("lods", {}).get("levels", []):
        if level.get("name") == "LOD2":
            return float(level["from_m"])
    raise ValueError("the contract has no [[lods.levels]] LOD2")


HAND_LOD_M = contract_hand_lod_m()


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
    proxy; with the shadow part also "hand" (the part as a hand-made LOD2 beyond HAND_LOD_M, the contract's LOD2
    distance, full shadows). Grouped by GLB and count, the order bench.gd loads them in."""
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
            "hand_lod_m": hand_lod_m, "ring": dict(RING), "sheet_cell": list(SHEET_CELL), "sheet_cols": SHEET_COLS}


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
    """Adds to each row its characters' share: gpu_ms, cpu_ms and process_ms minus the empty stage's (`char_gpu_ms`,
    `char_cpu_ms`, `char_process_ms`); and to each group its buffer and video memory growth (`buffer_mb_added`,
    `video_mb_added`)."""
    rows = record.get("rows", [])
    empty = next((r for r in rows if r.get("copies") == 0), None)
    for r in rows:
        if empty is not None:
            r["char_gpu_ms"] = round(r["gpu_ms"] - empty["gpu_ms"], 3)
            r["char_cpu_ms"] = round(r["cpu_ms"] - empty["cpu_ms"], 3)
            if "process_ms" in r and "process_ms" in empty:
                r["char_process_ms"] = round(r["process_ms"] - empty["process_ms"], 3)
    for g in record.get("groups", []):
        before, after = g.get("memory_before", {}), g.get("memory_after", {})
        for key in ("buffer_mb", "video_mb", "texture_mb"):
            if key in before and key in after:
                g[key.replace("_mb", "_mb_added")] = round(after[key] - before[key], 2)
    return record


def verdict(record: dict[str, Any], glbs: list[dict[str, Any]], copies: int, budget_ms: float = BUDGET_MS) -> list[str]:
    """One line per GLB: the characters' GPU share at `copies` bodies in the default setup (`auto_full`: the automatic
    LODs, every mesh casting) against budget_ms, and the worst variant beside it."""
    out = []
    for g in glbs:
        rows = [r for r in record.get("rows", []) if r.get("glb") == g["id"] and r.get("copies") == copies
                and "char_gpu_ms" in r]
        default = next((r for r in rows if r.get("lod") == "auto" and r.get("shadow") == "full"), None)
        if default is None:
            continue
        worst = max(rows, key=lambda r: r["char_gpu_ms"])
        word = "within" if default["char_gpu_ms"] <= budget_ms else "OVER"
        worst_word = "within" if worst["char_gpu_ms"] <= budget_ms else "OVER"
        out.append(f"{g['id']} ({g['triangles']:,} tris, {g['morphs']} morphs): {int(copies)} bodies cost "
                   f"{default['char_gpu_ms']:.2f} ms GPU in the default setup ({default['id']}), {word} the "
                   f"{budget_ms:g} ms budget; the worst variant {worst['char_gpu_ms']:.2f} ms ({worst['id']}, "
                   f"{worst_word})")
    return out


def report(record: dict[str, Any], glbs: list[dict[str, Any]], budget_ms: float = BUDGET_MS) -> list[str]:
    """The Markdown report: the machine, the GLBs, the timing table, the memory per group, the verdicts."""
    lines = [f"# bench: {', '.join(g['id'] for g in glbs)}", "",
             f"- adapter: {record.get('adapter', '?')} ({record.get('adapter_vendor', '?')}); renderer "
             f"{record.get('renderer', '?')}; Godot {record.get('godot', '?')}",
             f"- window {'x'.join(map(str, record.get('window', [])))}, vertical FOV {record.get('fov_deg', '?')} deg, "
             f"{int(record.get('frames', 0))} measured frames per variant (median; p95 beside it)",
             "- stage: ground, procedural sky, AgX, SSAO; a directional light with 4 shadow splits and a shadowed "
             "omni lamp (cube) at the ring's centre; every face morph weighted 0.05",
             "- CPU ms is the viewport's render time only; process ms (animation players, skeleton poses) and frame ms "
             "(the whole frame) beside it; `beyond` counts the copies farther than the hand-made LOD2's "
             f"{record.get('hand_lod_m', HAND_LOD_M):g} m from the camera, "
             "the only ones the hand variant switches", "",
             "| GLB | triangles | shadow part | face morphs | MB |", "|---|---|---|---|---|"]
    for g in glbs:
        lines.append(f"| {g['id']} | {g['triangles']:,} | {g['shadow_triangles']:,} | {g['morphs']} | {g['mb']:.1f} |")
    far = float(record.get("hand_lod_m", HAND_LOD_M))
    lines += ["", "| variant | copies | beyond | LOD | shadows | GPU ms | p95 | chars GPU ms | CPU ms | chars CPU ms | "
                  "process ms | frame ms | primitives | draw calls | video MB | buffer MB |", "|" + "---|" * 16]

    def ms(r: dict[str, Any], key: str) -> str:
        return f"{r[key]:.2f}" if key in r else "-"  # records made before the field have none

    for r in record.get("rows", []):
        n = int(r["copies"])
        lines.append(f"| {r['id']} | {n} | {int(r.get('beyond_hand_lod', beyond(n, far)))} | {r['lod']} | "
                     f"{r['shadow']} | {r['gpu_ms']:.2f} | {r.get('gpu_ms_p95', 0):.2f} | "
                     f"{r.get('char_gpu_ms', 0):.2f} | {r['cpu_ms']:.2f} | {r.get('char_cpu_ms', 0):.2f} | "
                     f"{ms(r, 'process_ms')} | {ms(r, 'frame_ms')} | "
                     f"{r['primitives']:,} | {r['draw_calls']:,} | {r['video_mb']:.1f} | {r['buffer_mb']:.1f} |")
    lines += ["", "| loaded | buffer MB added | video MB added | texture MB added |", "|---|---|---|---|"]
    for g in record.get("groups", []):
        lines.append(f"| {g['key']} | {g.get('buffer_mb_added', 0):.2f} | {g.get('video_mb_added', 0):.2f} | "
                     f"{g.get('texture_mb_added', 0):.2f} |")
    counts = sorted({r["copies"] for r in record.get("rows", []) if r.get("copies")})
    verdicts = [line for n in counts for line in verdict(record, glbs, n, budget_ms)]
    if verdicts:
        lines += [""] + [f"- {line}" for line in verdicts]
    return lines
