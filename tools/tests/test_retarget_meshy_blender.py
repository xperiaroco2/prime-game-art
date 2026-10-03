"""Meshy's clips in background Blender (art #25): the library loader (extra files, renames, skips, in-place clips),
Meshy's own rig as a review character (bones renamed to ours, flat colours) and a Meshy clip retargeted onto a pack
donor with the toe bones (skipped without Blender, the packs or batch 4's raw files)."""

from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runner import blender, common, pins
from runner.commands import _anim

RAW = common.raw_dir()
CFG = tomllib.loads(_anim.CONFIG.read_text(encoding="utf-8"))
MESHY = CFG.get("libraries", {}).get("meshy", {})
HAVE = (bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
        and (RAW / CFG["bodies"]["men"]["character"]).is_file()
        and bool(MESHY) and all((RAW / f).is_file() for f in [MESHY["file"], *MESHY["extra"]]))


@unittest.skipUnless(HAVE, "needs Blender, the Ultimate Modular packs and batch 4's Meshy files in the raw folder")
class MeshyLibraryTest(unittest.TestCase):
    def test_the_library_its_own_rig_and_a_retargeted_clip(self) -> None:
        with TemporaryDirectory() as tmp:
            script = Path(tmp) / "meshy_check.py"
            out = Path(tmp) / "meshy.json"
            script.write_text(SCRIPT.format(blender=str(common.ROOT / "tools" / "blender").replace("\\", "/"),
                                            raw=str(RAW).replace("\\", "/"),
                                            donor=str(RAW / CFG["bodies"]["men"]["character"]).replace("\\", "/"),
                                            config=str(_anim.CONFIG).replace("\\", "/"),
                                            out=str(out).replace("\\", "/")), encoding="utf-8")
            blender.run_script(script, [], timeout=900)
            res = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn("Walking", res["clips"])  # the rig's walk from an extra file, renamed
        self.assertIn("Crawl_Prompt", res["clips"])  # the text-to-motion crawl
        self.assertIn("RunFast", res["clips"])
        self.assertNotIn("clip0", res["clips"])
        self.assertGreater(res["backward_travel_raw_m"], 0.9)  # Walk_Backward walks about a metre ...
        self.assertLess(res["backward_travel_in_place_m"], 0.01)  # ... and stays put in place
        self.assertTrue(res["own_bones_renamed"])
        self.assertGreaterEqual(res["own_colours"], 5)
        self.assertLess(res["rest"]["max_offset_mm"], 0.01)
        self.assertLess(res["rest"]["max_rotation_deg"], 0.01)
        self.assertGreater(res["rest"]["aligned_deg"]["UpperArm.L"], 5.0)
        self.assertGreater(res["toe_turn_deg"], 5.0)  # Meshy's toes drive our toe bones
        self.assertGreater(res["lowest_cm"], -3.0)


SCRIPT = '''
import json, math, sys, tomllib
sys.path.insert(0, "{blender}")
import bpy
import numpy as np
import anim_libs
import retarget_core as rc
import retarget_map
from anim_metrics import world_points

cfg = tomllib.load(open("{config}", "rb"))
ent = anim_libs.entry(cfg, "meshy")
bmap = retarget_map.load(retarget_map.MAPS / ent["map"])
rc.new_scene()
lib = anim_libs.load("{raw}/" + ent["file"], ent, "{raw}", bmap["hips"][0])
rig = rc.Rig(lib["arm"])

def travel(s):
    p0 = rig.W @ rc.fk(rig, s.basis(s.start))["Hips"].translation
    p1 = rig.W @ rc.fk(rig, s.basis(s.end))["Hips"].translation
    return math.hypot(p1.x - p0.x, p1.y - p0.y)

back = lib["actions"]["Walk_Backward"]
res = {{"clips": sorted(lib["actions"]), "backward_travel_raw_m": travel(rc.Sampler(back)),
       "backward_travel_in_place_m": travel(lib["samplers"]["Walk_Backward"])}}
rc.new_scene()
own = anim_libs.own_character("{raw}/" + ent["file"], ent, "{raw}", bmap)
names = set(own["arm"].data.bones.keys())
res["own_bones_renamed"] = {{"Body", "Foot.L", "Toe.R", "Wrist.L"}} <= names and "LeftFoot" not in names
res["own_colours"] = max(len(o.data.materials) for o in own["meshes"].values())
rc.new_scene()
donor = rc.load_glb("{donor}")
rc.add_toes(donor)
src = anim_libs.load("{raw}/" + ent["file"], ent, "{raw}", bmap["hips"][0])
rt = rc.Retargeter(rc.Rig(src["arm"]), rc.Rig(donor["arm"]), bmap)
rt.set_soles(donor["meshes"].values())
res["rest"] = rt.rest_error()
act, n = rt.clip(src["actions"]["Walking"], "Meshy|Walking", donor["arm"], src["samplers"]["Walking"])
s = rc.Sampler(act)
turn, low = 0.0, 1e9
for i in range(n + 1):
    basis = s.basis(s.start + i)
    q = rc.rot(basis["Toe.L"])
    turn = max(turn, math.degrees(q.angle) if q.angle < math.pi else 360 - math.degrees(q.angle))
    rc.apply_basis(donor["arm"], basis)
    bpy.context.view_layer.update()
    low = min(low, min(float(world_points(o)[:, 2].min()) for o in donor["meshes"].values()))
res["toe_turn_deg"], res["lowest_cm"] = turn, low * 100
json.dump(res, open("{out}", "w"))
'''


if __name__ == "__main__":
    unittest.main()
