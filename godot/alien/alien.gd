extends Node
## The alien parts kit's character controller (art #196, S3). Add it as a child of an instanced alien_character.glb
## (tools/blender/alien_assemble.py: every variant a named node under the Head joint's sockets) and call setup().
## It swaps the hue material for alien_hue.gdshader, and then:
## - set_eyes("bored"|"manic"), set_mouth_design("frog"|"overbite"), set_crest(""|"antennae"|"fins"), set_hue(name);
## - blinks by lid rotation (the lid node's local X, the angles of parts.json): BLINK_MS close, hold, open, every 2-6 s
##   at random; the lids rest at "rest" (the default: bored's heavy lids; "open" only for surprise, set_lids("open"));
## - talks: listen(bus) reads an AudioEffectSpectrumAnalyzer on that bus and every 60-80 ms shows one of the six mouth
##   pieces, snapped: the loudness (against a decaying peak) picks closed, small or wide; among the wide ones the
##   low/high band ratio (150-1000 against 1000-4000 Hz) picks O when high, and a second ratio (1800-4000 against
##   1000-1800 Hz, F2 above or below 1800) picks E, else A. One ratio could not tell A from E: A's F2 (about 1150 Hz)
##   lies in the high band, so A has the lowest low/high ratio of the three (measured in S3: A 1.8, E 3.5, O 6.3 on
##   the test WAV, as the harmonic model predicts). A closed pick just after speech shows M. talk_log holds every pick.
## - the face materials (S5, set_face_look): "s5" (the default) puts the stage-1 human faces' eye and lip look on the
##   imported face materials by name: alien_eye.gdshader on the eyeballs (alien_eye_<design>: a warm off-white, soft warm
##   shading toward the corners and under the lids, a dark iris and pupil, one soft catch light), matte warm lips, a
##   dark warm mouth cup, ivory teeth, and the lid shells in the lips' material (the eye sheets eb1 and em1: coral
##   skin domes the colour of the lips); "first" keeps the first test's imported materials (for before/after sheets).
## - set_mouth_mode("3d"|"flip"): the replacement pieces or the flipbook test's face shells (S6); since S6 the overbite
##   pieces hold their own teeth.
## Used through preload (a -s script has no global class cache): const AlienRig = preload("res://alien/alien.gd").

