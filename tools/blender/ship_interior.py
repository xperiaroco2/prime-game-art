"""The ship's INTERIOR pieces (art #263, docs/ship.md): the INTERIOR lane owns this file and ship_interior_*.py.

Each builder(args, layout) returns ship_lib parts in the piece's local frame (plan axes x east, y south, h up; metres;
heights absolute from the ground, so a placement's h is an offset). A placement [x, y, h] + yaw (layouts/ship/
interior.toml, written by ship_interior_place.py) moves it; yaw turns a plan angle a into a - yaw. Wall-like pieces are
built at plan angle 0 (their room toward -x) and placed with yaw = -(their angle).

The numbers (ship.toml): the hall a 16-sided room, inner faces at apothem 3.4, rim 3.4 m, apex 4.0 m over the deck at
h 1.0; three openings (mouth north, corridors east and west) two facets wide, framed by portals on the chords; the
corridors one profile (2.5 m wide, vertical to 1.45 m, slanted in to 1.8 m wide at the 2.6 m ceiling) in five modules
from the hall portal to the tip portal; the tip rooms polygons on radius 2.1 (eight window segments over +-65 deg,
three wall facets a side, the corridor chord over +-37.6 deg from the back), rim 2.8 m, apex 3.2 m."""

from __future__ import annotations

import math

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
    "int_cable_red": {"base": (0.32, 0.025, 0.02, 1.0), "metallic": 0.0, "roughness": 0.42},
    "int_cable_black": {"base": (0.018, 0.018, 0.02, 1.0), "metallic": 0.0, "roughness": 0.5},
    "int_cable_blue": {"base": (0.025, 0.07, 0.28, 1.0), "metallic": 0.0, "roughness": 0.42},
    "int_scratch": {"base": (0.85, 0.86, 0.88, 1.0), "metallic": 1.0, "roughness": 0.58},
    "int_cup_red": {"base": (0.6, 0.02, 0.02, 1.0), "metallic": 0.0, "roughness": 0.28},
    "int_cup_white": {"base": (0.86, 0.86, 0.84, 1.0), "metallic": 0.0, "roughness": 0.4},
})

D = math.radians
FLOOR = 1.0
# the hall
N_HALL, R_HALL, H_HALL, APEX_HALL = 16, 3.4, 3.4, 4.0
PHI = math.pi / N_HALL
HV = R_HALL / math.cos(PHI)                # vertex radius 3.467
HW = R_HALL * math.tan(PHI)                # facet half width 0.676
HC = HV * math.cos(2 * PHI)                # an opening's chord (two facets) 3.203
HCH = HV * math.sin(2 * PHI)               # its half width 1.327
R_RING = 1.25                              # the lamp ring and the ceiling's inner edge
OPENINGS = {"corridor_e": 0.0, "mouth": -90.0, "corridor_w": 180.0}   # opening centre angles (deg)
# the corridors: profile (u across, v up from the deck), the five modules between the portals
PROF = [(-1.25, 0.0), (-1.25, 1.45), (-0.9, 2.6), (0.9, 2.6), (1.25, 1.45), (1.25, 0.0)]
H_COR = 2.6
PORTAL_D = 0.15
# the tip rooms
R_TIP, H_TIP, APEX_TIP, R_TIP_RING = 2.1, 2.8, 3.2, 0.6
TIP_X = 10.75
WIN_HALF, DOOR_HALF, SILL, HEAD = 65.0, 37.6, 0.5, 2.4
TIP_CHORD = -R_TIP * math.cos(D(DOOR_HALF))          # -1.664
TIP_CHORD_H = R_TIP * math.sin(D(DOOR_HALF))         # 1.281
COR_X0 = HC + PORTAL_D                               # 3.353
COR_X1 = TIP_X + TIP_CHORD - PORTAL_D                # 8.936
N_MOD = 5
MOD_L = (COR_X1 - COR_X0) / N_MOD                    # 1.117
MOUTH_L = 4.6 - COR_X0                               # the mouth passage, from the hall portal to the ramp hinge


