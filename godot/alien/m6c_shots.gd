extends "res://alien/m6_shots.gd"
## M6c's proofs (art #196): the skin's grain back on M2b's sculpt, one contact channel per design, the manic eyes,
## under the approved look (second_test.gd's stage, light D), no crest, Idle at frame 0, in an off-screen window (the
## runner's _godot.window(), 1536 x 1536). Spec "kits": [{"key", "res", "look" ("m5" or "m6"), "label"}, ...] in
## column order (the last one is the hero, the kit under test); "modes", in this order:
## - "cmp": cmp.png, a column per kit then rf2; rows rf2's framing, the front at 1.2 m, the face at 3/4 and from the
##   front at 0.4 m (rf2's eye crop there); the hero's tiles alone (hero_face_34.png, front.png, close_34.png,
##   close_front.png);
## - "designs": designs.png, the hero's four eye x mouth designs, 3/4 and front at 1.2 m (teal); hues.png, a row per
##   hue (teal, coral, violet): 3/4 at 1.2 m, the face at 3/4 and from the front at 0.4 m, manic with the overbite;
## - "contact": contact.png and contact_debug.png, a row per kit with a contact marker, a column per design pair
##   (bored frog, bored overbite, manic frog, manic overbite), the face from the front at 0.45 m; the debug sheet
##   draws the contact shade black (contact_tint 0, contact_ao 1), so where it lands shows;
## - "blink": blink_bored.png and blink_manic.png, a row per kit: open, rest, half, closed, the left eye from the front;
## - "manic": manic.png, a row per kit: the manic eyes at 3/4 from 0.4 m, the left eye from the front at rest and open.
## Each kit's CUSTOM1 maxima are logged ("PROOF <key> custom1 ..."): an M6c kit carries four channels.

const HUE_NAMES: Array[String] = ["teal", "coral", "violet"]
const PAIRS: Array = [["bored", "frog"], ["bored", "overbite"], ["manic", "frog"], ["manic", "overbite"]]

var _keys: Array = []
var _labels: Dictionary = {}


