extends Node
## The gills' animation controller (art #263 gills step 11; docs/ship.md "The gills' animation"): a small state
## machine per gills unit that the game copies. Data in, signals out; the game owns the task's rules.
##
## Inputs (set them each frame):
##   problem: bool   the unit is broken (the round's task is live)
##   hold: 0..1      the scanner hold's progress while a palm is on the scanner (0 without a palm)
##   release()       call it once when the palm leaves the scanner
## Signals:
##   fixed           released with the marker inside GREEN: the exhale plays; the game clears `problem`
##   too_early       released below GREEN: the game plays its "try again" sound; the look falls back to the problem
##   missed          released past GREEN (below TOP): the unit coughs steam and stays broken
##   thrown          the hold reached TOP: a hard red shudder and a cough; the game throws the player back a few
##                   metres (and lifts the palm: a release() after `thrown` is ignored)
## The release is judged on `marker` (the drawn marker: hold followed over HOLD_FOLLOW_S), so what the player sees on
## the bar is what counts. After `fixed` the controller re-arms only once the game has set `problem` false; after a
## release or `thrown` a new hold starts only once `hold` has been back to 0.
##
## Use: add it as a child of the placed unit (its GLB root), after the scene's materials and vent_glow.gd's lights are
## set; call setup(unit_root, "station_vent_e") (or set vent_id and let _ready find the parent). `manual = true` stops
## _process: a proof calls step(dt) itself at a fixed rate and runs Godot with --fixed-fps (the particles keep the
## engine's clock). `particles = false` before setup makes none (headless checks).
##
## What it drives: the four ribs `<id>_cover1..4`, each about its vertical axis through its origin (the builder's
## rib_axis), never past ROCK_DEG either way (ship_interior_gills.RIB_ROCK_DEG, whose clearance its tests check); the
## cool glow `<id>_cool` with its mesh children (the well's bands, the slots, the floor strips) and its well lights,
## each by its height from cyan to the heat's red (the `<id>_heat` panel stays hidden: the cool carries both colours,
## so the red can turn cyan band by band); the marker on the bar (made here when the GLB has none); the bar, its green
## band (`bar_green`) and the lamp; and three particle emitters per slot (steam, mist, cough) at each `<id>_seam<k>`.
## Beauty over motion (the engineer's standing rule): sines and smoothsteps, never linear; every amplitude and timing
## is a constant below.

signal fixed
signal too_early
signal missed
signal thrown

enum State { CALM, PROBLEM, HOLD, EXHALE, RETRY, COUGH, THROWN, RESET }
const STATE_NAMES := ["calm", "problem", "hold", "exhale", "retry", "cough", "thrown", "reset"]

# --- the ribs (degrees about each rib's vertical axis; + is the builder's +RIB_ROCK_DEG, mirrored on the w unit) -----
const RIBS := 4
const ROCK_DEG := 4.0               # the most either way (ship_interior_gills.RIB_ROCK_DEG; its clearance is tested)
# CALM: breathing, a small wave along the four
const BREATH_PERIOD_S := 4.2        # one breath
const BREATH_DEG := 1.5             # each rib sways this much either way
const BREATH_WAVE := 0.12           # each rib this much of a breath behind the one by the mouth
const BREATH_IN_S := 1.5            # the breath's amplitude eases in over this when calm begins
const BREATH_GLOW := 0.15           # the cyan swells by up to this with each breath
# PROBLEM: a fast shudder at the full range (two sines whose weights sum to 1: never past ROCK_DEG)
const SHUDDER_HZ := [4.5, 11.0]
const SHUDDER_MIX := [0.8, 0.2]
const SHUDDER_PHASE := 1.3          # radians between neighbouring ribs (not one plate)
const SHAKE_IN_S := 0.25            # the shudder's weight eases in (exponential: an ease-out) ...
const SHAKE_OUT_S := 0.12           # ... and out
const BLEND_S := 0.4                # a state's pose eases in from the angles it began with (smoothstep)
# HOLD: still, a little clenched
const HOLD_DEG := -1.0
const HOLD_FOLLOW_S := 0.06         # the marker follows hold
const STEPS := 6                    # the clicks: the red turns cyan a sixth of the slots' height a click, foot first
const GREEN := [0.808, 0.923]       # the green band on the bar (ship_interior_gills.BAR_GREEN over BAR_H); the sixth
                                    # click lands on its foot: every slot cyan = release now
