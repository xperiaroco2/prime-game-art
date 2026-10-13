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
const SLOTS := 8  # textured layers (prop_lib.FINE_SLOTS)


static func read_json(path: String) -> Dictionary:
	var text: String = FileAccess.get_file_as_string(path)
	var data: Variant = JSON.parse_string(text)
	return data if data is Dictionary else {}


## The pack's ShaderMaterial from <folder>/fine_d.png, fine_d1.png and fine_n0-n3.png (the ones the tier's `files`
## in fine.json name; an old build without `files`: fine_d, fine_n0 and fine_n1); `fine` is the build's fine.json
## (the layers' values, each textured layer's slot and its detail mean per tier).
static func make(folder: String, fine: Dictionary, tier: String, compress: bool = false) -> ShaderMaterial:
	var mat: ShaderMaterial = ShaderMaterial.new()
	mat.shader = SHADER
	var info: Dictionary = fine.get("tiers", {}).get(tier, {})
	for key: String in keys(fine, tier):
		mat.set_shader_parameter("%s_%s" % [PACK, key], texture(folder.path_join("%s_%s.png" % [PACK, key]), compress))
	var rough: PackedFloat32Array = PackedFloat32Array()
	var metal: PackedFloat32Array = PackedFloat32Array()
	var strength: PackedFloat32Array = PackedFloat32Array()
	var slot: PackedInt32Array = PackedInt32Array()
	var gain: PackedFloat32Array = PackedFloat32Array()
	rough.resize(LAYERS)
	metal.resize(LAYERS)
	strength.resize(LAYERS)
	slot.resize(LAYERS)
	slot.fill(-1)
	gain.resize(SLOTS)
	gain.fill(2.0)
	var means: Dictionary = info.get("detail_mean", {})
	var layers: Array = fine.get("layers", [])
	var next: int = 0
	for k: int in mini(layers.size(), LAYERS):
		var layer: Dictionary = layers[k]
		rough[k] = float(layer.get("roughness", 0.7))
		metal[k] = float(layer.get("metallic", 0.0))
		strength[k] = float(layer.get("normal_strength", 0.0))
		if layer.get("source", "") != "" and next < SLOTS:
			var s: int = int(layer.get("slot", next))
			next = s + 1
			slot[k] = s
			if means.has(layer.get("name", "")):
				gain[s] = 1.0 / maxf(float(means[layer["name"]]), 0.05)
	mat.set_shader_parameter("layer_roughness", rough)
	mat.set_shader_parameter("layer_metallic", metal)
	mat.set_shader_parameter("layer_normal_strength", strength)
	mat.set_shader_parameter("layer_slot", slot)
	mat.set_shader_parameter("slot_gain", gain)
	return mat


## The tier's texture keys ("d", "d1", "n0" ... "n3"): the ones its `files` in fine.json name, in that order.
static func keys(fine: Dictionary, tier: String) -> Array:
	var info: Dictionary = fine.get("tiers", {}).get(tier, {})
	var out: Array = []
	for key: String in ["d", "d1", "n0", "n1", "n2", "n3"]:
		if not info.has("files") and key in ["d", "n0", "n1"] or info.get("files", {}).has(key):
			out.append(key)
	return out


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
