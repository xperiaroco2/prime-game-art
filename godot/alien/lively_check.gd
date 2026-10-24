extends SceneTree
## A3b (art #196, A3's left item): alien_lively.gd's pile-up guard and its motion filter run headless on a minimal rig
## (Chest, Neck, Head; no springs), printed as one JSON line "LIVELYCHK {...}" for tools/tests/test_alien_lively_godot.py:
## - "pileup": the head's turn toward a target on a clip, the clip re-posing Neck and Head every step ("reposed") or
##   only once (the clip stopped posing them: "held"); the guard puts the turn on the clip's last own pose, so the two
##   end on the same Head rotation (degrees of the Head's yaw and the angle between them);
## - "rate": the skeleton turning at RATE rad/s about its up, the measured yaw rate (_mv.x) after 1 s per frame rate;
## - "accel": the skeleton accelerating at ACCEL m/s^2 along +X, the measured acceleration (_ma) after 1 s per frame
##   rate, with an uneven step (1/60 and 1/240 alternating), and its largest length in the 0.2 s after a reset_motion()
##   and a 5 m teleport.
##     godot --headless --path godot -s res://alien/lively_check.gd

const Lively = preload("res://alien/alien_lively.gd")
const RATE := 2.0
const ACCEL := 3.0


func _initialize() -> void:
	_run.call_deferred()  # the rig's nodes are inside the tree only once the loop runs


func _run() -> void:
	var out := {"pileup": _pileup(), "rate": {}, "accel": {}}
	for fps: int in [30, 120]:
		out["rate"][str(fps)] = _rate([1.0 / fps])
		out["accel"][str(fps)] = _accel([1.0 / fps])
	out["accel"]["uneven"] = _accel([1.0 / 60.0, 1.0 / 240.0])
	out["accel"]["after_teleport_max"] = _teleport()
	print("LIVELYCHK ", JSON.stringify(out))
	quit(0)


func _rig() -> Array:
	var body := Node3D.new()
	root.add_child(body)
	var sk := Skeleton3D.new()
	body.add_child(sk)
	for b: Array in [["Chest", -1, Vector3(0.0, 1.3, 0.0)], ["Neck", 0, Vector3(0.0, 0.15, 0.0)], ["Head", 1, Vector3(0.0, 0.1, 0.0)]]:
		var i: int = sk.add_bone(b[0])
		sk.set_bone_parent(i, b[1])
		sk.set_bone_rest(i, Transform3D(Basis.IDENTITY, b[2]))
		sk.set_bone_pose(i, Transform3D(Basis.IDENTITY, b[2]))
	var mesh := MeshInstance3D.new()
	mesh.mesh = BoxMesh.new()
	body.add_child(mesh)
	var eye := {"centre": [0.03, 1.6, 0.08], "rest": [0.0, 0.0, 1.0], "radius": 0.02, "iris_angle": 0.3, "pupil_angle": 0.1,
		"iris_profile": [[0.5, 0.3, 0.1]], "pupil_colour": [0.0, 0.0, 0.0],
		"limits_deg": {"pos_x": 20, "neg_x": 20, "up": 10, "down": 10}}
	var eye_r: Dictionary = eye.duplicate(true)
	eye_r["centre"] = [-0.03, 1.6, 0.08]
	var mats: Array[ShaderMaterial] = []
	var live = Lively.new(body, mats, {"eyes": {"left": eye, "right": eye_r}, "rig": {}}, null)
	live.on_clip = true
	live.breathing = 0.0
	return [body, sk, live]


func _pose_clip(sk: Skeleton3D, neck_pitch: float) -> void:
	sk.set_bone_pose_rotation(sk.find_bone("Neck"), Quaternion.from_euler(Vector3(neck_pitch, 0.0, 0.0)))
	sk.set_bone_pose_rotation(sk.find_bone("Head"), Quaternion.IDENTITY)


func _pileup() -> Dictionary:
	var res := {}
	var q := {}
	for mode: String in ["reposed", "held"]:
		var r: Array = _rig()
		var sk: Skeleton3D = r[1]
		var live = r[2]
		live.target = Vector3(1.0, 1.6, 2.0)
		for i: int in 120:
			if mode == "reposed" or i == 0:
				_pose_clip(sk, 0.17)
			live.step(1.0 / 60.0)
		var g: Quaternion = sk.get_bone_global_pose(sk.find_bone("Head")).basis.get_rotation_quaternion()
		q[mode] = g
		var f: Vector3 = g * Vector3.BACK
		res[mode + "_yaw_deg"] = rad_to_deg(atan2(f.x, f.z))
		(r[0] as Node3D).free()
	res["apart_deg"] = rad_to_deg((q["reposed"] as Quaternion).angle_to(q["held"]))
	return res


func _rate(dts: Array) -> float:
	var r: Array = _rig()
	var body: Node3D = r[0]
	var live = r[2]
	live.head_follow = 0.0
	var t := 0.0
	var k := 0
	while t < 1.0 - 1e-9:
		var dt: float = dts[k % dts.size()]
		t += dt
		k += 1
		body.rotation = Vector3(0.0, RATE * t, 0.0)
		_pose_clip(r[1], 0.0)
		live.step(dt)
	var v: float = live._mv.x
	body.free()
	return v


func _accel(dts: Array) -> Array:
	var r: Array = _rig()
	var body: Node3D = r[0]
	var live = r[2]
	live.head_follow = 0.0
	var t := 0.0
	var k := 0
	while t < 1.0 - 1e-9:
		var dt: float = dts[k % dts.size()]
		t += dt
		k += 1
		body.position = Vector3(0.5 * ACCEL * t * t, 0.0, 0.0)
		_pose_clip(r[1], 0.0)
		live.step(dt)
	var a: Vector3 = live._ma
	body.free()
	return [a.x, a.y, a.z]


func _teleport() -> float:
	var r: Array = _rig()
	var body: Node3D = r[0]
	var live = r[2]
	live.head_follow = 0.0
	var dt := 1.0 / 60.0
	var top := 0.0
	for i: int in 72:  # 1 s at 2 m/s, then the teleport, then 0.2 s on
		var t: float = i * dt
		body.position = Vector3(2.0 * t + (5.0 if i >= 60 else 0.0), 0.0, 0.0)
		if i == 60:
			live.reset_motion()
		_pose_clip(r[1], 0.0)
		live.step(dt)
		if i >= 60:
			top = maxf(top, (live._ma as Vector3).length())
	body.free()
	return top
