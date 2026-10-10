extends SceneTree
## The House shell's walk for `tools/run.py house --walk DIR` (docs/house.md): loads the generated house.tscn
## (res://import/house), walks a 1.4 m capsule through every doorway of the ground and upper floors and up and down every
## flight, shoots eye-height stills (1.6 m), a top-down plan of the ground floor with room labels and an aerial view,
## and counts the shell's draw calls per view; then the exterior's four sides at dusk (exterior.png), the kit's own
## colours, with each `Placeholders` marker drawn as a see-through orange box (its `size` metadata, from the bottom up). Pictures need a real window placed off-screen, never headless:
##   godot --path godot --position -30000,-30000 --resolution 1600x900 -s res://house/walk.gd -- <request.json> <out dir>
## request.json: house_layout.walk_request(): {"walks": [{"name", "kind", "points": [[x, h, z], ...]}], "pads": [...],
## "rooms": [{"level", "id", "title", "rect", "kind", "floor_y"}], "levels": {"<level>": {"node", "floor_y"}}}.
## Writes <out>/<shot>.png, <out>/sheet.png, <out>/exterior.png, with upper rooms or a loop <out>/upper.png (all
## 1280 px wide), and <out>/walk.json; prints WALK saved <dir>.

const WATCHDOG_S: float = 170.0
const EYE: float = 1.6
const UP := Vector3.UP
const LAMP := Color(1.0, 0.85, 0.68)
const SHEET_W: int = 1280
const GAP: int = 4
## The doors' clear width is exactly 1.4 m (kits/house.json door_w_m): a 1.4 m capsule touches both jambs and jams on
## them, so the walk's capsule keeps 2 cm a side (1.36 m).
const RADIUS: float = 0.68
const CONTROL_RADIUS: float = 0.75  # 1.5 m: must stop at a 1.4 m door (the colliders are there)
const SPEED: float = 3.0
## The exterior's four sides at dusk from 1.7 m eye height outside the plot's middle, aimed at the house (x 17..43, z 16..45).
const EXTERIOR: Array = [
	["ext_south", "south: the front (path, front door, porch)", Vector3(30, 1.7, 76), Vector3(30, 4.0, 34)],
	["ext_east", "east: kitchen and garage side", Vector3(78, 1.7, 33), Vector3(30, 4.0, 31)],
	["ext_north", "north: terrace and balcony", Vector3(30, 1.7, -14), Vector3(30, 3.5, 28)],
	["ext_west", "west: living room and WC side", Vector3(-18, 1.7, 33), Vector3(30, 4.0, 31)],
]
const PLAN_RECT := Rect2(13.0, 13.0, 34.0, 34.0)  # the top-down's ground area (x, z): the house and the terrace

