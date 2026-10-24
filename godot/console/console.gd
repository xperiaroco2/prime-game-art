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

const METAL := preload("console_metal.gdshader")  # relative: the same files work where the game keeps them
const SIGNAL := preload("console_signal.gdshader")
const HOLO := preload("console_holo.gdshader")

const CYAN := Color(0.0, 0.62, 1.0)
const ORANGE := Color(1.0, 0.2, 0.0)        # deep: the glow and AgX pale a bright orange to peach
const CYAN_ENERGY := 2.4         # the channels, the ring and the core (HDR: they bloom; more bleaches them white)
const BUTTON_ENERGY := 0.8
const HOLO_ENERGY := 2.6         # the hologram's lines at full brightness
const STATES := {"idle": [1, -1, false], "order": [1, 1, true], "stage": [2, -1, false]}


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
	var beam := ShaderMaterial.new()
	beam.shader = HOLO
	beam.set_shader_parameter("mode", 2)
	beam.set_shader_parameter("colour", Color(0.3, 0.78, 1.0))
	beam.set_shader_parameter("energy", 0.5)
	var by_name := {"console_bronze": bronze, "console_graphite": graphite, "console_cyan": cyan,
		"console_button": button, "console_stage": strips, "console_lamp": lamps, "console_holo_line": holo,
		"console_holo_shell": shell, "console_beam": beam}
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
		"button_light": lamp, "passed": 1, "lit": -1, "order": false}
	set_state(look, "idle")
	return look


## One of the review states: "idle" (the button glowing, the first strip green), "order" (the order playing: the
## west wing's yellow lamp lit), "stage" (a stage passed: two strips green).
static func set_state(look: Dictionary, state: String) -> void:
	var s: Array = STATES[state]
	set_passed(look, s[0])
	set_lit(look, s[1], s[2])


## How many stage strips are green (0..3).
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
