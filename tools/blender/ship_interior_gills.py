"""The throat's gills (art #263; the engineer's choice prime-game#1095 c6470177717, design's row "Ряд у горлі" of
2026-10-28; docs/ship.md "The throat's gills"): `th_gills_e` and its mirror `th_gills_w`, each the whole clean wall
of one throat side under the roof (s 1.62 m from the mouth's corner to the hall's corner K, 4.051): the plinth with
its cyan line, the clean band of the wall's own metal on the throat's profile (vertical to 1.45, then 0.55 in to the
ceiling at 2.30) with two straight seams, five vertical crescent slits cut into it and the round button by the hall.
They replace the throat's wall modules (low, mid, cable bay, upper) and the louvred vent cabinets.

The slit (step 3, after the approved concept side_right.jpg): a true crescent, both edges arcs through the same two
tips 1.20 apart straight up the band (the chord, on the hall's side): the outer (convex) arc sags 0.27 toward the
mouth, the inner (concave) 0.06, so the crescent is 21 cm at its widest; its tips are cut at a 1.2 cm flat. On the
convex side a thick bevelled rim of the wall's metal stands 2.2 cm proud, 5 cm wide, tapering into the tips. The
recess (13 cm) holds a glowing back and 36 fine filaments radiating from the outer arc's centre. Two dark shutter
leaves close over it: they meet along the crescent's middle line (a thin light line on each meeting edge: the shut
slit's red line), and slide apart along the wall (+-u, the same on both planes of the 1.45 bend, so each leaf is one
rigid piece) through slots in the recess walls into pockets under the band: open, the whole crescent glows.

Frame: the piece's origin on the wall's line at the mouth's corner (east (1.65, -7.1), west mirrored), local x = s
along the wall toward the hall (the west piece mirrored: local -x), local y into the throat, h absolute. A point is
given in the wall's developed coordinates (u = s, t up the profile from the deck, w out of the surface toward the
room); `point` maps it, the bend's points on the mitre. Plain Python (ship_build.py makes the meshes).

The game drives (Godot, `<piece>_<part>`): `gill<k>_leaf_a` (the inner leaf, toward the hall) and `gill<k>_leaf_b`
(the outer, under the rim), built OPEN (the GLB's rest: calm, glowing), shut by moving them SLIDE along local x (a
toward -x, b toward +x; the west mirrored); `gill<k>_seam_a/_b` (their meeting edges' lines, children of the
leaves: `int_cyan__gill_seam`), `gill<k>_fil` (`int_cyan__gill_fil`), `gill<k>_glow` (the back,
`int_cyan__gill_glow`), `btn_ring` (`int_cyan__gill_ring`) and `btn_dome`; godot/ship/gill_row.gd is the reference
controller."""

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
LINE_H = (PLINTH_H - 0.036, PLINTH_H - 0.012)              # step 5: the plinth's cyan line, 2.4 cm (was 1.2: thin
                                                        # and dim beside the concept's)
CORNICE_H, CORNICE_W = 0.06, 0.022                      # step 5: the cornice along the band's top, under the ceiling
PLINTH_S0 = 0.02                                        # the plinth from the mouth's corner (under the ramp roof too, as the concept)
MOUTH_W = 0.003                                         # step 4: the band's mouth part (s 0.02-1.62, under the ramp roof, to
                                                        # the bend) 3 mm proud of the jambs' plates it covers (no z-fighting)
BAND = (1.70, 3.95)                                     # the clean band's seams (design: s 1.70-3.95)
SEAM_W = 0.006

