// The alien pilot's static premium head skin (art #196): one material for the whole head, Meshy's own sculpt with
// its painted eyes. The albedo (sRGB) holds the 2D's teal and mint; mask_tex (linear) holds R the skin tint mask
// (1 skin, 0 the eyes), G the roughness (wet eyes, softer lips, matte gills), B the subsurface and sheen weight.
// skin_color recolours the skin: its hue, saturation and value relative to base_skin (the albedo's own skin teal)
// shift every masked texel, so the light and shade and the pale front's two-tone stay. skin_color == base_skin is
// the identity. alien_static.gd builds this material from the imported glTF material.
shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx, sss_mode_skin;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D mask_tex : hint_default_white, filter_linear_mipmap, repeat_disable;
uniform vec3 base_skin : source_color = vec3(0.39, 0.77, 0.76);
uniform vec3 skin_color : source_color = vec3(0.39, 0.77, 0.76);
uniform float normal_strength : hint_range(0.0, 2.0) = 1.0;
uniform float specular_level : hint_range(0.0, 1.0) = 0.45;
uniform float sss : hint_range(0.0, 1.0) = 0.25;
uniform float sheen : hint_range(0.0, 1.0) = 0.2;
uniform float sheen_tint : hint_range(0.0, 1.0) = 0.6;

vec3 rgb2hsv(vec3 c) {
	vec4 k = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
	vec4 p = mix(vec4(c.bg, k.wz), vec4(c.gb, k.xy), step(c.b, c.g));
	vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
	float d = q.x - min(q.w, q.y);
	float e = 1.0e-10;
	return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

vec3 hsv2rgb(vec3 c) {
	vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
	return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}

vec3 recolour(vec3 c) {
	vec3 h = rgb2hsv(c);
	vec3 b = rgb2hsv(base_skin);
	vec3 t = rgb2hsv(skin_color);
	h.x = fract(h.x + t.x - b.x);
	h.y = clamp(h.y * t.y / max(b.y, 1.0e-4), 0.0, 1.0);
	h.z = clamp(h.z * t.z / max(b.z, 1.0e-4), 0.0, 1.0);
	return hsv2rgb(h);
}

void fragment() {
	vec3 a = texture(albedo_tex, UV).rgb;
	vec3 m = texture(mask_tex, UV).rgb;
	ALBEDO = mix(a, recolour(a), m.r);
	ROUGHNESS = m.g;
	METALLIC = 0.0;
	SPECULAR = specular_level;
	NORMAL_MAP = texture(normal_tex, UV).rgb;
	NORMAL_MAP_DEPTH = normal_strength;
	SSS_STRENGTH = sss * m.b;
	RIM = sheen * m.b;
	RIM_TINT = sheen_tint;
}
