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
QUESTIONS = [  # for the game side (prime-game #523); package.json carries them
    "G3: the room scenes are under levels/house/rooms/ (11.1 keeps assets/ data only); the game's workflow swaps them "
    "into its greybox rooms (Body/Looks out, Shell/Dressing/Fixtures in).",
    "G11: the kit and the props are sets: one folder each (house_kit, house_props), a GLB per piece, not one GLB per "
    "folder named after it as 11.1's <id>/<id>.glb says for a single asset.",
    "Kit look: the GLBs carry vertex-colour materials; the textured look needs the art's kit_set.gdshader with the "
    "shared set_d/set_n0/set_n1 textures (a shader is not data: who owns it?).",
    "Lights: every fixture is a real-time OmniLight3D without shadows (191 in the house); the bake comes later (#83).",
]


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
               fixtures: list[dict], have=lambda pid: True) -> str:
    """One room's scene text (origin at its north-west floor corner, like the game's greybox rooms). A dressing prop
    without a GLB (have(id) false) becomes a Marker3D under Placeholders with its size, never a CSG box."""
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
    for p in pieces:
        seen[p["id"]] = seen.get(p["id"], 0) + 1
        sc.instance(f"{p['id']}_{seen[p['id']]}", "Shell", asset_res(data, kit, p["id"]),
                    H._tf(p["turn"], p["x"] - rx, p["h"], p["y"] - ry))
    for p in extras:
        seen[p["id"]] = seen.get(p["id"], 0) + 1
        sc.instance(p.get("name", f"{p['id']}_{seen[p['id']]}"), "Shell", asset_res(data, kit, p["id"]),
                    H._tf(p["turn"], p["x"] - rx, p["h"] - p["floor_y"], p["y"] - ry))
    house_dressing.scene_nodes(sc, [r for r in resolved if have(r["id"])],
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


def attic_dressing(z: dict) -> dict:
    """The attic's old things and hiding spots (house_attic.load("attic"): their own format in
    layouts/house/dressing/attic_roof/, plan metres) as the attic room's resolved dressing: room-local, on the floor,
    their yaw kept (the same front-+Z convention). A hero prop with its own `size` and no GLB becomes a Placeholders
    marker like any other prop without one. The roof's items stand on the slopes: not exported yet."""
    rx, ry = z["rect"][0], z["rect"][1]
    out = []
    for it in z["items"]:
        out.append({"id": it["id"], "kind": "props", "at": (it["at"][0] - rx, 0.0, it["at"][1] - ry),
                    "yaw": float(it["yaw"]), "size": [it.get("w", 0.5), it.get("d", 0.5), it.get("h", 0.5)],
                    "pivot": "floor", "collision": "box", "known": "w" in it})
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
        out[room["id"]] = {"level": lv["level"], "node": room["node"],
                           "text": room_scene(data, lv, rr, pieces, ext, resolved, fixtures, have),
                           "kit": sorted({p["id"] for p in pieces + ext}),
                           "props": sorted({r["id"] for r in resolved if have(r["id"])}),
                           "held": sorted({r["id"] for r in resolved if not have(r["id"])})}
    return out


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
               "placeholders": sorted({pid for r in built.values() for pid in r["held"]}), "files": files, "questions": QUESTIONS}
    (out / "package.json").write_text(json.dumps(summary, indent=1), encoding="utf-8", newline="\n")
    return summary
