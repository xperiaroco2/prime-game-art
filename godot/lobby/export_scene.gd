extends "res://lobby/hall.gd"
## The lobby hall's game-ready scene for `lobby --export DIR` (art #356 step 5b, docs/lobby.md "The export"):
## assembles the hall exactly as hall.gd's shoot does (_environment, _build with the ship package, _glass,
## _apply_light) and saves it as one packed scene of data, no script. Headless, in godot/ with the hall's pieces staged
## as res://import/lobby_<id>.glb, the Earth's textures as res://import/lobby_earth/ and the ship package as
## res://import/ship_pkg/:
##   godot --headless --path godot -s res://lobby/export_scene.gd -- <request.json> <out dir>
## request.json: lobby.py's shoot request plus "spawns" [[x, y, z]], "spawn_yaw", "size_m" [w, l], "meta" {key: value}.
## Writes res://import/lobby_export/ (the runner moves it into the package and rewrites the res:// paths):
##   lobby_hall.tscn, lobby_env.tres, earth_object.tres, window_glass.tres; <out>/export.json.
## Everything hall.gd sets by code becomes overrides inside the instances (the hall's pieces and the ship, each an
## editable instance, the ship's own pieces too): the glass, the hanging lamps' shadows, the glow surfaces, the ship's
## render layer 11 and its lamps. The package's nodes hall.gd frees ([ship.package] free) are switched off instead
## (hidden, disabled, the environment cleared): a packed scene cannot remove a node of an instance.

const EXPORT_DIR: String = "res://import/lobby_export"


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
	_gen = PackedScene.GEN_EDIT_STATE_INSTANCE
	_hide_freed = true
	DirAccess.make_dir_recursive_absolute(_out)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(EXPORT_DIR))
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	_export.call_deferred()


func _export() -> void:
	var before: Array = root.get_children()
	_environment()
	_build()
	_glass()
	_apply_light(_req["light"])
	var hall: Node3D = root.get_node("Lobby") as Node3D
	var ship: Node3D = _placed["ship_pkg"][0]
	var level: Node3D = Node3D.new()
	level.name = "LobbyHall"
	root.add_child(level)
	var groups: Dictionary = {}
	for g: String in ["Hall", "Ship", "Earth", "Environment", "Lights", "Probes", "Markers"]:
		if g == "Hall" or g == "Ship":
			continue
		var n: Node3D = Node3D.new()
		n.name = g
		groups[g] = n
	hall.name = "Hall"
	hall.reparent(level)
	ship.reparent(level)
	ship.name = "Ship"
	for g: String in ["Earth", "Environment", "Lights", "Probes", "Markers"]:
		level.add_child(groups[g])
	for n: Node in root.get_children():
		if n in before or n == level:
			continue
		if n is WorldEnvironment:
			n.name = "WorldEnvironment"
			n.reparent(groups["Environment"])
		elif n is MeshInstance3D:
			n.reparent(groups["Earth"])   # EarthObject
		elif n.name == "light_rig":
			for c: Node in n.get_children():
				c.reparent(groups["Probes"] if c is ReflectionProbe else groups["Lights"])
			n.free()
		elif n is Camera3D or n is CanvasLayer:
			n.free()
		else:
			_fail("an unexpected node at the root: %s" % n.name)
			return
	var i: int = 0
	for at: Array in _req["spawns"]:
		var m: Marker3D = Marker3D.new()
		m.name = "Spawn%d" % i
		m.position = _v(at)
		m.rotation_degrees.y = float(_req["spawn_yaw"])
		m.set_meta("index", i)
		groups["Markers"].add_child(m)
		i += 1
	var meta: Dictionary = _req["meta"]
	for k: String in meta:
		level.set_meta(k, meta[k])
	level.set_meta("size_m", Vector2(float(_req["size_m"][0]), float(_req["size_m"][1])))
	level.set_meta("camera_far_m", _far)
	for n: Node in level.find_children("*", "", true, false):
		for k: String in ["lobby_dropped", "lobby_e0"]:
			if n.has_meta(k):
				n.remove_meta(k)
	var saved: String = _save_shared(groups)
	if saved != "":
		_fail(saved)
		return
	for n: Node in level.find_children("*", "", true, false):
		if n.owner == null:
			n.owner = level
	var editable: int = 0
	for n: Node in level.find_children("*", "", true, false):
		if n.scene_file_path != "":
			level.set_editable_instance(n, true)
			editable += 1
	var scripts: Array = level.find_children("*", "", true, false).filter(func(n: Node) -> bool: return n.get_script() != null)
	if not scripts.is_empty():
		_fail("a node carries a script: %s" % scripts[0].name)
		return
	var packed: PackedScene = PackedScene.new()
	var error: Error = packed.pack(level)
	if error != OK:
		_fail("pack: %s" % error_string(error))
		return
	error = ResourceSaver.save(packed, EXPORT_DIR.path_join("lobby_hall.tscn"))
	if error != OK:
		_fail("save lobby_hall.tscn: %s" % error_string(error))
		return
	_write("export.json", {"hall_pieces": hall.get_child_count(), "lights": groups["Lights"].get_child_count(),
		"probes": groups["Probes"].get_child_count(), "spawns": groups["Markers"].get_child_count(),
		"editable_instances": editable, "ship": _pkg_info, "camera_far_m": _far,
		"emissive_surfaces": _emissive.size()})
	print("LOBBY export saved %s" % EXPORT_DIR)
	quit(0)


## The environment, the Earth's material and the glass as their own .tres files (the scene refers to them).
func _save_shared(groups: Dictionary) -> String:
	var env: Environment = (groups["Environment"].get_child(0) as WorldEnvironment).environment
	var earth: MeshInstance3D = groups["Earth"].get_child(0) as MeshInstance3D
	var glass: Material = null
	for top: Node in _placed.get("window_glass", []):
		for c: Node in top.find_children("*", "MeshInstance3D", true, false):
			var mi: MeshInstance3D = c as MeshInstance3D
			for s: int in mi.mesh.get_surface_count():
				if mi.get_surface_override_material(s) is ShaderMaterial:
					glass = mi.get_surface_override_material(s)
	if glass == null:
		return "no window glass material"
	for pair: Array in [[env, "lobby_env.tres"], [earth.material_override, "earth_object.tres"], [glass, "window_glass.tres"]]:
		var path: String = EXPORT_DIR.path_join(pair[1])
		var error: Error = ResourceSaver.save(pair[0], path)
		if error != OK:
			return "save %s: %s" % [path, error_string(error)]
		(pair[0] as Resource).take_over_path(path)
	# a cleared environment does not survive the pack (null is no override), and two WorldEnvironments fight: the
	# ship's own (switched off by hall.gd) takes the hall's environment, so whichever Godot picks draws the hall's look
	for w: Node in (_placed["ship_pkg"][0] as Node).find_children("*", "WorldEnvironment", true, false):
		(w as WorldEnvironment).environment = env
	return ""
