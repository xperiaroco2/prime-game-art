"""The alien parts kit's body rebuilt from a clean cage (art #196, step S4a): a symmetric low-poly quad cage built by
measurement to the approved u1 turnaround, subdivided (Catmull-Clark, level 2, applied) into a smooth designer-toy
body with its hands built in the same cage (S8: a palm, three fingers and a thumb, one surface with the arm), and
the standard neck ring of S1 unchanged, on S1c's contract skeleton and clips.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_cage.py -- \
        --src <S1c/build/alien_body.blend> --ring <S1/build/neck_ring.json> --out <dir> [--target <body.glb>]

Writes <out>/alien_body.blend (a saved character for `tools/run.py export` and `alien_assemble.py`, with the cage kept
as the hidden object `BodyCage`), <out>/neck_ring.json (S1's, copied unchanged: the assembler reads it beside the
body) and <out>/cage.json (the cage's counts and poles, the measures against u1, the hand's weights).

The method (no sculpting, no smoothing passes over a dense mesh; every shape is a number at the top):
1. The cage, left half and midline (x >= 0), mirrored and merged at x = 0:
   - the trunk: rings of 12 vertices (index k at 30k degrees from the front midline towards the left side, 7 per
     half), each a superellipse of half width a and its own front and back depth (TRUNK, measured on u1 front and
     side: the round belly, the soft seat, the waist), from the crotch to the neck;
   - the arm hole: between the rings `armpit`, `shoulder` and `top` the side vertices k = 2..4 are the 8 vertices of
     an ellipse around the arm's root (ARM_HOLE); the shoulder ring has no k = 3;
   - the arms: rings of 8 along x (ARM: the T-pose arm, edge loops either side of the elbow) to the wrist, whose
     ring takes S1c's wrist section;
   - the hands (S8): HAND's rings (rotated octagons: the wrist joint, the palm, the knuckles), whose end splits into
     three quads, the roots of the Index, Middle and Ring fingers; the palm's lower front quad is the thumb's root.
     Each finger and the thumb is a square tube (tube()) along its contract bones, with a loop either side of every
     knuckle and a smaller ring and a cap at the tip (FINGER_RINGS, THUMB_RINGS), so it subdivides into a round,
     soft finger;
   - the legs: the crotch vertex C closes each leg's first loop (the trunk's bottom k = 0..6 and C); rings of 8 down
     the leg (LEG: loops at the hip, knee and ankle) turn by 22.5 degrees from hip to ankle, so the ankle ring has
     four vertices in front and four behind;
   - the feet: the rings bend from horizontal to vertical (FOOT: the heel is the bend's outer side), the front four
     become the top of the foot and the back four its flat sole; the last ring's three quads are the three toes, each
     extruded twice and capped (TOE), the middle one longest.
   The poles (vertices of valence 3 or 5 and more) sit at the arm hole's corners, the crotch and the toes, away from
   the elbow, knee, wrist, ankle and neck loops.
   With --target <glb> (step S4b), the cage is then shrink-wrapped onto that body shape, which is measured and
   never kept (class Wrap): the ring vertices move only along their ring's radius, so the loops stay.
2. Subdivision: Catmull-Clark, level 2, applied. The soles: the cage's lowest vertices are lowered until the
   subdivided sole touches z = 0.
3. Rings: the neck's open end (48 vertices) is laid on the ellipse just below S1's ring and joined to S1's two rings
   (2 to 1), so the head welds exactly as before.
4. Weights: the hand's are set on the cage's loops (per ring, by finger segment: FINGER_RINGS, THUMB_RINGS, HAND_W)
   and interpolated by the subdivision; the rest are copied from S1c's body (the Quaternius base's weights, refitted)
   by nearest-face interpolation, scaled by what the hand's leave, then blended with the neighbours' at every joint
   (WEIGHT_SMOOTH passes; the hands and the rings keep theirs), at most four per vertex, normalised. The Little
   finger's bones stay, unweighted.

H1 (art #196, the chameleon's hybrid body): `--targets <toml>` (tools/blender/alien_cage_targets/) sets any of the
constants in CAGE_KEYS; without it the defaults rebuild S4b exactly. Its new paths, each off by default:
- BODY_SCALE scales the source character (rest skeleton, body, the clips' location keys) about the origin and moves
  the neck ring down with it, its ellipse unchanged (the head's size stays; the whole character's height changes);
- CAGE_REMAP moves the cage's numbers from S1c's skeleton (REF_*) onto the source's: heights by the ankle, knee, hip,
  chest, shoulder and ring stations, the arm's x by the shoulder, elbow, wrist and knuckles, the foot's y by the
  ankle, ball and toe tip; WRAP_Z and WRAP_X keep S1c-frame cage stations on the left and are remapped the same way;
- HAND_REL reads HAND's rings as offsets from the LeftHand bone's head; HAND_COLS (the rings' columns as shares of
  the half width, front to back) gives the hand len(HAND_COLS) - 1 finger roots: five columns for FINGERS of four
  (the wrist joint's ring stays an octagon; two pentagons in the palm's heel join it to the ten-vertex rings);
  FINGER_CURL bends each finger's mesh at its knuckles (a relaxed rest; the bones stay straight);
- TOE_SET picks which of the foot's three end quads become toes (two groups: the middle one is capped, a cleft);
- the target (--target) can be welded (TARGET_WELD), smoothed in soft boxes (TARGET_CLEAN: lumps, dimples, grooves
  and seams it should not pass on) and symmetrised from one half (TARGET_MIRROR) before it is measured; ARM_GUESS is
  the first guess of its arm's section centre.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tomllib

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alien_parts_geom as G  # noqa: E402

S = math.sqrt(0.5)
SUPER = 2.5  # the trunk sections' superellipse exponent (2: an ellipse; higher: fuller sides)
# The trunk rings: (name, z, half width a, front y, back y); Blender, front is -Y. u1 front (width) and side (depth),
# 0.0019 m per pixel, the side image's x mapped by y = 0.346 - x (its neck centre on the ring's centre).
TRUNK = [
    ("crotch", 0.790, 0.150, -0.066, 0.140),
    ("hip", 0.860, 0.142, -0.098, 0.152),
    ("belly", 0.930, 0.132, -0.110, 0.140),
    ("navel", 1.000, 0.119, -0.103, 0.126),
    ("waist", 1.070, 0.115, -0.090, 0.127),
    ("chest", 1.140, 0.127, -0.076, 0.136),
    ("armpit", 1.200, 0.134, -0.063, 0.146),
    ("shoulder", 1.262, 0.132, -0.034, 0.146),
    ("top", 1.312, 0.112, -0.010, 0.128),
    ("neck", 1.348, 0.066, -0.012, 0.108),
]
NECK_END = 1.374  # m: the cage's last neck ring (its subdivided edge is laid on the ring ellipse here)
CROTCH = (0.0, 0.035, 0.748)  # the vertex C closing both legs' first loops
CROTCH_Z = {0: 0.778, 6: 0.786}  # the bottom ring's front and back midline, m
# The arm hole: centre, (ry, rz), and x for its bottom, middle and top vertices.
ARM_HOLE = ((0.055, 1.266), (0.060, 0.054), (0.142, 0.150, 0.156))
# Arm rings along x: (x, y centre, z centre, ry, rz); the last is the wrist's end (replaced by the measured ring).
ARM = [
    (0.200, 0.061, 1.271, 0.047, 0.046),
    (0.280, 0.065, 1.275, 0.042, 0.041),
    (0.360, 0.068, 1.2765, 0.037, 0.036),
    (0.413, 0.070, 1.2765, 0.034, 0.033),
    (0.465, 0.069, 1.2765, 0.034, 0.032),
    (0.540, 0.067, 1.2765, 0.031, 0.029),
]
# The limbs a little sturdier than the u1 reading (they read thin at 3 m, UPDATE 10): each arm and leg ring's radii
# times this, per ring (the last arm ring and the ankle less, so the wrist ring and the foot stay).
ARM_THICK = [1.10, 1.10, 1.10, 1.10, 1.09, 1.04]
LEG_THICK = [1.06, 1.12, 1.13, 1.12, 1.12, 1.12, 1.10, 1.06]
# The order of the arm's octagon (dy, dz), matching the hole: bottom-front, bottom, bottom-back, back, top-back, top,
# top-front, front (+Y is back).
OCT = [(-S, -S), (0, -1), (S, -S), (1, 0), (S, S), (0, 1), (-S, S), (-1, 0)]
WRIST_X = 0.605   # m: the arm's last ring (S1c's wrist section, measured at WRIST_X + WRIST_GAP)
WRIST_GAP = 0.005
# The hand (S8, art #196): built in the cage, one surface with the arm (no S1c or Quaternius hand mesh). Rings along x
# after the wrist: (x, y centre, z centre, half width in y, half height in z). Each is a rounded box on a rotated
# octagon (vertices at 22.5 + 45 k degrees), so the last ring's end splits into three quads, one per finger, and the
# palm's lower front quad between the second and third ring is the thumb's root. The positions are read off the
# contract skeleton's hand bones (LeftHand's head at x 0.644; the knuckles at 0.767 to 0.776; Index, Middle and Ring
# 4.1 to 4.5 cm apart in y): u1's big soft hand with three fat fingers and a thumb.
HAND = [  # S8b: the palm a little wider and thicker (u1's soft mitten)
    (0.640, 0.062, 1.2725, 0.033, 0.0245),  # the wrist joint
    (0.680, 0.056, 1.2690, 0.051, 0.0260),  # the palm's heel
    (0.722, 0.050, 1.2700, 0.061, 0.0242),
    (0.758, 0.049, 1.2705, 0.062, 0.0218),  # the knuckles: its end is the fingers' roots
]
HAND_INNER = (0.56, 0.56, 0.50, 0.36)  # each ring's top and bottom inner vertices at this share of the half width
HAND_SIDE_H = 0.55  # the side vertices' height, a share of the half height
FINGERS = ("Index", "Middle", "Ring")  # the Little finger's bones stay, unweighted
# S8b: shorter, chunkier fingers in the mesh only (the bones and clips stay): each finger ring's place along its bones
# is pulled toward the knuckle (J0) by FINGER_K, so the knuckle loops sit up to 1.2 cm before the bones' joints and
# the tip ends about 1.5 cm short of S8's; the weights follow the rings.
# M7 (art #196): the engineer found the digits "like sausages"; the pick of a 3 x 3 grid (length x 1.0/1.1/1.2,
# thickness x 1.0/0.9/0.8) is the longest and slimmest, L1.2 T0.8: FINGER_K 0.82 -> 0.984 (the mesh's joints nearly
# at the bones'), FINGER_R 0.0208 -> 0.01664, the thumb and toes alike.
FINGER_K = 0.984
FINGER_R = 0.01664  # m: a finger tube's cage half side times 0.93 (subdivided, the finger's radius is about 0.7 of it)
TIP_BACK = 0.010  # m: the tips end this far before the distal bone's tail (before FINGER_K)
# Per finger ring: (joint, offset m along the finger, radius scale, weights by segment P/I/D/H(and)/M(etacarpal)).
FINGER_RINGS = [
    ("J0", 0.008, 1.00, {"P": 0.85, "H": 0.15}),
    ("J1", -0.006, 0.98, {"P": 0.8, "I": 0.2}),
    ("J1", 0.006, 0.98, {"P": 0.2, "I": 0.8}),
    ("J2", -0.005, 0.97, {"I": 0.85, "D": 0.15}),
    ("J2", 0.005, 0.96, {"I": 0.5, "D": 0.5}),
    ("TIP", -0.004, 0.92, {"I": 0.3, "D": 0.7}),
    ("TIP", 0.004, 0.60, {"I": 0.3, "D": 0.7}),
]
# S8b: the thumb leaves the palm's front side (the quad between the heel and the middle ring) as a soft mound and
# points forward along the hand and a little toward the palm (u1), not down along its bones: a quadratic curve from the
# quad's centre, THUMB_OUT m out of the side, then THUMB_LEN m along THUMB_DIR (Blender: +X along the hand, -Y the
# front, -Z the palm). Rings: (t on the curve, radius scale, weights by segment M/P/D/H).
THUMB_R = 0.0172  # M7: S9's 0.0215 x 0.8 past the root (thumb_thin); the root keeps THUMB_R0
THUMB_OUT = 0.014
THUMB_LEN = 0.0744  # M7: S9's 0.062 x 1.2
THUMB_DIR = (0.83, -0.43, -0.14)  # S9: less downward (S8b: z -0.24, the thumb hung below the palm)
THUMB_RINGS = [
    (0.20, (0.60, 0.92), {"M": 0.85, "H": 0.15}),  # the root: as tall as the palm's side quad (no fold over it)
    (0.42, (0.85, 0.98), {"M": 0.7, "P": 0.3}),
    (0.56, 0.97, {"M": 0.2, "P": 0.8}),
    (0.72, 0.95, {"P": 0.7, "D": 0.3}),
    (0.83, 0.93, {"P": 0.2, "D": 0.8}),
    (0.95, 0.85, {"D": 1.0}),
    (1.00, 0.52, {"D": 1.0}),
]
HAND_W = [{"Hand": 0.5}, {"Hand": 1.0}, {"Hand": 1.0}, {"Hand": 1.0}]  # the rest of the wrist ring's weight: S1c's
THUMB_ROOT_W = {"Hand": 0.6, "ThumbMetacarpal": 0.4}
# Leg rings: (z, x centre, y centre, rx, ry); a ring of 8 turning by 22.5 degrees from the first to the last.
LEG = [
    (0.715, 0.104, 0.030, 0.066, 0.071),
    (0.630, 0.111, 0.033, 0.058, 0.063),
    (0.560, 0.114, 0.036, 0.050, 0.055),
    (0.515, 0.114, 0.038, 0.047, 0.052),
    (0.470, 0.114, 0.043, 0.047, 0.053),
    (0.380, 0.114, 0.054, 0.046, 0.053),
    (0.265, 0.114, 0.068, 0.037, 0.043),
    (0.170, 0.114, 0.080, 0.036, 0.042),
]
# Foot rings: (y, z centre, tilt deg from horizontal, half width, height above centre, depth below centre). The tilted
# ring is a regular octagon in its frame; vertical rings (90) are a rounded box with a flat sole.
FOOT = [
    (0.088, 0.100, 25.0, 0.045, 0.050, 0.075),
    (0.062, 0.060, 55.0, 0.055, 0.062, 0.080),
    (-0.005, 0.046, 90.0, 0.060, 0.056, 0.046),
    (-0.048, 0.040, 90.0, 0.071, 0.054, 0.040),
    (-0.072, 0.040, 90.0, 0.078, 0.054, 0.040),
]
# The vertical rings' top side vertices, as a share of the ring's height (S7: 0.35 -> 0.62, with the tops above raised
# about 1 cm, so the forefoot stays high and round from the side to the toes, as u1's paddle, and the outer toes sit
# level instead of slanting down)
FOOT_SIDE_H = 0.62
FOOT_X = 0.117
# Toes: per extrusion (forward m from the toe's base, width scale, height scale, drop m); the middle toe reaches
# TOE_MID further. Fat round lobes (u1): they keep the base's width and height nearly to the end, then a short
# rounded cap ring, so the subdivided tip stays full instead of pinching.
# S8b: a fourth, small ring closes each toe in a dome (S7's flat cap on the third read boxy from the side)
TOE = [(0.014, 1.04, 1.0, 0.0), (0.028, 1.0, 0.95, 0.002), (0.038, 0.84, 0.80, 0.004), (0.045, 0.48, 0.46, 0.006)]
TOE_MID = 0.006
# M7 (art #196): the engineer found the digits "like sausages": a little longer and slimmer, chosen on a 3 x 3 grid
# (length x thickness, the pick L1.2 T0.8 above; `--digits JSON` sets these names for a variant, FINGER_K at most 1).
# THUMB_R0 and the toes' first ring keep the root's size (the palm's quad, the foot's), so the slimming starts past the root and the roots do not fold.
THUMB_R0 = 0.0215  # the thumb's root rings' radius (S9's THUMB_R)
TOE_LEN = 1.2  # TOE's forward steps times this (S9: 1)
TOE_THICK = 0.8  # TOE's width and height scales times this (the first ring by half as much; S9: 1)
DIGITS = ("FINGER_K", "FINGER_R", "TIP_BACK", "THUMB_R", "THUMB_LEN", "TOE_LEN", "TOE_THICK", "TOE_MID")
SUBDIV = 2
# The trunk's fit: which of each ring's numbers are corrected against u1 (the arm hole's rings only their depth).
FIT = {"hip": ("a", "yf", "yb"), "belly": ("a", "yf", "yb"), "navel": ("a", "yf", "yb"),
       "waist": ("a", "yf", "yb"), "chest": ("a", "yf", "yb"), "armpit": ("yf", "yb"),
       "shoulder": ("yf", "yb"), "top": ("yf",)}
FIT_TOL = 0.001
FIT_ITERS = 8
WEIGHT_SMOOTH = 4
WRIST_KEEP = 0.04  # m: the arm's vertices this close to the wrist ring keep S1c's weights (no step at the weld)
RING_W = {"Neck": 0.7, "Head": 0.3}
# S4b's wrap onto a target body (--target): the stations, cage -> target, m above each one's sole. Heights: the ankle,
# knee, crotch, armpit (the arm's underside), shoulder top and neck; the arm's x: the shoulder, elbow and wrist.
WRAP_Z = [(0.0, 0.0), (0.17, 0.205), (0.518, 0.575), (0.748, 0.815), (1.231, 1.300), (1.312, 1.395), (1.374, 1.45)]
WRAP_X = [(0.15, 0.185), (0.413, 0.355), (0.605, 0.525)]
WRAP_S = 0.95  # the trunk's target radii are scaled by this
# The rings' weights: 1 takes the target fully, 0 keeps the cage (the neck, the wrist, the feet stay the cage's).
WRAP_W = {"trunk": {"crotch": 0.3, "hip": 0.7, "belly": 1.0, "navel": 1.0, "waist": 1.0, "chest": 1.0,
                    "armpit": 0.6, "shoulder": 0.5, "top": 0.3, "neck": 0.0},
          "arm": [0.7, 1.0, 1.0, 1.0, 1.0, 0.4],
          "leg": [0.5, 0.9, 0.9, 0.6, 0.6, 0.9, 0.9, 0.4]}
# The goals' ratios to the cage's radii relaxed over the cage's edges: (factor, passes) per kind. The limbs more, so
# the target's kneecap and calf hints do not come through as knobs.
WRAP_RELAX = {"trunk": (0.5, 1), "arm": (0.5, 6), "leg": (0.5, 8)}
WRAP_TOL = 0.0015
# H1 (art #196): the cage targets' new paths (see the docstring); these defaults keep S4b.
BODY_SCALE = 1.0
CAGE_REMAP = False
HAND_REL = False
HAND_COLS = None  # None: S8's rotated octagons (three finger roots)
FINGER_CURL = (0.0, 0.0, 0.0)  # degrees at the J0, J1 and J2 knuckles, toward the palm
TOE_SET = (0, 1, 2)
ARM_GUESS = (-0.01, 1.34)  # the target arm section's first centre guess (y, z)
NECK_END_ELLIPSE = (0.0605, 0.047, 0.0565)  # the neck's end ring: semi x, centre y, semi y
TARGET_WELD = 0.0  # m; 0: the target is not welded
TARGET_MIRROR = ""  # "+x" or "-x": the half of the target kept and mirrored
TARGET_CLEAN = []  # [[x0, x1, y0, y1, z0, z1, passes], ...] soft boxes smoothed on the target (its own frame)
TARGET_CLEAN_MARGIN = 0.015  # m: each box's soft edge
# S1c's skeleton, the cage numbers' frame (CAGE_REMAP): heights, the arm's x and the foot's y of its joints.
REF_Z = {"LeftFoot": 0.115, "LeftLowerLeg": 0.5181, "LeftUpperLeg": 0.8409, "Chest": 1.0283, "UpperChest": 1.1491,
         "LeftUpperArm": 1.2765}
REF_RING = (1.39, 0.008)  # S1's ring height and step
REF_X = {"LeftUpperArm": 0.152, "LeftLowerArm": 0.4131, "LeftHand": 0.6444, "LeftIndexProximal": 0.7759}
REF_FOOT_Y = (-0.1811, -0.0865, 0.0913)  # the toe bone's tail, its head (the ball) and the ankle
CAGE_KEYS = ("TRUNK", "NECK_END", "CROTCH", "CROTCH_Z", "ARM_HOLE", "ARM", "ARM_THICK", "LEG_THICK", "WRIST_X",
             "WRIST_GAP", "HAND", "HAND_INNER", "HAND_SIDE_H", "FINGERS", "FINGER_K", "FINGER_R", "TIP_BACK",
             "FINGER_RINGS", "THUMB_R", "THUMB_OUT", "THUMB_LEN", "THUMB_DIR", "THUMB_RINGS", "HAND_W", "THUMB_ROOT_W",
             "LEG", "FOOT", "FOOT_SIDE_H", "FOOT_X", "TOE", "TOE_MID", "THUMB_R0", "TOE_LEN", "TOE_THICK", "FIT",
             "WEIGHT_SMOOTH", "WRAP_Z", "WRAP_X", "WRAP_S", "WRAP_W", "WRAP_RELAX", "WRAP_TOL", "BODY_SCALE",
             "CAGE_REMAP", "HAND_REL", "HAND_COLS", "FINGER_CURL", "TOE_SET", "ARM_GUESS", "NECK_END_ELLIPSE",
             "TARGET_WELD", "TARGET_MIRROR", "TARGET_CLEAN", "TARGET_CLEAN_MARGIN")


def apply_cage_targets(path):
    """H1: a cage targets file's upper-case keys over the module's constants (CAGE_KEYS only; CROTCH_Z's keys become
    ints, the short vectors tuples). Returns the file's name key."""
    with open(path, "rb") as fh:
        t = tomllib.load(fh)
    bad = sorted(k for k in t if k.isupper() and k not in CAGE_KEYS)
    if bad:
        raise SystemExit(f"{path}: unknown keys {bad}")
    g = globals()
    for k, v in t.items():
        if not k.isupper():
            continue
        if k == "CROTCH_Z":
            v = {int(a): b for a, b in v.items()}
        elif k in ("FINGERS", "FINGER_CURL", "TOE_SET", "ARM_GUESS", "NECK_END_ELLIPSE", "CROTCH", "THUMB_DIR"):
            v = tuple(v)
        elif k in ("FINGER_RINGS", "THUMB_RINGS"):
            v = [tuple(tuple(x) if isinstance(x, list) else x for x in row) for row in v]
        elif k == "FIT":
            v = {a: tuple(b) for a, b in v.items()}
        g[k] = v
    if HAND_COLS is not None and len(HAND_COLS) != len(FINGERS) + 1:
        raise SystemExit(f"{path}: HAND_COLS needs len(FINGERS) + 1 = {len(FINGERS) + 1} columns")
    if HAND_COLS is not None and len(HAND_COLS) not in (4, 5):
        raise SystemExit(f"{path}: HAND_COLS: 4 or 5 columns (three or four fingers)")
    return t.get("name", os.path.basename(path))


