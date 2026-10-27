extends "res://ship/ship.gd"
## What the stations' shared bronze noise costs (art#263, fix pass 2; the review's minor 2 on #324; option A shipped):
## ship.gd's night ship with all four stations in their looks (console.gd, socket.gd, board.gd, charger.gd; no
## crystals), and per view the median GPU ms of the frame with the metal shader (console_metal.gdshader) as shipped
## (the slope from the gradient noise's exact derivative), with its dent and wave off, with one octave of the noise
## instead of two, with the slope as it shipped before option A (FINITE: the forward difference of the noise, 64
## hashes per slope), and with that view's station hidden (the station's whole cost). Rounds alternate the variants so
## a drift in the GPU's clock falls on all of them; vsync is off. Per console view (dent = wave = 0) it also shoots the
## console alone (the other stations hidden) before and after option A and records their pixel difference, which must
## be 0. Started by tools/blender/metal_cost_run.py through the runner's `_godot.window()` (one off-screen pixel grown
## to 1920x1080):
##   godot <_godot.window() flags> -s res://ship/metal_cost.gd -- <request.json> <out>
## The request is ship.gd's "shoot" request with "views": [[name, station, eye, look, fov]] and "cost": {"rounds",
## "settle", "frames"}. Writes <out>/cost.json, per view <name>__<variant>.png (the pixel check of each variant) and
## <name>__compare.png (before option A | shipped | difference x8) and <name>__compare_crop.png (its middle 1:1), per
## console view <name>__solo.png and <name>__solo_compare.png.

const Console = preload("res://console/console.gd")
const Socket = preload("res://socket/socket.gd")
const Board = preload("res://board/board.gd")
const Charger = preload("res://charger/charger.gd")
const METAL = "res://console/console_metal.gdshader"
## slope()'s second octave in the shipped shader; the one-octave variant drops the line
const TWO_OCTAVES = "\tg += 0.35 * 2.17 * (t * (t * gnoised(TURN * q * 2.17 + vec3(5.2, 1.3, 7.7)).yzw));\n"
## The slope as it shipped before option A (fix1 to 2026-10-26), put back in place of gnoised() and slope() for the
## "finite" variant: a forward difference over 0.3 of a cell of the two-octave field, four field() calls of 16 hashes
const FINITE = """float gnoise(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	vec3 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
	float x00 = mix(dot(ghash(i), f), dot(ghash(i + vec3(1.0, 0.0, 0.0)), f - vec3(1.0, 0.0, 0.0)), u.x);
	float x10 = mix(dot(ghash(i + vec3(0.0, 1.0, 0.0)), f - vec3(0.0, 1.0, 0.0)),
		dot(ghash(i + vec3(1.0, 1.0, 0.0)), f - vec3(1.0, 1.0, 0.0)), u.x);
	float x01 = mix(dot(ghash(i + vec3(0.0, 0.0, 1.0)), f - vec3(0.0, 0.0, 1.0)),
		dot(ghash(i + vec3(1.0, 0.0, 1.0)), f - vec3(1.0, 0.0, 1.0)), u.x);
	float x11 = mix(dot(ghash(i + vec3(0.0, 1.0, 1.0)), f - vec3(0.0, 1.0, 1.0)),
		dot(ghash(i + vec3(1.0, 1.0, 1.0)), f - vec3(1.0, 1.0, 1.0)), u.x);
	return mix(mix(x00, x10, u.y), mix(x01, x11, u.y), u.z);
}

float field(vec3 p, float s) {
	vec3 q = TURN * (p * s);
	return (gnoise(q) + 0.35 * gnoise(TURN * q * 2.17 + vec3(5.2, 1.3, 7.7))) * 0.69;
}

vec3 slope(vec3 p, vec3 nrm, float s) {
	float e = 0.3 / s;
	float h0 = field(p, s);
	vec3 g = vec3(field(p + vec3(e, 0.0, 0.0), s), field(p + vec3(0.0, e, 0.0), s), field(p + vec3(0.0, 0.0, e), s)) - h0;
	g /= 0.3;
	return g - nrm * dot(g, nrm);
}

"""
const PREFIX := {"console": "start_console", "socket": "crystal_socket", "board": "breaker_board",
	"charger": "crystal_charger"}

var _kinds: Dictionary = {}  # station -> its placed nodes
var _mats: Array[ShaderMaterial] = []  # every material on the shared metal shader


