"""Judges a model's measurements (from tools/blender/check_model.py) against the contract: pure Python, so every rule
is testable without Blender. evaluate() returns the report that `check` writes as report.json.

A result's status is "pass", "warn" or "fail"; any "fail" makes the verdict "fail" and `check` exit non-zero.
"""

from __future__ import annotations

from typing import Any

from . import _contract

PASS, WARN, FAIL = "pass", "warn", "fail"


class _Report:
    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []

    def add(self, check: str, status: str, detail: str) -> None:
        if status == "off":
            return
        self.results.append({"check": check, "status": status, "detail": detail})

    def gate(self, check: str, severity: str, good: bool, detail: str) -> None:
        """A check whose failure has the kind's severity ("fail", "warn"); "off" skips it."""
        if severity != "off":
            self.add(check, PASS if good else severity, detail)


def measure_params(contract: dict[str, Any]) -> dict[str, Any]:
    """The thresholds check_model.py needs while it measures."""
    skeleton = contract["skeleton"]
    return {
        "min_weight": skeleton["min_weight"],
        "weight_sum_tolerance": skeleton["weight_sum_tolerance"],
        "max_weights": skeleton["max_weights_per_vertex"],
        "weld_distance": 0.00001,
        "small_island_faces": 4,
    }


def evaluate(
    measure: dict[str, Any],
    kind: str,
    contract: dict[str, Any],
    profile: dict[str, Any],
    bone_map: dict[str, Any] | None = None,
    slot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """With a slot, the slot's budget wins over the kind's (hair_or_hat: head_item, not accessory)."""
    rules = contract["kinds"][kind]
    budget = (slot or {}).get("budget") or rules["budget"]
    report = _Report()
    meshes = measure.get("meshes", [])
    _mesh_checks(report, meshes, measure, contract, kind, budget)
    if meshes:
        _shape_checks(report, meshes, contract, rules)
    bones = _rig_checks(report, measure, kind, contract, profile, rules, bone_map)
    if bones is not None:
        _pose_checks(report, bones, contract, rules)
    counts = {status: sum(1 for r in report.results if r["status"] == status) for status in (PASS, WARN, FAIL)}
    return {
        "model": measure.get("model"),
        "kind": kind,
        "slot": slot["id"] if slot else None,
        "budget": budget,
        "map": bone_map["name"] if bone_map else None,
        "map_confirmed": bone_map.get("confirmed") if bone_map else None,
        "contract_version": contract.get("version"),
        "godot_profile": f"{profile.get('profile')} from Godot {profile.get('godot_version')}",
        "verdict": FAIL if counts[FAIL] else PASS,
        "summary": counts,
        "results": report.results,
        "measure": measure,
    }


def _total(meshes: list[dict[str, Any]], key: str) -> int:
    return sum(int(m.get(key, 0)) for m in meshes)


def _names(meshes: list[dict[str, Any]], key: str) -> str:
    return ", ".join(f"{m['name']} ({m[key]})" for m in meshes if m.get(key))


def _mesh_checks(report: _Report, meshes: list, measure: dict, contract: dict, kind: str, budget_name: str) -> None:
    rules = contract["kinds"][kind]
    if not meshes:
        report.add("meshes", FAIL, "the file has no mesh")
        return
    report.add("meshes", PASS, f"{len(meshes)}: {', '.join(m['name'] for m in meshes)}")
    budget = contract["budgets"][budget_name]
    for metric in ("triangles", "vertices"):
        if f"{metric}_cap" not in budget:
            continue
        value, target, cap = _total(meshes, metric), budget[f"{metric}_target"], budget[f"{metric}_cap"]
        status = FAIL if value > cap else WARN if value > target else PASS
        note = " (a provisional budget)" if budget.get("provisional") else ""
        report.add(metric, status, f"{value:,} (budget {budget_name}: target {target:,}, cap {cap:,}){note}")
    ngons = _total(meshes, "ngons")
    report.add("ngons", FAIL if ngons else PASS, f"{ngons} faces with more than 4 corners {_names(meshes, 'ngons')}".rstrip())
    loose = _total(meshes, "loose_vertices") + _total(meshes, "loose_edges")
    report.add("loose_geometry", FAIL if loose else PASS, f"{loose} vertices or edges without a face")
    bad = _total(meshes, "non_manifold_edges")
    report.add("non_manifold_edges", FAIL if bad else PASS, f"{bad} edges shared by more than two faces")
    open_edges = _total(meshes, "boundary_edges")
    report.add("open_edges", WARN if open_edges else PASS, f"{open_edges} edges on a hole or an open border")
    small = _total(meshes, "small_islands")
    report.add(
        "loose_parts",
        WARN if small else PASS,
        f"{_total(meshes, 'islands')} connected parts, {small} of them debris (fewer than 4 faces)",
    )
    no_uv = [m["name"] for m in meshes if not m.get("uv_layers")]
    report.add("uvs", FAIL if no_uv else PASS, f"no UV map on {', '.join(no_uv)}" if no_uv else "every mesh has a UV map")
    outside = _total(meshes, "uv_loops_out_of_range")
    if outside:
        report.add("uv_range", WARN, f"{outside} UV corners outside 0..1")
    materials = _total(meshes, "materials")
    report.add(
        "materials",
        WARN if materials > rules["max_materials"] else PASS,
        f"{materials} material surfaces (at most {rules['max_materials']})",
    )
    modifiers = sorted({t for m in meshes for t in m.get("modifiers", [])})
    if modifiers:
        report.add("modifiers", WARN, f"unapplied modifiers {', '.join(modifiers)}: apply them before export")
    keys = _total(meshes, "shape_keys")
    if keys:
        report.add("blend_shapes", FAIL if kind == "body" else WARN, f"{keys} shape keys")
    tolerance = contract["body"]["transform_tolerance"]
    unapplied = [
        obj["name"]
        for obj in meshes + measure.get("armatures", [])
        if not _identity(obj["transform"], tolerance)
    ]
    report.add(
        "transforms_applied",
        FAIL if unapplied else PASS,
        f"not applied on {', '.join(unapplied)}" if unapplied else "location 0, rotation 0, scale 1 everywhere",
    )
    if measure.get("other_objects"):
        report.add("other_objects", WARN, f"the file also holds {', '.join(measure['other_objects'])} objects")


def _identity(transform: dict[str, Any], tolerance: float) -> bool:
    return (
        all(abs(c) <= tolerance for c in transform["location"])
        and abs(transform["rotation_deg"]) <= tolerance * 100
        and all(abs(c - 1.0) <= tolerance for c in transform["scale"])
    )


def _shape_checks(report: _Report, meshes: list, contract: dict, rules: dict) -> None:
    body = contract["body"]
    low = min(m["min"][1] for m in meshes)
    high = max(m["max"][1] for m in meshes)
    height = high - low
    report.gate(
        "height",
        rules["height"],
        body["height_min_m"] <= height <= body["height_max_m"],
        f"{height:.3f} m (contract {body['height_m']} m, allowed {body['height_min_m']} to {body['height_max_m']})",
    )
    report.gate(
        "feet_at_zero",
        rules["feet"],
        abs(low) <= body["feet_tolerance_m"],
        f"the lowest point is at y = {low:.4f} m (within {body['feet_tolerance_m']} m of 0)",
    )


def _rig_checks(
    report: _Report,
    measure: dict,
    kind: str,
    contract: dict,
    profile: dict,
    rules: dict,
    bone_map: dict | None,
) -> dict[str, dict[str, Any]] | None:
    """Returns the bones by contract name (after the map), or None without a usable rig."""
    armatures = measure.get("armatures", [])
    meshes = measure.get("meshes", [])
    skinned = [m for m in meshes if m.get("skinned")]
    if rules["rig"] == "forbidden":
        report.add(
            "rig",
            FAIL if armatures or skinned else PASS,
            "a rigid piece has no armature and no skin" if not (armatures or skinned) else "a rigid piece must not be rigged",
        )
        return None
    if len(armatures) != 1:
        report.add("rig", FAIL, f"{len(armatures)} armatures; a {kind} needs exactly one")
        return None
    report.add("rig", PASS, f"armature {armatures[0]['name']} with {len(armatures[0]['bones'])} bones")
    if not skinned:
        report.add("skinned", FAIL, "no mesh is bound to the armature (no Armature modifier)")

    skeleton = contract["skeleton"]
    parents = _contract.profile_parents(profile)
    raw = armatures[0]["bones"]
    by_raw = {b["name"]: b for b in raw}
    raw_weights = _raw_weights(skinned)
    # Like rename-bones: a dropped bone's weights move to its nearest kept ancestor; with none, a weighted one stays.
    heirs = _heirs(raw, bone_map)
    dropped = [n for n, heir in heirs.items() if heir or not raw_weights.get(n)]
    if dropped:
        moved = [f"{n} to {heirs[n]}" for n in dropped if raw_weights.get(n)]
        note = f"; weights move from {', '.join(moved)}" if moved else ""
        report.add("dropped_bones", WARN, f"rename-bones would delete {', '.join(dropped)}{note}")
    bones: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for bone in raw:
        if bone["name"] in dropped:
            continue
        name = _contract.mapped_name(bone["name"], bone_map)
        if name in bones:
            duplicates.append(name)
        parent = bone["parent"]
        while parent in dropped:
            parent = by_raw[parent]["parent"]
        bones[name] = {**bone, "source": bone["name"], "parent": _contract.mapped_name(parent, bone_map) if parent else ""}
    if duplicates:
        report.add("duplicate_bones", FAIL, f"two bones become {', '.join(sorted(set(duplicates)))} after the map")
    extra = sorted(n for n in bones if n not in parents)
    report.add(
        "extra_bones",
        FAIL if extra else PASS,
        f"not in the profile: {', '.join(extra)}" if extra else "every bone is a profile bone",
    )
    if rules["bones"] == "all":
        missing = [n for n in parents if n not in bones]
        report.add(
            "missing_bones",
            FAIL if missing else PASS,
            f"missing: {', '.join(missing)}" if missing else f"all {len(parents)} profile bones are present",
        )
    wrong = [
        f"{n} under {b['parent'] or 'nothing'} (profile: {parents[n] or 'nothing'})"
        for n, b in bones.items()
        if n in parents and b["parent"] != parents[n] and (b["parent"] or parents[n] in bones)
    ]
    report.add("bone_parents", FAIL if wrong else PASS, "; ".join(wrong) if wrong else "parents match the profile")

    weights: dict[str, int] = {}
    for name, count in raw_weights.items():
        target = _contract.mapped_name(heirs[name] if name in dropped else name, bone_map)
        weights[target] = weights.get(target, 0) + count
    over = sum(m["weights"]["vertices_over_limit"] for m in skinned)
    report.add(
        "weights_per_vertex",
        FAIL if over else PASS,
        f"{over} vertices with more than {skeleton['max_weights_per_vertex']} influences (max seen "
        f"{max((m['weights']['max_influences'] for m in skinned), default=0)})",
    )
    unweighted = sum(m["weights"]["unweighted_vertices"] for m in skinned)
    report.add("unweighted_vertices", FAIL if unweighted else PASS, f"{unweighted} skinned vertices without a weight")
    below = sum(m["weights"]["vertices_below_min_weight"] for m in skinned)
    if below:
        report.add("tiny_weights", WARN, f"{below} vertices with an influence below {skeleton['min_weight']}")
    unnormalized = sum(m["weights"]["vertices_not_normalized"] for m in skinned)
    if unnormalized:
        report.add("weights_normalized", WARN, f"{unnormalized} vertices whose weights do not sum to 1")
    stray = sorted({g for m in skinned for g in m["weights"]["groups_without_bone"]})
    if stray:
        report.add("stray_vertex_groups", WARN, f"vertex groups without a bone: {', '.join(stray)}")
    root = skeleton["root"]
    report.add(
        "root_unweighted",
        FAIL if weights.get(root) else PASS,
        f"{root} carries weights on {weights[root]} vertices" if weights.get(root) else f"{root} carries no weights",
    )
    if rules["bones"] == "all":
        unpainted = [n for n in skeleton["weighted"] if not weights.get(n)]
        report.add(
            "weighted_bones",
            FAIL if unpainted else PASS,
            f"no weights on {', '.join(unpainted)}" if unpainted else f"all {len(skeleton['weighted'])} bones carry weights",
        )
    if rules["fingers"] != "off":
        problems = []
        for chain, names in _contract.finger_chains(profile).items():
            absent = [n for n in names if n not in bones]
            if absent:
                problems.append(f"{chain} lacks {', '.join(absent)}")
            elif skeleton.get("fingers_weighted") and not all(weights.get(n) for n in names):
                problems.append(f"{chain} is not weighted on {', '.join(n for n in names if not weights.get(n))}")
        report.gate(
            "finger_chains",
            rules["fingers"],
            not problems,
            "; ".join(problems) if problems else "five weighted fingers per hand",
        )
    return bones


def _raw_weights(skinned: list[dict[str, Any]]) -> dict[str, int]:
    """Weighted vertex counts per bone, by the bone names in the file, summed over the skinned meshes."""
    weights: dict[str, int] = {}
    for mesh in skinned:
        for name, count in mesh["weights"]["weighted_bones"].items():
            weights[name] = weights.get(name, 0) + count
    return weights


def _heirs(raw: list[dict[str, Any]], bone_map: dict | None) -> dict[str, str]:
    """Each bone the map drops -> its nearest ancestor the map keeps ("" when there is none), by file names."""
    parents = {b["name"]: b["parent"] for b in raw}
    heirs: dict[str, str] = {}
    for bone in raw:
        if not _contract.is_dropped(bone["name"], bone_map):
            continue
        parent = bone["parent"]
        while parent and _contract.is_dropped(parent, bone_map):
            parent = parents.get(parent, "")
        heirs[bone["name"]] = parent
    return heirs


def _pose_checks(report: _Report, bones: dict[str, dict[str, Any]], contract: dict, rules: dict) -> None:
    body = contract["body"]
    eyes = [bones[n]["head"][1] for n in ("LeftEye", "RightEye") if n in bones]
    if eyes:
        eye = sum(eyes) / len(eyes)
        report.gate(
            "eye_height",
            rules["eyes"],
            abs(eye - body["eye_height_m"]) <= body["eye_tolerance_m"],
            f"eyes at {eye:.3f} m (contract {body['eye_height_m']} +- {body['eye_tolerance_m']} m)",
        )
    else:
        report.gate("eye_height", rules["eyes"], False, "no eye bones to measure")
    needed = ("LeftFoot", "LeftToes", "RightFoot", "RightToes", "LeftHand", "RightHand")
    if all(n in bones for n in needed):
        toes_ahead = all(bones[f"{s}Toes"]["head"][2] > bones[f"{s}Foot"]["head"][2] for s in ("Left", "Right"))
        left_at_plus_x = bones["LeftHand"]["head"][0] > bones["RightHand"]["head"][0]
        good = toes_ahead and left_at_plus_x
        detail = "front +Z: the toes point to +Z and the left hand is at +X"
        if not good:
            detail = f"the toes point to {'+Z' if toes_ahead else '-Z'} and the left hand is at {'+X' if left_at_plus_x else '-X'}; the contract wants +Z and +X"
        report.gate("facing", rules["facing"], good, detail)
    else:
        report.gate("facing", rules["facing"], False, "cannot tell: the feet, toes or hands are missing")
