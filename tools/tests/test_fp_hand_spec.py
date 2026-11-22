"""The detailed first-person hand's spec (art#136, prime-game#1587; specs/fp_hand_dims.toml, Gate 1 of
docs/decisions/2026-10-31-asset-pipeline-gates.md): the station tables line up, the sizes are positive and in their
order (the forearm toward the elbow, the palm widening to the knuckles, each finger's knuckle before its crotch before
its tip), the phalanx shares make the whole finger, the concept's scale is its own measure (the wrist row to the index's
tip at px_per_mm gives the hand's length), and the punch's fist in fp_hands.toml ([grips.fist]) is the spec's fist.
Pure Python, no Blender."""

from __future__ import annotations

import hashlib
import subprocess
import json
import tomllib
import unittest

from runner import common

SPEC = tomllib.loads((common.ROOT / "specs" / "fp_hand_dims.toml").read_text(encoding="utf-8"))
FP = tomllib.loads((common.ROOT / "tools" / "blender" / "fp_hands.toml").read_text(encoding="utf-8"))
DIGITS = ("index", "middle", "ring")
SEED = json.loads((common.ROOT / SPEC["hand"]["rig_seed"]).read_text(encoding="utf-8"))


class FpHandSpecTest(unittest.TestCase):
    def test_forearm_stations(self):
        fa = SPEC["forearm"]
        n = len(fa["u"])
        for key in ("width", "depth", "centre_v"):
            self.assertEqual(len(fa[key]), n, key)
        self.assertEqual(fa["u"], sorted(fa["u"]), "stations from the elbow side to the wrist")
        self.assertLessEqual(fa["u"][1], -SPEC["hand"]["forearm_len_mm"] + 1.0, "a station at the elbow")
        for w, d in zip(fa["width"], fa["depth"]):
            self.assertGreater(w, 0.0)
            self.assertGreater(d, 0.0)

    def test_palm_stations(self):
        pa = SPEC["palm"]
        n = len(pa["u"])
        for key in ("v_min", "v_max", "thickness"):
            self.assertEqual(len(pa[key]), n, key)
        for a, b in zip(pa["v_min"], pa["v_max"]):
            self.assertLess(a, 0.0)
            self.assertGreater(b, 0.0)
        widths = [b - a for a, b in zip(pa["v_min"], pa["v_max"])]
        self.assertGreater(widths[2], widths[0], "the palm widens from the wrist")

    def test_fingers(self):
        f = SPEC["fingers"]
        for name in DIGITS:
            d = f[name]
            self.assertLess(d["knuckle_u"], d["crotch_u"], name)
            self.assertLess(d["crotch_u"], d["tip_u"], name)
            self.assertAlmostEqual(sum(d["phalanx"]), 1.0, places=6, msg=name)
            self.assertLess(d["thickness"], d["width"], f"{name}: a soft sausage, flatter than wide")
        t = f["thumb"]
        self.assertLess(t["base_u"], t["apart_u"])
        self.assertLess(t["apart_u"], t["tip_u"])
        self.assertAlmostEqual(sum(t["phalanx"]), 1.0, places=6)
        self.assertGreater(f["index"]["centre_v"][0], f["middle"]["centre_v"][0])
        self.assertGreater(f["middle"]["centre_v"][0], f["ring"]["centre_v"][0])

    def test_four_digits(self):
        """The engineer, 2026-11-20: three fingers and a thumb (the final word); m40: the middle the longest, index
        and ring about equal (knuckle to tip), each finger narrower than m30's (47.5 / 45 / 39 mm) and its knuckle
        inside the palm's outline at the knuckle row, with palm between neighbouring knuckles."""
        f = SPEC["fingers"]
        self.assertNotIn("little", f)
        length = {n: f[n]["tip_u"] - f[n]["knuckle_u"] for n in DIGITS}
        self.assertEqual(max(length, key=length.get), "middle")
        self.assertLess(abs(length["index"] - length["ring"]), 0.05 * length["ring"])
        for n, m30 in (("index", 47.5), ("middle", 45.0), ("ring", 39.0)):
            self.assertLess(f[n]["width"], m30 - 3.0, n)
            self.assertAlmostEqual(f[n]["thickness"] / f[n]["width"], 0.88, delta=0.01)
        pa = SPEC["palm"]
        edges = []
        for n in DIGITS:
            v = f[n]["knuckle_v"]
            self.assertLessEqual(v + f[n]["width"] / 2, pa["v_max"][-1], n)
            self.assertGreaterEqual(v - f[n]["width"] / 2, pa["v_min"][-1], n)
            edges.append((v - f[n]["width"] / 2, v + f[n]["width"] / 2))
        for (lo, _), (_, hi) in zip(edges, edges[1:]):
            self.assertGreater(lo, hi, "neighbouring knuckles overlap")
        self.assertGreater(SPEC["fingers"]["thumb"]["waist_mm"], 0.0)

    def test_concept_scale(self):
        h = SPEC["hand"]
        top = max(SPEC["fingers"][n]["tip_u"] for n in DIGITS)   # the middle's since m40 (the index's until m30)
        tip_row = h["wrist_row"] + top * h["px_per_mm"]
        self.assertAlmostEqual(tip_row, 793.0, delta=6.0, msg="the longest tip's row in view 0")
        self.assertAlmostEqual(SPEC["fingers"]["middle"]["tip_u"], h["hand_len_mm"], delta=h["tol_mm"])

    def test_fist_in_the_clips(self):
        g = FP["grips"]["fist"]
        for name in DIGITS:
            self.assertEqual(list(g[name.capitalize()]), list(SPEC["fist"]["curl_deg"][name]), name)
        punch = [k for k in FP["clips"]["Punch"]["keys"] if k.get("fist")]
        self.assertTrue(punch)
        for k in punch:
            self.assertEqual(k.get("grip_R"), "fist", "the morph `fist` is the corrective of [grips.fist] alone")



