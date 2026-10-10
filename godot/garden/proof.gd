extends "res://outdoor/proof.gd"
## The garden and the greenhouse in Godot for `tools/run.py garden --proof` (art #80, docs/house-garden.md): the
## outdoor proof's plot, sky and backdrop (res://outdoor/proof.gd) plus the layout engine's house scene (the greenhouse's
## glass walls and dressing), and the garden's layer: the glass roof from garden.json, the garden's props and the
## scatter plants, each GLB as one MultiMesh per mesh (colliders per placement); stand-in lamps; the walks (every
## garden path, the herb route from the kitchen), the glass roof's ray test and the pictures with their draw calls
## (all, and the garden layer's: the difference when it is hidden).
## Pictures need a real window placed off-screen (the runner passes --position -30000,-30000), never headless:
##   godot --path godot --position -30000,-30000 --resolution 1600x900 -s res://garden/proof.gd -- <request.json> <out>
## request.json (tools/runner/house_garden_scene.py): the outdoor proof's keys and "house": res, "roof": [[id, at,
##   yaw]], "props": [[res, at, yaw]], "plants": {res: [[x, z, yaw, scale]]}, "rays": {"rect", "step", "inset",
##   "from_h", "level_step", "gable_tol", "control"}, "no_shadow": [res], "draw_call_limit".
## Writes <out>/<view>.png, sheet.png (1280 px wide, rows of three) and proof.json (the walks, the rays, per view its
## draw calls, primitives and objects, and the garden layer's draw calls and primitives); prints PROOF saved <dir>.

const ROOF_LAYER: int = 2  # the glass roof's trimesh colliders for the rays (bit 2); the walks use layer 1

var _views: Dictionary = {}
var _layer: Node3D


func _run(args: PackedStringArray) -> void:
	var request: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if typeof(request) != TYPE_DICTIONARY:
		_fail("cannot read %s" % args[0])
		return
	_req = request
	_out = args[1]
	DirAccess.make_dir_recursive_absolute(_out)
	var pack: Dictionary = _req.get("pack", {})
	if not pack.is_empty():
		_set = KitMaterials.make(pack["textures"], pack)
	_environment()
	_build()
	_garden()
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.far = 600.0
	root.add_child(_camera)
	_camera.make_current()
	var layer: CanvasLayer = CanvasLayer.new()
	_label = Label.new()
	_label.position = Vector2(16, 10)
	_label.add_theme_font_size_override("font_size", 44)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 8)
	layer.add_child(_label)
	root.add_child(layer)
	for i: int in 3:
		await physics_frame
	var result: Dictionary = {"walks": {}, "leaves": _leaves.size(), "views": _views,
		"draw_call_limit": int(_req.get("draw_call_limit", 150))}
	result["rays"] = _rays(_req["rays"])
	var walks: Dictionary = _req["walks"]
	for name: String in walks:
		var w: Dictionary = walks[name]
		await _set_leaves(w.get("leaves", "open"))
		result["walks"][name] = await _walk(float(w["r"]), w["points"].map(_v), bool(w["must_pass"]))
	await _set_leaves("closed")
	var shots: Array[Image] = []
	for s: Array in _req["views"]:
		shots.append(await _view(s[0], s[1], _v(s[2]), _v(s[3])))
		var all: Array = _counts()
		_layer.visible = false
		for i: int in 4:
			await process_frame
		await RenderingServer.frame_post_draw
		var rest: Array = _counts()
		_layer.visible = true
		_views[s[0]] = {"draw_calls": all[0], "primitives": all[1], "objects": all[2],
			"garden_draw_calls": all[0] - rest[0], "garden_primitives": all[1] - rest[1]}
	var rows: Array = []
	for i: int in range(0, shots.size(), 3):
		rows.append(shots.slice(i, i + 3))
	_save(_sheet(rows), _out.path_join("sheet.png"))
	var f: FileAccess = FileAccess.open(_out.path_join("proof.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(result, " "))
	f.close()
	print("PROOF saved %s" % _out)
	quit(0)


func _counts() -> Array:
	return [int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)),
		int(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)),
		int(Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME))]


