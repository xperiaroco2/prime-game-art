"""The ship's INTERIOR pieces (art #263, docs/ship.md): the INTERIOR lane owns this file and ship_interior_*.py.

Each builder(args, layout) returns ship_lib parts in the piece's local frame (plan axes x east, y south, h up; metres;
heights absolute from the ground, so a placement's h is an offset). A placement [x, y, h] + yaw (layouts/ship/
interior.toml, written by ship_interior_place.py) moves it; yaw turns a plan angle a into a - yaw. Wall-like pieces are
built at plan angle 0 (their room toward -x) and placed with yaw = -(their angle).

The numbers (version 2, rebuilt for the hull variant J, art #263; heights from ship.toml: `floor_h`, each room's
`clear_h` and `apex_h`): the hall a 16-sided room, vertices on 4.078 (inner faces at about 4.0), rim 3.2 m, apex
3.8 m over the deck at h 0.6; three openings (mouth north, corridors on the diagonal at +-25.73 deg from east) two
facets wide, framed by portals on the chords (3.768); the vents' and sockets' plain flat chords; the other facets
re-spaced round the openings (hall_segments); the corridors one profile (3 m wide, vertical to 1.45 m, slanted in to
2.3 m wide at the 2.4 m ceiling) straight along the axis from the hall's centre to the tip room's, four modules of
1.026 m from the hall portal (u 3.918) to the tip portal (8.024); the tip rooms polygons on radius 1.85 round
(+-8.3, 4.0) turned to face the hall (13 wall facets, no window, the corridor chord over +-55.8 deg from the back),
rim 2.5 m, apex 2.8 m. docs/ship.md, "The interior kit", has the full table."""

from __future__ import annotations

import math
import tomllib
from pathlib import Path

import ship_interior_geom as G
import ship_lib as L

MODULES: list = []  # further interior modules the harness searches for builders

# --- the lane's materials (added to the shared library; ship_lib.material builds them) ------------------------------
L.MATERIALS.update({
    "int_silver_a": {"base": (0.66, 0.67, 0.69, 1.0), "metallic": 0.7, "roughness": 0.36},
    "int_silver_b": {"base": (0.55, 0.565, 0.59, 1.0), "metallic": 0.7, "roughness": 0.42},
    "int_silver_c": {"base": (0.38, 0.39, 0.41, 1.0), "metallic": 0.8, "roughness": 0.34},
    "int_dark": {"base": (0.035, 0.038, 0.042, 1.0), "metallic": 0.6, "roughness": 0.55},
    "int_grate": {"base": (0.22, 0.225, 0.23, 1.0), "metallic": 0.8, "roughness": 0.42},
    "int_plate": {"base": (0.34, 0.35, 0.36, 1.0), "metallic": 0.8, "roughness": 0.40},
    "int_cyan": {"base": (0.25, 0.95, 1.0, 1.0), "metallic": 0.0, "roughness": 0.3, "emission": (0.25, 0.95, 1.0),
                 "strength": 9.0},
    "int_amber": {"base": (1.0, 0.55, 0.15, 1.0), "metallic": 0.0, "roughness": 0.3, "emission": (1.0, 0.55, 0.15),
                  "strength": 8.0},
    "int_lamp": {"base": (1.0, 0.86, 0.68, 1.0), "metallic": 0.0, "roughness": 0.3, "emission": (1.0, 0.86, 0.68),
                 "strength": 12.0},
    "int_glass": {"base": (0.10, 0.14, 0.17, 0.16), "metallic": 0.0, "roughness": 0.03, "alpha": True},
    # the halo round a floor strip: a frosted diffuser glowing weaker than the strip (lights nothing, ship.toml)
    "int_halo": {"base": (1.0, 0.5, 0.12, 1.0), "metallic": 0.0, "roughness": 0.5, "emission": (1.0, 0.5, 0.12),
                 "strength": 2.0},
    # the cables: saturated mid values so they read in the bays (materials-3, corridor.jpg)
    "int_cable_red": {"base": (0.55, 0.035, 0.025, 1.0), "metallic": 0.0, "roughness": 0.36},
    "int_cable_black": {"base": (0.03, 0.03, 0.034, 1.0), "metallic": 0.0, "roughness": 0.45},
    "int_cable_blue": {"base": (0.03, 0.12, 0.5, 1.0), "metallic": 0.0, "roughness": 0.36},
    "int_cable_yellow": {"base": (0.8, 0.52, 0.04, 1.0), "metallic": 0.0, "roughness": 0.36},
    "int_bolt": {"base": (0.5, 0.51, 0.53, 1.0), "metallic": 0.85, "roughness": 0.3},
    "int_scratch": {"base": (0.85, 0.86, 0.88, 1.0), "metallic": 1.0, "roughness": 0.58},
    "int_cup_red": {"base": (0.6, 0.02, 0.02, 1.0), "metallic": 0.0, "roughness": 0.28},
    "int_cup_white": {"base": (0.86, 0.86, 0.84, 1.0), "metallic": 0.0, "roughness": 0.4},
    # the hall's amber floor ring: the corridors' amber, its own material so its strip lights get their own numbers
    "int_amber_ring": {"base": (1.0, 0.55, 0.15, 1.0), "metallic": 0.0, "roughness": 0.3, "emission": (1.0, 0.55, 0.15),
                       "strength": 8.0},
    # a soda spill: a thin glossy dark red film
    "int_spill": {"base": (0.22, 0.012, 0.01, 1.0), "metallic": 0.0, "roughness": 0.04},
    # a repair plate: a slightly warmer, rougher steel than the floor round it
    "int_patch": {"base": (0.42, 0.41, 0.39, 1.0), "metallic": 0.75, "roughness": 0.5},
    # inside-fix: the hall ceiling's face panels, a lit pale steel (the 2D's faceted ceiling): low metallic, so the
    # wall lamps light them instead of the dark room mirroring in them (no [light.mats] entry: Blender's values hold)
    "int_ceil_a": {"base": (0.74, 0.75, 0.77, 1.0), "metallic": 0.3, "roughness": 0.48},
    "int_ceil_b": {"base": (0.64, 0.655, 0.68, 1.0), "metallic": 0.3, "roughness": 0.5},
})

D = math.radians
with (Path(__file__).resolve().parents[2] / "layouts" / "ship" / "ship.toml").open("rb") as _f:
    _SHIP = tomllib.load(_f)
_ROOM = {r["id"]: r for r in _SHIP["rooms"]}
FLOOR = _SHIP["deck"]["floor_h"]                # the heights come from ship.toml (the hull lane owns them)
# rebuild C (art#263 c6341553197) moved the inside forward; rebuild E (c6342342554): 0.4 m forward of step A, the hall's
# rim full height all round. The builders and the generator work round the hall's centre (HALL_C, (0, -0.4));
# ship_interior_place.py adds HALL_C to every placement.
HALL_C = tuple(_ROOM["hall"]["centre"])
# the hall
N_HALL, R_HALL, H_HALL, APEX_HALL = 16, _ROOM["hall"]["radius"], _ROOM["hall"]["clear_h"], _ROOM["hall"]["apex_h"]
PHI = math.pi / N_HALL
HV = R_HALL / math.cos(PHI)                # vertex radius 4.078 (v2: R_HALL 4.0)
HW = R_HALL * math.tan(PHI)                # facet half width 0.796
HC = HV * math.cos(2 * PHI)                # an opening's chord (two facets) 3.768
HCH = HV * math.sin(2 * PHI)               # its half width 1.561
# v2 (5a mirrored): the plain wall spots at 45 deg (vents, sockets) get one flat chord over two facets, as an opening's
FLATS = sorted(round(math.degrees(math.atan2(s["at"][1] - HALL_C[1], s["at"][0] - HALL_C[0])), 4)
               for s in _SHIP["stations"]["spot"] if s["room"] == "hall" and s.get("normal"))
# rebuild C: the throat (ship.toml room "throat"): its hall corner on the 16-gon's circle HV (rebuild E: the rim full
# height all round)
_TH = _ROOM["throat"]
TH_PTS = [(x - HALL_C[0], y - HALL_C[1]) for x, y in _TH["points"]]   # hall-relative: mouth (-+1.65, -6.7), corners
TH_CORNER = math.degrees(math.atan2(TH_PTS[2][1], TH_PTS[2][0]))      # -44.38
TH_ROOF = _TH["roof_y"] - HALL_C[1]                                   # -5.161: the throat's ceiling from here aft
TH_H, (TH_BEND, TH_IN) = _TH["clear_h"], _TH["chamfer"]                # 2.3; walls vertical to 1.45, then 0.55 in
TH_HALF = 1.0                                                         # the wall modules' nominal half width
# inside-1: the hall's floor rings and lamp ring scaled with the hall (v1 apothem 3.4 -> 4.0: x 1.176)
K_HALL = R_HALL / 3.4
R_RING = round(1.25 * K_HALL, 3)           # the lamp ring and the ceiling's inner edge (1.47; v1 1.25)
R_DISC = round(1.0 * K_HALL, 3)            # the lit grating disc (1.176)
R_GRATE = (round(1.1 * K_HALL, 3), round(2.5 * K_HALL, 3))   # the grate ring between the disc and the amber ring
R_ARC = round(2.58 * K_HALL, 3)            # the amber floor ring (3.035)
R_RIM0 = round(2.66 * K_HALL, 3)           # the solid rim plates' inner edge (3.129)
R_RIM_REF = round(3.0 * K_HALL, 3)         # a rim plate's origin (3.529)
# rebuild A (variant J, art #263 comment 6340589162): the corridors run straight along the diagonal from the hall's
# centre to the tip rooms' (ship.toml `axis`), so the corridor openings sit on that angle (25.73 deg), off the 16-gon's
# vertices; the hall keeps its 16 facets' look, re-spaced round the moved openings (hall_segments)
_COR = _ROOM["corridor_e"]
COR_ANG = math.degrees(math.atan2(_COR["axis"][1][1] - _COR["axis"][0][1], _COR["axis"][1][0] - _COR["axis"][0][0]))
COR_DIR = (math.cos(D(COR_ANG)), math.sin(D(COR_ANG)))
OPENINGS = {"corridor_e": COR_ANG, "mouth": -90.0, "corridor_w": 180.0 - COR_ANG}   # opening centre angles (deg)
BACK_DEG = 12.5   # each of the two back facets either side of the back's trunk at 90 deg (was 22.5: the sockets' flats
# moved back off the corridor openings and need 1.6 m of plain chord clear of the portal pilaster: 2.06 m)
# lens step 1: the back sockets' flat chord stays where rebuild A put it (48.23..77.5 deg, the old corridor chord's end
# at 25.73 + 22.5), the sockets unchanged
SOCK_A0 = 25.7299 + 2 * math.degrees(PHI)


def hall_segments() -> list[tuple[float, float, str]]:
    """The hall's wall round the ring, (a0, a1, kind) counter-clockwise from the mouth: kind "opening" (two facets'
    chord, a portal: the mouth and the corridors), "flat" (a station's plain chord over two sub-facets: the vents and
    sockets), "facet" (one wall facet) or "door" (the vault's shut door, a flat chord over the two back facets). Every
    vertex on the circle HV, so the openings keep their chord (HC, HCH)."""
    e0, e1 = COR_ANG - 2 * math.degrees(PHI), COR_ANG + 2 * math.degrees(PHI)   # the east corridor's chord ends
    # lens step 1: the corridors' openings at +-8.66 deg; the front socket's flat from the throat's corner to the
    # opening (30.54 deg), one side facet from the opening to the back socket's flat, the vault's door at the back
    east = [(-180.0 - TH_CORNER, TH_CORNER, "throat"), (TH_CORNER, e0, "flat"), (e0, e1, "opening"),
            (e1, SOCK_A0, "facet"), (SOCK_A0, 90.0 - BACK_DEG, "flat")]
    west = [(180.0 - b, 180.0 - a, k) for a, b, k in reversed(east[1:])]
    return east + [(90.0 - BACK_DEG, 90.0 + BACK_DEG, "door")] + west


