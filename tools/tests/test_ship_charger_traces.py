"""The charger traces on the lens alcoves' back panel (art #263, prime-game#1095 c6468773545; docs/ship.md "Lens room
C"): the layout mirrored, every line orthogonal or at 45 degrees, apart from the others and inside the panel, the
ring centred on the crystal's axis, the fill coordinate 0 at each outer end to 1 at the ring (a branch meeting its
trunk's value at the junction), the faces toward the room, and the shader shipped with the export. Plain Python (the
builder's parts, no Blender)."""

from __future__ import annotations

import math
import re
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
sys.path.insert(0, str(ROOT / "tools"))
import ship_interior_lens as LN  # noqa: E402
from runner import ship_export as X  # noqa: E402

LAY = LN.trace_layout()
STROKES = {s["name"]: s for s in LAY["strokes"]}
with (ROOT / "tools" / "blender" / "charger_dims.toml").open("rb") as _f:
    DIMS = tomllib.load(_f)


def seg_dist(p, a, b) -> float:
    ax, ay, bx, by = *a, *b
    L2 = (bx - ax) ** 2 + (by - ay) ** 2
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / L2))
    return math.hypot(p[0] - ax - t * (bx - ax), p[1] - ay - t * (by - ay))


def samples(stroke: dict, step: float = 0.25) -> list[tuple[float, float]]:
    """Points along a stroke's centre line every `step` cm."""
    out = []
    for a, b in zip(stroke["pts"], stroke["pts"][1:]):
        n = max(1, round(math.dist(a, b) / step))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1)]
    return out


def fill_at(stroke: dict, q) -> float | None:
    """A stroke's fill at a point on its centre line (None off it)."""
    pts, fill = stroke["pts"], stroke["fill"]
    for (a, b), (fa, fb) in zip(zip(pts, pts[1:]), zip(fill, fill[1:])):
        if seg_dist(q, a, b) < 1e-6:
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            return fa + (fb - fa) * math.hypot(q[0] - a[0], q[1] - a[1]) / L
    return None


class TraceLayoutTest(unittest.TestCase):
    def test_mirrored_left_to_right(self) -> None:
        for name, s in STROKES.items():
            if name.endswith("_r"):
                other = STROKES[name[:-2] + "_l"]
                self.assertEqual([(-u, h) for u, h in s["pts"]], other["pts"], name)
                self.assertEqual(s["fill"], other["fill"], name)
        self.assertTrue(all(u == 0.0 for u, _ in STROKES["centre"]["pts"]))
        dots = {d["name"]: d["at"] for d in LAY["dots"]}
        self.assertEqual(dots["dot_l"], (-dots["dot_r"][0], dots["dot_r"][1]))

    def test_orthogonal_with_45_degree_bends(self) -> None:
        for s in LAY["strokes"]:
            for a, b in zip(s["pts"], s["pts"][1:]):
                ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 45.0
                self.assertTrue(min(ang, 45.0 - ang) < 1e-6, (s["name"], a, b))

    def test_inside_the_panel_and_apart(self) -> None:
        A, w = LN.ALCOVE, LN.TRACE["w"]
        for s in LAY["strokes"]:
            for u, h in s["pts"]:
                self.assertLessEqual(abs(u), A["open_back"] + 0.5, s["name"])
                self.assertLessEqual(h, A["top"] + 0.5, s["name"])
        # two lines never closer than two widths (centre to centre), but a branch's last 3 widths, where it meets its
        # trunk at 45 degrees
        pts = {}
        for name, s in STROKES.items():
            pts[name] = [q for q in samples(s) if s["kind"] == "trunk" or math.dist(q, s["pts"][-1]) > 3 * w]
        names = list(STROKES)
        for i, n0 in enumerate(names):
            for n1 in names[i + 1:]:
                d = min(math.dist(p, q) for p in pts[n0] for q in pts[n1])
                self.assertGreater(d, 2 * w, (n0, n1))

    def test_ring_centred_on_the_crystal_axis(self) -> None:
        u, h, r, w = LAY["ring"]
        self.assertEqual((u, h, r, w), (0.0, 115.0, 18.0, 1.5))   # the design: h 115, about 36 across, a 1.5 line
        self.assertEqual(LN.AXIS_D, DIMS["frame"]["axis_d"])      # u 0 is the crystal's axis in the charger's frame
        ring = next(p for p in LN.trace_parts() if p["name"] == "trace_ring")
        cu = sum(v[1] for v in ring["verts"]) / len(ring["verts"]) * 100
        ch = (sum(v[2] for v in ring["verts"]) / len(ring["verts"]) - LN.FLOOR) * 100
        self.assertAlmostEqual(cu, 0.0, places=6)
        self.assertAlmostEqual(ch, 115.0, places=6)
        radii = sorted({round(math.hypot(v[1] * 100, (v[2] - LN.FLOOR) * 100 - 115.0), 4) for v in ring["verts"]})
        self.assertEqual(radii, [17.25, 18.75])

    def test_lines_end_on_the_ring_or_their_trunk(self) -> None:
        r, hc = LN.TRACE["ring_r"], LN.TRACE["ring_h"]
        trunks = [s for s in LAY["strokes"] if s["kind"] == "trunk"]
        for s in LAY["strokes"]:
            end = s["pts"][-1]
            if s["kind"] == "trunk":
                self.assertAlmostEqual(math.hypot(end[0], end[1] - hc), r, places=6, msg=s["name"])
            else:
                on = [t for t in trunks if fill_at(t, end) is not None]
                self.assertEqual(len(on), 1, s["name"])
                self.assertAlmostEqual(s["fill"][-1], fill_at(on[0], end), places=9, msg=s["name"])


