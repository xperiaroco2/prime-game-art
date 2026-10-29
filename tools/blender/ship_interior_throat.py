"""The clean throat (art #263, step B of 2026-10-29; the engineer's yes "fold at 2.10"; docs/ship.md "The clean
throat"): the throat's walls, the ramp frame and the hall jambs, drawn in <raw>/ship/v5/gills-throat/clean/drawing.

- `th_wall_e` and its mirror `th_wall_w`: each side wall, flat and vertical from the deck to the fold (2.10), then a
  25 cm cove (a lighter metal, a 1.4 cm dark line at the fold) in to the flat ceiling at 2.30 (ship.toml throat
  `chamfer`); the plinth (0-0.60, 3 cm proud) with its cyan line; one clean panel from the ramp frame to the hall
  jamb (s 1.668-3.88). Under the entry tunnel (s 0.02 to the frame) only the plinth and the band to the tunnel's own
  bend (1.45): above it the tunnel leans in (`tunnel_chamfer`, the hull's jamb plates). The gill covers and the
  button (step 2) come from ship_interior_cover.py; no slits in
  this step (the engineer, 2026-10-29: the slits come back as hinged gill covers; ship_interior_gills.py is parked).
- `th_frame`: one frame to the ramp in the roof line's plane (y roof_y - 0.039 .. roof_y + 0.046): on each side it
  fills the step from the tunnel's profile to the room's with an 8 cm trim round the tunnel's opening, and a flush
  bar across the ceiling (no drop: the 2.30 head room holds). It replaces the roof line's arch (th_arch).
- `th_jambs`: one jamb at each hall corner K, the deck to the hall's rim (3.20), replacing the hall pilasters there:
  its end face square to the wall at s 3.88, its front on the corner sub-facet's header plane (1.6 cm proud into the
  throat), its hall face 1.6 cm proud of the header's hall face, so the wall, plinth, line and cove all end on it.

The walls' frame (as the gills'): the piece's origin on the wall's line at the mouth's corner (east (1.65, -7.1),
west mirrored), local x = s along the wall toward the hall, local y into the throat, h absolute. A point is given in
the wall's developed coordinates (u = s, t up the profile from the deck, w out of the surface toward the room). The
frame and the jambs are built in hall-relative plan coordinates (placed at the hall's centre, as throat_ceil).
Plain Python (ship_build.py makes the meshes)."""

from __future__ import annotations

import math

import ship_interior as S
import ship_interior_cover as C
import ship_interior_geom as G

P, M = S.P, S.M
FLOOR = S.FLOOR
FOLD, COVE, CEIL = S.TH_BEND, S.TH_IN, S.TH_H            # 2.10, 0.25, 2.30 (ship.toml throat chamfer, clear_h)
TUN_BEND, TUN_IN = S.TUN_BEND, S.TUN_IN                   # 1.45, 0.55: the entry tunnel's own profile
LEAN = math.hypot(COVE, CEIL - FOLD)                      # the cove's length up its slope (0.320)
LV, LH = COVE / LEAN, (CEIL - FOLD) / LEAN                # its direction (into the room, up)
T_TOP = FOLD + LEAN                                       # the cove's top in t (the ceiling's edge)
T_OVER = 0.02                                             # the cove runs on this far past the ceiling's edge, into it
_MK, _KK = S.TH_PTS[1], S.TH_PTS[2]                       # hall-relative: the mouth's corner, the hall's corner K
WALL_LEN = math.dist(_MK, _KK)                            # 4.051
WALL_D = ((_KK[0] - _MK[0]) / WALL_LEN, (_KK[1] - _MK[1]) / WALL_LEN)   # the east wall's direction (0.312, 0.950)
WALL_N = (-WALL_D[1], WALL_D[0])                          # into the throat (east wall)
WALL_YAW = math.degrees(math.atan2(WALL_D[1], WALL_D[0]))  # 71.80
KX = 1.0 / WALL_D[1]                                      # an across distance (or s) as a plan y or x offset

BAND_MAT, DARK, COVE_MAT, JAMB_MAT, FRAME_MAT = "int_silver_b", "int_dark", "hull_silver", "int_silver_a", "int_silver_c"
PLINTH_S0 = 0.02                                          # the plinth from the mouth's corner (under the tunnel too)
PLINTH_H, PLINTH_W = 0.60, 0.03                           # the plinth: 0-60 cm, 3 cm proud of the band
KICK_H = 0.08
LINE_H = (PLINTH_H - 0.036, PLINTH_H - 0.012)             # its cyan line, 2.4 cm (as built in the gills step 5)
GAP_H = 0.014                                             # the dark line at the fold, under the cove
MOUTH_TOP = 0.002                                         # the band under the tunnel stops this far under its bend

