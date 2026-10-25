// The start console's metal, warm bronze or graphite (console.gd sets the colours): a fine brushed grain and a broad
// mottle in model space, and the bright edges the stations' concepts show: the build's chamfer faces (UV0 u = 1),
// broken up a little. No textures.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

// sRGB (source_color): the Blender look's linear bronze (0.56, 0.27, 0.10) and bright edge (1.0, 0.70, 0.40)
uniform vec3 base_color : source_color = vec3(0.774, 0.556, 0.349);
uniform vec3 worn_color : source_color = vec3(1.0, 0.854, 0.665);
uniform float metallic : hint_range(0.0, 1.0) = 1.0;
uniform float roughness : hint_range(0.0, 1.0) = 0.34;
uniform float wear : hint_range(0.0, 1.0) = 0.9;
// a faint glow of its own colour: the hall lights its middle little (its lamps stand at the wall), and a metal with
// nothing to mirror reads black there; the concept's bronze stays warm and bright
uniform float lift : hint_range(0.0, 0.5) = 0.0;

varying vec3 mpos;
varying vec3 mnrm;

void vertex() {
	mpos = VERTEX;
	mnrm = NORMAL;
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

// x: the brushed grain (along the blocks, up), y: the broad mottle
vec2 layer(vec2 uv) {
	float g = noise(vec2(uv.x * 12.0, uv.y * 360.0)) * 0.6 + noise(vec2(uv.x * 4.0, uv.y * 110.0)) * 0.4;
	float m = noise(uv * 7.0) * 0.6 + noise(uv * 22.0) * 0.4;
	return vec2(g, m);
}

void fragment() {
	vec3 n = abs(mnrm);
	n = pow(n, vec3(4.0));
	n /= (n.x + n.y + n.z);
	vec2 v = layer(mpos.zy) * n.x + layer(mpos.xz) * n.y + layer(mpos.xy) * n.z;
	float worn = clamp(UV.x * wear * (0.6 + 0.5 * v.y), 0.0, 1.0);
	// faint: stronger streaks read as wood grain on the bronze (the crystal's 2026-10-24 trial)
	vec3 col = mix(base_color, worn_color, worn) * (0.94 + 0.12 * v.y) * (1.0 + (v.x - 0.5) * 0.04);
	ALBEDO = col;
	EMISSION = col * lift;
	METALLIC = metallic;
	ROUGHNESS = clamp(roughness + (v.x - 0.5) * 0.02 + (v.y - 0.5) * 0.06 - worn * 0.14, 0.05, 1.0);
}
