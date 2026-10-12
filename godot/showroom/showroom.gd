extends SceneTree
## The showroom (art #140, docs/godot.md "Showroom and recommended look settings"): one character under up to six look
## variants, rendered by Godot in a real window for `tools/run.py showroom`. Never headless and never minimized
## (Godot does not draw then); the runner opens the window off-screen:
##   godot --path godot --position -30000,-30000 --resolution 640x800 -s res://showroom/showroom.gd
##       -- <res://import/x.glb> <out folder> <showroom_spec.json>
## The spec (tools/runner/commands/_showroom.py) lists the variants; each sets the tonemapper and exposure, the ambient
## source (a flat colour or the studio sky), sky reflections, the key light's specular, SSAO, soft shadows (the key
## light's angular size: PCSS) and subsurface scattering on the materials whose name ends in _clay. Writes face.png
## (the approved sheet's crops, then per variant the face front and three-quarter), body.png (per variant the full
## body) and showroom.json (each variant's GPU time averaged over drawn frames with the window at the timing size).
## The frames stand (godot/frames/frames.gd) stays the measuring stand; its look is the first variant here.
## Prints SHOWROOM saved <path>, or SHOWROOM error <why> and exits 1.

const Character = preload("res://lib/character.gd")
const WATCHDOG_S: float = 600.0
const BACKGROUND: Color = Color(0.80, 0.80, 0.82)
const FLOOR: Color = Color(0.66, 0.66, 0.68)
const INK: Color = Color(0.12, 0.12, 0.14)
const TITLE_H: int = 52
const GAP: int = 4
const MARGIN: float = 1.10
const SSAO_RADIUS: float = 0.6
const SSAO_INTENSITY: float = 1.5
const KEY_ANGULAR_DEG: float = 1.5
const SSS_STRENGTH: float = 0.25
const SSAO_LIGHT_AFFECT: float = 0.2  # a little contact shade on directly lit clay too, as Blender's AO-like look
const CATCH_DIR: Vector3 = Vector3(-0.3, 0.4, 1.0)  # the catch light comes from up-left of the view (camera space)
const CATCH_ENERGY: float = 0.1
const CATCH_SPECULAR: float = 4.0

