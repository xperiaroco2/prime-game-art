extends SceneTree
## The head-look modifier's unit check (art #196, H1), headless: per character GLB the modifier (head_look.gd) on its
## skeleton, smoothing off; the head bone's facing (its global rotation against the same pose without the modifier,
## applied to the forward axis) measured as a yaw and a pitch:
## - inside the clamps (yaw -70..+70 x pitch -50..+40) on the rest pose: within TOL_DEG of the asked angles;
## - beyond them (yaw +-100, pitch -80 / +80): at the clamps;
## - held for 10 frames: no drift (the modifier must not add to its own last result);
## - on the Idle and Jog_Fwd clips: the clip's own head facing turned by the aim, within TOL_DEG;
## - a middle bone (Neck) turned by aim_turn() of its cumulative share of the split, the shares summed here from the
##   modifier's yaw_split and pitch_split along the skeleton's own parents (a wrong share between bones fails it);
## - a fresh modifier with its defaults clamps at them (pitch -80 gives -35, yaw 100 gives 70);
## - the smoothing reaches a step's target; body_follow() on the dead zone's cases (its default, DEAD_ZONE, 45).
## Prints HEADLOOK <json> per character and exits 1 on any failure. Args after "--": <res://...glb>...

const HeadLook = preload("res://alien/head_look.gd")
const TOL_DEG := 1.0

var _head_q := Quaternion.IDENTITY
var _sk: Skeleton3D
var _hb := -1
var _neck_q := Quaternion.IDENTITY
var _nb := -1


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var ok := true
	for path: String in OS.get_cmdline_user_args():
		var r: Dictionary = await _check(path)
		print("HEADLOOK ", JSON.stringify(r))
		ok = ok and r["pass"]
	ok = ok and _follow_cases()
	print("HEADLOOK_RESULT ", "pass" if ok else "FAIL")
	quit(0 if ok else 1)


func _follow_cases() -> bool:
	var dz := deg_to_rad(45.0)
	var cases := [[0.0, 30.0, 0.0], [0.0, 45.0, 0.0], [0.0, 60.0, 15.0], [0.0, -90.0, -45.0], [10.0, 120.0, 75.0],
		[170.0, -170.0, 170.0], [170.0, -100.0, -145.0]]  # body, aim, expected body (degrees)
	var ok := absf(HeadLook.DEAD_ZONE - dz) < 1e-6  # the default: the engineer's pick (2026-10-26)
	print("FOLLOW default dead zone %.1f deg %s" % [rad_to_deg(HeadLook.DEAD_ZONE), "ok" if ok else "FAIL"])
	for c: Array in cases:
		var got := rad_to_deg(HeadLook.body_follow(deg_to_rad(c[0]), deg_to_rad(c[1]), dz))
		var good := absf(wrapf(got - float(c[2]), -180.0, 180.0)) < 0.01
		ok = ok and good
		print("FOLLOW body %.0f aim %.0f -> %.2f (expected %.0f) %s" % [c[0], c[1], got, c[2], "ok" if good else "FAIL"])
	# the default third argument exercised: no dead zone passed, DEAD_ZONE (45) applies (PR #331's review, minor 3)
	var got_default := rad_to_deg(HeadLook.body_follow(0.0, deg_to_rad(60.0)))
	var good_default := absf(got_default - 15.0) < 0.01
	ok = ok and good_default
	print("FOLLOW default arg body 0 aim 60 -> %.2f (expected 15) %s" % [got_default, "ok" if good_default else "FAIL"])
	return ok


func _on_done() -> void:
	_head_q = _sk.get_bone_global_pose(_hb).basis.get_rotation_quaternion()
	if _nb >= 0:
		_neck_q = _sk.get_bone_global_pose(_nb).basis.get_rotation_quaternion()


## The head's global rotation after n frames: the modifier's result when it runs (read at modification_processed), the
## pose itself when it is off (an inactive modifier sends no signal).
func _settle(n: int = 3, active: bool = true) -> Quaternion:
	for _i: int in n:
		await process_frame
	return _head_q if active else _sk.get_bone_global_pose(_hb).basis.get_rotation_quaternion()


func _angles(f: Vector3) -> Vector2:
	return Vector2(rad_to_deg(atan2(f.x, f.z)), rad_to_deg(asin(clampf(f.y, -1.0, 1.0))))


