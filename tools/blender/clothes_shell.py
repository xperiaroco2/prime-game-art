"""The dungarees' upper body as our own clean pieces, pure maths (art #196, clothes step 2, C1f; no bpy,
unittest-tested in tools/tests/test_clothes_shell.py). clothes_dress.py --shell imports it.

The hybrid route: a fitted top is a shell of the body itself, the loose lower parts stay Meshy's.
- The striped top: the body's own faces over the torso and arms, each vertex moved out along its normal by the
  clearance (offset: less where the kept Meshy denim lies nearer, tapered to a few mm at the hem, which is tucked under
  the trousers), cut by planes at a round crew neck, the wrists and the hem, with a rolled lip toward the body at the
  collar and the cuffs. Its weights are the body's (same vertices), so no clip can push the body through it.
- Its UVs (region, torso_uv, arm_uv, unwrap): the torso a cylinder round the vertical axis (v by height), each arm a
  cylinder round its T-pose axis (v along the arm), all at one scale in v, so a stripe is an image row
  (stripe_cover): navy and white bands of one width, from the collar down and from each cuff up.
- The Meshy garment keeps the trousers below the waistband, the bib inside its outline at the front and the back
  panel inside its V (keep_face); the straps are new strips from the bib's top corners over the shoulders down to the
  back's V (strap_x: the strip's x along its angle round the shoulder axis).
- The finish (C1g): a bronze buckle at each front strap end, a rectangular ring with chamfered corners
  (buckle_ring) over the strap and a domed button (button) at the tab's end on the bib; two dashed stitch lines along
  each strap (stitch_mask, painted into a free patch of the garment's texture, across the strap's lat_us); the torso
  island's AO wrapped across its back seam (seam_wrap_cols), so mips and the normal map see no edge there.
"""
from __future__ import annotations

import math

TORSO, LEFT, RIGHT = "torso", "left", "right"


def region(x: float, z: float, x_seam: float, z_arm: float) -> str:
    """The shell piece a face belongs to by its centre: an arm beyond the shoulder seam's plane |x| = x_seam above
    z_arm (a set-in sleeve: the arm's rings meet the torso's horizontal stripes at a vertical seam), else the torso."""
    if abs(x) > x_seam and z > z_arm:
        return LEFT if x > 0 else RIGHT
    return TORSO


def torso_uv(x: float, y: float, z: float, yc: float, u0: float, width: float, v0: float, per_m: float,
             z_top: float) -> tuple[float, float]:
    """The torso's UV: u by the angle round the vertical axis through (0, yc), the front centre in the middle of
    [u0, u0 + width] and the seam at the back centre; v = v0 + (z_top - z) * per_m (down from the collar)."""
    t = math.atan2(x, -(y - yc))  # 0 at the front centre, +-pi at the back
    return u0 + width * (t + math.pi) / (2 * math.pi), v0 + (z_top - z) * per_m


def arm_uv(x: float, y: float, z: float, x_cuff: float, axis_y: float, axis_z: float, u0: float, width: float,
           v0: float, per_m: float) -> tuple[float, float]:
    """An arm's UV (the T-pose arm along x): u by the angle round the axis (y = axis_y, z = axis_z), the seam on the
    underside; v = v0 + (x_cuff - |x|) * per_m (up the arm from the cuff)."""
    t = math.atan2(y - axis_y, z - axis_z)  # 0 on top, +-pi underneath
    return u0 + width * (t + math.pi) / (2 * math.pi), v0 + (x_cuff - abs(x)) * per_m


def unwrap(us: list[float], u0: float, width: float) -> list[float]:
    """One face's u values on a cylinder's island [u0, u0 + width]: a face across the seam has some loops near each
    end; those near the low end move up by the width, so the face stays whole (it reaches a little past the island)."""
    if max(us) - min(us) <= width / 2:
        return list(us)
    mid = u0 + width / 2
    return [u + width if u < mid else u for u in us]


