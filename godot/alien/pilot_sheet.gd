extends SceneTree
## The alien 3D pilot's proof sheets (art #196, steps 2b-2 and 2b-3) in an off-screen window (the runner's
## _godot.window(); tools/blender/alien_pilot_run.py --sheet stages the welded <head>_char.glb and calls it).
## Args after "--": <res:// GLB> <out PNG> <mode> [<Blender PNG>] [lod]
##   Every mode but colour renders under the approved look (look_presets.json: AgX at exposure 0.9, half sky and half
##   warm ambient, light D through showroom/look_lights.gd). The viewport's mesh LOD is off unless "lod" is given:
##   Godot's generated LODs of the axolotl's thin gill fins smear them sideways (2b-3, docs/godot.md, "The pilot
##   character in Godot"); the import turns them off too (meshes/generate_lods false).
##   expr:   from 3/4 front: rest, smile, sad, angry, surprised, talk, blink and the Head bone turned 40 degrees (the
##           neck weld), 4 x 2 cells of 320 px;
##   gills:  the Head bone swinging +-35 degrees (1.2 s period), six frames per row, one row per spring setting
##           (none, then GRID's stiffness and drag) through pilot_gills.gd: the gills lag and sway;
##   colour: the front at rest: the Blender PNG (the head's review render), the bare albedo, then the approved look
##           at each of FACTORS, 213 px cells; prints each cell's median head colour (sRGB, the cell's top 55 %) as
##           COLOUR lines.

const Offscreen = preload("res://lib/offscreen.gd")
const PilotGills = preload("res://alien/pilot_gills.gd")
const LookLights = preload("res://showroom/look_lights.gd")
const PRESETS := "res://showroom/look_presets.json"
const CELLS := ["rest", "smile", "sad", "angry", "surprised", "talk", "blink", "turn"]
const GRID := [[], [2.0, 0.6], [1.0, 0.4], [0.4, 0.2]]  # [stiffness, drag]; [] = no springs
const TIMES := [0.15, 0.35, 0.55, 0.75, 0.95, 1.15]
## The colour grid: the bare albedo (unshaded, linear tonemap: the texture as Godot reads it), then the approved look
## with every material's albedo but the eyes' scaled by each of FACTORS (glTF baseColorFactor).
const FACTORS := [1.0, 0.7, 0.5, 0.35]

var model: Node3D
var skeleton: Skeleton3D
var head_bone := -1
var cam: Camera3D
var _look_nodes: Array[Node] = []
var _materials := {}


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
	if not "lod" in args:
		root.mesh_lod_threshold = 0.0
	cam = Camera3D.new()
	cam.fov = 30.0
	root.add_child(cam)
	var mode := args[2]
	var sheet: Image
	if mode == "colour":
		_frame(0.0, 1.3)
		sheet = await _colour(args[3])
	elif mode == "gills":
		_look("approved")
		_frame(0.0, 1.25)
		sheet = await _gills()
	else:
		_look("approved")
		_frame(30.0, 1.3)
		sheet = await _expr()
	sheet.save_png(args[1])
	print("SHEET %s %s %dx%d" % [mode, args[1], sheet.get_width(), sheet.get_height()])
	quit(0)


func _look(which: String) -> void:
	for n: Node in _look_nodes:
		n.queue_free()
	_look_nodes.clear()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.42, 0.43, 0.45)
	var lights: Array[DirectionalLight3D] = []
	if which == "albedo":
		env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	else:  # the approved look: its environment and light D
		var doc: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(PRESETS))
		var e: Dictionary = doc["environment"]
		var sky := Sky.new()
		sky.radiance_size = Sky.RADIANCE_SIZE_256
		sky.sky_material = ProceduralSkyMaterial.new()
		env.sky = sky
		env.tonemap_mode = Environment.TONE_MAPPER_AGX
		env.tonemap_exposure = float(e["tonemap_exposure"])
		env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
		env.ambient_light_energy = float(e["ambient_light_energy"])
		var c: Array = e["ambient_light_color"]
		env.ambient_light_color = Color(c[0], c[1], c[2])
		env.ambient_light_sky_contribution = float(e["ambient_light_sky_contribution"])
		env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
		for l: Dictionary in LookLights.directional():
			var light := DirectionalLight3D.new()
			var at: Array = l["at"]
			var to: Array = l["look_at"]
			light.light_energy = float(l["energy"])
			light.light_specular = float(l.get("specular", 0.5))
			light.shadow_enabled = bool(l.get("shadow", false))
			light.light_angular_distance = 2.0
			light.set_meta("aim", [Vector3(at[0], at[1], at[2]), Vector3(to[0], to[1], to[2])])
			lights.append(light)
	_unlit(which == "albedo")
	var world := WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	_look_nodes.append(world)
	for light: DirectionalLight3D in lights:
		root.add_child(light)
		if light.has_meta("aim"):
			var aim: Array = light.get_meta("aim")
			light.look_at_from_position(aim[0], aim[1])
		_look_nodes.append(light)


