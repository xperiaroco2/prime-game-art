// The lens alcoves' conduit cores (art#263, prime-game#1095 "some electricity there"; tools/blender/ship_interior_lens.py
// lens_conduits, material int_cyan__lens_core): the cyan core of the four bronze conduits, with pulses that run along
// them into the jambs while the charger charges. UV0: x the run coordinate (0 where the conduit leaves the jamb .. 1
// at the deck or the ceiling), y the run's length (m). charger/zap.gd's bind puts one copy on a charger's conduits,
// its base the material's own glow (ship.gd's look), and drives it:
//   idle      flow 0, steady 0: the base glow alone
//   charging  flow 1: bright bands run from the deck and the ceiling into the jambs (`clock` s, zap.gd's own clock)
//   charged   flow 0, steady 1: the core a little brighter, steady
//   taken out `lit` 1 -> 0: back to the base glow
// Emission only: it lights nothing.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec3 albedo : source_color = vec3(0.03, 0.06, 0.09);
uniform float roughness : hint_range(0.0, 1.0) = 0.3;
// the base glow (linear colour times energy, from the surface's own material)
uniform vec3 base_emission = vec3(0.0, 0.15, 0.6);
uniform float flow : hint_range(0.0, 1.0) = 0.0;
uniform float steady : hint_range(0.0, 1.0) = 0.0;
uniform float lit : hint_range(0.0, 1.0) = 1.0;
uniform float clock = 0.0;
uniform vec3 pulse_color : source_color = vec3(0.55, 0.9, 1.0);
uniform float pulse_energy : hint_range(0.0, 16.0) = 5.0;
// the pulses: m apart, m/s, their length (m)
uniform float spacing = 0.45;
uniform float speed = 1.1;
uniform float band = 0.12;
// charged: the base's share added
uniform float steady_gain : hint_range(0.0, 4.0) = 0.8;

void fragment() {
	ALBEDO = albedo;
	ROUGHNESS = roughness;
	METALLIC = 0.0;
	float len = max(UV.y, 0.01);
	float s = (1.0 - UV.x) * len;   // m from the far end
	float ph = fract((s - speed * clock) / spacing) * spacing;   // m behind the pulse's front
	float x = ph / band;
	float pulse = x < 1.0 ? (1.0 - x) * (1.0 - x) * smoothstep(0.0, 0.08, x) : 0.0;
	float k = flow * lit;
	vec3 e = base_emission * (1.0 + steady_gain * steady * lit + 0.4 * k);
	e += pulse_color * pulse * pulse_energy * k;
	EMISSION = e;
}
