extends SceneTree
## The eye pit's proof (art #196, lively v3): before/after close-ups of both eyes of the lively chameleon in an
## off-screen window (run by tools/blender/alien_lively_run.py through the runner's _godot.window()). Columns: before
## (the older build) and after; rows: rest, the gaze far to the head's left, far right, down, up (the lids' limit), then
## the gaze down under a raking light (the old iris place exposed): grey geometry only (debug_mode 2) from +X and from
## -X, and the full material from +X. One 1280 px wide JPG and a JSON of the row labels and eye states beside it.
## Since v4 also the upper lid edge of each eye at 4x the sheet's scale (the window's own pixels, 2x, nearest), rows
## far left, far right and down, columns before | after: <out>_crop_right.jpg (the head's right eye, on the image's
## left) and <out>_crop_left.jpg. Since v5 (AL2) the JSON's away_from_eyes: the whole head before/after at rest from
## four sides, the pixel difference with the eyes left out.
## Args after "--": <before res://GLB> <before sclera PNG> <before lively.json> <after res://GLB> <after sclera PNG>
##   <after lively.json> <mask PNG> <base skin r,g,b> <HDRI> <out JPG>

const Offscreen = preload("res://lib/offscreen.gd")
const AlienStatic = preload("res://alien/alien_static.gd")
const Lively = preload("res://alien/alien_lively.gd")
const BACKGROUND := Color(0.16, 0.16, 0.17)
const CELL := Vector2i(640, 300)
const FPS := 24.0
## the upper lid edges in a sheet cell's pixels (x, y, w, h), per eye; the crops show them 4x (1280 x 720 per eye)
const CROPS := {"right": Rect2i(40, 100, 160, 60), "left": Rect2i(410, 100, 160, 60)}
const CROP_ROWS := [1, 2, 3, 8, 9]
const ROWS := [
	["rest", Vector3(0, 0, 3), ""], ["eyes far to the head's left", Vector3(3.0, 0.0, 2.0), ""],
	["eyes far to the head's right", Vector3(-3.0, 0.0, 2.0), ""], ["eyes down", Vector3(0.0, -2.5, 2.0), ""],
	["eyes up (the lids' limit)", Vector3(0.0, 2.5, 2.0), ""],
	["eyes down, raking light from +X, grey geometry", Vector3(0.0, -2.5, 2.0), "grey+x"],
	["eyes down, raking light from -X, grey geometry", Vector3(0.0, -2.5, 2.0), "grey-x"],
	["eyes down, raking light from +X, full material", Vector3(0.0, -2.5, 2.0), "lit+x"],
	["eyes far to the head's left, studio light, grey with the normal map", Vector3(3.0, 0.0, 2.0), "nm"],
	["eyes far to the head's left, studio light, grey geometry only", Vector3(3.0, 0.0, 2.0), "geo"]]

var _cam: Camera3D
var _studio: Array[DirectionalLight3D] = []
var _rake_pos: DirectionalLight3D
var _rake_neg: DirectionalLight3D
var _env: Environment
var _full: Image  # the last shot at the window's resolution


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
	var crops := {}
	for key: String in CROPS:
		var cr: Rect2i = CROPS[key]
		crops[key] = Image.create(2 * cr.size.x * 4, CROP_ROWS.size() * cr.size.y * 4, false, Image.FORMAT_RGB8)
	for r: int in ROWS.size():
		var row: Array = ROWS[r]
		report["rows"].append(row[0])
		var mode: String = row[2]
		for l: DirectionalLight3D in _studio:
			l.visible = mode in ["", "nm", "geo"]  # AL6: the studio light for the two grey crop rows too
		_rake_pos.visible = mode == "grey+x" or mode == "lit+x"
		_rake_neg.visible = mode == "grey-x"
		var studio: bool = mode in ["", "nm", "geo"]
		_env.ambient_light_energy = 0.12 if studio else 0.02
		_env.ambient_light_sky_contribution = 0.5 if studio else 0.0
		var states := []
		for k: int in 2:
			heads[k].visible = true
			heads[1 - k].visible = false
			for sm: ShaderMaterial in mats[k]:
				sm.set_shader_parameter("debug_mode", 2 if mode.begins_with("grey") or mode == "geo" else (1 if mode == "nm" else 0))
			lives[k].target = mid + (row[1] as Vector3)
			for _i: int in 48:
				lives[k].step(1.0 / FPS)
			states.append({"left": lives[k]._eye["left"], "right": lives[k]._eye["right"]})
			var img: Image = await _shot(mid)
			sheet.blit_rect(img, Rect2i(Vector2i.ZERO, CELL), Vector2i(k * CELL.x, r * (CELL.y + 4)))
			if r in CROP_ROWS:
				for key: String in CROPS:
					var cr: Rect2i = CROPS[key]
					var part: Image = _full.get_region(Rect2i(cr.position * 2, cr.size * 2))
					part.resize(cr.size.x * 4, cr.size.y * 4, Image.INTERPOLATE_NEAREST)
					(crops[key] as Image).blit_rect(part, Rect2i(Vector2i.ZERO, part.get_size()),
						Vector2i(k * cr.size.x * 4, CROP_ROWS.find(r) * cr.size.y * 4))
		report["eyes"].append(states)
	sheet.fill_rect(Rect2i(CELL.x - 2, 0, 4, sheet.get_height()), Color(0.0, 0.0, 0.0))
	sheet.save_jpg(a[9], 0.92)
	for key: String in crops:
		var ci: Image = crops[key]
		ci.fill_rect(Rect2i(ci.get_width() / 2 - 2, 0, 4, ci.get_height()), Color(0.0, 0.0, 0.0))
		for j: int in range(1, CROP_ROWS.size()):
			ci.fill_rect(Rect2i(0, j * ci.get_height() / CROP_ROWS.size() - 2, ci.get_width(), 4), Color(0.0, 0.0, 0.0))
		ci.save_jpg(a[9].get_basename() + "_crop_%s.jpg" % key, 0.95)
	report["crops"] = {"rows": CROP_ROWS.map(func(i: int) -> String: return ROWS[i][0]), "cells": str(CROPS),
		"scale": "4x the sheet (2x the window's pixels, nearest)"}
	report["away_from_eyes"] = await _away_diff(heads, lives, mid)
	print("PIT whole head before/after away from the eyes: %s" % JSON.stringify(report["away_from_eyes"]))
	var f := FileAccess.open(a[9].get_basename() + ".json", FileAccess.WRITE)
	f.store_string(JSON.stringify(report, "  ") + "\n")
	f.close()
	print("PIT wrote %s (%d x %d)" % [a[9], sheet.get_width(), sheet.get_height()])
	quit(0)


