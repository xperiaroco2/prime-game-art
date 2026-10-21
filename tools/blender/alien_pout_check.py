"""M16 (art #196, brief UPDATE 29): the pout's closed pieces (rest, M, small) mirrored across the face's centre line, in
headless Blender. Opens a kit's export/alien_character.blend (M10b's or later), builds the pout's closed pieces from
the current code (alien_mouths.build_piece with alien_lips_geom.LIP_SHAPE_POUT, as alien_m12.build_design does, no
bake, nothing saved) and, for a kit that already has them (--kit-pieces), its own mouth_pout_<shape> nodes, and
prints one line "POUT_SYM {json}": per piece the largest distance (mm) from a vertex's mirror (x -> -x, world, rest
pose) to the nearest vertex, its vertex count and its x extent. tools/tests/test_alien_pout_rest_blender.py reads it.

    tools/runner/blender.py run_script("alien_pout_check.py", ["--kit", <M10c/export>])
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import kdtree
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_lips_geom as LP  # noqa: E402
import alien_m6 as M6  # noqa: E402
import alien_m12 as M12  # noqa: E402
import alien_mouths as AM  # noqa: E402

CLOSED = ("rest", "M", "small")


def mirror_dev(ob) -> dict:
    """The object's world vertices against their mirror across x = 0: the largest nearest-vertex distance (mm)."""
    mw = ob.matrix_world
    co = [mw @ v.co for v in ob.data.vertices]
    kd = kdtree.KDTree(len(co))
    for i, c in enumerate(co):
        kd.insert(c, i)
    kd.balance()
    dev = max(kd.find((-c.x, c.y, c.z))[2] for c in co)
    xs = [c.x for c in co]
    return {"max_mm": round(dev * 1000, 4), "verts": len(co), "x_mm": [round(min(xs) * 1000, 2), round(max(xs) * 1000, 2)]}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--kit", required=True)
    p.add_argument("--sheet", default=M12.SHEET)
    p.add_argument("--kit-pieces", action="store_true", help="also the kit's own mouth_pout_<shape> nodes")
    a = p.parse_args(argv)
    kit = Path(a.kit)
    bpy.ops.wm.open_mainfile(filepath=str(kit / "alien_character.blend"))
    out = {"kit": {}, "built": {}}
    if a.kit_pieces:
        for s in CLOSED:
            ob = bpy.data.objects.get(f"mouth_pout_{s}")
            if ob is not None:
                out["kit"][s] = mirror_dev(ob)
    cj = json.loads((kit / "character.json").read_text(encoding="utf-8"))
    body = M6.rest_pose()
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    sock = bpy.data.objects["Mouth"].matrix_world.copy()
    z_sock = sock.translation.z
    face_w = AM.face_width(bvh, z_sock)
    chin_z = cj.get("report_s6", {}).get("chin_z", AM.CHIN_Z)
    ms, _drep, frames = AM.shape_frames(AM.load_rgb(a.sheet), face_w, z_sock, chin_z, "pout")
    mat = bpy.data.materials.new("pout_check")
    mats = {"lip": mat, "inner": mat, "teeth": mat, "tongue": mat}
    coll = bpy.context.scene.collection
    for k, s in enumerate(AM.SHAPES):
        if s not in CLOSED:
            continue
        ob, meas, _st = AM.build_piece(bvh, ms[k], "pout", s, frames[s]["world"], mats, coll, sock,
                                       lips=LP.merged_pout(None), name=f"pout_check_{s}")
        out["built"][s] = dict(mirror_dev(ob), form=meas["form"], width_mm=meas["width_mm"])
    out["socket_x_mm"] = round(sock.translation.x * 1000, 4)
    print("POUT_SYM " + json.dumps(out))


if __name__ == "__main__":
    main()
