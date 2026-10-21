extends "res://alien/m10_shots.gd"
## M12's proofs (art #196, brief UPDATE 16): the red pout mouth mp1 ("pout"), the third mouth design, under the
## approved look (second_test.gd's stage, light D), no crest, in an off-screen window (the runner's _godot.window(),
## 1536 x 1536). Spec as m10_shots.gd's, plus "sheet" (the mp1 sheet), "crops" (per shape [x0, y0, x1, y1] of its
## mouth in the sheet, px), "m2_pout" ([png, [x0, y0, x1, y1] shares]: m2's second head), "variants" ([[name, label],
## ...]: the grid kit's lipvar_<name>_pout_<shape> nodes), per kit "mouth" (its design in "head"). "modes":
## - "grid": the reference row (the sheet's rest, A and O, m2's pout head), then per variant rest from the front and
##   at 3/4 at 0.4 m, the face at 3/4 at 1.2 m, A at 3/4 and O from the front (0.4 m): grid.png;
## - "phases": phases.png, per shape the sheet's mouth, then front and 3/4 at 0.4 m; noblack.png, per shape front,
##   3/4 right and left, profile, from below at 0.4 m and 3/4 at 1.2 m (no black anywhere at the mouth);
## - "talk": talk.png, the hero talking alien_talk.gd's LINE in the pout style during Talk_Upper, every 200 ms, 3/4 at
##   0.5 m (the piece, the lower lip's drop and the pucker in each caption); talk_frog.png the same line in frog's;
## - "video": the line at 30 fps (Talk_Upper playing, 3/4 at 0.6 m and the face from the front at 0.45 m) as PNG
##   frames in video/talk_34/ and video/talk_front/ (tools/blender/encode_clips.py makes the MP4s);
## - "clips": clips.png, Idle, Walk and Talk_Upper at four times each, the face at 3/4 from 0.9 m and the body;
## - "hues": hues.png, teal, coral and violet, the pout from the front and at 3/4 at 0.4 m and at 3/4 at 1.2 m;
## - "head": m10_shots.gd's whole-head gate, each kit with its own "mouth";
## - "vgrid" (M12b): the variant grid of the open shapes, vgrid.png: a row of the sheet's mouths, then per variant
##   (spec "variants", the hero's lipvar_<name>_pout_<shape> nodes; first the hero's own pieces, "M12") each piece of
##   spec "vgrid" ([[shape, yaw], ...] at 0.4 m, or [shape, yaw, dist]);
## M13: spec "design" (default "pout") is the design every mode shows ("fangs": the mg2 mouth; "sheet" and "crops" then
## its sheet's), "talk_also" the other designs whose talk.png follows ("talk_<design>.png", default ["frog"]),
## "hero_label" vgrid's first row's label (default "M12").
## - "compare" (M12b): before above after, compare_closed.png (rest, M, small) and compare_open.png (A, E, O): per
##   shape the sheet's mouth, then the first kit's pout (before) and the hero's (after) from the front, at 3/4 and in
##   profile at 0.4 m and at 3/4 at 1.2 m.

const AlienTalkData = preload("res://alien/alien_talk.gd")
const PH_FOV := 20.0  # the phases: about 0.14 m of face at 0.4 m (the crops are 140 px of the sheet: about 0.13 m)
var _mouth_of: Dictionary = {}
var _design: String = "pout"  # M13: the design the proofs show (spec "design")


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
		_mouth_of[k] = kit.get("mouth", "pout")
	var hero: String = _keys[-1]
	_design = _spec.get("design", _design)
	if not _rig[hero].has_mouth_design(_design):
		_fail("the hero kit has no %s mouth" % _design)
		return
	var p: Node3D = _rig[hero].node("mouth_%s_rest" % _design)
	print("PROOF mouth_%s_rest basis " % _design, p.global_transform.basis, " at ", p.global_position)
	_pose("Idle", 0.0)
	_only([hero], false)
	for _i: int in 4:
		await process_frame
	if _modes.has("grid"):
		await _pgrid(hero)
	if _modes.has("phases"):
		await _pphases(hero)
	if _modes.has("talk"):
		await _ptalk(hero, _design, "talk.png")
		for other: String in _spec.get("talk_also", ["frog"]):
			await _ptalk(hero, other, "talk_%s.png" % other)
	if _modes.has("video"):
		await _pvideo(hero)
	if _modes.has("clips"):
		await _pclips(hero)
	if _modes.has("hues"):
		await _phues(hero)
	if _modes.has("head"):
		await _head()
	if _modes.has("vgrid"):
		await _pvgrid(hero)
	if _modes.has("compare"):
		await _pcompare(hero)
	quit(0)


## m10_shots.gd's parts on/off with the kit's own mouth design.
func _parts(k: String, on: bool) -> void:
	super._parts(k, on)
	if on:
		_combo(k, "bored", _mouth_of.get(k, "frog"))


func _crop(shape: String) -> Image:
	var sheet: Image = _png(_spec.get("sheet", ""))
	var c: Array = _spec.get("crops", {}).get(shape, [])
	if sheet == null or c.size() != 4:
		return null
	return sheet.get_region(Rect2i(int(c[0]), int(c[1]), int(c[2]) - int(c[0]), int(c[3]) - int(c[1])))