var _label: Label
var _scene: Node
var _skeleton: Skeleton3D
var _player: AnimationPlayer
var _camera: Camera3D
var _env: Environment
var _key: DirectionalLight3D
var _catch: DirectionalLight3D
var _clay: Array[BaseMaterial3D] = []
var _sky_name: String = ""


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if DisplayServer.get_name() == "headless":
		_fail("running headless; the showroom needs a real window")
		return
	if args.size() < 3:
		_fail("usage: -- <res://import/x.glb> <out folder> <showroom_spec.json>")
		return
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	var spec: Variant = Character.read_json(args[2])
	if not (spec is Dictionary and spec.has("variants")):
		_fail("%s is not a showroom spec (give an absolute path)" % args[2])
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
	var clip: String = spec["clip"]
	if not _player.has_animation(clip):
		_fail("no animation %s" % clip)
		return
	_collect_clay()
	_stage(spec["hdri"])
	Character.pose_at(_player, _skeleton, clip, 0.0)
	await process_frame
	var size: Vector2i = root.get_visible_rect().size
	var fov: float = float(spec["fov_deg"])
	var record: Dictionary = {"character": spec["character"], "clip": clip, "window": [size.x, size.y],
			"godot": Engine.get_version_info()["string"], "sky": _sky_name, "clay_materials": _clay.size(),
			"renderer": "%s %s" % [RenderingServer.get_current_rendering_driver_name(),
					RenderingServer.get_current_rendering_method()],
			"adapter": RenderingServer.get_video_adapter_name(), "variants": [], "timing": []}
	var face_cams: Array[Dictionary] = []
	for yaw: float in spec["face_yaws"]:
		face_cams.append(_fit(float(yaw), 0.0, fov, true, size))
	var body_cam: Dictionary = _fit(float(spec["body_yaw"]), float(spec["body_pitch"]), fov, false, size)
	var face_shots: Array[Image] = []
	var beside: String = spec.get("beside", "")
	if beside != "":
		var approved: Image = Image.load_from_file(beside)
		if approved == null:
			_fail("cannot read %s" % beside)
			return
		for r: Array in spec["beside_rects"]:
			face_shots.append(approved.get_region(Rect2i(int(r[0]), int(r[1]), int(r[2]), int(r[3]))))
	var body_shots: Array[Image] = []
	for v: Dictionary in spec["variants"]:
		_apply(v)
		for i: int in face_cams.size():
			_place(face_cams[i])
			var img: Image = await _shot("%s  %s" % [v["label"], "front" if i == 0 else "3/4"])
			_save(img, "%s/shots/%s_face%d.png" % [out_dir, v["id"], i])
			face_shots.append(img)
		_place(body_cam)
		var body: Image = await _shot(v["label"])
		_save(body, "%s/shots/%s_body.png" % [out_dir, v["id"]])
		body_shots.append(body)
		record["variants"].append(v["id"])
		print("SHOWROOM variant ", v["id"])
	var fc: Vector2i = Vector2i(int(spec["face_cell"][0]), int(spec["face_cell"][1]))
	_save(await _sheet(face_shots, fc, 4, spec["face_title"]), "%s/face.png" % out_dir)
	var bc: Vector2i = Vector2i(int(spec["body_cell"][0]), int(spec["body_cell"][1]))
	_save(await _sheet(body_shots, bc, 3, spec["body_title"]), "%s/body.png" % out_dir)
	# GPU time per variant, the full body framed in a window at the timing size (the label hidden)
	_label.visible = false
	DisplayServer.window_set_size(Vector2i(int(spec["timing_size"][0]), int(spec["timing_size"][1])))
	for i: int in 4:
		await process_frame
	size = root.get_visible_rect().size
	record["timing_window"] = [size.x, size.y]
	_place(_fit(float(spec["body_yaw"]), float(spec["body_pitch"]), fov, false, size))
	var vp: RID = root.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	var settle: int = int(spec["settle_frames"])
	var count: int = int(spec["timing_frames"])
	var variants: Array = spec["variants"]
	for f: int in int(spec["warmup_frames"]):  # the GPU clocks up and every pipeline compiles first
		if f % 20 == 0:
			_apply(variants[(f / 20) % variants.size()])
		await RenderingServer.frame_post_draw
	var gpu_runs: Array = []
	var cpu_runs: Array = []
	for _i: int in variants.size():
		gpu_runs.append([])
		cpu_runs.append([])
	for r: int in int(spec["timing_rounds"]):
		for i: int in variants.size():
			_apply(variants[i])
			var gpu: float = 0.0
			var cpu: float = 0.0
			for f: int in settle + count:
				await RenderingServer.frame_post_draw
				if f >= settle:
					gpu += RenderingServer.viewport_get_measured_render_time_gpu(vp)
					cpu += RenderingServer.viewport_get_measured_render_time_cpu(vp)
			gpu_runs[i].append(gpu / count)
			cpu_runs[i].append(cpu / count)
	for i: int in variants.size():
		var row: Dictionary = (variants[i] as Dictionary).duplicate()
		row["gpu_ms"] = snappedf(_median(gpu_runs[i]), 0.001)
		row["cpu_ms"] = snappedf(_median(cpu_runs[i]), 0.001)
		row["gpu_ms_rounds"] = (gpu_runs[i] as Array).map(func(x: float) -> float: return snappedf(x, 0.001))
		record["timing"].append(row)
		print("SHOWROOM gpu ", row["id"], " ", row["gpu_ms"], " ms")
	var json_path: String = "%s/showroom.json" % out_dir
	if not Character.write_json(json_path, record):
		_fail("cannot write %s" % json_path)
		return
	print("SHOWROOM saved ", json_path)
	quit(0)


## The materials whose name ends in _clay (the plasticine), each once.
func _collect_clay() -> void:
	for mesh: MeshInstance3D in Character.meshes(_scene):
		for s: int in mesh.mesh.get_surface_count():
			var mat: Material = mesh.get_active_material(s)
			if mat is BaseMaterial3D and mat.resource_name.ends_with("_clay") and not _clay.has(mat):
				_clay.append(mat as BaseMaterial3D)


