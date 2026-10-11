"""The House's game-ready package (art #119, docs/house.md "The export"): the GLBs under the game's asset paths
(ARCHITECTURE 11.1: `assets/environment/<set>/<id>.glb`, the kit's shared textures beside its pieces) and one room
scene per game room (`levels/house/rooms/<room>.tscn`): the root named like the game's node with `metadata/size_m`,
the `Name` label, `Shell` (kit instances, the level's stairs and railings that stand in the room), `Dressing`,
`Fixtures` (lamp props and real-time `OmniLight3D` lights, no shadows), `Doors`, `Stations` and `Markers` with the
game's names and room-local positions. Pure Python; `house --export` copies the files and Godot checks them."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import shutil
from pathlib import Path

from . import house_layout as H

FORMAT = 1  # package.json's format
GLB_IMPORT = {  # ARCHITECTURE 11.2: a Node3D root, 1 unit = 1 m, animations kept
    "nodes/root_type": "", "nodes/root_scale": 1.0, "nodes/apply_root_scale": True, "animation/import": True}
PNG_COMPRESS = 2  # VRAM Compressed under environment/ (11.2)
SURFACES = ("concrete", "wood", "carpet", "grass")  # the game's FootstepSurface.SURFACES (ARCHITECTURE 4.7.40)
ROOF_TYPES = ("pitched", "ridge", "chimney", "vent", "dormer", "downpipe", "glass_roof", "glass_ridge")  # never carpet
ROOF_MARGIN = 1.0  # m round a roof's rect the check's roof rays cover (the eaves' overhang)
ROOF_FROM = 10.0  # m over the level's floor the roof rays start (over the ridge)
RUG = "rug"  # dressing props whose id starts so cover the floor (no collider): the tiles under them are carpet
QUESTIONS = [  # for the game side (prime-game #523); package.json carries them (questions() adds the package's lamps)
    "G3: the room scenes are under levels/house/rooms/ (11.1 keeps assets/ data only); the game's workflow swaps them "
    "into its greybox rooms (Body/Looks out, Shell/Dressing/Fixtures in).",
    "G11: the kit and the props are sets: one folder each (house_kit, house_props), a GLB per piece, not one GLB per "
    "folder named after it as 11.1's <id>/<id>.glb says for a single asset.",
    "Kit look: the GLBs carry vertex-colour materials; the textured look needs the art's kit_set.gdshader with the "
    "shared set_d/set_n0/set_n1 textures (a shader is not data: who owns it?).",
    "Imports: each file's .import here holds only ARCHITECTURE 11.2's options; the game's editor regenerates the "
    ".import files (and their uids) on its first import: commit the regenerated ones, not these.",
    "Surfaces: every walkable kit piece's instance carries metadata/surface (house.toml [export.surfaces]); the kit's "
    "GLBs carry none, so a game-side wrapper of a piece takes its surface from package.json's `surfaces`. The plot's "
    "ground (house_outdoor/outdoor.glb, package 7) is one GLB with its paths and street: grass needs its own node.",
]


def questions(lights: int) -> list[str]:
    """QUESTIONS with the package's lamp count (its rooms' fixtures, no moon spots)."""
    return QUESTIONS + [f"Lights: every fixture is a real-time OmniLight3D without shadows ({lights} in this "
                        "package); the bake comes later (#83)."]


def surface_of(data: dict, pid: str) -> str | None:
    """The footstep surface of a kit piece by house.toml's [export.surfaces] (first matching pattern), or None."""
    for pat, surface in settings(data).get("surfaces", {}).items():
        if fnmatch.fnmatchcase(pid, pat):
            return surface
    return None


def prop_surface(data: dict, pid: str) -> str | None:
    """The footstep surface a low dressing prop a player stands on carries (house.toml's [export.prop_surfaces], by
    id pattern), or None: the rays down meet its collider before the floor (art #126: the attic's rolled carpets)."""
    for pat, surface in settings(data).get("prop_surfaces", {}).items():
        if fnmatch.fnmatchcase(pid, pat):
            return surface
    return None


