extends SceneTree
## The basement's review pictures for `tools/run.py house --basement DIR` (art #78, docs/house.md "The basement"):
## loads the generated house.tscn (res://import/house), lights the basement with real-time lamp stand-ins at its light
## fixtures (a review aid: not the light pass, nothing baked), one fixed exposure, then shoots each room from its door at
## 1.6 m, the top-down plan of the basement alone with room labels and the route times, and measures the generator
## hall's far wall from the passage (median L*). Pictures need a real window placed off-screen, never headless:
##   godot --path godot --position -30000,-30000 --resolution 1600x900 -s res://house/basement.gd -- <request.json> <out>
## request.json: house_basement.review_request(). Writes <out>/<shot>.png, <out>/plan_basement.png, <out>/sheet.png
## (1280 px wide) and <out>/basement.json; prints BASEMENT saved <dir>.

const WATCHDOG_S: float = 170.0
const SHEET_W: int = 1280
const GAP: int = 4
const PLAN_H: int = 600  # the sheet's plan row; the shots below in rows of three

var _req: Dictionary
var _out: String
var _house: Node3D
var _camera: Camera3D
var _label: Label
var _notes: Label


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 2:
		_fail("usage: -- <request.json> <out dir>")
		return
	if DisplayServer.get_name() == "headless":
		_fail("needs a window (off-screen), not --headless")
		return
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	_run(args)


