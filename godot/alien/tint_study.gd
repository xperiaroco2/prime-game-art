extends SceneTree
## The static premium heads' skin colour study (art #196, 2026-10-23): labelled sheets from a JSON job in an off-screen
## window (the runner's _godot.window(); tools/blender/alien_tint_study.py writes the job and calls it). Each head gets
## tint_study.gdshader (alien_static.gd's apply() with that shader) and its accent mask. Two lights: "studio" (the
## static heads' stage, static_alive.gd's, under AgX 0.65 + saturation 1.35) and "dusk" (an evening forest: a low warm
## key with shadows, a cool blue sky fill, a dim green bounce from below, a dusk sky for the ambient). The job:
##   {"hdri": PATH, "window": [w, h],
##    "heads": {KEY: {"glb": "res://...", "mask": PNG, "detail": PNG, "plain": PNG, "accent": PNG, "base": [r, g, b],
##                    "params": {...}}},
##    "sheets": [{"file": JPG, "cell": [w, h], "width": 1280, "title": "line 1\nline 2",
##                "rows": [[{"head": KEY, "params": {...}, "debug": 0, "light": "studio"|"dusk",
##                           "shot": {"target": [x, y, z] or "box", "target_y": m, "yaw": deg, "pitch": deg,
##                                    "width": m},
##                           "label": "text"} or {"image": PNG, "label": "text"}, ...], ...]}]}
## A cell's parameters are the head's "params" with the cell's on top (sRGB colours as [r, g, b]); its label is drawn
## in the cell's top left corner, the sheet's title in a strip above the rows.
## Args after "--": <job JSON>

const Offscreen = preload("res://lib/offscreen.gd")
const AlienStatic = preload("res://alien/alien_static.gd")
const SHADER: Shader = preload("res://alien/tint_study.gdshader")

var _world: WorldEnvironment
var _envs: Dictionary = {}  # "studio" | "dusk" -> Environment
var _lights: Dictionary = {}  # "studio" | "dusk" -> Array[Light3D]
var _cam: Camera3D
var _label: Label
var _picture: TextureRect
var _heads: Dictionary = {}  # KEY -> {"node": Node3D, "mats": Array[ShaderMaterial], "box": AABB, "params": {}}


func _initialize() -> void:
	var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
	if placed != "":
		printerr(placed)
		quit(2)
		return
	_run.call_deferred()


func _run() -> void:
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	_stage(job["hdri"])
	for key: String in job["heads"]:
		var h: Dictionary = job["heads"][key]
		var scene: PackedScene = load(h["glb"])
		if scene == null:
			printerr("TINT cannot load %s" % h["glb"])
			quit(3)
			return
		var node: Node3D = scene.instantiate()
		root.add_child(node)
		var tex: Dictionary = {}
		for which: String in ["mask", "detail", "plain", "accent"]:
			tex[which] = _texture(h.get(which, ""))
			if tex[which] == null:  # every map is needed: never a white or black default
				printerr("TINT %s: cannot load the %s texture '%s'" % [key, which, h.get(which, "")])
				quit(4)
				return
		var b: Array = h["base"]
		var mats: Array[ShaderMaterial] = AlienStatic.apply(node, tex["mask"], Color(b[0], b[1], b[2]), tex["detail"],
				tex["plain"], SHADER)
		if mats.is_empty():
			printerr("TINT no _static_skin material in %s" % h["glb"])
			quit(4)
			return
		for sm: ShaderMaterial in mats:
			sm.set_shader_parameter("accent_tex", tex["accent"])
		_heads[key] = {"node": node, "mats": mats, "box": _bounds(node), "params": h.get("params", {}), "set": []}
		node.visible = false
	for sheet: Dictionary in job["sheets"]:
		var cell := Vector2i(int(sheet["cell"][0]), int(sheet["cell"][1]))
		var rows: Array[Image] = []
		for row: Array in sheet["rows"]:
			var cells: Array[Image] = []
			for c: Dictionary in row:
				cells.append(await _cell(c, cell))
			rows.append(_strip(cells, cell))
		var img: Image = _stack(rows)
		var w: int = sheet.get("width", 1280)
		if img.get_width() != w:
			img.resize(w, img.get_height() * w / img.get_width(), Image.INTERPOLATE_LANCZOS)
		if sheet.has("title"):
			var t: Image = await _title(sheet["title"], w)
			var full := Image.create(w, t.get_height() + img.get_height(), false, Image.FORMAT_RGB8)
			full.blit_rect(t, Rect2i(Vector2i.ZERO, t.get_size()), Vector2i.ZERO)
			full.blit_rect(img, Rect2i(Vector2i.ZERO, img.get_size()), Vector2i(0, t.get_height()))
			img = full
		img.save_jpg(sheet["file"], 0.9)
		print("TINT wrote %s" % sheet["file"])
	quit(0)