FRAME_Y = (S.TH_ROOF - 0.0392, S.TH_ROOF + 0.0458)        # the ramp frame's body in plan y (hall-relative): -5.60 .. -5.515
TRIM = 0.08                                               # its trim round the tunnel's opening (in from the tunnel's walls)
BAR = 0.005                                               # the bar across the ceiling: this far under it
TUCK = 0.02                                               # the frame runs this far into the walls and up into the ceiling
JAMB_U = 3.88                                             # the hall jamb's end face along the wall (the old button ended 3.84)
JAMB_PROUD = 0.016                                        # its hall face this far proud of the header's
COVER_SIDES = ("e", "w")                                  # the gill covers: five on each wall (step 2), the west mirrored
DROP_D = 0.02                                             # the header's throat face carried down to the cove by the jamb


def s_of_y(y: float) -> float:
    """s along the wall at hall-relative plan y."""
    return (y - _MK[1]) / WALL_D[1]


S_F0, S_F1 = s_of_y(FRAME_Y[0]), s_of_y(FRAME_Y[1])       # 1.579, 1.668: the frame's front and aft faces on the wall


def point(u: float, t: float, w: float = 0.0) -> tuple[float, float, float]:
    """Developed (u, t, w) -> the east wall piece's (x, y, h); the fold's points on the mitre."""
    if t < FOLD - 1e-9:
        return (u, w, FLOOR + t)
    if abs(t - FOLD) <= 1e-9:
        return (u, w, FLOOR + FOLD - w * LV / (1.0 + LH))
    return (u, (t - FOLD) * LV + w * LH, FLOOR + FOLD + (t - FOLD) * LH - w * LV)


def _poly(pts: list, w: float = 0.0, flip: bool = False):
    """A convex (u, t) polygon at w (its t all on one side of the fold), counter-clockwise seen from the room."""
    verts = [point(u, t, w) for u, t in pts]
    f = tuple(range(len(pts)))
    return verts, [f[::-1] if flip else f]


# --- the hall corner: the header plane in the wall's (u, v) plan frame -------------------------------------------------
def _uv(p) -> tuple[float, float]:
    """A hall-relative plan point -> (u along the east wall from the mouth's corner, v into the throat)."""
    dx, dy = p[0] - _MK[0], p[1] - _MK[1]
    return dx * WALL_D[0] + dy * WALL_D[1], dx * WALL_N[0] + dy * WALL_N[1]


def _xy(u: float, v: float) -> tuple[float, float]:
    return _MK[0] + WALL_D[0] * u + WALL_N[0] * v, _MK[1] + WALL_D[1] * u + WALL_N[1] * v


def header_line(offset: float = 0.0) -> tuple[float, float, float]:
    """(a, b, c): the corner sub-facet's chord as a u + b v = c in the wall's frame, `offset` toward the throat
    (positive) or the hall (negative); a u + b v <= c is the throat's side."""
    k, _v, m, dist = S.th_corner_chord()
    md, mn = m[0] * WALL_D[0] + m[1] * WALL_D[1], m[0] * WALL_N[0] + m[1] * WALL_N[1]
    mm = m[0] * _MK[0] + m[1] * _MK[1]
    # the chord: m . p = dist, p = MK + u D + v N; the throat lies outside the hall (m . p >= dist)
    return -md, -mn, mm - dist - offset


def v_on(line, u: float) -> float:
    a, b, c = line
    return (c - a * u) / b


def u_on(line, v: float) -> float:
    a, b, c = line
    return (c - b * v) / a


FRONT = header_line(0.0)                                  # the jamb's front: the header's plane (the chord)
JAMB_V = v_on(FRONT, JAMB_U)                              # its end face's depth from the wall (0.131)
COVE_END = u_on(FRONT, COVE)                              # where the cove's top line meets the header's plane (3.72)


def numbers() -> dict:
    """The clean throat's numbers for the tests and the report (metres)."""
    return {"fold": FOLD, "cove": COVE, "ceil": CEIL, "lean": LEAN, "wall_len": WALL_LEN, "s_frame": (S_F0, S_F1),
            "jamb_u": JAMB_U, "jamb_v": JAMB_V, "cove_end": COVE_END, "plinth_h": PLINTH_H, "line_h": LINE_H,
            "trim": TRIM, "frame_y": FRAME_Y}


# --- the walls -------------------------------------------------------------------------------------------------------
def _cut_cove(q: list) -> list:
    """A cove polygon (u, t) on the throat's side of the jamb's front (the line linear in (u, v), v = (t - FOLD) LV)."""
    a, b, c = FRONT
    return S._clip2(q, a, b * LV, c + b * LV * FOLD)


