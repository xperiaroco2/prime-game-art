extends "res://alien/m12_shots.gd"
## Test B's proofs (art #196, brief UPDATE 53): the mouth sculpted into the head (tools/blender/alien_muzzle.py). The
## hero kit's Body carries the welded lips and the morph targets `jaw` (14 degrees at weight 1) and `O`; its mouth_*
## pieces are hidden, the pout design shown for its contact channel. The first kit is the before (M20d's pout rest
## piece). Under the approved look (second_test.gd's stage, light D) in the off-screen window. Spec as m12_shots.gd's,
## plus "refs" ({name: [png, [x0, y0, x1, y1] px]}), "jaw_deg" (the morph's full angle), "talk" ([jaw weight per
## frame at 30 fps]), "gate_y" (the nose line's height, Godot y). "modes":
## - "sheet": sheet.png, the 2D refs, then the before, then per state (closed, jaw 8, jaw 14, O) front / 3/4 /
##   profile at 0.4 m, 3/4 at 1.2 m and at 3.5 m (fov 20.6: the game's pixels per metre at 3.5 m in a 256 px cell);
## - "pairs": pairs.png, the 2D beside our closest view (u1 side | profile, rf2 | 3/4, mp1 rest | front, mp1 A |
##   jaw 14 front);
## - "gate": gate.png and the PROOF gate lines: before and after from the front, 3/4, profile and the back, the mean
##   and largest pixel change above the nose line;
## - "diag": diag.png, the hero from the front as imported and with Body's mesh copied without its blend shapes
##   (does the morph change the skin's look);
## - "video": the talk at 30 fps (3/4 at 0.6 m, front at 0.45 m) as PNG frames in video/talk_34, video/talk_front.

const FOV_35M := 20.6
var _jaw_deg: float = 14.0
var _tb_lips: MeshInstance3D  # Body's lip and mouth surfaces on their own instance (see _tb_split)


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_modes = _spec.get("modes", ["sheet"])
	_jaw_deg = _spec.get("jaw_deg", 14.0)
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
		_mouth_of[k] = "pout"
	var hero: String = _keys[-1]
	_tb_split(hero)
	var body: MeshInstance3D = _tb_body(hero)
	print("PROOF blend shapes ", body.mesh.get_blend_shape_count(), " jaw ", body.find_blend_shape_by_name("jaw"),
		" O ", body.find_blend_shape_by_name("O"), " surfaces ", body.mesh.get_surface_count())
	_pose("Idle", 0.0)
	for _i: int in 4:
		await process_frame
	if _modes.has("sheet"):
		await _tb_psheet(hero)
	if _modes.has("pairs"):
		await _tb_ppairs(hero)
	if _modes.has("gate"):
		await _tb_pgate(hero)
	if _modes.has("diag"):
		await _tb_diag(hero)
	if _modes.has("video"):
		await _tb_ptbvideo(hero)
	quit(0)


func _tb_body(k: String) -> MeshInstance3D:
	return _ch[k].find_child("Body", true, false) as MeshInstance3D


## The hero with no mouth piece (its lips are Body's), or the before with its pout rest piece.
func _tb_state(k: String, jaw: float, o: float = 0.0) -> void:
	_only([k], false)
	_combo(k, "bored", "pout")
	var hero: bool = k == _keys[-1]
	if hero:
		_show_only(k, "")
	var b: MeshInstance3D = _tb_body(k)
	var ij: int = b.find_blend_shape_by_name("jaw")
	var io: int = b.find_blend_shape_by_name("O")
	for mi: MeshInstance3D in ([b, _tb_lips] if hero and _tb_lips != null else [b]):
		if ij >= 0:
			mi.set_blend_shape_value(ij, jaw)
		if io >= 0:
			mi.set_blend_shape_value(io, o)


func _tb_ref(name: String) -> Image:
	var r: Array = _spec.get("refs", {}).get(name, [])
	if r.size() != 2:
		return null
	var img: Image = _png(r[0])
	if img == null:
		return null
	var c: Array = r[1]
	return img.get_region(Rect2i(int(c[0]), int(c[1]), int(c[2]) - int(c[0]), int(c[3]) - int(c[1])))


func _tb_near(k: String, yaw: float) -> void:
	_look(_find(k, "Mouth") + Vector3(0, 0.012, 0), yaw, 2.0, 0.4, 28.0)


