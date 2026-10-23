"""The vault plush's paint (art#297, step 3): repaints the cleaned model's Meshy base colour to the approved concept.

blender -b --factory-startup --python plush_paint.py -- <clean.glb> <out dir> [--orange r,g,b] [--brown r,g,b]
    [--pink r,g,b] [--size 2048] [--smile smile.json]

Every texel of Meshy's base colour is sorted by its sRGB hue, saturation and value into five classes: the orange
plush (the lids are its darker part), the brown velour, the eye whites, the dark thread (pupils and the smile) and
the rest (given to the nearer of orange and brown). The orange keeps a softened copy of its own light and dark (so the
lids stay a darker orange) at the concept's hue; the velour is flattened (Meshy painted wrinkles into it) to one brown
with a faint blurred variation; the eye whites (Meshy's marks inside them filled) are painted afresh in 3D (pink, a soft redder rim, a round
pupil, a catch light); the dark thread becomes one near-black brown. Writes into <out dir>:
- plush_albedo.png (sRGB), plush_mask.png (linear: R fur, G velour, B eye, the shader's weights), plush_normal.png
  (the cleanup's baked normal, copied), plush.glb (the mesh with the new albedo and normal, roughness 1, metallic 0:
  the plain-PBR fallback; the game look is godot/plush/plush.gdshader);
- paint.json: the classes' texel shares and the colours used.
Prints one line `PLUSH_PAINT {...}`.
"""

import json
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
src, out = Path(argv[0]), Path(argv[1])
opts = dict(zip(argv[2::2], argv[3::2]))


def rgb(text):
    return np.array([float(v) / 255.0 for v in text.split(",")], dtype=np.float32)


# Calibrated (2026-10-22) so that godot/plush/shots.gd under the approved look (AgX 0.9) lands near the concept's
# medians: orange 222,80,19 (Godot 234,98,53: AgX adds blue no albedo can take out), brown 78,33,21 (75,30,20), eye
# pink 187,136,129 (196,141,132). Meshy's own colours, painted for an unlit view, came out pale peach.
ORANGE = rgb(opts.get("--orange", "180,34,0"))
BROWN = rgb(opts.get("--brown", "60,26,19"))
PINK = rgb(opts.get("--pink", "200,122,115"))
VEIN = rgb(opts.get("--vein", "196,52,48"))
THREAD = rgb(opts.get("--thread", "34,18,12"))
SIZE = int(opts.get("--size", 2048))
SMILE_JSON = opts.get("--smile")  # plush_mouth.py's line (option A); without it the line is fitted here
out.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(src))
obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")
mat = obj.active_material
bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
base_img = bsdf.inputs["Base Color"].links[0].from_node.image

w, h = base_img.size
px = np.array(base_img.pixels[:], dtype=np.float32).reshape(h, w, 4)[..., :3]  # sRGB values, bottom row first
if (w, h) != (SIZE, SIZE):
    raise SystemExit(f"base colour is {w}x{h}, expected {SIZE}")

mx, mn = px.max(-1), px.min(-1)
v = mx
s = np.where(mx > 1e-4, (mx - mn) / np.maximum(mx, 1e-4), 0.0)
r, g, b = px[..., 0], px[..., 1], px[..., 2]
d = np.maximum(mx - mn, 1e-4)
hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60.0

dark = v < 0.20
white = (~dark) & (s < 0.32) & (v > 0.55)
orange = (~dark) & (~white) & (s > 0.55) & (v > 0.55) & (hue < 45)
brown = (~dark) & (~white) & (~orange) & (v < 0.55)
rest = ~(dark | white | orange | brown)
# the rest: the nearer of the two plush colours by value
orange |= rest & (v >= 0.55)
brown |= rest & (v < 0.55)


