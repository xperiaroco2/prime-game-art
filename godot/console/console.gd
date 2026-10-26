extends RefCounted
## The ship engine's start console's look (art#263's stations): puts the metal, signal, hologram and light materials
## on an imported start_console.glb by its glTF material names, and adds two small lights (the hologram's cyan over
## the emitter, the button's orange), so the console lights what is near it. The states are three values:
## `passed` the stage strips lit green (idle 1, one more per stage passed), `lit` the order lamp lit bright (-1 none;
## 0..3 the west wing from the hall outward, red, yellow, green, blue; 4..7 the east), `order` true while the order
## plays (the other lamps dim). Use with preload (no class cache in a `-s` script); every apply() makes the console
## its own materials.
##
##   const Console = preload("console.gd")
##   var look: Dictionary = Console.apply(model)
##   Console.set_state(look, "order")        # or set_passed(look, 2), set_lit(look, 5)
##
## The spin-up (art#263, step 1): the hologram's turbines, the stations' wiring, the charge ring and the countdown,
## all values on the same mesh, and a clock of their own (a tween on the console's clock uniform, no _process):
##   Console.set_calling(look, true)          # before the start: the turbines pulse orange every CALL_PERIOD s,
##   Console.call_phase(look)                 #   the button glows; 0..1 (0 the pulse's onset: play the beep there)
##   Console.set_charge(look, 0.4)            # the strips and the ring fill as one bar (stage k is a third)
##   Console.set_spin(look, 1.0)              # the turbines' fans in turns per second (each broken station halves it)
##   Console.set_station(look, "vent_e", "broken", 2.0)   # "ok" | "broken" (its blink per second) | "fixed" | "off"
##   Console.set_countdown(look, 7.3)         # the nearest failure's seconds over the hologram; -1 hides it
## Step 2 (read from the hall): the call floods the turbines orange with a glow round the pods and a wash over the
## shell; a broken point shows a big red bead and a red pillar blinking at its rate; the bar runs on the hologram's
## band and again on the emitter deck; its colour and the ring's look are choices with defaults:
##   Console.set_fill(look, "cyan")           # or "green": the strips' and the rings' lit colour (FILL)
##   Console.set_ring_style(look, "both")     # "band" | "deck" | "both" | "step1" (RING_STYLE)
## The strips show max(passed / 3, charge): a game driving the bar alone calls set_passed(look, 0) first.

const METAL := preload("console_metal.gdshader")  # relative: the same files work where the game keeps them
const SIGNAL := preload("console_signal.gdshader")
const HOLO := preload("console_holo.gdshader")

const CYAN := Color(0.0, 0.62, 1.0)
const ORANGE := Color(1.0, 0.2, 0.0)        # deep: the glow and AgX pale a bright orange to peach
const CYAN_ENERGY := 2.4         # the channels, the ring and the core (HDR: they bloom; more bleaches them white)
const BUTTON_ENERGY := 0.8
const HOLO_ENERGY := 2.6         # the hologram's lines at full brightness
const STATES := {"idle": [1, -1, false], "order": [1, 1, true], "stage": [2, -1, false]}
# the spin-up: the stations in the wiring's order (the build's UV0 v; 8 the manifold to the turbines)
const STATIONS := ["socket_w", "socket_e", "socket_fw", "socket_fe", "breaker_w", "breaker_e", "vent_w", "vent_e"]
const STATION_STATES := {"off": 0.0, "ok": 1.0, "broken": 2.0, "fixed": 1.0}
const CALL_PERIOD := 3.0         # s from one call to the next (the turbines' orange pulse, the button's glow)
const CALL_GLOW := 4.0           # the button's glow over BUTTON_ENERGY at a call's peak (step 1: 2.5)
const CALLING_ENERGY := 1.4      # the button's glow while calling, between the pulses
const SLOW := 0.5                # each broken station multiplies the turbines' spin by this
const CLOCK_SPAN := 100000.0     # s: the clock's run (it restarts at reset_spinup)
const BLINK_MIN := 0.5           # a broken station blinks at least this often per second (0 would read solid red)
# the bar's lit colour on the strips and the rings (set_fill; sRGB)
const FILLS := {"cyan": Color(0.06, 0.5, 1.0), "green": Color(0.02, 1.0, 0.1)}
const FILL := "green"            # step 2's pick from the review's grid: cyan vanishes into the cyan hologram
# the charge ring's look (set_ring_style): [band_top: the share of the built band drawn, band_gain: its lit
# brightness, deck: the bar's second ring on the emitter deck 0/1]; "step1" the band as step 1 drew it
const RING_STYLES := {"band": [1.0, 1.6, 0.0], "deck": [0.5, 1.0, 1.0], "both": [1.0, 1.6, 1.0],
	"step1": [0.5, 1.0, 0.0]}