# --- the slit (m; the chord and the spots are design's, the crescent the concept's) ---
SLITS = (1.95, 2.32, 2.69, 3.06, 3.43)                  # the crescents' middles along the wall (design's row, 37 cm)
WORKING = 3                                             # the slit the 6 s proof drives (the vent spot, ship.toml)
CHORD = 1.20                                            # the tips' line, straight up the band, t 0.75-1.95
T_MID = 1.35
SAG = 0.27                                              # the outer (convex) arc's sag from the chord, toward the mouth
SAG_IN = 0.06                                           # the inner (concave) arc's
WIDTH = SAG - SAG_IN                                    # 0.21 at the middle (about 1/6 of the chord)
TIP = 0.012                                             # the tips cut where the crescent is this wide
DEPTH = 0.13                                            # the recess
RIM_W, RIM_UP = 0.05, 0.022                             # the convex side's rim: width on the band, height (at the middle)
LEAF_F, LEAF_B, FLANGE_B = -0.034, -0.044, -0.047       # the leaves' front and back w; leaf a's flange under leaf b
SLOT = (-0.031, -0.049)                                 # the slots in the recess walls (w), the leaves' way out
POCKET_W = -0.050                                       # the pockets' back face under the band
TUCK = 0.010                                            # shut, a leaf's outer edge stays this far inside its slot
MEET = 0.002                                            # half the gap between the shut leaves
FLANGE = 0.015                                          # leaf a's flange reaches this far under leaf b
SLIDE = WIDTH / 2 + FLANGE + 0.003                      # each leaf's travel from shut to open (0.123)
SEAM_W = 0.007                                          # the light line on each leaf's meeting edge
FILS, FIL_T, FIL_W = 36, 0.003, -0.108                  # the filaments: count, thickness, their front w (back: the recess)
# step 4: 3 mm ribs standing 2.2 cm off the glowing back (step 3's 6 mm blades 7.5 cm deep read as coarse sawteeth in
# perspective, worst on the lean, where the eye looks down their sides)
GASP_OPEN = 0.6                                         # the gasp: the leaves 60 % open
N_ROWS = 28                                             # rows along the chord


def _r(sag: float) -> float:
    return (CHORD ** 2 / 4 + sag ** 2) / (2 * sag)


R_OUT, R_IN = _r(SAG), _r(SAG_IN)                       # the arcs' radii (0.802, 3.03)

# --- the button (the concept's: a dark dome in a bright cyan ring, in an octagonal recess) ---
BUTTON_S, BUTTON_T = 3.72, 1.15                         # by the hall (s 3.72: the seam at 3.95 passes clear right of the recess), h 1.15
OCT_FLATS, OCT_D = 0.24, 0.025                          # the octagonal recess: across the flats, deep (in front of slit 5's pocket)
DOME_R, DOME_UP = 0.065, 0.035                          # the dome: radius (13 cm across), standing proud of the wall
RING_W = 0.022                                          # the light ring round it

for _name, _base, _upd in (
        ("int_cyan__gill_fil", "int_cyan", dict(base=(0.3, 0.9, 1.0, 1.0), emission=(0.3, 0.9, 1.0), strength=3.0)),
        ("int_cyan__gill_glow", "int_cyan", dict(base=(0.05, 0.7, 1.0, 1.0), emission=(0.05, 0.7, 1.0), strength=1.6)),
        ("int_cyan__gill_seam", "int_cyan", dict(base=(1.0, 0.1, 0.03, 1.0), emission=(1.0, 0.1, 0.03), strength=1.6)),
        ("int_cyan__gill_ring", "int_cyan", dict(base=(0.1, 0.85, 1.0, 1.0), emission=(0.1, 0.85, 1.0), strength=2.4)),
        ("int_cyan__gill_plinth", "int_cyan", dict(base=(0.1, 0.8, 1.0, 1.0), emission=(0.1, 0.8, 1.0), strength=2.4)),
        ("int_dark__gill_btn", "int_dark", dict(base=(0.035, 0.04, 0.045, 1.0), metallic=0.6, roughness=0.38)),
        ("int_dark__gill_leaf", "int_dark", dict(base=(0.05, 0.05, 0.055, 1.0), metallic=0.5, roughness=0.45))):
    L.MATERIALS[_name] = {**L.MATERIALS[_base], **_upd}
BAND_MAT, RIM_MAT, DARK, LEAF_MAT = "int_silver_b", "int_silver_c", "int_dark", "int_dark__gill_leaf"


# --- the numbers (plain Python, the tests read them) -----------------------------------------------------------------
def _off(r: float, sag: float, tau: float) -> float:
    return math.sqrt(max(r ** 2 - tau ** 2, 0.0)) - (r - sag)


def arc_off(tau: float) -> float:
    """The outer (convex) arc's distance from the chord at tau (from the middle along the chord)."""
    return _off(R_OUT, SAG, tau)


def arc_in(tau: float) -> float:
    """The inner (concave) arc's."""
    return _off(R_IN, SAG_IN, tau)


def width(tau: float) -> float:
    return arc_off(tau) - arc_in(tau)


