// M12/M13 (art #196): a talking mouth piece's secondary motion (alien.gd's talk styles, alien_talk.gd), shared by the
// lips' shader (alien_lip.gdshader: the lips and the fangs) and the inner cup's and tongue's (alien_mouth_part.gdshader),
// so everything of the shown piece moves together. All three are instance uniforms on the shown piece, 0 by default:
// every other part draws as before. The pieces' model space is the Mouth socket's: y up, z toward the front.
// - `lip_drop` (m): the lower jaw down (positive) or pressed up (negative), times the vertex's jaw weight;
// - `jaw_thrust` (m): the lower jaw forward, times the jaw weight (the fangs' A and E);
// - `pucker` (0..1): the lips purse between words: narrower toward the centre line (`pucker_amount.x` of x at full)
//   and forward at the centre (`pucker_amount.y` m).
// - `tongue_flop` (m, M14): the tongue mouth's tongue tip lags and flops (alien_talk.gd's `flop`), times the
//   vertex's flop weight (TEXCOORD_1's u, Godot UV2.x: 0 up to the lower lip's top, rising to 1 at the tip) and the
//   material's `flop_mask` (1 only on the tongue's alien_tongue_pink, so no other surface reads UV2).
// The jaw weight is COLOR_0's alpha (M13b; M13 had it in g, which tinted a viewer that shows vertex colour), written
// by tools/blender/alien_m12.py (1 on the lower lip, the tongue and the fangs, 0
// on the upper lip, a smooth blend round an open ring, less toward the corners); COLOR_0's rgb stays the baked AO.
instance uniform float lip_drop = 0.0;
instance uniform float pucker = 0.0;
instance uniform float jaw_thrust = 0.0;
instance uniform vec3 tongue_flop = vec3(0.0);
uniform vec2 pucker_amount = vec2(0.14, 0.003);
uniform float flop_mask = 0.0;

vec3 tongue_motion(vec3 v, float w) {
	return v + tongue_flop * (flop_mask * w);
}

vec3 mouth_motion(vec3 v, float jaw) {
	if (lip_drop != 0.0 || jaw_thrust != 0.0 || pucker > 0.0) {
		v.y -= lip_drop * jaw;
		v.z += jaw_thrust * jaw;
		v.x *= 1.0 - pucker_amount.x * pucker;
		v.z += pucker_amount.y * pucker * (1.0 - smoothstep(0.0, 0.03, abs(v.x)));
	}
	return v;
}
