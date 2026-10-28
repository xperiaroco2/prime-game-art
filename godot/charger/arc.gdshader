// The charger's lightning (art#263, prime-game#1095: "some electricity there"): the arcs from the inner prongs'
// electrodes into the crystal and the sparks, drawn by charger/zap.gd as ribbons rebuilt every frame. Each ribbon
// vertex sits on the bolt's centre line; the vertex stage turns it into a strip that always faces the camera:
//   NORMAL  the bolt's direction at that point (model space)
//   UV      x along the bolt (0 at the electrode .. 1), y the side (-1 .. +1)
//   UV2     x the ribbon's half width (m)
//   COLOR   a its strength (a branch fades toward its tip, a spark with its life)
// Unshaded and additive: a white-cyan core over a cyan halo, HDR so the ship's glow blooms it. It lights nothing;
// zap.gd's small omni lights at the hits do that.
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, skip_vertex_transform, shadows_disabled, fog_disabled;

uniform vec3 core_color : source_color = vec3(0.86, 0.97, 1.0);
uniform vec3 glow_color : source_color = vec3(0.1, 0.62, 1.0);
uniform float core_energy : hint_range(0.0, 32.0) = 6.0;
uniform float glow_energy : hint_range(0.0, 16.0) = 1.6;
// the core's half width as a share of the ribbon's
uniform float core_share : hint_range(0.01, 1.0) = 0.22;
// zap.gd: 0 .. 1 the whole effect (the fade), above 1 the full-charge flash
uniform float strength : hint_range(0.0, 4.0) = 1.0;

void vertex() {
	vec3 p = (MODELVIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 t = (MODELVIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;
	vec3 s = cross(t, p);
	float l = length(s);
	s = l > 1e-8 ? s / l : vec3(1.0, 0.0, 0.0);
	VERTEX = p + s * UV.y * UV2.x;
	NORMAL = vec3(0.0, 0.0, 1.0);
}

void fragment() {
	float y = abs(UV.y);
	float core = 1.0 - smoothstep(core_share * 0.6, core_share, y);
	float halo = (1.0 - y) * (1.0 - y);
	halo *= halo;
	ALBEDO = (core_color * core * core_energy + glow_color * halo * glow_energy) * COLOR.a * strength;
}
