shader_type spatial;
// The mug lab's foam (research, pipeline A, round 2): ONE volume from the beer's surface up, shaped here from the
// fill. The mesh is canonical (mug_lab_build.py foam_unit: UV.x the dome's share from its edge to its pole, UV.y the
// side's share from the bottom); the vertex stage puts its side from `level` to `top`, swells it over the rim where
// it passes the rim (the head that overhangs the lip), domes it by `dome_h`, and makes the crown and the lower edge
// lumpy. Round 1's critics read a separate head and layer as a lid on a strip. Opaque, soft wrap lighting, small
// bubble cells from 3D Worley noise in object space; wetter and darker where it meets the beer.
render_mode diffuse_lambert_wrap;

uniform float level = 0.126;
uniform float top = 0.153;
uniform float dome_h = 0.03;
uniform float inner_r = 0.0381;
uniform float rim = 0.15;
uniform float rim_r = 0.045;
uniform float swell = 1.0;                         // flush with the rim's outer edge (round 2: wider read as a lid)                       // the head's radius over the rim, as a share of rim_r
uniform float lump = 0.0045;                       // m: the crown's lumps
uniform float edge_lump = 0.0025;                  // m: how ragged the lower edge is
uniform vec3 cream : source_color = vec3(0.97, 0.93, 0.84);
uniform vec3 shade : source_color = vec3(0.80, 0.66, 0.46);
uniform float cell_size = 0.0016;
uniform float bump = 0.3;
uniform float glow = 0.12;

varying vec3 obj;
varying float above;                               // height over the beer's surface (m)
varying float hollow;                              // 0 in a lump's crevice, 1 on its crown (for the shading)

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

float fbm(vec3 p) {
	return 0.6 * vnoise(p) + 0.3 * vnoise(p * 2.3 + 7.1) + 0.1 * vnoise(p * 5.1 + 3.7);
}

float radius_at(float y) {
	return mix(inner_r, rim_r * swell, smoothstep(rim - 0.002, rim + 0.0025, y));
}

void vertex() {
	float a = atan(VERTEX.z, VERTEX.x);
	vec2 dir = vec2(cos(a), sin(a));
	float s = UV.x;
	float t = UV.y;
	float y;
	float r;
	vec2 n2;                                       // the normal in (radial, up)
	float rt = radius_at(top);
	if (s < 0.0005) {
		y = mix(level, top, t);
		r = radius_at(y);
		if (t < 0.001) {                           // the ragged lower edge: up into the foam, never into the beer
			y += edge_lump * (0.5 + 0.5 * vnoise(vec3(dir * 5.0, 3.0)));
		}
		n2 = vec2(1.0, 0.0);
	} else {
		float phi = s * 1.5707963;
		r = rt * pow(cos(phi), 0.45);                  // a cushion: a round shoulder, a broad, flatter crown
		y = top + dome_h * pow(sin(phi), 0.7);
		n2 = normalize(vec2(dome_h * cos(phi), rt * sin(phi)));
	}
	// lumps on the crown and the head's overhang: none low on the side, where the glass holds the foam
	float on = smoothstep(rim - 0.004, rim + 0.004, y) + (s > 0.0005 ? 1.0 : 0.0);
	on = clamp(on, 0.0, 1.0);
	// big lobes round the head (a few per turn), mid clumps, and the crown's own rise and dips
	float big = fbm(vec3(dir * 1.7, y * 40.0 + 2.0));
	float mid = fbm(vec3(dir * 5.5 + 4.0, y * 150.0));
	float crown = fbm(vec3(dir * 2.2 + 9.0, s * 2.5));
	r += lump * (1.1 * big + 0.45 * mid) * on;
	float sv = s > 0.0005 ? sqrt(s) : 0.0;
	y += lump * (1.2 * crown + 0.4 * mid) * sv;
	hollow = clamp(0.5 + 0.9 * (0.7 * big + 0.5 * mid), 0.0, 1.0);
	VERTEX = vec3(dir.x * r, y, dir.y * r);
	NORMAL = normalize(vec3(dir.x * n2.x, n2.y, dir.y * n2.x));
	obj = VERTEX;
	above = y - level;
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
	vec3 p = obj / cell_size;
	vec2 w = worley(p);
	float wall = smoothstep(0.0, 0.35, w.y - w.x);
	vec2 w2 = worley(p * 2.7 + 11.0);
	float fine = smoothstep(0.0, 0.25, w2.y - w2.x);
	float cav = mix(0.88, 1.0, wall) * mix(0.95, 1.0, fine) * mix(0.72, 1.0, smoothstep(0.1, 0.7, hollow));
	vec2 e = vec2(0.15, 0.0);
	float gx = worley(p + e.xyy).x - w.x;
	float gy = worley(p + e.yxy).x - w.x;
	float gz = worley(p + e.yyx).x - w.x;
	vec3 gv = (VIEW_MATRIX * MODEL_MATRIX * vec4(gx, gy, gz, 0.0)).xyz;
	NORMAL = normalize(NORMAL - gv * bump);
	// wet and beer-tinted where it meets the beer, creamy above: a soft gradient, not a cut
	float wet = 1.0 - smoothstep(0.0, 0.009, above);
	vec3 col = mix(cream, shade, wet * 0.75) * cav;
	ALBEDO = col;
	EMISSION = col * glow + vec3(1.0, 0.6, 0.15) * wet * 0.12;
	ROUGHNESS = mix(0.6, 0.3, wet);
	SPECULAR = 0.35;
}
