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
// step 5a4: the cap, a [lat0, lat1] x [lon0, lon1] degree box (cap_box) of the night and cloud maps at the sources' full
// resolution, where the window shows the globe up close; the global maps outside it, faded over cap_fade_deg
uniform sampler2D night_cap_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D cloud_cap_tex : filter_linear_mipmap_anisotropic, repeat_disable;
uniform vec4 cap_box = vec4(-8.0, 82.0, -48.0, 72.0);
uniform float cap_fade_deg = 3.0;
uniform float cap_on = 0.0;
// step 5a4: the cities as points: a light below city_ref is dimmed as lum^city_gamma (the halos round each city go,
// its bright core stays)
uniform float city_gamma = 1.8;
uniform float city_ref = 0.7;
// step 5a4: where soft (seen at a slant from the hall's far side) the cities dim by slant_dim, so the screen's glow does
// not swell each into a blob, and the moonlit clouds by cloud_calm (the snowy speckle)
uniform float slant_dim = 0.6;
uniform float cloud_calm = 0.45;

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
// step 5a3: from the hall's far side (a_entrance, corner_nw) the window shows the high north seen obliquely, where the
// equirectangular maps stretch: clouds as snowy speckle, cities as stretched blobs. There (mu * cos(latitude) low) the
// clouds are read soft_lod mips softer and lose contrast (step 5a4: the cities stay sharp, the cap gives them points);
// head-on (spawn_eye) stays as it was
uniform float soft_lod = 1.5;

// step 5a5: a night Earth from low orbit up close (corner_nw): light_cap caps each city pixel's brightest channel so the
// screen's glow (threshold 1) does not swell each city into a dot of ~5 px; halo_energy gives them a soft small halo
// of their own instead (the night map read halo_bias mips softer); cloud_city lights the clouds faintly from the cities
// below; cloud_shade is how much a cloud hides what is under it; haze_energy a little atmosphere over the surface at
// grazing angles, (1 - mu)^haze_pow. The defaults draw step 5a4's look
uniform float light_cap = 1000.0;
uniform float halo_energy = 0.0;
uniform float halo_bias = 2.5;
uniform float cloud_city = 0.0;
uniform float cloud_shade = 0.5;
uniform float haze_energy = 0.0;
uniform float haze_pow = 3.0;
// step 5a5: the day map under the moon, its bright land (December's snow on the north, deserts) compressed as
// day * (1 + moon_knee * 0.1) / (1 + moon_knee * day), so the snow does not read as white streaks; the dark blue sea
// (about 0.1) keeps its value
uniform float moon_knee = 0.0;
// step 5a6 (the engineer, 2026-10-31: less snow from the hall's corner): snow_cut takes the day map's white (its least
// channel, linear, over snow_lo..snow_hi: snow and ice, not the dark land or the sea) toward snow_rgb, a dark winter
// land, before the moon lights it; moon_land dims the moonlight on land (the sea told by its blue over red), so the sea
// and the coastlines keep theirs. The defaults draw step 5a5's look
uniform float snow_cut = 0.0;
uniform float snow_lo = 0.12;
uniform float snow_hi = 0.4;
uniform vec3 snow_rgb = vec3(0.03, 0.035, 0.025);
uniform float moon_land = 0.0;
// step 5a5: a debug paint (1: the cap's weight red, soft green, latitude lines every 10 deg white (thick at 0, 30, 60),
// longitude lines every 10 deg cyan (thick at 0); 0 draws the Earth)
uniform float debug_mode = 0.0;
// step 5a7: the far mode (docs/lobby.md "Step 5a7"): every ray starts at far_eye whatever the camera's place, and the
// shell moves with the camera by (camera - far_eye), so the planet sits at infinity: the same angular size, horizon
// height and direction from every point of the hall, the window framing a different part of it. 0: from the camera
uniform float far_mode = 0.0;
uniform vec3 far_eye = vec3(0.0, 1.65, 2.5);

const float AA = 0.0009;

void vertex() {
	if (far_mode > 0.5) {   // the node has no rotation or scale: a world offset is a model one
		VERTEX += CAMERA_POSITION_WORLD - far_eye;
	}
}

