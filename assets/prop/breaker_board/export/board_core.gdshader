// The breaker board's crystal cores (godot/board/board.gd gives each core its own copy): kin to the energy crystal's
// core (godot/crystal/crystal_core.gdshader), a cyan glow facet by facet with pale edges, brighter face-on so it reads
// as light from inside. `glow` 1 full, 0 dark glass; the game's sparks and smoke ride on it when its shell trips.
// UV0 from the build (tools/blender/board_build.py): u = 1 on the facets' chamfers, v the facet's random value.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform float glow : hint_range(0.0, 2.0) = 1.0;
uniform vec3 glow_colour : source_color = vec3(0.0, 0.7, 1.0);
uniform vec3 edge_colour : source_color = vec3(0.3, 0.92, 1.0);
uniform vec3 deep : source_color = vec3(0.0, 0.16, 0.34);
uniform float energy = 1.6;          // HDR: over 1 blooms; more bleaches the cyan white
uniform float edge_glow = 0.6;
uniform float pulse : hint_range(0.0, 0.3) = 0.06;

void fragment() {
	float edge = UV.x;
	float rnd = UV.y;
	float facing = clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	float beat = 1.0 + pulse * sin(TIME * 1.6 + rnd * 6.2832);
	float shade = 0.35 + 1.1 * rnd * rnd;
	ALBEDO = deep;
	ROUGHNESS = 0.12;
	SPECULAR = 0.45;
	EMISSION = (glow_colour * energy * shade * (0.35 + 0.95 * facing * facing) + edge_colour * edge_glow * edge)
		* beat * glow;
}