class TraceFillTest(unittest.TestCase):
    def test_fill_runs_0_to_1_along_each_line(self) -> None:
        for s in LAY["strokes"]:
            f = s["fill"]
            self.assertEqual(f[0], 0.0, s["name"])
            self.assertTrue(all(b > a for a, b in zip(f, f[1:])), s["name"])
            self.assertTrue(0.0 < f[-1] <= 1.0, s["name"])
            if s["kind"] == "trunk":
                self.assertAlmostEqual(f[-1], 1.0, places=12, msg=s["name"])
            # proportional to the arc length: scale cm per unit of fill
            arc = LN._seg_len(s["pts"])
            for a, x in zip(arc, f):
                self.assertAlmostEqual(a, x * s["scale"], places=6, msg=s["name"])

    def test_parts_carry_the_fill_in_their_uv(self) -> None:
        parts = {p["name"]: p for p in LN.trace_parts()}
        self.assertEqual(set(parts), {"trace_lines", "trace_dots", "trace_ring"})
        for p in parts.values():
            self.assertEqual(p["mat"], "lens_trace")
            self.assertFalse(p["solid"])
            self.assertEqual(len(p["uv"]), len(p["faces"]))
            for face, uvs in zip(p["faces"], p["uv"]):
                self.assertEqual(len(face), len(uvs))
                for x, v in uvs:
                    self.assertTrue(0.0 <= x <= 1.0)
                    y = 1.0 - v                                   # Godot's UV.y after the glTF exporter's flip
                    if p["name"] == "trace_ring":
                        self.assertEqual((x, y), (1.0, -1.0))
                    else:
                        self.assertTrue(0.3 < y < 1.5, (p["name"], y))   # metres of line per unit of fill
        self.assertTrue(all(x == 0.0 for uvs in parts["trace_dots"]["uv"] for x, _ in uvs))

    def test_faces_toward_the_room_once_built(self) -> None:
        # the harness builds plan (x, y, h) as Blender (x, -y, h); the room is toward -x
        for p in LN.trace_parts():
            for face in p["faces"]:
                a, b, c = ((v[0], -v[1], v[2]) for v in (p["verts"][i] for i in face[:3]))
                nx = (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1])
                self.assertLess(nx, 0.0, p["name"])

    def test_layers_over_the_panel_never_coplanar(self) -> None:
        lift = LN.TRACE["lift"]
        self.assertLess(0.0, lift["branch"])
        self.assertLess(lift["branch"], lift["trunk"])
        self.assertLess(lift["trunk"], min(lift["dot"], lift["ring"]))
        parts = {p["name"]: p for p in LN.trace_parts()}
        d = {n: sorted({round(-v[0] * 100 - LN.ALCOVE["back"], 4) for v in p["verts"]}) for n, p in parts.items()}
        self.assertEqual(d["trace_ring"], [lift["ring"]])
        self.assertEqual(d["trace_dots"], [lift["dot"]])
        self.assertEqual(d["trace_lines"], [lift["branch"], lift["trunk"]])


class TraceShaderTest(unittest.TestCase):
    def test_the_shader_ships_with_the_export(self) -> None:
        self.assertIn("charger/traces.gdshader", X.SHADERS)
        self.assertTrue((ROOT / "godot" / "charger" / "traces.gdshader").is_file())
        text = X.relocate('[ext_resource type="Shader" path="res://charger/traces.gdshader" id="3_t"]\n')
        self.assertIn(f'path="res://{X.ASSET_DIR}/charger_traces.gdshader"', text)
        self.assertEqual(X.leftovers(text), [])

    def test_ship_and_traces_gd_use_the_same_shader_and_material(self) -> None:
        ship = (ROOT / "godot" / "ship" / "ship.gd").read_text(encoding="utf-8")
        charger = (ROOT / "godot" / "charger" / "traces.gd").read_text(encoding="utf-8")
        self.assertIn('const TRACE_SHADER := "res://charger/traces.gdshader"', ship)
        self.assertIn('preload("res://charger/traces.gdshader")', charger)
        # the panel is the ship's, not the charger package's: charger.gd (copied into its asset) stays free of it
        self.assertNotIn("traces", (ROOT / "godot" / "charger" / "charger.gd").read_text(encoding="utf-8"))
        for text in (ship, charger):
            self.assertEqual(re.findall(r'TRACE_MAT := "(\w+)"', text), ["lens_trace"])
        shader = (ROOT / "godot" / "charger" / "traces.gdshader").read_text(encoding="utf-8")
        for name in ("fill", "lit", "flare", "dim"):
            self.assertRegex(shader, rf"uniform float {name}\b")


if __name__ == "__main__":
    unittest.main()