const SHADER: Shader = preload("res://alien/alien_hue.gdshader")
## The hue materials the shader replaces: the skin, and since M3a (art #196) the crest parts' own untextured copy
## (the skin's material carries the texture set on Body's UV, which the crest parts do not share).
const HUE_MATERIALS := ["alien_hue", "alien_hue_part"]
const EYE_SHADER: Shader = preload("res://alien/alien_eye.gdshader")
const LIP_SHADER: Shader = preload("res://alien/alien_lip.gdshader")
const LIP := Color(0.82, 0.44, 0.37)  # sRGB: S9, rf2's warmer coral (S5: e2's dusty salmon (0.76, 0.45, 0.40)) (the first test: a glossy (0.86, 0.42, 0.36))
const FACE := {  # sRGB colour, roughness, specular: the stage-1 face kit's (faces/clay_kit.json: lip tint on the skin,
	# cavity (0.05, 0.012, 0.02) and teeth (0.92, 0.9, 0.8) linear, teeth roughness 0.28), soft-matte for the alien
	"alien_lip": [LIP, 0.6, 0.3],
	"alien_mouth_inner": [Color(0.25, 0.11, 0.14), 0.9, 0.08],
	"alien_teeth": [Color(0.96, 0.95, 0.90), 0.4, 0.3],
}
## S9, the release look (the paintover rf2): alien_hue.gdshader's gradient, baked AO, grain, subsurface and rim, and
## alien_lip.gdshader's sheen and grain on the lips and lid domes. Tuned by grids against rf2 (hero_shots.gd).
const SKIN := {
	"deep_top": 0.6, "deep_back": 1.0, "face_warm": 0.6, "ao_albedo": 0.5, "ao_light": 1.0, "grain": 0.12, "sss": 0.3,
	"rim_glow": 0.3,
	"rim_value": 0.6, "rim_tint": 0.3,  # light D's tuning grid (2026-10-19): Godot's rim, a lighter edge as rf2's (was 0.2, 0.6)
}
const LIP_LOOK := {"sheen": 0.08, "sheen_roughness": 0.7, "grain": 0.05}
const EYE_LOOK := {  # alien_eye.gdshader's per-design uniforms (angles from the pupil axis, degrees; colours sRGB)
	"bored": {"iris_deg": 25.0, "pupil_deg": 11.5, "iris": Color(0.20, 0.12, 0.08), "catch_at_deg": Vector2(6.0, -2.0),
		"catch_deg": 2.5, "catch_soft_deg": 0.4, "catch_energy": 2.2},  # S9: below the rest lid's edge, crisp (rf2)
	"manic": {"iris_deg": 0.0, "pupil_deg": 12.0, "iris": Color(0.05, 0.04, 0.05), "catch_at_deg": Vector2(4.5, 4.5)},
}
## The eyeballs' rest look: each ball turned inward about its socket's up axis (set absolutely, so a GLB whose balls
## already carry it is unchanged): the sockets' 8 degrees outward (S2a's sphere fit) undone, plus 3.5 toward each
## other (the eyes, 15 cm apart, look at a point about 1.2 m ahead). Without it the pupils diverged (S5's grid).
var aim_in_deg: float = 11.5
const HUES := {  # sRGB: the base hue and its light tint (face, throat, belly)
	"teal": [Color(0.11, 0.48, 0.51), Color(0.86, 0.92, 0.81)],  # S9: rf2 (S3: (0.17, 0.56, 0.55), (0.80, 0.91, 0.80))
	"coral": [Color(0.90, 0.42, 0.34), Color(0.98, 0.84, 0.74)],
	"violet": [Color(0.58, 0.46, 0.82), Color(0.87, 0.83, 0.96)],
}
const LIDS := {  # lid_rot_x_deg of parts.json (S2a): the lid node's local X rotation per state
	"bored": {"upper": {"open": -30.0, "rest": -6.0, "half": 2.0, "closed": 12.0},
		"lower": {"open": 40.0, "rest": 30.0, "half": 20.0, "closed": 6.0}},
	"manic": {"upper": {"open": -58.0, "rest": -50.0, "half": -18.0, "closed": 12.0},
		"lower": {"open": 55.0, "rest": 50.0, "half": 28.0, "closed": 6.0}},
}
const VISEMES: Array[String] = ["rest", "M", "small", "A", "E", "O"]
const BLINK_MS := {"close": 60.0, "hold": 40.0, "open": 100.0}
const BLINK_EVERY_S := Vector2(2.0, 6.0)
const SWITCH_MS := Vector2(60.0, 80.0)
const BAND_LOW := Vector2(150.0, 1000.0)  # Hz
const BAND_HIGH := Vector2(1000.0, 4000.0)
const CLOSED_BELOW := 0.10  # loudness against the decaying peak
const SMALL_BELOW := 0.40
const BAND_F2_LOW := Vector2(1000.0, 1800.0)
const BAND_F2_HIGH := Vector2(1800.0, 4000.0)
const RATIO_O := 4.8  # low/high above this: O (test WAV: O 6.3, E 3.5, A 1.8)
const RATIO_E := 1.0  # F2 high/low above this: E (harmonic model: E 9.4, O 0.09, A 0.04)
const PEAK_DECAY := 0.997  # per pick
const M_AFTER_MS := 160.0  # a closed pick this soon after an open one shows M

var character: Node3D
var eyes: String = "bored"
var mouth_design: String = "frog"
var crest: String = ""
var lid_state: String = "rest"
var auto_blink: bool = true
var talk_log: Array = []  # {t_ms, low, high, level, ratio, f2, piece}
var mouth_piece: String = "rest"
var mouth_mode: String = "3d"

