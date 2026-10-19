extends "res://alien/second_test.gd"
## The alien's neck judged on its own (art #196, S9b), under second_test.gd's stage (the showroom's Medium look), in a
## real window kept off-screen (godot/lib/offscreen.gd, #214; run through the runner's _godot.window()). Two or more
## characters in the spec's "order" (before first); teal, eyes bored, mouth frog, no crest. Writes into <out>:
## - beside.png: per row a view (three-quarter front and profile at 0.5 m), the characters in order, then the spec's
##   reference images ("refs": one PNG per row, e.g. rf2 and u1's side);
## - motion.png: per pose (rest, Walk at a quarter and three quarters, the head turned 40 degrees left and right,
##   nodded 25 degrees down and 20 up; the turn and nod spread 35/65 over Neck and Head about world axes), the
##   profile and the three-quarter back of each character at 0.5 m;
## - far.png: each character at 1 m from the three-quarter front, the profile and the three-quarter back, at rest.
## - swim.png (spec "swim": true): the left upper arm at two Walk times with the camera fixed in the arm bone's frame
##   and the grain exaggerated (grain 0.5 at 150 per metre), one row per character: a skin whose gradient and grain
##   read the rest pose shows the same pattern in both frames; one reading the skinned VERTEX shows it swim.
## - torso.png (spec "torso": [PNG, ...], S9d): the pale panel's edge on the upper body at 1.5 m, one row per
##   character (front, three-quarter, profile, three-quarter back), then a row of the given turnaround views (their
##   upper halves, e.g. u1's front and side).
## Spec: {"scenes": {key: "res://import/..glb"}, "order": [keys], "out": DIR, "hdri": .., "refs": [PNG, PNG]}.

const NECK_SHARE: float = 0.35
const POSES: Array = [["rest", "Idle", 0.0, 0.0, 0.0], ["walk .25", "Walk", -0.25, 0.0, 0.0],
	["walk .75", "Walk", -0.75, 0.0, 0.0], ["turn L 40", "Idle", 0.0, 40.0, 0.0],
	["turn R 40", "Idle", 0.0, -40.0, 0.0], ["nod down 25", "Idle", 0.0, 0.0, 25.0],
	["nod up 20", "Idle", 0.0, 0.0, -20.0]]


func _sk(k: String) -> Skeleton3D:
	return (_ch[k] as Node3D).find_child("Skeleton3D", true, false) as Skeleton3D


## The neck's middle in the world: halfway between the Neck and Head joints.
func _neck(k: String) -> Vector3:
	var sk: Skeleton3D = _sk(k)
	var a: Vector3 = sk.get_bone_global_pose(sk.find_bone("Neck")).origin
	var b: Vector3 = sk.get_bone_global_pose(sk.find_bone("Head")).origin
	return sk.global_transform * ((a + b) * 0.5)


## Rotates Neck and Head about world axes (yaw about up, nod about the character's right-left axis, + = down).
func _turn(k: String, yaw_deg: float, nod_deg: float) -> void:
	var sk: Skeleton3D = _sk(k)
	var to_sk: Basis = sk.global_transform.basis.orthonormalized().inverse()
	var up: Vector3 = (to_sk * Vector3.UP).normalized()
	var side: Vector3 = (to_sk * (_ch[k] as Node3D).global_transform.basis.x).normalized()
	var applied := Quaternion.IDENTITY  # the rotation already given to the parent (skeleton space)
	var parents: Array = []  # every parent's global rotation, read before any bone changes
	for name: String in ["Neck", "Head"]:
		parents.append(sk.get_bone_global_pose(sk.get_bone_parent(sk.find_bone(name))).basis.get_rotation_quaternion())
	for j: int in 2:
		var pair: Array = [["Neck", NECK_SHARE], ["Head", 1.0 - NECK_SHARE]][j]
		var i: int = sk.find_bone(pair[0])
		var share: float = pair[1]
		var r := Quaternion(up, deg_to_rad(yaw_deg * share)) * Quaternion(side, deg_to_rad(nod_deg * share))
		var pq: Quaternion = applied * (parents[j] as Quaternion)
		var local: Quaternion = sk.get_bone_pose_rotation(i)
		sk.set_bone_pose_rotation(i, (pq.inverse() * r * pq * local).normalized())
		applied = r * applied


func _set_pose(p: Array) -> void:
	_pose(p[1], p[2])
	await process_frame
	for k: String in _ch:
		if p[3] != 0.0 or p[4] != 0.0:
			_turn(k, p[3], p[4])
	await process_frame


func _ref(path: String) -> Image:
	var img: Image = Image.load_from_file(path)
	if img == null or img.is_empty():
		_fail("cannot read %s" % path)
		return null
	var s: int = mini(img.get_width(), img.get_height())
	if img.get_height() > 2 * img.get_width():  # a full-body turnaround view: its head and neck, near the top
		return img.get_region(Rect2i(0, int(img.get_height() * 0.04), s, s))
	return img.get_region(Rect2i((img.get_width() - s) / 2, (img.get_height() - s) / 2, s, s))


