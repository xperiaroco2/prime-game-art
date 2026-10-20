"""The thumb's skin weights (art #196, M10b and its review): a smooth blend along the thumb's length.

The engineer on v30: "the thumb at rest (Idle) looks bugged, too big". The cause (measured on M10's kit,
`tools/out/m10b/thumb_var.py`): since S8b the mesh's thumb leaves the palm's front side and points forward along the
hand (`alien_cage.THUMB_DIR`), 5 to 7 cm off its bones, which run down from the wrist. The cage weights its rings by
segment along the mesh (Metacarpal at the root, then Proximal, then Distal at the tip, each ring on one or two bones),
as if the mesh's joints were the bones'. The clips turn the thumb's bones about their own heads (Idle: Metacarpal
11.9, Proximal 25.5, Distal 8.8 degrees; Walk: Distal 86.8), so each ring swings about a pivot 5 to 7 cm away and by a
different turn than its neighbour: the tube stretches (Idle: the thumb's edges up to 2.2 times their rest length, the
thumb 10 % larger; Walk 23 %) and reads swollen, as long as the hand.

M10b's first cure put every thumb vertex's thumb weight on the Metacarpal (0.7) and the Hand (0.3): no stretch, but
the thumb became a straight bar in fists and grips (PR #245's review, major 1). The fix here keeps the cure's two
parts (a Hand share that damps the far pivots, and no ring-by-ring steps) and gives the bend back: each thumb vertex's
thumb weight t is split by its position u along the thumb (`axis_params`: 0 at the root blend, 1 at the tip, the
vertex projected on the root-to-tip axis of the mesh's thumb; the bones' chain mapped onto that length, never the
distance to the nearest bone, which is 5 to 7 cm for every ring), `shares(u)`: HAND on the Hand everywhere, a
Proximal share growing smoothly over PROXIMAL's span, a Distal share over DISTAL's, the rest on the Metacarpal. The
shares change slowly along the tube, so neighbouring rings move alike (no stretch), and the tip follows the Proximal
and Distal turns part-way (the curl).

The cage's own segment weights stay the texture and sculpt masks: `apply` stores them per vertex in the point
attributes `CAGE_ATTR` (never exported: export_glb leaves `export_attributes` off), and `cage_view` gives a vertex's
weights back as the cage had them; `alien_texture.group_weights` reads them (the thumb tip's warm tint).
`alien_m6.py` applies this to the kit it exports and marks the Body with `MARKER`.
"""
from __future__ import annotations

import json

SEGMENTS = ("Metacarpal", "Proximal", "Distal")
# The shares, picked from a grid on M10's kit (the left thumb; size = the thumb vertices' largest distance from their
# centre in the Hand's frame against rest, over eight phases of each clip; bend = the turn between the thumb's
# base-to-middle and middle-to-tip against rest): Idle 1.026, Walk 1.029, the fist (alien_cage_review.curl 70/60)
# bends 22 degrees, a grip (45/40) 13; M10b's 0.7/0.3 split: 1.025, 1.025, 6 and 3 degrees; the cage's: 1.103,
# 1.227. A Distal share from mid-thumb on, or a smaller Hand share, swelled Walk past 1.035 (its Distal turns 87 deg).
HAND = 0.6  # of the thumb's weight on the Hand, along the whole thumb (M10b's damping of the far pivots)
PROXIMAL = (0.1, 0.6, 0.2)  # the Proximal share: from u, to u, the share reached (smoothstep between)
DISTAL = (0.6, 1.0, 0.2)  # the Distal share, the same form: the tip's curl
MARKER = "prime_thumb"
CAGE_ATTR = "prime_cage_{}"  # + "ThumbMetacarpal" | "ThumbProximal" | "ThumbDistal" | "Hand": the cage's weights
CAGE_KEYS = tuple(f"Thumb{s}" for s in SEGMENTS) + ("Hand",)
ROOT_T = (0.35, 0.65)  # the root blend: vertices whose thumb weight is in this range give the axis's root


def _smooth(a: float, b: float, x: float) -> float:
    s = min(1.0, max(0.0, (x - a) / (b - a)))
    return s * s * (3.0 - 2.0 * s)


def shares(u: float) -> dict[str, float]:
    """The split of a thumb vertex's thumb weight at u (0 root, 1 tip): {"Hand", "Metacarpal", "Proximal", "Distal"}."""
    p = PROXIMAL[2] * _smooth(PROXIMAL[0], PROXIMAL[1], u)
    d = DISTAL[2] * _smooth(DISTAL[0], DISTAL[1], u)
    return {"Hand": HAND, "Metacarpal": 1.0 - HAND - p - d, "Proximal": p, "Distal": d}


