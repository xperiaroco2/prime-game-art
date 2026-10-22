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

const SHADER: Shader = preload("res://alien/alien_static.gdshader")
const SHADER_288: Shader = preload("res://alien/alien_static_288.gdshader")  # static_v5: #288's look, byte for byte
const SUFFIX: String = "_static_skin"

## A curated skin palette (sRGB); the build's own teal comes first at run time.
const PALETTE: Array[Color] = [Color(0.93, 0.55, 0.56), Color(0.64, 0.56, 0.92), Color(0.98, 0.78, 0.30),
	Color(0.30, 0.50, 0.90)]


## Replaces every "_static_skin" surface material under root; returns the new ShaderMaterials.
static func apply(root: Node, mask: Texture2D, base_skin: Color, detail: Texture2D = null,
		plain: Texture2D = null, shader: Shader = null) -> Array[ShaderMaterial]:
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
			mi.set_surface_override_material(i, sm)
			made.append(sm)
	return made


## The player's skin colour (sRGB) on every material apply() made.
static func set_skin(mats: Array[ShaderMaterial], color: Color) -> void:
	for sm: ShaderMaterial in mats:
		sm.set_shader_parameter("skin_color", color)