def stripe_cover(d0: float, d1: float, period: float, duty: float) -> float:
    """The navy share of the band [d0, d1] (metres from the edge: the collar or a cuff); each period starts with
    white for period * (1 - duty), then navy. The box filter of one texel: no jagged stripe edges."""
    if d1 < d0:
        d0, d1 = d1, d0
    white = period * (1 - duty)

    def navy_upto(d: float) -> float:  # the navy length in [0, d]
        n, r = divmod(d, period)
        return n * period * duty + max(0.0, r - white)

    if d1 - d0 < 1e-12:
        return 1.0 if (d0 % period) >= white else 0.0
    return (navy_upto(d1) - navy_upto(d0)) / (d1 - d0)


def clearance(want: float, hit: float | None, gap: float, floor: float) -> float:
    """The shell's offset at a vertex: want, unless a kept piece (the bib) lies hit m out along its normal; then gap
    inside that piece, but never under floor."""
    if hit is None:
        return want
    return max(floor, min(want, hit - gap))


def taper(z: float, z_hem: float, z_full: float, d_hem: float, d_full: float) -> float:
    """The offset toward the tucked hem: d_full above z_full, d_hem at z_hem, linear between."""
    if z >= z_full:
        return d_full
    if z <= z_hem:
        return d_hem
    return d_hem + (d_full - d_hem) * (z - z_hem) / (z_full - z_hem)


def back_halfwidth(z: float, z_waist: float, z_apex: float, hw_waist: float, hw_apex: float) -> float:
    """The back panel's half width at height z: hw_waist at the waistband narrowing to hw_apex at the apex, where the
    straps meet; 0 above the apex."""
    if z > z_apex:
        return 0.0
    if z <= z_waist:
        return hw_waist
    return hw_waist + (hw_apex - hw_waist) * (z - z_waist) / (z_apex - z_waist)


def keep_face(x: float, y: float, z: float, z_waist: float, bib_hw: float, bib_top: float, back_y: float,
              z_apex: float, back_hw_waist: float, back_hw_apex: float) -> bool:
    """Whether a Meshy garment face (its centre) stays: below the waistband; or on the front (y < 0) inside the bib
    (|x| < bib_hw, z < bib_top); or on the back (y > back_y) inside the back panel's V."""
    if z <= z_waist:
        return True
    if y < 0:
        return abs(x) < bib_hw and z < bib_top
    if y > back_y:
        return abs(x) < back_halfwidth(z, z_waist, z_apex, back_hw_waist, back_hw_apex)
    return False


def strap_x(t: float, ts: list[float], xs: list[float]) -> float:
    """A strap's |x| at angle t round the shoulder axis: piecewise linear through (ts[i], xs[i]), held at the ends."""
    if t <= ts[0]:
        return xs[0]
    for (a, xa), (b, xb) in zip(zip(ts, xs), zip(ts[1:], xs[1:])):
        if t <= b:
            return xa + (xb - xa) * (t - a) / (b - a) if b > a else xb
    return xs[-1]


def plane_side(p: tuple[float, float, float], co: tuple[float, float, float], no: tuple[float, float, float]) -> float:
    """The signed distance of p from the plane through co with the unit normal no."""
    return sum((a - b) * n for a, b, n in zip(p, co, no))


def neck_plane(y_front: float, z_front: float, y_back: float, z_back: float) -> tuple[tuple[float, float, float],
                                                                                       tuple[float, float, float]]:
    """The crew neck's cut: the plane through the collar's front (y_front, z_front) and back (y_back, z_back) points,
    level across x; returns (a point, the unit normal pointing up, out of the top)."""
    dy, dz = y_back - y_front, z_back - z_front
    n = math.hypot(dy, dz)
    return (0.0, y_front, z_front), (0.0, -dz / n, dy / n)