TH_SUBS = 4   # the throat's sub-facets (22.81 deg) under the hall's ceiling


def hall_vertices() -> list[float]:
    """Every vertex angle of the hall's wall (the segment ends and the openings' and flats' middle vertices)."""
    out = set()
    for a0, a1, k in hall_segments():
        if k == "throat":
            out |= {round(a0 + (a1 - a0) * i / TH_SUBS, 6) for i in range(TH_SUBS + 1)}
            continue
        out |= {round(a0, 6), round(a1, 6)} | ({round((a0 + a1) / 2, 6)} if k != "facet" else set())
    return sorted(((a + 180.0) % 360.0) - 180.0 for a in out)
# the corridors: profile (u across, v up from the deck), the five modules between the portals
H_COR = _ROOM["corridor_e"]["clear_h"]
COR_HALF = _ROOM["corridor_e"]["width"] / 2          # v2: 1.5 (3 m wide; v1 1.25)
MOUTH_HALF = 1.25
THROAT_PROF = [(-TH_HALF, 0.0), (-TH_HALF, TH_BEND), (-TH_HALF + TH_IN, TH_H), (TH_HALF - TH_IN, TH_H),
               (TH_HALF, TH_BEND), (TH_HALF, 0.0)]
PROF = [(-COR_HALF, 0.0), (-COR_HALF, H_COR - 0.95), (-COR_HALF + 0.35, H_COR), (COR_HALF - 0.35, H_COR),
        (COR_HALF, H_COR - 0.95), (COR_HALF, 0.0)]
# the mouth passage (inside 3-1, hall_out-2's wide opening): the mouth room's full 2.5 m width and clear height, the
# walls vertical to 0.35 m under the ceiling, only the top corners chamfered (the corridors' profile narrowed the view
# out to about 1.6 m)
H_MOUTH = 2.4   # rebuild C: v2's mouth passage (gone; the profile stays for the blockout's reference)
MOUTH_PROF = [(-1.25, 0.0), (-1.25, H_MOUTH - 0.35), (-0.95, H_MOUTH), (0.95, H_MOUTH), (1.25, H_MOUTH - 0.35),
              (1.25, 0.0)]


def _prof(args):
    if args.get("prof") == "throat":   # rebuild C: the throat's, args half (its width where an arch stands)
        w, k = args.get("half", TH_HALF), args.get("k", 1.0)   # k: the chamfer's lean in a cut across the walls
        return [(-w, 0.0), (-w, TH_BEND), (-w + TH_IN * k, TH_H), (w - TH_IN * k, TH_H), (w, TH_BEND), (w, 0.0)]
    return MOUTH_PROF if args.get("prof") == "mouth" else PROF


def _half(args):
    """A passage's half width: the throat's, the mouth's or a corridor's."""
    prof = (args or {}).get("prof")
    if prof == "throat":
        return args.get("half", TH_HALF)
    return MOUTH_HALF if prof == "mouth" else COR_HALF

PORTAL_D = 0.15
# the tip rooms
R_TIP, H_TIP, APEX_TIP, R_TIP_RING = (_ROOM["tip_e"]["radius"] + 0.05, _ROOM["tip_e"]["clear_h"],
                                      _ROOM["tip_e"]["apex_h"], 0.32)   # lens step 1: room r 2.0 -> vertex radius 2.05
# polish 4: R_TIP_RING 0.6 -> 0.42 (the tip ceiling's pale lamp cog read oversized from the room); lens step 1: 0.32,
# its beam (to r 0.42) clear of the roof windows (their nearest corner at r 0.46)
# lens step 1 (art#263 c6344490367): the lens rooms' ceiling slants down outward along the axis (P's ray_roof): clear
# H_TIP_IN at the corridor's side, H_TIP at the outer wall; the walls stand H_TIP high and the ceiling's fascia closes
# the slant's gap over them. The window band (local degrees, + aft in the east room; the west room is placed mirrored)
# and the three roof windows (local rects along x, across y).
H_TIP_IN = _ROOM["tip_e"]["clear_h_in"]
RW_TIP = _ROOM["tip_e"]["radius"] + _SHIP["deck"]["wall_m"]          # 2.2: the slant's span is the outer wall's
BAND = _ROOM["tip_e"]["band"]
SILL, HEAD = BAND["sill_h"], BAND["head_h"]
_RWS = _ROOM["tip_e"]["roof_window_m"]
ROOF_WINS = [(t - _RWS[0] / 2, t + _RWS[0] / 2, w - _RWS[1] / 2, w + _RWS[1] / 2) for t, w in _ROOM["tip_e"]["roof_windows"]]


def tip_clear(t: float) -> float:
    """The lens room's clear height t along its outward axis from its centre (P's ray_roof: 2.4455 at the corridor's
    wall face, 2.3545 at the outer one)."""
    return H_TIP + (H_TIP_IN - H_TIP) * (RW_TIP - t) / (2 * RW_TIP)
TIP_C = (_ROOM["tip_e"]["centre"][0] - HALL_C[0], _ROOM["tip_e"]["centre"][1] - HALL_C[1])   # (8.3, 4.0) from the hall
TIP_X = math.hypot(*TIP_C)                           # the tip room's centre along the axis from the hall's (9.214)
DOOR_HALF = math.degrees(math.asin((COR_HALF + 0.03) / R_TIP))   # v2: the 3 m corridor's chord, 55.8 (v1 37.6)
TIP_N = 12                                           # lens step 1: 12 wall facets of 21.95 deg (rebuild A: 13); vertex 0 on
# the axis, the window band on facets 3..7 (-65.86..43.91 deg, the asked -65..45 snapped to the vertices)
TIP_STEP = (360.0 - 2 * DOOR_HALF) / TIP_N           # a wall facet's angle (19.11; v2's wall facets 19.73)
TIP_CHORD = -R_TIP * math.cos(D(DOOR_HALF))          # -1.039
TIP_CHORD_H = R_TIP * math.sin(D(DOOR_HALF))         # 1.53
# the corridor's modules along its axis (u from the hall's centre): hall portal to tip portal
COR_X0 = HC + PORTAL_D                               # 3.918
COR_X1 = TIP_X + TIP_CHORD - PORTAL_D                # 8.024 (v2 7.111 on the x axis)
N_MOD = 5                                            # lens step 1: five modules of 1.038 (rebuild A: four of 1.026)
MOD_L = (COR_X1 - COR_X0) / N_MOD                    # 1.038
H_TIP_PORTAL = round(tip_clear(TIP_CHORD) - 0.003, 4)   # the door's portal and pilasters up to the slanted ceiling (2.428)


def tip_band_facets(side: int = 1) -> list[int]:
    """The wall facets (indices into tip_vertices' pairs) in the window band; side -1: the west room's, mirrored."""
    tv = tip_vertices()
    lo, hi = (BAND["from_deg"], BAND["to_deg"]) if side > 0 else (-BAND["to_deg"], -BAND["from_deg"])
    return [i for i, (a0, a1) in enumerate(zip(tv, tv[1:])) if lo - 1.5 <= a0 and a1 <= hi + 1.5]


def tip_vertices() -> list[float]:
    """The tip room's vertex angles (deg, in the room's frame, the door toward 180): TIP_N wall facets from one door
    edge round the outer side to the other (rebuild A: no window), the corridor chord between them."""
    a0 = -(180.0 - DOOR_HALF)
    return [a0 + TIP_STEP * i for i in range(TIP_N + 1)]


def tip_edges() -> list[tuple[float, float]]:
    """(a0, a1) of every tip-room edge, counter-clockwise, the corridor chord last."""
    a = sorted(tip_vertices())
    edges = list(zip(a, a[1:]))
    return edges + [(a[-1], a[0] + 360.0)]


# --- small helpers -------------------------------------------------------------------------------------------------
def P(name, vf, mat):
    return L.part(name, *vf, mat)


def shift(vf, dx=0.0, dy=0.0, dh=0.0):
    v, f = vf
    return [(x + dx, y + dy, h + dh) for x, y, h in v], f


def rot(vf, deg):
    c, s = math.cos(D(deg)), math.sin(D(deg))
    v, f = vf
    return [(x * c - y * s, x * s + y * c, h) for x, y, h in v], f


def M(*vfs):
    return L.merge(*vfs)


def wedge(r0, r1, a0, a1):
    return G.arc(r0, a0, a1)[::-1] + G.arc(r1, a0, a1)


# --- walls: panels, pilasters, portals -----------------------------------------------------------------------------
def wall_panel(args, layout):
    """A wall facet (the hall's or a tip room's): body, kick plate, folded main panel, belt, upper panel."""
    hw, h, tone = args.get("half", HW), args.get("height", H_HALL), args.get("tone", "a")
    fr = G.wall_frame(FLOOR)
    lo, hi = ("int_silver_a", "int_silver_b") if tone == "a" else ("int_silver_b", "int_silver_a")
    belt = h - 0.9
    e = hw - 0.135
    # hall_in-3's faceted wall: a raised diamond folded up to a ridge point, four chamfered corner plates round it
    # (seams 12 mm), the upper panel split on its diagonal into two folds (alternating with the tone)
    v0, v1, g = 0.2, belt - 0.05, 0.012
    vm = (v0 + v1) / 2
    dia = [(0.0, v0 + g), (e - g, vm), (0.0, v1 - g), (-e + g, vm)]
    corners = [[(-e, v0), (-g, v0), (-e, vm - g)], [(g, v0), (e, v0), (e, vm - g)],
               [(e, vm + g), (e, v1), (g, v1)], [(-e, vm + g), (-g, v1), (-e, v1)]]
    u0, u1 = belt + 0.17, h - 0.04
    tris = (([(-e, u0), (e, u0), (-e, u1)], [(e, u0), (e, u1), (-e, u1)]) if tone == "a" else
            ([(-e, u0), (e, u0), (e, u1)], [(-e, u0), (e, u1), (-e, u1)]))
    up = [G.inset(t, 0.006) for t in tris]
    out = []
    if args.get("soffit"):  # a flat chord over two hall facets: close the ceiling's rim behind it
        tri = [(0.0, -hw), (HV - HC, 0.0), (0.0, hw)]
        out.append(P("soffit", G.slab(G.floor_frame(0.0), tri, FLOOR + h, FLOOR + h + 0.08), "int_silver_b"))
    return out + [P("body", G.slab(fr, G.rect(-hw, hw, 0.0, h), -0.2, 0.0), "int_silver_b"),
            P("kick", G.slab(fr, G.rect(-e, e, 0.0, 0.16), 0.0, 0.015), "int_dark"),
            P("diamond", pyramid(fr, dia, 0.0, 0.035, 0.1, 0.012), lo),
            P("corners", M(*[G.slab(fr, G.inset(c, 0.004), 0.0, 0.025, 0.01) for c in corners]), hi),
            P("belt", G.slab(fr, G.rect(-hw, hw, belt, belt + 0.12), 0.0, 0.05, 0.012), "int_silver_c"),
            P("upper", M(G.slab(fr, up[0], 0.0, 0.03, 0.01), G.slab(fr, up[1], 0.0, 0.045, 0.01)), hi)]