var _req: Dictionary
var _out: String
var _house: Node3D
var _camera: Camera3D
var _label: Label
var _env: Environment


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
	_lamps()
	_pads()
	_placeholders()
	_camera = Camera3D.new()
	_camera.near = 0.05
	root.add_child(_camera)
	_camera.make_current()
	var layer: CanvasLayer = CanvasLayer.new()
	_label = Label.new()
	_label.position = Vector2(16, 10)
	_label.add_theme_font_size_override("font_size", 40)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 8)
	layer.add_child(_label)
	root.add_child(layer)
	for i: int in 3:
		await physics_frame
	var result: Dictionary = {"walks": [], "radius_m": RADIUS, "shots": {}, "instances": _count_instances()}
	var loops: Array = []  # [request walk, its result]: drawn on the upper floor's top-down
	for w: Dictionary in _req["walks"]:
		var loop: bool = w["kind"] == "loop"  # a doc route (#76): the game's speed, timed against the doc
		var r: Dictionary = await _walk(RADIUS, w["points"], float(w.get("speed", SPEED)), 40.0 if loop else 8.0)
		r["name"] = w["name"]
		r["kind"] = w["kind"]
		if loop:
			r["doc_s"] = w["doc_s"]
			r["within_1s"] = r["arrived"] and absf(float(r["seconds"]) - float(w["doc_s"])) <= 1.0
		r["pass"] = r["arrived"]
		result["walks"].append(r)
		if loop:
			loops.append([w, r])
	var door: Dictionary = _req["walks"][0]
	var control: Dictionary = await _walk(CONTROL_RADIUS, door["points"])
	control["name"] = "control_1.5m:" + door["name"]
	control["pass"] = not control["arrived"]
	result["control"] = control
	# Pictures: the stills and the aerial with every level, then the ground floor alone for the plan.
	var shots: Array = [
		["front_door", "front door from the path", Vector3(30, EYE, 48.5), Vector3(30, 1.4, 38)],
		["dining_terrace", "dining room to the terrace door", Vector3(36, EYE, 28.6), Vector3(36, 1.2, 18)],
		["living_hallway", "living room to the hallway door", Vector3(21, EYE, 40), Vector3(31, 1.2, 40)],
		["main_stairs", "stairs room: the U-turn up (placeholder)", Vector3(33.4, EYE, 35.4), Vector3(27, 1.4, 33)],
		["pantry_stairs", "pantry: stairs down (placeholder)", Vector3(25.2, EYE, 24.8), Vector3(27, -2.6, 31)],
		["landing_balcony", "upper landing to the balcony door", Vector3(32, 3.2 + EYE, 29.5), Vector3(32, 3.2 + 1.2, 20)],
	]
	var images: Array[Image] = []
	for s: Array in shots:
		images.append(await _shot(s[0], s[1], s[2], s[3], result))
	var aerial: Image = await _shot("aerial", "the shell from the south-east (kit v1; orange: placeholders)",
		Vector3(62, 26, 70), Vector3(32, 2, 30), result, 50.0)
	var balcony: Image = await _shot("balcony_stairs", "terrace: balcony stairs (Q6 default)",
		Vector3(34, EYE, 11.5), Vector3(39, 2.4, 19), result)
	var sides: Array[Image] = []
	var fill: DirectionalLight3D = DirectionalLight3D.new()  # review only: the moon backlights the front
	fill.light_color = Color(0.6, 0.66, 0.9)
	fill.light_energy = 0.3
	fill.rotation_degrees = Vector3(-20.0, 20.0, 0.0)
	root.add_child(fill)
	for s: Array in EXTERIOR:
		sides.append(await _shot(s[0], s[1], s[2], s[3], result, 38.0))
	fill.queue_free()
	_save(_grid(sides), _out.path_join("exterior.png"))
	# The dressed rooms (house_dressing.review_request): one shot per room from its door, the feature shots.
	var room_images: Array[Image] = []
	var upper_images: Array[Image] = []  # the second floor's rooms (#76): upper.png
	var feature_images: Array[Image] = []
	result["rooms"] = {}
	for s: Dictionary in _req.get("room_shots", []):
		var img: Image = await _shot(s["name"], s["title"], _v(s["from"]), _v(s["to"]), result)
		if s.get("level", "ground") == "upper":
			upper_images.append(img)
		else:
			room_images.append(img)
		var info: Dictionary = result["shots"][s["name"]].duplicate()
		info.merge(_dressing_triangles(s["node"]))
		result["rooms"][s["room"]] = info
	for s: Dictionary in _req.get("features", []):
		feature_images.append(await _shot(s["name"], s["title"], _v(s["from"]), _v(s["to"]), result, 60.0))
	var sw: Dictionary = _req.get("swatches", {})
	if not sw.is_empty():
		feature_images.append(await _swatches(sw, result))
	var plan: Image = await _plan(result)
	_save(_sheet(plan, [aerial, balcony], images), _out.path_join("sheet.png"))
	if not room_images.is_empty():
		var right: Array = feature_images.duplicate()
		right.append(aerial)
		_save(_rooms_sheet(plan, right.slice(0, 2), room_images), _out.path_join("rooms.png"))
	if _req["levels"].has("upper") and (not upper_images.is_empty() or not loops.is_empty()):
		var upper_plan: Image = await _plan(result, "upper")
		var loop_image: Image = upper_plan
		for lr: Array in loops:
			loop_image = await _loop_plan(lr[0], lr[1], result)
		upper_images.append(balcony)
		_save(_upper_sheet(upper_plan, loop_image, upper_images), _out.path_join("upper.png"))
	var f: FileAccess = FileAccess.open(_out.path_join("walk.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(result, " "))
	f.close()
	print("WALK saved %s" % _out)
	quit(0)


# --- the scene -----------------------------------------------------------------------------------------------------
func _environment() -> void:
	var sky_mat: ProceduralSkyMaterial = ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.13, 0.14, 0.36)
	sky_mat.sky_horizon_color = Color(0.95, 0.52, 0.3)
	sky_mat.ground_horizon_color = Color(0.3, 0.2, 0.18)
	sky_mat.ground_bottom_color = Color(0.05, 0.05, 0.07)
	var sky: Sky = Sky.new()
	sky.sky_material = sky_mat
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 1.5
	env.tonemap_white = 4.0
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.35
	env.ssao_enabled = true
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_light_color = Color(0.3, 0.27, 0.4)
	env.fog_light_energy = 0.8
	env.fog_depth_begin = 60.0
	env.fog_depth_end = 200.0
	_env = env
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.light_color = Color(0.55, 0.65, 1.0)
	sun.light_energy = 0.45
	sun.rotation_degrees = Vector3(-24.0, 200.0, 0.0)
	sun.shadow_enabled = true
	root.add_child(sun)
	var ground: MeshInstance3D = MeshInstance3D.new()  # the yard to look at (no collider: the basement lies below)
	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(200, 200)
	ground.mesh = plane
	var earth: StandardMaterial3D = StandardMaterial3D.new()
	earth.albedo_color = Color(0.16, 0.13, 0.11)
	earth.roughness = 1.0
	ground.material_override = earth
	ground.position = Vector3(40, -0.02, 30)
	root.add_child(ground)


## A warm lamp without shadows at 2.7 m in every room (kind "room") of every level: light to see the shell by.
## With a dressing (`lamps`): a c2 stand-in at every light fixture instead, in the rooms of `lamp_rooms`.
func _lamps() -> void:
	var dressed: Array = _req.get("lamp_rooms", [])
	for l: Dictionary in _req.get("lamps", []):
		var lamp: OmniLight3D = OmniLight3D.new()
		lamp.light_color = LAMP
		lamp.light_energy = 1.3
		lamp.omni_range = 5.0
		lamp.position = _v(l["at"])
		_house.add_child(lamp)
	for r: Dictionary in _req["rooms"]:
		if r["kind"] != "room" or r["id"] in dressed:
			continue
		var rect: Array = r["rect"]
		var lamp: OmniLight3D = OmniLight3D.new()
		lamp.light_color = LAMP
		lamp.light_energy = 2.5
		lamp.omni_range = maxf(5.0, 0.75 * maxf(float(rect[2]), float(rect[3])))
		lamp.position = Vector3(rect[0] + rect[2] * 0.5, float(r["floor_y"]) + 2.7, rect[1] + rect[3] * 0.5)
		_house.add_child(lamp)


## Every marker under a `Placeholders` node (porch, chimneys, pitched roof: kit v2) as a see-through orange box with its
## name; no collider, so walks pass through.
func _placeholders() -> void:
	var paint: StandardMaterial3D = StandardMaterial3D.new()
	paint.albedo_color = Color(1.0, 0.45, 0.05, 0.45)
	paint.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	paint.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	for n: Node in _house.find_children("*", "Marker3D", true, false):
		if n.get_parent().name != "Placeholders":
			continue
		var m: Marker3D = n as Marker3D
		var size: Vector3 = Vector3(0.6, 0.6, 0.6)
		if m.has_meta("size"):
			size = _v(m.get_meta("size"))
		var box: MeshInstance3D = MeshInstance3D.new()
		var mesh: BoxMesh = BoxMesh.new()
		mesh.size = size
		box.mesh = mesh
		box.material_override = paint
		box.position = Vector3(0, size.y * 0.5, 0)
		m.add_child(box)
		var t: Label3D = Label3D.new()
		t.text = String(m.name)
		t.font_size = 28
		t.pixel_size = 0.02
		t.outline_size = 8
		t.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		t.position = Vector3(0, size.y + 0.4, 0)
		m.add_child(t)


## A 3 x 3 m slab (top at the end's height) under every walk end that has no floor: the yard (#81a builds it).
func _pads() -> void:
	for p: Array in _req["pads"]:
		var body: StaticBody3D = StaticBody3D.new()
		var shape: CollisionShape3D = CollisionShape3D.new()
		var box: BoxShape3D = BoxShape3D.new()
		box.size = Vector3(3, 0.2, 3)
		shape.shape = box
		body.add_child(shape)
		body.position = Vector3(p[0], float(p[1]) - 0.1, p[2])
		root.add_child(body)


func _count_instances() -> Dictionary:
	return {"mesh_instances": _house.find_children("*", "MeshInstance3D", true, false).size(),
		"static_bodies": _house.find_children("*", "StaticBody3D", true, false).size()}


# --- the walk check ------------------------------------------------------------------------------------------------
## A capsule (radius r, 1.8 m) walks the waypoints [x, h, z] at `speed` (3 m/s) over the plan for at most `max_s`
## seconds; it arrives when it reaches the last within 0.3 m and its height within 0.15 m. Stops early when it has not
## moved for 30 ticks.
func _walk(r: float, points: Array, speed: float = SPEED, max_s: float = 8.0) -> Dictionary:
	var body: CharacterBody3D = CharacterBody3D.new()
	var shape: CollisionShape3D = CollisionShape3D.new()
	var cap: CapsuleShape3D = CapsuleShape3D.new()
	cap.radius = r
	cap.height = 1.8
	shape.shape = cap
	shape.position.y = 0.9
	body.add_child(shape)
	body.floor_snap_length = 0.3
	root.add_child(body)
	body.global_position = _v(points[0]) + Vector3(0, 0.05, 0)
	await physics_frame
	var reached: int = 0
	var dt: float = 1.0 / Engine.physics_ticks_per_second
	var steps: int = 0
	var stuck: int = 0
	var last: Vector3 = body.global_position
	while steps < max_s * Engine.physics_ticks_per_second and reached < points.size() - 1 and stuck < 30:
		await physics_frame
		steps += 1
		var target: Vector3 = _v(points[reached + 1])
		var flat: Vector3 = Vector3(target.x - body.global_position.x, 0, target.z - body.global_position.z)
		while flat.length() < 0.3 and reached < points.size() - 2:  # next waypoint in the same tick: no idle ticks
			reached += 1
			target = _v(points[reached + 1])
			flat = Vector3(target.x - body.global_position.x, 0, target.z - body.global_position.z)
		if flat.length() < 0.3:
			reached += 1
			continue
		var v: Vector3 = flat.normalized() * speed
		v.y = 0.0 if body.is_on_floor() else body.velocity.y - 9.8 * dt
		body.velocity = v
		body.move_and_slide()
		stuck = stuck + 1 if body.global_position.distance_to(last) < 0.002 else 0
		last = body.global_position
	var end: Vector3 = body.global_position
	var arrived: bool = reached == points.size() - 1 and absf(end.y - float(points[-1][1])) < 0.15
	body.queue_free()
	await physics_frame
	return {"radius_m": r, "reached": reached + 1, "of": points.size(), "end": [snappedf(end.x, 0.01),
		snappedf(end.y, 0.01), snappedf(end.z, 0.01)], "seconds": snappedf(steps * dt, 0.01), "arrived": arrived}


# --- pictures ------------------------------------------------------------------------------------------------------
func _shot(name: String, title: String, from: Vector3, to: Vector3, result: Dictionary, fov: float = 70.0) -> Image:
	_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
	_camera.fov = fov
	_camera.look_at_from_position(from, to, UP)
	_label.text = title
	var image: Image = await _grab()
	result["shots"][name] = _frame_info()
	_save(image, _out.path_join("%s.png" % name))
	return image


## One floor from above (orthographic): the levels above it, the basement and every ceiling hidden, a label per room
## of the floor; saved as plan_<level>.png (a square crop). The labels are freed after the grab.
func _plan(result: Dictionary, level: String = "ground") -> Image:
	var top: float = float(_req["levels"][level]["floor_y"])
	for lv: String in _req["levels"]:
		var node: Node = _house.get_node_or_null(String(_req["levels"][lv]["node"]) if lv != "roof" else "RoofDeck")
		var fy: float = float(_req["levels"][lv]["floor_y"])
		if node != null:
			(node as Node3D).visible = lv == level or (lv != "roof" and fy >= 0.0 and fy < top)
	for n: Node in _house.find_children("ceiling*", "Node3D", true, false):
		(n as Node3D).visible = false
	var labels: Array[Label3D] = []
	for r: Dictionary in _req["rooms"]:
		if r["level"] != level or r["kind"] == "area":
			continue
		var rect: Array = r["rect"]
		var t: Label3D = Label3D.new()
		t.text = "%s\n%dx%d" % [r["title"], int(rect[2]), int(rect[3])]
		t.font_size = 36
		t.pixel_size = 0.022
		t.outline_size = 10
		t.outline_modulate = Color(0, 0, 0)
		t.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		t.no_depth_test = true
		t.position = Vector3(rect[0] + rect[2] * 0.5, top + 4.0, rect[1] + rect[3] * 0.5)
		root.add_child(t)
		labels.append(t)
	var square: Image = await _top_down("%s floor from above" % ("second" if level == "upper" else level))
	for t: Label3D in labels:
		t.queue_free()
	result["shots"]["plan_" + level] = _frame_info()
	_save(square, _out.path_join("plan_%s.png" % level))
	return square


## The current scene from above (orthographic, PLAN_RECT), cropped to a square, with a title.
func _top_down(title: String) -> Image:
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_camera.size = PLAN_RECT.size.y
	var c: Vector2 = PLAN_RECT.get_center()
	_camera.look_at_from_position(Vector3(c.x, 40, c.y + 0.001), Vector3(c.x, 0, c.y), Vector3(0, 0, -1))
	_label.text = title
	var frame: Vector2 = root.get_visible_rect().size
	_label.position.x = (frame.x - frame.y) * 0.5 + 16.0  # inside the square crop
	var image: Image = await _grab()
	_label.position.x = 16.0
	var side: int = image.get_height()
	return image.get_region(Rect2i((image.get_width() - side) / 2, 0, side, side))


## A walk of kind "loop" (#76) drawn over the upper floor's top-down: a 0.25 m ribbon through its waypoints, seen
## through the floors (orange on the ground, cyan upstairs), the walked time in the title; saved as <loop id>.png.
func _loop_plan(w: Dictionary, r: Dictionary, result: Dictionary) -> Image:
	var paint: Array[StandardMaterial3D] = []
	for col: Color in [Color(1.0, 0.5, 0.05), Color(0.1, 0.85, 1.0)]:
		var m: StandardMaterial3D = StandardMaterial3D.new()
		m.albedo_color = col
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.no_depth_test = true
		paint.append(m)
	var marks: Array[Node3D] = []
	var pts: Array = w["points"]
	for i: int in pts.size() - 1:
		var a: Vector3 = _v(pts[i])
		var b: Vector3 = _v(pts[i + 1])
		var seg: MeshInstance3D = MeshInstance3D.new()
		var box: BoxMesh = BoxMesh.new()
		box.size = Vector3(0.25, 0.05, Vector2(b.x - a.x, b.z - a.z).length() + 0.25)
		seg.mesh = box
		seg.material_override = paint[1 if maxf(a.y, b.y) > 1.6 else 0]
		root.add_child(seg)
		seg.position = Vector3((a.x + b.x) * 0.5, 8.0, (a.z + b.z) * 0.5)
		if Vector2(b.x - a.x, b.z - a.z).length() > 0.01:
			seg.look_at(Vector3(b.x, 8.0, b.z), UP)
		marks.append(seg)
	var title: String = "%s: %s s at %s m/s, doc %s s%s" % [String(w["name"]).get_slice(":", 1), r["seconds"],
		w.get("speed", SPEED), w["doc_s"], "" if r["arrived"] else ", STOPPED"]
	var image: Image = await _top_down(title)
	for m: Node3D in marks:
		m.queue_free()
	var file: String = String(w["name"]).get_slice(":", 1)  # "loop:<id>": no colon in a Windows file name
	result["shots"][file] = _frame_info()
	_save(image, _out.path_join("%s.png" % file))
	return image


func _frame_info() -> Dictionary:
	return {"draw_calls": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		"objects": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME),
		"primitives": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)}


