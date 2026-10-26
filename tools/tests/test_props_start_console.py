"""The start console's committed asset (art#263's stations): the drawing's numbers in console_dims.toml, the
manifest, the GLB's size, surfaces and UVs, the report and the look's files, read without Blender or Godot. Skips
the GLB checks in a checkout without its LFS files."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import tomllib
import unittest

from runner import common
from runner.commands import _manifest

ASSET = common.ROOT / "assets" / "prop" / "start_console"
EXPORT = ASSET / "export"
DIMS = common.ROOT / "tools" / "blender" / "console_dims.toml"
TRIANGLES = 58700  # the whole console: 55,661 at build2; spin-up step 1 58,217, step 2 58,555 (the deck ring, sprites)
SURFACES = {"console_bronze", "console_graphite", "console_cyan", "console_button", "console_stage", "console_lamp",
            "console_holo_line", "console_holo_shell", "console_beam", "console_holo_turbine", "console_holo_wire",
            "console_holo_ring", "console_holo_digit"}
STATIONS = ["socket_w", "socket_e", "socket_fw", "socket_fe", "breaker_w", "breaker_e", "vent_w", "vent_e"]
SHIP = common.ROOT / "layouts" / "ship" / "ship.toml"
MATERIAL_FILES = ("console.gd", "console_metal.gdshader", "console_signal.gdshader", "console_holo.gdshader")


def lfs_pointer(path) -> bool:
    return path.read_bytes()[:40].startswith(b"version https://git-lfs")


def glb_json(path) -> dict:
    """The GLB's JSON chunk (the first chunk after the 12-byte header)."""
    data = path.read_bytes()
    magic, _, _ = struct.unpack("<4sII", data[:12])
    assert magic == b"glTF", path
    length, kind = struct.unpack("<I4s", data[12:20])
    assert kind == b"JSON", path
    return json.loads(data[20:20 + length])


def glb_uvs(path, doc: dict, prim: dict) -> list[tuple[float, float]]:
    """A primitive's TEXCOORD_0 pairs (float VEC2) from the GLB's binary chunk."""
    data = path.read_bytes()
    jlen = struct.unpack("<I", data[12:16])[0]
    bin_start = 20 + jlen + 8
    acc = doc["accessors"][prim["attributes"]["TEXCOORD_0"]]
    assert acc["componentType"] == 5126 and acc["type"] == "VEC2", acc
    view = doc["bufferViews"][acc["bufferView"]]
    start = bin_start + view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride", 8)
    return [struct.unpack_from("<2f", data, start + i * stride) for i in range(acc["count"])]


class StartConsoleDrawing(unittest.TestCase):
    def test_dims_keep_the_drawings_numbers(self) -> None:
        # prime-game-design stations-final/console-drawing/drawing.js (node: its N object), the engineer's sizes
        d = tomllib.loads(DIMS.read_text(encoding="utf-8"))
        self.assertAlmostEqual(d["plinth"]["r_top"] * 2, 120.0, delta=0.1)
        self.assertAlmostEqual(d["plinth"]["h_top"], 15.25, delta=0.05)
        self.assertAlmostEqual(d["body"]["r_bottom"] * 2, 110.8, delta=0.1)
        self.assertAlmostEqual(d["body"]["r_top"] * 2, 105.2, delta=0.1)
        self.assertAlmostEqual(d["body"]["h0"], 19.67, delta=0.05)
        self.assertAlmostEqual(d["body"]["h1"], 91.64, delta=0.05)
        self.assertAlmostEqual(d["rim"]["r"] * 2, 111.5, delta=0.1)
        self.assertAlmostEqual(d["rim"]["r_top"] * 2, 103.3, delta=0.1)
        self.assertAlmostEqual(d["rim"]["h0"], 93.28, delta=0.05)
        self.assertAlmostEqual(d["rim"]["h1"], 109.34, delta=0.05)
        self.assertAlmostEqual(d["button"]["h"], 81.4, delta=0.05)  # the drawing's 85.41, lowered 4 cm on review
        self.assertAlmostEqual(d["button"]["collar"], 15.57, delta=0.05)
        self.assertAlmostEqual(d["button"]["proud"], 4.42, delta=0.05)
        self.assertEqual(len(d["strips"]["u"]), 3)
        self.assertAlmostEqual(d["emitter"]["ring"], 82.78, delta=0.05)
        self.assertAlmostEqual(d["emitter"]["core"], 19.75, delta=0.05)
        self.assertAlmostEqual(d["hologram"]["span"], 159.84, delta=0.05)
        self.assertAlmostEqual(d["hologram"]["disc_h"], 145.74, delta=0.05)
        self.assertEqual(d["hologram"]["tilt"], 12.0)
        self.assertEqual(d["measure"]["lift"], 40.0)


