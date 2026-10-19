extends "res://alien/m5_shots.gd"
## M6's proofs (art #196): the eyes and lips sized, rounded and integrated, under the approved look (second_test.gd's
## stage, light D), teal, no crest, Idle at frame 0, in an off-screen window (the runner's _godot.window(),
## 1536 x 1536). Spec "modes", in this order:
## - "size": grid_size.png, rf2 then the face under each spec "sizes" entry ({"label", "scale" (the eye unit about its
##   socket, at run time: ball, lids and wet strips), "iris" (iris_deg, pupil_deg and limbus_deg times it, both
##   designs)}), the three-quarter face (row 1) and the front (row 2) at 1.2 m;
## - "corners": grid_corners.png, one row per spec "corner_scenes" entry (name: res, kits built with other lid
##   corners), the left eye from the front at 0.4 m with the lids at rest, closed and open, and the face from the
##   front at 1.2 m; spec "scale" applies to every scene;
## - "look": grid_look.png and zoom_look.png, rf2 then the hero face under each spec "variants" entry ({"label",
##   "lip": {alien_lip.gdshader uniform: value}, "lid": {..} (the lid domes' copy), "skin": {alien_hue..}}), and
##   grid_look_close.png, the same at 0.4 m;
## - "final": the sheets of the before kit (spec "scenes" "before", drawn with alien.gd lip_look "m5") against the
##   hero kit: cmp.png (rows: rf2's framing, the front at 1.2 m, the close face at 0.4 m; before | after | rf2),
##   blink_<design>.png (open, rest, half, closed; before above after), designs.png (both eye designs with both
##   mouths, three-quarter and front, after), mouths.png (per mouth design rest, A and O from 0.5 m, before above
##   after), and the after shots alone (hero_face_34.png, front.png, close_34.png, close_front.png).
## Spec: m5_shots.gd's plus "sizes", "corner_scenes", "scale", "variants".

const LID_STATES: Array[String] = ["open", "rest", "half", "closed"]

var _base_eye: Dictionary = {}  # node name -> its transform before any scale


func _add_look(k: String, res: String, look: String) -> bool:
	var packed: PackedScene = load(res) as PackedScene
	if packed == null:
		_fail("cannot load %s" % res)
		return false
	var ch: Node3D = packed.instantiate()
	root.add_child(ch)
	var rig: Node = AlienRig.new()
	rig.lip_look = look
	ch.add_child(rig)
	rig.setup(ch)
	rig.auto_blink = false
	rig.set_crest("")
	rig.set_hue("teal")
	_ch[k] = ch
	_rig[k] = rig
	_player[k] = ch.find_child("AnimationPlayer", true, false)
	_combo(k, "bored", "frog")
	_order.append(k)
	print("PROOF ", k, " textured ", rig.is_textured(), " look ", look, " m6 lips ", rig.uses_m6_lips(),
		" contact max ", _contact_max(ch))
	return true


## The largest contact value on Body (CUSTOM1.x, alien_m6.py's field; -1 when Body has no CUSTOM1 floats).
func _contact_max(ch: Node3D) -> float:
	var body: MeshInstance3D = ch.find_child("Body", true, false) as MeshInstance3D
	if body == null:
		return -1.0
	var best: float = -1.0
	for s: int in body.mesh.get_surface_count():
		var c: Variant = body.mesh.surface_get_arrays(s)[Mesh.ARRAY_CUSTOM1]
		if c is PackedFloat32Array:
			var a: PackedFloat32Array = c
			for i: int in range(0, a.size(), 2):  # RG_FLOAT: u (the field), v
				best = maxf(best, a[i])
	return best


## The eye units of a character scaled by s about each ball's centre and moved `sink` m back along the socket's axis
## into the head (absolute: from the transforms at the first call).
func _eye_scale(k: String, s: float, sink: float = 0.0) -> void:
	var rig: Node = _rig[k]
	for d: String in ["bored", "manic"]:
		for side: String in ["L", "R"]:
			var ball: Node3D = rig.node("eye_%s_ball_%s" % [d, side])
			var sock: Node3D = rig.node("Eye_" + side)
			var back: Vector3 = -sock.global_transform.basis.z.normalized() * sink  # glTF +Z: the eye's forward
			var back_local: Vector3 = (ball.get_parent() as Node3D).global_transform.basis.inverse() * back
			for part: String in ["ball", "lid_upper", "lid_lower"]:
				var n: Node3D = rig.node("eye_%s_%s_%s" % [d, part, side])
				var key: String = k + "/" + n.name
				if not _base_eye.has(key):
					_base_eye[key] = n.transform
				var t: Transform3D = _base_eye[key]
				# the ball's centre in the part's parent frame; the parts share the ball's origin
				var pivot: Vector3 = (_base_eye[k + "/" + ball.name] as Transform3D).origin if _base_eye.has(k + "/" + ball.name) else ball.transform.origin
				n.transform = Transform3D(t.basis.scaled_local(Vector3.ONE * s), pivot + (t.origin - pivot) * s + back_local)


