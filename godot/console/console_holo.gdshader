// The start console's hologram and light column (console.gd): additive cyan light, no depth write, both sides.
// mode 0 the lines (their brightness x 100 in the build's UV0 v; glTF flips v: 1 - UV.y), mode 1 the see-through
// shell (brighter where it turns away from the eye, its outline; washed orange by the call's pulse), mode 2 the
// column from the core (fading upward, UV0 v the height share x 100, and toward its silhouette).
// The spin-up (art#263): mode 3 the turbines (v their brightness x 100; u the angle round the pod, the fans u 5,
// turned round their pod's axis; the call's glow sprites u 7, v 200), mode 4 the wiring (v the station's index, 8 the
// manifold; u the distance along the line toward the turbines in dm; the points u -1, their halos u -2, a broken
// point's pillar u -3..-4 and its glow sprite u -5), mode 5 the charge ring (u the bar's share 0..1; v 0 at the band's
// foot, 1 at its built top, 2..3 the deck ring's foot to top), mode 6 the countdown (v digit x 10 + segment a..g;
// turned about the console's axis to the eye). A sprite's or pillar's corner sits FX_SPREAD off its id in u and v
// (sx, sy in -1..1); the vertex stage moves the corners to face the eye at their own size, or folds them onto their
// centre (no pixels) while their state is off. Time is console.gd's `clock` (seconds), so the game can read the call's
// phase.
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, shadows_disabled, fog_disabled;

uniform int mode = 0;
uniform vec3 colour : source_color = vec3(0.06, 0.42, 1.0);
uniform float energy = 1.6;
uniform float clock = 0.0;
uniform vec3 orange : source_color = vec3(1.0, 0.11, 0.0);  // deep: the glow and AgX pale it to orange
uniform vec3 red : source_color = vec3(1.0, 0.012, 0.0);  // deep: bright red blooms to pink
uniform float calling = 0.0;
uniform float call_t0 = 0.0;
uniform float call_period = 3.0;
uniform vec3 call_colour : source_color = vec3(1.0, 0.62, 0.0);  // the call's orange: over the blue, a redder one reads pink
uniform float call_flood = 1.4;  // the turbines' brightness over their own at a call's peak (more bleaches to peach)
uniform float call_thick = 0.0022;  // m: how far the turbines' lines swell at a call's peak
uniform float call_glow_r = 0.16;   // m: the call's orange glow round each pod (a camera-facing sprite)
uniform float call_glow = 1.4;
uniform float call_wash = 0.12;     // the shell's orange wash at a call's peak (mode 1; more turns the blue lavender)
uniform float spin_phase = 0.0;  // turns at clock spin_t0, then spin_rate turns per second
uniform float spin_t0 = 0.0;
uniform float spin_rate = 0.0;
uniform float spin_full = 0.6;   // the rate at which the turbines' chase shows fully
uniform vec3 fan_centre[3];
uniform vec3 fan_axis = vec3(0.0, 0.0, 1.0);
uniform float charge = 0.0;
uniform vec3 fill : source_color = vec3(0.06, 0.5, 1.0);  // the bar's lit colour (the strips' fill_colour)
uniform float band_top = 0.5;    // the share of the built band drawn (0.5: step 1's 0.75 m of the built 1.5 m)
uniform float band_gain = 1.0;   // the band's brightness when lit
uniform float deck = 0.0;        // the deck ring: 1 drawn, 0 not
uniform float flow = 0.0;        // the wiring's flow (0 before the start)
uniform float st_state[9];       // 0 off, 1 ok, 2 broken; the manifold: the share of the lines not broken
uniform float st_blink[9];       // a broken station's blinks per second
uniform float st_fixed_at[9];    // the clock when a station was fixed (its flash)
uniform float countdown = -1.0;  // seconds; below 0 hidden
uniform vec3 wire_colour : source_color = vec3(0.25, 0.85, 1.0);  // the wiring: paler than the hull's lines
uniform float fx_w0 = 0.005;     // m: the half size the sprites and pillars are built at (build.json spinup fx w0_m)
uniform float broken_glow_r = 0.055;  // m: a broken point's red glow (its sprite's half size)
uniform float pillar_w = 0.02;   // m: a broken point's pillar's half width

