"""The parts catalogue of the Ultimate Modular packs (docs/catalogue.md): every character's parts inventoried, heads
split into offerable items with extraction recipes, and compatibility measured pair by pair with the assembler's
library (tools/blender/um/).

The runner calls it (tools/run.py catalogue); by hand, background only:
  blender -b --factory-startup --python-exit-code 1 --python tools/blender/catalogue.py -- \
      --raw D:/prime-art-raw --data catalogue/ultimate_modular.json [--out DIR --modes sheets,matrices,confirm] [--res 100]

--data: where the catalogue JSON is written (sorted keys, rounded numbers: two runs give identical files). With
--modes, renders go into --out: sheets/ (every item alone, by slot and body type), matrices/ (the pair matrices as
coloured grids), confirm/ (pairs assembled with um/ and rendered front and side, with seam close-ups).
"""

import argparse
import hashlib
import json
import os
import struct
import sys
import time
from pathlib import Path

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalogue_heads as ch  # noqa: E402
import catalogue_parts as cp  # noqa: E402
import catalogue_rules as cr  # noqa: E402
from um import packs as pk  # noqa: E402
from um.util import update  # noqa: E402

SCHEMA = "prime-game-art/catalogue/ultimate-modular/1"
PACKS = {"M": "refs/Ultimate_Modular_Men_Pack", "W": "refs/Ultimate_Modular_Women_Pack"}
SOURCES = {"M": "sources/quaternius_ultimate_modular_men.toml", "W": "sources/quaternius_ultimate_modular_women.toml"}
MODES = ("sheets", "matrices", "confirm")

REVIEW = ("no vertical gap, and the rays fail the allowance by at most 4 rays or 1 % of the rays cast: too close to "
          "call by rays; the designer decides on a render")

RULES = [
    {"id": "bottom_shoes", "seam": "ankle",
     "condition": "After um/fit.py tuck_cull, rays at each ankle in the rest pose: see-through and poke-through no "
                  "higher than the references' (the bottom with its own shoes, the shoes with their own bottom) plus 2. "
                  "overlap_mm = collar top - bottom lower edge (the lower leg): below -30 mm the bottom is too short "
                  "(gap); below 0, or too many see-through rays, extend_edge is tried on the bottom's hem. Tucked when "
                  "most of the shin just under the collar is inside the shoe, else worn over.",
     "verdicts": {"review": REVIEW,
                  "ok_tucked": "tucked in; after tuck_cull no see-through and no poke-through",
                  "ok_over": "worn over the shoe; no see-through and the shoe does not show through",
                  "needs_fix": "a gap of up to 30 mm (or a sliver) that extend_edge on the bottom closes, measured",
                  "gap": "the bottom ends more than 30 mm above the collar (a knee-length bottom over low shoes) or "
                         "the fix does not close it",
                  "poke": "the shoe and the bottom cross: one shows through the other"}},
    {"id": "top_bottom", "seam": "waist",
     "condition": "Rays at the waist, at rest and walking: see-through and poke-through no higher than the "
                  "references' (each part with its own pack partner) plus 2. overlap_mm = bottom upper edge - top lower "
                  "edge: below 0, or too many see-through rays, extend_edge is tried on the top's hem. The outer part "
                  "is the one hit first where both are.",
     "verdicts": {"review": REVIEW,
                  "ok_over": "the top hangs over the bottom", "ok_tucked": "the top goes inside the bottom",
                  "needs_fix": "a gap of up to 30 mm (or a sliver) that extend_edge on the top's hem closes, measured",
                  "gap": "more than 30 mm apart, or the fix does not close it",
                  "poke": "the waistband and the hem cross: one shows through the other"}},
    {"id": "head_top", "seam": "neck",
     "condition": "Rays at the neck, at rest and walking: see-through and poke-through no higher than the "
                  "references' (the head with its own top, the top with its own head) plus 2; too many see-through rays "
                  "send the pair to extend_edge on the head's neck. overlap_mm (top neck ring top - head bottom) is "
                  "recorded but is positive for every pair: the rays decide every neck verdict.",
     "verdicts": {"review": REVIEW,
                  "ok": "the neck seam closes", "needs_fix": "extend_edge on the head's neck closes it, measured",
                  "gap": "more than 30 mm apart, or the fix does not close it",
                  "poke": "the neck and the collar cross: one shows through the other"}},
    {"id": "headwear_hair", "seam": "hat",
     "condition": "The hair stays inside the hat: on the scalp rays (toward the skull centre) no more hair comes out "
                  "in front of the hat, or lies on it, than with the hat's own hair (poke and z-fight rays no higher "
                  "than that reference plus 2). The helmets that are whole heads replace the skull and the hair.",
     "verdicts": {"review": REVIEW,
                  "ok": "the hair stays inside the hat",
                  "needs_fix": "fits after the hat is inflated (scaled off the skull by 1 to 3 %), measured",
                  "poke": "the hair comes out through the hat even with the hat inflated by 3 %"}},
    {"id": "hair_skull", "seam": "scalp",
     "condition": "Hair covers the skull's open top (no hole rays) and the skull surface never comes out through the "
                  "hair or lies on it (no poke or z-fight rays).",
     "verdicts": {"review": REVIEW,
                  "ok": "fits as is", "needs_fix": "fits after inflate 0.006 (the hair scaled off the skull), measured",
                  "gap": "the open top of the skull shows (cap-style hair is missing or does not cover it)",
                  "poke": "the skull cuts through the hair even after the inflate"}},
]


