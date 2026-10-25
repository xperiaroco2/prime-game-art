extends SceneTree
## The crystal socket on a neutral backdrop at the picked sheet's three-quarter angle (art#263's stations, socket-2),
## in an off-screen window (the runner's _godot.window(); tools/blender/socket_run.py calls it after hall.gd's shots,
## with the socket and the crystal staged in res://import/). A dark blue wall and floor, a soft sky for the metal to
## mirror, a warm key from the upper left and a cool fill, AgX and glow: the sheet's studio, not the game's hall.
## Writes into OUT:
## - studio.png: the socket (socket.gd's look, the charged crystal seated);
## - compare_sheet.png: the sheet's hero view (its left panel) beside studio.png at the same height;
## - studio_open.png (socket-3): the claws open and the crystal pulled PULL_CM out;
## - grid.png, when a variants file is given: one render per variant of the look's materials' parameters
##   ([{"title": "...", "bronze": {"metallic": 0.8, ...}, "amber": {"emission_energy_multiplier": 3.0}}, ...]:
##   shader parameters, or a StandardMaterial3D's properties), side by side.
## Args after "--": <OUT dir> <sheet jpg> [<variants json>]

const Offscreen = preload("res://lib/offscreen.gd")
const Socket = preload("res://socket/socket.gd")
const Crystal = preload("res://crystal/crystal.gd")
const SIZE := Vector2i(900, 1000)
const CELL := Vector2i(540, 640)
const YAW := -20.0          # the camera toward the socket's left (-u), as the sheet's hero view
const ELEV := 4.0
const DIST := 1.75
const TARGET := Vector3(0.0, 1.31, 0.10)

var _look: Dictionary
var _crystal: Node3D


func _initialize() -> void:
	var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
	if placed != "":
		printerr(placed)
		quit(2)
		return
	create_timer(150.0).timeout.connect(func() -> void:  # a script error stops _run: quit with its log, not hang
		printerr("SOCKET studio: no result in 150 s")
		quit(3))
	_run.call_deferred()


func _run() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var out: String = a[0]
	_stage()
	if a.size() > 2 and a[2] != "":
		var variants: Array = JSON.parse_string(FileAccess.get_file_as_string(a[2]))
		var cells: Array[Image] = []
		for v: Dictionary in variants:
			var undo: Array = []
			for key: String in v:
				if key == "title" or not _look.has(key):
					continue
				var m: Material = _look[key]
				for p: String in (v[key] as Dictionary):
					var val: Variant = v[key][p]
					val = Color(val[0], val[1], val[2]) if val is Array else val
					if m is ShaderMaterial:
						undo.append([m, p, (m as ShaderMaterial).get_shader_parameter(p)])
						(m as ShaderMaterial).set_shader_parameter(p, val)
					else:
						undo.append([m, p, m.get(p)])
						m.set(p, val)
			cells.append(await _shot(CELL))
			print("SOCKET studio variant %s" % v.get("title", ""))
			undo.reverse()
			for u: Array in undo:
				if u[0] is ShaderMaterial:
					(u[0] as ShaderMaterial).set_shader_parameter(u[1], u[2])
				else:
					(u[0] as Material).set(u[1], u[2])
		var grid := Image.create(CELL.x * cells.size(), CELL.y, false, Image.FORMAT_RGB8)
		for i: int in cells.size():
			grid.blit_rect(cells[i], Rect2i(Vector2i.ZERO, CELL), Vector2i(CELL.x * i, 0))
		grid.save_png(out.path_join("grid.png"))
		print("SOCKET studio wrote %s" % out.path_join("grid.png"))
	var shot: Image = await _shot(SIZE)
	shot.save_png(out.path_join("studio.png"))
	var sheet: Image = Image.load_from_file(a[1])
	sheet.convert(Image.FORMAT_RGB8)
	# the sheet's hero view: its left two thirds (1536 x 1024: the socket and the figure), cut round the socket
	var w: int = sheet.get_width()
	var h: int = sheet.get_height()
	var cut: Image = sheet.get_region(Rect2i(int(w * 0.10), int(h * 0.12), int(w * 0.30), int(h * 0.75)))
	cut.resize(int(cut.get_width() * float(SIZE.y) / cut.get_height()), SIZE.y, Image.INTERPOLATE_LANCZOS)
	var both := Image.create(cut.get_width() + 8 + SIZE.x, SIZE.y, false, Image.FORMAT_RGB8)
	both.fill(Color(0.9, 0.9, 0.9))
	both.blit_rect(cut, Rect2i(Vector2i.ZERO, cut.get_size()), Vector2i.ZERO)
	both.blit_rect(shot, Rect2i(Vector2i.ZERO, SIZE), Vector2i(cut.get_width() + 8, 0))
	both.save_png(out.path_join("compare_sheet.png"))
	print("SOCKET studio wrote %s" % out.path_join("compare_sheet.png"))
	Socket.set_claws(_look, 1.0)
	_crystal.position = Vector3(0.0, 0.0, Socket.PULL_CM * 0.01)
	(await _shot(SIZE)).save_png(out.path_join("studio_open.png"))
	print("SOCKET studio wrote %s" % out.path_join("studio_open.png"))
	quit(0)


