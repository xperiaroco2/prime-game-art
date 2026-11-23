shader_type spatial;
// The mug lab's foam (research, pipeline A, round 5): ONE volume from the beer's surface up, its shape a profile of
// nine (radius, height) points evaluated here, so the critics' "lid on a sleeve" goes:
// - full (`crown` 1): a column inside the glass from the level to just under the rim, over the lip, a short drape
//   just outside the rim's edge, a mushroom bulge, and a lumpy dome to `head_top`;
// - drinking (`crown` 0): a layer of `layer` m on the beer with a low dome; the profiles blend by `crown`.
// The canonical mesh (mug_lab_build.py foam_unit) has rings at UV.y = t along the profile and a pole at t = 1; the
// angle comes from the vertex. Every position is a function pos(angle, t) (profile plus lumps along its normal), so
// the normal is taken from that function's own finite differences: the lumps light correctly. In the fragment stage:
// Worley bubbles, bigger and darker where the foam presses on the glass (under the rim), small on the crown with a
// few craters; wet and beer-tinted over the beer, with a ragged edge.
render_mode diffuse_lambert_wrap;

uniform float level = 0.126;
uniform float layer = 0.016;
uniform float crown = 1.0;
uniform float inner_r = 0.0381;
uniform float rim = 0.15;
uniform float rim_r = 0.045;
uniform float head_top = 0.182;
uniform float lump = 0.0036;
uniform vec3 cream : source_color = vec3(0.94, 0.87, 0.73);   // round 10: measured on the concept's head, 238,205,170 (h 0.09, s 0.3)
uniform vec3 pressed : source_color = vec3(0.86, 0.72, 0.55);   // seen through the glass under the rim
uniform vec3 wet : source_color = vec3(0.86, 0.62, 0.30);
uniform float glow = 0.03;                         // round 9: a brighter stage made the foam bloom into a halo

varying vec3 obj;
varying float hollow;

float h31(vec3 p) {
	p = fract(p * 0.3183099 + 0.1);
	p *= 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vnoise(vec3 x) {
	vec3 i = floor(x);
	vec3 f = fract(x);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(h31(i), h31(i + vec3(1, 0, 0)), f.x), mix(h31(i + vec3(0, 1, 0)), h31(i + vec3(1, 1, 0)), f.x), f.y),
			mix(mix(h31(i + vec3(0, 0, 1)), h31(i + vec3(1, 0, 1)), f.x), mix(h31(i + vec3(0, 1, 1)), h31(i + vec3(1, 1, 1)), f.x), f.y), f.z) * 2.0 - 1.0;
}

// the profile: nine (radius, height) points for the full head and for the drinking layer, blended by `crown`, and a
// Catmull-Rom curve through them. Plain locals and an explicit segment pick: indexing points through int-parameter
// functions gave every middle point the last one in Godot 4.7.2 (a cone).
vec2 cr(vec2 p0, vec2 p1, vec2 p2, vec2 p3, float f) {
	return 0.5 * (2.0 * p1 + (p2 - p0) * f + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * f * f
			+ (3.0 * p1 - p0 - 3.0 * p2 + p3) * f * f * f);
}

