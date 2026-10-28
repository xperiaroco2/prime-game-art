extends Node
## The throat gills' reference controller (art #263, 2026-10-28; docs/ship.md "The throat's gills"): one throat
## side's row of five slits and its button (tools/blender/ship_interior_gills.py, piece th_gills_e / th_gills_w).
## The game copies it. Each slit shows a state; the east's slit 3 has the working lip (two leaves, `gill3_lip_lo`
## and `gill3_lip_hi`, each with its origin on its piece of the hinge):
##   calm    shut, the gap's seam dim cyan, the filaments dark
##   fault   shut, the seam red (the slit needs a repair)
##   gasp    the lip at GASP_DEG, the filaments and a small light red (it snatches air)
##   open    the lip at OPEN_DEG, the filaments and the light cyan
## Use: add as a child of the placed piece (after the scene's materials are set), setup(piece_root), then pose()
## or set_slit() / set_lip() / flash_ring(). demo(t) is the 6 s proof's timeline on a fixed clock.

const OPEN_DEG := 25.0
const GASP_DEG := 8.0
const OVERSHOOT_DEG := 28.0
const WORKING := 3
## the leaves' hinge axes in the east piece's frame (Godot x, y up, z into the throat): the lower leaf's hinge is
## vertical, the upper one's runs up the lean (ship_interior_gills.lip_hinges; the test checks they match)
const AXIS_LO := Vector3(0.0, 1.0, 0.0)
const AXIS_HI := Vector3(0.0, 0.8395702, 0.5432513)
const CYAN := Color(0.0, 0.62, 1.0)
const RED := Color(1.0, 0.09, 0.02)
const WHITE := Color(0.95, 0.97, 1.0)
const FIL_GAIN := {"calm": 0.0, "fault": 0.15, "gasp": 2.2, "open": 1.6}
const SEAM_GAIN := {"calm": 1.0, "fault": 6.0, "gasp": 6.0, "open": 2.0}
const LIGHT_ENERGY := {"calm": 0.0, "fault": 0.0, "gasp": 0.5, "open": 0.35}

var _root: Node3D
var _mats: Dictionary = {}       # node name -> [StandardMaterial3D override, its built emission energy]
var _leaves: Dictionary = {}     # "lo"/"hi" -> Node3D
var _lights: Dictionary = {}     # slit -> OmniLight3D
var _mirror: float = 1.0


func setup(piece: Node3D) -> void:
	_root = piece
	_mirror = -1.0 if String(piece.name).begins_with("th_gills_w") else 1.0
	for leaf: String in ["lo", "hi"]:
		var n: Node = piece.find_child("gill%d_lip_%s*" % [WORKING, leaf], true, false)
		if n != null:
			_leaves[leaf] = n
	for k: int in range(1, 6):
		for part: String in ["fil", "seam"]:
			_own("gill%d_%s" % [k, part])
		var fil: MeshInstance3D = piece.find_child("gill%d_fil*" % k, true, false) as MeshInstance3D
		if fil != null:
			var light: OmniLight3D = OmniLight3D.new()
			var box: AABB = fil.get_aabb()
			light.position = fil.position + box.get_center() + Vector3(0, 0, 0.12)
			light.omni_range = 0.9
			light.omni_attenuation = 1.6
			light.light_energy = 0.0
			light.shadow_enabled = false
			piece.add_child(light)
			_lights[k] = light
	_own("btn_ring")


func _own(pname: String) -> void:
	var mi: MeshInstance3D = _root.find_child(pname + "*", true, false) as MeshInstance3D
	if mi == null:
		return
	var src: Material = mi.get_active_material(0)
	if not (src is BaseMaterial3D):
		return
	var m: BaseMaterial3D = (src as BaseMaterial3D).duplicate()
	mi.material_override = m
	_mats[pname] = [m, m.emission_energy_multiplier, m.emission, m.albedo_color]


func _glow(pname: String, colour: Color, gain: float) -> void:
	if not _mats.has(pname):
		return
	var e: Array = _mats[pname]
	var m: BaseMaterial3D = e[0]
	m.emission = colour
	m.albedo_color = Color(colour.r * 0.25, colour.g * 0.25, colour.b * 0.25) if gain > 0.0 else Color(0.02, 0.02, 0.025)
	m.emission_energy_multiplier = float(e[1]) * gain


