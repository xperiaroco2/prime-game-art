extends SceneTree
## The alien's face materials proof (art #196, S5), in a real window kept off-screen (godot/lib/offscreen.gd, #214;
## never headless, never minimized). A run goes through the runner's _godot.window() (docs/godot.md, "The off-screen
## window") with the arguments
##   --path godot -s res://alien/face_proof.gd -- <spec.json>
## The spec: {"scene": "res://import/alien_character.glb", "out": "<dir>", "hdri": "<studio .hdr, or empty>"}. The stage
## is the approved showroom look's Medium preset (godot/showroom/look_presets.json: AgX at exposure 0.9, the studio
## sky as ambient (half, the other half a warm colour at 0.12) and reflections, SSAO, MSAA 2x; the lights are
## look_presets.json's, light D since 2026-10-19: key 3.0 with specular 0.6, fill 0.12, back 0.3, a back rim 3.0; the eyes' catch light is the eye shader's own, alien_eye.gdshader). alien.gd drives the
## character; set_face_look("first") shows the first test's materials, "s5" the new ones. Writes into <out>:
## compare.png (the four eye/mouth combinations, first test above, S5 below), faces.png (S5, 2 x 2 close),
## eyes.png (both eye designs very close, first test and S5), blink.png, talk.png (the six pieces of both mouths),
## hues.png, grid.png (the lips: roughness against colour) and face_proof.json.
## Prints PROOF saved <path>, or PROOF error <why> and exits 1.

const Offscreen = preload("res://lib/offscreen.gd")
const AlienRig = preload("res://alien/alien.gd")
const LookLights = preload("res://showroom/look_lights.gd")
const WATCHDOG_S: float = 300.0
const SHEET_W: int = 1280

var _spec: Dictionary
var _camera: Camera3D
var _label: Label
var _ch: Node3D
var _rig: Node
var _player: AnimationPlayer
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
	if not (spec is Dictionary and spec.has("scene") and spec.has("out")):
		_fail("%s is not a face proof spec" % args[0])
		return
	_spec = spec
	_run()


func _fail(why: String) -> void:
	printerr("PROOF error ", why)
	quit(1)


func _light(at: Vector3, energy: float, specular: float, shadow: bool) -> DirectionalLight3D:
	var light := DirectionalLight3D.new()
	root.add_child(light)
	light.look_at_from_position(at, Vector3(0, 0.9, 0))
	light.light_energy = energy
	light.light_specular = specular
	light.shadow_enabled = shadow
	light.directional_shadow_max_distance = 12.0
	return light


## The showroom's studio under the approved Medium preset (godot/showroom/showroom.gd _stage and _apply).
func _stage() -> void:
	root.msaa_3d = Viewport.MSAA_2X
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.80, 0.80, 0.82)
	var sky := Sky.new()
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	var hdri: String = _spec.get("hdri", "")
	var image: Image = Image.load_from_file(hdri) if hdri != "" else null
	if image != null and not image.is_empty():
		var pano := PanoramaSkyMaterial.new()
		pano.panorama = ImageTexture.create_from_image(image)
		sky.sky_material = pano
		_report["sky"] = hdri.get_file()
	else:
		sky.sky_material = ProceduralSkyMaterial.new()
		_report["sky"] = "ProceduralSky"
	env.sky = sky
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 0.9
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_sky_contribution = 0.5
	env.ambient_light_color = Color(1.0, 0.8, 0.62)
	env.ambient_light_energy = 0.12
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.ssao_enabled = true
	env.ssao_radius = 0.6
	env.ssao_intensity = 1.5
	env.ssao_light_affect = 0.2
	var we := WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	for l: Dictionary in LookLights.directional():  # light D since 2026-10-19 (art #196)
		var at: Array = l["at"]
		var aim: Array = l.get("look_at", [0.0, 0.9, 0.0])
		var light := _light(Vector3(at[0], at[1], at[2]), l["energy"], l.get("specular", 0.0), l.get("shadow", false))
		light.look_at_from_position(Vector3(at[0], at[1], at[2]), Vector3(aim[0], aim[1], aim[2]))
	RenderingServer.directional_soft_shadow_filter_set_quality(RenderingServer.SHADOW_QUALITY_SOFT_MEDIUM)
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(40, 40)
	var fm := StandardMaterial3D.new()
	fm.albedo_color = Color(0.66, 0.66, 0.68)
	fm.roughness = 1.0
	plane.material = fm
	floor_mesh.mesh = plane
	root.add_child(floor_mesh)
	_camera = Camera3D.new()
	_camera.near = 0.02
	root.add_child(_camera)
	_camera.make_current()
	var layer := CanvasLayer.new()
	root.add_child(layer)
	_label = Label.new()
	_label.position = Vector2(10, 6)
	_label.add_theme_font_size_override("font_size", 30)
	_label.add_theme_color_override("font_color", Color(0.1, 0.1, 0.12))
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
	for n: String in _player.get_animation_list():
		if n.get_slice("|", n.get_slice_count("|") - 1).to_lower() == word.to_lower():
			return n
	return ""