def pw(table, v):
    """A piecewise-linear map through (a, b) pairs sorted by a; past either end it continues the end segment's
    slope (one segment) or slope 1 (more)."""
    if v <= table[0][0]:
        (a0, b0), (a1, b1) = table[0], table[1]
        return b0 + (v - a0) * ((b1 - b0) / (a1 - a0) if len(table) == 2 else 1.0)
    for (a0, b0), (a1, b1) in zip(table, table[1:]):
        if v <= a1:
            return b0 + (b1 - b0) * (v - a0) / (a1 - a0)
    return table[-1][1] + (v - table[-1][0])


def remap_tables(heads, ring_z, ring_step):
    """H1 (CAGE_REMAP): the z, x and foot-y maps from S1c's skeleton onto one given by its bone heads
    ({name: (x, y, z)}, plus LeftToes' tail as "LeftToesTail") and its ring."""
    tz = [(0.0, 0.0)] + sorted((REF_Z[n], heads[n][2]) for n in REF_Z)
    tz += [(REF_RING[0] - 2 * REF_RING[1], ring_z - 2 * ring_step), (REF_RING[0], ring_z)]
    tx = [(0.0, 0.0)] + sorted((REF_X[n], heads[n][0]) for n in REF_X)
    ty = list(zip(REF_FOOT_Y, (heads["LeftToesTail"][1], heads["LeftToes"][1], heads["LeftFoot"][1])))
    return tz, tx, ty


