"""`meshy`: the Meshy API client: estimate, run, balance and status of approved batches, and the animation library's
listing (docs/meshy.md)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from .. import blender, common
from . import _meshy_api as api
from . import _meshy_batch as batches
from . import _meshy_inputs as inputs
from . import _meshy_run as runs

NAME = "meshy"
HELP = "Meshy batches: estimate, run (approved only), balance, status; the animation library's listing"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="action", metavar="<action>", required=True)
    p = sub.add_parser("estimate", help="the credits a batch would spend, per item and in total (no network)")
    p.add_argument("batch", help="batches/<id>.toml or a batch id")
    p = sub.add_parser("run", help="run an approved batch within its credit cap; resumes and skips finished items")
    p.add_argument("batch", help="batches/<id>.toml or a batch id")
    p.add_argument("items", nargs="*", help="only these item ids (default: every item)")
    p.add_argument("--retry-failed", action="store_true", help="submit failed items again (spends credits again)")
    sub.add_parser("balance", help="the Meshy credit balance (needs MESHY_API_KEY; spends nothing)")
    p = sub.add_parser("status", help="each item's state from the raw folder (no network)")
    p.add_argument("batch", help="batches/<id>.toml or a batch id")
    p = sub.add_parser("library", help="save the animation library's listing to the raw folder (needs MESHY_API_KEY; "
                                       "spends nothing)")
    p.add_argument("--search", default="", help="only actions matching this text")
    p.add_argument("--category", default="", help="only this category, e.g. WalkAndRun")
    p.add_argument("--out", type=Path, help="the JSON file (default <raw>/meshy/animation-library-<date>.json)")
    p = sub.add_parser("rig-input", help="a saved character (assemble --blend) as a static textured GLB facing +Z, "
                                         "the input of a rig item (no network)")
    p.add_argument("blend", type=Path, nargs="+", help="saved character files, blend/<id>.blend")
    p.add_argument("--out", type=Path, required=True, help="output folder, e.g. <raw>/<batch id>/inputs")
    p = sub.add_parser("retexture-input", help="one mesh of a saved character as a static rest-pose GLB with only its "
                                               "texture UV, the model of a retexture item (no network)")
    p.add_argument("blend", type=Path, help="the character's .blend (e.g. the alien kit's alien_character.blend)")
    p.add_argument("--out", type=Path, required=True, help="output folder")
    p.add_argument("--object", default="Body", help="the mesh object (default Body)")
    p.add_argument("--uv", default="UVMap", help="the UV map to keep as TEXCOORD_0 (default UVMap)")
    p.add_argument("--name", default="alien_body", help="the file stem (default alien_body)")


def run(args: argparse.Namespace) -> int:
    key = None
    try:
        if args.action == "estimate":
            return estimate(batches.load(args.batch))
        if args.action == "status":
            return status(batches.load(args.batch))
        if args.action == "balance":
            key = api.api_key()
            common.say(f"Meshy balance: {api.MeshyClient(key).balance()} credits")
            return 0
        if args.action == "rig-input":
            return rig_input(args.blend, args.out)
        if args.action == "retexture-input":
            return retexture_input(args.blend, args.out, args.object, args.uv, args.name)
        if args.action == "library":
            key = api.api_key()
            return library(api.MeshyClient(key), args.search, args.category, args.out)
        batch = batches.load(args.batch)
        problems = batches.approval_problems(batch)
        if problems:
            raise common.Failure(f"batch {batch.id} may not run:\n  " + "\n  ".join(problems))
        key = api.api_key()
        return runs.Runner(batch, api.MeshyClient(key), retry_failed=args.retry_failed, only=args.items).run()
    except common.Failure as exc:
        raise common.Failure(api.redact(exc, key)) from None
    except Exception as exc:  # anything unexpected still leaves without the key or its traceback
        raise common.Failure(f"{type(exc).__name__}: {api.redact(exc, key)}") from None


def estimate(batch: batches.Batch) -> int:
    common.say(f"batch {batch.id}: {len(batch.items)} items")
    common.say(f"  {'item':18} {'kind':17} {'model':16} {'stages':32} credits")
    problems: list[str] = []
    for item in batch.items:
        stages = " + ".join(f"{s.name} {s.credits}" for s in item.stages)
        common.say(f"  {item.id:18} {item.kind:17} {item.model or '-':16} {stages:32} {item.credits}")
        if item.images > 1:
            common.say(f"      makes {item.images} images (multi-view, estimated at {item.images} times the per-image "
                       f"price, an upper bound); 'pick' takes 0 to {item.images - 1}")
        for n, inp in enumerate(item.inputs):
            line, trouble = input_line(inp)
            common.say(f"      input {n}: {line}")
            problems += [f"{item.id}: {t}" for t in trouble]
        if item.kind == "retexture":
            views = len(item.inputs) - 1
            style = (f"{views} view input(s) as multiview_image_urls" if item.multiview else
                     "input 1 as image_style_url" if views else f"the prompt as text_style_prompt ({item.prompt!r})")
            p = item.stages[0].params
            common.say(f"      style: {style}; model_url: input 0; enable_original_uv {p.get('enable_original_uv')}, "
                       f"enable_pbr {p.get('enable_pbr')}, texture_resolution {p.get('texture_resolution', '2k')}")
    common.say(f"  total {batch.credits} credits; approved cap {batch.credit_cap}")
    approval = batches.approval_problems(batch)
    common.say("  approval: " + ("complete, within the cap" if not approval else "; ".join(approval)))
    if any(not inp.from_item for item in batch.items for inp in item.inputs):
        common.say("  input files: " + ("every one is ready to send" if not problems else f"{len(problems)} not ready "
                                        "(`meshy run` refuses the batch until they are):"))
        for problem in problems:
            common.say(f"    {problem}")
    return 0


def input_line(inp: inputs.Input) -> tuple[str, list[str]]:
    """One input for the estimate: a `from`, or a file with its current size and sha256 (to pin in the batch)."""
    if inp.from_item:
        return inp.describe(), []
    trouble = inputs.file_problems(inp)
    if trouble:
        return f"{inp.file} ({inp.provenance}): NOT READY", trouble
    path = inputs.resolve(inp.file)
    pin = "pinned" if inp.sha256 else "not pinned"
    return f"{inp.file} ({inp.provenance}): {path.stat().st_size} bytes, sha256 {inputs.sha256(path)} ({pin})", []


def status(batch: batches.Batch) -> int:
    folder = runs.batch_dir(batch)
    common.say(f"batch {batch.id} in {folder}")
    total = 0
    for item in batch.items:
        common.say("  " + runs.item_status(batch, item))
        total += runs.spent(runs.read_state(batch, item))
    common.say(f"  {total} credits spent of the approved cap {batch.credit_cap}")
    return 0


def actions_of(answer: object) -> list[dict]:
    """The action records of a library answer: a list of objects, or the first such list inside an object."""
    if isinstance(answer, list):
        return [a for a in answer if isinstance(a, dict)]
    if isinstance(answer, dict):
        for value in answer.values():
            if isinstance(value, list) and all(isinstance(a, dict) for a in value):
                return value
    raise common.Failure("the animation library's answer holds no list of actions")


def library(client: api.MeshyClient, search: str, category: str, out: Path | None) -> int:
    """Saves the library's listing as Meshy sent it (with the time and the query) and prints a summary."""
    answer = client.library(search, category)
    actions = actions_of(answer)
    now = dt.datetime.now(dt.UTC)
    out = out or common.raw_dir() / "meshy" / f"animation-library-{now:%Y-%m-%d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    record = {"fetched_at": now.isoformat(timespec="seconds"), "endpoint": api.LIBRARY_PATH,
              "search": search, "category": category, "count": len(actions), "answer": answer}
    out.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    cats: dict[str, int] = {}
    for a in actions:
        cats[str(a.get("category", "?"))] = cats.get(str(a.get("category", "?")), 0) + 1
    common.say(f"animation library: {len(actions)} actions ({', '.join(f'{k} {v}' for k, v in sorted(cats.items()))})")
    common.say(f"saved to {out}")
    return 0