func _grab() -> Image:
	for i: int in 20:
		await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	return image


## Four views in a 2 x 2 grid, 1280 px wide.
func _grid(views: Array[Image]) -> Image:
	var cw: int = (SHEET_W - GAP) / 2
	var ch: int = int(cw * views[0].get_height() / float(views[0].get_width()))
	var sheet: Image = Image.create_empty(SHEET_W, 2 * ch + GAP, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.97, 0.97, 0.97))
	for i: int in views.size():
		_paste(sheet, views[i], Vector2i((i % 2) * (cw + GAP), (i / 2) * (ch + GAP)), Vector2i(cw, ch))
	return sheet


## The plan (a square) on the left, the two side views stacked on its right, the six stills in two rows of three.
func _sheet(plan: Image, side: Array, shots: Array[Image]) -> Image:
	var s: int = 677
	var w: int = SHEET_W - s - GAP
	var h: int = (s - GAP) / 2
	var cw: int = (SHEET_W - 2 * GAP) / 3
	var ch: int = int(cw * shots[0].get_height() / float(shots[0].get_width()))
	var sheet: Image = Image.create_empty(SHEET_W, s + 2 * (ch + GAP), false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.97, 0.97, 0.97))
	_paste(sheet, plan, Vector2i.ZERO, Vector2i(s, s))
	for i: int in side.size():
		_paste(sheet, side[i], Vector2i(s + GAP, i * (h + GAP)), Vector2i(w, h))
	for i: int in shots.size():
		_paste(sheet, shots[i], Vector2i((i % 3) * (cw + GAP), s + GAP + (i / 3) * (ch + GAP)), Vector2i(cw, ch))
	return sheet


