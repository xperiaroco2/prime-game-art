"""M15 (art #196, brief UPDATE 26): the eye socket rebuilt for the 80 % eye unit, plain geometry (numpy only, no bpy),
so it is tested without Blender. tools/blender/alien_socket_fit.py applies it to a character.

Why not M9's mount (alien_socket.py, rejected): M9 moved the skin WITH the eye. Everything within 1.3 old ball radii
followed the eye 20 mm back and 19 mm in, faded out to 2.0 radii, so the brow, the cheek and the nose bridge sank
with it: "half the head removed". Here the face never follows the eye back. Per side:

1. The eye unit is placed: scaled by `eye_scale` (against S9's ball, as alien_lids_geom.SOCKET's scale) about its old
   centre C, turned about the vertical axis by `toe` of its outward splay (1: straight ahead), moved `sink` back along
   its new axis and `inward` toward the midline: the new centre C'.
2. The old crater (S9's socket, sized for the big eye) is filled: the skin within `free_r` old ball radii of C (and
   within the new socket's sphere plus `free_margin` of C') is replaced by the fairest surface (least squares on the
   uniform Laplacian, fair_fill) that meets the untouched face round it with its slope. The face round the eye is
   continued over the crater; nothing sinks. Nothing more than `free_below` under the old centre is free (the
   cheek toward the mouth keeps its shape; a free area reaching the mouth's kept skin left a crease there).
3. The socket is cut into that surface: the skin inside the sphere of radius R_s (the slim lids' outer reach plus
   `gap`) round C' is laid onto the sphere's far side (bowl_map: the disc of skin the sphere covers goes onto the
   bowl behind the ball, its centre to the back pole, its edge to where the surface meets the sphere), so the lids
   sit in a socket that hugs them, with the face's own level round it.
4. The socket's edge is rounded (`fillet` m wide, `fillet_passes` smoothing passes, the skin kept outside R_s).
5. M17: the edge is lowered onto the lids (rim_drop): the rounded edge stood 0.6 mm from the lid as a convex lip
   that caught the light, a thin pale ring round each eye at game distance. The face less than `rim_drop` m over the
   socket's sphere is drawn onto it, so it meets the lid's surface tangentially and the lid reads tucked under the
   skin.
6. M17: the paint masks (the Body's `masks` UV: light, accent) of the free skin are filled from the face round it
   (fair_fill on the values), so the crown's hue reaches the lid above the eye as on the face beside it; the free
   skin kept the old crater's masks, a pale band between the teal and the lid (`mask_fill` 1).

7. M17b: the unit grows inside the socket (`unit`, a factor over `eye_scale`; brief UPDATE 40, "the eyes about 5 %
   bigger so less of the hollow shows"). The socket's sphere follows only `follow` of that growth (socket_radius;
   0: the socket as cut for `eye_scale`), so a bigger ball and lids fill more of the same hole and the gap between
   the lids and the bowl shrinks. The lids' rolled rim fades to nothing at the corners (alien_lids_geom.CORNER), so
   the largest reach (the upper rim's middle) only sweeps the front of the opening.

The unit's front then sits against the face's level instead of 30 mm before it (M10c), and the head round it keeps
its shape; the sink sets how deep the eye sits (the depth grid).
"""
from __future__ import annotations

import math

import numpy as np

FIT = {"eye_scale": 0.76, "sink": 0.018, "inward": 0.019, "toe": 1.0, "gap": 0.0006, "free_r": 1.5,
       "free_margin": 0.010, "free_below": 0.065, "fillet": 0.008, "fillet_passes": 24, "keep_mm": 0.2, "fill_iters": 1500,
       "rim_drop": 0.004, "mask_fill": 1.0, "unit": 1.08, "follow": 0.0}
FIT_KEYS = tuple(FIT)
BINS = 72
# M17b: the pick of the size grid (100 / 105 / 110 %, then 108 %; brief UPDATE 40): unit 1.08 in M15's socket (follow
# 0). At 100 % a 4 mm gap ran between the lower lid (1.048 r) and the socket (1.151 r + 0.6 mm) and read as a cavity at
# 0.4 m; at 105 % it was 2.3 mm and still showed the lit lip and the groove; from 108 % it reads as a shadowed crease.
RIM_DROP_DEG = 45.0  # M17: rim_drop reaches at most this far (from the ball's centre) beyond the crossing curve
RIM_DROP_FADE = 15.0  # M17b: ... fading out over the last this many degrees (and the last RIM_DROP_FADE_R R of 1.6 R)
RIM_DROP_FADE_R = 0.2
LAST = {}  # fair_fill's convergence per axis (iterations, the gradient's last share of its first): the stage reports it


