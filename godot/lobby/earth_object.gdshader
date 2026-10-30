// The lobby window's night Earth as an object (art #356, docs/lobby.md "Step 4c"): a sphere of radius `radius` at a
// finite distance south of the window, so it shows parallax against the mullions and shrinks as the player backs
// away (step 3b's sky Earth sat at infinity and kept its angular size while the window's changed). Earth imagery:
// NASA (sources/nasa_earth_lobby.toml, licence NASA-PD). The same maps, city lights, clouds, atmosphere rim and dawn
// glow as earth_sky.gdshader, traced per pixel from the camera: the mesh is a shell `shell` times the planet's radius
// drawn by its back faces only (cull_front), far beyond the hall, so it never cuts the hall's geometry and the rim's
// halo has room outside the limb; premultiplied alpha over the sky's stars, which stay at infinity.
shader_type spatial;
render_mode unshaded, cull_front, depth_draw_never, blend_premul_alpha, fog_disabled, shadows_disabled;

uniform sampler2D night_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D day_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D cloud_tex : filter_linear_mipmap_anisotropic, repeat_enable;

uniform vec3 centre = vec3(0.0, -110.0, 280.0);      // the planet's centre (world)
uniform float radius = 220.0;                        // its radius, metres
uniform vec3 frame_dir = vec3(0.0, 0.3746, -0.9272); // from the centre toward the spawn: the map's frame, fixed
uniform float ref_radius_deg = 48.0;                 // its angular radius from the spawn: the rim's width is set there
uniform vec2 subpoint = vec2(24.0, 18.0);            // [lat, lon] degrees: the surface point facing the spawn
uniform float roll_deg = 0.0;
uniform vec3 sun_dir = vec3(0.0, -0.3746, 0.9272);   // toward the sun (world, unit; at infinity)
uniform float sun_energy = 0.0;

uniform vec3 lights_rgb = vec3(1.0, 0.52, 0.2);
uniform float lights_energy = 6.0;
uniform float base_energy = 3.0;
uniform vec3 moon_rgb = vec3(0.35, 0.45, 0.7);
uniform float moon_energy = 0.12;
uniform float cloud_energy = 0.11;
uniform vec3 rim_rgb = vec3(0.25, 0.55, 1.0);
uniform float rim_energy = 2.4;
uniform float rim_width_deg = 0.35;
uniform vec3 dawn_rgb = vec3(1.0, 0.55, 0.25);

const float AA = 0.0009;

void fragment() {
	vec3 eye = CAMERA_POSITION_WORLD;
	vec3 wpos = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 v = normalize(wpos - eye);
	vec3 oc = centre - eye;
	float dist = length(oc);
	vec3 to_c = oc / dist;
	float alpha = asin(clamp(radius / dist, 0.0, 1.0));
	float ang = acos(clamp(dot(v, to_c), -1.0, 1.0));
	float edge = ang - alpha;                 // < 0 on the disc (radians)
	float cover = smoothstep(AA, -AA, edge);
	vec3 col = vec3(0.0);
	float mu = 0.0;
	if (edge < AA) {
		float b = dot(v, oc);
		float disc = max(b * b - (dist * dist - radius * radius), 0.0);
		vec3 N = normalize(eye + v * (b - sqrt(disc)) - centre);
		mu = clamp(dot(N, -v), 0.0, 1.0);
		vec3 f = frame_dir;
		vec3 up = abs(f.y) > 0.99 ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
		vec3 u0 = normalize(up - f * dot(up, f));
		vec3 r0 = normalize(cross(-f, u0));
		float rr = radians(roll_deg);
		vec3 u = cos(rr) * u0 + sin(rr) * r0;
		vec3 r = cos(rr) * r0 - sin(rr) * u0;
		float lx = dot(N, r), ly = dot(N, u), lz = dot(N, f);
		float p0 = radians(subpoint.x), l0 = radians(subpoint.y);
		vec3 s = vec3(cos(p0) * cos(l0), sin(p0), -cos(p0) * sin(l0));
		vec3 e = vec3(-sin(l0), 0.0, -cos(l0));
		vec3 n = vec3(-sin(p0) * cos(l0), cos(p0), sin(p0) * sin(l0));
		vec3 g = normalize(lx * e + ly * n + lz * s);
		float lat = asin(clamp(g.y, -1.0, 1.0));
		float lon = atan(-g.z, g.x);
		vec2 uv = vec2((lon + PI) / (2.0 * PI), (PI * 0.5 - lat) / PI);
		vec3 night = texture(night_tex, uv).rgb;
		vec3 day = texture(day_tex, uv).rgb;
		float cloud = smoothstep(0.12, 0.85, texture(cloud_tex, uv).r);
		float lum = dot(night, vec3(0.2126, 0.7152, 0.0722));
		float city = smoothstep(0.012, 0.12, lum);
		float lit = sun_energy * smoothstep(-0.03, 0.1, dot(N, sun_dir));
		vec3 lights = lights_rgb * lum * lights_energy * city * (1.0 - 0.6 * cloud) * (1.0 - lit);
		col = night * (1.0 - city) * base_energy * 0.05 + day * moon_rgb * moon_energy + lights;
		col = col * (1.0 - 0.5 * cloud) + moon_rgb * cloud * cloud_energy;
		col = mix(col, (day * (1.0 - cloud) + vec3(cloud)) * 1.6, lit);
	}
	// the atmosphere as in the sky shader; its width scales with the planet's angular size (a shell of fixed metres)
	float w = radians(rim_width_deg) * alpha / radians(ref_radius_deg);
	float sunward = sun_energy * pow(max(dot(v, sun_dir), 0.0), 70.0);
	float rim = edge > 0.0 ? exp(-edge / w) + 0.04 * exp(-edge / (5.0 * w)) : exp(edge / (1.5 * w)) * 0.8 + pow(1.0 - mu, 14.0) * 0.12;
	vec3 rim_c = mix(rim_rgb, dawn_rgb, clamp(sunward * 1.2, 0.0, 0.85));
	vec3 atmo = rim_c * rim * rim_energy * (1.0 + 4.0 * sunward);
	atmo += dawn_rgb * sun_energy * pow(max(dot(v, sun_dir), 0.0), 600.0) * 0.8 * (1.0 - cover);
	ALBEDO = col * cover + atmo;
	ALPHA = clamp(cover + clamp(rim * 2.0, 0.0, 1.0), 0.0, 1.0);   // the stars behind fade as in the sky shader
}
