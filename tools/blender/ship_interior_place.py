"""Writes layouts/ship/interior.toml, the INTERIOR lane's pieces and placements (art #263, docs/ship.md), from the
numbers in ship_interior.py. Plain Python (no Blender):

    $PYTHON_BIN tools/blender/ship_interior_place.py [--check]

--check: exit 1 when the committed file differs from what this script writes (the fast test runs it).
A placement is [piece, [x, y, h], yaw]: a piece built at plan angle 0 and standing at angle a gets yaw -a; inside a tip
room turned by r the yaw is r - a (the west room is the east one turned 180)."""

from __future__ import annotations

import math
import os
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
REF_HALL = round(sum(S.R_GRATE) / 2, 3)    # inside-1: a hall grate sector's origin (v1 1.8)
R_TIP_DISC, R_TIP_GRATE0, REF_TIP = 0.55, 0.62, 1.07   # inside-1: the tip floor scaled to the 1.85 m room (v1 2.1)

# id: (builder, args, collide)
PIECES: dict[str, tuple[str, dict, bool]] = {
    # the hall
    "hall_floor_base": ("hall_floor_base", {}, True),
    "hall_floor_disc": ("floor_disc", {"radius": S.R_DISC, "grate": True}, True),  # polish 4: the lit grating disc
    "hall_grate": ("radial_grate", {"r0": S.R_GRATE[0], "r1": S.R_GRATE[1], "half_deg": 22.5 - SPOKE_HALL,
                                    "ref": REF_HALL}, True),
    "hall_spoke": ("spoke", {"r0": S.R_GRATE[0] - 0.03, "r1": S.R_GRATE[1] + 0.03, "half_deg": SPOKE_HALL,
                             "ref": REF_HALL}, True),
    "hall_amber_arc": ("amber_arc", {"radius": S.R_ARC}, False),
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
    "mouth_clip_h": ("clip_h", {"prof": "mouth"}, False),
    "cor_wall_mid": ("cor_wall_mid", {"length": S.MOD_L}, True),     # v2: the plain wall at a breaker board's spot
    # inside-1: a plain 1.6 m centre panel between two narrow diamond panels (was one 3.1 m diamond)
    "hall_panel_flat": ("flat_panel", {"half": S.HCH, "height": S.H_HALL,
                                       "plain": S._SHIP["stations"]["plain_width_m"] / 2}, True),
    "cor_wall_up_a": ("cor_wall_up", {"length": S.MOD_L, "tone": "a"}, True),
    "cor_wall_up_b": ("cor_wall_up", {"length": S.MOD_L, "tone": "b"}, True),
    "cor_ceil": ("cor_ceil", {"length": S.MOD_L}, False),
    "cor_arch": ("cor_arch", {}, True),
    "arch_strip_l": ("cor_arch_strip", {"side": -1}, False),
    "arch_strip_r": ("cor_arch_strip", {"side": 1}, False),
    "mouth_floor_base": ("cor_floor_base", {"prof": "mouth", "length": S.MOUTH_L}, True),
    "mouth_grate": ("cor_grate", {"length": S.MOUTH_L}, True),
    "mouth_gutter": ("cor_gutter", {"prof": "mouth", "length": S.MOUTH_L}, True),
    "mouth_wall_low": ("cor_wall_low", {"prof": "mouth", "length": S.MOUTH_L, "tone": "a"}, True),
    "mouth_channel": ("cor_channel", {"prof": "mouth", "length": S.MOUTH_L}, True),
    "mouth_cables": ("cor_cables", {"prof": "mouth", "length": S.MOUTH_L}, False),
    "mouth_wall_up": ("cor_wall_up", {"length": S.MOUTH_L, "tone": "a", "prof": "mouth"}, True),
    "mouth_ceil": ("cor_ceil", {"length": S.MOUTH_L, "prof": "mouth"}, False),
    # inside 3-1: the mouth's own wide portal and arch (S.MOUTH_PROF: hall_out-2's opening)
    "mouth_portal": ("portal", {"half": S.HCH, "height": S.H_HALL, "soffit": True, "prof": "mouth"}, True),
    "mouth_portal_strip_l": ("portal_strip", {"side": -1, "prof": "mouth"}, False),
    "mouth_portal_strip_r": ("portal_strip", {"side": 1, "prof": "mouth"}, False),
    "mouth_arch": ("cor_arch", {"prof": "mouth", "inset": 0.08}, True),  # polish 4: thin, the opening wide
    "mouth_arch_strip_l": ("cor_arch_strip", {"side": -1, "prof": "mouth", "inset": 0.08}, False),
    "mouth_arch_strip_r": ("cor_arch_strip", {"side": 1, "prof": "mouth", "inset": 0.08}, False),
    # the tip rooms
    "tip_floor_base": ("tip_floor_base", {}, True),
    "tip_floor_disc": ("floor_disc", {"radius": R_TIP_DISC}, True),
    "tip_grate": ("radial_grate", {"r0": R_TIP_GRATE0, "r1": S.R_TIP - 0.33, "half_deg": 22.5 - SPOKE_TIP,
                                   "ref": REF_TIP}, True),
    "tip_spoke": ("spoke", {"r0": R_TIP_GRATE0 - 0.02, "r1": S.R_TIP - 0.29, "half_deg": SPOKE_TIP, "ref": REF_TIP},
                  True),
    "tip_light": ("floor_light", {"length": 0.72}, False),
    "tip_floor_rim": ("tip_floor_rim", {}, True),
    "tip_panel_a": ("wall_panel", {"half": S.R_TIP * math.sin(math.radians(S.TIP_STEP / 2)), "height": S.H_TIP, "tone": "a"},
                    True),
    "tip_panel_b": ("wall_panel", {"half": S.R_TIP * math.sin(math.radians(S.TIP_STEP / 2)), "height": S.H_TIP, "tone": "b"},
                    True),
    "tip_pilaster": ("pilaster", {"height": S.H_TIP}, True),
    "tip_pilaster_strip": ("pilaster_strip", {"height": S.H_TIP}, False),
    "tip_trunk": ("trunk", {"height": S.H_TIP}, True),
    "tip_trunk_cables": ("trunk_cables", {"height": S.H_TIP}, False),
    "tip_window_frame": ("tip_window_frame", {}, True),
    # inside 3-2: the window's well out to the lens's slanted band and the glass in the band, one per side (the lens
    # is not symmetric about the room's axis: the swept tip's rear side reaches farther)
    "tip_well_e": ("tip_well", {"side": 1}, False),
    "tip_well_w": ("tip_well", {"side": -1}, False),
    "tip_sill_strip": ("tip_sill_strip", {}, False),
    "tip_portal": ("portal", {"half": S.TIP_CHORD_H, "height": S.H_TIP}, True),
    "tip_ceiling": ("tip_ceiling", {}, False),
    # inside-1: the window's shutter (one panel per segment, dropped into the low wall when open), guides, button
    "tip_shutter": ("shutter_panel", {}, False),
    "tip_shutter_track": ("shutter_track", {}, False),
    "tip_shutter_button": ("shutter_button", {}, False),
}
# inside-2's tone grid (SHIP_SHUTTER_GRID=1, never committed): the east room's closed panels in four tones, two
# segments each (tones a..d of ship_interior.SHUTTER_TONES, north to south); the west room keeps SHUTTER_TONE
GRID = os.environ.get("SHIP_SHUTTER_GRID") == "1"
if GRID:
    PIECES.update({f"tip_shutter_t{t}": ("shutter_panel", {"tone": t}, False) for t in "abcd"})