## Every surface unshaded (its albedo as is), or back to its imported material.
func _unlit(on: bool) -> void:
	for mi: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		if mi.mesh == null:
			continue
		for s: int in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(s) as BaseMaterial3D
			if m == null:
				continue
			if on:
				if not _materials.has(m):
					var u: BaseMaterial3D = m.duplicate()
					u.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
					_materials[m] = u
				mi.set_surface_override_material(s, _materials[m])
			else:
				mi.set_surface_override_material(s, null)


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


## The median colour (sRGB) of the pixels that differ from the cell's top-left corner (the background).
func _median_fg(img: Image) -> Color:
	var bg := img.get_pixel(2, 2)
	var rs: Array[float] = []
	var gs: Array[float] = []
	var bs: Array[float] = []
	for y: int in range(0, img.get_height(), 2):
		for x: int in range(0, img.get_width(), 2):
			var p := img.get_pixel(x, y)
			if absf(p.r - bg.r) + absf(p.g - bg.g) + absf(p.b - bg.b) > 0.12:
				rs.append(p.r)
				gs.append(p.g)
				bs.append(p.b)
	if rs.is_empty():
		return bg
	rs.sort()
	gs.sort()
	bs.sort()
	var k := rs.size() / 2
	return Color(rs[k], gs[k], bs[k])


func _colour(blender_png: String) -> Image:
	var size := 213
	var sheet := Image.create(size * (FACTORS.size() + 2), size, false, Image.FORMAT_RGBA8)
	var ref := Image.load_from_file(blender_png)
	ref.convert(Image.FORMAT_RGBA8)
	ref.resize(size, size, Image.INTERPOLATE_LANCZOS)
	sheet.blit_rect(ref, Rect2i(0, 0, size, size), Vector2i.ZERO)
	var c := _median_fg(ref.get_region(Rect2i(0, 0, size, int(size * 0.55))))
	print("COLOUR blender %.3f %.3f %.3f" % [c.r, c.g, c.b])
	_shapes("rest")
	for k: int in FACTORS.size() + 1:
		_look("albedo" if k == 0 else "approved")
		if k > 0:
			_scale_albedo(FACTORS[k - 1])
		for _i: int in 8:
			await process_frame
		var cell := await _grab(size)
		sheet.blit_rect(cell, Rect2i(0, 0, size, size), Vector2i((k + 1) * size, 0))
		c = _median_fg(cell.get_region(Rect2i(0, 0, size, int(size * 0.55))))
		print("COLOUR %s %.3f %.3f %.3f" % ["albedo" if k == 0 else "x%.2f" % FACTORS[k - 1], c.r, c.g, c.b])
	return sheet


## Every material but the eyes' with its albedo colour (the texture's factor) at f.
func _scale_albedo(f: float) -> void:
	for mi: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		if mi.mesh == null:
			continue
		for s: int in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(s) as BaseMaterial3D
			if m == null or m.resource_name.ends_with("_eye"):
				continue
			var u: BaseMaterial3D = m.duplicate()
			u.albedo_color = Color(m.albedo_color.r * f, m.albedo_color.g * f, m.albedo_color.b * f, m.albedo_color.a)
			mi.set_surface_override_material(s, u)


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
