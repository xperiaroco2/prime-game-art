// The alien's eyeball (art #196, S5; M4: the modern eye). Everything is drawn from the eyeball's own model space, no
// texture: the ball is centred at its node's origin, forward +Z and up +Y (Blender's -Y forward and +Z up through
// glTF), so the iris and pupil turn with the ball when it looks. Lengths below are in eyeball radii.
// - The white: `white` (sRGB), shaded warm (`shade`, never grey) toward the eye's corners (left and right of the
//   forward axis), toward its rim as the ball turns away from the view (`edge_falloff`: never paper-white at the
//   edges), and under the lids: a broad soft shadow below the upper lid's edge and above the lower one, plus a narrow
//   contact shadow right at each edge (`contact_*`, also an AO term that dims the reflections there). The lid edges
//   are `instance uniform`s in degrees above the forward axis (alien.gd sets them from the lid rotations: edge =
//   -rotation.x), so both shadows follow a blink.
// - M4, the cornea (`cornea` 1; 0 keeps S9's painted eye for before/after sheets): a clear cap over the iris, a
//   sphere through the limbus ring (`limbus_deg` from the axis) rising `bulge` above the ball. It is optical only: the
//   ball's mesh stays a sphere (the lower lids' inner radius, 1.012, leaves no room for a real bulge). Per pixel the
//   view ray is intersected with that sphere, refracted (`ior`) and followed to the iris plane `iris_depth` below the
//   limbus plane, so the iris and pupil sit behind the cornea and shift as the view turns (parallax). The iris and
//   pupil radii on that plane are solved so that seen along the axis they cover `iris_deg` and `pupil_deg` of the
//   ball exactly as the S9 design did. The cornea's own normal and a low roughness give the key light and the sky a
//   crisp reflection (`cornea_normal`: only part of it for the diffuse, so no ring shows round the manic eye's pupil);
//   the catch light is a view-space light (`catch_dir`, toward the camera, a little left) reflected on the cornea,
//   pulled toward a place on the eye (`catch_anchor_deg`, `catch_follow`), so it moves over the cornea as the view turns
//   but never leaves the pupil and iris.
// - The iris (bored): a dark brown with fine radial fibres, a lighter ring round the pupil, a darker limbal ring and
//   a warm glow low on the side away from the catch light (light through the cornea).
// - The wet film: a soft clear coat over the white (`wet`), sharper on the cornea.
shader_type spatial;
render_mode diffuse_lambert_wrap, specular_schlick_ggx;

uniform vec3 white : source_color = vec3(0.95, 0.93, 0.86);  // sRGB of stage 1's linear (0.9, 0.86, 0.72), a touch lighter
uniform vec3 shade : source_color = vec3(0.86, 0.72, 0.64);  // the warm tint the white goes toward in the corners
uniform float corner_shade : hint_range(0.0, 1.0) = 0.55;
uniform float corner_from_deg = 30.0;  // the side angle (from the forward axis) where the corner shading starts ...
uniform float corner_to_deg = 80.0;  // ... and where it is full
uniform float lid_shade : hint_range(0.0, 1.0) = 0.6;  // under the upper lid
uniform float lid_soft_deg = 16.0;  // how far below the upper lid's edge its shadow reaches
uniform float lower_shade : hint_range(0.0, 1.0) = 0.3;  // above the lower lid (a half-width band)
uniform vec3 iris : source_color = vec3(0.26, 0.16, 0.11);
uniform vec3 pupil : source_color = vec3(0.025, 0.02, 0.025);
uniform float iris_deg = 25.0;  // 0: no iris (the manic design)
uniform float pupil_deg = 11.5;
uniform float edge_deg = 0.9;  // the soft edge of the iris and pupil
uniform float ring : hint_range(0.0, 1.0) = 0.45;  // the darker ring at the iris edge
uniform vec2 catch_at_deg = vec2(5.0, 4.0);  // S9's painted glint (cornea 0) from the pupil axis: x toward -X, y up
uniform float catch_deg = 2.4;  // its radius
uniform float catch_soft_deg = 1.0;
uniform float catch_energy = 1.1;
uniform float roughness_value : hint_range(0.0, 1.0) = 0.38;
uniform float specular_value : hint_range(0.0, 1.0) = 0.35;
// M4
uniform float cornea : hint_range(0.0, 1.0) = 1.0;
uniform float limbus_deg = 27.0;  // the cornea's edge, from the pupil axis
uniform float limbus_soft_deg = 3.0;
uniform float bulge = 0.12;  // the cornea's apex above the ball
uniform float iris_depth = 0.05;  // the iris plane below the limbus plane
uniform float ior = 1.336;
uniform float cornea_roughness : hint_range(0.0, 1.0) = 0.14;  // 0.03: a hard second dot; 0.06: a mottled softbox
uniform float cornea_specular : hint_range(0.0, 1.0) = 0.25;
uniform float cornea_normal : hint_range(0.0, 1.0) = 0.4;  // how much of the cornea's normal the lights see (the catch light: all)
uniform vec3 catch_dir = vec3(-0.45, -0.25, 1.0);  // view space: x right, y up, z toward the camera
uniform vec2 catch_anchor_deg = vec2(5.0, -10.0);  // its place on the eye (as catch_at_deg): just below the rest lid
uniform float catch_follow : hint_range(0.0, 1.0) = 0.3;  // 0: fixed on the eye at catch_anchor_deg, 1: the view's
uniform float catch_size_deg = 4.0;  // the catch light's half angle on the cornea (of the half vector)
uniform float catch_m4_energy = 2.4;
uniform float fibres : hint_range(0.0, 1.0) = 0.12;
uniform float collarette : hint_range(0.0, 1.0) = 0.12;  // the lighter ring round the pupil
uniform float iris_glow : hint_range(0.0, 2.0) = 0.5;  // the warm glow low in the iris
uniform float limbal : hint_range(0.0, 1.0) = 0.55;  // the darkness inside the cornea beyond the iris (the limbal ring)
uniform float edge_falloff : hint_range(0.0, 1.0) = 0.2;  // the white toward `shade` where the ball turns away (0.35 bared the socket)
uniform float contact_deg = 3.5;  // the contact shadow's width below the upper and above the lower lid's edge
uniform float contact_dark : hint_range(0.0, 1.0) = 0.45;
uniform float wet : hint_range(0.0, 1.0) = 0.5;  // the clear coat on the white
uniform float wet_roughness : hint_range(0.0, 1.0) = 0.22;
instance uniform float upper_edge_deg = 6.0;
instance uniform float lower_edge_deg = -30.0;

