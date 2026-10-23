extends SceneTree
## The vault plush's review shots (art#297, step 3) in an off-screen window (the runner's _godot.window();
## tools/blender/plush_run.py stages the GLB and calls it). The plush wears plush.gd's material under the showroom's
## light (the studio HDRI's light and reflections, AgX 0.9, a soft-shadowed key, fill, rim, SSAO) in a plain dark
## room. The game's first-person camera: eyes at 1.6 m, Camera3D's 75 degree FOV. Writes into OUT:
## - views.png: front, 3/4, side, back and the face close up, with the pile shells;
## - pile.png: the face close up and the 3 m stand without and with the shells (the A/B of the fuzz);
## - colour.png: the concept, then Godot's 3/4 at the same framing;
## - hand.png: the plush held at arm's length in front of the first-person camera (1280x720);
## - stand_3m.png, stand_5m.png: the plush on a 1 m stand at 3 and 5 m (1280x720);
## - cost.json: the GPU ms of the hand view without and with the shells.
## Args after "--": <res:// GLB> <OUT dir> <albedo PNG> <normal PNG> <mask PNG> <HDRI> <concept JPG> [shells]

const Offscreen = preload("res://lib/offscreen.gd")
const Plush = preload("res://plush/plush.gd")
const BACKGROUND: Color = Color(0.13, 0.14, 0.16)
const CELL: Vector2i = Vector2i(320, 400)
const EYE: float = 1.6