def lat_us(n: int, lip_share: float) -> list[float]:
    """The u fraction (0..1) of each of a strap's n lats (lip, flat..., lip): the two lips get lip_share each, the
    flat top the rest, evenly."""
    if n < 4:
        raise ValueError("a strap needs two lips and two flat edges")
    flat = [lip_share + (1 - 2 * lip_share) * i / (n - 3) for i in range(n - 2)]
    return [0.0] + flat + [1.0]


def stitch_mask(w: int, h: int, cols: list[float], dash: int, gap: int) -> list[list[bool]]:
    """The stitch lines of a w x h patch (row-major, h rows): at each fraction in cols one texel column, dashed along
    the rows (dash on, gap off)."""
    xs = {min(w - 1, max(0, int(round(c * (w - 1))))) for c in cols}
    return [[(x in xs) and (r % (dash + gap) < dash) for x in range(w)] for r in range(h)]


def seam_wrap_cols(lo: int, c0: int, c1: int, hi: int) -> list[tuple[int, int]]:
    """A periodic island's margin texels from the other side of its seam: (destination, source) columns for the
    columns lo..c0-1 left of the island [c0, c1) and c1..hi-1 right of it."""
    span = c1 - c0
    return [(c, c + span) for c in range(lo, c0)] + [(c, c - span) for c in range(c1, hi)]


def _frame_add(c, t, s, n, a, b, h):
    return tuple(c[k] + s[k] * a + t[k] * b + n[k] * h for k in range(3))


def chamfer_loop(a: float, b: float, ch: float) -> list[tuple[float, float]]:
    """The 8 corners of an a x b half-size rectangle (a across, b along) with its corners cut by ch, counter-clockwise
    from the +a side."""
    return [(a, -b + ch), (a, b - ch), (a - ch, b), (-a + ch, b), (-a, b - ch), (-a, -b + ch), (-a + ch, -b),
            (a - ch, -b)]


def buckle_ring(c, t, s, n, half_w: float, half_l: float, bar: float, z0: float, z1: float, ch: float):
    """A rectangular ring (the slider of a strap's buckle) centred on c in the frame t (along the strap), s (across),
    n (out): outer half sizes half_w x half_l, the bar's width, from height z0 to z1 above c. Returns (vertices, quads):
    four loops of 8 (outer low, outer high, inner high, inner low), closed into a ring of 32 quads."""
    loops = [(half_w, half_l, z0), (half_w, half_l, z1), (half_w - bar, half_l - bar, z1), (half_w - bar, half_l - bar, z0)]
    verts = []
    for a, b, z in loops:
        chi = max(0.0, ch - (bar if a < half_w else 0.0) * 0.5)
        verts += [_frame_add(c, t, s, n, x, y, z) for x, y in chamfer_loop(a, b, chi)]
    quads = []
    for li in range(4):
        lj = (li + 1) % 4
        for k in range(8):
            k2 = (k + 1) % 8
            quads.append([li * 8 + k, li * 8 + k2, lj * 8 + k2, lj * 8 + k])
    return verts, quads


def button(c, t, s, n, r: float, z0: float, z1: float, dome: float, seg: int):
    """A domed button on c in the frame (t, s, n): a ring of seg at z0 (radius r), one at z1 (0.85 r) and the dome's
    top at z1 + dome. Returns (vertices, faces): seg side quads and seg top triangles, open underneath."""
    verts = []
    for rr, z in ((r, z0), (0.85 * r, z1)):
        for i in range(seg):
            ang = 2 * math.pi * i / seg
            verts.append(_frame_add(c, t, s, n, rr * math.cos(ang), rr * math.sin(ang), z))
    verts.append(_frame_add(c, t, s, n, 0.0, 0.0, z1 + dome))
    faces = [[i, (i + 1) % seg, seg + (i + 1) % seg, seg + i] for i in range(seg)]
    faces += [[seg + i, seg + (i + 1) % seg, 2 * seg] for i in range(seg)]
    return verts, faces


