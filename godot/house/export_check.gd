extends SceneTree
## The House export's load check (art #119, docs/house.md "The export"). Runs headless inside the export folder,
## opened as its own Godot project (`house --export` writes a project.godot there for the check): loads and
## instantiates every room scene, counts per room the layer-1 static bodies and their shapes, the kit and prop
## instances, the lights and anything the game refuses (CSG, GridMap, CollisionPolygon3D, a rigid or character body
## on layer 1, a light with shadows). Args after `--`: the rooms folder (res://) and the JSON path to write.

var rooms := {}


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var folder: String = args[0]
	var out: String = args[1]
	var names := DirAccess.get_files_at(folder)
	for f in names:
		if f.ends_with(".tscn"):
			rooms[f.get_basename()] = _room(folder.path_join(f))
	var file := FileAccess.open(out, FileAccess.WRITE)
	file.store_string(JSON.stringify({"rooms": rooms}, " "))
	file.close()
	quit(0)


func _room(path: String) -> Dictionary:
	var r := {"loaded": false, "bodies": 0, "shapes": 0, "instances": 0, "meshes": 0, "lights": 0,
		"refused": [], "size_m": null, "root": ""}
	var packed := load(path) as PackedScene
	if packed == null:
		return r
	var root := packed.instantiate()
	if root == null:
		return r
	r["loaded"] = true
	r["root"] = String(root.name)
	if root.has_meta("size_m"):
		var s: Vector2i = root.get_meta("size_m")
		r["size_m"] = [s.x, s.y]
	_walk(root, r)
	root.free()
	return r


func _walk(n: Node, r: Dictionary) -> void:
	if n is CSGShape3D or n is GridMap or n is CollisionPolygon3D:
		r["refused"].append("%s %s" % [n.get_class(), n.name])
	if (n is RigidBody3D or n is CharacterBody3D) and (n.collision_layer & 1):
		r["refused"].append("%s on layer 1: %s" % [n.get_class(), n.name])
	if n is StaticBody3D and (n.collision_layer & 1):
		r["bodies"] += 1
		for c in n.get_children():
			if c is CollisionShape3D and c.shape != null:
				r["shapes"] += 1
	if n is MeshInstance3D:
		r["meshes"] += 1
	if n is Light3D:
		r["lights"] += 1
		if n.shadow_enabled:
			r["refused"].append("shadowed light %s" % n.name)
	if n.scene_file_path != "" and n.owner != null:
		r["instances"] += 1
	for c in n.get_children():
		_walk(c, r)
