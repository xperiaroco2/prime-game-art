"""The faces command without Blender: refusals before Blender starts, the checks of a finished report and its summary."""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

from runner import cli, common
from runner.commands import faces

RAW = common.raw_dir()
HAVE_PACKS = (RAW / "refs" / "Ultimate_Modular_Men_Pack").is_dir() and (RAW / "refs" / "Ultimate_Modular_Women_Pack").is_dir()


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), \
            mock.patch("runner.blender.run_script", side_effect=AssertionError("Blender must not start")):
        code = cli.main(list(argv))
    return code, out.getvalue()


def part(**kw: object) -> dict:
    info = {"triangles": 100, "materials": 2, "decal": True, "clearance_min_mm": 0.8, "under_skin": 0, "samples": 50,
            "vertex_groups": ["Head"], "armature": "m_full_rig"}
    info.update(kw)
    return info


def report(**eyes: object) -> dict:
    return {"families": {"f9_test": {"name": "Test", "expressions": {"neutral": {"m_full": {
        "eyes": part(decal=False, clearance_min_mm=-8.0, triangles=300, materials=5, **eyes),
        "brows": part(triangles=128, materials=1), "mouth": part(triangles=92)}}}}},
        "strip": {"m_full_f9_test": {"action": "Walk", "frames": [0, 4], "face_in_head_space_max_move_mm": 0.0}},
        "renders": 3}


@unittest.skipUnless(HAVE_PACKS, f"needs the Ultimate Modular packs in {RAW.as_posix()}/refs")
class RefusalsTest(unittest.TestCase):
    """Each refusal happens before Blender starts."""

    def test_check_reads_every_input(self) -> None:
        code, out = run_cli("faces", "--check")
        self.assertEqual(code, 0, out)
        self.assertIn("styles.json: 7 families, 9 expressions; review_heads.json: m_full, m_open, w_full, w_open", out)

    def test_unknown_names_list_the_known_ones(self) -> None:
        code, out = run_cli("faces", "--families", "f3_almond,f9_none", "--check")
        self.assertEqual(code, 1)
        self.assertIn("unknown families f9_none; known: f1_dots", out)
        code, out = run_cli("faces", "--expressions", "wink")
        self.assertEqual(code, 1)
        self.assertIn("unknown expressions wink; known: neutral, happy", out)
        code, out = run_cli("faces", "--sheets", "close,poster")
        self.assertEqual(code, 1)
        self.assertIn("unknown sheets poster; known: close, distance, overview, strip", out)

    def test_res_bounds(self) -> None:
        code, out = run_cli("faces", "--res", "200")
        self.assertEqual(code, 1)
        self.assertIn("--res must be from 5 to 100", out)

    def test_a_broken_styles_file_fails_with_its_problems(self) -> None:
        tmp = common.OUT / "tests" / "faces_command"
        tmp.mkdir(parents=True, exist_ok=True)
        bad = tmp / "styles.json"
        bad.write_text('{"expressions": {}, "families": {}}', encoding="utf-8")
        code, out = run_cli("faces", "--styles", str(bad), "--check")
        self.assertEqual(code, 1)
        self.assertIn("expressions: missing 'neutral'", out)
        self.assertIn("families: must be an object of style families", out)


class ReportChecksTest(unittest.TestCase):
    def test_a_good_report_passes(self) -> None:
        self.assertEqual(faces.check_report(report()), [])

    def test_dome_eyes_may_sink_into_the_skin_but_decals_may_not(self) -> None:
        bad = report()
        bad["families"]["f9_test"]["expressions"]["neutral"]["m_full"]["mouth"]["clearance_min_mm"] = 0.05
        self.assertEqual(faces.check_report(bad), ["f9_test/neutral/m_full/mouth: a decal 0.05 mm off the skin (at least 0.2 mm)"])

    def test_parts_must_be_rigid_on_the_head_bone(self) -> None:
        bad = report(vertex_groups=["Head", "Neck"], armature=None)
        bad["strip"]["m_full_f9_test"]["face_in_head_space_max_move_mm"] = 1.5
        found = "\n".join(faces.check_report(bad))
        self.assertIn("vertex groups ['Head', 'Neck'], want only Head", found)
        self.assertIn("no Armature modifier", found)
        self.assertIn("the face moved 1.5 mm in the Head bone's space", found)

    def test_summary_line(self) -> None:
        self.assertEqual(faces.summary(report()),
                         ["f9_test (Test): triangles eyes 300, brows 128, mouth 92; materials 5/1/2; decals at least 0.8 mm off the skin"])


class DistanceLinesTest(unittest.TestCase):
    def test_face_blink_and_talk_pixels_per_distance(self) -> None:
        fp = {"m_full_neutral_2m": 190, "m_full_neutral_10m": 5, "m_full_blink_change_2m": 120, "m_full_blink_change_10m": 0,
              "m_full_talk_change_2m": 40, "m_full_talk_change_10m": 2}
        self.assertEqual(faces.distance_lines({"distance": {"face_pixels": {"f9_test": fp}}}),
                         ["f9_test: m_full face 190/5, blink 120/0, talk 40/2 px at 2m/10m"])
