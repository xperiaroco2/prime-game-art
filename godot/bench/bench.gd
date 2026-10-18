extends SceneTree
## The character budget bench (art #212, docs/godot.md "Bench"): N copies of a character in a meeting ring, each
## playing its idle clip, under a directional light with 4 shadow splits and one shadowed omni lamp at the ring's
## centre, timed in a real window for `tools/run.py bench`. Never headless and never minimized (Godot does not draw
## then); the runner opens the window through _godot.window() (1920x1080 in PRIME_WINDOW) and the script moves it
## off-screen first (godot/lib/offscreen.gd, #214):
##   godot --position 30000,30000 --resolution 1x1 --path godot -s res://bench/bench.gd -- <out folder> <bench_spec.json>
## The spec (tools/runner/commands/_bench.py) lists the GLBs (one per face-morph count) and the variants; a variant
## names a GLB, a copy count, the LOD ("auto": the importer's LODs, the viewport's mesh_lod_threshold 1.0; "off":
## 0.0, always LOD0; "hand": the shadow part drawn as a hand-made LOD2 from the spec's hand_lod_m on, with visibility
## ranges, the full meshes before it, all casting) and the shadow caster ("full": every mesh casts; "proxy": the
## meshes draw without shadows and the part whose name holds the spec's shadow_part casts alone, SHADOWS_ONLY).
## Every face morph is weighted (weight 0.05 each, the worst case). Per variant: the median GPU and CPU ms over the measured frames (viewport measure render time: the
## rendering only), the median process ms (Performance TIME_PROCESS: the animation players and skeleton poses) and
## whole frame ms, the frame's primitives, draw calls and objects, the video, texture and buffer memory (Performance
## monitors), and how many copies stand beyond hand_lod_m from the camera (to each copy's origin). The ring's
## geometry comes from the spec's "ring".
## Writes bench.json and sheet.png (one shot per GLB and copy count); prints BENCH saved <path>, or BENCH error <why>
## and exits 1.

const Character = preload("res://lib/character.gd")
const Offscreen = preload("res://lib/offscreen.gd")
const WATCHDOG_S: float = 900.0
const MORPH_WEIGHT: float = 0.05
var _label: Label
var _ring: Dictionary = {}
var _copies: Array[Node] = []
var _players: Array[AnimationPlayer] = []


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if DisplayServer.get_name() == "headless":
		_fail("running headless; the bench needs a real window")
		return
	var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
	if placed != "":
		_fail(placed)
		return
	if args.size() < 2:
		_fail("usage: -- <out folder> <bench_spec.json>")
		return
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	var spec: Variant = Character.read_json(args[1])
	if not (spec is Dictionary and spec.has("variants") and spec.has("glbs") and spec.has("ring")):
		_fail("%s is not a bench spec (give an absolute path)" % args[1])
		return
	_ring = spec["ring"]
	_run(args[0], spec)


func _run(out_dir: String, spec: Dictionary) -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	_stage()
	await process_frame
	var size: Vector2i = root.get_visible_rect().size
	var record: Dictionary = {"window": [size.x, size.y], "godot": Engine.get_version_info()["string"],
			"renderer": "%s %s" % [RenderingServer.get_current_rendering_driver_name(),
					RenderingServer.get_current_rendering_method()],
			"adapter": RenderingServer.get_video_adapter_name(),
			"adapter_vendor": RenderingServer.get_video_adapter_vendor(), "fov_deg": spec["fov_deg"],
			"frames": spec["frames"], "hand_lod_m": spec["hand_lod_m"], "ring": _ring, "rows": [], "groups": []}
	var vp: RID = root.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	var shots: Array[Image] = []
	var group_key: String = ""
	var scenes: Dictionary = {}
	for v: Dictionary in spec["variants"]:
		var key: String = "%s x%d" % [v["glb"], int(v["copies"])]
		if key != group_key:
			group_key = key
			_clear()
			if not scenes.has(v["glb"]):
				scenes.clear()  # one GLB loaded at a time
			for _i: int in 8:
				await process_frame
			var before: Dictionary = _memory()
			var glb: Dictionary = spec["glbs"][v["glb"]]
			if not scenes.has(v["glb"]):
				var packed: PackedScene = load(glb["res"]) as PackedScene
				if packed == null:
					_fail("cannot load %s" % glb["res"])
					return
				scenes[v["glb"]] = packed
			if not _place(scenes[v["glb"]], int(v["copies"]), spec):
				return
			_apply(v, spec)
			for f: int in int(spec["warmup_frames"]):  # the GPU clocks up and every pipeline compiles first
				await RenderingServer.frame_post_draw
			var after: Dictionary = _memory()
			var group: Dictionary = {"key": key, "glb": v["glb"], "copies": v["copies"], "memory_before": before,
					"memory_after": after}
			record["groups"].append(group)
			_label.text = "%s   %d copies   %d face morphs" % [v["glb"], int(v["copies"]), int(glb["morphs"])]
			_label.visible = true
			await RenderingServer.frame_post_draw
			await RenderingServer.frame_post_draw
			var img: Image = root.get_texture().get_image()
			img.save_png("%s/shots/%s_x%d.png" % [out_dir, v["glb"], int(v["copies"])])
			shots.append(img)
			_label.visible = false
		_apply(v, spec)
		var row: Dictionary = await _measure(v, spec, vp)
		record["rows"].append(row)
		print("BENCH row ", row["id"], " gpu ", row["gpu_ms"], " ms cpu ", row["cpu_ms"], " ms")
	_clear()
	_save_sheet(shots, spec, "%s/sheet.png" % out_dir)
	var json_path: String = "%s/bench.json" % out_dir
	if not Character.write_json(json_path, record):
		_fail("cannot write %s" % json_path)
		return
	print("BENCH saved ", json_path)
	quit(0)


