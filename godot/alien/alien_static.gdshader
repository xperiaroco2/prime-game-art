// The alien pilot's static premium head skin (art #196): one material for the whole head, Meshy's own sculpt with
// its painted eyes. The albedo (sRGB) holds the 2D's teal and mint; mask_tex (linear) holds R the skin tint mask
// (1 skin, 0 the eyes), G the roughness (wet eyes, softer lips, matte gills), B the subsurface and sheen weight.
// skin_color recolours the skin: its hue, saturation and value relative to base_skin (the albedo's own skin teal)
// shift every masked texel, so the light and shade and the pale front's two-tone stay. skin_color == base_skin is
// the identity. alien_static.gd builds this material from the imported glTF material.
//
// The "alive" levers (static_v2, 2026-10-22), each off at its default. The defaults are NOT the #288 material: static_v3
// dropped sss_mode_skin from the render mode, so the #288 heads are shown with alien_static_288.gdshader, the merged
// #288 shader kept byte for byte (static_v5):
// detail_tex (linear, baked from the dense original) holds R the cavity (1 open, 0 deep crease), G the thinness
// (1 thin: gills, crest, lips), B the flush region (lips, lids), A the eyes' limbal ring.
// - transmission: light through the thin parts (BACKLIGHT) in a saturated scatter colour;
// - micro: a fine procedural grain in object space (a bump from 3D value noise), faded with distance and pixel size,
//   and a roughness breakup from the same noise;
// - cavity, flush: the creases deeper and more saturated (never grey), the lips and lids a little flushed;
// - fuzz: a soft, lighter and more saturated sheen at grazing angles;
// - eye_coat: a wet clear coat on the eyes over a softer iris, the limbal ring darker.
// static_v3: the alive read is baked into the albedo; plain_tex (the albedo without it) and alive_mix scale it for the
// review grids (1 = the GLB's albedo as baked; above 1 extrapolates). The shader's cavity, flush and micro grain stay
// off in the pick (baked now; the grain read as orange peel).
// lively (2026-10-23): the gaze. gaze_on 0 (the default) leaves the merged look untouched. gaze_on 1 draws the eyes
// from sclera_tex (the albedo with the painted irises filled from the sclera around them, alien_lively_build.py) and
// a procedural iris on the build's fitted eye sphere: per eye (left = +X) its centre and gaze in this mesh's own
// space (alien_lively.gd moves both with the head bone), the iris and pupil caps' angles, the iris's radial colour
// profile (8 medians of the painted iris, pupil edge to limbus), the pupil's colour, a limbal ring and a painted
// catch light (catch_light 0: none, as the painted eyes have none).
// debug_mode: 1 grey with the normal map, 2 grey geometry only, 3 the albedo alone (emitted).
shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;  // static_v3: no sss_mode_skin (its red profile browned the teal creases)

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D mask_tex : hint_default_white, filter_linear_mipmap, repeat_disable;
uniform sampler2D detail_tex : hint_default_white, filter_linear_mipmap, repeat_disable;
uniform sampler2D plain_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform float alive_mix : hint_range(0.0, 2.0) = 1.0;
uniform vec3 base_skin : source_color = vec3(0.39, 0.77, 0.76);
uniform vec3 skin_color : source_color = vec3(0.39, 0.77, 0.76);
uniform float normal_strength : hint_range(0.0, 2.0) = 1.0;
uniform float specular_level : hint_range(0.0, 1.0) = 0.45;
uniform float sss : hint_range(0.0, 1.0) = 0.25;
uniform float sheen : hint_range(0.0, 1.0) = 0.2;
uniform float sheen_tint : hint_range(0.0, 1.0) = 0.6;
uniform float transmission : hint_range(0.0, 2.0) = 0.0;
uniform float scatter_from_skin : hint_range(0.0, 1.0) = 1.0;
uniform vec3 scatter_color : source_color = vec3(1.0, 0.5, 0.4);
uniform float micro_strength : hint_range(0.0, 1.0) = 0.0;
uniform float micro_scale = 140.0;
uniform float micro_fade = 2.5;
uniform float rough_breakup : hint_range(0.0, 0.3) = 0.0;
uniform float cavity : hint_range(0.0, 1.0) = 0.0;
uniform float cavity_warm : hint_range(-0.2, 0.2) = 0.0;
uniform float flush : hint_range(0.0, 1.0) = 0.0;
uniform float fuzz : hint_range(0.0, 1.0) = 0.0;
uniform float fuzz_power = 3.0;
uniform float eye_coat : hint_range(0.0, 1.0) = 0.0;
uniform float eye_coat_rough : hint_range(0.0, 1.0) = 0.03;
uniform float eye_under_rough : hint_range(0.0, 1.0) = 0.3;
uniform float limbal : hint_range(0.0, 1.0) = 0.0;
uniform int debug_mode = 0;
uniform float gaze_on : hint_range(0.0, 1.0) = 0.0;
uniform sampler2D sclera_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform vec3 eye_centre_l = vec3(0.265, 0.266, 0.355);
uniform vec3 eye_centre_r = vec3(-0.265, 0.266, 0.355);
uniform vec3 gaze_l = vec3(0.0, 0.0, 1.0);
uniform vec3 gaze_r = vec3(0.0, 0.0, 1.0);
uniform float iris_angle = 0.27;
uniform float pupil_angle = 0.19;
uniform vec3 iris_profile[8];
uniform vec3 pupil_colour : source_color = vec3(0.05, 0.03, 0.02);
uniform float limbal_ring : hint_range(0.0, 1.0) = 0.0;
uniform float catch_light : hint_range(0.0, 1.0) = 0.0;
uniform vec2 catch_offset = vec2(-0.35, 0.45);  // the catch light's place in iris radii: (toward -X, up)
uniform float catch_size = 0.16;  // its radius in iris radii

