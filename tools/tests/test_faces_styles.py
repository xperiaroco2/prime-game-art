"""The face kit's data without Blender (tools/blender/faces_styles.py): the shipped styles and review files load, and
every kind of mistake is reported, all at once, naming what is allowed."""

from __future__ import annotations

import copy
import json
import unittest

from runner import common
from runner.commands import faces

fst = faces.styles_module()
STYLES = common.ROOT / "faces" / "styles.json"
REVIEW = common.ROOT / "faces" / "review.json"


def shipped() -> dict:
    return json.loads(STYLES.read_text(encoding="utf-8"))


def problems(data: dict) -> list[str]:
    with self_raises() as ctx:
        fst.check_styles(data)
    return ctx.problems


class self_raises:
    """Captures the StylesError a block raises (and fails when it raises nothing)."""

    problems: list[str]

    def __enter__(self) -> "self_raises":
        return self

    def __exit__(self, kind, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        if exc is None:
            raise AssertionError("expected a StylesError")
        if not isinstance(exc, fst.StylesError):
            return False
        self.problems = exc.problems
        return True


class ShippedStylesTest(unittest.TestCase):
    def test_at_least_six_families_each_with_every_expression(self) -> None:
        styles = fst.load_styles(STYLES)
        self.assertGreaterEqual(len(styles["families"]), 6)
        for name in fst.REQUIRED_EXPRESSIONS:
            self.assertIn(name, styles["expressions"])
        for fid, fam in styles["families"].items():
            self.assertEqual(list(fam["expressions"]), styles["expressions"], fid)
            self.assertTrue(fam["name"] and fam["summary"], fid)

    def test_families_cover_simple_to_near_human_and_flat(self) -> None:
        kinds = {fam["eyes"]["kind"] for fam in fst.load_styles(STYLES)["families"].values()}
        self.assertTrue({"dot", "ball", "toon", "almond", "painted"} <= kinds, kinds)

    def test_a_family_override_merges_into_the_shared_expression(self) -> None:
        styles = fst.load_styles(STYLES)
        happy = styles["families"]["f2_googly"]["expressions"]["happy"]
        self.assertEqual(happy["mouth"]["gap"], 0.008)  # the family's open smile
        self.assertEqual(happy["eyes"], shipped()["expressions"]["happy"]["eyes"])  # the shared rest stays
        self.assertNotIn("gap", styles["families"]["f3_almond"]["expressions"]["happy"]["mouth"])

    def test_the_closed_expression_closes_the_eyes(self) -> None:
        for fid, fam in fst.load_styles(STYLES)["families"].items():
            self.assertEqual(fam["expressions"]["closed"]["eyes"]["open"], 0.0, fid)

    def test_lip_colour_follows_the_skin(self) -> None:
        self.assertEqual(fst.lip_rgb([0.8, 0.5, 0.4], [0.5, 0.5, 1.0]), [0.4, 0.25, 0.4])


class StyleProblemsTest(unittest.TestCase):
    def test_every_problem_is_reported_at_once(self) -> None:
        data = shipped()
        fam = data["families"]["f3_almond"]
        fam["eyes"]["kind"] = "laser"
        del fam["eyes"]["top"]
        fam["brows"]["w"] = fam["brows"]["w"][:2]
        fam["mouth"]["lips"] = "rim"
        fam["colors"]["white"] = [1.5, 0, 0]
        fam["expressions"] = {"sleepy": {}, "happy": {"eyes": {"wink": 1}}}
        found = "\n".join(problems(data))
        self.assertIn("eyes.kind: 'laser' is not one of dot, ball, toon, almond, painted", found)
        self.assertIn("an almond shape needs top", found)
        self.assertIn("pts has 4 points but w 2 half-widths", found)
        self.assertIn("lips rim needs rim", found)
        self.assertIn("colors.white: must be [r, g, b] from 0 to 1", found)
        self.assertIn("'sleepy' is not a shared expression", found)
        self.assertIn("unknown key 'wink'", found)

    def test_lengths_are_metres(self) -> None:
        data = shipped()
        data["families"]["f1_dots"]["eyes"]["w"] = 6.2  # millimetres by mistake
        self.assertIn("families.f1_dots.eyes.w: 6.2 is not a length in metres from 0 to 0.1", problems(data))

    def test_missing_expression_and_bad_family_id(self) -> None:
        data = shipped()
        del data["expressions"]["closed"]
        data["families"]["Almond"] = copy.deepcopy(data["families"]["f3_almond"])
        found = "\n".join(problems(data))
        self.assertIn("expressions: missing 'closed'", found)
        self.assertIn("families.Almond: an id is f<number>_<name>", found)

    def test_sided_keys_and_dome_eyes(self) -> None:
        data = shipped()
        data["expressions"]["suspicious"]["eyes"]["open_x"] = 1
        del data["families"]["f2_googly"]["eyes"]["depth"]
        data["families"]["f6_painted"]["eyes"]["shape"] = "ellipse"
        found = "\n".join(problems(data))
        self.assertIn("unknown key 'open_x'", found)
        self.assertIn("a ball eye needs depth", found)
        self.assertIn("kind painted needs shape almond", found)

    def test_brow_points_run_outward(self) -> None:
        data = shipped()
        data["families"]["f1_dots"]["brows"]["pts"].reverse()
        self.assertIn("families.f1_dots.brows.pts: x must grow from the inner end to the outer end", problems(data))


class ReviewTest(unittest.TestCase):
    def test_the_shipped_review_loads(self) -> None:
        styles = fst.load_styles(STYLES)
        review = fst.load_review(REVIEW, styles)
        self.assertEqual(set(review["heads"]), {"m_full", "m_open", "w_full", "w_open"})
        self.assertEqual(review["distances_m"], [2, 5, 10])
        self.assertEqual(review["game_camera"]["fov_deg"], 75.0)

    def test_pixels_at_the_game_distances(self) -> None:
        cam = {"fov_deg": 75.0, "height": 1080}
        self.assertAlmostEqual(fst.pixels_per_metre(cam, 2.0), 351.87, places=1)
        self.assertAlmostEqual(fst.pixels_per_metre(cam, 10.0), 70.37, places=1)

    def test_review_problems(self) -> None:
        styles = fst.load_styles(STYLES)
        data = json.loads(REVIEW.read_text(encoding="utf-8"))
        data["overview_skins"]["x_head"] = "green"
        data["strip"]["rows"].append(["m_full", "light", "f9_none"])
        data["game_camera"]["fov_deg"] = 0
        with self_raises() as ctx:
            fst.check_review(data, styles)
        found = "\n".join(ctx.problems)
        self.assertIn("overview_skins: unknown head 'x_head'", found)
        self.assertIn("overview_skins.x_head: unknown skin 'green'", found)
        self.assertIn("is not [head, skin, family]", found)
        self.assertIn("game_camera.fov_deg: must be a positive number", found)
