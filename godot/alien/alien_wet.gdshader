// The alien's wet line (art #196, M4): the thin tear film where a lid meets the eyeball, on the strip
// eye_<design>_wet_<lid>_<side> that tools/blender/alien_eyes.py hangs under each lid (it turns with the lid). A clear,
// glossy film: half transparent, a warm white on the ball's side going toward the lid's coral under the rim, a low
// roughness so the lights draw a fine bright line along the lid. UV: x across the lid (faded at both corners), y from
// the ball's side to the lid's edge, flipped by the glTF exporter (v_gltf = 1 - v_blender), so across = 1 - UV.y.
// `open` (an instance uniform, alien.gd) fades it out as the lids close, where the two lids' strips would cross.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_lambert_wrap, specular_schlick_ggx;

uniform vec3 film : source_color = vec3(0.98, 0.94, 0.91);
uniform vec3 lid_tint : source_color = vec3(0.92, 0.62, 0.56);
uniform float alpha_max : hint_range(0.0, 1.0) = 0.6;
uniform float ball_soft : hint_range(0.01, 1.0) = 0.3;  // the fade-in from the ball's side (share of the strip)
uniform float lid_from : hint_range(0.0, 1.0) = 0.5;  // the fade-out toward the lid's edge, from here to the end: the
// part under the rim showed as a pale shelf in a grazing view
uniform float end_fade : hint_range(0.01, 0.5) = 0.3;  // the fade at the corners (share of the span)
uniform float roughness_value : hint_range(0.0, 1.0) = 0.07;
uniform float specular_value : hint_range(0.0, 1.0) = 0.7;
instance uniform float open = 1.0;

void fragment() {
	float across = 1.0 - UV.y;
	float along = smoothstep(0.0, end_fade, UV.x) * smoothstep(1.0, 1.0 - end_fade, UV.x);
	ALBEDO = mix(film, lid_tint, smoothstep(0.55, 1.0, across));
	ALPHA = alpha_max * smoothstep(0.0, ball_soft, across) * (1.0 - smoothstep(lid_from, 1.0, across)) * along * open;
	ROUGHNESS = roughness_value;
	SPECULAR = specular_value;
}
