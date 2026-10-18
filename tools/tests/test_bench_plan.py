"""The bench command's plain-Python half (art #212; tools/runner/commands/_bench.py): the copy counts, the variants,
the spec, what a GLB holds, the VRAM texture import, the derived numbers and the Markdown report. No Godot needed."""

import argparse
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import common  # noqa: E402
from runner.commands import _bench, bench  # noqa: E402


def glb_bytes(doc: dict) -> bytes:
    body = json.dumps(doc).encode()
    body += b" " * (-len(body) % 4)
    return struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(body)) + struct.pack("<I4s", len(body), b"JSON") + body


GLTF = {
    "accessors": [{"count": 300}, {"count": 90}, {"count": 60}],
    "meshes": [
        {"name": "alien_base_body", "primitives": [{"indices": 0, "attributes": {"POSITION": 2}}]},
        {"name": "alien_base_body_head", "primitives": [{"indices": 1, "attributes": {"POSITION": 2},
                                                         "targets": [{}] * 64}]},
        {"name": "bench_shadow", "primitives": [{"attributes": {"POSITION": 2}}]},
    ],
}
GLB_A = {"id": "a", "res": "res://import/a.glb", "morphs": 64, "triangles": 130, "shadow_triangles": 20,
         "shadow_part": True, "mb": 29.6}
GLB_B = {"id": "b", "res": "res://import/b.glb", "morphs": 0, "triangles": 130, "shadow_triangles": 0,
         "shadow_part": False, "mb": 7.5}


