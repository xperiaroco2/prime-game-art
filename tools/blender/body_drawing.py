"""The bodies' drawing sheets in mm (art #196, step D2): plain Python, no Blender; a raster canvas with a 5 x 7 bitmap
font, written as PNG. From the dims tables (tools/blender/body_dims/<name>.toml) and the measure's JSON
(body_dims_measure.py --out, the concept's panels and landmarks):

- <out>/drawing_<name>.png: top row the front, side and back outlines in ink with the key dimensions; bottom row the
  concept's views with the same outlines over them (the outlines at the concept's own heights);
- <out>/drawing_AB.png: A and B side by side at one scale, front and side, with their key numbers.

    $PYTHON_BIN tools/blender/body_drawing.py --dims <measure out dir> --out DIR [--names A B]
"""
from __future__ import annotations

import argparse
import json
import math
import tomllib
from pathlib import Path

import body_dims_geom as G

FONT = {  # 5 columns per glyph, bit 0 the top row (the classic 5 x 7 table)
    "A": "7c1211127c", "B": "7f49494936", "C": "3e41414122", "D": "7f4141221c", "E": "7f49494941",
    "F": "7f09090901", "G": "3e4149497a", "H": "7f0808087f", "I": "00417f4100", "J": "2040413f01",
    "K": "7f08142241", "L": "7f40404040", "M": "7f020c027f", "N": "7f0408107f", "O": "3e4141413e",
    "P": "7f09090906", "Q": "3e4151215e", "R": "7f09192946", "S": "4649494931", "T": "01017f0101",
    "U": "3f4040403f", "V": "1f2040201f", "W": "3f4038403f", "X": "6314081463", "Y": "0708700807",
    "Z": "6151494543", "0": "3e5149453e", "1": "00427f4000", "2": "4261514946", "3": "2141454b31",
    "4": "1814127f10", "5": "2745454539", "6": "3c4a494930", "7": "0171090503", "8": "3649494936",
    "9": "064949291e", ".": "0060600000", ",": "0050300000", "-": "0808080808", ":": "0036360000",
    "/": "2010080402", "(": "001c224100", ")": "0041221c00", "=": "1414141414", "+": "08083e0808",
    " ": "0000000000", "%": "2313086462",
}
PAPER, INK, DIM, RING, FAINT = (244, 241, 232), (30, 42, 54), (155, 59, 22), (20, 120, 200), (184, 178, 162)
OVER = (255, 210, 60)


class Canvas:
    def __init__(self, w: int, h: int, bg=PAPER) -> None:
        self.w, self.h = w, h
        self.px = bytearray(bytes(bg) * (w * h))

    def dot(self, x: int, y: int, c, r: int = 0) -> None:
        for yy in range(y - r, y + r + 1):
            for xx in range(x - r, x + r + 1):
                if 0 <= xx < self.w and 0 <= yy < self.h:
                    i = (yy * self.w + xx) * 3
                    self.px[i:i + 3] = bytes(c)

    def line(self, a, b, c, r: int = 0) -> None:
        (x0, y0), (x1, y1) = a, b
        n = max(1, int(max(abs(x1 - x0), abs(y1 - y0))))
        for i in range(n + 1):
            t = i / n
            self.dot(round(x0 + t * (x1 - x0)), round(y0 + t * (y1 - y0)), c, r)

    def poly(self, pts, c, r: int = 0) -> None:
        for a, b in zip(pts, pts[1:]):
            self.line(a, b, c, r)

    def text(self, x: int, y: int, s: str, c=INK, k: int = 2) -> int:
        """Upper-case text at (x, y) (top left), k px per font pixel; returns the end x."""
        for ch in s.upper():
            cols = FONT.get(ch, FONT[" "])
            for ci in range(5):
                v = int(cols[2 * ci:2 * ci + 2], 16)
                for ri in range(7):
                    if v >> ri & 1:
                        for dy in range(k):
                            for dx in range(k):
                                xx, yy = x + ci * k + dx, y + ri * k + dy
                                if 0 <= xx < self.w and 0 <= yy < self.h:
                                    i = (yy * self.w + xx) * 3
                                    self.px[i:i + 3] = bytes(c)
            x += 6 * k
        return x

    def blit(self, rows, box, at, f: float, fade: float = 0.0) -> None:
        """Paste the picture's box (x0, y0, x1, y1) at `at`, scaled by f (box filter), faded toward the paper."""
        x0, y0, x1, y1 = box
        W, H = int((x1 - x0) * f), int((y1 - y0) * f)
        for j in range(H):
            sy0, sy1 = y0 + int(j / f), max(y0 + int(j / f) + 1, y0 + int((j + 1) / f))
            for i in range(W):
                sx0, sx1 = x0 + int(i / f), max(x0 + int(i / f) + 1, x0 + int((i + 1) / f))
                acc, n = [0, 0, 0], 0
                for yy in range(sy0, min(sy1, len(rows))):
                    for xx in range(sx0, min(sx1, len(rows[0]))):
                        p = rows[yy][xx]
                        acc[0] += p[0]; acc[1] += p[1]; acc[2] += p[2]
                        n += 1
                if n:
                    c = [round(a / n * (1 - fade) + PAPER[k] * fade) for k, a in enumerate(acc)]
                    self.dot(at[0] + i, at[1] + j, c)

    def save(self, path) -> Path:
        return G.write_png(path, self.w, self.h, self.px)


