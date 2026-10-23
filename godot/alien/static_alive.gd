extends SceneTree
## The alien pilot's static heads, round 2 (art #196, static_v2): review sheets from a JSON job in an off-screen window
## (the runner's _godot.window(); tools/blender/alien_static_review.py writes the job and calls it). The stage is
## static_shots.gd's (the showroom's: studio HDRI, key with soft shadows, fill, rim, SSAO, SSS). The job:
##   {"hdri": PATH, "window": [w, h],
##    "heads": {KEY: {"glb": "res://...", "mask": PNG, "detail": PNG or "", "plain": PNG or "", "base": [r, g, b],
##                    "shader": "288" or "", "grey_only": false}},
##    "sheets": [{"file": PNG, "cell": [w, h], "width": 1280,
##                "rows": [[{"head": KEY, "params": {...}, "debug": 0, "tone": "pick"|"showroom",
##                           "shot": {"target": [x, y, z] or "box", "yaw": deg, "pitch": deg, "width": m},
##                           "gpu": false}, ...], ...]}]}
## Each cell shows one head (the others hidden) with its shader parameters reset to its shader's defaults and then set
## from "params". The current shader's defaults are not the #288 material (static_v3 dropped sss_mode_skin): a head with
## "shader": "288" gets alien_static_288.gdshader, the merged #288 shader as it was, and no detail or plain texture
## (static_v5). A head on the current shader needs both textures (a missing one is an error, never a white default),
## unless it is "grey_only": an older build shown in the debug views only (debug 1-3), never in the full material.
## "gpu": the median GPU ms of 60 frames at that cell, written to <sheet>.json.
## Args after "--": <job JSON>

const Offscreen = preload("res://lib/offscreen.gd")
const AlienStatic = preload("res://alien/alien_static.gd")
const BACKGROUND: Color = Color(0.45, 0.46, 0.48)
const TONES: Dictionary = {
	"showroom": {"map": Environment.TONE_MAPPER_AGX, "exposure": 0.9, "sat": 1.0},
	"pick": {"map": Environment.TONE_MAPPER_AGX, "exposure": 0.65, "sat": 1.35},
}

var _env: Environment
var _cam: Camera3D
var _heads: Dictionary = {}  # KEY -> {"node": Node3D, "mats": Array[ShaderMaterial], "box": AABB}


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
			printerr("ALIVE cannot load %s" % h["glb"])
			quit(3)
			return
		var node: Node3D = scene.instantiate()
		root.add_child(node)
		var mask: Texture2D = _texture(h["mask"])
		if mask == null:
			printerr("ALIVE cannot load the mask %s" % h["mask"])
			quit(4)
			return
		var is_288: bool = h.get("shader", "") == "288"
		var detail: Texture2D = null
		var plain: Texture2D = null
		if not is_288:
			for which: String in ["detail", "plain"]:
				var path: String = h.get(which, "")
				if path == "" and h.get("grey_only", false):
					continue
				var tex: Texture2D = _texture(path)
				if tex == null:
					printerr("ALIVE %s: cannot load the %s texture '%s'" % [key, which, path])
					quit(4)
					return
				if which == "detail":
					detail = tex
				else:
					plain = tex
		var b: Array = h["base"]
		var mats: Array[ShaderMaterial] = AlienStatic.apply(node, mask, Color(b[0], b[1], b[2]), detail, plain,
				AlienStatic.SHADER_288 if is_288 else null)
		if mats.is_empty():
			printerr("ALIVE no _static_skin material in %s" % h["glb"])
			quit(4)
			return
		_heads[key] = {"node": node, "mats": mats, "box": _bounds(node), "is_288": is_288, "set": [],
				"grey_only": h.get("grey_only", false)}
		node.visible = false
	for sheet: Dictionary in job["sheets"]:
		var cell := Vector2i(int(sheet["cell"][0]), int(sheet["cell"][1]))
		var rows: Array[Image] = []
		var gpu: Array = []
		for row: Array in sheet["rows"]:
			var cells: Array[Image] = []
			for c: Dictionary in row:
				cells.append(await _cell(c, cell, gpu))
			rows.append(_strip(cells, cell))
		var img: Image = _stack(rows)
		var w: int = sheet.get("width", 1280)
		if img.get_width() > w:
			img.resize(w, img.get_height() * w / img.get_width(), Image.INTERPOLATE_LANCZOS)
		if sheet["file"].ends_with(".jpg"):
			img.save_jpg(sheet["file"], 0.9)
		else:
			img.save_png(sheet["file"])
		if not gpu.is_empty():
			var f := FileAccess.open(sheet["file"].get_basename() + ".json", FileAccess.WRITE)
			f.store_string(JSON.stringify({"gpu_ms": gpu}, "  ") + "\n")
			f.close()
		print("ALIVE wrote %s %s" % [sheet["file"], JSON.stringify(gpu)])
	quit(0)