## The whole head before | after at rest from the front, left, back and right (AL2: "the look otherwise unchanged"):
## per side the mean absolute difference (0..255) and the share of pixels over 8/255, both away from the eyes (every
## pixel within 2.2 eye radii of a projected eye centre left out), and the pixels compared.
func _away_diff(heads: Array[Node3D], lives: Array, mid: Vector3) -> Dictionary:
	for l: DirectionalLight3D in _studio:
		l.visible = true
	_rake_pos.visible = false
	_rake_neg.visible = false
	_env.ambient_light_energy = 0.12
	_env.ambient_light_sky_contribution = 0.5
	var res := {}
	var at := Vector3(0.0, mid.y - 0.05, 0.0)
	for yaw_deg: float in [0.0, 90.0, 180.0, 270.0]:
		var imgs: Array[Image] = []
		var eyes_px: Array = []
		for k: int in 2:
			heads[k].visible = true
			heads[1 - k].visible = false
			lives[k].target = mid + Vector3(0.0, 0.0, 1000.0)
			for _i: int in 48:
				lives[k].step(1.0 / FPS)
			var yaw := deg_to_rad(yaw_deg)
			var dist: float = 1.5 * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
			_cam.position = at + Vector3(sin(yaw), 0.04, cos(yaw)).normalized() * dist
			_cam.look_at(at)
			for _i: int in 6:
				await process_frame
			await RenderingServer.frame_post_draw
			var img: Image = root.get_texture().get_image()
			img.convert(Image.FORMAT_RGB8)
			imgs.append(img)
			if k == 0:
				var mesh: MeshInstance3D = lives[k].mesh
				for side: String in ["left", "right"]:
					var e: Dictionary = lives[k].eyes[side]
					var c: Vector3 = mesh.global_transform * Lively._v(e["centre"])
					var edge: Vector3 = c + _cam.global_transform.basis.x * float(e["radius"]) * 2.2
					var pc: Vector2 = _cam.unproject_position(c)
					eyes_px.append([pc, pc.distance_to(_cam.unproject_position(edge))])
		var sum := 0.0
		var over := 0
		var n := 0
		for j: int in imgs[0].get_height():
			for i: int in imgs[0].get_width():
				var skip := false
				for ep: Array in eyes_px:
					skip = skip or Vector2(i, j).distance_to(ep[0]) < float(ep[1])
				if skip:
					continue
				var p: Color = imgs[0].get_pixel(i, j)
				var q: Color = imgs[1].get_pixel(i, j)
				sum += (absf(p.r - q.r) + absf(p.g - q.g) + absf(p.b - q.b)) / 3.0
				over += 1 if maxf(absf(p.r - q.r), maxf(absf(p.g - q.g), absf(p.b - q.b))) > 8.0 / 255.0 else 0
				n += 1
		res[str(int(yaw_deg))] = {"mean_abs": snappedf(sum / maxf(n, 1) * 255.0, 0.001),
			"share_over_8": snappedf(float(over) / maxf(n, 1), 0.00001), "pixels": n}
	return res


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
	_full = c.duplicate()
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
