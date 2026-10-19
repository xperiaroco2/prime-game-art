extends "res://alien/hero_shots.gd"
## The eyes' proof (art #196, M4): one alien under second_test.gd's stage (the approved look, light D), teal, mouth
## frog, no crest, Idle at frame 0, per eye design ("bored", "manic"):
## - <design>_face34.png and <design>_front.png at 1.2 m, <design>_close.png at 0.4 m (three-quarter), fov 30;
## - <design>_blink.png: one eye at 0.4 m, fov 16, the lids open, rest, half and closed (the lid shadow, the wet line);
##   <design>_blink_zoom.png: their middles (ZOOM) at full resolution, 1600 px wide;
## - <design>_parallax.png: the eye open from three yaws (PARALLAX_YAWS), S9's painted eye (cornea 0) above M4's;
## - with spec "before" (a folder of an earlier run's PNGs, the same names): cmp_<design>.png, one row per shot
##   (face34, front, close), before | after | the target (spec "rf2"; the close row its part "rf2_eye"
##   [x0, y0, x1, y1], fractions), and blink_<design>.png, before above after;
## - with spec "variants" ([{"label", "eye": {alien_eye.gdshader uniform: value}, "wet": {..}}], each on top of the
##   defaults and undone after its shot): grid_<grid_name>.png, the close eye of both designs per variant.
## Spec: {"scenes": {"hero": "res://import/..glb"}, "out": DIR, "hdri": .., "bg": [r, g, b], "rf2": PNG,
## "rf2_eye": [..], "before": DIR, "eye": {uniform: value}, "variants": [..], "grid_name": "..", "grid_lids": "rest", "grid_yaw": 18}. Run like second_test.gd (through
## _godot.window(), never on a screen) in a 1536 x 1536 window.

const DESIGNS: Array[String] = ["bored", "manic"]
const SHOTS: Array[String] = ["face34", "front", "close"]
const LID_STATES: Array[String] = ["open", "rest", "half", "closed"]
const PARALLAX_YAWS: Array = [-10.0, 18.0, 46.0]  # the blink shot's yaw, and 28 degrees either side
const ZOOM: Array = [0.2, 0.25, 0.8, 0.85]  # the blink shots' middle, at full resolution


func _eye_shot(rig: Node, k: String, design: String, shot: String) -> void:
	var eyes: Vector3 = (_find(k, "Eye_L") + _find(k, "Eye_R")) * 0.5
	var mouth: Vector3 = _find(k, "Mouth")
	var mid: Vector3 = (eyes + mouth) * 0.5
	match shot:
		"face34":
			_look(mid + Vector3(0, 0.02, 0), 30.0, 2.0, 1.2, 30.0)
		"front":
			_look(mid + Vector3(0, 0.02, 0), 0.0, 2.0, 1.2, 30.0)
		"close":
			_look(eyes + Vector3(0, -0.01, 0), 30.0, 2.0, 0.4, 30.0)
		_:  # blink: the character's left eye (the viewer's right), a little from its side
			_look(_find(k, "Eye_L"), 18.0, 3.0, 0.4, 16.0)


func _variant(rig: Node, v: Dictionary, undo: Dictionary) -> void:
	for d: String in DESIGNS:
		undo[d] = {}
		_apply(rig.eye_material(d), v.get("eye", {}), undo[d])
	undo["wet"] = {}
	_apply(rig.face_material("alien_wet"), v.get("wet", {}), undo["wet"])


func _unvariant(rig: Node, undo: Dictionary) -> void:
	for d: String in DESIGNS:
		_restore(rig.eye_material(d), undo[d])
	_restore(rig.face_material("alien_wet"), undo["wet"])


