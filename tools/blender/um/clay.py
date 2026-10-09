"""The clay pass (inside Blender): a built character turned from the pack look into the approved clay look, static
plasticine (no boil), as round D of the faces lab made it (docs/assembly.md, "The clay look"):

- the head and everything on it (hair, extras, the scripted face) x1.3 about the Head joint, baked into the meshes
  with each vertex's Head share and faded out below the joint (glTF carries no scale constraint);
- every pack part welded, subdivided once and decimated to its kind's budget (material borders held), smooth shaded,
  pushed by the shared world-space lump field; open shoe collars and hat rims rolled thick;
- every material made clay (a procedural plasticine: flat colour x low-frequency value noise x a 2 cm mottle, thumb
  dents and fingerprint dents in the bump, roughness 0.72 to 0.88) or glossy (eye whites, pupils, irises, teeth);
  the noise reads the mesh attribute rest_pos (world position at rest), so it does not crawl under skinning;
- at most four bone weights per vertex (what glTF and the game skin with).

Call apply() in the rest position with the character at the origin, after the parts and the scripted face are built.
Static copies of the undecimated clothing (`sources`) are kept for the bake's pack-colour pass (um/claybake.py).
Ported from clay_lib.py, clay_parts.py and clay_bake.py of D:/prime-art-raw/research/2026-10-05-faces/lab/clay_d.
"""

import bmesh
import bpy
from mathutils import Vector, noise

from . import claylook as L
from .util import base_name, update

SOURCE_ROLES = ("top", "bottom", "shoes")  # clothing whose base colour the bake takes from the undecimated pack part


# ----------------------------------------------------------------------------------------------- materials
def _tree(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(p.outputs["BSDF"], out.inputs["Surface"])
    return nt, p


def gloss(mat, rgb, rough=0.2, spec=0.5):
    """Eye whites, pupils, teeth: the only glossy parts; a flat colour (the glTF export keeps it as is)."""
    nt, p = _tree(mat)
    p.inputs["Base Color"].default_value = (*rgb, 1.0)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Specular IOR Level"].default_value = spec
    mat.diffuse_color = (*rgb, 1.0)
    mat.roughness = rough
    mat["look"] = "gloss"
    return mat


def clay(mat, rgb, rough=0.8, sheen=0.03, sss=0.07, bump=0.48, dent_m=0.018):
    """Plasticine: the flat colour (node 'clay_rgb') x +-5 % value noise at about 14 cm x a +-4 % mottle at about 2 cm;
    the bump carries thumb dents (dent_m cells), fingerprint dents (6 mm) and a fine grain; roughness 0.72 to 0.88; a
    faint sheen and a little short red subsurface (neither survives glTF: about one level of 255). Every noise reads
    the attribute rest_pos directly (round D's static clay: the stop-motion boil is gone)."""
    nt, p = _tree(mat)
    N, Lk = nt.nodes, nt.links
    at = N.new("ShaderNodeAttribute")
    at.attribute_type = "GEOMETRY"
    at.attribute_name = "rest_pos"
    pos = at.outputs["Vector"]

    def tex(kind, scale, detail=None, feature=None):
        n = N.new(kind)
        if feature:
            n.feature = feature
        n.inputs["Scale"].default_value = scale
        if detail is not None:
            n.inputs["Detail"].default_value = detail
        Lk.new(pos, n.inputs["Vector"])
        return n

    lo = tex("ShaderNodeTexNoise", 7.0, 1.5)
    mot = tex("ShaderNodeTexNoise", 50.0, 1.0)
    vor = tex("ShaderNodeTexVoronoi", 1.0 / dent_m, feature="SMOOTH_F1")
    vor2 = tex("ShaderNodeTexVoronoi", 1.0 / 0.006, feature="SMOOTH_F1")
    fine = tex("ShaderNodeTexNoise", 140.0, 0.0)

    def math_node(op, a, b, c):
        n = N.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b, c)):
            if isinstance(v, float):
                n.inputs[i].default_value = v
            else:
                Lk.new(v, n.inputs[i])
        return n

    h1 = math_node("MULTIPLY_ADD", vor2.outputs["Distance"], 0.25, vor.outputs["Distance"])
    hsum = math_node("MULTIPLY_ADD", fine.outputs["Fac"], 0.05, h1.outputs[0])
    bmp = N.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump
    bmp.inputs["Distance"].default_value = 0.004
    Lk.new(hsum.outputs[0], bmp.inputs["Height"])
    Lk.new(bmp.outputs["Normal"], p.inputs["Normal"])
    col = N.new("ShaderNodeRGB")
    col.name = "clay_rgb"
    col.outputs[0].default_value = (*rgb, 1.0)

    def map_range(src, a, b, c, d):
        n = N.new("ShaderNodeMapRange")
        for name, v in (("From Min", a), ("From Max", b), ("To Min", c), ("To Max", d)):
            n.inputs[name].default_value = v
        Lk.new(src, n.inputs["Value"])
        return n

    val = map_range(lo.outputs["Fac"], 0.25, 0.75, 0.95, 1.05)
    val2 = map_range(mot.outputs["Fac"], 0.3, 0.7, 0.96, 1.04)
    vv = math_node("MULTIPLY", val.outputs["Result"], val2.outputs["Result"], 0.0)
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    Lk.new(col.outputs[0], mix.inputs[6])
    Lk.new(vv.outputs[0], mix.inputs[7])
    Lk.new(mix.outputs[2], p.inputs["Base Color"])
    rr = map_range(lo.outputs["Fac"], 0.25, 0.75, rough - 0.08, rough + 0.08)
    Lk.new(rr.outputs["Result"], p.inputs["Roughness"])
    p.inputs["Specular IOR Level"].default_value = 0.35
    p.inputs["Sheen Weight"].default_value = sheen
    Lk.new(col.outputs[0], p.inputs["Sheen Tint"])
    p.inputs["Sheen Roughness"].default_value = 0.5
    p.inputs["Subsurface Weight"].default_value = sss
    p.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
    p.inputs["Subsurface Scale"].default_value = 0.012
    mat.diffuse_color = (*rgb, 1.0)
    mat.roughness = rough
    mat["look"] = "clay"
    return mat