def tip_vertices() -> list[float]:
    """The tip room's vertex angles (deg, east room): window segments, wall facets, the corridor chord."""
    win = [-WIN_HALF + 2 * WIN_HALF * i / 8 for i in range(9)]
    step = (180.0 - DOOR_HALF - WIN_HALF) / 3
    walls = [WIN_HALF + step * i for i in range(1, 4)]
    return win + walls + [-a for a in walls]


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
    return [P("body", G.slab(fr, G.rect(-hw, hw, 0.0, h), -0.2, 0.0), "int_silver_b"),
            P("kick", G.slab(fr, G.rect(-e, e, 0.0, 0.16), 0.0, 0.015), "int_dark"),
            P("main", G.pillow(fr, -e, e, 0.2, belt - 0.05, 0.0, 0.03, 0.09, 0.015), lo),
            P("belt", G.slab(fr, G.rect(-hw, hw, belt, belt + 0.12), 0.0, 0.05, 0.012), "int_silver_c"),
            P("upper", G.slab(fr, G.rect(-e, e, belt + 0.17, h - 0.04), 0.0, 0.03, 0.012), hi)]


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


def cables_v(args, layout):
    """Three cables down a pilaster's channel."""
    h = args.get("height", H_HALL)
    out = []
    for (y, x, r, mat) in ((-0.032, 0.0, 0.019, "int_cable_red"), (0.0, -0.012, 0.023, "int_cable_black"),
                           (0.033, 0.004, 0.016, "int_cable_blue")):
        pts = [(x - 0.012 * math.sin(math.pi * t / 6), y + 0.004 * math.sin(2.3 * t), FLOOR + 0.16 + (h - 0.3) * t / 6)
               for t in range(7)]
        out.append(P(mat[4:], G.tube(pts, r), mat))
    return out


def clip_v(args, layout):
    """A strap across a pilaster's channel holding its cables (placed at a height offset)."""
    fr = G.wall_frame(FLOOR)
    return [P("strap", M(G.slab(fr, G.rect(-0.075, 0.075, 0.0, 0.045), 0.045, 0.058, 0.004),
                         G.slab(fr, G.rect(-0.012, 0.012, 0.012, 0.033), 0.058, 0.064, 0.002)), "int_silver_c")]


def portal(args, layout):
    """The frame of an opening on its chord (local x = 0; the room toward -x, the passage toward +x): the frame band
    round the corridor profile, the header and side fillers up to the rim, the soffit back to the facets (hall)."""
    w, h, soffit = args["half"], args["height"], args.get("soffit", False)
    fr = G.wall_frame(FLOOR)
    outer = [(u, max(0.0, v)) for u, v in G.inset(PROF, -0.1)]
    inner = PROF
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
    return [P("strip", G.band(fr, G.inset(PROF, -0.035), G.inset(PROF, -0.065), 0.045, 0.057, 0.0, edges),
              "int_cyan")]


# --- the hall ------------------------------------------------------------------------------------------------------
def hall_floor_base(args, layout):
    return [P("base", L.disc(3.75, N_HALL, FLOOR - 0.25, FLOOR - 0.035), "int_dark")]


def floor_disc(args, layout):
    """The plain centre disc with its trim ring (hall and tip rooms)."""
    r = args["radius"]
    disc = G.slab(G.floor_frame(0.0), G.arc(r - 0.005, 0.0, 2 * math.pi)[:-1], FLOOR - 0.035, FLOOR, 0.008)
    a = L.angles(0.0, 2 * math.pi, D(6.0))
    trim = M(*[L.sector(r, r + 0.07, p, q, FLOOR - 0.035, FLOOR) for p, q in zip(a, a[1:])])
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
    """One arc of the hall's amber floor ring: a bezel and the light, +-10 deg about angle 0."""
    r, ref = args["radius"], args["radius"]
    a = L.angles(D(-10.0), D(10.0), D(2.5))
    bezel = M(*[L.sector(r - 0.055, r + 0.055, p, q, FLOOR - 0.01, FLOOR + 0.003) for p, q in zip(a, a[1:])])
    light = M(*[L.sector(r - 0.03, r + 0.03, p, q, FLOOR + 0.003, FLOOR + 0.006) for p, q in zip(a, a[1:])])
    return [P("bezel", shift(bezel, -ref), "int_silver_c"), P("light", shift(light, -ref), "int_amber")]


