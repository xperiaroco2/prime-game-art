shader_type spatial;
// The mug lab's glass (research, pipeline A, round 2): the one transparent surface. It draws what is behind it from
// the screen texture (the opaque pass: the beer, the foam, the room) shifted by its view-space normal, so every facet
// bends the beer differently; lighter and whiter where it is seen edge-on; stylised studio reflections in view space
// (a matcap-like rig: every facet catches a highlight from any side); a bright line along every crease (the grooves,
// the rim, the handle's edges) from the normal's screen-space change. Where nothing opaque is close behind it (an
// empty glass, the handle) it adds the far wall's highlights, faked with the mirrored normal: round 1's critics read
// those parts as black plastic. ALPHA 1: the shader composites itself; depth_draw_always keeps only the nearest glass
// surface. Lacing: thin rings and drips of foam on the body (never the handle) between the foam and where the head was.
render_mode blend_mix, cull_back, depth_draw_always;

uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform sampler2D depth_tex : hint_depth_texture;
uniform float refraction = 0.04;
uniform vec3 tint : source_color = vec3(0.93, 0.98, 0.97);
uniform float edge_pow = 2.5;
uniform float fresnel_white = 0.35;
uniform float streaks = 1.0;
uniform float crease = 0.9;                        // the crease lines' strength
uniform float far_wall = 0.55;                     // the faked far wall where the glass is empty behind
uniform vec3 body_col : source_color = vec3(0.10, 0.13, 0.14);   // the glass's own faint body (never pure black)
uniform float floor_y = 0.022;
uniform float body_r = 0.048;                      // the body's outer radius: the lacing stays inside it
uniform vec3 beer_col : source_color = vec3(1.0, 0.55, 0.12);
uniform float beer_in = 1.0;
uniform float lace_bottom = 0.15;
uniform float lace_top = 0.15;
uniform float lace_from = 0.126;                   // the full level: rings only below the rim, from the drinking
uniform float lace = 0.0;

varying vec3 obj;

void vertex() {
	obj = VERTEX;
}

float h21(vec2 p) {
	p = fract(p * vec2(234.34, 435.345));
	p += dot(p, p + 34.23);
	return fract(p.x * p.y);
}

float vn(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(h21(i), h21(i + vec2(1.0, 0.0)), f.x), mix(h21(i + vec2(0.0, 1.0)), h21(i + vec2(1.0, 1.0)), f.x), f.y);
}

vec3 studio(vec3 n, vec3 view) {
	vec3 r = reflect(-view, n);
	float s1 = smoothstep(0.16, 0.0, abs(r.x - 0.62)) * smoothstep(-0.7, 0.2, r.y);
	float s2 = smoothstep(0.10, 0.0, abs(r.x + 0.55)) * smoothstep(-0.4, 0.4, r.y) * 0.55;
	float s3 = smoothstep(0.55, 0.9, r.y) * 0.22;
	return vec3(1.0, 0.94, 0.86) * s1 * 1.6 + vec3(0.7, 0.85, 1.0) * (s2 + s3);
}

void fragment() {
	float facing = clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	float edge = pow(1.0 - facing, edge_pow);
	vec2 off = NORMAL.xy * refraction * (0.4 + 0.6 * (1.0 - facing));
	vec2 suv = SCREEN_UV - off;
	vec3 behind = textureLod(screen_tex, suv, 0.0).rgb;
	// how far behind this glass the opaque scene is: far (> 6 cm) means an empty inside or the room
	float d = textureLod(depth_tex, suv, 0.0).r;
	vec4 vp = INV_PROJECTION_MATRIX * vec4(suv * 2.0 - 1.0, d, 1.0);
	float gap = clamp((-vp.z / vp.w) - (-VERTEX.z), 0.0, 1.0);
	float empty = smoothstep(0.03, 0.08, gap);
	vec3 col = behind * tint + body_col * (0.15 + 0.5 * edge);
	col = mix(col, vec3(0.85, 0.92, 0.95), edge * fresnel_white);
	col += studio(NORMAL, VIEW) * streaks * (0.25 + 0.75 * edge);
	vec3 nf = vec3(-NORMAL.x, NORMAL.y, -NORMAL.z);  // the far wall faces the other way
	col += studio(nf, VIEW) * far_wall * empty * 0.5 + body_col * empty * 0.8;
	// crease lines: where the normal turns fast across the screen
	float k = length(fwidth(NORMAL));
	col += vec3(0.95, 0.97, 1.0) * crease * smoothstep(0.12, 0.45, k);
	// the heavy base: an amber tint from the beer above, not a slab
	float base = 1.0 - smoothstep(floor_y * 0.4, floor_y, obj.y);
	col += beer_col * base * beer_in * 0.08 + vec3(0.06, 0.08, 0.09) * base;   // clear heavy glass, amber-tinged
	// lacing: thin broken rings at a few old levels and short drips, soft, on the body only
	float rad = length(obj.xz);
	float ang = atan(obj.z, obj.x);
	float band = smoothstep(lace_bottom, lace_bottom + 0.004, obj.y) * (1.0 - smoothstep(lace_top - 0.004, lace_top, obj.y));
	band *= step(rad, body_r) * step(obj.y, lace_from + 0.02);
	// a few irregular rings (one every ~1.2 cm, each wavy and broken into arcs) and rare short drips under them
	float yy = obj.y * 85.0 + (vn(vec2(ang * 3.0, 2.0)) - 0.5) * 0.9;
	float cell = floor(yy);
	float keep = step(0.45, h21(vec2(cell, 5.0)));                      // not every level left a ring
	float thin = smoothstep(0.16, 0.0, abs(fract(yy) - 0.5) - 0.03 * vn(vec2(ang * 30.0, cell))) * (0.55 + 0.45 * vn(vec2(ang * 120.0, obj.y * 900.0)));
	float ring = thin * keep * smoothstep(0.4, 0.7, vn(vec2(ang * 9.0, cell * 3.1)));
	float drip = smoothstep(0.95, 1.0, vn(vec2(ang * 55.0, cell))) * smoothstep(0.5, 0.2, fract(yy)) * keep;
	float trace = clamp(ring + drip * 0.6, 0.0, 1.0) * band * lace;
	col = mix(col, vec3(0.93, 0.91, 0.86), trace * 0.3);
	ALBEDO = vec3(0.0);
	EMISSION = col;
	ROUGHNESS = 0.03;
	SPECULAR = 0.65;
	ALPHA = 1.0;
}
