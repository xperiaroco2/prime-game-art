extends SceneTree
## The alien pilot's static premium heads (art #196): review shots of one head GLB with the alien_static ShaderMaterial
## under the showroom's look (step 6 of its ladder: the studio HDRI's light and reflections, AgX exposure 0.9, key 2.0
## with soft shadows, fill, rim, SSAO, SSS), in an off-screen window (the runner's _godot.window();
## tools/blender/alien_static_run.py stages the GLB and calls it). Writes into OUT: views.png (front, 3/4, side, back,
## the face close up) under the showroom's AgX, strip.png (the 2D front, Blender's Cycles front, then Godot under each
## of TONES), colour.json (each strip cell's median teal and pale skin, its distance to the 2D's, the pick),
## views_pick.png (the views under the picked tone) and colours.png (the build's teal first, then the curated palette,
## 3/4, under the pick).
## Args after "--": <res:// GLB> <OUT dir> <mask PNG> <base skin sRGB r,g,b> <HDRI> <Blender front PNG> <2D front PNG>

const Offscreen = preload("res://lib/offscreen.gd")
const AlienStatic = preload("res://alien/alien_static.gd")
const BACKGROUND: Color = Color(0.45, 0.46, 0.48)
const CELL: Vector2i = Vector2i(320, 400)

## The tone variants: the showroom's AgX first (step 6 of its ladder), then the pale fault's fixes.
const TONES: Array[Dictionary] = [
	{"name": "showroom_agx_0.9", "map": Environment.TONE_MAPPER_AGX, "exposure": 0.9, "sat": 1.0},
	{"name": "agx_0.65", "map": Environment.TONE_MAPPER_AGX, "exposure": 0.65, "sat": 1.0},
	{"name": "agx_0.65_sat1.35", "map": Environment.TONE_MAPPER_AGX, "exposure": 0.65, "sat": 1.35},
	{"name": "linear_0.6", "map": Environment.TONE_MAPPER_LINEAR, "exposure": 0.6, "sat": 1.0},
]

var _env: Environment
var _cam: Camera3D
var _box: AABB


func _initialize() -> void:
	var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
	if placed != "":
		printerr(placed)
		quit(2)
		return
	_run.call_deferred()


