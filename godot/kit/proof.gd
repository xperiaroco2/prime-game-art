extends SceneTree
## The House kit's proof for `tools/run.py kit --proof DIR` (docs/kit.md): a test room (6 x 4 m, a door and a window),
## a 2 m corridor and a stair flight to a second-floor landing, assembled from the imported kit pieces, lit with the
## house lab's round-3 settings (r3_v1 knobs: dusk sky, fog, sun, warm lamps c2, filmic exposure 1.5, saturation 1.35,
## SSAO; SDFGI stands in for the lab's baked LightmapGI), walked by capsules and shot at eye height 1.6 m.
## Pictures need a real window placed off-screen (the runner passes --position -30000,-30000), never headless:
##   godot --path godot --position -30000,-30000 --resolution 1600x900 -s res://kit/proof.gd -- <request.json> <out dir>
## request.json: {"pieces": {"<id>": {"scene": "res://import/kit_<id>.glb", "min": [x, y, z], "max": [x, y, z]}}}.
## Writes <out>/<shot>.png, <out>/sheet.png (1280 px wide) and <out>/proof.json (the walks); prints PROOF saved <dir>.

const WATCHDOG_S: float = 170.0
const EYE: float = 1.6
const UP := Vector3.UP
const LAMP := Color(1.0, 0.85, 0.68)
const SHEET_W: int = 1280
const GAP: int = 4
const LINEUP_Z: float = 40.0
const LINEUP_LAYER: int = 2

