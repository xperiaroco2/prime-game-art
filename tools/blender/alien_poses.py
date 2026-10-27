"""The photo poses on the alien (art #196): the legs and arms poses of anim_sets/alien_poses.toml solved on each
character's own rest skeleton and skin (alien_pose_math), written as held clips CharacterArmature|PoseLegs_<Name>_Loop
and CharacterArmature|PoseArms_<Name>_Loop, every pair measured, and a quick workbench sheet of the starting pairs
from the four facings with their outlines.

    $PYTHON_BIN tools/blender/alien_poses.py --raw D:/prime-art-raw --step s1 [--chars chameleon,axolotl] [--sheet]
    $PYTHON_BIN tools/blender/alien_poses.py --raw D:/prime-art-raw --step s1 --dump      # skeleton and skin only
    $PYTHON_BIN tools/blender/alien_poses.py --solve <dump.json> --out <dir> [--pairs starting|all]  # plain Python

Into <raw>/<raw_base>/<out>/<step>/: build/<char>/<char>_char.blend (the f3 build plus the pose clips),
build/<char>/poses.json (per pair the numbers, the fails, the landmarks), <char>_dump.json (the skin the solve
reads), sheet_<char>.png. A step folder that holds a build is refused (never over a raw folder). Long: run it in
the background.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import alien_pose_math as A  # noqa: E402

PREFIX = "CharacterArmature|"
CELL = (160, 240)
FACINGS = (("front", 0.0), ("left", 90.0), ("right", -90.0), ("back", 180.0))  # camera yaw about the body


def _dirs(raw: str, step: str, cfg: dict) -> tuple[Path, Path]:
    base = Path(raw) / cfg["set"]["raw_base"]
    return base / cfg["set"]["build"], base / cfg["set"]["out"] / step


# -------------------------------------------------------------------------------------------- plain Python
def pairs_of(cfg: dict, which: str) -> list:
    if which == "starting":
        return [tuple(p) for p in cfg["set"]["starting"]]
    legs = sorted({p[0] for p in cfg["set"]["starting"]}) if which == "starting_parts" else list(cfg["legs"])
    arms = sorted({p[1] for p in cfg["set"]["starting"]}) if which == "starting_parts" else list(cfg["arms"])
    return [(lg, am) for lg in legs for am in arms]


def solve(dump: dict, cfg: dict, which: str) -> tuple[A.Model, dict, dict, list]:
    """The model, its solved legs and arms rigs (by name) and the measures of the pairs."""
    model = A.Model(dump["skel"], dump["skin"], cfg)
    pairs = pairs_of(cfg, which)
    legs = {n: model.legs(n) for n in dict.fromkeys(p[0] for p in pairs)}
    arms = {n: model.arms(n) for n in dict.fromkeys(p[1] for p in pairs)}
    rows = []
    for lg, am in pairs:
        m = A.measure(model, A.compose(legs[lg], arms[am]), lg, am)
        rows.append(m)
        print(f"PAIR {m['pair']} floor {m['floor_cm']} com {m['com_margin_cm']} touch {m['touch_cm']} contacts "
              f"{m['contacts_cm']} through-max {max(m['through_cm'].values())} fails {m['fails']}", flush=True)
    return model, legs, arms, rows


def proxy_error(model: A.Model) -> dict:
    """The tube proxy's reading on the rest skin itself (cm): the floor under the through limits."""
    rp = model.rest_posed
    P = A.Rig(model.skel).P()
    out = {}
    for a, b in (("thigh_Left", "torso"), ("upperarm_Left", "torso"), ("hand_Left", "torso")):
        out[f"{a}>{b}"] = round(max(A.tube_depth(model.tubes[t], P, rp.group(a))
                                    for t in A.tube_bones(b, model.tubes)) * 100, 2)
    return out


def _solve_main(a, cfg: dict) -> int:
    dump = json.loads(Path(a.solve).read_text(encoding="utf-8"))
    model, legs, arms, rows = solve(dump, cfg, a.pairs)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "solve.json").write_text(json.dumps({"marks": model.marks, "proxy_rest_cm": proxy_error(model),
                                                "pairs": rows}, indent=1), encoding="utf-8", newline="\n")
    print("FAILS", sum(1 for r in rows if r["fails"]), "of", len(rows), flush=True)
    return 0


