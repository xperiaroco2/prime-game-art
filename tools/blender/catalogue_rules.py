"""The parts catalogue, part 3: compatibility measured pair by pair, with the assembler's own fits (docs/catalogue.md).

Seams (bottom x shoes at the ankles, top x bottom at the waist, head x top at the neck) are measured the way the
assembler builds them: the bottom goes through um/fit.py's tuck_cull first, then rays are cast at the seam like
um/fit.py's probe() (aimed at the LowerLeg, spine and Neck bone axes every 4 mm in 36 directions), in the rest pose and
in a walking pose. Hair x skull is measured with rays from outside toward the skull centre. A pair's verdict:

    ok, ok_tucked, ok_over   the seam is as clean as in the pack's own characters (below)
    needs_fix                an assembler fix makes it so, tried and measured: extend_edge (a hem or a neck moved
                             down), inflate (hair scaled off the skull)
    gap                      the parts do not meet (an opening; too far apart for extend_edge)
    poke                     one part shows through the other and no assembler fix removes it

The rays are judged against the pack's own outfits, because the pack's characters themselves show a few see-through
and poke-through rays at their seams (grazing rays, authored overlaps, skinning in motion): a pair passes when, in each
state, its counts are no higher than those of its references plus RAY_SLACK. The references of a pair are the pack
originals each of its parts belongs to (bottom x shoes: the bottom with its own shoes and the shoes with their own
bottom; hair x skull: the hair on its own skull). A pack original is its own reference and so always passes the rays.

At the ankles the verdict uses the rest pose only: in the walking pose the rays follow the shin while the shoe turns
with the foot, so the pack's own characters show 10 to 110 see-through rays there; the walk counts are recorded, with
whether they stay within the references'. The waist and the neck are judged in both states.
"""

import math

from mathutils import Vector

from um import fit, heads, poses, zones
from um.packs import reset_pose
from um.util import update

RAY_SLACK = 2  # rays a verdict tolerates above its references (the regression tolerance of docs/assembly.md)
GAP_MM = 5.0  # a vertical gap counted as "a gap" (the final test's threshold; whole millimetres, as it reported)
FIXABLE_MM = 30.0  # the largest vertical gap extend_edge is asked to close (beyond: the part is too short)
BEHIND = 0.015  # poke-through: the outer part's surface within this distance behind the inner part's (um/fit.py)
STATES = ({"name": "rest"}, {"name": "walk", "pose": {"action": "Walk", "frame": 6}})
HAIR_INFLATE = 0.006  # the assembler's inflate for shell hair on full skulls (docs/assembly.md)
ZFIGHT = 0.0005  # hair and skull surfaces closer than this along a ray z-fight
HOLE_ELEVATION = 20  # degrees above the skull centre from which a look into the skull counts as an open top
MEASURES = ("see_through", "poke")
HAIR_MEASURES = ("hole", "poke", "zfight")
ALL_STATES = tuple(st["name"] for st in STATES)
FIX_ROUNDS = 3  # extend_edge tries: the gap plus 10 mm, then 10 mm more each round


def r1(x):
    return round(x, 1)


def bvh(obj):
    return fit.bvh_of([("p", obj)])[0]


def spine_bone(arm, z):
    spans = [(s, (arm.matrix_world @ arm.data.bones[s].head_local).z, (arm.matrix_world @ arm.data.bones[s].tail_local).z)
             for s in fit.SPINE]
    return next((s for s, a, b in spans if a <= z < b), min(spans, key=lambda s: min(abs(z - s[1]), abs(z - s[2])))[0])


