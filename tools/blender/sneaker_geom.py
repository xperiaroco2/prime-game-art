"""The code-built canvas sneaker's maths (art #196, S1), no bpy: unittest-tested in tools/tests/test_sneaker_geom.py;
sneaker_build.py turns its output into the skinned mesh inside Blender (clothes_dress.py --sneakers).

The sneaker is parametric to the foot it is fitted to: every size comes from that body's foot (its Foot and Toes
vertices, the Foot and Toes bones' heads), so each body type gets its own pair from the same code.

The foot's frame (`Frame`): u along the foot from the heel's back (the Foot head toward the Toes head, flat), v out
from the body's middle (the right shoe is the left one mirrored), z up from the floor. In it:
- the outline (`outline`): the foot's plan hull offset by the clearance, the toes given `toe_room`, smoothed and
  resampled with more columns at the ball (the crease);
- the opening (`opening`): a keyhole, the collar round the heel and the ankle (the plan hull of the foot's points
  at the collar's heights behind the ankle's front, offset) and the throat's slot between the eyelet stays forward
  to `throat` before the ball, its rim heights from the collar's (heel, side dip) to the instep's top;
- the shell (`build`): one grid of rings, the rubber sole's wall (a rounded bottom edge, the foxing's raised band,
  the toe cap's rise at the front), the step to the canvas upper, the upper from the sole up to the opening's rim
  (each outline column joined to its opening point by arc length between anchors: heel to heel, the ball's side to
  the collar's front corner, the toe to the throat), the padded collar rolled in and a short lining; a bottom;
- the tongue, the eyelets (rings on the stays), the laces (criss-cross bars over the tongue) and the bow;
- the bend (`toes_weight`): the rear rigid on Foot, past the ball on Toes, a short smoothstep at the ball.
The texture's zones are rows of the UVs (`Shoe.uv_rows`): sole_strip, join, rim per column, so the painter in
sneaker_build.py draws the foxing stripe and the stitching on straight texel rows.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

Pt2 = tuple[float, float]
Pt3 = tuple[float, float, float]


@dataclass
class Params:
    around: int = 30  # outline columns
    clear: float = 0.004  # the even clearance round the foot (m)
    toe_room: float = 0.008  # the shoe past the toes
    sole_out: float = 0.002  # the sole's wall outside the upper
    sole_top: float = 0.036  # the sole's top (the foxing's top edge; E1j2: tall, as on the concept)
    cap_top: float = 0.046  # the toe cap's top at the toe's tip
    cap_reach: float = 0.060  # how far back from the tip the cap rises (m along u)
    band: tuple[float, float, float] = (0.0095, 0.0145, 0.0008)  # the foxing band (the lower navy line): from, to,
                                                                 # raised by (m)
    cap_step: float = 0.002  # the canvas's step in from the rubber's top edge (the toe cap's lip)
    cap_lip: float = 0.0012  # E1j2: the toe cap's edge (the upper's first row on it) out from the canvas (m)
    toe_cap: tuple[float, float, float] = (0.040, 0.075, 0.012)  # E1j: the rubber toe cap painted over the upper: its
                                       # edge's arc up the upper at the tip, how far back it reaches, its ease (m)
    toe_spring: float = 0.007  # the sole's front lifted off the floor at the tip (m)
    taper: float = 0.34  # E1j: the toe narrower than the ball (a sneaker's last, not a round clog): v x (1 - taper) at the tip
    slim: float = 0.80  # E1j2: the last's width x the foot's (the dress shrinks the kept skin inside the shoe)
    rim_in: float = 0.005  # E1j2: the collar's rim at least this far inside the outline (no flare over a slim last)
    upper_rows: int = 6
    fullness: float = 1.0  # the upper's height profile exponent (under 1: a fuller toe box; E1j2: crisper)
    wall: float = 1.0  # E1j2: the upper's walls rise first, then turn in (the plan's ease exponent; 1: a round shoulder)
    collar_clear: float = 0.007
    heel_clear: float = 0.004  # the collar's extra room at the heel's back
    heel_collar: float = 1.12  # the collar's height at the heel's back, x the ankle's (Foot head) height
    side_collar: float = 1.02  # at its side dip
    gap: float = 0.034  # the throat's slot between the eyelet stays (E1j2: wider, the tongue shows)
    stay_cap: float = 1.10  # the stays' rim at most this x the ankle's height (a low top)
    throat_rise: float = 0.036  # E1j: the stays' rim at the throat over the toe cap's top; a straight lace line
                                # rises from there to the collar's front corners (the foot's instep permitting)
    throat: float = 0.006  # the slot's front end before the ball (m; E1j: the lacing reaches the toe cap's back)
    slot_min: float = 0.055  # the slot at least this long (the top eyelets' end no further back than front - slot_min)
    instep_clear: float = 0.007  # the stays' rim over the instep's top
    pad: float = 0.006  # the collar's padding out
    lining: tuple[float, float] = (0.005, 0.012)  # the rolled collar's lining: in, down (m)
    blend: float = 0.025  # the crease's blend across the ball (m along u)
    eyelets: int = 5  # per side
    eyelet_r: tuple[float, float, float] = (0.0033, 0.0017, 0.0009)  # outer, inner radius, height
    eyelet_in: float = 0.0065  # from the stays' edge
    lace: tuple[float, float] = (0.0036, 0.0032)  # the lace's width, thickness (E1j2: a raised round cord)
    lace_arch: float = 0.004  # E1j2: the laces' rise over the tongue at their middle
    tongue_rise: float = 0.016  # the tongue's top above the top eyelets (E1j2: shows over the bow)
    tongue_lean: float = 0.3  # the tongue's top leaning back, x its rise
    tongue_thick: float = 0.003
    seam_back: float = 0.004  # E1j2: the vamp's seam with the quarters, this far behind the slot's front (m)


@dataclass
class Frame:
    """The foot's frame: origin (the heel's back on the floor, on the foot's axis), fwd and out unit vectors in the
    floor plane (x, y)."""
    origin: Pt2
    fwd: Pt2
    out: Pt2

    def local(self, p: Pt3) -> Pt3:
        dx, dy = p[0] - self.origin[0], p[1] - self.origin[1]
        return (dx * self.fwd[0] + dy * self.fwd[1], dx * self.out[0] + dy * self.out[1], p[2])

    def world(self, q: Pt3) -> Pt3:
        u, v, z = q
        return (self.origin[0] + u * self.fwd[0] + v * self.out[0],
                self.origin[1] + u * self.fwd[1] + v * self.out[1], z)

    def mirrored(self) -> bool:
        """True when (fwd, out, up) is left-handed: the faces' winding flips so the normals still point out."""
        return self.fwd[0] * self.out[1] - self.fwd[1] * self.out[0] < 0


