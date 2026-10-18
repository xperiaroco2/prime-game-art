"""`house`: checks the House map's layout data (layouts/house/*.toml) and generates its Godot scenes from the House
kit: one scene per room and per level and house.tscn (tools/runner/house_layout.py, docs/house.md)."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path

from .. import (common, house_bake, house_basement, house_bake_props, house_clutter, house_dressing, house_export,
               house_fill, house_layout, house_lights, house_merge, house_routes)
from . import _godot, _house_bake

NAME = "house"
HELP = "check the House layout (layouts/house/*.toml) and generate its room, level and house scenes from the kit"
DEFAULT_OUT = common.ROOT / "godot" / "import" / "house"
WALK = "res://house/walk.gd"
BASEMENT = "res://house/basement.gd"
ROUTES_OUT = common.OUT / "house" / "routes.json"  # the last walk's route times, for the basement's sheet
WALK_TIMEOUT = 240


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--layouts", type=Path, default=house_layout.LAYOUT_DIR, help="the layout folder")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="where the scenes go (default godot/import/house, res://import/house)")
    parser.add_argument("--check", action="store_true", help="only check the layout; write nothing")
    parser.add_argument("--clutter", action="store_true",
                        help="regenerate the dressing files' clutter blocks (house_clutter.py, seeded) before the checks")
    parser.add_argument("--props-spec", type=Path, action="append", default=[], metavar="TOML",
                        help="another prop catalogue for the dressing's sizes (e.g. a library.toml not yet on main)")
    parser.add_argument("--walk", type=Path, metavar="DIR",
                        help="stage the kit GLBs, import, then walk and shoot the house in an off-screen Godot window "
                             "into DIR (walk.json, sheet.png, exterior.png, stills)")
    parser.add_argument("--bake", metavar="ZONES",
                        help="bake these zones of lights.toml (comma-separated, or all) in the editor in an off-screen "
                             "window: night only (00:00-08:00 local) unless the manager granted a window")
    parser.add_argument("--preset", default="high", choices=["high", "low"], help="the bake's texel preset")
    parser.add_argument("--no-bake", action="store_true", help="with --bake: stage, import and build only (by day)")
    parser.add_argument("--grid", action="store_true",
                        help="with --bake: one bake per variant of texel 8/12/16 x denoiser on/off x bounce energy "
                             "1.0/1.5 instead of the preset (#83)")
    parser.add_argument("--diag", action="store_true",
                        help="with --bake: the diagnostic bakes of #83b instead of the preset (real time with and "
                             "without shadows, direct only, the hybrid row, the old default; docs/house.md)")
    parser.add_argument("--sheen", action="store_true",
                        help="with --bake: the sheen grid of #83c instead of the preset (the bake plus the lamps' "
                             "specular: the directional lightmap's lobe, reflection probes, specular-only real-time "
                             "lights; docs/house.md)")
    parser.add_argument("--merge", action="store_true",
                        help="with --bake: weld each room level's floor tiles into one unwrapped mesh (one lightmap "
                             "island per floor kind and height instead of one per tile)")
    parser.add_argument("--props-dir", type=Path, metavar="DIR",
                        help="with --bake: stage GLBs from DIR in place of the props named after them (or in "
                             "--props-map) for the bake and its review; the committed props are not touched")
    parser.add_argument("--props-map", type=Path, metavar="TOML",
                        help="with --props-dir: prop id -> GLB in DIR, extra pieces per room, the sheet's label "
                             "(tools/runner/house_bake_props.py)")
    parser.add_argument("--before", type=Path, metavar="DIR",
                        help="with --bake and --review: an earlier review of the same preset; adds before_after.png "
                             "and before_after.md (its baked row over this run's baked and sheen rows)")
    parser.add_argument("--count", type=Path, metavar="DIR",
                        help="with --bake: build without baking and count the draw calls per review view, baked and "
                             "High, against lights.toml's [budget] (draw_calls.json and .md, the frames; #107)")
    parser.add_argument("--no-merge", action="store_true",
                        help="draw every kit piece as its own instance (the scenes before #107's merged shell)")
    parser.add_argument("--cell", metavar="M|room",
                        help="override house.toml's [merge] cell: the merged shell's and batches' grid cell in metres, "
                             "or room (one per room; #185's grid run)")
    parser.add_argument("--review", type=Path, metavar="DIR",
                        help="with --bake: baked and real-time frames, sheet.png and measures.json into DIR")
    parser.add_argument("--export", type=Path, metavar="DIR",
                        help="write the game-ready package into DIR (GLBs under assets/environment/, one room scene per "
                             "game room under levels/house/rooms/, package.json), then load every scene headless")
    parser.add_argument("--package", type=int, metavar="N",
                        help="with --export: only package N of house.toml's [export] (1 kit .. 8 task props)")
    parser.add_argument("--no-godot", action="store_true", help="with --export: write only, no Godot check")
    parser.add_argument("--sheet", action="store_true",
                        help="with --export: after the check, shoot the kitchen, storage and attic off-screen from the "
                             "export folder into DIR/_check/sheet.png")
    parser.add_argument("--package-sheet", type=Path, metavar="DIR",
                        help="with --package N: stage package N from the committed files under assets/ into DIR and "
                             "shoot its look-approval sheet off-screen (the kit's families or each room from its door, its neighbours' walls and "
                             "the slab over it staged round it as unlit context)")
    parser.add_argument("--basement", type=Path, metavar="DIR",
                        help="stage and import like --walk, then light the basement with lamp stand-ins and shoot its "
                             "review into DIR (basement_review.toml; sheet.png, a still per room, basement.json)")


def report_fill(data: dict, layouts: Path, extra) -> list[dict]:
    """Logs every clutter room's fill measures (house_fill) and writes them to tools/out/house/fill.json."""
    st = data["settings"]
    cat = house_dressing.catalogue(house_dressing.spec_paths(st, extra=extra))
    dressings = house_dressing.load(Path(layouts) / st.get("dressing_dir", "dressing"))
    rows = house_fill.table(data, dressings, cat)
    for m in rows:
        common.say(f"  fill {house_fill.fmt(m)}")
    short = [m["room"] for m in rows if house_fill.passes(m)]
    common.say(f"house fill: {len(rows) - len(short)} of {len(rows)} rooms meet the targets"
               + (f"; short: {', '.join(short)}" if short else ""))
    out = common.OUT / "house" / "fill.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8", newline="\n")
    return rows