def seam_probe(arm, trees, bone, z0, z1, outer=None, dirs=36, step=0.004):
    """um/fit.py's probe() for one band and two parts {role: BVHTree}. Rays that miss or first hit a back face look
    through (see_through). Where the two parts lie in layers on a ray (the second surface within BEHIND of the first),
    the part hit first is the outer layer there: the outer part is the one given, else the one outer on most layered
    rays; a layered ray whose first hit is the other part is a poke-through. (Second hits farther away, such as the
    far side of the body, are not layers and are ignored.) Returns counts and the outer part."""
    rays = see = 0
    both = []
    z = z0
    while z <= z1 + 1e-9:
        c, dirf = fit.bone_ray_points(arm, bone or spine_bone(arm, z), z)
        for j in range(dirs):
            d = dirf(2 * math.pi * j / dirs)
            o = c - d * 0.5
            hits = sorted((h[3], k, h[1]) for k, t in trees.items() for h in [t.ray_cast(o, d, 0.55)] if h[0] is not None)
            rays += 1
            if not hits or hits[0][2].dot(d) > 0:
                see += 1
                continue
            if len(hits) > 1 and hits[1][1] != hits[0][1] and hits[1][0] - hits[0][0] < BEHIND:
                both.append(hits[0][1])
        z += step
    firsts = {k: both.count(k) for k in trees}
    if outer is None:
        outer = max(sorted(firsts), key=lambda k: firsts[k]) if both else sorted(trees)[0]
    poke = sum(1 for f in both if f != outer)
    return {"rays": rays, "see_through": see, "poke": poke, "outer": outer}


def set_state(arm, state):
    if "pose" in state:
        poses.apply(arm, state["pose"])
    else:
        rest(arm)


def rest(arm):
    reset_pose(arm)
    arm.data.pose_position = "REST"
    update()


def drop_for(overlap_mm):
    """extend_edge's drop: the gap plus 10 mm, in 5 mm steps (w1_ivy's hem took 20 mm, w2_nova's neck 15 mm)."""
    return math.ceil((max(0.0, -overlap_mm) + 10.0) / 5.0 - 1e-9) * 5.0 / 1000.0


class Job:
    """One pair's ray probe: parts {role: object}, bands [(bone or None, z0, z1, outer or None)] in rest heights."""

    def __init__(self, parts, bands):
        self.parts, self.bands, self.outer, self.probe = parts, bands, {}, {}


def run_jobs(arm, jobs):
    """Every job in every state: the rig is posed once per state and each object's BVH built once per state. The outer
    part of a band left open is decided in the first state (rest) and kept."""
    for st in STATES:
        set_state(arm, st)
        cache = {}
        for job in jobs:
            trees = {}
            for role, o in job.parts.items():
                if o.name not in cache:
                    cache[o.name] = bvh(o)
                trees[role] = cache[o.name]
            tot = {"rays": 0, "see_through": 0, "poke": 0}
            for i, (bone, z0, z1, outer) in enumerate(job.bands):
                p = seam_probe(arm, trees, bone, z0, z1, outer=job.outer.get(i, outer))
                job.outer[i] = p["outer"]
                for k in tot:
                    tot[k] += p[k]
            job.probe[st["name"]] = tot
    rest(arm)


def allowance(refs, states, measures=MEASURES):
    """Per state and measure: the highest count among the reference probes, plus RAY_SLACK."""
    return {st: {k: max([r[st][k] for r in refs] or [0]) + RAY_SLACK for k in measures} for st in states}


def passes(probe, allow, key):
    return all(probe[s][key] <= allow[s][key] for s in allow)


def judge(cell, refs, ok_word, states=None):
    """The verdict before a fix is tried: gap, try_fix, poke or ok_word (see the module doc)."""
    allow = allowance(refs, states or ALL_STATES)
    cell["allowance"] = allow
    cell["references"] = len(refs)
    if cell["overlap_mm"] < -FIXABLE_MM:
        return "gap"
    if cell["overlap_mm"] < 0 or not passes(cell["probe"], allow, "see_through"):
        return "try_fix"
    if not passes(cell["probe"], allow, "poke"):
        return "poke"
    return ok_word


class Fix:
    """An extend_edge try on a copy of one part of a pair; job(copy, drop) builds the probe of the moved pair."""

    def __init__(self, cell, copy, part, job):
        self.cell, self.copy, self.part, self.job, self.drop, self.moved = cell, copy, part, job, 0.0, 0


