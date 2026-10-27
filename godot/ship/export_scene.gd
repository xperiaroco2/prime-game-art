extends "res://ship/ship.gd"
## The ship's game-ready scene for `ship --export DIR` (art #335, docs/ship.md "The export"): assembles the night ship
## exactly as ship.gd's shoot does (_environment, _build, _dress, _probes) and saves it as one packed scene of data:
## no script. Headless, in godot/ with the pieces staged as res://import/ship_<id>.glb:
##   godot --headless --path godot -s res://ship/export_scene.gd -- <request.json> <out dir>
## request.json: ship.py's shoot request (pieces, place, outside, light, rooms) plus "stations" [[name, id, package,
##   kind, [x, h, y] Godot, yaw deg]], "spawn" [x, h, y], "spawn_yaw", "size_m" [w, l], "deck_h".
## Writes res://import/ship_export/ (the runner moves it into the package and rewrites the res:// paths):
##   ship.tscn, metal_<name>.tres per shared metal, night_sky.tres, night_env.tres; <out>/export.json.
## The look the shoot gives by code (the glTF materials changed in place by [light.mats], the outside pieces' render
## layer, the vents' heat panel hidden, their well lights) becomes overrides inside each piece's instance, every piece
## an editable instance (the game's ARCHITECTURE 11.2: an override survives a re-save only with its [editable path]).

const EXPORT_DIR: String = "res://import/ship_export"


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 2:
		_fail("usage: -- <request.json> <out dir>")
		return
	var request: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if typeof(request) != TYPE_DICTIONARY:
		_fail("cannot read %s" % args[0])
		return
	_req = request
	_out = args[1]
	nav_blink = false  # the game drives the nav lamps' blink (HANDOFF); the scene holds the shots' static glow
	DirAccess.make_dir_recursive_absolute(_out)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(EXPORT_DIR))
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	_export.call_deferred()


func _export() -> void:
	var before: Array = root.get_children()
	_environment()
	var ship: Node3D = _build()
	var lights: int = _dress(ship)
	_probes()
	ship.name = "Pieces"  # first: the level takes its name "Ship" (a sibling of that name made it @Node3D@n)
	var level: Node3D = Node3D.new()
	level.name = "Ship"
	root.add_child(level)
	var groups: Dictionary = {}
	for group: String in ["Environment", "Lights", "Probes", "Ground"]:
		var g: Node3D = Node3D.new()
		g.name = group
		level.add_child(g)
		groups[group] = g
	ship.reparent(level)
	for n: Node in root.get_children():
		if n in before or n == level:
			continue
		var into: String = "Lights"
		if n is WorldEnvironment:
			into = "Environment"
		elif n is ReflectionProbe:
			into = "Probes"
		elif n is StaticBody3D:
			into = "Ground"
		n.reparent(groups[into])
	var overrides: int = _materials(ship)
	_spots(level)
	level.set_meta("size_m", Vector2(float(_req["size_m"][0]), float(_req["size_m"][1])))
	level.set_meta("deck_h", float(_req["deck_h"]))
	level.set_meta("art_issue", "prime-game-art#335")
	var saved: String = _save_shared()
	if saved != "":
		_fail(saved)
		return
	for n: Node in level.find_children("*", "", true, false):
		if n.owner == null:
			n.owner = level
	for piece: Node in ship.get_children():
		level.set_editable_instance(piece, true)
	var scripts: Array = level.find_children("*", "", true, false).filter(func(n: Node) -> bool: return n.get_script() != null)
	if not scripts.is_empty():
		_fail("a node carries a script: %s" % scripts[0].name)
		return
	var packed: PackedScene = PackedScene.new()
	var error: Error = packed.pack(level)
	if error != OK:
		_fail("pack: %s" % error_string(error))
		return
	error = ResourceSaver.save(packed, EXPORT_DIR.path_join("ship.tscn"))
	if error != OK:
		_fail("save ship.tscn: %s" % error_string(error))
		return
	_write("export.json", {"pieces": ship.get_child_count(), "emissive_lights": lights, "overrides": overrides,
		"lights": groups["Lights"].get_child_count(), "probes": groups["Probes"].get_child_count(),
		"stations": level.get_node("Stations").get_child_count(), "metals": _metals.keys()})
	print("SHIP export saved %s" % EXPORT_DIR)
	quit(0)