def run(args: argparse.Namespace) -> int:
    data = house_layout.load(args.layouts)
    lights = house_lights.load(args.layouts / "lights.toml")
    problems = house_layout.validate(data) + house_lights.validate(lights, data)
    rooms = sum(len(lv["rooms"]) for lv in data["levels"])
    common.say(f"house layout: {len(data['levels'])} levels, {rooms} rooms, kit {data['settings']['kit_dir']}")
    if problems:
        for p in problems:
            common.say(f"  {p}")
        raise common.Failure(f"house layout: {len(problems)} problems")
    common.say("house layout: grid, openings, corners, footprints, stairs, holes and the light kit hold")
    if args.cell:
        data["settings"].setdefault("merge", {})["cell"] = args.cell
        cell_size(data)  # refuses a bad value before anything is built
    if args.clutter:
        st = data["settings"]
        cat = house_dressing.catalogue(house_dressing.spec_paths(st, extra=args.props_spec))
        counts = house_clutter.write(data, Path(args.layouts) / st.get("dressing_dir", "dressing"), cat)
        common.say(f"house clutter: {sum(counts.values())} items in {len(counts)} rooms (seed {house_clutter.SEED})")
        report_fill(data, args.layouts, args.props_spec)
    dressing = check_dressing(data, args.layouts, args.props_spec)
    check_basement(data, args.layouts, args.props_spec)
    routes = house_routes.load(args.layouts)
    bad_routes = house_routes.problems(data, routes)
    if bad_routes:
        for p in bad_routes:
            common.say(f"  {p}")
        raise common.Failure(f"house routes: {len(bad_routes)} problems")
    if args.check:
        return 0
    if args.package_sheet:
        if args.package is None:
            raise common.Failure("--package-sheet needs --package N")
        from . import _house_review
        return _house_review.run(args.package_sheet.resolve(), args.package,
                                 house_export.settings(data).get("kit_families", {"kit": ["*"]}),
                                 extra=_house_review.views(data), ctx=_house_review.context(data))
    planned = house_layout.plan(data)
    if args.export and (args.props_dir or args.props_map or args.before):
        raise common.Failure("--props-dir, --props-map and --before are for --bake, not --export")
    if args.export:
        return export(data, lights, planned, dressing, args)
    found = prop_glbs(data, dressing)
    label = None
    if args.props_dir or args.props_map or args.before:
        found, dressing, label = lab_props(args, found, dressing)
    st = data["settings"]
    merge = None if args.no_merge else merger(data, found)
    summary = house_layout.write_scenes(data, planned, args.out, dressing,
                                        lambda pid: st["prop_res"].format(id=pid) if pid in found else None, merge)
    if merge:
        uv2 = {k: v for k, v in merge.uv2.items() if v is not None}  # no null entry: zone_build.gd reads a float
        (_house_bake.MERGED / "uv2.json").write_text(json.dumps(uv2, indent=1), encoding="utf-8", newline="\n")
        common.say(f"  merged shell: {len(merge.uv2)} merged meshes for {merge.hidden} piece instances; batched "
                   f"dressing: {len(merge.batched)} batches for {merge.props} props (#107; "
                   f"{_house_bake.MERGED.as_posix()})")
    held = {rid: ids for rid, ids in summary["placeholders"].items() if ids}
    if summary["props"]:
        common.say(f"  dressing: {sum(summary['props'].values())} props and fixtures in {len(dressing)} rooms, "
                   f"{sum(len(v) for v in held.values())} as placeholder boxes (no GLB yet: "
                   f"{', '.join(sorted({i for v in held.values() for i in v})) or '-'})")
    for name, s in summary["levels"].items():
        common.say(f"  {name}: {s['rooms']} rooms, {s['instances']} piece instances")
    report = common.OUT / "house" / "plan.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"summary": summary, "plan": planned}, indent=1), encoding="utf-8", newline="\n")
    fixtures = house_lights.plan(lights, data)
    lit = house_lights.write(lights, data, planned, fixtures, args.out)
    (common.OUT / "house" / "lights.json").write_text(
        json.dumps({"summary": lit, "presets": lights["presets"], "bake": lights["bake"], "zones": lights["zones"],
                    "fixtures": fixtures}, indent=1), encoding="utf-8", newline="\n")
    for zone, z in lit["zones"].items():
        common.say(f"  zone {zone}: {z['rooms']} rooms, {z['pieces']} level pieces, {z['fixtures']} fixtures, "
                   f"{z['lights'] - z['fixtures']} moon spots")
    common.say(f"house: {summary['instances']} instances of {len(summary['pieces'])} pieces -> {args.out.as_posix()}; "
               f"plan {report.as_posix()}")
    if args.bake:
        if args.out.resolve() != DEFAULT_OUT.resolve():
            raise common.Failure("--bake needs the scenes in godot/import/house (drop --out)")
        zones = list(lights["zones"]) if args.bake == "all" else args.bake.split(",")
        return _house_bake.run(data, lights, zones, args.preset, args.review, args.no_bake, found, args.grid,
                               args.merge, args.diag, args.sheen, args.before, label,
                               args.count.resolve() if args.count else None)
    if (args.walk or args.basement) and args.out.resolve() != DEFAULT_OUT.resolve():
        raise common.Failure("--walk and --basement need the scenes in godot/import/house (drop --out)")
    code = 0
    if args.walk or args.basement:
        errors = stage(data, summary, found)
        if args.walk:
            code = walk(data, args.walk.resolve(), routes, errors, dressing, lights)
        if args.basement:
            code = basement(data, args.layouts, args.props_spec, args.basement.resolve(), errors) or code
    return code


