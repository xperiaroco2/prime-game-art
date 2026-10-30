extends SceneTree
## The lobby hall in Godot for `tools/run.py lobby` (art #356, docs/lobby.md): places the hall's pieces and art #263's
## ship pieces by the request's placements (pieces imported with `-col` meshes carry their trimesh colliders), then
## checks it headless or shoots it under a neutral review light in an off-screen window.
##   godot --headless --path godot -s res://lobby/hall.gd -- <request.json> <out>          (mode "check")
##   shoot, grid: started by the runner through `_godot.window()` (CLAUDE.md, #214), never by hand (modes "shoot", "grid")
## request.json (tools/runner/commands/lobby.py): {"mode", "pieces": {id: res}, "place": [[id, [x, y, z], yaw]],
##   "walk": {"r", "h", "points": [[x, y, z]]}, "blocks": [[name, from, to]], "views": [[name, title, eye, look, fov]],
##   "top": {"name", "title", "size_m", "centre": [x, z], "hide": [id]}, "compare": [[shot, image]], "background",
##   "look": {"id", "title", "mats": {material: {"rgb", "metallic", "roughness", "emit"}}},
##   grid: "variants": [look] (the schemes). The look replaces the hall's materials (by their glTF name).
## grid: <out>/grid.png, one row per scheme (its views side by side, labelled), and <out>/<scheme>_<view>.png.
## check: <out>/check.json {"bounds": {id: {min, max}} (each piece at its origin), "colliders": {id: n}, "walk",
##   "blocks": {name: walk}}. shoot: <out>/<view>.png, compare_<view>.png (the concept left, the shot right),
##   sheet.png (1280 px wide, two per row) and shots.json.

const Offscreen = preload("res://lib/offscreen.gd")
const WATCHDOG_S: float = 240.0
const SPEED: float = 3.0
const SHEET_W: int = 1280
const GAP: int = 4

var _req: Dictionary
var _out: String
var _camera: Camera3D
var _label: Label
var _scenes: Dictionary = {}
var _placed: Dictionary = {}   # piece id -> its placed nodes


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 2:
		_fail("usage: -- <request.json> <out dir>")
		return
	var request: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if typeof(request) != TYPE_DICTIONARY:
		_fail("cannot read %s" % args[0])
		return
	_req = request
	_out = args[1]
	DirAccess.make_dir_recursive_absolute(_out)
	if _req["mode"] != "check":
		if DisplayServer.get_name() == "headless":
			_fail("shoot needs a window (off-screen), not --headless")
			return
		var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
		if placed != "":
			_fail(placed)
			return
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	if _req["mode"] == "check":
		_check()
	elif _req["mode"] == "grid":
		_grid()
	else:
		_shoot()


## The hall's materials in a look (a colour scheme, the grid only): each surface whose glTF material is in the
## scheme's "mats" gets a copy of its imported material with the scheme's colour, metallic, roughness and emission; the
## copy keeps the GLB's own metal maps (step 2c: the normal and roughness maps live in the GLBs, so the shots show the
## game's look without this step). The ship's pieces keep their own.
func _apply_look(look: Dictionary) -> void:
	var mats: Dictionary = look["mats"]
	var made: Dictionary = {}
	for pid: String in _placed:
		if pid.begins_with("ship_"):
			continue
		for top: Node in _placed[pid]:
			var stack: Array = [top]
			while not stack.is_empty():
				var n: Node = stack.pop_back()
				stack.append_array(n.get_children())
				if not n is MeshInstance3D or (n as MeshInstance3D).mesh == null:
					continue
				var mi: MeshInstance3D = n
				for i: int in mi.mesh.get_surface_count():
					var m: Material = mi.mesh.surface_get_material(i)
					if m == null or not mats.has(m.resource_name) or not m is BaseMaterial3D:
						continue
					var mname: String = m.resource_name
					if not made.has(mname):
						made[mname] = _look_material(m as BaseMaterial3D, mats[mname])
					mi.set_surface_override_material(i, made[mname])


func _look_material(orig: BaseMaterial3D, spec: Dictionary) -> BaseMaterial3D:
	var mat: BaseMaterial3D = orig.duplicate()
	var c: Color = Color(float(spec["rgb"][0]), float(spec["rgb"][1]), float(spec["rgb"][2]))
	mat.albedo_color = c
	mat.metallic = float(spec["metallic"])
	mat.roughness = float(spec["roughness"])
	if float(spec["emit"]) > 0.0:
		mat.emission_enabled = true
		mat.emission = c
		mat.emission_energy_multiplier = float(spec["emit"])
	return mat


func _setup_scene() -> void:
	_environment()
	_build()
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.far = 400.0
	root.add_child(_camera)
	_camera.make_current()
	var layer: CanvasLayer = CanvasLayer.new()
	_label = Label.new()
	_label.position = Vector2(20, 12)
	_label.add_theme_font_size_override("font_size", 40)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 8)
	layer.add_child(_label)
	root.add_child(layer)


