"""The clay face kit's data and pure-Python rules (tools/blender/um/clayface/kit.py, faces/clay_kit.json,
faces/clay_hair.json): the tables' shapes, the per-hair flags against the parts catalogue, the picks' rules, and the
port's parity with the faces lab's kit while the lab file is the one the port was made from (docs/faces.md, "The clay
face kit")."""

from __future__ import annotations

import hashlib
import json
import random
import unittest
from unittest import mock
from pathlib import Path

from runner.commands import _assembly

_assembly.recipe_module()  # puts tools/blender on the path
from um.clayface import kit as K  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RAW = Path("D:/prime-art-raw")


def lab_data(path):
    """The lab kit's data section (its constants and pure helpers, up to the build context) run without Blender."""
    lines = path.read_text(encoding="utf-8").split("\n")
    a = next(i for i, ln in enumerate(lines) if ln.startswith("X = Vector"))
    b = next(i for i, ln in enumerate(lines) if ln.startswith("class Ctx"))
    ns = {"Vector": tuple}
    exec(compile("\n".join(lines[a:b]), str(path), "exec"), ns)
    return ns


class Tables(unittest.TestCase):
    def test_shapes(self):
        self.assertEqual(K.KIT["schema"], "prime-game-art/faces/clay-kit/1")
        self.assertIsInstance(K.SKINS["light"], tuple)
        self.assertIsInstance(K.NOSES["bulb"]["half"], tuple)
        self.assertIsInstance(K.LOUD["eye_size"], set)
        self.assertEqual(K.WEIGHTS["teeth"], {True: 1.0})
        self.assertEqual(K.STATES, ("rest", "closed", "a", "e", "o"))
        for m, spec in K.MOUTHS.items():
            self.assertEqual(set(spec["states"]), set(K.STATES), m)
            for t in spec["teeth"] or []:
                self.assertIsInstance(t["u"], tuple)
        for cat, table in K.WEIGHTS.items():
            self.assertEqual(set(table), set(K.PICKS[cat]), cat)
        self.assertEqual(K.FACIAL_HAIR["none"], [])

    def test_decisions(self):
        """The engineer's decisions (#34 comment 6076693443): the ball on every default face, the long nose at 0.8,
        the nose never loud."""
        self.assertEqual(K.DEFAULTS["M"]["nose"], "bulb")
        self.assertEqual(K.DEFAULTS["W"]["nose"], "bulb")
        self.assertEqual(K.NOSE_SCALE["long"], 0.8)
        self.assertNotIn("nose", K.LOUD)
        self.assertEqual(K.MOUSTACHE_VARIANT, "a")


class HairFlags(unittest.TestCase):
    def test_items_match_catalogue(self):
        cat = json.loads((ROOT / "catalogue" / "ultimate_modular.json").read_text(encoding="utf-8"))["items"]
        for iid, v in K.HAIR_ITEMS.items():
            self.assertIn(iid, cat, iid)
            r = cat[iid]["recipe"]
            self.assertEqual((v["file"], v["object"], sorted(v["materials"])),
                             (r["file"], r["object"], sorted(r["materials"])), iid)
            self.assertEqual(K.hair_item({"file": r["file"], "object": r["object"], "materials": r["materials"]},
                                         v["body_type"]), iid)

    def test_flags(self):
        self.assertEqual(K.hair_flags("hair_m_beach")["ears"], "hide")
        self.assertEqual(K.hair_flags("hair_w_formal_updo")["ears"], "tuck")
        self.assertEqual(K.hair_flags("hair_m_farmer_buzz")["ears"], "free")
        # measured on the repo's head (faces --kit-check, art #42 part B): the hair over the tucked or free ear
        self.assertEqual(K.hair_flags("hair_m_hoodie")["ears"], "tuck")
        self.assertEqual(K.hair_flags("hair_m_casual")["ears"], "hide")
        self.assertEqual(K.hair_flags("hair_m_king_long")["ears"], "hide")
        for iid, v in K.HAIR_ITEMS.items():
            if "lab_ears_free" in v:
                self.assertNotEqual(v["lab_ears_free"], v["ears_free"], iid)
        self.assertEqual(K.hair_flags("hair_m_farmer_buzz", "headwear_m_swat_helmet")["ears"], "hide")
        self.assertEqual(K.hair_flags(None, "no_such_item"), {"ears": "free", "brow_tuck": True})
        self.assertTrue(K.hair_flags("hair_w_witch")["brow_tuck"])
        self.assertEqual(K.hair_item({"item": "hair_w_witch"}), "hair_w_witch")
        self.assertIsNone(K.hair_item({"file": "x.glb", "object": "y", "materials": ["Hair"]}))
        self.assertEqual(K.COVERS_EARS, {i for i in K.EAR_RULES if K.covers_ears(i)})


