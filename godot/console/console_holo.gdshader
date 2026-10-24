// The start console's hologram and light column (console.gd): additive cyan light, no depth write, both sides.
// mode 0 the lines (their brightness x 100 in the build's UV0 v; glTF flips v: 1 - UV.y), mode 1 the see-through
// shell (brighter where it turns away from the eye, its outline), mode 2 the column from the core (fading upward,
// UV0 v the height share x 100, and toward its silhouette).
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, shadows_disabled, fog_disabled;

uniform int mode = 0;
uniform vec3 colour : source_color = vec3(0.06, 0.42, 1.0);
uniform float energy = 1.6;

void fragment() {
	float k = (1.0 - UV.y) * 0.01;
	float facing = abs(dot(NORMAL, VIEW));
	float a;
	if (mode == 0) {
		a = k * energy;
	} else if (mode == 1) {
		a = k * energy * (0.25 + 0.9 * (1.0 - facing));
	} else {
		a = pow(clamp(1.0 - k, 0.0, 1.0), 1.6) * facing * energy;
	}
	ALBEDO = colour * a;
}
