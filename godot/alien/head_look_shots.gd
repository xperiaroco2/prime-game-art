extends "res://alien/char_shots.gd"
## The head-look proof's pictures (art #196, H1): tools/blender/alien_headlook_run.py --shots writes the job (the
## head's entry as char_shots.gd's) and runs this in the runner's off-screen window with --fixed-fps 24. The modifier
## (head_look.gd) on the character's skeleton, the character held in place (the hips' travel taken off its node):
## - <out>/grid_<clip>.png (Idle, Jog_Fwd): yaw -70/-35/0/+35/+70 across x pitch +40/0/-50 down, the upper body from
##   the three-quarter (front-left), 5x3 cells of 256x340;
## - <out>/extremes_<variant>.png: the clamps' corners and edges (8 poses) on Idle, close on the neck from the front
##   and from the character's left, 4x4 cells of 320x320; per entry of the job's "variants" ({name, set: the
##   modifier's properties}, default one "r1": its own defaults);
## - <frames>/<reel>/0000.png... (1280x720, 24 fps) and <out>/<reel>.png (8 key frames): nod_<clip> (pitch +-20 deg
##   at 2 Hz) and shake_<clip> (yaw +-30 deg at 2 Hz) on Idle, Jog_Fwd and Strafe_Left, the aim smoothed with
##   SMOOTH_S as the modifier would; lag_dz45 and lag_dz60 on Idle: the aim (yellow) sweeping 0 to +120 deg and back,
##   the body (blue) kept by head_look.gd's body_follow() within the dead zone (grey edges), the head covering the
##   difference (the aim unsmoothed: body_follow keeps the head inside the dead zone);
## - <out>/shots.json: per sheet and reel what it shows. Args after "--": <job.json>

const HeadLook = preload("res://alien/head_look.gd")
const YAWS := [-70.0, -35.0, 0.0, 35.0, 70.0]
const PITCHES := [40.0, 0.0, -50.0]
const EXTREMES := [[-70.0, -50.0], [70.0, -50.0], [-70.0, 40.0], [70.0, 40.0], [0.0, -50.0], [0.0, 40.0],
	[70.0, 0.0], [-70.0, 0.0]]
const GRID_CELL := Vector2i(256, 340)
const CLOSE_CELL := Vector2i(320, 320)
const KEY_CROP := Vector2i(400, 720)
const KEY_CELL := Vector2i(160, 288)
const SMOOTH_S := 0.05
const GESTURE_S := 3.0
const LAG_S := 6.0

var _ch: Node3D
var _sk: Skeleton3D
var _ap: AnimationPlayer
var _m: SkeletonModifier3D
var _names := {}
var _label: Label
var _lines := {}


func _run() -> void:
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	_stage(job["hdri"])
	_apply_fix(job.get("fix", {}))
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(30.0, 30.0)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.5, 0.51, 0.53)
	gm.roughness = 0.9
	plane.material = gm
	ground.mesh = plane
	root.add_child(ground)
	var h: Dictionary = job["head"]
	_ch = (load(h["char"]) as PackedScene).instantiate()
	root.add_child(_ch)
	_setup(_ch, h, true)
	_sk = _ch.find_children("*", "Skeleton3D", true, false)[0]
	_ap = _ch.find_children("*", "AnimationPlayer", true, false)[0]
	_ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	for n: String in _ap.get_animation_list():
		_names[n.get_slice("|", n.get_slice_count("|") - 1).trim_suffix("_Loop")] = n
	_m = HeadLook.new()
	_m.smoothing_s = 0.0
	_sk.add_child(_m)
	var ui := CanvasLayer.new()
	root.add_child(ui)
	_label = Label.new()
	_label.add_theme_font_size_override("font_size", 18)
	_label.add_theme_color_override("font_color", Color.WHITE)
	_label.add_theme_color_override("font_outline_color", Color.BLACK)
	_label.add_theme_constant_override("outline_size", 4)
	ui.add_child(_label)
	for k: String in ["aim", "body", "edge_a", "edge_b"]:
		_lines[k] = _floor_line({"aim": Color(1.0, 0.85, 0.1), "body": Color(0.25, 0.55, 1.0)}.get(k,
			Color(0.75, 0.75, 0.75)), 0.03 if k in ["aim", "body"] else 0.012)
	_show_lines(false)
	_cam.projection = Camera3D.PROJECTION_PERSPECTIVE
	_cam.fov = 30.0
	var report := {"char": h["char"]}
	_m.pitch_down_deg = 50.0  # the grids show the brief's range, past the recommended clamp of 35 down
	for clip: String in ["Idle", "Jog_Fwd"]:
		report["grid_" + clip] = await _grid(clip, job["out"])
	_m.pitch_down_deg = 35.0
	for v: Dictionary in job.get("variants", [{"name": "r1"}]):
		var keep := {}
		for k: String in v.get("set", {}):
			keep[k] = _m.get(k)
			_m.set(k, v["set"][k])
		report["extremes_" + v["name"]] = await _extremes(job["out"], v["name"])
		for k: String in keep:
			_m.set(k, keep[k])
	if job.get("video", true):
		for clip: String in ["Idle", "Jog_Fwd", "Strafe_Left"]:
			for g: String in ["nod", "shake"]:
				report["%s_%s" % [g, clip]] = await _reel("%s_%s" % [g, clip], clip, g, 0.0, job)
		for dz: float in [45.0, 60.0]:
			report["lag_dz%d" % int(dz)] = await _reel("lag_dz%d" % int(dz), "Idle", "lag", dz, job)
	FileAccess.open(job["out"].path_join("shots.json"), FileAccess.WRITE).store_string(JSON.stringify(report, " "))
	quit(0)


