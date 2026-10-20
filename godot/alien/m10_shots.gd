extends "res://alien/m9_shots.gd"
## M10's proofs (art #196, brief UPDATE 12): smaller eyes and plumper lips on M8b's unchanged skull, under the
## approved look (second_test.gd's stage, light D), no crest, in an off-screen window (the runner's _godot.window(),
## 1536 x 1536). Spec as m9_shots.gd's; "refs": [[png, [x0, y0, x1, y1]], ...] the reference row's crops (fractions:
## the liked sheets e2 and m2), in place of "e2_crops". "modes", in this order:
## - "grid": m9_shots.gd's "eyes" (a row per kit and design over the refs row; "eyes_name", "eye_views");
## - "head": head.png, the whole-head gate: the first kit (before) against each other (after), front, 3/4, profile and
##   top. Per pair seven rows: before and after with every part and their difference (x4); before and after with no
##   eye or mouth part in one plain grey material (the skull's shape alone, no texture) and their difference (x4);
##   the silhouettes' difference (an unshaded white pass, no part). PROOF lines give per view the share of pixels
##   changed by more than 8 / 255 and the silhouette's changed pixels;
## - "socket", "blink", "mouths", "designs", "contact", "body": m9_shots.gd's, m6c_shots.gd's and m7_shots.gd's.

const HEAD_VIEWS: Array = [["front", 0.0, 2.0], ["3/4", 35.0, 2.0], ["profile", 90.0, 2.0], ["top", 0.0, 75.0]]
const HEAD_DIST := 1.05
const HEAD_FOV := 26.0
const DIFF_GAIN := 4.0
const DIFF_THRESHOLD := 8.0 / 255.0


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_modes = _spec.get("modes", ["grid"])
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
	if _modes.has("grid"):
		await _eyes()
	if _modes.has("head"):
		await _head()
	if _modes.has("socket"):
		await _socket()
	if _modes.has("blink"):
		await _blinks()
	if _modes.has("mouths"):
		await _mouths()
	if _modes.has("designs"):
		await _designs(hero)
	if _modes.has("contact"):
		await _contact()
	if _modes.has("body"):
		await _body()
	quit(0)


func _e2_row(cols: int) -> Array:
	if not _spec.has("refs"):
		return super(cols)
	var cells: Array = []
	for r: Array in _spec["refs"]:
		var img: Image = _png(r[0])
		cells.append(_region(img, r[1]) if img != null else null)
	while cells.size() % cols != 0:
		cells.append(null)
	return cells




var _hidden: Dictionary = {}  # kit -> the part meshes _parts hid


## Every eye and mouth part of a kit shown (on: the meshes _parts hid back, then the default combo) or hidden (off):
## the skull and skin alone for the gate.
func _parts(k: String, on: bool) -> void:
	if on:
		for m: MeshInstance3D in _hidden.get(k, []):
			m.visible = true
		_hidden[k] = []
		_combo(k, "bored", "frog")
		return
	var hid: Array = []
	for m: Node in _ch[k].find_children("*", "MeshInstance3D", true, false):
		var n: String = m.name
		if (n.begins_with("eye_") or n.begins_with("mouth_") or n.contains("_lid_") or n.contains("_wet_")) \
				and (m as MeshInstance3D).visible:
			(m as MeshInstance3D).visible = false
			hid.append(m)
	_hidden[k] = hid


## One material over every mesh of a kit (null: their own back): the clay pass (a plain lit grey, so only the shape
## shades) and the silhouette pass (unshaded white).
func _override(k: String, mat: Material) -> void:
	for m: Node in _ch[k].find_children("*", "MeshInstance3D", true, false):
		(m as MeshInstance3D).material_override = mat


func _head_target(k: String) -> Vector3:
	var eyes: Vector3 = (_find(k, "Eye_L") + _find(k, "Eye_R")) * 0.5
	var mouth: Vector3 = _find(k, "Mouth")
	return Vector3(0.0, (eyes.y + mouth.y) * 0.5 + 0.035, (eyes.z + mouth.z) * 0.5 - 0.05)


func _head_shot(k: String, v: Array, text: String) -> Image:
	_look(_head_target(k), v[1], v[2], HEAD_DIST, HEAD_FOV)
	var img: Image = await _shot(text)
	img.convert(Image.FORMAT_RGB8)
	img.resize(768, 768, Image.INTERPOLATE_BILINEAR)  # the diffs loop per pixel
	return img


