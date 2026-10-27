extends SceneTree
## The ship package's check (`ship --export DIR`, art #335, docs/ship.md "The export"): runs in the export folder
## opened as its own Godot project (the runner copies this file to DIR/_check/), against the package alone.
##   check (headless): godot --headless --path DIR -s res://_check/export_check.gd -- check <request.json> <out dir>
##     loads res://levels/ship/ship.tscn, measures each piece GLB at the origin (its meshes' bounds, its colliders, as
##     ship.gd's check), walks the 1.36 m capsule from the scene's Spawn marker through the layout's walk points on the
##     exported scene; <out>/load.json.
##   shoot (an off-screen window, through the runner's _godot.window(), never by hand): -- shoot <request.json> <out>
##     the scene's views as ship.gd shoots them (30 frames each, the title label), each beside the reference shot of
##     `ship --shoot` of the same view: the mean absolute difference (0..255) and the share of pixels off by more
##     than 16; per view the draw calls and the GPU ms (mean of 20 frames); <out>/shots.json.
## request.json: {"scene", "pieces": {id: res}, "walk": {"r", "h", "points"}, "views": [[name, title, eye, look, fov]],
##   "refs": dir of the reference PNGs}.

const Offscreen = preload("res://lib/offscreen.gd")
const SPEED: float = 3.0
const DIFF_PX: int = 16

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
	var result: Dictionary = {"bounds": {}, "colliders": {}, "scripts": [], "loaded": false}
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
	result["loaded"] = true
	result["root"] = String(level.name)
	result["size_m"] = level.get_meta("size_m", null) != null
	var all: Array = level.find_children("*", "", true, false)
	result["scripts"] = all.filter(func(n: Node) -> bool: return n.get_script() != null).map(func(n: Node) -> String: return str(level.get_path_to(n)))
	result["pieces"] = level.get_node("Pieces").get_child_count()
	result["bodies"] = all.filter(func(n: Node) -> bool: return n is StaticBody3D and (n as StaticBody3D).collision_layer & 1).size()
	result["lights"] = all.filter(func(n: Node) -> bool: return n is Light3D).size()
	result["stations"] = {}
	for m: Node in level.get_node("Stations").get_children():
		var mk: Marker3D = m
		result["stations"][String(mk.name)] = {"spot": mk.get_meta("spot", ""), "package": mk.get_meta("package", ""),
			"at": [mk.position.x, mk.position.y, mk.position.z], "yaw": mk.rotation_degrees.y}
	var spawn: Marker3D = level.get_node("Markers/Spawn")
	result["spawn"] = [spawn.position.x, spawn.position.y, spawn.position.z]
	for i: int in 3:
		await physics_frame
	var w: Dictionary = _req["walk"]
	var points: Array = [spawn.position]
	for p: Array in (w["points"] as Array).slice(1):
		points.append(Vector3(float(p[0]), float(p[1]), float(p[2])))
	result["walk"] = await _walk(float(w["r"]), float(w["h"]), points)
	_write("load.json", result)
	print("SHIP export check saved %s" % _out)
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
	if _scene() == null:
		_fail("cannot load %s" % _req["scene"])
		return
	var camera: Camera3D = Camera3D.new()
	camera.near = 0.05
	camera.far = 500.0
	root.add_child(camera)
	camera.make_current()
	var layer: CanvasLayer = CanvasLayer.new()  # ship.gd's title label, so the shots match its pixel for pixel
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
	for v: Array in _req["views"]:
		camera.fov = float(v[4])
		camera.look_at_from_position(_v(v[2]), _v(v[3]), Vector3.UP)
		label.text = str(v[1])
		var gpu: float = 0.0
		for i: int in 30:
			await process_frame
			if i >= 10:
				gpu += RenderingServer.viewport_get_measured_render_time_gpu(vp)
		await RenderingServer.frame_post_draw
		var image: Image = root.get_texture().get_image()
		image.convert(Image.FORMAT_RGB8)
		image.save_png(_out.path_join("%s.png" % v[0]))
		var info: Dictionary = {"draw_calls": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
			"primitives": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
			"gpu_ms": snappedf(gpu / 20.0, 0.01), "size": [image.get_width(), image.get_height()]}
		var ref: Image = Image.load_from_file(str(_req["refs"]).path_join("%s.png" % v[0]))
		if ref != null:
			ref.convert(Image.FORMAT_RGB8)
			info.merge(_diff(ref, image))
		shots[v[0]] = info
	_write("shots.json", {"shots": shots})
	print("SHIP export shots saved %s" % _out)
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
	printerr("SHIP export error %s" % why)
	quit(1)
