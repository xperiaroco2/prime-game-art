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
import struct
from pathlib import Path

from . import house_layout as H

FORMAT = 1  # package.json's format
GLB_IMPORT = {  # ARCHITECTURE 11.2: a Node3D root, 1 unit = 1 m, animations kept
    "nodes/root_type": "", "nodes/root_scale": 1.0, "nodes/apply_root_scale": True, "animation/import": True}
PNG_COMPRESS = 2  # VRAM Compressed under environment/ (11.2)
SURFACES = ("concrete", "wood", "carpet", "grass")  # the game's FootstepSurface.SURFACES (ARCHITECTURE 4.7.40)
ROOF_TYPES = ("pitched", "ridge", "chimney", "vent", "dormer", "downpipe", "glass_roof", "glass_ridge")  # never carpet
ROOF_MARGIN = 1.0  # m round a roof's rect the check's roof rays cover (the eaves' overhang)
ROOF_PIECES = ("roof_", "chimney_", "dormer_")  # the name prefixes of the shell pieces a ray in a roof's rect may meet
ROOF_FROM = 10.0  # m over the level's floor the roof rays start (over the ridge)
KIT_SHADER = "kit_set.gdshader"  # the kit's set shader, shipped once beside the kit's pieces (#132)
KIT_MATERIAL = "kit_set.tres"  # its material: the kit's textures and every painted room's paint (#132)
SHADER_SRC = Path(__file__).resolve().parents[2] / "godot" / "kit" / KIT_SHADER
SET_MATERIAL = "kit_set"  # the kit GLBs' stand-in material (Blender's kit_set-vcol; Godot drops the -vcol hint)
FINE_MATERIAL = "kit_fine"  # the world look's props' stand-in material (Blender's kit_fine-vcol, #143)
FINE_SHADER = "prop_fine.gdshader"  # the fine pack's shader, shipped once beside the props (#147)
FINE_SHADER_SRC = Path(__file__).resolve().parents[2] / "godot" / "props" / FINE_SHADER
FINE_DIR = "fine"  # house_props/fine/<tier>/fine_d.png, fine_n0.png, fine_n1.png: the fine pack's shared textures
FINE_TEXTURES = ("d", "d1", "n0", "n1", "n2", "n3")  # in this order; a build writes the ones its slots need
FINE_SLOTS = 8  # textured layers (prop_lib.FINE_SLOTS)
FINE_LAYERS = 16  # prop_fine.gdshader's layer arrays
RUG = "rug"  # dressing props whose id starts so cover the floor (no collider): the tiles under them are carpet
QUESTIONS = [  # for the game side (prime-game #523); package.json carries them (questions() adds the package's lamps)
    "G3: the room scenes are under levels/house/rooms/ (11.1 keeps assets/ data only); the game's workflow swaps them "
    "into its greybox rooms (Body/Looks out, Shell/Dressing/Fixtures in).",
    "G11: the kit and the props are sets: one folder each (house_kit, house_props), a GLB per piece, not one GLB per "
    "folder named after it as 11.1's <id>/<id>.glb says for a single asset.",
    "Kit look and wall paints (#132): the room scenes put house_kit/kit_set.tres (the art's kit_set.gdshader, the "
    "shared set_d/set_n0/set_n1 textures and every room's wall paint) on the kit pieces' set surfaces, each mesh "
    "with its plan pose as the instance parameter plan_at; the shader is art code shipped as a file: who owns it?",
    "Imports: each file's .import here holds only ARCHITECTURE 11.2's options; the game's editor regenerates the "
    ".import files (and their uids) on its first import: commit the regenerated ones, not these.",
    "Surfaces: every walkable kit piece's instance carries metadata/surface (house.toml [export.surfaces]); the kit's "
    "GLBs carry none, so a game-side wrapper of a piece takes its surface from package.json's `surfaces`. The plot's "
    "ground (house_outdoor/outdoor.glb, package 7) is one mesh per surface (ground_grass, ground_concrete, kerb); "
    "outdoor.tscn tags each node (editable children of Ground).",
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


def _gltf(path: Path) -> dict | None:
    """A GLB's JSON chunk, or None when the file is no GLB."""
    try:
        with open(path, "rb") as f:
            head = f.read(20)
            if len(head) < 20 or head[:4] != b"glTF":
                return None
            return json.loads(f.read(struct.unpack_from("<I", head, 12)[0]))
    except (OSError, ValueError):
        return None


def set_surfaces(path: Path, material: str = SET_MATERIAL, posed: bool = True) -> list[dict]:
    """A kit GLB's surfaces on the set material as Godot imports them (#132): per mesh node its path under the GLB's
    root (the glTF node names), its origin in the GLB and its surface indices (the primitives' order). Empty for a
    file that is no GLB; ValueError for a set surface under a turned or scaled node (the shader's plan_at is a
    position and a turn) unless `posed` is false. `material` names another stand-in: a prop's FINE_MATERIAL (#147)."""
    doc = _gltf(path)
    if doc is None:
        return []
    mats = [str(m.get("name", "")).split("-")[0] for m in doc.get("materials", [])]
    nodes, out = doc.get("nodes", []), []

    def walk(i: int, chain: list[str], at: list[float], turned: bool) -> None:
        nd = nodes[i]
        turned = turned or "matrix" in nd or nd.get("rotation", [0, 0, 0, 1]) != [0, 0, 0, 1] \
            or nd.get("scale", [1, 1, 1]) != [1, 1, 1]
        at = [a + b for a, b in zip(at, nd.get("translation", [0, 0, 0]))]
        chain = chain + [nd.get("name", f"node{i}")]
        if "mesh" in nd:
            idx = [k for k, pr in enumerate(doc["meshes"][nd["mesh"]]["primitives"])
                   if "material" in pr and mats[pr["material"]] == material]
            if idx and turned and posed:
                raise ValueError(f"{path.name}: set surfaces under a turned or scaled node {'/'.join(chain)}")
            if idx:
                out.append({"node": "/".join(chain), "at": [round(a, 4) for a in at], "surfaces": idx})
        for c in nd.get("children", []):
            walk(c, chain, at, turned)
    for i in doc.get("scenes", [{}])[doc.get("scene", 0)].get("nodes", []):
        walk(i, [], [0.0, 0.0, 0.0], False)
    return out


def material_res(data: dict, name: str = KIT_MATERIAL) -> str:
    """The res:// path of a file in the kit's folder (the shader, the material, a texture)."""
    return asset_res(data, settings(data)["kit_set"], "x").rsplit("/", 1)[0] + "/" + name


def _f(v: float) -> str:
    return f"{float(v):.6g}"


def material_text(data: dict) -> str:
    """The kit's set material as a resource (#132): kit_set.gdshader, the shared textures, the layers' roughness and
    normal strength, and every painted room's paint (house_layout.paint_request, the house plan's frame; at most
    16), as godot/kit/kit_materials.gd `make` and `paint` set them for the walk."""
    ex, spec = settings(data), data["spec"]
    mats = [spec["materials"][m] for m in spec.get("packs", {}).get("set", {}).get("layers", [])]
    paints = H.paint_request(data)
    rooms = paints["rooms"][:16]
    pad = [{"rect": [0, 0, 0, 0], "band": [0, 0], "to": [0, 0, 0]}] * (16 - len(rooms))
    ext = [("Shader", material_res(data, KIT_SHADER))] + [("Texture2D", material_res(data, t))
                                                          for t in ex["kit_textures"]]
    lines = ['[gd_resource type="ShaderMaterial" format=3]', ""]
    lines += [f'[ext_resource type="{t}" path="{path}" id="{k}"]' for k, (t, path) in enumerate(ext, 1)]
    lines += ["", "[resource]", 'resource_name = "kit_set_painted"', 'shader = ExtResource("1")']
    lines += [f'shader_parameter/{Path(t).stem} = ExtResource("{k}")' for k, t in enumerate(ex["kit_textures"], 2)]
    if len(mats) == 3:
        for key, field in (("layer_roughness", "roughness"), ("layer_normal_strength", "normal_strength")):
            lines.append(f"shader_parameter/{key} = Vector3({', '.join(_f(m[field]) for m in mats)})")
    lines += [f"shader_parameter/paint_count = {len(rooms)}",
              f"shader_parameter/paint_from = Vector3({', '.join(_f(c) for c in paints['from'])})",
              "shader_parameter/paint_rect = PackedVector4Array("
              + ", ".join(_f(v) for r in rooms + pad for v in r["rect"]) + ")",
              "shader_parameter/paint_band = PackedVector2Array("
              + ", ".join(_f(v) for r in rooms + pad for v in r["band"]) + ")",
              "shader_parameter/paint_to = PackedVector3Array("
              + ", ".join(_f(v) for r in rooms + pad for v in r["to"]) + ")"]
    return "\n".join(lines) + "\n"


def fine_tiers(data: dict, raw: Path) -> dict:
    """The fine pack's build (#143, `props-library --build`): fine.json from the raw folder's `fine_dir`, or {}."""
    path = raw / settings(data).get("fine_dir", "") / "fine.json"
    return json.loads(path.read_text(encoding="utf-8")) if settings(data).get("fine_dir") and path.is_file() else {}


def fine_keys(fine: dict, tier: str) -> list[str]:
    """The tier's texture keys (FINE_TEXTURES order): the ones its build's `files` name."""
    files = fine.get("tiers", {}).get(tier, {}).get("files", {})
    return [k for k in FINE_TEXTURES if k in files]


def fine_slots(layers: list[dict]) -> list[int]:
    """Each layer's texture slot (its `slot`, else its place among the textured layers), -1 for a flat finish."""
    out, nxt = [], 0
    for x in layers:
        if x.get("source") and nxt < FINE_SLOTS:
            out.append(int(x.get("slot", nxt)))
            nxt = out[-1] + 1
        else:
            out.append(-1)
    return out


def fine_res(data: dict, name: str) -> str:
    """The res:// path of a file of the fine pack in the props' folder (the shader, a tier's material or texture)."""
    return asset_res(data, settings(data)["prop_set"], "x").rsplit("/", 1)[0] + "/" + name


def fine_material_text(data: dict, fine: dict, tier: str) -> str:
    """The fine pack's material of one tier as a resource (#147): prop_fine.gdshader, the tier's shared textures
    and the layers' values, as godot/props/prop_materials.gd `make` sets them."""
    layers = fine.get("layers", [])[:FINE_LAYERS]
    means = fine.get("tiers", {}).get(tier, {}).get("detail_mean", {})
    keys = fine_keys(fine, tier)
    ext = [("Shader", fine_res(data, FINE_SHADER))] + [
        ("Texture2D", fine_res(data, f"{FINE_DIR}/{tier}/fine_{k}.png")) for k in keys]
    pad = lambda vals: vals + [0.0] * (FINE_LAYERS - len(vals))
    arr = lambda key, dflt: "PackedFloat32Array(" + ", ".join(
        _f(v) for v in pad([float(x.get(key, dflt)) for x in layers])) + ")"
    slots = fine_slots(layers)
    gain = [2.0] * FINE_SLOTS
    for x, s in zip(layers, slots):
        if s >= 0 and x.get("name") in means:
            gain[s] = 1.0 / max(float(means[x["name"]]), 0.05)
    lines = ['[gd_resource type="ShaderMaterial" format=3]', ""]
    lines += [f'[ext_resource type="{t}" path="{path}" id="{k}"]' for k, (t, path) in enumerate(ext, 1)]
    lines += ["", "[resource]", f'resource_name = "prop_fine_{tier}"', 'shader = ExtResource("1")']
    lines += [f'shader_parameter/fine_{t} = ExtResource("{k}")' for k, t in enumerate(keys, 2)]
    lines += [f"shader_parameter/layer_roughness = {arr('roughness', 0.7)}",
              f"shader_parameter/layer_metallic = {arr('metallic', 0.0)}",
              f"shader_parameter/layer_normal_strength = {arr('normal_strength', 0.0)}",
              "shader_parameter/layer_slot = PackedInt32Array("
              + ", ".join(str(v) for v in slots + [-1] * (FINE_LAYERS - len(slots))) + ")",
              f"shader_parameter/slot_gain = PackedFloat32Array({', '.join(_f(g) for g in gain)})"]
    return "\n".join(lines) + "\n"


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
               fixtures: list[dict], have=lambda pid: True, index: dict | None = None,
               surfaces: dict | None = None, fine: dict | None = None) -> str:
    """One room's scene text (origin at its north-west floor corner, like the game's greybox rooms). A dressing prop
    without a GLB (have(id) false) becomes a Marker3D under Placeholders with its size, never a CSG box. A walkable
    shell piece carries its footstep surface (piece_surface). `index`, when given, gets the check's node lists:
    "walkable" (Shell/<name> with a surface) and "hide" (Dressing/<name> of the props with a collider).
    `surfaces` (piece id -> set_surfaces) puts the kit's set material (KIT_MATERIAL) on each piece's set surfaces
    with the mesh's plan pose as `plan_at` (#132): the wall paints travel with the scene. `fine` (prop id ->
    set_surfaces(..., FINE_MATERIAL)) puts the fine pack's material of `fine_tier` on the props' kit_fine surfaces
    (#147): one shared resource, so the game swaps the tier for the whole house in one place."""
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
    # the room's middle, or its layout's `label_at` (plan metres) where the middle is inside a piece (#158: the stairs)
    lx, ly = (room["label_at"][0] - rx, room["label_at"][1] - ry) if room.get("label_at") else (w / 2, d / 2)
    sc.nodes.append("\n".join([
        '[node name="Name" type="Label3D" parent="."]',
        f"transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {H._num(lx)}, {H._num(lab['h'])}, {H._num(ly)})",
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
        for s in (surfaces or {}).get(p["id"], []):
            ax, az = H.axes(p["turn"])
            ox, oy, oz = s["at"]
            at = [p["x"] + ax[0] * ox + az[0] * oz, fy + h + oy, p["y"] + ax[1] * ox + az[1] * oz, p["turn"] % 360]
            parent, _, node = f"Shell/{name}/{s['node']}".rpartition("/")
            mat = sc.res(material_res(data))
            sc.nodes.append("\n".join([f'[node name="{node}" parent="{parent}"]']
                                      + [f'surface_material_override/{i} = ExtResource("{mat}")' for i in s["surfaces"]]
                                      + ["instance_shader_parameters/plan_at = Vector4("
                                         + ", ".join(H._num(v) for v in at) + ")"]))
    props_seen: dict = {}
    for r in resolved:
        if r["kind"] == "props" and have(r["id"]):
            props_seen[r["id"]] = props_seen.get(r["id"], 0) + 1
            if r.get("collision", "none") != "none":
                hide.append(f"{r['id']}_{props_seen[r['id']]}")
    if index is not None:
        index.update(walkable=walkable, hide=hide)
    tagged = [dict(r, surface=prop_surface(data, r["id"])) if prop_surface(data, r["id"]) else r for r in resolved]
    fine_mat = fine_res(data, f"prop_fine_{ex.get('fine_tier', 'high')}.tres")

    def fine_of(pid: str) -> list:
        return [(s["node"], [f'surface_material_override/{i} = ExtResource("{sc.res(fine_mat)}")' for i in s["surfaces"]])
                for s in (fine or {}).get(pid, [])]
    house_dressing.scene_nodes(sc, [r for r in tagged if have(r["id"])],
                               lambda pid: asset_res(data, ex["prop_set"], pid), fine_of)
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
    library's by default): picture frames and rugs have none. The layer is the library's (#168: a detail prop goes
    under Detail, like the rooms'). The roof's items stand on the slopes: not exported yet."""
    if cat is None:
        from . import house_attic, house_dressing
        cat = house_dressing.catalogue([house_attic.LIBRARY])
    rx, ry = z["rect"][0], z["rect"][1]
    out = []
    for it in z["items"]:
        out.append({"id": it["id"], "kind": "props", "at": (it["at"][0] - rx, 0.0, it["at"][1] - ry),
                    "yaw": float(it["yaw"]), "size": [it.get("w", 0.5), it.get("d", 0.5), it.get("h", 0.5)],
                    "pivot": "floor", "known": "w" in it,
                    "collision": it.get("collision", cat.get(it["id"], {}).get("collision", "box")),
                    "layer": it.get("layer", cat.get(it["id"], {}).get("layer", "base"))})
    return {"resolved": out}


def scenes(data: dict, planned: dict, dressing: dict, fixtures: list[dict], pkg: dict | None = None,
           have=lambda pid: True, surfaces: dict | None = None, fine: dict | None = None) -> dict:
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
        text = room_scene(data, lv, rr, pieces, ext, resolved, fixtures, have, index, surfaces, fine)
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
    round it) for the rays down from roof_from over its floor, and `roof_rect`, where a ray, past the props on the
    roof, must meet a roof piece (`roof_pieces`, ROOF_PIECES): a floor or no hit there is a hole in the roof; and
    the 1.36 m capsule's walks (house_layout.walk_request over every level: each doorway and flight) whose every
    point stands in a room of the package, with the pads under ends that have no floor. The walks leaving the
    package are listed as `outside`, the closed kit leaves as `closed`."""
    ex = settings(data)
    rooms = []
    paints = H.paint_request(data)
    for lv in data["levels"]:
        for room in lv["rooms"]:
            if room["id"] in built:
                b = built[room["id"]]
                rooms.append({"id": room["id"], "level": lv["level"], "node": room["node"], "rect": room["rect"],
                              "floor_y": lv["floor_y"], "floor": bool(room.get("floor")),
                              "scene": f"res://{ex['room_dir']}/{room['id']}.tscn",
                              "walkable": b.get("walkable", []), "hide": b.get("hide", [])})
                paint = next((pr for pr in paints["rooms"] if pr["room"] == room["id"]), None)
                if paint:
                    rooms[-1]["paint"] = {"hex": paint["hex"], "rect": paint["rect"], "band": paint["band"],
                                          "to": paint["to"], "from": paints["from"]}
                roof = next((rf for rf in lv.get("roofs", []) if rf.get("room") == room["id"]), None)
                if roof:  # the roof's rays: from over the ridge, the first hit is the roof a player walks on
                    x, y, w, d = (float(v) for v in roof["rect"])
                    m = ROOF_MARGIN
                    rooms[-1].update(roof=[x - m, y - m, w + 2 * m, d + 2 * m], roof_rect=[x, y, w, d],
                                     roof_from=ROOF_FROM, roof_pieces=list(ROOF_PIECES))

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
            "closed": req.get("closed", []), "material": material_res(data) if kit_ids else ""}


EXEMPT = ("package.json", "project.godot", "_check/*", "_build/*", ".godot/*", "*.import", "*.uid")  # not package files


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
        if path.parent.parent.name == FINE_DIR:  # the fine pack's textures (#147): sampled at every distance
            params.append("mipmaps/generate=true")
    return "\n".join(["[remap]", "", *head, "", "[params]", "", *params]) + "\n"


def write(data: dict, planned: dict, dressing: dict, fixtures: list[dict], out: Path, raw: Path,
          prop_glbs: dict[str, Path], n: int | None = None) -> dict:
    """Writes a package (or all of them) into out; returns the summary that also goes to out/package.json. Fails
    (ValueError) on a kit piece or set file the raw folder lacks."""
    ex = settings(data)
    pkg = packages(data)[n] if n is not None else None
    kit_dir = raw / data["settings"]["kit_dir"]
    surfaces = {p.stem: set_surfaces(p) for p in sorted(kit_dir.glob("*.glb"))}
    fine = {pid: f for pid, src in prop_glbs.items() if (f := set_surfaces(src, FINE_MATERIAL, posed=False))}
    built = scenes(data, planned, dressing, fixtures, pkg, lambda pid: pid in prop_glbs, surfaces, fine)
    unplaced = built.pop("")
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
    shipped = {pid for pid in {**extra, **{pid: 1 for pid in prop_ids}}
               if set_surfaces(extra.get(pid) or prop_glbs[pid], FINE_MATERIAL, posed=False)}
    fine_pack = fine_tiers(data, raw) if shipped else {}
    if shipped and not fine_pack:
        raise ValueError(f"{len(shipped)} props on the fine pack ({sorted(shipped)[0]}, ...) but no fine.json under "
                         f"<raw>/{ex.get('fine_dir', '')} (build the library: props-library --build)")
    for tier, t in fine_pack.get("tiers", {}).items():  # the fine pack's shared textures (#147), once per tier
        for k in fine_keys(fine_pack, tier):
            copies[env / ex["prop_set"] / FINE_DIR / tier / f"fine_{k}.png"] = Path(t["files"][k])
    set_ids = list(ex.get("sets", {})) if pkg is None else pkg.get("sets", [])
    builds: dict[str, Path] = {}
    for sid in set_ids:
        s = ex["sets"][sid]
        folder = raw / s["dir"]
        if s.get("build") == "outdoor":  # pure Python, seconds: the plot's files fresh from its layout (art #128)
            from . import house_outdoor
            folder = builds[sid] = Path(out) / "_build" / sid
            made = house_outdoor.write(house_outdoor.load(), folder)
            if made["problems"]:
                raise ValueError(f"the plot's build: {made['problems'][0]}")
        for f in sorted(folder.iterdir()) if folder.is_dir() else []:
            if f.is_file() and any(fnmatch.fnmatch(f.name, pat) for pat in s["files"]):
                copies[env / sid / f.name] = f
    plot = None
    if pkg is not None and pkg.get("plot") or pkg is None and "house_outdoor" in builds:
        from . import house_export_plot as PL
        inputs = PL.load_inputs(data, raw, builds["house_outdoor"])
        plot = PL.scene(data, raw, *inputs, surfaces=surfaces)
        for target, src in plot["copies"].items():
            copies[env / target] = src
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
    if kit_ids:  # the set material that carries the wall paints (#132): text resources, no .import
        for name, text in ((KIT_SHADER, SHADER_SRC.read_text(encoding="utf-8")), (KIT_MATERIAL, material_text(data))):
            target = env / ex["kit_set"] / name
            (out / target).parent.mkdir(parents=True, exist_ok=True)
            (out / target).write_text(text, encoding="utf-8", newline="\n")
            files[target.as_posix()] = sha256(out / target)
    if fine_pack:  # the fine pack's shader and one material per tier (#147): text resources, no .import
        texts = [(FINE_SHADER, FINE_SHADER_SRC.read_text(encoding="utf-8"))] + [
            (f"prop_fine_{tier}.tres", fine_material_text(data, fine_pack, tier)) for tier in fine_pack["tiers"]]
        for name, text in texts:
            target = env / ex["prop_set"] / name
            (out / target).write_text(text, encoding="utf-8", newline="\n")
            files[target.as_posix()] = sha256(out / target)
    room_dir = out / ex["room_dir"]
    room_dir.mkdir(parents=True, exist_ok=True)
    for rid, r in built.items():
        (room_dir / f"{rid}.tscn").write_text(r["text"], encoding="utf-8", newline="\n")
        files[f"{ex['room_dir']}/{rid}.tscn"] = sha256(room_dir / f"{rid}.tscn")
    if plot:
        rel = plot["res"].removeprefix("res://")
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(plot["text"], encoding="utf-8", newline="\n")
        files[rel] = sha256(out / rel)
    if plot:  # the plot's kit pieces (fence, outdoor stairs, the gazebo's deck, the glass roof) beside the rooms'
        kit_ids = set(kit_ids) | {k[len(ex["kit_set"]) + 1:-4] for k in plot["copies"]
                                  if k.startswith(ex["kit_set"] + "/")}
    summary = {"format": FORMAT, "package": n, "name": pkg["name"] if pkg else "all",
               "rooms": {rid: {"level": r["level"], "node": r["node"], "kit": len(r["kit"]), "props": len(r["props"])}
                         for rid, r in built.items()},
               "unplaced": [p.get("name", p["id"]) for p in unplaced],
               "placeholders": sorted({pid for r in built.values() for pid in r["held"]} |
                                      set(plot["held"] if plot else [])),
               "surfaces": {pid: surface_of(data, pid) for pid in sorted(kit_ids) if surface_of(data, pid)},
               "files": files, "questions": questions(sum(r.get("lights", 0) for r in built.values()))}
    if plot:
        summary["plot"] = {"scene": plot["res"], **plot["counts"], "held": plot["held"]}
    (out / "package.json").write_text(json.dumps(summary, indent=1), encoding="utf-8", newline="\n")
    summary["stale"] = stale(out, files)
    summary["check"] = check_request(data, built, kit_ids)
    if plot:
        from . import house_outdoor
        p_data = inputs[0]
        summary["check"]["plot"] = {"scene": plot["res"], "rect": p_data["ground"],
                                    "holes": [h["rect"] for h in house_outdoor.holes(p_data)],
                                    "walkable": plot["walkable"], "hide": plot["hide"]}
        summary["check"]["pieces"].update({asset_res(data, ex["kit_set"], k[len(ex["kit_set"]) + 1:-4]): surface_of(
            data, k[len(ex["kit_set"]) + 1:-4]) for k in plot["copies"] if k.startswith(ex["kit_set"] + "/")
            and surface_of(data, k[len(ex["kit_set"]) + 1:-4])})
    return summary
