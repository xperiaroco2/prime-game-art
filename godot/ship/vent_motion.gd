extends SceneTree
## The throat vents' motion proof and review shots (art #263 step 2, station 1; docs/ship.md "Station 1: the throat
## vents"), run by `tools/run.py ship --motion DIR` in the off-screen window (never headless, never on screen):
##   godot --path godot -s res://ship/vent_motion.gd -- <request.json> <out dir>
## On the imported GLBs: every leaf by its name, the slats driven from one 0..1 value each (rotation.x = -open_rad * t
## about the hinge at the node's origin) and the marker (position.y = rest + travel * t). Checks by numbers (each
## slat's hinge edge does not move, no slat cuts the next or leaves the frame's opening, the marker stays on its bar),
## then the video's frames (shut, open, breathing, slam shut; the marker up and down), the states sheet, the vent alone
## from 8 sides and the close-ups. Writes <out>/motion.json and PNGs; the runner encodes the frames into an MP4.

const Offscreen = preload("res://lib/offscreen.gd")

var _req: Dictionary
var _out: String
var _vents: Dictionary = {}     # id -> root Node3D
var _cam: Camera3D
var _label: Label
var _rest: Dictionary = {}      # id -> the marker's imported position.y (its rest point, the bar's bottom)


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 2:
		_fail("usage: -- <request.json> <out dir>")
		return
	_req = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	_out = args[1]
	DirAccess.make_dir_recursive_absolute(_out.path_join("frames"))
	if DisplayServer.get_name() == "headless":
		_fail("the motion proof needs a window (off-screen), not --headless")
		return
	var placed: String = Offscreen.place()
	if placed != "":
		_fail(placed)
		return
	create_timer(float(_req.get("watchdog_s", 600))).timeout.connect(_fail.bind("not done in time"))
	_run()


func _fail(why: String) -> void:
	printerr("VENT error %s" % why)
	quit(1)


func _v(a: Array) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))


# --- the scene ----------------------------------------------------------------------------------------------------
func _stage() -> void:
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.16, 0.17, 0.19)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.55, 0.57, 0.62)
	env.ambient_light_energy = 0.55
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.glow_enabled = true
	env.glow_intensity = 0.5
	var we: WorldEnvironment = WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	for d: Array in [[Vector3(-35, 35, 0), 1.6, true], [Vector3(-15, -120, 0), 0.6, false], [Vector3(-60, 160, 0), 0.5, false]]:
		var sun: DirectionalLight3D = DirectionalLight3D.new()
		sun.rotation_degrees = d[0]
		sun.light_energy = d[1]
		sun.shadow_enabled = d[2]
		root.add_child(sun)
	_cam = Camera3D.new()
	_cam.fov = 40.0
	root.add_child(_cam)
	_cam.make_current()
	var layer: CanvasLayer = CanvasLayer.new()
	_label = Label.new()
	_label.position = Vector2(14, 10)
	_label.add_theme_font_size_override("font_size", 26)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 6)
	layer.add_child(_label)
	root.add_child(layer)
	var x: float = 0.0
	for id: String in _req["ids"]:
		var scene: PackedScene = load("res://import/ship_%s.glb" % id) as PackedScene
		if scene == null:
			_fail("cannot load %s" % id)
			return
		var node: Node3D = scene.instantiate() as Node3D
		node.position = Vector3(x, 0, 0)
		root.add_child(node)
		_vents[id] = node
		var mk: Node3D = _leaf(id, "marker")
		_rest[id] = mk.position.y if mk != null else 0.0
		x += float(_req["gap_m"])
	# the review's wall and floor replica (the throat wall's profile from the builder's numbers), off for the 8 sides
	var wall: MeshInstance3D = MeshInstance3D.new()
	wall.name = "Backdrop"
	var st: SurfaceTool = SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var w: Dictionary = _req["wall"]
	var f: float = float(w["floor"])
	var prof: Array = [[0.0, 0.0], [0.0, float(w["bend"])], [float(w["in"]), float(w["top"])]]
	for k: int in 2:
		var a: Array = prof[k]
		var b: Array = prof[k + 1]
		var q: Array = [Vector3(-2, f + a[1], a[0]), Vector3(x + 2, f + a[1], a[0]), Vector3(x + 2, f + b[1], b[0]),
			Vector3(-2, f + b[1], b[0])]
		for i: int in [0, 1, 2, 0, 2, 3]:
			st.add_vertex(q[i])
	for i: int in [0, 1, 2, 0, 2, 3]:
		st.add_vertex([Vector3(-2, f, 0), Vector3(-2, f, 3), Vector3(x + 2, f, 3), Vector3(x + 2, f, 0)][i])
	st.generate_normals()
	wall.mesh = st.commit()
	var wm: StandardMaterial3D = StandardMaterial3D.new()
	wm.albedo_color = Color(0.42, 0.43, 0.45)
	wm.metallic = 0.5
	wm.roughness = 0.5
	wm.cull_mode = BaseMaterial3D.CULL_DISABLED
	wall.material_override = wm
	root.add_child(wall)


