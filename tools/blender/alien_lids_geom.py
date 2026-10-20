"""M6's pure parts (art #196): the lid shells' rounded corners, the eye unit's size and the skin's contact field. Plain
Python, no bpy: read by alien_parts_geom.lid_shell (the shell's profile), alien_eyes.py (the wet strips follow the
same profile), alien_m6.py inside Blender and tools/tests/test_alien_lids_geom.py.

Lengths are in eyeball radii; elevations p in radians about the lid's hinge (lid_shell: the moving edge at p = 0,
the upper lid covering p > 0, the lower p < 0); latitudes t in radians from the lid's middle toward the hinge poles
(the eye's inner and outer corners, at t = +-t_max).

Why: seen from the front, S7's rolled rim (`bead`, a swell of the outer surface over the last degrees before the
edge) kept its full height out to the hinge poles, so at both corners the upper lid's rim stuck out sideways past the
dome's outline as a point (the engineer, 2026-10-19: "very sharp corners"). M6 tapers the swell to nothing toward the
corners and lets the upper lid's edge droop a little there (the lower lid's rise), so the two lids meet in a soft
almond, as in the paintover rf2. The middle of each lid (|t| below `from_deg`) is unchanged, so the rim's reach, the
eye shader's contact band and the blink are as before.
"""
from __future__ import annotations

import math

# The corner rounding (chosen on M6's grid; alien_m6.py --corner JSON merges a variant over it). from_deg: the
# latitude where the taper starts (the lid's middle keeps S7's rim); bead_keep: the share of the swell left at the
# pole; droop_deg / lift_deg: how far the upper lid's edge moves down and the lower lid's edge up at the pole (the
# back of the shell stays; the shift fades out toward it).
CORNER = {"from_deg": 35.0, "bead_keep": 0.0, "droop_deg": 10.0, "lift_deg": 5.0}
# No rounding: S7's shell (alien_parts_geom.lid_shell without `corner`)
CORNER_OFF = {"from_deg": 90.0, "bead_keep": 1.0, "droop_deg": 0.0, "lift_deg": 0.0}

# The eye unit's size (ball, lids and wet strips scaled together about the socket, the ball's centre) and the iris
# and pupil's angular size (alien.gd EYE_LOOK); chosen on M6's grid beside rf2.
EYE_SCALE = 0.95
EYE_SINK = 0.002  # m: the unit moved back into the head along the socket's axis, so the smaller domes meet the skin
IRIS_SCALE = 1.0

# The skin's contact shade near the lids and lips (alien_hue.gdshader `contact_*`): full where the skin touches a
# part, none `reach` m away (a smoothstep), stored per Body vertex and per design (M6c: one channel per design, so the
# shade under the hidden design's lips or lids never shows; PR #238's minor 4) in two UV layers, CONTACT_UVS: layer
# name -> its (u, v) designs. Body's fifth and sixth UV layers are glTF TEXCOORD_4 and TEXCOORD_5, which Godot imports
# together as CUSTOM1 (RGBA_FLOAT: x, y from TEXCOORD_4, z, w from TEXCOORD_5): CONTACT_CHANNEL is a design's
# component there, and the skin shader takes the max of the picked eye design's and the picked mouth's (alien.gd
# CONTACT_CHANNEL, alien_hue.gdshader `contact_pick`).
CONTACT = {"reach": 0.007, "smooth": 2}
CONTACT_UVS = {"contact": ("bored", "manic"), "contact_mouth": ("frog", "overbite")}
CONTACT_CHANNEL = {d: 2 * i + j for i, ds in enumerate(CONTACT_UVS.values()) for j, d in enumerate(ds)}


def contact_pick(eye: str, mouth: str) -> tuple[float, float, float, float]:
    """The skin shader's `contact_pick` (a weight per CUSTOM1 component) for an eye design and a mouth design: 1 on
    the two designs' channels, 0 elsewhere."""
    pick = [0.0] * 4
    for d in (eye, mouth):
        pick[CONTACT_CHANNEL[d]] = 1.0
    return (pick[0], pick[1], pick[2], pick[3])


def smoothstep(a: float, b: float, x: float) -> float:
    if b == a:
        return 0.0 if x < a else 1.0
    s = min(1.0, max(0.0, (x - a) / (b - a)))
    return s * s * (3.0 - 2.0 * s)