def rig_input(blends: list[Path], out: Path) -> int:
    """Runs tools/blender/meshy_rig_input.py on each saved character: <out>/<id>.glb, <id>_texture.png, <id>.json."""
    out = out.resolve()
    for path in blends:
        if not path.is_file():
            raise common.Failure(f"no saved character {path}")
        blender.run_script("meshy_rig_input.py", ["--blend", str(path.resolve()), "--out", str(out)], timeout=600)
        info = json.loads((out / f"{path.stem}.json").read_text(encoding="utf-8"))
        inside = inputs.glb_contents(Path(info["glb"]))
        if len(inside["nodes"]) != 1 or len(inside["meshes"]) != 1:
            rejected = Path(info["glb"]).with_suffix(".glb.rejected")  # renamed so that nobody pins it by mistake
            Path(info["glb"]).replace(rejected)
            raise common.Failure(f"{rejected} holds nodes {inside['nodes']} and meshes {inside['meshes']}: a rig "
                                 "input is one mesh and nothing else")
        common.ok(f"{path.stem}: {info['glb']} ({info['glb_bytes']} bytes, {info['triangles']} triangles, "
                  f"{info['height_m']} m, palette {info['palette_px']} px of {len(info['materials'])} colours)")
        common.say(f"    sha256 {inputs.sha256(Path(info['glb']))} (glb), {inputs.sha256(Path(info['texture']))} "
                   "(texture): pin them in the batch")
    return 0


