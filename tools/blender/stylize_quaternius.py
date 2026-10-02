"""Stylizes the CC0 Quaternius base body toward our direction, keeping its rig, weights and finger chains.

Run through the runner (`tools/run.py stylize-quaternius`), which writes the plan; or directly:
    blender -b --factory-startup --python-exit-code 1 --python tools/blender/stylize_quaternius.py -- PLAN.json

The plan (tools/runner/commands/_stylize.py) names the bones in the rig's own names. Steps, in order:
 1. import the glTF (vertices merged at UV seams, no bone display shape) and delete the helper and face meshes
    (Icosphere, Eyes, Eyebrows), remembering where the eyes were;
 2. reshape like an armature would: each slimmed bone scales its vertices across the bone (the bone's length and the
    joints stay), the head bone scales its vertices uniformly about the neck joint; weights blend the two;
 3. a blank face: the eye sockets are smoothed flat and the mouth is filled up to a surface fitted to the face
    above and below it (never pulled in, so no notch under the nose in profile);
 4. a longer nose: the tip and its surroundings are pulled forward and a little down with a smooth falloff;
 5. softer muscles: Taubin smoothing (no shrinking) on the torso, shoulders, arms, legs and neck, by weight;
 6. the whole figure (mesh and bones) scaled to the plan's height;
 7. one flat skin material and flat shorts: the faces whose texture colour is a dark grey give the shorts' waist and
    hem heights, the mesh is cut along those two planes and the band between them becomes the shorts; textures,
    vertex colours and the old materials go;
 8. decimated (collapse, symmetric in X) to the target triangles when above it, keeping the shorts' border dense,
    then the weights cleaned: at most 4 per vertex, none under 0.01, normalized;
 9. exported as GLB, re-imported, and the rig probed: each probe bone is turned and the moved vertices counted.
Writes the GLB and the plan's info.json.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HELPER_COLLECTION = "glTF_not_exported"


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def base_name(obj: bpy.types.Object) -> str:
    return obj.name.split(".")[0]


def import_gltf(path: str) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path, merge_vertices=True, disable_bone_shape=True)


def armature_and_meshes() -> tuple[bpy.types.Object, list[bpy.types.Object]]:
    armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    if len(armatures) != 1:
        raise RuntimeError(f"expected one armature, found {len(armatures)}")
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"
              and any(m.type == "ARMATURE" for m in o.modifiers)]
    if not meshes:
        raise RuntimeError("no skinned mesh")
    for obj in (armatures[0], *meshes):
        if not np.allclose(np.array(obj.matrix_world), np.eye(4), atol=1e-5):
            raise RuntimeError(f"{obj.name} has a transform; this script expects applied transforms")
    return armatures[0], meshes


def drop_objects(names: list[str]) -> tuple[list[str], list[list[float]]]:
    """Deletes the named meshes and the importer's helpers; returns what went and the eye centres (left, right)."""
    dropped, eyes = [], []
    for obj in list(bpy.context.scene.objects):
        helper = any(c.name == HELPER_COLLECTION for c in obj.users_collection)
        if obj.type == "MESH" and (base_name(obj) in names or helper):
            if base_name(obj) == "Eyes":
                points = np.array([obj.matrix_world @ v.co for v in obj.data.vertices])
                for side in (points[:, 0] > 0, points[:, 0] < 0):
                    if side.any():
                        eyes.append(points[side].mean(axis=0).tolist())
            dropped.append(obj.name)
            bpy.data.objects.remove(obj)
    return dropped, eyes


def clear_custom_normals(obj: bpy.types.Object) -> None:
    """The imported normals no longer fit once vertices move: shade smooth from the geometry instead."""
    mesh = obj.data
    if mesh.has_custom_normals:
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for polygon in mesh.polygons:
        polygon.use_smooth = True


def positions(mesh: bpy.types.Mesh) -> np.ndarray:
    co = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
    mesh.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def set_positions(mesh: bpy.types.Mesh, co: np.ndarray) -> None:
    mesh.vertices.foreach_set("co", co.astype(np.float32).ravel())
    mesh.update()


