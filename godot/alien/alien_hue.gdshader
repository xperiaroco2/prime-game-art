// The alien's hue material (art #196, parts kit; S2a, tuned in S3, the release-look surface in S9): one colour per
// character (`hue`, an instance uniform, so every body, lid and crest of one character shares this material and sets
// its own colour), with its own light tint (`pale`, also an instance uniform: teal's mint as u1, coral's peach and
// violet's lavender as the hue sheet).
// `hue` and `pale` are LINEAR (no source_color hint: the hint's sRGB conversion is not applied the same way to instance uniforms;
// alien.gd converts the sRGB colours with Color.srgb_to_linear() before setting them).
// The masks are in UV2 (glTF TEXCOORD_1, the `masks` UV layer written by tools/blender/alien_parts.py and
// tools/blender/alien_assemble.py):
//   UV2.x = the light mask (face, throat, belly): the hue mixes toward `pale`;
//   1 - UV2.y = the accent mask (knees, elbows, knuckles): the hue mixes toward `accent`. The glTF exporter flips V
//   (v_gltf = 1 - v_blender) and Godot keeps glTF's V, so the shader flips it back (measured in S3: unflipped, the
//   whole body came out coral with teal knees).
// S9, the release look (the paintover rf2), each term a uniform so a grid can tune it and three.js can copy it:
//   - the gradient: away from the light mask the hue deepens (darker, more saturated: `deep_mul`) toward the top of
//     the head and the crest (`deep_top`, by model-space height) and toward the back (`deep_back`, by the model-space
//     normal; the character faces +Z), and the pale tint warms toward the face (`face_warm`);
//   - baked ambient occlusion in the vertex colour's red (glTF COLOR_0, tools/blender/alien_ao.py; white when
//     absent): it darkens the albedo by `ao_albedo` and feeds AO for the ambient light;
//   - a soft grain: a value-noise micro normal in model space (`grain`, `grain_freq` per metre), faded out with the
//     view distance so it never shimmers far away, and a matching small roughness variation;
//   - S9b: the gradient and the grain read the rest pose (CUSTOM0, see vertex()), so they do not swim in motion;
//   - wrapped diffuse (render mode), screen-space subsurface (`sss`), a soft rim (`rim_value`) and a fresnel edge
//     glow toward the pale tint (`rim_glow`). (S9c: the unused `backlight` uniform went; nothing set it.)
// The hues (sRGB): godot/alien/alien.gd HUES, from the S3 export's character.json.
shader_type spatial;
render_mode diffuse_lambert_wrap, specular_schlick_ggx;

instance uniform vec3 hue = vec3(0.0117, 0.196, 0.2233);  // linear; sRGB (0.11, 0.48, 0.51), the teal (S9: rf2's deeper, bluer teal)
instance uniform vec3 pale = vec3(0.7105, 0.8276, 0.6209);  // linear; sRGB (0.86, 0.92, 0.81), the warm mint (S9)
uniform float light_mix : hint_range(0.0, 1.0) = 0.88;
uniform vec3 accent : source_color = vec3(0.89, 0.42, 0.36);
uniform float accent_mix : hint_range(0.0, 1.0) = 0.9;
uniform float roughness_value : hint_range(0.0, 1.0) = 0.62;
uniform float specular_value : hint_range(0.0, 1.0) = 0.3;
uniform float rim_value : hint_range(0.0, 1.0) = 0.2;
uniform float rim_tint : hint_range(0.0, 1.0) = 0.6;
// S9 terms; 0 turns each off
uniform float deep_top : hint_range(0.0, 1.0) = 0.0;
uniform float deep_back : hint_range(0.0, 1.0) = 0.0;
uniform vec3 deep_mul = vec3(0.55, 0.72, 0.78);  // the deep hue = hue * deep_mul (linear): darker, a little bluer
uniform vec2 deep_top_range = vec2(1.50, 1.85);  // model-space height (m) where the top's deepening ramps in
uniform float face_warm : hint_range(0.0, 1.0) = 0.0;
uniform vec3 warm_mul = vec3(1.06, 1.0, 0.90);  // the pale tint's warm shift at full face_warm
uniform float ao_albedo : hint_range(0.0, 1.0) = 0.0;
uniform float ao_light : hint_range(0.0, 1.0) = 0.0;
uniform float grain : hint_range(0.0, 0.5) = 0.0;
uniform float grain_freq = 500.0;
uniform vec2 grain_fade = vec2(0.8, 2.5);  // view distance (m): full grain up to x, none beyond y
uniform float sss : hint_range(0.0, 1.0) = 0.0;
uniform float rim_glow : hint_range(0.0, 1.0) = 0.0;  // a soft fresnel lift toward the pale tint at grazing angles (rf2's soft edge light, any lighting)
uniform float rim_glow_power = 3.0;

