extends RefCounted
## The static premium head made lively (art #196, lively): the eyes look at a target (alien_static.gdshader's
## procedural iris on the fitted eye spheres, clamped to what the lids leave open), the head turns toward it with a
## lag and limits (Neck and Head bones, eyes leading), the crest springs (Crest1-3, a damped spring) and the
## chest breathes. No face rig: the sculpt never deforms above the neck except the crest.
## The head's skin and data come from tools/blender/alien_lively_build.py (`<name>_lively.glb`, `lively.json`,
## `<name>_sclera.png`). Use with preload:
##   const Lively = preload("res://alien/alien_lively.gd")
##   var live := Lively.new(head_scene_root, mats, lively_json_dict, sclera_texture)
##   live.target = some_global_position; live.step(delta)  # each frame (it advances the skeleton itself)
## The gaze maths repeat tools/blender/alien_lively_geom.py (eye_frame, gaze_dir, eye_offsets, clamp_gaze with
## cap_deg = EYE_LIMIT's 25).

## the controller's values when lively.json leaves one out (AL6, PR #306 review): the same table as lively.js's
## CONTROLLER_DEFAULTS (test_controller_defaults_agree); pitch_up_deg and pitch_down_deg fall back to pitch_deg,
## pitch_neck_share to neck_share; sclera_normal_map: the normal map's strength on the eye texels (AL6; 0 was tried on the
## chameleon: its facets under the upper lids stayed, they are not in the normal map)
const CONTROLLER_DEFAULTS := {"gaze": "iris", "head_hz": 1.6, "yaw_deg": 35.0, "pitch_deg": 20.0, "neck_share": 0.4, "tilt": 0.0, "sclera_normal_map": 1.0}
const CATCH_MARGIN := 0.12  # AL3: the bead glint's slide past its rest angle (radians), lively.js CATCH_MARGIN
const EYE_LIMIT := deg_to_rad(25.0)  # the lids' clamp, capped
const EYE_HZ := 9.0  # the eyes' (lead)
const BREATH_S := 4.4  # one breath
const BREATH_CHEST := Vector3(0.006, 0.004, 0.010)  # the chest's scale at the top of a breath (x, y, z)
const BREATH_NOD := deg_to_rad(0.6)  # the head's bob with it
# the head's critically damped follow per head, from lively.json's controller (the chameleon: gaze "iris", 1.6 Hz,
# yaw 35, pitch 20; the axolotl: gaze "none", its dark beads show no turn, so the head leads: 2.2 Hz; AL5: yaw 30,
# pitch up 12 and down 18, AL4's 40 and 24 stretched the neck looking up and swivelled the far eye out of sight);
# neck_share of the yaw in Neck, pitch_neck_share of the pitch (default neck_share), the rest in Head; tilt: the head's
# roll per radian of yaw (AL5, the axolotl 0.15: the top leans into a turn, default 0)
var yaw_limit := deg_to_rad(35.0)
var pitch_limit := deg_to_rad(20.0)
var pitch_down_limit := deg_to_rad(20.0)
var neck_share := 0.4
var pitch_neck_share := 0.4
var tilt := 0.0
var head_hz := 1.6
var bead := false
# the springs (lively.json rig.springs: the chameleon's crest, Crest1-3 as one chain; the axolotl's six gills, one
# bone each, each its own rate, capped at max_deg so no gill pokes into the head; max_deg 0 or missing holds it still): under-damped, pulled back by the
# head's turn speed, the same as the web port's (a SpringBoneSimulator3D on Crest1-3 under the manual skeleton advance
# showed no measurable swing in the first proof)
var springs: Array[Dictionary] = []

