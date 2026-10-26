// The start console's hologram and light column (console.gd): additive cyan light, no depth write, both sides.
// mode 0 the lines (their brightness x 100 in the build's UV0 v; glTF flips v: 1 - UV.y), mode 1 the see-through
// shell (brighter where it turns away from the eye, its outline), mode 2 the column from the core (fading upward,
// UV0 v the height share x 100, and toward its silhouette).
// The spin-up (art#263): mode 3 the turbines (v their brightness x 100; u the angle round the pod, the fans u 5,
// turned round their pod's axis), mode 4 the wiring (v the station's index, 8 the manifold; u the distance along the
// line toward the turbines in dm; the points u -1, their halos u -2), mode 5 the charge ring (u the bar's share, v 0
// at its foot, 1 at its top), mode 6 the countdown (v digit x 10 + segment a..g; turned about the console's axis to
// the eye). Time is console.gd's `clock` (seconds), so the game can read the call's phase.
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, shadows_disabled, fog_disabled;

uniform int mode = 0;
uniform vec3 colour : source_color = vec3(0.06, 0.42, 1.0);
uniform float energy = 1.6;
uniform float clock = 0.0;
uniform vec3 orange : source_color = vec3(1.0, 0.11, 0.0);  // deep: the glow and AgX pale it to orange
uniform vec3 red : source_color = vec3(1.0, 0.03, 0.02);
uniform float calling = 0.0;
uniform float call_t0 = 0.0;
uniform float call_period = 3.0;
uniform float spin_phase = 0.0;  // turns at clock spin_t0, then spin_rate turns per second
uniform float spin_t0 = 0.0;
uniform float spin_rate = 0.0;
uniform float spin_full = 0.6;   // the rate at which the turbines' chase shows fully
uniform vec3 fan_centre[3];
uniform vec3 fan_axis = vec3(0.0, 0.0, 1.0);
uniform float charge = 0.0;
uniform float flow = 0.0;        // the wiring's flow (0 before the start)
uniform float st_state[9];       // 0 off, 1 ok, 2 broken; the manifold: the share of the lines not broken
uniform float st_blink[9];       // a broken station's blinks per second
uniform float st_fixed_at[9];    // the clock when a station was fixed (its flash)
uniform float countdown = -1.0;  // seconds; below 0 hidden
uniform vec3 wire_colour : source_color = vec3(0.25, 0.85, 1.0);  // the wiring: paler than the hull's lines

const int DIGITS[10] = int[10](63, 6, 91, 79, 102, 109, 125, 7, 127, 111);  // bit 0 segment a ... bit 6 g

float call_pulse(float ph) {  // the call's light over its period, from the beep at 0
	return smoothstep(0.0, 0.05, ph) * (1.0 - smoothstep(0.05, 0.45, ph));
}

float spin_turns() {
	return spin_phase + (clock - spin_t0) * spin_rate;
}

void vertex() {
	if (mode == 3 && UV.x > 4.5) {  // a fan: turned round the axis through its own centre (the nearest)
		vec3 c = fan_centre[0];
		for (int i = 1; i < 3; i++) {
			if (distance(VERTEX, fan_centre[i]) < distance(VERTEX, c)) {
				c = fan_centre[i];
			}
		}
		float a = TAU * spin_turns();
		vec3 k = normalize(fan_axis);
		vec3 p = VERTEX - c;
		VERTEX = c + p * cos(a) + cross(k, p) * sin(a) + k * dot(k, p) * (1.0 - cos(a));
	} else if (mode == 6) {  // the countdown faces the eye, turned about the console's vertical axis
		vec3 eye = (inverse(MODEL_MATRIX) * vec4(CAMERA_POSITION_WORLD, 1.0)).xyz;
		float yaw = atan(eye.x, eye.z);
		float cy = cos(yaw);
		float sy = sin(yaw);
		VERTEX = vec3(VERTEX.x * cy + VERTEX.z * sy, VERTEX.y, -VERTEX.x * sy + VERTEX.z * cy);
	}
}

