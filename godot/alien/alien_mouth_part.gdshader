// M13 (art #196, PR #246's review minor 5): the inner cup and the tongue of a talking mouth design's pieces (the pout,
// the fangs), so they move with the lips (alien_mouth_motion.gdshaderinc on the jaw weight COLOR.g). Otherwise the
// face kit's StandardMaterial3D for them (alien.gd FACE: the colour, roughness and specular, the wrapped diffuse, both
// sides drawn); the frog's and overbite's cups and tongues keep that material.
shader_type spatial;
render_mode diffuse_lambert_wrap, specular_schlick_ggx, cull_disabled;

uniform vec3 albedo : source_color = vec3(0.25, 0.11, 0.14);
uniform float roughness_value : hint_range(0.0, 1.0) = 0.9;
uniform float specular_value : hint_range(0.0, 1.0) = 0.08;

#include "res://alien/alien_mouth_motion.gdshaderinc"

void vertex() {
	VERTEX = mouth_motion(VERTEX, COLOR.g);
}

void fragment() {
	ALBEDO = albedo;
	ROUGHNESS = roughness_value;
	SPECULAR = specular_value;
}