def set_fit(spec: dict) -> dict:
    """FIT with a variant's values over it; refuses unknown keys and values out of range."""
    bad = set(spec) - set(FIT_KEYS)
    if bad:
        raise SystemExit(f"fit: unknown {sorted(bad)}; known {FIT_KEYS}")
    out = dict(FIT, **{k: float(v) for k, v in spec.items()})
    out["fillet_passes"] = int(out["fillet_passes"])
    out["fill_iters"] = int(out["fill_iters"])
    if not (0.5 <= out["eye_scale"] <= 1.0 and -0.01 <= out["sink"] <= 0.04 and -0.01 <= out["inward"] <= 0.03
            and 0.0 <= out["toe"] <= 1.0 and 0.0 <= out["gap"] <= 0.004 and 1.0 <= out["free_r"] <= 2.0
            and 0.0 <= out["free_below"] <= 0.12 and 0.0 <= out["free_margin"] <= 0.03
            and 0.0 <= out["fillet"] <= 0.02 and 0 <= out["fillet_passes"] <= 100
            and 1 <= out["fill_iters"] <= 10000 and 0.0 < out["keep_mm"] <= 1.0
            and 0.0 <= out["rim_drop"] <= 0.02 and out["mask_fill"] in (0.0, 1.0)  # M15b: review minor 4
            and 0.9 <= out["unit"] <= 1.25 and 0.0 <= out["follow"] <= 1.0):  # M17b
        raise SystemExit(f"fit: out of range {out}")
    return out


def lid_reach(eyes: dict, beads: dict, lids: dict) -> float:
    """The slim lids' outer reach in ball radii (the largest rho_out + bead over every design and lid; lids as
    alien_lids_geom.LIDS: the thickness times thin, the swell times rim)."""
    best = 0.0
    for d in eyes.values():
        for lid in ("upper", "lower"):
            r0, r1 = d[lid]["rho"]
            best = max(best, r0 + lids["thin"] * (r1 - r0) + lids["rim"] * beads[lid])
    return best


def socket_radius(k: float, r0: float, reach: float, s: dict) -> float:
    """M17b: the socket sphere's radius: the slim lids' reach on the `eye_scale` unit, grown by `follow` of the unit's
    own growth `unit`, plus `gap`. unit 1 (or follow 1 with unit 1) is M15's k * r0 * reach + gap exactly."""
    return k * r0 * reach * (1.0 + s["follow"] * (s["unit"] - 1.0)) + s["gap"]


def toe_angle(fwd: tuple, toe: float) -> float:
    """The turn (radians, about +Z) that takes `toe` of the axis's outward splay away (fwd's x against its -y)."""
    return -toe * math.atan2(fwd[0], -fwd[1])