class Picks(unittest.TestCase):
    def test_rules(self):
        for g in ("M", "W"):
            rng = random.Random(500 + ("M", "W").index(g))
            for _ in range(320):
                p = K.random_picks(rng, g)
                self.assertFalse(K.forbidden(p), p)
                self.assertIn(p[p["loud"]], K.LOUD[p["loud"]], p)
                if g == "W":
                    self.assertEqual(p["facial_hair"], "none")
                for cat in K.WEIGHTS:
                    self.assertIn(p[cat], K.PICKS[cat], (cat, p))


class RecipePicks(unittest.TestCase):
    def test_defaults_and_overrides(self):
        self.assertEqual(K.picks_for(None, "M"), K.default_picks("M"))
        p = K.picks_for({"mouth": "buck", "eye_size": "big"}, "W")
        self.assertEqual((p["mouth"], p["eye_size"], p["teeth"]), ("buck", "big", True))
        self.assertEqual(K.check_picks({"nose": "long", "brow_rgb": [0.1, 0.05, 0.02]}, "M"), [])

    def test_problems(self):
        probs = K.check_picks({"nose": "potato", "colour": 1, "brow_rgb": [2, 0, 0]}, "M", "c.face_kit")
        self.assertEqual(len(probs), 3, probs)
        self.assertTrue(any(p.startswith("c.face_kit.nose: 'potato'") for p in probs))
        beards = [k for k in K.PICKS["facial_hair"] if k != "none"]
        self.assertTrue(K.check_picks({"facial_hair": beards[0]}, "W"))  # no facial hair on the women's body
        self.assertEqual(K.check_picks({"facial_hair": beards[0]}, "M"), [])
        self.assertEqual(K.check_picks("big", "M"), ["face_kit: must be an object of picks (" + ", ".join(K.FACE_KIT_KEYS) + ")"])


class NosesTest(unittest.TestCase):
    def test_three_noses(self):
        # art #42 round 3: BALL (bulb), BEAN ("long" at 0.8, the lab's droop) and the new PINOCCHIO; the ball the most
        # common pick and every cast default
        self.assertEqual(set(K.NOSES), {"bulb", "long", "pinocchio"})
        self.assertEqual(set(K.PICKS["nose"]), {"bulb", "long", "pinocchio"})
        self.assertEqual(K.NOSE_SCALE["long"], 0.8)
        w = K.WEIGHTS["nose"]
        self.assertEqual(max(w, key=w.get), "bulb")
        self.assertTrue(all(w[n] > 0 for n in K.NOSES))

    def test_pinocchio_points_forward_and_down(self):
        P = K.NOSES["pinocchio"]
        self.assertGreater(P["half"][1] + P["capsule"], 1.5 * P["half"][0])  # long along the forward axis
        self.assertGreaterEqual(P["half"][1] + P["capsule"], 0.04)  # long like the old accidental nose (42b sheet2)
        self.assertGreater(P["tilt"], 0.0)  # the tip goes down
        self.assertLess(P["taper"][1], P["taper"][0])  # thinner toward the tip
        self.assertIn("pinocchio", K.STRICT_NOSES)  # it must clear the eyes and lids as well