def tile_rect(data: dict, p: dict) -> tuple[float, float, float, float] | None:
    """A floor piece's footprint (x0, y0, x1, y1, plan metres) from its pivot, size and turn; None without a size."""
    size = data["pieces"][p["id"]].get("size")
    if not size:
        return None
    ax, az = H.axes(p["turn"])
    xs = [p["x"] + u * ax[0] + v * az[0] for u in (0, size[0]) for v in (0, size[1])]
    ys = [p["y"] + u * ax[1] + v * az[1] for u in (0, size[0]) for v in (0, size[1])]
    return min(xs), min(ys), max(xs), max(ys)


def piece_surface(data: dict, p: dict, rugs: list[tuple], rx: float, ry: float) -> str | None:
    """A shell piece's surface: carpet when at least half its footprint lies under the room's rugs (room-local AABBs,
    house_dressing.footprint), else its [export.surfaces] one."""
    surface = surface_of(data, p["id"])
    under = data["pieces"][p["id"]].get("type") not in ROOF_TYPES  # a roof over a rug stays a roof
    rect = tile_rect(data, p) if surface and rugs and under else None
    if rect:
        x0, y0, x1, y1 = rect[0] - rx, rect[1] - ry, rect[2] - rx, rect[3] - ry
        covered = sum(max(0.0, min(x1, r[2]) - max(x0, r[0])) * max(0.0, min(y1, r[3]) - max(y0, r[1])) for r in rugs)
        if covered >= 0.5 * (x1 - x0) * (y1 - y0) - H.EPS:
            return "carpet"
    return surface


def settings(data: dict) -> dict:
    return data["settings"]["export"]


def asset_res(data: dict, set_id: str, item: str) -> str:
    return settings(data)["asset_res"].format(set=set_id, id=item)


def packages(data: dict) -> dict[int, dict]:
    return {p["n"]: p for p in settings(data)["packages"]}


def rooms_of(data: dict, pkg: dict | None) -> list[tuple[dict, dict]]:
    """(level, room) pairs a package writes; every room of the house without a package."""
    out = []
    for lv in data["levels"]:
        for room in lv["rooms"]:
            if pkg is None:
                out.append((lv, room))
                continue
            names = pkg.get("rooms", [])
            if (room["id"] in names or lv["level"] in names) and room["id"] not in pkg.get("except", []):
                out.append((lv, room))
    return out


def level_extras(data: dict, planned: dict) -> dict[str, list[dict]]:
    """The level scenes' pieces (stairs, railings) per room: the smallest room of the piece's level whose rect holds
    its pivot; failing that, the smallest such room of the highest level at or below the pivot's height (a flight
    whose foot stands outside: the balcony's stairs on the yard); those in no room under the key ''."""
    out: dict[str, list[dict]] = {}
    area = lambda r: r["rect"][2] * r["rect"][3]
    for lv, pl in zip(data["levels"], planned["levels"]):
        for p in pl["extra"]:
            homes = [(lv, r) for r in lv["rooms"] if H.inside(r["rect"], p["x"], p["y"])]
            if not homes:
                homes = [(o, r) for o in data["levels"] if o["floor_y"] <= p["h"] + H.EPS
                         for r in o["rooms"] if H.inside(r["rect"], p["x"], p["y"])]
                top = max((o["floor_y"] for o, _ in homes), default=None)
                homes = [(o, r) for o, r in homes if o["floor_y"] == top]
            home = min(homes, key=lambda h: area(h[1])) if homes else None
            key = home[1]["id"] if home else ""
            out.setdefault(key, []).append(dict(p, floor_y=home[0]["floor_y"] if home else lv["floor_y"]))
    return out


