extends "res://ship/ship.gd"
## The start console in the ship's hall at night (art#263's stations): ship.gd's own "shoot" mode, its pieces, its
## night light, probes and lamps from layouts/ship (tools/blender/console_run.py builds the request: every built
## ship piece plus "start_console" at the hall's centre, turned so its button faces the mouth), and two additions:
## the console wears console.gd's look after ship.gd dresses the ship, and a view's sixth element may name the
## console's state ({"console": "idle" | "order" | "stage"}; idle without it). Started by the runner through
## `_godot.window()` like ship.gd:
##   godot <_godot.window() flags> -s res://console/hall.gd -- <request.json> <out>

const Console = preload("res://console/console.gd")

var _console_look: Dictionary = {}


func _dress(ship: Node3D) -> int:
	var lights: int = super(ship)
	for n: Node in ship.get_children():
		if n.name.begins_with("start_console"):
			_console_look = Console.apply(n as Node3D)
			print("CONSOLE look on %s" % n.name)
	return lights


func _ab(off: Dictionary) -> void:
	super(off)
	if not _console_look.is_empty():
		Console.set_state(_console_look, str(off.get("console", "idle")))