# ---------------------------------------------------------------------------------------------- in Blender
def _dump(arm) -> dict:
    import bpy
    import alien_stride as ST
    mesh = [o for o in bpy.data.objects if o.type == "MESH" and o.parent == arm]
    bones = [b.name for b in arm.data.bones]
    bi = {b: i for i, b in enumerate(bones)}
    pts, ws, dom = [], [], []
    for o in mesh:
        gname = {g.index: g.name for g in o.vertex_groups}
        mw = o.matrix_world
        for v in o.data.vertices:
            w = sorted(((g.weight, bi[gname[g.group]]) for g in v.groups if gname.get(g.group) in bi and g.weight > 0),
                       reverse=True)[:4]
            if not w:
                continue
            t = sum(x for x, _ in w)
            pts.append(tuple(round(c, 6) for c in (mw @ v.co)))
            ws.append([(b, round(x / t, 5)) for x, b in w])
            dom.append(w[0][1])
    return {"skel": ST.skeleton(arm), "skin": {"bones": bones, "points": pts, "weights": ws, "dom": dom}}


def _apply(arm, rig: A.Rig) -> None:
    import bpy
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.location, pb.rotation_quaternion = rig.loc[pb.name], rig.rot[pb.name]
    bpy.context.view_layer.update()


def _lowest_blender(arm) -> float:
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    low = 1e9
    for o in bpy.data.objects:
        if o.type == "MESH" and o.parent == arm:
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            mw = o.matrix_world
            low = min(low, min((mw @ v.co).z for v in me.vertices))
            ev.to_mesh_clear()
    return low


def _stage(arm):
    """The workbench stage: the character's meshes only, a floor, a camera; returns (camera, floor, meshes)."""
    import bpy
    sc = bpy.context.scene
    mesh = [o for o in bpy.data.objects if o.type == "MESH" and o.parent == arm]
    for o in bpy.data.objects:
        if o.type in ("MESH", "LIGHT") and o not in mesh and o.name != "pose_floor":
            o.hide_render = True
    floor = bpy.data.objects.get("pose_floor")
    if floor is None:
        bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0.0, 0.0, 0.0))
        floor = bpy.context.active_object
        floor.name = "pose_floor"
    cam = bpy.data.objects.get("pose_cam")
    if cam is None:
        cam = bpy.data.objects.new("pose_cam", bpy.data.cameras.new("pose_cam"))
        sc.collection.objects.link(cam)
    cam.data.sensor_width = 36.0
    sc.camera = cam
    if sc.world is None:
        sc.world = bpy.data.worlds.new("pose_world")
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.film_transparent = False
    return cam, floor, mesh


def _shot(stage, yaw: float, mask: bool, size: tuple, lens: float, tmp: Path, dist: float = 7.0, cz: float = 1.5):
    """One render as an (h, w, 4) array (bottom row first): the camera `dist` away at `cz` high, aimed at 0.92 m,
    turned `yaw` degrees about the body (0 the front); `mask` flat black on white, else shaded on a grey floor."""
    import bpy
    import numpy as np
    cam, floor, mesh = stage
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = size
    cam.data.lens = lens
    th = math.radians(yaw)
    # the body faces -Y: "front" puts the camera at -Y; "left" at the character's left (+X)
    cam.location = (dist * math.sin(th), -dist * math.cos(th), cz)
    cam.rotation_euler = (math.pi / 2 - math.atan2(cz - 0.92, dist), 0.0, th)
    shade = sc.display.shading
    if mask:
        shade.light, shade.color_type, shade.single_color = "FLAT", "SINGLE", (0.0, 0.0, 0.0)
        shade.show_shadows = False
        floor.hide_render = True
        sc.world.color = (1.0, 1.0, 1.0)
    else:
        shade.light, shade.color_type = "STUDIO", "OBJECT"
        shade.show_shadows = True
        floor.hide_render = False
        floor.color = (0.55, 0.55, 0.55, 1.0)
        for o in mesh:
            o.color = (0.45, 0.72, 0.68, 1.0)
        sc.world.color = (0.82, 0.82, 0.82)
    sc.render.filepath = str(tmp)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(tmp), check_existing=False)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(size[1], size[0], 4)
    bpy.data.images.remove(img)
    return px


