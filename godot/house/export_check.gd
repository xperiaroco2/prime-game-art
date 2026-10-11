extends SceneTree
## The House export's check (art #119, #122; docs/house.md "The export"). Runs headless inside the export folder,
## opened as its own Godot project (`house --export` writes a project.godot there and copies this script and
## walker.gd into `_check/`). Args after `--`: the rooms folder (res://), the JSON path to write and, optionally, the
## request (house_export.check_request) as a JSON path.
## 1. Loads and instantiates every room scene: per room the layer-1 static bodies and their shapes, the kit and prop
##    instances, the lights and anything the game refuses (CSG, GridMap, CollisionPolygon3D, a rigid or character
##    body on layer 1, a light with shadows).
## 2. With a request, assembles the package (each room at its plan origin) and names, per room and node, every
##    problem: a walkable shell piece or a prop with a collider that holds no layer-1 StaticBody3D with a shape; a ray
##    down onto the shell (the game's footstep ray: 0.3 m over the floor to 0.5 m under it, every 0.5 m) that finds
##    no `surface`, or one the game does not know; a kit GLB with a surface but no collider; a doorway or flight the
##    1.36 m capsule (walker.gd) does not walk through.

const Walker := preload("walker.gd")
const SURFACES: Array = ["concrete", "wood", "carpet", "grass"]  # the game's FootstepSurface.SURFACES
const RADIUS: float = 0.68  # walk.gd's: the 1.4 m doors less 2 cm a side
const STEP: float = 0.5  # the ray grid's spacing, m
const ABOVE: float = 0.3  # FootstepSurface.ABOVE_M
const BELOW: float = 0.5  # FootstepSurface.BELOW_M
const WATCHDOG_S: float = 170.0

var rooms := {}


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	create_timer(WATCHDOG_S).timeout.connect(func() -> void:
		printerr("ERROR: export_check.gd not done within %d s" % WATCHDOG_S)
		quit(2))
	_run(args)


func _run(args: PackedStringArray) -> void:
	var folder: String = args[0]
	var out: String = args[1]
	for f in DirAccess.get_files_at(folder):
		if f.ends_with(".tscn"):
			rooms[f.get_basename()] = _room(folder.path_join(f))
	var result := {"rooms": rooms}
	if args.size() > 2:
		var req: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[2]))
		if typeof(req) != TYPE_DICTIONARY:
			printerr("ERROR: cannot read the request %s" % args[2])
			quit(1)
			return
		result["package"] = await _package(req)
	var file := FileAccess.open(out, FileAccess.WRITE)
	file.store_string(JSON.stringify(result, " "))
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


## True when n or a descendant is a layer-1 StaticBody3D with a shape.
func _collides(n: Node) -> bool:
	if n is StaticBody3D and (n.collision_layer & 1):
		for c in n.get_children():
			if c is CollisionShape3D and c.shape != null:
				return true
	for c in n.get_children():
		if _collides(c):
			return true
	return false


## FootstepSurface.of: the tag of the nearest of the collider and its ancestors that has one, or null.
func _surface(n: Node) -> Variant:
	while n != null:
		if n.has_meta(&"surface"):
			return n.get_meta(&"surface")
		n = n.get_parent()
	return null


func _package(req: Dictionary) -> Dictionary:
	var problems: Array = []
	var pieces := {}
	for path: String in req.get("pieces", {}):
		var packed := load(path) as PackedScene
		var node: Node = packed.instantiate() if packed != null else null
		pieces[path] = node != null and _collides(node)
		if not pieces[path]:
			problems.append("kit %s: no layer-1 StaticBody3D (surface %s)" % [path.get_file(), req["pieces"][path]])
		if node != null:
			node.free()
	var placed := {}
	for r: Dictionary in req["rooms"]:
		var packed := load(String(r["scene"])) as PackedScene
		if packed == null:
			problems.append("%s: %s does not load" % [r["id"], r["scene"]])
			continue
		var node := packed.instantiate() as Node3D
		node.position = Vector3(float(r["rect"][0]), float(r["floor_y"]), float(r["rect"][1]))
		root.add_child(node)
		placed[r["id"]] = node
		for group: String in ["Shell", "Dressing"]:
			for name: String in r["walkable" if group == "Shell" else "hide"]:
				var n := node.get_node_or_null("%s/%s" % [group, name])
				if n == null:
					problems.append("%s: %s/%s missing" % [r["id"], group, name])
				elif not _collides(n):
					problems.append("%s: %s/%s has no layer-1 StaticBody3D" % [r["id"], group, name])
	for p: Array in req.get("pads", []):
		Walker.pad(self, p)
	for i in 3:
		await physics_frame
	var space := root.get_world_3d().direct_space_state
	var counts := {}
	var named := {}
	var rays := 0
	for r: Dictionary in req["rooms"]:
		if not placed.has(r["id"]):
			continue
		var fy := float(r["floor_y"])
		var x := float(r["rect"][0]) + STEP / 2
		while x < float(r["rect"][0]) + float(r["rect"][2]):
			var z := float(r["rect"][1]) + STEP / 2
			while z < float(r["rect"][1]) + float(r["rect"][3]):
				var q := PhysicsRayQueryParameters3D.create(Vector3(x, fy + ABOVE, z), Vector3(x, fy - BELOW, z), 1)
				var hit := space.intersect_ray(q)
				rays += 1
				if not hit.is_empty():
					var col := hit["collider"] as Node
					var path := String(root.get_path_to(col))
					var tag: Variant = _surface(col)
					var key := "none" if tag == null else String(tag)
					counts[key] = int(counts.get(key, 0)) + 1
					if path.contains("/Shell/") and (tag == null or not String(tag) in SURFACES) and not named.has(path):
						named[path] = true
						problems.append("%s: no known surface (%s) under %.2f, %.2f on %s" % [r["id"], key, x, z, path])
				z += STEP
			x += STEP
	var walks: Array = []
	for w: Dictionary in req.get("walks", []):
		var res: Dictionary = await Walker.walk(self, RADIUS, w["points"])
		res["name"] = w["name"]
		walks.append(res)
		if not res["arrived"]:
			problems.append("walk %s: the %.2f m capsule stops at %s" % [w["name"], 2 * RADIUS, str(res["end"])])
	return {"problems": problems, "rays": rays, "surfaces": counts, "pieces": pieces, "walks": walks,
		"outside": req.get("outside", []), "closed": req.get("closed", [])}