# --- the garden's additions ----------------------------------------------------------------------------------------
## The house scene, then the garden's layer (`_layer`, hidden per view to count its draw calls): the glass roof, the
## props and the plants, each GLB as one MultiMesh per mesh over all its placements (its glass apart, without shadow).
func _garden() -> void:
	var house: Node3D = _load(_req["house"])
	root.add_child(house)
	_find_leaves(house)
	_layer = Node3D.new()
	_layer.name = "GardenLayer"
	root.add_child(_layer)
	var groups: Dictionary = {}  # res: [transforms, is roof]
	for r: Array in _req["roof"]:
		_group(groups, _req["pieces"][r[0]], _xform(r[1], float(r[2]), 1.0), true)
	for p: Array in _req["props"]:
		_group(groups, p[0], _xform(p[1], float(p[2]), 1.0), false)
	var plants: Dictionary = _req["plants"]
	for res: String in plants:
		for q: Array in plants[res]:
			_group(groups, res, _xform([q[0], 0.0, q[1]], float(q[2]), float(q[3])), false)
	for res: String in groups:
		_multi(res, groups[res][0], groups[res][1], res in _req.get("no_shadow", []))


func _group(groups: Dictionary, res: String, x: Transform3D, roof: bool) -> void:
	if not groups.has(res):
		groups[res] = [[], roof]
	groups[res][0].append(x)


func _xform(at: Variant, yaw: float, scale: float) -> Transform3D:
	return Transform3D(Basis(UP, deg_to_rad(yaw)).scaled(Vector3.ONE * scale), _v(at))


## One MultiMeshInstance3D per mesh of the GLB over the transforms (the kit pack's surface overrides baked into a copy
## of the mesh); per transform a StaticBody3D with the GLB's collision shapes, and for the roof a trimesh collider per
## mesh on ROOF_LAYER for the rays.
func _multi(res: String, xforms: Array, roof: bool, no_shadow: bool) -> void:
	var proto: Node3D = _load(res)
	if roof and _set != null:
		KitMaterials.apply(proto, _set)
	for n: Node in [proto] + proto.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n as MeshInstance3D
		if mi == null or mi.mesh == null:
			continue
		var mesh: Mesh = mi.mesh
		for s: int in mesh.get_surface_count():
			if mi.get_surface_override_material(s) != null:
				if mesh == mi.mesh:
					mesh = mi.mesh.duplicate() as Mesh
				mesh.surface_set_material(s, mi.get_surface_override_material(s))
		var local: Transform3D = _rel(mi, proto)
		for part: Array in _parts(mesh):
			var mm: MultiMesh = MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.mesh = part[0]
			mm.instance_count = xforms.size()
			for i: int in xforms.size():
				mm.set_instance_transform(i, (xforms[i] as Transform3D) * local)
			var mmi: MultiMeshInstance3D = MultiMeshInstance3D.new()
			mmi.multimesh = mm
			if part[1] or no_shadow:
				mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			_layer.add_child(mmi)
		if roof:
			var shape: Shape3D = mi.mesh.create_trimesh_shape()
			for x: Transform3D in xforms:
				var body: StaticBody3D = StaticBody3D.new()
				body.collision_layer = ROOF_LAYER
				body.collision_mask = 0
				body.transform = x * local
				var cs: CollisionShape3D = CollisionShape3D.new()
				cs.shape = shape
				body.add_child(cs)
				root.add_child(body)
	var shapes: Array = proto.find_children("*", "CollisionShape3D", true, false)
	if shapes.is_empty():
		return
	for x: Transform3D in xforms:
		var body: StaticBody3D = StaticBody3D.new()
		body.transform = x
		for c: Node in shapes:
			var cs: CollisionShape3D = CollisionShape3D.new()
			cs.shape = (c as CollisionShape3D).shape
			cs.transform = _rel(c as Node3D, proto)
			body.add_child(cs)
		root.add_child(body)


