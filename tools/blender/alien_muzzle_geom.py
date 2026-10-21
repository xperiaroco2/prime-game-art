"""Pure geometry for alien_muzzle.py (art #196, Test B: the mouth sculpted into the head). Numpy only, no bpy, so the
fast tests can import it. Blender axes: x across (+ the alien's left), -y forward, z up; metres.

The muzzle is a height field along -y over the lower face: the skin swelled forward by `swell(x, z)` (a plateau round
the mouth that fades out at the cheeks, at the chin and below the nose line), and the AI rest lips joined to it by a
smooth union (`smin`): where the lips stand in front of the swelled skin the surface is the lips' front, and the two
meet in a fillet `blend` wide, so lip and skin are one surface with no edge.
"""
from __future__ import annotations

import math

import numpy as np

MUZZLE = {
    "swell_mm": 11.0,  # the forward swell of the skin round the mouth (u1's side view: the lower face bulges forward)
    "rx": 0.060,  # the swell's half-width (m), measured from the mouth's centre
    "rz_up": 0.040,  # its reach above the mouth's centre (then cut by the nose line's band)
    "rz_lo": 0.052,  # its reach below (to the chin)
    "plateau": 0.30,  # share of the radius at full swell
    "top_band": 0.010,  # the swell fades to 0 over this band below the region's top (the nose line's gate)
    "blend_mm": 4.0,  # the smooth union's width (the fillet between skin and lips)
    "lip_t0_mm": -1.2,  # a point is lip (coral) where the lips stand this far in front of the swelled skin (< 0:
    # the coral reaches down into the fillet, so its steep wall is lip, not a pale skin rim)
    "ride": 1.0,  # the lips move forward with the swell under them (1: the muzzle carries the lips)
    "chin_mm": 2.0,  # a soft chin: the swell's extra forward push centred under the lower lip
    "chin_z": -0.030,  # its centre below the mouth's centre (m)
    "chin_r": 0.016,  # its radius (m)
}

INSIDE_PUSH = 0.03  # m: see surface_y
INSIDE_MM = (0.6, 2.4)  # the share `inside` rises from 0 to 1 over this depth inside the lips' outline

