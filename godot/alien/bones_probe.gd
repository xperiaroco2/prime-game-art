extends SceneTree
## B4 review (a), art #196: do the alien heads' spring bones survive the contract's import path? Headless:
##   godot --headless --path godot -s res://alien/bones_probe.gd -- <job.json>
## job.json: {"out": <bones.json>, "heads": {<head>: {"lively": <head>_char_lively.json, "variants": {<name>: res
## path}}}}, the first variant the plain import. Per variant: the skeleton's bones; the lively controller
## (alien_lively.gd) driving the springs for SECONDS under the idle clip, the head following a target swept left and
## right: the springs' largest pose angle off their rest, the spring-weighted vertices' largest skinned move off the
## rest pose and, against the first variant at the same frames, their largest difference; the Head bone's global scale
## over one breath (alien_lively.BREATH_S) with the head held and following; per clip its tracks that name no bone and
## its largest bone turn between 0 and half its length.

const Lively = preload("res://alien/alien_lively.gd")
const Character = preload("res://lib/character.gd")
const FPS := 30.0
const SECONDS := 3.0
const SAMPLE := 6  # skinned points every SAMPLE frames


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var report := {}
	for head: String in job["heads"]:
		var h: Dictionary = job["heads"][head]
		var lively: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(h["lively"]))
		var first: Array = []
		report[head] = {}
		for variant: String in h["variants"]:
			var r: Dictionary = await _probe(h["variants"][variant], lively, first)
			report[head][variant] = r
			print("BONES %s %s: %d bones, springs %s deg, spring vertices %s mm (against the plain import %s mm), head scale %s %%"
				% [head, variant, r.get("bone_count", 0), r.get("spring_max_deg"), r.get("spring_move_max_mm"),
				r.get("against_first_mm"), r.get("head_scale_range_pct")])
	var f := FileAccess.open(job["out"], FileAccess.WRITE)
	f.store_string(JSON.stringify(report, " "))
	f.close()
	quit(0)


