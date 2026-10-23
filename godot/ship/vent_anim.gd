extends Node
## The throat vent's animation controller (art #263 station 1, vents-anim1; docs/ship.md "Station 1", "The
## animation"): a small state machine per vent that the game copies. The game sets two inputs and the controller
## drives the seven blades, the marker on the bar, the glows (cool / heat and their well lights), the seams, the lamp
## and the bar:
##   problem: bool   the vent is broken (the round's task is live): CALM -> SLAM -> SHUT
##   hold: 0..1      a player's scanner hold; the marker climbs, the blades open step by step, orange fades to cyan;
##                   at 1 the vent coughs (COUGH), emits `fixed` and breathes again (CALM). It re-arms only once the
##                   game sets problem back to false.
## Use: add it as a child of the placed vent (its GLB root, after the scene's materials are set), call
## setup(vent_root, "station_vent_e") (or leave vent_id set and let _ready find the parent), then set `problem` and
## `hold` each frame. `manual = true` stops _process; a proof calls step(dt) itself at a fixed rate.
## Beauty over motion (the engineer's standing rule): small angles, ease curves, never linear; every amplitude is a
## constant below. The blades stay between shut (0) and CALM_DEG + 20 deg (vents-b3: shut is 20 deg below calm, the
## blades first cut 60 deg below it), and the top blade never above calm: its crest stands under the frame's header
## sill (the clip check).

signal fixed                        # the cough began: the game clears `problem`

enum State { CALM, SLAM, SHUT, COUGH, OPEN }

# --- the blades (degrees of opening from shut; rotation.x = -deg_to_rad(angle) about each blade's hinge) ----------
const SLATS := 7
const CALM_DEG := 20.0              # the calm pose (the builder's CLOSED_DEG / OPEN_RAD: shut is 20 deg below calm)
# CALM: gills breathing, a soft wave running down the blades
const BREATH_PERIOD_S := 3.6        # one breath
const BREATH_DEG := 5.0             # each breath closes from calm by this and opens back (calm is the widest: the look)
const BREATH_WAVE := 0.07           # each blade this much of a breath behind the one above (top to bottom)
const BREATH_IN_S := 1.6            # after the cough the breath's amplitude eases in over this
# SLAM: shut fast, each blade a hair after the one above, then bounce off the stop
const SLAM_S := 0.16                # calm to shut (ease-in: accelerating into the stop)
const SLAM_STAGGER_S := 0.012       # per blade, top to bottom (a clatter, not one plate)
const BOUNCE_DEG := 3.0             # the first rebound off the stop

const BOUNCE_HALF_S := 0.085        # each rebound's length
const BOUNCE_DECAY_S := 0.11        # the rebounds' fall-off (two or three are seen)
# SHUT: the heat makes the shut blades tremble, barely
const TREMBLE_DEG := 0.22
const TREMBLE_HZ := 7.0
# the hold: the blades open with it step by step toward calm (a ratchet)
const HOLD_STEPS := 6
const STEP_MOVE := 0.35             # each step moves in its last 35 % (then rests: a click)
const HOLD_FOLLOW_S := 0.12         # the blades and the marker follow hold with this lag (a falling hold closes them)
# COUGH at hold 1: kicks past calm and snaps back, a stutter; [time s, degrees past calm]
const COUGH := [[0.0, 0.0], [0.07, 10.0], [0.19, 1.0], [0.27, 6.5], [0.38, 0.5], [0.45, 3.5], [0.58, 0.0]]
const COUGH_S := 0.58               # its length (the last key); then CALM, the breath easing in
const COUGH_STAGGER_S := 0.015      # per blade, top to bottom
const COUGH_TOP := -0.2             # the top blade's share of each kick: a dip (it cannot rise into the header sill)
const OPEN_S := 1.2                 # problem cleared without a hold (the game's reset): shut to calm, eased
const MARKER_RETURN_S := 0.5        # after the cough the marker sinks back to the bar's bottom (its lag)
# --- the glows (multipliers of each material's emission energy as the scene set it) --------------------------------
const BREATH_GLOW := 0.35           # the cyan eases by up to this as the blades close (full at calm), swells as they open
const FLASH_GAIN := 2.6             # the orange's hard flash on the slam (x the heat's energy), falling to 1
const FLASH_DECAY_S := 0.3
const PUFF_GAIN := 2.4              # the cough's bright cyan puff (x the cool's energy), falling to 1
const PUFF_DECAY_S := 0.55
const HEAT_FADE := [0.15, 0.95]     # hold over which the orange fades into cyan (smoothstep)
const LAMP_CALM := 0.1              # the red lamp at a tenth when calm (as ship --shoot dims it)
const LAMP_LOW := 0.35              # the problem's pulse between LAMP_LOW and 1
const LAMP_PULSE_HZ := 1.3
const BAR_CALM := 0.6               # the bar's amber when calm; 1 with the problem
const BAND_GAIN := 1.6              # the green band brightens by up to this as the marker nears it
const SEAM_DARK := Color(0.16, 0.09, 0.05)   # the blades' seam strips, unlit (calm)

