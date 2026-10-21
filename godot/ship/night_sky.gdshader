// The clearing's night sky (art #263, docs/ship.md): a deep blue gradient, a faint horizon glow, stars that thin out
// toward the horizon and the moon with its halo in the moonlight's direction (LIGHT0, the DirectionalLight3D).
shader_type sky;

uniform vec3 zenith : source_color = vec3(0.008, 0.012, 0.04);
uniform vec3 horizon : source_color = vec3(0.04, 0.06, 0.12);
uniform vec3 below : source_color = vec3(0.01, 0.012, 0.018);
uniform float star_density : hint_range(0.0, 0.05) = 0.018;
uniform float star_energy = 2.2;
uniform vec3 moon_color : source_color = vec3(0.95, 0.96, 1.0);
uniform float moon_size_deg = 2.2;
uniform float moon_energy = 6.0;

float hash3(vec3 p) {
	return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453);
}

void sky() {
	vec3 d = normalize(EYEDIR);
	float up = d.y;
	vec3 col = mix(horizon, zenith, pow(clamp(up, 0.0, 1.0), 0.45));
	if (up < 0.0) {
		col = mix(horizon * 0.6, below, clamp(-up * 6.0, 0.0, 1.0));
	}
	if (!AT_CUBEMAP_PASS && up > 0.02) {
		vec3 p = d * 260.0;
		vec3 c = floor(p);
		float r = hash3(c);
		if (r > 1.0 - star_density) {
			vec3 o = vec3(hash3(c + 1.3), hash3(c + 4.1), hash3(c + 7.9)) * 0.6 + 0.2;
			float s = 1.0 - smoothstep(0.0, 0.22, length(fract(p) - o));
			float tw = 0.4 + 0.6 * hash3(c + 2.7);
			col += vec3(0.85, 0.9, 1.0) * s * tw * star_energy * smoothstep(0.02, 0.25, up);
		}
	}
	if (LIGHT0_ENABLED) {
		float m = dot(d, LIGHT0_DIRECTION);
		float edge = cos(radians(moon_size_deg * 0.5));
		float disc = smoothstep(edge - 0.00002, edge + 0.00002, m);
		col += moon_color * moon_energy * disc;
		col += moon_color * (pow(max(m, 0.0), 900.0) * 0.6 + pow(max(m, 0.0), 40.0) * 0.06);
	}
	COLOR = col;
}
