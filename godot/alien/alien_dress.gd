extends RefCounted
## The alien's approved static look (art #196) on a game package's character (art #393): reads the package's
## `<id>_look.json` and puts alien_static.gdshader on the GLB's `*_static_skin` (the head) and `*_body_skin` (the
## body) surfaces, exactly as the review pages' shots (look_shots.gd) do. Shipped in the package's `look/` folder beside
## alien_static.gd and its shaders (the preloads are relative, so the folder works wherever the game puts it):
##   const AlienDress = preload("res://assets/characters/<id>/look/alien_dress.gd")
##   var mats := AlienDress.dress_from(model, "res://assets/characters/<id>/look/<id>_look.json")
##   AlienDress.AlienStatic.set_skin(mats, Color("e98a8c"))  # a player's skin colour (sRGB); optional
## The look file holds the mask's file name (beside it; imported lossless, its .import shipped), the base skin (sRGB),
## the constant maps that stand in for the sidecar maps lost with D: ([r, g, b, a]: a 4 x 4 texture) and the shader's
## "alive" levers.

const AlienStatic = preload("alien_static.gd")


## Reads the look file and dresses model; returns the head's and the body's ShaderMaterials (empty on a failure,
## with the error pushed).
static func dress_from(model: Node, look_path: String) -> Array[ShaderMaterial]:
	var text := FileAccess.get_file_as_string(look_path)
	var look: Variant = JSON.parse_string(text)
	if not (look is Dictionary):
		push_error("alien_dress: cannot read %s" % look_path)
		return []
	var mask := load(look_path.get_base_dir().path_join(str(look["mask"]))) as Texture2D
	if mask == null:
		push_error("alien_dress: no mask %s beside %s" % [look["mask"], look_path])
		return []
	return dress(model, look, mask)


## The look on model's surfaces: the head (`*_static_skin`) first, then the body (`*_body_skin`) with the head's
## material and colour slots.
static func dress(model: Node, look: Dictionary, mask: Texture2D) -> Array[ShaderMaterial]:
	var mats: Array[ShaderMaterial] = AlienStatic.apply(model, mask, _col(look["base_skin"]),
		_const_tex(look["detail"]))
	if mats.is_empty():
		push_error("alien_dress: no *_static_skin surface under %s" % model.name)
		return mats
	mats.append_array(AlienStatic.apply_body(model, mats[0], _const_tex(look["body_mask"]), null,
		_const_tex(look["body_detail"])))
	var params: Dictionary = look["params"]
	for sm: ShaderMaterial in mats:
		for k: String in params:
			sm.set_shader_parameter(k, params[k])
	return mats


static func _col(a: Array) -> Color:
	return Color(float(a[0]), float(a[1]), float(a[2]))


## A constant map: a 4 x 4 texture of one value ([r, g, b(, a)], data, not colour).
static func _const_tex(c: Array) -> Texture2D:
	var img := Image.create(4, 4, false, Image.FORMAT_RGBA8)
	img.fill(Color(float(c[0]), float(c[1]), float(c[2]), float(c[3]) if c.size() > 3 else 1.0))
	return ImageTexture.create_from_image(img)
