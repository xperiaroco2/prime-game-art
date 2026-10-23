extends SceneTree
## The energy crystal's review shots and sheet (art#263's station props) in an off-screen window (the runner's
## _godot.window(); tools/blender/crystal_run.py stages the GLB and calls it). The crystal wears crystal.gd's look
## under the ship interior's night light, rebuilt from godot/ship/ship.gd and layouts/ship/ship.toml [light]: AgX at
## exposure 1.0, the dark blue ambient (0.13, 0.155, 0.24), glow for the emissive parts (intensity 0.6, bloom 0.03,
## HDR threshold 1.0, soft light), SSAO 0.6 / 1.5, SSIL, a warm interior lamp (1.0, 0.7, 0.42), the cool night key
## (0.78, 0.84, 1.0) and a cyan strip's light. Writes into OUT, for state in charged and spent:
## - <state>_q34.png, <state>_front.png, <state>_top.png: the orbit views (576x720) on the dark backdrop;
## - <state>_cap.png, <state>_loop.png, <state>_facets.png: close-ups (720x720);
## - <state>_room.png: the crystal on a 1 m post by a wall, seen from 1 m at eye height (1280x720): its glow on
##   the wall and the post;
## - hand.png: the charged crystal carried at arm's length in the first-person view (1280x720);
## - sheet.png: the concept beside Blender's and Godot's views of both states and the close-ups, labelled;
## - cost.json: the GPU ms of the hand view, charged and spent.
## Args after "--": <res:// GLB> <OUT dir> <Blender renders dir> <concept charged> <concept spent> <concept charger>
## [HDRI for the reflections]

const Offscreen = preload("res://lib/offscreen.gd")
const Crystal = preload("res://crystal/crystal.gd")
const BACKGROUND: Color = Color(0.055, 0.075, 0.12)
const EYE: float = 1.6
const VIEW: Vector2i = Vector2i(576, 720)
const CLOSE: Vector2i = Vector2i(720, 720)