def export(data: dict, lights: dict, planned: dict, dressing: dict, args: argparse.Namespace) -> int:
    """`--export DIR`: writes the package (house_export.write), then, unless --no-godot, opens DIR as a Godot project
    and loads every room scene headless (_house_export.check)."""
    if args.package is not None and args.package not in house_export.packages(data):
        raise common.Failure(f"no package {args.package} in house.toml's [export] "
                             f"({', '.join(str(n) for n in house_export.packages(data))})")
    fixtures = house_lights.plan(lights, data)
    if "attic" not in dressing and any(r["id"] == "attic" for lv in data["levels"] for r in lv["rooms"]):
        from .. import house_attic
        dressing = dict(dressing, attic=house_export.attic_dressing(house_attic.load("attic")))
    try:
        glbs = prop_glbs(data, dressing)
        ex = house_export.settings(data)
        merge = None if args.no_merge else merger(  # the merged shell and batched dressing ship in the package (#107)
            data, glbs, Path(args.export) / "_build" / "merged",
            house_export.asset_res(data, ex["kit_set"], f"{house_export.MERGED_DIR}/{{id}}"),
            house_export.asset_res(data, ex["prop_set"], f"{house_export.MERGED_DIR}/{{id}}"))
        summary = house_export.write(data, planned, dressing, fixtures, args.export, common.raw_dir(), glbs,
                                     args.package, merge)
    except ValueError as e:
        raise common.Failure(f"house export: {e}") from e
    glbs = sum(1 for f in summary["files"] if f.endswith(".glb"))
    common.say(f"house export: package {summary['name']}: {len(summary['rooms'])} room scenes, {glbs} GLBs, "
               f"{len(summary['files'])} files -> {args.export.as_posix()}")
    if summary["placeholders"]:
        common.say(f"  props without a GLB, as sized Placeholders markers: {', '.join(summary['placeholders'])}")
    if summary["unplaced"]:
        common.say(f"  level pieces in no room (not exported): {', '.join(summary['unplaced'])}")
    if summary["stale"]:
        common.warn(f"  {len(summary['stale'])} files in {args.export.as_posix()} are not in this package (an earlier "
                    f"export; not deleted), e.g. {summary['stale'][0]}")
    if args.no_godot:
        return 0
    from . import _house_export
    code = _house_export.check(args.export.resolve(), summary)
    if args.sheet:
        code = _house_export.sheet(args.export.resolve(), summary) or code
    return code


