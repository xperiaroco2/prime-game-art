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
import ship_interior_vent as V  # noqa: E402,F401
import ship_interior_throat as T_  # noqa: E402
import ship_interior_lens as LN  # noqa: E402
import ship_interior_workshop as WS  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "layouts" / "ship" / "interior.toml"
F = S.FLOOR
H_IN_HALL = F + S.H_HALL + (S.APEX_HALL - S.H_HALL) * (1 - S.R_RING / S.R_HALL)
SPOKE_HALL, SPOKE_TIP = 3.07, 4.1
REF_HALL = round(sum(S.R_GRATE) / 2, 3)    # inside-1: a hall grate sector's origin (v1 1.8)
R_TIP_DISC, R_TIP_GRATE0, REF_TIP = 0.55, 0.62, 1.07   # inside-1: the tip floor scaled to the 1.85 m room (v1 2.1)

# inside-fix: the breaker board's plain run on a corridor's front wall (u along the corridor's axis from the hall's
# centre): the spot's plain width + 0.1 a side
_SPOT = next(s["at"] for s in S._SHIP["stations"]["spot"] if s["room"] == "corridor_e")
_BOARD = (_SPOT[0] - S.HALL_C[0]) * S.COR_DIR[0] + (_SPOT[1] - S.HALL_C[1]) * S.COR_DIR[1]
BOARD_X = (round(_BOARD - S._SHIP["stations"]["plain_width_m"] / 2 - 0.1, 4),
           round(_BOARD + S._SHIP["stations"]["plain_width_m"] / 2 + 0.1, 4))
# v2: the corridors' cyan arches (u), 0.232 in from each portal, off the breaker board's span; rebuild A: three
# ceiling ribs evenly between them (inside-fix: v2 had two between 4.15 and 6.4)
TIP_NARROW = 0.03                                      # step 6: the tip door's frame inside the corridor's walls
TIP_STRIP = (-0.0135, 0.0115)                          # its strip's offsets from the corridor's profile (the band's middle)
ARCH_X = (round(S.COR_X0 + 0.232, 4), round(S.COR_X1 - 0.232, 4))
COR_RIBS = tuple(round(ARCH_X[0] + (ARCH_X[1] - ARCH_X[0]) * k / 5, 4) for k in (1, 2, 3, 4))   # lens step 1: four

# rebuild A: the hall's facets re-spaced round the diagonal corridors' openings (ship_interior.hall_segments): a
# piece per half angle (deg); "" the 16-gon's own (the openings' and the vents' sub-facets)
SEGS = S.hall_segments()
_E0 = S.COR_ANG - 2 * math.degrees(S.PHI)
PHI_STD = math.degrees(S.PHI)                                  # 11.25
_E1 = S.COR_ANG + 2 * math.degrees(S.PHI)
PHI_SIDE = round((S.SOCK_A0 - _E1) / 2, 4)                     # lens step 1: the facet from the opening to the back flat (8.53)
PHI_SOCKF = round((_E0 - S.TH_CORNER) / 2, 4)                  # lens step 1: the front socket's flat chord (15.27)
PHI_THROAT = round((180.0 + 2 * S.TH_CORNER) / S.TH_SUBS / 2, 4)   # a throat sub-facet (11.40; rebuild D: was negative, the rims turned inside out)
# rebuild C: the throat's walls, from the mouth to the hall's corner, in modules; the vent's plain band. Rebuild E:
# five modules (the wall 0.6 m longer), so the roof line (ship.toml roof_y) falls on a module line
TH_N = 5
_TM, _TK = S.TH_PTS[1], S.TH_PTS[2]
TH_LEN = math.dist(_TM, _TK)                                   # 4.051
TH_MOD = TH_LEN / TH_N                                         # 0.810
TH_DIR = math.degrees(math.atan2(_TK[1] - _TM[1], _TK[0] - _TM[0]))   # 71.80: the east wall's direction
_VENT = next(s["at"] for s in S._SHIP["stations"]["spot"] if s["id"] == "vent_e")
_VS = math.dist(_TM, (_VENT[0] - S.HALL_C[0], _VENT[1] - S.HALL_C[1]))   # the vent along the wall (rebuild F: 2.430)
_PW = S._SHIP["stations"]["plain_width_m"] / 2
TH_PLAIN = [i for i in range(TH_N) if i * TH_MOD < _VS + _PW - 1e-6 and (i + 1) * TH_MOD > _VS - _PW + 1e-6]
TH_COVER = [i for i in range(TH_N) if _TM[1] + (_TK[1] - _TM[1]) * i / TH_N >= S.TH_ROOF - 1e-6]   # under the roof
PHI_BACK = round(S.BACK_DEG / 2, 4)                            # a back facet (6.25): the door's two sub-facets now
PHI_SOCK = round((90.0 - S.BACK_DEG - S.SOCK_A0) / 2, 4)       # the back socket's flat chord (14.64), as rebuild A built it


