"""The throat's gills (art #263; the engineer's choice prime-game#1095 c6470177717, design's row "Ряд у горлі" of
2026-10-28; docs/ship.md "The throat's gills"): `th_gills_e` and its mirror `th_gills_w`, each the whole clean wall
of one throat side under the roof (s 1.62 m from the mouth's corner to the hall's corner K, 4.051): the plinth with
its cyan line, the clean band of the wall's own metal on the throat's profile (vertical to 1.45, then 0.55 in to the
ceiling at 2.30) with two straight seams, five vertical crescent slits cut into it and the round button by the hall.
They replace the throat's wall modules (low, mid, cable bay, upper) and the louvred vent cabinets.

The slit (design's drawing, turned vertical): a circular segment, its chord 1.20 straight up the band on the hall's
side, its arc sagging 0.16 toward the mouth, the tips chamfered to a 2 cm flat; a recess 0.18 deep holding 24
filaments (2 cm thick, 12 cm deep, behind the lip); the lip a faceted plate of the wall's metal 6 cm thick filling the
segment less a 1.5 cm gap round its free edge, a cyan line on that edge, hinged along the chord at its back face
(inside the wall). The chord crosses the profile's bend at 1.45, so every lip is two leaves, `lo` on the vertical part
and `hi` on the lean, each hinged on its own straight piece of the chord (they part by under 1 cm at 25 deg).

Frame: the piece's origin on the wall's line at the mouth's corner (east (1.65, -7.1), west mirrored), local x = s
along the wall toward the hall (the west piece mirrored: local -x), local y into the throat, h absolute. A point is
given in the wall's developed coordinates (u = s, t up the profile from the deck, w out of the surface toward the
room); `point` maps it, the bend's points on the mitre. Plain Python (ship_build.py makes the meshes).

The game drives (Godot, `<piece>_<part>`): `gill3_lip_lo`, `gill3_lip_hi` (east only, origin on the hinge; open by
rotating about LIP_AXES by +angle; 25 deg open, 8 deg the gasp), `gill<k>_fil` (the filaments: material
`int_cyan__gill_fil`), `gill<k>_seam` (the gap's floor, `int_cyan__gill_seam`: calm dim cyan, red for a fault),
`btn_ring` (`int_cyan__gill_ring`) and `btn_dome`; godot/ship/gill_row.gd is the reference controller."""

from __future__ import annotations

import math

import ship_interior as S
import ship_interior_geom as G
import ship_lib as L

P, M = S.P, S.M
FLOOR = S.FLOOR
BEND, IN, TOP = S.TH_BEND, S.TH_IN, S.TH_H            # the throat's wall: vertical to 1.45, then 0.55 in at 2.30
LEAN = math.hypot(IN, TOP - BEND)                      # the lean's length up its slope (1.012)
LV, LH = IN / LEAN, (TOP - BEND) / LEAN                 # its direction (into the room, up)
T_TOP = BEND + LEAN                                     # the band's top in t (the ceiling's edge)
T_OVER = 0.03                                           # the band runs on this far past the ceiling's edge, into it
_MK, _KK = S.TH_PTS[1], S.TH_PTS[2]
WALL_LEN = math.dist(_MK, _KK)                          # 4.051: the mouth's corner to the hall's corner K
WALL_D = ((_KK[0] - _MK[0]) / WALL_LEN, (_KK[1] - _MK[1]) / WALL_LEN)   # the east wall's direction (0.312, 0.950)
WALL_YAW = math.degrees(math.atan2(WALL_D[1], WALL_D[0]))              # 71.80
_MOD = WALL_LEN / 5
S0 = min(i * _MOD for i in range(5) if _MK[1] + (_KK[1] - _MK[1]) * i / 5 >= S.TH_ROOF - 1e-6)   # 1.620: under the roof
PLINTH_H, PLINTH_W = 0.60, 0.03                        # the plinth: 0-60 cm, 3 cm proud of the band
KICK_H = 0.08
BAND = (1.70, 3.95)                                     # the clean band's seams (design: s 1.70-3.95)
SEAM_W = 0.006

