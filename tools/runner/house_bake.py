"""The House's lightmap bake, the pure parts (#83; docs/house.md "Light"): the night window, the pieces a zone scene
uses, the zone build's arguments, the review cameras and the frame measures (L*, the dark share, C* p90).

The bake itself needs the Godot editor with a window (LightmapGI.bake() is editor-only C++): `house --bake` stages
the pieces, builds each zone's bake scene headless (godot/house/zone_build.gd), presses the editor's bake button
through the lmbake plugin (godot/addons/lmbake) in an off-screen window, and shoots the baked and real-time frames
(godot/house/bake_shots.gd). Editor runs only at night (00:00-08:00 local) or inside a window the manager granted."""

from __future__ import annotations

import math
import re
import struct
import time
import zlib
from pathlib import Path

NIGHT_START_H, NIGHT_END_H = 0, 8
# One grant file for the lab runner and this command: "until YYYY-MM-DD HH:MM" (local), written by the manager only
# after the engineer's yes in chat, removed after the run (labrun.py's rule).
GRANT = "research/2026-10-06-locations/lab/editor_window.txt"
EDITOR_BAN = ("house --bake: the editor bakes only between 00:00 and 08:00 local (or inside a window the manager "
              "granted); build the zones by day with --no-bake and bake at night")
PROP_IMPORT = {"meshes/light_baking": 2, "meshes/lightmap_texel_size": 0.2}  # Godot unwraps the props' UV2
KIT_IMPORT = {"meshes/light_baking": 1}  # the kit keeps its own UV2 (one island per face, docs/kit.md)
PROP_TEXEL_PER_M = 1.0 / PROP_IMPORT["meshes/lightmap_texel_size"]
ABOVE_OTHER_K = 0.1  # Above's walls and props only occlude: a tenth of the texels


def granted_until(text: str | None) -> float | None:
    """The grant file's end time (epoch seconds), or None when there is none or it is unreadable."""
    for line in (text or "").splitlines():
        if line.startswith("until "):
            try:
                return time.mktime(time.strptime(line[6:].strip(), "%Y-%m-%d %H:%M"))
            except ValueError:
                return None
    return None


def editor_allowed(now: float, grant_text: str | None = None) -> bool:
    """True inside the night window (local hours NIGHT_START_H..NIGHT_END_H) or before a grant's end."""
    until = granted_until(grant_text)
    if until is not None and now < until:
        return True
    return NIGHT_START_H <= time.localtime(now).tm_hour < NIGHT_END_H


def grant_text(raw: Path | None) -> str | None:
    path = raw / GRANT if raw else None
    try:
        return path.read_text(encoding="utf-8") if path else None
    except OSError:
        return None


def used_glbs(texts) -> set[str]:
    """The kit_<id> and prop_<id> names the zone and room scenes instance (res://import/<name>.glb)."""
    found: set[str] = set()
    for t in texts:
        found |= set(re.findall(r"res://import/((?:kit|prop)_[a-z0-9_]+)\.glb", t))
    return found


def uv2_table(pieces: list[dict]) -> dict[str, float]:
    """kit piece id -> its UV2 units per metre (the kit's pieces.json), for the lightmap size hints."""
    return {p["id"]: p["uv2_per_m"] for p in pieces if p.get("uv2_per_m")}


def size_hint(texel_per_m: float, uv2_per_m: float, k: float = 1.0) -> int:
    """A kit piece's lightmap_size_hint for texel_per_m (times k); at least 4. zone_build.gd computes the same."""
    return max(4, math.ceil(texel_per_m * k / uv2_per_m - 1e-9))


# The grid run (#83): texel density x the denoiser x the bounce energy on one zone, each variant baked and shot beside
# the zone's real-time frame. 1.5 is lights.toml's bounce energy (the lab's ceiling); 1.0 the plain bounce.
GRID_TEXELS = (8.0, 12.0, 16.0)
GRID_DENOISER = (True, False)
GRID_ENERGIES = (1.0, 1.5)


