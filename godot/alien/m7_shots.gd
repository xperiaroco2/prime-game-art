extends "res://alien/m6c_shots.gd"
## M7's proofs (art #196): the mouth without the black strip, the longer and slimmer digits, under the approved look
## (second_test.gd's stage, light D), no crest, in an off-screen window (the runner's _godot.window(), 1536 x 1536).
## Spec "kits" as m6c_shots.gd (the last one is the hero); "modes", in this order:
## - "digits": digits.png, a row per kit (the grid's variants), columns: the left hand open (Idle) from the back and
##   the palm side at 0.5 m, a fist (the finger bones curled by "curl" degrees, the thumb swung) from the back and the
##   front, the hand in Sprint, the feet in Walk from the side and from the front at 0.8 m, the whole body at 3.5 m
##   (the hand's region enlarged in feet_far); spec "refs": images for a first row (u1, rf2, rb1);
## - "mouths": mouths_<design>.png per design, a row per shape and kit (before above after), the columns: front, 3/4
##   left and right, profile, from below at 0.4 m and 3/4 at 1.2 m; mouths_clips.png: each kit talking (the Talk clip)
##   and in Walk, every shape at 3/4 from 0.6 m;
## - "cmp", "designs", "contact": m6c_shots.gd's;
## - "body": body.png, a column per kit: the whole body from the front and the side at 3 m (Idle frame 0), u1 last.

const SHAPES: Array[String] = ["rest", "M", "small", "A", "E", "O"]
const MOUTH_VIEWS: Array = [[0.0, 2.0, 0.4], [35.0, 2.0, 0.4], [-35.0, 2.0, 0.4], [90.0, 2.0, 0.4],
	[20.0, -25.0, 0.4], [35.0, 2.0, 1.2]]
const FINGERS: Array[String] = ["Index", "Middle", "Ring"]


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_modes = _spec.get("modes", ["digits"])
	_stage()
	if _spec.has("bg"):
		_backdrop(_spec["bg"])
	_order = []
	for kit: Dictionary in _spec["kits"]:
		var k: String = kit["key"]
		if not _add_look(k, kit["res"], kit.get("look", "m6")):
			return
		_keys.append(k)
		_labels[k] = kit.get("label", k)
	var hero: String = _keys[-1]
	_pose("Idle", 0.0)
	_only([hero], false)
	for _i: int in 4:
		await process_frame
	var rf2: Image = _png(_spec.get("beside", ""))
	var rf2_eye: Image = _region(rf2, _spec.get("rf2_eye", [0.17, 0.26, 0.67, 0.76])) if rf2 != null else null
	if _modes.has("digits"):
		await _digits()
	if _modes.has("mouths"):
		await _mouths()
	if _modes.has("cmp"):
		_pose("Idle", 0.0)
		await _cmp(hero, rf2, rf2_eye)
	if _modes.has("designs"):
		await _designs(hero)
	if _modes.has("contact"):
		await _contact()
	if _modes.has("body"):
		await _body()
	quit(0)


func _sk(k: String) -> Skeleton3D:
	return (_ch[k] as Node3D).find_child("Skeleton3D", true, false) as Skeleton3D


func _bone_at(k: String, bone: String) -> Vector3:
	var sk: Skeleton3D = _sk(k)
	return sk.global_transform * sk.get_bone_global_pose(sk.find_bone(bone)).origin


## The rest pose (the animation stopped) with the left hand's fingers curled by `deg` about the palm's side axis
## (world +Z in the T-pose: the hand points +X, the palm faces -Y) and the thumb swung about the hand's long axis.
func _fist(k: String, deg: float) -> void:
	(_player[k] as AnimationPlayer).stop()
	var sk: Skeleton3D = _sk(k)
	sk.reset_bone_poses()
	var curl: Array = []
	for f: String in FINGERS:
		for seg: String in ["Proximal", "Intermediate", "Distal"]:
			curl.append(["Left%s%s" % [f, seg], Vector3(0, 0, -1), deg])
	curl.append(["LeftThumbProximal", Vector3(1, 0, 0), deg * 0.6])
	curl.append(["LeftThumbDistal", Vector3(0, 0, -1), deg * 0.5])
	for c: Array in curl:
		var i: int = sk.find_bone(c[0])
		if i < 0:
			continue
		var g: Basis = sk.get_bone_global_rest(i).basis.orthonormalized()
		var ax: Vector3 = (g.inverse() * (c[1] as Vector3)).normalized()
		sk.set_bone_pose_rotation(i, sk.get_bone_rest(i).basis.get_rotation_quaternion() * Quaternion(ax, deg_to_rad(c[2])))


