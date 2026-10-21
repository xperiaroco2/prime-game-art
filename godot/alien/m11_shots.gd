extends "res://alien/m12_shots.gd"
## M11's proofs (art #196, brief UPDATE 21): the upper lashes (el2) on both eye designs, under the approved look
## (second_test.gd's stage, light D), no crest, in an off-screen window (the runner's _godot.window(), 1536 x 1536).
## Spec as m12_shots.gd's, plus "el2" (the el2 sheet: six 512 px panels), per kit "lashes" (on or off) and "mouth",
## "variants" ([[name, label], ...]: the grid kit's lashvar_<name>_<design>_<side> nodes). Every lashvar_ node is
## hidden after loading. "modes" (the hero is the last kit):
## - "lgrid": el2's eyes (rest, half, closed, wide), then per variant the eyes from the front, at 3/4 and in profile at
##   0.4 m, at 3/4 at 1.2 m and the left eye close (bored; "lgrid_design" for another): lgrid_<design>.png;
## - "lviews": el2's row, then per design the hero with lashes, front / 3/4 / profile at 0.4 m and 3/4 at 1.2 m:
##   lviews.png;
## - "lblink": per design open, rest, half and closed, the left eye close (0.4 m) and both eyes from the front:
##   lblink.png;
## - "lsizes": every kit (the eye sizes) front and 3/4 at 0.4 m and 3/4 at 1.2 m, both designs: lsizes.png;
## - "lmouths": the hero with each mouth design it has (lashes on), front and 3/4 at 0.6 m: lmouths.png;
## - "lhues": teal, coral, violet with lashes, front at 0.4 m and 3/4 at 1.2 m: lhues.png;
## - "lgame": the game's distance: the hero at 3.5 m (FOV 70, a 1536 px frame: the head about 50 px tall) with and
##   without lashes, and 3x crops of the head (nearest); then 24 frames of Idle with a blink at 3.5 m and at 1.2 m as
##   PNGs in game/far and game/near (the shimmer check: PROOF lines give the mean frame-to-frame change round the eyes;
##   M11b: also Idle without the blink at 3.5 and 3.0 m, game/faridle and game/mididle);
## - "lfade" (M11b): the lashes' fade with distance, bored and manic with lashes at 1.2, 2.0, 2.4, 2.8, 3.2, 3.5 and
##   4.5 m (FOV 70), the head's eye band cropped and scaled to one size (nearest): lfade.png;
## - "lvideo": a blink and talk line (the hero's mouth, its talk style, blinks at 0.5, 2.3 and 4.0 s) at 30 fps,
##   3/4 at 0.6 m and front at 0.45 m, as PNG frames in video/lash_34/ and video/lash_front/;
## - "head": m10_shots.gd's whole-head gate (each kit with its own "lashes" and "mouth");
## - "socket": m9_shots.gd's socket close-ups (the collar from four sides) of every kit.

const EL2_PANELS: Array = [0, 1, 2, 5]  # rest, half, closed, wide (the sheet's panels, row-major)
const EYE_BAND := [0.17, 0.36, 0.83, 0.66]  # a panel's eye band (shares of the 512 px panel)
const BLINK_AT_MS: Array = [500.0, 2300.0, 4000.0]
var _lashes_of: Dictionary = {}


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
	quit(0)


## m12_shots.gd's parts on/off, then the kit's own lashes again.
func _parts(k: String, on: bool) -> void:
	super._parts(k, on)
	if on:
		_rig[k].set_lashes(_lashes_of.get(k, false))


func _el2_row(cols: int) -> Array:
	var sheet: Image = _png(_spec.get("el2", ""))
	var cells: Array = []
	if sheet != null:
		for i: int in EL2_PANELS:
			var px: int = (i % 3) * 512
			var py: int = (i / 3) * 512
			cells.append(sheet.get_region(Rect2i(px + int(EYE_BAND[0] * 512), py + int(EYE_BAND[1] * 512),
				int((EYE_BAND[2] - EYE_BAND[0]) * 512), int((EYE_BAND[3] - EYE_BAND[1]) * 512))))
	while cells.size() % cols != 0:
		cells.append(null)
	return cells


