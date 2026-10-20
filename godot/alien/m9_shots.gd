extends "res://alien/m7_shots.gd"
## M9's proofs (art #196): the eyes smaller and nested in one standard socket, beside the liked 2D part sheet e2,
## under the approved look (second_test.gd's stage, light D), no crest, in an off-screen window (the runner's
## _godot.window(), 1536 x 1536). Spec "kits" as m6c_shots.gd (the last one is the hero); spec "e2": the sheet's path,
## "e2_crops": [[x0, y0, x1, y1], ...] its heads' close and whole-head regions (fractions), shown as the first row;
## "designs": the eye designs per kit (default ["bored"]). "modes", in this order:
## - "eyes": eyes.png ("eyes_name"), a row per kit and design: the face from the front and at 3/4 from 0.4 m, then
##   from 1.2 m ("eye_views": [[yaw, pitch, distance], ...] instead, M9b's lid grid);
## - "socket": socket.png, a row per kit and design: the left eye's socket close (front, from the outer side, from
##   above and from below), the place where a lid meets the skin;
## - "blink": m6c_shots.gd's blink_<design>.png (open, rest, half, closed);
## - "designs", "contact", "body": m6c_shots.gd's and m7_shots.gd's (designs.png and hues.png, contact.png, body.png).

const EYE_VIEWS: Array = [[0.0, 2.0, 0.4], [30.0, 2.0, 0.4], [0.0, 2.0, 1.2], [30.0, 2.0, 1.2]]
const SOCKET_VIEWS: Array = [[8.0, 2.0], [55.0, 2.0], [10.0, 35.0], [10.0, -30.0]]


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_modes = _spec.get("modes", ["eyes"])
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
	var hero: String = _keys[-1]
	_pose("Idle", 0.0)
	_only([hero], false)
	for _i: int in 4:
		await process_frame
	if _modes.has("eyes"):
		await _eyes()
	if _modes.has("socket"):
		await _socket()
	if _modes.has("blink"):
		await _blinks()
	if _modes.has("designs"):
		await _designs(hero)
	if _modes.has("contact"):
		await _contact()
	if _modes.has("body"):
		await _body()
	quit(0)


func _e2_row(cols: int) -> Array:
	var cells: Array = []
	var e2: Image = _png(_spec.get("e2", ""))
	for r: Array in _spec.get("e2_crops", []):
		cells.append(_region(e2, r) if e2 != null else null)
	while cells.size() % cols != 0:
		cells.append(null)
	return cells


func _eyes() -> void:
	var views: Array = _spec.get("eye_views", EYE_VIEWS)
	var cells: Array = _e2_row(views.size())
	for k: String in _keys:
		_only([k], false)
		for d: String in _spec.get("designs", ["bored"]):
			_combo(k, d, "frog")
			await process_frame
			for v: Array in views:
				var fv: Array = _face_view(k)
				if v[2] < 1.0:
					_look(fv[0], v[0], v[1], v[2], CLOSE_FOV)
				else:
					_face_at(k, v[0], v[2])
				cells.append(await _shot("%s %s y%d %.1fm" % [_labels[k], d, v[0], v[2]]))
			_combo(k, "bored", "frog")
	_grid_cells(cells, views.size(), Vector2i(400, 400), _spec.get("eyes_name", "eyes.png"))


func _socket() -> void:
	var cells: Array = []
	for k: String in _keys:
		_only([k], false)
		for d: String in _spec.get("designs", ["bored"]):
			_combo(k, d, "frog")
			await process_frame
			var e: Vector3 = _find(k, "Eye_L")
			for v: Array in SOCKET_VIEWS:
				_look(e + Vector3(0, -0.004, 0), v[0], v[1], 0.4, 17.0)
				cells.append(await _shot("%s %s socket y%d p%d" % [_labels[k], d, v[0], v[1]]))
			_combo(k, "bored", "frog")
	_grid_cells(cells, SOCKET_VIEWS.size(), Vector2i(400, 400), "socket.png")