const TOP := 0.995                  # the marker at the bar's top: thrown
const CLICK_TAU_S := 0.05           # a band's colour after a click (exponential: a quick ease-out, a click)
const FADE_TAU_S := 0.3             # a band's colour after a state change
const CLICK_POP := 0.6              # the cyan flares by this on each click ...
const CLICK_POP_S := 0.25           # ... and settles over this
# EXHALE: all four swing out together to ROCK_DEG, the slots at their brightest, mist from every slot; then calm
const EXHALE_OUT_S := 0.55          # out (cubic ease-out)
const EXHALE_HOLD_S := 1.2          # held out
const EXHALE_BACK_S := 1.8          # back to rest (smoothstep)
const EXHALE_GLOW := 1.2            # the cyan at (1 + this) at the exhale's peak
# RETRY (too early): the shudder grows back, the colour falls back to red
const RETRY_S := 0.9
const RETRY_TAU_S := 0.45
# COUGH (missed): a jolt out, back, a smaller one [time s, degrees]; steam from every slot
const COUGH := [[0.0, 0.0], [0.09, 3.5], [0.24, -1.2], [0.36, 2.2], [0.5, -0.4], [0.62, 0.0]]
const COUGH_S := 0.62
# THROWN (held to the top): a hard shudder, the red flashing, a cough of steam
const THROW_S := 1.2
const THROW_HZ := [8.0, 13.0]
const THROW_FLASH := 0.9            # the red at (1 + this) at the throw, falling over THROW_S
const RESET_S := 1.0                # problem cleared without a fix: back to rest, the colour back to cyan
# --- the light (multipliers of each material's or light's energy as the scene set it) ------------------------------
const RED_GAIN := 1.0               # a band's red: the heat's energy x (the band's cyan / the brightest band's)
const RED_THROB := 0.12             # the red throbs with the lamp by this
const LAMP_CALM := 0.1              # the red lamp at a tenth when calm
const LAMP_LOW := 0.35              # the problem's pulse between LAMP_LOW and 1 ...
const LAMP_PULSE_HZ := 1.3          # ... at this rate; THROWN and past the green faster:
const LAMP_FAST_HZ := 4.0
const BAR_CALM := 0.45              # the bar's white when calm; 1 while the problem or a hold is on
const GREEN_GAIN := 1.8             # the green band brightens by up to this as the marker reaches it
const MARKER_SIZE := [0.07, 0.012, 0.012]   # the marker made here (m: across, up, out)
const MARKER_COLOUR := Color(1.0, 0.96, 0.88)
const MARKER_E := 3.0
const MARKER_RETURN_S := 0.5        # after a release the marker sinks back (exponential)
const SEAM_DARK := Color(0.16, 0.09, 0.05)   # ship --shoot --vent-states' "dark" (ship.gd); unused by the gills
# --- the particles (per slot; five slots) -------------------------------------------------------------------------
const STEAM_PER_SLOT := 6           # the problem's steam, rising (continuous)
const MIST_PER_SLOT := 12           # the exhale's cyan mist (one burst)
const COUGH_PER_SLOT := 10          # the miss's and the throw's steam (one burst)
const STEAM_COLOUR := Color(1.0, 0.86, 0.82, 0.16)
const MIST_COLOUR := Color(0.55, 0.86, 1.0, 0.11)
const COUGH_COLOUR := Color(0.95, 0.92, 0.9, 0.13)
const PUFF_M := 0.22                # a sprite's size (r11 first clip: 0.26 at higher alpha read as cotton balls)
const FADE_M := 0.05                # the sprites fade within this of a surface (0.2 hid the steam by the wall)
const EMIT_OUT_M := 0.06            # the emitters this far out of the wall's face, between the ribs
# The unit's frame in its GLB: x along the wall, y up, +z out of the wall (the builder's v); the builder's (u, v, h)
# maps to (x, z, y), a mirror, so its +RIB_ROCK_DEG about h is -ROCK_DEG about y here (SIDE: e -1, w +1, mirrored)
const OUT := Vector3(0.0, 0.0, 1.0)

var vent_id: String = ""
var problem: bool = false
var hold: float = 0.0
var manual: bool = false
var particles: bool = true

var state: int = State.CALM
var angles: PackedFloat32Array = PackedFloat32Array()   # each rib's angle now (degrees), for checks
var marker: float = 0.0                                  # the marker 0..1 now
var clicks: int = 0                                      # the clicks passed in this hold
var red: float = 0.0                                     # the bands' mean red now (0 cyan .. 1 red)

