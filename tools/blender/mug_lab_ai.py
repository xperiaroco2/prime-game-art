"""The mug lab (research): an AI-generated mug GLB made ready for the lab's shots, in headless Blender.
- `--mode plain` (pipeline B, the AI model as it comes): joined into one mesh `Mug`, turned so its handle is on +x,
  scaled so the whole (glass and head) is `--height` cm tall, its origin at the middle of the base's underside; its
  own materials and textures kept.
- `--mode hybrid` (pipeline C, the AI shape with the lab's shaders): the same, then the shell cut at the rim (its baked
  foam head goes), a wall given to it inward (Solidify), and the lab's own Liquid, Foam and FoamHead (from
  mug_lab_build.py and mug_lab.toml) fitted inside: the inner radius measured from the shell. The AI's textures go;
  the Godot look (mug_look.gd) paints glass, beer and foam.
Writes <out>/mug.glb, <out>/build.json (the levels the look needs: floor, full, rim, inner_r in cm).

Args after "--": --src GLB --out DIR --mode plain|hybrid [--height 18.2] [--rim 15.0] [--wall 0.45]
"""
from __future__ import annotations

import json
import math
import sys
import tomllib
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mug_lab_build as L  # noqa: E402

CM = 0.01


def argv() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"height": "18.2", "rim": "15.0", "wall": "0.45", "width": "9.1"}
    for i in range(0, len(a), 2):
        out[a[i].lstrip("-")] = a[i + 1]
    return out


def load(src: str) -> bpy.types.Object:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    bpy.ops.import_scene.gltf(filepath=src)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in meshes:   # bake every transform in, then join
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    for o in list(bpy.context.scene.objects):
        if o is not ob:
            bpy.data.objects.remove(o)
    ob.name = "Mug"
    return ob


def normalise(ob, height_cm: float) -> dict:
    """Blender z up. Base to z 0, the body's axis (the foot's centre) to x = y = 0, the handle to +x, the height."""
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
    zmin, zmax = min(v.z for v in vs), max(v.z for v in vs)
    h = zmax - zmin
    foot = [v for v in vs if v.z < zmin + 0.08 * h]
    cx = sum(v.x for v in foot) / len(foot)
    cy = sum(v.y for v in foot) / len(foot)
    # the handle: the direction (in xy) of the points farthest from the axis at mid height
    mid = [v for v in vs if zmin + 0.3 * h < v.z < zmin + 0.7 * h]
    far = sorted(mid, key=lambda v: (v.x - cx) ** 2 + (v.y - cy) ** 2)[-max(20, len(mid) // 50):]
    ax = sum(v.x - cx for v in far)
    ay = sum(v.y - cy for v in far)
    ang = math.atan2(ay, ax)
    s = height_cm * CM / h
    m = Matrix.Scale(s, 4) @ Matrix.Rotation(-ang, 4, "Z") @ Matrix.Translation((-cx, -cy, -zmin))
    ob.data.transform(m)
    ob.matrix_world = Matrix.Identity(4)
    vs = [v.co for v in ob.data.vertices]
    return {"turned_deg": round(math.degrees(-ang), 1), "scale": round(s, 5),
            "bounds_cm": [[round(min(v[i] for v in vs) / CM, 2) for i in range(3)],
                          [round(max(v[i] for v in vs) / CM, 2) for i in range(3)]]}


def body_radius(ob, z_cm: float, handle_cut: float) -> float:
    """The shell's smallest radius at a height (cm), the handle's side (x > handle_cut cm) left out."""
    rs = [math.hypot(v.co.x, v.co.y) / CM for v in ob.data.vertices
          if abs(v.co.z / CM - z_cm) < 0.4 and v.co.x / CM < handle_cut]
    return min(rs) if rs else 4.0


def cut_at_rim(ob, rim_cm: float) -> None:
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, rim_cm * CM), plane_no=(0, 0, 1), clear_outer=True)
    bm.to_mesh(ob.data)
    bm.free()


def tris(ob) -> int:
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def main() -> None:
    a = argv()
    out = Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    ob = load(a["src"])
    info = normalise(ob, float(a["height"]))
    # fit the body's width to the contract (9 cm across): the generator's proportions are its own
    w = 2 * max(math.hypot(v.co.x, v.co.y) for v in ob.data.vertices
                if 5.0 < v.co.z / CM < 12.0 and v.co.x / CM < 0.3 * max(u.co.x for u in ob.data.vertices) / CM)
    k = float(a["width"]) * CM / w
    ob.data.transform(Matrix.Diagonal((k, k, 1.0, 1.0)))
    info["width_fit"] = round(k, 4)
    vs = [v.co for v in ob.data.vertices]
    info["bounds_cm"] = [[round(min(v[i] for v in vs) / CM, 2) for i in range(3)],
                         [round(max(v[i] for v in vs) / CM, 2) for i in range(3)]]
    rep = {"mode": a["mode"], "src": a["src"], **info}
    if a["mode"] == "hybrid":
        rim = float(a["rim"])
        wall = float(a["wall"])
        r_rim = body_radius(ob, rim - 0.6, 4.6)
        cut_at_rim(ob, rim)
        for slot in list(ob.data.materials):
            ob.data.materials.pop()
        sol = ob.modifiers.new("wall", "SOLIDIFY")
        sol.thickness = wall * CM
        sol.offset = -1.0   # inward: the AI shell's normals face out
        sol.use_even_offset = True
        sol.use_rim = True
        with bpy.context.temp_override(active_object=ob, object=ob):
            bpy.ops.object.modifier_apply(modifier="wall")
        ob.data.materials.append(L.mat("mug_glass", (0.8, 0.88, 0.9, 0.2), 0.03, True))
        L.smooth(ob, 40)
        # the lab's beer and foam inside, sized from the shell
        S = tomllib.loads((HERE / "mug_lab.toml").read_text(encoding="utf-8"))
        inner = min(body_radius(ob, z, 4.6) for z in (6.0, 9.0, 12.0)) - wall - 0.08
        S["body"]["inner_r"] = inner
        S["body"]["rim_y"] = rim
        S["body"]["profile"] = [[0.0, r_rim], [rim, r_rim]]   # the head sits on the shell's rim
        beer = bpy.data.objects.new("Beer", None)
        bpy.context.scene.collection.objects.link(beer)
        liq = L.liquid(S)
        L.smooth(liq, 30)
        liq.data.materials.append(L.mat("mug_beer", (0.55, 0.25, 0.02, 1.0), 0.15))
        fl = L.foam_unit(S)
        for p in fl.data.polygons:
            p.use_smooth = True
        fl.data.materials.append(L.mat("mug_foam", (0.95, 0.92, 0.85, 1.0), 0.7))
        for o in (liq, fl):
            o.parent = beer
        rep["levels_cm"] = {"floor": S["body"]["floor_y"], "full": S["beer"]["full_level"], "rim": rim,
                            "inner_r": round(inner, 3), "rim_r": round(r_rim, 3),
                            "head_top": S["foam"]["head_top"]}
        rep["by_mesh"] = {o.name: tris(o) for o in (ob, liq, fl)}
    else:
        rep["by_mesh"] = {ob.name: tris(ob)}
    rep["triangles"] = sum(rep["by_mesh"].values())
    for o in bpy.context.scene.objects:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(out / "mug.glb"), export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_texcoords=True, export_materials="EXPORT", export_extras=False,
                              export_cameras=False, export_lights=False)
    (out / "build.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print("MUG_AI " + json.dumps(rep), flush=True)


if __name__ == "__main__":
    main()