def parse():
    p = argparse.ArgumentParser(prog="catalogue.py")
    p.add_argument("--raw", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--out", default="")
    p.add_argument("--modes", default="")
    p.add_argument("--res", type=int, default=100)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:])


def rounded(v):
    if isinstance(v, float):
        return round(v, 4) + 0.0
    if isinstance(v, dict):
        return {k: rounded(x) for k, x in v.items() if not k.startswith("_")}
    if isinstance(v, (list, tuple)):
        return [rounded(x) for x in v]
    return v


def glb_digest(path):
    """Hashes of a GLB's mesh positions per mesh, its skins' inverse bind matrices and each animation's channels,
    to tell a duplicate from a variant (pure Python on the binary chunk)."""
    data = path.read_bytes()
    jl = struct.unpack("<I", data[12:16])[0]
    js = json.loads(data[20:20 + jl])
    off = 20 + jl
    bl = struct.unpack("<I", data[off:off + 4])[0]
    b = data[off + 8:off + 8 + bl]

    def acc(i):
        a = js["accessors"][i]
        bv = js["bufferViews"][a["bufferView"]]
        size = {5126: 4, 5123: 2, 5125: 4, 5121: 1, 5122: 2}[a["componentType"]] * \
            {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[a["type"]]
        st = bv.get("byteStride", size)
        o = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        return b"".join(b[o + k * st:o + k * st + size] for k in range(a["count"]))

    def h(x):
        return hashlib.sha256(x).hexdigest()[:16]

    anims = {}
    for an in js.get("animations", []):
        hh = hashlib.sha256()
        for c in an["channels"]:
            s = an["samplers"][c["sampler"]]
            hh.update((js["nodes"][c["target"]["node"]]["name"] + c["target"]["path"]).encode())
            hh.update(acc(s["input"]) + acc(s["output"]))
        anims[an["name"].split("|")[-1]] = hh.hexdigest()[:16]
    meshes = {m["name"]: h(b"".join(acc(p["attributes"]["POSITION"]) for p in m["primitives"])) for m in js["meshes"]}
    skins = sorted({h(acc(s["inverseBindMatrices"])) for s in js.get("skins", [])})
    return {"sha256": hashlib.sha256(data).hexdigest(), "meshes": meshes, "skins": skins,
            "animations": h(json.dumps(anims, sort_keys=True).encode()), "animation_names": sorted(anims)}


def files_section(lib, raw):
    out, digests = [], {}
    for fe in sorted(lib.files, key=lambda e: (e["body_type"], e["file"])):
        d = glb_digest(Path(raw) / PACKS[fe["body_type"]] / fe["file"])
        digests[(fe["body_type"], fe["file"])] = d
        out.append({"body_type": fe["body_type"], "file": fe["file"], "character": fe["character"], "sha256": d["sha256"],
                    "parts": {k: v for k, v in sorted(fe["parts"].items())}, "props": fe["props"],
                    "animations": len(d["animation_names"]), "animation_set": d["animations"], "skin": d["skins"]})
    a = digests[("W", "Animated Woman.glb")]
    b = digests[("W", "Animated Woman-nIItLV9nxS.glb")]
    shared = sorted(set(a["meshes"].values()) & set(b["meshes"].values()))
    anim_sets = {g: sorted({d["animations"] for (gg, _), d in digests.items() if gg == g}) for g in cp.GENDERS}
    skins = {g: sorted({s for (gg, _), d in digests.items() if gg == g for s in d["skins"]}) for g in cp.GENDERS}
    animated_woman = {
        "files": ["Animated Woman.glb", "Animated Woman-nIItLV9nxS.glb"],
        "sha256": [a["sha256"], b["sha256"]],
        "objects": [sorted(a["meshes"]), sorted(b["meshes"])],
        "meshes_with_equal_positions": len(shared),
        "animations_equal": a["animations"] == b["animations"],
        "skin_equal": a["skins"] == b["skins"],
        "verdict": "different characters" if not shared else "variants",
        "explanation": "Animated Woman.glb is the Casual character (Casual_Head, _Body, _Legs, _Feet) and "
                       "Animated Woman-nIItLV9nxS.glb the Formal one (Formad_Head, Formal_Body, _Legs, _Feet): no mesh "
                       "is shared; they share the skeleton (equal inverse bind matrices) and the 24 animations, as "
                       "every women's file does. Both are catalogued.",
    }
    counts = {g: sum(1 for e in out if e["body_type"] == g) for g in cp.GENDERS}
    chars = {"M": counts["M"], "W": counts["W"], "total": counts["M"] + counts["W"], "animated_woman": animated_woman,
             "animation_sets_per_body_type": {g: len(v) for g, v in anim_sets.items()},
             "skeletons_per_body_type": {g: len(v) for g, v in skins.items()}}
    return out, chars


def make_copy_factory(coll):
    return lambda obj, name: cp.copy_part(obj, name, coll)


def matrices(lib, inv, items, coll, log):
    mk, rm = make_copy_factory(coll), cp.remove
    out = {"bottom_shoes": {}, "top_bottom": {}, "head_top": {}, "hair_skull": {}, "headwear_hair": {}}
    for g in cp.GENDERS:
        t0 = time.time()
        out["bottom_shoes"][g] = cr.ankle_matrix(lib, g, inv, mk, rm)
        log("bottom x shoes %s: %.1f s" % (g, time.time() - t0))
        t0 = time.time()
        out["top_bottom"][g] = cr.waist_matrix(lib, g, inv, mk, rm)
        log("top x bottom %s: %.1f s" % (g, time.time() - t0))
    # skulls and hair of unique geometry (an item with same_geometry_as is measured through its twin)
    unique = {i: e.get("same_geometry_as", i) for i, e in items.items() if e["kind"] == "skull"}
    skulls = sorted(i for i, e in items.items() if e["kind"] == "skull" and "same_geometry_as" not in e)
    hairs = sorted(i for i, e in items.items() if e["kind"] == "hair" and "same_geometry_as" not in e)
    helmets = sorted(i for i, e in items.items() if e.get("replaces") == "skull")
    hats = sorted(i for i, e in items.items() if e["kind"] == "headwear" and i not in helmets
                  and "same_geometry_as" not in e)
    # the neck rows: every unique skull and the helmets that are whole heads; their owners and each head's row
    necks = sorted(skulls + helmets)
    head_of = {}
    for i, e in items.items():
        if e["kind"] == "skull" or i in helmets:
            hd = e["head"].split("_", 2)
            head_of[(hd[1].upper(), hd[2])] = e.get("same_geometry_as", i)
    owners = {}
    for key, row in sorted(head_of.items()):
        owners.setdefault(row, []).append(key)
    objs = {}
    for g in cp.GENDERS:
        for iid in skulls + hairs + helmets + hats:
            e = items[iid]
            objs[(iid, g)] = ch.item_object(lib.head(e["head"], g), e["_faces"], "%s@%s" % (iid, g), coll)
    update()
    for g in cp.GENDERS:
        t0 = time.time()
        out["head_top"][g] = cr.neck_matrix(lib, g, inv, necks, {s: objs[(s, g)] for s in necks}, items, owners,
                                            head_of, mk, rm)
        log("head x top %s: %.1f s" % (g, time.time() - t0))
    t0 = time.time()
    by_g = {g: [s for s in skulls if s.split("_")[1] == g.lower()] for g in cp.GENDERS}
    out["hair_skull"] = cr.hair_matrix(lib.rigs, hairs, by_g, objs, items, unique, mk, rm)
    log("hair x skull: %.1f s" % (time.time() - t0))
    t0 = time.time()
    hair_unique = {i: e.get("same_geometry_as", i) for i, e in items.items() if e["kind"] == "hair"}
    out["headwear_hair"] = cr.hat_matrix(lib.rigs, hats, hairs, objs, items, hair_unique, mk, rm)
    log("headwear x hair: %.1f s" % (time.time() - t0))
    for o in objs.values():
        cp.remove(o)
    return out


def summary(mats):
    out = {}
    for name, per in mats.items():
        out[name] = {}
        for g, m in per.items():
            counts = {}
            for c in m["cells"]:
                counts[c["verdict"]] = counts.get(c["verdict"], 0) + 1
            entry = {"pairs": len(m["cells"]), "verdicts": dict(sorted(counts.items()))}
            if name in ("bottom_shoes", "top_bottom", "head_top"):
                # whole millimetres, as the final test reported them (bottom_m_king x shoes_m_hoodie is 5.1 mm)
                entry["gap_over_5mm"] = sum(1 for c in m["cells"] if round(c["overlap_mm"]) < -cr.GAP_MM)
                entry["gap_over_5mm_exact"] = sum(1 for c in m["cells"] if c["overlap_mm"] < -cr.GAP_MM)
            out[name][g] = entry
    return out


def main():
    args = parse()
    t_start = time.time()

    def log(msg):
        print("CATALOGUE %6.1fs %s" % (time.time() - t_start, msg), flush=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    coll = bpy.data.collections.new("catalogue")
    bpy.context.scene.collection.children.link(coll)
    packs = pk.Packs({g: Path(args.raw) / PACKS[g] for g in cp.GENDERS})
    lib = cp.Library(packs, coll)
    lib.load_all()
    log("loaded %d files" % len(lib.files))
    files, chars = files_section(lib, args.raw)
    inv = cp.inventory(lib)
    heads, items = ch.analyse(lib, lib.files)
    log("heads analysed: %d heads, %d items" % (len(heads), len(items)))
    mats = matrices(lib, inv, items, coll, log)
    data = {
        "schema": SCHEMA,
        "generated_by": "tools/run.py catalogue (tools/blender/catalogue.py)",
        "sources": {g: {"pack": PACKS[g], "record": SOURCES[g], "skeleton": cp.SKELETON[g]} for g in cp.GENDERS},
        "conventions": {
            "space": "world metres in the rest pose of the body type's skeleton file; +Z up, the face toward -Y, +X the "
                     "character's left; every part rebound onto that rest (um/rebind.py), heads onto both rigs",
            "numbers": "metres to 4 decimals (_m), millimetres to 1 decimal (_mm)",
            "ids": "<slot>_<m|w>_<character> for pack parts; <kind>_<m|w>_<character>[_<descriptor>] for head items "
                   "(m or w is the source pack, not a restriction: heads, hair and face items cross body types)",
        },
        "thresholds": {"ray_slack": cr.RAY_SLACK, "gap_mm": cr.GAP_MM, "fixable_mm": cr.FIXABLE_MM,
                       "poke_behind_m": cr.BEHIND, "review_rays": cr.REVIEW_RAYS, "review_share": cr.REVIEW_SHARE, "hair_inflate": cr.HAIR_INFLATE, "hat_inflate": list(cr.HAT_INFLATE), "zfight_m": cr.ZFIGHT,
                       "states": [s["name"] + (" (%s f%d)" % (s["pose"]["action"], s["pose"]["frame"]) if "pose" in s else "")
                                  for s in cr.STATES]},
        "characters": chars,
        "files": files,
        "parts": inv,
        "heads": {hid: ch.head_record(hid, heads[hid]) for hid in sorted(heads)},
        "items": items,
        "proposed_zones": sorted(ch.PROPOSED_ZONES),
        "rules": RULES,
        "matrices": mats,
        "summary": summary(mats),
    }
    data = rounded(data)
    os.makedirs(os.path.dirname(os.path.abspath(args.data)), exist_ok=True)
    with open(args.data, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
        fh.write("\n")
    log("wrote %s" % args.data)
    modes = [m for m in args.modes.split(",") if m]
    if modes:
        import catalogue_render as crd
        crd.run(lib, data, items, heads, coll, args, modes, log)
    log("done")


if __name__ == "__main__":
    main()
