"""The charger's electricity (art #263, prime-game#1095 "some electricity there"; docs/ship.md "Lens room C"):
godot/charger/zap.gd's arcs leave the inner prongs' electrodes (charger_dims.toml's, on the track ring) and land on
the crystal's surface; they run only while charging (never idle or charged), the flash only inside the charging
state at the charge's end; the conduit cores carry their run coordinate in their UV; the two shaders ship with the
export. Plain Python (the scripts' text, the builder's parts, no Godot or Blender)."""

from __future__ import annotations

import math
import re
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
sys.path.insert(0, str(ROOT / "tools"))
import ship_interior_lens as LN  # noqa: E402
from runner import ship_export as X  # noqa: E402

CHARGER = ROOT / "godot" / "charger"
ZAP = (CHARGER / "zap.gd").read_text(encoding="utf-8")
CYCLE = (CHARGER / "cycle.gd").read_text(encoding="utf-8")
with (ROOT / "tools" / "blender" / "charger_dims.toml").open("rb") as _f:
    DIMS = tomllib.load(_f)


def const(text: str, name: str):
    """A GDScript const's value (numbers and nested lists of numbers)."""
    m = re.search(rf"^const {name} := (.+?)(?:\s*#.*)?$", text, re.M)
    if m is None:
        raise AssertionError(f"no const {name}")
    return eval(m.group(1), {"__builtins__": {}})  # noqa: S307: numbers and lists only, from our own script


def func(text: str, name: str) -> str:
    """A static func's body (up to the next top-level line)."""
    m = re.search(rf"^static func {name}\(.*?(?=^\S)", text + "\nEND", re.M | re.S)
    if m is None:
        raise AssertionError(f"no func {name}")
    return m.group(0)


class EndpointsTest(unittest.TestCase):
    def test_the_electrodes_are_the_builds(self) -> None:
        self.assertEqual(const(ZAP, "ELECTRODES"), DIMS["inner"]["electrodes"])
        self.assertEqual(const(ZAP, "HALF_DEG"), DIMS["inner"]["half_deg"])
        # charger_build.build_electrodes: r cos(half_deg / 3) - 0.45 er from the axis
        body = func(ZAP, "bind")
        self.assertIn('float(e[0]) * cos(deg_to_rad(HALF_DEG / 3.0)) - 0.45 * float(e[2])', body)

    def test_the_axis_is_the_chargers(self) -> None:
        charger = (CHARGER / "charger.gd").read_text(encoding="utf-8")
        m = re.search(r"glow\.position = Vector3\(([-\d.]+), ([-\d.]+), ([-\d.]+)\)", charger)
        self.assertIsNotNone(m)
        self.assertAlmostEqual(const(ZAP, "AXIS_D"), float(m.group(3)))
        self.assertAlmostEqual(float(m.group(1)), 0.0)

    def test_an_arc_leaves_an_electrode_on_the_ring_and_lands_on_the_crystal(self) -> None:
        body = func(ZAP, "_ends")
        # the start: the electrode where the ring is now, moved its own radius toward the hit
        self.assertIn('_rel(z["ring"], model) * (z["locals"][i] as Vector3)', body)
        self.assertIn('e + (hit - e).normalized() * float(z["radii"][i])', body)
        # the hit: on the crystal's surface (its radius profile) where the crystal is now
        self.assertIn('_rel(z["crystal"], model)', body)
        self.assertIn("ct * Vector3(dir.x * r, h, dir.y * r)", body)
        self.assertIn("_radius(p, h)", body)
        # the bolt's ends are fixed: midpoint displacement never moves the first or last point
        bolt = func(ZAP, "_bolt")
        self.assertIn("var pts: Array[Vector3] = [a, b]", bolt)
        self.assertIn("next.append(pts[-1])", bolt)

    def test_the_cycle_checks_the_ends(self) -> None:
        self.assertIn("Zap.endpoints(look)", CYCLE)
        self.assertIn('"arc_ends_off": _zap_bad', CYCLE)