def variant_tag(texel: float, denoiser: bool, energy: float, merge: bool = False) -> str:
    """A variant's file-safe tag: t12_d1_e15 is 12 texels/m, the denoiser on, bounce energy 1.5; _m: merged floors."""
    return f"t{texel:g}_d{int(bool(denoiser))}_e{round(energy * 10)}" + ("_m" if merge else "")


def variants(lights: dict, zone: str, preset: str | None = None, grid: bool = False, merge: bool = False,
             reference: bool = False) -> list[dict]:
    """The bakes of one zone: the preset's texel with lights.toml's [bake] (tag = the preset's name), or with `grid`
    every GRID_TEXELS x GRID_DENOISER x GRID_ENERGIES variant. Each: tag, texel, bake (a copy with the overrides),
    merge. A preset with a `sheen` mode (#83c) is shot real time, baked and with its sheen. With `reference` (a
    review) the first variant's reference bake follows (reference_variant)."""
    bake = lights["bake"]
    if not grid:
        p = lights["presets"][preset]
        texel = float(lights["zones"][zone][p["lightmap"]])
        tag = preset + ("_m" if merge else "")
        vs = [{"tag": tag, "texel": texel, "bake": dict(bake), "merge": merge}]
        if p.get("sheen"):
            vs[0]["modes"] = ["realtime", "baked", p["sheen"]]
    else:
        vs = [{"tag": variant_tag(t, d, e, merge), "texel": t,
               "bake": {**bake, "denoiser": d, "bounce_indirect_energy": e}, "merge": merge}
              for t in GRID_TEXELS for d in GRID_DENOISER for e in GRID_ENERGIES]
    return vs + [reference_variant(vs[0])] if reference else vs


# The review's light modes (#83b); each row's mode is how bake_shots.gd lights it:
#   realtime         no lightmap, the lights dynamic without shadows (the light kit's real-time lights: they leak
#                    through walls, so this was a wrong reference for a bake)
#   realtime_shadow  no lightmap, the lights dynamic with shadows (direct light only, occluded as the bake occludes)
#   realtime_shadow_nospec  the same with the lights' specular at 0 (diffuse direct light only)
#   baked            the bake's lightmap, the lights static (what the game would ship)
#   hybrid           a bake made with the lights dynamic (its lightmap holds only their bounce) plus the lights in
#                    real time with shadows: Godot's own direct light with Godot's own bounce
#   hybrid_nospec    the same with the lights' specular at 0: what a diffuse lightmap can hold, the bake's reference
MODES = ("realtime", "realtime_shadow", "realtime_shadow_nospec", "baked", "hybrid", "hybrid_nospec")
REFERENCE_MODE = "hybrid_nospec"
REFERENCE_NOTE = "real-time diffuse direct light with shadows plus the bake's own bounce"
# [bake] before #83b (the denoiser on): the before row of the diagnostic run.
BEFORE_83B = {"denoiser": True, "bounce_indirect_energy": 1.5}


def reference_variant(v: dict) -> dict:
    """The reference bake beside a variant: the same settings baked with the lights dynamic (its lightmap holds only
    their bounce), shot as hybrid_nospec."""
    return {**v, "tag": v["tag"] + "_ld", "lights": "dynamic", "modes": [REFERENCE_MODE]}


def diag_variants(lights: dict, zone: str) -> list[dict]:
    """The diagnostic bakes of one zone at its High texel: the chosen settings (denoiser off, bounce energy 1.5),
    the same with no bounce (direct light only), the same with the lights dynamic (bounce only, for the hybrid rows)
    and the default before #83b (BEFORE_83B, the before row). Each: tag, texel, bake, merge, lights, modes. (#83b's
    directional lightmap measured as the base within 0.2 L*: it is not in the run.)"""
    texel = float(lights["zones"][zone]["texel_high"])
    base = {**lights["bake"], "denoiser": False, "bounce_indirect_energy": 1.5}
    tag = variant_tag(texel, False, 1.5)
    old = {**lights["bake"], **BEFORE_83B}
    v = lambda t, b, li, modes: {"tag": t, "texel": texel, "bake": b, "merge": False, "lights": li, "modes": modes}
    return [v(tag, base, "static", ["realtime", "realtime_shadow", "realtime_shadow_nospec", "baked"]),
            v(tag + "_b0", {**base, "bounces": 0}, "static", ["baked"]),
            v(tag + "_ld", base, "dynamic", ["hybrid", "hybrid_nospec"]),
            v(variant_tag(texel, old["denoiser"], old["bounce_indirect_energy"]) + "_old", old, "static", ["baked"])]


