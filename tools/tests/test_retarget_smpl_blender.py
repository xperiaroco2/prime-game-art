"""Meshy text to motion through the retarget in background Blender (art #33): the SMPL-H loader's floor shift (the rest
stands on the floor and a clip's world poses stay the file's own), the rest check on both body types without any
aligned bone, the crawl's length, and the turn on the men: no vertex 1 cm under the floor, the legs on the source's
ankle path while the feet are down (the pivot foot exact; the stepping leg stands nearly straight, a median of 5.2 mm
short and at most 16.4 mm where its heel starts to rise and our leg locks, as at UAL's push-offs), and SMPL-H's
constant relaxed hand on our fingers. Skipped without Blender, the packs or the text-to-motion files of batches 4 and
5 in the raw folder."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runner import blender, common, pins
from runner.commands import _anim

RAW = common.raw_dir()
CFG = _anim.load_config()
TM = CFG.get("libraries", {}).get("tm", {})
CLIPS = ("crawl", "turn-left-90")
HAVE = (bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
        and all((RAW / b["character"]).is_file() for b in CFG["bodies"].values())
        and bool(TM) and all((RAW / TM["clips"][c]).is_file() for c in CLIPS))


def posix(p: Path) -> str:
    return str(p).replace("\\", "/")


@unittest.skipUnless(HAVE, "needs Blender, the Ultimate Modular packs and the text-to-motion FBX files (raw folder)")
class TextToMotionRetargetTest(unittest.TestCase):
    res: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        with TemporaryDirectory() as tmp:
            script, out = Path(tmp) / "tm_check.py", Path(tmp) / "tm.json"
            script.write_text(SCRIPT.format(blender=posix(common.ROOT / "tools" / "blender"), raw=posix(RAW),
                                            config=posix(_anim.CONFIG), out=posix(out),
                                            men=posix(RAW / CFG["bodies"]["men"]["character"]),
                                            women=posix(RAW / CFG["bodies"]["women"]["character"])),
                              encoding="utf-8")
            blender.run_script(script, [], timeout=900)
            cls.res = json.loads(out.read_text(encoding="utf-8"))

    def test_the_floor_shift(self) -> None:
        self.assertAlmostEqual(self.res["floor_shift_m"], 1.161, delta=0.002)  # the mannequin's soles at rest
        self.assertLess(abs(self.res["rest_lowest_m"]), 0.001)  # the lifted rest stands on the floor
        # the motion keeps the file's own world poses: the turn's lowest vertex at frame 45, against a plain import
        self.assertLess(abs(self.res["turn45_lowest_m"] - self.res["turn45_plain_lowest_m"]), 0.0001)
        self.assertLess(abs(self.res["turn45_lowest_m"]), 0.01)  # standing: on the floor

    def test_the_rest_check_on_both_bodies(self) -> None:
        for body, scale in (("men", 1.096), ("women", 1.178)):
            with self.subTest(body=body):
                rest = self.res[body]["rest"]
                self.assertLess(rest["max_offset_mm"], 0.01)
                self.assertLess(rest["max_rotation_deg"], 0.01)
                self.assertNotIn("aligned_deg", rest)  # no [align]
                self.assertAlmostEqual(self.res[body]["ratio"], scale, delta=0.002)
                self.assertEqual(self.res[body]["crawl_frames"], 119)  # 3.967 s at 30 fps

    def test_the_turn_on_the_men(self) -> None:
        turn = self.res["men"]["turn"]
        self.assertEqual(turn["frames"], 89)
        self.assertGreater(turn["lowest_cm"], -1.0)
        for side in ("L", "R"):
            self.assertGreater(turn["contact_frames"][side], 10)
            self.assertLess(turn["contact_median_mm"][side], 8.0)
            self.assertLess(turn["contact_miss_mm"][side], 20.0)

    def test_the_relaxed_hand(self) -> None:
        turn = self.res["men"]["turn"]
        self.assertLess(turn["finger_change_deg"], 0.01)  # the fingers never move in a text-to-motion clip
        self.assertAlmostEqual(turn["finger_curl_deg"], 31.0, delta=8.0)  # SMPL-H's mean relaxed hand


SCRIPT = '''
import json, math, sys, tomllib
sys.path.insert(0, "{blender}")
import bpy
import anim_libs
import anim_math
import retarget_core as rc
import retarget_map
import retarget_smpl

cfg = tomllib.load(open("{config}", "rb"))
ent = anim_libs.entry(cfg, "tm")
clips = ("crawl", "turn-left-90")
ent = dict(ent, clips={{c: ent["clips"][c] for c in clips}}, in_place=[c for c in ent["in_place"] if c in clips])
bmap = retarget_map.load(retarget_map.MAPS / ent["map"])
rc.new_scene()
src = anim_libs.load("{raw}/" + ent["file"], ent, "{raw}", bmap["hips"][0])
res = {{"floor_shift_m": src["floor_shift_m"], "rest_lowest_m": retarget_smpl.lowest(src["meshes"].values())}}
turn = src["samplers"]["turn-left-90"]
rc.apply_basis(src["arm"], turn.basis(45.0))
res["turn45_lowest_m"] = retarget_smpl.lowest(src["meshes"].values())
rc.reset_pose(src["arm"])
objs = set(bpy.data.objects)
plain = retarget_smpl.import_fbx("{raw}/" + ent["clips"]["turn-left-90"], shift=False)
rc.apply_basis(plain["arm"], rc.Sampler(plain["action"]).basis(45.0))
res["turn45_plain_lowest_m"] = retarget_smpl.lowest(plain["meshes"].values())
for o in set(bpy.data.objects) - objs:
    bpy.data.objects.remove(o, do_unlink=True)
srig = rc.Rig(src["arm"])
FINGERS = [f"{{f}}{{k}}.{{s}}" for f in ("Index", "Middle", "Ring", "Pinky") for k in (2, 3, 4) for s in "LR"]


def angle(q):
    a = math.degrees(q.angle)
    return min(a, 360 - a)


for body, donor in (("men", "{men}"), ("women", "{women}")):
    objs = set(bpy.data.objects)
    tgt = rc.load_glb(donor)
    rc.add_toes(tgt)
    rt = rc.Retargeter(srig, rc.Rig(tgt["arm"]), bmap)
    rt.set_soles(tgt["meshes"].values())
    out = res[body] = {{"rest": rt.rest_error(), "ratio": rt.ratio}}
    _, out["crawl_frames"] = rt.clip(src["actions"]["crawl"], "TTM|crawl", tgt["arm"], src["samplers"]["crawl"])
    if body == "men":
        act, n = rt.clip(src["actions"]["turn-left-90"], "TTM|turn", tgt["arm"], turn)
        t = rc.Sampler(act)
        ankle = {{"L": "L_Ankle", "R": "R_Ankle"}}
        frames = []
        for i in range(n + 1):
            sp = rc.fk(srig, turn.basis(turn.start + i))
            basis = t.basis(t.start + i)
            tp = rc.fk(rt.tgt, basis)
            rc.apply_basis(tgt["arm"], basis)
            bpy.context.view_layer.update()
            row = {{"low": retarget_smpl.lowest(tgt["meshes"].values()), "fingers": {{b: rc.rot(basis[b]) for b in FINGERS}}}}
            for s in "LR":
                sw = srig.W @ sp[ankle[s]]
                goal = rt.to_tgt(sw @ rt.foot_anchor["Foot." + s])
                row[s] = (sw.translation.z, (rt.tgt.W @ tp["Foot." + s].translation - goal).length * 1000)
            frames.append(row)
        rc.reset_pose(tgt["arm"])
        info = out["turn"] = {{"frames": n, "lowest_cm": 100 * min(r["low"] for r in frames),
                              "contact_frames": {{}}, "contact_miss_mm": {{}}, "contact_median_mm": {{}}}}
        for s in "LR":
            floor = min(r[s][0] for r in frames)
            down = [r[s][1] for r in frames if r[s][0] < floor + anim_math.CONTACT_WINDOW_M]
            info["contact_frames"][s], info["contact_miss_mm"][s] = len(down), max(down)
            info["contact_median_mm"][s] = sorted(down)[len(down) // 2]
        info["finger_change_deg"] = max(angle(frames[0]["fingers"][b].rotation_difference(r["fingers"][b]))
                                        for r in frames for b in FINGERS)
        info["finger_curl_deg"] = sum(angle(frames[0]["fingers"][b]) for b in FINGERS) / len(FINGERS)
    for o in set(bpy.data.objects) - objs:
        bpy.data.objects.remove(o, do_unlink=True)
json.dump(res, open("{out}", "w"), indent=1)
'''


if __name__ == "__main__":
    unittest.main()