def weight_matrix(obj: bpy.types.Object, bones: list[str]) -> np.ndarray:
    """(vertices, bones) weights of the named bones, each row normalized over all of the vertex's groups."""
    column = {name: i for i, name in enumerate(bones)}
    names = {g.index: g.name for g in obj.vertex_groups}
    weights = np.zeros((len(obj.data.vertices), len(bones)))
    totals = np.zeros(len(obj.data.vertices))
    for vertex in obj.data.vertices:
        for group in vertex.groups:
            totals[vertex.index] += group.weight
            col = column.get(names.get(group.group, ""))
            if col is not None:
                weights[vertex.index, col] += group.weight
    return weights / np.where(totals > 0, totals, 1.0)[:, None]


def edges_of(mesh: bpy.types.Mesh) -> np.ndarray:
    edges = np.empty(len(mesh.edges) * 2, dtype=np.int64)
    mesh.edges.foreach_get("vertices", edges)
    return edges.reshape(-1, 2)


def boundary_vertices(mesh: bpy.types.Mesh) -> np.ndarray:
    """A mask of the vertices on open edges (edges with one face)."""
    count: dict[tuple[int, int], int] = {}
    for polygon in mesh.polygons:
        for key in polygon.edge_keys:
            count[key] = count.get(key, 0) + 1
    mask = np.zeros(len(mesh.vertices), dtype=bool)
    for (a, b), n in count.items():
        if n == 1:
            mask[a] = mask[b] = True
    return mask


