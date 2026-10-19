extends SceneTree
## The alien parts kit's second test (art #196, S7): the first test and the two new bodies ("cage" and "wrap") side
## by side under the approved showroom look, in a real window kept off-screen (godot/lib/offscreen.gd, #214; never
## headless, never minimized). A run goes through the runner's _godot.window() (docs/godot.md, "The off-screen
## window") with the arguments
##   --path godot -s res://alien/second_test.gd -- <spec.json>
## The spec: {"scenes": {"first": "res://import/...glb", "cage": ..., "wrap": ...}, "out": "<dir>", "hdri": "<.hdr>"}.
## The stage is face_proof.gd's (the showroom's Medium preset: AgX 0.9, the studio sky, key, fill, rim, SSAO, MSAA 2x).
## Each character gets its own alien.gd; the first test keeps its own materials (set_face_look("first")). Writes into
## <out>: turntable_3m.png (the three side by side, 8 angles), turntable_1m.png (one row per body, 8 angles),
## idle_walk.png (4 Idle and 6 Walk frames, the three side by side), walk_side.png (the Walk from the side at the
## legs and feet, one row per body), faces.png (every eye and mouth combination at 0.6 m, the first test above the
## second), crests.png, blink.png, talk.png (the twelve mouth pieces, front and three-quarter), hues.png (both new
## bodies in the three hues) and second_test.json. Prints PROOF saved <path>, or PROOF error <why> and exits 1.

const Offscreen = preload("res://lib/offscreen.gd")
const AlienRig = preload("res://alien/alien.gd")
const WATCHDOG_S: float = 280.0
const SHEET_W: int = 1280
var _order: Array = ["first", "cage", "wrap"]  # the spec's "order" replaces it (S8: ["s7", "s8"])
const SPACING: float = 0.95

var _spec: Dictionary
var _camera: Camera3D
var _label: Label
var _out: String
var _report: Dictionary = {}
var _ch: Dictionary = {}  # name -> Node3D
var _rig: Dictionary = {}  # name -> alien.gd
var _player: Dictionary = {}  # name -> AnimationPlayer


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
	if not (spec is Dictionary and spec.has("scenes") and spec.has("out")):
		_fail("%s is not a second-test spec" % args[0])
		return
	_spec = spec
	_run()


func _fail(why: String) -> void:
	printerr("PROOF error ", why)
	quit(1)


func _light(at: Vector3, energy: float, specular: float, shadow: bool) -> void:
	var light := DirectionalLight3D.new()
	root.add_child(light)
	light.look_at_from_position(at, Vector3(0, 0.9, 0))
	light.light_energy = energy
	light.light_specular = specular
	light.shadow_enabled = shadow
	light.directional_shadow_max_distance = 12.0


## face_proof.gd's stage: the showroom's studio under the approved Medium preset.
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
	_light(Vector3(-2.0, 3.2, 3.0), 2.0, 0.6, true)
	_light(Vector3(3.0, 1.6, 2.0), 0.12, 0.0, false)
	_light(Vector3(0.5, 2.5, -3.0), 0.3, 0.0, false)
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
	_label.add_theme_font_size_override("font_size", 26)
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
	if images.is_empty():
		_fail("no image for %s" % name)
		return
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


func _clip(p: AnimationPlayer, word: String) -> String:
	for n: String in p.get_animation_list():
		if n.get_slice("|", n.get_slice_count("|") - 1).to_lower() == word.to_lower():
			return n
	return ""


## Every character at the same clip time (seconds; a negative time is that share of the clip).
func _pose(word: String, t: float) -> void:
	for k: String in _ch:
		var p: AnimationPlayer = _player[k]
		var c: String = _clip(p, word)
		if c == "":  # said, not silent (PR #225 review): that character keeps its pose
			print("PROOF warning: %s has no clip matching %s" % [k, word])
			_report.get_or_add("missing_clips", []).append("%s:%s" % [k, word])
			continue
		p.play(c)
		var length: float = p.get_animation(c).length
		p.seek(length * -t if t < 0.0 else t, true)
		p.pause()


## Only the named characters show, at their places (the rest hidden); the others' x places when side by side.
func _only(names: Array, side_by_side: bool) -> void:
	for i: int in _order.size():
		var k: String = _order[i]
		if not _ch.has(k):
			continue
		var n: Node3D = _ch[k]
		n.visible = names.has(k)
		var at: int = names.find(k)
		n.position = Vector3((at - (names.size() - 1) * 0.5) * SPACING if side_by_side and at >= 0 else 0.0, 0, 0)
		n.rotation = Vector3.ZERO


