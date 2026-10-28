extends SceneTree
## The gills' controller's state machine, headless (art #263 gills step 11; tools/tests/test_ship_vent_anim.py):
##   godot --headless --path godot -s res://ship/vent_anim_check.gd
## On a stand-in unit with the GLB's leaf names (four ribs, the cool glow with bands up the well and a light, the
## heat, five seams, the bar and its green band, the lamp) it drives vent_anim.gd at 60 steps a second through every
## transition and checks: the states and the signals (each once, at the right moment), the six clicks climbing from the
## foot, the ribs still while held, the exhale reaching ROCK_DEG, and every rib's pose within +-ROCK_DEG on every
## step before the controller's clamp (the builder's tests check the clearance there); gills step 13: the release at
## GREEN's ends, the latch (a step after the palm left before release()), hold falling to 0 with no release, `fixed`
## while `problem` stays true, a release after `problem` cleared mid-hold, hold jitter around the 0.002 threshold, and
## restore() (the panels back, step() a no-op). Prints "VENT_ANIM_CHECK pass" or the failures and exits 1.

const VentAnim = preload("res://ship/vent_anim.gd")
const ID := "station_vent_e"
const DT := 1.0 / 60.0

var anim: Node
var heard: Array = []
var fails: Array = []
var worst: float = 0.0
var unit: Node3D


func _init() -> void:
	var root: Node3D = Node3D.new()
	root.name = ID + "_x"
	get_root().add_child(root)
	unit = root
	for k: int in range(1, 5):
		_mesh(root, "cover%d" % k, Vector3(-0.6 + 0.34 * k, 0.05, 0.0), Color.BLACK, 0.0)
	var cool: MeshInstance3D = _mesh(root, "cool", Vector3(0, 0.2, 0.05), Color(0.05, 0.55, 1.0), 0.5)
	for k: int in range(2, 7):   # bands up the well, children of the cool (as the GLB)
		var b: MeshInstance3D = _mesh(cool, "cool%d" % k, Vector3(0, 0.45 * (k - 1), 0), Color(0.05, 0.55, 1.0), 0.4)
		b.name = "%s_cool%d" % [ID, k]
	var heat: MeshInstance3D = _mesh(root, "heat", Vector3(0, 0.2, 0.05), Color(1.0, 0.2, 0.02), 0.8)
	for pair: Array in [[cool, Color(0.05, 0.55, 1.0), 0.26], [heat, Color(1.0, 0.2, 0.02), 0.9]]:
		var o: OmniLight3D = OmniLight3D.new()
		o.name = "%s_gap1_light1" % (pair[0] as Node).name
		o.light_color = pair[1]
		o.light_energy = pair[2]
		(pair[0] as Node).add_child(o)
	for k: int in range(1, 6):
		_mesh(root, "seam%d" % k, Vector3(-0.7 + 0.34 * k, 1.4, 0.06), Color(1, 0.2, 0.02), 0.5)
	_mesh(root, "bar", Vector3(0.66, 1.5, -0.04), Color.WHITE, 1.0)
	_mesh(root, "bar_green", Vector3(0.66, 1.81, -0.04), Color.GREEN, 1.0)
	_mesh(root, "bar_top", Vector3(0.66, 1.86, -0.04), Color.WHITE, 1.0)
	_mesh(root, "lamp", Vector3(0.66, 1.97, -0.04), Color.RED, 1.0)
	anim = VentAnim.new()
	anim.manual = true
	root.add_child(anim)
	anim.setup(root, ID)
	for sig: String in ["fixed", "too_early", "missed", "thrown"]:
		anim.connect(sig, func() -> void: heard.append(sig))
	_check()
	print("VENT_ANIM_CHECK worst angle %.4f deg (limit %.1f)" % [worst, VentAnim.ROCK_DEG])
	if fails.is_empty():
		print("VENT_ANIM_CHECK pass")
		quit(0)
	else:
		for f: String in fails:
			print("VENT_ANIM_CHECK fail: " + f)
		quit(1)


func _mesh(parent: Node, suffix: String, at: Vector3, emission: Color, energy: float) -> MeshInstance3D:
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.name = "%s_%s" % [ID, suffix]
	var box: BoxMesh = BoxMesh.new()
	box.size = Vector3(0.1, 0.1, 0.02)
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.emission_enabled = energy > 0.0
	m.emission = emission
	m.emission_energy_multiplier = energy
	box.material = m
	mi.mesh = box
	mi.position = at
	parent.add_child(mi)
	return mi


func _ok(cond: bool, what: String) -> void:
	if not cond:
		fails.append(what)


