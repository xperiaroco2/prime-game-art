"""The look-approval sheet of a committed House package (`house --package-sheet DIR --package N`, art #124,
docs/house.md "The export"): stages the package from the committed files under assets/ (not the raw build) into DIR,
laid out like the game's tree, and shoots it with godot/house/package_sheet.gd in an off-screen window."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import shutil
from pathlib import Path

from .. import common
from . import _frames, _godot, _manifest

SCRIPT = common.ROOT / "godot" / "house" / "package_sheet.gd"
REVIEW_DIR = "_review"  # the sheet's own files in DIR (not part of the package)
WIDTH = 2400  # the engineer's sheet; the script adds a 1280 px copy for agents
KIT_COLS, ROOM_COLS = 3, 4
EYE = 1.6  # the rooms' camera height over the door's floor, m
TIMEOUT = 900
PROJECT = """; A committed House package staged for its look-approval sheet (house --package-sheet); not part of it.
config_version=5

[application]

config/name="prime-game-art house package sheet"
config/features=PackedStringArray("4.7", "Forward Plus")
"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def committed(root: Path) -> dict[str, Path]:
    """sha256 -> the committed file: every set manifest's [[files]] entry already in its export/ folder whose bytes
    hash to the recorded sha256."""
    found: dict[str, Path] = {}
    for path in _manifest.find(root)[0]:
        data, problem = _manifest.load(path)
        for entry in (data or {}).get("files", []) if not problem else []:
            f = path.parent / "export" / entry["name"]
            if f.is_file() and _sha256(f) == entry["sha256"]:
                found[entry["sha256"]] = f
    return found


def find_package(root: Path, n: int) -> tuple[Path, dict]:
    """The committed package.json of package n (beside a set manifest under assets/)."""
    for path in sorted((root / "assets").glob("*/*/package.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("package") == n:
            return path, data
    raise common.Failure(f"no committed package.json of package {n} under assets/*/*/")


def stage(package: dict, files: dict[str, Path], folder: Path) -> list[str]:
    """Copies every file of the package from its committed copy (by sha256) to its game path under folder; returns
    the package paths with no committed copy."""
    missing = []
    for rel, sha in sorted(package["files"].items()):
        src = files.get(sha)
        if src is None:
            missing.append(rel)
            continue
        dst = folder / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    return missing


def families(ids: list[str], patterns: dict[str, list[str]]) -> dict[str, list[str]]:
    """Kit piece ids by family: the first family with a matching pattern, else the last family."""
    names = list(patterns)
    out: dict[str, list[str]] = {name: [] for name in names}
    for pid in sorted(ids):
        fam = next((n for n in names if any(fnmatch.fnmatchcase(pid, p) for p in patterns[n])), names[-1])
        out[fam].append(pid)
    return {name: v for name, v in out.items() if v}


def request(package: dict, kit_families: dict[str, list[str]], kit_set: str = "house_kit") -> dict:
    """The sheet request: the kit's families (a package without rooms) or the package's rooms."""
    name = f"p{package['package']}_{package['name']}"
    if package["rooms"]:
        tiles = [{"title": room, "scene": f"res://levels/house/rooms/{room}.tscn"} for room in package["rooms"]]
        return {"mode": "rooms", "sheet": name, "cols": ROOM_COLS, "width": WIDTH, "eye": EYE, "tiles": tiles}
    prefix = f"assets/environment/{kit_set}/"
    ids = [Path(p).stem for p in package["files"] if p.startswith(prefix) and p.endswith(".glb")]
    tiles = [{"title": f"{fam} ({len(v)})", "pieces": v} for fam, v in families(ids, kit_families).items()]
    return {"mode": "kit", "sheet": name, "cols": KIT_COLS, "width": WIDTH, "dir": f"res://{prefix}",
            "tiles": tiles, "font_size": 64}


def run(folder: Path, n: int, kit_families: dict[str, list[str]], root: Path = common.ROOT) -> int:
    """Stages package n from the committed files into folder and shoots its sheet into folder/<name>.png,
    <name>_1280.png and <name>.json."""
    path, package = find_package(root, n)
    folder.mkdir(parents=True, exist_ok=True)
    missing = stage(package, committed(root), folder)
    if missing:
        raise common.Failure(f"package {n} ({path.as_posix()}): {len(missing)} files have no committed copy with "
                             f"their sha256, e.g. {missing[0]}")
    common.say(f"house package sheet: package {n} ({package['name']}), {len(package['files'])} committed files "
               f"staged into {folder.as_posix()}")
    (folder / "project.godot").write_text(PROJECT, encoding="utf-8", newline="\n")
    (folder / REVIEW_DIR).mkdir(exist_ok=True)
    shutil.copyfile(SCRIPT, folder / REVIEW_DIR / SCRIPT.name)
    req = request(package, kit_families)
    req_path = folder / REVIEW_DIR / "request.json"
    req_path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    code, output = _godot.godot(["--headless", "--path", folder, "--import"], TIMEOUT)
    if code != 0:
        raise common.Failure(f"godot --import of the staged package exited {code}:\n"
                             + "\n".join(output.splitlines()[-20:]))
    report = folder / f"{req['sheet']}.json"
    report.unlink(missing_ok=True)
    w = 1200 if req["mode"] == "rooms" else 1600
    h = 675 if req["mode"] == "rooms" else 1200
    code, output = _godot.godot(["--path", folder, "--audio-driver", "Dummy", "--position", _frames.POSITION,
                                 "--resolution", f"{w}x{h}", "-s", f"res://{REVIEW_DIR}/{SCRIPT.name}", "--",
                                 f"request={req_path.as_posix()}", f"out={folder.as_posix()}"], TIMEOUT)
    if code != 0 or not report.is_file():
        raise common.Failure(f"package_sheet.gd failed (exit {code}):\n" + "\n".join(output.splitlines()[-20:]))
    for line in [x for x in _godot.noteworthy(output) if "ERROR" in x][:10]:
        common.say(f"  godot: {line}")
    for tile in json.loads(report.read_text(encoding="utf-8"))["tiles"]:
        extra = (f"door {tile['door'] or '-'}, {tile['lights']} lights" if req["mode"] == "rooms"
                 else f"{tile['pieces']} pieces")
        common.say(f"  {tile['title']}: {extra}, {tile['draw_calls']} draw calls")
    common.ok(f"house package sheet: {(folder / (req['sheet'] + '.png')).as_posix()} and its 1280 px copy")
    return 0
