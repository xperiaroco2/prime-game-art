"""Writes a body's dims table from its approved concept (art #196, step D2; plain Python, no Blender):
body_dims_geom.measure, then the hands, feet, the chest rounds, the neck ring and the key numbers, into
tools/blender/body_dims/<name>.toml, and the outlines for the drawing into <out>/<name>.json.

    $PYTHON_BIN tools/blender/body_dims_measure.py --name A --concept <image-0.png> --probe <A probe.json> --out DIR
    $PYTHON_BIN tools/blender/body_dims_measure.py --name B --concept <image-0.png> --probe <A probe.json> --out DIR \
        --height-ratio 0.953

The probe (body_dims_probe.py on body A's alien_body.blend) gives the landmarks: the neck ring's loop and height, the
crotch, the mid-depth the side view is aligned to, the joints; B's are A's times --height-ratio (f's 0.953, B1).
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import body_dims_geom as G

FINE = {"neck": (-140.0, 0.0), "chest": (-340.0, -140.0), "crotch": (-50.0, 50.0)}  # around the ring and the crotch


def body_landmarks(probe: dict, ratio: float) -> dict:
    """The body's own heights (mm) for the height map, from body A's probe times ratio."""
    V = probe["vertices"]
    crotch = min(v[2] for v in V if abs(v[0]) < 0.006 and 0.5 < v[2] < 1.0
                 and v[3] in ("Hips", "LeftUpperLeg", "RightUpperLeg")) * 1000
    ring = probe["loops"][0]
    zc = crotch + 60
    near = [v for v in V if abs(v[2] * 1000 - zc) < 6 and v[3] in ("Hips", "LeftUpperLeg", "RightUpperLeg")]
    mid_y = (min(v[1] for v in near) + max(v[1] for v in near)) / 2 * 1000
    b = probe["bones"]
    joints = {"shoulder": b["LeftUpperArm"]["head"], "elbow": b["LeftLowerArm"]["head"], "wrist": b["LeftHand"]["head"],
              "fingertip": b["LeftMiddleDistal"]["tail"], "hip": b["LeftUpperLeg"]["head"],
              "knee": b["LeftLowerLeg"]["head"], "ankle": b["LeftFoot"]["head"], "toe": b["LeftToes"]["tail"],
              "neck": b["Neck"]["head"], "head": b["Head"]["head"]}
    return {"ring_z": ring["centre"][2] * 1000 * ratio, "crotch_z": crotch * ratio, "mid_y": mid_y,
            "ring": ring, "joints": {k: [round(c * 1000 * (ratio if i == 2 else 1.0), 1) for i, c in enumerate(v)]
                                     for k, v in joints.items()}}


def hands_feet(d: dict) -> dict:
    lm, sc = d["landmarks"], d["scale"]
    k = sc["mm_px"]
    cos = math.cos(math.radians(d["arm_axis"]["angle_deg"]))
    front, cx = d["_front"], lm["cx"]
    # the hand: the rows from the wrist down; the digits are the runs outside the leg and trunk on the image left
    counts, widths, first3, thumb = {}, [], None, None
    for y in range(lm["wrist"], lm["hand_end"] + 1):
        ext = d["_arm"](y, -1)
        if not ext:
            continue
        rs = [r for r in front[y] if r[0] >= ext[0] and r[1] <= ext[1]]
        counts[y] = len(rs)
        if len(rs) >= 2 and thumb is None:
            thumb = y
        if len(rs) >= 3:
            first3 = first3 or y
            widths += [r[1] - r[0] + 1 for r in rs]
    hand_w = max((lambda e: e[1] - e[0] + 1)(d["_arm"](y, -1)) for y in counts) * k * cos
    widths.sort()
    finger_t = widths[len(widths) // 2] * k * cos if widths else None
    finger_len = (lm["hand_end"] - first3) * k / cos if first3 else None
    # the foot: front width from the ankle to the sole; side length and the toe's height
    foot_w = max(G._w(d["_leg"](y, -1)) or 0 for y in range(lm["ankle"], lm["sole"] + 1)) * k
    side, sf, sb = d["_side"], d["_sf"], d["_sb"]
    ssole = side["sole"]
    rows = [y for y in range(ssole - 12, ssole + 1) if y in sf]
    toe_px, heel_px = min(sf[y] for y in rows), max(sb[y] for y in rows)
    span = heel_px - toe_px
    m = d["_mask"]
    toe_cols = range(int(toe_px), int(toe_px + 0.2 * span))
    foot_top = ssole - round(0.12 * (ssole - side["top"]))
    toe_top = min(y for y in range(foot_top, ssole + 1) for x in toe_cols if m[y][x])
    ankle_side = side["sole"] - G.z_of(lm["ankle"], lm, sc) / k
    ya = round(ankle_side)
    ankle_mid = (sf[ya] + sb[ya]) / 2
    return {"hand": {"digits": 4, "length": round((d["arm_axis"]["s_end"] - d["arm_axis"]["s_wrist"]), 1),
                     "width": round(hand_w, 1), "finger_length": finger_len and round(finger_len, 1),
                     "finger_thickness": finger_t and round(finger_t, 1),
                     "thumb_from_wrist": thumb and round((thumb - lm["wrist"]) * k / cos, 1),
                     "most_runs": max(counts.values())},
            "foot": {"length": round(span * k, 1), "width": round(foot_w, 1),
                     "toe_ahead_of_ankle": round((ankle_mid - toe_px) * k, 1),
                     "heel_behind_ankle": round((heel_px - ankle_mid) * k, 1),
                     "toe_height": round((ssole - toe_top) * k, 1), "ankle_z": round(G.z_of(lm["ankle"], lm, sc), 1),
                     "toe_shape": "one soft rounded front, no separate toes"}}


def chest(d: dict, to_body) -> dict:
    """The chest from the side (the front edge's apex and the hollow under it) and the rounds' centres from the front
    (the luminance's two highlights across the trunk at the apex height)."""
    t = d["trunk"]
    zs, fy = t["z"], t["front_y"]
    arm_z = to_body(G.z_of(d["landmarks"]["armpit"], d["landmarks"], d["scale"]))  # the table's z is the body's
    band = [i for i, z in enumerate(zs) if arm_z - 150 <= z <= arm_z + 80 and fy[i] is not None]
    apex = min(band, key=lambda i: fy[i])
    wide = [i for i, z in enumerate(zs) if zs[apex] - 150 <= z < zs[apex] and fy[i] is not None]
    # under the round: going down from the apex, the first station where the front edge stops receding fast (its
    # slope under 30 % of the steepest in the band): the crease, not the belly line further down
    slope = {i: (fy[i] - fy[i + 1]) / (zs[i + 1] - zs[i]) for i in wide if i + 1 < len(zs) and fy[i + 1] is not None}
    steep = max(slope, key=lambda i: slope[i], default=apex)
    top_s = slope.get(steep, 0.0)
    under = max((i for i in wide if i in slope and zs[i] < zs[steep] and slope[i] < 0.3 * top_s),
                key=lambda i: zs[i], default=apex)
    above = max((i for i in band if zs[i] > zs[apex]), key=lambda i: fy[i], default=apex)
    lm, sc, rows = d["landmarks"], d["scale"], d["_rows"]
    y = round(G.y_of(t["z_concept"][apex], lm, sc))
    r = G.run_at(d["_front"][y], lm["cx"])
    prof = []
    for x in range(r[0], r[1] + 1):
        prof.append(sum(G.luminance(rows[yy][x]) for yy in range(y - 6, y + 7)) / 13)
    sm = [sum(prof[max(0, i - 4):i + 5]) / len(prof[max(0, i - 4):i + 5]) for i in range(len(prof))]
    c = lm["cx"] - r[0]
    q = (r[1] - r[0]) // 8
    left = max(range(q, c - 15), key=lambda i: sm[i])
    k = sc["mm_px"]
    # the light comes from the image's left: the lit round's highlight is the clear one, and it sits toward the
    # light by about a tenth of its offset (checked by eye on b_c3s against the table's centre_x)
    return {"rounds": True, "apex_z": zs[apex], "apex_front_y": fy[apex], "under_z": zs[under],
            "under_front_y": fy[under], "top_z": zs[above], "projection": round(fy[under] - fy[apex], 1),
            "projection_from_top": round(fy[above] - fy[apex], 1),
            "centre_x": round(0.9 * (c - left) * k, 1), "centre_z": round((zs[above] + zs[under]) / 2, 1),
            "width": round(zs[above] - zs[under], 1),
            "note": "two soft rounds, no nipples; the width is the round's height from the side (a round)"}


def fingers(probe: dict, scale_: float) -> dict:
    """Per digit of body A's hand: its length (the proximal head to the distal tail) and thickness (twice the median
    distance of its vertices from the bone line), times scale_; the thumb's base from the wrist."""
    b, V = probe["bones"], probe["vertices"]
    out = {}
    for f in ("Thumb", "Index", "Middle", "Ring", "Little"):
        p, q = b.get(f"Left{f}Proximal"), b.get(f"Left{f}Distal")
        if not p or not q:
            continue
        h, t = p["head"], q["tail"]
        ax = [t[i] - h[i] for i in range(3)]
        L = math.sqrt(sum(a * a for a in ax))
        u = [a / L for a in ax]
        ds = []
        for v in V:
            if v[3] in (f"Left{f}Proximal", f"Left{f}Distal"):
                d = [v[i] - h[i] for i in range(3)]
                along = sum(d[i] * u[i] for i in range(3))
                ds.append(math.sqrt(max(0.0, sum(x * x for x in d) - along * along)))
        if not ds:
            continue
        ds.sort()
        out[f.lower()] = {"length": round(L * 1000 * scale_, 1),
                          "thickness": round(2 * ds[len(ds) // 2] * 1000 * scale_, 1)}
    w = b["LeftHand"]["head"]
    th = b["LeftThumbProximal"]["head"]
    out["thumb_base_from_wrist"] = [round((th[i] - w[i]) * 1000 * scale_, 1) for i in range(3)]
    return out


def key_numbers(d: dict, hf: dict, to_body) -> dict:
    """The key numbers; the windows are in the tables' (the body's) z: the concept's landmark heights mapped first."""
    t, legs, arms, ax = d["trunk"], d["legs"], d["arms"], d["arm_axis"]
    lm, sc = d["landmarks"], d["scale"]
    arm_c = G.z_of(lm["armpit"], lm, sc)
    arm_z = to_body(arm_c)
    cr = to_body(d["crotch_concept"])

    def at(table, key, zkey, lo, hi, f):
        vals = [(v, z) for v, z in zip(table[key], table[zkey]) if v is not None and lo <= z <= hi]
        return f(vals, key=lambda p: p[0]) if vals else (None, None)
    shz = to_body(G.z_of(lm["shoulder"], lm, sc))
    sh = at(t, "front_w", "z", shz - 6, shz + 6, max)
    ch = at(t, "front_w", "z", arm_z - 40, arm_z - 20, max)
    wa = at(t, "front_w", "z", cr + 100, arm_z - 60, min)
    hp = at(t, "front_w", "z", cr, cr + 250, max)
    th = at(legs, "width", "z", cr - 80, cr - 40, max)
    ca = at(legs, "width", "z", 200, 450, max)
    ua = at(arms, "width", "s", ax["s_armpit"] + 30, ax["s_armpit"] + 60, max)
    fa = at(arms, "width", "s", ax["s_wrist"] - 160, ax["s_wrist"] - 60, max)
    ring_i = len(t["z"]) - 1
    rz = round(sc["ring_z"], 1)   # the table's z are rounded to 0.1 mm, its last row the ring's
    near = [i for i, z in enumerate(t["z"]) if rz - 60 <= z <= rz and t["depth"][i] is not None]
    neck_d = min(t["depth"][i] for i in near)
    return {"height_top": round(sc["top_z"], 1), "ring_z": round(sc["ring_z"], 1),
            "shoulder_w": sh[0], "shoulder_z": sh[1], "chest_w": ch[0], "chest_z": ch[1], "waist_w": wa[0],
            "waist_z": wa[1], "hip_w": hp[0], "hip_z": hp[1], "thigh_w": th[0], "calf_w": ca[0], "calf_z": ca[1],
            "upper_arm_w": ua[0], "forearm_w": fa[0], "hand_length": hf["hand"]["length"],
            "hand_width": hf["hand"]["width"], "foot_length": hf["foot"]["length"], "foot_width": hf["foot"]["width"],
            "neck_at_ring_w": t["front_w"][ring_i], "neck_at_ring_d": neck_d,
            "armpit_z": round(arm_z, 1), "armpit_z_concept": round(arm_c, 1), "crotch_z_concept": d["crotch_concept"]}


def toml_value(v) -> str:
    if v is None:
        return '"-"'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(round(v, 4))
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, list):
        return "[" + ", ".join(toml_value(x) for x in v) + "]"
    raise TypeError(v)


def to_toml(doc: dict, head: str) -> str:
    """Tables of scalars and lists (None as "-"); lists of numbers wrap at 16 per line."""
    out = [head.rstrip(), ""]
    for name, table in doc.items():
        out.append(f"[{name}]")
        for k, v in table.items():
            if isinstance(v, list) and len(v) > 16 and not isinstance(v[0], list):
                parts = [", ".join(toml_value(x) for x in v[i:i + 16]) for i in range(0, len(v), 16)]
                out.append(f"{k} = [\n  " + ",\n  ".join(parts) + ",\n]")
            else:
                out.append(f"{k} = {toml_value(v)}")
        out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--concept", required=True)
    ap.add_argument("--probe", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--height-ratio", type=float, default=1.0)
    ap.add_argument("--note", default="")
    ap.add_argument("--chest", action="store_true", help="measure the chest's two rounds (body B)")
    args = ap.parse_args()
    probe = json.loads(Path(args.probe).read_text(encoding="utf-8"))
    bl = body_landmarks(probe, args.height_ratio)
    ring = bl["ring_z"]
    fine = {k: (ring + a if k != "crotch" else bl["crotch_z"] + a, ring + b if k != "crotch" else bl["crotch_z"] + b)
            for k, (a, b) in FINE.items()}
    d = G.measure(args.concept, ring, bl["crotch_z"], bl["mid_y"], fine)
    hf = hands_feet(d)
    to_body = G.zmap([(0.0, 0.0), (d["crotch_concept"], bl["crotch_z"]), (ring, ring)])[0]
    ch = chest(d, to_body) if args.chest else {"rounds": False}
    b = probe["bones"]
    our_hand = (b["LeftMiddleDistal"]["tail"][0] - b["LeftHand"]["head"][0]) * 1000 * args.height_ratio
    hf["hand"]["our_length"] = round(our_hand, 1)
    hf["hand"] |= {f"{k}_{kk}": vv for k, v in fingers(probe, hf["hand"]["length"] / our_hand * args.height_ratio).items()
                   if isinstance(v, dict) for kk, vv in v.items()}
    hf["hand"]["thumb_base_from_wrist"] = fingers(probe, hf["hand"]["length"] / our_hand * args.height_ratio)["thumb_base_from_wrist"]
    hf["hand"]["digits_note"] = ("four digits (three fingers and a thumb) as the concept and body A; the concept's "
                                 "fingers curl together in the front view, so their lengths and thicknesses are body "
                                 "A's hand scaled to the concept's hand length")
    hf["hand"].pop("finger_length")
    hf["hand"].pop("finger_thickness")
    keys = key_numbers(d, hf, to_body)
    lm, sc = d["landmarks"], d["scale"]
    concept_z = {k: round(G.z_of(lm[k], lm, sc), 1) for k in
                 ("top", "ring", "shoulder_top", "shoulder", "armpit", "wrist", "hand_end", "crotch", "ankle")}
    lp = bl["ring"]
    head_above = round((probe["bones"]["Head"]["head"][2] - lp["centre"][2]) * 1000, 1)
    neck_below = round((lp["centre"][2] - probe["bones"]["Neck"]["head"][2]) * 1000, 1)
    # the ring's tilt from the side: its back's height over its front's across its depth (+: the back higher)
    tilt = math.degrees(math.atan2((lp["back_z"] - lp["front_z"]) * 1000, 2 * lp["y_half"] * 1000))
    joints = dict(bl["joints"])
    joints["neck"] = joints["neck"][:2] + [round(ring - neck_below, 1)]
    joints["head"] = joints["head"][:2] + [round(ring + head_above, 1)]
    doc = {
        "body": {"name": args.name, "concept": args.concept.replace("\\", "/"), "height_ratio": args.height_ratio,
                 "mm_per_px": round(sc["mm_px"], 4), "side_mid_y": round(bl["mid_y"], 1),
                 "side_hidden_z": d["side_hidden_z"] or "-", "side_back_hidden_z": d["side_back_hidden_z"] or "-",
                 "note": args.note},
        "keys": keys,
        "landmarks_concept": concept_z,
        "skeleton": joints | {
            "note": "body A's joints (S4b), z times height_ratio (B1's rule), but Neck and Head at the standard "
                    "ring's offsets (ring - neck_bone_below, ring + head_bone_above); the arms in A's T rest"},
        "height_map": {"concept_z": [0.0, d["crotch_concept"], ring], "body_z": [0.0, round(bl["crotch_z"], 1), ring]},
        "neck_ring": {"z": round(ring, 1), "vertices": lp["count"], "centre_y": round(lp["centre"][1] * 1000, 1),
                      "half_x": round(lp["x_half"] * 1000, 1), "half_y": round(lp["y_half"] * 1000, 1),
                      "tilt_deg": round(tilt, 1) + 0.0, "z_span": round((lp["z_max"] - lp["z_min"]) * 1000, 1),
                      "head_bone_above": head_above, "neck_bone_below": neck_below,
                      "concept_w": keys["neck_at_ring_w"], "concept_d": keys["neck_at_ring_d"]},
        "trunk": d["trunk"],
        "legs": d["legs"] | {"axis_deg": d["leg_axis"]["angle_deg"]},
        "arms": d["arms"] | {"axis_deg": d["arm_axis"]["angle_deg"], "s_armpit": d["arm_axis"]["s_armpit"],
                             "s_wrist": d["arm_axis"]["s_wrist"], "s_end": d["arm_axis"]["s_end"]},
        "hand": hf["hand"],
        "foot": hf["foot"],
        "chest": ch,
    }
    head = (f"# Body {args.name}'s dims table (art #196, step D2): read from its approved concept per pixel row by\n"
            "# body_dims_measure.py (body_dims_geom.py); regenerate, never hand-edit. Lengths in mm, the body file's\n"
            "# frame (x lateral, z up from the sole, the front at -y); \"-\" where a view has no value: the trunk's\n"
            "# widths, depth, front_y and back_y under the crotch (the legs' own table holds them), and front_y and\n"
            "# depth (trunk and legs) over body.side_hidden_z, where the hand hangs in front of the body in the side\n"
            "# view, and back_y and depth over body.side_back_hidden_z, where the hanging arm, not the body, forms\n"
            "# the side's back edge (from under the armpits down to where the seat comes out behind the arm). Those\n"
            "# edges are not measured (no interpolated values); each band is its first and last table height without\n"
            "# them. trunk.front_w above the armpits is the outline across the shoulder caps. The limbs' s runs along their own axes (arms from the shoulder line,\n"
            "# legs from the crotch); their widths are across the axis. The neck ring is the standard ring\n"
            "# (docs/decisions/2026-10-29-neck-ring.md); its concept_w and concept_d are the concept's neck there.")
    tables = Path(__file__).with_name("body_dims")
    tables.mkdir(exist_ok=True)
    (tables / f"{args.name}.toml").write_text(to_toml(doc, head), encoding="utf-8", newline="\n")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    keep = {k: v for k, v in d.items() if not k.startswith("_")}
    (out / f"{args.name}.json").write_text(json.dumps(keep | {"doc": doc}), encoding="utf-8")
    print(json.dumps({"keys": keys, "chest": ch, "hand": hf["hand"], "foot": hf["foot"], "concept_z": concept_z}))


if __name__ == "__main__":
    main()