func _texture(path: String) -> Texture2D:
	if path == "" or not FileAccess.file_exists(path):
		return null
	var img: Image = Image.load_from_file(path)
	if img == null or img.is_empty():
		return null
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _grab(ratio: float) -> Image:
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	var k: int = mini(img.get_width(), int(img.get_height() * ratio))
	return img.get_region(Rect2i((img.get_width() - k) / 2, 0, k, img.get_height()))


func _cell(c: Dictionary, cell: Vector2i) -> Image:
	_label.text = c.get("label", "")
	_label.add_theme_font_size_override("font_size", 46)
	_picture.visible = c.has("image")
	for key: String in _heads:
		_heads[key]["node"].visible = c.has("head") and key == c["head"]
	_use_light("studio")
	if c.has("image"):
		_picture.texture = _texture(c["image"])
	else:
		var h: Dictionary = _heads[c["head"]]
		var params: Dictionary = h["params"].duplicate()
		params.merge(c.get("params", {}), true)
		params["debug_mode"] = int(c.get("debug", 0))
		var shader: Shader = h["mats"][0].shader
		for sm: ShaderMaterial in h["mats"]:
			for name: String in h["set"]:
				sm.set_shader_parameter(name, RenderingServer.shader_get_parameter_default(shader.get_rid(), name))
			for name: String in params:
				var v: Variant = params[name]
				if v is Array:
					v = Color(v[0], v[1], v[2])
				elif name == "debug_mode":
					v = int(v)
				sm.set_shader_parameter(name, v)
		h["set"] = params.keys()
		_use_light(c.get("light", "studio"))
		var s: Dictionary = c["shot"]
		var box: AABB = h["box"]
		var target: Vector3 = box.get_center()
		var width: float = s.get("width", box.size.y * 1.08 * float(cell.x) / cell.y)
		if s["target"] is Array:
			target = Vector3(s["target"][0], s["target"][1], s["target"][2])
		elif s.has("target_y"):  # the box's centre at that height
			target.y = s["target_y"]
		var yaw := deg_to_rad(s.get("yaw", 0.0))
		var pitch := deg_to_rad(s.get("pitch", 3.0))
		var dist: float = width * 0.5 / tan(deg_to_rad(_cam.fov * 0.5)) * float(cell.y) / cell.x
		_cam.position = target + Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch)) * dist
		_cam.look_at(target)
	for _i: int in 12:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = _grab(float(cell.x) / cell.y)
	img.resize(cell.x, cell.y, Image.INTERPOLATE_LANCZOS)
	return img


func _title(text: String, w: int) -> Image:
	for key: String in _heads:
		_heads[key]["node"].visible = false
	_picture.visible = false
	_use_light("studio")
	_envs["studio"].background_color = Color(0.13, 0.13, 0.14)
	_label.text = text
	_label.add_theme_font_size_override("font_size", 28)
	for _i: int in 6:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	_envs["studio"].background_color = Color(0.45, 0.46, 0.48)
	img = img.get_region(Rect2i(0, 0, img.get_width(), 132))
	img.resize(w, 132 * w / img.get_width(), Image.INTERPOLATE_LANCZOS)
	return img


func _strip(cells: Array[Image], cell: Vector2i) -> Image:
	var img := Image.create(cells.size() * (cell.x + 4) - 4, cell.y, false, Image.FORMAT_RGB8)
	img.fill(Color(0.2, 0.2, 0.2))
	for i: int in cells.size():
		img.blit_rect(cells[i], Rect2i(Vector2i.ZERO, cell), Vector2i(i * (cell.x + 4), 0))
	return img


func _stack(rows: Array[Image]) -> Image:
	var w: int = 0
	var h: int = 0
	for r: Image in rows:
		w = maxi(w, r.get_width())
		h += r.get_height() + 4
	var img := Image.create(w, h - 4, false, Image.FORMAT_RGB8)
	img.fill(Color(0.2, 0.2, 0.2))
	var y: int = 0
	for r: Image in rows:
		img.blit_rect(r, Rect2i(Vector2i.ZERO, r.get_size()), Vector2i(0, y))
		y += r.get_height() + 4
	return img


func _use_light(which: String) -> void:
	_world.environment = _envs[which]
	for key: String in _lights:
		for l: Light3D in _lights[key]:
			l.visible = key == which