def facet_tag(a0: float, a1: float, kind: str) -> str:
    """A hall segment's piece suffix: "" for the 16-gon's own facets, "_side", "_back", "_socket", "_sockf"."""
    phi = (a1 - a0) / 2 if kind == "facet" else (a1 - a0) / 4
    if kind == "throat":
        return "_throat"
    for tag, ref in (("", PHI_STD), ("_side", PHI_SIDE), ("_back", PHI_BACK), ("_socket", PHI_SOCK / 2),
                     ("_sockf", PHI_SOCKF / 2)):
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
    "hall_flat_floor_socket": ("hall_flat_floor", {"phi_deg": PHI_SOCK}, True),
    "hall_flat_floor_sockf": ("hall_flat_floor", {"phi_deg": PHI_SOCKF}, True),
    # lens step 1: the vault's shut door on the back's flat chord, and the vault's shell behind it
    "hall_door": ("hall_door", {"half": round(_hv(2 * PHI_BACK)[1], 5), "apo": round(_hv(2 * PHI_BACK)[0], 5)}, True),
    "vault_shell": ("vault_shell", {}, True),
    "hall_threshold": ("hall_threshold", {}, True),
    # step 5: no hall pilasters (the corridor portals frame their own jambs, the throat's corners end in its frame)
    # lens step 1: no hall trunk (its last vertex, the back's at 90 deg, is the vault's door now)
    # step 5: the corridor portals' band 6 cm, inside the chord (it ran 4 cm into the next facet), its strip centred
    "hall_portal": ("portal", {"half": S.HCH, "height": S.H_HALL, "soffit": True,
                               "rim": round(S.HCH - S.COR_HALF - 0.002, 4), "bevel": 0.012}, True),
    "hall_portal_strip_l": ("portal_strip", {"side": -1, "at_in": 0.017, "at_out": 0.042}, False),
    "hall_portal_strip_r": ("portal_strip", {"side": 1, "at_in": 0.017, "at_out": 0.042}, False),
    "hall_ceil_panel_a": ("hall_ceil_panel", {"tone": "a"}, False),
    "hall_ceil_panel_b": ("hall_ceil_panel", {"tone": "b"}, False),
    # rebuild A: the re-spaced facets' wall panels, floor rims and ceiling panels
    **{f"hall_panel{tag}_{tone}": ("wall_panel", {"half": round(_hv(phi)[1], 5), "height": S.H_HALL, "tone": tone},
                                   True) for tag, phi in (("_side", PHI_SIDE),) for tone in "ab"},
    **{f"hall_floor_rim{tag}": ("hall_floor_rim", {"phi_deg": phi}, True)
       for tag, phi in (("_side", PHI_SIDE), ("_back", PHI_BACK), ("_throat", PHI_THROAT))},
    **{f"hall_ceil{tag}_{tone}": ("hall_ceil_panel", {"tone": tone, "phi_deg": phi}, False)
       for tag, phi in (("_side", PHI_SIDE), ("_back", PHI_BACK), ("_socket", round(PHI_SOCK / 2, 4)),
                        ("_sockf", round(PHI_SOCKF / 2, 4)),
                        ("_throat", PHI_THROAT)) for tone in "ab"},
    # rebuild C: the throat (its floor and ceiling in hall-relative plan coordinates; the walls in modules)
    "throat_floor": ("throat_floor", {}, True),
    "throat_ceil": ("throat_ceil", {}, True),
    # vents-b5: the pillow panels behind the vents again (b4's flat plates were for the recess, undone)
    # the clean throat (2026-10-29, ship_interior_throat.py): one frame to the ramp at the roof line (it replaces the
    # arch there) and one jamb at each hall corner (it replaces the hall pilasters there), both in hall-relative plan
    # coordinates
    "th_frame": ("th_frame", {}, False),
    "th_jambs": ("th_jambs", {}, True),
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
    "th_light": ("floor_light", {"length": 0.7, "mat": "int_amber_throat"}, False),   # the throat's (gill set step 2)
    "cor_wall_low_a": ("cor_wall_low", {"length": S.MOD_L, "tone": "a"}, True),
    "cor_wall_low_b": ("cor_wall_low", {"length": S.MOD_L, "tone": "b"}, True),
    "cor_channel": ("cor_channel", {"length": S.MOD_L}, True),
    "cor_cables": ("cor_cables", {"length": S.MOD_L}, False),
    "clip_h": ("clip_h", {}, False),
    # inside-fix: a corridor's front wall in three runs, a cable bay either side of the breaker board's plain wall
    "cor_bay_in": ("cor_channel", {"length": BOARD_X[0] - S.COR_X0}, True),
    "cor_bay_in_cables": ("cor_cables", {"length": BOARD_X[0] - S.COR_X0}, False),
    "cor_wall_board": ("cor_wall_mid", {"length": BOARD_X[1] - BOARD_X[0]}, True),
    "cor_bay_out": ("cor_channel", {"length": S.COR_X1 - BOARD_X[1]}, True),
    "cor_bay_out_cables": ("cor_cables", {"length": S.COR_X1 - BOARD_X[1]}, False),
    "cor_ceil_rib": ("cor_ceil_rib", {}, False),        # inside-fix: the ceiling's ribs between the arches
    # rebuild A: a socket's flat chord, 1.89 m (the back between the corridor and the back facets): all plain
    "hall_panel_flat_socket": ("flat_panel", {"half": round(_hv(PHI_SOCK)[1], 5), "apo": round(_hv(PHI_SOCK)[0], 5),
                                              "height": S.H_HALL,
                                              "plain": S._SHIP["stations"]["plain_width_m"] / 2}, True),
    # lens step 1: the front socket's flat chord from the throat's corner to the corridor's opening (2.15 m)
    "hall_panel_flat_sockf": ("flat_panel", {"half": round(_hv(PHI_SOCKF)[1], 5), "apo": round(_hv(PHI_SOCKF)[0], 5),
                                             "height": S.H_HALL, "plain": 0.86, "clad": "int_silver_c__clad"}, True),   # the spot 0.045 m off its middle;
    # step 6: clad in the throat's end-frame metal (flat, the station spot stays plain), a soft warm lamp on it (ship.toml)
    "cor_wall_up_a": ("cor_wall_up", {"length": S.MOD_L, "tone": "a"}, True),
    "cor_wall_up_b": ("cor_wall_up", {"length": S.MOD_L, "tone": "b"}, True),
    "cor_ceil": ("cor_ceil", {"length": S.MOD_L}, False),
    # inside 3-1: the mouth's own wide portal and arch (S.MOUTH_PROF: hall_out-2's opening)
    # the tip rooms
    "tip_floor_base": ("tip_floor_base", {}, True),
    "tip_floor_disc": ("floor_disc", {"radius": R_TIP_DISC, "mat": "int_plate__tip"}, True),  # polish n2: matte
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
    "tip_pilaster": ("pilaster", {"height": S.H_TIP_PORTAL}, True),        # lens step 1: up to the slanted ceiling
    "tip_pilaster_strip": ("pilaster_strip", {"height": S.H_TIP_PORTAL}, False),
    # lens step 1: the window band's facets (revived from v2's tip window: low wall, sill, header), glass, mullions
    "tip_window_a": ("tip_window", {"tone": "a"}, True),
    "tip_window_b": ("tip_window", {"tone": "b"}, True),
    "tip_glass": ("tip_glass", {}, False),
    "tip_mullion": ("tip_mullion", {}, True),
    "tip_sill_strip": ("tip_sill_strip", {}, False),
    # step 6 (the corridor-to-lens-room doors, as step 5's hall portals): no tip pilaster at the door, no arch beside
    # it; the door's chord leaves 3 cm past the corridor (TIP_CHORD_H 1.53), so its frame steps 3 cm into the opening
    # (`narrow`) for a 5.8 cm band that ends at the facets' vertex in a bevelled reveal, its strip centred on it
    "tip_portal": ("portal", {"half": S.TIP_CHORD_H, "height": S.H_TIP_PORTAL, "narrow": TIP_NARROW,
                              "rim": round(S.TIP_CHORD_H - S.COR_HALF - 0.002, 4), "bevel": 0.012}, True),
    "tip_portal_strip_l": ("portal_strip", {"side": -1, "at_in": TIP_STRIP[0], "at_out": TIP_STRIP[1]}, False),
    "tip_portal_strip_r": ("portal_strip", {"side": 1, "at_in": TIP_STRIP[0], "at_out": TIP_STRIP[1]}, False),
    # (step 6: cor_arch, arch_strip_l/_r and the old portal_strip_l/_r are no longer placed: dropped)
    "tip_ceiling": ("tip_ceiling", {}, False),
}
PIECES |= {
    # details
    "cup_b": ("cup", {"seed": 11, "scale": 1.8}, False),
    "cup_c": ("cup", {"seed": 27, "scale": 1.8}, False),
    "spill_c": ("spill", {"seed": 8, "from": 0.2, "size": 2.0}, False),
    "cable_coil": ("cable_coil", {}, False),
    "floor_patch_a": ("floor_patch", {"u": 0.42, "v": 0.36}, False),
    "floor_patch_b": ("floor_patch", {"u": 0.36, "v": 0.3}, False),
    "rim_bolts": ("rim_bolts", {}, False),
    # step 2, station 1: the throat vents (ship_interior_vent.py), each on its spot
    # the clean throat (2026-10-29, ship_interior_throat.py): each side's flat wall, cove and plinth (no slits and no
    # button this step: the gills (ship_interior_gills.py, th_gills) are parked for the hinged gill covers)
    "th_wall_e": ("th_wall", {"side": "e"}, True),
    "th_wall_w": ("th_wall", {"side": "w"}, True),
}
# lens room C, step 1 (ship_interior_lens.py): the charger's alcove and conduits in both lens rooms, the two facets
# beside it plain; the east room's lounge on its facets -109.77..+21.95 (their panels' relief above the sofa's spine,
# their windows' sill a flush 3 cm ledge, the spine the shelf), the table and the spine's lamp, speaker and plant
_TIP_HALF = S.R_TIP * math.sin(math.radians(S.TIP_STEP / 2))
PIECES |= {
    "tip_panel_plain": ("wall_panel", {"half": _TIP_HALF, "height": S.H_TIP, "tone": "a", "plain": True}, True),
    "tip_panel_low_a": ("wall_panel", {"half": _TIP_HALF, "height": S.H_TIP, "tone": "a", "v0": 0.92}, True),
    "tip_panel_low_b": ("wall_panel", {"half": _TIP_HALF, "height": S.H_TIP, "tone": "b", "v0": 0.92}, True),
    "tip_window_lounge_a": ("tip_window", {"tone": "a", "ledge": 0.03}, True),
    "tip_window_lounge_b": ("tip_window", {"tone": "b", "ledge": 0.03}, True),
    "tip_sill_strip_lounge": ("tip_sill_strip", {"ledge": 0.03}, False),
    "lens_alcove": ("lens_alcove", {}, True),
    "lens_conduits_e": ("lens_conduits", {"side": "e"}, False),
    "lens_conduits_w": ("lens_conduits", {"side": "w"}, False),
    "lounge_sofa_base": ("lounge_sofa_base", {}, True),        # the collider: the base only (the drawing)
    "lounge_sofa_fore": ("lounge_sofa", {"arm": -1}, False),
    "lounge_sofa_mid": ("lounge_sofa", {}, False),
    "lounge_sofa_mid_dark": ("lounge_sofa", {"tone": "dark"}, False),
    "lounge_sofa_aft": ("lounge_sofa", {"arm": 1}, False),
    "lounge_pillow_red": ("lounge_pillow", {"y": -0.1}, False),
    "lounge_pillow_dark": ("lounge_pillow", {"y": 0.08, "fabric": "lens_pillow_slate"}, False),   # step 4: slate
    "lounge_throw": ("lounge_throw", {}, False),   # step 4: c_lounge's folded charcoal throw
    "lounge_table": ("lounge_table", {}, True),
    "lounge_cans": ("lounge_cans", {}, False),
    "lounge_lamp": ("lounge_lamp", {}, False),
    "lounge_speaker": ("lounge_speaker", {}, False),
    "lounge_plant": ("lounge_plant", {}, False),
}
# the sofa's facets (indices into tip_vertices' pairs, the east room) and each one's module and pillow
SOFA_LO, SOFA_HI = LN.SOFA_K[0] * S.TIP_STEP, LN.SOFA_K[1] * S.TIP_STEP
SOFA_MODULES = {1: "lounge_sofa_fore", 2: "lounge_sofa_mid", 3: "lounge_sofa_mid_dark", 4: "lounge_sofa_mid",
                5: "lounge_sofa_mid", 6: "lounge_sofa_aft"}
