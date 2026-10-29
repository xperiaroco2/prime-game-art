extends Node
## The throat's gill cover, the pilot's reference controller (art #263, 2026-10-29; docs/ship.md "The gill cover
## pilot"): one rigid curved cover on its hinge (tools/blender/ship_interior_cover.py, parts `cover<k>_*` of the
## placed th_wall_e). The game copies it. States:
##   shut     pressed to the wall (0 deg): the thin red line under its open edge, a little vapour now and then
##   gasp     it lifts about GASP_DEG and settles (eased); red flares from under it: the window for the press
##   open     a press during a gasp: it swings to OPEN_DEG with a small overshoot and settles; calm cyan light
##            behind it that never blinks, a puff of vapour; it stays open and no longer gasps
##   cough    a press outside the window: a short shudder, a grey puff, the red line dims for COUGH_S
## Use: add as a child of the placed piece, setup(piece_root, k), then call press() from the game and step(delta) each
## frame (or set `breathing` false and drive gasp() yourself, as cover_row.gd does for a row of five). demo_events()
## is the pilot MP4's timeline.
## The light (step 2, 2026-10-29): two small omnis between the plate and the wall (no shadows, no specular) throw the
## glow onto the wall round the open edge and into the pocket; they never reach the plate's front. A soft additive
## haze billboard held in the gap gives the open pocket its misty scoop. The step-1 halo quad on the wall never showed:
## see docs/ship.md "The gill covers" (the light). `look` holds the variant grid's knobs (LOOK, the pick).

const GASP_DEG := 8.0
const OPEN_DEG := 30.0
const GASP_S := 1.35            # one gasp: up 0.45 s (ease out), a short hang, down (ease in-out), a tiny landing bounce
const GASP_UP := 0.45
const GASP_HANG := 0.22
const BREATH_S := 2.4           # a gasp every 2.4 s while shut
const WINDOW_DEG := 3.0         # a press counts while the cover stands at least this far open in a gasp
const SPRING_W := 9.0           # the open swing: a damped spring (rad/s, damping ratio): about 9 % overshoot
const SPRING_Z := 0.6
const COLOUR_S := 0.35          # red to cyan as it swings
const COUGH_S := 1.0
const RED := Color(1.0, 0.12, 0.04)
const CYAN := Color(0.12, 0.78, 1.0)
const GREY := Color(0.55, 0.58, 0.62)
## the glow (pocket floor) and rim gains over their built strength, and the light's energy, per look
const GLOW := {"shut": 1.8, "gasp": 7.5, "open": 3.2, "cough": 0.15}
const RIM := {"shut": 2.4, "gasp": 5.0, "open": 1.8, "cough": 0.15}
## the spill omnis' energy (each of the two) and the haze's strength per look
const LIGHT := {"shut": 0.03, "gasp": 0.55, "open": 0.42, "cough": 0.0}
const HAZE := {"shut": 0.0, "gasp": 0.35, "open": 1.0, "cough": 0.0}
const PUFFS := 8
const WIDTH := 0.304            # the axis to the open edge (ship_interior_cover.py WIDTH + the axis' 4 mm)
const AXIS_W := 0.013           # the axis off the wall's face
## the variant grid's knobs and their pick (step 2, sheets in <raw>/ship/v5/gills-throat/covers2/grid): spill (the
## omnis' gain), decal (an additive glow quad on the wall, 0 = none), haze (the pocket's mist gain), metal (the
## plate's albedo [r, g, b, metallic, roughness]; null keeps the GLB's), wisp (the shut vapour's strength), range
const LOOK := {"spill": 1.0, "decal": 0.0, "haze": 1.0, "metal": null, "wisp": 1.0, "range": 0.5}

