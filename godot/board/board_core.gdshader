// The breaker board's crystal cores (godot/board/board.gd gives each core its own copy): kin to the energy crystal's
// core (godot/crystal/crystal_core.gdshader), a cut gem glowing facet by facet with bright edges, brighter face-on so
// it reads as light from inside. `glow` 1 full, 0 dark glass; the game's sparks and smoke ride on it when its shell
// trips. board-3: a deep saturated blue with a wide spread from facet to facet and bright cyan edges (b4's 1.6 cyan
// on every facet bleached them to pale prisms under AgX).
// UV0 from the build (tools/blender/board_build.py): u = 1 on the facets' chamfers, v the facet's random value.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform float glow : hint_range(0.0, 2.0) = 1.0;
uniform vec3 glow_colour : source_color = vec3(0.0, 0.5, 1.0);
uniform vec3 edge_colour : source_color = vec3(0.35, 0.95, 1.0);
uniform vec3 deep : source_color = vec3(0.0, 0.1, 0.36);
uniform float energy = 1.3;          // HDR: over 1 blooms; more bleaches the blue white
uniform float edge_glow = 1.6;
uniform float pulse : hint_range(0.0, 0.3) = 0.06;

void fragment() {
	float edge = UV.x;
	float rnd = UV.y;
	float facing = clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	float beat = 1.0 + pulse * sin(TIME * 1.6 + rnd * 6.2832);
	float shade = 0.15 + 1.5 * rnd * rnd;
	ALBEDO = deep;
	ROUGHNESS = 0.08;
	SPECULAR = 0.6;
	EMISSION = (glow_colour * energy * shade * (0.25 + 1.0 * facing * facing) + edge_colour * edge_glow * edge)
		* beat * glow;
}