def fix_rounds(arm, fixes):
    """Up to FIX_ROUNDS extend_edge tries per pair (the gap plus 10 mm, then 10 mm more each time), each measured like
    the pair itself; the first that passes makes the verdict needs_fix. Else the last try decides: gap when it still
    sees through, poke when only poke-through remains (the opening closed but the moved edge crosses the other part).
    Every try is recorded in fix_tried.rounds."""
    pending = list(fixes)
    for rnd in range(FIX_ROUNDS):
        if not pending:
            break
        jobs = []
        for f in pending:
            d = drop_for(f.cell["overlap_mm"]) if rnd == 0 else 0.01
            f.moved = fit.extend_edge(f.copy, d)["vertices_moved"]
            f.drop = round(f.drop + d, 4)
            jobs.append(f.job(f.copy, f.drop))
        update()
        run_jobs(arm, jobs)
        still = []
        for f, job in zip(pending, jobs):
            allow = f.cell["allowance"]
            closes = passes(job.probe, allow, "see_through") and passes(job.probe, allow, "poke")
            rounds = f.cell.get("fix_tried", {}).get("rounds", []) + [{"drop_m": f.drop, "probe": job.probe}]
            f.cell["fix_tried"] = {"fix": "extend_edge", "part": f.part, "drop_m": f.drop, "vertices_moved": f.moved,
                                   "probe": job.probe, "closes": closes, "rounds": rounds}
            if closes:
                f.cell["verdict"] = "needs_fix"
                f.cell["fix"] = {"fix": "extend_edge", "part": f.part, "drop_m": f.drop}
            else:
                still.append(f)
        pending = still
    for f in pending:
        last = f.cell["fix_tried"]["probe"]
        f.cell["verdict"] = "poke" if passes(last, f.cell["allowance"], "see_through") else "gap"


def own(pid, slot):
    """The pack original's part of another slot: own("bottom_m_king", "shoes") is "shoes_m_king"."""
    _, g, char = pid.split("_", 2)
    return "%s_%s_%s" % (slot, g, char)


def twins(inv, pid):
    """pid and every part with the same mesh (same_geometry_as): their pack outfits are all references, so that equal
    parts get equal verdicts (the men's Adventurer and Worker trousers are one mesh)."""
    root = inv[pid].get("same_geometry_as", pid)
    return sorted(p for p, e in inv.items() if p == root or e.get("same_geometry_as") == root)


def ref_keys(inv, a, b, slot_a, slot_b):
    """The reference pairs of (a, b): a with the own slot_b part of each of its twins, and the own slot_a part of each
    of b's twins with b."""
    return [(a, own(t, slot_b)) for t in twins(inv, a)] + [(own(t, slot_a), b) for t in twins(inv, b)]


def ref_probes(by, keys):
    return [by[k]["probe"] for k in keys if k in by]


# ---------------------------------------------------------------- bottom x shoes (the ankles)

def ankle_bands(arm, legs):
    """Per leg, um/fit.py's probe() band: inside the shoe shaft where a tucked bottom must be hidden, else across the
    bottom's hem and the shoe's collar."""
    bands = []
    for side in ("L", "R"):
        foot = arm.matrix_world @ arm.data.bones["Foot." + side].head_local
        lg = legs[side]
        if lg["tucked"]:
            bands.append(("LowerLeg." + side, foot.z + 0.05, lg["collar_min_m"] - 0.004, "shoes"))
        else:  # the outer part (the bottom over the shoe, or the shoe over a bare leg) is decided by the rays
            z0 = min(lg["bottom_lower_edge_m"], lg["collar_max_m"]) - 0.01
            z1 = max(lg["bottom_lower_edge_m"], lg["collar_max_m"]) + 0.01
            bands.append(("LowerLeg." + side, z0, z1, None))
    return bands


