// The alien pilot's static premium head skin (art #196): one material for the whole head, Meshy's own sculpt with
// its painted eyes. The albedo (sRGB) holds the 2D's teal and mint; mask_tex (linear) holds R the skin tint mask
// (1 skin, 0 the eyes), G the roughness (wet eyes, softer lips, matte gills), B the subsurface and sheen weight.
// The colour slots (2026-10-23; tools/blender/alien_tint_mask.py): accent_tex (`<head>_accent.png`, linear RGB)
// holds R the lips, G the details (the chameleon's crest stripes, the axolotl's freckles and its gills'
// root-to-tip gradient), B the pale front; gill_tex (`<head>_gill.png`, linear, grey; v3: out of the accent's
// alpha) the whole gills (stalk and fringe). Both are data: lossless, no sRGB, no alpha (docs/godot.md).
// Every skin texel is recoloured from base_skin (the skin's own median, CS6b) to skin_color; the front from
// front_base to front_color (a tinted cream, set_colours' front mode); the details from detail_base to detail_color where
// detail_on (off: they follow the skin), the gills (gill_base to gill_color) with them by gill_mode (0 the skin, 1 the
// gradient: skin at the root to the details at the tips, 2 the whole gill); the lips from lip_base to lip_color.
// CS6 (2026-10-23): the recolour carries each texel's offset from its region's base (the region's median) onto the
// target in OKLab (shift): the base texel becomes the pick, the region's median within the albedo table's dE of it,
// and the paint's lighter and darker texels stay lighter and darker round it (CS6b: relative on a darker pick); on
// the raw albedo texel (linear), gated by the skin mask (the eyes keep their paint): the same maths as tools/web/alien_colour/colour.js's GLSL and alien_colour_geom.py's texel. Every
// target at its base is the identity. alien_static.gd builds this material from the imported glTF material and
// works out the targets from the player's picks (set_colours: the picks as picked, no guard rails since CS6).
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
// debug_mode: 1 grey with the normal map, 2 grey geometry only, 3 the albedo alone (emitted), 4 and 5 the colour
// slots' regions as flat codes and inverted (CS6's lit measurement), 6 the recoloured albedo alone (emitted; B4).
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
uniform sampler2D accent_tex : hint_default_black, filter_linear_mipmap, repeat_disable;
uniform sampler2D gill_tex : hint_default_black, filter_linear_mipmap, repeat_disable;
uniform vec3 lip_base : source_color = vec3(0.39, 0.77, 0.76);
uniform vec3 lip_color : source_color = vec3(0.39, 0.77, 0.76);
uniform vec3 detail_base : source_color = vec3(0.39, 0.77, 0.76);
uniform vec3 detail_color : source_color = vec3(0.39, 0.77, 0.76);
uniform vec3 gill_base : source_color = vec3(0.39, 0.77, 0.76);
uniform vec3 gill_color : source_color = vec3(0.39, 0.77, 0.76);
uniform vec3 front_base : source_color = vec3(0.39, 0.77, 0.76);
uniform vec3 front_color : source_color = vec3(0.39, 0.77, 0.76);
uniform float detail_on : hint_range(0.0, 1.0) = 1.0;
uniform float gill_mode : hint_range(0.0, 2.0) = 1.0;
uniform float normal_strength : hint_range(0.0, 2.0) = 1.0;
// AL6 (lively): the normal map's strength on the eye texels while gaze_on (lively.json controller.sclera_normal_map;
// 1 the merged look; 0 tried on the chameleon, eyes_pit_v6: its facets under the upper lids stayed)
uniform float sclera_normal_map : hint_range(0.0, 1.0) = 1.0;
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
// the bead (AL1, 2026-10-23: the axolotl's all-dark eyes, no iris to move): bead 1 draws sclera_tex (the albedo with
// the painted catch light painted out) and a catch light fixed in the mesh's own frame (to the light) at catch_dir_l/r,
// catch_angle wide, in catch_colour, times catch_light; the bead turns with the head under it
uniform float bead : hint_range(0.0, 1.0) = 0.0;
// AL2: one glint per bead, the drawn one: the bead's own reflections (specular, clear coat) times bead_reflect and
// its roughness at least bead_rough, so the key light leaves a soft sheen, not a second sharp point
uniform float bead_reflect : hint_range(0.0, 1.0) = 0.15;
uniform float bead_rough : hint_range(0.0, 1.0) = 0.55;
uniform vec3 catch_dir_l = vec3(0.0, 0.0, 1.0);
uniform vec3 catch_dir_r = vec3(0.0, 0.0, 1.0);
uniform float catch_angle = 0.1;
uniform vec3 catch_colour : source_color = vec3(1.0);
// AL3: the glint at a head turn. The catch light stays toward the light while the bead turns under it; past the
// bead's open cap (a turned-away eye) it would fall under the lid and the bead go flat and dead. catch_reach_l/r (radians,
// 0: off) is how far from the posed bead front (gaze_l/r, set each frame by the controller) the glint may sit: the
// rest angle between front and catch plus a margin, so at rest nothing changes and at a turn the glint slides to the
// cap's edge nearest the light, where the light would still catch the bead
uniform float catch_reach_l = 0.0;
uniform float catch_reach_r = 0.0;

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

