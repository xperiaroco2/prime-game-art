"""The recovered aliens under the approved static look (art #393; the look of art #196, char_shots.gd): plain-Python
driver. Takes each character's GLB (one skinned mesh, `<name>_static_skin` and `<name>_body_skin`), extracts its
embedded images, stands in for the sidecar maps lost with D: (2026-11-18, #136), stages the GLBs, runs
godot/alien/look_shots.gd in the runner's off-screen window and encodes the videos with Blender's FFmpeg.

    $PYTHON_BIN tools/blender/alien_look_run.py --glb chameleon=<glb> --glb axolotl=<glb> --out <dir>
        [--shots default|<json file>] [--only NAMES]

The sidecar maps (char_shots.gd's head job) and what stands in for each when only the GLB is left:
- mask (R the skin tint mask, G roughness, B the subsurface and sheen weight): the GLB's own `<name>_mask` image
  (the head material's metallicRoughness texture), extracted;
- body mask: R 1 (all skin) and the head mask's median G and B over its skin texels (the build took the median at
  the neck cut, alien_char_build.py);
- detail (R cavity, G thinness, B flush, A the limbal ring) and the body's: a constant [1, 0, 0, 0] (no crease, thick:
  no transmission, no flush, no painted limbal ring); the shader's white default would read the whole skin as thin;
- accent, gill, body accent and the regions' bases: none (black; every base the skin's), so the build's own paint
  (preset 0, the identity recolour) is exact and the colour presets are not available;
- base skin: the body albedo's median (the body was painted from the head's skin base);
- the alive levers: alien_static_review.PICK through column F (the static_v5 pick without a build's pick.json);
- the studio HDRI: missing, so char_shots.gd's procedural sky stands in.
Writes <out>/<shot>.png, <out>/mp4/<shot>.mp4, looks.json and inputs.json. Long: run it in the background.
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "blender"))
from runner import blender, common  # noqa: E402
from runner.commands import _godot  # noqa: E402

DETAIL = [1.0, 0.0, 0.0, 0.0]
DEFAULT_SHOTS = [
    {"name": "chameleon_idle_front", "char": "chameleon", "kind": "sheet", "clip": "Idle", "yaw": 0},
    {"name": "chameleon_jog_34", "char": "chameleon", "kind": "sheet", "clip": "Jog_Fwd", "yaw": 35},
    {"name": "chameleon_walk_side", "char": "chameleon", "kind": "sheet", "clip": "Walk", "yaw": 90},
    {"name": "chameleon_jog_back", "char": "chameleon", "kind": "sheet", "clip": "Jog_Fwd", "yaw": 180},
    {"name": "chameleon_turn", "char": "chameleon", "kind": "turn", "clip": "Idle"},
    {"name": "axolotl_idle_34", "char": "axolotl", "kind": "sheet", "clip": "Idle", "yaw": 35},
    {"name": "axolotl_jog_34", "char": "axolotl", "kind": "sheet", "clip": "Jog_Fwd", "yaw": 35},
    {"name": "axolotl_turn", "char": "axolotl", "kind": "turn", "clip": "Idle"},
    {"name": "chameleon_jog", "char": "chameleon", "kind": "video", "clip": "Jog_Fwd", "yaw": 35},
    {"name": "chameleon_idle", "char": "chameleon", "kind": "video", "clip": "Idle", "yaw": 35},
    {"name": "chameleon_thigh_diag", "char": "chameleon", "kind": "diag", "clip": "Idle"},
]


def glb_images(path: Path) -> dict[str, bytes]:
    """The GLB's embedded images by name (their bytes as stored)."""
    data = path.read_bytes()
    n = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + n])
    base = 20 + n + 8
    out = {}
    for i, im in enumerate(gltf.get("images", [])):
        bv = gltf["bufferViews"][im["bufferView"]]
        s = base + bv.get("byteOffset", 0)
        out[im.get("name", f"image_{i}")] = data[s:s + bv["byteLength"]]
    return out


