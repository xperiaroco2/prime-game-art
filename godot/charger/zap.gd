extends RefCounted
## The charger's electricity (art#263, prime-game#1095: "no effects at all ... some electricity there"), a reference
## the game copies: lightning arcs from the two inner prongs' electrodes into the seated crystal while it charges,
## sparks where they land, cyan pulses up the lens alcove's four conduits, one big flash at full charge, then quiet.
## Everything is driven by the charger look's state and the charge; nothing is a canned clip. Kept out of charger.gd,
## whose copy ships in assets/prop/crystal_charger byte-equal (test_props_crystal_charger); the conduits are a ship
## piece (lens_conduits_e/w, material int_cyan__lens_core, its UV along each run).
## Use with preload (no class cache in a `-s` script):
##
##   const Zap = preload("res://charger/zap.gd")
##   Zap.bind(look, ship, crystal)                 # after Charger.apply and seat_crystal, the ring at angle 0
##   Zap.step(look, dt, charge, flash, lit)        # each frame: the charge 0..1, the full-charge flash 0..1, the fade
##
## The gating (step): arcs only while the look's state is "charging" and 0 < charge < 1, or during the flash (still
## "charging"); none idle or charged. Sparks live out their short life. The conduits pulse while the arcs run, glow
## steady once the charge is full, and go back to their base glow with `lit` (the crystal taken out).
## Arcs, sparks and their lights live under the charger's model root, in its frame; their shapes are re-rolled every
## TICK s from a seeded generator and rebuilt every frame on the electrodes' and the crystal's current places, so they
## follow the turning ring and the rising, turning crystal. The sparks are simulated here on the caller's dt (not
## GPUParticles3D), so a fixed-clock shot (cycle.gd) draws the same frames every run.

const ARC_SHADER := preload("res://charger/arc.gdshader")
const CONDUIT_SHADER := preload("res://charger/conduit.gdshader")
const CORE_MAT := "int_cyan__lens_core"
const CONDUIT_REACH := 1.2   # m: a core mesh whose box centre is this near the crystal's middle is this charger's

## The electrodes on the track ring: tools/blender/charger_dims.toml [inner] electrodes [r, h, er] (cm), placed as
## charger_build.build_electrodes does: at u ±(r cos(HALF_DEG / 3) - 0.45 er), h, on the crystal's axis (AXIS_D out
## of the wall). Index 0 the tip electrode under the hook's lip, 1 the low one on the column's inner face.
const HALF_DEG := 12.0
const ELECTRODES := [[11.0, 116.0, 1.5], [16.8, 101.0, 1.0]]
const AXIS_D := 0.38
## per electrode: where on the crystal its arcs land (m up the crystal from the electrode's height) and the jitter
const LIFT := [-0.045, 0.09]   # zap-2: the tip pair dives down the crystal (level, 2.5 cm, read as nothing at 2 m)
const LIFT_JITTER := [0.04, 0.045]
const ANGLE_JITTER := 0.7        # rad round the crystal's axis, either side of the electrode's own direction
const SKIP := [0.1, 0.45]        # per electrode: the share of ticks it does not arc (the flicker's gaps)
const TICK := [0.05, 0.08]       # s between re-rolls
const FLASH_TICK := 0.03
## the ribbons' half widths (m) and the bolts' roughness (the largest sideways step as a share of the bolt's length)
const HALF_WIDTH := [0.011, 0.008]   # zap-2: 4.2 mm drew a sub-pixel core at the player's 2 m
const BRANCH_WIDTH := 0.55       # a branch's share of its bolt's width
const ROUGH := 0.28
const FLASH_WIDTH := 2.2
const FLASH_BRANCHES := 4
## the lights at the hits: small, a whiter cyan that stays neutral on the bronze (charger.gd SEATED_OMNI_COLOUR)
const LIGHT_COLOUR := Color(0.45, 0.82, 1.0)
const LIGHT_ENERGY := [0.45, 0.25]
const LIGHT_RANGE := 0.2
const FLASH_ENERGY := 1.8
const FLASH_RANGE := 0.42
## sparks: per tick per hit and at an electrode, their speed (m/s), life (s), the flash's burst
const SPARKS_HIT := [1, 3]
const SPARK_ELECTRODE := 0.18
const SPARK_SPEED := [0.35, 1.1]
const SPARK_LIFE := [0.1, 0.28]
const SPARK_BURST := 28
const SPARK_HALF_WIDTH := 0.003
const GRAVITY := 5.0
const MAX_SPARKS := 200
## zap-3 (the engineer: "lightning, white, around the crystal, spinning"): per prong a wrap arc that leaves the tip
## electrode and crawls round the crystal's surface (WRAP_SWEEP rad, the ring's way, up or down WRAP_RISE m) and a
## crawler between two points on the surface; glints orbit the crystal the ring's way and spiral out
const WRAP_SWEEP := [1.2, 3.0]
const WRAP_RISE := 0.05
const WRAP_OUT := 1.12           # the wrap's distance from the axis, a share of the crystal's radius there
const CRAWL_CHANCE := 0.7
const GLINTS := [3, 6]           # per tick
const GLINT_SPEED := [5.0, 10.0] # rad/s round the axis
const GLINT_LIFE := [0.3, 0.7]
const GLINT_BURST := 40
## the conduits' flow and steady glow ease toward their targets at this rate (1/s)
const EASE := 3.0