def remap_constants(tz, tx, ty):
    """H1: the cage's S1c-frame numbers moved onto the new skeleton by the maps (module constants rewritten)."""
    global NECK_END, CROTCH, CROTCH_Z, ARM_HOLE, ARM, WRIST_X, HAND, LEG, FOOT, WRAP_Z, WRAP_X, TRUNK
    Z, X, Y = (lambda v: pw(tz, v)), (lambda v: pw(tx, v)), (lambda v: pw(ty, v))  # noqa: E731
    TRUNK = [(n, Z(z), a, yf, yb) for n, z, a, yf, yb in TRUNK]
    NECK_END = Z(NECK_END)
    CROTCH = (CROTCH[0], CROTCH[1], Z(CROTCH[2]))
    CROTCH_Z = {k: Z(v) for k, v in CROTCH_Z.items()}
    (hy, hz), r, xs = ARM_HOLE
    ARM_HOLE = ((hy, Z(hz)), r, tuple(X(x) for x in xs))
    ARM = [(X(x), yc, Z(zc), ry, rz) for x, yc, zc, ry, rz in ARM]
    WRIST_X = X(WRIST_X)
    if not HAND_REL:
        HAND = [(X(x), yc, Z(zc), w, h) for x, yc, zc, w, h in HAND]
    LEG = [(Z(z), cx, cy, rx, ry) for z, cx, cy, rx, ry in LEG]
    FOOT = [(Y(row[0]),) + tuple(row[1:]) for row in FOOT]
    WRAP_Z = [(Z(a), b) for a, b in WRAP_Z]
    WRAP_X = [(X(a), b) for a, b in WRAP_X]


def fcurves_of(act):
    """Every F-curve of an action (layered actions: layers, strips, channel bags)."""
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out += list(cb.fcurves)
    return out


def scale_character(arm, body, ring, s):
    """H1 (BODY_SCALE): the source's rest skeleton, its body and its clips' location keys scaled by s about the
    origin; the ring (S1's dict, before densifying) moved to z * s with its ellipse unchanged."""
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for eb in arm.data.edit_bones:
        eb.head = eb.head * s
        eb.tail = eb.tail * s
    bpy.ops.object.mode_set(mode="OBJECT")
    for v in body.data.vertices:
        v.co = v.co * s
    keys = 0
    for act in bpy.data.actions:
        for fc in fcurves_of(act):
            if fc.data_path.endswith(".location"):
                for kp in fc.keyframe_points:
                    kp.co.y *= s
                    kp.handle_left.y *= s
                    kp.handle_right.y *= s
                    keys += 1
                fc.update()
    dz = ring["z"] * (s - 1.0)
    ring["z"] = round(ring["z"] + dz, 6)
    for key in ("loop", "loop_below"):
        ring[key] = [[q[0], q[1], round(q[2] + dz, 6)] for q in ring[key]]
    bpy.context.view_layer.update()
    return {"scale": s, "location_keys": keys, "ring_z": ring["z"]}


def trunk_vert(k, z, a, yf, yb, n=SUPER):
    th = math.radians(30 * k)
    s, c = math.sin(th), math.cos(th)
    x = a * abs(s) ** (2 / n)
    yc = 0.5 * (yf + yb)
    y = yc - (yc - yf) * abs(c) ** (2 / n) if c > 0 else yc + (yb - yc) * abs(c) ** (2 / n)
    return Vector((x, y, z))