def corner_weight(t: float, t_max: float, c: dict = CORNER) -> float:
    """0 in the lid's middle, rising to 1 at the hinge poles (|t| = t_max)."""
    t0 = math.radians(c["from_deg"])
    if t0 >= t_max:
        return 0.0
    return smoothstep(t0, t_max, abs(t))


def bead_at(bead: float, t: float, t_max: float, c: dict = CORNER) -> float:
    """The rolled rim's swell at latitude t: the full `bead` in the middle, `bead_keep` of it at the poles."""
    return bead * (1.0 - (1.0 - c["bead_keep"]) * corner_weight(t, t_max, c))


def edge_shift(t: float, t_max: float, upper: bool, c: dict = CORNER) -> float:
    """How far (radians) the lid's edge moves at latitude t: the upper lid's down (negative p), the lower lid's up
    (positive p), so the edges bend toward each other at the corners."""
    d = math.radians(c["droop_deg"] if upper else c["lift_deg"])
    return (-d if upper else d) * corner_weight(t, t_max, c)


def shell_profile(rho_in: float, rho_out: float, bead: float, upper: bool, span_deg: float = 200.0, seg_p: int = 12,
                  rim_seg: int = 5, bead_deg: float = 26.0, shift: float = 0.0,
                  crowd: bool | None = None, flare: dict | None = None,
                  t: float = 0.0) -> list[tuple[float, float, float]]:
    """lid_shell()'s closed cross-section as (rho, p, p0) round the loop: the outer surface from the back to the edge,
    the rim's half circle beyond the edge, the inner surface back again (rho in r; p the elevation, p0 the same point's
    elevation before `shift`, for the accent mask). `bead` swells the outer surface over the last bead_deg before the
    edge, the rim's half circle spanning the thicker edge; the samples crowd toward the edge (quadratic) when bead > 0.
    `shift` moves the edge by that many radians, fading out to nothing at the shell's back (span_deg), so the shell
    stays closed and its back is unchanged. With shift 0 this is S7's profile exactly. `crowd` (default: bead > 0)
    sets the quadratic sampling apart from the bead, so a rounded shell tapered to no bead at its poles keeps the
    same sampling in every row (no crease). `flare` (M10, FLARE_OFF's form) swells the outer surface behind the edge
    (flare_at, faded toward the hinge poles by the row's latitude t, M10b); None or amount 0 changes nothing."""
    sgn = 1.0 if upper else -1.0
    ex = 2 if (bool(bead) if crowd is None else crowd) else 1
    span = math.radians(span_deg)
    ro, ri = rho_out, rho_in
    re = ro + bead
    rm, hw = (re + ri) / 2, (re - ri) / 2
    bd = math.radians(bead_deg)
    out = []

    def put(rho, p):
        out.append((rho, p + shift * (1.0 - min(1.0, abs(p) / span)), p))

    for j in range(seg_p + 1):
        f = (1 - j / seg_p) ** ex
        p = span * f
        swell = bead * (1 - smoothstep(0.0, bd, p)) if bead else 0.0
        put(ro + swell + flare_at(p, flare, t), sgn * p)
    for j in range(1, rim_seg):
        a = math.pi * j / rim_seg
        put(rm + hw * math.cos(a), -sgn * (hw * math.sin(a)) / rm)
    for j in range(seg_p + 1):
        put(ri, sgn * span * (j / seg_p) ** ex)
    return out


def front_outline(rho_out: float, bead: float, edge_deg: float, upper: bool, t_max_deg: float = 89.0,
                  c: dict = CORNER, n: int = 90) -> list[tuple[float, float]]:
    """The lid edge's rim seen from the front (x right, z up, in r): per latitude the outermost point of the rim at
    the lid's rest edge elevation edge_deg (the lid turned so its edge lies there). For the test: how far the corner
    sticks out beyond the dome's own outline (rho_out)."""
    tm = math.radians(t_max_deg)
    pts = []
    for i in range(n + 1):
        t = -tm + 2 * tm * i / n
        b = bead_at(bead, t, tm, c)
        p = math.radians(edge_deg) + edge_shift(t, tm, upper, c)
        rho = rho_out + b
        pts.append((rho * math.sin(t), rho * math.cos(t) * math.sin(p)))
    return pts


