extends Node
## The alien parts kit's character controller (art #196, S3). Add it as a child of an instanced alien_character.glb
## (tools/blender/alien_assemble.py: every variant a named node under the Head joint's sockets) and call setup().
## It swaps the hue material for alien_hue.gdshader, and then:
## - set_eyes("bored"|"manic"), set_mouth_design("frog"|"overbite"|"pout"|"fangs"), set_crest(""|"antennae"|"fins"), set_hue(name);
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
## - M4, the modern eyes (art #196): alien_eye.gdshader draws a cornea (refraction, iris depth, a view-space catch
##   light), the lids' contact shadow and the white's falloff per pixel; each lid's wet line (the strip
##   eye_<design>_wet_<lid>_<side>, material alien_wet, from tools/blender/alien_eyes.py) takes alien_wet.gdshader, casts
##   no shadow and fades out as the lids close (instance uniform `open`, set with the lids).
## - set_mouth_mode("3d"|"flip"): the replacement pieces or the flipbook test's face shells (S6); since S6 the overbite
##   pieces hold their own teeth.
## - M6, the lips and lid domes in the skin's surface quality (lip_look, LIP_LOOK, LID_LOOK) and the textured skin's
##   contact shade (SKIN_CONTACT), each only on a kit that carries its marker (PART_AO_MARKER, CONTACT_MARKER): an older
##   kit keeps its look.
## - M12, the red pout mouth (mp1): a third mouth design "pout" on a kit that has its pieces (mouth_pout_<shape>,
##   material alien_lip_pout: LIP_LOOK_POUT, glossy deep red), its skin contact in CUSTOM2.x (contact_pick2), and a
##   talk style of its own: talk_at(t_ms, line) shows a phase line's piece at t through the design's style
##   (alien_talk.gd: lag, merged flickers, a lower-lip bounce and a pucker between words, as the lip shader's
##   instance uniforms lip_drop and pucker on the shown piece); play_line(line) drives it in time.
## - M13, the fangs mouth (mg2): a fourth design "fangs" (mouth_fangs_<shape>: the coral alien_lip lips, two lower fangs
##   in alien_fang, FANG_LOOK), its contact in CUSTOM2.y, a heavier jaw's talk (alien_talk.gd: a slower opening, a
##   forward jaw thrust on A and E, a small bounce). The talking designs' lips, fangs, cup and tongue move together on
##   the jaw weight COLOR_0.a (M13b; alien_mouth_motion.gdshaderinc; the bounce presses a closed mouth shut, never sags it).
## Used through preload (a -s script has no global class cache): const AlienRig = preload("res://alien/alien.gd").

