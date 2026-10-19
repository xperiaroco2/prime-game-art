// The alien's hand-made plasticine skin (art #196, step G3). Shared body of alien_clay.gdshader (the micro-detail
// tiled in the sheets' UV space) and alien_clay_tri.gdshader (TRIPLANAR: tiled in the mesh's model space).
// Inputs: the baked base colour and normal (the 2048 game sheets at a clay strength), the tiling micro-detail normal
// and height from the master's bake (fingerprint whorls and smudges, 1024, one tile = 7 cm of skin). Output: a soft
// waxy sheen (roughness about 0.55, a low specular, a light rim) with Godot's subsurface scattering in skin mode;
// the scattering needs the project's SSS quality above disabled. The eyes never use this shader.
// MICRO_MIX (step G3b, alien_clay_mix.gdshader): the tile's repetition is broken by a second sample of the same tile,
// rotated, offset and at another scale, blended with the first by a low-frequency value-noise mask in UV space
// (variance-preserving, so the mix keeps the single tile's contrast); still UV space, so nothing slides when the
// body bends. ALBEDO_FIX (calibration only, alien_clay_cal.gdshader): a linear colour matrix on the base colour, the
// matrix G3b's colour calibration then baked into the base colour sheets.
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx, sss_mode_skin;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D micro_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D micro_height : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
// UV mode: tiles per UV unit, so that one tile covers 7 cm of skin on this sheet (bake.json micro.uv_scale).
uniform float micro_uv_scale = 9.5;
// TRIPLANAR mode: tiles per metre of model space.
uniform float micro_per_m = 14.29;
uniform float micro_strength : hint_range(0.0, 3.0) = 1.0;
uniform float normal_depth : hint_range(0.0, 2.0) = 1.0;
uniform float roughness_base : hint_range(0.0, 1.0) = 0.55;
uniform float roughness_groove : hint_range(0.0, 0.5) = 0.12;
uniform float cavity : hint_range(0.0, 1.0) = 0.12;
uniform float specular_level : hint_range(0.0, 1.0) = 0.3;
uniform float rim_amount : hint_range(0.0, 1.0) = 0.25;
uniform float rim_tint_amount : hint_range(0.0, 1.0) = 0.6;
uniform float sss_strength : hint_range(0.0, 1.0) = 0.25;
#ifdef MICRO_MIX
uniform float mix_scale = 0.81;  // the second sample's scale against the first
uniform float mix_angle = 2.2;  // and its rotation (radians)
uniform vec2 mix_offset = vec2(0.37, 0.61);
uniform float mix_freq = 0.63;  // the mask's noise cells per tile (incommensurate with the tile)
#endif
#ifdef ALBEDO_FIX
uniform vec3 fix_c0 = vec3(1.0, 0.0, 0.0);  // the colour matrix's columns, linear light
uniform vec3 fix_c1 = vec3(0.0, 1.0, 0.0);
uniform vec3 fix_c2 = vec3(0.0, 0.0, 1.0);
#endif

#ifdef TRIPLANAR
varying vec3 v_pos;
varying vec3 v_nrm;

void vertex() {
	// Godot skins the mesh before vertex(): this is the posed model-space position, so the pattern slides a little
	// over the skin where the body bends (the reason the UV mode is the recommended one).
	v_pos = VERTEX * micro_per_m;
	v_nrm = NORMAL;
}
#endif

vec2 unpack_xy(vec4 t) {
	return t.xy * 2.0 - 1.0;
}

#ifdef MICRO_MIX
float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash21(i), hash21(i + vec2(1.0, 0.0)), f.x),
			mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), f.x), f.y);
}
#endif

void fragment() {
	vec2 base_xy = unpack_xy(texture(normal_tex, UV)) * normal_depth;
#ifdef TRIPLANAR
	vec3 w = pow(abs(normalize(v_nrm)), vec3(4.0));
	w /= (w.x + w.y + w.z);
	vec2 mx = unpack_xy(texture(micro_normal, v_pos.zy));
	vec2 my = unpack_xy(texture(micro_normal, v_pos.xz));
	vec2 mz = unpack_xy(texture(micro_normal, v_pos.xy));
	float h = texture(micro_height, v_pos.zy).r * w.x + texture(micro_height, v_pos.xz).r * w.y
			+ texture(micro_height, v_pos.xy).r * w.z;
	// the projections' tangent-space slopes as a model-space offset (UDN blend), then into view space
	vec3 d = vec3(0.0, mx.y, mx.x) * w.x + vec3(my.x, 0.0, my.y) * w.y + vec3(mz.x, mz.y, 0.0) * w.z;
	vec3 dv = (VIEW_MATRIX * vec4(MODEL_NORMAL_MATRIX * d, 0.0)).xyz;
	vec3 nb = vec3(base_xy, sqrt(max(0.0, 1.0 - dot(base_xy, base_xy))));
	// needs the mesh's tangents (the export writes them for the normal map); without them the base normal collapses
	vec3 n = TANGENT * nb.x + BINORMAL * nb.y + NORMAL * nb.z;
	NORMAL = normalize(n + dv * micro_strength);
#else
	vec2 muv = UV * micro_uv_scale;
#ifdef MICRO_MIX
	float ca = cos(mix_angle);
	float sa = sin(mix_angle);
	mat2 rot = mat2(vec2(ca, sa), vec2(-sa, ca));
	vec2 muv2 = rot * (muv * mix_scale) + mix_offset;
	vec2 m1 = unpack_xy(texture(micro_normal, muv));
	// the second sample's slopes back into the sheet's tangent frame: the chain rule of h(R k p + o) is k R^T grad h
	vec2 m2 = transpose(rot) * unpack_xy(texture(micro_normal, muv2)) * mix_scale;
	float w = smoothstep(0.3, 0.7, value_noise(muv * mix_freq + vec2(17.0, 5.0)));
	float keep = inversesqrt(w * w + (1.0 - w) * (1.0 - w));  // two uncorrelated samples: keep the contrast
	vec2 m = mix(m1, m2, w) * keep * micro_strength;
	float h = 0.5 + (mix(texture(micro_height, muv).r, texture(micro_height, muv2).r, w) - 0.5) * keep;
#else
	vec2 m = unpack_xy(texture(micro_normal, muv)) * micro_strength;
	float h = texture(micro_height, muv).r;
#endif
	vec2 xy = base_xy + m;  // whiteout-style: the slopes add
	NORMAL_MAP = vec3(xy * 0.5 + 0.5, 1.0);
	NORMAL_MAP_DEPTH = 1.0;
#endif
	float groove = clamp((0.5 - h) * 2.0, -1.0, 1.0);  // above 0: a fingerprint groove or a smudge's hollow
	vec3 albedo = texture(albedo_tex, UV).rgb;
#ifdef ALBEDO_FIX
	albedo = clamp(mat3(fix_c0, fix_c1, fix_c2) * albedo, 0.0, 1.0);
#endif
	ALBEDO = albedo * (1.0 - cavity * groove);
	ROUGHNESS = clamp(roughness_base + roughness_groove * groove, 0.0, 1.0);
	SPECULAR = specular_level;
	RIM = rim_amount;
	RIM_TINT = rim_tint_amount;
	SSS_STRENGTH = sss_strength;
}