def blend(weights: dict[str, float], side: str, u: float) -> dict[str, float]:
    """One vertex's weights {group: w} with its side's thumb weight t split by shares(u) (other groups untouched)."""
    names = [f"{side}Thumb{s}" for s in SEGMENTS]
    t = sum(weights.get(n, 0.0) for n in names)
    if t <= 0.0:
        return dict(weights)
    out = {k: w for k, w in weights.items() if k not in names}
    sh = shares(u)
    for s, n in zip(SEGMENTS, names):
        if sh[s] * t > 0.0:
            out[n] = sh[s] * t
    out[f"{side}Hand"] = out.get(f"{side}Hand", 0.0) + sh["Hand"] * t
    return out


def axis_params(points: list, totals: list) -> list[float]:
    """Per thumb vertex (rest positions, thumb weights t) its u: the projection on the axis from the root blend's
    centre (ROOT_T) to the vertex farthest from it, as a fraction of that axis, clamped to 0..1."""
    root_pts = [p for p, t in zip(points, totals) if ROOT_T[0] <= t <= ROOT_T[1]] or \
        [p for p, t in zip(points, totals) if t == min(totals)]
    root = [sum(c) / len(root_pts) for c in zip(*root_pts)]
    d2 = [sum((a - b) ** 2 for a, b in zip(p, root)) for p in points]
    tip = max((d, i) for i, d in enumerate(d2) if totals[i] > 0.5)[1] if any(t > 0.5 for t in totals) else \
        max(range(len(points)), key=d2.__getitem__)
    ax = [a - b for a, b in zip(points[tip], root)]
    n2 = sum(a * a for a in ax) or 1.0
    return [min(1.0, max(0.0, sum((a - b) * c for a, b, c in zip(p, root, ax)) / n2)) for p in points]


def cage_view(weights: dict[str, float], side: str, stored: dict[str, float]) -> dict[str, float]:
    """A vertex's weights as the cage had them: its side's thumb groups and Hand from `stored` ({CAGE_KEYS: w},
    as apply() kept them), every other group as it is now."""
    keys = {f"{side}{k}" for k in CAGE_KEYS}
    out = {k: w for k, w in weights.items() if k not in keys}
    for k in CAGE_KEYS:
        if stored.get(k, 0.0) > 0.0:
            out[f"{side}{k}"] = stored[k]
    return out


def stored(obj) -> dict | None:
    """{vertex index: {CAGE_KEYS: w}} of a mesh object apply() ran on (the vertices it changed), else None."""
    if MARKER not in obj.keys():
        return None
    attrs = [obj.data.attributes.get(CAGE_ATTR.format(k)) for k in CAGE_KEYS]
    if any(a is None for a in attrs):
        return None
    vals = [[d.value for d in a.data] for a in attrs]
    return {i: dict(zip(CAGE_KEYS, row)) for i, row in enumerate(zip(*vals)) if any(x > 0.0 for x in row[:3])}


def side_of(weights: dict[str, float]) -> str | None:
    """The side whose thumb groups a vertex has (None: no thumb weight)."""
    for side in ("Left", "Right"):
        if any(weights.get(f"{side}Thumb{s}", 0.0) > 0.0 for s in SEGMENTS):
            return side
    return None


def apply(obj) -> dict:
    """The blended thumb on a skinned Blender mesh object's vertex groups, both sides, once (the marker); the cage's
    weights kept in the CAGE_ATTR point attributes."""
    if MARKER in obj.keys():
        return {"skipped": "already applied", **json.loads(obj[MARKER])}
    groups = {g.name: g for g in obj.vertex_groups}
    index = {g.index: g.name for g in obj.vertex_groups}
    me = obj.data
    keep = {k: [0.0] * len(me.vertices) for k in CAGE_KEYS}
    moved = 0
    for side in ("Left", "Right"):
        names = [f"{side}Thumb{s}" for s in SEGMENTS] + [f"{side}Hand"]
        if any(n not in groups for n in names):
            raise SystemExit(f"alien_thumb: {obj.name} has no {[n for n in names if n not in groups]}")
        verts, ws = [], []
        for v in me.vertices:
            w = {index[g.group]: g.weight for g in v.groups}
            if any(w.get(f"{side}Thumb{s}", 0.0) > 0.0 for s in SEGMENTS):
                verts.append(v)
                ws.append(w)
        totals = [sum(w.get(f"{side}Thumb{s}", 0.0) for s in SEGMENTS) for w in ws]
        us = axis_params([tuple(v.co) for v in verts], totals)
        for v, w, u in zip(verts, ws, us):
            for k in CAGE_KEYS:
                keep[k][v.index] = w.get(f"{side}{k}", 0.0)
            new = blend(w, side, u)
            for n in names:
                if n in new:
                    groups[n].add([v.index], new[n], "REPLACE")
                elif n in w:
                    groups[n].remove([v.index])
            moved += 1
    for k, vals in keep.items():
        name = CAGE_ATTR.format(k)
        if name in me.attributes:
            me.attributes.remove(me.attributes[name])
        me.attributes.new(name, "FLOAT", "POINT").data.foreach_set("value", vals)
    rep = {"hand": HAND, "proximal": list(PROXIMAL), "distal": list(DISTAL), "vertices": moved}
    obj[MARKER] = json.dumps(rep, sort_keys=True)
    return rep
