"""`probe`: proves headless Blender works here (tools/out/probe/report.json) and builds the stand-in fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common
from . import _review

NAME = "probe"
HELP = "probe headless Blender (report.json, a Workbench and an EEVEE frame) and build the test fixtures"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", type=Path, default=_review.PROBE_OUT, help="report folder (default tools/out/probe)")
    parser.add_argument("--no-fixtures", action="store_true", help="skip building tools/out/fixtures/*.glb")


def record_eevee_crash(report_path: Path, report: dict, crash: str) -> None:
    """Blender died after writing the report: fatal unless it died in the EEVEE render, which the probe marks as
    attempted before it starts; then the crash goes into the report as EEVEE's error and the probe goes on."""
    renders = report.get("renders", {})
    if not (renders.get("workbench", {}).get("ok") and renders.get("eevee", {}).get("attempted")):
        raise common.Failure(crash)
    renders["eevee"]["error"] = f"Blender crashed in the EEVEE render: {crash.splitlines()[0]}"
    renders["eevee"]["output_tail"] = crash
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    out: Path = args.out.resolve()
    report_path = out / "report.json"
    report_path.unlink(missing_ok=True)
    try:
        blender.run_script("probe.py", ["--out", str(out)], timeout=600)
        crash = ""
    except common.Failure as failure:
        crash = str(failure)
    if not report_path.is_file():
        raise common.Failure(crash or f"probe.py wrote no {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if crash:
        record_eevee_crash(report_path, report, crash)
    common.say(f"Blender {report['blender']['version_string']} (Python {report['blender']['python']})")
    numpy = report["numpy"]
    if numpy["imports"]:
        common.ok(f"numpy {numpy['version']}")
    else:
        common.bad(f"numpy does not import: {numpy['error']}", "render_views.py composes the sheet with numpy")
    common.ok(f"render engines: {', '.join(report['render_engines']['settable'])}")
    common.ok(f"glTF exporter: {len(report['gltf_export'])} properties, importer: {len(report['gltf_import'])}")
    for key, result in report["renders"].items():
        if result["ok"]:
            common.ok(f"{key} frame in {result['seconds']} s: {result['path']}")
        else:
            common.warn(f"{key} frame failed (recorded, not fatal): {result['error']}")
    common.say(f"report: {report_path}")
    if not args.no_fixtures:
        for path in _review.make_fixtures():
            common.ok(f"fixture {path}")
    return 0
