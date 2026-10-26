extends "res://ship/ship.gd"
## The start console in the ship's hall at night (art#263's stations): ship.gd's own "shoot" mode, its pieces, its
## night light, probes and lamps from layouts/ship (tools/blender/console_run.py builds the request: every built
## ship piece plus "start_console" on the console's station spot, turned so its button faces the mouth), and two
## additions: the console wears console.gd's look, and a view's sixth element may name the console's state
## ({"console": "idle" | "order" | "stage"}; idle without it), its spin-up ({"spin": {"clock", "calling", "charge",
## "spin", "stations": {id: [state, blink_hz, fixed_s_ago]}, "countdown"}}; at rest without it) and
## {"hide_spinup": true} (the spin-up's four surfaces hidden: the before/after diff against an older GLB).
## The "video" mode is the spin-up's scripted round (console_run.py --spinup): the camera through the request's keys
## as ship.gd's video, the console driven by round() frame by frame on its own clock, a caption per phase.
## Started by the runner through `_godot.window()` like ship.gd:
##   godot <_godot.window() flags> -s res://console/hall.gd -- <request.json> <out>

const Console = preload("res://console/console.gd")
const SPINUP_SURFACES: Array = ["wire", "ring", "digit"]  # hidden for the diff (the turbines at rest are the old look)

var _console_look: Dictionary = {}


## ship.gd dresses the ship without the console: its pass would give the GLB's plain emissive fallbacks their own
## strip lights (lights the game never has) and retune their materials; the console then gets console.gd's look,
## whose two lights are the game's.
func _dress(ship: Node3D) -> int:
	var consoles: Array[Node3D] = []
	for n: Node in ship.get_children():
		if n.name.begins_with("start_console"):
			consoles.append(n as Node3D)
	for c: Node3D in consoles:
		ship.remove_child(c)
	var lights: int = super(ship)
	for c: Node3D in consoles:
		ship.add_child(c)
		_console_look = Console.apply(c)
		Console.set_clock(_console_look, 0.0)
		print("CONSOLE look on %s" % c.name)
	return lights


func _ab(off: Dictionary) -> void:
	super(off)
	if _console_look.is_empty():
		return
	var look: Dictionary = _console_look
	Console.set_state(look, str(off.get("console", "idle")))
	Console.reset_spinup(look)
	var s: Dictionary = off.get("spin", {})
	var t: float = float(s.get("clock", 0.0))
	Console.set_clock(look, 0.0)
	Console.set_calling(look, bool(s.get("calling", false)))
	Console.set_spin(look, float(s.get("spin", 0.0)))
	Console.set_clock(look, t)
	var stations: Dictionary = s.get("stations", {})
	for id: String in stations:
		var v: Array = stations[id]
		Console.set_clock(look, t - (float(v[2]) if v.size() > 2 else 0.0))
		Console.set_station(look, id, str(v[0]), float(v[1]) if v.size() > 1 else 1.0)
	Console.set_clock(look, t)
	if s.has("charge"):
		Console.set_charge(look, float(s["charge"]))
	Console.set_countdown(look, float(s.get("countdown", -1.0)))
	var hide: bool = bool(off.get("hide_spinup", false))
	for m: String in SPINUP_SURFACES:
		(look[m] as ShaderMaterial).set_shader_parameter("energy", 0.0 if hide else _energy(m))


func _energy(m: String) -> float:
	return {"turbine": Console.HOLO_ENERGY, "wire": 1.5, "ring": 2.2, "digit": 2.6}[m]


## The scripted round (seconds; the brief's: calling -> start -> charging with two failures, one left to count
## down -> fixed -> full). Returns its caption.
const T_START := 9.0
const T_VENT := 15.0          # vent_e breaks: 30 s to fix it
const T_BREAKER := 18.0       # breaker_w breaks: 10 s, it blows first (blinks fastest)
const T_FIX_VENT := 21.0
const T_FIX_BREAKER := 26.2
const T_END := 44.0
const SPIN := 1.2
const CHARGE_S := 32.0        # the charge's full run without failures


func _charge_at(t: float) -> float:
	var run: float = maxf(0.0, minf(t, T_VENT) - T_START) + maxf(0.0, t - T_FIX_BREAKER)
	return clampf(run / CHARGE_S, 0.0, 1.0)


