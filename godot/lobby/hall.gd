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
##   "earth" (step 3b): {"textures": {night, day, clouds: path}, "look", "centre", "radius_deg", "subpoint", "roll_deg",
##   "sun", "sun_energy", "stars"} draws the night Earth as the sky (earth_sky.gdshader) and the window's glass with
##   window_glass.gdshader; an Earth grid's variants are {"id", "title", "earth"}.
## grid: <out>/grid.png, one row per scheme (its views side by side, labelled), and <out>/<scheme>_<view>.png.
## check: <out>/check.json {"bounds": {id: {min, max}} (each piece at its origin), "colliders": {id: n}, "walk",
##   "blocks": {name: walk}}. shoot: <out>/<view>.png, compare_<view>.png (the concept left, the shot right),
##   sheet.png (1280 px wide, two per row) and shots.json.

const Offscreen = preload("res://lib/offscreen.gd")
const WATCHDOG_S: float = 240.0
const SPEED: float = 3.0
const SHEET_W: int = 1280
const GAP: int = 4
const SHIP_LAYER: int = 1 << 10   # step 5a2: the package ship's meshes draw on render layer 11 (its own light set)
const ALL_LAYERS: int = 0xFFFFF

var _req: Dictionary
var _out: String
var _camera: Camera3D
var _label: Label
var _scenes: Dictionary = {}
var _placed: Dictionary = {}   # piece id -> its placed nodes
var _earth: ShaderMaterial      # the sky's material when the request has an Earth (step 3b)
var _textures: Dictionary = {}  # path -> ImageTexture
var _earth_obj: MeshInstance3D   # step 4c: the Earth as a sphere at a finite distance (earth_object.gdshader)
var _far: float = 400.0          # the camera's far plane (step 4c: past the Earth object's shell)
var _env: Environment
var _rig: Node3D                 # step 4: the light rig of the current mood (rebuilt per mood)
var _pkg_info: Dictionary = {}   # step 5a: the ship package's freed nodes, jaws, colliders and lights
var _gen: int = PackedScene.GEN_EDIT_STATE_DISABLED   # step 5b: export_scene.gd instantiates in edit state
var _hide_freed: bool = false    # step 5b: [ship.package] free hidden and disabled instead (a packed scene keeps no removal)
var _emissive: Array = []        # step 4: [mesh, surface, its material, is the ship] of the lens, strip, ring, lamp and the ship's glow surfaces


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
	create_timer(float(_req.get("watchdog_s", WATCHDOG_S))).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	if _req["mode"] == "check":
		_check()
	elif _req["mode"] == "grid":
		_grid()
	elif _req["mode"] == "video":
		_video()
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
	if _req.has("earth"):
		_glass()
	if _req.has("light"):
		_apply_light(_req["light"])
	RenderingServer.viewport_set_measure_render_time(root.get_viewport_rid(), true)
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.far = _far
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
		if look.has("earth"):
			_apply_earth(look["earth"])
		if look.has("light"):   # step 5a5: a variant may set both
			_apply_light(look["light"])
		if not look.has("earth") and not look.has("light"):
			_apply_look(look)
		var row: Array = []
		for v: Array in _req["views"]:
			_camera.fov = float(v[4])
			_camera.look_at_from_position(_v(v[2]), _v(v[3]), Vector3.UP)
			var par: bool = (v[0] as String).begins_with("par_")   # step 5a7: the sky alone, the hall hidden
			var hall: Node3D = root.get_node_or_null("Lobby") as Node3D
			if par and hall != null:
				hall.visible = false
			var nm: String = "%s_%s" % [look["id"], v[0]]
			row.append(await _shot(nm, "%s %s: %s%s" % [look["id"], look["title"], v[0], " (hall hidden)" if par else ""], shots))
			if par:
				shots[nm]["limb"] = _limb(row[-1])
				if hall != null:
					hall.visible = true
		rows.append(row)
	if _req.get("rows", "") == "views":   # step 5a7: a row per view, a column per variant
		var t: Array = []
		for j: int in (rows[0] as Array).size():
			t.append(rows.map(func(r: Array) -> Image: return r[j]))
		rows = t
	_save(_sheet(rows), _out.path_join("grid.png"))
	_write("shots.json", {"shots": shots})
	print("LOBBY grid saved %s" % _out)
	quit(0)