def hall_floor_rim(args, layout):
    """The solid floor plates between the amber ring and a wall facet: two halves with a seam (origin at r 3.0)."""
    g = 0.003
    a = G.arc(2.66, -PHI, -g / 2.66)
    b = G.arc(2.66, g / 2.66, PHI)
    fr = G.floor_frame(0.0)
    halves = M(G.slab(fr, a + [(R_HALL, -g), (R_HALL, -HW)], FLOOR - 0.035, FLOOR, 0.006),
               G.slab(fr, b + [(R_HALL, HW), (R_HALL, g)], FLOOR - 0.035, FLOOR, 0.006))
    return [P("plates", shift(halves, -3.0), "int_plate")]


def hall_threshold(args, layout):
    """The floor plate of an opening, from the amber ring through the portal (origin on the chord)."""
    poly = G.arc(2.66, -2 * PHI, 2 * PHI) + [(HC, HCH), (COR_X0 - 0.001, 1.25), (COR_X0 - 0.001, -1.25), (HC, -HCH)]
    return [P("plate", shift(G.slab(G.floor_frame(0.0), poly, FLOOR - 0.035, FLOOR, 0.006), -HC), "int_plate")]


def ceiling_facet(apo, half, rim_h, r_in, h_in, phi):
    """(frame, polygon) of a conical ceiling facet over an edge centred on angle 0."""
    inner = (r_in * math.cos(phi), r_in * math.sin(phi))
    vdir = (inner[0] - apo, 0.0, h_in - rim_h)
    vlen = math.hypot(vdir[0], vdir[2])
    fr = G.Frame((apo, 0.0, rim_h), (0, 1, 0), vdir, G.cross(G.unit(vdir), (0, 1, 0)))
    return fr, [(-half, 0.0), (half, 0.0), (inner[1], vlen), (-inner[1], vlen)]


def ceiling_panels(fr, poly, tone):
    """A ceiling facet: its body and two triangular face panels split on the diagonal."""
    a, b = ("int_silver_a", "int_silver_b") if tone == "a" else ("int_silver_b", "int_silver_a")
    face = G.inset(poly, 0.09)
    t1 = G.inset([face[0], face[1], face[2]], 0.006)
    t2 = G.inset([face[0], face[2], face[3]], 0.006)
    return [G.slab(fr, poly, -0.15, 0.0), G.slab(fr, t1, 0.0, 0.025, 0.008), G.slab(fr, t2, 0.0, 0.03, 0.008)], (a, b)


def hall_ceil_panel(args, layout):
    h_in = FLOOR + H_HALL + (APEX_HALL - H_HALL) * (1 - R_RING / R_HALL)
    fr, poly = ceiling_facet(R_HALL, HW, FLOOR + H_HALL, R_RING, h_in, PHI)
    (body, t1, t2), (a, b) = ceiling_panels(fr, poly, args.get("tone", "a"))
    return [P("body", shift(body, -R_HALL), "int_silver_b"), P("tri_a", shift(t1, -R_HALL), a),
            P("tri_b", shift(t2, -R_HALL), b)]


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
    cap = L.disc(r - 0.1, 32, h - 0.02, h + 0.08)
    boss = L.disc(r * 0.4, 16, h - 0.08, h - 0.02)
    # the warm band: the beam's whole underside glows (hall_in-3's thick amber ring of light, inside-1)
    band = M(*[L.sector(r - 0.11, r + 0.08, p, q, h - 0.165, h - 0.15) for p, q in zip(a, a[1:])])
    return [P("beam", beam, "int_silver_c"), P("lip", lip, "int_silver_a"), P("cap", cap, "int_silver_b"),
            P("boss", boss, "int_silver_c"), P("band", band, "int_lamp")]


def lamp(args, layout):
    """A lamp fixture under the ring (local y along the ring): housing and warm lens."""
    h = args["h_in"]
    return [P("housing", G.bbox(-0.075, 0.075, -0.17, 0.17, h - 0.2, h - 0.15), "int_silver_c"),
            P("lens", G.bbox(-0.052, 0.052, -0.14, 0.14, h - 0.212, h - 0.2), "int_lamp")]