func _run() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var out: String = a[1]
	var scene: PackedScene = load(a[0])
	if scene == null:
		printerr("STATIC cannot load %s" % a[0])
		quit(3)
		return
	var head: Node3D = scene.instantiate()
	root.add_child(head)
	var mask_img: Image = Image.load_from_file(a[2]) if FileAccess.file_exists(a[2]) else null
	if mask_img == null or mask_img.is_empty():
		printerr("STATIC cannot load the mask %s" % a[2])
		quit(4)
		return
	mask_img.generate_mipmaps()
	var rgb: PackedStringArray = a[3].split(",")
	var base := Color(float(rgb[0]), float(rgb[1]), float(rgb[2]))
	var mats: Array[ShaderMaterial] = AlienStatic.apply(head, ImageTexture.create_from_image(mask_img), base)
	if mats.is_empty():
		printerr("STATIC no _static_skin material in %s" % a[0])
		quit(4)
		return
	_stage(a[4])
	_box = _bounds(head)
	var shots: Array = [[0.0, 0.0, 1.0], [35.0, 0.0, 1.0], [90.0, 0.0, 1.0], [180.0, 0.0, 1.0], [0.0, 0.1, 0.5]]
	_tone(TONES[0])
	var views: Array[Image] = []
	for v: Array in shots:
		views.append(await _shot(v[0], v[1], v[2]))
	_save(_sheet(views), out.path_join("views.png"))
	# the tone grid: the 2D front, Blender's Cycles front (Standard view), then the front under each tone variant;
	# the pick is the variant whose teal and pale skin medians sit closest to the 2D's
	var strip: Array[Image] = [_load_cell(a[6]), _load_cell(a[5])]
	var report := {"2d": _skin_median(strip[0]), "blender": _skin_median(strip[1])}
	var best: int = 0
	var best_d: float = INF
	for i: int in TONES.size():
		_tone(TONES[i])
		var img: Image = await _shot(0.0, 0.0, 1.0)
		strip.append(img)
		var m: Dictionary = _skin_median(img)
		var d: float = _distance(m, report["2d"])
		m["distance_to_2d"] = snappedf(d, 0.001)
		report[TONES[i]["name"]] = m
		if d < best_d:
			best_d = d
			best = i
	report["pick"] = TONES[best]["name"]
	_save(_scaled(_sheet(strip), 1280), out.path_join("strip.png"))
	_tone(TONES[best])
	var picked: Array[Image] = []
	for v: Array in shots:
		picked.append(await _shot(v[0], v[1], v[2]))
	_save(_sheet(picked), out.path_join("views_pick.png"))
	var colours: Array[Image] = []
	var palette: Array[Color] = [base]
	palette.append_array(AlienStatic.PALETTE)  # SHADER (apply's default): the guarded colours
	for c: Color in palette:
		AlienStatic.set_skin(mats, c)
		colours.append(await _shot(35.0, 0.0, 1.0))
	AlienStatic.set_skin(mats, base)
	_save(_sheet(colours), out.path_join("colours.png"))
	var f := FileAccess.open(out.path_join("colour.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, "  ") + "
")
	f.close()
	print("STATIC colour pick %s %s" % [report["pick"], JSON.stringify(report)])
	quit(0)


func _stage(hdri: String) -> void:
	root.msaa_3d = Viewport.MSAA_4X
	RenderingServer.sub_surface_scattering_set_quality(RenderingServer.SUB_SURFACE_SCATTERING_QUALITY_MEDIUM)
	_env = Environment.new()
	_env.background_mode = Environment.BG_COLOR
	_env.background_color = BACKGROUND
	var sky := Sky.new()
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	var image: Image = Image.load_from_file(hdri) if FileAccess.file_exists(hdri) else null
	if image != null and not image.is_empty():
		var pano := PanoramaSkyMaterial.new()
		pano.panorama = ImageTexture.create_from_image(image)
		sky.sky_material = pano
	else:
		sky.sky_material = ProceduralSkyMaterial.new()
	_env.sky = sky
	_env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	_env.ambient_light_sky_contribution = 0.5
	_env.ambient_light_color = Color(1.0, 0.8, 0.62)
	_env.ambient_light_energy = 0.12
	_env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	_env.tonemap_mode = Environment.TONE_MAPPER_AGX
	_env.tonemap_exposure = 0.9
	_env.ssao_enabled = true
	_env.ssao_radius = 0.6
	_env.ssao_intensity = 1.5
	_env.ssao_light_affect = 0.2
	var world := WorldEnvironment.new()
	world.environment = _env
	root.add_child(world)
	var key := _light(Vector3(-2.0, 3.2, 3.0), 2.0, true, 0.6)
	key.light_angular_distance = 1.5
	key.shadow_blur = 1.0
	_light(Vector3(3.0, 1.6, 2.0), 0.12, false, 0.0)
	_light(Vector3(0.5, 2.5, -3.0), 0.30, false, 0.3)
	_cam = Camera3D.new()
	_cam.fov = 22.0
	_cam.near = 0.05
	_cam.far = 100.0
	root.add_child(_cam)
	_cam.make_current()


func _tone(t: Dictionary) -> void:
	_env.tonemap_mode = t["map"]
	_env.tonemap_exposure = t["exposure"]
	_env.adjustment_enabled = t["sat"] != 1.0
	_env.adjustment_saturation = t["sat"]


func _distance(m: Dictionary, ref: Dictionary) -> float:
	var d: float = 0.0
	for k: String in ["teal", "pale"]:
		var x: Array = m[k]
		var y: Array = ref[k]
		if x.is_empty() or y.is_empty():
			d += 5.0
			continue
		for i: int in 5:
			d += absf(x[i] - y[i])
	return d


func _scaled(img: Image, width: int) -> Image:
	if img.get_width() > width:
		img.resize(width, img.get_height() * width / img.get_width(), Image.INTERPOLATE_LANCZOS)
	return img


func _light(at: Vector3, energy: float, shadow: bool, specular: float) -> DirectionalLight3D:
	var light := DirectionalLight3D.new()
	root.add_child(light)
	light.look_at_from_position(at, Vector3.ZERO)
	light.light_energy = energy
	light.light_specular = specular
	light.shadow_enabled = shadow
	return light


## yaw: 0 the front (+Z), 90 the head's left; lift: the target's rise in head heights; frac: the framed height share.
func _shot(yaw_deg: float, lift: float, frac: float) -> Image:
	var c: Vector3 = _box.get_center() + Vector3(0.0, lift * _box.size.y, 0.0)
	var h: float = _box.size.y * 1.08 * frac
	var dist: float = h * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
	var yaw := deg_to_rad(yaw_deg)
	_cam.position = c + Vector3(sin(yaw), 0.06, cos(yaw)).normalized() * dist
	_cam.look_at(c)
	for _i: int in 10:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	img.resize(CELL.x, CELL.y, Image.INTERPOLATE_LANCZOS)
	return img


func _load_cell(path: String) -> Image:
	var img: Image = Image.load_from_file(path)
	img.convert(Image.FORMAT_RGB8)
	var k: int = mini(img.get_width(), img.get_height() * CELL.x / CELL.y)
	var hh: int = k * CELL.y / CELL.x
	img = img.get_region(Rect2i((img.get_width() - k) / 2, (img.get_height() - hh) / 2, k, hh))
	img.resize(CELL.x, CELL.y, Image.INTERPOLATE_LANCZOS)
	return img


## The median sRGB of a cell's saturated teal pixels and of its pale (light, low-saturation) pixels.
func _skin_median(img: Image) -> Dictionary:
	var teal: Array = []
	var pale: Array = []
	for y: int in range(0, img.get_height(), 2):
		for x: int in range(0, img.get_width(), 2):
			var c: Color = img.get_pixel(x, y)
			if c.s > 0.3 and c.h > 0.39 and c.h < 0.6 and c.v > 0.25:
				teal.append(c)
			elif c.s < 0.3 and c.s > 0.06 and c.v > 0.7:
				pale.append(c)
	return {"teal": _med(teal), "pale": _med(pale), "teal_n": teal.size(), "pale_n": pale.size()}


func _med(cs: Array) -> Array:
	if cs.is_empty():
		return []
	var out: Array = []
	for ch: int in 5:
		var vals: Array = cs.map(func(c: Color) -> float: return [c.r, c.g, c.b, c.s, c.v][ch])
		vals.sort()
		out.append(snappedf(vals[vals.size() / 2], 0.001))
	return out


func _sheet(cells: Array[Image]) -> Image:
	var sheet := Image.create(cells.size() * (CELL.x + 4) - 4, CELL.y, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.2, 0.2, 0.2))
	for i: int in cells.size():
		sheet.blit_rect(cells[i], Rect2i(Vector2i.ZERO, CELL), Vector2i(i * (CELL.x + 4), 0))
	return sheet


func _save(img: Image, path: String) -> void:
	img.save_png(path)
	print("STATIC wrote %s" % path)


func _bounds(node: Node) -> AABB:
	var box := AABB()
	var first := true
	for m: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		var b: AABB = m.global_transform * m.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box
