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
from unittest import mock
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
        cls.ORIG = {n: getattr(cls.B, n) for n in ("RIM_CUT_MAX_TO_EYE_PCT", "RIM_CUT_FIT_MAX_TO_EYE_PCT")}  # before setUp's patch

    def setUp(self):
        """E1: the area bounds each way are set from the heads' cuts (5.0 % to the lid, 1.5 % to the eyeball); the
        sheets' sawtooth is deeper than a head's (teeth up to 3 mm on a 20 mm opening) and trades about 5.2 % and 6.7 %
        each way, so the sheets are cut under 10 % bounds; the guard's own test sets them under the sheets' values."""
        for name in ("RIM_CUT_MAX_TO_LID_PCT", "RIM_CUT_MAX_TO_EYE_PCT", "RIM_CUT_FIT_MAX_TO_EYE_PCT"):  # E2: the last a --rim-fit candidate's
            patch = mock.patch.object(self.B, name, 10.0)
            patch.start()
            self.addCleanup(patch.stop)

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

    # ---- E1: R2b's review follow-ups, the guards of rim_cut, lip_smooth and rim_split
    def cut(self, seed: int = 3):
        """The sheets cut at order 4 with a lid to smooth: the lid's normals and heights jittered (seeded), a skin
        (JOINTS_0, WEIGHTS_0) on every vertex, so a copy's attributes can be told from its neighbours'."""
        A, I, eyeball, centres = sheets()
        rng = np.random.default_rng(seed)
        n = len(A["POSITION"])
        lid_only = np.ones(n, bool)
        lid_only[I[eyeball].ravel()] = False
        A["POSITION"][lid_only, 2] += rng.uniform(-3e-4, 3e-4, int(lid_only.sum()))
        Nj = A["NORMAL"] + rng.normal(0, 0.15, (n, 3)) * [1, 1, 0]
        A["NORMAL"] = Nj / np.linalg.norm(Nj, axis=1)[:, None]
        A["JOINTS_0"] = rng.integers(0, 6, (n, 4)).astype(float)
        W = rng.uniform(0, 1, (n, 4))
        A["WEIGHTS_0"] = W / W.sum(1)[:, None]
        A1, I1, cls1, _band1, rep = self.B.rim_cut(A, I, eyeball, centres, R_EYE, 4)
        return A1, I1, cls1, centres, rep

    def test_rim_cut_reports_the_area_each_way(self):
        _A1, _I1, _cls1, _c, rep = self.cut()
        for key in ("left", "right"):
            v = rep["eyeball_area"][key]
            self.assertGreater(v["to_lid_pct"], 0.0)  # the sawtooth's teeth go to the lid
            self.assertGreater(v["to_eye_pct"], 0.0)  # and its gaps to the eyeball
            self.assertAlmostEqual(v["change_pct"], v["to_eye_pct"] - v["to_lid_pct"], delta=0.01)  # the pieces tile
            self.assertLess(v["to_lid_pct"], self.B.RIM_CUT_MAX_TO_LID_PCT)
            self.assertLess(v["to_eye_pct"], self.B.RIM_CUT_MAX_TO_EYE_PCT)
            self.assertIn("lean_mm", rep[key]["trim_bias"])

    def test_rim_cut_area_guard_raises_each_way(self):
        """A cut over a bound fails the build: the sheets' cut against bounds set just under its own areas."""
        rep = self.cut()[4]
        worst_lid = max(v["to_lid_pct"] for v in rep["eyeball_area"].values())
        worst_eye = max(v["to_eye_pct"] for v in rep["eyeball_area"].values())
        worst_net = max(abs(v["change_pct"]) for v in rep["eyeball_area"].values())
        for name, value, field in (("RIM_CUT_MAX_TO_LID_PCT", worst_lid, "to_lid"),
                                   ("RIM_CUT_MAX_TO_EYE_PCT", worst_eye, "to_eye"),
                                   ("RIM_CUT_MAX_AREA_PCT", worst_net, "net change")):
            with self.subTest(name), mock.patch.object(self.B, name, value * 0.9):
                with self.assertRaises(SystemExit) as e:
                    self.cut()
                self.assertIn(field, str(e.exception))  # E2: the field that failed, not only "bound"
        area = {"left": {"change_pct": 0.5, "to_lid_pct": 0.2, "to_eye_pct": 0.7}}
        self.assertEqual(self.B.area_faults(area), [])
        area["left"]["to_lid_pct"] = self.B.RIM_CUT_MAX_TO_LID_PCT + 0.01
        self.assertEqual(len(self.B.area_faults(area)), 1)

    def test_lip_smooth_keeps_the_rim_and_the_eyeball(self):
        A1, I1, cls1, centres, _rep = self.cut()
        eb = np.zeros(len(A1["POSITION"]), bool)
        eb[I1[cls1].ravel()] = True  # the eyeball's vertices, the rim's among them
        for mode, steps in (("normals", 4), ("taubin", 4)):
            with self.subTest(mode):
                A2, rep = self.B.lip_smooth({k: v.copy() for k, v in A1.items()}, I1, cls1, centres, R_EYE, steps, mode)
                self.assertGreater(rep["vertices"], 0)
                self.assertTrue(np.array_equal(A2["POSITION"][eb], A1["POSITION"][eb]))
                self.assertTrue(np.array_equal(A2["NORMAL"][eb], A1["NORMAL"][eb]))
                move = np.linalg.norm(A2["POSITION"] - A1["POSITION"], axis=1)
                self.assertLessEqual(move.max(), self.B.LIP_CAP * R_EYE * (1 + 1e-9))
                if mode == "normals":
                    self.assertEqual(move.max(), 0.0)  # the normals alone: no position moves
                    self.assertGreater(np.abs(A2["NORMAL"] - A1["NORMAL"]).max(), 1e-3)  # but the lip's normals do
                else:
                    self.assertGreater(move.max(), 0.0)
                self.assertGreaterEqual(rep["min_face_dot"], self.B.LIP_FLIP_DOT)

    def test_lip_smooth_fails_a_turned_triangle(self):
        """The fold check: a lip triangle turned past LIP_FLIP_DOT fails. The sheets' lip turns its triangles a few
        degrees at most (face dot near 1), so a bound over that dot stands for a turned one."""
        A1, I1, cls1, centres, _rep = self.cut()
        for mode in ("normals", "taubin"):
            with self.subTest(mode), mock.patch.object(self.B, "LIP_FLIP_DOT", 1.5):
                with self.assertRaises(SystemExit) as e:
                    self.B.lip_smooth({k: v.copy() for k, v in A1.items()}, I1, cls1, centres, R_EYE, 4, mode)
                self.assertIn("turned", str(e.exception))

    def test_lip_smooth_fails_a_triangle_really_turned(self):
        """E2: a lip triangle that really turns under the real LIP_FLIP_DOT fails. Taubin mode with LIP_CAP patched
        large and one lid position one ring off the rim spiked: moved just past the far edge of one of its triangles
        (1e-6 of the radius), so the steps pull it back across that edge and even the fold guard's smallest move
        (1/64) turns the triangle over. (A spike far out of the sheet does not do it: its triangles leave the eye's
        reach and every position on them is held.) The same patch without the spike passes (the control)."""
        A1, I1, cls1, centres, _rep = self.cut()
        P = A1["POSITION"]
        eb = np.zeros(len(P), bool)
        eb[I1[cls1].ravel()] = True
        lid_t = ~cls1 & eb[I1].any(1)  # the lid triangles on the rim
        cand = [int(v) for v in I1[lid_t].ravel() if not eb[v]]
        self.assertTrue(cand)
        spiked = np.all(np.isclose(P, P[cand[0]]), axis=1)  # every copy of that position (lip_smooth welds them)
        with mock.patch.object(self.B, "LIP_CAP", 1e6):
            _A, ok = self.B.lip_smooth({k: v.copy() for k, v in A1.items()}, I1, cls1, centres, R_EYE, 4, "taubin")
            self.assertGreaterEqual(ok["min_face_dot"], self.B.LIP_FLIP_DOT)
            A2 = {k: v.copy() for k, v in A1.items()}
            v = cand[0]
            tri = next(t for t in I1[~cls1] if v in t)
            a, b = (P[x] for x in tri if x != v)
            m = (a + b) / 2
            A2["POSITION"][spiked] = m + (m - P[v]) / np.linalg.norm(m - P[v]) * 1e-6 * R_EYE
            with self.assertRaises(SystemExit) as e:
                self.B.lip_smooth(A2, I1, cls1, centres, R_EYE, 4, "taubin")
        self.assertIn("turned", str(e.exception))
        self.assertLess(float(str(e.exception).split("face dot ")[1].rstrip(")")), self.B.LIP_FLIP_DOT)

    def test_rim_cut_fit_all_keeps_every_rim_position(self):
        """E2 candidate B (--rim-fit, off by default): "all" fits through every rim position and names its fit in the
        report; the default trimmed cut's report has no "fit". Like with like (F3): the same sheets at the same order,
        only the fit changed. The sheets have no spur, so the trimmed fit is made to drop the outermost 5 % of each
        eye's rim positions (they lie outside its curve): "all" and "outer" must keep them, and "trimmed" must not."""
        A, I, eyeball, centres = sheets()
        G, real = self.B.G, self.B.G.fourier_fit_trimmed

        def drop_outer(phi, val, order, *args, **kw):
            _coef, kept = real(phi, val, order, *args, **kw)
            edge = sorted(val)[-max(1, len(val) // 20)]
            kept = [bool(w) and v < edge for w, v in zip(kept, val)]
            return G.fourier_fit([p for p, w in zip(phi, kept) if w], [v for v, w in zip(val, kept) if w], order), kept
        patch = mock.patch.object(G, "fourier_fit_trimmed", drop_outer)
        patch.start()
        self.addCleanup(patch.stop)
        cut = {fit: self.B.rim_cut({k: v.copy() for k, v in A.items()}, I, eyeball, centres, R_EYE, 8, fit)[4]
               for fit in ("trimmed", "all", "outer")}
        trimmed = cut["trimmed"]
        self.assertNotIn("fit", trimmed)
        self.assertGreater(sum(trimmed[k]["trimmed"] for k in ("left", "right")), 0)  # the trim bites
        for fit in ("all", "outer"):
            with self.subTest(fit):
                rep = cut[fit]
                self.assertEqual(rep["fit"], fit)
                for key in ("left", "right"):
                    self.assertEqual(rep[key]["rim_positions"], trimmed[key]["rim_positions"])  # the same rim
                    self.assertGreaterEqual(rep[key]["fit_kept"], trimmed[key]["fit_kept"])
                    if fit == "all":
                        self.assertEqual(rep[key]["fit_kept"], rep[key]["rim_positions"])
                        self.assertEqual(rep[key]["trimmed"], 0)
                self.assertEqual(rep["bad_triangles"], 0)
                self.assertEqual(rep["edges_after"], rep["edges_before"])
        for fit in ("all", "outer"):
            self.assertGreater(sum(cut[fit][k]["fit_kept"] for k in ("left", "right")),
                               sum(trimmed[k]["fit_kept"] for k in ("left", "right")), fit)

    def test_each_path_takes_its_own_bounds(self):
        """E2: the default (trimmed) path keeps the approved build's bounds, a --rim-fit candidate takes its own: the
        constants pinned, rim_cut's to-eye bound per fit, rim_split's past-90 bound (None: the default's), and the
        build's main passing the candidate's past-90 bound only under a --rim-fit candidate."""
        O = self.ORIG
        self.assertEqual((O["RIM_CUT_MAX_TO_EYE_PCT"], O["RIM_CUT_FIT_MAX_TO_EYE_PCT"]), (1.5, 4.0))
        self.assertEqual((self.B.RIM_SPLIT_MAX_PAST90_PCT, self.B.RIM_SPLIT_FIT_MAX_PAST90_PCT), (6.5, 10.0))
        A, I, eyeball, centres = sheets()
        with mock.patch.object(self.B, "RIM_CUT_MAX_TO_EYE_PCT", 9.0),                 mock.patch.object(self.B, "RIM_CUT_FIT_MAX_TO_EYE_PCT", 9.5):  # both over the sheets' 6.7 %, told apart
            for fit, want in (("trimmed", 9.0), ("all", 9.5), ("outer", 9.5)):
                with self.subTest(fit):
                    rep = self.B.rim_cut({k: v.copy() for k, v in A.items()}, I, eyeball, centres, R_EYE, 8, fit)[4]
                    self.assertEqual(rep["eyeball_area_bounds_pct"]["to_eye"], want)
        *_rest, rep = self.split(flip=5)
        self.assertEqual(rep["past_90_bound_pct"], self.B.RIM_SPLIT_MAX_PAST90_PCT)
        A1, I1, cls1, centres, _rep = self.cut()
        views = {"left": (None, None, centres[1], R_EYE), "right": (None, None, centres[-1], R_EYE)}
        rep = self.B.rim_split({k: v.copy() for k, v in A1.items()}, I1, cls1, views, False,
                               self.B.RIM_SPLIT_FIT_MAX_PAST90_PCT)[2]
        self.assertEqual(rep["past_90_bound_pct"], 10.0)
        src = (BLENDER / "alien_lively_build.py").read_text(encoding="utf-8")
        self.assertIn('None if args.rim_fit == "trimmed" else RIM_SPLIT_FIT_MAX_PAST90_PCT', src)  # main's wiring
        self.assertIn("rim_cut(A, I, eyeball, centres, r, args.rim_cut, args.rim_fit)", src)

    def split(self, flip: int = 0, sphere_only: bool = False, stray: int = 0):
        """rim_split on the cut sheets, each eye's sphere the eye centre 1 cm behind with radius R_EYE (eyeball_fix's
        views: only the centre and radius are read); flip: that many eyeball-only vertices per eye given a normal
        facing away (-z) before the split, so their radial normal turns past 90 degrees."""
        A1, I1, cls1, centres, _rep = self.cut()
        views = {"left": (None, None, centres[1], R_EYE), "right": (None, None, centres[-1], R_EYE)}
        lid = np.zeros(len(A1["POSITION"]), bool)
        lid[I1[~cls1].ravel()] = True
        if flip:
            for s in (1, -1):
                d = np.linalg.norm(A1["POSITION"] - centres[s] * [1, 1, 0], axis=1)
                pick = np.nonzero(~lid & (d < RHO / 2))[0][:flip]
                A1["NORMAL"][pick] = [0.0, 0.0, -1.0]
        self._stray = []
        if stray:  # E2: that many eyeball-only vertices per eye moved 3 radii below their sphere's centre (a stray)
            for s in (1, -1):
                d = np.linalg.norm(A1["POSITION"] - centres[s] * [1, 1, 0], axis=1)
                pick = np.nonzero(~lid & (d < RHO / 2))[0][-stray:]
                A1["POSITION"][pick] = centres[s] + [0.0, -3.0 * R_EYE, 0.0]
                self._stray += [int(x) for x in pick]
        A2, I2, rep = self.B.rim_split({k: v.copy() for k, v in A1.items()}, I1, cls1, views, sphere_only)
        return A1, I1, cls1, centres, A2, I2, rep

    def test_rim_split_sphere_only_leaves_the_strays(self):
        """E2 candidate A (--rim-split-sphere-only, off by default): an eyeball vertex over RIM_SPLIT_SPHERE_BAND radii
        from its sphere's centre keeps its own normal; the default gives it the radial one and has no "sphere_only"."""
        A1, _I1, _c, _centres, A2, _I2, rep = self.split(stray=2, sphere_only=True)
        pick = self._stray  # eyeball-only vertices: rim_split copies none of them, so their indices stay
        self.assertEqual(len(pick), 4)
        self.assertTrue(np.array_equal(A2["NORMAL"][pick], A1["NORMAL"][pick]))  # their own normals
        self.assertEqual(sum(v["vertices"] for v in rep["sphere_only"]["kept_own"].values()), 4)
        self.assertEqual(rep["sphere_only"]["band_r"], self.B.RIM_SPLIT_SPHERE_BAND)
        A0, rep0 = (lambda r: (r[4], r[6]))(self.split(stray=2))
        self.assertNotIn("sphere_only", rep0)
        self.assertLess(np.abs(A0["NORMAL"][pick] - [0.0, -1.0, 0.0]).max(), 1e-9)  # the default: the radial normal

    def test_rim_split_opens_no_edge_and_gives_the_eyeball_its_sphere(self):
        A1, I1, cls1, centres, A2, I2, rep = self.split()
        n = len(A1["POSITION"])
        eb, lid = np.zeros(n, bool), np.zeros(n, bool)
        eb[I1[cls1].ravel()] = True
        lid[I1[~cls1].ravel()] = True
        shared = np.nonzero(eb & lid)[0]
        self.assertEqual(rep["copied"], len(shared))
        self.assertGreater(len(shared), 0)
        for k in ("POSITION", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"):  # every copy equals its source
            self.assertTrue(np.array_equal(A2[k][n:], A1[k][shared]), k)
            self.assertTrue(np.array_equal(A2[k][:n], A1[k]), k)
        self.assertTrue(np.array_equal(A2["TANGENT"][n:, 3], A1["TANGENT"][shared, 3]))
        self.assertTrue(np.array_equal(A2["POSITION"][I2], A1["POSITION"][I1]))  # every corner where it was
        self.assertEqual(self.B.edge_faults(A2["POSITION"], I2), self.B.edge_faults(A1["POSITION"], I1))
        self.assertTrue(np.array_equal(I2[~cls1], I1[~cls1]))
        self.assertFalse(np.isin(I2[cls1], shared).any())  # the eyeball's triangles use the copies
        own = np.unique(I2[cls1].ravel())
        P = A2["POSITION"][own]
        c = np.where((P[:, 0] > 0)[:, None], centres[1], centres[-1])
        rad = (P - c) / np.linalg.norm(P - c, axis=1)[:, None]
        self.assertTrue(np.allclose(A2["NORMAL"][own], rad, atol=1e-12))  # the sphere's radial normal in full
        lid_v = np.unique(I2[~cls1].ravel())
        self.assertTrue(np.array_equal(A2["NORMAL"][lid_v], A1["NORMAL"][lid_v]))  # the lid keeps its own
        T = A2["TANGENT"][own]
        self.assertLess(np.abs((T[:, :3] * A2["NORMAL"][own]).sum(1)).max(), 1e-9)
        for key in ("left", "right"):
            self.assertEqual(rep["eyes"][key]["past_90"], 0)

    def test_rim_split_counts_and_bounds_normals_past_90(self):
        *_rest, rep = self.split(flip=5)
        for key in ("left", "right"):
            e = rep["eyes"][key]
            self.assertEqual(e["past_90"], 5)
            self.assertAlmostEqual(e["past_90_pct"], 100 * 5 / e["vertices"], places=2)
            self.assertGreater(e["past_90_off_lid_r"]["p50"], 0.0)  # inside the eye, off the lid line
        worst = max(v["past_90_pct"] for v in rep["eyes"].values())
        self.assertLess(worst, self.B.RIM_SPLIT_MAX_PAST90_PCT)  # 5 of a few hundred: under the bound
        with mock.patch.object(self.B, "RIM_SPLIT_MAX_PAST90_PCT", worst * 0.9):
            with self.assertRaises(SystemExit) as e:
                self.split(flip=5)
            self.assertIn("past 90", str(e.exception))


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
            blender.run_script(script, [str(Path(__file__).resolve().parent), str(Path(tmp) / "out.json")], timeout=900)
            res = json.loads((Path(tmp) / "out.json").read_text(encoding="utf-8"))
        self.assertEqual(res["bad"], [])
        self.assertEqual(res["skipped"], 0)
        self.assertEqual(res["run"], 13)


if __name__ == "__main__":
    unittest.main()
