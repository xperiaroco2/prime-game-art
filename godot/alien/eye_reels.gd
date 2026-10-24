extends "res://alien/char_shots.gd"
## The bare aliens' eyes on the body (art #196, A3), in the runner's off-screen window; tools/blender/alien_clip_run.py
## --eyes writes the job (clip_reels.gd's, plus "eye_modes"). Per head:
## - rim_<head>.jpg: the lower rim of each eye close (orthographic, RIM_SIZE high: 0.14 m since A3b, from the eye's front a little below),
##   rows the gaze at rest, down, to the head's left and right (eye_mode "free", the head held), each eye; columns as
##   built | albedo only | geometry only | SSAO off | the eye mask's share (debug_mode 0, 3, 2, 0, 7);
##   rim_<head>_4x/<row>_<eye>.png: the as-built and SSAO-off cells at 4x (the window's pixels, nearest);
## - <frames>/<head>_look_<mode>/0000.png...: per eye mode (fixed, lead) 8 s at 24 fps of the same scripted look-around (a
##   player turning their camera: yaw +-40, pitch +-15, holds), Idle underneath, head and shoulders, 1280x720;
## - <frames>/<head>_look_side/0000.png...: the two modes side by side (fixed | lead), the middle 640 px of each;
## eyes.json: per head and mode the eyes' largest and mean turn off the head's forward (degrees).
## Args after "--": <job.json>

const Char = preload("res://lib/character.gd")
const RIM_CELL := Vector2i(256, 192)
const RIM_SIZE := 0.14  # m: the rim close-up's height (A3's 0.09 cut the eye off)
const LOOK := Vector2i(1280, 720)
const LOOK_S := 8.0
## the look-around's keys: (time s, yaw deg toward +X, pitch deg up); smoothstep between, so the holds stay still
const KEYS := [[0.0, 0.0, 0.0], [0.6, 0.0, 0.0], [1.2, 40.0, 0.0], [2.2, 40.0, 0.0], [3.0, -40.0, 8.0],
	[4.0, -40.0, 8.0], [4.6, -10.0, -15.0], [5.4, -10.0, -15.0], [6.0, 25.0, 15.0], [6.8, 25.0, 15.0], [7.4, 0.0, 0.0],
	[8.0, 0.0, 0.0]]
const GAZES := [["rest", Vector3(0.0, 0.0, 3.0)], ["down", Vector3(0.0, -2.5, 2.0)], ["left", Vector3(3.0, 0.0, 2.0)],
	["right", Vector3(-3.0, 0.0, 2.0)]]