## Step 5a7: the planet's limb in a shot of the sky alone: per column (every 32 px) the first row below the label
## where 6 rows in a row are brighter than 0.06 (a star is smaller), -1 where none.
func _limb(image: Image) -> Array:
	var out: Array = []
	for x: int in range(16, image.get_width(), 32):
		var found: int = -1
		var run: int = 0
		for y: int in range(80, image.get_height()):
			var c: Color = image.get_pixel(x, y)
			run = run + 1 if maxf(c.r, maxf(c.g, c.b)) > 0.06 else 0
			if run == 6:
				found = y - 5
				break
		out.append([x, found])
	return out


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
		var node: Node3D = _scene(p[0]).instantiate(_gen) as Node3D
		node.name = "%s_%d" % [p[0], hall.get_child_count()]
		node.position = _v(p[1])
		node.rotation_degrees.y = float(p[2])
		hall.add_child(node)
		if not _placed.has(p[0]):
			_placed[p[0]] = []
		_placed[p[0]].append(node)
	if _req.has("ship_package"):
		_ship_package(hall, _req["ship_package"])


## Step 5a: art #263's packaged ship (levels/ship/ship.tscn, staged under res://import/ship_pkg/) at the ship's origin:
## the request's "free" nodes freed ("path", or "path:Class" for that node's children of the class), the jaw nose shut
## at once (the package's HANDOFF.md "The jaw nose"). Its key starts with ship_, so _emit scales its glows.
func _ship_package(hall: Node3D, pk: Dictionary) -> void:
	var scn: PackedScene = load(String(pk["scene"])) as PackedScene
	if scn == null:
		_fail("cannot load %s" % pk["scene"])
		return
	var ship: Node3D = scn.instantiate(_gen) as Node3D
	ship.name = "ship_pkg"
	ship.position = _v(pk["at"])
	var freed: Array = []
	for f: String in pk["free"]:
		var parts: PackedStringArray = f.split(":")
		var n: Node = ship.get_node_or_null(NodePath(parts[0]))
		if n == null:
			_fail("ship package: no node %s" % parts[0])
			return
		if parts.size() == 1:
			_drop(n)
			freed.append(f)
			continue
		var k: int = 0
		for c: Node in n.get_children():
			if c.is_class(parts[1]):
				_drop(c)
				k += 1
		freed.append("%s x%d" % [f, k])
	# step 5a3: only the ship itself may stay; any other top-level node of the package (a new scenery group, a sky,
	# a camera, a sun) fails the run instead of drawing into the hall
	var kept: Array = []
	for c: Node in ship.get_children():
		if c.has_meta("lobby_dropped"):
			continue
		kept.append(String(c.name))
		if not (pk["keep"] as Array).has(String(c.name)):
			_fail("ship package: %s is left (not in [ship.package] keep)" % c.name)
			return
	for cls: String in ["WorldEnvironment", "Camera3D", "DirectionalLight3D", "GPUParticles3D", "Decal"]:
		var left: Array = ship.find_children("*", cls, true, false).filter(func(x: Node) -> bool: return not x.has_meta("lobby_dropped") and not (x.get_parent() != null and x.get_parent().has_meta("lobby_dropped")))
		if not left.is_empty():
			_fail("ship package: a %s is left (%s)" % [cls, left[0].name])
			return
	hall.add_child(ship)   # in the tree first: an AnimationPlayer outside it does not apply a seek
	var nose: AnimationPlayer = ship.get_node("Nose/AnimationPlayer") as AnimationPlayer
	nose.play("close")
	nose.seek(nose.current_animation_length, true)
	var jaws: Dictionary = {}
	for j: String in ["jaw_lower", "jaw_upper"]:
		var jn: Node3D = ship.get_node("Nose").find_child(j, true, false) as Node3D
		if jn != null:
			jaws[j] = snappedf(jn.rotation_degrees.x, 0.001)
	var colliders: int = 0
	var lights: int = 0
	var stack: Array = [ship]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		if n.has_meta("lobby_dropped"):   # step 5b: the switched-off clearing keeps its own
			continue
		stack.append_array(n.get_children())
		if n is CollisionShape3D and (n as CollisionShape3D).shape != null:
			colliders += 1
		if n is Light3D:
			lights += 1
		if n is GeometryInstance3D:   # step 5a2: per instance only; the package's files stay as they are
			(n as GeometryInstance3D).layers = SHIP_LAYER
	_pkg_info = {"freed": freed, "kept": kept, "jaws": jaws, "colliders": colliders, "lights": lights}
	_placed["ship_pkg"] = [ship]
	print("LOBBY ship package: %s" % JSON.stringify(_pkg_info))