def laplacian(co: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """The umbrella operator: the mean of each vertex's neighbours minus the vertex."""
    total = np.zeros_like(co)
    degree = np.zeros(len(co))
    np.add.at(total, edges[:, 0], co[edges[:, 1]])
    np.add.at(total, edges[:, 1], co[edges[:, 0]])
    np.add.at(degree, edges[:, 0], 1)
    np.add.at(degree, edges[:, 1], 1)
    return total / np.where(degree > 0, degree, 1)[:, None] - co


def smooth(co: np.ndarray, edges: np.ndarray, mask: np.ndarray, iterations: int, taubin: bool) -> np.ndarray:
    """Masked smoothing; Taubin's lambda/mu pair keeps the volume, plain Laplacian flattens dents."""
    co = co.copy()
    for _ in range(iterations):
        co += 0.5 * mask[:, None] * laplacian(co, edges)
        if taubin:
            co += -0.53 * mask[:, None] * laplacian(co, edges)
    return co


def falloff(co: np.ndarray, centre: np.ndarray, radius: float) -> np.ndarray:
    d = np.linalg.norm(co - centre, axis=1) / radius
    return np.where(d < 1.0, (1.0 - d**2) ** 2, 0.0)


def reshape(plan: dict, armature: bpy.types.Object, obj: bpy.types.Object, co: np.ndarray) -> np.ndarray:
    """Step 2: per-bone slimming across the bone and the head's uniform scale, blended by weight."""
    bones = armature.data.bones
    targets: dict[str, Matrix] = {}
    for name, factor in plan["slim"].items():
        if name in bones:
            rest = bones[name].matrix_local
            targets[name] = rest @ Matrix.Diagonal((factor, 1.0, factor, 1.0)) @ rest.inverted()
    head = bones[plan["head_bone"]].head_local
    targets[plan["head_bone"]] = (Matrix.Translation(head) @ Matrix.Scale(plan["head_scale"], 4)
                                  @ Matrix.Translation(-head))
    names = list(targets)
    weights = weight_matrix(obj, names)
    homogeneous = np.hstack([co, np.ones((len(co), 1))])
    delta = np.zeros_like(co)
    for i, name in enumerate(names):
        change = np.array(targets[name]) - np.eye(4)
        delta += weights[:, i : i + 1] * (homogeneous @ change.T)[:, :3]
    return co + delta


def head_transform(plan: dict, armature: bpy.types.Object, point: list[float]) -> np.ndarray:
    head = np.array(armature.data.bones[plan["head_bone"]].head_local)
    return head + (np.array(point) - head) * plan["head_scale"]


def ramp(value: np.ndarray, full: float, zero: float) -> np.ndarray:
    """1 up to full, a smooth step down to 0 at zero (full < zero)."""
    t = np.clip((value - full) / (zero - full), 0.0, 1.0)
    return 1.0 - t * t * (3.0 - 2.0 * t)


def mouth_slit(co: np.ndarray, head_w: np.ndarray, eye: np.ndarray, scale: float) -> np.ndarray | None:
    """The mouth's slit: the deepest front-facing centre-line vertex 5.5 to 10 cm under the eyes (between the nose
    and the chin, the lips stand forward and the slit sits back)."""
    window = ((np.abs(co[:, 0]) < 0.006) & (head_w > 0.5) & (co[:, 2] < eye[2] - 0.055 * scale)
              & (co[:, 2] > eye[2] - 0.1 * scale) & (co[:, 1] < eye[1] + 0.01 * scale))
    if not window.any():
        return None
    index = np.nonzero(window)[0]
    return co[index[np.argmax(co[index, 1])]].copy()


def mouth_surface(co: np.ndarray, head_w: np.ndarray, slit: np.ndarray, scale: float) -> np.ndarray:
    """The face's depth (Y) over the mouth as if it had none: a surface symmetric in X fitted (least squares) to the
    front of the face just above the lips (the philtrum) and just below them (the chin); returns Y for every vertex."""
    dz = co[:, 2] - slit[2]

    def features(points: np.ndarray, rise: np.ndarray) -> np.ndarray:
        x2 = points[:, 0] ** 2
        return np.stack([np.ones(len(points)), rise, x2, x2 * rise, x2 * x2], axis=1)

    front = (head_w > 0.5) & (np.abs(co[:, 0]) < 0.04 * scale) & (co[:, 1] < slit[1] - 0.006 * scale)
    bands = front & (((dz > 0.010 * scale) & (dz < 0.018 * scale)) | ((dz > -0.032 * scale) & (dz < -0.016 * scale)))
    coef, *_ = np.linalg.lstsq(features(co[bands], dz[bands]), co[bands, 1], rcond=None)
    return features(co, dz) @ coef


def fill_mouth(co: np.ndarray, edges: np.ndarray, head_w: np.ndarray, slit: np.ndarray,
               scale: float) -> tuple[np.ndarray, int]:
    """Closes the mouth by filling it, never by pulling it in: (1) the inside of the mouth, every vertex well behind
    the fitted face surface, relaxes into a membrane spanning the lips (the lips held still), (2) the lips and that
    membrane move onto the surface, fully in the middle and fading out at the corners, (3) a light Taubin smoothing
    (no shrinking) removes the creases. Returns the new positions and how many vertices it moved."""

    def weight(points: np.ndarray, surface: np.ndarray) -> np.ndarray:
        dz = points[:, 2] - slit[2]
        across = ramp(np.abs(points[:, 0]), 0.024 * scale, 0.036 * scale)
        up = ramp(dz, 0.007 * scale, 0.012 * scale) * ramp(-dz, 0.012 * scale, 0.02 * scale)
        return across * up * (head_w > 0.5) * (points[:, 1] < surface + 0.05 * scale)

    before = co.copy()
    surface = mouth_surface(co, head_w, slit, scale)
    inside = (weight(co, surface) > 0) & (co[:, 1] > surface + 0.004 * scale)
    co = smooth(co, edges, inside.astype(float), 300, taubin=False)
    surface = mouth_surface(co, head_w, slit, scale)
    co[:, 1] += weight(co, surface) * (surface - co[:, 1])
    region = falloff(co, slit, 0.04 * scale) * head_w
    co = smooth(co, edges, region, 20, taubin=True)
    return co, int((np.linalg.norm(co - before, axis=1) > 1e-4).sum())


def mouth_dent(co: np.ndarray, head_w: np.ndarray, slit: np.ndarray, scale: float, step: float = 0.004) -> float:
    """How far (m) the centre line's front between the chin and the philtrum sits behind the straight line joining
    them: the depth an open mouth or a notch under the nose shows in profile (about 0 for a blank face). The profile
    runs up from 3.5 cm under the slit and stops under the nose, where the front jumps forward by more than 1 cm."""
    centre = (np.abs(co[:, 0]) < 0.006) & (head_w > 0.5)
    profile: list[tuple[float, float]] = []
    for low in np.arange(slit[2] - 0.035 * scale, slit[2] + 0.02 * scale, step):
        band = centre & (co[:, 2] >= low) & (co[:, 2] < low + step)
        if band.any():
            y = float(co[band, 1].min())
            if profile and low > slit[2] and y < profile[-1][1] - 0.01 * scale:
                break
            profile.append((low + step / 2, y))
    if len(profile) < 3:
        return 0.0
    (z0, y0), (z1, y1) = profile[0], profile[-1]
    return max(0.0, max(y - (y0 + (y1 - y0) * (z - z0) / (z1 - z0)) for z, y in profile))


def blank_face(co: np.ndarray, edges: np.ndarray, eyes: list[np.ndarray], head_w: np.ndarray,
               scale: float) -> tuple[np.ndarray, dict]:
    """Step 3: smooths the eye sockets flat (plain Laplacian, which fills dents) and fills the mouth (fill_mouth).
    The mouth's slit is found below the eyes, so a source without an eye mesh keeps its face."""
    if not eyes:
        return co, {"smoothed": 0, "mouth": None, "note": "no eye mesh: nothing to flatten"}
    mask = np.zeros(len(co))
    for eye in eyes:
        mask = np.maximum(mask, falloff(co, np.array(eye), 0.032 * scale))
    mask *= head_w
    co = smooth(co, edges, np.clip(mask * 1.6, 0.0, 1.0), 60, taubin=False)
    smoothed = int((mask > 0.01).sum())
    slit = mouth_slit(co, head_w, np.mean(eyes, axis=0), scale)
    if slit is not None:
        co, moved = fill_mouth(co, edges, head_w, slit, scale)
        smoothed += moved
    return co, {"smoothed": smoothed, "mouth": slit}


def longer_nose(co: np.ndarray, head_w: np.ndarray, eyes: list[np.ndarray], length: float,
                scale: float) -> tuple[np.ndarray, dict]:
    """Step 4: pulls the nose tip forward (-Y) and a little down, with a smooth falloff."""
    candidates = (head_w > 0.6) & (np.abs(co[:, 0]) < 0.006)
    if eyes:
        eye_z = float(np.mean([e[2] for e in eyes]))
        candidates &= (co[:, 2] < eye_z) & (co[:, 2] > eye_z - 0.07 * scale)
    if not candidates.any():
        return co, {"tip": None}
    index = np.nonzero(candidates)[0]
    tip = co[index[np.argmin(co[index, 1])]].copy()
    direction = np.array([0.0, -1.0, -0.35])
    direction /= np.linalg.norm(direction)
    weight = falloff(co, tip, 0.03 * scale) * head_w
    return co + weight[:, None] * direction * length, {"tip": tip, "moved": int((weight > 0.01).sum())}


def scale_bones(armature: bpy.types.Object, factor: float, head_bone: str, head_scale: float) -> None:
    """Step 6 for the skeleton: every head and tail scaled about the origin; the head bone's length grows with the
    head. New positions are computed first: setting a connected child's head also moves its parent's tail."""
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    bones = armature.data.edit_bones
    new = {}
    for bone in bones:
        tail = bone.tail.copy()
        if bone.name == head_bone:
            tail = bone.head + (bone.tail - bone.head) * head_scale
        new[bone.name] = (bone.head * factor, tail * factor)
    for bone in bones:
        bone.head, bone.tail = new[bone.name]
    bpy.ops.object.mode_set(mode="OBJECT")


def triangles(objects: list[bpy.types.Object]) -> int:
    return sum(len(p.vertices) - 2 for o in objects for p in o.data.polygons)


KEEP_GROUP = "decimate_keep"


def mark_material_borders(obj: bpy.types.Object) -> int:
    """A vertex group on the vertices of faces next to the border between two materials (and one ring around
    them), so decimation keeps the shorts' edge as dense as the source; returns how many vertices it holds."""
    mesh = obj.data
    material = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("material_index", material)
    by_edge: dict[tuple[int, int], set[int]] = {}
    for polygon in mesh.polygons:
        for key in polygon.edge_keys:
            by_edge.setdefault(key, set()).add(int(material[polygon.index]))
    border = {v for key, kinds in by_edge.items() if len(kinds) > 1 for v in key}
    for _ in range(2):
        border |= {v for polygon in mesh.polygons if border.intersection(polygon.vertices) for v in polygon.vertices}
    group = obj.vertex_groups.new(name=KEEP_GROUP)
    if border:
        group.add(sorted(border), 1.0, "REPLACE")
    return len(border)


def decimate(objects: list[bpy.types.Object], armature: bpy.types.Object, target: int) -> float:
    """Step 8: collapse decimation, symmetric in X; the armature modifier is taken off while it is applied. The
    vertices in KEEP_GROUP are protected: with the group inverted, an edge between two of them costs its length
    more, so the collapse spends its triangles elsewhere first."""
    total = triangles(objects)
    if total <= target:
        return 1.0
    ratio = target / total
    for obj in objects:
        for modifier in [m for m in obj.modifiers if m.type == "ARMATURE"]:
            obj.modifiers.remove(modifier)
        modifier = obj.modifiers.new("Decimate", "DECIMATE")
        modifier.decimate_type = "COLLAPSE"
        modifier.ratio = ratio
        modifier.use_symmetry = True
        modifier.symmetry_axis = "X"
        modifier.use_collapse_triangulate = True
        if KEEP_GROUP in obj.vertex_groups:
            modifier.vertex_group = KEEP_GROUP
            modifier.invert_vertex_group = True
            modifier.vertex_group_factor = 1.0
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        skin = obj.modifiers.new("Armature", "ARMATURE")
        skin.object = armature
        skin.use_vertex_groups = True
    return ratio


def clean_weights(obj: bpy.types.Object, limit: int = 4, minimum: float = 0.01) -> int:
    """At most limit weights per vertex, none under minimum, normalized; returns how many vertices changed."""
    groups = obj.vertex_groups
    changed = 0
    for vertex in obj.data.vertices:
        entries = sorted(((g.weight, g.group) for g in vertex.groups if g.weight > 0), reverse=True)
        keep = [(w, g) for w, g in entries[:limit] if w >= minimum] or entries[:1]
        total = sum(w for w, _ in keep)
        current = {g.group: g.weight for g in vertex.groups}
        wanted = {g: w / total for w, g in keep} if total > 0 else {}
        if any(abs(current.get(g, 0.0) - w) > 1e-6 for g, w in wanted.items()) or set(current) - set(wanted):
            changed += 1
            for g in set(current) - set(wanted):
                groups[g].remove([vertex.index])
            for g, w in wanted.items():
                groups[g].add([vertex.index], w, "REPLACE")
    return changed


def base_colour_image(material: bpy.types.Material | None) -> bpy.types.Image | None:
    """The image feeding a material's Base Color, through any nodes between."""
    if material is None or material.node_tree is None:
        return None
    bsdf = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return None
    todo, seen = [bsdf.inputs["Base Color"]], set()
    while todo:
        socket = todo.pop()
        for link in socket.links:
            node = link.from_node
            if node.name in seen:
                continue
            seen.add(node.name)
            if node.type == "TEX_IMAGE" and node.image and node.image.size[0] > 0:
                return node.image
            todo.extend(node.inputs)
    return None


def shorts_faces(obj: bpy.types.Object) -> np.ndarray:
    """Step 7: a mask of the faces whose base-colour texel at the face's UV centre is a dark grey (the shorts),
    cleaned by two majority passes over neighbouring faces."""
    mesh = obj.data
    mask = np.zeros(len(mesh.polygons), dtype=bool)
    image = base_colour_image(mesh.materials[0] if mesh.materials else None)
    if image is None or not mesh.uv_layers:
        return mask
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height, width, 4)
    uv = mesh.uv_layers.active.data
    for polygon in mesh.polygons:
        u = sum(uv[i].uv[0] for i in polygon.loop_indices) / polygon.loop_total
        v = sum(uv[i].uv[1] for i in polygon.loop_indices) / polygon.loop_total
        texel = pixels[int((v % 1.0) * height) % height, int((u % 1.0) * width) % width, :3]
        mask[polygon.index] = texel.max() < 0.5 and texel.max() - texel.min() < 0.12
    neighbours: dict[int, list[int]] = {}
    by_edge: dict[tuple[int, int], list[int]] = {}
    for polygon in mesh.polygons:
        for key in polygon.edge_keys:
            by_edge.setdefault(key, []).append(polygon.index)
    for faces in by_edge.values():
        for a in faces:
            neighbours.setdefault(a, []).extend(f for f in faces if f != a)
    for _ in range(2):
        votes = np.array([np.mean(mask[neighbours[i]]) if neighbours.get(i) else float(mask[i])
                          for i in range(len(mask))])
        mask = np.where(votes > 0.5, True, np.where(votes < 0.5, False, mask))
    return mask