var target := Vector3(0.0, 0.0, 10.0)
var head_follow := 1.0  # 0 holds the head (the eyes alone), 1 follows
var breathing := 1.0
var skeleton: Skeleton3D
## A1 (art #196): true when an AnimationPlayer poses the skeleton before every step (a clip on the body): the head's
## turn goes on top of the clip's Neck and Head instead of their rest (the clip's own head motion stays), and the
## springs swing from the head's real motion in the world (its turn and its acceleration, so a jog bobs the crest and
## the gills) instead of the controller's turn alone. The caller re-poses the clip before each step (seek or advance)
## and calls reset_motion() when it jumps to another clip or teleports the character (a respawn; the next step seeds
## the body's velocity from that step's raw velocity, A3), reset_springs() too when the springs must start still. A clip that stops posing Neck and Head (a one-shot's end, a pause, a layer
## that leaves them out) does not pile the turn up: the turn goes on the clip's last own pose (A2). False: the busts'
## and the shots' way, unchanged.
var on_clip := false
var accel_gain := 1.0  # rad/s^2 of spring push per m/s^2 of the head's acceleration (A1)
## A2: the share of the clip's own head yaw (the Head's facing about the skeleton's up, as the clip poses it) taken
## back, so in a run the head stays pointed where the body travels instead of swivelling with the chest; 0 keeps it
var yaw_counter := 0.0
## A2: small eye darts (degrees; 0 none): every 0.6-2.4 s the eyes jump to a new point near the target, the head
## does not follow; the eyes are the static head's only life at rest
var darts := 0.0
## A3: the eyes. "fixed" (the default): the pupils stay centred in the head, the gaze is the head's forward; "lead":
## the eyes reach a new look target first, by at most EYE_LEAD_DEG off the head's forward, and re-centre as the head
## follows; "free": the eyes follow the target as far as the lids allow (A1-A2's way; the eye proofs use it)
var eye_mode := "fixed"
const EYE_LEAD_DEG := 8.0
## A3: the yaw counter low-passed over this time constant (s), so the head does not snap against the chest's swivel
const YAW_COUNTER_TAU := 0.25
## A3: on a clip, each spring's push (its lag behind the head's turn and the acceleration) scaled by the first entry
## whose key starts its name: the axolotl's gills, at 1 four times the crest's jitter in a jog, to about twice
var clip_drive := {"Gill": 0.5}
## A3: the darts' random seed (applied at the first step, or call reseed()), so a reel is the same on every run
var rng_seed := 196
const MOTION_TAU := 0.1  # A2: the measured motion's low-pass time constant (s), the same at any frame rate
var _h_prev := Quaternion.IDENTITY
var _p1 := Vector3.ZERO
var _v1 := Vector3.ZERO
var _body_p := Vector3.ZERO
var _body_v := Vector3.ZERO  # the skeleton's velocity in the world, low-passed
var _body_v1 := Vector3.ZERO
var _seen := 0
var _mv := Vector2.ZERO  # the measured yaw and pitch rates, low-passed
var _ma := Vector3.ZERO  # the measured acceleration in the head's frame, low-passed
var _last := {}  # A2: bone -> [the rotation this controller wrote, the clip's pose under it]
var _dart := Vector2.ZERO
var _dart_t := 0.0
var _rng := RandomNumberGenerator.new()
var _yc := 0.0  # A3: the clip's head yaw, low-passed (the counter's input)
var _seeded := false
var mesh: MeshInstance3D
var mats: Array[ShaderMaterial]
var eyes: Dictionary  # "left"/"right" -> lively.json's eye
var time := 0.0
var _hy := 0.0  # the head's yaw and pitch now, and their velocities
var _hp := 0.0
var _hvy := 0.0
var _hvp := 0.0
var _eye := {"left": Vector4.ZERO, "right": Vector4.ZERO}  # yaw, pitch, their velocities
var _bones := {}
var _rest_q := {}  # B1: bone -> [its local rest rotation, its global rest rotation]


