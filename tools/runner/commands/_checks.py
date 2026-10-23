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
        "morph_epsilon": 0.00001,  # a shape key moves a vertex when it shifts it more than 0.01 mm
    }


def evaluate(
    measure: dict[str, Any],
    kind: str,
    contract: dict[str, Any],
    profile: dict[str, Any],
    bone_map: dict[str, Any] | None = None,
    slot: dict[str, Any] | None = None,
    socketed: bool = False,
) -> dict[str, Any]:
    """With a slot, the slot's budget wins over the kind's (hair_or_hat: head_item, not accessory). socketed: a rigid
    part that sits on a socket in its kit's file, placed by its own transform by design (no transforms_applied)."""
    rules = contract["kinds"][kind]
    budget = (slot or {}).get("budget") or rules["budget"]
    report = _Report()
    meshes = measure.get("meshes", [])
    _mesh_checks(report, meshes, measure, contract, kind, budget, socketed)
    _morph_checks(report, meshes, contract, kind, bone_map, slot)
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


# An alien parts kit (art #226): the slot each group of character.json's `nodes` is judged under. A crest takes the
# hair's place on top of the head, so it is held to the head item's budget.
KIT_SLOTS = {"eyes": "eyes", "mouths": "mouth", "crests": "hair_or_hat"}


