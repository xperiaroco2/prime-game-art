// The lobby window's glass (art #356, docs/lobby.md "Step 3b"): a faint tint and the sky's reflection, stronger at
// grazing angles (Schlick's Fresnel), so the Earth behind stays clear head-on.
shader_type spatial;
render_mode blend_mix, cull_disabled, depth_draw_never, specular_schlick_ggx;

uniform vec3 tint : source_color = vec3(0.55, 0.7, 0.75);
uniform float base_alpha = 0.05;
uniform float edge_alpha = 0.3;

void fragment() {
	float f = pow(1.0 - clamp(abs(dot(NORMAL, VIEW)), 0.0, 1.0), 5.0);
	ALBEDO = tint * 0.08;
	ALPHA = base_alpha + edge_alpha * f;
	METALLIC = 0.0;
	ROUGHNESS = 0.04;
	SPECULAR = 0.6;
}
