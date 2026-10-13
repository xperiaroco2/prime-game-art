// The House props' `fine` pack (docs/decisions/2026-10-13-house-world-look.md, docs/props.md "World look rules"):
// one shared opaque material for the world look's props. The paint is the vertex colour (COLOR_0, sRGB-encoded,
// the role's hex); its alpha picks the layer: k = round((1 - a) * 16) (prop_geom.FINE_STEP). Layers 0-3 are
// textured: their grey detail is channel k of fine_d (linear, mean prop_lib.FINE_DETAIL_MEAN; layer_gain is the
// inverse of its measured mean, so the paint keeps its hex on average) and their normal's XY is fine_n0.rg, .ba,
// fine_n1.rg or .ba; Godot rebuilds the normal's Z. The other layers are flat finishes. Per-layer roughness,
// metallic and normal strength are props/library.toml's [fine] layers; prop_materials.gd sets them from fine.json.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D fine_d : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D fine_n0 : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D fine_n1 : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 layer_gain = vec4(2.0);
uniform float layer_roughness[16];
uniform float layer_metallic[16];
uniform float layer_normal_strength[16];

varying flat int v_layer;
varying vec3 v_paint;

vec3 srgb_to_linear(vec3 c) {
	return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

void vertex() {
	v_layer = clamp(int(round((1.0 - COLOR.a) * 16.0)), 0, 15);
	v_paint = srgb_to_linear(COLOR.rgb);
}

void fragment() {
	float detail = 1.0;
	vec2 nxy = vec2(0.5);
	if (v_layer < 4) {
		vec4 d = texture(fine_d, UV);
		vec4 n = v_layer < 2 ? texture(fine_n0, UV) : texture(fine_n1, UV);
		detail = d[v_layer] * layer_gain[v_layer];
		nxy = (v_layer % 2 == 0) ? n.rg : n.ba;
	}
	ALBEDO = clamp(v_paint * detail, vec3(0.0), vec3(1.0));
	ROUGHNESS = layer_roughness[v_layer];
	METALLIC = layer_metallic[v_layer];
	NORMAL_MAP = vec3(nxy, 1.0);
	NORMAL_MAP_DEPTH = v_layer < 4 ? layer_normal_strength[v_layer] : 0.0;
}
