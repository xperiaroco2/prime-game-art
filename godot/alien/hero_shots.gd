extends "res://alien/second_test.gd"
## Large clean stills of one alien beside its paintover target (art #196, S9), under second_test.gd's stage (the
## showroom's Medium look), teal, eyes bored, mouth frog, no crest, Idle at frame 0:
## - hero_face_34.png (the framing the paintover rf2 was drawn over), hero_body_34.png, hero_body_front.png;
## - beside.png: the face shot and the target (spec "beside", a PNG) side by side, 1280 x 640;
## - grid_<name>.png: the target, then the face shot under each of spec "variants" (a tuning grid, 2 columns of 640):
##   [{"label", "skin": {alien_hue.gdshader uniform: value}, "lip": {alien_lip.gdshader uniform: value},
##   "eye": {alien_eye.gdshader uniform: value}, "hue": [[r, g, b], [r, g, b]] (sRGB hue and pale)}], each applied
##   on top of the defaults and undone after its shot; a variant's "lights" (light_sheet's form, below) replace the
##   stage's directional lights for its shot (the approved lights, look_presets.json, come back after it); spec
##   "grid_zoom" [x0, y0, x1, y1] (fractions of a shot) adds zoom_<name>.png, that part of each shot, the
##   target first (its own part: "grid_zoom_target"), 4 columns of 320 px.
## - light_sheet.png (spec "lights", S9d: the lighting question): per variant [{"label", "lights": [{"at": [x, y, z],
##   "energy", "specular", "shadow"}]}] the stage's directional lights replaced by the variant's (each aimed at
##   (0, 0.9, 0), as the stage's), the face shot and the three-quarter body shot; one sheet with the faces in the top
##   row and the bodies below, then the spec's "beside" and "lights_body_ref" PNGs in the last column; 1600 px wide.
## Spec: {"scenes": {"hero": "res://import/..glb"}, "out": DIR, "hdri": .., "beside": PNG, "bg": [r, g, b] (a plain
## backdrop, no floor, as the paintover's), "face": {"yaw", "dist", "fov", "dy", "z", "pitch"}, "body": {"yaw",
## "fill", "fov"} or false, "variants": [..], "grid_name": ".."}. Run like second_test.gd in a 1536 x 1536 window.


