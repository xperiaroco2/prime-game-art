extends "res://alien/m21_shots.gd"
## Test D (art #196, brief UPDATE 53): one material. The face's skin darker and greener as the 2D sheets, one coral
## family for the lips, lid domes and tongue, a soft lip gloss and a softer face light with more form, tried as looks
## on today's kit under light D's stage (second_test.gd), in an off-screen window (the runner's _godot.window(),
## 1536 x 1536). Spec as m21_shots.gd's, plus:
## - a look: {"label", "skin": {alien_hue uniform: value}, "mat": {face material key: {uniform: value}},
##   "lights": {look_presets light name: {"energy", "angular", "blur", "specular", "at"}}, "env": {"ambient_energy",
##   "sky", "ssao", "ssao_light", "exposure"}, "diffuse": "wrap" (the shaders' own diffuse_lambert_wrap) | "burley" |
##   "lambert" (the skin, lip and mouth-part shaders recompiled with that diffuse mode)}; every change is undone after
##   its cell; colours of the face materials are sRGB, the skin's vectors linear;
## - "grid": per cell of skins x lights x lips ("td_skins" x "td_lights" x "td_lips", three lists of looks) the pout at rest from the front at 0.4 m and the
##   face 3/4 at 1.2 m: cells/NN_f.png, cells/NN_q.png (640 px), grid_front.png, grid_34.png and grid.json (each cell's
##   labels and the mouth's box in the cell's pixels, for scripts/measure.py);
## - "views": per look of "td_compare" the face front, 3/4 and profile at 0.4 m, 3/4 at 1.2 m and 3.5 m (3x crop), the
##   tongue mouth's A at 0.4 m, then a row of "td_refs" ([path, [x0, y0, x1, y1] shares or [], label]): views.png and
##   views/<look>_<view>.png.

const CELL_PX := 640
const MOUTH_BOX := [0.055, 0.025, 0.04]  # m round the Mouth socket: half width, up, down (the pout 78 mm wide)
const COLOUR_UNIFORMS: Array[String] = ["albedo", "deep", "transmit_color"]
var _lights: Dictionary = {}  # look_presets light name -> DirectionalLight3D
var _variants: Dictionary = {}  # shader path + diffuse mode -> Shader
var _orig_shader: Dictionary = {}  # material -> its own shader


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	await process_frame
	_out = _spec["out"]
	DirAccess.make_dir_recursive_absolute(_out)
	_modes = _spec.get("modes", ["grid"])
	if not (_modes.has("grid") or _modes.has("views")):
		await super._run()
		return
	_stage()
	if _spec.has("bg"):
		_backdrop(_spec["bg"])
	var names: Array = []
	for l: Dictionary in LookLights.directional():
		names.append(l["name"])
	for n: Node in root.get_children():
		if n is DirectionalLight3D and _lights.size() < names.size():
			_lights[names[_lights.size()]] = n
	_order = []
	for kit: Dictionary in _spec["kits"]:
		var k: String = kit["key"]
		if not _add_look(k, kit["res"], kit.get("look", "m6")):
			return
		_keys.append(k)
		_labels[k] = kit.get("label", k)
		_mouth_of[k] = kit.get("mouth", "pout")
		_lashes_of[k] = kit.get("lashes", true)
		_rig[k].set_lashes(_lashes_of[k])
	_pose("Idle", 0.0)
	for _i: int in 4:
		await process_frame
	var hero: String = _keys[-1]
	_only([hero], false)
	if _modes.has("grid"):
		await _td_grid(hero)
	if _modes.has("views"):
		await _td_views(hero)
	quit(0)


func _env() -> Environment:
	for n: Node in root.get_children():
		if n is WorldEnvironment:
			return (n as WorldEnvironment).environment
	return null


func _keep(saved: Array, obj: Object, prop: String) -> void:
	saved.append([obj, "prop", prop, obj.get(prop)])


func _td_param(mat: Material, u: String, v: Variant, saved: Array, face: bool) -> void:
	if mat is ShaderMaterial:
		var sm := mat as ShaderMaterial
		var val: Variant = v
		if v is Array:
			var a: Array = v
			if face and u in COLOUR_UNIFORMS:
				val = Color(a[0], a[1], a[2])
			else:
				val = _val(v)
		saved.append([sm, "param", u, sm.get_shader_parameter(u)])
		sm.set_shader_parameter(u, val)
	elif mat is BaseMaterial3D:
		var bm := mat as BaseMaterial3D
		var prop: String = {"albedo": "albedo_color", "roughness_value": "roughness",
			"specular_value": "metallic_specular"}.get(u, u)
		_keep(saved, bm, prop)
		bm.set(prop, Color(v[0], v[1], v[2]) if v is Array else v)