SOFA_PILLOWS = {2: "lounge_pillow_red", 5: "lounge_pillow_dark"}
SOFA_THROWS = {4: "lounge_throw"}   # step 4
# the west room's workshop (ship_interior_workshop.py, docs/ship.md "The west lens room's workshop"): the bench's four
# (step 3: every bench module has one drawer pulled out, so the closed module ws_bench is no longer placed)
# facets (the lounge's wall pieces: the panels' relief over the top, a flush sill ledge) and the cabinet's two (plain
# window facets), both by the drawing's east angles (the west room's a_w = -a_e); its free items at their points
PIECES |= {
    "ws_bench_open_top": ("ws_bench", {"open": "top"}, True),
    "ws_bench_open_low": ("ws_bench", {"open": "low"}, True),
    "ws_drawer_eyes": ("ws_drawer", {"slot": "top", "fill": "eyes"}, False),
    "ws_drawer_limbs": ("ws_drawer", {"slot": "low", "fill": "limbs"}, False),
    "ws_drawer_parts_a": ("ws_drawer", {"slot": "low", "fill": "parts", "seed": 3}, False),
    "ws_drawer_parts_b": ("ws_drawer", {"slot": "top", "fill": "parts", "seed": 8}, False),
    "ws_cabinet": ("ws_cabinet", {}, True),
    "ws_cradle": ("ws_cradle", {}, False),
    "ws_sleeper_a": ("ws_sleeper", {"roll": 10.0, "yaw": 12.0}, False),
    "ws_sleeper_b": ("ws_sleeper", {"roll": -12.0, "yaw": -16.0}, False),
    "ws_robot_body": ("ws_robot_body", {}, True),   # the collider: the core and the shell band (the sphere Ø 60)
    "ws_robot": ("ws_robot", {}, False),
    "ws_hoist": ("ws_hoist", {}, False),
    "ws_rail": ("ws_rail", {}, False),
    "ws_lamp": ("ws_lamp", {}, False),
}
WS_LO, WS_MID, WS_HI = WS.BENCH_K[0] * S.TIP_STEP, WS.BENCH_K[1] * S.TIP_STEP, WS.CAB_K[1] * S.TIP_STEP
# step 2: a station piece's spot and its box [u0, u1, v0, v1, h0, h1] in the spot's frame (u along the wall, v out
# of it, h over the deck): `ship --check` holds it inside the spot's plain band, depth and the room's height
# the gills (2026-10-28): the vent cabinets are no longer placed (ship_interior_vent.py stays for the record)
UNITS: dict[str, tuple[str, list[float]]] = {}
# v2: the plan box [x0, x1, y0, y1] in its own frame of every piece that stands out from a wall: `ship --check` keeps
# them off the station spots' plain panels (layouts/ship/ship.toml [stations])
_V = [-0.2, 0.2, -0.2, 0.2]
_BAY = [-S.MOD_L / 2, S.MOD_L / 2, -S.COR_HALF - 0.05, -S.COR_HALF + 0.35]
FOOT: dict[str, list[float]] = {
    "hall_trunk": _V, "hall_trunk_cables": _V, "trunk_clip": _V,
    "tip_pilaster": _V, "tip_pilaster_strip": _V,
    "cor_bay_in": [(S.COR_X0 - BOARD_X[0]) / 2, (BOARD_X[0] - S.COR_X0) / 2] + _BAY[2:],
    "cor_bay_in_cables": [(S.COR_X0 - BOARD_X[0]) / 2, (BOARD_X[0] - S.COR_X0) / 2] + _BAY[2:],
    "cor_bay_out": [(BOARD_X[1] - S.COR_X1) / 2, (S.COR_X1 - BOARD_X[1]) / 2] + _BAY[2:],
    "cor_bay_out_cables": [(BOARD_X[1] - S.COR_X1) / 2, (S.COR_X1 - BOARD_X[1]) / 2] + _BAY[2:],
    "cor_channel": _BAY, "cor_cables": _BAY, "clip_h": [-0.05, 0.05, -S.COR_HALF - 0.05, -S.COR_HALF + 0.35],
}