## The dressed rooms' sheet, 1280 px wide: the plan (a square) on the left, the feature shot and the aerial stacked on
## its right, the room shots in rows of four.
func _rooms_sheet(plan: Image, side: Array, rooms: Array[Image]) -> Image:
	var s: int = 632
	var w: int = SHEET_W - s - GAP
	var h: int = (s - GAP) / 2
	var cw: int = (SHEET_W - 3 * GAP) / 4
	var ch: int = int(cw * rooms[0].get_height() / float(rooms[0].get_width()))
	var rows: int = (rooms.size() + 3) / 4
	var sheet: Image = Image.create_empty(SHEET_W, s + rows * (ch + GAP), false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.97, 0.97, 0.97))
	_paste(sheet, plan, Vector2i.ZERO, Vector2i(s, s))
	for i: int in side.size():
		_paste(sheet, side[i], Vector2i(s + GAP, i * (h + GAP)), Vector2i(w, h))
	for i: int in rooms.size():
		_paste(sheet, rooms[i], Vector2i((i % 4) * (cw + GAP), s + GAP + (i / 4) * (ch + GAP)), Vector2i(cw, ch))
	return sheet


## The second floor's sheet (#76), 1280 px wide: its top-down with labels and the balcony loop's top-down side by side,
## then the tiles (the upper rooms from their doors, the balcony stairs) in rows of four.
func _upper_sheet(plan: Image, loop: Image, tiles: Array[Image]) -> Image:
	var s: int = (SHEET_W - GAP) / 2
	var cw: int = (SHEET_W - 3 * GAP) / 4
	var ch: int = int(cw * tiles[0].get_height() / float(tiles[0].get_width()))
	var rows: int = (tiles.size() + 3) / 4
	var sheet: Image = Image.create_empty(SHEET_W, s + rows * (ch + GAP), false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.97, 0.97, 0.97))
	_paste(sheet, plan, Vector2i.ZERO, Vector2i(s, s))
	_paste(sheet, loop, Vector2i(s + GAP, 0), Vector2i(s, s))
	for i: int in tiles.size():
		_paste(sheet, tiles[i], Vector2i((i % 4) * (cw + GAP), s + GAP + (i / 4) * (ch + GAP)), Vector2i(cw, ch))
	return sheet


