"""Gate 2's checks on a garment build (art #196; docs/clothes.md, "Gate 2"; the ADR 2026-10-31-asset-pipeline-gates):
plain Python, with headless Blender for the build's rest dump and its motion numbers. From the garment's spec
(specs/<garment>_dims.toml and its [gate2] section) and a dressed build it writes into OUT:

1. the spec numbers: every spec size measured on the build (garment_drawing.measure_build), within its tol_cm;
2. the silhouettes: per view (front, side, back) the build's garment drawn at the concept's scale by her landmark
   rows (the legs moved to the concept's leg lines, as the drawing does), over the concept's garment mask (a colour
   rule and morphology, garment_gate2_geom.concept_mask, or a hand mask `mask_<view>` in [gate2]); the overlap
   (intersection over union) against overlap_min, the stations' table (concept | spec | build, mm), overlay_<view>.png;
3. the motion numbers per clip (garment_motion.py): slip at the named joins, the flatness of the flat parts (change
   from rest), the stretch of edges, and the pokes from clothes_proof.py's poke.json, each against its tolerance;
4. the review page: index.html with concept | drawing | build at one scale per view (garment_drawing.view_sheet on the
   build), the overlays, the tables, and the close-up Walk and Jog videos (`frames --video-camera`, copied in);
   gate2.json and gate2.md; the verdict: PASS only when every number is measured and within its tolerance.

    tools/run.sh gate2 --spec specs/dungarees_dims.toml --body <char probe.json> --blend <dressed .blend>
        [--dress <dress.json>] --poke <poke.json> --out DIR [--probe P] [--motion M] [--video DIR] [--tag d79]
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import body_dims_geom as BG
import body_drawing as D
import garment_drawing as GD
import garment_gate2_geom as G
import garment_spec as S

VIEWS = ("front", "side", "back")
BUILD_MESH = "garment"
OK_C, BAD_C, NA_C = (40, 130, 60), (200, 30, 30), (120, 120, 120)


# --- 1. the spec numbers -----------------------------------------------------------------------------------------

def spec_numbers(spec, build_probe, sec) -> tuple[dict, list]:
    meas = GD.measure_build(spec, build_probe, sec)
    _md, rows = GD.table(spec, meas, "build")
    return meas, rows


# --- 2. the silhouettes ------------------------------------------------------------------------------------------

def leg_shift(spec, sec, view: str):
    """u shift (cm) of a build point under the crotch onto the concept's leg line (front and back views)."""
    c, lm = spec["concept"], spec["body"]["landmarks_cm"]
    if view == "side":
        return lambda u, z: 0.0
    zs = (lm["crotch"] - 3, lm["knee"], spec["dims"]["hem_z"]["cm"])
    offs = [o / c["px_per_cm"] for o in c["leg_cx_px"][view]]
    cache = {}

    def legc(z):
        if z >= zs[0]:
            return offs[0]
        if z >= zs[1]:
            return offs[1] + (offs[0] - offs[1]) * (z - zs[1]) / (zs[0] - zs[1])
        return offs[2] + (offs[1] - offs[2]) * max(0.0, z - zs[2]) / (zs[1] - zs[2])

    def hers(z):
        k = round(z * 2) / 2
        if k not in cache:
            cache[k] = GD.leg_centre(sec, k)
        return cache[k]

    def f(u, z):
        w = min(1.0, max(0.0, (lm["crotch"] - z) / 3.0))
        if w == 0.0 or u == 0:
            return 0.0
        s = 1.0 if u > 0 else -1.0
        return s * w * (legc(z) - hers(z))
    return f


def build_mask(spec, probe, sec, view: str):
    """The build's garment as seen in the view (z-buffered against her body, the shirt and the shoes), at the
    concept's scale by her landmark rows, in the view's box."""
    box = spec["concept"]["boxes"][view]
    w, h = box[2] - box[0], box[3] - box[1]
    tf, shift = GD.concept_map(spec, view), leg_shift(spec, sec, view)
    depth, owner = [1e9] * (w * h), bytearray(w * h)
    for m in probe["meshes"]:
        pts = []
        for v in m["vertices"]:
            u, z, d = GD.project(v, view)
            col, row = tf(u + shift(u, z), z)
            pts.append((col - box[0], row - box[1], d))
        G.raster([(pts[t[0]], pts[t[1]], pts[t[2]]) for t in m["tris"]], w, h, depth, owner,
                 1 if m["name"] == BUILD_MESH else 2)
    return w, h, bytearray(1 if o == 1 else 0 for o in owner)


