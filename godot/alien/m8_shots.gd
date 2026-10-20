extends "res://alien/m6c_shots.gd"
## M8's proofs (art #196): the lips shaped like lips (alien_lips_geom.py), under the approved look (second_test.gd's
## stage, light D), teal, no crest, Idle at frame 0, in an off-screen window (the runner's _godot.window(),
## 1536 x 1536). Spec "kits" as m6c_shots.gd (column order; the last is the hero), "modes", in this order:
## - "grid": the hero is the grid kit (alien_m8.py --grid: nodes lipvar_<variant>_<design>_<shape>); per spec
##   "variants" entry (names, the M6c lips first) a row: frog rest from the front and at 3/4 at 0.4 m (the mouth
##   framed), frog rest at 3/4 from 1.2 m (the face), frog A at 3/4 at 0.4 m, overbite rest from the front at 0.4 m;
##   the first row is the references (mf1 rest, rf2's mouth, rf2, mf1 A, mo1 rest). grid_a.png and grid_b.png;
## - "phases": phases_frog.png and phases_overbite.png, a row per shape (rest, M, small, A, E, O): the sheet's panel,
##   then before (the first kit) and after (the hero) from the front, at 3/4 and in profile, the mouth at 0.4 m;
## - "talk": talk.png, the hero talking (Idle at 0.6 s): rest, M, A, E, O, small at 3/4 from 1.2 m, then at 0.4 m;
## - "cmp": m6c_shots.gd's cmp.png (rf2's framing, the front at 1.2 m, the face at 3/4 and from the front at 0.4 m;
##   before | after | rf2) with spec "rf2_eye" the rf2 crop of the close rows.
## Spec: m6c_shots.gd's plus "variants" (names), "sheets" {"frog": png, "overbite": png} (mf1, mo1).

const SHAPES: Array[String] = ["rest", "M", "small", "A", "E", "O"]
const MOUTH_FOV := 26.0  # the mouth from 0.4 m: about 0.18 m of face (the grid)
const PHASE_FOV := 20.0  # the phases: about 0.14 m
const PANEL_PHASE := [166, 210, 346, 390]  # the same 0.14 m on the sheets (K 0.78 mm per px)
const PANEL := 512
const PANEL_MOUTH := [138, 182, 374, 418]  # a panel's mouth window on the sheets (px in the 512 px panel)
const RF2_MOUTH := [0.31, 0.52, 0.57, 0.78]  # rf2's mouth, shares of the image


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_modes = _spec.get("modes", ["phases"])
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
		print("PROOF ", k, " custom1 ", _custom1(_ch[k]))
	var hero: String = _keys[-1]
	_pose("Idle", 0.0)
	_only([hero], false)
	for _i: int in 4:
		await process_frame
	var rf2: Image = _png(_spec.get("beside", ""))
	if _modes.has("grid"):
		await _grid(hero, rf2)
	if _modes.has("phases"):
		for d: String in ["frog", "overbite"]:
			await _phases(d)
	if _modes.has("talk"):
		await _talk(hero)
	if _modes.has("cmp"):
		var rf2_face: Image = _region(rf2, _spec.get("rf2_eye", [0.2, 0.36, 0.62, 0.78])) if rf2 != null else null
		_pose("Idle", 0.0)
		await _cmp(hero, rf2, rf2_face)
	quit(0)


## Panel k's mouth window of a talk-shape sheet (3 x 2 panels of 512 px).
func _panel(sheet: Image, k: int, r: Array = PANEL_MOUTH) -> Image:
	if sheet == null:
		return null
	var x0: int = (k % 3) * PANEL
	var y0: int = (k / 3) * PANEL
	return sheet.get_region(Rect2i(x0 + r[0], y0 + r[1], r[2] - r[0], r[3] - r[1]))


func _mouth_at(k: String, yaw: float, dist: float = 0.4, fov: float = MOUTH_FOV) -> void:
	_look(_find(k, "Mouth") + Vector3(0, -0.004, 0), yaw, 2.0, dist, fov)


