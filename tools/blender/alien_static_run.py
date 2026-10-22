"""The alien pilot's static premium heads (art #196): the driver (plain Python, outside Blender). Per head it builds the
static head in headless Blender (alien_static_head.py: Meshy's own sculpt decimated, the albedo, normal and tint mask
maps, the base-choice sheet), checks both GLBs with glTF-Validator and shoots the review sheets under the showroom's
look in an off-screen Godot window (godot/alien/static_shots.gd through the runner's _godot.window(), the skin's
ShaderMaterial from godot/alien/alien_static.gd). godot-check runs separately (`tools/run.sh godot-check --textured
<glb>`). Inputs are read from the raw folder, never written.

    $PYTHON_BIN tools/blender/alien_static_run.py [--heads chameleon,axolotl] [--out DIR] [--no-build] [--no-shots]
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import blender, common  # noqa: E402
from runner.commands import _export, _godot  # noqa: E402

RAW = common.raw_dir()
MESHY = RAW / "2026-10-22-alien-pilot-3d"
DESIGN = RAW / "research" / "2026-10-22-roster" / "design"
STEP2A = DESIGN / "pilot3d" / "step2a"
ROSTER = {"chameleon": DESIGN / "final" / "m01-chameleon.jpg", "axolotl": DESIGN / "final" / "w01-axolotl.jpg"}
OUT = DESIGN / "pilot3d" / "static_v3"  # #288 wrote static/, step 1 static_v2/, both kept as they were
# static_v3: the builds per head: (name, extra arguments); the chameleon's heavier-lid alternative keeps more of
# the budget on the lid rims (the dense original's lids)
BUILDS = {"axolotl": [("axolotl", [])],
          "chameleon": [("chameleon", []), ("chameleon_heavylid", ["--rims", "on"])]}
HDRI = RAW / "env" / "polyhaven" / "studio_small_09" / "studio_small_09_2k.hdr"  # CC0, sources/polyhaven_hdris_2k.toml


def fix_tangents(glb: Path) -> int:
    """static_v2: Blender exports a zero TANGENT where a triangle's UVs have no area (glTF-Validator: non-unit
    TANGENT; a glTF viewer then shades the vertex black). Each zero tangent becomes a unit vector perpendicular to its
    vertex normal (w = 1); returns how many were fixed. The GLB is rewritten in place (the chunks keep their sizes)."""
    data = bytearray(glb.read_bytes())
    jlen = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + jlen])
    base = 20 + jlen + 8  # the BIN chunk's data
    fixed = 0

    def where(i: int) -> tuple[int, int]:
        acc = doc["accessors"][i]
        view = doc["bufferViews"][acc["bufferView"]]
        return base + view.get("byteOffset", 0) + acc.get("byteOffset", 0), acc["count"]

    for mesh in doc["meshes"]:
        for prim in mesh["primitives"]:
            att = prim["attributes"]
            if "TANGENT" not in att or "NORMAL" not in att:
                continue
            t0, n = where(att["TANGENT"])
            n0, _ = where(att["NORMAL"])
            for k in range(n):
                tx, ty, tz, _w = struct.unpack_from("<4f", data, t0 + 16 * k)
                if tx * tx + ty * ty + tz * tz > 0.5:
                    continue
                nx, ny, nz = struct.unpack_from("<3f", data, n0 + 12 * k)
                ax = (0.0, 1.0, 0.0) if abs(ny) < 0.9 else (1.0, 0.0, 0.0)
                cx, cy, cz = ny * ax[2] - nz * ax[1], nz * ax[0] - nx * ax[2], nx * ax[1] - ny * ax[0]
                ln = math.sqrt(cx * cx + cy * cy + cz * cz) or 1.0
                struct.pack_into("<4f", data, t0 + 16 * k, cx / ln, cy / ln, cz / ln, 1.0)
                fixed += 1
    if fixed:
        glb.write_bytes(bytes(data))
    return fixed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heads", default="chameleon,axolotl")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--alive", type=float, default=1.0, help="the baked alive layers' strength")
    args = ap.parse_args()
    summary = {}
    failed = False
    ap_alive = args.alive
    for head, name, extra in [(h, n, e) for h in args.heads.split(",") for n, e in BUILDS[h]]:
        out = args.out / name
        out.mkdir(parents=True, exist_ok=True)
        if not args.no_build:
            result = blender.run_script("alien_static_head.py", [
                "--head", head, "--src", str(MESHY / head / "multi_image_to_3d-model.glb"),
                "--dense", str(MESHY / head / "multi_image_to_3d-pre_remeshed_model.glb"),
                "--ref", str(STEP2A / head / "v2" / "build.json"), "--v2", str(STEP2A / head / "v2" / f"{head}.glb"),
                "--view2d", str(MESHY / "views" / head), "--roster", str(ROSTER[head]), "--out", str(out), "--name", name, "--alive", str(ap_alive),
                *extra],
                timeout=2400)
            lines = [x for x in (result.stdout or "").splitlines() if x.startswith("STATIC ")]
            (out / "build.log").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            print(f"built {name}", *lines[-2:], sep="\n", flush=True)
        for glb in (out / f"{name}_static.glb", out / f"{name}_static_lod1.glb"):
            print(f"tangents fixed in {glb.name}: {fix_tangents(glb)}", flush=True)
            report = _export.validate(glb, out / f"{glb.stem}.validator.json")
            ok, text = _export.verdict(report)
            summary[glb.name] = text
            failed = failed or not ok
            print(f"validator {glb.name}: {text}", flush=True)
        if not args.no_shots:
            build = json.loads((out / "build.json").read_text(encoding="utf-8"))
            base = "%.4f,%.4f,%.4f" % tuple(build["base_skin_srgb"])
            res = _godot.stage(out / f"{name}_static.glb", f"static_{name}")
            _godot.import_project()
            shots = out / "godot"
            shots.mkdir(exist_ok=True)
            code, _ = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/static_shots.gd", "--", res,
                                     str(shots), str(out / f"{name}_mask.png"), base, str(HDRI),
                                     str(out / "blender_front.png"), str(MESHY / "views" / head / "front.png")],
                                    (640, 800), 170, log=out / "godot_shots.log")
            print(f"godot shots {head}: exit {code} {shots}", flush=True)
            summary[f"{name}_godot"] = code
            failed = failed or code != 0
    (args.out / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
