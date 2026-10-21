extends SceneTree
## The empty ship in Godot for `tools/run.py ship` (art #263, docs/ship.md): places every piece GLB by the layout's
## placements (pieces imported with `-col` meshes carry their trimesh colliders), then either checks it headless or
## shoots it at night in an off-screen window. The EXTERIOR lane owns this folder after the foundation step.
##   godot --headless --path godot -s res://ship/ship.gd -- <request.json> <out>          (mode "check")
##   PRIME_WINDOW=1920x1080 godot --path godot --position 30000,30000 --resolution 1x1 -s res://ship/ship.gd
##       -- <request.json> <out>                                                          (mode "shoot")
## request.json (tools/runner/commands/ship.py): {"mode", "pieces": {id: res}, "place": [[id, [x, h, y], yaw]],
##   "collide": [id], "bounds": {id: {"min", "max"}}, "walk": {"r", "h", "points"}, "light": {"moon_dir_deg",
##   "moon_energy", "lamps": [[x, h, y, energy, range, r, g, b]]}, "views": [[name, title, eye, look, fov]],
##   "top": {"name", "title", "size_m"}, "compare": [[shot, reference image]]}.
## check: <out>/check.json {"bounds": {id: {min, max}} (each piece at the origin), "colliders": {id: n}, "walk"}.
## shoot: <out>/<view>.png at the window's size, compare_<shot>.png (the reference left, the shot right),
##   sheet.png (1280 px wide) and shots.json; prints SHIP saved <dir>.
## video (off-screen window, as shoot): "video": {"fps", "fov", "keys": [[eye, look, seconds]]} (Godot coordinates):
##   the camera through the keys (cubic in time), one PNG per frame in <out>/frames/, video.json; "watchdog_s".

const Offscreen = preload("res://lib/offscreen.gd")
const WATCHDOG_S: float = 240.0
const UP := Vector3.UP
const SPEED: float = 3.0
const SHEET_W: int = 1280
const GAP: int = 4

var _req: Dictionary
var _out: String
var _camera: Camera3D
var _label: Label
var _scenes: Dictionary = {}
var _metals: Dictionary = {}

## The shared metal library (metal.gdshader) by glTF material name: base colour, metallic, roughness, grain, seams,
## scratches, grime. Other materials keep their glTF look.
const METALS: Dictionary = {
	"hull_silver": [Color(0.66, 0.68, 0.71), 0.6, 0.36, 0.6, 0.35, 0.55, 0.25],
	"ext_silver_b": [Color(0.74, 0.76, 0.79), 0.6, 0.32, 0.6, 0.35, 0.5, 0.2],
	"ext_silver_c": [Color(0.56, 0.58, 0.61), 0.6, 0.4, 0.6, 0.35, 0.6, 0.3],
	"hull_dark": [Color(0.12, 0.125, 0.13), 0.8, 0.42, 0.4, 0.2, 0.4, 0.3],
	"ext_frame": [Color(0.17, 0.18, 0.19), 0.85, 0.34, 0.35, 0.0, 0.35, 0.2],
	"leg_metal": [Color(0.32, 0.33, 0.35), 0.9, 0.36, 0.5, 0.15, 0.6, 0.35],
	"wall_panel": [Color(0.42, 0.44, 0.47), 0.75, 0.4, 0.4, 0.4, 0.3, 0.25],
	"ceiling": [Color(0.36, 0.38, 0.41), 0.75, 0.42, 0.4, 0.4, 0.2, 0.2],
	"ext_seam": [Color(0.035, 0.037, 0.04), 0.6, 0.6, 0.0, 0.0, 0.0, 0.0],
}
const METAL_KEYS: Array = ["metallic", "roughness", "grain", "seams", "scratches", "grime"]
const LIGHT_CELL_M: float = 1.6
const MAX_LIGHTS: int = 96


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
	if _req["mode"] in ["shoot", "video"]:
		if DisplayServer.get_name() == "headless":
			_fail("shoot needs a window (off-screen), not --headless")
			return
		var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
		if placed != "":
			_fail(placed)
			return
	var watchdog: float = float(_req.get("watchdog_s", WATCHDOG_S))
	create_timer(watchdog).timeout.connect(_fail.bind("not done within %d s" % watchdog))
	if _req["mode"] == "check":
		_check()
	elif _req["mode"] == "video":
		_video()
	else:
		_shoot()


# --- the scene -----------------------------------------------------------------------------------------------------
func _scene(pid: String) -> PackedScene:
	if not _scenes.has(pid):
		_scenes[pid] = load(_req["pieces"][pid]) as PackedScene
		if _scenes[pid] == null:
			_fail("cannot load %s" % _req["pieces"][pid])
	return _scenes[pid]


