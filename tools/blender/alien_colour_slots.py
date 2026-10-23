"""The alien pilot's static heads (art #196, 2026-10-23): the player's colour slots in the real material, the proof.
Plain Python, outside Blender (the maths: alien_colour_geom.py; the material: godot/alien/alien_static.gdshader and
alien_static.gd's set_colours):
- `regions` (CS6, plain Python): each head's region medians, the recolour's bases (alien_colour_geom.bases_from_texels
  on every second texel of the albedo, skin mask, accent and gill PNGs), into `<out>/maps/<head>_regions.json`, and
  per slot the picked colour against the recoloured albedo at the region's median for MEASURE's colours
  (`albedo_table.json`); the maps are copied from MAPS_FROM when `<out>/maps` has none (CS6 left the masks as v4);
- `masks`: each head's accent mask in headless Blender (alien_tint_mask.py: R lips, G details, B the pale front;
  v3: the whole gills in their own `<head>_gill.png`; the axolotl's smile tail grown into the lips) into
  `<out>/maps/`;
- `sheets`: a job for godot/alien/tint_study.gd on the real shader (its heads' `"static": true`), rendered in an
  off-screen window under the study's studio and dusk lights: the eight presets (the study's E), free picks with
  deliberately bad colours (the guard rails), details off and on, the axolotl's gills as a root-to-tip gradient or whole,
  the lips' corners close up (both corners at front, 3/4 and side, 4x), and the identity check (set_colours({})
  against the merged shader, origin/main's alien_static.gdshader); v3: the import path (the masks imported by Godot
  with the settings in docs/godot.md, IMPORT_SETTINGS, and with Godot's defaults, against Image.load_from_file);
  the pixel diffs into `diffs.json`; the study's E sheets beside v2's presets (`E_compare.jpg`) and the per-cell
  drift (CS6: v4's presets against this run's, `drift.json`); v4: the freckle sheets (`<light>/freckles.jpg`: E2, E5, E7 all round); every cell's uniforms as Godot set them into `uniforms.json`, compared here
  with alien_colour_geom.slot_colours (within 1e-5: float32 against float64); CS6: the details in seven colours
  (`<light>/details_colours.jpg`), the gill tips close up in #ffee00 (`gill_tips.jpg`) and the lit measurement: per
  head and colour every slot in that colour, beside the shader's region codes (debug 4 and 5), into `measure/`, then
  per region the lit median against the pick (`lit_table.json`, `swatches_<head>.png`, `table.md`);
- `web`: the three.js page: the GLBs, masks and bases beside tools/web/alien_colour/{colour.js,index.html} in
  `<out>/web/`.
One run can pass 180 s: in the background, its log in a file.

    $PYTHON_BIN tools/blender/alien_colour_slots.py <regions|masks|sheets|web|all> [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import sys
import textwrap
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner import blender  # noqa: E402
from runner.commands import _godot  # noqa: E402
import alien_colour_geom as G  # noqa: E402
import alien_static_review as R  # noqa: E402
import alien_tint_study as T  # noqa: E402  (the study's lights, framings and head entries)

BUILD = R.NEW  # static_v5
OUT = R.DESIGN / "pilot3d" / "colour_slots" / "v6"  # v6 (CS6): the picks as picked, every region reaching its pick
V = "v6"  # the proof's version in the sheet titles and stems
V4 = R.DESIGN / "pilot3d" / "colour_slots" / "v4"
MAPS_FROM = V4 / "maps"  # CS6 left the masks as v4 made them
# CS6's measurement: 12 hues every 30 degrees, the engineer's yellow, black and white
MEASURE = ["#ff0000", "#ff8000", "#ffff00", "#80ff00", "#00ff00", "#00ff80", "#00ffff", "#0080ff", "#0000ff",
           "#8000ff", "#ff00ff", "#ff0080", "#ffee00", "#000000", "#ffffff"]
DETAILS = ["#ffee00", "#ff8000", "#00ffff", "#ff0000", "#00ff00", "#000000", "#ffffff"]  # the details sheet
# the slots measured: (name, the picks key, the region (bases_from_texels; the shader's debug code), gill mode)
SLOTS = [("skin", "skin", "skin", "gradient"), ("lips", "lips", "lips", "gradient"),
         ("details", "detail", "detail", "gradient"), ("gill tips", "detail", "gill_tips", "gradient"),
         ("whole gills", "detail", "gill_whole", "whole")]
HEADS = T.HEADS
WEB = ROOT / "tools" / "web" / "alien_colour"
MERGED_SHADER_REF = "1aa19cd"  # origin/main when the slots began: the merged alien_static.gdshader
UNIFORM_TOL = 1e-5  # Godot's float32 uniforms against Python's float64 (measured 1.3e-7 in v2)
# The colour slots' masks are data: a Godot import keeps them lossless, linear and whole with these settings (each
# mask's `.import` [params]; docs/godot.md); IMPORT_DIR (ignored by git) holds the proof's imported copies.
IMPORT_SETTINGS = {"compress/mode": 0, "compress/high_quality": False, "compress/lossy_quality": 0.7,
                   "compress/hdr_compression": 1, "compress/normal_map": 0, "compress/channel_pack": 0,
                   "mipmaps/generate": True, "mipmaps/limit": -1, "roughness/mode": 0, "process/fix_alpha_border": False,
                   "process/premult_alpha": False, "process/normal_map_invert_y": False, "process/hdr_as_srgb": False,
                   "process/hdr_clamp_exposure": False, "process/size_limit": 0, "detect_3d/compress_to": 0}
IMPORT_DIR = _godot.PROJECT / "import" / "colour_slots"
IMPORT_MAPS = ("mask", "accent", "gill")
# free picks: the player's own colours, acidic ones on purpose (CS6: shown as picked)
FREE = [("acid green skin, hot pink lips", {"skin": "#39ff14", "lips": "#ff1493"}),
        ("neon green, hot pink lips, yellow details", {"skin": "#39ff14", "lips": "#ff1493", "detail": "#ffff00"}),
        ("hot pink skin", {"skin": "#ff1493"}),
        ("pure yellow, lips the same", {"skin": "#ffff00", "lips": "#ffff00"}),
        ("navy, white lips", {"skin": "#14206e", "lips": "#ffffff", "detail": "#ffffff"}),
        ("orange, cyan details", {"skin": "#ff7a00", "detail": "#00e5ff"}),
        ("mint, rose lips, details off", {"skin": "#b8f0d0", "lips": "#c48a8c", "detail": "#ff0000",
                                          "detail_on": False})]


def bases(build: Path, maps: Path, head: str) -> dict:
    """The build's own colours: the skin from the GLB's build (base_skin_srgb, the face's teal; the painted skin's
    median is within 0.012 OKLab of it), the rest the regions' medians (`<head>_regions.json`, `regions`)."""
    b = json.loads((build / head / "build.json").read_text(encoding="utf-8"))
    med = json.loads((maps / f"{head}_regions.json").read_text(encoding="utf-8"))["bases"]
    return {**{k: v for k, v in med.items() if k != "skin"}, "skin": b["base_skin_srgb"]}


