extends SceneTree
## The look-approval sheet of a committed House package (art #124, docs/house.md "The export"): runs in an off-screen
## window (a headless Godot draws nothing) inside a review folder that `house --review` staged from the committed
## files under assets/, laid out like the game's tree. Two modes:
##   kit: every kit piece of the request's families in a line-up, one tile per family, under a key light;
##   rooms: every room scene from its door (Doors/Door1, else the first) at eye height, looking into the room, lit only by its
##     own fixtures and a dim review ambient; a room without a door is shot from the middle of its front side. A tile
##     with `eye` and `look` (room-local) is an extra view of its room; with `sun` a key light joins its lamps.
## Writes <out>/<sheet>.png (`width` px wide), <sheet>_1280.png (the agents' copy) and <sheet>.json (per tile).
##   -s res://_review/package_sheet.gd -- request=<abs json> out=<abs dir>

const SMALL := 1280
const INSET := 0.3
const ELEV := 40.0  # the kit tiles' camera elevation, degrees
const ASPECT := 4.0 / 3.0  # the kit tiles' aspect


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var a := {}
	for s in OS.get_cmdline_user_args():
		var kv := s.split("=", true, 1)
		a[kv[0]] = kv[1]
	var req: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(a["request"]))
	var out: String = a["out"]
	DirAccess.make_dir_recursive_absolute(out)
	var cols := int(req["cols"])
	var tiles: Array = req["tiles"]
	var tw := int(req["width"]) / cols
	var th := int(round(tw * 9.0 / 16.0)) if req["mode"] == "rooms" else int(round(tw * 3.0 / 4.0))
	var rows := int(ceil(tiles.size() / float(cols)))
	var sheet := Image.create(tw * cols, th * rows, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.1, 0.1, 0.12))
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.05, 0.05, 0.07) if req["mode"] == "rooms" else Color(0.32, 0.34, 0.38)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.75, 0.75, 0.8)
	env.environment.ambient_light_energy = 0.45 if req["mode"] == "rooms" else 0.6
	env.environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	root.add_child(env)
	var ui := CanvasLayer.new()
	var label := Label.new()
	label.add_theme_font_size_override("font_size", int(req.get("font_size", 64)))
	label.add_theme_color_override("font_outline_color", Color.BLACK)
	label.add_theme_constant_override("outline_size", 10)
	# A dark box behind the title; in rooms mode it sits bottom left, clear of the scenes' own room-name labels
	# (Label3D near the top middle), which it would otherwise overprint.
	var box := StyleBoxFlat.new()
	box.bg_color = Color(0.0, 0.0, 0.0, 0.65)
	box.set_content_margin_all(8.0)
	box.content_margin_left = 14.0
	box.content_margin_right = 14.0
	label.add_theme_stylebox_override("normal", box)
	ui.add_child(label)
	root.add_child(ui)
	var stats := []
	for i in tiles.size():
		var tile: Dictionary = tiles[i]
		var holder := Node3D.new()
		root.add_child(holder)
		var cam := Camera3D.new()
		cam.fov = 75 if req["mode"] == "rooms" else 40
		holder.add_child(cam)
		var info := {}
		if req["mode"] == "rooms":
			info = _room(holder, cam, String(tile["scene"]), float(req["eye"]), tile)
		else:
			info = _kit(holder, cam, tile["pieces"], String(req["dir"]))
		if info.has("error"):
			print("SHEET ", info["error"])
			quit(1)
			return
		cam.current = true
		label.text = String(tile["title"])
		label.reset_size()
		if req["mode"] == "rooms":
			label.position = Vector2(0, root.get_visible_rect().size.y - label.get_combined_minimum_size().y)
		else:
			label.position = Vector2.ZERO
		for f in 16:
			await process_frame
		var img := root.get_texture().get_image()
		img.convert(Image.FORMAT_RGB8)
		info["title"] = tile["title"]
		info["draw_calls"] = int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
		stats.append(info)
		img.resize(tw, th, Image.INTERPOLATE_LANCZOS)
		sheet.blit_rect(img, Rect2i(0, 0, tw, th), Vector2i((i % cols) * tw, (i / cols) * th))
		root.remove_child(holder)
		holder.free()
	var name: String = req["sheet"]
	sheet.save_png(out.path_join(name + ".png"))
	var small := sheet.duplicate() as Image
	small.resize(SMALL, int(round(sheet.get_height() * SMALL / float(sheet.get_width()))), Image.INTERPOLATE_LANCZOS)
	small.save_png(out.path_join(name + "_1280.png"))
	var f := FileAccess.open(out.path_join(name + ".json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"sheet": name, "size": [sheet.get_width(), sheet.get_height()], "tiles": stats}, " "))
	f.close()
	print("SHEET ok ", stats.size())
	quit(0)


## A room scene from its first door at eye height: inward from the wall the door is nearest to, looking at the
## room's middle at 1 m (Door1, else the first door).
func _room(holder: Node3D, cam: Camera3D, path: String, eye: float, tile: Dictionary = {}) -> Dictionary:
	var ps := load(path) as PackedScene
	if ps == null:
		return {"error": "missing " + path}
	var sc: Node3D = ps.instantiate()
	holder.add_child(sc)
	var size: Vector2i = sc.get_meta("size_m", Vector2i(1, 1))  # the plot scene (#128) has no size_m
	for r: Dictionary in tile.get("rooms", []):  # the plot's views: the package's rooms at their plan corners
		var rs := load(String(r["scene"])) as PackedScene
		if rs == null:
			return {"error": "missing " + String(r["scene"])}
		var rn: Node3D = rs.instantiate()
		rn.position = Vector3(r["at"][0], r["at"][1], r["at"][2])
		holder.add_child(rn)
	var w := float(size.x)
	var d := float(size.y)
	var pos := Vector3(w / 2, 0, INSET)
	var door := ""
	var doors := sc.get_node_or_null("Doors")
	if doors and doors.get_child_count() > 0:
		var m := (doors.get_node("Door1") if doors.has_node("Door1") else doors.get_child(0)) as Node3D
		door = String(m.name)
		var p := m.position
		var walls := [[p.x, Vector3.RIGHT], [w - p.x, Vector3.LEFT], [p.z, Vector3.BACK], [d - p.z, Vector3.FORWARD]]
		walls.sort_custom(func(x, y): return x[0] < y[0])
		pos = Vector3(clampf(p.x, INSET, w - INSET), p.y, clampf(p.z, INSET, d - INSET)) + walls[0][1] * INSET
	cam.position = Vector3(pos.x, pos.y + eye, pos.z)
	var target := Vector3(w / 2, pos.y + 1.0, d / 2)
	if Vector2(target.x - pos.x, target.z - pos.z).length() < 0.5:
		target += Vector3(0, 0, 1)
	if tile.has("eye"):  # an extra view (house.toml's [[export.sheet_views]]): its own eye and target, room-local
		door = ""
		cam.position = Vector3(tile["eye"][0], tile["eye"][1], tile["eye"][2])
		target = Vector3(tile["look"][0], tile["look"][1], tile["look"][2])
	if tile.get("sun", false):  # outside the room's own lamps: a low key light from the south-west
		var sun := DirectionalLight3D.new()
		sun.rotation_degrees = Vector3(-35, -140, 0)
		sun.light_energy = 1.2
		holder.add_child(sun)
	cam.look_at_from_position(cam.position, target)
	return {"room": String(sc.name), "door": door, "size_m": [size.x, size.y], "eye": cam.position.y,
		"lights": sc.find_children("*", "Light3D", true, false).size()}


## A family of kit pieces in rows on the ground (the shortest in front), seen from the front and above, under a key light.
func _kit(holder: Node3D, cam: Camera3D, pieces: Array, dir: String) -> Dictionary:
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -35, 0)
	sun.light_energy = 1.1
	holder.add_child(sun)
	var nodes := []
	var area := 0.0
	for id in pieces:
		var ps := load(dir.path_join(String(id) + ".glb")) as PackedScene
		if ps == null:
			return {"error": "missing " + String(id)}
		var n: Node3D = ps.instantiate()
		holder.add_child(n)
		var box := _bounds(n)
		nodes.append([n, box])
		area += (box.size.x + 0.4) * (box.size.z + 0.6)
	# Short pieces in front, tall ones at the back: a row hides less of the rows behind it.
	nodes.sort_custom(func(p, q): return p[1].size.y < q[1].size.y)
	# The row length whose layout, seen from ELEV above, fills the tile's aspect best.
	var best := []
	var best_err := INF
	for k in 24:
		var lay := _layout(nodes, maxf(sqrt(area) * (0.4 + 0.15 * k), 2.0))
		var box: AABB = lay[1]
		var err := absf(log(box.size.x / _seen_h(box) / ASPECT))
		if err < best_err:
			best_err = err
			best = lay
	var all: AABB = best[1]
	for i in nodes.size():
		(nodes[i][0] as Node3D).position = best[0][i]
	var c := all.get_center()
	var vf := deg_to_rad(cam.fov) / 2
	var hf := atan(tan(vf) * ASPECT)
	var dist := maxf(all.size.x / 2 / tan(hf), _seen_h(all) / 2 / tan(vf)) * 1.08 + all.size.z / 2
	var e := deg_to_rad(ELEV)
	cam.look_at_from_position(c + Vector3(0, sin(e), cos(e)) * dist, c)
	return {"pieces": pieces.size(), "extent_m": [all.size.x, all.size.y, all.size.z]}


## The pieces in rows (left to right, rows going back), each row behind the last by its tallest piece so the rows
## seen from ELEV do not hide each other: [positions, the whole AABB].
func _layout(nodes: Array, row_len: float) -> Array:
	var pos := []
	var x := 0.0
	var z := 0.0
	var depth := 0.0
	var height := 0.0
	var all := AABB()
	for i in nodes.size():
		var box: AABB = nodes[i][1]
		if x > 0 and x + box.size.x > row_len:
			x = 0
			z -= depth + 0.4 + height / tan(deg_to_rad(ELEV))
			depth = 0
			height = 0
		pos.append(Vector3(x - box.position.x, -box.position.y, z - box.end.z))
		var placed := AABB(Vector3(x, 0, z - box.size.z), box.size)
		all = placed if i == 0 else all.merge(placed)
		x += box.size.x + 0.4
		depth = maxf(depth, box.size.z)
		height = maxf(height, box.size.y)
	return [pos, all]


## A box's height on screen (m) seen from ELEV above.
func _seen_h(box: AABB) -> float:
	var e := deg_to_rad(ELEV)
	return box.size.z * sin(e) + box.size.y * cos(e)


func _bounds(n: Node3D) -> AABB:
	var box := AABB()
	var first := true
	for v in n.find_children("*", "VisualInstance3D", true, false):
		var b: AABB = (v as VisualInstance3D).get_aabb()
		var t: Transform3D = n.global_transform.affine_inverse() * (v as Node3D).global_transform
		b = t * b
		box = b if first else box.merge(b)
		first = false
	return box
