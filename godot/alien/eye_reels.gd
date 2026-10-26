extends "res://alien/char_shots.gd"
## The bare aliens' eyes on the body (art #196, A3), in the runner's off-screen window; tools/blender/alien_clip_run.py
## --eyes writes the job (clip_reels.gd's, plus "eye_modes"). Per head:
## - rim_<head>.jpg: the lower rim of each eye close (orthographic, RIM_SIZE high: 0.14 m since A3b, from the eye's front a little below),
##   rows the gaze at rest, down, to the head's left and right (eye_mode "free", the head held), each eye; columns as
##   (A3c) before (A3b's look: the painted limbal on) | built | the rim rule's trial | albedo only | geometry only |
##   SSAO off | the rim rule's map (debug_mode 8: R off the sphere over rim_band, G its eye share, B the mask's);
##   rim_<head>_4x/<row>_<eye>_{before,after}.png: the first two cells at 4x round the lower rim (nearest);
## - rings_<head>.jpg (A3c): each eye front on at rest, A3b's look (gaze_limbal 1) | as built | limbal 0 | eye_coat 0 | sclera_normal_map 0 |
##   normal_strength 0 | the mask's G | the detail's A | the normal map's tilt (debug_mode 9, 10, 11);
## - <frames>/<head>_look_<mode>/0000.png...: per eye mode (fixed, lead) 8 s at 24 fps of the same scripted look-around (a
##   player turning their camera: yaw +-40, pitch +-15, holds), Idle underneath, head and shoulders, 1280x720;
## - <frames>/<head>_look_side/0000.png...: the two modes side by side (fixed | lead), the middle 640 px of each;
## - corner_<head>.jpg (R2b): each eye's outer corner at rest (the eye's side away from the head's middle), rows
##   front, three-quarters (CORNER_VIEWS degrees toward the outer side), side, each eye; columns as built | albedo only |
##   geometry only | SSAO off | the key light's shadow off | the eye mask's share (debug_mode 7);
##   corner_<head>_4x/<view>_<eye>.png: the as-built cell at 4x round the corner (nearest);
## - spots_<head>.jpg (E2, only with the job's "spots": per head [label, [x, y, z] in the character mesh's space]):
##   each spot at rest from the front, both three-quarters (SPOT_VIEWS), below and above, as built, the spot at each
##   cell's centre; spots_<head>_4x/<label>_<view>.png: the cell at 4x round the spot (nearest);
## eyes.json: per head and mode the eyes' largest and mean turn off the head's forward (degrees).
## Args after "--": <job.json>

const Char = preload("res://lib/character.gd")
const RIM_CELL := Vector2i(256, 192)
const RIM_SIZE := 0.14  # m: the rim close-up's height (A3's 0.09 cut the eye off)
## A3c: the rim sheet's columns: [debug_mode, the rim rule, gaze_limbal]; the first A3b's look (the before), the second
## as built (the after), the third the rim rule's trial, the sixth SSAO off
const RIM_COLS := [[0, false, 1.0], [0, false, 0.0], [0, true, 0.0], [3, false, 0.0], [2, false, 0.0], [0, false, 0.0],
	[8, true, 0.0]]
const CROP_Y := 0.8  # the 4x crops' middle, down the window (the lower rim; A3b's centre crops missed it)
const RING_SIZE := 0.06  # m: the rings' close-up height, the eye front on
## the rings' isolation (A3c): one shader parameter per column, as built first
const RING_COLS := [["gaze_limbal", 1.0], ["debug_mode", 0], ["limbal", 0.0], ["eye_coat", 0.0], ["sclera_normal_map", 0.0],
	["normal_strength", 0.0], ["debug_mode", 9], ["debug_mode", 10], ["debug_mode", 11]]
