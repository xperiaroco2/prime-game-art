extends SceneTree
## The lobby package's check (`lobby --export DIR`, art #356 step 5b, docs/lobby.md "The export"): runs in the export
## folder opened as its own Godot project (the runner copies this file to DIR/_check/ and the ship package beside the
## lobby's files), against the packages alone.
##   check (headless): godot --headless --path DIR -s res://_check/export_check.gd -- check <request.json> <out dir>
##     measures each hall GLB at the origin (bounds, colliders), loads res://levels/lobby/lobby_hall.tscn and reads its
##     tree (spawns, the ship instance and what is switched off, the jaws, the ship's layers, the Earth), then walks the
##     1.36 m capsule through the layout's walk points; <out>/load.json.
##   shoot (an off-screen window, through the runner's _godot.window(), never by hand): -- shoot <request.json> <out>
##     the views as hall.gd shoots them (the title label, 30 frames, the GPU median of the last 16), each beside the
##     reference shot of `lobby --shoot`: the mean absolute difference (0..255) and the share of pixels off by more
##     than 16; <out>/shots.json.
## request.json: {"scene", "pieces": {id: res}, "walk": {"r", "h", "points"}, "views": [[name, title, eye, look, fov]],
##   "refs": dir of the reference PNGs}.

const Offscreen = preload("res://lib/offscreen.gd")
const SPEED: float = 3.0
const DIFF_PX: int = 16
const SHIP_LAYER: int = 1 << 10

var _req: Dictionary
var _out: String


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 3:
		_fail("usage: -- check|shoot <request.json> <out dir>")
		return
	_req = JSON.parse_string(FileAccess.get_file_as_string(args[1]))
	_out = args[2]
	DirAccess.make_dir_recursive_absolute(_out)
	create_timer(240.0).timeout.connect(_fail.bind("not done within 240 s"))
	if args[0] == "shoot":
		var placed: String = Offscreen.place()
		if placed != "":
			_fail(placed)
			return
		_shoot.call_deferred()
	else:
		_check.call_deferred()


func _scene() -> Node3D:
	var packed: PackedScene = load(_req["scene"]) as PackedScene
	if packed == null:
		return null
	var level: Node3D = packed.instantiate() as Node3D
	root.add_child(level)
	return level


func _check() -> void:
	var result: Dictionary = {"bounds": {}, "colliders": {}, "scripts": []}
	for pid: String in _req["pieces"]:
		var scene: PackedScene = load(_req["pieces"][pid]) as PackedScene
		if scene == null:
			_fail("cannot load %s" % _req["pieces"][pid])
			return
		var m: Array = _measure(scene.instantiate() as Node3D)
		var box: AABB = m[0]
		result["bounds"][pid] = {"min": [box.position.x, box.position.y, box.position.z],
			"max": [box.end.x, box.end.y, box.end.z]}
		result["colliders"][pid] = m[1]
	var level: Node3D = _scene()
	if level == null:
		_fail("cannot load %s" % _req["scene"])
		return
	await physics_frame
	await physics_frame
	result["root"] = String(level.name)
	result["meta"] = {}
	for k: StringName in level.get_meta_list():
		result["meta"][String(k)] = var_to_str(level.get_meta(k))
	result["groups"] = level.get_children().map(func(n: Node) -> String: return String(n.name))
	for n: Node in level.find_children("*", "", true, false):
		if n.get_script() != null:
			result["scripts"].append(String(n.name))
	result["spawns"] = []
	for m: Node in level.get_node("Markers").get_children():
		var mk: Node3D = m as Node3D
		var fwd: Vector3 = -mk.global_transform.basis.z
		result["spawns"].append({"name": String(mk.name), "at": [mk.global_position.x, mk.global_position.y, mk.global_position.z],
			"yaw": snappedf(mk.rotation_degrees.y, 0.001), "forward": [snappedf(fwd.x, 0.001), snappedf(fwd.y, 0.001), snappedf(fwd.z, 0.001)]})
	var ship: Node3D = level.get_node("Ship") as Node3D
	var clearing: Node3D = ship.get_node("Clearing") as Node3D
	var own: Environment = (level.get_node("Environment").get_child(0) as WorldEnvironment).environment
	var worlds: Array = ship.find_children("*", "WorldEnvironment", true, false).filter(func(w: Node) -> bool: return (w as WorldEnvironment).environment not in [null, own])
	var suns: Array = ship.get_node("Lights").find_children("*", "DirectionalLight3D", true, false).filter(func(l: Node) -> bool: return (l as Node3D).is_visible_in_tree())
	var info: Dictionary = {"scene": ship.scene_file_path, "at": [ship.position.x, ship.position.y, ship.position.z],
		"clearing_visible": clearing.is_visible_in_tree(), "clearing_processing": clearing.can_process(),
		"environments": worlds.size(), "suns_visible": suns.size(),
		"jaws": {}, "colliders_on": 0, "colliders_off": 0, "off_layer": 0, "meshes": 0, "lights_visible": 0}
	for j: String in ["jaw_lower", "jaw_upper"]:
		var jn: Node3D = ship.get_node("Nose").find_child(j, true, false) as Node3D
		info["jaws"][j] = snappedf(jn.rotation_degrees.x, 0.001) if jn != null else null
	for n: Node in ship.find_children("*", "", true, false):
		if n is CollisionShape3D and (n as CollisionShape3D).shape != null:
			info["colliders_on" if n.get_parent().can_process() else "colliders_off"] += 1
		if n is GeometryInstance3D and (n as Node3D).is_visible_in_tree():
			info["meshes"] += 1
			if (n as GeometryInstance3D).layers != SHIP_LAYER:
				info["off_layer"] += 1
		if n is Light3D and (n as Node3D).is_visible_in_tree():
			info["lights_visible"] += 1
	result["ship"] = info
	var earth: MeshInstance3D = level.get_node_or_null("Earth/EarthObject") as MeshInstance3D
	result["earth"] = {}
	if earth != null:
		var mat: ShaderMaterial = earth.material_override as ShaderMaterial
		result["earth"] = {"far_mode": float(mat.get_shader_parameter("far_mode")), "shell_m": (earth.mesh as SphereMesh).radius,
			"at": [earth.position.x, earth.position.y, earth.position.z],
			"textures": ["night_tex", "day_tex", "cloud_tex", "night_cap_tex", "cloud_cap_tex"].map(func(k: String) -> String:
				var t: Texture2D = mat.get_shader_parameter(k) as Texture2D
				return "" if t == null else "%s %dx%d" % [t.resource_path, t.get_width(), t.get_height()])}
	result["lights"] = level.get_node("Lights").get_child_count()
	result["probes"] = level.get_node("Probes").get_child_count()
	var pts: Array = (_req["walk"]["points"] as Array).map(func(p: Array) -> Vector3: return _v(p))
	result["walk"] = await _walk(float(_req["walk"]["r"]), float(_req["walk"]["h"]), pts)
	_write("load.json", result)
	print("LOBBY export check saved %s" % _out)
	quit(0)