func _init(root: Node, materials: Array[ShaderMaterial], lively: Dictionary, sclera: Texture2D) -> void:
	skeleton = root.find_children("*", "Skeleton3D", true, false)[0]
	mesh = root.find_children("*", "MeshInstance3D", true, false)[0]
	mats = materials
	eyes = lively["eyes"]
	var ctl: Dictionary = CONTROLLER_DEFAULTS.merged(lively.get("controller", {}), true)
	yaw_limit = deg_to_rad(float(ctl["yaw_deg"]))
	pitch_limit = deg_to_rad(float(ctl.get("pitch_up_deg", ctl["pitch_deg"])))
	pitch_down_limit = deg_to_rad(float(ctl.get("pitch_down_deg", ctl["pitch_deg"])))
	neck_share = float(ctl["neck_share"])
	pitch_neck_share = float(ctl.get("pitch_neck_share", neck_share))
	tilt = float(ctl["tilt"])
	head_hz = float(ctl["head_hz"])
	bead = ctl["gaze"] == "none"
	for sm: ShaderMaterial in mats:
		sm.set_shader_parameter("sclera_normal_map", float(ctl["sclera_normal_map"]))
	# no rig.springs: no spring (AL6, as the web; v2's build had none listed and kept its crest still on the web)
	var specs: Array = lively["rig"].get("springs", [])
	for sp: Dictionary in specs:
		var bones: Array[int] = []
		for b: String in sp["bones"]:
			bones.append(skeleton.find_bone(b))
			if bones[-1] < 0:
				push_error("LIVELY no bone %s" % b)
		springs.append({"name": sp["name"], "bones": bones, "hz": float(sp["hz"]), "zeta": float(sp["zeta"]),
			"lag": float(sp["lag"]), "cap": deg_to_rad(float(sp.get("max_deg", 0.0))), "s": Vector4.ZERO})
	for b: String in ["Chest", "Neck", "Head"]:
		_bones[b] = skeleton.find_bone(b)
		if _bones[b] < 0:
			push_error("LIVELY no bone %s" % b)
	for bi: int in [_bones["Neck"], _bones["Head"]]:
		_keep_rest(bi)
	for sp: Dictionary in springs:
		for bi: int in sp["bones"]:
			_keep_rest(bi)
	skeleton.modifier_callback_mode_process = Skeleton3D.MODIFIER_CALLBACK_MODE_PROCESS_MANUAL
	if bead:
		var lc: Dictionary = eyes["left"]["catch"]
		var rc: Dictionary = eyes["right"]["catch"]
		var cc: Array = lc["colour"]
		for sm: ShaderMaterial in mats:
			sm.set_shader_parameter("gaze_on", 1.0)
			sm.set_shader_parameter("bead", 1.0)
			sm.set_shader_parameter("sclera_tex", sclera)
			sm.set_shader_parameter("catch_light", 1.0)
			sm.set_shader_parameter("catch_dir_l", _v(lc["dir"]))
			sm.set_shader_parameter("catch_dir_r", _v(rc["dir"]))
			sm.set_shader_parameter("catch_angle", (float(lc["angle"]) + float(rc["angle"])) * 0.5)
			sm.set_shader_parameter("catch_colour", Color(cc[0], cc[1], cc[2]))
			sm.set_shader_parameter("catch_reach_l", catch_reach(eyes["left"]))
			sm.set_shader_parameter("catch_reach_r", catch_reach(eyes["right"]))
		_apply_eyes()
		return
	var l: Dictionary = eyes["left"]
	var profile := PackedVector3Array()
	for c: Array in l["iris_profile"]:
		var lin: Color = Color(c[0], c[1], c[2]).srgb_to_linear()
		profile.append(Vector3(lin.r, lin.g, lin.b))
	var pc: Array = l["pupil_colour"]
	for sm: ShaderMaterial in mats:
		sm.set_shader_parameter("gaze_on", 1.0)
		sm.set_shader_parameter("sclera_tex", sclera)
		sm.set_shader_parameter("iris_angle", (float(l["iris_angle"]) + float(eyes["right"]["iris_angle"])) * 0.5)
		sm.set_shader_parameter("pupil_angle", (float(l["pupil_angle"]) + float(eyes["right"]["pupil_angle"])) * 0.5)
		sm.set_shader_parameter("iris_profile", profile)
		sm.set_shader_parameter("pupil_colour", Color(pc[0], pc[1], pc[2]))
	_apply_eyes()


func _keep_rest(bi: int) -> void:
	_rest_q[bi] = [skeleton.get_bone_rest(bi).basis.get_rotation_quaternion(),
		skeleton.get_bone_global_rest(bi).basis.get_rotation_quaternion()]


## B1 (the head on the body): q is a turn in the skeleton's frame about the bone's joint; it goes on top of the bone's
## rest as rest * (G^-1 q G), G the bone's global rest rotation. The lively busts' bones rest unturned (G and the rest
## the identity), so there this is set_bone_pose_rotation(q) as before; the contract skeleton's do not.
func _set_rot(bi: int, q: Quaternion) -> void:
	skeleton.set_bone_pose_rotation(bi, rest_turn(_rest_q[bi][0], _rest_q[bi][1], q))


static func rest_turn(rest: Quaternion, g: Quaternion, q: Quaternion) -> Quaternion:
	return (rest * (g.inverse() * q * g)).normalized()


static func _v(a: Array) -> Vector3:
	return Vector3(a[0], a[1], a[2])


