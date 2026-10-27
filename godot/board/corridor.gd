extends "res://ship/ship.gd"
## The breaker board in the ship's corridors at night (art#263's stations): ship.gd's own "shoot" mode, its pieces,
## night light, probes and lamps from layouts/ship (tools/blender/board_run.py builds the request: every built ship
## piece plus "breaker_board" on breaker_e and breaker_w), and two additions: each board wears board.gd's look, and a
## view's sixth element may hold the boards' state ({"board": {"open": [4 x 0..1], "on": [4 x bool], "problem":
## bool}}; all on without it). Started by the runner through `_godot.window()` like ship.gd:
##   godot <_godot.window() flags> -s res://board/corridor.gd -- <request.json> <out>

const Board = preload("res://board/board.gd")

var _board_looks: Array = []


## ship.gd dresses the ship without the boards (its pass would give their emissive fallbacks strip lights the game
## never has); each board then gets board.gd's look.
func _dress(ship: Node3D) -> int:
	var boards: Array[Node3D] = []
	for n: Node in ship.get_children():
		if n.name.begins_with("breaker_board"):
			boards.append(n as Node3D)
	for b: Node3D in boards:
		ship.remove_child(b)
	var lights: int = super(ship)
	for b: Node3D in boards:
		ship.add_child(b)
		var look: Dictionary = Board.apply(b)
		if look.is_empty():
			_fail("no board look on %s" % b.name)
		_board_looks.append(look)
		print("BOARD look on %s" % b.name)
	return lights


func _ab(off: Dictionary) -> void:
	super(off)
	var st: Dictionary = off.get("board", {})
	for look: Dictionary in _board_looks:
		var open: Array = st.get("open", [0, 0, 0, 0])
		var on: Array = st.get("on", [true, true, true, true])
		for i: int in 4:
			Board.set_shell(look, i, float(open[i]))
			Board.set_on(look, i, bool(on[i]))
		Board.set_problem(look, bool(st.get("problem", false)))