func _bounds(root_node: Node3D) -> AABB:
	var box := AABB()
	var first := true
	for n: Node in root_node.find_children("*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		if not mi.is_visible_in_tree() or mi.mesh == null:
			continue
		var b: AABB = mi.global_transform * mi.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box


func _save(name: String, img: Image) -> void:
	img.convert(Image.FORMAT_RGB8)
	img.save_png(_out + "/" + name)
	print("PROOF saved ", _out + "/" + name)


func _backdrop(c: Array) -> void:
	for n: Node in root.get_children():
		if n is WorldEnvironment:
			(n as WorldEnvironment).environment.background_color = Color(c[0], c[1], c[2])
		elif n is MeshInstance3D and (n as MeshInstance3D).mesh is PlaneMesh:
			(n as MeshInstance3D).visible = false


func _apply(mat: Material, params: Dictionary, undo: Dictionary) -> void:
	var sm := mat as ShaderMaterial
	if sm == null:
		return
	for k: String in params:
		if not undo.has(k):
			undo[k] = sm.get_shader_parameter(k)
		var v: Variant = params[k]
		if v is Array and (v as Array).size() == 3:
			v = Vector3(v[0], v[1], v[2]) if not k in ["accent", "albedo", "iris"] else Color(v[0], v[1], v[2])
		elif v is Array and (v as Array).size() == 2:
			v = Vector2(v[0], v[1])
		sm.set_shader_parameter(k, v)


func _restore(mat: Material, undo: Dictionary) -> void:
	var sm := mat as ShaderMaterial
	if sm == null:
		return
	for k: String in undo:
		sm.set_shader_parameter(k, undo[k])


## A part of a shot: [x0, y0, x1, y1] as fractions of its size.
func _region(img: Image, r: Array) -> Image:
	var w: int = img.get_width()
	var h: int = img.get_height()
	return img.get_region(Rect2i(int(r[0] * w), int(r[1] * h), int((r[2] - r[0]) * w), int((r[3] - r[1]) * h)))


func _set_lights(lights: Array) -> void:
	for n: Node in root.get_children():
		if n is DirectionalLight3D:
			root.remove_child(n)
			n.queue_free()
	for l: Dictionary in lights:
		var at: Array = l["at"]
		var aim: Array = l.get("look_at", [0.0, 0.9, 0.0])
		_light(Vector3(at[0], at[1], at[2]), l["energy"], l.get("specular", 0.0), l.get("shadow", false),
			Vector3(aim[0], aim[1], aim[2]))


func _light_sheet(face_at: Array, body_at: Array, target: Image) -> void:
	var faces: Array = []
	var bodies: Array = []
	_label.add_theme_font_size_override("font_size", 84)  # readable at 320 px a cell
	for v: Dictionary in _spec["lights"]:
		_set_lights(v["lights"])
		_look(face_at[0], face_at[1], face_at[2], face_at[3], face_at[4])
		faces.append(await _shot(v.get("label", "")))
		_look(body_at[0], body_at[1], body_at[2], body_at[3], body_at[4])
		bodies.append(await _shot(v.get("label", "")))
	if target != null:
		faces.append(target)
		var body_ref: Image = Image.load_from_file(_spec.get("lights_body_ref", "")) if _spec.has("lights_body_ref") else null
		if body_ref == null or body_ref.is_empty():
			body_ref = Image.create(16, 16, false, Image.FORMAT_RGB8)
			body_ref.fill(Color(0.1, 0.1, 0.1))
		bodies.append(body_ref)
	_sheet(faces + bodies, faces.size(), "light_sheet.png", 1600)


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
	_combo("hero", "bored", "frog")
	_pose("Idle", 0.0)
	for _i: int in 4:
		await process_frame
	var box: AABB = _bounds(ch)
	var eyes: Vector3 = (_find("hero", "Eye_L") + _find("hero", "Eye_R")) * 0.5
	var mouth: Vector3 = _find("hero", "Mouth")
	print("PROOF bounds ", box, " eyes ", eyes, " mouth ", mouth)
	var fc: Dictionary = _spec.get("face", {})
	var fov: float = fc.get("fov", 30.0)
	var face_mid: Vector3 = (eyes + mouth) * 0.5 + Vector3(0, fc.get("dy", -0.04), -(eyes.z + mouth.z) * 0.5 + fc.get("z", 0.0))
	_look(face_mid, fc.get("yaw", 30.0), fc.get("pitch", 2.0), fc.get("dist", 0.9), fov)
	var face: Image = await _shot("")
	_save("hero_face_34.png", face.duplicate())
	var target: Image = null
	if _spec.has("beside"):
		target = Image.load_from_file(_spec["beside"])
		if target == null or target.is_empty():
			_fail("cannot read %s" % _spec["beside"])
			return
		_sheet([face, target], 2, "beside.png")
	var variants: Array = _spec.get("variants", [])
	if not variants.is_empty():
		var imgs: Array = [target] if target != null else []
		var zooms: Array = []
		if _spec.has("grid_zoom") and target != null:
			zooms.append(_region(target, _spec.get("grid_zoom_target", _spec["grid_zoom"])))
		for v: Dictionary in variants:
			var undo := {"skin": {}, "lip": {}, "eye": {}}
			# the skin material: since M5 the textured one on a kit with the SSS marker (alien.gd SKIN_TEX: SKIN's grain
			# and ao_albedo do nothing there; tune those on an untextured kit or through rig.procedural_material())
			_apply(rig.skin_material(), v.get("skin", {}), undo["skin"])
			_apply(rig.face_material("alien_lip"), v.get("lip", {}), undo["lip"])
			_apply(rig.eye_material("bored"), v.get("eye", {}), undo["eye"])
			if v.has("hue"):
				var h: Array = v["hue"]
				var c := Color(h[0][0], h[0][1], h[0][2]).srgb_to_linear()
				var p := Color(h[1][0], h[1][1], h[1][2]).srgb_to_linear()
				for m: Node in ch.find_children("*", "MeshInstance3D", true, false):
					var om: Material = (m as MeshInstance3D).get_surface_override_material(0)
					if om == rig.skin_material() or om == rig.procedural_material():  # M5: the crests too
						(m as GeometryInstance3D).set_instance_shader_parameter("hue", Vector3(c.r, c.g, c.b))
						(m as GeometryInstance3D).set_instance_shader_parameter("pale", Vector3(p.r, p.g, p.b))
			if v.has("lights"):
				_set_lights(v["lights"])
			imgs.append(await _shot(v.get("label", "")))
			if _spec.has("grid_zoom"):
				zooms.append(_region(imgs[-1], _spec["grid_zoom"]))
			if v.has("lights"):
				_set_lights(LookLights.directional())
			_restore(rig.skin_material(), undo["skin"])
			_restore(rig.face_material("alien_lip"), undo["lip"])
			_restore(rig.eye_material("bored"), undo["eye"])
			rig.set_hue("teal")
		_sheet(imgs, 2, "grid_%s.png" % _spec.get("grid_name", "tune"))
		if not zooms.is_empty():
			_sheet(zooms, mini(zooms.size(), 4), "zoom_%s.png" % _spec.get("grid_name", "tune"), 320 * mini(zooms.size(), 4))
	var bc: Variant = _spec.get("body", {})
	if bc is Dictionary:
		var bfov: float = bc.get("fov", 24.0)
		var h: float = box.size.y
		var mid: Vector3 = Vector3(0, box.position.y + h * 0.5, 0)
		var dist: float = h / (bc.get("fill", 0.85) * 2.0 * tan(deg_to_rad(bfov * 0.5)))
		_look(mid, bc.get("yaw", 30.0), bc.get("pitch", 2.0), dist, bfov)
		_save("hero_body_34.png", await _shot(""))
		_look(mid, 0.0, bc.get("pitch", 2.0), dist, bfov)
		_save("hero_body_front.png", await _shot(""))
		if _spec.has("lights"):
			await _light_sheet([face_mid, fc.get("yaw", 30.0), fc.get("pitch", 2.0), fc.get("dist", 0.9), fov],
				[mid, bc.get("yaw", 30.0), bc.get("pitch", 2.0), dist, bfov], target)
	quit(0)