## A freed node of the package (step 5a), or in the export (step 5b, _hide_freed) the same node switched off by
## overrides a packed scene can keep: hidden, its processing and physics disabled (a StaticBody3D's disable_mode
## removes it from the world), a WorldEnvironment's environment cleared.
func _drop(n: Node) -> void:
	if not _hide_freed:
		n.get_parent().remove_child(n)
		n.free()
		return
	n.set_meta("lobby_dropped", true)
	if n is Node3D:
		(n as Node3D).visible = false
	if n is WorldEnvironment:
		(n as WorldEnvironment).environment = null
	n.process_mode = Node.PROCESS_MODE_DISABLED


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
	if not _pkg_info.is_empty():
		result["ship_package"] = _pkg_info
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
## behind the window the dark blue placeholder, or since step 3b the Earth (the request's "earth").
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
	if _req.has("earth"):   # step 3b: the Earth is the background; its cubemap pass keeps this grey for reflections
		_earth = ShaderMaterial.new()
		_earth.shader = load("res://lobby/earth_sky.gdshader")
		_earth.set_shader_parameter("neutral_top", Vector3(0.55, 0.56, 0.6))
		_earth.set_shader_parameter("neutral_horizon", Vector3(0.5, 0.5, 0.52))
		_earth.set_shader_parameter("neutral_ground", Vector3(0.35, 0.35, 0.36))
		_earth.set_shader_parameter("neutral_bottom", Vector3(0.25, 0.25, 0.26))
		sky.sky_material = _earth
		env.background_mode = Environment.BG_SKY
		_apply_earth(_req["earth"])
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
	_env = env
	if _req.has("light"):   # step 4: the hall's own light (_apply_light) instead of the review light
		if _earth != null:
			_earth.set_shader_parameter("cubemap_earth", 1.0)   # the probes and reflections show the Earth
		return
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


## One Earth variant into the sky's material: the maps (loaded once, mipmapped), the shared look and its numbers.
func _apply_earth(e: Dictionary) -> void:
	for k: String in e["textures"]:
		var path: String = e["textures"][k]
		if not _textures.has(path) and path.begins_with("res://"):   # step 5b: the package's imported textures
			_textures[path] = load(path) as Texture2D
		if not _textures.has(path):
			var img: Image = Image.load_from_file(path)
			if img == null:
				_fail("cannot load %s" % path)
				return
			if k.begins_with("clouds"):
				img.convert(Image.FORMAT_L8)   # step 5a4: one channel (a quarter of RGBA8's memory)
			img.generate_mipmaps()
			_textures[path] = ImageTexture.create_from_image(img)
		if not k.ends_with("_cap"):   # the caps are the Earth object's alone (step 5a4)
			_earth.set_shader_parameter({"night": "night_tex", "day": "day_tex", "clouds": "cloud_tex"}[k], _textures[path])
	var look: Dictionary = e["look"]
	for k: String in look:
		if k.begins_with("glass_"):
			continue
		var val: Variant = look[k]
		_earth.set_shader_parameter(k, _v(val) if typeof(val) == TYPE_ARRAY else float(val))
	_earth.set_shader_parameter("earth_dir", _v(e["centre"]).normalized())
	_earth.set_shader_parameter("earth_radius_deg", float(e["radius_deg"]))
	_earth.set_shader_parameter("subpoint", Vector2(float(e["subpoint"][0]), float(e["subpoint"][1])))
	_earth.set_shader_parameter("roll_deg", float(e["roll_deg"]))
	_earth.set_shader_parameter("sun_dir", _v(e["sun"]).normalized())
	_earth.set_shader_parameter("sun_energy", float(e["sun_energy"]))
	_earth.set_shader_parameter("stars_density", float(e["stars"]))
	_earth.set_shader_parameter("draw_earth", 0.0 if e.has("object") else 1.0)
	if _earth_obj != null:
		_earth_obj.queue_free()
		_earth_obj = null
	if e.has("object"):
		_earth_object(e)