def frame(foot_head: Pt3, toes_head: Pt3, foot_pts: list[Pt3]) -> Frame:
    """The frame of one foot from its bones and its points: fwd the Foot head to the Toes head, flat; out away from
    the body's middle (x = 0); the origin on the axis at the hindmost foot point."""
    fx, fy = toes_head[0] - foot_head[0], toes_head[1] - foot_head[1]
    n = math.hypot(fx, fy)
    if n < 1e-6:
        raise ValueError("the Foot and Toes heads coincide in plan")
    fx, fy = fx / n, fy / n
    ox, oy = fy, -fx
    if ox * foot_head[0] + oy * foot_head[1] < 0:
        ox, oy = -ox, -oy
    back = min((p[0] - foot_head[0]) * fx + (p[1] - foot_head[1]) * fy for p in foot_pts)
    return Frame((foot_head[0] + back * fx, foot_head[1] + back * fy), (fx, fy), (ox, oy))


@dataclass
class Foot:
    """A foot's measures in its frame: its points (u, v, z), the ball's u (the Toes head), the ankle's u and z (the
    Foot head); `sect`, the points the collar's section and the rim are taken from (E1, S1's collar shards: every
    vertex with any Foot, Toes or LowerLeg weight low on the leg, so the ankle's mostly-shin skin over the rim lies
    inside the collar; empty: `pts`)."""
    pts: list[Pt3]
    ball_u: float
    ankle_u: float
    ankle_z: float
    sect: list[Pt3] = field(default_factory=list)

    @property
    def section_pts(self) -> list[Pt3]:
        return self.sect or self.pts

    @property
    def length(self) -> float:
        return max(p[0] for p in self.pts) - min(p[0] for p in self.pts)

    @property
    def width(self) -> float:
        return max(p[1] for p in self.pts) - min(p[1] for p in self.pts)

    def top(self, u: float, half: float, reach: float = 0.006) -> float:
        """The foot's highest point near u within |v| <= half (the instep under the stays); 0 when none."""
        zs = [p[2] for p in self.pts if abs(p[0] - u) <= reach and abs(p[1]) <= half]
        return max(zs) if zs else 0.0


def measure(fr: Frame, pts: list[Pt3], foot_head: Pt3, toes_head: Pt3, sect: list[Pt3] | None = None) -> Foot:
    loc = [fr.local(p) for p in pts]
    return Foot(loc, fr.local(toes_head)[0], fr.local(foot_head)[0], foot_head[2], [fr.local(p) for p in sect or []])


def merge(a: Foot, b: Foot) -> Foot:
    """Both feet in one: the points of both (each in its own frame, so the right foot lies mirrored on the left),
    the bones' means; the pair is then one shape, symmetric left and right."""
    return Foot(a.pts + b.pts, 0.5 * (a.ball_u + b.ball_u), 0.5 * (a.ankle_u + b.ankle_u), 0.5 * (a.ankle_z + b.ankle_z),
                a.sect + b.sect)


# ---- plane curves -------------------------------------------------------------------------------------------------

def hull(pts: list[Pt2]) -> list[Pt2]:
    """The convex hull, counter-clockwise (monotone chain)."""
    p = sorted(set(pts))
    if len(p) < 3:
        return p

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for q in p:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], q) <= 0:
            lo.pop()
        lo.append(q)
    for q in reversed(p):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], q) <= 0:
            hi.pop()
        hi.append(q)
    return lo[:-1] + hi[:-1]


def area(poly: list[Pt2]) -> float:
    return 0.5 * sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly)))


def _norm(x: float, y: float) -> Pt2:
    n = math.hypot(x, y) or 1.0
    return x / n, y / n


def offset(poly: list[Pt2], d: float) -> list[Pt2]:
    """A closed curve moved out by d (either winding) along its vertex normals (the mean of its edges')."""
    out, n = [], len(poly)
    if area(poly) < 0:
        d = -d
    for i in range(n):
        a, b, c = poly[i - 1], poly[i], poly[(i + 1) % n]
        e1, e2 = _norm(b[0] - a[0], b[1] - a[1]), _norm(c[0] - b[0], c[1] - b[1])
        nx, ny = _norm(e1[1] + e2[1], -(e1[0] + e2[0]))
        cos = max(0.3, nx * e1[1] - ny * e1[0])
        out.append((b[0] + nx * d / cos, b[1] + ny * d / cos))
    return out


def densify(poly: list[Pt2], step: float) -> list[Pt2]:
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        k = max(1, math.ceil(math.dist(a, b) / step))
        out += [(a[0] + (b[0] - a[0]) * j / k, a[1] + (b[1] - a[1]) * j / k) for j in range(k)]
    return out


def smooth(poly: list[Pt2], passes: int, w: float = 0.5) -> list[Pt2]:
    """Laplacian smoothing of a closed curve (it shrinks a little: offset after)."""
    for _ in range(passes):
        n = len(poly)
        poly = [((1 - w) * poly[i][0] + w * 0.5 * (poly[i - 1][0] + poly[(i + 1) % n][0]),
                 (1 - w) * poly[i][1] + w * 0.5 * (poly[i - 1][1] + poly[(i + 1) % n][1])) for i in range(n)]
    return poly


def arclen(poly: list[Pt2], closed: bool = True) -> list[float]:
    """The cumulative arc length at each point (and, closed, the total as a last entry)."""
    s, out = 0.0, [0.0]
    pts = poly + [poly[0]] if closed else poly
    for i in range(1, len(pts)):
        s += math.dist(pts[i - 1], pts[i])
        out.append(s)
    return out