var k: int = 3
var breathing: bool = true
var state: String = "shut"
var angle: float = 0.0          # degrees, outward
var _root: Node3D
var _swing: Array = []          # [Node3D, its rest basis]
var _mats: Dictionary = {}      # part -> [material, built energy]
var look: Dictionary = LOOK.duplicate()
var _lights: Array = []         # the two spill omnis
var _axis: Vector3              # the hinge axis at the cover's middle height, piece space
var _decal: Array = []          # [MeshInstance3D, StandardMaterial3D] or empty
var _haze: Array = []           # [MeshInstance3D, StandardMaterial3D]
var _plate_mat: BaseMaterial3D
var _light: OmniLight3D         # (for info(): the upper spill omni)
var _mist: Array = []           # [MeshInstance3D, StandardMaterial3D]
var _puffs: Array = []          # active puffs: {t0, life, k, size, tint, drift}
var _mirror: float = 1.0
var _edge: Vector3              # the open edge's middle (shut), piece space
var _clock: float = 0.0
var _t_state: float = 0.0       # time in the state
var _gasp_t: float = -1.0       # time into the running gasp (-1: none)
var _next_gasp: float = 1.0
var _from: float = 0.0          # the open swing's start angle
var _cough_t: float = -1.0
var _wisp_t: float = 0.0


func setup(piece: Node3D, slot: int = 3) -> void:
	_root = piece
	k = slot
	_mirror = -1.0 if String(piece.name).begins_with("th_wall_w") else 1.0
	_wisp_t = 0.23 * slot   # the ten covers' wisps out of step
	for part: String in ["plate", "rim", "knuckle"]:
		var n: Node3D = piece.find_child("cover%d_%s*" % [k, part], true, false) as Node3D
		if n != null:
			_swing.append([n, n.basis])
			if part == "plate":
				_axis = n.position
				var src: Material = (n as MeshInstance3D).get_active_material(0) if n is MeshInstance3D else null
				if src is BaseMaterial3D:
					_plate_mat = (src as BaseMaterial3D).duplicate()
					(n as MeshInstance3D).material_override = _plate_mat
	for part: String in ["rim", "glow", "pocket"]:
		_own(part)
	var glow: MeshInstance3D = piece.find_child("cover%d_glow*" % k, true, false) as MeshInstance3D
	var box: AABB = glow.get_aabb() if glow != null else AABB()
	var mid: Vector3 = (glow.position if glow != null else Vector3.ZERO) + box.get_center()
	_edge = mid + Vector3(box.size.x * 0.42 * _mirror, 0.0, 0.0)
	# the spill: two omnis between the plate and the wall, 0.3 m above and below the middle (_place_light moves them
	# with the plate); in front of the wall (the GLB's +z), under the plate's front: they light the wall round the
	# open edge, the pocket and the plate's inside, never its front (no hot spot)
	for i: int in 2:
		var l: OmniLight3D = OmniLight3D.new()
		l.omni_attenuation = 1.6
		l.light_specular = 0.0
		l.light_energy = 0.0
		l.shadow_enabled = false
		piece.add_child(l)
		_lights.append(l)
	_light = _lights[0]
	_haze = _make_glow_quad(piece, true)
	for i: int in PUFFS:
		_mist.append(_make_puff(piece))
	set_look({})


## The variant grid: override LOOK's knobs (spill, decal, haze, metal, wisp, range).
func set_look(over: Dictionary) -> void:
	look = LOOK.duplicate()
	look.merge(over, true)
	for l: OmniLight3D in _lights:
		l.omni_range = float(look["range"])
	if float(look["decal"]) > 0.0 and _decal.is_empty():
		_decal = _make_glow_quad(_root, false)
	if _plate_mat != null and look["metal"] != null:
		var c: Array = look["metal"]
		_plate_mat.albedo_color = Color(c[0], c[1], c[2])
		if c.size() > 3:
			_plate_mat.metallic = c[3]
		if c.size() > 4:
			_plate_mat.roughness = c[4]
	_apply()