# What a retexture input may hold (art #196 M3b): the mesh, its normals and the one texture UV, nothing else.
RETEXTURE_ATTRIBUTES = {"POSITION", "NORMAL", "TEXCOORD_0"}


def retexture_problems(path: Path) -> list[str]:
    """Why a GLB is not a clean retexture input: one node with one mesh, only POSITION, NORMAL and TEXCOORD_0, no
    skin, animation, morph target, image or texture, and within the client's model size."""
    doc = inputs.glb_json(path)
    problems = []
    if len(doc.get("nodes", [])) != 1 or len(doc.get("meshes", [])) != 1:
        problems.append(f"{len(doc.get('nodes', []))} nodes and {len(doc.get('meshes', []))} meshes, not one of each")
    for key in ("skins", "animations", "images", "textures"):
        if doc.get(key):
            problems.append(f"it has {key}")
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            extra = set(prim.get("attributes", {})) - RETEXTURE_ATTRIBUTES
            if extra or "TEXCOORD_0" not in prim.get("attributes", {}):
                problems.append(f"attributes {sorted(prim.get('attributes', {}))}, want {sorted(RETEXTURE_ATTRIBUTES)}")
            if prim.get("targets"):
                problems.append("it has morph targets")
    if path.stat().st_size > inputs.MODEL_MAX_BYTES:
        problems.append(f"{path.stat().st_size} bytes, over the client's {inputs.MODEL_MAX_BYTES}")
    return problems


def retexture_input(blend: Path, out: Path, obj: str, uv: str, name: str) -> int:
    """Runs tools/blender/meshy_retexture_input.py: <out>/<name>.glb and <name>.json; checks the GLB's contents."""
    if not blend.is_file():
        raise common.Failure(f"no file {blend}")
    out = out.resolve()
    blender.run_script("meshy_retexture_input.py", ["--blend", str(blend.resolve()), "--out", str(out), "--object", obj,
                                                    "--uv", uv, "--name", name], timeout=600)
    info = json.loads((out / f"{name}.json").read_text(encoding="utf-8"))
    glb = Path(info["glb"])
    problems = retexture_problems(glb)
    if problems:
        rejected = glb.with_suffix(".glb.rejected")  # renamed so that nobody pins it by mistake
        glb.replace(rejected)
        raise common.Failure(f"{rejected} is no clean retexture input: " + "; ".join(problems))
    check = info["uv_check"]
    common.ok(f"{name}: {glb} ({info['glb_bytes']} bytes, {info['triangles']} triangles, {info['height_m']} m); "
              f"UV {uv}: {check['islands']} islands, the same in the GLB")
    common.say(f"    sha256 {inputs.sha256(glb)}: pin it in the batch")
    return 0