## |a - b| times DIFF_GAIN, and the share of pixels changed by more than DIFF_THRESHOLD in any channel.
func _diff(a: Image, b: Image) -> Array:
	var w: int = mini(a.get_width(), b.get_width())
	var h: int = mini(a.get_height(), b.get_height())
	var d := Image.create(w, h, false, Image.FORMAT_RGB8)
	var changed: int = 0
	for y: int in h:
		for x: int in w:
			var ca: Color = a.get_pixel(x, y)
			var cb: Color = b.get_pixel(x, y)
			var dr: float = absf(ca.r - cb.r)
			var dg: float = absf(ca.g - cb.g)
			var db: float = absf(ca.b - cb.b)
			if maxf(dr, maxf(dg, db)) > DIFF_THRESHOLD:
				changed += 1
			d.set_pixel(x, y, Color(minf(1.0, dr * DIFF_GAIN), minf(1.0, dg * DIFF_GAIN), minf(1.0, db * DIFF_GAIN)))
	return [d, float(changed) / float(w * h)]


## Two silhouette passes (unshaded white on the stage): white where only one of them covers a pixel, grey where both
## do; and the count of the white.
func _silhouette_diff(a: Image, b: Image) -> Array:
	var w: int = a.get_width()
	var h: int = a.get_height()
	var d := Image.create(w, h, false, Image.FORMAT_RGB8)
	var n: int = 0
	for y: int in h:
		for x: int in w:
			var ia: bool = a.get_pixel(x, y).v > 0.85
			var ib: bool = b.get_pixel(x, y).v > 0.85
			if ia != ib:
				n += 1
				d.set_pixel(x, y, Color(1, 1, 1))
			else:
				d.set_pixel(x, y, Color(0.25, 0.25, 0.25) if ia else Color(0, 0, 0))
	return [d, n]


func _head() -> void:
	var before: String = _keys[0]
	var cells: Array = []
	var cols: int = HEAD_VIEWS.size()
	var clay := StandardMaterial3D.new()
	clay.albedo_color = Color(0.6, 0.6, 0.6)
	clay.roughness = 0.7
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color(1, 1, 1)
	for k: String in _keys.slice(1):
		var rows: Array = [[], [], [], [], [], [], []]
		for v: Array in HEAD_VIEWS:
			var shots: Dictionary = {}
			for kk: String in [before, k]:
				_only([kk], false)
				_parts(kk, true)
				await process_frame
				shots[kk + "_parts"] = await _head_shot(kk, v, "")
				shots[kk + "_parts_tag"] = await _head_shot(kk, v, "%s %s" % [_labels[kk], v[0]])
				_parts(kk, false)
				_override(kk, clay)
				await process_frame
				shots[kk + "_clay"] = await _head_shot(kk, v, "")
				shots[kk + "_clay_tag"] = await _head_shot(kk, v, "%s %s (skull, plain grey, no part)" % [
					_labels[kk], v[0]])
				_override(kk, white)
				_label.text = ""
				await process_frame
				shots[kk + "_sil"] = await _head_shot(kk, v, "")
				_override(kk, null)
				_parts(kk, true)
			var dp: Array = _diff(shots[before + "_parts"], shots[k + "_parts"])
			var ds: Array = _diff(shots[before + "_clay"], shots[k + "_clay"])
			var sil: Array = _silhouette_diff(shots[before + "_sil"], shots[k + "_sil"])
			print("PROOF head %s vs %s %s: with parts changed %.4f, skull (plain grey, no part) changed %.4f, "
				% [_labels[before], _labels[k], v[0], dp[1], ds[1]] + "silhouette changed %d px" % sil[1])
			rows[0].append(shots[before + "_parts_tag"])
			rows[1].append(shots[k + "_parts_tag"])
			rows[2].append(_tag(dp[0], "diff x4 %.2f %%" % (dp[1] * 100.0)))
			rows[3].append(shots[before + "_clay_tag"])
			rows[4].append(shots[k + "_clay_tag"])
			rows[5].append(_tag(ds[0], "skull diff x4 %.2f %%" % (ds[1] * 100.0)))
			rows[6].append(_tag(sil[0], "silhouette diff %d px" % sil[1]))
		for r: Array in rows:
			cells.append_array(r)
	_only([_keys[-1]], false)
	_grid_cells(cells, cols, Vector2i(360, 360), _spec.get("head_name", "head.png"))


## A computed tile (a difference) has no viewport label: its caption goes to the log (the rows' order is in the header).
func _tag(img: Image, text: String) -> Image:
	print("PROOF tile ", text)
	return img
