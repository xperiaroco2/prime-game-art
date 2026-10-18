"""`house --bake`: the House's lightmap bake per zone (#83, from #83a's spike; docs/house.md "Light"). Stages the kit
and prop GLBs the zone scenes use, imports them, builds each zone's bake scene headless (godot/house/zone_build.gd),
bakes it in the editor through the lmbake plugin in an off-screen window (night only: house_bake.editor_allowed),
then shoots the baked and real-time frames (godot/house/bake_shots.gd) and measures them. With `--grid` each zone is
built and baked once per variant of house_bake.variants (texel x denoiser x bounce energy); with `--diag` once per
house_bake.diag_variants (#83b: the darkness against real time); with `--sheen` once per house_bake.sheen_variants
(#83c: the lamps' specular on top of the bake). Every Godot run takes the heavy-run lock (common.run)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from .. import common, house_bake, house_bake_props, house_lights, house_sky
from . import _godot

BUILD = "res://house/zone_build.gd"
SHOTS = "res://house/bake_shots.gd"
BAKE_DIR = _godot.PROJECT / "import" / "house" / "bake"
TIMEOUT = 900
MERGED = common.OUT / "house" / "merged"  # the merged shell's and batched dressing's GLBs, uv2.json (#107; house.py merger)
REVIEW_ROOMS = {"ground": ["living_room", "kitchen"], "basement": ["storage", "generator_hall"],
                "upper": ["bedroom", "landing"]}
# Rooms also shot facing their north wall (house_bake.wall_cam): the kitchen's worktops, uppers and fridge (#83).
REVIEW_WALL = {"ground": ["kitchen"]}


def stage(data: dict, scenes: Path, props: dict) -> list[str]:
    """Stages every kit piece and prop GLB the scenes under `scenes` instance; returns the names staged."""
    texts = [p.read_text(encoding="utf-8") for p in scenes.rglob("*.tscn")]
    names = house_bake.used_glbs(texts)
    kit = common.raw_dir() / data["settings"]["kit_dir"]
    staged = []
    for name in sorted(names):
        if name.startswith("kit_"):
            src, params = kit / f"{name[4:]}.glb", house_bake.KIT_IMPORT
            if "_m_" in name and (MERGED / f"{name[4:]}.glb").is_file():
                src = MERGED / f"{name[4:]}.glb"
        elif name.startswith("prop_batch_"):
            src, params = MERGED / f"{name[5:]}.glb", house_bake.PROP_IMPORT
        else:
            src, params = props.get(name[5:]), house_bake.PROP_IMPORT
        if name.endswith("_shadow"):  # #185: a shadow proxy (cast_shadow SHADOWS_ONLY, gi_mode off): no UV2
            params = house_bake.SHADOW_IMPORT
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
        props: dict, grid: bool = False, merge: bool = False, diag: bool = False, sheen: bool = False,
        before: Path | None = None, label: str | None = None, count: Path | None = None) -> int:
    unknown = [z for z in zones if z not in lights["zones"]]
    if unknown:
        raise common.Failure(f"house --bake: no zone {', '.join(unknown)} in lights.toml")
    raw = common.raw_dir()
    if count and (review or grid or diag or sheen):
        raise common.Failure("--count is a preset build without a bake: no --review, --grid, --diag or --sheen")
    no_bake = no_bake or bool(count)
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
    merged = MERGED / "uv2.json"
    extra = json.loads(merged.read_text(encoding="utf-8")) if merged.is_file() else {}
    extra = {k: v for k, v in extra.items() if v is not None}  # no null entry: zone_build.gd reads a float
    uv2.write_text(json.dumps({**house_bake.uv2_table(pieces), **extra}), encoding="utf-8", newline="\n")
    report: dict = {"preset": preset, "grid": grid, "merge": merge, "diag": diag, "sheen": sheen, "zones": {}}
    for zone in zones:
        report["zones"][zone] = {}
        for v in zone_variants(lights, zone, preset, grid, merge, diag, review is not None and not no_bake, sheen):
            report["zones"][zone][v["tag"]] = bake_variant(zone, v, work, raw, no_bake)
    (work / "bake_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    if count:
        shoot(data, lights, zones, preset, False, merge, count, count=True)
    if review and not no_bake:
        shoot(data, lights, zones, preset, grid, merge, review, diag, sheen)
        if before:
            compare(data, lights, zones, preset, review, before, label or "after")
    kind = "sheen" if sheen else "diag" if diag else "grid" if grid else preset
    common.ok(f"house --bake: {len(zones)} zones ({kind}); {(work / 'bake_report.json').as_posix()}")
    return 0


def zone_variants(lights: dict, zone: str, preset: str, grid: bool, merge: bool, diag: bool,
                  reference: bool = False, sheen: bool = False) -> list[dict]:
    """The zone's bakes: --sheen's, --diag's, or the preset's or grid's (with `reference`, a review: the reference
    bake too)."""
    if sheen:
        return house_bake.sheen_variants(lights, zone)
    if diag:
        return house_bake.diag_variants(lights, zone)
    return house_bake.variants(lights, zone, preset, grid, merge, reference)


def bake_variant(zone: str, v: dict, work: Path, raw: Path, no_bake: bool) -> dict:
    """Builds one zone's bake scene for one variant headless and, unless no_bake, bakes it in the editor."""
    tag = v["tag"]
    bake_json = work / f"bake_{tag}.json"
    bake_json.write_text(json.dumps(v["bake"]), encoding="utf-8", newline="\n")
    args = house_bake.build_args(zone, tag, v["texel"], v["bake"], (work / "uv2.json").as_posix(),
                                 bake_json.as_posix(), merge=v["merge"],
                                 lights=v.get("lights", "static"))
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
    project = Path(_godot.PROJECT) / "project.godot"
    kept = project.read_bytes()  # the editor rewrites the committed file's header comment on save: put it back
    try:
        # the editor ignores the 1x1 borderless start: part of its window shows at the screen's corner during its
        # start-up, until lmbake.gd moves it off-screen (#214, docs/godot.md "The off-screen window")
        code, out = _godot.window(["--editor", "--path", _godot.PROJECT, "--", f"lmbake={scene}"], (1280, 720),
                                  TIMEOUT)
    finally:
        if project.read_bytes() != kept:
            project.write_bytes(kept)
    z["bake"] = {"exit": code, "seconds": round(time.time() - t0),
                 "log": log.read_text(encoding="utf-8") if log.is_file() else ""}
    if code != 0 or not log.is_file() or "light_data=none" in z["bake"]["log"]:
        raise common.Failure(f"the editor bake of {zone} {tag} failed (exit {code}): {z['bake']['log'][-400:]}")
    common.say(f"  {zone} {tag}: baked in {z['bake']['seconds']} s")
    return z