def ankle_matrix(lib, g, inv, make_copy, remove):
    """Every bottom with every pair of shoes of body type g: tuck_cull on a copy of the bottom (as the assembler does),
    the ankle probe per leg in each state, the verdict against the pack originals; extend_edge tried where needed."""
    arm = lib.rigs[g]
    bots, shoes = lib.of("bottom", g), lib.of("shoes", g)
    cells, jobs, copies = [], [], []
    for bid in bots:
        for sid in shoes:
            b_seams, s_seams = inv[bid]["seams"], inv[sid]["seams"]
            legs = {}
            for side in ("L", "R"):
                lo = b_seams["leg_lower_edge_m"][side]
                col = s_seams["collar"][side]
                legs[side] = {"bottom_lower_edge_m": lo, "collar_min_m": col["min_m"], "collar_max_m": col["max_m"],
                              "overlap_mm": r1((col["max_m"] - lo) * 1000.0)}
            copy = make_copy(lib.parts[bid], "%s+%s" % (bid, sid))
            tuck = fit.tuck_cull(copy, lib.parts[sid], arm)
            for side in ("L", "R"):
                legs[side]["tucked"] = tuck[side]["tucked"]
                legs[side]["inside_fraction"] = tuck[side]["inside_fraction"]
            cells.append({"a": bid, "b": sid, "overlap_mm": min(v["overlap_mm"] for v in legs.values()), "legs": legs,
                          "faces_removed_by_tuck": tuck["faces_removed"]})
            jobs.append(Job({"bottom": copy, "shoes": lib.parts[sid]}, ankle_bands(arm, legs)))
            copies.append(copy)
    update()
    run_jobs(arm, jobs)
    by = {}
    for cell, job in zip(cells, jobs):
        cell["probe"] = job.probe
        cell["outer"] = "shoes" if all(job.outer[i] == "shoes" for i in job.outer) else "bottom"
        by[(cell["a"], cell["b"])] = cell
    fixes = []
    for cell, job, copy in zip(cells, jobs, copies):
        refs = ref_probes(by, ref_keys(inv, cell["a"], cell["b"], "bottom", "shoes"))
        tucked = any(v["tucked"] for v in cell["legs"].values()) or cell["outer"] == "shoes"
        cell["verdict"] = judge(cell, refs, "ok_tucked" if tucked else "ok_over", states=("rest",))
        walk = allowance(refs, ("walk",))
        cell["walk_within_references"] = passes(cell["probe"], walk, "see_through") and passes(cell["probe"], walk, "poke")
        if cell["verdict"] == "try_fix":
            fixes.append(Fix(cell, copy, "bottom", lambda c, d, cell=cell, shoes=job.parts["shoes"]: Job(
                {"bottom": c, "shoes": shoes},
                ankle_bands(arm, {s: dict(v, bottom_lower_edge_m=round(v["bottom_lower_edge_m"] - d, 4))
                                  for s, v in cell["legs"].items()}))))
    fix_rounds(arm, fixes)
    for copy in copies:
        remove(copy)
    return {"rows": bots, "cols": shoes, "cells": cells}


# ---------------------------------------------------------------- top x bottom (the waist)

def waist_job(top, bottom, t_lo, b_hi):
    return Job({"top": top, "bottom": bottom}, [(None, min(t_lo, b_hi) - 0.01, max(t_lo, b_hi) + 0.01, None)])


def waist_matrix(lib, g, inv, make_copy, remove):
    arm = lib.rigs[g]
    tops, bots = lib.of("top", g), lib.of("bottom", g)
    cells, jobs = [], []
    for tid in tops:
        for bid in bots:
            t_lo, b_hi = inv[tid]["seams"]["lower_edge_m"], inv[bid]["seams"]["upper_edge_m"]
            cells.append({"a": tid, "b": bid, "overlap_mm": r1((b_hi - t_lo) * 1000.0), "top_lower_edge_m": t_lo,
                          "bottom_upper_edge_m": b_hi})
            jobs.append(waist_job(lib.parts[tid], lib.parts[bid], t_lo, b_hi))
    run_jobs(arm, jobs)
    by = {}
    for cell, job in zip(cells, jobs):
        cell["probe"], cell["outer"] = job.probe, job.outer[0]
        by[(cell["a"], cell["b"])] = cell
    fixes = []
    for cell in cells:
        refs = ref_probes(by, ref_keys(inv, cell["a"], cell["b"], "top", "bottom"))
        cell["verdict"] = judge(cell, refs, "ok_over" if cell["outer"] == "top" else "ok_tucked")
        if cell["verdict"] == "try_fix":
            copy = make_copy(lib.parts[cell["a"]], "%s+%s" % (cell["a"], cell["b"]))
            fixes.append(Fix(cell, copy, "top", lambda c, d, cell=cell: waist_job(
                c, lib.parts[cell["b"]], cell["top_lower_edge_m"] - d, cell["bottom_upper_edge_m"])))
    fix_rounds(arm, fixes)
    for copy in [f.copy for f in fixes]:
        remove(copy)
    return {"rows": tops, "cols": bots, "cells": cells}