def concept_garment(spec, rows, view: str, out: Path, base: Path = Path(".")):
    g2 = spec["gate2"]
    box = spec["concept"]["boxes"][view]
    hand = g2.get(f"mask_{view}")
    if hand:   # a hand-painted mask, the box's size: any non-black pixel is garment; a relative path from the spec's folder
        path = Path(hand) if Path(hand).is_absolute() else base / hand
        if not path.is_file():
            raise SystemExit(f"gate2.mask_{view}: no file {path.as_posix()}")
        w, h, mrows = BG.read_png(path)
        if (w, h) != (box[2] - box[0], box[3] - box[1]):
            raise SystemExit(f"gate2.mask_{view}: {w} x {h} px, but the {view} box is {box[2] - box[0]} x {box[3] - box[1]}")
        return w, h, bytearray(1 if sum(p[:3]) > 0 else 0 for r in mrows for p in r)
    w, h, m = G.concept_mask(rows, box, g2["concept_mask"])
    cv = D.Canvas(w, h, bg=(0, 0, 0))
    for i, v in enumerate(m):
        if v:
            cv.px[3 * i:3 * i + 3] = b"\xff\xff\xff"
    cv.save(out / f"concept_mask_{view}.png")
    return w, h, m


def check_gate2(spec) -> list[str]:
    """The [gate2] section's cross-references that do not resolve: every expression (parts, stations, classify,
    overlap_z), every station's dim, view and kind, every part a join, flat or stretch names (empty when sound)."""
    g2, lm, dims = spec["gate2"], spec["body"]["landmarks_cm"], spec["dims"]
    bad = []

    def expr(where, e):
        try:
            G.resolve(e, {}, dims, lm)
        except (ValueError, KeyError) as err:
            bad.append(f"{where}: {err}")
    for name, p in g2["parts"].items():
        for key in ("x_abs", "y", "z"):
            for e in p[key]:
                expr(f"parts.{name}.{key}", e)
    expr("classify.over_z", g2["classify"]["over_z"])
    for v, zs in g2.get("overlap_z", {}).items():
        for e in zs:
            expr(f"overlap_z.{v}", e)
    for v in g2.get("overlap_min", {}):
        if v not in VIEWS:
            bad.append(f"overlap_min: no view {v!r}")
    for st in g2.get("stations", []):
        where = f"stations '{st.get('name')}'"
        if st.get("view") not in VIEWS:
            bad.append(f"{where}: no view {st.get('view')!r}")
        if st.get("kind") not in ("top", "bottom", "width", "front", "back"):
            bad.append(f"{where}: no kind {st.get('kind')!r}")
        if "dim" in st and st["dim"] not in dims:
            bad.append(f"{where}: dim {st['dim']!r} is no spec size")
        if "dim" not in st and "concept_tol_cm" not in st:
            bad.append(f"{where}: neither a dim nor a concept_tol_cm")
        for e in (st["z"] if isinstance(st["z"], list) else [st["z"]]):
            expr(where, e)
    for j in g2.get("joins", []):
        for key in ("moving", "on"):
            if j[key] not in g2["parts"]:
                bad.append(f"joins '{j['name']}': {key} {j[key]!r} is no part")
    for key in ("flat", "stretch"):
        for f in g2.get(key, []):
            if f["part"] not in g2["parts"]:
                bad.append(f"{key}: {f['part']!r} is no part")
    return bad


def build_of(path, sha: str | None, what: str) -> None:
    """Refuse a dump or a motion result made from another build than the --blend (its blend_sha256)."""
    if sha is None:
        return
    got = json.loads(Path(path).read_text(encoding="utf-8")).get("blend_sha256")
    if got != sha:
        raise SystemExit(f"{what} {Path(path).as_posix()} is not of this build: its blend_sha256 is "
                         f"{got or 'missing (made before build ids: make it again)'}, the --blend's {sha[:12]}...")