def cut_band(obj: bpy.types.Object, mask: np.ndarray) -> tuple[float, float] | None:
    """Turns the texture's ragged shorts into a clean band: the mesh is cut by the horizontal planes of the band's
    waist and hem (taken from the textured faces' heights, robustly), and every face between them becomes the
    shorts. Returns (hem, waist) heights, or None without shorts. Only the hips and legs span those heights in the
    T-pose."""
    if mask.sum() < 20:
        return None
    mesh = obj.data
    centres = np.array([p.center for p in mesh.polygons])
    heights = centres[mask, 2]
    hem, waist = float(np.percentile(heights, 4)), float(np.percentile(heights, 97))
    bm = bmesh.new()
    bm.from_mesh(mesh)
    for z in (hem, waist):
        geom = [*bm.verts, *bm.edges, *bm.faces]
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(0.0, 0.0, z), plane_no=(0.0, 0.0, 1.0))
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return hem, waist


def band_faces(obj: bpy.types.Object, band: tuple[float, float] | None) -> np.ndarray:
    mesh = obj.data
    if band is None:
        return np.zeros(len(mesh.polygons), dtype=bool)
    centres = np.array([p.center for p in mesh.polygons])
    return (centres[:, 2] > band[0]) & (centres[:, 2] < band[1])