# --- the corridors and the mouth passage (one module, length from args) ---------------------------------------------
def _north(y=-1.25, h=FLOOR):
    return G.Frame((0.0, y, h), (1, 0, 0), (0, 0, 1), (0, 1, 0))


def cor_floor_base(args, layout):
    hl = args["length"] / 2
    return [P("base", L.box(-hl, hl, -1.45, 1.45, FLOOR - 0.25, FLOOR - 0.04), "int_dark")]


def cor_grate(args, layout):
    hl = args["length"] / 2 - 0.004
    return [P("grate", G.rect_grate(-hl, hl, -0.88, 0.88, FLOOR - 0.035, FLOOR), "int_grate")]


def cor_gutter(args, layout):
    """The solid floor strip along the north wall (the amber dash sits on it)."""
    hl = args["length"] / 2 - 0.004
    return [P("plate", G.slab(G.floor_frame(0.0), G.rect(-hl, hl, -1.25, -0.895), FLOOR - 0.035, FLOOR, 0.008),
              "int_plate")]


def floor_light(args, layout):
    """An amber light bar set in the floor along local x: bezel and light (length from args)."""
    hl = args.get("length", 0.44) / 2
    return [P("bezel", G.bbox(-hl, hl, -0.042, 0.042, FLOOR - 0.002, FLOOR + 0.004, 0.002), "int_silver_c"),
            P("light", G.bbox(-hl + 0.03, hl - 0.03, -0.024, 0.024, FLOOR + 0.004, FLOOR + 0.007), "int_amber")]


def cor_wall_low(args, layout):
    hl = args["length"] / 2
    fr = _north()
    e = hl - 0.006
    tone = "int_silver_a" if args.get("tone", "a") == "a" else "int_silver_b"
    return [P("body", G.slab(fr, G.rect(-hl, hl, 0.0, 1.1), -0.2, 0.0), "int_silver_b"),
            P("kick", G.slab(fr, G.rect(-e, e, 0.0, 0.13), 0.0, 0.015), "int_dark"),
            P("panel", G.slab(fr, G.rect(-e, e, 0.16, 1.05), 0.0, 0.035, 0.012), tone)]


def cor_channel(args, layout):
    """The cable channel at the wall's bend: dark back and two bevelled lips."""
    hl = args["length"] / 2
    fr = _north()
    lips = M(G.slab(fr, G.rect(-hl, hl, 1.07, 1.13), -0.15, 0.035, 0.01),
             G.slab(fr, G.rect(-hl, hl, 1.42, 1.48), -0.15, 0.03, 0.01))
    return [P("back", G.slab(fr, G.rect(-hl, hl, 1.1, 1.45), -0.2, -0.15), "int_dark"), P("lips", lips, "int_silver_c")]


def cor_cables(args, layout):
    hl = args["length"] / 2
    out = []
    for (y, h, r, mat, ph) in ((-1.36, 1.19, 0.024, "int_cable_red", 0.0), (-1.32, 1.27, 0.02, "int_cable_black", 1.3),
                               (-1.35, 1.35, 0.017, "int_cable_blue", 2.1)):
        pts = [(-hl + 2 * hl * t / 8, y + 0.006 * math.sin(math.pi * t / 8 * 2 + ph) * math.sin(math.pi * t / 8),
                FLOOR + h - 0.012 * math.sin(math.pi * t / 8)) for t in range(9)]
        out.append(P(mat[4:], G.tube(pts, r), mat))
    return out


def clip_h(args, layout):
    fr = _north()
    return [P("strap", M(G.slab(fr, G.rect(-0.022, 0.022, 1.12, 1.43), -0.04, -0.025, 0.004),
                         G.slab(fr, G.rect(-0.022, 0.022, 1.12, 1.15), -0.15, -0.025, 0.003),
                         G.slab(fr, G.rect(-0.022, 0.022, 1.40, 1.43), -0.15, -0.025, 0.003)), "int_silver_c")]