func _mouth_view(k: String, yaw: float, pitch: float = 2.0, dist: float = 0.4, fov: float = PH_FOV) -> void:
	_look(_find(k, "Mouth") + Vector3(0, -0.004, 0), yaw, pitch, dist, fov)


## Only node `show` among the hero's mouth pieces and grid variants.
func _show_only(k: String, show: String) -> void:
	for n: Node in _ch[k].find_children("*", "", true, false):
		var nm: String = n.name
		if (nm.begins_with("mouth_") or nm.begins_with("lipvar_")) and n is Node3D:
			(n as Node3D).visible = nm == show


func _pgrid(hero: String) -> void:
	var m2: Array = _spec.get("m2_pout", [])
	var refs: Array = [_crop("rest"), _crop("A"), _crop("O"),
		_region(_png(m2[0]), m2[1]) if m2.size() == 2 else null, _crop("E")]
	var cells: Array = refs
	_only([hero], false)
	for v: Array in _spec.get("variants", []):
		_combo(hero, "bored", _design)
		_show_only(hero, "lipvar_%s_%s_rest" % [v[0], _design])
		await process_frame
		_mouth_view(hero, 0.0, 2.0, 0.4, 26.0)
		cells.append(await _shot("%s: спокій, анфас 0.4 м" % v[1]))
		_mouth_view(hero, 35.0, 2.0, 0.4, 26.0)
		cells.append(await _shot("%s: 3/4 0.4 м" % v[1]))
		_face_at(hero, 30.0, 1.2)
		cells.append(await _shot("%s: 3/4 1.2 м" % v[1]))
		_show_only(hero, "lipvar_%s_%s_A" % [v[0], _design])
		_mouth_view(hero, 35.0, 2.0, 0.4, 26.0)
		cells.append(await _shot("%s: A 3/4" % v[1]))
		_show_only(hero, "lipvar_%s_%s_O" % [v[0], _design])
		_mouth_view(hero, 0.0, 2.0, 0.4, 26.0)
		cells.append(await _shot("%s: O анфас" % v[1]))
	_grid_cells(cells, 5, Vector2i(256, 256), "grid.png")
	_combo(hero, "bored", _design)


func _pphases(hero: String) -> void:
	_only([hero], false)
	_pose("Idle", 0.0)
	var cells: Array = []
	var nb: Array = []
	for s: String in SHAPES:
		_combo(hero, "bored", _design, s)
		await process_frame
		cells.append(_crop(s))
		_mouth_view(hero, 0.0)
		cells.append(await _shot("%s %s front 0.4 m" % [_design, s]))
		_mouth_view(hero, 35.0)
		cells.append(await _shot("%s %s 3/4 0.4 m" % [_design, s]))
		var m: Vector3 = _find(hero, "Mouth") + Vector3(0, -0.012, 0)
		for v: Array in MOUTH_VIEWS:
			_look(m, v[0], v[1], v[2], 30.0 if v[2] < 1.0 else 12.0)
			nb.append(await _shot("%s %s y%d p%d %.1fm" % [_design, s, v[0], v[1], v[2]]))
	_grid_cells(cells, 3, Vector2i(420, 420), "phases.png")
	_grid_cells(nb, MOUTH_VIEWS.size(), Vector2i(260, 260), "noblack.png")
	_combo(hero, "bored", _design)


## The talk pose at line time t_ms: Talk_Upper at the same time (looped), the line's sample through the style.
func _talk_pose(hero: String, t_ms: float) -> Dictionary:
	var p: AnimationPlayer = _player[hero]
	var c: String = _clip(p, "Talk_Upper")
	if c != "":
		var length: float = p.get_animation(c).length
		p.play(c)
		p.seek(fmod(t_ms / 1000.0, length), true)
		p.pause()
	return _rig[hero].talk_at(t_ms)


func _ptalk(hero: String, design: String, name: String) -> void:
	_only([hero], false)
	_combo(hero, "bored", design)
	var cells: Array = []
	var t: float = 0.0
	while t <= AlienTalkData.LINE_MS:
		var s: Dictionary = _talk_pose(hero, t)
		await process_frame
		_look(_find(hero, "Mouth") + Vector3(0, 0.02, 0), 30.0, 2.0, 0.5, 30.0)
		cells.append(await _shot("%s %.1f s %s drop %.1f mm pucker %.2f thrust %.1f mm" % [design, t / 1000.0,
			s["piece"], s["drop"] * 1000.0, s["pucker"], s["thrust"] * 1000.0]))
		t += 200.0
	_grid_cells(cells, 6, Vector2i(213, 213), name)
	_rig[hero].set_mouth_motion(0.0, 0.0)
	_combo(hero, "bored", _design)
	_pose("Idle", 0.0)