def flat_material(name: str, srgb: list[float]) -> bpy.types.Material:
    colour = (*(srgb_to_linear(c) for c in srgb), 1.0)
    material = bpy.data.materials.new(name)
    tree = material.node_tree
    if tree is None:
        material.use_nodes = True
        tree = material.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = colour
    bsdf.inputs["Roughness"].default_value = 1.0
    material.diffuse_color = colour
    return material


def flatten_materials(objects: list[bpy.types.Object], plan: dict) -> dict:
    """Step 7 (before decimation, while the faces are dense): the skin and shorts materials replace the textured
    one; returns the shorts faces per mesh."""
    masks = {}
    bands = {}
    for obj in objects:
        bands[obj.name] = cut_band(obj, shorts_faces(obj))
        masks[obj.name] = band_faces(obj, bands[obj.name])
    skin, shorts = flat_material("Skin", plan["skin"]), flat_material("Shorts", plan["shorts"])
    for obj in objects:
        mesh = obj.data
        mesh.materials.clear()
        mesh.materials.append(skin)
        mask = masks[obj.name]
        if mask.any():
            mesh.materials.append(shorts)
        indices = mask.astype(np.int32)
        mesh.polygons.foreach_set("material_index", indices)
        for attribute in list(mesh.color_attributes):
            mesh.color_attributes.remove(attribute)
        mesh.update()
    for material in list(bpy.data.materials):
        if material not in (skin, shorts):
            bpy.data.materials.remove(material)
    for image in list(bpy.data.images):
        bpy.data.images.remove(image)
    return {name: {"faces": int(mask.sum()), "band": None if bands[name] is None else [round(z, 4) for z in bands[name]]}
            for name, mask in masks.items()}


