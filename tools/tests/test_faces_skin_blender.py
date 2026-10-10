"""The face kit's surface without the recipe's as_skin pieces (tools/blender/um/heads.py mark_as_skin and
skin_only_copy, art #42) and the pack nose left unflattened (um/clayface/adapter.py FLATTEN_PACK_NOSE off), in headless
Blender on a small made-up head: a 4 x 4 grid whose skin faces use "Skin" and three faces "Skin_Darker.001" (the
Casual head's stubble, as the pack names a duplicate). Checks that mark_as_skin marks exactly the faces of the named
materials, that skin_only_copy returns an unlinked copy at the head's place without them, leaves the head whole and
removes the mark, and returns None when nothing is marked or the head was never marked.

This file is also the Blender side of the test: run inside Blender (`blender -b ... --python <this file> -- <out>`)
it writes its numbers to <out>/skin.json, which the unittest reads. Skipped when Blender is missing; needs no raw
files. One Blender run, a few seconds."""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

IN_BLENDER = "bpy" in sys.modules  # Blender runs this file with its bpy already loaded: the driver below runs

if not IN_BLENDER:
    from runner import blender, common, pins

    OUT = common.OUT / "tests" / "faces_skin"
    HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())

    @unittest.skipUnless(HAVE_BLENDER, f"needs Blender {pins.BLENDER} ({path})")
    class SkinOnlySurfaceTest(unittest.TestCase):
        r: dict = {}

        @classmethod
        def setUpClass(cls) -> None:
            shutil.rmtree(OUT, ignore_errors=True)
            OUT.mkdir(parents=True)
            blender.run_script(Path(__file__).resolve(), [str(OUT)], timeout=170)
            cls.r = json.loads((OUT / "skin.json").read_text(encoding="utf-8"))

        def test_the_pack_nose_is_not_flattened(self) -> None:
            self.assertIs(self.r["flatten_pack_nose"], False)

        def test_mark_as_skin_marks_the_named_materials(self) -> None:
            self.assertEqual(self.r["marked"], 3)
            self.assertTrue(self.r["attr_after_mark"])

        def test_the_copy_leaves_the_marked_faces_out(self) -> None:
            c = self.r["copy"]
            self.assertEqual(c["faces"], 16 - 3)
            self.assertEqual(c["materials_left"], ["Skin"])
            self.assertEqual(c["collections"], 0)  # unlinked
            self.assertFalse(c["same_mesh"])
            self.assertLess(c["matrix_diff"], 1e-6)  # at the head's place
            self.assertFalse(c["has_attr"])

        def test_the_head_stays_whole_and_loses_the_mark(self) -> None:
            self.assertEqual(self.r["head_faces_after"], 16)
            self.assertFalse(self.r["attr_after_copy"])

        def test_none_without_a_mark(self) -> None:
            self.assertTrue(self.r["second_copy_none"])  # the mark was read once
            self.assertEqual(self.r["marked_none"], 0)
            self.assertTrue(self.r["copy_none_when_nothing_marked"])
            self.assertFalse(self.r["attr_after_empty_copy"])


def _blender_main(argv: list[str]) -> None:
    import bmesh
    import bpy
    from mathutils import Matrix

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
    from um import heads
    from um.clayface import adapter

    me = bpy.data.meshes.new("head")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=4, y_segments=4, size=0.1)
    bm.to_mesh(me)
    bm.free()
    head = bpy.data.objects.new("head", me)
    bpy.context.scene.collection.objects.link(head)
    head.matrix_world = Matrix.Translation((0.1, -0.2, 1.7)) @ Matrix.Rotation(0.3, 4, "Z")
    for name in ("Skin", "Skin_Darker.001"):
        head.data.materials.append(bpy.data.materials.new(name))
    for i in (2, 7, 11):
        me.polygons[i].material_index = 1

    r = {"flatten_pack_nose": adapter.FLATTEN_PACK_NOSE}
    r["marked"] = heads.mark_as_skin(head, ["Skin_Darker"])
    r["attr_after_mark"] = me.attributes.get(heads.AS_SKIN_ATTR) is not None
    cp = heads.skin_only_copy(head)
    diff = max(abs(a - b) for ra, rb in zip(cp.matrix_world, head.matrix_world) for a, b in zip(ra, rb))
    r["copy"] = {"faces": len(cp.data.polygons), "collections": len(cp.users_collection), "same_mesh": cp.data == me,
                 "matrix_diff": diff, "has_attr": cp.data.attributes.get(heads.AS_SKIN_ATTR) is not None,
                 "materials_left": sorted({cp.data.materials[p.material_index].name for p in cp.data.polygons})}
    r["head_faces_after"] = len(me.polygons)
    r["attr_after_copy"] = me.attributes.get(heads.AS_SKIN_ATTR) is not None
    r["second_copy_none"] = heads.skin_only_copy(head) is None
    r["marked_none"] = heads.mark_as_skin(head, ["Hair"])
    r["copy_none_when_nothing_marked"] = heads.skin_only_copy(head) is None
    r["attr_after_empty_copy"] = me.attributes.get(heads.AS_SKIN_ATTR) is not None
    with open(Path(argv[0]) / "skin.json", "w", encoding="utf-8") as f:
        json.dump(r, f, indent=1)


if IN_BLENDER and __name__ == "__main__":
    _blender_main(sys.argv[sys.argv.index("--") + 1:])
elif __name__ == "__main__":
    unittest.main()
