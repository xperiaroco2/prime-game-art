extends "res://alien/m6c_shots.gd"
## M7's proofs (art #196): the mouth without the black strip, the longer and slimmer digits, under the approved look
## (second_test.gd's stage, light D), no crest, in an off-screen window (the runner's _godot.window(), 1536 x 1536).
## Spec "kits" as m6c_shots.gd (the last one is the hero); "modes", in this order:
## - "digits": digits.png ("digits_name"), a row per kit (the grid's variants), framed on the bones (spec "marks":
##   red balls at the aim points, a framing check), columns: the left hand open (the rest pose) from the back and the
##   palm, a fist (alien_cage_review.curl's: "curl" degrees per finger joint, "thumb_curl") from the back and the
##   palm, the hand in Idle from the outside and in Sprint, the planted foot in Walk from its side and the front, the
##   hand's region of the whole body at 3.5 m; spec "refs": images for a first row (u1, rf2, rb1);
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


## Turns a bone by `deg` about a world axis, on top of its current pose (the parents' turns already in its global pose).
func _turn_world(sk: Skeleton3D, bone: String, axis: Vector3, deg: float) -> void:
	var i: int = sk.find_bone(bone)
	if i < 0:
		return
	var g: Basis = (sk.global_transform.basis * sk.get_bone_global_pose(i).basis).orthonormalized()
	var ax: Vector3 = (g.inverse() * axis).normalized()
	sk.set_bone_pose_rotation(i, sk.get_bone_pose_rotation(i) * Quaternion(ax, deg_to_rad(deg)))


## The rest pose (the animation stopped) with the left hand curled as alien_cage_review.curl does it in Blender: the
## fingers by deg per joint (0.9, 1.1, 0.7 of it) about Blender's +Y (Godot -Z; the hand points +X), the thumb about
## the axis across its forward-pointing mesh and its metacarpal about +X by thumb_deg.
func _fist(k: String, deg: float, thumb_deg: float) -> void:
	(_player[k] as AnimationPlayer).stop()
	var sk: Skeleton3D = _sk(k)
	sk.reset_bone_poses()
	for f: String in FINGERS:
		var ks: Array = [0.9, 1.1, 0.7]
		var segs: Array = ["Proximal", "Intermediate", "Distal"]
		for j: int in 3:
			_turn_world(sk, "Left%s%s" % [f, segs[j]], Vector3(0, 0, -1), deg * ks[j])
	_turn_world(sk, "LeftThumbMetacarpal", Vector3(1, 0, 0), 0.9 * thumb_deg)
	var d := Vector3(0.82, -0.24, 0.42).normalized()  # Blender (0.82, -0.42, -0.24) in Godot axes
	var ax: Vector3 = d.cross(Vector3(0, -1, 0))
	for s: String in ["Proximal", "Distal"]:
		_turn_world(sk, "LeftThumb%s" % s, ax, 0.6 * thumb_deg)


## The yaw (the _look convention: the camera at sin(yaw), cos(yaw) from the target) of the horizontal direction
## from the hips out through p.
func _out_yaw(k: String, p: Vector3) -> float:
	var o: Vector3 = p - _bone_at(k, "Hips")
	return rad_to_deg(atan2(o.x, o.z))


## The left hand: its centre (the mesh's fingers are shorter than their bones, FINGER_K, so the centre is near the
## knuckles) and its bones' length, wrist to the middle finger's last joint.
func _hand_frame(k: String) -> Array:
	var w: Vector3 = _bone_at(k, "LeftHand")
	var t: Vector3 = _bone_at(k, "LeftMiddleDistal")
	return [w.lerp(_bone_at(k, "LeftMiddleProximal"), 0.75), maxf(w.distance_to(t), 0.04)]


var _marks: Array = []


## Spec "marks": small unshaded red balls at the given points (a framing check).
func _mark(points: Array) -> void:
	for m: Node in _marks:
		m.queue_free()
	_marks = []
	if not _spec.get("marks", false):
		return
	for p: Vector3 in points:
		var mi := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 0.008
		sm.height = 0.016
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_color = Color(1, 0, 0)
		mat.no_depth_test = true
		sm.material = mat
		mi.mesh = sm
		root.add_child(mi)
		mi.global_position = p
		_marks.append(mi)


