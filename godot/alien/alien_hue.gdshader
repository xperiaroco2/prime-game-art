// The alien's hue material (art #196, parts kit, step S2a): one colour per character (`hue`, an instance uniform,
// so every body, head, lid and crest of one character shares this material and sets its own colour).
// The masks are in UV2 (glTF TEXCOORD_1, the `masks` UV layer written by tools/blender/alien_parts.py):
//   UV2.x = the light mask (face, throat, belly): the hue mixes toward `pale`;
//   UV2.y = the accent mask (knees, elbows, knuckles, lid rims, crest and antenna tips): the hue mixes toward `accent`.
// Soft matte: wrapped Lambert diffuse, a weak wide specular, a little rim; no texture and no noise.
// The three sampled hues (sRGB, from the 2026-10-17 hue sheet): see parts.json "hues_srgb".
shader_type spatial;
render_mode diffuse_lambert_wrap, specular_schlick_ggx;

instance uniform vec3 hue : source_color = vec3(0.30, 0.62, 0.60);
uniform vec3 pale : source_color = vec3(0.93, 0.95, 0.88);
uniform float light_mix : hint_range(0.0, 1.0) = 0.55;
uniform vec3 accent : source_color = vec3(0.85, 0.40, 0.36);
uniform float accent_mix : hint_range(0.0, 1.0) = 0.85;
uniform float roughness_value : hint_range(0.0, 1.0) = 0.62;
uniform float specular_value : hint_range(0.0, 1.0) = 0.35;
uniform float rim_value : hint_range(0.0, 1.0) = 0.25;

void fragment() {
	vec2 m = UV2;
	vec3 c = mix(hue, pale, clamp(m.x, 0.0, 1.0) * light_mix);
	c = mix(c, accent, clamp(m.y, 0.0, 1.0) * accent_mix);
	ALBEDO = c;
	ROUGHNESS = roughness_value;
	SPECULAR = specular_value;
	RIM = rim_value;
	RIM_TINT = 0.6;
}
