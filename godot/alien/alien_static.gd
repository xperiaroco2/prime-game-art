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
## The colour slots (2026-10-23): apply()'s 7th to 9th arguments, the accent mask (`<head>_accent.png` beside the
## GLB: R lips, G details, B the pale front), its bases ({"lips", "detail", "front"}: the sRGB medians in
## `<head>_accent.json`) and the whole gills (`<head>_gill.png`, grey; v3: out of the accent's alpha). Both masks are
## data: load them with data_texture() (Image.load_from_file) or import them lossless with the settings in
## docs/godot.md ("The colour slots' masks"); then
##   AlienStatic.set_colours(mats, {"skin": Color(...), "lips": Color(...), "detail": Color(...), "detail_on": true})
## (a slot left out keeps the build's own paint; set_colours(mats, {}) is the merged look) or a preset:
##   AlienStatic.set_colours(mats, AlienStatic.PRESETS[1]["picks"])
## The guard rails (here, in OKLCh, the hue kept; tools/blender/alien_colour_geom.py holds the same maths and its tests) act on
## every picked colour before it reaches the shader, which does the recolour in sRGB HSV.

const SHADER: Shader = preload("res://alien/alien_static.gdshader")
const SHADER_288: Shader = preload("res://alien/alien_static_288.gdshader")  # static_v5: #288's look, byte for byte
const SUFFIX: String = "_static_skin"
const BODY_SUFFIX: String = "_body_skin"  # B1: the shared body's surface (apply_body)

## The guard rails per slot: [chroma cap C, L min, L max, dark knee, light knee] (OKLCh: the hue angle kept; the cap
## scaled by (L - 0.009) / (dark - 0.009) below the dark knee, by (1 - L) / (1 - light) above the light knee; null:
## none). v2: re-derived from CS1's CIELAB rails, whose chroma cut turned navy violet (alien_colour_geom.py).
const RAILS: Dictionary = {"skin": [0.108, 0.44, 0.871, 0.612, null], "lips": [0.113, 0.353, 0.828, null, 0.741],
	"detail": [0.113, 0.31, 0.871, null, 0.741], "front": [0.043, 0.845, 0.94, null, null]}
## Hue bands with a lower cap: [centre, half width (OKLCh hue degrees), the cap's factor at the centre]: yellow-green, hot pink.
const BANDS: Array = [[125.0, 36.0, 0.7], [341.0, 41.0, 0.8]]
const LIP_CONTRAST: float = 0.1  # OKLab delta E, lips against the skin
const GILL_MODES: PackedStringArray = ["skin", "gradient", "whole"]  # the shader's gill_mode: 0, 1, 2
const FRONT_SAT_GAIN: float = 1.4  # a front texel's HSV saturation never above max(its own, this x the target's)

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

## A curated skin palette (sRGB); the build's own teal comes first at run time. v3: the colours as set_skin's guard
## rails render them on SHADER: v4, generated as alien_colour_geom.hexs(guard("skin", PALETTE_288[i])) and pinned by
## tools/tests/test_alien_colour_slots.py; PALETTE_288, the merged values, stay for SHADER_288, whose set_skin is
## unguarded as merged (the #288 review output reproducible).
const PALETTE: Array[Color] = [Color("#e89091"), Color("#a293dd"), Color("#efca79"), Color("#6183c5")]
const PALETTE_288: Array[Color] = [Color(0.93, 0.55, 0.56), Color(0.64, 0.56, 0.92), Color(0.98, 0.78, 0.30),
	Color(0.30, 0.50, 0.90)]


## Replaces every "_static_skin" surface material under root; returns the new ShaderMaterials.
static func apply(root: Node, mask: Texture2D, base_skin: Color, detail: Texture2D = null,
		plain: Texture2D = null, shader: Shader = null, accent: Texture2D = null,
		bases: Dictionary = {}, gill: Texture2D = null) -> Array[ShaderMaterial]:
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
			if gill != null:
				sm.set_shader_parameter("gill_tex", gill)
			elif accent != null:  # v4: without the gills' texture "skin" and "whole" would act as "gradient"
				push_warning("alien_static: %s: an accent mask without the gill texture: the gills modes 'skin' and"
						% src.resource_name + " 'whole' act as 'gradient' (pass <head>_gill.png)")
			var b: Dictionary = {"skin": base_skin}
			for k: String in ["lips", "detail", "front"]:
				b[k] = _pick(bases[k]) if bases.has(k) else base_skin
			sm.set_meta("colour_bases", b)
			_put(sm, slot_colours(b, {}))
			mi.set_surface_override_material(i, sm)
			made.append(sm)
	return made