## Builds the effect's nodes under the charger's model root and binds the alcove's conduit cores near the crystal
## (their own conduit.gdshader copy, its base the surface's own glow); keeps everything in look["zap"]. Returns the
## conduit surfaces bound (1 per lens_conduits piece: its cores).
static func bind(look: Dictionary, scene: Node, crystal: Node3D) -> int:
	var ring: Node3D = look["ring"]
	var model: Node3D = (look["glow"] as Node3D).get_parent()
	var ring_t: Transform3D = _rel(ring, model)
	var locals: Array[Vector3] = []
	var radii: Array[float] = []
	for side: float in [-1.0, 1.0]:
		for e: Array in ELECTRODES:
			var u: float = side * (float(e[0]) * cos(deg_to_rad(HALF_DEG / 3.0)) - 0.45 * float(e[2])) / 100.0
			locals.append(ring_t.affine_inverse() * Vector3(u, float(e[1]) / 100.0, AXIS_D))
			radii.append(float(e[2]) / 100.0)
	var mat := ShaderMaterial.new()
	mat.shader = ARC_SHADER
	var mesh := ImmediateMesh.new()
	var node := MeshInstance3D.new()
	node.name = "ChargerZap"
	node.mesh = mesh
	node.material_override = mat
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	node.custom_aabb = AABB(Vector3(-0.6, 0.6, -0.3), Vector3(1.2, 1.2, 1.4))
	model.add_child(node)
	var lights: Array[OmniLight3D] = []
	for i: int in locals.size():
		var l := OmniLight3D.new()
		l.name = "ZapLight%d" % i
		l.light_color = LIGHT_COLOUR
		l.omni_range = LIGHT_RANGE
		l.omni_attenuation = 2.0
		l.shadow_enabled = false
		l.visible = false
		model.add_child(l)
		lights.append(l)
	var rng := RandomNumberGenerator.new()
	rng.seed = 263
	var arcs: Array[Dictionary] = []
	for i: int in locals.size():
		arcs.append({"on": false, "seed": 0, "lift": 0.0, "angle": 0.0, "flicker": 1.0})
	var z := {"model": model, "ring": ring, "crystal": crystal, "locals": locals, "radii": radii, "mesh": mesh,
		"node": node, "mat": mat, "lights": lights, "rng": rng, "clock": 0.0, "next": 0.0, "arcs": arcs,
		"sparks": [], "flow": 0.0, "steady": 0.0, "flashed": false, "conduits": null, "profile": _profile(crystal),
		"active": false, "ends": []}
	look["zap"] = z
	# the conduits: every int_cyan__lens_core surface whose mesh's box centre is near the crystal's middle
	var centre: Vector3 = _world(look["glow"]).origin
	var count := 0
	var cm: ShaderMaterial = null
	for m: MeshInstance3D in scene.find_children("*", "MeshInstance3D", true, false):
		if m.mesh == null or (_world(m) * m.mesh.get_aabb().get_center()).distance_to(centre) > CONDUIT_REACH:
			continue
		for i: int in m.mesh.get_surface_count():
			var src: Material = m.mesh.surface_get_material(i)
			if src == null or src.resource_name != CORE_MAT:
				continue
			if cm == null:
				cm = ShaderMaterial.new()
				cm.shader = CONDUIT_SHADER
				if src is BaseMaterial3D:
					var b: BaseMaterial3D = src
					var e: Color = b.emission.srgb_to_linear() * b.emission_energy_multiplier
					cm.set_shader_parameter("base_emission", Vector3(e.r, e.g, e.b))
					cm.set_shader_parameter("albedo", b.albedo_color)
					cm.set_shader_parameter("roughness", b.roughness)
			m.set_surface_override_material(i, cm)
			count += 1
	z["conduits"] = cm
	return count