func _run(args: PackedStringArray) -> void:
	var request: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if typeof(request) != TYPE_DICTIONARY:
		_fail("cannot read %s" % args[0])
		return
	_req = request
	_out = args[1]
	DirAccess.make_dir_recursive_absolute(_out)
	_environment()
	var scene: PackedScene = load("res://import/house/house.tscn") as PackedScene
	if scene == null:
		_fail("cannot load res://import/house/house.tscn")
		return
	_house = scene.instantiate() as Node3D
	root.add_child(_house)
	for l: Dictionary in _req["lamps"]:
		var lamp: OmniLight3D = OmniLight3D.new()
		var c: Array = l["color"]
		lamp.light_color = Color(c[0], c[1], c[2])
		lamp.light_energy = float(l["energy"])
		lamp.omni_range = float(l["range"])
		lamp.shadow_enabled = bool(l["shadow"])
		lamp.position = _v(l["pos"])
		root.add_child(lamp)
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.fov = float(_req["fov"])
	root.add_child(_camera)
	_camera.make_current()
	var layer: CanvasLayer = CanvasLayer.new()
	_label = _text(40, Vector2(16, 10))
	_notes = _text(30, Vector2(16, 760))
	layer.add_child(_label)
	layer.add_child(_notes)
	root.add_child(layer)
	for i: int in 3:
		await physics_frame
	var result: Dictionary = {"shots": {}, "lamps": _req["lamps"].size()}
	var images: Array[Image] = []
	var far: Dictionary = _req["far_edge"]
	for s: Dictionary in _req["shots"]:
		_camera.look_at_from_position(_v(s["from"]), _v(s["to"]), Vector3.UP)
		_label.text = s["title"]
		var image: Image = await _grab()
		var info: Dictionary = {"title": s["title"], "lstar_median": _lstar(image, Rect2i(Vector2i.ZERO, image.get_size()))}
		if s["name"] == far["shot"]:
			var box: Rect2i = _project_box(_v(far["a"]), _v(far["b"]), image.get_size())
			var l: float = _lstar(image, box)
			result["far_edge"] = {"shot": s["name"], "box": [box.position.x, box.position.y, box.size.x, box.size.y],
				"lstar_median": l, "min_lstar": far["min_lstar"], "pass": l > float(far["min_lstar"])}
		result["shots"][s["name"]] = info
		_save(image, _out.path_join("%s.png" % s["name"]))
		images.append(image)
	var plan: Image = await _plan()
	_save(plan, _out.path_join("plan_basement.png"))
	_save(_sheet(plan, images), _out.path_join("sheet.png"))
	var f: FileAccess = FileAccess.open(_out.path_join("basement.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(result, " "))
	f.close()
	print("BASEMENT saved %s" % _out)
	quit(0)


## Night underground: no sky light, a faint cool ambient, one fixed exposure (Q24 A).
func _environment() -> void:
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.0, 0.0, 0.0)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	var a: Array = _req["ambient"]
	env.ambient_light_color = Color(a[0], a[1], a[2])
	env.ambient_light_energy = float(_req["ambient_energy"])
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = float(_req["exposure"])
	env.tonemap_white = 4.0
	env.ssao_enabled = true
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = env
	root.add_child(world)


func _text(size: int, at: Vector2) -> Label:
	var l: Label = Label.new()
	l.position = at
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", Color(1, 1, 1))
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	l.add_theme_constant_override("outline_size", 8)
	return l


## The basement alone from above (orthographic): the other levels hidden, a label per room, the route times below.
func _plan() -> Image:
	for n: String in _req["hide"]:
		var node: Node = _house.get_node_or_null(n)
		if node != null:
			(node as Node3D).visible = false
	for n: Node in _house.find_children("ceiling*", "Node3D", true, false):
		(n as Node3D).visible = false
	var fy: float = float(_req["plan"]["floor_y"])
	for r: Dictionary in _req["rooms"]:
		var rect: Array = r["rect"]
		var t: Label3D = Label3D.new()
		t.text = "%s\n%dx%d" % [r["title"], int(rect[2]), int(rect[3])]
		t.font_size = 36
		t.pixel_size = 0.03
		t.outline_size = 10
		t.outline_modulate = Color(0, 0, 0)
		t.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		t.no_depth_test = true
		t.position = Vector3(rect[0] + rect[2] * 0.5, fy + 4.0, rect[1] + rect[3] * 0.5)
		root.add_child(t)
	var pr: Array = _req["plan"]["rect"]
	var frame: Vector2 = root.get_visible_rect().size
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	var keep: float = minf(1.0, PLAN_H / float(SHEET_W) * frame.x / frame.y)  # the share of the height the sheet keeps
	_camera.size = maxf(float(pr[3]) / keep, float(pr[2]) * frame.y / frame.x)
	var c: Vector2 = Vector2(pr[0] + pr[2] * 0.5, pr[1] + pr[3] * 0.5)
	_camera.look_at_from_position(Vector3(c.x, fy + 30.0, c.y + 0.001), Vector3(c.x, fy, c.y), Vector3(0, 0, -1))
	_label.text = "basement from above (lamp stand-ins, not the light pass)"
	_notes.text = "\n".join(PackedStringArray(_req["lines"]))
	_label.position.y = frame.y * (1.0 - keep) * 0.5 + 10.0
	_notes.position.y = frame.y * (1.0 + keep) * 0.5 - 40.0 * _req["lines"].size() - 10.0
	var image: Image = await _grab()
	_notes.text = ""
	_label.position.y = 10.0
	return image


## The screen box of the wall band between two corners a (low) and b (high), clipped to the frame.
func _project_box(a: Vector3, b: Vector3, size: Vector2i) -> Rect2i:
	var pts: Array[Vector2] = []
	for p: Vector3 in [a, b, Vector3(a.x, b.y, a.z), Vector3(b.x, a.y, b.z)]:
		if not _camera.is_position_behind(p):
			pts.append(_camera.unproject_position(p))
	if pts.is_empty():
		return Rect2i()
	var box: Rect2 = Rect2(pts[0], Vector2.ZERO)
	for p: Vector2 in pts:
		box = box.expand(p)
	return Rect2i(box).intersection(Rect2i(Vector2i.ZERO, size))


## The median CIE L* (0..100) of the image's pixels in the box, every 4th pixel each way.
func _lstar(image: Image, box: Rect2i) -> float:
	var values: Array[float] = []
	for y: int in range(box.position.y, box.end.y, 4):
		for x: int in range(box.position.x, box.end.x, 4):
			var c: Color = image.get_pixel(x, y).srgb_to_linear()
			var lum: float = 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b
			var f: float = pow(lum, 1.0 / 3.0) if lum > 0.008856 else 7.787 * lum + 16.0 / 116.0
			values.append(116.0 * f - 16.0)
	if values.is_empty():
		return -1.0
	values.sort()
	return snappedf(values[values.size() / 2], 0.1)


func _grab() -> Image:
	for i: int in 20:
		await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	return image


## The plan across the top (PLAN_H high), the shots below in rows of three.
func _sheet(plan: Image, shots: Array[Image]) -> Image:
	var cw: int = (SHEET_W - 2 * GAP) / 3
	var ch: int = int(cw * shots[0].get_height() / float(shots[0].get_width()))
	var rows: int = (shots.size() + 2) / 3
	var sheet: Image = Image.create_empty(SHEET_W, PLAN_H + rows * (ch + GAP), false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.97, 0.97, 0.97))
	_paste(sheet, plan, Vector2i.ZERO, Vector2i(SHEET_W, PLAN_H))
	for i: int in shots.size():
		_paste(sheet, shots[i], Vector2i((i % 3) * (cw + GAP), PLAN_H + GAP + (i / 3) * (ch + GAP)), Vector2i(cw, ch))
	return sheet


## Scales src to cover size (cropping the overflow, centred) and pastes it at `at`.
func _paste(sheet: Image, src: Image, at: Vector2i, size: Vector2i) -> void:
	var img: Image = src.duplicate() as Image
	var k: float = maxf(size.x / float(img.get_width()), size.y / float(img.get_height()))
	img.resize(maxi(size.x, int(ceil(img.get_width() * k))), maxi(size.y, int(ceil(img.get_height() * k))),
		Image.INTERPOLATE_LANCZOS)
	var off: Vector2i = (img.get_size() - size) / 2
	sheet.blit_rect(img, Rect2i(off, size), at)


func _v(a: Array) -> Vector3:
	return Vector3(a[0], a[1], a[2])


func _save(image: Image, path: String) -> void:
	var error: Error = image.save_png(path)
	if error != OK:
		_fail("cannot save %s: %s" % [path, error_string(error)])


func _fail(why: String) -> void:
	printerr("BASEMENT error %s" % why)
	quit(1)
