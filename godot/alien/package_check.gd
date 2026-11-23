extends "res://alien/char_shots.gd"
## The alien game package's proof (art #393; tools/run.py alien-package --check): in the runner's off-screen window,
## from the package folder staged as it is (res://import/pkg_<id>/: the GLB, look/ and package.json):
## - loads the GLB and dresses it with the package's own look/alien_dress.gd (its relative preloads, its
##   alien_static.gd and shaders, its mask through its shipped .import), never the art project's copies;
## - checks the game's clips and bones (package.json's "game") and that both surfaces took the package's shader;
## - builds the sockets as the game's character_rig.gd does (a BoneAttachment3D on the bone, the point in the bone's
##   frame, turned upright at the fitting pose: the Idle clip's first frame; there is no Carry_Upper, so Carry fits on
##   the Idle too) and reports each socket's place at that pose;
## - shoots the turnaround without markers (`look_turn.png`, diffed against the review page's `compare` PNG when the
##   job gives one), with the sockets' stand-in items (`sockets_turn.png`) and the hand close up (`sockets_hand.png`).
## Writes report.json; prints "PKG ok" or "PKG fail <why>" lines. Args after "--": <job.json>

const ITEM_HAND := Vector3(0.06, 0.15, 0.06)  # a one-handed item standing on the Hand socket
const ITEM_BELT := Vector3(0.05, 0.12, 0.05)
const ITEM_CARRY := Vector3(0.40, 0.30, 0.30)  # the package standing on the Carry socket


func _run() -> void:
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	var dir: String = job["dir"]
	var id: String = job["id"]
	var out: String = job["out"]
	var fails: Array[String] = []
	var pkg: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("package.json")))
	var game: Dictionary = pkg["game"]
	_stage("")
	_apply_fix({})
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(60.0, 60.0)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.33, 0.34, 0.36)
	gm.roughness = 0.9
	plane.material = gm
	ground.mesh = plane
	root.add_child(ground)
	var scene: PackedScene = load(dir.path_join(id + ".glb"))
	if scene == null:
		_finish(out, {}, ["cannot load %s" % dir.path_join(id + ".glb")])
		return
	var node: Node3D = scene.instantiate()
	root.add_child(node)
	var dress: GDScript = load(dir.path_join("look/alien_dress.gd"))
	var mats: Array[ShaderMaterial] = dress.dress_from(node, dir.path_join("look/%s_look.json" % id))
	var report := {"materials": [], "clips": [], "missing_clips": [], "missing_bones": [], "sockets": {}}
	for sm: ShaderMaterial in mats:
		report["materials"].append({"name": sm.resource_name, "shader": sm.shader.resource_path})
		if not sm.shader.resource_path.begins_with(dir.path_join("look/")):
			fails.append("%s took %s, not the package's shader" % [sm.resource_name, sm.shader.resource_path])
	if mats.size() != 2:
		fails.append("%d shader materials (the head's and the body's expected)" % mats.size())
	var ap: AnimationPlayer = node.find_children("*", "AnimationPlayer", true, false)[0]
	var sk: Skeleton3D = node.find_children("*", "Skeleton3D", true, false)[0]
	report["clips"] = Array(ap.get_animation_list())
	for clip: String in (game["clips"] as Array):
		if not ap.has_animation(clip):
			report["missing_clips"].append(clip)
			fails.append("no clip %s" % clip)
		elif ap.get_animation(clip).loop_mode != Animation.LOOP_LINEAR and clip != "Jump_Start" and clip != "Jump_Land":
			fails.append("%s does not loop" % clip)
	for bone: String in (game["bones"] as Dictionary).values():
		if sk.find_bone(bone) < 0:
			report["missing_bones"].append(bone)
			fails.append("no bone %s" % bone)
	ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	ap.play("Idle")
	ap.seek(0.0, true)
	var items: Array[MeshInstance3D] = []
	var sockets := {}
	for name: String in (pkg["sockets"] as Dictionary):
		var s: Dictionary = pkg["sockets"][name]
		var bone: int = sk.find_bone(s["bone"])
		if bone < 0:
			fails.append("socket %s: no bone %s" % [name, s["bone"]])
			continue
		var p: Array = s["point"]
		var attach := BoneAttachment3D.new()
		attach.bone_name = s["bone"]
		sk.add_child(attach)
		var at := Node3D.new()
		at.transform = Transform3D(_fit_pose(node, ap.get_animation("Idle"), sk, bone).basis.inverse(),
			Vector3(float(p[0]), float(p[1]), float(p[2])))
		attach.add_child(at)
		sockets[name] = at
		var box := BoxMesh.new()
		box.size = ITEM_HAND if name == "Hand" else (ITEM_BELT if name == "Belt" else ITEM_CARRY)
		var lit := StandardMaterial3D.new()
		lit.albedo_color = Color(1.0, 0.55, 0.2) if name != "Carry" else Color(0.85, 0.75, 0.45)
		box.material = lit
		var mi := MeshInstance3D.new()
		mi.mesh = box
		mi.position = Vector3(0.0, box.size.y * 0.5, 0.0)  # the item's bottom on the socket
		at.add_child(mi)
		items.append(mi)
	ap.seek(0.0, true)
	await process_frame
	for name: String in sockets:
		var g: Transform3D = (sockets[name] as Node3D).global_transform
		report["sockets"][name] = {"at_idle_m": [snappedf(g.origin.x, 0.001), snappedf(g.origin.y, 0.001),
			snappedf(g.origin.z, 0.001)], "up": [snappedf(g.basis.y.x, 0.001), snappedf(g.basis.y.y, 0.001),
			snappedf(g.basis.y.z, 0.001)]}
		if g.basis.y.dot(Vector3.UP) < 0.99:
			fails.append("socket %s is not upright at the Idle's first frame" % name)
	var top := 0.0
	for mi: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		top = maxf(top, (mi.global_transform * mi.get_aabb()).end.y)
	report["top_m"] = snappedf(top, 0.001)
	var hips: Vector3 = sk.global_transform * sk.get_bone_global_pose(maxi(sk.find_bone("Hips"), 0)).origin
	var centre := Vector3(hips.x, top * 0.5, hips.z)  # look_shots.gd's turn: the Idle's hips at mid height
	for mi: MeshInstance3D in items:
		mi.visible = false
	var cells: Array[Image] = []
	for y: float in [0.0, 35.0, 90.0, 180.0]:
		cells.append(await _cell(centre, top * 1.06, y, CELL))
	var turn: Image = _sheet(cells, CELL, 4)
	turn.save_png(out.path_join("look_turn.png"))
	var compare: String = job.get("compare", "")
	if compare != "" and FileAccess.file_exists(compare):
		var ref: Image = Image.load_from_file(compare)
		ref.convert(Image.FORMAT_RGB8)
		if ref.get_size() == turn.get_size():
			report["compare"] = _diff(turn, ref, turn.get_height())
		else:
			report["compare"] = {"size": [ref.get_width(), ref.get_height()], "ours": [turn.get_width(), turn.get_height()]}
	for mi: MeshInstance3D in items:
		mi.visible = true
	cells.clear()
	for y: float in [0.0, 35.0, 90.0, 180.0]:
		cells.append(await _cell(centre, top * 1.06, y, CELL))
	_sheet(cells, CELL, 4).save_png(out.path_join("sockets_turn.png"))
	var hp: Array = report["sockets"].get("Hand", {}).get("at_idle_m", [0.0, 1.0, 0.0])
	var hand := Vector3(float(hp[0]), float(hp[1]) + 0.05, float(hp[2]))
	cells.clear()
	for y: float in [0.0, -90.0, 180.0]:
		cells.append(await _cell(hand, 0.45, y, SQ))
	_sheet(cells, SQ, 3).save_png(out.path_join("sockets_hand.png"))
	_finish(out, report, fails)