var vent_id: String = ""
var problem: bool = false
var hold: float = 0.0
var manual: bool = false

var state: int = State.CALM
var angles: PackedFloat32Array = PackedFloat32Array()   # each blade's opening now (degrees), for checks
var marker: float = 0.0                                  # the marker 0..1 now
var heat_mix: float = 0.0                                # 0 cyan .. 1 orange now

var _t: float = 0.0                  # the clock
var _since: float = 0.0              # time in the current state
var _breath_t0: float = 0.0          # the breath's phase origin
var _armed: bool = true
var _hold_f: float = 0.0             # hold, followed
var _from: PackedFloat32Array = PackedFloat32Array()   # each blade's angle as SLAM began
var _p0: float = 0.0                 # when the problem began (the lamp's pulse phase)
var _flash: float = 0.0
var _puff: float = 0.0
var _slats: Array = []
var _marker: Node3D
var _rest_y: float = 0.0
var _travel: float = 0.0
var _cool: MeshInstance3D
var _heat: MeshInstance3D
var _glow: Dictionary = {}           # "cool" / "heat" -> [[material, energy, emission colour]], lights [[light, energy, colour]]
var _lamp: Array = []                # [[material, energy]]
var _bar: Array = []
var _band: Array = []
var _seams: Array = []               # [[material, energy, albedo]]


func _ready() -> void:
	if vent_id != "" and _slats.is_empty() and get_parent() is Node3D:
		setup(get_parent(), vent_id)


func _process(delta: float) -> void:
	if not manual and not _slats.is_empty():
		step(delta)


## Finds the vent's leaves under root by their names (`<id>_slat1..7`, `_marker`, `_cool`, `_heat` and their
## `_light<n>` children, `_lamp`, `_bar`, `_band`; the slats' `__vent_seam` surfaces) and takes over their materials
## (a copy each, as surface overrides). mark_travel: the marker's travel up the glass (ship_interior_vent.MARK_TRAVEL).
func setup(root: Node3D, id: String, mark_travel: float = 0.896) -> void:
	vent_id = id
	_slats.clear()
	for k: int in range(1, SLATS + 1):
		_slats.append(root.find_child("%s_slat%d" % [id, k], true, false))
	_marker = root.find_child(id + "_marker", true, false)
	_rest_y = _marker.position.y if _marker != null else 0.0
	_travel = mark_travel
	_cool = root.find_child(id + "_cool", true, false)
	_heat = root.find_child(id + "_heat", true, false)
	for pair: Array in [["cool", _cool], ["heat", _heat]]:
		var lights: Array = []
		if pair[1] != null:
			for l: Node in (pair[1] as Node).find_children("*_light*", "OmniLight3D", false, false):
				lights.append([l, (l as OmniLight3D).light_energy, (l as OmniLight3D).light_color])
		_glow[pair[0]] = {"mats": _take(pair[1]), "lights": lights}
	_lamp = _take(root.find_child(id + "_lamp", true, false))
	_bar = _take(root.find_child(id + "_bar", true, false))
	_band = _take(root.find_child(id + "_band", true, false))
	_seams.clear()
	for s: Node in _slats:
		_seams.append_array(_take(s, "__vent_seam"))
	angles.resize(SLATS)
	_from.resize(SLATS)
	for k: int in SLATS:
		angles[k] = CALM_DEG
	state = State.CALM
	_since = 0.0
	_breath_t0 = _t - BREATH_IN_S   # the first breath at full amplitude
	_apply()