def at(poly: list[Pt2], cum: list[float], s: float) -> Pt2:
    """The point at arc length s on a closed curve (cum from arclen)."""
    tot = cum[-1]
    s %= tot
    lo, hi = 0, len(cum) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if cum[mid] <= s:
            lo = mid
        else:
            hi = mid
    a, b = poly[lo % len(poly)], poly[hi % len(poly)]
    t = (s - cum[lo]) / max(1e-12, cum[hi] - cum[lo])
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def start_at_heel(poly: list[Pt2]) -> list[Pt2]:
    """The curve rotated to start at its hindmost point near the axis (least u among |v| small), clockwise in (u, v)
    (from the heel round the outside, v > 0, to the toe and back along the inside)."""
    if area(poly) > 0:
        poly = poly[::-1]
    i = min(range(len(poly)), key=lambda k: poly[k][0] + 0.5 * abs(poly[k][1]))
    return poly[i:] + poly[:i]


def resample(poly: list[Pt2], n: int, dense_at: float | None = None, dense: float = 1.5, sigma: float = 0.02) -> list[Pt2]:
    """n points along a closed curve from its first, by arc length weighted up near u = dense_at (the ball)."""
    fine = densify(poly, 0.001)
    cum = arclen(fine)
    wts = []
    for i in range(len(fine)):
        a, b = fine[i], fine[(i + 1) % len(fine)]
        m = 1.0 if dense_at is None else 1.0 + dense * math.exp(-(((a[0] + b[0]) / 2 - dense_at) / sigma) ** 2)
        wts.append((cum[i + 1] - cum[i]) * m)
    tot, acc, out, j = sum(wts), 0.0, [], 0
    for k in range(n):
        want = tot * k / n
        while j < len(wts) - 1 and acc + wts[j] < want:
            acc += wts[j]
            j += 1
        t = (want - acc) / max(1e-12, wts[j])
        a, b = fine[j], fine[(j + 1) % len(fine)]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


# ---- the outline and the opening ----------------------------------------------------------------------------------

def outline(foot: Foot, p: Params) -> list[Pt2]:
    """The upper's foot line on the sole (clockwise from the heel's back): the plan hull offset by the
    clearance, the toes stretched by toe_room ahead of the ball, smoothed, resampled to p.around columns."""
    h = hull([(q[0], q[1]) for q in foot.pts])
    tip = max(q[0] for q in h)
    span = max(1e-6, tip - foot.ball_u)
    h = [((u + p.toe_room * ((u - foot.ball_u) / span) ** 2) if u > foot.ball_u else u, v) for u, v in h]
    h = taper(h, foot.ball_u, p.taper)
    h = slim(h, p.slim, foot.ankle_u, foot.ball_u)
    c = densify(offset(h, p.clear), 0.004)
    c = offset(smooth(c, 30), p.clear * 0.5)
    return resample(start_at_heel(c), p.around, dense_at=foot.ball_u)


def taper(pts: list[Pt2], ball_u: float, k: float) -> list[Pt2]:
    """The points ahead of the ball pulled toward the axis, more toward the tip (v x (1 - k s^1.5), s 0 at the ball,
    1 at the tip): the toe narrower than the ball; behind the ball unchanged."""
    tip = max(q[0] for q in pts)
    span = max(1e-6, tip - ball_u)
    return [(u, v * (1 - k * max(0.0, (u - ball_u) / span) ** 1.5)) for u, v in pts]


def slim(pts: list[Pt2], k: float, u0: float = -1.0, u1: float = -1.0) -> list[Pt2]:
    """E1j2: the plan's width scaled about its middle line (per u, the middle of its v extent, from the points
    within 1 cm of that u): a slimmer last than the soft foot, its length kept. The scale eases from 1 at u0 (the
    ankle: the heel cup keeps the leg's room, the collar fits it) to k at u1 (the ball) and on; u0 = u1: k
    everywhere."""
    if k >= 1.0:
        return list(pts)
    out = []
    for u, v in pts:
        vs = [q[1] for q in pts if abs(q[0] - u) <= 0.01]
        mid = 0.5 * (min(vs) + max(vs))
        kk = k if u1 <= u0 else 1 - (1 - k) * smoothstep(u0, u1, u)
        out.append((u, mid + (v - mid) * kk))
    return out


def inside_by(b: Pt2, q: Pt2, nin: Pt2, d: float) -> Pt2:
    """E1j2: q moved along the inward normal nin (a unit vector at the outline point b) until it lies at least d
    inside b: the collar's rim never flares outside a slim last."""
    k = (q[0] - b[0]) * nin[0] + (q[1] - b[1]) * nin[1]
    if k >= d:
        return q
    return (q[0] + nin[0] * (d - k), q[1] + nin[1] * (d - k))


def seam_cols(out: list[Pt2], u: float) -> list[float]:
    """E1j2: the fractional outline columns where the outline crosses u, front to back on each side (the vamp's
    stitched seam with the quarter panels)."""
    n, cols = len(out), []
    for c in range(n):
        a, b = out[c], out[(c + 1) % n]
        if (a[0] - u) * (b[0] - u) < 0:
            cols.append(c + (u - a[0]) / (b[0] - a[0]))
    return cols


def tongue_back_u(foot: "Foot", p: Params) -> float:
    """E1j2: the u of the tongue's back face at its top (its top end leans back over the leg's front): the dress
    flattens the leg's front skin behind this, less its clearance, so nothing shows under the laces."""
    return slot_rear(foot, p) - 0.012 - p.tongue_lean * p.tongue_rise - p.tongue_thick


def toe_cap_arc(u: float, v: float, tip_u: float, half_w: float, cap: tuple[float, float, float]) -> float:
    """The rubber toe cap's edge at an outline column (u, v): its arc length up the upper from the canvas's foot
    line; arc at the tip, falling to 0 at reach behind the tip along the sides (a U from above), eased over ease."""
    arc, reach, ease = cap
    back = tip_u - u + 0.5 * reach * (abs(v) / max(1e-6, half_w)) ** 2
    return arc * (1 - smoothstep(reach - ease, reach, back)) * (1 - 0.35 * smoothstep(0.0, reach, back))


def toe_spring(u: float, ball_u: float, tip_u: float, rise: float) -> float:
    """The sole's lift off the floor at u: 0 behind the ball, rise at the tip (a smoothstep)."""
    return rise * smoothstep(ball_u, tip_u, u)


def lace_line(front_z: float, corner_z: float, front_u: float, rear_u: float, u: float) -> float:
    """The straight lace line's height at u: front_z at the throat (front_u), corner_z at the slot's rear end."""
    t = max(0.0, min(1.0, (front_u - u) / max(1e-6, front_u - rear_u)))
    return front_z + (corner_z - front_z) * t