def basement(data: dict, layouts: Path, extra, folder: Path, errors: list[str] = ()) -> int:
    """Runs godot/house/basement.gd off-screen on the staged house: lamp stand-ins at the basement's fixtures, a still
    per room from its door, the plan with the last walk's route times (tools/out/house/routes.json), the hall's far
    edge L* (house_basement.review_request, layouts/house/basement_review.toml). A far edge at or under its L* fails."""
    st = data["settings"]
    spec = tomllib.loads((Path(layouts) / house_basement.REVIEW).read_text(encoding="utf-8"))
    dressings = house_dressing.load(Path(layouts) / st.get("dressing_dir", "dressing"))
    cat = house_dressing.catalogue(house_dressing.spec_paths(st, extra=extra))
    routes = json.loads(ROUTES_OUT.read_text(encoding="utf-8")) if ROUTES_OUT.is_file() else []
    request = house_basement.review_request(data, dressings, cat, spec, routes)
    req = common.OUT / "house" / "basement_request.json"
    req.write_text(json.dumps(request, indent=1), encoding="utf-8", newline="\n")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "basement.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", _godot.PROJECT, "--audio-driver", "Dummy", "-s", BASEMENT, "--",
                                  req.as_posix(), folder.as_posix()], (1600, 900), WALK_TIMEOUT)
    if code != 0 or not (folder / "basement.json").is_file():
        tail = "\n".join(output.splitlines()[-20:])
        raise common.Failure(f"basement.gd failed (exit code {code}):\n{tail}")
    result = json.loads((folder / "basement.json").read_text(encoding="utf-8"))
    for name, info in result["shots"].items():
        common.say(f"  {name}: median L* {info['lstar_median']:g}; {info.get('draw_calls')} draw calls in view "
                   f"({info.get('dressing_draw_calls')} the dressing's), {info.get('primitives')} primitives; "
                   f"{info.get('room')}'s dressing {info.get('dressing_meshes')} meshes, "
                   f"{info.get('dressing_triangles')} triangles")
    far = result.get("far_edge", {})
    common.say(f"  far edge ({far.get('shot')}): median L* {far.get('lstar_median')} (needs > {far.get('min_lstar')})")
    common.say(f"  {result['lamps']} lamp stand-ins; route lines: {len(routes)}; sheet {(folder / 'sheet.png').as_posix()}")
    if not far.get("pass") or errors:
        common.bad(f"house basement review: far edge {'ok' if far.get('pass') else 'too dark'}, "
                   f"{len(errors)} import errors")
        return 1
    common.ok(f"house basement review: {len(result['shots'])} shots, the far edge holds")
    return 0


def check_dressing(data: dict, layouts: Path, extra) -> dict:
    """Checks layouts/house/dressing/*.toml against the rooms (house_dressing.check); writes tools/out/house/dressing.json;
    returns room id -> its report. A problem fails the command."""
    st = data["settings"]
    folder = Path(layouts) / st.get("dressing_dir", "dressing")
    if not folder.is_dir():
        return {}
    paths = house_dressing.spec_paths(st, extra=extra)
    missing = [p.as_posix() for p in paths if not p.is_file()]
    cat = house_dressing.catalogue(paths)
    result = house_dressing.check(data, house_dressing.load(folder), cat)
    report = common.OUT / "house" / "dressing.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    slim = {rid: {k: v for k, v in r.items() if k != "resolved"} for rid, r in result["rooms"].items()}
    report.write_text(json.dumps({"catalogues": [p.as_posix() for p in paths], "missing": missing, "rooms": slim,
                                  "problems": result["problems"], "notes": result["notes"]}, indent=1),
                      encoding="utf-8", newline="\n")
    for r in result["rooms"].values():
        common.say(f"  dressing {r['room']}: {r['props']} props, {r['fixtures']} fixtures; capsule reaches "
                   f"{sum(r['reach'].values())}/{len(r['reach'])} doors, stairs, stations and spawns")
    for n in result["notes"]:
        common.say(f"  note: {n}")
    if result["problems"]:
        for p in result["problems"]:
            common.say(f"  {p}")
        hint = f" (catalogues missing: {', '.join(missing)}; pass --props-spec)" if missing else ""
        raise common.Failure(f"house dressing: {len(result['problems'])} problems{hint}")
    common.say(f"house dressing: {len(result['rooms'])} rooms hold (bounds, overlaps, stations, the capsule's paths); "
               f"{report.as_posix()}")
    return result["rooms"]