def is_clay(mat):
    return bool(mat is not None and mat.get("look") == "clay")


def glossy_roughness(name):
    low = base_name(name).lower()
    return next((r for k, r in L.GLOSSY.items() if k in low), None)


def convert_materials(cid, o, cache):
    """Every slot of o: a clay or glossy copy of its material (one per source material and character). The skin keeps
    a name ending in _skin (the bake's skin mask finds it by name)."""
    for s in o.material_slots:
        m = s.material
        if m is None or m.get("look") in ("clay", "gloss", "baked"):
            continue
        if m.name not in cache:
            base = base_name(m.name)
            rgb = tuple(round(c, 4) for c in m.diffuse_color[:3])
            rough = glossy_roughness(base)
            name = f"{cid}_clay_skin" if base.endswith("_skin") else f"{cid}_clay_{base}"
            nm = bpy.data.materials.get(name) or bpy.data.materials.new(name)
            cache[m.name] = gloss(nm, rgb, rough) if rough is not None else clay(nm, rgb)
        s.material = cache[m.name]


# ----------------------------------------------------------------------------------------------- geometry
def wscale(o):
    return sum(o.matrix_world.to_scale()) / 3.0


def tris(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def smooth_shade(me):
    for name in ("sharp_face", "sharp_edge", "custom_normal"):
        a = me.attributes.get(name)
        if a is not None:
            me.attributes.remove(a)
    me.shade_smooth()


def weld(o, dist_m=1e-5):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist_m / wscale(o))
    n1 = len(bm.verts)
    bm.to_mesh(o.data)
    bm.free()
    smooth_shade(o.data)
    o.data.update()
    return n0 - n1


def _without_armature(o):
    off = [m for m in o.modifiers if m.type == "ARMATURE" and m.show_viewport]
    for m in off:
        m.show_viewport = False
    return off


def eval_tris(o):
    off = _without_armature(o)
    d = bpy.context.evaluated_depsgraph_get()
    d.update()
    ev = o.evaluated_get(d)
    me = ev.to_mesh()
    n = tris(me)
    ev.to_mesh_clear()
    for m in off:
        m.show_viewport = True
    return n


def apply_modifiers(o):
    """Applies every modifier but the Armature one on the rest mesh; vertex groups survive."""
    off = _without_armature(o)
    d = bpy.context.evaluated_depsgraph_get()
    d.update()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(d), preserve_all_data_layers=True, depsgraph=d)
    for m in list(o.modifiers):
        if m.type != "ARMATURE":
            o.modifiers.remove(m)
    for m in off:
        m.show_viewport = True
    old, o.data = o.data, me
    me.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    smooth_shade(o.data)
    return tris(o.data)


BORDER_FACTORS = (20.0, 6.0, 2.0, 0.7, 0.0)