var _t: float = 0.0
var _since: float = 0.0
var _breath_t0: float = 0.0
var _armed: bool = true
var _need_zero: bool = false
var _shake: float = 0.0
var _pop: float = 0.0
var _active: float = 0.0
var _over: float = 0.0
var _side: float = 1.0
var _from: PackedFloat32Array = PackedFloat32Array()
var _ribs: Array = []                # [node, rest basis]
var _bands: Array = []               # [material, h 0..1, cyan colour, cyan energy, red energy, red now]
var _lights: Array = []              # [light, h 0..1, cyan colour, cyan energy, red colour, red energy, red now]
var _red_c: Color = Color(1.0, 0.2, 0.02)
var _cool: Node3D
var _heat: Node3D
var _lamp: Array = []
var _bar: Array = []
var _green: Array = []
var _marker: MeshInstance3D
var _made: Array = []                # nodes made here (restore() frees them)
var _bar_y: Vector2 = Vector2.ZERO   # the bar's foot and top (unit frame)
var _emit: Dictionary = {"steam": [], "mist": [], "cough": []}


func _ready() -> void:
	if vent_id != "" and _ribs.is_empty() and get_parent() is Node3D:
		setup(get_parent(), vent_id)


func _process(delta: float) -> void:
	if not manual and not _ribs.is_empty():
		step(delta)


## Finds the unit's leaves under root by their names and takes over their materials (a copy each, as surface
## overrides); makes the marker and the particle emitters.
func setup(root: Node3D, id: String) -> void:
	vent_id = id
	_side = 1.0 if id.ends_with("_w") else -1.0
	_ribs.clear()
	for k: int in range(1, RIBS + 1):
		var n: Node3D = _leaf(root, id, "cover%d" % k) as Node3D
		_ribs.append([n, n.transform.basis if n != null else Basis()])
	_cool = _leaf(root, id, "cool") as Node3D
	_heat = _leaf(root, id, "heat") as Node3D
	var red_e: float = 1.0
	if _heat is MeshInstance3D:
		var hm: Material = _mat(_heat as MeshInstance3D, 0)
		if hm is BaseMaterial3D:
			_red_c = (hm as BaseMaterial3D).emission
			red_e = (hm as BaseMaterial3D).emission_energy_multiplier
		_heat.visible = false   # the cool carries the red too
	_bands.clear()
	_lights.clear()
	if _cool != null:
		_cool.visible = true
		var meshes: Array = [_cool] + _cool.find_children("*", "MeshInstance3D", true, false)
		for k: int in range(1, RIBS + 1):   # the ribs' lit flanks (the covers' children) turn with the slots
			for part: String in ["flank%d" % k, "flank%db" % k]:
				var f: Node = root.find_child("%s_%s" % [id, part], true, false)
				if f is MeshInstance3D:
					meshes.append(f)
		var ys: Array = []
		for mi: Node in meshes:
			if mi is MeshInstance3D and (mi as MeshInstance3D).mesh != null:
				ys.append(_frame(root, mi).origin.y + (mi as MeshInstance3D).mesh.get_aabb().get_center().y)
		var y0: float = ys.min() if not ys.is_empty() else 0.0
		var y1: float = ys.max() if not ys.is_empty() else 1.0
		var e_max: float = 0.0
		for i: int in meshes.size():
			if not (meshes[i] is MeshInstance3D) or (meshes[i] as MeshInstance3D).mesh == null:
				continue
			for e: Array in _take(meshes[i]):
				e_max = maxf(e_max, float(e[1]))
				_bands.append([e[0], _norm(_frame(root, meshes[i]).origin.y + (meshes[i] as MeshInstance3D).mesh.get_aabb().get_center().y, y0, y1), e[3], e[1], 0.0, 0.0])
		for b: Array in _bands:
			b[4] = red_e * float(b[3]) / maxf(e_max, 1e-6) * RED_GAIN
		for l: Node in _cool.find_children("*", "OmniLight3D", true, false):
			var o: OmniLight3D = l
			var twin: OmniLight3D = null
			if _heat != null:
				twin = _heat.find_child(String(o.name).replace(String(_cool.name), String(_heat.name)), true, false) as OmniLight3D
			_lights.append([o, _norm(_frame(root, o).origin.y, y0, y1), o.light_color, o.light_energy,
				twin.light_color if twin != null else _red_c, twin.light_energy if twin != null else o.light_energy * 2.0, 0.0])
	_lamp = _take(_leaf(root, id, "lamp"))
	_bar = _take(_leaf(root, id, "bar")) + _take(_leaf(root, id, "bar_top"))
	_green = _take(_leaf(root, id, "bar_green"))
	_make_marker(root, id)
	if particles:
		_make_particles(root, id)
	angles.resize(RIBS)
	_from.resize(RIBS)
	for k: int in RIBS:
		angles[k] = 0.0
		_from[k] = 0.0
	state = State.CALM
	_since = 0.0
	_breath_t0 = _t - BREATH_IN_S   # the first breath at full amplitude
	_apply()