## One frame: the clock moves on by dt (0: a still, the conduits' glow snaps to its target), the arcs re-roll every
## TICK s, follow the electrodes and the crystal, the sparks fly and die, the lights flicker, the conduits pulse.
static func step(look: Dictionary, dt: float, charge: float, flash: float = 0.0, lit: float = 1.0) -> void:
	var z: Dictionary = look.get("zap", {})
	if z.is_empty():
		return
	var charging: bool = look["state"] == "charging"
	var crystal: Node3D = z["crystal"]
	var seated: bool = crystal != null and crystal.visible
	var flashing: bool = charging and seated and flash > 0.0
	var arcing: bool = flashing or (charging and seated and charge > 0.0 and charge < 1.0)
	z["active"] = arcing
	var ring_y: float = (z["ring"] as Node3D).rotation.y
	if dt > 0.0 and absf(ring_y - float(z.get("ring_y", ring_y))) > 1e-5:
		z["sense"] = signf(ring_y - float(z.get("ring_y", ring_y)))
	z["ring_y"] = ring_y
	if crystal != null:
		z["centre"] = _rel(crystal, z["model"]).origin
	var rng: RandomNumberGenerator = z["rng"]
	z["clock"] = float(z["clock"]) + dt
	if not arcing:
		z["next"] = float(z["clock"])
	while arcing and float(z["clock"]) >= float(z["next"]):
		_reroll(z, flashing)
		z["next"] = float(z["next"]) + (FLASH_TICK if flashing else rng.randf_range(TICK[0], TICK[1]))
	if flashing and not bool(z["flashed"]):
		z["flashed"] = true
		for k: int in SPARK_BURST:
			var i: int = k % (z["locals"] as Array).size()
			var ends: Array = _ends(z, i, flashing)
			_spark(z, ends[1], ((ends[0] as Vector3) - (ends[1] as Vector3)).normalized(), 1.4)
		for k: int in GLINT_BURST:
			_glint(z)
	if not charging:
		z["flashed"] = false
	_fly(z, dt)
	var ramp: float = smoothstep(0.0, 0.03, charge) if not flashing else 1.0 + 1.2 * flash
	(z["mat"] as ShaderMaterial).set_shader_parameter("strength", ramp * lit)
	_draw(z, arcing, flashing, flash, ramp)
	# the conduits: pulses while arcing, steady once full, the base glow idle; `lit` fades them with the traces
	var cm: ShaderMaterial = z["conduits"]
	if cm != null:
		var flow_to: float = 1.0 if arcing else 0.0
		var steady_to: float = 1.0 if seated and look["state"] != "idle" and charge >= 1.0 else 0.0
		var k: float = INF if dt <= 0.0 else EASE * dt
		z["flow"] = move_toward(float(z["flow"]), flow_to, k)
		z["steady"] = move_toward(float(z["steady"]), steady_to, k)
		cm.set_shader_parameter("flow", z["flow"])
		cm.set_shader_parameter("steady", z["steady"])
		cm.set_shader_parameter("lit", clampf(lit, 0.0, 1.0))
		cm.set_shader_parameter("clock", z["clock"])


