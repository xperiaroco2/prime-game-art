"""The alien pilot's static heads, round 5 (art #196, static_v5): two Blender comparison sheets (JPG, about 1280 px wide).
Run as plain Python (the driver calls headless Blender through tools/runner/blender.py), or inside Blender with the
same arguments after "--".
- `lids`: the chameleon's lids in grey clay (Workbench, studio light): the dense Meshy original, #288, round 4
  (static_v4) and this round (rows); the eye from the front, at 3/4 and from
  the side (columns). Which lid the original has, and which build keeps it.
- `web`: what a browser's glTF viewer (three.js) shows: each GLB as Blender's glTF importer reads it (the base colour,
  roughness and normal maps and the KHR_materials_clearcoat, _sheen and _specular extensions; no Godot shader), Cycles
  under the plain studio HDRI only, the Standard view transform (no Filmic or AgX); rows #288 and this round (no
  earlier rounds); columns the face from the front, at 3/4 and the full head at 3/4.

    $PYTHON_BIN tools/blender/alien_static_compare.py <lids|web> [--heads axolotl,chameleon]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import bpy
except ImportError:  # the driver, outside Blender
    bpy = None

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import common  # noqa: E402

RAW = common.raw_dir()
MESHY = RAW / "2026-10-22-alien-pilot-3d"
PILOT = RAW / "research" / "2026-10-22-roster" / "design" / "pilot3d"
HDRI = RAW / "env" / "polyhaven" / "studio_small_09" / "studio_small_09_2k.hdr"  # CC0, sources/polyhaven_hdris_2k.toml
NEW = PILOT / "static_v5"  # static_v4 dropped the heavier-lid alternative (its lids were the same geometry)
BUILDS = {"axolotl": ["axolotl"], "chameleon": ["chameleon"]}


def rows_for(what: str, head: str) -> list[tuple[str, Path]]:
    if what == "lids":
        return [("dense", MESHY / head / "multi_image_to_3d-pre_remeshed_model.glb"),
                ("288", PILOT / "static" / head / f"{head}_static.glb"),
                ("v4", PILOT / "static_v4" / head / f"{head}_static.glb"),
                *[(n, NEW / n / f"{n}_static.glb") for n in BUILDS[head]]]
    return [("288", PILOT / "static" / head / f"{head}_static.glb"),
            *[(n, NEW / n / f"{n}_static.glb") for n in BUILDS[head]]]


def blender_main(argv: list[str]) -> None:
    import numpy as np
    from mathutils import Matrix, Vector

    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["lids", "web"])
    ap.add_argument("--heads", default="axolotl,chameleon")
    args = ap.parse_args(argv)
    heads = ["chameleon"] if args.what == "lids" else args.heads.split(",")
    tmp = NEW / f"_{args.what}"
    tmp.mkdir(parents=True, exist_ok=True)
    cell = 420
    for head in heads:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        ref = json.loads((PILOT / "step2a" / head / "v2" / "build.json").read_text(encoding="utf-8"))
        e = ref["eye_fit"]
        ex, ey, ez, r = abs(e["x"]), e["y"], e["z"], e["r"]
        mz = ref["lip_line"]["front_point"][2]
        groups = []
        for key, glb in rows_for(args.what, head):
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=str(glb))
            groups.append((key, [o for o in bpy.data.objects if o not in before and o.type == "MESH"]))
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        scene.collection.objects.link(cam)
        scene.camera = cam
        scene.world = bpy.data.worlds.new("w")
        scene.world.use_nodes = True
        scene.view_settings.view_transform = "Standard"
        scene.render.resolution_x, scene.render.resolution_y = cell, cell if args.what == "lids" else int(cell * 1.15)
        if args.what == "lids":
            scene.render.engine = "BLENDER_WORKBENCH"
            sh = scene.display.shading
            sh.light, sh.color_type, sh.single_color = "STUDIO", "SINGLE", (0.7, 0.7, 0.7)
            sh.show_specular_highlight = True
            scene.world.color = (0.17, 0.17, 0.17)
            shots = [((ex, ey, ez), (0.0, -1.0, 0.0), 3.0 * r), ((ex, ey, ez), (0.6, -0.8, 0.0), 3.0 * r),
                     ((ex, ey, ez), (1.0, 0.0, 0.0), 3.0 * r)]
        else:
            scene.render.engine = "CYCLES"
            scene.cycles.device = "CPU"
            scene.cycles.samples = 48
            scene.cycles.use_denoising = True
            nt = scene.world.node_tree
            env = nt.nodes.new("ShaderNodeTexEnvironment")
            env.image = bpy.data.images.load(str(HDRI))
            nt.links.new(env.outputs["Color"], nt.nodes["Background"].inputs["Color"])
            face = (0.0, ey, (ez + mz) / 2)
            fw = 2.0 * max(ex + r, ref["lip_line"]["half_width"]) * 1.25
            pts = [o.matrix_world @ Vector(c) for o in groups[0][1] for c in o.bound_box]
            lo = Vector([min(p[k] for p in pts) for k in range(3)])
            hi = Vector([max(p[k] for p in pts) for k in range(3)])
            box_c = (lo + hi) / 2
            shots = [(face, (0.0, -1.0, 0.05), fw), (face, (0.57, -0.82, 0.05), fw),
                     (tuple(box_c), (0.5, -0.86, 0.08), (hi.z - lo.z) * 1.1 / 1.15)]
        files = []
        for gi, (key, objs) in enumerate(groups):
            for _, o2 in groups:
                for o in o2:
                    o.hide_render = True
            for o in objs:
                o.hide_render = False
            row = []
            for si, (centre, d, width) in enumerate(shots):
                d = Vector(d).normalized()
                z = d
                x = Vector((0.0, 0.0, 1.0)).cross(z).normalized()
                cam.rotation_euler = Matrix((x, z.cross(x), z)).transposed().to_euler()
                if args.what == "lids":
                    cam.data.type = "ORTHO"
                    cam.data.ortho_scale = width
                    cam.location = Vector(centre) + d * 10.0
                else:
                    cam.data.type = "PERSP"
                    cam.data.lens = 85
                    cam.location = Vector(centre) + d * (width * 85 / 36)
                cam.data.clip_end = 40.0
                path = tmp / f"{head}_{gi}_{si}.png"
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
                row.append(path)
            files.append(row)
        # the sheet: cells 4 px apart, scaled to 1280 px wide
        img0 = bpy.data.images.load(str(files[0][0]))
        w, h = img0.size
        sheet = np.full((len(files) * (h + 4) - 4, 3 * (w + 4) - 4, 4), 0.2, np.float32)
        sheet[..., 3] = 1
        for i, row in enumerate(files):
            for j, p in enumerate(row):
                im = bpy.data.images.load(str(p))
                a = np.empty(w * h * 4, np.float32)
                im.pixels.foreach_get(a)
                y0 = (len(files) - 1 - i) * (h + 4)
                sheet[y0:y0 + h, j * (w + 4):j * (w + 4) + w] = a.reshape(h, w, 4)
        out = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0])
        out.pixels.foreach_set(sheet.ravel())
        out.scale(1280, int(sheet.shape[0] * 1280 / sheet.shape[1]))
        out.filepath_raw = str((NEW / head / f"{args.what}.jpg") if args.what == "web" else NEW / "chameleon" / "lids.jpg")
        out.file_format = "JPEG"
        out.save()
        print(f"COMPARE wrote {out.filepath_raw} rows {[k for k, _ in groups]}", flush=True)


def driver() -> int:
    from runner import blender
    result = blender.run_script(Path(__file__), sys.argv[1:], timeout=3000)
    print("\n".join(x for x in (result.stdout or "").splitlines() if x.startswith("COMPARE")), flush=True)
    return 0


if __name__ == "__main__":
    if bpy is None:
        sys.exit(driver())
    blender_main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