## Steps the controller for secs with the given inputs; returns [the angles' largest change between two steps over
## the last half, the largest |angle| seen].
func _run(secs: float, problem: bool, hold_from: float = 0.0, hold_to: float = -1.0) -> Array:
	var n: int = int(round(secs / DT))
	var still: float = 0.0
	var peak: float = 0.0
	var prev: PackedFloat32Array = anim.angles.duplicate()
	for i: int in n:
		anim.problem = problem
		anim.hold = hold_from if hold_to < 0.0 else lerpf(hold_from, hold_to, float(i + 1) / n)
		anim.step(DT)
		_track()
		for k: int in anim.angles.size():
			peak = maxf(peak, absf(anim.angles[k]))
			if i >= n / 2:
				still = maxf(still, absf(anim.angles[k] - prev[k]))
		prev = anim.angles.duplicate()
	return [still, peak]


## The worst pose before the clamp (raw_angles): the controller's own sums must stay in range, not the clamp.
func _track() -> void:
	for k: int in anim.raw_angles.size():
		worst = maxf(worst, absf(anim.raw_angles[k]))
		_ok(absf(anim.raw_angles[k] - anim.angles[k]) < 1e-5, "rib %d clamped: pose %.4f" % [k, anim.raw_angles[k]])


## A band's red now by its mesh's name (the override material setup made).
func _red_of(suffix: String) -> float:
	var mi: MeshInstance3D = unit.find_child("%s_%s" % [ID, suffix], true, false) as MeshInstance3D
	var m: Material = mi.get_surface_override_material(0)
	for b: Array in anim._bands:
		if b[0] == m:
			return float(b[5])
	fails.append("no band for %s" % suffix)
	return -1.0


## From any state back to calm with the problem cleared, then the problem live again (PROBLEM, shuddering).
func _fresh() -> void:
	_run(VentAnim.EXHALE_S + VentAnim.RESET_S + VentAnim.RETRY_S + 1.0, false)
	_run(1.0, true)
	heard.clear()


## A hold climbed to v over 1 s and held 0.4 s (the marker settled at v).
func _hold_to(v: float) -> void:
	_run(1.0, true, 0.0, v)
	_run(0.4, true, v)


func _st() -> String:
	return VentAnim.STATE_NAMES[anim.state]


