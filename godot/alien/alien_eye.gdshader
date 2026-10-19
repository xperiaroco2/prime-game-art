// The alien's eyeball (art #196, S5): the stage-1 human faces' eye (tools/blender/um/clayface, docs/faces.md: a warm
// off-white white, a dark iris and pupil, glossy but soft) on the parts kit's rigid eyeball, which replaces the first
// test's texture (a cold white with a tiny pupil, "so-so, creepy"). Everything is drawn from the eyeball's own model
// space, no texture: the ball is centred at its node's origin, forward +Z and up +Y (Blender's -Y forward and +Z up
// through glTF), so the iris and pupil turn with the ball when it looks.
// - The white: `white` (sRGB), shaded warm (`shade`, never grey) toward the eye's corners (left and right of the
//   forward axis) and under the lids, as a soft contact shadow below the upper lid's edge and above the lower one.
//   The lid edges are `instance uniform`s in degrees above the forward axis (alien.gd sets them from the lid
//   rotations: edge = -rotation.x), so the shadow follows the blink.
// - The iris and pupil: discs round the ball's +Z, with soft edges and a darker ring at the iris edge. (The sockets
//   point 8 degrees outward, which made the pupils diverge: alien.gd turns each ball back in at rest, its look.)
// - One catch light, painted: a small soft dot on the pupil, up and toward the viewer's left (-X) on both eyes (the
//   light from one side, as the face kit's `highlights`), added as emission. It moves with the eye, as a designer
//   toy's painted glint does; the scene's lights see a soft roughness, so the key gives a broad sheen, no hard glint.
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
uniform vec2 catch_at_deg = vec2(5.0, 4.0);  // the glint from the pupil axis: x toward -X (the viewer's left), y up
uniform float catch_deg = 2.4;  // its radius
uniform float catch_soft_deg = 1.0;
uniform float catch_energy = 1.1;
uniform float roughness_value : hint_range(0.0, 1.0) = 0.38;
uniform float specular_value : hint_range(0.0, 1.0) = 0.35;
instance uniform float upper_edge_deg = 6.0;
instance uniform float lower_edge_deg = -30.0;

varying vec3 dir;

void vertex() {
	dir = VERTEX;
}

void fragment() {
	vec3 d = normalize(dir);
	float side = degrees(atan(abs(d.x), d.z));
	float elev = degrees(atan(d.y, max(d.z, 0.0) + 1e-4));
	float k = smoothstep(corner_from_deg, corner_to_deg, side) * corner_shade;
	k = max(k, smoothstep(upper_edge_deg - lid_soft_deg, upper_edge_deg, elev) * lid_shade);
	k = max(k, (1.0 - smoothstep(lower_edge_deg, lower_edge_deg + 0.5 * lid_soft_deg, elev)) * lower_shade);
	vec3 c = mix(white, white * shade, k);
	vec3 p = d;  // the pupil axis is the ball's +Z
	float from_axis = degrees(acos(clamp(p.z, -1.0, 1.0)));
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
}
