"""M15 (art #196): the eye socket rebuilt for the 80 % eye (tools/blender/alien_fit_geom.py): the fill keeps a smooth
surface, the cut lays the covered skin onto the bowl behind the ball, the fillet keeps it outside the sphere, the fold
check, the placement and the slim lids' reach. The checks need numpy, which the runner's Python lacks: InBlender runs
them in background Blender's Python (skips without Blender)."""
from __future__ import annotations

import ast
import importlib.util
import json
import math
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
BLENDER = ROOT / "tools" / "blender"

try:
    import numpy as np
except ImportError:  # the runner is standard library only; numpy comes with Blender
    np = None


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, BLENDER / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def grid(n: int = 41, half: float = 0.08):
    """A flat sheet z = 0 facing +z (n x n vertices), its edges and triangles."""
    xs = np.linspace(-half, half, n)
    X, Y = np.meshgrid(xs, xs, indexing="ij")
    co = np.stack([X.ravel(), Y.ravel(), np.zeros(n * n)], 1)
    idx = np.arange(n * n).reshape(n, n)
    e = np.concatenate([np.stack([idx[:-1, :].ravel(), idx[1:, :].ravel()], 1),
                        np.stack([idx[:, :-1].ravel(), idx[:, 1:].ravel()], 1),
                        np.stack([idx[:-1, :-1].ravel(), idx[1:, 1:].ravel()], 1)])
    a, b, c, d = idx[:-1, :-1].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel(), idx[:-1, 1:].ravel()
    tris = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
    return co, e, tris


@unittest.skipIf(np is None, "numpy is not installed (Blender ships it)")
class FitGeom(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.F = load("alien_fit_geom")

    def test_fill_restores_a_dent(self):
        """A crater pressed into a flat sheet is filled back to the plane (nothing sinks round it)."""
        F = self.F
        co, e, _ = grid()
        r = np.hypot(co[:, 0], co[:, 1])
        dent = co.copy()
        dent[:, 2] -= 0.03 * np.clip(1 - r / 0.04, 0, 1)
        free = r < 0.045
        out = F.fair_fill(dent, F.Lap(len(co), e), free, 2000)
        self.assertLess(np.abs(out[:, 2]).max(), 1e-4)
        self.assertTrue(np.allclose(out[~free], dent[~free]))

    def test_cut_lays_the_disc_on_the_bowl(self):
        """The skin a sphere covers goes onto its far side; nothing stays inside it; no fold."""
        F = self.F
        co, e, tris = grid()
        c, a, R = np.array((0.0, 0.0, -0.01)), np.array((0.0, 0.0, 1.0)), 0.03
        ex, ey = np.array((1.0, 0.0, 0.0)), np.array((0.0, 1.0, 0.0))
        lap = F.Lap(len(co), e)
        region = np.ones(len(co), dtype=bool)
        tc = F.crossing_angles(co, e, region, c, a, ex, ey, R)
        self.assertAlmostEqual(float(tc.mean()), math.acos(0.01 / R), delta=0.05)
        ins = F.opening(co, c, a, ex, ey, tc, R)
        self.assertEqual(int((ins != (np.linalg.norm(co - c, axis=1) < R)).sum()), 0)
        P = co.copy()
        P[ins] = F.bowl_map(co[ins], c, a, ex, ey, R, tc)
        d = np.linalg.norm(P[ins] - c, axis=1)
        self.assertTrue(np.allclose(d, R))
        self.assertLess(float(((P[ins] - c) @ a).max()), 0.0104)  # behind the sheet's level, on the bowl
        band = F.rim_band(co, c, a, ex, ey, tc, 0.006, R)
        P2 = F.fillet(P, lap, band, c, R, 12)
        self.assertGreaterEqual(float(np.linalg.norm(P2 - c, axis=1).min()), R - 1e-9)
        self.assertEqual(len(F.folds(P2, tris, np.ones(len(tris), dtype=bool))), 0)

    def test_fold_found(self):
        F = self.F
        co = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0.2, 0.2, -0.0]], dtype=float)
        tris = np.array([[0, 1, 2], [1, 0, 3]])
        co[3] = (0.3, 0.3, 0.0)  # the second triangle folded back over the first
        self.assertEqual(len(F.folds(co, tris, np.ones(2, dtype=bool))), 1)

    def test_place_turns_straight_and_sinks(self):
        F = self.F
        s = F.set_fit({"sink": 0.01, "inward": 0.005, "toe": 1.0})
        fwd = np.array((0.138, -0.990, -0.016))
        fwd /= np.linalg.norm(fwd)
        c1, rz, f1 = F.place(np.array((0.076, -0.06, 1.55)), fwd, 1.0, s)
        self.assertAlmostEqual(float(f1[0]), 0.0, places=6)
        self.assertAlmostEqual(float(c1[0]), 0.076 - 0.005, places=6)
        self.assertGreater(float(c1[1]), -0.06 + 0.0099)
        with self.assertRaises(SystemExit):
            F.set_fit({"depth": 1})

    def test_slim_reach(self):
        """The socket is cut for the slim lids (alien_lids_geom.LIDS): bored's upper lid reaches 1.151 r."""
        F = self.F
        tree = ast.parse((BLENDER / "alien_parts.py").read_text(encoding="utf-8"))
        cons = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id in ("EYES", "LID_BEAD")}
        self.assertAlmostEqual(F.lid_reach(cons["EYES"], cons["LID_BEAD"], {"thin": 0.3, "rim": 0.7}), 1.151, places=3)

    def test_stage_uses_the_marker(self):
        """alien_m6.py reads alien_socket.MARKER as "sized and placed"; the fit writes the same key."""
        src = (BLENDER / "alien_socket_fit.py").read_text(encoding="utf-8")
        self.assertIn('MARKER = "prime_socket"', src)
        self.assertIn('MARKER = "prime_socket"', (BLENDER / "alien_socket.py").read_text(encoding="utf-8"))


SCRIPT = '''
import json, sys, unittest
a = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, a[0])
import test_alien_fit_geom as T
res = unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(T.FitGeom))
open(a[1], "w").write(json.dumps({"run": res.testsRun, "skipped": len(res.skipped),
                                  "bad": [str(x[0]) + ": " + x[1][-600:] for x in res.failures + res.errors]}))
'''


@unittest.skipIf(np is not None, "numpy is here: FitGeom runs directly")
class InBlender(unittest.TestCase):
    def test_checks_pass_in_blender(self):
        sys.path.insert(0, str(ROOT / "tools"))
        from runner import blender, common, pins
        path = common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)
        if not (path and path.is_file()):
            self.skipTest("needs Blender")
        with TemporaryDirectory() as tmp:
            script = Path(tmp) / "fit_check.py"
            script.write_text(SCRIPT, encoding="utf-8", newline="\n")
            blender.run_script(script, [str(Path(__file__).resolve().parent), str(Path(tmp) / "out.json")], timeout=300)
            res = json.loads((Path(tmp) / "out.json").read_text(encoding="utf-8"))
        self.assertEqual(res["bad"], [])
        self.assertEqual(res["skipped"], 0)
        self.assertGreaterEqual(res["run"], 6)


if __name__ == "__main__":
    unittest.main()
