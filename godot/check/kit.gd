extends SceneTree
## Describes imported kit pieces for `tools/run.py kit` (docs/kit.md); the runner makes the assertions.
## Headless:
##   godot --headless --path godot -s res://check/kit.gd -- <request.json> <out.json>
## request.json: {"pieces": {"<id>": {"scene": "res://import/kit_<id>.glb", "rays": [[from xyz, to xyz], ...]}}}.
## Per piece: the visual meshes (surfaces, UV2, vertex colour as albedo, triangles, world bounds), the static bodies
## and their shapes (class, convex point count), each ray's first hit (the piece alone in the physics world) and the
## `LightAnchor*` nodes' positions (the dressing library's fixtures, `props`).
## Prints KIT saved <path>, or KIT error <why> and exits 1.

const WATCHDOG_S: float = 240.0


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 2:
		_fail("usage: -- <request.json> <out.json>")
		return
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	_run(args)


func _run(args: PackedStringArray) -> void:
	var text: String = FileAccess.get_file_as_string(args[0])
	var request: Variant = JSON.parse_string(text)
	if typeof(request) != TYPE_DICTIONARY:
		_fail("cannot read %s" % args[0])
		return
	var out: Dictionary = {"godot": Engine.get_version_info()["string"], "pieces": {}}
	for id: String in request["pieces"]:
		var job: Dictionary = request["pieces"][id]
		var packed: PackedScene = load(job["scene"]) as PackedScene
		if packed == null:
			out["pieces"][id] = {"error": "cannot load %s" % job["scene"]}
			continue
		var scene: Node3D = packed.instantiate() as Node3D
		root.add_child(scene)
		await physics_frame
		await physics_frame
		out["pieces"][id] = _describe(scene, job.get("rays", []))
		scene.queue_free()
		await process_frame
	var f: FileAccess = FileAccess.open(args[1], FileAccess.WRITE)
	f.store_string(JSON.stringify(out, " "))
	f.close()
	print("KIT saved %s" % args[1])
	quit(0)


func _describe(scene: Node3D, rays: Array) -> Dictionary:
	var meshes: Array = []
	var bodies: Array = []
	var anchors: Array = []
	var lo := Vector3(INF, INF, INF)
	var hi := Vector3(-INF, -INF, -INF)
	for n: Node in _all(scene):
		if n is MeshInstance3D:
			var mi: MeshInstance3D = n
			var surfaces: Array = []
			var tris: int = 0
			for s: int in mi.mesh.get_surface_count():
				var fmt: int = mi.mesh.surface_get_format(s)
				var arr: Array = mi.mesh.surface_get_arrays(s)
				var count: int = (arr[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3 if arr[Mesh.ARRAY_INDEX] != null else (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
				tris += count
				var mat: Material = mi.get_active_material(s)
				var vc: bool = mat is BaseMaterial3D and (mat as BaseMaterial3D).vertex_color_use_as_albedo
				surfaces.append({
					"material": mat.resource_name if mat else "",
					"uv2": (fmt & Mesh.ARRAY_FORMAT_TEX_UV2) != 0,
					"color": (fmt & Mesh.ARRAY_FORMAT_COLOR) != 0,
					"vertex_colour_albedo": vc,
					"vertex_colour_srgb": mat is BaseMaterial3D and (mat as BaseMaterial3D).vertex_color_is_srgb,
					"transparent": mat is BaseMaterial3D and (mat as BaseMaterial3D).transparency != BaseMaterial3D.TRANSPARENCY_DISABLED,
					"triangles": count,
				})
			var box: AABB = mi.global_transform * mi.get_aabb()
			lo = lo.min(box.position)
			hi = hi.max(box.end)
			meshes.append({"name": str(mi.name), "path": str(scene.get_path_to(mi)), "triangles": tris, "surfaces": surfaces})
		elif n is StaticBody3D:
			var shapes: Array = []
			for c: Node in n.get_children():
				if c is CollisionShape3D and (c as CollisionShape3D).shape != null:
					var sh: Shape3D = (c as CollisionShape3D).shape
					var pts: int = (sh as ConvexPolygonShape3D).points.size() if sh is ConvexPolygonShape3D else 0
					shapes.append({"class": sh.get_class(), "points": pts})
			bodies.append({"name": str(n.name), "parent": str(n.get_parent().name), "shapes": shapes})
		elif n is Node3D and str(n.name).begins_with("LightAnchor"):
			var at: Vector3 = (n as Node3D).global_position
			anchors.append({"name": str(n.name), "position": [at.x, at.y, at.z]})
	var space: PhysicsDirectSpaceState3D = scene.get_world_3d().direct_space_state
	var hits: Array = []
	for r: Array in rays:
		var q := PhysicsRayQueryParameters3D.create(_v(r[0]), _v(r[1]))
		var hit: Dictionary = space.intersect_ray(q)
		hits.append([hit["position"].x, hit["position"].y, hit["position"].z] if hit else null)
	return {
		"meshes": meshes, "bodies": bodies, "hits": hits, "anchors": anchors,
		"bounds": {"min": [lo.x, lo.y, lo.z], "max": [hi.x, hi.y, hi.z]},
	}


func _v(a: Array) -> Vector3:
	return Vector3(a[0], a[1], a[2])


func _all(n: Node) -> Array:
	var out: Array = [n]
	for c: Node in n.get_children():
		out.append_array(_all(c))
	return out


func _fail(why: String) -> void:
	printerr("KIT error %s" % why)
	quit(1)