func _iris(k: String, f: float) -> void:
	for d: String in ["bored", "manic"]:
		# alien_lids_geom.iris_look: the iris and pupil times f, the cornea's edge moved with the iris' edge
		var em: ShaderMaterial = _rig[k].eye_material(d)
		var look: Dictionary = AlienRig.EYE_LOOK[d]
		var iris: float = look["iris_deg"]
		em.set_shader_parameter("iris_deg", iris * f)
		em.set_shader_parameter("pupil_deg", float(look["pupil_deg"]) * f)
		em.set_shader_parameter("limbus_deg", float(look["limbus_deg"]) - iris * (1.0 - f) if iris > 0.0
			else float(look["limbus_deg"]) * f)


func _face_at(k: String, yaw: float, dist: float = 1.2) -> void:
	var eyes: Vector3 = (_find(k, "Eye_L") + _find(k, "Eye_R")) * 0.5
	var mouth: Vector3 = _find(k, "Mouth")
	_look((eyes + mouth) * 0.5 + Vector3(0, 0.02, 0), yaw, 2.0, dist, 30.0)


func _eye_front(k: String) -> void:
	_look(_find(k, "Eye_L") + Vector3(0, -0.005, 0), 8.0, 2.0, 0.4, 16.0)


## hero_shots.gd's _apply with the lip shader's colours (source_color uniforms take a Color, sRGB).
func _apply(mat: Material, params: Dictionary, undo: Dictionary) -> void:
	var sm := mat as ShaderMaterial
	if sm == null:
		return
	for k: String in params:
		if not undo.has(k):
			undo[k] = sm.get_shader_parameter(k)
		var v: Variant = params[k]
		if v is Array and (v as Array).size() == 3:
			v = Color(v[0], v[1], v[2]) if k in ["accent", "albedo", "iris", "deep", "transmit_color"] else Vector3(v[0], v[1], v[2])
		elif v is Array and (v as Array).size() == 2:
			v = Vector2(v[0], v[1])
		sm.set_shader_parameter(k, v)


func _lip_apply(k: String, v: Dictionary, undo: Dictionary) -> void:
	undo["lip"] = {}
	undo["lid"] = {}
	undo["skin"] = {}
	_apply(_rig[k].face_material("alien_lip"), v.get("lip", {}), undo["lip"])
	_apply(_rig[k].face_material("alien_lid"), v.get("lid", v.get("lip", {})), undo["lid"])
	_apply(_rig[k].skin_material(), v.get("skin", {}), undo["skin"])


func _lip_restore(k: String, undo: Dictionary) -> void:
	_restore(_rig[k].face_material("alien_lip"), undo["lip"])
	_restore(_rig[k].face_material("alien_lid"), undo["lid"])
	_restore(_rig[k].skin_material(), undo["skin"])


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_modes = _spec.get("modes", ["final"])
	_stage()
	if _spec.has("bg"):
		_backdrop(_spec["bg"])
	_order = []
	var scenes: Dictionary = _spec["scenes"]
	if scenes.has("before") and not _add_look("before", scenes["before"], "m5"):
		return
	if not _add_look("hero", scenes["hero"], "m6"):
		return
	var cs: Dictionary = _spec.get("corner_scenes", {})
	if _modes.has("corners"):
		for name: String in cs:
			if not _add_look(name, cs[name], "m6"):
				return
	for k: String in _ch:
		if k != "before":
			_eye_scale(k, float(_spec.get("scale", 1.0)), float(_spec.get("sink", 0.0)))
	_pose("Idle", 0.0)
	_only(["hero"], false)
	for _i: int in 4:
		await process_frame
	var rf2: Image = _png(_spec.get("beside", ""))
	var rf2_eye: Image = _region(rf2, _spec.get("rf2_eye", [0.17, 0.26, 0.67, 0.76])) if rf2 != null else null
	if _modes.has("size"):
		var row34: Array = [rf2]
		var rowf: Array = [rf2]
		for v: Dictionary in _spec.get("sizes", []):
			_eye_scale("hero", float(v.get("scale", 1.0)), float(v.get("sink", 0.0)))
			_iris("hero", float(v.get("iris", 1.0)))
			_face_at("hero", 30.0, float(_spec.get("size_dist", 1.2)))
			row34.append(await _shot(v.get("label", "")))
			_face_at("hero", 0.0, float(_spec.get("size_dist", 1.2)))
			rowf.append(await _shot(v.get("label", "")))
		_eye_scale("hero", float(_spec.get("scale", 1.0)), float(_spec.get("sink", 0.0)))
		_iris("hero", 1.0)
		_grid_cells(row34 + rowf, row34.size(), Vector2i(640, 640), "grid_size.png")
	if _modes.has("corners"):
		var cells: Array = []
		for name: String in cs:
			_only([name], false)
			await process_frame
			for st: String in ["rest", "closed", "open"]:
				_rig[name].set_lids(st)
				_eye_front(name)
				cells.append(await _shot("%s %s" % [name, st]))
			_rig[name].set_lids("rest")
			_face_at(name, 0.0)
			cells.append(await _shot(name))
		_only(["hero"], false)
		_grid_cells(cells, 4, Vector2i(480, 480), "grid_corners.png")
	if _modes.has("look"):
		var faces: Array = [rf2]
		var closes: Array = [rf2_eye]
		var zooms: Array = [_region(rf2, _spec.get("grid_zoom_target", [0.2, 0.35, 0.6, 0.75]))] if rf2 != null else []
		for v: Dictionary in _spec.get("variants", []):
			var undo := {}
			_lip_apply("hero", v, undo)
			_view(_face_view("hero"))
			faces.append(await _shot(v.get("label", "")))
			zooms.append(_region(faces[-1], _spec.get("grid_zoom", [0.15, 0.3, 0.65, 0.8])))
			var fv: Array = _face_view("hero")
			_look(fv[0], float(_spec.get("look_yaw", 30.0)), 2.0, 0.4, CLOSE_FOV)
			closes.append(await _shot(v.get("label", "")))
			_lip_restore("hero", undo)
		_grid_cells(faces, 4, Vector2i(640, 640), "grid_look.png")
		_grid_cells(zooms, 4, Vector2i(640, 640), "zoom_look.png")
		_grid_cells(closes, 4, Vector2i(640, 640), "grid_look_close.png")
	if _modes.has("final"):
		await _final(rf2, rf2_eye)
	quit(0)


