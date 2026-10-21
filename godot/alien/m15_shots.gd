extends "res://alien/m11_shots.gd"
## M15's proofs (art #196, brief UPDATE 26): the eye socket rebuilt for the 80 % eye, under the approved look
## (second_test.gd's stage, light D), no crest, in an off-screen window (the runner's _godot.window(), 1536 x 1536).
## Spec as m11_shots.gd's, plus "refs" (m10_shots.gd's reference row: [[png, [x0, y0, x1, y1]], ...]). Modes, besides
## m11_shots.gd's:
## - "depth": the reference row, then per kit three rows: bored and manic with the kit's own lashes and mouth, and
##   bored with the skin in one plain grey (the parts keep their look, so only the socket's shape shades), each from
##   the front, at 3/4 and in profile at 0.4 m and at 3/4 from 1.2 m: depth.png ("depth_name").

const CLAY_SKIN := Color(0.62, 0.62, 0.62)


## m11_shots.gd's run with "depth" before the quit.
func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_modes = _spec.get("modes", ["lviews"])
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
		for n: Node in _ch[k].find_children("lashvar_*", "", true, false):
			(n as Node3D).visible = false
		_rig[k].set_lashes(_lashes_of[k])
		print("PROOF kit %s lashes %s (has %s) mouth %s" % [k, _lashes_of[k], _rig[k].has_lashes(), _mouth_of[k]])
	var hero: String = _keys[-1]
	_pose("Idle", 0.0)
	_only([hero], false)
	for _i: int in 4:
		await process_frame
	if _modes.has("lgrid"):
		await _lgrid(hero)
	if _modes.has("lviews"):
		await _lviews(hero)
	if _modes.has("lblink"):
		await _lblink(hero)
	if _modes.has("lsizes"):
		await _lsizes()
	if _modes.has("lmouths"):
		await _lmouths(hero)
	if _modes.has("lhues"):
		await _lhues(hero)
	if _modes.has("lgame"):
		await _lgame(hero)
	if _modes.has("lfade"):
		await _lfade(hero)
	if _modes.has("lvideo"):
		await _lvideo(hero)
	if _modes.has("head"):
		await _head()
	if _modes.has("socket"):
		await _socket()
	if _modes.has("depth"):
		await _depth()
	quit(0)


## The skin (the Body and any skin collar) in one plain grey, or its own material back (on false).
func _clay_skin(k: String, on: bool, mat: Material) -> void:
	for m: Node in _ch[k].find_children("*", "MeshInstance3D", true, false):
		var nm: String = m.name
		if nm.begins_with("Body") or nm.contains("_collar_"):
			(m as MeshInstance3D).material_override = mat if on else null


func _depth() -> void:
	var cells: Array = _e2_row(4)
	var clay := StandardMaterial3D.new()
	clay.albedo_color = CLAY_SKIN
	clay.roughness = 0.7
	for k: String in _keys:
		_only([k], false)
		for row: Array in [["bored", false], ["manic", false], ["bored", true]]:
			_combo(k, row[0], _mouth_of[k])
			_rig[k].set_lashes(_lashes_of[k])
			_clay_skin(k, row[1], clay)
			await process_frame
			for view: Array in _views():
				_eyes_view(k, view[1], view[2])
				cells.append(await _shot("%s %s%s: %s" % [_labels[k], row[0], ", сірий" if row[1] else "", view[0]]))
			_clay_skin(k, false, clay)
		_combo(k, "bored", _mouth_of[k])
	_grid_cells(cells, 4, Vector2i(480, 320), _spec.get("depth_name", "depth.png"))
