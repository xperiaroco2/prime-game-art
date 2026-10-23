// The energy crystal's shell (art#263's station props; godot/crystal/crystal.gd applies it). One material, two
// states: charge 1 is a tinted translucent gem, glowing facet by facet with bright edges, the core's light seen
// through it; charge 0 is a matte grey stone, opaque, no glow. UV0 from the build (tools/blender/crystal_build.py):
// u = 1 on the facet edges' chamfers, v = the facet's random value. No textures.
shader_type spatial;
render_mode blend_mix, depth_prepass_alpha, cull_back, diffuse_burley, specular_schlick_ggx;

uniform float charge : hint_range(0.0, 1.0) = 1.0;
uniform vec3 deep : source_color = vec3(0.0, 0.22, 0.48);         // the gem's own colour, under its glow
uniform vec3 glow_colour : source_color = vec3(0.0, 0.78, 1.0);
uniform vec3 edge_colour : source_color = vec3(0.2, 0.88, 1.0);
uniform float glow = 0.75;                                          // the facets' glow (HDR: over 1 blooms)
uniform float edge_glow = 0.45;
uniform float clarity : hint_range(0.0, 1.0) = 0.45;               // how much of the core shows through, face-on
uniform vec3 stone : source_color = vec3(0.33, 0.37, 0.43);        // the spent crystal
uniform float pulse : hint_range(0.0, 0.3) = 0.05;                  // a slow shimmer while charged; 0: still

varying vec3 mpos;

void vertex() {
	mpos = VERTEX;
}

float hash(vec3 p) {
	return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453);
}

// a smooth value noise in model space (the stone's mottle stays put when the crystal is carried)
float vnoise(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = mix(mix(hash(i), hash(i + vec3(1, 0, 0)), f.x), mix(hash(i + vec3(0, 1, 0)), hash(i + vec3(1, 1, 0)), f.x), f.y);
	float b = mix(mix(hash(i + vec3(0, 0, 1)), hash(i + vec3(1, 0, 1)), f.x), mix(hash(i + vec3(0, 1, 1)), hash(i + vec3(1, 1, 1)), f.x), f.y);
	return mix(a, b, f.z);
}

void fragment() {
	float mottle = vnoise(mpos * 40.0) * 0.65 + vnoise(mpos * 110.0) * 0.35;
	float edge = UV.x;
	float rnd = UV.y;
	float facing = clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	float fres = pow(1.0 - facing, 3.0);
	// charged: each facet its own brightness (a squared random, so a few facets flash), brighter face-on, where
	// the eye looks into the gem; the edges a pale cyan line
	float shade = 0.3 + 1.25 * rnd * rnd;
	float beat = 1.0 + pulse * sin(TIME * 1.6 + rnd * 6.2832);
	float inner = 0.35 + 1.05 * facing * facing;  // the middle of the silhouette brightest, as if lit from the core
	vec3 c_em = (glow_colour * glow * shade * inner + edge_colour * edge_glow * edge) * beat;
	float c_alpha = clamp(1.0 - clarity * facing + 0.6 * fres + edge, 0.0, 1.0);
	// spent: grey stone, the facets a little lighter or darker, a soft mottle, the edges a faint lighter line
	vec3 s_alb = stone * (0.8 + 0.35 * rnd) * (0.9 + 0.2 * mottle) + vec3(0.045) * edge;
	ALBEDO = mix(s_alb, deep, charge);
	EMISSION = c_em * charge;
	ROUGHNESS = mix(0.72, 0.1, charge);
	SPECULAR = mix(0.3, 0.4, charge);  // more mirrors the room in white and washes the cyan out
	ALPHA = mix(1.0, c_alpha, charge);
}