## A mesh's surfaces' materials (those whose name ends with suffix) as copies set as surface overrides:
## [[material, emission energy, albedo, emission colour]].
func _take(n: Node, suffix: String = "") -> Array:
	var out: Array = []
	var mi: MeshInstance3D = n as MeshInstance3D
	if mi == null or mi.mesh == null:
		return out
	for i: int in mi.mesh.get_surface_count():
		var src: Material = mi.get_surface_override_material(i)
		if src == null:
			src = mi.mesh.surface_get_material(i)
		if not (src is BaseMaterial3D) or (suffix != "" and not src.resource_name.ends_with(suffix)):
			continue
		var m: BaseMaterial3D = (src as BaseMaterial3D).duplicate()
		mi.set_surface_override_material(i, m)
		out.append([m, m.emission_energy_multiplier, m.albedo_color, m.emission])
	return out


## Puts the vent's materials back as the scene had them (the overrides off) and the leaves at calm.
func release(root: Node3D) -> void:
	for suffix: String in ["cool", "heat", "lamp", "bar", "band"] + range(1, SLATS + 1).map(func(k: int) -> String: return "slat%d" % k):
		var mi: MeshInstance3D = root.find_child("%s_%s" % [vent_id, suffix], true, false) as MeshInstance3D
		if mi != null:
			for i: int in mi.mesh.get_surface_count():
				mi.set_surface_override_material(i, null)
	for e: Array in _glow["cool"]["lights"] + _glow["heat"]["lights"]:
		(e[0] as OmniLight3D).light_energy = float(e[1])
		(e[0] as OmniLight3D).light_color = e[2]
	_slats.clear()


func _ease_in(x: float) -> float:
	return x * x * x


func _go(s: int) -> void:
	state = s
	_since = 0.0


## Advances the controller by dt seconds and sets every driven part.
func step(dt: float) -> void:
	_t += dt
	_since += dt
	# hold, followed (exponential), so a falling or jumping input never snaps the blades
	_hold_f += (clampf(hold, 0.0, 1.0) - _hold_f) * (1.0 - exp(-dt / HOLD_FOLLOW_S))
	if not problem:
		_armed = true
	match state:
		State.CALM:
			if problem and _armed:
				_from = angles.duplicate()
				_flash = FLASH_GAIN
				_p0 = _t
				_go(State.SLAM)
		State.SLAM:
			if _since >= SLAM_S + SLAM_STAGGER_S * (SLATS - 1) + 0.45:
				_go(State.SHUT)
		State.SHUT:
			if hold >= 1.0 and _hold_f > 0.995:
				_armed = false
				_puff = PUFF_GAIN
				_go(State.COUGH)
				fixed.emit()
			elif not problem and _hold_f < 0.02:   # cleared without a hold (the game's own reset): open gently
				_from = angles.duplicate()
				_go(State.OPEN)
		State.COUGH:
			if _since >= COUGH_S + COUGH_STAGGER_S * (SLATS - 1):
				_breath_t0 = _t
				_go(State.CALM)
		State.OPEN:
			if _since >= OPEN_S:
				_breath_t0 = _t
				_go(State.CALM)
	_flash = 1.0 + (_flash - 1.0) * exp(-dt / FLASH_DECAY_S) if _flash > 1.0 else 1.0
	_puff = 1.0 + (_puff - 1.0) * exp(-dt / PUFF_DECAY_S) if _puff > 1.0 else 1.0
	for k: int in SLATS:
		angles[k] = _angle(k)
	match state:
		State.CALM, State.OPEN:
			marker *= exp(-dt / MARKER_RETURN_S)
			heat_mix = 1.0 - smoothstep(0.0, 1.0, _since / OPEN_S) if state == State.OPEN else 0.0
		State.SLAM:
			marker = _hold_f
			heat_mix = 1.0
		State.SHUT:
			marker = _hold_f
			heat_mix = 1.0 - smoothstep(float(HEAT_FADE[0]), float(HEAT_FADE[1]), _hold_f)
		State.COUGH:
			marker = 1.0   # held at the top through the stutter
			heat_mix = 0.0
	_apply()