## Step 4c: the Earth as an object, a shell of `shell` times the planet's radius round its centre (drawn by its back
## faces, earth_object.gdshader) with the sky material's maps and look; the sky keeps the stars and, in its cubemap
## pass, the Earth at infinity for the reflections.
func _earth_object(e: Dictionary) -> void:
	var o: Dictionary = e["object"]
	var mat: ShaderMaterial = ShaderMaterial.new()
	mat.shader = load("res://lobby/earth_object.gdshader")
	mat.render_priority = -1
	for k: String in ["night_tex", "day_tex", "cloud_tex", "subpoint", "roll_deg", "sun_dir", "sun_energy"]:
		mat.set_shader_parameter(k, _earth.get_shader_parameter(k))
	for k: String in e["look"]:
		if not k.begins_with("glass_") and not k.begins_with("stars"):
			var val: Variant = e["look"][k]
			mat.set_shader_parameter(k, _v(val) if typeof(val) == TYPE_ARRAY else float(val))
	mat.set_shader_parameter("centre", _v(o["centre"]))
	mat.set_shader_parameter("radius", float(o["radius_m"]))
	mat.set_shader_parameter("frame_dir", _v(o["frame_dir"]))
	mat.set_shader_parameter("ref_radius_deg", float(e["radius_deg"]))
	if o.get("far", false):   # step 5a7: at infinity, every ray from far_eye
		mat.set_shader_parameter("far_mode", 1.0)
		mat.set_shader_parameter("far_eye", _v(o["far_eye"]))
	if o.has("sun_dir"):   # step 5a7: F36's sun kept just behind its smaller limb
		mat.set_shader_parameter("sun_dir", _v(o["sun_dir"]).normalized())
	if e.has("cap"):   # step 5a4: the regional caps at the sources' full resolution
		var cap: Dictionary = e["cap"]
		mat.set_shader_parameter("night_cap_tex", _textures[e["textures"]["night_cap"]])
		mat.set_shader_parameter("cloud_cap_tex", _textures[e["textures"]["clouds_cap"]])
		mat.set_shader_parameter("cap_box", Vector4(float(cap["lat"][0]), float(cap["lat"][1]), float(cap["lon"][0]), float(cap["lon"][1])))
		mat.set_shader_parameter("cap_fade_deg", float(cap["fade_deg"]))
		mat.set_shader_parameter("cap_on", 1.0)
	var sphere: SphereMesh = SphereMesh.new()
	sphere.radius = float(o["radius_m"]) * float(o["shell"])
	sphere.height = sphere.radius * 2.0
	sphere.radial_segments = 96
	sphere.rings = 48
	_earth_obj = MeshInstance3D.new()
	_earth_obj.name = "EarthObject"
	_earth_obj.mesh = sphere
	_earth_obj.material_override = mat
	_earth_obj.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_earth_obj.extra_cull_margin = 16384.0
	_earth_obj.position = _v(o["centre"])
	root.add_child(_earth_obj)
	_far = maxf(_far, float(o["far_m"]))
	if _camera != null:
		_camera.far = _far
	print("LOBBY earth object %s: radius %.1f m at %.1f m from the spawn, far %.0f m%s" % [o["id"], float(o["radius_m"]), float(o["distance_m"]), _far, " (far mode)" if o.get("far", false) else ""])


## The window's glass (step 3b): window_glass.gdshader with the layout's tint over every lobby_glass surface.
func _glass() -> void:
	var look: Dictionary = _req["earth"]["look"]
	var mat: ShaderMaterial = ShaderMaterial.new()
	mat.shader = load("res://lobby/window_glass.gdshader")
	var c: Array = look["glass_rgb"]
	mat.set_shader_parameter("tint", Color(float(c[0]), float(c[1]), float(c[2])))
	mat.set_shader_parameter("base_alpha", float(look["glass_alpha"]))
	var n_set: int = 0
	for top: Node in _placed.get("window_glass", []):
		var stack: Array = [top]
		while not stack.is_empty():
			var n: Node = stack.pop_back()
			stack.append_array(n.get_children())
			if n is MeshInstance3D and (n as MeshInstance3D).mesh != null:
				var mi: MeshInstance3D = n
				for i: int in mi.mesh.get_surface_count():
					var m: Material = mi.mesh.surface_get_material(i)
					if m != null and m.resource_name == "lobby_glass":
						mi.set_surface_override_material(i, mat)
						mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF   # the Earth's light comes in
						n_set += 1
	if n_set == 0:
		_fail("no lobby_glass surface on window_glass")


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
	var bg: Environment.BGMode = _env.background_mode   # step 4: a plain background (a sky under an ortho camera streaks)
	_env.background_mode = Environment.BG_COLOR
	_env.background_color = Color(0.05, 0.055, 0.065)
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_camera.size = float(top["size_m"])
	_camera.keep_aspect = Camera3D.KEEP_HEIGHT
	var c: Vector3 = Vector3(float(top["centre"][0]), 0, float(top["centre"][1]))
	_camera.look_at_from_position(c + Vector3(0, 80, 0), c, Vector3(0, 0, -1))  # north (-z) up the picture
	images[top["name"]] = await _shot(top["name"], top["title"], shots)
	_env.background_mode = bg
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
	var gpu: Array = []
	for i: int in 30:
		await process_frame
		if i >= 14:
			gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(root.get_viewport_rid()))
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	_save(image, _out.path_join("%s.png" % name))
	shots[name] = {"draw_calls": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		"primitives": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
		"gpu_ms": _median(gpu)}
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


func _median(a: Array) -> float:
	if a.is_empty():
		return 0.0
	var b: Array = a.duplicate()
	b.sort()
	return float(b[b.size() / 2])


