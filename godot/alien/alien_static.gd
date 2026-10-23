extends RefCounted
## The alien pilot's static premium head (art #196): swaps the imported glTF material whose name ends in
## "_static_skin" for the alien_static.gdshader ShaderMaterial (its albedo and normal textures kept) and sets the
## player's skin colour. Use with preload (no class cache in a -s script):
##   const AlienStatic = preload("res://alien/alien_static.gd")
##   var mats := AlienStatic.apply(head, mask_texture, Color(0.39, 0.77, 0.76))  # base_skin: the build's sRGB median
##   (optional 4th and 5th arguments: the detail texture, `<head>_detail.png`, for the "alive" levers, and the
##   plain albedo, `<head>_albedo_plain.png`, for alive_mix; the 6th another shader: SHADER_288, the merged #288
##   shader kept as it was, for the review's "before" rows)
##   AlienStatic.set_skin(mats, Color("e98a8c"))
## The colour slots (2026-10-23): apply()'s 7th and 8th arguments, the accent mask (`<head>_accent.png` beside the
## GLB: R lips, G details, B the pale front, A 1 - the gills) and its bases ({"lips", "detail", "front"}: the sRGB
## medians in `<head>_accent.json`); then
##   AlienStatic.set_colours(mats, {"skin": Color(...), "lips": Color(...), "detail": Color(...), "detail_on": true})
## (a slot left out keeps the build's own paint; set_colours(mats, {}) is the merged look) or a preset:
##   AlienStatic.set_colours(mats, AlienStatic.PRESETS[1]["picks"])
## The guard rails (here, in CIELAB; tools/blender/alien_colour_geom.py holds the same maths and its tests) act on
## every picked colour before it reaches the shader, which does the recolour in sRGB HSV.

const SHADER: Shader = preload("res://alien/alien_static.gdshader")
const SHADER_288: Shader = preload("res://alien/alien_static_288.gdshader")  # static_v5: #288's look, byte for byte
const SUFFIX: String = "_static_skin"

## The guard rails per slot: [chroma cap C*, L* min, L* max, dark knee, light knee] (CIELAB, D65; the cap scaled by
## (L* + 15) / (dark + 15) below the dark knee, by (100 - L*) / (100 - light) above the light knee; null: none).
const RAILS: Dictionary = {"skin": [40.0, 35.0, 85.0, 55.0, null], "lips": [42.0, 25.0, 80.0, null, 70.0],
	"detail": [42.0, 20.0, 85.0, null, 70.0], "front": [16.0, 82.0, 93.0, null, null]}
## Hue bands with a lower cap: [centre, half width (hue degrees), the cap's factor at the centre]: yellow-green, hot pink.
const BANDS: Array = [[125.0, 35.0, 0.7], [345.0, 40.0, 0.8]]
const LIP_CONTRAST: float = 12.0  # CIE76 delta E, lips against the skin
const FRONT_SAT_GAIN: float = 1.4  # a front texel's HSV saturation never above max(its own, this x the target's)
const WHITE := Vector3(0.95047, 1.0, 1.08883)

## The study's E palettes (E1: the build's own paint).
const PRESETS: Array[Dictionary] = [
	{"name": "alien teal", "picks": {}},
	{"name": "coral reef", "picks": {"skin": "#e39c8c", "lips": "#a2575a", "detail": "#a2575a", "detail_on": true}},
	{"name": "lilac", "picks": {"skin": "#a99cd8", "lips": "#6c5896", "detail": "#6c5896", "detail_on": true}},
	{"name": "honey", "picks": {"skin": "#e2c07a", "lips": "#a96e51", "detail": "#a96e51", "detail_on": true}},
	{"name": "cobalt", "picks": {"skin": "#6c87c6", "lips": "#d48c72", "detail": "#d48c72", "detail_on": true}},
	{"name": "sage", "picks": {"skin": "#8fb99f", "lips": "#4e7a65", "detail": "#4e7a65", "detail_on": true}},
	{"name": "plum", "picks": {"skin": "#a07596", "lips": "#5c3a5a", "detail": "#5c3a5a", "detail_on": true}},
	{"name": "slate", "picks": {"skin": "#7f98a8", "lips": "#c98a7e", "detail": "#c98a7e", "detail_on": true}},
]

## A curated skin palette (sRGB); the build's own teal comes first at run time.
const PALETTE: Array[Color] = [Color(0.93, 0.55, 0.56), Color(0.64, 0.56, 0.92), Color(0.98, 0.78, 0.30),
	Color(0.30, 0.50, 0.90)]


