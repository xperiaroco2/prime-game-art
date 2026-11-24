extends SceneTree
## The M8 clearing's ground looks (prime-game#1704) and the package's proof: the game's clearing rebuilt from
## its scenes' numbers (prime-game levels/clearing/: the 200 x 1 x 200 m ground box at the ship, the Sky's fog, the
## round markers; levels/estate/rooms/ship.tscn: the art ship package with its Environment, both directional lights
## and its Clearing freed), then each look's ground, shot from the same cameras in an off-screen window.
## Run by tools/review/clearing_ground_looks.py:  -- <request.json> <out dir>
## The request: {"ship": res path, "at": [x,y,z], "fov": deg, "size": [w,h], "looks": [{"name", "ground": "box"|
## "pad"|"soil"|"material"|"none", "material": res path (ground "material": the package's .tres on ground.tscn's box),
## "free": [node paths]}], "views": [{"name", "eye": [..], "target": [..]} or {"name", "marker": "Transform3D(...)",
## "eye_h": m}], "sheets": dir, "compare": [[look, look], ...] (optional: per view the two looks' pixel difference)}

const Offscreen = preload("res://lib/offscreen.gd")
const SHADER = preload("res://clearing/ground.gdshader")
const WATCHDOG_S := 600.0

var _req: Dictionary
var _out: String


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
	if DisplayServer.get_name() == "headless":
		_fail("the shots need a window (off-screen), not --headless")
		return
	var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
	if placed != "":
		_fail(placed)
		return
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	_run.call_deferred()


func _run() -> void:
	RenderingServer.viewport_set_measure_render_time(root.get_viewport_rid(), true)
	var result: Dictionary = {}
	var kept: Dictionary = {}   # look -> view -> Image, only the looks a comparison needs
	var compared: Array = _req.get("compare", [])
	for look: Dictionary in _req["looks"]:
		var world := Node3D.new()
		world.name = "Clearing_" + String(look["name"])
		_environment(world)
		if not _ground(world, look):
			return
		var ship: Node3D = _ship(look)
		if ship == null:
			return
		world.add_child(ship)
		var cam := Camera3D.new()
		cam.fov = float(_req["fov"])
		cam.far = 500.0
		world.add_child(cam)
		root.add_child(world)
		cam.current = true
		var dir: String = _out.path_join(String(look["name"]))
		DirAccess.make_dir_recursive_absolute(dir)
		var shots: Dictionary = {}
		var images: Array[Image] = []
		for view: Dictionary in _req["views"]:
			_aim(cam, view)
			var image: Image = await _shot(dir.path_join("%s.png" % view["name"]), shots, String(view["name"]))
			images.append(image)
			for pair: Array in compared:
				if pair.has(look["name"]):
					if not kept.has(look["name"]):
						kept[look["name"]] = {}
					kept[look["name"]][view["name"]] = image
		result[look["name"]] = shots
		_save(_sheet(images), String(_req["sheets"]).path_join("sheet_%s.png" % look["name"]))
		root.remove_child(world)
		world.free()
		await process_frame
	if not compared.is_empty():
		result["compare"] = _compare(kept, compared)
	var f := FileAccess.open(_out.path_join("shots.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(result, " "))
	f.close()
	print("CLEARING saved %s" % _out)
	quit(0)


## prime-game levels/clearing/rooms/sky.tscn exactly (background colour, fog on, density 0.035, everything else at
## Godot's defaults: no tonemap, glow or SSAO; the round adds no light or environment of its own).
func _environment(world: Node3D) -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.42, 0.45, 0.5, 1)
	env.fog_enabled = true
	env.fog_light_color = Color(0.42, 0.45, 0.5, 1)
	env.fog_density = 0.035
	var we := WorldEnvironment.new()
	we.name = "Sky"
	we.environment = env
	world.add_child(we)


func _ground(world: Node3D, look: Dictionary) -> bool:
	var kind: String = String(look["ground"])
	var at: Vector3 = _v(_req["at"])
	var mi := MeshInstance3D.new()
	mi.name = "Ground"
	if kind == "box" or kind == "material":   # levels/clearing/rooms/ground.tscn: the box, its top at y 0
		var box := BoxMesh.new()
		box.size = Vector3(200, 1, 200)
		if kind == "box":   # with levels/kit/greybox_floor_garden.tres
			var mat := StandardMaterial3D.new()
			mat.albedo_color = Color(0.33, 0.52, 0.28, 1)
			box.material = mat
		else:   # with the package's material in its place
			var pkg: Material = load(String(look["material"])) as Material
			if pkg == null:
				_fail("cannot load %s" % look["material"])
				return false
			box.material = pkg
		mi.mesh = box
		mi.position = at + Vector3(0, -0.5, 0)
	elif kind == "pad" or kind == "soil":
		var plane := PlaneMesh.new()
		plane.size = Vector2(200, 200)
		var mat := ShaderMaterial.new()
		mat.shader = SHADER
		mat.set_shader_parameter("pad", kind == "pad")
		mat.set_shader_parameter("centre", Vector2(at.x, at.z))
		plane.material = mat
		mi.mesh = plane
		mi.position = at
	else:
		return true
	world.add_child(mi)
	return true


## The ship package as the game's estate ship piece has it: the listed nodes freed before it enters the tree, so
## its reflection probes capture without them (the game recaptures them a frame after freeing).
func _ship(look: Dictionary) -> Node3D:
	var scn: PackedScene = load(String(_req["ship"])) as PackedScene
	if scn == null:
		_fail("cannot load %s" % _req["ship"])
		return null
	var ship: Node3D = scn.instantiate() as Node3D
	ship.position = _v(_req["at"])
	for p: String in look["free"]:
		var n: Node = ship.get_node_or_null(NodePath(p))
		if n == null:
			_fail("ship package: no node %s" % p)
			return null
		n.get_parent().remove_child(n)
		n.free()
	return ship


func _aim(cam: Camera3D, view: Dictionary) -> void:
	if view.has("marker"):   # the round marker's own transform: the eye eye_h over it, looking along -z (the game's)
		var t: Transform3D = str_to_var(String(view["marker"]))
		var facing: Vector3 = -t.basis.z
		facing.y = 0.0
		var eye: Vector3 = t.origin + Vector3.UP * float(view["eye_h"])
		cam.look_at_from_position(eye, eye + facing.normalized())
	else:
		cam.look_at_from_position(_v(view["eye"]), _v(view["target"]))


func _shot(path: String, shots: Dictionary, name: String) -> Image:
	var gpu: Array = []
	for i: int in 40:
		await process_frame
		if i >= 20:
			gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(root.get_viewport_rid()))
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	_save(image, path)
	gpu.sort()
	shots[name] = {"gpu_ms": gpu[gpu.size() / 2], "size": [image.get_width(), image.get_height()],
		"draw_calls": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		"primitives": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)}
	return image