def tube(bm, base, path, half, out):
    """Extrudes a square tube from a quad `base` through `path` [(centre, direction, half side scale, weights)]; each
    ring is a square around its centre, normal to its direction, its corners on the base corners' sides (no twist);
    the last ring is capped. Weights per vertex go into `out`."""
    bc = sum((v.co for v in base), Vector()) / 4
    last = base
    for c, d, sc, w in path:
        e1 = base[1].co - base[0].co
        e1 = (e1 - d * e1.dot(d)).normalized()
        e2 = d.cross(e1)
        ring = []
        for b in base:
            u = b.co - bc
            s1 = 1.0 if u.dot(e1) >= 0 else -1.0
            s2 = 1.0 if u.dot(e2) >= 0 else -1.0
            k1, k2 = sc if isinstance(sc, tuple) else (sc, sc)  # a ring's scale, or (along e1, along e2)
            ring.append(bm.verts.new(c + (e1 * s1 * k1 + e2 * s2 * k2) * half))
            out[ring[-1]] = dict(w)
        for j in range(4):
            bm.faces.new((last[j], last[(j + 1) % 4], ring[(j + 1) % 4], ring[j]))
        last = ring
    bm.faces.new(last)


def thumb_thin(t):
    """M7: a thumb ring's radius factor at curve parameter t: 1 (THUMB_R0) at the root, THUMB_R / THUMB_R0 from
    t 0.56 on, a smoothstep between (from t 0.2)."""
    s = min(max((t - 0.2) / 0.36, 0.0), 1.0)
    return 1.0 + (THUMB_R / THUMB_R0 - 1.0) * s * s * (3 - 2 * s)


def toe_ring(i, fwd, sw, sh):
    """M7: TOE's ring i scaled by TOE_LEN (forward) and TOE_THICK (width, height; the first ring by half)."""
    k = 1.0 + (TOE_THICK - 1.0) * (0.5 if i == 0 else 1.0)
    return fwd * TOE_LEN, sw * k, sh * k


def set_digits(spec):
    """M7: a variant's digit settings ({name: value}, names from DIGITS) over the module's."""
    bad = set(spec) - set(DIGITS)
    if bad:
        raise SystemExit(f"--digits: unknown {sorted(bad)}; known {DIGITS}")
    vals = {k: float(v) for k, v in spec.items()}
    if vals.get("FINGER_K", 0.0) > 1.0:  # PR #240's review: past 1 the mesh's finger joints pass the bones'
        raise SystemExit(f"--digits: FINGER_K {vals['FINGER_K']} > 1 puts the mesh's joints past the bones'")
    globals().update(vals)


def build_hand(bm, wrist, bones):
    """S8: the left hand in the cage, from the wrist ring (8, OCT order): HAND's rings (rotated octagons), three
    finger tubes from the knuckle ring's end and the thumb from the palm's lower front quad. Returns the hand
    vertices' weights {vertex: {group: w}} (the Little finger gets none)."""
    out = {}
    prev = wrist
    hr = []
    h0 = bones["LeftHand"][0] if HAND_REL else Vector((0.0, 0.0, 0.0))
    for i, ((x, yc, zc, w, h), inner) in enumerate(zip(HAND, HAND_INNER)):
        x, yc, zc = x + h0.x, yc + h0.y, zc + h0.z
        ring = []
        if HAND_COLS is None or i == 0:
            for k in range(8):
                ph = math.radians(202.5 - 45 * k)
                sy, sz = math.copysign(1, math.sin(ph)), math.copysign(1, math.cos(ph))
                side = abs(math.sin(ph)) > 0.7
                ring.append(bm.verts.new((x, yc + sy * w * (1.0 if side else inner),
                                          zc + sz * h * (HAND_SIDE_H if side else 1.0))))
        else:  # H1: columns front (c 0) to back; order: bottom c 1..C-1, back top, top C-2..1, front top, bottom
            C = len(HAND_COLS)

            def col(c, top):
                side = c in (0, C - 1)
                return bm.verts.new((x, yc + w * HAND_COLS[c] * (1.0 if side else inner / HAND_INNER[-1]),
                                     zc + (1 if top else -1) * h * (HAND_SIDE_H if side else 1.0)))
            ring = ([col(c, False) for c in range(1, C)] + [col(C - 1, True)]
                    + [col(c, True) for c in range(C - 2, 0, -1)] + [col(0, True), col(0, False)])
        for v in ring:
            out[v] = dict(HAND_W[i])
        n = len(ring)
        if len(prev) == 8 and n == 10:  # H1: the octagon to ten, two pentagons (bottom and top middle)
            P, R = prev, ring
            for f in ((P[0], P[1], R[2], R[1], R[0]), (P[1], P[2], R[3], R[2]), (P[2], P[3], R[4], R[3]),
                      (P[3], P[4], R[5], R[4]), (P[4], P[5], R[7], R[6], R[5]), (P[5], P[6], R[8], R[7]),
                      (P[6], P[7], R[9], R[8]), (P[7], P[0], R[0], R[9])):
                bm.faces.new(f)
        else:
            for k in range(n):
                if i == 2 and k == n - 2:
                    continue  # the thumb's root: the front side quad
                bm.faces.new((prev[k], prev[(k + 1) % n], ring[(k + 1) % n], ring[k]))
        hr.append(ring)
        prev = ring
    K = hr[-1]
    C = len(K) // 2

    def top(c):
        return K[2 * C - 2 - c]

    def bot(c):
        return K[2 * C - 1] if c == 0 else K[c - 1]
    seg = {"P": "Proximal", "I": "Intermediate", "D": "Distal"}

    def path(joints, rows, radius, names):
        pts = []
        for jn, off, sc, w in rows:
            if jn == "TIP":
                a, b = joints["J2"], joints["T"]
                d = (b - a).normalized()
                c = b - d * (TIP_BACK - off)
            else:
                j = joints[jn]
                nxt = {"J0": "J1", "J1": "J2", "J2": "T"}[jn]
                prv = {"J0": None, "J1": "J0", "J2": "J1"}[jn]
                d = (joints[nxt] - j).normalized() if off >= 0 or prv is None else (j - joints[prv]).normalized()
                c = j + d * off
            c = joints["J0"] + (c - joints["J0"]) * FINGER_K
            pts.append((c, d, sc, {names[k]: v for k, v in w.items()}))
        return pts, radius / 0.93

    for fi, f in enumerate(FINGERS):
        base = [top(fi), top(fi + 1), bot(fi + 1), bot(fi)]
        j = {"J0": bones[f"Left{f}Proximal"][0], "J1": bones[f"Left{f}Intermediate"][0],
             "J2": bones[f"Left{f}Distal"][0], "T": bones[f"Left{f}Distal"][1]}
        if any(FINGER_CURL):  # H1: a relaxed rest, each knuckle bent toward the palm (-Z), the joints after it with it
            j = {k: Vector(v) for k, v in j.items()}
            order = ("J0", "J1", "J2", "T")
            for a, deg in zip(order, FINGER_CURL):
                if not deg:
                    continue
                d = (j[order[order.index(a) + 1]] - j[a]).normalized()
                axis = d.cross(Vector((0.0, 0.0, -1.0))).normalized()
                rot = Matrix.Rotation(math.radians(deg), 3, axis)
                for b in order[order.index(a) + 1:]:
                    j[b] = j[a] + rot @ (j[b] - j[a])
        names = {k: f"Left{f}{v}" for k, v in seg.items()} | {"H": "LeftHand"}
        pts, half = path(j, FINGER_RINGS, FINGER_R, names)
        tube(bm, base, pts, half, out)
    P1, P2 = hr[1], hr[2]
    kt = len(P2) - 2
    base = [P1[kt], P1[kt + 1], P2[kt + 1], P2[kt]]
    for v in base:
        out[v] = {"Left" + k: w for k, w in THUMB_ROOT_W.items()}
    names = {"M": "LeftThumbMetacarpal", "P": "LeftThumbProximal", "D": "LeftThumbDistal", "H": "LeftHand"}
    q0 = sum((v.co for v in base), Vector()) / 4
    q1 = q0 + Vector((0.0, -THUMB_OUT, 0.0))
    q2 = q1 + Vector(THUMB_DIR).normalized() * THUMB_LEN
    pts = []
    for t, sc, w in THUMB_RINGS:
        c = q0 * (1 - t) ** 2 + q1 * 2 * t * (1 - t) + q2 * t * t
        d = ((q1 - q0) * 2 * (1 - t) + (q2 - q1) * 2 * t).normalized()
        k = thumb_thin(t)  # M7: the root keeps THUMB_R0, the rest THUMB_R
        sc = (sc[0] * k, sc[1] * k) if isinstance(sc, tuple) else sc * k
        pts.append((c, d, sc, {names[k_]: v for k_, v in w.items()}))
    tube(bm, base, pts, THUMB_R0 / 0.93, out)
    for v, w in list(out.items()):  # HAND_W's "Hand" -> LeftHand
        out[v] = {(k if k.startswith("Left") else "Left" + k): x for k, x in w.items()}
    return out


