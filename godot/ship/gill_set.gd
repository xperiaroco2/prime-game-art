extends Node
## The throat's gill set (art #263, 2026-10-29; the engineer's pick, prime-game-design
## ideas/ship-components/slits-lamps/set_plate.jpg; docs/ship.md "The gill set"): the reference controller the game
## copies. Five static crescent niches on th_wall_e (`gill<k>_scoop|glow|edge`, k = 1..5 from the mouth), a light bar
## over each (`gill<k>_bar_glow`), the groove (`groove_glow`) and the button (`btn_ring`). NOTHING MOVES:
## - a niche glows red while shut, calm cyan once open (the colour eases over EASE_S);
## - the bars: red over a shut slit, cyan over an open one; ONE white bar runs ORDER (1-2-3-4-5-4-3-2), STEP_S a step,
##   over open slits too;
## - press(): flips the slit under the white bar (shut opens with a puff of steam, open shuts again);
## - all five open: a big steam cloud that stays (GPUParticles3D, emitting while all are open).
## Each niche lights the wall round it with a shadowless omni in front of it (no specular hot spot).
## API: setup(piece), step(delta), press() -> "open" / "shut", pose(open, runner), reset(), info(); `time_scale` scales
## the steam (the proof's frame-by-frame render sets it from the real frame time).

const RED := Color(1.0, 0.12, 0.04)
const CYAN := Color(0.1, 0.85, 1.0)
const WHITE := Color(1.0, 0.96, 0.9)
const STEP_S := 0.6
const ORDER: Array = [0, 1, 2, 3, 4, 3, 2, 1]
const EASE_S := 0.25
const DEMO_S := 14.0
# the glows' emission energies (absolute) and the lights; the look knobs
# step 2 (the look pass): "grad" a single gradient over the three parts (NICHE_SHADER: "rim" at the hole's edge down to
# "floor" at the scoop's bottom, "power" the rim's falloff), else the three bands' energies; "albedo" the niches' base
# colour x (dark inside); bars and the groove saturated (their base colour a tenth of the glow)
# The pick (grid_sheet.png, variant "dark"): dark bands with a saturated lip, the closest to set_plate.jpg's dark scoops
const LOOK: Dictionary = {"grad": false, "rim": 1.5, "floor": 0.04, "power": 1.5, "scoop": 0.03, "glow": 0.15,
	"edge": 1.0, "albedo": 0.015, "bar": 0.8, "white": 1.8, "groove": 0.8, "light": 0.12, "light_range": 0.75,
	"light_out": 0.16, "puff": 0.55, "cloud": 0.42}
const NICHE_SHADER := """
shader_type spatial;
uniform vec3 colour : source_color = vec3(1.0, 0.12, 0.04);
uniform float rim = 1.5;
uniform float floor_e = 0.04;
uniform float power = 1.5;
uniform float albedo = 0.04;
uniform vec3 plane_p;
uniform vec3 plane_n;
uniform float depth = 0.065;
varying float d;
void vertex() {
	d = clamp(dot(plane_p - VERTEX, plane_n) / depth, 0.0, 1.0);
}
void fragment() {
	ALBEDO = colour * albedo;
	ROUGHNESS = 0.45;
	METALLIC = 0.0;
	EMISSION = colour * mix(floor_e, rim, pow(1.0 - d, power));
}
"""

var time_scale: float = 1.0
var look: Dictionary = LOOK.duplicate()
var open: Array = [false, false, false, false, false]
var runner: int = 0              # ORDER's index under the white bar
var _root: Node3D
var _out: Vector3 = Vector3(0, 0, 1)   # out of the wall, piece space
var _mats: Array = []            # per slit {part: material}
var _bars: Array = []            # per slit the bar's material
var _lights: Array = []
var _puffs: Array = []           # per slit GPUParticles3D (one shot)
var _clouds: Array = []        # per slit GPUParticles3D (held while all five are open)
var _shaders: Array = []       # per slit the gradient ShaderMaterial
var _groove: StandardMaterial3D
var _mix: Array = [0.0, 0.0, 0.0, 0.0, 0.0]   # 0 red .. 1 cyan, easing to open[k]
var _clock: float = 0.0
var _mids: Array = []            # per slit the niche's middle on the wall's face, piece space
var _sizes: Array = []           # per slit the niche's size (x along, y up)