const float FX_SPREAD = 0.3;
const int DIGITS[10] = int[10](63, 6, 91, 79, 102, 109, 125, 7, 127, 111);  // bit 0 segment a ... bit 6 g

float call_pulse(float ph) {  // the call's light over its period, from the beep at 0
	return smoothstep(0.0, 0.05, ph) * (1.0 - smoothstep(0.05, 0.45, ph));
}

float call_now() {
	return calling * call_pulse(fract((clock - call_t0) / call_period));
}

float spin_turns() {
	return spin_phase + (clock - spin_t0) * spin_rate;
}

float blink_at(int i) {
	return pow(max(0.5 + 0.5 * cos(TAU * clock * st_blink[i]), 0.0), 2.0);  // cos may undershoot -1: no NaN
}

vec3 eye_model(mat4 model, vec3 cam) {
	return (inverse(model) * vec4(cam, 1.0)).xyz;
}

void vertex() {
	if (mode == 3 && UV.x > 6.0) {  // the call's glow round a pod: a sprite, there only while a pulse is up
		float sx = (UV.x - 7.0) / FX_SPREAD;
		float sy = ((1.0 - UV.y) - 200.0) / FX_SPREAD;
		vec3 c = VERTEX - vec3(sx, sy, 0.0) * fx_w0;
		vec3 r = normalize((inverse(MODEL_MATRIX) * vec4(INV_VIEW_MATRIX[0].xyz, 0.0)).xyz);
		vec3 u = normalize((inverse(MODEL_MATRIX) * vec4(INV_VIEW_MATRIX[1].xyz, 0.0)).xyz);
		VERTEX = c + (r * sx + u * sy) * call_glow_r * step(0.002, call_now());
	} else if (mode == 3) {
		VERTEX += NORMAL * call_thick * call_now();  // the lines swell with the pulse
		if (UV.x > 4.5) {  // a fan: turned round the axis through its own centre (the nearest)
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
		}
	} else if (mode == 4 && UV.x < -2.5) {  // a broken point's pillar or glow: there only while it is broken
		float vv = 1.0 - UV.y;
		int i = clamp(int(round(vv)), 0, 8);
		float on = st_state[i] > 1.5 ? 1.0 : 0.0;
		float s2 = (vv - float(i)) / FX_SPREAD;
		if (UV.x > -4.5) {  // the pillar: turned about the vertical to the eye
			vec3 c = VERTEX - vec3(s2 * fx_w0, 0.0, 0.0);
			vec3 to = eye_model(MODEL_MATRIX, CAMERA_POSITION_WORLD) - c;
			vec3 side = normalize(cross(vec3(0.0, 1.0, 0.0), vec3(to.x, 0.0, to.z) + vec3(1e-5, 0.0, 0.0)));
			VERTEX = c + side * s2 * pillar_w * on;
		} else {
			float sx = (UV.x + 5.0) / FX_SPREAD;
			vec3 c = VERTEX - vec3(sx, s2, 0.0) * fx_w0;
			vec3 r = normalize((inverse(MODEL_MATRIX) * vec4(INV_VIEW_MATRIX[0].xyz, 0.0)).xyz);
			vec3 u = normalize((inverse(MODEL_MATRIX) * vec4(INV_VIEW_MATRIX[1].xyz, 0.0)).xyz);
			VERTEX = c + (r * sx + u * s2) * broken_glow_r * on;
		}
	} else if (mode == 6) {  // the countdown faces the eye, turned about the console's vertical axis
		vec3 eye = eye_model(MODEL_MATRIX, CAMERA_POSITION_WORLD);
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
	float a = 0.0;
	if (mode == 0) {
		a = k * energy;
	} else if (mode == 1) {
		float p = call_now();
		col = mix(colour, call_colour, call_wash * p);
		a = k * energy * (0.25 + 0.9 * (1.0 - facing)) * (1.0 + 0.8 * p);
	} else if (mode == 2) {
		a = pow(clamp(1.0 - k, 0.0, 1.0), 1.6) * facing * energy;
	} else if (mode == 3) {
		float p = call_now();
		if (UV.x > 6.0) {  // the call's glow: soft, round, orange
			vec2 q = vec2((UV.x - 7.0), ((1.0 - UV.y) - 200.0)) / FX_SPREAD;
			float r2 = dot(q, q);
			col = call_colour;
			a = p * call_glow * exp(-r2 * 4.5) * (1.0 - smoothstep(0.8, 1.0, r2));
		} else {
			float amount = clamp(spin_rate / spin_full, 0.0, 1.0);
			float chase = 1.0 + 0.5 * amount;
			if (UV.x < 4.5) {  // three bright arcs running round each pod with its fan
				float w = 0.5 + 0.5 * cos(TAU * 3.0 * (UV.x + spin_turns()));
				chase = mix(1.0, 0.5 + 1.8 * pow(max(w, 0.0), 4.0), amount);
			}
			col = mix(colour, call_colour, p);
			a = k * energy * chase * (1.0 + call_flood * p);
		}
	} else if (mode == 4) {
		int i = clamp(int(round(1.0 - UV.y)), 0, 8);
		float st = st_state[i];
		float since = clock - st_fixed_at[i];
		float flash = since >= 0.0 ? exp(-since * 2.2) : 0.0;
		float blink = blink_at(i);
		bool broken = i < 8 && st > 1.5;
		if (UV.x < -2.5) {  // a broken point's pillar (u -3 - its height share) or glow (u -5)
			float s2 = ((1.0 - UV.y) - float(i)) / FX_SPREAD;
			col = red;
			flash = 0.0;
			if (UV.x > -4.5) {
				float h = clamp(-3.0 - UV.x, 0.0, 1.0);
				float core = 2.2 * exp(-s2 * s2 * 18.0) + 0.5 * exp(-s2 * s2 * 2.5);
				a = (0.3 + 2.4 * blink) * core * pow(1.0 - h, 0.9) * smoothstep(0.0, 0.05, h);
			} else {
				vec2 q = vec2((UV.x + 5.0) / FX_SPREAD, s2);
				float r2 = dot(q, q);
				float bead = 1.0 - smoothstep(0.07, 0.12, r2);
				a = (0.3 + 2.6 * blink) * (2.5 * bead + 1.1 * exp(-r2 * 4.0)) * (1.0 - smoothstep(0.75, 1.0, r2));
			}
		} else if (UV.x < -0.5) {  // the station's point (u -1) and its halo (u -2)
			bool is_halo = UV.x < -1.5;
			if (broken) {
				col = red;
				a = (0.15 + 2.2 * blink) * (is_halo ? 1.2 : 1.0);
			} else {
				col = wire_colour;
				a = st > 0.5 ? (is_halo ? 0.9 : 2.0) : (is_halo ? 0.48 : 0.8);  // ok: a calmer halo than step 1's 1.2
			}
		} else {
			float dash = pow(max(0.5 + 0.5 * cos(TAU * (UV.x * 1.25 - clock * 1.4)), 0.0), 6.0);
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
		float v = 1.0 - UV.y;
		bool on_deck = v > 1.5;
		float h = on_deck ? clamp(v - 2.0, 0.0, 1.0) : v / band_top;  // 0 at the foot, 1 at the drawn top
		float shown = on_deck ? deck : step(h, 1.0);
		h = min(h, 1.0);  // over the drawn top: pow() of a negative is NaN, and a NaN blooms the frame black
		float body = 0.3 + 0.7 * pow(1.0 - h, 1.5) + 0.7 * smoothstep(0.85, 1.0, h);
		float lit = charge > 0.0005 ? step(UV.x, charge) : 0.0;
		float head = lit * exp(-max(charge - UV.x, 0.0) * 60.0) * step(charge, 0.9995);
		float shimmer = 0.85 + 0.15 * sin(TAU * (UV.x * 18.0 - clock * 0.7));
		col = mix(mix(colour, fill, lit), vec3(0.75, 0.95, 1.0), head * 0.8);
		float gain = on_deck ? 1.0 : mix(1.0, band_gain, lit);
		a = shown * (mix(0.13, shimmer, lit) * body * gain + 1.6 * head * body) * energy;
	} else if (mode == 6) {
		if (countdown >= 0.0) {
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
