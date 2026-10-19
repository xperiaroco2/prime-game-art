// The alien's hue material (art #196, parts kit; S2a, tuned in S3): one colour per character (`hue`, an instance
// uniform, so every body, lid and crest of one character shares this material and sets its own colour), with its own
// light tint (`pale`, also an instance uniform: teal's mint as u1, coral's peach and violet's lavender as the hue sheet).
// `hue` and `pale` are LINEAR (no source_color hint: the hint's sRGB conversion is not applied the same way to instance uniforms;
// alien.gd converts the sRGB colours with Color.srgb_to_linear() before setting them).
// The masks are in UV2 (glTF TEXCOORD_1, the `masks` UV layer written by tools/blender/alien_parts.py and
// tools/blender/alien_assemble.py):
//   UV2.x = the light mask (face, throat, belly): the hue mixes toward `pale`;
//   1 - UV2.y = the accent mask (knees, elbows, knuckles, lid rims, crest and antenna tips): the hue mixes toward
//   `accent`. The glTF exporter flips V (v_gltf = 1 - v_blender) and Godot keeps glTF's V, so the shader flips it back
//   (measured in S3: unflipped, the whole body came out coral with teal knees).
// Soft matte: wrapped Lambert diffuse, a weak wide specular, a little rim; no texture and no noise.
// The hues (sRGB): godot/alien/alien.gd HUES, from the S3 export's character.json.
shader_type spatial;
render_mode diffuse_lambert_wrap, specular_schlick_ggx;

instance uniform vec3 hue = vec3(0.0256, 0.2733, 0.2623);  // linear; sRGB (0.17, 0.56, 0.55), the teal
instance uniform vec3 pale = vec3(0.6038, 0.807, 0.6038);  // linear; sRGB (0.80, 0.91, 0.80), u1's mint
uniform float light_mix : hint_range(0.0, 1.0) = 0.88;
uniform vec3 accent : source_color = vec3(0.89, 0.42, 0.36);
uniform float accent_mix : hint_range(0.0, 1.0) = 0.9;
uniform float roughness_value : hint_range(0.0, 1.0) = 0.62;
uniform float specular_value : hint_range(0.0, 1.0) = 0.3;
uniform float rim_value : hint_range(0.0, 1.0) = 0.2;

void fragment() {
	vec2 m = UV2;
	vec3 c = mix(hue, pale, clamp(m.x, 0.0, 1.0) * light_mix);
	c = mix(c, accent, clamp(1.0 - m.y, 0.0, 1.0) * accent_mix);
	ALBEDO = c;
	ROUGHNESS = roughness_value;
	SPECULAR = specular_value;
	RIM = rim_value;
	RIM_TINT = 0.6;
}
