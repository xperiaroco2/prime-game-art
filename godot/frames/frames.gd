extends SceneTree
## Motion frame sheets of an imported character, rendered by Godot itself in a real window for `tools/run.py frames`
## (docs/godot.md). Never headless and never minimized (Godot does not draw then, so frame_post_draw never fires); the
## runner opens the window off-screen like the game's `tools\run.cmd shot`:
##   godot --path godot --position -30000,-30000 --resolution 480x600 -s res://frames/frames.gd
##       -- <res://import/x.glb> <out folder> <spec.json>
## spec.json: {"character": id, "cell": [w, h], "yaw_deg": 35, "pitch_deg": 8, "fps": 24,
##             "clips": [{"name": animation, "label": short name, "times": [s, ...], "keep": bool, "video": bool}]}
## For each clip, one fixed orthographic three-quarter camera frames the whole character over all its sample times;
## each time is rendered (seek with update, then the next drawn frame), labelled, scaled to the cell and placed in
## sheets/<label>.png under a title band. "keep" also saves frames/<label>/<i>.png at window size, "video" saves every
## frame of one cycle at fps as video/<label>/<i>.png. frames.json records the cameras, the times and every joint's
## world position at each time. Prints FRAMES saved <path>, or FRAMES error <why> and exits 1.

const Character = preload("res://lib/character.gd")
const WATCHDOG_S: float = 600.0
const BACKGROUND: Color = Color(0.80, 0.80, 0.82)
const FLOOR: Color = Color(0.66, 0.66, 0.68)
const INK: Color = Color(0.12, 0.12, 0.14)
const TITLE_H: int = 52
const GAP: int = 4
const MARGIN: float = 1.10

var _label: Label
var _scene: Node
var _skeleton: Skeleton3D
var _player: AnimationPlayer
var _camera: Camera3D


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if DisplayServer.get_name() == "headless":
		_fail("running headless; frames needs a real window")
		return
	if args.size() < 3:
		_fail("usage: -- <res://import/x.glb> <out folder> <spec.json>")
		return
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	print("FRAMES renderer ", RenderingServer.get_current_rendering_driver_name(), " ",
			RenderingServer.get_current_rendering_method())
	var spec: Variant = Character.read_json(args[2])
	if not (spec is Dictionary and spec.has("clips") and spec.has("cell")):
		_fail("%s is not a frames spec (give an absolute path)" % args[2])
		return
	_run(args[0], args[1], spec)


func _run(scene_path: String, out_dir: String, spec: Dictionary) -> void:
	_scene = Character.instance(scene_path, root)
	if _scene == null:
		_fail("cannot load %s" % scene_path)
		return
	var skeletons: Array[Node] = Character.nodes_of(_scene, "Skeleton3D")
	var players: Array[Node] = Character.nodes_of(_scene, "AnimationPlayer")
	if skeletons.size() != 1 or players.size() != 1:
		_fail("%d skeletons and %d animation players, not one each" % [skeletons.size(), players.size()])
		return
	_skeleton = skeletons[0] as Skeleton3D
	_player = players[0] as AnimationPlayer
	_stage()
	await process_frame
	var size: Vector2i = root.get_visible_rect().size
	var cell: Vector2i = Vector2i(int(spec["cell"][0]), int(spec["cell"][1]))
	var record: Dictionary = {"character": spec["character"], "window": [size.x, size.y], "cell": [cell.x, cell.y],
			"godot": Engine.get_version_info()["string"], "clips": {}}
	for clip: Dictionary in spec["clips"]:
		var name: String = clip["name"]
		if not _player.has_animation(name):
			_fail("no animation %s" % name)
			return
		var times: Array = clip["times"]
		var cam: Dictionary = _frame(name, times, float(spec["yaw_deg"]), float(spec["pitch_deg"]), size)
		var entry: Dictionary = {"name": name, "label": clip["label"], "times": times, "camera": cam, "joints": []}
		var shots: Array[Image] = []
		for i: int in times.size():
			var t: float = times[i]
			var image: Image = await _shot(name, t, "%s   f%s   %.2f s" % [clip["label"], _frame_label(t, spec["fps"]), t])
			entry["joints"].append(Character.joints(_skeleton))
			if clip.get("keep", false):
				_save(image, "%s/frames/%s/%02d.png" % [out_dir, clip["label"], i])
			shots.append(image)
		var title: String = "%s   %s   %d frames, %.2f s, %s   (Godot %s)" % [
				spec["character"], clip["label"], times.size(), _player.get_animation(name).length,
				"one loop" if clip.get("loop", false) else "first to last frame",
				Engine.get_version_info()["string"].get_slice("-", 0)]
		var sheet: Image = await _sheet(shots, cell, title)
		_save(sheet, "%s/sheets/%s.png" % [out_dir, clip["label"]])
		if clip.get("video", false):
			var n: int = int(round(_player.get_animation(name).length * float(spec["fps"])))
			for f: int in n:
				var img: Image = await _shot(name, f / float(spec["fps"]), "%s   %s" % [spec["character"], clip["label"]])
				_save(img, "%s/video/%s/%04d.png" % [out_dir, clip["label"], f])
			entry["video_frames"] = n
		record["clips"][clip["label"]] = entry
		print("FRAMES sheet ", clip["label"], " ", times.size(), " frames")
	var json_path: String = "%s/frames.json" % out_dir
	if not Character.write_json(json_path, record):
		_fail("cannot write %s" % json_path)
		return
	print("FRAMES saved ", json_path)
	quit(0)


