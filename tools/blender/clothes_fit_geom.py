"""The clothes fit's pure maths (art #196, clothes step 2, C1; no bpy, unittest-tested in tools/tests): the arm and
leg swings that bring the T-posed body into the cloth's drawn pose, the cloth's new distance from the body (a small
even offset, the looseness kept in part, never through the body), smoothing a field over the cloth's edges (the fit's
displacements, the skin weights where the cloth bridges), limiting weights to four bones, undoing linear blend
skinning (the fitted cloth, posed like the body, back into the body's rest pose), the body faces the cloth covers,
and a clip's poke-through numbers. clothes_fit.py, clothes_dress.py and clothes_proof.py import it.

Matrices are 3x4 row lists [[r00, r01, r02, t0], ...] (an affine map), points 3-tuples.
"""
from __future__ import annotations

import math

Vec = tuple[float, float, float]
Mat = list[list[float]]


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec, b: Vec) -> Vec:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def unit(a: Vec) -> Vec:
    n = math.sqrt(dot(a, a))
    if n == 0.0:
        raise ValueError("zero vector")
    return a[0] / n, a[1] / n, a[2] / n


def swing(a: Vec, b: Vec) -> tuple[Vec, float]:
    """(axis, angle in radians) of the shortest rotation taking direction a onto direction b; axis (0, 0, 1) and 0
    for parallel directions (opposite ones are refused: no shortest rotation)."""
    a, b = unit(a), unit(b)
    c = max(-1.0, min(1.0, dot(a, b)))
    ax = cross(a, b)
    n = math.sqrt(dot(ax, ax))
    if n < 1e-12:
        if c < 0:
            raise ValueError("opposite directions")
        return (0.0, 0.0, 1.0), 0.0
    return (ax[0] / n, ax[1] / n, ax[2] / n), math.atan2(n, c)


def fit_distance(s: float, offset: float, keep: float, floor: float) -> float:
    """The cloth vertex's new signed distance from the body (s: its distance along the body's normal, negative
    inside): beyond offset, offset plus keep times the looseness, so a loose garment comes in but stays a little
    loose; between floor and offset it stays; below floor (too close, or inside the body) it goes out to floor."""
    if not 0.0 <= keep <= 1.0 or floor > offset:
        raise ValueError("keep must be in [0, 1] and floor <= offset")
    if s > offset:
        return offset + keep * (s - offset)
    return max(floor, s)


def smooth(values: list[list[float]], nbrs: list[list[int]], iters: int, alpha: float,
           mask: list[float] | None = None) -> list[list[float]]:
    """Laplacian smoothing of a per-vertex field (each value a list of floats) over the mesh's edges: each round a
    vertex moves alpha times its mask (1 when no mask) toward its neighbours' mean. A vertex with no neighbour keeps
    its value."""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be in [0, 1]")
    cur = [list(v) for v in values]
    for _ in range(iters):
        nxt = []
        for i, v in enumerate(cur):
            nb = nbrs[i]
            a = alpha * (mask[i] if mask is not None else 1.0)
            if not nb or a == 0.0:
                nxt.append(v)
                continue
            mean = [sum(cur[j][k] for j in nb) / len(nb) for k in range(len(v))]
            nxt.append([x + a * (m - x) for x, m in zip(v, mean)])
        cur = nxt
    return cur


def limit(row: dict[str, float], n: int = 4, floor: float = 1e-3) -> dict[str, float]:
    """The n largest weights of a vertex above floor, normalised to sum 1 ({} when none is left)."""
    top = sorted(((w, b) for b, w in row.items() if w > floor), reverse=True)[:n]
    tot = sum(w for w, _ in top)
    return {b: w / tot for w, b in top} if tot > 0 else {}


def mix_rows(own: dict[str, float], other: dict[str, float], share: float, n: int = 4) -> dict[str, float]:
    """E1e: a vertex's weights blended toward another's (the ankle skin under the collar takes its nearest shoe
    vertex's, so the two move as one): share of other plus (1 - share) of own, limited to n and normalised."""
    if not 0.0 <= share <= 1.0:
        raise ValueError(f"share {share} must lie in [0, 1]")
    names = set(own) | set(other)
    return limit({b: (1.0 - share) * own.get(b, 0.0) + share * other.get(b, 0.0) for b in names}, n)