def _tau_tip() -> float:
    lo, hi = 0.0, CHORD / 2
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if width(mid) > TIP else (lo, mid)
    return lo


TAU_C = _tau_tip()                                      # the cut tips' half length


def taus() -> list[float]:
    """The rows' tau, the bend's own row included (so no face crosses the bend)."""
    out = {round(-TAU_C + 2 * TAU_C * k / N_ROWS, 9) for k in range(N_ROWS + 1)}
    if -TAU_C < BEND - T_MID < TAU_C:
        out.add(round(BEND - T_MID, 9))
    return sorted(out)


def slit_chord(s: float) -> float:
    """A slit's chord's u (the crescent's middle at s; its arcs toward the mouth, -u)."""
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
            "t_lo": T_MID - CHORD / 2, "t_hi": T_MID + CHORD / 2, "sag": SAG, "sag_in": SAG_IN, "width": WIDTH,
            "tau_c": TAU_C, "depth": DEPTH, "rim": (RIM_W, RIM_UP), "slide": SLIDE, "fils": FILS,
            "button": (BUTTON_S, BUTTON_T),
            "oct_flats": OCT_FLATS, "oct_d": OCT_D, "dome_r": DOME_R, "dome_up": DOME_UP, "ring_w": RING_W,
            "h_lo": point(0, T_MID - CHORD / 2)[2] - FLOOR, "h_hi": point(0, T_MID + CHORD / 2)[2] - FLOOR, "gasp_open": GASP_OPEN}


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


def _slotted_walls(loop: list, n_right: int) -> tuple:
    """The recess walls round a crescent's loop (u, t), counter-clockwise seen from the room (the inner arc's n_right
    points up, then the outer arc down): on the arcs open between SLOT's two w (the leaves' way to their pockets),
    the two cut tips whole. -> (upper walls of the band's metal, lower walls, dark)."""
    up, lo = [], []
    n = len(loop)
    for i, p in enumerate(loop):
        q = loop[(i + 1) % n]
        tip = i in (n_right - 1, n - 1)   # inner top -> outer top, outer bottom -> inner bottom
        spans = [(0.0, -DEPTH, lo)] if tip else [(0.0, SLOT[0], up), (SLOT[1], -DEPTH, lo)]
        for w0, w1, out in spans:
            out.append(([point(p[0], p[1], w0), point(q[0], q[1], w0), point(q[0], q[1], w1), point(p[0], p[1], w1)],
                        [(0, 1, 2, 3)]))
    return M(*up), M(*lo)


def _radial(uc: float, tau: float) -> tuple:
    """A filament's line in (u, t): from the outer arc at tau toward the outer arc's centre, to the inner arc."""
    pu, pt = uc - arc_off(tau), T_MID + tau
    cu, ct = uc - SAG + R_OUT, T_MID
    du, dt = cu - pu, ct - pt
    d = math.hypot(du, dt)
    du, dt = du / d, dt / d
    qu, qt = pu - (uc - SAG_IN + R_IN), pt - T_MID   # from the inner arc's centre
    b = qu * du + qt * dt
    c = qu * qu + qt * qt - R_IN ** 2
    s1 = -b - math.sqrt(max(b * b - c, 0.0))
    return (pu, pt), (du, dt), s1


def leaf_rows() -> list[float]:
    """The leaves' rows: the slit's rows, the ends 1.5 cm in from the cut tips."""
    end = TAU_C - 0.015
    return [-end, *[tau for tau in taus() if abs(tau) < end - 1e-6], end]


