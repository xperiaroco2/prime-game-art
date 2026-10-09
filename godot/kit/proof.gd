extends SceneTree
## The House kit's proof for `tools/run.py kit --proof DIR` (docs/kit.md): a test room (6 x 4 m, a door and a window),
## a 2 m corridor and a stair flight to a second-floor landing; v2 (art #86) adds the line-up by kind, the porch on a
## wall, the attic roof over a 4 m span and the gazebo with rays up through their roofs; assembled from the imported
## kit pieces with the `set` pack's shader (kit_materials.gd), lit with the
## house lab's round-3 settings (r3_v1 knobs: dusk sky, fog, sun, warm lamps c2, filmic exposure 1.5, saturation 1.35,
## SSAO; SDFGI stands in for the lab's baked LightmapGI), walked by capsules and shot at eye height 1.6 m.
## Pictures need a real window placed off-screen (the runner passes --position -30000,-30000), never headless:
##   godot --path godot --position -30000,-30000 --resolution 1600x900 -s res://kit/proof.gd -- <request.json> <out dir>
## request.json: {"pieces": {"<id>": {"scene": "res://import/kit_<id>.glb", "min": [x, y, z], "max": [x, y, z]}},
##   "groups": [[title, [ids], view pitch deg]], "attic": [[id, deg, [x, y, z]]], "gazebo": [...], "man": "<glb>",
##   "pack": {"textures": dir, "roughness": [3], "normal_strength": [3]}, "version": n, "pitch": rise per m}.
## Writes <out>/<shot>.png, lineup_<n>.png, <out>/sheet.png (1280 px wide, rows of three) and <out>/proof.json (the
## walks and the rays); prints PROOF saved <dir>.

const WATCHDOG_S: float = 280.0
const EYE: float = 1.6
const UP := Vector3.UP
const LAMP := Color(1.0, 0.85, 0.68)
const SHEET_W: int = 1280
const GAP: int = 4
const LINEUP_Z: float = 40.0
const LINEUP_X: float = 200.0
const LINEUP_STEP: float = 150.0
const LINEUP_LAYER: int = 2
const ROW_W: float = 32.0
const LABEL_CHAR_M: float = 0.13
const LABEL_ROW_M: float = 1.3
const PORCH := Vector3(-30, 0, 20)
const ATTIC := Vector3(-50, 0, 20)
const GAZEBO := Vector3(-75, 0, 22)
const KitMaterials := preload("res://kit/kit_materials.gd")

var _req: Dictionary
var _request: Dictionary
var _groups: Array
var _set: Material
var _out: String
var _house: Node3D
var _camera: Camera3D
var _label: Label
var _env: Environment


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 2:
		_fail("usage: -- <request.json> <out dir>")
		return
	if DisplayServer.get_name() == "headless":
		_fail("needs a window (off-screen), not --headless")
		return
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	_run(args)