var _material: ShaderMaterial
var _hue_meshes: Array[GeometryInstance3D] = []
var face_look: String = "s5"
var _lid_material: Material
var _face_surfaces: Array = []  # [MeshInstance3D, surface, imported material name]
var _lid_surfaces: Array = []  # [MeshInstance3D, surface]
var _face_materials: Dictionary = {}  # imported name -> the S5 material
var _rng := RandomNumberGenerator.new()
var _blink_t: float = -1.0  # ms into the current blink, -1 when not blinking
var _next_blink_s: float = 3.0
var _analyzer: AudioEffectSpectrumAnalyzerInstance
var _next_switch_ms: float = 0.0
var _peak: float = 1e-4
var _last_open_ms: float = -1e9
var _listen_t0: int = 0


func setup(root: Node3D, seed: int = 196) -> void:
	character = root
	_rng.seed = seed
	_material = ShaderMaterial.new()
	_material.shader = SHADER
	for k: String in SKIN:
		_material.set_shader_parameter(k, SKIN[k])
	for mi: Node in root.find_children("*", "MeshInstance3D", true, false):
		var m: MeshInstance3D = mi
		var uses: bool = false
		for s: int in m.mesh.get_surface_count():
			var mat: Material = m.mesh.surface_get_material(s)
			if mat != null and HUE_MATERIALS.has(mat.resource_name):
				m.set_surface_override_material(s, _material)
				uses = true
				if m.name.contains("_lid_"):
					_lid_surfaces.append([m, s])
			elif mat != null and (FACE.has(mat.resource_name) or mat.resource_name.begins_with("alien_eye_")):
				_face_surfaces.append([m, s, mat.resource_name])
		if uses:
			_hue_meshes.append(m)
	_make_face_materials()
	set_face_look(face_look)
	set_hue("teal")
	set_eyes(eyes)
	set_mouth_design(mouth_design)
	set_crest(crest)
	_next_blink_s = _rng.randf_range(BLINK_EVERY_S.x, BLINK_EVERY_S.y)


func _make_face_materials() -> void:
	for name: String in FACE:
		var f: Array = FACE[name]
		if name == "alien_lip":  # S9: the lips and lid domes take the sheen and grain shader
			var lm := ShaderMaterial.new()
			lm.shader = LIP_SHADER
			lm.resource_name = name
			lm.set_shader_parameter("albedo", f[0])
			lm.set_shader_parameter("roughness_value", f[1])
			lm.set_shader_parameter("specular_value", f[2])
			for k: String in LIP_LOOK:
				lm.set_shader_parameter(k, LIP_LOOK[k])
			_face_materials[name] = lm
			continue
		var m := StandardMaterial3D.new()
		m.resource_name = name
		m.albedo_color = f[0]
		m.roughness = f[1]
		m.metallic_specular = f[2]
		m.diffuse_mode = BaseMaterial3D.DIFFUSE_LAMBERT_WRAP
		m.cull_mode = BaseMaterial3D.CULL_DISABLED  # as the imported (double-sided) ones: culled, the inner cup vanished
		_face_materials[name] = m
	_lid_material = _face_materials["alien_lip"]  # the eye sheets (eb1, em1): the lids are soft domes in the lips' colour
	for design: String in EYE_LOOK:
		var e := ShaderMaterial.new()
		e.shader = EYE_SHADER
		e.resource_name = "alien_eye_" + design
		for k: String in EYE_LOOK[design]:
			e.set_shader_parameter(k, EYE_LOOK[design][k])
		_face_materials["alien_eye_" + design] = e


## "s5": the new face materials; "first": the first test's imported ones.
func set_face_look(look: String) -> void:
	face_look = look
	for fs: Array in _face_surfaces:
		var m: MeshInstance3D = fs[0]
		m.set_surface_override_material(fs[1], _face_materials[fs[2]] if look == "s5" else null)
	for ls: Array in _lid_surfaces:
		var m: MeshInstance3D = ls[0]
		m.set_surface_override_material(ls[1], _lid_material if look == "s5" else _material)
	set_lids(lid_state)  # the balls' rest look and the eye shader's lid edges