## Only node `show` among the hero's mouth pieces and grid variants (all hidden when show is "").
func _show_piece(k: String, show: String) -> void:
	var ch: Node3D = _ch[k]
	for n: Node in ch.find_children("*", "", true, false):
		var nm: String = n.name
		if (nm.begins_with("mouth_") or nm.begins_with("lipvar_")) and n is Node3D:
			(n as Node3D).visible = nm == show


func _grid(hero: String, rf2: Image) -> void:
	var sheets: Dictionary = _spec.get("sheets", {})
	var mf1: Image = _png(sheets.get("frog", ""))
	var mo1: Image = _png(sheets.get("overbite", ""))
	var refs: Array = [_panel(mf1, 0), _region(rf2, RF2_MOUTH) if rf2 != null else null, rf2, _panel(mf1, 3),
		_panel(mo1, 0)]
	var variants: Array = _spec.get("variants", [])
	var halves: Array = [variants.slice(0, 5), variants.slice(5)]
	_only([hero], false)
	for h: int in halves.size():
		var cells: Array = refs.duplicate()
		for v: String in halves[h]:
			_combo(hero, "bored", "frog")
			_show_piece(hero, "lipvar_%s_frog_rest" % v)
			await process_frame
			_mouth_at(hero, 0.0)
			cells.append(await _shot("%s frog rest" % v))
			_mouth_at(hero, 30.0)
			cells.append(await _shot("%s 3/4 0.4 m" % v))
			_face_at(hero, 30.0, 1.2)
			cells.append(await _shot("%s 3/4 1.2 m" % v))
			_show_piece(hero, "lipvar_%s_frog_A" % v)
			_mouth_at(hero, 30.0)
			cells.append(await _shot("%s frog A" % v))
			_combo(hero, "bored", "overbite")
			_show_piece(hero, "lipvar_%s_overbite_rest" % v)
			_mouth_at(hero, 0.0)
			cells.append(await _shot("%s overbite rest" % v))
		_grid_cells(cells, 5, Vector2i(320, 320), "grid_%s.png" % ["a", "b"][h])
	_combo(hero, "bored", "frog")


func _phases(design: String) -> void:
	var sheet: Image = _png(_spec.get("sheets", {}).get(design, ""))
	var before: String = _keys[0]
	var after: String = _keys[-1]
	var cells: Array = []
	for i: int in SHAPES.size():
		var s: String = SHAPES[i]
		cells.append(_panel(sheet, i, PANEL_PHASE))
		for view: Array in [[0.0, "front"], [35.0, "3/4"], [90.0, "profile"]]:
			for k: String in [before, after]:
				_only([k], false)
				_combo(k, "bored", design, s)
				await process_frame
				_mouth_at(k, view[0], 0.4, PHASE_FOV)
				cells.append(await _shot("%s %s %s %s" % [_labels[k], design, s, view[1]]))
	_grid_cells(cells, 7, Vector2i(256, 256), "phases_%s.png" % design)
	for k: String in [before, after]:
		_combo(k, "bored", "frog")


func _talk(hero: String) -> void:
	_only([hero], false)
	_pose("Idle", 0.6)
	var cells: Array = []
	for d: String in ["frog", "overbite"]:
		for s: String in ["rest", "M", "A", "E", "O", "small"]:
			_combo(hero, "bored", d, s)
			await process_frame
			_face_at(hero, 30.0, 1.2)
			cells.append(await _shot("%s talking: %s" % [d, s]))
	for s: String in ["rest", "M", "A", "E", "O", "small"]:
		_combo(hero, "bored", "frog", s)
		await process_frame
		_look(_face_view(hero)[0], 30.0, 2.0, 0.4, CLOSE_FOV)
		cells.append(await _shot("frog talking 0.4 m: %s" % s))
	_grid_cells(cells, 6, Vector2i(320, 320), "talk.png")
	_combo(hero, "bored", "frog")
	_pose("Idle", 0.0)