PIECES |= {
    "tip_rib": ("rib", {"rv": S.R_TIP, "rim": F + S.H_TIP, "r_in": S.R_TIP_RING, "h_in": H_IN_TIP}, False),
    "tip_rib_strip": ("rib", {"rv": S.R_TIP, "rim": F + S.H_TIP, "r_in": S.R_TIP_RING, "h_in": H_IN_TIP,
                              "strip": True}, False),
    "tip_lamp_ring": ("lamp_ring", {"radius": S.R_TIP_RING, "h_in": H_IN_TIP}, False),
    "tip_lamp": ("lamp", {"h_in": H_IN_TIP}, False),
    # details
    "cup_a": ("cup", {"seed": 3, "scale": 1.8}, False),  # polish 4: 1.8 (22 cm; inside 3-1: 1.5 read as a red mark)
    "cup_b": ("cup", {"seed": 11, "scale": 1.8}, False),
    "cup_c": ("cup", {"seed": 27, "scale": 1.8}, False),
    "spill_a": ("spill", {"seed": 4, "from": 0.2, "size": 2.2}, False),
    "spill_c": ("spill", {"seed": 8, "from": 0.2, "size": 2.0}, False),
    "cable_coil": ("cable_coil", {}, False),
    "floor_patch_a": ("floor_patch", {"u": 0.42, "v": 0.36}, False),
    "floor_patch_b": ("floor_patch", {"u": 0.36, "v": 0.3}, False),
    "rim_bolts": ("rim_bolts", {}, False),
}
# v2: the plan box [x0, x1, y0, y1] in its own frame of every piece that stands out from a wall: `ship --check` keeps
# them off the station spots' plain panels (layouts/ship/ship.toml [stations])
_V = [-0.2, 0.2, -0.2, 0.2]
_BAY = [-S.MOD_L / 2, S.MOD_L / 2, -S.COR_HALF - 0.05, -S.COR_HALF + 0.35]
FOOT: dict[str, list[float]] = {
    "hall_trunk": _V, "hall_trunk_cables": _V, "trunk_clip": _V, "hall_pilaster": _V, "hall_pilaster_strip": _V,
    "tip_trunk": _V, "tip_trunk_cables": _V, "tip_pilaster": _V, "tip_pilaster_strip": _V,
    "cor_channel": _BAY, "cor_cables": _BAY, "clip_h": [-0.05, 0.05, -S.COR_HALF - 0.05, -S.COR_HALF + 0.35],
    "cor_arch": [-0.16, 0.16, -S.COR_HALF - 0.05, S.COR_HALF + 0.05],
    "arch_strip_l": [-0.16, 0.16, -S.COR_HALF - 0.05, S.COR_HALF + 0.05],
    "arch_strip_r": [-0.16, 0.16, -S.COR_HALF - 0.05, S.COR_HALF + 0.05],
}
# v2: the breaker boards' plain wall: no cable bay over [x - half, x + half] on a corridor's front wall (y < 0)
BREAKERS = [(s["at"][0], S._SHIP["stations"]["plain_width_m"] / 2 + 0.1) for s in S._SHIP["stations"]["spot"]
            if s["room"].startswith("corridor")]
