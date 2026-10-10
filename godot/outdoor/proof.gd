extends SceneTree
## The House map's plot outside the house in Godot for `tools/run.py outdoor --proof` (art #81, docs/house-outdoor.md):
## the kit v2 fence, gates and outdoor stairs placed by house_outdoor.py, the ground (outdoor.glb: `-col` meshes make
## their colliders), the backdrop's flats (backdrop.glb: unlit, out of GI and shadows), the painted sky as a panorama,
## fog, grey stand-in blocks and prop boxes, warm stand-in lamps; capsules walk it and cameras shoot it.
## Pictures need a real window placed off-screen (the runner passes --position -30000,-30000), never headless:
##   godot --path godot --position -30000,-30000 --resolution 1600x900 -s res://outdoor/proof.gd -- <request.json> <out>
## request.json (tools/runner/house_outdoor_scene.py): {"pieces": {id: res}, "placed": [[id, [x, y, z], yaw]],
##   "ground": res, "backdrop": res, "sky": png, "fog": [begin, end], "pack": {...}, "blocks": [{"id", "at", "size",
##   "color", "yaw"}], "lights": [[x, h, z, energy, range]], "walks": {name: {"r", "points", "must_pass"}},
##   "strips": [[name, title, eye]], "views": [[name, title, from, to, leaves]]}; a walk's or view's "leaves" ("open"
##   or "closed") swings the wicket's and the gates' leaves (kit nodes `*_leaf*`, hinge at their origin) inwards first.
## Writes <out>/<view>.png, <strip>.png, sheet.png (1280 px wide: the strips, then the views in rows of three) and
## proof.json (the walks, and per picture its lit-window pixels: those that change when the flats' textures swap to
## copies with the windows painted dark; every 2nd pixel of every 2nd row); prints PROOF saved <dir>.

const WATCHDOG_S: float = 280.0
const UP := Vector3.UP
const LAMP := Color(1.0, 0.8, 0.6)
const SHEET_W: int = 1280
const GAP: int = 4
const SPEED: float = 3.0
const KitMaterials := preload("res://kit/kit_materials.gd")