def blur(a, radius):
    """A separable box blur, twice (close to a Gaussian), wrapping at the edges like the atlas never needs."""
    k = 2 * radius + 1
    for _ in range(2):
        for axis in (0, 1):
            c = np.cumsum(np.pad(a, [(radius + 1, radius)] if a.ndim == 1 else
                                 [((radius + 1, radius) if i == axis else (0, 0)) for i in range(a.ndim)],
                                 mode="edge"), axis=axis)
            a = (np.take(c, range(k, c.shape[axis]), axis=axis) - np.take(c, range(0, c.shape[axis] - k), axis=axis)) / k
    return a


def masked_blur(values, mask, radius):
    m = mask.astype(np.float32)
    return blur(values * m, radius) / np.maximum(blur(m, radius), 1e-4)


# dark texels inside the velour are Meshy's painted wrinkles, not thread: thread (pupils, the smile) sits in orange
# or in the eye whites
near_brown = blur(brown.astype(np.float32), 6)
near_light = blur((orange | white).astype(np.float32), 6)
wrinkle = dark & (near_brown > near_light)
brown |= wrinkle
dark &= ~wrinkle

# lone dark specks in the orange are Meshy's noise: thread is a line or a pupil, never a dot on its own
lone = dark & (blur(dark.astype(np.float32), 4) < 0.08) & (blur(white.astype(np.float32), 6) < 0.02)
orange |= lone
dark &= ~lone

# Regions Meshy painted wrong, found in 3D and drawn into the texture through each face's UVs (the engineer's critic,
# art#297, 2026-10-23): the tail's stalk is orange (Meshy made it brown), only its end pompom brown; the antenna balls
# are brown all round (Meshy left orange crescents under them); dark thread marks only on the face's front. Front is -Y, up +Z (Blender's import of the GLB), the model 0.30 m tall on the floor.
me = obj.data
uv_layer = me.uv_layers.active.data
cent = np.array([tuple(obj.matrix_world @ p.center) for p in me.polygons])
face_uv = [np.array([tuple(uv_layer[li].uv) for li in p.loop_indices]) for p in me.polygons]


def texel_class(cls, uv):
    x = min(w - 1, max(0, int(uv[0] * w)))
    y = min(h - 1, max(0, int(uv[1] * h)))
    return cls[y, x]


def raster(faces, grow=2):
    """The texels the faces cover in UV space (row 0 is v = 0, as in the pixel array), grown by grow texels."""
    out_mask = np.zeros((h, w), dtype=bool)
    for f in faces:
        pts = face_uv[f] * np.array([w, h])
        for k in range(1, len(pts) - 1):
            tri = np.array([pts[0], pts[k], pts[k + 1]])
            x0, y0 = np.floor(tri.min(0)).astype(int)
            x1, y1 = np.ceil(tri.max(0)).astype(int)
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w - 1), min(y1, h - 1)
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = tri
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-9:
                continue
            l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
            l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
            inside_t = (l1 >= -0.02) & (l2 >= -0.02) & (1 - l1 - l2 >= -0.02)
            out_mask[y0:y1 + 1, x0:x1 + 1] |= inside_t
    if grow:
        out_mask = blur(out_mask.astype(np.float32), grow) > 0.01
    return out_mask


zmax = cent[:, 2].max()
# the tail: it leaves the body low at the back, along the middle; its tip is the farthest point back
body = np.abs(cent[:, 0]) > 0.03
back_y = {}
for z0 in np.arange(0.0, 0.12, 0.01):
    band = body & (cent[:, 2] >= z0) & (cent[:, 2] < z0 + 0.01)
    back_y[round(z0, 2)] = cent[band, 1].max() if band.any() else 0.0
tip = cent[np.argsort(-cent[:, 1])[:20]].mean(0)
# a sphere's cap 2 cm deep is about as wide as the sphere when its radius is near 2 cm: the cap gives the radius
cap = cent[:, 1] > tip[1] - 0.02
pom_r = float(np.clip((cent[cap, 2].max() - cent[cap, 2].min()) / 2, 0.012, 0.03)) if cap.any() else 0.02
pom_c = tip - np.array([0.0, pom_r, 0.0])
in_pompom = np.linalg.norm(cent - pom_c, axis=1) < pom_r * 1.08
pompom_info = (pom_c, pom_r, np.array([0.0, -1.0, 0.0]))  # the tail leaves the pompom towards the body (-Y)
stalk = np.array([abs(c[0]) < 0.03 and c[2] < 0.1 and c[1] > back_y.get(round(np.floor(c[2] * 100) / 100, 2), 1.0) + 0.004
                  for c in cent]) & ~in_pompom