func _floor_line(c: Color, w: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var b := BoxMesh.new()
	b.size = Vector3(w, 0.004, 1.3)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = c
	b.material = m
	mi.mesh = b
	root.add_child(mi)
	return mi


func _show_lines(on: bool) -> void:
	for k: String in _lines:
		(_lines[k] as Node3D).visible = on


## A floor line from the origin toward a world yaw (radians; 0 = +Z, + toward +X).
func _point_line(k: String, yaw: float) -> void:
	var mi: MeshInstance3D = _lines[k]
	mi.rotation = Vector3(0.0, yaw, 0.0)
	mi.position = Vector3(sin(yaw), 0.0, cos(yaw)) * 0.65 + Vector3(0.0, 0.004 if k in ["aim", "body"] else 0.003, 0.0)


func _bone_at(b: String) -> Vector3:
	return _sk.global_transform * _sk.get_bone_global_pose(_sk.find_bone(b)).origin


## The clip at time t (looped), the body at yaw (radians), the aim (degrees, relative to the body), held in place.
func _pose(clip: String, t: float, body_yaw: float, yaw_deg: float, pitch_deg: float) -> void:
	var anim: String = _names[clip]
	if _ap.current_animation != anim:
		_ap.play(anim)
	_ap.seek(fposmod(t, _ap.get_animation(anim).length), true)
	_ch.rotation = Vector3(0.0, body_yaw, 0.0)
	_ch.position = Vector3.ZERO
	var p: Vector3 = _bone_at("Hips")
	_ch.position = Vector3(-p.x, 0.0, -p.z)
	_m.aim_yaw = deg_to_rad(yaw_deg)
	_m.aim_pitch = deg_to_rad(pitch_deg)
	if _m.smoothing_s <= 0.0:
		_m.snap()


func _grid(clip: String, out: String) -> Dictionary:
	var cells: Array[Image] = []
	for p: float in PITCHES:
		for y: float in YAWS:
			_pose(clip, 0.1, 0.0, y, p)
			for _i: int in 3:
				await process_frame
			var c: Vector3 = (_bone_at("UpperChest") + _bone_at("Head")) * 0.5 + Vector3(0.0, 0.12, 0.0)
			var tg: Vector2 = _m.target() * (180.0 / PI)  # the clamped angles the head is shown at, not the asked ones
			_label.text = "%s  yaw %+d  pitch %+d" % [clip, roundi(tg.x), roundi(tg.y)]
			_label.position = Vector2(385.0, 8.0)
			cells.append(await _cell(c, 1.4, 45.0, GRID_CELL))
	_sheet(cells, GRID_CELL, YAWS.size()).save_png(out.path_join("grid_%s.png" % clip))
	print("SHOT grid_%s %d cells" % [clip, cells.size()])
	return {"yaws": YAWS, "pitches": PITCHES, "clip_t": 0.1, "view": "three-quarter front-left, upper body"}


func _extremes(out: String, tag: String) -> Dictionary:
	var cells: Array[Image] = []
	for half: int in 2:
		for view: float in [0.0, 90.0]:
			for k: int in 4:
				var e: Array = EXTREMES[half * 4 + k]
				_pose("Idle", 0.0, 0.0, e[0], e[1])
				for _i: int in 3:
					await process_frame
				var c: Vector3 = _bone_at("Neck") + Vector3(0.0, 0.14, 0.0)
				var tg: Vector2 = _m.target() * (180.0 / PI)  # the clamped angles (rec: -50 asked is shown at -35)
				_label.text = "%s %s  yaw %+d  pitch %+d" % [tag, "front" if view == 0.0 else "side", roundi(tg.x),
					roundi(tg.y)]
				_label.position = Vector2(290.0, 8.0)
				cells.append(await _cell(c, 0.8, view, CLOSE_CELL))
	_sheet(cells, CLOSE_CELL, 4).save_png(out.path_join("extremes_%s.png" % tag))
	print("SHOT extremes_%s %d cells" % [tag, cells.size()])
	return {"poses": EXTREMES, "rows": "front 1-4, side 1-4, front 5-8, side 5-8", "view_h_m": 0.8,
		"split": [_m.yaw_split, _m.pitch_split], "clamps": [_m.yaw_limit_deg, _m.pitch_down_deg, _m.pitch_up_deg]}


func _video_frame() -> Image:
	for _i: int in 2:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	return img


func _reel(name: String, clip: String, kind: String, dz_deg: float, job: Dictionary) -> Dictionary:
	var seconds: float = LAG_S if kind == "lag" else GESTURE_S
	var n: int = int(round(seconds * FPS))
	var dir_out: String = job["frames"].path_join(name)
	DirAccess.make_dir_recursive_absolute(dir_out)
	var keys := {}
	for k: int in 8:
		keys[int(round(k * (n - 1) / 7.0)) if kind == "lag" else k * 3] = k
	var row: Array[Image] = []
	row.resize(8)
	var lag := kind == "lag"
	_show_lines(lag)
	_m.smoothing_s = 0.0  # the aim is smoothed here, at the video's step (two process frames per video frame)
	var dz := deg_to_rad(dz_deg)
	var body := 0.0
	var sy := 0.0
	var sp := 0.0
	var peak := Vector2.ZERO
	var body_max := 0.0
	_pose(clip, 0.0, 0.0, 0.0, 0.0)
	_m.snap()
	for _i: int in 3:
		await process_frame
	if lag:
		_cam.position = Vector3(1.3, 2.9, 3.6)
		_cam.look_at(Vector3(0.35, 0.95, 0.3))
	else:
		var c: Vector3 = _bone_at("Neck")  # the head is large: the frame from the hips to above the crest
		var dist: float = 1.45 * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
		_cam.position = c + Vector3(sin(deg_to_rad(35.0)), 0.08, cos(deg_to_rad(35.0))).normalized() * dist
		_cam.look_at(c)
	_label.position = Vector2(20.0, 14.0)
	for f: int in n:
		var t: float = f / FPS
		var y := 0.0
		var p := 0.0
		if lag:
			var u: float = t / (seconds * 0.5)  # 0..1 up (2.5 s sweep, 0.5 s hold), then back
			var s: float = smoothstep(0.0, 1.0, clampf(u / (5.0 / 6.0), 0.0, 1.0)) if u <= 1.0 \
					else 1.0 - smoothstep(0.0, 1.0, clampf((u - 1.0) / (5.0 / 6.0), 0.0, 1.0))
			var aim := deg_to_rad(120.0) * s
			body = HeadLook.body_follow(body, aim, dz)
			_pose(clip, t, body, rad_to_deg(wrapf(aim - body, -PI, PI)), 0.0)
			_point_line("aim", aim)
			_point_line("body", body)
			_point_line("edge_a", body + dz)
			_point_line("edge_b", body - dz)
			body_max = maxf(body_max, rad_to_deg(body))
			_label.text = "%s  dead zone %d deg   aim %+.0f  body %+.0f  head (rel.) %+.0f" % [name, int(dz_deg),
				rad_to_deg(aim), rad_to_deg(body), rad_to_deg(_m.applied().x)]
		else:
			var w: float = sin(TAU * 2.0 * t)
			if kind == "nod":
				p = 20.0 * w
			else:
				y = 30.0 * w
			var k: float = 1.0 - exp(-(1.0 / FPS) / SMOOTH_S)  # the modifier's smoothing, at the video's step
			sy += (y - sy) * k
			sp += (p - sp) * k
			_pose(clip, t, 0.0, sy, sp)
			peak = Vector2(maxf(peak.x, absf(sy)), maxf(peak.y, absf(sp)))
			_label.text = "%s  %s  %s at 2 Hz   yaw %+.0f  pitch %+.0f" % [name, clip,
				"pitch +-20" if kind == "nod" else "yaw +-30", sy, sp]
		var img: Image = await _video_frame()
		img.save_png(dir_out.path_join("%04d.png" % f))
		if keys.has(f):
			var c2: Image = img.get_region(Rect2i((img.get_width() - KEY_CROP.x) / 2, 0, KEY_CROP.x, KEY_CROP.y))
			c2.resize(KEY_CELL.x, KEY_CELL.y, Image.INTERPOLATE_LANCZOS)
			row[keys[f]] = c2
	_show_lines(false)
	_m.smoothing_s = 0.0
	_sheet(row, KEY_CELL, 8).save_png(job["out"].path_join(name + ".png"))
	var info := {"clip": clip, "frames": n, "seconds": seconds}
	if lag:
		info["dead_zone_deg"] = dz_deg
		info["body_max_deg"] = snappedf(body_max, 0.1)
		info["body_end_deg"] = snappedf(rad_to_deg(body), 0.1)
	else:
		info["peak_after_smoothing_deg"] = [snappedf(peak.x, 0.1), snappedf(peak.y, 0.1)]
	print("SHOT %s %s" % [name, JSON.stringify(info)])
	return info
