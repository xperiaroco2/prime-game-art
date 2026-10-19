extends SceneTree
## The alien mouths' proof (art #196, S6): each mouth shape three ways at the same framing, the GPT sheet's panel
## (the target), the 3D replacement piece and the flipbook shell, plus both at a three-quarter view and talking side
## by side from the same WAV. In a real window kept off-screen (godot/lib/offscreen.gd, #214), run through the
## runner's _godot.window() with the window 448 x 300 (the mouth window's aspect, 224 x 150 sheet px):
##   --path godot --audio-driver Dummy -s res://alien/mouths.gd -- <spec.json>
## The spec: {"scene": "res://import/<character>.glb", "wav": "<speech.wav>", "out": "<dir>", "ref": "<dir of
## <design>_<shape>.png>", "rects": {design: {shape: [x0, x1, z0, z1]}}} (tools/blender/alien_mouths.py's
## build_report.json: flip_rects_m, Blender metres, front -Y). Writes into <out>: compare_<design>.png (rows: the
## shapes; columns: sheet, 3D, flip), threequarter_<design>.png, talk.png and mouths.json (the talk picks).
## Prints MOUTHS saved <path>, or MOUTHS error <why> and exits 1.

const Offscreen = preload("res://lib/offscreen.gd")
const AlienRig = preload("res://alien/alien.gd")
const WATCHDOG_S: float = 300.0
const SHEET_W: int = 1260
const SHAPES: Array[String] = ["rest", "M", "small", "A", "E", "O"]

var _spec: Dictionary
var _camera: Camera3D
var _label: Label
var _a: Node3D  # the 3D mouth
var _b: Node3D  # the flipbook mouth
var _rig_a: Node
var _rig_b: Node
var _out: String


func _initialize() -> void:
	var placed: String = Offscreen.place()
	if placed != "":
		_fail(placed)
		return
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 1:
		_fail("usage: -- <spec.json>")
		return
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	var spec: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not (spec is Dictionary and spec.has("scene") and spec.has("out") and spec.has("rects")):
		_fail("%s is not a mouths spec" % args[0])
		return
	_spec = spec
	_run()


func _fail(why: String) -> void:
	printerr("MOUTHS error ", why)
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
	var key := DirectionalLight3D.new()  # the S3 proof's key and fill
	key.rotation_degrees = Vector3(-38, 28, 0)
	key.light_energy = 1.35
	key.light_color = Color(1.0, 0.97, 0.92)
	key.shadow_enabled = true
	key.directional_shadow_max_distance = 6.0
	root.add_child(key)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-15, 200, 0)
	fill.light_energy = 0.45
	fill.light_color = Color(0.85, 0.9, 1.0)
	root.add_child(fill)
	_camera = Camera3D.new()
	root.add_child(_camera)
	_camera.make_current()
	var layer := CanvasLayer.new()
	root.add_child(layer)
	_label = Label.new()
	_label.position = Vector2(6, 2)
	_label.add_theme_font_size_override("font_size", 20)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 5)
	layer.add_child(_label)


func _character(x: float, mode: String) -> Array:
	var packed: PackedScene = load(_spec["scene"])
	var ch: Node3D = packed.instantiate()
	ch.position = Vector3(x, 0, 0)
	root.add_child(ch)
	var rig: Node = AlienRig.new()
	ch.add_child(rig)
	rig.setup(ch)
	rig.auto_blink = false
	rig.set_mouth_mode(mode)
	for ap: Node in ch.find_children("*", "AnimationPlayer", true, false):
		(ap as AnimationPlayer).stop()
	return [ch, rig]


func _shot(text: String, frames: int = 3) -> Image:
	_label.text = text
	for _i: int in frames:
		await process_frame
	await RenderingServer.frame_post_draw
	return root.get_texture().get_image()


func _front(rect: Array, x_off: float) -> void:  # rect: Blender [x0, x1, z0, z1]; Godot x = x, y = z
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_camera.keep_aspect = Camera3D.KEEP_HEIGHT
	_camera.size = float(rect[3]) - float(rect[2])
	var c := Vector3((float(rect[0]) + float(rect[1])) / 2.0 + x_off, (float(rect[2]) + float(rect[3])) / 2.0, 1.0)
	_camera.look_at_from_position(c, c - Vector3(0, 0, 1), Vector3.UP)


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
	print("MOUTHS saved ", path)


