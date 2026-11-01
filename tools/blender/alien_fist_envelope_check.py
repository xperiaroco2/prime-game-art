"""The fist union's self-check (art #196, Hands H1l, H1q), run inside Blender for its numpy by
tools/tests/test_alien_fist_envelope_blender.py; prints one line `ENVELOPE_CHECK {json}`.

On synthetic shapes: the round cone's field against brute force; the iso-mesh of a two-finger union (closed, facing
out, on the field); the contact corrective on two tubes apart (the gap fills under the cap, no fold) and touching
(their facing sides sink)."""
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

# H1q contact: two tubes 4 mm apart, then 2 mm into each other; the
# corrective closes the gap under its cap, the touching sides sink, no triangle folds
cdig = {"A": tube(0, 0, 0, 0.05, 0.008), "B": tube(0.020, 0, 0, 0.05, 0.008)}
plain = E.Envelope(cdig, "Thumb", None, k=0.0, k_core=0.0, k_thumb=0.0, core=0.0)
Vc, Tc = E.iso_mesh(plain.sd, (-0.012, -0.012, -0.012), (0.032, 0.012, 0.062), 0.0015)
# the mesher leaves zero-area triangles where grid points land on the surface (H1s: ~200 here); they have no
# orientation, so any move "folds" them: dropped, as a modelled hand has none
Tc = Tc[np.linalg.norm(np.cross(Vc[Tc[:, 1]] - Vc[Tc[:, 0]], Vc[Tc[:, 2]] - Vc[Tc[:, 0]]), axis=1) > 2e-12]
ec = E.edges_of(Tc)
oc = np.where(Vc[:, 0] < 0.010, 0, 1)
blend = E.Envelope(cdig, "Thumb", None, k=0.008, k_core=0.0, k_thumb=0.0, core=0.0)
# the shipped smoothing (`[fist] c_smooth` 6); the valley's skin (the facing sides, mid-length) starts inside the
# union by its fill and ends on it
Xc, stc = E.contact(blend, Vc, np.ones(len(Vc)), oc, ec, Tc, cap=0.004, smooth=6)
val = (np.abs(Vc[:, 0] - 0.010) < 0.004) & (Vc[:, 2] > 0.01) & (Vc[:, 2] < 0.04)
out["contact"] = {**stc, "valley_depth_before_mm": float(np.maximum(-blend.sd(Vc[val]), 0).mean() * 1000),
                  "valley_depth_after_mm": float(np.maximum(-blend.sd(Xc[val]), 0).mean() * 1000),
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
print("ENVELOPE_CHECK " + json.dumps(out), flush=True)
