// One shell of the vault plush's pile (art#297, step 3): the mesh drawn again, pushed out along its normal by
// `layer` of the pile's length (fur longer than velour, none on the eyes), keeping only thin tapering strands. The
// strands are cells of the unpushed model-space position, so every shell cuts the same strands higher up and thinner.
// plush.gd chains the shells as next passes of the surface material. Beyond fade_far metres the shells draw nothing:
// a few pixels of fuzz are left to the surface's rim there.
shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx, cull_back;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform sampler2D mask_tex : filter_linear_mipmap, repeat_disable;
uniform float layer : hint_range(0.0, 1.0) = 0.5;  // this shell's height, 0 at the surface, 1 at the tips
uniform float fur_len = 0.0026;     // metres
uniform float velour_len = 0.0011;
uniform float strands_per_m = 1100.0;
uniform float sheen : hint_range(0.0, 1.0) = 0.55;
uniform float sheen_tint : hint_range(0.0, 1.0) = 0.85;
uniform float fade_far = 6.0;

varying vec3 base_pos;

float hash(vec3 p) {
	p = fract(p * vec3(0.1031, 0.1030, 0.0973));
	p += dot(p, p.yxz + 33.33);
	return fract((p.x + p.y) * p.z);
}

void vertex() {
	base_pos = VERTEX;
	vec3 m = textureLod(mask_tex, UV, 0.0).rgb;
	float len = m.r * fur_len + m.g * velour_len;
	VERTEX += NORMAL * len * layer;
}

void fragment() {
	float dist = length(VERTEX);
	if (dist > fade_far) {
		discard;
	}
	// past arm's length a strand is under a pixel: the strands thicken and their shade flattens with distance, so the
	// pile reads as a soft fuzzy edge, not as sparkling noise
	float far = clamp((dist - 0.5) / 1.5, 0.0, 1.0);
	vec3 m = texture(mask_tex, UV).rgb;
	float fabric = clamp(m.r + m.g, 0.0, 1.0);
	if (fabric < 0.5) {
		discard;
	}
	vec3 p = base_pos * strands_per_m;
	vec3 cell = floor(p);
	float r = hash(cell);
	// each strand sits off its cell's middle by its own random amount, so the strands never line up in a grid
	vec3 jitter = vec3(hash(cell + 17.0), hash(cell + 41.0), hash(cell + 83.0)) - 0.5;
	vec3 off = fract(p) - 0.5 - jitter * 0.55;
	float radius = mix(0.32, 0.52, hash(cell + 7.0)) * (1.0 - layer * 0.85) + far * 0.35;
	if (length(off) > radius || r < layer * 0.75) {
		discard;
	}
	vec3 base = texture(albedo_tex, UV).rgb;
	ALBEDO = base * mix(mix(0.78, 1.0, layer) * mix(0.93, 1.04, r), 1.0, far);
	ROUGHNESS = 1.0;
	SPECULAR = 0.1;
	RIM = sheen * fabric;
	RIM_TINT = sheen_tint;
}