# lens step 1: the renewer's angle round the east lens's centre in the room's frame (its vertex, 87.82 deg aft)
_REN = next(s["at"] for s in S._SHIP["stations"]["spot"] if s["id"] == "renewer_e")
RENEWER_DEG = math.degrees(math.atan2(_REN[1] - S._ROOM["tip_e"]["centre"][1], _REN[0] - S._ROOM["tip_e"]["centre"][0])) - S.COR_ANG


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

    def put(pid, xy, yaw=0.0, h=0.0):   # rebuild C: hall-relative xy, written at the hall's centre (0, -1)
        assert pid in PIECES, pid
        out.append((pid, [round(xy[0] + S.HALL_C[0], 4), round(xy[1] + S.HALL_C[1], 4), round(h, 4)], norm(yaw)))

    # --- the hall (rebuild A: hall_segments, the facets re-spaced round the diagonal corridors' openings)
    put("hall_floor_base", [0.0, 0.0])
    put("hall_floor_disc", [0.0, 0.0])
    put("hall_lamp_ring", [0.0, 0.0])
    put("throat_floor", [0.0, 0.0])
    put("throat_ceil", [0.0, 0.0])
    mouth = S.OPENINGS["mouth"]
    lows: set[float] = set()   # rebuild C: the throat's sub-facets' vertices (no cable trunk there)
    for k in range(8):
        put("hall_grate", polar(REF_HALL, 22.5 + 45 * k), -(22.5 + 45 * k))
        put("hall_spoke", polar(REF_HALL, 45 * k), -45 * k)
        put("hall_lamp", polar(S.R_RING, 22.5 + 45 * k), -(22.5 + 45 * k))
    for a in [norm(11.25 + 22.5 * k) for k in range(16)]:   # the amber ring keeps the 16-gon's spacing
        near = abs(norm(a - mouth)) < 40   # inside-fix: thin by the mouth
        put("hall_amber_arc_thin" if near else "hall_amber_arc", polar(S.R_ARC, a), -a)
    claimed: set[float] = set()   # vertices a station's flat or an opening keeps free of a cable trunk
    edges: list[float] = []
    cor_edges: list[float] = []   # step 5: the corridors' portals frame their own jambs (no pilaster beside them)
    n_ceil = n_wall = 0
    for a0, a1, kind in SEGS:
        mid, tag = (a0 + a1) / 2, facet_tag(a0, a1, kind)
        subs = [(a0, mid), (mid, a1)] if kind != "facet" else [(a0, a1)]
        if kind == "throat":
            subs = [(a0 + (a1 - a0) * i / S.TH_SUBS, a0 + (a1 - a0) * (i + 1) / S.TH_SUBS) for i in range(S.TH_SUBS)]
        if kind == "throat":
            lows |= {round(norm(b), 4) for b0, b1 in subs for b in (b0, b1)}
        for b0, b1 in subs:   # the ceiling: one conical panel per (sub-)facet
            m = (b0 + b1) / 2
            put(f"hall_ceil{tag or '_panel'}_{'ab'[n_ceil % 2]}", polar(_hv((b1 - b0) / 2)[0], m), -m)
            n_ceil += 1
        if kind == "throat":   # rebuild C: its floor's rim plates to the 16-gon; the throat's own pieces below
            for b0, b1 in subs:
                m = (b0 + b1) / 2
                put("hall_floor_rim_throat", polar(S.R_RIM_REF, m), -m)
            claimed |= lows
            continue
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
        elif kind == "door":   # lens step 1: the vault's shut door over the two back facets, their rim plates
            put("hall_door", polar(_hv((a1 - a0) / 2)[0], mid), -mid)
            for b0, b1 in subs:
                put("hall_floor_rim_back", polar(S.R_RIM_REF, (b0 + b1) / 2), -(b0 + b1) / 2)
            claimed |= {round(norm(a0), 4), round(norm(a1), 4)}
        else:
            pre = "mouth_" if abs(norm(mid - mouth)) < 1e-6 else ""
            put("hall_threshold", polar(S.HC, mid), -mid)
            put("mouth_portal" if pre else "hall_portal", polar(S.HC, mid), -mid)
            put((pre or "hall_") + "portal_strip_l", polar(S.HC, mid), -mid)
            put((pre or "hall_") + "portal_strip_r", polar(S.HC, mid), -mid)
            (edges if pre else cor_edges).extend([norm(a0), norm(a1)])
        if kind != "facet":
            claimed.add(round(norm(mid), 4))
    corners = {norm(S.TH_CORNER), norm(-180.0 - S.TH_CORNER)}   # the gills: norm's own rounding (the east had none)
    for v in S.hall_vertices():
        put("hall_rib", polar(S.HV, v), -v)
        put("hall_rib_strip", polar(S.HV, v), -v)
        if round(norm(v), 4) in corners:   # the throat's walls meet the hall here: its jamb (th_jambs), no pilaster
            pass
        elif any(abs(norm(v - e)) < 1e-4 for e in cor_edges):
            pass   # step 5 (his walk, shots 004-007): the pilaster doubled the portal's jamb and strip
        elif any(abs(norm(v - e)) < 1e-4 for e in edges):
            raise ValueError(f"a hall opening's edge at {v} has no frame")   # the mouth's are the throat's corners
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
        # (no cor_arch: step 5 dropped the one beside the hall's portal, step 6 the one beside the tip door's; the
        # corridor keeps its ceiling ribs, spaced on ARCH_X)
    # rebuild C: the throat's two slanted walls, four modules each from the mouth to the hall's corner (a piece's wall
    # at local -y, TH_HALF from its origin): plain where the vent hangs, a cable bay elsewhere, the chamfer under the
    # roof; amber floor lights along each wall
    for sx in (1, -1):
        mx, my = sx * _TM[0], _TM[1]
        d = (math.cos(math.radians(TH_DIR)), math.sin(math.radians(TH_DIR)))
        d = (sx * d[0], d[1])
        yaw = -TH_DIR if sx > 0 else TH_DIR   # local +x along the wall (east: mouth to hall; west: hall to mouth)
        if sx < 0:
            yaw = -(180.0 - TH_DIR) + 180.0
        inward = (-sx * math.sin(math.radians(TH_DIR)), math.cos(math.radians(TH_DIR)) * 1.0)
        inward = (-sx * d[1], sx * d[0]) if sx > 0 else (d[1], -d[0])
        for i in range(TH_N):
            s = TH_MOD * (i + 0.5)
            w = (mx + d[0] * s, my + d[1] * s)
            o = [round(w[0] + inward[0] * S.TH_HALF, 4), round(w[1] + inward[1] * S.TH_HALF, 4)]
            yw = -math.degrees(math.atan2(d[1], d[0])) if sx > 0 else -math.degrees(math.atan2(-d[1], -d[0]))
            tone = "ab"[(i + (sx < 0)) % 2]
            if i not in TH_COVER:   # rebuild E: forward of the roof line the wall is the hull's jamb (skin_cheeks)
                if i in (0, 3):
                    lp = [round(w[0] + d[0] * TH_MOD * 0.5 + inward[0] * 0.3, 4),
                          round(w[1] + d[1] * TH_MOD * 0.5 + inward[1] * 0.3, 4)]
                    put("th_light", lp, yw)
                continue
            # the clean throat: under the roof the wall is th_wall_<side>'s (placed once a side below), no modules
            if i in (0, 3):   # rebuild E: two a side, at 1/5 and 4/5 of the wall (the vent's 0.36 m shift went with it)
                sh = TH_MOD * 0.5
                lp = [round(w[0] + d[0] * sh + inward[0] * 0.3, 4), round(w[1] + d[1] * sh + inward[1] * 0.3, 4)]
                put("th_light", lp, yw)
        put("th_wall_" + ("e" if sx > 0 else "w"), [round(mx, 4), round(my, 4)], -sx * T_.WALL_YAW)

    put("th_frame", [0.0, 0.0])
    put("th_jambs", [0.0, 0.0])

    # --- the tip rooms (rebuild A: at (+-8.3, 4.0), turned so the door faces the hall along the corridor's axis:
    # room yaw -COR_ANG east, 180 + COR_ANG west; no window, TIP_N wall facets round the outer side)
    tv = S.tip_vertices()
    door = 180.0 - S.DOOR_HALF
    for s, room in ((1, -S.COR_ANG), (-1, 180.0 + S.COR_ANG)):
        c = (s * S.TIP_C[0], S.TIP_C[1])
        for pid in ("tip_floor_base", "tip_floor_disc", "tip_floor_rim", "tip_ceiling"):
            put(pid, list(c), room)
        # details 1: no lamp ring at the centre (the oculus): tip_ceiling's light ring; details 2: its lamps merged into it
        for k in range(8):
            put("tip_grate", polar(REF_TIP, 22.5 + 45 * k, c, room), room - (22.5 + 45 * k))
            put("tip_spoke", polar(REF_TIP, 45 * k, c, room), room - 45 * k)
            put("tip_light", polar(REF_TIP + 0.01, 45 * k, c, room), room - 45 * k)
        apo = S.R_TIP * math.cos(math.radians(S.TIP_STEP / 2))
        band = S.tip_band_facets(s)
        band_v = {round(v, 4) for i in band for v in (tv[i], tv[i + 1])}
        ends = {round(tv[band[0]], 4), round(tv[band[-1] + 1], 4)}
        for i, (a0, a1) in enumerate(zip(tv, tv[1:])):
            a = (a0 + a1) / 2
            lounge = s > 0 and SOFA_LO < a < SOFA_HI   # lens C: the east lounge's facets
            bench = s < 0 and WS_LO < -a < WS_MID       # the west workshop's bench facets (a_w = -a_e)
            cab = s < 0 and WS_MID < -a < WS_HI         # and its cabinet's
            lounge = lounge or bench                     # the bench takes the lounge's wall pieces
            if i in band:   # lens step 1: the window band (the west room's mirrored: + aft in both)
                put(("tip_window_lounge_" if lounge else "tip_window_") + ("a" if i % 2 else "b"),
                    polar(apo, a, c, room), room - a)
                put("tip_glass", polar(apo, a, c, room), room - a)
                put("tip_sill_strip_lounge" if lounge else "tip_sill_strip", polar(apo, a, c, room), room - a)
            elif abs(s * a - RENEWER_DEG) < S.TIP_STEP / 2 + 0.01:   # lens C: the two facets behind the alcove
                put("tip_panel_plain", polar(apo, a, c, room), room - a)
            else:
                put(("tip_panel_low_" if lounge else "tip_panel_") + ("a" if i % 2 else "b"),
                    polar(apo, a, c, room), room - a)
            if bench:
                slot = next((v for k, v in WS.OPEN.items() if abs(-a - k) < 0.5), None)
                put("ws_bench_open_" + slot[0] if slot else "ws_bench", polar(apo, a, c, room), room - a)
                if slot:
                    put("ws_drawer_" + slot[1], polar(apo, a, c, room), room - a)
            elif cab:
                put("ws_cabinet", polar(apo, a, c, room), room - a)
            elif lounge:
                put("lounge_sofa_base", polar(apo, a, c, room), room - a)
                put(SOFA_MODULES[i], polar(apo, a, c, room), room - a)
                if i in SOFA_PILLOWS:
                    put(SOFA_PILLOWS[i], polar(apo, a, c, room), room - a)
                if i in SOFA_THROWS:
                    put(SOFA_THROWS[i], polar(apo, a, c, room), room - a)
        for a in tv:
            v = round(a, 4)
            if abs(abs(a) - door) < 1e-6:
                pass   # step 6: the door's portal frames its own jambs (the pilaster doubled its jamb and strip)
            elif v in ends:
                put("tip_pilaster", polar(S.R_TIP, a, c, room), room - a)
                put("tip_pilaster_strip", polar(S.R_TIP, a, c, room), room - a)
            elif v in band_v:
                put("tip_mullion", polar(S.R_TIP, a, c, room), room - a)
            # (the door side's cable trunks went with the west workshop: its bench and cabinet took their last two
            # vertices, the east lounge and the alcoves the others)
        p = polar(-S.TIP_CHORD, 180.0, c, room)
        for pid in ("tip_portal", "tip_portal_strip_l", "tip_portal_strip_r"):
            put(pid, p, room - 180.0)
        # lens C: the charger's alcove on the renewer's vertex, its conduits; the east lounge's free pieces
        ren = s * RENEWER_DEG
        put("lens_alcove", polar(S.R_TIP, ren, c, room), room - ren)
        put("lens_conduits_" + ("e" if s > 0 else "w"), polar(S.R_TIP, ren, c, room), room - ren)
        if s > 0:
            for pid in ("lounge_table", "lounge_cans", "lounge_lamp", "lounge_speaker", "lounge_plant"):
                r, th, face = LN.item_polar("lounge_table" if pid == "lounge_cans" else pid)
                put(pid, polar(r, th, c, room), room - face)
        else:   # the west workshop's free items, in the west room's frame
            for pid, r, th, face in WS.ITEMS:
                put(pid, polar(r, th, c, room), room - face)

    # --- the vault (lens step 1): its shell behind the hall's back door (the door itself is a hall segment)
    put("vault_shell", [0.0, S._VAULT["y"][0] - S.HALL_C[1]])

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
    # the engineer's walk (2026-10-29, shot 009): the hall's spilled cup_a and its puddle removed
    for pid, xy, yaw in (("cup_c", [-1.05, -0.45], 200.0), ("spill_c", [-1.05, -0.45], 200.0),
                         ("cup_b", cor_pt(-1, 7.37, 0.95), 80.0 + S.COR_ANG),
                         ("cable_coil", cor_pt(1, 7.11, 1.0), 20.0 - S.COR_ANG),
                         ("floor_patch_a", polar(S.R_RIM_REF - 0.08, 96.0), -96.0 + 8.0),   # rebuild A: 112.5 is a socket flat now
                         ("floor_patch_b", polar(S.R_RIM_REF - 0.08, -62.0), 62.0 - 5.0)):
        put(pid, xy, yaw)

    # --- step 2: the stations on their spots (the piece's +v onto the spot's normal: plan angle 90 - yaw)
    spots = {s["id"]: s for s in S._SHIP["stations"]["spot"]}
    for pid, (spot, _unit) in UNITS.items():
        s = spots[spot]
        put(pid, [s["at"][0] - S.HALL_C[0], s["at"][1] - S.HALL_C[1]],
            90.0 - math.degrees(math.atan2(s["normal"][1], s["normal"][0])))
    return out


