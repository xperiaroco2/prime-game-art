// The start console's metal, warm bronze or graphite (console.gd sets the colours): a fine brushed grain and a broad
// mottle in model space, and the bright edges the stations' concepts show: the build's chamfer faces (UV0 u = 1),
// broken up a little. No textures. The stations share it byte for byte (art#263; test_props_metal_shader.py): the
// start console's export copy, the crystal socket's socket_metal.gdshader, the breaker board's board_metal.gdshader
// and the crystal charger's export copy. The parameters after `lift` (socket-3) default to the console's look; the
// stations raise them for the sheet's machined bronze (light-to-dark faces, glints, worn edges).
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

// fix1 (art#263): the dent and wave height field, a smooth 3D gradient noise with a quintic fade (its slope has no
// creases) in a turned model space (its lattice runs along no face). The value noise above, projected on the three
// planes, drew square tone patches on the stations' big flat faces: its slope steps at every cell edge
const mat3 TURN = mat3(vec3(0.0, 0.8, 0.6), vec3(-0.8, 0.36, -0.48), vec3(-0.6, -0.48, 0.64));

vec3 ghash(vec3 p) {
	p = vec3(dot(p, vec3(127.1, 311.7, 74.7)), dot(p, vec3(269.5, 183.3, 246.1)), dot(p, vec3(113.5, 271.9, 124.6)));
	return fract(sin(p) * 43758.5453) * 2.0 - 1.0;
}

// the gradient noise and its exact derivative: x the value, yzw the gradient (d/dp), from one pass over the cell's 8
// corners (8 hashes). Option A (art#263, the engineer 2026-10-26): the slope below used to be a forward difference of
// four noise passes per octave (64 hashes per slope); the derivative gives the same field's slope at a quarter of it
vec4 gnoised(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	vec3 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
	vec3 du = 30.0 * f * f * (f * (f - 2.0) + 1.0);
	vec3 ga = ghash(i);
	vec3 gb = ghash(i + vec3(1.0, 0.0, 0.0));
	vec3 gc = ghash(i + vec3(0.0, 1.0, 0.0));
	vec3 gd = ghash(i + vec3(1.0, 1.0, 0.0));
	vec3 ge = ghash(i + vec3(0.0, 0.0, 1.0));
	vec3 gf = ghash(i + vec3(1.0, 0.0, 1.0));
	vec3 gg = ghash(i + vec3(0.0, 1.0, 1.0));
	vec3 gh = ghash(i + vec3(1.0, 1.0, 1.0));
	float va = dot(ga, f);
	float vb = dot(gb, f - vec3(1.0, 0.0, 0.0));
	float vc = dot(gc, f - vec3(0.0, 1.0, 0.0));
	float vd = dot(gd, f - vec3(1.0, 1.0, 0.0));
	float ve = dot(ge, f - vec3(0.0, 0.0, 1.0));
	float vf = dot(gf, f - vec3(1.0, 0.0, 1.0));
	float vg = dot(gg, f - vec3(0.0, 1.0, 1.0));
	float vh = dot(gh, f - vec3(1.0, 1.0, 1.0));
	float v = va + u.x * (vb - va) + u.y * (vc - va) + u.z * (ve - va) + u.x * u.y * (va - vb - vc + vd)
		+ u.y * u.z * (va - vc - ve + vg) + u.z * u.x * (va - vb - ve + vf)
		+ u.x * u.y * u.z * (-va + vb + vc - vd + ve - vf - vg + vh);
	vec3 d = ga + u.x * (gb - ga) + u.y * (gc - ga) + u.z * (ge - ga) + u.x * u.y * (ga - gb - gc + gd)
		+ u.y * u.z * (ga - gc - ge + gg) + u.z * u.x * (ga - gb - ge + gf)
		+ u.x * u.y * u.z * (-ga + gb + gc - gd + ge - gf - gg + gh)
		+ du * (vec3(vb - va, vc - va, ve - va) + u.yzx * vec3(va - vb - vc + vd, va - vc - ve + vg, va - vb - ve + vf)
		+ u.zxy * vec3(va - vb - ve + vf, va - vb - vc + vd, va - vc - ve + vg)
		+ u.yzx * u.zxy * (-va + vb + vc - vd + ve - vf - vg + vh));
	return vec4(v, d);
}

// the height field's slope along the face (model space, about unit size), s cycles per metre: two octaves of the
// gradient noise, each in its own turned space; 0.69 keeps the slope's strength the old value noise's (its RMS over a
// face). The gradient divided by s (the old forward difference over 0.3 of a cell, divided by 0.3), taken at that
// difference's midpoint so most glints stay near where they were
vec3 slope(vec3 p, vec3 nrm, float s) {
	vec3 q = TURN * ((p + vec3(0.15 / s)) * s);
	mat3 t = transpose(TURN);
	vec3 g = t * gnoised(q).yzw;
	g += 0.35 * 2.17 * (t * (t * gnoised(TURN * q * 2.17 + vec3(5.2, 1.3, 7.7)).yzw));
	g *= 0.69;
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
		vec3 bend = vec3(0.0);
		if (dent > 0.0) {
			bend += slope(mpos, nm, dent_scale) * dent;
		}
		if (wave > 0.0) {
			bend += slope(mpos, nm, wave_scale) * wave;
		}
		NORMAL = normalize(NORMAL - (VIEW_MATRIX * (MODEL_MATRIX * vec4(bend, 0.0))).xyz);
	}
	ALBEDO = col;
	EMISSION = col * lift;
	METALLIC = metallic;
	ROUGHNESS = clamp(roughness + (v.x - 0.5) * rough_grain + (v.y - 0.5) * rough_mottle - worn * edge_polish, 0.05, 1.0);
}
