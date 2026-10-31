"""`lobby`: the lobby hall (art #356, docs/lobby.md): checks layouts/lobby/hall.toml with art #263's ship in place;
--build the grey massing in headless Blender, one GLB per piece with glTF-Validator; --godot the headless import
(sizes, colliders), a capsule walk and the doors' and the corridor's end's proof; --shoot DIR the review views beside
concepts A and C, a top view, a spawn's eye and the close-ups, in an off-screen window; --grid DIR the taste grid (the
colour schemes, [look.schemes], in the layout's grid views); --earth-tex the window's Earth textures from NASA's
sources (step 3b); --earth-grid DIR the Earth variants ([earth.variants]) in [earth] grid's views."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .. import blender, common, lobby_layout
from . import _export, _godot

NAME = "lobby"
HELP = ("the lobby hall (layouts/lobby/hall.toml): check it with the ship in place; --build the grey massing GLBs; "
        "--godot import, colliders, walk, doors; --shoot DIR the review views off-screen; --grid DIR the colour schemes")
BUILD_SCRIPT = blender.SCRIPTS / "lobby_build.py"
EARTH_SCRIPT = blender.SCRIPTS / "lobby_earth_tex.py"
GODOT_SCRIPT = "res://lobby/hall.gd"
BUILD_TIMEOUT = 600
GODOT_TIMEOUT = 300
VIDEO_SCRIPT = blender.SCRIPTS / "ship_video.py"   # the ship's encoder (art #263), only run, never changed
VIDEO_TIMEOUT = 1500
VIEW_SIZE = (1920, 1080)
SIZE_TOL_M = 0.01


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--check", action="store_true", help="only the layout's check and its text plan (the default)")
    parser.add_argument("--build", action="store_true", help="build the hall's pieces in headless Blender")
    parser.add_argument("--godot", action="store_true", help="import headless: sizes, colliders, the walk, the doors")
    parser.add_argument("--shoot", type=Path, metavar="DIR", help="shoot the review views into DIR (off-screen)")
    parser.add_argument("--grid", type=Path, metavar="DIR", help="shoot the colour schemes' grid into DIR (off-screen)")
    parser.add_argument("--earth-tex", action="store_true", help="scale NASA's Earth sources to the window's textures")
    parser.add_argument("--earth-grid", type=Path, metavar="DIR", help="shoot the Earth variants' grid into DIR")
    parser.add_argument("--light-grid", type=Path, metavar="DIR", help="shoot the light moods' grid into DIR (step 4)")
    parser.add_argument("--ship-grid", type=Path, metavar="DIR",
                        help="step 5a2: the ship's light sets ([light.ship.sets]) in [light.ship] grid's views into DIR")
    parser.add_argument("--video", type=Path, metavar="DIR", help="the eye-height walk-through MP4 into DIR (step 4)")
    parser.add_argument("--distance-grid", type=Path, metavar="DIR",
                        help="step 4c: the Earth object's distances D1-D3 from [earth] distance_views into DIR")
    parser.add_argument("--earth-video", type=Path, metavar="DIR",
                        help="step 4c: one short MP4 per Earth distance ([earth] video_keys) into DIR")
    parser.add_argument("--out", type=Path, help="the pieces' folder (default <raw>/<layout raw_dir>/pieces)")


def raw(layout: dict) -> Path:
    return common.raw_dir() / layout["raw_dir"]


def ship_scene(layout: dict) -> tuple[list, list, dict, dict]:
    """The ship's kept placements (plan), the dropped ids, the ship's build report and its layout."""
    ship = lobby_layout.ship_layout_data()
    report = lobby_layout.ship_report(layout)
    ids = {p["id"] for p in ship["pieces"]}
    unknown = sorted(set(layout["ship"]["drop"]) - ids)
    if unknown:
        raise common.Failure(f"lobby: [ship] drop names no ship piece: {', '.join(unknown)}")
    return lobby_layout.ship_place(layout, ship), layout["ship"]["drop"], report, ship


def run(args: argparse.Namespace) -> int:
    layout = lobby_layout.load()
    place, drop, report, _ship = ship_scene(layout)
    fp = lobby_layout.footprint(layout, lobby_layout.hull_outline(layout["ship"]["hull"]), report, place)
    problems = lobby_layout.check(layout, fp)
    n = lobby_layout.ship_numbers(layout, fp)
    gaps = lobby_layout.wall_gaps(layout, fp)
    spawn = min(lobby_layout.poly_dist(fp, (x, layout["floor"]["spawns_z"])) for x in layout["floor"]["spawns_x"])
    r, cz = lobby_layout.arc(layout)
    common.say(f"lobby hall v{layout['version']}: window arc r {r:.3f} m (centre z {cz:.3f}); ship nose z {n['nose_z']:.2f}, "
               f"aft z {n['aft_z']:.2f}, middle z {n['middle_z']:.2f}, half span {n['half_span']:.2f} m; "
               f"{len(place)} ship placements, {len(drop)} clearing pieces dropped")
    common.say(f"  spawns to the ship {spawn:.2f} m; ship to " + ", ".join(f"{k} {v:.2f}" for k, v in gaps.items()))
    pk = layout["ship"].get("package")
    if pk:   # step 4c: the closed ship of art #263's package, its pointed jaw nose shut, measured against the same rules
        cf = lobby_layout.closed_footprint(layout, fp, place)
        cn = lobby_layout.ship_numbers(layout, cf)
        cg = lobby_layout.wall_gaps(layout, cf)
        cs = min(lobby_layout.poly_dist(cf, (x, layout["floor"]["spawns_z"])) for x in layout["floor"]["spawns_x"])
        closed = [q for q in lobby_layout.check(layout, cf) if q.startswith(("ship:", "spawn", "ring:"))]
        common.say(f"  the closed ship ({pk['dir']}, nose {', '.join(pk['nose'])} shut): nose z {cn['nose_z']:.2f}, aft z "
                   f"{cn['aft_z']:.2f}; spawns {cs:.2f} m; " + ", ".join(f"{k} {v:.2f}" for k, v in cg.items())
                   + (f"; FAILS: {'; '.join(closed)}" if closed else "; holds"))
        if pk["use"]:   # step 5a: the package's ship.tscn stands in the lobby; the ring and the plan follow its footprint
            problems += [f"the closed ship: {q}" for q in closed]
            fp, n = cf, cn
            rr = layout["floor"]["ring_r"]
            common.say(f"  the package instance is used ([ship.package] use = true): the ring centred at z {n['middle_z']:.2f} "
                       f"(r {rr}: z {n['middle_z'] - rr:.2f}..{n['middle_z'] + rr:.2f}); the spawns at z {layout['floor']['spawns_z']}")
        elif closed:
            common.say("  the package instance is not used ([ship.package] use = false); the pieces of pieces_dir stand in, their jaws shut")
    for p in problems:
        common.say(f"  {p}")
    if problems:
        raise common.Failure(f"lobby: {len(problems)} layout problems")
    plan = raw(layout) / "plan" / "plan.txt"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(lobby_layout.ascii_plan(layout, fp), encoding="utf-8", newline="\n")
    common.ok(f"lobby: hall, arc, ribs, arch, doors, spawns and the ship's place hold; plan {plan.as_posix()}")
    out = (args.out or raw(layout) / "pieces").resolve()
    if args.earth_tex:
        earth_tex(layout)
    if args.build:
        code = build(layout, out, n["middle_z"])
        if code:
            return code
    if args.godot:
        code = godot_check(layout, out, place, report, raw(layout) / "godot")
        if code:
            return code
    if args.shoot:
        code = shoot(layout, out, place, args.shoot.resolve())
        if code:
            return code
    if args.grid:
        code = shoot(layout, out, place, args.grid.resolve(), grid=True)
        if code:
            return code
    if args.earth_grid:
        code = shoot(layout, out, place, args.earth_grid.resolve(), grid="earth")
        if code:
            return code
    if args.light_grid:
        code = shoot(layout, out, place, args.light_grid.resolve(), grid="light")
        if code:
            return code
    if args.distance_grid:
        code = shoot(layout, out, place, args.distance_grid.resolve(), grid="distance")
        if code:
            return code
    if args.ship_grid:
        code = shoot(layout, out, place, args.ship_grid.resolve(), grid="ship")
        if code:
            return code
    if args.earth_video:
        e = layout["earth"]
        vd = dict(layout["video"], keys=e["video_keys"], max_mb=e["video_max_mb"])
        for did in e["distances"]:
            code = video(layout, out, place, args.earth_video.resolve(), vd=vd, distance=did, name=f"earth_{did}.mp4")
            if code:
                return code
    if args.video:
        return video(layout, out, place, args.video.resolve())
    return 0


# --- the Earth (step 3b) -------------------------------------------------------------------------------------------
def earth_tex(layout: dict) -> None:
    """NASA's raw sources scaled to [earth] size in headless Blender into [earth] tex_dir (the sources only read)."""
    e = layout["earth"]
    src = common.raw_dir() / e["src_dir"]
    maps = {k: (src / f).as_posix() for k, f in e["maps"].items()}
    missing = [m for m in maps.values() if not Path(m).is_file()]
    if missing:
        raise common.Failure(f"lobby --earth-tex: missing sources {', '.join(missing)}")
    out = common.raw_dir() / e["tex_dir"]
    request = common.OUT / "lobby" / "earth_request.json"
    request.parent.mkdir(parents=True, exist_ok=True)
    request.write_text(json.dumps({"size": e["size"], "quality": e["quality"], "out": out.as_posix(), "maps": maps},
                                  indent=1), encoding="utf-8", newline="\n")
    blender.run_script(EARTH_SCRIPT, ["--request", str(request)], timeout=BUILD_TIMEOUT)
    common.ok(f"lobby --earth-tex: {len(maps)} textures {e['size'][0]} x {e['size'][1]} -> {out.as_posix()}")