def kit_parts(character: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    """The choices of an alien kit's character.json (`nodes`, written by tools/blender/alien_assemble.py and
    alien_mouths.py): {group: {choice: [mesh names shown together]}}. An eye design is both sides' ball and lids
    (the side's group node is an empty); a mouth choice is one piece, 3D or flipbook, with its design's `teeth` when it
    has them; a crest is itself."""
    nodes = character.get("nodes")
    if not isinstance(nodes, dict):
        raise ValueError("not an alien kit: character.json has no `nodes`")
    kit: dict[str, dict[str, list[str]]] = {"eyes": {}, "mouths": {}, "crests": {}}
    for design, sides in sorted(nodes.get("eyes", {}).items()):
        kit["eyes"][design] = [
            name for _, side in sorted(sides.items()) for key, name in sorted(side.items()) if key != "node"
        ]
    for design, pieces in sorted(nodes.get("mouths", {}).items()):
        teeth = [pieces["teeth"]] if "teeth" in pieces else []
        for shape, name in sorted(pieces.items()):
            if shape != "teeth":
                kit["mouths"][name] = [name, *teeth]
    for name in nodes.get("crests", []):
        kit["crests"][name] = [name]
    return kit


def evaluate_kit(
    measure: dict[str, Any],
    kit: dict[str, dict[str, list[str]]],
    contract: dict[str, Any],
    profile: dict[str, Any],
    bone_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """An alien kit GLB judged per part (docs/contract.md, "The alien parts kit"): every mesh the kit does not list
    (`Body`) as `--kind alien` (its height from them alone); each listed mesh alone under its group's slot (KIT_SLOTS:
    the slot's check_kind and budget), rigid on its socket by design; and the shown combination (the body, one eye
    design, one mouth piece, one crest: the largest of each) against the character budget."""
    by_name = {m["name"]: m for m in measure.get("meshes", [])}
    listed = {name for choices in kit.values() for members in choices.values() for name in members}
    body_measure = {**measure, "meshes": [m for m in measure.get("meshes", []) if m["name"] not in listed]}
    report = evaluate(body_measure, "alien", contract, profile, bone_map)
    body_results = report["results"]
    kit_line = _Report()
    kit_line.add(
        "kit",
        PASS,
        f"Body judged as the alien ({', '.join(m['name'] for m in body_measure['meshes']) or 'no mesh'}); "
        + ", ".join(f"{len(choices)} {group}" for group, choices in kit.items())
        + f" judged per part ({len(listed)} meshes)",
    )
    parts: dict[str, Any] = {}
    part_results = _Report()
    for group, choices in kit.items():
        slot = _contract.checkable_slot(contract, KIT_SLOTS[group])
        for name in sorted({n for members in choices.values() for n in members}):
            mesh = by_name.get(name)
            if mesh is None:
                part_results.add(f"part {name}", WARN, f"{group}: listed in the kit but not in the file")
                continue
            alone = {"model": measure.get("model"), "meshes": [mesh], "armatures": [], "empties": [],
                     "other_objects": []}
            part = evaluate(alone, slot["check_kind"], contract, profile, None, slot, socketed=True)
            parts[name] = {k: part[k] for k in ("kind", "slot", "budget", "verdict", "summary", "results")}
            others = [r for r in part["results"] if r["status"] != PASS]
            status = FAIL if part["verdict"] == FAIL else WARN if others else PASS
            # the failures with their detail, the warnings by name (report.json's kit.parts holds every detail)
            notes = "; ".join(f"{r['check']}: {r['detail']}" if r["status"] == FAIL else r["check"] for r in others)
            part_results.add(
                f"part {name}",
                status,
                f"{group} ({slot['id']}, budget {part['budget']}): {mesh['triangles']:,} triangles, "
                f"{mesh['vertices']:,} vertices" + (f"; {notes}" if notes else ""),
            )
    combination = _kit_combination(report["measure"]["meshes"], kit, by_name)
    combo = _Report()
    budget = contract["budgets"]["character"]
    for metric in ("triangles", "vertices"):
        value, target, cap = combination[metric], budget[f"{metric}_target"], budget[f"{metric}_cap"]
        status = FAIL if value > cap else WARN if value > target else PASS
        terms = " + ".join(f"{label} {n:,}" for label, n in combination[f"{metric}_terms"])
        combo.add(
            f"character_{metric}",
            status,
            f"{value:,} = {terms}: the largest shown combination (budget character: target {target:,}, cap {cap:,})",
        )
    results = kit_line.results + body_results + part_results.results + combo.results
    summary = {status: sum(1 for r in results if r["status"] == status) for status in (PASS, WARN, FAIL)}
    report.update(
        verdict=FAIL if summary[FAIL] else PASS,
        summary=summary,
        results=results,
        measure=measure,
        kit={"parts": parts, "combination": combination, "slots": KIT_SLOTS},
    )
    return report


def _kit_combination(body_meshes: list, kit: dict[str, dict[str, list[str]]], by_name: dict) -> dict[str, Any]:
    """What one character shows at most: the body plus, per group, the choice with the most triangles."""
    out: dict[str, Any] = {"choices": {}}
    for metric in ("triangles", "vertices"):
        terms = [("Body" if len(body_meshes) == 1 else "body", _total(body_meshes, metric))]
        for group, choices in kit.items():
            sized = {c: sum(int(by_name[n][metric]) for n in members if n in by_name) for c, members in choices.items()}
            if not sized:
                continue
            biggest = max(sorted(sized), key=lambda c: (_choice_triangles(choices[c], by_name), sized[c]))
            out["choices"][group] = biggest
            terms.append((f"{group.removesuffix('s')} {biggest}", sized[biggest]))
        out[metric] = sum(n for _, n in terms)
        out[f"{metric}_terms"] = terms
    return out


def _choice_triangles(members: list[str], by_name: dict) -> int:
    return sum(int(by_name[n]["triangles"]) for n in members if n in by_name)


def _total(meshes: list[dict[str, Any]], key: str) -> int:
    return sum(int(m.get(key, 0)) for m in meshes)


def _names(meshes: list[dict[str, Any]], key: str) -> str:
    return ", ".join(f"{m['name']} ({m[key]})" for m in meshes if m.get(key))


def _mesh_checks(
    report: _Report, meshes: list, measure: dict, contract: dict, kind: str, budget_name: str, socketed: bool = False
) -> None:
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
    report.add(
        "ngons", FAIL if ngons else PASS, f"{ngons} faces with more than 4 corners {_names(meshes, 'ngons')}".rstrip()
    )
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
    report.add(
        "uvs", FAIL if no_uv else PASS, f"no UV map on {', '.join(no_uv)}" if no_uv else "every mesh has a UV map"
    )
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
    if socketed:
        report.add("transforms_applied", PASS, "a rigid part on its socket: its transform places it, by design")
    else:
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


def _morph_checks(
    report: _Report, meshes: list, contract: dict, kind: str, bone_map: dict | None, slot: dict | None
) -> None:
    """Faces are morphs on the template head (docs/decisions/2026-10-18-faces-as-morphs.md). On a body, a shape key
    is a face morph when every vertex it moves has its largest weight on face.morph_bones (a tie with another bone
    counts as on the head), or on face.edge_bones only (every tied bone an edge bone) moved at most face.edge_mm in a
    key that also moves head skin (a soft jaw or chin morph's edge on the neck): it passes, and more than
    budgets.limits.face_morphs_target on one mesh warn. Any other key is a body-shape
    morph and fails beyond blend_shapes_body (0). On the parts of a slot with part_morphs (the eyes slot's eyeballs:
    their look morphs) those keys pass; any other shape key on clothing, accessories and props warns."""
    keys = _total(meshes, "shape_keys")
    if not keys:
        return
    if kind not in _contract.BODY_KINDS:
        _part_morph_checks(report, meshes, slot)
        return
    face = contract["face"]
    face_bones, edge_bones, edge_mm = set(face["morph_bones"]), set(face["edge_bones"]), face["edge_mm"]
    limits = contract["budgets"]["limits"]
    body_keys: list[str] = []
    face_counts: dict[str, int] = {}
    edge_keys = 0
    for mesh in meshes:
        if not mesh.get("shape_keys"):
            continue
        moves = mesh.get("shape_key_bones")
        if moves is None:  # a measure without the per-key bones: nothing proves a key is a face morph
            body_keys.append(f"{mesh['name']} ({mesh['shape_keys']} keys, not measured per key)")
            continue
        for key, groups in moves.items():
            off, edge, on_head = [], [], False
            for group, moved in sorted(groups.items()):
                bones = {_contract.mapped_name(b, bone_map) for b in group.split("|")} if group else set()
                where = f"{group or 'no bone'} ({moved['vertices']} vertices, up to {moved['max_mm']:g} mm)"
                if bones & face_bones:
                    on_head = True
                elif bones and bones <= edge_bones and moved["max_mm"] <= edge_mm:
                    edge.append((group, where))  # every tied bone an edge bone: a Chest|Neck tie is body skin
                else:
                    off.append((group, where))
            if edge and not on_head:  # the edge is a face morph's soft tail: neck skin alone is a body shape
                off = sorted(off + edge)
            if off:
                body_keys.append(f"{mesh['name']}:{key} moves skin on {', '.join(where for _, where in off)}")
            else:
                face_counts[mesh["name"]] = face_counts.get(mesh["name"], 0) + 1
                edge_keys += bool(edge)
    report.add(
        "body_shape_morphs",
        FAIL if len(body_keys) > limits["blend_shapes_body"] else PASS,
        f"{len(body_keys)} shape keys move skin off the head bones: {'; '.join(body_keys)}"
        if body_keys else "no shape key moves skin off the head bones",
    )
    if face_counts:
        target = limits["face_morphs_target"]
        over = any(n > target for n in face_counts.values())
        edge = (
            f"; {edge_keys} move {', '.join(sorted(edge_bones))} skin by at most {edge_mm:g} mm" if edge_keys else ""
        )
        report.add(
            "face_morphs",
            WARN if over else PASS,
            f"face morphs on {', '.join(f'{n} ({c})' for n, c in sorted(face_counts.items()))}{edge}; "
            f"at most {target} per mesh (provisional)",
        )


def _part_morph_checks(report: _Report, meshes: list, slot: dict | None) -> None:
    """Shape keys on a piece that is not a body: the slot's part_morphs pass, any other key warns."""
    allowed = set((slot or {}).get("part_morphs", []))
    passed: dict[str, int] = {}
    others: dict[str, int] = {}
    for mesh in meshes:
        count = int(mesh.get("shape_keys", 0))
        if not count:
            continue
        good = sum(1 for name in mesh.get("shape_key_bones") or {} if name in allowed)
        if good:
            passed[mesh["name"]] = good
        if count > good:
            others[mesh["name"]] = count - good
    if passed:
        report.add(
            "part_morphs",
            PASS,
            f"the {slot['id']} slot's part morphs on {', '.join(f'{n} ({c})' for n, c in sorted(passed.items()))}",
        )
    if others:
        listed = ", ".join(f"{n} ({c})" for n, c in sorted(others.items()))
        report.add("blend_shapes", WARN, f"{sum(others.values())} shape keys on {listed}")


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
    # head_top_max_m (kinds.alien, art #196 comment 6374319309): the head's top may stand above the capsule; the body
    # below the Head's skin is held to height_max_m by godot-check's contract_height, which has the skin per bone
    top = rules.get("head_top_max_m", body["height_max_m"])
    report.gate(
        "height",
        rules["height"],
        body["height_min_m"] <= height <= top,
        f"{height:.3f} m (contract {body['height_m']} m, allowed {body['height_min_m']} to {top}"
        + (f"; the head may pass the {body['height_max_m']} m capsule, the body may not: godot-check)"
           if "head_top_max_m" in rules else ")"),
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
        rigged = bool(armatures or skinned)
        report.add(
            "rig",
            FAIL if rigged else PASS,
            "a rigid piece must not be rigged" if rigged else "a rigid piece has no armature and no skin",
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
        mapped_parent = _contract.mapped_name(parent, bone_map) if parent else ""
        bones[name] = {**bone, "source": bone["name"], "parent": mapped_parent}
    if duplicates:
        report.add("duplicate_bones", FAIL, f"two bones become {', '.join(sorted(set(duplicates)))} after the map")
    extra = sorted(n for n in bones if n not in parents)
    split = _contract.spring_split(rules, extra, {n: b["parent"] for n, b in bones.items()})
    bad = split["stray"] or split["partial"] or split["outside"]
    if bad:
        detail = (f"not in the profile: {', '.join(extra)}"
                  + (f" (spring sets in part: {split['partial']})" if split["partial"] else "")
                  + (f" (not below {rules.get('spring_parent')}: {split['outside']})" if split["outside"] else ""))
    elif extra:
        detail = f"every bone is a profile bone or in a whole spring set: {', '.join(extra)}"
    else:
        detail = "every bone is a profile bone"
    report.add("extra_bones", FAIL if bad else PASS, detail)
    if rules["bones"] != "subset":
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
    if rules["bones"] != "subset":
        unpainted = [n for n in skeleton["weighted"] if not weights.get(n)]
        report.add(
            "weighted_bones",
            FAIL if unpainted else PASS,
            f"no weights on {', '.join(unpainted)}"
            if unpainted
            else f"all {len(skeleton['weighted'])} bones carry weights",
        )
    if rules["fingers"] != "off":
        _finger_checks(report, bones, weights, skeleton, profile, rules)
    return bones


def _finger_checks(
    report: _Report, bones: dict, weights: dict[str, int], skeleton: dict, profile: dict, rules: dict
) -> None:
    """Every finger chain is present. A finger in the kind's fingers_unweighted (the alien's Little,
    docs/decisions/2026-10-19-alien-overlaid-face-four-fingers.md) carries no weights; the others carry weights when
    skeleton.fingers_weighted is set."""
    bare = rules.get("fingers_unweighted", [])
    problems = []
    for chain, names in _contract.finger_chains(profile).items():
        absent = [n for n in names if n not in bones]
        if absent:
            problems.append(f"{chain} lacks {', '.join(absent)}")
        elif chain.removeprefix("Left").removeprefix("Right") in bare:
            painted = [n for n in names if weights.get(n)]
            if painted:
                problems.append(f"{chain} must carry no weights but is weighted on {', '.join(painted)}")
        elif skeleton.get("fingers_weighted") and not all(weights.get(n) for n in names):
            problems.append(f"{chain} is not weighted on {', '.join(n for n in names if not weights.get(n))}")
    good = "five weighted fingers per hand"
    if bare:
        weighted = [finger for finger in skeleton["fingers"] if finger not in bare]
        good = (
            f"{len(weighted)} weighted fingers per hand ({', '.join(weighted)}); {', '.join(bare)} present and "
            "unweighted"
        )
    report.gate("finger_chains", rules["fingers"], not problems, "; ".join(problems) if problems else good)


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
            detail = (
                f"the toes point to {'+Z' if toes_ahead else '-Z'} and the left hand is at "
                f"{'+X' if left_at_plus_x else '-X'}; the contract wants +Z and +X"
            )
        report.gate("facing", rules["facing"], good, detail)
    else:
        report.gate("facing", rules["facing"], False, "cannot tell: the feet, toes or hands are missing")
