// The alien's lips and lid domes (art #196, S9): the soft coral of S5's StandardMaterial3D (wrapped diffuse, both
// sides drawn) plus rf2's slight sheen (a soft clear coat) and a faint fine grain (a model-space value-noise micro
// normal, faded with the view distance). alien.gd sets the colour and the terms (FACE, LIP_LOOK, LID_LOOK).
// M6 (art #196): the skin's surface quality, so the parts read as the same soft body as the head (the engineer: they
// looked like parts "from another universe"), every term off at its default (S9's look; alien.gd "m5"):
// - the part's own baked AO (COLOR.r: glTF COLOR_0 of tools/blender/alien_m6.py, white on an older kit) moves the
//   colour toward a deeper, warmer coral (`deep`) in the folds and where the part meets the skin (`ao_mix`, over
//   `ao_range`), feeds AO (`ao_occl`), and the rolls keep the lighter coral;
// - a soft colour drift (`drift`: model-space value noise at `drift_freq`, warm/cool and light/dark), as the skin's;
// - screen-space SSS (`sss`) and a warm transmittance (`transmit`), as the skin's thin parts;
// - Godot's rim (`rim_value`, `rim_tint`) as on the skin.
shader_type spatial;
render_mode diffuse_lambert_wrap, specular_schlick_ggx, cull_disabled;

uniform vec3 albedo : source_color = vec3(0.82, 0.44, 0.37);
uniform float roughness_value : hint_range(0.0, 1.0) = 0.6;
uniform float specular_value : hint_range(0.0, 1.0) = 0.3;
uniform float sheen : hint_range(0.0, 1.0) = 0.0;  // the clear coat's strength
uniform float sheen_roughness : hint_range(0.0, 1.0) = 0.5;
uniform float grain : hint_range(0.0, 0.5) = 0.0;
uniform float grain_freq = 900.0;
uniform vec2 grain_fade = vec2(0.6, 2.0);
// M6
uniform vec3 deep : source_color = vec3(0.56, 0.18, 0.17);  // the coral in the folds (sRGB)
uniform float ao_mix : hint_range(0.0, 1.0) = 0.0;
uniform vec2 ao_range = vec2(0.45, 0.95);  // COLOR.r from full `deep` to the plain albedo
uniform float ao_occl : hint_range(0.0, 1.0) = 0.0;
uniform float drift : hint_range(0.0, 0.3) = 0.0;
uniform float drift_freq = 40.0;  // per m: blotches of about 2.5 cm
uniform float sss : hint_range(0.0, 1.0) = 0.0;
uniform float transmit : hint_range(0.0, 1.0) = 0.0;
uniform float transmit_depth = 0.01;
uniform vec3 transmit_color : source_color = vec3(1.0, 0.55, 0.42);
uniform float rim_value : hint_range(0.0, 1.0) = 0.0;
uniform float rim_tint : hint_range(0.0, 1.0) = 0.5;

// M12/M13 (art #196): a talking mouth piece's secondary motion (lip_drop, jaw_thrust, pucker on the jaw weight
// COLOR.a since M13b): alien_mouth_motion.gdshaderinc.
#include "res://alien/alien_mouth_motion.gdshaderinc"

varying vec3 m_pos;

#include "res://alien/alien_grain.gdshaderinc"

void vertex() {
	m_pos = VERTEX;  // the grain and drift stay on the lips as they move
	VERTEX = mouth_motion(VERTEX, COLOR.a);
}

void fragment() {
	float rough = roughness_value;
	float fade = 1.0 - smoothstep(grain_fade.x, grain_fade.y, length(VERTEX));
	if (grain > 0.0 && fade > 0.0) {
		vec3 q = m_pos * grain_freq;
		vec3 g = vec3(vnoise(q), vnoise(q + vec3(17.1, 3.3, 9.7)), vnoise(q + vec3(5.9, 23.4, 1.7))) - 0.5;
		vec3 gv = (VIEW_MATRIX * (MODEL_MATRIX * vec4(g, 0.0))).xyz;
		gv -= dot(gv, NORMAL) * NORMAL;
		NORMAL = normalize(NORMAL + gv * grain * fade);
		rough = clamp(rough + (vnoise(q * 0.5) - 0.5) * grain * fade * 0.6, 0.0, 1.0);
	}
	vec3 c = albedo;
	float ao = clamp(COLOR.r, 0.0, 1.0);
	if (ao_mix > 0.0) {
		float s = smoothstep(ao_range.x, ao_range.y, ao);
		c = mix(mix(deep, albedo, s), albedo, 1.0 - ao_mix);
	}
	if (drift > 0.0) {
		vec3 q = m_pos * drift_freq;
		float a = vnoise(q) - 0.5;
		float b = vnoise(q * 2.1 + vec3(7.3, 1.9, 4.4)) - 0.5;
		c *= vec3(1.0 + drift * (a + 0.4 * b), 1.0 + drift * 0.6 * b, 1.0 - drift * 0.5 * a);
	}
	ALBEDO = c;
	AO = mix(1.0, ao, ao_occl);
	ROUGHNESS = rough;
	SPECULAR = specular_value;
	CLEARCOAT = sheen;
	CLEARCOAT_ROUGHNESS = sheen_roughness;
	SSS_STRENGTH = sss;
	// the transmittance is always written with a depth above 0: Godot divides by it (M5's black skin)
	SSS_TRANSMITTANCE_COLOR = vec4(transmit_color, step(1e-4, transmit));
	SSS_TRANSMITTANCE_DEPTH = max(transmit_depth, 0.001);
	SSS_TRANSMITTANCE_BOOST = transmit;
	RIM = rim_value;
	RIM_TINT = rim_tint;
}