def _dir(azimuth: float, elevation: float) -> list[float]:
    """A direction from [azimuth from south (+z) toward east (+x), elevation] in degrees."""
    a, el = math.radians(azimuth), math.radians(elevation)
    return [math.sin(a) * math.cos(el), math.sin(el), math.cos(a) * math.cos(el)]


def earth_request(layout: dict, vid: str, distance: str | None = None) -> dict:
    """What hall.gd hands earth_sky.gdshader for one variant: the textures' paths, the look and the variant's numbers."""
    e = layout["earth"]
    tex = common.raw_dir() / e["tex_dir"]
    files = {k: (tex / f"earth_{k}.jpg").as_posix() for k in e["maps"]}
    missing = [f for f in files.values() if not Path(f).is_file()]
    if missing:
        raise common.Failure(f"the Earth's textures are missing (lobby --earth-tex): {', '.join(missing)}")
    v = e["variants"][vid]
    out = {"id": vid, "title": v["title"], "earth": {
        "textures": files, "look": e["look"], "centre": _dir(*v["centre"]), "radius_deg": v["radius_deg"],
        "subpoint": v["subpoint"], "roll_deg": v["roll_deg"], "sun": _dir(*v["sun"]), "sun_energy": v["sun_energy"],
        "stars": v["stars"]}}
    did = distance or e.get("distance")
    if did:   # step 4c: the Earth as an object at a finite distance (earth_object.gdshader)
        out["earth"]["object"] = lobby_layout.earth_object(layout, vid, did)
        out.update({"id": did, "title": e["distances"][did]["title"]} if distance else {})
    return out


