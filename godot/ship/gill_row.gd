extends Node
## The throat gills' reference controller (art #263, 2026-10-28; docs/ship.md "The throat's gills"): one throat
## side's row of five crescent slits and its button (tools/blender/ship_interior_gills.py, piece th_gills_e /
## th_gills_w). The game copies it. Each slit has two dark shutter leaves (`gill<k>_leaf_a`, the inner one, and
## `gill<k>_leaf_b`, under the rim), built open; they slide SLIDE along the wall to meet over the glowing filaments.
##   calm    open, the filaments and the back cyan, a soft cyan mist
##   open    the same, brighter (the vent blowing)
##   gasp    the leaves 60 % open, the filaments red-orange, an orange mist (it snatches air)
##   shut    the leaves closed: a dark crescent, its seam line dim cyan
##   fault   the leaves closed, the seam line bright red (the slit needs a repair)
## Use: add as a child of the placed piece (after the scene's materials are set), setup(piece_root), then pose()
## or set_slit() / set_open() / flash_ring(). demo(t) is the 6 s proof's timeline on a fixed clock.

const SLIDE := 0.123
const GASP_OPEN := 0.6
const WORKING := 3
const CYAN := Color(0.05, 0.72, 1.0)
const RED := Color(1.0, 0.16, 0.03)
const SEAM_CYAN := Color(0.1, 0.6, 1.0)
const SEAM_RED := Color(1.0, 0.06, 0.02)
const WHITE := Color(0.95, 0.97, 1.0)
const FIL_GAIN := {"calm": 1.0, "open": 1.3, "gasp": 1.2, "shut": 0.0, "fault": 0.0}
const SEAM_GAIN := {"calm": 0.0, "open": 0.0, "gasp": 0.6, "shut": 0.25, "fault": 1.6}
## step 6: the lights stand in front of the wall now (they hung behind it), so a third as strong: at the old values
## the whole band went cyan
const LIGHT_ENERGY := {"calm": 0.08, "open": 0.13, "gasp": 0.13, "shut": 0.0, "fault": 0.02}
## step 6: the mist and the slit's light hung behind the wall: the throat is the piece's +z (the band leans to +z),
## not -z. Now both stand in front of the slit, the mist a soft add MIST_OUT out from the glow's middle.
const MIST := {"calm": 0.2, "open": 0.32, "gasp": 0.26, "shut": 0.0, "fault": 0.0}
const MIST_OUT := 0.22

var _root: Node3D
var _mats: Dictionary = {}       # node name -> [StandardMaterial3D override, its built emission energy]
var _leaves: Dictionary = {}     # slit -> {"a": Node3D, "b": Node3D}
var _rest: Dictionary = {}       # leaf node -> its built (open) position
var _lights: Dictionary = {}     # slit -> OmniLight3D
var _mists: Dictionary = {}      # slit -> [MeshInstance3D, its material]
var _mirror: float = 1.0


func setup(piece: Node3D) -> void:
	_root = piece
	_mirror = -1.0 if String(piece.name).begins_with("th_gills_w") else 1.0
	for k: int in range(1, 6):
		_leaves[k] = {}
		for side: String in ["a", "b"]:
			var n: Node3D = piece.find_child("gill%d_leaf_%s*" % [k, side], true, false) as Node3D
			if n != null:
				_leaves[k][side] = n
				_rest[n] = n.position
			_own("gill%d_seam_%s" % [k, side])
		for part: String in ["fil", "glow"]:
			_own("gill%d_%s" % [k, part])
		var glow: MeshInstance3D = piece.find_child("gill%d_glow*" % k, true, false) as MeshInstance3D
		if glow == null:
			continue
		var box: AABB = glow.get_aabb()
		var at: Vector3 = glow.position + box.get_center()
		at.y = glow.position.y + box.position.y + box.size.y * 0.42   # the slit's middle, below the bend
		var out: Vector3 = Vector3(0.0, 0.0, 1.0)                      # out of the wall into the throat (the GLB's +z)
		var light: OmniLight3D = OmniLight3D.new()
		light.position = at + out * 0.3
		light.omni_range = 0.8
		light.omni_attenuation = 1.4
		light.light_energy = 0.0
		light.shadow_enabled = false
		piece.add_child(light)
		_lights[k] = light
		_mists[k] = _make_mist(piece, at + out * MIST_OUT + Vector3(-0.2 * _mirror, 0.0, 0.0))
	_own("btn_ring")