## The hue (skin) material shared by the body, head and crests (for tuning grids).
func skin_material() -> ShaderMaterial:
	return _material


## The S5 eye material of a design (for tuning grids).
func eye_material(design: String) -> ShaderMaterial:
	return _face_materials["alien_eye_" + design]


## For the proofs: the face materials swapped in (imported name -> material) and the counts of the face and lid
## surfaces they were swapped on.
func face_material(imported_name: String) -> Material:
	return _face_materials.get(imported_name)


func face_surface_counts() -> Dictionary:
	return {"face": _face_surfaces.size(), "lid": _lid_surfaces.size()}


func node(name: String) -> Node3D:
	return character.find_child(name, true, false) as Node3D


func set_hue(name: String) -> void:
	var c: Color = (HUES[name][0] as Color).srgb_to_linear()
	var p: Color = (HUES[name][1] as Color).srgb_to_linear()
	for m: GeometryInstance3D in _hue_meshes:
		m.set_instance_shader_parameter("hue", Vector3(c.r, c.g, c.b))
		m.set_instance_shader_parameter("pale", Vector3(p.r, p.g, p.b))


func set_eyes(design: String) -> void:
	eyes = design
	for d: String in LIDS:
		for side: String in ["L", "R"]:
			node("eye_%s_%s" % [d, side]).visible = d == design
	set_lids(lid_state)


func set_lids(state: String) -> void:
	lid_state = state
	_apply_lids(LIDS[eyes]["upper"][state], LIDS[eyes]["lower"][state])


func _apply_lids(upper_deg: float, lower_deg: float) -> void:
	for side: String in ["L", "R"]:
		node("eye_%s_lid_upper_%s" % [eyes, side]).rotation = Vector3(deg_to_rad(upper_deg), 0, 0)
		node("eye_%s_lid_lower_%s" % [eyes, side]).rotation = Vector3(deg_to_rad(lower_deg), 0, 0)
		var ball := node("eye_%s_ball_%s" % [eyes, side]) as GeometryInstance3D
		if ball != null:  # the eye shader's lid shadow follows the lid edges (edge = -rotation)
			ball.set_instance_shader_parameter("upper_edge_deg", -upper_deg)
			ball.set_instance_shader_parameter("lower_edge_deg", -lower_deg)
			var aim: float = aim_in_deg if face_look == "s5" else 0.0  # the first test: unturned
			ball.rotation = Vector3(0, deg_to_rad(-aim if side == "L" else aim), 0)


## The lids at t ms into a blink (0 = the lid state, BLINK_MS close, hold, open): returns false once it is over.
func blink_at(t_ms: float) -> bool:
	var close: float = BLINK_MS["close"]
	var hold: float = BLINK_MS["hold"]
	var open: float = BLINK_MS["open"]
	var k: float
	if t_ms < close:
		k = t_ms / close
	elif t_ms < close + hold:
		k = 1.0
	elif t_ms < close + hold + open:
		k = 1.0 - (t_ms - close - hold) / open
	else:
		set_lids(lid_state)
		return false
	k = k * k * (3.0 - 2.0 * k)
	var u: Dictionary = LIDS[eyes]["upper"]
	var l: Dictionary = LIDS[eyes]["lower"]
	_apply_lids(lerpf(u[lid_state], u["closed"], k), lerpf(l[lid_state], l["closed"], k))
	return true


func set_mouth_design(design: String) -> void:
	mouth_design = design
	show_mouth(mouth_piece)


## "3d": the replacement pieces (mouth_<design>_<shape>); "flip": the flipbook test (S6), one face shell per shape
## (mouthflip_<design>_<shape>) on the design's atlas. A GLB without flip shells keeps "3d".
func set_mouth_mode(mode: String) -> void:
	mouth_mode = mode
	show_mouth(mouth_piece)


