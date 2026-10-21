// M11b (art #196, brief UPDATE 23): the lash liner (eye_<design>_liner_<side>), the lashes' look (alien.gd LASH_LOOK)
// with a least screen width. Up close the liner keeps its modelled shape; farther away, where its band would cover
// less than `min_px` pixels, each vertex moves out along its normal by a share of the missing width (the band's edges'
// normals run along the roll, so the band widens on screen), so the lash line stays one unbroken dark line at the
// game's distances, where the tubes have faded out (LASH_FADE_M).
shader_type spatial;
render_mode cull_back;

uniform vec3 albedo : source_color = vec3(0.035, 0.03, 0.04);
uniform float roughness_value = 0.32;
uniform float specular_value = 0.55;
uniform float clearcoat_value = 0.6;
uniform float clearcoat_roughness_value = 0.15;
uniform float min_px = 2.0;  // the least width of the band on screen, pixels
uniform float band_m = 0.004;  // the band's own width as seen from the front, metres
uniform float grow_share = 0.55;  // growth per metre of missing width (the two edges spread about 1.8 times it)
uniform float max_grow_m = 0.004;  // never more (alien.gd turns the liner's shadow off: a light's shadow camera stands
// far away, so the growth there would balloon the band over the face)

void vertex() {
	vec3 world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float dist = length(world - CAMERA_POSITION_WORLD);
	float px = 2.0 * dist / (PROJECTION_MATRIX[1][1] * VIEWPORT_SIZE.y);  // one pixel's size at that distance
	float grow = clamp((min_px * px - band_m) * grow_share, 0.0, max_grow_m);
	float scale = length((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	VERTEX += NORMAL * grow / max(scale, 1e-6);
}

void fragment() {
	ALBEDO = albedo;
	ROUGHNESS = roughness_value;
	SPECULAR = specular_value;
	CLEARCOAT = clearcoat_value;
	CLEARCOAT_ROUGHNESS = clearcoat_roughness_value;
}