def cor_wall_up(args, layout):
    hl = args["length"] / 2
    a, b = PROF[1], PROF[2]
    vdir = (0.0, b[0] - a[0], b[1] - a[1])
    vlen = math.hypot(vdir[1], vdir[2])
    fr = G.Frame((0.0, a[0], FLOOR + a[1]), (1, 0, 0), vdir, (0.0, vdir[2], -vdir[1]))
    e = hl - 0.006
    tone = "int_silver_b" if args.get("tone", "a") == "a" else "int_silver_a"
    return [P("body", G.slab(fr, G.rect(-hl, hl, 0.0, vlen), -0.2, 0.0), "int_silver_b"),
            P("panel", G.pillow(fr, -e, e, 0.05, vlen - 0.03, 0.0, 0.03, 0.065, 0.012), tone)]


def cor_ceil(args, layout):
    hl = args["length"] / 2
    fr = G.Frame((0.0, 0.0, FLOOR + H_COR), (1, 0, 0), (0, 1, 0), (0, 0, -1))
    e = hl - 0.006
    return [P("body", G.slab(fr, G.rect(-hl, hl, -0.9, 0.9), -0.2, 0.0), "int_silver_b"),
            P("panels", M(G.slab(fr, G.rect(-e, e, -0.88, -0.05), 0.0, 0.03, 0.01),
                          G.slab(fr, G.rect(-e, e, 0.05, 0.88), 0.0, 0.03, 0.01)), "int_silver_a"),
            P("spine", G.slab(fr, G.rect(-hl, hl, -0.03, 0.03), -0.02, 0.0), "int_dark")]


def cor_arch(args, layout):
    """A rib arch across the corridor (local x = 0), bevelled on both faces."""
    inner = [(u, max(0.0, v)) for u, v in G.inset(PROF, 0.08)]
    outer = [(u, max(0.0, v)) for u, v in G.inset(PROF, -0.03)]
    out = []
    for n in ((-1, 0, 0), (1, 0, 0)):
        fr = G.Frame((0.0, 0.0, FLOOR), (0, 1, 0), (0, 0, 1), n)
        out.append(G.band(fr, inner, outer, 0.0, 0.09, 0.015, range(5)))
    return [P("arch", M(*out), "int_silver_c")]


def cor_arch_strip(args, layout):
    """The cyan strips on both faces of an arch, up one side (side -1: -y, +1: +y)."""
    edges = (0, 1) if args["side"] < 0 else (3, 4)
    a = [(u, max(0.0, v)) for u, v in G.inset(PROF, 0.055)]
    b = [(u, max(0.0, v)) for u, v in G.inset(PROF, 0.075)]
    out = []
    for n in ((-1, 0, 0), (1, 0, 0)):
        fr = G.Frame((0.0, 0.0, FLOOR), (0, 1, 0), (0, 0, 1), n)
        out.append(G.band(fr, a, b, 0.09, 0.1, 0.0, edges))
    return [P("strip", M(*out), "int_cyan")]


# --- the tip rooms (built for the east room, centre at the origin; the west one is turned 180) ----------------------
def _tv(a):
    return (R_TIP * math.cos(D(a)), R_TIP * math.sin(D(a)))


def tip_floor_base(args, layout):
    poly = [(x * 2.35 / R_TIP, y * 2.35 / R_TIP) for x, y in map(_tv, sorted(tip_vertices()))]
    return [P("base", G.slab(G.floor_frame(0.0), poly, FLOOR - 0.25, FLOOR - 0.04), "int_dark")]


def tip_floor_rim(args, layout):
    fr = G.floor_frame(0.0)
    plates = []
    for a0, a1 in tip_edges():
        arc = G.arc(1.8, D(a0) + 0.003 / 1.8, D(a1) - 0.003 / 1.8)
        if a1 - a0 > 2 * DOOR_HALF - 1:
            v0, v1 = _tv(a0), _tv(a1)
            poly = arc + [v1, (COR_X1 - TIP_X + 0.001, -1.25), (COR_X1 - TIP_X + 0.001, 1.25), v0]
        else:
            poly = arc + [_tv(a1), _tv(a0)]
        plates.append(G.slab(fr, poly, FLOOR - 0.035, FLOOR, 0.006))
    return [P("plates", M(*plates), "int_plate")]