## Studio-like light on a neutral background: a key light with soft shadows, a fill and a rim light, ambient light, a
## floor at y = 0, and a label in the lower left.
func _stage() -> void:
	var viewport: Viewport = root
	viewport.msaa_3d = Viewport.MSAA_4X
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = BACKGROUND
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(1, 1, 1)
	env.ambient_light_energy = 0.55
	env.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	_light(Vector3(-2.0, 3.2, 3.0), 1.05, true)
	_light(Vector3(3.0, 1.6, 2.0), 0.35, false)
	_light(Vector3(0.5, 2.5, -3.0), 0.30, false)
	var floor_mesh: MeshInstance3D = MeshInstance3D.new()
	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(200, 200)  # its far edge stays out of the frame
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.albedo_color = FLOOR
	mat.roughness = 1.0
	plane.material = mat
	floor_mesh.mesh = plane
	root.add_child(floor_mesh)
	_camera = Camera3D.new()
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_camera.far = 100.0
	root.add_child(_camera)
	_camera.make_current()
	var layer: CanvasLayer = CanvasLayer.new()
	root.add_child(layer)
	_label = Label.new()
	_label.add_theme_font_size_override("font_size", 20)
	_label.add_theme_color_override("font_color", INK)
	_label.position = Vector2(12, 8)
	layer.add_child(_label)


func _light(at: Vector3, energy: float, shadow: bool) -> void:
	var light: DirectionalLight3D = DirectionalLight3D.new()
	root.add_child(light)
	light.look_at_from_position(at, Vector3(0, 0.9, 0))
	light.light_energy = energy
	light.shadow_enabled = shadow
	if shadow:
		light.shadow_blur = 2.0
		light.directional_shadow_max_distance = 12.0