## Both eyes framed: yaw (degrees), from dist m (FOV for about 0.2 m of face at 0.4 m).
func _eyes_view(k: String, yaw: float, dist: float = 0.4, pitch: float = 2.0) -> void:
	var e: Vector3 = (_find(k, "Eye_L") + _find(k, "Eye_R")) * 0.5 + Vector3(0, 0.004, 0)
	if dist >= 1.0:
		_face_at(k, yaw, dist)
		return
	_look(e, yaw, pitch, dist, 42.0 if absf(yaw) < 60.0 else 30.0)


func _views() -> Array:
	return [["анфас 0.4 м", 0.0, 0.4], ["3/4 0.4 м", 35.0, 0.4], ["профіль 0.4 м", 90.0, 0.4], ["3/4 1.2 м", 30.0, 1.2]]


## Only lashvar_<v> (or the kit's own set when v is ""), on the shown design.
func _show_variant(k: String, v: String) -> void:
	for n: Node in _ch[k].find_children("*", "", true, false):
		var nm: String = n.name
		if nm.begins_with("lashvar_"):
			(n as Node3D).visible = v != "" and nm.begins_with("lashvar_%s_" % v)
	_rig[k].set_lashes(v == "")


func _lgrid(hero: String) -> void:
	var design: String = _spec.get("lgrid_design", "bored")
	var cells: Array = _el2_row(5)
	_only([hero], false)
	_combo(hero, design, _mouth_of[hero])
	for v: Array in _spec.get("variants", []):
		_show_variant(hero, v[0])
		await process_frame
		for view: Array in _views():
			_eyes_view(hero, view[1], view[2])
			cells.append(await _shot("%s: %s" % [v[1], view[0]]))
		_look(_find(hero, "Eye_L") + Vector3(0, 0.004, 0), 25.0, 2.0, 0.4, 14.0)  # the left eye close
		cells.append(await _shot("%s: ліве око зблизька" % v[1]))
	_show_variant(hero, "")
	_rig[hero].set_lashes(_lashes_of[hero])
	_grid_cells(cells, 5, Vector2i(480, 320), "lgrid_%s.png" % design)


func _lviews(hero: String) -> void:
	var cells: Array = _el2_row(4)
	_only([hero], false)
	for d: String in ["bored", "manic"]:
		_combo(hero, d, _mouth_of[hero])
		_rig[hero].set_lashes(true)
		await process_frame
		for view: Array in _views():
			_eyes_view(hero, view[1], view[2])
			cells.append(await _shot("%s, вії: %s" % [d, view[0]]))
	_combo(hero, "bored", _mouth_of[hero])
	_rig[hero].set_lashes(_lashes_of[hero])
	_grid_cells(cells, 4, Vector2i(480, 320), "lviews.png")


func _lblink(hero: String) -> void:
	var cells: Array = _el2_row(4)
	_only([hero], false)
	_rig[hero].set_lashes(true)
	for d: String in ["bored", "manic"]:
		_combo(hero, d, _mouth_of[hero])
		for close: bool in [true, false]:
			for st: String in LID_STATES:
				_rig[hero].set_lids(st)
				await process_frame
				if close:
					_look(_find(hero, "Eye_L") + Vector3(0, 0.004, 0), 25.0, 2.0, 0.4, 14.0)
				else:
					_eyes_view(hero, 0.0, 0.4)
				cells.append(await _shot("%s %s" % [d, st]))
		_rig[hero].set_lids("rest")
	_combo(hero, "bored", _mouth_of[hero])
	_rig[hero].set_lashes(_lashes_of[hero])
	_grid_cells(cells, 4, Vector2i(480, 320), "lblink.png")


func _lsizes() -> void:
	var cells: Array = []
	for k: String in _keys:
		_only([k], false)
		for d: String in ["bored", "manic"]:
			_combo(k, d, _mouth_of[k])
			_rig[k].set_lashes(true)
			await process_frame
			for view: Array in [["анфас 0.4 м", 0.0, 0.4], ["3/4 0.4 м", 35.0, 0.4], ["3/4 1.2 м", 30.0, 1.2]]:
				_eyes_view(k, view[1], view[2])
				cells.append(await _shot("%s %s: %s" % [_labels[k], d, view[0]]))
		_rig[k].set_lashes(_lashes_of[k])
		_combo(k, "bored", _mouth_of[k])
	_only([_keys[-1]], false)
	_grid_cells(cells, 6, Vector2i(400, 300), "lsizes.png")