func _check() -> void:
	# calm: breathing, a wave (the ribs differ), nothing heard
	var r: Array = _run(3.0, false)
	_ok(_st() == "calm", "calm: state %s" % _st())
	_ok(r[1] <= VentAnim.BREATH_DEG + 1e-4 and r[1] > 0.5 * VentAnim.BREATH_DEG, "calm: breath peak %.3f" % r[1])
	_ok(absf(anim.angles[0] - anim.angles[3]) > 0.05, "calm: no wave along the ribs")
	_ok(anim.red < 0.01, "calm: red %.3f" % anim.red)
	# the problem: the shudder at (nearly) the full range, red, the lamp up
	r = _run(2.5, true)
	_ok(_st() == "problem", "problem: state %s" % _st())
	_ok(r[1] > 0.85 * VentAnim.ROCK_DEG, "problem: shudder peak %.3f" % r[1])
	_ok(anim.red > 0.97, "problem: red %.3f" % anim.red)
	# the hold: still ribs, six clicks climbing from the foot, the sixth at GREEN's foot
	var g0: float = float(VentAnim.GREEN[0])
	var seen: Array = []
	var foot_red: float = -1.0
	var top_red: float = -1.0
	var n: int = 300
	for i: int in n:
		anim.problem = true
		anim.hold = 0.865 * float(i + 1) / n
		var before: int = anim.clicks
		anim.step(DT)
		_track()
		if anim.clicks != before:
			seen.append([anim.clicks, anim.marker])
		if anim.clicks == 2:   # the last step of two clicks: the foot band (cool2, h 0.2) cyan, the top (cool6) red
			foot_red = _red_of("cool2")
			top_red = _red_of("cool6")
	_ok(_st() == "hold", "hold: state %s" % _st())
	_ok(seen.size() == VentAnim.STEPS, "hold: %d clicks, not %d: %s" % [seen.size(), VentAnim.STEPS, seen])
	for i: int in seen.size():
		_ok(int(seen[i][0]) == i + 1, "hold: click %d out of order" % (i + 1))
		_ok(absf(float(seen[i][1]) - g0 * (i + 1) / VentAnim.STEPS) < 0.02, "hold: click %d at marker %.3f" % [i + 1, seen[i][1]])
	_ok(foot_red >= 0.0 and foot_red < 0.1 and top_red > 0.9,
		"hold: the red did not leave the foot first (two clicks: foot %.3f, top %.3f)" % [foot_red, top_red])
	r = _run(1.0, true, 0.865)
	_ok(r[0] < 1e-4, "hold: the ribs move %.5f deg a step" % r[0])
	_ok(absf(anim.angles[0] - VentAnim.HOLD_DEG) < 0.01, "hold: rib at %.3f, not HOLD_DEG" % anim.angles[0])
	_ok(anim.red < 0.02, "hold: six clicks leave red %.3f" % anim.red)
	_ok(heard.is_empty(), "hold: heard %s" % [heard])
	# release in the green: fixed, the exhale to ROCK_DEG, calm after
	anim.release()
	_ok(heard == ["fixed"], "fixed: heard %s" % [heard])
	_ok(_st() == "exhale", "fixed: state %s" % _st())
	r = _run(1.2, false)
	_ok(r[1] > VentAnim.ROCK_DEG - 0.01, "exhale: peak %.3f" % r[1])
	_ok(absf(anim.angles[0] - anim.angles[3]) < 1e-3, "exhale: the ribs not together")
	_run(VentAnim.EXHALE_S, false)
	_ok(_st() == "calm", "after the exhale: state %s" % _st())
	anim.release()   # a release in calm: nothing
	_ok(heard == ["fixed"], "calm release: heard %s" % [heard])
	# too early
	heard.clear()
	_run(1.0, true)
	_run(1.0, true, 0.0, 0.5)
	_ok(_st() == "hold", "early: state %s" % _st())
	anim.release()
	_ok(heard == ["too_early"], "early: heard %s" % [heard])
	_ok(_st() == "retry", "early: state %s" % _st())
	_run(VentAnim.RETRY_S + 0.6, true)
	_ok(_st() == "problem" and anim.red > 0.9, "early: back to %s, red %.2f" % [_st(), anim.red])
	# missed: past the green
	heard.clear()
	_run(1.0, true, 0.0, 0.96)
	_run(0.3, true, 0.96)
	anim.release()
	_ok(heard == ["missed"], "missed: heard %s" % [heard])
	_ok(_st() == "cough", "missed: state %s" % _st())
	_run(VentAnim.COUGH_S + 0.1, true)
	_ok(_st() == "problem", "missed: back to %s" % _st())
	# held to the top: thrown while held, the release after it ignored, no new hold until hold is back at 0
	heard.clear()
	_run(1.5, true, 0.0, 1.0)
	_run(0.4, true, 1.0)
	_ok(heard == ["thrown"], "thrown: heard %s" % [heard])
	_ok(_st() == "thrown", "thrown: state %s" % _st())
	anim.release()
	_ok(heard == ["thrown"], "thrown: the release after it heard %s" % [heard])
	_run(VentAnim.THROW_S + 0.2, true, 1.0)
	_ok(_st() == "problem", "thrown: back to %s while the palm stays" % _st())
	_run(0.2, true, 0.0)
	_run(0.5, true, 0.0, 0.3)
	_ok(_st() == "hold", "thrown: a new hold after hold 0: %s" % _st())
	# the game clears the problem mid-hold: reset to calm
	_run(0.2, false, 0.3)
	_ok(_st() == "reset", "cleared: state %s" % _st())
	_run(VentAnim.RESET_S + 0.1, false)
	_ok(_st() == "calm" and anim.red < 0.05, "cleared: %s red %.2f" % [_st(), anim.red])
	_cases()
	# the demo (gills step 12): fixed, too early, missed, thrown, in that order, nothing else
	heard.clear()
	var a2: Node = anim
	var f: int = 0
	var fps: float = 24.0
	while f / fps < VentAnim.DEMO_S:
		var inp: Array = VentAnim.demo(f / fps)
		a2.problem = inp[0]
		a2.hold = inp[1]
		for t: float in VentAnim.DEMO_RELEASES:
			if f / fps >= t and (f - 1) / fps < t:
				a2.release()
		a2.step(1.0 / fps)
		_track()
		f += 1
	_ok(heard == VentAnim.DEMO_HEARD, "demo: heard %s" % [heard])
	_ok(worst <= VentAnim.ROCK_DEG + 1e-4, "a rib reached %.4f deg" % worst)
	_restore()