const RING_STYLE := "both"       # step 2's pick from the review's grid
const CALL_SHELL := ["calling", "call_t0", "call_period"]  # the call's uniforms on the turbines and the shell
# the fans' centres and axis in the GLB's frame (the build's build.json "spinup" "turbines"; the test checks them)
const FAN_CENTRES := [Vector3(0.18365, 1.55792, -0.62014), Vector3(-0.18365, 1.55792, -0.62014),
	Vector3(0.0, 1.59086, -0.61314)]
const FAN_AXIS := Vector3(0.0, -0.20791, 0.97815)


## Puts the console's materials on every surface under root; returns the look: {"signal" (the strips),
## "lamps", "holo", "shell", "beam" (ShaderMaterial), "glow" and "button_light" (OmniLight3D), "passed", "lit",
## "order"}.
static func apply(root: Node3D) -> Dictionary:
	var bronze := ShaderMaterial.new()
	bronze.shader = METAL
	bronze.set_shader_parameter("metallic", 0.35)  # fully metallic, it mirrors the dark hall and reads black
	bronze.set_shader_parameter("roughness", 0.42)
	bronze.set_shader_parameter("wear", 1.0)
	bronze.set_shader_parameter("lift", 0.12)
	var graphite := ShaderMaterial.new()
	graphite.shader = METAL
	graphite.set_shader_parameter("base_color", Color(0.272, 0.276, 0.293))  # sRGB of the Blender look's linear
	graphite.set_shader_parameter("worn_color", Color(0.634, 0.626, 0.618))
	graphite.set_shader_parameter("metallic", 0.75)
	graphite.set_shader_parameter("roughness", 0.38)
	var cyan := StandardMaterial3D.new()
	cyan.albedo_color = Color(0.02, 0.05, 0.06)
	cyan.roughness = 0.2
	cyan.emission_enabled = true
	cyan.emission = CYAN
	cyan.emission_energy_multiplier = CYAN_ENERGY
	var button := StandardMaterial3D.new()
	button.albedo_color = Color(0.95, 0.32, 0.04)
	button.roughness = 0.18
	button.clearcoat_enabled = true
	button.clearcoat = 1.0
	button.emission_enabled = true
	button.emission = ORANGE
	button.emission_energy_multiplier = BUTTON_ENERGY
	button.rim_enabled = true
	button.rim = 0.4
	var strips := ShaderMaterial.new()
	strips.shader = SIGNAL
	strips.set_shader_parameter("mode", 0)
	var lamps := ShaderMaterial.new()
	lamps.shader = SIGNAL
	lamps.set_shader_parameter("mode", 1)
	var holo := ShaderMaterial.new()
	holo.shader = HOLO
	holo.set_shader_parameter("mode", 0)
	holo.set_shader_parameter("energy", HOLO_ENERGY)
	var shell := ShaderMaterial.new()
	shell.shader = HOLO
	shell.set_shader_parameter("mode", 1)
	shell.set_shader_parameter("colour", Color(0.12, 0.5, 1.0))
	shell.set_shader_parameter("energy", 0.45)
	shell.set_shader_parameter("call_period", CALL_PERIOD)  # the call washes the shell orange (step 2)
	var beam := ShaderMaterial.new()
	beam.shader = HOLO
	beam.set_shader_parameter("mode", 2)
	beam.set_shader_parameter("colour", Color(0.3, 0.78, 1.0))
	beam.set_shader_parameter("energy", 0.5)
	var turbine := _holo(3, Color(0.06, 0.42, 1.0), HOLO_ENERGY)  # mode 0's look at rest
	turbine.set_shader_parameter("fan_centre", PackedVector3Array(FAN_CENTRES))
	turbine.set_shader_parameter("fan_axis", FAN_AXIS)
	turbine.set_shader_parameter("call_period", CALL_PERIOD)
	var wire := _holo(4, Color(0.06, 0.42, 1.0), 1.5)
	var ring := _holo(5, Color(0.06, 0.5, 1.0), 2.2)
	var digit := _holo(6, Color(0.2, 0.7, 1.0), 2.6)
	var by_name := {"console_bronze": bronze, "console_graphite": graphite, "console_cyan": cyan,
		"console_button": button, "console_stage": strips, "console_lamp": lamps, "console_holo_line": holo,
		"console_holo_shell": shell, "console_beam": beam, "console_holo_turbine": turbine,
		"console_holo_wire": wire, "console_holo_ring": ring, "console_holo_digit": digit}
	if root.has_meta("console_tween"):  # a second apply(): the first look's clock stops (it drove the old materials)
		var prior: Tween = root.get_meta("console_tween") as Tween
		if prior != null and prior.is_valid():
			prior.kill()
		root.remove_meta("console_tween")
	for old_name: String in ["ConsoleGlow", "ConsoleButtonLight"]:  # a second apply() replaces the lights
		var old: Node = root.get_node_or_null(NodePath(old_name))
		if old != null:
			root.remove_child(old)
			old.free()
	for m: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if m.mesh == null:
			continue
		m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		for i: int in m.mesh.get_surface_count():
			var src: Material = m.mesh.surface_get_material(i)
			var key: String = src.resource_name if src != null else ""
			if by_name.has(key):
				m.set_surface_override_material(i, by_name[key])
			else:
				push_warning("console.gd: no look for surface material '%s'" % key)
	# the hologram's light over the emitter, the button's at its face (the model's frame: front +Z, metres)
	var glow := OmniLight3D.new()
	glow.name = "ConsoleGlow"
	glow.light_color = Color(0.3, 0.75, 1.0)
	glow.light_energy = 0.9
	glow.omni_range = 2.2
	glow.omni_attenuation = 1.4
	glow.shadow_enabled = false
	root.add_child(glow)
	glow.position = Vector3(0.0, 1.3, 0.0)
	var lamp := OmniLight3D.new()
	lamp.name = "ConsoleButtonLight"
	lamp.light_color = ORANGE
	lamp.light_energy = 0.08  # more paints the front block red
	lamp.omni_range = 0.7
	lamp.shadow_enabled = false
	root.add_child(lamp)
	lamp.position = Vector3(0.0, 0.814, 0.58)
	var look := {"signal": strips, "lamps": lamps, "holo": holo, "shell": shell, "beam": beam, "glow": glow,
		"button_light": lamp, "passed": 1, "lit": -1, "order": false, "button": button, "turbine": turbine,
		"wire": wire, "ring": ring, "digit": digit, "root": root, "tween": null, "clock": 0.0, "calling": false,
		"call_t0": 0.0, "spin": 0.0, "stations": {}, "charge": 0.0, "countdown": -1.0, "fill": FILL,
		"ring_style": RING_STYLE}
	set_state(look, "idle")
	set_fill(look, FILL)
	set_ring_style(look, RING_STYLE)
	reset_spinup(look)
	return look