func _stage() -> void:
	var env := Environment.new()
	var sky := Sky.new()
	sky.sky_material = ProceduralSkyMaterial.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	var world := WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50.0, 35.0, 0.0)
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_max_distance = 60.0
	root.add_child(sun)
	var lamp := OmniLight3D.new()
	lamp.position = Vector3(0.0, 2.6, 0.0)
	lamp.omni_range = 9.0
	lamp.light_energy = 1.5
	lamp.shadow_enabled = true
	lamp.omni_shadow_mode = OmniLight3D.SHADOW_CUBE
	root.add_child(lamp)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(60.0, 60.0)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.55, 0.56, 0.58)
	plane.material = mat
	ground.mesh = plane
	root.add_child(ground)
	var cam := Camera3D.new()
	cam.name = "BenchCamera"
	root.add_child(cam)
	var layer := CanvasLayer.new()
	_label = Label.new()
	_label.position = Vector2(16, 12)
	_label.add_theme_font_size_override("font_size", 40)
	_label.add_theme_color_override("font_color", Color(0.1, 0.1, 0.12))
	_label.visible = false
	layer.add_child(_label)
	root.add_child(layer)


func _ring_radius(copies: int) -> float:
	return maxf(float(_ring["min_m"]), copies * float(_ring["spacing_m"]) / TAU)


func _place(packed: PackedScene, copies: int, spec: Dictionary) -> bool:
	var r: float = _ring_radius(copies)
	for i: int in copies:
		var node: Node3D = packed.instantiate() as Node3D
		var a: float = TAU * i / copies
		node.position = Vector3(sin(a) * r, 0.0, cos(a) * r)
		root.add_child(node)
		node.look_at(Vector3(0.0, 0.0, 0.0), Vector3.UP, true)  # the model's front is +Z
		_copies.append(node)
		var players: Array[Node] = Character.nodes_of(node, "AnimationPlayer")
		if players.size() != 1:
			_fail("%d animation players in a copy, not one" % players.size())
			return false
		var player: AnimationPlayer = players[0] as AnimationPlayer
		var clip: String = _clip(player, spec["clip"])
		if clip == "":
			_fail("no animation like %s" % spec["clip"])
			return false
		player.play(clip)
		player.seek(fmod(i * 0.37, maxf(0.01, player.get_animation(clip).length)), true)
		_players.append(player)
		for mi: MeshInstance3D in Character.meshes(node):
			if mi.mesh == null:
				continue
			for b: int in mi.mesh.get_blend_shape_count():
				mi.set_blend_shape_value(b, MORPH_WEIGHT)
	var cam: Camera3D = root.get_node("BenchCamera") as Camera3D
	cam.fov = float(spec["fov_deg"])
	cam.position = Vector3(0.0, float(_ring["eye_m"]), r + float(_ring["camera_back_m"]))
	cam.look_at(Vector3(0.0, 1.0, 0.0))
	cam.current = true
	return true


func _clip(player: AnimationPlayer, want: String) -> String:
	if player.has_animation(want):
		return want
	for name: StringName in player.get_animation_list():
		if want.to_lower() in String(name).to_lower():
			return name
	return ""