def outlines(doc: dict, concept_z: bool = False) -> dict:
    """The views' polylines in mm: front and back (x, z), side (y, z), from a dims table; z the body's, or the
    concept's own heights when concept_z (for the overlay)."""
    t, legs, arms = doc["trunk"], doc["legs"], doc["arms"]
    hm = doc["height_map"]
    to_c = G.zmap(list(zip(hm["body_z"], hm["concept_z"])))[0] if concept_z else (lambda z: z)

    def num(v):
        return None if v == "-" else v
    out = {"front": [], "back": [], "side": []}
    for key, view in (("front_w", "front"), ("back_w", "back")):
        pts = [(num(w) / 2, to_c(z)) for z, w in zip(t["z"], t[key]) if num(w) is not None]
        out[view] += [pts, [(-x, z) for x, z in pts]]
    lc = math.cos(math.radians(legs["axis_deg"]))
    outer = [(c + w / 2 / lc, to_c(z)) for z, w, c in zip(legs["z"], legs["width"], legs["centre_x"])]
    inner = [(c - w / 2 / lc, to_c(z)) for z, w, c in zip(legs["z"], legs["width"], legs["centre_x"])]
    ac = math.cos(math.radians(arms["axis_deg"]))
    aout = [(c + w / 2 / ac, to_c(z)) for z, w, c in zip(arms["z"], arms["width"], arms["centre_x"])]
    ain = [(c - w / 2 / ac, to_c(z)) for z, w, c in zip(arms["z"], arms["width"], arms["centre_x"])]
    for view in ("front", "back"):
        for pl in (outer, inner, aout, ain):
            out[view] += [pl, [(-x, z) for x, z in pl]]
    fy = [(num(a), to_c(z)) for z, a in zip(t["z"], t["front_y"]) if num(a) is not None]
    by = [(num(a), to_c(z)) for z, a in zip(t["z"], t["back_y"]) if num(a) is not None]
    # under the crotch the side is the legs' own table (the trunk's side values stop there)
    lfy = [(num(a), to_c(z)) for z, a in zip(legs["z"], legs["front_y"]) if num(a) is not None]
    lby = [(num(a), to_c(z)) for z, a in zip(legs["z"], legs["back_y"]) if num(a) is not None]
    out["side"] = [fy, by, lfy, lby]
    return out


def dims_list(doc: dict) -> list[tuple[str, float, float, float]]:
    """(label, z, half-width, value) of the front's key dimensions."""
    k, nr = doc["keys"], doc["neck_ring"]
    legs, arms = doc["legs"], doc["arms"]

    def leg_at(z):
        i = min(range(len(legs["z"])), key=lambda i: abs(legs["z"][i] - z))
        return legs["centre_x"][i], legs["width"][i]
    rows = [("shoulder", k["shoulder_z"], k["shoulder_w"] / 2, k["shoulder_w"]),
            ("chest", k["chest_z"], k["chest_w"] / 2, k["chest_w"]),
            ("waist", k["waist_z"], k["waist_w"] / 2, k["waist_w"]),
            ("hip", k["hip_z"], k["hip_w"] / 2, k["hip_w"])]
    crotch = doc["height_map"]["body_z"][1]   # the drawing's z is the body's (the tables' stations)
    c, w = leg_at(crotch - 60)
    rows.append(("thigh", crotch - 60, c + w / 2, k["thigh_w"]))
    c, w = leg_at(k["calf_z"])
    rows.append(("calf", k["calf_z"], c + w / 2, k["calf_w"]))
    rows.append(("neck ring", nr["z"], nr["half_x"], 2 * nr["half_x"]))
    return rows


def draw_view(cv: Canvas, pls, ox: int, oz: int, s: float, c, r: int = 1, flip: bool = False) -> None:
    for pl in pls:
        pts = [(ox + (-x if flip else x) * s, oz - z * s) for x, z in pl]
        cv.poly(pts, c, r)


