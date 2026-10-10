"""`house --bake`: the House's lightmap bake per zone (#83, from #83a's spike; docs/house.md "Light"). Stages the kit
and prop GLBs the zone scenes use, imports them, builds each zone's bake scene headless (godot/house/zone_build.gd),
bakes it in the editor through the lmbake plugin in an off-screen window (night only: house_bake.editor_allowed),
then shoots the baked and real-time frames (godot/house/bake_shots.gd) and measures them. With `--grid` each zone is
built and baked once per variant of house_bake.variants (texel x denoiser x bounce energy). Every Godot run takes the
heavy-run lock (common.run)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from .. import common, house_bake
from . import _frames, _godot

BUILD = "res://house/zone_build.gd"
SHOTS = "res://house/bake_shots.gd"
BAKE_DIR = _godot.PROJECT / "import" / "house" / "bake"
TIMEOUT = 900
REVIEW_ROOMS = {"ground": ["living_room", "kitchen"], "basement": ["storage", "generator_hall"],
                "upper": ["bedroom", "landing"]}


def stage(data: dict, scenes: Path, props: dict) -> list[str]:
    """Stages every kit piece and prop GLB the scenes under `scenes` instance; returns the names staged."""
    texts = [p.read_text(encoding="utf-8") for p in scenes.rglob("*.tscn")]
    names = house_bake.used_glbs(texts)
    kit = common.raw_dir() / data["settings"]["kit_dir"]
    staged = []
    for name in sorted(names):
        if name.startswith("kit_"):
            src, params = kit / f"{name[4:]}.glb", house_bake.KIT_IMPORT
        else:
            src, params = props.get(name[5:]), house_bake.PROP_IMPORT
        if src is None or not Path(src).is_file():
            common.say(f"  bake: no GLB for {name} (left out)")
            continue
        _godot.stage(Path(src), name, params)
        staged.append(name)
    return staged


def night_or_fail(raw: Path) -> None:
    """Refuses an editor run outside the night window (or a granted one)."""
    if not house_bake.editor_allowed(time.time(), house_bake.grant_text(raw)):
        raise common.Failure(house_bake.EDITOR_BAN)


def run(data: dict, lights: dict, zones: list[str], preset: str, review: Path | None, no_bake: bool,
        props: dict, grid: bool = False, merge: bool = False) -> int:
    unknown = [z for z in zones if z not in lights["zones"]]
    if unknown:
        raise common.Failure(f"house --bake: no zone {', '.join(unknown)} in lights.toml")
    raw = common.raw_dir()
    if not no_bake:
        night_or_fail(raw)
    staged = stage(data, _godot.PROJECT / "import" / "house", props)
    _godot.clear_staged(set(staged))
    errors = [line for line in _godot.import_project() if "ERROR" in line]
    for line in errors[:10]:
        common.say(f"  import: {line}")
    work = common.OUT / "house" / "bake"
    work.mkdir(parents=True, exist_ok=True)
    uv2 = work / "uv2.json"
    pieces = json.loads((raw / data["settings"]["kit_dir"] / "pieces.json").read_text(encoding="utf-8"))
    uv2.write_text(json.dumps(house_bake.uv2_table(pieces)), encoding="utf-8", newline="\n")
    report: dict = {"preset": preset, "grid": grid, "merge": merge, "zones": {}}
    for zone in zones:
        report["zones"][zone] = {}
        for v in house_bake.variants(lights, zone, preset, grid, merge):
            report["zones"][zone][v["tag"]] = bake_variant(zone, v, work, raw, no_bake)
    (work / "bake_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    if review and not no_bake:
        shoot(data, lights, zones, preset, grid, merge, review)
    common.ok(f"house --bake: {len(zones)} zones ({'grid' if grid else preset}); {(work / 'bake_report.json').as_posix()}")
    return 0


def bake_variant(zone: str, v: dict, work: Path, raw: Path, no_bake: bool) -> dict:
    """Builds one zone's bake scene for one variant headless and, unless no_bake, bakes it in the editor."""
    tag = v["tag"]
    bake_json = work / f"bake_{tag}.json"
    bake_json.write_text(json.dumps(v["bake"]), encoding="utf-8", newline="\n")
    args = house_bake.build_args(zone, tag, v["texel"], v["bake"], (work / "uv2.json").as_posix(),
                                 bake_json.as_posix(), merge=v["merge"])
    code, out = _godot.godot(["--headless", "--path", _godot.PROJECT, "-s", BUILD, "--", *args], TIMEOUT)
    built = BAKE_DIR / f"{zone}_{tag}_build.json"
    if code != 0 or not built.is_file():
        raise common.Failure(f"zone_build.gd {zone} {tag} exited {code}:\n" + "\n".join(out.splitlines()[-15:]))
    z = {"build": json.loads(built.read_text(encoding="utf-8"))}
    b = z["build"]
    common.say(f"  {zone} {tag}: {b['meshes']} meshes ({b['merged']} floor tiles merged), {b['lights']} lights, "
               f"{b['texels'] / 1e6:.2f} M texels at {v['texel']:g}/m")
    if no_bake:
        return z
    night_or_fail(raw)
    t0 = time.time()
    scene = f"res://import/house/bake/{zone}_{tag}.scn"
    log = BAKE_DIR / f"{zone}_{tag}_bake_log.txt"
    log.unlink(missing_ok=True)
    code, out = _godot.godot(["--editor", "--path", _godot.PROJECT, "--position", _frames.POSITION,
                              "--resolution", "1280x720", "--", f"lmbake={scene}"], TIMEOUT)
    z["bake"] = {"exit": code, "seconds": round(time.time() - t0),
                 "log": log.read_text(encoding="utf-8") if log.is_file() else ""}
    if code != 0 or not log.is_file() or "light_data=none" in z["bake"]["log"]:
        raise common.Failure(f"the editor bake of {zone} {tag} failed (exit {code}): {z['bake']['log'][-400:]}")
    common.say(f"  {zone} {tag}: baked in {z['bake']['seconds']} s")
    return z


