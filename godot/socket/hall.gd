extends "res://ship/ship.gd"
## The crystal sockets in the ship's hall at night (art#263's stations): ship.gd's own "shoot" mode, its pieces, its
## night light, probes and lamps from layouts/ship (tools/blender/socket_run.py builds the request: every built ship
## piece plus "crystal_socket" on the four socket spots, each turned so its glTF +Z is the spot's normal), and three
## additions: each socket wears socket.gd's look, the built crystal (the request's "crystal") is parented on each
## socket's crystal_anchor with crystal.gd's look, and a view's sixth element may name the state
## ({"socket": "charged" | "spent" | "empty" | "mixed"}; charged without it; mixed: the spots in order charged,
## spent, empty, charged). Started by the runner through `_godot.window()` like ship.gd:
##   godot <_godot.window() flags> -s res://socket/hall.gd -- <request.json> <out>

const Socket = preload("res://socket/socket.gd")
const Crystal = preload("res://crystal/crystal.gd")
const MIXED := ["charged", "spent", "empty", "charged"]

var _sockets: Array = []


## ship.gd dresses the ship without the sockets (its pass would give the GLB's plain emissive fallbacks strip lights
## the game never has); the sockets then get socket.gd's look and their crystals.
func _dress(ship: Node3D) -> int:
	var sockets: Array[Node3D] = []
	for n: Node in ship.get_children():
		if n.name.begins_with("crystal_socket"):
			sockets.append(n as Node3D)
	for s: Node3D in sockets:
		ship.remove_child(s)
	var lights: int = super(ship)
	var crystal: PackedScene = load(str(_req["crystal"]))
	for s: Node3D in sockets:
		ship.add_child(s)
		var look: Dictionary = Socket.apply(s)
		var anchor: Node3D = s.find_child("crystal_anchor", true, false)
		if anchor == null:
			_fail("no crystal_anchor in %s" % s.name)
			return lights
		var c: Node3D = crystal.instantiate() as Node3D
		anchor.add_child(c)
		var cl: Dictionary = Crystal.apply(c)
		Socket.seat_crystal(cl)
		_sockets.append({"look": look, "crystal": c, "crystal_look": cl})
		var a: Vector3 = anchor.global_position
		var out: Vector3 = anchor.global_transform.basis.z
		print("SOCKET look on %s: anchor (%.3f, %.3f, %.3f), out (%.3f, %.3f, %.3f)" % [s.name, a.x, a.y, a.z, out.x,
			out.y, out.z])
	return lights


func _ab(off: Dictionary) -> void:
	super(off)
	var state: String = str(off.get("socket", "charged"))
	for i: int in _sockets.size():
		var s: Dictionary = _sockets[i]
		var st: String = MIXED[i % MIXED.size()] if state == "mixed" else state
		Socket.set_state(s["look"], st)
		(s["crystal"] as Node3D).visible = st != "empty"
		Crystal.set_charge(s["crystal_look"], 0.0 if st == "spent" else 1.0)