## The taste grid: the grid's views once per scheme, a row each.
func _grid() -> void:
	_setup_scene()
	var shots: Dictionary = {}
	var rows: Array = []
	for look: Dictionary in _req["variants"]:
		_apply_look(look)
		var row: Array = []
		for v: Array in _req["views"]:
			_camera.fov = float(v[4])
			_camera.look_at_from_position(_v(v[2]), _v(v[3]), Vector3.UP)
			row.append(await _shot("%s_%s" % [look["id"], v[0]], "%s %s: %s" % [look["id"], look["title"], v[0]], shots))
		rows.append(row)
	_save(_sheet(rows), _out.path_join("grid.png"))
	_write("shots.json", {"shots": shots})
	print("LOBBY grid saved %s" % _out)
	quit(0)


func _scene(pid: String) -> PackedScene:
	if not _scenes.has(pid):
		_scenes[pid] = load(_req["pieces"][pid]) as PackedScene
		if _scenes[pid] == null:
			_fail("cannot load %s" % _req["pieces"][pid])
	return _scenes[pid]


func _build() -> void:
	var hall: Node3D = Node3D.new()
	hall.name = "Lobby"
	root.add_child(hall)
	for p: Array in _req["place"]:
		var node: Node3D = _scene(p[0]).instantiate() as Node3D
		node.name = "%s_%d" % [p[0], hall.get_child_count()]
		node.position = _v(p[1])
		node.rotation_degrees.y = float(p[2])
		hall.add_child(node)
		if not _placed.has(p[0]):
			_placed[p[0]] = []
		_placed[p[0]].append(node)


## A piece's bounds at its origin (its meshes' AABBs) and its colliders.
func _measure(pid: String) -> Array:
	var node: Node3D = _scene(pid).instantiate() as Node3D
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


func _check() -> void:
	var result: Dictionary = {"bounds": {}, "colliders": {}, "blocks": {}}
	for pid: String in _req["pieces"]:
		var m: Array = _measure(pid)
		var box: AABB = m[0]
		result["bounds"][pid] = {"min": [box.position.x, box.position.y, box.position.z],
			"max": [box.end.x, box.end.y, box.end.z]}
		result["colliders"][pid] = m[1]
	_build()
	for i: int in 3:
		await physics_frame
	var w: Dictionary = _req["walk"]
	result["walk"] = await _walk(float(w["r"]), float(w["h"]), w["points"].map(_v))
	for b: Array in _req.get("blocks", []):
		result["blocks"][b[0]] = await _walk(float(w["r"]), float(w["h"]), [_v(b[1]), _v(b[2])])
	_write("check.json", result)
	print("LOBBY check saved %s" % _out)
	quit(0)


## A capsule (radius r, height h) walks the waypoints at 3 m/s with gravity; it arrives when it reaches the last one
## within 0.3 m and its height within 0.15 m; it gives up after 2 s without moving.
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
	while steps < limit and reached < points.size() - 1:
		await physics_frame
		steps += 1
		var target: Vector3 = points[reached + 1]
		var flat: Vector3 = Vector3(target.x - body.global_position.x, 0, target.z - body.global_position.z)
		if flat.length() < 0.3:
			reached += 1
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
	await physics_frame
	return {"of": points.size(), "reached": reached + 1, "end": [end.x, end.y, end.z], "min_y": min_y,
		"seconds": steps * dt, "length_m": length, "arrived": arrived, "stuck": [last_pos.x, last_pos.y, last_pos.z]}


# --- pictures ------------------------------------------------------------------------------------------------------
## The neutral review light: a grey ambient, a grey sky for reflections only, a soft key from the north-west above without shadows, SSAO for the forms;
## the dark blue placeholder fills everything behind the window (no Earth yet).
func _environment() -> void:
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(_req["background"][0], _req["background"][1], _req["background"][2])
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.85, 0.86, 0.9)
	env.ambient_light_energy = 0.4
	# a neutral grey sky for the reflections only (the ship's metal reads black without one); never the background
	var sky_mat: ProceduralSkyMaterial = ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.55, 0.56, 0.6)
	sky_mat.sky_horizon_color = Color(0.5, 0.5, 0.52)
	sky_mat.ground_horizon_color = Color(0.35, 0.35, 0.36)
	sky_mat.ground_bottom_color = Color(0.25, 0.25, 0.26)
	var sky: Sky = Sky.new()
	sky.sky_material = sky_mat
	env.sky = sky
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssr_enabled = true   # the polished floor's reflections (step 2)
	env.ssr_max_steps = 96
	env.ssao_enabled = true
	env.ssao_radius = 1.5
	env.ssao_intensity = 1.6
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var key: DirectionalLight3D = DirectionalLight3D.new()
	key.light_energy = 0.8
	key.shadow_enabled = false
	key.rotation_degrees = Vector3(-55, -35, 0)
	root.add_child(key)
	var fill: DirectionalLight3D = DirectionalLight3D.new()
	fill.light_energy = 0.35
	fill.shadow_enabled = false
	fill.rotation_degrees = Vector3(-30, 150, 0)
	root.add_child(fill)