# --- the slit (cm in the drawing; m here) ---
SLITS = (1.95, 2.32, 2.69, 3.06, 3.43)                  # the segments' centres along the wall (design's row, 37 cm)
WORKING = 3                                             # the one slit with a working lip (east)
CHORD = 1.20                                            # straight up the band, t 0.75-1.95 along the profile
T_MID = 1.35
SAG = 0.16                                              # the arc's sag from the chord, toward the mouth
CHAMFER = 0.02                                          # the tips cut where the segment is this wide
GAP = 0.015                                             # the shut gap round the lip's free edge and ends
DEPTH = 0.18                                            # the recess
LIP_T = 0.06                                            # the lip's thickness (its back face carries the hinge)
LIP_RIDGE, LIP_RIDGE_AT, LIP_EDGE = 0.012, 0.4, 0.01    # its facets: a ridge 12 mm proud, a 1 cm chamfer on its edge
FILS, FIL_T, FIL_D = 24, 0.02, 0.12                     # the filaments: count, thickness, depth (behind the lip)
OPEN_DEG, GASP_DEG = 25.0, 8.0
R_ARC = (CHORD ** 2 / 4 + SAG ** 2) / (2 * SAG)         # the arc's radius (1.205)
TAU_C = math.sqrt(R_ARC ** 2 - (R_ARC - SAG + CHAMFER) ** 2)   # the chamfered tips' half length (0.564)
N_ROWS = 24                                             # rows along the chord

# --- the button ---
BUTTON_S, BUTTON_T = 3.72, 1.15                         # by the hall (s 3.72: the seam at 3.95 passes clear right of the recess), h 1.15
OCT_FLATS, OCT_D = 0.16, 0.03                           # the octagonal recess: across the flats, deep
DOME_R, DOME_UP = 0.045, 0.025                          # the dome: radius (9 cm across), standing proud of the wall
RING_W = 0.012                                          # the light ring round it

for _name, _base, _upd in (
        ("int_cyan__gill_fil", "int_cyan", dict(base=(0.05, 0.75, 1.0, 1.0), emission=(0.05, 0.75, 1.0), strength=2.2)),
        ("int_cyan__gill_seam", "int_cyan", dict(base=(0.05, 0.6, 0.9, 1.0), emission=(0.05, 0.6, 0.9), strength=0.6)),
        ("int_cyan__gill_line", "int_cyan", dict(base=(0.1, 0.85, 1.0, 1.0), emission=(0.1, 0.85, 1.0), strength=1.6)),
        ("int_cyan__gill_ring", "int_cyan", dict(base=(0.1, 0.85, 1.0, 1.0), emission=(0.1, 0.85, 1.0), strength=2.0)),
        ("int_cyan__gill_plinth", "int_cyan", dict(base=(0.1, 0.8, 1.0, 1.0), emission=(0.1, 0.8, 1.0), strength=1.4)),
        ("int_dark__gill_btn", "int_dark", dict(base=(0.05, 0.05, 0.055, 1.0), metallic=0.85, roughness=0.18))):
    L.MATERIALS[_name] = {**L.MATERIALS[_base], **_upd}
BAND_MAT, LIP_MAT, RIM_MAT, DARK = "int_silver_b", "int_silver_b", "int_silver_c", "int_dark"


# --- the numbers (plain Python, the tests read them) -----------------------------------------------------------------
def arc_off(tau: float) -> float:
    """The segment's width at tau (from its middle along the chord): the arc's distance from the chord."""
    return math.sqrt(max(R_ARC ** 2 - tau ** 2, 0.0)) - (R_ARC - SAG)


def taus() -> list[float]:
    """The rows' tau, the bend's own row included (so no face crosses the bend)."""
    out = {round(-TAU_C + 2 * TAU_C * k / N_ROWS, 9) for k in range(N_ROWS + 1)}
    if -TAU_C < BEND - T_MID < TAU_C:
        out.add(round(BEND - T_MID, 9))
    return sorted(out)


def slit_chord(s: float) -> float:
    """A slit's chord's u (the segment's middle at s; its arc toward the mouth, -u)."""
    return s + SAG / 2


def point(u: float, t: float, w: float = 0.0, leaf: str = "") -> tuple[float, float, float]:
    """Developed (u, t, w) -> the east piece's (x, y, h). leaf "lo"/"hi": that plane alone (a lip's leaf at the bend);
    else the bend's points on the mitre."""
    lo = leaf == "lo" or (leaf == "" and t < BEND - 1e-9)
    if leaf == "" and abs(t - BEND) <= 1e-9:
        return (u, w, FLOOR + BEND - w * LV / (1.0 + LH))
    if lo:
        return (u, w, FLOOR + t)
    return (u, (t - BEND) * LV + w * LH, FLOOR + BEND + (t - BEND) * LH - w * LV)