func _run() -> void:
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	var out: String = job["sheet_out"]
	_stage(job["hdri"])
	_apply_fix(job.get("fix", {}))
	var report := {}
	for name: String in (job["heads"] as Dictionary):
		var h: Dictionary = job["heads"][name]
		var ch: Node3D = (load(h["char"]) as PackedScene).instantiate()
		root.add_child(ch)
		var lively: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(h["lively"]))
		var mats := _setup(ch, h, true)
		var live = Lively.new(ch, mats, lively, _texture(h["sclera"]))
		var sk: Skeleton3D = ch.find_children("*", "Skeleton3D", true, false)[0]
		var ap: AnimationPlayer = _anim(ch)
		var mid: Vector3 = (Lively._v(lively["eyes"]["left"]["centre"]) + Lively._v(lively["eyes"]["right"]["centre"])) * 0.5
		var rep := {}
		# the rim close-ups: the rest skeleton (no clip), the head held, the eyes free
		live.on_clip = false
		live.head_follow = 0.0
		live.breathing = 0.0
		live.eye_mode = "free"
		var cells: Array[Image] = []
		var crops := out.path_join("rim_%s_4x" % name)
		DirAccess.make_dir_recursive_absolute(crops)
		for g: Array in GAZES:
			live.target = sk.global_transform * (mid + (g[1] as Vector3))
			for i: int in 30:
				live.step(1.0 / 24.0)
			for side: String in ["right", "left"]:
				var e: Dictionary = lively["eyes"][side]
				var to_world: Transform3D = live.mesh.global_transform
				var front: Vector3 = to_world * live.eye_front(side)
				var fwd: Vector3 = (to_world.basis * Lively._v(e["rest"])).normalized()
				var lower: Vector3 = front - Vector3(0.0, float(e["radius"]) * 0.45, 0.0)
				_cam.projection = Camera3D.PROJECTION_ORTHOGONAL
				_cam.size = RIM_SIZE
				_cam.position = lower + (fwd + Vector3(0.0, -0.35, 0.0)).normalized() * 1.0
				_cam.look_at(lower)
				for col: int in 5:
					for sm: ShaderMaterial in mats:
						sm.set_shader_parameter("debug_mode", [0, 3, 2, 0, 7][col])
					_env.ssao_enabled = col != 3
					var img: Image = await _grab(RIM_CELL)
					cells.append(img)
					if col == 0 or col == 3:
						var big: Image = root.get_texture().get_image()
						big.convert(Image.FORMAT_RGB8)
						var w: int = big.get_width() / 4
						var hh: int = big.get_height() / 4
						var z: Image = big.get_region(Rect2i((big.get_width() - w) / 2, (big.get_height() - hh) / 2, w, hh))
						z.resize(w * 4, hh * 4, Image.INTERPOLATE_NEAREST)
						z.save_png(crops.path_join("%s_%s_%s.png" % [g[0], side, "built" if col == 0 else "no_ssao"]))
				for sm: ShaderMaterial in mats:
					sm.set_shader_parameter("debug_mode", 0)
				_env.ssao_enabled = true
		_sheet(cells, RIM_CELL, 5).save_jpg(out.path_join("rim_%s.jpg" % name), 0.92)
		_cam.projection = Camera3D.PROJECTION_PERSPECTIVE
		# the look-around per eye mode, Idle underneath
		live.on_clip = true
		live.head_follow = 1.0
		live.breathing = 1.0
		live.darts = 0.0
		live.yaw_counter = 0.0
		var length: float = ap.current_animation_length if ap != null else 1.0
		for mode: String in (job.get("eye_modes", ["fixed", "lead"]) as Array):
			live.eye_mode = mode
			live.reset_motion()
			live.reset_springs()
			live.reset_eyes()  # A3b: the rim pass left the eyes turned (fixed's first frames settled from it)
			live.reseed()
			var dir := String(job["frames"]).path_join("%s_look_%s" % [name, mode])
			DirAccess.make_dir_recursive_absolute(dir)
			var off_max := 0.0
			var off_sum := 0.0
			var n: int = int(LOOK_S * FPS)
			for i: int in n:
				var t: float = i / FPS
				var yp: Vector2 = look_at_time(t)
				var d := Vector3(sin(deg_to_rad(yp.x)) * cos(deg_to_rad(yp.y)), sin(deg_to_rad(yp.y)),
					cos(deg_to_rad(yp.x)) * cos(deg_to_rad(yp.y)))
				live.target = sk.global_transform * (mid + d * 2.5)
				if ap != null:
					ap.seek(fmod(t, length), true)
				live.step(1.0 / FPS)
				var off := 0.0
				for side: String in ["left", "right"]:
					var s: Vector4 = live._eye[side]
					off = maxf(off, rad_to_deg(Vector2(s.x, s.y).length()))
				off_max = maxf(off_max, off)
				off_sum += off
				var head: Vector3 = sk.global_transform * sk.get_bone_global_pose(sk.find_bone("Head")).origin
				var img: Image = await _look_frame(head + Vector3(0.0, 0.02, 0.0))
				img.save_png(dir.path_join("%04d.png" % i))
			rep[mode] = {"eye_off_head_max_deg": snappedf(off_max, 0.01), "eye_off_head_mean_deg": snappedf(off_sum / n, 0.01)}
			print("EYES %s %s %s" % [name, mode, JSON.stringify(rep[mode])])
		var side_dir := String(job["frames"]).path_join("%s_look_side" % name)
		DirAccess.make_dir_recursive_absolute(side_dir)
		for i: int in int(LOOK_S * FPS):
			var both := Image.create(LOOK.x, LOOK.y, false, Image.FORMAT_RGB8)
			for j: int in 2:
				var m: String = ["fixed", "lead"][j]
				var img: Image = Image.load_from_file(String(job["frames"]).path_join("%s_look_%s/%04d.png" % [name, m, i]))
				img.convert(Image.FORMAT_RGB8)
				both.blit_rect(img, Rect2i(LOOK.x / 4, 0, LOOK.x / 2, LOOK.y), Vector2i(j * LOOK.x / 2, 0))
			both.fill_rect(Rect2i(LOOK.x / 2 - 1, 0, 2, LOOK.y), Color(0.1, 0.1, 0.1))
			both.save_png(side_dir.path_join("%04d.png" % i))
		report[name] = rep
		ch.queue_free()
		await process_frame
	var f := FileAccess.open(out.path_join("eyes.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, " "))
	f.close()
	print("EYES done")
	quit(0)


## The look-around's (yaw, pitch) in degrees at t (KEYS, smoothstep between keys).
static func look_at_time(t: float) -> Vector2:
	for k: int in range(1, KEYS.size()):
		if t <= float(KEYS[k][0]):
			var a: Array = KEYS[k - 1]
			var b: Array = KEYS[k]
			var u: float = smoothstep(0.0, 1.0, (t - float(a[0])) / maxf(1e-6, float(b[0]) - float(a[0])))
			return Vector2(lerpf(a[1], b[1], u), lerpf(a[2], b[2], u))
	return Vector2.ZERO


func _look_frame(c: Vector3) -> Image:
	var yaw := deg_to_rad(15.0)
	var h := 0.55
	var dist: float = h * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
	_cam.position = c + Vector3(sin(yaw), 0.05, cos(yaw)).normalized() * dist
	_cam.look_at(c)
	await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	if img.get_size() != LOOK:
		img.resize(LOOK.x, LOOK.y, Image.INTERPOLATE_LANCZOS)
	return img