## Every glTF material the look changed in place becomes a copy set as its surface's override (the instance's own
## state, saved with the scene); the metals already are overrides. Returns the overrides set.
func _materials(ship: Node3D) -> int:
	var copies: Dictionary = {}
	var count: int = 0
	for n: Node in ship.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n
		if mi.mesh == null:
			continue
		for i: int in mi.mesh.get_surface_count():
			var mat: Material = mi.mesh.surface_get_material(i)
			if mi.get_surface_override_material(i) != null:
				count += 1
				continue
			if not (mat is BaseMaterial3D):
				continue
			if not copies.has(mat):
				var copy: BaseMaterial3D = (mat as BaseMaterial3D).duplicate() as BaseMaterial3D
				copy.resource_name = mat.resource_name
				copies[mat] = copy
			mi.set_surface_override_material(i, copies[mat])
			count += 1
	return count


## The station spots (Stations/<Name>: Marker3D, +Z the spot's normal) and the spawn (Markers/Spawn).
func _spots(level: Node3D) -> void:
	var stations: Node3D = Node3D.new()
	stations.name = "Stations"
	level.add_child(stations)
	for s: Array in _req["stations"]:  # [name, id, package, kind, [x, h, y] Godot, yaw]
		var m: Marker3D = Marker3D.new()
		m.name = str(s[0])
		m.position = _v(s[4])
		m.rotation_degrees.y = float(s[5])
		m.set_meta("spot", str(s[1]))
		m.set_meta("package", str(s[2]))
		m.set_meta("kind", str(s[3]))
		stations.add_child(m)
	var markers: Node3D = Node3D.new()
	markers.name = "Markers"
	level.add_child(markers)
	var spawn: Marker3D = Marker3D.new()
	spawn.name = "Spawn"
	spawn.position = _v(_req["spawn"])
	spawn.rotation_degrees.y = float(_req["spawn_yaw"])
	markers.add_child(spawn)


## The shared metals, the sky's material and the environment as .tres files the scene refers to.
func _save_shared() -> String:
	var items: Array = []
	for name: String in _metals:
		items.append([_metals[name], "metal_%s.tres" % name])
	items.append([_sky_mat, "night_sky.tres"])
	items.append([_env, "night_env.tres"])
	for item: Array in items:
		if item[0] is ShaderMaterial:
			_colours(item[0])
		var path: String = EXPORT_DIR.path_join(item[1])
		var error: Error = ResourceSaver.save(item[0], path, ResourceSaver.FLAG_CHANGE_PATH)
		if error != OK:
			return "save %s: %s" % [path, error_string(error)]
	return ""


## ship.gd's _build with each piece instantiated in edit state: the instance keeps its scene's state, so packing saves
## only what the look changed inside it (at runtime instantiate() keeps none, and every mesh and shape was saved as a
## change: a 14 MB scene).
func _build() -> Node3D:
	var ship: Node3D = Node3D.new()
	ship.name = "Ship"
	root.add_child(ship)
	for p: Array in _req["place"]:
		var node: Node3D = _scene(p[0]).instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE) as Node3D
		node.name = "%s_%d" % [p[0], ship.get_child_count()]
		node.position = _v(p[1])
		node.rotation_degrees.y = float(p[2])
		ship.add_child(node)
		if p[0] in _req.get("outside", []):
			_set_layers(node, OUTSIDE_LAYER)
	var ground: StaticBody3D = StaticBody3D.new()
	var shape: CollisionShape3D = CollisionShape3D.new()
	shape.shape = WorldBoundaryShape3D.new()
	ground.add_child(shape)
	root.add_child(ground)
	if not _req["pieces"].has("ground"):
		_fail("the clearing's ground piece is missing")
	return ship


## A vec3 `source_color` uniform set from a Vector3 (ship.gd's metals and sky) is saved as null: the value is not the
## uniform's Color type. The Color that renders the same: the renderer takes a Color as sRGB and turns it linear,
## a Vector3 as it is, so the Vector3 goes in as its sRGB.
func _colours(sm: ShaderMaterial) -> void:
	for u: Dictionary in sm.shader.get_shader_uniform_list():
		var value: Variant = sm.get_shader_parameter(u["name"])
		if value is Vector3:
			var v: Vector3 = value
			sm.set_shader_parameter(u["name"], Color(v.x, v.y, v.z).linear_to_srgb())
