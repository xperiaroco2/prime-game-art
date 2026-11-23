extends SceneTree
## The mug lab's review shots (research, the AI-art pipeline trials) in an off-screen window (the runner's
## _godot.window(); tools/blender/mug_lab_run.py stages the GLB and calls it). A lookdev stage in the lobby's colours:
## a dark polished steel bar top, a dark teal-grey wall with light strips behind, a warm key from above, a cold rim
## from the window's side, and studio_sky.gdshader for reflections; AgX, glow, SSR, MSAA 4x.
## Writes into OUT:
## - q34_full.png, q34_half.png, q34_empty.png: the mug on the bar from the concept's 3/4 view (960x960);
## - side_full.png: straight from +z with a long lens (960x960); top_full.png: the head from above (960x960);
## - close_full.png: the rim, foam and facets close up (960x960);
## - fp_full.png, fp_half.png, fp_empty.png: first person, the mug where the right hand holds it (1280x720,
##   the viewmodel's 50 degree lens);
## - drink/NNNN.png: the level going down from full to almost empty in first person (960x540, 24 fps, 3 s);
## - cost.json: the GPU ms of the full first-person view.
## Args after "--": <res:// GLB> <OUT dir> <levels JSON (cm: floor, full, rim, inner_r)> <look|plain> [quick]
## `plain`: the GLB's own materials (an AI mesh as it comes), no fill states (one shot per view).

const Offscreen = preload("res://lib/offscreen.gd")
const MugLook = preload("res://mug_lab/mug_look.gd")
const SQUARE := Vector2i(960, 960)
const WIDE := Vector2i(1280, 720)
const CLIP := Vector2i(960, 540)
const EYE := 1.6
const BAR_Y := 1.05

var _cam: Camera3D
var _env: Environment
var _mug: Node3D
var _look: Dictionary = {}
var _plain := false


func _initialize() -> void:
	var placed: String = Offscreen.place()
	if placed != "":
		printerr(placed)
		quit(2)
		return
	_run.call_deferred()


func _run() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var out: String = a[1]
	var levels: Dictionary = JSON.parse_string(a[2]) if a.size() > 2 else {}
	_plain = a.size() > 3 and a[3] == "plain"
	var quick: bool = a.size() > 4 and a[4] == "quick"
	var scene: PackedScene = load(a[0])
	if scene == null:
		printerr("MUGLAB cannot load %s" % a[0])
		quit(3)
		return
	_stage()
	_mug = Node3D.new()
	root.add_child(_mug)
	var model: Node3D = scene.instantiate()
	_mug.add_child(model)
	if not _plain:
		_look = MugLook.apply(model, levels)
	var box := _bounds(model)
	print("MUGLAB bounds %s" % box)
	var states: Array = [["full", 1.0]] if _plain else [["full", 1.0], ["half", 0.5], ["empty", 0.0]]
	for s: Array in states:
		_fill(s[1])
		_on_bar()
		_save(await _view(Vector3(-0.17, BAR_Y + 0.21, 0.36), Vector3(0.012, BAR_Y + 0.085, 0.0), 30.0, SQUARE),
				out, "q34_%s" % s[0])
		_save(await _fp(), out, "fp_%s" % s[0])
		if quick:
			break
	_fill(1.0)
	_on_bar()
	_save(await _view(Vector3(0.012, BAR_Y + 0.09, 0.9), Vector3(0.012, BAR_Y + 0.09, 0.0), 14.0, SQUARE), out,
			"side_full")
	_save(await _view(Vector3(-0.05, BAR_Y + 0.42, 0.16), Vector3(0.0, BAR_Y + 0.15, 0.0), 30.0, SQUARE), out,
			"top_full")
	_save(await _view(Vector3(-0.09, BAR_Y + 0.215, 0.17), Vector3(0.0, BAR_Y + 0.135, 0.0), 30.0, SQUARE), out,
			"close_full")
	# the GPU cost of the first-person view, full
	_fill(1.0)
	await _fp()
	var vp: RID = root.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	var ms: Array = []
	for i: int in 30:
		await RenderingServer.frame_post_draw
		ms.append(RenderingServer.viewport_get_measured_render_time_gpu(vp))
	ms.sort()
	var f := FileAccess.open(out.path_join("cost.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"gpu_ms_fp_1280x720_median": ms[15], "renderer":
			RenderingServer.get_video_adapter_name()}))
	f.close()
	if not _plain and not quick:
		DirAccess.make_dir_recursive_absolute(out.path_join("drink"))
		var n: int = 72
		for i: int in n:
			var t: float = float(i) / float(n - 1)
			_fill(1.0 - 0.92 * smoothstep(0.08, 0.95, t))
			var img: Image = await _fp(CLIP, 1)
			img.save_png(out.path_join("drink/%04d.png" % i))
	print("MUGLAB done")
	quit(0)


func _fill(f: float) -> void:
	if not _plain:
		MugLook.set_fill(_look, f)


func _on_bar() -> void:
	_mug.transform = Transform3D(Basis(), Vector3(0.0, BAR_Y, 0.0))


