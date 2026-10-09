"""Builds the House dressing library (props/library.toml, docs/props.md) as one GLB per prop (art #87). The runner
calls it (tools/run.py props --build); by hand, background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/prop_build.py -- \
      --library props/library.toml --kit kits/house.json --out D:/prime-art-raw/props/library/v1 \
      --ambientcg D:/prime-art-raw/env/ambientcg --env D:/prime-art-raw/env [--batch 1] [--only id,...]

Per prop: <out>/<id>.glb; for the run: <out>/textures/ (the kit's detail maps) and <out>/build.json (merged with the
props built before, so batches accumulate). A prop that fails is recorded with its error and the run goes on; the
runner turns errors into problems.
"""

import json
import sys
import tomllib
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prop_geom  # noqa: E402
import prop_lib  # noqa: E402

DECIMATE_SHARE = 0.85  # a decimated source keeps this share of its class's maximum (room for the extras)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = {"only": "", "batch": "0"}
    for i in range(0, len(argv), 2):
        out[argv[i].lstrip("-")] = argv[i + 1]
    return out


def main():
    import bmesh
    import bpy
    import numpy as np

    a = args()
    lib = tomllib.loads(Path(a["library"]).read_text(encoding="utf-8"))
    kit = json.loads(Path(a["kit"]).read_text(encoding="utf-8"))
    spec = prop_geom.lib_spec(lib, kit)
    out = Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    only = {s for s in a["only"].split(",") if s}
    batch = int(a["batch"])
    props = [p for p in lib["prop"] if (not batch or p["batch"] == batch) and (not only or p["id"] in only)]
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    mats, textures = prop_lib.materials(bpy, np, spec, Path(a["ambientcg"]), out)
    path = out / "build.json"
    report = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"props": {}}
    report["textures"] = textures
    for p in props:
        rec = {"route": p["route"], "class": p["class"], "batch": p["batch"]}
        try:
            if p["route"] == "pack":
                cap = None
                if p.get("decimate"):
                    cap = int(lib["budgets"][p["class"]][1] * DECIMATE_SHARE)
                parts, src = prop_lib.import_pack(bpy, np, p, Path(a["env"]), cap)
                pc = prop_geom.pack_piece(p, parts, spec)
                rec["src_triangles"] = src
            else:
                pc = prop_geom.build_proc(p)
            prop_geom.finish(pc, p, spec)
            d = prop_geom.describe(pc, spec)
            rec.update(prop_lib.export_prop(bpy, bmesh, d, spec, mats, out / f"{p['id']}.glb"))
            rec.update({"triangles": d["triangles"], "size_m": d["size_m"], "size_error_m": prop_geom.size_error(d, p),
                        "roles": d["roles"], "light_anchor": d["light_anchor"],
                        "meshes": [m["name"] for m in d["meshes"]]})
            print(f"PROP built {p['id']}: {d['triangles']} triangles, {len(d['colliders'])} colliders")
        except Exception as e:  # noqa: BLE001 - one prop's failure is recorded, the run goes on
            traceback.print_exc()
            rec["error"] = f"{type(e).__name__}: {e}"
            print(f"PROP failed {p['id']}: {rec['error']}")
        report["props"][p["id"]] = rec
    path.write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