## Where the controller put its pieces (piece space and world), for the proof's anim.json.
func info() -> Dictionary:
	var d: Dictionary = {"swing": _swing.size(), "mats": _mats.keys(), "edge": str(_edge)}
	if _light != null:
		d["light"] = str(_light.position)
		d["light_world"] = str(_light.global_position)
		d["axis"] = str(_axis)
	for e: Array in _swing:
		d[String((e[0] as Node3D).name)] = str((e[0] as Node3D).global_position)
	return d


## The game's input: a press. During a gasp's window it opens the cover; otherwise it coughs. Returns "open",
## "cough" or "" (already open).
func press() -> String:
	if state == "open":
		return ""
	if state == "shut" and _gasp_t >= 0.0 and angle >= WINDOW_DEG:
		state = "open"
		_from = angle
		_t_state = 0.0
		_gasp_t = -1.0
		_puff(0.0, 1.6, 0.75, 1.6, 0.0)
		_puff(0.12, 1.3, 0.6, 1.9, 0.1)
		_puff(0.3, 1.0, 0.5, 2.2, -0.05)
		return "open"
	cough()
	return "cough"


## The cough (a wrong press): a short outward shudder (`amount` x 1.6 deg), a grey puff, the line dims for COUGH_S.
var _cough_amp: float = 1.0
func cough(amount: float = 1.0) -> void:
	_cough_t = 0.0
	_cough_amp = amount
	_puff(0.0, 0.5 * amount, 0.35, 0.9, 0.0, GREY)


## The big exhale (cover_row.gd, all five open): three large puffs after `delay`.
func exhale(delay: float = 0.0) -> void:
	_puff(delay, 1.8, 1.0, 2.6, 0.08)
	_puff(delay + 0.15, 1.5, 0.9, 2.4, 0.12)
	_puff(delay + 0.35, 1.2, 0.8, 2.2, 0.16)


## The stills' poses: "shut", "gasp" (at its peak) or "open" (calm), no puffs.
func pose(p: String) -> void:
	reset()
	if p == "gasp":
		_gasp_t = GASP_UP
		angle = GASP_DEG
	elif p == "open":
		state = "open"
		_from = GASP_DEG
		_t_state = 4.0
		angle = OPEN_DEG
	_apply()


func gasp() -> void:
	if state == "shut" and _gasp_t < 0.0:
		_gasp_t = 0.0
		_puff(0.18, 0.8, 0.4, 1.1, 0.0)


## Back to shut (a new round).
func reset() -> void:
	state = "shut"
	angle = 0.0
	_gasp_t = -1.0
	_cough_t = -1.0
	_t_state = 0.0
	_clock = 0.0
	_next_gasp = 1.0
	_puffs.clear()
	_apply()


func step(dt: float) -> void:
	_clock += dt
	_t_state += dt
	if state == "shut":
		if breathing and _clock >= _next_gasp and _gasp_t < 0.0:
			gasp()
			_next_gasp = _clock + BREATH_S
		angle = 0.0
		if _gasp_t >= 0.0:
			_gasp_t += dt
			angle = gasp_angle(_gasp_t)
			if _gasp_t >= GASP_S:
				_gasp_t = -1.0
		_wisp_t += dt
		if _wisp_t >= 1.15:   # the shut cover's breath of vapour now and then
			_wisp_t = 0.0
			_puff(0.0, 0.55 * float(look["wisp"]), 0.3 + 0.06 * float(look["wisp"]), 1.8, 0.02)
	elif state == "open":
		angle = open_angle(_t_state, _from)
		_wisp_t += dt
		if _t_state > 1.6 and _wisp_t >= 0.9:   # open and calm: a soft drift out of the pocket, no flashing
			_wisp_t = 0.0
			_puff(0.0, 0.35, 0.35, 2.4, 0.0)
	if _cough_t >= 0.0:
		_cough_t += dt
		# a shudder outward only: a negative angle would press the plate into the wall
		angle += _cough_amp * 1.6 * absf(sin(_cough_t * 38.0)) * exp(-_cough_t * 9.0) if _cough_t < 0.4 else 0.0
		if _cough_t >= COUGH_S:
			_cough_t = -1.0
	_apply()


