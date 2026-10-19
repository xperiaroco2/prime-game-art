extends "res://alien/hero_shots.gd"
## M5's proofs (art #196): the alien on its texture set (alien_hue.gdshader `textured`) under the approved look
## (second_test.gd's stage: AgX 0.9, the studio sky, SSAO, light D), teal, eyes bored, mouth frog, no crest, in an
## off-screen window (run through the runner's _godot.window(), 1536 x 1536). Spec "modes", in this order:
## - "hero": hero_face_34.png at the paintover rf2's framing (hero_shots.gd's face camera, spec "face");
## - "turntable": turntable.png, a 3840 x 1920 sheet of 768 x 960 cells: rf2, then the body at 0..135 degrees; the
##   hero face, then 180..315 (the character turns under the fixed lights); each cell also as turn_<deg>.png;
## - "close": close_34.png and close_front.png, the face from 0.4 m;
## - "compare": before_after.png, rows face (rf2's framing), close (0.4 m) and body three-quarter; columns the
##   spec's "before" scene (S9d, the procedural skin), the M5 kit and the target (rf2; spec "body_ref" for the body);
## - "grid": grid_<grid_name>.png (rf2, then the face under each spec "variants" entry: hero_shots.gd's form, applied
##   to the textured skin material) and zoom_<grid_name>.png (spec "grid_zoom");
## - "room": room.png, before, teal, coral and violet side by side on the stand at game distance (spec "room":
##   {"dist", "eye", "fov"}; the camera at eye height, as a player), and room_hues.png, the three hues closer;
## - "taa": taa.png, the close face and the body under MSAA 2x, TAA, both, and FSR 2 at 1.0 scale, each with the
##   GPU ms of the frame (median of 40), and taa_zoom.png, the face's eye and lid zoomed; m5_shots.json "gpu_ms";
## - "clips": clips/<clip>/<nnnn>.png, every frame of one cycle of each spec "clips" (default Idle, Walk) at 30 fps,
##   the body three-quarter at 768 x 960, for tools/blender/encode_clips.py; with spec "taa" true under TAA (the
##   stills stay without it: a cut leaves TAA's history of the last view in the first frames).
## Spec: hero_shots.gd's ("scenes": {"hero", "before"?}, "out", "hdri", "beside", "bg", "face"), plus "modes",
## "skin" (alien_hue.gdshader uniforms over alien.gd SKIN_TEX for the whole run: the chosen tuning), "variants",
## "grid_name", "grid_zoom", "grid_view" ("face" or "close"), "body_ref", "room", "clips", "taa".

const CELL := Vector2i(768, 960)
const CLOSE_FOV := 50.0  # the close face from 0.4 m: the whole face (30 degrees showed one eye)

var _modes: Array = []


func _add(k: String, res: String, hue: String) -> bool:
	var packed: PackedScene = load(res) as PackedScene
	if packed == null:
		_fail("cannot load %s" % res)
		return false
	var ch: Node3D = packed.instantiate()
	root.add_child(ch)
	var rig: Node = AlienRig.new()
	ch.add_child(rig)
	rig.setup(ch)
	rig.auto_blink = false
	rig.set_crest("")
	rig.set_hue(hue)
	_ch[k] = ch
	_rig[k] = rig
	_player[k] = ch.find_child("AnimationPlayer", true, false)
	_combo(k, "bored", "frog")
	print("PROOF ", k, " textured ", rig.is_textured())
	return true


## The centre of a shot cropped to an aspect (width / height), scaled to size.
func _cell(img: Image, size: Vector2i) -> Image:
	var w: int = img.get_width()
	var h: int = img.get_height()
	var aspect: float = float(size.x) / size.y
	var cw: int = mini(w, int(round(h * aspect)))
	var chh: int = mini(h, int(round(cw / aspect)))
	var c: Image = img.get_region(Rect2i((w - cw) / 2, (h - chh) / 2, cw, chh))
	c.convert(Image.FORMAT_RGB8)
	c.resize(size.x, size.y, Image.INTERPOLATE_LANCZOS)
	return c


func _grid_cells(cells: Array, cols: int, size: Vector2i, name: String) -> void:
	var rows: int = int(ceil(float(cells.size()) / cols))
	var sheet := Image.create(size.x * cols, size.y * rows, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.1, 0.1, 0.1))
	for i: int in cells.size():
		if cells[i] == null:
			continue
		sheet.blit_rect(_cell(cells[i], size), Rect2i(Vector2i.ZERO, size), Vector2i((i % cols) * size.x, (i / cols) * size.y))
	_save(name, sheet)


