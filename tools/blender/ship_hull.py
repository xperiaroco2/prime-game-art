"""The ship's EXTERIOR pieces (art #263, docs/ship.md): the EXTERIOR lane owns this file and ship_hull_*.py. Each
builder(args, layout) returns ship_lib parts in the piece's local frame (plan axes, metres; layouts/ship/exterior.toml
places them). Step 1: the greybox hull (the lofted core over the hall and corridors, open at its ends inside the tip
shells and at the mouth; the thin wing-tip plates), the tip shells with their window and corridor openings, the
ramp, legs, cockpit bubbles and nozzles; the lane replaces each with the worked-out piece."""

from __future__ import annotations

import math

import ship_lib as L

MODULES: list = []  # further exterior modules (ship_hull_*.py) the harness searches for builders


def _section(row: list, hull: dict) -> list[tuple[float, float]]:
    """A hull section's points (y, h) round its loop: front edge, bottom front, bottom back, back edge, top back,
    top front, and (core rows) the brow on the front slope."""
    _x, lead, trail, zl, top, c = row
    zb = hull["bottom_h"]
    if c < 0:  # the thin plate
        return [(lead, zl), (lead + 0.2, zb), (trail - 0.2, zb), (trail, zl), (trail - 0.3, top), (lead + 0.3, top)]
    pts = [(lead, zl), (lead + 0.25, zb), (trail - 0.25, zb), (trail, zl + 0.1), (c, top), (-c, top)]
    t = (hull["brow_h"] - zl) / (top - zl) if top > hull["brow_h"] + 0.05 else 0.5
    pts.append((lead + (-c - lead) * t, zl + (top - zl) * t))
    return pts


def _loft(rows: list, hull: dict, skip=None, cap_end: bool = False) -> tuple[list, list]:
    """Quads between consecutive sections (rows sorted by x); skip(i, j) leaves the strip j between rows i and i+1
    out; cap_end closes the last section with a fan. Faces turned outward from the sections' centre line."""
    secs = [[(row[0], y, h) for y, h in _section(row, hull)] for row in rows]
    n = len(secs[0])
    verts = [p for s in secs for p in s]
    faces = []
    for i in range(len(secs) - 1):
        for j in range(n):
            if skip and skip(i, j):
                continue
            a, b = i * n + j, i * n + (j + 1) % n
            faces.append((a, b, b + n, a + n))
    if cap_end:
        last = len(secs) - 1
        cx = secs[-1][0][0]
        verts.append((cx, sum(p[1] for p in secs[-1]) / n, sum(p[2] for p in secs[-1]) / n))
        faces += [(last * n + j, last * n + (j + 1) % n, len(verts) - 1) for j in range(n)]
    mids = {round(s[0][0], 6): (sum(p[1] for p in s) / n, sum(p[2] for p in s) / n) for s in secs}

    def inner(c: tuple) -> tuple:
        x = min(mids, key=lambda k: abs(k - c[0]))
        if cap_end and abs(c[0] - secs[-1][0][0]) < 1e-6:
            x0 = secs[-2][0][0]  # a cap face: inside lies back toward the previous section
            return (x0, *mids[round(x0, 6)])
        return (c[0], *mids[x])
    return verts, L.orient(verts, faces, inner)


def hull_core(args: dict, layout: dict) -> list:
    hull = layout["hull"]
    half = [r for r in hull["core"] if r[0] > 0]
    rows = [[-r[0], *r[1:]] for r in reversed(half)] + [r for r in hull["core"] if r[0] == 0] + half
    mouth = hull["mouth_half_width_m"] + 1e-6
    n = len(_section(rows[0], hull))

    def skip(i: int, j: int) -> bool:  # the lower front strip (brow to front edge) over the mouth
        return j == n - 1 and abs(rows[i][0]) <= mouth and abs(rows[i + 1][0]) <= mouth
    return [L.part("hull_core", *_loft(rows, hull, skip), "hull_silver", solid=False)]


