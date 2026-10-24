extends SceneTree
## The start console's review sheet and cost (art#263's stations) in an off-screen window (the runner's
## _godot.window(); tools/blender/console_run.py calls it after hall.gd's shots). Writes into OUT:
## - sheet.png: the concept beside Blender's renders and Godot's shots in the ship's hall (three-quarter, front,
##   side, top; the close-ups of the button, the strips, the emitter and the hologram; the states), labelled;
## - cost.json: the console's GPU ms alone under the hall's night look at 1280x720 from a player's eyes 1.6 m away
##   (with and without it; the rest of the scene is a dark floor), and its draw calls.
## Args after "--": <res:// GLB> <OUT dir> <Blender renders dir> <hall shots dir> <concept look> <concept hologram>

const Offscreen = preload("res://lib/offscreen.gd")
const Console = preload("res://console/console.gd")


func _initialize() -> void:
	var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
	if placed != "":
		printerr(placed)
		quit(2)
		return
	_run.call_deferred()


func _run() -> void:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var out: String = a[1]
	var cost: Dictionary = await _cost(a[0])
	var f := FileAccess.open(out.path_join("cost.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(cost, "  ") + "\n")
	f.close()
	print("CONSOLE cost %s" % JSON.stringify(cost))
	var sheet: Image = await _sheet(a[2], a[3], a[4], a[5])
	sheet.save_png(out.path_join("sheet.png"))
	print("CONSOLE wrote %s" % out.path_join("sheet.png"))
	quit(0)


func _cost(res: String) -> Dictionary:
	var scene: PackedScene = load(res)
	if scene == null:
		printerr("CONSOLE cannot load %s" % res)
		return {}
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.03, 0.035, 0.05)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.13, 0.155, 0.24)
	env.ambient_light_energy = 0.12
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.glow_enabled = true
	env.glow_intensity = 0.6
	env.glow_bloom = 0.03
	env.glow_hdr_threshold = 1.0
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	env.ssao_enabled = true
	env.ssil_enabled = true
	var world := WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var lamp := OmniLight3D.new()
	lamp.light_color = Color(1.0, 0.7, 0.42)
	lamp.omni_range = 4.0
	lamp.shadow_enabled = true
	root.add_child(lamp)
	lamp.position = Vector3(-1.5, 3.0, 1.5)
	var floor_mesh := PlaneMesh.new()
	floor_mesh.size = Vector2(10.0, 10.0)
	var floor_node := MeshInstance3D.new()
	floor_node.mesh = floor_mesh
	root.add_child(floor_node)
	var model: Node3D = scene.instantiate()
	root.add_child(model)
	Console.apply(model)
	var cam := Camera3D.new()
	cam.fov = 75.0
	root.add_child(cam)
	cam.make_current()
	cam.look_at_from_position(Vector3(0.3, 1.6, 2.1), Vector3(0.0, 1.3, 0.0))
	var with: Dictionary = await _gpu(Vector2i(1280, 720))
	model.visible = false
	var without: Dictionary = await _gpu(Vector2i(1280, 720))
	model.queue_free()
	world.queue_free()
	lamp.queue_free()
	floor_node.queue_free()
	cam.queue_free()
	return {"gpu_ms_with": with["gpu"], "gpu_ms_without": without["gpu"],
		"gpu_ms_console": snappedf(with["gpu"] - without["gpu"], 0.001),
		"draw_calls_console": with["draws"] - without["draws"], "view": "1280x720, eye 1.6 m, 2.1 m away"}


func _gpu(size: Vector2i) -> Dictionary:
	root.size = size
	var vp: RID = root.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	for _i: int in 30:
		await process_frame
	var total: float = 0.0
	for _i: int in 90:
		await RenderingServer.frame_post_draw
		total += RenderingServer.viewport_get_measured_render_time_gpu(vp)
	var draws: int = RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
	return {"gpu": snappedf(total / 90.0, 0.001), "draws": draws}


## The middle of img at size's aspect, scaled to size.
func _fit(img: Image, size: Vector2i) -> Image:
	var w: int = img.get_width()
	var h: int = img.get_height()
	var cw: int = mini(w, h * size.x / size.y)
	var ch: int = cw * size.y / size.x
	var c: Image = img.get_region(Rect2i((w - cw) / 2, (h - ch) / 2, cw, ch))
	c.convert(Image.FORMAT_RGB8)
	c.resize(size.x, size.y, Image.INTERPOLATE_LANCZOS)
	return c


func _load(path: String, size: Vector2i, region: Rect2 = Rect2(0, 0, 1, 1)) -> Image:
	var img: Image = Image.load_from_file(path) if FileAccess.file_exists(path) else null
	if img == null or img.is_empty():
		img = Image.create(size.x, size.y, false, Image.FORMAT_RGB8)
		img.fill(Color(0.3, 0.0, 0.0))
		return img
	var w: int = img.get_width()
	var h: int = img.get_height()
	img = img.get_region(Rect2i(int(region.position.x * w), int(region.position.y * h), int(region.size.x * w),
		int(region.size.y * h)))
	return _fit(img, size)


