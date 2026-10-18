"""`ragdoll`: a character's ragdoll data (art #115; docs/contract.md, "Ragdoll"; docs/godot.md, "The ragdoll"). Measures
the GLB in plain Python (tools/runner/commands/_ragdoll.py) and writes `<stem>.ragdoll.json`; `--asset` puts it in the
character's asset folder (export/, package.json, HANDOFF.md's ragdoll section); `--fall` builds the PhysicalBone3D
nodes from it in Godot 4.7.2 on Jolt Physics (godot/ragdoll/, headless) and asserts the fall; `--shots DIR` shoots
the fall and the shapes in an off-screen window."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .. import common
from . import _godot, _ragdoll

NAME = "ragdoll"
HELP = "a character's ragdoll data from its GLB; --asset into its package; --fall the Godot proof; --shots its sheets"

PROJECT = common.ROOT / "godot" / "ragdoll"
SCRIPT = "res://fall.gd"
TIMEOUT = 300
OUT = common.OUT / "ragdoll"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("glb", type=Path, help="the character GLB (the Ultimate Modular rig)")
    parser.add_argument("--out", type=Path, help="work folder (default tools/out/ragdoll/<stem>/)")
    parser.add_argument("--asset", type=Path, help="write the data into this asset folder (export/, package.json, HANDOFF.md)")
    parser.add_argument("--fall", action="store_true", help="the headless Godot fall check")
    parser.add_argument("--shots", type=Path, help="shoot the fall and the shapes off-screen; copy the sheets here")


def handoff_section(data: dict, file_name: str) -> str:
    """HANDOFF.md's ragdoll section: what the file is and how the game builds the bones."""
    bones = data["bones"]
    rows = "\n".join(
        f"| `{b['bone']}` | {b['profile']} | {b['parent'] or '-'} | {b['shape']} | {b['mass_kg']:.2f} | "
        f"{(b['joint'] or {}).get('type', 'root')} |" for b in bones)
    c = data["collision"]
    return f"""## Ragdoll (art #115)

The knockdown is a ragdoll (prime-game PR #754, KE7); the knockdown, downed and get-up clips are gone. `export/{file_name}`
holds the ragdoll data: {len(bones)} bodies, each on one bone of this GLB's skeleton, with its shape and offset in the
bone's rest frame, its mass ({data['total_mass_kg']:.0f} kg in all) and its joint to its physical parent (type, limits,
anchor). The game builds the bones from it at spawn with art's reference builder, `godot/ragdoll/builder.gd` (copy it
as it is): `build(skeleton, data)` adds a `PhysicalBoneSimulator3D` with one `PhysicalBone3D` per body;
`start(sim, data, velocity)` at the knockdown starts the simulation from the current (standing) pose with the avatar's
velocity and links the bodies with `Joint3D` nodes; `stop(sim)` at a revive. The parts are on layer {c['layer']}
(`{c['layer_name']}`) with mask {', '.join(str(m) for m in c['mask'])} (`{', '.join(c['mask_names'])}`): never players,
another ragdoll or itself. Bones without a body follow their parent (fingers the hand, toes the foot, the shoulders
and upper chest the chest); the sockets' `BoneAttachment3D`s follow the simulated bones with no change. The rig's feet
hang from `Root`, so a foot's joint links it to the lower leg (the builder's `Joint3D`s, not `PhysicalBone3D`'s own
joint). Proven on Jolt Physics, the game's engine: `tools/run.py ragdoll <glb> --fall`.

| Bone | Profile | Physical parent | Shape | kg | Joint |
|---|---|---|---|---|---|
{rows}
"""


def put_in_asset(asset: Path, data: dict) -> Path:
    """Writes the data into the asset folder, lists it in package.json and puts the ragdoll section in HANDOFF.md
    (replacing an earlier one)."""
    name = f"{data['asset']}.ragdoll.json"
    target = asset / "export" / name
    _ragdoll.write(data, target)
    pkg_path = asset / "package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    files = [f for f in pkg.get("files", []) if f.get("name") != name]
    files.append({"name": name, "bytes": target.stat().st_size, "sha256": _ragdoll.sha256(target)})
    pkg["files"] = files
    pkg_path.write_text(json.dumps(pkg, indent=1) + "\n", encoding="utf-8", newline="\n")
    handoff = asset / "HANDOFF.md"
    if handoff.is_file():
        text = handoff.read_text(encoding="utf-8")
        head, sep, rest = text.partition("## Ragdoll (art #115)")
        tail = ""
        if sep:
            nxt = rest.find("\n## ")
            tail = rest[nxt + 1:] if nxt >= 0 else ""
        text = head.rstrip("\n") + "\n\n" + handoff_section(data, name) + ("\n" + tail if tail else "")
        handoff.write_text(text, encoding="utf-8", newline="\n")
    return target