varying vec3 pos_m;
varying vec3 cam_m;

void vertex() {
	pos_m = VERTEX;
	cam_m = (inverse(MODEL_MATRIX) * vec4(CAMERA_POSITION_WORLD, 1.0)).xyz;
}

// The cornea: a sphere through the limbus ring (sin L, cos L) and the apex 1 + bulge; returns (centre z, radius).
vec2 cornea_sphere() {
	float l = radians(limbus_deg);
	float d = 1.0 + bulge - cos(l);
	float rc = (sin(l) * sin(l) + d * d) / (2.0 * d);
	return vec2(1.0 + bulge - rc, rc);
}

// Where a ray along -Z at distance x from the axis meets the iris plane after the cornea: the plane radius that
// looks like x from the front (so the design's angles keep their look).
float front_rho(float x, vec2 cs, float zp) {
	float hz = cs.x + sqrt(max(cs.y * cs.y - x * x, 0.0));
	vec3 n = normalize(vec3(x, 0.0, hz - cs.x));
	vec3 r = refract(vec3(0.0, 0.0, -1.0), n, 1.0 / ior);
	return x + r.x * (zp - hz) / min(r.z, -1e-3);
}

float fibre_noise(float a, float rho) {
	return 0.5 * sin(a * 37.0 + 2.0 * sin(a * 11.0)) + 0.3 * sin(a * 71.0 + rho * 9.0) + 0.2 * sin(a * 23.0 - 1.7);
}

