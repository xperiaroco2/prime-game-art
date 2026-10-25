// The start console's metal, warm bronze or graphite (console.gd sets the colours): a fine brushed grain and a broad
// mottle in model space, and the bright edges the stations' concepts show: the build's chamfer faces (UV0 u = 1),
// broken up a little. No textures. The stations share it (the crystal socket's socket_metal.gdshader is this file):
// the parameters after `lift` (art#263, socket-3) default to the console's look; the socket raises them for the
// sheet's machined bronze (light-to-dark faces, glints, worn edges).
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

// sRGB (source_color): the Blender look's linear bronze (0.56, 0.27, 0.10) and bright edge (1.0, 0.70, 0.40)
uniform vec3 base_color : source_color = vec3(0.774, 0.556, 0.349);
uniform vec3 worn_color : source_color = vec3(1.0, 0.854, 0.665);
uniform float metallic : hint_range(0.0, 1.0) = 1.0;
uniform float roughness : hint_range(0.0, 1.0) = 0.34;
// the edges' wear: UV0 u (0 flat, 1 the bright bevels) times this; over 1 the broad chamfers wear bright too
uniform float wear : hint_range(0.0, 2.0) = 0.9;
// a faint glow of its own colour: the hall lights its middle little (its lamps stand at the wall), and a metal with
// nothing to mirror reads black there; the concept's bronze stays warm and bright
uniform float lift : hint_range(0.0, 0.5) = 0.0;
// socket-3: the strengths the console had built in (its defaults), now parameters: the colour's broad mottle and
// brushed grain, the roughness's grain and mottle, and how much smoother (polished) the worn edges are
uniform float mottle : hint_range(0.0, 1.0) = 0.12;
uniform float grain : hint_range(0.0, 0.5) = 0.04;
uniform float rough_grain : hint_range(0.0, 0.5) = 0.02;
uniform float rough_mottle : hint_range(0.0, 0.5) = 0.06;
uniform float edge_polish : hint_range(0.0, 0.5) = 0.14;
// socket-3, off by default: each face lighter or darker by its facing (a painted light from shade_dir, model space),
// the sheet's light-to-dark facets
uniform float shade : hint_range(0.0, 0.6) = 0.0;
uniform vec3 shade_dir = vec3(-0.45, 0.8, 0.45);
// socket-3, off by default: the normal bent by a hammered dimple (dent, about 1 / dent_scale m across) and a broad
// wave (about 1 / wave_scale m), so the flat faces mirror their surroundings as gradients and glints
uniform float dent : hint_range(0.0, 1.0) = 0.0;
uniform float dent_scale = 80.0;
uniform float wave : hint_range(0.0, 1.0) = 0.0;
uniform float wave_scale = 9.0;

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

// a height field in model space, projected on the three planes (w: the planes' weights), s cycles per metre
float field(vec3 p, vec3 w, float s) {
	return noise(p.zy * s) * w.x + noise(p.xz * s) * w.y + noise(p.xy * s) * w.z;
}

// the field's slope along the face (model space, about unit size)
vec3 slope(vec3 p, vec3 w, vec3 nrm, float s) {
	float e = 0.3 / s;
	float h0 = field(p, w, s);
	vec3 g = vec3(field(p + vec3(e, 0.0, 0.0), w, s), field(p + vec3(0.0, e, 0.0), w, s),
		field(p + vec3(0.0, 0.0, e), w, s)) - h0;
	g /= 0.3;
	return g - nrm * dot(g, nrm);
}

void fragment() {
	vec3 n = abs(mnrm);
	n = pow(n, vec3(4.0));
	n /= (n.x + n.y + n.z);
	vec2 v = layer(mpos.zy) * n.x + layer(mpos.xz) * n.y + layer(mpos.xy) * n.z;
	float worn = clamp(UV.x * wear * (0.6 + 0.5 * v.y), 0.0, 1.0);
	// faint: stronger streaks read as wood grain on the bronze (the crystal's 2026-10-24 trial)
	vec3 col = mix(base_color, worn_color, worn) * (1.0 - mottle * 0.5 + mottle * v.y) * (1.0 + (v.x - 0.5) * grain);
	if (shade > 0.0) {
		col *= 1.0 + shade * dot(normalize(mnrm), normalize(shade_dir));
	}
	if (dent > 0.0 || wave > 0.0) {
		vec3 nm = normalize(mnrm);
		vec3 bend = slope(mpos, n, nm, dent_scale) * dent + slope(mpos, n, nm, wave_scale) * wave;
		NORMAL = normalize(NORMAL - (VIEW_MATRIX * (MODEL_MATRIX * vec4(bend, 0.0))).xyz);
	}
	ALBEDO = col;
	EMISSION = col * lift;
	METALLIC = metallic;
	ROUGHNESS = clamp(roughness + (v.x - 0.5) * rough_grain + (v.y - 0.5) * rough_mottle - worn * edge_polish, 0.05, 1.0);
}