def video_source(video: Path, blend: Path | None, sha: str | None) -> tuple[bool, str]:
    """Whether the videos in `video` are this build's close-ups: frames' spec.json has the --video-camera shot and its
    source GLB is unchanged (its SHA-256) and of this build (the .blend's hash, or the GLB beside the .blend with its
    name)."""
    sp = video / "spec.json"
    if not sp.is_file():
        return False, f"no {sp.as_posix()}"
    vs = json.loads(sp.read_text(encoding="utf-8"))
    if not vs.get("video_camera"):
        return False, "made without --video-camera (the whole-body camera)"
    src = vs.get("source")
    if not src:
        return False, "spec.json has no source (made before build ids: make the videos again)"
    if blend is None or sha is None:
        return False, "no --blend to check the videos' build against"
    glb = Path(src["glb"])
    if not glb.is_file() or G.file_sha256(glb) != src["glb_sha256"]:
        return False, f"the GLB {glb.as_posix()} changed or is gone since the videos"
    if src.get("blend_sha256") == sha or (glb.parent.resolve() == blend.parent.resolve() and glb.stem == blend.stem):
        return True, f"from {glb.as_posix()} ({src['glb_sha256'][:12]}), this build"
    return False, f"from {glb.as_posix()}, another build than {blend.as_posix()}"


def stations(spec, view, cm, bm, w, h, meas) -> list[dict]:
    """The view's stations: the concept's and the build's value in cm, the spec's, the errors."""
    c, lm, dims = spec["concept"], spec["body"]["landmarks_cm"], spec["dims"]
    pairs = S.concept_pairs(spec)
    box, k = c["boxes"][view], c["px_per_cm"]
    cx = c["side_mid_x"] if view == "side" else (c["front_cx"] if view == "front" else c["back_cx"])
    u_off = c["side_mid_y_cm"] if view == "side" else 0.0
    to_col = lambda u: int(round(cx + (u - u_off) * k)) - box[0]
    to_u = lambda col: u_off + (col + box[0] + 0.5 - cx) / k
    to_row = lambda z: int(round(GD.concept_map(spec, view)(0, z)[1])) - box[1]
    to_z = lambda row: S.concept_row_to_z(pairs, row + box[1] + 0.5)
    res = []
    for st in spec["gate2"]["stations"]:
        if st["view"] != view:
            continue
        r = lambda e: G.resolve(e, {}, dims, lm)
        c0, c1 = to_col(st["u"][0]), to_col(st["u"][1])
        c0, c1 = min(c0, c1), max(c0, c1)
        vals = []
        for m in (cm, bm):
            if st["kind"] in ("top", "bottom"):
                r0, r1 = sorted((to_row(r(st["z"][1])), to_row(r(st["z"][0]))))
                y = G.top_row(m, w, h, c0, c1, r0, r1, bottom=st["kind"] == "bottom")
                vals.append(None if y is None else to_z(y - 0.5 if st["kind"] == "top" else y + 0.5))
            else:
                e = G.edges(m, w, h, to_row(r(st["z"])), c0, c1)
                if e is None:
                    vals.append(None)
                elif st["kind"] == "width":
                    vals.append((e[1] - e[0] + 1) / k)
                else:
                    vals.append(to_u(e[0] - 0.5) if st["kind"] == "front" else to_u(e[1] + 0.5))
        d = dims.get(st.get("dim", ""), None)
        spec_cm = d["cm"] if d else None
        tol = d["tol_cm"] if d else st.get("concept_tol_cm", 1.0)
        ref = spec_cm if spec_cm is not None else vals[0]
        err = None if vals[1] is None or ref is None else (vals[1] - ref) * 10
        res.append({"view": view, "name": st["name"], "kind": st["kind"], "dim": st.get("dim"),
                    "concept_cm": None if vals[0] is None else round(vals[0], 2), "spec_cm": spec_cm,
                    "build_cm": None if vals[1] is None else round(vals[1], 2),
                    "against": "spec" if spec_cm is not None else "concept",
                    "err_mm": None if err is None else round(err, 1),
                    "build_vs_concept_mm": None if None in vals else round((vals[1] - vals[0]) * 10, 1),
                    "tol_mm": round(tol * 10, 1), "pass": None if err is None else abs(err) <= tol * 10})
    return res