# the antenna balls: around the highest point on each side, a ball's radius down
balls = np.zeros(len(cent), dtype=bool)
ball_info = []
for side in (-1.0, 1.0):
    s_sel = (np.sign(cent[:, 0]) == side) & (cent[:, 2] > zmax - 0.08)
    if not s_sel.any():
        continue
    top = cent[s_sel][np.argmax(cent[s_sel][:, 2])]
    cap = s_sel & (cent[:, 2] > top[2] - 0.02)
    r_ball = float(np.clip((cent[cap, 0].max() - cent[cap, 0].min()) / 2, 0.012, 0.035)) if cap.any() else 0.022
    ball_c = top - np.array([0.0, 0.0, r_ball])
    # the whole ball, but not the stalk where it goes in: the stalks lean outwards, so the stalk is the faces within
    # 25 degrees of the line from the ball's middle down towards the head, past 0.9 of the ball's radius
    d = cent - ball_c
    dist = np.linalg.norm(d, axis=1)
    to_head = np.array([-0.6 * ball_c[0], 0.0, -0.07])
    to_head /= np.linalg.norm(to_head)
    along_stalk = (d @ to_head) > np.cos(np.radians(25.0)) * np.maximum(dist, 1e-9)
    balls |= (dist < r_ball * 1.1) & ~(along_stalk & (dist > 0.9 * r_ball))
    ball_info.append((ball_c, r_ball, to_head))
face_co = [np.array([tuple(obj.matrix_world @ me.vertices[me.loops[li].vertex_index].co) for li in poly.loop_indices])
           for poly in me.polygons]
areas = np.array([poly.area for poly in me.polygons])


def raster_pos(faces):
    """The texels the faces cover and each one's 3D point (interpolated over its triangle)."""
    hit = np.zeros((h, w), dtype=bool)
    pos = np.zeros((h, w, 3), dtype=np.float32)
    for f in faces:
        pts = face_uv[f] * np.array([w, h])
        p3 = face_co[f]
        for k in range(1, len(pts) - 1):
            tri = np.array([pts[0], pts[k], pts[k + 1]])
            t3 = np.array([p3[0], p3[k], p3[k + 1]])
            x0, y0 = np.floor(tri.min(0)).astype(int)
            x1, y1 = np.ceil(tri.max(0)).astype(int)
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w - 1), min(y1, h - 1)
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = tri
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-9:
                continue
            l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
            l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
            l3 = 1 - l1 - l2
            ins = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
            p = l1[..., None] * t3[0] + l2[..., None] * t3[1] + l3[..., None] * t3[2]
            sub_hit = hit[y0:y1 + 1, x0:x1 + 1]
            sub_pos = pos[y0:y1 + 1, x0:x1 + 1]
            sub_pos[ins] = p[ins]
            sub_hit |= ins
    return hit, pos


# The fabric's colour is decided per face of the model, never per texel (the engineer, art#297, 2026-10-23: dots on
# the belly, by an eye): each face's share of brown texels is diffused over the surface and cut at a half (a smooth
# border), and islands under 200 faces join the colour around them, so no stray mark of Meshy's can stay a dot.
# Then the tail's stalk is orange and its pompom and the antenna balls brown. Only the eyes and the thread (pupils,
# the smile) keep texel detail, and only on the face's front.
orig_orange, orig_brown = orange.copy(), brown.copy()
co = np.array([tuple(obj.matrix_world @ vv.co) for vv in me.vertices])
_, weld = np.unique(np.round(co / 1e-5).astype(np.int64), axis=0, return_inverse=True)
weld = weld.ravel()
edge_faces = {}
for poly in me.polygons:
    vs = [int(weld[i]) for i in poly.vertices]
    for k in range(len(vs)):
        key = (min(vs[k], vs[k - 1]), max(vs[k], vs[k - 1]))
        edge_faces.setdefault(key, []).append(poly.index)
