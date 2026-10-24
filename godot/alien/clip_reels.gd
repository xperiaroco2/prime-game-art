extends "res://alien/char_shots.gd"
## Every clip the bare alien carries, in motion (art #196, A1): tools/blender/alien_clip_run.py writes the job (the
## same per-head entries as char_shots.gd's, plus "frames" and "sheet_out") and runs this in the runner's off-screen
## window. Per head and clip:
## - <frames>/<head>_<clip>/0000.png...: 1280x720 at 24 fps, the camera at 3/4 front (35 degrees) framed to the clip's
##   whole motion (every bone over 48 samples, the head's top, the floor), fixed for the clip, over a grey floor; loops twice (at least
##   3 s), one-shots once with a 0.4 s hold at each end; the lively controller on (the eyes follow a slow target, the
##   head follows it at head_follow 0.5, breathing, the springs);
## - clips_<head>.jpg: one row per clip, six phases each, each row framed to its clip;
## - reels.json: per clip the length, the loop seam (the largest bone turn between the last and first frame), the
##   lowest skinned vertex (cm; below 0 through the floor), the feet's slide while planted (cm/s; an in-place loop's
##   planted foot moves at the travel speed), the hands' vertices near the trunk or legs (the share within 1.5 cm), the
##   fingers' curl (degrees), the springs' largest swing and jitter, the Neck and Head's turn from the clip's own.
## The lively controller runs with on_clip (A1) when it has it, unless the job says "on_clip": false.
## A2: with "split": true in the job each reel frame is a 2x2 of 640x360 views (three-quarter front, the left side, the
## back, a close-up of the head and hands following the chest), the sheet's cells stay the three-quarter view; per
## clip in "head60" (Jog_Fwd, Sprint_Fwd) a second reel <head>_<clip>_head60 at 60 fps of the head alone (the gills'
## and the crest's jitter); "yaw_counter" per clip (the locomotion) and "darts" go to the controller when it has them.
## Args after "--": <job.json>

const Char = preload("res://lib/character.gd")
const REEL := Vector2i(1280, 720)
const PH := Vector2i(212, 212)
const HALF := Vector2i(640, 360)
const LOCOMOTION := ["Walk", "Jog_Fwd", "Sprint_Fwd", "Crouch_Fwd"]
const ARM_PARTS := ["Hand", "Thumb", "Index", "Middle", "Ring", "Little"]
const CORE_SKIP := ["UpperArm", "LowerArm", "Shoulder", "Hand", "Thumb", "Index", "Middle", "Ring", "Little", "Head",
	"Neck", "Eye", "Jaw"]