def slit(k: int) -> tuple[list, tuple]:
    """Slit k's parts (east frame) and its hole for the band: (parts, (u0, u1, left chain, right chain))."""
    uc = slit_chord(SLITS[k - 1])
    ts = taus()
    outer = [(uc - arc_off(tau), T_MID + tau) for tau in ts]
    inner = [(uc - arc_in(tau), T_MID + tau) for tau in ts]
    loop = [*inner, *outer[::-1]]
    up, lo = _slotted_walls(loop, len(inner))
    parts = [P(f"gill{k}_recess", up, RIM_MAT), P(f"gill{k}_wall", lo, DARK)]
    parts.append(P(f"gill{k}_glow", _sheet([[(o[0], o[1], -DEPTH), (i[0], i[1], -DEPTH)] for o, i in zip(outer, inner)]),
                   "int_cyan__gill_glow"))
    # the pockets' backs under the band, where the open leaves rest
    reach = SLIDE + TUCK + 0.012
    pockets = [_sheet([[(o[0] - reach, o[1], POCKET_W), (o[0], o[1], POCKET_W)] for o in outer]),
               _sheet([[(i[0], i[1], POCKET_W), (i[0] + reach, i[1], POCKET_W)] for i in inner])]
    parts.append(P(f"gill{k}_pocket", M(*pockets), DARK))
    # the rim on the convex side: a bevelled ridge on the band along the outer arc, tapering into the tips
    sec = []
    for tau in ts:
        f = max(width(tau) / WIDTH, 0.0) ** 0.6
        uo, t = uc - arc_off(tau), T_MID + tau
        rw, ru = RIM_W * (0.25 + 0.75 * f), RIM_UP * f + 0.001
        sec.append([(uo, t, 0.0), (uo - 0.15 * rw, t, ru * 0.92), (uo - 0.5 * rw, t, ru), (uo - rw, t, 0.0)])
    v, f_ = _sheet(sec, closed=True)
    m = len(sec[0])
    f_ += [tuple(range(m)), tuple(range(len(v) - m, len(v)))[::-1]]
    parts.append(P(f"gill{k}_rim", (v, f_), RIM_MAT))
    # the filaments: thin blades radiating from the outer arc's centre, from the recess's back to FIL_W
    fil = []
    for j in range(FILS):
        tau = -TAU_C + 0.02 + (j + 0.5) * (2 * TAU_C - 0.04) / FILS
        (pu, pt), (du, dt), s1 = _radial(uc, tau)
        nu, nt = -dt * FIL_T / 2, du * FIL_T / 2
        a0, a1 = (pu + du * 0.004, pt + dt * 0.004), (pu + du * (s1 - 0.004), pt + dt * (s1 - 0.004))
        if s1 < 0.012:
            continue
        box = []
        for w in (-DEPTH + 0.001, FIL_W):
            box += [(a0[0] - nu, a0[1] - nt, w), (a1[0] - nu, a1[1] - nt, w), (a1[0] + nu, a1[1] + nt, w),
                    (a0[0] + nu, a0[1] + nt, w)]
        fil.append(([point(*q) for q in box],
                    [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]))
    parts.append(P(f"gill{k}_fil", M(*fil), "int_cyan__gill_fil"))
    # the two leaves, built open (slid SLIDE apart into their pockets), and their meeting edges' light lines
    secs = {"a": [], "b": []}
    seams = {"a": [], "b": []}
    for tau in leaf_rows():
        t = T_MID + tau
        uo, ui = uc - arc_off(tau), uc - arc_in(tau)
        um = (uo + ui) / 2
        ea, eb = um + MEET + SLIDE, um - MEET - SLIDE   # the meeting edges, open
        secs["b"].append([(uo - TUCK - SLIDE, t, LEAF_B), (eb, t, LEAF_B), (eb, t, LEAF_F), (uo - TUCK - SLIDE, t, LEAF_F)])
        secs["a"].append([(ea, t, LEAF_F), (ea, t, LEAF_B), (ea - FLANGE, t, LEAF_B), (ea - FLANGE, t, FLANGE_B),
                          (ui + TUCK + SLIDE, t, FLANGE_B), (ui + TUCK + SLIDE, t, LEAF_F)])
        lift = 0.0008
        seams["b"].append([(eb - SEAM_W, t, LEAF_F + lift), (eb + lift, t, LEAF_F + lift), (eb + lift, t, LEAF_B + 0.002)])
        seams["a"].append([(ea - lift, t, LEAF_B + 0.002), (ea - lift, t, LEAF_F + lift), (ea + SEAM_W, t, LEAF_F + lift)])
    for side in ("a", "b"):
        v, f_ = _sheet(secs[side], closed=True)
        m = len(secs[side][0])
        f_ += [tuple(range(m)), tuple(range(len(v) - m, len(v)))[::-1]]
        mid = len(secs[side]) // 2
        cu = sum(q[0] for q in secs[side][mid]) / m
        parts.append({**P(f"gill{k}_leaf_{side}", (v, f_), LEAF_MAT), "origin": point(cu, T_MID, LEAF_F)})
        parts.append({**P(f"gill{k}_seam_{side}", _sheet(seams[side]), "int_cyan__gill_seam"),
                      "parent": f"gill{k}_leaf_{side}"})
    return parts, (uc - SAG, uc, outer, inner)


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
    n = 48
    ring_in, ring_out = DOME_R, DOME_R + RING_W
    ring = _sheet([[(us + r * math.cos(2 * math.pi * i / n), ts + r * math.sin(2 * math.pi * i / n), -OCT_D + 0.002)
                    for i in range(n)] for r in (ring_out, ring_in)], closed=True)
    rho = (DOME_R ** 2 + DOME_UP ** 2) / (2 * DOME_UP)   # the cap's sphere
    rings = [(DOME_R, -OCT_D), (DOME_R, 0.0)]
    for i in range(1, 10):
        r = DOME_R * (1 - i / 10)
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
    body = G.slab(fr, G.rect(PLINTH_S0, WALL_LEN, KICK_H, PLINTH_H), -0.2, PLINTH_W, 0.008)
    kick = G.slab(fr, G.rect(PLINTH_S0, WALL_LEN, 0.0, KICK_H), -0.2, PLINTH_W - 0.012)
    line = G.slab(fr, G.rect(PLINTH_S0, WALL_LEN, *LINE_H), PLINTH_W - 0.001, PLINTH_W + 0.004)
    return [P("plinth", body, BAND_MAT), P("kick", kick, DARK), P("plinth_line", line, "int_cyan__gill_plinth")]