def blend_rows(rows: list[dict[str, float]], ws: list[float], n: int = 4) -> dict[str, float]:
    """M2d: several vertices' weights mixed by ws (a garment face's corners by their nearness to a point), limited to
    n and normalised ({} when ws sum to nothing)."""
    if len(rows) != len(ws):
        raise ValueError("one weight per row")
    tot = sum(ws)
    if tot <= 0:
        return {}
    out: dict[str, float] = {}
    for row, w in zip(rows, ws):
        for b, x in row.items():
            out[b] = out.get(b, 0.0) + x * w / tot
    return limit(out, n)


def follow_share(open_dist: float, lo: float, hi: float) -> float:
    """M2d: how much a kept skin vertex under the garment takes the garment's weights and is pulled inside it: none
    within lo m of an opening (the skin there shows and keeps its own motion), all from hi m on, smooth between."""
    if hi <= lo:
        raise ValueError(f"hi {hi} must exceed lo {lo}")
    t = min(1.0, max(0.0, (open_dist - lo) / (hi - lo)))
    return t * t * (3.0 - 2.0 * t)


def pull_in(side: float, clear: float, share: float, most: float = 0.015) -> float:
    """M2d: how far (m) a skin vertex at side m of its nearest garment face (+: outside, poking through) moves in
    along that face's normal: until clear m inside it, times share; none when it is already that far in or more than
    most m outside (skin that far out is no poke under the cloth but skin beside it)."""
    if side > most:
        return 0.0
    return share * max(0.0, side + clear)


def blend(row: dict[str, float], mats: dict[str, Mat]) -> Mat:
    """Linear blend skinning's per-vertex matrix: the weighted sum of the bones' deform matrices (the weights
    normalised); the identity for a vertex with no weight."""
    if not row:
        return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]]
    tot = sum(row.values())
    out = [[0.0] * 4 for _ in range(3)]
    for b, w in row.items():
        m = mats[b]
        for r in range(3):
            for c in range(4):
                out[r][c] += w / tot * m[r][c]
    return out


def apply(m: Mat, p: Vec) -> Vec:
    return tuple(m[r][0] * p[0] + m[r][1] * p[1] + m[r][2] * p[2] + m[r][3] for r in range(3))


