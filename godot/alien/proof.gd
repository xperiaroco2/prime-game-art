extends SceneTree
## The alien parts kit's Godot proof (art #196, S3), in a real window kept off-screen (godot/lib/offscreen.gd, #214;
## never headless, never minimized). A run goes through the runner's _godot.window() (docs/godot.md, "The off-screen
## window"), which adds `--position 30000,30000 --resolution 1x1` and PRIME_WINDOW=<w>x<h>, with the arguments
##   --path godot --audio-driver Dummy -s res://alien/proof.gd -- <spec.json>
## The spec: {"scene": "res://import/alien_character.glb", "wav": "<speech.wav>", "out": "<dir>"}. The character is
## driven by alien.gd (hue shader, eye, mouth and crest swaps, blink by lid rotation, the mouth from the WAV through an
## AudioEffectSpectrumAnalyzer on its own bus; Master muted, so nothing is heard). Writes into <out>:
## turntable_1m.png, turntable_3m.png, idle_walk.png, walk_hands.png, blink.png, talk.png, variants.png, hues.png
## (sheets of about 1280 px, one caption per tile) and proof.json (draw calls and primitives, the talk picks).
## Prints PROOF saved <path>, or PROOF error <why> and exits 1.

const Offscreen = preload("res://lib/offscreen.gd")
const AlienRig = preload("res://alien/alien.gd")
const WATCHDOG_S: float = 400.0
const SHEET_W: int = 1280

var _spec: Dictionary
var _camera: Camera3D
var _label: Label
var _ch: Node3D
var _rig: Node
var _player: AnimationPlayer
var _floor: MeshInstance3D
var _out: String
var _report: Dictionary = {}


func _initialize() -> void:
	var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
	if placed != "":
		_fail(placed)
		return
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 1:
		_fail("usage: -- <spec.json>")
		return
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	var spec: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not (spec is Dictionary and spec.has("scene") and spec.has("wav") and spec.has("out")):
		_fail("%s is not a proof spec" % args[0])
		return
	_spec = spec
	_run()


func _fail(why: String) -> void:
	printerr("PROOF error ", why)
	quit(1)


func _stage() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.40, 0.41, 0.43)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.62, 0.66, 0.72)
	env.ambient_light_energy = 0.55
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var we := WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-38, 28, 0)
	key.light_energy = 1.35
	key.light_color = Color(1.0, 0.97, 0.92)
	key.shadow_enabled = true
	key.directional_shadow_max_distance = 12.0
	root.add_child(key)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-15, 200, 0)
	fill.light_energy = 0.45
	fill.light_color = Color(0.85, 0.9, 1.0)
	root.add_child(fill)
	_floor = MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(12, 12)
	_floor.mesh = plane
	var fm := StandardMaterial3D.new()
	fm.albedo_color = Color(0.46, 0.46, 0.47)
	fm.roughness = 0.9
	_floor.material_override = fm
	root.add_child(_floor)
	_camera = Camera3D.new()
	root.add_child(_camera)
	_camera.make_current()
	var layer := CanvasLayer.new()
	root.add_child(layer)
	_label = Label.new()
	_label.position = Vector2(8, 4)
	_label.add_theme_font_size_override("font_size", 26)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 6)
	layer.add_child(_label)


func _look(target: Vector3, yaw_deg: float, pitch_deg: float, dist: float, fov: float) -> void:
	var yaw: float = deg_to_rad(yaw_deg)
	var pitch: float = deg_to_rad(pitch_deg)
	var back := Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch))
	_camera.fov = fov
	_camera.look_at_from_position(target + back * dist, target, Vector3.UP)


func _shot(text: String, frames: int = 3) -> Image:
	_label.text = text
	for _i: int in frames:
		await process_frame
	await RenderingServer.frame_post_draw
	return root.get_texture().get_image()


func _pose(clip: String, t: float) -> void:
	_player.play(clip)
	_player.seek(t, true)
	_player.pause()


func _sheet(images: Array, cols: int, name: String) -> void:
	var tw: int = SHEET_W / cols
	var first: Image = images[0]
	var th: int = int(round(float(tw) * first.get_height() / first.get_width()))
	var rows: int = int(ceil(float(images.size()) / cols))
	var sheet := Image.create(tw * cols, th * rows, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.1, 0.1, 0.1))
	for i: int in images.size():
		var img: Image = images[i].duplicate()
		img.convert(Image.FORMAT_RGB8)
		img.resize(tw, th, Image.INTERPOLATE_LANCZOS)
		sheet.blit_rect(img, Rect2i(0, 0, tw, th), Vector2i((i % cols) * tw, (i / cols) * th))
	var path: String = _out + "/" + name
	sheet.save_png(path)
	print("PROOF saved ", path)