## Step 4: one light mood (docs/lobby.md "Step 4"): the environment's exposure, ambient, glow and SSAO; a shadowed spot
## under each pendant's lens (its height read from the vault's lens mesh), an omni before each pilaster strip, a red
## omni before each door lamp, the corridor's omnis, the Earth's cold shadowed directional and E2's warmer hint, the
## reflection probes; the lenses lit, the strips', ring's and lamps' glTF emission scaled. Rebuilt per mood.
func _apply_light(l: Dictionary) -> void:
	if _rig != null:
		_rig.free()
	_rig = Node3D.new()
	_rig.name = "light_rig"
	root.add_child(_rig)
	_env.tonemap_mode = Environment.TONE_MAPPER_AGX
	_env.tonemap_exposure = float(l["exposure"])
	_env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	_env.ambient_light_color = _c(l["ambient_rgb"])
	_env.ambient_light_energy = float(l["ambient_energy"])
	_env.glow_enabled = true
	_env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SCREEN
	_env.glow_intensity = float(l["glow_intensity"])
	_env.glow_bloom = float(l["glow_bloom"])
	_env.glow_hdr_threshold = float(l["glow_threshold"])
	_env.glow_hdr_scale = float(l["glow_hdr_scale"])
	_env.glow_hdr_luminance_cap = float(l["glow_cap"])
	_env.ssao_intensity = float(l["ssao_intensity"])
	var vp: Viewport = root
	vp.positional_shadow_atlas_size = 4096
	for q: int in 4:
		vp.set_positional_shadow_atlas_quadrant_subdiv(q, Viewport.SHADOW_ATLAS_QUADRANT_SUBDIV_4)
	var lens_y: Dictionary = _lens_bottoms(l["pendants"])
	var warm: Color = _c(l["pendant_rgb"])
	var hall_lights: Dictionary = {"pendant": [], "fill": [], "earth": [], "probe": []}   # step 5a2: _ship_light's
	for p: Array in l["pendants"]:
		var key: String = "%s,%s" % [p[0], p[1]]
		if not lens_y.has(key):
			_fail("no pendant lens at %s" % key)
			return
		var spot: SpotLight3D = SpotLight3D.new()
		spot.light_color = warm
		spot.light_energy = float(l["pendant_energy"])
		spot.spot_range = float(l["pendant_range"])
		spot.spot_angle = float(l["pendant_angle"])
		spot.spot_angle_attenuation = 1.4
		spot.spot_attenuation = 1.0
		spot.shadow_enabled = true
		spot.shadow_blur = 1.5
		spot.shadow_bias = 0.04
		spot.light_specular = float(l["pendant_specular"])   # step 4b: the ship's silver top's hot spots softer
		_rig.add_child(spot)
		spot.position = Vector3(float(p[0]), float(lens_y[key]) - 0.03, float(p[1]))
		spot.rotation_degrees = Vector3(-90, 0, 0)   # -z (the spot's axis) straight down
		hall_lights["pendant"].append(spot)
		if float(l["fill_energy"]) > 0.0:   # step 4b: the shade's wide warm spill up onto the vault and ribs (no shadow)
			var up: SpotLight3D = SpotLight3D.new()
			up.light_color = _c(l["fill_rgb"])
			up.light_energy = float(l["fill_energy"])
			up.spot_range = float(l["fill_range"])
			up.spot_angle = float(l["fill_angle"])
			up.spot_angle_attenuation = 0.8
			up.spot_attenuation = 0.8
			up.light_specular = 0.2
			up.shadow_enabled = false
			_rig.add_child(up)
			up.position = Vector3(float(p[0]), float(lens_y[key]) + 0.6, float(p[1]))
			up.rotation_degrees = Vector3(90, 0, 0)   # straight up
			hall_lights["fill"].append(up)
	for at: Array in l["strips"]:
		var o: OmniLight3D = _omni(_v(at), _c(l["strip_rgb"]), float(l["strip_energy"]), float(l["strip_range"]))
		o.light_specular = float(l["strip_specular"])   # step 4b: longer, softer streaks on the polished floor
		o.light_size = float(l["strip_size"])
	for at: Array in l["doors"]:
		_omni(_v(at), _c(l["door_rgb"]), float(l["door_energy"]), float(l["door_range"]))
	for at: Array in l["corridor"]:
		_omni(_v(at), _c(l["corridor_rgb"]), float(l["corridor_energy"]), float(l["corridor_range"]))
	for k: String in ["earth", "dawn"]:
		var sun: DirectionalLight3D = DirectionalLight3D.new()
		sun.light_color = _c(l[k + "_rgb"])
		sun.light_energy = float(l[k + "_energy"])
		sun.shadow_enabled = k == "earth"
		sun.directional_shadow_max_distance = 80.0
		if k == "earth":   # step 4b: the ship's shadow on the north wall and doors soft and lighter
			sun.shadow_blur = float(l["earth_soft"])   # a PCF blur: the angular size's PCSS cost ~1.4 ms (grid 4b)
			sun.shadow_opacity = float(l["earth_shadow"])
			sun.light_specular = float(l.get("earth_specular", 0.5))   # its glare on the polished floor's seams
		_rig.add_child(sun)
		var d: Vector3 = _v(l[k + "_dir"]).normalized()
		sun.look_at_from_position(Vector3.ZERO, -d, Vector3.UP)   # the light travels away from the Earth
		if k == "earth":
			hall_lights["earth"].append(sun)
	if float(l["window_energy"]) > 0.0:   # step 4b: the Earth's cold spill just inside the glass, north and down
		for at: Array in l["window"]:
			var cold: SpotLight3D = SpotLight3D.new()
			cold.light_color = _c(l["window_rgb"])
			cold.light_energy = float(l["window_energy"])
			cold.spot_range = float(l["window_range"])
			cold.spot_angle = 35.0
			cold.spot_angle_attenuation = 0.8
			cold.shadow_enabled = false
			_rig.add_child(cold)
			cold.position = _v(at)
			cold.rotation_degrees = Vector3(-float(l["window_tilt"]), 0, 0)
			cold.light_specular = float(l.get("window_specular", 0.5))   # step 5a3: its white streaks on the floor
	if l.has("wash"):   # step 5a3: a darker, warmer wash on the north wall behind the ship (a negative spot, not on it)
		var w: Dictionary = l["wash"]
		var wash: SpotLight3D = SpotLight3D.new()
		wash.name = "north_wash"
		wash.light_negative = true
		wash.light_color = _c(w["rgb"])
		wash.light_energy = float(w["energy"])
		wash.light_specular = 0.0
		wash.spot_range = float(w["range"])
		wash.spot_angle = float(w["angle"])
		wash.spot_angle_attenuation = 1.0
		wash.spot_attenuation = 0.0   # no 1/d falloff: the energy is what it takes off the wall
		wash.shadow_enabled = false
		wash.light_cull_mask = ALL_LAYERS & ~SHIP_LAYER
		_rig.add_child(wash)
		wash.position = _v(w["at"])   # looking north (-z)
	_fixtures(float(l["fixtures_below"]))
	for pr: Array in l["probes"]:
		var probe: ReflectionProbe = ReflectionProbe.new()
		probe.name = "probe_" + String(pr[0])
		probe.size = _v(pr[2])
		probe.box_projection = true
		probe.interior = bool(pr[3])
		probe.enable_shadows = true
		probe.max_distance = 80.0
		probe.intensity = float(l["probe_intensity"])
		probe.update_mode = ReflectionProbe.UPDATE_ONCE
		probe.ambient_mode = ReflectionProbe.AMBIENT_COLOR   # inside a probe its own (dark) capture would replace the ambient
		probe.ambient_color = _c(l["ambient_rgb"])
		probe.ambient_color_energy = float(l["ambient_energy"])
		_rig.add_child(probe)
		probe.position = _v(pr[1])
		hall_lights["probe"].append(probe)
	if l.has("ship") and _placed.has("ship_pkg"):
		_ship_light(l["ship"], l, hall_lights)
	# step 5a: the ship package's own lamps (its ship.tscn's Light3D nodes left after the freed ones) times ship_lights
	for top: Node in _placed.get("ship_pkg", []):
		for n: Node in top.find_children("*", "Light3D", true, false):
			var lt: Light3D = n as Light3D
			if lt.has_meta("lobby_dropped"):
				continue
			if not lt.has_meta("lobby_e0"):
				lt.set_meta("lobby_e0", lt.light_energy)
			lt.light_energy = float(lt.get_meta("lobby_e0")) * float(l["ship_lights"])
			lt.visible = lt.light_energy > 0.0
	_emit(l)