def look_request(layout: dict, scheme: str) -> dict:
    """The look Godot applies to the hall's materials: one scheme's resolved materials (lobby_layout.look_materials)."""
    return {"id": scheme, "title": layout["look"]["schemes"][scheme]["title"],
            "mats": lobby_layout.look_materials(layout, scheme)}


# --- the light (step 4) ---------------------------------------------------------------------------------------------
def ship_light(layout: dict, sid: str | None = None) -> dict | None:
    """Step 5a2: one of [light.ship]'s sets for hall.gd (the layout's `set` by default): its numbers, the key's and the
    rim's directions as vectors and the ship's own probe box; None without a [light.ship]."""
    sh = layout["light"].get("ship")
    if sh is None:
        return None
    sid = sid or sh["set"]
    s = dict(sh["sets"][sid])
    for k in ("key", "rim", "back", "bounce"):
        s[f"{k}_dir"] = _dir(*s[f"{k}_dir"])
    s.update({"id": sid, "probe": sh["probe"]})
    return s


def light_request(layout: dict, mood: str, trial: str | None = None, ship: str | None = None) -> dict:
    """One mood's rig for hall.gd: its numbers, the directions, and every lamp's place in the lobby frame (the pendants'
    x and z (hall.gd finds each lens's height in the vault's mesh), the strips before the pilasters' faces, the red
    omnis before the door lamps, the corridor's omnis) and the reflection probes."""
    li, h = layout["light"], layout["hall"]
    m = dict(li["moods"][mood])
    if trial:   # step 4b's grid: a trial's numbers over the mood
        m.update(li["trials"][trial])
        m["title"] = f"{mood}+{trial} " + m["title"]
    title = m.pop("title")
    m["earth_dir"], m["dawn_dir"] = _dir(*m["earth_dir"]), _dir(*m["dawn_dir"])
    face = {"W": (h["x0"] + h["pilaster_d"] + li["strip_off"], 1), "E": (h["x1"] - h["pilaster_d"] - li["strip_off"], -1)}
    strips = []
    for side, u in lobby_layout.pilasters(layout):
        if side == "N":
            strips.append([u, li["strip_y"], h["zN"] + h["pilaster_d"] + li["strip_off"]])
        else:
            strips.append([face[side][0], li["strip_y"], u])
    doors = []
    for _did, side, u in layout["door"]["doors"]:
        y = layout["door"]["lamp"]
        if side == "N":
            doors.append([u, y, h["zN"] + li["door_off"]])
        else:
            doors.append([h["x0"] + li["door_off"] if side == "W" else h["x1"] - li["door_off"], y, u])
    m.update({"pendants": [[x, z] for x in li["pendants_x"] for z in li["pendants_z"]], "strips": strips,
              "doors": doors, "corridor": li["corridor"], "probes": li["probes"],
              "window": li.get("window", []), "window_tilt": li.get("window_tilt", 0.0),
              "fixtures_below": li["fixtures_below"], "earth_specular": li["earth_specular"],
              "window_specular": li["window_specular"]})
    if "wash" in li:   # step 5a3: the north wall's wash behind the ship
        m["wash"] = li["wash"]
    sl = ship_light(layout, ship)
    if sl is not None:
        m["ship"] = sl
    if ship:   # step 5a2's grid: one ship set over the mood
        return {"id": ship, "title": f"{mood}+{ship} {li['ship']['sets'][ship]['title']}", "light": m}
    return {"id": trial or mood, "title": title, "light": m}