def flat_panel(args, layout):
    """inside-1: a station's flat chord over two hall facets (3.12 m): a PLAIN centre panel 2 x `plain` wide (a
    station hangs flat on it later: no relief, no trunk) between two narrow diamond panels, the soffit closing the
    ceiling's rim behind the chord."""
    hw, h, pl = args["half"], args.get("height", H_HALL), args.get("plain", 0.8)
    apo = args.get("apo", HC)   # rebuild A: the chord's apothem (a socket's flat is narrower than two facets)
    fr = G.wall_frame(FLOOR)
    belt = h - 0.9
    side = (hw - pl) / 2
    if side < 0.12:   # rebuild A: too narrow for a diamond panel: the plain panel takes the whole chord
        pl, side = hw, 0.0
    out = []
    for k, sgn in enumerate((-1, 1) if side else ()):
        for part in wall_panel({"half": side, "height": h, "tone": "ab"[k]}, layout):
            v = [(x, y + sgn * (pl + side), z) for x, y, z in part["verts"]]
            out.append(L.part(f"{part['name']}_{k}", v, part["faces"], part["mat"]))
    tri = [(0.0, -hw), (HV - apo, 0.0), (0.0, hw)]
    e = pl - 0.06
    return out + [P("soffit", G.slab(G.floor_frame(0.0), tri, FLOOR + h, FLOOR + h + 0.08), "int_silver_b"),
                  P("body", G.slab(fr, G.rect(-pl, pl, 0.0, h), -0.2, 0.0), "int_silver_b"),
                  P("kick", G.slab(fr, G.rect(-e, e, 0.0, 0.16), 0.0, 0.015), "int_dark"),
                  P("plain", G.slab(fr, G.rect(-e, e, 0.2, belt - 0.05), 0.0, 0.02, 0.008), "int_silver_a"),
                  P("belt", G.slab(fr, G.rect(-pl, pl, belt, belt + 0.12), 0.0, 0.05, 0.012), "int_silver_c"),
                  P("upper", G.slab(fr, G.rect(-e, e, belt + 0.17, h - 0.04), 0.0, 0.03, 0.01), "int_silver_b")]


