extends "res://lobby/hall.gd"
## The lobby's pinball machine in our hall (art #374): hall.gd's scene (the hall, the ship and the light of
## `lobby --shoot`) with the cabinet placed by the request ("place": ["pinball", origin, 0]), the table's art under its
## TableMount marker and three placeholder Label3D lines on its Display marker. Started only by
## tools/blender/pinball_run.py through `_godot.window()` (CLAUDE.md, #214), never by hand.
## mode "shoot": <out>/<view>.png, sheet.png (the concept beside the 3/4 front), closeups.png (Gate 3's close-ups:
##   c_corner, c_foot, c_medallion, c_side, c_field), drawing*.png (the drawing's SVGs
##   rasterised), shots.json. mode "video": <out>/frames/%05d.png from the CloseUp marker's camera (the flippers at the
##   contract's swing and speed, a ball on a scripted path), video.json.
## request "pinball": {"table", "concept", "spot", "origin", "fov", "lines", "swing_deg", "speed_deg_s", "rest_deg",
##   "ball_r", "svgs", "video": {"size", "fps", "seconds"}}.

var _pb: Dictionary
var _cab: Node3D
var _mount: Node3D
var _table: Node3D
var _ball: MeshInstance3D

# The ball's scripted path in the table frame: [x, z, seconds]; the flippers' flicks: [node, start seconds].
const PATH: Array = [[0.20, 0.25, 0.0], [0.27, 0.0, 0.35], [0.25, -0.45, 0.85], [0.08, -0.56, 1.15],
	[-0.04, -0.33, 1.6], [-0.20, -0.05, 2.1], [-0.073, 0.432, 2.6], [0.0, -0.20, 3.3], [0.0, -0.53, 3.75],
	[0.16, -0.36, 4.3], [0.20, 0.10, 4.9], [0.073, 0.432, 5.4], [-0.05, -0.15, 6.1], [-0.20, -0.45, 6.7],
	[-0.27, -0.10, 7.3], [-0.16, 0.25, 8.0], [-0.073, 0.432, 8.5], [0.10, -0.30, 9.3], [0.22, -0.52, 10.0]]
const FLICKS: Array = [["FlipperLeft", 2.56], ["FlipperRight", 5.36], ["FlipperRight", 7.0], ["FlipperLeft", 8.46]]
const HOLD_S: float = 0.18