class FpRigSeedTest(unittest.TestCase):
    """The rig seed (tools/blender/fp_rig_seed.json, art#136): the arm rig the detailed hand is built on, read from
    the committed hands asset once the character build was lost with D: (2026-11-18)."""

    def test_bones_the_build_needs(self):
        names = [b["name"] for b in SEED["bones"]]
        self.assertEqual(len(names), len(set(names)))
        need = {"View", "Crystal"}
        for side in ("Right", "Left"):
            need |= {side + n for n in ("Shoulder", "UpperArm", "LowerArm", "Hand")}
            for f in ("Index", "Middle", "Ring", "Little"):
                need |= {side + f + ph for ph in ("Proximal", "Intermediate", "Distal")}
            need |= {side + "Thumb" + ph for ph in ("Metacarpal", "Proximal", "Distal")}
        self.assertEqual(need - set(names), set())

    def test_parents_come_first(self):
        seen = set()
        for b in SEED["bones"]:
            if b["parent"] is not None:
                self.assertIn(b["parent"], seen, b["name"])
            seen.add(b["name"])

    def test_round_trip_and_source(self):
        self.assertLess(SEED["roundtrip"]["max_pos_m"], 1e-5)
        self.assertGreater(SEED["roundtrip"]["min_z_dot"], 0.99999)
        src = common.ROOT / SEED["source"]
        self.assertTrue(src.is_file(), SEED["source"])
        if src.read_bytes()[:7] != b"version" and hashlib.sha256(src.read_bytes()).hexdigest() == SEED["sha256"]:
            return   # the seed's own source is the file in the checkout
        # the asset was rebuilt since the seed was read (run n2, 2026-11-19): the seed's source is one of the file's
        # earlier versions, whose LFS pointer names its SHA-256
        git = ["git", "-C", str(common.ROOT)]
        try:
            revs = subprocess.run(git + ["log", "--format=%H", "--", SEED["source"]], capture_output=True, text=True,
                                  check=True).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("no git history")
        oids = set()
        for rev in revs:
            blob = subprocess.run(git + ["show", f"{rev}:{SEED['source']}"], capture_output=True).stdout
            if blob[:7] == b"version":
                oids |= {ln.split(b":", 1)[1].decode() for ln in blob.splitlines() if ln.startswith(b"oid sha256:")}
        self.assertIn(SEED["sha256"], oids, "the seed's source is no version of the file in git")

    def test_skin_and_crystal_inputs_are_in_git(self):
        self.assertEqual(len(SPEC["skin"]["base_srgb"]), 3)
        self.assertTrue(all(0.0 <= c <= 1.0 for c in SPEC["skin"]["base_srgb"]))
        self.assertTrue((common.ROOT / FP["source"]["crystal"]).is_file(), FP["source"]["crystal"])


if __name__ == "__main__":
    unittest.main()
