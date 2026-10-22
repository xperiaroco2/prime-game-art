"""Writes layouts/ship/interior.toml, the INTERIOR lane's pieces and placements (art #263, docs/ship.md), from the
numbers in ship_interior.py. Plain Python (no Blender):

    $PYTHON_BIN tools/blender/ship_interior_place.py [--check]

--check: exit 1 when the committed file differs from what this script writes (the fast test runs it).
A placement is [piece, [x, y, h], yaw]: a piece built at plan angle 0 and standing at angle a gets yaw -a; inside a tip
room turned by r the yaw is r - a (the west room is the east one turned 180)."""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ship_interior as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "layouts" / "ship" / "interior.toml"
F = S.FLOOR
H_IN_HALL = F + S.H_HALL + (S.APEX_HALL - S.H_HALL) * (1 - S.R_RING / S.R_HALL)
H_IN_TIP = F + S.H_TIP + (S.APEX_TIP - S.H_TIP) * (1 - S.R_TIP_RING / S.R_TIP)
SPOKE_HALL, SPOKE_TIP = 3.07, 4.1

# id: (builder, args, collide)
PIECES: dict[str, tuple[str, dict, bool]] = {
    # the hall
    "hall_floor_base": ("hall_floor_base", {}, True),
    "hall_floor_disc": ("floor_disc", {"radius": 1.0}, True),
    "hall_grate": ("radial_grate", {"r0": 1.1, "r1": 2.5, "half_deg": 22.5 - SPOKE_HALL, "ref": 1.8}, True),
    "hall_spoke": ("spoke", {"r0": 1.07, "r1": 2.53, "half_deg": SPOKE_HALL, "ref": 1.8}, True),
    "hall_amber_arc": ("amber_arc", {"radius": 2.58}, False),
    "hall_floor_rim": ("hall_floor_rim", {}, True),
    "hall_threshold": ("hall_threshold", {}, True),
    "hall_panel_a": ("wall_panel", {"half": S.HW, "height": S.H_HALL, "tone": "a"}, True),
    "hall_panel_b": ("wall_panel", {"half": S.HW, "height": S.H_HALL, "tone": "b"}, True),
    "hall_pilaster": ("pilaster", {"height": S.H_HALL}, True),
    "hall_pilaster_strip": ("pilaster_strip", {"height": S.H_HALL}, False),
    "hall_trunk": ("trunk", {"height": S.H_HALL}, True),
    "hall_trunk_cables": ("trunk_cables", {"height": S.H_HALL}, False),
    "trunk_clip": ("trunk_clip", {}, False),
    "hall_portal": ("portal", {"half": S.HCH, "height": S.H_HALL, "soffit": True}, True),
    "portal_strip_l": ("portal_strip", {"side": -1}, False),
    "portal_strip_r": ("portal_strip", {"side": 1}, False),
    "hall_ceil_panel_a": ("hall_ceil_panel", {"tone": "a"}, False),
    "hall_ceil_panel_b": ("hall_ceil_panel", {"tone": "b"}, False),
    "hall_rib": ("rib", {"rv": S.HV, "rim": F + S.H_HALL, "r_in": S.R_RING, "h_in": H_IN_HALL}, False),
    "hall_rib_strip": ("rib", {"rv": S.HV, "rim": F + S.H_HALL, "r_in": S.R_RING, "h_in": H_IN_HALL, "strip": True},
                       False),
    "hall_lamp_ring": ("lamp_ring", {"radius": S.R_RING, "h_in": H_IN_HALL}, False),
    "hall_lamp": ("lamp", {"h_in": H_IN_HALL}, False),
    # the corridors and the mouth passage
    "cor_floor_base": ("cor_floor_base", {"length": S.COR_X1 - S.COR_X0}, True),
    "cor_grate": ("cor_grate", {"length": S.MOD_L}, True),
    "cor_gutter": ("cor_gutter", {"length": S.MOD_L}, True),
    "floor_light": ("floor_light", {"length": 0.7}, False),
    "cor_wall_low_a": ("cor_wall_low", {"length": S.MOD_L, "tone": "a"}, True),
    "cor_wall_low_b": ("cor_wall_low", {"length": S.MOD_L, "tone": "b"}, True),
    "cor_channel": ("cor_channel", {"length": S.MOD_L}, True),
    "cor_cables": ("cor_cables", {"length": S.MOD_L}, False),
    "clip_h": ("clip_h", {}, False),
    "cor_wall_up_a": ("cor_wall_up", {"length": S.MOD_L, "tone": "a"}, True),
    "cor_wall_up_b": ("cor_wall_up", {"length": S.MOD_L, "tone": "b"}, True),
    "cor_ceil": ("cor_ceil", {"length": S.MOD_L}, False),
    "cor_arch": ("cor_arch", {}, True),
    "arch_strip_l": ("cor_arch_strip", {"side": -1}, False),
    "arch_strip_r": ("cor_arch_strip", {"side": 1}, False),
    "mouth_floor_base": ("cor_floor_base", {"length": S.MOUTH_L}, True),
    "mouth_grate": ("cor_grate", {"length": S.MOUTH_L}, True),
    "mouth_gutter": ("cor_gutter", {"length": S.MOUTH_L}, True),
    "mouth_wall_low": ("cor_wall_low", {"length": S.MOUTH_L, "tone": "a"}, True),
    "mouth_channel": ("cor_channel", {"length": S.MOUTH_L}, True),
    "mouth_cables": ("cor_cables", {"length": S.MOUTH_L}, False),
    "mouth_wall_up": ("cor_wall_up", {"length": S.MOUTH_L, "tone": "a"}, True),
    "mouth_ceil": ("cor_ceil", {"length": S.MOUTH_L}, False),
    # the tip rooms
    "tip_floor_base": ("tip_floor_base", {}, True),
    "tip_floor_disc": ("floor_disc", {"radius": 0.62}, True),
    "tip_grate": ("radial_grate", {"r0": 0.7, "r1": 1.72, "half_deg": 22.5 - SPOKE_TIP, "ref": 1.2}, True),
    "tip_spoke": ("spoke", {"r0": 0.68, "r1": 1.76, "half_deg": SPOKE_TIP, "ref": 1.2}, True),
    "tip_light": ("floor_light", {"length": 0.72}, False),
    "tip_floor_rim": ("tip_floor_rim", {}, True),
    "tip_panel_a": ("wall_panel", {"half": S.R_TIP * math.sin(math.radians(12.9)), "height": S.H_TIP, "tone": "a"},
                    True),
    "tip_panel_b": ("wall_panel", {"half": S.R_TIP * math.sin(math.radians(12.9)), "height": S.H_TIP, "tone": "b"},
                    True),
    "tip_pilaster": ("pilaster", {"height": S.H_TIP}, True),
    "tip_pilaster_strip": ("pilaster_strip", {"height": S.H_TIP}, False),
    "tip_trunk": ("trunk", {"height": S.H_TIP}, True),
    "tip_trunk_cables": ("trunk_cables", {"height": S.H_TIP}, False),
    "tip_window_frame": ("tip_window_frame", {}, True),
    "tip_glass": ("tip_glass", {}, True),
    "tip_sill_strip": ("tip_sill_strip", {}, False),
    "tip_portal": ("portal", {"half": S.TIP_CHORD_H, "height": S.H_TIP}, True),
    "tip_ceiling": ("tip_ceiling", {}, False),
    "tip_rib": ("rib", {"rv": S.R_TIP, "rim": F + S.H_TIP, "r_in": S.R_TIP_RING, "h_in": H_IN_TIP}, False),
    "tip_rib_strip": ("rib", {"rv": S.R_TIP, "rim": F + S.H_TIP, "r_in": S.R_TIP_RING, "h_in": H_IN_TIP,
                              "strip": True}, False),
    "tip_lamp_ring": ("lamp_ring", {"radius": S.R_TIP_RING, "h_in": H_IN_TIP}, False),
    "tip_lamp": ("lamp", {"h_in": H_IN_TIP}, False),
    # details
    "cup_a": ("cup", {"seed": 3, "scale": 1.25}, False),
    "cup_b": ("cup", {"seed": 11, "scale": 1.25}, False),
    "cup_c": ("cup", {"seed": 27, "scale": 1.25}, False),
    "spill_a": ("spill", {"seed": 4}, False),
    "spill_c": ("spill", {"seed": 8}, False),
    "cable_coil": ("cable_coil", {}, False),
    "floor_patch_a": ("floor_patch", {"u": 0.42, "v": 0.36}, False),
    "floor_patch_b": ("floor_patch", {"u": 0.36, "v": 0.3}, False),
    "rim_bolts": ("rim_bolts", {}, False),
    "scratch_a": ("scratches", {"seed": 5}, False),
    "scratch_b": ("scratches", {"seed": 9, "count": 12}, False),
}