func _apply(v: Dictionary, spec: Dictionary) -> void:
	var lod: String = v["lod"]
	root.mesh_lod_threshold = 0.0 if lod == "off" else 1.0
	var hand: bool = lod == "hand"
	var proxy: bool = v["shadow"] == "proxy"
	var far: float = float(spec["hand_lod_m"])
	for node: Node in _copies:
		for mi: MeshInstance3D in Character.meshes(node):
			var is_proxy: bool = spec["shadow_part"] in String(mi.name)
			mi.visibility_range_begin = far if hand and is_proxy else 0.0
			mi.visibility_range_end = far if hand and not is_proxy else 0.0
			if hand:  # the part as a hand-made LOD2 beyond `far`, the full meshes before it; both cast
				mi.visible = true
				mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
			elif is_proxy:
				mi.visible = proxy
				mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
			else:
				mi.cast_shadow = (GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if proxy
						else GeometryInstance3D.SHADOW_CASTING_SETTING_ON)


func _clear() -> void:
	for node: Node in _copies:
		node.queue_free()
	_copies.clear()
	_players.clear()


func _memory() -> Dictionary:
	return {"video_mb": snappedf(Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0, 0.01),
			"texture_mb": snappedf(Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED) / 1048576.0, 0.01),
			"buffer_mb": snappedf(Performance.get_monitor(Performance.RENDER_BUFFER_MEM_USED) / 1048576.0, 0.01)}


func _measure(v: Dictionary, spec: Dictionary, vp: RID) -> Dictionary:
	for f: int in int(spec["settle_frames"]):
		await RenderingServer.frame_post_draw
	var gpu: Array[float] = []
	var cpu: Array[float] = []
	var prims: Array[float] = []
	var draws: Array[float] = []
	var objects: Array[float] = []
	var process: Array[float] = []
	var frame: Array[float] = []
	var last_us: int = Time.get_ticks_usec()
	for f: int in int(spec["frames"]):
		await RenderingServer.frame_post_draw
		var now_us: int = Time.get_ticks_usec()
		frame.append((now_us - last_us) / 1000.0)
		last_us = now_us
		process.append(Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0)
		gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(vp))
		cpu.append(RenderingServer.viewport_get_measured_render_time_cpu(vp))
		prims.append(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME))
		draws.append(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
		objects.append(Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME))
	var row: Dictionary = v.duplicate()
	row["gpu_ms"] = snappedf(_median(gpu), 0.001)
	row["cpu_ms"] = snappedf(_median(cpu), 0.001)
	row["gpu_ms_p95"] = snappedf(_quantile(gpu, 0.95), 0.001)
	row["process_ms"] = snappedf(_median(process), 0.001)
	row["frame_ms"] = snappedf(_median(frame), 0.001)
	row["beyond_hand_lod"] = _beyond(float(spec["hand_lod_m"]))
	row["primitives"] = int(_median(prims))
	row["draw_calls"] = int(_median(draws))
	row["objects"] = int(_median(objects))
	row["fps"] = Engine.get_frames_per_second()
	row.merge(_memory())
	return row


func _beyond(far: float) -> int:
	var cam: Camera3D = root.get_node("BenchCamera") as Camera3D
	var n: int = 0
	for node: Node in _copies:
		if cam.global_position.distance_to((node as Node3D).global_position) > far:
			n += 1
	return n


func _median(values: Array[float]) -> float:
	return _quantile(values, 0.5)


func _quantile(values: Array[float], q: float) -> float:
	if values.is_empty():
		return 0.0
	var s: Array[float] = values.duplicate()
	s.sort()
	return s[clampi(int(round(q * (s.size() - 1))), 0, s.size() - 1)]


func _save_sheet(shots: Array[Image], spec: Dictionary, path: String) -> void:
	if shots.is_empty():
		return
	var cw: int = int(spec["sheet_cell"][0])
	var ch: int = int(spec["sheet_cell"][1])
	var cols: int = mini(int(spec["sheet_cols"]), shots.size())
	var rows: int = ceili(shots.size() / float(cols))
	var sheet: Image = Image.create(cw * cols, ch * rows, false, Image.FORMAT_RGB8)
	sheet.fill(Color(1, 1, 1))
	for i: int in shots.size():
		var img: Image = shots[i].duplicate() as Image
		img.convert(Image.FORMAT_RGB8)
		img.resize(cw, ch, Image.INTERPOLATE_LANCZOS)
		sheet.blit_rect(img, Rect2i(0, 0, cw, ch), Vector2i((i % cols) * cw, (i / cols) * ch))
	sheet.save_png(path)


func _fail(why: String) -> void:
	push_error("BENCH error " + why)
	print("BENCH error ", why)
	quit(1)