def light_node(f: dict, parent: str, rx: float, fy: float, ry: float) -> str:
    """A fixture as a real-time OmniLight3D without shadows (a spot of the light kit becomes an omni of its range)."""
    n = H._num
    return "\n".join([
        f'[node name="{f["name"]}" type="OmniLight3D" parent="{parent}"]',
        f"transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {n(f['x'] - rx)}, {n(f['h'] - fy)}, {n(f['y'] - ry)})",
        "light_color = Color(" + ", ".join(n(c) for c in f["color"]) + ", 1)",
        f"light_energy = {n(f['energy'])}", "shadow_enabled = false", f"omni_range = {n(f['range'])}",
        f'metadata/fixture = "{f["type"]}"', f"metadata/glow = {'true' if f['glow'] else 'false'}"])


def room_scene(data: dict, lv: dict, room: dict, pieces: list[dict], extras: list[dict], resolved: list[dict],
               fixtures: list[dict], have=lambda pid: True, index: dict | None = None) -> str:
    """One room's scene text (origin at its north-west floor corner, like the game's greybox rooms). A dressing prop
    without a GLB (have(id) false) becomes a Marker3D under Placeholders with its size, never a CSG box. A walkable
    shell piece carries its footstep surface (piece_surface). `index`, when given, gets the check's node lists:
    "walkable" (Shell/<name> with a surface) and "hide" (Dressing/<name> of the props with a collider)."""
    from . import house_dressing

    ex = settings(data)
    kit = ex["kit_set"]
    rx, ry, w, d = room["rect"]
    fy = lv["floor_y"]
    sc = H._Scene(room["node"])
    meta = [f"metadata/size_m = Vector2i({H._num(w)}, {H._num(d)})", f'metadata/art_room = "{room["id"]}"']
    if H.wall_paint(data, room["id"]):
        meta.append(f'metadata/wall_paint = "{H.wall_paint(data, room["id"])}"')
    sc.nodes[0] += "\n" + "\n".join(meta)
    lab = ex["label"]
    sc.nodes.append("\n".join([
        '[node name="Name" type="Label3D" parent="."]',
        f"transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {H._num(w / 2)}, {H._num(lab['h'])}, {H._num(d / 2)})",
        "billboard = 1", f"text = {json.dumps(room.get('title', room['node']))}",
        f"font_size = {lab['font_size']}", f"outline_size = {lab['outline_size']}"]))
    sc.group("Shell")
    seen: dict = {}
    rugs = [house_dressing.footprint(r) for r in resolved if r["kind"] == "props" and r["id"].startswith(RUG)]
    walkable, hide = [], []
    for p, h in [(p, p["h"]) for p in pieces] + [(p, p["h"] - p["floor_y"]) for p in extras]:
        seen[p["id"]] = seen.get(p["id"], 0) + 1
        name = p.get("name", f"{p['id']}_{seen[p['id']]}")
        surface = piece_surface(data, p, rugs, rx, ry)
        sc.instance(name, "Shell", asset_res(data, kit, p["id"]), H._tf(p["turn"], p["x"] - rx, h, p["y"] - ry),
                    {"surface": surface} if surface else None)
        if surface:
            walkable.append(name)
    props_seen: dict = {}
    for r in resolved:
        if r["kind"] == "props" and have(r["id"]):
            props_seen[r["id"]] = props_seen.get(r["id"], 0) + 1
            if r.get("collision", "none") != "none":
                hide.append(f"{r['id']}_{props_seen[r['id']]}")
    if index is not None:
        index.update(walkable=walkable, hide=hide)
    tagged = [dict(r, surface=prop_surface(data, r["id"])) if prop_surface(data, r["id"]) else r for r in resolved]
    house_dressing.scene_nodes(sc, [r for r in tagged if have(r["id"])],
                               lambda pid: asset_res(data, ex["prop_set"], pid))
    lights = [f for f in fixtures if f["room"] == room["id"] and f["type"] != "moon"]
    if lights:
        if not any(n.startswith('[node name="Fixtures"') for n in sc.nodes):
            sc.group("Fixtures")
        for f in lights:
            sc.nodes.append(light_node(f, "Fixtures", rx, fy, ry))
    sc.group("Doors")
    planned_doors = room.get("_doors", [])
    for dm in planned_doors:
        sc.marker(dm["name"], "Doors", dm["x"] - rx, 0, dm["y"] - ry,
                  meta={"leaf": dm["leaf"]} if dm["leaf"] != "none" else None)
    sc.group("Stations")
    for s in room.get("stations", []):
        sc.marker(s["name"], "Stations", *s["at"])
    sc.group("Markers")
    for m in room.get("markers", []):
        sc.marker(m["name"], "Markers", *m["at"], group=m.get("group"))
    phs = [p for p in lv.get("placeholders", []) if p.get("room") == room["id"]]
    held = [r for r in resolved if not have(r["id"])]
    if phs or held:
        sc.group("Placeholders")
        for p in phs:
            sc.marker(p["name"], "Placeholders", p["at"][0] - rx, p["at"][1], p["at"][2] - ry, meta={"note": p["note"]})
        for k, r in enumerate(held, 1):
            sc.marker(f"{r['id']}_{k}", "Placeholders", *r["at"],
                      meta={"prop": r["id"], "size": r["size"], "yaw": r["yaw"], "note": "no GLB yet"})
    return sc.text()