## The package colours (house_dressing.SWATCHES) as 0.25 m cubes in a row on a prop's top, shot from its front; each
## cube's front face is sampled (7 x 7 px) into result["swatches"]: {name, hex, seen}.
func _swatches(sw: Dictionary, result: Dictionary) -> Image:
	var at: Vector3 = _v(sw["at"])
	var along: Vector3 = Vector3(sw["along"][0], 0, sw["along"][1])
	var facing: Vector3 = Vector3(sw["facing"][0], 0, sw["facing"][1])
	var colors: Array = sw["colors"]
	var cubes: Array[Vector3] = []
	for i: int in colors.size():
		var box: MeshInstance3D = MeshInstance3D.new()
		var mesh: BoxMesh = BoxMesh.new()
		mesh.size = Vector3(0.25, 0.25, 0.25)
		box.mesh = mesh
		var paint: StandardMaterial3D = StandardMaterial3D.new()
		paint.albedo_color = Color.html(String(colors[i]["hex"]))
		paint.roughness = 0.9
		box.material_override = paint
		box.position = at + along * ((i - (colors.size() - 1) * 0.5) * 0.32) + Vector3(0, 0.125, 0)
		root.add_child(box)
		cubes.append(box.position)
	var image: Image = await _shot("swatches", "package colours under the c2 lamps",
		at + facing * 1.4 + Vector3(0, 0.6, 0), at + Vector3(0, 0.1, 0), result, 60.0)
	var k: Vector2 = Vector2(image.get_size()) / root.get_visible_rect().size
	var out: Array = []
	for i: int in colors.size():
		var px: Vector2 = _camera.unproject_position(cubes[i] + facing * 0.125) * k
		var sum: Color = Color(0, 0, 0)
		var n: int = 0
		for dx: int in range(-3, 4):
			for dy: int in range(-3, 4):
				var q: Vector2i = Vector2i(int(px.x) + dx, int(px.y) + dy)
				if q.x >= 0 and q.y >= 0 and q.x < image.get_width() and q.y < image.get_height():
					sum += image.get_pixelv(q)
					n += 1
		var seen: Color = sum / float(maxi(n, 1))
		out.append({"name": colors[i]["name"], "hex": colors[i]["hex"], "seen": seen.to_html(false)})
	result["swatches"] = out
	return image


## The meshes and triangles under a room's Dressing and Fixtures groups (a placeholder box counts 12).
func _dressing_triangles(path: String) -> Dictionary:
	var meshes: int = 0
	var tris: int = 0
	var room: Node = _house.get_node_or_null(path)
	if room == null:
		return {"dressing_meshes": 0, "dressing_triangles": 0, "dressing_node": "missing: " + path}
	for group: String in ["Dressing", "Fixtures"]:
		var g: Node = room.get_node_or_null(group)
		if g == null:
			continue
		for n: Node in g.find_children("*", "MeshInstance3D", true, false):
			var mesh: Mesh = (n as MeshInstance3D).mesh
			if mesh == null:
				continue
			meshes += 1
			for i: int in mesh.get_surface_count():
				var arrays: Array = mesh.surface_get_arrays(i)
				var index: Variant = arrays[Mesh.ARRAY_INDEX]
				var count: int = (index as PackedInt32Array).size() if index != null else (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()
				tris += count / 3
		for n: Node in g.find_children("*", "CSGBox3D", true, false):
			meshes += 1
			tris += 12
	return {"dressing_meshes": meshes, "dressing_triangles": tris}


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
	printerr("WALK error %s" % why)
	quit(1)