def lab_props(args, found: dict, dressing: dict) -> tuple[dict, dict, str | None]:
    """--props-dir, --props-map and --before (bake only): the prop table and dressing with the lab props swapped in and
    the extras added (house_bake_props), and the after rows' label."""
    if not args.bake or (args.props_map and not args.props_dir):
        raise common.Failure("--props-dir and --before need --bake; --props-map needs --props-dir")
    if args.before and (not args.review or args.grid or args.diag or args.sheen):
        raise common.Failure("--before needs --review and a preset bake (no --grid, --diag or --sheen)")
    if not args.props_dir:
        return found, dressing, None
    if not args.props_dir.is_dir():
        raise common.Failure(f"--props-dir: no folder {args.props_dir.as_posix()}")
    try:
        mapping = house_bake_props.load_map(args.props_map)
        known = {r["id"] for rep in dressing.values() for r in rep["resolved"]}
        got = house_bake_props.swap(found, known, args.props_dir, mapping)
        dressing = house_bake_props.add_extras(dressing, mapping["extra"])
    except (OSError, ValueError) as e:
        raise common.Failure(str(e)) from None
    common.say(f"  props-dir {args.props_dir.as_posix()}: {len(got['swapped'])} props swapped "
               f"({', '.join(got['swapped'])}), {len(got['extra'])} extra pieces")
    return got["found"], dressing, mapping["label"] or args.props_dir.name


def prop_glbs(data: dict, dressing: dict) -> dict:
    """prop id -> its GLB under the raw folder (the first of house.toml's prop_dirs that has it)."""
    raw = common.raw_dir()
    ids = {r["id"] for rep in dressing.values() for r in rep["resolved"]}
    found = {}
    for pid in sorted(ids):
        for d in data["settings"].get("prop_dirs", []):
            glb = raw / d / f"{pid}.glb"
            if glb.is_file():
                found[pid] = glb
                break
    return found


def cell_size(data: dict) -> float | None:
    """house.toml's [merge] cell (#185): the merged shell's and the batched dressing's grid cell in metres, or None
    ("room" or missing: one merged mesh per room, class and group, as #107 shipped)."""
    v = data["settings"].get("merge", {}).get("cell", "room")
    if v in ("room", None):
        return None
    v = float(v)
    if v <= 0:
        raise ValueError(f"house.toml [merge] cell must be a positive number of metres or \"room\", not {v}")
    return v


