extends SceneTree
## The yard's chill zone and photo gazebo at dusk for `tools/run.py zones --shoot DIR` (docs/zones.md): instances the
## zone props, the task props and the kit's gazebo and railing from the request (each at its plan point, Godot (x, h, y),
## turned by its yaw about +Y), grey boxes for the dressing placeholders, a review light at every fixture socket, then
## shoots each view, a line-up of the zone props beside a 1.8 m capsule and sheet.png (1280 px wide). Pictures need a
## real window placed off-screen, never headless:
##   godot --path godot --position -30000,-30000 --resolution 1600x900 -s res://house/zones.gd -- <request.json> <out dir>
## request.json: commands/zones.py request(): {"pieces": [{"zone", "id", "src", "pos", "yaw", "scene" | "size",
## "lights", "light"}], "views": [[name, title, eye [x, y, h], look [x, y, h], fov]], "lineup": [{"id", "scene", "min",
## "max"}], "lineup_at": [x, y], "pack": {...}}; optional "lamps": [[x, h, z]] with "lamp": [colour, energy, range]
## (review lights). Without "lineup_at" there is no line-up (the attic's shoot, commands/attic.py). Writes
## <out>/<view>.png, lineup.png, sheet.png and zones.json.

const KitMaterials := preload("res://kit/kit_materials.gd")
const WATCHDOG_S: float = 170.0
const UP := Vector3.UP
const SHEET_W: int = 1280
const GAP: int = 4
const EMISSION_BOOST: float = 3.0  # the bulbs' glow at dusk (review only)