var _env: Environment
var _cam: Camera3D
var _crystal: Node3D
var _look: Dictionary
var _room: Node3D
var _strip: OmniLight3D
var _box: AABB


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
	var scene: PackedScene = load(a[0])
	if scene == null:
		printerr("CRYSTAL cannot load %s" % a[0])
		quit(3)
		return
	_crystal = Node3D.new()
	root.add_child(_crystal)
	var model: Node3D = scene.instantiate()
	_crystal.add_child(model)
	_look = Crystal.apply(model)
	_stage(a[6] if a.size() > 6 else "")
	_box = _bounds(model)
	print("CRYSTAL bounds %s" % _box)

	var shots := {}
	for state: String in ["charged", "spent"]:
		Crystal.set_charge(_look, 1.0 if state == "charged" else 0.0)
		_room.visible = false
		_strip.visible = true
		_place(Vector3.ZERO, 0.0)
		for v: Array in [["q34", -35.0, 14.0, 1.0, 0.0], ["front", 0.0, 4.0, 1.0, 0.0], ["top", 0.0, 82.0, 0.5, 0.13]]:
			var img: Image = await _orbit(v[1], v[2], v[3], v[4], VIEW)
			shots["%s_%s" % [state, v[0]]] = img
			_save(img, out.path_join("%s_%s.png" % [state, v[0]]))
		for v: Array in [["cap", -30.0, 18.0, 0.34, 0.105], ["loop", 20.0, 32.0, 0.24, 0.15],
				["facets", -20.0, 6.0, 0.42, -0.05]]:
			var img: Image = await _orbit(v[1], v[2], v[3], v[4], CLOSE)
			shots["%s_%s" % [state, v[0]]] = img
			_save(img, out.path_join("%s_%s.png" % [state, v[0]]))
		_room.visible = true
		_strip.visible = false
		_place(Vector3(0.0, 1.0, -1.0), -30.0)
		var room: Image = await _eye(Vector3(0.0, 1.17, -1.0))
		shots["%s_room" % state] = room
		_save(room, out.path_join("%s_room.png" % state))
	Crystal.set_charge(_look, 1.0)
	_room.visible = true
	_place(Vector3(0.16, EYE - 0.46, -0.52), -25.0, 8.0)
	var hand: Image = await _eye(Vector3(0.0, EYE - 0.25, -1.0))
	shots["hand"] = hand
	_save(hand, out.path_join("hand.png"))
	var cost := {}
	for c: float in [1.0, 0.0]:
		Crystal.set_charge(_look, c)
		cost["hand_charge_%d" % int(c)] = await _gpu_ms()
	var f := FileAccess.open(out.path_join("cost.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(cost, "  ") + "\n")
	f.close()
	print("CRYSTAL cost %s" % JSON.stringify(cost))
	var sheet: Image = await _sheet(shots, a[2], a[3], a[4], a[5])
	_save(sheet, out.path_join("sheet.png"))
	quit(0)


func _place(at: Vector3, yaw_deg: float, pitch_deg: float = 0.0) -> void:
	_crystal.position = at
	_crystal.rotation = Vector3(deg_to_rad(pitch_deg), deg_to_rad(yaw_deg), 0.0)


func _stage(hdri: String) -> void:
	root.msaa_3d = Viewport.MSAA_4X
	_env = Environment.new()
	_env.background_mode = Environment.BG_COLOR
	_env.background_color = BACKGROUND
	# only for reflections (the background stays the plain colour): a studio HDRI stands in for the ship room's
	# reflection probes, so the bronze has something to mirror; a procedural dim room without it
	var sky := Sky.new()
	var image: Image = Image.load_from_file(hdri) if FileAccess.file_exists(hdri) else null
	if image != null and not image.is_empty():
		var pano := PanoramaSkyMaterial.new()
		pano.panorama = ImageTexture.create_from_image(image)
		pano.energy_multiplier = 0.55
		sky.sky_material = pano
	else:
		var sm := ProceduralSkyMaterial.new()
		sm.sky_top_color = Color(0.22, 0.26, 0.34)
		sm.sky_horizon_color = Color(0.55, 0.45, 0.34)
		sm.ground_horizon_color = Color(0.30, 0.26, 0.22)
		sm.ground_bottom_color = Color(0.08, 0.08, 0.09)
		sm.sun_angle_max = 0.0
		sky.sky_material = sm
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	_env.sky = sky
	_env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	_env.ambient_light_color = Color(0.13, 0.155, 0.24)
	_env.ambient_light_energy = 0.35
	_env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	_env.tonemap_mode = Environment.TONE_MAPPER_AGX
	_env.tonemap_exposure = 1.0
	_env.glow_enabled = true
	_env.glow_intensity = 0.6
	_env.glow_bloom = 0.03
	_env.glow_hdr_threshold = 1.0
	_env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	_env.ssao_enabled = true
	_env.ssao_radius = 0.6
	_env.ssao_intensity = 1.5
	_env.ssil_enabled = true
	var world := WorldEnvironment.new()
	world.environment = _env
	root.add_child(world)
	var key := DirectionalLight3D.new()  # the night key's colour, from the camera's left and above
	root.add_child(key)
	key.look_at_from_position(Vector3(-1.0, 1.6, 1.4), Vector3.ZERO)
	key.light_color = Color(0.78, 0.84, 1.0)
	key.light_energy = 0.5
	key.light_specular = 1.4
	key.shadow_enabled = true
	var lamp := OmniLight3D.new()  # a warm interior lamp, front left and above
	root.add_child(lamp)
	lamp.light_color = Color(1.0, 0.7, 0.42)
	lamp.light_energy = 1.6
	lamp.omni_range = 4.0
	lamp.omni_attenuation = 1.4
	lamp.shadow_enabled = true
	lamp.position = Vector3(-0.7, 0.75, 0.9)
	var strip := OmniLight3D.new()  # a cyan strip's light from behind right: the rim (orbit views only)
	_strip = strip
	root.add_child(strip)
	strip.light_color = Color(0.35, 0.8, 1.0)
	strip.light_energy = 0.7
	strip.omni_range = 3.0
	strip.position = Vector3(0.8, 0.45, -0.7)
	# the room: a dark metal floor, a back wall and a 1 m post for the room views
	_room = Node3D.new()
	root.add_child(_room)
	var metal := StandardMaterial3D.new()
	metal.albedo_color = Color(0.30, 0.32, 0.36)
	metal.roughness = 0.5
	metal.metallic = 0.6
	var floor_mesh := PlaneMesh.new()
	floor_mesh.size = Vector2(8.0, 8.0)
	_mesh(_room, floor_mesh, metal, Vector3(0.0, 0.0, -1.5))
	var wall := BoxMesh.new()
	wall.size = Vector3(8.0, 3.0, 0.1)
	_mesh(_room, wall, metal, Vector3(0.0, 1.5, -1.45))
	var post_mesh := CylinderMesh.new()
	post_mesh.top_radius = 0.06
	post_mesh.bottom_radius = 0.09
	post_mesh.height = 1.0
	var post_mat := StandardMaterial3D.new()
	post_mat.albedo_color = Color(0.22, 0.23, 0.26)
	post_mat.roughness = 0.35
	post_mat.metallic = 0.8
	_mesh(_room, post_mesh, post_mat, Vector3(0.0, 0.5, -1.0))
	_cam = Camera3D.new()
	_cam.near = 0.02
	_cam.far = 100.0
	root.add_child(_cam)
	_cam.make_current()


func _mesh(parent: Node, mesh: Mesh, mat: Material, at: Vector3) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	parent.add_child(mi)
	mi.position = at
	return mi


## An orbit framing of the crystal at the origin (the same as tools/blender/crystal_build.py's VIEWS): yaw 0 its
## front (+Z), elev the camera's rise, frame the share of its height shown, lift the aim above its middle in m.
func _orbit(yaw_deg: float, elev_deg: float, frame: float, lift: float, size: Vector2i) -> Image:
	_cam.fov = 22.0
	var target: Vector3 = _box.get_center() + _crystal.position + Vector3(0.0, lift, 0.0)
	var span: float = _box.size.y * frame * 1.12
	var dist: float = span * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
	var y := deg_to_rad(yaw_deg)
	var e := deg_to_rad(elev_deg)
	_cam.position = target + Vector3(sin(y) * cos(e), sin(e), cos(y) * cos(e)) * dist
	_cam.look_at(target, Vector3.UP if elev_deg < 80.0 else Vector3(0.0, 0.0, -1.0))
	return _fit(await _frame(), size)


## The first-person view: the camera at eye height over the origin, looking at target.
func _eye(target: Vector3) -> Image:
	_cam.fov = 75.0
	_cam.position = Vector3(0.0, EYE, 0.0)
	_cam.look_at(target)
	return await _frame()


func _frame() -> Image:
	for _i: int in 12:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	return img


func _gpu_ms() -> float:
	var vp: RID = root.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	for _i: int in 20:
		await process_frame
	var total: float = 0.0
	for _i: int in 60:
		await RenderingServer.frame_post_draw
		total += RenderingServer.viewport_get_measured_render_time_gpu(vp)
	return snappedf(total / 60.0, 0.001)


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


func _load(path: String, size: Vector2i) -> Image:
	var img: Image = Image.load_from_file(path)
	if img == null or img.is_empty():
		img = Image.create(size.x, size.y, false, Image.FORMAT_RGB8)
		img.fill(Color(0.3, 0.0, 0.0))
		return img
	return _fit(img, size)


## The sheet: per state the concept, Blender's 3/4, front and top, Godot's 3/4, front and top; then the close-ups
## (cap, loop, facets) charged in Blender and Godot, and the spent facets in Godot; then both room views and the hand
## view. Labelled through a SubViewport of Labels over the composed image.
func _sheet(shots: Dictionary, blender: String, c_charged: String, c_spent: String, c_charger: String) -> Image:
	var cell := Vector2i(300, 375)
	var sq := Vector2i(300, 300)
	var gap: int = 8
	var head: int = 30
	var cols: int = 7
	var width: int = cols * cell.x + (cols + 1) * gap
	var row_h: Array[int] = [cell.y, cell.y, sq.y, 340]
	var height: int = gap
	for h: int in row_h:
		height += head + h + gap
	var sheet := Image.create(width, height, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.09, 0.095, 0.11))
	var labels: Array = []  # [text, position]
	var y: int = gap
	var rows: Array = []
	for state: String in ["charged", "spent"]:
		var concept: String = c_charged if state == "charged" else c_spent
		rows.append([state, [
			["concept", _load(concept, cell)],
			["Blender 3/4", _load(blender.path_join("%s_q34.png" % state), cell)],
			["Blender front", _load(blender.path_join("%s_front.png" % state), cell)],
			["Blender top", _load(blender.path_join("%s_top.png" % state), cell)],
			["Godot 3/4", _fit(shots["%s_q34" % state], cell)],
			["Godot front", _fit(shots["%s_front" % state], cell)],
			["Godot top", _fit(shots["%s_top" % state], cell)]]])
	rows.append(["close-ups", [
		["Blender cap", _load(blender.path_join("charged_cap.png"), sq)],
		["Blender loop", _load(blender.path_join("charged_loop.png"), sq)],
		["Blender facets", _load(blender.path_join("charged_facets.png"), sq)],
		["Godot cap", _fit(shots["charged_cap"], sq)],
		["Godot loop", _fit(shots["charged_loop"], sq)],
		["Godot facets", _fit(shots["charged_facets"], sq)],
		["Godot facets, spent", _fit(shots["spent_facets"], sq)]]])
	var wide := Vector2i(cell.x * 2 + gap, 340)
	rows.append(["in the ship's light", [
		["concept: the charger", _load(c_charger, Vector2i(cell.x, 340))],
		["Godot: charged on a post, 1 m", _fit(shots["charged_room"], wide)],
		["Godot: spent on a post, 1 m", _fit(shots["spent_room"], wide)],
		["Godot: carried, first person", _fit(shots["hand"], wide)]]])
	for r: int in rows.size():
		labels.append([str(rows[r][0]).to_upper(), Vector2i(gap, y + 4), 18])
		y += head
		var x: int = gap
		for item: Array in rows[r][1]:
			var img: Image = item[1]
			sheet.blit_rect(img, Rect2i(Vector2i.ZERO, img.get_size()), Vector2i(x, y))
			labels.append([item[0], Vector2i(x + 6, y + img.get_height() - 24), 14])
			x += img.get_width() + gap
		y += row_h[r] + gap
	return await _label(sheet, labels)


func _save(img: Image, path: String) -> void:
	img.save_png(path)
	print("CRYSTAL wrote %s" % path)


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


func _bounds(node: Node) -> AABB:
	var box := AABB()
	var first := true
	for m: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		var b: AABB = m.global_transform * m.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box