def cove_start(t: float) -> float:
    """The cove's front end at t: on the plane 1 cm inside the frame's aft face (constant plan y), not square to the
    wall: square, its top began 6.8 cm aft of the frame and left a lit notch at the corner (step B's close-up)."""
    return S_F1 - 0.01 - max(0.0, t - FOLD) * LV * WALL_N[1] / WALL_D[1]


def wall_parts(cover: bool = False) -> list:
    """The east wall: band (one panel), plinth, kick, cyan line, the fold's dark line, the cove and the back skin;
    `cover`: the five gill covers and the button (ship_interior_cover.py), their pockets cut into the band."""
    u0, u1 = S_F0 + 0.01, JAMB_U
    band = [_poly([(PLINTH_S0, PLINTH_H), (u0, PLINTH_H), (u0, TUN_BEND - MOUTH_TOP), (PLINTH_S0, TUN_BEND - MOUTH_TOP)]),
            C.band_with_holes(point, u0, u1, PLINTH_H, FOLD - GAP_H) if cover else
            _poly([(u0, PLINTH_H), (u1, PLINTH_H), (u1, FOLD - GAP_H), (u0, FOLD - GAP_H)])]
    gap = _poly([(S_F1 - 0.01, FOLD - GAP_H), (u1, FOLD - GAP_H), (u1, FOLD), (S_F1 - 0.01, FOLD)], 0.0)
    tt = T_TOP + T_OVER
    cove = [_poly(q) for q in [_cut_cove([(cove_start(FOLD), FOLD), (u1, FOLD), (u1, tt), (cove_start(tt), tt)])]
            if len(q) >= 3]
    fr = G.Frame((0.0, 0.0, FLOOR), (1, 0, 0), (0, 0, 1), (0, 1, 0))
    body = G.slab(fr, G.rect(PLINTH_S0, JAMB_U, KICK_H, PLINTH_H), -0.2, PLINTH_W, 0.008)
    kick = G.slab(fr, G.rect(PLINTH_S0, JAMB_U, 0.0, KICK_H), -0.2, PLINTH_W - 0.012)
    line = G.slab(fr, G.rect(PLINTH_S0, JAMB_U, *LINE_H), PLINTH_W - 0.001, PLINTH_W + 0.004)
    back = [_poly([(u0, PLINTH_H), (u1, PLINTH_H), (u1, FOLD), (u0, FOLD)], -0.2, flip=True),
            _poly(_cut_cove([(u0, FOLD), (u1, FOLD), (u1, T_TOP + T_OVER), (u0, T_TOP + T_OVER)]), -0.2, flip=True)]
    parts = [P("band", M(*band), BAND_MAT), P("fold_line", M(gap), DARK), P("cove", M(*cove), COVE_MAT),
             P("plinth", body, BAND_MAT), P("kick", kick, DARK), P("plinth_line", line, "int_cyan__gill_plinth"),
             P("back", M(*back), BAND_MAT)]
    for p in parts:   # the open sheets keep their winding (recalc_face_normals guesses on an open sheet)
        p["solid"] = p["name"] in ("plinth", "kick", "plinth_line")
    return parts + ([q for k in C.SLOTS for q in C.cover_parts(point, k)] + C.button(point) if cover else [])


def mirror(parts: list) -> list:
    """The west piece: x mirrored (faces turned back)."""
    out = []
    for p in parts:
        q = dict(p)
        q["verts"] = [(-x, y, h) for x, y, h in p["verts"]]
        q["faces"] = [tuple(f[::-1]) for f in p["faces"]]
        if p.get("origin"):   # a moving part's hinge (the gill cover)
            x, y, h = p["origin"]
            q["origin"] = (-x, y, h)
        out.append(q)
    return out


def th_wall(args, layout):
    """One throat side's clean wall (args side "e"/"w")."""
    side = args.get("side", "e")
    parts = wall_parts(cover=side in COVER_SIDES)
    return parts if side == "e" else mirror(parts)


# --- the hall jambs (hall-relative plan coordinates) -------------------------------------------------------------------
def _chord_normal() -> tuple[float, float]:
    """The corner sub-facet chord's normal toward the throat, in the wall's (u, v) frame."""
    _k, _v, m, _d = S.th_corner_chord()
    return m[0] * WALL_D[0] + m[1] * WALL_D[1], m[0] * WALL_N[0] + m[1] * WALL_N[1]