func _pos(name: String) -> Vector3:
	return (_ch.find_child(name, true, false) as Node3D).global_position


func _combo(e: String, m: String, piece: String = "rest") -> void:
	_rig.set_eyes(e)
	_rig.set_lids("rest")
	_rig.set_mouth_design(m)
	_rig.show_mouth(piece)


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
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
	if idle == "":
		_fail("no Idle clip")
		return
	_player.play(idle)
	_player.seek(0.0, true)
	_player.pause()
	for _i: int in 3:
		await process_frame
	var eye: Vector3 = (_pos("Eye_L") + _pos("Eye_R")) * 0.5
	var mouth: Vector3 = _pos("Mouth")
	var face: Vector3 = (eye + mouth) * 0.5
	_report["eye_centre"] = [eye.x, eye.y, eye.z]
	_report["mouth"] = [mouth.x, mouth.y, mouth.z]
	_report["face_surfaces"] = _rig.face_surface_counts()["face"]
	_report["lid_surfaces"] = _rig.face_surface_counts()["lid"]
	var combos: Array = [["bored", "frog"], ["bored", "overbite"], ["manic", "frog"], ["manic", "overbite"]]
	# 1: compare (first test above, S5 below), 3/4 view
	var imgs: Array = []
	for look: String in ["first", "s5"]:
		_rig.set_face_look(look)
		for c: Array in combos:
			_combo(c[0], c[1])
			_look(face, 22, 2, 0.62, 34)
			imgs.append(await _shot("%s %s+%s" % ["first" if look == "first" else "S5", c[0], c[1]]))
	_sheet(imgs, 4, "compare.png")
	# 2: S5 close, front-ish
	_rig.set_face_look("s5")
	imgs = []
	for c: Array in combos:
		_combo(c[0], c[1])
		_look(face, 12, 4, 0.5, 34)
		imgs.append(await _shot("S5 %s + %s" % [c[0], c[1]]))
	_sheet(imgs, 2, "faces.png")
	# 3: the eyes very close, first and S5
	imgs = []
	for e: String in ["bored", "manic"]:
		for look: String in ["first", "s5"]:
			_rig.set_face_look(look)
			_combo(e, "frog")
			_look(eye, 6, 3, 0.5, 30)
			imgs.append(await _shot("%s %s" % ["first" if look == "first" else "S5", e]))
	_sheet(imgs, 2, "eyes.png")
	_rig.set_face_look("s5")
	# 4: the blink, both designs
	imgs = []
	for e: String in ["bored", "manic"]:
		_combo(e, "frog")
		for t: float in [0.0, 30.0, 60.0, 80.0, 100.0, 125.0, 150.0, 200.0]:
			_rig.blink_at(t)
			_look(eye, 6, 2, 0.42, 34)
			imgs.append(await _shot("%s blink %d ms" % [e, int(t)]))
		_rig.set_lids("rest")
	_sheet(imgs, 4, "blink.png")
	# 5: the six mouth pieces of both designs
	imgs = []
	for m: String in ["frog", "overbite"]:
		for v: String in AlienRig.VISEMES:
			_combo("bored", m, v)
			_look(mouth + Vector3(0, 0.01, 0), 18, 4, 0.36, 34)
			imgs.append(await _shot("%s %s" % [m, v]))
	_sheet(imgs, 4, "talk.png")
	# 6: the hues
	imgs = []
	for h: String in ["teal", "coral", "violet"]:
		_rig.set_hue(h)
		_combo("bored", "frog")
		_look(face, 22, 2, 0.62, 34)
		imgs.append(await _shot("S5 %s" % h))
	_rig.set_hue("teal")
	_sheet(imgs, 3, "hues.png")
	# 7: the tuning grid: the lips' roughness (rows) against their colour (columns), front at 0.5 m
	imgs = []
	var lip: ShaderMaterial = _rig.face_material("alien_lip")  # S9: alien_lip.gdshader
	var col0: Color = lip.get_shader_parameter("albedo")
	var r0: float = lip.get_shader_parameter("roughness_value")
	_combo("bored", "frog")
	for r: float in [0.75, 0.6, 0.45]:
		for c: Color in [Color(0.74, 0.42, 0.38), col0, Color(0.86, 0.57, 0.49)]:
			lip.set_shader_parameter("roughness_value", r)
			lip.set_shader_parameter("albedo", c)
			_look(face, 10, 3, 0.5, 34)
			imgs.append(await _shot("lip rough %.2f  (%.2f %.2f %.2f)" % [r, c.r, c.g, c.b]))
	lip.set_shader_parameter("albedo", col0)
	lip.set_shader_parameter("roughness_value", r0)
	_sheet(imgs, 3, "grid.png")
	var f :=FileAccess.open(_out + "/face_proof.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(_report, " "))
	f.close()
	print("PROOF saved ", _out + "/face_proof.json")
	quit(0)