func _norm(y: float, y0: float, y1: float) -> float:
	return clampf((y - y0) / maxf(y1 - y0, 1e-6), 0.0, 0.9999)   # under 1: the sixth click turns the top band too


## n's transform in root's frame (walks the parents; no scene tree needed).
func _frame(root: Node, n: Node) -> Transform3D:
	var t: Transform3D = Transform3D.IDENTITY
	var p: Node = n
	while p != null and p != root:
		if p is Node3D:
			t = (p as Node3D).transform * t
		p = p.get_parent()
	return t


## The leaf `<id>_<suffix>` under root, or null with a warning.
func _leaf(root: Node3D, id: String, suffix: String) -> Node:
	var n: Node = root.find_child("%s_%s" % [id, suffix], true, false)
	if n == null:
		push_warning("vent_anim: no %s_%s under %s (a renamed import?)" % [id, suffix, root.name])
	return n


func _mat(mi: MeshInstance3D, i: int) -> Material:
	var m: Material = mi.get_surface_override_material(i)
	return m if m != null else mi.mesh.surface_get_material(i)


## A mesh's surfaces' materials as copies set as surface overrides: [[material, emission energy, albedo, emission]].
func _take(n: Node) -> Array:
	var out: Array = []
	var mi: MeshInstance3D = n as MeshInstance3D
	if mi == null or mi.mesh == null:
		return out
	for i: int in mi.mesh.get_surface_count():
		var src: Material = _mat(mi, i)
		if not (src is BaseMaterial3D):
			continue
		var m: BaseMaterial3D = (src as BaseMaterial3D).duplicate()
		mi.set_surface_override_material(i, m)
		out.append([m, m.emission_energy_multiplier, m.albedo_color, m.emission])
	return out


## The marker: the GLB's `<id>_marker` if it has one, else a small white-hot bar made here in front of the bar's glass
## (`bar`, `bar_green`, `bar_top`: the foot and top of its travel).
func _make_marker(root: Node3D, id: String) -> void:
	var box: AABB = AABB()
	var first: bool = true
	for part: String in ["bar", "bar_green", "bar_top"]:
		var mi: MeshInstance3D = root.find_child("%s_%s" % [id, part], true, false) as MeshInstance3D
		if mi == null or mi.mesh == null:
			continue
		var b: AABB = _frame(root, mi) * mi.mesh.get_aabb()
		box = b if first else box.merge(b)
		first = false
	_bar_y = Vector2(box.position.y, box.end.y)
	_marker = root.find_child("%s_marker" % id, true, false) as MeshInstance3D
	if _marker != null or first:
		return
	_marker = MeshInstance3D.new()
	_marker.name = "%s_marker" % id
	var mesh: BoxMesh = BoxMesh.new()
	mesh.size = Vector3(MARKER_SIZE[0], MARKER_SIZE[1], MARKER_SIZE[2])
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.albedo_color = MARKER_COLOUR
	m.emission_enabled = true
	m.emission = MARKER_COLOUR
	m.emission_energy_multiplier = MARKER_E
	mesh.material = m
	_marker.mesh = mesh
	_marker.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_marker.position = Vector3(box.get_center().x, _bar_y.x, box.end.z + float(MARKER_SIZE[2]) / 2.0 + 0.001)
	root.add_child(_marker)
	_made.append(_marker)