func _leaf(id: String, suffix: String) -> Node3D:
	return _vents[id].find_child("%s_%s" % [id, suffix], true, false) as Node3D


func _drive(id: String, slats: float, marker: float) -> void:
	for k: int in range(1, int(_req["slats"]) + 1):
		_leaf(id, "slat%d" % k).rotation.x = -float(_req["open_rad"]) * slats
	var m: Node3D = _leaf(id, "marker")
	m.position.y = float(_rest[id]) + float(_req["mark_travel"]) * marker


## A mesh's vertices in the vent's frame (the vent root at the origin, not turned).
func _verts(id: String, node: MeshInstance3D) -> PackedVector3Array:
	var to_vent: Transform3D = (_vents[id] as Node3D).global_transform.affine_inverse() * node.global_transform
	var out: PackedVector3Array = PackedVector3Array()
	for s: int in node.mesh.get_surface_count():
		for p: Vector3 in node.mesh.surface_get_arrays(s)[Mesh.ARRAY_VERTEX]:
			out.append(to_vent * p)
	return out


## The slat's cross-sections: per distinct x, the convex hull of its vertices' (z, y) (a curved gill blade is not
## star-shaped round its centre; its hull is a safe outline: hulls apart means blades apart).
func _sections(pts: PackedVector3Array) -> Dictionary:
	var by_x: Dictionary = {}
	for p: Vector3 in pts:
		var key: int = roundi(p.x * 1000.0)
		if not by_x.has(key):
			by_x[key] = PackedVector2Array()
		by_x[key].append(Vector2(p.z, p.y))
	for key: int in by_x:
		by_x[key] = Geometry2D.convex_hull(by_x[key])
	return by_x