func _tb_far(k: String, yaw: float, dist: float, fov: float) -> void:
	var eyes: Vector3 = (_find(k, "Eye_L") + _find(k, "Eye_R")) * 0.5
	var mouth: Vector3 = _find(k, "Mouth")
	_look((eyes + mouth) * 0.5 + Vector3(0, 0.02, 0), yaw, 2.0, dist, fov)


func _tb_views(k: String, tag: String) -> Array:
	var cells: Array = []
	for v: Array in [[0.0, "front 0.4 m"], [35.0, "3/4 0.4 m"], [90.0, "profile 0.4 m"]]:
		_tb_near(k, v[0])
		cells.append(await _shot("%s %s" % [tag, v[1]]))
	_tb_far(k, 30.0, 1.2, 30.0)
	cells.append(await _shot("%s 3/4 1.2 m" % tag))
	_tb_far(k, 30.0, 3.5, FOV_35M)
	cells.append(await _shot("%s 3/4 3.5 m" % tag))
	return cells


func _tb_psheet(hero: String) -> void:
	var cells: Array = [_tb_ref("u1_side"), _tb_ref("rf2"), _tb_ref("mp1_rest"), _tb_ref("mp1_A"), _tb_ref("mp1_O")]
	var before: String = _keys[0]
	_tb_state(before, 0.0)
	await process_frame
	cells += await _tb_views(before, "M20d piece")
	for s: Array in [[0.0, 0.0, "closed"], [8.0 / _jaw_deg, 0.0, "jaw 8"], [1.0, 0.0, "jaw 14"], [0.0, 1.0, "O"]]:
		_tb_state(hero, s[0], s[1])
		await process_frame
		cells += await _tb_views(hero, "TB " + s[2])
	_grid_cells(cells, 5, Vector2i(256, 256), "sheet.png")
	_tb_state(hero, 0.0)


func _tb_ppairs(hero: String) -> void:
	var cells: Array = []
	_tb_state(hero, 0.0)
	await process_frame
	cells.append(_tb_ref("u1_side"))
	_tb_far(hero, 90.0, 0.75, 30.0)
	cells.append(await _shot("TB closed, profile 0.75 m"))
	cells.append(_tb_ref("rf2"))
	_tb_far(hero, 28.0, 0.75, 30.0)
	cells.append(await _shot("TB closed, 3/4 0.75 m"))
	cells.append(_tb_ref("mp1_rest"))
	_tb_near(hero, 0.0)
	cells.append(await _shot("TB closed, front 0.4 m"))
	cells.append(_tb_ref("mp1_A"))
	_tb_state(hero, 1.0)
	await process_frame
	_tb_near(hero, 0.0)
	cells.append(await _shot("TB jaw 14, front 0.4 m"))
	_grid_cells(cells, 4, Vector2i(320, 320), "pairs.png")
	_tb_state(hero, 0.0)


func _tb_pgate(hero: String) -> void:
	var before: String = _keys[0]
	var gate_y: float = _spec.get("gate_y", 1.505)
	var cells: Array = []
	for yaw: float in [0.0, 35.0, 90.0, 180.0]:
		var imgs: Array = []
		var row: int = 0
		for k: String in [before, hero]:
			_tb_state(k, 0.0)
			await process_frame
			_tb_far(k, yaw, 0.6, 30.0)
			var m: Vector3 = _find(k, "Mouth")
			row = int(_camera.unproject_position(Vector3(m.x, gate_y, m.z)).y)
			imgs.append(await _shot(""))
		var a: Image = imgs[0]
		var b: Image = imgs[1]
		var tot: float = 0.0
		var most: float = 0.0
		var n: int = 0
		for y: int in range(0, mini(row, a.get_height())):
			for x: int in range(0, a.get_width(), 2):
				var ca: Color = a.get_pixel(x, y)
				var cb: Color = b.get_pixel(x, y)
				var d: float = (absf(ca.r - cb.r) + absf(ca.g - cb.g) + absf(ca.b - cb.b)) / 3.0
				tot += d
				most = maxf(most, d)
				n += 1
		print("PROOF gate yaw %d above row %d: mean %.4f max %.4f" % [int(yaw), row, tot / maxf(n, 1.0), most])
		for img: Image in imgs:
			var c: Image = img.duplicate()
			for x: int in c.get_width():
				for t: int in 3:
					if row + t < c.get_height():
						c.set_pixel(x, row + t, Color(1, 0.2, 0.2))
			cells.append(c)
	_grid_cells(cells, 4, Vector2i(320, 320), "gate.png")


