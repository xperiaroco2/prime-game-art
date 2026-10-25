extends RefCounted
## The ship's breaker board's look and states (art#263's stations): puts the bronze, graphite, enamel, cyan, core,
## lamp and beacon materials on an imported breaker_board.glb by its glTF material names (each core and lamp its own
## copy, so each can be driven alone), finds the four shell leaves, and adds the beacon's red light. The states:
## a shell's trip (0 closed .. 1 tripped, 110 degrees forward and down round its hinge), a lamp (dark, yellow, green)
## and the beacon (the problem). The sparks and smoke at a tripped core are the game's. Use with preload (no class
## cache in a `-s` script); every apply() makes the board its own materials.
##
##   const Board = preload("board.gd")
##   var look: Dictionary = Board.apply(model)
##   Board.set_shell(look, 1, 1.0)      # the yellow shell tripped
##   Board.set_on(look, 1, false)       # its lamp dark
##   Board.set_problem(look, true)      # the beacon on

const METAL := preload("board_metal.gdshader")  # relative: the same files work where the game keeps them
const CORE := preload("board_core.gdshader")

const COLOURS := ["red", "yellow", "green", "blue"]   # left to right as you face the board
const TRIP := deg_to_rad(110.0)                         # a shell's local rotation.x when tripped
const ENAMEL := {"red": Color(0.78, 0.09, 0.07), "yellow": Color(0.93, 0.68, 0.08),
	"green": Color(0.13, 0.55, 0.22), "blue": Color(0.12, 0.25, 0.75)}
const CYAN := Color(0.0, 0.62, 1.0)
const CYAN_ENERGY := 2.4
const LAMP := [Color(0.02, 0.02, 0.02), Color(1.0, 0.62, 0.02), Color(0.1, 1.0, 0.22)]   # dark, yellow, green
const LAMP_ENERGY := 2.2
const BEACON := Color(1.0, 0.06, 0.03)
const BEACON_ENERGY := 3.0
const BEACON_LIGHT := 0.9


