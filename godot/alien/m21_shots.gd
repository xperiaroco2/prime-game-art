extends "res://alien/m17_shots.gd"
## M21's proofs (art #196, brief UPDATE 45): the eyes' last three flaws at the game's distance (the pale line under the
## eyes, manic's closed lash "zipper", the blotchy upper lids), under the approved look (second_test.gd's stage, light
## D), in an off-screen window (the runner's _godot.window(), 1536 x 1536). Spec as m17_shots.gd's. Modes, besides
## m17_shots.gd's:
## - "diag": the isolating test on the hero: per variant of "diag" ([{"label", "hide": [name parts], "mat": {face
##   material key: {uniform: value}}, "skin": {uniform: value}}, ...]) one row of bored rest, manic rest, bored closed
##   and manic closed at 3.5 m (lashes on; 3x crops, nearest); every change is undone after its row: diag.png
##   ("diag_name"); "diag_near": the same rows at 0.4 m (the left eye): diag_near.png.
## - "lclosed": the closed lashes' grid: per variant of "variants" ([[name, label], ...], the grid kit's lashvar_ sets;
##   "" the kit's own) bored closed (the left eye close, both eyes from the front at 0.4 m), manic closed (the same)
##   and manic half (close): lclosed.png;
## - "states": per kit and design open, rest, half and closed at 3.5 m (lashes on), one row of eight per kit, and the
##   same at 0.4 m (the left eye): states_game.png, states_near.png.


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_modes = _spec.get("modes", ["diag"])
	if not (_modes.has("diag") or _modes.has("diag_near") or _modes.has("states") or _modes.has("lclosed")):
		await super._run()
		return
	_stage()
	if _spec.has("bg"):
		_backdrop(_spec["bg"])
	_order = []
	for kit: Dictionary in _spec["kits"]:
		var k: String = kit["key"]
		if not _add_look(k, kit["res"], kit.get("look", "m6")):
			return
		_keys.append(k)
		_labels[k] = kit.get("label", k)
		_mouth_of[k] = kit.get("mouth", "frog")
		_lashes_of[k] = kit.get("lashes", true)
		_rig[k].set_lashes(_lashes_of[k])
	_pose("Idle", 0.0)
	for _i: int in 4:
		await process_frame
	var hero: String = _keys[-1]
	if _modes.has("diag"):
		await _diag(hero, false)
	if _modes.has("diag_near"):
		await _diag(hero, true)
	if _modes.has("lclosed"):
		await _lclosed(hero)
	if _modes.has("states"):
		await _states(false)
		await _states(true)
	quit(0)


func _near(k: String) -> void:
	_look(_find(k, "Eye_L") + Vector3(0, 0.0, 0), 20.0, 2.0, 0.4, 16.0)


## One variant's changes on kit k (or undone with the saved values, on undo).
func _diag_apply(k: String, v: Dictionary, saved: Dictionary) -> void:
	for m: Node in _ch[k].find_children("*", "GeometryInstance3D", true, false):
		for part: String in v.get("hide", []):
			if m.name.contains(part):
				saved["vis:" + str(m.get_path())] = [m, (m as Node3D).visible]
				(m as Node3D).visible = false
		for part: String in v.get("lod_bias", {}):
			if m.name.contains(part):
				saved["lod:" + str(m.get_path())] = [m, (m as GeometryInstance3D).lod_bias]
				(m as GeometryInstance3D).lod_bias = float(v["lod_bias"][part])
	if v.has("lod_threshold"):  # the viewport's mesh LOD threshold (0: every mesh at full detail)
		saved["vp_lod"] = [root, root.mesh_lod_threshold]
		root.mesh_lod_threshold = float(v["lod_threshold"])
	var mats: Dictionary = _rig[k]._face_materials
	for key: String in v.get("mat", {}):
		var mat: ShaderMaterial = mats[key]
		for u: String in v["mat"][key]:
			saved["mat:%s:%s" % [key, u]] = [mat, u, mat.get_shader_parameter(u)]
			var val: Variant = v["mat"][key][u]
			mat.set_shader_parameter(u, _val(val))
	var skin: ShaderMaterial = _rig[k]._tex_material
	for u: String in v.get("skin", {}):
		saved["skin:" + u] = [skin, u, skin.get_shader_parameter(u)]
		var val: Variant = v["skin"][u]
		skin.set_shader_parameter(u, _val(val))