varying vec3 m_pos;
varying float m_nz;

#include "res://alien/alien_grain.gdshaderinc"

void vertex() {
	// S9b: the rest pose, so the gradient and the grain stay on the skin in motion (VERTEX here is already skinned).
	// The skin carries it in CUSTOM0 (glTF TEXCOORD_2 = rest x, y; TEXCOORD_3 = rest z, normal z + 2; written by
	// tools/blender/alien_ao.py); a part without it (CUSTOM0 = 0: the crests, rigid under the Head) uses its own.
	if (CUSTOM0.w > 0.5) {
		m_pos = CUSTOM0.xyz;
		m_nz = CUSTOM0.w - 2.0;
	} else {
		m_pos = VERTEX;
		m_nz = NORMAL.z;
	}
}

void fragment() {
	vec2 m = UV2;
	float light = clamp(m.x, 0.0, 1.0);
	// the gradient
	float top = smoothstep(deep_top_range.x, deep_top_range.y, m_pos.y) * deep_top;
	float back = smoothstep(-0.3, 0.9, -m_nz) * smoothstep(1.0, 1.4, m_pos.y) * deep_back;
	float deep = clamp(top + back, 0.0, 1.0) * (1.0 - light);
	vec3 base = mix(hue, hue * deep_mul, deep);
	vec3 p = pale * mix(vec3(1.0), warm_mul, face_warm * smoothstep(1.38, 1.50, m_pos.y));
	vec3 c = mix(base, p, light * light_mix);
	c = mix(c, accent, clamp(1.0 - m.y, 0.0, 1.0) * accent_mix);
	// baked AO
	float ao = COLOR.r;
	c *= mix(1.0, ao, ao_albedo);
	AO = ao;
	AO_LIGHT_AFFECT = ao_light;
	// the grain
	float fade = 1.0 - smoothstep(grain_fade.x, grain_fade.y, length(VERTEX));
	float rough = roughness_value;
	if (grain > 0.0 && fade > 0.0) {
		vec3 q = m_pos * grain_freq;
		vec3 g = vec3(vnoise(q), vnoise(q + vec3(17.1, 3.3, 9.7)), vnoise(q + vec3(5.9, 23.4, 1.7))) - 0.5;
		g += 0.5 * (vec3(vnoise(q * 2.3), vnoise(q * 2.3 + 11.0), vnoise(q * 2.3 + 29.0)) - 0.5);
		vec3 gv = (VIEW_MATRIX * (MODEL_MATRIX * vec4(g, 0.0))).xyz;
		gv -= dot(gv, NORMAL) * NORMAL;
		NORMAL = normalize(NORMAL + gv * grain * fade);
		rough = clamp(rough + (vnoise(q * 0.5) - 0.5) * grain * fade * 0.6, 0.0, 1.0);
	}
	ALBEDO = c;
	ROUGHNESS = rough;
	SPECULAR = specular_value;
	RIM = rim_value;
	RIM_TINT = rim_tint;
	SSS_STRENGTH = sss;
	float fr = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), rim_glow_power);
	EMISSION = mix(c, p, 0.5) * fr * rim_glow;
}