func _face_view(k: String) -> Array:
	var fc: Dictionary = _spec.get("face", {})
	var eyes: Vector3 = (_find(k, "Eye_L") + _find(k, "Eye_R")) * 0.5
	var mouth: Vector3 = _find(k, "Mouth")
	var mid: Vector3 = (eyes + mouth) * 0.5 + Vector3(0, fc.get("dy", -0.04), -(eyes.z + mouth.z) * 0.5 + fc.get("z", 0.0))
	return [mid, fc.get("yaw", 30.0), fc.get("pitch", 2.0), fc.get("dist", 0.9), fc.get("fov", 30.0)]


func _body_view(k: String, yaw: float, fill: float = 0.85, fov: float = 24.0) -> Array:
	var box: AABB = _bounds(_ch[k])
	var mid := Vector3(_ch[k].position.x, box.position.y + box.size.y * 0.5, 0)
	return [mid, yaw, 2.0, box.size.y / (fill * 2.0 * tan(deg_to_rad(fov * 0.5))), fov]


func _view(v: Array) -> void:
	_look(v[0], v[1], v[2], v[3], v[4])


func _png(path: String) -> Image:
	if path == "":
		return null
	var img: Image = Image.load_from_file(path)
	return null if img == null or img.is_empty() else img


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_modes = _spec.get("modes", ["hero"])
	_stage()
	if _spec.has("bg"):
		_backdrop(_spec["bg"])
	var scenes: Dictionary = _spec["scenes"]
	_order = []
	if scenes.has("before"):
		_order.append("before")
		if not _add("before", scenes["before"], "teal"):
			return
	_order.append("hero")
	if not _add("hero", scenes["hero"], "teal"):
		return
	if _modes.has("room"):
		for h: String in ["coral", "violet"]:
			_order.append(h)
			if not _add(h, scenes["hero"], h):
				return
	var skin: Dictionary = _spec.get("skin", {})
	for k: String in _ch:
		if _rig[k].is_textured():
			_apply(_rig[k].skin_material(), skin, {})
	_pose("Idle", 0.0)
	_only(["hero"], false)
	for _i: int in 4:
		await process_frame
	var rf2: Image = _png(_spec.get("beside", ""))
	var face: Image = null
	if _modes.has("hero") or _modes.has("turntable"):
		_view(_face_view("hero"))
		face = await _shot("")
		_save("hero_face_34.png", face.duplicate())
		if rf2 != null:
			_sheet([face, rf2], 2, "beside.png")
	if _modes.has("turntable"):
		var cells: Array = [rf2]
		var turns: Dictionary = {}
		for deg: int in range(0, 360, 45):
			_spin(["hero"], float(deg))
			_view(_body_view("hero", 0.0, 0.9))
			var img: Image = await _shot("")
			turns[deg] = img
			var c: Image = _cell(img, CELL)
			_save("turn_%03d.png" % deg, c)
		_spin(["hero"], 0.0)
		cells += [turns[0], turns[45], turns[90], turns[135], face, turns[180], turns[225], turns[270], turns[315]]
		_grid_cells(cells, 5, CELL, "turntable.png")
	if _modes.has("close"):
		var fv: Array = _face_view("hero")
		_look(fv[0], 30.0, 2.0, 0.4, CLOSE_FOV)
		_save("close_34.png", await _shot(""))
		_look(fv[0], 0.0, 2.0, 0.4, CLOSE_FOV)
		_save("close_front.png", await _shot(""))
	if _modes.has("compare") and _ch.has("before"):
		var rows: Array = []
		var body_ref: Image = _png(_spec.get("body_ref", ""))
		for row: String in ["face", "close", "body"]:
			for k: String in ["before", "hero"]:
				_only([k], false)
				await process_frame
				var v: Array = _face_view(k) if row != "body" else _body_view(k, 30.0)
				if row == "close":
					v = [v[0], 30.0, 2.0, 0.4, CLOSE_FOV]
				_view(v)
				rows.append(await _shot("S9d" if k == "before" else "M5"))
			rows.append(body_ref if row == "body" else rf2)
		_only(["hero"], false)
		_grid_cells(rows, 3, Vector2i(640, 640), "before_after.png")
	if _modes.has("grid"):
		var variants: Array = _spec.get("variants", [])
		var imgs: Array = [rf2]
		var zooms: Array = []
		var gz: Array = _spec.get("grid_zoom", [0.2, 0.2, 0.8, 0.8])
		if rf2 != null:
			zooms.append(_region(rf2, _spec.get("grid_zoom_target", gz)))
		var fv0: Array = _face_view("hero")
		_view(fv0 if _spec.get("grid_view", "face") == "face" else [fv0[0], 30.0, 2.0, 0.4, CLOSE_FOV])
		var rig: Node = _rig["hero"]
		for v: Dictionary in variants:
			var undo := {}
			_apply(rig.skin_material(), v.get("skin", {}), undo)
			var img: Image = await _shot(v.get("label", ""))
			imgs.append(img)
			zooms.append(_region(img, gz))
			_restore(rig.skin_material(), undo)
		var name: String = _spec.get("grid_name", "tune")
		_sheet(imgs, mini(imgs.size(), 4), "grid_%s.png" % name, 2560)
		_sheet(zooms, mini(zooms.size(), 4), "zoom_%s.png" % name, 1280)
	if _modes.has("room"):
		var rc: Dictionary = _spec.get("room", {})
		var names: Array = ["before", "hero", "coral", "violet"] if _ch.has("before") else ["hero", "coral", "violet"]
		_only(names, true)
		for n: Node in root.get_children():  # the stand back (a "bg" backdrop hides the floor for the face shots)
			if n is WorldEnvironment:
				(n as WorldEnvironment).environment.background_color = Color(0.80, 0.80, 0.82)
			elif n is MeshInstance3D and (n as MeshInstance3D).mesh is PlaneMesh:
				(n as MeshInstance3D).visible = true
		await process_frame
		var dist: float = rc.get("dist", 3.5)
		var eye: float = rc.get("eye", 1.6)
		_camera.fov = rc.get("fov", 70.0)
		_camera.look_at_from_position(Vector3(0.6, eye, dist), Vector3(0, 1.0, 0), Vector3.UP)
		_save("room.png", await _shot(""))
		_only(["hero", "coral", "violet"], true)
		await process_frame
		_camera.fov = 40.0
		_camera.look_at_from_position(Vector3(0.0, 1.5, 2.6), Vector3(0, 1.05, 0), Vector3.UP)
		_save("room_hues.png", await _shot(""))
		_only(["hero"], false)
	if _modes.has("taa"):
		await _taa()
	if _modes.has("clips"):
		await _clips()
	FileAccess.open(_out + "/m5_shots.json", FileAccess.WRITE).store_string(JSON.stringify(_report, " "))
	quit(0)