def border_group(o):
    """A vertex group 'clay_border' on every vertex where two materials meet: the decimation keeps those, so colour
    borders stay straight instead of zig-zagging."""
    fm = {}
    for p in o.data.polygons:
        for v in p.vertices:
            fm.setdefault(v, set()).add(p.material_index)
    border = sorted(v for v, ms in fm.items() if len(ms) > 1)
    if not border:
        return 0
    g = o.vertex_groups.get("clay_border") or o.vertex_groups.new(name="clay_border")
    g.add(border, 1.0, "REPLACE")
    return len(border)


def clay_pass(o, target, rim=0.0, subdiv=1):
    """weld -> optional rim (Solidify, rim only, inward) -> subdivide -> decimate to target -> apply -> smooth."""
    info = {"tris_pack": tris(o.data), "welded_vertices": weld(o)}
    sc = wscale(o)
    if rim:
        so = o.modifiers.new("clay_rim", "SOLIDIFY")
        so.thickness = rim / sc
        so.offset = -1.0
        so.use_even_offset = True
        so.use_rim = True
        so.use_rim_only = True
        info["rim_mm"] = round(rim * 1000, 1)
    sub = o.modifiers.new("clay_sub", "SUBSURF")
    sub.levels = sub.render_levels = subdiv
    sub.quality = 3
    t_sub = eval_tris(o)
    ratio = min(1.0, target / max(1, t_sub))
    apply_modifiers(o)
    if ratio < 0.999:
        info["border_vertices"] = border_group(o)
        dec = o.modifiers.new("clay_dec", "DECIMATE")
        dec.ratio = ratio
        info["border_factor"] = 0.0
        if info["border_vertices"]:
            dec.vertex_group = "clay_border"
            for f in BORDER_FACTORS:  # the strongest hold on the material borders that still meets the budget
                dec.vertex_group_factor = f
                info["border_factor"] = f
                if f == 0.0 or eval_tris(o) <= target * 1.04:
                    break
            if info["border_factor"] == 0.0:
                dec.vertex_group = ""
        apply_modifiers(o)
    g = o.vertex_groups.get("clay_border")
    if g is not None:
        o.vertex_groups.remove(g)
    info.update(tris_subdivided=t_sub, decimate_ratio=round(ratio, 3), tris=tris(o.data))
    return info


def lump(o, amp, freq=L.LUMP_FREQ, seed=L.LUMP_SEED):
    """The shared lump field: each vertex pushed along its normal by Perlin noise read in world rest space."""
    me = o.data
    mw = o.matrix_world
    inv = mw.inverted()
    nm = mw.to_3x3().inverted().transposed()
    off = Vector((seed * 17.31, seed * 5.13, seed * 11.77))
    for v in me.vertices:
        p = mw @ v.co
        n = (nm @ v.normal).normalized()
        v.co = inv @ (p + n * (amp * noise.noise(p * freq + off)))
    me.update()


def add_rest(o):
    """rest_pos: each vertex's world position now (at rest, metres), for the clay noise."""
    me = o.data
    mw = o.matrix_world
    flat = []
    for v in me.vertices:
        flat.extend(mw @ v.co)
    a = me.attributes.get("rest_pos") or me.attributes.new("rest_pos", "FLOAT_VECTOR", "POINT")
    a.data.foreach_set("vector", flat)


def head_scale(o, arm, s, fade=L.SCALE_FADE):
    """x s about the Head joint for each vertex's Head share (Head and its children over all its weights), faded to
    nothing over `fade` below the joint (the clay_parts form: the same for the head and every head item keeps them in
    register). Returns the number of vertices moved and the largest move in mm."""
    if abs(s - 1.0) < 1e-9:
        return {"scale": s, "vertices_scaled": 0, "largest_move_mm": 0.0}
    names = {"Head"} | {b.name for b in arm.data.bones["Head"].children_recursive}
    idx = {g.index for g in o.vertex_groups if g.name in names}
    joint = arm.matrix_world @ arm.data.bones["Head"].head_local
    mw = o.matrix_world
    inv = mw.inverted()
    moved, most = 0, 0.0
    for v in o.data.vertices:
        tot = sum(g.weight for g in v.groups)
        w = sum(g.weight for g in v.groups if g.group in idx) / tot if tot > 1e-9 else 0.0
        if w <= 0:
            continue
        p = mw @ v.co
        t = min(1.0, max(0.0, (p.z - (joint.z - fade)) / fade))
        k = w * t * t * (3 - 2 * t)
        if k <= 1e-4:
            continue
        q = p + (p - joint) * ((s - 1.0) * k)
        most = max(most, (q - p).length)
        v.co = inv @ q
        moved += 1
    o.data.update()
    return {"scale": s, "fade_m": fade, "vertices_scaled": moved, "largest_move_mm": round(most * 1000, 1)}


