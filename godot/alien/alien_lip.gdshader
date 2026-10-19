// The alien's lips and lid domes (art #196, S9): the soft coral of S5's StandardMaterial3D (wrapped diffuse, both
// sides drawn) plus rf2's slight sheen (a soft clear coat) and a faint fine grain (a model-space value-noise micro
// normal, faded with the view distance). alien.gd sets the colour and the terms (FACE, LIP_LOOK).
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
uniform float sss : hint_range(0.0, 1.0) = 0.0;
uniform float rim_value : hint_range(0.0, 1.0) = 0.0;

varying vec3 m_pos;

#include "res://alien/alien_grain.gdshaderinc"

void vertex() {
	m_pos = VERTEX;
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
	ALBEDO = albedo;
	ROUGHNESS = rough;
	SPECULAR = specular_value;
	CLEARCOAT = sheen;
	CLEARCOAT_ROUGHNESS = sheen_roughness;
	SSS_STRENGTH = sss;
	RIM = rim_value;
	RIM_TINT = 0.5;
}