func _digits() -> void:
	var cells: Array = []
	var cols: int = 8
	for p: String in _spec.get("refs", []):
		cells.append(_png(p))
	while cells.size() % cols != 0:
		cells.append(null)
	var curl: float = _spec.get("curl", 75.0)
	for k: String in _keys:
		_only([k], false)
		_pose("Idle", 0.0)
		await process_frame
		var h: Vector3 = _hand(k)
		_look(h, 90.0, 35.0, 0.5, 30.0)
		cells.append(await _shot("%s open, back" % _labels[k]))
		_look(h, 60.0, -35.0, 0.5, 30.0)
		cells.append(await _shot("%s open, palm" % _labels[k]))
		_fist(k, curl)
		await process_frame
		h = _bone_at(k, "LeftHand").lerp(_bone_at(k, "LeftMiddleProximal"), 0.8)
		_look(h, 0.0, 45.0, 0.42, 30.0)
		cells.append(await _shot("%s fist, back" % _labels[k]))
		_look(h, 10.0, -10.0, 0.42, 30.0)
		cells.append(await _shot("%s fist, front" % _labels[k]))
		_pose("Sprint_Fwd", 0.12)
		await process_frame
		_look(_hand(k), 70.0, 10.0, 0.55, 30.0)
		cells.append(await _shot("%s Sprint" % _labels[k]))
		_pose("Walk", 0.25)
		await process_frame
		var feet: Vector3 = (_bone_at(k, "LeftFoot") + _bone_at(k, "RightFoot")) * 0.5 + Vector3(0, -0.04, 0)
		_look(feet, 90.0, 8.0, 0.8, 30.0)
		cells.append(await _shot("%s Walk, side" % _labels[k]))
		_look(feet, 15.0, 20.0, 0.8, 30.0)
		cells.append(await _shot("%s Walk, front" % _labels[k]))
		_pose("Idle", 0.0)
		await process_frame
		_look(Vector3(0, 0.95, 0), 30.0, 3.0, 3.5, 40.0)
		var far: Image = await _shot("")
		var hs: Vector2 = _camera.unproject_position(_hand(k))
		var w: int = far.get_width() / 6
		var r := Rect2i(clampi(int(hs.x) - w / 2, 0, far.get_width() - w), clampi(int(hs.y) - w / 2, 0, far.get_height() - w), w, w)
		var crop: Image = far.get_region(r)
		_label.text = ""
		cells.append(crop)
		_pose("Idle", 0.0)
	_grid_cells(cells, cols, Vector2i(320, 320), "digits.png")


func _mouths() -> void:
	for design: String in ["frog", "overbite"]:
		var cells: Array = []
		for s: String in SHAPES:
			for k: String in _keys:
				_only([k], false)
				_pose("Idle", 0.0)
				_combo(k, "bored", design, s)
				await process_frame
				var m: Vector3 = _find(k, "Mouth") + Vector3(0, -0.012, 0)
				for v: Array in MOUTH_VIEWS:
					_look(m, v[0], v[1], v[2], 30.0 if v[2] < 1.0 else 12.0)
					cells.append(await _shot("%s %s %s y%d p%d %.1fm" % [_labels[k], design, s, v[0], v[1], v[2]]))
				_combo(k, "bored", "frog")
		_grid_cells(cells, MOUTH_VIEWS.size(), Vector2i(260, 260), "mouths_%s.png" % design)
	var cells2: Array = []
	for k: String in _keys:
		_only([k], false)
		for clip: String in ["Talk_Upper", "Walk"]:
			for s: String in SHAPES:
				_pose(clip, -0.4)
				_combo(k, "bored", "frog" if clip == "Talk_Upper" else "overbite", s)
				await process_frame
				_look(_find(k, "Mouth"), 35.0, 0.0, 0.6, 30.0)
				cells2.append(await _shot("%s %s %s" % [_labels[k], clip, s]))
		_combo(k, "bored", "frog")
	_pose("Idle", 0.0)
	_grid_cells(cells2, SHAPES.size(), Vector2i(260, 260), "mouths_clips.png")


func _body() -> void:
	var cells: Array = []
	for yaw: float in [0.0, 90.0]:
		for k: String in _keys:
			_only([k], false)
			_pose("Idle", 0.0)
			await process_frame
			_view(_body_view(k, yaw, 0.85, 24.0))
			cells.append(await _shot("%s %d" % [_labels[k], yaw]))
		cells.append(_png(_spec.get("body_refs", ["", ""])[0 if yaw == 0.0 else 1]))
	_grid_cells(cells, _keys.size() + 1, Vector2i(400, 640), "body.png")