func _texture(path: String) -> Texture2D:  # null when missing: the caller fails loudly
	if path == "" or not FileAccess.file_exists(path):
		return null
	var img: Image = Image.load_from_file(path)
	if img == null or img.is_empty():
		return null
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _cell(c: Dictionary, cell: Vector2i, gpu: Array) -> Image:
	var h: Dictionary = _heads[c["head"]]
	if h["grey_only"] and int(c.get("debug", 0)) == 0:
		printerr("ALIVE %s is grey_only: shown in a debug view only" % c["head"])
		quit(5)
		return Image.create(cell.x, cell.y, false, Image.FORMAT_RGB8)
	if h["is_288"] and (int(c.get("debug", 0)) != 0 or not c.get("params", {}).is_empty()):
		printerr("ALIVE %s is #288's shader: no debug view, no parameters" % c["head"])
		quit(5)
		return Image.create(cell.x, cell.y, false, Image.FORMAT_RGB8)
	for key: String in _heads:
		_heads[key]["node"].visible = key == c["head"]
	var shader: Shader = h["mats"][0].shader
	var params: Dictionary = c.get("params", {}).duplicate()
	if not h["is_288"]:  # #288's shader has no debug_mode
		params["debug_mode"] = c.get("debug", 0)
	for sm: ShaderMaterial in h["mats"]:
		for name: String in h["set"]:  # static_v5: per head (a shared list missed a head's own last parameters)
			sm.set_shader_parameter(name, RenderingServer.shader_get_parameter_default(shader.get_rid(), name))
		for name: String in params:
			var v: Variant = params[name]
			if v is Array:
				v = Color(v[0], v[1], v[2])
			elif name == "debug_mode":
				v = int(v)
			sm.set_shader_parameter(name, v)
	h["set"] = params.keys()
	var t: Dictionary = TONES[c.get("tone", "pick")]
	_env.tonemap_mode = t["map"]
	_env.tonemap_exposure = t["exposure"]
	_env.adjustment_enabled = t["sat"] != 1.0
	_env.adjustment_saturation = t["sat"]
	var s: Dictionary = c["shot"]
	var box: AABB = h["box"]
	var target: Vector3 = box.get_center()
	var width: float = s.get("width", box.size.y * 1.08 * float(cell.x) / cell.y)
	if s["target"] is Array:
		target = Vector3(s["target"][0], s["target"][1], s["target"][2])
	var yaw := deg_to_rad(s.get("yaw", 0.0))
	var pitch := deg_to_rad(s.get("pitch", 3.0))
	var dist: float = width * 0.5 / tan(deg_to_rad(_cam.fov * 0.5)) * float(cell.y) / cell.x
	var ratio := float(cell.x) / cell.y
	_cam.position = target + Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch)) * dist
	_cam.look_at(target)
	for _i: int in 12:
		await process_frame
	await RenderingServer.frame_post_draw
	if c.get("gpu", false):
		var vp: RID = root.get_viewport_rid()
		RenderingServer.viewport_set_measure_render_time(vp, true)
		var ms: Array = []
		for _i: int in 60:
			await RenderingServer.frame_post_draw
			ms.append(RenderingServer.viewport_get_measured_render_time_gpu(vp))
		ms.sort()
		gpu.append({"head": c["head"], "params": params.keys(), "gpu_ms": snappedf(ms[30], 0.001)})
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	var k: int = mini(img.get_width(), int(img.get_height() * ratio))
	img = img.get_region(Rect2i((img.get_width() - k) / 2, 0, k, img.get_height()))
	img.resize(cell.x, cell.y, Image.INTERPOLATE_LANCZOS)
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
	_cam.near = 0.02
	_cam.far = 100.0
	root.add_child(_cam)
	_cam.make_current()


func _light(at: Vector3, energy: float, shadow: bool, specular: float) -> DirectionalLight3D:
	var light := DirectionalLight3D.new()
	root.add_child(light)
	light.look_at_from_position(at, Vector3.ZERO)
	light.light_energy = energy
	light.light_specular = specular
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