var _env: Environment
var _cam: Camera3D
var _plush: Node3D
var _room: Node3D
var _stand: MeshInstance3D
var _mats: Array[ShaderMaterial]
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
	var shells: int = int(a[7]) if a.size() > 7 else 12
	var scene: PackedScene = load(a[0])
	if scene == null:
		printerr("PLUSH cannot load %s" % a[0])
		quit(3)
		return
	_plush = Node3D.new()
	root.add_child(_plush)
	var model: Node3D = scene.instantiate()
	_plush.add_child(model)
	var pile: NoiseTexture2D = Plush.pile_texture()
	await pile.changed
	_mats = Plush.apply(model, _tex(a[2]), _tex(a[3]), _tex(a[4]), pile, shells)
	_stage(a[5])
	_box = _bounds(model)
	print("PLUSH bounds %s" % _box)

	# the turnaround and the face, on the plain backdrop
	_room.visible = false
	_stand.visible = false
	_place(Vector3.ZERO, 0.0)
	var views: Array[Image] = []
	for v: Array in [[0.0, 0.0, 1.0], [35.0, 0.0, 1.0], [90.0, 0.0, 1.0], [180.0, 0.0, 1.0], [-30.0, 0.22, 0.5]]:
		views.append(await _orbit(v[0], v[1], v[2]))
	_save(_sheet(views), out.path_join("views.png"))
	var colour: Array[Image] = [_load_cell(a[6]), await _orbit(-35.0, 0.0, 1.0)]
	_save(_sheet(colour), out.path_join("colour.png"))
	# the close-ups a defect hunt needs, 720x720 each: the face, each eye, the belly, the back, the tail
	for d: Array in [["face", 0.0, 0.2, 0.42], ["eye_l", 18.0, 0.27, 0.16], ["eye_r", -18.0, 0.27, 0.16],
			["face_34", -35.0, 0.2, 0.45], ["belly", 0.0, -0.18, 0.5], ["back", 180.0, 0.0, 0.8],
			["tail", 140.0, -0.35, 0.45], ["feet", 20.0, -0.38, 0.4]]:
		var img: Image = await _orbit_full(d[1], d[2], d[3])
		_save(img, out.path_join("detail_%s.png" % d[0]))

	# the pile A/B: the face close up and the stand at 3 m, without and with the shells
	var ab: Array[Image] = []
	_shells(false)
	ab.append(await _orbit(-30.0, 0.22, 0.5))
	_shells(true)
	ab.append(await _orbit(-30.0, 0.22, 0.5))
	_room.visible = true
	_stand.visible = true
	_place(Vector3(0.0, 1.0, -3.0), 0.0)
	_shells(false)
	ab.append(_crop(await _eye(Vector3(0.0, 1.15, -3.0))))
	_shells(true)
	ab.append(_crop(await _eye(Vector3(0.0, 1.15, -3.0))))
	_save(_sheet(ab), out.path_join("pile.png"))

	# the game's views
	_save(await _eye(Vector3(0.0, 1.15, -3.0)), out.path_join("stand_3m.png"))
	_place(Vector3(0.0, 1.0, -5.0), 0.0)
	_save(await _eye(Vector3(0.0, 1.15, -5.0)), out.path_join("stand_5m.png"))
	_stand.visible = false
	_place(Vector3(0.12, EYE - 0.36, -0.46), -28.0, -12.0)
	var hand: Image = await _eye(Vector3(0.0, EYE - 0.22, -1.0))
	_save(hand, out.path_join("hand.png"))
	var cost := {}
	for on: bool in [false, true]:
		_shells(on)
		cost["shells_%d" % (shells if on else 0)] = await _gpu_ms()
	var f := FileAccess.open(out.path_join("cost.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(cost, "  ") + "\n")
	f.close()
	print("PLUSH cost %s" % JSON.stringify(cost))
	quit(0)


func _tex(path: String) -> ImageTexture:
	var img: Image = Image.load_from_file(path)
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _shells(on: bool) -> void:
	_mats[0].next_pass = _mats[1] if on and _mats.size() > 1 else null


func _place(at: Vector3, yaw_deg: float, pitch_deg: float = 0.0) -> void:
	_plush.position = at
	_plush.rotation = Vector3(deg_to_rad(pitch_deg), deg_to_rad(yaw_deg), 0.0)


func _stage(hdri: String) -> void:
	root.msaa_3d = Viewport.MSAA_4X
	_env = Environment.new()
	_env.background_mode = Environment.BG_COLOR
	_env.background_color = BACKGROUND
	var sky := Sky.new()
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	var image: Image = Image.load_from_file(hdri) if FileAccess.file_exists(hdri) else null
	if image != null and not image.is_empty():
		var pano := PanoramaSkyMaterial.new()
		pano.panorama = ImageTexture.create_from_image(image)
		sky.sky_material = pano
	else:
		sky.sky_material = ProceduralSkyMaterial.new()
	_env.sky = sky
	_env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	_env.ambient_light_sky_contribution = 0.5
	_env.ambient_light_color = Color(1.0, 0.8, 0.62)
	_env.ambient_light_energy = 0.12
	_env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	_env.tonemap_mode = Environment.TONE_MAPPER_AGX
	_env.tonemap_exposure = 0.9
	_env.ssao_enabled = true
	_env.ssao_radius = 0.6
	_env.ssao_intensity = 1.5
	_env.ssao_light_affect = 0.2
	var world := WorldEnvironment.new()
	world.environment = _env
	root.add_child(world)
	var key := _light(Vector3(-2.0, 3.2, 3.0), 2.0, true, 0.6)
	key.light_angular_distance = 1.5
	key.shadow_blur = 1.0
	_light(Vector3(3.0, 1.6, 2.0), 0.12, false, 0.0)
	_light(Vector3(0.5, 2.5, -3.0), 0.30, false, 0.3)
	# a plain dark room (a floor and a back wall) and a 1 m stand
	_room = Node3D.new()
	root.add_child(_room)
	var metal := StandardMaterial3D.new()
	metal.albedo_color = Color(0.32, 0.34, 0.38)
	metal.roughness = 0.55
	metal.metallic = 0.6
	var floor_mesh := PlaneMesh.new()
	floor_mesh.size = Vector2(12.0, 12.0)
	_mesh(_room, floor_mesh, metal, Vector3(0.0, 0.0, -3.0))
	var wall := BoxMesh.new()
	wall.size = Vector3(12.0, 4.0, 0.1)
	_mesh(_room, wall, metal, Vector3(0.0, 2.0, -7.0))
	var stand_mesh := CylinderMesh.new()
	stand_mesh.top_radius = 0.17
	stand_mesh.bottom_radius = 0.2
	stand_mesh.height = 1.0
	var stand_mat := StandardMaterial3D.new()
	stand_mat.albedo_color = Color(0.2, 0.21, 0.24)
	stand_mat.roughness = 0.35
	stand_mat.metallic = 0.8
	_stand = _mesh(root, stand_mesh, stand_mat, Vector3(0.0, 0.5, -3.0))
	_cam = Camera3D.new()
	_cam.fov = 75.0
	_cam.near = 0.05
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


func _light(at: Vector3, energy: float, shadow: bool, specular: float) -> DirectionalLight3D:
	var light := DirectionalLight3D.new()
	root.add_child(light)
	light.look_at_from_position(at, Vector3.ZERO)
	light.light_energy = energy
	light.light_specular = specular
	light.shadow_enabled = shadow
	return light


## A studio framing around the plush at the origin: yaw 0 its front (+Z), lift in plush heights, frac the framed share.
func _orbit(yaw_deg: float, lift: float, frac: float) -> Image:
	_cam.fov = 22.0
	var c: Vector3 = _box.get_center() + _plush.position + Vector3(0.0, lift * _box.size.y, 0.0)
	var h: float = _box.size.y * 1.08 * frac
	var dist: float = h * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
	var yaw := deg_to_rad(yaw_deg)
	_cam.position = c + Vector3(sin(yaw), 0.06, cos(yaw)).normalized() * dist
	_cam.look_at(c)
	return _crop(await _frame())


## The same framing as _orbit, the frame's middle 720x720 at full resolution.
func _orbit_full(yaw_deg: float, lift: float, frac: float) -> Image:
	_cam.fov = 22.0
	var c: Vector3 = _box.get_center() + _plush.position + Vector3(0.0, lift * _box.size.y, 0.0)
	var h: float = _box.size.y * 1.08 * frac
	var dist: float = h * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
	var yaw := deg_to_rad(yaw_deg)
	_cam.position = c + Vector3(sin(yaw), 0.06, cos(yaw)).normalized() * dist
	_cam.look_at(c)
	var img: Image = await _frame()
	var s: int = img.get_height()
	return img.get_region(Rect2i((img.get_width() - s) / 2, 0, s, s))


## The first-person view: the camera at eye height over the origin, looking at target.
func _eye(target: Vector3) -> Image:
	_cam.fov = 75.0
	_cam.position = Vector3(0.0, EYE, 0.0)
	_cam.look_at(target)
	return await _frame()


func _frame() -> Image:
	for _i: int in 10:
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


## The middle of a frame at the cell's aspect, scaled to the cell.
func _crop(img: Image) -> Image:
	var hh: int = img.get_height()
	var ww: int = hh * CELL.x / CELL.y
	var c: Image = img.get_region(Rect2i((img.get_width() - ww) / 2, 0, ww, hh))
	c.resize(CELL.x, CELL.y, Image.INTERPOLATE_LANCZOS)
	return c


func _load_cell(path: String) -> Image:
	var img: Image = Image.load_from_file(path)
	img.convert(Image.FORMAT_RGB8)
	var k: int = mini(img.get_width(), img.get_height() * CELL.x / CELL.y)
	var hh: int = k * CELL.y / CELL.x
	img = img.get_region(Rect2i((img.get_width() - k) / 2, (img.get_height() - hh) / 2, k, hh))
	img.resize(CELL.x, CELL.y, Image.INTERPOLATE_LANCZOS)
	return img


func _sheet(cells: Array[Image]) -> Image:
	var sheet := Image.create(cells.size() * (CELL.x + 4) - 4, CELL.y, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.2, 0.2, 0.2))
	for i: int in cells.size():
		sheet.blit_rect(cells[i], Rect2i(Vector2i.ZERO, CELL), Vector2i(i * (CELL.x + 4), 0))
	return sheet


func _save(img: Image, path: String) -> void:
	img.save_png(path)
	print("PLUSH wrote %s" % path)


func _bounds(node: Node) -> AABB:
	var box := AABB()
	var first := true
	for m: MeshInstance3D in node.find_children("*", "MeshInstance3D", true, false):
		var b: AABB = m.global_transform * m.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box