def attic_dressing(z: dict, cat: dict | None = None) -> dict:
    """The attic's old things and hiding spots (house_attic.load("attic"): their own format in
    layouts/house/dressing/attic_roof/, plan metres) as the attic room's resolved dressing: room-local, on the floor,
    their yaw kept (the same front-+Z convention). A hero prop with its own `size` and no GLB becomes a Placeholders
    marker like any other prop without one. A library prop keeps its collision (cat: house_dressing.catalogue, the
    library's by default): picture frames and rugs have none. The roof's items stand on the slopes: not exported yet."""
    if cat is None:
        from . import house_attic, house_dressing
        cat = house_dressing.catalogue([house_attic.LIBRARY])
    rx, ry = z["rect"][0], z["rect"][1]
    out = []
    for it in z["items"]:
        out.append({"id": it["id"], "kind": "props", "at": (it["at"][0] - rx, 0.0, it["at"][1] - ry),
                    "yaw": float(it["yaw"]), "size": [it.get("w", 0.5), it.get("d", 0.5), it.get("h", 0.5)],
                    "pivot": "floor", "known": "w" in it,
                    "collision": it.get("collision", cat.get(it["id"], {}).get("collision", "box"))})
    return {"resolved": out}


def scenes(data: dict, planned: dict, dressing: dict, fixtures: list[dict], pkg: dict | None = None,
           have=lambda pid: True) -> dict:
    """room id -> {"level", "node", "text", "kit": piece ids, "props": prop ids}; plus "" -> the level pieces that
    stand in no room (a list). No CSG: a dressing prop always instances its GLB (house_dressing's placeholder box is
    for the art's own review only; a prop without a GLB is a sized Marker3D under Placeholders)."""
    extras = level_extras(data, planned)
    out: dict = {"": extras.get("", [])}
    plans = {lv["level"]: pl for lv, pl in zip(data["levels"], planned["levels"])}
    for lv, room in rooms_of(data, pkg):
        pl = plans[lv["level"]]
        rr = dict(room, _doors=pl["doors"][room["id"]])
        resolved = (dressing.get(room["id"]) or {}).get("resolved", [])
        pieces, ext = pl["pieces"][room["id"]], extras.get(room["id"], [])
        index: dict = {}
        text = room_scene(data, lv, rr, pieces, ext, resolved, fixtures, have, index)
        out[room["id"]] = {"level": lv["level"], "node": room["node"], "text": text, **index,
                           "lights": sum(1 for f in fixtures if f["room"] == room["id"] and f["type"] != "moon"),
                           "kit": sorted({p["id"] for p in pieces + ext}),
                           "props": sorted({r["id"] for r in resolved if have(r["id"])}),
                           "held": sorted({r["id"] for r in resolved if not have(r["id"])})}
    return out