pairs = np.array([fs[:2] for fs in edge_faces.values() if len(fs) >= 2], dtype=np.int64)


def share(cls, f):
    uv = face_uv[f]
    c = uv.mean(0)
    return np.mean([texel_class(cls, q) for q in [c] + [(c + u) / 2 for u in uv]])


field = np.array([share(brown | (dark & ~white), f) for f in range(len(cent))])
for _ in range(15):  # diffuse the brown share over the surface, so the border is a smooth level line, not a zigzag
    total = field.copy()
    count = np.ones(len(field))
    np.add.at(total, pairs[:, 0], field[pairs[:, 1]])
    np.add.at(total, pairs[:, 1], field[pairs[:, 0]])
    np.add.at(count, pairs[:, 0], 1.0)
    np.add.at(count, pairs[:, 1], 1.0)
    field = total / count
label = field > 0.5


def islands(lab):
    """Each face's island id among faces of the same label (union-find over the neighbour pairs)."""
    parent = np.arange(len(lab))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for f0, f1 in pairs:
        if lab[f0] == lab[f1]:
            r0, r1 = find(f0), find(f1)
            if r0 != r1:
                parent[r0] = r1
    return np.array([find(i) for i in range(len(lab))])


ids = islands(label)
sizes = np.bincount(ids, minlength=len(label))
small = sizes[ids] < 200
label[small] = ~label[small]
label[stalk] = False
label[in_pompom | balls] = True
# no growing in UV space: the atlas packs unrelated parts of the model side by side, so a grown region paints into a
# neighbour island (red marks on the back, one on an eye white). Texels between islands, which no face covers, take
# the colour of the nearer covered texels.
covered = raster(np.arange(len(cent)), grow=0)
brown_in = raster(np.nonzero(label)[0], grow=0) & covered
brown_t = brown_in | (~covered & (blur(brown_in.astype(np.float32), 2) > blur((covered & ~brown_in).astype(np.float32), 2)))
face_front = (cent[:, 2] > zmax * 0.42) & (cent[:, 1] < -0.02)
face_t = raster(np.nonzero(face_front)[0], grow=0)
white &= face_t
dark &= face_t
brown = brown_t & ~white & ~dark
orange = ~brown_t & ~white & ~dark
regions = {"tail_stalk_faces": int(stalk.sum()), "tail_pompom_faces": int(in_pompom.sum()),
           "antenna_ball_faces": int(balls.sum()), "brown_faces": int(label.sum()), "faces": len(label),
           "small_islands_flipped_faces": int(small.sum()), "pompom_radius_m": round(float(pom_r), 4)}

# The balls (the antennae's, the tail's pompom) per texel in 3D (the engineer, art#297, 2026-10-23: the antenna tips
# "look buggy", a gap where the paint ran short): per face the border zigzagged. Every texel near a ball gets its 3D
# point: inside the ball brown, on the stalk orange right up to where it goes in, a clean ring.
ball_report = []
for bc0, r0, sdir in ball_info + [pompom_info]:
    near = np.linalg.norm(cent - bc0, axis=1) < r0 * 2.2
    d0 = cent - bc0
    surf_sel = near & ((d0 @ sdir) < 0.5 * r0) & (np.linalg.norm(d0, axis=1) < 1.3 * r0)
    bc = cent[surf_sel].mean(0) if surf_sel.sum() > 20 else bc0
    rr = float(np.median(np.linalg.norm(cent[surf_sel] - bc, axis=1))) if surf_sel.sum() > 20 else r0
    ds = cent - bc
    proj = ds @ sdir
    st = near & (proj > 1.2 * rr) & (proj < 2.0 * rr)
    if st.sum() > 5:
        axis_dir = cent[st].mean(0) - bc
        axis_dir /= np.linalg.norm(axis_dir)
        radial = ds[st] - np.outer(ds[st] @ axis_dir, axis_dir)
        sr = float(np.median(np.linalg.norm(radial, axis=1)))
    else:
        axis_dir, sr = sdir, 0.005
    hit, pos = raster_pos(np.nonzero(near)[0])
    p = pos[hit] - bc
    along = p @ axis_dir
    off_axis = np.linalg.norm(p - np.outer(along, axis_dir), axis=1)
    stalk_px = (off_axis < sr * 1.6) & (along > 0.9 * rr)
    ball_px = (np.linalg.norm(p, axis=1) < 1.4 * rr) & ~stalk_px
    on = np.zeros((h, w), dtype=bool)
    off = np.zeros((h, w), dtype=bool)
    on[hit] = ball_px
    off[hit] = stalk_px
    brown_t = (brown_t | on) & ~off
    ball_report.append({"centre": [round(float(c), 4) for c in bc], "radius_m": round(rr, 4),
                        "stalk_radius_m": round(sr, 4)})