# --- the checks ---------------------------------------------------------------------------------------------------
func _check(id: String) -> Dictionary:
	var r: Dictionary = {"missing": [], "problems": []}
	var names: Array = ["marker", "body", "column", "heat", "lamp", "band", "hand"]
	for k: int in range(1, int(_req["slats"]) + 1):
		names.append("slat%d" % k)
	for suffix: String in names:
		if _leaf(id, suffix) == null:
			r["missing"].append(suffix)
	var shapes: int = 0
	for body: Node in _vents[id].find_children("*", "StaticBody3D", true, false):
		for cs: Node in body.find_children("*", "CollisionShape3D", true, false):
			if (cs as CollisionShape3D).shape is ConvexPolygonShape3D:
				shapes += 1
	r["convex_colliders"] = shapes
	var tris: int = 0
	for mi: Node in _vents[id].find_children("*", "MeshInstance3D", true, false):
		for s: int in (mi as MeshInstance3D).mesh.get_surface_count():
			tris += (mi as MeshInstance3D).mesh.surface_get_array_index_len(s) / 3
	r["triangles"] = tris
	var mats: Array = []
	for mi: Node in _vents[id].find_children("*", "MeshInstance3D", true, false):
		for s: int in (mi as MeshInstance3D).mesh.get_surface_count():
			var m: Material = (mi as MeshInstance3D).mesh.surface_get_material(s)
			if m != null and not mats.has(m.resource_name):
				mats.append(m.resource_name)
	mats.sort()
	r["materials"] = mats
	if not r["missing"].is_empty() or shapes != 2:
		r["problems"].append("missing %s, %d convex colliders" % [str(r["missing"]), shapes])
		return r
	var o: Dictionary = _req["vents"][id]["opening"]   # u0 u1 h0 h1 (h absolute), v_back, v_max
	# each slat: its origin on its upper edge, the edge still at 0 and 1, the hinge's drift, the tip's swing
	var edge_drift: float = 0.0
	var origin_off: float = 0.0
	var tip_swing: float = 0.0
	var cuts: Array = []
	var outside: Array = []
	var steps: int = 10
	var sections: Array = []   # [t][k] -> Dictionary
	for i: int in steps + 1:
		var t: float = float(i) / steps
		_drive(id, t, 0.0)
		var row: Array = []
		for k: int in range(1, int(_req["slats"]) + 1):
			var node: MeshInstance3D = _leaf(id, "slat%d" % k) as MeshInstance3D
			var pts: PackedVector3Array = _verts(id, node)
			row.append(_sections(pts))
			for p: Vector3 in pts:
				var inside_open: bool = p.x > o["u0"] and p.x < o["u1"] and p.y > o["h0"] and p.y < o["h1"]
				if not inside_open or p.z < o["v_back"] or p.z > o["v_max"]:
					outside.append("slat%d t %.1f at (%.3f, %.3f, %.3f)" % [k, t, p.x, p.y, p.z])
					break
		sections.append(row)
		for k: int in int(_req["slats"]) - 1:
			for key: int in row[k]:
				if row[k + 1].has(key) and not Geometry2D.intersect_polygons(row[k][key], row[k + 1][key]).is_empty():
					cuts.append("slat%d/slat%d at t %.1f, x %.3f" % [k + 1, k + 2, t, key / 1000.0])
					break
	for k: int in range(1, int(_req["slats"]) + 1):
		var node: MeshInstance3D = _leaf(id, "slat%d" % k) as MeshInstance3D
		_drive(id, 0.0, 0.0)
		var p0: PackedVector3Array = _verts(id, node)
		var local: PackedVector3Array = node.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
		_drive(id, 1.0, 0.0)
		var p1: PackedVector3Array = _verts(id, node)
		var top: float = -1e9
		for q: Vector3 in local:
			top = maxf(top, q.y)
		origin_off = maxf(origin_off, absf(top))
		for j: int in local.size():
			if local[j].y > top - 0.012:   # the upper edge's vertices (the hinge line)
				edge_drift = maxf(edge_drift, p0[j].distance_to(p1[j]))
			tip_swing = maxf(tip_swing, p0[j].distance_to(p1[j]))
	r["hinge_edge_drift_m"] = edge_drift
	r["origin_to_upper_edge_m"] = origin_off
	r["tip_swing_m"] = tip_swing
	r["slat_cuts"] = cuts
	r["slat_outside_opening"] = outside
	if edge_drift > 0.012 or origin_off > 0.01 or tip_swing < 0.15:
		r["problems"].append("hinge: edge drift %.4f, origin off %.4f, tip swing %.3f" % [edge_drift, origin_off, tip_swing])
	if not cuts.is_empty() or not outside.is_empty():
		r["problems"].append("%d cuts, %d outside the opening" % [cuts.size(), outside.size()])
	# the marker: on the bar's glass all the way
	var g: Dictionary = _req["vents"][id]["glass"]
	var mk: Dictionary = {}
	for t: float in [0.0, 0.5, 1.0]:
		_drive(id, 0.0, t)
		var pts: PackedVector3Array = _verts(id, _leaf(id, "marker") as MeshInstance3D)
		var lo: Vector3 = Vector3(1e9, 1e9, 1e9)
		var hi: Vector3 = -lo
		for p: Vector3 in pts:
			lo = lo.min(p)
			hi = hi.max(p)
		mk[str(t)] = [lo.x, hi.x, lo.y, hi.y, lo.z, hi.z]
		if lo.x < g["u0"] - 0.001 or hi.x > g["u1"] + 0.001 or lo.y < g["h0"] - 0.001 or hi.y > g["h1"] + 0.001:
			r["problems"].append("marker off its bar at t %.1f: %s" % [t, str(mk[str(t)])])
	r["marker_bounds"] = mk
	_drive(id, 0.0, 0.0)
	return r


# --- pictures -----------------------------------------------------------------------------------------------------
func _look(eye: Vector3, at: Vector3, fov: float = 40.0) -> void:
	_cam.fov = fov
	_cam.position = eye
	_cam.look_at(at, Vector3.UP)


func _grab(frames: int = 2) -> Image:
	for i: int in frames:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	return img


func _tile(img: Image, w: int, h: int) -> Image:
	var src: Image = img.duplicate()
	var aspect: float = float(w) / h
	var cw: int = mini(src.get_width(), int(src.get_height() * aspect))
	var ch: int = int(cw / aspect)
	src = src.get_region(Rect2i((src.get_width() - cw) / 2, (src.get_height() - ch) / 2, cw, ch))
	src.resize(w, h, Image.INTERPOLATE_LANCZOS)
	return src


func _sheet(tiles: Array, cols: int, w: int, h: int, path: String) -> void:
	var rows: int = ceili(float(tiles.size()) / cols)
	var sheet: Image = Image.create(cols * w, rows * h, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.05, 0.05, 0.06))
	for i: int in tiles.size():
		sheet.blit_rect(tiles[i], Rect2i(0, 0, w, h), Vector2i((i % cols) * w, (i / cols) * h))
	sheet.save_png(path)


