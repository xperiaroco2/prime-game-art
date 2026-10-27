extends SceneTree
## The photo poses' layers check (art #196), headless: tools/blender/alien_poses_run.py --check writes the job and runs
## this. Per character (the job's "chars": {glb, ref, out}):
## - pose_layers.gd plays every pair of the reference (the 48) as its two filtered layers; each bone's head in the
##   skeleton's space against the Blender-composed pose (the ref: the plain-Python composition of the same clips,
##   equal to Blender's evaluated pose; heads in glTF axes), the largest error in cm, a failure over TOL_CM;
## - the pair holds: the same pose after the tree has run 0.7 s more (HOLD_CM);
## - stop() hands the skeleton back to the player (Idle plays again);
## - the head look (head_look.gd) on the contact pairs at yaw -70 and +70 per split (the modifier's defaults; Neck and
##   Head only): how far each contact slides, the hand (or fingertip) in its target bone's frame against no look, cm.
## Prints POSES {json} per character and POSES_RESULT pass|FAIL; exit 1 on a failure. Args after "--": <job.json>

const PoseLayers = preload("res://alien/pose_layers.gd")
const HeadLook = preload("res://alien/head_look.gd")
const TOL_CM := 0.5
const HOLD_CM := 0.01
const SPLITS := {
	"default": {},
	"neck_head": {"yaw_split": {"Neck": 0.4, "Head": 0.6}, "pitch_split": {"Neck": 0.4, "Head": 0.6}},
}
## [pair, the moving point's bone, the bone whose frame it should keep to]
const CONTACTS := [
	["Stand+HandsOnHips", "LeftHand", "Hips"], ["Stand+HandsOnHips", "RightHand", "Hips"],
	["Lunge+FingerUp", "LeftHand", "Hips"],
	["Sit+HandsBehindHead", "LeftHand", "Head"], ["Sit+HandsBehindHead", "RightHand", "Head"],
	["Stand+Salute", "RightIndexDistal", "Head"], ["Stand+Salute", "LeftHand", "Hips"],
	["Kneel+Heart", "LeftIndexDistal", "RightIndexDistal"],
	["OneLeg+Plane", "LeftHand", "Hips"],
]

var _sk: Skeleton3D
var _snap := {}


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	var ok := true
	for c: Dictionary in job["chars"]:
		var r: Dictionary = await _check(c)
		FileAccess.open(c["out"], FileAccess.WRITE).store_string(JSON.stringify(r, " "))
		r.erase("pairs")
		print("POSES ", JSON.stringify(r))
		ok = ok and r["fails"].is_empty()
	print("POSES_RESULT ", "pass" if ok else "FAIL")
	quit(0 if ok else 1)


func _heads() -> Dictionary:
	var out := {}
	for b: int in _sk.get_bone_count():
		out[_sk.get_bone_name(b)] = _sk.get_bone_global_pose(b)
	return out


func _on_done() -> void:
	_snap = _heads()