def png_pixels(png: bytes) -> tuple[int, int, int, bytes]:
    """An 8-bit RGB or RGBA PNG (not interlaced) as (width, height, channels, raw pixel bytes)."""
    i, idat, w, h, ch = 8, b"", 0, 0, 0
    while i < len(png):
        n, kind = struct.unpack(">I4s", png[i:i + 8])
        body = png[i + 8:i + 8 + n]
        i += 12 + n
        if kind == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
            if depth != 8 or ctype not in (2, 6) or body[12] != 0:
                raise ValueError(f"only 8-bit RGB/RGBA non-interlaced PNGs (depth {depth}, type {ctype})")
            ch = 3 if ctype == 2 else 4
        elif kind == b"IDAT":
            idat += body
    raw = zlib.decompress(idat)
    stride = w * ch
    out = bytearray()
    prev = bytearray(stride)
    p = 0
    for _ in range(h):
        f = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        if f == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif f:
            for x in range(stride):
                a = line[x - ch] if x >= ch else 0
                b = prev[x]
                c = prev[x - ch] if x >= ch else 0
                if f == 1:
                    line[x] = (line[x] + a) & 255
                elif f == 3:
                    line[x] = (line[x] + (a + b) // 2) & 255
                else:
                    pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                    line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += line
        prev = line
    return w, h, ch, bytes(out)


def _median(hist: list[int]) -> float:
    total, run = sum(hist), 0
    for v, n in enumerate(hist):
        run += n
        if run * 2 >= total:
            return v / 255.0
    return 0.0


def body_mask(mask_png: bytes) -> list[float]:
    """The body's mask constant: R 1 (all skin), G and B the head mask's medians over its skin texels (R >= 0.5)."""
    _, _, ch, px = png_pixels(mask_png)
    g, b = [0] * 256, [0] * 256
    for k in range(0, len(px), ch):
        if px[k] >= 128:
            g[px[k + 1]] += 1
            b[px[k + 2]] += 1
    return [1.0, _median(g), _median(b), 1.0]


def median_rgb(png: bytes) -> list[float]:
    """Each channel's median (sRGB, 0-1)."""
    _, _, ch, px = png_pixels(png)
    hists = [[0] * 256 for _ in range(3)]
    for k in range(0, len(px), ch):
        for c in range(3):
            hists[c][px[k + c]] += 1
    return [_median(h) for h in hists]


def alive_params() -> dict:
    import alien_static_review as R  # the static_v5 lever grid (plain Python)
    return R.column("F", dict(R.PICK))


def char_entry(name: str, glb: Path, tex: Path) -> dict:
    """One character's job entry and the inputs it got; writes the GLB's images into tex."""
    images = glb_images(glb)
    tex.mkdir(parents=True, exist_ok=True)
    for k, v in images.items():
        (tex / f"{k}.png").write_bytes(v)
    mask = images[f"{name}_mask"]
    return {"glb": _godot.stage(glb, f"look_{name}"), "mask": str(tex / f"{name}_mask.png"), "detail": DETAIL,
            "body_mask": body_mask(mask), "body_detail": DETAIL, "accent": "", "gill": "", "body_accent": "",
            "bases": {}, "base_skin": median_rgb(images[f"{name}_body_albedo"]), "params": alive_params()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", action="append", required=True, help="name=path, the name the materials carry")
    ap.add_argument("--out", required=True)
    ap.add_argument("--shots", default="default")
    ap.add_argument("--only", default="", help="shot names, comma separated")
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    shots = DEFAULT_SHOTS if a.shots == "default" else json.loads(Path(a.shots).read_text(encoding="utf-8"))
    if a.only:
        shots = [s for s in shots if s["name"] in a.only.split(",")]
    chars = {}
    for spec in a.glb:
        name, path = spec.split("=", 1)
        chars[name] = char_entry(name, Path(path), out / "tex" / name)
    (out / "inputs.json").write_text(json.dumps(chars, indent=1), encoding="utf-8", newline="\n")
    job = {"out": str(out), "hdri": "", "fix": {"shadow_quality": 5}, "chars": chars, "shots": shots}
    (out / "look_job.json").write_text(json.dumps(job, indent=1), encoding="utf-8", newline="\n")
    _godot.import_project()
    code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/look_shots.gd", "--",
                                  str(out / "look_job.json")], (1280, 720), 3000, log=out / "look_godot.log")
    (out / "look_godot.log").write_text(output, encoding="utf-8", newline="\n")
    print(f"godot: exit {code}", *[x for x in output.splitlines() if "LOOK" in x or "ERROR" in x][-30:], sep="\n",
          flush=True)
    if code != 0:
        return 1
    videos = [str(out / "frames" / s["name"]) for s in shots if s["kind"] == "video"]
    if videos:
        res = blender.run_script("encode_clips.py", ["--frames", *videos, "--out", str(out / "mp4"), "--fps", "24",
                                                     "--repeat", "1"], timeout=1200)
        print(*[x for x in (res.stdout or "").splitlines() if x.startswith("ENCODED")], sep="\n", flush=True)
        shutil.rmtree(out / "frames", ignore_errors=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except common.Failure as e:
        print(e, file=sys.stderr)
        sys.exit(1)