func _dress(ship: Node3D) -> int:
	var mine: Array[Node3D] = []
	for n: Node in ship.get_children():
		for k: String in PREFIX:
			if n.name.begins_with(PREFIX[k]):
				mine.append(n as Node3D)
				if not _kinds.has(k):
					_kinds[k] = []
				(_kinds[k] as Array).append(n)
	for c: Node3D in mine:
		ship.remove_child(c)
	var lights: int = super(ship)
	for c: Node3D in mine:
		ship.add_child(c)
	for c: Node3D in _kinds.get("console", []):
		Console.set_clock(Console.apply(c), 0.0)
	for c: Node3D in _kinds.get("socket", []):
		Socket.set_state(Socket.apply(c), "charged")
	for c: Node3D in _kinds.get("board", []):
		Board.apply(c)
	for c: Node3D in _kinds.get("charger", []):
		Charger.set_state(Charger.apply(c), "idle")
	return lights


func _collect(n: Node) -> void:
	if n is MeshInstance3D:
		var mi := n as MeshInstance3D
		var found: Array[Material] = [mi.material_override]
		for i: int in mi.get_surface_override_material_count():
			found.append(mi.get_active_material(i))
		for m: Material in found:
			if m is ShaderMaterial and (m as ShaderMaterial).shader != null \
					and (m as ShaderMaterial).shader.code.contains("uniform float wave_scale") and not _mats.has(m):
				_mats.append(m as ShaderMaterial)
	for c: Node in n.get_children():
		_collect(c)


func _shoot() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	_environment()
	var ship: Node3D = _build()
	_dress(ship)
	_stations(ship)
	_probes()
	for k: String in PREFIX:
		if not _kinds.has(k):
			_fail("no %s placed" % PREFIX[k])
			return
	_collect(root)
	var src: String = (load(METAL) as Shader).code
	if not src.contains(TWO_OCTAVES):
		_fail("the metal shader's slope() changed: no second-octave line to drop")
		return
	var one := Shader.new()
	one.code = src.replace(TWO_OCTAVES, "")
	var at: int = src.find("vec4 gnoised(")
	var end: int = src.find("void fragment()")
	if at < 0 or end < at:
		_fail("the metal shader changed: no gnoised() and slope() to replace for the finite variant")
		return
	var finite := Shader.new()
	finite.code = src.substr(0, at) + FINITE + src.substr(end)
	var alt: Dictionary = {"one_octave": one, "finite": finite}
	var shipped: Array = []  # per material: its shader and its parameters as the looks set them
	for m: ShaderMaterial in _mats:
		var p: Dictionary = {}
		for u: Dictionary in m.shader.get_shader_uniform_list():
			p[u["name"]] = m.get_shader_parameter(u["name"])
		shipped.append([m.shader, p])
	print("COST %d metal materials, %s" % [_mats.size(), JSON.stringify(_kinds.keys())])
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.far = 500.0
	root.add_child(_camera)
	_camera.make_current()
	var spec: Dictionary = _req["cost"]
	var vp: RID = root.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	var rows: Array = []
	for v: Array in _req["views"]:
		_camera.fov = float(v[4])
		_camera.look_at_from_position(_v(v[2]), _v(v[3]), UP)
		var per: Dictionary = {"shipped": [], "flat": [], "one_octave": [], "finite": [], "hidden": []}
		var images: Dictionary = {}
		for r: int in int(spec["rounds"]):
			for variant: String in per:
				_variant(variant, str(v[1]), shipped, alt)
				(per[variant] as Array).append(await _median_gpu(vp, int(spec["settle"]), int(spec["frames"])))
				if r == 0:
					var img: Image = root.get_texture().get_image()
					img.convert(Image.FORMAT_RGB8)
					img.save_png(_out.path_join("%s__%s.png" % [v[0], variant]))
					images[variant] = img
				_variant("shipped", str(v[1]), shipped, alt)
		var row: Dictionary = {"view": v[0], "station": v[1], "fov": v[4]}
		for variant: String in ["flat", "one_octave", "finite"]:  # the pixels' change against the shipped frame, 0..255
			var d: Dictionary = (images[variant] as Image).compute_image_metrics(images["shipped"], false)
			row["px_mean_" + variant] = snappedf(float(d["mean"]), 0.001)
			row["px_max_" + variant] = float(d["max"])
		for variant: String in per:
			row["gpu_ms_" + variant] = snappedf(_median(per[variant]), 0.001)
			row["rounds_" + variant] = per[variant]
		row["noise_ms"] = snappedf(row["gpu_ms_shipped"] - row["gpu_ms_flat"], 0.001)
		row["octave2_ms"] = snappedf(row["gpu_ms_shipped"] - row["gpu_ms_one_octave"], 0.001)
		row["station_ms"] = snappedf(row["gpu_ms_shipped"] - row["gpu_ms_hidden"], 0.001)
		row["saves_ms"] = snappedf(row["gpu_ms_finite"] - row["gpu_ms_shipped"], 0.001)
		_compare(images["finite"], images["shipped"]).save_png(_out.path_join("%s__compare.png" % v[0]))
		_compare(images["finite"], images["shipped"], true).save_png(_out.path_join("%s__compare_crop.png" % v[0]))
		if str(v[1]) == "console":  # the control: dent = wave = 0, so option A must leave its pixels alone
			var solo: Dictionary = {}
			for variant: String in ["finite", "shipped"]:
				_variant(variant, "console", shipped, alt)
				for k: String in _kinds:
					for n: Node3D in _kinds[k]:
						n.visible = k == "console"
				await _median_gpu(vp, int(spec["settle"]), 4)
				var img: Image = root.get_texture().get_image()
				img.convert(Image.FORMAT_RGB8)
				solo[variant] = img
			for k: String in _kinds:
				for n: Node3D in _kinds[k]:
					n.visible = true
			_variant("shipped", "console", shipped, alt)
			var sd: Dictionary = (solo["finite"] as Image).compute_image_metrics(solo["shipped"], false)
			row["solo_px_max"] = float(sd["max"])
			row["solo_identical"] = (solo["finite"] as Image).get_data() == (solo["shipped"] as Image).get_data()
			(solo["shipped"] as Image).save_png(_out.path_join("%s__solo.png" % v[0]))
			_compare(solo["finite"], solo["shipped"]).save_png(_out.path_join("%s__solo_compare.png" % v[0]))
		rows.append(row)
		print("COST %s" % JSON.stringify(row))
	var f := FileAccess.open(_out.path_join("cost.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"size": [root.size.x, root.size.y], "spec": spec,
		"adapter": RenderingServer.get_video_adapter_name(), "views": rows}, "  ") + "\n")
	f.close()
	print("COST wrote %s" % _out.path_join("cost.json"))
	quit(0)


