"""The merged shell's GLB writer (#107, tools/runner/house_merge.py): pieces merged where the scene puts them, the
kit's UV0 and vertex colours unchanged, UV2 islands packed apart inside [0, 1], one primitive per material, and a
uniform UV2 density. Pure Python on the committed kit GLBs (skips when they are LFS pointers)."""

from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from runner import house_merge as M

KIT = M.Path(__file__).resolve().parents[2] / "assets" / "kit" / "house_kit"
TURNED = "Transform3D(0, 0, 1, 0, 1, 0, -1, 0, 0, 4, 3, 2)"  # a quarter turn, then (4, 3, 2)
IDENT = "Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)"


class Pack(unittest.TestCase):
    def test_rects_do_not_overlap_and_fit(self):
        sizes = [(3.0, 2.0), (1.0, 1.0), (2.5, 4.0), (0.5, 0.5), (4.0, 1.0)]
        at, side = M.pack(sizes, gap=0.25)
        rects = [(x, y, x + w, y + h) for (x, y), (w, h) in zip(at, sizes)]
        for i, a in enumerate(rects):
            self.assertTrue(0 <= a[0] and 0 <= a[1] and a[2] <= side and a[3] <= side, a)
            for b in rects[i + 1:]:
                self.assertTrue(a[2] + 0.25 <= b[0] + 1e-9 or b[2] + 0.25 <= a[0] + 1e-9
                                or a[3] + 0.25 <= b[1] + 1e-9 or b[3] + 0.25 <= a[1] + 1e-9, (a, b))

    def test_rows_of_reads_the_scene_text(self):
        self.assertEqual(M.rows_of(TURNED), [[0, 0, 1, 4], [0, 1, 0, 3], [-1, 0, 0, 2]])


class Merge(unittest.TestCase):
    def glb(self, pid: str) -> Path:
        p = KIT / "export" / f"{pid}.glb"
        if not p.exists() or p.read_bytes()[:4] != b"glTF":
            self.skipTest(f"{p} missing or an LFS pointer")
        return p

    def test_two_pieces_merge_in_place(self):
        wall, window = self.glb("wall_storey_2m_int"), self.glb("wall_storey_2m_window_int")
        items = [{"glb": wall, "transform": IDENT, "class": "shell", "uv2_per_m": 0.2},
                 {"glb": window, "transform": TURNED, "class": "shell", "uv2_per_m": 0.14},
                 {"glb": wall, "transform": TURNED.replace("4, 3, 2", "0, 0, 6"), "class": "floor", "uv2_per_m": 0.2}]
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "m.glb"
            rec = M.merge(items, out)
            prims = M.visual(out)
        self.assertEqual(sorted(rec["classes"]), ["floor", "shell"])
        self.assertEqual(rec["classes"]["shell"]["materials"], ["kit_glass-vcol", "kit_set-vcol"])
        self.assertEqual(len(prims), 3)  # floor: kit_set; shell: glass, set
        src_w, src_g = M.visual(wall), M.visual(window)
        shell_set = next(p for p in prims if p["node"] == "merged_shell" and p["material"]["name"] == "kit_set-vcol")
        n = len(src_w[0]["pos"])
        self.assertEqual([tuple(round(c, 5) for c in v) for v in shell_set["pos"][:n]],
                         [tuple(round(c, 5) for c in v) for v in src_w[0]["pos"]])
        turned = [(v[2] + 4, v[1] + 3, -v[0] + 2) for p in src_g if p["material"]["name"] == "kit_set-vcol"
                  for v in p["pos"]]
        self.assertEqual([tuple(round(c, 4) for c in v) for v in shell_set["pos"][n:]],
                         [tuple(round(c, 4) for c in v) for v in turned])
        self.assertEqual(shell_set["uv0"][:n], src_w[0]["uv0"])  # the look: UV0 and colours as the piece's
        self.assertTrue(all(abs(a - b) < 1e-4 for u, v in zip(shell_set["col"][:n], src_w[0]["col"])
                            for a, b in zip(u, v)))
        for p in prims:
            self.assertTrue(all(0 <= c <= 1 for t in p["uv1"] for c in t))
        self.assertGreater(rec["classes"]["shell"]["uv2_per_m"], 0)


if __name__ == "__main__":
    unittest.main()


def tiny_glb(path: Path, material: dict, x: float = 0.0) -> Path:
    """One triangle at x with one material: a stand-in prop GLB."""
    pos = struct.pack("<9f", x, 0, 0, x + 1, 0, 0, x, 1, 0)
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"name": "lamp", "mesh": 0}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "material": 0}]}], "materials": [material],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
                          "min": [x, 0, 0], "max": [x + 1, 1, 0]}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(pos)}],
           "buffers": [{"byteLength": len(pos)}]}
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(pos), 0x004E4942) + pos
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body)
    return path


class Variants(unittest.TestCase):
    """#184's review: two prop GLBs may give one material name different values (a red safelight and a bare bulb
    both `kit_emissive-vcol`); each keeps its own surface and values."""

    def test_same_name_different_emission_stays_apart(self):
        red = {"name": "kit_emissive-vcol", "emissiveFactor": [1.0, 0.02, 0.01],
               "pbrMetallicRoughness": {"roughnessFactor": 0.5}}
        warm = {**red, "emissiveFactor": [1.0, 0.8, 0.5]}
        with tempfile.TemporaryDirectory() as d:
            items = [{"glb": tiny_glb(Path(d) / f"{i}.glb", m, x), "transform": IDENT, "class": "props",
                      "uv2_per_m": None} for i, (m, x) in enumerate([(red, 0), (warm, 2), (red, 4)])]
            rec = M.merge(items, Path(d) / "m.glb")
            prims = M.visual(Path(d) / "m.glb")
            from runner import house_export
            self.assertEqual(len(house_export.set_surfaces(Path(d) / "m.glb", "kit_emissive", posed=False)[0]
                                 ["surfaces"]), 2)
        self.assertEqual(rec["classes"]["props"]["materials"], ["kit_emissive-vcol", "kit_emissive__1-vcol"])
        got = {p["material"]["name"]: (p["material"]["emissiveFactor"], sorted(v[0] for v in p["pos"])) for p in prims}
        self.assertEqual(got["kit_emissive-vcol"], ([1.0, 0.02, 0.01], [0, 0, 1, 4, 4, 5]))
        self.assertEqual(got["kit_emissive__1-vcol"], ([1.0, 0.8, 0.5], [2, 2, 3]))

    def test_key_ignores_the_name_only(self):
        a = {"name": "a", "pbrMetallicRoughness": {"roughnessFactor": 0.5}}
        self.assertEqual(M.material_key(a), M.material_key({**a, "name": "b"}))
        self.assertNotEqual(M.material_key(a), M.material_key({**a, "pbrMetallicRoughness": {"roughnessFactor": 0.6}}))
        with self.assertRaises(ValueError):
            M.material_key({**a, "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}})
