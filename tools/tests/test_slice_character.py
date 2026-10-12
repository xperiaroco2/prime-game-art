"""The slice character's pure side (art #42 part C): the settings against the MVP set, the clip selection, each clip's
provenance, and the manifest it writes passing manifest-check's [[clips]] rules."""

from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from runner import common
from runner.commands import _manifest, _slice

ROOT = common.ROOT


def mvp() -> dict:
    with open(ROOT / "tools" / "blender" / "anim_sets" / "mvp.toml", "rb") as fh:
        return tomllib.load(fh)


SET = {"clips": [
    {"name": "Idle_Loop", "source": "ual:Idle_Loop", "loop": True, "needs": [{"need": "idle", "layer": "full"}]},
    {"name": "Turn_Left", "source": "tm:turn-left-90", "loop": False},
    {"name": "Turn_Right", "from": "Turn_Left", "loop": False},
    {"name": "Knife_Swing", "source": "pack:Sword_Slash", "loop": False, "needs": [{"need": "knife", "layer": "upper"}]},
    {"name": "Old_Loop", "source": "tm:old", "loop": True, "export": False},
    {"name": "Knockdown", "source": "ual:Death01", "loop": False},
]}
RECORDS = {
    "quaternius_ual1_standard": {"licence": "CC0-1.0", "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                                 "public_repo_ok": True, "ai_generated": False, "credit": "UAL by Quaternius"},
    "quaternius_ultimate_modular_men": {"licence": "CC0-1.0", "licence_url": "https://quaternius.com/",
                                        "public_repo_ok": True, "ai_generated": False},
}
BATCHES = {"2026-10-b5-anim-mvp": {"terms_url": "https://www.meshy.ai/terms-of-use", "plan": "Meshy Pro (monthly)"}}
TM = {"turn-left-90": "2026-10-b5-anim-mvp/turn-left-90/text_to_motion-clip.fbx"}
GEN = {"turn-left-90": {"tasks": {"text_to_motion": {"id": "task-1"}},
                        "files": [{"name": "text_to_motion-clip.fbx", "sha256": "a" * 64}]}}


class Selection(unittest.TestCase):
    def test_kept_in_set_order_and_every_other_clip_left_with_a_reason(self):
        kept, left = _slice.selection(SET, {"Knockdown": "the ragdoll"})
        self.assertEqual(kept, ["Idle_Loop", "Turn_Left", "Turn_Right", "Knife_Swing"])
        self.assertEqual([n for n, _ in left], ["Old_Loop", "Knockdown"])
        self.assertEqual(dict(left)["Knockdown"], "the ragdoll")
        self.assertIn("export = false", dict(left)["Old_Loop"])

    def test_root_source_follows_from(self):
        self.assertEqual(_slice.root_source(SET, "Turn_Right"), "tm:turn-left-90")
        self.assertEqual(_slice.root_source(SET, "Idle_Loop"), "ual:Idle_Loop")

    def test_tm_batch(self):
        self.assertEqual(_slice.tm_batch("2026-10-b5-anim-mvp\\x\\y.fbx"), "2026-10-b5-anim-mvp")

    def test_the_committed_settings_fit_the_mvp_set(self):
        settings, data = _slice.load_settings(), mvp()
        self.assertEqual(_slice.check_settings(settings, data), [])
        kept, left = _slice.selection(data, settings["exclude"])
        for need in ("Idle_Loop", "Jog_Fwd_Loop", "Sprint_Fwd_Loop", "Carry_Upper_Loop", "Pickup_Package",
                     "Putdown_Package"):
            self.assertIn(need, kept)
        for gone in ("Knockdown", "Crawl_Start", "Crawl_Loop", "Getup_Back", "Getup_Fours"):
            self.assertNotIn(gone, kept)
        self.assertEqual(len(kept) + len(left), len(data["clips"]))

    def test_check_settings_catches_unknown_clips(self):
        bad = {"cast": "m1", "recipe": "r", "set": "mvp", "exclude": {"Nope": "x", "Knockdown": ""},
               "review_clips": ["Knockdown"], "extra": 1}
        errors = _slice.check_settings(bad, SET)
        self.assertEqual(len(errors), 4, errors)


class Provenance(unittest.TestCase):
    def test_library_clips_carry_their_record(self):
        p = _slice.provenance("ual:Idle_Loop", "men", RECORDS, BATCHES, TM)
        self.assertEqual((p["record"], p["licence"], p["ai_generated"]), ("quaternius_ual1_standard", "CC0-1.0", False))
        p = _slice.provenance("pack:Sword_Slash", "men", RECORDS, BATCHES, TM)
        self.assertEqual(p["record"], "quaternius_ultimate_modular_men")

    def test_meshy_clips_carry_their_batch_and_task(self):
        p = _slice.provenance("tm:turn-left-90", "men", RECORDS, BATCHES, TM, GEN)
        self.assertEqual(p["record"], "batches/2026-10-b5-anim-mvp.toml")
        self.assertEqual((p["licence"], p["ai_generated"], p["public_repo_ok"]), ("owned-paid-output", True, True))
        self.assertEqual((p["task_id"], p["raw_sha256"]), ("task-1", "a" * 64))

    def test_unknown_sources_fail(self):
        with self.assertRaises(ValueError):
            _slice.provenance("mixamo:Walk", "men", RECORDS, BATCHES, TM)
        with self.assertRaises(ValueError):
            _slice.provenance("tm:nothing", "men", RECORDS, BATCHES, TM)

    def test_private_sources_stay_off(self):
        rows = [{"name": "A", "public_repo_ok": True, "record": "r"}, {"name": "B", "public_repo_ok": False, "record": "s"}]
        ok, off = _slice.split_public(rows)
        self.assertEqual([r["name"] for r in ok], ["A"])
        self.assertEqual(off[0][0], "B")


class Manifest(unittest.TestCase):
    def rows(self):
        kept, _ = _slice.selection(SET, {"Knockdown": "x"})
        return _slice.clip_rows(SET, kept, "men", RECORDS, BATCHES, TM, GEN, {"Idle_Loop": 1.0})

    def test_rows(self):
        rows = self.rows()
        self.assertEqual(rows[0]["godot_name"], "Idle")
        self.assertEqual(rows[0]["seconds"], 1.0)
        self.assertEqual(rows[2]["from"], "Turn_Left")
        self.assertEqual(rows[3]["layer"], "upper")
        self.assertIn("`Idle` | `Idle_Loop` | LINEAR", _slice.clip_table(rows))

    def test_the_manifest_passes_manifest_check(self):
        text = _slice.manifest_toml("slice_m1", "m1", "clay_cast_e", self.rows(), [("a/b.glb", "b" * 64)],
                                    ["blender 5.2.2"], "2026-10-12", [("Knockdown", "x")])
        data = tomllib.loads(text)
        sources = {k: {"licence": v["licence"], "public_repo_ok": v["public_repo_ok"]} for k, v in RECORDS.items()}
        self.assertEqual(_manifest.validate(data, "character", "slice_m1", sources), [])
        self.assertTrue(data["ai_generated"])
        self.assertEqual(data["source"]["task_ids"], ["task-1"])

    def test_clip_rules(self):
        text = _slice.manifest_toml("slice_m1", "m1", "r", self.rows(), [("a/b.glb", "b" * 64)], ["blender"],
                                    "2026-10-12", [])
        data = tomllib.loads(text)
        data["ai_generated"] = False
        data["clips"][0]["public_repo_ok"] = False
        data["clips"].append(dict(data["clips"][0]))
        del data["clips"][1]["task_id"]
        data["clips"][2]["record"] = "nowhere"
        errors = "\n".join(_manifest.validate(data, "character", "slice_m1", {}))
        for part in ("but the clip is not", "makes the asset ai_generated", "listed twice", "needs its task_id",
                     "no source record"):
            self.assertIn(part, errors)
        data = tomllib.loads(text)
        data["kind"] = "prop"
        self.assertTrue(any("carries no clips" in e for e in _manifest.validate(data)))

    def test_package_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "x.glb"
            f.write_bytes(b"abc")
            pkg = _slice.package_json("slice_m1", {"x.glb": f}, _slice.game_dir("slice_m1"))
        self.assertEqual(pkg["game_dir"], "assets/characters/slice_m1")
        self.assertEqual(pkg["files"][0]["bytes"], 3)
        self.assertEqual(pkg["files"][0]["sha256"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_body_credit_leads(self):
        body = "Ultimate Modular Men Pack by Quaternius (CC0 1.0)"
        text = _slice.manifest_toml("slice_m1", "m1", "r", self.rows(), [], ["blender"], "2026-10-12", [], (body,))
        credit = tomllib.loads(text)["credit"]
        self.assertTrue(credit.startswith(body + "; "))
        self.assertEqual(credit.count(body), 1)

    def test_source_credit(self):
        self.assertEqual(_slice.source_credit({"credit": "X by Y"}), "X by Y")
        self.assertEqual(_slice.source_credit({"title": "Pack", "author": "Q", "licence": "CC0-1.0"}),
                         "Pack by Q (CC0-1.0)")
        for gender, record in _slice.PACK_RECORDS.items():
            with open(common.ROOT / "sources" / f"{record}.toml", "rb") as fh:
                self.assertIn("Quaternius", _slice.source_credit(tomllib.load(fh)), gender)


if __name__ == "__main__":
    unittest.main()