func _shoot() -> void:
	_setup_scene()   # the GLBs' own materials: the layout's scheme, built in (step 2c)
	var shots: Dictionary = {}
	var images: Dictionary = {}
	for v: Array in _req["views"]:
		_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
		_camera.fov = float(v[4])
		_camera.look_at_from_position(_v(v[2]), _v(v[3]), Vector3.UP)
		images[v[0]] = await _shot(v[0], v[1], shots)
	var top: Dictionary = _req["top"]
	for pid: String in top.get("hide", []):
		for n: Node3D in _placed.get(pid, []):
			n.visible = false
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_camera.size = float(top["size_m"])
	_camera.keep_aspect = Camera3D.KEEP_HEIGHT
	var c: Vector3 = Vector3(float(top["centre"][0]), 0, float(top["centre"][1]))
	_camera.look_at_from_position(c + Vector3(0, 80, 0), c, Vector3(0, 0, -1))  # north (-z) up the picture
	images[top["name"]] = await _shot(top["name"], top["title"], shots)
	for pid: String in top.get("hide", []):   # back for the close-ups
		for n: Node3D in _placed.get(pid, []):
			n.visible = true
	for cmp: Array in _req["compare"]:
		var ref: Image = Image.load_from_file(cmp[1])
		if ref == null:
			_fail("cannot load %s" % cmp[1])
			return
		ref.convert(Image.FORMAT_RGB8)
		_save(_sheet([[ref, images[cmp[0]]]]), _out.path_join("compare_%s.png" % cmp[0]))
	var names: Array = images.keys()
	var rows: Array = []
	for i: int in range(0, names.size(), 2):
		rows.append(names.slice(i, i + 2).map(func(n: String) -> Image: return images[n]))
	_save(_sheet(rows), _out.path_join("sheet.png"))
	var close: Array = []   # step 2c: the close-ups of each fix, two a row, in their own sheet
	for v: Array in _req.get("closeups", []):
		_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
		_camera.fov = float(v[4])
		_camera.look_at_from_position(_v(v[2]), _v(v[3]), Vector3.UP)
		close.append(await _shot(v[0], v[1], shots))
	if not close.is_empty():
		var crow: Array = []
		for i: int in range(0, close.size(), 2):
			crow.append(close.slice(i, i + 2))
		_save(_sheet(crow), _out.path_join("closeups.png"))
	_write("shots.json", {"shots": shots})
	print("LOBBY saved %s" % _out)
	quit(0)


func _shot(name: String, title: String, shots: Dictionary) -> Image:
	_label.text = title
	for i: int in 30:
		await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	_save(image, _out.path_join("%s.png" % name))
	shots[name] = {"draw_calls": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		"primitives": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)}
	return image


func _sheet(rows: Array) -> Image:
	var scaled: Array = []
	var height: int = 0
	for row: Array in rows:
		var h0: float = float((row[0] as Image).get_height())
		var widths: Array = row.map(func(img: Image) -> float: return img.get_width() * h0 / img.get_height())
		var total: float = 0.0
		for w: float in widths:
			total += w
		var k: float = (SHEET_W - (row.size() - 1) * GAP) / total
		var tiles: Array = []
		for i: int in row.size():
			var img: Image = (row[i] as Image).duplicate() as Image
			img.resize(maxi(1, int(widths[i] * k)), maxi(1, int(h0 * k)), Image.INTERPOLATE_LANCZOS)
			tiles.append(img)
		scaled.append(tiles)
		height += int(h0 * k) + GAP
	var sheet: Image = Image.create_empty(SHEET_W, maxi(1, height - GAP), false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.97, 0.97, 0.97))
	var y: int = 0
	for tiles: Array in scaled:
		var x: int = 0
		for img: Image in tiles:
			sheet.blit_rect(img, Rect2i(Vector2i.ZERO, img.get_size()), Vector2i(x, y))
			x += img.get_width() + GAP
		y += (tiles[0] as Image).get_height() + GAP
	return sheet


func _v(a: Variant) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))


func _save(image: Image, path: String) -> void:
	var error: Error = image.save_png(path)
	if error != OK:
		_fail("cannot save %s: %s" % [path, error_string(error)])


func _write(name: String, data: Dictionary) -> void:
	var f: FileAccess = FileAccess.open(_out.path_join(name), FileAccess.WRITE)
	f.store_string(JSON.stringify(data, " "))
	f.close()


func _fail(why: String) -> void:
	printerr("LOBBY error %s" % why)
	quit(1)
