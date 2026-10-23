"""The alien pilot's static heads (art #196): the skin colour study's accent mask, made in headless Blender
(tools/runner/blender.py) from a static build's saved .blend and maps (never changed). Writes into --out:
- `<head>_accent.png` (2048, linear RGB): R the lips, G the marks (the axolotl's gills and cheek freckles, the
  chameleon's crest stripes), B the pale front panel; every channel already multiplied by the skin tint mask, so the
  eyes stay out;
- `<head>_accent.json`: each region's median sRGB in the build's albedo (the study's recolour bases) and its texel share.

The regions come from the object-space position baked onto the build's own UVs (an emission bake with Blender's
margin, so a region is continuous across the UV seams and the gutters) and the plain albedo's saturation:
- lips: a band round step 2a's fitted lip line (the slit's height across the mouth), inside the lip line's half
  width and in front of the face, kept to the saturated (teal) texels: the lips are teal on a pale snout and chin, so
  the paint gives the edge, not the band;
- marks: the axolotl's gills (step 2a's gill roots, as the build's rough map has them, on its thin parts) and its
  freckles (saturated dots inside the pale cheeks); the chameleon's crest stripes (the build's own stripe formula,
  step 2a's `stripes`);
- front: the pale texels (low saturation against the skin's teal), the lips taken out.

    run_script("alien_tint_mask.py", ["--head", "axolotl", "--build", <static_v5/axolotl>, "--ref", <step 2a v2
               build.json>, "--out", <dir>])
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_pilot_head as H  # noqa: E402
import alien_static_head as S  # noqa: E402

# lips: the band's half height round the slit (eye radii), its depth behind the lip line's front point (m), and its
# side fade in lip line half widths (the axolotl's lips sit in the pale face, so its band may be wide: the paint gives
# the edge; the chameleon's corners meet the teal cheek, so its fade ends at the lip line's end)
LIP_BAND = {"axolotl": (1.1, 0.22, (1.0, 1.15)), "chameleon": (0.62, 0.26, (0.95, 1.0))}


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def load(path: Path) -> np.ndarray:
    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = "Non-Color"  # the stored values (sRGB for the albedo), never converted
    return H.image_array(img)


def main() -> int:
    ap = argparse.ArgumentParser()
    for a in ("--head", "--build", "--ref", "--out"):
        ap.add_argument(a, required=True)
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    head, build, out = args.head, Path(args.build), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ref = json.loads(Path(args.ref).read_text(encoding="utf-8"))
    eye = ref["eye_fit"]
    r = eye["r"]
    bpy.ops.wm.open_mainfile(filepath=str(build / f"{head}_static.blend"))
    low = bpy.data.objects[f"{head}_static"]
    for o in list(bpy.data.objects):
        if o is not low:
            o.hide_render = True
    mat = bpy.data.materials.new(f"{head}_posbake")
    mat.use_nodes = True
    low.data.materials.clear()
    low.data.materials.append(mat)
    nt = mat.node_tree
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(geo.outputs["Position"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 1
    plain = load(build / f"{head}_albedo_plain.png")[..., :3]
    albedo = load(build / f"{head}_albedo.png")[..., :3]
    skin = load(build / f"{head}_mask.png")[..., 0]
    thin = load(build / f"{head}_detail.png")[..., 1]  # the thinness (1 thin: gills, crest, lips)
    n = plain.shape[0]
    pos_img = S.new_image(f"{head}_pos", n, data=True, float_buffer=True)
    S.bake_to(low, pos_img, "EMIT")
    pos = H.image_array(pos_img)[..., :3]
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    hue, sat, val = (a.reshape(n, n) for a in S.hsv(plain.reshape(-1, 3)))
    teal_s = float(np.median(sat[(skin > 0.95) & (sat > 0.3)]))
    lit = smoothstep(0.12, 0.25, val)  # the paint, not the black gutters between the UV islands
    teal = smoothstep(0.45 * teal_s, 0.7 * teal_s, sat) * lit  # 1 on the teal, 0 on the pale panel
    pale = (1.0 - smoothstep(0.45 * teal_s, 0.7 * teal_s, sat)) * smoothstep(0.45, 0.6, val)  # the pale panel is light

    # lips: the slit's band, the lip line's half width, in front of the face, on the teal paint only
    line = np.asarray(ref["lip_line"]["line"], np.float64)  # (x, up, front)
    order = np.argsort(line[:, 0])
    slit = np.interp(np.abs(x), line[order, 0], line[order, 1])
    hw = ref["lip_line"]["half_width"]
    fp = ref["lip_line"]["front_point"]
    band_h, depth, (w0, w1) = LIP_BAND[head]
    band = 1.0 - smoothstep(0.8 * band_h * r, band_h * r, np.abs(z - slit))
    wide = 1.0 - smoothstep(w0 * hw, w1 * hw, np.abs(x))
    front = 1.0 - smoothstep(fp[1] + 0.8 * depth, fp[1] + depth, y)
    lips = S.blur((band * wide * front * teal).astype(np.float32), 1) * skin

    # marks
    marks = np.zeros_like(lips)
    roots = (ref.get("pivots") or {}).get(f"{head}_gills") or {}
    if roots:  # the build's own gill region (alien_static_head.py, the rough map)
        rx = min(abs(p[0]) for p in roots.values())
        rz = min(p[2] for p in roots.values())
        gills = np.clip((np.abs(x) - rx + 0.02) / 0.06, 0, 1) * np.clip((z - rz + 0.1) / 0.1, 0, 1)
        gills = gills * smoothstep(0.25, 0.55, thin)  # the thin gills only, not the head's side behind them
        # freckles: teal dots inside the pale cheeks, between the lips and the eyes, on the face's front
        cheeks = smoothstep(0.55, 0.75, S.blur(pale.astype(np.float32), 6))
        face = (1.0 - smoothstep(eye["y"] + 0.5 * r, eye["y"] + 2.0 * r, y)) \
            * smoothstep(slit + 0.6 * r, slit + 1.2 * r, z) * (1.0 - smoothstep(eye["z"], eye["z"] + 0.8 * r, z))
        freckles = teal * cheeks * face * (1.0 - lips)
        marks = np.maximum(gills, freckles)
    st = ref.get("stripes")
    if st:  # the crest stripes: alien_pilot_head.grade_source's formula
        axis = 0 if abs(st["front"][0]) > 0.5 else 1
        dyb = (pos[..., axis] - st["c_depth"]) * -st["front_sign"]
        ang = np.arctan2(z - st["c_z"], dyb)
        wave = np.sin(ang * st["k"])
        marks = smoothstep(-0.25, 0.25, wave) * smoothstep(st["z_lo"], st["z_hi"], z)
    marks = S.blur(marks.astype(np.float32), 1) * skin * (1.0 - lips)
    front_w = S.blur(pale.astype(np.float32), 1) * skin * (1.0 - lips) * (1.0 - marks)
    acc = np.stack([lips, marks, front_w], -1)
    S.save(acc, out / f"{head}_accent.png", data=True)

    report = {"head": head, "teal_sat": round(teal_s, 4), "regions": {}}
    core = skin > 0.95
    base = albedo[core & (teal > 0.9) & (lips < 0.1) & (marks < 0.1)]
    for name, w in (("skin", None), ("lips", lips), ("marks", marks), ("front", front_w)):
        px = base if w is None else albedo[core & (w > 0.8)]
        report["regions"][name] = {"srgb": [round(float(v), 4) for v in np.median(px, axis=0)] if len(px) else None,
                                   "share": round(len(px) / float(core.sum()), 4)}
    (out / f"{head}_accent.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"TINT {head} {json.dumps(report)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