var _req: Dictionary
var _out: String
var _camera: Camera3D
var _label: Label
var _set: Material
var _counts: Dictionary = {"instances": 0, "lights": 0, "proxies": 0}
var _row_length: float = 0.0


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
	for p: Dictionary in _req["pieces"]:
		if p.has("scene"):
			_instance(p)
		else:
			_proxy(p)
	for l: Array in _req.get("lamps", []):
		var c: Array = _req["lamp"][0]
		var lamp: OmniLight3D = OmniLight3D.new()
		lamp.light_color = Color(float(c[0]), float(c[1]), float(c[2]))
		lamp.light_energy = float(_req["lamp"][1])
		lamp.omni_range = float(_req["lamp"][2])
		lamp.position = Vector3(float(l[0]), float(l[1]), float(l[2]))
		root.add_child(lamp)
		_counts["lights"] += 1
	if _req.has("lineup_at"):
		_lineup()
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
	var result: Dictionary = {"shots": {}}
	result.merge(_counts)
	var images: Array[Image] = []
	for v: Array in _req["views"]:
		images.append(await _shot(v[0], v[1], _p(v[2]), _p(v[3]), result, float(v[4])))
	if _req.has("lineup_at"):
		await _lineup_shot(images, result)
	_save(_grid(images), _out.path_join("sheet.png"))
	var f: FileAccess = FileAccess.open(_out.path_join("zones.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(result, " "))
	f.close()
	print("ZONES saved %s" % _out)
	quit(0)


func _lineup_shot(images: Array[Image], result: Dictionary) -> void:
	var fill: DirectionalLight3D = DirectionalLight3D.new()  # review only: the line-up gets a soft key light
	fill.light_color = Color(1.0, 0.92, 0.85)
	fill.light_energy = 0.9
	fill.rotation_degrees = Vector3(-35.0, 30.0, 0.0)
	root.add_child(fill)
	var at: Array = _req["lineup_at"]
	var mid: float = float(at[0]) + _row_length * 0.5
	var back: float = maxf(6.0, _row_length * 0.8 + 1.0)  # the whole row inside a 40-degree (vertical) 16:9 frame
	images.append(await _shot("lineup", "the zone props beside a 1.8 m capsule",
		Vector3(mid, 1.6, float(at[1]) + back), Vector3(mid, 0.9, float(at[1])), result, 40.0))
	fill.queue_free()


# --- the scene -----------------------------------------------------------------------------------------------------
func _environment() -> void:
	var sky_mat: ProceduralSkyMaterial = ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.1, 0.11, 0.3)
	sky_mat.sky_horizon_color = Color(0.9, 0.48, 0.28)
	sky_mat.ground_horizon_color = Color(0.25, 0.18, 0.16)
	sky_mat.ground_bottom_color = Color(0.05, 0.05, 0.07)
	var sky: Sky = Sky.new()
	sky.sky_material = sky_mat
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.6
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 1.4
	env.tonemap_white = 4.0
	env.glow_enabled = true
	env.glow_intensity = 0.6
	env.glow_hdr_threshold = 1.2
	env.ssao_enabled = true
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_light_color = Color(0.3, 0.27, 0.4)
	env.fog_light_energy = 0.8
	env.fog_depth_begin = 40.0
	env.fog_depth_end = 160.0
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var sun: DirectionalLight3D = DirectionalLight3D.new()  # the last of the sky: low, cool, from the west
	sun.light_color = Color(0.6, 0.66, 1.0)
	sun.light_energy = 0.35
	sun.rotation_degrees = Vector3(-18.0, -70.0, 0.0)
	sun.shadow_enabled = true
	root.add_child(sun)
	var ground: MeshInstance3D = MeshInstance3D.new()  # the yard's grass stand-in (#81a builds the ground)
	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(240, 240)
	ground.mesh = plane
	var grass: StandardMaterial3D = StandardMaterial3D.new()
	grass.albedo_color = Color(0.17, 0.22, 0.11)
	grass.roughness = 1.0
	ground.material_override = grass
	ground.position = Vector3(40, -0.01, 30)
	root.add_child(ground)


func _place(node: Node3D, pos: Array, yaw: float) -> void:
	node.position = Vector3(float(pos[0]), float(pos[1]), float(pos[2]))
	node.rotation.y = deg_to_rad(yaw)
	root.add_child(node)


func _instance(p: Dictionary) -> void:
	var scene: PackedScene = load(String(p["scene"])) as PackedScene
	if scene == null:
		_fail("cannot load %s" % p["scene"])
		return
	var node: Node3D = scene.instantiate() as Node3D
	_place(node, p["pos"], float(p["yaw"]))
	_dress(node)
	_counts["instances"] += 1
	for s: Array in p.get("lights", []):
		var c: Array = p["light"][0]
		var lamp: OmniLight3D = OmniLight3D.new()
		lamp.light_color = Color(float(c[0]), float(c[1]), float(c[2]))
		lamp.light_energy = float(p["light"][1])
		lamp.omni_range = float(p["light"][2])
		lamp.position = Vector3(float(s[0]), float(s[1]) - 0.08, float(s[2]))  # just under the bulb
		node.add_child(lamp)
		_counts["lights"] += 1


## The kit's `set` pack on its stand-in surfaces, and the bulbs' emission raised for dusk.
func _dress(node: Node) -> void:
	if _set != null:
		KitMaterials.apply(node, _set)
	for n: Node in node.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n as MeshInstance3D
		for i: int in mi.mesh.get_surface_count():
			var m: Material = mi.mesh.surface_get_material(i)
			if m is StandardMaterial3D and String(m.resource_name).begins_with("kit_emissive"):
				var glow: StandardMaterial3D = (m as StandardMaterial3D).duplicate() as StandardMaterial3D
				glow.emission_enabled = true
				glow.emission_energy_multiplier *= EMISSION_BOOST
				mi.set_surface_override_material(i, glow)


## A grey box of the placeholder's size [w, d, h] with its id: a dressing piece another package (#87) builds.
func _proxy(p: Dictionary) -> void:
	var size: Array = p.get("size", [0.6, 0.6, 0.6])
	var holder: Node3D = Node3D.new()
	_place(holder, p["pos"], float(p["yaw"]))
	var box: MeshInstance3D = MeshInstance3D.new()
	var mesh: BoxMesh = BoxMesh.new()
	mesh.size = Vector3(float(size[0]), float(size[2]), float(size[1]))
	box.mesh = mesh
	var grey: StandardMaterial3D = StandardMaterial3D.new()
	grey.albedo_color = Color(0.55, 0.55, 0.55)
	box.material_override = grey
	box.position = Vector3(0, float(size[2]) * 0.5, 0)
	holder.add_child(box)
	var t: Label3D = Label3D.new()
	t.text = "%s (%s)" % [p["id"], p["src"]]
	t.font_size = 24
	t.pixel_size = 0.01
	t.outline_size = 6
	t.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	t.position = Vector3(0, float(size[2]) + 0.25, 0)
	holder.add_child(t)
	_counts["proxies"] += 1


## The zone props in a row on the line-up's spot, 0.4 m apart, each named, a 1.8 m capsule at the row's start.
func _lineup() -> void:
	var at: Array = _req["lineup_at"]
	var x: float = float(at[0])
	var capsule: MeshInstance3D = MeshInstance3D.new()
	var cm: CapsuleMesh = CapsuleMesh.new()
	cm.radius = 0.25
	cm.height = 1.8
	capsule.mesh = cm
	var skin: StandardMaterial3D = StandardMaterial3D.new()
	skin.albedo_color = Color(0.75, 0.6, 0.5)
	capsule.material_override = skin
	capsule.position = Vector3(x, 0.9, float(at[1]))
	root.add_child(capsule)
	x += 0.25 + 0.4
	for p: Dictionary in _req["lineup"]:
		var lo: Array = p["min"]
		var hi: Array = p["max"]
		var scene: PackedScene = load(String(p["scene"])) as PackedScene
		if scene == null:
			_fail("cannot load %s" % p["scene"])
			return
		var node: Node3D = scene.instantiate() as Node3D
		node.position = Vector3(x - float(lo[0]), -minf(0.0, float(lo[1])), float(at[1]))
		root.add_child(node)
		_dress(node)
		var t: Label3D = Label3D.new()
		t.text = String(p["id"])
		t.font_size = 22
		t.pixel_size = 0.008
		t.outline_size = 6
		t.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		t.position = Vector3(x + (float(hi[0]) - float(lo[0])) * 0.5, 0.15, float(at[1]) + 1.0)
		root.add_child(t)
		x += float(hi[0]) - float(lo[0]) + 0.4
	_row_length = x - 0.4 - float(at[0]) + 0.25


# --- pictures ------------------------------------------------------------------------------------------------------
func _shot(name: String, title: String, from: Vector3, to: Vector3, result: Dictionary, fov: float) -> Image:
	_camera.fov = fov
	_camera.look_at_from_position(from, to, UP)
	_label.text = title
	var image: Image = await _grab()
	result["shots"][name] = {"draw_calls": RenderingServer.get_rendering_info(
		RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME), "primitives": RenderingServer.get_rendering_info(
		RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)}
	_save(image, _out.path_join("%s.png" % name))
	return image


func _grab() -> Image:
	for i: int in 20:
		await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	return image


## The frames two to a row, 1280 px wide.
func _grid(views: Array[Image]) -> Image:
	var cw: int = (SHEET_W - GAP) / 2
	var ch: int = int(cw * views[0].get_height() / float(views[0].get_width()))
	var rows: int = (views.size() + 1) / 2
	var sheet: Image = Image.create_empty(SHEET_W, rows * ch + (rows - 1) * GAP, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.97, 0.97, 0.97))
	for i: int in views.size():
		var img: Image = views[i].duplicate() as Image
		img.resize(cw, ch, Image.INTERPOLATE_LANCZOS)
		sheet.blit_rect(img, Rect2i(Vector2i.ZERO, Vector2i(cw, ch)), Vector2i((i % 2) * (cw + GAP), (i / 2) * (ch + GAP)))
	return sheet


## A plan point [x, y, height] as a Godot position.
func _p(a: Array) -> Vector3:
	return Vector3(float(a[0]), float(a[2]), float(a[1]))


func _save(image: Image, path: String) -> void:
	var error: Error = image.save_png(path)
	if error != OK:
		_fail("cannot save %s: %s" % [path, error_string(error)])


func _fail(why: String) -> void:
	printerr("ZONES error %s" % why)
	quit(1)