def read_png(path: Path) -> tuple:
    """An 8-bit grey, RGB or RGBA PNG (not interlaced): width, height, channels and the unfiltered bytes."""
    data = Path(path).read_bytes()
    pos, idat = 8, bytearray()
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, colour, _, _, inter = struct.unpack(">IIBBBBB", body[:13])
            if depth != 8 or colour not in (0, 2, 6) or inter:
                raise ValueError(f"{path}: only 8-bit grey/RGB/RGBA, not interlaced")
            ch = {0: 1, 2: 3, 6: 4}[colour]
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    raw, stride = zlib.decompress(bytes(idat)), w * ch
    out, prev, p = bytearray(stride * h), bytearray(stride), 0
    for y in range(h):
        f, line = raw[p], bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 255
        elif f == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif f == 3:
            for i in range(stride):
                line[i] = (line[i] + (((line[i - ch] if i >= ch else 0) + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a, b, c = (line[i - ch] if i >= ch else 0), prev[i], (prev[i - ch] if i >= ch else 0)
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
        out[y * stride:(y + 1) * stride], prev = line, line
    return w, h, ch, out


def write_png(path: Path, w: int, h: int, rgb: bytearray) -> None:
    rows = b"".join(b"\0" + bytes(rgb[y * w * 3:(y + 1) * w * 3]) for y in range(h))
    chunk = lambda k, d: struct.pack(">I", len(d)) + k + d + struct.pack(">I", zlib.crc32(k + d))  # noqa: E731
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
                           chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


def texels(build: Path, maps: Path, head: str, stride: int = 2) -> list:
    """Every stride-th skin texel (skin mask R >= SKIN_GATE): (albedo sRGB 0-1, accent 8-bit RGB, gill 8-bit)."""
    imgs = [read_png(p) for p in (build / head / f"{head}_albedo.png", build / head / f"{head}_mask.png",
                                  maps / f"{head}_accent.png", maps / f"{head}_gill.png")]
    w = imgs[0][0]
    out = []
    for y in range(0, w, stride):
        for x in range(0, w, stride):
            px = [d[(y * w + x) * ch:(y * w + x) * ch + 3] for _, _, ch, d in imgs]
            if px[1][0] >= G.SKIN_GATE:
                out.append((tuple(v / 255 for v in px[0]), tuple(px[2]), px[3][0]))
    return out


def regions(build: Path, out: Path) -> None:
    """The bases (`<head>_regions.json`) and the albedo table: per slot and MEASURE colour the recoloured albedo's
    median over the region against the pick (OKLab delta E)."""
    maps = out / "maps"
    if not (maps / f"{HEADS[0]}_accent.png").exists():
        shutil.copytree(MAPS_FROM, maps, dirs_exist_ok=True)
    table = {}
    for h in HEADS:
        tx = texels(build, maps, h)
        b = G.bases_from_texels(tx)
        n = {k: 0 for k in G.REGIONS}
        by = {k: [] for k in G.REGIONS}
        for t in tx:
            if max(t[0]) >= G.UNPAINTED:
                for k in G.region_of(t[1], t[2]):
                    n[k] += 1
                    by[k].append(t)
        (maps / f"{h}_regions.json").write_text(json.dumps(
            {"head": h, "rules": G.REGIONS, "stride": 2, "texels": n,
             "bases": {k: [round(x, 4) for x in v] for k, v in b.items()},
             "hex": {k: G.hexs(v) for k, v in b.items()}}, indent=1) + "\n", encoding="utf-8", newline="\n")
        bs = bases(build, maps, h)
        rows = []
        for name, key, reg, mode in SLOTS:
            sample = by[reg][::max(1, len(by[reg]) // 4000)]
            if not sample:
                continue
            for col in MEASURE:
                u = G.slot_colours(bs, {key: col, "gills": mode})
                m = G.median_lab([G.texel(c, [v / 255 for v in a], g / 255, u) for c, a, g in sample])
                rows.append({"slot": name, "pick": col, "albedo": G.hexs(m),
                             "dE": round(G.delta_e(m, G.hexc(col)), 4)})
        table[h] = {"bases": {k: G.hexs(v) for k, v in bs.items()}, "texels": n, "rows": rows}
        print(f"regions {h}: {table[h]['bases']}; albedo max dE "
              f"{max(r['dE'] for r in rows):.4f}", flush=True)
    (out / "albedo_table.json").write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8", newline="\n")


def masks(build: Path, out: Path) -> None:
    for h in HEADS:
        blender.run_script("alien_tint_mask.py", ["--head", h, "--build", str(build / h), "--ref",
                                                  str(R.STEP2A / h / "v2" / "build.json"), "--out", str(out / "maps"),
                                                  "--debug"])
        print(f"mask {h}: {(out / 'maps' / f'{h}_accent.json').read_text(encoding='utf-8')}", flush=True)


def title(*parts: str) -> str:
    """A sheet title the window shows whole: each part wrapped at TITLE_CHARS, at most three lines (the strip)."""
    lines = [ln for part in parts for ln in textwrap.wrap(part, TITLE_CHARS)]
    if len(lines) > 3:
        raise ValueError(f"title over three lines: {lines}")
    return "\n".join(lines)


TITLE_CHARS = 64  # tint_study.gd's title strip: 28 px type in the 1000 px window, three lines in 132 px


def corners(head: str) -> dict:
    """The lips' corners close up (4x the sheets' face framing): per corner (L: +x, R: -x) front, 3/4, side."""
    ref = json.loads((R.STEP2A / head / "v2" / "build.json").read_text(encoding="utf-8"))
    cx, cy, cz = ref["lip_line"]["line"][-1]  # (x, up, front), the slit's end; the corner a little past it
    w = T.shots(head)["front"]["width"] / 4.0
    out = {}
    for sx, side in ((1.0, "L"), (-1.0, "R")):
        t = [sx * (cx + 0.15 * w), cy + 0.05 * w, cz - 0.1 * w]
        for view, yaw in (("front", 0.0), ("3/4", 38.0), ("side", 80.0)):
            out[f"{side} {view}"] = {"target": t, "width": w, "yaw": sx * yaw, "pitch": 3.0}
    return out


def freckle_shots() -> dict:
    """The axolotl all round (v4's freckle sheets): the study's front and 3/4, then the side and the back turned
    round the head's middle (the study's orbit point is near the face's front)."""
    f = T.shots("axolotl")
    w = f["front"]["width"]
    t = f["front"]["target"]
    mid = {"target": [t[0], t[1], t[2] - 0.3 * w], "width": 1.1 * w, "pitch": 3.0}
    return {"front": f["front"], "3/4": f["3/4"], "side": {**mid, "yaw": 85.0}, "back": {**mid, "yaw": 180.0}}


def label(picks: dict) -> str:
    return " ".join(f"{k[0]}{v}" if isinstance(v, str) else f"{k}={'on' if v else 'off'}" for k, v in picks.items())


def job(build: Path, out: Path) -> dict:
    j = {"hdri": str(R.HDRI), "window": list(T.WINDOW), "heads": {}, "sheets": [],
         "uniforms": str(out / "uniforms.json"), "diffs": []}
    ref = out / "merged_alien_static.gdshader"
    ref.write_text(subprocess.run(["git", "-C", str(ROOT), "show", f"{MERGED_SHADER_REF}:godot/alien/"
                                   "alien_static.gdshader"], capture_output=True, text=True, check=True).stdout,
                   encoding="utf-8", newline="\n")
    for h in HEADS:
        e = R.head_entry(build, h, f"slots_{h}")
        e["params"] = R.column("F", R.picks(build))  # the static_v5 pick of the alive levers
        e.update(static=True, accent=str(out / "maps" / f"{h}_accent.png"), gill=str(out / "maps" / f"{h}_gill.png"),
                 bases=bases(build, out / "maps", h))
        j["heads"][h] = e
        j["heads"][f"{h}_merged"] = {**e, "static": False, "accent": "", "gill": "", "shader_code": str(ref)}
        for kind in ("set", "default"):  # v3: the masks as a Godot import gives them (the settings, the defaults)
            j["heads"][f"{h}_import_{kind}"] = {**e, **{m: f"res://import/colour_slots/{kind}/{h}_{m}.png"
                                                        for m in IMPORT_MAPS}}

    def cell(head, picks, light, shot, text):
        return {"head": head, "colours": picks, "light": light, "shot": shot, "label": text}

    presets = G.PRESETS
    for light in T.LIGHTS:
        lt = T.LIGHTS[light]
        for part, idx in (("a", range(4)), ("b", range(4, 8))):
            rows = [[cell(h, presets[i][1], light, shot, f"E{i + 1} {presets[i][0]}\n{h} {view}") for i in idx]
                    for h in HEADS for view, shot in T.shots(h).items()]
            j["sheets"].append({"file": str(out / light / f"presets_{part}.jpg"), "cell": [320, 320], "width": 1280,
                                "title": title(f"Presets E{idx[0] + 1}-E{idx[-1] + 1} on the real material ({V})", lt,
                                               "rows: axolotl front, 3/4, chameleon front, 3/4"), "rows": rows})
        rows = [[cell(h, p, light, shot, f"{k + 1} {name}\n{h} {view}") for k, (name, p) in enumerate(FREE)]
                for h in HEADS for view, shot in T.shots(h).items()]
        j["sheets"].append({"file": str(out / light / "free.jpg"), "cell": [256, 256], "width": 1280,
                            "title": title(f"Free picks, acidic on purpose, applied as picked ({V}); the picks in "
                                           "the cells", lt),
                            "rows": rows})
        rows = []
        for h in HEADS:
            row = []
            for i in (1, 4, 6):
                for on in (False, True):
                    row.append(cell(h, {**presets[i][1], "detail_on": on}, light, T.shots(h)["3/4"],
                                    f"E{i + 1} details {'on' if on else 'off'}\n{h} 3/4"))
            rows.append(row)
        j["sheets"].append({"file": str(out / light / "details.jpg"), "cell": [256, 256], "width": 1280,
                            "title": title("Details off (they follow the skin) vs on (their own colour): E2, E5, E7",
                                           lt),
                            "rows": rows})
        # v4: every freckle in the details: the axolotl all round, three contrasting presets
        rows = [[cell("axolotl", presets[i][1], light, shot, f"E{i + 1} {presets[i][0]}\n{view}")
                 for view, shot in freckle_shots().items()] for i in (1, 4, 6)]
        j["sheets"].append({"file": str(out / light / "freckles.jpg"), "cell": [320, 320], "width": 1280,
                            "title": title(f"Freckles ({V}): every freckle on the head in the details colour",
                                           "rows E2, E5, E7; front, 3/4, side, back", lt), "rows": rows})
        rows = []
        for i in (1, 3, 4, 6):
            row = []
            for mode in ("gradient", "whole"):
                for view, shot in T.shots("axolotl").items():
                    row.append(cell("axolotl", {**presets[i][1], "gills": mode}, light, shot,
                                    f"E{i + 1} gills {mode}\n{view}"))
            rows.append(row)
        j["sheets"].append({"file": str(out / light / "gills.jpg"), "cell": [320, 320], "width": 1280,
                            "title": title("Gills: gradient (left pair, default), whole (right pair)",
                                           "rows E2, E4, E5, E7", lt),
                            "rows": rows})
    # the lips' corners close up (v2): both corners at front, 3/4 and side, 4x, three presets, studio
    for head in HEADS:
        rows = []
        for i in (1, 4, 6):
            for side in ("L", "R"):
                rows.append([cell(head, presets[i][1], "studio", shot, f"E{i + 1} {head}\n{name}")
                             for name, shot in corners(head).items() if name.startswith(side)])
        stem = f"lips_{V}" if head == "axolotl" else f"lips_{V}_{head}"
        j["sheets"].append({"file": str(out / f"{stem}.jpg"), "cell": [426, 426], "width": 1280,
                            "title": title(f"The {head}'s lip corners, 4x: L (+x) and R (-x) at front, 3/4, side",
                                           "rows: E2, E5, E7, each L then R; studio"), "rows": rows})
    # CS6: the details in seven colours on both heads (the build's paint first), studio and dusk
    for light in T.LIGHTS:
        rows = [[cell(h, {}, light, T.shots(h)["3/4"], f"build\n{h}")] +
                [cell(h, {"detail": c}, light, T.shots(h)["3/4"], f"details {c}\n{h}") for c in DETAILS]
                for h in HEADS]
        rows += [[cell(h, {}, light, T.shots(h)["front"], f"build\n{h} front")] +
                 [cell(h, {"detail": c}, light, T.shots(h)["front"], f"details {c}\n{h} front") for c in DETAILS]
                 for h in HEADS]
        j["sheets"].append({"file": str(out / light / "details_colours.jpg"), "cell": [160, 160], "width": 1280,
                            "title": title(f"Details ({V}): build #ffee00 orange cyan red green black white",
                                           "rows: axolotl, chameleon 3/4, then front", T.LIGHTS[light]),
                            "rows": rows})
    # CS6: the gill tips close up in #ffee00, gradient and whole, with the build's paint for reference
    gs = {k: v for k, v in freckle_shots().items() if k in ("3/4", "side", "back")}
    rows = [[cell("axolotl", p, "studio", shot, f"{name}\n{view}") for view, shot in gs.items()]
            for name, p in (("build", {}), ("#ffee00 gradient", {"detail": "#ffee00", "gills": "gradient"}),
                            ("#ffee00 whole", {"detail": "#ffee00", "gills": "whole"}))]
    j["sheets"].append({"file": str(out / "gill_tips.jpg"), "cell": [426, 426], "width": 1280,
                        "title": title(f"Gill tips, details #ffee00 ({V}): rows the build, gradient, whole",
                                       "3/4, side, back; studio"), "rows": rows})
    # CS6: the lit measurement: per head, shot and gill mode the region codes (debug 4, 5), then every MEASURE
    # colour on every slot at once (a region's median against the pick; regions.json's rules in the shader)
    for h in HEADS:
        for mode in (("gradient", "whole") if h == "axolotl" else ("gradient",)):
            for view in ("front", "3/4"):
                shot, tag = T.shots(h)[view], f"{h}_{mode}_{view.replace('/', '')}"
                row = [{**cell(h, {"detail_on": True, "gills": mode}, "studio", shot, ""), "debug": d,
                        "save": str(out / "measure" / f"{tag}_code{d}.png")} for d in (4, 5)]
                row += [{**cell(h, {"skin": c, "lips": c, "detail": c, "gills": mode}, "studio", shot, ""),
                         "save": str(out / "measure" / f"{tag}_{c[1:]}.png")} for c in MEASURE]
                j["sheets"].append({"file": str(out / "measure" / f"{tag}.jpg"), "cell": [320, 320], "width": 1280,
                                    "title": title(f"Measure {h} {view} gills {mode} ({V}): the region codes, then "
                                                   "every slot in each colour", "studio"),
                                    "rows": [row[i:i + 4] for i in range(0, len(row), 4)]})
    # the identity: set_colours({}) on the new material against the merged shader, the same levers and light
    rows = []
    for h in HEADS:
        row = []
        for view, shot in T.shots(h).items():
            for key, name in ((f"{h}_merged", "merged"), (h, "slots {}")):
                tag = f"{h}_{view.replace('/', '')}_{name.split()[0]}"
                # the same label on both: the label is drawn in the window, so it is in the grab
                row.append({**cell(key, {}, "studio", shot, f"identity\n{h} {view}"),
                            "save": str(out / "identity" / f"{tag}.png")})
            j["diffs"].append([str(out / "identity" / f"{h}_{view.replace('/', '')}_merged.png"),
                               str(out / "identity" / f"{h}_{view.replace('/', '')}_slots.png")])
        rows.append(row)
    j["sheets"].append({"file": str(out / "identity.jpg"), "cell": [320, 320], "width": 1280,
                        "title": title("Identity: per pair the merged shader (left) and the slots material with "
                                       "no picks (right), studio; pixel diff in identity.json"), "rows": rows})
    # v3: the import path: the masks imported by Godot (the shipped settings; Godot's defaults) against
    # Image.load_from_file, E5 cobalt with the whole gills (every mask channel in play), studio
    rows = []
    for h in HEADS:
        row = []
        for view, shot in T.shots(h).items():
            # the same label on all three (drawn in the window, so in the grab): the title gives the column order
            for key, name in ((h, "file"), (f"{h}_import_set", "import"), (f"{h}_import_default", "default")):
                tag = f"import_{h}_{view.replace('/', '')}_{name}"
                row.append({**cell(key, {**presets[4][1], "gills": "whole"}, "studio", shot,
                                   f"E5 whole gills\n{h} {view}"), "save": str(out / "identity" / f"{tag}.png")})
            for name in ("import", "default"):
                j["diffs"].append([str(out / "identity" / f"import_{h}_{view.replace('/', '')}_file.png"),
                                   str(out / "identity" / f"import_{h}_{view.replace('/', '')}_{name}.png")])
        rows.append(row)
    j["sheets"].append({"file": str(out / "import.jpg"), "cell": [213, 213], "width": 1280,
                        "title": title("Import path: masks from Image.load_from_file, a Godot import with the "
                                       "shipped settings, Godot's defaults (E5, whole gills); diffs.json"),
                        "rows": rows})
    j["diff_out"] = str(out / "diffs.json")
    # v3: the study's E sheets (linear HSV, raw picks) beside v2's presets, and the drift per cell
    # CS6: v4's presets (HSV recolour, one detail base) beside this run's, and the drift per cell
    j["stacks"] = [{"file": str(out / "presets_compare.jpg"), "width": 1280,
                    "rows": [[str(V4 / "studio" / f"presets_{p}.jpg"), str(out / "studio" / f"presets_{p}.jpg")]
                             for p in ("a", "b")]}]
    j["drifts"] = [{"a": str(V4 / light / f"presets_{p}.jpg"), "b": str(out / light / f"presets_{p}.jpg"),
                    "top": 168, "cell": [320, 320], "label": 40} for light in T.LIGHTS for p in ("a", "b")]
    j["drift_out"] = str(out / "drift.json")
    return j


def import_maps(build: Path, out: Path) -> None:
    """The proof's imported masks: per head the skin mask, accent and gill PNGs copied into IMPORT_DIR/set with
    IMPORT_SETTINGS in their `.import` files and into IMPORT_DIR/default with none (Godot's defaults)."""
    for kind in ("set", "default"):
        d = IMPORT_DIR / kind
        d.mkdir(parents=True, exist_ok=True)
        for h in HEADS:
            for m in IMPORT_MAPS:
                src = build / h / f"{h}_mask.png" if m == "mask" else out / "maps" / f"{h}_{m}.png"
                shutil.copy2(src, d / f"{h}_{m}.png")
                imp = d / f"{h}_{m}.png.import"
                if kind == "set":
                    params = "\n".join(f"{k}={json.dumps(v)}" if not isinstance(v, bool) else
                                        f"{k}={'true' if v else 'false'}" for k, v in IMPORT_SETTINGS.items())
                    imp.write_text(f'[remap]\n\nimporter="texture"\ntype="CompressedTexture2D"\n\n[params]\n\n'
                                   f"{params}\n", encoding="utf-8", newline="\n")
                elif imp.exists():
                    imp.unlink()


def check_uniforms(out: Path, j: dict) -> float:
    """Godot's set_colours against alien_colour_geom.slot_colours on every cell: the largest channel difference."""
    got = json.loads((out / "uniforms.json").read_text(encoding="utf-8"))
    worst = 0.0
    for rec in got:
        b = j["heads"][rec["head"]].get("bases")
        if not b:
            continue
        want = G.slot_colours(b, rec["picks"])
        for k, v in want.items():
            g = rec["uniforms"][k]
            vv = v if isinstance(v, tuple) else (v,)
            gg = g if isinstance(g, list) else [g]
            worst = max(worst, max(abs(x - y) for x, y in zip(vv, gg)))
    print(f"uniforms: {len(got)} cells, Godot vs Python max |diff| {worst:.2e}", flush=True)
    return worst


def lit_table(out: Path) -> dict:
    """Per head, gill mode, shot and slot: the lit region's median (sRGB, OKLab per component) in the measure cells
    against the pick; a pixel counts in a region when debug 4 shows its code, debug 5 the inverse (the background
    equal in both), and its four neighbours share the code."""
    codes = {"skin": (1, 1, 0), "lips": (1, 0, 0), "detail": (0, 1, 0)}
    res = {}
    for h in HEADS:
        for mode in (("gradient", "whole") if h == "axolotl" else ("gradient",)):
            for view in ("front", "3/4"):
                tag = f"{h}_{mode}_{view.replace('/', '')}"
                w, hh, ch, c4 = read_png(out / "measure" / f"{tag}_code4.png")
                c5 = read_png(out / "measure" / f"{tag}_code5.png")[3]

                def code(i):
                    a, b = c4[i * ch:i * ch + 3], c5[i * ch:i * ch + 3]
                    if sum(abs(x - y) for x, y in zip(a, b)) < 200:
                        return None
                    bits = tuple(1 if v > 150 else (0 if v < 90 else -1) for v in a)
                    return bits if -1 not in bits else None
                cls = [code(i) for i in range(w * hh)]
                masks = {}
                for k, cv in codes.items():
                    masks[k] = [i for i in range(w + 1, w * hh - w - 1) if cls[i] == cv and cls[i - 1] == cv and
                                cls[i + 1] == cv and cls[i - w] == cv and cls[i + w] == cv]
                for col in MEASURE:
                    _, _, chl, lit = read_png(out / "measure" / f"{tag}_{col[1:]}.png")
                    for k, idx in masks.items():
                        if len(idx) < 30 or (k != "detail" and mode == "whole"):
                            continue
                        slot = {"detail": "gill tips" if mode == "gradient" and h == "axolotl" else "details",
                                "skin": "skin", "lips": "lips"}[k]
                        if mode == "whole":
                            slot = "whole gills"
                        m = G.median_lab([tuple(lit[i * chl + c] / 255 for c in range(3)) for i in idx])
                        res.setdefault(h, []).append({"slot": slot, "view": view, "pick": col, "lit": G.hexs(m),
                                                      "px": len(idx), "dE": round(G.delta_e(m, G.hexc(col)), 4)})
    (out / "lit_table.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    return res


def swatches(out: Path, lit: dict) -> None:
    """Per head a swatch sheet (`swatches_<head>.png`): rows MEASURE's colours, per slot (SLOTS' order) three
    swatches: the pick, the recoloured albedo at the region (albedo_table.json), the lit region (3/4, lit_table.json);
    `table.md` the same in numbers."""
    alb = json.loads((out / "albedo_table.json").read_text(encoding="utf-8"))
    md = [f"# CS6 ({V}): picked colour vs rendered region", "",
          "Per slot: the pick, the recoloured albedo's median over the region (before light) and the lit region's "
          "median in Godot (studio, 3/4; tonemapped, so never equal), with OKLab delta E to the pick.", ""]
    for h in HEADS:
        slots = [s[0] for s in SLOTS if any(r["slot"] == s[0] for r in alb[h]["rows"])]
        sw, gap = 40, 12
        w = len(slots) * (3 * sw + gap) + gap
        hh = len(MEASURE) * sw
        img = bytearray([24, 24, 24] * (w * hh))
        md += [f"## {h}", "", "| slot | pick | albedo | dE | lit 3/4 | dE | lit front | dE |", "|---|---|---|---|---|---|---|---|"]
        for si, s in enumerate(slots):
            for ri, col in enumerate(MEASURE):
                a = next(r for r in alb[h]["rows"] if r["slot"] == s and r["pick"] == col)
                ls = {r["view"]: r for r in lit.get(h, []) if r["slot"] == s and r["pick"] == col}
                cells = [col, a["albedo"], ls["3/4"]["lit"] if "3/4" in ls else "#181818"]
                for k, hx in enumerate(cells):
                    c = G.hexc(hx)
                    x0 = gap + si * (3 * sw + gap) + k * sw
                    for y in range(ri * sw + 2, (ri + 1) * sw - 2):
                        for x in range(x0 + 1, x0 + sw - 1):
                            img[(y * w + x) * 3:(y * w + x) * 3 + 3] = bytes(round(v * 255) for v in c)
                lit_s = " | ".join(f"{ls[v]['lit']} | {ls[v]['dE']:.3f}" if v in ls else "- | -" for v in ("3/4", "front"))
                md.append(f"| {s} | {col} | {a['albedo']} | {a['dE']:.4f} | {lit_s} |")
        write_png(out / f"swatches_{h}.png", w, hh, img)
        md += ["", f"`swatches_{h}.png`: rows {', '.join(MEASURE)}; per slot ({', '.join(slots)}) the pick, the "
               "albedo, the lit 3/4.", ""]
    (out / "table.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")


def sheets(build: Path, out: Path, only: str = "") -> int:
    for d in [*T.LIGHTS, "identity", "measure"]:
        (out / d).mkdir(parents=True, exist_ok=True)
    j = job(build, out)
    if only:  # sheets by stem (e.g. "identity"); each sheet's diffs only with it (identity, import)
        stems = only.split(",")
        j["sheets"] = [s for s in j["sheets"] if Path(s["file"]).stem in stems]
        j["diffs"] = [d for d in j["diffs"] if ("import" if Path(d[1]).name.startswith("import_") else "identity")
                      in stems]
    import_maps(build, out)
    _godot.import_project()
    path = out / "job.json"
    path.write_text(json.dumps(j, indent=1), encoding="utf-8", newline="\n")
    code, _ = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/tint_study.gd", "--", str(path)],
                            T.WINDOW, 900, log=out / "godot.log")
    print(f"sheets: exit {code}", flush=True)
    if code == 0 and j["diffs"]:
        print(f"diffs: {(out / 'diffs.json').read_text(encoding='utf-8')}", flush=True)
    if code == 0 and check_uniforms(out, j) > UNIFORM_TOL:
        return 5
    if code == 0 and (out / "measure" / f"{HEADS[0]}_gradient_34_code4.png").exists():
        swatches(out, lit_table(out))
        print(f"lit: {out / 'table.md'}", flush=True)
    return code


def web(build: Path, out: Path) -> None:
    d = out / "web"
    d.mkdir(parents=True, exist_ok=True)
    heads = {}
    for h in HEADS:
        shutil.copy2(build / h / f"{h}_static.glb", d / f"{h}_static.glb")
        shutil.copy2(out / "maps" / f"{h}_accent.png", d / f"{h}_accent.png")
        shutil.copy2(out / "maps" / f"{h}_gill.png", d / f"{h}_gill.png")
        shutil.copy2(build / h / f"{h}_mask.png", d / f"{h}_mask.png")
        heads[h] = bases(build, out / "maps", h)
    (d / "heads.json").write_text(json.dumps(heads, indent=1) + "\n", encoding="utf-8", newline="\n")
    for f in ("colour.js", "index.html"):
        shutil.copy2(WEB / f, d / f)
    print(f"web: {d}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["regions", "masks", "sheets", "web", "all"])
    ap.add_argument("--build", type=Path, default=BUILD)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--only", default="", help="sheets by stem, comma-separated (default: all)")
    args = ap.parse_args()
    if args.what == "masks":  # CS6: "all" keeps v4's masks (MAPS_FROM); `masks` remakes them in Blender
        masks(args.build, args.out)
    if args.what in ("regions", "all"):
        regions(args.build, args.out)
    if args.what in ("web", "all"):
        web(args.build, args.out)
    if args.what in ("sheets", "all"):
        return sheets(args.build, args.out, args.only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