JAW = {
    "hinge_y": 0.004,  # the jaw's hinge axis (x), Blender y and z (m): behind the mouth, near the lip line's height
    "hinge_z": 1.462,
    "deg": 14.0,  # the morph target's angle; 8 degrees is its weight 8 / 14
    "x_full": 0.040,  # the jaw weight is full within |x| <= this ...
    "x_zero": 0.062,  # ... and 0 beyond this (the cheeks stay)
    "back_full": -0.045,  # under the chin: full in front of this y ...
    "back_zero": -0.020,  # ... 0 behind it (the throat stays)
    "corner_band": 0.003,  # past the slit's end the weight crosses the lip line over this band (m), growing outward
    "corner_grow": 0.8,
    "taper": 0.45,  # at the parting's ends the lower lip turns this share of the jaw (an oval opening, not a slot)
    "taper_mm": 9.0,  # ... fading to the full turn this far below the lip line
    "lift_mm": 2.5,  # the upper lip's centre rises this much at the full jaw
    "lift_reach_mm": 9.0,  # ... fading out this far above the lip line
}


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, dtype=float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def smin(a, b, k):
    """The polynomial smooth minimum of a and b (k > 0: the blend's width); equals min(a, b) where |a - b| >= k.
    Returns (value, h) with h the share of b (0: a wins, 1: b wins)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    h = np.clip(0.5 + 0.5 * (a - b) / k, 0.0, 1.0)
    return b * h + a * (1.0 - h) - k * h * (1.0 - h), h


def swell(x, z, centre_z: float, z_top: float, p: dict = MUZZLE):
    """The skin's forward swell (m, >= 0) at (x, z): a plateau round the mouth's centre, fading out at rx / rz and to
    exactly 0 at z_top and above."""
    x = np.asarray(x, dtype=float)
    dz = np.asarray(z, dtype=float) - centre_z
    rz = np.where(dz > 0, p["rz_up"], p["rz_lo"])
    r = np.sqrt((x / p["rx"]) ** 2 + (dz / rz) ** 2)
    g = 1.0 - smoothstep(p["plateau"], 1.0, r)
    top = 1.0 - smoothstep(z_top - p["top_band"], z_top, np.asarray(z, dtype=float))
    rc = np.sqrt(x ** 2 + (dz - p["chin_z"]) ** 2) / p["chin_r"]
    chin = p["chin_mm"] / 1000.0 * (1.0 - smoothstep(0.0, 1.0, rc))
    return (p["swell_mm"] / 1000.0 * g + chin) * top


def surface_y(y_skin, lip_y, s, inside=0.0, p: dict = MUZZLE):
    """The muzzle's y at a point: the swelled skin (y_skin - s) united with the lips' front lip_y (nan: no lip there).
    `inside` (0..1) is how deep the point lies inside the lips' outline seen from the front: there the skin is sent
    back by INSIDE_PUSH, so the lips win (their groove is never filled by skin) and the fillet stays at the outline.
    Returns (y, stand) with stand = how far the lips stand in front of that skin (m; -inf with no lip)."""
    ys = np.asarray(y_skin, dtype=float) - s + INSIDE_PUSH * np.asarray(inside, dtype=float)
    lip = np.asarray(lip_y, dtype=float)
    has = np.isfinite(lip)
    k = p["blend_mm"] / 1000.0
    u, _ = smin(ys, np.where(has, lip, ys + 1.0), k)
    y = np.where(has, u, ys)
    stand = np.where(has, ys - np.where(has, lip, 0.0), -np.inf)
    return y, stand


def lip_line(xs, zs, depth, jaw_alpha, search_mm: float = 3.0):
    """The lip line on the lips' front: per column x (xs, the columns of the depth grid depth[z, x], larger y =
    deeper, nan where no lip), the z of the deepest point within search_mm of the jaw weight's 0.5 crossing (the groove
    between the upper and the lower lip). Returns z per column (nan where the column has no crossing)."""
    out = np.full(len(xs), np.nan)
    for j in range(len(xs)):
        col, a = depth[:, j], jaw_alpha[:, j]
        ok = np.isfinite(col) & np.isfinite(a)
        if ok.sum() < 3:
            continue
        idx = np.where(ok)[0]
        zc = None
        for i0, i1 in zip(idx[:-1], idx[1:]):  # zs ascending: the alpha goes from 1 (below) to 0 (above)
            if i1 == i0 + 1 and (a[i0] - 0.5) * (a[i1] - 0.5) <= 0 and a[i0] != a[i1]:
                t = (a[i0] - 0.5) / (a[i0] - a[i1])
                zc = zs[i0] + t * (zs[i1] - zs[i0])
                break
        if zc is None:
            continue
        near = ok & (np.abs(zs - zc) <= search_mm / 1000.0)
        if near.sum() == 0:
            out[j] = zc
            continue
        k = np.where(near)[0][np.argmax(col[near])]
        out[j] = zs[k]
    return out


def smooth_symmetric(xs, zl, passes: int = 4):
    """A lip line made mirror-symmetric about x = 0 (xs symmetric) and smoothed by a 3-tap filter."""
    z = np.array(zl, dtype=float)
    z = np.where(np.isfinite(z) & np.isfinite(z[::-1]), 0.5 * (z + z[::-1]), np.nan)
    for _ in range(passes):
        zp = z.copy()
        for j in range(1, len(z) - 1):
            if np.isfinite(z[j - 1]) and np.isfinite(z[j]) and np.isfinite(z[j + 1]):
                zp[j] = 0.25 * z[j - 1] + 0.5 * z[j] + 0.25 * z[j + 1]
        z = zp
    return z


def rot_x(p, hinge_y: float, hinge_z: float, deg):
    """Points p (n, 3) turned about the x axis through (hinge_y, hinge_z) by deg (per point or one angle); a positive
    angle takes a point in front of the hinge (y < hinge_y) down: the jaw opening."""
    p = np.asarray(p, dtype=float)
    a = np.radians(np.broadcast_to(np.asarray(deg, dtype=float), (len(p),)))
    y, z = p[:, 1] - hinge_y, p[:, 2] - hinge_z
    c, s = np.cos(a), np.sin(a)
    out = p.copy()
    out[:, 1] = hinge_y + y * c - z * s
    out[:, 2] = hinge_z + y * s + z * c
    return out


def jaw_weight(x, y, sd, x_slit: float, p: dict = JAW):
    """The skin's jaw weight (0..1) from x, y and sd (the signed height over the lip line, m; + above): below the line
    1 within the slit's span, a band past its ends that widens outward, then faded out at the cheeks and the throat."""
    x = np.abs(np.asarray(x, dtype=float))
    sd = np.asarray(sd, dtype=float)
    band = p["corner_band"] + np.maximum(x - x_slit, 0.0) * p["corner_grow"]
    inside = x <= x_slit
    w = np.where(inside, (sd < 0).astype(float), 1.0 - smoothstep(-band, band, sd))
    w = w * (1.0 - smoothstep(p["x_full"], p["x_zero"], x))
    w = w * (1.0 - smoothstep(p["back_full"], p["back_zero"], np.asarray(y, dtype=float)))
    return w