class StartConsoleAsset(unittest.TestCase):
    def test_manifest_is_valid(self) -> None:
        data, problem = _manifest.load(ASSET / "manifest.toml")
        self.assertIsNotNone(data, problem)
        self.assertEqual(data["id"], "start_console")
        self.assertEqual(data["kind"], "prop")
        self.assertFalse(data["ai_generated"])  # built from code in Blender: no generator touched it
        self.assertEqual(data["licence"], "own-work")
        self.assertEqual(_manifest.validate(data, "prop", "start_console"), [])

    def test_glb_size_surfaces_and_uvs(self) -> None:
        glb = EXPORT / "start_console.glb"
        if lfs_pointer(glb):
            self.skipTest("LFS file not fetched")
        doc = glb_json(glb)
        self.assertEqual(len(doc["meshes"]), 1)
        prims = doc["meshes"][0]["primitives"]
        names = {doc["materials"][p["material"]]["name"] for p in prims}
        self.assertEqual(names, SURFACES)  # console.gd finds its surfaces by these names
        tris = sum(doc["accessors"][p["indices"]]["count"] // 3 for p in prims)
        self.assertLessEqual(tris, TRIANGLES)
        lo = [min(doc["accessors"][p["attributes"]["POSITION"]]["min"][i] for p in prims) for i in range(3)]
        hi = [max(doc["accessors"][p["attributes"]["POSITION"]]["max"][i] for p in prims) for i in range(3)]
        self.assertAlmostEqual(lo[1], 0.0, delta=0.001)  # glTF is Y-up: the origin on the floor
        self.assertAlmostEqual(hi[0] - lo[0], 1.598, delta=0.03)  # the hologram's span, the drawing's 159.8 cm
        self.assertTrue(2.27 < hi[1] < 2.30, hi[1])  # the countdown's digits (step 2: 45 cm, 2.06 m their middle)
        self.assertNotIn("images", doc)  # no textures
        # UV0 carries the chamfer flag (u) and the strip's or lamp's index (v); the exporter writes 1 - v and the
        # shaders read 1 - UV.y, so the indices come back from 1 - v
        by_name = {doc["materials"][p["material"]]["name"]: p for p in prims}
        index = lambda name: {round(1.0 - v) for _u, v in glb_uvs(glb, doc, by_name[name])}  # noqa: E731
        self.assertEqual(index("console_stage"), {0, 1, 2})
        self.assertEqual(index("console_lamp"), set(range(8)))
        self.assertEqual(index("console_holo_line") - set(range(101)), set())  # brightness x 100
        bronze_u = {round(u) for u, _v in glb_uvs(glb, doc, by_name["console_bronze"])}
        self.assertEqual(bronze_u, {0, 1})  # the chamfer faces are flagged, the metal brightens them

    def test_spinup_ids_in_uv0(self) -> None:
        # the spin-up's parts carry their ids in UV0 (console_holo.gdshader modes 3..6); glTF writes 1 - v
        glb = EXPORT / "start_console.glb"
        if lfs_pointer(glb):
            self.skipTest("LFS file not fetched")
        doc = glb_json(glb)
        by_name = {doc["materials"][p["material"]]["name"]: p for p in doc["meshes"][0]["primitives"]}
        uvs = lambda name: glb_uvs(glb, doc, by_name[name])  # noqa: E731
        stage_u = [u for u, _v in uvs("console_stage")]  # the fill's share across each strip
        self.assertAlmostEqual(min(stage_u), 0.0, delta=0.02)  # the light face sits inside its 3 mm chamfer
        self.assertAlmostEqual(max(stage_u), 1.0, delta=0.02)
        wire = uvs("console_holo_wire")
        self.assertEqual({round(1.0 - v) for _u, v in wire}, set(range(9)))  # 8 stations and the manifold
        # the points and their halos; step 2: a broken point's pillar (u -3 - its height share) and glow (u -5)
        self.assertEqual({round(u) for u, _v in wire if u < -0.5}, {-1, -2, -3, -4, -5})
        self.assertTrue(all(u >= -1e-4 for u, _v in wire if u > -0.5))  # the lines' distance toward the turbines
        fx = [(u, 1.0 - v) for u, v in wire if u < -2.5]  # each corner FX_SPREAD off its station's index
        self.assertEqual({round(abs(v - round(v)), 3) for _u, v in fx}, {0.3})
        self.assertEqual({round(v) for _u, v in fx}, set(range(8)))
        ring = uvs("console_holo_ring")
        # the band's foot and built top (step 2: built 2x tall, the shader draws a share), the deck ring's foot, top
        self.assertEqual({round(1.0 - v, 3) for _u, v in ring}, {0.0, 1.0, 2.0, 3.0})
        self.assertAlmostEqual(min(u for u, _v in ring), 0.0, delta=1e-4)
        self.assertAlmostEqual(max(u for u, _v in ring), 1.0, delta=1e-4)
        digits = {round(1.0 - v) for _u, v in uvs("console_holo_digit")}
        self.assertEqual(digits, {d * 10 + s for d in range(2) for s in range(7)})
        turbine = uvs("console_holo_turbine")
        self.assertIn(5.0, {round(u, 3) for u, _v in turbine})  # the fans, turned by the shader
        lines = [(u, 1.0 - v) for u, v in turbine if u < 6.0]
        self.assertTrue(all(0 <= round(v) <= 100 for _u, v in lines))  # brightness x 100
        glow = [(u, 1.0 - v) for u, v in turbine if u > 6.0]  # step 2: the call's glow sprites, one per pod
        self.assertEqual(len(glow), 3 * 4)
        self.assertEqual({(round(u, 3), round(v, 3)) for u, v in glow},
                         {(7.0 + 0.3 * sx, 200.0 + 0.3 * sy) for sx in (-1, 1) for sy in (-1, 1)})

    def test_shipped_glb_is_the_recorded_build(self) -> None:
        glb = EXPORT / "start_console.glb"
        if lfs_pointer(glb):
            self.skipTest("LFS file not fetched")
        data, _ = _manifest.load(ASSET / "manifest.toml")
        recorded = {r["file"]: r["sha256"] for r in data["raw"]}
        built = next(sha for name, sha in recorded.items() if name.endswith("/start_console.glb"))  # <tag>/
        self.assertEqual(hashlib.sha256(glb.read_bytes()).hexdigest(), built)

    def test_report_records_a_clean_validation_and_the_size(self) -> None:
        report = json.loads((ASSET / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["gltf_validator"]["numErrors"], 0)
        self.assertEqual(report["gltf_validator"]["numWarnings"], 0)
        ped = report["mesh"]["pedestal_size_m"]  # Blender axes: x, y, z
        self.assertAlmostEqual(ped[0], 1.20, delta=0.01)
        self.assertAlmostEqual(ped[2], 1.105, delta=0.01)  # the emitter's collar, a little over the rim's 109.3
        self.assertEqual(report["mesh"]["hologram"]["lamps"], 8)

    def test_report_records_the_spinup(self) -> None:
        report = json.loads((ASSET / "report.json").read_text(encoding="utf-8"))
        spin = report["spinup"]
        self.assertEqual(spin["order"], STATIONS + ["bus"])
        spots = {s["id"]: s["at"] for s in tomllib.loads(SHIP.read_text(encoding="utf-8"))["stations"]["spot"]}
        for sid in STATIONS:  # each station's point at its real place (ship.toml's spot)
            self.assertEqual(spin["stations"][sid]["plan"], spots[sid], sid)
        self.assertEqual(len(spin["turbines"]["centres"]), 3)
        self.assertEqual(spin["ring"]["dashes"], 30)

    def test_console_gd_spinup_api_and_constants(self) -> None:
        look = (common.ROOT / "godot" / "console" / "console.gd").read_text(encoding="utf-8")
        for fn in ("set_calling", "call_phase", "set_charge", "set_spin", "set_station", "set_countdown",
                   "reset_spinup", "set_clock", "clock", "set_state", "set_passed", "set_lit"):
            self.assertRegex(look, rf"static func {fn}\(")
        m = re.search(r"const STATIONS := (\[[^\]]*\])", look)
        self.assertEqual(json.loads(m.group(1)), STATIONS)  # the order of the build's UV0 v
        report = json.loads((ASSET / "report.json").read_text(encoding="utf-8"))
        turb = report["spinup"]["turbines"]
        found = [[float(x) for x in v.split(",")] for v in
                 re.findall(r"Vector3\(([-0-9., ]+)\)", look[look.index("const FAN_CENTRES"):look.index("const FAN_AXIS")])]
        for got, want in zip(found, turb["centres"], strict=True):  # the fans turn round the GLB's own centres
            for a, b in zip(got, want):
                self.assertAlmostEqual(a, b, delta=1e-4)
        axis = [float(x) for x in re.search(r"const FAN_AXIS := Vector3\(([^)]*)\)", look).group(1).split(",")]
        for a, b in zip(axis, turb["axis"]):
            self.assertAlmostEqual(a, b, delta=1e-4)
        shader = (common.ROOT / "godot" / "console" / "console_holo.gdshader").read_text(encoding="utf-8")
        for mode in range(3, 7):
            self.assertIn(f"mode == {mode}", shader)
        for fn in ("set_fill", "set_ring_style"):  # step 2's choices
            self.assertRegex(look, rf"static func {fn}\(")
        fx = report["spinup"]["fx"]  # the sprites' and pillars' build size and corner spread match the shader's
        w0 = float(re.search(r"uniform float fx_w0 = ([0-9.]+);", shader).group(1))
        self.assertAlmostEqual(w0, fx["w0_m"], delta=1e-6)
        self.assertEqual(float(re.search(r"const float FX_SPREAD = ([0-9.]+);", shader).group(1)), fx["spread"])
        self.assertEqual(fx["glow_uv"], [7.0, 200.0])
        ring = report["spinup"]["ring"]  # step 1's band is the "step1" and "deck" styles' share of the built band
        styles = re.search(r"const RING_STYLES := (\{[^}]*\})", look).group(1)
        self.assertIn(f'"step1": [{ring["band_top"]}, 1.0, 0.0]', styles.replace("\n\t", " "))
        self.assertRegex(look, r'const RING_STYLE := "(band|deck|both)"')
        self.assertRegex(look, r'const FILL := "(cyan|green)"')

    def test_passed_and_charge_are_separate_uniforms(self) -> None:
        # review 1 of PR #325: reset_spinup's set_charge(0) wiped set_passed's strips; the strips show
        # max(passed / 3, charge), the ring the charge alone, and reset_spinup leaves passed alone
        look = (common.ROOT / "godot" / "console" / "console.gd").read_text(encoding="utf-8")
        signal = (common.ROOT / "godot" / "console" / "console_signal.gdshader").read_text(encoding="utf-8")
        self.assertIn("uniform float passed", signal)
        self.assertIn("max(clamp(passed, 0.0, 3.0) / 3.0, charge)", signal)
        body = lambda fn: look[look.index(f"static func {fn}("):].split("\n\n\n")[0]  # noqa: E731
        self.assertIn('set_shader_parameter("passed"', body("set_passed"))
        self.assertNotIn('"charge"', body("set_passed"))
        self.assertNotIn("passed", body("set_charge"))
        self.assertNotIn("set_passed", body("reset_spinup"))
        self.assertIn("BLINK_MIN", body("set_station"))  # a broken station never reads solid red
        self.assertIn("console_tween", body("apply"))  # a second apply() stops the first look's clock

    def test_build_pods_are_the_exteriors_places(self) -> None:
        # review 1 of PR #325: the hologram takes the raise off the pods (h - LIFT); PODS must be exterior.toml's
        # design-frame places, and --pieces without --lift is refused (else the hologram's pods sit 0.6 m high)
        src = (common.ROOT / "tools" / "blender" / "console_build.py").read_text(encoding="utf-8")
        pods = re.findall(r'\("(nozzle_pod_\w+)", \(([-0-9.]+), ([-0-9.]+), ([-0-9.]+)\)\)', src)
        self.assertEqual(len(pods), 3)
        place = tomllib.loads((common.ROOT / "layouts" / "ship" / "exterior.toml").read_text(encoding="utf-8"))["place"]
        for name, x, y, h in pods:
            self.assertIn([name, [float(x), float(y), float(h)], 0.0], place)
        self.assertIn('--pieces needs --lift', src)

    def test_dims_spinup(self) -> None:
        d = tomllib.loads(DIMS.read_text(encoding="utf-8"))["spinup"]
        self.assertEqual(d["ring_r"], 4.45)  # where the dashed ring was round the hall's disc
        self.assertEqual(set(d["lanes"]), {"socket_back", "socket_front", "breaker", "vent"})
        radii = sorted(r for r, _x in d["lanes"].values())
        self.assertEqual(len(set(radii)), 4)  # one lane each: the lines never share a path
        self.assertLess(max(radii), 4.0)  # inside the hall's disc

    def test_shipped_look_matches_the_godot_files(self) -> None:
        for name in MATERIAL_FILES:
            shipped = (EXPORT / name).read_text(encoding="utf-8")
            self.assertEqual(shipped, (common.ROOT / "godot" / "console" / name).read_text(encoding="utf-8"), name)
        look = (EXPORT / "console.gd").read_text(encoding="utf-8")
        for surface in SURFACES:  # every surface has its material in the look
            self.assertIn(f'"{surface}"', look)


if __name__ == "__main__":
    unittest.main()