class GatingTest(unittest.TestCase):
    def test_arcs_only_while_charging(self) -> None:
        body = func(ZAP, "step")
        self.assertIn('var charging: bool = look["state"] == "charging"', body)
        self.assertIn("var flashing: bool = charging and seated and flash > 0.0", body)
        self.assertIn("var arcing: bool = flashing or (charging and seated and charge > 0.0 and charge < 1.0)",
                      body)
        draw = func(ZAP, "_draw")
        self.assertIn('l.visible = arcing and bool(a["on"])', draw)
        self.assertIn("if not l.visible:\n\t\t\tcontinue", draw)

    def test_the_flash_falls_inside_charging_at_the_charges_end(self) -> None:
        flash, charge = const(CYCLE, "FLASH"), const(CYCLE, "CHARGE")
        charging_at, rise_down = const(CYCLE, "CHARGING_AT"), const(CYCLE, "RISE_DOWN")
        self.assertAlmostEqual(flash[0], charge[1])          # with the full charge (and the ring's flare)
        self.assertTrue(charging_at < flash[0] < flash[1] < rise_down[1])   # still "charging": never idle or charged
        self.assertTrue(0.15 <= flash[1] - flash[0] <= 0.3)

    def test_the_keys_show_the_arcs_and_the_flash(self) -> None:
        labels = re.findall(r'\[([\d.]+), "([^"]+)"\]', CYCLE[CYCLE.index("const KEYS"):])
        times = {lab: float(t) for t, lab in labels}
        arcs = [t for lab, t in times.items() if "the arcs" in lab]
        flash = [t for lab, t in times.items() if "the big flash" in lab]
        self.assertTrue(arcs and const(CYCLE, "CHARGE")[0] < arcs[0] < const(CYCLE, "CHARGE")[1])
        self.assertTrue(flash and const(CYCLE, "FLASH")[0] < flash[0] < const(CYCLE, "FLASH")[1])


class ConduitTest(unittest.TestCase):
    def test_the_cores_carry_their_run_in_their_uv(self) -> None:
        for side in ("e", "w"):
            parts = {p["name"]: p for p in LN.lens_conduits({"side": side}, None)}
            core = parts["cores"]
            self.assertEqual(core["mat"], "int_cyan__lens_core")
            self.assertEqual(len(core["uv"]), len(core["faces"]))
            lengths = set()
            for face, uvs in zip(core["faces"], core["uv"]):
                self.assertEqual(len(face), len(uvs))
                for x, v in uvs:
                    self.assertTrue(0.0 <= x <= 1.0)
                    lengths.add(round(1.0 - v, 6))   # Godot's UV.y: the run's metres
            self.assertTrue(all(0.5 < m < 2.5 for m in lengths), lengths)
            # x 0 where the run leaves the jamb (the path's first point), 1 at the deck or the ceiling
            for s in (-1, 1):
                for path in LN.conduit_paths(side, s):
                    uv = LN.core_uvs(path, LN.CORE_SIDES)
                    self.assertEqual(uv[0][0][0], 0.0)
                    self.assertEqual(uv[-1][0][0], 1.0)
                    self.assertAlmostEqual(1.0 - uv[0][0][1],
                                           sum(math.dist(a, b) for a, b in zip(path, path[1:])))

    def test_zap_binds_the_cores_material(self) -> None:
        self.assertEqual(re.findall(r'const CORE_MAT := "(\w+)"', ZAP), ["int_cyan__lens_core"])
        shader = (CHARGER / "conduit.gdshader").read_text(encoding="utf-8")
        for name in ("flow", "steady", "lit", "clock"):
            self.assertRegex(shader, rf"uniform float {name}\b")


class ShaderTest(unittest.TestCase):
    def test_the_shaders_ship_with_the_export(self) -> None:
        for src, name in (("charger/arc.gdshader", "charger_arc.gdshader"),
                          ("charger/conduit.gdshader", "charger_conduit.gdshader")):
            self.assertEqual(X.SHADERS.get(src), name)
            self.assertTrue((ROOT / "godot" / src).is_file(), src)
            text = X.relocate(f'[ext_resource type="Shader" path="res://{src}" id="3_t"]\n')
            self.assertIn(f'path="res://{X.ASSET_DIR}/{name}"', text)
            self.assertEqual(X.leftovers(text), [])
        self.assertIn('preload("res://charger/arc.gdshader")', ZAP)
        self.assertIn('preload("res://charger/conduit.gdshader")', ZAP)

    def test_the_arcs_are_unshaded_and_additive(self) -> None:
        shader = (CHARGER / "arc.gdshader").read_text(encoding="utf-8")
        mode = re.search(r"render_mode ([^;]+);", shader).group(1)
        for m in ("unshaded", "blend_add", "depth_draw_never"):
            self.assertIn(m, mode)

    def test_charger_gd_stays_free_of_the_zap(self) -> None:
        # charger.gd's copy ships in assets/prop/crystal_charger byte-equal; the electricity is zap.gd's
        self.assertNotIn("zap", (CHARGER / "charger.gd").read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
