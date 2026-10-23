extends SceneTree
## The pilot heads on the shared body (art #196, B1) in an off-screen window (the runner's _godot.window();
## tools/blender/alien_char_run.py stages the GLBs and writes the job): per head
## - gate_<head>.jpg: the approved static v5 head (placed by the build's fit) | the welded head at rest, from the
##   front, left, back and right in an orthographic view, the pixel diff over the rows above the neck's morph band (the cut + NECK_BAND);
## - turn_<head>.jpg: front, 3/4, side, back under the studio light, two colour presets (E1, the build's own paint,
##   and the job's preset), the standing idle's first frame, the head at rest;
## - seam_<head>.jpg: the neck seam close (a 0.16 m frame) from the four sides;
## - lineup_<head>.jpg: the 2D bust | the 3D at the bust's 3/4 framing | the whole character;
## - video/char_<head>/0000.png...: 20 s, 1280x720, the idle clip, the head following a light ball, the springs;
## shots.json: the gate numbers, the springs' largest swing.
## Args after "--": <job.json>

const Offscreen = preload("res://lib/offscreen.gd")
const AlienStatic = preload("res://alien/alien_static.gd")
const Lively = preload("res://alien/alien_lively.gd")
const BACKGROUND: Color = Color(0.45, 0.46, 0.48)
const CELL: Vector2i = Vector2i(320, 640)
const SQ: Vector2i = Vector2i(320, 320)
const FPS := 24.0

var _cam: Camera3D
var _marker: MeshInstance3D


func _initialize() -> void:
	var placed: String = Offscreen.place()  # first (#214)
	if placed != "":
		printerr(placed)
		quit(2)
		return
	_run.call_deferred()


func _texture(path: String) -> Texture2D:
	var img: Image = Image.load_from_file(path) if FileAccess.file_exists(path) else null
	if img == null or img.is_empty():
		return null
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _col(a: Array) -> Color:
	return Color(float(a[0]), float(a[1]), float(a[2]))


func _setup(node: Node3D, h: Dictionary, body: bool) -> Array[ShaderMaterial]:
	var b: Dictionary = h["bases"]
	var bases := {"lips": _col(b["lips"]), "detail": _col(b["detail"]), "front": _col(b["front"])}
	var mats: Array[ShaderMaterial] = AlienStatic.apply(node, AlienStatic.data_texture(h["mask"]), _col(b["skin"]),
		_texture(h["detail"]), _texture(h["plain"]), null, AlienStatic.data_texture(h["accent"]), bases,
		AlienStatic.data_texture(h["gill"]))
	if mats.is_empty():
		return mats
	for k: String in (h["params"] as Dictionary):
		mats[0].set_shader_parameter(k, h["params"][k])
	if body:
		mats.append_array(AlienStatic.apply_body(node, mats[0], AlienStatic.data_texture(h["body_mask"]),
			AlienStatic.data_texture(h["body_accent"])))
	for sm: ShaderMaterial in mats:
		for k: String in (h["params"] as Dictionary):
			sm.set_shader_parameter(k, h["params"][k])
	return mats


func _anim(node: Node) -> AnimationPlayer:
	var found := node.find_children("*", "AnimationPlayer", true, false)
	if found.is_empty():
		return null
	var ap: AnimationPlayer = found[0]
	for n: String in ap.get_animation_list():
		if n.get_slice("|", n.get_slice_count("|") - 1).to_lower() in ["idle", "idle_loop"]:  # not Crouch_Idle
			ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
			ap.play(n)
			ap.get_animation(n).loop_mode = Animation.LOOP_LINEAR
			return ap
	return null