## The gasp's angle at time g into it: ease-out up to GASP_DEG, a short hang, ease-in-out down, a small bounce.
static func gasp_angle(g: float) -> float:
	if g <= 0.0:
		return 0.0
	if g < GASP_UP:
		var x: float = g / GASP_UP
		return GASP_DEG * (1.0 - pow(1.0 - x, 3.0))
	if g < GASP_UP + GASP_HANG:
		return GASP_DEG * (1.0 - 0.06 * (g - GASP_UP) / GASP_HANG)
	var down: float = GASP_S - GASP_UP - GASP_HANG - 0.16
	var d: float = (g - GASP_UP - GASP_HANG) / down
	if d < 1.0:
		var e: float = 4.0 * d * d * d if d < 0.5 else 1.0 - pow(-2.0 * d + 2.0, 3.0) / 2.0
		return GASP_DEG * 0.94 * (1.0 - e)
	var b: float = (g - GASP_S + 0.16) / 0.16   # the landing: one small lift and down
	return 0.7 * sin(PI * clampf(b, 0.0, 1.0))


## The open swing at time s after the press, from angle a0: a damped spring to OPEN_DEG (about 9 % overshoot).
static func open_angle(s: float, a0: float) -> float:
	var wd: float = SPRING_W * sqrt(1.0 - SPRING_Z * SPRING_Z)
	var x: float = 1.0 - exp(-SPRING_Z * SPRING_W * s) * (cos(wd * s) + SPRING_Z * SPRING_W / wd * sin(wd * s))
	return a0 + (OPEN_DEG - a0) * x


func _apply() -> void:
	var rad: float = deg_to_rad(angle) * -_mirror   # east: a negative turn about Y takes +x (the open edge) to +z
	for e: Array in _swing:
		(e[0] as Node3D).basis = Basis(Vector3.UP, rad) * (e[1] as Basis)
	var look: String = state
	var colour: Color = RED
	var w: float = 0.0
	if state == "shut":
		w = clampf(angle / GASP_DEG, 0.0, 1.0)
		look = "gasp" if w > 0.0 else "shut"
	elif state == "open":
		w = clampf(_t_state / COLOUR_S, 0.0, 1.0)
		colour = RED.lerp(CYAN, w * w * (3.0 - 2.0 * w))
	var glow: float = lerpf(GLOW["shut"], GLOW["gasp"], pow(w, 1.4)) if state == "shut" else lerpf(GLOW["gasp"], GLOW["open"], w)
	var rim: float = lerpf(RIM["shut"], RIM["gasp"], w) if state == "shut" else lerpf(RIM["gasp"], RIM["open"], w)
	var light: float = lerpf(LIGHT["shut"], LIGHT["gasp"], pow(w, 1.4)) if state == "shut" else lerpf(LIGHT["gasp"], LIGHT["open"], w)
	var haze: float = lerpf(HAZE["shut"], HAZE["gasp"], w) if state == "shut" else lerpf(HAZE["gasp"], HAZE["open"], w)
	if _cough_t >= 0.0:   # the cough: the line dims for a second, back with an ease
		var c: float = clampf(_cough_t / COUGH_S, 0.0, 1.0)
		var dim: float = 1.0 - (1.0 - c * c)
		glow = lerpf(GLOW["cough"], glow, dim)
		rim = lerpf(RIM["cough"], rim, dim)
		light = lerpf(LIGHT["cough"], light, dim)
		haze = lerpf(HAZE["cough"], haze, dim)
	_glow("glow", colour, glow)
	_glow("pocket", colour, glow * 0.55)   # the walls darker than the floor: the pocket reads as a scoop, not a lens
	_glow("rim", colour, rim)
	_place_light(colour, light * float(look["spill"]))
	_quad(_haze, colour, haze * float(look["haze"]) * 0.32)
	_quad(_decal, colour, light / LIGHT["gasp"] * float(look["decal"]) * 0.5)
	_update_puffs(colour)


