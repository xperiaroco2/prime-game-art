extends SceneTree
## The fine pack's shared-texture check for `tools/run.py props-library --build` (#143; docs/decisions/
## 2026-10-13-house-world-look.md): per tier ONE ShaderMaterial (props/prop_materials.gd, its textures with mipmaps
## and BPTC-compressed as the import does) goes on every prop's `kit_fine` surfaces; the check asserts that every such
## surface of every prop holds that same material and the same three texture objects, and measures per tier the
## texture memory and per prop its surfaces (one draw call each). `compare` names other GLBs (the kitchen pilot's lab
## props) loaded at run time for the same counts and their embedded images' memory (RGBA8 with mipmaps).
##   godot --headless --path godot -s res://props/fine_check.gd -- <request.json> <out.json>
## request.json: {"fine": "<build>/textures/fine", "scenes": {"<id>": "res://import/prop_<id>.glb"},
##   "compare": {"<id>": "<absolute .glb>"}}. Prints FINE ok|failed; exit code 1 on a problem.

const PropMaterials := preload("res://props/prop_materials.gd")
const KEYS: Array[String] = ["fine_d", "fine_n0", "fine_n1"]


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var req: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if typeof(req) != TYPE_DICTIONARY:
		print("FINE failed: cannot read %s" % args[0])
		quit(1)
		return
	var fine_dir: String = req["fine"]
	var fine: Dictionary = PropMaterials.read_json(fine_dir.path_join("fine.json"))
	var out: Dictionary = {"godot": Engine.get_version_info()["string"], "tiers": {}, "props": {}, "compare": {},
		"problems": []}
	var problems: Array = out["problems"]
	for tier: String in fine.get("tiers", {}):
		var mat: ShaderMaterial = PropMaterials.make(fine_dir.path_join(tier), fine, tier, false)
		var bytes: int = 0
		var formats: Array = []
		var size: int = 0
		for key: String in KEYS:
			var image: Image = Image.load_from_file(fine_dir.path_join(tier).path_join("%s.png" % key))
			image.generate_mipmaps()
			var err: Error = image.compress(Image.COMPRESS_BPTC)
			if err != OK:
				problems.append("%s %s: BPTC compression failed (%d)" % [tier, key, err])
			bytes += image.get_data_size()
			formats.append(image.get_format())
			size = image.get_width()
			mat.set_shader_parameter(key, ImageTexture.create_from_image(image))
		var textures: Array = KEYS.map(func(k: String) -> Object: return mat.get_shader_parameter(k))
		var shared_by: int = 0
		for id: String in req["scenes"]:
			var packed: PackedScene = load(req["scenes"][id]) as PackedScene
			if packed == null:
				problems.append("%s: cannot load %s" % [id, req["scenes"][id]])
				continue
			var n: Node = packed.instantiate()
			root.add_child(n)
			var applied: int = PropMaterials.apply(n, mat)
			var counts: Dictionary = _surfaces(n)
			var same: bool = applied == counts["fine"] and applied > 0
			for mi: MeshInstance3D in _meshes(n):
				for i: int in mi.mesh.get_surface_count():
					var base: Material = mi.mesh.surface_get_material(i)
					if base == null or base.resource_name != "kit_fine":
						continue
					var m: ShaderMaterial = mi.get_surface_override_material(i) as ShaderMaterial
					if m != mat or KEYS.map(func(k: String) -> Object: return m.get_shader_parameter(k)) != textures:
						same = false
			if not same:
				problems.append("%s %s: a kit_fine surface without the shared material (%d of %d set)"
					% [tier, id, applied, counts["fine"]])
			else:
				shared_by += 1
			out["props"][id] = counts
			n.free()
		out["tiers"][tier] = {"size": size, "bytes": bytes, "mb": snappedf(bytes / 1048576.0, 0.01),
			"formats": formats, "textures": KEYS.size(), "shared_by": shared_by}
	for id: String in req.get("compare", {}):
		var doc: GLTFDocument = GLTFDocument.new()
		var state: GLTFState = GLTFState.new()
		if doc.append_from_file(req["compare"][id], state) != OK:
			problems.append("compare %s: cannot read %s" % [id, req["compare"][id]])
			continue
		var n: Node = doc.generate_scene(state)
		var counts: Dictionary = _surfaces(n)
		var tex_bytes: int = 0
		for t: Texture2D in state.get_images():
			if t != null:  # RGBA8 with a full mip chain: 4 bytes a pixel, 4/3 for the mips
				tex_bytes += int(t.get_width() * t.get_height() * 4 * 4.0 / 3.0)
		counts["images"] = state.get_images().size()
		counts["texture_bytes"] = tex_bytes
		out["compare"][id] = counts
		n.free()
	var f: FileAccess = FileAccess.open(args[1], FileAccess.WRITE)
	f.store_string(JSON.stringify(out, " "))
	f.close()
	print("FINE %s: %d tiers, %d props, %d compared" % ["ok" if problems.is_empty() else "failed",
		out["tiers"].size(), out["props"].size(), out["compare"].size()])
	for p: String in problems:
		print("FINE problem: " + p)
	quit(0 if problems.is_empty() else 1)


func _meshes(n: Node) -> Array[MeshInstance3D]:
	var found: Array[MeshInstance3D] = []
	for c: Node in [n] + n.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = c as MeshInstance3D
		if mi != null and mi.mesh != null:
			found.append(mi)
	return found


## Surfaces (draw calls) of a prop and how many carry the fine pack's stand-in material.
func _surfaces(n: Node) -> Dictionary:
	var total: int = 0
	var fine: int = 0
	var names: Array = []
	for mi: MeshInstance3D in _meshes(n):
		for i: int in mi.mesh.get_surface_count():
			total += 1
			var m: Material = mi.mesh.surface_get_material(i)
			var mname: String = m.resource_name if m != null else ""
			names.append(mname)
			if mname == "kit_fine":
				fine += 1
	return {"surfaces": total, "fine": fine, "materials": names}