# the cloth's real openings (C1h): per piece the joints it opens at; the garment takes the top's when no top is made
OPENINGS = {"top": ("Neck", "LeftHand", "RightHand"), "garment": ("LeftFoot", "RightFoot"),
            "shoes": ("LeftFoot", "RightFoot")}
OPENING_REACH = {"Neck": 0.15, "LeftHand": 0.15, "RightHand": 0.15, "LeftFoot": 0.3, "RightFoot": 0.3}


def edge_loops(edges: list[tuple[int, int]]) -> list[list[int]]:
    """The connected runs of a mesh's boundary edges (vertex index pairs), each its sorted vertex indices; longest
    run first."""
    parent: dict[int, int] = {}

    def root(a: int) -> int:
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in edges:
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[ra] = rb
    runs: dict[int, list[int]] = {}
    for v in parent:
        runs.setdefault(root(v), []).append(v)
    return sorted((sorted(r) for r in runs.values()), key=lambda r: (-len(r), r[0]))


def pick_openings(loops: list[tuple[tuple[float, float, float], float]], joint: tuple[float, float, float],
                  reach: float, share: float = 0.5) -> list[int]:
    """The indexes of the boundary loops (centre, length in m) that are a piece's opening at a joint (the collar at
    the neck, a cuff at the wrist, a hem or a shoe's top at the ankle): the centre within reach of the joint and the
    length at least share of the longest such loop's, so a small hole beside it (a hidden-face hole, a button's
    bottom) is no opening."""
    near = [i for i, (c, _ln) in enumerate(loops) if math.dist(c, joint) <= reach]
    if not near:
        return []
    most = max(loops[i][1] for i in near)
    return [i for i in near if loops[i][1] >= share * most]


def follow_row(own: dict[str, float], panel: dict[str, float], share: float, n: int = 4) -> dict[str, float]:
    """A top vertex's weights under a panel (C1h): its own (the body's) blended toward the panel's at its nearest
    point by share (0: its own, 1: the panel's), the n largest kept and normalised, so the top moves with the bib,
    the back panel and the trousers' waist and stays under them in every clip."""
    share = min(1.0, max(0.0, share))
    row = {b: (1 - share) * own.get(b, 0.0) + share * panel.get(b, 0.0) for b in set(own) | set(panel)}
    best = sorted(((w, b) for b, w in row.items() if w > 1e-4), reverse=True)[:n]
    tot = sum(w for w, _ in best)
    return {b: w / tot for w, b in best} if tot > 0 else dict(own)


def in_waist_band(x: float, y: float, z: float, z_waist: float, height: float, bib_hw: float, back_y: float,
                  back_hw: float) -> bool:
    """Whether a Meshy garment face (its centre) lies in the band the built waistband replaces (C1i): from height
    below the waistband line up to it, outside the bib (front, y < 0, |x| < bib_hw) and the back panel (y > back_y,
    |x| < back_hw, its half width at the waistband)."""
    if not z_waist - height < z <= z_waist:
        return False
    if y < 0:
        return abs(x) >= bib_hw
    if y > back_y:
        return abs(x) >= back_hw
    return True


def under_offset(d: float, share: float, under: float) -> float:
    """The top's offset under a panel (C1i): d (its own clearance) pulled in toward under by share, the share of the
    five rays that meet the panel (0: d; 1: under), never pushed out."""
    share = min(1.0, max(0.0, share))
    return min(d, d - share * (d - under))


def band_lats(height: float, lip: float, ledge: float, n_flat: int) -> list[tuple[float, float]]:
    """The waistband strip's lats from its lower edge up (C1i): (height above the lower edge, offset change toward
    the body). The lower lip folds lip toward the body (it rests on the trousers), n_flat flat rows span the height,
    and the upper edge rolls in by ledge (down to the tucked top), so neither edge shows a gap."""
    if n_flat < 2:
        raise ValueError("a waistband needs two flat rows at least")
    flat = [(height * i / (n_flat - 1), 0.0) for i in range(n_flat)]
    return [(0.0, -lip)] + flat + [(height, -ledge)]