def band_mouth() -> list:
    """Step 4: the band's mouth part, under the ramp roof from the mouth's corner to the roof line, the plinth's top to
    the bend (the tunnel's chamfer leans in over it): the band's own metal over the jambs' bluish hull plates, so the
    concept's one clean band runs from the ramp roof's edge to the hall's corner. Its aft end steps the 3 mm back."""
    face = _poly([(PLINTH_S0, PLINTH_H), (S0, PLINTH_H), (S0, BEND), (PLINTH_S0, BEND)], MOUTH_W)
    end = _sheet([[(S0, t, MOUTH_W), (S0, t, 0.0)] for t in (PLINTH_H, BEND)], flip=True)
    front = _sheet([[(PLINTH_S0, t, 0.0), (PLINTH_S0, t, MOUTH_W)] for t in (PLINTH_H, BEND)], flip=True)
    return [P("band_mouth", M(face, end, front), BAND_MAT)]


def cornice() -> list:
    """Step 5: a strip along the band's top edge under the ceiling (the concept's clean line where the band meets it),
    from the roof line to the header's face at the hall's corner, its end cut on that face."""
    a, b, c = header_clip()
    def at(u, t, w):   # the point's u, cut back on the header's face
        return (min(u, (c - b * v_of(t, w)) / a), t, w)
    prof = [(T_TOP - CORNICE_H, 0.001), (T_TOP - CORNICE_H, CORNICE_W), (T_TOP + T_OVER, CORNICE_W)]
    rows = [[at(u, t, w) for t, w in prof] for u in (S0, WALL_LEN)]
    body = _sheet(rows)   # bottom face down, front face toward the room
    ends = []
    for r, u, flip in ((rows[0], S0, True), (rows[1], WALL_LEN, False)):
        vs = [point(*p) for p in r] + [point(*at(u, T_TOP + T_OVER, 0.001))]
        ends.append((vs, [(0, 1, 2, 3)[::-1] if flip else (0, 1, 2, 3)]))
    return [P("cornice", M(body, *ends), RIM_MAT)]


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
    """One throat side's clean wall (args side "e"/"w"), its five slits alike."""
    side = args.get("side", "e")
    parts, holes = [], []
    for k in range(1, len(SLITS) + 1):
        ps, hole = slit(k)
        parts += ps
        holes.append(hole)
    ps, hole = button()
    parts += ps
    holes.append(hole)
    parts.append(P("band", M(*_band_faces(holes)), BAND_MAT))
    parts += plinth() + band_mouth() + cornice() + seams() + back_and_ends()
    closed = ("_fil", "_rim", "_leaf_a", "_leaf_b", "plinth", "kick", "plinth_line")
    for p in parts:   # the open sheets keep their winding (recalc_face_normals guesses on an open sheet)
        p["solid"] = p["name"].endswith(closed)
    return parts if side == "e" else mirror(parts)
