extends SceneTree
## The alien 3D pilot's step-2a shot (art #196): one head GLB under a plain key, fill and sky-coloured ambient light,
## from 3/4 front, in an off-screen window (the runner's _godot.window(); tools/blender/alien_pilot_run.py stages the
## GLB and calls it). Args after "--": <res:// GLB> <out PNG> [yaw in degrees, default 30].

const Offscreen = preload("res://lib/offscreen.gd")


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
		printerr("PILOT cannot load %s" % args[0])
		quit(3)
		return
	var head: Node3D = scene.instantiate()
	root.add_child(head)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.42, 0.43, 0.45)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.78, 0.84, 0.9)
	env.ambient_light_energy = 0.55
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	var world := WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var key := DirectionalLight3D.new()
	key.light_energy = 1.7
	key.shadow_enabled = true
	key.rotation_degrees = Vector3(-35.0, -35.0, 0.0)
	root.add_child(key)
	var fill := DirectionalLight3D.new()
	fill.light_energy = 0.45
	fill.rotation_degrees = Vector3(-10.0, 150.0, 0.0)
	root.add_child(fill)
	var box := _bounds(head)
	var centre := box.get_center()
	var yaw := deg_to_rad(float(args[2]) if args.size() > 2 else 30.0)
	var cam := Camera3D.new()
	cam.fov = 30.0
	root.add_child(cam)
	cam.position = centre + Vector3(sin(yaw), 0.1, cos(yaw)).normalized() * box.size.length() * 1.7
	cam.look_at(centre)
	cam.make_current()
	for _i: int in 8:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.save_png(args[1])
	print("PILOT shot %s %dx%d" % [args[1], img.get_width(), img.get_height()])
	quit(0)


func _bounds(node: Node) -> AABB:
	var box := AABB()
	var first := true
	for m: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		var b: AABB = m.global_transform * m.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box