const SHADER: Shader = preload("res://alien/alien_hue.gdshader")
const AlienTalk = preload("res://alien/alien_talk.gd")
## The hue materials the shader replaces: the skin, and since M3a (art #196) the crest parts' own copy with no image
## at all, not even M2's normal map (the skin's material carries the texture set on Body's UV, which the crest parts
## do not share; alien_texture.py's export stage fails if any material but the skin and the flipbook mouths has one).
const HUE_MATERIALS := ["alien_hue", "alien_hue_part"]
const EYE_SHADER: Shader = preload("res://alien/alien_eye.gdshader")
const LIP_SHADER: Shader = preload("res://alien/alien_lip.gdshader")
const WET_SHADER: Shader = preload("res://alien/alien_wet.gdshader")
## M13: the inner cup and tongue of a talking design's pieces, moving with the lips (alien_mouth_motion.gdshaderinc).
const MOUTH_PART_SHADER: Shader = preload("res://alien/alien_mouth_part.gdshader")
const WET_OPEN_DEG := Vector2(6.0, 16.0)  # M4: the wet lines fade out as the gap between the lid edges closes (degrees)
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
## M5 (art #196): the textured skin's own uniforms (alien_hue.gdshader `textured`), on top of SKIN, for a mesh whose
## imported hue material carries the SSS marker (SSS_MARKER: M5's kit, tools/blender/alien_eyes.py --sss-orm; the
## albedo, the ORM with the subsurface mask in B, M2's normal map). A kit without the marker (M3a, M3c, M4) keeps the
## procedural skin, its look before M5. Tuned on grids under light D against rf2 (m5_shots.gd); SKIN's grain and
## ao_albedo do not apply to it. Chosen on M5's grids g1, g2 (rf2 first): the texture's teal washed out to a light
## cyan under AgX (sat 1.45 and the hue parts' value 0.72 bring rf2's deeper teal; the pale's sat 1.3 its mint); the
## screen-space SSS at SKIN's 0.3 and the fresnel glow made a waxy, hazy skin with no form, so the SSS is 0.08 plus
## 0.4 on the mask's thin parts and the glow is off (0; a white line along the jaw's and neck's contour at 0.4 m),
## with Godot's rim at 0.35; specular 0.5 and the roughness 0.08 lower give rf2's soft sheen on the dome; the normal
## map at 0.7 (M2's neck rings and brow grooves read less; the sculpt's own fix is later), and on the pale only 0.35
## of that (g3, the face from 0.4 m: the creases under the mouth and on the throat read as wrinkles).
const SKIN_TEX := {
	"textured": true, "normal_depth": 0.7, "normal_pale": 0.35, "tex_sat": 1.45, "tex_pale_sat": 1.3,
	"tex_value": 0.72, "roughness_add": -0.08, "specular_value": 0.5, "sss": 0.08, "sss_thin": 0.4, "transmit": 0.3,
	"rim_value": 0.35, "rim_glow": 0.0,
}
## M5: the SKIN_TEX keys the procedural skin (the crests' alien_hue_part, untextured) also takes when the kit is
## textured, so a crest matches the head it sits on: the teal's saturation and value, the specular, the rim and glow,
## and the dome's SSS (the mask is about 0 where the crests stand).
const SKIN_TEX_SHARED := ["tex_sat", "tex_pale_sat", "tex_value", "specular_value", "sss", "rim_value", "rim_glow"]
const SSS_MARKER := {"prime_sss": "orm_b"}  # the imported material's glTF extras (tools/blender/alien_eyes_geom.py)
## S9 to M5's lip and lid look (lip_look "m5", for before/after sheets).
const LIP_LOOK_M5 := {"albedo": LIP, "roughness_value": 0.6, "specular_value": 0.3, "sheen": 0.08,
	"sheen_roughness": 0.7, "grain": 0.05}
## M6 (art #196): the lips and lid domes in the skin's surface quality (alien_lip.gdshader's M6 terms; the engineer:
## they looked like parts "from another universe"): rf2's deeper, warmer coral, deeper still in the folds and where a
## part meets the skin (the part's baked AO, tools/blender/alien_m6.py), lighter on the rolls; a soft colour drift; the
## skin's subsurface, transmittance and rim; a satin roughness near the skin's (M3c 0.66 - 0.08) with a soft sheen
## on the lips; the grain finer. Chosen on M6's grids beside rf2 (m6_shots.gd).
const LIP_LOOK := {"albedo": Color(0.78, 0.35, 0.31), "deep": Color(0.56, 0.18, 0.17), "ao_mix": 1.0,
	"ao_range": Vector2(0.45, 0.95), "ao_occl": 0.5, "drift": 0.06, "roughness_value": 0.55, "specular_value": 0.4,
	"sheen": 0.06, "sheen_roughness": 0.5, "grain": 0.08, "grain_freq": 600.0, "sss": 0.25, "transmit": 0.2,
	"rim_value": 0.35, "rim_tint": 0.5}
## M6: the lid domes' own values over LIP_LOOK (a satin dome as the skin's, no clear coat: its sheen read plastic;
## the lips keep a soft sheen).
const LID_LOOK := {"roughness_value": 0.64, "sheen": 0.0}
## M12: the pout mouth's lips (material alien_lip_pout) over LIP_LOOK: the mp1 sheet's glossy deep red-coral, a deeper
## red in the folds, a low roughness with a clear, crisp coat (the wet highlight on the lower lip), less drift and
## grain (a smooth gloss). Chosen beside the sheet on M12's grid (m12_shots.gd).
const LIP_LOOK_POUT := {"albedo": Color(0.72, 0.18, 0.18), "deep": Color(0.42, 0.05, 0.07), "roughness_value": 0.30,
	"specular_value": 0.55, "sheen": 0.55, "sheen_roughness": 0.12, "drift": 0.03, "grain": 0.03}
