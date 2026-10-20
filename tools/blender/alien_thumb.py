"""The thumb's skin weights (art #196, M10b): the thumb moves as one piece with its metacarpal, part-way.

The engineer on v30: "the thumb at rest (Idle) looks bugged, too big". The cause (measured on M10's kit,
`tools/out/m10b/thumb_var.py`): since S8b the mesh's thumb leaves the palm's front side and points forward along the
hand (`alien_cage.THUMB_DIR`), 5 to 7 cm off its bones, which run down from the wrist. The cage weights its rings by
segment along the mesh (Metacarpal at the root, then Proximal, then Distal at the tip), as if the mesh's joints were
the bones'. The clips turn the thumb's bones about their own heads (Idle: Metacarpal 11.9, Proximal 25.5, Distal 8.8
degrees; Walk: Distal 86.8), so each ring swings about a pivot 5 to 7 cm away and by a different turn than its
neighbour: the tube stretches (Idle: the thumb's edges up to 2.2 times their rest length, 1.55 at the 99th
percentile, the thumb 10 % larger; Walk 2.65 and 23 %) and reads swollen, as long as the hand. M7's 1.2 times longer
thumb lengthened the lever.

The fix keeps the mesh, the skeleton and the clips: every thumb vertex's Metacarpal + Proximal + Distal weight t
becomes `METACARPAL * t` on the Metacarpal and `HAND * t` more on the Hand. The thumb past its root then moves as one
piece (no stretch along it), a little less than the metacarpal turns, and the stretch left is at the root's blend into
the palm (Idle: 1.7 max, 1.29 at the 99th percentile, the thumb 2.5 % larger). The cage's segment weights stay the
texture and sculpt masks (`alien_texture`'s warm finger tips, `alien_detail`'s hand mask), so the skin is unchanged;
`alien_m6.py` applies this to the kit it exports and marks the Body with `MARKER`.
"""
from __future__ import annotations

import json

SEGMENTS = ("Metacarpal", "Proximal", "Distal")
METACARPAL = 0.7  # of the thumb's weight on its Metacarpal
HAND = 0.3  # of the thumb's weight moved onto the Hand
MARKER = "prime_thumb"


def rigid(weights: dict[str, float], side: str) -> dict[str, float]:
    """One vertex's weights {group: w} with its side's thumb weight moved as above (other groups untouched)."""
    names = [f"{side}Thumb{s}" for s in SEGMENTS]
    t = sum(weights.get(n, 0.0) for n in names)
    if t <= 0.0:
        return dict(weights)
    out = {k: w for k, w in weights.items() if k not in names}
    out[names[0]] = METACARPAL * t
    out[f"{side}Hand"] = out.get(f"{side}Hand", 0.0) + HAND * t
    return out


def apply(obj) -> dict:
    """The rigid thumb on a skinned Blender mesh object's vertex groups, both sides, once (the marker)."""
    if MARKER in obj.keys():
        return {"skipped": "already applied", **json.loads(obj[MARKER])}
    groups = {g.name: g for g in obj.vertex_groups}
    index = {g.index: g.name for g in obj.vertex_groups}
    moved = 0
    for side in ("Left", "Right"):
        names = [f"{side}Thumb{s}" for s in SEGMENTS] + [f"{side}Hand"]
        if any(n not in groups for n in names):
            raise SystemExit(f"alien_thumb: {obj.name} has no {[n for n in names if n not in groups]}")
        for v in obj.data.vertices:
            w = {index[g.group]: g.weight for g in v.groups}
            if not any(f"{side}Thumb{s}" in w for s in SEGMENTS):
                continue
            new = rigid(w, side)
            for n in names:
                if n in new:
                    groups[n].add([v.index], new[n], "REPLACE")
                elif n in w:
                    groups[n].remove([v.index])
            moved += 1
    rep = {"metacarpal": METACARPAL, "hand": HAND, "vertices": moved}
    obj[MARKER] = json.dumps(rep, sort_keys=True)
    return rep
