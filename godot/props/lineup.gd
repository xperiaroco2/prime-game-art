extends SceneTree
## The dressing library's line-up sheets for `tools/run.py props-library --sheets DIR` (art #87, docs/props.md): the
## imported props in rows of similar height, each row beside a 1.8 m capsule for scale, every prop labelled with its id,
## shot by an orthographic camera from the front-right and above, the kit's `set` pack shader on the `kit_set` surfaces
## (kit/kit_materials.gd) and a small warm light at each fixture's LightAnchor.
## Pictures need a real window placed off-screen (the runner passes --position -30000,-30000), never headless:
##   godot --path godot --position -30000,-30000 --resolution 1600x900 -s res://props/lineup.gd -- <request.json> <out dir>
## request.json: {"textures": "<dir with set_d.png ...>", "pack": {"roughness": [..], "normal_strength": [..]},
##   "sheets": [{"file": "lineup_1.png", "title": "...", "rows": [[{"id", "scene", "min": [x, y, z], "max": [..]}]]}]}.
## Writes <out>/<file> per sheet (1280 px wide) and <out>/lineup.json (the rows and the anchors found); prints
## LINEUP saved <dir>.

const KitMaterials := preload("res://kit/kit_materials.gd")
const WATCHDOG_S: float = 170.0
const SHEET_W: int = 1280
const ROW_MAX_H: int = 420
const GAP: int = 6
const LABEL_PX: float = 13.0  # label height on the sheet
const SLOT_GAP_M: float = 0.35
const CAPSULE_H: float = 1.8
const CAPSULE_R: float = 0.25
const ROW_SPACING_X: float = 2000.0
const YAW_DEG: float = 25.0
const PITCH_DEG: float = -20.0
const ANCHOR_LIGHT := Color(1.0, 0.82, 0.6)

var _camera: Camera3D
var _set: Material
var _anchors: Dictionary = {}
var _title_label: Label


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
	var out: String = args[1]
	DirAccess.make_dir_recursive_absolute(out)
	if request.get("textures", "") != "" and FileAccess.file_exists(String(request["textures"]).path_join("set_d.png")):
		_set = KitMaterials.make(request["textures"], request.get("pack", {}))
	_environment()
	_camera = Camera3D.new()
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_camera.keep_aspect = Camera3D.KEEP_WIDTH
	_camera.near = 0.05
	_camera.far = 400.0
	root.add_child(_camera)
	_camera.make_current()
	var layer: CanvasLayer = CanvasLayer.new()
	_title_label = Label.new()
	_title_label.position = Vector2(12, 6)
	_title_label.add_theme_font_size_override("font_size", 22)
	_title_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_title_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_title_label.add_theme_constant_override("outline_size", 6)
	_title_label.visible = false
	layer.add_child(_title_label)
	root.add_child(layer)
	var result: Dictionary = {"sheets": []}
	var row_index: int = 0
	for sheet: Dictionary in request["sheets"]:
		var crops: Array[Image] = []
		for row: Array in sheet["rows"]:
			var frame: Array = _build_row(row, Vector3(row_index * ROW_SPACING_X, 0, 0))
			row_index += 1
			crops.append(await _row_shot(frame[0], frame[1]))
		var title: Image = await _title_image(sheet["title"])
		_save(_sheet(title, crops), out.path_join(sheet["file"]))
		result["sheets"].append({"file": sheet["file"], "rows": (sheet["rows"] as Array).map(
			func(r: Array) -> Array: return r.map(func(p: Dictionary) -> String: return p["id"]))})
	result["anchors"] = _anchors
	var f: FileAccess = FileAccess.open(out.path_join("lineup.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(result, " "))
	f.close()
	print("LINEUP saved %s" % out)
	quit(0)


func _environment() -> void:
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.55, 0.56, 0.58)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.62, 0.64, 0.7)
	env.ambient_light_energy = 0.55
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 1.3
	env.glow_enabled = true
	env.glow_hdr_threshold = 0.9
	env.glow_intensity = 0.4
	env.ssao_enabled = true
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var key: DirectionalLight3D = DirectionalLight3D.new()
	key.light_energy = 1.4
	key.rotation_degrees = Vector3(-50.0, 45.0, 0.0)  # from the camera's side (front-right, above)
	key.shadow_enabled = true
	root.add_child(key)