var _req: Dictionary
var _out: String
var _house: Node3D
var _camera: Camera3D
var _label: Label


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
	_req = request["pieces"]
	_out = args[1]
	DirAccess.make_dir_recursive_absolute(_out)
	_house = Node3D.new()
	root.add_child(_house)
	_environment()
	_build_house()
	var lineup_box: AABB = _build_lineup()
	_camera = Camera3D.new()
	_camera.fov = 70.0
	_camera.near = 0.05
	root.add_child(_camera)
	_camera.make_current()
	var layer: CanvasLayer = CanvasLayer.new()
	_label = Label.new()
	_label.position = Vector2(16, 10)
	_label.add_theme_font_size_override("font_size", 48)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 8)
	layer.add_child(_label)
	root.add_child(layer)
	for i: int in 3:
		await physics_frame
	var result: Dictionary = {"walks": {}}
	# The package carrier: a capsule 0.8 m wide through the 1.4 m door, the corridor and up the flight to the landing.
	result["walks"]["package_0.8m"] = await _walk(0.4, [Vector3(3, 0.05, 1.5), Vector3(3, 0, 4), Vector3(3, 0, 5),
		Vector3(6.3, 0, 5), Vector3(12.6, 3.2, 5), Vector3(15.0, 3.2, 5)], true)
	# The control: a capsule 1.5 m wide must stop at the door (the colliders block).
	result["walks"]["control_1.5m"] = await _walk(0.75, [Vector3(3, 0.05, 1.5), Vector3(3, 0, 5)], false)
	var shots: Array = [
		["room_corner", "test room 6 x 4 m, from the SW corner", Vector3(0.6, EYE, 0.6), Vector3(5.6, 1.3, 3.8)],
		["room_window", "test room, the window wall", Vector3(5.4, EYE, 3.5), Vector3(0.6, 1.2, 0.2)],
		["room_door", "through the 1.4 m door from the corridor", Vector3(3.0, EYE, 5.5), Vector3(3.0, 1.3, 0.5)],
		["corridor", "corridor 2 m, towards the stairs", Vector3(0.6, EYE, 5.0), Vector3(12.0, 2.4, 5.0)],
		["stairs_up", "stairs_main, up to the 3.2 m landing", Vector3(4.6, EYE, 5.0), Vector3(12.0, 3.9, 5.0)],
		["stairs_down", "from the landing, down the flight", Vector3(15.4, 3.2 + EYE, 5.0), Vector3(6.0, 0.6, 5.0)],
	]
	var images: Array[Image] = []
	for s: Array in shots:
		images.append(await _shot(s[0], s[1], s[2], s[3]))
	result["shots"] = shots.map(func(s: Array) -> String: return s[0])
	var lineup: Image = await _lineup_shot(lineup_box)
	_save(_sheet(lineup, images), _out.path_join("sheet.png"))
	var f: FileAccess = FileAccess.open(_out.path_join("proof.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(result, " "))
	f.close()
	print("PROOF saved %s" % _out)
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
	env.adjustment_contrast = 1.0
	env.glow_enabled = true
	env.glow_hdr_threshold = 0.9
	env.glow_intensity = 0.5
	env.ssao_enabled = true
	env.ssao_intensity = 1.0
	env.ssao_radius = 0.8
	env.sdfgi_enabled = true
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_light_color = Color(0.3, 0.27, 0.4)
	env.fog_light_energy = 0.8
	env.fog_depth_begin = 30.0
	env.fog_depth_end = 140.0
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.light_color = Color(0.55, 0.65, 1.0)
	sun.light_energy = 0.35
	sun.rotation_degrees = Vector3(-14.0, 200.0, 0.0)
	sun.shadow_enabled = true
	root.add_child(sun)
	var ground: MeshInstance3D = MeshInstance3D.new()
	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(200, 200)
	ground.mesh = plane
	var earth: StandardMaterial3D = StandardMaterial3D.new()
	earth.albedo_color = Color(0.16, 0.13, 0.11)
	earth.roughness = 1.0
	ground.material_override = earth
	ground.position = Vector3(0, -0.21, 0)
	root.add_child(ground)


func _build_house() -> void:
	var y2: float = 3.2
	# Ground floor: the room (x 0..6, z 0..4), the corridor (z 4..6), the stairwell (x 6..16, z 4..6).
	_tiles("floor_boards_2x2", 0, 6, 0, 4, 0.0)
	_tiles("floor_lino_2x2", 0, 6, 4, 6, 0.0)
	_tiles("floor_concrete_2x2", 6, 16, 4, 6, 0.0)
	_tiles("ceiling_2x2", 0, 6, 0, 6, 3.0)
	_tiles("ceiling_2x2", 12, 16, 4, 6, 3.0)
	_tiles("floor_boards_2x2", 12, 16, 4, 6, y2)
	_tiles("ceiling_2x2", 6, 16, 4, 6, y2 + 3.0)
	_line(["wall_storey_2m_ext", "wall_storey_2m_window_ext", "wall_storey_2m_ext"], Vector3(0, 0, 0), Vector3(6, 0, 0), Vector3.FORWARD)
	_line(["wall_storey_2m_ext", "wall_storey_2m_ext", "wall_storey_2m_ext"], Vector3(0, 0, 0), Vector3(0, 0, 6), Vector3.LEFT)
	_line(["wall_storey_2m_ext", "wall_storey_2m_window_ext"], Vector3(6, 0, 0), Vector3(6, 0, 4), Vector3.RIGHT)
	_line(["wall_storey_2m_int", "wall_storey_2m_door_int", "wall_storey_2m_int"], Vector3(0, 0, 4), Vector3(6, 0, 4), Vector3.BACK)
	_line(_n("wall_storey_2m_ext", 8), Vector3(0, 0, 6), Vector3(16, 0, 6), Vector3.BACK)
	_line(_n("wall_storey_2m_ext", 5), Vector3(6, 0, 4), Vector3(16, 0, 4), Vector3.FORWARD)
	_line(["wall_storey_2m_ext"], Vector3(16, 0, 4), Vector3(16, 0, 6), Vector3.RIGHT)
	for c: Array in [[0, 0, 180.0], [6, 0, 90.0], [0, 6, -90.0], [16, 6, 0.0], [16, 4, 90.0]]:
		_put("wall_storey_corner_ext", Vector3(c[0], 0, c[1]), c[2])
	# Upper storey round the stairwell and the landing.
	_line(_n("wall_storey_2m_ext", 5), Vector3(6, y2, 6), Vector3(16, y2, 6), Vector3.BACK)
	_line(_n("wall_storey_2m_ext", 5), Vector3(6, y2, 4), Vector3(16, y2, 4), Vector3.FORWARD)
	_line(["wall_storey_2m_ext"], Vector3(16, y2, 4), Vector3(16, y2, 6), Vector3.RIGHT)
	_line(["wall_storey_2m_ext"], Vector3(6, y2, 4), Vector3(6, y2, 6), Vector3.LEFT)
	for c: Array in [[16, 6, 0.0], [16, 4, 90.0], [6, 4, 180.0], [6, 6, -90.0]]:
		_put("wall_storey_corner_ext", Vector3(c[0], y2, c[1]), c[2])
	_put("stairs_main", Vector3(6, 0, 4), 0.0)
	for at: Vector3 in [Vector3(3, 2.7, 2), Vector3(3, 2.7, 5), Vector3(9, 4.6, 5), Vector3(14, 5.8, 5)]:
		var lamp: OmniLight3D = OmniLight3D.new()
		lamp.light_color = LAMP
		lamp.light_energy = 3.0
		lamp.omni_range = 6.0
		lamp.light_size = 0.06
		lamp.shadow_enabled = true
		lamp.position = at
		_house.add_child(lamp)


func _n(id: String, count: int) -> Array:
	var out: Array = []
	for i: int in count:
		out.append(id)
	return out


## Pieces along the grid line a..b with their exterior side towards `ext`: a wall runs along its local +X with its
## exterior at local +Z, so the run goes along UP x ext from whichever end that direction starts.
func _line(ids: Array, a: Vector3, b: Vector3, ext: Vector3) -> void:
	var d: Vector3 = UP.cross(ext)
	var start: Vector3 = a if (b - a).dot(d) > 0 else b
	var basis: Basis = Basis(d, UP, ext)
	var x: float = 0.0
	for id: String in ids:
		var n: Node3D = _instance(id)
		n.transform = Transform3D(basis, start + d * x)
		_house.add_child(n)
		x += _width(id)


func _tiles(id: String, x0: float, x1: float, z0: float, z1: float, y: float) -> void:
	var w: float = _width(id)
	var x: float = x0
	while x < x1 - 0.01:
		var z: float = z0
		while z < z1 - 0.01:
			_put(id, Vector3(x, y, z), 0.0)
			z += w
		x += w


func _put(id: String, at: Vector3, turn_deg: float) -> Node3D:
	var n: Node3D = _instance(id)
	n.position = at
	n.rotation_degrees.y = turn_deg
	_house.add_child(n)
	return n


func _instance(id: String) -> Node3D:
	if not _req.has(id):
		_fail("no piece %s in the request" % id)
	return (load(_req[id]["scene"]) as PackedScene).instantiate() as Node3D


func _width(id: String) -> float:
	return roundf(float(_req[id]["max"][0]) - float(_req[id]["min"][0]))


## Every piece in a row-packed line-up north of the house, with a 5 m bar of 1 m blocks in front; its own neutral key
## light (render layer 2 only). Returns the line-up's box.
func _build_lineup() -> AABB:
	var lineup: Node3D = Node3D.new()
	root.add_child(lineup)
	var x: float = 0.0
	var z: float = LINEUP_Z
	var row_depth: float = 0.0
	var box: AABB = AABB(Vector3(0, 0, LINEUP_Z), Vector3.ZERO)
	for id: String in _req:
		var lo: Vector3 = _v(_req[id]["min"])
		var hi: Vector3 = _v(_req[id]["max"])
		var size: Vector3 = hi - lo
		if x > 0.0 and x + size.x > 30.0:
			x = 0.0
			z -= row_depth + 1.2
			row_depth = 0.0
		var n: Node3D = _instance(id)
		n.position = Vector3(x - lo.x, -lo.y, z - hi.z)
		lineup.add_child(n)
		box = box.merge(AABB(n.position + lo, size))
		x += size.x + 0.6
		row_depth = maxf(row_depth, size.z)
	for i: int in 5:
		var bar: MeshInstance3D = MeshInstance3D.new()
		var cube: BoxMesh = BoxMesh.new()
		cube.size = Vector3(1.0, 0.08, 0.15)
		bar.mesh = cube
		var m: StandardMaterial3D = StandardMaterial3D.new()
		m.albedo_color = Color(0.9, 0.9, 0.9) if i % 2 == 0 else Color(0.05, 0.05, 0.05)
		bar.material_override = m
		bar.position = Vector3(0.5 + i, 0.04, LINEUP_Z + 0.8)
		lineup.add_child(bar)
	for g: Node in lineup.find_children("*", "GeometryInstance3D", true, false):
		(g as GeometryInstance3D).layers = 1 << (LINEUP_LAYER - 1)
	var key: DirectionalLight3D = DirectionalLight3D.new()
	key.light_cull_mask = 1 << (LINEUP_LAYER - 1)
	key.light_energy = 1.2
	key.rotation_degrees = Vector3(-50.0, 210.0, 0.0)  # shines towards +Z, the camera side
	key.shadow_enabled = true
	root.add_child(key)
	return box


# --- the walk check ------------------------------------------------------------------------------------------------
## A capsule (radius r, 1.8 m) walks the waypoints at 3 m/s; passes when it reaches the last within 0.3 m (and its
## height within 0.15 m), or, for a control (`must_pass` false), when it does not.
func _walk(r: float, points: Array, must_pass: bool) -> Dictionary:
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
	body.global_position = points[0]
	var reached: int = 0
	var dt: float = 1.0 / Engine.physics_ticks_per_second
	var steps: int = 0
	var max_y: float = 0.0
	while steps < 12 * Engine.physics_ticks_per_second and reached < points.size() - 1:
		await physics_frame
		steps += 1
		var target: Vector3 = points[reached + 1]
		var flat: Vector3 = Vector3(target.x - body.global_position.x, 0, target.z - body.global_position.z)
		if flat.length() < 0.3:
			reached += 1
			continue
		var v: Vector3 = flat.normalized() * 3.0
		v.y = 0.0 if body.is_on_floor() else body.velocity.y - 9.8 * dt
		body.velocity = v
		body.move_and_slide()
		max_y = maxf(max_y, body.global_position.y)
	var end: Vector3 = body.global_position
	var arrived: bool = reached == points.size() - 1 and absf(end.y - (points[-1] as Vector3).y) < 0.15
	body.queue_free()
	return {"radius_m": r, "waypoints": points.size(), "reached": reached + 1, "end": [end.x, end.y, end.z],
		"max_y": max_y, "seconds": steps * dt, "arrived": arrived, "pass": arrived == must_pass}


# --- pictures ------------------------------------------------------------------------------------------------------
func _shot(name: String, title: String, from: Vector3, to: Vector3) -> Image:
	_camera.fov = 70.0
	_camera.cull_mask = 1
	_camera.look_at_from_position(from, to, UP)
	_label.text = "%s   (eye %.1f m)" % [title, from.y - (3.2 if from.y > 3.2 + 0.5 else 0.0)]
	var image: Image = await _grab()
	_save(image, _out.path_join("%s.png" % name))
	return image


func _lineup_shot(box: AABB) -> Image:
	_camera.fov = 40.0
	_camera.cull_mask = 1 << (LINEUP_LAYER - 1)
	var c: Vector3 = box.get_center()
	var half_w: float = box.size.x * 0.5 + 1.0
	var d: float = 1.25 * half_w / tan(deg_to_rad(33.0))
	var dir: Vector3 = Vector3(0, sin(deg_to_rad(35.0)), cos(deg_to_rad(35.0)))
	_camera.look_at_from_position(c + dir * d, c, UP)
	_label.text = "House kit v1: %d pieces (bar: 5 x 1 m)" % _req.size()
	var image: Image = await _grab()
	_save(image, _out.path_join("lineup.png"))
	return image


func _grab() -> Image:
	for i: int in 30:
		await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	return image


## The line-up across the top (1280 px wide), the six eye-height views in two rows of three under it.
func _sheet(lineup: Image, shots: Array[Image]) -> Image:
	var top: Image = lineup.duplicate() as Image
	top.resize(SHEET_W, int(SHEET_W * lineup.get_height() / float(lineup.get_width())), Image.INTERPOLATE_LANCZOS)
	var cw: int = (SHEET_W - 2 * GAP) / 3
	var ch: int = int(cw * shots[0].get_height() / float(shots[0].get_width()))
	var sheet: Image = Image.create_empty(SHEET_W, top.get_height() + 2 * (ch + GAP), false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.97, 0.97, 0.97))
	sheet.blit_rect(top, Rect2i(Vector2i.ZERO, top.get_size()), Vector2i.ZERO)
	for i: int in shots.size():
		var img: Image = shots[i].duplicate() as Image
		img.resize(cw, ch, Image.INTERPOLATE_LANCZOS)
		sheet.blit_rect(img, Rect2i(Vector2i.ZERO, img.get_size()),
			Vector2i((i % 3) * (cw + GAP), top.get_height() + GAP + (i / 3) * (ch + GAP)))
	return sheet


func _v(a: Array) -> Vector3:
	return Vector3(a[0], a[1], a[2])


func _save(image: Image, path: String) -> void:
	var error: Error = image.save_png(path)
	if error != OK:
		_fail("cannot save %s: %s" % [path, error_string(error)])


func _fail(why: String) -> void:
	printerr("PROOF error %s" % why)
	quit(1)
