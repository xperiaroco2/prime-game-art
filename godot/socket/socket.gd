extends RefCounted
## The ship's crystal socket's look (art#263's stations): puts the metal, strip, amber and lamp materials on an
## imported crystal_socket.glb by its glTF material names, and adds the red problem-lamp's light at the dome. The
## bronze and graphite are the start console's shader (socket_metal.gdshader is console_metal.gdshader; socket-3 gave
## it parameters whose defaults keep the console's look, and the socket's bronze sets them). One state drives the
## lamp and the bay's glow: "charged" (lamp off, bay lit), "spent" and "empty" (lamp lit red, bay dark). The two
## claws (nodes claw_r, claw_l) open round their hinges: set_claws(look, 0..1); the timing and the sounds are the
## game's. The crystal itself is the game's: parent energy_crystal.glb on the socket's `crystal_anchor` node and give
## it crystal.gd's look and charge; it slides out along the anchor's +Z and is free PULL_CM out. Use with preload (no
## class cache in a `-s` script); every apply() makes the socket its own materials.
##
##   const Socket = preload("socket.gd")
##   var look: Dictionary = Socket.apply(model)
##   Socket.set_state(look, "spent")        # or "charged", "empty"
##   Socket.set_claws(look, 1.0)            # open (0 closed)

const METAL := preload("socket_metal.gdshader")  # relative: the same files work where the game keeps them
const BAY := preload("socket_bay.gdshader")

const CYAN := Color(0.0, 0.62, 1.0)
const AMBER := Color(1.0, 0.5, 0.0)   # socket-3: sRGB; red-heavy reads pink, bright reads cream under AgX (step 2: peach)
const RED := Color(1.0, 0.05, 0.02)
const BRONZE := Color(0.5, 0.38, 0.24)        # sRGB: socket-3 a warmer, darker gold (b5: (0.56, 0.46, 0.32))
const BRONZE_EDGE := Color(1.0, 0.9, 0.7)
## socket-3: the bronze's finish on the shared metal shader (the board and the charger match these): the faces
## lighter or darker by their facing, a broad wave in the normal (gradients and glints; the hammered dent showed its
## noise cells as squares, so it is off), more
## roughness variation, the broad chamfers worn bright, the worn edges polished
const BRONZE_FINISH := {"metallic": 0.75, "roughness": 0.3, "wear": 1.4, "lift": 0.08, "mottle": 0.3, "grain": 0.06,
	"rough_grain": 0.06, "rough_mottle": 0.15, "edge_polish": 0.25, "shade": 0.3, "dent": 0.0, "dent_scale": 45.0,
	"wave": 0.3, "wave_scale": 8.0}
const CYAN_ENERGY := 5.0         # socket-3: bright with a bloom (socket-2: 4.0)
const AMBER_ENERGY := 0.9        # the windows sunk in their bezels (socket-2: 2.4; brighter reads peach under AgX)
const BAY_ENERGY := 1.6          # socket-3: the bay's floor glowing round a charged crystal
const CLAW_OPEN_DEG := 25.0      # tools/blender/socket_dims.toml [claw] open (the drawing's 35 cut the bay's lip)
const PULL_CM := 15.0            # the crystal is free this far out along the anchor's +Z
const LAMP_ENERGY := 3.2         # the dome lit (HDR: it blooms)
const LAMP_LIGHT := 0.9          # its omni light, lit
const LAMP_RANGE := 1.6
const STATES := ["charged", "spent", "empty"]
const SOCKET_LAYER := 1 << 19    # the socket draws on render layer 20 alone: its seated crystal's light skips it


## Puts the socket's materials on every surface under root; returns the look: {"lamp" (StandardMaterial3D),
## "lamp_light" (OmniLight3D), "state", and the surfaces' materials "bronze", "graphite", "cyan", "amber"}.
static func apply(root: Node3D) -> Dictionary:
	var bronze := ShaderMaterial.new()
	bronze.shader = METAL
	# socket-2: the sheet's polished bronze, darker and more metallic than step 1's (the console's 0.35 read as
	# matte brown plastic beside the sheet), its broad chamfers half worn and the fine bevels bright (the build's
	# UV0 u 0.5 and 1.0); the vents' family: a dark bronze body, bright edges
	bronze.set_shader_parameter("base_color", BRONZE)
	bronze.set_shader_parameter("worn_color", BRONZE_EDGE)
	for p: String in BRONZE_FINISH:  # metallic 0.75: 0.9 read near-black in the hall (b5)
		bronze.set_shader_parameter(p, BRONZE_FINISH[p])
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
	var bay := ShaderMaterial.new()
	bay.shader = BAY
	var by_name := {"socket_bronze": bronze, "socket_graphite": graphite, "socket_cyan": cyan, "socket_amber": amber,
		"socket_lamp": lamp, "socket_bay": bay}
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
	var look := {"lamp": lamp, "lamp_light": light, "state": "", "bronze": bronze, "graphite": graphite, "cyan": cyan,
		"amber": amber, "bay": bay, "claws": 0.0}
	var anchor: Node3D = root.find_child("crystal_anchor", true, false)
	if anchor != null:  # the glow's middle: the seated crystal's (its tip on the anchor, 34.9 cm tall)
		bay.set_shader_parameter("centre", anchor.position + Vector3(0.0, 0.1745, 0.0))
	for side: String in ["claw_r", "claw_l"]:
		var claw: Node3D = root.find_child(side, true, false)
		if claw == null:
			push_warning("socket.gd: no %s node" % side)
		look[side] = claw
	set_state(look, "charged")
	return look


## The claws: 0 closed (on the crystal's cap), 1 open (CLAW_OPEN_DEG up and outward round their hinges, in the
## wall's plane; claw_r turns +Z, claw_l -Z). The game animates open01 (the drawing: open in 0.25 s with a metal
## sound as the crystal is pulled, closed in 0.15 s with a click as a charged one is seated).
static func set_claws(look: Dictionary, open01: float) -> void:
	var k: float = clampf(open01, 0.0, 1.0)
	var a: float = deg_to_rad(CLAW_OPEN_DEG) * k
	for side: String in ["claw_r", "claw_l"]:
		var claw: Node3D = look.get(side)
		if claw != null:
			claw.rotation = Vector3(0.0, 0.0, a if side == "claw_r" else -a)
	look["claws"] = k


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
	if look.has("bay"):  # the bay glows round a charged crystal only
		(look["bay"] as ShaderMaterial).set_shader_parameter("energy", 0.0 if on else BAY_ENERGY)
	look["state"] = state


static func _glow(colour: Color, energy: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.03, 0.04, 0.05)
	m.roughness = 0.25
	m.emission_enabled = true
	m.emission = colour
	m.emission_energy_multiplier = energy
	return m