def invert(m: Mat) -> Mat:
    """The inverse of an affine 3x4 map (ValueError when singular)."""
    a = [row[:3] for row in m]
    det = (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
           + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
    if abs(det) < 1e-12:
        raise ValueError("singular matrix")
    inv = [[(a[(c + 1) % 3][(r + 1) % 3] * a[(c + 2) % 3][(r + 2) % 3]
             - a[(c + 1) % 3][(r + 2) % 3] * a[(c + 2) % 3][(r + 1) % 3]) / det for c in range(3)] for r in range(3)]
    t = [row[3] for row in m]
    return [inv[r] + [-(inv[r][0] * t[0] + inv[r][1] * t[1] + inv[r][2] * t[2])] for r in range(3)]


def unskin(p: Vec, row: dict[str, float], mats: dict[str, Mat]) -> Vec:
    """The rest position whose linear blend skinning with row and the bones' deform matrices is the posed p."""
    return apply(invert(blend(row, mats)), p)


def covered_faces(faces: list[list[int]], vert_covered: list[bool], face_nbrs: list[list[int]],
                  erode: int = 1, vert_sure: list[bool] | None = None) -> list[bool]:
    """The body faces to remove under the cloth: a face whose vertices are all covered, then eroded by erode rings
    (a face beside a kept one is kept), so the cut's edge stays under the cloth, never at an opening. vert_sure: the
    vertices hidden for certain (inside a rigid shoe, below its rim): a face whose vertices are all sure goes without
    the erosion, so the cut reaches the rim and no foot skin is left to poke through the shoe's sides."""
    cov = [all(vert_covered[v] for v in f) for f in faces]
    for _ in range(erode):
        cov = [c and all(cov[j] for j in face_nbrs[i]) for i, c in enumerate(cov)]
    if vert_sure is not None:
        cov = [c or all(vert_sure[v] for v in f) for c, f in zip(cov, faces)]
    return cov


def frame_max(per_frame: list[tuple[int, float]]) -> dict[str, float]:
    """A clip's poke-through numbers from its frames' (count of body vertices outside the cloth, the deepest in m):
    the frame maximum of each and the frame where the count peaks."""
    if not per_frame:
        return {"frames": 0, "max_count": 0, "max_depth_m": 0.0, "worst_frame": -1}
    worst = max(range(len(per_frame)), key=lambda i: per_frame[i][0])
    return {"frames": len(per_frame), "max_count": max(c for c, _ in per_frame),
            "max_depth_m": round(max(d for _, d in per_frame), 4), "worst_frame": worst}


def pick_facing(cands: list[tuple[float, Vec, int]], n: Vec, min_dot: float = 0.2) -> int | None:
    """The body face a cloth vertex takes its weights from: among cands (distance, the body face's outward normal,
    the face index) the nearest whose normal faces the same way as the cloth's outward normal n (dot >= min_dot).
    So the inner side of a sleeve takes the arm, not the torso beside it, and an inner trouser leg its own thigh.
    None when no face qualifies (the caller falls back to the plain nearest); a zero normal on either side never
    qualifies."""
    if not -1.0 <= min_dot <= 1.0:
        raise ValueError(f"min_dot {min_dot} outside -1..1")
    if dot(n, n) < 1e-24:  # E1: a cloth vertex without a normal picks nothing (the plain nearest)
        return None
    best = None
    for d, nor, fi in cands:
        if dot(nor, nor) < 1e-24:  # E1: a degenerate body face (D3's A11 has some) has no direction to agree with
            continue
        if dot(unit(nor), unit(n)) >= min_dot and (best is None or d < best[0]):
            best = (d, fi)
    return None if best is None else best[1]


def rigid(row: dict[str, float], bones: tuple[str, ...], default: str) -> dict[str, float]:
    """A row of skin weights kept to bones only and summed to 1 (a shoe on its Foot and Toes, nothing of the shin);
    {default: 1} when row has none of them."""
    if default not in bones:
        raise ValueError(f"default {default} not in {bones}")
    kept = {b: w for b, w in row.items() if b in bones and w > 0}
    total = sum(kept.values())
    return {b: w / total for b, w in kept.items()} if total > 0 else {default: 1.0}


def hug_weight(front_diff: float, start: float = 0.003, full: float = 0.010) -> float:
    """How much a cloth vertex hugs the female body (0..1) from the forward part of the body's base-to-female
    difference at its nearest body point (m): 0 up to start, 1 from full, smooth between. The bib and the top
    follow the chest the female shape adds; the rest of the cloth keeps its fit."""
    if full <= start:
        raise ValueError(f"full {full} must exceed start {start}")
    t = min(1.0, max(0.0, (front_diff - start) / (full - start)))
    return t * t * (3.0 - 2.0 * t)


def shoe_top(boundary_z: list[float], margin: float = 0.01, above: float = 0.05) -> float | None:
    """The height under which a closed shoe hides the foot: the lowest point of the shoe's top opening (its boundary
    vertices above `above` m, so a sole's open edge is no top) less margin; None when the shoe has no such opening."""
    if margin < 0:
        raise ValueError(f"margin {margin} is negative")
    tops = [z for z in boundary_z if z > above]
    return min(tops) - margin if tops else None


def local_rim(rim_z: list[float], margin: float = 0.004) -> float | None:
    """The height under which a shoe hides a foot vertex where it stands: the lowest of the shoe opening's boundary
    points close above it (rim_z, those within a few cm across the floor) less margin; None when the opening is not
    above it (the toe box, the heel's back). The opening dips low on a shoe's sides and rises at the heel and the
    tongue, so one height for the whole shoe (shoe_top, the lowest point) leaves the foot by the heel and the tongue
    to poke through the shoe's sides."""
    if margin < 0:
        raise ValueError(f"margin {margin} is negative")
    return min(rim_z) - margin if rim_z else None


def through_shoe(s: float, rim_dist: float, tol: float = 0.001, most: float = 0.03, rim: float = 0.01) -> bool:
    """A foot vertex through a shoe's wall: outside the shoe by more than tol and at most most (s, the signed
    distance from the nearest shoe face, + out), with that nearest shoe point farther than rim from the opening's
    rim (rim_dist), where the ankle above the rim is meant to show. The shoe is rigid on the foot, so such a vertex
    is the foot's side bulging through a shoe narrower than it, the teal on the shoes' outer sides (r12)."""
    return tol < s <= most and rim_dist > rim


UNCUT_BONES = ("Neck", "Head", "Hand", "Eye")


def under_cloth(s: float, edge_dist: float, bone: str, deep: float = 0.001, away: float = 0.08,
                away_shoulder: float | None = None) -> bool:
    """A body vertex hidden under the cloth for certain: inside it at rest by more than deep (s, the signed distance
    from the nearest cloth face within the proof's reach, + out) and farther than away (m) from every opening
    (edge_dist), on no bone that leaves the cloth through an opening (the neck, the hands: UNCUT_BONES, by suffix).
    The rays' cover test keeps some of these (the upper back between the straps, the crotch), and a clip then moves
    them out through the cloth (r12: 48 vertices up to 52 mm in a crouch); cut, the cloth shows instead.
    away_shoulder, when given, is the limit on a Shoulder bone: the skin under a strap's base lies within 8 cm of the
    collar, and the clips moved it out beside the strap (r16: the collar fleck, up to 58 mm in Jump_Start)."""
    limit = away_shoulder if away_shoulder is not None and bone.endswith("Shoulder") else away
    return s < -deep and edge_dist > limit and not bone.endswith(UNCUT_BONES)


def shoe_face(through: list[bool], low_foot: list[bool]) -> bool:
    """A body face cut from a shoe: one of its vertices through the shoe's wall (through_shoe) and every one on the
    foot below the rim's high point where it stands, or cut already (low_foot). The face of a foot vertex through
    the wall also holds vertices inside the shoe that no rule cuts, and the shoe's coarse faces show it as a teal
    triangle on the shoe's side (r12 to r15)."""
    if len(through) != len(low_foot):
        raise ValueError("through and low_foot differ in length")
    return any(through) and all(low_foot)


def in_shoe(foot_weight: float, z: float, top: float | None, min_weight: float = 0.5, under: bool = False,
            toes_weight: float = 0.0, shoe: bool | None = None, rim: float | None = None) -> bool:
    """A body vertex inside a shoe: mostly on Foot and Toes (foot_weight, the sum of their weights) and below the
    shoe's top (shoe_top), or under the shoe (under: a ray straight up hits it, the toes under the toe box, while
    the ankle seen through the opening has none), or mostly on Toes (toes_weight): a closed shoe's toe box always
    hides the toes, also where they bulge through its coarse faces, or below the opening's rim where it stands
    (rim, local_rim). shoe: whether the build has shoes at all (None: told by top). Such a vertex is always cut from
    the dressed build."""
    if shoe is None:
        shoe = top is not None
    if not shoe or foot_weight < min_weight:
        return False
    return (under or toes_weight >= min_weight or (top is not None and z < top)
            or (rim is not None and z < rim))


def rest_poke(signed_mm: list[float], at_opening: list[bool], tol_mm: float = 1.0) -> int:
    """The body vertices already through the cloth at rest: outside it by more than tol (signed distance, + out)
    and not by an opening (collar, cuffs, hems, the shoes' tops), where the body is meant to show."""
    if len(signed_mm) != len(at_opening):
        raise ValueError("signed_mm and at_opening differ in length")
    return sum(1 for s, o in zip(signed_mm, at_opening) if s > tol_mm and not o)


def exposed_skin(depth: float, cloth_z: float, cloth_nz: float, above_z: float, deep: float = 0.02,
                 up: float = 0.3) -> bool:
    """A watched body vertex outside the cloth that is exposed skin, not poke-through: more than deep (m) outside,
    its nearest cloth point (height cloth_z) above above_z (the top of the chest, the UpperChest bone's head in that
    frame), and that cloth face turned up (the z of its normal, cloth_nz, at least up): the neck over the collar's
    thick roll, whose nearest cloth point lies too far from the collar's boundary loop for the opening rule. A real
    crossing is never that deep, and the upper back's or the crotch's cloth faces sideways or lies lower (r13: the
    neck 36 to 79 mm over a collar face of normal z 0.36 to 0.83)."""
    if deep < 0:
        raise ValueError(f"deep {deep} is negative")
    return depth > deep and cloth_z > above_z and cloth_nz >= up


def long_edges(lengths: list[float], max_len: float) -> list[int]:
    """The edges to split before the fit (their indices): longer than max_len (m). A coarse sleeve's flat faces cut a
    chord through the arm's curve, and the arm shows through between its vertices; split to max_len, the chord's sag
    on a 5.5 cm arm stays under 4 mm, inside the sleeve's clearance."""
    if max_len <= 0:
        raise ValueError(f"max_len {max_len} must be positive")
    return [i for i, x in enumerate(lengths) if x > max_len]


def first_exit(hits: list[tuple[float, float]]) -> int | None:
    """The hits of a ray from a point inside the body, in order along it, as (distance, the hit face's normal dotted
    with the ray): the index of the first where the ray leaves the body (the face faces along the ray), or None."""
    for k, (_t, dot) in enumerate(hits):
        if dot > 0:
            return k
    return None


def deep_exit(depth: float, travel: float, slack: float = 0.03, most: float = 0.05) -> bool:
    """Whether a cloth point inside a limb takes the way out along its own normal (travel, m) instead of the plain
    push to its nearest face (depth, m, that face on the far side): a point past the limb's middle is nearer the far
    side, and its way out the near side is at most twice that plus a slack; a longer way crosses the limb."""
    return travel <= min(most, 2.0 * depth + slack)


def boundary_verts(faces: list[list[int]]) -> set[int]:
    """The vertices on the mesh's open edges (an edge used by one face only): the openings' rims."""
    count: dict[tuple[int, int], int] = {}
    for f in faces:
        for k in range(len(f)):
            e = tuple(sorted((f[k], f[(k + 1) % len(f)])))
            count[e] = count.get(e, 0) + 1
    return {v for e, n in count.items() if n == 1 for v in e}


def ankle_kept(z: float, rim_z: float | None, rim_xy: float, keep: float = 0.04, reach: float = 0.06) -> bool:
    """E1b, the shoe collar's shards: an ankle vertex (any Foot, Toes or LowerLeg weight) between the shoe opening's
    nearest rim point across the floor (rim_z, rim_xy m away) and keep m above it is open skin between the shoe and
    the trousers' hem, never cut by the cover rays (their tilted rays meet the hem above and the shoe below, and cut
    holes into the ankle over the collar); None or a rim farther than reach: not by a shoe."""
    if keep <= 0 or rim_z is None or rim_xy > reach:
        return False
    return rim_z <= z < rim_z + keep


def ankle_ride(z: float, rim_z: float, below: float = 0.005, band: float = 0.03) -> float:
    """E1b: the share of an ankle vertex's LowerLeg weight that goes to its Foot, so the skin under the shoe's collar
    rides with the rigid shoe instead of the shin (in Idle and Crouch the shin's tilt pushed it out through the
    collar: the teal shards): all of it from below m under the rim (rim_z) down, none from band m over that up,
    smooth between."""
    if band <= 0:
        raise ValueError(f"band {band} must be positive")
    t = min(1.0, max(0.0, (z - (rim_z - below)) / band))
    return 1.0 - t * t * (3.0 - 2.0 * t)


def rim_plane(rim: list[Vec], below: float = 0.012) -> tuple[float, float, float]:
    """E1c, the collar's clean cut: the plane z = a x + b y + c through a shoe opening's rim points (least squares,
    so it tilts with the collar), lowered until every rim point lies at least below m over it; the ankle skin is
    bisected there, one clean ring inside the shoe instead of the faces' staircase over the rim."""
    if len(rim) < 3:
        raise ValueError("a rim needs three points")
    n = float(len(rim))
    mx, my, mz = (sum(p[k] for p in rim) / n for k in range(3))
    sxx = sum((p[0] - mx) ** 2 for p in rim)
    syy = sum((p[1] - my) ** 2 for p in rim)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in rim)
    sxz = sum((p[0] - mx) * (p[2] - mz) for p in rim)
    syz = sum((p[1] - my) * (p[2] - mz) for p in rim)
    det = sxx * syy - sxy * sxy
    a, b = ((sxz * syy - syz * sxy) / det, (syz * sxx - sxz * sxy) / det) if abs(det) > 1e-12 else (0.0, 0.0)
    c = min(p[2] - a * p[0] - b * p[1] for p in rim) - below
    return a, b, c