def corner_overhang(rho_out: float, bead: float, c: dict = CORNER, t_max_deg: float = 89.0) -> float:
    """How far (in r) the rim at the pole reaches sideways past the dome's outline: S7's full bead there was the
    point the engineer saw."""
    tm = math.radians(t_max_deg)
    return (rho_out + bead_at(bead, tm, tm, c)) * math.sin(tm) - rho_out


def scale_about(co: tuple[float, float, float], pivot: tuple[float, float, float], k: float) -> tuple:
    """A point scaled by k about a pivot (the eye unit about its socket)."""
    return tuple(p + k * (x - p) for x, p in zip(co, pivot))


def iris_look(look: dict, k: float) -> dict:
    """An eye design's EYE_LOOK angles with the iris and pupil scaled by k: iris_deg and pupil_deg times k, and
    limbus_deg (the cornea's edge) moved by as much as the iris' edge, so iris_deg + edge 0.9 <= limbus_deg -
    limbus_soft_deg still holds; with no iris (manic) the limbus scales with the pupil."""
    out = dict(look)
    iris = out.get("iris_deg", 0.0)
    for key in ("iris_deg", "pupil_deg"):
        if key in out:
            out[key] = round(out[key] * k, 3)
    if "limbus_deg" in out:
        out["limbus_deg"] = round(out["limbus_deg"] - iris * (1.0 - k) if iris > 0 else out["limbus_deg"] * k, 3)
    return out


def contact(dist: float, reach: float = CONTACT["reach"]) -> float:
    """The contact field at a skin point `dist` m from the nearest lid or lip surface: 1 at contact, 0 beyond reach."""
    return 1.0 - smoothstep(0.0, reach, dist)


# M9 (art #196): one standard eye mount. The engineer (2026-10-20): the eyes too big and bulging out "like a crab's";
# in the liked 2D part sheet e2 the ball's front sits about flush with the face, the eyes stay inside the head's front
# silhouette and a soft socket rim surrounds each. So the eye unit and the skin's socket move together: every eye
# part (ball, lids, wet strips) and the Body's socket bowl are scaled by `scale` about the old ball centre C and moved
# by eye_offset() (`sink` m back along the socket's axis, `inward` m toward the head's midline), so the bowl still
# hugs the smaller eye as it hugged the full-size one (no gap, no dark line where a lid meets the skin; M6's open
# issue). The skin within `inner` old ball radii of C follows exactly; from there to `outer` the follow fades
# (socket_weight, a smootherstep), which forms the socket's slope. A soft rim of `rim` m is raised on the skin round
# the smaller eye, at `rim_at` new lid radii from the new centre (rim_bump, `rim_w` wide), on the socket's front half.
# `scale` is against S9's full-size eye (M6/M7's EYE_SCALE 0.95 is the same measure). Every design built on S9's
# sockets fits the mount; tools/blender/alien_socket.py applies it to a character (Body["prime_socket"] records it,
# so alien_m6.py does not scale the eyes again). Chosen on M9's grid beside e2.
SOCKET = {"scale": 0.82, "sink": 0.020, "inward": 0.019, "inner": 1.3, "outer": 2.0, "rim": 0.0008, "rim_at": 1.10,
          "rim_w": 0.14, "light_in": 1.4, "light_out": 1.95, "smooth": 30}
# M9b: the pale skin round the mounted eye. The mount pulls the skin within `inner` toward the smaller eye, so the
# vertices that carried the crown's teal (the `masks` light 0, once hidden under S9's big lids) moved down beside the
# eye and read, shaded on the socket's downward slope, as a dark band of eye shadow. In e2 the skin round each eye is
# the pale face's. So the mount raises the light mask (never lowers it) to eye_light(): full within `light_in` new
# ball radii of the new centre, none past `light_out` (a smoothstep), on skin facing the socket's way (the skin
# normal's cosine to the socket's forward axis: none below -0.3, full from 0.4; the temples and the head's sides keep
# their teal). light_out 0 is M9's mask.
# M9b: the slope's ripples. The warp packs the old socket's skin (1.3 to 2.0 old radii) into a narrower slope, and its
# small undulations, hidden under S9's lids and the teal, showed on the pale as two or three arcs above each eye.
# `smooth` Taubin passes (alien_socket.py) even out that band before the rim is raised: full weight from `inner` to
# 0.85 of the way to `outer`, none at `outer`, above the eye only (from 0.2 old radii below its centre, full
# from 0.3 above; the nose keeps its shape); the bowl inside `inner` (under the lids) and the skin beyond keep
# their shape. 0 is M9's slope.
SOCKET_KEYS = tuple(SOCKET)


