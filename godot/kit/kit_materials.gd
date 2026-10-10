extends RefCounted
## The House kit's `set` pack in Godot (art #86, docs/kit.md "Materials"): a kit GLB's surfaces whose material is named
## `kit_set` (Blender's `kit_set-vcol`, a plain white stand-in) get one shared ShaderMaterial on kit_set.gdshader with
## the packed textures. Used by the proof and by the layout engine (#75a):
##   const KitMaterials := preload("res://kit/kit_materials.gd")
##   var mat := KitMaterials.make("D:/prime-art-raw/kits/house/v2/textures", {"roughness": [...], "normal_strength": [...]})
##   KitMaterials.apply(piece_root, mat)

const SHADER := preload("res://kit/kit_set.gdshader")
const PACK := "set"


## The pack's ShaderMaterial from <textures>/set_d.png, set_n0.png and set_n1.png (absolute paths or res://).
## params: optional "roughness" and "normal_strength", three numbers each (the spec's layers in order).
static func make(textures: String, params: Dictionary = {}) -> ShaderMaterial:
	var mat: ShaderMaterial = ShaderMaterial.new()
	mat.shader = SHADER
	for key: String in ["d", "n0", "n1"]:
		mat.set_shader_parameter("%s_%s" % [PACK, key], _texture(textures.path_join("%s_%s.png" % [PACK, key])))
	if params.has("roughness"):
		mat.set_shader_parameter("layer_roughness", _vec3(params["roughness"]))
	if params.has("normal_strength"):
		mat.set_shader_parameter("layer_normal_strength", _vec3(params["normal_strength"]))
	return mat


## Per-room wall paint (Q11 = B, docs/house.md "Wall paint"): `paints` is house_layout.paint_request's dictionary
## ({"from": [r, g, b], "rooms": [{"rect": [x0, z0, x1, z1], "band": [y0, y1], "to": [r, g, b]}]}, world metres,
## sRGB-encoded vertex colours). The shader recolours the inner plaster of each room's faces; returns the rooms set.
static func paint(mat: ShaderMaterial, paints: Dictionary) -> int:
	var rooms: Array = paints.get("rooms", [])
	var n: int = mini(rooms.size(), 16)
	var rects: PackedVector4Array = PackedVector4Array()
	var bands: PackedVector2Array = PackedVector2Array()
	var tos: PackedVector3Array = PackedVector3Array()
	for i: int in 16:
		var r: Dictionary = rooms[i] if i < n else {"rect": [0, 0, 0, 0], "band": [0, 0], "to": [0, 0, 0]}
		rects.append(Vector4(float(r["rect"][0]), float(r["rect"][1]), float(r["rect"][2]), float(r["rect"][3])))
		bands.append(Vector2(float(r["band"][0]), float(r["band"][1])))
		tos.append(_vec3(r["to"]))
	mat.set_shader_parameter("paint_from", _vec3(paints.get("from", [0, 0, 0])))
	mat.set_shader_parameter("paint_rect", rects)
	mat.set_shader_parameter("paint_band", bands)
	mat.set_shader_parameter("paint_to", tos)
	mat.set_shader_parameter("paint_count", n)
	return n


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


static func _texture(path: String) -> Texture2D:
	if path.begins_with("res://"):
		return load(path) as Texture2D
	var image: Image = Image.load_from_file(path)
	if image == null:
		push_error("KitMaterials: cannot load %s" % path)
		return null
	image.generate_mipmaps()
	return ImageTexture.create_from_image(image)


static func _vec3(a: Array) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))