def rot_z(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array(((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0)))


def place(c: np.ndarray, fwd: np.ndarray, x_sign: float, s: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The unit's new centre, its turn (3x3) and its new forward axis."""
    rz = rot_z(toe_angle(tuple(fwd), s["toe"]))
    f1 = rz @ fwd
    c1 = c - f1 * s["sink"] - np.array((x_sign * s["inward"], 0.0, 0.0))
    return c1, rz, f1


def frame(a: np.ndarray, x_sign: float) -> tuple[np.ndarray, np.ndarray]:
    """Lateral axes about the forward axis a: ey up (world +Z made normal to a), ex toward the temple."""
    ey = np.array((0.0, 0.0, 1.0)) - a * a[2]
    ey /= np.linalg.norm(ey)
    ex = np.cross(ey, a)
    if ex[0] * x_sign < 0:
        ex = -ex
    return ex, ey


class Lap:
    """The uniform graph Laplacian (L x)_i = x_i - mean of i's neighbours, as COO arrays."""

    def __init__(self, n: int, edges: np.ndarray):
        e = np.asarray(edges, dtype=np.int64).reshape(-1, 2)
        i = np.concatenate([e[:, 0], e[:, 1]])
        j = np.concatenate([e[:, 1], e[:, 0]])
        deg = np.bincount(i, minlength=n).astype(float)
        self.n = n
        self.deg = deg
        self.rows = np.concatenate([np.arange(n), i])
        self.cols = np.concatenate([np.arange(n), j])
        self.vals = np.concatenate([np.where(deg > 0, 1.0, 0.0), -1.0 / np.maximum(deg[i], 1.0)])
        self.nbr_i, self.nbr_j = i, j

    def neighbours(self, mask: np.ndarray) -> np.ndarray:
        """mask grown by one ring."""
        out = mask.copy()
        out[self.nbr_j[mask[self.nbr_i]]] = True
        return out


def fair_fill(co: np.ndarray, lap: Lap, free: np.ndarray, iters: int = 1500, tol: float = 1e-10) -> np.ndarray:
    """The free vertices moved to the fairest surface on the fixed ones: least squares of the Laplacian over the free
    vertices and their first ring (so the fill meets the fixed face with its slope), solved by CGLS from co."""
    rows_m = lap.neighbours(free)
    keep = rows_m[lap.rows]
    r, c, v = lap.rows[keep], lap.cols[keep], lap.vals[keep]
    fidx = np.flatnonzero(free)
    pos = -np.ones(lap.n, dtype=np.int64)
    pos[fidx] = np.arange(len(fidx))
    isf = free[c]
    rf, cf, vf = r[isf], pos[c[isf]], v[isf]
    rb, cb, vb = r[~isf], c[~isf], v[~isf]
    out = co.copy()
    for k in range(3):
        b = -np.bincount(rb, weights=vb * co[cb, k], minlength=lap.n)  # A_f x = b on the rows

        def A(x):
            return np.bincount(rf, weights=vf * x[cf], minlength=lap.n)

        def At(y):
            return np.bincount(cf, weights=vf * y[rf], minlength=len(fidx))

        x = co[fidx, k].copy()
        res = b - A(x)
        s_ = At(res)
        p = s_.copy()
        gamma = s_ @ s_
        g0 = gamma
        for _ in range(iters):
            q = A(p)
            qq = q @ q
            if qq <= 0:
                break
            alpha = gamma / qq
            x += alpha * p
            res -= alpha * q
            s_ = At(res)
            gn = s_ @ s_
            if gn < tol * g0:
                break
            p = s_ + (gn / gamma) * p
            gamma = gn
        out[fidx, k] = x
        LAST[k] = (_ + 1, float(gn / g0) if g0 else 0.0)
    return out


def polar(P: np.ndarray, c: np.ndarray, a: np.ndarray, ex: np.ndarray, ey: np.ndarray):
    """Distance from c, angle from the forward axis a (theta, 0 at the front pole) and azimuth (phi, from ex toward
    ey) of each point."""
    q = P - c
    d = np.maximum(np.linalg.norm(q, axis=1), 1e-12)
    theta = np.arccos(np.clip((q @ a) / d, -1.0, 1.0))
    return d, theta, np.arctan2(q @ ey, q @ ex) % (2 * np.pi)


def crossing_angles(P: np.ndarray, edges: np.ndarray, region: np.ndarray, c: np.ndarray, a: np.ndarray,
                    ex: np.ndarray, ey: np.ndarray, R: float, bins: int = BINS, smooth: int = 3) -> np.ndarray:
    """Per azimuth bin the angle from the front pole where the surface leaves the sphere (c, R): the largest
    crossing of an edge with one end inside and one outside, within 125 degrees of the front pole; empty bins
    interpolated round the circle, then `smooth` passes of a 3-bin mean. By angle, not by lateral radius, so a skin
    wall running along the axis (the temple, beside the eye) has one clean crossing too."""
    e = np.asarray(edges, dtype=np.int64).reshape(-1, 2)
    e = e[region[e[:, 0]] & region[e[:, 1]]]
    d = np.linalg.norm(P - c, axis=1)
    i0, i1 = e[:, 0], e[:, 1]
    cross = (d[i0] < R) != (d[i1] < R)
    i0, i1 = i0[cross], i1[cross]
    t = ((R - d[i0]) / (d[i1] - d[i0]))[:, None]
    _, th, phi = polar(P[i0] + t * (P[i1] - P[i0]), c, a, ex, ey)
    keep = th < math.radians(125.0)
    th, phi = th[keep], phi[keep]
    b = (phi / (2 * np.pi) * bins).astype(int) % bins
    out = np.full(bins, np.nan)
    for k in range(bins):
        if (b == k).any():
            out[k] = th[b == k].max()
    good = np.flatnonzero(~np.isnan(out))
    if len(good) == 0:
        raise SystemExit("fit: the surface never meets the socket's sphere")
    xs = np.arange(bins)
    out = np.interp(xs, np.concatenate([good - bins, good, good + bins]), np.tile(out[good], 3))
    for _ in range(smooth):
        out = (np.roll(out, 1) + out + np.roll(out, -1)) / 3.0
    return out


def at_phi(phi: np.ndarray, per_bin: np.ndarray) -> np.ndarray:
    """A per-bin value at the angles phi, linear between the bins' centres, round the circle."""
    bins = len(per_bin)
    f = phi / (2 * np.pi) * bins - 0.5
    k0 = np.floor(f).astype(int)
    w = f - k0
    return (1 - w) * per_bin[k0 % bins] + w * per_bin[(k0 + 1) % bins]


def opening(P: np.ndarray, c: np.ndarray, a: np.ndarray, ex: np.ndarray, ey: np.ndarray, th_c: np.ndarray,
            R: float) -> np.ndarray:
    """The skin the socket opens: within the crossing angle th_c(phi) of the front pole and within 1.6 R of c (the
    skin round the eye, not the head behind it). Its edge is the smooth crossing curve, so the cut leaves no saw."""
    d, th, phi = polar(P, c, a, ex, ey)
    return (th < at_phi(phi, th_c)) & (d < 1.6 * R)


def bowl_map(P: np.ndarray, c: np.ndarray, a: np.ndarray, ex: np.ndarray, ey: np.ndarray, R: float,
             th_c: np.ndarray) -> np.ndarray:
    """The opened skin laid onto the sphere's far side: its angle from the front pole over the crossing angle sets
    the angle from the back pole (0 at the back pole, the crossing's own place at the crossing)."""
    _, th, phi = polar(P, c, a, ex, ey)
    tc = at_phi(phi, th_c)
    psi = (np.pi - tc) * np.clip(th / np.maximum(tc, 1e-9), 0.0, 1.0)
    lat = np.cos(phi)[:, None] * ex + np.sin(phi)[:, None] * ey
    return c + R * (np.cos(psi)[:, None] * (-a) + np.sin(psi)[:, None] * lat)


def rim_band(P: np.ndarray, c: np.ndarray, a: np.ndarray, ex: np.ndarray, ey: np.ndarray, th_c: np.ndarray,
             width: float, R: float) -> np.ndarray:
    """The skin within `width` (m, along the sphere) of the crossing curve, before the cut, within 1.6 R of c: the
    fillet's band (the face just outside the socket and the bowl just inside its edge)."""
    d, th, phi = polar(P, c, a, ex, ey)
    return (np.abs(th - at_phi(phi, th_c)) * R < width) & (d < 1.6 * R)


def fillet(P: np.ndarray, lap: Lap, band: np.ndarray, c: np.ndarray, R: float, passes: int) -> np.ndarray:
    """The socket's edge rounded: Taubin passes (lambda 0.5, mu -0.53) over the band (rim_band: the crease and a
    few mm either side, never the packed bowl), each followed by every band point inside the sphere pushed back onto
    it along its ray from c."""
    out = P.copy()
    idx = np.flatnonzero(band)
    for _ in range(passes):
        for lam in (0.5, -0.53):
            mean = np.zeros_like(out)
            for k in range(3):
                mean[:, k] = np.bincount(lap.nbr_i, weights=out[lap.nbr_j, k], minlength=lap.n)
            mean /= np.maximum(lap.deg, 1.0)[:, None]
            out[idx] += lam * (mean[idx] - out[idx])
        q = out[idx] - c
        ql = np.linalg.norm(q, axis=1)
        ins = ql < R
        out[idx[ins]] = c + q[ins] * (R / np.maximum(ql[ins], 1e-12))[:, None]
    return out


def rim_drop(P: np.ndarray, sel: np.ndarray, c: np.ndarray, a: np.ndarray, ex: np.ndarray, ey: np.ndarray,
             th_c: np.ndarray, R: float, width: float) -> np.ndarray:
    """M17: the socket's edge lowered onto the lids. Each selected point outside the sphere (c, R) and less than
    `width` over it is drawn along its ray from c: its height h over the sphere becomes
    h * (1 - w + w * smoothstep(0, width, h)) (monotone in h, so nothing folds along a ray). The face then meets the
    sphere (the lid's surface plus the gap) tangentially instead of in a rounded convex lip and is back at its own
    level `width` over the sphere; nothing farther and nothing inside the sphere moves.
    M17b (PR #257 review, minor 3): the reach limits fade instead of cutting (w, rim_drop_weight: 1 inside, 0 past
    RIM_DROP_DEG beyond the crossing curve th_c and past 1.6 R from c), so no step is left where a limit ran through
    the band; rim_drop_steps counts what a cut still leaves (unselected points in the band)."""
    out = P.copy()
    if width <= 0.0:
        return out
    d, th, phi = polar(P, c, a, ex, ey)
    h = d - R
    w = rim_drop_weight(d, th, at_phi(phi, th_c), R)
    m = sel & (h > 0.0) & (h < width) & (w > 0.0)
    u = h[m] / width
    dn = R + h[m] * (1.0 - w[m] + w[m] * (u * u * (3.0 - 2.0 * u)))
    out[m] = c + (P[m] - c) * (dn / d[m])[:, None]
    return out


def rim_drop_weight(d: np.ndarray, th: np.ndarray, th_lim: np.ndarray, R: float) -> np.ndarray:
    """M17b: rim_drop's reach, faded: 1 up to RIM_DROP_FADE before each limit (RIM_DROP_DEG beyond the crossing curve,
    1.6 R from the centre), 0 at it, a smoothstep between."""
    lim = math.radians(RIM_DROP_DEG)
    fade = math.radians(RIM_DROP_FADE)
    wa = 1.0 - smoothstep(lim - fade, lim, th - th_lim)
    wd = 1.0 - smoothstep(1.6 * R - RIM_DROP_FADE_R * R, 1.6 * R, d)
    return wa * wd


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    u = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def rim_drop_steps(P: np.ndarray, sel: np.ndarray, edges: np.ndarray, c: np.ndarray, a: np.ndarray, ex: np.ndarray,
                   ey: np.ndarray, th_c: np.ndarray, R: float, width: float) -> int:
    """M17b: the steps rim_drop can still leave: edges between a point it draws in (selected, in the band, weight > 0)
    and an unselected point in the same band (the fixed face, which never moves). 0 on M15's socket."""
    if width <= 0.0:
        return 0
    d, th, phi = polar(P, c, a, ex, ey)
    h = d - R
    band = (h > 0.0) & (h < width) & (rim_drop_weight(d, th, at_phi(phi, th_c), R) > 0.0)
    moved = sel & band
    fixed = ~sel & band
    return int((moved[edges[:, 0]] & fixed[edges[:, 1]]).sum() + (fixed[edges[:, 0]] & moved[edges[:, 1]]).sum())


def tri_normals(co: np.ndarray, tris: np.ndarray) -> np.ndarray:
    a, b, c = co[tris[:, 0]], co[tris[:, 1]], co[tris[:, 2]]
    n = np.cross(b - a, c - a)
    return n / np.maximum(np.linalg.norm(n, axis=1), 1e-15)[:, None]


def folds(co: np.ndarray, tris: np.ndarray, mask_tri: np.ndarray, limit: float = -0.7) -> np.ndarray:
    """The midpoints of the edges inside the masked triangles whose two triangles' normals meet at more than about
    135 degrees: a surface folded back over itself (a fold turns the normal about 180 degrees; the socket's rounded
    edge turns it far less)."""
    n = tri_normals(co, tris)
    ed = {}
    bad = []
    for t in np.flatnonzero(mask_tri):
        for u, v in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((int(tris[t, u]), int(tris[t, v]))))
            o = ed.get(key)
            if o is None:
                ed[key] = t
            elif n[o] @ n[t] < limit:
                bad.append((co[key[0]] + co[key[1]]) * 0.5)
    return np.array(bad).reshape(-1, 3)


def hidden(pts: np.ndarray, c: np.ndarray, a: np.ndarray, r_ball: float, R: float) -> np.ndarray:
    """Points of the socket's bowl that no view sees: within R (plus 1 mm) of the new centre and behind the ball's
    front half (h below 0.3 ball radii: the lids and the ball cover them from every angle the head is seen)."""
    q = pts - c
    return (np.linalg.norm(q, axis=1) < R + 0.001) & ((q @ a) < 0.3 * r_ball)
