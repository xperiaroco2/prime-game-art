"""The vault plush's paint (art#297, step 3): repaints the cleaned model's Meshy base colour to the approved concept.

blender -b --factory-startup --python plush_paint.py -- <clean.glb> <out dir> [--orange r,g,b] [--brown r,g,b]
    [--pink r,g,b] [--size 2048] [--seed 297]

Every texel of Meshy's base colour is sorted by its sRGB hue, saturation and value into five classes: the orange
plush (the lids are its darker part), the brown velour, the eye whites, the dark thread (pupils and the smile) and
the rest (given to the nearer of orange and brown). The orange keeps a softened copy of its own light and dark (so the
lids stay a darker orange) at the concept's hue; the velour is flattened (Meshy painted wrinkles into it) to one brown
with a faint blurred variation; the eye whites turn pink with red veins drawn as random walks from each eye patch's
rim inward; the dark thread becomes one near-black brown. Writes into <out dir>:
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


ORANGE = rgb(opts.get("--orange", "236,92,14"))
BROWN = rgb(opts.get("--brown", "92,47,28"))
PINK = rgb(opts.get("--pink", "238,176,170"))
VEIN = rgb(opts.get("--vein", "196,52,48"))
THREAD = rgb(opts.get("--thread", "34,18,12"))
SIZE = int(opts.get("--size", 2048))
rng = np.random.default_rng(int(opts.get("--seed", 297)))
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

res = px.copy()
# orange: the concept hue, its own light and dark softened (k 0.6), lids included
vo = np.median(v[orange])
shade_o = np.clip((v / vo) ** 0.6, 0.55, 1.15)
shade_o = masked_blur(shade_o, orange, 2)
res[orange] = (ORANGE[None, :] * shade_o[orange][:, None])
# velour: flattened, a faint large-scale variation only
vb = np.median(v[brown])
shade_b = np.clip(masked_blur(v / vb, brown, 24), 0.85, 1.15) ** 0.5
res[brown] = BROWN[None, :] * shade_b[brown][:, None]
# thread
res[dark] = THREAD
# eye whites: pink, slightly lighter towards each patch's middle, then veins
inside = masked_blur(white.astype(np.float32), white, 6)
res[white] = PINK[None, :] * (0.9 + 0.12 * inside[white])[:, None]
veins = 0
ys, xs = np.nonzero(white)
rim = white & (blur(white.astype(np.float32), 3) < 0.75)
ry, rx = np.nonzero(rim)
if ry.size:
    picks = rng.choice(ry.size, size=min(ry.size, max(12, ry.size // 60)), replace=False)
    cy, cx = ys.mean(), xs.mean()
    for i in picks:
        y, x = float(ry[i]), float(rx[i])
        ang = rng.uniform(0, 2 * np.pi)
        for _ in range(int(rng.integers(18, 46))):
            iy, ix = int(round(y)), int(round(x))
            if not (0 <= iy < h and 0 <= ix < w) or not white[iy, ix]:
                break
            a = 0.55 if rng.random() < 0.8 else 0.35
            res[iy, ix] = res[iy, ix] * (1 - a) + VEIN * a
            ang += rng.normal(0, 0.45)
            y += np.sin(ang) * 1.2
            x += np.cos(ang) * 1.2
        veins += 1

# the shader's weights: R fur, G velour, B eye (thread counts as eye: embroidered, no pile)
mask = np.zeros((h, w, 3), dtype=np.float32)
mask[..., 0] = masked_blur(orange.astype(np.float32), np.ones_like(orange), 1)
mask[..., 1] = masked_blur(brown.astype(np.float32), np.ones_like(brown), 1)
mask[..., 2] = masked_blur((white | dark).astype(np.float32), np.ones_like(white), 1)


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
    "veins": veins, "orange_median_v": round(float(vo), 3), "brown_median_v": round(float(vb), 3),
}
(out / "paint.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("PLUSH_PAINT " + json.dumps(report))