def band_offset(frac: float, low: float, high: float) -> float:
    """The waistband's offset off the body at frac of its height (0: the lower edge, low: the trousers' own
    clearance; 1: the upper edge, high, cinched toward the top), linear between."""
    frac = min(1.0, max(0.0, frac))
    return low + (high - low) * frac


def blend_rows(rows: list[tuple[dict[str, float], float]], n: int = 4) -> dict[str, float]:
    """Weights from nearby vertices (the trousers' under the waistband, C1i): each row (weights, distance) counts by
    1 / distance; the n largest kept and normalised."""
    acc: dict[str, float] = {}
    for w, d in rows:
        k = 1.0 / max(d, 1e-4)
        for b, x in w.items():
            acc[b] = acc.get(b, 0.0) + k * x
    best = sorted(((x, b) for b, x in acc.items() if x > 1e-6), reverse=True)[:n]
    tot = sum(x for x, _ in best)
    return {b: x / tot for x, b in best} if tot > 0 else {}


def inward_flap(x: float, y: float, z: float, nx: float, ny: float, z_lo: float, z_hi: float, axis_y: float,
                bib_hw: float, back_y: float, back_hw: float, edge: float, dot: float = -0.2) -> bool:
    """Whether a Meshy garment face (centre, normal's x and y) is one of the panels' edge flaps turned toward the
    body (C1i: the layered side opening's dark shards beside the waistband): between z_lo and z_hi, within edge of
    the bib's side edge (front) or the back panel's (back_hw, its half width at z), its normal pointing in (its
    horizontal part against the direction out from the waist's centre by more than -dot)."""
    if not z_lo < z < z_hi:
        return False
    if y < 0:
        near = abs(x) > bib_hw - edge
    elif y > back_y:
        near = abs(x) > back_hw - edge
    else:
        near = True
    if not near:
        return False
    ox, oy = x, y - axis_y
    ln = (ox * ox + oy * oy) ** 0.5
    return ln > 1e-9 and (nx * ox + ny * oy) / ln < dot


def min_altitude(edges: list[float], area: float) -> float:
    """A face's thinness (C1j): twice its area over its longest edge (a triangle's least altitude; a quad's width
    across its longest edge, about); 0 for a degenerate face."""
    longest = max(edges) if edges else 0.0
    if longest <= 0:
        return 0.0
    return (2.0 if len(edges) == 3 else 1.0) * area / longest


def track_face_ok(edges: list[float], area: float, nbr_dots: list[float], min_alt: float = 0.0015,
                  fold: float = 0.0) -> bool:
    """Whether a garment face can carry a tracked top vertex's panel point (C1j): neither a sliver (its least
    altitude under min_alt: its plane swings when it bends) nor folded back (the mean of its neighbours' normals
    against its own, nbr_dots, under fold: a face wound against the cloth round it)."""
    if min_altitude(edges, area) < min_alt:
        return False
    return not nbr_dots or sum(nbr_dots) / len(nbr_dots) >= fold


def near_panel_edge(x: float, y: float, z: float, z_lo: float, z_hi: float, bib_hw: float, back_y: float,
                    back_hw: float, edge: float) -> bool:
    """Whether a garment face (its centre) lies along the bib's or the back panel's side edge (C1j): between z_lo
    and z_hi, within edge of the bib's half width (front, y < 0) or of the back panel's (y > back_y; back_hw its
    half width at z), on either side of the cut; the side between them is left alone (r27: peeling there opened the
    waist at the hip)."""
    if not z_lo < z < z_hi:
        return False
    if y < 0:
        return abs(abs(x) - bib_hw) < edge
    if y > back_y:
        return abs(abs(x) - back_hw) < edge
    return False


