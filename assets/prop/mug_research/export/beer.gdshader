shader_type spatial;
// The mug lab's beer (research, pipeline A): an opaque liquid cut at a fill level. Cull disabled: where the cut
// opens the cylinder, its back faces show through and are drawn as the flat surface (the liquid-in-a-mesh trick).
// Opaque on purpose: the glass is the only transparent surface, so nothing sorts wrong, and the glass's refraction
// (the screen texture) sees the beer.
render_mode cull_disabled, diffuse_lambert_wrap;

uniform float level = 0.126;                       // the surface, object-space metres
uniform vec3 deep : source_color = vec3(0.5, 0.25, 0.02);   // round 10: measured on the concept: dark amber, s 0.99, v 0.33
uniform vec3 bright : source_color = vec3(0.95, 0.56, 0.01);   // the concept's bright beer: 242,151,2
uniform vec3 surface_col : source_color = vec3(0.98, 0.78, 0.38);
uniform float glow = 0.16;                         // the light the beer passes on (a faked transmission)
uniform float bubbles = 1.0;
uniform float bubble_speed = 0.035;                // m/s
uniform float inner_r = 0.0381;

varying vec3 obj;

void vertex() {
	obj = VERTEX;
}

float h21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float bubble_mask(vec3 o) {
	float r = length(o.xz);
	float ang = atan(o.z, o.x);
	float cols = 140.0;
	float u = (ang / 6.2831853 + 0.5) * cols;
	float col = floor(u);
	float sp = bubble_speed * (0.6 + 0.8 * h21(vec2(col, 3.1)));
	float cell = 0.007;
	float y = (o.y - TIME * sp) / cell;
	float row = floor(y);
	float on = step(0.64, h21(vec2(col, row))) * step(0.35, h21(vec2(col, 9.7)));   // some columns stream, most rest
	vec2 c = vec2(0.3 + 0.4 * h21(vec2(row, col)), 0.5);
	vec2 f = vec2(fract(u), fract(y));
	vec2 d = (f - c) * vec2(6.2831853 * r / cols, cell);   // cells in metres, so the dots stay round
	float rad = 0.00014 + 0.0003 * pow(h21(vec2(col + 7.0, row)), 2.0);
	return on * smoothstep(rad, rad * 0.1, length(d)) * 0.8;
}

void fragment() {
	if (obj.y > level) {
		discard;
	}
	if (FRONT_FACING) {
		float facing = clamp(dot(NORMAL, VIEW), 0.0, 1.0);
		vec3 col = mix(deep, bright, pow(smoothstep(0.2, 1.0, facing), 3.0) * 0.55);   // mostly dark amber; the glass's panel lenses add the gold
		col *= mix(0.85, 1.12, smoothstep(0.03, level, obj.y));        // lit from above through the foam

		float under = smoothstep(level - 0.012, level - 0.002, obj.y);  // a lit band just under the surface
		col = mix(col, surface_col, under * 0.45);
		float men = smoothstep(level - 0.0012, level - 0.0002, obj.y);   // the meniscus: a thin bright line at the top
		col += vec3(1.0, 0.85, 0.5) * men * 0.0;
		if (obj.y < 0.0235) {                                               // the bottom, seen through the heavy base: lit
			col = bright * 0.9;
		}
		float b = bubble_mask(obj) * bubbles;
		ALBEDO = col * 0.1;    // round 8: AgX washes a bright amber out; a darker beer keeps its gold
		EMISSION = col * glow + vec3(1.0, 0.85, 0.55) * b * 0.9;
		ROUGHNESS = 0.12;
		SPECULAR = 0.4;
	} else {
		// the surface: flat, facing up, a little brighter at the wall (the meniscus)
		NORMAL = normalize((VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
		float rim = smoothstep(inner_r - 0.004, inner_r, length(obj.xz));
		vec3 col = mix(surface_col * 0.8, vec3(1.0, 0.9, 0.7), rim * 0.6);
		ALBEDO = col * 0.4;
		EMISSION = col * glow * 0.7;
		ROUGHNESS = 0.04;
		SPECULAR = 0.6;
	}
}
