"""The face kit in headless Blender (skipped when Blender or the Ultimate Modular packs are missing): two families in
two expressions on the four review heads at low resolution, the frame strip and its clip. Checks the sheets exist,
every part is a mesh weighted to the Head bone alone, decals stay off the skin and the face is rigid on the head over
the walk. One Blender run, about 25 s."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import unittest

from runner import cli, common, pins
from runner.commands import _review

OUT = common.OUT / "tests" / "faces"
RAW = common.raw_dir()
HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
HAVE_PACKS = (RAW / "refs" / "Ultimate_Modular_Men_Pack").is_dir() and (RAW / "refs" / "Ultimate_Modular_Women_Pack").is_dir()
SKIP = f"needs Blender {pins.BLENDER} ({path}) and the Ultimate Modular packs in {RAW.as_posix()}/refs"
FAMILIES = ("f3_almond", "f6_painted")


@unittest.skipUnless(HAVE_BLENDER and HAVE_PACKS, SKIP)
class FacesInBlenderTest(unittest.TestCase):
    code: int
    out: str
    report: dict

    @classmethod
    def setUpClass(cls) -> None:
        shutil.rmtree(OUT, ignore_errors=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cls.code = cli.main(["faces", "--families", ",".join(FAMILIES), "--expressions", "neutral,closed",
                                 "--sheets", "close,strip", "--res", "10", "--out", str(OUT)])
        cls.out = buf.getvalue()
        report = OUT / "faces_report.json"
        cls.report = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}

    def test_the_run_passes_its_own_checks(self) -> None:
        self.assertEqual(self.code, 0, self.out)
        self.assertIn("f3_almond (Almond): triangles", self.out)

    def test_every_part_on_every_head(self) -> None:
        for fid in FAMILIES:
            for ename in ("neutral", "closed"):
                heads = self.report["families"][fid]["expressions"][ename]
                self.assertEqual(sorted(heads), ["m_full", "m_open", "w_full", "w_open"])
                for hid, parts in heads.items():
                    for name, info in parts.items():
                        self.assertEqual(info["vertex_groups"], ["Head"], f"{fid} {ename} {hid} {name}")
                        self.assertEqual(info["armature"], f"{hid}_rig")
                        self.assertGreater(info["triangles"], 0)

    def test_a_closed_eye_is_a_lid_not_a_missing_eye(self) -> None:
        almond = self.report["families"]["f3_almond"]["expressions"]
        for hid in ("m_full", "w_open"):
            closed = almond["closed"][hid]["eyes"]
            self.assertGreater(closed["triangles"], 50)  # the skin lid and its lash line
            self.assertLess(closed["triangles"], almond["neutral"][hid]["eyes"]["triangles"])

    def test_painted_eyes_are_decals_off_the_skin(self) -> None:
        for hid, parts in self.report["families"]["f6_painted"]["expressions"]["neutral"].items():
            self.assertTrue(parts["eyes"]["decal"])
            self.assertEqual(parts["eyes"]["under_skin"], 0, hid)
            self.assertGreaterEqual(parts["eyes"]["clearance_min_mm"], 0.2, hid)

    def test_the_face_follows_the_head(self) -> None:
        self.assertTrue(self.report["strip"])
        for key, strip in self.report["strip"].items():
            self.assertEqual(len(strip["frames"]), 8, key)
            self.assertLessEqual(strip["face_in_head_space_max_move_mm"], 0.01, key)
            self.assertTrue((OUT / strip["clip"]).is_file(), key)

    def test_the_sheets_exist(self) -> None:
        for fid in FAMILIES:
            for name in ("front", "threequarter", "hero"):
                self.assertTrue((OUT / f"{fid}_{name}.jpg").is_file(), f"{fid}_{name}")
        width, height = _review.png_size(OUT / "work" / "f3_almond_neutral_light_front.png")
        self.assertEqual(height, 38)  # 10 % of a 384 px cell
        self.assertGreater(width, 4 * 38)