# The sheen (#83c): a lightmap holds diffuse light only, so the lamps' specular (the grazing sheen on floors, polished
# furniture and ceilings) comes back on top of the bake. A sheen mode is the baked mode plus any of these tokens,
# joined by "_":
#   lmspec<k>  the directional lightmap's own specular lobe, LightmapGI.specular_intensity k / 10 (needs a bake
#              with directional = true; no real-time light)
#   probes     one ReflectionProbe per room of the zone (update once, interior, box projection, no ambient): it
#              captures the baked rooms and reflects them
#   sheen<n>   the nearest n glow fixtures (to the camera) as real-time lights that add specular only: they light a
#              copy of the lightmapped meshes (render layer 2) whose material is black, additive and without ambient,
#              so their diffuse light is never added twice
#   shadow     with sheen<n>: those lights cast shadows (no sheen through walls)
def sheen_mode(mode: str) -> dict | None:
    """A sheen mode's settings ({"lm_specular", "probes", "n", "shadow"}), or None when `mode` is not one."""
    out = {"lm_specular": 0.0, "probes": False, "n": 0, "shadow": False}
    for p in mode.split("_"):
        m = re.fullmatch(r"(lmspec|sheen)(\d+)|probes|shadow", p)
        if not m:
            return None
        if m.group(1) == "lmspec":
            out["lm_specular"] = int(m.group(2)) / 10
        elif m.group(1) == "sheen":
            out["n"] = int(m.group(2))
        else:
            out[p] = True
    if out["shadow"] and not out["n"]:
        return None
    return out if out["lm_specular"] or out["probes"] or out["n"] else None


def sheen_variants(lights: dict, zone: str) -> list[dict]:
    """The sheen grid of one zone at its High texel (#83c): the default bake (bake only, probes, the specular-only
    real-time lights), the same bake directional (the lightmap's own specular lobe, alone and with probes) and the
    same with the lights dynamic (the `hybrid` reference: every lamp real-time with shadows and specular)."""
    texel = float(lights["zones"][zone]["texel_high"])
    base = {**lights["bake"], "directional": False, "specular_intensity": 0.0}
    tag = variant_tag(texel, base["denoiser"], base["bounce_indirect_energy"])
    v = lambda t, b, li, modes: {"tag": t, "texel": texel, "bake": b, "merge": False, "lights": li, "modes": modes}
    return [v(tag, base, "static", ["baked", "probes", "sheen4_shadow", "sheen12_shadow", "sheen12"]),
            v(tag + "_dir", {**base, "directional": True}, "static", ["lmspec5", "lmspec10", "lmspec10_probes"]),
            v(tag + "_ld", base, "dynamic", ["hybrid"])]


def glow_types(lights: dict) -> list[str]:
    """The fixture types that may get a real-time light (glow = true), sorted."""
    return sorted(t for t, v in lights["types"].items() if v.get("glow"))


def probe_boxes(data: dict, room_ids: list[str], height: float = 3.0) -> list[dict]:
    """One reflection probe box per room: room, centre and size (Godot x, y, z) over the room's rect from its level's
    floor to `height` (the kit's storey wall)."""
    found = {r["id"]: (r["rect"], lv["floor_y"]) for lv in data["levels"] for r in lv["rooms"]}
    out = []
    for rid in room_ids:
        if rid not in found:
            raise ValueError(f"no room {rid}")
        (x, z, w, d), y = found[rid]
        out.append({"room": rid, "center": [x + w / 2, y + height / 2, z + d / 2], "size": [w, height, d]})
    return out