## Blade k's angle (degrees from shut) in the current state.
func _angle(k: int) -> float:
	match state:
		State.CALM:
			var amp: float = BREATH_DEG * smoothstep(0.0, 1.0, (_t - _breath_t0) / BREATH_IN_S)
			var ph: float = maxf((_t - _breath_t0) / BREATH_PERIOD_S - BREATH_WAVE * k, 0.0)
			return CALM_DEG - amp * (0.5 - 0.5 * cos(TAU * ph))
		State.SLAM:
			var s: float = _since - SLAM_STAGGER_S * k
			if s <= 0.0:
				return _from[k]
			if s < SLAM_S:
				return _from[k] * (1.0 - _ease_in(s / SLAM_S))
			var b: float = s - SLAM_S   # off the stop: decaying rebounds, never below shut
			return BOUNCE_DEG * exp(-b / BOUNCE_DECAY_S) * absf(sin(PI * b / BOUNCE_HALF_S))
		State.SHUT:
			var h: float = _hold_f * HOLD_STEPS
			var n: float = floorf(h)
			var f: float = clampf((h - n - (1.0 - STEP_MOVE)) / STEP_MOVE, 0.0, 1.0)
			var stepped: float = minf((n + smoothstep(0.0, 1.0, f)) / HOLD_STEPS, 1.0)
			var shake: float = TREMBLE_DEG * (1.0 - stepped) * (0.6 * sin(TAU * TREMBLE_HZ * _t + 1.7 * k)
				+ 0.4 * sin(TAU * TREMBLE_HZ * 1.73 * _t + 0.9 * k))
			return maxf(CALM_DEG * stepped + shake + TREMBLE_DEG * (1.0 - stepped), 0.0)
		State.COUGH:
			var s: float = clampf(_since - COUGH_STAGGER_S * k, 0.0, COUGH_S)
			for i: int in COUGH.size() - 1:
				if s <= float(COUGH[i + 1][0]):
					var w: float = (s - float(COUGH[i][0])) / (float(COUGH[i + 1][0]) - float(COUGH[i][0]))
					var kick: float = lerpf(float(COUGH[i][1]), float(COUGH[i + 1][1]), smoothstep(0.0, 1.0, w))
					return CALM_DEG + kick * (COUGH_TOP if k == 0 else 1.0)
			return CALM_DEG
		State.OPEN:
			return lerpf(_from[k], CALM_DEG, smoothstep(0.0, 1.0, _since / OPEN_S))
	return CALM_DEG