def v_of(t: float, w: float = 0.0) -> float:
    return point(0.0, t, w)[1]


def header_clip() -> tuple[float, float, float]:
    """(a, b, c): the hall-relative half plane a u + b v <= c (u along the east wall from the mouth's corner, v into
    the throat) on the throat's side of the hall's header face (1 cm in), as the old end module was cut (th_end_cut)."""
    k, _v, m, dist = S.th_corner_chord()
    n_in = (-WALL_D[1], WALL_D[0])
    md, mn = m[0] * WALL_D[0] + m[1] * WALL_D[1], m[0] * n_in[0] + m[1] * n_in[1]
    mm = m[0] * _MK[0] + m[1] * _MK[1]
    return -md, -mn, mm - (dist - S.TH_HEAD_D + 0.01)


def u_max(t: float, w: float = 0.0) -> float:
    """The band's end along u at t: the hall's corner K, or the header's face where that comes first."""
    a, b, c = header_clip()
    return min(WALL_LEN, (c - b * v_of(t, w)) / a)


def t_max(u: float) -> float:
    """The band's top at u: the ceiling's edge (plus T_OVER), or lower where the header's face cuts it."""
    a, b, c = header_clip()
    v = (c - a * u) / b if b > 0 else 1e9
    return min(T_TOP + T_OVER, BEND + max(v, 0.0) / LV) if v < IN + T_OVER * LV else T_TOP + T_OVER


def numbers() -> dict:
    """The row's numbers for the tests and the report (metres)."""
    return {"s0": S0, "wall_len": WALL_LEN, "band": BAND, "plinth_h": PLINTH_H, "slits": SLITS, "chord": CHORD,
            "t_lo": T_MID - CHORD / 2, "t_hi": T_MID + CHORD / 2, "sag": SAG, "tau_c": TAU_C, "gap": GAP,
            "depth": DEPTH, "lip_t": LIP_T, "fils": FILS, "fil_t": FIL_T, "fil_d": FIL_D, "button": (BUTTON_S, BUTTON_T),
            "oct_flats": OCT_FLATS, "oct_d": OCT_D, "dome_r": DOME_R, "dome_up": DOME_UP, "ring_w": RING_W,
            "h_lo": point(0, T_MID - CHORD / 2)[2] - FLOOR, "h_hi": point(0, T_MID + CHORD / 2)[2] - FLOOR,
            "open_deg": OPEN_DEG, "gasp_deg": GASP_DEG}


def lip_hinges(k: int = WORKING) -> dict:
    """The working lip's two leaves: {leaf: (origin (x, y, h) in the east piece, axis in Godot's (x, y up, z) of the
    piece)}; +angle about the axis lifts the free edge out of the wall."""
    uc = slit_chord(SLITS[k - 1])
    return {"lo": (point(uc, BEND, -LIP_T, "lo"), (0.0, 1.0, 0.0)),
            "hi": (point(uc, BEND, -LIP_T, "hi"), (0.0, LH, LV))}


# --- meshes in developed coordinates ---------------------------------------------------------------------------------
def _sheet(rows: list, closed: bool = False, leaf: str = "", flip: bool = False):
    """Rows of developed points (same count each) -> the quads between neighbouring rows and columns."""
    n = len(rows[0])
    verts = [point(*p, leaf=leaf) for r in rows for p in r]
    faces = []
    for i in range(len(rows) - 1):
        for j in range(n - (0 if closed else 1)):
            a, b = i * n + j, i * n + (j + 1) % n
            f = (a, b, b + n, a + n)
            faces.append(f[::-1] if flip else f)
    return verts, faces


def _poly(pts: list, w: float = 0.0, flip: bool = False):
    """A convex (u, t) polygon at w (its t all on one side of the bend), counter-clockwise seen from the room."""
    verts = [point(u, t, w) for u, t in pts]
    f = tuple(range(len(pts)))
    return verts, [f[::-1] if flip else f]


def _clip(poly, a, b, c):
    return S._clip2(poly, a, b, c)