## One of the review states: "idle" (the button glowing, the first strip green), "order" (the order playing: the
## west wing's yellow lamp lit), "stage" (a stage passed: two strips green).
static func set_state(look: Dictionary, state: String) -> void:
	var s: Array = STATES[state]
	set_passed(look, s[0])
	set_lit(look, s[1], s[2])


## How many stage strips are lit (0..3). Its own uniform beside the spin-up's charge: the strips show
## max(passed / 3, charge), the ring the charge alone; reset_spinup() leaves it.
static func set_passed(look: Dictionary, n: int) -> void:
	look["passed"] = clampi(n, 0, 3)
	(look["signal"] as ShaderMaterial).set_shader_parameter("passed", float(look["passed"]))


## The order lamp lit bright (-1 none; 0..3 west from the hall outward, 4..7 east); playing: the others dim.
static func set_lit(look: Dictionary, index: int, playing: bool = true) -> void:
	look["lit"] = clampi(index, -1, 7)
	look["order"] = playing and index >= 0
	var lamps: ShaderMaterial = look["lamps"]
	lamps.set_shader_parameter("lit", float(look["lit"]))
	lamps.set_shader_parameter("order", 1.0 if look["order"] else 0.0)


static func _holo(mode: int, colour: Color, energy: float) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = HOLO
	m.set_shader_parameter("mode", mode)
	m.set_shader_parameter("colour", colour)
	m.set_shader_parameter("energy", energy)
	return m