def plane_z(plane: tuple[float, float, float], x: float, y: float) -> float:
    a, b, c = plane
    return a * x + b * y + c


def outside_shell(out_hits: int) -> bool:
    """E1c: a skin vertex under the rim whose ray outward (away from the rim's centre, across the floor) meets no
    shoe face is outside the shoe's outer shell; one hit (inside the wall) or more is hidden."""
    return out_hits == 0


def hem_drop(hem_z: float, rim_z: float, rest: float, most: float = 0.04) -> float:
    """E1j3: how far the trousers' turn-up goes down so its lowest point (hem_z) rests rest m under the shoe's
    collar at the heel (rim_z): never up, at most most m."""
    return max(0.0, min(most, hem_z - (rim_z - rest)))


def hem_drops(hem: list[float | None], top: list[float | None], rest: float, most: float = 0.04,
              passes: int = 2) -> list[float]:
    """E1j3: per angle bin round a leg, how far its turn-up goes down so its lowest point there (hem) rests rest m
    under the shoe's top there (top): hem_drop per bin, a bin missing either taking its neighbours', then smoothed
    round the circle (passes of 1/4, 1/2, 1/4) so the hem's line bends gently."""
    n = len(hem)
    raw = [None if h is None or t is None else hem_drop(h, t, rest, most) for h, t in zip(hem, top)]
    if all(x is None for x in raw):
        return [0.0] * n
    for _ in range(n):
        if all(x is not None for x in raw):
            break
        raw = [x if x is not None else next((y for y in (raw[i - 1], raw[(i + 1) % n]) if y is not None), None)
               for i, x in enumerate(raw)]
    out = [float(x) for x in raw]
    for _ in range(passes):
        out = [0.25 * out[i - 1] + 0.5 * out[i] + 0.25 * out[(i + 1) % n] for i in range(n)]
    return out