# v2: the corridors' cyan arches (plan |x|), off the breaker boards' span 4.35..6.15
ARCH_X = (4.15, 6.4)


def polar(r: float, a: float, c=(0.0, 0.0), room: float = 0.0) -> list[float]:
    t = math.radians(a - room)
    return [round(c[0] + r * math.cos(t), 4), round(c[1] + r * math.sin(t), 4)]


def local(c, yaw: float, x: float, y: float) -> list[float]:
    t = math.radians(-yaw)
    return [round(c[0] + x * math.cos(t) - y * math.sin(t), 4), round(c[1] + x * math.sin(t) + y * math.cos(t), 4)]


def norm(yaw: float) -> float:
    return round((yaw + 180.0) % 360.0 - 180.0, 3)


def shutter(c, room: float, pose: str) -> list[tuple[str, list[float], float]]:
    """A tip room's shutter panels (centre c, room yaw), open (lowered into the low wall) or closed."""
    half = S.WIN_HALF / 8
    apo = S.R_TIP * math.cos(math.radians(half))
    h = -S.SHUTTER_DROP if pose == "open" else 0.0
    out = []
    for i in range(8):
        a = -S.WIN_HALF + half * (2 * i + 1)
        xy = polar(apo + S.SHUTTER_W, a, c, room)
        pid = f"tip_shutter_t{'abcd'[i // 2]}" if GRID and pose == "closed" and room == 0.0 else "tip_shutter"
        out.append((pid, [xy[0], xy[1], round(h, 4)], norm(room - a)))
    return out


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
    flats = S.FLATS
    flat_f = [a for a in facets if any(abs(((a - f + 180) % 360) - 180) < 12 for f in flats)]
    walls = [a for a in facets if a not in door and a not in flat_f]
    verts = [((22.5 * k + 180) % 360) - 180 for k in range(16)]
    edge = [v for v in verts if any(abs(abs(((v - o + 180) % 360) - 180) - 22.5) < 1 for o in openings)]
    plain = [v for v in verts if v not in edge and all(abs(((v - o + 180) % 360) - 180) > 1 for o in openings + flats)]
    for k in range(8):
        put("hall_grate", polar(REF_HALL, 22.5 + 45 * k), -(22.5 + 45 * k))
        put("hall_spoke", polar(REF_HALL, 45 * k), -45 * k)
        put("hall_lamp", polar(S.R_RING, 22.5 + 45 * k), -(22.5 + 45 * k))
    for i, a in enumerate(facets):
        put("hall_amber_arc", polar(S.R_ARC, a), -a)
        put("hall_ceil_panel_a" if i % 2 else "hall_ceil_panel_b", polar(S.R_HALL, a), -a)
    for i, a in enumerate(walls):
        put("hall_floor_rim", polar(S.R_RIM_REF, a), -a)
        put("rim_bolts", polar(S.R_RIM_REF, a), -a)
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
    for f in flats:  # v2: one flat panel over two facets at each vent and socket spot
        put("hall_panel_flat", polar(S.HC, f), -f)
    for o in openings:
        pre = "mouth_" if o == S.OPENINGS["mouth"] else ""
        put("hall_threshold", polar(S.HC, o), -o)
        put("mouth_portal" if pre else "hall_portal", polar(S.HC, o), -o)
        put(pre + "portal_strip_l", polar(S.HC, o), -o)
        put(pre + "portal_strip_r", polar(S.HC, o), -o)

    # --- a passage: modules along its axis (yaw: its outward direction a gives yaw -a)
    def passage(prefix, x0, n, length, yaw, tones):
        c = local((0.0, 0.0), yaw, x0 + n * length / 2, 0.0)
        for i in range(n):
            mc = local((0.0, 0.0), yaw, x0 + length * (i + 0.5), 0.0)
            put(f"{prefix}_grate", mc, yaw)
            put(f"{prefix}_ceil", mc, yaw)
            half = S.MOUTH_HALF if prefix == "mouth" else S.COR_HALF
            for side in (0.0, 180.0):
                t = tones[(i + (side > 0)) % len(tones)]
                put(f"{prefix}_gutter", mc, yaw + side)
                put(f"{prefix}_wall_low{t}", mc, yaw + side)
                put(f"{prefix}_wall_up{t}", mc, yaw + side)
                wall = local(mc, yaw + side, 0.0, -half)
                if prefix == "cor" and wall[1] < 0 and any(abs(abs(wall[0]) - bx) < bh + length / 2
                                                           for bx, bh in ((abs(x), h) for x, h in BREAKERS)):
                    put("cor_wall_mid", mc, yaw + side)  # v2: a breaker board's plain wall, no cable bay
                else:
                    put(f"{prefix}_channel", mc, yaw + side)
                    put(f"{prefix}_cables", mc, yaw + side)
                    for dx in (-0.3, 0.3):
                        put("mouth_clip_h" if prefix == "mouth" else "clip_h", local(mc, yaw + side, dx, 0.0),
                            yaw + side)
                put("floor_light", local(mc, yaw, 0.0, -(half - 0.175) if side == 0 else half - 0.175), yaw)
        return c

    for s, yaw in ((1, 0.0), (-1, 180.0)):
        c = passage("cor", S.COR_X0, S.N_MOD, S.MOD_L, yaw, ["_a", "_b"])
        put("cor_floor_base", c, yaw)
        for x in ARCH_X:  # v2: off the breaker board's plain wall
            p = local((0.0, 0.0), yaw, x, 0.0)
            for pid in ("cor_arch", "arch_strip_l", "arch_strip_r"):
                put(pid, p, yaw)
    c = passage("mouth", S.COR_X0, 1, S.MOUTH_L, 90.0, [""])
    put("mouth_floor_base", c, 90.0)
    p = local((0.0, 0.0), 90.0, 4.6 - 0.09, 0.0)
    for pid in ("mouth_arch", "mouth_arch_strip_l", "mouth_arch_strip_r"):
        put(pid, p, 90.0)

    # --- the tip rooms
    half_w = S.WIN_HALF / 8
    apo_w = S.R_TIP * math.cos(math.radians(half_w))
    tv = sorted(S.tip_vertices())
    wall_v = [a for a in tv if abs(a) > S.WIN_HALF + 1e-6]
    step = (180.0 - S.DOOR_HALF - S.WIN_HALF) / 3
    for s, room in ((1, 0.0), (-1, 180.0)):
        c = (s * S.TIP_X, 0.0)
        for pid in ("tip_floor_base", "tip_floor_disc", "tip_floor_rim", "tip_window_frame", "tip_shutter_track",
                    "tip_ceiling", "tip_lamp_ring"):
            put(pid, list(c), room)
        # polish 4: one glass, the hull's tip window (the well's own pane doubled it: dim and tinted)
        put(f"tip_well_{'e' if s > 0 else 'w'}", list(c), room)
        for k in range(8):
            put("tip_grate", polar(REF_TIP, 22.5 + 45 * k, c, room), room - (22.5 + 45 * k))
            put("tip_spoke", polar(REF_TIP, 45 * k, c, room), room - 45 * k)
            put("tip_light", polar(REF_TIP + 0.01, 45 * k, c, room), room - 45 * k)
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
        # inside-1: the shutter's button on the first wall facet north of the window (the mouth's side), 14 cm in
        # from the window's pilaster on the facet's flat corner plate (off the renewer's 1.6 m band)
        a = -S.WIN_HALF - step / 2 if s > 0 else S.WIN_HALF + step / 2
        put("tip_shutter_button", local(polar(S.R_TIP * math.cos(math.radians(step / 2)), a, c, room), room - a,
                                        0.0, 0.14 if a < 0 else -0.14), room - a)
        out.extend(shutter(c, room, "open"))

    # --- details: a few crushed party cups, scratches on flat panels
    # (inside-3: three bigger cups where the party left them, two with a spill from the mouth, none near a station
    # spot; a coil of spare cable by the east corridor's south bay; two bolted repair plates on the hall's rim floor)
    # inside 3-1: the two hall cups moved onto the grate ring in sight of both hall views (were by the wall)
    # polish 4: cup_a in the hall-out view's foreground (fov 52: its floor shows from y -2.9 on), cup_c in hall-in's
    for pid, xy, yaw in (("cup_a", [0.75, -3.0], 145.0), ("spill_a", [0.75, -3.0], 145.0),
                         ("cup_c", [-1.05, -0.45], 200.0), ("spill_c", [-1.05, -0.45], 200.0),
                         ("cup_b", [-6.6, 0.95], 80.0), ("cable_coil", [6.4, 1.0], 20.0),
                         ("floor_patch_a", polar(S.R_RIM_REF - 0.08, 112.5), -112.5 + 8.0),
                         ("floor_patch_b", polar(S.R_RIM_REF - 0.08, -62.0), 62.0 - 5.0)):
        put(pid, xy, yaw)
    # inside-1: a cup left on the east window's sill, on the window's last north segment (off the renewer's band)
    a = -S.WIN_HALF + S.WIN_HALF / 8
    put("cup_b", polar(S.R_TIP * math.cos(math.radians(S.WIN_HALF / 8)) - 0.1, a, (S.TIP_X, 0.0)), 30.0 - a, S.SILL)
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
    lines += ["", "# inside-1: the tip windows' shutters CLOSED (`ship --shutters closed` swaps these rows for the",
              "# tip_shutter rows of `place`, the open pose): the same panels, raised from the low wall over the glass",
              "shutter_closed = ["]
    for s, room in ((1, 0.0), (-1, 180.0)):
        lines += [f'  ["{pid}", [{fmt(p[0])}, {fmt(p[1])}, {fmt(p[2])}], {fmt(yaw)}],'
                  for pid, p, yaw in shutter((s * S.TIP_X, 0.0), room, "closed")]
    lines.append("]")
    for pid, (builder, args, collide) in PIECES.items():
        lines += ["", "[[pieces]]", f'id = "{pid}"', f'builder = "{builder}"', f"collide = {fmt(collide)}"]
        if args:
            lines.append("args = { " + ", ".join(f"{k} = {fmt(v)}" for k, v in args.items()) + " }")
        if pid in FOOT:
            lines.append("foot = [" + ", ".join(fmt(v) for v in FOOT[pid]) + "]")
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