## (fwd, side, up) of an eye's rest gaze: side toward +X, up toward +Y (alien_lively_geom.eye_frame).
static func eye_frame(rest: Vector3) -> Array[Vector3]:
	var f := rest.normalized()
	var s := Vector3(f.z, 0.0, -f.x).normalized()
	return [f, s, f.cross(s).normalized()]


static func gaze_dir(rest: Vector3, yaw: float, pitch: float) -> Vector3:
	var fr := eye_frame(rest)
	return (fr[0] + fr[1] * tan(yaw) + fr[2] * tan(pitch)).normalized()


## (yaw, pitch) of a direction t in the eye's rest frame: gaze_dir's inverse (alien_lively_geom.eye_offsets).
static func eye_offsets(rest: Vector3, t: Vector3) -> Vector2:
	var fr := eye_frame(rest)
	var a: float = t.dot(fr[0])
	return Vector2(atan2(t.dot(fr[1]), a), atan2(t.dot(fr[2]), a))


static func clamp_gaze(yaw: float, pitch: float, lim: Dictionary) -> Vector2:
	var ly: float = minf(deg_to_rad(float(lim["pos_x"] if yaw >= 0.0 else lim["neg_x"])), EYE_LIMIT)
	var lp: float = minf(deg_to_rad(float(lim["up"] if pitch >= 0.0 else lim["down"])), EYE_LIMIT)
	if ly <= 0.0 or lp <= 0.0:
		return Vector2(clampf(yaw, -ly, ly) if ly > 0.0 else 0.0, clampf(pitch, -lp, lp) if lp > 0.0 else 0.0)
	var e: float = (yaw / ly) ** 2 + (pitch / lp) ** 2
	return Vector2(yaw, pitch) if e <= 1.0 else Vector2(yaw, pitch) / sqrt(e)


## A critically damped step of x toward goal (x, velocity) at frequency hz: the exact solution, stable at any dt.
static func _damp(x: float, v: float, goal: float, hz: float, dt: float) -> Vector2:
	var w := TAU * hz
	var y := x - goal
	var k := (v + w * y) * dt
	var e := exp(-w * dt)
	return Vector2(goal + (y + k) * e, (v - w * k) * e)


