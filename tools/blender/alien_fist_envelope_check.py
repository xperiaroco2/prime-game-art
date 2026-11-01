"""The envelope route's self-check (art #196, Hands H1l), run inside Blender for its numpy by
tools/tests/test_alien_fist_envelope_blender.py; prints one line `ENVELOPE_CHECK {json}`.

On synthetic shapes: the round cone's field against brute force; the iso-mesh of a two-finger envelope (closed,
facing out, on the field); the shrink-wrap of two separate tubes onto their merged envelope, first bare (the facing
sides bunch and fold) and then relaxed (no fold, no short edge); a triangle turned over counts as folded; H1q's
contact corrective on two tubes apart (the gap fills under the cap, no fold) and touching (their facing sides sink);
H1r's local zone (its own cap on a part of the tubes, the rest under the global cap)."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_fist_envelope as E  # noqa: E402

out = {}
rng = np.random.default_rng(7)

# the round cone against a brute-force distance to its swept spheres (outside points)
a, b, r1, r2 = np.array([0.0, 0, 0]), np.array([0.03, 0.01, 0]), 0.008, 0.005
P = rng.uniform(-0.03, 0.06, (400, 3))
ts = np.linspace(0, 1, 4001)
C = a + np.outer(ts, b - a)
Rs = r1 + (r2 - r1) * ts
brute = (np.linalg.norm(P[:, None, :] - C[None], axis=2) - Rs[None]).min(axis=1)
d = E.round_cone(P, a, b, r1, r2)
outside = brute > 0.001
out["cone_err_mm"] = float(np.abs(d[outside] - brute[outside]).max() * 1000)


def tube(x0, y0, z0, z1, r):
    return [((x0, y0, z0), r), ((x0, y0, z1), r)]


# two fingers 20 mm apart (radius 8 mm: a 4 mm gap), one envelope over k = 10 mm, the core off, no palm, no thumb
digits = {"A": tube(0, 0, 0, 0.05, 0.008), "B": tube(0.020, 0, 0, 0.05, 0.008)}
env = E.Envelope(digits, "Thumb", None, k=0.010, k_core=0.0, k_thumb=0.0, core=0.0)
V, T = E.iso_mesh(env.sd, (-0.02, -0.02, -0.02), (0.04, 0.02, 0.07), 0.0015)
edges = np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), axis=1)
_, counts = np.unique(edges, axis=0, return_counts=True)
vol = float(np.einsum("ij,ij->i", V[T[:, 0]], np.cross(V[T[:, 1]], V[T[:, 2]])).sum() / 6)
out["iso"] = {"verts": int(len(V)), "tris": int(len(T)), "open_edges": int((counts != 2).sum()),
              "volume_cm3": vol * 1e6, "off_mm": float(np.abs(env.sd(V)).max() * 1000),
              "groove_mm": float(-env.sd(np.array([[0.010, 0.0, 0.025]]))[0] * 1000)}

# two separate tubes (iso-meshed with no blend) wrapped onto the merged envelope: closed meshes, nothing pinned
sep = E.Envelope(digits, "Thumb", None, k=0.0, k_core=0.0, k_thumb=0.0, core=0.0)
# one mesh: the two tubes joined by a thin bridge at their root, as two fingers on a palm
bridge = E.Envelope({"A": tube(0, 0, 0, 0.05, 0.008), "B": tube(0.020, 0, 0, 0.05, 0.008),
                     "W": [((0.0, 0, -0.004), 0.009), ((0.020, 0, -0.004), 0.009)]}, "Thumb", None, k=0.0,
                    k_core=0.0, k_thumb=0.0, core=0.0)
V2, T2 = E.iso_mesh(bridge.sd, (-0.02, -0.02, -0.025), (0.04, 0.02, 0.07), 0.002)
e2 = E.edges_of(T2)
w = np.ones(len(V2))
full = w >= 0.999
bare = E.metrics(env, env.project(V2, 12), T2, full)
X, st = E.wrap(env, V2, w, e2, rounds=300, lam=0.5, tris=T2)
relaxed = E.metrics(env, X, T2, full)
out["wrap"] = {"bare": bare, "relaxed": relaxed, "stats": st}

# a pinned rim stays where it is: wrap with the lowest ring pinned
w3 = np.where(V2[:, 2] < -0.008, 0.0, 1.0)
X3, _ = E.wrap(env, V2, w3, e2, rounds=50, lam=0.5)
out["pinned_moved_mm"] = float(np.linalg.norm(X3[w3 == 0] - V2[w3 == 0], axis=1).max() * 1000)

# press: the same two tubes inflated into contact and clipped at their bisector; each vertex follows its own tube
press = E.Envelope(digits, "Thumb", None, core=0.0, mode="press", inflate=1.3, gap=0.0004, lip=0.002)
# the bridge is the palm: pinned below z -2 mm, the fingers fading in up to z 8 mm (as the finger weights do)
owner = np.where(V2[:, 0] < 0.010, 0, 1)
wp = np.clip((V2[:, 2] + 0.002) / 0.010, 0.0, 1.0)
wp = wp * wp * (3 - 2 * wp)
fp = wp >= 0.999
bare_p = E.metrics(press, press.project(V2, 12, owner), T2, fp, owner)
Xp, stp = E.wrap(press, V2, wp, e2, rounds=300, lam=0.5, owner=owner, tris=T2)
out["press"] = {"bare": bare_p, "relaxed": E.metrics(press, Xp, T2, fp, owner), "stats": stp,
                "slit_mm": float((Xp[fp & (owner == 1), 0].min() - Xp[fp & (owner == 0), 0].max()) * 1000)}
flip = T2.copy()
k = int(np.flatnonzero(fp[T2].all(axis=1))[0])
flip[k] = flip[k][::-1]
out["press"]["flip_folded"] = E.metrics(press, Xp, flip, fp, owner)["folded"]
# H1q contact: two tubes 4 mm apart, then 2 mm into each other; the
# corrective closes the gap under its cap, the touching sides sink, no triangle folds
cdig = {"A": tube(0, 0, 0, 0.05, 0.008), "B": tube(0.020, 0, 0, 0.05, 0.008)}
plain = E.Envelope(cdig, "Thumb", None, k=0.0, k_core=0.0, k_thumb=0.0, core=0.0)
Vc, Tc = E.iso_mesh(plain.sd, (-0.012, -0.012, -0.012), (0.032, 0.012, 0.062), 0.0015)
ec = E.edges_of(Tc)
oc = np.where(Vc[:, 0] < 0.010, 0, 1)
blend = E.Envelope(cdig, "Thumb", None, k=0.008, k_core=0.0, k_thumb=0.0, core=0.0)
Xc, stc = E.contact(blend, Vc, np.ones(len(Vc)), oc, ec, Tc, cap=0.004, smooth=12)
top = (np.abs(Vc[:, 0] - 0.010) < 0.004) & (Vc[:, 1] > 0.004) & (Vc[:, 2] > 0.01) & (Vc[:, 2] < 0.04)
out["contact"] = {**stc, "valley_up_mm": float((Xc[top, 1] - Vc[top, 1]).mean() * 1000),
                  "move_max_mm": float(np.linalg.norm(Xc - Vc, axis=1).max() * 1000)}
odig = {"A": tube(0, 0, 0, 0.05, 0.008), "B": tube(0.014, 0, 0, 0.05, 0.008)}
# each tube's own closed skin, as two bent fingers' skins overlap where they touch
Va, Ta = E.iso_mesh(E.Envelope({"A": odig["A"]}, "Thumb", None, k=0.0, k_core=0.0, k_thumb=0.0, core=0.0).sd,
                    (-0.012, -0.012, -0.012), (0.012, 0.012, 0.062), 0.0015)
V2t = np.concatenate([Va, Va + np.array([0.014, 0, 0])])
T2t = np.concatenate([Ta, Ta + len(Va)])
o2t = np.repeat([0, 1], len(Va))
blend2 = E.Envelope(odig, "Thumb", None, k=0.008, k_core=0.0, k_thumb=0.0, core=0.0)
Xo, sto = E.contact(blend2, V2t, np.ones(len(V2t)), o2t, E.edges_of(T2t), T2t, cap=0.004, smooth=12)
inside = np.array([blend2.digit("B" if k == 0 else "A", V2t[i:i + 1])[0] < -0.001 for i, k in enumerate(o2t)])
out["contact_touch"] = {**sto, "inside": int(inside.sum()),
                        "inside_max_move_mm": float(np.linalg.norm(Xo[inside] - V2t[inside], axis=1).max() * 1000),
                        "inside_on_shell": int((np.abs(blend2.sd(Xo[inside])) < 0.0002).sum())}
# H1r local zone: the same two tubes apart, the global cap 1.5 mm, a local cap of 4 mm on their upper half (the mask
# ramps over z 20-30 mm); the zone moves past the global cap, the far end stays under it, no triangle folds
zm = np.clip((Vc[:, 2] - 0.020) / 0.010, 0.0, 1.0)
Xl, stl = E.contact(blend, Vc, np.ones(len(Vc)), oc, ec, Tc, cap=0.0015, smooth=12,
                    local=(blend, zm * zm * (3 - 2 * zm), 0.004, 0.003))
ml = np.linalg.norm(Xl - Vc, axis=1) * 1000
out["contact_local"] = {**stl, "far_max_mm": float(ml[Vc[:, 2] < 0.010].max()),
                        "zone_max_mm": float(ml[Vc[:, 2] > 0.035].max())}
print("ENVELOPE_CHECK " + json.dumps(out), flush=True)