## The arcs' current [start, hit] per electrode that arcs this tick (the charger model's frame), for checks.
static func endpoints(look: Dictionary) -> Array:
	return (look.get("zap", {}) as Dictionary).get("ends", [])


## A new tick: each arc's seed, whether it arcs, where it lands, its flicker; sparks at the hits.
static func _reroll(z: Dictionary, flashing: bool) -> void:
	var rng: RandomNumberGenerator = z["rng"]
	var arcs: Array = z["arcs"]
	for i: int in arcs.size():
		var a: Dictionary = arcs[i]
		var kind: int = i % ELECTRODES.size()
		a["seed"] = rng.randi()
		a["on"] = flashing or rng.randf() >= float(SKIP[kind])
		a["lift"] = float(LIFT[kind]) + rng.randf_range(-1.0, 1.0) * float(LIFT_JITTER[kind])
		a["angle"] = rng.randf_range(-ANGLE_JITTER, ANGLE_JITTER)
		a["flicker"] = rng.randf_range(0.55, 1.0)
		if not a["on"]:
			continue
		var ends: Array = _ends(z, i, flashing)
		var out: Vector3 = ((ends[0] as Vector3) - (ends[1] as Vector3)).normalized()
		for k: int in rng.randi_range(SPARKS_HIT[0], SPARKS_HIT[1]):
			_spark(z, ends[1], out, 1.0)
		if rng.randf() < SPARK_ELECTRODE:
			_spark(z, ends[0], -out, 0.7)
	for k: int in rng.randi_range(GLINTS[0], GLINTS[1]) * (3 if flashing else 1):
		_glint(z)


## Arc i's start (on its electrode's surface, toward the hit) and its hit on the crystal's surface, in the model's
## frame, now.
static func _ends(z: Dictionary, i: int, flashing: bool) -> Array:
	var model: Node3D = z["model"]
	var e: Vector3 = _rel(z["ring"], model) * (z["locals"][i] as Vector3)
	var ct: Transform3D = _rel(z["crystal"], model)
	var ec: Vector3 = ct.affine_inverse() * e   # the electrode in the crystal's frame (its axis +Y, the tip at 0)
	var a: Dictionary = z["arcs"][i]
	var p: Dictionary = z["profile"]
	var lo: float = float(p["min"]) + 0.01
	var hi: float = float(p["max"]) - 0.01
	var h: float = clampf(ec.y + float(a["lift"]) + (0.04 if flashing else 0.0), lo, hi)
	var dir := Vector2(ec.x, ec.z).normalized().rotated(float(a["angle"]))
	var r: float = _radius(p, h) * 0.97
	var hit: Vector3 = ct * Vector3(dir.x * r, h, dir.y * r)
	var start: Vector3 = e + (hit - e).normalized() * float(z["radii"][i])
	return [start, hit]


static func _spark(z: Dictionary, at: Vector3, out: Vector3, speed: float) -> void:
	var sparks: Array = z["sparks"]
	if sparks.size() >= MAX_SPARKS:
		return
	var rng: RandomNumberGenerator = z["rng"]
	var rand := Vector3(rng.randf_range(-1, 1), rng.randf_range(-1, 1), rng.randf_range(-1, 1))
	var v: Vector3 = (out + rand * 0.9).normalized() * rng.randf_range(SPARK_SPEED[0], SPARK_SPEED[1]) * speed
	sparks.append({"p": at, "v": v, "age": 0.0, "life": rng.randf_range(SPARK_LIFE[0], SPARK_LIFE[1])})