def _band_faces(holes: list) -> tuple:
    """The band's face (u from S0 to the corner, t from the plinth's top to the ceiling) in columns, each split at
    the bend and cut by the header's face; a column with a hole leaves it open: holes [(u0, u1, left, right)] with the
    hole's boundary as two chains of (u, t) (left: low u, right: high u) on shared t rows, bottom to top."""
    cols = sorted({S0, *BAND, WALL_LEN} | {x for h in holes for x in h[:2]})
    a, b, c = header_clip()
    out = []
    t_lo, t_hi = PLINTH_H, T_TOP + T_OVER
    def emit(poly):
        for lo, hi in ((t_lo, BEND), (BEND, t_hi)):
            q = _clip(_clip(poly, 0.0, -1.0, -lo), 0.0, 1.0, hi)
            if lo >= BEND - 1e-9:   # the lean: v = (t - BEND) LV, the header's cut linear in (u, t)
                q = _clip(q, a, b * LV, c + b * LV * BEND)
            else:
                q = _clip(q, a, 0.0, c)
            q = _clip(q, 1.0, 0.0, WALL_LEN)
            if len(q) >= 3 and abs(G.area2(q)) > 1e-8:
                out.append(_poly(q))
    for u0, u1 in zip(cols, cols[1:]):
        hole = next((h for h in holes if h[0] <= u0 + 1e-9 and h[1] >= u1 - 1e-9), None)
        if hole is None:
            emit([(u0, t_lo), (u1, t_lo), (u1, t_hi), (u0, t_hi)])
            continue
        _, _, left, right = hole
        tb, tt = left[0][1], left[-1][1]
        emit([(u0, t_lo), (u1, t_lo), (u1, tb), right[0], left[0], (u0, tb)])
        emit([(u0, tt), left[-1], right[-1], (u1, tt), (u1, t_hi), (u0, t_hi)])
        for (l0, l1, r0, r1) in zip(left, left[1:], right, right[1:]):
            emit([(u0, l0[1]), l0, l1, (u0, l1[1])])
            emit([r0, (u1, r0[1]), (u1, r1[1]), r1])
    return out


def _walls(loop: list, w0: float, w1: float):
    """The walls of a hole's boundary loop (u, t), counter-clockwise seen from the room, from w0 back to w1."""
    verts, faces = [], []
    for i, p in enumerate(loop):
        q = loop[(i + 1) % len(loop)]
        base = len(verts)
        verts += [point(p[0], p[1], w0), point(q[0], q[1], w0), point(q[0], q[1], w1), point(p[0], p[1], w1)]
        faces.append((base, base + 1, base + 2, base + 3))   # facing into the hole
    return verts, faces