## A soft billboard puff in front of the slit, drifting toward the mouth (the convex side), additive.
func _make_mist(piece: Node3D, at: Vector3) -> Array:
	var tex: GradientTexture2D = GradientTexture2D.new()
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	var g: Gradient = Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	g.add_point(0.45, Color(1, 1, 1, 0.35))
	tex.gradient = g
	tex.width = 128
	tex.height = 128
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.proximity_fade_enabled = true
	m.proximity_fade_distance = 0.15
	m.no_depth_test = false
	m.albedo_texture = tex
	m.albedo_color = Color(0, 0, 0, 0)
	var q: QuadMesh = QuadMesh.new()
	q.size = Vector2(0.45, 0.8)
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.mesh = q
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.position = at
	mi.visible = false
	piece.add_child(mi)
	return [mi, m, at]


func _own(pname: String) -> void:
	var mi: MeshInstance3D = _root.find_child(pname + "*", true, false) as MeshInstance3D
	if mi == null:
		return
	var src: Material = mi.get_active_material(0)
	if not (src is BaseMaterial3D):
		return
	var m: BaseMaterial3D = (src as BaseMaterial3D).duplicate()
	mi.material_override = m
	_mats[pname] = [m, m.emission_energy_multiplier]


func _glow(pname: String, colour: Color, gain: float) -> void:
	if not _mats.has(pname):
		return
	var e: Array = _mats[pname]
	var m: BaseMaterial3D = e[0]
	m.emission = colour
	m.albedo_color = Color(colour.r * 0.3, colour.g * 0.3, colour.b * 0.3) if gain > 0.0 else Color(0.02, 0.02, 0.025)
	m.emission_energy_multiplier = float(e[1]) * gain


## Slit k's leaves: 0 shut, 1 open (as built).
func set_open(k: int, x: float) -> void:
	var shut: float = SLIDE * (1.0 - x) * _mirror
	for side: String in _leaves.get(k, {}):
		var n: Node3D = _leaves[k][side]
		n.position = _rest[n] + Vector3((-shut if side == "a" else shut), 0.0, 0.0)


## Slit k's look: state "calm", "open", "gasp", "shut" or "fault"; mix (0..1) blends a gasp's red toward cyan;
## open_x (-1: the state's own) the leaves' opening; puff (0..1) the mist's drift.
func set_slit(k: int, state: String, mix: float = 0.0, open_x: float = -1.0, puff: float = 0.0) -> void:
	var colour: Color = RED.lerp(CYAN, mix) if state == "gasp" else CYAN
	var fil: float = float(FIL_GAIN[state])
	_glow("gill%d_fil" % k, colour, fil)
	_glow("gill%d_glow" % k, colour, fil)
	var seam: Color = SEAM_CYAN if state == "shut" else SEAM_RED
	for side: String in ["a", "b"]:
		_glow("gill%d_seam_%s" % [k, side], seam, float(SEAM_GAIN[state]))
	if open_x < 0.0:
		open_x = 1.0 if state in ["calm", "open"] else (GASP_OPEN if state == "gasp" else 0.0)
	set_open(k, open_x)
	if _lights.has(k):
		var l: OmniLight3D = _lights[k]
		l.light_color = colour if fil > 0.0 else SEAM_RED
		l.light_energy = float(LIGHT_ENERGY[state]) * (open_x if fil > 0.0 else 1.0)
	if _mists.has(k):
		var mi: MeshInstance3D = _mists[k][0]
		var m: StandardMaterial3D = _mists[k][1]
		var a: float = float(MIST[state]) * open_x
		mi.visible = a > 0.001
		m.albedo_color = Color(colour.r * a, colour.g * a, colour.b * a, 1.0)
		mi.position = (_mists[k][2] as Vector3) + Vector3(-0.08 * puff * _mirror, 0.03 * puff, 0.04 * puff)


## The button's ring: 0 its calm cyan, 1 the press's white flash.
func flash_ring(t: float) -> void:
	_glow("btn_ring", CYAN.lerp(WHITE, t), 1.0 + 2.5 * t)


## A view's pose: {"slits": {"3": "open", ...}, "ring": 0..1} (a slit left out: calm).
func pose(spec: Dictionary) -> void:
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
## The proof's timeline: [opening 0..1, slit 3's state, its red-to-cyan mix, ring flash 0..1, label] at t seconds.
## fault (shut, red line) -> the gasp (half open, red, fluttering) -> shut -> the press (ring white) -> open, a
## touch past 1 -> settle.
static func demo(t: float) -> Array:
	if t < 0.9:
		return [0.0, "fault", 0.0, 0.0, "shut, fault line"]
	if t < 1.2:
		return [GASP_OPEN * _ease_out((t - 0.9) / 0.3), "gasp", 0.0, 0.0, "gasp"]
	if t < 1.8:
		return [GASP_OPEN + 0.06 * sin((t - 1.2) * TAU * 2.0), "gasp", 0.0, 0.0, "gasp"]
	if t < 2.1:
		return [GASP_OPEN * (1.0 - _ease_in_out((t - 1.8) / 0.3)), "gasp", 0.0, 0.0, "shut"]
	var flash: float = 0.0
	if t >= 2.8 and t < 3.3:
		flash = 1.0 - _ease_in_out((t - 2.8) / 0.5)
	if t < 3.0:
		return [0.0, "fault", 0.0, flash, "shut" if t < 2.8 else "press"]
	if t < 3.75:
		var x: float = _ease_out((t - 3.0) / 0.75)
		return [1.04 * x, "gasp", x, flash, "open, a touch past"]
	if t < 4.3:
		var y: float = _ease_in_out((t - 3.75) / 0.55)
		return [lerpf(1.04, 1.0, y), "open", 1.0, flash, "settle"]
	return [1.0, "open", 1.0, 0.0, "open"]


