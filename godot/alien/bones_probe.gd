extends SceneTree
## B4 review (a), art #196: do the alien heads' spring bones survive the contract's import path? Headless:
##   godot --headless --path godot -s res://alien/bones_probe.gd -- <job.json>
## job.json: {"out": <bones.json>, "heads": {<head>: {"lively": <head>_char_lively.json, "variants": {<name>: res
## path}}}}, the first variant the plain import. Per variant: the skeleton's bones; the lively controller
## (alien_lively.gd) driving the springs for SECONDS under the idle clip, the head following a target swept left and
## right: the springs' largest pose angle off their rest (an echo of what alien_lively writes, the same in every
## import by construction); the spring-weighted vertices' head-relative motion as vectors in rest world space
## (W hr * ((W hb)^-1 * p) - rest, W the Skeleton3D's global transform: skinned_points are world space, the bone
## poses skeleton space; a frame both imports share), its largest length and, against the first
## variant at the same frames, the largest vector difference (mm) and the angle between the swing directions (max over
## the vertices moving at least MIN_SWING_MM in both, and the motion-weighted mean); the Head bone's global scale
## over one breath (alien_lively.BREATH_S) with the head held and following; per clip its tracks that name no bone and
## its largest bone turn between 0 and half its length. B6 (the frames): against the first variant, the largest
## rest-point difference over every vertex by index and whether the spring-weighted vertex lists are equal (the
## BoneMap import reorders the vertices: the spring vertices are then paired by rest position, the largest pairing
## distance reported; a vertex count mismatch or an unpaired vertex is an error and the run exits 1, no truncation);
## the Skeleton3D's global rotation, and per spring
## bone the turn between the two imports' local rests and between their world rests.

const Lively = preload("res://alien/alien_lively.gd")
const Character = preload("res://lib/character.gd")
const FPS := 30.0
const SECONDS := 3.0
const SAMPLE := 6  # skinned points every SAMPLE frames
const MIN_SWING_MM := 2.0  # the swing angle only where both imports move at least this
const MATCH_MM := 0.5  # a spring vertex paired across imports by its rest position, at most this far


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var report := {}
	var failed := false
	for head: String in job["heads"]:
		var h: Dictionary = job["heads"][head]
		var lively: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(h["lively"]))
		var first := {}
		report[head] = {}
		for variant: String in h["variants"]:
			var r: Dictionary = await _probe(h["variants"][variant], lively, first)
			report[head][variant] = r
			print("BONES %s %s: %d bones, springs %s deg, spring swing %s mm (against the plain import: %s mm apart, directions %s deg max, %s deg mean), head scale %s %%"
				% [head, variant, r.get("bone_count", 0), r.get("spring_max_deg"), r.get("spring_move_max_mm"),
				r.get("against_first_mm"), r.get("swing_angle_max_deg"), r.get("swing_angle_mean_deg"), r.get("head_scale_range_pct")])
			print("FRAME %s %s: skeleton global turn %s deg (against the plain import %s deg), rest points %s mm apart by index and %s mm paired by position, spring vertex lists equal %s, spring bones' local rests %s deg and world rests %s deg apart at most"
				% [head, variant, r.get("skeleton_turn_deg"), r.get("skeleton_turn_vs_first_deg"), r.get("rest_by_index_vs_first_mm"), r.get("rest_paired_vs_first_mm"),
				r.get("spring_idx_equal"), r.get("spring_local_rest_vs_first_deg"), r.get("spring_world_rest_vs_first_deg")])
			if r.has("error"):
				push_error("BONES %s %s: %s" % [head, variant, r["error"]])
				failed = true
	var f := FileAccess.open(job["out"], FileAccess.WRITE)
	f.store_string(JSON.stringify(report, " "))
	f.close()
	quit(1 if failed else 0)