## M13: the fangs mouth's two lower fangs (material alien_fang, the lips' shader so they move with the lower jaw):
## ivory, a soft satin with a little clear coat, deeper and warmer at the root (the baked AO), a faint warm
## transmittance. The lips are the kit's coral alien_lip (LIP_LOOK). Chosen beside the mg2 sheet on M13's grids.
## M13b (UPDATE 22: soft ivory shading, a hint of translucency at the tip): a creamier ivory, a warmer and deeper root
## over a wider AO range, more AO occlusion, and a warm SSS and transmittance through the thin tip.
const FANG_LOOK := {"albedo": Color(0.88, 0.80, 0.62), "deep": Color(0.60, 0.46, 0.30), "ao_mix": 1.0,
	"ao_range": Vector2(0.40, 0.98), "ao_occl": 0.6, "drift": 0.02, "roughness_value": 0.45, "specular_value": 0.40,
	"sheen": 0.25, "sheen_roughness": 0.3, "grain": 0.02, "sss": 0.35, "transmit": 0.40,
	"transmit_color": Color(1.0, 0.80, 0.56), "transmit_depth": 0.006, "rim_value": 0.2}
## M14: the tongue mouth's tongue (material alien_tongue_pink, the lips' shader so it moves with the lower jaw and
## flops, `flop_mask`): the mt2 sheet's soft pink, a deeper rose in the groove and at the root (the baked AO), a soft
## wet sheen, a little warm SSS. Its teeth are alien_tooth (FANG_LOOK's ivory with TOOTH_LOOK: the sheet's cream),
## its lips alien_lip (LIP_LOOK).
const TONGUE_LOOK := {"albedo": Color(0.86, 0.38, 0.47), "deep": Color(0.58, 0.16, 0.27), "ao_mix": 1.0,
	"ao_range": Vector2(0.40, 0.95), "ao_occl": 0.5, "drift": 0.03, "roughness_value": 0.38, "specular_value": 0.45,
	"sheen": 0.25, "sheen_roughness": 0.25, "grain": 0.02, "sss": 0.15, "rim_value": 0.10, "flop_mask": 1.0}
