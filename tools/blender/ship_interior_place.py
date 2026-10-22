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
REF_HALL = round(sum(S.R_GRATE) / 2, 3)    # inside-1: a hall grate sector's origin (v1 1.8)
R_TIP_DISC, R_TIP_GRATE0, REF_TIP = 0.55, 0.62, 1.07   # inside-1: the tip floor scaled to the 1.85 m room (v1 2.1)

# inside-fix: the breaker board's plain run on a corridor's front wall (u along the corridor's axis from the hall's
# centre): the spot's plain width + 0.1 a side
_SPOT = next(s["at"] for s in S._SHIP["stations"]["spot"] if s["room"] == "corridor_e")
_BOARD = _SPOT[0] * S.COR_DIR[0] + _SPOT[1] * S.COR_DIR[1]
BOARD_X = (round(_BOARD - S._SHIP["stations"]["plain_width_m"] / 2 - 0.1, 4),
           round(_BOARD + S._SHIP["stations"]["plain_width_m"] / 2 + 0.1, 4))
# v2: the corridors' cyan arches (u), 0.232 in from each portal, off the breaker board's span; rebuild A: three
# ceiling ribs evenly between them (inside-fix: v2 had two between 4.15 and 6.4)
ARCH_X = (round(S.COR_X0 + 0.232, 4), round(S.COR_X1 - 0.232, 4))
COR_RIBS = tuple(round(ARCH_X[0] + (ARCH_X[1] - ARCH_X[0]) * k / 4, 4) for k in (1, 2, 3))

# rebuild A: the hall's facets re-spaced round the diagonal corridors' openings (ship_interior.hall_segments): a
# piece per half angle (deg); "" the 16-gon's own (the openings' and the vents' sub-facets)
SEGS = S.hall_segments()
_E0 = S.COR_ANG - 2 * math.degrees(S.PHI)
PHI_STD = math.degrees(S.PHI)                                  # 11.25
PHI_SIDE = round((_E0 + 22.5) / 2, 4)                          # the facet between a vent and a corridor (12.87)
PHI_BACK = round(S.BACK_DEG / 2, 4)                            # a back facet (7.5)
PHI_SOCK = round((90.0 - S.BACK_DEG - (S.COR_ANG + 2 * PHI_STD)) / 2, 4)   # a socket's flat chord (13.39)


def facet_tag(a0: float, a1: float, kind: str) -> str:
    """A hall segment's piece suffix: "" for the 16-gon's own facets, "_side", "_back", "_socket"."""
    phi = (a1 - a0) / 2 if kind == "facet" else (a1 - a0) / 4
    for tag, ref in (("", PHI_STD), ("_side", PHI_SIDE), ("_back", PHI_BACK), ("_socket", PHI_SOCK / 2)):
        if abs(phi - ref) < 1e-3:
            return tag
    raise ValueError(f"hall segment {a0:.3f}..{a1:.3f} ({kind}): no piece for half angle {phi:.4f}")


