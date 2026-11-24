// The M8 clearing's ground (prime-game#1704; the landing pad approved by the engineer 2026-11-24, art#263): one
// procedural material for the clearing's 200 x 200 m ground, no texture reads. `pad` off: dark blue-grey regolith with
// gravel and sparse teal glints (look B, not picked). `pad` on: a round pad of dark cold-steel plates round the ship's
// centre, hazard chevrons in front of the ramp's foot and a thin teal light ring at its edge, the regolith beyond
// (look A, the game's: assets/environment/clearing_ground). World xz drives everything, so the mesh needs no UVs; the
// pad is placed by `centre` (the ship's origin in the world) and assumes the ship unrotated, its ramp toward -z.
// Kept byte-identical with assets/environment/clearing_ground/export/clearing_ground.gdshader (a test checks it).
shader_type spatial;
render_mode cull_back;

uniform bool pad = false;
uniform vec2 centre = vec2(116.0, 72.0);    // the ship's origin (clearing.tscn's Ship)
uniform float pad_r = 18.0;                  // the pad's radius: the ten spawns are at most 15.2 m out
uniform float ramp_foot = 12.6;              // the ramp's foot, metres in front of the centre (-z)
uniform vec3 ring_glow : source_color = vec3(0.16, 0.86, 0.92);
uniform float ring_energy = 1.6;
uniform vec3 glint_glow : source_color = vec3(0.2, 0.9, 0.95);
uniform float glint_energy = 1.2;
uniform float glint_share = 0.03;            // the share of stones that glint

varying vec3 wp;

float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

vec2 hash22(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.xx + p3.yz) * p3.zy);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), u.x),
			mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
	float s = 0.0;
	float a = 0.5;
	mat2 m = mat2(vec2(1.6, 1.2), vec2(-1.2, 1.6));
	for (int i = 0; i < 4; i++) {
		s += a * vnoise(p);
		p = m * p;
		a *= 0.5;
	}
	return s;
}

// nearest feature point: x its distance (cells), y its cell's hash, zw its offset from p (cells)
vec4 voronoi(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec4 best = vec4(8.0, 0.0, 0.0, 0.0);
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 g = vec2(float(x), float(y));
			vec2 o = 0.15 + 0.7 * hash22(i + g);
			vec2 r = g + o - f;
			float d = dot(r, r);
			if (d < best.x) {
				best = vec4(d, hash12(i + g + 17.0), r);
			}
		}
	}
	best.x = sqrt(best.x);
	return best;
}