## B1, the head on the shared body: every surface whose material name ends in BODY_SUFFIX takes a copy of the head's
## ShaderMaterial (its look, its slot bases and colours) with the body's own maps on the body's UV: the imported
## albedo and normal, `mask` (R 1: all skin) and `accent` (B the pale front; no lips, details or gills). One material
## set: set_colours on the head's and these materials gives the body the same slots.
static func apply_body(root: Node, head: ShaderMaterial, mask: Texture2D, accent: Texture2D,
		detail: Texture2D = null) -> Array[ShaderMaterial]:
	var made: Array[ShaderMaterial] = []
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = node
		for i: int in mi.mesh.get_surface_count():
			var src: Material = mi.get_active_material(i)
			if not (src is BaseMaterial3D) or not src.resource_name.ends_with(BODY_SUFFIX):
				continue
			var base3d: BaseMaterial3D = src
			var sm: ShaderMaterial = head.duplicate()
			sm.resource_name = src.resource_name
			sm.set_meta("colour_bases", head.get_meta("colour_bases"))
			sm.set_shader_parameter("albedo_tex", base3d.albedo_texture)
			sm.set_shader_parameter("plain_tex", base3d.albedo_texture)  # no alive layers on the body
			sm.set_shader_parameter("normal_tex", base3d.normal_texture)
			sm.set_shader_parameter("mask_tex", mask)
			sm.set_shader_parameter("accent_tex", accent)
			# the body's detail map (B2: the head's at the cut); null leaves the shader's white default, which reads the
			# whole body as thin (transmission everywhere: r2's lighter, speckled body)
			sm.set_shader_parameter("detail_tex", detail)
			sm.set_shader_parameter("gill_tex", null)
			mi.set_surface_override_material(i, sm)
			made.append(sm)
	return made

## The player's skin colour (sRGB) on every material apply() made: through the guard rails (set_colours), except on
## SHADER_288 materials, which take it as it is (the merged #288 path, its review output reproducible).
static func set_skin(mats: Array[ShaderMaterial], color: Color) -> void:
	for sm: ShaderMaterial in mats:
		if sm.shader == SHADER_288:
			sm.set_shader_parameter("skin_color", color)
		else:
			var one: Array[ShaderMaterial] = [sm]
			set_colours(one, {"skin": color})


## A colour slots mask (accent or gill PNG) as data: an imported res:// texture as it is (its import settings in
## docs/godot.md), any other path through Image.load_from_file (lossless, linear) with mipmaps; null if missing.
static func data_texture(path: String) -> Texture2D:
	if path.begins_with("res://"):
		return load(path) as Texture2D
	if not FileAccess.file_exists(path):
		return null
	var img: Image = Image.load_from_file(path)
	if img == null or img.is_empty():
		return null
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


## The player's colour slots on every material apply() made: picks holds any of "skin", "lips", "detail" (Color,
## "#rrggbb" or [r, g, b]), "detail_on" (default: true when "detail" is picked), "gills" ("skin", "gradient" (default), "whole").
## Returns the uniforms set (sRGB), the same for every material of one head; an unknown "gills" value is an error
## (push_error, {} returned, the materials left as they were), as in alien_colour_geom.py and colour.js.
static func set_colours(mats: Array[ShaderMaterial], picks: Dictionary) -> Dictionary:
	var u: Dictionary = {}
	for sm: ShaderMaterial in mats:
		u = slot_colours(sm.get_meta("colour_bases", {}), picks)
		if u.is_empty():
			return u
		_put(sm, u)
	return u


static func _put(sm: ShaderMaterial, u: Dictionary) -> void:
	for k: String in u:
		sm.set_shader_parameter(k, u[k])


## The shader's colour uniforms for a head's bases ({"skin", "lips", "detail", "front"}, sRGB) and the picks; no
## picks: every target its base (the identity). alien_colour_geom.slot_colours, line for line.
static func slot_colours(bases: Dictionary, picks: Dictionary) -> Dictionary:
	var gm: int = GILL_MODES.find(str(picks.get("gills", "gradient")))
	if gm < 0:
		push_error("alien_static: unknown gills '%s' (one of %s)" % [picks["gills"], ", ".join(GILL_MODES)])
		return {}
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
	u["gill_mode"] = float(gm)
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