func _lmouths(hero: String) -> void:
	var cells: Array = []
	_only([hero], false)
	_rig[hero].set_lashes(true)
	for m: String in MOUTH_DESIGNS_ALL:
		if not _rig[hero].has_mouth_design(m):
			continue
		for d: String in ["bored", "manic"]:
			_combo(hero, d, m)
			await process_frame
			for yaw: float in [0.0, 30.0]:
				_look(_head_target(hero) + Vector3(0, 0.0, 0), yaw, 2.0, 0.6, 30.0)
				cells.append(await _shot("%s + %s, вії, %s 0.6 м" % [d, m, "анфас" if yaw == 0.0 else "3/4"]))
	_combo(hero, "bored", _mouth_of[hero])
	_rig[hero].set_lashes(_lashes_of[hero])
	_grid_cells(cells, 4, Vector2i(400, 400), "lmouths.png")


const MOUTH_DESIGNS_ALL: Array[String] = ["frog", "overbite", "pout", "fangs"]


func _lhues(hero: String) -> void:
	var cells: Array = []
	_only([hero], false)
	_rig[hero].set_lashes(true)
	for h: String in HUE_NAMES:
		_rig[hero].set_hue(h)
		for d: String in ["bored", "manic"]:
			_combo(hero, d, _mouth_of[hero])
			await process_frame
			_eyes_view(hero, 0.0, 0.4)
			cells.append(await _shot("%s %s анфас 0.4 м" % [h, d]))
			_eyes_view(hero, 30.0, 1.2)
			cells.append(await _shot("%s %s 3/4 1.2 м" % [h, d]))
	_rig[hero].set_hue("teal")
	_combo(hero, "bored", _mouth_of[hero])
	_rig[hero].set_lashes(_lashes_of[hero])
	_grid_cells(cells, 4, Vector2i(400, 400), "lhues.png")


## The mean change (0..1) between two frames in a region (shares) round the eyes.
func _change(a: Image, b: Image, r: Rect2i) -> float:
	var s: float = 0.0
	var n: int = 0
	for y: int in range(r.position.y, r.end.y):
		for x: int in range(r.position.x, r.end.x):
			var ca: Color = a.get_pixel(x, y)
			var cb: Color = b.get_pixel(x, y)
			s += (absf(ca.r - cb.r) + absf(ca.g - cb.g) + absf(ca.b - cb.b)) / 3.0
			n += 1
	return s / maxf(1.0, float(n))


func _screen_rect(k: String, half: float) -> Rect2i:
	var cam: Camera3D = _camera
	var e: Vector3 = (_find(k, "Eye_L") + _find(k, "Eye_R")) * 0.5
	var c: Vector2 = cam.unproject_position(e)
	var off: Vector2 = cam.unproject_position(e + Vector3(half, 0, 0)) - c
	var h: int = maxi(4, int(absf(off.x)))
	return Rect2i(int(c.x) - h, int(c.y) - h / 2, 2 * h, h)