func setup(piece: Node3D) -> void:
	_root = piece
	var bar1: MeshInstance3D = _mesh("gill1_bar_glow")
	var scoop1: MeshInstance3D = _mesh("gill1_glow")
	if bar1 != null and scoop1 != null:   # the niches lie behind the wall's face, the bars in front: that is "out"
		var dz: float = _centre(bar1).z - _centre(scoop1).z
		_out = Vector3(0, 0, 1.0 if dz > 0.0 else -1.0)
	var wall_z: float = _centre(bar1).z - _out.z * 0.002 if bar1 != null else 0.0
	for k: int in 5:
		var m: Dictionary = {}
		for part: String in ["scoop", "glow", "edge"]:
			var mat: StandardMaterial3D = _own("gill%d_%s" % [k + 1, part])
			if mat != null:
				m[part] = mat
		_mats.append(m)
		_bars.append(_own("gill%d_bar_glow" % (k + 1)))
		var glow: MeshInstance3D = _mesh("gill%d_glow" % (k + 1))
		var box: AABB = _box(glow) if glow != null else AABB()
		var mid: Vector3 = box.get_center()
		mid.z = wall_z
		_mids.append(mid)
		_sizes.append(Vector2(box.size.x, box.size.y))
		var l: OmniLight3D = OmniLight3D.new()
		l.position = mid + _out * float(LOOK["light_out"])
		l.omni_range = float(LOOK["light_range"]) * (0.8 + 0.25 * box.size.y)
		l.omni_attenuation = 1.3
		l.light_specular = 0.0
		l.shadow_enabled = false
		piece.add_child(l)
		_lights.append(l)
		_puffs.append(_particles(mid + _out * 0.02, Vector3(0.03, box.size.y * 0.32, 0.01), 28, 1.8, true))
		_clouds.append(_particles(mid + _out * 0.03, Vector3(0.05, box.size.y * 0.36, 0.02), 26, 3.6, false))
		var sh: ShaderMaterial = ShaderMaterial.new()
		var shader: Shader = Shader.new()
		shader.code = NICHE_SHADER
		sh.shader = shader
		if glow != null:   # the wall's plane in the niche meshes' own space (they share the piece's frame or not)
			sh.set_shader_parameter("plane_p", glow.to_local(_root.to_global(mid)))
			var n: Vector3 = (glow.global_basis.inverse() * _root.global_basis * _out).normalized()
			sh.set_shader_parameter("plane_n", n)
		_shaders.append(sh)
	_groove = _own("groove_glow")
	reset()
	set_look({})


## The variant grid: override LOOK's knobs.
func set_look(over: Dictionary) -> void:
	look = LOOK.duplicate()
	look.merge(over, true)
	for k: int in 5:
		for part: String in ["scoop", "glow", "edge"]:
			var mi: MeshInstance3D = _mesh("gill%d_%s" % [k + 1, part])
			if mi != null and _mats[k].has(part):
				mi.material_override = _shaders[k] if bool(look["grad"]) else _mats[k][part]
	_apply()


func info() -> Dictionary:
	return {"open": open.duplicate(), "runner": ORDER[runner] + 1, "out": [_out.x, _out.y, _out.z],
		"mids": _mids.map(func(v: Vector3) -> Array: return [snappedf(v.x, 0.001), snappedf(v.y, 0.001), snappedf(v.z, 0.001)])}


func slit() -> int:
	return int(ORDER[runner])


func press() -> String:
	var k: int = slit()
	open[k] = not open[k]
	if open[k]:
		(_puffs[k] as GPUParticles3D).restart()
		(_puffs[k] as GPUParticles3D).emitting = true
	_hold()
	return "open" if open[k] else "shut"


func _hold() -> void:
	var all_open: bool = not open.has(false)
	for c: GPUParticles3D in _clouds:
		c.emitting = all_open


func pose(opened: Array, at: int) -> void:
	for k: int in 5:
		open[k] = opened.has(k + 1) or opened.has(float(k + 1))   # (JSON numbers are floats)
		_mix[k] = 1.0 if open[k] else 0.0
	runner = maxi(0, ORDER.find(at - 1))
	_clock = runner * STEP_S + 0.3
	_hold()
	_apply()


func reset() -> void:
	open = [false, false, false, false, false]
	_mix = [0.0, 0.0, 0.0, 0.0, 0.0]
	_clock = 0.0
	runner = 0
	for p: GPUParticles3D in _puffs + _clouds:
		p.emitting = false
		p.restart()
		p.emitting = false
	_apply()


func step(dt: float) -> void:
	_clock += dt
	runner = int(floorf(_clock / STEP_S)) % ORDER.size()
	for k: int in 5:
		_mix[k] = move_toward(_mix[k], 1.0 if open[k] else 0.0, dt / EASE_S)
	for p: GPUParticles3D in _puffs + _clouds:
		p.speed_scale = time_scale
	_apply()


func _apply() -> void:
	for k: int in 5:
		var c: Color = RED.lerp(CYAN, _mix[k])
		var al: float = float(look["albedo"])
		for part: String in _mats[k]:
			var m: StandardMaterial3D = _mats[k][part]
			m.emission = c
			m.albedo_color = Color(c.r * al, c.g * al, c.b * al)
			m.metallic = 0.0
			m.emission_energy_multiplier = float(look[part])
		var sh: ShaderMaterial = _shaders[k]
		sh.set_shader_parameter("colour", Vector3(c.r, c.g, c.b))
		sh.set_shader_parameter("rim", float(look["rim"]))
		sh.set_shader_parameter("floor_e", float(look["floor"]))
		sh.set_shader_parameter("power", float(look["power"]))
		sh.set_shader_parameter("albedo", al)
		var l: OmniLight3D = _lights[k]
		l.light_color = c
		l.omni_range = float(look["light_range"]) * (0.8 + 0.25 * float(_sizes[k].y))
		l.light_energy = float(look["light"]) * (1.0 + 0.3 * _mix[k])
		var bar: StandardMaterial3D = _bars[k]
		if bar != null:
			var white: bool = k == slit()
			var bc: Color = WHITE if white else (CYAN if open[k] else RED)
			bar.emission = bc
			bar.albedo_color = bc if white else Color(bc.r * 0.1, bc.g * 0.1, bc.b * 0.1)
			bar.emission_energy_multiplier = float(look["white" if white else "bar"])
	if _groove != null:
		_groove.emission = CYAN
		_groove.albedo_color = Color(CYAN.r * 0.1, CYAN.g * 0.1, CYAN.b * 0.1)
		_groove.emission_energy_multiplier = float(look["groove"])