## A piece's bounds at the origin (its meshes' AABBs in its frame) and its collision shapes (ship.gd _measure).
func _measure(node: Node3D) -> Array:
	var box: AABB = AABB()
	var first: bool = true
	var colliders: int = 0
	var stack: Array = [[node, Transform3D.IDENTITY]]
	while not stack.is_empty():
		var item: Array = stack.pop_back()
		var n: Node = item[0]
		var t: Transform3D = item[1]
		if n is MeshInstance3D and (n as MeshInstance3D).mesh != null:
			var b: AABB = t * (n as MeshInstance3D).mesh.get_aabb()
			box = b if first else box.merge(b)
			first = false
		if n is CollisionShape3D and (n as CollisionShape3D).shape != null:
			colliders += 1
		for c: Node in n.get_children():
			stack.append([c, t * (c as Node3D).transform if c is Node3D else t])
	node.free()
	return [box, colliders]


## The capsule walk of ship.gd _walk: 3 m/s with gravity through the points; arrives at the last within 0.3 m and
## its height within 0.15 m.
func _walk(r: float, h: float, points: Array) -> Dictionary:
	var body: CharacterBody3D = CharacterBody3D.new()
	var shape: CollisionShape3D = CollisionShape3D.new()
	var cap: CapsuleShape3D = CapsuleShape3D.new()
	cap.radius = r
	cap.height = h
	shape.shape = cap
	shape.position.y = h / 2.0
	body.add_child(shape)
	body.floor_snap_length = 0.3
	root.add_child(body)
	body.global_position = (points[0] as Vector3) + Vector3(0, 0.05, 0)
	var length: float = 0.0
	for i: int in points.size() - 1:
		length += (points[i + 1] as Vector3).distance_to(points[i])
	var limit: int = int((length / SPEED + 8.0) * Engine.physics_ticks_per_second)
	var reached: int = 0
	var dt: float = 1.0 / Engine.physics_ticks_per_second
	var steps: int = 0
	var min_y: float = 99.0
	var last_move: int = 0
	var last_pos: Vector3 = body.global_position
	var rooms: Array = []
	while steps < limit and reached < points.size() - 1:
		await physics_frame
		steps += 1
		var target: Vector3 = points[reached + 1]
		var flat: Vector3 = Vector3(target.x - body.global_position.x, 0, target.z - body.global_position.z)
		if flat.length() < 0.3:
			reached += 1
			rooms.append([snappedf(body.global_position.x, 0.01), snappedf(body.global_position.z, 0.01)])
			continue
		var v: Vector3 = flat.normalized() * SPEED
		v.y = 0.0 if body.is_on_floor() else body.velocity.y - 9.8 * dt
		body.velocity = v
		body.move_and_slide()
		min_y = minf(min_y, body.global_position.y)
		if body.global_position.distance_to(last_pos) > 0.05:
			last_pos = body.global_position
			last_move = steps
		elif steps - last_move > 2 * Engine.physics_ticks_per_second:
			break
	var end: Vector3 = body.global_position
	var arrived: bool = reached == points.size() - 1 and absf(end.y - (points[-1] as Vector3).y) < 0.15
	body.queue_free()
	return {"radius_m": r, "of": points.size(), "reached": reached + 1, "end": [end.x, end.y, end.z],
		"min_y": min_y, "seconds": steps * dt, "arrived": arrived, "stuck": [last_pos.x, last_pos.y, last_pos.z],
		"passed": rooms}