## The working lip's angle in degrees from shut (both leaves).
func set_lip(deg: float) -> void:
	for leaf: String in _leaves:
		var axis: Vector3 = AXIS_LO if leaf == "lo" else AXIS_HI
		axis.x *= _mirror
		(_leaves[leaf] as Node3D).transform.basis = Basis(axis.normalized(), deg_to_rad(deg) * _mirror)


## Slit k's state: "calm", "fault", "gasp" or "open"; mix (0..1) blends a gasp's red toward the open cyan.
func set_slit(k: int, state: String, mix: float = 0.0) -> void:
	var colour: Color = CYAN if state in ["calm", "open"] else RED
	if state == "gasp" and mix > 0.0:
		colour = RED.lerp(CYAN, mix)
	_glow("gill%d_fil" % k, colour, float(FIL_GAIN[state]))
	_glow("gill%d_seam" % k, colour, float(SEAM_GAIN[state]))
	if _lights.has(k):
		(_lights[k] as OmniLight3D).light_color = colour
		(_lights[k] as OmniLight3D).light_energy = float(LIGHT_ENERGY[state])


## The button's ring: 0 its calm cyan, 1 the press's white flash.
func flash_ring(t: float) -> void:
	_glow("btn_ring", CYAN.lerp(WHITE, t), 1.0 + 2.5 * t)


## A view's pose: {"lip": deg, "slits": {"3": "open", ...}, "ring": 0..1}.
func pose(spec: Dictionary) -> void:
	set_lip(float(spec.get("lip", 0.0)))
	var slits: Dictionary = spec.get("slits", {})
	for k: int in range(1, 6):
		set_slit(k, String(slits.get(str(k), "calm")))
	flash_ring(float(spec.get("ring", 0.0)))


static func _ease_out(x: float) -> float:
	return 1.0 - pow(1.0 - clampf(x, 0.0, 1.0), 3.0)


static func _ease_in_out(x: float) -> float:
	x = clampf(x, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)


const DEMO_S := 6.0
## The proof's timeline: [lip deg, slit 3's state, its red-to-cyan mix, ring flash 0..1, label] at t seconds.
## shut (fault) -> the gasp (8 deg, red) -> shut -> the press (ring white) -> open, over to 28 deg -> settle at 25.
static func demo(t: float) -> Array:
	if t < 0.9:
		return [0.0, "fault", 0.0, 0.0, "shut, fault seam"]
	if t < 1.2:
		return [GASP_DEG * _ease_out((t - 0.9) / 0.3), "gasp", 0.0, 0.0, "gasp"]
	if t < 1.8:
		return [GASP_DEG + 0.6 * sin((t - 1.2) * TAU * 2.0), "gasp", 0.0, 0.0, "gasp"]
	if t < 2.1:
		return [GASP_DEG * (1.0 - _ease_in_out((t - 1.8) / 0.3)), "fault", 0.0, 0.0, "shut"]
	if t < 2.8:
		return [0.0, "fault", 0.0, 0.0, "shut"]
	var flash: float = 0.0
	if t >= 2.8 and t < 3.3:
		flash = 1.0 - _ease_in_out((t - 2.8) / 0.5)
	if t < 3.0:
		return [0.0, "fault", 0.0, flash, "press"]
	if t < 3.75:
		var x: float = _ease_out((t - 3.0) / 0.75)
		return [OVERSHOOT_DEG * x, "gasp", x, flash, "open, over to 28"]
	if t < 4.3:
		var y: float = _ease_in_out((t - 3.75) / 0.55)
		return [lerpf(OVERSHOOT_DEG, OPEN_DEG, y), "open", 1.0, flash, "settle at 25"]
	return [OPEN_DEG + 0.3 * sin((t - 4.3) * TAU * 0.5), "open", 1.0, 0.0, "open"]


## Applies demo(t) to the working slit (the others calm).
func play_demo(t: float) -> String:
	var d: Array = demo(t)
	set_lip(float(d[0]))
	for k: int in range(1, 6):
		if k != WORKING:
			set_slit(k, "calm")
	var st: String = d[1]
	set_slit(WORKING, "gasp" if st == "gasp" else st, float(d[2]))
	if st == "gasp" and float(d[2]) >= 1.0:
		set_slit(WORKING, "open")
	flash_ring(float(d[3]))
	return String(d[4])
