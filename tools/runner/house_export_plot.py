"""Package 7's plot scene (art #128, docs/house.md "The export"): `levels/house/outdoor.tscn`, everything outside the
house that no room scene holds, at the plan's coordinates (Godot x = plan x, z = plan y, the ground's top at y 0):
`Ground` (the plot's `outdoor.glb`, each ground mesh tagged with its footstep surface), `Backdrop`, `Shell` (the
fence, the gates, the outdoor stairs and rails, the greenhouse's glass roof, the gazebo and the zones' railings: kit
pieces) and `Dressing` (the plot's, the garden's and the zones' props and the garden's plants); a prop without a GLB
is a sized `Marker3D` under `Placeholders`. No lights: the rooms of P2 and P7 carry the plot's lamps.

The props' game names (`game_name`): the game folder `house_props/` is flat, and 17 basenames repeat between the
prop sources (task, library, zones). The first source in `prop_order` (house.toml's `prop_dirs`, then `[export.plot]`
`prop_src`'s other folders) that holds `<id>.glb` ships it as `<id>.glb`, the name every package before P7 used; any
other source's `<id>.glb` ships as `<id>_<source>.glb` (`zones`, `library`). Standard library only."""

from __future__ import annotations

import json
import math
from pathlib import Path

from . import house_layout as H

ROOT_NODE = "Outdoor"
GROUND_KERB = ("kerb", "concrete")  # outdoor.glb's kerb-col: Godot's node `kerb`, a concrete strip


def plot_settings(data: dict) -> dict:
    return data["settings"]["export"].get("plot", {})


def prop_order(data: dict) -> list[str]:
    """The prop sources in the naming order: house.toml's prop_dirs, then the other folders of [export.plot] prop_src."""
    order = list(data["settings"].get("prop_dirs", []))
    for d in plot_settings(data).get("prop_src", {}).values():
        if d not in order:
            order.append(d)
    return order


def source_tag(src_dir: str) -> str:
    """`props/zones/v1` -> `zones`: the suffix a non-first source's clashing GLB gets."""
    parts = Path(src_dir).parts
    return parts[1] if len(parts) > 1 else parts[0]


def game_name(order: list[str], has, src_dir: str, pid: str) -> str:
    """The flat game file name of `<src_dir>/<pid>.glb`: `<pid>.glb` when src_dir is the first source of `order`
    holding the id (has(dir, pid)), else `<pid>_<source>.glb`."""
    owner = next((d for d in order if has(d, pid)), src_dir)
    return f"{pid}.glb" if owner == src_dir else f"{pid}_{source_tag(src_dir)}.glb"


def clashes(order: list[str], ids: dict[str, set[str]]) -> dict[str, list[str]]:
    """basename -> the sources holding it, for every basename more than one source holds (ids: dir -> its ids)."""
    out: dict[str, list[str]] = {}
    for d in order:
        for pid in ids.get(d, set()):
            out.setdefault(pid, []).append(d)
    return {k: v for k, v in sorted(out.items()) if len(v) > 1}


def tf(yaw: float, x: float, h: float, z: float, scale: float = 1.0) -> str:
    """A Godot transform turned yaw degrees about Y (rotation_degrees.y, as the proofs place them), scaled evenly."""
    t = math.radians(float(yaw))
    c, s = math.cos(t) * scale, math.sin(t) * scale
    v = [c, 0, s, 0, scale, 0, -s, 0, c, x, h, z]
    return "Transform3D(" + ", ".join(H._num(n) for n in v) + ")"


def ground_surfaces(plot: dict) -> list[tuple[str, str]]:
    """outdoor.glb's ground nodes as Godot names them (the `-col` suffix stripped) and their surfaces."""
    from . import house_outdoor
    names = sorted({house_outdoor.paint_surface(plot, z["paint"]) for z in plot["zones"]})
    return [(f"ground_{s}", s) for s in names] + [GROUND_KERB]


def placements(plot_doc: dict, garden: dict, zones: list[dict]) -> list[dict]:
    """Every piece and prop of the plot: {"src", "id", "at": [x, h, z], "yaw", "scale", "size"}; src "kit" is a
    shell piece, "garden" a house_garden plant or hedge, "" a prop resolved by prop_dirs, else a prop_src key."""
    out = []
    for p in plot_doc["fence"] + plot_doc["stairs"]["pieces"] + plot_doc["stairs"]["rails"]:
        out.append({"src": "kit", "id": p["piece"], "at": p["at"], "yaw": p.get("yaw", 0)})
    for p in plot_doc["props"]:
        rect = p.get("rect") or [p["at"][0], p["at"][1], 0, 0]
        out.append({"src": "garden" if p["id"] == "hedge" else "", "id": p["id"],
                    "at": [p["at"][0], p.get("h", 0.0), p["at"][1]], "yaw": p.get("yaw", 0),
                    "size": [rect[2], p.get("height", 1.0), rect[3]]})
    for r in garden["roof"]:
        out.append({"src": "kit", "id": r["id"], "at": [r["x"], r["h"], r["y"]], "yaw": r["turn"]})
    for p in garden["props"]:
        src = "garden" if p["src"] == "garden" else p["src"]
        out.append({"src": src, "id": p["id"], "at": [p["at"][0], p["h"], p["at"][1]], "yaw": p["yaw"],
                    "size": p.get("size")})
    for q in garden["scatter"]:
        out.append({"src": "garden", "id": f"{q['id']}_{q['kind']}", "at": [q["at"][0], 0.0, q["at"][1]],
                    "yaw": q["yaw"], "scale": q["scale"], "size": q.get("size")})
    for z in zones:
        for p in z:
            out.append({"src": p["src"], "id": p["id"], "at": p["pos"], "yaw": p["yaw"], "size": p.get("size")})
    return out


