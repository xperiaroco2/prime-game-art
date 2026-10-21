"""The manta's skin (tools/blender/ship_hull_skin.py, art #263): plain geometry, no Blender. Every grid variant keeps
the rooms inside, the placed variant's tip fairing meets the wing's last section, the window and the mouth are cut,
and the skin's faces point outward after the harness's mirror."""

from __future__ import annotations

import math
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "blender"))

from runner import ship_layout as sl  # noqa: E402

import ship_hull_skin as S  # noqa: E402

LAYOUT = sl.load()
with (ROOT / "layouts" / "ship" / "exterior.toml").open("rb") as f:
    EXT = tomllib.load(f)


def newell(p):
    n = [0.0, 0.0, 0.0]
    for a, b in zip(p, p[1:] + p[:1]):
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


class HullSkinTest(unittest.TestCase):
    def test_every_variant_keeps_the_rooms_inside(self) -> None:
        for name, var in S.VARIANTS.items():
            self.assertEqual(S.clearance(var), [], f"variant {name}")

    def test_the_placed_pieces_use_one_variant(self) -> None:
        variants = {p["args"]["variant"] for p in EXT["pieces"] if p["builder"] in ("hull_skin", "skin_stripes")}
        self.assertEqual(len(variants), 1)
        self.assertIn(variants.pop(), S.VARIANTS)

    def test_the_tip_fairing_meets_the_last_wing_section(self) -> None:
        for name, var in S.VARIANTS.items():
            loop = S.section(S.TIP_X, var)
            front = S.tip_profile(var, -math.pi / 2)
            back = S.tip_profile(var, math.pi / 2)
            # loop points 12, 13, 0..4 are the front profile's points 1..7; 11, 10, 9..5 the back's
            for k, j in zip((12, 13, 0, 1, 2, 3, 4), range(1, 8)):
                self.assertAlmostEqual(loop[k][0], -front[j][0], delta=0.02, msg=f"{name} front {k}")
                self.assertAlmostEqual(loop[k][1], front[j][1], delta=0.02, msg=f"{name} front {k}")
            for k, j in zip((11, 10, 9, 8, 7, 6, 5), range(1, 8)):
                self.assertAlmostEqual(loop[k][0], back[j][0], delta=0.02, msg=f"{name} back {k}")
                self.assertAlmostEqual(loop[k][1], back[j][1], delta=0.02, msg=f"{name} back {k}")

    def test_the_window_and_the_mouth_are_open(self) -> None:
        tip = S.hull_skin({"part": "tip", "side": 1.0, "variant": "F"}, LAYOUT)
        seam = [p for p in tip if p["name"].endswith("_seam")][0]
        for face in seam["faces"]:
            c = [sum(seam["verts"][i][k] for i in face) / len(face) for k in range(3)]
            ang = math.degrees(math.atan2(c[1], c[0] - S.TIP_X))
            r = math.hypot(c[0] - S.TIP_X, c[1])
            self.assertFalse(abs(ang) < 64 and S.SILL + 0.05 < c[2] < S.HEAD - 0.05 and r > 2.2,
                             f"skin across the window at {c}")
        body = S.hull_skin({"part": "body", "side": 1.0, "variant": "F"}, LAYOUT)
        seam = [p for p in body if p["name"].endswith("_seam")][0]
        for face in seam["faces"]:
            c = [sum(seam["verts"][i][k] for i in face) / len(face) for k in range(3)]
            self.assertFalse(c[0] < 1.3 and c[1] < -4.5 and 1.0 < c[2] < 3.6, f"skin across the mouth at {c}")

    def test_faces_point_outward_after_the_mirror(self) -> None:
        """The harness writes (x, -y, h): after it, every wing face's normal points away from its section's middle."""
        for part in ("wing1", "wing2"):
            parts = S.hull_skin({"part": part, "side": 1.0, "variant": "F"}, LAYOUT)
            seam = [p for p in parts if p["name"].endswith("_seam")][0]
            verts = [(x, -y, h) for x, y, h in seam["verts"]]
            for face in seam["faces"]:
                p = [verts[i] for i in face]
                c = [sum(q[k] for q in p) / len(p) for k in range(3)]
                loop = S.section(c[0], S.VARIANTS["F"])
                mid = (-sum(q[0] for q in loop) / 14, 2.4)
                n = newell(p)
                self.assertGreater(n[1] * (c[1] - mid[0]) + n[2] * (c[2] - mid[1]), 0.0, f"inward face at {c}")

    def test_the_footprint_rows_follow_the_skin(self) -> None:
        rows = {r[0]: r for r in LAYOUT["hull"]["core"]}
        for x, lead, trail in S.outline(S.VARIANTS["F"]):
            if x in rows:
                self.assertAlmostEqual(rows[x][1], lead, delta=0.02, msg=f"lead at x {x}")
                self.assertAlmostEqual(rows[x][2], trail, delta=0.02, msg=f"trail at x {x}")


if __name__ == "__main__":
    unittest.main()
