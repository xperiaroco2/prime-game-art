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


def _sheet(arm, model, rigs: list, labels: list, path: Path) -> None:
    """Per pair one row: the four facings shaded, then their four outlines (black on white); camera 1.5 m high, 7 m
    away, never turning (the photographer's)."""
    import bpy
    import numpy as np
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
    cam.data.lens = 120.0
    cam.data.sensor_width = 36.0
    sc.camera = cam
    if sc.world is None:
        sc.world = bpy.data.worlds.new("pose_world")
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x, sc.render.resolution_y = CELL
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.film_transparent = False
    w, h = CELL
    cols = 2 * len(FACINGS)
    canvas = np.ones((h * len(rigs) + 4 * (len(rigs) - 1), w * cols, 4), dtype=np.float32)
    tmp = path.parent / "_cell.png"
    dist, cz = 7.0, 1.5
    for row, rig in enumerate(rigs):
        _apply(arm, rig)
        for c, (face, yaw) in enumerate(FACINGS):
            th = math.radians(yaw)
            # the body faces -Y: "front" puts the camera at -Y; "left" at the character's left (+X)
            cam.location = (dist * math.sin(th), -dist * math.cos(th), cz)
            tilt = math.atan2(cz - 0.92, dist)
            cam.rotation_euler = (math.pi / 2 - tilt, 0.0, th)
            for k, mask in enumerate((False, True)):
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
                px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
                bpy.data.images.remove(img)
                y0 = canvas.shape[0] - (row + 1) * h - row * 4
                x0 = (c + k * len(FACINGS)) * w
                canvas[y0:y0 + h, x0:x0 + w] = px
        print(f"SHEET row {labels[row]}", flush=True)
    tmp.unlink(missing_ok=True)
    out = bpy.data.images.new("pose_sheet", canvas.shape[1], canvas.shape[0], alpha=True)
    out.pixels.foreach_set(canvas.ravel())
    out.filepath_raw = str(path)
    out.file_format = "PNG"
    out.save()


def _blender_main(argv: list[str]) -> None:
    import bpy
    import alien_stride as ST
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--step", required=True)
    ap.add_argument("--chars", default="")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--pairs", default="starting_parts")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    cfg = A.load()
    build, out = _dirs(a.raw, a.step, cfg)
    out = Path(a.out) if a.out else out
    for char in a.chars.split(",") if a.chars else cfg["set"]["chars"]:
        bpy.ops.wm.open_mainfile(filepath=str(build / char / f"{char}_char.blend"))
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
        before = {x.name for x in bpy.data.actions}
        for n, r in legs.items():
            ST.write(arm, A.layer_clip(r, "legs", f"{A.LEGS_PREFIX}{n}_Loop"), f"{A.LEGS_PREFIX}{n}_Loop")
        for n, r in arms.items():
            ST.write(arm, A.layer_clip(r, "arms", f"{A.ARMS_PREFIX}{n}_Loop"), f"{A.ARMS_PREFIX}{n}_Loop")
        # the pure skinning against Blender's own evaluated mesh: the lowest point of every measured pair
        for m in rows:
            lg, am = m["pair"].split("+")
            _apply(arm, A.compose(legs[lg], arms[am]))
            m["floor_blender_cm"] = round(_lowest_blender(arm) * 100.0, 2)
        worst = max(abs(m["floor_blender_cm"] - m["floor_cm"]) for m in rows)
        print(f"CHECK {char} lowest point, pure skinning vs Blender: at most {worst:.3f} cm apart", flush=True)
        added = sorted({x.name for x in bpy.data.actions} - before)
        bpy.ops.wm.save_as_mainfile(filepath=str(hd / f"{char}_char.blend"), compress=True)
        (hd / "poses.json").write_text(json.dumps({"char": char, "marks": model.marks, "leg_len": model.leg_len,
                                                   "proxy_rest_cm": proxy_error(model), "split": A.split(
                                                       model.skel["order"]), "added": added, "skin_check_cm": worst,
                                                   "pairs": rows}, indent=1), encoding="utf-8", newline="\n")
        print(f"CHAR {char} {len(added)} clips, {sum(1 for m in rows if m['fails'])} of {len(rows)} pairs over a "
              f"limit", flush=True)
        if a.sheet:
            st = [tuple(p) for p in cfg["set"]["starting"]]
            _sheet(arm, model, [A.compose(legs[lg], arms[am]) for lg, am in st], [f"{lg}+{am}" for lg, am in st],
                   out / f"sheet_{char}.png")


def main() -> int:
    sys.path.insert(0, str(ROOT / "tools"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="")
    ap.add_argument("--step", default="")
    ap.add_argument("--chars", default="")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--solve", default="", help="a dump JSON: solve and measure in plain Python, no Blender")
    ap.add_argument("--out", default="")
    ap.add_argument("--pairs", default="starting_parts", choices=("starting", "starting_parts", "all"))
    a = ap.parse_args()
    cfg = A.load()
    if a.solve:
        return _solve_main(a, cfg)
    from runner import blender
    _, out = _dirs(a.raw, a.step, cfg)
    out = Path(a.out) if a.out else out  # a scratch folder for tuning (tools/out/poses/...)
    if (out / "build").exists() and not a.dump:
        print(f"{out / 'build'} exists: a new --step folder, never over a raw folder", flush=True)
        return 2
    args = ["--raw", a.raw, "--step", a.step, "--pairs", a.pairs] + (["--chars", a.chars] if a.chars else []) + \
        (["--dump"] if a.dump else []) + (["--sheet"] if a.sheet else []) + (["--out", str(Path(a.out).resolve())] if a.out else [])
    res = blender.run_script(Path(__file__).resolve(), args, timeout=3600)
    out.mkdir(parents=True, exist_ok=True)
    (out / "blender.log").write_text((res.stdout or "") + (res.stderr or ""), encoding="utf-8", newline="\n")
    print(*[x for x in (res.stdout or "").splitlines() if x.startswith(("DUMP", "PAIR", "CHECK", "CHAR", "SHEET"))],
          sep="\n", flush=True)
    return res.returncode


if __name__ == "__main__":
    if "bpy" in sys.modules:
        _blender_main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    else:
        sys.exit(main())