func _gpu_ms(frames: int) -> float:
	var vp: RID = root.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	var ms: Array = []
	for _i: int in frames:
		await RenderingServer.frame_post_draw
		ms.append(RenderingServer.viewport_get_measured_render_time_gpu(vp))
	ms.sort()
	return ms[ms.size() / 2]


func _taa() -> void:
	var fv: Array = _face_view("hero")
	var shots: Array = []
	var zooms: Array = []
	var res: Dictionary = {}
	var modes := [["msaa2x", Viewport.MSAA_2X, false, Viewport.SCALING_3D_MODE_BILINEAR],
		["taa", Viewport.MSAA_DISABLED, true, Viewport.SCALING_3D_MODE_BILINEAR],
		["msaa2x_taa", Viewport.MSAA_2X, true, Viewport.SCALING_3D_MODE_BILINEAR],
		["fsr2", Viewport.MSAA_DISABLED, false, Viewport.SCALING_3D_MODE_FSR2]]
	for views: Array in [["face", [fv[0], 30.0, 2.0, 0.4, CLOSE_FOV]], ["body", _body_view("hero", 30.0)]]:
		for md: Array in modes:
			root.msaa_3d = md[1]
			root.use_taa = md[2]
			root.scaling_3d_mode = md[3]
			root.scaling_3d_scale = 1.0
			_view(views[1])
			var ms: float = await _gpu_ms(40)
			res["%s_%s" % [views[0], md[0]]] = snappedf(ms, 0.01)
			var img: Image = await _shot("%s %s  GPU %.2f ms" % [views[0], md[0], ms], 12)
			shots.append(img)
			if views[0] == "face":
				zooms.append(_region(img, [0.45, 0.35, 0.75, 0.65]))
	root.msaa_3d = Viewport.MSAA_2X
	root.use_taa = false
	root.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
	_report["gpu_ms"] = res
	print("PROOF gpu_ms ", res)
	_sheet(shots, 4, "taa.png", 2560)
	_sheet(zooms, 4, "taa_zoom.png", 2560)


func _clips() -> void:
	var p: AnimationPlayer = _player["hero"]
	var view: Array = _body_view("hero", 30.0, 0.8)
	_view(view)
	_label.text = ""
	root.use_taa = _spec.get("taa", false)  # look_presets.json High and Ultra (M5)
	for word: String in _spec.get("clips", ["Idle", "Walk"]):
		var c: String = _clip(p, word)
		if c == "":
			_fail("no clip %s" % word)
			return
		var length: float = p.get_animation(c).length
		var n: int = int(round(length * 30.0))
		var dir: String = "%s/clips/%s" % [_out, word]
		DirAccess.make_dir_recursive_absolute(dir)
		p.play(c)
		for i: int in n:
			p.seek(float(i) / 30.0, true)
			p.pause()
			await process_frame
			await process_frame
			await RenderingServer.frame_post_draw
			var img: Image = _cell(root.get_texture().get_image(), CELL)
			img.save_png("%s/%04d.png" % [dir, i])
		_report.get_or_add("clips", {})[word] = {"frames": n, "length": length}
		print("PROOF clip ", word, " frames ", n)