def jamb_outline(sx: int = 1) -> list[tuple[float, float]]:
    """The east (sx 1) or west (-1) jamb's plan outline (hall-relative): the wall's line at JAMB_U, out along the end
    face (square to the wall) to the front (the header's plane), then square to the chord
    through the header's depth to its hall face (JAMB_PROUD proud of the header's), along that to K's normal and back
    to K: the reveal face (square to the chord) is what the opening shows, the end face what the wall runs into."""
    mu, mv = _chord_normal()
    a0, a1 = (JAMB_U, 0.0), (JAMB_U, JAMB_V)
    deep = S.TH_HEAD_D + 2 * JAMB_PROUD
    a2 = (a1[0] - deep * mu, a1[1] - deep * mv)
    k = _uv(_KK)
    b0 = (k[0] - (S.TH_HEAD_D + JAMB_PROUD) * mu, k[1] - (S.TH_HEAD_D + JAMB_PROUD) * mv)
    ring = [_xy(*q) for q in (a0, a1, a2, b0, k)]
    return [(sx * x, y) for x, y in ring]


def drop(sx: int = 1):
    """The header's throat face carried down from the ceiling to the cove between the jamb's front corner (JAMB_U,
    JAMB_V) and the cove's top line (COVE_END, COVE): the cove ends on it (step A's drawing: "the cove's top and the
    ceiling on the header plane"), so no gap opens under the header by the corner. DROP_D thick, hall-ward."""
    mu, mv = _chord_normal()
    pts = []
    for (u, v), h in (((JAMB_U, JAMB_V), FOLD + JAMB_V / COVE * (CEIL - FOLD)), ((COVE_END, COVE), CEIL),
                      ((COVE_END, COVE), CEIL + 0.01), ((JAMB_U, JAMB_V), CEIL + 0.01)):
        pts.append((u, v, h))
    verts = []
    for w in (0.0, -DROP_D):
        verts += [(*_xy(u + w * mu, v + w * mv), FLOOR + h) for u, v, h in pts]
    verts = [(sx * x, y, h) for x, y, h in verts]
    faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    return verts, faces


def th_jambs(args, layout):
    """The two hall jambs, the deck to the hall's rim (a collider each: `-col` by the piece's collide), and the
    header's drop to the cove by each."""
    fr = G.floor_frame(0.0)
    out = []
    for sx, side in ((1, "e"), (-1, "w")):
        q = jamb_outline(sx)
        if G.area2(q) < 0:
            q = q[::-1]
        out.append(P("jamb_" + side, G.slab(fr, q, FLOOR, FLOOR + S.H_HALL), JAMB_MAT))
    out.append(P("drop", M(drop(1), drop(-1)), BAND_MAT))
    return out


# --- the ramp frame (hall-relative plan coordinates) -------------------------------------------------------------------
def _x_wall(y: float) -> float:
    """The east wall's inner line's x at hall-relative y."""
    return _MK[0] + WALL_D[0] * s_of_y(y)


def x_room(h: float) -> float:
    """The room's profile at the frame's aft face: the east wall's x at height h over the deck."""
    lean = 0.0 if h <= FOLD else min(1.0, (h - FOLD) / (CEIL - FOLD)) * COVE
    return _x_wall(FRAME_Y[1]) - lean * KX


def x_tun(h: float) -> float:
    """The tunnel's profile at the frame's front face."""
    lean = 0.0 if h <= TUN_BEND else min(1.0, (h - TUN_BEND) / (CEIL - TUN_BEND)) * TUN_IN
    return _x_wall(FRAME_Y[0]) - lean * KX


def frame_heights() -> list[float]:
    return sorted({0.0, TUN_BEND, FOLD, CEIL} | {TUN_BEND + (CEIL - TUN_BEND) * i / 8 for i in range(1, 8)}
                  | {FOLD + (CEIL - FOLD) * i / 4 for i in range(1, 4)})


def frame_side(sx: int = 1):
    """One side of the frame: the region between the trim's inner edge (x_tun - TRIM) and the room's or tunnel's
    outer line (TUCK into the wall), the deck to the ceiling, from the frame's front to its aft face: one closed solid
    (rings of inner and outer points at the frame's heights)."""
    hs = frame_heights()
    inner = [(x_tun(h) - TRIM, FLOOR + h) for h in hs]
    outer = [(max(x_room(h), x_tun(h)) + TUCK * KX, FLOOR + h) for h in hs]
    outer[-1] = (outer[-1][0], FLOOR + CEIL + TUCK)       # the outer top corner up into the ceiling
    loop = inner + outer[::-1]                             # up the inner edge, down the outer
    n = len(loop)
    verts = [(sx * x, y, h) for y in FRAME_Y for x, h in loop]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return verts, faces


def th_frame(args, layout):
    """The ramp frame: both sides and the flush bar across the ceiling."""
    xa = x_tun(CEIL) - TRIM + TUCK
    bar = G.bbox(-xa, xa, FRAME_Y[0], FRAME_Y[1], FLOOR + CEIL - BAR, FLOOR + CEIL + TUCK)
    return [P("frame", M(frame_side(1), frame_side(-1)), FRAME_MAT), P("bar", bar, FRAME_MAT)]