func _run(args: PackedStringArray) -> void:
	var request: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if typeof(request) != TYPE_DICTIONARY:
		_fail("cannot read %s" % args[0])
		return
	_request = request
	_req = request["pieces"]
	_groups = request.get("groups", [["every piece", _req.keys(), 30.0]])
	var pack: Dictionary = request.get("pack", {})
	if not pack.is_empty():
		_set = KitMaterials.make(pack["textures"], pack)
	_out = args[1]
	DirAccess.make_dir_recursive_absolute(_out)
	_house = Node3D.new()
	root.add_child(_house)
	_environment()
	_build_house()
	_build_assemblies()
	var lineup_groups: Array = _build_lineup()
	_camera = Camera3D.new()
	_camera.fov = 70.0
	_camera.near = 0.05
	root.add_child(_camera)
	_camera.make_current()
	var layer: CanvasLayer = CanvasLayer.new()
	_label = Label.new()
	_label.position = Vector2(16, 10)
	_label.add_theme_font_size_override("font_size", 48)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 8)
	layer.add_child(_label)
	root.add_child(layer)
	for i: int in 3:
		await physics_frame
	var result: Dictionary = {"walks": {}}
	# The package carrier: a capsule 0.8 m wide through the 1.4 m door, the corridor and up the flight to the landing.
	result["walks"]["package_0.8m"] = await _walk(0.4, [Vector3(3, 0.05, 1.5), Vector3(3, 0, 4), Vector3(3, 0, 5),
		Vector3(6.3, 0, 5), Vector3(12.6, 3.2, 5), Vector3(15.0, 3.2, 5)], true)
	# The control: a capsule 1.5 m wide must stop at the door (the colliders block).
	result["walks"]["control_1.5m"] = await _walk(0.75, [Vector3(3, 0.05, 1.5), Vector3(3, 0, 5)], false)
	var shots: Array = [
		["room_corner", "test room 6 x 4 m, from the SW corner", Vector3(0.6, EYE, 0.6), Vector3(5.6, 1.3, 3.8)],
		["room_window", "test room, the window wall", Vector3(5.4, EYE, 3.5), Vector3(0.6, 1.2, 0.2)],
		["room_door", "through the 1.4 m door from the corridor", Vector3(3.0, EYE, 5.5), Vector3(3.0, 1.3, 0.5)],
		["corridor", "corridor 2 m, towards the stairs", Vector3(0.6, EYE, 5.0), Vector3(12.0, 2.4, 5.0)],
		["stairs_up", "stairs_main, up to the 3.2 m landing", Vector3(4.6, EYE, 5.0), Vector3(12.0, 3.9, 5.0)],
		["stairs_down", "from the landing, down the flight", Vector3(15.4, 3.2 + EYE, 5.0), Vector3(6.0, 0.6, 5.0)],
	]
	# The roofs close: rays straight up from inside the attic (over the knee walls' top) and the gazebo's deck.
	result["rays"] = {
		"attic": _rays_up(ATTIC, 0.11, 0.11, 3.89, 3.89, 0.0, 1.0, 1.8),
		"gazebo": _rays_up(GAZEBO, -2.5, -2.5, 2.5, 2.5, 2.3, 1.0, 2.4),
	}
	var views: Array[Image] = []
	for s: Array in shots:
		views.append(await _shot(s[0], s[1], s[2], s[3]))
	result["shots"] = shots.map(func(s: Array) -> String: return s[0])
	var a: Vector3 = ATTIC
	var assemblies: Array[Image] = []
	assemblies.append(await _view("porch", "porch_2x2 on a 6 m exterior wall", PORCH + Vector3(7.5, 2.2, 7.0),
		PORCH + Vector3(2.5, 1.5, 0.5)))
	assemblies.append(await _view("attic_out", "attic roof over 4 x 4 m (knee 2.2 m, %s)" % _pitch_note(),
		a + Vector3(-4.5, 5.5, -5.0), a + Vector3(2, 2.6, 2)))
	assemblies.append(await _view("attic_in", "inside the attic: the roof's underside and a gable", a + Vector3(3.6, 1.6, 0.6),
		a + Vector3(0.2, 2.9, 2.4)))
	assemblies.append(await _view("gazebo", "gazebo: 6 deck sectors (1 open), 6 roof sectors, finial",
		GAZEBO + Vector3(5.5, 2.6, 6.5), GAZEBO + Vector3(0, 1.4, 0)))
	_lineup_mode()
	var tiles: Array[Image] = []
	for i: int in lineup_groups.size():
		tiles.append(await _lineup_shot(i, lineup_groups[i]))
	_camera.cull_mask = 1 | (1 << (LINEUP_LAYER - 1))
	tiles.append_array(assemblies)
	tiles.append_array([views[0], views[3], views[4]])
	_save(_sheet(tiles), _out.path_join("sheet.png"))
	var f: FileAccess = FileAccess.open(_out.path_join("proof.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(result, " "))
	f.close()
	print("PROOF saved %s" % _out)
	quit(0)


# --- the scene -----------------------------------------------------------------------------------------------------
func _environment() -> void:
	var sky_mat: ProceduralSkyMaterial = ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.13, 0.14, 0.36)
	sky_mat.sky_horizon_color = Color(0.95, 0.52, 0.3)
	sky_mat.ground_horizon_color = Color(0.3, 0.2, 0.18)
	sky_mat.ground_bottom_color = Color(0.05, 0.05, 0.07)
	var sky: Sky = Sky.new()
	sky.sky_material = sky_mat
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 1.5
	env.tonemap_white = 4.0
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.35
	env.adjustment_contrast = 1.0
	env.glow_enabled = true
	env.glow_hdr_threshold = 0.9
	env.glow_intensity = 0.5
	env.ssao_enabled = true
	env.ssao_intensity = 1.0
	env.ssao_radius = 0.8
	env.sdfgi_enabled = true
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_light_color = Color(0.3, 0.27, 0.4)
	env.fog_light_energy = 0.8
	env.fog_depth_begin = 30.0
	env.fog_depth_end = 140.0
	_env = env
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.light_color = Color(0.55, 0.65, 1.0)
	sun.light_energy = 0.35
	sun.rotation_degrees = Vector3(-14.0, 200.0, 0.0)
	sun.shadow_enabled = true
	root.add_child(sun)
	var ground: MeshInstance3D = MeshInstance3D.new()
	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(200, 200)
	ground.mesh = plane
	var earth: StandardMaterial3D = StandardMaterial3D.new()
	earth.albedo_color = Color(0.16, 0.13, 0.11)
	earth.roughness = 1.0
	ground.material_override = earth
	ground.position = Vector3(0, -0.21, 0)
	root.add_child(ground)


func _build_house() -> void:
	var y2: float = 3.2
	# Ground floor: the room (x 0..6, z 0..4), the corridor (z 4..6), the stairwell (x 6..16, z 4..6).
	_tiles("floor_boards_2x2", 0, 6, 0, 4, 0.0)
	_tiles("floor_lino_2x2", 0, 6, 4, 6, 0.0)
	_tiles("floor_concrete_2x2", 6, 16, 4, 6, 0.0)
	_tiles("ceiling_2x2", 0, 6, 0, 6, 3.0)
	_tiles("ceiling_2x2", 12, 16, 4, 6, 3.0)
	_tiles("floor_boards_2x2", 12, 16, 4, 6, y2)
	_tiles("ceiling_2x2", 6, 16, 4, 6, y2 + 3.0)
	_line(["wall_storey_2m_ext", "wall_storey_2m_window_ext", "wall_storey_2m_ext"], Vector3(0, 0, 0), Vector3(6, 0, 0), Vector3.FORWARD)
	_line(["wall_storey_2m_ext", "wall_storey_2m_ext", "wall_storey_2m_ext"], Vector3(0, 0, 0), Vector3(0, 0, 6), Vector3.LEFT)
	_line(["wall_storey_2m_ext", "wall_storey_2m_window_ext"], Vector3(6, 0, 0), Vector3(6, 0, 4), Vector3.RIGHT)
	_line(["wall_storey_2m_int", "wall_storey_2m_door_int", "wall_storey_2m_int"], Vector3(0, 0, 4), Vector3(6, 0, 4), Vector3.BACK)
	_line(_n("wall_storey_2m_ext", 8), Vector3(0, 0, 6), Vector3(16, 0, 6), Vector3.BACK)
	_line(_n("wall_storey_2m_ext", 5), Vector3(6, 0, 4), Vector3(16, 0, 4), Vector3.FORWARD)
	_line(["wall_storey_2m_ext"], Vector3(16, 0, 4), Vector3(16, 0, 6), Vector3.RIGHT)
	for c: Array in [[0, 0, 180.0], [6, 0, 90.0], [0, 6, -90.0], [16, 6, 0.0], [16, 4, 90.0]]:
		_put("wall_storey_corner_ext", Vector3(c[0], 0, c[1]), c[2])
	# Upper storey round the stairwell and the landing.
	_line(_n("wall_storey_2m_ext", 5), Vector3(6, y2, 6), Vector3(16, y2, 6), Vector3.BACK)
	_line(_n("wall_storey_2m_ext", 5), Vector3(6, y2, 4), Vector3(16, y2, 4), Vector3.FORWARD)
	_line(["wall_storey_2m_ext"], Vector3(16, y2, 4), Vector3(16, y2, 6), Vector3.RIGHT)
	_line(["wall_storey_2m_ext"], Vector3(6, y2, 4), Vector3(6, y2, 6), Vector3.LEFT)
	for c: Array in [[16, 6, 0.0], [16, 4, 90.0], [6, 4, 180.0], [6, 6, -90.0]]:
		_put("wall_storey_corner_ext", Vector3(c[0], y2, c[1]), c[2])
	_put("stairs_main", Vector3(6, 0, 4), 0.0)
	for at: Vector3 in [Vector3(3, 2.7, 2), Vector3(3, 2.7, 5), Vector3(9, 4.6, 5), Vector3(14, 5.8, 5)]:
		var lamp: OmniLight3D = OmniLight3D.new()
		lamp.light_color = LAMP
		lamp.light_energy = 3.0
		lamp.omni_range = 6.0
		lamp.light_size = 0.06
		lamp.shadow_enabled = true
		lamp.position = at
		_house.add_child(lamp)


func _n(id: String, count: int) -> Array:
	var out: Array = []
	for i: int in count:
		out.append(id)
	return out


## Pieces along the grid line a..b with their exterior side towards `ext`: a wall runs along its local +X with its
## exterior at local +Z, so the run goes along UP x ext from whichever end that direction starts.
func _line(ids: Array, a: Vector3, b: Vector3, ext: Vector3) -> void:
	var d: Vector3 = UP.cross(ext)
	var start: Vector3 = a if (b - a).dot(d) > 0 else b
	var basis: Basis = Basis(d, UP, ext)
	var x: float = 0.0
	for id: String in ids:
		var n: Node3D = _instance(id)
		n.transform = Transform3D(basis, start + d * x)
		_house.add_child(n)
		x += _width(id)


func _tiles(id: String, x0: float, x1: float, z0: float, z1: float, y: float) -> void:
	var w: float = _width(id)
	var x: float = x0
	while x < x1 - 0.01:
		var z: float = z0
		while z < z1 - 0.01:
			_put(id, Vector3(x, y, z), 0.0)
			z += w
		x += w


func _put(id: String, at: Vector3, turn_deg: float) -> Node3D:
	var n: Node3D = _instance(id)
	n.position = at
	n.rotation_degrees.y = turn_deg
	_house.add_child(n)
	return n


func _instance(id: String) -> Node3D:
	if not _req.has(id):
		_fail("no piece %s in the request" % id)
	var n: Node3D = (load(_req[id]["scene"]) as PackedScene).instantiate() as Node3D
	if _set != null:
		KitMaterials.apply(n, _set)
	return n


func _pitch_note() -> String:
	return "pitch %.2f per m" % float(_request.get("pitch", 0.7))


func _width(id: String) -> float:
	return roundf(float(_req[id]["max"][0]) - float(_req[id]["min"][0]))


## The line-up (art #86): every piece, grouped by kind (the request's "groups": title, piece ids, view pitch in degrees:
## 8 front, 90 top), each group row-packed at its own spot east of the house with its id under it, a 5 m bar of 1 m
## blocks and the clay man (or a 1.8 m capsule) at its left; render layer 2 only, under its own neutral key light.
## Returns, per group, [title, box, pitch].
func _build_lineup() -> Array:
	var groups: Array = []
	var lineup: Node3D = Node3D.new()
	root.add_child(lineup)
	for gi: int in _groups.size():
		var g: Array = _groups[gi]
		var top: bool = float(g[2]) > 45.0  # rows go back in z (seen from above) or up in y (seen from the front)
		var origin: Vector3 = Vector3(LINEUP_X + LINEUP_STEP * gi, 0, LINEUP_Z)
		# Rows: a width that makes the group about as wide as the frame's aspect, each slot as wide as its piece or id.
		var total: float = 0.0
		var tallest: float = 0.0
		for id: String in g[1]:
			var size: Vector3 = _v(_req[id]["max"]) - _v(_req[id]["min"])
			total += maxf(size.x, _label_w(id)) + 0.5
			tallest = maxf(tallest, size.z if top else size.y)
		var row_w: float = clampf(sqrt(1.78 * total * (tallest + LABEL_ROW_M)), 8.0, 40.0)
		var rows: Array = [[]]
		var x: float = 0.0
		for id: String in g[1]:
			var size: Vector3 = _v(_req[id]["max"]) - _v(_req[id]["min"])
			var slot: float = maxf(size.x, _label_w(id))
			if x > 0.0 and x + slot > row_w:
				rows.append([])
				x = 0.0
			rows[-1].append([id, x, slot])
			x += slot + 0.5
		var box: AABB = AABB(origin, Vector3.ZERO)
		var cursor: float = 0.0
		var first_base: float = 0.0
		for ri: int in rows.size():
			var row_h: float = 0.0
			for e: Array in rows[ri]:
				var size: Vector3 = _v(_req[e[0]]["max"]) - _v(_req[e[0]]["min"])
				row_h = maxf(row_h, size.z if top else size.y)
			var base: float = cursor if top else cursor - row_h  # top: the row's back edge z; front: its floor y
			if ri == 0:
				first_base = base + row_h if top else base
			for e: Array in rows[ri]:
				var id: String = e[0]
				var lo: Vector3 = _v(_req[id]["min"])
				var hi: Vector3 = _v(_req[id]["max"])
				var size: Vector3 = hi - lo
				var cx: float = float(e[1]) + float(e[2]) * 0.5
				var n: Node3D = _instance(id)
				if top:  # the row's back edge at z = base, its pieces' front towards +z
					n.position = origin + Vector3(cx - (lo.x + hi.x) * 0.5, -lo.y, base + row_h - hi.z)
				else:
					n.position = origin + Vector3(cx - (lo.x + hi.x) * 0.5, base - lo.y, -hi.z)
				lineup.add_child(n)
				box = box.merge(AABB(n.position + lo, size))
				var label: Label3D = _label3d(_label_text(id))
				label.position = origin + (Vector3(cx, hi.y - lo.y + 0.05, base + row_h + 0.5) if top
					else Vector3(cx, base - 0.45, 0.3))
				lineup.add_child(label)
				box = box.merge(AABB(label.position - Vector3(float(e[2]) * 0.5, 0.45, 0.4), Vector3(float(e[2]), 0.9, 0.8)))
			cursor = base + row_h + LABEL_ROW_M if top else base - LABEL_ROW_M
		# The man and the 5 m bar left of the first row.
		var man: Node3D = _man()
		man.position = origin + (Vector3(-1.2, 0, first_base - 0.4) if top else Vector3(-1.2, first_base, -0.3))
		lineup.add_child(man)
		box = box.merge(AABB(man.position + Vector3(-0.9, 0, -0.4), Vector3(1.8, 1.8, 0.8)))
		for i: int in 5:
			var bar: MeshInstance3D = MeshInstance3D.new()
			var cube: BoxMesh = BoxMesh.new()
			cube.size = Vector3(1.0, 0.08, 0.15)
			bar.mesh = cube
			var m: StandardMaterial3D = StandardMaterial3D.new()
			m.albedo_color = Color(0.9, 0.9, 0.9) if i % 2 == 0 else Color(0.05, 0.05, 0.05)
			bar.material_override = m
			bar.position = origin + (Vector3(-6.7 + i, 0.04, first_base + 0.6) if top
				else Vector3(-6.7 + i, first_base - 0.6, 0.0))
			lineup.add_child(bar)
			box = box.merge(AABB(bar.position - Vector3(0.5, 0.05, 0.1), Vector3(1.0, 0.1, 0.2)))
		groups.append([g[0], box, float(g[2])])
	for g: Node in lineup.find_children("*", "VisualInstance3D", true, false):
		(g as VisualInstance3D).layers = 1 << (LINEUP_LAYER - 1)
	# A key from the camera side and a fill from the other; the line-up's ambient is neutral (_lineup_mode).
	for k: Array in [[Vector3(-50.0, 30.0, 0.0), 3.0], [Vector3(-25.0, -40.0, 0.0), 1.2]]:
		var key: DirectionalLight3D = DirectionalLight3D.new()
		key.light_cull_mask = 1 << (LINEUP_LAYER - 1)
		key.light_energy = k[1]
		key.rotation_degrees = k[0]  # towards -Z: lights the faces the camera (at +Z) sees
		key.shadow_enabled = false  # the house must not shade the line-up
		root.add_child(key)
	return groups


## A piece id in two lines, split at the underscore nearest its middle (the longer line first).
func _label_text(id: String) -> String:
	var best: int = -1
	for i: int in id.length():
		if id[i] == "_" and (best < 0 or absi(i - id.length() / 2) < absi(best - id.length() / 2)):
			best = i
	if best < 0 or id.length() < 14:
		return id
	var a: String = id.substr(0, best)
	var b: String = id.substr(best)
	return a + "\n" + b


func _label_w(id: String) -> float:
	var w: int = 0
	for line: String in _label_text(id).split("\n"):
		w = maxi(w, line.length())
	return LABEL_CHAR_M * w


func _label3d(text: String) -> Label3D:
	var label: Label3D = Label3D.new()
	label.text = text
	label.font_size = 48
	label.pixel_size = LABEL_CHAR_M / 26.0
	label.outline_size = 10
	label.modulate = Color(0.02, 0.02, 0.02)
	label.outline_modulate = Color(1, 1, 1)
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	return label


## The clay man of the look (the request's "man" GLB, loaded at run time) or, without one, a 1.8 m capsule.
func _man() -> Node3D:
	var path: String = str(_request.get("man", ""))
	if path != "" and FileAccess.file_exists(path):
		var doc: GLTFDocument = GLTFDocument.new()
		var state: GLTFState = GLTFState.new()
		if doc.append_from_file(path, state) == OK:
			var scene: Node = doc.generate_scene(state)
			if scene is Node3D:
				return scene as Node3D
	var mi: MeshInstance3D = MeshInstance3D.new()
	var cap: CapsuleMesh = CapsuleMesh.new()
	cap.radius = 0.25
	cap.height = 1.8
	mi.mesh = cap
	mi.position.y = 0.9
	var holder: Node3D = Node3D.new()
	holder.add_child(mi)
	return holder


# --- the assemblies (art #86): the porch on a wall, the attic roof over a 4 m span, the gazebo ----------------------
func _build_assemblies() -> void:
	# The porch against a 6 m exterior wall (exterior +Z), the man under it.
	_tiles_at("floor_concrete_2x2", PORCH, 0, 6, 0, 4, 0.0)
	_line_at(PORCH, ["wall_storey_2m_ext", "wall_storey_2m_window_ext", "wall_storey_2m_ext"], Vector3(0, 0, 0),
		Vector3(6, 0, 0), Vector3.BACK)
	_put("porch_2x2", PORCH + Vector3(2, 0, 0), 0.0)
	_add_man(PORCH + Vector3(3.3, 0, 1.3))
	# The attic: knee walls 2.2 m round a 4 x 4 m floor, the gables on the x walls, the pitched roof from attic_roof().
	var k: float = 2.2
	_tiles_at("floor_boards_2x2", ATTIC, 0, 4, 0, 4, 0.0)
	_line_at(ATTIC, ["wall_knee_2m_ext", "wall_knee_2m_window_ext"], Vector3(0, 0, 0), Vector3(4, 0, 0), Vector3.FORWARD)
	_line_at(ATTIC, ["wall_knee_2m_ext", "wall_knee_2m_ext"], Vector3(0, 0, 4), Vector3(4, 0, 4), Vector3.BACK)
	_line_at(ATTIC, ["wall_knee_2m_ext", "wall_knee_2m_ext"], Vector3(0, 0, 0), Vector3(0, 0, 4), Vector3.LEFT)
	_line_at(ATTIC, ["wall_knee_2m_ext", "wall_knee_2m_ext"], Vector3(4, 0, 0), Vector3(4, 0, 4), Vector3.RIGHT)
	_line_at(ATTIC, ["gable_tri_2m_up", "gable_tri_2m_down"], Vector3(0, k, 0), Vector3(0, k, 4), Vector3.LEFT)
	_line_at(ATTIC, ["gable_tri_2m_up", "gable_tri_2m_down"], Vector3(4, k, 0), Vector3(4, k, 4), Vector3.RIGHT)
	for c: Array in [[0, 0, 180.0], [4, 0, 90.0], [0, 4, -90.0], [4, 4, 0.0]]:
		_put("wall_knee_corner_ext", ATTIC + Vector3(c[0], 0, c[1]), c[2])
	for p: Array in _request.get("attic", []):
		_put(p[0], ATTIC + Vector3(0, k, 0) + _v(p[2]), float(p[1]))
	_add_man(ATTIC + Vector3(2.0, 0, 1.6))
	# The gazebo from gazebo(), the man inside.
	for p: Array in _request.get("gazebo", []):
		_put(p[0], GAZEBO + _v(p[2]), float(p[1]))
	_add_man(GAZEBO + Vector3(0.6, 0.15, 0.4))
	for at: Vector3 in [ATTIC + Vector3(2, 2.6, 2), GAZEBO + Vector3(0, 2.3, 0), PORCH + Vector3(3, 2.3, 1)]:
		var lamp: OmniLight3D = OmniLight3D.new()
		lamp.light_color = LAMP
		lamp.light_energy = 2.0
		lamp.omni_range = 5.0
		lamp.position = at
		_house.add_child(lamp)


func _add_man(at: Vector3) -> void:
	var man: Node3D = _man()
	man.position = at
	_house.add_child(man)


func _line_at(origin: Vector3, ids: Array, a: Vector3, b: Vector3, ext: Vector3) -> void:
	_line(ids, origin + a, origin + b, ext)


func _tiles_at(id: String, origin: Vector3, x0: float, x1: float, z0: float, z1: float, y: float) -> void:
	_tiles(id, origin.x + x0, origin.x + x1, origin.z + z0, origin.z + z1, origin.y + y)


## Rays straight up from a grid of points (step 0.25 m) over x0..x1, z0..z1 round origin (only those within r of it
## when r > 0) must hit a collider above origin.y + min_y. Returns the count and the misses.
func _rays_up(origin: Vector3, x0: float, z0: float, x1: float, z1: float, r: float, from_y: float,
		min_y: float) -> Dictionary:
	var space: PhysicsDirectSpaceState3D = _house.get_world_3d().direct_space_state
	var count: int = 0
	var misses: Array = []
	var x: float = x0
	while x <= x1 + 1e-6:
		var z: float = z0
		while z <= z1 + 1e-6:
			if r <= 0.0 or Vector2(x, z).length() <= r:
				count += 1
				var a: Vector3 = origin + Vector3(x, from_y, z)
				var q: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(a, a + Vector3(0, 20, 0))
				var hit: Dictionary = space.intersect_ray(q)
				if hit.is_empty() or (hit["position"] as Vector3).y < origin.y + min_y:
					misses.append([snappedf(x, 0.01), snappedf(z, 0.01)])
			z += 0.25
		x += 0.25
	return {"rays": count, "misses": misses.slice(0, 8), "missed": misses.size(), "pass": misses.is_empty()}


# --- the walk check ------------------------------------------------------------------------------------------------
## A capsule (radius r, 1.8 m) walks the waypoints at 3 m/s; passes when it reaches the last within 0.3 m (and its
## height within 0.15 m), or, for a control (`must_pass` false), when it does not.
func _walk(r: float, points: Array, must_pass: bool) -> Dictionary:
	var body: CharacterBody3D = CharacterBody3D.new()
	var shape: CollisionShape3D = CollisionShape3D.new()
	var cap: CapsuleShape3D = CapsuleShape3D.new()
	cap.radius = r
	cap.height = 1.8
	shape.shape = cap
	shape.position.y = 0.9
	body.add_child(shape)
	body.floor_snap_length = 0.3
	root.add_child(body)
	body.global_position = points[0]
	var reached: int = 0
	var dt: float = 1.0 / Engine.physics_ticks_per_second
	var steps: int = 0
	var max_y: float = 0.0
	while steps < 12 * Engine.physics_ticks_per_second and reached < points.size() - 1:
		await physics_frame
		steps += 1
		var target: Vector3 = points[reached + 1]
		var flat: Vector3 = Vector3(target.x - body.global_position.x, 0, target.z - body.global_position.z)
		if flat.length() < 0.3:
			reached += 1
			continue
		var v: Vector3 = flat.normalized() * 3.0
		v.y = 0.0 if body.is_on_floor() else body.velocity.y - 9.8 * dt
		body.velocity = v
		body.move_and_slide()
		max_y = maxf(max_y, body.global_position.y)
	var end: Vector3 = body.global_position
	var arrived: bool = reached == points.size() - 1 and absf(end.y - (points[-1] as Vector3).y) < 0.15
	body.queue_free()
	return {"radius_m": r, "waypoints": points.size(), "reached": reached + 1, "end": [end.x, end.y, end.z],
		"max_y": max_y, "seconds": steps * dt, "arrived": arrived, "pass": arrived == must_pass}


# --- pictures ------------------------------------------------------------------------------------------------------
func _shot(name: String, title: String, from: Vector3, to: Vector3) -> Image:
	_camera.fov = 70.0
	_camera.cull_mask = 1
	_camera.look_at_from_position(from, to, UP)
	_label.text = "%s   (eye %.1f m)" % [title, from.y - (3.2 if from.y > 3.2 + 0.5 else 0.0)]
	var image: Image = await _grab()
	_save(image, _out.path_join("%s.png" % name))
	return image


func _lineup_mode() -> void:
	_camera.cull_mask = 1 << (LINEUP_LAYER - 1)
	_env.fog_enabled = false  # the line-up camera stands past the fog's 30 m start: no purple haze
	_env.background_mode = Environment.BG_COLOR
	_env.background_color = Color(0.55, 0.56, 0.58)
	_env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR  # neutral: no dusk horizon tinting the paints
	_env.ambient_light_color = Color(0.5, 0.5, 0.52)
	_env.ambient_light_energy = 1.0
	_env.ssao_enabled = false  # screen-space AO does not suit the orthographic line-up
	_env.sdfgi_enabled = false


## One line-up group, orthographic, from the front (+Z, raised by its pitch) or from above (pitch 90).
func _lineup_shot(index: int, group: Array) -> Image:
	var box: AABB = group[1]
	var pitch: float = deg_to_rad(group[2])
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	var aspect: float = float(root.size.x) / float(root.size.y)
	var tall: float = box.size.y * cos(pitch) + box.size.z * sin(pitch)
	_camera.size = maxf(tall, box.size.x / aspect) * 1.08 + 1.2
	_camera.near = 0.05
	_camera.far = 400.0
	var c: Vector3 = box.get_center()
	var dir: Vector3 = Vector3(0, sin(pitch), cos(pitch))
	_camera.look_at_from_position(c + dir * 100.0, c, Vector3.FORWARD if group[2] > 89.0 else UP)
	_label.text = "House kit v%d: %s (%s; bar 5 x 1 m)" % [_request.get("version", 2), group[0],
		"from above" if group[2] > 60.0 else "front, %d deg up" % int(group[2])]
	var image: Image = await _grab()
	_save(image, _out.path_join("lineup_%d.png" % index))
	return image


func _view(name: String, title: String, from: Vector3, to: Vector3) -> Image:
	_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
	_camera.fov = 60.0
	_camera.look_at_from_position(from, to, UP)
	_label.text = title
	var image: Image = await _grab()
	_save(image, _out.path_join("%s.png" % name))
	return image


func _grab() -> Image:
	for i: int in 30:
		await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	return image


## The tiles in rows of three, SHEET_W wide.
func _sheet(tiles: Array[Image]) -> Image:
	var cw: int = (SHEET_W - 2 * GAP) / 3
	var ch: int = int(cw * tiles[0].get_height() / float(tiles[0].get_width()))
	var rows: int = (tiles.size() + 2) / 3
	var sheet: Image = Image.create_empty(SHEET_W, rows * ch + (rows - 1) * GAP, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.97, 0.97, 0.97))
	for i: int in tiles.size():
		var img: Image = tiles[i].duplicate() as Image
		img.resize(cw, ch, Image.INTERPOLATE_LANCZOS)
		sheet.blit_rect(img, Rect2i(Vector2i.ZERO, img.get_size()), Vector2i((i % 3) * (cw + GAP), (i / 3) * (ch + GAP)))
	return sheet


func _v(a: Array) -> Vector3:
	return Vector3(a[0], a[1], a[2])


func _save(image: Image, path: String) -> void:
	var error: Error = image.save_png(path)
	if error != OK:
		_fail("cannot save %s: %s" % [path, error_string(error)])


func _fail(why: String) -> void:
	printerr("PROOF error %s" % why)
	quit(1)
