extends SceneTree
## The alien 3D pilot's step-2b-2 proof (art #196) in an off-screen window (the runner's _godot.window();
## tools/blender/alien_pilot_run.py --sheet stages the welded <head>_char.glb and calls it).
## Args after "--": <res:// GLB> <out PNG> <mode>
##   expr:  the head under lights after the recommended look (look_presets.json, 2026-10-19: AgX at exposure
##          0.9, sky ambient, a key and a back rim, here 2.2 and 2.0 for the textured skin) from 3/4 front: rest, smile, sad, angry,
##          surprised, talk, blink and the Head bone turned 40 degrees (the neck weld), 4 x 2 cells of 320 px;
##   gills: the Head bone swinging +-35 degrees (1.2 s period), six frames per row, one row per spring setting
##          (none, then GRID's stiffness and drag) through pilot_gills.gd: the gills lag and sway.

const Offscreen = preload("res://lib/offscreen.gd")
const PilotGills = preload("res://alien/pilot_gills.gd")
const CELLS := ["rest", "smile", "sad", "angry", "surprised", "talk", "blink", "turn"]
const GRID := [[], [2.0, 0.6], [1.0, 0.4], [0.4, 0.2]]  # [stiffness, drag]; [] = no springs
const TIMES := [0.15, 0.35, 0.55, 0.75, 0.95, 1.15]

var model: Node3D
var skeleton: Skeleton3D
var head_bone := -1
var cam: Camera3D


func _initialize() -> void:
	var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
	if placed != "":
		printerr(placed)
		quit(2)
		return
	_run.call_deferred()


func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var scene: PackedScene = load(args[0])
	if scene == null:
		printerr("SHEET cannot load %s" % args[0])
		quit(3)
		return
	model = scene.instantiate()
	root.add_child(model)
	skeleton = model.find_children("*", "Skeleton3D", true, false)[0]
	head_bone = skeleton.find_bone("Head")
	_look()
	cam = Camera3D.new()
	cam.fov = 30.0
	root.add_child(cam)
	var mode := args[2]
	var sheet: Image
	if mode == "gills":
		_frame(0.0, 1.25)
		sheet = await _gills()
	else:
		_frame(30.0, 1.3)
		sheet = await _expr()
	sheet.save_png(args[1])
	print("SHEET %s %s %dx%d" % [mode, args[1], sheet.get_width(), sheet.get_height()])
	quit(0)


func _look() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.42, 0.43, 0.45)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.78, 0.84, 0.9)
	env.ambient_light_energy = 0.5
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 0.9
	var world := WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	for spec: Array in [[2.2, Vector3(-35.0, -35.0, 0.0), true], [2.0, Vector3(-20.0, 160.0, 0.0), false],
			[0.6, Vector3(-10.0, 60.0, 0.0), false]]:
		var light := DirectionalLight3D.new()
		light.light_energy = spec[0]
		light.rotation_degrees = spec[1]
		light.shadow_enabled = spec[2]
		light.light_angular_distance = 2.0
		root.add_child(light)


func _frame(yaw_deg: float, dist: float) -> void:
	var centre := Vector3(0.0, 1.57, 0.0)
	var yaw := deg_to_rad(yaw_deg)
	cam.position = centre + Vector3(sin(yaw), 0.05, cos(yaw)).normalized() * dist
	cam.look_at(centre)
	cam.make_current()


func _shapes(name: String) -> void:
	for mi: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		if mi.mesh == null:
			continue
		for i: int in mi.mesh.get_blend_shape_count():
			var n := String(mi.mesh.get_blend_shape_name(i))
			var on := n == name or (name == "blink" and (n == "blink_L" or n == "blink_R"))
			mi.set_blend_shape_value(i, 1.0 if on else 0.0)


func _turn(yaw_deg: float) -> void:
	var rest := skeleton.get_bone_rest(head_bone).basis.get_rotation_quaternion()
	skeleton.set_bone_pose_rotation(head_bone, rest * Quaternion(Vector3.UP, deg_to_rad(yaw_deg)))


func _grab(size: int) -> Image:
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.resize(size, size, Image.INTERPOLATE_LANCZOS)
	img.convert(Image.FORMAT_RGBA8)
	return img


func _expr() -> Image:
	var sheet := Image.create(1280, 640, false, Image.FORMAT_RGBA8)
	for k: int in CELLS.size():
		var name: String = CELLS[k]
		_shapes(name)
		_turn(40.0 if name == "turn" else 0.0)
		for _i: int in 6:
			await process_frame
		var cell := await _grab(320)
		sheet.blit_rect(cell, Rect2i(0, 0, 320, 320), Vector2i((k % 4) * 320, (k / 4) * 320))
	return sheet


func _gills() -> Image:
	var size := 213
	var sheet := Image.create(size * TIMES.size(), size * GRID.size(), false, Image.FORMAT_RGBA8)
	_shapes("rest")
	for row: int in GRID.size():
		var sim: SpringBoneSimulator3D = null
		if GRID[row].size() == 2:
			sim = PilotGills.attach(skeleton, GRID[row][0], GRID[row][1])
		_turn(0.0)
		for _i: int in 10:
			await process_frame
		var start := Time.get_ticks_usec()
		var col := 0
		while col < TIMES.size():
			var t := (Time.get_ticks_usec() - start) / 1e6
			_turn(35.0 * sin(TAU * t / 1.2))
			await process_frame
			if t >= TIMES[col]:
				var cell := await _grab(size)
				sheet.blit_rect(cell, Rect2i(0, 0, size, size), Vector2i(col * size, row * size))
				col += 1
		if sim != null:
			print("SHEET gills row %d: %d chains, stiffness %.2f drag %.2f" % [row, sim.get_setting_count(),
					GRID[row][0], GRID[row][1]])
			sim.queue_free()
			await process_frame
	return sheet