// OKLab from linear sRGB (Ottosson's matrices; alien_colour_geom.py's _lab_lin)
vec3 oklab(vec3 c) {
	vec3 lms = vec3(dot(c, vec3(0.4122214708, 0.5363325363, 0.0514459929)),
		dot(c, vec3(0.2119034982, 0.6806995451, 0.1073969566)),
		dot(c, vec3(0.0883024619, 0.2817188376, 0.6299787005)));
	lms = sign(lms) * pow(abs(lms), vec3(1.0 / 3.0));
	return vec3(dot(lms, vec3(0.2104542553, 0.7936177850, -0.0040720468)),
		dot(lms, vec3(1.9779984951, -2.4285922050, 0.4505937099)),
		dot(lms, vec3(0.0259040371, 0.7827717662, -0.8086757660)));
}

// linear sRGB from OKLab (unclamped)
vec3 oklab_linear(vec3 lab) {
	vec3 lms = vec3(dot(lab, vec3(1.0, 0.3963377774, 0.2158037573)),
		dot(lab, vec3(1.0, -0.1055613458, -0.0638541728)),
		dot(lab, vec3(1.0, -0.0894841775, -1.2914855480)));
	lms = lms * lms * lms;
	return vec3(dot(lms, vec3(4.0767416621, -3.3077115913, 0.2309699292)),
		dot(lms, vec3(-1.2684380046, 2.6097574011, -0.3413193965)),
		dot(lms, vec3(-0.0041960863, -0.7034186147, 1.7076147010)));
}

// one texel x (OKLab) from its region's base b to the target t: its offset from b carried onto t; kr the lightness
// ratio on a darker t (CS6b: the mottling relative), the lightness offset scaled by kr (a lighter texel's also by
// the room toward white), the a/b offset turned by the hue turn and scaled by min(1, C_t / C_b) * kr
// (alien_colour_geom.py's shift)
vec3 shift(vec3 x, vec3 b, vec3 t) {
	float dl = x.x - b.x;
	float kr = min(1.0, t.x / max(b.x, 1.0e-4));
	float kl = dl > 0.0 ? min(kr, (1.0 - t.x) / max(1.0 - b.x, 1.0e-4)) : kr;
	float cb = length(b.yz);
	float ct = length(t.yz);
	vec2 r = vec2(1.0, 0.0);
	if (cb > 1.0e-4 && ct > 1.0e-4) {
		r = vec2(dot(b.yz, t.yz), b.y * t.z - b.z * t.y) / (cb * ct);
	}
	float kc = min(1.0, ct / max(cb, 1.0e-4)) * kr;
	vec2 d = x.yz - b.yz;
	return vec3(t.x + dl * kl, t.yz + vec2(d.x * r.x - d.y * r.y, d.x * r.y + d.y * r.x) * kc);
}