## Step 5a3: the vault's meshes hanging below `below` m (the pendants' shades, lenses, cords and copper rims; the
## vault's meshes are split by material) cast no shadow. The Earth's light, 2 deg up from the south, laid each column
## of three lamps (x -10, 0, 10) onto the north wall's upper panels, stacked into three soft "trees" (c_back); their own
## spots hang under the lenses and the fills are unshadowed, so no other shadow is lost. None found fails the run.
func _fixtures(below: float) -> void:
	var n: int = 0
	for top: Node in _placed.get("vault", []):
		for c: Node in top.find_children("*", "MeshInstance3D", true, false):
			var mi: MeshInstance3D = c as MeshInstance3D
			if mi.mesh != null and (mi.global_transform * mi.get_aabb()).position.y < below:
				mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
				n += 1
	if n == 0:
		_fail("no hanging lamp meshes in the vault below %.1f m" % below)


## Step 5a2: the package ship's own light set (docs/lobby.md "Step 5a2"), by cull masks on its render layer: the hall's
## pendants (with their fill) and the Earth's light skip it below k 1, still casting its shadow, and unshadowed copies
## at k light it; its own probe (the hall captured without it) instead of the hall's; a cool key and a rim on it alone.
func _ship_light(s: Dictionary, l: Dictionary, hall_lights: Dictionary) -> void:
	var not_ship: int = ALL_LAYERS & ~SHIP_LAYER
	for k: String in ["pendant", "earth"]:
		var share: float = float(s[k + "_k"])
		if share >= 1.0:
			continue
		for lt: Light3D in hall_lights[k] + (hall_lights["fill"] if k == "pendant" else []):
			lt.light_cull_mask = not_ship
			lt.shadow_caster_mask = ALL_LAYERS
		if share <= 0.0:
			continue
		for lt: Light3D in hall_lights[k]:
			var copy: Light3D = lt.duplicate() as Light3D
			copy.light_energy = lt.light_energy * share
			copy.shadow_enabled = false
			copy.light_cull_mask = SHIP_LAYER
			if k == "pendant":
				copy.light_specular = float(s["pendant_specular"])
			_rig.add_child(copy)
			copy.global_transform = lt.global_transform
	if bool(s["own_probe"]):
		for pr: ReflectionProbe in hall_lights["probe"]:
			pr.reflection_mask = not_ship
		var probe: ReflectionProbe = ReflectionProbe.new()
		probe.name = "probe_ship"
		probe.size = _v(s["probe"][1])
		probe.box_projection = true
		probe.enable_shadows = true
		probe.max_distance = 80.0
		probe.cull_mask = not_ship
		probe.reflection_mask = SHIP_LAYER
		probe.intensity = float(s["probe_intensity"])
		probe.update_mode = ReflectionProbe.UPDATE_ONCE
		probe.ambient_mode = ReflectionProbe.AMBIENT_COLOR
		probe.ambient_color = _c(s["ambient_rgb"])
		probe.ambient_color_energy = float(s["ambient_energy"])
		_rig.add_child(probe)
		probe.position = _v(s["probe"][0])
	for k: String in ["key", "rim", "back", "bounce"]:   # step 5a3: a back light (the outline) and a warm bounce
		if float(s[k + "_energy"]) <= 0.0:
			continue
		var sun: DirectionalLight3D = DirectionalLight3D.new()
		sun.name = "ship_" + k
		sun.light_color = _c(s[k + "_rgb"])
		sun.light_energy = float(s[k + "_energy"])
		sun.shadow_enabled = false
		sun.light_cull_mask = SHIP_LAYER
		_rig.add_child(sun)
		sun.look_at_from_position(Vector3.ZERO, -_v(s[k + "_dir"]).normalized(), Vector3.UP)
	print("LOBBY ship light %s: pendants x%s, Earth x%s, own probe %s, key %s, rim %s, back %s, bounce %s" % [s["id"],
		s["pendant_k"], s["earth_k"], s["own_probe"], s["key_energy"], s["rim_energy"], s["back_energy"],
		s["bounce_energy"]])


