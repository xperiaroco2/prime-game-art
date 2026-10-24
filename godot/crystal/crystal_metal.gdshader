// The energy crystal's cap metal, warm bronze or graphite (crystal.gd sets the colours): a fine brushed grain and
// a broad mottle in model space (the grain stays put when the crystal is carried), and the bright worn edges the
// stations' concepts show: the build's chamfer faces (UV0 u = 1), broken up a little. No textures.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

// sRGB (source_color): the Blender look's linear bronze (0.42, 0.29, 0.17) and worn edge (0.92, 0.74, 0.52)
uniform vec3 base_color : source_color = vec3(0.68, 0.578, 0.454);
uniform vec3 worn_color : source_color = vec3(0.965, 0.88, 0.755);
uniform float metallic : hint_range(0.0, 1.0) = 1.0;
uniform float roughness : hint_range(0.0, 1.0) = 0.36;
uniform float wear : hint_range(0.0, 1.0) = 0.85;

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

// x: the brushed grain, y: the broad mottle
vec2 layer(vec2 uv) {
	float g = noise(vec2(uv.x * 30.0, uv.y * 900.0)) * 0.6 + noise(vec2(uv.x * 9.0, uv.y * 260.0)) * 0.4;
	float m = noise(uv * 18.0) * 0.6 + noise(uv * 55.0) * 0.4;
	return vec2(g, m);
}

void fragment() {
	vec3 n = abs(mnrm);
	n = pow(n, vec3(4.0));
	n /= (n.x + n.y + n.z);
	vec2 v = layer(mpos.zy) * n.x + layer(mpos.xz) * n.y + layer(mpos.xy) * n.z;
	float worn = clamp(UV.x * wear * (0.55 + 0.6 * v.y), 0.0, 1.0);
	// faint: stronger streaks read as wood grain on the bronze (the 2026-10-24 trial)
	vec3 col = mix(base_color, worn_color, worn) * (0.94 + 0.12 * v.y) * (1.0 + (v.x - 0.5) * 0.04);
	ALBEDO = col;
	METALLIC = metallic;
	ROUGHNESS = clamp(roughness + (v.x - 0.5) * 0.02 + (v.y - 0.5) * 0.06 - worn * 0.14, 0.05, 1.0);
}
