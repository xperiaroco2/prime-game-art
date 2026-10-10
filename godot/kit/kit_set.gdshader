// The House kit's `set` material (art #86, look.md section 5; docs/kit.md "Materials"): plaster, wood and concrete in
// one material. The paint is the vertex colour (COLOR_0, sRGB-encoded); its alpha picks the layer: 1.0 plaster,
// 0.75 wood, 0.5 concrete (kit_geom.layer_alpha), i.e. layer = round((1 - a) * 4). The layer's grey detail is one
// channel of set_d (sRGB, linear mean kit_geom.TEX_MEAN, which the paint is already divided by), its normal's XY is
// set_n0.rg (layer 0), set_n0.ba (layer 1) or set_n1.rg (layer 2); Godot rebuilds the normal's Z. Opaque.
// The per-layer roughness and normal strength are the spec's materials.<layer>.roughness and .normal_strength;
// kit_materials.gd sets them from the request, the defaults below are kits/house.json v2's.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D set_d : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D set_n0 : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D set_n1 : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec3 layer_roughness = vec3(0.88, 0.72, 0.92);
uniform vec3 layer_normal_strength = vec3(0.15, 0.4, 0.3);
// Per-room wall paint (Q11 = B, docs/house.md "Wall paint"; kit_materials.gd `paint`): a plaster fragment whose vertex
// colour is the inner plaster's (paint_from, sRGB-encoded) and whose world position lies in a painted room's rect
// (x0, z0, x1, z1) and band of heights takes that room's paint_to. A wall's two faces sit 0.1 m either side of its
// grid line, so each face takes the paint of the room it faces. paint_count 0: the kit's own paint.
const int MAX_PAINTS = 16;
uniform int paint_count = 0;
uniform vec3 paint_from = vec3(0.0);
uniform vec4 paint_rect[MAX_PAINTS];
uniform vec2 paint_band[MAX_PAINTS];
uniform vec3 paint_to[MAX_PAINTS];

varying flat int v_layer;
varying vec3 v_paint;
varying vec3 v_raw;
varying vec3 v_world;

vec3 srgb_to_linear(vec3 c) {
	return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

void vertex() {
	v_layer = clamp(int(round((1.0 - COLOR.a) * 4.0)), 0, 2);
	v_paint = srgb_to_linear(COLOR.rgb);
	v_raw = COLOR.rgb;
	v_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec3 d = texture(set_d, UV).rgb;
	vec4 n0 = texture(set_n0, UV);
	vec2 n1 = texture(set_n1, UV).rg;
	float detail = d.r;
	vec2 nxy = n0.rg;
	if (v_layer == 1) {
		detail = d.g;
		nxy = n0.ba;
	} else if (v_layer == 2) {
		detail = d.b;
		nxy = n1;
	}
	vec3 paint = v_paint;
	if (paint_count > 0 && v_layer == 0 && distance(v_raw, paint_from) < 0.01) {
		for (int i = 0; i < min(paint_count, MAX_PAINTS); i++) {
			vec4 r = paint_rect[i];
			vec2 b = paint_band[i];
			if (v_world.x > r.x && v_world.x < r.z && v_world.z > r.y && v_world.z < r.w
					&& v_world.y > b.x && v_world.y < b.y) {
				paint = srgb_to_linear(paint_to[i]);
				break;
			}
		}
	}
	ALBEDO = paint * detail;
	ROUGHNESS = layer_roughness[v_layer];
	METALLIC = 0.0;
	NORMAL_MAP = vec3(nxy, 1.0);
	NORMAL_MAP_DEPTH = layer_normal_strength[v_layer];
}
