// The ship's shared metal (art #263, docs/ship.md): ship.gd puts it on every piece surface whose glTF material is one
// of the library's metals (godot/ship/look.json). No textures and no UVs: a triplanar, world-space brushed grain, fine
// panel seams in a staggered grid, sparse thin scratches and a little grime toward the seams. The plates' own
// chamfers and dark seams are geometry (tools/blender/ship_hull.py).
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec3 base_color : source_color = vec3(0.6, 0.62, 0.65);
uniform float metallic : hint_range(0.0, 1.0) = 0.9;
uniform float roughness : hint_range(0.0, 1.0) = 0.32;
uniform float grain : hint_range(0.0, 1.0) = 0.5;      // brushed streaks
uniform float seams : hint_range(0.0, 1.0) = 0.5;      // fine panel seam lines
uniform float seam_size = 1.15;                        // the fine panels' size in metres
uniform float scratches : hint_range(0.0, 1.0) = 0.5;
uniform float grime : hint_range(0.0, 1.0) = 0.3;

varying vec3 wpos;
varying vec3 wnrm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
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

// x: grain (0..1), y: scratch mask, z: seam mask, w: grime
vec4 layer(vec2 uv) {
	float g = noise(vec2(uv.x * 1.3, uv.y * 140.0)) * 0.6 + noise(vec2(uv.x * 0.4, uv.y * 31.0)) * 0.4;
	// the fine seams: a brick grid, every other row shifted by half a panel
	vec2 q = uv / seam_size;
	q.x += 0.5 * step(1.0, mod(floor(q.y), 2.0));
	vec2 f = fract(q);
	vec2 e = min(f, 1.0 - f) * seam_size;
	float d = min(e.x, e.y);
	float seam = 1.0 - smoothstep(0.003, 0.009, d);
	float dirt = 1.0 - smoothstep(0.0, 0.12, d);
	// scratches: a short thin line in some of the 0.4 m cells
	vec2 c = floor(uv * 2.5);
	vec2 p = fract(uv * 2.5);
	float s = 0.0;
	for (int k = 0; k < 2; k++) {
		vec2 ck = c + vec2(float(k) * 17.0, 3.0);
		if (hash(ck) > 0.62) {
			float a = hash(ck + 3.1) * 6.2832;
			vec2 dir = vec2(cos(a), sin(a));
			vec2 o = vec2(hash(ck + 7.3), hash(ck + 1.7)) * 0.6 + 0.2;
			vec2 r = p - o;
			float along = dot(r, dir);
			float across = abs(dot(r, vec2(-dir.y, dir.x)));
			float len = 0.08 + 0.25 * hash(ck + 9.1);
			s = max(s, (1.0 - smoothstep(0.0012, 0.004, across)) * (1.0 - smoothstep(len * 0.8, len, abs(along))));
		}
	}
	return vec4(g, s, seam, dirt);
}

void fragment() {
	vec3 n = abs(wnrm);
	n = pow(n, vec3(4.0));
	n /= (n.x + n.y + n.z);
	vec4 v = layer(wpos.zy) * n.x + layer(wpos.xz) * n.y + layer(wpos.xy) * n.z;
	float big = noise(wpos.xz * 0.35 + wpos.y * 0.2);
	// polish n2: faces looking down (the belly) keep a third of the grain: its 1.3/m along-streak noise read as long
	// stretched streaks over the belly's big flat plates
	float gr = grain * mix(1.0, 0.35, smoothstep(0.5, 0.9, -wnrm.y));
	vec3 col = base_color * (0.9 + 0.2 * big) * (1.0 + gr * (v.x - 0.5) * 0.18);
	col = mix(col, col * 0.35, v.z * seams);
	col = mix(col, col * 0.75, v.w * grime);
	col = mix(col, vec3(0.85), v.y * scratches * 0.6);
	ALBEDO = col;
	METALLIC = metallic;
	ROUGHNESS = clamp(roughness + gr * (v.x - 0.5) * 0.12 + 0.06 * (big - 0.5) + v.w * grime * 0.15
		- v.y * scratches * 0.12 + v.z * seams * 0.2, 0.04, 1.0);
}