func _pvideo(hero: String) -> void:
	_only([hero], false)
	_combo(hero, "bored", _design)
	_label.text = ""
	var n: int = int(ceil(AlienTalkData.LINE_MS / 1000.0 * 30.0))
	for view: Array in [["talk_34", 30.0, 0.6, 0.02], ["talk_front", 0.0, 0.45, 0.03]]:
		var dir: String = "%s/video/%s" % [_out, view[0]]
		DirAccess.make_dir_recursive_absolute(dir)
		for i: int in n:
			var t: float = float(i) * 1000.0 / 30.0
			_talk_pose(hero, t)
			_look(_find(hero, "Mouth") + Vector3(0, view[3], 0), view[1], 2.0, view[2], 30.0)
			_label.text = ""
			await process_frame
			await process_frame
			await RenderingServer.frame_post_draw
			var img: Image = root.get_texture().get_image()
			img.resize(720, 720, Image.INTERPOLATE_LANCZOS)
			img.save_png("%s/%04d.png" % [dir, i])
		print("PROOF video ", view[0], " frames ", n)
	_rig[hero].set_mouth_motion(0.0, 0.0)
	_pose("Idle", 0.0)


func _pclips(hero: String) -> void:
	_only([hero], false)
	_combo(hero, "bored", _design)
	var cells: Array = []
	for word: String in ["Idle", "Walk", "Talk_Upper"]:
		for i: int in 4:
			var tt: float = -0.05 - 0.3 * float(i)  # shares of the clip (negative: m5's seek by share)
			_pose(word, tt)
			_combo(hero, "bored", _design, ["rest", "A", "O", "E"][i] if word == "Talk_Upper" else "rest")
			await process_frame
			_look(_find(hero, "Mouth") + Vector3(0, 0.04, 0), 30.0, 2.0, 0.9, 30.0)
			cells.append(await _shot("%s %.0f %% face" % [word, -tt * 100.0]))
		var view: Array = _body_view(hero, 30.0, 0.85)
		_view(view)
		cells.append(await _shot("%s body" % word))
	_grid_cells(cells, 5, Vector2i(256, 256), "clips.png")
	_pose("Idle", 0.0)
	_combo(hero, "bored", _design)


func _phues(hero: String) -> void:
	_only([hero], false)
	var cells: Array = []
	for h: String in HUE_NAMES:
		_rig[hero].set_hue(h)
		_combo(hero, "bored", _design)
		await process_frame
		_mouth_view(hero, 0.0, 2.0, 0.4, 26.0)
		cells.append(await _shot("%s front 0.4 m" % h))
		_mouth_view(hero, 35.0, 2.0, 0.4, 26.0)
		cells.append(await _shot("%s 3/4 0.4 m" % h))
		_face_at(hero, 30.0, 1.2)
		cells.append(await _shot("%s 3/4 1.2 m" % h))
	_rig[hero].set_hue("teal")
	_grid_cells(cells, 3, Vector2i(420, 420), "hues.png")


func _pvgrid(hero: String) -> void:
	var views: Array = _spec.get("vgrid", [["A", 0.0], ["A", 35.0], ["E", 0.0], ["E", 35.0], ["O", 0.0], ["O", 35.0]])
	var cells: Array = []
	for v: Array in views:
		cells.append(_crop(v[0]))
	_only([hero], false)
	_combo(hero, "bored", _design)
	var rows: Array = [["", _spec.get("hero_label", "M12")]]
	rows.append_array(_spec.get("variants", []))
	for r: Array in rows:
		for v: Array in views:
			_show_only(hero, ("mouth_%s_%s" % [_design, v[0]]) if r[0] == "" else ("lipvar_%s_%s_%s" % [r[0], _design, v[0]]))
			await process_frame
			_mouth_view(hero, v[1], 2.0, float(v[2]) if v.size() > 2 else 0.4, PH_FOV)  # M13b: [shape, yaw, dist]
			cells.append(await _shot("%s %s y%d" % [r[1], v[0], v[1]]))
	var px: int = int(_spec.get("vgrid_px", 0))
	if px <= 0:
		px = mini(320, 1280 / views.size())
	_grid_cells(cells, views.size(), Vector2i(px, px), "vgrid.png")
	_combo(hero, "bored", _design)


func _pcompare(hero: String) -> void:
	var before: String = _keys[0]
	for part: Array in [["compare_closed.png", ["rest", "M", "small"]], ["compare_open.png", ["A", "E", "O"]]]:
		var cells: Array = []
		for s: String in part[1]:
			for k: String in [before, hero]:
				cells.append(_crop(s) if k == before else null)
				_only([k], false)
				_combo(k, "bored", _design, s)
				await process_frame
				for v: Array in [[0.0, 0.4], [35.0, 0.4], [90.0, 0.4]]:
					_mouth_view(k, v[0], 2.0, v[1], PH_FOV)
					cells.append(await _shot("%s %s y%d %.1f m" % [_labels[k], s, v[0], v[1]]))
				_face_at(k, 30.0, 1.2)
				cells.append(await _shot("%s %s 3/4 1.2 m" % [_labels[k], s]))
		_grid_cells(cells, 5, Vector2i(256, 256), part[0])
	_only([hero], false)
	_combo(hero, "bored", _design)
