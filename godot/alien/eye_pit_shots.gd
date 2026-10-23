extends SceneTree
## The eye pit's proof (art #196, lively v3): before/after close-ups of both eyes of the lively chameleon in an
## off-screen window (run by tools/blender/alien_lively_run.py through the runner's _godot.window()). Columns: before
## (the older build) and after; rows: rest, the gaze far to the head's left, far right, down, up (the lids' limit), then
## the gaze down under a raking light (the old iris place exposed): grey geometry only (debug_mode 2) from +X and from
## -X, and the full material from +X. One 1280 px wide JPG and a JSON of the row labels and eye states beside it.
## Args after "--": <before res://GLB> <before sclera PNG> <before lively.json> <after res://GLB> <after sclera PNG>
##   <after lively.json> <mask PNG> <base skin r,g,b> <HDRI> <out JPG>

const Offscreen = preload("res://lib/offscreen.gd")
const AlienStatic = preload("res://alien/alien_static.gd")
const Lively = preload("res://alien/alien_lively.gd")
const BACKGROUND := Color(0.16, 0.16, 0.17)
const CELL := Vector2i(640, 300)
const FPS := 24.0
const ROWS := [
	["rest", Vector3(0, 0, 3), ""], ["eyes far to the head's left", Vector3(3.0, 0.0, 2.0), ""],
	["eyes far to the head's right", Vector3(-3.0, 0.0, 2.0), ""], ["eyes down", Vector3(0.0, -2.5, 2.0), ""],
	["eyes up (the lids' limit)", Vector3(0.0, 2.5, 2.0), ""],
	["eyes down, raking light from +X, grey geometry", Vector3(0.0, -2.5, 2.0), "grey+x"],
	["eyes down, raking light from -X, grey geometry", Vector3(0.0, -2.5, 2.0), "grey-x"],
	["eyes down, raking light from +X, full material", Vector3(0.0, -2.5, 2.0), "lit+x"]]

var _cam: Camera3D
var _studio: Array[DirectionalLight3D] = []
var _rake_pos: DirectionalLight3D
var _rake_neg: DirectionalLight3D
var _env: Environment


func _initialize() -> void:
	var placed: String = Offscreen.place()  # first (#214)
	if placed != "":
		printerr(placed)
		quit(2)
		return
	_run.call_deferred()


func _texture(path: String) -> Texture2D:
	var img: Image = Image.load_from_file(path) if FileAccess.file_exists(path) else null
	if img == null or img.is_empty():
		return null
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _run() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var mask: Texture2D = _texture(a[6])
	var rgb: PackedStringArray = a[7].split(",")
	var base := Color(float(rgb[0]), float(rgb[1]), float(rgb[2]))
	var heads: Array[Node3D] = []
	var lives := []
	var mats := []
	var mid := Vector3.ZERO
	for k: int in 2:
		var scene: PackedScene = load(a[3 * k])
		var sclera: Texture2D = _texture(a[3 * k + 1])
		var lively = JSON.parse_string(FileAccess.get_file_as_string(a[3 * k + 2]))
		if scene == null or sclera == null or lively == null or mask == null:
			printerr("PIT cannot load the head, sclera, lively.json or mask of column %d" % k)
			quit(3)
			return
		var h: Node3D = scene.instantiate()
		root.add_child(h)
		var m: Array[ShaderMaterial] = AlienStatic.apply(h, mask, base)
		var live = Lively.new(h, m, lively, sclera)
		live.head_follow = 0.0
		live.breathing = 0.0
		heads.append(h)
		lives.append(live)
		mats.append(m)
		mid = (Lively._v(lively["eyes"]["left"]["centre"]) + Lively._v(lively["eyes"]["right"]["centre"])) * 0.5
	_stage(a[8])
	var sheet := Image.create(2 * CELL.x, ROWS.size() * (CELL.y + 4) - 4, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.3, 0.3, 0.3))
	var report := {"columns": ["before: " + a[0], "after: " + a[3]], "rows": [], "eyes": []}
	for r: int in ROWS.size():
		var row: Array = ROWS[r]
		report["rows"].append(row[0])
		var mode: String = row[2]
		for l: DirectionalLight3D in _studio:
			l.visible = mode == ""
		_rake_pos.visible = mode == "grey+x" or mode == "lit+x"
		_rake_neg.visible = mode == "grey-x"
		_env.ambient_light_energy = 0.12 if mode == "" else 0.02
		_env.ambient_light_sky_contribution = 0.5 if mode == "" else 0.0
		var states := []
		for k: int in 2:
			heads[k].visible = true
			heads[1 - k].visible = false
			for sm: ShaderMaterial in mats[k]:
				sm.set_shader_parameter("debug_mode", 2 if mode.begins_with("grey") else 0)
			lives[k].target = mid + (row[1] as Vector3)
			for _i: int in 48:
				lives[k].step(1.0 / FPS)
			states.append({"left": lives[k]._eye["left"], "right": lives[k]._eye["right"]})
			var img: Image = await _shot(mid)
			sheet.blit_rect(img, Rect2i(Vector2i.ZERO, CELL), Vector2i(k * CELL.x, r * (CELL.y + 4)))
		report["eyes"].append(states)
	sheet.fill_rect(Rect2i(CELL.x - 2, 0, 4, sheet.get_height()), Color(0.0, 0.0, 0.0))
	sheet.save_jpg(a[9], 0.92)
	var f := FileAccess.open(a[9].get_basename() + ".json", FileAccess.WRITE)
	f.store_string(JSON.stringify(report, "  ") + "\n")
	f.close()
	print("PIT wrote %s (%d x %d)" % [a[9], sheet.get_width(), sheet.get_height()])
	quit(0)


## Both eyes from the front, 1 m wide (the window's 1280 x 720 middle 1280 x 600, halved).
func _shot(mid: Vector3) -> Image:
	var h := 1.0 * 720.0 / 1280.0
	var dist: float = h * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
	_cam.position = mid + Vector3(0.0, 0.0, dist)
	_cam.look_at(mid)
	for _i: int in 6:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	var c: Image = img.get_region(Rect2i(0, (img.get_height() - 600) / 2, 1280, 600))
	c.resize(CELL.x, CELL.y, Image.INTERPOLATE_LANCZOS)
	return c


## The lively proof's studio (lively_shots.gd: the HDRI, AgX 0.65, saturation 1.35, SSAO, key, fill, rim) and two
## raking lights nearly along the eyes' fronts, off unless a row asks.
func _stage(hdri: String) -> void:
	root.msaa_3d = Viewport.MSAA_4X
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
	_env.ambient_light_color = Color(1.0, 0.8, 0.62)
	_env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	_env.tonemap_mode = Environment.TONE_MAPPER_AGX
	_env.tonemap_exposure = 0.65
	_env.adjustment_enabled = true
	_env.adjustment_saturation = 1.35
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
	_studio = [key, _light(Vector3(3.0, 1.6, 2.0), 0.12, false, 0.0), _light(Vector3(0.5, 2.5, -3.0), 0.30, false, 0.3)]
	_rake_pos = _light(Vector3(3.0, 0.5, 0.45), 3.0, true, 0.8)
	_rake_neg = _light(Vector3(-3.0, 0.5, 0.45), 3.0, true, 0.8)
	_cam = Camera3D.new()
	_cam.fov = 22.0
	_cam.near = 0.05
	_cam.far = 2000.0
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