## First person: the eye at 1.6 m looking down the bar, the mug where the right hand holds it (the handle toward
## the hand, a little toward the eye), the viewmodel's 50 degree lens.
func _fp(size: Vector2i = WIDE, settle: int = 12) -> Image:
	_cam.fov = 50.0
	_cam.transform = Transform3D(Basis.from_euler(Vector3(deg_to_rad(-6.0), 0.0, 0.0)), Vector3(0.0, EYE, 0.6))
	var local := Transform3D(Basis.from_euler(Vector3(deg_to_rad(4.0), deg_to_rad(-28.0), deg_to_rad(-3.0))),
			Vector3(0.1, -0.13, -0.37))
	_mug.transform = _cam.transform * local
	return await _frame(size, settle)


func _view(eye: Vector3, at: Vector3, fov: float, size: Vector2i) -> Image:
	_cam.fov = fov
	_cam.position = eye
	_cam.look_at(at)
	return await _frame(size, 12)


func _frame(size: Vector2i, settle: int) -> Image:
	if root.size != size:
		root.size = size
		DisplayServer.window_set_size(size)
		settle = maxi(settle, 12)
	for _i: int in settle:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	return img


func _save(img: Image, out: String, name: String) -> void:
	img.save_png(out.path_join(name + ".png"))
	print("MUGLAB wrote %s" % name)


func _bounds(n: Node) -> AABB:
	var box := AABB()
	var first := true
	for mi: Node in n.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		var b: AABB = m.global_transform * m.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box


func _stage() -> void:
	root.msaa_3d = Viewport.MSAA_4X
	root.screen_space_aa = Viewport.SCREEN_SPACE_AA_SMAA
	_env = Environment.new()
	_env.background_mode = Environment.BG_COLOR
	_env.background_color = Color(0.03, 0.04, 0.05)
	var sky := Sky.new()
	var sm := ShaderMaterial.new()
	sm.shader = preload("res://mug_lab/studio_sky.gdshader")
	sky.sky_material = sm
	sky.radiance_size = Sky.RADIANCE_SIZE_512
	_env.sky = sky
	_env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	_env.ambient_light_energy = 0.6
	_env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	_env.tonemap_mode = Environment.TONE_MAPPER_AGX
	_env.tonemap_exposure = 1.0
	_env.glow_enabled = true
	_env.glow_intensity = 0.5
	_env.glow_bloom = 0.02
	_env.glow_hdr_threshold = 1.2
	_env.ssr_enabled = true
	_env.ssao_enabled = true
	_env.ssao_radius = 0.3
	_env.ssao_intensity = 1.0
	var we := WorldEnvironment.new()
	we.environment = _env
	root.add_child(we)
	_cam = Camera3D.new()
	_cam.near = 0.02
	root.add_child(_cam)
	_cam.make_current()
	# the bar top: dark polished steel
	var bar := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(2.4, 0.05, 0.9)
	bar.mesh = bm
	var steel := StandardMaterial3D.new()
	steel.albedo_color = Color(0.07, 0.075, 0.085)
	steel.metallic = 0.85
	steel.roughness = 0.24
	bar.material_override = steel
	bar.position = Vector3(0.0, BAR_Y - 0.025, -0.15)
	root.add_child(bar)
	# the wall behind: teal-grey panels with warm and cold light strips (out of focus at these distances)
	var wall := MeshInstance3D.new()
	var wm := BoxMesh.new()
	wm.size = Vector3(8.0, 4.0, 0.1)
	wall.mesh = wm
	var wmat := StandardMaterial3D.new()
	wmat.albedo_color = Color(0.13, 0.17, 0.18)
	wmat.metallic = 0.5
	wmat.roughness = 0.45
	wall.material_override = wmat
	wall.position = Vector3(0.0, 1.5, -2.2)
	root.add_child(wall)
	for s: Array in [[Vector3(-0.9, 1.9, -2.13), Color(1.0, 0.7, 0.4), 6.0], [Vector3(1.1, 1.35, -2.13),
			Color(0.45, 0.75, 1.0), 5.0], [Vector3(0.2, 2.6, -2.13), Color(1.0, 0.8, 0.55), 6.0]]:
		var strip := MeshInstance3D.new()
		var sb := BoxMesh.new()
		sb.size = Vector3(1.2, 0.035, 0.02)
		strip.mesh = sb
		var em := StandardMaterial3D.new()
		em.albedo_color = Color(0, 0, 0)
		em.emission_enabled = true
		em.emission = s[1]
		em.emission_energy_multiplier = s[2]
		strip.material_override = em
		strip.position = s[0]
		root.add_child(strip)
	var key := DirectionalLight3D.new()
	key.light_color = Color(1.0, 0.86, 0.68)
	key.light_energy = 1.6
	key.shadow_enabled = true
	key.rotation_degrees = Vector3(-62.0, 25.0, 0.0)
	root.add_child(key)
	var rim := OmniLight3D.new()
	rim.light_color = Color(0.55, 0.75, 1.0)
	rim.light_energy = 2.5
	rim.omni_range = 3.0
	rim.position = Vector3(-0.9, BAR_Y + 0.35, -0.6)
	root.add_child(rim)
	var fp_rim := OmniLight3D.new()
	fp_rim.light_color = Color(0.55, 0.75, 1.0)
	fp_rim.light_energy = 1.5
	fp_rim.omni_range = 2.0
	fp_rim.position = Vector3(-0.5, EYE, -0.2)
	root.add_child(fp_rim)