def stay_cap(foot: Foot, p: Params) -> float:
    return p.stay_cap * foot.ankle_z


def stay_z(foot: Foot, p: Params, u: float) -> float:
    """The stays' rim height at u (E1j): a straight lace line from throat_rise over the toe cap's top at the throat to
    the collar's front corners (the stays' cap plus instep_clear), as on a sneaker's last; the foot's own instep no
    longer lifts it (the dress removes the foot's skin under the collar's plane, so a low vamp cannot show it)."""
    corner = stay_cap(foot, p) + p.instep_clear
    return min(lace_line(p.cap_top + p.throat_rise, corner, throat_u(foot, p), slot_rear(foot, p), u), corner)


def slot_rear(foot: Foot, p: Params) -> float:
    """The slot's rear end (the top eyelets' side): in front of the leg where the collar meets the stays (the
    foot's points at the stays' cap height and over, their front plus collar_clear), so the collar's front corners
    never cut into the ankle and a low top never climbs the leg."""
    cap, front = stay_cap(foot, p), throat_u(foot, p)
    leg = [q[0] for q in foot.section_pts if q[2] >= cap - 0.004 and q[0] < front - 0.04]
    u = (max(leg) if leg else foot.ankle_u) + p.collar_clear
    return min(max(u, foot.ankle_u + 0.01), front - p.slot_min)


def throat_u(foot: Foot, p: Params) -> float:
    return foot.ball_u - p.throat


def slot_curve(foot: Foot, p: Params) -> list[Pt2]:
    """The slot's rim in plan, from its lateral rear end forward along the stays, round its front and back along
    the inside, densified."""
    rear, front, g = slot_rear(foot, p), throat_u(foot, p), p.gap / 2
    pts = [(rear, g), (front, g)]
    pts += [(front + g * math.cos(math.pi / 2 - math.pi * i / 8), g * math.sin(math.pi / 2 - math.pi * i / 8))
            for i in range(1, 8)]
    pts += [(front, -g), (rear, -g)]
    out = []
    for a, b in zip(pts, pts[1:]):
        k = max(1, math.ceil(math.dist(a, b) / 0.002))
        out += [(a[0] + (b[0] - a[0]) * j / k, a[1] + (b[1] - a[1]) * j / k) for j in range(k)]
    return out + [pts[-1]]


def _ray_hull(poly: list[Pt2], c: Pt2, d: Pt2) -> Pt2 | None:
    """The farthest hit of the ray c + t d (t > 0) on a closed polygon's edges."""
    best = None
    for i in range(len(poly)):
        a, b = poly[i - 1], poly[i]
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-12:
            continue
        t = ((a[0] - c[0]) * ey - (a[1] - c[1]) * ex) / den
        s = ((a[0] - c[0]) * d[1] - (a[1] - c[1]) * d[0]) / den
        if t > 0 and -1e-9 <= s <= 1 + 1e-9 and (best is None or t > best):
            best = t
    return None if best is None else (c[0] + d[0] * best, c[1] + d[1] * best)


def collar_z(foot: Foot, p: Params, f: float, corner: float) -> float:
    """The collar's rim height at f (0 at the heel's back, 1 at the slot's rear end): heel_collar, dipping to
    side_collar at the middle, rising to the stays' rim."""
    heel, side = p.heel_collar * foot.ankle_z, p.side_collar * foot.ankle_z
    return heel + (side - heel) * smoothstep(0.0, 0.5, f) + (corner - side) * smoothstep(0.55, 1.0, f)


def rim_points(foot: Foot, p: Params, out: list[Pt2]) -> tuple[list[Pt2], list[float], dict]:
    """Each outline column's rim point and height. The columns behind the slot's rear end (round the heel) meet the
    foot's own section at their collar height (the hull of its points from 8 mm under it to 2 cm over it, the
    ankle's bulge over the rim included, hit from the section's
    middle toward the column, plus collar_clear), eased into the slot's corners; the others meet the slot's curve,
    by arc length from its lateral rear end (the first outline column past it on the outside) to the medial one."""
    n = len(out)
    rear = slot_rear(foot, p)
    lat = min(i for i in range(n) if out[i][1] > 0 and out[i][0] >= rear)
    med = max(i for i in range(n) if out[i][1] < 0 and out[i][0] >= rear)
    if not 0 < lat < med < n:
        raise ValueError(f"the outline's slot columns are out of order: {lat}, {med}")
    slot = slot_curve(foot, p)
    s_cum = arclen(slot, closed=False)
    o_cum = arclen(out)
    pts, zs = [None] * n, [0.0] * n
    corner = stay_z(foot, p, rear)
    for i in range(lat, med + 1):
        f = (o_cum[i] - o_cum[lat]) / (o_cum[med] - o_cum[lat])
        s = f * s_cum[-1]
        k = max(j for j in range(len(s_cum)) if s_cum[j] <= s + 1e-12)
        k2 = min(k + 1, len(slot) - 1)
        t = (s - s_cum[k]) / max(1e-12, s_cum[k2] - s_cum[k])
        q = (slot[k][0] + (slot[k2][0] - slot[k][0]) * t, slot[k][1] + (slot[k2][1] - slot[k][1]) * t)
        pts[i], zs[i] = q, stay_z(foot, p, q[0])
    rear_cols = list(range(med + 1, n)) + list(range(0, lat))
    for j, i in enumerate(rear_cols):
        b = out[i]
        f = b[0] / max(1e-6, rear)
        z = collar_z(foot, p, max(0.0, min(1.0, f)), corner)
        sec = [(q[0], q[1]) for q in foot.section_pts if z - 0.008 < q[2] < z + 0.02 and q[0] <= rear + 0.005]
        q = None
        if len(sec) >= 3:
            h = hull(sec)
            c = (sum(x for x, _ in h) / len(h), sum(y for _, y in h) / len(h))
            d = _norm(b[0] - c[0], b[1] - c[1])
            hit = _ray_hull(h, c, d)
            if hit is not None:  # more room at the heel's back, where the crouch's ankle pushes
                cl = p.collar_clear + p.heel_clear * (1 - smoothstep(0.0, 0.5, f))
                q = (hit[0] + d[0] * cl, hit[1] + d[1] * cl)
        if q is None:
            q = b
        nin = _norm(out[i - 1][1] - out[(i + 1) % n][1], out[(i + 1) % n][0] - out[i - 1][0])
        if nin[0] * (sum(x for x, _ in out) / n - b[0]) + nin[1] * (sum(y for _, y in out) / n - b[1]) < 0:
            nin = (-nin[0], -nin[1])
        q = inside_by(b, q, nin, p.rim_in)
        # ease into the slot's corner (the rim's front of the collar, at |v| = gap / 2)
        sgn = 1.0 if b[1] > 0 else -1.0
        w = smoothstep(rear - 0.035, rear, b[0])
        q = (q[0] + (rear - q[0]) * w, q[1] + (sgn * p.gap / 2 - q[1]) * w)
        pts[i], zs[i] = q, z
    # smooth the collar's rim points round the heel (the sections jitter), the slot's columns kept
    for _ in range(4):
        new = list(pts)
        for i in rear_cols:
            a, c = pts[i - 1], pts[(i + 1) % n]
            new[i] = (0.5 * pts[i][0] + 0.25 * (a[0] + c[0]), 0.5 * pts[i][1] + 0.25 * (a[1] + c[1]))
        pts = new
    return pts, zs, {"lat": lat, "med": med, "slot_rear_u": round(rear, 4), "corner_z": round(corner, 4)}


