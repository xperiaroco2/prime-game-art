extends RefCounted
## The House props' `fine` pack in Godot (docs/decisions/2026-10-13-house-world-look.md, docs/props.md "World look
## rules"): a prop GLB's surfaces whose material is named `kit_fine` (Blender's `kit_fine-vcol`, a plain white
## stand-in) get ONE shared ShaderMaterial on prop_fine.gdshader with the tier's textures. One material and one
## texture set serve every prop, so the textures are shared resources, not copies per GLB:
##   const PropMaterials := preload("res://props/prop_materials.gd")
##   var fine: Dictionary = PropMaterials.read_json("<build>/textures/fine/fine.json")
##   var mat := PropMaterials.make("res://import/fine/high", fine, "high")   # or "low"
##   PropMaterials.apply(prop_root, mat)
## A res:// folder loads the imported, VRAM-compressed textures (their .import files ask for it); an absolute folder
## loads the PNGs at run time, with mipmaps, compressed when `compress` is set.

const SHADER := preload("res://props/prop_fine.gdshader")
const PACK := "fine"
const LAYERS := 16


static func read_json(path: String) -> Dictionary:
	var text: String = FileAccess.get_file_as_string(path)
	var data: Variant = JSON.parse_string(text)
	return data if data is Dictionary else {}


## The pack's ShaderMaterial from <folder>/fine_d.png, fine_n0.png and fine_n1.png; `fine` is the build's fine.json
## (the layers' values and each textured layer's detail mean per tier).
static func make(folder: String, fine: Dictionary, tier: String, compress: bool = false) -> ShaderMaterial:
	var mat: ShaderMaterial = ShaderMaterial.new()
	mat.shader = SHADER
	for key: String in ["d", "n0", "n1"]:
		mat.set_shader_parameter("%s_%s" % [PACK, key], texture(folder.path_join("%s_%s.png" % [PACK, key]), compress))
	var rough: PackedFloat32Array = PackedFloat32Array()
	var metal: PackedFloat32Array = PackedFloat32Array()
	var strength: PackedFloat32Array = PackedFloat32Array()
	rough.resize(LAYERS)
	metal.resize(LAYERS)
	strength.resize(LAYERS)
	var gain: Vector4 = Vector4(2.0, 2.0, 2.0, 2.0)
	var means: Dictionary = fine.get("tiers", {}).get(tier, {}).get("detail_mean", {})
	var layers: Array = fine.get("layers", [])
	for k: int in mini(layers.size(), LAYERS):
		var layer: Dictionary = layers[k]
		rough[k] = float(layer.get("roughness", 0.7))
		metal[k] = float(layer.get("metallic", 0.0))
		strength[k] = float(layer.get("normal_strength", 0.0))
		if k < 4 and means.has(layer.get("name", "")):
			gain[k] = 1.0 / maxf(float(means[layer["name"]]), 0.05)
	mat.set_shader_parameter("layer_roughness", rough)
	mat.set_shader_parameter("layer_metallic", metal)
	mat.set_shader_parameter("layer_normal_strength", strength)
	mat.set_shader_parameter("layer_gain", gain)
	return mat


## Puts `mat` on every surface under `node` whose material is the pack's stand-in; returns how many surfaces it set.
static func apply(node: Node, mat: Material) -> int:
	var count: int = 0
	for n: Node in [node] + node.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n as MeshInstance3D
		if mi == null or mi.mesh == null:
			continue
		for i: int in mi.mesh.get_surface_count():
			var m: Material = mi.mesh.surface_get_material(i)
			if m != null and m.resource_name == "kit_%s" % PACK:
				mi.set_surface_override_material(i, mat)
				count += 1
	return count


static func texture(path: String, compress: bool = false) -> Texture2D:
	if path.begins_with("res://"):
		return load(path) as Texture2D
	var image: Image = Image.load_from_file(path)
	if image == null:
		push_error("PropMaterials: cannot load %s" % path)
		return null
	image.generate_mipmaps()
	if compress:
		image.compress(Image.COMPRESS_BPTC)
	return ImageTexture.create_from_image(image)
