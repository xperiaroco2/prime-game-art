"""The clip libraries of the retarget and the review (docs/animations.md, "Sources"): a library is a GLB on one rig
(UAL1, UAL2, or since art #25 a Meshy rig) whose actions are its clips, retargeted onto our characters with the bone
map its review settings name. A Meshy library also has:

- `extra`: more GLBs on the same rig (Meshy returns each task as its own file: the rig's walking and running, the
  library actions merged into one file, a text-to-motion clip animated on the rig); their actions join the library.
  The rigs must agree (the same bone names, every rest head within 1 mm), or the load fails.
- `rename` (action name -> clip name) and `skip` (action names left out: Meshy's one-frame "clip0" bind pose).
- `in_place`: clips whose hips travel (a walk backwards, a crawl): their horizontal travel from the first frame to the
  last is taken out linearly, as an in-place file does, keeping the sway within the cycle.

own_character() loads a library's own GLB (Meshy's rig and weights on our mesh: comparison (a) of art #25) with its
bones renamed to ours through the bone map, so the review's measures, which name our bones, read it as they read a
retargeted clip on a pack character.
"""

from __future__ import annotations

import os

import bpy

import retarget_core as rc

REST_TOLERANCE_M = 0.001  # the largest rest head offset between two files of one library's rig


def entry(cfg: dict, lib: str) -> dict:
    """A library's review settings ({} for UAL1, which has none)."""
    return cfg.get("libraries", {}).get(lib, {})


class InPlace(rc.Sampler):
    """A sampler of an action whose top bone (the hips, with no parent) travels: the horizontal travel between the
    first and the last frame is taken out in proportion to time."""

    def __init__(self, action, rig: rc.Rig, bone: str):
        super().__init__(action)
        if rig.parent.get(bone) is not None:
            raise ValueError(f"in place: {bone!r} is not the rig's top bone")
        self.bone = bone
        p0 = rig.W @ rc.fk(rig, super().basis(self.start))[bone].translation
        p1 = rig.W @ rc.fk(rig, super().basis(self.end))[bone].translation
        travel = p1 - p0
        travel.z = 0.0
        self.travel_m = travel.length
        # world -> armature space (the armature's scale and rotation) -> the bone's rest frame, where its basis
        # location lives: a top bone's pose is rest @ basis, so a basis location l moves it by rest.rot @ l
        self.drift = rc.rot(rig.rest[bone]).inverted() @ (rig.Wi.to_3x3() @ travel)

    def basis(self, frame: float) -> dict:
        out = super().basis(frame)
        m = out.get(self.bone)
        if m is not None and self.frames > 0:
            m = m.copy()
            m.translation = m.translation - self.drift * ((frame - self.start) / self.frames)
            out[self.bone] = m
        return out


def _same_rig(a, b, path: str) -> None:
    ra = {x.name: a.matrix_world @ x.head_local for x in a.data.bones}
    rb = {x.name: b.matrix_world @ x.head_local for x in b.data.bones}
    if set(ra) != set(rb):
        raise SystemExit(f"{path}: another rig than the library's (bones {sorted(set(ra) ^ set(rb))})")
    worst = max((ra[n] - rb[n]).length for n in ra)
    if worst > REST_TOLERANCE_M:
        raise SystemExit(f"{path}: the rig's rest differs from the library's by {worst * 1000:.1f} mm")


def load(path: str, ent: dict | None = None, raw: str | None = None, hips: str | None = None) -> dict:
    """Imports a library: rc.load_glb's dict with `actions` {clip name: action} (the extra files' too, renamed, the
    skipped left out) and `samplers` {clip name: sampler} (in-place ones for `in_place`; `hips` names the top bone
    they hold, the bone map's hips source)."""
    ent = ent or {}
    src = rc.load_glb(path)
    actions = dict(src["actions"])
    for rel in ent.get("extra", []):
        extra_path = os.path.join(raw or "", rel)
        objs = set(bpy.data.objects)
        x = rc.load_glb(extra_path)
        _same_rig(src["arm"], x["arm"], extra_path)
        for act in x["actions"].values():
            act.use_fake_user = True  # kept once its armature is gone
        actions.update(x["actions"])
        for o in set(bpy.data.objects) - objs:
            bpy.data.objects.remove(o, do_unlink=True)
    rename, skip = ent.get("rename", {}), set(ent.get("skip", []))
    src["actions"] = {rename.get(n, n): act for n, act in actions.items() if n not in skip}
    rig = rc.Rig(src["arm"])
    in_place = set(ent.get("in_place", []))
    missing = in_place - set(src["actions"])
    if missing:
        raise SystemExit(f"{path}: in_place names clips the library lacks: {sorted(missing)}")
    src["samplers"] = {n: (InPlace(act, rig, hips) if n in in_place else rc.Sampler(act))
                       for n, act in src["actions"].items()}
    return src


def own_character(path: str, ent: dict, raw: str | None, bmap: dict) -> dict:
    """A library's own GLB as a character of the review: its mesh with the library rig's own weights, its bones and
    vertex groups renamed to ours through the bone map's [bones] (source -> target), its clips' samplers reading the
    renamed bones. The map's toes and feet become our Toe and Foot, so the measures find the shoes."""
    ch = load(path, ent, raw, bmap["hips"][0])
    names = bmap["bones"]
    for bone in ch["arm"].data.bones:
        if bone.name in names:
            bone.name = names[bone.name]
    for obj in ch["meshes"].values():
        for group in obj.vertex_groups:
            if group.name in names:  # Blender renames them with the bone; this covers a mesh it did not
                group.name = names[group.name]
    for s in ch["samplers"].values():
        s.channels = {names.get(b, b): c for b, c in s.channels.items()}
        if isinstance(s, InPlace):
            s.bone = names.get(s.bone, s.bone)
    for obj in ch["meshes"].values():
        flat_colours(obj)
    bpy.context.view_layer.update()
    return ch


def flat_colours(obj) -> int:
    """Gives a mesh whose colours live in a palette texture (Meshy's output of our rig input: one textured material)
    a flat material per palette colour, read at each face's UV, so the review's Workbench renders (material colours)
    show it in its colours like our characters. Returns the number of colours."""
    me = obj.data
    image = next((n.image for m in me.materials if m and m.use_nodes for n in m.node_tree.nodes
                  if n.type == "TEX_IMAGE" and n.image), None)
    if image is None or not me.uv_layers:
        return 0
    w, h = image.size
    px = list(image.pixels)  # the stored sRGB values, RGBA rows from the bottom
    uv = me.uv_layers.active.data
    mats, index = [], {}
    me.materials.clear()
    for poly in me.polygons:
        u, v = uv[poly.loop_indices[0]].uv
        x, y = min(max(int(u * w), 0), w - 1), min(max(int(v * h), 0), h - 1)
        rgb = tuple(round(c, 3) for c in px[(y * w + x) * 4:(y * w + x) * 4 + 3])
        if rgb not in index:
            mat = bpy.data.materials.new(f"{obj.name}_flat_{len(mats)}")
            lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]  # sRGB -> linear
            mat.diffuse_color = (*lin, 1.0)
            mat.roughness, mat.metallic = 0.8, 0.0
            index[rgb] = len(mats)
            mats.append(mat)
            me.materials.append(mat)
        poly.material_index = index[rgb]
    return len(mats)