func _shoot() -> void:
	_pinball_scene()
	var shots: Dictionary = {}
	var images: Dictionary = {}
	var o: Vector3 = _v(_pb["origin"])
	var spot: Vector3 = _v(_pb["spot"])
	var views: Array = [
		["q34", "3/4 front (the concept's side)", o + Vector3(1.45, 1.75, -2.05), o + Vector3(0, 0.9, 0.05), 45.0],
		["side", "side, from the hall", o + Vector3(-2.9, 1.25, 0.1), o + Vector3(0, 0.95, 0.1), 50.0],
		["eye", "the player's eye at the spawn (1.65 m)", spot + Vector3(0, 1.65, 0), o + Vector3(0, 0.95, 0.0), 75.0],
		["backbox", "the backbox close-up", o + Vector3(0.0, 1.62, -0.75), o + Vector3(0, 1.60, 0.6), 45.0],
		["hall", "in the hall: the east wall, its pilasters and door D2", o + Vector3(-5.5, 2.4, -4.5), o + Vector3(0.6, 0.9, 0.2), 55.0],
	]
	for v: Array in views:
		_camera.fov = float(v[4])
		_camera.look_at_from_position(v[2], v[3], Vector3.UP)
		images[v[0]] = await _shot(v[0], v[1], shots)
	var cu: Node3D = _cab.find_child("CloseUp", true, false) as Node3D
	_camera.global_transform = cu.global_transform
	_camera.fov = float(_pb["fov"])
	images["closeup"] = await _shot("closeup", "the CloseUp marker's camera (fov %d)" % int(_pb["fov"]), shots)
	# Gate 3's close-ups (step 2): a copper corner with rivets, a foot with its rings, the front medallion, the side
	# art, the playfield under the glass; closeups.png
	var close: Array = [
		["c_corner", "copper corner, rivets", o + Vector3(0.62, 1.18, -1.22), o + Vector3(0.40, 0.96, -0.84), 30.0],
		["c_foot", "a front foot, its two rings", o + Vector3(0.78, 0.26, -1.30), o + Vector3(0.38, 0.07, -0.78), 25.0],
		["c_medallion", "the front medallion", o + Vector3(0.12, 0.86, -1.42), o + Vector3(0.0, 0.80, -0.84), 28.0],
		["c_side", "the side art", o + Vector3(-1.75, 1.00, -0.05), o + Vector3(-0.41, 0.80, 0.10), 40.0],
		["c_field", "the playfield under the glass", o + Vector3(0.08, 1.55, -0.78), o + Vector3(0.0, 0.98, -0.08), 50.0],
	]
	var cimg: Array = []
	for v: Array in close:
		_camera.fov = float(v[4])
		_camera.look_at_from_position(v[2], v[3], Vector3.UP)
		cimg.append(await _shot(v[0], v[1], shots))
	_save(_sheet([[cimg[0], cimg[1]], [cimg[2], cimg[3]], [cimg[4]]]), _out.path_join("closeups.png"))
	var concept: Image = Image.load_from_file(_pb["concept"])
	concept.convert(Image.FORMAT_RGB8)
	_save(_sheet([[concept, images["q34"]], [images["side"], images["eye"]], [images["closeup"], images["backbox"]],
		[images["hall"]]]), _out.path_join("sheet.png"))
	for svg: String in _pb["svgs"]:
		var img: Image = Image.new()
		if img.load_svg_from_string(FileAccess.get_file_as_string(svg), 1.0) == OK:
			_save(img, _out.path_join(svg.get_file().get_basename() + ".png"))
		else:
			print("PINBALL cannot rasterise %s" % svg)
	var probe: Dictionary = {}
	for n: String in ["TableMount", "CloseUp", "Display"]:
		var m: Node3D = _cab.find_child(n, true, false) as Node3D
		probe[n] = [m.global_position.x, m.global_position.y, m.global_position.z]
	var bodies: Array = []
	for c: Node in _table.get_children():
		bodies.append(c.name)
	_write("shots.json", {"shots": shots, "markers": probe, "table_nodes": bodies})
	print("PINBALL shots %d, markers %s, table nodes %s" % [shots.size(), probe, bodies])
	quit(0)


func _video() -> void:
	_pinball_scene()
	_label.visible = false
	var v: Dictionary = _pb["video"]
	var cu: Node3D = _cab.find_child("CloseUp", true, false) as Node3D
	_camera.fov = float(_pb["fov"])
	var fps: float = float(v["fps"])
	var count: int = int(float(v["seconds"]) * fps)
	var dir: String = _out.path_join("frames")
	DirAccess.make_dir_recursive_absolute(dir)
	_animate(0.0)
	for i: int in 40:
		await process_frame
	var started: int = Time.get_ticks_msec()
	var gpu: Array = []
	var peak: Dictionary = {}
	var cams: Array = []
	for f: int in count:
		var t: float = f / fps
		_animate(t)
		_camera.global_transform = cu.global_transform   # every frame: nothing else may move it
		if f % 90 == 0:
			cams.append([f, _camera.global_position, -_camera.global_basis.z])
		for fl: String in ["FlipperLeft", "FlipperRight"]:
			var deg: float = (_table.find_child(fl, true, false) as Node3D).rotation_degrees.y
			peak[fl] = [minf(peak.get(fl, [deg, deg])[0], deg), maxf(peak.get(fl, [deg, deg])[1], deg)]
		await RenderingServer.frame_post_draw
		gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(root.get_viewport_rid()))
		var image: Image = root.get_texture().get_image()
		image.convert(Image.FORMAT_RGB8)
		_save(image, dir.path_join("%05d.png" % f))
	_write("video.json", {"frames": count, "fps": fps, "seconds": count / fps, "gpu_ms": _median(gpu),
		"render_s": (Time.get_ticks_msec() - started) / 1000.0, "flipper_deg_range": peak, "camera": str(cams),
		"closeup": str(cu.global_transform)})
	print("PINBALL video %d frames, flippers %s" % [count, peak])
	quit(0)


