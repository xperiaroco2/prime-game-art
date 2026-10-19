// The alien's wet line (art #196, M4): the thin tear film where a lid meets the eyeball, on the strip
// eye_<design>_wet_<lid>_<side> that tools/blender/alien_eyes.py hangs under each lid (it turns with the lid). A clear,
// glossy film: half transparent, a warm white on the ball's side going toward the lid's coral under the rim, a low
// roughness so the lights draw a fine bright line along the lid. UV: x across the lid (faded at both corners), y from
// the ball's side to the lid's edge, flipped by the glTF exporter (v_gltf = 1 - v_blender), so across = 1 - UV.y; the
// rolled rim's farthest point is at across = `rim_v` on every lid (alien_eyes_geom.rim_v), so the film shows on the
// ball beyond the rim and fades out just under it. It also fades where the view grazes it (a film seen edge-on read as
// a grey shelf with a light line in a turned view, the first M4).
// `open` (an instance uniform, alien.gd) fades it out as the lids close, where the two lids' strips would cross.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_lambert_wrap, specular_schlick_ggx;

uniform vec3 film : source_color = vec3(0.98, 0.94, 0.91);
uniform vec3 lid_tint : source_color = vec3(0.92, 0.62, 0.56);
uniform float alpha_max : hint_range(0.0, 1.0) = 0.6;
uniform float ball_soft : hint_range(0.01, 1.0) = 0.25;  // the fade-in from the ball's side (share of the strip)
uniform float rim_v : hint_range(0.0, 1.0) = 0.5;  // the rim's reach (alien_eyes_geom.rim_v)
uniform float under_soft : hint_range(0.01, 1.0) = 0.15;  // the fade-out under the rim, from rim_v
uniform float graze_from : hint_range(0.0, 1.0) = 0.1;  // the fade where the view grazes the film (dot(NORMAL, VIEW)) ...
uniform float graze_to : hint_range(0.0, 1.0) = 0.45;  // ... from nothing to full
uniform float end_fade : hint_range(0.01, 0.5) = 0.3;  // the fade at the corners (share of the span)
uniform float roughness_value : hint_range(0.0, 1.0) = 0.07;
uniform float specular_value : hint_range(0.0, 1.0) = 0.7;
instance uniform float open = 1.0;

void fragment() {
	float across = 1.0 - UV.y;
	float along = smoothstep(0.0, end_fade, UV.x) * (1.0 - smoothstep(1.0 - end_fade, 1.0, UV.x));
	ALBEDO = mix(film, lid_tint, smoothstep(rim_v, 1.0, across));
	float graze = smoothstep(graze_from, graze_to, abs(dot(NORMAL, VIEW)));
	ALPHA = alpha_max * smoothstep(0.0, ball_soft, across) * (1.0 - smoothstep(rim_v, rim_v + under_soft, across))
			* along * graze * open;
	ROUGHNESS = roughness_value;
	SPECULAR = specular_value;
}
