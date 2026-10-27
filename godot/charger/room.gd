extends "res://ship/ship.gd"
## The crystal charger in the east lens room at night (art#263's stations): ship.gd's own "shoot" mode, its pieces,
## night light, probes and lamps from layouts/ship (tools/blender/charger_run.py builds the request: every built ship
## piece plus "crystal_charger" on renewer_e, its front along the spot's normal, and "energy_crystal"), and two
## additions: the charger wears charger.gd's look with the crystal seated on its carrier's anchor (crystal.gd's look),
## and a view's sixth element sets the charger ({"charger": "idle" | "charging" | "charged", "ring" and "carrier"
## (deg), "rise" (0..1), "crystal" (shown), "charge" (0..1)}). Started by the runner through `_godot.window()`:
##   godot <_godot.window() flags> -s res://charger/room.gd -- <request.json> <out>

const Charger = preload("res://charger/charger.gd")
const Crystal = preload("res://crystal/crystal.gd")

var _charger_look: Dictionary = {}
var _crystal: Node3D = null
var _crystal_look: Dictionary = {}


## ship.gd dresses the ship without the charger and the crystal (its pass would give the GLBs' plain emissive
## fallbacks strip lights the game never has); they then get their own looks.
func _dress(ship: Node3D) -> int:
	var mine: Array[Node3D] = []
	for n: Node in ship.get_children():
		if n.name.begins_with("crystal_charger") or n.name.begins_with("energy_crystal"):
			mine.append(n as Node3D)
	for c: Node3D in mine:
		ship.remove_child(c)
	var lights: int = super(ship)
	for c: Node3D in mine:
		ship.add_child(c)
	for c: Node3D in mine:
		if c.name.begins_with("crystal_charger"):
			_charger_look = Charger.apply(c)
			print("CHARGER look on %s" % c.name)
	for c: Node3D in mine:
		if c.name.begins_with("energy_crystal") and not _charger_look.is_empty():
			_crystal = c
			_crystal_look = Crystal.apply(c)
			Charger.seat_crystal(_charger_look, c, _crystal_look)
			print("CHARGER crystal seated on %s" % str(c.get_parent().name))
	return lights


func _ab(off: Dictionary) -> void:
	super(off)
	if _charger_look.is_empty():
		return
	Charger.set_state(_charger_look, str(off.get("charger", "idle")))
	Charger.set_carrier(_charger_look, float(off.get("rise", 0.0)), deg_to_rad(float(off.get("carrier", 0.0))))
	Charger.set_ring(_charger_look, deg_to_rad(float(off.get("ring", 0.0))))
	if _crystal != null:
		_crystal.visible = bool(off.get("crystal", false))
		Crystal.set_charge(_crystal_look, float(off.get("charge", 1.0)))
		(_crystal_look["omni"] as OmniLight3D).visible = _crystal.visible