def overlay(spec, rows, view, cm, bm, w, h, sts, iou, out: Path) -> Path:
    """The concept faded, its garment blue, the build's red, both green; the stations' rows ticked."""
    box = spec["concept"]["boxes"][view]
    top = 40
    cv = D.Canvas(w, h + top)
    for y in range(h):
        src = rows[box[1] + y]
        for x in range(w):
            i = y * w + x
            a, b = cm[i], bm[i]
            p = src[box[0] + x]
            g = (p[0] + p[1] + p[2]) // 3
            base = (int(244 * 0.6 + g * 0.4),) * 3
            col = (60, 170, 70) if a and b else (40, 90, 220) if a else (220, 50, 40) if b else base
            j = 3 * ((y + top) * w + x)
            cv.px[j:j + 3] = bytes(col)
    cv.text(6, 4, f"{view.upper()}  IOU {iou['iou']:.3f}", k=2)
    cv.text(6, 22, "GREEN BOTH  BLUE CONCEPT ONLY  RED BUILD ONLY", k=1)
    tf = GD.concept_map(spec, view)
    for s in sts:
        st = next(x for x in spec["gate2"]["stations"] if x["view"] == view and x["name"] == s["name"])
        lm, dims = spec["body"]["landmarks_cm"], spec["dims"]
        zs = [s["concept_cm"], s["build_cm"]] if s["kind"] in ("top", "bottom") else [G.resolve(st["z"], {}, dims, lm)]
        for z, colr in zip(zs, (D.RING, D.DIM)):
            if z is None:
                continue
            y = top + tf(0, z)[1] - box[1]
            cv.line((0, y), (14, y), colr, 0)
            cv.line((w - 15, y), (w - 1, y), colr, 0)
    return cv.save(out)


# --- 3. motion ---------------------------------------------------------------------------------------------------

def motion_config(spec, meas, blend: str) -> dict:
    g2, lm, dims = spec["gate2"], spec["body"]["landmarks_cm"], spec["dims"]
    r = lambda e: G.resolve(e, meas, dims, lm) / 100
    parts = {}
    for name, p in g2["parts"].items():
        parts[name] = {"classes": p["classes"], "x_abs": [r(v) for v in p["x_abs"]], "y": [r(v) for v in p["y"]],
                       "z": [r(v) for v in p["z"]]}
    return {"blend": blend, "clips": g2["clips"], "parts": parts, "reference_clip": g2.get("reference_clip"),
            "classify": {"over_z": r(g2["classify"]["over_z"]), "hardware_max_verts": g2["classify"]["hardware_max_verts"]},
            "joins": [{**j, "reach_m": j["reach_mm"] / 1000} for j in g2["joins"]],
            "flat": g2["flat"], "stretch": g2["stretch"]}