def limit_influences(o, n=4):
    """At most n bone weights per vertex, renormalised. Returns how many vertices had more."""
    names = {g.index: g.name for g in o.vertex_groups}
    bones = set(o.parent.data.bones.keys()) if o.parent and o.parent.type == "ARMATURE" else set(names.values())
    over = 0
    for v in o.data.vertices:
        ws = sorted(((g.weight, g.group) for g in v.groups if names.get(g.group) in bones and g.weight > 0), reverse=True)
        if len(ws) > n:
            over += 1
            for _, gi in ws[n:]:
                o.vertex_groups[gi].remove([v.index])
            ws = ws[:n]
        tot = sum(w for w, _ in ws)
        if ws and abs(tot - 1.0) > 1e-6:
            for w, gi in ws:
                o.vertex_groups[gi].add([v.index], w / tot, "REPLACE")
    return over


def static_copy(o, name, coll):
    """The evaluated rest mesh of o in world coordinates as a hidden static object (a bake source)."""
    d = bpy.context.evaluated_depsgraph_get()
    d.update()
    ev = o.evaluated_get(d)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=d)
    me.transform(ev.matrix_world)
    me.name = name
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.hide_render = True
    return ob


# ----------------------------------------------------------------------------------------------- the pass
def apply(cid, arm, parts, cfg, kinds=None):
    """The clay pass on a built character (rest position, at the origin). parts: {role: object}; kinds maps an extra's
    role to a part kind (its budget and lump). Returns (report, sources): sources are hidden static copies of the
    undecimated clothing for the bake, in the collection '<cid>_clay_sources'."""
    arm.data.pose_position = "REST"
    update()
    src_coll = bpy.data.collections.new(cid + "_clay_sources")
    bpy.context.scene.collection.children.link(src_coll)
    sources = {r: static_copy(parts[r], f"{cid}_src_{r}", src_coll) for r in SOURCE_ROLES if r in parts}
    rep = {"head_scale": cfg["head_scale"], "parts": {}}
    cache = {}
    for role, o in parts.items():
        info = {}
        head_item = role in L.HEAD_ROLES or role not in ("top", "bottom", "shoes")
        if head_item:
            info["head_scale"] = head_scale(o, arm, cfg["head_scale"])
        if role in L.FACE_ROLES:  # the repo's scripted face: smooth already; the face kit (art #42 B) replaces it
            info["tris"] = tris(o.data)
            smooth_shade(o.data)
        else:
            kind = L.kind_of(role, kinds)
            info.update(clay_pass(o, int(cfg["budget"].get(kind, L.BUDGET[L.DEFAULT_KIND])), rim=L.RIMS.get(kind, 0.0)))
            lump(o, cfg["lump"].get(kind, L.LUMP[L.DEFAULT_KIND]))
            smooth_shade(o.data)
            info["kind"] = kind
        add_rest(o)
        convert_materials(cid, o, cache)
        info["influences_limited"] = limit_influences(o, 4)
        rep["parts"][role] = info
    rep["joined_into_head"] = join_into_head(parts)
    update()
    rep["triangles"] = {r: tris(o.data) for r, o in parts.items()}
    rep["triangles_total"] = sum(rep["triangles"].values())
    rep["materials"] = sorted({m.name for m in cache.values()})
    return rep, sources


def join_into_head(parts, roles=L.JOIN_INTO_HEAD):
    """The face parts in roles joined into the head object (one atlas, one surface; vertex groups merge by name) and
    removed from parts. Returns the roles joined."""
    head = parts["head"]
    others = [parts[r] for r in roles if r in parts]
    if not others:
        return []
    objs = [head] + others
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = head
    with bpy.context.temp_override(active_object=head, object=head, selected_objects=objs, selected_editable_objects=objs):
        bpy.ops.object.join()
    done = [r for r in roles if r in parts]
    for r in done:
        del parts[r]
    return done


def remove_sources(sources):
    for o in sources.values():
        me = o.data
        coll = o.users_collection
        bpy.data.objects.remove(o, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)
        for c in coll:
            if not c.objects and c.name in bpy.data.collections:
                bpy.data.collections.remove(c)
