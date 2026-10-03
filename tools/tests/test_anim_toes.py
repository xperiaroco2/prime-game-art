"""The toe bones in the animation review (art #25): the settings, the runner's feet step and the toe bones on a donor
in background Blender (skipped without Blender or the packs)."""

from __future__ import annotations

import json
import shutil
import tomllib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runner import blender, common, pins
from runner.commands import _anim
from runner.commands import anim_review as review


class SettingsTest(unittest.TestCase):
    def write(self, tmp: str, extra: str) -> Path:
        path = Path(tmp) / "anim_review.toml"
        path.write_text(_anim.CONFIG.read_text(encoding="utf-8") + extra, encoding="utf-8")
        return path

    def test_the_settings_give_the_donors_toes_and_a_feet_row(self) -> None:
        cfg = _anim.load_config()
        self.assertTrue(cfg["toe_bones"])
        self.assertEqual(cfg["feet"][0]["clips"], ["ual:Walk_Loop", "ual:Jog_Fwd_Loop", "ual:Sprint_Loop"])
        self.assertIn("feet", review.STEPS)

    def test_a_library_may_name_its_bone_maps(self) -> None:
        with TemporaryDirectory() as tmp:
            ok = self.write(tmp, '\n[libraries.other]\nfile = "a.glb"\nrm = "a.glb"\nmap = "ual_um.toml"\n'
                                 'rigid_map = "ual_um_rigid.toml"\n')
            self.assertEqual(_anim.load_config(ok)["libraries"]["other"]["map"], "ual_um.toml")
            bad = self.write(tmp, '\n[libraries.other]\nfile = "a.glb"\nrm = "a.glb"\nmap = "nope.toml"\n')
            with self.assertRaises(common.Failure) as ctx:
                _anim.load_config(bad)
            self.assertIn("nope.toml", str(ctx.exception))


RAW = common.raw_dir()
CFG = tomllib.loads(_anim.CONFIG.read_text(encoding="utf-8"))
HAVE = (bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
        and (RAW / CFG["bodies"]["men"]["character"]).is_file())


@unittest.skipUnless(HAVE, "needs Blender and the Ultimate Modular packs in the raw folder")
class DonorToesTest(unittest.TestCase):
    def test_a_donor_gets_toes_and_its_pack_clips_play_as_before(self) -> None:
        with TemporaryDirectory() as tmp:
            script = Path(tmp) / "toes_check.py"
            out = Path(tmp) / "toes.json"
            script.write_text(SCRIPT.format(blender=str(common.ROOT / "tools" / "blender").replace("\\", "/"),
                                            glb=str(RAW / CFG["bodies"]["men"]["character"]).replace("\\", "/"),
                                            out=str(out).replace("\\", "/")), encoding="utf-8")
            blender.run_script(script, [], timeout=600)
            res = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual((res["before"], res["after"]), (62, 64))
        self.assertEqual(res["parents"], ["Foot.L", "Foot.R"])
        self.assertLess(res["walk_moved_mm"], 0.01)  # the pack's Walk deforms every vertex exactly as before
        self.assertGreater(res["toe_weighted"], 50)  # the front of the left shoe (96 vertices on Business Man)


SCRIPT = '''
import json, sys
sys.path.insert(0, "{blender}")
import bpy
import numpy as np
import retarget_core as rc
from anim_metrics import world_points

rc.new_scene()
char = rc.load_glb("{glb}")
before = len(char["arm"].data.bones)

def posed():
    rc.apply_basis(char["arm"], rc.Sampler(char["actions"]["Walk"]).basis(8))
    bpy.context.view_layer.update()
    return np.concatenate([world_points(o) for o in char["meshes"].values()])

a = posed()
rc.add_toes(char)
b = posed()
shoes = [o for n, o in char["meshes"].items() if n.endswith("_Feet")][0]
g = shoes.vertex_groups["Toe.L"].index
weighted = sum(1 for v in shoes.data.vertices for x in v.groups if x.group == g and x.weight > 0.5)
bones = char["arm"].data.bones
json.dump({{"before": before, "after": len(bones), "parents": [bones["Toe.L"].parent.name, bones["Toe.R"].parent.name],
           "walk_moved_mm": float(np.abs(a - b).max() * 1000), "toe_weighted": weighted}}, open("{out}", "w"))
'''


if __name__ == "__main__":
    unittest.main()