def hull_tip(args: dict, layout: dict) -> list:
    hull = layout["hull"]
    side = float(args.get("side", 1.0))
    rows = [[side * r[0], *r[1:]] for r in sorted(hull["plate"], key=lambda r: r[0])]
    v, f = _loft(rows, hull, cap_end=True)
    return [L.part("hull_tip", v, f, "hull_silver", solid=False)]


def tip_shell(args: dict, layout: dict) -> list:
    """The tip room's outer shell (facing east), open at the window and where the corridor comes in, with a cap."""
    hull, deck = layout["hull"], layout["deck"]
    room = next(r for r in layout["rooms"] if r["id"] == "tip_e")
    cor = next(r for r in layout["rooms"] if r["id"] == "corridor_e")
    win, floor, wall = room["window"], deck["floor_h"], deck["wall_m"]
    r, n = hull["pod_radius_m"], 48
    window_half = math.radians(win["half_angle_deg"])
    cor_half = math.asin(min(0.99, ((cor["y"][1] - cor["y"][0]) / 2 + wall + 0.05) / r))
    cor_top = floor + cor["clear_h"] + wall
    top = floor + room["clear_h"] + wall
    rows = sorted({0.9, floor + win["sill_h"], floor + win["head_h"], cor_top, top})
    a = L.angles(-math.pi, math.pi, math.radians(7.5), (-window_half, window_half, math.pi - cor_half,
                                                         -math.pi + cor_half))
    verts, faces = [], []
    for a0, a1 in zip(a, a[1:]):
        mid = (a0 + a1) / 2
        for h0, h1 in zip(rows, rows[1:]):
            if abs(mid) < window_half and h0 >= floor + win["sill_h"] - 1e-6 and h1 <= floor + win["head_h"] + 1e-6:
                continue
            if abs(abs(mid) - math.pi) < cor_half and h1 <= cor_top + 1e-6:
                continue
            k = len(verts)
            verts += [(r * math.cos(a0), r * math.sin(a0), h0), (r * math.cos(a1), r * math.sin(a1), h0),
                      (r * math.cos(a1), r * math.sin(a1), h1), (r * math.cos(a0), r * math.sin(a0), h1)]
            faces.append((k, k + 1, k + 2, k + 3))
        k = len(verts)
        verts += [(r * math.cos(a0), r * math.sin(a0), top), (r * math.cos(a1), r * math.sin(a1), top),
                  (0.0, 0.0, top + 0.45)]
        faces.append((k, k + 1, k + 2))
    faces = L.orient(verts, faces, lambda c: (0.0, 0.0, min(c[2], top) - (0.5 if c[2] >= top - 1e-6 else 0.0)))
    return [L.part("tip_shell", verts, faces, "hull_silver", solid=False)]


def ramp(args: dict, layout: dict) -> list:
    """The mouth ramp from its hinge (the local origin, at floor height) down north to its foot on the ground."""
    rp, deck = layout["ramp"], layout["deck"]
    run = rp["hinge"][1] - rp["foot"][1]
    hw, t = rp["width_m"] / 2, rp["thickness_m"]
    top = [(-hw, 0.0, deck["floor_h"]), (hw, 0.0, deck["floor_h"]), (hw, -run, deck["ground_h"]),
           (-hw, -run, deck["ground_h"])]
    v = top + [(x, y, h - t) for x, y, h in top]
    f = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    return [L.part("ramp", v, f, "floor_grate")]


def leg(args: dict, layout: dict) -> list:
    top = layout["hull"]["bottom_h"] + 0.05
    strut = L.disc(0.16, 12, 0.08, top)
    pad = L.disc(0.45, 12, 0.0, 0.08)
    return [L.part("leg_strut", *strut, "leg_metal"), L.part("leg_pad", *pad, "hull_dark")]


def bubble(args: dict, layout: dict) -> list:
    return [L.part("bubble", *L.sphere(0.8, 8, 16), "glass_tint")]


def nozzle(args: dict, layout: dict) -> list:
    body = L.cylinder_y(0.7, 20, -0.3, 1.1)
    ring = L.cylinder_y(0.74, 20, 0.95, 1.12)
    return [L.part("nozzle_body", *body, "hull_dark"), L.part("nozzle_ring", *ring, "glow_cyan")]
