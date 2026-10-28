extends "res://alien/char_shots.gd"
## Full-body clip frames (art #196, T3): one character's builds side by side, a row per build (r2b's loco set above
## the new body's), a column per clip at a fixed phase of its cycle (idle, walk, run, crouch, jump, strafe), the whole
## body and head in frame under the game look (char_shots.gd's stage, fix and head setup). The camera follows the
## Hips over the floor, so a clip's travel keeps the body centred; the same 3/4 view and framing on every cell.
## tools/blender/alien_body_clips.py writes the job and runs this in the runner's off-screen window.
## - <out>/<sheet>.jpg: the sheet (rows x clips, about 1280 px wide);
## - <out>/<sheet>.json: per row and clip the animation played, its time and the Hips' height there.
## Args after "--": <job.json> ({"hdri", "fix", "out", "sheet", "rows": [{"label", "head"}], "clips":
## [{"label", "anim", "phase"}], "height_m", "yaw_deg"})

const BODY_CELL := Vector2i(212, 424)


func _run() -> void:
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	_stage(job["hdri"])
	_apply_fix(job.get("fix", {}))
	var ground := MeshInstance3D.new()  # a floor to judge the feet's contact and shadows against
	var plane := PlaneMesh.new()
	plane.size = Vector2(40.0, 40.0)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.56, 0.56, 0.58)
	gm.roughness = 0.9
	plane.material = gm
	ground.mesh = plane
	root.add_child(ground)
	var out: String = job["out"]
	var frame_h: float = job.get("height_m", 2.4)
	var yaw: float = job.get("yaw_deg", 35.0)
	var cells: Array[Image] = []
	var rep := {}
	for row: Dictionary in job["rows"]:
		var h: Dictionary = row["head"]
		var ch: Node3D = (load(h["char"]) as PackedScene).instantiate()
		root.add_child(ch)
		_setup(ch, h, true)
		var sk: Skeleton3D = ch.find_children("*", "Skeleton3D", true, false)[0]
		var ap: AnimationPlayer = ch.find_children("*", "AnimationPlayer", true, false)[0]
		ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
		var names := {}
		for n: String in ap.get_animation_list():
			names[n.get_slice("|", n.get_slice_count("|") - 1).trim_suffix("_Loop")] = n
		var hips: int = sk.find_bone("Hips")
		var per := {}
		for c: Dictionary in job["clips"]:
			var anim: String = c["anim"]
			if not names.has(anim):
				printerr("BODY %s: no clip %s (has %s)" % [row["label"], anim, ", ".join(names.keys())])
				quit(1)
				return
			ap.play(names[anim])
			var t: float = ap.get_animation(names[anim]).length * float(c["phase"])
			ap.seek(t, true)
			var hp: Vector3 = sk.global_transform * sk.get_bone_global_pose(hips).origin
			var img: Image = await _cell(Vector3(hp.x, frame_h * 0.45, hp.z), frame_h, yaw, BODY_CELL)
			cells.append(img)
			per[c["label"]] = {"anim": names[anim], "t_s": snappedf(t, 0.001), "hips_m": snappedf(hp.y, 0.001)}
		rep[row["label"]] = per
		print("BODY %s %s" % [row["label"], JSON.stringify(per)])
		ch.queue_free()
		await process_frame
	_sheet(cells, BODY_CELL, job["clips"].size()).save_jpg(out.path_join("%s.jpg" % job["sheet"]), 0.92)
	var f := FileAccess.open(out.path_join("%s.json" % job["sheet"]), FileAccess.WRITE)
	f.store_string(JSON.stringify(rep, " "))
	f.close()
	print("BODY done")
	quit(0)