func _build() -> Node3D:
	var ship: Node3D = Node3D.new()
	ship.name = "Ship"
	root.add_child(ship)
	for p: Array in _req["place"]:
		var node: Node3D = _scene(p[0]).instantiate() as Node3D
		node.name = "%s_%d" % [p[0], ship.get_child_count()]
		node.position = _v(p[1])
		node.rotation_degrees.y = float(p[2])
		ship.add_child(node)
	var ground: StaticBody3D = StaticBody3D.new()
	var shape: CollisionShape3D = CollisionShape3D.new()
	shape.shape = WorldBoundaryShape3D.new()
	ground.add_child(shape)
	root.add_child(ground)
	if _req["pieces"].has("ground"):  # the clearing's own ground piece draws it
		return ship
	var mesh: MeshInstance3D = MeshInstance3D.new()
	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(200, 200)
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.albedo_color = Color(0.09, 0.11, 0.07)
	mat.roughness = 1.0
	plane.material = mat
	mesh.mesh = plane
	ground.add_child(mesh)
	return ship


## A piece's bounds at the origin (its meshes' AABBs in the piece's frame) and its colliders.
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
			var ct: Transform3D = t * (c as Node3D).transform if c is Node3D else t
			stack.append([c, ct])
	node.free()
	return [box, colliders]


func _check() -> void:
	var result: Dictionary = {"bounds": {}, "colliders": {}}
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
	_write("check.json", result)
	print("SHIP check saved %s" % _out)
	quit(0)


## A capsule (radius r, height h) walks the waypoints at 3 m/s with gravity; it arrives when it reaches the last one
## within 0.3 m and its height within 0.15 m.
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
	return {"radius_m": r, "of": points.size(), "reached": reached + 1, "end": [end.x, end.y, end.z],
		"min_y": min_y, "seconds": steps * dt, "arrived": arrived, "stuck": [last_pos.x, last_pos.y, last_pos.z]}


# --- pictures ------------------------------------------------------------------------------------------------------
## The night: the star sky (night_sky.gdshader), the look of godot/showroom/look_presets.json's High preset (AgX,
## SSAO 0.6 / 1.5) at exposure 1.1 for a night exterior, glow for the emissive strips, SSIL, a thin blue distance fog,
## the moonlight and the layout's lamps.
func _environment() -> void:
	var light: Dictionary = _req["light"]
	var env: Environment = Environment.new()
	var sky: Sky = Sky.new()
	var sm: ShaderMaterial = ShaderMaterial.new()
	sm.shader = load("res://ship/night_sky.gdshader") as Shader
	sky.sky_material = sm
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.13, 0.155, 0.24)
	env.ambient_light_energy = _lk("ambient_energy", 0.9)
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = _lk("exposure", 1.2)
	env.glow_enabled = true
	env.glow_intensity = 0.6
	env.glow_bloom = 0.03
	env.glow_hdr_threshold = 1.0
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	env.ssao_enabled = true
	env.ssao_radius = 0.6
	env.ssao_intensity = 1.5
	env.ssil_enabled = true
	env.fog_enabled = true
	env.fog_light_color = Color(0.05, 0.07, 0.12)
	env.fog_density = 0.0045
	env.fog_sky_affect = 0.0
	var we: WorldEnvironment = WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	var moon: DirectionalLight3D = DirectionalLight3D.new()
	moon.light_color = Color(0.62, 0.72, 1.0)
	moon.light_energy = float(light["moon_energy"])
	moon.shadow_enabled = true
	moon.directional_shadow_max_distance = 90.0
	moon.rotation_degrees = Vector3(float(light["moon_dir_deg"][0]), float(light["moon_dir_deg"][1]), 0)
	root.add_child(moon)
	for l: Array in light["lamps"]:
		var omni: OmniLight3D = OmniLight3D.new()
		omni.position = Vector3(float(l[0]), float(l[1]), float(l[2]))
		omni.light_energy = float(l[3]) * _lk("lamp_scale", 1.0)
		omni.omni_range = float(l[4])
		omni.light_color = Color(float(l[5]), float(l[6]), float(l[7]))
		omni.shadow_enabled = true
		root.add_child(omni)


## A look number from the request's light table (ship.toml [light]), else its default.
func _lk(key: String, default: float) -> float:
	return float((_req["light"] as Dictionary).get(key, default))