static func _cbrt(v: float) -> float:
	return signf(v) * pow(absf(v), 1.0 / 3.0)


static func to_oklab(c: Color) -> Vector3:
	var r: float = _lin(c.r)
	var g: float = _lin(c.g)
	var b: float = _lin(c.b)
	var l: float = _cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
	var m: float = _cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
	var s: float = _cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
	return Vector3(0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
		1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


## OKLab to linear sRGB, unclipped.
static func _oklab_rgb(lab: Vector3) -> Vector3:
	var l: float = pow(lab.x + 0.3963377774 * lab.y + 0.2158037573 * lab.z, 3.0)
	var m: float = pow(lab.x - 0.1055613458 * lab.y - 0.0638541728 * lab.z, 3.0)
	var s: float = pow(lab.x - 0.0894841775 * lab.y - 1.2914855480 * lab.z, 3.0)
	return Vector3(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
		-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


static func from_oklab(lab: Vector3) -> Color:
	var v: Vector3 = _oklab_rgb(lab)
	return Color(_srgb(v.x), _srgb(v.y), _srgb(v.z))


static func _fits(lab: Vector3, k: float) -> bool:
	var v: Vector3 = _oklab_rgb(Vector3(lab.x, lab.y * k, lab.z * k))
	return v.x >= -1e-6 and v.y >= -1e-6 and v.z >= -1e-6 and v.x <= 1.000001 and v.y <= 1.000001 and v.z <= 1.000001


## OKLab to sRGB, the chroma scaled down (bisection, the hue and L kept) until every channel is inside 0-1.
static func _in_gamut(lab: Vector3) -> Color:
	if _fits(lab, 1.0):
		return from_oklab(lab)
	var lo: float = 0.0
	var hi: float = 1.0
	for i in 20:
		var k: float = 0.5 * (lo + hi)
		if _fits(lab, k):
			lo = k
		else:
			hi = k
	return from_oklab(Vector3(lab.x, lab.y * lo, lab.z * lo))


static func chroma_cap(slot: String, hue_deg: float, l: float) -> float:
	var r: Array = RAILS[slot]
	var cap: float = r[0]
	for band: Array in BANDS:
		var d: float = absf(fposmod(hue_deg - band[0] + 180.0, 360.0) - 180.0)
		if d < band[1]:
			cap *= 1.0 - (1.0 - band[2]) * 0.5 * (1.0 + cos(PI * d / band[1]))
	if r[3] != null:
		cap *= minf(1.0, (l - 0.009) / (r[3] - 0.009))
	if r[4] != null:
		cap *= minf(1.0, (1.0 - l) / (1.0 - r[4]))
	return cap


## One picked sRGB colour inside its slot's rails (unchanged when inside them; the hue angle kept).
static func guard(slot: String, c: Color) -> Color:
	var lab: Vector3 = to_oklab(c)
	var r: Array = RAILS[slot]
	var lc: float = clampf(lab.x, r[1], r[2])
	var ch: float = Vector2(lab.y, lab.z).length()
	var cap: float = chroma_cap(slot, fposmod(rad_to_deg(atan2(lab.z, lab.y)), 360.0), lc)
	if ch <= cap and lab.x >= r[1] and lab.x <= r[2]:
		return Color(c.r, c.g, c.b)
	var k: float = minf(1.0, cap / ch) if ch > 0.0 else 1.0
	return _in_gamut(Vector3(lc, lab.y * k, lab.z * k))


## The lips at least LIP_CONTRAST (OKLab) from the skin: L darker (lighter when darker leaves the range).
static func lip_contrast(lips: Color, skin: Color) -> Color:
	var a: Vector3 = to_oklab(lips)
	var s: Vector3 = to_oklab(skin)
	if a.distance_to(s) >= LIP_CONTRAST:
		return lips
	var dl: float = sqrt(maxf(0.0, LIP_CONTRAST * LIP_CONTRAST - pow(a.y - s.y, 2.0) - pow(a.z - s.z, 2.0))) + 0.005
	var r: Array = RAILS["lips"]
	var l: float = s.x - dl if s.x - dl >= r[1] else minf(r[2], s.x + dl)
	return _in_gamut(Vector3(l, a.y, a.z))

