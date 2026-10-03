"""Shared by test_export_*.py and test_godot_*.py: one man and one woman of the final test assembled (--modes none
--blend) and exported once per test run, with the command output; the tests skip when Blender, the glTF-Validator or
the Ultimate Modular packs are missing."""

from __future__ import annotations

import contextlib
import io
import shutil

from runner import cli, common, pins

OUT = common.OUT / "tests" / "export"
IDS = ("m1_rex", "w1_ivy")
RAW = common.raw_dir()


def have(env_name: str, default: str | None) -> bool:
    path = common.tool_path(env_name, default)
    return bool(path and path.is_file())


HAVE_BLENDER = have(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)
HAVE_VALIDATOR = have(pins.GLTF_VALIDATOR_ENV, pins.GLTF_VALIDATOR_DEFAULT)
HAVE_GODOT = have(pins.GODOT_ENV, None)
HAVE_PACKS = all((RAW / "refs" / f"Ultimate_Modular_{p}_Pack").is_dir() for p in ("Men", "Women"))
CAN_EXPORT = HAVE_BLENDER and HAVE_VALIDATOR and HAVE_PACKS
SKIP_EXPORT = (f"needs Blender {pins.BLENDER}, the glTF-Validator {pins.GLTF_VALIDATOR} and the Ultimate Modular packs "
               f"in {RAW.as_posix()}/refs")

_cache: dict[str, tuple[int, str]] = {}


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


def exported() -> tuple[int, str]:
    """Assembles and exports IDS into OUT once per process; returns the export command's exit code and output."""
    if "export" not in _cache:
        shutil.rmtree(OUT, ignore_errors=True)
        code, text = run_cli("assemble", "um_final_test", "--ids", ",".join(IDS), "--modes", "none", "--blend",
                             "--out", str(OUT / "assemble"))
        if code != 0:
            _cache["export"] = (code, text)
        else:
            _cache["export"] = run_cli("export", *(str(OUT / "assemble" / "blend" / f"{i}.blend") for i in IDS),
                                       "--out", str(OUT / "glb"))
    return _cache["export"]


def glb(cid: str):
    return OUT / "glb" / cid / f"{cid}.glb"