def merger(data: dict, found: dict | None = None, out: Path | None = None, kit_res: str | None = None,
           prop_res: str | None = None):
    """The merged shell's callable for house_layout.write_scenes (#107), or None without the kit's pieces.json: per room
    the static kit pieces (not house.toml's [merge] keep, which the game moves or opens) of each class (floor_*,
    ceiling_*, the rest: shell) merged into one GLB (house_merge.merge) under _house_bake.MERGED, named
    <class>_m_<level>_<room> (staged as kit_<name>, so the bake's flat rule and UV2 table find it); a class of one
    piece stays an instance. The callable's `uv2` (name -> UV2 units per metre) goes to MERGED/uv2.json.
    Its `batch` (the batched dressing, #107): per room and group (Dressing, Detail, Fixtures) the static props (found:
    prop id -> GLB; not a station, not house.toml's [merge] keep_props) merged into one GLB batch_<level>_<room>_<group>
    (one surface per material, staged as prop_<name>, which Godot unwraps for the bake like any prop); each prop
    instance stays with its colliders, name and metadata, its visual nodes hidden.
    With house.toml's [merge] shadow_proxy (#185) each merged GLB of two or more casting surfaces gets its shadow
    proxy <name>_shadow (house_merge.shadow; add entry `<node>_shadow` after the GLB's own); the callable's `cast`
    maps both res paths to their override lines (the merged mesh casts no shadow, the proxy only casts).
    `out`, `kit_res` and `prop_res` (the export's, #107) put the GLBs elsewhere and name their res:// paths ({id}: the
    GLB's stem); the callable's `files` maps each written GLB's stem to its path. A batch's "add" entries carry the
    stem as a third item (house_dressing.scene_nodes' overrides key)."""
    kit = common.raw_dir() / data["settings"]["kit_dir"]
    if not (kit / "pieces.json").is_file():
        return None
    uv2 = house_bake.uv2_table(json.loads((kit / "pieces.json").read_text(encoding="utf-8")))
    keep = set(data["settings"].get("merge", {}).get("keep", []))
    cell = cell_size(data)
    out = Path(out) if out else _house_bake.MERGED
    kit_res = kit_res or data["settings"]["kit_res"]
    prop_res = prop_res or data["settings"]["prop_res"]
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.glb"):
        old.unlink()
    visuals: dict = {}
    shadow = bool(data["settings"].get("merge", {}).get("shadow_proxy", False))

    def proxy(name: str, res: str, add: list, entry: tuple) -> None:
        """#185: the merged GLB's shadow proxy (house_merge.shadow) beside it, its add entry after the GLB's own, and
        both res paths' override lines in merge.cast (res path -> [(sub-node, lines)])."""
        add.append(entry)
        if not shadow:
            return
        got = house_merge.shadow(out / f"{name}.glb", out / f"{name}_shadow.glb")
        if got is None:
            return
        lines = house_merge.cast_lines(got)
        merge.files[f"{name}_shadow"] = out / f"{name}_shadow.glb"
        merge.cast[res.format(id=name)] = lines["merged"]
        merge.cast[res.format(id=f"{name}_shadow")] = lines["proxy"]
        merge.proxies += 1
        add.append((f"{entry[0]}_shadow", res.format(id=f"{name}_shadow"))
                   + ((f"{name}_shadow",) if len(entry) > 2 else ()))

    def visual_nodes(glb) -> list:
        if glb not in visuals:
            visuals[glb] = sorted({p["node"] for p in house_merge.visual(Path(glb))})
        return visuals[glb]

    def merge(level: str, rid: str, pieces: list[dict]) -> dict:
        by: dict[str, list[dict]] = {}
        for p in pieces:
            if p["id"] in keep or not (kit / f"{p['id']}.glb").is_file():
                continue
            cls = next((c for c in ("floor", "ceiling") if p["id"].startswith(c + "_")), "shell")
            by.setdefault(cls, []).append({**p, "glb": kit / f"{p['id']}.glb", "class": cls,
                                           "uv2_per_m": uv2.get(p["id"])})
        hide, add = set(), []
        for cls, items in sorted(by.items()):
            if len(items) < 2:
                continue
            for it in items:  # the scene hides only the node named after the piece: a second mesh would draw twice
                if visual_nodes(it["glb"]) != [it["id"]]:
                    raise ValueError(f"{it['glb']}: a merged kit piece's visual nodes must be [{it['id']!r}], not "
                                     f"{visual_nodes(it['glb'])} (list the piece in house.toml's [merge] keep)")
            for c, its in house_merge.cells(items, cell):  # a cell of one piece stays an instance
                if len(its) < 2:
                    continue
                name = f"{cls}_m_{level}_{rid}" + (f"_{c}" if c else "")
                rec = house_merge.merge(its, out / f"{name}.glb")
                merge.files[name] = out / f"{name}.glb"
                merge.uv2[name] = rec["classes"][cls]["uv2_per_m"]
                hide |= {it["node"] for it in its}
                proxy(name, kit_res, add, (f"merged_{cls}" + (f"_{c}" if c else ""), kit_res.format(id=name)))
        merge.hidden += len(hide)
        return {"hide": hide, "add": add, "cast": merge.cast}

    keep_props = set(data["settings"].get("merge", {}).get("keep_props", []))

    def batch(level: str, rid: str, parent: str, items: list) -> dict:
        its, hide = [], {}
        for r, node in items:
            glb = (found or {}).get(r["id"])
            if r.get("station") or r["id"] in keep_props or glb is None:
                continue
            names = visual_nodes(glb)
            if not names or not all(re.fullmatch(r"[A-Za-z0-9_]+", v or "") for v in names):
                continue
            its.append({"glb": Path(glb), "transform": house_dressing.tf_yaw(r["yaw"], *r["at"]), "class": "props",
                        "uv2_per_m": None, "node": node})
            hide[node] = names
        out_hide, add = {}, []
        for c, group in house_merge.cells(its, cell):  # a cell of one prop keeps its instance drawing
            if len(group) < 2:
                continue
            name = f"batch_{level}_{rid}_{parent.lower()}" + (f"_{c}" if c else "")
            house_merge.merge(group, out / f"{name}.glb")
            merge.files[name] = out / f"{name}.glb"
            merge.batched.append(name)
            merge.props += len(group)
            out_hide.update({it["node"]: hide[it["node"]] for it in group})
            proxy(name, prop_res, add, (f"batch_{parent.lower()}" + (f"_{c}" if c else ""), prop_res.format(id=name),
                                        name))
        return {"hide": out_hide, "add": add, "cast": merge.cast}
    merge.uv2, merge.hidden, merge.batch, merge.batched, merge.props, merge.files = {}, 0, batch, [], 0, {}
    merge.cast, merge.proxies = {}, 0
    return merge