## Per slot (`<id>_seam1..5`, the gaps' red seams on the well's back) three emitters EMIT_OUT_M out of the wall.
func _make_particles(root: Node3D, id: String) -> void:
	var soft: GradientTexture2D = GradientTexture2D.new()
	var g: Gradient = Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))     # a soft falloff, no edge (a disc reads as a ball)
	g.set_color(1, Color(1, 1, 1, 0))
	g.add_point(0.25, Color(1, 1, 1, 0.6))
	g.add_point(0.6, Color(1, 1, 1, 0.15))
	soft.gradient = g
	soft.fill = GradientTexture2D.FILL_RADIAL
	soft.fill_from = Vector2(0.5, 0.5)
	soft.fill_to = Vector2(1.0, 0.5)
	soft.width = 64
	soft.height = 64
	for k: int in range(1, 9):
		var seam: MeshInstance3D = root.find_child("%s_seam%d" % [id, k], true, false) as MeshInstance3D
		if seam == null or seam.mesh == null:
			break
		var b: AABB = _frame(root, seam) * seam.mesh.get_aabb()
		var c: Vector3 = Vector3(b.get_center().x, b.get_center().y, 0.0) + OUT * EMIT_OUT_M
		var half_h: float = b.size.y * 0.42
		_emit["steam"].append(_emitter(root, "%s_steam%d" % [id, k], c, half_h, STEAM_PER_SLOT, false, STEAM_COLOUR,
			2.6, [0.12, 0.25], 0.32, soft))
		_emit["mist"].append(_emitter(root, "%s_mist%d" % [id, k], c, half_h, MIST_PER_SLOT, true, MIST_COLOUR,
			1.6, [0.5, 0.9], 0.12, soft))
		_emit["cough"].append(_emitter(root, "%s_cough%d" % [id, k], c, half_h * 0.8, COUGH_PER_SLOT, true,
			COUGH_COLOUR, 1.4, [0.5, 0.9], 0.25, soft))


func _emitter(root: Node3D, name: String, at: Vector3, half_h: float, amount: int, burst: bool, colour: Color,
		life: float, speed: Array, rise: float, soft: Texture2D) -> GPUParticles3D:
	var p: GPUParticles3D = GPUParticles3D.new()
	p.name = name
	p.position = at
	p.amount = amount
	p.lifetime = life
	p.one_shot = burst
	p.explosiveness = 0.85 if burst else 0.0
	p.randomness = 0.4
	p.local_coords = false
	p.emitting = false
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.visibility_aabb = AABB(Vector3(-1.0, -2.0, -2.5), Vector3(2.0, 5.0, 3.0))
	var pm: ParticleProcessMaterial = ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = Vector3(0.025, half_h, 0.015)
	pm.direction = OUT + Vector3(0.0, 0.25, 0.0)   # out of the wall, a little up
	pm.spread = 18.0
	pm.initial_velocity_min = float(speed[0])
	pm.initial_velocity_max = float(speed[1])
	pm.gravity = Vector3(0.0, rise, 0.0)     # rising: warm air
	pm.damping_min = 0.4
	pm.damping_max = 0.8
	pm.angle_min = -180.0
	pm.angle_max = 180.0
	pm.scale_min = 0.6
	pm.scale_max = 1.0
	var sc: Curve = Curve.new()
	sc.add_point(Vector2(0.0, 0.35))
	sc.add_point(Vector2(1.0, 1.0), 0.0, 0.0)
	var sct: CurveTexture = CurveTexture.new()
	sct.curve = sc
	pm.scale_curve = sct
	var ramp: Gradient = Gradient.new()
	ramp.set_color(0, Color(1, 1, 1, 0))
	ramp.set_color(1, Color(1, 1, 1, 0))
	ramp.add_point(0.18, Color(1, 1, 1, 1))
	ramp.add_point(0.55, Color(1, 1, 1, 0.6))
	var rt: GradientTexture1D = GradientTexture1D.new()
	rt.gradient = ramp
	pm.color_ramp = rt
	pm.color = colour
	p.process_material = pm
	var quad: QuadMesh = QuadMesh.new()
	quad.size = Vector2(PUFF_M, PUFF_M)
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.vertex_color_use_as_albedo = true
	m.albedo_texture = soft
	m.proximity_fade_enabled = true
	m.proximity_fade_distance = FADE_M
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	quad.material = m
	p.draw_pass_1 = quad
	root.add_child(p)
	_made.append(p)
	return p