void fragment() {
	vec3 cam = CAMERA_POSITION_WORLD;
	vec3 eye = far_mode > 0.5 ? far_eye : cam;
	vec3 wpos = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 v = normalize(wpos - cam);
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
		float soft = 1.0 - smoothstep(0.15, 0.45, mu * cos(lat));
		float latd = degrees(lat), lond = degrees(lon);
		vec2 cuv = vec2((lond - cap_box.z) / (cap_box.w - cap_box.z), (cap_box.y - latd) / (cap_box.y - cap_box.x));
		float inside = min(min(latd - cap_box.x, cap_box.y - latd), min(lond - cap_box.z, cap_box.w - lond));
		float capw = cap_on * smoothstep(0.0, cap_fade_deg, inside);
		vec3 night = mix(texture(night_tex, uv).rgb, texture(night_cap_tex, cuv).rgb, capw);
		vec3 day = texture(day_tex, uv).rgb;
		float c_sharp = mix(texture(cloud_tex, uv).r, texture(cloud_cap_tex, cuv).r, capw);
		float c_soft = mix(textureLod(cloud_tex, uv, soft_lod).r, textureLod(cloud_cap_tex, cuv, soft_lod + 1.0).r, capw);
		float cloud = smoothstep(0.12, 0.85, mix(c_sharp, c_soft, soft));
		cloud = mix(cloud, 0.2 + 0.45 * cloud, soft);   // less cloud contrast where soft
		float lum = dot(night, vec3(0.2126, 0.7152, 0.0722));
		float pts = lum * pow(clamp(lum / city_ref, 0.0, 1.0), city_gamma - 1.0);
		float city = smoothstep(0.012, 0.12, lum) * (1.0 - slant_dim * soft);   // at a slant below the glow's bloom
		float lit = sun_energy * smoothstep(-0.03, 0.1, dot(N, sun_dir));
		vec3 lights = lights_rgb * pts * lights_energy * city * (1.0 - 0.6 * cloud) * (1.0 - lit);
		vec3 night_b = mix(texture(night_tex, uv, halo_bias).rgb, texture(night_cap_tex, cuv, halo_bias).rgb, capw);
		float lum_b = dot(night_b, vec3(0.2126, 0.7152, 0.0722));
		lights += lights_rgb * lum_b * halo_energy * (1.0 - cloud) * (1.0 - lit);
		lights *= min(1.0, light_cap / max(max(lights.r, lights.g), max(lights.b, 1e-4)));
		float snow = smoothstep(snow_lo, snow_hi, min(day.r, min(day.g, day.b))) * snow_cut;
		vec3 day_s = mix(day, snow_rgb, snow);
		float sea = smoothstep(1.6, 3.0, day.b / max(day.r, 0.002));
		vec3 day_m = day_s * (1.0 + moon_knee * 0.1) / (1.0 + moon_knee * day_s) * (1.0 - moon_land * (1.0 - sea));
		col = night * (1.0 - city) * base_energy * 0.05 + day_m * moon_rgb * moon_energy + lights;
		col = col * (1.0 - cloud_shade * cloud) + moon_rgb * cloud * cloud_energy * (1.0 - cloud_calm * soft);
		col += lights_rgb * lum_b * cloud * cloud_city * (1.0 - lit);
		col += rim_rgb * haze_energy * pow(1.0 - mu, haze_pow);
		col = mix(col, (day * (1.0 - cloud) + vec3(cloud)) * 1.6, lit);
		if (debug_mode > 0.5) {
			float la = abs(fract(latd / 10.0 + 0.5) - 0.5) * 10.0, lo = abs(fract(lond / 10.0 + 0.5) - 0.5) * 10.0;
			float big = (abs(latd) < 5.0 || abs(latd - 30.0) < 5.0 || abs(latd - 60.0) < 5.0) ? 0.6 : 0.25;
			float lob = abs(lond) < 5.0 ? 0.6 : 0.25;
			col = vec3(capw, soft, 0.0) * 0.5 + vec3(1.0) * (1.0 - smoothstep(0.0, big, la)) + vec3(0.0, 1.0, 1.0) * (1.0 - smoothstep(0.0, lob, lo));
		}
		if (debug_mode > 1.5) {   // step 5a6: 2 paints the snow mask red and the sea mask green
			col = vec3(snow, sea, 0.0) * 0.5;
		}
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