def slit(k: int, working: bool) -> tuple[list, tuple]:
    """Slit k's parts (east frame) and its hole for the band: (parts, (u0, u1, left chain, right chain))."""
    sc = SLITS[k - 1]
    uc = slit_chord(sc)
    ts = taus()
    arc = [(uc - arc_off(tau), T_MID + tau) for tau in ts]
    chord = [(uc, T_MID + tau) for tau in ts]
    loop = [*chord, *arc[::-1]]   # up the chord (high u), down the arc (low u): counter-clockwise in (u, t)
    parts = []
    walls = _walls(loop, 0.0, -DEPTH)
    floor = _sheet([[(a[0], a[1], -DEPTH), (c[0], c[1], -DEPTH)] for a, c in zip(arc, chord)])
    parts += [P(f"gill{k}_recess", walls, RIM_MAT), P(f"gill{k}_back", floor, DARK)]
    # the filaments, square to the chord, behind the lip
    fil = []
    for j in range(FILS):
        tau = -TAU_C + (j + 0.5) * 2 * TAU_C / FILS
        t0, t1 = T_MID + tau - FIL_T / 2, T_MID + tau + FIL_T / 2
        ua, ub = uc - arc_off(tau) + 0.004, uc - 0.004
        w0, w1 = -DEPTH + 0.002, -DEPTH + FIL_D
        box = [(ua, t0, w0), (ub, t0, w0), (ub, t1, w0), (ua, t1, w0), (ua, t0, w1), (ub, t0, w1), (ub, t1, w1),
               (ua, t1, w1)]
        verts = [point(*p) for p in box]
        fil.append((verts, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]))
    parts.append(P(f"gill{k}_fil", M(*fil), "int_cyan__gill_fil"))
    # the seam: the gap's floor under the lip's free edge, seen through the 1.5 cm gap
    seam_rows = [[(uc - arc_off(tau) - 0.002, T_MID + tau, -LIP_T - 0.004),
                  (uc - arc_off(tau) + GAP + 0.004, T_MID + tau, -LIP_T - 0.004)] for tau in ts]
    parts.append(P(f"gill{k}_seam", _sheet(seam_rows), "int_cyan__gill_seam"))
    # the lip, a leaf each side of the bend
    lo_rows = [tau for tau in ts if T_MID + tau <= BEND + 1e-9]
    hi_rows = [tau for tau in ts if T_MID + tau >= BEND - 1e-9]
    lips, lines = {}, {}
    for leaf, rows in (("lo", lo_rows), ("hi", hi_rows)):
        if len(rows) < 2:
            continue
        sec, line = [], []
        for idx, tau in enumerate(rows):
            end = idx == 0 and leaf == "lo" or idx == len(rows) - 1 and leaf == "hi"
            g = GAP if (abs(tau) >= TAU_C - 1e-9) else 0.0
            t = T_MID + tau + (g if tau < 0 else -g)
            wid = max(arc_off(tau) - GAP, 0.004)
            ue, ur = uc - wid, uc - wid * LIP_RIDGE_AT
            sec.append([(uc - 0.002, t, -LIP_T), (uc - 0.002, t, 0.0), (ur, t, LIP_RIDGE), (ue + LIP_EDGE, t, 0.0),
                        (ue, t, -LIP_EDGE), (ue, t, -LIP_T)])
            line.append([(ue + LIP_EDGE * 0.9, t, 0.0015), (ue + 0.0005, t, -LIP_EDGE * 0.85 + 0.0015)])
        v, f = _sheet(sec, closed=True, leaf=leaf, flip=True)
        n = len(sec[0])
        f += [tuple(range(n)), tuple(range(len(v) - n, len(v)))[::-1]]   # the leaf's two ends
        lips[leaf], lines[leaf] = (v, f), _sheet(line, leaf=leaf, flip=True)
    if working:
        for leaf, (origin, _axis) in lip_hinges(k).items():
            if leaf in lips:
                parts.append({**P(f"gill{k}_lip_{leaf}", lips[leaf], LIP_MAT), "origin": origin})
                parts.append({**P(f"gill{k}_line_{leaf}", lines[leaf], "int_cyan__gill_line"),
                              "parent": f"gill{k}_lip_{leaf}"})
    else:
        parts.append(P(f"gill{k}_lip", M(*lips.values()), LIP_MAT))
        parts.append(P(f"gill{k}_line", M(*lines.values()), "int_cyan__gill_line"))
    return parts, (uc - SAG, uc, arc, chord)


def button() -> tuple[list, tuple]:
    """The button: an octagonal recess, the light ring on its floor, the dome; its hole for the band."""
    a = OCT_FLATS / 2
    b = a * math.tan(math.pi / 8)
    us, ts = BUTTON_S, BUTTON_T
    left = [(us - b, ts - a), (us - a, ts - b), (us - a, ts + b), (us - b, ts + a)]
    right = [(us + b, ts - a), (us + a, ts - b), (us + a, ts + b), (us + b, ts + a)]
    loop = [right[0], right[1], right[2], right[3], left[3], left[2], left[1], left[0]]
    walls = _walls(loop, 0.0, -OCT_D)
    floor = _poly(loop, -OCT_D)
    n = 32
    ring_in, ring_out = DOME_R, DOME_R + RING_W
    ring = _sheet([[(us + r * math.cos(2 * math.pi * i / n), ts + r * math.sin(2 * math.pi * i / n), -OCT_D + 0.002)
                    for i in range(n)] for r in (ring_out, ring_in)], closed=True)
    rho = (DOME_R ** 2 + DOME_UP ** 2) / (2 * DOME_UP)   # the cap's sphere
    rings = [(DOME_R, -OCT_D), (DOME_R, 0.0)]
    for i in range(1, 7):
        r = DOME_R * (1 - i / 7)
        rings.append((r, DOME_UP - rho + math.sqrt(rho ** 2 - r ** 2)))
    dome_rows = [[(us + r * math.cos(2 * math.pi * i / n), ts + r * math.sin(2 * math.pi * i / n), w) for i in range(n)]
                 for r, w in rings]
    dv, df = _sheet(dome_rows, closed=True)
    dv.append(point(us, ts, DOME_UP))
    top = len(dv) - 1 - n
    df += [(top + i, top + (i + 1) % n, len(dv) - 1) for i in range(n)]
    parts = [P("btn_recess", walls, RIM_MAT), P("btn_floor", floor, DARK), P("btn_ring", ring, "int_cyan__gill_ring"),
             P("btn_dome", (dv, df), "int_dark__gill_btn")]
    return parts, (us - a, us + a, left, right)