func show_mouth(piece: String) -> void:
	mouth_piece = piece
	for d: String in ["frog", "overbite"]:
		for v: String in VISEMES:
			node("mouth_%s_%s" % [d, v]).visible = mouth_mode == "3d" and d == mouth_design and v == piece
			var f: Node3D = node("mouthflip_%s_%s" % [d, v])
			if f != null:
				f.visible = mouth_mode == "flip" and d == mouth_design and v == piece
	var teeth: Node3D = node("mouth_overbite_teeth")  # S3's separate teeth; since S6 each overbite piece has its own
	if teeth != null:
		teeth.visible = mouth_mode == "3d" and mouth_design == "overbite"


func set_crest(name: String) -> void:
	crest = name
	for c: String in ["antennae", "fins"]:
		node("crest_%s" % c).visible = c == name


func listen(bus: String) -> void:
	var idx: int = AudioServer.get_bus_index(bus)
	if idx < 0 or AudioServer.get_bus_effect_count(idx) == 0:
		push_error("alien: no bus '%s' with a spectrum analyzer; the mouth stays at rest" % bus)
		_analyzer = null
		return
	_analyzer = AudioServer.get_bus_effect_instance(idx, 0) as AudioEffectSpectrumAnalyzerInstance
	_listen_t0 = Time.get_ticks_msec()
	_next_switch_ms = 0.0
	_peak = 1e-4
	talk_log.clear()


func stop_listening() -> void:
	_analyzer = null
	show_mouth("rest")


## One mouth pick from the analyzer now (also called by _process every 60-80 ms while listening).
func pick_mouth() -> String:
	var t: float = float(Time.get_ticks_msec() - _listen_t0)
	var low: float = _analyzer.get_magnitude_for_frequency_range(BAND_LOW.x, BAND_LOW.y).length()
	var high: float = _analyzer.get_magnitude_for_frequency_range(BAND_HIGH.x, BAND_HIGH.y).length()
	var m: float = low + high
	_peak = maxf(_peak * PEAK_DECAY, m)
	var level: float = m / _peak
	var ratio: float = low / maxf(high, 1e-6)
	var f2: float = _analyzer.get_magnitude_for_frequency_range(BAND_F2_HIGH.x, BAND_F2_HIGH.y).length() / maxf(
		_analyzer.get_magnitude_for_frequency_range(BAND_F2_LOW.x, BAND_F2_LOW.y).length(), 1e-6)
	var piece: String
	if level < CLOSED_BELOW:
		piece = "M" if t - _last_open_ms < M_AFTER_MS else "rest"
	elif level < SMALL_BELOW:
		piece = "small"
	elif ratio > RATIO_O:
		piece = "O"
	elif f2 > RATIO_E:
		piece = "E"
	else:
		piece = "A"
	if piece != "rest" and piece != "M":
		_last_open_ms = t
	show_mouth(piece)
	talk_log.append({"t_ms": int(t), "low": snappedf(low, 1e-5), "high": snappedf(high, 1e-5),
		"level": snappedf(level, 0.001), "ratio": snappedf(ratio, 0.01), "f2": snappedf(f2, 0.01), "piece": piece})
	return piece


func _process(delta: float) -> void:
	if character == null:
		return
	if _analyzer != null:
		var t: float = float(Time.get_ticks_msec() - _listen_t0)
		if t >= _next_switch_ms:
			pick_mouth()
			_next_switch_ms = t + _rng.randf_range(SWITCH_MS.x, SWITCH_MS.y)
	if not auto_blink:
		return
	if _blink_t >= 0.0:
		_blink_t += delta * 1000.0
		if not blink_at(_blink_t):
			_blink_t = -1.0
			_next_blink_s = _rng.randf_range(BLINK_EVERY_S.x, BLINK_EVERY_S.y)
	else:
		_next_blink_s -= delta
		if _next_blink_s <= 0.0:
			_blink_t = 0.0
