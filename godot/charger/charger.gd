extends RefCounted
## The ship's crystal charger's look (art#263's stations; two, on the lens rooms' aft walls): puts the metal and light
## materials on an imported crystal_charger.glb by its glTF material names (the bronze and graphite are the start
## console's console_metal.gdshader, shared, not forked), finds its leaves and drives them. The leaves, each a node
## with its pivot on its axis: `carrier` (under the crystal; rises RISE and spins round its vertical axis; its child
## `crystal_anchor` is where the crystal's tip sits), `track_ring` (spins round the crystal's axis with the inner
## prong pair), `button` (presses TRAVEL in along its +Z, the spot's normal). The lightning and the crystal's glow are
## the game's; the crystal is the built energy_crystal.glb with its own crystal.gd look.
## The charger draws on render layer 20 alone (CHARGER_LAYER): seat_crystal() takes that layer off the crystal's own
## light, which otherwise burns the bronze white a few centimetres away (the socket's way, art#263); the charger's
## own soft cyan light (`glow`) stands in for it while charging. Use with preload (no class cache in a `-s` script);
## every apply() makes the charger its own materials.
##
##   const Charger = preload("charger.gd")
##   var look: Dictionary = Charger.apply(model)
##   Charger.seat_crystal(look, crystal, crystal_look)   # the crystal on the carrier's anchor
##   Charger.set_state(look, "charging")                 # "idle" | "charging" | "charged"
##   Charger.set_carrier(look, rise01, angle)            # each frame while charging (angle in radians)
##   Charger.set_ring(look, angle)
##   Charger.set_pressed(look, true)

const METAL := preload("res://console/console_metal.gdshader")

const CHARGER_LAYER := 1 << 19   # render layer 20: the crystal's own light skips it (seat_crystal)
const RISE := 0.06               # the carrier's travel up (m; the drawing's RISE)
const TRAVEL := 0.01             # the button's travel in (m)
const CYAN := Color(0.0, 0.45, 1.0)  # charger-3: deeper (b5 0.62 read pale blue-white in the room)
const AMBER := Color(1.0, 0.42, 0.0)  # charger-3: toward the socket's (1, 0.5, 0); b5's 0.22 read red
## per state: the cyan lights' energy, the amber lights', the button lens's, the glow light's
## (charger-2: 3 to 4.6 bleached the wide strips white under AgX; charger-3: brighter again, a deeper cyan)
const STATES := {"idle": [2.4, 2.2, 2.2, 0.0], "charging": [3.2, 2.4, 1.2, 0.5], "charged": [3.0, 1.6, 2.6, 0.25]}
## the bronze: the crystal socket's step 3 (art#263 socket-3: socket.gd BRONZE and BRONZE_FINISH on the shared
## console_metal.gdshader), so the three stations match: a warmer polished copper-bronze, the faces lighter or darker
## by their facing, a broad wave for glints, the chamfers worn bright
const BRONZE := Color(0.5, 0.38, 0.24)
const BRONZE_EDGE := Color(1.0, 0.9, 0.7)
const BRONZE_FINISH := {"metallic": 0.75, "roughness": 0.3, "wear": 1.4, "lift": 0.08, "mottle": 0.3, "grain": 0.06,
	"rough_grain": 0.06, "rough_mottle": 0.15, "edge_polish": 0.25, "shade": 0.3, "dent": 0.0, "dent_scale": 45.0,
	"wave": 0.3, "wave_scale": 8.0}


