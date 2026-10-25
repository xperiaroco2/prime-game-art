extends SceneTree
## The breaker board on a neutral backdrop at the picked sheet's hero angle (art#263's stations, board-2), in an
## off-screen window (the runner's _godot.window(); tools/blender/board_run.py calls it after the corridor shots, with
## the board staged in res://import/). The socket's studio (socket-2): a dark blue wall and floor, a soft sky for the
## metal to mirror, a warm key from the upper left and a cool fill, AgX and glow: the sheet's studio, not the ship.
## Writes into OUT:
## - studio.png: the board (board.gd's look, all on, the beacon lit as on the sheet's hero view);
## - compare_sheet.png: the sheet's hero view (its left half) beside studio.png at the same height.
## Args after "--": <OUT dir> <sheet jpg>

const Offscreen = preload("res://lib/offscreen.gd")
const Board = preload("res://board/board.gd")
const SIZE := Vector2i(1100, 800)
const YAW := -24.0          # the camera toward the board's left (-u), as the sheet's hero view
const ELEV := 6.0
const DIST := 2.7
const TARGET := Vector3(0.0, 0.88, 0.12)


func _initialize() -> void:
	var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
	if placed != "":
		printerr(placed)
		quit(2)
		return
	create_timer(150.0).timeout.connect(func() -> void:  # a script error stops _run: quit with its log, not hang
		printerr("BOARD studio: no result in 150 s")
		quit(3))
	_run.call_deferred()


func _run() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var out: String = a[0]
	_stage()
	var shot: Image = await _shot(SIZE)
	shot.save_png(out.path_join("studio.png"))
	var sheet: Image = Image.load_from_file(a[1])
	sheet.convert(Image.FORMAT_RGB8)
	# the sheet's hero view (1536 x 1024): the big board left of the figure
	var w: int = sheet.get_width()
	var h: int = sheet.get_height()
	var cut: Image = sheet.get_region(Rect2i(int(w * 0.01), int(h * 0.08), int(w * 0.49), int(h * 0.56)))
	cut.resize(int(cut.get_width() * float(SIZE.y) / cut.get_height()), SIZE.y, Image.INTERPOLATE_LANCZOS)
	var both := Image.create(cut.get_width() + 8 + SIZE.x, SIZE.y, false, Image.FORMAT_RGB8)
	both.fill(Color(0.9, 0.9, 0.9))
	both.blit_rect(cut, Rect2i(Vector2i.ZERO, cut.get_size()), Vector2i.ZERO)
	both.blit_rect(shot, Rect2i(Vector2i.ZERO, SIZE), Vector2i(cut.get_width() + 8, 0))
	both.save_png(out.path_join("compare_sheet.png"))
	print("BOARD studio wrote %s" % out.path_join("compare_sheet.png"))
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
	env.glow_intensity = 0.6
	env.glow_bloom = 0.03
	env.glow_hdr_threshold = 1.0
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	env.ssao_enabled = true
	var world := WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var backdrop := StandardMaterial3D.new()
	backdrop.albedo_color = Color(0.09, 0.12, 0.22)
	backdrop.roughness = 0.85
	for b: Array in [[Vector3(8.0, 4.0, 0.02), Vector3(0.0, 2.0, -0.01)], [Vector3(8.0, 0.02, 6.0), Vector3(0.0, -0.01, 3.0)]]:
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
	key.look_at_from_position(Vector3(-1.6, 2.6, 2.2), TARGET)
	var fill := OmniLight3D.new()
	fill.light_color = Color(0.6, 0.72, 1.0)
	fill.light_energy = 1.2
	fill.omni_range = 5.0
	root.add_child(fill)
	fill.position = Vector3(1.8, 1.2, 1.8)
	var board: Node3D = (load("res://import/breaker_board.glb") as PackedScene).instantiate()
	root.add_child(board)
	# on a flat backdrop the board's mount block stands its plate off the wall by [mount] d, as on the ship's pillows
	board.position = Vector3(0.0, 0.0, 0.07)
	var look: Dictionary = Board.apply(board)
	Board.set_problem(look, true)
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
