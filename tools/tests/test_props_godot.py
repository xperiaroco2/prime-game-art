"""The dressing library's Godot helpers (tools/runner/commands/_props.py): GLB points, pivot bounds, the light anchor's
check and the line-up plan. Pure Python; no Godot needed."""

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner.commands import _props  # noqa: E402


def _glb(path: Path, nodes: list, points: list) -> None:
    """A minimal GLB: one float VEC3 POSITION accessor per mesh, the nodes as given."""
    blob = b"".join(struct.pack("<3f", *p) for pts in points for p in pts)
    views, accs, meshes, off = [], [], [], 0
    for k, pts in enumerate(points):
        views.append({"buffer": 0, "byteOffset": off, "byteLength": 12 * len(pts)})
        accs.append({"bufferView": k, "componentType": 5126, "type": "VEC3", "count": len(pts)})
        meshes.append({"primitives": [{"attributes": {"POSITION": k}}]})
        off += 12 * len(pts)
    gltf = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": nodes, "meshes": meshes,
            "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(blob)}]}
    js = json.dumps(gltf).encode("utf-8")
    js += b" " * (-len(js) % 4)
    blob += b"\0" * (-len(blob) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(blob), 0x004E4942) + blob
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body)


class GlbPointsTest(unittest.TestCase):
    def test_world_points_through_the_node_tree(self):
        with tempfile.TemporaryDirectory() as d:
            glb = Path(d) / "t.glb"
            nodes = [{"name": "root", "translation": [1.0, 0.0, 0.0], "children": [1]},
                     {"name": "box_col0-convcolonly", "mesh": 0, "translation": [0.0, 2.0, 0.0]}]
            _glb(glb, nodes, [[(0.0, 0.0, 0.0), (0.5, 0.5, 0.5)]])
            pts = _props.glb_points(glb)
        self.assertEqual(pts["box_col0-convcolonly"], [[1.0, 2.0, 0.0], [1.5, 2.5, 0.5]])
        self.assertNotIn("root", pts)


class PivotBoundsTest(unittest.TestCase):
    def test_floor_wall_and_ceiling(self):
        size = [1.0, 2.0, 0.4]
        self.assertEqual(_props.pivot_bounds(size, "floor"), {"min": [-0.5, 0.0, -0.2], "max": [0.5, 2.0, 0.2]})
        self.assertEqual(_props.pivot_bounds(size, "wall"), {"min": [-0.5, 0.0, 0.0], "max": [0.5, 2.0, 0.4]})
        self.assertEqual(_props.pivot_bounds(size, "ceiling"), {"min": [-0.5, -2.0, -0.2], "max": [0.5, 0.0, 0.2]})


class AnchorTest(unittest.TestCase):
    def test_fixture_anchor_must_match(self):
        rec = {"light_anchor": [0.0, 1.0, 0.1]}
        good = {"anchors": [{"name": "LightAnchor", "position": [0.0, 1.002, 0.1]}]}
        far = {"anchors": [{"name": "LightAnchor", "position": [0.0, 1.2, 0.1]}]}
        self.assertEqual(_props.evaluate_anchor("lamp", good, rec), [])
        self.assertEqual(len(_props.evaluate_anchor("lamp", far, rec)), 1)
        self.assertEqual(len(_props.evaluate_anchor("lamp", {"anchors": []}, rec)), 1)

    def test_no_anchor_on_other_props(self):
        rec = {"light_anchor": None}
        self.assertEqual(_props.evaluate_anchor("chair", {"anchors": []}, rec), [])
        self.assertEqual(len(_props.evaluate_anchor("chair", {"anchors": [{"name": "LightAnchor"}]}, rec)), 1)
        self.assertEqual(_props.evaluate_anchor("chair", {"error": "cannot load"}, rec), [])


class SheetPlanTest(unittest.TestCase):
    def test_sheets_rows_and_order(self):
        props = [{"id": f"p{k}", "batch": 2 if k < 10 else 1} for k in range(30)]
        built = {f"p{k}": {"size_m": [1.0, float(k), 1.0]} for k in range(30)}
        built["p5"] = {"error": "failed"}
        plan = _props.sheet_plan(props, built, sheets=4, row=3)
        ids = [i for sheet in plan for row in sheet for i in row]
        self.assertEqual(len(plan), 4)
        self.assertEqual(sorted(ids), sorted(f"p{k}" for k in range(30) if k != 5))
        self.assertTrue(all(len(row) <= 3 for sheet in plan for row in sheet))
        self.assertTrue(all(i in {f"p{k}" for k in range(10, 30)} for row in plan[0] for i in row))  # batch 1 first
        heights = [built[i]["size_m"][1] for row in plan[1] for i in row]
        self.assertEqual(heights, sorted(heights, reverse=True))  # tallest first
        self.assertEqual(_props.sheet_plan([], {}), [])


if __name__ == "__main__":
    unittest.main()