## Body's CUSTOM1 per component maxima (RG_FLOAT: 2, RGBA_FLOAT: 4 floats a vertex).
func _custom1(ch: Node3D) -> Array:
	var body: MeshInstance3D = ch.find_child("Body", true, false) as MeshInstance3D
	if body == null:
		return []
	var best: Array = []
	for s: int in body.mesh.get_surface_count():
		var arr: Array = body.mesh.surface_get_arrays(s)
		var c: Variant = arr[Mesh.ARRAY_CUSTOM1]
		var n: int = (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()
		if not c is PackedFloat32Array or n == 0:
			continue
		var a: PackedFloat32Array = c
		var per: int = a.size() / n
		if best.is_empty():
			best.resize(per)
			best.fill(0.0)
		for i: int in a.size():
			best[i % per] = maxf(best[i % per], a[i])
	return best


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_modes = _spec.get("modes", ["cmp"])
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
	var rf2_eye: Image = _region(rf2, _spec.get("rf2_eye", [0.17, 0.26, 0.67, 0.76])) if rf2 != null else null
	if _modes.has("cmp"):
		await _cmp(hero, rf2, rf2_eye)
	if _modes.has("designs"):
		await _designs(hero)
	if _modes.has("contact"):
		await _contact()
	if _modes.has("channels"):
		await _channels(hero)
	if _modes.has("blink"):
		await _blinks()
	if _modes.has("manic"):
		await _manic()
	quit(0)


func _frame(k: String, row: String) -> void:
	var fv: Array = _face_view(k)
	match row:
		"hero":
			_view(fv)
		"front":
			_face_at(k, 0.0)
		"close":
			_look(fv[0], 30.0, 2.0, 0.4, CLOSE_FOV)
		"close_front":
			_look(fv[0], 0.0, 2.0, 0.4, CLOSE_FOV)


func _cmp(hero: String, rf2: Image, rf2_eye: Image) -> void:
	var cells: Array = []
	var names := {"hero": "hero_face_34.png", "front": "front.png", "close": "close_34.png",
		"close_front": "close_front.png"}
	for row: String in ["hero", "front", "close", "close_front"]:
		for k: String in _keys:
			_only([k], false)
			await process_frame
			_frame(k, row)
			var img: Image = await _shot(_labels[k])
			if k == hero:
				_save(names[row], img.duplicate())
			cells.append(img)
		cells.append(rf2_eye if row.begins_with("close") else rf2)
	_grid_cells(cells, _keys.size() + 1, Vector2i(640, 640), "cmp.png")
	_only([hero], false)


func _designs(hero: String) -> void:
	_only([hero], false)
	var cells: Array = []
	for p: Array in PAIRS:
		_combo(hero, p[0], p[1])
		await process_frame
		_face_at(hero, 30.0)
		cells.append(await _shot("%s %s" % p))
		_face_at(hero, 0.0)
		cells.append(await _shot("%s %s" % p))
	_grid_cells(cells, 4, Vector2i(480, 480), "designs.png")
	cells = []
	for h: String in HUE_NAMES:
		_rig[hero].set_hue(h)
		_combo(hero, "bored", "frog")
		await process_frame
		for row: String in ["hero", "close", "close_front"]:
			_frame(hero, row)
			cells.append(await _shot("%s bored frog" % h))
		_combo(hero, "manic", "overbite")
		await process_frame
		_frame(hero, "hero")
		cells.append(await _shot("%s manic overbite" % h))
	_rig[hero].set_hue("teal")
	_combo(hero, "bored", "frog")
	_grid_cells(cells, 4, Vector2i(480, 480), "hues.png")


func _contact() -> void:
	var dbg := {"skin": {"contact_tint": [0.0, 0.0, 0.0], "contact_ao": 1.0}}
	for sheet: String in ["contact.png", "contact_debug.png"]:
		var cells: Array = []
		var cols: int = 0
		for k: String in _keys:
			if _rig[k].lip_look == "m5":
				continue
			_only([k], false)
			var undo := {}
			if sheet == "contact_debug.png":
				_lip_apply(k, dbg, undo)
			for p: Array in PAIRS:
				_combo(k, p[0], p[1])
				await process_frame
				var fv: Array = _face_view(k)
				_look(fv[0], 0.0, 2.0, 0.45, CLOSE_FOV)
				cells.append(await _shot("%s %s %s" % [_labels[k], p[0], p[1]]))
			_combo(k, "bored", "frog")
			if sheet == "contact_debug.png":
				_lip_restore(k, undo)
			cols = PAIRS.size()
		_grid_cells(cells, cols, Vector2i(480, 480), sheet)


## The hero's contact channels, the shade drawn black: per shown design pair the picked channels (as alien.gd picks
## them) beside every channel at once (M6's one field, what the overbite and the manic eyes showed before).
func _channels(hero: String) -> void:
	var sm: ShaderMaterial = _rig[hero].skin_material()
	var undo := {}
	_lip_apply(hero, {"skin": {"contact_tint": [0.0, 0.0, 0.0], "contact_ao": 1.0}}, undo)
	_only([hero], false)
	var cells: Array = []
	for p: Array in [["bored", "overbite"], ["manic", "frog"], ["manic", "overbite"]]:
		_combo(hero, p[0], p[1])
		await process_frame
		var fv: Array = _face_view(hero)
		for all: bool in [false, true]:
			if all:
				sm.set_shader_parameter("contact_pick", Vector4.ONE)
			_look(fv[0], 0.0, 2.0, 0.45, CLOSE_FOV)
			cells.append(await _shot("%s %s: %s" % [p[0], p[1], "every channel (M6)" if all else "picked (M6c)"]))
		_combo(hero, "bored", "frog")  # set_eyes / set_mouth_design pick again
	_lip_restore(hero, undo)
	_grid_cells(cells, 2, Vector2i(640, 640), "channels.png")


func _blinks() -> void:
	for d: String in ["bored", "manic"]:
		var cells: Array = []
		for k: String in _keys:
			_only([k], false)
			_combo(k, d, "frog")
			for st: String in LID_STATES:
				_rig[k].set_lids(st)
				_eye_front(k)
				cells.append(await _shot("%s %s %s" % [_labels[k], d, st]))
			_rig[k].set_lids("rest")
			_combo(k, "bored", "frog")
		_grid_cells(cells, 4, Vector2i(400, 400), "blink_%s.png" % d)


func _manic() -> void:
	var cells: Array = []
	for k: String in _keys:
		_only([k], false)
		_combo(k, "manic", "frog")
		await process_frame
		var fv: Array = _face_view(k)
		_look(fv[0] + Vector3(0, 0.03, 0), 30.0, 2.0, 0.4, CLOSE_FOV)
		cells.append(await _shot("%s manic 3/4" % _labels[k]))
		for st: String in ["rest", "open"]:
			_rig[k].set_lids(st)
			_eye_front(k)
			cells.append(await _shot("%s manic %s" % [_labels[k], st]))
		_rig[k].set_lids("rest")
		_combo(k, "bored", "frog")
	_grid_cells(cells, 3, Vector2i(480, 480), "manic.png")