# ---- the mesh -----------------------------------------------------------------------------------------------------

@dataclass
class Shoe:
    verts: list[Pt3] = field(default_factory=list)  # (u, v, z) in the foot's frame
    faces: list[tuple[int, ...]] = field(default_factory=list)
    uvs: list[tuple[Pt2, ...]] = field(default_factory=list)  # per face, per corner, in [0, 1]
    part: list[str] = field(default_factory=list)  # per face: sole, upper, lining, bottom, tongue, eyelet, lace
    uv_rows: dict = field(default_factory=dict)  # the texture's zones (UV v): sole_strip, join, stitch, rim per column
    info: dict = field(default_factory=dict)

    def add(self, q: Pt3) -> int:
        self.verts.append(q)
        return len(self.verts) - 1

    def face(self, idx: tuple[int, ...], uv: tuple[Pt2, ...], part: str) -> None:
        self.faces.append(idx)
        self.uvs.append(uv)
        self.part.append(part)

    @property
    def tris(self) -> int:
        return sum(len(f) - 2 for f in self.faces)


# the texture's atlas (UV, v up): the shell's rows at the bottom, the sole's bottom above, small patches at the top
ASPECT = 2.0  # the atlas image's width over its height
ATLAS = {"shell": (0.0, 0.0, 1.0, 0.62), "bottom": (0.0, 0.64, 0.54, 0.36), "tongue": (0.56, 0.64, 0.2, 0.36),
         "lace": (0.78, 0.64, 0.12, 0.36), "eyelet": (0.92, 0.64, 0.08, 0.36)}


