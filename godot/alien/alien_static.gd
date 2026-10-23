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
## GLB: R lips, G details, B the pale front), its bases ({"lips", "detail", "front", "gill_tips", "gill_whole"}: the
## regions' sRGB medians, `<head>_regions.json`; a missing gill base is the detail's) and the whole gills (`<head>_gill.png`, grey; v3: out of the accent's alpha). Both masks are
## data: load them with data_texture() (Image.load_from_file) or import them lossless with the settings in
## docs/godot.md ("The colour slots' masks"); then
##   AlienStatic.set_colours(mats, {"skin": Color(...), "lips": Color(...), "detail": Color(...), "detail_on": true})
## (a slot left out keeps the build's own paint; set_colours(mats, {}) is the merged look) or a preset:
##   AlienStatic.set_colours(mats, AlienStatic.PRESETS[1]["picks"])
## Every pick is applied as picked (CS6, 2026-10-23: no guard rails); the shader carries each texel's offset from
## its region's median onto the pick in OKLab. tools/blender/alien_colour_geom.py holds the same maths and its tests.

const SHADER: Shader = preload("res://alien/alien_static.gdshader")
const SHADER_288: Shader = preload("res://alien/alien_static_288.gdshader")  # static_v5: #288's look, byte for byte
const SUFFIX: String = "_static_skin"

const GILL_MODES: PackedStringArray = ["skin", "gradient", "whole"]  # the shader's gill_mode: 0, 1, 2

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

## A curated skin palette (sRGB); the build's own teal comes first at run time. CS6: as picked on every shader (v3-v5
## held the guarded colours for SHADER and these for SHADER_288).
const PALETTE: Array[Color] = [Color(0.93, 0.55, 0.56), Color(0.64, 0.56, 0.92), Color(0.98, 0.78, 0.30),
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
			for k: String in ["gill_tips", "gill_whole"]:
				b[k] = _pick(bases[k]) if bases.has(k) else b["detail"]
			sm.set_meta("colour_bases", b)
			_put(sm, slot_colours(b, {}))
			mi.set_surface_override_material(i, sm)
			made.append(sm)
	return made


## The player's skin colour (sRGB) on every material apply() made: set_colours({"skin": color}), or on SHADER_288
## materials (no colour slots) the skin uniform alone (the merged #288 path, its review output reproducible).
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


## The shader's colour uniforms for a head's bases ({"skin", "lips", "detail", "front", "gill_tips", "gill_whole"},
## sRGB) and the picks, applied as picked; no picks: every target its base (the identity).
## alien_colour_geom.slot_colours, line for line.
static func slot_colours(bases: Dictionary, picks: Dictionary) -> Dictionary:
	var gm: int = GILL_MODES.find(str(picks.get("gills", "gradient")))
	if gm < 0:
		push_error("alien_static: unknown gills '%s' (one of %s)" % [picks["gills"], ", ".join(GILL_MODES)])
		return {}
	var base: Color = bases["skin"]
	var gb: Color = bases.get("gill_whole" if gm == 2 else "gill_tips", bases["detail"])
	var u: Dictionary = {"base_skin": base, "lip_base": bases["lips"], "detail_base": bases["detail"],
		"gill_base": gb, "front_base": bases["front"]}
	var picked: bool = picks.has("skin")
	var skin: Color = _pick(picks["skin"]) if picked else base
	u["skin_color"] = skin
	u["front_color"] = front_for(skin, base, u["front_base"]) if picked else u["front_base"]
	# a slot left out: the build's paint there, following a picked skin as its paint does
	if picks.has("lips"):
		u["lip_color"] = _pick(picks["lips"])
	else:
		u["lip_color"] = recolour(u["lip_base"], base, skin) if picked else u["lip_base"]
	for pair: Array in [["detail_color", u["detail_base"]], ["gill_color", gb]]:
		if picks.has("detail"):
			u[pair[0]] = _pick(picks["detail"])
		else:
			u[pair[0]] = recolour(pair[1], base, skin) if picked else pair[1]
	u["detail_on"] = 1.0 if bool(picks.get("detail_on", picks.has("detail"))) else 0.0
	u["gill_mode"] = float(gm)
	return u


static func _pick(v: Variant) -> Color:
	if v is String:
		return Color(v)
	if v is Array:
		return Color(v[0], v[1], v[2])
	return v


## The shader's shift on one sRGB colour (sRGB in and out, clamped to the gamut).
static func recolour(c: Color, base: Color, target: Color) -> Color:
	return from_oklab(shift(to_oklab(c), to_oklab(base), to_oklab(target)))


## A texel x (OKLab) from its region's base b to the target t (alien_colour_geom.shift): its offset from b carried
## onto t, the lightness offset scaled by the room at t against the room at b, the a/b offset turned by the hue turn
## and scaled by min(1, C_t / C_b).
static func shift(x: Vector3, b: Vector3, t: Vector3) -> Vector3:
	var dl: float = x.x - b.x
	var kl: float = minf(1.0, (1.0 - t.x) / maxf(1.0 - b.x, 1.0e-4)) if dl > 0.0 else minf(1.0, t.x / maxf(b.x, 1.0e-4))
	var cb: float = Vector2(b.y, b.z).length()
	var ct: float = Vector2(t.y, t.z).length()
	var co: float = 1.0
	var si: float = 0.0
	if cb > 1.0e-4 and ct > 1.0e-4:
		co = (b.y * t.y + b.z * t.z) / (cb * ct)
		si = (b.y * t.z - b.z * t.y) / (cb * ct)
	var kc: float = minf(1.0, ct / maxf(cb, 1.0e-4))
	var da: float = x.y - b.y
	var db: float = x.z - b.z
	return Vector3(t.x + dl * kl, t.y + (da * co - db * si) * kc, t.z + (da * si + db * co) * kc)


## The pale front for a picked skin: the build's front shifted with the skin, its chroma never above the build's
## front's (a tinted cream).
static func front_for(skin: Color, base_skin: Color, front_base: Color) -> Color:
	var f: Vector3 = shift(to_oklab(front_base), to_oklab(base_skin), to_oklab(skin))
	var fb: Vector3 = to_oklab(front_base)
	var cf: float = Vector2(fb.y, fb.z).length()
	var c: float = Vector2(f.y, f.z).length()
	var k: float = minf(1.0, cf / c) if c > 0.0 else 1.0
	return from_oklab(Vector3(f.x, f.y * k, f.z * k))


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