## A glint: a bright speck orbiting the crystal's axis the ring's way, spiralling out and drifting up or down.
static func _glint(z: Dictionary) -> void:
	var sparks: Array = z["sparks"]
	if sparks.size() >= MAX_SPARKS or not z.has("centre"):
		return
	var rng: RandomNumberGenerator = z["rng"]
	var p: Dictionary = z["profile"]
	var h: float = rng.randf_range(float(p["min"]) + 0.02, float(p["max"]) - 0.02)
	sparks.append({"orbit": true, "a": rng.randf_range(0.0, TAU), "R": _radius(p, h) * rng.randf_range(1.1, 1.5),
		"h": h, "w": float(z.get("sense", -1.0)) * rng.randf_range(GLINT_SPEED[0], GLINT_SPEED[1]),
		"dr": rng.randf_range(0.03, 0.12), "dh": rng.randf_range(-0.03, 0.06), "age": 0.0,
		"life": rng.randf_range(GLINT_LIFE[0], GLINT_LIFE[1])})


static func _orbit_at(z: Dictionary, s: Dictionary, a: float) -> Vector3:
	return (z["centre"] as Vector3) + Basis(Vector3.UP, a) * Vector3(float(s["R"]), 0.0, 0.0) \
		+ Vector3(0.0, float(s["h"]), 0.0)


static func _fly(z: Dictionary, dt: float) -> void:
	var keep: Array = []
	for s: Dictionary in z["sparks"]:
		s["age"] = float(s["age"]) + dt
		if float(s["age"]) >= float(s["life"]):
			continue
		if s.has("orbit"):
			s["a"] = float(s["a"]) + float(s["w"]) * dt
			s["R"] = float(s["R"]) + float(s["dr"]) * dt
			s["h"] = float(s["h"]) + float(s["dh"]) * dt
			keep.append(s)
			continue
		var v: Vector3 = s["v"]
		v.y -= GRAVITY * dt
		v *= maxf(0.0, 1.0 - 2.0 * dt)
		s["v"] = v
		s["p"] = (s["p"] as Vector3) + v * dt
		keep.append(s)
	z["sparks"] = keep


## Rebuilds the ribbons: per arc a jagged bolt with its branches, per spark a short streak; places the lights.
static func _draw(z: Dictionary, arcing: bool, flashing: bool, flash: float, ramp: float) -> void:
	var im: ImmediateMesh = z["mesh"]
	im.clear_surfaces()
	var strips: Array = []   # [points, half width, alpha from, alpha to]
	var ends_out: Array = []
	var lights: Array = z["lights"]
	for i: int in (z["arcs"] as Array).size():
		var a: Dictionary = z["arcs"][i]
		var l: OmniLight3D = lights[i]
		l.visible = arcing and bool(a["on"])
		if not l.visible:
			continue
		var kind: int = i % ELECTRODES.size()
		var ends: Array = _ends(z, i, flashing)
		ends_out.append(ends)
		var rng := RandomNumberGenerator.new()
		rng.seed = int(a["seed"])
		var w: float = float(HALF_WIDTH[kind]) * (FLASH_WIDTH if flashing else 1.0)
		var main: Array[Vector3] = _bolt(rng, ends[0], ends[1], 4, ROUGH)
		strips.append([main, w, 1.0, 1.0])
		var branches: int = FLASH_BRANCHES if flashing else rng.randi_range(0, 2)
		for b: int in branches:
			var j: int = rng.randi_range(int(main.size() * 0.2), int(main.size() * 0.75))
			var from: Vector3 = main[j]
			var along: Vector3 = (ends[1] as Vector3) - (ends[0] as Vector3)
			var side := Vector3(rng.randf_range(-1, 1), rng.randf_range(-1, 1), rng.randf_range(-1, 1))
			var to: Vector3 = from + (along.normalized() * 0.5 + side.normalized() * 0.8).normalized() \
				* along.length() * rng.randf_range(0.3, 0.6) * (1.4 if flashing else 1.0)
			strips.append([_bolt(rng, from, to, 3, ROUGH * 1.3), w * BRANCH_WIDTH, 0.85, 0.0])
		if kind == 0:
			strips.append([_wrap(z, rng, ends[0], flashing), w * 0.8, 1.0, 0.25])
			if flashing or rng.randf() < CRAWL_CHANCE:
				strips.append([_crawl(z, rng), w * 0.6, 0.9, 0.9])
		var out: Vector3 = ((ends[0] as Vector3) - (ends[1] as Vector3)).normalized()
		l.position = (ends[1] as Vector3) + out * 0.015
		l.omni_range = lerpf(LIGHT_RANGE, FLASH_RANGE, flash) if flashing else LIGHT_RANGE
		l.light_energy = (FLASH_ENERGY * flash if flashing else float(LIGHT_ENERGY[kind]) * float(a["flicker"]) \
			* minf(ramp, 1.0))
	z["ends"] = ends_out
	for s: Dictionary in z["sparks"]:
		if s.has("orbit"):
			var g: float = (1.0 - float(s["age"]) / float(s["life"])) * minf(1.0, float(s["age"]) * 20.0)
			var a1: float = float(s["a"])
			var tw: float = 0.35 * signf(float(s["w"]))
			strips.append([[_orbit_at(z, s, a1 - tw), _orbit_at(z, s, a1 - tw * 0.4), _orbit_at(z, s, a1)],
				SPARK_HALF_WIDTH * 1.2, 0.0, g])
			continue
		var p: Vector3 = s["p"]
		var v: Vector3 = s["v"]
		var tail: Vector3 = v * 0.02 if v.length() * 0.02 > 0.004 else v.normalized() * 0.004
		var fade: float = 1.0 - float(s["age"]) / float(s["life"])
		strips.append([[p - tail, p], SPARK_HALF_WIDTH, 0.3 * fade, fade])
	var verts := 0
	for st: Array in strips:
		verts += ((st[0] as Array).size() - 1) * 6
	if verts == 0:
		return
	im.surface_begin(Mesh.PRIMITIVE_TRIANGLES)
	for st: Array in strips:
		_strip(im, st[0], st[1], st[2], st[3])
	im.surface_end()


