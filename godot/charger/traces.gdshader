// The charger traces (art#263, prime-game#1095 c6468773545, a_circuit.jpg): the cyan lines inlaid in a lens room's
// alcove back panel (tools/blender/ship_interior_lens.py trace_parts, material lens_trace), lit by the charge. Each
// line's UV0: x its fill coordinate (0 at its outer end .. 1 at the ring), y the line's metres per unit of fill (the
// head's and the soft front's size in cm); the ring has y < 0. traces.gd's set_panel drives `fill`, `lit` and
// `flare`; ship.gd puts one copy on every lens_trace surface (the idle look: these defaults). Emission only: it lights
// nothing (no strip light, no GI).
//   idle      fill 0: every line at `dim`, the ring at `ring_dim`
//   charging  fill = the charge: behind the front full, ahead `dim`, a small bright head on the front
//   full      fill 1: everything full; `flare` (0..1, a 0.3 s pulse) flares the ring white-cyan
//   taken out `lit` 1 -> 0 over 0.5 s: everything back to dim
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform float fill : hint_range(0.0, 1.0) = 0.0;
uniform float lit : hint_range(0.0, 1.0) = 1.0;
uniform float flare : hint_range(0.0, 1.0) = 0.0;
// the lines' dim glow (a share of full) and the ring's; full is `energy` (3.0, then 1.5 bleached the cyan pale under
// AgX, the concept's lines are a saturated cyan)
uniform float dim : hint_range(0.0, 1.0) = 0.13;
uniform float ring_dim : hint_range(0.0, 1.0) = 0.18;
// the ring's share of full while the fronts run toward it (it builds with the fill, full at fill 1)
uniform float ring_build : hint_range(0.0, 1.0) = 0.35;
uniform vec3 glow_color : source_color = vec3(0.0, 0.6, 1.0);
uniform vec3 head_color : source_color = vec3(0.72, 0.96, 1.0);
uniform vec3 flare_color : source_color = vec3(0.82, 0.97, 1.0);
uniform float energy : hint_range(0.0, 16.0) = 1.3;
uniform float head_energy : hint_range(0.0, 8.0) = 2.2;
uniform float flare_energy : hint_range(0.0, 16.0) = 4.0;
// the head: its tail behind the front (cm) and its nose ahead (cm); the front's soft edge ahead (cm)
uniform float head_cm : hint_range(0.1, 20.0) = 3.0;
uniform float nose_cm : hint_range(0.1, 10.0) = 0.8;
uniform float soft_cm : hint_range(0.01, 5.0) = 0.5;
// the line's own surface where it does not glow: a dark glassy cyan, flush with the matte navy panel
uniform vec3 albedo : source_color = vec3(0.02, 0.06, 0.09);
uniform float roughness : hint_range(0.0, 1.0) = 0.5;

void fragment() {
	ALBEDO = albedo;
	ROUGHNESS = roughness;
	METALLIC = 0.0;
	float b;
	vec3 e;
	if (UV.y < 0.0) {
		float on = max(smoothstep(0.97, 1.0, fill), ring_build * fill) * lit;
		b = mix(ring_dim, 1.0, on);
		e = glow_color * b * energy + flare_color * flare * flare_energy;
	} else {
		float x = (fill - UV.x) * UV.y * 100.0;   // cm behind the front (negative ahead of it)
		float active = smoothstep(0.0, 0.01, fill);
		float behind = smoothstep(-soft_cm, 0.0, x) * active;
		b = mix(dim, 1.0, behind * lit);
		float run = active * (1.0 - smoothstep(0.985, 1.0, fill)) * lit;
		float d = x >= 0.0 ? x / head_cm : -x / nose_cm;
		float head = exp(-d * d) * run;
		e = glow_color * b * energy + head_color * head * head_energy * energy;
	}
	EMISSION = e;
}
