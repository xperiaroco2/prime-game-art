"""Dresses a built alien character in a fitted outfit (art #196, clothes step 2, C1): opens a game build's character
.blend (alien_loco.py's <char>_char.blend: the character mesh, CharacterArmature and its clips), appends the fitted
cloth (clothes_fit.py's fit_<body>.blend: garment and shoes, skinned, at rest) as separate skinned meshes on the
character's armature, and removes the character's body faces the cloth fully covers, so nothing pokes through (the
body source stays whole: only this build's copy loses them). Then the GLB with export_glb.py's fixed textured options
(alien_loco._export) and the dressed .blend.

- --body-from/--body-to: the character was built on one body variant (f1) and is dressed on another (f2) of the same
  topology: every character vertex that sits on a --body-from vertex (within 0.01 mm) moves by that vertex's
  difference, every other one within 3 cm of the body the difference at its nearest body face (barycentric); the
  head, which no variant moves, stays.
- Covered: a character vertex is covered when five rays from it (its normal and four tilted 40 degrees) all hit the
  cloth within --reach m; a face goes when all its vertices are covered and so are its neighbours
  (clothes_fit_geom.covered_faces, one ring of erosion), so the cut's edge stays under the cloth. A vertex up to
  --outside m outside the cloth (one ray along its reversed normal) is tested from just inside the cloth instead,
  so a shoulder or a toe that crosses the cloth at rest is cut too.
- Under the cloth for certain (clothes_fit_geom.under_cloth): a body vertex inside the cloth at rest (its nearest
  cloth face within --near m) and farther than --away m from every real opening (clothes_open.opening_points: the
  top's collar and cuffs, the trousers' hems, the shoes' tops), on no neck, head or hand bone, is cut
  without the erosion, also where a ray escapes: a clip would move it out through the cloth; on the Shoulder bones
  farther than --away-shoulder m (the skin under the straps' base, near the collar).
- The shoes: the shoes are rigid on the feet, so a foot vertex inside one is cut for certain (no erosion): below the
  shoe's lowest top less --shoe-margin, under the shoe or its toe box, or below the opening's rim where it stands
  (the rim points within --rim-reach across the floor, less --rim-margin: the rim is low on the sides and high at the
  heel and the tongue), or through the shoe's wall (clothes_fit_geom.through_shoe: outside the shoe by 1 to 30 mm,
  its nearest shoe point over 1 cm from the rim); a face with such a vertex goes when all its vertices are on the
  foot below the rim's high point where they stand (clothes_fit_geom.shoe_face), so no face of the foot's side is
  left half through the shoe's coarse faces.
- The cloth's maps (clothes_texture): every piece's albedo, roughness and normal map grown from its UV islands into
  the empty texels, so a far camera's mipmaps average cloth, not the bake's black (unless --no-fill); the garment's
  denim scaled by --denim-gain (linear R,G,B; the stripes and the orange stitching kept).

    blender -b --factory-startup --python tools/blender/clothes_dress.py -- --char CHAR.blend --fit FIT.blend
        --name chameleon --out DIR [--body-from F1.blend --body-to F2.blend] [--reach 0.12]

Writes DIR/<name>_char.blend, DIR/<name>_char.glb and DIR/dress.json; never overwrites (refused when the GLB
exists). Prints CLOTHES_DRESS lines.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clothes_fit_geom as F  # noqa: E402
import clothes_shell as H  # noqa: E402
import clothes_texture as T  # noqa: E402

PIECES = ("garment", "shoes")


def say(*a) -> None:
    print("CLOTHES_DRESS", *a, flush=True)


def tris(o) -> int:
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def body_co(path: str) -> np.ndarray:
    with bpy.data.libraries.load(str(Path(path).resolve())) as (src, dst):
        dst.objects = ["Body"]
    o = dst.objects[0]
    co = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices])
    bpy.data.objects.remove(o)
    return co


def body_polys(path: str) -> list[list[int]]:
    with bpy.data.libraries.load(str(Path(path).resolve())) as (src, dst):
        dst.objects = ["Body"]
    o = dst.objects[0]
    polys = [list(p.vertices) for p in o.data.polygons]
    bpy.data.objects.remove(o)
    return polys


def cloth_tree(objs) -> BVHTree:
    co, polys, off = [], [], 0
    for o in objs:
        co += [tuple(o.matrix_world @ v.co) for v in o.data.vertices]
        polys += [[i + off for i in p.vertices] for p in o.data.polygons]
        off += len(o.data.vertices)
    return BVHTree.FromPolygons(co, polys)


def rays(n: Vector) -> list[Vector]:
    t1 = n.cross(Vector((0, 0, 1)))
    if t1.length < 0.3:
        t1 = n.cross(Vector((1, 0, 0)))
    t1.normalize()
    t2 = n.cross(t1).normalized()
    k = math.tan(math.radians(40))
    return [n] + [(n + k * s * t).normalized() for t in (t1, t2) for s in (1, -1)]


def maps(cloth, grow: bool, gain: tuple[float, float, float]) -> dict:
    """Each cloth piece's image maps filled from its UV islands (grow) and the garment's albedo shifted by gain;
    re-packed so the .blend and the GLB carry them. Returns per image the share of texels filled. The top is left
    out: clothes_top fills its maps itself and then wraps its back seam's margin columns, which a fill here would
    undo."""
    rep = {}
    for o in cloth:
        if o.name == "top":
            continue
        me = o.data
        uv = me.uv_layers.active.data
        tri = np.array([[uv[t.loops[i]].uv[:] for i in range(3)] for t in me.loop_triangles] if me.loop_triangles
                       else [], dtype=np.float64)
        if not len(tri):
            me.calc_loop_triangles()
            tri = np.array([[uv[t.loops[i]].uv[:] for i in range(3)] for t in me.loop_triangles], dtype=np.float64)
        imgs = {n.image for s in o.material_slots if s.material and s.material.node_tree
                for n in s.material.node_tree.nodes if n.type == "TEX_IMAGE" and n.image}
        masks = {}
        for img in sorted(imgs, key=lambda i: i.name):
            w, h = img.size
            px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
            entry = {}
            if grow:
                if (w, h) not in masks:
                    masks[(w, h)] = T.island_mask(tri, w, h)
                valid = masks[(w, h)]
                px[..., :3] = T.fill(px[..., :3], valid)
                entry["filled_share"] = round(float((~valid).mean()), 4)
            if o.name == "garment" and "diffuse" in img.name and gain != (1.0, 1.0, 1.0):
                px[..., :3] = T.shift(px[..., :3], gain)
                entry["denim_gain"] = list(gain)
            if entry:
                img.pixels[:] = px.ravel()
                img.update()
                img.pack()
                rep[img.name] = entry
                say("map", img.name, entry)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True)
    ap.add_argument("--fit", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--body-from", default="")
    ap.add_argument("--body-to", default="")
    ap.add_argument("--reach", type=float, default=0.12)
    ap.add_argument("--outside", type=float, default=0.03, help="a body vertex this far outside the cloth still counts")
    ap.add_argument("--opening", type=float, default=0.04, help="no outside cut this near an opening (m)")
    ap.add_argument("--opening-leg", type=float, default=0.015,
                    help="--opening for skin on the LowerLeg bones (m): the shin poked through the trouser leg 25 mm "
                         "over the hem, inside the 40 mm (E1c)")
    ap.add_argument("--shoe-margin", type=float, default=0.01, help="the foot cut stays this far below the shoe's top")
    ap.add_argument("--near", type=float, default=0.06, help="the cloth this near a body vertex at rest (m)")
    ap.add_argument("--away", type=float, default=0.08,
                    help="a body vertex inside the cloth and this far from every opening is cut for certain (m)")
    ap.add_argument("--rim-margin", type=float, default=0.004,
                    help="the foot cut stays this far below the shoe opening's rim where the vertex stands (m)")
    ap.add_argument("--rim-reach", type=float, default=0.03,
                    help="the rim points this near a foot vertex across the floor give its local rim (m)")
    ap.add_argument("--away-shoulder", type=float, default=0.04,
                    help="--away on the Shoulder bones (m): the skin under the straps' base, near the collar")
    ap.add_argument("--no-fill", action="store_true", help="leave the maps' empty texels black (the r16 build)")
    ap.add_argument("--denim-gain", default="1,1,1", help="the garment denim's linear gain R,G,B (1,1,1: as baked)")
    ap.add_argument("--strap-axis", default="0.04,1.18", help="the shoulders' axis in the side view: y,z (m)")
    ap.add_argument("--strap-width", type=float, default=0.035)
    ap.add_argument("--strap-lip", type=float, default=0.003, help="the strip's edges fold this far toward the body")
    ap.add_argument("--strap-uv", default="0.4725,0.4935,0.784,0.829",
                    help="the plain denim rectangle the straps' patch copies: u0,u1,v0,v1")
    ap.add_argument("--strap-texels", type=float, default=0.743, help="the strips' UV units per metre along")
    ap.add_argument("--sneakers", choices=("auto", "on", "off"), default="auto",
                    help="our code-built canvas sneakers (sneaker_build.py) in place of the fit's Meshy shoes; auto: "
                         "on with --shell (the dungarees)")
    ap.add_argument("--toes-cap", default="alien_loco",
                    help="with the sneakers, the anim set whose [toes_cap] caps every clip's Toes bend ('': none)")
    ap.add_argument("--shell", action="store_true",
                    help="the hybrid route (clothes_top): a shell top of the body, the Meshy garment cut to the "
                         "trousers, bib and back panel, new straps")
    ap.add_argument("--shell-off", type=float, default=0.006, help="the top's clearance off the body (m)")
    ap.add_argument("--shell-hem", type=float, default=0.95, help="the top's hem, tucked under the trousers (z, m)")
    ap.add_argument("--shell-full", type=float, default=1.02, help="the full clearance from this height up (z, m)")
    ap.add_argument("--shell-hem-off", type=float, default=0.002, help="the clearance at the hem (m)")
    ap.add_argument("--shell-gap", type=float, default=0.003, help="the top stays this far inside a kept piece (m)")
    ap.add_argument("--shell-floor", type=float, default=0.002, help="the top's least clearance (m)")
    ap.add_argument("--shell-hide", type=float, default=0.06,
                    help="a top face whose five rays (its normal and four tilted) meet a kept piece this near is "
                         "hidden under it (m)")
    ap.add_argument("--shell-hide-tilt", type=float, default=0.6, help="the four rays' tilt off the normal (tan)")
    ap.add_argument("--shell-hide-rings", type=int, default=1, help="the hidden faces kept next to a panel's edge")
    ap.add_argument("--shell-follow", type=float, default=0.04,
                    help="a top vertex whose rays meet the garment this near takes its weights by their share "
                         "(m; 0: the body's alone)")
    ap.add_argument("--shell-under", type=float, default=0.0015,
                    help="the top under the bib and the back panel is pulled in to this offset off the body, by the "
                         "share of its five rays meeting them (m; 0: off; C1i)")
    ap.add_argument("--waistband", default="0.038,0.006",
                    help="the built waistband beside the bib (C1i): its height, and how far its lower edge laps over "
                         "the trousers below the Meshy band it replaces (m; 0,0: off)")
    ap.add_argument("--band-axis-y", type=float, default=0.015, help="the waist's centre in y, for the band's rays (m)")
    ap.add_argument("--band-lip", type=float, default=0.003, help="the band's lower lip toward the body (m)")
    ap.add_argument("--band-cinch", type=float, default=0.006,
                    help="the band's upper edge stands this far out of the tucked top (m)")
    ap.add_argument("--band-over", type=float, default=0.03,
                    help="the band's ends run this far under the bib's and the back panel's edges (m)")
    ap.add_argument("--band-step", type=float, default=3.0, help="degrees between the band's stations")
    ap.add_argument("--seat-wrap", type=float, default=0.24,
                    help="E1f: the cloth over the seat, from under the waist down this far, re-laid on the body "
                         "(clothes_top.seat_wrap; 0: off)")
    ap.add_argument("--seat-clear", default="0.004,0.03", help="the seat's offset off the body, least and most (m)")
    ap.add_argument("--seat-smooth", type=int, default=20, help="rounds smoothing the seat's offsets")
    ap.add_argument("--seat-relax", type=int, default=8, help="rounds relaxing the seat's folds along the body")
    ap.add_argument("--fill-holes", type=int, default=12,
                    help="E1g: the garment's closed open-edge loops of at most this many edges under the waist are "
                         "filled (Meshy's holes, the dark divots; 0: off)")
    ap.add_argument("--despike", type=float, default=0.015,
                    help="E1g: a garment vertex under the waist this far (m) out of its neighbours' mean along the "
                         "body's normal goes to that mean (the hips' spikes; 0: off)")
    ap.add_argument("--despike-rounds", type=int, default=3, help="E1g: the despike's passes")
    ap.add_argument("--seat-y0", type=float, default=-0.02,
                    help="the seat's zone lies behind this y (the side seams; -1: no bound)")
    ap.add_argument("--seat-y1", type=float, default=float("inf"),
                    help="E1g: and in front of this y (a front zone, the chameleon's divots: --seat-y0 -1 --seat-y1 -0.03)")
    ap.add_argument("--seat-open-rings", type=int, default=0,
                    help="E1g: the relax only on folds within this many edge rings of an open edge (the flaps); 0: "
                         "every fold (E1f, smeared the stitches)")
    ap.add_argument("--seat-fold", type=float, default=0.5,
                    help="a seat face whose normal's dot with the body's is under this is a fold (relaxed)")
    ap.add_argument("--band-flaps", type=float, default=0.10,
                    help="the panels' edge faces turned toward the body go up to this far above the waist (m)")
    ap.add_argument("--edge-peel", type=int, default=3,
                    help="passes peeling the bib's and the back panel's ragged side-edge faces (C1j; 0: none)")
    ap.add_argument("--edge-zone", type=float, default=0.02, help="the peel's reach either side of a panel's edge (m)")
    ap.add_argument("--edge-inward", type=float, default=-0.1,
                    help="an edge face whose normal's horizontal part points in by more than this is peeled")
    ap.add_argument("--edge-island", type=int, default=12, help="loose bits of this many faces or fewer along the edges go")
    ap.add_argument("--band-button", type=float, default=0.012,
                    help="the band's side button this far beyond the bib's edge in |x| (m; 0: none)")
    ap.add_argument("--shell-decimate", default="0.32,0.22",
                    help="the top's faces kept away from its openings: arms, torso (share; 1,1: no decimation)")
    ap.add_argument("--shell-protect", default="0.035,0.03,0.02",
                    help="no decimation this near the cuffs, the neck cut and the hem (m)")
    ap.add_argument("--shell-lip", type=float, default=0.0045, help="the collar's and cuffs' lip toward the body (m)")
    ap.add_argument("--shell-per-m", type=float, default=1.29, help="the top's UV units per metre in v")
    ap.add_argument("--shell-ao", type=float, default=0.45, help="how much the AO bake darkens the top (0: no bake)")
    ap.add_argument("--shell-ao-dist", type=float, default=0.06)
    ap.add_argument("--shell-ao-samples", type=int, default=24)
    ap.add_argument("--stripe", default="0.032,0.5",
                    help="the stripes' period (m) and navy share (the chameleon's; the axolotl's 0.026,0.5)")
    ap.add_argument("--planes", choices=("fixed", "bones"), default="fixed",
                    help="bones: the cuff, seam, arm, neck, waist, bib and back planes from the character's own bones "
                         "(clothes_shell.body_planes; E1b, D3's bodies), over the flags below; fixed: the flags")
    ap.add_argument("--cuff-back", type=float, default=0.035, help="with --planes bones: the cuffs this far in from "
                    "the hand bone's head (m)")
    ap.add_argument("--ankle-keep", type=float, default=0.04,
                    help="the ankle's skin up to this far over the shoe opening's rim is never cut by the cover rays "
                         "(E1b, the collar's shards; 0: off)")
    ap.add_argument("--ankle-ride", default="0.005,0.03",
                    help="the ankle skin's LowerLeg weight goes to the Foot from this far under the shoe opening's rim "
                         "down, easing out over the band above (m: below,band; E1b; 0,0: off)")
    ap.add_argument("--collar-cut", type=float, default=0.012,
                    help="E1e: each foot's skin is bisected on one plane through the shoe opening's rim, this far "
                         "under its lowest point; everything under it goes, no face over it is deleted (m, 0: off)")
    ap.add_argument("--collar-keep", type=float, default=0.09,
                    help="E1e: the plane rule owns the leg's and foot's skin up to this far over the rim's top (m; "
                         "E1k: 6 to 9 cm, the low collar's rim is 2 to 3 cm lower, so the skin still reaches into the "
                         "turn-up and its cut edge stays hidden there)")
    ap.add_argument("--collar-ankle", type=float, default=0.08,
                    help="E1l: the collar's region also holds the ankle's skin within this far of the leg's axis, "
                         "over the rim's lowest point (m; 0: the rim's xy reach alone)")
    ap.add_argument("--collar-beside", type=int, default=1,
                    help="E1l: skin with the shoe's wall beside it at its own height counts as under the rim (1) or "
                         "only by its nearest rim point (0, E1e to E1k)")
    ap.add_argument("--front-band", type=float, default=0.015,
                    help="E1l: the instep's flattening onto the tongue's back eases out over this much over the "
                         "tongue's top (m; 0: collar_band, E1j2 to E1k)")
    ap.add_argument("--front-soft", type=float, default=0.01,
                    help="E1l: the flattening's soft ramp across the tongue's back plane, +- this (m; 0: a hard edge)")
    ap.add_argument("--collar-band", type=float, default=0.045,
                    help="E1e: the skin's shrink toward the leg's axis eases out over this much over the rim (m; E1j2: 3 cm, the leg narrows into the collar with no shards; "
                         "E1k: 4.5 cm, the low collar's ankle eases out over more)")
    ap.add_argument("--collar-clear-under", type=float, default=0.006,
                    help="E1f: the clearance inside the shoe for skin with the shoe over it (the instep: the vamp's "
                         "specks in motion; m)")
    ap.add_argument("--collar-clear", type=float, default=0.003,
                    help="E1e: the shrunk skin stays this far inside the shoe's inner wall (m)")
    ap.add_argument("--collar-weights", type=float, default=0.03,
                    help="E1e: the skin takes its nearest shoe vertex's weights up to the rim, blended back to its "
                         "own over this much over the rim (m; 0: off)")
    ap.add_argument("--hem-rest", type=float, default=-1.0,
                    help="E1j3, with the sneakers: each trouser leg's turn-up lowered so its lowest point rests this "
                         "far under the shoe's collar at the heel (m; -1: off), the shin's cloth easing over 15 cm")
    ap.add_argument("--stray", type=float, default=0.08,
                    help="garment vertices farther than this from the body go with their faces (the fit's strays: "
                         "E1b's spikes at the hips; m, 0: off)")
    ap.add_argument("--cuff-x", type=float, default=0.625, help="the cuffs' plane |x| (T-pose, m)")
    ap.add_argument("--seam-x", type=float, default=0.165, help="the sleeves' seam plane |x| (m)")
    ap.add_argument("--arm-z", type=float, default=1.18, help="the sleeves start above this height (m)")
    ap.add_argument("--arm-axis", default="0.068,1.277", help="the T-pose arms' axis: y,z (m)")
    ap.add_argument("--neck", default="-0.06,1.335,0.09,1.365",
                    help="the crew neck's plane through its front and back points: yf,zf,yb,zb (m)")
    ap.add_argument("--neck-r", type=float, default=0.09, help="the neck cut reaches this far out in |x| (m)")
    ap.add_argument("--waist", type=float, default=1.0, help="the Meshy trousers' waistband height (m)")
    ap.add_argument("--waist-z", type=float, default=None,
                    help="M2c: the waist plane at this height over --planes bones' (m; a garment whose own band sits "
                         "lower than the bones' waist: the band's edge, so no shirt texels stay over it; default: off)")
    ap.add_argument("--bib", default="0.105,1.166", help="the bib's half width and top (m)")
    ap.add_argument("--back", default="0.03,1.12,0.12,0.03",
                    help="the back panel: least y, apex z, half width at the waist and at the apex (m)")
    ap.add_argument("--shell-strap-t", default="-118,20,134",
                    help="the new straps' angles round the shoulder axis: front, shoulder, back (degrees)")
    ap.add_argument("--shell-strap-x", default="0.078,0.10,0.015", help="the new straps' |x| at those angles (m)")
    ap.add_argument("--strap-back-below", type=float, default=0.032,
                    help="with --planes bones the straps' back ends reach this far under the back panel's apex (m)")
    ap.add_argument("--shell-strap-off", type=float, default=0.010, help="the new straps' least distance off the body")
    ap.add_argument("--shell-strap-step", type=float, default=6.0, help="degrees between the new straps' stations")
    ap.add_argument("--shell-strap-lats", type=int, default=5, help="the new straps' vertices across (lips included)")
    ap.add_argument("--shell-strap-reach", type=float, default=0.04,
                    help="the new straps clear the outermost kept surface this far along the body's normal (m)")
    ap.add_argument("--strap-lip-u", type=float, default=0.1, help="each lip's share of the strap patch's width")
    ap.add_argument("--stitch", default="0.003,0.003,0.002",
                    help="the straps' two stitch lines: inset from each edge, dash, gap (m)")
    ap.add_argument("--buckle", default="0.01,0.036",
                    help="the button's and the buckle ring's places along each strap from its front end (m)")
    ap.add_argument("--buckle-size", default="0.004,0.011,0.004,0.0035",
                    help="the ring's margin past the strap, half length, bar width, height; m")
    ap.add_argument("--button-size", default="0.0065,0.003,0.001", help="the button's radius, height, dome (m)")
    ap.add_argument("--strap-front", type=float, default=0.09,
                    help="the Meshy bib under this much of each strap's front goes (m)")
    ap.add_argument("--stitch-colour", default="0.78,0.48,0.22", help="the straps' stitching, the sketch's orange (sRGB)")
    ap.add_argument("--shell-hide-above", type=float, default=None,
                    help="E1h: the top's faces under the panels go from this height over the waist (m; default: from "
                         "--shell-full)")
    ap.add_argument("--plain", default="",
                    help="E1h: boxes x0,x1,y0,y1,z0,z1 (|x|, bind pose, m; ';' between) whose denim gets plain texels "
                         "(clothes_top.plain_denim; empty: off)")
    ap.add_argument("--flat-bib", default="",
                    help="E1i: the bib as a flat, stiff panel: blend,curve,radius,clear (m, 1/m (<0: fitted), m, m; "
                         "clothes_top.flat_bib; empty: off)")
    ap.add_argument("--bib-raise", default="",
                    help="E1i: with --flat-bib, the bib raised dz over the band waist+b0..waist+b1: dz,b0,b1 (m)")
    ap.add_argument("--fill-holes-above", type=float, default=None,
                    help="E1i2: fill the small holes up to this height over the waist (m; default: under the waist "
                         "only)")
    ap.add_argument("--bib-chain", default="",
                    help="E1i2: with --flat-bib, the bib's weights by height along these bones (up the spine, comma "
                         "separated; clothes_shell.chain_row; empty: the rows' means of the body's weights)")
    ap.add_argument("--plain-density", type=float, default=1.0,
                    help="E1h: the plain texels' density against the garment's median")
    ap.add_argument("--bronze", default="0.60,0.42,0.20,0.85,0.38",
                    help="the buckles' metal: sRGB R,G,B, metallic, roughness")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    out = Path(args.out)
    glb = out / f"{args.name}_char.glb"
    if glb.exists():
        say("REFUSED", glb, "exists")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.char).resolve()))
    arm = bpy.data.objects["CharacterArmature"]
    import clothes_open as O
    try:
        char = O.body_mesh(arm, [], args.name)
    except ValueError as e:
        say("REFUSED", e)
        return 3
    rep = {"char": args.char, "fit": args.fit, "mesh": char.name, "tris_before": tris(char)}
    with bpy.data.libraries.load(str(Path(args.fit).resolve())) as (src, dst):
        dst.objects = [n for n in src.objects if n in PIECES or n == "CharacterArmature"]
    farm = next(o for o in dst.objects if o.type == "ARMATURE")
    # the bones the cloth is weighted to must rest where the character's do (the head's own bones may differ)
    used = {g.name for o in dst.objects if o.type == "MESH" for g in o.vertex_groups
            if any(g.index == vg.group and vg.weight > 0 for v in o.data.vertices for vg in v.groups)}
    diffs = {b.name: max((farm.data.bones[b.name].head_local - b.head_local).length,
                         (farm.data.bones[b.name].tail_local - b.tail_local).length)
             for b in arm.data.bones if b.name in farm.data.bones}
    missing = sorted(used - set(diffs))
    if not used or missing:
        say("REFUSED the fit's cloth bones", sorted(used), "are not all the character's: missing", missing)
        return 3
    rest_diff = max(diffs[n] for n in used)
    rep["fit_armature_rest_diff_mm"] = round(rest_diff * 1000, 4)
    rep["other_bones_differing"] = sorted(n for n, d in diffs.items() if d > 1e-4 and n not in used)
    say("cloth bones", len(used), "rest diff mm", rep["fit_armature_rest_diff_mm"], "others differing",
        rep["other_bones_differing"])
    if rest_diff > 1e-4:
        say("REFUSED the fit's armature rest differs from the character's by", rest_diff, "m")
        return 3
    cloth = [o for o in dst.objects if o.type == "MESH"]
    for o in cloth:
        bpy.context.scene.collection.objects.link(o)
        for m in o.modifiers:
            if m.type == "ARMATURE":
                m.object = arm
        o.parent = arm
        o.matrix_parent_inverse = arm.matrix_world.inverted()
    bpy.data.objects.remove(farm)
    if args.body_from:
        a, b = body_co(args.body_from), body_co(args.body_to)
        kd = KDTree(len(a))
        for i, p in enumerate(a):
            kd.insert(p, i)
        kd.balance()
        inv = char.matrix_world.inverted()
        polys = body_polys(args.body_from)
        tree = BVHTree.FromPolygons([tuple(c) for c in a], polys)
        diff = b - a
        matched = moved = followed = 0
        for v in char.data.vertices:
            p = char.matrix_world @ v.co
            _co, i, d = kd.find(p)
            if d < 1e-5:
                matched += 1
                dv = Vector(diff[i])
            else:  # a vertex the build moved off the body (the welds, smoothing): the nearest face's difference
                loc, _n, fi, dist = tree.find_nearest(p, 0.03)
                if loc is None:
                    continue
                vs = polys[fi]
                bary = poly_3d_calc([Vector(a[k]) for k in vs], loc)
                dv = Vector(sum(w * diff[k] for k, w in zip(vs, bary)))
                followed += dv.length > 1e-7
            if dv.length > 1e-7:
                moved += 1
                v.co = inv @ (p + dv)
        char.data.update()
        rep["body_variant"] = {"from": args.body_from, "to": args.body_to, "matched": matched, "moved": moved,
                               "followed_nearest_face": followed,
                               "unmatched": len(char.data.vertices) - matched}
        say("body variant", rep["body_variant"])
    if args.planes == "bones":
        bw = lambda n: arm.matrix_world @ arm.data.bones[n].head_local
        try:
            ua, hand = bw("LeftUpperArm"), bw("LeftHand")
            pl = H.body_planes(bw("Chest").z, bw("Neck").z, bw("Neck").y, tuple(ua), hand.x, args.cuff_back,
                                 waist_z=args.waist_z)
        except KeyError as e:
            say("REFUSED --planes bones: no bone", e)
            return 3
        args.cuff_x, args.seam_x, args.arm_z = pl["cuff_x"], pl["seam_x"], pl["arm_z"]
        args.waist = pl["waist"]
        args.arm_axis = ",".join(f"{v:.4f}" for v in pl["arm_axis"])
        args.bib = ",".join(f"{v:.4f}" for v in pl["bib"])
        args.back = ",".join(f"{v:.4f}" for v in pl["back"])
        # E1d: the straps' back ends reach strap_back_below under the back panel's apex on every body (the shorter
        # body's straps met over it: a flat bar of shirt and panel under their V)
        args.strap_back_z = pl["back"][1] - args.strap_back_below
        args.neck = ",".join(f"{v:.4f}" for v in pl["neck"])
        rep["planes"] = {k: (round(v, 4) if isinstance(v, float) else [round(x, 4) for x in v]) for k, v in pl.items()}
        say("planes from the bones", rep["planes"])
    if args.sneakers == "on" or (args.sneakers == "auto" and args.shell):
        import sneaker_build as SB
        old = next((o for o in cloth if o.name == "shoes"), None)
        if old is not None:
            cloth.remove(old)
            bpy.data.objects.remove(old)
        try:
            new, rep["sneakers"] = SB.shoes(char, arm)
        except ValueError as e:
            say("REFUSED the sneakers:", e)
            return 3
        cloth.append(new)
        say("sneakers", {k: rep["sneakers"][k] for k in ("tris_pair", "foot", "clearance", "rim_z_min_max")})
        if args.toes_cap:
            cap = SB.toes_cap(args.toes_cap)
            if cap:
                ba = SB.cap_toes(cap)
                rep["toes_cap"] = {"settings": cap, "clips_before_after_deg": ba}
                if ba:
                    say("toes cap", cap, "largest before / after", max(v[0] for v in ba.values()),
                        max(v[1] for v in ba.values()))
                else:  # no clip had a toe bend to cap: report it, never crash on max() over nothing
                    say("toes cap", cap, "no clip capped")
    garment = next((o for o in cloth if o.name == "garment"), None)
    if args.stray > 0 and garment is not None:  # E1b: the fit's stray vertices (spikes out of the hips)
        btree = BVHTree.FromObject(char, bpy.context.evaluated_depsgraph_get())
        gm = garment.matrix_world
        bad = [v.index for v in garment.data.vertices if btree.find_nearest(gm @ v.co, args.stray)[0] is None]
        if bad:
            bm = bmesh.new()
            bm.from_mesh(garment.data)
            bm.verts.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.verts[i] for i in bad], context="VERTS")
            bm.to_mesh(garment.data)
            bm.free()
            garment.data.update()
        rep["garment_stray_verts_removed"] = len(bad)
        say("garment strays removed", len(bad))
    shoe_ob = next((o for o in cloth if o.name == "shoes"), None)
    if args.hem_rest >= 0 and garment is not None and shoe_ob is not None and "heel_rim_z" in shoe_ob.keys():
        # E1j3: the turn-up rests on the collar, as on the concept (the leg's skin between them showed as a band): per
        # angle round each leg (24 bins about the hem's middle) the hem's lowest point goes down to the shoe's top
        # there less hem_rest (the hem was higher at the front and outside than at the back)
        gm, gi = garment.matrix_world, garment.matrix_world.inverted()
        sm = shoe_ob.matrix_world
        rim_z, hems, nb = float(shoe_ob["heel_rim_z"]), {}, 24
        sv = [sm @ v.co for v in shoe_ob.data.vertices]
        gw = [gm @ v.co for v in garment.data.vertices]

        def ang(p, ctr):
            return int(((math.atan2(p.y - ctr.y, p.x - ctr.x) / (2 * math.pi)) % 1.0) * nb) % nb
        for sgn in (1.0, -1.0):
            low = [p for p in gw if p.x * sgn > 0.02 and p.z < 0.4]
            if not low:
                continue
            hz = min(p.z for p in low)
            ring = [p for p in low if p.z < hz + 0.07]
            ctr = sum(ring, Vector()) / len(ring)
            hem_b, top_b = [None] * nb, [None] * nb
            for p in ring:
                a = ang(p, ctr)
                hem_b[a] = p.z if hem_b[a] is None else min(hem_b[a], p.z)
            for p in sv:
                if p.x * sgn > 0 and (p.xy - ctr.xy).length < 0.12:
                    a = ang(p, ctr)
                    top_b[a] = p.z if top_b[a] is None else max(top_b[a], p.z)
            drops = F.hem_drops(hem_b, top_b, args.hem_rest)
            hems["left" if sgn > 0 else "right"] = {"hem_z": round(hz, 4), "drop_mm_min_max": [
                round(1000 * min(drops), 1), round(1000 * max(drops), 1)]}
            for v, p in zip(garment.data.vertices, gw):
                if p.x * sgn > 0.02 and p.z < hz + 0.25:
                    t = ((math.atan2(p.y - ctr.y, p.x - ctr.x) / (2 * math.pi)) % 1.0) * nb - 0.5
                    i0 = math.floor(t)
                    f = t - i0
                    d = drops[i0 % nb] * (1 - f) + drops[(i0 + 1) % nb] * f
                    if d > 0:
                        q = p.copy()
                        q.z -= F.hem_shift(p.z, hz, d)
                        v.co = gi @ q
        garment.data.update()
        rep["hem_rest"] = {"heel_rim_z": round(rim_z, 4), **hems}
        say("hem rest", rep["hem_rest"])
    if args.fill_holes > 0 and garment is not None:  # E1g: Meshy's small holes in the trousers (the dark divots)
        import clothes_top as TOP
        rep["holes_filled"] = TOP.fill_holes(garment, args)
    if args.despike > 0 and garment is not None:  # E1g: the hips' spikes
        import clothes_top as TOP
        rep["despike"] = TOP.despike(garment, char, args)
    if args.seat_wrap > 0 and garment is not None:  # E1f: the seat's folds re-laid on the body
        import clothes_top as TOP
        rep["seat_wrap"] = TOP.seat_wrap(garment, char, args)
    if args.shell and garment is not None:  # the hybrid route: our own top, bib, back and straps (clothes_top)
        import clothes_top as TOP
        try:
            args.stripe_cols = TOP.stripe_colours(garment)
        except ValueError as e:
            say("REFUSED", e)
            return 3
        rep["garment_cut"] = TOP.cut_garment(garment, args)
        if args.flat_bib:  # E1i: her bib a flat, stiff panel over the chest (the concept), before the top and straps
            rep["flat_bib"] = TOP.flat_bib(garment, char, args)
        top, rep["shell"] = TOP.shell(char, arm, garment, args)
        rep["straps"] = TOP.straps(garment, char, [garment, top], args)
        if args.plain:  # E1h: plain denim texels over the areas whose own texels are wrong
            rep["plain_denim"] = TOP.plain_denim(garment, args)
        cloth.append(top)
    gname = {g.index: g.name for g in char.vertex_groups}
    # the covered faces
    tree = cloth_tree(cloth)
    me = char.data
    mw = char.matrix_world
    nmat = mw.to_3x3().inverted().transposed()
    # the cloth's real openings (collar, cuffs, hems, the shoes' tops): no cut reaches past them
    import clothes_open as O
    edge, rep["openings"] = O.opening_points(cloth, arm)
    say("openings", len(edge), "points:", rep["openings"])
    ekd = O.kd_of(edge)
    # a shoe is closed: the foot inside it (Foot and Toes, below the shoe's top opening) never shows
    # (each shoe its own top, by side; and any foot vertex with the shoe above it, the toes under the toe box)
    shoe = next((o for o in cloth if o.name == "shoes"), None)
    top_z = {1.0: None, -1.0: None}
    stree = None
    rim_kd, rim_pts, main_rim = None, [], []
    if shoe is not None:
        # E1c: the opening's own rim, the boundary of each shoe's main island (the eyelets' and laces' small islands
        # left out: their edges pulled the rim's centre onto the instep); E1d: every rim rule uses it (the old rim's
        # lace points over the instep cut holes into the ankle's front and left the dark blocks there)
        bm = bmesh.new()
        bm.from_mesh(shoe.data)
        bm.verts.ensure_lookup_table()
        seen, big = set(), set()
        for v0 in bm.verts:
            if v0.index in seen:
                continue
            isl, st = [], [v0]
            seen.add(v0.index)
            while st:
                a = st.pop()
                isl.append(a.index)
                for e in a.link_edges:
                    b = e.other_vert(a)
                    if b.index not in seen:
                        seen.add(b.index)
                        st.append(b)
            if len(isl) >= 100:
                big.update(isl)
        bz = [shoe.matrix_world @ v.co for v in bm.verts if v.is_boundary and v.index in big]
        bm.free()
        main_rim = [q for q in bz if q.z > 0.05]
        for sgn in top_z:
            top_z[sgn] = F.shoe_top([q.z for q in bz if q.x * sgn > 0], args.shoe_margin)
        # the opening's rim across the floor (x, y): each foot vertex is cut below the rim where it stands
        rim_pts = main_rim
        rim_kd = KDTree(max(1, len(rim_pts)))
        for i, q in enumerate(rim_pts):
            rim_kd.insert((q.x, q.y, 0.0), i)
        rim_kd.balance()
        rim_kd3 = KDTree(max(1, len(rim_pts)))
        for i, q in enumerate(rim_pts):
            rim_kd3.insert(q, i)
        rim_kd3.balance()
        sv = [shoe.matrix_world @ v.co for v in shoe.data.vertices]
        stree = BVHTree.FromPolygons(sv, [list(p.vertices) for p in shoe.data.polygons])
    rep["shoe_top_z"] = {("left" if k > 0 else "right"): (None if t is None else round(t, 4)) for k, t in top_z.items()}
    up = Vector((0.0, 0.0, 1.0))
    cov, sure, outside, in_shoe, by_rim, by_wall, n_under = [], [], 0, 0, 0, 0, 0
    legs = ("Foot", "Toes", "LowerLeg")
    n_ankle = 0
    thru, low_foot = [False] * len(me.vertices), [False] * len(me.vertices)
    footw = [0.0] * len(me.vertices)
    for v in me.vertices:
        p = mw @ v.co
        n = (nmat @ v.normal).normalized()
        foot = sum(g.weight for g in v.groups if gname.get(g.group, "").endswith(("Foot", "Toes")))
        toes = sum(g.weight for g in v.groups if gname.get(g.group, "").endswith("Toes"))
        footw[v.index] = foot
        top = top_z[1.0 if p.x > 0 else -1.0]
        under = foot >= 0.5 and stree is not None and stree.ray_cast(p + up * 1e-4, up, 0.15)[0] is not None
        rim = None
        if foot >= 0.5 and rim_pts:
            near_rim = [rim_pts[j].z for _c, j, _d in rim_kd.find_range((p.x, p.y, 0.0), args.rim_reach)
                        if rim_pts[j].x * p.x > 0]
            rim = F.local_rim(near_rim, args.rim_margin)
            low_foot[v.index] = bool(near_rim) and p.z < max(near_rim)
        through = False
        if foot >= 0.5 and stree is not None and rim_pts:
            sloc, snor, _sf, _sd = stree.find_nearest(p)
            if sloc is not None:
                through = F.through_shoe((p - sloc).dot(snor), rim_kd3.find(sloc)[2])
                thru[v.index] = through
        if through or F.in_shoe(foot, p.z, top, under=under, toes_weight=toes, shoe=stree is not None, rim=rim):
            cov.append(True)
            sure.append(True)
            in_shoe += 1
            by_rim += not F.in_shoe(foot, p.z, top, under=under, toes_weight=toes, shoe=stree is not None)
            by_wall += through
            continue
        if rim_pts and p.z < 0.3 and any(g.weight > 0 and gname.get(g.group, "").endswith(legs) for g in v.groups):
            _c, j, dxy = rim_kd.find((p.x, p.y, 0.0))
            if rim_pts[j].x * p.x > 0 and F.ankle_kept(p.z, rim_pts[j].z, dxy, args.ankle_keep):
                cov.append(False)
                sure.append(False)
                n_ankle += 1
                continue
        top_bone = gname.get(max(v.groups, key=lambda g: g.weight).group, "") if v.groups else ""
        loc, nor, _fi, _d = tree.find_nearest(p, args.near)
        if loc is not None and F.under_cloth((p - loc).dot(nor), H.opening_dist(ekd.find(p)[2]), top_bone, away=args.away,
                                              away_shoulder=args.away_shoulder):
            cov.append(True)
            sure.append(True)
            n_under += 1
            continue
        sure.append(False)
        hit = all(tree.ray_cast(p + d * 1e-4, d, args.reach)[0] is not None for d in rays(n))
        if not hit:  # the body outside the cloth (a shoulder): covered if the cloth lies within --outside behind it
            loc, _nor, _fi, t = tree.ray_cast(p, -n, args.outside)
            near = args.opening_leg if top_bone.endswith("LowerLeg") else args.opening
            if loc is not None and H.opening_dist(ekd.find(loc)[2]) >= near:
                q = loc - n * 1e-3
                hit = all(tree.ray_cast(q + d * 1e-4, d, args.reach)[0] is not None for d in rays(n))
                outside += hit
        cov.append(hit)
    rep["covered_from_outside"] = outside
    rep["ankle_kept_over_the_rim"] = n_ankle
    rep["covered_in_shoes"] = in_shoe
    rep["covered_in_shoes_by_rim"] = by_rim
    rep["covered_through_shoe_walls"] = by_wall
    rep["covered_under_the_cloth"] = n_under
    faces = [list(p.vertices) for p in me.polygons]
    by_edge: dict[tuple[int, int], list[int]] = {}
    for fi, p in enumerate(me.polygons):
        for ek in p.edge_keys:
            by_edge.setdefault(ek, []).append(fi)
    nbrs = [sorted({j for ek in p.edge_keys for j in by_edge[ek] if j != fi}) for fi, p in enumerate(me.polygons)]
    gone = F.covered_faces(faces, cov, nbrs, erode=1, vert_sure=sure)
    shoe_faces = [not g and F.shoe_face([thru[k] for k in f], [low_foot[k] or sure[k] for k in f])
                  for g, f in zip(gone, faces)]
    gone = [g or x for g, x in zip(gone, shoe_faces)]
    # E1c, the collar's clean cut: the ankle's faces between the plane under the rim and the rim's top come back
    # (their removal left the staircase of teal shards over the collar); the bisect below cuts them on the plane
    collar = {}
    if args.collar_cut > 0 and stree is not None and main_rim:
        for sgn in (1.0, -1.0):
            side_rim = [q for q in main_rim if q.x * sgn > 0]
            if len(side_rim) < 8:
                continue
            zs = sorted(q.z for q in side_rim)
            side_rim = [q for q in side_rim if q.z > zs[len(zs) // 2] - 0.025]
            ctr = sum(side_rim, Vector()) / len(side_rim)
            reach = max((q - ctr).xy.length for q in side_rim) + 0.03
            collar[sgn] = {"plane": F.rim_plane([tuple(q) for q in side_rim], args.collar_cut), "ctr": ctr,
                           "reach": reach, "top": max(q.z for q in side_rim), "low": min(q.z for q in side_rim)}
        # E1e: the plane alone decides the leg's and foot's skin near each shoe (up to collar_keep over the rim's
        # top, within the rim's reach): a face goes only when it lies wholly under the plane; every face with a
        # vertex over it stays (the bisect below cuts the crossing ones into one clean loop). E1b to E1d's per-face
        # deletes near the rim (cover rays, in-shoe, through-wall, column, vamp) each left a sawtooth at the collar.
        # E1l: also the ankle's skin within collar_ankle of the leg's axis (the rim's reach missed the ankle's
        # forward-leaning front: a jagged vertical skin edge inside the turn-up)
        leg_axes = {}
        for sgn, side in ((1.0, "Left"), (-1.0, "Right")):
            bone = arm.data.bones.get(side + "LowerLeg")
            if bone is not None:
                leg_axes[sgn] = (tuple(arm.matrix_world @ bone.head_local), tuple(arm.matrix_world @ bone.tail_local))
        n_ankle_region = [0]

        def in_reach(c: dict, p: Vector, extra: float = 0.0) -> bool:
            if (p.xy - c["ctr"].xy).length <= c["reach"] + extra:
                return True
            ax = leg_axes.get(1.0 if p.x > 0 else -1.0)
            return (args.collar_ankle > 0 and ax is not None
                    and F.near_ankle(p.z, F.axis_dist(ax[0], ax[1], tuple(p)), c["low"], c["top"] + args.collar_keep,
                                     args.collar_ankle + extra))

        wco = [mw @ v.co for v in me.vertices]
        region, over = [False] * len(wco), [False] * len(wco)
        for k, p in enumerate(wco):
            c = collar.get(1.0 if p.x > 0 else -1.0)
            if c is None or p.z > c["top"] + args.collar_keep or not in_reach(c, p):
                continue
            n_ankle_region[0] += (p.xy - c["ctr"].xy).length > c["reach"]
            v = me.vertices[k]
            if not any(g.weight > 0 and gname.get(g.group, "").endswith(legs) for g in v.groups):
                continue
            region[k] = True
            over[k] = p.z >= F.plane_z(c["plane"], p.x, p.y)
        back, under = 0, 0
        for fi, f in enumerate(faces):
            if not all(region[k] for k in f):
                continue
            keep = any(over[k] for k in f)
            back += gone[fi] and keep
            under += (not gone[fi]) and not keep
            gone[fi] = not keep
        rep["collar"] = {("left" if k > 0 else "right"): {"plane": [round(x, 4) for x in c["plane"]],
                                                          "rim_low": round(c["low"], 4), "rim_top": round(c["top"], 4),
                                                          "reach": round(c["reach"], 4)} for k, c in collar.items()}
        rep["collar"]["faces_back"] = back
        rep["collar"]["ankle_verts_beyond_reach"] = n_ankle_region[0]
        rep["collar"]["faces_under_plane_removed"] = under
    rep["faces_removed_through_shoe_walls"] = sum(shoe_faces)
    # the removed part, kept in the blend for the proof's gap check (C1k): its own object with the body's weights and
    # armature modifier, not parented to the armature, so the GLB leaves it out (alien_loco._export)
    rem = char.copy()
    rem.data = char.data.copy()
    rem.name = rem.data.name = "body_removed"
    bpy.context.scene.collection.objects.link(rem)
    mwc = char.matrix_world.copy()
    rem.parent = None
    rem.matrix_world = mwc
    rem.hide_render = True
    rbm = bmesh.new()
    rbm.from_mesh(rem.data)
    rbm.faces.ensure_lookup_table()
    bmesh.ops.delete(rbm, geom=[rbm.faces[i] for i, g in enumerate(gone) if not g], context="FACES")
    bmesh.ops.delete(rbm, geom=[v for v in rbm.verts if not v.link_faces], context="VERTS")
    rbm.to_mesh(rem.data)
    rbm.free()
    rep["removed_body_kept_verts"] = len(rem.data.vertices)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i, g in enumerate(gone) if g], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    if collar:  # E1c: the ankle bisected on each collar's plane, everything under it near the shoe goes
        inv = mw.inverted()
        bm = bmesh.new()
        bm.from_mesh(me)
        cut = 0
        for sgn, c in collar.items():
            a, b, _c = c["plane"]
            vs = [v for v in bm.verts if (mw @ v.co).x * sgn > 0 and (mw @ v.co).z < c["top"] + 0.06
                  and in_reach(c, mw @ v.co, 0.03)]
            if not vs:
                continue
            vset = set(vs)
            fs = [f for f in {f for v in vs for f in v.link_faces} if all(x in vset for x in f.verts)]
            es = list({e for f in fs for e in f.edges})
            vs = list({x for f in fs for x in f.verts})
            co = inv @ Vector((c["ctr"].x, c["ctr"].y, F.plane_z(c["plane"], c["ctr"].x, c["ctr"].y)))
            no = (mw.to_3x3().transposed() @ Vector((-a, -b, 1.0))).normalized()
            n0 = len(bm.faces)
            bmesh.ops.bisect_plane(bm, geom=vs + es + fs, dist=1e-6, plane_co=co, plane_no=no, clear_inner=True)
            cut += n0 - len(bm.faces)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(me)
        bm.free()
        me.update()
        # E1e: the skin between the plane and the rim (easing out collar_band over it) is shrunk toward the leg's
        # own axis (the LowerLeg bone's line, extended down) until it lies collar_clear inside the shoe's inner
        # wall: the wall is found by a ray from the axis out toward the vertex at its own height (over the rim: at
        # the rim's height, so the shrink eases out with no step)
        axes = {}
        for sgn, side in ((1.0, "Left"), (-1.0, "Right")):
            bone = arm.data.bones.get(side + "LowerLeg")
            if bone is not None and sgn in collar:
                axes[sgn] = (arm.matrix_world @ bone.head_local, arm.matrix_world @ bone.tail_local)

        def axis_at(sgn: float, z: float) -> Vector:
            h, t = axes[sgn]
            k = (z - h.z) / (t.z - h.z) if abs(t.z - h.z) > 1e-6 else 0.0
            return h + (t - h) * k

        def wall(o: Vector, d: Vector, most: float) -> float | None:
            loc, _n, _f, t = stree.ray_cast(o, d, most)
            return None if loc is None else t

        shrunk, most_mm, beside = 0, 0.0, 0
        new_co = {}
        # E1j2: the foot's skin ahead of the tongue's back (the instep under the laces and the vamp) is flattened onto
        # that vertical plane, under the tongue's top (easing out collar_band over it): the shoe can take a slimmer
        # last than the soft foot, and nothing shows under the laces or pokes through the vamp
        fronts = {}
        for sgn, side in ((1.0, "Left"), (-1.0, "Right")):
            if f"front_{side}" in shoe.keys():
                fronts[sgn] = (Vector(tuple(shoe[f"front_{side}"])), Vector(tuple(shoe[f"fwd_{side}"])),
                               float(shoe["front_top_z"]))
        flat = 0
        for v in me.vertices:
            p = mw @ v.co
            sgn = 1.0 if p.x > 0 else -1.0
            c = collar.get(sgn)
            if c is None or sgn not in axes or p.z > c["top"] + args.collar_keep:
                continue
            fp = fronts.get(sgn)
            if fp is not None and (p.xy - c["ctr"].xy).length <= c["reach"] + 0.03:
                ahead = (p.xy - fp[0]).dot(fp[1])
                # E1l: eased out over front_band over the tongue's top (collar_band's 4.5 cm flattened the ankle's
                # front up into the turn-up), with a soft ramp across the plane (no vertical crease on the ankle)
                t = max(0.0, min(1.0, (p.z - fp[2]) / (args.front_band or args.collar_band)))
                k = 1.0 - t * t * (3 - 2 * t)
                back = F.soft_flat(ahead, k, args.front_soft) if k > 0 else 0.0
                if back > 0:
                    p = Vector((p.x - fp[1].x * back, p.y - fp[1].y * back, p.z))
                    new_co[v.index] = inv @ p
                    flat += 1
            _c, j, _dxy = rim_kd.find((p.x, p.y, 0.0))
            rz = rim_pts[j].z
            # skin with the shoe over it or just under it (the instep under the vamp or poking through it, beside
            # the throat's low slot) counts as under the rim wherever its nearest rim point lies
            over = (stree.ray_cast(p + up * 1e-4, up, 0.1)[0] is not None
                    or stree.ray_cast(p - up * 1e-4, -up, 0.012)[0] is not None)
            if over:
                rz = max(rz, p.z + 0.002)
            ax = axis_at(sgn, p.z)
            d = Vector((p.x - ax.x, p.y - ax.y, 0.0))
            r = d.length
            if r < 1e-5:
                continue
            d /= r
            # E1l: skin with the shoe's wall beside it at its own height is under the rim too, wherever its nearest
            # rim point (in xy) lies: the collar's height changes fast between the heel and the side, and that skin
            # was eased out through the padding (the teal specks on the collar at the heel and outside)
            if args.collar_beside and p.z <= rz + args.collar_band and in_reach(c, p)                     and wall(Vector((ax.x, ax.y, p.z)), d, r + 0.05) is not None and p.z + 0.002 > rz:
                rz = p.z + 0.002
                beside += 1
            if p.z > rz + args.collar_band or not in_reach(c, p):
                continue
            h = min(p.z, rz - 0.002)
            o = Vector((ax.x, ax.y, h)) if h == p.z else axis_at(sgn, h)
            t = wall(Vector((o.x, o.y, h)), d, r + 0.05)
            if t is None:
                continue
            r2 = F.collar_clamp(r, t, p.z, rz, args.collar_clear_under if over else args.collar_clear,
                                args.collar_band)
            if r2 < r - 1e-6:
                new_co[v.index] = inv @ Vector((ax.x + d.x * r2, ax.y + d.y * r2, p.z))
                shrunk += 1
                most_mm = max(most_mm, 1000 * (r - r2))
        for i, q in new_co.items():
            me.vertices[i].co = q
        me.update()
        rep["collar"]["shrunk"] = shrunk
        rep["collar"]["beside_the_wall"] = beside
        rep["collar"]["flattened_front"] = flat
        rep["collar"]["shrunk_most_mm"] = round(most_mm, 1)
        rep["collar"]["faces_cut"] = cut
        # E1e: the same skin moves as one with the shoe: up to the rim it takes its nearest shoe vertex's weights,
        # blended back to its own over collar_weights over the rim
        took = 0
        if args.collar_weights > 0:
            sg = {g.index: g.name for g in shoe.vertex_groups}
            skd = KDTree(len(shoe.data.vertices))
            for sv0 in shoe.data.vertices:
                skd.insert(shoe.matrix_world @ sv0.co, sv0.index)
            skd.balance()
            vg = {g.name: g for g in char.vertex_groups}
            for v in me.vertices:
                p = mw @ v.co
                c = collar.get(1.0 if p.x > 0 else -1.0)
                if c is None or p.z > c["top"] + args.collar_weights or (p.xy - c["ctr"].xy).length > c["reach"]:
                    continue
                _c, j, _dxy = rim_kd.find((p.x, p.y, 0.0))
                f = F.ankle_ride(p.z, rim_pts[j].z, 0.0, args.collar_weights)
                if f <= 0:
                    continue
                _q, si, _d = skd.find(p)
                theirs = {sg[g.group]: g.weight for g in shoe.data.vertices[si].groups if g.group in sg}
                if not theirs:
                    continue
                own = {gname[g.group]: g.weight for g in v.groups if g.group in gname}
                row = F.mix_rows(own, theirs, f)
                for name in set(own) - set(row):
                    vg[name].remove([v.index])
                for name, w in row.items():
                    if name not in vg:
                        vg[name] = char.vertex_groups.new(name=name)
                        gname[vg[name].index] = name
                    vg[name].add([v.index], w, "REPLACE")
                took += 1
        rep["collar"]["shoe_weights"] = took
        say("collar", rep["collar"])
    rep["covered_vertices"] = sum(cov)
    rep["faces_removed"] = sum(gone)
    below, band = (float(v) for v in args.ankle_ride.split(","))
    if band > 0 and rim_pts and not collar:  # E1b (off with E1e's collar): the skin under the collar rides with the
        # shoe (its Foot), not the shin
        rode = 0
        for v in me.vertices:
            p = mw @ v.co
            if p.z > 0.3:
                continue
            side = "Left" if p.x > 0 else "Right"
            _c, j, dxy = rim_kd.find((p.x, p.y, 0.0))
            gl, gf = char.vertex_groups.get(side + "LowerLeg"), char.vertex_groups.get(side + "Foot")
            if dxy > 0.06 or gl is None or gf is None:
                continue
            wl = next((g.weight for g in v.groups if g.group == gl.index), 0.0)
            share = F.ankle_ride(p.z, rim_pts[j].z, below, band)
            if wl <= 0 or share <= 0:
                continue
            wf = next((g.weight for g in v.groups if g.group == gf.index), 0.0)
            gf.add([v.index], wf + share * wl, "REPLACE")
            gl.add([v.index], wl * (1 - share), "REPLACE")
            rode += 1
        rep["ankle_rides_with_the_shoe"] = rode
        say("ankle verts riding with the shoe", rode)
    if collar:  # E1c, the outer-shell probe: kept skin under the rim with no shoe face on its way out
        outs = 0
        for v in me.vertices:
            p = mw @ v.co
            c = collar.get(1.0 if p.x > 0 else -1.0)
            if c is None or p.z >= c["top"] or (p.xy - c["ctr"].xy).length >= c["reach"]:
                continue
            nr = min((q for q in main_rim if q.x * p.x > 0), key=lambda q: (q.xy - p.xy).length)
            d = Vector((p.x - c["ctr"].x, p.y - c["ctr"].y, 0.0))
            if p.z >= nr.z or d.length < 1e-5:
                continue
            d.normalize()
            outs += F.outside_shell(int(stree.ray_cast(p + d * 1e-4, d, 0.1)[0] is not None))
        rep["collar_shell_probe"] = {"kept_under_rim_outside_shell": outs}
        say("collar shell probe", rep["collar_shell_probe"])
    if stree is not None and rim_pts:  # E1b, the collar probe: kept skin under the rim outside the shoe's surface
        outs = []
        for v in me.vertices:
            p = mw @ v.co
            if p.z > 0.3:
                continue
            _c, j, dxy = rim_kd.find((p.x, p.y, 0.0))
            if dxy > 0.06 or rim_pts[j].x * p.x <= 0 or not (rim_pts[j].z - 0.02 <= p.z < rim_pts[j].z):
                continue
            sloc, snor, _sf, _sd = stree.find_nearest(p)
            if sloc is not None and (p - sloc).dot(snor) > 0.001:
                outs.append((p - sloc).length)
        rep["collar_probe"] = {"kept_under_rim_outside_shoe": len(outs),
                               "max_mm": round(1000 * max(outs), 1) if outs else 0.0}
        say("collar probe", rep["collar_probe"])
    rep["tris"] = {"body": tris(char), **{o.name: tris(o) for o in cloth}}
    rep["tris"]["cloth"] = sum(tris(o) for o in cloth)
    rep["tris"]["total"] = rep["tris"]["body"] + rep["tris"]["cloth"]
    say("covered", sum(cov), "vertices,", in_shoe, "in the shoes (", by_rim, "by the rim,", by_wall,
        "through the walls ),", n_under,
        "under the cloth for certain,", sum(gone),
        "faces removed; tris", rep["tris"])
    rep["maps"] = maps(cloth, not args.no_fill, tuple(float(v) for v in args.denim_gain.split(",")))
    blend = out / f"{args.name}_char.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    import alien_loco
    alien_loco._export(arm, glb)
    rep["glb"] = str(glb)
    rep["clips"] = sorted(a.name for a in bpy.data.actions)
    (out / "dress.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    say("wrote", glb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
