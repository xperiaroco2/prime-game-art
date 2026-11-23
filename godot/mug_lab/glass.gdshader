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
uniform float refraction = 0.05;
uniform vec3 tint : source_color = vec3(0.99, 0.96, 0.9);   // a faint warm amber, as the concept's glass
uniform float edge_pow = 2.5;
uniform float fresnel_white = 0.1;                 // round 7: a white edge read as a sticker halo
uniform float streaks = 0.6;
uniform float crease = 0.9;                        // the crease lines' strength
uniform float far_wall = 0.55;                     // the faked far wall where the glass is empty behind
uniform vec3 body_col : source_color = vec3(0.06, 0.08, 0.08);   // the glass's own faint body (never pure black)
uniform vec3 thick_col : source_color = vec3(0.22, 0.42, 0.38);  // thick glass seen edge-on: a deep green-teal
uniform float smooth_refr = 0.35;                   // refraction from the smooth radial normal: no seams between facets
uniform float floor_y = 0.022;
uniform float body_r = 0.048;                      // the body's outer radius: the lacing stays inside it
uniform vec3 beer_col : source_color = vec3(1.0, 0.55, 0.12);
uniform vec3 beer_col_hi : source_color = vec3(0.95, 0.56, 0.01);
uniform float beer_in = 1.0;
uniform float level = 0.126;                       // the beer's level: the base shows beer only while some is above it
uniform float lace_bottom = 0.15;
uniform float lace_top = 0.15;
uniform float lace_from = 0.126;                   // the full level: rings only below the rim, from the drinking
uniform float lace = 0.0;
// round 12: the Cycles bake on the glass's UVs (mug_lab_bake.py): R thickness, G edges, B studio light; baked 0: off
uniform sampler2D glass_map : hint_default_black, filter_linear_mipmap, repeat_disable;
uniform float baked = 0.0;
uniform float bake_thick = 0.9;                    // how far thick glass shifts toward thick_col
uniform float bake_edge = 0.9;                     // the baked ridges' brightness
uniform float bake_light = 0.55;                   // the baked light shapes' brightness
uniform vec3 bake_light_col : source_color = vec3(1.0, 0.93, 0.82);

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
	vec3 radial = normalize((VIEW_MATRIX * MODEL_MATRIX * vec4(obj.x, 0.0, obj.z, 0.0)).xyz + vec3(0.0, 0.0, 1e-5));
	vec3 rn = normalize(mix(NORMAL, radial, smooth_refr));
	float d0 = textureLod(depth_tex, SCREEN_UV, 0.0).r;
	vec4 vp0 = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, d0, 1.0);
	float empty0 = smoothstep(0.03, 0.08, clamp((-vp0.z / vp0.w) - (-VERTEX.z), 0.0, 1.0));
	vec2 off = rn.xy * refraction * (0.4 + 0.6 * (1.0 - facing)) * (1.0 + 0.6 * empty0) * smoothstep(0.02, 0.25, facing);   // round 14: milder, none at grazing angles (round 13 shattered the flute tops)
	// the heavy base shows the beer above it, bent down through the thick glass: sample the screen higher up there
	float base = 1.0 - smoothstep(floor_y * 0.55, floor_y * 1.05, obj.y);
	// how far up the screen the beer is: project a point 4.5 cm above this one (object up), so the shift follows the
	// mug's size in the frame (Vulkan NDC and SCREEN_UV share their y direction)
	vec3 up_v = (VIEW_MATRIX * MODEL_MATRIX * vec4(0.0, 0.045, 0.0, 0.0)).xyz;
	vec4 c0 = PROJECTION_MATRIX * vec4(VERTEX, 1.0);
	vec4 c1 = PROJECTION_MATRIX * vec4(VERTEX + up_v, 1.0);
	vec2 dn = (c1.xy / c1.w - c0.xy / c0.w) * 0.5;
	vec2 suv = SCREEN_UV - off + dn * base * beer_in * clamp((level - floor_y - 0.006) / 0.045, 0.0, 1.0);   // Vulkan NDC y already points down the screen
	vec3 behind = textureLod(screen_tex, suv, 0.0).rgb;
	vec3 plain = textureLod(screen_tex, SCREEN_UV - off, 0.0).rgb;
	behind = mix(behind, mix(plain, behind, 0.4) + vec3(0.06, 0.05, 0.03), base);   // round 9: a clear base with a warm caustic, not a pool of beer
	// how far behind this glass the opaque scene is: far (> 6 cm) means an empty inside or the room
	float d = textureLod(depth_tex, suv, 0.0).r;
	vec4 vp = INV_PROJECTION_MATRIX * vec4(suv * 2.0 - 1.0, d, 1.0);
	float gap = clamp((-vp.z / vp.w) - (-VERTEX.z), 0.0, 1.0);
	float empty = smoothstep(0.03, 0.08, gap);
	float body = step(0.029, obj.y) * step(obj.y, min(0.123, level - 0.002)) * step(length(obj.xz), 0.0475) * beer_in;
	vec3 gm = texture(glass_map, UV).rgb * baked;     // thickness, edges, baked light
	float absorb = max(smoothstep(0.25, 0.85, 1.0 - facing) * 0.75, gm.r * bake_thick);
	vec3 col = behind * mix(tint, thick_col, absorb) + body_col * (0.15 + 0.5 * edge) * (1.0 - body * 0.85);
	col = mix(col, vec3(0.85, 0.92, 0.95), pow(1.0 - facing, 5.0) * fresnel_white);
	vec3 key_v = normalize((VIEW_MATRIX * vec4(-0.45, 0.6, 0.65, 0.0)).xyz);
	col *= mix(0.78, 1.18, clamp(dot(NORMAL, key_v) * 0.5 + 0.5, 0.0, 1.0));
	// every panel is a lens: bright through its middle, darker toward its grooves (the concept's alternating panels)
	col *= mix(1.0, mix(0.85, 1.0, pow(facing, 1.6)), body);
	// each panel is a lens that gathers the light through the beer: a saturated gold glow down its middle (the
	// concept's bright panels: 242,151,2), the beer between them dark amber
	float lensv = pow(clamp(dot(NORMAL, VIEW), 0.0, 1.0), 9.0);
	col += beer_col_hi * lensv * body * 1.3;
	col *= mix(1.0, 0.7, edge);                       // thick glass darkens toward the silhouette
	col += studio(NORMAL, VIEW) * streaks * (0.4 + 0.3 * edge);
	vec3 nf = vec3(-NORMAL.x, NORMAL.y, -NORMAL.z);  // the far wall faces the other way
	col += studio(nf, VIEW) * far_wall * empty * 0.7 + body_col * empty * 1.2;
	// crease lines: where the normal turns fast across the screen
	float k = length(fwidth(NORMAL));
	col += vec3(0.95, 0.97, 1.0) * crease * smoothstep(0.12, 0.45, k) * (1.0 - edge) * (1.0 - baked);
	// baked: crisp ridges where the geometry turns, and the studio's light shapes as Cycles lit them
	// a ridge lights only where the studio's light falls on it (g2: an even white rim on every edge read as an outline)
	vec3 st = studio(NORMAL, VIEW);
	col += vec3(0.95, 0.97, 1.0) * bake_edge * gm.g * clamp(dot(st, vec3(0.33)) * 1.4, 0.0, 1.0);
	col *= mix(1.0, 0.7, gm.g * (1.0 - clamp(dot(st, vec3(0.33)) * 1.4, 0.0, 1.0)));   // the unlit ridges darken
	col += bake_light_col * bake_light * gm.b * gm.b;
	col += vec3(0.05, 0.06, 0.06) * base;
	// lacing: thin broken rings at a few old levels and short drips, soft, on the body only
	float rad = length(obj.xz);
	float ang = atan(obj.z, obj.x);
	float band = smoothstep(lace_bottom, lace_bottom + 0.004, obj.y) * (1.0 - smoothstep(lace_top - 0.004, lace_top, obj.y));
	band *= step(rad, body_r) * step(obj.y, lace_from + 0.02);
	// lacing: a few broken arcs at old levels, denser toward the rim where the head was, made of small bubbles, and a
	// short drip under some (round 5: even full rings read as stitching)
	float yy = obj.y * 55.0 + (vn(vec2(ang * 2.5, 2.0)) - 0.5) * 1.2;
	float cell = floor(yy);
	float near_top = smoothstep(lace_from - 0.05, lace_top, obj.y);
	float keep = step(mix(0.7, 0.25, near_top), h21(vec2(cell, 5.0)));
	float arc = smoothstep(0.35, 0.6, vn(vec2(ang * 1.6 + cell * 7.0, cell)));            // only part of the way round
	float w = 0.09 + 0.14 * vn(vec2(ang * 7.0, cell * 3.1));
	float dots = smoothstep(0.35, 0.9, vn(vec2(ang * 260.0, obj.y * 2600.0))) + 0.35 * smoothstep(0.5, 0.8, vn(vec2(ang * 110.0, obj.y * 1100.0)));
	float ring = smoothstep(w, w * 0.2, abs(fract(yy) - 0.5 + 0.15 * (vn(vec2(ang * 12.0, cell)) - 0.5))) * keep * arc * clamp(dots, 0.0, 1.0);
	float drip = smoothstep(0.9, 1.0, vn(vec2(ang * 30.0, cell))) * smoothstep(0.5, 0.15, fract(yy)) * keep * arc * 0.7;
	float trace = clamp(ring + drip * 0.6, 0.0, 1.0) * band * lace;
	col = mix(col, vec3(0.9, 0.88, 0.82), trace * 0.2 * mix(0.7, 1.0, near_top));
	ALBEDO = vec3(0.0);
	EMISSION = col;
	ROUGHNESS = 0.03;
	SPECULAR = 0.3;                                   // round 14: half the environment reflection (critics: chrome)                                   // round 11: stronger reflections of the room (the probe)
	ALPHA = 1.0;
}