def tip_window_frame(args, layout):
    """The window wall of the tip room: low wall and sill, header, mullions, over the eight segments."""
    half = WIN_HALF / 8
    apo, hw = R_TIP * math.cos(D(half)), R_TIP * math.sin(D(half))
    fr = G.wall_frame(FLOOR, apo)
    body, panel, sill, trim, mull = [], [], [], [], []
    for i in range(8):
        c = -WIN_HALF + half * (2 * i + 1)
        body += [rot(G.slab(fr, G.rect(-hw, hw, 0.0, SILL), -0.2, 0.0), c),
                 rot(G.slab(fr, G.rect(-hw, hw, HEAD, H_TIP), -0.2, 0.0), c)]
        panel.append(rot(G.slab(fr, G.rect(-hw + 0.04, hw - 0.04, 0.05, SILL - 0.09), 0.0, 0.03, 0.01), c))
        sill.append(rot(G.slab(fr, G.rect(-hw - 0.01, hw + 0.01, SILL - 0.06, SILL), 0.0, 0.13, 0.015), c))
        trim.append(rot(G.slab(fr, G.rect(-hw, hw, HEAD, HEAD + 0.09), 0.0, 0.07, 0.012), c))
    for i in range(1, 8):
        a = -WIN_HALF + 2 * half * i
        mull.append(rot(shift(G.slab(G.wall_frame(FLOOR), G.rect(-0.04, 0.04, SILL, HEAD), -0.1, 0.07, 0.012), R_TIP),
                        a))
    return [P("body", M(*body), "int_silver_b"), P("panels", M(*panel), "int_silver_a"),
            P("sill", M(*sill), "int_silver_c"), P("trim", M(*trim), "int_silver_c"),
            P("mullions", M(*mull), "int_silver_c")]


def tip_glass(args, layout):
    half = WIN_HALF / 8
    apo, hw = R_TIP * math.cos(D(half)), R_TIP * math.sin(D(half))
    panes = [rot(G.slab(G.wall_frame(FLOOR, apo + 0.06), G.rect(-hw, hw, SILL - 0.02, HEAD + 0.02), -0.02, 0.0),
                 -WIN_HALF + half * (2 * i + 1)) for i in range(8)]
    return [P("glass", M(*panes), "int_glass")]


def tip_sill_strip(args, layout):
    """The cyan strip along one window segment's sill (origin on the segment)."""
    half = WIN_HALF / 8
    hw = R_TIP * math.sin(D(half))
    return [P("strip", G.slab(G.wall_frame(FLOOR), G.rect(-hw + 0.03, hw - 0.03, SILL - 0.045, SILL - 0.02), 0.13,
                              0.14), "int_cyan")]


def tip_ceiling(args, layout):
    h_in = FLOOR + H_TIP + (APEX_TIP - H_TIP) * (1 - R_TIP_RING / R_TIP)
    out = {"int_silver_b": [], "int_silver_a": []}
    body = []
    for i, (a0, a1) in enumerate(tip_edges()):
        phi = D(a1 - a0) / 2
        fr, poly = ceiling_facet(R_TIP * math.cos(phi), R_TIP * math.sin(phi), FLOOR + H_TIP, R_TIP_RING, h_in, phi)
        (b, t1, t2), (ma, mb) = ceiling_panels(fr, poly, "a" if i % 2 else "b")
        c = (a0 + a1) / 2
        body.append(rot(b, c))
        out[ma].append(rot(t1, c))
        out[mb].append(rot(t2, c))
    return [P("body", M(*body), "int_silver_b"), P("tri_a", M(*out["int_silver_a"]), "int_silver_a"),
            P("tri_b", M(*out["int_silver_b"]), "int_silver_b")]


# --- details -------------------------------------------------------------------------------------------------------
def cup(args, layout):
    body, lip = G.cup(args["seed"])
    return [P("cup", shift(body, dh=FLOOR), "int_cup_red"), P("lip", shift(lip, dh=FLOOR), "int_cup_white")]


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
