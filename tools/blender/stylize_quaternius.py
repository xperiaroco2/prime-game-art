"""Restyles the CC0 Quaternius base body into our base body (art #14), keeping its 65-bone rig, weights and five-finger
chains: an egg head with a blank face and a long cone nose, a soft trunk, lanky limbs, one palette material, about
6,000 triangles.

Run through the runner (`tools/run.py stylize-quaternius`), which writes the plan, renames the bones afterwards and
renders the gates; or directly:
    blender -b --factory-startup --python-exit-code 1 --python tools/blender/stylize_quaternius.py -- PLAN.json

The plan (tools/runner/commands/_stylize.py) names the bones in the rig's own names. Steps, in order:
 1. import the glTF (vertices merged at UV seams, no bone display shape); delete the eyes, the eyebrows and any mesh
    not skinned to the armature, remembering where the eyes were; the body mesh becomes "Body";
 2. a soft body: the trunk and each limb bone and the neck get a smooth surface around their axis (the pecs, abs,
    shoulder blades, biceps and calves go; vertices only move towards or away from the axis and the blend fades out
    at the joints), then normal-only Taubin smoothing on the trunk (no edge loop slides) and the groin's bulge
    flattened;
 3. the head: everything above a cut from the chin to the skull's base moves onto an egg (radial projection), which
    flattens the lips, the mouth, the nasolabial folds, the brow ridge and the cheek planes; the egg's surface is
    relaxed and the mouth laid flat (no folds); the ears ride along, are smoothed and pulled in; a membrane replaces
    the jaw line down to the neck; a cone nose is pulled out of the face; the head is weighted to the head bone alone,
    the membrane blended down to the neck;
 4. the proportions in pose mode: every trunk and limb bone is scaled across (slimmer) and the upper arms, forearms,
    thighs, shins and neck along their length (longer), the head uniformly, the neck turned upright; no bone inherits
    its parent's scale, so the hands and feet move but are never stretched. The head's scale is solved so the finished
    figure's head is the preset's size against the source's at the same height. The posed skin is applied and the
    pose becomes the rest;
 5. normalized: 1.75 m tall, the soles at z = 0, the feet centred on the origin; the skin saved for comparing a
    preset with base vertex by vertex;
 6. the face bones the rig lacks (Jaw, LeftEye, RightEye) are added under the head bone, unweighted;
 7. one palette material: the briefs are cut along two planes (waist and leg openings) and every face gets UVs in its
    colour's cell of a small palette image;
 8. decimated (collapse, symmetric in X) to the target, with the finger roots, the shoulder, elbow, hip and knee loops
    and the briefs' border protected; the weights cleaned (at most 4 per vertex, none under 0.01, normalized);
 9. saved as a .blend with the rig's own names (the runner renames the bones and exports the GLB).
Writes the plan's build.json.
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
KEEP_GROUP = "decimate_keep"


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def base_name(obj: bpy.types.Object) -> str:
    return obj.name.split(".")[0]


def import_gltf(path: str) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path, merge_vertices=True, disable_bone_shape=True)


def the_armature() -> bpy.types.Object:
    armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    if len(armatures) != 1:
        raise RuntimeError(f"expected one armature, found {len(armatures)}")
    return armatures[0]


def skinned(obj: bpy.types.Object, armature: bpy.types.Object) -> bool:
    return obj.type == "MESH" and any(m.type == "ARMATURE" and m.object == armature for m in obj.modifiers)


def drop_objects(names: list[str], armature: bpy.types.Object) -> tuple[list[str], list[list[float]]]:
    """Deletes the named meshes, the importer's helpers and every mesh not skinned to the armature; returns what went
    and the eye centres (left, right)."""
    dropped, eyes = [], []
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH":
            continue
        helper = any(c.name == HELPER_COLLECTION for c in obj.users_collection)
        if base_name(obj) in names or helper or not skinned(obj, armature):
            if base_name(obj) == "Eyes":
                points = np.array([obj.matrix_world @ v.co for v in obj.data.vertices])
                for side in (points[:, 0] > 0, points[:, 0] < 0):
                    if side.any():
                        eyes.append(points[side].mean(axis=0).tolist())
            dropped.append(obj.name)
            bpy.data.objects.remove(obj)
    return dropped, eyes


def the_body(armature: bpy.types.Object, name: str) -> bpy.types.Object:
    meshes = [o for o in bpy.context.scene.objects if skinned(o, armature)]
    if len(meshes) != 1:
        raise RuntimeError(f"expected one skinned body mesh, found {[o.name for o in meshes]}")
    body = meshes[0]
    for obj in (armature, body):
        if not np.allclose(np.array(obj.matrix_world), np.eye(4), atol=1e-5):
            raise RuntimeError(f"{obj.name} has a transform; this script expects applied transforms")
    body.name = body.data.name = name
    return body


def clear_custom_normals(obj: bpy.types.Object) -> None:
    """The imported normals no longer fit once vertices move: shade smooth from the geometry instead."""
    mesh = obj.data
    if mesh.has_custom_normals:
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for polygon in mesh.polygons:
        polygon.use_smooth = True


# --- mesh arrays ---------------------------------------------------------------------------------------------------


def positions(mesh: bpy.types.Mesh) -> np.ndarray:
    co = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
    mesh.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def set_positions(mesh: bpy.types.Mesh, co: np.ndarray) -> None:
    mesh.vertices.foreach_set("co", co.astype(np.float32).ravel())
    mesh.update()


def edges_of(mesh: bpy.types.Mesh) -> np.ndarray:
    edges = np.empty(len(mesh.edges) * 2, dtype=np.int64)
    mesh.edges.foreach_get("vertices", edges)
    return edges.reshape(-1, 2)


def triangles_of(mesh: bpy.types.Mesh) -> np.ndarray:
    mesh.calc_loop_triangles()
    tris = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("vertices", tris)
    return tris.reshape(-1, 3)


def triangle_count(objects: list[bpy.types.Object]) -> int:
    return sum(len(p.vertices) - 2 for o in objects for p in o.data.polygons)


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


def vertex_normals(co: np.ndarray, tris: np.ndarray) -> np.ndarray:
    face = np.cross(co[tris[:, 1]] - co[tris[:, 0]], co[tris[:, 2]] - co[tris[:, 0]])
    normals = np.zeros_like(co)
    for k in range(3):
        np.add.at(normals, tris[:, k], face)
    length = np.linalg.norm(normals, axis=1)
    return normals / np.where(length > 0, length, 1.0)[:, None]


def laplacian(co: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """The umbrella operator: the mean of each vertex's neighbours minus the vertex."""
    total = np.zeros_like(co)
    degree = np.zeros(len(co))
    np.add.at(total, edges[:, 0], co[edges[:, 1]])
    np.add.at(total, edges[:, 1], co[edges[:, 0]])
    np.add.at(degree, edges[:, 0], 1)
    np.add.at(degree, edges[:, 1], 1)
    return total / np.where(degree > 0, degree, 1)[:, None] - co


