extends Node3D
## The lobby hall's level script (prime-game-art#356 step 5c2, docs/lobby.md "Step 5c2"): the one script of the
## package, on the root LobbyHall of levels/lobby/lobby_hall.tscn. A saved scene cannot remove a node inside an
## instance, so the ship package's nodes the lobby must not have (its forest Clearing, its Environment with a second
## WorldEnvironment, its suns under Ship/Lights) are saved hidden and switched off. On _ready this script frees them, as
## the art's assembly (hall.gd) and the ship package's HANDOFF S7 do, so the game gets the art's scene; one frame later
## every reflection probe (UPDATE_ONCE) is taken out of the tree and put back, so it captures again with them gone.
## Nothing else runs: the jaw nose is saved shut, the ship's render layer 11 and the glow scaling are overrides in the
## scene. No res:// path here: the file moves with the package.

## The nodes freed on _ready, relative to this node (export_scene.gd fills it from layouts/lobby [ship.package] free).
@export var ship_free: Array[NodePath] = []


func _ready() -> void:
	var freed: int = 0
	for p: NodePath in ship_free:
		var n: Node = get_node_or_null(p)
		if n == null:
			push_warning("lobby_hall.gd: no node %s to free" % p)
			continue
		n.get_parent().remove_child(n)
		n.free()
		freed += 1
	set_meta("ship_freed", freed)
	_recapture.call_deferred()


## Each probe out of the tree and back in its place: a probe entering the scenario again renders its capture again.
func _recapture() -> void:
	await get_tree().process_frame
	var probes: Array[Node] = find_children("*", "ReflectionProbe", true, false)
	for probe: Node in probes:
		var parent: Node = probe.get_parent()
		var at: int = probe.get_index()
		parent.remove_child(probe)
		parent.add_child(probe)
		parent.move_child(probe, at)
	set_meta("probes_recaptured", probes.size())
