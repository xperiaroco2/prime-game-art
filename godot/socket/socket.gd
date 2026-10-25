extends RefCounted
## The ship's crystal socket's look (art#263's stations): puts the metal, strip, amber and lamp materials on an
## imported crystal_socket.glb by its glTF material names, and adds the red problem-lamp's light at the dome. The
## bronze and graphite are the start console's (socket_metal.gdshader is console_metal.gdshader, unchanged). One
## state drives the lamp: "charged" off, "spent" and "empty" lit red. The crystal itself is the game's: parent
## energy_crystal.glb on the socket's `crystal_anchor` node and give it crystal.gd's look and charge. Use with
## preload (no class cache in a `-s` script); every apply() makes the socket its own materials.
##
##   const Socket = preload("socket.gd")
##   var look: Dictionary = Socket.apply(model)
##   Socket.set_state(look, "spent")        # or "charged", "empty"

const METAL := preload("socket_metal.gdshader")  # relative: the same files work where the game keeps them

const CYAN := Color(0.0, 0.62, 1.0)
const AMBER := Color(1.0, 0.46, 0.04)
const RED := Color(1.0, 0.05, 0.02)
const CYAN_ENERGY := 2.2
const AMBER_ENERGY := 1.6
const LAMP_ENERGY := 3.2         # the dome lit (HDR: it blooms)
const LAMP_LIGHT := 0.9          # its omni light, lit
const LAMP_RANGE := 1.6
const STATES := ["charged", "spent", "empty"]
const SOCKET_LAYER := 1 << 19    # the socket draws on render layer 20 alone: its seated crystal's light skips it


## Puts the socket's materials on every surface under root; returns the look: {"lamp" (StandardMaterial3D),
## "lamp_light" (OmniLight3D), "state"}.
static func apply(root: Node3D) -> Dictionary:
	var bronze := ShaderMaterial.new()
	bronze.shader = METAL
	bronze.set_shader_parameter("metallic", 0.35)  # the console's bronze: fully metallic reads black in the hall
	bronze.set_shader_parameter("roughness", 0.42)
	bronze.set_shader_parameter("wear", 1.0)
	bronze.set_shader_parameter("lift", 0.12)
	var graphite := ShaderMaterial.new()
	graphite.shader = METAL
	graphite.set_shader_parameter("base_color", Color(0.272, 0.276, 0.293))
	graphite.set_shader_parameter("worn_color", Color(0.634, 0.626, 0.618))
	graphite.set_shader_parameter("metallic", 0.75)
	graphite.set_shader_parameter("roughness", 0.38)
	var cyan := _glow(CYAN, CYAN_ENERGY)
	var amber := _glow(AMBER, AMBER_ENERGY)
	var lamp := StandardMaterial3D.new()
	lamp.albedo_color = Color(0.55, 0.03, 0.02)
	lamp.roughness = 0.12
	lamp.clearcoat_enabled = true
	lamp.clearcoat = 1.0
	lamp.rim_enabled = true
	lamp.rim = 0.3
	lamp.emission_enabled = true
	lamp.emission = RED
	var by_name := {"socket_bronze": bronze, "socket_graphite": graphite, "socket_cyan": cyan, "socket_amber": amber,
		"socket_lamp": lamp}
	var old: Node = root.get_node_or_null(NodePath("SocketLampLight"))  # a second apply() replaces the light
	if old != null:
		root.remove_child(old)
		old.free()
	var lamp_at := Vector3.ZERO
	for m: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if m.mesh == null or m.get_parent() is CollisionObject3D:
			continue
		m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		m.layers = SOCKET_LAYER  # the hall's lights reach every layer; seat_crystal() takes this one off the crystal's
		for i: int in m.mesh.get_surface_count():
			var src: Material = m.mesh.surface_get_material(i)
			var key: String = src.resource_name if src != null else ""
			if by_name.has(key):
				m.set_surface_override_material(i, by_name[key])
			else:
				push_warning("socket.gd: no look for surface material '%s'" % key)
			if key == "socket_lamp":  # the light at the dome's middle, wherever the build put it
				var v: PackedVector3Array = m.mesh.surface_get_arrays(i)[Mesh.ARRAY_VERTEX]
				var sum := Vector3.ZERO
				for p: Vector3 in v:
					sum += p
				lamp_at = m.transform * (sum / maxf(1.0, v.size()))
	var light := OmniLight3D.new()
	light.name = "SocketLampLight"
	light.light_color = RED
	light.omni_range = LAMP_RANGE
	light.omni_attenuation = 1.6
	light.shadow_enabled = false
	root.add_child(light)
	light.position = lamp_at + Vector3(0.0, 0.0, 0.03)
	var look := {"lamp": lamp, "lamp_light": light, "state": ""}
	set_state(look, "charged")
	return look


## Seats a crystal (its crystal.gd look) in the socket: the crystal's own light lights the hall and the players but
## not the socket (its cull mask without SOCKET_LAYER). A few centimetres from the frame it burned the bronze
## white-cyan, and moved 30 cm out it washed the whole face mint (the hall shots b2 and b4, 2026-10-25); the socket's
## own strips give the bay its cyan.
static func seat_crystal(crystal_look: Dictionary) -> void:
	var omni: OmniLight3D = crystal_look.get("omni")
	if omni != null:
		omni.light_cull_mask = omni.light_cull_mask & ~SOCKET_LAYER


## The socket's state: "charged" (a charged crystal in it: the lamp off), "spent" (a spent crystal: the lamp lit),
## "empty" (no crystal: the lamp lit).
static func set_state(look: Dictionary, state: String) -> void:
	assert(state in STATES, "socket.gd: no state '%s'" % state)
	var on: bool = state != "charged"
	(look["lamp"] as StandardMaterial3D).emission_energy_multiplier = LAMP_ENERGY if on else 0.0
	var light: OmniLight3D = look["lamp_light"]
	light.light_energy = LAMP_LIGHT if on else 0.0
	light.visible = on
	look["state"] = state


static func _glow(colour: Color, energy: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.03, 0.04, 0.05)
	m.roughness = 0.25
	m.emission_enabled = true
	m.emission = colour
	m.emission_energy_multiplier = energy
	return m
