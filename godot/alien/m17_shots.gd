extends "res://alien/m15_shots.gd"
## M17's proofs (art #196, brief UPDATE 36): the socket's edge against the lids (the pale ring at game distance) and
## the lids' AO over the blink, under the approved look (second_test.gd's stage, light D), in an off-screen window
## (the runner's _godot.window(), 1536 x 1536). Spec as m15_shots.gd's; a kit may carry "hue": {uniform: value} set
## on its textured skin material (a contact-shade variant on the same kit). Modes, besides m15_shots.gd's:
## - "rim": per kit two rows of four: bored's socket at 0.4 m, manic closed at 0.4 m, bored at 3/4 from 1.2 m, manic
##   from the front at 1.2 m; then the 3.5 m view (the lgame crop, 3x nearest) bored and manic, lashes off and on:
##   rim.png ("rim_name").


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_modes = _spec.get("modes", ["rim"])
	if not _modes.has("rim"):
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
		_lashes_of[k] = kit.get("lashes", false)
		_rig[k].set_lashes(_lashes_of[k])
		if kit.has("aim_in_deg"):
			_rig[k].aim_in_deg = float(kit["aim_in_deg"])
		var mat: ShaderMaterial = _rig[k]._tex_material
		for u: String in kit.get("hue", {}):
			var v: Variant = kit["hue"][u]
			mat.set_shader_parameter(u, Vector3(v[0], v[1], v[2]) if v is Array else v)
			print("PROOF kit %s hue %s = %s" % [k, u, str(v)])
	_pose("Idle", 0.0)
	for _i: int in 4:
		await process_frame
	await _rim()
	quit(0)


func _game_crop(k: String) -> Image:
	_look(_head_target(k), 20.0, 2.0, 3.5, 70.0)
	var img: Image = await _shot("")
	var r: Rect2i = _screen_rect(k, 0.16)
	var crop: Image = img.get_region(r.grow_individual(0, r.size.y / 2, 0, r.size.y))
	crop.resize(crop.get_width() * 3, crop.get_height() * 3, Image.INTERPOLATE_NEAREST)
	return _tag(crop, _labels[k])


func _rim() -> void:
	var cells: Array = []
	for k: String in _keys:
		_only([k], false)
		_rig[k].set_lashes(_lashes_of[k])
		_combo(k, "bored", _mouth_of[k])
		_rig[k].set_lids("rest")
		await process_frame
		_look(_find(k, "Eye_L") + Vector3(0, -0.004, 0), 8.0, 2.0, 0.4, 17.0)
		cells.append(await _shot("%s bored 0.4 м" % _labels[k]))
		_combo(k, "manic", _mouth_of[k])
		_rig[k].set_lids("closed")
		await process_frame
		_look(_find(k, "Eye_L") + Vector3(0, 0.004, 0), 25.0, 2.0, 0.4, 14.0)
		cells.append(await _shot("%s manic closed" % _labels[k]))
		_rig[k].set_lids("rest")
		_combo(k, "bored", _mouth_of[k])
		await process_frame
		_eyes_view(k, 30.0, 1.2)
		cells.append(await _shot("%s bored 3/4 1.2 м" % _labels[k]))
		_combo(k, "manic", _mouth_of[k])
		await process_frame
		_eyes_view(k, 0.0, 1.2)
		cells.append(await _shot("%s manic 1.2 м" % _labels[k]))
		for on: bool in [false, true]:
			for d: String in ["bored", "manic"]:
				_combo(k, d, _mouth_of[k])
				_rig[k].set_lashes(on)
				await process_frame
				cells.append(await _game_crop(k))
		_rig[k].set_lashes(_lashes_of[k])
		_combo(k, "bored", _mouth_of[k])
	_grid_cells(cells, 4, Vector2i(320, 320), _spec.get("rim_name", "rim.png"))