func _variant(sh: Shader, mode: String) -> Shader:
	var key: String = sh.resource_path + ":" + mode
	if not _variants.has(key):
		var s := Shader.new()
		s.code = sh.code.replace("diffuse_lambert_wrap", "diffuse_" + mode)
		_variants[key] = s
	return _variants[key]


## The skin's, lips', lids', tongue's and mouth parts' shaders with another diffuse mode ("wrap": their own).
func _td_diffuse(k: String, mode: String, saved: Array) -> void:
	var mats: Array = [_rig[k]._tex_material, _rig[k]._material]
	for key: String in _rig[k]._face_materials:
		var m: Variant = _rig[k]._face_materials[key]
		if m is ShaderMaterial and ((m as ShaderMaterial).shader == AlienRig.LIP_SHADER
				or (m as ShaderMaterial).shader == AlienRig.MOUTH_PART_SHADER or _orig_shader.has(m)):
			mats.append(m)
	for m: ShaderMaterial in mats:
		if m == null:
			continue
		var orig: Shader = _orig_shader.get(m, m.shader)
		_orig_shader[m] = orig
		var target: Shader = orig if mode == "wrap" else _variant(orig, mode)
		if m.shader == target:
			continue
		var vals: Dictionary = {}
		for u: Dictionary in m.shader.get_shader_uniform_list():
			vals[u["name"]] = m.get_shader_parameter(u["name"])
		saved.append([m, "shader", vals, m.shader])
		m.shader = target
		for n: String in vals:
			if vals[n] != null:
				m.set_shader_parameter(n, vals[n])


func _td_apply(k: String, look: Dictionary, saved: Array) -> void:
	if look.has("diffuse"):
		_td_diffuse(k, look["diffuse"], saved)
	for u: String in look.get("skin", {}):
		_td_param(_rig[k]._tex_material, u, look["skin"][u], saved, false)
	for key: String in look.get("mat", {}):
		var mat: Material = _rig[k]._face_materials.get(key)
		if mat == null:
			print("PROOF warn: no face material ", key)
			continue
		for u: String in look["mat"][key]:
			_td_param(mat, u, look["mat"][key][u], saved, true)
	for name: String in look.get("lights", {}):
		var l: DirectionalLight3D = _lights.get(name)
		if l == null:
			print("PROOF warn: no light ", name)
			continue
		var d: Dictionary = look["lights"][name]
		for p: String in d:
			if p == "at":
				_keep(saved, l, "global_transform")
				var at: Array = d["at"]
				l.look_at_from_position(Vector3(at[0], at[1], at[2]), Vector3(0, 0.9, 0))
				continue
			var prop: String = {"energy": "light_energy", "angular": "light_angular_distance", "blur": "shadow_blur",
				"specular": "light_specular"}.get(p, p)
			_keep(saved, l, prop)
			l.set(prop, d[p])
	var env: Environment = _env()
	for p: String in look.get("env", {}):
		var prop: String = {"ambient_energy": "ambient_light_energy", "sky": "ambient_light_sky_contribution",
			"ssao": "ssao_intensity", "ssao_light": "ssao_light_affect", "exposure": "tonemap_exposure"}.get(p, p)
		_keep(saved, env, prop)
		env.set(prop, look["env"][p])


func _td_undo(saved: Array) -> void:
	for i: int in range(saved.size() - 1, -1, -1):
		var s: Array = saved[i]
		match s[1]:
			"param":
				(s[0] as ShaderMaterial).set_shader_parameter(s[2], s[3])
			"prop":
				(s[0] as Object).set(s[2], s[3])
			"shader":
				var m: ShaderMaterial = s[0]
				m.shader = s[3]
				for n: String in s[2]:
					if s[2][n] != null:
						m.set_shader_parameter(n, s[2][n])


## The Mouth socket's box (MOUTH_BOX) on screen, in a CELL_PX cell made by _cell from a square shot of side w.
func _mouth_box(k: String, w: int) -> Array:
	var c: Vector3 = _find(k, "Mouth")
	var right: Vector3 = _camera.global_transform.basis.x
	var up: Vector3 = _camera.global_transform.basis.y
	var xs: Array = []
	var ys: Array = []
	for sx: float in [-1.0, 1.0]:
		for sy: float in [MOUTH_BOX[1], -MOUTH_BOX[2]]:
			var p: Vector2 = _camera.unproject_position(c + right * sx * MOUTH_BOX[0] + up * sy)
			xs.append(p.x)
			ys.append(p.y)
	var f: float = float(CELL_PX) / w
	return [int(xs.min() * f), int(ys.min() * f), int(ceil(xs.max() * f)), int(ceil(ys.max() * f))]


