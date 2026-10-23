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

const EYE_LIMIT := deg_to_rad(25.0)  # the lids' clamp, capped
const EYE_HZ := 9.0  # the eyes' (lead)
const BREATH_S := 4.4  # one breath
const BREATH_CHEST := Vector3(0.006, 0.004, 0.010)  # the chest's scale at the top of a breath (x, y, z)
const BREATH_NOD := deg_to_rad(0.6)  # the head's bob with it
# the head's critically damped follow per head, from lively.json's controller (the chameleon: gaze "iris", 1.6 Hz,
# yaw 35, pitch 20; the axolotl: gaze "none", its dark beads show no turn, so the head leads: 2.2 Hz, yaw 40, pitch 24);
# neck_share of the turn in Neck, the rest in Head
var yaw_limit := deg_to_rad(35.0)
var pitch_limit := deg_to_rad(20.0)
var neck_share := 0.4
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


func _init(root: Node, materials: Array[ShaderMaterial], lively: Dictionary, sclera: Texture2D) -> void:
	skeleton = root.find_children("*", "Skeleton3D", true, false)[0]
	mesh = root.find_children("*", "MeshInstance3D", true, false)[0]
	mats = materials
	eyes = lively["eyes"]
	var ctl: Dictionary = lively.get("controller", {"gaze": "iris", "head_hz": 1.6, "yaw_deg": 35.0, "pitch_deg": 20.0,
		"neck_share": 0.4})
	yaw_limit = deg_to_rad(float(ctl["yaw_deg"]))
	pitch_limit = deg_to_rad(float(ctl["pitch_deg"]))
	neck_share = float(ctl["neck_share"])
	head_hz = float(ctl["head_hz"])
	bead = ctl["gaze"] == "none"
	var specs: Array = lively["rig"].get("springs", [{"name": "crest", "bones": ["Crest1", "Crest2", "Crest3"],
		"hz": 2.2, "zeta": 0.3, "lag": 0.09, "max_deg": 30.0}])
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
	dt = minf(dt, 0.05)  # a hitch frame must not kick the crest spring (as the web)
	time += dt
	var to_skel: Transform3D = skeleton.global_transform.affine_inverse()
	var t_local: Vector3 = to_skel * target
	# the head: toward the target from between the eyes at rest, clamped, lagging
	var mid: Vector3 = (_v(eyes["left"]["centre"]) + _v(eyes["right"]["centre"])) * 0.5
	var d := t_local - mid
	var gy: float = clampf(atan2(d.x, d.z), -yaw_limit, yaw_limit) * head_follow
	var gp: float = clampf(atan2(d.y, Vector2(d.x, d.z).length()), -pitch_limit, pitch_limit) * head_follow
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
	skeleton.set_bone_pose_rotation(_bones["Neck"], Quaternion.from_euler(Vector3(-_hp * neck_share, _hy * neck_share, 0.0)))
	skeleton.set_bone_pose_rotation(_bones["Head"],
		Quaternion.from_euler(Vector3(-_hp * (1.0 - neck_share) - nod, _hy * (1.0 - neck_share), 0.0)))
	for sp: Dictionary in springs:
		var w: float = TAU * float(sp["hz"])
		var st: Vector4 = sp["s"]
		var cv := Vector2(st.z, st.w)
		cv.x += (-w * w * (st.x + _hvy * float(sp["lag"])) - 2.0 * float(sp["zeta"]) * w * cv.x) * dt
		cv.y += (-w * w * (st.y + _hvp * float(sp["lag"])) - 2.0 * float(sp["zeta"]) * w * cv.y) * dt
		var sy: float = st.x + cv.x * dt
		var spt: float = st.y + cv.y * dt
		var cap: float = sp["cap"]
		sy = clampf(sy, -cap, cap)  # AL2: max_deg 0 (or none given) holds the spring still; no "no cap"
		spt = clampf(spt, -cap, cap)
		if cap <= 0.0:
			cv = Vector2.ZERO
		sp["s"] = Vector4(sy, spt, cv.x, cv.y)
		var n: float = float((sp["bones"] as Array).size())
		for bi: int in sp["bones"]:
			skeleton.set_bone_pose_rotation(bi, Quaternion.from_euler(Vector3(-spt / n, sy / n, 0.0)))
	skeleton.advance(dt)
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
		var s: Vector4 = _eye[side]
		var ry := _damp(s.x, s.z, lim.x, EYE_HZ, dt)
		var rp := _damp(s.y, s.w, lim.y, EYE_HZ, dt)
		_eye[side] = Vector4(ry.x, rp.x, ry.y, rp.y)
	_apply_eyes()


func _apply_eyes() -> void:
	var posed: Transform3D = skeleton.get_bone_global_pose(_bones["Head"]) * \
		skeleton.get_bone_global_rest(_bones["Head"]).affine_inverse()
	var to_mesh: Transform3D = mesh.global_transform.affine_inverse() * skeleton.global_transform
	for side: String in ["left", "right"]:
		var e: Dictionary = eyes[side]
		var s: Vector4 = _eye[side]
		var g: Vector3 = (to_mesh.basis * posed.basis * gaze_dir(_v(e["rest"]), s.x, s.y)).normalized()
		var c: Vector3 = to_mesh * (posed * _v(e["centre"]))
		for sm: ShaderMaterial in mats:
			sm.set_shader_parameter("eye_centre_" + side.left(1), c)
			if not bead:
				sm.set_shader_parameter("gaze_" + side.left(1), g)


## Every spring held at (yf, pf) times its cap (the poke proof, AL2: the gills at their limit corners), no motion.
func hold_springs(yf: float, pf: float) -> void:
	for sp: Dictionary in springs:
		var cap: float = sp["cap"]
		sp["s"] = Vector4(cap * yf, cap * pf, 0.0, 0.0)
		var n: float = float((sp["bones"] as Array).size())
		for bi: int in sp["bones"]:
			skeleton.set_bone_pose_rotation(bi, Quaternion.from_euler(Vector3(-cap * pf / n, cap * yf / n, 0.0)))
	skeleton.advance(0.0)


## A posed eye's front in mesh space (its centre plus its rest direction times its radius, turned with the head):
## the eye close-ups' middle (AL2: the sphere's centre sits deep inside, so framing on it put the bead off-centre).
func eye_front(side: String) -> Vector3:
	var posed: Transform3D = skeleton.get_bone_global_pose(_bones["Head"]) * \
		skeleton.get_bone_global_rest(_bones["Head"]).affine_inverse()
	var to_mesh: Transform3D = mesh.global_transform.affine_inverse() * skeleton.global_transform
	var e: Dictionary = eyes[side]
	var c: Vector3 = to_mesh * (posed * _v(e["centre"]))
	return c + (to_mesh.basis * posed.basis * _v(e["rest"])).normalized() * float(e["radius"])


## The springs' largest swing now (degrees): the crest's or a gill's turn from its rest, carried by the head.
func crest_swing() -> float:
	var best := 0.0
	for sp: Dictionary in springs:
		var st: Vector4 = sp["s"]
		best = maxf(best, rad_to_deg(Vector2(st.x, st.y).length()))
	return best