def check_request(data: dict, built: dict, kit_ids=()) -> dict:
    """What godot/house/export_check.gd checks on the assembled package (its rooms placed at their plan origins): per
    room its rect, floor height and node lists (walkable shell pieces, props with a collider); the kit GLBs with a
    surface (each must hold a layer-1 collider); a room under a roof of its level also its `roof` rect (ROOF_MARGIN
    round it) for the rays down from roof_from over its floor; and the 1.36 m capsule's walks (house_layout.walk_request over every
    level: each doorway and flight) whose every point stands in a room of the package, with the pads under ends that
    have no floor. The walks leaving the package are listed as `outside`, the closed kit leaves as `closed`."""
    ex = settings(data)
    rooms = []
    for lv in data["levels"]:
        for room in lv["rooms"]:
            if room["id"] in built:
                b = built[room["id"]]
                rooms.append({"id": room["id"], "level": lv["level"], "node": room["node"], "rect": room["rect"],
                              "floor_y": lv["floor_y"], "floor": bool(room.get("floor")),
                              "scene": f"res://{ex['room_dir']}/{room['id']}.tscn",
                              "walkable": b.get("walkable", []), "hide": b.get("hide", [])})
                roof = next((rf for rf in lv.get("roofs", []) if rf.get("room") == room["id"]), None)
                if roof:  # the roof's rays: from over the ridge, the first hit is the roof a player walks on
                    x, y, w, d = (float(v) for v in roof["rect"])
                    m = ROOF_MARGIN
                    rooms[-1].update(roof=[x - m, y - m, w + 2 * m, d + 2 * m], roof_from=ROOF_FROM)

    storey = data["settings"].get("floor_to_floor_m", 3.2)

    def inside(pt) -> bool:
        """The point stands in the package: on a floored room of it, or, where no room of the house has a floor (a
        pad goes there), in any room of it."""
        here = [(lv, r) for lv in data["levels"] for r in lv["rooms"]
                if H.inside(r["rect"], pt[0], pt[2]) and lv["floor_y"] - H.EPS <= pt[1] < lv["floor_y"] + storey]
        floored = [r for _, r in here if r.get("floor")]
        return any(r["id"] in built for r in (floored or [r for _, r in here]))
    req = H.walk_request(data, [lv["level"] for lv in data["levels"]])
    walks, outside = [], []
    for w in req["walks"]:
        if all(inside(pt) for pt in w["points"]):
            walks.append({"name": w["name"], "kind": w["kind"], "points": w["points"]})
        elif any(inside(pt) for pt in w["points"]):
            outside.append(w["name"])
    ends = {tuple(pt) for w in walks for pt in (w["points"][0], w["points"][-1])}
    pads = [p for p in req["pads"] if (p[0], p[1], p[2]) in ends]
    pieces = {asset_res(data, ex["kit_set"], pid): surface_of(data, pid) for pid in sorted(kit_ids)
              if surface_of(data, pid)}
    return {"rooms": rooms, "pieces": pieces, "walks": walks, "pads": pads, "outside": outside,
            "closed": req.get("closed", [])}


EXEMPT = ("package.json", "project.godot", "_check/*", ".godot/*", "*.import", "*.uid")  # not package files


def stale(out: Path, files: dict) -> list[str]:
    """Files in the export folder that the package does not list (left by an earlier export): warned, never deleted."""
    found = (f.relative_to(out).as_posix() for f in Path(out).rglob("*") if f.is_file())
    return sorted(f for f in found if f not in files and not any(fnmatch.fnmatch(f, pat) for pat in EXEMPT))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def import_text(path: Path) -> str:
    """A minimal .import beside a packaged file with ARCHITECTURE 11.2's options; Godot fills in the rest."""
    if path.suffix == ".glb":
        params = [f"{k}={json.dumps(v)}" for k, v in GLB_IMPORT.items()]
        head = ['importer="scene"', 'type="PackedScene"']
    else:
        params, head = [f"compress/mode={PNG_COMPRESS}"], ['importer="texture"', 'type="CompressedTexture2D"']
    return "\n".join(["[remap]", "", *head, "", "[params]", "", *params]) + "\n"