const TOOTH_LOOK := {"albedo": Color(0.92, 0.86, 0.68), "deep": Color(0.62, 0.52, 0.36), "transmit": 0.2}
const MOUTH_DESIGNS: Array[String] = ["frog", "overbite", "pout", "fangs", "tongue"]
## M13: the talking designs whose pieces move (alien_talk.gd's bounce, pucker, thrust): their lips, fangs, cup and
## tongue take the motion shaders on the jaw weight COLOR_0.a (tools/blender/alien_m12.py); frog and overbite snap.
const MOVING_DESIGNS: Array[String] = ["pout", "fangs", "tongue"]
const MOVING_PARTS: Array[String] = ["alien_mouth_inner", "alien_tongue"]
## The face materials beyond FACE that the s5 look replaces (M12 the pout's lips, M13 the fangs, M14 the tongue).
const EXTRA_FACE: Array[String] = ["alien_lip_pout", "alien_fang", "alien_tongue_pink", "alien_tooth"]
## M6: the textured skin's contact shade near the lids and lips (alien_hue.gdshader `contact*`), only for a kit whose
## hue material carries a contact marker: M6's CONTACT_MARKER_M6 (one field for every design in TEXCOORD_4's u) or
## M6c's CONTACT_MARKER (tools/blender/alien_m6.py: one channel per design, TEXCOORD_4 = (bored, manic), TEXCOORD_5 =
## (frog, overbite), Godot CUSTOM1; CONTACT_CHANNEL is a design's component, as alien_lids_geom.CONTACT_CHANNEL).
## On an M6c kit set_eyes() and set_mouth_design() pick the shown designs' channels (`contact_pick`).
const CONTACT_MARKER := {"prime_contact": "custom1_designs"}
const CONTACT_MARKER_M6 := {"prime_contact": "custom1_x"}
const CONTACT_CHANNEL := {"bored": 0, "manic": 1, "frog": 2, "overbite": 3}
## M12: the third mouth's channel, a component of CUSTOM2 (glTF TEXCOORD_6 = (pout, fangs); alien_lips_geom
## CONTACT_UV_MOUTH2), picked by `contact_pick2`; M13: the fourth mouth's (fangs) is its v.
const CONTACT_CHANNEL2 := {"pout": 0, "fangs": 1}
## M14: the fifth mouth's (tongue) channel, a component of CUSTOM2's zw (glTF TEXCOORD_7 = (tongue, 0);
## alien_lips_geom CONTACT_UV_MOUTH3), picked by `contact_pick3`.
const CONTACT_CHANNEL3 := {"tongue": 0}
const SKIN_CONTACT := {"contact": 1.0, "contact_tint": Vector3(0.80, 0.66, 0.62), "contact_ao": 0.3}
## M6: LIP_LOOK reads the part's baked AO (COLOR_0), so it applies only to a kit whose imported alien_lip (the lips' and
## the lid domes' one material) carries this marker in its glTF extras (tools/blender/alien_m6.py, after the bake).
const PART_AO_MARKER := {"prime_part_ao": "color0_r"}
const LIDS_MARKER := "prime_lids"  # M10: alien_lip's extras key with the lids' rim reaches (tools/blender/alien_m6.py)
## "m6" (the default): LIP_LOOK and LID_LOOK on a kit with PART_AO_MARKER, LIP_LOOK_M5 on an older kit; "m5":
## LIP_LOOK_M5 on both, no contact shade (before/after sheets). Set before setup().
var lip_look: String = "m6"
const EYE_LOOK := {  # alien_eye.gdshader's per-design uniforms (angles from the pupil axis, degrees; colours sRGB)
	"bored": {"limbus_deg": 27.0, "iris_deg": 25.0, "pupil_deg": 11.5, "iris": Color(0.20, 0.12, 0.08),
		"catch_at_deg": Vector2(6.0, -2.0),
		"catch_deg": 2.5, "catch_soft_deg": 0.4, "catch_energy": 2.2,  # S9: below the rest lid's edge, crisp (rf2)
		# M4: low left by the pupil, just under the rim with the lids at rest
		"catch_anchor_deg": Vector2(5.0, -10.0), "catch_dir": Vector3(-0.45, -0.25, 1.0),
		"limbus_soft_deg": 1.0,  # the cornea's edge outside the iris' soft edge (25 + 0.9 <= 27 - 1)
		# the rims' reach beyond the lid edges (alien_eyes_geom.rim_reach) of S9's lids; a kit with LIDS_MARKER gives
		# its own (M10; M9b's slim lids reached 2.36 and 1.0)
		"upper_reach_deg": 4.3, "lower_reach_deg": 2.0},
	"manic": {"limbus_deg": 21.0, "iris_deg": 0.0, "pupil_deg": 12.0, "iris": Color(0.05, 0.04, 0.05),
		"catch_at_deg": Vector2(4.5, 4.5),
		"catch_anchor_deg": Vector2(4.5, 4.5), "catch_dir": Vector3(-0.45, 0.12, 1.0),  # M4: up and left (S9's place)
		"cornea_normal": 0.15, "limbus_soft_deg": 8.0,  # M4: no ring round the dot pupil (the cornea's edge on the white)
		"upper_reach_deg": 3.7, "lower_reach_deg": 1.8},  # S9's lids (M9b's slim: 2.19, 0.93; LIDS_MARKER)
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
var _part_ao: bool = false  # M6: the kit's alien_lip carries PART_AO_MARKER
var _tex_material: ShaderMaterial  # M5: the skin on its texture set (null for a kit without SSS_MARKER)
var _contact_designs: bool = false  # M6c: the kit's contact field has one channel per design (CONTACT_MARKER)
var _hue_meshes: Array[GeometryInstance3D] = []
var face_look: String = "s5"
var _lid_material: Material
var _face_surfaces: Array = []  # [MeshInstance3D, surface, imported material name]
var _lid_surfaces: Array = []  # [MeshInstance3D, surface]
var _lid_reach: Dictionary = {}  # M10: design -> [upper, lower] rim reach (deg) from the kit's LIDS_MARKER
var _face_materials: Dictionary = {}  # imported name -> the S5 material
var _moving_src: Dictionary = {}  # M13: "<imported name>_moving" -> the imported material (its colour if not in FACE)
var _wet_nodes: Array[GeometryInstance3D] = []  # M4: the lids' wet lines
var _rng := RandomNumberGenerator.new()
var _blink_t: float = -1.0  # ms into the current blink, -1 when not blinking
var _next_blink_s: float = 3.0
var _analyzer: AudioEffectSpectrumAnalyzerInstance
var _next_switch_ms: float = 0.0
var _peak: float = 1e-4
var _last_open_ms: float = -1e9
var _listen_t0: int = 0
var _line: Array = []  # M12: the phase line play_line() drives (alien_talk.gd segments)
var _line_t0: int = 0


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
				var textured: ShaderMaterial = _textured_material(mat)
				m.set_surface_override_material(s, textured if textured != null else _material)
				uses = true
				if m.name.contains("_lid_"):
					_lid_surfaces.append([m, s])
			elif mat != null and (FACE.has(mat.resource_name) or mat.resource_name.begins_with("alien_eye_")
					or mat.resource_name == "alien_wet" or mat.resource_name in EXTRA_FACE
					or (mat.resource_name in MOVING_PARTS and _moving_piece(m.name))):
				# M6: the lid domes take their own copy of the lips' material (LID_LOOK)
				var key: String = mat.resource_name
				if key == "alien_lip" and has_marker(mat, PART_AO_MARKER):
					_part_ao = true
				if key == "alien_lip":
					_read_lid_reach(mat)
				if key == "alien_lip" and m.name.contains("_lid_"):
					key = "alien_lid"
				if key in MOVING_PARTS and _moving_piece(m.name):  # M13: the cup and tongue move with the lips
					key += "_moving"
					_moving_src[key] = mat
				_face_surfaces.append([m, s, key])
				if mat.resource_name == "alien_wet" and not _wet_nodes.has(m):
					m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
					_wet_nodes.append(m)
		if uses:
			_hue_meshes.append(m)
		if _moving_piece(m.name) and m.name.begins_with("mouth_") and not has_jaw_weight(m.mesh):
			# PR #250's review: an M13 kit (the weight in COLOR_0.g, alpha 1) moves the whole piece with the jaw
			push_warning(("alien: %s has no jaw weight (COLOR_0's alpha is 1 everywhere): rebuild the kit with "
				+ "tools/blender/alien_m12.py") % m.name)
	_make_face_materials()
	set_face_look(face_look)
	set_hue("teal")
	set_eyes(eyes)
	set_mouth_design(mouth_design)
	set_crest(crest)
	_next_blink_s = _rng.randf_range(BLINK_EVERY_S.x, BLINK_EVERY_S.y)


## M5: the skin material on the imported material's texture set (the albedo, the ORM with the SSS mask in B, the
## normal map), made once and shared like _material; null unless the imported material carries SSS_MARKER (its glTF
## extras, Godot's "extras" metadata) and an albedo texture: an older textured kit keeps the procedural skin. The first
## textured surface also gives _material SKIN_TEX_SHARED (the crests).
func _textured_material(imported: Material) -> ShaderMaterial:
	var bm := imported as BaseMaterial3D
	if bm == null or bm.albedo_texture == null or not has_sss_marker(imported):
		return null
	if _tex_material == null:
		_tex_material = ShaderMaterial.new()
		_tex_material.shader = SHADER
		_tex_material.resource_name = "alien_hue_textured"
		for k: String in SKIN:
			_tex_material.set_shader_parameter(k, SKIN[k])
		for k: String in SKIN_TEX:
			_tex_material.set_shader_parameter(k, SKIN_TEX[k])
		for k: String in SKIN_TEX_SHARED:
			_material.set_shader_parameter(k, SKIN_TEX[k])
		_tex_material.set_shader_parameter("albedo_tex", bm.albedo_texture)
		var orm: Texture2D = bm.roughness_texture if bm.roughness_texture != null else bm.ao_texture
		if orm != null:
			_tex_material.set_shader_parameter("orm_tex", orm)
		if bm.normal_enabled and bm.normal_texture != null:
			_tex_material.set_shader_parameter("normal_tex", bm.normal_texture)
		_contact_designs = has_marker(imported, CONTACT_MARKER)
		if (_contact_designs or has_marker(imported, CONTACT_MARKER_M6)) and lip_look != "m5":  # M6: the contact shade
			for k: String in SKIN_CONTACT:
				_tex_material.set_shader_parameter(k, SKIN_CONTACT[k])
		var t: Color = (HUES["teal"][0] as Color).srgb_to_linear()
		var p: Color = (HUES["teal"][1] as Color).srgb_to_linear()
		for m: ShaderMaterial in [_tex_material, _material]:
			m.set_shader_parameter("tex_hue", Vector3(t.r, t.g, t.b))
			m.set_shader_parameter("tex_pale", Vector3(p.r, p.g, p.b))
	return _tex_material


## M5: whether an imported material carries SSS_MARKER in its glTF extras.
static func has_sss_marker(imported: Material) -> bool:
	return has_marker(imported, SSS_MARKER)


## Whether an imported material's glTF extras hold every key of a marker (M5's SSS_MARKER, M6's CONTACT_MARKER).
static func has_marker(imported: Material, marker: Dictionary) -> bool:
	if imported == null or not imported.has_meta("extras"):
		return false
	var ex: Variant = imported.get_meta("extras")
	if not ex is Dictionary:
		return false
	for k: String in marker:
		if (ex as Dictionary).get(k, "") != marker[k]:
			return false
	return true


## M6: whether the lips and lid domes take LIP_LOOK and LID_LOOK (lip_look "m6" on a kit with PART_AO_MARKER).
func uses_m6_lips() -> bool:
	return lip_look != "m5" and _part_ao


## M5: whether the skin samples a texture set.
func is_textured() -> bool:
	return _tex_material != null


func _make_face_materials() -> void:
	for name: String in FACE:
		var f: Array = FACE[name]
		if name == "alien_lip":  # S9: the lips and lid domes take the sheen and grain shader (M6: the lids a copy)
			for key: String in ["alien_lip", "alien_lid"]:
				var lm := ShaderMaterial.new()
				lm.shader = LIP_SHADER
				lm.resource_name = key
				lm.set_shader_parameter("albedo", f[0])
				lm.set_shader_parameter("roughness_value", f[1])
				lm.set_shader_parameter("specular_value", f[2])
				var m6: bool = uses_m6_lips()
				var look: Dictionary = LIP_LOOK if m6 else LIP_LOOK_M5
				for k: String in look:
					var v: Variant = look[k]
					if k == "ao_range":  # smoothstep needs 0 <= x < y <= 1
						var r: Vector2 = v
						r.x = clampf(r.x, 0.0, 0.99)
						v = Vector2(r.x, clampf(r.y, r.x + 0.01, 1.0))
					lm.set_shader_parameter(k, v)
				if key == "alien_lid" and m6:
					for k: String in LID_LOOK:
						lm.set_shader_parameter(k, LID_LOOK[k])
				_face_materials[key] = lm
			var pm := ShaderMaterial.new()  # M12: the pout's own glossy red (alien_lip_pout)
			pm.shader = LIP_SHADER
			pm.resource_name = "alien_lip_pout"
			for k: String in LIP_LOOK:
				pm.set_shader_parameter(k, LIP_LOOK[k])
			for k: String in LIP_LOOK_POUT:
				pm.set_shader_parameter(k, LIP_LOOK_POUT[k])
			_face_materials["alien_lip_pout"] = pm
			var fm := ShaderMaterial.new()  # M13: the fangs (alien_fang)
			fm.shader = LIP_SHADER
			fm.resource_name = "alien_fang"
			for k: String in LIP_LOOK:
				fm.set_shader_parameter(k, LIP_LOOK[k])
			for k: String in FANG_LOOK:
				fm.set_shader_parameter(k, FANG_LOOK[k])
				_face_materials["alien_fang"] = fm
			var tm := ShaderMaterial.new()  # M14: the tongue (alien_tongue_pink)
			tm.shader = LIP_SHADER
			tm.resource_name = "alien_tongue_pink"
			for k: String in LIP_LOOK:
				tm.set_shader_parameter(k, LIP_LOOK[k])
			for k: String in TONGUE_LOOK:
				tm.set_shader_parameter(k, TONGUE_LOOK[k])
			_face_materials["alien_tongue_pink"] = tm
			var th := ShaderMaterial.new()  # M14: the tongue mouth's teeth (alien_tooth)
			th.shader = LIP_SHADER
			th.resource_name = "alien_tooth"
			for look: Dictionary in [LIP_LOOK, FANG_LOOK, TOOTH_LOOK]:
				for k: String in look:
					th.set_shader_parameter(k, look[k])
			_face_materials["alien_tooth"] = th
			continue
		var m := StandardMaterial3D.new()
		m.resource_name = name
		m.albedo_color = f[0]
		m.roughness = f[1]
		m.metallic_specular = f[2]
		m.diffuse_mode = BaseMaterial3D.DIFFUSE_LAMBERT_WRAP
		m.cull_mode = BaseMaterial3D.CULL_DISABLED  # as the imported (double-sided) ones: culled, the inner cup vanished
		_face_materials[name] = m
	for key: String in _moving_src:  # M13: the moving cups and tongues (alien_mouth_part.gdshader)
		var src: Material = _moving_src[key]
		var base: String = key.trim_suffix("_moving")
		var mm := ShaderMaterial.new()
		mm.shader = MOUTH_PART_SHADER
		mm.resource_name = key
		if FACE.has(base):
			mm.set_shader_parameter("albedo", FACE[base][0])
			mm.set_shader_parameter("roughness_value", FACE[base][1])
			mm.set_shader_parameter("specular_value", FACE[base][2])
		elif src is BaseMaterial3D:
			mm.set_shader_parameter("albedo", (src as BaseMaterial3D).albedo_color)
			mm.set_shader_parameter("roughness_value", (src as BaseMaterial3D).roughness)
			mm.set_shader_parameter("specular_value", (src as BaseMaterial3D).metallic_specular)
		_face_materials[key] = mm
	var w := ShaderMaterial.new()
	w.shader = WET_SHADER
	w.resource_name = "alien_wet"
	_face_materials["alien_wet"] = w
	_lid_material = _face_materials["alien_lid"]  # the eye sheets (eb1, em1): the lids are soft domes in the lips' colour
	for design: String in EYE_LOOK:
		var e := ShaderMaterial.new()
		e.shader = EYE_SHADER
		e.resource_name = "alien_eye_" + design
		for k: String in EYE_LOOK[design]:
			e.set_shader_parameter(k, EYE_LOOK[design][k])
		if _lid_reach.has(design):  # M10: the kit's own lids' rim reaches (LIDS_MARKER)
			e.set_shader_parameter("upper_reach_deg", float(_lid_reach[design][0]))
			e.set_shader_parameter("lower_reach_deg", float(_lid_reach[design][1]))
		_face_materials["alien_eye_" + design] = e


## M10 (PR #243's review minor 1): the rims' reaches from alien_lip's LIDS_MARKER (tools/blender/alien_m6.py: a JSON
## string {"lids": {...}, "reach_deg": {design: [upper, lower]}}); a kit without it keeps EYE_LOOK's (S9's lids).
func _read_lid_reach(imported: Material) -> void:
	if imported == null or not imported.has_meta("extras"):
		return
	var ex: Variant = imported.get_meta("extras")
	if not ex is Dictionary or not (ex as Dictionary).has(LIDS_MARKER):
		return
	var parsed: Variant = JSON.parse_string(str((ex as Dictionary)[LIDS_MARKER]))
	if parsed is Dictionary and (parsed as Dictionary).get("reach_deg") is Dictionary:
		_lid_reach = (parsed as Dictionary)["reach_deg"]


## The rim reaches in use for an eye design: [upper, lower] degrees.
func lid_reach(design: String) -> Array:
	if _lid_reach.has(design):
		return _lid_reach[design]
	return [EYE_LOOK[design]["upper_reach_deg"], EYE_LOOK[design]["lower_reach_deg"]]


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


## The hue (skin) material shared by the body and head (for tuning grids): since M5 the textured one when the kit's
## hue material carries SSS_MARKER (the crests keep the procedural one, procedural_material()).
func skin_material() -> ShaderMaterial:
	return _tex_material if _tex_material != null else _material


## The procedural skin: the whole skin of a kit without SSS_MARKER, the crests' on a textured kit (SKIN_TEX_SHARED).
func procedural_material() -> ShaderMaterial:
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
	_pick_contact()
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
			ball.set_instance_shader_parameter("aim_deg", -aim if side == "L" else aim)  # M4: the lids' frame
		var open: float = smoothstep(WET_OPEN_DEG.x, WET_OPEN_DEG.y, lower_deg - upper_deg)  # the edges' gap
		for lid: String in ["upper", "lower"]:
			var wet := node("eye_%s_wet_%s_%s" % [eyes, lid, side]) as GeometryInstance3D
			if wet != null:
				wet.set_instance_shader_parameter("open", open)


## M6c: the skin's contact shade from the shown eye design's and mouth's channels only (an M6c kit; M6's one field
## stays on CUSTOM1.x, the shader's default pick).
func _pick_contact() -> void:
	if _tex_material == null or not _contact_designs:
		return
	var pick := Vector4.ZERO
	var pick2 := Vector2.ZERO  # M12: CUSTOM2.xy (TEXCOORD_6: pout, fangs)
	var pick3 := Vector2.ZERO  # M14: CUSTOM2.zw (TEXCOORD_7: tongue, 0)
	for d: String in [eyes, mouth_design]:
		if CONTACT_CHANNEL.has(d):
			pick[CONTACT_CHANNEL[d]] = 1.0
		elif CONTACT_CHANNEL2.has(d):
			pick2[CONTACT_CHANNEL2[d]] = 1.0
		elif CONTACT_CHANNEL3.has(d):
			pick3[CONTACT_CHANNEL3[d]] = 1.0
	_tex_material.set_shader_parameter("contact_pick", pick)
	_tex_material.set_shader_parameter("contact_pick2", pick2)
	_tex_material.set_shader_parameter("contact_pick3", pick3)


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
	_pick_contact()
	show_mouth(mouth_piece)


## "3d": the replacement pieces (mouth_<design>_<shape>); "flip": the flipbook test (S6), one face shell per shape
## (mouthflip_<design>_<shape>) on the design's atlas. A GLB without flip shells keeps "3d".
func set_mouth_mode(mode: String) -> void:
	mouth_mode = mode
	show_mouth(mouth_piece)


func show_mouth(piece: String) -> void:
	mouth_piece = piece
	for d: String in MOUTH_DESIGNS:
		for v: String in VISEMES:
			var p: Node3D = node("mouth_%s_%s" % [d, v])
			if p == null:  # a kit without that design (the pout before M12)
				continue
			# the pout and the fangs have no flipbook shells: they show their 3D pieces in both modes
			p.visible = (mouth_mode == "3d" or d in MOVING_DESIGNS) and d == mouth_design and v == piece
			var f: Node3D = node("mouthflip_%s_%s" % [d, v])
			if f != null:
				f.visible = mouth_mode == "flip" and d == mouth_design and v == piece
	var teeth: Node3D = node("mouth_overbite_teeth")  # S3's separate teeth; since S6 each overbite piece has its own
	if teeth != null:
		teeth.visible = mouth_mode == "3d" and mouth_design == "overbite"


## PR #250's review: whether a talking piece's mesh carries a jaw weight (COLOR_0's alpha below 1 somewhere; the
## upper lip is 0). A mesh without vertex colours has none.
static func has_jaw_weight(mesh: Mesh) -> bool:
	if mesh == null:
		return false
	for s: int in mesh.get_surface_count():
		var arrays: Array = mesh.surface_get_arrays(s)
		var cols: Variant = arrays[Mesh.ARRAY_COLOR]
		if cols is PackedColorArray:
			for c: Color in cols:
				if c.a < 0.999:
					return true
	return false


## M12: whether the kit has a mouth design's pieces.
func has_mouth_design(design: String) -> bool:
	return node("mouth_%s_rest" % design) != null


## M13: whether a piece node (mouth_<design>_<shape>, a grid's lipvar_<variant>_<design>_<shape>) is of a talking
## design whose cup and tongue move with its lips.
static func _moving_piece(name: String) -> bool:
	if not (name.begins_with("mouth_") or name.begins_with("lipvar_")):
		return false
	for d: String in MOVING_DESIGNS:
		if name.begins_with("mouth_%s_" % d) or (name.begins_with("lipvar_") and name.contains("_%s_" % d)):
			return true
	return false


## M12: the secondary motion on the shown 3D piece (alien_mouth_motion.gdshaderinc's instance uniforms on the lips,
## fangs, cup and tongue; 0 = none). M13: the lower jaw's forward thrust; the motion lives in the s5 face look's
## shaders, so with the "first" look (the imported materials) the piece does not move.
## M14: `flop`, the tongue mouth's tongue tip (m, the socket's frame: y up, z forward).
func set_mouth_motion(drop: float, pucker: float, thrust: float = 0.0, flop: Vector3 = Vector3.ZERO) -> void:
	var p := node("mouth_%s_%s" % [mouth_design, mouth_piece]) as GeometryInstance3D
	if p != null and face_look == "s5":
		p.set_instance_shader_parameter("lip_drop", drop)
		p.set_instance_shader_parameter("pucker", pucker)
		p.set_instance_shader_parameter("jaw_thrust", thrust)
		p.set_instance_shader_parameter("tongue_flop", flop)


## M12: a phase line's piece and motion at t_ms through the shown design's talk style (alien_talk.gd); returns the
## sample ({"piece", "drop", "pucker", "thrust", "flop", "since_ms"}).
func talk_at(t_ms: float, line: Array = AlienTalk.LINE) -> Dictionary:
	var s: Dictionary = AlienTalk.sample(mouth_design, AlienTalk.segments(line), t_ms)
	set_mouth_motion(0.0, 0.0)
	show_mouth(s["piece"])
	set_mouth_motion(s["drop"], s["pucker"], s["thrust"], s["flop"])
	return s


## M12: talk a phase line from now (stops listening; _process drives talk_at until the line ends).
func play_line(line: Array = AlienTalk.LINE) -> void:
	_analyzer = null
	_line = line
	_line_t0 = Time.get_ticks_msec()


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
	_line = []  # M13 (PR #246's review minor 6): listening ends a playing line
	set_mouth_motion(0.0, 0.0)
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
	if not _line.is_empty():  # M12: a phase line
		var tl: float = float(Time.get_ticks_msec() - _line_t0)
		talk_at(tl, _line)
		var segs: Array = AlienTalk.segments(_line)
		if segs.is_empty() or tl > float(segs[-1][1]) + 600.0:
			_line = []
			set_mouth_motion(0.0, 0.0)
			show_mouth("rest")
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