def body_sheet(doc: dict, meas: dict, out: Path) -> Path:
    s = 0.40                                  # px per mm
    k = doc["keys"]
    H = k["height_top"]
    rowh = int(H * s) + 90
    W = 1900
    cv = Canvas(W, 2 * rowh + 60)
    name = doc["body"]["name"]
    cv.text(20, 14, f"BODY {name}   DIMS IN MM   SCALE 1:{round(1000 / s / 3.78)} ON SCREEN   "
                    f"CONCEPT {Path(doc['body']['concept']).parent.name}", INK, 3)
    ol = outlines(doc)
    oz = 60 + int(H * s) + 20
    cx = {"front": 260, "side": 900, "back": 1450}
    for view in ("front", "back"):
        draw_view(cv, ol[view], cx[view], oz, s, INK)
    draw_view(cv, ol["side"], cx["side"], oz, s, INK)
    nr = doc["neck_ring"]
    for view in ("front", "back"):
        cv.line((cx[view] - nr["half_x"] * s, oz - nr["z"] * s), (cx[view] + nr["half_x"] * s, oz - nr["z"] * s), RING, 2)
    cv.line((cx["side"] + (nr["centre_y"] - nr["half_y"]) * s, oz - nr["z"] * s),
            (cx["side"] + (nr["centre_y"] + nr["half_y"]) * s, oz - nr["z"] * s), RING, 2)
    # the head above the ring: a faint box to the concept's top
    cv.line((cx["front"] - 60, oz - H * s), (cx["front"] + 60, oz - H * s), FAINT, 0)
    # height
    cv.line((40, oz), (40, oz - H * s), DIM, 0)
    cv.text(48, int(oz - H * s) - 4, f"TOP {H:.0f}", DIM)
    cv.text(48, int(oz - nr["z"] * s) - 4, f"RING {nr['z']:.0f}", RING)
    cv.line((20, oz), (W - 20, oz), FAINT, 0)
    # front dimensions: a line across the body, the label at the right of the front view
    lx = 520
    for i, (label, z, half, val) in enumerate(dims_list(doc)):
        y = oz - z * s
        col = RING if label == "neck ring" else DIM
        cv.line((cx["front"] - half * s, y), (cx["front"] + half * s, y), col, 0)
        cv.line((cx["front"] + half * s, y), (lx - 6, y), FAINT, 0)
        cv.text(lx, int(y) - 7, f"{label} {val:.0f} AT {z:.0f}", col)
    arms, hand, foot = doc["arms"], doc["hand"], doc["foot"]
    ua = k["upper_arm_w"]
    extra = [f"UPPER ARM {ua:.0f}", f"FOREARM {k['forearm_w']:.0f}", f"ARM AXIS {arms['axis_deg']:.0f} DEG",
             f"HAND {hand['length']:.0f} X {hand['width']:.0f}, 4 DIGITS", f"FOOT {foot['length']:.0f} X {foot['width']:.0f}",
             f"LEG AXIS {doc['legs']['axis_deg']:.0f} DEG", f"CROTCH {doc['height_map']['body_z'][1]:.0f} (CONCEPT {k['crotch_z_concept']:.0f})",
             f"ARMPIT (CONCEPT) {k['armpit_z']:.0f}"]
    ch = doc["chest"]
    rounds = [f"CHEST ROUNDS +{ch['projection']:.0f} AT {ch['apex_z']:.0f}",
              f"ROUNDS {2 * ch['centre_x']:.0f} APART"] if ch.get("rounds") else []
    ex_y = int(oz - (H - 120) * s) - len(rounds) * 22   # the column moves up to keep clear of the depth labels
    for i, e in enumerate(extra + rounds):
        cv.text(cx["side"] + 140, ex_y + i * 22, e, RING if i >= len(extra) else INK)
    # side dimensions: depth at the chest, waist, seat
    t = doc["trunk"]
    for label, zz in (("depth chest", k["chest_z"]), ("depth waist", k["waist_z"]), ("depth seat", k["hip_z"] + 60)):
        i = min(range(len(t["z"])), key=lambda i: abs(t["z"][i] - zz))
        f_, b_ = t["front_y"][i], t["back_y"][i]
        if "-" in (f_, b_):
            continue   # the hand hides the front there (body.side_hidden_z)
        y = oz - t["z"][i] * s
        cv.line((cx["side"] + f_ * s, y), (cx["side"] + b_ * s, y), DIM, 0)
        cv.text(cx["side"] + 140, int(y) - 7, f"{label} {b_ - f_:.0f}", DIM)
    if ch.get("rounds"):
        # no dots on the chest (they read as nipples): a tick on the side's profile, a dimension line between
        # the rounds' centres on the front; their labels end the extras' column
        y = oz - ch["apex_z"] * s
        ax = cx["side"] + ch["apex_front_y"] * s
        cv.line((ax - 14, y), (ax - 4, y), RING, 1)
        yc = oz - (ch["centre_z"] + 90) * s
        x0, x1 = cx["front"] - ch["centre_x"] * s, cx["front"] + ch["centre_x"] * s
        cv.line((x0, yc), (x1, yc), RING, 0)
        for xx in (x0, x1):
            cv.line((xx, yc - 4), (xx, yc + 4), RING, 0)
    for view, lab in (("front", "FRONT"), ("side", "SIDE (FRONT TO THE LEFT)"), ("back", "BACK")):
        cv.text(cx[view] - 60, oz + 14, lab, INK)
    # the bottom row: the concept's views with the outlines over them
    lm, sc = meas["landmarks"], meas["scale"]
    w_, h_, rows = G.read_png(doc["body"]["concept"])
    f = sc["mm_px"] * s
    oz2 = oz + rowh
    olc = outlines(doc, concept_z=True)
    for view, pi, ccol, sole in (("front", 0, lm["cx"], lm["sole"]), ("side", 2, meas["side_mid_px"], meas["side"]["sole"]),
                                 ("back", 3, meas["back"]["cx"], meas["back"]["sole"])):
        x0, x1 = meas["panels"][pi]
        top = int(sole - H / sc["mm_px"]) - 10
        cv.blit(rows, (x0 - 20, max(0, top), x1 + 20, sole + 4), (int(cx[view] - (ccol - x0 + 20) * f),
                                                                  int(oz2 - (sole - max(0, top)) * f)), f, 0.25)
        if view == "side":
            # the side's outline sits at the body's y; on the concept its mid is the side_mid_px column
            mid_y = doc["_mid_y"]
            pls = [[(y - mid_y, z) for y, z in pl] for pl in olc["side"]]
            draw_view(cv, pls, cx[view], oz2, s, OVER, 1)
        else:
            draw_view(cv, olc[view], cx[view], oz2, s, OVER, 1)
    cv.text(20, oz + 50, "THE CONCEPT UNDER THE TABLE OUTLINES (YELLOW), AT THE CONCEPT HEIGHTS", INK)
    return cv.save(out / f"drawing_{name}.png")