def clamp01(x):
    """x clamped to [0, 1]; plain arithmetic, so it takes floats and numpy arrays alike."""
    return (abs(x) - abs(x - 1.0) + 1.0) * 0.5


def socket_weight(d, inner: float, outer: float):
    """How fully the skin follows the eye at d old ball radii from the old centre: 1 within `inner`, a smootherstep
    down to 0 at `outer`."""
    t = clamp01((d - inner) / (outer - inner))
    return 1.0 - t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def rim_bump(dd, at: float, width: float):
    """The soft rim's profile at dd new lid radii from the new centre: 1 at `at`, 0 beyond `width` either side."""
    x = (dd - at) / width
    b = clamp01(1.0 - x * x)
    return b * b


def eye_light(dd, cos_fwd, light_in: float, light_out: float):
    """The light mask's floor at dd new ball radii from the new centre, cos_fwd the skin normal's cosine to the
    socket's forward axis: 1 inside light_in, a smoothstep to 0 at light_out, on skin facing forward only."""
    t = clamp01((dd - light_in) / max(light_out - light_in, 1e-9))
    return (1.0 - t * t * (3.0 - 2.0 * t)) * clamp01((cos_fwd + 0.3) / 0.7)


def smooth_band(d, inner: float, outer: float):
    """The slope smoothing's weight at d old ball radii: 0 inside `inner`, a smoothstep up to 1 just past it, 1 to
    0.85 of the way to `outer`, a smoothstep down to 0 at `outer`."""
    a = clamp01((d - inner) / 0.08)
    b = clamp01((outer - d) / (0.15 * (outer - inner)))
    return a * a * (3.0 - 2.0 * a) * b * b * (3.0 - 2.0 * b)


def eye_offset(fwd: tuple, x_sign: float, sink: float, inward: float) -> tuple:
    """The eye unit's move (m, world): `sink` back along the socket's forward axis fwd, `inward` toward x = 0 (x_sign:
    the side's sign of x)."""
    return (-fwd[0] * sink - x_sign * inward, -fwd[1] * sink, -fwd[2] * sink)


def socket_warp(p: tuple, c: tuple, off: tuple, k: float, r0: float, s: dict = SOCKET) -> tuple:
    """A skin point p after the mount (the rim aside): toward c + off + k (p - c) by socket_weight of its distance."""
    w = socket_weight(math.dist(p, c) / r0, s["inner"], s["outer"])
    return tuple(pi + w * (ci + oi + k * (pi - ci) - pi) for pi, ci, oi in zip(p, c, off))


def set_socket(spec: dict) -> dict:
    """SOCKET with a variant's values over it ({name: value}, names from SOCKET_KEYS)."""
    bad = set(spec) - set(SOCKET_KEYS)
    if bad:
        raise SystemExit(f"socket: unknown {sorted(bad)}; known {SOCKET_KEYS}")
    out = dict(SOCKET, **{k: float(v) for k, v in spec.items()})
    if (not 0.4 <= out["scale"] <= 1.2 or out["outer"] <= out["inner"] or out["rim_w"] <= 0
            or (out["light_out"] and out["light_out"] <= out["light_in"])):
        raise SystemExit(f"socket: out of range {out}")
    return out


# M9b (art #196): slim lid shells. In the liked sheet e2 the coral lids are thin shells hugging the ball with a soft
# rolled rim; S9's shells (alien_parts.EYES rho, LID_BEAD) read as thick domes on M9's smaller eyes. A lid setting
# keeps each shell's inner radius (the ball's clearance, the wet strip under it and the blink: the upper lid's inner
# surface stays outside the lower lid, so the closed lids still overlap and seal) and multiplies the shell's thickness
# (rho_out - rho_in) by `thin` and the rolled rim's swell (LID_BEAD) by `rim`. alien_m6.py rebuilds the shells and the
# wet strips with it (`--lids JSON` for a grid); alien.gd EYE_LOOK's *_reach_deg follow (alien_eyes_geom.rim_reach of
# the slimmed lid). LIDS_S9 builds S9's shells exactly. Chosen on M9b's grid beside e2.
LIDS = {"thin": 0.3, "rim": 0.7}
LIDS_S9 = {"thin": 1.0, "rim": 1.0}