func _apply() -> void:
	for k: int in SLATS:
		var s: Node3D = _slats[k]
		if s != null:
			s.rotation.x = -deg_to_rad(angles[k])
	if _marker != null:
		_marker.position.y = _rest_y + _travel * marker
	# the glow: orange (the heat panel) while fully hot; else the cool panel, its colour from orange to cyan
	var hot: bool = heat_mix >= 0.999
	if _cool != null:
		_cool.visible = not hot
	if _heat != null:
		_heat.visible = hot
	var breath: float = 0.0
	if state == State.CALM:
		var amp: float = smoothstep(0.0, 1.0, (_t - _breath_t0) / BREATH_IN_S)
		breath = -BREATH_GLOW * amp * (0.5 - 0.5 * cos(TAU * (_t - _breath_t0) / BREATH_PERIOD_S))
	var heat_ref: Array = (_glow["heat"]["mats"] as Array)
	var hc: Color = heat_ref[0][3] if not heat_ref.is_empty() else Color(1, 0.3, 0.02)
	var he: float = float(heat_ref[0][1]) if not heat_ref.is_empty() else 1.0
	for e: Array in _glow["cool"]["mats"]:
		var m: BaseMaterial3D = e[0]
		m.emission = (e[3] as Color).lerp(hc, heat_mix)
		m.emission_energy_multiplier = lerpf(float(e[1]), he, heat_mix) * (1.0 + breath) * _puff
	var hl: Array = _glow["heat"]["lights"]
	for e: Array in _glow["cool"]["lights"]:
		var l: OmniLight3D = e[0]
		var hot_c: Color = hl[0][2] if not hl.is_empty() else hc
		var hot_e: float = float(hl[0][1]) if not hl.is_empty() else float(e[1])
		l.light_color = (e[2] as Color).lerp(hot_c, heat_mix)
		l.light_energy = lerpf(float(e[1]), hot_e, heat_mix) * (1.0 + breath) * _puff
	for e: Array in _glow["heat"]["mats"]:
		(e[0] as BaseMaterial3D).emission_energy_multiplier = float(e[1]) * _flash
	for e: Array in hl:
		(e[0] as OmniLight3D).light_energy = float(e[1]) * _flash
	# the seams glow with the heat, dark bronze when calm
	for e: Array in _seams:
		var m: BaseMaterial3D = e[0]
		m.emission_enabled = heat_mix > 0.01
		m.emission_energy_multiplier = float(e[1]) * heat_mix * _flash
		m.albedo_color = SEAM_DARK.lerp(e[2], heat_mix)
	# the lamp: dim calm, pulsing with the problem (and the flash), easing down as the hold rises
	var lamp: float = LAMP_CALM
	if state == State.SLAM or state == State.SHUT or state == State.OPEN:
		var pulse: float = LAMP_LOW + (1.0 - LAMP_LOW) * pow(0.5 + 0.5 * cos(TAU * LAMP_PULSE_HZ * (_t - _p0)), 2.0)
		lamp = lerpf(LAMP_CALM, maxf(pulse, minf(_flash - 1.0, 1.0)), clampf(heat_mix * 1.5, 0.0, 1.0))
	for e: Array in _lamp:
		(e[0] as BaseMaterial3D).emission_energy_multiplier = float(e[1]) * lamp
	var bar: float = lerpf(BAR_CALM, 1.0, heat_mix)
	for e: Array in _bar:
		(e[0] as BaseMaterial3D).emission_energy_multiplier = float(e[1]) * bar
	var band: float = 1.0 + (BAND_GAIN - 1.0) * smoothstep(0.75, 1.0, marker) + (_puff - 1.0) * 0.4
	for e: Array in _band:
		(e[0] as BaseMaterial3D).emission_energy_multiplier = float(e[1]) * band


# --- the proofs' input script (ship --motion, ship --vent-anim): calm, problem, a hold over 5 s, the cough, calm ---
const DEMO_PROBLEM_S := 6.0         # calm until then
const DEMO_HOLD := [8.0, 13.0]      # the scanner held from .. to (hold 0 -> 1, eased)
const DEMO_S := 22.0                # the clip's length


## The demo's inputs at time s: [problem, hold]. The problem clears when the hold completes (the game on `fixed`).
static func demo(s: float) -> Array:
	var h: float = 0.0
	if s >= float(DEMO_HOLD[0]) and s < float(DEMO_HOLD[1]) + 0.4:
		h = smoothstep(0.0, 1.0, (s - float(DEMO_HOLD[0])) / (float(DEMO_HOLD[1]) - float(DEMO_HOLD[0])))
	return [s >= DEMO_PROBLEM_S and s < float(DEMO_HOLD[1]) + 0.4, h]


## The demo's key moments [time s, label] for the frame sheet.
static func demo_keys() -> Array:
	return [[3.0, "calm: breathing"], [4.8, "calm: the wave down"], [6.07, "problem: slam"], [6.3, "problem: bounce"],
		[7.2, "problem: shut, the lamp"], [9.6, "hold 0.3"], [11.2, "hold 0.7"], [12.9, "hold 1"],
		[13.1, "cough: kick"], [13.35, "cough: snap"], [14.3, "calm again"], [18.0, "calm: breathing"]]