def build_cage(sole_drop, trunk, bones=None):
    """The half cage (x >= 0) as a bmesh, and the named vertex lists; with `bones` ({name: (head, tail)} of the left
    hand) the hand is built in the cage (rings["hand_w"]: its vertices' weights)."""
    bm = bmesh.new()
    bm.verts.layers.deform.verify()  # before any vertex: adding a layer later frees the BMVert references
    V = lambda co: bm.verts.new(co)  # noqa: E731
    meta = []  # (vertex, kind, ring, ring centre) of every trunk, arm and leg ring vertex: the wrap's stations
    rings = {"meta": meta}
    (hy, hz), (hry, hrz), (hx0, hx1, hx2) = ARM_HOLE
    hole = [V((hx0 if dz < 0 else (hx2 if dz > 0 else hx1), hy + hry * dy, hz + hrz * dz)) for dy, dz in OCT]
    for name, z, a, yf, yb in trunk:
        ring = []
        for k in range(7):
            if name == "armpit" and k in (2, 3, 4):
                ring.append(hole[{2: 0, 3: 1, 4: 2}[k]])
            elif name == "shoulder" and k in (2, 3, 4):
                ring.append({2: hole[7], 3: None, 4: hole[3]}[k])
            elif name == "top" and k in (2, 3, 4):
                ring.append(hole[{2: 6, 3: 5, 4: 4}[k]])
            else:
                co = trunk_vert(k, z, a, yf, yb)
                if name == "crotch" and k in CROTCH_Z:
                    co.z = CROTCH_Z[k]
                ring.append(V(co))
                meta.append((ring[-1], "trunk", name, Vector((0.0, 0.5 * (yf + yb), z))))
        rings[name] = ring
    # the neck's end ring: an ellipse on the ring's centre, sized so its subdivided edge lies near the ring
    names = [t[0] for t in trunk]
    end = []
    for k in range(7):
        th = math.radians(30 * k)
        ex, ey, eb = NECK_END_ELLIPSE
        end.append(V((ex * math.sin(th), ey - eb * math.cos(th), NECK_END)))
    rings["end"] = end
    names.append("end")
    for lo, hi in zip(names, names[1:]):
        A, B = rings[lo], rings[hi]
        for k in range(6):
            if (lo, hi) in (("armpit", "shoulder"), ("shoulder", "top")) and k in (2, 3):
                continue  # the arm hole
            bm.faces.new((A[k], A[k + 1], B[k + 1], B[k]))
    # arms
    prev = hole
    for i, (x, yc, zc, ry, rz) in enumerate(ARM + [(WRIST_X, 0.0, 0.0, 0.0, 0.0)]):
        if x == WRIST_X:
            ring = [V((x, 0, 0)) for _ in OCT]  # placed after the wrist is measured
            rings["wrist_cage"] = ring
        else:
            t = ARM_THICK[i]
            ring = [V((x, yc + t * ry * dy, zc + t * rz * dz)) for dy, dz in OCT]
            meta += [(v, "arm", i, Vector((x, yc, zc))) for v in ring]
        for i in range(8):
            bm.faces.new((prev[i], prev[(i + 1) % 8], ring[(i + 1) % 8], ring[i]))
        prev = ring
    if bones is not None:
        rings["hand_w"] = build_hand(bm, prev, bones)
    # legs: the first loop is the crotch ring's k = 0..6 and C
    c = V(CROTCH)
    loop = rings["crotch"][:7] + [c]
    prev = loop
    for i, (z, cx, cy, rx, ry) in enumerate(LEG):
        tw = 22.5 * i / (len(LEG) - 1)
        ring = []
        for j in range(8):
            ph = math.radians(-45 + 45 * j + tw)
            t = LEG_THICK[i]
            ring.append(V((cx + t * rx * math.sin(ph), cy - t * ry * math.cos(ph), z)))
        meta += [(v, "leg", i, Vector((cx, cy, z))) for v in ring]
        for j in range(8):
            bm.faces.new((prev[j], prev[(j + 1) % 8], ring[(j + 1) % 8], ring[j]))
        prev = ring
    # feet: the ankle ring's j at -22.5 + 45 j degrees; front four (7, 0, 1, 2) become the top, back four the sole
    role = {7: (-1.0, FOOT_SIDE_H, 1), 0: (-0.4, 1.0, 1), 1: (0.4, 1.0, 1), 2: (1.0, FOOT_SIDE_H, 1),
            3: (1.0, -0.6, -1), 4: (0.4, -1.0, -1), 5: (-0.4, -1.0, -1), 6: (-1.0, -0.6, -1)}
    for y, zc, tilt, w, ht, hb in FOOT:
        al = math.radians(tilt)
        v = Vector((0, -math.cos(al), math.sin(al)))
        ring = []
        for j in range(8):
            if tilt < 89:
                ph = math.radians(-22.5 + 45 * j)
                off = Vector((w * math.sin(ph), 0, 0)) + v * ((ht if math.cos(ph) > 0 else hb) * math.cos(ph))
            else:
                u, h, sgn = role[j]
                off = Vector((u * w, 0, h * (ht if sgn > 0 else hb)))
            co = Vector((FOOT_X, y, zc)) + off
            if co.z < 0.004:
                co.z -= sole_drop
            ring.append(V(co))
        for j in range(8):
            bm.faces.new((prev[j], prev[(j + 1) % 8], ring[(j + 1) % 8], ring[j]))
        prev = ring
    top = [prev[7], prev[0], prev[1], prev[2]]
    bot = [prev[6], prev[5], prev[4], prev[3]]
    for i in range(3):
        base = [top[i], top[i + 1], bot[i + 1], bot[i]]
        if i not in TOE_SET:  # H1: no toe here (the cleft between two toe groups): the end quad capped
            bm.faces.new(base)
            continue
        cen = sum((p.co for p in base), Vector()) / 4
        last = base
        for r, (fwd, sw, sh, drop) in enumerate(TOE):
            fwd, sw, sh = toe_ring(r, fwd, sw, sh)
            f = fwd + (TOE_MID * fwd / (TOE[-1][0] * TOE_LEN) if i == 1 else 0.0)
            ring = []
            for p in base:
                d = p.co - cen
                co = Vector((cen.x + d.x * sw, cen.y - f, cen.z - drop + d.z * sh))
                if p in bot:
                    co.z = min(co.z, p.co.z + 0.002 + drop * 0.3)
                ring.append(V(co))
            for j in range(4):
                bm.faces.new((last[j], last[(j + 1) % 4], ring[(j + 1) % 4], ring[j]))
            last = ring
        bm.faces.new(last)
    return bm, rings


def trunk_measure(me, z):
    """The subdivided trunk at height z: half width (|x| < 0.2) and the midline's front and back y."""
    band = [v.co for v in me.vertices if abs(v.co.z - z) < 0.004 and abs(v.co.x) < 0.2]
    mid = [c for c in band if abs(c.x) < 0.012]
    return {"a": max((abs(c.x) for c in band), default=None),
            "yf": min((c.y for c in mid), default=None), "yb": max((c.y for c in mid), default=None)}


def subdivided(bm_half, name, gnames=()):
    """Mirrors and subdivides a half cage; returns (cage object, subdivided mesh object). The cage's vertex groups
    (`gnames`, in the bmesh's deform indices) are mirrored Left -> Right and interpolated by the subdivision."""
    me = bpy.data.meshes.new(name + "Cage")
    bm_half.to_mesh(me)
    cage = bpy.data.objects.new(name + "Cage", me)
    bpy.context.scene.collection.objects.link(cage)
    for n in gnames:
        cage.vertex_groups.new(name=n)
    mm = cage.modifiers.new("Mirror", "MIRROR")
    mm.use_axis = (True, False, False)
    mm.use_clip = True
    mm.use_mirror_merge = True
    mm.merge_threshold = 1e-5
    dg = bpy.context.evaluated_depsgraph_get()
    full = bpy.data.meshes.new_from_object(cage.evaluated_get(dg))
    cage.modifiers.clear()
    cage.data = full
    bm = bmesh.new()
    bm.from_mesh(full)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(full)
    bm.free()
    sd = cage.modifiers.new("Subdiv", "SUBSURF")
    sd.levels = sd.render_levels = SUBDIV
    sd.quality = 3
    sd.boundary_smooth = "ALL"
    dg = bpy.context.evaluated_depsgraph_get()
    sub = bpy.data.meshes.new_from_object(cage.evaluated_get(dg))
    cage.modifiers.clear()
    obj = bpy.data.objects.new(name, sub)
    bpy.context.scene.collection.objects.link(obj)
    return cage, obj