vec2 profile(float t) {
	float ri = inner_r;
	float d = head_top - rim;
	float top = level + layer;
	float c = crown;
	vec2 q0 = vec2(ri, level);
	vec2 q1 = mix(vec2(ri, top - 0.002), vec2(ri, rim - 0.003), c);
	vec2 q2 = mix(vec2(ri * 0.985, top), vec2(mix(ri, rim_r, 0.45), rim + 0.0045), c);
	vec2 q3 = mix(vec2(ri * 0.94, top + 0.0012), vec2(rim_r - 0.0002, rim + 0.0016), c);
	vec2 q4 = mix(vec2(ri * 0.85, top + 0.0022), vec2(rim_r + 0.0004, rim + 0.0065), c);
	vec2 q5 = mix(vec2(ri * 0.70, top + 0.0045), vec2(rim_r - 0.0002, rim + d * 0.48), c);
	vec2 q6 = mix(vec2(ri * 0.48, top + 0.0058), vec2(rim_r * 0.80, rim + d * 0.80), c);
	vec2 q7 = mix(vec2(ri * 0.24, top + 0.0066), vec2(rim_r * 0.42, rim + d * 0.96), c);
	vec2 q8 = mix(vec2(0.0, top + 0.007), vec2(0.0, head_top), c);
	float u = clamp(t, 0.0, 1.0) * 8.0;
	vec2 r;
	if (u < 1.0) {
		r = cr(q0, q0, q1, q2, u);
	} else if (u < 2.0) {
		r = cr(q0, q1, q2, q3, u - 1.0);
	} else if (u < 3.0) {
		r = cr(q1, q2, q3, q4, u - 2.0);
	} else if (u < 4.0) {
		r = cr(q2, q3, q4, q5, u - 3.0);
	} else if (u < 5.0) {
		r = cr(q3, q4, q5, q6, u - 4.0);
	} else if (u < 6.0) {
		r = cr(q4, q5, q6, q7, u - 5.0);
	} else if (u < 7.0) {
		r = cr(q5, q6, q7, q8, u - 6.0);
	} else {
		r = cr(q6, q7, q8, q8, u - 7.0);
	}
	return r;
}

// the lumps along the profile's normal: none low on the side (the glass holds it), full on the crown
float lumps(float a, float t, vec2 p) {
	vec2 q = vec2(cos(a), sin(a));
	float big = vnoise(vec3(q * 1.6, p.y * 45.0 + 3.0));
	float mid = vnoise(vec3(q * 4.5 + 4.0, p.y * 130.0));
	float sml = vnoise(vec3(q * 11.0 + 9.0, p.y * 300.0));
	float on = smoothstep(rim - 0.006, rim + 0.002, p.y) * crown + (1.0 - crown) * smoothstep(0.1, 0.4, t) * 0.6;
	return lump * (1.0 * big + 0.45 * mid + 0.18 * sml) * on * (1.0 - smoothstep(0.86, 0.99, t));   // none at the pole: one vertex, one angle
}

vec3 pos(float a, float t) {
	vec2 p = profile(t);
	vec2 dp = profile(t + 0.004) - profile(t - 0.004);
	vec2 n = normalize(vec2(dp.y, -dp.x) + vec2(1e-6, 0.0));
	if (t > 0.995) {
		n = vec2(0.0, 1.0);
	}
	vec2 q = p + n * lumps(a, t, p);
	if (t < 0.001) {                                  // the ragged lower edge: up into the foam, never into the beer
		q.y += 0.0022 * (0.5 + 0.5 * vnoise(vec3(cos(a) * 5.0, sin(a) * 5.0, 3.0)));
	}
	q.x = max(q.x, 0.0);
	return vec3(cos(a) * q.x, q.y, sin(a) * q.x);
}

void vertex() {
	float a = atan(VERTEX.z, VERTEX.x);
	float t = 1.0 - UV.y;                          // glTF flips v: Blender's t comes in as 1 - t
	vec3 p = pos(a, t);
	vec3 du = pos(a + 0.01, t) - pos(a - 0.01, t);
	vec3 dv = pos(a, min(t + 0.006, 1.0)) - pos(a, max(t - 0.006, 0.0));
	vec3 n = normalize(cross(du, dv) + vec3(0.0, 1e-9, 0.0));
	vec2 dp = profile(t + 0.004) - profile(t - 0.004);
	vec3 outward = vec3(cos(a) * dp.y, -dp.x, sin(a) * dp.y);
	if (dot(n, outward) < 0.0) {
		n = -n;
	}
	if (t > 0.99) {
		n = normalize(mix(vec3(0.0, 1.0, 0.0), n, 0.3));
	}
	VERTEX = p;
	NORMAL = n;
	obj = p;
	hollow = clamp(0.5 + lumps(a, t, profile(t)) / (lump * 1.6), 0.0, 1.0);
}

vec3 h33(vec3 p) {
	p = vec3(dot(p, vec3(127.1, 311.7, 74.7)), dot(p, vec3(269.5, 183.3, 246.1)), dot(p, vec3(113.5, 271.9, 124.6)));
	return fract(sin(p) * 43758.5453);
}