def without_repo_noses():
    """The repo's tables without its own noses (REPO_NOSES, art #42 round 3's pinocchio), which the lab never had."""
    drop = lambda t: {k: v for k, v in t.items() if k not in REPO_NOSES}  # noqa: E731
    return {"NOSES": drop(K.NOSES), "NOSE_SCALE": drop(K.NOSE_SCALE),
            "WEIGHTS": {c: (drop(t) if c == "nose" else t) for c, t in K.WEIGHTS.items()},
            "PICKS": {c: ([n for n in v if n not in REPO_NOSES] if c == "nose" else v) for c, v in K.PICKS.items()}}


REPO_NOSES = {"pinocchio"}


class LabParity(unittest.TestCase):
    """The port against the lab file it was made from (faces/clay_kit.json lab_source): every table and the picks of
    the check's seeds. Skipped without the raw folder or once the lab file has moved on (re-sync then)."""

    def setUp(self):
        src = K.KIT["lab_source"]
        self.path = RAW / src["path"]
        if not self.path.is_file():
            self.skipTest("the faces lab is not on this machine")
        if hashlib.sha256(self.path.read_bytes()).hexdigest() != src["sha256"]:
            self.skipTest("the lab kit changed since the port: re-sync faces/clay_kit.json")
        self.lab = lab_data(self.path)

    def test_tables(self):
        names = ["SKINS", "TINT", "FIXED", "GLOSS", "BROW_RGB", "HAIR_RGB", "BROW_COLOURS", "EYE_SIZES", "LOUD_EYE_R",
                 "PUPILS", "LIDS", "LOOK", "BROWS", "NOSES", "NOSE_SCALE", "EARS", "MOUTHS", "STATES", "FACIAL_HAIR",
                 "ASYM", "WEIGHTS", "LOUD", "LOUD_WEIGHTS", "LOUD_SCALE", "DEFAULTS", "SMILING_AT_REST",
                 "VISIBLE_SMILE", "MASK_UV", "MASK", "PICKS", "EAR_RULES", "COVERS_EARS", "LAYOUT", "EYEBALL",
                 "NOSE_K", "MOUTH_K", "PROFILE", "EAR_TUCK", "EAR_HIDE", "BROW_PAD_CAP"]

        def norm(v):
            return json.loads(json.dumps(v, default=sorted, sort_keys=True).replace("true", "true"))

        # the repo's ear flags where its heads measure otherwise (lab_ears_free in faces/clay_hair.json) compare as the lab's
        lab_rules = {iid: tuple(v.get("lab_ears_free", v["ears_free"])) for iid, v in K.HAIR_ITEMS.items()}
        as_lab = {"EAR_RULES": lab_rules, "COVERS_EARS": {k for k, (f, b) in lab_rules.items() if not f and not b}}
        as_lab.update(without_repo_noses())
        for n in names:
            a, b = self.lab[n], as_lab.get(n, getattr(K, n))
            if n == "WEIGHTS":
                a = {c: {str(k): w for k, w in t.items()} for c, t in a.items()}
                b = {c: {str(k): w for k, w in t.items()} for c, t in b.items()}
            self.assertEqual(norm(a), norm(b), n)
        self.assertEqual(self.lab["RULES"]["forbid"], [tuple(f) for f in K.RULES["forbid"]])

    def test_picks(self):
        for g in ("M", "W"):
            ra, rb = random.Random(500 + ("M", "W").index(g)), random.Random(500 + ("M", "W").index(g))
            with mock.patch.dict(K.WEIGHTS, {"nose": without_repo_noses()["WEIGHTS"]["nose"]}):
                for _ in range(320):
                    self.assertEqual(self.lab["random_picks"](ra, g), K.random_picks(rb, g))


if __name__ == "__main__":
    unittest.main()