## Puts the unit's materials and panels back as the scene had them and frees what setup made.
func restore(root: Node3D) -> void:
	for n: Node in root.find_children("%s_*" % vent_id, "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n
		if mi.mesh != null and not _made.has(mi):
			for i: int in mi.mesh.get_surface_count():
				mi.set_surface_override_material(i, null)
	for e: Array in _lights:
		(e[0] as OmniLight3D).light_color = e[2]
		(e[0] as OmniLight3D).light_energy = float(e[3])
	for r: Array in _ribs:
		if r[0] != null:
			(r[0] as Node3D).transform.basis = r[1]
	for n: Node in _made:
		n.queue_free()
	_made.clear()
	_ribs.clear()


func _go(s: int) -> void:
	_from = angles.duplicate()
	state = s
	_since = 0.0


func _burst(kind: String) -> void:
	for p: GPUParticles3D in _emit[kind]:
		p.restart()


## The palm left the scanner: judges the hold by the marker and emits too_early, fixed or missed.
func release() -> void:
	if state != State.HOLD:
		return
	_need_zero = true
	if marker < float(GREEN[0]):
		_go(State.RETRY)
		too_early.emit()
	elif marker <= float(GREEN[1]):
		_armed = false
		_go(State.EXHALE)
		_burst("mist")
		fixed.emit()
	else:
		_go(State.COUGH)
		_burst("cough")
		missed.emit()


## Advances the controller by dt seconds and sets every driven part.
func step(dt: float) -> void:
	_t += dt
	_since += dt
	var h_in: float = clampf(hold, 0.0, 1.0)
	if h_in < 0.002:
		_need_zero = false
	if not problem:
		_armed = true
	match state:
		State.CALM:
			if problem and _armed:
				_go(State.PROBLEM)
		State.PROBLEM:
			if not problem:
				_go(State.RESET)
			elif h_in >= 0.002 and not _need_zero:
				_go(State.HOLD)
		State.HOLD:
			if not problem:
				_go(State.RESET)
		State.EXHALE:
			if _since >= EXHALE_OUT_S + EXHALE_HOLD_S + EXHALE_BACK_S:
				_breath_t0 = _t
				_go(State.CALM)
		State.RETRY:
			if _since >= RETRY_S:
				_go(State.PROBLEM)
		State.COUGH:
			if _since >= COUGH_S:
				_go(State.PROBLEM)
		State.THROWN:
			if _since >= THROW_S:
				_go(State.PROBLEM)
		State.RESET:
			if _since >= RESET_S:
				_breath_t0 = _t
				_go(State.CALM)
	# the marker and the clicks
	if state == State.HOLD:
		marker += (h_in - marker) * (1.0 - exp(-dt / HOLD_FOLLOW_S))
		var c: int = 0
		for k: int in range(1, STEPS + 1):
			if marker >= float(GREEN[0]) * k / STEPS - 1e-6:
				c = k
		if c > clicks:
			_pop = 1.0
		clicks = c
		_over = smoothstep(float(GREEN[1]), TOP, marker)
		if marker >= TOP:
			_need_zero = true
			_go(State.THROWN)
			_burst("cough")
			thrown.emit()
	else:
		marker *= exp(-dt / MARKER_RETURN_S)
		_over = 0.0
		if state != State.EXHALE:
			clicks = 0
	_pop *= exp(-dt / CLICK_POP_S)
	# the shudder's weight
	var shake_to: float = 1.0 if state == State.PROBLEM or state == State.RETRY else 0.0
	var tau: float = RETRY_TAU_S if state == State.RETRY else (SHAKE_IN_S if shake_to > _shake else SHAKE_OUT_S)
	_shake += (shake_to - _shake) * (1.0 - exp(-dt / tau))
	var busy: bool = state in [State.PROBLEM, State.HOLD, State.RETRY, State.COUGH, State.THROWN]
	_active += ((1.0 if busy else 0.0) - _active) * (1.0 - exp(-dt / FADE_TAU_S))
	for k: int in RIBS:
		var a: float = _shake * ROCK_DEG * _shudder(k, SHUDDER_HZ, SHUDDER_MIX, SHUDDER_PHASE) + (1.0 - _shake) * _pose(k)
		angles[k] = clampf(a, -ROCK_DEG, ROCK_DEG)
	# the colours: each band's red eases toward its target
	var red_to: float = 1.0 if state in [State.PROBLEM, State.RETRY, State.COUGH, State.THROWN] else 0.0
	var ctau: float = CLICK_TAU_S if state == State.HOLD else (RETRY_TAU_S if state == State.RETRY else
		(CLICK_TAU_S if state == State.THROWN else FADE_TAU_S))
	var w: float = 1.0 - exp(-dt / ctau)
	var sum: float = 0.0
	for b: Array in _bands:
		b[5] = float(b[5]) + (_red_target(float(b[1]), red_to) - float(b[5])) * w
		sum += float(b[5])
	for l: Array in _lights:
		l[6] = float(l[6]) + (_red_target(float(l[1]), red_to) - float(l[6])) * w
	red = sum / _bands.size() if not _bands.is_empty() else red_to
	# the steam rises while the slots are mostly red
	for p: GPUParticles3D in _emit["steam"]:
		p.emitting = red > 0.5 and state != State.CALM
	_apply()


## A band's red target at height h (0 foot .. 1 top): the hold turns a sixth a click from the foot; past the green the
## red comes back from the top.
func _red_target(h: float, red_to: float) -> float:
	if state != State.HOLD:
		return red_to
	if h * STEPS >= clicks or h > 1.0 - _over:
		return 1.0
	return 0.0


func _shudder(k: int, hz: Array, mix: Array, phase: float) -> float:
	return (float(mix[0]) * sin(TAU * float(hz[0]) * _t + phase * k)
		+ float(mix[1]) * sin(TAU * float(hz[1]) * _t + 2.1 * phase * k))


func _ease_out(x: float) -> float:
	var y: float = 1.0 - clampf(x, 0.0, 1.0)
	return 1.0 - y * y * y


## Rib k's pose (degrees) in the current state, before the shudder's weight.
func _pose(k: int) -> float:
	var blend: float = smoothstep(0.0, 1.0, _since / BLEND_S)
	match state:
		State.CALM:
			var amp: float = BREATH_DEG * smoothstep(0.0, 1.0, (_t - _breath_t0) / BREATH_IN_S)
			return amp * sin(TAU * ((_t - _breath_t0) / BREATH_PERIOD_S - BREATH_WAVE * k))
		State.PROBLEM:
			return lerpf(_from[k], 0.0, blend)
		State.HOLD:
			return lerpf(_from[k], HOLD_DEG, blend)
		State.EXHALE:
			if _since < EXHALE_OUT_S:
				return lerpf(_from[k], ROCK_DEG, _ease_out(_since / EXHALE_OUT_S))
			var back: float = (_since - EXHALE_OUT_S - EXHALE_HOLD_S) / EXHALE_BACK_S
			return ROCK_DEG * (1.0 - smoothstep(0.0, 1.0, back))
		State.RETRY:
			return _from[k]
		State.COUGH:
			return lerpf(_from[k], 0.0, blend) + _keys(COUGH, _since)
		State.THROWN:
			var hard: float = ROCK_DEG * _shudder(k, THROW_HZ, [0.75, 0.25], 2.0)
			var env: float = 1.0 - smoothstep(THROW_S * 0.6, THROW_S, _since)
			return lerpf(_from[k], hard, smoothstep(0.0, 1.0, _since / 0.08)) * env
		State.RESET:
			return lerpf(_from[k], 0.0, smoothstep(0.0, 1.0, _since / RESET_S))
	return 0.0


## [time, value] keys at s, smoothstep between them.
func _keys(keys: Array, s: float) -> float:
	for i: int in keys.size() - 1:
		if s <= float(keys[i + 1][0]):
			var w: float = (s - float(keys[i][0])) / (float(keys[i + 1][0]) - float(keys[i][0]))
			return lerpf(float(keys[i][1]), float(keys[i + 1][1]), smoothstep(0.0, 1.0, clampf(w, 0.0, 1.0)))
	return float(keys[-1][1])


## The exhale's swell 0..1 (the ribs' swing out, as a share of ROCK_DEG).
func _exhale() -> float:
	if state != State.EXHALE:
		return 0.0
	if _since < EXHALE_OUT_S:
		return _ease_out(_since / EXHALE_OUT_S)
	return 1.0 - smoothstep(0.0, 1.0, (_since - EXHALE_OUT_S - EXHALE_HOLD_S) / EXHALE_BACK_S)


func _apply() -> void:
	for k: int in RIBS:
		var r: Array = _ribs[k]
		if r[0] != null:
			(r[0] as Node3D).transform.basis = Basis(Vector3.UP, _side * deg_to_rad(angles[k])) * (r[1] as Basis)
	if _marker != null:
		_marker.position.y = _bar_y.x + float(MARKER_SIZE[1]) / 2.0 + (_bar_y.y - _bar_y.x - float(MARKER_SIZE[1])) * marker
		_marker.visible = state == State.HOLD or marker > 0.003
	# the lamp's pulse, faster for the throw and past the green
	var fast: bool = state == State.THROWN or _over > 0.0
	var hz: float = LAMP_FAST_HZ if fast else LAMP_PULSE_HZ
	var pulse: float = LAMP_LOW + (1.0 - LAMP_LOW) * pow(0.5 + 0.5 * cos(TAU * hz * _t), 2.0)
	var breath: float = 0.0
	if state == State.CALM:
		var amp: float = smoothstep(0.0, 1.0, (_t - _breath_t0) / BREATH_IN_S)
		breath = BREATH_GLOW * amp * (0.5 + 0.5 * sin(TAU * (_t - _breath_t0) / BREATH_PERIOD_S))
	var cyan_gain: float = 1.0 + breath + EXHALE_GLOW * _exhale() + CLICK_POP * _pop
	var flash: float = 1.0 + THROW_FLASH * (1.0 - smoothstep(0.0, THROW_S, _since)) if state == State.THROWN else 1.0
	var red_gain: float = (1.0 + RED_THROB * (pulse - 0.5)) * flash
	for b: Array in _bands:
		var m: BaseMaterial3D = b[0]
		var r: float = float(b[5])
		m.emission = (b[2] as Color).lerp(_red_c, r)
		m.emission_energy_multiplier = lerpf(float(b[3]) * cyan_gain, float(b[4]) * red_gain, r)
	for l: Array in _lights:
		var o: OmniLight3D = l[0]
		var r2: float = float(l[6])
		o.light_color = (l[2] as Color).lerp(l[4], r2)
		o.light_energy = lerpf(float(l[3]) * cyan_gain, float(l[5]) * red_gain, r2)
	var lamp: float = lerpf(LAMP_CALM, pulse * flash, clampf(red * 1.2, 0.0, 1.0))
	for e: Array in _lamp:
		(e[0] as BaseMaterial3D).emission_energy_multiplier = float(e[1]) * lamp
	var bar: float = lerpf(BAR_CALM, 1.0, _active)
	for e: Array in _bar:
		(e[0] as BaseMaterial3D).emission_energy_multiplier = float(e[1]) * bar
	var near: float = smoothstep(float(GREEN[0]) - 0.1, float(GREEN[0]), marker)
	for e: Array in _green:
		(e[0] as BaseMaterial3D).emission_energy_multiplier = float(e[1]) * lerpf(bar, GREEN_GAIN, near)


# --- the proofs' input script (ship --vent-anim): pass 1 calm, the problem, a hold with its six clicks, the release in
# the green (the exhale), calm; pass 2 the problem, a hold to the top, thrown ---------------------------------------
const DEMO_S := 30.0
const DEMO_PROBLEM_S := 4.5                          # pass 1's problem begins
const DEMO_PROBLEM := [[4.5, 14.0], [21.0, 30.0]]    # problem on from .. to (pass 1: the game clears it on `fixed`)
const DEMO_HOLD := [[8.5, 13.5, 0.865], [23.0, 27.0, 1.0]]   # the palm from .. to: hold 0 -> the value (the game's
                                                             # clock: linear), then kept until the release
const DEMO_RELEASES := [14.0, 27.6]                  # the palm leaves (pass 2: after `thrown`, ignored)


## The demo's inputs at time s: [problem, hold].
static func demo(s: float) -> Array:
	var p: bool = false
	for r: Array in DEMO_PROBLEM:
		p = p or (s >= float(r[0]) and s < float(r[1]))
	var h: float = 0.0
	for i: int in DEMO_HOLD.size():
		var d: Array = DEMO_HOLD[i]
		if s >= float(d[0]) and s < float(DEMO_RELEASES[i]):
			h = minf((s - float(d[0])) / (float(d[1]) - float(d[0])), 1.0) * float(d[2])
	return [p, h]


## The demo's key moments [time s, label] for the frame sheet: one per state.
static func demo_keys() -> Array:
	return [[3.0, "calm: breathing"], [6.6, "problem: shudder, red, steam"], [10.3, "hold: two clicks"],
		[13.8, "hold: six clicks, in the green"], [14.5, "release in the green: the exhale"],
		[19.5, "calm again"], [26.9, "pass 2: past the green"], [27.4, "held to the top: thrown"]]