## The game's fit pose (character_rig.gd fit_pose without the carry layer): the bone's pose in the model's frame on
## the clip's first frame, a bone the clip leaves alone at its rest.
func _fit_pose(model: Node3D, clip: Animation, sk: Skeleton3D, bone: int) -> Transform3D:
	var prefix := String(model.get_path_to(sk)) + ":"
	var out := Transform3D.IDENTITY
	var at := bone
	while at >= 0:
		var rest := sk.get_bone_rest(at)
		var origin := rest.origin
		var turn := rest.basis.get_rotation_quaternion()
		var size := rest.basis.get_scale()
		var path := NodePath(prefix + sk.get_bone_name(at))
		var t := clip.find_track(path, Animation.TYPE_POSITION_3D)
		if t >= 0:
			origin = clip.position_track_interpolate(t, 0.0)
		t = clip.find_track(path, Animation.TYPE_ROTATION_3D)
		if t >= 0:
			turn = clip.rotation_track_interpolate(t, 0.0)
		t = clip.find_track(path, Animation.TYPE_SCALE_3D)
		if t >= 0:
			size = clip.scale_track_interpolate(t, 0.0)
		out = Transform3D(Basis(turn) * Basis.from_scale(size), origin) * out
		at = sk.get_bone_parent(at)
	var frame := Transform3D.IDENTITY
	var n: Node = sk
	while n != null and n != model:
		if n is Node3D:
			frame = (n as Node3D).transform * frame
		n = n.get_parent()
	return frame * out


func _finish(out: String, report: Dictionary, fails: Array[String]) -> void:
	report["failures"] = fails
	var f := FileAccess.open(out.path_join("report.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, " "))
	f.close()
	for why: String in fails:
		print("PKG fail %s" % why)
	if fails.is_empty():
		print("PKG ok")
	quit(0 if fails.is_empty() else 1)