def fall(glb: Path, data_path: Path, out: Path, shots: bool) -> dict:
    """Runs godot/ragdoll/fall.gd on the GLB (headless, or in an off-screen window for shots); returns its report."""
    import_dir = PROJECT / "import"
    import_dir.mkdir(parents=True, exist_ok=True)
    for old in import_dir.glob("*.glb"):
        if old.name != glb.name:
            old.unlink()
            old.with_name(old.name + ".import").unlink(missing_ok=True)
    shutil.copyfile(glb, import_dir / glb.name)
    (import_dir / f"{glb.name}.import").write_text(_godot.import_file(_godot.import_params(glb)), encoding="utf-8",
                                                    newline="\n")
    _godot.install_offscreen(PROJECT)  # fall.gd preloads res://lib/offscreen.gd in both modes (#214)
    code, output = _godot.godot(["--headless", "--path", PROJECT, "--import"], _godot.IMPORT_TIMEOUT)
    if code != 0:
        raise common.Failure(f"godot --import (godot/ragdoll) exited {code}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "fall.json").unlink(missing_ok=True)
    args = ["--fixed-fps", "60", "--path", PROJECT, "-s", SCRIPT, "--", f"res://import/{glb.name}",
            data_path.resolve().as_posix(), out.resolve().as_posix(), "shots" if shots else "check"]
    if shots:  # an off-screen window (#214)
        code, output = _godot.window(["--audio-driver", "Dummy", *args], (640, 400), TIMEOUT, log=out / "godot.log")
    else:
        code, output = _godot.godot(["--headless", *args], TIMEOUT)
    (out / "godot.log").write_text(output, encoding="utf-8")
    report_path = out / "fall.json"
    if not report_path.is_file():
        errors = [ln for ln in output.splitlines() if "RAGDOLL error" in ln or "SCRIPT ERROR" in ln]
        raise common.Failure(f"fall.gd wrote no report (exit {code}): {'; '.join(errors[:4]) or 'see ' + (out / 'godot.log').as_posix()}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["godot_lines"] = _godot.noteworthy(output)
    return report


def run(args: argparse.Namespace) -> int:
    glb = args.glb if args.glb.is_file() else common.ROOT / args.glb
    if not glb.is_file():
        raise common.Failure(f"no GLB {args.glb.as_posix()}")
    glb = glb.resolve()
    out = (args.out or OUT / glb.stem).resolve()
    data = _ragdoll.measure(glb)
    gltf, _ = _ragdoll.read_glb(glb)
    skel = _ragdoll.skeleton(gltf)
    problems = _ragdoll.check(data, skel["names"]) + _ragdoll.shapes_in_bounds(data, skel["global"])
    for p in problems:
        common.bad(f"ragdoll data: {p}")
    if problems:
        return 1
    data_path = out / f"{glb.stem}.ragdoll.json"
    _ragdoll.write(data, data_path)
    common.ok(f"{len(data['bones'])} bodies -> {data_path.as_posix()}")
    if args.asset:
        target = put_in_asset(args.asset.resolve(), data)
        common.ok(f"asset: {target.as_posix()}, package.json, HANDOFF.md")
    failed = False
    for shots in ([False] if args.fall else []) + ([True] if args.shots else []):
        sub = out / ("shots" if shots else "fall")
        report = fall(glb, data_path, sub, shots)
        w = report["worst"]
        common.say(f"fall ({'window' if shots else 'headless'}, {report['physics_engine']}): {report['bodies']} bodies, "
                   f"{report['joints']} joints, rest from {report['rest_s']:.2f} s, after 0.5 s at most "
                   f"{w['speed_after_05_m_s']:.2f} m/s, cone over {w['cone_over_deg']:.1f} deg, hinge over "
                   f"{w['hinge_over_deg']:.1f} deg, anchors {w['anchor_m'] * 1000:.1f} mm, sockets "
                   f"{w['socket_m'] * 1000:.2f} mm, rest y {w.get('lowest_y_m', 0):.3f}..{w.get('highest_y_m', 0):.3f} m")
        for line in report.get("godot_lines", []):
            common.warn(f"godot: {line}")
        for f in report["failures"]:
            common.bad(f"fall: {f}")
        failed |= bool(report["failures"])
        if shots:
            args.shots.mkdir(parents=True, exist_ok=True)
            for png in ("fall_sheet.png", "shapes_sheet.png"):
                if (sub / png).is_file():
                    shutil.copy2(sub / png, args.shots / png)
            shutil.copy2(sub / "fall.json", args.shots / "fall.json")
            common.ok(f"sheets -> {args.shots.as_posix()}")
    return 1 if failed else 0