## Puts the charger's materials on every surface under root and finds its leaves; returns the look: {"cyan",
## "amber", "lens" (StandardMaterial3D), "glow" (OmniLight3D), "carrier", "ring", "button", "anchor" (Node3D),
## "carrier_rest", "button_rest" (Vector3), "state"}.
static func apply(root: Node3D) -> Dictionary:
	var bronze := ShaderMaterial.new()
	bronze.shader = METAL
	bronze.set_shader_parameter("base_color", BRONZE)
	bronze.set_shader_parameter("worn_color", BRONZE_EDGE)
	for p: String in BRONZE_FINISH:
		bronze.set_shader_parameter(p, BRONZE_FINISH[p])
	var graphite := ShaderMaterial.new()
	graphite.shader = METAL
	graphite.set_shader_parameter("base_color", Color(0.272, 0.276, 0.293))
	graphite.set_shader_parameter("worn_color", Color(0.634, 0.626, 0.618))
	graphite.set_shader_parameter("metallic", 0.75)
	graphite.set_shader_parameter("roughness", 0.38)
	var steel := StandardMaterial3D.new()  # the legs' piston rods: polished dark steel
	steel.albedo_color = Color(0.5, 0.52, 0.56)
	steel.metallic = 0.85
	steel.roughness = 0.2
	var cyan := _light(CYAN)
	var amber := _light(AMBER)
	var lens := _light(Color(0.05, 0.75, 1.0))
	lens.albedo_color = Color(0.05, 0.4, 0.6)
	lens.clearcoat_enabled = true
	lens.clearcoat = 1.0
	var by_name := {"charger_bronze": bronze, "charger_graphite": graphite, "charger_cyan": cyan,
		"charger_amber": amber, "charger_lens": lens, "charger_steel": steel}
	for m: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if m.mesh == null:
			continue
		m.layers = CHARGER_LAYER  # the room's lights reach every layer; the crystal's skips this one
		m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		for i: int in m.mesh.get_surface_count():
			var src: Material = m.mesh.surface_get_material(i)
			var key: String = src.resource_name if src != null else ""
			if by_name.has(key):
				m.set_surface_override_material(i, by_name[key])
			else:
				push_warning("charger.gd: no look for surface material '%s'" % key)
	var old: Node = root.get_node_or_null(NodePath("ChargerGlow"))  # a second apply() replaces the light
	if old != null:
		root.remove_child(old)
		old.free()
	var carrier: Node3D = root.find_child("carrier", true, false)
	var ring: Node3D = root.find_child("track_ring", true, false)
	var button: Node3D = root.find_child("button", true, false)
	var anchor: Node3D = root.find_child("crystal_anchor", true, false)
	var glow := OmniLight3D.new()
	glow.name = "ChargerGlow"
	glow.light_color = Color(0.3, 0.78, 1.0)
	glow.omni_range = 1.6
	glow.omni_attenuation = 1.6
	glow.shadow_enabled = false
	root.add_child(glow)
	glow.position = Vector3(0.0, 1.13, 0.535)  # at the crystal's middle (the model's frame: front +Z, metres)
	var look := {"cyan": cyan, "amber": amber, "lens": lens, "glow": glow, "carrier": carrier, "ring": ring,
		"button": button, "anchor": anchor, "carrier_rest": carrier.position if carrier else Vector3.ZERO,
		"button_rest": button.position if button else Vector3.ZERO, "state": "idle"}
	set_state(look, "idle")
	return look


static func _light(colour: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.03, 0.03, 0.035)
	m.roughness = 0.25
	m.emission_enabled = true
	m.emission = colour
	return m


## The charger's state: "idle" (no charging: the carrier down, the lights at rest), "charging" (the cyan bright, the
## glow on; the game moves the carrier and the ring), "charged" (the carrier down, the cyan full, the amber low).
static func set_state(look: Dictionary, state: String) -> void:
	var s: Array = STATES[state]
	look["state"] = state
	(look["cyan"] as StandardMaterial3D).emission_energy_multiplier = s[0]
	(look["amber"] as StandardMaterial3D).emission_energy_multiplier = s[1]
	(look["lens"] as StandardMaterial3D).emission_energy_multiplier = s[2]
	(look["glow"] as OmniLight3D).light_energy = s[3]
	(look["glow"] as OmniLight3D).visible = s[3] > 0.0
	if state != "charging":
		set_carrier(look, 0.0, 0.0)


## The carrier: rise01 0 at rest .. 1 up RISE; angle round its vertical axis (radians). The crystal on its anchor
## follows.
static func set_carrier(look: Dictionary, rise01: float, angle: float) -> void:
	var c: Node3D = look["carrier"]
	if c == null:
		return
	c.position = (look["carrier_rest"] as Vector3) + Vector3(0.0, RISE * clampf(rise01, 0.0, 1.0), 0.0)
	c.rotation = Vector3(0.0, angle, 0.0)


## The track ring with the inner prongs, round the crystal's axis (radians; 0: the prongs left and right).
static func set_ring(look: Dictionary, angle: float) -> void:
	var r: Node3D = look["ring"]
	if r != null:
		r.rotation = Vector3(0.0, angle, 0.0)


## The start button pressed in (TRAVEL along -Z, into the charger) or out.
static func set_pressed(look: Dictionary, on: bool) -> void:
	var b: Node3D = look["button"]
	if b != null:
		b.position = (look["button_rest"] as Vector3) - Vector3(0.0, 0.0, TRAVEL if on else 0.0)


## Puts a crystal (its root, with its crystal.gd look) on the carrier's anchor, its tip on the anchor, and takes the
## charger's layer off the crystal's own light.
static func seat_crystal(look: Dictionary, crystal: Node3D, crystal_look: Dictionary) -> void:
	var anchor: Node3D = look["anchor"]
	if crystal.get_parent() != null:
		crystal.get_parent().remove_child(crystal)
	anchor.add_child(crystal)
	crystal.transform = Transform3D.IDENTITY
	var omni: OmniLight3D = crystal_look.get("omni")
	if omni != null:
		omni.light_cull_mask = omni.light_cull_mask & ~CHARGER_LAYER