void fragment() {
	float R = length(pos_m);
	vec3 d = pos_m / R;
	float side = degrees(atan(abs(d.x), d.z));
	float elev = degrees(atan(d.y, max(d.z, 0.0) + 1e-4));
	float k = smoothstep(corner_from_deg, corner_to_deg, side) * corner_shade;
	float lid_k = smoothstep(upper_edge_deg - lid_soft_deg, upper_edge_deg, elev) * lid_shade;
	lid_k = max(lid_k, (1.0 - smoothstep(lower_edge_deg, lower_edge_deg + 0.5 * lid_soft_deg, elev)) * lower_shade);
	k = max(k, lid_k);
	vec3 c = mix(white, white * shade, k);
	vec3 p = d;  // the pupil axis is the ball's +Z
	float from_axis = degrees(acos(clamp(p.z, -1.0, 1.0)));
	if (cornea < 0.5) {  // S9's painted eye
		if (iris_deg > 0.0) {
			float ia = 1.0 - smoothstep(iris_deg - edge_deg, iris_deg + edge_deg, from_axis);
			float r = smoothstep(iris_deg - 5.0, iris_deg, from_axis) * ring;
			c = mix(c, iris * (1.0 - r) * mix(1.0, 0.8, k), ia);
		}
		float pa = 1.0 - smoothstep(pupil_deg - edge_deg, pupil_deg + edge_deg, from_axis);
		c = mix(c, pupil, pa);
		ALBEDO = c;
		ROUGHNESS = roughness_value;
		SPECULAR = specular_value;
		vec3 g = normalize(vec3(-tan(radians(catch_at_deg.x)), tan(radians(catch_at_deg.y)), 1.0));
		float ga = degrees(acos(clamp(dot(p, g), -1.0, 1.0)));
		EMISSION = vec3(1.0, 0.98, 0.95) * (1.0 - smoothstep(catch_deg, catch_deg + catch_soft_deg, ga)) * catch_energy;
	} else {
		// the contact shadow right at each lid's edge, and the white's falloff toward the rim
		float contact = smoothstep(upper_edge_deg - contact_deg, upper_edge_deg, elev);
		contact = max(contact, 1.0 - smoothstep(lower_edge_deg, lower_edge_deg + contact_deg, elev));
		mat3 to_view = mat3(VIEW_MATRIX) * mat3(MODEL_MATRIX);
		vec3 n_ball = normalize(to_view * p);
		float nv = clamp(dot(n_ball, VIEW), 0.0, 1.0);
		c = mix(c, c * shade, edge_falloff * (1.0 - smoothstep(0.15, 0.75, nv)));
		// the cornea
		vec2 cs = cornea_sphere();
		float zl = cos(radians(limbus_deg));
		float zp = zl - iris_depth;
		vec3 o = cam_m / R;
		vec3 v = normalize(p - o);
		vec3 oc = o - vec3(0.0, 0.0, cs.x);
		float b = dot(oc, v);
		float disc = b * b - (dot(oc, oc) - cs.y * cs.y);
		vec3 hit = p;
		if (disc > 0.0) {
			vec3 h = o + v * (-b - sqrt(disc));
			hit = h.z >= zl ? h : p;
		}
		vec3 nc = normalize(hit - vec3(0.0, 0.0, cs.x));
		vec3 rr = refract(v, nc, 1.0 / ior);
		vec2 q = hit.xy + rr.xy * (zp - hit.z) / min(rr.z, -1e-3);
		float rho = length(q);
		float in_c = smoothstep(cos(radians(limbus_deg)), cos(radians(limbus_deg - limbus_soft_deg)), p.z);
		float iris_rho = front_rho(sin(radians(iris_deg)), cs, zp);
		float pupil_rho = front_rho(sin(radians(pupil_deg)), cs, zp);
		float e_rho = front_rho(sin(radians(pupil_deg + edge_deg)), cs, zp) - pupil_rho;
		vec3 thru;
		if (iris_deg > 0.0) {
			float u = rho / max(iris_rho, 1e-4);  // 0 at the centre, 1 at the iris edge
			float a = atan(q.y, q.x);
			vec3 ic = iris * (1.0 + fibres * fibre_noise(a, u) * smoothstep(0.3, 0.6, u) * (1.0 - smoothstep(0.85, 1.0, u)));
			ic *= 1.0 + collarette * exp(-pow((u - 0.62) / 0.1, 2.0));
			ic *= 1.0 - ring * smoothstep(0.78, 1.0, u);
			// the glow: low in the iris, on the side away from the catch light (in the ball's plane, the view's left is
			// the ball's -X when the eye faces the camera)
			float g = smoothstep(-0.1, -0.9, (q.y - 0.35 * q.x) / max(iris_rho, 1e-4)) * smoothstep(0.35, 0.65, u);
			ic *= 1.0 + iris_glow * g;
			ic *= mix(1.0, 0.8, k);
			vec3 beyond = mix(c, c * iris * 2.0, limbal);  // inside the cornea past the iris disc
			thru = mix(ic, beyond, smoothstep(1.0, 1.0 + e_rho / iris_rho * 1.5, u));
		} else {
			thru = c;  // the manic eye: the white through the clear cornea round a dot pupil
		}
		thru = mix(thru, pupil, 1.0 - smoothstep(pupil_rho - e_rho, pupil_rho + e_rho, rho));
		c = mix(c, thru, in_c);
		c *= 1.0 - contact_dark * contact;
		ALBEDO = c;
		vec3 n_m = normalize(mix(p, nc, in_c * cornea_normal));
		NORMAL = normalize(to_view * n_m);
		ROUGHNESS = mix(roughness_value, cornea_roughness, in_c);
		float occ = 1.0 - 0.85 * max(contact, lid_k / max(lid_shade, 1e-3) * 0.6);
		SPECULAR = mix(specular_value, cornea_specular, in_c) * occ;
		AO = 1.0 - 0.6 * contact;
		AO_LIGHT_AFFECT = 0.3;
		CLEARCOAT = wet * occ;
		CLEARCOAT_ROUGHNESS = mix(wet_roughness, cornea_roughness, in_c);
		// the catch light: a view-space light reflected on the cornea, pulled toward S9's place on the eye (so a turned
		// eye never loses it: a dead eye reads creepy)
		vec3 hv = normalize(normalize(catch_dir) + VIEW);
		vec3 g = normalize(vec3(-tan(radians(catch_anchor_deg.x)), tan(radians(catch_anchor_deg.y)), 1.0));
		vec3 anchor = normalize(to_view * normalize(g - vec3(0.0, 0.0, cs.x)));
		vec3 aim = normalize(mix(anchor, hv, catch_follow));
		float ca = degrees(acos(clamp(dot(normalize(to_view * nc), aim), -1.0, 1.0)));
		float cm = (1.0 - smoothstep(catch_size_deg * 0.75, catch_size_deg, ca)) * in_c * occ;
		EMISSION = vec3(1.0, 0.98, 0.95) * cm * catch_m4_energy;
	}
}
