"""R2 (art #196): the eye rim cut's numpy parts in tools/blender/alien_lively_build.py: edge_faults on a closed and an
opened mesh, rim_cut on two eyeball discs in their lid sheets (a stepped, sawtooth boundary made smooth, no vertex
moved, no edge opened, the eye opening's area kept), and rim_mask repainting the mask on the cut. The build imports
bpy and numpy, which the runner's Python lacks: InBlender runs the checks in background Blender's Python (skips
without Blender)."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
BLENDER = ROOT / "tools" / "blender"

try:
    import numpy as np
    import bpy  # noqa: F401  the build module needs it
except ImportError:  # the runner is standard library only; numpy and bpy come with Blender
    np = None


def load(name: str):
    sys.path.insert(0, str(BLENDER))
    spec = importlib.util.spec_from_file_location(name, BLENDER / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R_EYE = 0.03  # the eye sphere's radius
RHO = 0.02  # the opening's radius on the sheet


def sheets(n: int = 31, half: float = 0.06, gap: float = 0.2):
    """Two flat sheets z = 0 facing +z, one per eye (centres x = +-gap/2, 1 cm behind), each n x n vertices, its own
    half of the UV square; the eyeball class a sawtooth disc: a triangle is eyeball when its centroid lies within RHO
    plus 3 mm (ten teeth round the eye, irregular in depth)."""
    P, UV, I = [], [], []
    for k, x0 in enumerate((gap / 2, -gap / 2)):
        xs = np.linspace(-half, half, n)
        X, Y = np.meshgrid(xs, xs, indexing="ij")
        base = len(P) and sum(len(p) for p in P)
        P.append(np.stack([X.ravel() + x0, Y.ravel(), np.zeros(n * n)], 1))
        UV.append(np.stack([(X.ravel() / half * 0.5 + 0.5) * 0.48 + 0.5 * k + 0.01, Y.ravel() / half * 0.48 + 0.5], 1))
        idx = np.arange(n * n).reshape(n, n) + base
        a, b, c, d = idx[:-1, :-1].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel(), idx[:-1, 1:].ravel()
        I.append(np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)]))
    P, UV, I = np.concatenate(P), np.concatenate(UV), np.concatenate(I)
    centres = {+1: np.array([gap / 2, 0.0, -0.01]), -1: np.array([-gap / 2, 0.0, -0.01])}
    cen = P[I].mean(1)
    side = np.where(cen[:, 0] > 0, 1, -1)
    q = cen - np.array([[centres[s][0], 0.0, 0.0] for s in side])
    phi = np.arctan2(q[:, 1], q[:, 0])
    tooth = 0.003 * np.where(np.sin(10 * phi) > 0, 1.0, 0.0) * (0.6 + 0.4 * np.cos(3 * phi) ** 2)
    eyeball = np.hypot(q[:, 0], q[:, 1]) < RHO + tooth
    A = {"POSITION": P, "NORMAL": np.tile([0.0, 0.0, 1.0], (len(P), 1)), "TEXCOORD_0": UV,
         "TANGENT": np.tile([1.0, 0.0, 0.0, 1.0], (len(P), 1))}
    return A, I, eyeball, centres


@unittest.skipIf(np is None, "numpy and bpy are not here (Blender ships them)")
class LivelyCut(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.B = load("alien_lively_build")

    def test_edge_faults_counts_open_and_non_manifold_edges(self):
        P = np.array([[0.0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])
        I = np.array([[0, 2, 1], [0, 1, 3], [1, 2, 3], [0, 3, 2]])
        self.assertEqual(self.B.edge_faults(P, I), {"open": 0, "non_manifold": 0})
        self.assertEqual(self.B.edge_faults(P, I[:3]), {"open": 3, "non_manifold": 0})
        fin = np.concatenate([I, [[0, 1, 2]]])  # a third triangle on the edges 0-1, 1-2 and 2-0
        self.assertEqual(self.B.edge_faults(P, fin), {"open": 0, "non_manifold": 3})

    def test_rim_cut_smooths_the_sawtooth_and_moves_nothing(self):
        A, I, eyeball, centres = sheets()
        A1, I1, cls1, band1, rep = self.B.rim_cut({k: v.copy() for k, v in A.items()}, I, eyeball, centres, R_EYE, 4)
        n = len(A["POSITION"])
        self.assertTrue(np.array_equal(A1["POSITION"][:n], A["POSITION"]))  # no vertex moved
        self.assertGreater(rep["new_vertices"], 0)
        self.assertEqual(rep["bad_triangles"], 0)
        self.assertEqual(rep["edges_after"], rep["edges_before"])
        self.assertEqual(rep["zigzag_after"]["junctions"], 0)
        self.assertLess(rep["zigzag_after"]["p50_mm"], rep["zigzag_before"]["p50_mm"] * 0.5)
        for key in ("left", "right"):
            self.assertLess(abs(rep["eyeball_area"][key]["change_pct"]), self.B.RIM_CUT_MAX_AREA_PCT)
        # the new rim: its radial spread about each eye under half the stepped rim's and under the teeth's 3 mm. Not
        # tighter: a sliver's cut is snapped through a grid corner (RIM_CUT_MIN_SHARE), up to about a third of a 4 mm
        # grid edge off the curve, so the nodes spread about 2 mm round a curve that is itself near a circle
        def spread(P_, I_, cls_):
            weld, nodes, _nbr = self.B.rim_graph(P_, I_, cls_, np.ones(len(I_), bool))
            Q = np.zeros((int(weld.max()) + 1, 3))
            Q[weld] = P_
            out = {}
            for s, c in centres.items():
                q = Q[nodes][np.sign(Q[nodes][:, 0]) == s] - c
                rad = np.hypot(q[:, 0], q[:, 1])
                out[s] = float(rad.max() - rad.min())
            return out
        before, after = spread(A["POSITION"], I, eyeball), spread(A1["POSITION"], I1, cls1)
        for s in centres:
            self.assertLess(after[s], 0.5 * before[s])
            self.assertLess(after[s], 0.003)
        tn = A1["NORMAL"][n:]
        self.assertTrue(np.allclose(np.linalg.norm(tn, axis=1), 1.0))
        self.assertTrue(np.array_equal(band1, np.arange(len(I1) - len(band1), len(I1))))  # the pieces come last

    def test_rim_mask_follows_the_cut(self):
        A, I, eyeball, centres = sheets()
        A1, I1, cls1, band1, _rep = self.B.rim_cut({k: v.copy() for k, v in A.items()}, I, eyeball, centres, R_EYE, 4)
        H = W = 256
        mask = np.ones((H, W, 3))
        gy, gx = np.mgrid[0:H, 0:W]
        u, v = (gx + 0.5) / W, (gy + 0.5) / H
        k = (u > 0.5).astype(int)  # the texel's sheet (0: the left eye)
        x = ((u - 0.5 * k - 0.01) / 0.48 - 0.5) * 2 * 0.06
        y = (v - 0.5) / 0.48 * 0.06
        mask[np.hypot(x, y) < RHO + 0.0015] = 0.0  # the old mask's eye: a disc a little bigger than the cut's
        out, rep = self.B.rim_mask(mask, A1["TEXCOORD_0"], I1, cls1, band1)
        self.assertGreater(rep["to_eye"] + rep["to_skin"], 0)
        uvc = A1["TEXCOORD_0"][I1[band1]].mean(1)
        px = np.clip((uvc * [W, H]).astype(int), 0, [W - 1, H - 1])
        eye_now = out[px[:, 1], px[:, 0], 0] < 0.5
        self.assertTrue(np.array_equal(eye_now, cls1[band1]))  # every band triangle's middle texel says its class


SCRIPT = '''
import json, sys, unittest
a = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, a[0])
import test_alien_lively_cut as T
res = unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(T.LivelyCut))
open(a[1], "w").write(json.dumps({"run": res.testsRun, "skipped": len(res.skipped),
                                  "bad": [str(x[0]) + ": " + x[1][-800:] for x in res.failures + res.errors]}))
'''


@unittest.skipIf(np is not None, "numpy is here: LivelyCut runs directly")
class InBlender(unittest.TestCase):
    def test_checks_pass_in_blender(self):
        sys.path.insert(0, str(ROOT / "tools"))
        from runner import blender, common, pins
        path = common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)
        if not (path and path.is_file()):
            self.skipTest("needs Blender")
        with TemporaryDirectory() as tmp:
            script = Path(tmp) / "cut_check.py"
            script.write_text(SCRIPT, encoding="utf-8", newline="\n")
            blender.run_script(script, [str(Path(__file__).resolve().parent), str(Path(tmp) / "out.json")], timeout=300)
            res = json.loads((Path(tmp) / "out.json").read_text(encoding="utf-8"))
        self.assertEqual(res["bad"], [])
        self.assertEqual(res["skipped"], 0)
        self.assertEqual(res["run"], 3)


if __name__ == "__main__":
    unittest.main()