## Gills step 13's cases (the fresh review): the edges of the release's judgement and the game's call orders.
func _cases() -> void:
	var g0: float = float(VentAnim.GREEN[0])
	var g1: float = float(VentAnim.GREEN[1])
	# the release at GREEN's ends (both in) and just outside them, judged on `judged`
	for c: Array in [[g0, "fixed"], [g1, "fixed"], [g0 - 0.001, "too_early"], [g1 + 0.001, "missed"]]:
		_fresh()
		_hold_to(0.865)
		anim.judged = float(c[0])
		anim.release()
		_ok(heard == [c[1]], "release at %.4f: heard %s, not %s" % [c[0], heard, c[1]])
	# the latch: the game zeroes hold and a step runs before release(): the drawn marker sank, the judgement did not
	_fresh()
	_hold_to(0.865)
	anim.hold = 0.0
	anim.step(DT)
	_ok(anim.marker < 0.865 - 0.15 and absf(anim.judged - 0.865) < 0.005,
		"latch: marker %.3f, judged %.3f" % [anim.marker, anim.judged])
	anim.release()
	_ok(heard == ["fixed"], "latch: a good release after a lagging marker heard %s" % [heard])
	# hold falls to 0 with no release(): nothing judged, still HOLD, the marker sinks; a new climb is judged on its own
	_fresh()
	_hold_to(0.865)
	_run(1.0, true, 0.0)
	_ok(heard.is_empty() and _st() == "hold" and anim.marker < 0.01,
		"hold to 0 without a release: heard %s, %s, marker %.3f" % [heard, _st(), anim.marker])
	_hold_to(0.5)
	anim.release()
	_ok(heard == ["too_early"], "hold to 0 then a climb to 0.5: heard %s" % [heard])
	# fixed while the game leaves `problem` true: the exhale, calm, and no re-arm until problem has been false
	_fresh()
	_hold_to(0.865)
	anim.release()
	_run(VentAnim.EXHALE_S + 2.0, true)
	_ok(heard == ["fixed"] and _st() == "calm" and anim.red < 0.05,
		"fixed, problem kept: heard %s, %s, red %.2f" % [heard, _st(), anim.red])
	_run(0.2, false)
	_run(0.5, true)
	_ok(_st() == "problem", "fixed, problem cleared then set: %s" % _st())
	# the problem clears mid-hold, then the palm leaves: reset, the release ignored
	_fresh()
	_hold_to(0.865)
	_run(0.1, false, 0.865)
	anim.release()
	_ok(heard.is_empty() and _st() == "reset", "release after the problem cleared: heard %s, %s" % [heard, _st()])
	# hold jitter around the 0.002 threshold: one hold, no click, no signal; one release, one too_early
	_fresh()
	var states: Dictionary = {}
	for i: int in 60:
		anim.problem = true
		anim.hold = 0.0019 if i % 2 == 0 else 0.0021
		anim.step(DT)
		_track()
		states[_st()] = true
	_ok(states.keys().all(func(k: String) -> bool: return k in ["problem", "hold"]) and _st() == "hold",
		"jitter: states %s, now %s" % [states.keys(), _st()])
	_ok(heard.is_empty() and anim.clicks == 0 and anim.marker < 0.01,
		"jitter: heard %s, clicks %d, marker %.4f" % [heard, anim.clicks, anim.marker])
	anim.release()
	anim.release()
	_ok(heard == ["too_early"], "jitter: two releases heard %s" % [heard])
	_run(VentAnim.EXHALE_S + VentAnim.RESET_S + VentAnim.RETRY_S + 1.0, false)
	_ok(_st() == "calm", "after the cases: %s" % _st())


## restore(): the heat and the cool back as the scene had them, every list cleared, step() a no-op.
func _restore() -> void:
	var heat: Node3D = unit.find_child("%s_heat" % ID, true, false)
	var cool: Node3D = unit.find_child("%s_cool" % ID, true, false)
	_ok(not heat.visible, "restore: the heat shown before restore()")
	anim.restore(unit)
	_ok(heat.visible and cool.visible, "restore: heat %s, cool %s" % [heat.visible, cool.visible])
	_ok(anim._bands.is_empty() and anim._lights.is_empty() and anim._lamp.is_empty() and anim._bar.is_empty()
		and anim._green.is_empty() and anim._emit["steam"].is_empty() and anim.angles.is_empty(),
		"restore: lists left full")
	var mi: MeshInstance3D = unit.find_child("%s_cool2" % ID, true, false)
	_ok(mi.get_surface_override_material(0) == null, "restore: an override left on cool2")
	anim.step(DT)   # no ribs: nothing happens, no error
	_ok(anim.angles.is_empty(), "restore: step() ran without ribs")