def poles(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    out = {}
    for v in bm.verts:
        n = len(v.link_edges)
        interior = not any(e.is_boundary for e in v.link_edges)
        if interior and n != 4:
            out.setdefault(n, []).append([round(c, 3) for c in v.co])
    bm.free()
    return out


class Wrap:
    """S4b: the cage shrink-wrapped onto a target body shape (a Meshy generation), used only as a surface to measure,
    never as mesh. Each trunk, arm and leg ring vertex keeps its ring and its direction from the ring's centre; only
    its distance changes, to the target section's radius in that direction at the matching station (WRAP_Z, WRAP_X:
    the joints matched, so the forms land on the cage's skeleton), blended by the ring's weight (WRAP_W: the neck,
    the wrists, the feet and the arm hole stay the cage's). The trunk takes the target's radii times WRAP_S; each limb
    takes the target's shape at the cage's own mean thickness. Then the radii are relaxed over the cage's edges
    (WRAP_RELAX), and corrected each fit iteration by the subdivided body's error, as the trunk's fit is in S4a."""

    def __init__(self, path):
        from mathutils.bvhtree import BVHTree
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        pts, polys = [], []
        for o in new:
            if o.type == "MESH":
                base = len(pts)
                pts += [o.matrix_world @ v.co for v in o.data.vertices]
                polys += [[base + i for i in p.vertices] for p in o.data.polygons]
        for o in new:
            me = o.data if o.type == "MESH" else None
            bpy.data.objects.remove(o)
            if me is not None:
                bpy.data.meshes.remove(me)
        lo_z = min(p.z for p in pts)
        cx = 0.5 * (min(p.x for p in pts) + max(p.x for p in pts))
        self.pts = [Vector((p.x - cx, p.y, p.z - lo_z)) for p in pts]
        self.report = {"target": path, "target_verts": len(pts), "target_height": round(max(p.z for p in self.pts), 4)}
        if TARGET_WELD or TARGET_CLEAN or TARGET_MIRROR:
            self.pts, polys = self.clean(self.pts, polys)
        self.bvh = BVHTree.FromPolygons(self.pts, polys)
        self.corr = {}
        self.cache = {}

    def clean(self, pts, polys):
        """H1: the target welded (TARGET_WELD), smoothed in TARGET_CLEAN's soft boxes (a Laplacian per pass, each
        vertex by its box weight: the lumps, dimples, grooves and seams the cage should not take) and symmetrised
        (TARGET_MIRROR: the faces touching the kept half, mirrored across x = 0)."""
        bm = bmesh.new()
        vs = [bm.verts.new(p) for p in pts]
        for f in polys:
            try:
                bm.faces.new([vs[i] for i in f])
            except ValueError:
                pass
        if TARGET_WELD:
            n0 = len(bm.verts)
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=TARGET_WELD)
            self.report["target_welded"] = n0 - len(bm.verts)
        smoothed = {}
        for box in TARGET_CLEAN:
            x0, x1, y0, y1, z0, z1, passes = box
            m = TARGET_CLEAN_MARGIN

            def wgt(co):
                t = 1.0
                for v, a, b in ((co.x, x0, x1), (co.y, y0, y1), (co.z, z0, z1)):
                    d = min(v - a, b - v)
                    if d <= 0:
                        return 0.0
                    t = min(t, d / m)
                return min(t, 1.0)
            sel = [(v, wgt(v.co)) for v in bm.verts]
            sel = [(v, w) for v, w in sel if w > 0]
            for _ in range(int(passes)):
                new = []
                for v, w in sel:
                    nb = [e.other_vert(v).co for e in v.link_edges]
                    if nb:
                        avg = sum(nb, Vector()) / len(nb)
                        new.append(v.co + (avg - v.co) * (0.5 * w))
                    else:
                        new.append(v.co.copy())
                for (v, _), co in zip(sel, new):
                    v.co = co
            smoothed[str(box)] = len(sel)
        self.report["target_clean"] = smoothed
        bm.verts.index_update()
        pts = [v.co.copy() for v in bm.verts]
        polys = [[v.index for v in f.verts] for f in bm.faces]
        bm.free()
        if TARGET_MIRROR:
            sgn = 1.0 if TARGET_MIRROR == "+x" else -1.0
            keep = [f for f in polys if any(sgn * pts[i].x >= 0 for i in f)]
            n = len(pts)
            pts = pts + [Vector((-p.x, p.y, p.z)) for p in pts]
            polys = keep + [[n + i for i in reversed(f)] for f in keep]
            self.report["target_mirror"] = {"kept": TARGET_MIRROR, "faces": len(polys)}
        return pts, polys

    def ray(self, bvh, o, d):
        hit = bvh.ray_cast(o, d)
        return hit[3]

    def centre(self, kind, station):
        """The target section's centre at a station: (x, y, z) found by casting rays both ways along the section's
        two axes from a first guess, twice."""
        if kind == "arm":
            c, axes = Vector((station, ARM_GUESS[0], ARM_GUESS[1])), (Vector((0, 1, 0)), Vector((0, 0, 1)))
        elif kind == "leg":
            band = [p for p in self.pts if abs(p.z - station) < 0.006 and 0.05 < p.x < 0.35]
            c = Vector((0.5 * (min(p.x for p in band) + max(p.x for p in band)),
                        0.5 * (min(p.y for p in band) + max(p.y for p in band)), station))
            axes = (Vector((1, 0, 0)), Vector((0, 1, 0)))
        else:
            c, axes = Vector((0.0, -0.04, station)), (Vector((0, 1, 0)),)
        for _ in range(2):
            for ax in axes:
                a, b = self.ray(self.bvh, c, ax), self.ray(self.bvh, c, -ax)
                if a is not None and b is not None:
                    c = c + ax * (0.5 * (a - b))
        return c

    @staticmethod
    def interp(table, v):
        for (a0, b0), (a1, b1) in zip(table, table[1:]):
            if v <= a1 or (a1, b1) == table[-1]:
                return b0 + (b1 - b0) * (v - a0) / (a1 - a0)
        return table[0][1]

    def goals(self, bm, rings):
        """Each wrapped cage vertex's goal: (index, ring centre, unit direction, cage radius, goal radius, weight)."""
        rows, raw = [], {"arm": [], "leg": []}
        cache = self.cache
        for v, kind, ring, c in rings["meta"]:
            w = WRAP_W[kind][ring]
            if w <= 0:
                continue
            d = v.co - c
            if kind == "arm":
                d.x = 0.0
                station = self.interp(WRAP_X, c.x)
            else:
                d.z = 0.0
                station = self.interp(WRAP_Z, c.z)
            r0 = d.length
            d.normalize()
            key = (kind, round(station, 4))
            if key not in cache:
                cache[key] = self.centre(kind, station)
            rt = self.ray(self.bvh, cache[key], d)
            if rt is None:
                continue
            rows.append([v.index, c, d, r0, rt, w, kind])
            if kind in raw:
                raw[kind].append((r0, rt))
        k = {kind: sum(a for a, _ in pairs) / sum(b for _, b in pairs) for kind, pairs in raw.items() if pairs}
        k["trunk"] = WRAP_S
        for row in rows:
            row[4] *= k[row[6]]
        self.report["scale"] = {key: round(val, 4) for key, val in k.items()}
        # the relax: each goal's ratio to the cage radius averaged with its wrapped neighbours' (along the cage's edges)
        bm.verts.ensure_lookup_table()
        ratio = {row[0]: row[4] / row[3] for row in rows}
        kinds = {row[0]: row[6] for row in rows}
        for p in range(max(n for _, n in WRAP_RELAX.values())):
            new = {}
            for i, q in ratio.items():
                fac, passes = WRAP_RELAX[kinds[i]]
                nb = [ratio[e.other_vert(bm.verts[i]).index] for e in bm.verts[i].link_edges
                      if e.other_vert(bm.verts[i]).index in ratio]
                new[i] = q if not nb or p >= passes else (1 - fac) * q + fac * sum(nb) / len(nb)
            ratio = new
        for row in rows:
            row[4] = row[3] * ratio[row[0]]
        return rows

    def apply(self, bm, rings):
        """Moves the wrapped cage vertices to their goals (blended by weight), plus the corrections so far."""
        bm.verts.index_update()
        bm.verts.ensure_lookup_table()
        self.rows = self.goals(bm, rings)
        for i, c, d, r0, rg, w, kind in self.rows:
            v = bm.verts[i]
            r = r0 + w * (rg - r0) + self.corr.get(i, 0.0)
            along = v.co.x if kind == "arm" else v.co.z
            v.co = c + d * r
            if kind == "arm":
                v.co.x = along
            else:
                v.co.z = along

    def measure(self, body):
        """The subdivided body's radius along each wrapped vertex's direction against its goal; the corrections are
        updated. Returns the worst error (m)."""
        from mathutils.bvhtree import BVHTree
        me = body.data
        bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [p.vertices for p in me.polygons])
        worst = 0.0
        errs = []
        for i, c, d, r0, rg, w, kind in self.rows:
            c2 = Vector(c)
            if kind == "arm":
                c2.x = c.x
            rs = self.ray(bvh, c2, d)
            if rs is None:
                continue
            err = (r0 + w * (rg - r0)) - rs
            self.corr[i] = self.corr.get(i, 0.0) + err * w
            worst = max(worst, abs(err) * w)
            errs.append(abs(err) * w)
        self.report.setdefault("fit_worst_mm", []).append(round(worst * 1000, 2))
        self.report.setdefault("fit_mean_mm", []).append(round(1000 * sum(errs) / max(len(errs), 1), 2))
        return worst


def angle_sort(verts, centre, axis):
    """Sorts a loop by its angle around an axis ('x' for the wrists, 'z' for the neck): 0 at the front (-Y)."""
    if axis == "z":
        key = lambda v: (math.atan2(v.co.x - centre[0], -(v.co.y - centre[1])) + 1e-4) % (2 * math.pi)  # noqa: E731
    else:
        key = lambda v: (math.atan2(v.co.z - centre[1], -(v.co.y - centre[0])) + 1e-4) % (2 * math.pi)  # noqa: E731
    return sorted(verts, key=key), key


def zip_loops(bm, a, ka, b, kb):
    """Joins two closed loops, both sorted by angle, with triangles in angle order (the S1 neck zip)."""
    M, N = len(a), len(b)
    angA, angB = [ka(v) for v in a], [kb(v) for v in b]
    shift = min(range(N), key=lambda j: abs(((angB[j] - angA[0] + math.pi) % (2 * math.pi)) - math.pi))
    b = b[shift:] + b[:shift]
    angB = [(x - angA[0]) % (2 * math.pi) for x in angB[shift:] + angB[:shift]]
    angA = [(x - angA[0]) % (2 * math.pi) for x in angA]
    if angB[0] > math.pi:
        angB[0] -= 2 * math.pi
    i = j = 0
    while i < M or j < N:
        a_next = angA[(i + 1) % M] + (2 * math.pi if i + 1 >= M else 0)
        b_next = angB[(j + 1) % N] + (2 * math.pi if j + 1 >= N else 0)
        if j >= N or (i < M and a_next <= b_next):
            bm.faces.new((a[i % M], a[(i + 1) % M], b[j % N]))
            i += 1
        else:
            bm.faces.new((a[i % M], b[(j + 1) % N], b[j % N]))
            j += 1