func _stage() -> void:
	var env := Environment.new()
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.16, 0.2, 0.3)
	sky_mat.sky_horizon_color = Color(0.36, 0.32, 0.28)
	sky_mat.ground_horizon_color = Color(0.3, 0.27, 0.25)
	sky_mat.ground_bottom_color = Color(0.06, 0.06, 0.08)
	var sky := Sky.new()
	sky.sky_material = sky_mat
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.35
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.glow_enabled = true
	# socket-3: a soft bloom round the strips, windows and bay (the sheet's; softlight at 0.6 left them flat)
	env.glow_intensity = 0.5
	env.glow_strength = 1.0
	env.glow_bloom = 0.0
	env.glow_hdr_threshold = 1.1
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SCREEN
	for i: int in 7:
		env.set_glow_level(i, 1.0 if i in [2, 3, 4, 5] else 0.0)
	env.ssao_enabled = true
	var world := WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var backdrop := StandardMaterial3D.new()
	backdrop.albedo_color = Color(0.09, 0.12, 0.22)
	backdrop.roughness = 0.85
	for b: Array in [[Vector3(6.0, 4.0, 0.02), Vector3(0.0, 2.0, -0.01)], [Vector3(6.0, 0.02, 6.0), Vector3(0.0, -0.01, 3.0)]]:
		var mesh := BoxMesh.new()
		mesh.size = b[0]
		mesh.material = backdrop
		var node := MeshInstance3D.new()
		node.mesh = mesh
		root.add_child(node)
		node.position = b[1]
	var key := DirectionalLight3D.new()
	key.light_color = Color(1.0, 0.9, 0.78)
	key.light_energy = 2.4
	key.shadow_enabled = true
	root.add_child(key)
	key.look_at_from_position(Vector3(-1.4, 2.6, 2.0), TARGET)
	var fill := OmniLight3D.new()
	fill.light_color = Color(0.6, 0.72, 1.0)
	fill.light_energy = 1.2
	fill.omni_range = 5.0
	root.add_child(fill)
	fill.position = Vector3(1.6, 1.2, 1.6)
	var socket: Node3D = (load("res://import/crystal_socket.glb") as PackedScene).instantiate()
	root.add_child(socket)
	_look = Socket.apply(socket)
	var anchor: Node3D = socket.find_child("crystal_anchor", true, false)
	var crystal: Node3D = (load("res://import/energy_crystal.glb") as PackedScene).instantiate()
	anchor.add_child(crystal)
	_crystal = crystal
	var cl: Dictionary = Crystal.apply(crystal)
	Socket.seat_crystal(cl)
	Crystal.set_charge(cl, 1.0)
	Socket.set_state(_look, "charged")
	var cam := Camera3D.new()
	cam.fov = 36.0
	root.add_child(cam)
	cam.make_current()
	var y: float = deg_to_rad(YAW)
	var e: float = deg_to_rad(ELEV)
	var eye := TARGET + Vector3(sin(y) * cos(e), sin(e), cos(y) * cos(e)) * DIST
	cam.look_at_from_position(eye, TARGET)


func _shot(size: Vector2i) -> Image:
	root.size = size
	for _i: int in 40:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	if img.get_size() != size:
		img.resize(size.x, size.y, Image.INTERPOLATE_LANCZOS)
	return img