def edge_defect(on_boundary: bool, out_dot: float, min_alt: float, area: float, fold_dot: float,
                inward: float = 0.0, thin: float = 0.001, tiny: float = 2e-6, fold: float = 0.0) -> bool:
    """Whether a garment face on a panel's open edge is a wedge, flap or sliver to peel off (C1j): only faces with
    an open edge (so peeling opens no hole inside the cloth), turned toward the body (their normal's horizontal part
    against the way out, out_dot, under inward), thinner than thin, smaller than tiny (m^2) or folded back against
    their neighbours (fold_dot, the mean of their normals against its own, under fold)."""
    if not on_boundary:
        return False
    return out_dot < inward or min_alt < thin or area < tiny or fold_dot < fold


def cleared(sides: list[float], picked: list[bool], outer: bool | None, eps: float = 1e-6) -> list[bool]:
    """Which faces a plane cut clears (C1k), by the signed distances of their centres from the plane after the cut
    (sides): of the picked faces, those on its positive side (outer True), on its negative side (False) or none
    (None). bisect_plane's own clear kills vertices, and with each every face round it, picked or not (the second
    review's major: the trousers' faces under the waist line beside the panels); this deletes only the faces meant."""
    if outer is None:
        return [False] * len(sides)
    return [bool(p) and (s > eps if outer else s < -eps) for s, p in zip(sides, picked)]


def flood(seeds: list[int], nbrs: list[list[int]], allowed: set[int]) -> set[int]:
    """The allowed faces reached from seeds through neighbours that are allowed too (C1k: the shirt Meshy baked into
    the denim peels only from an open edge inward, never as a hole inside the bib)."""
    got = {s for s in seeds if s in allowed}
    stack = list(got)
    while stack:
        f = stack.pop()
        for g in nbrs[f]:
            if g in allowed and g not in got:
                got.add(g)
                stack.append(g)
    return got


def opening_dist(d: float | None) -> float:
    """A KD-tree find's distance to the nearest opening point; infinite when it found none (C1k: a tree of no
    opening points finds (None, None, None))."""
    return math.inf if d is None else d


def band_end(off: float, hit: float | None, gap: float = 0.002, floor: float = 0.0005) -> tuple[float, bool]:
    """A waistband end's offset from the body where it runs under a Meshy panel whose face is hit m out along the
    body normal (C1k): at least gap inside that face, never under floor; and whether the panel lies so near the body
    that even floor leaves the band on or outside it."""
    if hit is None:
        return off, False
    cap = hit - gap
    return max(floor, min(off, cap)), cap < floor