def polar(r: float, a: float, c=(0.0, 0.0), room: float = 0.0) -> list[float]:
    t = math.radians(a - room)
    return [round(c[0] + r * math.cos(t), 4), round(c[1] + r * math.sin(t), 4)]


def local(c, yaw: float, x: float, y: float) -> list[float]:
    t = math.radians(-yaw)
    return [round(c[0] + x * math.cos(t) - y * math.sin(t), 4), round(c[1] + x * math.sin(t) + y * math.cos(t), 4)]


def norm(yaw: float) -> float:
    return round((yaw + 180.0) % 360.0 - 180.0, 3)


def placements() -> list[tuple[str, list[float], float]]:
    out: list[tuple[str, list[float], float]] = []

    def put(pid, xy, yaw=0.0, h=0.0):
        assert pid in PIECES, pid
        out.append((pid, [xy[0], xy[1], round(h, 4)], norm(yaw)))

    # --- the hall
    put("hall_floor_base", [0.0, 0.0])
    put("hall_floor_disc", [0.0, 0.0])
    put("hall_lamp_ring", [0.0, 0.0])
    openings = list(S.OPENINGS.values())
    facets = [11.25 + 22.5 * k for k in range(16)]
    facets = [((a + 180) % 360) - 180 for a in facets]
    door = [a for a in facets if any(abs(((a - o + 180) % 360) - 180) < 12 for o in openings)]
    walls = [a for a in facets if a not in door]
    verts = [((22.5 * k + 180) % 360) - 180 for k in range(16)]
    edge = [v for v in verts if any(abs(abs(((v - o + 180) % 360) - 180) - 22.5) < 1 for o in openings)]
    plain = [v for v in verts if v not in edge and all(abs(((v - o + 180) % 360) - 180) > 1 for o in openings)]
    for k in range(8):
        put("hall_grate", polar(1.8, 22.5 + 45 * k), -(22.5 + 45 * k))
        put("hall_spoke", polar(1.8, 45 * k), -45 * k)
        put("hall_lamp", polar(S.R_RING, 22.5 + 45 * k), -(22.5 + 45 * k))
    for i, a in enumerate(facets):
        put("hall_amber_arc", polar(2.58, a), -a)
        put("hall_ceil_panel_a" if i % 2 else "hall_ceil_panel_b", polar(S.R_HALL, a), -a)
    for i, a in enumerate(walls):
        put("hall_floor_rim", polar(3.0, a), -a)
        put("rim_bolts", polar(3.0, a), -a)
        put("hall_panel_a" if i % 2 else "hall_panel_b", polar(S.R_HALL, a), -a)
    for v in verts:
        put("hall_rib", polar(S.HV, v), -v)
        put("hall_rib_strip", polar(S.HV, v), -v)
    for v in edge:
        put("hall_pilaster", polar(S.HV, v), -v)
        put("hall_pilaster_strip", polar(S.HV, v), -v)
    for v in plain:  # hall_in-3's radial columns: cable trunks
        put("hall_trunk", polar(S.HV, v), -v)
        put("hall_trunk_cables", polar(S.HV, v), -v)
        for h in (0.55, 1.25, 1.95, 2.65):
            put("trunk_clip", polar(S.HV, v), -v, h)
    for o in openings:
        put("hall_threshold", polar(S.HC, o), -o)
        put("hall_portal", polar(S.HC, o), -o)
        put("portal_strip_l", polar(S.HC, o), -o)
        put("portal_strip_r", polar(S.HC, o), -o)

    # --- a passage: modules along its axis (yaw: its outward direction a gives yaw -a)
    def passage(prefix, x0, n, length, yaw, tones):
        c = local((0.0, 0.0), yaw, x0 + n * length / 2, 0.0)
        for i in range(n):
            mc = local((0.0, 0.0), yaw, x0 + length * (i + 0.5), 0.0)
            put(f"{prefix}_grate", mc, yaw)
            put(f"{prefix}_ceil", mc, yaw)
            for side in (0.0, 180.0):
                t = tones[(i + (side > 0)) % len(tones)]
                put(f"{prefix}_gutter", mc, yaw + side)
                put(f"{prefix}_wall_low{t}", mc, yaw + side)
                put(f"{prefix}_channel", mc, yaw + side)
                put(f"{prefix}_cables", mc, yaw + side)
                put(f"{prefix}_wall_up{t}", mc, yaw + side)
                for dx in (-0.3, 0.3):
                    put("clip_h", local(mc, yaw + side, dx, 0.0), yaw + side)
                put("floor_light", local(mc, yaw, 0.0, -1.075 if side == 0 else 1.075), yaw)
        return c

    for s, yaw in ((1, 0.0), (-1, 180.0)):
        c = passage("cor", S.COR_X0, S.N_MOD, S.MOD_L, yaw, ["_a", "_b"])
        put("cor_floor_base", c, yaw)
        for i in (1, 2, 3):  # no arch at 7.82: the socket spot (8, -1) stays clear
            p = local((0.0, 0.0), yaw, S.COR_X0 + S.MOD_L * i, 0.0)
            for pid in ("cor_arch", "arch_strip_l", "arch_strip_r"):
                put(pid, p, yaw)
    c = passage("mouth", S.COR_X0, 1, S.MOUTH_L, 90.0, [""])
    put("mouth_floor_base", c, 90.0)
    p = local((0.0, 0.0), 90.0, 4.6 - 0.09, 0.0)
    for pid in ("cor_arch", "arch_strip_l", "arch_strip_r"):
        put(pid, p, 90.0)

    # --- the tip rooms
    half_w = S.WIN_HALF / 8
    apo_w = S.R_TIP * math.cos(math.radians(half_w))
    tv = sorted(S.tip_vertices())
    wall_v = [a for a in tv if abs(a) > S.WIN_HALF + 1e-6]
    step = (180.0 - S.DOOR_HALF - S.WIN_HALF) / 3
    for s, room in ((1, 0.0), (-1, 180.0)):
        c = (s * S.TIP_X, 0.0)
        for pid in ("tip_floor_base", "tip_floor_disc", "tip_floor_rim", "tip_window_frame", "tip_glass",
                    "tip_ceiling", "tip_lamp_ring"):
            put(pid, list(c), room)
        for k in range(8):
            put("tip_grate", polar(1.2, 22.5 + 45 * k, c, room), room - (22.5 + 45 * k))
            put("tip_spoke", polar(1.2, 45 * k, c, room), room - 45 * k)
            put("tip_light", polar(1.22, 45 * k, c, room), room - 45 * k)
            a = -S.WIN_HALF + half_w * (2 * k + 1)
            put("tip_sill_strip", polar(apo_w, a, c, room), room - a)
        for k in range(6):
            put("tip_lamp", polar(S.R_TIP_RING, 30 + 60 * k, c, room), room - (30 + 60 * k))
        i = 0
        for sign in (1, -1):
            for j in range(3):
                a = sign * (S.WIN_HALF + step * (j + 0.5))
                put("tip_panel_a" if i % 2 else "tip_panel_b", polar(S.R_TIP * math.cos(math.radians(step / 2)), a,
                                                                      c, room), room - a)
                i += 1
        for a in tv:
            put("tip_rib", polar(S.R_TIP, a, c, room), room - a)
            put("tip_rib_strip", polar(S.R_TIP, a, c, room), room - a)
        for a in [-S.WIN_HALF, S.WIN_HALF] + wall_v:
            if abs(abs(a) - S.WIN_HALF) < 1e-6 or abs(abs(a) - (180 - S.DOOR_HALF)) < 1e-6:
                put("tip_pilaster", polar(S.R_TIP, a, c, room), room - a)
                put("tip_pilaster_strip", polar(S.R_TIP, a, c, room), room - a)
            else:  # the plain vertices: cable trunks, as the hall's
                put("tip_trunk", polar(S.R_TIP, a, c, room), room - a)
                put("tip_trunk_cables", polar(S.R_TIP, a, c, room), room - a)
                for h in (0.55, 1.3, 2.05):
                    put("trunk_clip", polar(S.R_TIP, a, c, room), room - a, h)
        p = polar(-S.TIP_CHORD, 180.0, c, room)
        for pid in ("tip_portal", "portal_strip_l", "portal_strip_r"):
            put(pid, p, room - 180.0)

    # --- details: a few crushed party cups, scratches on flat panels
    # (inside-3: three bigger cups where the party left them, two with a spill from the mouth, none near a station
    # spot; a coil of spare cable by the east corridor's south bay; two bolted repair plates on the hall's rim floor)
    for pid, xy, yaw in (("cup_a", [2.69, -1.2], 35.0), ("spill_a", [2.69, -1.2], 35.0),
                         ("cup_c", polar(2.98, -146.25), 200.0), ("spill_c", polar(2.98, -146.25), 200.0),
                         ("cup_b", [-6.6, 0.7], 80.0), ("cable_coil", [6.5, 0.72], 20.0),
                         ("floor_patch_a", polar(2.92, 140.0), -140.0 + 8.0), ("floor_patch_b", polar(2.92, -50.0), 50.0 - 5.0)):
        put(pid, xy, yaw)
    up = F + S.H_HALL - 0.9 + 0.2
    for pid, a in (("scratch_a", 33.75), ("scratch_b", 123.75), ("scratch_a", -56.25), ("scratch_b", -146.25)):
        put(pid, polar(S.R_HALL - 0.0302, a), -a, up)
    for pid, x, y in (("scratch_b", 5.9, -1.2148), ("scratch_a", -7.0, 1.2148), ("scratch_a", 7.2, 1.2148),
                      ("scratch_b", -4.2, -1.2148)):
        put(pid, [x, y], 90.0 if y < 0 else -90.0, F + 0.3)
    return out


