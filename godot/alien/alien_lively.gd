extends RefCounted
## The static premium head made lively (art #196, lively): the eyes look at a target (alien_static.gdshader's
## procedural iris on the fitted eye spheres, clamped to what the lids leave open), the head turns toward it with a
## lag and limits (Neck and Head bones, eyes leading), the crest springs (a SpringBoneSimulator3D on Crest1-3) and the
## chest breathes. No face rig: the sculpt never deforms above the neck except the crest.
## The head's skin and data come from tools/blender/alien_lively_build.py (`<name>_lively.glb`, `lively.json`,
## `<name>_sclera.png`). Use with preload:
##   const Lively = preload("res://alien/alien_lively.gd")
##   var live := Lively.new(head_scene_root, mats, lively_json_dict, sclera_texture)
##   live.target = some_global_position; live.step(delta)  # each frame (it advances the skeleton itself)
## The gaze maths repeat tools/blender/alien_lively_geom.py (eye_frame, gaze_dir, gaze_offsets, clamp_gaze).

const YAW_LIMIT := deg_to_rad(35.0)
const PITCH_LIMIT := deg_to_rad(20.0)
const EYE_LIMIT := deg_to_rad(25.0)  # the lids' clamp, capped
const NECK_SHARE := 0.4  # of the head's turn; the Head bone takes the rest
const HEAD_HZ := 1.6  # the head's critically damped follow (lags)
const EYE_HZ := 9.0  # the eyes' (lead)
const BREATH_S := 4.4  # one breath
const BREATH_CHEST := Vector3(0.006, 0.004, 0.010)  # the chest's scale at the top of a breath (x, y, z)
const BREATH_NOD := deg_to_rad(0.6)  # the head's bob with it
const CREST_STIFFNESS := 1.2
const CREST_DRAG := 0.35

var target := Vector3(0.0, 0.0, 10.0)
var head_follow := 1.0  # 0 holds the head (the eyes alone), 1 follows
var breathing := 1.0
var skeleton: Skeleton3D
var mesh: MeshInstance3D
var springs: SpringBoneSimulator3D
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
	for b: String in ["Chest", "Neck", "Head", "Crest1", "Crest2", "Crest3"]:
		_bones[b] = skeleton.find_bone(b)
		if _bones[b] < 0:
			push_error("LIVELY no bone %s" % b)
	skeleton.modifier_callback_mode_process = Skeleton3D.MODIFIER_CALLBACK_MODE_PROCESS_MANUAL
	springs = SpringBoneSimulator3D.new()
	springs.name = "CrestSprings"
	springs.set_setting_count(1)
	var seg: float = skeleton.get_bone_global_rest(_bones["Crest3"]).origin.distance_to(
		skeleton.get_bone_global_rest(_bones["Crest2"]).origin)
	springs.set_root_bone_name(0, "Crest1")
	springs.set_end_bone_name(0, "Crest3")
	springs.set_extend_end_bone(0, true)
	springs.set_end_bone_direction(0, 6)  # SpringBoneSimulator3D.BONE_DIRECTION_FROM_PARENT
	springs.set_end_bone_length(0, seg)
	springs.set_stiffness(0, CREST_STIFFNESS)
	springs.set_drag(0, CREST_DRAG)
	springs.set_gravity(0, 0.0)
	springs.set_radius(0, seg * 0.1)
	skeleton.add_child(springs)
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
	time += dt
	var to_skel: Transform3D = skeleton.global_transform.affine_inverse()
	var t_local: Vector3 = to_skel * target
	# the head: toward the target from between the eyes at rest, clamped, lagging
	var mid: Vector3 = (_v(eyes["left"]["centre"]) + _v(eyes["right"]["centre"])) * 0.5
	var d := t_local - mid
	var gy: float = clampf(atan2(d.x, d.z), -YAW_LIMIT, YAW_LIMIT) * head_follow
	var gp: float = clampf(atan2(d.y, Vector2(d.x, d.z).length()), -PITCH_LIMIT, PITCH_LIMIT) * head_follow
	var r := _damp(_hy, _hvy, gy, HEAD_HZ, dt)
	_hy = r.x
	_hvy = r.y
	r = _damp(_hp, _hvp, gp, HEAD_HZ, dt)
	_hp = r.x
	_hvp = r.y
	var b: float = (0.5 - 0.5 * cos(TAU * time / BREATH_S)) * breathing
	var nod: float = BREATH_NOD * sin(TAU * time / BREATH_S - 0.6) * breathing
	var chest := Vector3.ONE + BREATH_CHEST * b
	skeleton.set_bone_pose_scale(_bones["Chest"], chest)
	skeleton.set_bone_pose_scale(_bones["Neck"], Vector3.ONE / chest)  # the head keeps its size
	skeleton.set_bone_pose_rotation(_bones["Neck"], Quaternion.from_euler(Vector3(-_hp * NECK_SHARE, _hy * NECK_SHARE, 0.0)))
	skeleton.set_bone_pose_rotation(_bones["Head"],
		Quaternion.from_euler(Vector3(-_hp * (1.0 - NECK_SHARE) - nod, _hy * (1.0 - NECK_SHARE), 0.0)))
	skeleton.advance(dt)
	# the eyes: toward the target from each posed eye centre, in the posed head's frame, clamped by the lids, leading
	var head_pose: Transform3D = skeleton.get_bone_global_pose(_bones["Head"])
	var head_rest_inv: Transform3D = skeleton.get_bone_global_rest(_bones["Head"]).affine_inverse()
	var posed: Transform3D = head_pose * head_rest_inv  # rest skeleton space -> posed skeleton space
	for side: String in ["left", "right"]:
		var e: Dictionary = eyes[side]
		var c: Vector3 = posed * _v(e["centre"])
		var tl: Vector3 = posed.basis.inverse() * (t_local - c)
		var lim := clamp_gaze(atan2(tl.x, tl.z), atan2(tl.y, Vector2(tl.x, tl.z).length()), e["limits_deg"])
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
			sm.set_shader_parameter("gaze_" + side.left(1), g)


## The crest tip's swing now: the angle (degrees) between Crest3's posed direction and its rest one carried by the head.
func crest_swing() -> float:
	var posed: Transform3D = skeleton.get_bone_global_pose(_bones["Head"]) * \
		skeleton.get_bone_global_rest(_bones["Head"]).affine_inverse()
	var rest_dir: Vector3 = posed.basis * skeleton.get_bone_global_rest(_bones["Crest3"]).origin - \
		posed.basis * skeleton.get_bone_global_rest(_bones["Crest2"]).origin
	var now: Vector3 = skeleton.get_bone_global_pose(_bones["Crest3"]).origin - \
		skeleton.get_bone_global_pose(_bones["Crest2"]).origin
	return rad_to_deg(rest_dir.angle_to(now))