def set_lids(spec: dict) -> dict:
    """LIDS with a variant's values over it; refuses unknown keys and a value outside (0.1, 1.5)."""
    bad = set(spec) - set(LIDS)
    if bad:
        raise SystemExit(f"lids: unknown {sorted(bad)}; known {sorted(LIDS)}")
    out = dict(LIDS, **{k: float(v) for k, v in spec.items()})
    if not all(0.1 <= v <= 1.5 for v in out.values()):
        raise SystemExit(f"lids: out of range {out}")
    return out


def slim(rho: tuple, bead: float, lids: dict = LIDS) -> tuple[tuple[float, float], float]:
    """A lid's (rho_in, rho_out) and rim swell under a lid setting: the inner radius kept, the thickness times
    `thin`, the swell times `rim`."""
    return (rho[0], rho[0] + lids["thin"] * (rho[1] - rho[0])), bead * lids["rim"]


# M10 (art #196, brief UPDATE 12): smaller eyes on the unchanged skull. M9's socket re-sculpt was rejected (the skull
# looked dented), so the skin round the eye never moves: the eye unit is only scaled about its socket (EYE_SCALE, as
# M6) and S9's lids are kept. Below about 95 % a gap opens between the shrunken dome and the socket's skin, which was
# shaped for the full-size eye (M6's grid: a dark crescent at 86 %). The flare closes it on the lid alone: the
# shell's outer surface swells by `amount` ball radii from `from_deg` to `to_deg` of elevation behind the edge (a
# smoothstep measured from the edge), where the dome runs into the socket's skin, so the rim, the rolled bead, the
# wet strip, the rim reach and the blink's seal (the inner surface) are untouched. alien_m6.py --flare auto finds the
# smallest amount per design and lid with which the dome reaches `margin` into the skin at every latitude (lid_gap).
# FLARE_OFF is S9's shell exactly.
FLARE_OFF = {"amount": 0.0, "from_deg": 25.0, "to_deg": 70.0}
# Where the ramp sits (M10's first grid: a ramp from 25 degrees swelled the dome's visible top, so the eyes did not
# read smaller): it starts `from_off` degrees before the elevation where the dome turns away from a front view (90
# degrees from the eye's forward axis, at local p = 90 - |the lid's rest edge elevation|) and rises over `width`
# degrees behind it, so the swell sits behind the dome's front outline, where it runs into the head's skin.
# M10b: the ramp is longer (width 50 -> 90 degrees: M10's 50 left a soft shoulder where the swell began at 0.4 m).
FLARE_SIL = {"from_off": -5.0, "width": 90.0}
# M10b: the flare can fade toward the hinge poles (the corners, where the two lids meet): at latitude t it is
# 1 - FLARE_POLE_FADE * corner_weight(t, FLARE_POLE_TMAX) of the amount, with CORNER's ramp. Off (0): the gaps are
# largest at the corners (M10: 0.6 to 1.1 mm at 100 %), so a fade there only raises the amount everywhere (a uniform
# bowl: 0.0765 r without, 0.1275 r with a fade of 0.5), which swells the dome's middle. The corner notch is gone
# instead by alien_m6.flares giving both lids of a design one amount.
FLARE_POLE_FADE = 0.0
FLARE_POLE_TMAX = 89.0  # lid_shell's t_max_deg


def flare_base(rest_deg: float, s: dict = FLARE_SIL) -> dict:
    """FLARE_OFF with its ramp placed for a lid whose edge rests at rest_deg (alien_parts.EYES' `rest`)."""
    a = max(10.0, 90.0 - abs(rest_deg) + s["from_off"])
    return dict(FLARE_OFF, from_deg=a, to_deg=a + s["width"])
FLARE_MARGIN = 0.004  # ball radii (about 0.15 mm): the dome must reach this far into the skin at every latitude
FLARE_STEP = 0.0025
FLARE_MAX = 0.4


def flare_at(p_abs: float, f: dict | None, t: float = 0.0) -> float:
    """The outer surface's swell (ball radii) at |p| radians behind the lid's edge and latitude t (radians; the
    swell fades toward the hinge poles by f's `pole_fade`, FLARE_POLE_FADE when f has none)."""
    if not f or not f["amount"]:
        return 0.0
    fade = 1.0 - f.get("pole_fade", FLARE_POLE_FADE) * corner_weight(t, math.radians(FLARE_POLE_TMAX))
    return f["amount"] * fade * smoothstep(math.radians(f["from_deg"]), math.radians(f["to_deg"]), abs(p_abs))