# ---------------------------------------------------------------- head x top (the neck)

def neck_job(head, top, h_lo, t_hi):
    return Job({"head": head, "top": top}, [("Neck", min(h_lo, t_hi) - 0.01, max(h_lo, t_hi) + 0.01, None)])


def neck_matrix(lib, g, inv, skulls, skull_objs, items, unique, make_copy, remove):
    """skulls: unique skull item ids; skull_objs[id]: that skull on rig g; unique: any skull id -> its unique id. The
    references: the skull with its own character's top (on its own body type) and the top with its own skull."""
    arm = lib.rigs[g]
    tops = lib.of("top", g)
    cells, jobs = [], []
    for sk in skulls:
        for tid in tops:
            h_lo, t_hi = items[sk]["neck_bottom_m"], inv[tid]["seams"]["neck_ring_top_m"]
            cells.append({"a": sk, "b": tid, "overlap_mm": r1((t_hi - h_lo) * 1000.0), "head_bottom_m": h_lo,
                          "top_neck_ring_m": t_hi})
            jobs.append(neck_job(skull_objs[sk], lib.parts[tid], h_lo, t_hi))
    run_jobs(arm, jobs)
    by = {}
    for cell, job in zip(cells, jobs):
        cell["probe"], cell["outer"] = job.probe, job.outer[0]
        by[(cell["a"], cell["b"])] = cell
    owners = {}  # unique skull id -> the characters whose head it is
    for sid, u in unique.items():
        owners.setdefault(u, []).append(sid.split("_", 2)[2] if sid.split("_")[1] == g.lower() else None)
    fixes = []
    for cell in cells:
        keys = [(cell["a"], "top_%s_%s" % (g.lower(), c)) for c in owners.get(cell["a"], []) if c]
        for t in twins(inv, cell["b"]):
            own_skull = unique.get("skull_%s_%s" % (g.lower(), t.split("_", 2)[2]))
            if own_skull:
                keys.append((own_skull, cell["b"]))
        cell["verdict"] = judge(cell, ref_probes(by, keys), "ok")
        if cell["verdict"] == "try_fix":
            copy = make_copy(skull_objs[cell["a"]], "%s+%s" % (cell["a"], cell["b"]))
            fixes.append(Fix(cell, copy, "head", lambda c, d, cell=cell: neck_job(
                c, lib.parts[cell["b"]], cell["head_bottom_m"] - d, cell["top_neck_ring_m"])))
    fix_rounds(arm, fixes)
    for copy in [f.copy for f in fixes]:
        remove(copy)
    return {"rows": skulls, "cols": tops, "cells": cells}


# ---------------------------------------------------------------- hair x skull

def sphere_dirs(elev_from=-30, elev_to=85, elev_step=5, az_step=10):
    out = [(90, Vector((0.0, 0.0, 1.0)))]
    for e in range(elev_from, elev_to + 1, elev_step):
        for a in range(0, 360, az_step):
            er, ar = math.radians(e), math.radians(a)
            out.append((e, Vector((math.cos(er) * math.sin(ar), -math.cos(er) * math.cos(ar), math.sin(er)))))
    return out


DIRS = sphere_dirs()