void fragment() {
	float k = (1.0 - UV.y) * 0.01;
	float facing = abs(dot(NORMAL, VIEW));
	vec3 col = colour;
	float a;
	if (mode == 0) {
		a = k * energy;
	} else if (mode == 1) {
		a = k * energy * (0.25 + 0.9 * (1.0 - facing));
	} else if (mode == 2) {
		a = pow(clamp(1.0 - k, 0.0, 1.0), 1.6) * facing * energy;
	} else if (mode == 3) {
		float amount = clamp(spin_rate / spin_full, 0.0, 1.0);
		float chase = 1.0 + 0.5 * amount;
		if (UV.x < 4.5) {  // three bright arcs running round each pod with its fan
			float w = 0.5 + 0.5 * cos(TAU * 3.0 * (UV.x + spin_turns()));
			chase = mix(1.0, 0.5 + 1.8 * pow(w, 4.0), amount);
		}
		float p = calling * call_pulse(fract((clock - call_t0) / call_period));
		col = mix(colour, orange, p);
		a = k * energy * chase * (1.0 + 0.9 * p);
	} else if (mode == 4) {
		int i = clamp(int(round(1.0 - UV.y)), 0, 8);
		float st = st_state[i];
		float since = clock - st_fixed_at[i];
		float flash = since >= 0.0 ? exp(-since * 2.2) : 0.0;
		float blink = pow(0.5 + 0.5 * cos(TAU * clock * st_blink[i]), 2.0);
		bool broken = i < 8 && st > 1.5;
		if (UV.x < -0.5) {  // the station's point (u -1) and its halo (u -2)
			float halo = UV.x < -1.5 ? 0.6 : 1.0;
			if (broken) {
				col = red;
				a = (0.2 + 4.5 * blink) * halo;
			} else {
				col = wire_colour;
				a = (st > 0.5 ? 2.0 : 0.8) * halo;
			}
		} else {
			float dash = pow(0.5 + 0.5 * cos(TAU * (UV.x * 1.25 - clock * 1.4)), 6.0);
			float lit = i == 8 ? st : (st > 0.5 ? 1.0 : 0.0);
			if (broken) {
				col = mix(colour, red, 0.5);
				a = 0.05;
			} else {
				col = wire_colour;
				a = 0.35 + lit * flow * (0.35 + 1.8 * dash);
			}
		}
		col = mix(col, vec3(0.75, 0.95, 1.0), flash);
		a = (a + 3.5 * flash) * energy;
	} else if (mode == 5) {
		float h = 1.0 - UV.y;
		float body = 0.3 + 0.7 * pow(1.0 - h, 1.5) + 0.7 * smoothstep(0.85, 1.0, h);
		float lit = charge > 0.0005 ? step(UV.x, charge) : 0.0;
		float head = lit * exp(-max(charge - UV.x, 0.0) * 60.0) * step(charge, 0.9995);
		float shimmer = 0.85 + 0.15 * sin(TAU * (UV.x * 18.0 - clock * 0.7));
		col = mix(colour, vec3(0.75, 0.95, 1.0), head * 0.8);
		a = (mix(0.13, shimmer, lit) * body + 1.6 * head * body) * energy;
	} else {
		if (countdown < 0.0) {
			a = 0.0;
		} else {
			int id = int(round(1.0 - UV.y));
			int dg = id / 10;
			int sg = id - dg * 10;
			int secs = clamp(int(ceil(countdown)), 0, 99);
			int val = dg == 0 ? secs / 10 : secs - (secs / 10) * 10;
			float on = (dg == 0 && secs < 10) ? 0.0 : float((DIGITS[val] >> sg) & 1);
			bool urgent = countdown <= 5.0;
			col = countdown <= 3.0 ? red : (urgent ? orange : colour);
			float tick = urgent ? pow(fract(countdown), 5.0) : 0.0;
			a = on * (1.0 + 1.2 * tick) * energy;
		}
	}
	ALBEDO = col * a;
}
