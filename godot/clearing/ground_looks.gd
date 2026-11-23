extends SceneTree
## The M8 clearing's ground looks (prime-game#1704; review shots only, no package): the game's clearing rebuilt from
## its scenes' numbers (prime-game levels/clearing/: the 200 x 1 x 200 m ground box at the ship, the Sky's fog, the
## round markers; levels/estate/rooms/ship.tscn: the art ship package with its Environment, both directional lights
## and its Clearing freed), then each look's ground, shot from the same cameras in an off-screen window.
## Run by tools/review/clearing_ground_looks.py:  -- <request.json> <out dir>
## The request: {"ship": res path, "at": [x,y,z], "fov": deg, "size": [w,h], "looks": [{"name", "ground": "box"|
## "pad"|"soil"|"none", "free": [node paths]}], "views": [{"name", "eye": [..], "target": [..]} or {"name",
## "marker": "Transform3D(...)", "eye_h": m}], "sheets": dir}

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
	for look: Dictionary in _req["looks"]:
		var world := Node3D.new()
		world.name = "Clearing_" + String(look["name"])
		_environment(world)
		_ground(world, String(look["ground"]))
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
		result[look["name"]] = shots
		_save(_sheet(images), String(_req["sheets"]).path_join("sheet_%s.png" % look["name"]))
		root.remove_child(world)
		world.free()
		await process_frame
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


func _ground(world: Node3D, kind: String) -> void:
	var at: Vector3 = _v(_req["at"])
	var mi := MeshInstance3D.new()
	mi.name = "Ground"
	if kind == "box":   # levels/clearing/rooms/ground.tscn with levels/kit/greybox_floor_garden.tres
		var box := BoxMesh.new()
		box.size = Vector3(200, 1, 200)
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(0.33, 0.52, 0.28, 1)
		box.material = mat
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
		return
	world.add_child(mi)


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