def shoot(data: dict, lights: dict, zones: list[str], preset: str, grid: bool, merge: bool, review: Path) -> None:
    """Per zone its real-time row (the first variant's scene without its lightmap), then one baked row per variant,
    from its review rooms' E1 cameras and seam camera: the frames, sheet.png (about 1280 px across),
    measures.json and numbers.md (L*, dark %, C* p90 per frame; each baked row's L* against real time) into
    `review`."""
    rows = []
    for zone in zones:
        if zone not in REVIEW_ROOMS:
            common.say(f"  bake: no review rooms for {zone} (not shot)")
            continue
        cams = house_bake.views(data, REVIEW_ROOMS[zone])
        tags = [v["tag"] for v in house_bake.variants(lights, zone, preset, grid, merge)]
        scene = "res://import/house/bake/{}_{}.scn"
        rows.append({"label": f"{zone}_realtime", "zone": zone, "scene": scene.format(zone, tags[0]),
                     "mode": "realtime", "cams": cams})
        rows += [{"label": f"{zone}_{t}_baked", "zone": zone, "scene": scene.format(zone, t), "mode": "baked",
                  "cams": cams} for t in tags]
    if not rows:
        return
    jobs = common.OUT / "house" / "bake" / "shots.json"
    layout = house_bake.sheet_layout(len(rows), max(len(r["cams"]) for r in rows))
    jobs.write_text(json.dumps({**layout, "rows": rows}, indent=1), encoding="utf-8", newline="\n")
    review.mkdir(parents=True, exist_ok=True)
    code, out = _godot.godot(["--path", _godot.PROJECT, "--position", _frames.POSITION, "--resolution", "1280x720",
                              "-s", SHOTS, "--", f"jobs={jobs.as_posix()}", f"out={review.as_posix()}"], TIMEOUT)
    if code != 0:
        raise common.Failure(f"bake_shots.gd exited {code}:\n" + "\n".join(out.splitlines()[-15:]))
    numbers: dict[str, list[dict]] = {}
    for row in rows:
        frames = [review / f"{row['label']}_{ci}.png" for ci in range(len(row["cams"]))]
        numbers[row["label"]] = [house_bake.measures(*house_bake.read_png(f)) for f in frames if f.is_file()]
    (review / "measures.json").write_text(json.dumps(numbers, indent=1), encoding="utf-8", newline="\n")
    md = "\n".join(house_bake.numbers_md(z, {k: v for k, v in numbers.items() if k.startswith(z + "_")},
                                         f"{z}_realtime", ["E1 " + r for r in REVIEW_ROOMS[z]] + ["seam"])
                   for z in zones if z in REVIEW_ROOMS)
    (review / "numbers.md").write_text(md, encoding="utf-8", newline="\n")
    for name, ms in numbers.items():
        common.say(f"  {name}: L* " + ", ".join(str(m["L_mean"]) for m in ms))