# rebuild F: the plan box [x0, x1, y0, y1] in its own frame of every PLAIN wall piece's face (a wall spot's plain
# band lies on it; the box reaches 0.25 m behind the face, for the round walls' chords): `ship --check` holds that
# plain pieces cover every wall spot's whole band (the vents stood half on the throat's hull jamb, rebuild E)
_FACE = 0.25
PLAIN: dict[str, list[float]] = {
    # the clean throat: the wall's face from the ramp frame to the hall jamb (its frame: x along the wall from the
    # mouth's corner, the face at y 0; the west mirrored), the station's 1.6 m band on it
    "th_wall_e": [T_.S_F0 + 0.01, T_.JAMB_U, -_FACE, 0.05],   # (the panel runs on behind the frame: vent_e's band
                                                              # starts at s 1.63, 4 cm under the frame's trim)
    "th_wall_w": [-T_.JAMB_U, -T_.S_F0 - 0.01, -_FACE, 0.05],
    "cor_wall_board": [-(BOARD_X[1] - BOARD_X[0]) / 2, (BOARD_X[1] - BOARD_X[0]) / 2, -S.COR_HALF - _FACE,
                       -S.COR_HALF + 0.05],
    **{pid: [-_FACE, _FACE, -PIECES[pid][1]["plain"], PIECES[pid][1]["plain"]]
       for pid in ("hall_panel_flat_socket", "hall_panel_flat_sockf")},
    **{f"tip_panel_{t}": [-_FACE, _FACE, -PIECES[f"tip_panel_{t}"][1]["half"], PIECES[f"tip_panel_{t}"][1]["half"]]
       for t in ("a", "b", "plain")},
}


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
        if pid in PLAIN:
            lines.append("plain = [" + ", ".join(fmt(v) for v in PLAIN[pid]) + "]")
        if pid in UNITS:
            lines += [f'spot = "{UNITS[pid][0]}"', "unit = [" + ", ".join(fmt(v) for v in UNITS[pid][1]) + "]"]
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
