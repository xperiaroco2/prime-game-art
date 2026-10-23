// The vault plush's surface (art#297, step 3): the painted albedo, the baked normal and a fine pile normal in model
// space (the atlas is cut into many islands, so a UV-space pattern would show every seam), soft Burley diffuse,
// roughness 1 on the pile, and the sheen of a plush as Godot's rim. mask_tex (linear): R the orange fur, G the brown
// velour, B the eyes (glossy: whites, pupils and their catch lights; the smile's thread is in no channel, matte). The fuzzy silhouette comes from plush_shell.gdshader,
// chained as next passes by plush.gd.
shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap, repeat_disable;
uniform sampler2D mask_tex : filter_linear_mipmap, repeat_disable;
uniform sampler2D pile_tex : hint_normal, filter_linear_mipmap, repeat_enable;
uniform float pile_tiles_per_m = 45.0;  // one pile tile per 2.2 cm of fabric
uniform float pile_strength = 0.55;
uniform float sheen : hint_range(0.0, 1.0) = 0.55;
uniform float sheen_tint : hint_range(0.0, 1.0) = 0.85;  // the sheen takes the fabric's colour, not white
uniform float grazing_lift : hint_range(0.0, 1.0) = 0.12;  // fibres catch light at the silhouette
uniform float eye_roughness : hint_range(0.0, 1.0) = 0.18;  // glossy eyes with a catch light, as in the concept

varying vec3 mpos;
varying vec3 mnorm;

void vertex() {
	mpos = VERTEX;
	mnorm = NORMAL;
}

vec3 pile(vec3 p, vec3 n) {
	vec3 w = pow(abs(n), vec3(4.0));
	w /= (w.x + w.y + w.z);
	vec3 q = p * pile_tiles_per_m;
	return texture(pile_tex, q.zy).rgb * w.x + texture(pile_tex, q.xz).rgb * w.y + texture(pile_tex, q.xy).rgb * w.z;
}

void fragment() {
	vec3 m = texture(mask_tex, UV).rgb;
	float fabric = clamp(m.r + m.g, 0.0, 1.0);
	vec3 base = texture(albedo_tex, UV).rgb;
	float facing = clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	float graze = pow(1.0 - facing, 2.0);
	ALBEDO = base * mix(1.0, 0.9 + grazing_lift * graze * 1.6, fabric);
	vec3 n = texture(normal_tex, UV).rgb * 2.0 - 1.0;
	vec3 f = pile(mpos, mnorm) * 2.0 - 1.0;
	n = normalize(n + vec3(f.xy * pile_strength * fabric, 0.0));
	// the eyes are smooth glossy toy eyes: Meshy's sculpt wrinkles in them would crumple the gloss
	n = normalize(mix(n, vec3(0.0, 0.0, 1.0), m.b * 0.9));
	NORMAL_MAP = n * 0.5 + 0.5;
	// the fabric matte, the smile's thread (neither fabric nor eye) nearly so, the eyes glossy
	ROUGHNESS = mix(mix(0.9, 1.0, fabric), eye_roughness, m.b);
	SPECULAR = mix(mix(0.2, 0.1, fabric), 0.5, m.b);
	METALLIC = 0.0;
	RIM = sheen * fabric;
	RIM_TINT = sheen_tint;
}