func _digits() -> void:
	var cells: Array = []
	var cols: int = 9
	for p: String in _spec.get("refs", []):
		cells.append(_png(p))
	while cells.size() % cols != 0:
		cells.append(null)
	var deg: float = _spec.get("curl", 62.0)
	var tdeg: float = _spec.get("thumb_curl", 55.0)
	var tan15: float = tan(deg_to_rad(15.0))
	for k: String in _keys:
		_only([k], false)
		_pose("Idle", 0.0)
		await process_frame
		var hf: Array = _hand_frame(k)
		var c: Vector3 = hf[0]
		var d: float = hf[1] * 3.2 / (2.0 * tan15)
		var yo: float = _out_yaw(k, c)
		print("PROOF digits %s hand %s len %.3f yaw %.0f hips %s toes %s box %s" % [k, c, hf[1], yo,
			_bone_at(k, "Hips"), _bone_at(k, "LeftToes"), _bounds(_ch[k])])
		_mark([c, _bone_at(k, "LeftHand"), _bone_at(k, "LeftMiddleDistal")])
		var idle_c: Vector3 = c
		var idle_d: float = d
		# the open hand: the rest pose (the arm out along +X, the palm down), from above and from below in front
		_fist(k, 0.0, 0.0)
		await process_frame
		hf = _hand_frame(k)
		c = _bone_at(k, "LeftHand").lerp(_bone_at(k, "LeftMiddleDistal"), 0.5)
		_look(c, 10.0, 70.0, hf[1] * 2.6 / (2.0 * tan15), 30.0)
		cells.append(await _shot("%s open, back" % _labels[k]))
		_look(c, 25.0, -55.0, hf[1] * 2.6 / (2.0 * tan15), 30.0)
		cells.append(await _shot("%s open, palm" % _labels[k]))
		_fist(k, deg, tdeg)
		await process_frame
		hf = _hand_frame(k)
		c = _bone_at(k, "LeftHand").lerp(_bone_at(k, "LeftMiddleProximal"), 0.85)
		d = hf[1] * 2.8 / (2.0 * tan15)
		_look(c, 15.0, 35.0, d, 30.0)
		cells.append(await _shot("%s fist, back" % _labels[k]))
		_look(c, 35.0, -40.0, d, 30.0)
		cells.append(await _shot("%s fist, palm" % _labels[k]))
		_pose("Idle", 0.0)
		await process_frame
		_look(idle_c, yo + 20.0, 12.0, idle_d, 30.0)
		cells.append(await _shot("%s Idle, outside" % _labels[k]))
		_pose("Sprint_Fwd", 0.12)
		await process_frame
		hf = _hand_frame(k)
		_look(hf[0], _out_yaw(k, hf[0]) + 10.0, 10.0, hf[1] * 3.4 / (2.0 * tan15), 30.0)
		cells.append(await _shot("%s Sprint" % _labels[k]))
		_pose("Walk", 0.25)
		await process_frame
		# the planted foot (the lower toes), framed at foot level from its own side
		var side: String = "Left" if _bone_at(k, "LeftToes").y <= _bone_at(k, "RightToes").y else "Right"
		var ft: Vector3 = _bone_at(k, side + "Foot")
		var toe: Vector3 = _bone_at(k, side + "Toes")
		var fl: float = maxf(ft.distance_to(toe), 0.04)
		var foot: Vector3 = ft.lerp(toe, 0.6)
		foot.y = 0.05
		print("PROOF digits walk %s foot %s toe %s" % [side, ft, toe])
		_mark([foot, ft, toe])
		_look(foot, 90.0 if side == "Left" else -90.0, 6.0, fl * 2.6 / (2.0 * tan15), 30.0)
		cells.append(await _shot("%s Walk, side" % _labels[k]))
		_look(foot, 25.0 if side == "Left" else -25.0, 18.0, fl * 2.6 / (2.0 * tan15), 30.0)
		cells.append(await _shot("%s Walk, front" % _labels[k]))
		_mark([])
		_pose("Idle", 0.0)
		await process_frame
		_look(Vector3(0, 0.95, 0), 30.0, 3.0, 3.5, 40.0)
		var far: Image = await _shot("")
		var hs: Vector2 = _camera.unproject_position(_hand(k))
		var w: int = far.get_width() / 6
		var r := Rect2i(clampi(int(hs.x) - w / 2, 0, far.get_width() - w), clampi(int(hs.y) - w / 2, 0, far.get_height() - w), w, w)
		cells.append(far.get_region(r))
		_label.text = ""
		_pose("Idle", 0.0)
	_grid_cells(cells, cols, Vector2i(320, 320), _spec.get("digits_name", "digits.png"))


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