def ab_sheet(docs: list[dict], out: Path) -> Path:
    s = 0.40
    H = max(d["keys"]["height_top"] for d in docs)
    cv = Canvas(1600, int(H * s) + 260)
    cv.text(20, 14, "BODIES A AND B AT ONE SCALE, DIMS IN MM", INK, 3)
    oz = 60 + int(H * s) + 20
    cv.line((20, oz), (1580, oz), FAINT, 0)
    for j, d in enumerate(docs):
        ol = outlines(d)
        fx, sx = 230 + j * 760, 560 + j * 760
        draw_view(cv, ol["front"], fx, oz, s, INK)
        draw_view(cv, ol["side"], sx, oz, s, INK)
        nr = d["neck_ring"]
        cv.line((fx - nr["half_x"] * s, oz - nr["z"] * s), (fx + nr["half_x"] * s, oz - nr["z"] * s), RING, 2)
        cv.line((sx + (nr["centre_y"] - nr["half_y"]) * s, oz - nr["z"] * s),
                (sx + (nr["centre_y"] + nr["half_y"]) * s, oz - nr["z"] * s), RING, 2)
        k = d["keys"]
        cv.text(fx - 120, oz + 14, f"BODY {d['body']['name']}", INK, 3)
        lines = [f"TOP {k['height_top']:.0f}  RING {nr['z']:.0f}", f"SHOULDER {k['shoulder_w']:.0f}  CHEST {k['chest_w']:.0f}",
                 f"WAIST {k['waist_w']:.0f}  HIP {k['hip_w']:.0f}", f"THIGH {k['thigh_w']:.0f}  CALF {k['calf_w']:.0f}",
                 f"UPPER ARM {k['upper_arm_w']:.0f}  FOREARM {k['forearm_w']:.0f}",
                 f"HAND {k['hand_length']:.0f}  FOOT {k['foot_length']:.0f} X {k['foot_width']:.0f}"]
        for i, l in enumerate(lines):
            cv.text(fx - 120, oz + 50 + i * 22, l, DIM)
    return cv.save(out / "drawing_AB.png")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dims", required=True, help="body_dims_measure.py's --out folder (<name>.json)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--names", nargs="+", default=["A", "B"])
    args = ap.parse_args()
    out = Path(args.out)
    docs = []
    for n in args.names:
        meas = json.loads((Path(args.dims) / f"{n}.json").read_text(encoding="utf-8"))
        doc = tomllib.loads((Path(__file__).with_name("body_dims") / f"{n}.toml").read_text(encoding="utf-8"))
        # the side profile's alignment: the measure put the side's mid column at the body's mid-depth
        doc["_mid_y"] = doc["body"]["side_mid_y"]
        print(body_sheet(doc, meas, out))
        docs.append(doc)
    if len(docs) > 1:
        print(ab_sheet(docs, out))


if __name__ == "__main__":
    main()