func _load(path: String) -> Image:
	if path == "" or not FileAccess.file_exists(path):
		return null
	var img: Image = Image.load_from_file(path)
	return null if img == null or img.is_empty() else img


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_stage()
	if _spec.has("bg"):
		_backdrop(_spec["bg"])
	var packed: PackedScene = load(_spec["scenes"]["hero"]) as PackedScene
	if packed == null:
		_fail("cannot load the hero scene")
		return
	var ch: Node3D = packed.instantiate()
	root.add_child(ch)
	var rig: Node = AlienRig.new()
	ch.add_child(rig)
	rig.setup(ch)
	rig.auto_blink = false
	rig.set_crest("")
	rig.set_hue("teal")
	_ch["hero"] = ch
	_rig["hero"] = rig
	_player["hero"] = ch.find_child("AnimationPlayer", true, false)
	_pose("Idle", 0.0)
	for d: String in DESIGNS:  # spec "eye": uniforms on both designs for the whole run ({"cornea": 0}: S9's eye)
		_apply(rig.eye_material(d), _spec.get("eye", {}), {})
	var rf2: Image = _load(_spec.get("rf2", ""))
	var rf2_eye: Image = _region(rf2, _spec.get("rf2_eye", [0.18, 0.36, 0.66, 0.6])) if rf2 != null else null
	var before: String = _spec.get("before", "")
	for d: String in DESIGNS:
		_combo("hero", d, "frog")
		for _i: int in 4:
			await process_frame
		var rows: Array = []
		for s: String in SHOTS:
			_eye_shot(rig, "hero", d, s)
			var img: Image = await _shot("")
			_save("%s_%s.png" % [d, s], img.duplicate())
			var b: Image = _load(before + "/%s_%s.png" % [d, s]) if before != "" else null
			if b != null:
				var t: Image = rf2_eye if s == "close" else rf2
				rows.append_array([b, img, t if t != null else img])
		if not rows.is_empty():
			_sheet(rows, 3, "cmp_%s.png" % d)
		var strip: Array = []
		var zooms: Array = []
		for st: String in LID_STATES:
			rig.set_lids(st)
			_eye_shot(rig, "hero", d, "blink")
			strip.append(await _shot(""))
			zooms.append(_region(strip[-1], ZOOM))
		rig.set_lids("rest")
		_sheet(strip, 4, "%s_blink.png" % d)
		_sheet(zooms, 4, "%s_blink_zoom.png" % d, 1600)
		# the parallax: the eye open, the view turned; S9's painted eye (cornea 0) above the M4 eye
		var turns: Array = []
		rig.set_lids("open")
		var em: ShaderMaterial = rig.eye_material(d)
		for cv: float in [0.0, 1.0]:
			em.set_shader_parameter("cornea", cv)
			for yaw: float in PARALLAX_YAWS:
				_look(_find("hero", "Eye_L"), yaw, 3.0, 0.4, 16.0)
				turns.append(_region(await _shot(""), ZOOM))
		em.set_shader_parameter("cornea", 1.0)
		rig.set_lids("rest")
		_sheet(turns, PARALLAX_YAWS.size(), "%s_parallax.png" % d, 1600)
		var bb: Image = _load(before + "/%s_blink.png" % d) if before != "" else null
		if bb != null:
			_sheet([bb, _load(_out + "/%s_blink.png" % d)], 1, "blink_%s.png" % d)
	var variants: Array = _spec.get("variants", [])
	if not variants.is_empty():
		var imgs: Array = []
		for d: String in DESIGNS:
			_combo("hero", d, "frog")
			rig.set_lids(_spec.get("grid_lids", "rest"))
			for v: Dictionary in variants:
				var undo := {}
				_variant(rig, v, undo)
				_look(_find("hero", "Eye_L"), _spec.get("grid_yaw", 18.0), 3.0, 0.4, 16.0)
				imgs.append(await _shot(v.get("label", "")))
				_unvariant(rig, undo)
		_sheet(imgs, variants.size(), "grid_%s.png" % _spec.get("grid_name", "tune"), mini(1600, 400 * variants.size()))
	quit(0)