func _clip(word: String) -> String:
	for n: String in _player.get_animation_list():  # "CharacterArmature|Idle": the part after the action's prefix
		if n.get_slice("|", n.get_slice_count("|") - 1).to_lower() == word.to_lower():
			return n
	return ""


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_stage()
	var packed: PackedScene = load(_spec["scene"]) as PackedScene
	if packed == null:
		_fail("cannot load %s" % _spec["scene"])
		return
	_ch = packed.instantiate()
	root.add_child(_ch)
	_rig = AlienRig.new()
	_ch.add_child(_rig)
	_rig.setup(_ch)
	_rig.auto_blink = false
	_player = _ch.find_child("AnimationPlayer", true, false) as AnimationPlayer
	var idle: String = _clip("Idle")
	var walk: String = _clip("Walk")
	_report["clips"] = Array(_player.get_animation_list())
	if idle == "" or walk == "":
		_fail("no Idle or Walk clip in %s" % [_report["clips"]])
		return
	_pose(idle, 0.0)
	await _stats()
	# 1, 2: the turntables (Idle's first frame)
	var t1: Array = []
	var t3: Array = []
	for yaw: int in range(0, 360, 45):
		_look(Vector3(0, 1.45, 0), yaw, 0, 1.0, 50)
		t1.append(await _shot("1 m  %d deg" % yaw))
	for yaw: int in range(0, 360, 45):
		_look(Vector3(0, 0.9, 0), yaw, 3, 3.0, 40)
		t3.append(await _shot("3 m  %d deg" % yaw))
	_sheet(t1, 4, "turntable_1m.png")
	_sheet(t3, 4, "turntable_3m.png")
	# 3: Idle and Walk, 3/4 at 2.6 m; the hands in the Walk from the side at 1.2 m
	var iw: Array = []
	var hands: Array = []
	for clip: String in [idle, walk]:
		var length: float = _player.get_animation(clip).length
		for i: int in 6:
			_pose(clip, length * i / 6.0)
			_look(Vector3(0, 0.9, 0), 35, 3, 2.6, 40)
			iw.append(await _shot("%s %.2f s" % [clip, length * i / 6.0]))
	var wl: float = _player.get_animation(walk).length
	for i: int in 8:
		_pose(walk, wl * i / 8.0)
		_look(Vector3(0.0, 0.95, 0), 90 if i < 4 else 140, 0, 1.15, 40)
		hands.append(await _shot("%s %.2f s %s" % [walk, wl * i / 8.0, "side" if i < 4 else "back 3/4"]))
	_sheet(iw, 6, "idle_walk.png")
	_sheet(hands, 4, "walk_hands.png")
	_pose(idle, 0.0)
	# 4: the blink strip, both eye designs, from the rest state
	var blink: Array = []
	for design: String in ["bored", "manic"]:
		_rig.set_eyes(design)
		_rig.set_lids("rest")
		for t: float in [0.0, 30.0, 60.0, 80.0, 100.0, 125.0, 150.0, 200.0]:
			_rig.blink_at(t)
			_look(Vector3(0, 1.56, 0), 0, 0, 0.75, 40)
			blink.append(await _shot("%s blink %d ms" % [design, int(t)]))
		_rig.set_lids("open")
		blink.append(await _shot("%s open (surprise)" % design))
		_rig.set_lids("rest")
		blink.append(await _shot("%s rest" % design))
	_sheet(blink, 5, "blink.png")
	_rig.set_eyes("bored")
	# 5: talk from the WAV through the analyzer, 12 consecutive picks per mouth design
	var talk: Array = await _talk()
	if talk.is_empty():
		return
	_sheet(talk, 6, "talk.png")
	# 6: the 2 x 2 face variants and the crests
	var var_imgs: Array = []
	for e: String in ["bored", "manic"]:
		for m: String in ["frog", "overbite"]:
			_rig.set_eyes(e)
			_rig.set_mouth_design(m)
			_rig.show_mouth("rest")
			_look(Vector3(0, 1.55, 0), 25, 0, 0.8, 40)
			var_imgs.append(await _shot("%s + %s" % [e, m]))
	_rig.set_eyes("bored")
	_rig.set_mouth_design("frog")
	for c: String in ["antennae", "fins"]:
		_rig.set_crest(c)
		_look(Vector3(0, 1.6, 0), 35, 0, 1.0, 40)
		var_imgs.append(await _shot("crest %s" % c))
	_rig.set_crest("")
	_sheet(var_imgs, 3, "variants.png")
	# 7: the three hues, 1.6 m and 3.5 m
	var hue_imgs: Array = []
	for d: Array in [[Vector3(0, 1.25, 0), 1.6], [Vector3(0, 0.9, 0), 3.5]]:
		for h: String in ["teal", "coral", "violet"]:
			_rig.set_hue(h)
			_look(d[0], 30, 2, d[1], 40)
			hue_imgs.append(await _shot("%s %.1f m" % [h, d[1]]))
	_rig.set_hue("teal")
	_sheet(hue_imgs, 3, "hues.png")
	var f := FileAccess.open(_out + "/proof.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(_report, " "))
	f.close()
	print("PROOF saved ", _out + "/proof.json")
	print("PROOF stats ", JSON.stringify(_report["stats"]))
	quit(0)


func _info(kind: int) -> Dictionary:
	var vp: Viewport = root
	return {
		"draw_calls": vp.get_render_info(kind, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME),
		"primitives": vp.get_render_info(kind, Viewport.RENDER_INFO_PRIMITIVES_IN_FRAME),
		"objects": vp.get_render_info(kind, Viewport.RENDER_INFO_OBJECTS_IN_FRAME),
	}


func _stats() -> void:
	## Draw calls and primitives at 3 m (front), the character on and off, the floor off: the difference is the
	## character's own cost (the visible pass and the shadow pass apart).
	_floor.visible = false
	_look(Vector3(0, 0.9, 0), 0, 3, 3.0, 40)
	var out: Dictionary = {}
	for state: String in ["character", "empty"]:
		_ch.visible = state == "character"
		for _i: int in 6:
			await process_frame
		await RenderingServer.frame_post_draw
		out[state] = {"visible": _info(Viewport.RENDER_INFO_TYPE_VISIBLE), "shadow": _info(Viewport.RENDER_INFO_TYPE_SHADOW)}
	_ch.visible = true
	_floor.visible = true
	var shown: int = 0
	var shown_meshes: Array = []
	for mi: Node in _ch.find_children("*", "MeshInstance3D", true, false):
		var m: MeshInstance3D = mi
		if m.is_visible_in_tree():
			shown_meshes.append(m.name)
			for s: int in m.mesh.get_surface_count():
				var arr: Array = m.mesh.surface_get_arrays(s)
				var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
				shown += idx.size() / 3 if idx.size() > 0 else (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
	out["shown_meshes"] = shown_meshes
	out["shown_triangles"] = shown
	_report["stats"] = out


func _talk() -> Array:
	var bus: int = AudioServer.bus_count
	AudioServer.add_bus(bus)
	AudioServer.set_bus_name(bus, "AlienVoice")
	AudioServer.set_bus_send(bus, "Master")
	var an := AudioEffectSpectrumAnalyzer.new()
	an.buffer_length = 0.1
	an.fft_size = AudioEffectSpectrumAnalyzer.FFT_SIZE_1024
	AudioServer.add_bus_effect(bus, an, 0)
	AudioServer.set_bus_mute(0, true)  # Master: nothing is heard
	var stream: AudioStreamWAV = AudioStreamWAV.load_from_file(_spec["wav"])
	if stream == null:
		_fail("cannot load %s" % _spec["wav"])
		return []
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.bus = "AlienVoice"
	root.add_child(player)
	var imgs: Array = []
	var logs: Dictionary = {}
	for design: String in ["frog", "overbite"]:
		_rig.set_mouth_design(design)
		_look(Vector3(0, 1.52, 0), 30, 0, 0.7, 40)
		player.play()
		_rig.listen("AlienVoice")
		var start: int = Time.get_ticks_msec()
		var taken: int = 0
		var seen: int = 0
		while player.playing and Time.get_ticks_msec() - start < 8000:
			await process_frame
			var n: int = _rig.talk_log.size()
			if n > seen:
				seen = n
				var e: Dictionary = _rig.talk_log[n - 1]
				if taken < 12 and e["t_ms"] >= 120:
					imgs.append(await _shot("%s %s  %d ms" % [design, e["piece"], e["t_ms"]], 1))
					taken += 1
		_rig.stop_listening()
		logs[design] = _rig.talk_log.duplicate()
		var counts: Dictionary = {}
		for e: Dictionary in logs[design]:
			counts[e["piece"]] = counts.get(e["piece"], 0) + 1
		print("PROOF talk %s picks %d %s" % [design, logs[design].size(), JSON.stringify(counts)])
		if counts.size() <= 1:
			_fail("the analyzer gave no signal (%s): picks %s" % [design, JSON.stringify(counts)])
			return []
	_report["talk"] = logs
	return imgs
