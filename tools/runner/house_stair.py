"""The attic stair's section (#183): the walked profile of the kit's stair_attic (the floor, its nosing ramp, the
attic floor at its top), the game's standing capsule resting on it, and the attic slab over the foot and the hatch's
hole above. Pure Python: `surface` and `sphere_centre` are the sweep test_house_attic_stair asserts the clearance
with; `section` measures the sweep and `section_png` draws it (the review sheet's side section, `attic --stair`)."""

from __future__ import annotations

import math
from pathlib import Path

from . import house_attic, house_layout, house_sky
from .commands import _kit

CAPSULE_H = house_attic.PLAYER_H  # base_mode.tres capsule_height_m
CAPSULE_R = house_attic.PLAYER_R  # base_mode.tres capsule_radius_m


def surface(p: dict, u: float) -> float:
    """The walked collision's height at u metres along the run from the foot (the floor, the nosing ramp, the top)."""
    run, rise = float(p["run"]), float(p["rise"])
    (u0, _), _, _ = _kit.geom().nosing_ramp(p)
    if u < u0:
        return 0.0
    if u > run:
        return rise
    return (u - u0) * rise / (run - u0)


def sphere_centre(p: dict, u: float, r: float) -> float:
    """The lowest height of the capsule's bottom sphere centre over the profile at u (resting on it, exact for a
    piecewise-linear profile sampled finely, the riser's top corner included)."""
    best = -1e9
    n = 80
    for i in range(n + 1):
        v = u - r + 2 * r * i / n
        best = max(best, surface(p, v) + math.sqrt(max(0.0, r * r - (v - u) ** 2)))
    if abs(u) <= r:  # the riser's top corner
        best = max(best, surface(p, 0.0) + math.sqrt(r * r - u * u))
    return best


def seg_rect_distance(ax: float, a0: float, a1: float, x0: float, x1: float, y0: float, y1: float) -> float:
    """The distance from the vertical segment x = ax, y in [a0, a1] to the rectangle [x0, x1] x [y0, y1]."""
    dx = max(x0 - ax, 0.0, ax - x1)
    dy = max(y0 - a1, 0.0, a0 - y1)
    return math.hypot(dx, dy)


def section(step: float = 0.01) -> dict:
    """The sweep along the stair's axis (u from the foot, 1 m before it to 1 m past the top): the capsule's bottom
    sphere centre per u and its gap to the attic slab over the foot (east of the hole), the worst gap and where."""
    g = _kit.geom()
    spec = g.load_spec(_kit.SPEC)
    p = next(pc for pc in spec["pieces"] if pc["id"] == "stair_attic")
    data = house_layout.load()
    attic = next(lv for lv in data["levels"] if lv["level"] == "attic")
    st = next(s for s in attic["stairs"] if s["id"] == "attic_stair")
    hole = house_layout.hatch_hole(next(h for h in attic["holes"] if h["id"] == "hatch"), data)
    run, rise, slab = float(p["run"]), float(p["rise"]), float(spec["grid"]["slab_m"])
    x, _, w, _ = st["rect"]
    u_hole_end = x + w - (hole[0] + hole[2])
    path, worst = [], (1e9, 0.0)
    u = -1.0
    while u <= run + 1.0 + 1e-9:
        c = sphere_centre(p, u, CAPSULE_R)
        gap = seg_rect_distance(u, c, c + CAPSULE_H - 2 * CAPSULE_R, -10.0, u_hole_end, rise - slab, rise) - CAPSULE_R
        path.append([round(u, 3), round(c, 4), round(gap, 4)])
        worst = min(worst, (gap, u))
        u += step
    h, going, n = g.stair_numbers(p)
    return {"piece": p, "run": run, "rise": rise, "slab": slab, "riser": h, "going": going, "risers": n,
            "pitch_deg": math.degrees(math.atan2(h, going)), "ramp": g.nosing_ramp(p), "u_hole_end": u_hole_end,
            "hole": hole, "path": path, "worst_gap": worst[0], "worst_u": worst[1]}


class _Canvas:
    def __init__(self, w: int, h: int, bg=(247, 247, 247)) -> None:
        self.w, self.h = w, h
        self.px = [bytearray(bytes(bg) * w) for _ in range(h)]

    def dot(self, x: float, y: float, c, r: float = 1.0) -> None:
        for j in range(int(y - r), int(y + r) + 1):
            for i in range(int(x - r), int(x + r) + 1):
                if 0 <= i < self.w and 0 <= j < self.h and (i - x) ** 2 + (j - y) ** 2 <= r * r + 0.5:
                    self.px[j][3 * i:3 * i + 3] = bytes(c)

    def line(self, a, b, c, r: float = 1.0) -> None:
        n = max(1, int(math.dist(a, b)))
        for k in range(n + 1):
            t = k / n
            self.dot(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, c, r)

    def poly(self, pts, c) -> None:
        """Fills a polygon (even-odd, pixel centres)."""
        y0, y1 = max(0, int(min(p[1] for p in pts))), min(self.h - 1, int(max(p[1] for p in pts)) + 1)
        for j in range(y0, y1 + 1):
            yc, xs = j + 0.5, []
            for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
                if (ay <= yc < by) or (by <= yc < ay):
                    xs.append(ax + (yc - ay) * (bx - ax) / (by - ay))
            xs.sort()
            for xa, xb in zip(xs[::2], xs[1::2]):
                for i in range(max(0, int(xa + 0.5)), min(self.w, int(xb + 0.5))):
                    self.px[j][3 * i:3 * i + 3] = bytes(c)