func step(dt: float) -> void:
	if dt <= 0.0:  # A3: a zero step would divide by it (the measured motion): nothing moves
		return
	if not _seeded:
		reseed()
	dt = minf(dt, 0.05)  # a hitch frame must not kick the crest spring (as the web)
	time += dt
	var to_skel: Transform3D = skeleton.global_transform.affine_inverse()
	var t_local: Vector3 = to_skel * target
	# the head: toward the target from between the eyes at rest, clamped, lagging
	var mid: Vector3 = (_v(eyes["left"]["centre"]) + _v(eyes["right"]["centre"])) * 0.5
	var d := t_local - mid
	var gy: float = clampf(atan2(d.x, d.z), -yaw_limit, yaw_limit) * head_follow
	var gp: float = clampf(atan2(d.y, Vector2(d.x, d.z).length()), -pitch_down_limit, pitch_limit) * head_follow
	var r := _damp(_hy, _hvy, gy, head_hz, dt)
	_hy = r.x
	_hvy = r.y
	r = _damp(_hp, _hvp, gp, head_hz, dt)
	_hp = r.x
	_hvp = r.y
	var b: float = (0.5 - 0.5 * cos(TAU * time / BREATH_S)) * breathing
	var nod: float = BREATH_NOD * sin(TAU * time / BREATH_S - 0.6) * breathing
	var chest := Vector3.ONE + BREATH_CHEST * b
	skeleton.set_bone_pose_scale(_bones["Chest"], chest)
	skeleton.set_bone_pose_scale(_bones["Neck"], Vector3.ONE / chest)  # the head keeps its size
	var hy := _hy
	if on_clip:
		var bn: int = _bones["Neck"]
		var bh: int = _bones["Head"]
		var ln := _clip_pose(bn)
		var lh := _clip_pose(bh)
		# the bones' global turns as the clip posed them (the parent's global times the clip's local)
		var pn: Quaternion = _parent_global(bn)
		var gn: Quaternion = pn * ln
		var gh: Quaternion = gn * lh
		if yaw_counter != 0.0:  # A2: take back part of the clip's own head yaw (its facing about the skeleton's up)
			var f: Vector3 = (gh * skeleton.get_bone_global_rest(bh).basis.get_rotation_quaternion().inverse()) * Vector3.BACK
			# A3: scaled by the facing's horizontal length (near +-90 pitch the yaw is arbitrary), low-passed
			var yc: float = atan2(f.x, f.z) * clampf(Vector2(f.x, f.z).length(), 0.0, 1.0)
			_yc = lerpf(_yc, yc, 1.0 - exp(-dt / YAW_COUNTER_TAU)) if _seen > 0 else yc
			hy -= yaw_counter * _yc
		var qn := Quaternion.from_euler(Vector3(-_hp * pitch_neck_share, hy * neck_share, 0.0))
		var qh := Quaternion.from_euler(Vector3(-_hp * (1.0 - pitch_neck_share) - nod, hy * (1.0 - neck_share), -tilt * hy))
		var rn := rest_turn(ln, gn, qn)
		var rh := rest_turn(lh, pn * rn * lh, qh)
		skeleton.set_bone_pose_rotation(bn, rn)
		skeleton.set_bone_pose_rotation(bh, rh)
		_last[bn] = [rn, ln]
		_last[bh] = [rh, lh]
	else:
		var qn := Quaternion.from_euler(Vector3(-_hp * pitch_neck_share, _hy * neck_share, 0.0))
		var qh := Quaternion.from_euler(Vector3(-_hp * (1.0 - pitch_neck_share) - nod, _hy * (1.0 - neck_share), -tilt * _hy))
		_set_rot(_bones["Neck"], qn)
		_set_rot(_bones["Head"], qh)
	var vy: float = _hvy
	var vp: float = _hvp
	var acc := Vector3.ZERO
	if on_clip:
		var m := _head_motion(dt)
		vy = m[0].x
		vp = m[0].y
		acc = m[1]
	for sp: Dictionary in springs:
		var w: float = TAU * float(sp["hz"])
		var st: Vector4 = sp["s"]
		var cv := Vector2(st.z, st.w)
		var g: float = drive(String(sp["name"])) if on_clip else 1.0  # A3
		cv.x += (-w * w * (st.x + g * vy * float(sp["lag"])) + g * accel_gain * acc.x - 2.0 * float(sp["zeta"]) * w * cv.x) * dt
		cv.y += (-w * w * (st.y + g * vp * float(sp["lag"])) + g * accel_gain * (acc.y + 0.5 * acc.z)
			- 2.0 * float(sp["zeta"]) * w * cv.y) * dt
		var sy: float = st.x + cv.x * dt
		var spt: float = st.y + cv.y * dt
		var cap: float = sp["cap"]
		# AL2: max_deg 0 (or none given) holds the spring still; no "no cap". AL6: at the cap the outward velocity
		# is dropped (it kept growing against the clamp and held the spring there), the inward kept
		if absf(sy) >= cap and cv.x * sy > 0.0:
			cv.x = 0.0
		if absf(spt) >= cap and cv.y * spt > 0.0:
			cv.y = 0.0
		sy = clampf(sy, -cap, cap)
		spt = clampf(spt, -cap, cap)
		if cap <= 0.0:
			cv = Vector2.ZERO
		sp["s"] = Vector4(sy, spt, cv.x, cv.y)
		var n: float = float((sp["bones"] as Array).size())
		for bi: int in sp["bones"]:
			_set_rot(bi, Quaternion.from_euler(Vector3(-spt / n, sy / n, 0.0)))
	skeleton.advance(dt)
	if darts > 0.0:  # A2: a new dart now and then, the eyes' target only
		_dart_t -= dt
		if _dart_t <= 0.0:
			_dart_t = _rng.randf_range(0.6, 2.4)
			_dart = Vector2(_rng.randf_range(-1.0, 1.0), _rng.randf_range(-0.6, 0.6)) * deg_to_rad(darts)
		var dd: float = t_local.distance_to(mid)
		t_local += (skeleton.get_bone_global_pose(_bones["Head"]).basis * Vector3(_dart.x, _dart.y, 0.0)) * dd
	# the eyes: toward the target from each posed eye centre, in the posed head's frame, clamped by the lids, leading
	var head_pose: Transform3D = skeleton.get_bone_global_pose(_bones["Head"])
	var head_rest_inv: Transform3D = skeleton.get_bone_global_rest(_bones["Head"]).affine_inverse()
	var posed: Transform3D = head_pose * head_rest_inv  # rest skeleton space -> posed skeleton space
	for side: String in ["left", "right"]:
		if bead:
			break  # no gaze: the catch light stays in the mesh's frame; _apply_eyes moves the eye centres
		var e: Dictionary = eyes[side]
		var c: Vector3 = posed * _v(e["centre"])
		var tl: Vector3 = posed.basis.inverse() * (t_local - c)
		var off := eye_offsets(_v(e["rest"]), tl)  # in the eye's rest frame, where the lid limits were measured
		var lim := clamp_gaze(off.x, off.y, e["limits_deg"])
		if eye_mode == "fixed":  # A3
			lim = Vector2.ZERO
		elif eye_mode == "lead":
			lim = lim.limit_length(deg_to_rad(EYE_LEAD_DEG))
		var s: Vector4 = _eye[side]
		var ry := _damp(s.x, s.z, lim.x, EYE_HZ, dt)
		var rp := _damp(s.y, s.w, lim.y, EYE_HZ, dt)
		_eye[side] = Vector4(ry.x, rp.x, ry.y, rp.y)
	_apply_eyes()