## The shared metal for a library material name (one ShaderMaterial per name, shared by every piece).
func _metal(name: String) -> Material:
	if not _metals.has(name):
		var m: Array = METALS[name]
		var sm: ShaderMaterial = ShaderMaterial.new()
		sm.shader = load("res://ship/metal.gdshader") as Shader
		var c: Color = m[0]
		sm.set_shader_parameter("base_color", Vector3(c.r, c.g, c.b))
		for i: int in METAL_KEYS.size():
			sm.set_shader_parameter(METAL_KEYS[i], float(m[i + 1]))
		if name in ["hull_silver", "ext_silver_b", "ext_silver_c"]:  # the moonlit wing plates (exterior-2, open 5)
			sm.set_shader_parameter("roughness", minf(float(m[2]) + _lk("hull_rough_add", 0.0), 0.95))
		_metals[name] = sm
	return _metals[name]


## The look: the library metal on every surface whose glTF material is one; an omni light for every cell of emissive
## surfaces (the lamp and strip pieces light the ship). Returns the number of lights it added.
func _dress(ship: Node3D) -> int:
	var cells: Dictionary = {}
	var seen: Dictionary = {}
	var stack: Array = [ship]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		stack.append_array(n.get_children())
		if not (n is MeshInstance3D) or (n as MeshInstance3D).mesh == null:
			continue
		var mi: MeshInstance3D = n
		for i: int in mi.mesh.get_surface_count():
			var mat: Material = mi.mesh.surface_get_material(i)
			if mat == null:
				continue
			if METALS.has(mat.resource_name):
				mi.set_surface_override_material(i, _metal(mat.resource_name))
			elif mat is BaseMaterial3D and mat.resource_name.begins_with("int_silver") and not seen.has(mat):
				var im: BaseMaterial3D = mat  # the interior's metal: mid-to-dark brushed silver at night
				seen[im] = 0.0
				im.albedo_color = im.albedo_color * Color(1, 1, 1, 1) * _lk("int_value", 1.0)
				im.albedo_color.a = 1.0
				im.roughness = minf(im.roughness + _lk("int_rough_add", 0.0), 0.95)
			elif mat is BaseMaterial3D and (mat as BaseMaterial3D).emission_enabled:
				var bm: BaseMaterial3D = mat
				if not seen.has(bm):  # a shared glTF material is scaled once; its strip light keeps the original
					seen[bm] = bm.emission_energy_multiplier
					bm.emission_energy_multiplier *= _lk("emission_scale", 1.0)
				var box: AABB = mi.global_transform * mi.mesh.get_aabb()
				var area: float = maxf(box.size.x * box.size.z, maxf(box.size.x * box.size.y, box.size.y * box.size.z))
				var c: Vector3 = box.get_center()
				var key: String = "%d_%d_%d_%s" % [floori(c.x / LIGHT_CELL_M), floori(c.y / LIGHT_CELL_M),
					floori(c.z / LIGHT_CELL_M), bm.emission.to_html(false)]
				if not cells.has(key):
					cells[key] = [Vector3.ZERO, 0.0, bm.emission, 0.0]
				var cell: Array = cells[key]
				cell[0] = (cell[0] as Vector3) + c * area
				cell[1] = float(cell[1]) + area
				cell[3] = maxf(float(cell[3]), float(seen[bm]))
	var list: Array = cells.values()
	list.sort_custom(func(a: Array, b: Array) -> bool: return float(a[1]) > float(b[1]))
	for cell: Array in list.slice(0, MAX_LIGHTS):
		var omni: OmniLight3D = OmniLight3D.new()
		omni.position = (cell[0] as Vector3) / maxf(float(cell[1]), 1e-6) + Vector3(0, 0.12, 0)
		omni.light_color = (cell[2] as Color).lightened(_lk("strip_whiten", 0.15))
		omni.light_energy = clampf(sqrt(float(cell[1])) * 0.9 * minf(float(cell[3]), 6.0) / 3.0, 0.08, 1.6) * _lk("strip_light_scale", 1.0)
		omni.omni_range = clampf(2.2 + sqrt(float(cell[1])) * 2.0, 2.2, 5.0)
		omni.omni_attenuation = 1.6
		root.add_child(omni)
	return mini(list.size(), MAX_LIGHTS)


## A reflection probe per room (the request's rooms: [id, centre [x, h, y], size [x, h, y], interior]).
func _probes() -> void:
	for r: Array in _req.get("rooms", []):
		var probe: ReflectionProbe = ReflectionProbe.new()
		probe.position = _v(r[1])
		probe.size = _v(r[2])
		probe.box_projection = true
		probe.interior = bool(r[3])
		probe.update_mode = ReflectionProbe.UPDATE_ONCE
		probe.intensity = _lk("probe_intensity", 1.0) if bool(r[3]) else 1.0
		root.add_child(probe)