def local_tp(pts) -> list[tuple[float, float, float]]:
    """Points (x, y, z) in a lid's local frame (lid_shell's: the edge on -Y, the hinge on X) as (rho, t, p): their
    distance (in the points' unit), the latitude toward the hinge and the elevation from -Y toward +Z (radians)."""
    out = []
    for x, y, z in pts:
        rho = math.sqrt(x * x + y * y + z * z)
        t = math.asin(max(-1.0, min(1.0, x / max(rho, 1e-12))))
        out.append((rho, t, math.atan2(z, -y)))
    return out


def lid_gap(pts, rho_out: float, bead: float, upper: bool, flare: dict | None, span_deg: float = 200.0,
            bead_deg: float = 26.0, bin_deg: float = 10.0, t_max_deg: float = 80.0, rho_max: float = 1.8,
            min_pts: int = 3, tp: list | None = None) -> list[tuple[float, float, float]]:
    """How far the socket's skin stands outside a lid's dome. pts: the skin's points (x, y, z) in the lid's local
    frame, in ball radii (the lid at rest; or tp, their local_tp). Per latitude bin (bin_deg wide, |t| < t_max_deg)
    over the skin the lid covers (p of the lid's sign, within span_deg, closer than rho_max): (the bin's centre t in
    degrees, the smallest rho minus the dome's outer radius there (r; negative: the dome reaches into the skin), the p
    in degrees where it is). A positive value is a gap: along that latitude the dome never meets the skin."""
    sgn = 1.0 if upper else -1.0
    span, bd = math.radians(span_deg), math.radians(bead_deg)
    nb = int(round(2 * t_max_deg / bin_deg))
    best: list = [None] * nb
    count = [0] * nb
    for rho, t, p in (tp if tp is not None else local_tp(pts)):
        pa = p * sgn
        if not (0.0 < pa < span and rho < rho_max):
            continue
        i = int(math.floor((math.degrees(t) + t_max_deg) / bin_deg))
        if not 0 <= i < nb:
            continue
        g = rho - (rho_out + bead * (1.0 - smoothstep(0.0, bd, pa)) + flare_at(pa, flare, t))
        count[i] += 1
        if best[i] is None or g < best[i][0]:
            best[i] = (g, pa)
    return [(round(-t_max_deg + (i + 0.5) * bin_deg, 1), b[0], round(math.degrees(b[1]), 1))
            for i, b in enumerate(best) if b is not None and count[i] >= min_pts]


def auto_flare(pts, rho_out: float, bead: float, upper: bool, base: dict = FLARE_OFF,
               margin: float = FLARE_MARGIN) -> dict:
    """The smallest flare (base's ramp; the amount in FLARE_STEP steps up to FLARE_MAX) with which lid_gap is at most
    -margin in every latitude bin; refuses when even FLARE_MAX leaves a gap."""
    tp = local_tp(pts)
    n = 0
    while True:
        f = dict(base, amount=round(n * FLARE_STEP, 4))
        gaps = lid_gap(None, rho_out, bead, upper, f, tp=tp)
        if not gaps or max(g for _, g, _ in gaps) <= -margin:
            return f
        n += 1
        if n * FLARE_STEP > FLARE_MAX + 1e-9:
            raise SystemExit(f"auto_flare: a gap is left at {FLARE_MAX} r: {gaps}")


# M10b: the static socket collar (brief UPDATE 14; the manager approved it for the case the flare showed at 80 %). The
# socket, unchanged, was shaped round M8b's eye unit (EYE_SCALE); a smaller unit leaves a crater ring bare, about 9 mm
# wide at 80 %, and the flare that closed it on the lids stood out as flanges at the eye corners (M10b/godot/sock80).
# The collar is a thin coral ring per design and side that belongs to the eye unit (alien_m6.build_collars:
# `eye_<design>_lid_collar_<side>`, a sibling of the ball, so it shows with its design and takes the lids' material;
# it neither blinks nor follows the gaze). It covers exactly the skin M8b's larger dome covered and the smaller one
# leaves bare: per azimuth round the eye's forward axis, in the (s, h) half-plane (s: the distance from the axis, h:
# along it, from the ball's centre), a flat elliptic tube from `tuck_in_mm` inside the dome's outline (s = rd, the lids'
# outer radius) to `tuck_mm` past the farthest skin point within `margin_mm` of M8b's dome (radius rd_ref), as a front
# view sees it. Where no bare crater shows (the skin meets the new dome, or falls away far behind it at the temple)
# the ring keeps `min_mm`, so it reads as one even rim round the eye (M10b/godot/sockc7: without it a lopsided disc
# on the nose side; with the deep crater followed, fins at the temple). The skin is never moved.
COLLAR = {"bins": 72, "margin_mm": 1.5, "h_back": 0.25, "fill_bins": 2, "grow": 1, "smooth": 2, "tuck_mm": 0.8,
          "tuck_in_mm": 3.5, "ds_mm": 0.5, "min_mm": 3.0, "flat": 0.45, "depth_max_mm": 3.0, "back": 0.3, "seg": 16}