def write(data: dict, planned: dict, dressing: dict, fixtures: list[dict], out: Path, raw: Path,
          prop_glbs: dict[str, Path], n: int | None = None) -> dict:
    """Writes a package (or all of them) into out; returns the summary that also goes to out/package.json. Fails
    (ValueError) on a kit piece or set file the raw folder lacks."""
    ex = settings(data)
    pkg = packages(data)[n] if n is not None else None
    built = scenes(data, planned, dressing, fixtures, pkg, lambda pid: pid in prop_glbs)
    unplaced = built.pop("")
    kit_dir = raw / data["settings"]["kit_dir"]
    kit_ids = {pid for r in built.values() for pid in r["kit"]}
    if pkg is None or pkg.get("kit"):
        kit_ids |= {p.stem for p in kit_dir.glob("*.glb")}
    prop_ids = {pid for r in built.values() for pid in r["props"]}
    copies: dict[Path, Path] = {}  # target (relative) -> source
    env = Path("assets/environment")
    for pid in sorted(kit_ids):
        copies[env / ex["kit_set"] / f"{pid}.glb"] = kit_dir / f"{pid}.glb"
    if kit_ids:
        for t in ex["kit_textures"]:
            copies[env / ex["kit_set"] / t] = kit_dir / "textures" / t
    task_dir = raw / data["settings"]["prop_dirs"][0]
    extra = {p.stem: p for p in task_dir.glob("*.glb")} if pkg is None or pkg.get("task_props") else {}
    for pid, src in sorted({**extra, **{pid: prop_glbs[pid] for pid in prop_ids}}.items()):
        copies[env / ex["prop_set"] / f"{pid}.glb"] = src
    set_ids = list(ex.get("sets", {})) if pkg is None else pkg.get("sets", [])
    for sid in set_ids:
        s = ex["sets"][sid]
        folder = raw / s["dir"]
        for f in sorted(folder.iterdir()) if folder.is_dir() else []:
            if f.is_file() and any(fnmatch.fnmatch(f.name, pat) for pat in s["files"]):
                copies[env / sid / f.name] = f
    lost = sorted(t.as_posix() for t, src in copies.items() if not src.is_file())
    if lost:
        raise ValueError(f"{len(lost)} files missing in the raw folder, e.g. {lost[0]} (build the kit and props)")
    out = Path(out)
    files = {}
    for target, src in sorted(copies.items()):
        dst = out / target
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        (dst.parent / (dst.name + ".import")).write_text(import_text(dst), encoding="utf-8", newline="\n")
        files[target.as_posix()] = sha256(dst)
    room_dir = out / ex["room_dir"]
    room_dir.mkdir(parents=True, exist_ok=True)
    for rid, r in built.items():
        (room_dir / f"{rid}.tscn").write_text(r["text"], encoding="utf-8", newline="\n")
        files[f"{ex['room_dir']}/{rid}.tscn"] = sha256(room_dir / f"{rid}.tscn")
    summary = {"format": FORMAT, "package": n, "name": pkg["name"] if pkg else "all",
               "rooms": {rid: {"level": r["level"], "node": r["node"], "kit": len(r["kit"]), "props": len(r["props"])}
                         for rid, r in built.items()},
               "unplaced": [p.get("name", p["id"]) for p in unplaced],
               "placeholders": sorted({pid for r in built.values() for pid in r["held"]}),
               "surfaces": {pid: surface_of(data, pid) for pid in sorted(kit_ids) if surface_of(data, pid)},
               "files": files, "questions": questions(sum(r.get("lights", 0) for r in built.values()))}
    (out / "package.json").write_text(json.dumps(summary, indent=1), encoding="utf-8", newline="\n")
    summary["stale"] = stale(out, files)
    summary["check"] = check_request(data, built, kit_ids)
    return summary