var _req: Dictionary
var _set: Material
var _out: String
var _camera: Camera3D
var _label: Label
var _env: Environment
var _leaves: Array = []  # [leaf node, its closed Y rotation in degrees, the open swing in degrees]
var _flats: Array = []  # [material, its texture, the copy with the windows dark]
var _windows: Dictionary = {}  # picture name: its sampled lit-window pixels


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
	var pack: Dictionary = _req.get("pack", {})
	if not pack.is_empty():
		_set = KitMaterials.make(pack["textures"], pack)
	_environment()
	_build()
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.far = 600.0
	root.add_child(_camera)
	_camera.make_current()
	var layer: CanvasLayer = CanvasLayer.new()
	_label = Label.new()
	_label.position = Vector2(16, 10)
	_label.add_theme_font_size_override("font_size", 44)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 8)
	layer.add_child(_label)
	root.add_child(layer)
	for i: int in 3:
		await physics_frame
	var result: Dictionary = {"walks": {}, "leaves": _leaves.size(), "windows": _windows}
	var walks: Dictionary = _req["walks"]
	for name: String in walks:
		var w: Dictionary = walks[name]
		await _set_leaves(w.get("leaves", "open"))
		result["walks"][name] = await _walk(float(w["r"]), w["points"].map(_v), bool(w["must_pass"]))
	var rows: Array = []
	for s: Array in _req["strips"]:
		rows.append(await _strip(s[0], s[1], _v(s[2])))
	var views: Array[Image] = []
	for s: Array in _req["views"]:
		await _set_leaves(s[4] if s.size() > 4 else "open")
		views.append(await _view(s[0], s[1], _v(s[2]), _v(s[3])))
	for i: int in range(0, views.size(), 3):
		rows.append(views.slice(i, i + 3))
	_save(_sheet(rows), _out.path_join("sheet.png"))
	var f: FileAccess = FileAccess.open(_out.path_join("proof.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(result, " "))
	f.close()
	print("PROOF saved %s" % _out)
	quit(0)


# --- the scene -----------------------------------------------------------------------------------------------------
func _environment() -> void:
	var image: Image = Image.load_from_file(_req["sky"])
	if image == null:
		_fail("cannot load the sky %s" % _req["sky"])
		return
	var horizon: Color = Color(0, 0, 0)
	var row: int = image.get_height() / 2 - 2
	for x: int in image.get_width():
		horizon += image.get_pixel(x, row)
	horizon /= float(image.get_width())
	var pano: PanoramaSkyMaterial = PanoramaSkyMaterial.new()
	pano.panorama = ImageTexture.create_from_image(image)
	pano.filter = true
	var sky: Sky = Sky.new()
	sky.sky_material = pano
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 1.0
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 1.5
	env.tonemap_white = 4.0
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.2
	env.glow_enabled = true
	env.glow_hdr_threshold = 0.9
	env.glow_intensity = 0.5
	env.ssao_enabled = true
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_light_color = horizon
	env.fog_light_energy = 0.8
	env.fog_sky_affect = 0.0
	env.fog_depth_begin = float(_req["fog"][0])
	env.fog_depth_end = float(_req["fog"][1])
	_env = env
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.light_color = Color(0.6, 0.62, 0.95)
	sun.light_energy = 0.35
	sun.rotation_degrees = Vector3(-14.0, 200.0, 0.0)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 120.0
	root.add_child(sun)


func _build() -> void:
	var scene: Node3D = Node3D.new()
	root.add_child(scene)
	var ground: Node3D = _load(_req["ground"])
	scene.add_child(ground)
	var backdrop: Node3D = _load(_req["backdrop"])
	for n: Node in backdrop.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n as MeshInstance3D
		mi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		for i: int in mi.mesh.get_surface_count():
			_windows_off(mi.get_active_material(i))
	scene.add_child(backdrop)
	var scenes: Dictionary = {}
	for id: String in _req["pieces"]:
		scenes[id] = load(_req["pieces"][id]) as PackedScene
		if scenes[id] == null:
			_fail("cannot load the piece %s" % id)
			return
	for p: Array in _req["placed"]:
		var n: Node3D = (scenes[p[0]] as PackedScene).instantiate() as Node3D
		if _set != null:
			KitMaterials.apply(n, _set)
		n.position = _v(p[1])
		n.rotation_degrees.y = float(p[2])
		scene.add_child(n)
		_find_leaves(n)
	for b: Dictionary in _req["blocks"]:
		scene.add_child(_block(b))
	for l: Array in _req["lights"]:
		var lamp: OmniLight3D = OmniLight3D.new()
		lamp.light_color = LAMP
		lamp.light_energy = float(l[3])
		lamp.omni_range = float(l[4])
		lamp.position = Vector3(l[0], l[1], l[2])
		scene.add_child(lamp)


## The topmost `*_leaf*` nodes under a piece; a leaf whose mesh lies on its local +X swings +90 degrees (inwards, to
## the piece's local -Z), one on -X swings -90.
func _find_leaves(piece: Node3D) -> void:
	for n: Node in piece.find_children("*leaf*", "Node3D", true, false):
		if "leaf" in String(n.get_parent().name):
			continue
		var centre: float = 0.0
		for m: Node in [n] + n.find_children("*", "MeshInstance3D", true, false):
			if m is MeshInstance3D:
				centre = (m as MeshInstance3D).get_aabb().get_center().x
				break
		_leaves.append([n, (n as Node3D).rotation_degrees.y, 90.0 if centre >= 0.0 else -90.0])


func _set_leaves(state: String) -> void:
	for l: Array in _leaves:
		(l[0] as Node3D).rotation_degrees.y = float(l[1]) + (float(l[2]) if state == "open" else 0.0)
	for i: int in 3:
		await physics_frame


func _load(res: String) -> Node3D:
	var packed: PackedScene = load(res) as PackedScene
	if packed == null:
		_fail("cannot load %s" % res)
		return Node3D.new()
	return packed.instantiate() as Node3D


## A box with a collider: a stand-in block or a prop.
func _block(b: Dictionary) -> StaticBody3D:
	var size: Vector3 = _v(b["size"])
	var body: StaticBody3D = StaticBody3D.new()
	body.name = b["id"]
	body.position = _v(b["at"])
	body.rotation_degrees.y = float(b.get("yaw", 0))
	var mesh: MeshInstance3D = MeshInstance3D.new()
	var bm: BoxMesh = BoxMesh.new()
	bm.size = size
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.albedo_color = Color(b["color"][0], b["color"][1], b["color"][2])
	mat.roughness = 0.9
	bm.material = mat
	mesh.mesh = bm
	body.add_child(mesh)
	var shape: CollisionShape3D = CollisionShape3D.new()
	var bs: BoxShape3D = BoxShape3D.new()
	bs.size = size
	shape.shape = bs
	body.add_child(shape)
	return body


# --- the walk check ------------------------------------------------------------------------------------------------
## A capsule (radius r, 1.8 m) walks the waypoints at 3 m/s with gravity; it passes when it reaches the last within
## 0.3 m (and its height within 0.15 m), or, for a control (`must_pass` false), when it does not.
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
	body.global_position = (points[0] as Vector3) + Vector3(0, 0.05, 0)
	var length: float = 0.0
	for i: int in points.size() - 1:
		length += (points[i + 1] as Vector3).distance_to(points[i])
	var limit: int = int((length / SPEED + 6.0) * Engine.physics_ticks_per_second)
	var reached: int = 0
	var dt: float = 1.0 / Engine.physics_ticks_per_second
	var steps: int = 0
	var min_y: float = 0.0
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
	var end: Vector3 = body.global_position
	var arrived: bool = reached == points.size() - 1 and absf(end.y - (points[-1] as Vector3).y) < 0.15
	body.queue_free()
	return {"radius_m": r, "waypoints": points.size(), "reached": reached + 1, "end": [end.x, end.y, end.z],
		"min_y": min_y, "seconds": steps * dt, "arrived": arrived, "pass": arrived == must_pass}


# --- pictures ------------------------------------------------------------------------------------------------------
## Four 90-degree views round the eye (north, east, south, west) as one row; each also saved full size.
func _strip(name: String, title: String, eye: Vector3) -> Array:
	_camera.keep_aspect = Camera3D.KEEP_WIDTH
	_camera.fov = 90.0
	var tiles: Array = []
	var heads: Array = [["N", Vector3(0, 0, -1)], ["E", Vector3(1, 0, 0)], ["S", Vector3(0, 0, 1)], ["W", Vector3(-1, 0, 0)]]
	for h: Array in heads:
		_camera.look_at_from_position(eye, eye + (h[1] as Vector3), UP)
		_label.text = "360 from the %s: %s" % [title, h[0]]
		var image: Image = await _grab()
		_save(image, _out.path_join("%s_%s.png" % [name, h[0]]))
		_windows["%s_%s" % [name, h[0]]] = await _count_windows(image)
		tiles.append(image)
	_camera.keep_aspect = Camera3D.KEEP_HEIGHT
	return tiles


func _view(name: String, title: String, from: Vector3, to: Vector3) -> Image:
	_camera.fov = 62.0
	_camera.look_at_from_position(from, to, UP)
	_label.text = title
	var image: Image = await _grab()
	_save(image, _out.path_join("%s.png" % name))
	_windows[name] = await _count_windows(image)
	return image


## A flat's material gets a copy of its texture with the lit windows (the only bright texels; the flats are dark)
## painted dark, for _count_windows.
func _windows_off(material: Material) -> void:
	var m: StandardMaterial3D = material as StandardMaterial3D
	if m == null or m.albedo_texture == null:
		return
	var image: Image = m.albedo_texture.get_image()
	if image.is_compressed():
		image.decompress()
	image.clear_mipmaps()
	image.convert(Image.FORMAT_RGBA8)
	var data: PackedByteArray = image.get_data()
	for i: int in range(0, data.size(), 4):
		if data[i] >= 128 and data[i + 3] >= 128:
			data[i] = 24
			data[i + 1] = 30
			data[i + 2] = 36
	image.set_data(image.get_width(), image.get_height(), false, Image.FORMAT_RGBA8, data)
	image.generate_mipmaps()
	_flats.append([m, m.albedo_texture, ImageTexture.create_from_image(image)])


## The lit windows in a picture: the pixels that change by more than 45 (the sum over R, G and B) when the flats show
## their copies with the windows dark; every 2nd pixel of every 2nd row. Fog and light act on both pictures alike.
func _count_windows(shown: Image) -> int:
	for f: Array in _flats:
		(f[0] as StandardMaterial3D).albedo_texture = f[2]
	var off: Image = await _grab()
	for f: Array in _flats:
		(f[0] as StandardMaterial3D).albedo_texture = f[1]
	var a: PackedByteArray = shown.get_data()
	var b: PackedByteArray = off.get_data()
	var w: int = shown.get_width()
	var n: int = 0
	for y: int in range(0, shown.get_height(), 2):
		for x: int in range(0, w, 2):
			var i: int = (y * w + x) * 3
			if absi(a[i] - b[i]) + absi(a[i + 1] - b[i + 1]) + absi(a[i + 2] - b[i + 2]) > 45:
				n += 1
	return n


func _grab() -> Image:
	for i: int in 30:
		await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	return image


## Each row's tiles side by side over SHEET_W, rows stacked.
func _sheet(rows: Array) -> Image:
	var sizes: Array = []
	var height: int = 0
	for row: Array in rows:
		var cw: int = (SHEET_W - (row.size() - 1) * GAP) / maxi(row.size(), 1)
		var ch: int = int(cw * (row[0] as Image).get_height() / float((row[0] as Image).get_width()))
		sizes.append(Vector2i(cw, ch))
		height += ch + GAP
	var sheet: Image = Image.create_empty(SHEET_W, height - GAP, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.97, 0.97, 0.97))
	var y: int = 0
	for r: int in rows.size():
		var s: Vector2i = sizes[r]
		for i: int in (rows[r] as Array).size():
			var img: Image = (rows[r][i] as Image).duplicate() as Image
			img.resize(s.x, s.y, Image.INTERPOLATE_LANCZOS)
			sheet.blit_rect(img, Rect2i(Vector2i.ZERO, img.get_size()), Vector2i(i * (s.x + GAP), y))
		y += s.y + GAP
	return sheet


func _v(a: Variant) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))


func _save(image: Image, path: String) -> void:
	var error: Error = image.save_png(path)
	if error != OK:
		_fail("cannot save %s: %s" % [path, error_string(error)])


func _fail(why: String) -> void:
	printerr("PROOF error %s" % why)
	quit(1)