def motion_rows(spec, motion: dict, poke: dict | None) -> list[dict]:
    """One row per part (its vertices: a part with none fails) and per clip and check: value, tolerance, pass."""
    g2, rows = spec["gate2"], []
    parts = motion.get("parts") or {}
    for name in g2["parts"]:
        n = (parts.get(name) or {}).get("verts")
        rows.append({"clip": "rest", "check": f"part found: {name} (vertices)", "value": n, "unit": "verts",
                     "tol": 1, "pass": None if n is None else n > 0})
    for clip in g2["clips"]:
        m = (motion.get("clips") or {}).get(clip)
        for j in g2["joins"]:
            v = None if m is None else m["slip_mm"].get(j["name"])
            rows.append({"clip": clip, "check": f"slip: {j['name']}", "value": v, "unit": "mm", "tol": j["tol_mm"],
                         "pass": G.verdict(v, j["tol_mm"])})
        for f in g2["flat"]:
            v = None if m is None else m["flat_mm"].get(f["part"])
            rows.append({"clip": clip, "check": f"flatness: {f['part']}", "value": v, "unit": "mm", "tol": f["tol_mm"],
                         "pass": G.verdict(v, f["tol_mm"])})
        for s in g2["stretch"]:
            mx = None if m is None else m["stretch_pct"].get(s["part"])
            v = None if m is None else m["stretch_p95_pct"].get(s["part"])   # judged: one torn edge shows in the max
            rows.append({"clip": clip, "check": f"stretch p95: {s['part']} (max {mx})", "value": v, "unit": "%",
                         "tol": s["tol_pct"], "pass": G.verdict(v, s["tol_pct"])})
        pk = None if poke is None else (poke.get("clips") or {}).get(clip)
        v = None if pk is None else pk.get("max_count")
        depth = None if pk is None else round(1000 * pk.get("max_depth_m", 0.0), 1)
        rows.append({"clip": clip, "check": f"pokes (deepest {depth} mm)", "value": v, "unit": "verts",
                     "tol": g2["pokes"]["max_count"], "pass": G.verdict(v, g2["pokes"]["max_count"])})
    return rows


# --- 4. the page -------------------------------------------------------------------------------------------------

def _cell(v):
    return "-" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))


def _pass(p):
    return '<td class="na">unmeasured</td>' if p is None else ('<td class="ok">yes</td>' if p else '<td class="bad">NO</td>')


def page(tag, spec, nums, sil, mrows, videos, verdict, out: Path) -> Path:
    css = ("body{font:14px sans-serif;background:#f4f1e8;color:#1e2a36;margin:20px}img{max-width:100%;border:1px solid "
           "#bbb}table{border-collapse:collapse;margin:8px 0 24px}td,th{border:1px solid #bbb;padding:2px 8px;"
           "text-align:right}td:first-child,th:first-child{text-align:left}.ok{color:#287f3c}.bad{color:#c81e1e;"
           "font-weight:bold}.na{color:#888}.row{display:flex;gap:12px;align-items:flex-start}video{width:480px}")
    h = [f"<!doctype html><meta charset=utf-8><title>Gate 2: {spec['garment']['id']} {tag}</title><style>{css}</style>",
         f"<h1>Gate 2: {spec['garment']['id']} - build {tag} - {'PASS' if verdict['pass'] else 'NOT PASSED'}</h1>",
         f"<p>{verdict['summary']}</p>", "<h2>Concept | drawing over the concept | build with the spec's lines, one scale</h2>"]
    for v in VIEWS:
        h.append(f"<h3>{v}</h3><div class=row><img src='sheet_{v}.png' style='max-width:75%'>"
                 f"<img src='overlay_{v}.png' style='max-width:24%'></div>")
    h.append("<h2>Close-up in motion (front, the torso, carried with the Chest)</h2><div class=row>")
    for name in ("Walk", "Jog_Fwd"):
        src = videos.get(name)
        h.append(f"<div><b>{name}</b><br>" + (f"<video src='{src}' controls loop autoplay muted></video>" if src
                                              else "<i>no video: run frames --video-camera</i>") + "</div>")
    h.append("</div><h2>Silhouette overlap and stations</h2><table><tr><th>view</th><th>IoU</th><th>min</th>"
             "<th>build only</th><th>concept only</th><th>pass</th></tr>")
    for v in VIEWS:
        o = sil[v]["overlap"]
        h.append(f"<tr><td>{v}</td><td>{o['iou']:.3f}</td><td>{sil[v]['min']}</td><td>{o['b_only']:.3f}</td>"
                 f"<td>{o['a_only']:.3f}</td>{_pass(sil[v]['pass'])}</tr>")
    h.append("</table><table><tr><th>station</th><th>view</th><th>concept cm</th><th>spec cm</th><th>build cm</th>"
             "<th>error mm (vs)</th><th>tol mm</th><th>build - concept mm</th><th>pass</th></tr>")
    for v in VIEWS:
        for s in sil[v]["stations"]:
            h.append(f"<tr><td>{s['name']}</td><td>{v}</td><td>{_cell(s['concept_cm'])}</td><td>{_cell(s['spec_cm'])}"
                     f"</td><td>{_cell(s['build_cm'])}</td><td>{_cell(s['err_mm'])} ({s['against']})</td>"
                     f"<td>{s['tol_mm']}</td><td>{_cell(s['build_vs_concept_mm'])}</td>{_pass(s['pass'])}</tr>")
    h.append("</table><h2>Spec numbers on the build</h2><table><tr><th>size</th><th>spec cm</th><th>tol</th>"
             "<th>build cm</th><th>diff</th><th>pass</th><th>how</th></tr>")
    for k, sc, t, m, df, ok, how in nums:
        h.append(f"<tr><td>{k}</td><td>{sc}</td><td>{t}</td><td>{_cell(m)}</td><td>{_cell(df)}</td>{_pass(ok)}"
                 f"<td style='text-align:left'>{how}</td></tr>")
    h.append("</table><h2>Motion per clip</h2><table><tr><th>clip</th><th>check</th><th>value</th><th>tol</th>"
             "<th>pass</th></tr>")
    for r in mrows:
        h.append(f"<tr><td>{r['clip']}</td><td style='text-align:left'>{r['check']}</td><td>{_cell(r['value'])} "
                 f"{r['unit']}</td><td>{r['tol']}</td>{_pass(r['pass'])}</tr>")
    h.append("</table>")
    p = out / "index.html"
    p.write_text("\n".join(h) + "\n", encoding="utf-8", newline="\n")
    return p