WOOD, SLAB, RAMP, CAP, PATH, BAD, FLOOR = (176, 124, 74), (150, 150, 158), (200, 40, 40), (40, 90, 200), \
    (10, 30, 110), (230, 120, 0), (90, 90, 90)


def section_png(path: Path, sec: dict | None = None, width: int = 1280) -> dict:
    """Draws the section (foot on the right, as the stair climbs west seen from the stairwell, south): the landing
    floor, the steps (wood), the walked ramp (red), the attic slab either side of the hole (grey), the capsule's
    outline every 0.4 m (blue), its bottom sphere's path (dark blue) and the closest approach to the slab (orange)."""
    sec = sec or section()
    p, run, rise, slab = sec["piece"], sec["run"], sec["rise"], sec["slab"]
    u_lo, u_hi, h_lo, h_hi = -1.6, run + 1.6, -0.3, rise + CAPSULE_H + 0.4
    s = (width - 40) / (u_hi - u_lo)
    height = int((h_hi - h_lo) * s) + 40
    cv = _Canvas(width, height)

    def P(u: float, h: float):  # u grows west (to the left): the foot is on the right
        return (20 + (u_hi - u) * s, 20 + (h_hi - h) * s)
    cv.poly([P(u_lo, 0), P(u_hi, 0), P(u_hi, h_lo), P(u_lo, h_lo)], FLOOR)
    h, going, n = sec["riser"], sec["going"], sec["risers"]
    for k in range(n - 1):  # tread k's top at (k + 1) * h, u from k to k + 1 goings; the last riser meets the attic floor
        cv.poly([P(k * going, 0), P(k * going, (k + 1) * h), P((k + 1) * going, (k + 1) * h), P((k + 1) * going, 0)],
                WOOD)
    cv.poly([P(u_lo, rise), P(sec["u_hole_end"], rise), P(sec["u_hole_end"], rise - slab), P(u_lo, rise - slab)], SLAB)
    cv.poly([P(run, rise), P(u_hi, rise), P(u_hi, rise - slab), P(run, rise - slab)], SLAB)
    (a, b), _, (c, d) = sec["ramp"]
    cv.line(P(a, b), P(c, d), RAMP, 2.0)
    for u, cz, _ in sec["path"][::40]:
        top = cz + CAPSULE_H - 2 * CAPSULE_R
        for k in range(73):
            t = k * math.pi / 72
            cv.dot(*P(u + CAPSULE_R * math.cos(t), cz - CAPSULE_R * math.sin(t)), CAP)
            cv.dot(*P(u + CAPSULE_R * math.cos(t), top + CAPSULE_R * math.sin(t)), CAP)
        cv.line(P(u - CAPSULE_R, cz), P(u - CAPSULE_R, top), CAP)
        cv.line(P(u + CAPSULE_R, cz), P(u + CAPSULE_R, top), CAP)
    pts = [P(u, cz) for u, cz, _ in sec["path"]]
    for a, b in zip(pts, pts[1:]):
        cv.line(a, b, PATH, 1.5)
    wu = sec["worst_u"]
    wc = next(cz for u, cz, _ in sec["path"] if abs(u - wu) < 1e-6)
    top = wc + CAPSULE_H - 2 * CAPSULE_R
    corner = (sec["u_hole_end"], rise - slab)
    near = (wu + CAPSULE_R * (corner[0] - wu) / math.hypot(corner[0] - wu, corner[1] - top),
            top + CAPSULE_R * (corner[1] - top) / math.hypot(corner[0] - wu, corner[1] - top))
    cv.line(P(*near), P(*corner), BAD, 2.5)
    cv.dot(*P(*corner), BAD, 5.0)
    house_sky.write_png(path, width, height, [bytes(r) for r in cv.px])
    return {"png": path.as_posix(), "size": [width, height], "worst_gap_m": round(sec["worst_gap"], 3),
            "worst_u_m": round(wu, 3), "pitch_deg": round(sec["pitch_deg"], 2), "riser_m": round(h, 4),
            "going_m": round(going, 4), "risers": n, "hole": sec["hole"], "capsule": [CAPSULE_H, CAPSULE_R]}
