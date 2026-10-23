"""Builds the ship's pieces, one GLB each (art #263, docs/ship.md): the build harness the `ship --build` command runs.
SHARED and FROZEN after the foundation step (additions only, in separate functions).

    blender -b --python ship_build.py -- --request <request.json> --out <dir>

request.json (tools/runner/commands/ship.py): {"layout": <ship.toml with both lanes' pieces>, "only": [ids]}. Each
piece's builder is a function of its lane's module (interior: ship_interior.py, exterior: ship_hull.py; a lane may add
modules ship_interior_*.py / ship_hull_*.py and list them in its MODULES) called as builder(args, layout) -> [parts]
(ship_lib.part). Writes <out>/<id>.glb per piece and <out>/build_report.json: per piece its triangles, objects,
materials and bounds in Godot's frame (x, h, y)."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ship_hull  # noqa: E402
import ship_interior  # noqa: E402
import ship_lib  # noqa: E402

LANES = {"interior": ship_interior, "exterior": ship_hull}
EXPORT = {"export_format": "GLB", "use_selection": False, "use_visible": False, "use_renderable": False,
          "use_active_collection": False, "export_yup": True, "export_apply": True, "export_skins": False,
          "export_animations": False, "export_morph": False, "export_cameras": False, "export_lights": False,
          "export_materials": "EXPORT", "export_texcoords": True, "export_normals": True}


def builder(lane: str, name: str):
    for mod in [LANES[lane], *getattr(LANES[lane], "MODULES", [])]:
        if hasattr(mod, name):
            return getattr(mod, name)
    raise SystemExit(f"ship_build: no builder {name} in the {lane} lane")


def clear() -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)


def make(p: dict):
    mesh = bpy.data.meshes.new(p["name"])
    mesh.from_pydata([(x, -y, h) for x, y, h in p["verts"]], [], p["faces"])
    mesh.validate()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    if p["solid"]:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if p.get("smooth_deg"):   # lens polish: smooth across shallow edges, sharp over smooth_deg (the lens's plates)
        lim = math.radians(p["smooth_deg"])
        for e in bm.edges:
            e.smooth = e.is_manifold and e.calc_face_angle(math.pi) <= lim
        for f in bm.faces:
            f.smooth = True
    bm.to_mesh(mesh)
    bm.free()
    if p.get("smooth"):  # a part shaded smooth (the nozzle pods' shells, the canopy glass)
        for poly in mesh.polygons:
            poly.use_smooth = True
    mesh.materials.append(ship_lib.material(p["mat"]))
    obj = bpy.data.objects.new(p["name"], mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def import_glb(p: dict) -> list:
    """A part made elsewhere (way A of station 1: Meshy's cleaned vent body): {"name", "glb", "offset": (x, y, h),
    "mirror_u": bool}. Every mesh of the GLB, its own materials and textures kept, joined into one object named
    p["name"], moved by offset (plan x, y, h) and mirrored in x when mirror_u (its normals flipped back)."""
    from mathutils import Matrix
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=p["glb"])
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    for o in meshes:
        o.data.transform(o.matrix_world)
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    for o in new:
        if o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
    obj = meshes[0]
    if len(meshes) > 1:
        with bpy.context.temp_override(active_object=obj, selected_editable_objects=meshes):
            bpy.ops.object.join()
    x, y, h = p.get("offset", (0.0, 0.0, 0.0))
    m = Matrix.Translation((x, -y, h))
    if p.get("mirror_u"):
        m = m @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
    obj.data.transform(m)
    if p.get("mirror_u"):
        obj.data.flip_normals()
    obj.name = obj.data.name = p["name"]
    for c in obj.users_collection:
        if c is not bpy.context.scene.collection:
            c.objects.unlink(obj)
    if obj.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(obj)
    return obj


def rig(objs: list, parts: list[dict]) -> None:
    """Moving parts (step 2, the stations; docs/props.md "Conventions"): a part with "origin" (plan x, y, h in the
    piece's frame) gets its object's origin there, its hinge or rest point, the mesh kept in place; a part with
    "parent" (another part's name) is parented to that part's object, its place kept. Parts without either are
    unchanged."""
    from mathutils import Matrix
    for o, p in zip(objs, parts):
        if p.get("origin"):
            x, y, h = p["origin"]
            o.data.transform(Matrix.Translation((-x, y, -h)))
            o.location = (x, -y, h)
    bpy.context.view_layer.update()
    by_name = {p["name"]: o for o, p in zip(objs, parts)}
    for o, p in zip(objs, parts):
        if p.get("parent"):
            par = by_name[p["parent"]]
            o.parent = par
            o.matrix_parent_inverse = par.matrix_world.inverted()
    bpy.context.view_layer.update()


def build(piece: dict, layout: dict, out: Path) -> dict:
    clear()
    parts = builder(piece["lane"], piece["builder"])(piece.get("args", {}), layout)
    for p in parts:  # Godot's importer gives a `-col` mesh a static body with its trimesh (one-sided: solids face out)
        if piece.get("collide"):
            p["name"] += "-col"
    objs = [import_glb(p) if p.get("glb") else make(p) for p in parts]
    rig(objs, parts)
    glb = out / f"{piece['id']}.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb), **EXPORT)
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    return {"glb": glb.as_posix(), "lane": piece["lane"],
            "triangles": sum(len(pl.vertices) - 2 for o in objs for pl in o.data.polygons),
            "objects": [o.name for o in objs], "materials": sorted({p["mat"] for p in parts if p.get("mat")} | {m.name for o in objs for m in o.data.materials if m}),
            "bounds": {"min": [lo[0], lo[2], -hi[1]], "max": [hi[0], hi[2], -lo[1]]}}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    request = json.loads(Path(argv[argv.index("--request") + 1]).read_text(encoding="utf-8"))
    out = Path(argv[argv.index("--out") + 1])
    out.mkdir(parents=True, exist_ok=True)
    layout = request["layout"]
    only = set(request.get("only") or [])
    report = {"pieces": {}}
    for piece in layout["pieces"]:
        if only and piece["id"] not in only:
            continue
        report["pieces"][piece["id"]] = build(piece, layout, out)
        print(f"SHIP built {piece['id']}: {report['pieces'][piece['id']]['triangles']} triangles")
    (out / "build_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    print(f"SHIP done {len(report['pieces'])} pieces")


if __name__ == "__main__":
    main()