## A studio: the background colour of the frames stand, a sky (the HDRI, else a ProceduralSky) for the ambient light
## and reflections of the variants that use it, a floor, a key, a fill and a rim light, a perspective camera, a label.
func _stage(hdri: String) -> void:
	root.msaa_3d = Viewport.MSAA_4X
	_env = Environment.new()
	_env.background_mode = Environment.BG_COLOR
	_env.background_color = BACKGROUND
	_env.ambient_light_color = Color(1, 1, 1)
	var sky: Sky = Sky.new()
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	var image: Image = Image.load_from_file(hdri) if hdri != "" else null
	if image != null and not image.is_empty():
		var pano: PanoramaSkyMaterial = PanoramaSkyMaterial.new()
		pano.panorama = ImageTexture.create_from_image(image)
		sky.sky_material = pano
		_sky_name = hdri.get_file()
	else:
		sky.sky_material = ProceduralSkyMaterial.new()
		_sky_name = "ProceduralSky"
	_env.sky = sky
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = _env
	root.add_child(world)
	_key = _light(Vector3(-2.0, 3.2, 3.0), 1.05, true)
	_light(Vector3(3.0, 1.6, 2.0), 0.35, false)
	_light(Vector3(0.5, 2.5, -3.0), 0.30, false)
	var floor_mesh: MeshInstance3D = MeshInstance3D.new()
	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(200, 200)
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.albedo_color = FLOOR
	mat.roughness = 1.0
	plane.material = mat
	floor_mesh.mesh = plane
	root.add_child(floor_mesh)
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.far = 100.0
	root.add_child(_camera)
	_camera.make_current()
	# the catch light: rides on the camera; so weak it lights nothing, its specular gives the glossy eyes their glint
	_catch = DirectionalLight3D.new()
	_camera.add_child(_catch)
	_catch.basis = Basis.looking_at(-CATCH_DIR.normalized(), Vector3.UP)
	_catch.light_energy = CATCH_ENERGY
	_catch.light_specular = CATCH_SPECULAR
	_catch.shadow_enabled = false
	var layer: CanvasLayer = CanvasLayer.new()
	root.add_child(layer)
	_label = Label.new()
	_label.add_theme_font_size_override("font_size", 34)
	_label.add_theme_color_override("font_color", INK)
	_label.position = Vector2(14, 8)
	layer.add_child(_label)


func _light(at: Vector3, energy: float, shadow: bool) -> DirectionalLight3D:
	var light: DirectionalLight3D = DirectionalLight3D.new()
	root.add_child(light)
	light.look_at_from_position(at, Vector3(0, 0.9, 0))
	light.light_energy = energy
	light.light_specular = 0.0
	light.shadow_enabled = shadow
	return light


## One variant: every setting it names, whatever the one before it set.
func _apply(v: Dictionary) -> void:
	_env.tonemap_mode = Environment.TONE_MAPPER_AGX if v["tonemap"] == "agx" else Environment.TONE_MAPPER_LINEAR
	_env.tonemap_exposure = float(v["exposure"])
	_env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY if v["ambient"] == "sky" else Environment.AMBIENT_SOURCE_COLOR
	_env.ambient_light_energy = float(v["ambient_energy"])
	_env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY if v["reflections"] else Environment.REFLECTION_SOURCE_DISABLED
	_env.ssao_enabled = bool(v["ssao"])
	_env.ssao_radius = SSAO_RADIUS
	_env.ssao_intensity = SSAO_INTENSITY
	_env.ssao_light_affect = SSAO_LIGHT_AFFECT
	_key.light_energy = float(v["key_energy"])
	_key.light_specular = float(v["key_specular"])
	_catch.visible = bool(v["catch_light"])
	_key.directional_shadow_max_distance = 12.0
	if v["soft_shadows"]:
		_key.light_angular_distance = KEY_ANGULAR_DEG
		_key.shadow_blur = 1.0
		RenderingServer.directional_soft_shadow_filter_set_quality(RenderingServer.SHADOW_QUALITY_SOFT_HIGH)
	else:
		_key.light_angular_distance = 0.0
		_key.shadow_blur = 2.0
		RenderingServer.directional_soft_shadow_filter_set_quality(RenderingServer.SHADOW_QUALITY_SOFT_LOW)
	RenderingServer.sub_surface_scattering_set_quality(RenderingServer.SUB_SURFACE_SCATTERING_QUALITY_MEDIUM
			if v["sss"] else RenderingServer.SUB_SURFACE_SCATTERING_QUALITY_DISABLED)
	for mat: BaseMaterial3D in _clay:
		mat.subsurf_scatter_enabled = bool(v["sss"])
		mat.subsurf_scatter_strength = SSS_STRENGTH
		mat.subsurf_scatter_skin_mode = mat.resource_name.contains("head")


