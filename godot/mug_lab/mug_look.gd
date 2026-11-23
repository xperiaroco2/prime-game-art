extends RefCounted
## The mug lab's look (research, pipeline A): the shaders on a mug GLB's meshes and its fill level.
##   var look := MugLook.apply(model, levels)  # model: the GLB's instance (meshes Mug, Liquid, Foam)
##   MugLook.set_fill(look, 0.5)               # 1 full (the head over the rim), 0 empty (Beer hidden, lacing left)
## The levels (object space, cm in `levels`) come from the build: the inside floor, the full level, the rim, the
## inner and the rim's outer radius, the crown's top when full.

const GLASS := preload("res://mug_lab/glass.gdshader")
const BEER := preload("res://mug_lab/beer.gdshader")
const FOAM := preload("res://mug_lab/foam.gdshader")


static func apply(model: Node, levels: Dictionary = {}) -> Dictionary:
	var look := {
		"floor": float(levels.get("floor", 2.2)) * 0.01,
		"full": float(levels.get("full", 12.6)) * 0.01,
		"rim": float(levels.get("rim", 15.0)) * 0.01,
		"inner_r": float(levels.get("inner_r", 3.85)) * 0.01,
		"rim_r": float(levels.get("rim_r", 4.5)) * 0.01,
		"head_top": float(levels.get("head_top", 18.2)) * 0.01,
	}
	var glass := ShaderMaterial.new()
	glass.shader = GLASS
	glass.set_shader_parameter("floor_y", look["floor"])
	glass.set_shader_parameter("body_r", look["rim_r"] + 0.003)
	var beer := ShaderMaterial.new()
	beer.shader = BEER
	beer.set_shader_parameter("inner_r", look["inner_r"] - 0.0004)
	var foam := ShaderMaterial.new()
	foam.shader = FOAM
	foam.set_shader_parameter("inner_r", look["inner_r"] - 0.0008)
	foam.set_shader_parameter("rim", look["rim"])
	foam.set_shader_parameter("rim_r", look["rim_r"])
	foam.set_shader_parameter("head_top", look["head_top"])
	for pair: Array in [["Mug", glass], ["Liquid", beer], ["Foam", foam]]:
		var mi := model.find_child(pair[0], true, false) as MeshInstance3D
		if mi == null:
			push_error("MUGLAB no mesh %s" % pair[0])
			continue
		mi.material_override = pair[1]
		look[pair[0]] = mi
	# the foam's mesh is canonical (a 1 cm unit): its shader places it, so its box is the glass's
	(look["Foam"] as MeshInstance3D).custom_aabb = AABB(Vector3(-0.06, 0.0, -0.06), Vector3(0.12, 0.2, 0.12))
	# ...and its import LODs are useless: every ring of the canonical mesh lies on one cylinder, so Godot's mesh
	# simplifier drops the middle rings and the shader gets a cone (round 5). Keep the full mesh at every distance; in
	# the game's import, turn LOD generation off for this mesh.
	(look["Foam"] as MeshInstance3D).lod_bias = 128.0
	look["glass"] = glass
	look["beer"] = beer
	look["foam_mat"] = foam
	look["Beer"] = model.find_child("Beer", true, false)
	return look


static func set_fill(look: Dictionary, f: float) -> void:
	f = clampf(f, 0.0, 1.0)
	var floor_y: float = look["floor"]
	var full: float = look["full"]
	var rim: float = look["rim"]
	var beer_node: Node3D = look["Beer"]
	var glass: ShaderMaterial = look["glass"]
	glass.set_shader_parameter("lace_top", rim - 0.002)
	glass.set_shader_parameter("lace_from", full)
	if f <= 0.001:
		beer_node.visible = false
		glass.set_shader_parameter("lace", 1.0)
		glass.set_shader_parameter("beer_in", 0.0)
		glass.set_shader_parameter("lace_bottom", floor_y + 0.004)
		return
	beer_node.visible = true
	glass.set_shader_parameter("beer_in", 1.0)
	var level: float = floor_y + f * (full - floor_y)
	(look["beer"] as ShaderMaterial).set_shader_parameter("level", level)
	glass.set_shader_parameter("level", level)
	# the foam: one volume from the surface (foam.gdshader's profile); full, the column fills the glass to the rim and
	# the crown domes over it to head_top; the first sip takes the crown, then the layer thins as the level goes down
	var crown: float = smoothstep(0.86, 1.0, f)
	var layer: float = lerpf(0.008, 0.014, smoothstep(0.0, 0.7, f))   # the foam stays on to the last sip
	var fm: ShaderMaterial = look["foam_mat"]
	fm.set_shader_parameter("level", level)
	fm.set_shader_parameter("layer", layer)
	fm.set_shader_parameter("crown", crown)
	var col_top: float = lerpf(level + layer, rim, crown)
	var dome: float = lerpf(0.004, look["head_top"] - rim, crown)
	glass.set_shader_parameter("lace", clampf((1.0 - f) * 4.0, 0.0, 1.0))
	glass.set_shader_parameter("lace_bottom", col_top + dome * 0.5)