brown = brown_t & ~white & ~dark
orange = ~brown_t & ~white & ~dark
regions["balls"] = ball_report


res = px.copy()
# orange: the concept hue; Meshy's own light and dark only where Meshy painted orange, clipped and blurred, so large
# forms (the lids' darker orange) stay and thin marks go
vo = np.median(v[orig_orange])
ratio_o = np.where(orig_orange, np.clip(v / vo, 0.75, 1.1), 1.0)
shade_o = masked_blur(ratio_o, orange, 6) ** 0.6
res[orange] = (ORANGE[None, :] * shade_o[orange][:, None])
# velour: flattened, a faint large-scale variation only
vb = np.median(v[orig_brown])
shade_b = np.clip(masked_blur(np.where(orig_brown, v / vb, 1.0), brown, 24), 0.85, 1.15) ** 0.5
res[brown] = BROWN[None, :] * shade_b[brown][:, None]
# The eyes, painted afresh in 3D (the engineer, art#297, 2026-10-23: specks on the whites, odd eyes): Meshy's texels
# there are a mess of red, dark and white bits, and every texel-level patch left a new mark. Each eye is the faces
# Meshy painted white or as its pupil; every texel of them gets its 3D point, and from it: pink with a soft redder
# rim towards the eye's edge (bloodshot, never dotted), a round pupil where Meshy's pupil sits and of its size, and a
# small catch light above the pupil's middle.
share_white = np.array([share(white, f) if face_front[f] else 0.0 for f in range(len(cent))])
share_dark = np.array([share(dark, f) if face_front[f] else 0.0 for f in range(len(cent))])
eye_t = np.zeros((h, w), dtype=bool)
eyes = []
for side in (-1.0, 1.0):
    on_side = face_front & (np.sign(cent[:, 0]) == side)
    e = on_side & (share_white > 0.4)
    if e.sum() < 10:
        continue
    ec = np.median(cent[e], axis=0)
    er = float(np.percentile(np.linalg.norm(cent[e] - ec, axis=1), 90))
    near = np.linalg.norm(cent - ec, axis=1) < er * 1.3
    pup = on_side & near & (share_dark > 0.5)
    faces = e | pup
    for _ in range(2):  # close the small gaps between Meshy's white and pupil patches
        total = faces.astype(np.float32)
        count = np.ones(len(faces), dtype=np.float32)
        np.add.at(total, pairs[:, 0], faces[pairs[:, 1]])
        np.add.at(total, pairs[:, 1], faces[pairs[:, 0]])
        np.add.at(count, pairs[:, 0], 1.0)
        np.add.at(count, pairs[:, 1], 1.0)
        faces = (total / count > 0.5) & near
    pc = np.average(cent[pup], axis=0, weights=areas[pup]) if pup.any() else ec
    pr = float(np.sqrt(areas[pup].sum() / np.pi)) if pup.any() else er * 0.35
    # every face around the pupil belongs to the eye (one left out stayed orange: a chip in the pupil)
    faces |= np.linalg.norm(cent - pc, axis=1) < pr * 1.3
    hit, pos = raster_pos(np.nonzero(faces)[0])
    d_eye = np.linalg.norm(pos[hit] - ec, axis=1) / er
    rim_r = np.clip((d_eye - 0.5) / 0.5, 0.0, 1.0) ** 1.4
    col = PINK[None, :] * (1.0 - 0.45 * rim_r[:, None]) + VEIN[None, :] * (0.45 * rim_r[:, None])
    d_pup = np.linalg.norm(pos[hit] - pc, axis=1) / pr
    a_pup = np.clip((1.0 - d_pup) / 0.08 + 0.5, 0.0, 1.0)[:, None]
    col = col * (1 - a_pup) + THREAD[None, :] * a_pup
    catch_c = pc + np.array([0.0, -0.15 * pr, 0.45 * pr])
    d_catch = np.linalg.norm(pos[hit] - catch_c, axis=1) / (0.28 * pr)
    a_catch = np.clip((1.0 - d_catch) / 0.15 + 0.5, 0.0, 1.0)[:, None]
    col = col * (1 - a_catch) + np.array([0.96, 0.94, 0.92], dtype=np.float32)[None, :] * a_catch
    res[hit] = col
    eye_t |= hit
    eyes.append({"centre": [round(float(c), 5) for c in ec], "side": side, "faces": int(faces.sum()), "pupil_faces": int(pup.sum()),
                 "eye_radius_m": round(er, 4), "pupil_radius_m": round(pr, 4)})