## Replaces every "_static_skin" surface material under root; returns the new ShaderMaterials.
static func apply(root: Node, mask: Texture2D, base_skin: Color, detail: Texture2D = null,
		plain: Texture2D = null, shader: Shader = null, accent: Texture2D = null,
		bases: Dictionary = {}) -> Array[ShaderMaterial]:
	var made: Array[ShaderMaterial] = []
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = node
		for i: int in mi.mesh.get_surface_count():
			var src: Material = mi.get_active_material(i)
			if not (src is BaseMaterial3D) or not src.resource_name.ends_with(SUFFIX):
				continue
			var base3d: BaseMaterial3D = src
			var sm := ShaderMaterial.new()
			sm.resource_name = src.resource_name
			sm.shader = shader if shader != null else SHADER
			sm.set_shader_parameter("albedo_tex", base3d.albedo_texture)
			sm.set_shader_parameter("normal_tex", base3d.normal_texture)
			sm.set_shader_parameter("mask_tex", mask)
			if detail != null:
				sm.set_shader_parameter("detail_tex", detail)
			if plain != null:  # static_v3: the albedo without the baked alive layers, for alive_mix
				sm.set_shader_parameter("plain_tex", plain)
			sm.set_shader_parameter("base_skin", base_skin)
			sm.set_shader_parameter("skin_color", base_skin)
			if accent != null:
				sm.set_shader_parameter("accent_tex", accent)
			var b: Dictionary = {"skin": base_skin}
			for k: String in ["lips", "detail", "front"]:
				b[k] = _pick(bases[k]) if bases.has(k) else base_skin
			sm.set_meta("colour_bases", b)
			_put(sm, slot_colours(b, {}))
			mi.set_surface_override_material(i, sm)
			made.append(sm)
	return made


## The player's skin colour (sRGB) on every material apply() made.
static func set_skin(mats: Array[ShaderMaterial], color: Color) -> void:
	set_colours(mats, {"skin": color})


## The player's colour slots on every material apply() made: picks holds any of "skin", "lips", "detail" (Color,
## "#rrggbb" or [r, g, b]), "detail_on" (default: true when "detail" is picked), "gills_detail" (default true).
## Returns the uniforms set (sRGB), the same for every material of one head.
static func set_colours(mats: Array[ShaderMaterial], picks: Dictionary) -> Dictionary:
	var u: Dictionary = {}
	for sm: ShaderMaterial in mats:
		u = slot_colours(sm.get_meta("colour_bases", {}), picks)
		_put(sm, u)
	return u


static func _put(sm: ShaderMaterial, u: Dictionary) -> void:
	for k: String in u:
		sm.set_shader_parameter(k, u[k])


## The shader's colour uniforms for a head's bases ({"skin", "lips", "detail", "front"}, sRGB) and the picks; no
## picks: every target its base (the identity). alien_colour_geom.slot_colours, line for line.
static func slot_colours(bases: Dictionary, picks: Dictionary) -> Dictionary:
	var base: Color = bases["skin"]
	var u: Dictionary = {"base_skin": base, "lip_base": bases["lips"], "detail_base": bases["detail"],
		"front_base": bases["front"]}
	var skin: Color = guard("skin", _pick(picks["skin"])) if picks.has("skin") else base
	u["skin_color"] = skin
	if picks.has("skin"):
		var fc: Color = guard("front", recolour(u["front_base"], base, skin))
		u["front_color"] = fc
		u["front_sat_max"] = minf(1.0, FRONT_SAT_GAIN * fc.s)
	else:
		u["front_color"] = u["front_base"]
		u["front_sat_max"] = 1.0
	if picks.has("lips"):
		u["lip_color"] = lip_contrast(guard("lips", _pick(picks["lips"])), skin)
	else:  # the build's lips, following a picked skin as its paint does
		u["lip_color"] = recolour(u["lip_base"], base, skin)
	var on: bool = picks.get("detail_on", picks.has("detail"))
	if picks.has("detail"):
		u["detail_color"] = guard("detail", _pick(picks["detail"]))
	else:  # the build's marks, following a picked skin
		u["detail_color"] = recolour(u["detail_base"], base, skin)
	u["detail_on"] = 1.0 if on else 0.0
	u["gills_detail"] = 1.0 if picks.get("gills_detail", true) else 0.0
	return u