def shoot(data: dict, lights: dict, zones: list[str], preset: str, grid: bool, merge: bool, review: Path,
          diag: bool = False, sheen: bool = False, count: bool = False) -> None:
    """Per zone the rows of house_bake.shot_rows (the preset and the grid: the real-time row, the first variant's scene
    without its lightmap, then one baked row per variant; --diag: its modes) from its review rooms' E1 cameras, wall
    cameras (REVIEW_WALL) and seam camera: the frames, sheet.png (about 1280 px across, a label per row), measures.json
    and numbers.md (L*, dark %, C* p90 per frame; each row's L* against the reference rows; real-time and shadowed
    lights and draw calls per camera) into `review`. A sheen row also carries the zone's probe boxes and the glow types."""
    rows = []
    glow = house_bake.glow_types(lights)
    rooms_of = house_lights.zone_rooms(lights, data)
    for zone in zones:
        if zone not in REVIEW_ROOMS:
            common.say(f"  bake: no review rooms for {zone} (not shot)")
            continue
        cams = house_bake.views(data, REVIEW_ROOMS[zone], REVIEW_WALL.get(zone, []))
        scene = "res://import/house/bake/{}_{}.scn"
        probes = house_bake.probe_boxes(data, rooms_of[zone])
        rows += [{**r, "zone": zone, "scene": scene.format(zone, r["tag"]), "cams": cams,
                  **({"probes": probes, "glow_types": glow} if "sheen" in r else {})}
                 for r in house_bake.shot_rows(zone, zone_variants(lights, zone, preset, grid, merge, diag, not count,
                                                                   sheen))]
    if not rows:
        return
    jobs = common.OUT / "house" / "bake" / "shots.json"
    layout = house_bake.sheet_layout(len(rows), max(len(r["cams"]) for r in rows))
    jobs.write_text(json.dumps({**layout, "rows": rows}, indent=1), encoding="utf-8", newline="\n")
    review.mkdir(parents=True, exist_ok=True)
    code, out = _godot.window(["--path", _godot.PROJECT, "-s", SHOTS, "--", f"jobs={jobs.as_posix()}",
                               f"out={review.as_posix()}"], (1280, 720), TIMEOUT)
    if code != 0:
        raise common.Failure(f"bake_shots.gd exited {code}:\n" + "\n".join(out.splitlines()[-15:]))
    if count:
        write_counts(lights, zones, rows, review)
        return
    numbers: dict[str, list[dict]] = {}
    for row in rows:
        frames = [review / f"{row['label']}_{ci}.png" for ci in range(len(row["cams"]))]
        numbers[row["label"]] = [house_bake.measures(*house_bake.read_png(f)) for f in frames if f.is_file()]
    (review / "measures.json").write_text(json.dumps(numbers, indent=1), encoding="utf-8", newline="\n")
    shots = json.loads((review / "shots.json").read_text(encoding="utf-8")).get("shots", [])
    costs = house_bake.shot_costs(shots)
    md = "\n".join(house_bake.numbers_md(z, {k: v for k, v in numbers.items() if k.startswith(z + "_")},
                                         references(z, rows, diag, sheen),
                                         house_bake.view_names(REVIEW_ROOMS[z], REVIEW_WALL.get(z, [])),
                                         note=SHEEN_NOTE if sheen else house_bake.REFERENCE_NOTE, extra=costs)
                   for z in zones if z in REVIEW_ROOMS)
    (review / "numbers.md").write_text(md, encoding="utf-8", newline="\n")
    for name, ms in numbers.items():
        common.say(f"  {name}: L* " + ", ".join(str(m["L_mean"]) for m in ms))