// the colour slots on one linear albedo texel: acc the accent (lips, details, front), gill the whole gills' weight;
// the regions mixed in OKLab (alien_colour_geom.py's texel)
vec3 recolour(vec3 c, vec3 acc, float gill) {
	vec3 x = oklab(c);
	vec3 t = shift(x, oklab(base_skin), oklab(skin_color));
	t = mix(t, shift(x, oklab(front_base), oklab(front_color)), acc.b);
	float dw = gill_mode < 0.5 ? max(acc.g - gill, 0.0) : (gill_mode < 1.5 ? acc.g : max(acc.g, gill));
	vec3 db = oklab(mix(detail_base, gill_base, gill));
	vec3 dt = oklab(mix(detail_color, gill_color, gill));
	t = mix(t, shift(x, db, dt), detail_on * dw);
	t = mix(t, shift(x, oklab(lip_base), oklab(lip_color)), acc.r);
	return clamp(oklab_linear(t), 0.0, 1.0);
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
	if (bead > 0.5) {
		vec3 cd = left ? catch_dir_l : catch_dir_r;
		vec3 f = normalize(left ? gaze_l : gaze_r);
		float reach = left ? catch_reach_l : catch_reach_r;
		float fa = acos(clamp(dot(f, cd), -1.0, 1.0));
		if (reach > 0.0 && fa > reach) {
			cd = normalize(f * cos(reach) + normalize(cd - f * dot(cd, f)) * sin(reach));
		}
		float ca = acos(clamp(dot(dir, cd), -1.0, 1.0));
		float wa = max(fwidth(ca), 1.0e-4);
		return mix(sclera, catch_colour, catch_light * (1.0 - smoothstep(catch_angle * 0.75 - wa, catch_angle * 1.1 + wa, ca)));
	}
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
	vec3 c = mix(a, recolour(a, texture(accent_tex, UV).rgb, texture(gill_tex, UV).r), m.r);
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
		float ns = normal_strength * mix(1.0, sclera_normal_map, gaze_on * eye);
		n = normalize(mix(NORMAL, TANGENT * nm.x + BINORMAL * nm.y + NORMAL * nm.z, ns));
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
	float br = step(0.5, bead) * gaze_on * eye;  // the bead's own eye texels (0 on the chameleon)
	SPECULAR = specular_level * mix(1.0, bead_reflect, br);
	ROUGHNESS = mix(mix(rough, max(rough, eye_under_rough), eye * step(0.001, eye_coat)), max(rough, bead_rough), br);
	CLEARCOAT = eye_coat * eye * mix(1.0, bead_reflect, br);
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
	} else if (debug_mode == 3 || debug_mode == 6) {
		ALBEDO = vec3(0.0);
		SPECULAR = 0.0;
		ROUGHNESS = 1.0;
		SSS_STRENGTH = 0.0;
		RIM = 0.0;
		BACKLIGHT = vec3(0.0);
		CLEARCOAT = 0.0;
		EMISSION = (debug_mode == 6 ? c : a) * 0.8;  // 6 (B4): the recoloured albedo, picks and creases in
	} else if (debug_mode == 4 || debug_mode == 5) {
		// CS6's proof: the colour slots' regions as flat codes for the lit measurement (alien_colour_slots.py): the
		// lips red, the details (under gill_mode, with detail_on) green, the front blue, the rest of the skin yellow,
		// a texel between regions grey, the eyes black; 5 the same inverted (the background is equal in both)
		vec3 acc = texture(accent_tex, UV).rgb;
		float gl = texture(gill_tex, UV).r;
		float dw = detail_on * (gill_mode < 0.5 ? max(acc.g - gl, 0.0) : (gill_mode < 1.5 ? acc.g : max(acc.g, gl)));
		vec3 code = vec3(0.25);
		if (acc.r > 0.9) {
			code = vec3(1.0, 0.0, 0.0);
		} else if (acc.r < 0.1 && dw > 0.9) {
			code = vec3(0.0, 1.0, 0.0);
		} else if (acc.r < 0.1 && dw < 0.1 && acc.b > 0.9) {
			code = vec3(0.0, 0.0, 1.0);
		} else if (max(acc.r, max(dw, acc.b)) < 0.1) {
			code = vec3(1.0, 1.0, 0.0);
		}
		code *= step(0.9, m.r);
		ALBEDO = vec3(0.0);
		SPECULAR = 0.0;
		ROUGHNESS = 1.0;
		SSS_STRENGTH = 0.0;
		RIM = 0.0;
		BACKLIGHT = vec3(0.0);
		CLEARCOAT = 0.0;
		EMISSION = debug_mode == 4 ? code : vec3(1.0) - code;
	}
}