def _save(canvas, path: Path, width: int = 0) -> None:
    """A float RGBA canvas (bottom row first) as a PNG; `width`: scaled down to it (nearest)."""
    import bpy
    import numpy as np
    if width and canvas.shape[1] > width:
        h = int(round(canvas.shape[0] * width / canvas.shape[1]))
        canvas = canvas[(np.arange(h) * canvas.shape[0] // h)][:, (np.arange(width) * canvas.shape[1] // width)]
    canvas = np.ascontiguousarray(canvas)
    out = bpy.data.images.new(path.stem, canvas.shape[1], canvas.shape[0], alpha=True)
    out.pixels.foreach_set(canvas.ravel())
    out.filepath_raw = str(path)
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)


def _sheet(arm, model, rigs: list, labels: list, path: Path) -> None:
    """Per pair one row: the four facings shaded, then their four outlines (black on white); camera 1.5 m high, 7 m
    away, never turning (the photographer's)."""
    import numpy as np
    stage = _stage(arm)
    w, h = CELL
    cols = 2 * len(FACINGS)
    canvas = np.ones((h * len(rigs) + 4 * (len(rigs) - 1), w * cols, 4), dtype=np.float32)
    tmp = path.parent / "_cell.png"
    for row, rig in enumerate(rigs):
        _apply(arm, rig)
        for c, (face, yaw) in enumerate(FACINGS):
            for k, mask in enumerate((False, True)):
                y0 = canvas.shape[0] - (row + 1) * h - row * 4
                x0 = (c + k * len(FACINGS)) * w
                canvas[y0:y0 + h, x0:x0 + w] = _shot(stage, yaw, mask, CELL, 120.0, tmp)
        print(f"SHEET row {labels[row]}", flush=True)
    tmp.unlink(missing_ok=True)
    _save(canvas, path)


MASK = (240, 240)  # the outline masks: 240 px square, 2.5 m across at 7 m (lens 100)


def _masks(arm, char: str, model, legs: dict, arms: dict, out: Path) -> None:
    """Every pair's outline from the four facings (masks_<char>.json, rows as hex bitsets, top row first), the
    silhouette table (silhouettes_<char>.json), a 48-pair outline grid per facing and the shaded 48-pair grids from
    the front and a three-quarter view (rows the legs, columns the arms, in the data's order)."""
    import numpy as np
    stage = _stage(arm)
    tmp = out / "_cell.png"
    w, h = MASK
    ln, an = list(legs), list(arms)
    grids = {f: np.ones((h * len(ln), w * len(an), 4), dtype=np.float32) for f, _ in FACINGS}
    shaded = {k: np.ones((h * len(ln), w * len(an), 4), dtype=np.float32) for k in ("front", "34")}
    masks = {}
    pad = 8 * ((w + 7) // 8) - w
    for i, lg in enumerate(ln):
        for j, am in enumerate(an):
            _apply(arm, A.compose(legs[lg], arms[am]))
            y0, x0 = (len(ln) - 1 - i) * h, j * w
            for face, yaw in FACINGS:
                px = _shot(stage, yaw, True, MASK, 100.0, tmp)
                grids[face][y0:y0 + h, x0:x0 + w] = px
                m = px[::-1, :, 0] < 0.5
                masks[f"{lg}+{am}|{face}"] = [format(int.from_bytes(np.packbits(r).tobytes(), "big") >> pad, "x")
                                              for r in m]
            for key, yaw in (("front", 0.0), ("34", 35.0)):
                shaded[key][y0:y0 + h, x0:x0 + w] = _shot(stage, yaw, False, MASK, 100.0, tmp)
        print(f"MASKS {char} {lg}", flush=True)
    tmp.unlink(missing_ok=True)
    for g in list(grids.values()) + list(shaded.values()):  # thin grey cell lines
        for c in range(1, len(an)):
            g[:, c * w, :3] = 0.6
        for r in range(1, len(ln)):
            g[r * h, :, :3] = 0.6
    for face, g in grids.items():
        _save(g, out / f"grid_outline_{face}_{char}.png")
    for key, g in shaded.items():
        _save(g, out / f"grid_{key}_{char}.png")
        _save(g, out / f"grid_{key}_{char}_1280.png", 1280)
    (out / f"masks_{char}.json").write_text(json.dumps({"w": w, "h": h, "legs": ln, "arms": an, "masks": masks}),
                                            encoding="utf-8", newline="\n")
    write_table(out, char, model.data)


def write_table(out: Path, char: str, cfg: dict) -> dict:
    """The silhouette table from masks_<char>.json into silhouettes_<char>.json (plain Python too)."""
    d = json.loads((out / f"masks_{char}.json").read_text(encoding="utf-8"))
    masks = {}
    for k, v in d["masks"].items():
        pair, face = k.split("|")
        lg, am = pair.split("+")
        masks[(lg, am, face)] = [int(x, 16) for x in v]
    tab = A.silhouette_table(masks, d["legs"], d["arms"], d["w"], lopsided=tuple(cfg["set"].get("lopsided", ())))
    (out / f"silhouettes_{char}.json").write_text(json.dumps(tab, indent=1), encoding="utf-8", newline="\n")
    return tab


def _fcurves(act) -> list:
    """An action's F-curves (a layered action keeps them in its channelbags)."""
    if getattr(act, "fcurves", None) is not None and len(act.fcurves):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", ()):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", ()):
                out += list(bag.fcurves)
    return out


def _digest() -> dict:
    """Per action a hash of its F-curves' keys (data path, index, each key's frame, value and interpolation)."""
    import bpy
    import hashlib
    out = {}
    for act in bpy.data.actions:
        h = hashlib.sha256()
        for fc in sorted(_fcurves(act), key=lambda f: (f.data_path, f.array_index)):
            h.update(f"{fc.data_path}[{fc.array_index}]".encode())
            for k in fc.keyframe_points:
                h.update(f"{k.co[0]:.5f},{k.co[1]:.7f},{k.interpolation};".encode())
        out[act.name] = h.hexdigest()
    return out


def _blender_main(argv: list[str]) -> None:
    import bpy
    import alien_stride as ST
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--step", required=True)
    ap.add_argument("--chars", default="")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--masks", action="store_true")
    ap.add_argument("--glb", action="store_true")
    ap.add_argument("--pairs", default="all")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    cfg = A.load()
    build, out = _dirs(a.raw, a.step, cfg)
    out = Path(a.out) if a.out else out
    for char in a.chars.split(",") if a.chars else cfg["set"]["chars"]:
        bpy.ops.wm.open_mainfile(filepath=str(build / char / f"{char}_char.blend"))
        before = _digest()
        arm = ST._armature()
        dump = _dump(arm)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{char}_dump.json").write_text(json.dumps(dump), encoding="utf-8", newline="\n")
        print(f"DUMP {char} {len(dump['skin']['points'])} points", flush=True)
        if a.dump:
            continue
        hd = out / "build" / char
        hd.mkdir(parents=True, exist_ok=True)
        model, legs, arms, rows = solve(dump, cfg, a.pairs)
        for n, r in legs.items():
            ST.write(arm, A.layer_clip(r, "legs", f"{A.LEGS_PREFIX}{n}_Loop"), f"{A.LEGS_PREFIX}{n}_Loop")
        for n, r in arms.items():
            ST.write(arm, A.layer_clip(r, "arms", f"{A.ARMS_PREFIX}{n}_Loop"), f"{A.ARMS_PREFIX}{n}_Loop")
        after = _digest()
        changed = sorted(k for k in before if after.get(k) != before[k])
        print(f"CHECK {char} the build's {len(before)} clips: {len(changed)} changed {changed}", flush=True)
        # the pure skinning against Blender's own evaluated mesh: the lowest point of every measured pair
        for m in rows:
            lg, am = m["pair"].split("+")
            _apply(arm, A.compose(legs[lg], arms[am]))
            m["floor_blender_cm"] = round(_lowest_blender(arm) * 100.0, 2)
        worst = max(abs(m["floor_blender_cm"] - m["floor_cm"]) for m in rows)
        print(f"CHECK {char} lowest point, pure skinning vs Blender: at most {worst:.3f} cm apart", flush=True)
        added = sorted(set(after) - set(before))
        bpy.ops.wm.save_as_mainfile(filepath=str(hd / f"{char}_char.blend"), compress=True)
        (hd / "poses.json").write_text(json.dumps({
            "char": char, "marks": model.marks, "leg_len": model.leg_len, "proxy_rest_cm": proxy_error(model),
            "split": A.split(model.skel["order"]), "added": added, "skin_check_cm": worst,
            "build_clips": {"count": len(before), "changed": changed}, "pairs": rows}, indent=1),
            encoding="utf-8", newline="\n")
        print(f"CHAR {char} {len(added)} clips, {sum(1 for m in rows if m['fails'])} of {len(rows)} pairs over a "
              f"limit", flush=True)
        if a.glb:
            import alien_loco as LO
            LO._export(arm, hd / f"{char}_char.glb")
            print(f"GLB {char} {hd / (char + '_char.glb')}", flush=True)
        if a.sheet:
            st = [tuple(p) for p in cfg["set"]["starting"]]
            _sheet(arm, model, [A.compose(legs[lg], arms[am]) for lg, am in st], [f"{lg}+{am}" for lg, am in st],
                   out / f"sheet_{char}.png")
        if a.masks:
            _masks(arm, char, model, legs, arms, out)


def glb_clips(path: Path) -> dict:
    """Per animation of a GLB a hash of its channels: the target node's name and path, the interpolation, and the
    bytes of the key times and values (compared clip by clip against another build's GLB)."""
    import hashlib
    import struct
    data = Path(path).read_bytes()
    n = struct.unpack_from("<I", data, 12)[0]
    js = json.loads(data[20:20 + n])
    bn = data[20 + n + 8:]

    def acc(i):
        a = js["accessors"][i]
        v = js["bufferViews"][a["bufferView"]]
        comp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
        size = {5126: 4, 5123: 2, 5121: 1, 5125: 4}[a["componentType"]] * comp
        st = v.get("byteStride", size)
        o = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        return b"".join(bn[o + k * st:o + k * st + size] for k in range(a["count"]))

    out = {}
    for an in js.get("animations", []):
        h = hashlib.sha256()
        for ch in sorted(an["channels"], key=lambda c: (js["nodes"][c["target"]["node"]].get("name", ""),
                                                        c["target"]["path"])):
            s = an["samplers"][ch["sampler"]]
            h.update(f"{js['nodes'][ch['target']['node']].get('name')}/{ch['target']['path']}/"
                     f"{s.get('interpolation', 'LINEAR')}".encode())
            h.update(acc(s["input"]))
            h.update(acc(s["output"]))
        out[an["name"]] = h.hexdigest()
    return out


def main() -> int:
    sys.path.insert(0, str(ROOT / "tools"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="")
    ap.add_argument("--step", default="")
    ap.add_argument("--chars", default="")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--masks", action="store_true", help="every pair's outlines, the silhouette table, the grids")
    ap.add_argument("--glb", action="store_true", help="the GLB, glTF-Validator, the build's clips compared")
    ap.add_argument("--solve", default="", help="a dump JSON: solve and measure in plain Python, no Blender")
    ap.add_argument("--out", default="")
    ap.add_argument("--pairs", default="all", choices=("starting", "starting_parts", "all"))
    a = ap.parse_args()
    cfg = A.load()
    if a.solve:
        return _solve_main(a, cfg)
    from runner import blender
    from runner.commands import _export
    import alien_loco as LO
    build, out = _dirs(a.raw, a.step, cfg)
    out = Path(a.out) if a.out else out  # a scratch folder for tuning (tools/out/poses/...)
    if (out / "build").exists() and not a.dump:
        print(f"{out / 'build'} exists: a new --step folder, never over a raw folder", flush=True)
        return 2
    chars = a.chars.split(",") if a.chars else cfg["set"]["chars"]
    if a.glb:  # the build's side files beside the GLB, as alien_loco.py copies them
        for c in chars:
            (out / "build" / c).mkdir(parents=True, exist_ok=True)
            for f in LO.COPY:
                p = build / c / f.format(c=c)
                if p.exists():
                    shutil.copy2(p, out / "build" / c / p.name)
    args = ["--raw", a.raw, "--step", a.step, "--pairs", a.pairs] + (["--chars", a.chars] if a.chars else []) + \
        [f"--{k}" for k in ("dump", "sheet", "masks", "glb") if getattr(a, k)] + \
        (["--out", str(Path(a.out).resolve())] if a.out else [])
    res = blender.run_script(Path(__file__).resolve(), args, timeout=3600)
    out.mkdir(parents=True, exist_ok=True)
    (out / "blender.log").write_text((res.stdout or "") + (res.stderr or ""), encoding="utf-8", newline="\n")
    print(*[x for x in (res.stdout or "").splitlines() if x.startswith(
        ("DUMP", "CHECK", "CHAR", "SHEET", "MASKS", "GLB", "Traceback"))], sep="\n", flush=True)
    if res.returncode != 0:
        print(f"blender: exit {res.returncode} (see {out / 'blender.log'})", flush=True)
        return res.returncode
    ok = True
    for c in chars if a.glb else ():
        glb = out / "build" / c / f"{c}_char.glb"
        good, text = _export.verdict(_export.validate(glb, glb.with_suffix(".validator.json")))
        old, new = glb_clips(build / c / f"{c}_char.glb"), glb_clips(glb)
        diff = sorted(k for k in old if new.get(k) != old[k])
        added = sorted(set(new) - set(old))
        print(f"validator {glb.name}: {text}", flush=True)
        print(f"GLB-CLIPS {c}: of the f3 build's {len(old)} clips {len(diff)} differ {diff}; {len(added)} added",
              flush=True)
        (glb.parent / "clips_proof.json").write_text(json.dumps({
            "f3": str(build / c / f"{c}_char.glb"), "changed": diff, "added": added, "f3_clips": old, "clips": new},
            indent=1), encoding="utf-8", newline="\n")
        ok &= good and not diff
    return 0 if ok else 1


if __name__ == "__main__":
    if "bpy" in sys.modules:
        _blender_main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    else:
        sys.exit(main())