varying vec3 v_obj;

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

// hue (turns), saturation gain, value gain
vec3 shade(vec3 c, float dh, float ks, float kv) {
	vec3 h = rgb2hsv(c);
	return hsv2rgb(vec3(fract(h.x + dh), clamp(h.y * ks, 0.0, 1.0), clamp(h.z * kv, 0.0, 1.0)));
}

float hash3(vec3 p) {
	p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
	p *= 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vnoise(vec3 x) {
	vec3 i = floor(x);
	vec3 f = fract(x);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(hash3(i), hash3(i + vec3(1, 0, 0)), f.x), mix(hash3(i + vec3(0, 1, 0)), hash3(i + vec3(1, 1, 0)), f.x), f.y),
		mix(mix(hash3(i + vec3(0, 0, 1)), hash3(i + vec3(1, 0, 1)), f.x), mix(hash3(i + vec3(0, 1, 1)), hash3(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}

float grain(vec3 p) {
	return vnoise(p) * 0.65 + vnoise(p * 2.31 + vec3(7.1, 3.3, 1.7)) * 0.35;
}

void vertex() {
	v_obj = VERTEX;
}

// The procedural iris over the clean sclera at one eye texel (lively).
vec3 lively_eye(vec3 sclera) {
	// the nearer eye centre (v_obj is the posed position: after a head turn a texel may cross x = 0)
	bool left = distance(v_obj, eye_centre_l) < distance(v_obj, eye_centre_r);
	vec3 dir = normalize(v_obj - (left ? eye_centre_l : eye_centre_r));
	vec3 g = left ? gaze_l : gaze_r;
	float th = acos(clamp(dot(dir, g), -1.0, 1.0));
	float w = max(fwidth(th), 1.0e-4);
	float t = clamp((th - pupil_angle) / (iris_angle - pupil_angle), 0.0, 1.0) * 7.0;
	int k = min(int(t), 6);
	vec3 iris = mix(iris_profile[k], iris_profile[k + 1], t - float(k));
	iris *= 1.0 - limbal_ring * smoothstep(iris_angle * 0.8, iris_angle, th);
	vec3 c = mix(sclera, iris, 1.0 - smoothstep(iris_angle - w, iris_angle + w, th));
	c = mix(c, pupil_colour, 1.0 - smoothstep(pupil_angle - w, pupil_angle + w, th));
	if (catch_light > 0.0) {
		// the catch light's place: the gaze turned by catch_offset iris radii in the eye's own frame
		vec3 side = normalize(vec3(g.z, 0.0, -g.x));
		vec3 up = cross(g, side);
		vec3 cd = normalize(g + (side * catch_offset.x + up * catch_offset.y) * tan(iris_angle));
		float cth = acos(clamp(dot(dir, cd), -1.0, 1.0));
		float cr = catch_size * iris_angle;
		c = mix(c, vec3(1.0), catch_light * (1.0 - smoothstep(cr - w, cr + w, cth)));
	}
	return c;
}

void fragment() {
	vec3 a = texture(albedo_tex, UV).rgb;
	if (alive_mix != 1.0) {
		a = clamp(mix(texture(plain_tex, UV).rgb, a, alive_mix), 0.0, 1.0);
	}
	vec3 m = texture(mask_tex, UV).rgb;
	if (gaze_on > 0.0) {
		a = mix(a, lively_eye(texture(sclera_tex, UV).rgb), gaze_on * (1.0 - m.r));
	}
	vec4 d = texture(detail_tex, UV);
	float eye = 1.0 - m.r;
	vec3 c = mix(a, recolour(a), m.r);
	float rough = m.g;
	// the creases deeper and more saturated, the lips and lids a little flushed (skin only)
	float crease = (1.0 - d.r) * cavity * m.r;
	c = mix(c, shade(c, cavity_warm, 1.35, 0.55), crease);
	c = mix(c, shade(c, -0.02, 1.25, 0.9), flush * d.b * m.r);
	c *= 1.0 - limbal * d.a * eye;
	// the normal map as Godot's own NORMAL_MAP does it, then the micro grain on top
	vec3 n = NORMAL;
	if (debug_mode != 2) {
		vec2 nxy = texture(normal_tex, UV).xy * 2.0 - 1.0;
		vec3 nm = vec3(nxy, sqrt(max(0.0, 1.0 - dot(nxy, nxy))));
		n = normalize(mix(NORMAL, TANGENT * nm.x + BINORMAL * nm.y + NORMAL * nm.z, normal_strength));
	}
	if (micro_strength > 0.0 && debug_mode == 0) {
		vec3 p = v_obj * micro_scale;
		float fade = clamp(1.0 - (length(VERTEX) - 0.5) / micro_fade, 0.0, 1.0);
		fade *= clamp(1.6 - length(fwidth(p)), 0.0, 1.0) * m.r;
		float e = 0.3;
		float g0 = grain(p);
		vec3 g = vec3(grain(p + vec3(e, 0, 0)) - g0, grain(p + vec3(0, e, 0)) - g0, grain(p + vec3(0, 0, e)) - g0) / e;
		vec3 gv = mat3(VIEW_MATRIX) * (mat3(MODEL_MATRIX) * g);
		gv -= n * dot(gv, n);
		n = normalize(n - micro_strength * fade * gv);
		rough = clamp(rough + rough_breakup * fade * (g0 - 0.5) * 2.0, 0.05, 1.0);
	}
	NORMAL = n;
	float nv = clamp(dot(n, VIEW), 0.0, 1.0);
	c = mix(c, shade(c, 0.0, 1.15, 1.25), fuzz * pow(1.0 - nv, fuzz_power) * m.r);
	ALBEDO = c;
	METALLIC = 0.0;
	SPECULAR = specular_level;
	ROUGHNESS = mix(rough, max(rough, eye_under_rough), eye * step(0.001, eye_coat));
	CLEARCOAT = eye_coat * eye;
	CLEARCOAT_ROUGHNESS = eye_coat_rough;
	SSS_STRENGTH = sss * m.b;
	RIM = sheen * m.b;
	RIM_TINT = sheen_tint;
	vec3 scatter = mix(scatter_color, shade(c, 0.0, 1.3, 1.0), scatter_from_skin);
	BACKLIGHT = scatter * transmission * d.g * m.r;
	if (debug_mode == 1 || debug_mode == 2) {
		ALBEDO = vec3(0.5);
		ROUGHNESS = 0.35;
		SSS_STRENGTH = 0.0;
		RIM = 0.0;
		BACKLIGHT = vec3(0.0);
		CLEARCOAT = 0.0;
	} else if (debug_mode == 3) {
		ALBEDO = vec3(0.0);
		SPECULAR = 0.0;
		ROUGHNESS = 1.0;
		SSS_STRENGTH = 0.0;
		RIM = 0.0;
		BACKLIGHT = vec3(0.0);
		CLEARCOAT = 0.0;
		EMISSION = a * 0.8;
	}
}