## The cabinet's table, display and ball, after hall.gd's scene.
func _pinball_scene() -> void:
	_pb = _req["pinball"]
	_setup_scene()
	_cab = _placed["pinball"][0]
	_mount = _cab.find_child("TableMount", true, false) as Node3D
	var display: Node3D = _cab.find_child("Display", true, false) as Node3D
	if _mount == null or display == null:
		_fail("pinball.glb has no TableMount or Display")
		return
	_table = (load(_pb["table"]) as PackedScene).instantiate() as Node3D
	_table.name = "PinballTable"
	_mount.add_child(_table)
	var lines: Array = _pb["lines"]
	for i: int in lines.size():
		var l: Label3D = Label3D.new()
		l.text = lines[i]
		l.font_size = 72
		l.pixel_size = 0.0009
		l.outline_size = 0
		l.modulate = Color(0.55, 0.97, 1.0) if i != 1 else Color(1.0, 0.78, 0.45)
		l.shaded = false
		l.position = Vector3(0, 0.11 * (1 - i), 0)
		display.add_child(l)
	_ball = MeshInstance3D.new()
	var s: SphereMesh = SphereMesh.new()
	s.radius = float(_pb["ball_r"])
	s.height = 2.0 * s.radius
	_ball.mesh = s
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.albedo_color = Color(0.9, 0.9, 0.92)
	m.metallic = 1.0
	m.roughness = 0.08
	_ball.material_override = m
	_mount.add_child(_ball)
	_animate(0.0)


## The scene at t seconds: the ball on its Catmull-Rom path, rolling; each flipper up at the contract's speed, held,
## and back.
func _animate(t: float) -> void:
	var k: int = 0
	while k < PATH.size() - 2 and t > float(PATH[k + 1][2]):
		k += 1
	var gap: float = float(PATH[k + 1][2]) - float(PATH[k][2])
	var w: float = clampf((t - float(PATH[k][2])) / gap, 0.0, 1.0)
	var p: Vector2 = _cr2(k, w)
	var r: float = float(_pb["ball_r"])
	var prev: Vector3 = _ball.position
	_ball.position = Vector3(p.x, r, p.y)
	var d: Vector3 = _ball.position - prev
	if d.length() > 1e-5 and d.length() < 0.5:
		_ball.rotate(Vector3.UP.cross(d).normalized(), d.length() / r)
	var swing: float = float(_pb["swing_deg"])
	var speed: float = float(_pb["speed_deg_s"])
	var rest: float = float(_pb["rest_deg"])
	for fl: String in ["FlipperLeft", "FlipperRight"]:
		var up: float = 0.0
		for f: Array in FLICKS:
			if f[0] != fl:
				continue
			var dt: float = t - float(f[1])
			var rise: float = swing / speed
			if dt >= 0.0 and dt < rise + HOLD_S + rise:
				up = maxf(up, minf(dt * speed, swing) if dt < rise + HOLD_S else maxf(swing - (dt - rise - HOLD_S) * speed, 0.0))
		var side: float = -1.0 if fl == "FlipperLeft" else 1.0
		(_table.find_child(fl, true, false) as Node3D).rotation_degrees.y = side * (rest - up)


func _cr2(k: int, w: float) -> Vector2:
	var n: int = PATH.size()
	var a: Array = [PATH[maxi(k - 1, 0)], PATH[k], PATH[mini(k + 1, n - 1)], PATH[mini(k + 2, n - 1)]]
	var q: Array = a.map(func(e: Array) -> Vector2: return Vector2(float(e[0]), float(e[1])))
	var w2: float = w * w
	var w3: float = w2 * w
	return 0.5 * ((2.0 * q[1]) + (q[2] - q[0]) * w + (2.0 * q[0] - 5.0 * q[1] + 4.0 * q[2] - q[3]) * w2
		+ (3.0 * q[1] - q[0] - 3.0 * q[2] + q[3]) * w3)
