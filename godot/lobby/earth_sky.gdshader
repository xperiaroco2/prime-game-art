// The lobby window's night Earth from low orbit (art #356, docs/lobby.md "Step 3b"), a sky shader: the planet, its
// atmosphere rim and the stars at infinity, so nothing shifts as the player walks. Earth imagery: NASA (Black Marble
// 2016 for the night, Blue Marble for land and sea, the cloud map; sources/nasa_earth_lobby.toml, licence NASA-PD).
// The planet is a unit sphere whose centre lies along earth_dir at the distance that gives it earth_radius_deg; each
// view ray that hits it reads the maps at the hit's latitude and longitude, turned so that `subpoint` faces the eye
// with north up. The radiance cubemap pass (reflections) draws a neutral grey sky instead, the review light's own.
shader_type sky;

uniform sampler2D night_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D day_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D cloud_tex : filter_linear_mipmap_anisotropic, repeat_enable;

uniform vec3 earth_dir = vec3(0.0, -0.3746, 0.9272);   // toward the planet's centre (world, unit)
uniform float earth_radius_deg = 48.0;                // the disc's angular radius
uniform vec2 subpoint = vec2(24.0, 18.0);             // [lat, lon] degrees: the surface point nearest the eye
uniform float roll_deg = 0.0;                         // the planet's north turned about earth_dir
uniform vec3 sun_dir = vec3(0.0, -0.3746, 0.9272);    // toward the sun (world, unit)
uniform float sun_energy = 0.0;                       // 0: full night

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
uniform float stars_energy = 1.6;
uniform float stars_density = 1.0;

// the neutral review sky for the reflections only (hall.gd's former ProceduralSkyMaterial)
uniform float draw_earth = 1.0;     // step 4c: 0 when the Earth is an object (earth_object.gdshader): stars only
uniform float cubemap_earth = 0.0;   // step 4: 1 draws the Earth in the radiance pass too (the probes, the floor)
uniform vec3 neutral_top = vec3(0.55, 0.56, 0.6);
uniform vec3 neutral_horizon = vec3(0.5, 0.5, 0.52);
uniform vec3 neutral_ground = vec3(0.35, 0.35, 0.36);
uniform vec3 neutral_bottom = vec3(0.25, 0.25, 0.26);

const float AA = 0.0009;   // the limb's soft edge, radians (about a pixel at 75 deg and 1080 px)

vec3 neutral(vec3 v) {
	float y = clamp(v.y, -1.0, 1.0);
	float c = asin(y) / (PI * 0.5);
	if (y >= 0.0) {
		return mix(neutral_horizon, neutral_top, clamp(1.0 - pow(1.0 - c, 1.0 / 0.15), 0.0, 1.0));
	}
	return mix(neutral_ground, neutral_bottom, clamp(1.0 - pow(1.0 + c, 1.0 / 0.02), 0.0, 1.0));
}

vec3 hash32(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yxz + 33.33);
	return fract((p3.xxy + p3.yzz) * p3.zyx);
}

// one layer of stars: a grid on the cube face the ray points through, at most one star per cell, kept inside it
vec3 star_layer(vec3 v, float cells, float chance, float bright) {
	vec3 a = abs(v);
	vec2 uv;
	float face;
	if (a.x >= a.y && a.x >= a.z) {
		uv = v.yz / a.x; face = v.x > 0.0 ? 0.0 : 1.0;
	} else if (a.y >= a.z) {
		uv = v.xz / a.y; face = v.y > 0.0 ? 2.0 : 3.0;
	} else {
		uv = v.xy / a.z; face = v.z > 0.0 ? 4.0 : 5.0;
	}
	vec2 p = uv * cells;
	vec2 cell = floor(p);
	vec3 h = hash32(cell + face * 1013.0);
	if (h.z > chance) {
		return vec3(0.0);
	}
	vec2 at = cell + 0.25 + 0.5 * h.xy;
	float sigma = 0.0007 * cells;   // about 0.6 px
	float d2 = dot(p - at, p - at);
	float b = bright * pow(fract(h.z * 91.7), 6.0) * exp(-d2 / (2.0 * sigma * sigma));
	vec3 tint = mix(vec3(0.72, 0.82, 1.0), vec3(1.0, 0.86, 0.7), fract(h.x * 53.1));
	return tint * b;
}

void sky() {
	vec3 v = normalize(EYEDIR);
	if (AT_CUBEMAP_PASS && cubemap_earth < 0.5) {
		COLOR = neutral(v);
	} else if (!AT_CUBEMAP_PASS && draw_earth < 0.5) {   // step 4c: the visible Earth is the object; the stars stay
		COLOR = (star_layer(v, 110.0, 0.07 * stars_density, 4.0) + star_layer(v, 260.0, 0.06 * stars_density, 1.0)) * stars_energy;
	} else {
		float alpha = radians(earth_radius_deg);
		float d = 1.0 / sin(alpha);
		vec3 C = earth_dir * d;
		float ang = acos(clamp(dot(v, earth_dir), -1.0, 1.0));
		float edge = ang - alpha;                 // < 0 on the disc
		float cover = smoothstep(AA, -AA, edge);
		vec3 col = vec3(0.0);
		float mu = 0.0;
		if (edge < AA) {
			float b = dot(v, C);
			float disc = max(b * b - (d * d - 1.0), 0.0);
			vec3 N = normalize(v * (b - sqrt(disc)) - C);
			mu = clamp(dot(N, -v), 0.0, 1.0);
			// the planet's frame: f toward the eye, u its north on screen, r east (right)
			vec3 f = -earth_dir;
			vec3 up = abs(f.y) > 0.99 ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
			vec3 u0 = normalize(up - f * dot(up, f));
			vec3 r0 = normalize(cross(earth_dir, u0));
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
		// the atmosphere: a thin bright rim at the limb, a little haze inside it and a faint halo outside
		float w = radians(rim_width_deg);
		float sunward = sun_energy * pow(max(dot(v, sun_dir), 0.0), 70.0);
		float rim = edge > 0.0 ? exp(-edge / w) + 0.04 * exp(-edge / (5.0 * w)) : exp(edge / (1.5 * w)) * 0.8 + pow(1.0 - mu, 14.0) * 0.12;
		vec3 rim_c = mix(rim_rgb, dawn_rgb, clamp(sunward * 1.2, 0.0, 0.85));
		vec3 atmo = rim_c * rim * rim_energy * (1.0 + 4.0 * sunward);
		atmo += dawn_rgb * sun_energy * pow(max(dot(v, sun_dir), 0.0), 600.0) * 0.8 * (1.0 - cover);
		vec3 stars = star_layer(v, 110.0, 0.07 * stars_density, 4.0) + star_layer(v, 260.0, 0.06 * stars_density, 1.0);
		stars *= stars_energy * (1.0 - cover) * (1.0 - clamp(rim * 2.0, 0.0, 1.0));
		COLOR = col * cover + atmo + stars;
	}
}