def hem_shift(z: float, hem_z: float, drop: float, hold: float = 0.07, ease: float = 0.15) -> float:
    """E1j3: a garment vertex's move down (m) when the turn-up drops by drop: all of it up to hold m over the hem's
    lowest point (the turn-up keeps its shape), easing to none over the next ease m up the shin (the cloth stretches
    a little there, nothing moves above)."""
    if ease <= 0:
        raise ValueError(f"ease {ease} must be positive")
    t = min(1.0, max(0.0, (z - (hem_z + hold)) / ease))
    return drop * (1.0 - t * t * (3.0 - 2.0 * t))


def axis_dist(head: Vec, tail: Vec, p: Vec) -> float:
    """E1l: p's horizontal distance (m) from a leg's axis (the line through the LowerLeg bone's head and tail,
    extended), taken at p's own height; a level bone gives the distance from its head."""
    dz = tail[2] - head[2]
    k = (p[2] - head[2]) / dz if abs(dz) > 1e-6 else 0.0
    ax, ay = head[0] + (tail[0] - head[0]) * k, head[1] + (tail[1] - head[1]) * k
    return math.hypot(p[0] - ax, p[1] - ay)


def near_ankle(z: float, axis_d: float, rim_low: float, top: float, radius: float = 0.08) -> bool:
    """E1l: the collar's region also holds the ankle's skin over the rim's lowest point and within radius m of the
    leg's axis (up to top): the rim's xy reach missed the forward-leaning ankle front, whose faces the cover rays then
    cut one by one into a jagged edge inside the turn-up."""
    return rim_low < z <= top and axis_d <= radius