void vertex() {
	wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = wp.xz;
	float dist = length(VERTEX);
	// detail fades where a gravel cell gets under about two pixels, so nothing shimmers far off
	float gscale = 7.0;
	float detail = 1.0 - smoothstep(0.25, 0.6, length(fwidth(p * gscale)));

	// --- the regolith (look B, and look A beyond the pad): tone patches at 25 m, 4 m and 0.5 m, a fine grain, and
	// stones in some cells only, denser in gravel patches; their normals come from the domes' own slopes (no bump
	// from screen derivatives, which showed the 2 x 2 pixel quads)
	float macro = fbm(p * 0.04);
	float mid = fbm(p * 0.25 + 7.1);
	float small = vnoise(p * 2.1 + 3.3);
	float grain = vnoise(p * 23.0) * 0.6 + vnoise(p * 61.0) * 0.4;
	float tone = smoothstep(0.3, 0.7, macro * 0.65 + mid * 0.25 + small * 0.1);
	vec3 col = mix(vec3(0.052, 0.06, 0.076), vec3(0.22, 0.235, 0.262), tone);
	col *= mix(vec3(1.0), vec3(0.9, 0.97, 1.1), smoothstep(0.35, 0.65, fbm(p * 0.09 + 3.0)));
	col *= 0.86 + 0.28 * mix(0.5, grain, detail);
	float gravel = smoothstep(0.35, 0.75, fbm(p * 0.5 + 21.0));            // where the gravel lies thick
	col *= mix(1.0, 0.78, gravel);                                         // the gravel patches darker
	vec4 v = voronoi(p * gscale);
	float size = 0.18 + 0.22 * fract(v.y * 13.7);                          // the stone's radius, cells
	float has = step(fract(v.y * 7.31), mix(0.18, 0.85, gravel));
	float stone = has * (1.0 - smoothstep(size - 0.04, size, v.x)) * detail;
	float shade = 0.5 + 0.65 * fract(v.y * 3.17);
	col = mix(col, col * shade * (1.0 + 0.25 * (1.0 - v.x / size)), stone * 0.8);
	vec2 slope = stone * 0.9 * v.zw / size;                                // the dome leans away from its centre
	float rough = 0.93 - stone * 0.1;
	float metal = 0.0;
	vec3 glow = vec3(0.0);
	// a teal mineral fleck on a few stones, small, fading out by 20 m
	float fleck = has * step(1.0 - glint_share, fract(v.y * 91.7)) * (1.0 - smoothstep(0.05, 0.09, v.x))
			* (1.0 - smoothstep(9.0, 20.0, dist)) * detail;
	glow += glint_glow * glint_energy * fleck;
	col = mix(col, glint_glow * 0.25, fleck);

	if (pad) {
		vec2 q = p - centre;
		float r = length(q);
		float aa = fwidth(r);
		if (r < pad_r + 0.2) {
			// plates in offset rows, 2.4 x 1.6 m, aligned with the ship
			vec2 cell = vec2(2.4, 1.6);
			vec2 s = q / cell;
			float row = floor(s.y);
			s.x += mod(row, 2.0) * 0.5;
			vec2 id = floor(s);
			vec2 f = (fract(s) - 0.5) * cell;          // metres from the plate's centre
			vec2 e = cell * 0.5 - abs(f);                // metres to the plate's edges
			float edge = min(e.x, e.y);
			float seam = 1.0 - smoothstep(0.008, 0.008 + fwidth(edge) * 1.5, edge);
			float ptone = hash12(id + 5.0);
			vec3 steel = vec3(0.2, 0.225, 0.25) * (0.82 + 0.3 * ptone);
			float scuff = fbm(p * 2.3 + id * 3.1);
			steel *= 0.88 + 0.2 * scuff;
			steel = mix(steel, col * 0.9, smoothstep(0.55, 0.85, macro) * 0.35);   // regolith blown over the plates
			// four bolts per plate, 0.12 m in from the corners
			vec2 b = abs(f) - (cell * 0.5 - 0.12);
			float bolt = 1.0 - smoothstep(0.022, 0.022 + fwidth(length(b)) * 1.5, length(b));
			steel = mix(steel, steel * 1.35, bolt);
			// the edge: a 0.5 m trim band of radial segments, and the light strip in a dark channel
			float band = smoothstep(pad_r - 0.55 - aa, pad_r - 0.55, r);
			float seg = abs(fract(atan(q.y, q.x) / 6.28318 * 96.0) - 0.5) * 6.28318 / 96.0 * r;
			float segseam = 1.0 - smoothstep(0.008, 0.008 + fwidth(seg) * 1.5, seg);
			vec3 trim = vec3(0.13, 0.145, 0.165) * (0.9 + 0.2 * scuff);
			float channel = 1.0 - smoothstep(0.07, 0.07 + aa, abs(r - (pad_r - 0.25)));
			float strip = 1.0 - smoothstep(0.025, 0.025 + aa, abs(r - (pad_r - 0.25)));
			vec3 pcol = mix(steel, trim, band);
			float pseam = mix(seam, segseam, band);
			pcol = mix(pcol, vec3(0.02, 0.022, 0.026), max(pseam, channel * 0.9));
			// four hazard chevrons in front of the ramp's foot, as wide as the ramp, pointing at the ship, the paint
			// scratched and dulled by the regolith
			vec2 c = vec2(q.x, q.y + ramp_foot + 0.5);  // 0 at 0.5 m in front of the foot
			float inbox = step(abs(q.x), 1.6) * step(-1.7, c.y) * step(c.y, 0.0);
			float chev = step(0.55, fract((c.y + abs(q.x) * 0.6) / 0.42));
			float wear = smoothstep(0.25, 0.4, vnoise(p * 9.0) * 0.5 + vnoise(p * 31.0) * 0.5);
			vec3 paint = vec3(0.46, 0.42, 0.17);
			float painted = inbox * chev * mix(0.45, 1.0, wear) * (1.0 - seam);
			pcol = mix(pcol, paint, painted);
			float inpad = 1.0 - smoothstep(pad_r - aa, pad_r, r);
			// a dark gap of 0.1 m where the regolith meets the pad's rim
			float gap = (1.0 - smoothstep(0.1, 0.1 + aa, r - pad_r)) * (1.0 - inpad);
			col = mix(col, pcol, inpad);
			col = mix(col, vec3(0.03, 0.033, 0.038), gap);
			slope *= 1.0 - inpad;
			rough = mix(rough, mix(mix(0.42 + 0.25 * scuff, 0.6, band), 0.7, painted), inpad);
			metal = mix(metal, mix(0.6, 0.5, band) * (1.0 - painted), inpad);
			glow = mix(glow, ring_glow * ring_energy * strip, inpad);
		}
	}

	vec3 n = normalize(vec3(-slope.x, 1.0, -slope.y));
	NORMAL = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);
	ALBEDO = col;
	ROUGHNESS = rough;
	METALLIC = metal;
	EMISSION = glow;
}