func round_state(look: Dictionary, t: float, last: Dictionary) -> String:
	var phase: String
	if t < T_START:
		phase = "calling: the turbines pulse orange every 3 s, the button glows"
	elif t < T_VENT:
		phase = "charging: the turbines spin, the strips and the ring fill"
	elif t < T_FIX_BREAKER:
		phase = "two failures: the points blink red, their lines dark, the turbines slow"
	elif _charge_at(t) < 1.0:
		phase = "fixed: charging again"
	else:
		phase = "full"
	var want: Dictionary = {"calling": t < T_START, "spin": 0.0 if t < T_START else SPIN * clampf((t - T_START) / 2.0, 0.0, 1.0)}
	var st: Dictionary = {}
	for id: String in Console.STATIONS:
		st[id] = ["off", 1.0] if t < T_START else ["ok", 1.0]
	if t >= T_VENT and t < T_FIX_VENT:
		st["vent_e"] = ["broken", 1.2]
	elif t >= T_FIX_VENT:
		st["vent_e"] = ["fixed" if t < T_FIX_VENT + 1.5 else "ok", 1.0]
	var left_b: float = T_BREAKER + 10.0 - t
	if t >= T_BREAKER and t < T_FIX_BREAKER:
		st["breaker_w"] = ["broken", 2.5 if left_b > 3.0 else 4.0]
	elif t >= T_FIX_BREAKER:
		st["breaker_w"] = ["fixed" if t < T_FIX_BREAKER + 1.5 else "ok", 1.0]
	Console.set_clock(look, t)
	if bool(last.get("calling", false)) != want["calling"]:
		Console.set_calling(look, want["calling"])
	for id: String in st:
		var key: String = "%s/%s/%s" % [id, st[id][0], st[id][1]]
		if last.get(id, "") != key:
			# "fixed" is set once (its flash starts then); its later "ok" keeps the flash's end
			if not (st[id][0] == "ok" and str(last.get(id, "")).begins_with(id + "/fixed")):
				Console.set_station(look, id, st[id][0], st[id][1])
			last[id] = key
	if absf(float(last.get("spin", -1.0)) - want["spin"]) > 0.0001:
		Console.set_spin(look, want["spin"])
		last["spin"] = want["spin"]
	last["calling"] = want["calling"]
	Console.set_charge(look, _charge_at(t))
	var left: float = -1.0
	if t >= T_VENT and t < T_FIX_VENT:
		left = T_VENT + 30.0 - t
	if t >= T_BREAKER and t < T_FIX_BREAKER:
		left = left_b if left < 0.0 else minf(left, left_b)
	Console.set_countdown(look, left)
	return phase


func _video() -> void:
	_environment()
	var ship: Node3D = _build()
	var lights: int = _dress(ship)
	_probes()
	var v: Dictionary = _req["video"]
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.far = 500.0
	_camera.fov = float(v["fov"])
	root.add_child(_camera)
	_camera.make_current()
	var layer: CanvasLayer = CanvasLayer.new()
	_label = Label.new()
	_label.position = Vector2(16, 10)
	_label.add_theme_font_size_override("font_size", 24)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 6)
	layer.add_child(_label)
	root.add_child(layer)
	var keys: Array = v["keys"]
	var times: Array = [0.0]
	for i: int in range(1, keys.size()):
		times.append(float(times[-1]) + float(keys[i][2]))
	var fps: float = float(v["fps"])
	var count: int = int(minf(float(times[-1]), T_END) * fps) + 1
	var dir: String = _out.path_join("frames")
	DirAccess.make_dir_recursive_absolute(dir)
	_camera.look_at_from_position(_v(keys[0][0]), _v(keys[0][1]), UP)
	var look: Dictionary = _console_look
	Console.reset_spinup(look)
	var last: Dictionary = {}
	round_state(look, 0.0, last)
	for i: int in 30:  # the probes, SSAO and glow settle
		await process_frame
	var started: int = Time.get_ticks_msec()
	var k: int = 0
	var phases: Array = []
	for f: int in count:
		var t: float = minf(f / fps, float(times[-1]))
		while k < keys.size() - 2 and t > float(times[k + 1]):
			k += 1
		var gap: float = float(times[k + 1]) - float(times[k])
		var w: float = (t - float(times[k])) / gap if gap > 0.0 else 1.0
		_camera.look_at_from_position(_key(keys, times, k, w, 0), _key(keys, times, k, w, 1), UP)
		var phase: String = round_state(look, t, last)
		_label.text = "%4.1f s  %s" % [t, phase]
		if phases.is_empty() or phases[-1][1] != phase:
			phases.append([snappedf(t, 0.01), phase])
		await RenderingServer.frame_post_draw
		var image: Image = root.get_texture().get_image()
		image.convert(Image.FORMAT_RGB8)
		_save(image, dir.path_join("%05d.png" % f))
	_write("video.json", {"frames": count, "fps": fps, "seconds": (count - 1) / fps, "lights": lights,
		"phases": phases, "render_s": (Time.get_ticks_msec() - started) / 1000.0})
	print("CONSOLE round %d frames" % count)
	quit(0)
