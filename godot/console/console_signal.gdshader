// The start console's signal lights (console.gd): mode 0 the three stage strips, one bar filled from max(`passed` / 3,
// `charge`) (strip k is its k-th third; UV0 u the share across a strip, left to right; the lit part `fill_colour`
// with a white head where it is filling, the rest a dim white), mode 1 the hologram's eight order lamps (each its
// colour by index mod 4, from the hall outward red, yellow, green, blue; the lamp `lit` bright, the others dimmed
// while the order plays). The strip's or lamp's index is the build's UV0 v (glTF flips v: index = 1 - UV.y).
shader_type spatial;
render_mode unshaded, cull_back;

uniform int mode = 0;
uniform float passed = 1.0;      // the stages passed (set_passed: the review states); the strips show at least this
uniform float charge = 0.0;      // the spin-up's bar 0..1 (set_charge; the ring shows it alone)
uniform vec3 fill_colour = vec3(0.02, 1.0, 0.1);
uniform float head = 0.0;        // the white head's strength at the filling edge (0 in step 1's green look)
uniform float lit = -1.0;
uniform float order = 0.0;
uniform float strip_on = 1.1;
uniform float strip_off = 0.45;
uniform float lamp_dim = 2.5;
uniform float lamp_lit = 12.0;

const vec3 WHITE = vec3(0.85, 0.9, 1.0);

vec3 lamp_colour(int k) {
	if (k == 0) {
		return vec3(1.0, 0.05, 0.03);
	} else if (k == 1) {
		return vec3(1.0, 0.72, 0.02);
	} else if (k == 2) {
		return vec3(0.08, 1.0, 0.15);
	}
	return vec3(0.05, 0.3, 1.0);
}

void fragment() {
	float idx = 1.0 - UV.y;
	vec3 col;
	float e;
	if (mode == 0) {
		float bar = max(clamp(passed, 0.0, 3.0) / 3.0, charge);
		float fill = clamp(bar * 3.0 - round(idx), 0.0, 1.0);
		float on = (fill >= 0.999 || UV.x < fill) ? 1.0 : 0.0;
		float tip = (fill > 0.0 && fill < 0.999) ? on * exp(-max(fill - UV.x, 0.0) * 14.0) * head : 0.0;
		col = mix(mix(WHITE, fill_colour, on), vec3(0.85, 0.97, 1.0), tip * 0.8);
		e = mix(strip_off, strip_on, on) * (1.0 + 1.5 * tip);
	} else {
		col = lamp_colour(int(mod(round(idx), 4.0)));
		float l = step(abs(idx - lit), 0.5);
		e = mix(lamp_dim, lamp_lit, l) * (1.0 - 0.55 * clamp(order - l, 0.0, 1.0));
	}
	ALBEDO = col * e;
}