func _diag_undo(saved: Dictionary) -> void:
	for key: String in saved:
		var s: Array = saved[key]
		if key.begins_with("vis:"):
			(s[0] as Node3D).visible = s[1]
		elif key.begins_with("lod:"):
			(s[0] as GeometryInstance3D).lod_bias = s[1]
		elif key == "vp_lod":
			root.mesh_lod_threshold = s[1]
		else:
			(s[0] as ShaderMaterial).set_shader_parameter(s[1], s[2])


func _diag(hero: String, near: bool) -> void:
	var cells: Array = []
	_only([hero], false)
	for v: Dictionary in _spec.get("diag", [{"label": "base"}]):
		var saved: Dictionary = {}
		_diag_apply(hero, v, saved)
		for st: String in ["rest", "closed"]:
			for d: String in ["bored", "manic"]:
				_combo(hero, d, _mouth_of[hero])
				_rig[hero].set_lashes(true)
				_rig[hero].set_lids(st)
				await process_frame
				if near:
					_near(hero)
					cells.append(await _shot("%s: %s %s" % [v["label"], d, st]))
				else:
					var c: Image = await _game_crop(hero)
					cells.append(_tag(c, "%s: %s %s" % [v["label"], d, st]))
		_rig[hero].set_lids("rest")
		_diag_undo(saved)
		print("PROOF diag %s" % v["label"])
	_combo(hero, "bored", _mouth_of[hero])
	if near:
		_grid_cells(cells, 4, Vector2i(400, 300), _spec.get("diag_name", "diag") + "_near.png")
	else:
		_grid_cells(cells, 4, Vector2i(480, 400), _spec.get("diag_name", "diag") + ".png")


func _states(near: bool) -> void:
	var cells: Array = []
	for k: String in _keys:
		_only([k], false)
		for d: String in ["bored", "manic"]:
			_combo(k, d, _mouth_of[k])
			_rig[k].set_lashes(true)
			for st: String in LID_STATES:
				_rig[k].set_lids(st)
				await process_frame
				if near:
					_near(k)
					cells.append(await _shot("%s %s %s" % [_labels[k], d, st]))
				else:
					cells.append(_tag(await _game_crop(k), "%s %s %s" % [_labels[k], d, st]))
			_rig[k].set_lids("rest")
		_combo(k, "bored", _mouth_of[k])
	if near:
		_grid_cells(cells, 8, Vector2i(320, 240), "states_near.png")
	else:
		_grid_cells(cells, 8, Vector2i(320, 270), "states_game.png")


## A spec value as a shader parameter: [x, y] a Vector2, [x, y, z] a Vector3, else as it is.
func _val(v: Variant) -> Variant:
	if v is Array:
		return Vector2(v[0], v[1]) if (v as Array).size() == 2 else Vector3(v[0], v[1], v[2])
	return v


func _lclosed(hero: String) -> void:
	var cells: Array = []
	_only([hero], false)
	for v: Array in _spec.get("variants", [["", "kit"]]):
		for d: String in ["bored", "manic"]:
			_combo(hero, d, _mouth_of[hero])
			_show_variant(hero, v[0])
			for st: String in (["closed"] if d == "bored" else ["closed", "half"]):
				_rig[hero].set_lids(st)
				await process_frame
				_look(_find(hero, "Eye_L") + Vector3(0, 0.004, 0), 25.0, 2.0, 0.4, 14.0)
				cells.append(await _shot("%s: %s %s" % [v[1], d, st]))
				if st == "closed":
					_eyes_view(hero, 0.0, 0.4)
					cells.append(await _shot("%s: %s %s" % [v[1], d, st]))
			_rig[hero].set_lids("rest")
	_show_variant(hero, "")
	_combo(hero, "bored", _mouth_of[hero])
	_grid_cells(cells, 5, Vector2i(400, 280), "lclosed.png")