## One row along +X at `origin`: the capsule, then the props (each centred in its slot, its front towards +Z), a floor
## strip and the labels. Returns [the row's points for framing, the view width in metres].
func _build_row(row: Array, origin: Vector3) -> Array:
	var holder: Node3D = Node3D.new()
	root.add_child(holder)
	var sizes: Array = row.map(func(p: Dictionary) -> Vector3: return _v(p["max"]) - _v(p["min"]))
	var slots: Array = sizes.map(func(s: Vector3) -> float: return s.x)
	var view_w: float = 0.0
	for it: int in 4:  # the labels' width depends on the view's width: a few rounds converge
		view_w = CAPSULE_R * 2.0 + SLOT_GAP_M
		for s: float in slots:
			view_w += s + SLOT_GAP_M
		var text_h: float = LABEL_PX / SHEET_W * view_w
		for i: int in row.size():
			slots[i] = maxf(sizes[i].x, 0.6 * text_h * String(row[i]["id"]).length())
	var text_h: float = LABEL_PX / SHEET_W * view_w
	var points: Array = []
	var x: float = 0.0
	var cap: MeshInstance3D = MeshInstance3D.new()
	var capsule: CapsuleMesh = CapsuleMesh.new()
	capsule.radius = CAPSULE_R
	capsule.height = CAPSULE_H
	cap.mesh = capsule
	var grey: StandardMaterial3D = StandardMaterial3D.new()
	grey.albedo_color = Color(0.72, 0.72, 0.74)
	cap.material_override = grey
	cap.position = origin + Vector3(CAPSULE_R, CAPSULE_H * 0.5, 0)
	holder.add_child(cap)
	_label(holder, "1.8 m", origin + Vector3(CAPSULE_R, -text_h * 0.9, CAPSULE_R + 0.1), text_h)
	points += _corners(origin + Vector3(0, 0, -CAPSULE_R), origin + Vector3(2 * CAPSULE_R, CAPSULE_H, CAPSULE_R))
	x = 2.0 * CAPSULE_R + SLOT_GAP_M
	var depth: float = 0.0
	for i: int in row.size():
		var p: Dictionary = row[i]
		var lo: Vector3 = _v(p["min"])
		var hi: Vector3 = _v(p["max"])
		var packed: PackedScene = load(p["scene"]) as PackedScene
		if packed == null:
			_fail("cannot load %s" % p["scene"])
			return [points, view_w]
		var n: Node3D = packed.instantiate() as Node3D
		var centre_x: float = x + slots[i] * 0.5
		n.position = origin + Vector3(centre_x - (lo.x + hi.x) * 0.5, -lo.y, -(lo.z + hi.z) * 0.5)
		holder.add_child(n)
		if _set != null:
			KitMaterials.apply(n, _set)
		for a: Node in n.find_children("LightAnchor*", "", true, false):
			var anchor: Node3D = a as Node3D
			_anchors[p["id"]] = [anchor.position.x, anchor.position.y, anchor.position.z]
			var lamp: OmniLight3D = OmniLight3D.new()
			lamp.light_color = ANCHOR_LIGHT
			lamp.light_energy = 0.8
			lamp.omni_range = clampf(hi.y - lo.y, 0.6, 2.0)
			anchor.add_child(lamp)
		var off: Vector3 = n.position
		points += _corners(off + lo, off + hi)
		depth = maxf(depth, hi.z - lo.z)
		_label(holder, p["id"], origin + Vector3(centre_x, -text_h * 0.9, (hi.z - lo.z) * 0.5 + 0.1), text_h)
		x += slots[i] + SLOT_GAP_M
	var strip: MeshInstance3D = MeshInstance3D.new()
	var box: BoxMesh = BoxMesh.new()
	box.size = Vector3(x, 0.02, depth + 0.4)
	strip.mesh = box
	var floor_mat: StandardMaterial3D = StandardMaterial3D.new()
	floor_mat.albedo_color = Color(0.42, 0.42, 0.43)
	strip.material_override = floor_mat
	strip.position = origin + Vector3(x * 0.5, -0.011, 0)
	holder.add_child(strip)
	points += _corners(origin + Vector3(0, -text_h * 1.8, -depth * 0.5 - 0.2), origin + Vector3(x, 0, depth * 0.5 + 0.2))
	return [points, view_w]


