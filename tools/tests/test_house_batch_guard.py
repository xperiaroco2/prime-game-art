"""#107: what the merged shell and the batched dressing must never take. A station, a house.toml [merge] keep piece
(it moves or opens in the game) and a [merge] keep_props prop (the game moves or uses it) are never hidden nor drawn
by a merged or batch mesh. Two guards: the real filter (house.py `merger` on tiny GLBs in a temporary raw folder) and
the committed room scenes (no hidden visual of such a node; each batch and merged mesh holds exactly the vertices of
the visuals its group hides). Pure Python; the committed check skips when the GLBs are LFS pointers."""

from __future__ import annotations

import json
import re
import struct
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from runner import house_contract as C
from runner import house_merge as M
from runner.commands import house as HC

IDENT = "Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)"
SETTINGS = tomllib.loads((C.ROOT / "layouts" / "house" / "house.toml").read_text(encoding="utf-8"))


def tiny_glb(path: Path, nodes: list[str]) -> Path:
    """A GLB with one triangle node per name (one material each)."""
    blob = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 0, 1)
    j = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}],
         "nodes": [{"name": n, "mesh": i} for i, n in enumerate(nodes)],
         "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "material": i}]} for i in range(len(nodes))],
         "materials": [{"name": f"m_{n}"} for n in nodes],
         "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
                        "min": [0, 0, 0], "max": [1, 0, 1]}],
         "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(blob)}],
         "buffers": [{"byteLength": len(blob)}]}
    js = json.dumps(j).encode()
    js += b" " * (-len(js) % 4)
    body = struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(blob), b"BIN\0") + blob
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)
    return path


class RealFilter(unittest.TestCase):
    """house.py merger's own merge and batch callables, on a temporary raw folder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        kit = root / "raw" / "kit"
        kit.mkdir(parents=True)
        for pid in ("wall_a", "wall_b", "floor_a", "door"):
            tiny_glb(kit / f"{pid}.glb", [pid])
        (kit / "pieces.json").write_text(json.dumps([{"id": p, "uv2_per_m": 0.25} for p in ("wall_a", "wall_b")]),
                                         encoding="utf-8")
        props = root / "props"
        props.mkdir()
        self.found = {pid: tiny_glb(props / f"{pid}.glb", [pid]) for pid in ("chair", "lamp", "desk", "car")}
        self.data = {"settings": {"kit_dir": "kit", "kit_res": "res://k/{id}.glb", "prop_res": "res://p/{id}.glb",
                                  "merge": {"keep": ["door"], "keep_props": ["car"]}}}
        self.root = root
        patch = mock.patch.object(HC.common, "raw_dir", return_value=root / "raw")
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.tmp.cleanup)

    def merger(self):
        return HC.merger(self.data, self.found, out=self.root / "out")

    def test_keep_pieces_are_never_hidden_nor_merged(self):
        merge = self.merger()
        pieces = [{"id": pid, "node": f"{pid}_{n}", "transform": IDENT}
                  for pid, n in (("wall_a", 1), ("wall_b", 1), ("wall_a", 2), ("door", 1), ("door", 2))]
        got = merge("ground", "hall", pieces)
        self.assertEqual(got["hide"], {"wall_a_1", "wall_b_1", "wall_a_2"})
        self.assertEqual(got["add"], [("merged_shell", "res://k/shell_m_ground_hall.glb")])
        self.assertEqual(vertices(merge.files["shell_m_ground_hall"]), 9)  # three walls of one triangle, no door

    def test_stations_and_keep_props_are_never_hidden_nor_batched(self):
        batch = self.merger().batch
        at = {"at": (0.0, 0.0, 0.0), "yaw": 0.0}
        items = [({"id": "chair", **at}, "chair_1"), ({"id": "chair", **at}, "chair_2"), ({"id": "lamp", **at}, "lamp_1"),
                 ({"id": "desk", "station": "fix_pc", **at}, "desk_1"), ({"id": "car", **at}, "car_1")]
        got = batch("ground", "garage", "Dressing", items)
        self.assertEqual(got["hide"], {"chair_1": ["chair"], "chair_2": ["chair"], "lamp_1": ["lamp"]})
        name = "batch_ground_garage_dressing"
        self.assertEqual(got["add"], [("batch_dressing", f"res://p/{name}.glb", name)])
        self.assertEqual(vertices(self.root / "out" / f"{name}.glb"), 9)  # two chairs and a lamp, no desk, no car

    def test_a_merged_piece_with_a_second_visual_mesh_is_refused(self):
        tiny_glb(self.root / "raw" / "kit" / "wall_b.glb", ["wall_b", "wall_b_leaf"])
        merge = self.merger()
        pieces = [{"id": "wall_a", "node": "wall_a_1", "transform": IDENT},
                  {"id": "wall_b", "node": "wall_b_1", "transform": IDENT}]
        with self.assertRaisesRegex(ValueError, "wall_b_leaf"):
            merge("ground", "hall", pieces)


def vertices(path: Path, names: set | None = None) -> int:
    """The POSITION count of a GLB's visual nodes (all, or those named)."""
    j, _ = C.glb_json(path)
    total = 0
    for n in j["nodes"]:
        name = n.get("name", "")
        if "mesh" in n and not name.endswith(M.COLLIDER) and (names is None or name in names):
            total += sum(j["accessors"][p["attributes"]["POSITION"]]["count"] for p in j["meshes"][n["mesh"]]["primitives"])
    return total