## Applies demo(t) to the working slit (the others calm).
func play_demo(t: float) -> String:
	var d: Array = demo(t)
	for k: int in range(1, 6):
		if k != WORKING:
			set_slit(k, "calm", 0.0, -1.0, fmod(t * 0.3 + k * 0.2, 1.0))
	var st: String = d[1]
	var open_x: float = float(d[0])
	var puff: float = clampf((t - 3.0) / 3.0, 0.0, 1.0) if open_x > 0.5 else 0.0
	set_slit(WORKING, st, float(d[2]), open_x, puff)
	flash_ring(float(d[3]))
	return String(d[4])


const ROW_S := 10.0
const ROW_T0 := 0.4                 # the first breath's start (s)
const ROW_BEAT := 0.42              # one slit's breath (s)
const ROW_ORDER := [1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4, 5, 4, 3, 2, 1]   # the breath runs 1-2-3-4-5-4-3-2...
const ROW_PRESS := [2, 7, 11, 12, 16]    # the beats (indices into ROW_ORDER) the player presses in: each a shut slit's gasp
const ROW_PRESS_AT := 0.45          # where in the gasp the press lands (its fraction)
const ROW_EXHALE := 0.5             # the exhale this long after the fifth slit opened


## The press times: slit k -> when it was pressed open.
static func row_presses() -> Dictionary:
	var out: Dictionary = {}
	for i: int in ROW_PRESS:
		out[int(ROW_ORDER[i])] = ROW_T0 + (i + ROW_PRESS_AT) * ROW_BEAT
	return out


## The engineer's mechanic on the whole row (a scripted 10 s demo): all five shut; the breath runs along the row
## (1-2-3-4-5-4-3-2...), each shut slit it reaches gasps (half open, red-orange); a press during a shut slit's gasp
## opens it for good (red to cyan, a touch past, settle; the ring flashes white); an open slit the breath reaches
## brightens; all five open, the row exhales (the mist puffs out) and rests calm. -> the beat's label.
func play_row(t: float) -> String:
	var pressed: Dictionary = row_presses()
	var last: float = 0.0
	for k: int in pressed:
		last = maxf(last, float(pressed[k]))
	var exhale: float = last + ROW_EXHALE
	var beat: int = int(floor((t - ROW_T0) / ROW_BEAT)) if t >= ROW_T0 else -1
	var on: int = int(ROW_ORDER[beat]) if beat >= 0 and beat < ROW_ORDER.size() and t < exhale else 0
	var p: float = (t - ROW_T0 - beat * ROW_BEAT) / ROW_BEAT
	var ring: float = 0.0
	var label: String = "breath %d" % on if on > 0 else "shut"
	for k: int in range(1, 6):
		if t >= exhale:
			var e: float = t - exhale
			var x: float = 1.0 + 0.04 * sin(clampf(e / 1.2, 0.0, 1.0) * PI)
			set_slit(k, "open" if e < 1.6 else "calm", 1.0, x, clampf(e / 1.6, 0.0, 1.0))
			label = "exhale" if e < 1.6 else "calm"
		elif pressed.has(k) and t >= float(pressed[k]):
			var d: float = t - float(pressed[k])
			ring = maxf(ring, 1.0 - _ease_in_out(d / 0.5))
			if d < 0.45:
				var y: float = _ease_out(d / 0.45)
				set_slit(k, "gasp", y, lerpf(GASP_OPEN * sin(ROW_PRESS_AT * PI), 1.04, y))
			elif d < 0.9:
				set_slit(k, "open", 1.0, lerpf(1.04, 1.0, _ease_in_out((d - 0.45) / 0.45)))
			else:
				set_slit(k, "open" if k == on else "calm", 1.0, 1.0, 0.5 + 0.5 * sin(t * 1.9 + k * 1.3))   # no wrap: the mist sways
			if d < 0.5:
				label = "press: %d opens" % k
		elif k == on:
			set_slit(k, "gasp", 0.0, GASP_OPEN * sin(clampf(p, 0.0, 1.0) * PI))
		else:
			set_slit(k, "fault", 0.0, 0.0)
	flash_ring(ring)
	return label