func _mesh(name: String) -> MeshInstance3D:
	return _root.find_child(name, true, false) as MeshInstance3D


func _box(mi: MeshInstance3D) -> AABB:
	return _root.global_transform.affine_inverse() * mi.global_transform * mi.get_aabb()


func _centre(mi: MeshInstance3D) -> Vector3:
	return _box(mi).get_center()


func _own(name: String) -> StandardMaterial3D:
	var mi: MeshInstance3D = _mesh(name)
	if mi == null:
		return null
	var src: Material = mi.get_active_material(0)
	var m: StandardMaterial3D = (src as StandardMaterial3D).duplicate() if src is StandardMaterial3D else StandardMaterial3D.new()
	m.emission_enabled = true
	mi.material_override = m
	return m


## Steam: soft additive billboards out of the wall, rising and spreading; a one-shot puff or a held cloud.
func _particles(at: Vector3, extents: Vector3, amount: int, life: float, one_shot: bool) -> GPUParticles3D:
	var p: GPUParticles3D = GPUParticles3D.new()
	p.position = at
	p.amount = amount
	p.lifetime = life
	p.one_shot = one_shot
	p.explosiveness = 0.75 if one_shot else 0.0
	p.randomness = 0.4
	p.emitting = false
	p.local_coords = false
	p.visibility_aabb = AABB(Vector3(-2, -1.5, -2), Vector3(4, 3, 4))
	var pm: ParticleProcessMaterial = ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = extents
	pm.direction = _out
	pm.spread = 30.0 if one_shot else 60.0
	pm.initial_velocity_min = 0.22 if one_shot else 0.06
	pm.initial_velocity_max = 0.45 if one_shot else 0.16
	pm.gravity = Vector3(0, 0.08 if one_shot else 0.025, 0)
	pm.damping_min = 0.25
	pm.damping_max = 0.4
	pm.scale_min = 0.7
	pm.scale_max = 1.3
	var sc: Curve = Curve.new()
	sc.add_point(Vector2(0.0, 0.35))
	sc.add_point(Vector2(1.0, 1.0))
	var sct: CurveTexture = CurveTexture.new()
	sct.curve = sc
	pm.scale_curve = sct
	var g: Gradient = Gradient.new()
	g.set_color(0, Color(1, 1, 1, 0))
	g.set_color(1, Color(1, 1, 1, 0))
	g.add_point(0.2 if one_shot else 0.3, Color(1, 1, 1, 1))
	g.add_point(0.6, Color(1, 1, 1, 0.6))
	var gt: GradientTexture1D = GradientTexture1D.new()
	gt.gradient = g
	pm.color_ramp = gt
	p.process_material = pm
	var tex: GradientTexture2D = GradientTexture2D.new()
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	var rg: Gradient = Gradient.new()
	rg.set_color(0, Color(1, 1, 1, 1))
	rg.set_color(1, Color(1, 1, 1, 0))
	rg.add_point(0.45, Color(1, 1, 1, 0.4))
	tex.gradient = rg
	tex.width = 128
	tex.height = 128
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.vertex_color_use_as_albedo = true
	m.proximity_fade_enabled = true
	m.proximity_fade_distance = 0.06
	m.albedo_texture = tex
	var k: float = float(LOOK["puff" if one_shot else "cloud"])
	m.albedo_color = Color(0.55 * k, 0.9 * k, 1.0 * k, 1.0)
	m.disable_receive_shadows = true
	var q: QuadMesh = QuadMesh.new()
	q.size = Vector2(0.24, 0.24) if one_shot else Vector2(0.42, 0.42)
	q.material = m
	p.draw_pass_1 = q
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_root.add_child(p)
	return p


## The proof's demo: presses at the white bar's steps (t s: the slit then under it).
static func demo_events() -> Array:
	return [[0.9, "press"], [2.1, "press"], [3.3, "press"], [5.1, "press"], [6.3, "press"], [7.5, "press"],
		[8.1, "press"]]


## Key moments [t, label, still name].
static func demo_keys() -> Array:
	return [[0.4, "all shut", "shut"], [1.3, "press: 2 opens", ""], [2.5, "press: 4 opens", ""],
		[3.7, "press on open 4: it shuts", ""], [5.5, "press: 1 opens", ""], [6.9, "press: 3 opens", "mid"],
		[8.6, "all open: the cloud", ""], [13.5, "the cloud stays", "open"]]