func _ref(design: String, shape: String, size: Vector2i) -> Image:
	var img := Image.load_from_file("%s/%s_%s.png" % [_spec["ref"], design, shape])
	img.convert(Image.FORMAT_RGBA8)
	img.resize(size.x, size.y, Image.INTERPOLATE_LANCZOS)
	return img


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_stage()
	var ra: Array = _character(-0.5, "3d")
	var rb: Array = _character(0.5, "flip")
	_a = ra[0]
	_rig_a = ra[1]
	_b = rb[0]
	_rig_b = rb[1]
	await process_frame
	var size: Vector2i = root.get_texture().get_image().get_size()
	for design: String in ["frog", "overbite"]:
		_rig_a.set_mouth_design(design)
		_rig_b.set_mouth_design(design)
		var imgs: Array = []
		var tq: Array = []
		for shape: String in SHAPES:
			_rig_a.show_mouth(shape)
			_rig_b.show_mouth(shape)
			var rect: Array = _spec["rects"][design][shape]
			_label.text = ""
			imgs.append(_ref(design, shape, size))
			_front(rect, -0.5)
			imgs.append(await _shot("%s %s 3D" % [design, shape]))
			_front(rect, 0.5)
			imgs.append(await _shot("%s %s flip" % [design, shape]))
			_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
			for side: Array in [[-0.5, "3D"], [0.5, "flip"]]:
				var t := Vector3(float(side[0]), 1.49, 0.0)
				var yaw: float = deg_to_rad(35.0)
				_camera.fov = 30.0
				_camera.look_at_from_position(t + Vector3(sin(yaw), 0.05, cos(yaw)) * 0.45, t, Vector3.UP)
				tq.append(await _shot("%s %s %s 35deg" % [design, shape, side[1]]))
		_sheet(imgs, 3, "compare_%s.png" % design)
		_sheet(tq, 4, "threequarter_%s.png" % design)
	var talk: Array = await _talk()
	if talk.is_empty():
		return
	_sheet(talk, 4, "talk.png")
	var f := FileAccess.open(_out + "/mouths.json", FileAccess.WRITE)
	f.store_string(JSON.stringify({"talk": _rig_a.talk_log}, " "))
	f.close()
	print("MOUTHS saved ", _out + "/mouths.json")
	quit(0)


func _talk() -> Array:
	var bus: int = AudioServer.bus_count
	AudioServer.add_bus(bus)
	AudioServer.set_bus_name(bus, "AlienVoice")
	AudioServer.set_bus_send(bus, "Master")
	var an := AudioEffectSpectrumAnalyzer.new()
	an.buffer_length = 0.1
	an.fft_size = AudioEffectSpectrumAnalyzer.FFT_SIZE_1024
	AudioServer.add_bus_effect(bus, an, 0)
	AudioServer.set_bus_mute(0, true)
	var stream: AudioStreamWAV = AudioStreamWAV.load_from_file(_spec["wav"])
	if stream == null:
		_fail("cannot load %s" % _spec["wav"])
		return []
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.bus = "AlienVoice"
	root.add_child(player)
	var imgs: Array = []
	_a.position.x = -0.27  # side by side in the Idle (arms down), the camera on the mouths
	_b.position.x = 0.27
	for ch: Node3D in [_a, _b]:
		for ap: Node in ch.find_children("*", "AnimationPlayer", true, false):
			var player_a: AnimationPlayer = ap
			for clip: String in player_a.get_animation_list():
				if clip.get_slice("|", clip.get_slice_count("|") - 1).to_lower() == "idle":
					player_a.play(clip)
					player_a.seek(0.5, true)
					player_a.pause()
	await process_frame
	await process_frame
	var m: Vector3 = (_a.find_child("Mouth", true, false) as Node3D).global_position
	_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
	_camera.fov = 30.0
	var t := Vector3(0, m.y + 0.03, m.z)
	_camera.look_at_from_position(t + Vector3(0, 0, 1.15), t, Vector3.UP)
	for design: String in ["frog", "overbite"]:
		_rig_a.set_mouth_design(design)
		_rig_b.set_mouth_design(design)
		player.play()
		_rig_a.listen("AlienVoice")
		var start: int = Time.get_ticks_msec()
		var taken: int = 0
		var seen: int = 0
		while player.playing and Time.get_ticks_msec() - start < 8000:
			await process_frame
			_rig_b.show_mouth(_rig_a.mouth_piece)
			var n: int = _rig_a.talk_log.size()
			if n > seen:
				seen = n
				var e: Dictionary = _rig_a.talk_log[n - 1]
				if taken < 8 and e["t_ms"] >= 120 and n % 3 == 0:
					imgs.append(await _shot("%s %s %d ms  3D | flip" % [design, e["piece"], e["t_ms"]], 1))
					taken += 1
		_rig_a.stop_listening()
		_rig_b.show_mouth("rest")
	return imgs