func _tb_ptbvideo(hero: String) -> void:
	_label.text = ""
	var talk: Array = _spec.get("talk", [])
	for view: Array in [["talk_34", 30.0, 0.6, 0.02], ["talk_front", 0.0, 0.45, 0.03]]:
		var dir: String = "%s/video/%s" % [_out, view[0]]
		DirAccess.make_dir_recursive_absolute(dir)
		for i: int in talk.size():
			var p: AnimationPlayer = _player[hero]
			var c: String = _clip(p, "Talk_Upper")
			if c != "":
				p.play(c)
				p.seek(fmod(float(i) / 30.0, p.get_animation(c).length), true)
				p.pause()
			_tb_state(hero, float(talk[i]))
			_look(_find(hero, "Mouth") + Vector3(0, view[3], 0), view[1], 2.0, view[2], 30.0)
			var img: Image = await _shot("", 2)
			img.save_png("%s/%04d.png" % [dir, i])
	_pose("Idle", 0.0)
	_tb_state(hero, 0.0)


func _tb_diag(hero: String) -> void:
	var cells: Array = []
	_tb_state(hero, 0.0)
	await process_frame
	_tb_far(hero, 0.0, 0.6, 30.0)
	cells.append(await _shot("TB as imported"))
	var b: MeshInstance3D = _tb_body(hero)
	var src: ArrayMesh = b.mesh
	var am := ArrayMesh.new()
	for s: int in src.get_surface_count():
		var fmt: int = src.surface_get_format(s)
		var flags: int = fmt & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS
		for c: int in 4:
			var sh: int = Mesh.ARRAY_FORMAT_CUSTOM_BASE + c * Mesh.ARRAY_FORMAT_CUSTOM_BITS
			flags |= ((fmt >> sh) & Mesh.ARRAY_FORMAT_CUSTOM_MASK) << sh
		am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, src.surface_get_arrays(s), [], {}, flags)
		am.surface_set_material(s, src.surface_get_material(s))
	b.mesh = am
	await process_frame
	cells.append(await _shot("TB without blend shapes"))
	b.mesh = src
	_grid_cells(cells, 2, Vector2i(512, 512), "diag.png")


## Godot draws instance uniforms per instance: alien.gd sets the skin's `hue` and `pale` on Body's MeshInstance, and
## with the lip and mouth materials on the same instance their slots collide (the skin falls back to its flat colour).
## So Body's surfaces after the first (the lips' alien_lip_pout, the mouth's alien_mouth_inner) are drawn by a sibling
## instance with the same vertices, blend shapes and skin: the GLB keeps one mesh, one surface of vertices.
func _tb_split(k: String) -> void:
	var b: MeshInstance3D = _tb_body(k)
	var src: ArrayMesh = b.mesh
	if src.get_surface_count() < 2:
		return
	var parts: Array = [ArrayMesh.new(), ArrayMesh.new()]
	for am: ArrayMesh in parts:
		am.blend_shape_mode = src.blend_shape_mode
		for i: int in src.get_blend_shape_count():
			am.add_blend_shape(src.get_blend_shape_name(i))
	var mats: Array = [[], []]
	for s: int in src.get_surface_count():
		var fmt: int = src.surface_get_format(s)
		var flags: int = fmt & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS
		for c: int in 4:
			var sh: int = Mesh.ARRAY_FORMAT_CUSTOM_BASE + c * Mesh.ARRAY_FORMAT_CUSTOM_BITS
			flags |= ((fmt >> sh) & Mesh.ARRAY_FORMAT_CUSTOM_MASK) << sh
		var which: int = 0 if s == 0 else 1
		(parts[which] as ArrayMesh).add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, src.surface_get_arrays(s),
			src.surface_get_blend_shape_arrays(s), {}, flags)
		var ov: Material = b.get_surface_override_material(s)
		mats[which].append(ov if ov != null else src.surface_get_material(s))
	var skel: Node = b.get_node_or_null(b.skeleton)
	b.mesh = parts[0]
	b.set_surface_override_material(0, mats[0][0])
	_tb_lips = MeshInstance3D.new()
	_tb_lips.name = "BodyLips"
	_tb_lips.mesh = parts[1]
	b.get_parent().add_child(_tb_lips)
	_tb_lips.transform = b.transform
	_tb_lips.skin = b.skin
	if skel != null:
		_tb_lips.skeleton = _tb_lips.get_path_to(skel)
	for i: int in mats[1].size():
		_tb_lips.set_surface_override_material(i, mats[1][i])
	print("PROOF split Body: skin 1 surface, lips ", mats[1].size(), " surfaces")