## The spill omnis and the haze follow the plate: between it and the wall, toward its open edge, never in front of it.
func _place_light(colour: Color, energy: float) -> void:
	var a: float = deg_to_rad(angle)
	var e: Vector3 = Vector3(_mirror, 0.0, 0.0)
	var wall: float = _axis.z - AXIS_W
	var base: Vector3 = Vector3(_axis.x, _axis.y, wall) + e * (WIDTH * cos(a) + 0.025) \
		+ Vector3(0.0, 0.0, 0.010 + WIDTH * sin(a) * 0.45)
	for i: int in _lights.size():
		var l: OmniLight3D = _lights[i]
		l.position = base + Vector3(0.0, 0.3 if i == 0 else -0.3, 0.0)
		l.light_color = colour
		l.light_energy = energy
		l.visible = energy > 0.002
	if not _haze.is_empty():
		(_haze[0] as Node3D).position = Vector3(_axis.x, _axis.y, wall) + e * (WIDTH * cos(a) * 0.62) \
			+ Vector3(0.0, 0.0, WIDTH * sin(a) * 0.35 + 0.004)
	if not _decal.is_empty():
		(_decal[0] as Node3D).position = Vector3(_axis.x, _axis.y, wall + 0.003) + e * (WIDTH * 0.8)


## A soft additive glow quad: the haze (a billboard held in the gap, fading into the wall and the plate) or the
## decal (flat on the wall, facing out of it, no proximity fade: the step-1 halo's suspect).
func _make_glow_quad(piece: Node3D, billboard: bool) -> Array:
	var tex: GradientTexture2D = GradientTexture2D.new()
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	var g: Gradient = Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	g.add_point(0.35, Color(1, 1, 1, 0.5))
	tex.gradient = g
	tex.width = 128
	tex.height = 128
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	m.render_priority = 1
	if billboard:
		m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
		m.billboard_keep_scale = true
		m.proximity_fade_enabled = true
		m.proximity_fade_distance = 0.04
	m.albedo_texture = tex
	m.albedo_color = Color(0, 0, 0, 1)
	var q: QuadMesh = QuadMesh.new()
	q.size = Vector2(0.26, 1.05) if billboard else Vector2(0.7, 1.5)
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.mesh = q
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.visible = false
	piece.add_child(mi)
	return [mi, m]


func _quad(q: Array, colour: Color, kk: float) -> void:
	if q.is_empty():
		return
	(q[1] as StandardMaterial3D).albedo_color = Color(colour.r * kk, colour.g * kk, colour.b * kk, 1.0)
	(q[0] as Node3D).visible = kk > 0.002


func _own(part: String) -> void:
	var mi: MeshInstance3D = _root.find_child("cover%d_%s*" % [k, part], true, false) as MeshInstance3D
	if mi == null:
		return
	var src: Material = mi.get_active_material(0)
	if not (src is BaseMaterial3D):
		return
	var m: BaseMaterial3D = (src as BaseMaterial3D).duplicate()
	mi.material_override = m
	_mats[part] = [m, m.emission_energy_multiplier]


func _glow(part: String, colour: Color, gain: float) -> void:
	if not _mats.has(part):
		return
	var m: BaseMaterial3D = _mats[part][0]
	m.emission = colour
	m.albedo_color = Color(colour.r * 0.25, colour.g * 0.25, colour.b * 0.25)
	m.emission_energy_multiplier = float(_mats[part][1]) * gain