func _check(path: String) -> Dictionary:
	var ch: Node3D = (load(path) as PackedScene).instantiate()
	root.add_child(ch)
	_sk = ch.find_children("*", "Skeleton3D", true, false)[0]
	_hb = _sk.find_bone("Head")
	_nb = _sk.find_bone("Neck")
	var ap: AnimationPlayer = ch.find_children("*", "AnimationPlayer", true, false)[0]
	ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var names := {}
	for n: String in ap.get_animation_list():
		names[n.get_slice("|", n.get_slice_count("|") - 1).trim_suffix("_Loop")] = n
	var m: SkeletonModifier3D = HeadLook.new()
	m.smoothing_s = 0.0
	m.pitch_down_deg = 50.0  # the check's range (R1's clamps), whatever the defaults
	m.yaw_limit_deg = 70.0
	m.pitch_up_deg = 40.0
	_sk.add_child(m)
	m.modification_processed.connect(_on_done)
	var r := {"glb": path, "inside": 0, "inside_max_err_deg": 0.0, "clamp_max_err_deg": 0.0, "drift_deg": 0.0,
		"clip_max_err_deg": {}, "fails": []}
	# the rest pose: the reference facing without the modifier
	ap.stop()
	_sk.reset_bone_poses()
	m.active = false
	var ref: Quaternion = await _settle(3, false)
	var ref_neck := Quaternion.IDENTITY
	if _nb >= 0:
		ref_neck = _sk.get_bone_global_pose(_nb).basis.get_rotation_quaternion()
	var share := _neck_share(m)
	r["neck_share"] = [snappedf(share.x, 0.001), snappedf(share.y, 0.001)]
	r["neck_max_err_deg"] = 0.0
	if _nb < 0:
		r["fails"].append("no Neck bone")
	m.active = true
	for y: float in [-70.0, -35.0, 0.0, 35.0, 70.0]:
		for p: float in [-50.0, -25.0, 0.0, 20.0, 40.0]:
			m.aim_yaw = deg_to_rad(y)
			m.aim_pitch = deg_to_rad(p)
			var q: Quaternion = await _settle()
			var a := _angles(q * ref.inverse() * HeadLook.FORWARD)
			var e := maxf(absf(a.x - y), absf(a.y - p))
			r["inside"] += 1
			r["inside_max_err_deg"] = maxf(r["inside_max_err_deg"], e)
			if e > TOL_DEG:
				r["fails"].append("inside %s,%s -> %.2f,%.2f" % [y, p, a.x, a.y])
			if _nb >= 0:  # the middle bone: its cumulative share of the aim
				var want: Quaternion = HeadLook.aim_turn(m.aim_yaw * share.x, m.aim_pitch * share.y)
				var en := rad_to_deg((_neck_q * ref_neck.inverse()).angle_to(want))
				r["neck_max_err_deg"] = maxf(r["neck_max_err_deg"], en)
				if en > TOL_DEG:
					r["fails"].append("neck %s,%s off by %.2f deg" % [y, p, en])
	for c: Array in [[100.0, 0.0, 70.0, 0.0], [-100.0, 0.0, -70.0, 0.0], [0.0, -80.0, 0.0, -50.0],
			[0.0, 80.0, 0.0, 40.0], [100.0, -80.0, 70.0, -50.0], [-100.0, 80.0, -70.0, 40.0]]:
		m.aim_yaw = deg_to_rad(c[0])
		m.aim_pitch = deg_to_rad(c[1])
		var q: Quaternion = await _settle()
		var a := _angles(q * ref.inverse() * HeadLook.FORWARD)
		var e := maxf(absf(a.x - c[2]), absf(a.y - c[3]))
		r["clamp_max_err_deg"] = maxf(r["clamp_max_err_deg"], e)
		if e > TOL_DEG:
			r["fails"].append("clamp %s,%s -> %.2f,%.2f" % [c[0], c[1], a.x, a.y])
	m.aim_yaw = deg_to_rad(50.0)
	m.aim_pitch = deg_to_rad(-30.0)
	var q0: Quaternion = await _settle()
	var q1: Quaternion = await _settle(10)
	r["drift_deg"] = rad_to_deg(q0.angle_to(q1))
	if r["drift_deg"] > 0.1:
		r["fails"].append("drift %.3f deg over 10 frames" % r["drift_deg"])
	# on clips: the clip's own head facing turned by the aim
	for clip: String in ["Idle", "Jog_Fwd"]:
		if not names.has(clip):
			r["fails"].append("no clip " + clip)
			continue
		ap.play(names[clip])
		var worst := 0.0
		for t: float in [0.0, 0.21, 0.43]:
			ap.seek(t, true)
			m.active = false
			var cref: Quaternion = await _settle(3, false)
			var f0: Vector3 = cref * ref.inverse() * HeadLook.FORWARD
			m.active = true
			for c: Array in [[70.0, 0.0], [-35.0, 40.0], [35.0, -50.0], [0.0, 0.0]]:
				m.aim_yaw = deg_to_rad(c[0])
				m.aim_pitch = deg_to_rad(c[1])
				var q: Quaternion = await _settle()
				var f: Vector3 = q * ref.inverse() * HeadLook.FORWARD
				var want: Vector3 = HeadLook.aim_turn(m.aim_yaw, m.aim_pitch) * f0
				worst = maxf(worst, rad_to_deg(f.angle_to(want)))
		r["clip_max_err_deg"][clip] = snappedf(worst, 0.001)
		if worst > TOL_DEG:
			r["fails"].append("clip %s %.2f deg" % [clip, worst])
	# the smoothing: a step reaches its target
	ap.stop()
	_sk.reset_bone_poses()
	m.smoothing_s = 0.08
	m.aim_yaw = 0.0
	m.aim_pitch = 0.0
	m.snap()
	m.aim_yaw = deg_to_rad(60.0)
	await _settle(1)
	var early: float = rad_to_deg(m.applied().x)
	await _settle(90)
	var late: float = rad_to_deg(m.applied().x)
	r["smoothing"] = {"after_1_frame_deg": snappedf(early, 0.01), "after_91_frames_deg": snappedf(late, 0.01)}
	if early >= 59.0 or absf(late - 60.0) > TOL_DEG:
		r["fails"].append("smoothing %.2f then %.2f" % [early, late])
	# a fresh modifier with its defaults (70 / 35 down / 40 up, smoothing on: its first frame snaps)
	_sk.remove_child(m)
	m.free()
	var d: SkeletonModifier3D = HeadLook.new()
	d.aim_yaw = deg_to_rad(100.0)
	d.aim_pitch = deg_to_rad(-80.0)
	_sk.add_child(d)
	d.modification_processed.connect(_on_done)
	ap.stop()
	_sk.reset_bone_poses()
	var qd: Quaternion = await _settle()
	var ad := _angles(qd * ref.inverse() * HeadLook.FORWARD)
	r["default_clamp_deg"] = [snappedf(ad.x, 0.01), snappedf(ad.y, 0.01)]
	if maxf(absf(ad.x - 70.0), absf(ad.y + 35.0)) > TOL_DEG:
		r["fails"].append("default clamp 100,-80 -> %.2f,%.2f (want 70,-35)" % [ad.x, ad.y])
	r["pass"] = (r["fails"] as Array).is_empty()
	for k: String in ["inside_max_err_deg", "clamp_max_err_deg", "drift_deg", "neck_max_err_deg"]:
		r[k] = snappedf(r[k], 0.001)
	ch.queue_free()
	return r


## The Neck's cumulative share (yaw, pitch) of the split, summed independently of the modifier's chain: each split bone
## from the Neck up its parents, over every split bone the skeleton has.
func _neck_share(m: SkeletonModifier3D) -> Vector2:
	var tot := Vector2.ZERO
	for n: String in m.yaw_split:
		if _sk.find_bone(n) >= 0:
			tot.x += float(m.yaw_split[n])
	for n: String in m.pitch_split:
		if _sk.find_bone(n) >= 0:
			tot.y += float(m.pitch_split[n])
	var cum := Vector2.ZERO
	var b := _nb
	while b >= 0:
		var n: String = _sk.get_bone_name(b)
		cum += Vector2(float(m.yaw_split.get(n, 0.0)), float(m.pitch_split.get(n, 0.0)))
		b = _sk.get_bone_parent(b)
	return Vector2(cum.x / tot.x if tot.x > 0.0 else 0.0, cum.y / tot.y if tot.y > 0.0 else 0.0)