## R2b: the outer corner's isolation: [debug_mode, SSAO, the key light's shadow], as built first
const CORNER_COLS := [[0, true, true], [3, true, true], [2, true, true], [0, false, true], [0, true, false], [7, true, true]]
const CORNER_VIEWS := [["front", 0.0], ["q", 40.0], ["side", 75.0]]  # degrees from the eye's front toward its outer side
## E2: the spots' views: [name, yaw degrees from the head's forward toward +X, pitch degrees up]
const SPOT_VIEWS := [["front", 0.0, 0.0], ["q_pos_x", 40.0, 0.0], ["q_neg_x", -40.0, 0.0], ["below", 0.0, -25.0],
	["above", 0.0, 25.0]]
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
		var rings: Array[Image] = []
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
				for col: int in RIM_COLS.size():
					live.rim_rule = RIM_COLS[col][1]
					live._apply_eyes()
					for sm: ShaderMaterial in mats:
						sm.set_shader_parameter("debug_mode", RIM_COLS[col][0])
						sm.set_shader_parameter("gaze_limbal", RIM_COLS[col][2])
					_env.ssao_enabled = col != 5
					var img: Image = await _grab(RIM_CELL)
					cells.append(img)
					if col <= 1:
						var big: Image = root.get_texture().get_image()
						big.convert(Image.FORMAT_RGB8)
						var w: int = big.get_width() / 4
						var hh: int = big.get_height() / 4
						var cy: int = int(big.get_height() * CROP_Y) - hh / 2
						var z: Image = big.get_region(Rect2i((big.get_width() - w) / 2, cy, w, hh))
						z.resize(w * 4, hh * 4, Image.INTERPOLATE_NEAREST)
						z.save_png(crops.path_join("%s_%s_%s.png" % [g[0], side, "before" if col == 0 else "after"]))
				for sm: ShaderMaterial in mats:
					sm.set_shader_parameter("debug_mode", 0)
					sm.set_shader_parameter("gaze_limbal", 0.0)
				live.rim_rule = false
				live._apply_eyes()
				_env.ssao_enabled = true
				if g[0] == "rest":
					# A3c: the rings' isolation, the eye front on
					_cam.size = RING_SIZE
					_cam.position = front + fwd * 1.0
					_cam.look_at(front)
					for col: int in RING_COLS.size():
						var tweak: Array = RING_COLS[col]
						var keep := []
						for sm: ShaderMaterial in mats:
							keep.append(sm.get_shader_parameter(tweak[0]))
							sm.set_shader_parameter(tweak[0], tweak[1])
						rings.append(await _grab(RIM_CELL))
						for k: int in mats.size():
							mats[k].set_shader_parameter(tweak[0], keep[k])
					_cam.size = RIM_SIZE
		# R2b: the outer corner (the dark wedge between lid and sclera), the gaze at rest
		live.target = sk.global_transform * (mid + (GAZES[0][1] as Vector3))
		for i: int in 30:
			live.step(1.0 / 24.0)
		var corner_cells: Array[Image] = []
		var corner_crops := out.path_join("corner_%s_4x" % name)
		DirAccess.make_dir_recursive_absolute(corner_crops)
		var mid_w: Vector3 = live.mesh.global_transform * mid
		for v: Array in CORNER_VIEWS:
			for side: String in ["right", "left"]:
				var e: Dictionary = lively["eyes"][side]
				var to_world: Transform3D = live.mesh.global_transform
				var centre: Vector3 = to_world * Lively._v(e["centre"])
				var fwd: Vector3 = (to_world.basis * Lively._v(e["rest"])).normalized()
				var out_dir: Vector3 = centre - mid_w
				out_dir.y = 0.0
				out_dir = (out_dir - fwd * out_dir.dot(fwd)).normalized()  # the outer side, across the eye's front
				var corner: Vector3 = to_world * live.eye_front(side) + out_dir * float(e["radius"]) * 0.75
				var view_dir: Vector3 = fwd * cos(deg_to_rad(float(v[1]))) + out_dir * sin(deg_to_rad(float(v[1])))
				_cam.projection = Camera3D.PROJECTION_ORTHOGONAL
				_cam.size = RIM_SIZE
				_cam.position = corner + view_dir.normalized() * 1.0
				_cam.look_at(corner)
				for col: int in CORNER_COLS.size():
					for sm: ShaderMaterial in mats:
						sm.set_shader_parameter("debug_mode", CORNER_COLS[col][0])
					_env.ssao_enabled = CORNER_COLS[col][1]
					_key.shadow_enabled = CORNER_COLS[col][2]
					corner_cells.append(await _grab(RIM_CELL))
					if col == 0:
						var big: Image = root.get_texture().get_image()
						big.convert(Image.FORMAT_RGB8)
						var w: int = big.get_width() / 4
						var hh: int = big.get_height() / 4
						var z: Image = big.get_region(Rect2i((big.get_width() - w) / 2, (big.get_height() - hh) / 2, w, hh))
						z.resize(w * 4, hh * 4, Image.INTERPOLATE_NEAREST)
						z.save_png(corner_crops.path_join("%s_%s.png" % [v[0], side]))
				for sm: ShaderMaterial in mats:
					sm.set_shader_parameter("debug_mode", 0)
				_env.ssao_enabled = true
				_key.shadow_enabled = true
		_sheet(corner_cells, RIM_CELL, CORNER_COLS.size()).save_jpg(out.path_join("corner_%s.jpg" % name), 0.92)
		_sheet(rings, RIM_CELL, RING_COLS.size()).save_jpg(out.path_join("rings_%s.jpg" % name), 0.92)
		_sheet(cells, RIM_CELL, RIM_COLS.size()).save_jpg(out.path_join("rim_%s.jpg" % name), 0.92)
		# E2: the job's spots (an eyeball-class stray off the eye), each from the game's angles, the gaze at rest
		var spots: Array = (job.get("spots", {}) as Dictionary).get(name, [])
		if not spots.is_empty():
			var spot_cells: Array[Image] = []
			var spot_crops := out.path_join("spots_%s_4x" % name)
			DirAccess.make_dir_recursive_absolute(spot_crops)
			var tw: Transform3D = live.mesh.global_transform
			var f0: Vector3 = tw.basis * (Lively._v(lively["eyes"]["left"]["rest"]) + Lively._v(lively["eyes"]["right"]["rest"]))
			f0.y = 0.0
			f0 = f0.normalized()
			for sp: Array in spots:
				var at: Vector3 = tw * Vector3(float(sp[1][0]), float(sp[1][1]), float(sp[1][2]))
				for v: Array in SPOT_VIEWS:
					var d: Vector3 = f0.rotated(Vector3.UP, deg_to_rad(float(v[1])))
					d = (d * cos(deg_to_rad(float(v[2]))) + Vector3.UP * sin(deg_to_rad(float(v[2])))).normalized()
					_cam.projection = Camera3D.PROJECTION_ORTHOGONAL
					_cam.size = RIM_SIZE
					_cam.position = at + d * 1.0
					_cam.look_at(at)
					spot_cells.append(await _grab(RIM_CELL))
					var big: Image = root.get_texture().get_image()
					big.convert(Image.FORMAT_RGB8)
					var w: int = big.get_width() / 4
					var hh: int = big.get_height() / 4
					var z: Image = big.get_region(Rect2i((big.get_width() - w) / 2, (big.get_height() - hh) / 2, w, hh))
					z.resize(w * 4, hh * 4, Image.INTERPOLATE_NEAREST)
					z.save_png(spot_crops.path_join("%s_%s.png" % [sp[0], v[0]]))
			_sheet(spot_cells, RIM_CELL, SPOT_VIEWS.size()).save_jpg(out.path_join("spots_%s.jpg" % name), 0.92)
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
