"""The ship's INTERIOR pieces (art #263, docs/ship.md): the INTERIOR lane owns this file and ship_interior_*.py.
Each builder(args, layout) returns ship_lib parts in the piece's local frame (plan axes, metres; the placement in
layouts/ship/interior.toml moves and turns it). Step 1: the greybox shell (floors, walls with their openings, ceilings,
the tip windows); the lane replaces each builder with the worked-out piece and adds the detail pieces."""

from __future__ import annotations

import math

import ship_lib as L

MODULES: list = []  # further interior modules (ship_interior_*.py) the harness searches for builders
STEP = math.radians(7.5)


def _room(layout: dict, rid: str) -> dict:
    return next(r for r in layout["rooms"] if r["id"] == rid)


def _deck(layout: dict) -> tuple[float, float, float]:
    d = layout["deck"]
    return d["floor_h"], d["slab_m"], d["wall_m"]


# --- the hall ------------------------------------------------------------------------------------------------------
def hall_floor(args: dict, layout: dict) -> list:
    floor, slab, wall = _deck(layout)
    r = _room(layout, "hall")["radius"] + wall
    return [L.part("hall_floor", *L.disc(r, 48, floor - slab, floor), "floor_grate")]


def _openings(layout: dict, radius: float) -> list[tuple[float, float, float]]:
    """(angle, half-angle, opening height) of the hall's openings: the mouth (north) and both corridors."""
    out = []
    for rid in ("mouth", "corridor_w", "corridor_e"):
        r = _room(layout, rid)
        if rid == "mouth":
            centre, half = -math.pi / 2, (r["x"][1] - r["x"][0]) / 2
        else:
            centre, half = (0.0 if r["x"][0] > 0 else math.pi), (r["y"][1] - r["y"][0]) / 2
        out.append((centre, math.asin(half / radius), r["clear_h"]))
    return out


def _off(a: float, b: float) -> float:
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def hall_wall(args: dict, layout: dict) -> list:
    floor, _slab, wall = _deck(layout)
    room = _room(layout, "hall")
    r = room["radius"]
    gaps = _openings(layout, r)
    cuts = tuple(c + s * h for c, h, _ in gaps for s in (-1, 1))
    cuts = tuple(((c + math.pi) % (2 * math.pi)) - math.pi for c in cuts)
    top = max(g[2] for g in gaps)
    rows = [floor, floor + top, floor + room["clear_h"]]

    def skip(a: float, h0: float, h1: float) -> bool:
        return any(_off(a, c) < half and h1 <= floor + height + 1e-6 for c, half, height in gaps)
    return [L.part("hall_wall", *L.ring(r, r + wall, rows, STEP, skip, cuts), "wall_panel")]


def hall_ceiling(args: dict, layout: dict) -> list:
    floor, _slab, wall = _deck(layout)
    room = _room(layout, "hall")
    return [L.part("hall_ceiling", *L.dome(room["radius"] + wall, 16, floor + room["clear_h"], floor + room["apex_h"],
                                           0.12), "ceiling")]


# --- the mouth passage ---------------------------------------------------------------------------------------------
def _mouth(layout: dict) -> tuple[float, float, float]:
    r = _room(layout, "mouth")
    return (r["x"][1] - r["x"][0]) / 2, (r["y"][1] - r["y"][0]) / 2, r["clear_h"]


def mouth_floor(args: dict, layout: dict) -> list:
    floor, slab, wall = _deck(layout)
    hx, hy, _ = _mouth(layout)
    return [L.part("mouth_floor", *L.box(-hx - wall, hx + wall, -hy, hy, floor - slab, floor), "floor_grate")]


def mouth_wall(args: dict, layout: dict) -> list:
    floor, _slab, wall = _deck(layout)
    _hx, hy, h = _mouth(layout)
    return [L.part("mouth_wall", *L.box(-wall / 2, wall / 2, -hy, hy, floor, floor + h), "wall_panel")]