def smooth(co: np.ndarray, edges: np.ndarray, mask: np.ndarray, iterations: int, taubin: bool,
           tris: np.ndarray | None = None) -> np.ndarray:
    """Masked smoothing. Taubin's lambda/mu pair keeps the volume, plain Laplacian flattens dents and shrinks; with
    tris, only the Laplacian's component along the vertex normal is used, so vertices never slide along the surface
    and edge loops keep their spacing."""
    co = co.copy()
    m = mask[:, None]

    def step(points: np.ndarray, factor: float) -> np.ndarray:
        lap = laplacian(points, edges)
        if tris is not None:
            n = vertex_normals(points, tris)
            lap = (lap * n).sum(axis=1)[:, None] * n
        return points + factor * m * lap

    for _ in range(iterations):
        co = step(co, 0.5)
        if taubin:
            co = step(co, -0.53)
    return co


def diffuse(values: np.ndarray, edges: np.ndarray, free: np.ndarray, iterations: int = 200) -> np.ndarray:
    """Harmonic fill: the rows where free is true become the mean of their neighbours (repeatedly), the others stay;
    so a displacement field set on the surrounding skin carries a masked part (the nose, the ears) along smoothly."""
    values = values.copy()
    for _ in range(iterations):
        values[free] += laplacian(values, edges)[free]
    return values


def falloff(co: np.ndarray, centre: np.ndarray, radius: float) -> np.ndarray:
    d = np.linalg.norm(co - centre, axis=1) / radius
    return np.where(d < 1.0, (1.0 - d**2) ** 2, 0.0)


def smoothstep(value: np.ndarray, low: float, high: float) -> np.ndarray:
    t = np.clip((value - low) / (high - low), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def dilate(mask: np.ndarray, edges: np.ndarray, rings: int) -> np.ndarray:
    mask = mask.copy()
    for _ in range(rings):
        grown = mask.copy()
        grown[edges[mask[edges[:, 0]], 1]] = True
        grown[edges[mask[edges[:, 1]], 0]] = True
        mask = grown
    return mask


# --- step 2: a soft body -------------------------------------------------------------------------------------------


def tube(co: np.ndarray, weights: np.ndarray, head: np.ndarray, end: np.ndarray, strength: float,
         fit_range: tuple[float, float], fade: tuple[float, float, float, float], degree: int = 2) -> np.ndarray:
    """A smooth body part around the axis from head to end: every vertex's distance from the axis is blended towards
    a smooth surface fitted (weighted least squares) to the part's own vertices: around the axis the harmonics up to
    the second (ellipse-like sections that may sit off the axis), each harmonic's amount a polynomial of the given
    degree in the position t along the axis (0 at head, 1 at end); 1 gives a limb a straight taper. Muscle bulges
    (pecs, abs, shoulder blades, biceps, calves) go; the taper and the section stay. Vertices only move away from or
    towards the axis, so edge loops keep their places along it. The blend follows the weights and fades in and out
    along t (fade: zero below fade[0], full from fade[1] to fade[2], zero above fade[3])."""
    vector = end - head
    length = float(np.linalg.norm(vector))
    axis = vector / length
    e1 = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 0.0, 1.0])
    e1 -= axis * np.dot(e1, axis)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    rel = co - head
    t = rel @ axis / length
    radial = rel - np.outer(t * length, axis)
    rho = np.linalg.norm(radial, axis=1)
    angle = np.arctan2(radial @ e2, radial @ e1)
    fit = (weights > 0.5) & (t > fit_range[0]) & (t < fit_range[1]) & (rho > 1e-4)
    if fit.sum() < 40:
        return co
    around = [np.ones_like(angle), np.cos(angle), np.sin(angle), np.cos(2 * angle), np.sin(2 * angle)]
    basis = np.stack([h * t**k for h in around for k in range(degree + 1)], axis=1)
    coef, *_ = np.linalg.lstsq(basis[fit] * weights[fit, None], rho[fit] * weights[fit], rcond=None)
    target = basis @ coef
    blend = strength * weights * smoothstep(t, fade[0], fade[1]) * (1.0 - smoothstep(t, fade[2], fade[3]))
    blend[(rho < 1e-4) | (target <= 0)] = 0.0
    scale = 1.0 + blend * (target / np.where(rho > 1e-4, rho, 1.0) - 1.0)
    return head + np.outer(t * length, axis) + radial * scale[:, None]


def tubes(co: np.ndarray, body: bpy.types.Object, armature: bpy.types.Object, plan: dict) -> np.ndarray:
    """Step 2 for the trunk and each limb bone, in the plan's order."""
    bones = armature.data.bones
    for part in plan["tubes"]:
        weights = np.clip(weight_matrix(body, part["weights"]).sum(axis=1), 0.0, 1.0)
        co = tube(co, weights, np.array(bones[part["start"]].head_local), np.array(bones[part["end"]].head_local),
                  part["strength"], tuple(part["fit"]), tuple(part["fade"]), part["degree"])
    return co