## Returns the look: {"shells" (Node3D x4), "cores" (ShaderMaterial x4), "lamps" (StandardMaterial3D x4), "beacon"
## (StandardMaterial3D), "beacon_light" (OmniLight3D), "open" (float x4), "lamp" (int x4), "problem"}.
static func apply(root: Node3D) -> Dictionary:
	var bronze := ShaderMaterial.new()
	bronze.shader = METAL
	bronze.set_shader_parameter("metallic", 0.4)  # fully metallic mirrors the dark corridor and reads black
	bronze.set_shader_parameter("roughness", 0.4)
	bronze.set_shader_parameter("wear", 1.0)
	bronze.set_shader_parameter("lift", 0.1)
	var graphite := ShaderMaterial.new()
	graphite.shader = METAL
	graphite.set_shader_parameter("base_color", Color(0.25, 0.255, 0.27))
	graphite.set_shader_parameter("worn_color", Color(0.6, 0.6, 0.6))
	graphite.set_shader_parameter("metallic", 0.75)
	graphite.set_shader_parameter("roughness", 0.4)
	var cyan := StandardMaterial3D.new()
	cyan.albedo_color = Color(0.02, 0.05, 0.06)
	cyan.emission_enabled = true
	cyan.emission = CYAN
	cyan.emission_energy_multiplier = CYAN_ENERGY
	var cable := StandardMaterial3D.new()
	cable.albedo_color = Color(0.05, 0.05, 0.055)
	cable.roughness = 0.42
	cable.metallic = 0.2
	var by_name := {"board_bronze": bronze, "board_graphite": graphite, "board_cyan": cyan, "board_cable": cable}
	for c: String in COLOURS:
		var e := StandardMaterial3D.new()
		e.albedo_color = ENAMEL[c]
		e.roughness = 0.24
		e.metallic = 0.15
		e.clearcoat_enabled = true
		e.clearcoat = 0.8
		e.emission_enabled = true  # a faint lift of its own colour: enamel, not black glass, in the night corridor
		e.emission = ENAMEL[c]
		e.emission_energy_multiplier = 0.12
		by_name["board_enamel_" + c] = e
	var look := {"shells": [], "cores": [], "lamps": [], "open": [0.0, 0.0, 0.0, 0.0], "lamp": [2, 2, 2, 2],
		"problem": false}
	var beacon := StandardMaterial3D.new()
	beacon.albedo_color = Color(0.45, 0.03, 0.02)
	beacon.roughness = 0.15
	beacon.emission_enabled = true
	beacon.emission = BEACON
	look["beacon"] = beacon
	for m: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if m.mesh == null:
			continue
		m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		for i: int in m.mesh.get_surface_count():
			var src: Material = m.mesh.surface_get_material(i)
			var key: String = src.resource_name if src != null else ""
			if by_name.has(key):
				m.set_surface_override_material(i, by_name[key])
			elif key == "board_beacon":
				m.set_surface_override_material(i, beacon)
			elif key != "board_core" and key != "board_lamp":
				push_warning("board.gd: no look for surface material '%s'" % key)
	for c: String in COLOURS:
		var shell: Node3D = root.find_child("shell_" + c, true, false)
		var core: MeshInstance3D = root.find_child("core_" + c, true, false)
		var lamp: MeshInstance3D = root.find_child("lamp_" + c, true, false)
		if shell == null or core == null or lamp == null:
			push_error("board.gd: no shell, core or lamp '%s'" % c)
			return {}
		var cm := ShaderMaterial.new()
		cm.shader = CORE
		core.set_surface_override_material(0, cm)
		var lm := StandardMaterial3D.new()
		lm.albedo_color = Color(0.03, 0.03, 0.03)
		lm.roughness = 0.12
		lm.emission_enabled = true
		lamp.set_surface_override_material(0, lm)
		(look["shells"] as Array).append(shell)
		(look["cores"] as Array).append(cm)
		(look["lamps"] as Array).append(lm)
	var old: Node = root.get_node_or_null(^"BoardBeaconLight")  # a second apply() replaces the light
	if old != null:
		root.remove_child(old)
		old.free()
	var light := OmniLight3D.new()
	light.name = "BoardBeaconLight"
	light.light_color = BEACON
	light.omni_range = 1.6
	light.omni_attenuation = 1.5
	light.shadow_enabled = false
	root.add_child(light)
	light.position = Vector3(0.0, 1.38, 0.2)  # over the dome, a little out of the wall (metres, the board's frame)
	look["beacon_light"] = light
	for i: int in 4:
		set_shell(look, i, 0.0)
		set_lamp(look, i, 2)
	set_problem(look, false)
	return look


## A shell's trip: 0 closed (on), 1 tripped (fallen open forward and down); values between turn it on its hinge.
static func set_shell(look: Dictionary, index: int, open01: float) -> void:
	var t := clampf(open01, 0.0, 1.0)
	(look["shells"][index] as Node3D).rotation.x = TRIP * t
	look["open"][index] = t


## The lamp over a bay: on green, off dark.
static func set_on(look: Dictionary, index: int, on: bool) -> void:
	set_lamp(look, index, 2 if on else 0)


## The lamp over a bay: 0 dark (tripped), 1 yellow (switching on), 2 green (on).
static func set_lamp(look: Dictionary, index: int, state: int) -> void:
	var s := clampi(state, 0, 2)
	var m: StandardMaterial3D = look["lamps"][index]
	m.emission = LAMP[s]
	m.emission_energy_multiplier = 0.0 if s == 0 else LAMP_ENERGY
	m.albedo_color = Color(0.12, 0.03, 0.02) if s == 0 else Color(0.03, 0.03, 0.03)
	look["lamp"][index] = s


## The red beacon: on while any shell is tripped.
static func set_problem(look: Dictionary, on: bool) -> void:
	var m: StandardMaterial3D = look["beacon"]
	m.emission_energy_multiplier = BEACON_ENERGY if on else 0.08
	var light: OmniLight3D = look["beacon_light"]
	light.light_energy = BEACON_LIGHT
	light.visible = on
	look["problem"] = on


## A core's glow: 1 full (the default), 0 dark.
static func set_core(look: Dictionary, index: int, glow: float) -> void:
	(look["cores"][index] as ShaderMaterial).set_shader_parameter("glow", maxf(glow, 0.0))