func _final(rf2: Image, rf2_eye: Image) -> void:
	var have_before: bool = _ch.has("before")
	var ks: Array = ["before", "hero"] if have_before else ["hero"]
	var rows: Array = []
	for row: String in ["hero", "front", "close"]:
		for k: String in ks:
			_only([k], false)
			await process_frame
			match row:
				"hero":
					_view(_face_view(k))
				"front":
					_face_at(k, 0.0)
				"close":
					var fv: Array = _face_view(k)
					_look(fv[0], 30.0, 2.0, 0.4, CLOSE_FOV)
			var img: Image = await _shot("M5" if k == "before" else "M6")
			if k == "hero":
				_save({"hero": "hero_face_34.png", "front": "front.png", "close": "close_34.png"}[row], img.duplicate())
			rows.append(img)
		rows.append(rf2_eye if row == "close" else rf2)
	_grid_cells(rows, ks.size() + 1, Vector2i(640, 640), "cmp.png")
	_only(["hero"], false)
	await process_frame
	var fv0: Array = _face_view("hero")
	_look(fv0[0], 0.0, 2.0, 0.4, CLOSE_FOV)
	_save("close_front.png", await _shot(""))
	for d: String in ["bored", "manic"]:
		var strip: Array = []
		for k: String in ks:
			_only([k], false)
			_combo(k, d, "frog")
			for st: String in LID_STATES:
				_rig[k].set_lids(st)
				_eye_front(k)
				strip.append(await _shot("%s %s" % ["M5" if k == "before" else "M6", st]))
			_rig[k].set_lids("rest")
			_combo(k, "bored", "frog")
		_grid_cells(strip, 4, Vector2i(400, 400), "blink_%s.png" % d)
	_only(["hero"], false)
	var cells: Array = []
	for d: String in ["bored", "manic"]:
		for m: String in ["frog", "overbite"]:
			_combo("hero", d, m)
			await process_frame
			_face_at("hero", 30.0)
			cells.append(await _shot("%s %s" % [d, m]))
			_face_at("hero", 0.0)
			cells.append(await _shot("%s %s" % [d, m]))
	_combo("hero", "bored", "frog")
	_grid_cells(cells, 4, Vector2i(480, 480), "designs.png")
	var mc: Array = []
	for m: String in ["frog", "overbite"]:
		for k: String in ks:
			_only([k], false)
			for piece: String in ["rest", "A", "O"]:
				_combo(k, "bored", m, piece)
				await process_frame
				var mouth: Vector3 = _find(k, "Mouth")
				_look(mouth, 25.0, 2.0, 0.5, 20.0)
				mc.append(await _shot("%s %s %s" % ["M5" if k == "before" else "M6", m, piece]))
			_combo(k, "bored", "frog")
	_grid_cells(mc, 3, Vector2i(400, 400), "mouths.png")
	_only(["hero"], false)