static func _pick(v: Variant) -> Color:
	if v is String:
		return Color(v)
	if v is Array:
		return Color(v[0], v[1], v[2])
	return v


## The shader's recolour on one sRGB colour (sRGB HSV).
static func recolour(c: Color, base: Color, target: Color) -> Color:
	var h: float = fposmod(c.h + target.h - base.h, 1.0)
	var s: float = minf(1.0, c.s * target.s / maxf(base.s, 1.0e-4))
	var v: float = minf(1.0, c.v * target.v / maxf(base.v, 1.0e-4))
	return Color.from_hsv(h, s, v)


static func _lin(c: float) -> float:
	return c / 12.92 if c <= 0.04045 else pow((c + 0.055) / 1.055, 2.4)


static func _srgb(c: float) -> float:
	c = clampf(c, 0.0, 1.0)
	return c * 12.92 if c <= 0.0031308 else 1.055 * pow(c, 1.0 / 2.4) - 0.055


static func _f(t: float) -> float:
	return pow(t, 1.0 / 3.0) if t > 216.0 / 24389.0 else (24389.0 / 27.0 * t + 16.0) / 116.0


static func _finv(t: float) -> float:
	return t * t * t if t * t * t > 216.0 / 24389.0 else (116.0 * t - 16.0) / (24389.0 / 27.0)


static func to_lab(c: Color) -> Vector3:
	var r: float = _lin(c.r)
	var g: float = _lin(c.g)
	var b: float = _lin(c.b)
	var x: float = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / WHITE.x
	var y: float = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / WHITE.y
	var z: float = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / WHITE.z
	return Vector3(116.0 * _f(y) - 16.0, 500.0 * (_f(x) - _f(y)), 200.0 * (_f(y) - _f(z)))


static func from_lab(lab: Vector3) -> Color:
	var fy: float = (lab.x + 16.0) / 116.0
	var x: float = _finv(fy + lab.y / 500.0) * WHITE.x
	var y: float = _finv(fy) * WHITE.y
	var z: float = _finv(fy - lab.z / 200.0) * WHITE.z
	return Color(_srgb(3.2404542 * x - 1.5371385 * y - 0.4985314 * z),
		_srgb(-0.9692660 * x + 1.8760108 * y + 0.0415560 * z), _srgb(0.0556434 * x - 0.2040259 * y + 1.0572252 * z))


static func chroma_cap(slot: String, hue_deg: float, l: float) -> float:
	var r: Array = RAILS[slot]
	var cap: float = r[0]
	for band: Array in BANDS:
		var d: float = absf(fposmod(hue_deg - band[0] + 180.0, 360.0) - 180.0)
		if d < band[1]:
			cap *= 1.0 - (1.0 - band[2]) * 0.5 * (1.0 + cos(PI * d / band[1]))
	if r[3] != null:
		cap *= minf(1.0, (l + 15.0) / (r[3] + 15.0))
	if r[4] != null:
		cap *= minf(1.0, (100.0 - l) / (100.0 - r[4]))
	return cap


## One picked sRGB colour inside its slot's rails (unchanged when inside them).
static func guard(slot: String, c: Color) -> Color:
	var lab: Vector3 = to_lab(c)
	var r: Array = RAILS[slot]
	var lc: float = clampf(lab.x, r[1], r[2])
	var ch: float = Vector2(lab.y, lab.z).length()
	var cap: float = chroma_cap(slot, fposmod(rad_to_deg(atan2(lab.z, lab.y)), 360.0), lc)
	if ch <= cap and lab.x >= r[1] and lab.x <= r[2]:
		return Color(c.r, c.g, c.b)
	var k: float = minf(1.0, cap / ch) if ch > 0.0 else 1.0
	return from_lab(Vector3(lc, lab.y * k, lab.z * k))


## The lips at least LIP_CONTRAST from the skin: L* darker (lighter when darker leaves the range).
static func lip_contrast(lips: Color, skin: Color) -> Color:
	var a: Vector3 = to_lab(lips)
	var s: Vector3 = to_lab(skin)
	if a.distance_to(s) >= LIP_CONTRAST:
		return lips
	var dl: float = sqrt(maxf(0.0, LIP_CONTRAST * LIP_CONTRAST - pow(a.y - s.y, 2.0) - pow(a.z - s.z, 2.0))) + 0.5
	var r: Array = RAILS["lips"]
	var l: float = s.x - dl if s.x - dl >= r[1] else minf(r[2], s.x + dl)
	return from_lab(Vector3(l, a.y, a.z))