def probe_rig(probe: dict[str, str]) -> dict[str, int]:
    """Step 9: turns each probe bone 30 degrees and counts the vertices that move more than 1 mm."""
    armature, meshes = armature_and_meshes()
    depsgraph = bpy.context.evaluated_depsgraph_get()

    def evaluated() -> np.ndarray:
        depsgraph.update()
        out = []
        for obj in meshes:
            mesh = obj.evaluated_get(depsgraph).to_mesh()
            out.append(positions(mesh))
            obj.evaluated_get(depsgraph).to_mesh_clear()
        return np.vstack(out)

    rest = evaluated()
    moved = {}
    for label, name in probe.items():
        bone = armature.pose.bones.get(name)
        if bone is None:
            moved[label] = -1
            continue
        bone.rotation_mode = "XYZ"
        bone.rotation_euler = (math.radians(30), 0.0, math.radians(20))
        moved[label] = int((np.linalg.norm(evaluated() - rest, axis=1) > 0.001).sum())
        bone.rotation_euler = (0.0, 0.0, 0.0)
    return moved


def main() -> None:
    plan = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    info: dict = {"preset": plan["preset"], "source": plan["source"]}
    import_gltf(plan["source"])
    info["dropped"], eyes = drop_objects(plan["drop_objects"])
    armature, meshes = armature_and_meshes()
    info["meshes"] = [o.name for o in meshes]
    info["triangles_source"] = triangles(meshes)
    info["open_edge_vertices"] = {o.name: int(boundary_vertices(o.data).sum()) for o in meshes}
    eyes_after = [head_transform(plan, armature, e) for e in eyes]
    for obj in meshes:
        clear_custom_normals(obj)
        mesh = obj.data
        co = reshape(plan, armature, obj, positions(mesh))
        edges = edges_of(mesh)
        head_w = weight_matrix(obj, [plan["head_bone"]])[:, 0]
        co, info["blank_face"] = blank_face(co, edges, eyes_after, head_w, plan["head_scale"])
        co, info["nose"] = longer_nose(co, head_w, eyes_after, plan["nose_length"], plan["head_scale"])
        soft = weight_matrix(obj, plan["soften_bones"]).sum(axis=1)
        soft[boundary_vertices(mesh)] = 0.0
        co = smooth(co, edges, np.clip(soft, 0.0, 1.0), plan["soften_iterations"], taubin=True)
        slit = info["blank_face"]["mouth"]
        info["blank_face"]["dent"] = None if slit is None else mouth_dent(co, head_w, slit, plan["head_scale"])
        set_positions(mesh, co)
    every = np.vstack([positions(o.data) for o in meshes])
    low, high = float(every[:, 2].min()), float(every[:, 2].max())
    factor = plan["height"] / (high - low)
    for obj in meshes:
        set_positions(obj.data, positions(obj.data) * factor)
    scale_bones(armature, factor, plan["head_bone"], plan["head_scale"])
    info["scale"] = round(factor, 5)
    # Every height and point in info.json is in the final, scaled figure's metres.
    face, nose = info["blank_face"], info["nose"]
    face["mouth"] = None if face["mouth"] is None else [round(float(v) * factor, 4) for v in face["mouth"]]
    face["dent"] = None if face.get("dent") is None else round(face["dent"] * factor, 4)
    nose["tip"] = None if nose["tip"] is None else [round(float(v) * factor, 4) for v in nose["tip"]]
    info["eye_height"] = round(float(np.mean([e[2] for e in eyes_after])) * factor, 4) if eyes_after else None
    info["shorts_faces_source"] = flatten_materials(meshes, plan)
    info["kept_border_vertices"] = {o.name: mark_material_borders(o) for o in meshes}
    info["decimate_ratio"] = round(decimate(meshes, armature, plan["target_triangles"]), 5)
    info["kept_border_vertices_after"] = {}
    for obj in meshes:
        group = obj.vertex_groups[KEEP_GROUP]
        info["kept_border_vertices_after"][obj.name] = sum(
            1 for v in obj.data.vertices for g in v.groups if g.group == group.index and g.weight > 0.5)
        obj.vertex_groups.remove(group)
    info["weights_cleaned"] = {o.name: clean_weights(o) for o in meshes}
    out = Path(plan["out_glb"])
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(out), export_format="GLB", export_yup=True, export_skins=True,
                              export_animations=False, export_apply=False)
    # Re-import what was written, so the numbers and the probe describe the file, not the scene.
    import_gltf(str(out))
    armature, meshes = armature_and_meshes()
    every = np.vstack([positions(o.data) for o in meshes])
    info.update({
        "glb": out.as_posix(),
        "triangles": triangles(meshes),
        "vertices": sum(len(o.data.vertices) for o in meshes),
        "height": round(float(every[:, 2].max() - every[:, 2].min()), 4),
        "lowest": round(float(every[:, 2].min()), 4),
        "bones": sorted(b.name for b in armature.data.bones),
        "materials": sorted({m.name for o in meshes for m in o.data.materials if m}),
        "images": len([i for i in bpy.data.images if i.size[0] > 0]),
        "probe": probe_rig(plan["probe_bones"]),
    })
    Path(plan["info"]).write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(f"STYLIZED {json.dumps({k: info[k] for k in ('preset', 'triangles', 'height')})}")


main()
