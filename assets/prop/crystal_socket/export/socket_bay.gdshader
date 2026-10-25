// The crystal socket's bay floor (art#263's stations, socket-3): dark, and glowing cyan round a charged crystal, the
// sheet's bay lit from inside. The crystal's own light skips the socket (socket.gd seat_crystal: up close it burned
// the bronze white), so the floor carries the glow itself: a soft oval round the crystal's middle (`centre`, model
// space, m), brightest behind it. socket.gd sets `energy` by the state (charged: lit; spent and empty: dark).
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec3 base_color : source_color = vec3(0.05, 0.06, 0.08);
uniform vec3 glow_color : source_color = vec3(0.0, 0.62, 1.0);
uniform float energy : hint_range(0.0, 16.0) = 0.0;
uniform vec3 centre = vec3(0.0, 1.40, 0.095);
uniform vec2 radius = vec2(0.075, 0.16);  // the oval's half width and half height (m)

varying vec3 mpos;

void vertex() {
	mpos = VERTEX;
}

void fragment() {
	vec2 q = (mpos.xy - centre.xy) / radius;
	float g = exp(-dot(q, q) * 1.6);
	ALBEDO = base_color;
	METALLIC = 0.2;
	ROUGHNESS = 0.55;
	EMISSION = glow_color * energy * g;
}
