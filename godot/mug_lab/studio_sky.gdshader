shader_type sky;
// The mug lab's reflection room (research): a dark room in the lobby's colours with a warm panel overhead, a big
// cold window on one side and thin strip lights, for the glass to mirror. Only for reflections and ambient light.

uniform vec3 room : source_color = vec3(0.045, 0.06, 0.075);
uniform vec3 warm : source_color = vec3(1.0, 0.78, 0.52);
uniform vec3 cold : source_color = vec3(0.45, 0.68, 1.0);
uniform float warm_energy = 5.0;
uniform float cold_energy = 3.0;
uniform float strip_energy = 6.0;

float box(vec2 p, vec2 c, vec2 h, float soft) {
	vec2 d = abs(p - c) - h;
	return 1.0 - smoothstep(0.0, soft, max(d.x, d.y));
}

void sky() {
	vec3 d = EYEDIR;
	vec3 col = room * (0.6 + 0.4 * clamp(d.y + 0.3, 0.0, 1.0));
	float az = atan(d.x, -d.z);
	float el = asin(clamp(d.y, -1.0, 1.0));
	col += warm * warm_energy * box(vec2(d.x, d.z), vec2(-0.1, 0.25), vec2(0.35, 0.22), 0.08) * step(0.0, d.y);
	col += cold * cold_energy * box(vec2(az, el), vec2(-1.7, 0.15), vec2(0.6, 0.35), 0.06);
	col += warm * strip_energy * box(vec2(az, el), vec2(1.4, 0.35), vec2(0.5, 0.012), 0.01);
	col += cold * strip_energy * 0.7 * box(vec2(az, el), vec2(2.8, 0.05), vec2(0.4, 0.01), 0.01);
	COLOR = col;
}
