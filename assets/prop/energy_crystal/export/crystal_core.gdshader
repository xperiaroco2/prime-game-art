// The energy crystal's core: a slimmer copy of the crystal inside it, turned 30 degrees, seen through the charged
// shell as its inner light and a second set of facet lines. Dark and unlit-looking when spent (the opaque stone
// hides it then). UV0 as on the shell: u the chamfer, v the facet's random value.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform float charge : hint_range(0.0, 1.0) = 1.0;
uniform vec3 glow_colour : source_color = vec3(0.0, 0.62, 1.0);
uniform vec3 edge_colour : source_color = vec3(0.15, 0.85, 1.0);
uniform float glow = 0.95;
uniform float edge_glow = 0.2;
uniform float pulse : hint_range(0.0, 0.3) = 0.05;

void fragment() {
	float edge = UV.x;
	float rnd = UV.y;
	float beat = 1.0 + pulse * sin(TIME * 1.6 + 1.3 + rnd * 6.2832);
	ALBEDO = vec3(0.02, 0.025, 0.03);
	ROUGHNESS = 0.5;
	float facing = clamp(dot(NORMAL, VIEW), 0.0, 1.0);  // soft toward its own outline: a glow, not a box
	EMISSION = (glow_colour * glow * (0.55 + 0.9 * rnd) * (0.3 + 0.9 * facing) + edge_colour * edge_glow * edge)
		* beat * charge;
}