def shot_rows(zone: str, vs: list[dict]) -> list[dict]:
    """The review rows of one zone's variants: label, tag, mode (and a sheen mode's settings as `sheen`). A variant
    without `modes` (the preset and the grid) is shot baked, and the first variant also gives the leaking real-time
    row first."""
    rows = []
    for i, v in enumerate(vs):
        modes = v.get("modes") or (["realtime", "baked"] if i == 0 else ["baked"])
        for mode in modes:
            sheen = None if mode in MODES else sheen_mode(mode)
            if mode not in MODES and sheen is None:
                raise ValueError(f"unknown shot mode {mode}")
            label = f"{zone}_{mode}" if mode.startswith("realtime") else f"{zone}_{v['tag']}_{mode}"
            rows.append({"label": label, "tag": v["tag"], "mode": mode, **({"sheen": sheen} if sheen else {})})
    return rows


def sheet_layout(rows: int, cams: int, width: int = 1280) -> dict:
    """The review sheet about `width` px across: up to four rows one per line, more rows two per line; 16:9 tiles."""
    per_line = 1 if rows <= 4 else 2
    tile_w = width // max(1, cams * per_line)
    return {"tile": [tile_w, tile_w * 9 // 16], "per_line": per_line}


def numbers_md(zone: str, table: dict[str, list[dict]], reference: str | list[str], cam_names: list[str],
               note: str = "real-time diffuse direct light with shadows plus the bake's own bounce",
               extra: dict[str, str] | None = None,
               extra_head: str = "real-time / shadowed lights, draw calls (per camera)") -> str:
    """measures per row label (one dict per camera) as a markdown table: L* mean, dark % and C* p90 per camera, and
    per reference row each other row's L* difference camera by camera and their mean (the first reference: the
    real-time row unless the caller names others); `extra` adds one last column per label (shot_costs)."""
    refs = [reference] if isinstance(reference, str) else list(reference)
    head = ("| row | " + " | ".join(f"{c} L* / dark % / C* p90" for c in cam_names) + " | "
            + " | ".join(f"dL* vs {r} (per camera; mean)" for r in refs) + (f" | {extra_head}" if extra else "")
            + " |")
    lines = [f"# House bake grid: {zone}", "", f"Reference: `{refs[0]}` ({note}).", "", head,
             "|" + "---|" * (len(cam_names) + 1 + len(refs) + (1 if extra else 0))]
    for label, ms in table.items():
        cells = [f"{m['L_mean']} / {m['dark_pct']} / {m['C_p90']}" for m in ms]
        cells += [""] * (len(cam_names) - len(cells))
        for r in refs:
            deltas = [m["L_mean"] - x["L_mean"] for m, x in zip(ms, table.get(r, []))]
            cells.append("" if label == r or not deltas else
                         " / ".join(f"{d:+.1f}" for d in deltas) + f" ({sum(deltas) / len(deltas):+.1f})")
        if extra:
            cells.append(extra.get(label, ""))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def shot_costs(shots: list[dict]) -> dict[str, str]:
    """bake_shots.gd's per-shot stats (row, cam, rt_lights, shadowed, draw_calls) as one cell per row: real-time /
    shadowed lights and draw calls, camera by camera ("4/4, 61; ...")."""
    out: dict[str, list[str]] = {}
    for s in sorted(shots, key=lambda s: (s["row"], s["cam"])):
        out.setdefault(s["row"], []).append(f"{s.get('rt_lights', 0)}/{s.get('shadowed', 0)}, "
                                             f"{int(s.get('draw_calls', 0))}")
    return {k: "; ".join(v) for k, v in out.items()}


def build_args(zone: str, tag: str, texel: float, bake: dict, uv2_json: str, bake_json: str, above: float = 1.0,
               merge: bool = False, lights: str = "static") -> list[str]:
    """The user arguments of zone_build.gd for one zone and preset; lights=dynamic bakes with the lights dynamic (the
    lightmap keeps only their bounce)."""
    if lights not in ("static", "dynamic"):
        raise ValueError(f"lights must be static or dynamic, not {lights}")
    return [f"zone={zone}", f"tag={tag}", f"texel={texel:g}", f"denoiser={int(bool(bake['denoiser']))}",
            f"energy={float(bake['bounce_indirect_energy']):g}", f"bounces={int(bake['bounces'])}", f"above={above:g}",
            f"merge={int(merge)}", f"lights={lights}", f"uv2={uv2_json}", f"bake={bake_json}"]


def e1_cam(rect: list[float], floor_y: float) -> list[float]:
    """The lab's E1 view: from a corner at eye height (1.6 m) across the room to three quarters, 0.9 m up."""
    x, z, w, d = rect
    return [x + 0.8, floor_y + 1.6, z + 0.8, x + w * 0.75, floor_y + 0.9, z + d * 0.75]


def seam_cam(rect: list[float], floor_y: float) -> list[float]:
    """A level view along the room's long middle line from 1 m inside its north wall: the ceiling and the floor tiles
    both in frame (#83a's seam camera stood inside a wall)."""
    x, z, w, d = rect
    return [x + w / 2, floor_y + 1.6, z + 1.0, x + w / 2, floor_y + 1.6, z + d * 0.6]


def views(data: dict, room_ids: list[str]) -> list[list[float]]:
    """E1 cameras of the given rooms, then the first room's seam camera."""
    found = {r["id"]: (r["rect"], lv["floor_y"]) for lv in data["levels"] for r in lv["rooms"]}
    missing = [r for r in room_ids if r not in found]
    if missing:
        raise ValueError(f"no room {', '.join(missing)}")
    return [e1_cam(*found[r]) for r in room_ids] + [seam_cam(*found[room_ids[0]])]


# ---------------------------------------------------------------- frame measures
def read_png(path: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    """An 8-bit RGB or RGBA PNG (any filter, not interlaced) as width, height and RGB pixels."""
    data = Path(path).read_bytes()
    pos, idat, width, height, ch = 8, b"", 0, 0, 3
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", body[:13])
            if depth != 8 or colour not in (2, 6) or interlace:
                raise ValueError(f"{path}: only 8-bit RGB/RGBA, not interlaced")
            ch = 3 if colour == 2 else 4
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    raw = zlib.decompress(idat)
    stride = width * ch
    prev = bytearray(stride)
    px = []
    for y in range(height):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - ch] if i >= ch else 0
            b = prev[i]
            c = prev[i - ch] if i >= ch else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        px.extend((line[i], line[i + 1], line[i + 2]) for i in range(0, stride, ch))
        prev = line
    return width, height, px


def srgb_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """8-bit sRGB -> CIELAB (D65)."""
    def lin(v: int) -> float:
        c = v / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    rl, gl, bl = lin(r), lin(g), lin(b)
    x = (0.4124 * rl + 0.3576 * gl + 0.1805 * bl) / 0.95047
    y = 0.2126 * rl + 0.7152 * gl + 0.0722 * bl
    z = (0.0193 * rl + 0.1192 * gl + 0.9505 * bl) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def measures(width: int, height: int, px: list[tuple[int, int, int]], grid: int = 160) -> dict:
    """The house lab's frame numbers on a grid of about `grid` pixels across: L* mean, the share under L* 20 (dark %)
    and C* p90."""
    step = max(1, width // grid)
    ls, cs = [], []
    for y in range(step // 2, height, step):
        for x in range(step // 2, width, step):
            lum, a, b = srgb_lab(*px[y * width + x])
            ls.append(lum)
            cs.append(math.hypot(a, b))
    cs.sort()
    return {"L_mean": round(sum(ls) / len(ls), 1), "dark_pct": round(100 * sum(v < 20 for v in ls) / len(ls), 1),
            "C_p90": round(cs[min(len(cs) - 1, int(0.9 * len(cs)))], 1)}