## A1: forget the head's motion history (a jump to another clip, a teleport or a respawn must not kick the springs);
## A3: the next measured step seeds the body's velocity from its raw velocity (zero kicked the springs mid-run).
func reset_motion() -> void:
	_seen = 0
	_mv = Vector2.ZERO
	_ma = Vector3.ZERO
	_last.clear()


## A3: the darts' generator back to rng_seed (a reel starts the same on every run).
func reseed() -> void:
	_rng.seed = rng_seed
	_rng.state = 0
	_dart_t = 0.0
	_seeded = true


## A3: the clip drive's scale for the spring named n (clip_drive's first key that starts it; 1 without one).
func drive(n: String) -> float:
	for k: String in clip_drive:
		if n.begins_with(k):
			return float(clip_drive[k])
	return 1.0


## A2: the springs at rest (between review reels; a respawn).
func reset_springs() -> void:
	for sp: Dictionary in springs:
		sp["s"] = Vector4.ZERO


## A2: the clip's own local rotation of bi: what the skeleton holds, unless that is still the turn this controller
## wrote last step (the clip did not pose the bone again), then the clip's pose that turn went on.
func _clip_pose(bi: int) -> Quaternion:
	var now := skeleton.get_bone_pose_rotation(bi)
	if _last.has(bi) and now.is_equal_approx(_last[bi][0]):
		return _last[bi][1]
	return now


func _parent_global(bi: int) -> Quaternion:
	var p := skeleton.get_bone_parent(bi)
	return skeleton.get_bone_global_pose(p).basis.get_rotation_quaternion() if p >= 0 else Quaternion.IDENTITY


## A1: the head's measured motion since the last step, in its own rest-aligned frame (the springs' frame): [the yaw and
## pitch rates (rad/s; + pitch = the face up, as _hvp), the acceleration (m/s^2; x its left, y up, z forward)], each
## clamped (a loop's seam or a clip's jump is not a hit). A2: low-passed by 1 - exp(-dt / MOTION_TAU), the same at any
## frame rate; the acceleration is the head's in the skeleton's space (the clip's bob, from velocities, so an uneven
## dt does not spike it) plus the change of the skeleton's low-passed world velocity (the body's own travel: a 60 Hz
## physics body drawn at 144 fps moves unevenly from frame to frame).
func _head_motion(dt: float) -> Array:
	var bh: int = _bones["Head"]
	var pose := skeleton.get_bone_global_pose(bh)
	var turn: Quaternion = (skeleton.global_basis.get_rotation_quaternion() * pose.basis.get_rotation_quaternion()
		* skeleton.get_bone_global_rest(bh).basis.get_rotation_quaternion().inverse()).normalized()
	var p: Vector3 = pose.origin
	var bp: Vector3 = skeleton.global_position
	var k: float = 1.0 - exp(-dt / MOTION_TAU)
	var v := Vector2.ZERO
	var a := Vector3.ZERO
	var vs := Vector3.ZERO
	if _seen >= 1:
		var e: Vector3 = (_h_prev.inverse() * turn).normalized().get_euler()
		v = Vector2(clampf(e.y / dt, -6.0, 6.0), clampf(-e.x / dt, -6.0, 6.0))
		vs = (p - _p1) / dt
		var raw: Vector3 = (bp - _body_p) / dt
		_body_v = raw if _seen == 1 else _body_v.lerp(raw, k)  # A3: seeded from the raw velocity after a reset
		if _seen == 1:
			_body_v1 = _body_v
	if _seen >= 2:
		var a_skel: Vector3 = skeleton.global_basis * ((vs - _v1) / dt)
		var a_body: Vector3 = (_body_v - _body_v1) / dt
		a = (turn.inverse() * (a_skel + a_body)).limit_length(30.0)
	_h_prev = turn
	_p1 = p
	_v1 = vs
	_body_p = bp
	_body_v1 = _body_v
	_seen += 1
	_mv = _mv.lerp(v, k)
	_ma = _ma.lerp(a, k)
	return [_mv, _ma]