func _lgame(hero: String) -> void:
	var cells: Array = []
	_only([hero], false)
	_combo(hero, "bored", _mouth_of[hero])
	for d: String in ["bored", "manic"]:
		_combo(hero, d, _mouth_of[hero])
		for on: bool in [false, true]:
			_rig[hero].set_lashes(on)
			_look(_head_target(hero), 20.0, 2.0, 3.5, 70.0)
			var img: Image = await _shot("")
			var r: Rect2i = _screen_rect(hero, 0.16)
			var crop: Image = img.get_region(r.grow_individual(0, r.size.y / 2, 0, r.size.y))
			crop.resize(crop.get_width() * 3, crop.get_height() * 3, Image.INTERPOLATE_NEAREST)
			cells.append(crop)
			print("PROOF game %s lashes %s: the eyes' box %s px at 3.5 m" % [d, on, r.size])
	_grid_cells(cells, 2, Vector2i(480, 400), "lgame.png")
	# the shimmer check: Idle at 30 fps with one blink, with and without lashes
	_combo(hero, "bored", _mouth_of[hero])
	# M11b: also Idle alone (no blink) at 3.5 and 3.0 m, the line's own crawl apart from the lid's motion
	for view: Array in [["far", 3.5, 70.0, true], ["near", 1.2, 30.0, true], ["faridle", 3.5, 70.0, false],
			["mididle", 3.0, 70.0, false]]:
		for on: bool in [false, true]:
			_rig[hero].set_lashes(on)
			var dir: String = "%s/game/%s_%s" % [_out, view[0], "on" if on else "off"]
			DirAccess.make_dir_recursive_absolute(dir)
			var prev: Image = null
			var tot: float = 0.0
			for i: int in 24:
				_pose("Idle", float(i) / 30.0)
				if view[3]:
					_rig[hero].blink_at(float(i) * 1000.0 / 30.0 - 150.0)
				_look(_head_target(hero), 20.0, 2.0, view[1], view[2])
				_label.text = ""
				await process_frame
				await process_frame
				await RenderingServer.frame_post_draw
				var img: Image = root.get_texture().get_image()
				var r: Rect2i = _screen_rect(hero, 0.16)
				if prev != null:
					tot += _change(prev, img, r)
				prev = img
				var crop: Image = img.get_region(r.grow_individual(0, r.size.y / 2, 0, r.size.y))
				crop.save_png("%s/%04d.png" % [dir, i])
			print("PROOF shimmer %s lashes %s: mean frame-to-frame change round the eyes %.5f" % [view[0], on, tot / 23.0])
			_rig[hero].set_lids("rest")
	_rig[hero].set_lashes(_lashes_of[hero])
	_pose("Idle", 0.0)


func _lfade(hero: String) -> void:
	var cells: Array = []
	_only([hero], false)
	for d: String in ["bored", "manic"]:
		_combo(hero, d, _mouth_of[hero])
		_rig[hero].set_lashes(true)
		for dist: float in [1.2, 2.0, 2.4, 2.8, 3.2, 3.5, 4.5]:
			_look(_head_target(hero), 20.0, 2.0, dist, 70.0)
			var img: Image = await _shot("")
			var r: Rect2i = _screen_rect(hero, 0.16)
			var crop: Image = img.get_region(r.grow_individual(0, r.size.y / 2, 0, r.size.y / 2))
			crop.resize(360, int(360.0 * crop.get_height() / maxf(1.0, crop.get_width())), Image.INTERPOLATE_NEAREST)
			cells.append(crop)
			print("PROOF fade %s %.1f m: the eyes' box %s px" % [d, dist, r.size])
	_grid_cells(cells, 7, Vector2i(360, 220), "lfade.png")
	_rig[hero].set_lashes(_lashes_of[hero])


func _lvideo(hero: String) -> void:
	_only([hero], false)
	_combo(hero, "bored", _mouth_of[hero])
	_rig[hero].set_lashes(true)
	_label.text = ""
	var n: int = int(ceil(AlienTalkData.LINE_MS / 1000.0 * 30.0))
	for view: Array in [["lash_34", 30.0, 0.6, 0.02], ["lash_front", 0.0, 0.45, 0.03]]:
		var dir: String = "%s/video/%s" % [_out, view[0]]
		DirAccess.make_dir_recursive_absolute(dir)
		for i: int in n:
			var t: float = float(i) * 1000.0 / 30.0
			_talk_pose(hero, t)
			_rig[hero].set_lids("rest")
			for b: float in BLINK_AT_MS:
				if t >= b and t < b + 200.0:
					_rig[hero].blink_at(t - b)
			_look(_find(hero, "Mouth") + Vector3(0, view[3] + 0.03, 0), view[1], 2.0, view[2], 30.0)
			_label.text = ""
			await process_frame
			await process_frame
			await RenderingServer.frame_post_draw
			var img: Image = root.get_texture().get_image()
			img.resize(720, 720, Image.INTERPOLATE_LANCZOS)
			img.save_png("%s/%04d.png" % [dir, i])
		print("PROOF video ", view[0], " frames ", n)
	_rig[hero].set_mouth_motion(0.0, 0.0)
	_rig[hero].set_lids("rest")
	_rig[hero].set_lashes(_lashes_of[hero])
	_pose("Idle", 0.0)