func _probe(res: String, lively: Dictionary, first: Array) -> Dictionary:
	var scene: PackedScene = load(res)
	if scene == null:
		return {"error": "cannot load " + res}
	var ch: Node3D = scene.instantiate()
	root.add_child(ch)
	await process_frame  # in the tree before any global transform
	var sk: Skeleton3D = ch.find_children("*", "Skeleton3D", true, false)[0]
	var mesh: MeshInstance3D = ch.find_children("*", "MeshInstance3D", true, false)[0]
	var ap: AnimationPlayer = ch.find_children("*", "AnimationPlayer", true, false)[0] if not ch.find_children("*", "AnimationPlayer", true, false).is_empty() else null
	var bones: Array = []
	for i: int in sk.get_bone_count():
		bones.append(sk.get_bone_name(i))
	var out := {"bones": bones, "bone_count": bones.size()}
	var specs: Array = lively["rig"].get("springs", [])
	var spring_names: Array = []
	for sp: Dictionary in specs:
		spring_names.append_array(sp["bones"])
	out["springs_found"] = spring_names.filter(func(b: String) -> bool: return sk.find_bone(b) >= 0)
	# the clips: tracks naming no bone, the largest turn between 0 and half the length
	var clips := {}
	if ap != null:
		for n: String in ap.get_animation_list():
			var a: Animation = ap.get_animation(n)
			var lost := 0
			for t: int in a.get_track_count():
				var p: NodePath = a.track_get_path(t)
				if p.get_subname_count() > 0 and sk.find_bone(p.get_concatenated_subnames()) < 0:
					lost += 1
			ap.play(n)
			ap.seek(0.0, true)
			var q0: Array = []
			for i: int in sk.get_bone_count():
				q0.append(sk.get_bone_pose_rotation(i))
			ap.seek(a.length * 0.5, true)
			var most := 0.0
			for i: int in sk.get_bone_count():
				most = maxf(most, rad_to_deg((q0[i] as Quaternion).angle_to(sk.get_bone_pose_rotation(i))))
			clips[n] = {"tracks": a.get_track_count(), "unresolved": lost, "turn_deg": snappedf(most, 0.1)}
	out["clips"] = clips
	var idle := ""
	for n: String in clips:
		if n.ends_with("Idle") and not n.contains("Crouch"):
			idle = n
	if ap != null and idle != "":
		ap.play(idle)
		ap.seek(0.0, true)
	sk.reset_bone_poses()
	var owners: PackedStringArray = Character.dominant_bones(mesh)
	var idx: Array[int] = []
	for i: int in owners.size():
		if owners[i] in spring_names:
			idx.append(i)
	var rest: PackedVector3Array = Character.skinned_points(mesh)
	var live = Lively.new(ch, [] as Array[ShaderMaterial], lively, null)
	var mid: Vector3 = (Lively._v(lively["eyes"]["left"]["centre"]) + Lively._v(lively["eyes"]["right"]["centre"])) * 0.5
	live.head_follow = 1.0
	live.breathing = 1.0
	var best := 0.0
	var move := 0.0
	var against := 0.0
	var k := 0
	for i: int in int(SECONDS * FPS):
		var t: float = i / FPS
		live.target = mid + Vector3(1.5 * sin(TAU * 0.7 * t), 0.3 * sin(TAU * 0.3 * t), 2.0)
		if ap != null:
			ap.advance(1.0 / FPS)
		live.step(1.0 / FPS)
		for b: String in spring_names:
			var bi: int = sk.find_bone(b)
			if bi >= 0:
				best = maxf(best, rad_to_deg(sk.get_bone_pose_rotation(bi).angle_to(sk.get_bone_rest(bi).basis.get_rotation_quaternion())))
		if i % SAMPLE == 0 and not idx.is_empty():
			var pts: PackedVector3Array = Character.skinned_points(mesh)
			var hb: Transform3D = sk.get_bone_global_pose(sk.find_bone("Head"))
			var hr: Transform3D = sk.get_bone_global_rest(sk.find_bone("Head"))
			var sample := PackedVector3Array()
			for j: int in idx:
				var local: Vector3 = hb.affine_inverse() * pts[j]  # in the head's frame: the springs' own move
				sample.append(local)
				move = maxf(move, local.distance_to(hr.affine_inverse() * rest[j]))
			if first.size() <= k:
				first.append(sample)
			else:
				var f: PackedVector3Array = first[k]
				for j: int in mini(f.size(), sample.size()):
					against = maxf(against, f[j].distance_to(sample[j]))
			k += 1
	out["spring_max_deg"] = snappedf(best, 0.01)
	out["spring_vertices"] = idx.size()
	out["spring_move_max_mm"] = snappedf(move * 1000.0, 0.1)
	out["against_first_mm"] = snappedf(against * 1000.0, 0.01)
	# the Head bone's global scale over one breath, held and following
	var hi: int = sk.find_bone("Head")
	var ranges := {}
	for follow: float in [0.0, 1.0]:
		live.head_follow = follow
		var lo := Vector3(INF, INF, INF)
		var up := Vector3(-INF, -INF, -INF)
		for i: int in int(Lively.BREATH_S * FPS) + 1:
			var t: float = i / FPS
			live.target = mid + Vector3(1.5 * sin(TAU * 0.7 * t), 0.3 * sin(TAU * 0.3 * t), 2.0)
			if ap != null:
				ap.advance(1.0 / FPS)
			live.step(1.0 / FPS)
			var sc: Vector3 = (sk.global_transform * sk.get_bone_global_pose(hi)).basis.get_scale()
			lo = lo.min(sc)
			up = up.max(sc)
		ranges["follow" if follow > 0.0 else "held"] = snappedf(maxf(maxf((up.x - lo.x) / lo.x, (up.y - lo.y) / lo.y), (up.z - lo.z) / lo.z) * 100.0, 0.001)
	out["head_scale_range_pct"] = ranges
	ch.queue_free()
	return out