def resolve(data: dict, raw: Path, p: dict) -> tuple[str, Path] | None:
    """(set id, file name) and the raw source of a placement's GLB, or None (a placeholder)."""
    ex = data["settings"]["export"]
    pl = plot_settings(data)
    if p["src"] == "kit":
        f = raw / data["settings"]["kit_dir"] / f"{p['id']}.glb"
        return ((ex["kit_set"], f"{p['id']}.glb"), f) if f.is_file() else None
    plant = p["id"] if p["src"] == "garden" else pl.get("plants", {}).get(p["id"])  # a zone's generic plant
    if plant:
        f = raw / ex["sets"]["house_garden"]["dir"] / f"{plant}.glb"
        return (("house_garden", f"{plant}.glb"), f) if f.is_file() else None
    order = prop_order(data)
    has = lambda d, pid: (raw / d / f"{pid}.glb").is_file()  # noqa: E731
    dirs = order if p["src"] == "" else [pl.get("prop_src", {}).get(p["src"], "")]
    src = next((d for d in dirs if d and has(d, p["id"])), None)
    if src is None:
        return None
    return (ex["prop_set"], game_name(order, has, src, p["id"])), raw / src / f"{p['id']}.glb"


def scene(data: dict, raw: Path, plot: dict, plot_doc: dict, garden: dict, zones: list[dict]) -> dict:
    """{"text": the scene, "copies": {set/file: raw source}, "walkable": Shell names with a surface, "hide": Dressing
    names, "held": placeholder ids, "counts"}."""
    from . import house_export as X

    ex = data["settings"]["export"]
    sc = H._Scene(ROOT_NODE)
    sc.nodes[0] += '\nmetadata/art_package = 7\nmetadata/coordinates = "plan: x east, z south, ground top y 0"'
    sc.instance("Ground", ".", X.asset_res(data, "house_outdoor", "outdoor"), tf(0, 0, 0, 0))
    sc.instance("Backdrop", ".", X.asset_res(data, "house_outdoor", "backdrop"), tf(0, 0, 0, 0))
    overrides = [f'[node name="{n}" parent="Ground"]\nmetadata/surface = "{s}"' for n, s in ground_surfaces(plot)]
    sc.group("Shell")
    sc.group("Dressing")
    copies: dict[str, Path] = {}
    seen: dict[str, int] = {}
    walkable, hide, held = [], [], []
    for p in placements(plot_doc, garden, zones):
        got = resolve(data, raw, p)
        seen[p["id"]] = seen.get(p["id"], 0) + 1
        name = f"{p['id']}_{seen[p['id']]}"
        x, h, z = (float(v) for v in p["at"])
        if got is None:
            held.append(p["id"])
            if not any(n.startswith('[node name="Placeholders"') for n in sc.nodes):
                sc.group("Placeholders")
            sc.marker(name, "Placeholders", x, h, z, meta={"prop": p["id"], "size": p.get("size"),
                                                            "yaw": p["yaw"], "note": "no GLB yet"})
            continue
        (set_id, fname), src = got
        copies[f"{set_id}/{fname}"] = src
        res = X.asset_res(data, set_id, fname[:-4])
        if p["src"] == "kit":
            surface = X.surface_of(data, p["id"])
            sc.instance(name, "Shell", res, tf(p["yaw"], x, h, z), {"surface": surface} if surface else None)
            if surface:
                walkable.append(name)
        else:
            surface = X.prop_surface(data, p["id"])
            sc.instance(name, "Dressing", res, tf(p["yaw"], x, h, z, float(p.get("scale", 1.0))),
                        {"surface": surface} if surface else None)
            hide.append(name)
    text = sc.text().rstrip("\n") + "\n\n" + "\n\n".join(overrides) + '\n\n[editable path="Ground"]\n'
    counts = {"shell": sum(1 for n in sc.nodes if 'parent="Shell"' in n),
              "dressing": sum(1 for n in sc.nodes if 'parent="Dressing"' in n), "placeholders": len(held)}
    return {"text": text, "copies": copies, "walkable": walkable, "hide": hide, "held": sorted(set(held)),
            "counts": counts, "res": f"res://{ex.get('plot', {}).get('scene', 'levels/house/outdoor.tscn')}"}


def load_inputs(data: dict, raw: Path, build: Path) -> tuple[dict, dict, dict, list[dict]]:
    """The plot's layout, its fresh plan (build/outdoor.json, written by the export), the garden's build and the
    zones' placements."""
    from . import house_outdoor, house_zones
    plot = house_outdoor.load()
    plot_doc = json.loads((build / "outdoor.json").read_text(encoding="utf-8"))
    garden = json.loads((raw / plot_settings(data)["garden"]).read_text(encoding="utf-8"))
    zones = [house_zones.placements(z) for z in house_zones.load_all()]
    return plot, plot_doc, garden, zones