def shirt_texel(r: float, g: float, b: float, lum: float = 0.55, sat: float = 0.3) -> bool:
    """Whether a garment texel (stored sRGB) is the shirt Meshy baked into the denim (C1j: the white wedges at the
    panels' edges): light (luminance over lum) and grey (saturation under sat), not denim, not orange stitching."""
    hi, lo = max(r, g, b), min(r, g, b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > lum and hi > 0 and (hi - lo) / hi < sat


# E1b: the planes' defaults (clothes_dress's flags) were set on the old body A, whose bones these are (A11 keeps them)
REF_CHEST_Z, REF_NECK_Z = 1.028, 1.339
REF_UPPER_ARM = (0.152, 0.065, 1.277)
REF_NECK_Y = 0.041


def body_planes(chest_z: float, neck_z: float, neck_y: float, upper_arm: tuple[float, float, float], hand_x: float,
                cuff_back: float = 0.035, waist: float = 1.0, bib: tuple[float, float] = (0.105, 1.166),
                back: tuple[float, float, float, float] = (0.03, 1.12, 0.12, 0.03),
                neck: tuple[float, float, float, float] = (-0.06, 1.335, 0.09, 1.365), seam_x: float = 0.165,
                arm_z: float = 1.18, waist_z: float | None = None) -> dict:
    """The top's and the garment's cut planes from a body's own bones (E1b, art #196): heights mapped linearly from
    the reference torso (Chest to Neck) to this body's, the sleeves' seam moved with the upper arm's root, the arms'
    axis through the upper arm's head, and the cuffs cuff_back m in from the hand bone's head (the wrist), so the
    sleeve never reaches the hand or the thumb's root. The reference body gets the defaults back but the cuff.
    waist_z (M2c): the waist plane at this height instead (a garment whose own band sits lower than the bones' waist,
    the m2 dungarees on B13: their band's edge, so no shirt texels stay over it)."""
    if neck_z <= chest_z:
        raise ValueError(f"neck {neck_z} not above chest {chest_z}")
    k = (neck_z - chest_z) / (REF_NECK_Z - REF_CHEST_Z)
    zm = lambda z: chest_z + (z - REF_CHEST_Z) * k
    dy = neck_y - REF_NECK_Y
    return {"cuff_x": hand_x - cuff_back, "seam_x": seam_x + upper_arm[0] - REF_UPPER_ARM[0], "arm_z": zm(arm_z),
            "arm_axis": (upper_arm[1], upper_arm[2]), "waist": zm(waist) if waist_z is None else waist_z,
            "bib": (bib[0], zm(bib[1])),
            "back": (back[0], zm(back[1]), back[2], back[3]),
            "neck": (neck[0] + dy, zm(neck[1]), neck[2] + dy, zm(neck[3])), "z_scale": k}


def mirror_tile(i: int, n: int) -> tuple[int, bool]:
    """E1h: texel i of a strip that repeats an n-texel source mirrored every other time (no seam where two copies
    meet): the source texel and whether this copy is mirrored."""
    k, r = divmod(i, n)
    return (n - 1 - r, True) if k % 2 else (r, False)


def cyl_coords(x: float, y: float, z: float, axis_y: float, a_ref: float, radius: float) -> tuple[float, float]:
    """E1h: a point's place on a vertical cylinder round the body's axis (x = 0, y = axis_y; the front at -y): the arc
    length (m) at `radius` from the angle a_ref (wrapped to within half a turn of it), and the height."""
    a = math.atan2(x, -(y - axis_y)) - a_ref
    a = (a + math.pi) % (2 * math.pi) - math.pi
    return radius * a, z


def in_box(x: float, y: float, z: float, box: tuple[float, float, float, float, float, float]) -> bool:
    """E1h: a point inside a box (x0, x1, y0, y1, z0, z1), mirrored in x (the box is given for |x|)."""
    x0, x1, y0, y1, z0, z1 = box
    return x0 <= abs(x) <= x1 and y0 <= y <= y1 and z0 <= z <= z1


def front_hull(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """The taut line a stiff panel takes over a side profile (E1i, her flat bib): pts are (z, y) with the front at
    the smaller y; the result is the profile's front hull, (z, y) from the lowest z to the highest, every point of
    pts on it or behind it (y no smaller than the hull's at its z)."""
    hull: list[tuple[float, float]] = []
    for z, y in sorted(pts):
        if hull and abs(z - hull[-1][0]) < 1e-12:
            continue  # sorted by (z, y): the first point at a height already has its smallest y
        while len(hull) >= 2:
            (z1, y1), (z2, y2) = hull[-2], hull[-1]
            if (y2 - y1) * (z - z1) >= (y - y1) * (z2 - z1):  # hull[-1] on or behind the chord: not taut
                hull.pop()
            else:
                break
        hull.append((z, y))
    return hull


def hull_at(hull: list[tuple[float, float]], z: float) -> float:
    """The hull's y at z, linear between its points, clamped to its ends."""
    if z <= hull[0][0]:
        return hull[0][1]
    for (z1, y1), (z2, y2) in zip(hull, hull[1:]):
        if z <= z2:
            return y1 + (y2 - y1) * (z - z1) / (z2 - z1)
    return hull[-1][1]


def ease(z: float, z0: float, span: float) -> float:
    """0 at z0 and below, 1 from z0 + span on, smoothstep between (E1i: the flat bib eased in over the waist)."""
    if span <= 0:
        return 1.0 if z > z0 else 0.0
    t = min(1.0, max(0.0, (z - z0) / span))
    return t * t * (3 - 2 * t)


def chain_row(z: float, knots: list[tuple[float, str]]) -> dict[str, float]:
    """A stiff panel's weights by height alone (E1i2, her flat bib): knots are (height, bone) up the spine (each bone's
    mid height in the bind pose, e.g. Hips, Spine, Chest, UpperChest); at z the two knots round it share the weight,
    smoothstep between them, so the panel bends only where the spine does and the same across its width. Below the
    lowest knot all goes to its bone, above the highest to its."""
    ks = sorted(knots)
    if not ks:
        return {}
    if z <= ks[0][0]:
        return {ks[0][1]: 1.0}
    for (z1, b1), (z2, b2) in zip(ks, ks[1:]):
        if z <= z2:
            t = ease(z, z1, z2 - z1)
            row: dict[str, float] = {}
            for b, w in ((b1, 1.0 - t), (b2, t)):
                if w > 1e-6:
                    row[b] = row.get(b, 0.0) + w
            return row
    return {ks[-1][1]: 1.0}


def panel_fit(nbrs: list[tuple[float, float, float]]) -> float:
    """M2d, the flat back panel: a panel point's smoothed depth from its neighbours (dx, dz, y), dx and dz their
    offsets from it: the least-squares y = a + b dx + c dx^2 + d dz, so a's the depth with the panel's round across
    and its slope up kept, and a fold narrower than the window gone. Too few or degenerate neighbours: their mean."""
    if not nbrs:
        raise ValueError("no neighbours")
    mean = sum(y for _x, _z, y in nbrs) / len(nbrs)
    if len(nbrs) < 6:
        return mean
    m = [[0.0] * 5 for _ in range(4)]
    for dx, dz, y in nbrs:
        r = (1.0, dx, dx * dx, dz)
        for i in range(4):
            for j in range(4):
                m[i][j] += r[i] * r[j]
            m[i][4] += r[i] * y
    for c in range(4):  # Gaussian elimination with partial pivoting
        piv = max(range(c, 4), key=lambda i: abs(m[i][c]))
        if abs(m[piv][c]) < 1e-14:
            return mean
        m[c], m[piv] = m[piv], m[c]
        for i in range(c + 1, 4):
            f = m[i][c] / m[c][c]
            for j in range(c, 5):
                m[i][j] -= f * m[c][j]
    sol = [0.0] * 4
    for i in range(3, -1, -1):
        sol[i] = (m[i][4] - sum(m[i][j] * sol[j] for j in range(i + 1, 4))) / m[i][i]
    return sol[0]


def join_rows(hits: list[float | None], along: list[float], blend: float) -> list[tuple[float, int | None]]:
    """M2e: the straps' back ends glued onto the back panel. hits: per strap row (front to back) the move along its
    normal that lays it on the panel (None: no panel under it); along: the rows' arc lengths. Returns per row
    (share, source row): a row over the panel takes its own move fully (share 1, itself); a row in front of the
    glued run takes the run's first row's move and weights eased out over blend m along the strap (smoothstep); the
    rest none (0, None). Only the run joined to the back end counts (a stray hit up the strap does not)."""
    n = len(hits)
    first = n
    while first > 0 and hits[first - 1] is not None:
        first -= 1
    out: list[tuple[float, int | None]] = [(0.0, None)] * n
    if first == n:
        return out
    for i in range(first, n):
        out[i] = (1.0, i)
    for i in range(first - 1, -1, -1):
        d = along[first] - along[i]
        if blend <= 0 or d >= blend:
            break
        t = d / blend
        out[i] = (1.0 - t * t * (3 - 2 * t), first)
    return out