def numbers_sheet(tag, nums, sil, mrows, out: Path) -> Path:
    """One PNG of the failing and unmeasured numbers (for agents without a browser)."""
    lines = [("SPEC NUMBERS", None)] + [(f"{k}: spec {s} tol {t} build {_cell(m)}", ok) for k, s, t, m, _d, ok, _h in nums]
    lines += [("SILHOUETTES", None)] + [(f"{v}: IOU {sil[v]['overlap']['iou']:.3f} (min {sil[v]['min']})", sil[v]['pass'])
                                        for v in VIEWS]
    lines += [(f"{s['view']} {s['name']}: concept {_cell(s['concept_cm'])} spec {_cell(s['spec_cm'])} build "
               f"{_cell(s['build_cm'])} err {_cell(s['err_mm'])} mm", s["pass"]) for v in VIEWS for s in sil[v]["stations"]]
    lines += [("MOTION (FAILED OR UNMEASURED)", None)] + [
        (f"{r['clip']} {r['check']}: {_cell(r['value'])} {r['unit']} (tol {r['tol']})", r["pass"]) for r in mrows
        if r["pass"] is not True]
    cv = D.Canvas(1280, 40 + 15 * len(lines))
    cv.text(10, 10, f"GATE 2: BUILD {tag}", k=2)
    for i, (text, ok) in enumerate(lines):
        c = D.INK if ok is None and text.isupper() else NA_C if ok is None else OK_C if ok else BAD_C
        cv.text(10, 34 + 15 * i, text.upper()[:200], c=c, k=1)
    return cv.save(out)


