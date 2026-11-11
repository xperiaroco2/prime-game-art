extends SceneTree
## The first-person hands' review frames (art#136, prime-game#1587) in an off-screen window (the runner's
## _godot.window(); tools/blender/fp_hands_run.py stages a copy of the ship package with the hands, the crystal and
## this script, and calls it). The hands GLB goes under the Camera3D with no offset, as the game will put it; the
## energy crystal (its GLB with crystal.gd's look, charged) goes under the hands' CrystalSocket, its tip at the
## socket. The camera stands in the ship's hall at eye height (1.6 m over the floor) with the game's lens (75 degrees
## vertical). For each clip of the request: its frames as PNGs at the request's fps into OUT/<clip>/, played `cycles`
## times; then OUT/check.json: per clip the socket's place in the camera's space at its first frame, the morph
## `fist`'s weight at the hit, the loop mode, and the GPU ms of a held frame.
## Args after "--": <request.json>

const Offscreen = preload("res://lib/offscreen.gd")
const Crystal = preload("res://crystal/crystal.gd")

var _req: Dictionary
var _cam: Camera3D
var _player: AnimationPlayer
var _arms: MeshInstance3D
var _socket: Node3D


func _initialize() -> void:
	var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
	if placed != "":
		printerr(placed)
		quit(2)
		return
	_run.call_deferred()


func _run() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	_req = JSON.parse_string(FileAccess.get_file_as_string(a[0]))
	var out: String = _req["out"]
	root.msaa_3d = Viewport.MSAA_4X
	var ship: Node = (load(_req["scene"]) as PackedScene).instantiate()
	root.add_child(ship)
	_cam = Camera3D.new()
	_cam.fov = float(_req["fov"])
	_cam.near = 0.05
	_cam.far = 500.0
	root.add_child(_cam)
	_cam.make_current()
	_cam.look_at_from_position(_v(_req["eye"]), _v(_req["look"]), Vector3.UP)
	var hands: Node3D = (load(_req["hands"]) as PackedScene).instantiate()
	_cam.add_child(hands)
	_player = hands.find_child("AnimationPlayer", true, false) as AnimationPlayer
	_socket = hands.find_child("CrystalSocket", true, false) as Node3D
	_arms = hands.find_child("FPArms", true, false) as MeshInstance3D
	if _player == null or _socket == null or _arms == null:
		_fail("the hands lack AnimationPlayer %s, CrystalSocket %s or FPArms %s" % [_player, _socket, _arms])
		return
	var crystal: Node3D = (load(_req["crystal"]) as PackedScene).instantiate()
	_socket.add_child(crystal)
	var look: Dictionary = Crystal.apply(crystal)
	Crystal.set_charge(look, 1.0)
	var check: Dictionary = {"socket_parent": _socket.get_parent().get_class(), "animations": Array(_player.get_animation_list()), "clips": {}}
	var vp: RID = root.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	for w: int in 60:  # warm up: shaders compiled and the exposure settled before the first frame is kept
		await process_frame
	for c: Dictionary in _req["clips"]:
		var name: String = c["name"]
		if not _player.has_animation(name):
			_fail("no animation %s" % name)
			return
		var anim: Animation = _player.get_animation(name)
		crystal.visible = bool(c["crystal"])
		var info: Dictionary = {"length": anim.length, "loop": anim.loop_mode}
		_player.play(name)
		_player.seek(0.0, true)
		_player.pause()
		await process_frame
		info["socket"] = _xf(_cam.global_transform.affine_inverse() * _socket.global_transform)
		if c.has("hit") and c["hit"] != null:
			_player.seek(float(c["hit"]), true)
			await process_frame
			info["fist_at_hit"] = _arms.get_blend_shape_value(0) if _arms.get_blend_shape_count() > 0 else -1.0
		var dir: String = out.path_join(name)
		DirAccess.make_dir_recursive_absolute(dir)
		var fps: float = float(_req["fps"])
		var n: int = int(round(anim.length * fps))
		var k: int = 0
		var gpu: float = 0.0
		for cycle: int in int(c.get("cycles", 1)):
			for i: int in n:
				_player.seek(float(i) / fps, true)
				for w: int in 2:
					await process_frame
				await RenderingServer.frame_post_draw
				gpu += RenderingServer.viewport_get_measured_render_time_gpu(vp)
				var img: Image = root.get_texture().get_image()
				img.convert(Image.FORMAT_RGB8)
				img.save_png(dir.path_join("%04d.png" % k))
				k += 1
		info["frames"] = k
		info["gpu_ms"] = snappedf(gpu / maxf(k, 1), 0.01)
		check["clips"][name] = info
		print("FPHANDS %s %d frames" % [name, k])
	# the crystal's own light on the hands (crystal.gd's omni, a holder may lower it): Crystal_Idle's first frame
	# at each level of the request, for the look question
	if _req.has("light_levels"):
		crystal.visible = true
		_player.play("Crystal_Idle")
		_player.seek(0.0, true)
		_player.pause()
		for level: float in _req["light_levels"]:
			look["omni_energy"] = Crystal.OMNI_ENERGY * level
			Crystal.set_charge(look, 1.0)
			for w: int in 8:
				await process_frame
			await RenderingServer.frame_post_draw
			var still: Image = root.get_texture().get_image()
			still.convert(Image.FORMAT_RGB8)
			still.save_png(out.path_join("light_%03d.png" % int(round(level * 100))))
	var f: FileAccess = FileAccess.open(out.path_join("check.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(check, " "))
	f.close()
	quit(0)


func _xf(t: Transform3D) -> Dictionary:
	return {"origin": [t.origin.x, t.origin.y, t.origin.z], "x": [t.basis.x.x, t.basis.x.y, t.basis.x.z],
		"y": [t.basis.y.x, t.basis.y.y, t.basis.y.z], "z": [t.basis.z.x, t.basis.z.y, t.basis.z.z]}


func _v(a: Variant) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))


func _fail(why: String) -> void:
	printerr("FPHANDS error %s" % why)
	quit(1)