orange &= ~eye_t
brown &= ~eye_t
dark &= ~eye_t  # what is left of the thread: Meshy's smile
# The smile, drawn afresh as one even line (the engineer, art#297, 2026-10-23: the mouth "looks strange"): Meshy's
# smile is broken bits and dashes in the muzzle's crease. Its texels' 3D points give the line: the median point in
# each of 30 slices across the face, smoothed and resampled; every face texel within half the thread's width of that
# line is thread, with a soft edge, and Meshy's own bits are fur again.
SMILE_HALF_M = 0.0012
sm_hit, sm_pos = raster_pos(np.nonzero(face_front)[0])
old_smile = dark & sm_hit
pts = sm_pos[old_smile]
smile_line = np.zeros((h, w), dtype=bool)
smile_flat = np.zeros((h, w), dtype=bool)
smile_points = 0
res[dark] = ORANGE  # Meshy's bits: fur, under the new line
orange |= dark
dark[:] = False
if SMILE_JSON:
    line = np.array(json.loads(Path(SMILE_JSON).read_text(encoding="utf-8"))["line"])
    smile_points = len(line)
elif len(pts) > 50:
    lo, hi = np.percentile(pts[:, 0], [1, 99])
    edges = np.linspace(lo, hi, 31)
    mids = [np.median(pts[(pts[:, 0] >= e0) & (pts[:, 0] < e1)], axis=0) for e0, e1 in zip(edges[:-1], edges[1:])
            if ((pts[:, 0] >= e0) & (pts[:, 0] < e1)).sum() >= 3]
    line = np.array(mids)
    for _ in range(3):
        line[1:-1] = (line[:-2] + 2 * line[1:-1] + line[2:]) / 4
    t = np.linspace(0, 1, len(line))
    tt = np.linspace(0, 1, 300)
    line = np.stack([np.interp(tt, t, line[:, k]) for k in range(3)], axis=1)
    smile_points = len(mids)
if smile_points:
    box_lo, box_hi = line.min(0) - 0.004, line.max(0) + 0.004
    ys, xs = np.nonzero(sm_hit)
    p = sm_pos[ys, xs]
    in_box = np.all((p >= box_lo) & (p <= box_hi), axis=1)
    ys, xs, p = ys[in_box], xs[in_box], p[in_box]
    dist = np.full(len(p), np.inf, dtype=np.float32)
    for k in range(0, len(line), 50):
        seg = line[k:k + 50]
        dist = np.minimum(dist, np.linalg.norm(p[:, None, :] - seg[None, :, :], axis=2).min(1))
    a = np.clip((SMILE_HALF_M - dist) / 0.0003 + 0.5, 0.0, 1.0)
    res[ys, xs] = res[ys, xs] * (1 - a[:, None]) + THREAD[None, :] * a[:, None]
    smile_line[ys[a > 0.5], xs[a > 0.5]] = True
    # the thread presses the pile flat in a 2 mm band, so no fur strand hangs over the line
    smile_flat = np.zeros((h, w), dtype=bool)
    smile_flat[ys[dist < SMILE_HALF_M + 0.002], xs[dist < SMILE_HALF_M + 0.002]] = True
