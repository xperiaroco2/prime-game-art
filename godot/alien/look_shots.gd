extends "res://alien/char_shots.gd"
## The recovered aliens (art #393) under the approved static look of art #196 (char_shots.gd's studio and
## materials: alien_static.gdshader on `*_static_skin`, apply_body on `*_body_skin`) in an off-screen window
## (tools/blender/alien_look_run.py stages the GLBs and writes the job). Per shot of the job's "shots":
## - "sheet": 8 frames over one loop of a clip from a yaw (degrees, 0 the front, 90 the character's left side), 4 x 2
##   cells of 320 x 480 over a grey floor, `<name>.png` about 1280 px wide;
## - "turn": the turnaround (front, 3/4, side, back) on the Idle clip's first frame, as char_shots' turn_ sheets;
## - "video": 1280 x 720 PNG frames at 24 fps into frames/<name>/ (whole loops, at least 3 s), the encoder's input;
## - "diag": a close-up of the thighs from the front and the 3/4 (Idle's first frame): the look | the look with the key
##   where frames.gd put it (its rig turned -35 degrees) | that key's shadow off | the GLB's own materials under that key | the same, shadow off.
## The job's per-character inputs are paths or constants ([r, g, b, a] linear: a 4 x 4 texture) for the sidecar maps
## the shader reads; looks.json reports what each character got.
## Args after "--": <job.json>

const SHEET_CELL: Vector2i = Vector2i(320, 480)
const VIDEO: Vector2i = Vector2i(1280, 720)


func _const_tex(c: Array) -> Texture2D:
	var img := Image.create(4, 4, false, Image.FORMAT_RGBA8)
	img.fill(Color(float(c[0]), float(c[1]), float(c[2]), float(c[3]) if c.size() > 3 else 1.0))
	return ImageTexture.create_from_image(img)


## A sidecar map: a path (AlienStatic.data_texture), a constant [r, g, b(, a)], or null for "" and a missing key.
func _map(h: Dictionary, key: String) -> Texture2D:
	var v: Variant = h.get(key, "")
	if v is Array:
		return _const_tex(v)
	if v is String and v != "":
		return AlienStatic.data_texture(v)
	return null


func _look(node: Node, h: Dictionary) -> Array[ShaderMaterial]:
	var bases := {}
	for k: String in (h.get("bases", {}) as Dictionary):
		bases[k] = _col(h["bases"][k])
	var mats: Array[ShaderMaterial] = AlienStatic.apply(node, _map(h, "mask"), _col(h["base_skin"]), _map(h, "detail"),
		null, null, _map(h, "accent"), bases, _map(h, "gill"))
	if mats.is_empty():
		return mats
	mats.append_array(AlienStatic.apply_body(node, mats[0], _map(h, "body_mask"), _map(h, "body_accent"),
		_map(h, "body_detail")))
	for sm: ShaderMaterial in mats:
		for k: String in (h["params"] as Dictionary):
			sm.set_shader_parameter(k, h["params"][k])
	return mats


## The clip whose last name part, "_Loop" dropped, is want (Godot's import drops the suffix already).
func _clip(ap: AnimationPlayer, want: String) -> String:
	for n: String in ap.get_animation_list():
		var short: String = n.get_slice("|", n.get_slice_count("|") - 1).trim_suffix("_Loop")
		if short.to_lower() == want.to_lower():
			return n
	return ""


func _hips(sk: Skeleton3D) -> Vector3:
	var i: int = sk.find_bone("Hips")
	return sk.global_transform * sk.get_bone_global_pose(maxi(i, 0)).origin


func _pose(ap: AnimationPlayer, clip: String, t: float) -> void:
	if ap.current_animation != clip:
		ap.play(clip)
	ap.seek(t, true)


## The camera's centre per sample time: fixed at the clip's mean hips (an in-place clip), or following the hips
## across the floor when they travel over 0.3 m.
func _centres(ap: AnimationPlayer, sk: Skeleton3D, clip: String, times: Array[float], mid_y: float) -> Array[Vector3]:
	var pts: Array[Vector3] = []
	var lo := Vector3.INF
	var hi := -Vector3.INF
	for t: float in times:
		_pose(ap, clip, t)
		var p: Vector3 = _hips(sk)
		pts.append(p)
		lo = lo.min(p)
		hi = hi.max(p)
	var mean := (lo + hi) * 0.5
	var travel: float = Vector2(hi.x - lo.x, hi.z - lo.z).length()
	var out: Array[Vector3] = []
	for p: Vector3 in pts:
		out.append(Vector3(p.x, mid_y, p.z) if travel > 0.3 else Vector3(mean.x, mid_y, mean.z))
	return out