class P:
    """A world point for the pure zone rules (anything with x, y and z)."""

    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Accessories(unittest.TestCase):
    """art #42 round 3: the ear and nose accessories' zones and seat measure (kit.accessory_zone, accessory_seat_ok)."""

    EYE_Z, NOSE_BACK = 1.70, -0.17

    def zone(self, x, y, z):
        return K.accessory_zone(P(x, y, z), 0.0, self.EYE_Z, self.NOSE_BACK)

    def test_ear_pieces_by_side(self):
        self.assertEqual(self.zone(0.11, -0.06, 1.66), "ear_l")  # +X is the character's left
        self.assertEqual(self.zone(-0.11, -0.06, 1.66), "ear_r")
        self.assertIsNone(self.zone(0.03, -0.06, 1.66))  # too near the centre line for an ear
        self.assertIsNone(self.zone(0.11, -0.06, 1.55))  # below the ear band (a necklace)

    def test_nose_pieces(self):
        self.assertEqual(self.zone(0.01, -0.19, 1.65), "nose")
        self.assertIsNone(self.zone(0.04, -0.19, 1.65))  # off the centre line
        self.assertIsNone(self.zone(0.0, -0.10, 1.65))  # well behind the nose's back
        self.assertIsNone(self.zone(0.0, -0.19, 1.72))  # above the eye line (a brow piercing)

    def test_the_seat_measure(self):
        self.assertTrue(K.accessory_seat_ok(1.39, 0.2))  # m3's ring, round 3
        self.assertTrue(K.accessory_seat_ok(K.ACC_GAP_MAX_MM, 0.0))
        self.assertFalse(K.accessory_seat_ok(K.ACC_GAP_MAX_MM + 0.01, 0.0))  # floating
        self.assertFalse(K.accessory_seat_ok(0.0, K.ACC_INSIDE_MAX))  # buried

    def test_the_build_enforces_it(self):
        src = (ROOT / "tools/blender/um/clayface/accessories.py").read_text(encoding="utf-8")
        self.assertIn("accessory_seat_ok(gap, inside)", src)
        self.assertIn("raise SeatError", src)


class BrowMeasure(unittest.TestCase):
    """art #42 round 3: the brow measure's verdict (kit.brow_visible_ok): strict for every style but the angry V."""

    SEEN = {"L": 0.53, "R": 0.55}

    def test_w3_fixed_passes_and_sunk_fails(self):
        self.assertTrue(K.brow_visible_ok(self.SEEN, -2.46, "normal"))  # w3 under the formal updo, fixed
        self.assertFalse(K.brow_visible_ok(self.SEEN, -17.4, "normal"))  # w3 before the fix

    def test_only_the_angry_v_may_dip(self):
        self.assertTrue(K.brow_visible_ok(self.SEEN, -9.99, "angry"))  # the 320-face run's deepest angry brow
        self.assertTrue(K.brow_visible_ok(self.SEEN, -5.53, "one_raised"))  # its lowered side, 320-face run
        self.assertTrue(K.brow_visible_ok(self.SEEN, -4.01, "normal"))
        for style in K.BROWS:
            if style not in ("angry", "one_raised"):
                self.assertFalse(K.brow_visible_ok(self.SEEN, -6.0, style), style)
        self.assertFalse(K.brow_visible_ok(self.SEEN, -7.0, "one_raised"))
        self.assertFalse(K.brow_visible_ok(self.SEEN, -11.0, "angry"))
        self.assertFalse(K.brow_visible_ok(self.SEEN, -6.0, None))  # an unknown style gets the strict limit

    def test_hidden_brows_fail(self):
        self.assertFalse(K.brow_visible_ok({"L": 0.53, "R": K.BROW_SEEN_MIN - 0.01}, 0.0, "normal"))


class StrictNose(unittest.TestCase):
    def test_only_the_pinocchio_must_clear_eyes_and_lids(self):
        self.assertLessEqual({("nose", "eye"), ("nose", "lid")}, K.bad_pairs("pinocchio"))
        for nose in K.NOSES:
            if nose not in K.STRICT_NOSES:
                self.assertEqual(K.bad_pairs(nose), K.BAD_PAIRS, nose)
        self.assertLessEqual(K.BAD_PAIRS, K.bad_pairs("pinocchio"))