func _run() -> void:
	_stage()
	await process_frame
	await process_frame
	var result: Dictionary = {"vents": {}}
	var ok: bool = true
	for id: String in _vents:
		result["vents"][id] = _check(id)
		ok = ok and (result["vents"][id]["problems"] as Array).is_empty()
		print("VENT check %s: %s" % [id, JSON.stringify(result["vents"][id]["problems"])])
	var id0: String = _req["ids"][0]
	var fl: float = float(_req["wall"]["floor"])
	var c: Vector3 = (_vents[id0] as Node3D).position + Vector3(0.0, fl + 1.04, 0.25)   # the east vent's middle
	for id: String in _vents:   # the pictures show the east vent alone
		(_vents[id] as Node3D).visible = id == id0
	# the motion video (the east vent): shut 1 s, open 2 s, breathing 3.5 s, slam 0.3 s, shut; the marker up, down
	var fps: int = int(_req["fps"])
	var secs: float = float(_req["seconds"])
	_label.text = ""
	_look(c + Vector3(1.9, 0.3, 3.3), c + Vector3(-0.05, 0.0, 0.0), 42.0)
	for i: int in int(secs * fps):
		var s: float = float(i) / fps
		var t: float = 0.0
		if s < 1.0:
			t = 0.0
		elif s < 3.0:
			t = smoothstep(0.0, 1.0, (s - 1.0) / 2.0)
		elif s < 7.0:
			t = 1.0 - 0.09 * (1.0 - cos((s - 3.0) * TAU / 1.6)) * minf(1.0, (s - 3.0) / 0.6)
		elif s < 7.3:
			var a: float = (s - 7.0) / 0.3
			t = (1.0 - 0.09 * (1.0 - cos(4.0 * TAU / 1.6))) * (1.0 - a * a)
		var m: float = 0.0
		if s >= 1.0 and s < 5.0:
			m = smoothstep(0.0, 1.0, (s - 1.0) / 4.0)
		elif s >= 5.0 and s < 9.0:
			m = 1.0 - smoothstep(0.0, 1.0, (s - 5.0) / 4.0)
		_drive(id0, t, m)
		var img: Image = await _grab(1)
		img.save_png(_out.path_join("frames/%05d.png" % i))
	result["frames"] = int(secs * fps)
	# the states sheet: shut, half, open, marker low, marker high, open from the side
	var states: Array = []
	for st: Array in [["shut", 0.0, 0.0, false], ["half open", 0.5, 0.0, false], ["fully open", 1.0, 0.0, false],
			["marker low (t 0)", 0.0, 0.0, true], ["marker high (t 1)", 0.0, 1.0, true], ["open, from the side", 1.0, 0.0, false]]:
		_drive(id0, st[1], st[2])
		_label.text = st[0]
		if st[3]:   # the column close
			var b: Vector3 = (_vents[id0] as Node3D).position + Vector3(0.55, fl + 1.62, 0.45)
			_look(b + Vector3(0.45, 0.05, 1.3), b + Vector3(0.0, -0.02, 0.0), 40.0)
		elif st[0].begins_with("open, from"):
			_look(c + Vector3(4.2, 0.2, 0.6), c + Vector3(0.0, 0.0, 0.25), 32.0)
		else:
			_look(c + Vector3(1.2, 0.25, 4.0), c, 40.0)
		states.append(_tile(await _grab(3), 426, 360))
	_sheet(states, 3, 426, 360, _out.path_join("states_sheet.png"))
	_drive(id0, 0.0, 0.0)
	# the vent alone from 8 sides (no backdrop), both vents' leaves shut
	(root.find_child("Backdrop", true, false) as Node3D).visible = false
	var sides: Array = []
	for i: int in 8:
		var a: float = deg_to_rad(45.0 * i)
		_label.text = "%d deg" % (45 * i)
		_look(c + Vector3(sin(a) * 4.6, 0.4, cos(a) * 4.6), c, 40.0)
		var img: Image = await _grab(3)
		img.save_png(_out.path_join("side_%03d.png" % (45 * i)))
		sides.append(_tile(img, 320, 320))
	_sheet(sides, 4, 320, 320, _out.path_join("sides_sheet.png"))
	(root.find_child("Backdrop", true, false) as Node3D).visible = true
	# close-ups (on the wall replica): [name, eye offset, look offset] from the vent's origin
	var closes: Array = []
	var o0: Vector3 = (_vents[id0] as Node3D).position
	for cu: Array in _req["closeups"]:
		_label.text = cu[0]
		_look(o0 + _v(cu[1]), o0 + _v(cu[2]), 30.0)
		var img: Image = await _grab(3)
		img.save_png(_out.path_join("close_%s.png" % cu[0]))
		closes.append(_tile(img, 426, 240))
	_sheet(closes, 3, 426, 240, _out.path_join("closeups_sheet.png"))
	result["ok"] = ok
	var f: FileAccess = FileAccess.open(_out.path_join("motion.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(result, " "))
	f.close()
	print("VENT done ok=%s frames=%d" % [str(ok), result["frames"]])
	quit(0 if ok else 2)