## A full-body turnaround view's upper body: from 4 % to 58 % of its height, as a square.
func _ref_torso(path: String) -> Image:
	var img: Image = Image.load_from_file(path)
	if img == null or img.is_empty():
		_fail("cannot read %s" % path)
		return null
	img.convert(Image.FORMAT_RGBA8)
	var h: int = int(img.get_height() * 0.54)
	var w: int = mini(h, img.get_width())
	var part: Image = img.get_region(Rect2i((img.get_width() - w) / 2, int(img.get_height() * 0.04), w, h))
	var r := Image.create(h, h, false, Image.FORMAT_RGBA8)
	r.fill(Color(0.5, 0.5, 0.52))
	r.blend_rect(part, Rect2i(0, 0, w, h), Vector2i((h - w) / 2, 0))
	return r


func _torso() -> void:
	var imgs: Array = []
	await _set_pose(POSES[0])
	var yaws: Array = [0.0, 45.0, 90.0, 150.0]
	for k: String in _order:
		_only([k], false)
		await process_frame
		for yaw: float in yaws:
			_look(_neck(k) - Vector3(0, 0.30, 0), yaw, 2.0, 1.5, 40)
			imgs.append(await _shot("%s %d 1.5 m" % [k, int(yaw)]))
	var refs: Array = _spec["torso"]
	for i: int in yaws.size():
		if i < refs.size():
			var r: Image = _ref_torso(refs[i])
			if r == null:
				return
			imgs.append(r)
	_sheet(imgs, yaws.size(), "torso.png")


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	_order = _spec["order"]
	DirAccess.make_dir_recursive_absolute(_out)
	_stage()
	for k: String in _order:
		var packed: PackedScene = load(_spec["scenes"][k]) as PackedScene
		if packed == null:
			_fail("cannot load %s" % _spec["scenes"][k])
			return
		var ch: Node3D = packed.instantiate()
		root.add_child(ch)
		var rig: Node = AlienRig.new()
		ch.add_child(rig)
		rig.setup(ch)
		rig.auto_blink = false
		rig.set_crest("")
		_ch[k] = ch
		_rig[k] = rig
		_player[k] = ch.find_child("AnimationPlayer", true, false)
		_combo(k, "bored", "frog")
	if _spec.has("torso"):
		await _torso()
	var refs: Array = _spec.get("refs", [])
	# beside.png
	var imgs: Array = []
	await _set_pose(POSES[0])
	var views: Array = [["3/4", 30.0, 2.0], ["profile", 90.0, 2.0]]
	for row: int in views.size():
		var v: Array = views[row]
		for k: String in _order:
			_only([k], false)
			await process_frame
			_look(_neck(k) + Vector3(0, 0.03, 0), v[1], v[2], 0.5, 40)
			imgs.append(await _shot("%s %s 0.5 m" % [k, v[0]]))
		if row < refs.size():
			var r: Image = _ref(refs[row])
			if r == null:
				return
			imgs.append(r)
	_sheet(imgs, _order.size() + (1 if not refs.is_empty() else 0), "beside.png")
	# motion.png
	imgs = []
	for p: Array in POSES:
		await _set_pose(p)
		for yaw: float in [90.0, 135.0]:
			for k: String in _order:
				_only([k], false)
				await process_frame
				_look(_neck(k), yaw, 4.0, 0.5, 40)
				imgs.append(await _shot("%s %s %d" % [k, p[0], int(yaw)]))
	_sheet(imgs, 2 * _order.size(), "motion.png")
	# far.png
	imgs = []
	await _set_pose(POSES[0])
	for k: String in _order:
		_only([k], false)
		await process_frame
		for yaw: float in [30.0, 90.0, 150.0]:
			_look(_neck(k) - Vector3(0, 0.05, 0), yaw, 2.0, 1.0, 40)
			imgs.append(await _shot("%s %d 1 m" % [k, int(yaw)]))
	_sheet(imgs, 3, "far.png")
	if _spec.get("swim", false):
		imgs = []
		for k: String in _order:
			_only([k], false)
			var mat: ShaderMaterial = _rig[k].skin_material()
			mat.set_shader_parameter("grain", 0.5)
			mat.set_shader_parameter("grain_freq", 150.0)
			for t: float in [-0.10, -0.40]:
				_pose("Walk", t)
				await process_frame
				await process_frame
				var sk: Skeleton3D = _sk(k)
				var g: Transform3D = sk.global_transform * sk.get_bone_global_pose(sk.find_bone("LeftUpperArm"))
				var at: Vector3 = g * Vector3(0, 0.12, 0)
				var eye: Vector3 = g * Vector3(0, 0.12, -0.30)
				_camera.fov = 40.0
				_camera.look_at_from_position(eye, at, (g.basis * Vector3.UP).normalized())
				imgs.append(await _shot("%s Walk %.2f, camera in the arm's frame" % [k, -t]))
			# restore the default grain
			mat.set_shader_parameter("grain", 0.12)
		_sheet(imgs, 2, "swim.png")
	quit(0)