def pyramid(fr, poly, w0, w1, apex, bevel):
    """A convex polygon (counter-clockwise in u, v) raised from w0 to w1, its top chamfered by `bevel` and folded up
    to a ridge point at its centroid (w apex): pillow() for any polygon."""
    n = len(poly)
    cu, cv = sum(u for u, _ in poly) / n, sum(v for _, v in poly) / n
    verts = [fr.point(u, v, w0) for u, v in poly] + [fr.point(u, v, w1) for u, v in poly]
    verts += [fr.point(u, v, w1 + bevel) for u, v in G.inset(poly, bevel)]
    verts.append(fr.point(cu, cv, apex))
    faces = [tuple(range(n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    faces += [(n + i, n + (i + 1) % n, 2 * n + (i + 1) % n, 2 * n + i) for i in range(n)]
    faces += [(2 * n + i, 2 * n + (i + 1) % n, 3 * n) for i in range(n)]
    return verts, faces


def hex_bolt(x, y, h, r=0.011):
    """A hex bolt head standing on the plane h (plan x, y)."""
    return shift(L.disc(r, 6, h, h + 0.007), x, y)


def trunk(args, layout):
    """A cable trunk on a plain vertex (hall_in-3's radial columns): two bevelled posts standing 0.2 m proud round a
    dark back, a foot and a capital; the cables and clip frames are their own pieces (trunk_cables, trunk_clip).
    inside-fix: `flat` (the tip rooms) stands 0.09 m proud, flat to the wall (0.2 read as thick posts)."""
    h = args.get("height", H_HALL)
    d = 0.09 if args.get("flat") else 0.2
    fr = G.wall_frame(FLOOR)
    posts = M(G.slab(fr, G.rect(-0.23, -0.13, 0.18, h - 0.16), -0.02, d, 0.03),
              G.slab(fr, G.rect(0.13, 0.23, 0.18, h - 0.16), -0.02, d, 0.03))
    caps = M(G.slab(fr, G.rect(-0.26, 0.26, 0.0, 0.18), -0.02, d + 0.03, 0.02 if args.get("flat") else 0.035),
             G.slab(fr, G.rect(-0.26, 0.26, h - 0.16, h), -0.02, d + 0.03, 0.02 if args.get("flat") else 0.035))
    return [P("posts", posts, "int_silver_a"), P("caps", caps, "int_silver_c"),
            P("back", G.slab(fr, G.rect(-0.13, 0.13, 0.18, h - 0.16), -0.02, 0.02), "int_dark")]


def trunk_cables(args, layout):
    """Five thick cables down a trunk, swaying a little between the clips (red, yellow, black, blue, red)."""
    h = args.get("height", H_HALL)
    kw, kr = (0.45, 0.75) if args.get("flat") else (1.0, 1.0)  # inside-fix: `flat`, pressed to the wall
    out = []
    for k, (u, w, r, mat) in enumerate(((-0.085, 0.07, 0.028, "int_cable_red"), (-0.035, 0.1, 0.024,
                                        "int_cable_yellow"), (0.015, 0.065, 0.032, "int_cable_black"),
                                        (0.068, 0.095, 0.026, "int_cable_blue"), (0.1, 0.06, 0.018, "int_cable_red"))):
        pts = [(kw * (-w - 0.012 * math.sin(math.pi * t / 8 + k)), u + 0.008 * math.sin(2.1 * t + k),
                FLOOR + 0.15 + (h - 0.28) * t / 8) for t in range(9)]
        out.append(P(f"{mat[10:]}{k}", G.tube(pts, kr * r, 8), mat))
    return out


def trunk_clip(args, layout):
    """A clip frame across a trunk (placed at a height offset): a bevelled bar over the cables, two bolted lugs."""
    fr = G.wall_frame(FLOOR)
    d = 0.09 if args.get("flat") else 0.16   # inside-fix: `flat` over a flat trunk
    bar = M(G.slab(fr, G.rect(-0.2, 0.2, 0.0, 0.06), d - 0.03, d, 0.008),
            G.slab(fr, G.rect(-0.2, -0.15, 0.0, 0.06), 0.0, d, 0.008),
            G.slab(fr, G.rect(0.15, 0.2, 0.0, 0.06), 0.0, d, 0.008))
    bolts = M(*[G.slab(fr, [(u + 0.011 * math.cos(math.pi * i / 3), 0.03 + 0.011 * math.sin(math.pi * i / 3))
                            for i in range(6)], d, d + 0.008, 0.002) for u in (-0.175, 0.175)])
    return [P("bar", bar, "int_silver_c"), P("bolts", bolts, "int_bolt")]


def pilaster(args, layout):
    """A pilaster on a vertex where two facets meet: two posts round a dark cable channel, foot and capital."""
    h = args.get("height", H_HALL)
    fr = G.wall_frame(FLOOR)
    posts = M(G.slab(fr, G.rect(-0.13, -0.06, 0.16, h - 0.14), -0.05, 0.10, 0.015),
              G.slab(fr, G.rect(0.06, 0.13, 0.16, h - 0.14), -0.05, 0.10, 0.015))
    caps = M(G.slab(fr, G.rect(-0.145, 0.145, 0.0, 0.16), -0.05, 0.12, 0.012),
             G.slab(fr, G.rect(-0.145, 0.145, h - 0.14, h), -0.05, 0.12, 0.012))
    return [P("posts", posts, "int_silver_a"), P("caps", caps, "int_silver_c"),
            P("channel", G.slab(fr, G.rect(-0.06, 0.06, 0.16, h - 0.14), -0.08, -0.03), "int_dark")]


def pilaster_strip(args, layout):
    """The cyan strip glowing in a pilaster's channel (at the openings and the windows)."""
    h = args.get("height", H_HALL)
    return [P("strip", G.slab(G.wall_frame(FLOOR), G.rect(-0.018, 0.018, 0.3, h - 0.3), -0.03, -0.012), "int_cyan")]


def portal(args, layout):
    """The frame of an opening on its chord (local x = 0; the room toward -x, the passage toward +x): the frame band
    round the corridor profile, the header and side fillers up to the rim, the soffit back to the facets (hall)."""
    w, h, soffit = args["half"], args["height"], args.get("soffit", False)
    fr = G.wall_frame(FLOOR)
    prof = _prof(args)
    outer = [(u, max(0.0, v)) for u, v in G.inset(prof, -0.1)]
    inner = prof
    o1, o2, o3 = outer[1], outer[2], outer[3]
    fill = M(G.slab(fr, [(-w, o1[1]), o2, (o2[0], h), (-w, h)], -PORTAL_D, 0.0),
             G.slab(fr, [(w, o1[1]), (w, h), (o3[0], h), o3], -PORTAL_D, 0.0),
             G.slab(fr, G.rect(o2[0], o3[0], o2[1], h), -PORTAL_D, 0.0))
    out = [P("band", G.band(fr, inner, outer, -PORTAL_D - 0.01, 0.045, 0.02, range(5)), "int_silver_c"),
           P("fill", fill, "int_silver_b")]
    if soffit:
        tri = [(0.0, -w, FLOOR + h), (HV - HC, 0.0, FLOOR + h), (0.0, w, FLOOR + h)]
        out.append(P("soffit", G.slab(G.floor_frame(0.0), [(x, y) for x, y, _ in tri], FLOOR + h, FLOOR + h + 0.08),
                     "int_silver_b"))
    return out


def portal_strip(args, layout):
    """A cyan strip on one side of a portal's band (side -1: edges up the -y side, +1 the +y side)."""
    fr = G.wall_frame(FLOOR)
    edges = (0, 1) if args["side"] < 0 else (3, 4)
    prof = _prof(args)
    return [P("strip", G.band(fr, G.inset(prof, -0.035), G.inset(prof, -0.065), 0.045, 0.057, 0.0, edges),
              "int_cyan")]


# --- the hall ------------------------------------------------------------------------------------------------------
def hall_floor_base(args, layout):
    return [P("base", L.disc(R_HALL + 0.35, N_HALL, FLOOR - 0.25, FLOOR - 0.035), "int_dark")]


def floor_disc(args, layout):
    """The plain centre disc with its trim ring (hall and tip rooms)."""
    r = args["radius"]
    disc = G.slab(G.floor_frame(0.0), G.arc(r - 0.005, 0.0, 2 * math.pi)[:-1], FLOOR - 0.035, FLOOR, 0.008)
    a = L.angles(0.0, 2 * math.pi, D(6.0))
    trim = M(*[L.sector(r, r + 0.07, p, q, FLOOR - 0.035, FLOOR) for p, q in zip(a, a[1:])])
    if args.get("grate"):
        # polish 4 (hall_in-3's lit centre): a slotted grating disc in four quarters round a bolted hub, a warm glow
        # layer under the slots (int_halo: glows, lights nothing), the trim ring kept (was a plain plate: a black hole)
        q = [G.radial_grate(0.26, r - 0.005, D(90.0 * k + 1.0), D(90.0 * (k + 1) - 1.0), FLOOR - 0.035, FLOOR)
             for k in range(4)]
        glow = L.disc(r - 0.01, 32, FLOOR - 0.034, FLOOR - 0.032)
        hub = G.slab(G.floor_frame(0.0), G.arc(0.265, 0.0, 2 * math.pi)[:-1], FLOOR - 0.035, FLOOR + 0.004, 0.008)
        bolts = M(*[hex_bolt(0.19 * math.cos(D(45.0 * k + 22.5)), 0.19 * math.sin(D(45.0 * k + 22.5)), FLOOR + 0.004,
                             0.012) for k in range(8)])
        return [P("grate", M(*q), "int_grate"), P("glow", glow, "int_halo"), P("hub", hub, "int_plate"),
                P("bolts", bolts, "int_bolt"), P("trim", trim, "int_silver_c")]
    inlay = M(*[L.sector(r * 0.55, r * 0.55 + 0.03, p, q, FLOOR, FLOOR + 0.002) for p, q in zip(a, a[1:])])
    return [P("disc", disc, "int_plate"), P("trim", trim, "int_silver_c"), P("inlay", inlay, "int_dark")]


def radial_grate(args, layout):
    """A grate sector between two spokes, centred on angle 0 (shifted so its origin is at radius `ref`)."""
    r0, r1, half, ref = args["r0"], args["r1"], D(args["half_deg"]), args["ref"]
    return [P("grate", shift(G.radial_grate(r0, r1, -half, half, FLOOR - 0.035, FLOOR), -ref), "int_grate")]


def spoke(args, layout):
    r0, r1, half, ref = args["r0"], args["r1"], D(args["half_deg"]), args["ref"]
    poly = [(r0 * math.cos(-half), r0 * math.sin(-half)), (r1 * math.cos(-half), r1 * math.sin(-half)),
            (r1 * math.cos(half), r1 * math.sin(half)), (r0 * math.cos(half), r0 * math.sin(half))]
    return [P("spoke", shift(G.slab(G.floor_frame(0.0), poly, FLOOR - 0.035, FLOOR, 0.006), -ref), "int_plate")]


def amber_arc(args, layout):
    """One arc of the hall's amber floor ring: a bezel and the light, +-10 deg about angle 0. inside-fix: the 2D's thin
    ring, a 5 cm light in a 9 cm halo (was 12 in 18: it blew out the grate by the ramp); `thin` (the four arcs by the
    mouth) a 3 cm light in a 6 cm halo."""
    r, ref = args["radius"], args["radius"]
    a = L.angles(D(-10.0), D(10.0), D(2.5))
    lw, hw, bw = (0.015, 0.03, 0.055) if args.get("thin") else (0.025, 0.045, 0.07)
    bezel = M(*[L.sector(r - bw, r + bw, p, q, FLOOR - 0.01, FLOOR + 0.004) for p, q in zip(a, a[1:])])
    halo = M(*[L.sector(r - hw, r + hw, p, q, FLOOR + 0.004, FLOOR + 0.006) for p, q in zip(a, a[1:])])
    light = M(*[L.sector(r - lw, r + lw, p, q, FLOOR + 0.006, FLOOR + 0.009) for p, q in zip(a, a[1:])])
    return [P("bezel", shift(bezel, -ref), "int_silver_c"), P("halo", shift(halo, -ref), "int_halo"),
            P("light", shift(light, -ref), "int_amber_ring")]


def _facet(args):
    """(half angle in radians, apothem, half width) of a hall facet or chord: `phi_deg` its half angle (default one
    16-gon facet), every vertex on the circle HV (rebuild A: the facets re-spaced round the moved openings)."""
    phi = D(args.get("phi_deg", math.degrees(PHI)))
    return phi, HV * math.cos(phi), HV * math.sin(phi)


def hall_floor_rim(args, layout):
    """The solid floor plates between the amber ring and a wall facet: two halves with a seam (origin at R_RIM_REF)."""
    g = 0.003
    phi, apo, hw = _facet(args)
    a = G.arc(R_RIM0, -phi, -g / R_RIM0)
    b = G.arc(R_RIM0, g / R_RIM0, phi)
    fr = G.floor_frame(0.0)
    halves = M(G.slab(fr, a + [(apo, -g), (apo, -hw)], FLOOR - 0.035, FLOOR, 0.006),
               G.slab(fr, b + [(apo, hw), (apo, g)], FLOOR - 0.035, FLOOR, 0.006))
    return [P("plates", shift(halves, -R_RIM_REF), "int_plate")]


def hall_threshold(args, layout):
    """The floor plate of an opening, from the amber ring through the portal (origin on the chord)."""
    poly = G.arc(R_RIM0, -2 * PHI, 2 * PHI) + [(HC, HCH), (COR_X0 - 0.001, COR_HALF), (COR_X0 - 0.001, -COR_HALF), (HC, -HCH)]
    return [P("plate", shift(G.slab(G.floor_frame(0.0), poly, FLOOR - 0.035, FLOOR, 0.006), -HC), "int_plate")]


def hall_flat_floor(args, layout):
    """inside-fix: the floor plate of a station's flat chord (two facets), from the amber ring's rim edge to the chord,
    where a player stands at a vent or a socket (was the dark base 3.5 cm down; origin on the chord)."""
    phi, apo, hw = _facet({"phi_deg": args.get("phi_deg", 2 * math.degrees(PHI))})
    poly = G.arc(R_RIM0, -phi, phi) + [(apo, hw), (apo, -hw)]
    return [P("plate", shift(G.slab(G.floor_frame(0.0), poly, FLOOR - 0.035, FLOOR, 0.006), -apo), "int_plate")]


def ceiling_facet(apo, half, rim_h, r_in, h_in, phi):
    """(frame, polygon) of a conical ceiling facet over an edge centred on angle 0."""
    inner = (r_in * math.cos(phi), r_in * math.sin(phi))
    vdir = (inner[0] - apo, 0.0, h_in - rim_h)
    vlen = math.hypot(vdir[0], vdir[2])
    fr = G.Frame((apo, 0.0, rim_h), (0, 1, 0), vdir, G.cross(G.unit(vdir), (0, 1, 0)))
    return fr, [(-half, 0.0), (half, 0.0), (inner[1], vlen), (-inner[1], vlen)]


def ceiling_panels(fr, poly, tone, mats=("int_silver_a", "int_silver_b")):
    """A ceiling facet: its body and two triangular face panels split on the diagonal."""
    a, b = mats if tone == "a" else mats[::-1]
    face = G.inset(poly, 0.09)
    t1 = G.inset([face[0], face[1], face[2]], 0.006)
    t2 = G.inset([face[0], face[2], face[3]], 0.006)
    return [G.slab(fr, poly, -0.15, 0.0), G.slab(fr, t1, 0.0, 0.025, 0.008), G.slab(fr, t2, 0.0, 0.03, 0.008)], (a, b)


def hall_ceil_panel(args, layout):
    h_in = FLOOR + H_HALL + (APEX_HALL - H_HALL) * (1 - R_RING / R_HALL)
    phi, apo, hw = _facet(args)
    fr, poly = ceiling_facet(apo, hw, FLOOR + args.get("height", H_HALL), R_RING, h_in, phi)   # rebuild C: the front's low rim
    (body, t1, t2), (a, b) = ceiling_panels(fr, poly, args.get("tone", "a"), ("int_ceil_a", "int_ceil_b"))
    return [P("body", shift(body, -apo), "int_silver_b"), P("tri_a", shift(t1, -apo), a),
            P("tri_b", shift(t2, -apo), b)]


def rib(args, layout):
    """A ceiling rib under a vertex line, from the rim to the lamp ring (origin at the vertex), and its cyan strip."""
    rv, rim, r_in, h_in = args["rv"], args["rim"], args["r_in"], args["h_in"]
    vdir = (r_in - rv, 0.0, h_in - rim)
    vlen = math.hypot(vdir[0], vdir[2])
    fr = G.Frame((0.0, 0.0, rim), (0, 1, 0), vdir, G.cross(G.unit(vdir), (0, 1, 0)))
    if args.get("strip"):
        return [P("strip", G.slab(fr, G.rect(-0.017, 0.017, 0.25, vlen * 0.62), 0.1, 0.112), "int_cyan")]
    return [P("rib", G.slab(fr, G.rect(-0.075, 0.075, -0.05, vlen), -0.02, 0.1, 0.018), "int_silver_c")]


def lamp_ring(args, layout):
    """The ceiling's centre: the lamp ring beam and the cap closing the middle."""
    r, h = args["radius"], args["h_in"]
    a = L.angles(0.0, 2 * math.pi, D(7.5))
    beam = M(*[L.sector(r - 0.13, r + 0.1, p, q, h - 0.15, h + 0.02) for p, q in zip(a, a[1:])])
    lip = M(*[L.sector(r - 0.16, r - 0.12, p, q, h - 0.19, h - 0.1) for p, q in zip(a, a[1:])])
    # inside 3-1: the middle is a faceted cone rising into the roof (16 facets), eight ribs under it and a lamp at
    # its top (was a flat disc that read as a black hole)
    rc, rise = r - 0.1, 0.34 * r / 1.25
    cap = L.dome(rc, 16, h - 0.02, h - 0.02 + rise, 0.06)

    def under(p):  # the cone's underside at radius p
        return h - 0.02 + rise * (1 - p / rc)
    r_lamp = 0.26 * r / 1.25
    ribs = []
    for i in range(8):
        p0, p1 = rc - 0.02, r_lamp + 0.02
        vdir = (p1 - p0, 0.0, under(p1) - under(p0))
        fr = G.Frame((p0, 0.0, under(p0)), (0, 1, 0), vdir, G.cross(G.unit(vdir), (0, 1, 0)))
        vlen = math.hypot(vdir[0], vdir[2])
        ribs.append(rot(G.slab(fr, G.rect(-0.03, 0.03, 0.0, vlen), -0.01, 0.045, 0.012), 22.5 * i + 11.25))
    boss = M(L.disc(r_lamp + 0.05, 16, under(r_lamp + 0.05) - 0.06, h - 0.02 + rise + 0.02), *ribs)
    lens = L.disc(r_lamp - 0.03, 16, under(r_lamp + 0.05) - 0.075, under(r_lamp + 0.05) - 0.06)
    # the warm band: the beam's whole underside glows (hall_in-3's thick amber ring of light, inside-1)
    band = M(*[L.sector(r - 0.11, r + 0.08, p, q, h - 0.165, h - 0.15) for p, q in zip(a, a[1:])])
    return [P("beam", beam, "int_silver_c"), P("lip", lip, "int_silver_a"), P("cap", cap, "int_silver_b"),
            P("boss", boss, "int_silver_c"), P("band", band, "int_lamp"), P("lens", lens, "int_lamp")]


def lamp(args, layout):
    """A lamp fixture under the ring (local y along the ring): housing and warm lens."""
    h = args["h_in"]
    return [P("housing", G.bbox(-0.075, 0.075, -0.17, 0.17, h - 0.2, h - 0.15), "int_silver_c"),
            P("lens", G.bbox(-0.052, 0.052, -0.14, 0.14, h - 0.212, h - 0.2), "int_lamp")]


# --- the corridors and the mouth passage (one module, length from args) ---------------------------------------------
def _north(y=None, h=FLOOR, args=None):
    y = -_half(args) if y is None else y
    return G.Frame((0.0, y, h), (1, 0, 0), (0, 0, 1), (0, 1, 0))


def cor_floor_base(args, layout):
    hl = args["length"] / 2
    hw = _half(args) + 0.2
    return [P("base", L.box(-hl, hl, -hw, hw, FLOOR - 0.25, FLOOR - 0.04), "int_dark")]


def cor_grate(args, layout):
    """A framed grate module (materials-3): the grate, a bevelled rim round it standing 8 mm proud, hex bolts at the
    corners and the middles of the long sides."""
    hl = args["length"] / 2 - 0.004
    fr = G.floor_frame(0.0)
    t = 0.05
    rim = M(G.slab(fr, G.rect(-hl, hl, -0.88, -0.88 + t), FLOOR - 0.035, FLOOR + 0.008, 0.007),
            G.slab(fr, G.rect(-hl, hl, 0.88 - t, 0.88), FLOOR - 0.035, FLOOR + 0.008, 0.007),
            G.slab(fr, G.rect(-hl, -hl + t, -0.88 + t, 0.88 - t), FLOOR - 0.035, FLOOR + 0.008, 0.007),
            G.slab(fr, G.rect(hl - t, hl, -0.88 + t, 0.88 - t), FLOOR - 0.035, FLOOR + 0.008, 0.007))
    bolts = M(*[hex_bolt(x, y, FLOOR + 0.008) for x in (-hl + t / 2, 0.0, hl - t / 2) for y in (-0.855, 0.855)])
    return [P("grate", G.rect_grate(-hl + t, hl - t, -0.88 + t, 0.88 - t, FLOOR - 0.035, FLOOR), "int_grate"),
            P("rim", rim, "int_silver_c"), P("bolts", bolts, "int_bolt")]


def cor_gutter(args, layout):
    """The solid floor strip along the north wall (the amber strip sits on it)."""
    hl = args["length"] / 2 - 0.004
    return [P("plate", G.slab(G.floor_frame(0.0), G.rect(-hl, hl, -_half(args), -0.895), FLOOR - 0.035, FLOOR, 0.008),
              "int_plate")]


def floor_light(args, layout):
    """An amber light bar set in the floor along local x (corridor.jpg, materials-3): a bevelled bezel with bolted
    ends, a frosted halo and the light (length from args)."""
    hl = args.get("length", 0.44) / 2
    bolts = M(hex_bolt(-hl + 0.03, 0.0, FLOOR + 0.006, 0.009), hex_bolt(hl - 0.03, 0.0, FLOOR + 0.006, 0.009))
    return [P("bezel", G.bbox(-hl, hl, -0.07, 0.07, FLOOR - 0.002, FLOOR + 0.006, 0.004), "int_silver_c"),
            P("halo", G.bbox(-hl + 0.055, hl - 0.055, -0.055, 0.055, FLOOR + 0.006, FLOOR + 0.008), "int_halo"),
            P("light", G.bbox(-hl + 0.07, hl - 0.07, -0.032, 0.032, FLOOR + 0.008, FLOOR + 0.011), "int_amber"),
            P("bolts", bolts, "int_bolt")]


def cor_wall_low(args, layout):
    hl = args["length"] / 2
    fr = _north(args=args)
    e = hl - 0.006
    tone = "int_silver_a" if args.get("tone", "a") == "a" else "int_silver_b"
    return [P("body", G.slab(fr, G.rect(-hl, hl, 0.0, 1.1), -0.2, 0.0), "int_silver_b"),
            P("kick", G.slab(fr, G.rect(-e, e, 0.0, 0.13), 0.0, 0.015), "int_dark"),
            P("panel", G.pillow(fr, -e + 0.01, e - 0.01, 0.16, 1.04, 0.0, 0.03, 0.07, 0.012), tone)]


def cor_channel(args, layout):
    """The cable bay at the wall's bend (corridor.jpg): a dark recess 0.24 m deep with bevelled sill and lintel."""
    hl = args["length"] / 2
    fr = _north(args=args)
    lips = M(G.slab(fr, G.rect(-hl, hl, 1.04, 1.12), -0.2, 0.06, 0.02),
             G.slab(fr, G.rect(-hl, hl, 1.43, 1.5), -0.2, 0.05, 0.02))
    return [P("back", G.slab(fr, G.rect(-hl, hl, 1.1, 1.45), -0.24, -0.2), "int_dark"), P("lips", lips, "int_silver_c")]


def cor_cables(args, layout):
    """Four thick cables along a bay (red, yellow, blue, black), sagging a little between the clip frames."""
    hl = args["length"] / 2
    out = []
    for (w, h, r, mat, ph) in ((-0.17, 1.165, 0.032, "int_cable_red", 0.0), (-0.12, 1.235, 0.026, "int_cable_yellow",
                               1.3), (-0.17, 1.305, 0.03, "int_cable_blue", 2.1), (-0.13, 1.38, 0.028,
                               "int_cable_black", 0.7)):
        pts = [(-hl + 2 * hl * t / 8, -_half(args) + w + 0.012 * math.sin(math.pi * t / 4 + ph) * math.sin(math.pi * t / 8),
                FLOOR + h - 0.014 * math.sin(math.pi * t / 8)) for t in range(9)]
        out.append(P(mat[10:], G.tube(pts, r, 8), mat))
    return out


def cor_wall_mid(args, layout):
    """v2: the plain wall between the low wall and the upper wall where a cable bay would be (a breaker board's)."""
    hl = args["length"] / 2
    fr = _north(args=args)
    return [P("body", G.slab(fr, G.rect(-hl, hl, 1.1, PROF[1][1]), -0.2, 0.0), "int_silver_b"),
            P("panel", G.pillow(fr, -hl + 0.01, hl - 0.01, 1.12, PROF[1][1] - 0.02, 0.0, 0.03, 0.07, 0.012),
              "int_silver_a")]


def clip_h(args, layout):
    """A clip frame across a bay (materials-3): a bevelled bar in front of the cables, its two arms back to the bay,
    bolted to the sill and the lintel."""
    fr = _north(args=args)
    bar = M(G.slab(fr, G.rect(-0.03, 0.03, 1.1, 1.45), 0.0, 0.03, 0.008),
            G.slab(fr, G.rect(-0.03, 0.03, 1.1, 1.14), -0.2, 0.03, 0.006),
            G.slab(fr, G.rect(-0.03, 0.03, 1.41, 1.45), -0.2, 0.03, 0.006))
    bolts = M(*[G.slab(fr, [(0.009 * math.cos(math.pi * i / 3), v + 0.009 * math.sin(math.pi * i / 3))
                            for i in range(6)], 0.03, 0.037, 0.002) for v in (1.15, 1.4)])
    return [P("strap", bar, "int_silver_c"), P("bolts", bolts, "int_bolt")]


def cor_wall_up(args, layout):
    hl = args["length"] / 2
    prof = _prof(args)
    a, b = prof[1], prof[2]
    vdir = (0.0, b[0] - a[0], b[1] - a[1])
    vlen = math.hypot(vdir[1], vdir[2])
    fr = G.Frame((0.0, a[0], FLOOR + a[1]), (1, 0, 0), vdir, (0.0, vdir[2], -vdir[1]))
    e = hl - 0.006
    tone = "int_silver_b" if args.get("tone", "a") == "a" else "int_silver_a"
    body = [G.slab(fr, G.rect(-hl, hl, 0.0, vlen), -0.2, 0.0)]
    panels = [G.pillow(fr, -e, e, 0.05, vlen - 0.03, 0.0, 0.03, 0.065, 0.012)]
    if a[1] > PROF[1][1] + 0.01:  # the mouth: a vertical panel from the bay's lintel up to the chamfer
        fv = _north(args=args)
        body.append(G.slab(fv, G.rect(-hl, hl, PROF[1][1], a[1]), -0.2, 0.0))
        panels.append(G.pillow(fv, -e, e, PROF[1][1] + 0.05, a[1] - 0.03, 0.0, 0.03, 0.065, 0.012))
    return [P("body", M(*body), "int_silver_b"), P("panel", M(*panels), tone)]


def cor_ceil(args, layout):
    hl = args["length"] / 2
    prof = _prof(args)
    top, w = prof[2][1], prof[3][0]
    fr = G.Frame((0.0, 0.0, FLOOR + top), (1, 0, 0), (0, 1, 0), (0, 0, -1))
    e = hl - 0.006
    return [P("body", G.slab(fr, G.rect(-hl, hl, -w, w), -0.2, 0.0), "int_silver_b"),
            P("panels", M(G.slab(fr, G.rect(-e, e, -w + 0.02, -0.05), 0.0, 0.03, 0.01),
                          G.slab(fr, G.rect(-e, e, 0.05, w - 0.02), 0.0, 0.03, 0.01)), "int_silver_a"),
            P("spine", G.slab(fr, G.rect(-hl, hl, -0.03, 0.03), -0.02, 0.0), "int_dark")]


def cor_ceil_rib(args, layout):
    """inside-fix: a rib across the corridor's flat ceiling between the arches (the night build's ceiling beams): a
    bevelled 12 cm beam 7 cm deep from one slanted wall's top to the other, a dark seam along it; never down the
    walls (the breaker boards' plain wall)."""
    prof = _prof(args)
    top, w = prof[2][1], prof[3][0]
    fr = G.Frame((0.0, 0.0, FLOOR + top), (1, 0, 0), (0, 1, 0), (0, 0, -1))
    return [P("beam", G.slab(fr, G.rect(-0.06, 0.06, -w, w), 0.0, 0.07, 0.015), "int_silver_c"),
            P("seam", G.slab(fr, G.rect(-0.012, 0.012, -w + 0.06, w - 0.06), 0.07, 0.074), "int_dark")]


def cor_arch(args, layout):
    """A rib frame across the corridor (local x = 0; corridor.jpg): a 0.2 m deep band 18 cm into the corridor,
    chamfered 3 cm on both faces, and a raised inner rim (the cyan strip's seat), stepped and chamfered again."""
    prof, i = _prof(args), args.get("inset", 0.18)  # polish 4: the mouth's arch 0.08 (its 0.18 narrowed the opening)
    inner = [(u, max(0.0, v)) for u, v in G.inset(prof, i)]
    outer = [(u, max(0.0, v)) for u, v in G.inset(prof, -0.03)]
    rim = [(u, max(0.0, v)) for u, v in G.inset(prof, i - 0.065)]
    out, lip = [], []
    for n in ((-1, 0, 0), (1, 0, 0)):
        fr = G.Frame((0.0, 0.0, FLOOR), (0, 1, 0), (0, 0, 1), n)
        out.append(G.band(fr, inner, outer, 0.0, 0.1, 0.03, range(5)))
        lip.append(G.band(fr, inner, rim, 0.1, 0.13, 0.012, range(5)))
    return [P("arch", M(*out), "int_silver_c"), P("rim", M(*lip), "int_silver_a")]


def cor_arch_strip(args, layout):
    """The cyan strips on both faces of an arch's inner rim, up one side (side -1: -y, +1: +y)."""
    edges = (0, 1) if args["side"] < 0 else (3, 4)
    i = args.get("inset", 0.18)
    a = [(u, max(0.0, v)) for u, v in G.inset(_prof(args), i - 0.045)]
    b = [(u, max(0.0, v)) for u, v in G.inset(_prof(args), i - 0.02)]
    out = []
    for n in ((-1, 0, 0), (1, 0, 0)):
        fr = G.Frame((0.0, 0.0, FLOOR), (0, 1, 0), (0, 0, 1), n)
        out.append(G.band(fr, a, b, 0.13, 0.138, 0.0, edges))
    return [P("strip", M(*out), "int_cyan")]


def th_arch(args, layout):
    """rebuild D: the throat's arch at its roof line in the corridors' arch style (cor_arch's band, stepped rim and
    cyan strips), over the ceiling and both chamfers only, so the vents' plain walls below stay clear; args half (the
    walls' half width in the cut across the throat's axis) and k (the chamfer's lean in that cut)."""
    prof, i = _prof({**args, "prof": "throat"}), 0.18
    edges = (1, 2, 3)
    inner, outer, rim = G.inset(prof, i), G.inset(prof, -0.03), G.inset(prof, i - 0.065)
    a, b = G.inset(prof, i - 0.045), G.inset(prof, i - 0.02)
    arch, lip, strip = [], [], []
    for n in ((-1, 0, 0), (1, 0, 0)):
        fr = G.Frame((0.0, 0.0, FLOOR), (0, 1, 0), (0, 0, 1), n)
        arch.append(G.band(fr, inner, outer, 0.0, 0.1, 0.03, edges))
        lip.append(G.band(fr, inner, rim, 0.1, 0.13, 0.012, edges))
        strip.append(G.band(fr, a, b, 0.13, 0.138, 0.0, edges))
    return [P("arch", M(*arch), "int_silver_c"), P("rim", M(*lip), "int_silver_a"), P("strip", M(*strip), "int_cyan")]


# --- rebuild C: the throat (hall-relative plan coordinates, placed at the hall's centre) -------------------------
def _clip2(poly, a, b, c):
    """A convex plan polygon's part with a x + b y <= c."""
    out = []
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        fp, fq = a * p[0] + b * p[1] - c, a * q[0] + b * q[1] - c
        if fp <= 1e-9:
            out.append(p)
        if (fp < -1e-9 < fq) or (fq < -1e-9 < fp):
            s = fp / (fp - fq)
            out.append((p[0] + s * (q[0] - p[0]), p[1] + s * (q[1] - p[1])))
    return out


def _wall_line(sx, inset=0.0):
    """(a, b, c) of the half plane inside the throat's east (sx 1) or west (-1) wall, `inset` in from its face."""
    (mx, my), (kx, ky) = TH_PTS[1], TH_PTS[2]
    ln = math.hypot(kx - mx, ky - my)
    n = (sx * (ky - my) / ln, -(kx - mx) / ln)       # outward
    return n[0], n[1], n[0] * sx * mx + n[1] * my - inset


def throat_pieces(inset=0.0, y0=None, y1=None, cut_x=None):
    """The throat's floor or ceiling region as convex plan polygons: between the walls (`inset` in), y0 <= y <= y1,
    outside the hall's 16-gon (one piece per sub-facet's wedge, plus the part forward of the hall's front vertex);
    cut_x: also |x| >= cut_x (the floor's grate strip left out)."""
    big = [(-12.0, -12.0), (12.0, -12.0), (12.0, 12.0), (-12.0, 12.0)]
    for sx in (1, -1):
        big = _clip2(big, *_wall_line(sx, inset))
    if y0 is not None:
        big = _clip2(big, 0.0, -1.0, -y0)
    if y1 is not None:
        big = _clip2(big, 0.0, 1.0, y1)
    a0, a1 = -180.0 - TH_CORNER, TH_CORNER
    out = []
    for i in range(TH_SUBS):
        b0, b1 = a0 + (a1 - a0) * i / TH_SUBS, a0 + (a1 - a0) * (i + 1) / TH_SUBS
        m, ph = D((b0 + b1) / 2), D((b1 - b0) / 2)
        apo = HV * math.cos(ph)
        q = _clip2(big, -math.cos(m), -math.sin(m), -apo)                               # outside the sub-facet's edge
        q = _clip2(q, math.sin(D(b0)), -math.cos(D(b0)), 0.0)                            # on its side of the rays
        q = _clip2(q, -math.sin(D(b1)), math.cos(D(b1)), 0.0)
        out.append(q)
    pieces = []
    for q in out:
        if cut_x:
            pieces += [_clip2(q, 1.0, 0.0, -cut_x), _clip2(q, -1.0, 0.0, -cut_x)]
        else:
            pieces.append(q)
    return [q for q in pieces if len(q) >= 3 and abs(G.area2(q)) > 1e-4]


def throat_floor(args, layout):
    """The throat's floor from the mouth to the hall's rim plates: solid plates either side of a grate strip down its
    middle (the corridors' grate, bevelled rim and bolts), the dark slab under it all (its underside open below the
    nose: J's notch)."""
    fr = G.floor_frame(0.0)
    my, gy = TH_PTS[1][1], -HV - 0.22
    mid = [_clip2(_clip2(q, 1.0, 0.0, 0.88), -1.0, 0.0, 0.88) for q in throat_pieces(0.0, gy, None)]
    plates = [G.slab(fr, q, FLOOR - 0.035, FLOOR, 0.006) for q in throat_pieces(0.0, my, None, 0.88)
              + [q for q in mid if len(q) >= 3 and abs(G.area2(q)) > 1e-4]]
    base = [(-12.0, -12.0), (12.0, -12.0), (12.0, 12.0), (-12.0, 12.0)]
    for sx in (1, -1):
        base = _clip2(base, *_wall_line(sx, -0.2))
    base = _clip2(_clip2(base, 0.0, -1.0, -my), 0.0, 1.0, TH_PTS[2][1])
    t = 0.05
    rim = M(G.slab(fr, G.rect(-0.88, -0.88 + t, my, gy), FLOOR - 0.035, FLOOR + 0.008, 0.007),
            G.slab(fr, G.rect(0.88 - t, 0.88, my, gy), FLOOR - 0.035, FLOOR + 0.008, 0.007),
            *[G.slab(fr, G.rect(-0.88 + t, 0.88 - t, y, y + t), FLOOR - 0.035, FLOOR + 0.008, 0.007)
              for y in (my, gy - t, (my + gy) / 2 - t / 2)])
    bolts = M(*[hex_bolt(x, y, FLOOR + 0.008) for x in (-0.855, 0.855) for y in (my + 0.03, (my + gy) / 2, gy - 0.03)])
    grates = M(G.rect_grate(-0.88 + t, 0.88 - t, my + t, (my + gy) / 2 - t / 2, FLOOR - 0.035, FLOOR),
               G.rect_grate(-0.88 + t, 0.88 - t, (my + gy) / 2 + t / 2, gy - t, FLOOR - 0.035, FLOOR))
    return [P("plates", M(*plates), "int_plate"), P("base", G.slab(fr, base, FLOOR - 0.25, FLOOR - 0.035), "int_dark"),
            P("grate", grates, "int_grate"), P("rim", rim, "int_silver_c"), P("bolts", bolts, "int_bolt")]


def throat_ceil(args, layout):
    """The throat's ceiling from its roof line aft to the hall's rim: the corridors' flat ceiling (a body, panels and
    a dark spine) between the walls' chamfer tops, and the header under the hall's rim over each sub-facet, down
    to the ceiling (to the chamfer near the corners)."""
    top = FLOOR + TH_H
    fr = G.Frame((0.0, 0.0, top), (1, 0, 0), (0, 1, 0), (0, 0, -1))
    fl = lambda q: [(x, y) for x, y in q]
    body = [G.slab(G.floor_frame(0.0), q, top, top + 0.12) for q in throat_pieces(TH_IN, TH_ROOF, None)]
    panels = [G.slab(G.floor_frame(0.0), G.inset(q, 0.03), top - 0.03, top, 0.01)
              for q in throat_pieces(TH_IN + 0.02, TH_ROOF + 0.03, None, 0.05)]
    spine = [G.slab(G.floor_frame(0.0), q, top - 0.02, top) for q in throat_pieces(TH_IN, TH_ROOF, None)
             if min(abs(x) for x, _ in q) < 0.05]
    spine = [G.slab(G.floor_frame(0.0), G.rect(-0.03, 0.03, TH_ROOF, -HV), top - 0.02, top)]
    head = []
    a0, a1 = -180.0 - TH_CORNER, TH_CORNER
    for i in range(TH_SUBS):
        b0, b1 = a0 + (a1 - a0) * i / TH_SUBS, a0 + (a1 - a0) * (i + 1) / TH_SUBS
        p0 = (HV * math.cos(D(b0)), HV * math.sin(D(b0)))
        p1 = (HV * math.cos(D(b1)), HV * math.sin(D(b1)))
        ln = math.dist(p0, p1)
        ex = ((p1[0] - p0[0]) / ln, (p1[1] - p0[1]) / ln)
        nrm = (ex[1], -ex[0])                                    # outward, into the throat
        fv = G.Frame((p0[0], p0[1], FLOOR), (ex[0], ex[1], 0.0), (0, 0, 1), (nrm[0], nrm[1], 0.0))
        def low(s):   # the throat's ceiling or chamfer under the edge point s along it
            x, y = p0[0] + ex[0] * s, p0[1] + ex[1] * s
            d = min(-(a * x + b * y - c) for a, b, c in (_wall_line(1), _wall_line(-1)))
            return TH_BEND + (TH_H - TH_BEND) * min(1.0, max(0.0, d) / TH_IN)
        ss = [0.0, ln]
        for s in [ln * k / 12 for k in range(1, 12)]:
            ss.append(s)
        ss = sorted(ss)
        for s0, s1 in zip(ss, ss[1:]):
            head.append(G.slab(fv, [(s0, low(s0)), (s1, low(s1)), (s1, H_HALL), (s0, H_HALL)], -0.2, 0.0))
    return [P("body", M(*body), "int_silver_b"), P("panels", M(*panels), "int_silver_a"),
            P("spine", M(*spine), "int_dark"), P("header", M(*head), "int_silver_b")]


# --- the tip rooms (built for the east room, centre at the origin; the west one is turned 180) ----------------------
def _tv(a):
    return (R_TIP * math.cos(D(a)), R_TIP * math.sin(D(a)))


def tip_floor_base(args, layout):
    poly = [(x * 2.35 / R_TIP, y * 2.35 / R_TIP) for x, y in map(_tv, sorted(tip_vertices()))]
    return [P("base", G.slab(G.floor_frame(0.0), poly, FLOOR - 0.25, FLOOR - 0.04), "int_dark")]


def tip_rim_polys() -> list[list[tuple[float, float]]]:
    """The tip room's solid floor plates (plan polygons, east room's frame): one per wall edge from 0.3 m in to the
    wall; at the corridor chord two slivers where the ring is inside the chord and the portal's plate out to the
    corridor's end. inside-fix: the v2 door plate ran the ring (r 1.5, out to x -1.5) past the chord (-1.04) and the
    corridor's end (-1.19): a self-crossing polygon, the black shard on the floor by the door."""
    ri = R_TIP - 0.3  # v2: the plates' inner edge 0.3 m in from the wall (v1 at 1.8 in a 2.1 room)
    polys = []
    for a0, a1 in tip_edges():
        v0, v1 = _tv(a0), _tv(a1)
        if a1 - a0 > 2 * DOOR_HALF - 1:
            t = math.degrees(math.acos(max(-1.0, v0[0] / ri)))   # where the ring meets the chord's line
            polys.append(G.arc(ri, D(a0) + 0.003 / ri, D(t)) + [v0])
            polys.append(G.arc(ri, D(360.0 - t), D(a1) - 0.003 / ri) + [v1])
            ce = COR_X1 - TIP_X + 0.001
            polys.append([v0, v1, (ce, -COR_HALF), (ce, COR_HALF)])
        else:
            polys.append(G.arc(ri, D(a0) + 0.003 / ri, D(a1) - 0.003 / ri) + [v1, v0])
    return polys


def tip_floor_rim(args, layout):
    fr = G.floor_frame(0.0)
    plates = [G.slab(fr, poly, FLOOR - 0.035, FLOOR, 0.006) for poly in tip_rim_polys()]
    return [P("plates", M(*plates), "int_plate")]


def _slant(parts, h0):
    """Every vertex of the parts at h0 or above raised by the lens ceiling's slant at its x (the room's axis)."""
    for p in parts:
        p["verts"] = [(x, y, h + (tip_clear(x) - H_TIP if h >= h0 - 1e-9 else 0.0)) for x, y, h in p["verts"]]
    return parts


def _clip_box(poly, x0, x1, y0, y1):
    """A convex plan polygon clipped to the box (Sutherland-Hodgman); [] when less than a triangle is left."""
    pts = list(poly)
    for k, v, sign in ((0, x0, 1.0), (0, x1, -1.0), (1, y0, 1.0), (1, y1, -1.0)):
        out = []
        for i, p in enumerate(pts):
            q = pts[i - 1]
            dp, dq = sign * (p[k] - v), sign * (q[k] - v)
            if (dp >= 0) != (dq >= 0):
                f = dq / (dq - dp)
                out.append((q[0] + (p[0] - q[0]) * f, q[1] + (p[1] - q[1]) * f))
            if dp >= 0:
                out.append(p)
        pts = out
        if len(pts) < 3:
            return []
    return pts


def tip_ceiling_cells():
    """The ceiling's cells round the roof windows: plan boxes (x0, x1, y0, y1) in the room's frame that tile the room
    but the windows (bands along the axis at the windows' edges)."""
    xs = sorted({round(v, 4) for w in ROOF_WINS for v in w[:2]})
    big = 9.0
    cells = []
    for x0, x1 in zip([-big] + xs, xs + [big]):
        holes = sorted((w[2], w[3]) for w in ROOF_WINS if w[0] <= x0 + 1e-6 and x1 <= w[1] + 1e-6)
        ys = [-big] + [v for h in holes for v in h] + [big]
        cells += [(x0, x1, ys[2 * i], ys[2 * i + 1]) for i in range(len(ys) // 2)]
    return cells


def tip_ceiling(args, layout):
    """lens step 1: the lens room's ceiling, a coffered plane slanting down outward (tip_clear) with the three roof
    windows: the slab and the face panels per cell round the windows, each window's frame, well and glass, four ribs
    across the axis with cyan strips, and the fascia over the walls' tops (the slant's gap)."""
    rim = FLOOR + H_TIP
    room = [_tv(a) for a in sorted(tip_vertices())]
    wide = [(x * (R_TIP + 0.25) / R_TIP, y * (R_TIP + 0.25) / R_TIP) for x, y in room]
    slab, faces = [], {"int_silver_a": [], "int_silver_b": []}
    for i, (x0, x1, y0, y1) in enumerate(tip_ceiling_cells()):
        cw = _clip_box(wide, x0, x1, y0, y1)
        if cw:
            slab.append(G.slab(G.floor_frame(0.0), cw, rim, rim + 0.12))
        cf = _clip_box(room, x0 + 0.03, x1 - 0.03, y0 + 0.03, y1 - 0.03)
        if cf:
            faces["int_silver_a" if i % 2 else "int_silver_b"].append(G.slab(G.floor_frame(0.0), cf, rim - 0.025, rim))
    frame, well, glass = [], [], ([], [])
    for x0, x1, y0, y1 in ROOF_WINS:
        e = 0.06
        for bx in ((x0 - e, x1 + e, y0 - e, y0), (x0 - e, x1 + e, y1, y1 + e), (x0 - e, x0, y0, y1), (x1, x1 + e, y0, y1)):
            frame.append(G.bbox(*bx, rim - 0.05, rim + 0.01))
        t = 0.025
        for bx in ((x0, x1, y0, y0 + t), (x0, x1, y1 - t, y1), (x0, x0 + t, y0, y1), (x1 - t, x1, y0, y1)):
            well.append(G.bbox(*bx, rim, rim + 0.26))
        gv, gf = glass
        k = len(gv)
        gv += [(x0, y0, rim + 0.24), (x1, y0, rim + 0.24), (x1, y1, rim + 0.24), (x0, y1, rim + 0.24)]
        gf += [(k, k + 1, k + 2, k + 3), (k + 3, k + 2, k + 1, k)]
    ribs, strips = [], []
    apo = R_TIP * math.cos(D(TIP_STEP / 2))
    for x, w in ((-1.0, 0.05), (-0.55, 0.05), (0.825, 0.025), (1.8, 0.05)):
        yh = math.sqrt(max(apo ** 2 - x ** 2, 0.0)) - 0.03
        ribs.append(G.bbox(x - w, x + w, -yh, yh, rim - 0.09, rim - 0.02))
        if w > 0.03:
            strips.append(G.bbox(x - 0.012, x + 0.012, -yh + 0.15, yh - 0.15, rim - 0.096, rim - 0.09))
    fv, ff = [], []
    for a0, a1 in tip_edges():
        if a1 - a0 > 2 * DOOR_HALF - 1:   # the door's chord: its portal reaches the ceiling
            continue
        (x0, y0), (x1, y1) = _tv(a0), _tv(a1)
        k = len(fv)
        fv += [(x0, y0, rim - 0.11), (x1, y1, rim - 0.11), (x1, y1, rim + 0.005), (x0, y0, rim + 0.005)]
        ff += [(k, k + 1, k + 2, k + 3), (k + 3, k + 2, k + 1, k)]
    parts = [P("slab", M(*slab), "int_silver_b"), P("frames", M(*frame), "int_silver_c"),
             P("wells", M(*well), "int_dark"), P("ribs", M(*ribs), "int_silver_c"), P("strips", M(*strips), "int_cyan"),
             L.part("glass", *glass, "int_glass", solid=False), L.part("fascia", fv, ff, "int_silver_c", solid=False)]
    parts += [P(f"face_{m[-1]}", M(*v), m) for m, v in faces.items() if v]
    return _slant(parts, rim - 0.1)


def tip_window(args, layout):
    """lens step 1 (revived from v2's tip_window_frame, one facet): a window facet of the lens room's band: the low
    wall and its panel under the sill, the sill ledge, the header over the head and its trim (the glass: tip_glass)."""
    hw, tone = R_TIP * math.sin(D(TIP_STEP / 2)), args.get("tone", "a")
    fr = G.wall_frame(FLOOR)
    lo, hi = ("int_silver_a", "int_silver_b") if tone == "a" else ("int_silver_b", "int_silver_a")
    return [P("body", M(G.slab(fr, G.rect(-hw, hw, 0.0, SILL), -0.2, 0.0), G.slab(fr, G.rect(-hw, hw, HEAD, H_TIP), -0.2, 0.0)),
              "int_silver_b"),
            P("kick", G.slab(fr, G.rect(-hw + 0.04, hw - 0.04, 0.0, 0.16), 0.0, 0.015), "int_dark"),
            P("panel", G.slab(fr, G.rect(-hw + 0.04, hw - 0.04, 0.2, SILL - 0.12), 0.0, 0.03, 0.01), lo),
            P("sill", G.slab(fr, G.rect(-hw - 0.01, hw + 0.01, SILL - 0.1, SILL), 0.0, 0.16, 0.03), "int_silver_c"),
            P("trim", G.slab(fr, G.rect(-hw, hw, HEAD, H_TIP - 0.02), 0.0, 0.06, 0.012), hi)]


def tip_glass(args, layout):
    """The glass of one window facet, a single pane 6 cm behind the wall's face (both windings)."""
    hw = R_TIP * math.sin(D(TIP_STEP / 2))
    x = 0.06
    v = [(x, -hw, FLOOR + SILL), (x, hw, FLOOR + SILL), (x, hw, FLOOR + HEAD), (x, -hw, FLOOR + HEAD)]
    return [L.part("glass", v, [(0, 1, 2, 3), (3, 2, 1, 0)], "int_glass", solid=False)]


def tip_mullion(args, layout):
    """A window vertex's mullion from the sill to the head (origin at the vertex), with a thin outer bar."""
    fr = G.wall_frame(FLOOR)
    return [P("mullion", M(G.slab(fr, G.rect(-0.045, 0.045, SILL - 0.02, HEAD + 0.02), -0.12, 0.08, 0.015),
                           G.slab(fr, G.rect(-0.018, 0.018, SILL, HEAD), 0.08, 0.1, 0.006)), "int_silver_c")]


def tip_sill_strip(args, layout):
    """The cyan strip along one window facet's sill ledge (revived from v2)."""
    hw = R_TIP * math.sin(D(TIP_STEP / 2))
    return [P("strip", G.slab(G.wall_frame(FLOOR), G.rect(-hw + 0.03, hw - 0.03, SILL - 0.075, SILL - 0.045), 0.16,
                              0.17), "int_cyan")]


# --- the vault (lens step 1): the hall's shut door and the closet behind it, a shell only ---------------------------
_VAULT = _ROOM["vault"]
VAULT_W = (_VAULT["x"][1] - _VAULT["x"][0]) / 2                       # 0.9
VAULT_L = _VAULT["y"][1] - _VAULT["y"][0]                             # 2.0
VAULT_H, VAULT_H_BACK = _VAULT["clear_h"], _VAULT["clear_h_back"]       # 2.3 at the door, 1.6 at the back
DOOR_HALF_W, DOOR_H = _VAULT["door"]["width_m"] / 2, 2.1


def hall_door(args, layout):
    """The vault's door in the hall's back wall: a flat chord over the two back facets (origin on its face, the hall
    toward -x) with the door's opening and (lens step 2) a ship hatch: a stepped frame in the corridors' arch style
    with a cyan strip in its header, the CLOSED sliding leaf (two recessed panels, a dark groove, a cyan strip along
    its leading edge; no handle), a card reader beside it with a small dim light; the soffit closing the ceiling's
    rim behind the chord. No logic: the hatch stays shut."""
    hw, apo, h = args["half"], args["apo"], H_HALL
    fr = G.wall_frame(FLOOR)
    d, dh = DOOR_HALF_W, DOOR_H
    body = M(G.slab(fr, G.rect(-hw, -d, 0.0, h), -0.2, 0.0), G.slab(fr, G.rect(d, hw, 0.0, h), -0.2, 0.0),
             G.slab(fr, G.rect(-d, d, dh, h), -0.2, 0.0))
    frame = M(G.slab(fr, G.rect(-d - 0.15, -d, 0.0, dh + 0.15), 0.0, 0.07, 0.015),
              G.slab(fr, G.rect(d, d + 0.15, 0.0, dh + 0.15), 0.0, 0.07, 0.015),
              G.slab(fr, G.rect(-d, d, dh, dh + 0.15), 0.0, 0.07, 0.015))
    step = M(G.slab(fr, G.rect(-d - 0.05, -d, 0.0, dh + 0.05), -0.06, 0.035),
             G.slab(fr, G.rect(d, d + 0.05, 0.0, dh + 0.05), -0.06, 0.035),
             G.slab(fr, G.rect(-d, d, dh, dh + 0.05), -0.06, 0.035))
    strip = G.slab(fr, G.rect(-d + 0.04, d - 0.04, dh + 0.075, dh + 0.1), 0.0, 0.075)
    side = M(*[G.slab(fr, G.rect(a, b, 0.2, h - 0.95), 0.0, 0.025, 0.01) for a, b in ((-hw + 0.05, -d - 0.16), (d + 0.16, hw - 0.05))])
    kick = M(*[G.slab(fr, G.rect(a, b, 0.0, 0.16), 0.0, 0.015) for a, b in ((-hw + 0.05, -d - 0.15), (d + 0.15, hw - 0.05))])
    upper = G.slab(fr, G.rect(-hw + 0.05, hw - 0.05, h - 0.8, h - 0.06), 0.0, 0.03, 0.01)
    belt = G.slab(fr, G.rect(-hw, hw, h - 0.9, h - 0.84), 0.0, 0.05, 0.012)
    leaf = G.slab(fr, G.rect(-d, d, 0.0, dh), -0.12, -0.06)
    panels = M(G.slab(fr, G.rect(-d + 0.07, d - 0.16, 0.1, 0.98), -0.06, -0.048, 0.006),
               G.slab(fr, G.rect(-d + 0.07, d - 0.16, 1.1, dh - 0.1), -0.06, -0.048, 0.006))
    groove = G.slab(fr, G.rect(-d, d - 0.12, 1.02, 1.06), -0.06, -0.056)
    edge = G.slab(fr, G.rect(d - 0.1, d - 0.07, 0.15, dh - 0.15), -0.06, -0.052)
    reader = G.slab(fr, G.rect(d + 0.22, d + 0.34, 1.12, 1.38), 0.0, 0.045, 0.008)
    light = G.slab(fr, G.rect(d + 0.25, d + 0.31, 1.29, 1.33), 0.045, 0.05)
    tri = [(0.0, -hw), (HV - apo, 0.0), (0.0, hw)]
    soffit = G.slab(G.floor_frame(0.0), tri, FLOOR + h, FLOOR + h + 0.08)
    return [P("body", body, "int_silver_b"), P("trim", M(frame, belt), "int_silver_c"), P("step", step, "int_dark"),
            P("side", side, "int_silver_a"), P("kick", kick, "int_dark"), P("upper", upper, "int_silver_a"),
            P("leaf", leaf, "int_silver_a"), P("leaf_panels", panels, "int_silver_b"), P("groove", groove, "int_dark"),
            P("strips", M(strip, edge), "int_cyan"), P("reader", reader, "int_dark"), P("lamp", light, "int_cyan"),
            P("soffit", soffit, "int_silver_b")]


def vault_top(y: float) -> float:
    """The vault's ceiling over the deck, y from its door-side clear face (2.3 there, 1.6 at the back)."""
    return VAULT_H + (VAULT_H_BACK - VAULT_H) * y / VAULT_L


def vault_shell(args, layout):
    """The vault's shell (origin at its door-side clear face's middle, y aft): floor, walls with the corridors'
    panels (kick, lower panel, belt, upper panel), the door's lining, the ceiling slanting down aft, two ribs and a
    lamp. Wall and panel heights over 1.5 m follow the ceiling; the ceiling and what hangs from it drop with it."""
    w, ln, t = VAULT_W, VAULT_L, 0.2
    d = DOOR_HALF_W
    top = FLOOR + VAULT_H + 0.12
    walls = [G.bbox(-w - t, -w, -t, ln + t, FLOOR - 0.25, top), G.bbox(w, w + t, -t, ln + t, FLOOR - 0.25, top),
             G.bbox(-w, w, ln, ln + t, FLOOR - 0.25, top), G.bbox(-w, -d - 0.1, -t, 0.0, FLOOR - 0.25, top),
             G.bbox(d + 0.1, w, -t, 0.0, FLOOR - 0.25, top), G.bbox(-d - 0.1, d + 0.1, -t, 0.0, FLOOR + DOOR_H + 0.1, top)]
    lining = [G.bbox(-d - 0.1, -d, -0.45, 0.0, FLOOR, FLOOR + DOOR_H + 0.1), G.bbox(d, d + 0.1, -0.45, 0.0, FLOOR, FLOOR + DOOR_H + 0.1),
              G.bbox(-d, d, -0.45, 0.0, FLOOR + DOOR_H, FLOOR + DOOR_H + 0.1)]
    floor = [G.bbox(-w - t, w + t, -t, ln + t, FLOOR - 0.25, FLOOR - 0.04)]
    plate = [G.bbox(-w, w, 0.0, ln, FLOOR - 0.04, FLOOR)]
    kick, low, belt, up = [], [], [], []
    for sx in (-1, 1):   # the side walls' panels, two along each
        for y0, y1 in ((0.05, 0.97), (1.03, 1.95)):
            f0, f1 = (w - 0.015, w) if sx > 0 else (-w, -w + 0.015)
            g0, g1 = (w - 0.025, w) if sx > 0 else (-w, -w + 0.025)
            kick.append(G.bbox(f0, f1, y0, y1, FLOOR, FLOOR + 0.16))
            low.append(G.bbox(g0, g1, y0, y1, FLOOR + 0.2, FLOOR + 1.35))
            up.append(G.bbox(g0, g1, y0, y1, FLOOR + 1.58, FLOOR + VAULT_H - 0.05))
        b0, b1 = (w - 0.04, w) if sx > 0 else (-w, -w + 0.04)
        belt.append(G.bbox(b0, b1, 0.0, ln, FLOOR + 1.4, FLOOR + 1.52))
    for x0, x1 in ((-0.85, -0.03), (0.03, 0.85)):   # the back wall's
        kick.append(G.bbox(x0, x1, ln - 0.015, ln, FLOOR, FLOOR + 0.16))
        low.append(G.bbox(x0, x1, ln - 0.025, ln, FLOOR + 0.2, FLOOR + 1.35))
        up.append(G.bbox(x0, x1, ln - 0.025, ln, FLOOR + 1.58, FLOOR + VAULT_H - 0.05))
    belt.append(G.bbox(-w, w, ln - 0.04, ln, FLOOR + 1.4, FLOOR + 1.52))
    ceil = [G.bbox(-w - t, w + t, -t, ln + t, FLOOR + VAULT_H, top)]
    ribs = [G.bbox(-w, w, y - 0.04, y + 0.04, FLOOR + VAULT_H - 0.06, FLOOR + VAULT_H) for y in (0.4, 1.4)]
    housing = [G.bbox(-0.16, 0.16, 0.72, 1.08, FLOOR + VAULT_H - 0.07, FLOOR + VAULT_H)]
    lens = [G.bbox(-0.13, 0.13, 0.75, 1.05, FLOOR + VAULT_H - 0.085, FLOOR + VAULT_H - 0.07)]
    squash = [P("walls", M(*walls), "int_silver_b"), P("lining", M(*lining), "int_silver_c"),
              P("kick", M(*kick), "int_dark"), P("low", M(*low), "int_silver_a"), P("belt", M(*belt), "int_silver_c"),
              P("up", M(*up), "int_silver_a")]
    drop = [P("ceil", M(*ceil), "int_silver_b"), P("ribs", M(*ribs), "int_silver_c"),
            P("housing", M(*housing), "int_silver_c"), P("lens", M(*lens), "int_lamp")]
    for p in squash:   # over 1.5 m: scaled to the ceiling at y
        p["verts"] = [(x, y, h if h <= FLOOR + 1.5 else FLOOR + 1.5 + (h - FLOOR - 1.5) * (vault_top(y) - 1.5) / (VAULT_H - 1.5))
                      for x, y, h in p["verts"]]
    for p in drop:     # rigid: down with the ceiling
        p["verts"] = [(x, y, h + vault_top(y) - VAULT_H) for x, y, h in p["verts"]]
    return squash + drop + [P("floor", M(*floor), "int_dark"), P("plate", M(*plate), "int_plate")]


# --- details -------------------------------------------------------------------------------------------------------
def cup(args, layout):
    """A crushed red party cup lying on its side (16 oz: 15 cm long at scale 1.25), its mouth toward local +x."""
    s = args.get("scale", 1.0)
    body, lip = G.cup(args["seed"])
    big = lambda vf: ([(x * s, y * s, h * s) for x, y, h in vf[0]], vf[1])  # noqa: E731
    return [P("cup", shift(big(body), dh=FLOOR), "int_cup_red"), P("lip", shift(big(lip), dh=FLOOR), "int_cup_white")]


def _blob(rnd, cx, cy, r, n=22, wobble=0.28):
    """A star-shaped puddle outline round (cx, cy): radius r, each point jittered by up to `wobble`."""
    k = [rnd.uniform(0, 2 * math.pi) for _ in range(3)]
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        f = 1 + wobble * (0.5 * math.sin(2 * a + k[0]) + 0.3 * math.sin(3 * a + k[1]) + 0.2 * math.sin(5 * a + k[2]))
        out.append((cx + r * f * math.cos(a) * 1.35, cy + r * f * math.sin(a)))
    return out


def spill(args, layout):
    """A soda spill from a cup's mouth (the cup's own frame: placed with the cup's position and yaw): one flat puddle
    running away along +x and two drops, a 1.5 mm glossy film on the floor."""
    import random
    rnd = random.Random(args["seed"])
    x0 = args.get("from", 0.14)
    k = args.get("size", 1.0)  # inside 3-1: 1.5 with the bigger cups, so the spill reads from the hall's views
    films = [G.slab(G.floor_frame(FLOOR), _blob(rnd, x0 + 0.12 * k, 0.0, 0.11 * k), 0.0003, 0.0018)]
    for dx, dy, r in ((0.32, 0.07, 0.025), (0.36, -0.05, 0.016)):
        films.append(G.slab(G.floor_frame(FLOOR), _blob(rnd, x0 + dx * k, dy * k, r * k, n=12, wobble=0.15), 0.0003,
                            0.0016))
    return [P("spill", M(*films), "int_spill")]


def cable_coil(args, layout):
    """A coil of spare cable left on the floor: a flat spiral of 3.5 turns (r 7..17 cm), its end running out 0.45 m to
    a plug (blue cable, steel plug)."""
    r_c, turns, r0, pitch = 0.012, 3.5, 0.07, 0.028
    pts = []
    n = int(turns * 28)
    for i in range(n + 1):
        a = 2 * math.pi * i / 28
        r = r0 + pitch * a / (2 * math.pi)
        pts.append((r * math.cos(a), r * math.sin(a), FLOOR + r_c + 0.0005))
    end = pts[-1]
    for i in range(1, 9):  # the loose end, curving away
        t = i / 8
        pts.append((end[0] + 0.45 * t, end[1] + 0.12 * math.sin(t * 2.4), FLOOR + r_c + 0.0005))
    tail = pts[-1]
    plug = shift(G.bbox(0.0, 0.07, -0.022, 0.022, 0.0, 0.034, 0.004), tail[0], tail[1], FLOOR)
    pins = M(*[shift(G.bbox(0.07, 0.085, y - 0.003, y + 0.003, 0.012, 0.02), tail[0], tail[1], FLOOR)
               for y in (-0.01, 0.01)])
    return [P("cable", G.tube(pts, r_c, 8), "int_cable_blue"), P("plug", M(plug, pins), "int_bolt")]


def floor_patch(args, layout):
    """A bolted repair plate (u x v m) on solid floor: a 6 mm plate, chamfered, ten bolts round its edge."""
    u, v = args["u"], args["v"]
    plate = G.slab(G.floor_frame(FLOOR), G.rect(-u / 2, u / 2, -v / 2, v / 2), 0.0, 0.006, 0.0025)
    bolts = []
    for i in range(5):
        x = -u / 2 + 0.03 + (u - 0.06) * i / 4
        bolts += [hex_bolt(x, -v / 2 + 0.03, FLOOR + 0.006, 0.009), hex_bolt(x, v / 2 - 0.03, FLOOR + 0.006, 0.009)]
    return [P("plate", plate, "int_patch"), P("bolts", M(*bolts), "int_bolt")]


def rim_bolts(args, layout):
    """The hex bolts down both sides of a hall rim plate's seam (hall_floor_rim's frame: origin at R_RIM_REF)."""
    rs = [R_RIM0 + (R_HALL - R_RIM0) * t for t in (0.2, 0.45, 0.7)]   # inside-1: spread over the wider rim
    return [P("bolts", M(*[hex_bolt(r - R_RIM_REF, y, FLOOR, 0.01) for r in rs for y in (-0.035, 0.035)]),
              "int_bolt")]


def scratches(args, layout):
    """A cluster of fine bright scratches standing 0.6 mm off a flat panel face (local plane x = 0, facing -x)."""
    import random
    rnd = random.Random(args["seed"])
    fr = G.wall_frame(0.0)
    lines = []
    for _ in range(args.get("count", 9)):
        u, v = rnd.uniform(-0.35, 0.35), rnd.uniform(0.05, 0.5)
        ang, ln = rnd.uniform(-0.6, 0.6) + (0.0 if rnd.random() < 0.6 else 1.3), rnd.uniform(0.04, 0.22)
        du, dv = math.cos(ang) * ln / 2, math.sin(ang) * ln / 2
        nu, nv = -math.sin(ang) * 0.0016, math.cos(ang) * 0.0016
        poly = [(u - du - nu, v - dv - nv), (u + du - nu, v + dv - nv), (u + du + nu, v + dv + nv),
                (u - du + nu, v - dv + nv)]
        lines.append(G.slab(fr, poly, 0.0, 0.0006))
    return [P("scratches", M(*lines), "int_scratch")]