## The eight corners of the box lo..hi: the camera looks from the front-right, so two diagonal corners miss the
## row's right end and its front-low labels.
func _corners(lo: Vector3, hi: Vector3) -> Array:
	var out: Array = []
	for c: int in 8:
		out.append(Vector3(hi.x if c & 1 else lo.x, hi.y if c & 2 else lo.y, hi.z if c & 4 else lo.z))
	return out


func _label(parent: Node3D, text: String, at: Vector3, text_h: float) -> void:
	var l: Label3D = Label3D.new()
	l.text = text
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.font_size = 48
	l.outline_size = 10
	l.pixel_size = text_h / 48.0
	l.modulate = Color(1, 1, 1)
	l.outline_modulate = Color(0, 0, 0)
	l.no_depth_test = true
	l.position = at
	parent.add_child(l)


## Frames the row's points in the orthographic camera (front-right, above), grabs the window and crops the content.
func _row_shot(points: Array, _view_w: float) -> Image:
	var basis: Basis = Basis.from_euler(Vector3(deg_to_rad(PITCH_DEG), deg_to_rad(YAW_DEG), 0.0))
	var lo := Vector3(INF, INF, INF)
	var hi := Vector3(-INF, -INF, -INF)
	var inv: Basis = basis.inverse()
	for p: Vector3 in points:
		var c: Vector3 = inv * p
		lo = lo.min(c)
		hi = hi.max(c)
	var w: float = (hi.x - lo.x) * 1.04
	var h: float = (hi.y - lo.y) * 1.04
	var vp: Vector2 = Vector2(root.get_visible_rect().size)
	_camera.size = maxf(w, h * vp.x / vp.y)
	var centre_cam: Vector3 = Vector3((lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5, hi.z + 100.0)
	_camera.transform = Transform3D(basis, basis * centre_cam)
	for i: int in 30:
		await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	var px_per_m: float = image.get_width() / _camera.size
	var cw: int = mini(image.get_width(), int(ceil(w * px_per_m)))
	var ch: int = mini(image.get_height(), int(ceil(h * px_per_m)))
	var rect := Rect2i((image.get_width() - cw) / 2, (image.get_height() - ch) / 2, cw, ch)
	return image.get_region(rect)


## The title across the top, the rows under it, each scaled to the sheet's width (at most ROW_MAX_H high), centred.
func _sheet(title: Image, crops: Array[Image]) -> Image:
	var scaled: Array[Image] = []
	var total: int = title.get_height() + GAP
	for c: Image in crops:
		var k: float = minf(float(SHEET_W) / c.get_width(), float(ROW_MAX_H) / c.get_height())
		var img: Image = c.duplicate() as Image
		img.resize(maxi(1, int(c.get_width() * k)), maxi(1, int(c.get_height() * k)), Image.INTERPOLATE_LANCZOS)
		scaled.append(img)
		total += img.get_height() + GAP
	var sheet: Image = Image.create_empty(SHEET_W, total, false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.97, 0.97, 0.97))
	sheet.blit_rect(title, Rect2i(Vector2i.ZERO, title.get_size()), Vector2i.ZERO)
	var y: int = title.get_height() + GAP
	for img: Image in scaled:
		sheet.blit_rect(img, Rect2i(Vector2i.ZERO, img.get_size()), Vector2i((SHEET_W - img.get_width()) / 2, y))
		y += img.get_height() + GAP
	return sheet


## The title strip: the window's Label over an empty view, grabbed and cropped to the label.
func _title_image(text: String) -> Image:
	_title_label.text = text
	_title_label.visible = true
	_camera.transform = Transform3D(Basis.IDENTITY, Vector3(-ROW_SPACING_X, -1000.0, 0.0))
	for i: int in 10:
		await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	_title_label.visible = false
	var size: Vector2i = Vector2i(_title_label.get_combined_minimum_size()) + Vector2i(24, 12)
	return image.get_region(Rect2i(Vector2i.ZERO, size.min(image.get_size())))


func _v(a: Array) -> Vector3:
	return Vector3(a[0], a[1], a[2])


func _save(image: Image, path: String) -> void:
	var error: Error = image.save_png(path)
	if error != OK:
		_fail("cannot save %s: %s" % [path, error_string(error)])


func _fail(why: String) -> void:
	printerr("LINEUP error %s" % why)
	quit(1)
