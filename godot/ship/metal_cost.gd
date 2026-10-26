extends "res://ship/ship.gd"
## What the stations' shared bronze noise costs (art#263, fix pass 2; the review's minor 2 on #324): ship.gd's night
## ship with all four stations in their looks (console.gd, socket.gd, board.gd, charger.gd; no crystals), and per view
## the median GPU ms of the frame with the metal shader (console_metal.gdshader) as shipped, with its dent and wave
## off, with one octave of the gradient noise instead of two, and with that view's station hidden (the station's whole
## cost). Rounds alternate the variants so a drift in the GPU's clock falls on all of them; vsync is off. Started by
## tools/blender/metal_cost_run.py through the runner's `_godot.window()` (one off-screen pixel grown to 1920x1080):
##   godot <_godot.window() flags> -s res://ship/metal_cost.gd -- <request.json> <out>
## The request is ship.gd's "shoot" request with "views": [[name, station, eye, look, fov]] and "cost": {"rounds",
## "settle", "frames"}. Writes <out>/cost.json and per view <name>__<variant>.png (the pixel check of each variant).

const Console = preload("res://console/console.gd")
const Socket = preload("res://socket/socket.gd")
const Board = preload("res://board/board.gd")
const Charger = preload("res://charger/charger.gd")
const METAL = "res://console/console_metal.gdshader"
const TWO_OCTAVES = "return (gnoise(q) + 0.35 * gnoise(TURN * q * 2.17 + vec3(5.2, 1.3, 7.7))) * 0.69;"
const ONE_OCTAVE = "return gnoise(q) * 0.69;"
## The proposal measured beside the shipped shader (not shipped): slope() from the gradient noise's analytic
## derivative, one pass of 8 hashes per octave instead of four field() calls of 16 each; the same lattice, hashes,
## fade, turns and strengths (the shipped forward difference over 0.3 of a cell is the derivative divided by s, taken
## at its midpoint).
const ANALYTIC = """vec4 gnoised(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	vec3 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
	vec3 du = 30.0 * f * f * (f * (f - 2.0) + 1.0);
	vec3 ga = ghash(i);
	vec3 gb = ghash(i + vec3(1.0, 0.0, 0.0));
	vec3 gc = ghash(i + vec3(0.0, 1.0, 0.0));
	vec3 gd = ghash(i + vec3(1.0, 1.0, 0.0));
	vec3 ge = ghash(i + vec3(0.0, 0.0, 1.0));
	vec3 gf = ghash(i + vec3(1.0, 0.0, 1.0));
	vec3 gg = ghash(i + vec3(0.0, 1.0, 1.0));
	vec3 gh = ghash(i + vec3(1.0, 1.0, 1.0));
	float va = dot(ga, f);
	float vb = dot(gb, f - vec3(1.0, 0.0, 0.0));
	float vc = dot(gc, f - vec3(0.0, 1.0, 0.0));
	float vd = dot(gd, f - vec3(1.0, 1.0, 0.0));
	float ve = dot(ge, f - vec3(0.0, 0.0, 1.0));
	float vf = dot(gf, f - vec3(1.0, 0.0, 1.0));
	float vg = dot(gg, f - vec3(0.0, 1.0, 1.0));
	float vh = dot(gh, f - vec3(1.0, 1.0, 1.0));
	float v = va + u.x * (vb - va) + u.y * (vc - va) + u.z * (ve - va) + u.x * u.y * (va - vb - vc + vd)
		+ u.y * u.z * (va - vc - ve + vg) + u.z * u.x * (va - vb - ve + vf)
		+ u.x * u.y * u.z * (-va + vb + vc - vd + ve - vf - vg + vh);
	vec3 d = ga + u.x * (gb - ga) + u.y * (gc - ga) + u.z * (ge - ga) + u.x * u.y * (ga - gb - gc + gd)
		+ u.y * u.z * (ga - gc - ge + gg) + u.z * u.x * (ga - gb - ge + gf)
		+ u.x * u.y * u.z * (-ga + gb + gc - gd + ge - gf - gg + gh)
		+ du * (vec3(vb - va, vc - va, ve - va) + u.yzx * vec3(va - vb - vc + vd, va - vc - ve + vg, va - vb - ve + vf)
		+ u.zxy * vec3(va - vb - ve + vf, va - vb - vc + vd, va - vc - ve + vg)
		+ u.yzx * u.zxy * (-va + vb + vc - vd + ve - vf - vg + vh));
	return vec4(v, d);
}

vec3 slope(vec3 p, vec3 nrm, float s) {
	vec3 q = TURN * ((p + vec3(0.15 / s)) * s);  // the shipped forward difference's midpoint: its glints stay put
	vec3 r = TURN * q * 2.17 + vec3(5.2, 1.3, 7.7);
	mat3 t = transpose(TURN);
	vec3 g = (t * gnoised(q).yzw + 0.35 * 2.17 * (t * (t * gnoised(r).yzw))) * 0.69;
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
		_fail("the metal shader's field() changed: no two-octave line to replace")
		return
	var one := Shader.new()
	one.code = src.replace(TWO_OCTAVES, ONE_OCTAVE)
	var at: int = src.find("vec3 slope(")
	var end: int = src.find("void fragment()")
	if at < 0 or end < at:
		_fail("the metal shader's slope() changed: nothing to replace for the analytic variant")
		return
	var analytic := Shader.new()
	analytic.code = src.substr(0, at) + ANALYTIC + src.substr(end)
	var alt: Dictionary = {"one_octave": one, "analytic": analytic}
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
		var per: Dictionary = {"shipped": [], "flat": [], "one_octave": [], "analytic": [], "hidden": []}
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
		for variant: String in ["flat", "one_octave", "analytic"]:  # the pixels' change against the shipped frame, 0..255
			var d: Dictionary = (images[variant] as Image).compute_image_metrics(images["shipped"], false)
			row["px_mean_" + variant] = snappedf(float(d["mean"]), 0.001)
			row["px_max_" + variant] = float(d["max"])
		for variant: String in per:
			row["gpu_ms_" + variant] = snappedf(_median(per[variant]), 0.001)
			row["rounds_" + variant] = per[variant]
		row["noise_ms"] = snappedf(row["gpu_ms_shipped"] - row["gpu_ms_flat"], 0.001)
		row["octave2_ms"] = snappedf(row["gpu_ms_shipped"] - row["gpu_ms_one_octave"], 0.001)
		row["station_ms"] = snappedf(row["gpu_ms_shipped"] - row["gpu_ms_hidden"], 0.001)
		row["analytic_saves_ms"] = snappedf(row["gpu_ms_shipped"] - row["gpu_ms_analytic"], 0.001)
		_compare(images["shipped"], images["analytic"]).save_png(_out.path_join("%s__compare.png" % v[0]))
		rows.append(row)
		print("COST %s" % JSON.stringify(row))
	var f := FileAccess.open(_out.path_join("cost.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"size": [root.size.x, root.size.y], "spec": spec,
		"adapter": RenderingServer.get_video_adapter_name(), "views": rows}, "  ") + "\n")
	f.close()
	print("COST wrote %s" % _out.path_join("cost.json"))
	quit(0)


## The same view before (shipped) and after (the proposal) side by side at 640x360 each, and their difference x8.
func _compare(before: Image, after: Image) -> Image:
	var size := Vector2i(640, 360)
	var a: Image = before.duplicate()
	var b: Image = after.duplicate()
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