func _apply_eyes() -> void:
	var posed: Transform3D = skeleton.get_bone_global_pose(_bones["Head"]) * \
		skeleton.get_bone_global_rest(_bones["Head"]).affine_inverse()
	var to_mesh: Transform3D = mesh.global_transform.affine_inverse() * skeleton.global_transform
	for side: String in ["left", "right"]:
		var e: Dictionary = eyes[side]
		var s: Vector4 = _eye[side]
		var g: Vector3 = (to_mesh.basis * posed.basis * gaze_dir(_v(e["rest"]), s.x, s.y)).normalized()
		var c: Vector3 = to_mesh * (posed * _v(e["centre"]))
		if bead:  # AL3: the bead's posed front, which bounds how far the fixed glint may sit (catch_reach)
			g = (to_mesh.basis * posed.basis * _v(e["rest"])).normalized()
		for sm: ShaderMaterial in mats:
			sm.set_shader_parameter("eye_centre_" + side.left(1), c)
			sm.set_shader_parameter("gaze_" + side.left(1), g)


## AL3: how far from the posed bead front the glint may sit (radians): its rest angle plus CATCH_MARGIN, so at rest
## nothing changes and at a head turn the glint slides to the open cap's edge nearest the light (lively.js catchReach).
static func catch_reach(e: Dictionary) -> float:
	var r: Vector3 = _v(e["rest"]).normalized()
	var d: Vector3 = _v(e["catch"]["dir"]).normalized()
	return acos(clampf(r.dot(d), -1.0, 1.0)) + CATCH_MARGIN


## Every spring held at (yf, pf) times its cap (the poke proof, AL2: the gills at their limit corners), no motion.
func hold_springs(yf: float, pf: float) -> void:
	for sp: Dictionary in springs:
		var cap: float = sp["cap"]
		sp["s"] = Vector4(cap * yf, cap * pf, 0.0, 0.0)
		var n: float = float((sp["bones"] as Array).size())
		for bi: int in sp["bones"]:
			_set_rot(bi, Quaternion.from_euler(Vector3(-cap * pf / n, cap * yf / n, 0.0)))
	skeleton.advance(0.0)


## A posed eye's front in mesh space (its centre plus its rest direction times its radius, turned with the head):
## the eye close-ups' middle (AL2: the sphere's centre sits deep inside, so framing on it put the bead off-centre).
func eye_front(side: String) -> Vector3:
	var posed: Transform3D = skeleton.get_bone_global_pose(_bones["Head"]) * \
		skeleton.get_bone_global_rest(_bones["Head"]).affine_inverse()
	var to_mesh: Transform3D = mesh.global_transform.affine_inverse() * skeleton.global_transform
	var e: Dictionary = eyes[side]
	return eye_centre(side) + (to_mesh.basis * posed.basis * _v(e["rest"])).normalized() * float(e["radius"])


## The eye sphere's posed centre in the mesh's frame (AL4: the close-ups frame on the visible cap's middle from it).
func eye_centre(side: String) -> Vector3:
	var posed: Transform3D = skeleton.get_bone_global_pose(_bones["Head"]) * \
		skeleton.get_bone_global_rest(_bones["Head"]).affine_inverse()
	var to_mesh: Transform3D = mesh.global_transform.affine_inverse() * skeleton.global_transform
	return to_mesh * (posed * _v(eyes[side]["centre"]))


## The springs' largest swing now (degrees): the crest's or a gill's turn from its rest, carried by the head.
func crest_swing() -> float:
	var best := 0.0
	for sp: Dictionary in springs:
		var st: Vector4 = sp["s"]
		best = maxf(best, rad_to_deg(Vector2(st.x, st.y).length()))
	return best