def chamfer(mask):
    """The distance (in cells) of each True cell of a 2D mask to the nearest False cell: a two-pass (1, 1.41)
    chamfer transform."""
    h, w = mask.shape
    d = np.where(mask, 1e9, 0.0)
    for rows, cols, di in ((range(h), range(w), -1), (range(h - 1, -1, -1), range(w - 1, -1, -1), 1)):
        for i in rows:
            for j in cols:
                v = d[i, j]
                if v == 0.0:
                    continue
                ii = i + di
                if 0 <= ii < h:
                    v = min(v, d[ii, j] + 1.0)
                    if j > 0:
                        v = min(v, d[ii, j - 1] + 1.41)
                    if j < w - 1:
                        v = min(v, d[ii, j + 1] + 1.41)
                jj = j + di
                if 0 <= jj < w:
                    v = min(v, d[i, jj] + 1.0)
                d[i, j] = v
    return d


def jaw_taper(x, sd, x_slit: float, p: dict = JAW):
    """The share of the jaw's turn near the lip line: 1 at the parting's centre, p["taper"] at its ends, back to 1
    p["taper_mm"] below the line (so the chin turns whole)."""
    q = np.clip(np.abs(np.asarray(x, dtype=float)) / x_slit, 0.0, 1.0)
    across = p["taper"] + (1.0 - p["taper"]) * np.sqrt(1.0 - q * q)
    near = 1.0 - smoothstep(0.0, p["taper_mm"] / 1000.0, -np.asarray(sd, dtype=float))
    return 1.0 - near * (1.0 - across)


def lip_lift(x, sd, x_slit: float, p: dict = JAW):
    """The upper lip's rise at the full jaw (m): most at the centre, 0 at the parting's ends and lift_reach above."""
    q = np.clip(np.abs(np.asarray(x, dtype=float)) / x_slit, 0.0, 1.0)
    sd = np.asarray(sd, dtype=float)
    up = (sd >= 0) * (1.0 - smoothstep(0.0, p["lift_reach_mm"] / 1000.0, sd))
    return p["lift_mm"] / 1000.0 * (1.0 - q * q) * up


def iso_t(va: float, vb: float) -> float:
    """Where along an edge from a (value va) to b (vb) the value crosses 0 (va, vb of opposite signs)."""
    return va / (va - vb)


def talk_curve(t_s, seed: int = 196):
    """A simple speech amplitude 0..1 over time (s): syllables at about 4.5 Hz in phrases of 1.6-2.4 s with pauses,
    the loudness varying per syllable. Deterministic."""
    rng = np.random.default_rng(seed)
    t = np.asarray(t_s, dtype=float)
    out = np.zeros_like(t)
    start = 0.25
    while start < float(t.max()) + 1.0:
        dur = rng.uniform(1.6, 2.4)
        n = max(2, int(dur * 4.5))
        amps = rng.uniform(0.35, 1.0, n)
        for i in range(n):
            c = start + (i + 0.5) * dur / n
            w = dur / n * 0.42
            out = np.maximum(out, amps[i] * np.exp(-0.5 * ((t - c) / w) ** 2))
        start += dur + rng.uniform(0.35, 0.7)
    return np.clip(out, 0.0, 1.0)


def deg_from_amp(a, max_deg: float = 14.0, gate: float = 0.08):
    """The jaw angle for amplitude a: closed under the gate, then eased up to max_deg."""
    a = np.clip((np.asarray(a, dtype=float) - gate) / (1.0 - gate), 0.0, 1.0)
    return max_deg * (1.0 - (1.0 - a) ** 1.6)


def mm(v) -> float:
    return round(float(v) * 1000.0, 2)


def angle_ok(deg) -> bool:
    return 0.0 <= deg <= 20.0 and not math.isnan(deg)