func _probe(res: String, lively: Dictionary, first: Dictionary) -> Dictionary:
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
	var W: Transform3D = sk.global_transform
	var order: Array[int] = idx.duplicate()  # this import's spring vertices in the plain import's order
	out["skeleton_turn_deg"] = snappedf(rad_to_deg(W.basis.get_rotation_quaternion().angle_to(Quaternion.IDENTITY)), 0.01)
	var local_rest := {}
	var world_rest := {}
	for b: String in spring_names:
		var bi: int = sk.find_bone(b)
		if bi >= 0:
			local_rest[b] = sk.get_bone_rest(bi).basis.get_rotation_quaternion()
			world_rest[b] = (W * sk.get_bone_global_rest(bi)).basis.get_rotation_quaternion()
	if first.is_empty():
		first.merge({"rest": rest, "idx": idx, "W": W, "local": local_rest, "world": world_rest, "samples": []})
	else:
		out["skeleton_turn_vs_first_deg"] = snappedf(rad_to_deg(W.basis.get_rotation_quaternion().angle_to((first["W"] as Transform3D).basis.get_rotation_quaternion())), 0.01)
		var r0: PackedVector3Array = first["rest"]
		if r0.size() != rest.size():
			out["error"] = "vertex count %d against the plain import's %d" % [rest.size(), r0.size()]
			ch.queue_free()
			return out
		var rd := 0.0
		for j: int in rest.size():
			rd = maxf(rd, r0[j].distance_to(rest[j]))
		out["rest_by_index_vs_first_mm"] = snappedf(rd * 1000.0, 0.001)
		var idx0: Array[int] = first["idx"]
		out["spring_idx_equal"] = idx == idx0
		if idx.size() != idx0.size():
			out["error"] = "%d spring-weighted vertices against the plain import's %d" % [idx.size(), idx0.size()]
			ch.queue_free()
			return out
		# the import may order the vertices otherwise: each of the plain import's spring vertices paired with this
		# import's nearest spring vertex at rest (a 0.5 mm hash, its 27 cells); none further than MATCH_MM
		var grid := {}
		for j: int in idx:
			var key := Vector3i((rest[j] / 0.0005).floor())
			if not grid.has(key):
				grid[key] = []
			grid[key].append(j)
		var md := 0.0
		order.clear()
		for j0: int in idx0:
			var c := Vector3i((r0[j0] / 0.0005).floor())
			var best_j := -1
			var best_d := INF
			for dx: int in [-1, 0, 1]:
				for dy: int in [-1, 0, 1]:
					for dz: int in [-1, 0, 1]:
						for j: int in grid.get(c + Vector3i(dx, dy, dz), []):
							var d: float = r0[j0].distance_to(rest[j])
							if d < best_d:
								best_d = d
								best_j = j
			if best_j < 0 or best_d * 1000.0 > MATCH_MM:
				out["error"] = "the plain import's spring vertex %d has no spring vertex within %.1f mm here" % [j0, MATCH_MM]
				ch.queue_free()
				return out
			md = maxf(md, best_d)
			order.append(best_j)
		out["rest_paired_vs_first_mm"] = snappedf(md * 1000.0, 0.001)
		var lr := 0.0
		var wr := 0.0
		for b: String in local_rest:
			lr = maxf(lr, rad_to_deg((local_rest[b] as Quaternion).angle_to(first["local"][b])))
			wr = maxf(wr, rad_to_deg((world_rest[b] as Quaternion).angle_to(first["world"][b])))
		out["spring_local_rest_vs_first_deg"] = snappedf(lr, 0.01)
		out["spring_world_rest_vs_first_deg"] = snappedf(wr, 0.01)
	var live = Lively.new(ch, [] as Array[ShaderMaterial], lively, null)
	var mid: Vector3 = (Lively._v(lively["eyes"]["left"]["centre"]) + Lively._v(lively["eyes"]["right"]["centre"])) * 0.5
	live.head_follow = 1.0
	live.breathing = 1.0
	var best := 0.0
	var move := 0.0
	var diff := 0.0
	var angle_max := 0.0
	var angle_sum := 0.0
	var weight := 0.0
	var k := 0
	var hi0: int = sk.find_bone("Head")
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
			var hb: Transform3D = sk.global_transform * sk.get_bone_global_pose(hi0)
			var hr: Transform3D = sk.global_transform * sk.get_bone_global_rest(hi0)
			var sample := PackedVector3Array()
			for j: int in order:
				# the head's own turn taken out, back in the rest pose's world space: the springs' swing alone
				var m: Vector3 = hr * (hb.affine_inverse() * pts[j]) - rest[j]
				sample.append(m)
				move = maxf(move, m.length())
			var samples: Array = first["samples"]
			if samples.size() <= k:
				samples.append(sample)
			else:
				var f: PackedVector3Array = samples[k]
				for j: int in f.size():  # equal sizes: the lists were checked above
					diff = maxf(diff, f[j].distance_to(sample[j]))
					if f[j].length() * 1000.0 >= MIN_SWING_MM and sample[j].length() * 1000.0 >= MIN_SWING_MM:
						var a: float = rad_to_deg(f[j].angle_to(sample[j]))
						angle_max = maxf(angle_max, a)
						angle_sum += a * f[j].length()
						weight += f[j].length()
			k += 1
	out["spring_max_deg"] = snappedf(best, 0.01)
	out["spring_vertices"] = idx.size()
	out["spring_move_max_mm"] = snappedf(move * 1000.0, 0.1)
	out["against_first_mm"] = snappedf(diff * 1000.0, 0.01)
	out["swing_angle_max_deg"] = snappedf(angle_max, 0.01)
	out["swing_angle_mean_deg"] = snappedf(angle_sum / weight, 0.01) if weight > 0.0 else 0.0
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