def smoothstep(e0: float, e1: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def toes_weight(u: float, ball_u: float, blend: float) -> float:
    """The Toes bone's share at u: 0 behind the ball's blend, 1 past it, a smoothstep across blend."""
    return smoothstep(ball_u - blend / 2, ball_u + blend / 2, u)


def row_ks(b: Pt2, o: Pt2, zb: float, zo: float, p: Params, cap_arc: float) -> list[float]:
    """E1j2: the upper's rows' parameters k (0 at the join, 1 at the rim) for one column: evenly spread, but where
    the toe cap's arc reaches past half a row the first row sits on the cap's edge (its arc length from the join),
    the rows over it spread evenly up to the rim."""
    n = p.upper_rows
    even = [j / n for j in range(1, n + 1)]
    if cap_arc <= 0:
        return even
    steps = 200
    pts = [_ring_point(b, o, zb, zo, i / steps, p) for i in range(steps + 1)]
    acc, k1 = 0.0, None
    for i in range(1, steps + 1):
        acc += math.dist(pts[i - 1], pts[i])
        if acc >= cap_arc:
            k1 = i / steps
            break
    if k1 is None or k1 <= 0.1 / n:
        return even
    k1 = min(k1, 1 - 1.5 / n)
    return [k1] + [k1 + (1 - k1) * (j - 1) / (n - 1) for j in range(2, n + 1)]


def _ring_point(b: Pt2, o: Pt2, zb: float, zo: float, k: float, p: Params) -> Pt3:
    h = (1 - math.cos(k * math.pi / 2)) ** p.wall
    vz = math.sin(k * math.pi / 2) ** p.fullness
    return (b[0] + (o[0] - b[0]) * h, b[1] + (o[1] - b[1]) * h, zb + (zo - zb) * vz)


def build(foot: Foot, p: Params | None = None) -> Shoe:
    """One shoe (the left; the right is the same in its mirrored frame) in the foot's frame."""
    p = p or Params()
    sh = Shoe()
    out = outline(foot, p)
    n = len(out)
    tip_u = max(q[0] for q in out)
    o_pts, o_z, o_anchor = rim_points(foot, p, out)
    rear_u = slot_rear(foot, p)
    o_anchor["tip"] = max(range(n), key=lambda i: out[i][0] - 2 * abs(out[i][1]))
    sole_n = offset(out, p.sole_out)
    # the sole's wall rows: (out from the upper's line, z); the top row rises into the toe cap at the front
    b0, b1, bh = p.band
    sole_rows = [(p.sole_out - 0.003, 0.0), (p.sole_out, 0.0035), (p.sole_out, b0),
                 (p.sole_out + bh, (b0 + b1) / 2), (p.sole_out, b1), (p.sole_out, None), (p.sole_out - p.cap_step, None)]

    def cap_z(u: float) -> float:
        return p.sole_top + (p.cap_top - p.sole_top) * smoothstep(tip_u - p.cap_reach, tip_u - 0.008, u)

    cols = []  # per column the ring points (u, v, z), bottom to the lining's end
    half_w = max(abs(q[1]) for q in out)
    for c in range(n):
        b = out[c]
        nb = (sole_n[c][0] - b[0], sole_n[c][1] - b[1])
        nn = math.hypot(*nb) or 1.0
        nb = (nb[0] / nn, nb[1] / nn)
        zt = cap_z(b[0])
        lift = toe_spring(b[0], foot.ball_u, tip_u, p.toe_spring)
        ring = []
        for d, z in sole_rows:
            zz = zt if z is None else z + lift
            if z is None and d < p.sole_out:
                zz = zt + p.cap_step * 0.6
            ring.append((b[0] + nb[0] * d, b[1] + nb[1] * d, zz))
        zj = ring[-1][2]
        o = o_pts[c]
        ks = row_ks(b, o, zj, o_z[c], p, toe_cap_arc(b[0], b[1], tip_u, half_w, p.toe_cap))
        for j in range(1, p.upper_rows + 1):
            q = _ring_point(b, o, zj, o_z[c], ks[j - 1], p)
            if j == 1 and ks[0] != 1 / p.upper_rows:  # E1j2: the rubber toe cap's edge stands proud
                lip = p.cap_lip * smoothstep(0.1, 0.5, ks[0] * p.upper_rows)
                q = (q[0] + nb[0] * lip, q[1] + nb[1] * lip, q[2])
            if j == p.upper_rows - 1:  # the padded collar's swell, out along the outline's normal (E1j2: round
                # the collar only; the stays stay flat, a crisp edge at the laces)
                pad = p.pad * (1 - smoothstep(rear_u - 0.025, rear_u, o[0]))
                q = (q[0] + nb[0] * pad, q[1] + nb[1] * pad, q[2])
            ring.append(q)
        # the roll over the rim and the lining, in toward the opening's middle
        inx, iny = _norm(o[0] - b[0], o[1] - b[1])
        ring.append((o[0] + inx * p.lining[0] * 0.5, o[1] + iny * p.lining[0] * 0.5, o_z[c] + 0.0005))
        ring.append((o[0] + inx * p.lining[0], o[1] + iny * p.lining[0], o_z[c] - p.lining[1]))
        cols.append(ring)
    rows = len(cols[0])
    join_row = len(sole_rows) - 1
    rim_row = join_row + p.upper_rows
    # UVs: u by column (the seam at the heel's back), v by arc length from the join ring, one scale
    x0, y0, w, hgt = ATLAS["shell"]
    col_len = []
    for ring in cols:
        acc = [0.0]
        for r in range(1, rows):
            acc.append(acc[-1] + math.dist(ring[r - 1], ring[r]))
        col_len.append(acc)
    perim = arclen([(q[0], q[1]) for q in (cols[c][join_row] for c in range(n))])[-1]
    span = max(a[-1] for a in col_len)
    scale = min(w / perim, hgt / span / ASPECT)  # UV units per metre along u; v takes ASPECT times (square texels)
    vs_ = scale * ASPECT
    vj = y0 + max(a[join_row] for a in col_len) * vs_
    v_of = [[vj + (a[r] - a[join_row]) * vs_ for r in range(rows)] for a in col_len]
    idx = [[sh.add(q) for q in ring] for ring in cols]
    flip = False

    def quad(a, b_, c_, d, uv, part):
        sh.face((a, b_, c_, d), uv, part)

    for c in range(n):
        c2 = (c + 1) % n
        u1, u2 = x0 + w * c / n, x0 + w * (c + 1) / n
        for r in range(rows - 1):
            part = "sole" if r < join_row else ("upper" if r < rim_row else "lining")
            quad(idx[c][r], idx[c][r + 1], idx[c2][r + 1], idx[c2][r],
                 ((u1, v_of[c][r]), (u1, v_of[c][r + 1]), (u2, v_of[c2][r + 1]), (u2, v_of[c2][r])), part)
    # E1j2: the toe cap's edge on the upper's first row where the cap reaches past it (a crisp mesh edge, no
    # zigzag across the quads), else its painted arc
    arcs = [toe_cap_arc(out[c][0], out[c][1], tip_u, half_w, p.toe_cap) for c in range(n)]
    cap_v = [v_of[c][join_row + 1] if abs(arcs[c] - (col_len[c][join_row + 1] - col_len[c][join_row])) < 0.002
             else vj + arcs[c] * vs_ for c in range(n)]
    sh.uv_rows = {"scale": scale, "scale_v": vs_, "join": vj, "cap": cap_v,
                  "stay_cols": [c for c in range(o_anchor["lat"], o_anchor["med"] + 1)], 
                  "sole_v": [v_of[0][r] for r in range(join_row + 1)], "rim": [v_of[c][rim_row] for c in range(n)],
                  "rim_u": [x0 + w * (c + 0.5) / n for c in range(n)], "band_rows": (2, 4),
                  "seam_u": [x0 + w * cf / n for cf in seam_cols(out, throat_u(foot, p) - p.seam_back)]}
    # the bottom: the first ring zipped across (heel to toe along both sides)
    bx, by, bw, bh_ = ATLAS["bottom"]
    us = [cols[c][0][0] for c in range(n)]
    vs = [cols[c][0][1] for c in range(n)]
    umin, umax, vmin, vmax = min(us), max(us), min(vs), max(vs)

    def buv(c):
        return (bx + bw * (us[c] - umin) / (umax - umin), by + bh_ * (vs[c] - vmin) / (vmax - vmin))
    lat = list(range(0, o_anchor["tip"] + 1))
    med = [0] + list(range(n - 1, o_anchor["tip"] - 1, -1))
    i, j = 0, 0
    while i < len(lat) - 1 or j < len(med) - 1:
        if j >= len(med) - 1 or (i < len(lat) - 1 and us[lat[i + 1]] <= us[med[j + 1]]):
            tri = (lat[i], med[j], lat[i + 1])
            i += 1
        else:
            tri = (lat[i], med[j], med[j + 1])
            j += 1
        if len(set(tri)) == 3:
            sh.face(tuple(idx[t][0] for t in tri[::-1]), tuple(buv(t) for t in tri[::-1]), "bottom")
    sh.info.update({"columns": n, "rows": rows, "outline_len_m": round(tip_u - min(us), 4),
                    "outline_width_m": round(vmax - vmin, 4), "rim_z_min_max": [round(min(o_z), 4), round(max(o_z), 4)],
                    "slot": o_anchor,
                    "uv_scale_per_m": round(scale, 3)})
    _stays(sh, foot, p, cols, rim_row, n, o_anchor)
    if flip:
        pass
    return sh


def _surface(cols, c: float, r: int) -> Pt3:
    n = len(cols)
    i = int(math.floor(c)) % n
    t = c - math.floor(c)
    a, b = cols[i][r], cols[(i + 1) % n][r]
    return tuple(a[k] + (b[k] - a[k]) * t for k in range(3))


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.sqrt(sum(x * x for x in a)) or 1.0
    return tuple(x / n for x in a)


def _add(a, b, k=1.0):
    return tuple(a[i] + b[i] * k for i in range(3))


def _box(sh: Shoe, a: Pt3, b: Pt3, side: Pt3, up: Pt3, w: float, t: float, part: str, uvbox, segs=1) -> None:
    """A flat strip (a lace bar) from a to b, w wide along side, t thick along up: a closed box."""
    x, y, bw, bh = uvbox
    rings = []
    for s in range(segs + 1):
        f = s / segs
        c = tuple(a[i] + (b[i] - a[i]) * f for i in range(3))
        rings.append([sh.add(_add(_add(c, side, sx * w / 2), up, sy * t / 2)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    for s in range(segs):
        for k in range(4):
            k2 = (k + 1) % 4
            sh.face((rings[s][k], rings[s][k2], rings[s + 1][k2], rings[s + 1][k]),
                    ((x + bw * k / 4, y + bh * s / segs), (x + bw * (k + 1) / 4, y + bh * s / segs),
                     (x + bw * (k + 1) / 4, y + bh * (s + 1) / segs), (x + bw * k / 4, y + bh * (s + 1) / segs)), part)
    mid = ((x + bw / 2, y + bh / 2),) * 4
    sh.face(tuple(reversed(rings[0])), mid, part)
    sh.face(tuple(rings[-1]), mid, part)


def _tube(sh: Shoe, path: list[Pt3], ups: list[Pt3], w: float, t: float, part: str, uvbox, closed=False,
          caps=True) -> None:
    """A flat strip along a path (a bow's loop or tail): its cross-section w by t, oriented by ups."""
    x, y, bw, bh = uvbox
    rings = []
    m = len(path)
    for s in range(m):
        a, b = path[max(0, s - 1)], path[min(m - 1, s + 1)]
        if closed:
            a, b = path[s - 1], path[(s + 1) % m]
        tan = _unit(_sub(b, a))
        side = _unit(_cross(ups[s], tan))
        up = _unit(_cross(tan, side))
        rings.append([sh.add(_add(_add(path[s], side, sx * w / 2), up, sy * t / 2)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    segs = m if closed else m - 1
    for s in range(segs):
        s2 = (s + 1) % m
        for k in range(4):
            k2 = (k + 1) % 4
            sh.face((rings[s][k], rings[s][k2], rings[s2][k2], rings[s2][k]),
                    ((x + bw * k / 4, y + bh * s / segs), (x + bw * (k + 1) / 4, y + bh * s / segs),
                     (x + bw * (k + 1) / 4, y + bh * (s + 1) / segs), (x + bw * k / 4, y + bh * (s + 1) / segs)), part)
    if not closed and caps:
        mid = ((x + bw / 2, y + bh / 2),) * 4
        sh.face(tuple(reversed(rings[0])), mid, part)
        sh.face(tuple(rings[-1]), mid, part)


def _stays(sh: Shoe, foot: Foot, p: Params, cols, rim_row: int, n: int, anchor: dict) -> None:
    """The tongue, the eyelets, the laces and the bow, on the stays either side of the slot."""
    front, rear = throat_u(foot, p), slot_rear(foot, p)
    # the stays' columns: those whose rim point lies on the slot's straight edges
    def on_slot(c, sgn):
        q = cols[c][rim_row]
        return rear + 0.008 <= q[0] <= front and q[1] * sgn > 0 and abs(abs(q[1]) - p.gap / 2) < 0.004
    eyes = {}
    for sgn in (1, -1):
        cs = [c for c in range(n) if on_slot(c, sgn)]
        if len(cs) < 2:
            raise ValueError(f"the stays have {len(cs)} columns on side {sgn}")
        us = [cols[c][rim_row][0] for c in cs]
        pts = []
        for e in range(p.eyelets):
            target = front - 0.007 - (front - 0.007 - (rear + 0.010)) * e / max(1, p.eyelets - 1)
            # the fractional column whose rim point is at target u (columns run along the slot monotonically)
            order = sorted(zip(us, cs))
            k = max(0, min(len(order) - 2, max(i for i in range(len(order)) if order[i][0] <= target) if order[0][0] <= target else 0))
            (ua, ca), (ub, cb) = order[k], order[k + 1]
            t = (target - ua) / max(1e-9, ub - ua)
            t = max(0.0, min(1.0, t))
            cf = ca + (cb - ca) * t if abs(cb - ca) == 1 else (ca if t < 0.5 else cb)
            rimp = _surface(cols, cf, rim_row)
            below = _surface(cols, cf, rim_row - 1)
            dirn = _unit(_sub(below, rimp))
            centre = _add(rimp, dirn, p.eyelet_in)
            tan = _unit(_sub(_surface(cols, cf + 0.3, rim_row - 1), _surface(cols, cf - 0.3, rim_row - 1)))
            nor = _unit(_cross(tan, dirn))
            if nor[2] < 0:  # keep (tan, dirn, nor) right-handed for the rings' winding
                nor, tan = tuple(-x for x in nor), tuple(-x for x in tan)
            pts.append((centre, nor, tan, dirn))
        eyes[sgn] = pts
    ro, ri, eh = p.eyelet_r
    x, y, bw, bh = ATLAS["eyelet"]
    for sgn, pts in eyes.items():
        for centre, nor, tan, dirn in pts:
            seg = 6
            ring = []
            for s in range(seg):
                a = 2 * math.pi * s / seg
                d = tuple(math.cos(a) * tan[i] + math.sin(a) * dirn[i] for i in range(3))
                ring.append((sh.add(_add(_add(centre, d, ro), nor, -0.0006)), sh.add(_add(_add(centre, d, ro), nor, eh)),
                             sh.add(_add(_add(centre, d, ri), nor, eh))))
            for s in range(seg):  # the outer wall and the top; the hole's floor is the lace
                a_, b_ = ring[s], ring[(s + 1) % seg]
                for k in range(2):
                    sh.face((a_[k], b_[k], b_[k + 1], a_[k + 1]),
                            ((x, y), (x + bw, y), (x + bw, y + bh), (x, y + bh)), "eyelet")
    # the tongue: a slab across the slot from under the throat to above the top eyelets, under the stays
    tx, ty, tw, th = ATLAS["tongue"]
    top_e = eyes[1][-1][0]
    rows = []
    n_al, n_ac = 5, 4
    half = p.gap / 2 + 0.009
    u0, u1 = front + 0.004, rear - 0.012
    for a in range(n_al):
        f = a / (n_al - 1)
        u = u0 + (u1 - u0) * f
        base = min(stay_z(foot, p, u), top_e[2] + 0.002) - 0.0015  # just under the stays' rim (E1j2: it shows)
        lift = p.tongue_rise * smoothstep(0.7, 1.0, f)
        row = []
        for b in range(n_ac):
            g = -1 + 2 * b / (n_ac - 1)
            row.append((u - p.tongue_lean * lift, g * half, base + lift + 0.004 * (1 - g * g)))
        rows.append(row)
    thick = p.tongue_thick
    top = [[sh.add((q[0], q[1], q[2])) for q in row] for row in rows]
    bot = [[sh.add((q[0], q[1], q[2] - thick)) for q in row] for row in rows]

    def tuv(a, b):
        return (tx + tw * b / (n_ac - 1), ty + th * a / (n_al - 1))
    for a in range(n_al - 1):
        for b in range(n_ac - 1):
            sh.face((top[a][b], top[a][b + 1], top[a + 1][b + 1], top[a + 1][b]),
                    (tuv(a, b), tuv(a, b + 1), tuv(a + 1, b + 1), tuv(a + 1, b)), "tongue")
            sh.face((bot[a][b], bot[a + 1][b], bot[a + 1][b + 1], bot[a][b + 1]),
                    (tuv(a, b), tuv(a + 1, b), tuv(a + 1, b + 1), tuv(a, b + 1)), "tongue")
    rim_loop = [(0, b) for b in range(n_ac)] + [(a, n_ac - 1) for a in range(1, n_al)] + \
               [(n_al - 1, b) for b in range(n_ac - 2, -1, -1)] + [(a, 0) for a in range(n_al - 2, 0, -1)]
    for k in range(len(rim_loop)):
        (a1, b1), (a2, b2) = rim_loop[k], rim_loop[(k + 1) % len(rim_loop)]
        sh.face((bot[a1][b1], bot[a2][b2], top[a2][b2], top[a1][b1]), (tuv(a1, b1), tuv(a2, b2), tuv(a2, b2), tuv(a1, b1)),
                "tongue")
    # the laces: criss-cross bars between the eyelets, the first straight across at the throat
    lw, lt = p.lace
    lbox = ATLAS["lace"]
    L, M = eyes[1], eyes[-1]

    def lace_pt(e):
        """Where a lace leaves its eyelet: on the hole's slot side, so the dark ring shows round it."""
        return _add(_add(e[0], e[3], -0.5 * p.eyelet_r[1]), e[1], p.eyelet_r[2] + lt * 0.5 + 0.0004)
    bars = [(L[0], M[0])]
    for e in range(p.eyelets - 1):
        bars += [(L[e], M[e + 1]), (M[e], L[e + 1])]
    for k, (ea, eb) in enumerate(bars):
        a, b = lace_pt(ea), lace_pt(eb)
        lift = 0.001 * (k % 2)
        a, b = (a[0], a[1], a[2] + lift), (b[0], b[1], b[2] + lift)
        up = _unit(_add(ea[1], eb[1]))
        tan = _unit(_sub(b, a))
        side = _unit(_cross(up, tan))
        mid = tuple((a[i] + b[i]) / 2 for i in range(3))
        mid = (mid[0], mid[1], mid[2] + p.lace_arch)
        _tube(sh, [a, mid, b], [up] * 3, lw, lt, "lace", lbox, caps=False)
    # the bow over the top pair: a knot, two flat loops out to the sides, two tails hanging over the stays
    ka, kb = lace_pt(L[-1]), lace_pt(M[-1])
    knot = ((ka[0] + kb[0]) / 2, (ka[1] + kb[1]) / 2, max(ka[2], kb[2]) + 2.5 * lt)
    up = _unit(_add(L[-1][1], M[-1][1]))
    _box(sh, _add(knot, (1, 0, 0), -0.004), _add(knot, (1, 0, 0), 0.004), (0, 1, 0), up, 0.008, 0.004, "lace", lbox)
    for sgn in (1, -1):
        loop = []
        for s in range(5):
            a = 2 * math.pi * s / 5
            loop.append((knot[0] - 0.008 * math.sin(a) - 0.002, knot[1] + sgn * (0.022 * (1 - math.cos(a)) / 2 + 0.003),
                         knot[2] + 0.0015 + 0.004 * (1 - math.cos(a)) / 2))
        _tube(sh, loop, [up] * len(loop), lw * 0.9, lt, "lace", lbox, closed=True)
        tail = [(knot[0] + 0.003, knot[1] + sgn * 0.003, knot[2]),
                (knot[0] + 0.013, knot[1] + sgn * 0.010, knot[2] - 0.003),
                (knot[0] + 0.024, knot[1] + sgn * 0.016, knot[2] - 0.010),
                (knot[0] + 0.032, knot[1] + sgn * 0.020, knot[2] - 0.020)]
        _tube(sh, tail, [up] * len(tail), lw * 0.9, lt, "lace", lbox)
    sh.info["eyelets_per_side"] = p.eyelets
    sh.info["lace_bars"] = len(bars)


# ---- the toes' bend cap -------------------------------------------------------------------------------------------

def soft_cap_deg(angle: float, cap: float, knee: float) -> float:
    """A bend angle capped softly: unchanged up to cap - knee, then easing into cap (never over it)."""
    if cap <= 0 or knee < 0 or knee > cap:
        raise ValueError(f"cap {cap} and knee {knee} must satisfy 0 <= knee <= cap, cap > 0")
    lo = cap - knee
    if angle <= lo or knee == 0:
        return min(angle, cap)
    return lo + knee * math.tanh((angle - lo) / knee)


def cap_quat(q: tuple[float, float, float, float], cap: float, knee: float) -> tuple[float, float, float, float]:
    """A rotation (w, x, y, z) about the same axis by soft_cap_deg of its angle (degrees)."""
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    if w < 0:
        w, x, y, z = -w, -x, -y, -z
    ang = math.degrees(2 * math.acos(min(1.0, w)))
    new = soft_cap_deg(ang, cap, knee)
    if new >= ang - 1e-9:
        return (w, x, y, z)
    s = math.sqrt(x * x + y * y + z * z) or 1.0
    h = math.radians(new) / 2
    return (math.cos(h), x / s * math.sin(h), y / s * math.sin(h), z / s * math.sin(h))
