"""Proves headless Blender works here and records what it offers: tools/out/probe/report.json and two test renders.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/probe.py -- --out DIR

The report holds Blender's version, every property of the glTF exporter and importer with its default, the render
engines, whether numpy imports, and the result of rendering one Workbench and one EEVEE frame of a small test scene.
An EEVEE failure (it may need a GPU context that background mode lacks) is recorded, not raised. The report is written
before the EEVEE render too, so even a crash of Blender itself leaves one behind (the runner then records the crash).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import traceback
from pathlib import Path

import bpy

ENGINE_CANDIDATES = ("BLENDER_WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES")


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="probe.py")
    parser.add_argument("--out", required=True)
    return parser.parse_args(argv)


def plain(value: object) -> object:
    """An RNA default as JSON: arrays become lists, sets become sorted lists."""
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    try:
        return [plain(v) for v in value]  # type: ignore[union-attr]
    except TypeError:
        return str(value)


def dynamic_enum(operator_class: type | None, identifier: str) -> tuple[list[str], object] | None:
    """(items, default) of an enum whose items a function computes; RNA lists none without a context, so they come
    from the operator class's property definition."""
    if operator_class is None:
        return None
    definition = None
    for klass in operator_class.__mro__:
        definition = getattr(klass, "__annotations__", {}).get(identifier)
        if definition is not None:
            break
    keywords = getattr(definition, "keywords", None)
    if not keywords or "items" not in keywords:
        return None
    items = keywords["items"]
    try:
        listed = items(None, bpy.context) if callable(items) else items
    except Exception:  # noqa: BLE001 - an items function that needs a real operator instance
        return None
    names = [item[0] for item in listed if item]
    default = keywords.get("default")
    if isinstance(default, int) and 0 <= default < len(names):
        default = names[default]  # dynamic enums give their default as an index
    return names, plain(default)


def operator_properties(operator: object) -> dict[str, dict]:
    """Every property of an operator: its type, default and, for enums, the allowed values."""
    rna = operator.get_rna_type()  # type: ignore[attr-defined]
    operator_class = getattr(bpy.types, rna.identifier, None)
    found: dict[str, dict] = {}
    for prop in rna.properties:
        if prop.identifier == "rna_type":
            continue
        entry: dict[str, object] = {"type": prop.type, "name": prop.name}
        if prop.type == "ENUM":
            entry["items"] = [item.identifier for item in prop.enum_items]
            entry["default"] = plain(prop.default_flag if prop.is_enum_flag else prop.default)
            if not entry["items"]:
                resolved = dynamic_enum(operator_class, prop.identifier)
                entry["dynamic"] = True
                if resolved:
                    entry["items"], entry["default"] = resolved
        elif prop.type in {"BOOLEAN", "INT", "FLOAT"} and getattr(prop, "is_array", False):
            entry["default"] = plain(prop.default_array)
        elif prop.type in {"BOOLEAN", "INT", "FLOAT", "STRING"}:
            entry["default"] = plain(prop.default)
        else:
            entry["default"] = None
        found[prop.identifier] = entry
    return found


def engines() -> dict[str, object]:
    scene = bpy.context.scene
    listed = [item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items]
    settable = []
    original = scene.render.engine
    for name in dict.fromkeys((*ENGINE_CANDIDATES, *listed)):
        try:
            scene.render.engine = name
            settable.append(name)
        except TypeError:
            pass
    scene.render.engine = original
    return {"enum_items": listed, "settable": settable}


def numpy_info() -> dict[str, object]:
    try:
        import numpy

        return {"imports": True, "version": numpy.__version__}
    except Exception as exc:  # noqa: BLE001 - any import failure is the answer
        return {"imports": False, "error": f"{type(exc).__name__}: {exc}"}


def test_scene() -> None:
    """A cube on a plane, a sun and a camera looking at them."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    bpy.ops.mesh.primitive_plane_add(size=4)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.35, location=(0.9, -0.4, 0.35))
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    scene.collection.objects.link(sun)
    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    camera.location = (3.2, -3.6, 2.6)
    camera.rotation_euler = (math.radians(63), 0, math.radians(42))
    scene.collection.objects.link(camera)
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = 320, 240
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"


def render(engine: str, path: Path) -> dict[str, object]:
    scene = bpy.context.scene
    started = time.perf_counter()
    try:
        scene.render.engine = engine
        if engine.startswith("BLENDER_EEVEE") and hasattr(scene, "eevee"):
            scene.eevee.taa_render_samples = 8
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        if not path.is_file():
            raise RuntimeError(f"no image written to {path}")
        return {"ok": True, "engine": engine, "path": str(path), "seconds": round(time.perf_counter() - started, 2)}
    except Exception as exc:  # noqa: BLE001 - the probe records any failure
        return {
            "ok": False,
            "engine": engine,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "seconds": round(time.perf_counter() - started, 2),
        }


def main() -> None:
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "blender": {
            "version": list(bpy.app.version),
            "version_string": bpy.app.version_string,
            "build_hash": bpy.app.build_hash.decode() if isinstance(bpy.app.build_hash, bytes) else bpy.app.build_hash,
            "background": bpy.app.background,
            "python": sys.version.split()[0],
        },
        "numpy": numpy_info(),
        "render_engines": engines(),
        "importers": {
            "gltf": hasattr(bpy.ops.import_scene, "gltf"),
            "fbx": hasattr(bpy.ops.import_scene, "fbx"),
            "obj": hasattr(bpy.ops.wm, "obj_import"),
        },
        "gltf_export": operator_properties(bpy.ops.export_scene.gltf),
        "gltf_import": operator_properties(bpy.ops.import_scene.gltf),
    }
    test_scene()
    renders: dict[str, dict] = {"workbench": render("BLENDER_WORKBENCH", out / "workbench.png")}
    # EEVEE without a GPU context can kill Blender outright (an abort, not a Python error), so the report is written
    # first with EEVEE marked as attempted and rewritten afterwards; the runner records a crash that leaves it so.
    renders["eevee"] = {"ok": False, "engine": "BLENDER_EEVEE", "attempted": True,
                        "error": "Blender exited during the EEVEE render"}
    report["renders"] = renders
    write_report(out, report)
    if not renders["workbench"]["ok"]:
        raise RuntimeError(f"the Workbench render failed: {renders['workbench']['error']}")
    renders["eevee"] = render("BLENDER_EEVEE", out / "eevee.png")
    write_report(out, report)
    print(f"REPORT {out / 'report.json'}")


def write_report(out: Path, report: dict) -> None:
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


main()