## The spin-up at rest: not calling, no charge, the fans still, every station off (its point dim, its line still),
## no countdown. The clock restarts at 0 and runs (a tween bound to the console) while the console is in the tree.
static func reset_spinup(look: Dictionary) -> void:
	var old: Tween = look["tween"]
	if old != null:
		old.kill()
	look["tween"] = null
	look["calling"] = false
	look["call_t0"] = 0.0
	look["spin"] = 0.0
	var stations := {}
	for id: String in STATIONS:
		stations[id] = {"state": "off", "blink": 1.0, "fixed_at": -1.0e6}
	look["stations"] = stations
	var t: ShaderMaterial = look["turbine"]
	t.set_shader_parameter("calling", 0.0)
	t.set_shader_parameter("call_t0", 0.0)
	t.set_shader_parameter("spin_phase", 0.0)
	t.set_shader_parameter("spin_t0", 0.0)
	t.set_shader_parameter("spin_rate", 0.0)
	_tick(look, 0.0)
	set_charge(look, 0.0)
	set_countdown(look, -1.0)
	_stations(look)
	_respin(look)
	var tree := Engine.get_main_loop() as SceneTree
	var root: Node = look["root"]
	if tree != null and is_instance_valid(root):
		var tw: Tween = tree.create_tween().bind_node(root)
		tw.tween_method(func(c: float) -> void: _tick(look, c), 0.0, CLOCK_SPAN, CLOCK_SPAN)
		look["tween"] = tw
		root.set_meta("console_tween", tw)


## The console's clock in seconds (the spin-up shaders' time).
static func clock(look: Dictionary) -> float:
	return float(look["clock"])


## Stops the running clock and sets it (reviews, recordings and tests step it themselves).
static func set_clock(look: Dictionary, seconds: float) -> void:
	var t: Tween = look["tween"]
	if t != null:
		t.kill()
		look["tween"] = null
	_tick(look, seconds)


static func _tick(look: Dictionary, c: float) -> void:
	look["clock"] = c
	for m: String in ["turbine", "wire", "ring", "digit", "shell"]:
		(look[m] as ShaderMaterial).set_shader_parameter("clock", c)
	var button: StandardMaterial3D = look["button"]
	var light: OmniLight3D = look["button_light"]
	if look["calling"]:
		var p := call_pulse(call_phase(look))
		button.emission_energy_multiplier = CALLING_ENERGY + BUTTON_ENERGY * CALL_GLOW * p
		light.light_energy = 0.08 * (1.0 + 4.0 * p)
	else:
		button.emission_energy_multiplier = BUTTON_ENERGY
		light.light_energy = 0.08


## Before the start the ship calls: the turbines pulse orange every CALL_PERIOD s and the button glows; the first
## pulse starts when calling starts.
static func set_calling(look: Dictionary, on: bool) -> void:
	if on and not look["calling"]:
		look["call_t0"] = clock(look)
	look["calling"] = on
	for m: String in ["turbine", "shell"]:  # the turbines flood orange and glow; the shell takes a wash of it
		var t: ShaderMaterial = look[m]
		t.set_shader_parameter("calling", 1.0 if on else 0.0)
		t.set_shader_parameter("call_t0", float(look["call_t0"]))
	_tick(look, clock(look))


## Where the call is in its period, 0..1 (0 the pulse's onset, the moment for the beep); -1 when not calling.
static func call_phase(look: Dictionary) -> float:
	if not look["calling"]:
		return -1.0
	return fposmod((clock(look) - float(look["call_t0"])) / CALL_PERIOD, 1.0)


## The call's light at a phase (the shader's call_pulse): up in 0.15 s, gone by 1.35 s.
static func call_pulse(phase: float) -> float:
	if phase < 0.0:
		return 0.0
	return smoothstep(0.0, 0.05, phase) * (1.0 - smoothstep(0.05, 0.45, phase))


## The charge 0..1 as one bar: the three stage strips fill one after another (stage k is a third) and the ring
## round the hologram's hall fills with them.
static func set_charge(look: Dictionary, charge: float) -> void:
	var c := clampf(charge, 0.0, 1.0)
	look["charge"] = c
	(look["signal"] as ShaderMaterial).set_shader_parameter("charge", c)
	(look["ring"] as ShaderMaterial).set_shader_parameter("charge", c)