func _td_grid(hero: String) -> void:
	DirAccess.make_dir_recursive_absolute(_out + "/cells")
	var fronts: Array = []
	var quarts: Array = []
	var rows: Array = []
	var n: int = 0
	var lips: Array = _spec.get("td_lips", [{"label": "lips"}])
	var lights: Array = _spec.get("td_lights", [{"label": "D"}])
	for s: Dictionary in _spec.get("td_skins", [{"label": "skin"}]):
		for l: Dictionary in lights:
			for p: Dictionary in lips:
				var saved: Array = []
				for look: Dictionary in [s, l, p]:
					_td_apply(hero, look, saved)
				_combo(hero, "bored", _mouth_of[hero])
				_rig[hero].set_lashes(true)
				var label: String = "%s / %s / %s" % [s["label"], l["label"], p["label"]]
				await process_frame
				_mouth_view(hero, 0.0, 2.0, 0.4, 24.0)
				var shot: Image = await _shot(label)
				var fbox: Array = _mouth_box(hero, shot.get_width())
				var f: Image = _cell(shot, Vector2i(CELL_PX, CELL_PX))
				_face_at(hero, 35.0, 1.2)
				shot = await _shot(label)
				var qbox: Array = _mouth_box(hero, shot.get_width())
				var q: Image = _cell(shot, Vector2i(CELL_PX, CELL_PX))
				_save("cells/%02d_f.png" % n, f)
				_save("cells/%02d_q.png" % n, q)
				fronts.append(f)
				quarts.append(q)
				rows.append({"n": n, "skin": s["label"], "light": l["label"], "lip": p["label"], "front_box": fbox,
					"q_box": qbox})
				_td_undo(saved)
				print("PROOF cell %d %s" % [n, label])
				n += 1
	var cols: int = lights.size() * lips.size()
	_grid_cells(fronts, cols, Vector2i(320, 320), "grid_front.png")
	_grid_cells(quarts, cols, Vector2i(320, 320), "grid_34.png")
	var fa := FileAccess.open(_out + "/grid.json", FileAccess.WRITE)
	fa.store_string(JSON.stringify({"cell_px": CELL_PX, "cells": rows}, " "))
	fa.close()


func _far(k: String, yaw: float) -> Image:
	_look(_head_target(k), yaw, 2.0, 3.5, 70.0)
	var img: Image = await _shot("")
	var r: Rect2i = _screen_rect(k, 0.16)
	var crop: Image = img.get_region(r.grow_individual(0, r.size.y / 2, 0, r.size.y))
	crop.resize(crop.get_width() * 3, crop.get_height() * 3, Image.INTERPOLATE_NEAREST)
	return crop


func _face_close(k: String, yaw: float, dist: float, fov: float) -> void:
	var eyes: Vector3 = (_find(k, "Eye_L") + _find(k, "Eye_R")) * 0.5
	var mouth: Vector3 = _find(k, "Mouth")
	_look((eyes + mouth) * 0.5 + Vector3(0, -0.005, 0), yaw, 2.0, dist, fov)


func _td_views(hero: String) -> void:
	DirAccess.make_dir_recursive_absolute(_out + "/views")
	var cells: Array = []
	for look: Dictionary in _spec.get("td_compare", [{"label": "today"}]):
		var saved: Array = []
		_td_apply(hero, look, saved)
		var lab: String = look["label"]
		_combo(hero, "bored", _mouth_of[hero])
		_rig[hero].set_lashes(true)
		await process_frame
		var row: Array = []
		for v: Array in [["front_04", 0.0, 0.4, 42.0], ["34_04", 35.0, 0.4, 42.0], ["profile_04", 90.0, 0.4, 46.0],
				["34_12", 35.0, 1.2, 22.0]]:
			_face_close(hero, v[1], v[2], v[3])
			row.append(await _shot("%s %s" % [lab, v[0]]))
		row.append(await _far(hero, 35.0))
		_combo(hero, "bored", "tongue", "A")
		await process_frame
		_mouth_view(hero, 20.0, 2.0, 0.4, 26.0)
		row.append(await _shot("%s tongue A" % lab))
		_combo(hero, "bored", _mouth_of[hero])
		var names: Array = ["front_04", "34_04", "profile_04", "34_12", "34_35", "tongueA_04"]
		for i: int in row.size():
			var c: Image = _cell(row[i], Vector2i(CELL_PX, CELL_PX))
			_save("views/%s_%s.png" % [lab, names[i]], c)
			cells.append(c)
		_td_undo(saved)
		print("PROOF views ", lab)
	for r: Array in _spec.get("td_refs", []):
		var img: Image = _png(r[0])
		if img == null:
			cells.append(null)
			continue
		var b: Array = r[1]
		if b.size() == 4:
			var w: int = img.get_width()
			var h: int = img.get_height()
			img = img.get_region(Rect2i(int(b[0] * w), int(b[1] * h), int((b[2] - b[0]) * w), int((b[3] - b[1]) * h)))
		cells.append(img)
	_grid_cells(cells, 6, Vector2i(420, 420), "views.png")