func _check(c: Dictionary) -> Dictionary:
	var ref: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(c["ref"]))
	var ch: Node3D = (load(c["glb"]) as PackedScene).instantiate()
	root.add_child(ch)
	_sk = ch.find_children("*", "Skeleton3D", true, false)[0]
	var ap: AnimationPlayer = ch.find_children("*", "AnimationPlayer", true, false)[0]
	ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var layers = PoseLayers.new()
	ch.add_child(layers)
	layers.setup(ap)
	var r := {"glb": c["glb"], "tol_cm": TOL_CM, "poses": layers.poses(), "pairs": {}, "max_err_cm": 0.0,
		"worst": "", "hold_max_cm": 0.0, "fails": [], "look": {}}
	# the player's Idle before any pose: what stop() must give back (every bone's position and rotation)
	var idle: String = "CharacterArmature|Idle_Loop" if ap.has_animation("CharacterArmature|Idle_Loop") else ap.get_animation_list()[0]
	ap.play(idle)
	ap.seek(0.0, true)
	await process_frame
	var idle_ref := _heads()
	for pair: String in ref["pairs"]:
		var p: Dictionary = ref["pairs"][pair]
		if not layers.play_pair(p["legs"], p["arms"]):
			r["fails"].append("%s: a clip is missing" % pair)
			continue
		await process_frame
		var got := _heads()
		var worst := 0.0
		var wb := ""
		for b: String in p["heads"]:
			var v: Array = p["heads"][b]
			var e: float = (got[b].origin - Vector3(v[0], v[1], v[2])).length() * 100.0
			if e > worst:
				worst = e
				wb = b
		layers.tree.advance(0.7)
		await process_frame
		var held := _heads()
		var hold := 0.0
		for b: String in held:
			hold = maxf(hold, (held[b].origin - got[b].origin).length() * 100.0)
		r["pairs"][pair] = {"max_err_cm": snappedf(worst, 0.0001), "bone": wb, "hold_cm": snappedf(hold, 0.0001)}
		if worst > r["max_err_cm"]:
			r["max_err_cm"] = snappedf(worst, 0.0001)
			r["worst"] = "%s %s" % [pair, wb]
		r["hold_max_cm"] = maxf(r["hold_max_cm"], snappedf(hold, 0.0001))
		if worst > TOL_CM:
			r["fails"].append("%s: %s off by %.3f cm" % [pair, wb, worst])
		if hold > HOLD_CM:
			r["fails"].append("%s: moves %.3f cm while held" % [pair, hold])
	# stop() gives the skeleton back to the player
	layers.stop()
	ap.play(idle)
	ap.seek(0.0, true)
	await process_frame
	var back := _heads()
	var back_cm := 0.0
	var back_deg := 0.0
	for b: String in idle_ref:  # every bone, the leaves (toes, eyes, jaw, fingertips) too: a channel leak shows
		back_cm = maxf(back_cm, (back[b].origin - idle_ref[b].origin).length() * 100.0)
		back_deg = maxf(back_deg, rad_to_deg((idle_ref[b].basis.inverse() * back[b].basis).get_rotation_quaternion().get_angle()))
	r["stop_back_cm"] = snappedf(back_cm, 0.0001)
	r["stop_back_deg"] = snappedf(back_deg, 0.0001)
	r["stop_gives_back"] = not layers.is_posing() and back_cm < 0.001 and back_deg < 0.01
	if not r["stop_gives_back"]:
		r["fails"].append("stop() did not give the skeleton back")
	# the head look on the contact pairs
	var m: SkeletonModifier3D = HeadLook.new()
	m.smoothing_s = 0.0
	_sk.add_child(m)
	m.modification_processed.connect(_on_done)
	var keep := {"yaw_split": m.yaw_split, "pitch_split": m.pitch_split}
	for split: String in SPLITS:
		for k: String in keep:
			m.set(k, SPLITS[split].get(k, keep[k]))
		var rows := []
		for cs: Array in CONTACTS:
			var lr: PackedStringArray = (cs[0] as String).split("+")
			layers.play_pair(lr[0], lr[1])
			var at := {}
			for yaw: float in [0.0, -70.0, 70.0]:
				m.aim_yaw = deg_to_rad(yaw)
				m.aim_pitch = 0.0
				m.snap()
				for _i: int in 3:
					await process_frame
				var a: Transform3D = _snap[cs[1]]
				var t: Transform3D = _snap[cs[2]]
				at[yaw] = t.affine_inverse() * a.origin
			rows.append({"pair": cs[0], "point": cs[1], "frame": cs[2],
				"slide_cm_-70": snappedf((at[-70.0] - at[0.0]).length() * 100.0, 0.01),
				"slide_cm_+70": snappedf((at[70.0] - at[0.0]).length() * 100.0, 0.01)})
		r["look"][split] = rows
	m.aim_yaw = 0.0
	layers.stop()
	ch.queue_free()
	await process_frame
	return r