class PlanTest(unittest.TestCase):
    def test_copies(self) -> None:
        self.assertEqual(_bench.parse_copies("10,20"), [10, 20])
        self.assertEqual(_bench.parse_copies(" 20, 10 ,20,"), [20, 10])
        for bad in ("", "0", "x", "65", "-3", "1.5"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _bench.parse_copies(bad)

    def test_describe_a_glb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.glb"
            path.write_bytes(glb_bytes(GLTF))
            info = _bench.describe(_bench.glb_json(path))
            (Path(tmp) / "y.glb").write_bytes(b"nope" * 8)
            with self.assertRaises(ValueError):
                _bench.glb_json(Path(tmp) / "y.glb")
        self.assertEqual(info, {"morphs": 64, "triangles": 130, "shadow_triangles": 20, "shadow_part": True})

    def test_variants(self) -> None:
        rows = _bench.variants([GLB_A, GLB_B], [10, 20])
        self.assertEqual(rows[0], {"id": "empty", "glb": "a", "copies": 0, "lod": "auto", "shadow": "full"})
        self.assertEqual(len(rows), 1 + 2 * 5 + 2 * 2)  # the shadow part adds the proxy and hand variants
        self.assertEqual([r["id"] for r in rows[1:6]], ["a_x10_auto_full", "a_x10_auto_proxy", "a_x10_off_full",
                                                        "a_x10_off_proxy", "a_x10_hand_full"])
        self.assertFalse([r for r in rows if r["glb"] == "b" and r["shadow"] == "proxy"])
        keys = [(r["glb"], r["copies"]) for r in rows[1:]]
        self.assertEqual(keys, sorted(keys, key=keys.index))  # grouped: each GLB and count once, in a run
        self.assertEqual(len({k for k in keys}), 4)
        with self.assertRaises(ValueError):
            _bench.variants([], [10])

    def test_spec(self) -> None:
        spec = _bench.spec([GLB_A], [10], frames=50, warmup=5, hand_lod_m=8.0)
        self.assertEqual(spec["glbs"], {"a": {"res": "res://import/a.glb", "morphs": 64}})
        self.assertEqual((spec["frames"], spec["warmup_frames"], spec["hand_lod_m"]), (50, 5, 8.0))
        self.assertEqual(spec["shadow_part"], _bench.SHADOW_PART)
        self.assertEqual(spec["fov_deg"], 75.0)
        with self.assertRaises(ValueError):
            _bench.spec([GLB_A], [10], frames=0)

    def test_ring(self) -> None:
        # the far side of a 10-body ring is 6.9 m away on the ground (7.1 m from the eye): no body past a 10 m LOD2
        ten = _bench.ring_distances(10)
        self.assertEqual(len(ten), 10)
        self.assertAlmostEqual(max(ten), 7.08, places=2)
        self.assertAlmostEqual(min(ten), 2.97, places=2)
        self.assertEqual(_bench.beyond(10, 10.0), 0)
        self.assertEqual(_bench.beyond(20, 10.0), 5)
        self.assertEqual(_bench.spec([GLB_A], [10])["ring"], _bench.RING)

    def test_hand_lod_from_the_contract(self) -> None:
        from runner.commands import _contract

        lod2 = next(lv for lv in _contract.load_contract()["lods"]["levels"] if lv["name"] == "LOD2")
        self.assertEqual(_bench.contract_hand_lod_m(), float(lod2["from_m"]))
        # read when the bench runs, never at import: cli.py imports every command, so a broken contract.toml would
        # otherwise break every runner command
        self.assertFalse(hasattr(_bench, "HAND_LOD_M"))
        self.assertEqual(_bench.spec([GLB_A], [10])["hand_lod_m"], float(lod2["from_m"]))
        self.assertEqual(_bench.contract_hand_lod_m({"lods": {"levels": [{"name": "LOD2", "from_m": 12}]}}), 12.0)
        with self.assertRaises(ValueError):
            _bench.contract_hand_lod_m({"lods": {"levels": []}})

    def test_vram_import(self) -> None:
        text = "[remap]\n\nimporter=\"texture\"\n\n[params]\n\ncompress/mode=0\ncompress/normal_map=0\n"
        out = _bench.vram_import(text, normal=True)
        self.assertIn("compress/mode=2\n", out)
        self.assertIn("compress/normal_map=1\n", out)
        self.assertIn("mipmaps/generate=true\n", out)
        self.assertEqual(_bench.vram_import(out, normal=True), out)
        self.assertIn("compress/normal_map=0", _bench.vram_import(text, normal=False))


RECORD = {
    "adapter": "Test GPU", "adapter_vendor": "Test", "renderer": "vulkan forward_plus", "godot": "4.7.2",
    "window": [1920, 1080], "fov_deg": 75.0, "frames": 300.0,
    "rows": [
        {"id": "empty", "glb": "a", "copies": 0.0, "lod": "auto", "shadow": "full", "gpu_ms": 0.7, "cpu_ms": 0.1,
         "process_ms": 0.05, "frame_ms": 1.2,
         "gpu_ms_p95": 0.75, "primitives": 10, "draw_calls": 5, "video_mb": 250.0, "buffer_mb": 31.0},
        {"id": "a_x20_auto_full", "glb": "a", "copies": 20.0, "lod": "auto", "shadow": "full", "gpu_ms": 1.4,
         "cpu_ms": 0.4, "process_ms": 0.25, "frame_ms": 8.1, "gpu_ms_p95": 1.5, "primitives": 900000, "draw_calls": 300, "video_mb": 270.0,
         "buffer_mb": 53.5},
        {"id": "a_x20_off_full", "glb": "a", "copies": 20.0, "lod": "off", "shadow": "full", "gpu_ms": 5.2,
         "cpu_ms": 0.5, "gpu_ms_p95": 6.0, "primitives": 4000000, "draw_calls": 300, "video_mb": 270.0,
         "buffer_mb": 53.5},
    ],
    "groups": [{"key": "a x20", "memory_before": {"buffer_mb": 31.0, "video_mb": 250.0, "texture_mb": 10.0},
                "memory_after": {"buffer_mb": 53.5, "video_mb": 270.0, "texture_mb": 18.0}}],
}


class ReportTest(unittest.TestCase):
    def test_derive_and_report(self) -> None:
        record = _bench.derive(json.loads(json.dumps(RECORD)))
        rows = {r["id"]: r for r in record["rows"]}
        self.assertEqual(rows["empty"]["char_gpu_ms"], 0.0)
        self.assertEqual(rows["a_x20_auto_full"]["char_gpu_ms"], 0.7)
        self.assertEqual(record["groups"][0]["buffer_mb_added"], 22.5)
        self.assertEqual(record["groups"][0]["texture_mb_added"], 8.0)
        lines = _bench.report(record, [GLB_A], budget_ms=4.0)
        text = "\n".join(lines)
        self.assertIn("Test GPU", text)
        self.assertIn("| a_x20_auto_full | 20 | 5 | auto | full | 1.40 |", text)  # 5 of 20 beyond 10 m
        self.assertIn("| 0.40 | 0.30 | 0.25 | 8.10 |", text)  # CPU ms, chars CPU ms, process ms, frame ms
        self.assertIn("| 0.50 | 0.40 | - | - |", text)  # a row from before the process and frame fields
        self.assertEqual(rows["a_x20_auto_full"]["char_process_ms"], 0.2)
        self.assertIn("CPU ms is the viewport's render time only", text)
        self.assertIn("300 measured frames", text)
        verdicts = [ln for ln in lines if "budget" in ln]
        self.assertEqual(len(verdicts), 1)
        self.assertIn("20 bodies cost 0.70 ms GPU in the default setup (a_x20_auto_full), within the 4 ms budget; "
                      "the worst variant 4.50 ms (a_x20_off_full, OVER)", verdicts[0])
        over = _bench.verdict(record, [GLB_A], 20, budget_ms=0.5)
        self.assertIn("OVER the 0.5 ms budget", over[0])
        # the default setup decides, not the cheapest variant
        cheap = json.loads(json.dumps(record))
        cheap["rows"].append(dict(rows["a_x20_auto_full"], id="a_x20_auto_proxy", shadow="proxy",
                                  char_gpu_ms=0.1))
        self.assertIn("OVER the 0.5 ms budget", _bench.verdict(cheap, [GLB_A], 20, budget_ms=0.5)[0])


class ProxyImagesTest(unittest.TestCase):
    def test_stem(self) -> None:
        sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
        import bench_proxy  # no bpy at import time

        self.assertEqual(bench_proxy.stem("alien_body_col"), "alien_body_col")
        self.assertEqual(bench_proxy.stem("Alien_Body_Col.png"), "alien_body_col")
        self.assertEqual(bench_proxy.stem("alien_body_col.001"), "alien_body_col")
        self.assertEqual(bench_proxy.stem("//textures/alien_eyes_col.png"), "alien_eyes_col")
        self.assertEqual(bench_proxy.stem("eyes.v2"), "eyes.v2")


class ArgumentsTest(unittest.TestCase):
    def parse(self, argv: list[str]) -> argparse.Namespace:
        parser = argparse.ArgumentParser()
        bench.add_arguments(parser)
        return parser.parse_args(argv)

    def test_defaults(self) -> None:
        args = self.parse([])
        self.assertEqual((args.copies, args.tris, args.morphs, args.frames), ("10,20", 40000, "0,32,64", 300))
        self.assertEqual(args.budget_ms, _bench.BUDGET_MS)

    def test_refusals_before_any_godot(self) -> None:
        for argv, why in ((["--copies", "0"], "copies"), ([], "--proxy-from"),
                          (["no/such.glb"], "no GLB"), (["--proxy-from", "no/such.blend"], "no character .blend")):
            with self.subTest(argv=argv), tempfile.TemporaryDirectory(dir=common.OUT if common.OUT.is_dir() else None) as tmp:
                with self.assertRaises(common.Failure) as caught:
                    bench.run(self.parse([*argv, "--out", tmp]))
                self.assertIn(why, str(caught.exception))

    def test_refuses_two_glbs_with_one_stem(self) -> None:
        with tempfile.TemporaryDirectory(dir=common.OUT if common.OUT.is_dir() else None) as tmp:
            for sub in ("a", "b"):
                (Path(tmp) / sub).mkdir()
                (Path(tmp) / sub / "char.glb").write_bytes(glb_bytes(GLTF))
            with self.assertRaises(common.Failure) as caught:
                bench.run(self.parse([str(Path(tmp) / "a" / "char.glb"), str(Path(tmp) / "b" / "char.glb"),
                                      "--out", str(Path(tmp) / "out")]))
            self.assertIn("two GLBs named char", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