def fmt(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, int):
        return str(v)
    return repr(round(float(v), 5))


def render() -> str:
    lines = ["# The INTERIOR lane's pieces and placements (art #263, docs/ship.md). GENERATED by",
             "# tools/blender/ship_interior_place.py from the numbers in tools/blender/ship_interior.py: edit those and",
             "# re-run it, never this file by hand. A piece is one GLB (<raw>/ship/v1/pieces/<id>.glb) built in its own",
             "# frame; a placement [piece, [x, y, h], yaw] puts it at plan (x, y), h an offset (the builders use absolute",
             "# heights), turned by yaw degrees about the vertical (Godot's rotation y; plan angle a -> a - yaw).",
             "", "place = ["]
    lines += [f'  ["{pid}", [{fmt(p[0])}, {fmt(p[1])}, {fmt(p[2])}], {fmt(yaw)}],' for pid, p, yaw in placements()]
    lines.append("]")
    for pid, (builder, args, collide) in PIECES.items():
        lines += ["", "[[pieces]]", f'id = "{pid}"', f'builder = "{builder}"', f"collide = {fmt(collide)}"]
        if args:
            lines.append("args = { " + ", ".join(f"{k} = {fmt(v)}" for k, v in args.items()) + " }")
    return "\n".join(lines) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        same = OUT.read_text(encoding="utf-8") == text
        print("interior.toml is current" if same else "interior.toml differs: re-run ship_interior_place.py")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(placements())} placements, {len(PIECES)} pieces)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