def _hv(phi: float) -> tuple[float, float]:
    """(apothem, half width) of a hall facet or chord of half angle phi (deg), its vertices on HV."""
    return S.HV * math.cos(math.radians(phi)), S.HV * math.sin(math.radians(phi))

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
    "hall_amber_arc_thin": ("amber_arc", {"radius": S.R_ARC, "thin": True}, False),  # inside-fix: the four by the mouth
    "hall_flat_floor": ("hall_flat_floor", {}, True),   # inside-fix: the floor at a vent's or socket's flat chord
    "hall_flat_floor_socket": ("hall_flat_floor", {"phi_deg": PHI_SOCK}, True),
    "hall_threshold": ("hall_threshold", {}, True),
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
    # rebuild A: the re-spaced facets' wall panels, floor rims and ceiling panels
    **{f"hall_panel{tag}_{tone}": ("wall_panel", {"half": round(_hv(phi)[1], 5), "height": S.H_HALL, "tone": tone},
                                   True) for tag, phi in (("_side", PHI_SIDE), ("_back", PHI_BACK)) for tone in "ab"},
    **{f"hall_floor_rim{tag}": ("hall_floor_rim", {"phi_deg": phi}, True)
       for tag, phi in (("_side", PHI_SIDE), ("_back", PHI_BACK))},
    **{f"hall_ceil{tag}_{tone}": ("hall_ceil_panel", {"tone": tone, "phi_deg": phi}, False)
       for tag, phi in (("_side", PHI_SIDE), ("_back", PHI_BACK), ("_socket", round(PHI_SOCK / 2, 4)))
       for tone in "ab"},
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
    # inside-fix: a corridor's front wall in three runs, a cable bay either side of the breaker board's plain wall
    "cor_bay_in": ("cor_channel", {"length": BOARD_X[0] - S.COR_X0}, True),
    "cor_bay_in_cables": ("cor_cables", {"length": BOARD_X[0] - S.COR_X0}, False),
    "cor_wall_board": ("cor_wall_mid", {"length": BOARD_X[1] - BOARD_X[0]}, True),
    "cor_bay_out": ("cor_channel", {"length": S.COR_X1 - BOARD_X[1]}, True),
    "cor_bay_out_cables": ("cor_cables", {"length": S.COR_X1 - BOARD_X[1]}, False),
    "cor_ceil_rib": ("cor_ceil_rib", {}, False),        # inside-fix: the ceiling's ribs between the arches
    # inside-1: a plain 1.6 m centre panel between two narrow diamond panels (was one 3.1 m diamond)
    "hall_panel_flat": ("flat_panel", {"half": S.HCH, "height": S.H_HALL,
                                       "plain": S._SHIP["stations"]["plain_width_m"] / 2}, True),
    # rebuild A: a socket's flat chord, 1.89 m (the back between the corridor and the back facets): all plain
    "hall_panel_flat_socket": ("flat_panel", {"half": round(_hv(PHI_SOCK)[1], 5), "apo": round(_hv(PHI_SOCK)[0], 5),
                                              "height": S.H_HALL,
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
    "tip_trunk": ("trunk", {"height": S.H_TIP, "flat": True}, True),       # inside-fix: flat to the wall
    "tip_trunk_cables": ("trunk_cables", {"height": S.H_TIP, "flat": True}, False),
    "tip_trunk_clip": ("trunk_clip", {"flat": True}, False),
    "tip_portal": ("portal", {"half": S.TIP_CHORD_H, "height": S.H_TIP}, True),
    "tip_ceiling": ("tip_ceiling", {}, False),
}
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
    "tip_trunk": _V, "tip_trunk_cables": _V, "tip_trunk_clip": _V, "tip_pilaster": _V, "tip_pilaster_strip": _V,
    "cor_bay_in": [(S.COR_X0 - BOARD_X[0]) / 2, (BOARD_X[0] - S.COR_X0) / 2] + _BAY[2:],
    "cor_bay_in_cables": [(S.COR_X0 - BOARD_X[0]) / 2, (BOARD_X[0] - S.COR_X0) / 2] + _BAY[2:],
    "cor_bay_out": [(BOARD_X[1] - S.COR_X1) / 2, (S.COR_X1 - BOARD_X[1]) / 2] + _BAY[2:],
    "cor_bay_out_cables": [(BOARD_X[1] - S.COR_X1) / 2, (S.COR_X1 - BOARD_X[1]) / 2] + _BAY[2:],
    "cor_channel": _BAY, "cor_cables": _BAY, "clip_h": [-0.05, 0.05, -S.COR_HALF - 0.05, -S.COR_HALF + 0.35],
    "cor_arch": [-0.16, 0.16, -S.COR_HALF - 0.05, S.COR_HALF + 0.05],
    "arch_strip_l": [-0.16, 0.16, -S.COR_HALF - 0.05, S.COR_HALF + 0.05],
    "arch_strip_r": [-0.16, 0.16, -S.COR_HALF - 0.05, S.COR_HALF + 0.05],
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

    # --- the hall (rebuild A: hall_segments, the facets re-spaced round the diagonal corridors' openings)
    put("hall_floor_base", [0.0, 0.0])
    put("hall_floor_disc", [0.0, 0.0])
    put("hall_lamp_ring", [0.0, 0.0])
    mouth = S.OPENINGS["mouth"]
    for k in range(8):
        put("hall_grate", polar(REF_HALL, 22.5 + 45 * k), -(22.5 + 45 * k))
        put("hall_spoke", polar(REF_HALL, 45 * k), -45 * k)
        put("hall_lamp", polar(S.R_RING, 22.5 + 45 * k), -(22.5 + 45 * k))
    for a in [norm(11.25 + 22.5 * k) for k in range(16)]:   # the amber ring keeps the 16-gon's spacing
        near = abs(norm(a - mouth)) < 40   # inside-fix: thin by the mouth
        put("hall_amber_arc_thin" if near else "hall_amber_arc", polar(S.R_ARC, a), -a)
    claimed: set[float] = set()   # vertices a station's flat or an opening keeps free of a cable trunk
    edges: list[float] = []
    n_ceil = n_wall = 0
    for a0, a1, kind in SEGS:
        mid, tag = (a0 + a1) / 2, facet_tag(a0, a1, kind)
        subs = [(a0, mid), (mid, a1)] if kind != "facet" else [(a0, a1)]
        for b0, b1 in subs:   # the ceiling: one conical panel per (sub-)facet
            m = (b0 + b1) / 2
            put(f"hall_ceil{tag or '_panel'}_{'ab'[n_ceil % 2]}", polar(_hv((b1 - b0) / 2)[0], m), -m)
            n_ceil += 1
        if kind == "facet":
            apo = _hv((a1 - a0) / 2)[0]
            put(f"hall_floor_rim{tag}", polar(S.R_RIM_REF, mid), -mid)
            put("rim_bolts", polar(S.R_RIM_REF, mid), -mid)
            put(f"hall_panel{tag}_{'ab'[n_wall % 2]}", polar(apo, mid), -mid)
            n_wall += 1
        elif kind == "flat":   # v2: one flat panel over two facets at each vent and socket spot
            apo = _hv((a1 - a0) / 2)[0]
            put("hall_panel_flat" + tag, polar(apo, mid), -mid)
            put("hall_flat_floor" + tag, polar(apo, mid), -mid)   # inside-fix: its floor, where the player stands
            claimed |= {round(norm(a0), 4), round(norm(a1), 4)}
        else:
            pre = "mouth_" if abs(norm(mid - mouth)) < 1e-6 else ""
            put("hall_threshold", polar(S.HC, mid), -mid)
            put("mouth_portal" if pre else "hall_portal", polar(S.HC, mid), -mid)
            put(pre + "portal_strip_l", polar(S.HC, mid), -mid)
            put(pre + "portal_strip_r", polar(S.HC, mid), -mid)
            edges += [norm(a0), norm(a1)]
        if kind != "facet":
            claimed.add(round(norm(mid), 4))
    for v in S.hall_vertices():
        put("hall_rib", polar(S.HV, v), -v)
        put("hall_rib_strip", polar(S.HV, v), -v)
        if any(abs(norm(v - e)) < 1e-4 for e in edges):
            put("hall_pilaster", polar(S.HV, v), -v)
            put("hall_pilaster_strip", polar(S.HV, v), -v)
        elif round(norm(v), 4) not in claimed:   # hall_in-3's radial columns: cable trunks (the back's, at 90)
            put("hall_trunk", polar(S.HV, v), -v)
            put("hall_trunk_cables", polar(S.HV, v), -v)
            for h in (0.55, 1.25, 1.95, 2.65):
                put("trunk_clip", polar(S.HV, v), -v, h)

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
                if prefix == "cor" and wall[1] < mc[1]:
                    pass   # inside-fix: the front (north) wall's three runs, below
                else:
                    put(f"{prefix}_channel", mc, yaw + side)
                    put(f"{prefix}_cables", mc, yaw + side)
                    for dx in (-0.3, 0.3):
                        put("mouth_clip_h" if prefix == "mouth" else "clip_h", local(mc, yaw + side, dx, 0.0),
                            yaw + side)
                put("floor_light", local(mc, yaw, 0.0, -(half - 0.175) if side == 0 else half - 0.175), yaw)
        return c

    # rebuild A: the corridors along their diagonal axes (east at COR_ANG, west at 180 - COR_ANG); a front-wall piece
    # (its wall at local -y) turned by -COR_ANG in the east and +COR_ANG in the west (the east's mirror image)
    for s, yaw in ((1, -S.COR_ANG), (-1, S.COR_ANG - 180.0)):
        front = -S.COR_ANG if s > 0 else S.COR_ANG
        c = passage("cor", S.COR_X0, S.N_MOD, S.MOD_L, yaw, ["_a", "_b"])
        put("cor_floor_base", c, yaw)
        # inside-fix: the front wall (north side): bay, the board's plain wall, bay
        for pid, x0, x1, clips in (("cor_bay_in", S.COR_X0, BOARD_X[0], (-0.25, 0.25)),
                                   ("cor_wall_board", BOARD_X[0], BOARD_X[1], ()),
                                   ("cor_bay_out", BOARD_X[1], S.COR_X1, (-0.25, 0.25))):
            at = local((0.0, 0.0), yaw, (x0 + x1) / 2, 0.0)
            put(pid, at, front)
            if clips:
                put(pid + "_cables", at, front)
            for dx in clips:
                put("clip_h", local(at, front, dx, 0.0), front)
        for x in COR_RIBS:
            put("cor_ceil_rib", local((0.0, 0.0), yaw, x, 0.0), yaw)
        for x in ARCH_X:  # v2: off the breaker board's plain wall
            p = local((0.0, 0.0), yaw, x, 0.0)
            for pid in ("cor_arch", "arch_strip_l", "arch_strip_r"):
                put(pid, p, yaw)
    c = passage("mouth", S.COR_X0, 1, S.MOUTH_L, 90.0, [""])
    put("mouth_floor_base", c, 90.0)
    p = local((0.0, 0.0), 90.0, 4.6 - 0.09, 0.0)
    for pid in ("mouth_arch", "mouth_arch_strip_l", "mouth_arch_strip_r"):
        put(pid, p, 90.0)

    # --- the tip rooms (rebuild A: at (+-8.3, 4.0), turned so the door faces the hall along the corridor's axis:
    # room yaw -COR_ANG east, 180 + COR_ANG west; no window, TIP_N wall facets round the outer side)
    tv = S.tip_vertices()
    door = 180.0 - S.DOOR_HALF
    for s, room in ((1, -S.COR_ANG), (-1, 180.0 + S.COR_ANG)):
        c = (s * S.TIP_C[0], S.TIP_C[1])
        for pid in ("tip_floor_base", "tip_floor_disc", "tip_floor_rim", "tip_ceiling", "tip_lamp_ring"):
            put(pid, list(c), room)
        for k in range(8):
            put("tip_grate", polar(REF_TIP, 22.5 + 45 * k, c, room), room - (22.5 + 45 * k))
            put("tip_spoke", polar(REF_TIP, 45 * k, c, room), room - 45 * k)
            put("tip_light", polar(REF_TIP + 0.01, 45 * k, c, room), room - 45 * k)
        for k in range(6):
            put("tip_lamp", polar(S.R_TIP_RING, 30 + 60 * k, c, room), room - (30 + 60 * k))
        apo = S.R_TIP * math.cos(math.radians(S.TIP_STEP / 2))
        for i, (a0, a1) in enumerate(zip(tv, tv[1:])):
            a = (a0 + a1) / 2
            put("tip_panel_a" if i % 2 else "tip_panel_b", polar(apo, a, c, room), room - a)
        for a in tv:
            put("tip_rib", polar(S.R_TIP, a, c, room), room - a)
            put("tip_rib_strip", polar(S.R_TIP, a, c, room), room - a)
            if abs(abs(a) - door) < 1e-6:
                put("tip_pilaster", polar(S.R_TIP, a, c, room), room - a)
                put("tip_pilaster_strip", polar(S.R_TIP, a, c, room), room - a)
            elif abs(a) > 70.0:  # the door's side: cable trunks, as the hall's; the outer side (the renewer's) plain
                put("tip_trunk", polar(S.R_TIP, a, c, room), room - a)
                put("tip_trunk_cables", polar(S.R_TIP, a, c, room), room - a)
                for h in (0.55, 1.3, 2.05):
                    put("tip_trunk_clip", polar(S.R_TIP, a, c, room), room - a, h)
        p = polar(-S.TIP_CHORD, 180.0, c, room)
        for pid in ("tip_portal", "portal_strip_l", "portal_strip_r"):
            put(pid, p, room - 180.0)

    # --- details: a few crushed party cups, scratches on flat panels
    # (inside-3: three bigger cups where the party left them, two with a spill from the mouth, none near a station
    # spot; a coil of spare cable by the east corridor's south bay; two bolted repair plates on the hall's rim floor)
    # inside 3-1: the two hall cups moved onto the grate ring in sight of both hall views (were by the wall)
    # polish 4: cup_a in the hall-out view's foreground (fov 52: its floor shows from y -2.9 on), cup_c in hall-in's
    # inside-fix: cup_a a little in from the threshold, on the grate inside the amber ring (was [0.75, -3.0])
    # rebuild A: the corridor's cup and coil at the same share of the longer corridors (u 7.37 and 7.11 of 3.92..8.02)
    def cor_pt(s, u, v):   # a point (u along, v across, +v south) in the east corridor's frame, or its west mirror
        x, y = local((0.0, 0.0), -S.COR_ANG, u, v)
        return [round(s * x, 4), y]
    for pid, xy, yaw in (("cup_a", [0.85, -2.82], 145.0), ("spill_a", [0.85, -2.82], 145.0),
                         ("cup_c", [-1.05, -0.45], 200.0), ("spill_c", [-1.05, -0.45], 200.0),
                         ("cup_b", cor_pt(-1, 7.37, 0.95), 80.0 + S.COR_ANG),
                         ("cable_coil", cor_pt(1, 7.11, 1.0), 20.0 - S.COR_ANG),
                         ("floor_patch_a", polar(S.R_RIM_REF - 0.08, 96.0), -96.0 + 8.0),   # rebuild A: 112.5 is a socket flat now
                         ("floor_patch_b", polar(S.R_RIM_REF - 0.08, -62.0), 62.0 - 5.0)):
        put(pid, xy, yaw)
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
             "# re-run it, never this file by hand. A piece is one GLB (<raw>/ship/v2/pieces/<id>.glb) built in its own",
             "# frame; a placement [piece, [x, y, h], yaw] puts it at plan (x, y), h an offset (the builders use absolute",
             "# heights), turned by yaw degrees about the vertical (Godot's rotation y; plan angle a -> a - yaw).",
             "", "place = ["]
    lines += [f'  ["{pid}", [{fmt(p[0])}, {fmt(p[1])}, {fmt(p[2])}], {fmt(yaw)}],' for pid, p, yaw in placements()]
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