## The bar's lit colour on the strips and both rings: "cyan" (the hologram's, a white head where it fills) or
## "green" (the strips' old green).
static func set_fill(look: Dictionary, name: String) -> void:
	if not FILLS.has(name):
		push_warning("console.gd: no fill '%s'" % name)
		return
	look["fill"] = name
	var c: Color = FILLS[name]
	var strips: ShaderMaterial = look["signal"]
	strips.set_shader_parameter("fill_colour", c.srgb_to_linear() if name == "cyan" else c)  # step 1's green as was
	strips.set_shader_parameter("head", 1.0)
	(look["ring"] as ShaderMaterial).set_shader_parameter("fill", c)


## The charge ring's look: "band" (the band on the hologram twice as tall and brighter when lit), "deck" (step 1's
## band and the bar again as a ring on the emitter deck), "both", or "step1".
static func set_ring_style(look: Dictionary, name: String) -> void:
	if not RING_STYLES.has(name):
		push_warning("console.gd: no ring style '%s'" % name)
		return
	look["ring_style"] = name
	var s: Array = RING_STYLES[name]
	var ring: ShaderMaterial = look["ring"]
	ring.set_shader_parameter("band_top", s[0])
	ring.set_shader_parameter("band_gain", s[1])
	ring.set_shader_parameter("deck", s[2])


## The turbines' spin in turns per second (0 still); each broken station multiplies it by SLOW. The fans keep their
## angle through a change.
static func set_spin(look: Dictionary, turns_per_s: float) -> void:
	look["spin"] = maxf(turns_per_s, 0.0)
	_respin(look)


## The fans' rate now (after the broken stations' slowing), turns per second.
static func spin_rate(look: Dictionary) -> float:
	return float((look["turbine"] as ShaderMaterial).get_shader_parameter("spin_rate"))


static func _respin(look: Dictionary) -> void:
	var t: ShaderMaterial = look["turbine"]
	var now := clock(look)
	var turns: float = float(t.get_shader_parameter("spin_phase")) \
		+ (now - float(t.get_shader_parameter("spin_t0"))) * float(t.get_shader_parameter("spin_rate"))
	var broken := 0
	for id: String in STATIONS:
		broken += 1 if look["stations"][id]["state"] == "broken" else 0
	t.set_shader_parameter("spin_phase", fposmod(turns, 1.0))
	t.set_shader_parameter("spin_t0", now)
	t.set_shader_parameter("spin_rate", float(look["spin"]) * pow(SLOW, broken))
	(look["wire"] as ShaderMaterial).set_shader_parameter("flow", 1.0 if float(look["spin"]) > 0.0 else 0.0)


## A station's state on the hologram: "off" (its point dim, its line still: before the start), "ok" (the line lit,
## flowing toward the turbines), "broken" (the point blinks red blink_hz times a second, its line dark, the turbines
## slow), "fixed" (the line flashes back bright, then reads ok).
static func set_station(look: Dictionary, id: String, state: String, blink_hz: float = 1.0) -> void:
	if not id in STATIONS or not STATION_STATES.has(state):
		push_warning("console.gd: no station '%s' or state '%s'" % [id, state])
		return
	var s: Dictionary = look["stations"][id]
	s["state"] = "ok" if state == "fixed" else state
	s["blink"] = maxf(blink_hz, BLINK_MIN)
	if state == "fixed":
		s["fixed_at"] = clock(look)
	_stations(look)
	_respin(look)


static func _stations(look: Dictionary) -> void:
	var st := PackedFloat32Array()
	var blink := PackedFloat32Array()
	var fixed := PackedFloat32Array()
	var on := 0
	var ok := 0
	for id: String in STATIONS:
		var s: Dictionary = look["stations"][id]
		st.append(STATION_STATES[s["state"]])
		blink.append(float(s["blink"]))
		fixed.append(float(s["fixed_at"]))
		on += 0 if s["state"] == "off" else 1
		ok += 1 if s["state"] == "ok" else 0
	st.append(1.0 if on == 0 else float(ok) / on)  # the manifold: the share of the lines not broken
	blink.append(0.0)
	fixed.append(-1.0e6)
	var w: ShaderMaterial = look["wire"]
	w.set_shader_parameter("st_state", st)
	w.set_shader_parameter("st_blink", blink)
	w.set_shader_parameter("st_fixed_at", fixed)


## The countdown over the hologram: the nearest failure's seconds (shown rounded up; orange in the last 5, red in
## the last 3, each second ticking); below 0 hidden.
static func set_countdown(look: Dictionary, seconds: float) -> void:
	look["countdown"] = seconds
	(look["digit"] as ShaderMaterial).set_shader_parameter("countdown", seconds)