def soft_flat(ahead: float, k: float, soft: float = 0.01) -> float:
    """E1l: how far (m) a foot or ankle vertex ahead (m) of the tongue's back plane moves back onto it, by share k:
    k * ahead well ahead of the plane, none well behind it, and a quadratic ramp across +-soft between, so the
    flattened front meets the round ankle with no crease (the hard max(0, ahead) drew a vertical edge on the ankle)."""
    if soft <= 0:
        return k * max(0.0, ahead)
    if ahead <= -soft:
        return 0.0
    if ahead >= soft:
        return k * ahead
    return k * (ahead + soft) ** 2 / (4.0 * soft)


def collar_clamp(r: float, outline: float, z: float, rim_z: float, clear: float = 0.003, band: float = 0.01) -> float:
    """E1d, E1e: an ankle vertex's radius round the leg's axis, shrunk inside the shoe: under its nearest rim point
    (rim_z) it lies at most clear m inside the shoe's inner wall (outline m out from the axis toward it); from rim_z
    up over band m the limit eases out to none (a smooth falloff, no step)."""
    if band <= 0:
        raise ValueError(f"band {band} must be positive")
    most = outline - clear
    if r <= most:
        return r
    t = min(1.0, max(0.0, (z - rim_z) / band))
    return most + (r - most) * t * t * (3.0 - 2.0 * t)