orange &= ~smile_line  # no pile over the thread
veins = 0


def pad(img, filled, steps):
    """Texels no face covers take the mean of their filled neighbours, ring by ring, so filtering at an island's
    edge never mixes in the colour of the island packed next to it."""
    img = img.copy()
    filled = filled.copy()
    for _ in range(steps):
        acc = np.zeros_like(img)
        cnt = np.zeros(filled.shape, dtype=np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sf = np.roll(filled, (dy, dx), axis=(0, 1))
            acc += np.roll(img, (dy, dx), axis=(0, 1)) * sf[..., None]
            cnt += sf
        grow = (~filled) & (cnt > 0)
        img[grow] = acc[grow] / cnt[grow][:, None]
        filled |= grow
    return img


# the shader's weights: R fur, G velour, B the glossy eye (whites, pupils, catch lights); the smile's thread none
mask = np.zeros((h, w, 3), dtype=np.float32)
mask[..., 0] = masked_blur(orange.astype(np.float32), np.ones_like(orange), 1)
mask[..., 0] = np.where(smile_flat, np.minimum(mask[..., 0], 0.35), mask[..., 0])  # under the shells' 0.5
mask[..., 1] = masked_blur(brown.astype(np.float32), np.ones_like(brown), 1)
mask[..., 2] = masked_blur(eye_t.astype(np.float32), np.ones_like(white), 1)  # the smile's thread: none, matte
res = pad(res, covered, 6)
mask = pad(mask, covered, 6)


def save(name, data, colorspace):
    img = bpy.data.images.new(name, w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = colorspace
    rgba = np.concatenate([np.clip(data, 0, 1), np.ones((h, w, 1), np.float32)], -1)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = str(out / f"{name}.png")
    img.file_format = "PNG"
    img.save()
    return img


albedo = save("plush_albedo", res, "sRGB")
save("plush_mask", mask, "Non-Color")
normal_path = out / "plush_normal.png"
shutil.copyfile(src.with_name(src.stem + "_normal.png"), normal_path)  # the cleanup's bake; the GLB packs it

# the plain-PBR fallback: the new albedo, the baked normal, roughness 1
nt = mat.node_tree
bsdf.inputs["Base Color"].links[0].from_node.image = albedo
if bsdf.inputs["Roughness"].links:
    nt.links.remove(bsdf.inputs["Roughness"].links[0])
bsdf.inputs["Roughness"].default_value = 1.0
bsdf.inputs["Metallic"].default_value = 0.0
for o in bpy.context.scene.objects:
    o.select_set(o == obj)
bpy.ops.export_scene.gltf(filepath=str(out / "plush.glb"), export_format="GLB", use_selection=True,
                          export_yup=True, export_image_format="AUTO", export_tangents=True)

total = float(w * h)
report = {
    "texels": {k: round(float(m.sum()) / total, 4) for k, m in
               (("orange", orange), ("brown", brown), ("white", white), ("dark", dark), ("rest", rest))},
    "colours": {k: [round(float(c) * 255) for c in val] for k, val in
                (("orange", ORANGE), ("brown", BROWN), ("pink", PINK), ("vein", VEIN), ("thread", THREAD))},
    "veins": veins, "regions": regions, "eyes": eyes, "smile_slices": smile_points, "orange_median_v": round(float(vo), 3), "brown_median_v": round(float(vb), 3),
}
(out / "paint.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("PLUSH_PAINT " + json.dumps(report))