## A wrap arc: from the electrode's start round the crystal's surface (WRAP_OUT of its radius), the ring's way,
## jagged; in the model's frame.
static func _wrap(z: Dictionary, rng: RandomNumberGenerator, start: Vector3, flashing: bool) -> Array[Vector3]:
	var ct: Transform3D = _rel(z["crystal"], z["model"])
	var p: Dictionary = z["profile"]
	var ec: Vector3 = ct.affine_inverse() * start
	var a0: float = atan2(ec.z, ec.x)
	var sweep: float = rng.randf_range(WRAP_SWEEP[0], WRAP_SWEEP[1]) * (1.5 if flashing else 1.0) \
		* -float(z.get("sense", -1.0))
	var h0: float = clampf(ec.y - 0.01, float(p["min"]) + 0.01, float(p["max"]) - 0.01)
	var dh: float = rng.randf_range(-WRAP_RISE, WRAP_RISE)
	var pts: Array[Vector3] = [start]
	var n := 14
	for k: int in range(1, n + 1):
		var f: float = float(k) / n
		var h: float = clampf(h0 + dh * f, float(p["min"]) + 0.01, float(p["max"]) - 0.01)
		var r: float = _radius(p, h) * WRAP_OUT + rng.randf_range(-0.004, 0.006)
		var a: float = a0 + sweep * f
		pts.append(ct * Vector3(cos(a) * r, h + rng.randf_range(-0.006, 0.006), sin(a) * r))
	return pts


## A crawler: a short jagged bolt between two points on the crystal's surface, a quarter to half a turn apart.
static func _crawl(z: Dictionary, rng: RandomNumberGenerator) -> Array[Vector3]:
	var ct: Transform3D = _rel(z["crystal"], z["model"])
	var p: Dictionary = z["profile"]
	var ends: Array[Vector3] = []
	var a: float = rng.randf_range(0.0, TAU)
	for k: int in 2:
		var h: float = rng.randf_range(float(p["min"]) + 0.02, float(p["max"]) - 0.02)
		var r: float = _radius(p, h) * 1.03
		ends.append(ct * Vector3(cos(a) * r, h, sin(a) * r))
		a += rng.randf_range(0.8, 1.8)
	return _bolt(rng, ends[0], ends[1], 3, ROUGH)