def run(a) -> int:
    spec = S.load_spec(a.spec)
    bad = S.check_spec(spec)
    if bad:
        raise SystemExit("spec: " + "; ".join(bad))
    if "gate2" not in spec:
        raise SystemExit(f"{a.spec} has no [gate2] section")
    bad = check_gate2(spec)
    if bad:
        raise SystemExit("spec [gate2]: " + "; ".join(bad))
    blend = Path(a.blend) if a.blend else None
    sha = G.file_sha256(blend) if blend else None
    build_of(a.probe, sha, "--probe")
    if a.motion:
        build_of(a.motion, sha, "--motion")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    body = S.load_probe(a.body)
    sec = S.Sections(body, [spec["body"]["mesh"]])
    build = S.load_probe(a.probe)
    meas, nums = spec_numbers(spec, build, sec)
    print("spec numbers:", sum(1 for r in nums if r[5]), "within,", sum(1 for r in nums if r[5] is False), "off,",
          sum(1 for r in nums if r[5] is None), "unmeasured")
    _, _, crow = BG.read_png(spec["garment"]["concept"])
    sil = {}
    for v in VIEWS:
        w, h, cm = concept_garment(spec, crow, v, out, Path(a.spec).parent)
        _, _, bm = build_mask(spec, build, sec, v)
        oz = spec["gate2"].get("overlap_z", {}).get(v)
        lim = None
        if oz:
            lm = spec["body"]["landmarks_cm"]
            rr = [int(round(GD.concept_map(spec, v)(0, G.resolve(z, {}, spec["dims"], lm))[1])) - spec["concept"]["boxes"][v][1]
                  for z in oz]
            lim = (max(0, min(rr)), min(h - 1, max(rr)))
        o = G.overlap(cm, bm, lim, w)
        o["rows"] = list(lim) if lim else None
        sts = stations(spec, v, cm, bm, w, h, meas)
        mn = spec["gate2"]["overlap_min"][v]
        sil[v] = {"overlap": o, "min": mn, "pass": o["iou"] >= mn, "stations": sts}
        print(f"overlay {v}: IoU {o['iou']:.3f} ->", overlay(spec, crow, v, cm, bm, w, h, sts, o, out / f"overlay_{v}.png"))
        print("sheet:", GD.view_sheet(spec, build, sec, crow, v, out / f"sheet_{v}.png", f"the build {a.tag}"))
    motion = json.loads(Path(a.motion).read_text(encoding="utf-8")) if a.motion else {"clips": {}}
    poke = json.loads(Path(a.poke).read_text(encoding="utf-8")) if a.poke else None
    mrows = motion_rows(spec, motion, poke)
    videos, vwhy = {}, "no --video"
    vok = False
    if a.video:
        vok, vwhy = video_source(Path(a.video), blend, sha)
        print("videos:", vwhy)
    if vok:
        for name in ("Walk", "Jog_Fwd"):
            src = Path(a.video) / "clips" / f"{name}.mp4"
            if src.is_file():
                shutil.copyfile(src, out / f"closeup_{name}.mp4")
                videos[name] = f"closeup_{name}.mp4"
    checks = [r[5] for r in nums] + [sil[v]["pass"] for v in VIEWS] + [s["pass"] for v in VIEWS for s in sil[v]["stations"]]
    checks += [r["pass"] for r in mrows]
    n_ok, n_bad, n_na = checks.count(True), checks.count(False), checks.count(None)
    verdict = {"pass": n_bad == 0 and n_na == 0 and len(videos) == 2,
               "summary": f"{n_ok} checks within tolerance, {n_bad} off, {n_na} unmeasured; videos {len(videos)}/2 ({vwhy}). "
                          "Gate 2 passes only with every check measured and within tolerance."}
    rep = {"tag": a.tag, "spec": a.spec, "build_probe": a.probe, "dress": a.dress, "verdict": verdict,
           "blend": a.blend, "blend_sha256": sha, "spec_numbers": meas, "silhouettes": sil, "motion": mrows, "motion_raw": motion, "videos": videos}
    (out / "gate2.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    print("numbers:", numbers_sheet(a.tag, nums, sil, mrows, out / "numbers.png"))
    print("page:", page(a.tag, spec, nums, sil, mrows, videos, verdict, out))
    print("verdict:", "PASS" if verdict["pass"] else "NOT PASSED", "-", verdict["summary"])
    return 0 if verdict["pass"] else 1


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--body", required=True, help="garment_spec_probe.py's dump of the undressed character")
    ap.add_argument("--probe", required=True, help="garment_spec_probe.py's dump of the dressed build")
    ap.add_argument("--dress", help="the build's dress.json (recorded only: every size is measured on the mesh)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--motion", help="garment_motion.py's result")
    ap.add_argument("--poke", help="clothes_proof.py's poke.json")
    ap.add_argument("--video", help="a `frames --video Walk,Jog_Fwd --video-camera ...` output folder")
    ap.add_argument("--blend", help="the build's .blend: the probe, the motion and the videos must be of it (SHA-256)")
    ap.add_argument("--tag", default="build")
    return ap


if __name__ == "__main__":
    raise SystemExit(run(parser().parse_args()))