def skull_rays(hair_tree, skull_tree):
    """Rays from outside toward the skull centre (um/zones.py SKULL_CENTRE), every 10 degrees round and 5 degrees up
    from 30 below the centre's level to the crown. Per ray: covered (hair in front of the skull), zfight (hair and
    skull within ZFIGHT), poke (the skull in front of hair lying within 30 mm behind it: the skull cuts through),
    hole (from HOLE_ELEVATION up: no skull front face and no hair in front: a look into an open top), bare (skin)."""
    c = Vector(zones.SKULL_CENTRE)
    n = {"rays": 0, "covered": 0, "zfight": 0, "poke": 0, "hole": 0, "bare": 0}
    for elev, d in DIRS:
        o = c + d * 0.4
        ray = -d
        h = hair_tree.ray_cast(o, ray, 0.4)
        s = skull_tree.ray_cast(o, ray, 0.4)
        n["rays"] += 1
        s_front = s[0] is not None and s[1].dot(ray) < 0
        h_front = h[0] is not None and h[1].dot(ray) < 0
        if not s_front and not (h[0] is not None and (s[0] is None or h[3] < s[3])):
            n["hole" if elev >= HOLE_ELEVATION else "bare"] += 1  # into the skull, nothing in front
        elif not s_front:
            n["covered" if h_front or elev < HOLE_ELEVATION else "hole"] += 1
        elif h[0] is None:
            n["bare"] += 1
        elif s[3] < h[3] - ZFIGHT:
            n["poke" if h[3] - s[3] < 0.03 else "bare"] += 1
        elif abs(s[3] - h[3]) <= ZFIGHT:
            n["zfight"] += 1
        else:
            n["covered"] += 1
    return n


def hair_matrix(rigs, hairs, skulls_by_g, objs, items, unique, make_copy, remove):
    """Every unique hair on every unique skull of each body type (on that body type's rig, rest pose). The reference:
    the hair on its own skull (on its own rig); without one (or for a pack original) zero plus RAY_SLACK."""
    raw = {}
    for g, skulls in skulls_by_g.items():
        rest(rigs[g])
        trees = {i: bvh(objs[(i, g)]) for i in hairs + skulls}
        for h in hairs:
            for s in skulls:
                raw[(h, s, g)] = skull_rays(trees[h], trees[s])
    out = {}
    for g, skulls in skulls_by_g.items():
        cells = []
        for h in hairs:
            own_skull = unique.get("skull_" + h.split("_", 2)[1] + "_" + h.split("_")[2])
            ref = raw.get((h, own_skull, h.split("_")[1].upper()))
            for s in skulls:
                n = raw[(h, s, g)]
                cell = {"a": h, "b": s, "rays": n, "own_skull": own_skull}
                allow = {k: (ref[k] if ref and s != own_skull else 0) + RAY_SLACK for k in HAIR_MEASURES}
                if s == own_skull:
                    allow = {k: n[k] + RAY_SLACK for k in HAIR_MEASURES}  # a pack original is its own reference
                cell["allowance"] = allow
                bad = [k for k in HAIR_MEASURES if n[k] > allow[k]]
                if not bad:
                    cell["verdict"] = "ok"
                elif "hole" in bad:
                    cell["verdict"] = "gap"
                else:
                    copy = make_copy(objs[(h, g)], "%s+%s" % (h, s))
                    heads.inflate(copy, rigs[g], HAIR_INFLATE)
                    update()
                    n2 = skull_rays(bvh(copy), bvh(objs[(s, g)]))
                    remove(copy)
                    closes = all(n2[k] <= allow[k] for k in HAIR_MEASURES)
                    cell["fix_tried"] = {"fix": "inflate", "amount": HAIR_INFLATE, "rays": n2, "closes": closes}
                    cell["verdict"] = "needs_fix" if closes else "poke"
                    if closes:
                        cell["fix"] = {"fix": "inflate", "amount": HAIR_INFLATE}
                cells.append(cell)
        out[g] = {"rows": hairs, "cols": skulls, "cells": cells}
    return out