## Per compared pair and view: the mean absolute difference of the RGB channels (0-255) and the share of pixels whose
## largest channel difference is over 8.
func _compare(kept: Dictionary, pairs: Array) -> Dictionary:
	var out: Dictionary = {}
	for pair: Array in pairs:
		var a: Dictionary = kept.get(pair[0], {})
		var b: Dictionary = kept.get(pair[1], {})
		var per: Dictionary = {}
		for view: String in a:
			if not b.has(view):
				continue
			var da: PackedByteArray = (a[view] as Image).get_data()
			var db: PackedByteArray = (b[view] as Image).get_data()
			var total := 0
			var over := 0
			for i: int in range(0, da.size(), 3):
				var m := 0
				for c: int in 3:
					var d: int = absi(da[i + c] - db[i + c])
					total += d
					m = maxi(m, d)
				if m > 8:
					over += 1
			per[view] = {"mean_abs": float(total) / da.size(), "share_over_8": float(over) / (da.size() / 3)}
		out["%s_vs_%s" % [pair[0], pair[1]]] = per
	return out


## A 2 x 2 sheet of the views at half size (1280 px wide for a 1280 x 720 window).
func _sheet(images: Array[Image]) -> Image:
	var w: int = images[0].get_width() / 2
	var h: int = images[0].get_height() / 2
	var sheet := Image.create(w * 2, h * ceili(images.size() / 2.0), false, Image.FORMAT_RGB8)
	for i: int in images.size():
		var im: Image = images[i].duplicate() as Image
		im.resize(w, h, Image.INTERPOLATE_LANCZOS)
		sheet.blit_rect(im, Rect2i(0, 0, w, h), Vector2i((i % 2) * w, (i / 2) * h))
	return sheet


func _v(a: Variant) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))


func _save(image: Image, path: String) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var error: Error = image.save_png(path)
	if error != OK:
		_fail("cannot save %s: %s" % [path, error_string(error)])


func _fail(why: String) -> void:
	push_error("ground_looks.gd: " + why)
	printerr("CLEARING FAILED: " + why)
	quit(1)
