extends "res://lobby/hall.gd"
## The lobby's bar, mirror and match console in our hall (art #389, #390, #391): hall.gd's scene (the hall, the ship
## and the light of `lobby --shoot`) with each piece placed by the request ("place": [["furn_<piece>", origin, yaw]]).
## Started only by tools/blender/lobby_furniture_run.py through `_godot.window()` (CLAUDE.md, #214), never by hand.
## The request's "furniture": {"views": [[name, title, eye, target, fov]] in the hall's frame, "sheets": [[file,
## concept png, [[view, ...], ...] rows]]}: one <view>.png per view, each sheet's rows of views (the concept first when
## the row names "concept"), shots.json with the markers' places.

func _shoot() -> void:
	var fu: Dictionary = _req["furniture"]
	_setup_scene()
	var shots: Dictionary = {}
	var images: Dictionary = {}
	for v: Array in fu["views"]:
		_camera.fov = float(v[4])
		_camera.look_at_from_position(_v(v[2]), _v(v[3]), Vector3.UP)
		images[v[0]] = await _shot(v[0], v[1], shots)
	for s: Array in fu["sheets"]:
		var concept: Image = Image.load_from_file(s[1])
		concept.convert(Image.FORMAT_RGB8)
		var rows: Array = []
		for r: Array in s[2]:
			var row: Array = []
			for n: String in r:
				row.append(concept if n == "concept" else images[n])
			rows.append(row)
		_save(_sheet(rows), _out.path_join(s[0]))
	var probe: Dictionary = {}
	for pid: String in _placed:
		if not pid.begins_with("furn_"):
			continue
		for top: Node in _placed[pid]:
			for m: Node in top.find_children("*", "Node3D", true, false):
				if m.get_class() == "Node3D" and m.get_child_count() == 0:
					var p: Vector3 = (m as Node3D).global_position
					probe["%s/%s" % [pid, m.name]] = [snappedf(p.x, 0.001), snappedf(p.y, 0.001), snappedf(p.z, 0.001)]
	_write("shots.json", {"shots": shots, "markers": probe})
	print("FURNITURE shots %d, markers %s" % [shots.size(), probe])
	quit(0)