func _omni(at: Vector3, c: Color, energy: float, rng: float) -> OmniLight3D:
	var o: OmniLight3D = OmniLight3D.new()
	o.light_color = c
	o.light_energy = energy
	o.omni_range = rng
	o.omni_attenuation = 1.2
	o.shadow_enabled = false
	_rig.add_child(o)
	o.position = at
	return o


## Each pendant's lens bottom (the lowest lobby_lens vertex within 0.2 m of its x, z), keyed "x,z".
func _lens_bottoms(pendants: Array) -> Dictionary:
	var out: Dictionary = {}
	for top: Node in _placed.get("vault", []):
		var stack: Array = [top]
		while not stack.is_empty():
			var n: Node = stack.pop_back()
			stack.append_array(n.get_children())
			if not n is MeshInstance3D or (n as MeshInstance3D).mesh == null:
				continue
			var mi: MeshInstance3D = n
			for i: int in mi.mesh.get_surface_count():
				var m: Material = mi.mesh.surface_get_material(i)
				if m == null or m.resource_name != "lobby_lens":
					continue
				var verts: PackedVector3Array = mi.mesh.surface_get_arrays(i)[Mesh.ARRAY_VERTEX]
				for vtx: Vector3 in verts:
					var g: Vector3 = mi.global_transform * vtx
					for p: Array in pendants:
						if Vector2(g.x - float(p[0]), g.z - float(p[1])).length() < 0.2:
							var key: String = "%s,%s" % [p[0], p[1]]
							out[key] = minf(float(out.get(key, 1e9)), g.y)
	return out