def compare(data: dict, lights: dict, zones: list[str], preset: str, review: Path, before: Path, label: str) -> None:
    """The before / after review (--before, docs/house.md "Baking with lab props"): per zone the before run's baked row
    over this run's baked and sheen rows (house_bake_props.compare_rows) from the same cameras, as before_after.png
    (about 1280 px across, each row titled) and before_after.md (house_bake.numbers_md against the before row)."""
    sheen = lights["presets"][preset].get("sheen")
    titles, tiles, table, md = [], [], {}, []
    for zone in [z for z in zones if z in REVIEW_ROOMS]:
        cams = house_bake.views(data, REVIEW_ROOMS[zone], REVIEW_WALL.get(zone, []))
        tw, th = house_bake_props.tile_size(len(cams))
        rows = house_bake_props.compare_rows(zone, preset, sheen, label)
        ztable = {}
        for r in rows:
            folder = before if r["side"] == "before" else review
            line, ms = [], []
            for ci in range(len(cams)):
                f = folder / f"{r['row']}_{ci}.png"
                if not f.is_file():
                    common.say(f"  compare: no {f.as_posix()} (a grey tile)")
                    line.append(None)
                    continue
                w, h, px = house_bake.read_png(f)
                ms.append(house_bake.measures(w, h, px))
                line.append(house_bake_props.downscale(w, h, px, tw, th))
            titles.append(f"{zone} {r['title']}")
            tiles.append(line)
            ztable[r["title"]] = ms
        table.update(ztable)
        md.append(house_bake.numbers_md(zone, ztable, rows[0]["title"],
                                        house_bake.view_names(REVIEW_ROOMS[zone], REVIEW_WALL.get(zone, [])),
                                        note=f"the props as committed, baked; before: {before.as_posix()}"))
    if not tiles:
        return
    width = max(len(line) for line in tiles) * tw
    rows_px = house_bake_props.sheet(tiles, titles, tw, th)
    house_sky.write_png(review / "before_after.png", width, len(rows_px), rows_px)
    (review / "before_after.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
    common.say(f"  compare: {(review / 'before_after.png').as_posix()} ({len(titles)} rows)")


def write_counts(lights: dict, zones: list[str], rows: list[dict], folder: Path) -> dict:
    """--count: draw_calls.json and draw_calls.md (house_bake.draw_calls_md) from the shots, a WARN line per view over
    lights.toml's [budget]; with a draw_calls.json in `folder`/../before, the table reads before -> after."""
    shots = json.loads((folder / "shots.json").read_text(encoding="utf-8")).get("shots", [])
    table = house_bake.draw_calls(shots, rows)
    names = {z: house_bake.view_names(REVIEW_ROOMS[z], REVIEW_WALL.get(z, [])) for z in zones if z in REVIEW_ROOMS}
    old = folder.parent / "before" / "draw_calls.json"
    before = json.loads(old.read_text(encoding="utf-8"))["table"] if old.is_file() and old.parent != folder else None
    report(lights.get("budget", {}), table, names, folder, before)
    return table


def report(budget: dict, table: dict, names: dict[str, list[str]], folder: Path, before: dict | None = None) -> None:
    """The draw calls per view against lights.toml's [budget], one code path for --count and --walk (#185):
    draw_calls.json and draw_calls.md (house_bake.draw_calls_md) into `folder`, a WARN line per view over a limit."""
    (folder / "draw_calls.json").write_text(json.dumps({"budget": budget, "views": names, "table": table}, indent=1),
                                            encoding="utf-8", newline="\n")
    (folder / "draw_calls.md").write_text(house_bake.draw_calls_md(table, names, budget, before), encoding="utf-8",
                                          newline="\n")
    for line in house_bake.budget_warnings(budget, table, names):
        common.say(f"  {line}")
    common.say(f"  draw calls: {(folder / 'draw_calls.md').as_posix()}")


SHEEN_NOTE = "every lamp real-time with shadows and specular plus the bake's bounce: the sheen's target"


def references(zone: str, rows: list[dict], diag: bool, sheen: bool = False) -> list[str]:
    """The rows numbers.md measures the others against: first the right reference (hybrid_nospec: real-time diffuse
    direct light with shadows plus the bake's own bounce, #83b), then the leaking real-time row; --diag adds real time
    with shadows (with and without specular) and the hybrid row; --sheen: hybrid (the look's target), then the bake
    alone (the before row)."""
    mine = [r for r in rows if r["zone"] == zone]
    if sheen:
        return ([r["label"] for r in mine if r["mode"] == "hybrid"]
                + [r["label"] for r in mine if r["mode"] == "baked"])
    first = [r["label"] for r in mine if r["mode"] == house_bake.REFERENCE_MODE]
    others = ("realtime", "realtime_shadow", "realtime_shadow_nospec", "hybrid") if diag else ("realtime",)
    return first + [r["label"] for r in mine if r["mode"] in others]