## The same view before option A (finite) and as shipped side by side at 640x360 each, and their difference x8: the
## whole frame scaled down, or with `crop` the 640x360 pixels at the frame's middle 1:1 (the close-up check).
func _compare(before: Image, after: Image, crop: bool = false) -> Image:
	var size := Vector2i(640, 360)
	var a: Image = before.duplicate()
	var b: Image = after.duplicate()
	if crop:
		var at := Rect2i((Vector2i(a.get_width(), a.get_height()) - size) / 2, size)
		a = a.get_region(at)
		b = b.get_region(at)
	else:
		a.resize(size.x, size.y, Image.INTERPOLATE_BILINEAR)
		b.resize(size.x, size.y, Image.INTERPOLATE_BILINEAR)
	var diff := Image.create(size.x, size.y, false, Image.FORMAT_RGB8)
	for y: int in size.y:
		for x: int in size.x:
			var ca: Color = a.get_pixel(x, y)
			var cb: Color = b.get_pixel(x, y)
			var dv: float = minf(1.0, 8.0 * (absf(ca.r - cb.r) + absf(ca.g - cb.g) + absf(ca.b - cb.b)) / 3.0)
			diff.set_pixel(x, y, Color(dv, dv, dv))
	var out := Image.create(size.x * 3 + 8, size.y, false, Image.FORMAT_RGB8)
	out.fill(Color(0, 0, 0))
	out.blit_rect(a, Rect2i(Vector2i.ZERO, size), Vector2i(0, 0))
	out.blit_rect(b, Rect2i(Vector2i.ZERO, size), Vector2i(size.x + 4, 0))
	out.blit_rect(diff, Rect2i(Vector2i.ZERO, size), Vector2i(size.x * 2 + 8, 0))
	return out


## One variant on every metal material (and the view's station shown or hidden).
func _variant(variant: String, station: String, shipped: Array, alt: Dictionary) -> void:
	for i: int in _mats.size():
		var m: ShaderMaterial = _mats[i]
		m.shader = alt[variant] if alt.has(variant) else shipped[i][0]
		var p: Dictionary = shipped[i][1]
		for k: String in p:
			m.set_shader_parameter(k, p[k])
		if variant == "flat":
			m.set_shader_parameter("dent", 0.0)
			m.set_shader_parameter("wave", 0.0)
	for n: Node3D in _kinds[station]:
		n.visible = variant != "hidden"


func _median_gpu(vp: RID, settle: int, frames: int) -> float:
	for _i: int in settle:
		await RenderingServer.frame_post_draw
	var gpu: Array[float] = []
	for _i: int in frames:
		await RenderingServer.frame_post_draw
		gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(vp))
	return snappedf(_median(gpu), 0.0001)


func _median(values: Array) -> float:
	var s: Array = values.duplicate()
	s.sort()
	var n: int = s.size()
	return (float(s[n / 2]) + float(s[(n - 1) / 2])) * 0.5