func _shoot() -> void:
	_environment()
	var lights: int = _dress(_build())
	_probes()
	print("SHIP look: %d emissive lights" % lights)
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.far = 500.0
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
	var shots: Dictionary = {}
	var images: Dictionary = {}
	for v: Array in _req["views"]:
		_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
		_camera.fov = float(v[4])
		_camera.look_at_from_position(_v(v[2]), _v(v[3]), UP)
		images[v[0]] = await _shot(v[0], v[1], shots)
	var top: Dictionary = _req["top"]
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_camera.size = float(top["size_m"])
	_camera.keep_aspect = Camera3D.KEEP_WIDTH
	# looking straight down with +z (south) up the picture: east falls on the left, as plan-3.jpg
	_camera.look_at_from_position(Vector3(0, 60, 0), Vector3.ZERO, Vector3(0, 0, 1))
	images[top["name"]] = await _shot(top["name"], top["title"], shots)
	var rows: Array = []
	for c: Array in _req["compare"]:
		var ref: Image = Image.load_from_file(c[1])
		if ref == null:
			_fail("cannot load %s" % c[1])
			return
		ref.convert(Image.FORMAT_RGB8)
		var pair: Image = _sheet([[ref, images[c[0]]]])
		_save(pair, _out.path_join("compare_%s.png" % c[0]))
	var names: Array = images.keys()
	for i: int in range(0, names.size(), 3):
		rows.append(names.slice(i, i + 3).map(func(n: String) -> Image: return images[n]))
	_save(_sheet(rows), _out.path_join("sheet.png"))
	_write("shots.json", {"shots": shots})
	print("SHIP saved %s" % _out)
	quit(0)


## The walk-through: the night scene as shoot dresses it, the camera at eye height through the keys, every frame
## saved as a PNG (the runner encodes them with Blender's FFmpeg).
func _video() -> void:
	_environment()
	var lights: int = _dress(_build())
	_probes()
	var v: Dictionary = _req["video"]
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.far = 500.0
	_camera.fov = float(v["fov"])
	root.add_child(_camera)
	_camera.make_current()
	var keys: Array = v["keys"]
	var times: Array = [0.0]
	for i: int in range(1, keys.size()):
		times.append(float(times[-1]) + float(keys[i][2]))
	var fps: float = float(v["fps"])
	var count: int = int(float(times[-1]) * fps) + 1
	var dir: String = _out.path_join("frames")
	DirAccess.make_dir_recursive_absolute(dir)
	_camera.look_at_from_position(_v(keys[0][0]), _v(keys[0][1]), UP)
	for i: int in 30:  # the probes, SSAO and glow settle
		await process_frame
	var started: int = Time.get_ticks_msec()
	var k: int = 0
	for f: int in count:
		var t: float = minf(f / fps, float(times[-1]))
		while k < keys.size() - 2 and t > float(times[k + 1]):
			k += 1
		var w: float = (t - float(times[k])) / (float(times[k + 1]) - float(times[k]))
		_camera.look_at_from_position(_key(keys, times, k, w, 0), _key(keys, times, k, w, 1), UP)
		await RenderingServer.frame_post_draw
		var image: Image = root.get_texture().get_image()
		image.convert(Image.FORMAT_RGB8)
		_save(image, dir.path_join("%05d.png" % f))
	_write("video.json", {"frames": count, "fps": fps, "seconds": times[-1], "lights": lights,
		"render_s": (Time.get_ticks_msec() - started) / 1000.0})
	print("SHIP video %d frames" % count)
	quit(0)


## Key j (0 eye, 1 look) between keys k and k + 1 at weight w, cubic in time through the neighbouring keys.
func _key(keys: Array, times: Array, k: int, w: float, j: int) -> Vector3:
	var a: Vector3 = _v(keys[k][j])
	var b: Vector3 = _v(keys[k + 1][j])
	var span: float = float(times[k + 1]) - float(times[k])
	var pre: Vector3 = _v(keys[k - 1][j]) if k > 0 else a
	var pre_t: float = float(times[k - 1]) - float(times[k]) if k > 0 else -span
	var post: Vector3 = _v(keys[k + 2][j]) if k + 2 < keys.size() else b
	var post_t: float = float(times[k + 2]) - float(times[k]) if k + 2 < keys.size() else 2.0 * span
	return a.cubic_interpolate_in_time(b, pre, post, w, span, pre_t, post_t)


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


## Each row's tiles side by side over SHEET_W (each tile scaled to the row's first tile's height), rows stacked.
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
	printerr("SHIP error %s" % why)
	quit(1)