## One fixed camera for the clip: yaw from the front (+Z) toward the character's left (+X), pitch up; its orthographic
## size fits the skinned vertices at every sample time, with a margin.
func _frame(name: String, times: Array, yaw_deg: float, pitch_deg: float, size: Vector2i) -> Dictionary:
	var yaw: float = deg_to_rad(yaw_deg)
	var pitch: float = deg_to_rad(pitch_deg)
	var back: Vector3 = Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch))
	var right: Vector3 = Vector3.UP.cross(back).normalized()
	var up: Vector3 = back.cross(right).normalized()
	var lo: Vector2 = Vector2(INF, INF)
	var hi: Vector2 = Vector2(-INF, -INF)
	var depth: float = 0.0
	var count: int = 0
	for t: float in times:
		Character.pose_at(_player, _skeleton, name, t)
		for mesh: MeshInstance3D in Character.meshes(_scene):
			for p: Vector3 in Character.skinned_points(mesh, 3):
				var q: Vector2 = Vector2(p.dot(right), p.dot(up))
				lo = lo.min(q)
				hi = hi.max(q)
				depth += p.dot(back)
				count += 1
	var mid: Vector2 = (lo + hi) * 0.5
	var extent: Vector2 = hi - lo
	var aspect: float = float(size.x) / float(size.y)
	var ortho: float = maxf(extent.y, extent.x / aspect) * MARGIN
	# room for the label above the head
	ortho += 40.0 / float(size.y) * ortho
	var centre: Vector3 = right * mid.x + up * mid.y + back * (depth / maxf(count, 1))
	centre += up * (20.0 / float(size.y) * ortho)
	_camera.size = ortho
	_camera.look_at_from_position(centre + back * 10.0, centre, up)
	return {"centre": Character.vec(centre), "back": Character.vec(back), "up": Character.vec(up),
			"right": Character.vec(right), "distance": 10.0, "ortho_size": snappedf(ortho, 0.00001),
			"yaw_deg": yaw_deg, "pitch_deg": pitch_deg, "projection": "orthogonal, size = the vertical extent"}


func _shot(name: String, t: float, text: String) -> Image:
	Character.pose_at(_player, _skeleton, name, t)
	_label.text = text
	await process_frame
	await process_frame
	await RenderingServer.frame_post_draw
	return root.get_texture().get_image()


## The frames in a grid of cells (at most 6 per row) under a title band.
func _sheet(shots: Array[Image], cell: Vector2i, title: String) -> Image:
	var cols: int = mini(shots.size(), 6 if shots.size() > 8 else 4)
	var rows: int = int(ceil(shots.size() / float(cols)))
	var width: int = cols * cell.x + (cols + 1) * GAP
	var height: int = TITLE_H + rows * cell.y + (rows + 1) * GAP
	var sheet: Image = Image.create_empty(width, height, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.97, 0.97, 0.97))
	var band: Image = await _title(title, Vector2i(width, TITLE_H))
	sheet.blit_rect(band, Rect2i(Vector2i.ZERO, band.get_size()), Vector2i.ZERO)
	for i: int in shots.size():
		var img: Image = shots[i].duplicate() as Image
		img.convert(Image.FORMAT_RGB8)
		img.resize(cell.x, cell.y, Image.INTERPOLATE_LANCZOS)
		var at: Vector2i = Vector2i(GAP + (i % cols) * (cell.x + GAP), TITLE_H + GAP + (i / cols) * (cell.y + GAP))
		sheet.blit_rect(img, Rect2i(Vector2i.ZERO, cell), at)
	return sheet


## The title rendered by a 2D SubViewport as wide as the sheet.
func _title(text: String, size: Vector2i) -> Image:
	var sub: SubViewport = SubViewport.new()
	sub.size = size
	sub.render_target_update_mode = SubViewport.UPDATE_ONCE
	var bg: ColorRect = ColorRect.new()
	bg.color = Color(0.97, 0.97, 0.97)
	bg.size = Vector2(size)
	sub.add_child(bg)
	var label: Label = Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", 20)
	label.add_theme_color_override("font_color", INK)
	label.position = Vector2(12, 12)
	sub.add_child(label)
	root.add_child(sub)
	await RenderingServer.frame_post_draw
	var image: Image = sub.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	sub.queue_free()
	return image


func _frame_label(t: float, fps: Variant) -> String:
	var f: float = t * float(fps)
	return str(int(round(f))) if absf(f - round(f)) < 0.01 else "%.1f" % f


func _save(image: Image, path: String) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var error: Error = image.save_png(path)
	if error != OK:
		_fail("cannot save %s: %s" % [path, error_string(error)])


func _fail(why: String) -> void:
	print("FRAMES error ", why)
	quit(1)