func _run() -> void:
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	var out: String = job["out"]
	_stage(job["hdri"])
	_apply_fix(job.get("fix", {}))
	var ground := MeshInstance3D.new()  # a floor at y = 0 to judge the feet against (sliding, floating, sinking)
	var plane := PlaneMesh.new()
	plane.size = Vector2(60.0, 60.0)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.33, 0.34, 0.36)
	gm.roughness = 0.9
	plane.material = gm
	ground.mesh = plane
	root.add_child(ground)
	var report := {}
	for name: String in (job["heads"] as Dictionary):
		var h: Dictionary = job["heads"][name]
		var ch: Node3D = (load(h["char"]) as PackedScene).instantiate()
		root.add_child(ch)
		var lively: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(h["lively"]))
		var mats := _setup(ch, h, true)
		var live = Lively.new(ch, mats, lively, _texture(h["sclera"]))
		var sk: Skeleton3D = ch.find_children("*", "Skeleton3D", true, false)[0]
		var ap: AnimationPlayer = ch.find_children("*", "AnimationPlayer", true, false)[0]
		ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
		var mesh: MeshInstance3D = Char.meshes(ch)[0]
		for m: MeshInstance3D in Char.meshes(ch):
			if m.mesh.get_surface_count() > mesh.mesh.get_surface_count():
				mesh = m
		var dom: PackedStringArray = Char.dominant_bones(mesh)
		var hand_i := PackedInt32Array()
		var core_i := PackedInt32Array()
		for i: int in range(0, dom.size(), 2):
			var b: String = dom[i]
			if _has_any(b, ARM_PARTS):
				hand_i.append(i)
			elif b != "" and not _has_any(b, CORE_SKIP) and sk.find_bone(b) >= 0 and not live.springs.any(
					func(sp: Dictionary) -> bool: return sk.find_bone(b) in (sp["bones"] as Array)):
				core_i.append(i)
		var fit: Dictionary = h["fit"]
		var top: float = fit["top_z"]
		var head_bi: int = sk.find_bone("Head")
		var head_top: float = top - (sk.global_transform * sk.get_bone_global_rest(head_bi)).origin.y
		var mid: Vector3 = (Lively._v(lively["eyes"]["left"]["centre"]) + Lively._v(lively["eyes"]["right"]["centre"])) * 0.5
		var curl_bones: Array[int] = []
		for side: String in ["Left", "Right"]:
			for f: String in ["Index", "Middle"]:
				for seg: String in ["Proximal", "Intermediate", "Distal"]:
					var bi: int = sk.find_bone(side + f + seg)
					if bi >= 0:
						curl_bones.append(bi)
		var rows: Array[Image] = []
		var clips := {}
		for n: String in ap.get_animation_list():
			if n == "RESET":
				continue
			var clip: String = n.get_slice("|", n.get_slice_count("|") - 1)
			var anim: Animation = ap.get_animation(n)
			var looped: bool = anim.loop_mode != Animation.LOOP_NONE  # the import names "*_Loop" loops, minus the suffix
			ap.play(n)
			var length: float = anim.length
			# the motion bounds and the loop seam
			var lo := Vector3(1e9, 1e9, 1e9)
			var hi := -lo
			for k: int in 49:
				ap.seek(length * k / 48.0, true)
				for bi: int in sk.get_bone_count():
					var p: Vector3 = sk.global_transform * sk.get_bone_global_pose(bi).origin
					lo = lo.min(p)
					hi = hi.max(p)
				var ht: Vector3 = sk.global_transform * sk.get_bone_global_pose(head_bi) * Vector3(0.0, head_top, 0.0)
				hi = hi.max(ht)
			lo = Vector3(lo.x - 0.14, minf(lo.y, 0.0) - 0.04, lo.z - 0.14)
			hi = Vector3(hi.x + 0.14, hi.y + 0.06, hi.z + 0.14)
			var c: Vector3 = (lo + hi) * 0.5
			var span: Vector3 = hi - lo
			var yaw := deg_to_rad(35.0)
			var across: float = absf(span.x * cos(yaw)) + absf(span.z * sin(yaw))
			var fh: float = maxf(span.y, across * REEL.y / REEL.x) * 1.22  # the feet in front need the room
			var seam := 0.0
			ap.seek(0.0, true)
			var first: Array[Quaternion] = []
			for bi: int in sk.get_bone_count():
				first.append(sk.get_bone_pose_rotation(bi))
			ap.seek(length, true)
			for bi: int in sk.get_bone_count():
				seam = maxf(seam, rad_to_deg(first[bi].angle_to(sk.get_bone_pose_rotation(bi))))
			# the measures on 24 samples (CPU skinning)
			var lowest := 1e9
			var lowest_hi := -1e9
			var near_max := 0.0
			var near_frames := 0
			var curl := 0.0
			var feet: Array[PackedVector3Array] = [PackedVector3Array(), PackedVector3Array()]
			var lf: int = sk.find_bone("LeftFoot")
			var rf: int = sk.find_bone("RightFoot")
			for k: int in 25:
				ap.seek(length * k / 24.0, true)
				var pts: PackedVector3Array = Char.skinned_points(mesh, 1)
				var lw := 1e9
				for i: int in range(0, pts.size(), 4):
					lw = minf(lw, pts[i].y)
				lowest = minf(lowest, lw)
				lowest_hi = maxf(lowest_hi, lw)
				var grid := {}
				for i: int in core_i:
					var key := Vector3i((pts[i] / 0.015).floor())
					grid[key] = true
				var near := 0
				for i: int in hand_i:
					var key := Vector3i((pts[i] / 0.015).floor())
					var hit := false
					for dx: int in [-1, 0, 1]:
						for dy: int in [-1, 0, 1]:
							for dz: int in [-1, 0, 1]:
								if grid.has(key + Vector3i(dx, dy, dz)):
									hit = true
					if hit:
						near += 1
				var share: float = float(near) / maxf(1.0, float(hand_i.size()))
				near_max = maxf(near_max, share)
				if share > 0.02:
					near_frames += 1
				for bi: int in curl_bones:
					curl += rad_to_deg(sk.get_bone_rest(bi).basis.get_rotation_quaternion().angle_to(sk.get_bone_pose_rotation(bi)))
			for k: int in int(length * 30.0) + 1:
				ap.seek(minf(length, k / 30.0), true)
				feet[0].append(sk.global_transform * sk.get_bone_global_pose(lf).origin)
				feet[1].append(sk.global_transform * sk.get_bone_global_pose(rf).origin)
			var slide := []
			for fp: PackedVector3Array in feet:
				var fmin := 1e9
				for p: Vector3 in fp:
					fmin = minf(fmin, p.y)
				var sum := 0.0
				var cnt := 0
				var mx := 0.0
				for k: int in range(1, fp.size()):
					if fp[k].y < fmin + 0.02 and fp[k - 1].y < fmin + 0.02:
						var v: float = Vector2(fp[k].x - fp[k - 1].x, fp[k].z - fp[k - 1].z).length() * 30.0 * 100.0
						sum += v
						cnt += 1
						mx = maxf(mx, v)
				slide.append([snappedf(sum / maxf(1, cnt), 0.1), snappedf(mx, 0.1)])
			# the reel and the row
			var dir: String = String(job["frames"]).path_join("%s_%s" % [name, clip])
			DirAccess.make_dir_recursive_absolute(dir)
			# the springs at rest per reel (A1's loop; A2's reset_springs() does the same, so A1's before is unchanged)
			for sp: Dictionary in live.springs:
				sp["s"] = Vector4.ZERO
			if "on_clip" in live:  # A1's lively: the head's turn and the springs on top of the clip
				live.on_clip = bool(job.get("on_clip", true))
				live.reset_motion()
			if "eye_mode" in live:  # A3
				live.eye_mode = String(job.get("eye_mode", "fixed"))
				live.reseed()
			if "yaw_counter" in live:  # A2
				live.yaw_counter = float(job.get("yaw_counter", 0.0)) if clip in LOCOMOTION else 0.0
				live.darts = float(job.get("darts", 0.0))
			live.head_follow = 0.5
			live.breathing = 1.0
			var shown: float = maxf(3.0, length * 2.0) if looped else length + 0.8
			shown = minf(shown, 8.0) if looped else shown
			var count: int = int(shown * FPS)
			var swing := 0.0
			var jitter := 0.0
			var p1 := []
			var p2 := []
			var head_off := 0.0
			var cells: Array[Image] = []
			ap.seek(0.0, true)
			for i: int in count:
				var t: float = i / FPS
				var ct: float = clampf(t - 0.4, 0.0, length) if not looped else fmod(t, length)
				live.target = sk.global_transform * mid + Vector3(1.2 * sin(TAU * t / 5.0), 0.25 * sin(TAU * t / 3.3), 2.5)
				ap.seek(ct, true)
				var clip_head: Quaternion = sk.get_bone_pose_rotation(head_bi)
				live.step(1.0 / FPS)
				head_off = maxf(head_off, rad_to_deg(clip_head.angle_to(sk.get_bone_pose_rotation(head_bi))))
				var now := []
				for sp: Dictionary in live.springs:
					var sv: Vector4 = sp["s"]
					swing = maxf(swing, rad_to_deg(maxf(absf(sv.x), absf(sv.y))))
					now.append(Vector2(sv.x, sv.y))
				if p2.size() == now.size():
					for j: int in now.size():
						jitter += rad_to_deg((now[j] - 2.0 * p1[j] + p2[j]).length())
				p2 = p1
				p1 = now
				var img: Image = await _framed(c, fh, 35.0)
				if bool(job.get("split", false)):
					var split_img: Image = await _split(img, sk, c, fh)
					split_img.save_png(dir.path_join("%04d.png" % i))
				else:
					img.save_png(dir.path_join("%04d.png" % i))
				if cells.size() < 6 and i == int(count * cells.size() / 6.0):
					var cimg: Image = img.get_region(Rect2i((REEL.x - REEL.y) / 2, 0, REEL.y, REEL.y))
					cimg.resize(PH.x, PH.y, Image.INTERPOLATE_LANCZOS)
					cells.append(cimg)
			var row := Image.create(PH.x * 6, PH.y, false, Image.FORMAT_RGB8)
			for j: int in cells.size():
				row.blit_rect(cells[j], Rect2i(Vector2i.ZERO, PH), Vector2i(PH.x * j, 0))
			rows.append(row)
			clips[clip] = {"length_s": snappedf(length, 0.001), "loop": looped, "frames": count,
				"seam_deg": snappedf(seam, 0.01), "lowest_cm": snappedf(lowest * 100.0, 0.01),
				"lowest_highest_cm": snappedf(lowest_hi * 100.0, 0.01),
				"feet_slide_mean_max_cm_s": slide, "hands_near_body_share_max": snappedf(near_max, 0.001),
				"hands_near_body_frames_of_25": near_frames,
				"finger_curl_mean_deg": snappedf(curl / (25.0 * maxf(1, curl_bones.size())), 0.1),
				"spring_swing_max_deg": snappedf(swing, 0.01),
				"spring_jitter_deg_per_s": snappedf(jitter / maxf(0.1, shown), 0.01),
				"head_off_clip_max_deg": snappedf(head_off, 0.1), "frame_height_m": snappedf(fh, 0.01)}
			print("REEL %s %s %s" % [name, clip, JSON.stringify(clips[clip])])
			if clip in (job.get("head60", []) as Array):
				await _head60(live, ap, sk, head_bi, mid, length, String(job["frames"]).path_join("%s_%s_head60" % [name, clip]))
		var sheet := Image.create(PH.x * 6, PH.y * rows.size(), false, Image.FORMAT_RGB8)
		for j: int in rows.size():
			sheet.blit_rect(rows[j], Rect2i(Vector2i.ZERO, rows[j].get_size()), Vector2i(0, PH.y * j))
		sheet.save_jpg(String(job["sheet_out"]).path_join("clips_%s.jpg" % name), 0.9)
		report[name] = {"clips": clips, "order": clips.keys(), "hand_vertices": hand_i.size(),
			"core_vertices": core_i.size()}
		ch.queue_free()
		await process_frame
	var f := FileAccess.open(String(job["sheet_out"]).path_join("reels.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, " "))
	f.close()
	print("REEL done")
	quit(0)


func _has_any(b: String, parts: Array) -> bool:
	for p: String in parts:
		if p in b:
			return true
	return false


func _framed(c: Vector3, h: float, yaw_deg: float) -> Image:
	_cam.projection = Camera3D.PROJECTION_PERSPECTIVE
	var yaw := deg_to_rad(yaw_deg)
	var dist: float = h * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
	_cam.position = c + Vector3(sin(yaw) * cos(0.08), sin(0.08), cos(yaw) * cos(0.08)) * dist
	_cam.look_at(c)
	await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	if img.get_size() != REEL:
		img.resize(REEL.x, REEL.y, Image.INTERPOLATE_LANCZOS)
	return img


## A2: the 2x2 review frame: the three-quarter view already rendered (top left), the left side, the back, and a
## close-up of the head and hands (bottom right, three-quarter, following the chest).
func _split(q34: Image, sk: Skeleton3D, c: Vector3, fh: float) -> Image:
	var out := Image.create(REEL.x, REEL.y, false, Image.FORMAT_RGB8)
	var views: Array[Image] = [q34, await _framed(c, fh, 90.0), await _framed(c, fh, 180.0)]
	var head: Vector3 = sk.global_transform * sk.get_bone_global_pose(sk.find_bone("Head")).origin
	var hands := Vector3.ZERO
	for b: String in ["LeftHand", "RightHand"]:
		hands += sk.global_transform * sk.get_bone_global_pose(sk.find_bone(b)).origin * 0.5
	var cc: Vector3 = (head + Vector3(0.0, 0.12, 0.0) + hands) * 0.5
	views.append(await _framed(cc, maxf(0.75, absf(head.y - hands.y) + 0.55), 35.0))
	for j: int in 4:
		var v: Image = views[j].duplicate()
		v.resize(HALF.x, HALF.y, Image.INTERPOLATE_LANCZOS)
		out.blit_rect(v, Rect2i(Vector2i.ZERO, HALF), Vector2i(HALF.x * (j % 2), HALF.y * (j / 2)))
	return out


## A2: the head alone at 60 fps over two loops (at least 2 s), three-quarter front, following the head: the springs'
## jitter at a game's frame rate.
func _head60(live, ap: AnimationPlayer, sk: Skeleton3D, head_bi: int, mid: Vector3, length: float, dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	live.reset_motion()
	live.reset_springs()
	var n: int = int(maxf(2.0, length * 2.0) * 60.0)
	for i: int in n:
		var t: float = i / 60.0
		live.target = sk.global_transform * mid + Vector3(1.2 * sin(TAU * t / 5.0), 0.25 * sin(TAU * t / 3.3), 2.5)
		ap.seek(fmod(t, length), true)
		live.step(1.0 / 60.0)
		var head: Vector3 = sk.global_transform * sk.get_bone_global_pose(head_bi).origin
		var img: Image = await _framed(head + Vector3(0.0, 0.12, 0.0), 0.62, 35.0)
		img.save_png(dir.path_join("%04d.png" % i))
