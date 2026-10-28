extends "res://ship/ship.gd"
## The crystal chargers in the lens rooms at night (art#263's stations): ship.gd's own "shoot" mode, its pieces,
## night light, probes and lamps from layouts/ship, and two additions: every charger wears charger.gd's look with a
## crystal seated on its own carrier's anchor (crystal.gd's look), and a view's sixth element sets them all
## ({"charger": "idle" | "charging" | "charged", "ring" and "carrier" (deg), "rise" (0..1), "crystal" (shown),
## "charge" (0..1)}). Two callers build the request: `ship --shoot --charger` (tools/runner/commands/ship.py
## charger_places: a charger on both spots, renewer_e and renewer_w, its front along the spot's normal, and a crystal
## by each) and tools/blender/charger_run.py (the charger on renewer_e). Each crystal goes to the nearest charger.
## Started by the runner through `_godot.window()`:
##   godot <_godot.window() flags> -s res://charger/room.gd -- <request.json> <out>
##
## lens C step 4: step 3 kept one charger look and one crystal; both crystals sat on the last charger's anchor and
## the first stayed at crystal.gd's full charge with its omni at 2.6 (the west alcove's cyan wash). Now a pair each.

const Charger = preload("res://charger/charger.gd")
const Crystal = preload("res://crystal/crystal.gd")
const Traces = preload("res://charger/traces.gd")

## {"charger": look, "crystal": Node3D or null, "crystal_look": Dictionary, "traces": its bound trace surfaces}
var _pairs: Array[Dictionary] = []


## ship.gd dresses the ship without the chargers and the crystals (its pass would give the GLBs' plain emissive
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
			var look: Dictionary = Charger.apply(c)
			var traces: int = Traces.bind(look, ship)   # its alcove's back-panel traces (3 surfaces)
			_pairs.append({"charger": look, "node": c, "crystal": null, "crystal_look": {}, "traces": traces})
			print("CHARGER look on %s; %d trace surfaces" % [c.name, traces])
	for c: Node3D in mine:
		if not c.name.begins_with("energy_crystal") or _pairs.is_empty():
			continue
		var best: Dictionary = {}
		var best_d := INF
		for p: Dictionary in _pairs:
			var d: float = (p["node"] as Node3D).global_position.distance_to(c.global_position)
			if p["crystal"] == null and d < best_d:
				best = p
				best_d = d
		if best.is_empty():
			push_warning("charger/room.gd: no free charger for %s" % c.name)
			continue
		best["crystal"] = c
		best["crystal_look"] = Crystal.apply(c)
		Charger.seat_crystal(best["charger"], c, best["crystal_look"])
		print("CHARGER crystal %s seated on %s (%.2f m)" % [c.name, (best["node"] as Node3D).name, best_d])
	return lights


func _ab(off: Dictionary) -> void:
	super(off)
	for p: Dictionary in _pairs:
		var look: Dictionary = p["charger"]
		Charger.set_state(look, str(off.get("charger", "idle")))
		Charger.set_carrier(look, float(off.get("rise", 0.0)), deg_to_rad(float(off.get("carrier", 0.0))))
		Charger.set_ring(look, deg_to_rad(float(off.get("ring", 0.0))))
		var state := str(off.get("charger", "idle"))   # the traces: dim idle, the charge's front, full when charged
		Traces.set_panel(look, 0.0 if state == "idle" else 1.0 if state == "charged" else float(off.get("charge", 1.0)))
		var crystal: Node3D = p["crystal"]
		if crystal == null:
			continue
		crystal.visible = bool(off.get("crystal", false))
		Crystal.set_charge(p["crystal_look"], float(off.get("charge", 1.0)))
		# set_charge hides the omni when spent; a hidden crystal never lights the room
		var omni: OmniLight3D = p["crystal_look"]["omni"]
		omni.visible = omni.visible and crystal.visible