def stage(data: dict, summary: dict, props: dict | None = None) -> list[str]:
    """Stages the pieces and props the scenes use (the kit folder, the prop GLBs), imports them headless; returns the
    import's error lines."""
    kit = common.raw_dir() / data["settings"]["kit_dir"]
    names = {pid: f"kit_{pid}" for pid in summary["pieces"]}
    merged = {Path(r).stem: _house_bake.MERGED / f"{Path(r).stem[4:]}.glb" for r in summary.get("merged", [])}
    batched = {f"prop_{g.stem}": g for g in _house_bake.MERGED.glob("batch_*.glb")} if merged else {}
    missing = [pid for pid in names if not (kit / f"{pid}.glb").is_file()]
    if missing:
        raise common.Failure(f"no {', '.join(sorted(missing))} in {kit.as_posix()} (build the kit first)")
    props = props or {}
    _godot.clear_staged(set(names.values()) | set(merged) | set(batched) | {f"prop_{pid}" for pid in props})
    for pid, name in names.items():
        _godot.stage(kit / f"{pid}.glb", name)
    for name, glb in merged.items():
        _godot.stage(glb, name, house_bake.SHADOW_IMPORT if name.endswith("_shadow") else house_bake.KIT_IMPORT)
    for pid, glb in props.items():
        _godot.stage(glb, f"prop_{pid}")
    for name, glb in batched.items():
        _godot.stage(glb, name, house_bake.SHADOW_IMPORT if name.endswith("_shadow") else None)
    errors = [line for line in _godot.import_project() if "ERROR" in line]
    for line in errors[:10]:
        common.say(f"  import: {line}")
    return errors


def kit_pack(data: dict) -> dict:
    """The kit's `set` material for walk.gd (kit_materials.gd `make`): its textures under the kit folder and the layers'
    roughness and normal strength; empty when the spec has no three-layer pack (the plain imported paint then)."""
    spec = data["spec"]
    mats = [spec["materials"][m] for m in spec.get("packs", {}).get("set", {}).get("layers", [])]
    if len(mats) != 3:
        return {}
    return {"textures": (common.raw_dir() / data["settings"]["kit_dir"] / "textures").as_posix(),
            "roughness": [m["roughness"] for m in mats], "normal_strength": [m["normal_strength"] for m in mats]}