## The sheet, rows of labelled cells: the look (the concept, Blender, Godot in the hall, a player's view), the
## straight views (Blender and Godot), the close-ups (Blender and Godot), the states.
func _sheet(blender: String, hall: String, c_look: String, c_holo: String) -> Image:
	var cell := Vector2i(320, 320)
	var gap: int = 8
	var head: int = 30
	var cols: int = 8
	var width: int = cols * cell.x + (cols + 1) * gap
	var concept_l := Rect2(0.0, 0.08, 0.625, 0.92)  # console-final.jpg: the big three-quarter view on its left
	var concept_f := Rect2(0.63, 0.0, 0.37, 0.46)   # its front view
	var concept_t := Rect2(0.63, 0.45, 0.37, 0.55)  # its top view
	var rows: Array = [
		["the look: the concept, Blender, Godot in the ship's hall at night", [
			["concept", _load(c_look, cell * Vector2i(2, 1) + Vector2i(gap, 0), concept_l)],
			["Blender 3/4", _load(blender.path_join("idle_q34.png"), cell)],
			["Godot 3/4, the hall", _load(hall.path_join("q34.png"), cell * Vector2i(2, 1) + Vector2i(gap, 0))],
			["Godot: a player at the console", _load(hall.path_join("eye.png"), cell * Vector2i(2, 1) + Vector2i(gap, 0))],
			["concept hologram", _load(c_holo, cell)]]],
		["straight views", [
			["concept front", _load(c_look, cell, concept_f)],
			["Blender front", _load(blender.path_join("idle_front.png"), cell)],
			["Blender side", _load(blender.path_join("idle_side.png"), cell)],
			["Blender top", _load(blender.path_join("idle_top.png"), cell)],
			["concept top", _load(c_look, cell, concept_t)],
			["Godot front", _load(hall.path_join("front.png"), cell)],
			["Godot side", _load(hall.path_join("side.png"), cell)],
			["Godot top", _load(hall.path_join("top_down.png"), cell)]]],
		["close-ups (idle)", [
			["Blender button", _load(blender.path_join("idle_button.png"), cell)],
			["Blender strips", _load(blender.path_join("idle_strips.png"), cell)],
			["Blender emitter", _load(blender.path_join("idle_emitter.png"), cell)],
			["Blender hologram", _load(blender.path_join("idle_holo.png"), cell)],
			["Godot button", _load(hall.path_join("button.png"), cell)],
			["Godot strips", _load(hall.path_join("strips.png"), cell)],
			["Godot emitter", _load(hall.path_join("emitter.png"), cell)],
			["Godot hologram", _load(hall.path_join("holo.png"), cell)]]],
		["states: the order playing (the west wing's yellow lamp), a stage passed (two strips green)", [
			["Blender: order", _load(blender.path_join("order_holo.png"), cell)],
			["Blender: order 3/4", _load(blender.path_join("order_q34.png"), cell)],
			["Blender: stage passed", _load(blender.path_join("stage_strips.png"), cell)],
			["Godot: order", _load(hall.path_join("holo_order.png"), cell * Vector2i(2, 1) + Vector2i(gap, 0))],
			["Godot: stage passed", _load(hall.path_join("strips_stage.png"), cell)],
			["Godot: idle strips", _load(hall.path_join("strips.png"), cell)]]],
		["the drawing (gold: the model's edges, orange: its heights, cyan: the hologram's box) over the concept's "
			+ "stretched views and over the model's straight renders", [
			["concept front", _load(blender.path_join("overlay_concept_front.png"), cell)],
			["concept side", _load(blender.path_join("overlay_concept_side.png"), cell)],
			["concept top", _load(blender.path_join("overlay_concept_top.png"), cell)],
			["model front", _load(blender.path_join("overlay_model_front.png"), cell)],
			["model side", _load(blender.path_join("overlay_model_side.png"), cell)],
			["model top", _load(blender.path_join("overlay_model_top.png"), cell)],
			["Godot top, the hall", _load(hall.path_join("top_down.png"), cell * Vector2i(2, 1) + Vector2i(gap, 0))]]],
	]
	var height: int = gap + rows.size() * (head + cell.y + gap)
	var sheet := Image.create(width, height, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.09, 0.095, 0.11))
	var labels: Array = []
	var y: int = gap
	for row: Array in rows:
		labels.append([str(row[0]).to_upper(), Vector2i(gap, y + 4), 18])
		y += head
		var x: int = gap
		for item: Array in row[1]:
			var img: Image = item[1]
			sheet.blit_rect(img, Rect2i(Vector2i.ZERO, img.get_size()), Vector2i(x, y))
			labels.append([item[0], Vector2i(x + 6, y + img.get_height() - 24), 14])
			x += img.get_width() + gap
		y += cell.y + gap
	return await _label(sheet, labels)


func _label(img: Image, labels: Array) -> Image:
	var vp := SubViewport.new()
	vp.size = img.get_size()
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.transparent_bg = false
	root.add_child(vp)
	var rect := TextureRect.new()
	rect.texture = ImageTexture.create_from_image(img)
	rect.size = Vector2(img.get_size())
	vp.add_child(rect)
	for l: Array in labels:
		var lab := Label.new()
		lab.text = l[0]
		lab.position = Vector2(l[1])
		lab.add_theme_font_size_override("font_size", l[2])
		lab.add_theme_color_override("font_color", Color(0.95, 0.95, 0.95))
		lab.add_theme_color_override("font_outline_color", Color(0, 0, 0))
		lab.add_theme_constant_override("outline_size", 5)
		vp.add_child(lab)
	for _i: int in 4:
		await process_frame
	await RenderingServer.frame_post_draw
	var out: Image = vp.get_texture().get_image()
	out.convert(Image.FORMAT_RGB8)
	vp.queue_free()
	return out