func _shoot() -> void:
	var level: Node3D = _scene()
	if level == null:
		_fail("cannot load %s" % _req["scene"])
		return
	var vp_node: Viewport = root
	vp_node.positional_shadow_atlas_size = 4096   # hall.gd _apply_light's (HANDOFF "Light")
	for q: int in 4:
		vp_node.set_positional_shadow_atlas_quadrant_subdiv(q, Viewport.SHADOW_ATLAS_QUADRANT_SUBDIV_4)
	var camera: Camera3D = Camera3D.new()
	camera.near = 0.05
	camera.far = float(level.get_meta("camera_far_m", 400.0))
	root.add_child(camera)
	camera.make_current()
	var layer: CanvasLayer = CanvasLayer.new()  # hall.gd's title label, so the shots match its pixel for pixel
	var label: Label = Label.new()
	label.position = Vector2(20, 12)
	label.add_theme_font_size_override("font_size", 40)
	label.add_theme_color_override("font_color", Color(1, 1, 1))
	label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	label.add_theme_constant_override("outline_size", 8)
	layer.add_child(label)
	root.add_child(layer)
	var vp: RID = root.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	var shots: Dictionary = {}
	for i: int in 60:   # the probes' one capture and the sky's radiance settle first (hall.gd shoots 20 views before)
		await process_frame
	for v: Array in _req["views"]:
		camera.fov = float(v[4])
		camera.look_at_from_position(_v(v[2]), _v(v[3]), Vector3.UP)
		label.text = str(v[1])
		var gpu: Array = []
		for i: int in 30:
			await process_frame
			if i >= 14:
				gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(vp))
		await RenderingServer.frame_post_draw
		var image: Image = root.get_texture().get_image()
		image.convert(Image.FORMAT_RGB8)
		image.save_png(_out.path_join("%s.png" % v[0]))
		gpu.sort()
		var info: Dictionary = {"draw_calls": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
			"primitives": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
			"gpu_ms": snappedf(float(gpu[gpu.size() / 2]), 0.01), "size": [image.get_width(), image.get_height()]}
		var ref: Image = Image.load_from_file(str(_req["refs"]).path_join("%s.png" % v[0]))
		if ref != null:
			ref.convert(Image.FORMAT_RGB8)
			info.merge(_diff(ref, image))
		shots[v[0]] = info
	_write("shots.json", {"shots": shots})
	print("LOBBY export shots saved %s" % _out)
	quit(0)


## The mean absolute difference over every channel (0..255) and the share of pixels with a channel off by more than
## DIFF_PX; a size mismatch is reported as such.
func _diff(a: Image, b: Image) -> Dictionary:
	if a.get_size() != b.get_size():
		return {"ref_size": [a.get_width(), a.get_height()], "mean_abs": -1.0, "off_share": 1.0}
	var da: PackedByteArray = a.get_data()
	var db: PackedByteArray = b.get_data()
	var total: int = 0
	var off: int = 0
	for i: int in range(0, da.size(), 3):
		var m: int = 0
		for k: int in 3:
			var d: int = absi(da[i + k] - db[i + k])
			total += d
			m = maxi(m, d)
		if m > DIFF_PX:
			off += 1
	var px: int = da.size() / 3
	return {"mean_abs": snappedf(float(total) / da.size(), 0.001), "off_share": snappedf(float(off) / px, 0.0001)}


func _v(a: Variant) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))


func _write(name: String, data: Dictionary) -> void:
	var f: FileAccess = FileAccess.open(_out.path_join(name), FileAccess.WRITE)
	f.store_string(JSON.stringify(data, " "))
	f.close()


func _fail(why: String) -> void:
	printerr("LOBBY export error %s" % why)
	quit(1)