func _spin(names: Array, deg: float) -> void:
	for k: String in names:
		(_ch[k] as Node3D).rotation = Vector3(0, deg_to_rad(deg), 0)


func _find(k: String, name: String) -> Vector3:
	return ((_ch[k] as Node3D).find_child(name, true, false) as Node3D).global_position


## The left hand's middle knuckle in the world (the skeleton's LeftMiddleProximal), for the close hand shots.
func _hand(k: String) -> Vector3:
	var sk: Skeleton3D = (_ch[k] as Node3D).find_child("Skeleton3D", true, false) as Skeleton3D
	var i: int = sk.find_bone("LeftMiddleProximal")
	return sk.global_transform * sk.get_bone_global_pose(i).origin


func _combo(k: String, e: String, m: String, piece: String = "rest") -> void:
	var r: Node = _rig[k]
	r.set_eyes(e)
	r.set_lids("rest")
	r.set_mouth_design(m)
	r.show_mouth(piece)


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	if _spec.has("order"):
		_order = _spec["order"]
	DirAccess.make_dir_recursive_absolute(_out)
	_stage()
	var scenes: Dictionary = _spec["scenes"]
	for k: String in _order:
		if not scenes.has(k):
			continue
		var packed: PackedScene = load(scenes[k]) as PackedScene
		if packed == null:
			_fail("cannot load %s" % scenes[k])
			return
		var ch: Node3D = packed.instantiate()
		root.add_child(ch)
		var rig: Node = AlienRig.new()
		ch.add_child(rig)
		rig.setup(ch)
		rig.auto_blink = false
		if k == "first":
			rig.set_face_look("first")
		rig.set_crest("")
		_ch[k] = ch
		_rig[k] = rig
		_player[k] = ch.find_child("AnimationPlayer", true, false)
		_combo(k, "bored", "frog")
	var all: Array = _order.filter(func(k: String) -> bool: return _ch.has(k))
	_pose("Idle", 0.0)
	for _i: int in 3:
		await process_frame
	var imgs: Array = []
	# 1: the three side by side at 3 m, 8 angles
	_only(all, true)
	for a: float in [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0]:
		_spin(all, a)
		_look(Vector3(0, 0.9, 0), 0, 4, 3.0, 50)
		imgs.append(await _shot("%s  %d deg  3 m" % [" | ".join(all), int(a)]))
	_sheet(imgs, 4, "turntable_3m.png")
	# 2: each body close at 1 m (head to hips), 8 angles, one row each
	imgs = []
	for k: String in all:
		_only([k], false)
		for a: float in [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0]:
			_spin([k], a)
			_look(Vector3(0, 1.38, 0), 0, 2, 1.0, 46)
			imgs.append(await _shot("%s %d" % [k, int(a)]))
	_sheet(imgs, 4, "turntable_1m.png")
	# 3: Idle and Walk, the three side by side, three-quarter at 3.2 m
	imgs = []
	_only(all, true)
	for f: float in [0.0, 0.25, 0.5, 0.75]:
		_pose("Idle", -f)
		_look(Vector3(0, 0.9, 0), 25, 6, 3.2, 50)
		imgs.append(await _shot("Idle %.2f" % f))
	for f: float in [0.0, 0.17, 0.33, 0.5, 0.67, 0.83]:
		_pose("Walk", -f)
		_look(Vector3(0, 0.9, 0), 25, 6, 3.2, 50)
		imgs.append(await _shot("Walk %.2f" % f))
	_sheet(imgs, 5, "idle_walk.png")
	# 4: the Walk from the side, legs and feet, one row per body
	imgs = []
	for k: String in all:
		_only([k], false)
		for f: float in [0.0, 0.25, 0.5, 0.75]:
			_pose("Walk", -f)
			_look(Vector3(0, 0.45, 0), 90, 4, 1.7, 40)
			imgs.append(await _shot("%s Walk %.2f side" % [k, f]))
	_pose("Idle", 0.0)
	_sheet(imgs, 4, "walk_side.png")
	# 5: the faces at 0.6 m, every eye and mouth combination, one row per character in the spec's order (S8b: the
	# old ["first", "cage"] list matched no key of an S8 order ["s7", "s8"], so the sheet had no image)
	var combos: Array = [["bored", "frog"], ["bored", "overbite"], ["manic", "frog"], ["manic", "overbite"]]
	imgs = []
	for k: String in all:
		_only([k], false)
		await process_frame
		var face: Vector3 = ((_find(k, "Eye_L") + _find(k, "Eye_R")) * 0.5 + _find(k, "Mouth")) * 0.5
		for c: Array in combos:
			_combo(k, c[0], c[1])
			_look(face, 20, 2, 0.6, 34)
			imgs.append(await _shot("%s %s+%s" % [k, c[0], c[1]]))
	_sheet(imgs, 4, "faces.png")
	# 5b (S8b): the neck weld at 0.5 m from the side, the back and the three-quarter back, in Idle and in the Talk's
	# head turn, and the left hand at 0.5 m in Idle and Walk; one row per character
	imgs = []
	for k: String in all:
		_only([k], false)
		for pose: Array in [["Idle", 0.0], ["Talk", -0.5]]:
			_pose(pose[0], pose[1])
			await process_frame
			for yaw: float in [90.0, 180.0, 225.0]:
				_look(Vector3(0, 1.40, 0), yaw, 4, 0.5, 40)
				imgs.append(await _shot("%s %s neck %d" % [k, pose[0], int(yaw)]))
		for pose: Array in [["Idle", 0.0], ["Walk", -0.25], ["Walk", -0.75]]:
			_pose(pose[0], pose[1])
			await process_frame
			var hand: Vector3 = _hand(k)
			_look(hand, 60, 10, 0.5, 40)
			imgs.append(await _shot("%s %s %.2f hand" % [k, pose[0], pose[1]]))
	_pose("Idle", 0.0)
	_sheet(imgs, 3, "neck_hands.png")
	# 6: the crests (second test), front three-quarter and side
	var k2: String = "cage" if _ch.has("cage") else all[-1]
	_only([k2], false)
	await process_frame
	var head: Vector3 = (_find(k2, "Eye_L") + _find(k2, "Eye_R")) * 0.5 + Vector3(0, 0.03, 0)
	imgs = []
	_combo(k2, "bored", "frog")
	for cr: String in ["", "antennae", "fins"]:
		_rig[k2].set_crest(cr)
		for yaw: float in [25.0, 90.0]:
			_look(head, yaw, 6, 0.75, 34)
			imgs.append(await _shot("crest %s %d" % [cr if cr != "" else "none", int(yaw)]))
	_rig[k2].set_crest("")
	_sheet(imgs, 3, "crests.png")
	# 7: the blink, both designs (second test)
	var eye: Vector3 = (_find(k2, "Eye_L") + _find(k2, "Eye_R")) * 0.5
	imgs = []
	for e: String in ["bored", "manic"]:
		_combo(k2, e, "frog")
		for t: float in [0.0, 30.0, 60.0, 80.0, 100.0, 125.0, 150.0, 200.0]:
			_rig[k2].blink_at(t)
			_look(eye, 8, 2, 0.42, 34)
			imgs.append(await _shot("%s blink %d ms" % [e, int(t)]))
		_rig[k2].set_lids("rest")
	_sheet(imgs, 4, "blink.png")
	# 8: the twelve mouth pieces (second test), front and three-quarter
	var mouth: Vector3 = _find(k2, "Mouth")
	for view: Array in [["talk.png", 0.0, 0.34], ["talk_34.png", 38.0, 0.40]]:
		imgs = []
		for m: String in ["frog", "overbite"]:
			for v: String in AlienRig.VISEMES:
				_combo(k2, "bored", m, v)
				_look(mouth + Vector3(0, 0.015, 0), view[1], 3, view[2], 34)
				imgs.append(await _shot("%s %s" % [m, v]))
		_sheet(imgs, 6, view[0])
	_combo(k2, "bored", "frog")
	# 9: the hues on both new bodies, front three-quarter at 2.4 m
	imgs = []
	var new: Array = all.filter(func(k: String) -> bool: return k != "first")
	_only(new, true)
	for h: String in ["teal", "coral", "violet"]:
		for k: String in new:
			_rig[k].set_hue(h)
		for yaw: float in [20.0, 160.0]:
			_look(Vector3(0, 0.95, 0), yaw, 5, 2.6, 50)
			imgs.append(await _shot("%s  %s  %d" % [" | ".join(new), h, int(yaw)]))
	_sheet(imgs, 2, "hues.png")
	_report["characters"] = all
	var f := FileAccess.open(_out + "/second_test.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(_report, " "))
	f.close()
	print("PROOF saved ", _out + "/second_test.json")
	quit(0)
