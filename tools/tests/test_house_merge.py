"""The merged shell's GLB writer (#107, tools/runner/house_merge.py): pieces merged where the scene puts them, the
kit's UV0 and vertex colours unchanged, UV2 islands packed apart inside [0, 1], one primitive per material, and a
uniform UV2 density. Pure Python on the committed kit GLBs (skips when they are LFS pointers)."""

from __future__ import annotations

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