def seat_weight(y: float, z: float, dist: float, z_lo: float, z_hi: float, y0: float, ramp: float = 0.03,
                far: float = 0.09, y1: float = math.inf) -> float:
    """How much a garment vertex over the seat is re-laid on the body (E1f, clothes_top.seat_wrap): 1 behind y0
    (the side seams) between z_lo and z_hi (under the waistband) and within far - ramp of the body; each border eased
    out over ramp with a smoothstep, so the re-laid cloth meets the rest without a step; 0 where the cloth bridges
    (farther than far: the crotch). E1g: y1 bounds the zone's other side too (the front's own zone: y0 < y < y1)."""
    def s(t: float) -> float:
        t = min(1.0, max(0.0, t / ramp))
        return t * t * (3.0 - 2.0 * t)
    return s(z - z_lo) * s(z_hi - z) * s(y - y0) * s(far - dist) * (s(y1 - y) if math.isfinite(y1) else 1.0)


def near_rings(seeds: list[int], nbrs: list[list[int]], rings: int) -> list[float]:
    """E1g: 1.0 for each vertex within rings edge steps of a seed (the seat's open edges), else 0.0: the seat's relax
    acts only there, so the cloth away from a flap keeps its layout (the relax over Meshy's whole relief smeared the
    stitches into wavy streaks, d16)."""
    out = [0.0] * len(nbrs)
    front = [i for i in seeds if 0 <= i < len(nbrs)]
    for i in front:
        out[i] = 1.0
    for _ in range(max(0, rings)):
        nxt = []
        for i in front:
            for j in nbrs[i]:
                if out[j] == 0.0:
                    out[j] = 1.0
                    nxt.append(j)
        front = nxt
    return out


def spike_out(d: tuple[float, float, float], n: tuple[float, float, float], limit: float) -> bool:
    """E1g: a vertex is a spike's tip when its offset d from its neighbours' mean reaches more than limit m along the
    body's outward normal n (a unit vector)."""
    return d[0] * n[0] + d[1] * n[1] + d[2] * n[2] > limit
