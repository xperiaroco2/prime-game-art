"""The first-person hands' rig seed (art#136): the armature the detailed hand is built on, kept as data in git.

The detailed hand (fp_hand_model.py) took its rig and skin colour from the axolotl character build of art#196 H1u,
which lived only in the raw folder on D: and is gone since 2026-11-18. The committed hands asset t4
(assets/body/fp_hands/source/fp_hands.blend, the engineer's choice of 2026-11-18 to go on from it) holds the same
character's arm rig: its FPRig armature kept the character's arm, hand and finger bones untouched in the armature's
space (fp_hands_build.py's cut only removes the other bones and adds View at the eye and Crystal). This script reads
that armature once into tools/blender/fp_rig_seed.json; fp_hand_model.py builds its armature from the JSON.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/fp_rig_seed.py -- \
        --blend assets/body/fp_hands/source/fp_hands.blend --out tools/blender/fp_rig_seed.json

The JSON: the source file's repo path and SHA-256; per bone (parents first) its name, parent, head and tail in the
armature's space (m), its z axis (the roll), connect and deform flags; the round trip's largest error (a rig built
from the JSON against the source's bones, m and the axes' dot products).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]


def bone_rows(arm) -> list[dict]:
    rows = []
    for b in arm.data.bones:   # Blender lists a bone after its parent
        z = b.matrix_local.col[2].to_3d()
        rows.append({"name": b.name, "parent": b.parent.name if b.parent else None,
                     "head": [round(x, 6) for x in b.head_local], "tail": [round(x, 6) for x in b.tail_local],
                     "z": [round(x, 6) for x in z], "connect": b.use_connect, "deform": b.use_deform})
    return rows


def build(seed: dict, name: str = "FPRig"):
    """An armature object from the seed, linked to the scene, at the world's origin, in object mode."""
    data = bpy.data.armatures.new(name)
    arm = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(arm)
    for o in bpy.context.scene.objects:
        if o is not arm:
            o.select_set(False)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = data.edit_bones
    for r in seed["bones"]:
        b = eb.new(r["name"])
        b.head, b.tail = Vector(r["head"]), Vector(r["tail"])
        b.align_roll(Vector(r["z"]))
        b.use_deform = bool(r["deform"])
    for r in seed["bones"]:
        if r["parent"]:
            eb[r["name"]].parent = eb[r["parent"]]
            eb[r["name"]].use_connect = bool(r["connect"])
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return arm


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv) -> None:
    ap = argparse.ArgumentParser(prog="fp_rig_seed.py")
    ap.add_argument("--blend", required=True, help="the hands asset's .blend (repo path)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--armature", default="FPRig")
    a = ap.parse_args(argv)
    src = (ROOT / a.blend).resolve()
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(src))
    arm = bpy.data.objects[a.armature]
    seed = {"source": Path(a.blend).as_posix(), "sha256": sha, "armature": a.armature, "bones": bone_rows(arm)}
    # the round trip: a rig built from the rows matches the source's bones
    copy = build(seed, "FPRigSeedCheck")
    dp, dz = 0.0, 1.0
    for b in arm.data.bones:
        c = copy.data.bones[b.name]
        dp = max(dp, (b.head_local - c.head_local).length, (b.tail_local - c.tail_local).length)
        dz = min(dz, b.matrix_local.col[2].to_3d().dot(c.matrix_local.col[2].to_3d()))
        assert (b.parent.name if b.parent else None) == (c.parent.name if c.parent else None), b.name
    seed["roundtrip"] = {"max_pos_m": round(dp, 9), "min_z_dot": round(dz, 9)}
    if dp > 1e-5 or dz < 0.99999:
        raise SystemExit(f"the seed does not rebuild the rig: {seed['roundtrip']}")
    head = {k: v for k, v in seed.items() if k != "bones"}
    lines = [json.dumps(head, indent=1)[:-2] + ',\n "bones": [']
    lines.append(",\n".join("  " + json.dumps(r) for r in seed["bones"]))
    lines.append(" ]\n}\n")
    text = "\n".join(lines)
    assert json.loads(text) == seed
    Path(a.out).write_text(text, encoding="utf-8")
    print("FP_RIG_SEED " + json.dumps({"bones": len(seed["bones"]), "roundtrip": seed["roundtrip"], "sha256": sha}))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