func _run() -> void:
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	var out: String = job["out"]
	_stage(job.get("hdri", ""))
	_apply_fix(job.get("fix", {}))
	var ground := MeshInstance3D.new()  # clip_reels.gd's floor
	var plane := PlaneMesh.new()
	plane.size = Vector2(60.0, 60.0)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.33, 0.34, 0.36)
	gm.roughness = 0.9
	plane.material = gm
	ground.mesh = plane
	root.add_child(ground)
	var chars := {}
	var report := {}
	for name: String in (job["chars"] as Dictionary):
		var h: Dictionary = job["chars"][name]
		var scene: PackedScene = load(h["glb"])
		if scene == null:
			printerr("LOOK %s: cannot load %s" % [name, h["glb"]])
			quit(3)
			return
		var node: Node3D = scene.instantiate()
		root.add_child(node)
		node.visible = false
		var mats := _look(node, h)
		if mats.size() < 2:
			printerr("LOOK %s: %d shader materials (the head's and the body's expected)" % [name, mats.size()])
			quit(4)
			return
		var ap: AnimationPlayer = node.find_children("*", "AnimationPlayer", true, false)[0]
		ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
		var sk: Skeleton3D = node.find_children("*", "Skeleton3D", true, false)[0]
		var top := 0.0
		for mi: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
			top = maxf(top, (mi.global_transform * mi.get_aabb()).end.y)
		chars[name] = {"node": node, "ap": ap, "sk": sk, "top": top, "mats": mats}
		report[name] = {"materials": mats.map(func(m: ShaderMaterial) -> String: return m.resource_name), "top_m": top}
	for shot: Dictionary in (job["shots"] as Array):
		var c: Dictionary = chars[shot["char"]]
		for other: String in chars:
			(chars[other]["node"] as Node3D).visible = other == shot["char"]
		var ap: AnimationPlayer = c["ap"]
		var sk: Skeleton3D = c["sk"]
		var top: float = c["top"]
		var kind: String = shot["kind"]
		var clip: String = _clip(ap, shot.get("clip", "Idle"))
		if clip == "":
			printerr("LOOK %s: no clip %s" % [shot["char"], shot.get("clip", "Idle")])
			quit(5)
			return
		var length: float = ap.get_animation(clip).length
		var yaw: float = float(shot.get("yaw", 0.0))
		if kind == "sheet":
			var times: Array[float] = []
			for k: int in 8:
				times.append(length * k / 8.0)
			var cs := _centres(ap, sk, clip, times, top * 0.5)
			var cells: Array[Image] = []
			for k: int in 8:
				_pose(ap, clip, times[k])
				cells.append(await _cell(cs[k], top * 1.12, yaw, SHEET_CELL))
			_sheet(cells, SHEET_CELL, 4).save_png(out.path_join(shot["name"] + ".png"))
		elif kind == "turn":
			_pose(ap, clip, 0.0)
			var t0: Array[float] = [0.0]
			var cs := _centres(ap, sk, clip, t0, top * 0.5)
			var cells: Array[Image] = []
			for y: float in [0.0, 35.0, 90.0, 180.0]:
				cells.append(await _cell(cs[0], top * 1.06, y, CELL))
			_sheet(cells, CELL, 4).save_png(out.path_join(shot["name"] + ".png"))
		elif kind == "video":
			var loops: int = maxi(1, ceili(3.0 / length))  # whole loops, at least 3 s
			var n: int = int(round(length * loops * FPS))
			var times: Array[float] = []
			for k: int in n:
				times.append(fmod(k / FPS, length))
			var cs := _centres(ap, sk, clip, times, top * 0.5)
			var dir: String = out.path_join("frames").path_join(shot["name"])
			DirAccess.make_dir_recursive_absolute(dir)
			for k: int in n:
				_pose(ap, clip, times[k])
				var img: Image = await _cell(cs[k], top * 1.12, yaw, VIDEO)
				img.save_png(dir.path_join("%04d.png" % k))
			report[shot["name"]] = {"frames": n, "seconds": n / FPS}
		elif kind == "diag":
			_pose(ap, clip, 0.0)
			var cells: Array[Image] = []
			var mats: Array[ShaderMaterial] = c["mats"]
			for y: float in [0.0, 35.0]:
				for v: int in 5:
					_pose(ap, clip, 0.0)
					# 1-4: the key where frames.gd puts it for the #393 sheets (its rig turned by light_turn_deg -35,
					# aimed at 0.9 m): from the character's right, lower than the studio's
					if v >= 1:
						_key.look_at_from_position(Vector3(-2.0, 3.2, 3.0).rotated(Vector3.UP, deg_to_rad(-35.0)),
							Vector3(0.0, 0.9, 0.0))
					_key.shadow_enabled = v != 2 and v != 4
					if v >= 3:
						_own_materials(c["node"], true)
					var hc: Vector3 = _hips(sk)
					cells.append(await _cell(Vector3(hc.x, hc.y - 0.12, hc.z), 0.5, y, SQ))
					_own_materials(c["node"], false, mats)
					_key.shadow_enabled = true
					_dusk(false)
			for sm: ShaderMaterial in mats:
				sm.set_shader_parameter("debug_mode", 0)
			_sheet(cells, SQ, 5).save_png(out.path_join(shot["name"] + ".png"))
		print("LOOK shot %s done" % shot["name"])
	FileAccess.open(out.path_join("looks.json"), FileAccess.WRITE).store_string(JSON.stringify(report, " "))
	print("LOOK done: %d shots" % (job["shots"] as Array).size())
	quit(0)


## The diag's GLB-materials cell: the imported materials back (own) or the shader materials again, by name.
func _own_materials(node: Node, own: bool, mats: Array[ShaderMaterial] = []) -> void:
	for mi: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		for i: int in mi.mesh.get_surface_count():
			if own:
				mi.set_surface_override_material(i, null)
				continue
			var name: String = mi.mesh.surface_get_material(i).resource_name if mi.mesh.surface_get_material(i) else ""
			for sm: ShaderMaterial in mats:
				if sm.resource_name == name:
					mi.set_surface_override_material(i, sm)