func _run() -> void:
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	var out: String = job["out"]
	_stage(job["hdri"])
	var report := {}
	for name: String in (job["heads"] as Dictionary):
		var h: Dictionary = job["heads"][name]
		var char_scene: PackedScene = load(h["char"])
		var static_scene: PackedScene = load(h["static"])
		var lively: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(h["lively"]))
		var sclera: Texture2D = _texture(h["sclera"])
		if char_scene == null or static_scene == null or lively == null or sclera == null:
			printerr("CHAR %s: cannot load the GLBs, lively.json or sclera" % name)
			quit(3)
			return
		var ch: Node3D = char_scene.instantiate()
		var st: Node3D = static_scene.instantiate()
		root.add_child(ch)
		root.add_child(st)
		var fit: Dictionary = h["fit"]
		var s: float = fit["scale"]
		var src := Vector3(fit["src"][0], fit["src"][2], -fit["src"][1])
		var dst := Vector3(fit["dst"][0], fit["dst"][2], -fit["dst"][1])
		st.scale = Vector3.ONE * s
		st.position = dst - src * s
		var mats := _setup(ch, h, true)
		var smats := _setup(st, h, false)
		if mats.size() < 2 or smats.is_empty():
			printerr("CHAR %s: materials %d/%d (head + body expected)" % [name, mats.size(), smats.size()])
			quit(4)
			return
		var rep := {"materials": mats.size()}
		var cut: float = h["cut_z"]
		var band: float = h["band"]
		var top: float = fit["top_z"]
		var axis := Vector3(dst.x, 0.0, dst.z)
		# the gate: static v5 vs the welded head, both at rest, no gaze, no pose (the rest skeleton)
		var gate := {}
		var gcells: Array[Image] = []
		var hc := Vector3(axis.x, (cut + top) * 0.5, axis.z)
		var span: float = (top - cut) * 1.25
		for yaw: float in [0.0, 90.0, 180.0, 270.0]:
			ch.visible = false
			st.visible = true
			var a_img: Image = await _ortho(hc, span, yaw)
			ch.visible = true
			st.visible = false
			var b_img: Image = await _ortho(hc, span, yaw)
			var rows: int = int(SQ.y * (0.5 - ((cut + band) - hc.y) / span))  # the rows above the neck's morph band
			gate[str(int(yaw))] = _diff(a_img, b_img, rows)
			gcells.append(a_img)
			gcells.append(b_img)
		st.visible = false
		rep["gate"] = gate
		_sheet(gcells, SQ, 8).save_jpg(out.path_join("gate_%s.jpg" % name), 0.92)
		print("CHAR %s gate (front, left, back, right; mean abs /255, share over 8/255, rows above the band): %s"
			% [name, JSON.stringify(gate)])
		# the lively controller on the whole character; the idle clip
		var live = Lively.new(ch, mats, lively, sclera)
		var mid: Vector3 = (Lively._v(lively["eyes"]["left"]["centre"]) + Lively._v(lively["eyes"]["right"]["centre"])) * 0.5
		var ap := _anim(ch)
		rep["idle"] = ap.current_animation if ap != null else "none (rest pose)"
		live.target = mid + Vector3(0.0, 0.0, 1000.0)
		live.head_follow = 0.0
		live.breathing = 0.0
		for _i: int in 24:
			if ap != null:
				ap.advance(0.0)
			live.step(1.0 / FPS)
		# turnarounds, two presets
		var tcells: Array[Image] = []
		var body_c := Vector3(axis.x, top * 0.5, axis.z)
		var presets: Array = [0, int(h["preset"])]
		for pi: int in presets:
			AlienStatic.set_colours(mats, AlienStatic.PRESETS[pi]["picks"])
			for yaw: float in [0.0, 35.0, 90.0, 180.0]:
				tcells.append(await _cell(body_c, top * 1.06, yaw, CELL))
		rep["presets"] = [AlienStatic.PRESETS[presets[0]]["name"], AlienStatic.PRESETS[presets[1]]["name"]]
		AlienStatic.set_colours(mats, {})
		_sheet(tcells, CELL, 4).save_jpg(out.path_join("turn_%s.jpg" % name), 0.92)
		# the seam close
		var scells: Array[Image] = []
		var sc := Vector3(axis.x, cut, axis.z)
		for yaw: float in [0.0, 90.0, 180.0, 270.0]:
			scells.append(await _cell(sc, 0.16, yaw, SQ))
		_sheet(scells, SQ, 4).save_jpg(out.path_join("seam_%s.jpg" % name), 0.92)
		# the line-up: the 2D bust | the 3D bust at 3/4 | the whole character
		var two: Image = Image.load_from_file(h["sheet2d"])
		two.convert(Image.FORMAT_RGB8)
		two.resize(CELL.y * two.get_width() / two.get_height(), CELL.y, Image.INTERPOLATE_LANCZOS)
		var bust_h: float = (top - cut) * 1.9
		var bust: Image = await _cell(Vector3(axis.x, top - bust_h * 0.5, axis.z), bust_h, 38.0,
			Vector2i(two.get_width(), CELL.y))
		var whole: Image = await _cell(body_c, top * 1.06, 38.0, CELL)
		var lw: int = two.get_width() * 2 + CELL.x + 8
		var line := Image.create(lw, CELL.y, false, Image.FORMAT_RGB8)
		line.fill(Color(0.2, 0.2, 0.2))
		line.blit_rect(two, Rect2i(Vector2i.ZERO, two.get_size()), Vector2i.ZERO)
		line.blit_rect(bust, Rect2i(Vector2i.ZERO, bust.get_size()), Vector2i(two.get_width() + 4, 0))
		line.blit_rect(whole, Rect2i(Vector2i.ZERO, whole.get_size()), Vector2i(two.get_width() * 2 + 8, 0))
		line.save_jpg(out.path_join("lineup_%s.jpg" % name), 0.92)
		# the video
		var seconds: float = job["seconds"]
		live.head_follow = 1.0
		live.breathing = 1.0
		_marker.visible = true
		var best := 0.0
		if seconds > 0.0:
			var dir: String = out.path_join("video").path_join("char_" + name)
			DirAccess.make_dir_recursive_absolute(dir)
			var vc := Vector3(axis.x, top - 0.62, axis.z)
			for i: int in int(seconds * FPS):
				var t: float = i / FPS
				live.target = _path(mid, t)
				_marker.position = live.target
				if ap != null:
					ap.advance(1.0 / FPS)
				live.step(1.0 / FPS)
				for sp: Dictionary in live.springs:
					var sv: Vector4 = sp["s"]
					best = maxf(best, rad_to_deg(maxf(absf(sv.x), absf(sv.y))))
				var img: Image = await _frame(vc, 1.3, 30.0)
				img.save_png(dir.path_join("%04d.png" % i))
		_marker.visible = false
		rep["spring_swing_max_deg"] = snappedf(best, 0.01)
		report[name] = rep
		print("CHAR %s %s" % [name, JSON.stringify(rep)])
		ch.queue_free()
		st.queue_free()
		await process_frame
	var f := FileAccess.open(out.path_join("shots.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, " "))
	f.close()
	print("CHAR done")
	quit(0)


func _path(mid: Vector3, t: float) -> Vector3:
	var keys := [[0.0, Vector3(0, 0, 3)], [1.5, Vector3(0, 0, 3)], [2.7, Vector3(2.0, 0.15, 2.4)], [4.6, Vector3(2.0, 0.15, 2.4)],
		[6.0, Vector3(-2.0, 0.0, 2.4)], [8.0, Vector3(-2.0, 0.0, 2.4)], [9.2, Vector3(0.3, 1.3, 2.6)], [11.0, Vector3(0.3, 1.3, 2.6)],
		[12.2, Vector3(-0.2, -1.1, 2.6)], [13.6, Vector3(-0.2, -1.1, 2.6)], [14.8, Vector3(0.05, -0.08, 0.8)],
		[16.6, Vector3(0.05, -0.08, 0.8)], [17.1, Vector3(2.4, 0.2, 2.0)], [17.6, Vector3(-2.4, 0.2, 2.0)],
		[18.1, Vector3(2.4, 0.2, 2.0)], [19.0, Vector3(0, 0, 3)], [99.0, Vector3(0, 0, 3)]]
	for k: int in keys.size() - 1:
		if t < keys[k + 1][0]:
			return mid + (keys[k][1] as Vector3).lerp(keys[k + 1][1], smoothstep(keys[k][0], keys[k + 1][0], t))
	return mid + Vector3(0, 0, 3)


func _diff(x: Image, y: Image, rows: int) -> Dictionary:
	var sum := 0.0
	var over := 0
	var n := 0
	var differ := 0
	for j: int in clampi(rows, 0, x.get_height()):
		for i: int in x.get_width():
			var p: Color = x.get_pixel(i, j)
			var q: Color = y.get_pixel(i, j)
			var d: float = maxf(absf(p.r - q.r), maxf(absf(p.g - q.g), absf(p.b - q.b)))
			sum += (absf(p.r - q.r) + absf(p.g - q.g) + absf(p.b - q.b)) / 3.0
			over += 1 if d > 8.0 / 255.0 else 0
			n += 1
	return {"mean_abs": snappedf(sum / maxf(n, 1) * 255.0, 0.001), "share_over_8": snappedf(float(over) / maxf(n, 1), 0.00001),
		"rows": rows}


func _sheet(cells: Array[Image], size: Vector2i, cols: int) -> Image:
	var rows: int = (cells.size() + cols - 1) / cols
	var img := Image.create(cols * (size.x + 4) - 4, rows * (size.y + 4) - 4, false, Image.FORMAT_RGB8)
	img.fill(Color(0.2, 0.2, 0.2))
	for i: int in cells.size():
		img.blit_rect(cells[i], Rect2i(Vector2i.ZERO, size), Vector2i((i % cols) * (size.x + 4), (i / cols) * (size.y + 4)))
	if img.get_width() > 1280:
		img.resize(1280, img.get_height() * 1280 / img.get_width(), Image.INTERPOLATE_LANCZOS)
	return img


func _grab(size: Vector2i) -> Image:
	for _i: int in 6:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	var hh: int = img.get_height()
	var w: int = mini(img.get_width(), hh * size.x / size.y)
	var c: Image = img.get_region(Rect2i((img.get_width() - w) / 2, 0, w, hh))
	c.resize(size.x, size.y, Image.INTERPOLATE_LANCZOS)
	return c


## A cell: a perspective camera at yaw (degrees) toward c framing height h.
func _cell(c: Vector3, h: float, yaw_deg: float, size: Vector2i) -> Image:
	_cam.projection = Camera3D.PROJECTION_PERSPECTIVE
	var yaw := deg_to_rad(yaw_deg)
	var dist: float = h * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
	_cam.position = c + Vector3(sin(yaw), 0.04, cos(yaw)).normalized() * dist
	_cam.look_at(c)
	return await _grab(size)


func _ortho(c: Vector3, h: float, yaw_deg: float) -> Image:
	_cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	_cam.size = h
	var yaw := deg_to_rad(yaw_deg)
	_cam.position = c + Vector3(sin(yaw), 0.0, cos(yaw)) * 6.0
	_cam.look_at(c)
	var img: Image = await _grab(SQ)
	_cam.projection = Camera3D.PROJECTION_PERSPECTIVE
	return img


func _frame(c: Vector3, h: float, yaw_deg: float) -> Image:
	var yaw := deg_to_rad(yaw_deg)
	var dist: float = h * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
	_cam.position = c + Vector3(sin(yaw), 0.05, cos(yaw)).normalized() * dist
	_cam.look_at(c)
	await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	return img


func _stage(hdri: String) -> void:
	root.msaa_3d = Viewport.MSAA_4X
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = BACKGROUND
	var sky := Sky.new()
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	var image: Image = Image.load_from_file(hdri) if FileAccess.file_exists(hdri) else null
	if image != null and not image.is_empty():
		var pano := PanoramaSkyMaterial.new()
		pano.panorama = ImageTexture.create_from_image(image)
		sky.sky_material = pano
	else:
		sky.sky_material = ProceduralSkyMaterial.new()
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_sky_contribution = 0.5
	env.ambient_light_color = Color(1.0, 0.8, 0.62)
	env.ambient_light_energy = 0.12
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX  # the static heads' studio (lively_shots.gd)
	env.tonemap_exposure = 0.65
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.35
	env.ssao_enabled = true
	env.ssao_radius = 0.6
	env.ssao_intensity = 1.5
	env.ssao_light_affect = 0.2
	var world := WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var key := _light(Vector3(-2.0, 3.2, 3.0), 2.0, true, 0.6)
	key.light_angular_distance = 1.5
	key.shadow_blur = 1.0
	key.directional_shadow_max_distance = 12.0
	_light(Vector3(3.0, 1.6, 2.0), 0.12, false, 0.0)
	_light(Vector3(0.5, 2.5, -3.0), 0.30, false, 0.3)
	_cam = Camera3D.new()
	_cam.fov = 22.0
	_cam.near = 0.05
	_cam.far = 2000.0
	root.add_child(_cam)
	_cam.make_current()
	_marker = MeshInstance3D.new()
	var ball := SphereMesh.new()
	ball.radius = 0.035
	ball.height = 0.07
	var lit := StandardMaterial3D.new()
	lit.emission_enabled = true
	lit.emission = Color(1.0, 0.85, 0.4)
	lit.emission_energy_multiplier = 3.0
	lit.albedo_color = Color(1.0, 0.85, 0.4)
	ball.material = lit
	_marker.mesh = ball
	_marker.visible = false
	root.add_child(_marker)


func _light(at: Vector3, energy: float, shadow: bool, specular: float) -> DirectionalLight3D:
	var light := DirectionalLight3D.new()
	root.add_child(light)
	light.look_at_from_position(at, Vector3.ZERO)
	light.light_energy = energy
	light.light_specular = specular
	light.shadow_enabled = shadow
	return light