## The mesh as [mesh, clear] parts: the mesh itself when its surfaces are all opaque or all clear, else its opaque
## surfaces and its clear (glass) ones apart, so that glass casts no shadow (a pane lets the sun through, and its
## shadow passes are draw calls the garden's budget does not need).
func _parts(mesh: Mesh) -> Array:
	var solid: Array[int] = []
	var clear: Array[int] = []
	for s: int in mesh.get_surface_count():
		var mat: Material = mesh.surface_get_material(s)
		if mat is BaseMaterial3D and (mat as BaseMaterial3D).transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
			clear.append(s)
		else:
			solid.append(s)
	if solid.is_empty() or clear.is_empty():
		return [[mesh, solid.is_empty()]]
	return [[_subset(mesh, solid), false], [_subset(mesh, clear), true]]


func _subset(mesh: Mesh, surfaces: Array[int]) -> ArrayMesh:
	var out: ArrayMesh = ArrayMesh.new()
	for s: int in surfaces:
		out.add_surface_from_arrays(mesh.surface_get_primitive_type(s), mesh.surface_get_arrays(s))
		out.surface_set_material(out.get_surface_count() - 1, mesh.surface_get_material(s))
	return out


func _rel(n: Node3D, top: Node) -> Transform3D:
	if n == top:
		return Transform3D.IDENTITY
	var t: Transform3D = n.transform
	var p: Node = n.get_parent()
	while p != null and p != top:
		if p is Node3D:
			t = (p as Node3D).transform * t
		p = p.get_parent()
	return t


# --- the glass roof's ray test -------------------------------------------------------------------------------------
func _hit(from: Vector3, to: Vector3) -> Dictionary:
	var q: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(from, to, ROOF_LAYER)
	q.hit_back_faces = true
	return root.get_world_3d().direct_space_state.intersect_ray(q)


## Up from inside on a grid; up along both gables `inset` in (each hit's height is that z's roof); level from the
## middle out through each gable below that height every `level_step`: each must hit within `gable_tol` of the gable.
func _rays(r: Dictionary) -> Dictionary:
	var x0: float = float(r["rect"][0])
	var z0: float = float(r["rect"][1])
	var w: float = float(r["rect"][2])
	var d: float = float(r["rect"][3])
	var step: float = float(r["step"])
	var h0: float = float(r["from_h"])
	var out: Dictionary = {"up": 0, "up_hit": 0, "gable_up": 0, "gable_up_hit": 0, "level": 0, "level_hit": 0,
		"misses": [], "control_hit": false}
	var x: float = x0 + step / 2.0
	while x < x0 + w:
		var z: float = z0 + step / 2.0
		while z < z0 + d:
			out["up"] += 1
			if _hit(Vector3(x, h0, z), Vector3(x, 20.0, z)).is_empty():
				out["misses"].append("up at x %.2f z %.2f" % [x, z])
			else:
				out["up_hit"] += 1
			z += step
		x += step
	var tol: float = float(r["gable_tol"])
	for side: float in [-1.0, 1.0]:
		var gx: float = x0 if side < 0.0 else x0 + w
		var inner: float = gx - side * float(r["inset"])
		var z: float = z0 + step / 2.0
		while z < z0 + d:
			out["gable_up"] += 1
			var up: Dictionary = _hit(Vector3(inner, h0, z), Vector3(inner, 20.0, z))
			if up.is_empty():
				out["misses"].append("gable up at x %.2f z %.2f" % [inner, z])
			else:
				out["gable_up_hit"] += 1
				var top: float = (up["position"] as Vector3).y - 0.1
				var h: float = h0 + 0.05
				while h < top:
					out["level"] += 1
					var lv: Dictionary = _hit(Vector3(x0 + w / 2.0, h, z), Vector3(gx + side * 3.0, h, z))
					if lv.is_empty() or absf((lv["position"] as Vector3).x - gx) > tol:
						out["misses"].append("level through x %.0f at z %.2f h %.2f%s" % [gx, z, h,
							"" if lv.is_empty() else " (hit x %.2f)" % (lv["position"] as Vector3).x])
					else:
						out["level_hit"] += 1
					h += float(r["level_step"])
			z += step
	var c: Vector3 = _v(r["control"])
	out["control_hit"] = not _hit(c, c + Vector3(0, 20, 0)).is_empty()
	return out