def mouth_ceiling(args: dict, layout: dict) -> list:
    floor, _slab, wall = _deck(layout)
    hx, hy, h = _mouth(layout)
    return [L.part("mouth_ceiling", *L.box(-hx - wall, hx + wall, -hy, hy, floor + h, floor + h + wall), "ceiling")]


# --- the wing corridors (one piece set, placed on both sides) -------------------------------------------------------
def _corridor(layout: dict) -> tuple[float, float, float]:
    r = _room(layout, "corridor_e")
    return (r["x"][1] - r["x"][0]) / 2, (r["y"][1] - r["y"][0]) / 2, r["clear_h"]


def corridor_floor(args: dict, layout: dict) -> list:
    floor, slab, wall = _deck(layout)
    hx, hy, _ = _corridor(layout)
    return [L.part("corridor_floor", *L.box(-hx, hx, -hy - wall, hy + wall, floor - slab, floor), "floor_grate")]


def corridor_wall(args: dict, layout: dict) -> list:
    floor, _slab, wall = _deck(layout)
    hx, _hy, h = _corridor(layout)
    return [L.part("corridor_wall", *L.box(-hx, hx, -wall / 2, wall / 2, floor, floor + h), "wall_panel")]


def corridor_ceiling(args: dict, layout: dict) -> list:
    floor, _slab, wall = _deck(layout)
    hx, hy, h = _corridor(layout)
    return [L.part("corridor_ceiling", *L.box(-hx, hx, -hy - wall, hy + wall, floor + h, floor + h + wall), "ceiling")]


# --- the tip rooms (built facing east: window at angle 0, the corridor at 180; the west one is turned 180) ----------
def tip_floor(args: dict, layout: dict) -> list:
    floor, slab, wall = _deck(layout)
    return [L.part("tip_floor", *L.disc(_room(layout, "tip_e")["radius"] + wall, 40, floor - slab, floor),
                   "floor_grate")]


def tip_wall(args: dict, layout: dict) -> list:
    floor, _slab, wall = _deck(layout)
    room = _room(layout, "tip_e")
    win = room["window"]
    r = room["radius"]
    _hx, chy, ch = _corridor(layout)
    corridor_half = math.asin(chy / r)
    window_half = math.radians(win["half_angle_deg"])
    rows = sorted({floor, floor + win["sill_h"], floor + win["head_h"], floor + ch, floor + room["clear_h"]})
    cuts = (-window_half, window_half, math.pi - corridor_half, -math.pi + corridor_half)

    def skip(a: float, h0: float, h1: float) -> bool:
        in_window = abs(a) < window_half and h0 >= floor + win["sill_h"] - 1e-6 and h1 <= floor + win["head_h"] + 1e-6
        in_corridor = _off(a, math.pi) < corridor_half and h1 <= floor + ch + 1e-6
        return in_window or in_corridor
    return [L.part("tip_wall", *L.ring(r, r + wall, rows, STEP, skip, cuts), "wall_panel")]


def tip_ceiling(args: dict, layout: dict) -> list:
    floor, _slab, wall = _deck(layout)
    room = _room(layout, "tip_e")
    return [L.part("tip_ceiling", *L.dome(room["radius"] + wall, 16, floor + room["clear_h"], floor + room["apex_h"],
                                          0.12), "ceiling")]


def tip_window(args: dict, layout: dict) -> list:
    floor, _slab, wall = _deck(layout)
    room = _room(layout, "tip_e")
    win = room["window"]
    half = math.radians(win["half_angle_deg"])
    r = room["radius"] + wall * 0.4
    a = L.angles(-half, half, STEP)
    blocks = [L.sector(r, r + 0.03, a0, a1, floor + win["sill_h"], floor + win["head_h"]) for a0, a1 in zip(a, a[1:])]
    return [L.part("tip_window", *L.merge(*blocks), "glass")]