def walk(data: dict, folder: Path, routes: dict | None = None, errors: list[str] = (),
         dressing: dict | None = None, lights: dict | None = None) -> int:
    """Runs godot/house/walk.gd in a window off-screen (pictures need one) on the staged house: every doorway of the
    ground and upper floors and every flight, walked by a 1.36 m capsule; the design doc's routes (routes.toml) at their
    speed, judged against the doc's times (also into tools/out/house/routes.json); the stills, the plan, sheet.png and
    the exterior at dusk (exterior.png); draw calls per view. With a dressing: c2 stand-in lamps at its fixtures, one
    shot per dressed room from its door and rooms.png (house_dressing.review_request), and per room the view's draw
    calls and the dressing's triangles. With `lights` (lights.toml): per still and room view the budget's draw calls,
    baked and High (house_bake.walk_count; draw_calls.json and .md in `folder`, a WARN per view over [budget]; #185)."""
    folder.mkdir(parents=True, exist_ok=True)
    req = common.OUT / "house" / "walk_request.json"
    request = house_layout.walk_request(data)
    request["walks"] += house_routes.walks(data, request, routes or {})
    request["pack"] = kit_pack(data)  # the kit's material, which carries the rooms' wall paints
    if dressing:  # the walked levels' rooms; the basement's have their own review (--basement)
        walked = {r["id"] for lv in data["levels"] if lv["level"] in house_layout.WALK_LEVELS for r in lv["rooms"]}
        request.update(house_dressing.review_request(data, {rid: r for rid, r in dressing.items() if rid in walked}))
    if lights:
        request["count"] = house_bake.walk_count(lights, house_lights.plan(lights, data))
    for name in request["closed"]:
        common.say(f"  not walked (closed kit leaf): {name}")
    req.write_text(json.dumps(request, indent=1), encoding="utf-8", newline="\n")
    (folder / "walk.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", _godot.PROJECT, "--audio-driver", "Dummy", "-s", WALK, "--",
                                  req.as_posix(), folder.as_posix()], (1600, 900), WALK_TIMEOUT)
    if code != 0 or not (folder / "walk.json").is_file():
        tail = "\n".join(output.splitlines()[-20:])
        raise common.Failure(f"walk.gd failed (exit code {code}):\n{tail}")
    result = json.loads((folder / "walk.json").read_text(encoding="utf-8"))
    tolerance = float((routes or {}).get("tolerance_s", 1.0))
    for w, r in zip(request["walks"], result["walks"]):
        if w["kind"] == "route":
            r.update(house_routes.judge(w, r, tolerance))
            common.say(f"  route {w['name']}: {r['seconds']} s walked at {w['speed']:g} m/s, the doc {r['doc_s']:g} s "
                       f"({r['delta_s']:+g} s, {'within' if r['time_ok'] else 'OVER'} {tolerance:g} s), {r['plan_m']:g} m on the "
                       f"plan, the doc {r['doc_m']:g} m")
    (folder / "walk.json").write_text(json.dumps(result, indent=1), encoding="utf-8", newline="\n")
    ROUTES_OUT.write_text(json.dumps([dict(r, name=w["name"]) for w, r in zip(request["walks"], result["walks"])
                                      if w["kind"] == "route"], indent=1), encoding="utf-8", newline="\n")
    failed = [w for w in result["walks"] if not w["pass"]] + ([] if result["control"]["pass"] else [result["control"]])
    for w in result["walks"] + [result["control"]]:
        mark = "ok  " if w["pass"] else "FAIL"
        common.say(f"  {mark} {w['name']}: {'arrived' if w['arrived'] else 'stopped'} at {w['end']} "
                   f"({w['reached']}/{w['of']} points, {w['seconds']} s)"
                   + (f"; the doc {w['doc_s']} s, {'within' if w['within_1s'] else 'NOT within'} 1 s" if "within_1s" in w else ""))
    for name, info in result["shots"].items():
        common.say(f"  {name}: {info['draw_calls']} draw calls, {info['objects']} objects, {info['primitives']} primitives")
    for name, info in result.get("rooms", {}).items():
        common.say(f"  {name}: {info['draw_calls']} draw calls ({info.get('dressing_draw_calls')} the dressing's), "
                   f"{info['primitives']} primitives in view; dressing {info['dressing_meshes']} meshes, "
                   f"{info['dressing_triangles']} triangles")
    if lights and result.get("counts"):  # the budget per walk view, as --count reports it (#185)
        table, names = house_bake.walk_table(result["counts"])
        _house_bake.report(lights.get("budget", {}), table, names, folder)
    for line in house_dressing.swatch_report(result.get("swatches", [])):
        common.say(f"  swatch {line}")
    common.say(f"  {result['instances']['mesh_instances']} mesh instances, {result['instances']['static_bodies']} bodies; "
               f"sheet {(folder / 'sheet.png').as_posix()}"
               + (f", the second floor {(folder / 'upper.png').as_posix()}" if (folder / "upper.png").is_file() else ""))
    if failed or errors:
        common.bad(f"house walk: {len(failed)} walks failed, {len(errors)} import errors")
        return 1
    common.ok(f"house walk: {len(result['walks'])} walks with a {2 * result['radius_m']:g} m capsule, the 1.5 m control stops")
    return 0


def check_basement(data: dict, layouts: Path, extra) -> None:
    """The basement's dead ends and sight lines (house_basement, art #78) into tools/out/house/basement.json; a dead end
    with more than one door, or a switch out of sight from a door of its room, fails the command."""
    st = data["settings"]
    folder = Path(layouts) / st.get("dressing_dir", "dressing")
    if not any(lv["level"] == house_basement.LEVEL for lv in data["levels"]):
        return
    dressings = house_dressing.load(folder) if folder.is_dir() else {}
    cat = house_dressing.catalogue(house_dressing.spec_paths(st, extra=extra))
    ends = house_basement.dead_ends(data)
    hall = house_basement.hall_sight(data, dressings, cat)
    switches = house_basement.switch_sight(data, dressings, cat)
    report = common.OUT / "house" / "basement.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"dead_ends": {k: {"doors": d, "stairs": s} for k, (d, s) in ends.items()},
                                  "hall_sight": hall, "switch_sight": switches}, indent=1),
                      encoding="utf-8", newline="\n")
    problems = [f"dead end {k}: {d} doors, {s} stairs (one door, no stairs)" for k, (d, s) in ends.items()
                if (d, s) != (1, 0)]
    problems += [f"{r['line']}: blocked by {r['nearest']}" for r in switches if r["clear"] is not None and r["clear"] <= 0]
    for r in hall:
        common.say(f"  sight {r['line']}: {r['length']:g} m, clear by {r['clear']} m ({r['nearest']})")
    if problems:
        for p in problems:
            common.say(f"  {p}")
        raise common.Failure(f"house basement: {len(problems)} problems")
    blocked = [r["line"] for r in hall if r["clear"] is not None and r["clear"] <= 0]
    common.say(f"house basement: {len(ends)} dead ends with one door each; {len(switches)} switch lines clear; "
               f"hall sight lines blocked: {', '.join(blocked) or 'none'}; {report.as_posix()}")