# --- the vapour: soft additive billboards out of the open edge, drifting out and up, tinted by the light ----------
func _make_puff(piece: Node3D) -> Array:
	var tex: GradientTexture2D = GradientTexture2D.new()
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	var g: Gradient = Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	g.add_point(0.4, Color(1, 1, 1, 0.45))
	tex.gradient = g
	tex.width = 128
	tex.height = 128
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.billboard_keep_scale = true
	m.proximity_fade_enabled = true
	m.proximity_fade_distance = 0.03
	m.albedo_texture = tex
	m.albedo_color = Color(0, 0, 0, 0)
	var q: QuadMesh = QuadMesh.new()
	q.size = Vector2(0.22, 0.34)
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.mesh = q
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.visible = false
	piece.add_child(mi)
	return [mi, m]


## A puff after `delay` s: strength s, size grows to `size`, lives `life` s, drifts up by `rise` (m/s) along the edge.
func _puff(delay: float, s: float, size: float, life: float, rise: float, tint: Color = Color(0, 0, 0, 0)) -> void:
	_puffs.append({"t0": _clock + delay, "s": s, "size": size, "life": life, "rise": rise, "tint": tint})
	while _puffs.size() > PUFFS:
		_puffs.pop_front()


func _update_puffs(colour: Color) -> void:
	var done: Array = []
	for i: int in PUFFS:
		var mi: MeshInstance3D = _mist[i][0] if i < _mist.size() else null
		if mi == null:
			continue
		if i >= _puffs.size():
			mi.visible = false
			continue
		var p: Dictionary = _puffs[i]
		var a: float = (_clock - float(p["t0"])) / float(p["life"])
		if a < 0.0:
			mi.visible = false
			continue
		if a >= 1.0:
			mi.visible = false
			done.append(p)
			continue
		var fade: float = smoothstep(0.0, 0.18, a) * (1.0 - smoothstep(0.35, 1.0, a))
		var tint: Color = p["tint"] if (p["tint"] as Color).a > 0.0 else colour.lerp(Color(0.8, 0.85, 0.9), 0.35)
		var open: float = deg_to_rad(angle)
		# out of the gap under the open edge: out of the wall (+z) and back along the plate, rising slowly
		var out: Vector3 = Vector3(0.08 * _mirror * a, float(p["rise"]) * a * float(p["life"]) + 0.03 * a, 0.11 + 0.20 * a)
		var swing: Vector3 = Vector3(-(1.0 - cos(open)) * 0.26 * _mirror, 0.0, sin(open) * 0.26 * 0.6)
		var at: Vector3 = _edge + swing + out
		mi.position = at
		var sc: float = lerpf(0.35, 1.0, sqrt(a)) * float(p["size"]) / 0.3
		mi.scale = Vector3(sc, sc, sc)
		var m: StandardMaterial3D = _mist[i][1]
		var kk: float = float(p["s"]) * fade * 0.5   # additive: the colour carries the strength, the texture the shape
		m.albedo_color = Color(tint.r * kk, tint.g * kk, tint.b * kk, 1.0)
		mi.visible = true
	for p: Dictionary in done:
		_puffs.erase(p)


## The pilot MP4's timeline (10 s): shut with the red line and vapour, three gasps (1.2, 3.6, 6.0 s), the press
## during the third (6.3 s), the open swing with the cyan and the puff, then calm open. [time, event]
static func demo_events() -> Array:
	return [[1.2, "gasp"], [3.6, "gasp"], [6.0, "gasp"], [6.3, "press"]]


const DEMO_S := 10.0
## the key moments for the sheets and stills: [time, label, still name or ""]
static func demo_keys() -> Array:
	return [[0.7, "shut: red line, vapour", "shut"], [1.62, "gasp: up 8 deg, red flare", "gasp"],
		[2.4, "settled shut", ""], [4.02, "gasp 2", ""], [6.3, "press in the gasp", ""],
		[6.62, "swing: overshoot", ""], [7.3, "open: cyan, puff", ""], [9.6, "calm open", "open"]]
