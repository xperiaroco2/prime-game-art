extends SceneTree
## The crystal charger's review sheets and cost (art#263's stations) in an off-screen window (the runner's
## _godot.window(); tools/blender/charger_run.py calls it after room.gd's shots). Writes into OUT:
## - compare_sheet.png: the approved sheet's hero view beside Blender's neutral render at its angle and Godot's shot
##   in the lens room;
## - room_sheet.png: the Godot shots in the east lens room at night (idle empty, charging, charged, a player's view,
##   the straight views, the wall's corner, the button, the ring's full turn from above);
## - closeups.png: Blender's close-ups of the edges and seams;
## - cost.json: the charger's GPU ms alone at 1280x720 from a player's eyes 1.6 m away, and its draw calls.
## Args after "--": <res:// GLB> <OUT dir> <Blender renders dir> <room shots dir> <approved sheet>

const Offscreen = preload("res://lib/offscreen.gd")
const Charger = preload("res://charger/charger.gd")


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
	print("CHARGER cost %s" % JSON.stringify(cost))
	var blender: String = a[2]
	var room: String = a[3]
	var big := Vector2i(420, 420)
	var compare: Array = [["the approved sheet (charger.jpg)", _load(a[4], big, Rect2(0.13, 0.08, 0.56, 0.84))],
		["Blender, neutral, the sheet's angle", _load(blender.path_join("hero.png"), big)],
		["Godot, the lens room at night", _load(room.path_join("q34_charged.png"), big)]]
	_save(await _grid(compare, big, 3), out.path_join("compare_sheet.png"))
	var cell := Vector2i(312, 312)
	var rows: Array = []
	for n: String in ["q34_idle", "q34_charging", "q34_charged", "eye", "front", "side", "top_down", "deck_charging",
			"wall_corner", "button", "turn_000", "turn_030", "turn_060", "turn_090", "turn_120", "turn_150"]:
		rows.append([n.replace("_", " "), _load(room.path_join(n + ".png"), cell)])
	_save(await _grid(rows, cell, 4), out.path_join("room_sheet.png"))
	var cu: Array = []
	for n: String in ["cu_button", "cu_facet", "cu_seams", "cu_band", "cu_deck", "cu_slot", "cu_prong_cap",
			"cu_prong_strips", "cu_inner_head", "cu_feet", "cu_back", "cu_panel_side", "charging", "hero_idle", "side_q",
			"ortho_top"]:
		cu.append([n.replace("_", " "), _load(blender.path_join(n + ".png"), cell)])
	_save(await _grid(cu, cell, 4), out.path_join("closeups.png"))
	quit(0)


func _save(img: Image, path: String) -> void:

	img.save_png(path)
	print("CHARGER wrote %s" % path)


func _cost(res: String) -> Dictionary:
	var scene: PackedScene = load(res)
	if scene == null:
		printerr("CHARGER cannot load %s" % res)
		return {}
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.03, 0.035, 0.05)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.13, 0.155, 0.24)
	env.ambient_light_energy = 0.12
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.glow_enabled = true
	env.ssao_enabled = true
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
	var look: Dictionary = Charger.apply(model)
	Charger.set_state(look, "charging")
	var cam := Camera3D.new()
	cam.fov = 75.0
	root.add_child(cam)
	cam.make_current()
	cam.look_at_from_position(Vector3(0.3, 1.6, 1.9), Vector3(0.0, 1.0, 0.27))
	var with: Dictionary = await _gpu(Vector2i(1280, 720))
	model.visible = false
	var without: Dictionary = await _gpu(Vector2i(1280, 720))
	for n: Node in [model, world, lamp, floor_node, cam]:
		n.queue_free()
	return {"gpu_ms_with": with["gpu"], "gpu_ms_without": without["gpu"],
		"gpu_ms_charger": snappedf(with["gpu"] - without["gpu"], 0.001),
		"draw_calls_charger": with["draws"] - without["draws"], "view": "1280x720, eye 1.6 m, 1.6 m away, charging"}


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


## Cells in rows of cols, each labelled at its foot.
func _grid(items: Array, cell: Vector2i, cols: int) -> Image:
	var gap: int = 8
	var rows: int = ceili(float(items.size()) / cols)
	var img := Image.create(cols * cell.x + (cols + 1) * gap, rows * cell.y + (rows + 1) * gap, false,
		Image.FORMAT_RGB8)
	img.fill(Color(0.09, 0.095, 0.11))
	var labels: Array = []
	for i: int in items.size():
		var x: int = gap + (i % cols) * (cell.x + gap)
		var y: int = gap + (i / cols) * (cell.y + gap)
		var c: Image = items[i][1]
		img.blit_rect(c, Rect2i(Vector2i.ZERO, c.get_size()), Vector2i(x, y))
		labels.append([items[i][0], Vector2i(x + 6, y + cell.y - 24)])
	return await _label(img, labels)


func _label(img: Image, labels: Array) -> Image:
	var vp := SubViewport.new()
	vp.size = img.get_size()
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var rect := TextureRect.new()
	rect.texture = ImageTexture.create_from_image(img)
	rect.size = Vector2(img.get_size())
	vp.add_child(rect)
	for l: Array in labels:
		var lab := Label.new()
		lab.text = l[0]
		lab.position = Vector2(l[1])
		lab.add_theme_font_size_override("font_size", 15)
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