## A bolt from a to b: midpoint displacement `levels` times (2^levels segments), each level's sideways step at most
## rough x its segment's length, the ends fixed.
static func _bolt(rng: RandomNumberGenerator, a: Vector3, b: Vector3, levels: int, rough: float) -> Array[Vector3]:
	var pts: Array[Vector3] = [a, b]
	var dir: Vector3 = (b - a).normalized()
	var s1: Vector3 = dir.cross(Vector3.UP if absf(dir.y) < 0.9 else Vector3.RIGHT).normalized()
	var s2: Vector3 = dir.cross(s1)
	for level: int in levels:
		var next: Array[Vector3] = []
		for i: int in pts.size() - 1:
			var p: Vector3 = pts[i]
			var q: Vector3 = pts[i + 1]
			var amp: float = p.distance_to(q) * rough
			next.append(p)
			next.append((p + q) * 0.5 + s1 * rng.randf_range(-amp, amp) + s2 * rng.randf_range(-amp, amp))
		next.append(pts[-1])
		pts = next
	return pts


## One camera-facing ribbon along pts (arc.gdshader turns it): two triangles per segment, the joints shared.
static func _strip(im: ImmediateMesh, pts: Array, hw: float, a0: float, a1: float) -> void:
	var n: int = pts.size()
	var tang: Array[Vector3] = []
	for i: int in n:
		var t: Vector3 = (pts[mini(i + 1, n - 1)] as Vector3) - (pts[maxi(i - 1, 0)] as Vector3)
		tang.append(t.normalized() if t.length() > 1e-6 else Vector3.UP)
	for i: int in n - 1:
		for c: Array in [[i, -1.0], [i, 1.0], [i + 1, 1.0], [i, -1.0], [i + 1, 1.0], [i + 1, -1.0]]:
			var k: int = c[0]
			var f: float = float(k) / float(n - 1)
			im.surface_set_normal(tang[k])
			im.surface_set_uv(Vector2(f, c[1]))
			im.surface_set_uv2(Vector2(hw * lerpf(1.0, 0.7, f), 0.0))
			im.surface_set_color(Color(1, 1, 1, lerpf(a0, a1, f)))
			im.surface_add_vertex(pts[k])


## The crystal's radius by height (its own frame: the axis +Y through the origin, the tip at 0): the vertices' largest
## distance from the axis per 5 mm band. {"min", "max" (m), "step", "r": PackedFloat32Array}.
static func _profile(crystal: Node3D) -> Dictionary:
	var step := 0.005
	var pts: Array[Vector3] = []
	for m: MeshInstance3D in crystal.find_children("*", "MeshInstance3D", true, false):
		if m.mesh == null:
			continue
		var t: Transform3D = _rel(m, crystal)
		for s: int in m.mesh.get_surface_count():
			for v: Vector3 in m.mesh.surface_get_arrays(s)[Mesh.ARRAY_VERTEX]:
				pts.append(t * v)
	var lo := INF
	var hi := -INF
	for p: Vector3 in pts:
		lo = minf(lo, p.y)
		hi = maxf(hi, p.y)
	var r := PackedFloat32Array()
	r.resize(maxi(1, ceili((hi - lo) / step) + 1))
	for p: Vector3 in pts:
		var k: int = int((p.y - lo) / step)
		r[k] = maxf(r[k], Vector2(p.x, p.z).length())
	return {"min": lo, "max": hi, "step": step, "r": r}


static func _radius(p: Dictionary, h: float) -> float:
	var r: PackedFloat32Array = p["r"]
	var k: int = clampi(int((h - float(p["min"])) / float(p["step"])), 0, r.size() - 1)
	return maxf(r[k], r[maxi(k - 1, 0)])


## A node's transform relative to an ancestor (walking the parents: the shots build the scene before the tree is
## entered).
static func _rel(n: Node, top: Node) -> Transform3D:
	var t := Transform3D.IDENTITY
	while n != null and n != top:
		if n is Node3D:
			t = (n as Node3D).transform * t
		n = n.get_parent()
	return t


static func _world(n: Node) -> Transform3D:
	return _rel(n, null)
