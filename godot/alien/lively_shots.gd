extends SceneTree
## The static head's liveliness proof (art #196, lively) in an off-screen window (the runner's _godot.window(),
## tools/blender/alien_lively_run.py stages the GLBs and calls it): the merged static head beside the lively one at
## rest, the eyes alone toward four targets and a near one, a head turn, the crest mid-swing (sheet.jpg), and a
## video's frames: a target (a small light ball) moving left, right, up, down, near and a fast swipe, the head following
## (video/lively/0000.png...). Writes shots.json (each cell, the crest's largest swing and its frame).
## Args after "--": <lively res://GLB> <static res://GLB> <OUT> <mask PNG> <base skin r,g,b> <HDRI> <lively.json>
##   <sclera PNG> <video seconds (0: none)>

const Offscreen = preload("res://lib/offscreen.gd")
const AlienStatic = preload("res://alien/alien_static.gd")
const Lively = preload("res://alien/alien_lively.gd")
const BACKGROUND: Color = Color(0.45, 0.46, 0.48)
const CELL: Vector2i = Vector2i(320, 400)
const FPS := 24.0

var _env: Environment
var _cam: Camera3D
var _mid: Vector3
var _marker: MeshInstance3D


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
	var out: String = a[2]
	var mask: Texture2D = _texture(a[3])
	var sclera: Texture2D = _texture(a[7])
	var lively: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(a[6]))
	if mask == null or sclera == null or lively == null:
		printerr("LIVELY cannot load the mask, sclera or lively.json")
		quit(3)
		return
	var rgb: PackedStringArray = a[4].split(",")
	var base := Color(float(rgb[0]), float(rgb[1]), float(rgb[2]))
	var heads: Array[Node3D] = []
	for res: String in [a[0], a[1]]:
		var scene: PackedScene = load(res)
		if scene == null:
			printerr("LIVELY cannot load %s" % res)
			quit(3)
			return
		var h: Node3D = scene.instantiate()
		root.add_child(h)
		heads.append(h)
	var mats: Array[ShaderMaterial] = AlienStatic.apply(heads[0], mask, base)
	var still: Array[ShaderMaterial] = AlienStatic.apply(heads[1], mask, base)
	if mats.is_empty() or still.is_empty():
		printerr("LIVELY no _static_skin material")
		quit(4)
		return
	var live = Lively.new(heads[0], mats, lively, sclera)
	_stage(a[5])
	_mid = (Lively._v(lively["eyes"]["left"]["centre"]) + Lively._v(lively["eyes"]["right"]["centre"])) * 0.5
	var report := {"cells": [], "eyes": {}}
	var cells: Array[Image] = []
	var far := _mid + Vector3(0.0, 0.0, 1000.0)
	# row 1: the merged head and the lively one at rest (eyes close up), with the catch light, a head turn
	heads[0].visible = false
	cells.append(await _cell(Vector3(0.0, _mid.y - 0.05, 0.0), 1.3, 0.0))
	report["cells"].append("merged static head at rest (alien_static.gdshader defaults)")
	heads[0].visible = true
	heads[1].visible = false
	live.target = far
	live.head_follow = 0.0
	live.breathing = 0.0
	_settle(live, 24)
	cells.append(await _cell(Vector3(0.0, _mid.y - 0.05, 0.0), 1.3, 0.0))
	report["cells"].append("lively at rest: procedural iris, gaze straight ahead")
	for sm: ShaderMaterial in mats:
		sm.set_shader_parameter("catch_light", 0.85)
	cells.append(await _cell(Vector3(0.0, _mid.y - 0.05, 0.0), 1.3, 0.0))
	report["cells"].append("lively at rest with the catch light 0.85")
	live.head_follow = 1.0
	live.target = _mid + Vector3(2.2, 0.5, 2.0)
	_settle(live, 72)
	cells.append(await _cell(Vector3(0.0, _mid.y - 0.25, 0.0), 1.5, 25.0))
	report["cells"].append("head turned toward a target up at the head's left (yaw clamp 35, pitch 20)")
	live.target = far
	_settle(live, 72)
	# row 2: the eyes alone (the head held), toward the head's left, right, up, down, and a near target
	live.head_follow = 0.0
	var gaze_cells := [["eyes to the head's left", Vector3(1.6, 0.0, 3.0)], ["eyes to the head's right", Vector3(-1.6, 0.0, 3.0)],
		["eyes up", Vector3(0.0, 1.4, 3.0)], ["eyes down", Vector3(0.0, -1.4, 3.0)], ["near target (convergence)", Vector3(0.0, -0.06, 0.42)]]
	var row2: Array[Image] = []
	for g: Array in gaze_cells:
		live.target = _mid + g[1]
		_settle(live, 36)
		row2.append(await _cell(Vector3(0.0, _mid.y - 0.05, 0.0), 1.3, 0.0))
		report["eyes"][g[0]] = {"left": live._eye["left"], "right": live._eye["right"]}
	for sm: ShaderMaterial in mats:
		sm.set_shader_parameter("catch_light", 0.0)
	# the video: the target's path; the crest's largest swing kept for the sheet
	var seconds: float = float(a[8])
	var best := {"deg": -1.0, "frame": -1}
	var swing_img: Image = null
	if seconds > 0.0:
		live.head_follow = 1.0
		live.breathing = 1.0
		live.time = 0.0
		var dir: String = out.path_join("video").path_join("lively")
		DirAccess.make_dir_recursive_absolute(dir)
		_marker.visible = true
		var n: int = int(seconds * FPS)
		for i: int in n:
			var t: float = float(i) / FPS
			live.target = _path(t)
			_marker.position = live.target
			live.step(1.0 / FPS)
			_frame_cam()
			await process_frame
			await RenderingServer.frame_post_draw
			var img: Image = root.get_texture().get_image()
			img.convert(Image.FORMAT_RGB8)
			img.save_png(dir.path_join("%04d.png" % i))
			var sw: float = live.crest_swing()
			if sw > best["deg"]:
				best = {"deg": snappedf(sw, 0.01), "frame": i}
				swing_img = img
		_marker.visible = false
	cells.append(_crop(swing_img) if swing_img != null else Image.create(CELL.x, CELL.y, false, Image.FORMAT_RGB8))
	report["cells"].append("the crest's largest swing in the video (frame %d, %.1f deg)" % [best["frame"], best["deg"]])
	report["crest_swing"] = best
	cells.append_array(row2)
	for g: Array in gaze_cells:
		report["cells"].append(g[0])
	var sheet := Image.create(5 * (CELL.x + 4) - 4, 2 * (CELL.y + 4) - 4, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.2, 0.2, 0.2))
	for i: int in cells.size():
		sheet.blit_rect(cells[i], Rect2i(Vector2i.ZERO, CELL), Vector2i((i % 5) * (CELL.x + 4), (i / 5) * (CELL.y + 4)))
	sheet.resize(1280, sheet.get_height() * 1280 / sheet.get_width(), Image.INTERPOLATE_LANCZOS)
	sheet.save_jpg(out.path_join("sheet.jpg"), 0.9)
	var f := FileAccess.open(out.path_join("shots.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, "  ") + "\n")
	f.close()
	print("LIVELY wrote %s %s" % [out.path_join("sheet.jpg"), JSON.stringify(best)])
	quit(0)


## The target's path (seconds): ahead, the head's left, right, up, down, near, a fast swipe, ahead.
func _path(t: float) -> Vector3:
	var keys := [[0.0, Vector3(0, 0, 3)], [1.5, Vector3(0, 0, 3)], [2.7, Vector3(2.0, 0.15, 2.4)], [4.6, Vector3(2.0, 0.15, 2.4)],
		[6.0, Vector3(-2.0, 0.0, 2.4)], [8.0, Vector3(-2.0, 0.0, 2.4)], [9.2, Vector3(0.3, 1.3, 2.6)], [11.0, Vector3(0.3, 1.3, 2.6)],
		[12.2, Vector3(-0.2, -1.1, 2.6)], [13.6, Vector3(-0.2, -1.1, 2.6)], [14.8, Vector3(0.05, -0.08, 0.45)],
		[16.6, Vector3(0.05, -0.08, 0.45)], [17.1, Vector3(2.4, 0.2, 2.0)], [17.6, Vector3(-2.4, 0.2, 2.0)],
		[18.1, Vector3(2.4, 0.2, 2.0)], [19.0, Vector3(0, 0, 3)], [99.0, Vector3(0, 0, 3)]]
	for k: int in keys.size() - 1:
		if t < keys[k + 1][0]:
			var u: float = smoothstep(keys[k][0], keys[k + 1][0], t)
			return _mid + (keys[k][1] as Vector3).lerp(keys[k + 1][1], u)
	return _mid + Vector3(0, 0, 3)


func _settle(live, steps: int) -> void:
	for _i: int in steps:
		live.step(1.0 / FPS)


func _frame_cam() -> void:
	var c := Vector3(0.0, _mid.y - 0.12, 0.0)
	var yaw := deg_to_rad(30.0)
	var h := 1.95
	var dist: float = h * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
	_cam.position = c + Vector3(sin(yaw), 0.05, cos(yaw)).normalized() * dist
	_cam.look_at(c)


## A sheet cell: the camera at yaw (degrees) toward c framing height h, the window's middle cropped to the cell.
func _cell(c: Vector3, h: float, yaw_deg: float) -> Image:
	var yaw := deg_to_rad(yaw_deg)
	var dist: float = h * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
	_cam.position = c + Vector3(sin(yaw), 0.04, cos(yaw)).normalized() * dist
	_cam.look_at(c)
	for _i: int in 6:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	return _crop(img)


func _crop(img: Image) -> Image:
	var hh: int = img.get_height()
	var w: int = hh * CELL.x / CELL.y
	var c: Image = img.get_region(Rect2i((img.get_width() - w) / 2, 0, w, hh))
	c.resize(CELL.x, CELL.y, Image.INTERPOLATE_LANCZOS)
	return c


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
	_env.ambient_light_sky_contribution = 0.5
	_env.ambient_light_color = Color(1.0, 0.8, 0.62)
	_env.ambient_light_energy = 0.12
	_env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	_env.tonemap_mode = Environment.TONE_MAPPER_AGX  # the light the engineer leans to: AgX 0.65, saturation 1.35
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
	_light(Vector3(3.0, 1.6, 2.0), 0.12, false, 0.0)
	_light(Vector3(0.5, 2.5, -3.0), 0.30, false, 0.3)
	_cam = Camera3D.new()
	_cam.fov = 22.0
	_cam.near = 0.05
	_cam.far = 2000.0
	root.add_child(_cam)
	_cam.make_current()
	_marker = MeshInstance3D.new()
	var ball := SphereMesh.new()
	ball.radius = 0.035
	ball.height = 0.07
	var lit := StandardMaterial3D.new()
	lit.emission_enabled = true
	lit.emission = Color(1.0, 0.85, 0.4)
	lit.emission_energy_multiplier = 3.0
	lit.albedo_color = Color(1.0, 0.85, 0.4)
	ball.material = lit
	_marker.mesh = ball
	_marker.visible = false
	root.add_child(_marker)


func _light(at: Vector3, energy: float, shadow: bool, specular: float) -> DirectionalLight3D:
	var light := DirectionalLight3D.new()
	root.add_child(light)
	light.look_at_from_position(at, Vector3.ZERO)
	light.light_energy = energy
	light.light_specular = specular
	light.shadow_enabled = shadow
	return light