func _stage(hdri: String) -> void:
	root.msaa_3d = Viewport.MSAA_4X
	RenderingServer.sub_surface_scattering_set_quality(RenderingServer.SUB_SURFACE_SCATTERING_QUALITY_MEDIUM)
	# studio: static_alive.gd's stage under its "pick" tone
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.45, 0.46, 0.48)
	var sky := Sky.new()
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	var image: Image = Image.load_from_file(hdri) if FileAccess.file_exists(hdri) else null
	if image != null and not image.is_empty():
		var pano := PanoramaSkyMaterial.new()
		pano.panorama = ImageTexture.create_from_image(image)
		sky.sky_material = pano
	else:
		sky.sky_material = ProceduralSkyMaterial.new()
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_sky_contribution = 0.5
	env.ambient_light_color = Color(1.0, 0.8, 0.62)
	env.ambient_light_energy = 0.12
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.ssao_enabled = true
	env.ssao_radius = 0.6
	env.ssao_intensity = 1.5
	env.ssao_light_affect = 0.2
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 0.65
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.35
	_envs["studio"] = env
	var key := _light(Vector3(-2.0, 3.2, 3.0), 2.0, true, 0.6, Color.WHITE)
	key.light_angular_distance = 1.5
	key.shadow_blur = 1.0
	_lights["studio"] = [key, _light(Vector3(3.0, 1.6, 2.0), 0.12, false, 0.0, Color.WHITE),
			_light(Vector3(0.5, 2.5, -3.0), 0.30, false, 0.3, Color.WHITE)]
	# dusk forest: a dusk sky for the ambient (blue above, a warm horizon, a dark green ground), the sun low and warm
	# from the front left, a blue fill from the sky above, a dim green bounce from the forest floor
	var dusk := Environment.new()
	dusk.background_mode = Environment.BG_COLOR
	dusk.background_color = Color(0.16, 0.19, 0.26)
	var dsky := Sky.new()
	dsky.radiance_size = Sky.RADIANCE_SIZE_256
	var proc := ProceduralSkyMaterial.new()
	proc.sky_top_color = Color(0.22, 0.32, 0.58)
	proc.sky_horizon_color = Color(0.62, 0.50, 0.46)
	proc.ground_horizon_color = Color(0.22, 0.25, 0.16)
	proc.ground_bottom_color = Color(0.07, 0.11, 0.05)
	proc.sun_angle_max = 1.0
	dsky.sky_material = proc
	dusk.sky = dsky
	dusk.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	dusk.ambient_light_sky_contribution = 1.0
	dusk.ambient_light_energy = 0.55
	dusk.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	dusk.ssao_enabled = true
	dusk.ssao_radius = 0.6
	dusk.ssao_intensity = 1.5
	dusk.ssao_light_affect = 0.2
	dusk.tonemap_mode = Environment.TONE_MAPPER_AGX
	dusk.tonemap_exposure = 0.9
	_envs["dusk"] = dusk
	var sun := _light(Vector3(-3.0, 0.45, 2.2), 2.4, true, 0.5, Color(1.0, 0.62, 0.36))
	sun.light_angular_distance = 1.0
	sun.shadow_blur = 1.0
	_lights["dusk"] = [sun, _light(Vector3(1.5, 3.0, 0.5), 0.35, false, 0.2, Color(0.55, 0.66, 1.0)),
			_light(Vector3(0.3, -2.5, 1.5), 0.16, false, 0.0, Color(0.48, 0.66, 0.32))]
	_world = WorldEnvironment.new()
	_world.environment = env
	root.add_child(_world)
	_cam = Camera3D.new()
	_cam.near = 0.02
	_cam.far = 100.0
	root.add_child(_cam)
	_cam.make_current()
	var layer := CanvasLayer.new()
	root.add_child(layer)
	_picture = TextureRect.new()
	_picture.set_anchors_preset(Control.PRESET_FULL_RECT)
	_picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	_picture.visible = false
	layer.add_child(_picture)
	_label = Label.new()
	_label.position = Vector2(16, 10)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 10)
	layer.add_child(_label)


func _light(at: Vector3, energy: float, shadow: bool, specular: float, color: Color) -> DirectionalLight3D:
	var light := DirectionalLight3D.new()
	root.add_child(light)
	light.look_at_from_position(at, Vector3.ZERO)
	light.light_energy = energy
	light.light_specular = specular
	light.light_color = color
	light.shadow_enabled = shadow
	return light


func _bounds(node: Node) -> AABB:
	var box := AABB()
	var first := true
	for m: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		var b: AABB = m.global_transform * m.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box