## A perspective camera that fits the skinned vertices (above the Head bone's origin less 4 cm for the face, all of
## them for the body) with the window's aspect and a margin.
func _fit(yaw_deg: float, pitch_deg: float, fov_deg: float, face: bool, size: Vector2i) -> Dictionary:
	var yaw: float = deg_to_rad(yaw_deg)
	var pitch: float = deg_to_rad(pitch_deg)
	var back: Vector3 = Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch))
	var right: Vector3 = Vector3.UP.cross(back).normalized()
	var up: Vector3 = back.cross(right).normalized()
	var floor_y: float = -INF
	var head: int = _skeleton.find_bone("Head")
	if face and head >= 0:
		floor_y = (_skeleton.global_transform * _skeleton.get_bone_global_pose(head)).origin.y - 0.04
	var lo: Vector2 = Vector2(INF, INF)
	var hi: Vector2 = Vector2(-INF, -INF)
	var depth: float = 0.0
	var front: float = -INF
	var count: int = 0
	for mesh: MeshInstance3D in Character.meshes(_scene):
		for p: Vector3 in Character.skinned_points(mesh, 1 if face else 3):
			if p.y < floor_y:
				continue
			var q: Vector2 = Vector2(p.dot(right), p.dot(up))
			lo = lo.min(q)
			hi = hi.max(q)
			depth += p.dot(back)
			front = maxf(front, p.dot(back))
			count += 1
	var mid: Vector2 = (lo + hi) * 0.5
	var extent: Vector2 = hi - lo
	var half: float = maxf(extent.y, extent.x / (float(size.x) / float(size.y))) * MARGIN * 0.5
	if not face:
		half += 50.0 / float(size.y) * half  # room for the label above the head
	var mean: float = depth / maxf(count, 1)
	var centre: Vector3 = right * mid.x + up * mid.y + back * mean
	if not face:
		centre += up * (25.0 / float(size.y) * 2.0 * half)
	var distance: float = half / tan(deg_to_rad(fov_deg) * 0.5) + (front - mean)
	return {"centre": centre, "back": back, "up": up, "distance": distance, "fov": fov_deg}


func _place(cam: Dictionary) -> void:
	_camera.fov = float(cam["fov"])
	var centre: Vector3 = cam["centre"]
	_camera.look_at_from_position(centre + (cam["back"] as Vector3) * float(cam["distance"]), centre, cam["up"])


func _shot(text: String) -> Image:
	_label.text = text
	await process_frame
	await process_frame
	await process_frame
	await RenderingServer.frame_post_draw
	return root.get_texture().get_image()


## The images in a grid of cells under a title band.
func _sheet(shots: Array[Image], cell: Vector2i, cols: int, title: String) -> Image:
	cols = mini(shots.size(), cols)
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
	label.add_theme_font_size_override("font_size", 18)
	label.add_theme_color_override("font_color", INK)
	label.position = Vector2(12, 12)
	sub.add_child(label)
	root.add_child(sub)
	await RenderingServer.frame_post_draw
	var image: Image = sub.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	sub.queue_free()
	return image


func _median(values: Array) -> float:
	var sorted: Array = values.duplicate()
	sorted.sort()
	return float(sorted[sorted.size() / 2])


func _save(image: Image, path: String) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var error: Error = image.save_png(path)
	if error != OK:
		_fail("cannot save %s: %s" % [path, error_string(error)])


func _fail(why: String) -> void:
	print("SHOWROOM error ", why)
	quit(1)