## The lenses glow warm (bulb_emit); the strips' and the ring's glTF emission times strip_emit, the lamps' door_emit.
func _emit(l: Dictionary) -> void:
	if _emissive.is_empty():
		for pid: String in _placed:
			for top: Node in _placed[pid]:
				var stack: Array = [top]
				while not stack.is_empty():
					var n: Node = stack.pop_back()
					if n.has_meta("lobby_dropped"):
						continue
					stack.append_array(n.get_children())
					if not n is MeshInstance3D or (n as MeshInstance3D).mesh == null:
						continue
					var mi: MeshInstance3D = n
					for i: int in mi.mesh.get_surface_count():
						var m: Material = mi.get_surface_override_material(i)
						if m == null:
							m = mi.mesh.surface_get_material(i)
						if pid.begins_with("ship_"):   # step 4b: the ship's glow surfaces (art #263's), only scaled here
							if m is BaseMaterial3D and (m as BaseMaterial3D).emission_enabled:
								_emissive.append([mi, i, m, true])
						elif m is BaseMaterial3D and m.resource_name in ["lobby_lens", "lobby_strip", "lobby_ring", "lobby_lamp"]:
							_emissive.append([mi, i, m, false])
	print("LOBBY emissive surfaces %d, the ship's %d (x%s)" % [_emissive.size(), _emissive.filter(func(e: Array) -> bool: return bool(e[3])).size(), l["ship_emit"]])
	var made: Dictionary = {}
	for e: Array in _emissive:
		var orig: BaseMaterial3D = e[2]
		var mname: String = orig.resource_name
		if bool(e[3]):   # a ship surface: its own material times ship_emit, keyed by the material itself
			mname = "ship:%d" % orig.get_instance_id()
		if not made.has(mname):
			var mat: BaseMaterial3D = orig.duplicate()
			if bool(e[3]):
				mat.emission_energy_multiplier = orig.emission_energy_multiplier * float(l["ship_emit"])
			elif mname == "lobby_lens":
				mat.emission_enabled = true
				mat.emission = _c(l["pendant_rgb"])
				mat.emission_energy_multiplier = float(l["bulb_emit"])
			else:
				var k: float = float(l["door_emit"]) if mname == "lobby_lamp" else float(l["strip_emit"])
				mat.emission_energy_multiplier = orig.emission_energy_multiplier * k
			made[mname] = mat
		(e[0] as MeshInstance3D).set_surface_override_material(int(e[1]), made[mname])


## Step 4: the eye-height walk-through: the request's keys [eye, look, seconds from the previous] through a
## Catmull-Rom path, every frame saved for the encoder; the GPU time's median for the record.
func _video() -> void:
	_setup_scene()
	_label.visible = false
	var v: Dictionary = _req["video"]
	_camera.fov = float(v["fov"])
	var keys: Array = v["keys"]
	var times: Array = [0.0]
	for i: int in range(1, keys.size()):
		times.append(float(times[-1]) + float(keys[i][2]))
	var fps: float = float(v["fps"])
	var count: int = int(float(times[-1]) * fps) + 1
	var dir: String = _out.path_join("frames")
	DirAccess.make_dir_recursive_absolute(dir)
	_camera.look_at_from_position(_v(keys[0][0]), _v(keys[0][1]), Vector3.UP)
	for i: int in 40:   # the probes, SSAO and glow settle
		await process_frame
	var started: int = Time.get_ticks_msec()
	var gpu: Array = []
	var k: int = 0
	for f: int in count:
		var t: float = minf(f / fps, float(times[-1]))
		while k < keys.size() - 2 and t > float(times[k + 1]):
			k += 1
		var gap: float = float(times[k + 1]) - float(times[k])
		var w: float = (t - float(times[k])) / gap if gap > 0.0 else 1.0
		_camera.look_at_from_position(_cr(keys, k, w, 0), _cr(keys, k, w, 1), Vector3.UP)
		await RenderingServer.frame_post_draw
		gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(root.get_viewport_rid()))
		var image: Image = root.get_texture().get_image()
		image.convert(Image.FORMAT_RGB8)
		_save(image, dir.path_join("%05d.png" % f))
	_write("video.json", {"frames": count, "fps": fps, "seconds": times[-1], "gpu_ms": _median(gpu),
		"render_s": (Time.get_ticks_msec() - started) / 1000.0})
	print("LOBBY video %d frames" % count)
	quit(0)


## A Catmull-Rom point between keys k and k + 1 at w (0..1) of field j (0 the eye, 1 the look), the ends repeated.
func _cr(keys: Array, k: int, w: float, j: int) -> Vector3:
	var n: int = keys.size()
	var p0: Vector3 = _v(keys[maxi(k - 1, 0)][j])
	var p1: Vector3 = _v(keys[k][j])
	var p2: Vector3 = _v(keys[mini(k + 1, n - 1)][j])
	var p3: Vector3 = _v(keys[mini(k + 2, n - 1)][j])
	var w2: float = w * w
	var w3: float = w2 * w
	return 0.5 * ((2.0 * p1) + (p2 - p0) * w + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * w2
		+ (3.0 * p1 - p0 - 3.0 * p2 + p3) * w3)


func _c(a: Variant) -> Color:
	return Color(float(a[0]), float(a[1]), float(a[2]))


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