def video(layout: dict, out: Path, place: list, folder: Path, vd: dict | None = None, distance: str | None = None,
          name: str = "walkthrough.mp4") -> int:
    """The eye-height walk-through (step 4): hall.gd renders every frame off-screen (mode "video", the layout's mood),
    headless Blender encodes them with the ship's ship_video.py under max_mb, and the frames are deleted."""
    import shutil
    req, staged, _want = scene_request(layout, out, place, lobby_layout.ship_report(layout))
    vd = vd or layout["video"]
    req.update({"mode": "video", "background": layout["review"]["background"], "video": vd,
                "watchdog_s": VIDEO_TIMEOUT - 60, "light": light_request(layout, layout["light"]["mood"])["light"]})
    if "earth" in layout:
        req["earth"] = earth_request(layout, layout["earth"]["variant"], distance)["earth"]
    errors = _stage(staged)
    work = folder / "work"
    shutil.rmtree(work / "frames", ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "lobby" / "video_request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (work / "video.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", GODOT_SCRIPT, "--",
                                  path.as_posix(), work.as_posix()], tuple(vd["size"]), VIDEO_TIMEOUT)
    if code != 0 or not (work / "video.json").is_file():
        raise common.Failure(f"hall.gd video failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
    info = json.loads((work / "video.json").read_text(encoding="utf-8"))
    clip = folder / name
    clip.unlink(missing_ok=True)
    blender.run_script(VIDEO_SCRIPT, ["--frames", str(work / "frames"), "--out", str(clip), "--fps", str(vd["fps"]),
                                      "--max-mb", str(vd["max_mb"])], timeout=VIDEO_TIMEOUT)
    if not clip.is_file():
        raise common.Failure(f"ship_video.py wrote no {clip}")
    shutil.rmtree(work / "frames", ignore_errors=True)
    mb = clip.stat().st_size / 2 ** 20
    if errors or mb > vd["max_mb"]:
        common.bad(f"lobby --video: {mb:.1f} MB (max {vd['max_mb']}), {len(errors)} import errors")
        return 1
    common.ok(f"lobby --video: {clip.as_posix()} {vd['size'][0]}x{vd['size'][1]}, {info['seconds']:.1f} s, "
              f"{info['frames']} frames, {mb:.1f} MB (rendered in {info['render_s']:.0f} s, GPU median "
              f"{info['gpu_ms']:.2f} ms)")
    return 0


# --- build ---------------------------------------------------------------------------------------------------------
def build(layout: dict, out: Path, ring_z: float) -> int:
    out.mkdir(parents=True, exist_ok=True)
    request = common.OUT / "lobby" / "build_request.json"
    request.parent.mkdir(parents=True, exist_ok=True)
    request.write_text(json.dumps({"layout": layout, "arc": list(lobby_layout.arc(layout)), "ring_z": ring_z,
                                   "look": lobby_layout.look_materials(layout, layout["look"]["scheme"])}, indent=1),
                       encoding="utf-8", newline="\n")
    blender.run_script(BUILD_SCRIPT, ["--request", str(request), "--out", str(out)], timeout=BUILD_TIMEOUT)
    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    reports = out / "reports"
    reports.mkdir(exist_ok=True)
    bad = []
    for pid, info in report["pieces"].items():
        passed, line = _export.verdict(_export.validate(Path(info["glb"]), reports / f"{pid}.json"))
        common.say(f"  {pid}: {info['triangles']} triangles; {line}")
        if not passed:
            bad.append(pid)
    if bad:
        common.bad(f"lobby --build: {', '.join(bad)} fail glTF-Validator")
        return 1
    tris = sum(i["triangles"] for i in report["pieces"].values())
    common.ok(f"lobby --build: {len(report['pieces'])} GLBs, {tris} triangles, glTF-Validator clean -> {out.as_posix()}")
    return 0


# --- Godot ---------------------------------------------------------------------------------------------------------
def scene_request(layout: dict, out: Path, place: list, ship_report: dict) -> tuple[dict, dict[str, Path], dict]:
    """The pieces (the hall's and the ship's), their placements in the lobby, the GLBs to stage and Blender's bounds."""
    hall = json.loads((out / "build_report.json").read_text(encoding="utf-8"))["pieces"]
    missing = [p["id"] for p in layout["pieces"] if p["id"] not in hall]
    if missing:
        raise common.Failure(f"pieces not built (lobby --build): {', '.join(missing)}")
    ship_dir = common.raw_dir() / layout["ship"]["pieces_dir"]
    pk = layout["ship"].get("package") or {}
    ship_ids = [] if pk.get("use") else sorted({p[0] for p in place})
    staged = {f"lobby_{p['id']}": out / f"{p['id']}.glb" for p in layout["pieces"]}
    staged.update({f"ship_{pid}": ship_dir / f"{pid}.glb" for pid in ship_ids})
    pieces = {p["id"]: f"res://import/lobby_{p['id']}.glb" for p in layout["pieces"]}
    pieces.update({f"ship_{pid}": f"res://import/ship_{pid}.glb" for pid in ship_ids})
    ox, oy, oz = layout["ship"]["origin"]
    places = [[pid, at, yaw] for pid, at, yaw in layout["place"]]
    places += [["door", *door_place(layout, d)] for d in layout["door"]["doors"]]
    places += [[f"ship_{pid}", [at[0] + ox, at[2] + oy, at[1] + oz], yaw] for pid, at, yaw in place if pid in ship_ids]
    bounds = {p["id"]: hall[p["id"]]["bounds"] for p in layout["pieces"]}
    bounds.update({f"ship_{pid}": ship_report[pid]["bounds"] for pid in ship_ids})
    collide = [p["id"] for p in layout["pieces"] if p["collide"]]
    req = {"pieces": pieces, "place": places}
    if pk.get("use"):   # step 5a: the ship's package instead of its pieces (hall.gd _ship_package)
        req["ship_package"] = {"scene": stage_package(pk), "at": [ox, oy, oz], "free": pk.get("free", []),
                              "keep": pk["keep"]}
    return req, staged, {"bounds": bounds, "collide": collide}


PKG_DIR = "ship_pkg"
PKG_TEXT = {".tscn", ".tres", ".gdshader", ".gdshaderinc", ".import", ".gd"}


def stage_package(pk: dict) -> str:
    """Step 5a: copies the files art #263's package.json lists into godot/import/ship_pkg/ (ignored by git), its text
    files' res://assets/ and res://levels/ rewritten under res://import/ship_pkg/; only changed files are written, so a
    second run imports nothing new. The package itself is only read. Returns the level scene's res:// path."""
    src = common.raw_dir() / pk["dir"]
    dst = _godot.IMPORT_DIR / PKG_DIR
    meta = json.loads((src / "package.json").read_text(encoding="utf-8"))
    prefix = f"res://import/{PKG_DIR}/"
    for rel in meta["files"]:
        if rel == "package.json":
            continue
        data = (src / rel).read_bytes()
        if Path(rel).suffix in PKG_TEXT:
            data = data.replace(b"res://assets/", f"{prefix}assets/".encode()).replace(b"res://levels/", f"{prefix}levels/".encode())
        target = dst / rel
        if not target.is_file() or target.read_bytes() != data:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    scene = str(meta.get("scene", "levels/ship/ship.tscn")).removeprefix("res://")
    return prefix + scene


def door_place(layout: dict, door: list) -> tuple[list, float]:
    """A door piece's position and yaw: built facing +z with the wall's inner face at its z 0."""
    h = layout["hall"]
    _id, wall, at = door
    if wall == "N":
        return [at, 0.0, h["zN"]], 0.0
    return ([h["x0"], 0.0, at], 90.0) if wall == "W" else ([h["x1"], 0.0, at], -90.0)


def _stage(staged: dict[str, Path]) -> list[str]:
    _godot.clear_staged(set(staged))
    for name, glb in staged.items():
        _godot.stage(glb, name)
    errors = [line for line in _godot.import_project() if "ERROR" in line]
    for line in errors[:10]:
        common.say(f"  import: {line}")
    return errors


def _xz(p: list, y: float = 0.0) -> list[float]:
    return [float(p[0]), y, float(p[1])]


def godot_check(layout: dict, out: Path, place: list, ship_report: dict, folder: Path) -> int:
    req, staged, want = scene_request(layout, out, place, ship_report)
    w = layout["walk"]
    req.update({"mode": "check", "walk": {"r": w["r"], "h": w["h"], "points": [_xz(p) for p in w["points"]]},
                "blocks": [[b[0], _xz(b[1]), _xz(b[2])] for b in w["blocks"]]})
    errors = _stage(staged)
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "lobby" / "check_request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "check.json").unlink(missing_ok=True)
    code, output = _godot.godot(["--headless", "--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s",
                                 GODOT_SCRIPT, "--", path.as_posix(), folder.as_posix()], GODOT_TIMEOUT)
    if code != 0 or not (folder / "check.json").is_file():
        raise common.Failure(f"hall.gd check failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
    result = json.loads((folder / "check.json").read_text(encoding="utf-8"))
    problems = list(errors)
    # step 5a: a script error inside hall.gd (a missing piece, a null scene) does not stop its check; it fails here
    problems += [f"hall.gd: {line.strip()}" for line in output.splitlines() if "SCRIPT ERROR" in line][:5]
    for pid, got in result["bounds"].items():
        exp = want["bounds"][pid]
        off = max(abs(a - b) for k in ("min", "max") for a, b in zip(got[k], exp[k]))
        if off > SIZE_TOL_M:
            problems.append(f"{pid}: Godot's bounds differ from Blender's by {off:.3f} m")
    for pid in want["collide"]:
        if result["colliders"].get(pid, 0) < 1:
            problems.append(f"{pid}: no collider after import")
    wk = result["walk"]
    common.say(f"  walk: {wk['reached']}/{wk['of']} points, {wk['length_m']:.1f} m in {wk['seconds']:.1f} s, end "
               f"{[round(v, 2) for v in wk['end']]}, lowest {wk['min_y']:.3f} m"
               + ("" if wk["arrived"] else f"; stuck near {[round(v, 2) for v in wk['stuck']]}"))
    if not wk["arrived"]:
        problems.append("the capsule walk did not arrive")
    sp = result.get("ship_package")
    if sp is not None:   # step 5a: the package's ship, its jaws shut and their colliders with them
        common.say(f"  ship package: {sp['colliders']} colliders, {sp['lights']} lights, jaws {sp['jaws']}, freed {sp['freed']}")
        if sp["colliders"] < 1:
            problems.append("the ship package: no collider")
        if len(sp["jaws"]) != 2 or any(abs(a) > 0.5 for a in sp["jaws"].values()):
            problems.append(f"the ship package: the jaws are not shut ({sp['jaws']})")
    for name, _a, _b, axis, face, side in w["blocks"]:
        b = result["blocks"][name]
        end = b["end"][0 if axis == "x" else 2]
        held = not b["arrived"] and (end - face) * side > 0
        common.say(f"  block {name}: stopped at {axis} {end:.2f} ({(end - face) * side:.2f} m on the hall's side of "
                   f"{axis} {face}){'' if held else ' PASSED THROUGH'}")
        if not held:
            problems.append(f"{name}: the capsule passed")
    for p in problems:
        common.say(f"  {p}")
    if problems:
        common.bad(f"lobby --godot: {len(problems)} problems")
        return 1
    common.ok(f"lobby --godot: {len(result['bounds'])} pieces import at Blender's sizes, "
              f"{sum(result['colliders'].values()) + (sp or {}).get('colliders', 0)} colliders, the walk arrives, {len(w['blocks'])} blocks hold "
              f"({folder.as_posix()})")
    return 0


def shoot(layout: dict, out: Path, place: list, folder: Path, grid: bool | str = False) -> int:
    req, staged, _want = scene_request(layout, out, place, lobby_layout.ship_report(layout))
    rv = layout["review"]
    req.update({"mode": "shoot", "background": rv["background"], "views": [v[:5] for v in rv["views"]],
                "top": rv["top"], "compare": [[v[0], v[5]] for v in rv["views"] if v[5]],
                "closeups": [v[:5] for v in rv.get("closeups", [])],
                "look": look_request(layout, layout["look"]["scheme"])})
    if "earth" in layout:
        req["earth"] = earth_request(layout, layout["earth"]["variant"])["earth"]
    if "light" in layout:
        req["light"] = light_request(layout, layout["light"]["mood"])["light"]
    if grid == "light":
        req.update({"mode": "grid", "views": [v[:5] for v in rv["views"] if v[0] in layout["light"]["grid"]],
                    "variants": ([light_request(layout, layout["light"]["mood"], k) for k in layout["light"]["trials"]]
                                 if layout["light"].get("trials") else
                                 [light_request(layout, k) for k in layout["light"]["moods"]])})
    elif grid == "ship":   # step 5a2: the ship's light sets over the mood
        sh = layout["light"]["ship"]
        views = [v[:5] for v in rv["views"]] + sh["views"]
        req.update({"mode": "grid", "views": [v for g in sh["grid"] for v in views if v[0] == g],
                    "variants": [light_request(layout, layout["light"]["mood"], ship=k) for k in sh["sets"]]})
    elif grid == "distance":   # step 4c: the Earth object's distances from the same positions
        e = layout["earth"]
        req.update({"mode": "grid", "views": e["distance_views"],
                    "variants": [earth_request(layout, e["variant"], d) for d in e["distances"]]})
    elif grid == "earth":
        req.update({"mode": "grid", "views": [v[:5] for v in rv["views"] if v[0] in layout["earth"]["grid"]],
                    "variants": [earth_request(layout, k) for k in layout["earth"]["variants"]]})
    elif grid:
        req.update({"mode": "grid", "views": [v[:5] for v in rv["views"] if v[0] in rv["grid"]],
                    "variants": [look_request(layout, k) for k in layout["look"]["schemes"]]})
    errors = _stage(staged)
    folder.mkdir(parents=True, exist_ok=True)
    path = common.OUT / "lobby" / "shoot_request.json"
    path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
    (folder / "shots.json").unlink(missing_ok=True)
    code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", GODOT_SCRIPT, "--",
                                  path.as_posix(), folder.as_posix()], VIEW_SIZE, GODOT_TIMEOUT)
    if code != 0 or not (folder / "shots.json").is_file():
        raise common.Failure(f"hall.gd shoot failed (exit code {code}):\n" + "\n".join(output.splitlines()[-20:]))
    result = json.loads((folder / "shots.json").read_text(encoding="utf-8"))
    errors += [f"hall.gd: {line.strip()}" for line in output.splitlines() if "SCRIPT ERROR" in line][:5]
    for line in errors[-5:]:
        common.say(f"  {line}")
    for name, info in result["shots"].items():
        common.say(f"  {name}: {info['draw_calls']} draw calls, {info['primitives']} primitives"
                   + (f", GPU {info['gpu_ms']:.2f} ms" if "gpu_ms" in info else ""))
    if errors:
        common.bad(f"lobby --shoot: {len(errors)} import errors")
        return 1
    sheet = folder / ("grid.png" if grid else "sheet.png")
    common.ok(f"lobby --{'grid' if grid else 'shoot'}: {len(result['shots'])} shots, sheet {sheet.as_posix()}")
    return 0