def flatten_groin(co: np.ndarray, edges: np.ndarray, armature: bpy.types.Object, plan: dict) -> tuple[np.ndarray, dict]:
    """The source's bulge at the front of the groin, flattened by plain Laplacian smoothing (which shrinks a bump
    towards the surface around it) within a falloff around its most forward point, between the hips' joints."""
    legs = [np.array(armature.data.bones[b].head_local) for b in plan["legs"]]
    hip_z = float(np.mean([leg[2] for leg in legs]))
    front = (np.abs(co[:, 0]) < 0.02) & (co[:, 2] < hip_z) & (co[:, 2] > hip_z - 0.15) & (co[:, 1] < 0.0)
    if not front.any():
        return co, {"moved": 0}
    index = np.nonzero(front)[0]
    tip = co[index[np.argmin(co[index, 1])]]
    mask = falloff(co, tip, plan["groin_radius"])
    out = smooth(co, edges, mask, plan["groin_smooth"], taubin=False)
    return out, {"bulge": [round(float(v), 4) for v in tip], "moved": int((mask > 0.01).sum())}


# --- step 3: the head ----------------------------------------------------------------------------------------------


class Egg:
    """The look target's egg (the mannequin's head profile): at height fraction t (0 chin, 1 crown) the section is an
    ellipse of half width W r(t) (0.8 + 0.26 t) and half depth D r(t) (0.92 + 0.1 t), with r(t) = sqrt(1 - (2 s - 1)^2),
    s = t^1.2: a round crown, the widest part a little above the middle, narrower at the jaw. Its centre line leans
    forward towards the chin by jaw D (1 - t)^2, so the jaw stays over the throat instead of folding back into the
    neck."""

    def __init__(self, chin: float, crown: float, centre_y: float, jaw: float) -> None:
        self.chin, self.height = chin, crown - chin
        self.centre_y, self.jaw = centre_y, jaw
        self.width = self.depth = 1.0

    @staticmethod
    def shape(t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        t = np.clip(t, 0.0, 1.0)
        s = t**1.2
        r = np.sqrt(np.maximum(0.0, 1.0 - (2.0 * s - 1.0) ** 2))
        return r * (0.8 + 0.26 * t), r * (0.92 + 0.1 * t)

    def fit(self, t: float, half_width: float, half_depth: float) -> None:
        """Sets W and D so the egg's section at t has these half extents."""
        w, d = self.shape(np.array([t]))
        self.width, self.depth = half_width / float(w[0]), half_depth / float(d[0])

    def axis_y(self, t: np.ndarray) -> np.ndarray:
        return self.centre_y - self.jaw * self.depth * (1.0 - np.clip(t, 0.0, 1.0)) ** 2

    def level(self, points: np.ndarray) -> np.ndarray:
        """(x / w)^2 + ((y - c) / d)^2 at each point's own height: below 1 inside, 1 on the surface."""
        t = (points[:, 2] - self.chin) / self.height
        w, d = self.shape(t)
        w, d = w * self.width, d * self.depth
        inside = (t > 0) & (t < 1) & (w > 1e-6) & (d > 1e-6)
        out = np.full(len(points), np.inf)
        out[inside] = ((points[inside, 0] / w[inside]) ** 2
                       + ((points[inside, 1] - self.axis_y(t[inside])) / d[inside]) ** 2)
        return out

    def centre(self) -> np.ndarray:
        return np.array([0.0, float(self.axis_y(np.array([0.5]))[0]), self.chin + 0.5 * self.height])

    def project(self, points: np.ndarray) -> np.ndarray:
        """Each point moved along the ray from the egg's centre onto the egg's surface (bisection)."""
        c = self.centre()
        rays = points - c
        length = np.linalg.norm(rays, axis=1)
        unit = rays / np.where(length > 1e-9, length, 1.0)[:, None]
        low, high = np.zeros(len(points)), np.full(len(points), 2.0 * self.height)
        for _ in range(48):
            mid = (low + high) / 2
            inside = self.level(c + unit * mid[:, None]) < 1.0
            low = np.where(inside, mid, low)
            high = np.where(inside, high, mid)
        return c + unit * ((low + high) / 2)[:, None]

    def front_y(self, x: np.ndarray, z: np.ndarray) -> np.ndarray:
        """The egg's front surface's depth (y) at each (x, z); the section's edge where |x| is beyond it."""
        t = (z - self.chin) / self.height
        w, d = self.shape(t)
        w, d = np.maximum(w * self.width, 1e-6), d * self.depth
        return self.axis_y(t) - d * np.sqrt(np.clip(1.0 - (x / w) ** 2, 0.0, 1.0))

    def front(self, z: float) -> np.ndarray:
        """The egg's front-most point (x = 0) at height z."""
        return self.project(np.array([[0.0, self.centre_y - 2.0 * self.height, z]]))[0]


def head_landmarks(co: np.ndarray, head_w: np.ndarray, eyes: list[np.ndarray]) -> dict:
    """The source head's chin, crown, eye level and cranium extents (the ears and nose left out)."""
    eye = np.mean(eyes, axis=0)
    head = head_w > 0.8
    crown = float(co[head, 2].max())
    # The chin: the lowest point of the face's front (the throat below it lies further back; its skin's head weight
    # is about 0.7, so a looser threshold than the cranium's).
    face = (head_w > 0.5) & (np.abs(co[:, 0]) < 0.03) & (co[:, 1] < eye[1] + 0.02)
    chin = float(co[face, 2].min())
    span = crown - chin
    k = span / 0.2  # the source head is about 0.2 m from chin to crown
    temple = head & (co[:, 2] > eye[2] + 0.03 * k) & (co[:, 2] < eye[2] + 0.08 * k)
    half_width = float(np.abs(co[temple, 0]).max())
    brow = head & (np.abs(co[:, 2] - (eye[2] + 0.035 * k)) < 0.01)
    front, back = float(co[brow, 1].min()), float(co[brow, 1].max())
    return {"eye": eye, "crown": crown, "chin": chin, "span": span, "half_width": half_width,
            "front": front, "back": back, "t_temple": (eye[2] + 0.055 * k - chin) / span,
            "t_brow": (eye[2] + 0.035 * k - chin) / span}


def restyle_head(co: np.ndarray, edges: np.ndarray, head_w: np.ndarray, eyes: list[np.ndarray],
                 params: dict) -> tuple[np.ndarray, dict]:
    """Step 3: the whole cranium and face (nose, lips, chin and brow included) move onto the egg, which leaves a
    truly blank face; the ears ride along on the egg's surface, are rounded off and pulled in; the seam between the
    jaw and the neck is relaxed; then a cone nose is pulled out of the face. Returns the new positions and what it
    found (in the source's metres)."""
    if not eyes:
        none = np.zeros(len(co), dtype=bool)
        return co, {"note": "no eye mesh: the head is left as it is"}, none, none
    marks = head_landmarks(co, head_w, eyes)
    span = marks["span"]
    egg = Egg(marks["chin"], marks["crown"], (marks["front"] + marks["back"]) / 2, params["egg_jaw"])
    # The temples give the width and the brow the depth (the nose and ears stand outside the egg).
    egg.fit(marks["t_temple"], marks["half_width"] * params["egg_width"],
            (marks["back"] - marks["front"]) / 2 * params["egg_depth"])
    target = egg.project(co)
    out = (np.linalg.norm(co - egg.centre(), axis=1) - np.linalg.norm(target - egg.centre(), axis=1)) / span
    eye_t = (marks["eye"][2] - marks["chin"]) / span
    t = (co[:, 2] - marks["chin"]) / span
    head = head_w > 0.5
    ears = head & (np.abs(co[:, 0]) > 0.5 * egg.width) & (t > eye_t - 0.3) & (t < eye_t + 0.15) & (out > 0.015)
    ears = dilate(ears, edges, 2) & head & (np.abs(co[:, 0]) > 0.35 * egg.width)
    # The egg holds on the head above a cut that rises from the chin at the front to the skull's base at the back
    # (a plane, so the egg's lower edge is a clean line); the ears ride on it (their displacement filled in
    # harmonically from the skin around them).
    rise = np.clip((co[:, 1] - (egg.centre_y - egg.depth)) / (2 * egg.depth), 0.0, 1.0)
    cut = egg.chin + span * (params["cut_front"] + (params["cut_back"] - params["cut_front"]) * rise)
    # Everything above the cut is the head, whatever its weights (the mouth's inside is barely weighted to the head
    # bone, and left where it was it would poke through the egg as a small mouth).
    inner = (co[:, 2] >= cut) & ~ears
    outer = (head_w <= 0.15) & ~inner
    displacement = np.where(inner[:, None], target - co, 0.0)
    displacement = diffuse(displacement, edges, ears, 400)
    moved = co + params["egg_strength"] * displacement
    # The egg's surface relaxed: smoothing spreads the vertices evenly (the eyelids' and lips' dense rings fold up
    # when projected) and each pass puts them back on the egg.
    # The nose's root zone relaxes on its own, inside its own fixed rim, so it keeps the face's dense vertices
    # around the old nose for the cone (relaxing never moves vertices across a fixed rim).
    zone = inner & (nose_distance(moved, egg, params) < 1.4)
    # The mouth (the lips and the pocket of skin inside them) folds up on the egg: it is laid flat inside its own
    # fixed rim afterwards (flat_disc).
    k = span / 0.2
    mouth = inner & ~zone & (np.abs(co[:, 0]) < 0.035 * k) & (t > 0.0) & (t < eye_t - 0.2) & (
        co[:, 1] < marks["eye"][1] + 0.045 * k)
    for _ in range(params["egg_relax"]):
        for part in (zone, mouth, inner & ~zone & ~mouth):
            moved = smooth(moved, edges, part.astype(float), 1, taubin=False)
            moved[part] = egg.project(moved[part])
    moved = flat_disc(moved, edges, mouth, egg)
    # The ears: rounded off (plain Laplacian smoothing fills their folds) and pulled in towards the egg.
    moved = smooth(moved, edges, ears.astype(float), params["ear_smooth"], taubin=False)
    surface = egg.project(moved)
    moved[ears] = surface[ears] + params["ear_keep"] * (moved[ears] - surface[ears])
    # Between the egg and the neck (the jaw's underside, the throat) a membrane: the positions themselves are filled
    # in harmonically, so nothing of the chin or the jaw line stays.
    seam = ~inner & ~outer & ~ears
    moved = smooth(moved, edges, seam.astype(float), params["seam_smooth"], taubin=False)
    # A light pass over the egg's lower edge and the ears' rims softens the creases where they meet.
    rims = (dilate(seam, edges, 3) & dilate(inner | outer, edges, 3)) | (dilate(ears, edges, 2) & ~ears)
    moved = smooth(moved, edges, rims.astype(float), 12, taubin=True)
    moved, nose = cone_nose(moved, egg, params)
    info = {"egg": {"chin": round(egg.chin, 4), "height": round(egg.height, 4), "centre_y": round(egg.centre_y, 4),
                    "width": round(egg.width, 4), "depth": round(egg.depth, 4), "jaw": params["egg_jaw"]},
            "ear_vertices": int(ears.sum()), "seam_vertices": int(seam.sum()), "mouth_vertices": int(mouth.sum()),
            "nose": nose,
            "moved": int((np.linalg.norm(moved - co, axis=1) > 1e-4).sum())}
    return moved, info, inner | ears, seam


def head_only(obj: bpy.types.Object, rigid: np.ndarray, seam: np.ndarray, edges: np.ndarray, head_bone: str) -> dict:
    """The egg, the ears and the nose become one rigid shape weighted to the head bone alone (with the source's mixed
    face weights, the mouth's inside leans on the neck, the bones' new proportions would pull the face out of the egg
    again as small dents), and across the membrane down to the neck the weights are filled in harmonically from
    there to the neck's own, so the head's scale hands over smoothly. Returns how many vertices changed."""
    seam_index = np.nonzero(seam)[0]
    names = sorted({obj.vertex_groups[g.group].name for v in seam_index for g in obj.data.vertices[int(v)].groups}
                   | {head_bone})
    weights = weight_matrix(obj, names)
    head = names.index(head_bone)
    weights[rigid] = 0.0
    weights[rigid, head] = 1.0
    weights = diffuse(weights, edges, seam, 600)
    groups = obj.vertex_groups
    rigid_index = [int(v) for v in np.nonzero(rigid)[0]]
    for group in groups:
        if group.name != head_bone:
            group.remove(rigid_index)
    groups[head_bone].add(rigid_index, 1.0, "REPLACE")
    for v in seam_index:
        row = np.where(weights[v] >= 0.01, weights[v], 0.0)
        row /= row.sum() or 1.0
        for i, name in enumerate(names):
            if row[i] > 0:
                groups[name].add([int(v)], float(row[i]), "REPLACE")
            elif name in groups:
                groups[name].remove([int(v)])
    return {"rigid": len(rigid_index), "blended": len(seam_index)}


def flat_disc(co: np.ndarray, edges: np.ndarray, part: np.ndarray, egg: Egg) -> np.ndarray:
    """Lays a part of the face flat on the egg's front without folds: its vertices' (x, z) solve the graph Laplace
    equation with the part's rim held (Tutte's embedding: inside a convex rim no triangle can fold over), then each
    takes the egg's depth there."""
    index = np.nonzero(part)[0]
    if len(index) < 3:
        return co
    local = {v: i for i, v in enumerate(index)}
    matrix = np.zeros((len(index), len(index)))
    rhs = np.zeros((len(index), 2))
    for a, b in edges:
        for u, v in ((a, b), (b, a)):
            if u in local:
                i = local[u]
                matrix[i, i] += 1.0
                if v in local:
                    matrix[i, local[v]] -= 1.0
                else:
                    rhs[i] += co[v, [0, 2]]
    solved = np.linalg.lstsq(matrix, rhs, rcond=None)[0]
    co = co.copy()
    co[index, 0], co[index, 2] = solved[:, 0], solved[:, 1]
    co[index, 1] = egg.front_y(co[index, 0], co[index, 2])
    return co


def nose_frame(egg: Egg, params: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The nose's root on the egg's front, its axis (forward and a little down) and two directions across it (e1
    along X, e2 up)."""
    root = egg.front(egg.chin + params["nose_root"] * egg.height)
    axis = np.array([0.0, -1.0, -params["nose_droop"]])
    axis /= np.linalg.norm(axis)
    e1 = np.array([1.0, 0.0, 0.0])
    e2 = np.cross(axis, e1)
    e2 *= np.sign(e2[2]) or 1.0
    return root, axis, e1, e2


def nose_distance(co: np.ndarray, egg: Egg, params: dict) -> np.ndarray:
    """Each point's elliptic distance from the nose's root across the face (1 on the root's rim); behind the face,
    infinity."""
    root, _, _, _ = nose_frame(egg, params)
    rel = co - root
    root_w, root_h = (r * egg.height for r in params["nose_root_radius"])
    d = np.sqrt((rel[:, 0] / root_w) ** 2 + (rel[:, 2] / root_h) ** 2)
    return np.where((co[:, 1] < egg.centre_y) & (np.abs(rel[:, 1]) < 0.5 * egg.height), d, np.inf)


def cone_nose(co: np.ndarray, egg: Egg, params: dict) -> tuple[np.ndarray, dict]:
    """Pulls a cone nose out of the blank face: the face's vertices inside an ellipse around the root (half width
    and half height from the plan) become the cone; the rim stays where it is and the centre becomes the tip. A
    vertex at elliptic distance d from the root keeps its angle around the axis and moves to t = 1 - d along the
    cone, at the cone's radius there; the last part is a half-sphere cap. The axis points forward and a little down."""
    span = egg.height
    root, axis, e1, e2 = nose_frame(egg, params)
    root_w, root_h = (r * span for r in params["nose_root_radius"])
    tip = params["nose_tip_radius"] * span
    length = params["nose_length"] * span
    rel = co - root
    u, v = rel[:, 0], rel[:, 2]
    d = nose_distance(co, egg, params)
    disc = d < 1.0
    if disc.sum() < 12:
        return co, {"note": "too few vertices around the nose root", "vertices": int(disc.sum())}
    t = np.clip(1.0 - d, 0.0, 1.0)
    angle = np.arctan2(v / root_h, u / root_w)
    cap_start = 1.0 - tip / max(length, 1e-6)  # the cap is a half sphere of the tip's radius
    along = np.minimum(t, cap_start)
    w = root_w + (tip - root_w) * (along / cap_start)
    h = root_h + (tip - root_h) * (along / cap_start)
    over = np.clip((t - cap_start) / max(1.0 - cap_start, 1e-6), 0.0, 1.0)
    cap = np.cos(over * np.pi / 2)
    position = length * along + tip * np.sin(over * np.pi / 2)
    cone = (root + np.outer(position, axis) + np.outer(w * cap * np.cos(angle), e1)
            + np.outer(h * cap * np.sin(angle), e2))
    moved = co.copy()
    moved[disc] = cone[disc]
    tip_point = root + axis * (length * cap_start + tip)
    return moved, {"root": [round(float(x), 4) for x in root], "tip": [round(float(x), 4) for x in tip_point],
                   "length": round(length, 4), "vertices": int(disc.sum())}


# --- step 4: proportions in pose mode -----------------------------------------------------------------------------


def evaluated_positions(obj: bpy.types.Object) -> np.ndarray:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    co = positions(mesh)
    evaluated.to_mesh_clear()
    return co


def head_height(co: np.ndarray, head_w: np.ndarray) -> float:
    """The head's size as a fraction of the figure's height: the vertical extent of the head-weighted skin."""
    head = co[head_w >= 0.5, 2]
    return float(head.max() - head.min()) / float(co[:, 2].max() - co[:, 2].min())


def rotate_pose_bone(pb: bpy.types.PoseBone, axis: Vector, angle: float) -> None:
    """Turns a pose bone (and so its children) by angle (radians) about a world axis through its head."""
    matrix = pb.matrix.copy()
    head = matrix.translation.copy()
    pb.matrix = Matrix.Translation(head) @ Matrix.Rotation(angle, 4, axis) @ Matrix.Translation(-head) @ matrix
    bpy.context.view_layer.update()


def straighten_neck(armature: bpy.types.Object, neck: str, head: str, amount: float) -> float:
    """Turns the neck towards upright by amount (1: fully) and the head back by as much, so the head sits over the
    neck instead of in front of it and still looks straight ahead. Returns the angle in degrees."""
    pose = armature.pose.bones
    direction = (pose[neck].tail - pose[neck].head).normalized()
    up = Vector((0.0, 0.0, 1.0))
    axis = direction.cross(up)
    if axis.length < 1e-6 or amount <= 0:
        return 0.0
    angle = direction.angle(up) * amount
    rotate_pose_bone(pose[neck], axis.normalized(), angle)
    rotate_pose_bone(pose[head], axis.normalized(), -angle)
    return math.degrees(angle)


def pose_proportions(armature: bpy.types.Object, body: bpy.types.Object, plan: dict, head_w: np.ndarray,
                     source_ratio: float) -> dict:
    """Step 4: scales the bones in pose mode, solves the head's scale for the plan's head ratio, applies the posed
    skin and makes the pose the rest. Returns the scales used."""
    inherit = {b.name: b.inherit_scale for b in armature.data.bones}
    for bone in armature.data.bones:
        bone.inherit_scale = "NONE"
    pose = armature.pose.bones
    for name, (across, along) in plan["scale"].items():
        pose[name].scale = (across, along, across)
    bpy.context.view_layer.update()
    upright = straighten_neck(armature, plan["neck_bone"], plan["head_bone"], plan["neck_upright"])
    head = pose[plan["head_bone"]]
    wanted = source_ratio * plan["head_ratio"]
    scale, history = plan["head_ratio"], []
    for _ in range(8):
        head.scale = (scale, scale, scale)
        ratio = head_height(evaluated_positions(body), head_w)
        history.append([round(scale, 5), round(ratio / source_ratio, 5)])
        if abs(ratio - wanted) < 1e-4:
            break
        scale *= (wanted / ratio) ** 1.3
    co = evaluated_positions(body)
    set_positions(body.data, co)
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    for name, mode in inherit.items():
        armature.data.bones[name].inherit_scale = mode
    for bone in pose:
        bone.scale = (1.0, 1.0, 1.0)
        bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        bone.location = (0.0, 0.0, 0.0)
    return {"head_scale": round(scale, 5), "head_solve": history, "neck_upright_deg": round(upright, 2)}


# --- step 5: normalize ---------------------------------------------------------------------------------------------


def transform_rig(armature: bpy.types.Object, body: bpy.types.Object, factor: float, shift: np.ndarray) -> None:
    """Scales the mesh and every bone about the origin by factor, then moves them by shift."""
    set_positions(body.data, positions(body.data) * factor + shift)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    bones = armature.data.edit_bones
    new = {b.name: (b.head * factor + Vector(shift), b.tail * factor + Vector(shift), b.roll) for b in bones}
    for bone in bones:
        bone.head, bone.tail, bone.roll = new[bone.name]
    bpy.ops.object.mode_set(mode="OBJECT")


def normalize(armature: bpy.types.Object, body: bpy.types.Object, height: float) -> dict:
    co = positions(body.data)
    low, high = float(co[:, 2].min()), float(co[:, 2].max())
    factor = height / (high - low)
    soles = co[co[:, 2] < low + 0.03 * (high - low)]
    centre = (soles.min(axis=0) + soles.max(axis=0)) / 2
    shift = np.array([-centre[0], -centre[1], -low]) * factor
    transform_rig(armature, body, factor, shift)
    return {"factor": factor, "shift": shift}


def compare_with_base(co: np.ndarray, plan: dict) -> dict | None:
    """Saves the normalized skin (every preset has the source's topology until the briefs are cut) and, for a preset
    other than base, measures how far each vertex lies from the same vertex of base: the honest version of the batch
    2 review's nearest-vertex diff, which found the old presets 3.5 mm (median) from base."""
    np.save(plan["positions"], co.astype(np.float32))
    other = plan.get("base_positions")
    if not other or not Path(other).is_file():
        return None
    base = np.load(other)
    if base.shape != co.shape:
        return {"note": f"base has {len(base)} vertices, this preset {len(co)}"}
    distance = np.linalg.norm(co - base, axis=1)
    return {"median": round(float(np.median(distance)), 4), "p95": round(float(np.percentile(distance, 95)), 4),
            "max": round(float(distance.max()), 4)}


# --- step 6: face bones --------------------------------------------------------------------------------------------


def add_face_bones(armature: bpy.types.Object, head_bone: str, eyes: list[np.ndarray], names: list[str]) -> dict:
    """Jaw, LeftEye and RightEye under the head bone, unweighted, pointing forward (-Y, the model's front). The eyes
    sit at the source's eye centres (moved with the head); the jaw a little in front of and above the head joint."""
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    bones = armature.data.edit_bones
    head = bones[head_bone]
    size = (head.tail - head.head).length
    if not eyes:  # a source without an eye mesh: in front of the head joint, a little above it
        eyes = [np.array(head.head + Vector((side * 0.4 * size, -0.8 * size, 1.1 * size))) for side in (1, -1)]
    left = max(eyes, key=lambda e: e[0])
    right = min(eyes, key=lambda e: e[0])
    spots = {"Jaw": head.head + Vector((0.0, -0.45 * size, 0.45 * size)),
             "LeftEye": Vector(left), "RightEye": Vector(right)}
    made = {}
    for name in names:
        if name in bones:
            continue
        bone = bones.new(name)
        bone.head = spots[name]
        bone.tail = spots[name] + Vector((0.0, -0.35 * size, 0.0))
        bone.roll = 0.0
        bone.parent = head
        bone.use_deform = True
        made[name] = [round(v, 4) for v in spots[name]]
    bpy.ops.object.mode_set(mode="OBJECT")
    return made


# --- step 7: the palette -------------------------------------------------------------------------------------------


def crotch_height(co: np.ndarray, hips_w: np.ndarray) -> float:
    """The highest point of the gap between the legs: the lowest centre-line vertex of the hips."""
    centre = (np.abs(co[:, 0]) < 0.012) & (hips_w > 0.2)
    return float(co[centre, 2].min()) if centre.any() else float(co[hips_w > 0.2, 2].min())


def cut_briefs(obj: bpy.types.Object, crotch: float, leg_x: float) -> dict:
    """Cuts the briefs' outline into the mesh: a horizontal waist plane and, per leg, a leg opening plane that rises
    towards the outside of the hip (a brief's cut). Returns the planes."""
    waist = crotch + 0.125
    hem = crotch - 0.025
    tilt = math.radians(28)
    planes = [("waist", (0.0, 0.0, waist), (0.0, 0.0, 1.0), None)]
    for side in (1.0, -1.0):
        point = (side * leg_x, 0.0, hem)
        normal = (-side * math.sin(tilt), 0.0, math.cos(tilt))
        planes.append(("leg_left" if side > 0 else "leg_right", point, normal, side))
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    for _, point, normal, side in planes:
        if side is None:
            geom = [*bm.verts, *bm.edges, *bm.faces]
        else:
            faces = [f for f in bm.faces if side * f.calc_center_median().x > 0 and f.calc_center_median().z < waist]
            edges = {e for f in faces for e in f.edges}
            verts = {v for f in faces for v in f.verts}
            geom = [*verts, *edges, *faces]
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=point, plane_no=normal)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return {"waist": round(waist, 4), "hem": round(hem, 4), "tilt_deg": 28.0, "leg_x": round(leg_x, 4),
            "planes": planes}


def briefs_faces(obj: bpy.types.Object, cut: dict) -> np.ndarray:
    centres = np.array([p.center for p in obj.data.polygons])
    inside = centres[:, 2] < cut["waist"]
    for _, point, normal, side in cut["planes"][1:]:
        on_side = side * centres[:, 0] > 0
        above = (centres - np.array(point)) @ np.array(normal) > 0
        inside &= ~on_side | above
    # Only the hips' region: the hands hang far above the waist in the T-pose, nothing else lies below it but legs.
    return inside & (centres[:, 2] > cut["hem"] - 0.2)


def palette_material(plan: dict) -> tuple[bpy.types.Material, dict[str, tuple[float, float]]]:
    """One matte material reading its base colour from a small palette image (closest-pixel sampling); returns it and
    each colour's UV (its cell's centre)."""
    palette = plan["palette"]
    cells, px = palette["cells"], palette["cell_px"]
    size = cells * px
    pixels = np.ones((size, size, 4), dtype=np.float32)
    uvs = {}
    for name, entry in palette["colours"].items():
        row, col = divmod(entry["cell"], cells)
        colour = [srgb_to_linear(c) for c in entry["srgb"]]
        y0 = size - (row + 1) * px  # image rows start at the bottom; cell 0 is the top-left
        pixels[y0 : y0 + px, col * px : (col + 1) * px, :3] = colour
        uvs[name] = ((col + 0.5) / cells, 1.0 - (row + 0.5) / cells)
    image = bpy.data.images.new("Palette", size, size, alpha=False)
    image.colorspace_settings.name = "sRGB"
    srgb = pixels.copy()
    srgb[..., :3] = np.where(pixels[..., :3] <= 0.0031308, pixels[..., :3] * 12.92,
                             1.055 * np.power(pixels[..., :3], 1 / 2.4) - 0.055)
    image.pixels.foreach_set(srgb.ravel())
    image.pack()
    material = bpy.data.materials.new("Palette")
    tree = material.node_tree
    if tree is None:
        material.use_nodes = True
        tree = material.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.interpolation = "Closest"
    tree.links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 1.0
    bsdf.inputs["Metallic"].default_value = 0.0
    skin = palette["colours"]["skin"]["srgb"]
    material.diffuse_color = (*(srgb_to_linear(c) for c in skin), 1.0)
    material.roughness = 1.0
    material.metallic = 0.0
    return material, uvs


def apply_palette(obj: bpy.types.Object, material: bpy.types.Material, uvs: dict, briefs: np.ndarray) -> None:
    mesh = obj.data
    mesh.materials.clear()
    mesh.materials.append(material)
    mesh.polygons.foreach_set("material_index", np.zeros(len(mesh.polygons), dtype=np.int32))
    while mesh.uv_layers:
        mesh.uv_layers.remove(mesh.uv_layers[0])
    layer = mesh.uv_layers.new(name="UVMap")
    loops = np.zeros((len(mesh.loops), 2), dtype=np.float32)
    skin, brief = np.array(uvs["skin"]), np.array(uvs["briefs"])
    for polygon in mesh.polygons:
        loops[polygon.loop_start : polygon.loop_start + polygon.loop_total] = brief if briefs[polygon.index] else skin
    layer.data.foreach_set("uv", loops.ravel())
    for attribute in list(mesh.color_attributes):
        mesh.color_attributes.remove(attribute)
    for other in list(bpy.data.materials):
        if other != material:
            bpy.data.materials.remove(other)
    for image in list(bpy.data.images):
        if image.name != "Palette":
            bpy.data.images.remove(image)
    mesh.update()


# --- step 8: decimate ----------------------------------------------------------------------------------------------


def protect_group(obj: bpy.types.Object, armature: bpy.types.Object, plan: dict, briefs: np.ndarray) -> dict:
    """The vertex group decimation protects: the finger roots (around each finger's first joint, and the webs between
    them), the shoulder, elbow, hip and knee loops, and the briefs' border."""
    mesh = obj.data
    co = positions(mesh)
    keep = np.zeros(len(co))
    bones = armature.data.bones
    for side in plan["fingers"].values():
        for chain in side.values():
            root = np.array(bones[chain[0] if "thumb" not in chain[0] else chain[1]].head_local)
            keep = np.maximum(keep, falloff(co, root, 0.018))
    for names in plan["joints"].values():
        for name in names:
            keep = np.maximum(keep, 0.8 * falloff(co, np.array(bones[name].head_local), 0.06))
    border = set()
    by_edge: dict[tuple[int, int], set[bool]] = {}
    for polygon in mesh.polygons:
        for key in polygon.edge_keys:
            by_edge.setdefault(key, set()).add(bool(briefs[polygon.index]))
    for key, kinds in by_edge.items():
        if len(kinds) > 1:
            border.update(key)
    for v in border:
        keep[v] = 1.0
    group = obj.vertex_groups.new(name=KEEP_GROUP)
    for value in (1.0, 0.75, 0.5, 0.25):
        chosen = np.nonzero((keep >= value) & (keep < value + 0.25 + (value == 1.0)))[0]
        if len(chosen):
            group.add(chosen.tolist(), value, "REPLACE")
    return {"protected": int((keep > 0.1).sum()), "border": len(border)}


def decimate(obj: bpy.types.Object, armature: bpy.types.Object, target: int) -> float:
    """Collapse decimation, symmetric in X, protected by KEEP_GROUP (inverted: an edge between protected vertices
    costs more, so the collapse spends its triangles elsewhere first); the armature modifier is off meanwhile."""
    total = triangle_count([obj])
    if total <= target:
        return 1.0
    ratio = target / total
    for modifier in [m for m in obj.modifiers if m.type == "ARMATURE"]:
        obj.modifiers.remove(modifier)
    modifier = obj.modifiers.new("Decimate", "DECIMATE")
    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = ratio
    modifier.use_symmetry = True
    modifier.symmetry_axis = "X"
    modifier.use_collapse_triangulate = True
    modifier.vertex_group = KEEP_GROUP
    modifier.invert_vertex_group = True
    modifier.vertex_group_factor = 4.0
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


# --- main ----------------------------------------------------------------------------------------------------------


def main() -> None:
    plan = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    info: dict = {"preset": plan["preset"], "source": plan["source"]}
    import_gltf(plan["source"])
    armature = the_armature()
    info["dropped"], eyes = drop_objects(plan["drop_objects"], armature)
    body = the_body(armature, plan["body_name"])
    clear_custom_normals(body)
    mesh = body.data
    info["triangles_source"] = triangle_count([body])
    info["open_edge_vertices_source"] = int(boundary_vertices(mesh).sum())
    co = positions(mesh)
    edges, tris = edges_of(mesh), triangles_of(mesh)
    head_w = weight_matrix(body, [plan["head_bone"]])[:, 0]
    source_ratio = head_height(co, head_w)
    info["source_head_ratio"] = round(source_ratio, 5)
    info["source_height"] = round(float(co[:, 2].max() - co[:, 2].min()), 4)

    # 2. a soft body
    open_edges = boundary_vertices(mesh)
    trunk = np.clip(weight_matrix(body, plan["soften_bones"]).sum(axis=1), 0.0, 1.0)
    trunk[open_edges] = 0.0
    co = smooth(co, edges, trunk, plan["soften_iterations"], taubin=True, tris=tris)
    co = tubes(co, body, armature, plan)
    co, info["groin"] = flatten_groin(co, edges, armature, plan)
    # 3. the head
    eyes = [np.array(e) for e in eyes]
    co, info["head"], rigid, seam = restyle_head(co, edges, head_w, eyes, plan["head"])
    info["head"]["weights"] = head_only(body, rigid, seam, edges, plan["head_bone"])
    set_positions(mesh, co)
    # 4. proportions; the eyes ride on the head bone
    head_rest = armature.data.bones[plan["head_bone"]].matrix_local.copy()
    # The head's size is measured as the gates measure the file: on the skin the head bone now moves at least half.
    info["pose"] = pose_proportions(armature, body, plan, weight_matrix(body, [plan["head_bone"]])[:, 0], source_ratio)
    head_new = armature.data.bones[plan["head_bone"]].matrix_local
    s = info["pose"]["head_scale"]
    eyes = [np.array(head_new @ Matrix.Diagonal((s, s, s, 1.0)) @ head_rest.inverted() @ Vector(e)) for e in eyes]
    # 5. normalize
    norm = normalize(armature, body, plan["height"])
    eyes = [e * norm["factor"] + norm["shift"] for e in eyes]
    info["scale"] = round(norm["factor"], 5)
    info["shift_from_base"] = compare_with_base(positions(mesh), plan)
    # 6. face bones
    info["face_bones"] = add_face_bones(armature, plan["head_bone"], eyes, plan["face_bones"])
    info["eye_height"] = round(float(np.mean([e[2] for e in eyes])), 4) if eyes else None
    # 7. the palette and the briefs
    co = positions(mesh)
    hips = weight_matrix(body, [plan["hips_bone"]])[:, 0]
    crotch = crotch_height(co, hips)
    leg_x = float(np.mean([abs(armature.data.bones[b].head_local.x) for b in plan["legs"]]))
    cut = cut_briefs(body, crotch, leg_x)
    briefs = briefs_faces(body, cut)
    material, uvs = palette_material(plan)
    apply_palette(body, material, uvs, briefs)
    info["briefs"] = {k: v for k, v in cut.items() if k != "planes"} | {"crotch": round(crotch, 4),
                                                                       "faces": int(briefs.sum())}
    # 8. decimate
    info["protect"] = protect_group(body, armature, plan, briefs)
    info["triangles_before_decimate"] = triangle_count([body])
    info["decimate_ratio"] = round(decimate(body, armature, plan["target_triangles"]), 5)
    body.vertex_groups.remove(body.vertex_groups[KEEP_GROUP])
    info["weights_cleaned"] = clean_weights(body)
    info["triangles"] = triangle_count([body])
    # 9. save with the rig's own names; the runner renames and exports
    out = Path(plan["stage_blend"])
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), check_existing=False, compress=True)
    blend1 = out.with_suffix(".blend1")
    if blend1.exists():
        blend1.unlink()
    Path(plan["info"]).write_text(json.dumps(info, indent=2, default=lambda o: o.tolist() if hasattr(o, "tolist")
                                             else str(o)) + "\n", encoding="utf-8")
    print(f"RESTYLED {json.dumps({k: info[k] for k in ('preset', 'triangles', 'eye_height')})}")


main()