vec2 worley(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	float d1 = 8.0;
	float d2 = 8.0;
	for (int z = -1; z <= 1; z++) {
		for (int y = -1; y <= 1; y++) {
			for (int x = -1; x <= 1; x++) {
				vec3 g = vec3(float(x), float(y), float(z));
				float d = length(g + h33(i + g) - f);
				if (d < d1) {
					d2 = d1;
					d1 = d;
				} else if (d < d2) {
					d2 = d;
				}
			}
		}
	}
	return vec2(d1, d2);
}

void fragment() {
	// under the rim the foam presses on the glass: bigger, flatter bubbles, a deeper cream
	float under = 1.0 - smoothstep(rim - 0.004, rim + 0.001, obj.y);
	float cell = mix(0.0028, 0.0026, under);
	vec3 p = obj / cell;
	vec2 w = worley(p);
	float wall = smoothstep(0.0, mix(0.32, 0.18, under), w.y - w.x);
	vec2 w2 = worley(p * 2.6 + 11.0);
	float fine = smoothstep(0.0, 0.25, w2.y - w2.x);
	vec3 cp = obj / 0.005 + 5.0;                       // a few craters on the crown: popped bubbles
	vec2 wc = worley(cp);
	float crater = (1.0 - smoothstep(0.08, 0.2, wc.x)) * step(0.82, h33(floor(cp)).x) * (1.0 - under);
	float cav = mix(mix(0.86, 0.86, under), 1.0, wall) * mix(0.95, 1.0, fine) * mix(0.72, 1.0, hollow) * (1.0 - 0.35 * crater);
	// a bubble pressed on the glass: a round lens, darker inside, a bright ring and a small highlight
	float lens = 1.0 - smoothstep(0.2, 0.42, w.x);
	float ringb = smoothstep(0.32, 0.4, w.x) * (1.0 - smoothstep(0.4, 0.5, w.x)) * 0.5;
	float glint = 1.0 - smoothstep(0.0, 0.09, length(fract(p) - vec3(0.35, 0.65, 0.5)));
	cav *= mix(1.0, 0.93, lens * under);
	vec2 e = vec2(0.15, 0.0);
	float gx = worley(p + e.xyy).x - w.x;
	float gy = worley(p + e.yxy).x - w.x;
	float gz = worley(p + e.yyx).x - w.x;
	vec3 gv = (VIEW_MATRIX * MODEL_MATRIX * vec4(gx, gy, gz, 0.0)).xyz;
	NORMAL = normalize(NORMAL - gv * mix(0.3, 0.4, under));
	float above = obj.y - level;                       // wet and beer-tinted over the beer, with a ragged boundary
	float rag = 0.003 * (0.5 + 0.5 * sin(atan(obj.z, obj.x) * 7.0 + obj.y * 400.0));
	float wetness = 1.0 - smoothstep(0.0, 0.006 + rag, above);
	vec3 col = mix(cream, pressed, under * 0.8);
	col = mix(col, wet, wetness * 0.8) * cav;
	col = mix(col * vec3(0.93, 0.86, 0.74), col, hollow);   // warm in the crevices between the lumps
	// the concept's head shades from v 1.0 on the crown to about 0.7 at its shoulder, and the foam in the glass goes
	// beer-tinted toward the beer (v 0.56, s 0.67 at the bottom)
	float crown_h = smoothstep(rim, rim + (head_top - rim) * 0.9, obj.y);
	col *= mix(0.74, 1.04, crown_h * crown + (1.0 - crown) * 0.8);
	float low = 1.0 - smoothstep(level, level + 0.012, obj.y);
	col = mix(col, vec3(0.62, 0.38, 0.16), low * 0.45 * under);
	ALBEDO = col;
	float sparkle = glint * lens * step(0.6, h33(floor(p)).y);                  // a wet glint on some bubbles
	EMISSION = col * glow + vec3(1.0, 0.6, 0.15) * wetness * 0.10 + vec3(1.0) * (ringb * 0.25 + glint * lens * 0.2) * under
			+ vec3(1.0, 0.97, 0.9) * sparkle * 0.35 * (1.0 - under);
	ROUGHNESS = mix(0.62, 0.3, wetness);
	SPECULAR = 0.35;
}