def collar_gaps(pts, rd: float, rd_ref: float, c: dict = COLLAR) -> list:
    """pts: the skin's points (s, h, phi) in the eye's frame (m, m, radians; alien_m6 casts them from the front);
    per azimuth bin (gap, h) of the farthest
    bare crater point: outside the new outline (s > rd), within margin_mm of M8b's dome (|(s, h)| < rd_ref + margin)
    and not far behind (h > -h_back * rd); gap = its s - rd. None for a bin without such a point."""
    n, lim = c["bins"], rd_ref + c["margin_mm"] / 1000.0
    best = [None] * n
    for s, h, ph in pts:
        if s <= rd or math.hypot(s, h) > lim or h < -c["h_back"] * rd:
            continue
        i = int((ph + math.pi) / (2.0 * math.pi) * n) % n
        if best[i] is None or s > best[i][0]:
            best[i] = (s, h)
    return [None if b is None else (b[0] - rd, b[1]) for b in best]


def collar_smooth(gaps: list, c: dict = COLLAR) -> list:
    """The (gap, h) round the circle: an empty bin takes its nearest bin's within fill_bins (the skin's vertex spacing),
    else (0, 0) (no bare crater: the skin meets the new dome, or falls away far behind it); then the gap's max over
    +-grow bins and min_mm (no bin falls short of its own; the ring never thins out to nothing, so it reads as one
    even rim where the crater is narrow or deep), then a mean of both over +-smooth bins."""
    n = len(gaps)
    known = [i for i, g in enumerate(gaps) if g is not None]

    def circ(i, j):
        d = abs(i - j) % n
        return min(d, n - d)

    g = []
    for i in range(n):
        if gaps[i] is not None:
            g.append(gaps[i])
            continue
        j = min(known, key=lambda j: circ(i, j)) if known else None
        g.append(gaps[j] if j is not None and circ(i, j) <= c["fill_bins"] else (0.0, 0.0))
    w = [max([g[(i + j) % n][0] for j in range(-c["grow"], c["grow"] + 1)] + [c["min_mm"] / 1000.0]) for i in range(n)]
    k = c["smooth"]
    return [(sum(w[(i + j) % n] for j in range(-k, k + 1)) / (2 * k + 1),
             sum(g[(i + j) % n][1] for j in range(-k, k + 1)) / (2 * k + 1)) for i in range(n)]


def collar_section(gap: float, h_edge: float, rd: float, c: dict = COLLAR) -> tuple:
    """(centre, u, n, a, b) of the collar's elliptic section in the (s, h) half-plane: its long axis u from A = (rd -
    tuck_in, 0), inside the dome's outline down to about the ball (no dark slit between the lids' corners and the
    ring), to tuck past the crater's edge (rd + gap, h_edge); half-length a, half-depth
    b = flat * a (at least tuck, at most depth_max_mm) along n (u turned toward the front), the centre `back` * b
    behind the axis. A point is centre + a cos(t) u + b sin(t) n."""
    t, ti = c["tuck_mm"] / 1000.0, c["tuck_in_mm"] / 1000.0
    ax, ay = rd - ti, 0.0
    dx, dy = rd + gap - ax, h_edge - ay
    ln = math.hypot(dx, dy)
    u = (dx / ln, dy / ln)
    n = (-u[1], u[0])
    a = (ln + t) / 2.0
    b = min(max(c["flat"] * a, t), c["depth_max_mm"] / 1000.0)
    cen = (ax + a * u[0] - c["back"] * b * n[0], ay + a * u[1] - c["back"] * b * n[1])
    return cen, u, n, a, b