def main():
    p = argparse.ArgumentParser(prog="alien_cage.py")
    p.add_argument("--src", required=True)
    p.add_argument("--ring", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--target", help="S4b: a body shape (GLB) the cage is shrink-wrapped onto before subdividing")
    p.add_argument("--digits", default="", help="M7: JSON {name: value} over DIGITS (a variant grid's setting)")
    p.add_argument("--targets", help="H1: a cage targets file (TOML, upper-case keys over CAGE_KEYS)")
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    name = apply_cage_targets(args.targets) if args.targets else "s4b"
    if args.digits:
        set_digits(json.loads(args.digits))
    report = {"src": args.src, "target": args.target, "targets": args.targets, "targets_name": name,
              "digits": {k: globals()[k] for k in DIGITS}}
    with open(args.ring, encoding="utf-8") as fh:
        ring = json.load(fh)
    bpy.ops.wm.open_mainfile(filepath=args.src)
    arm = bpy.data.objects["CharacterArmature"]
    old = bpy.data.objects["Body"]
    if arm.animation_data:
        arm.animation_data.action = None
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    if BODY_SCALE != 1.0:  # H1: the whole character's height by the body's scale, the ring's ellipse unchanged
        report["body_scale"] = scale_character(arm, old, ring, BODY_SCALE)
    ring = G.densify_ring(ring)  # S8b: 48 vertices, one to one with the body's end
    if CAGE_REMAP:  # H1: the cage's S1c-frame numbers onto this skeleton
        heads = {b.name: tuple(arm.matrix_world @ b.head_local) for b in arm.data.bones}
        heads["LeftToesTail"] = tuple(arm.matrix_world @ arm.data.bones["LeftToes"].tail_local)
        tz, tx, ty = remap_tables(heads, ring["z"], ring["step"])
        remap_constants(tz, tx, ty)
        report["remap"] = {"z": [[round(a, 4), round(b, 4)] for a, b in tz],
                           "x": [[round(a, 4), round(b, 4)] for a, b in tx],
                           "foot_y": [[round(a, 4), round(b, 4)] for a, b in ty],
                           "wrap_z": [[round(a, 4), b] for a, b in WRAP_Z],
                           "wrap_x": [[round(a, 4), b] for a, b in WRAP_X]}

    # The wrist: S1c's section at the hand's cut (WRIST_X + WRIST_GAP), as a radius per angle around its centre. The
    # standard ring and the cage's last octagon take that shape, so the arm meets the hand's section exactly.
    xs = WRIST_X + WRIST_GAP
    sec = []
    for e in old.data.edges:
        a, b = (old.data.vertices[i].co for i in e.vertices)
        if a.x > 0.3 and (a.x - xs) * (b.x - xs) < 0:
            p_ = a.lerp(b, (xs - a.x) / (b.x - a.x))
            sec.append((p_.y, p_.z))
    wy = (max(c[0] for c in sec) + min(c[0] for c in sec)) / 2
    wz = (max(c[1] for c in sec) + min(c[1] for c in sec)) / 2
    prof = sorted((math.atan2(z - wz, -(y - wy)) % (2 * math.pi), math.hypot(y - wy, z - wz)) for y, z in sec)
    prof = [(t - 2 * math.pi, r) for t, r in prof[-2:]] + prof + [(t + 2 * math.pi, r) for t, r in prof[:2]]

    def wrist_r(t):
        t %= 2 * math.pi
        for (t0, r0), (t1, r1) in zip(prof, prof[1:]):
            if t0 <= t <= t1:
                return r0 + (r1 - r0) * (t - t0) / max(t1 - t0, 1e-9)
        return prof[0][1]

    def wrist_pt(t, scale=1.0):
        r = wrist_r(t) * scale
        return wy - r * math.cos(t), wz + r * math.sin(t)
    wrist = {"count": 32, "x": WRIST_X, "centre": [round(wy, 5), round(wz, 5)],
             "radius_mean": round(sum(wrist_r(2 * math.pi * k / 32) for k in range(32)) / 32, 5),
             "shape": "S1c's wrist section at x + 0.005 (a radius per angle), not an ellipse",
             "order": "index k at angle 2*pi*k/count around +X from the front (-Y) towards up (+Z); the right "
                      "wrist is the mirror (x -> -x)",
             "axes": "Blender (Z up, front -Y); glTF/Godot: (x, z, -y)"}
    wrist["loop"] = [[WRIST_X] + [round(c, 5) for c in wrist_pt(2 * math.pi * k / 32)] for k in range(32)]

    # 1-2. The cage, mirrored and subdivided; the soles lowered until the subdivided sole is at z = 0.
    # The trunk's rings are fitted the same way: subdivision pulls a ring towards its neighbours (the belly's peak
    # comes back about a third), so each ring's cage numbers are corrected by the subdivided body's error against the
    # u1 target, until it is under FIT_TOL.
    drop = 0.0
    trunk = [list(t) for t in TRUNK]
    wrap = Wrap(args.target) if args.target else None
    gnames = [g.name for g in old.vertex_groups]
    gidx = {n: i for i, n in enumerate(gnames)}
    bones = {b.name: (arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local) for b in arm.data.bones
             if b.name.startswith("Left")}
    for it in range(FIT_ITERS):
        bm, rings = build_cage(drop, trunk, bones)
        for (dy, dz), v in zip(OCT, rings["wrist_cage"]):  # a subdivided octagon's edge lies at 0.902 of its radius
            v.co = Vector((WRIST_X, *wrist_pt(math.atan2(dz, -dy), 1 / 0.902)))
        if wrap:
            wrap.apply(bm, rings)
        dl = bm.verts.layers.deform.verify()
        for v, w in rings["hand_w"].items():
            for n, x in w.items():
                v[dl][gidx[n]] = x
        cage_faces = len(bm.faces)
        cage, body = subdivided(bm, "BodyNew", gnames)
        bm.free()
        low = min(v.co.z for v in body.data.vertices)
        worst = 0.0
        if wrap:  # the wrap replaces the trunk's u1 fit
            worst = wrap.measure(body) * FIT_TOL / WRAP_TOL
            report["wrap"] = wrap.report
        for row, target in zip(trunk, TRUNK if not wrap else []):
            name, z = row[0], row[1]
            if name not in FIT:
                continue
            m = trunk_measure(body.data, z)
            for i, key in ((2, "a"), (3, "yf"), (4, "yb")):
                if key in FIT[name] and m[key] is not None:
                    err = target[i] - m[key]
                    worst = max(worst, abs(err))
                    row[i] += err
        report.setdefault("fit_iterations", []).append({"sole_drop": round(drop, 5), "lowest": round(low, 5),
                                                        "trunk_worst_mm": round(worst * 1000, 2)})
        if (abs(low) < 0.0003 and worst < FIT_TOL) or it == FIT_ITERS - 1:
            break
        drop += low / 0.75
        for o in (cage, body):
            me = o.data
            bpy.data.objects.remove(o)
            bpy.data.meshes.remove(me)
    report["cage_trunk"] = [[t[0]] + [round(x, 4) for x in t[1:]] for t in trunk]
    report["cage"] = {"half_faces": cage_faces, "faces": len(cage.data.polygons), "verts": len(cage.data.vertices),
                      "poles": {str(k): len(v) for k, v in poles(cage.data).items()},
                      "pole_positions": poles(cage.data)}
    cage_me = cage.data
    cage_me.name = "BodyCage"
    cage_me.use_fake_user = True  # kept in the file as mesh data only, so no export picks it up
    bpy.data.objects.remove(cage)

    # 3. Rings. The body's open ends: the neck (z > 1.3) and the two wrists.
    me = body.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bnd = {v for e in bm.edges if e.is_boundary for v in e.verts}
    neck = [v for v in bnd if v.co.z > NECK_END - 0.074]
    cy = ring["centre"][1]
    ax, ay = (s / 0.98 for s in ring["semi_axes"])  # loop_below's semi-axes
    ax, ay = ax / 0.98, ay / 0.98
    neck, kn = angle_sort(neck, (0.0, cy), "z")
    zb = ring["z"] - 2 * ring["step"]
    err = 0.0
    nn = len(neck)
    for k, v in enumerate(neck):
        t = 2 * math.pi * k / nn
        new = Vector((ax * math.sin(t), cy - ay * math.cos(t), zb))
        err = max(err, (new - v.co).length)
        v.co = new
    report["neck"] = {"open_end": nn, "snap_max_mm": round(err * 1000, 2)}
    lower = [bm.verts.new(c) for c in ring["loop_below"]]
    top = [bm.verts.new(c) for c in ring["loop"]]
    N = len(lower)
    for k in range(N):
        bm.faces.new((lower[k], lower[(k + 1) % N], top[(k + 1) % N], top[k]))
    # S8b: the body's end meets the ring one to one (the ring densified to 48, G.densify_ring): plain quads, no S1
    # triangle zip, whose alternating triangles and quads showed as a pleated collar. A 24-vertex ring (a ring file
    # used without densifying) gets a quad reduction: four edges to two per unit, one middle vertex each.
    if nn == N:
        for k in range(N):
            bm.faces.new((neck[k], neck[(k + 1) % N], lower[(k + 1) % N], lower[k]))
        report["neck"]["join"] = f"quads {nn} -> {N}"
    elif nn != 2 * N or N % 2:
        raise RuntimeError(f"neck: the body's open end has {nn} vertices, the ring {N}; the join needs 1:1 or 2:1")
    for i in range(N // 2 if nn == 2 * N else 0):
        a = [neck[(4 * i + j) % nn] for j in range(5)]
        b = [lower[(2 * i + j) % N] for j in range(3)]
        m = bm.verts.new(a[2].co.lerp(b[1].co, 0.5))
        for f in ((a[0], a[1], m, b[0]), (a[1], a[2], a[3], m), (a[3], a[4], b[2], m), (b[0], m, b[2], b[1])):
            bm.faces.new(f)
        report["neck"]["join"] = f"quad reduction {nn} -> {N}"
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    ring_ids = {v.index for v in me.vertices if v.co.z > ring["z"] - ring["step"] - 1e-4}

    # 4. Weights. The hand's come from the cage (its loops' weights, interpolated by the subdivision); the rest from
    # S1c's body by nearest-face interpolation, scaled by what the hand's leave (the wrist ring is half and half).
    hand_w = [{g.group: g.weight for g in v.groups if g.weight > 0} for v in me.vertices]
    for n in gnames:
        if n not in body.vertex_groups:
            body.vertex_groups.new(name=n)
    gname = {g.index: g.name for g in body.vertex_groups}
    hand_w = [{gname[g]: w for g, w in d.items()} for d in hand_w]
    dt = body.modifiers.new("Weights", "DATA_TRANSFER")
    dt.object = old
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    dt.layers_vgroup_select_src = "ALL"
    dt.layers_vgroup_select_dst = "NAME"
    with bpy.context.temp_override(object=body, active_object=body):
        bpy.ops.object.modifier_apply(modifier=dt.name)
    nbody = len(me.vertices)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    dl = bm.verts.layers.deform.verify()
    gi0 = {g.name: g.index for g in body.vertex_groups}
    n_hand = 0
    for v in bm.verts:
        hw = hand_w[v.index] if v.index < len(hand_w) else {}
        s_ = sum(hw.values())
        if s_ <= 1e-4:
            continue
        n_hand += 1
        d = v[dl]
        tot = sum(d.values()) or 1.0
        keep = {g: w / tot * max(0.0, 1.0 - s_) for g, w in d.items()}
        for g in list(d.keys()):
            del d[g]
        for g, w in keep.items():
            if w > 1e-4:
                d[g] = w
        for n, w in hw.items():
            d[gi0[n]] = d.get(gi0[n], 0.0) + w
    report["hand_weighted_verts"] = n_hand
    # The hand's largest fold between neighbouring faces (a crease or a pinch would show here).
    bm.normal_update()
    folds = sorted(((math.degrees(e.link_faces[0].normal.angle(e.link_faces[1].normal)),
                     [round(c, 3) for c in (e.verts[0].co + e.verts[1].co) / 2]) for e in bm.edges
                    if len(e.link_faces) == 2 and e.verts[0].co.x > WRIST_X), reverse=True)
    report["hand_max_fold_deg"] = round(folds[0][0], 1)
    report["hand_folds_over_60"] = [[round(f, 1), at] for f, at in folds[:6] if f > 60]
    # Loose parts and open edges (only the neck ring's top should be open).
    seen, parts = set(), 0
    for v0 in bm.verts:
        if v0 in seen:
            continue
        parts += 1
        stack = [v0]
        seen.add(v0)
        while stack:
            for e in stack.pop().link_edges:
                for o in e.verts:
                    if o not in seen:
                        seen.add(o)
                        stack.append(o)
    report["loose_parts"] = parts
    report["open_edges_below_ring"] = [[round(c, 3) for c in (e.verts[0].co + e.verts[1].co) / 2]
                                       for e in bm.edges if e.is_boundary and e.verts[0].co.z < ring["z"] - 1e-4]
    deform = bm.verts.layers.deform.verify()
    gi = {g.name: g.index for g in body.vertex_groups}
    # The joints: each cage vertex's weights blended with its neighbours' (the hands and the rings keep theirs).
    free = [v for v in bm.verts if v.index < nbody and v.index not in ring_ids
            and abs(v.co.x) < WRIST_X - WRIST_KEEP]  # near the wrist the weights stay S1c's, as the hand's
    for _ in range(WEIGHT_SMOOTH):
        new = []
        for v in free:
            acc = {}
            nbs = [e.other_vert(v) for e in v.link_edges]
            for src, fw in [(v, 0.5)] + [(n, 0.5 / len(nbs)) for n in nbs]:
                for g, w in src[deform].items():
                    acc[g] = acc.get(g, 0.0) + fw * w
            new.append(acc)
        for v, acc in zip(free, new):
            d = v[deform]
            for g in list(d.keys()):
                del d[g]
            for g, w in acc.items():
                d[g] = w
    for v in bm.verts:
        d = v[deform]
        if v.index in ring_ids:
            for g in list(d.keys()):
                del d[g]
            for n, w in RING_W.items():
                d[gi[n]] = w
            continue
        top4 = sorted(d.items(), key=lambda kv: -kv[1])[:4]
        tot = sum(w for _, w in top4) or 1.0
        for g in list(d.keys()):
            del d[g]
        for g, w in top4:
            if w / tot > 0.005:
                d[g] = w / tot
    little = [gi[n] for n in gi if "Little" in n]
    leak = sum(1 for v in bm.verts if any(g in v[deform] for g in little))
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    report["little_weighted_verts"] = leak

    # The character: the new body replaces S1c's.
    old_name_mat = old.data.materials[0] if old.data.materials else None
    bpy.data.objects.remove(old)
    body.name = body.data.name = "Body"
    body.parent = arm
    body.modifiers.clear()
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    me.materials.clear()
    if old_name_mat:
        me.materials.append(old_name_mat)
    for poly in me.polygons:
        poly.material_index = 0
    if me.has_custom_normals:
        with bpy.context.temp_override(object=body, active_object=body, selected_editable_objects=[body]):
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for uv in list(me.uv_layers):
        me.uv_layers.remove(uv)
    me.uv_layers.new(name="UVMap")
    arm.data.pose_position = "POSE"
    me.calc_loop_triangles()
    report["body"] = {"verts": len(me.vertices), "tris": len(me.loop_triangles),
                      "height": round(max(v.co.z for v in me.vertices), 4),
                      "lowest": round(min(v.co.z for v in me.vertices), 5)}
    bm = bmesh.new()
    bm.from_mesh(me)
    report["body"]["open_edges"] = sum(1 for e in bm.edges if e.is_boundary and e.verts[0].co.z < ring["z"] - 0.005)
    report["body"]["non_manifold_edges"] = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    bm.free()
    # u1's measures against the body's: the trunk's front width (|x| < 0.2 at the midline's height) and midline depth.
    meas = {}
    for name, z, a, yf, yb in TRUNK:
        band = [v.co for v in me.vertices if abs(v.co.z - z) < 0.006 and abs(v.co.x) < 0.2]
        mid = [c for c in band if abs(c.x) < 0.01]
        if band and mid:
            meas[name] = {"z": z, "target_half_width": a, "half_width": round(max(abs(c.x) for c in band), 4),
                          "target_front_back": [yf, yb],
                          "front_back": [round(min(c.y for c in mid), 4), round(max(c.y for c in mid), 4)]}
    report["fit"] = meas
    # the midline's side profile every 2 cm (the front and back y) and the trunk's half width, for the u1 comparison
    report["profile"] = []
    for zc in range(70, 138, 2):
        m = trunk_measure(me, zc / 100)
        report["profile"].append([zc / 100] + [None if m[k] is None else round(m[k], 4) for k in ("a", "yf", "yb")])
    # each digit's subdivided radius at the middle of its second segment (the mean distance from the bone)
    report["finger_radius_mm"] = {}
    for f in FINGERS + ("Thumb",):
        h, t = bones[f"Left{f}{'Proximal' if f == 'Thumb' else 'Intermediate'}"]
        m, d = (h + t) / 2, (t - h).normalized()
        sec = [v.co - m for v in me.vertices if abs((v.co - m).dot(d)) < 0.0015 and (v.co - m).length < 0.019]
        r = [(c - d * c.dot(d)).length for c in sec]
        report["finger_radius_mm"][f] = round(1000 * sum(r) / max(len(r), 1), 1)
    report["hand_groups"] = {g.name: sum(1 for v in me.vertices for x in v.groups if x.group == g.index and x.weight > 0.01)
                             for g in body.vertex_groups if any(k in g.name for k in ("Thumb", "Index", "Middle", "Ring", "Little"))}
    report["wrist_section"] = wrist
    with open(f"{args.out}/neck_ring.json", "w", encoding="utf-8") as fh:
        json.dump(ring, fh, indent=1)
    with open(f"{args.out}/cage.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    body["prime_digits"] = json.dumps(report["digits"])  # M9: alien_detail.py's joint planes follow it
    bpy.ops.wm.save_as_mainfile(filepath=f"{args.out}/alien_body.blend")
    print("cage:", json.dumps({k: report[k] for k in ("body", "neck", "fit_iterations", "loose_parts",
                                                      "open_edges_below_ring", "little_weighted_verts",
                                                      "hand_weighted_verts", "hand_max_fold_deg", "hand_folds_over_60")}))


if __name__ == "__main__":
    main()
