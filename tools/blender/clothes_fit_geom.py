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
    None when no face qualifies (the caller falls back to the plain nearest)."""
    if not -1.0 <= min_dot <= 1.0:
        raise ValueError(f"min_dot {min_dot} outside -1..1")
    best = None
    for d, nor, fi in cands:
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


def under_cloth(s: float, edge_dist: float, bone: str, deep: float = 0.001, away: float = 0.08) -> bool:
    """A body vertex hidden under the cloth for certain: inside it at rest by more than deep (s, the signed distance
    from the nearest cloth face within the proof's reach, + out) and farther than away (m) from every opening
    (edge_dist), on no bone that leaves the cloth through an opening (the neck, the hands: UNCUT_BONES, by suffix).
    The rays' cover test keeps some of these (the upper back between the straps, the crotch), and a clip then moves
    them out through the cloth (r12: 48 vertices up to 52 mm in a crouch); cut, the cloth shows instead."""
    return s < -deep and edge_dist > away and not bone.endswith(UNCUT_BONES)


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