def plinth() -> list:
    fr = G.Frame((0.0, 0.0, FLOOR), (1, 0, 0), (0, 0, 1), (0, 1, 0))
    body = G.slab(fr, G.rect(S0, WALL_LEN, KICK_H, PLINTH_H), -0.2, PLINTH_W, 0.008)
    kick = G.slab(fr, G.rect(S0, WALL_LEN, 0.0, KICK_H), -0.2, PLINTH_W - 0.012)
    line = G.slab(fr, G.rect(S0, WALL_LEN, PLINTH_H - 0.024, PLINTH_H - 0.012), PLINTH_W - 0.001, PLINTH_W + 0.003)
    return [P("plinth", body, BAND_MAT), P("kick", kick, DARK), P("plinth_line", line, "int_cyan__gill_plinth")]


def seams() -> list:
    out = []
    for u in BAND:
        rows = [[(u - SEAM_W / 2, t, 0.001), (u + SEAM_W / 2, t, 0.001)]
                for t in (PLINTH_H, BEND, min(T_TOP, t_max(u + SEAM_W / 2)))]
        out.append(_sheet(rows))
    return [P("seams", M(*out), DARK)]


def back_and_ends() -> list:
    """The band's back skin 0.2 behind it (no light through the wall) and its two ends' caps."""
    a, b, c = header_clip()
    back = []
    for lo, hi in ((PLINTH_H, BEND), (BEND, T_TOP + T_OVER)):
        q = [(S0, lo), (WALL_LEN, lo), (WALL_LEN, hi), (S0, hi)]
        if lo >= BEND:
            q = _clip(q, a, b * LV, c + b * LV * BEND)   # (the skin's own cut is near enough: hidden behind)
        if len(q) >= 3:
            back.append(_poly(q, -0.2, flip=True))
    caps = []
    for u, flip in ((S0, True), (WALL_LEN, False)):
        tt = min(T_TOP + T_OVER, t_max(u))
        rows = [[(u, t, 0.0), (u, t, -0.2)] for t in (PLINTH_H, BEND, tt) if t <= tt + 1e-9]
        caps.append(_sheet(rows, flip=flip))
    return [P("back", M(*back), BAND_MAT), P("ends", M(*caps), BAND_MAT)]


def mirror(parts: list) -> list:
    """The west piece: x mirrored (faces turned back), origins too; Godot axes mirrored in x by gill_row.gd."""
    out = []
    for p in parts:
        q = dict(p)
        q["verts"] = [(-x, y, h) for x, y, h in p["verts"]]
        q["faces"] = [tuple(f[::-1]) for f in p["faces"]]
        if p.get("origin"):
            x, y, h = p["origin"]
            q["origin"] = (-x, y, h)
        out.append(q)
    return out


def th_gills(args, layout):
    """One throat side's clean wall (args side "e"/"w"; the east's middle slit has the working lip)."""
    side = args.get("side", "e")
    parts, holes = [], []
    for k in range(1, len(SLITS) + 1):
        ps, hole = slit(k, working=(side == "e" and k == WORKING))
        parts += ps
        holes.append(hole)
    ps, hole = button()
    parts += ps
    holes.append(hole)
    parts.append(P("band", M(*_band_faces(holes)), BAND_MAT))
    parts += plinth() + seams() + back_and_ends()
    closed = ("_fil", "_lip", "_lip_lo", "_lip_hi", "plinth", "kick", "plinth_line")
    for p in parts:   # the open sheets keep their winding (recalc_face_normals guesses on an open sheet)
        p["solid"] = p["name"].endswith(closed)
    return parts if side == "e" else mirror(parts)