class CommittedScenes(unittest.TestCase):
    """Every committed room scene of the House packages."""

    @classmethod
    def setUpClass(cls):
        cls.scenes = sorted((C.ROOT / "assets" / "room").glob("*/export/**/*.tscn"))
        probe = next((C.ROOT / "assets" / "room").glob("*/export/merged/*.glb"), None)
        if not cls.scenes or probe is None or probe.read_bytes()[:4] != b"glTF":
            raise unittest.SkipTest("no committed room scenes or merged GLBs (LFS pointers?)")
        cls.resolve = staticmethod(C.committed_resolver())
        merge = SETTINGS["merge"]
        cls.keep, cls.keep_props = set(merge["keep"]), set(merge["keep_props"])

    def walk(self, f: Path):
        ext, sections = C.parse_tscn(f.read_text(encoding="utf-8"))
        nodes = {}
        for s in sections:
            props = dict(s["props"])
            inst = re.fullmatch(r'ExtResource\("([^"]*)"\)', s["attrs"].get("instance", ""))
            nodes[C._path(s["attrs"])] = {"props": props, "res": ext[inst.group(1)] if inst else None}
        return nodes

    def test_protected_nodes_are_drawn_and_batches_hold_only_hidden_visuals(self):
        checked = {"protected": 0, "batches": 0}
        for f in self.scenes:
            nodes = self.walk(f)
            hidden = {p for p, n in nodes.items() if n["props"].get("visible") == "false"}
            for path, n in nodes.items():
                if n["res"] is None:
                    continue
                stem = Path(n["res"]).stem
                prop = n["props"].get("metadata/prop", "").strip('"')
                kit_keep = "/house_kit/" in n["res"] and stem in self.keep
                if "metadata/station" in n["props"] or prop in self.keep_props or kit_keep:
                    checked["protected"] += 1
                    bad = sorted(h for h in hidden if h == path or h.startswith(path + "/"))
                    self.assertEqual(bad, [], f"{f.name}: {path} ({stem}) has hidden visuals")
            groups: dict = {}  # group path -> {mesh kind: [res]} and the hidden visuals' vertices per kind
            for h in hidden:
                inst = h.rsplit("/", 1)[0]
                res = nodes.get(inst, {}).get("res")
                self.assertIsNotNone(res, f"{f.name}: hidden {h} is not a child of an instance")
                group = inst.rsplit("/", 1)[0]
                stem = Path(res).stem
                kind = ("batch" if "metadata/prop" in nodes[inst]["props"] else
                        next((c for c in ("floor", "ceiling") if stem.startswith(c + "_")), "shell"))
                g = groups.setdefault((group, kind), {"hidden": 0})
                g["hidden"] += vertices(self.resolve(res), {h.rsplit("/", 1)[1]})
            for (group, kind), g in groups.items():
                mesh = f"{group}/{'batch_' + group.lower() if kind == 'batch' else 'merged_' + kind}"
                self.assertIn(mesh, nodes, f"{f.name}: {group} hides {kind} visuals without {mesh}")
                self.assertEqual(vertices(self.resolve(nodes[mesh]["res"])), g["hidden"],
                                 f"{f.name}: {mesh} does not hold exactly the visuals {group} hides")
                checked["batches"] += kind == "batch"
        self.assertGreater(checked["protected"], 10)
        self.assertGreater(checked["batches"], 10)


if __name__ == "__main__":
    unittest.main()
