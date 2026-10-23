extends SceneTree
## The empty ship in Godot for `tools/run.py ship` (art #263, docs/ship.md): places every piece GLB by the layout's
## placements (pieces imported with `-col` meshes carry their trimesh colliders), then either checks it headless or
## shoots it at night in an off-screen window. The EXTERIOR lane owns this folder after the foundation step.
##   godot --headless --path godot -s res://ship/ship.gd -- <request.json> <out>          (mode "check")
##   shoot: started by the runner through `_godot.window()` (one off-screen pixel; CLAUDE.md, #214), never by hand:
##       PRIME_WINDOW=1920x1080 godot <_godot.window() flags> -s res://ship/ship.gd -- <request.json> <out>  (mode "shoot")
## request.json (tools/runner/commands/ship.py): {"mode", "pieces": {id: res}, "place": [[id, [x, h, y], yaw]],
##   "collide": [id], "bounds": {id: {"min", "max"}}, "walk": {"r", "h", "points"}, "light": {"moon_dir_deg",
##   "moon_energy", "lamps": [[x, h, y, energy, range, r, g, b]]}, "views": [[name, title, eye, look, fov]],
##   "top": {"name", "title", "size_m"}, "compare": [[shot, reference image]]}.
## check: <out>/check.json {"bounds": {id: {min, max}} (each piece at the origin), "colliders": {id: n}, "walk"}.
## shoot: <out>/<view>.png at the window's size, compare_<shot>.png (the reference left, the shot right),
##   sheet.png (1280 px wide) and shots.json; prints SHIP saved <dir>.
## video (off-screen window, as shoot): "video": {"fps", "fov", "keys": [[eye, look, seconds]]} (Godot coordinates):
##   the camera through the keys (cubic in time), one PNG per frame in <out>/frames/, video.json; "watchdog_s".
## vent_anim (off-screen window, as shoot; vents-anim1): "anim": {"piece", "eye", "look", "fov", "fps", "mark_travel"}:
##   vent_anim.gd's controller on the placed piece through its demo inputs, the camera still; one PNG per frame in
##   <out>/frames/, the key moments labelled in <out>/keys/, keys_sheet.png (1280 px) and anim.json.
## play (an on-screen window, for the engineer only: `ship --play`): the night scene as shoot dresses it and a
##   first-person capsule (player.gd) at "spawn" [x, h, y] facing "spawn_yaw" degrees; P saves <out>/shot_*.png and a
##   line in <out>/shots.txt. With "test": true the runner opens it off-screen (`ship --play-test`): the capsule walks
##   forward 2 s, saves one shot, writes <out>/play.json and quits.

const Offscreen = preload("res://lib/offscreen.gd")
const Player = preload("res://ship/player.gd")
const VentGlow = preload("res://ship/vent_glow.gd")
const VentAnim = preload("res://ship/vent_anim.gd")
const WATCHDOG_S: float = 240.0
const UP := Vector3.UP
const SPEED: float = 3.0
const SHEET_W: int = 1280
const GAP: int = 4

var _req: Dictionary
var _out: String
var _camera: Camera3D
var _label: Label
var _scenes: Dictionary = {}
var _metals: Dictionary = {}
## The navigation lamps blink (light layer): the white tail lamp flashes once a second, the red and green pulse softly.
## On in game; the request's "nav_blink" (false for shots and the video) turns it off: a static glow.
var nav_blink: bool = true
var _nav: Array = []   # [light, energy, tail]; [material, emission energy, tail] for the lamps' lenses
var _env: Environment
var _sky_mat: ShaderMaterial
var _by_name: Dictionary = {}   # fix 2: glTF material name -> its BaseMaterial3D copies (not the METALS), for _ab
var _ab_saved: Dictionary = {}   # material -> [roughness, metallic, specular] before an A/B row's "mats"
var _ab_env: Dictionary = {}   # the environment's ssil/ssao/glow and the night lights' shadows before the first A/B row
var _night_lights: Array = []   # details 1: the moon and the key, hidden by _day

## The shared metal library (metal.gdshader) by glTF material name: base colour, metallic, roughness, grain, seams,
## scratches, grime. Other materials keep their glTF look. The outside (rebuild B, the engineer: back to the night
## build's plated, brushed silver): the night's colours, brush and grime; no scratches, and no seam grid in the shader
## (the plates' seams are geometry, laid over the hull's facets by ship_hull_j.py).
const METALS: Dictionary = {
	"hull_silver": [Color(0.66, 0.68, 0.71), 0.6, 0.36, 0.6, 0.0, 0.0, 0.25],
	"ext_silver_b": [Color(0.74, 0.76, 0.79), 0.6, 0.32, 0.6, 0.0, 0.0, 0.2],
	"ext_silver_c": [Color(0.56, 0.58, 0.61), 0.6, 0.4, 0.6, 0.0, 0.0, 0.3],
	"hull_dark": [Color(0.12, 0.125, 0.13), 0.8, 0.42, 0.4, 0.0, 0.0, 0.3],
	"ext_frame": [Color(0.17, 0.18, 0.19), 0.85, 0.34, 0.35, 0.0, 0.0, 0.2],
	"leg_metal": [Color(0.32, 0.33, 0.35), 0.9, 0.36, 0.5, 0.0, 0.0, 0.35],
	"wall_panel": [Color(0.42, 0.44, 0.47), 0.75, 0.4, 0.4, 0.4, 0.3, 0.25],
	"ceiling": [Color(0.36, 0.38, 0.41), 0.75, 0.42, 0.4, 0.4, 0.2, 0.2],
	"ext_seam": [Color(0.035, 0.037, 0.04), 0.6, 0.6, 0.0, 0.0, 0.0, 0.0],
}
const METAL_KEYS: Array = ["metallic", "roughness", "grain", "seams", "scratches", "grime"]
const LIGHT_CELL_M: float = 1.6
const INSIDE_LAYER: int = 1   # render layer bits: the inside's pieces (default) and the outside's (inside-2)
const OUTSIDE_LAYER: int = 2
const MAX_LIGHTS: int = 96


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 2:
		_fail("usage: -- <request.json> <out dir>")
		return
	var request: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if typeof(request) != TYPE_DICTIONARY:
		_fail("cannot read %s" % args[0])
		return
	_req = request
	_out = args[1]
	nav_blink = bool(_req.get("nav_blink", true))
	DirAccess.make_dir_recursive_absolute(_out)
	var test_play: bool = _req["mode"] == "play" and bool(_req.get("test", false))
	if _req["mode"] in ["shoot", "video", "vent_anim"] or test_play:
		if DisplayServer.get_name() == "headless":
			_fail("shoot needs a window (off-screen), not --headless")
			return
		var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
		if placed != "":
			_fail(placed)
			return
	if _req["mode"] != "play" or test_play:
		var watchdog: float = float(_req.get("watchdog_s", WATCHDOG_S))
		create_timer(watchdog).timeout.connect(_fail.bind("not done within %d s" % watchdog))
	if _req["mode"] == "play":
		_play(test_play)
	elif _req["mode"] == "check":
		_check()
	elif _req["mode"] == "video":
		_video()
	elif _req["mode"] == "vent_anim":
		_vent_anim()
	else:
		_shoot()


# --- the scene -----------------------------------------------------------------------------------------------------
func _scene(pid: String) -> PackedScene:
	if not _scenes.has(pid):
		_scenes[pid] = load(_req["pieces"][pid]) as PackedScene
		if _scenes[pid] == null:
			_fail("cannot load %s" % _req["pieces"][pid])
	return _scenes[pid]


func _build() -> Node3D:
	var ship: Node3D = Node3D.new()
	ship.name = "Ship"
	root.add_child(ship)
	for p: Array in _req["place"]:
		var node: Node3D = _scene(p[0]).instantiate() as Node3D
		node.name = "%s_%d" % [p[0], ship.get_child_count()]
		node.position = _v(p[1])
		node.rotation_degrees.y = float(p[2])
		ship.add_child(node)
		if p[0] in _req.get("outside", []):  # inside-2: the outside draws on layer 2, unlit by the inside's strips
			_set_layers(node, OUTSIDE_LAYER)
	var ground: StaticBody3D = StaticBody3D.new()
	var shape: CollisionShape3D = CollisionShape3D.new()
	shape.shape = WorldBoundaryShape3D.new()
	ground.add_child(shape)
	root.add_child(ground)
	if _req["pieces"].has("ground"):  # the clearing's own ground piece draws it
		return ship
	var mesh: MeshInstance3D = MeshInstance3D.new()
	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(200, 200)
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.albedo_color = Color(0.09, 0.11, 0.07)
	mat.roughness = 1.0
	plane.material = mat
	mesh.mesh = plane
	ground.add_child(mesh)
	return ship


## A piece's bounds at the origin (its meshes' AABBs in the piece's frame) and its colliders.
func _measure(pid: String) -> Array:
	var node: Node3D = _scene(pid).instantiate() as Node3D
	var box: AABB = AABB()
	var first: bool = true
	var colliders: int = 0
	var stack: Array = [[node, Transform3D.IDENTITY]]
	while not stack.is_empty():
		var item: Array = stack.pop_back()
		var n: Node = item[0]
		var t: Transform3D = item[1]
		if n is MeshInstance3D and (n as MeshInstance3D).mesh != null:
			var b: AABB = t * (n as MeshInstance3D).mesh.get_aabb()
			box = b if first else box.merge(b)
			first = false
		if n is CollisionShape3D and (n as CollisionShape3D).shape != null:
			colliders += 1
		for c: Node in n.get_children():
			var ct: Transform3D = t * (c as Node3D).transform if c is Node3D else t
			stack.append([c, ct])
	node.free()
	return [box, colliders]


func _check() -> void:
	var result: Dictionary = {"bounds": {}, "colliders": {}}
	for pid: String in _req["pieces"]:
		var m: Array = _measure(pid)
		var box: AABB = m[0]
		result["bounds"][pid] = {"min": [box.position.x, box.position.y, box.position.z],
			"max": [box.end.x, box.end.y, box.end.z]}
		result["colliders"][pid] = m[1]
	_build()
	for i: int in 3:
		await physics_frame
	var w: Dictionary = _req["walk"]
	result["walk"] = await _walk(float(w["r"]), float(w["h"]), w["points"].map(_v))
	_write("check.json", result)
	print("SHIP check saved %s" % _out)
	quit(0)


## A capsule (radius r, height h) walks the waypoints at 3 m/s with gravity; it arrives when it reaches the last one
## within 0.3 m and its height within 0.15 m.
func _walk(r: float, h: float, points: Array) -> Dictionary:
	var body: CharacterBody3D = CharacterBody3D.new()
	var shape: CollisionShape3D = CollisionShape3D.new()
	var cap: CapsuleShape3D = CapsuleShape3D.new()
	cap.radius = r
	cap.height = h
	shape.shape = cap
	shape.position.y = h / 2.0
	body.add_child(shape)
	body.floor_snap_length = 0.3
	root.add_child(body)
	body.global_position = (points[0] as Vector3) + Vector3(0, 0.05, 0)
	var length: float = 0.0
	for i: int in points.size() - 1:
		length += (points[i + 1] as Vector3).distance_to(points[i])
	var limit: int = int((length / SPEED + 8.0) * Engine.physics_ticks_per_second)
	var reached: int = 0
	var dt: float = 1.0 / Engine.physics_ticks_per_second
	var steps: int = 0
	var min_y: float = 99.0
	var last_move: int = 0
	var last_pos: Vector3 = body.global_position
	while steps < limit and reached < points.size() - 1:
		await physics_frame
		steps += 1
		var target: Vector3 = points[reached + 1]
		var flat: Vector3 = Vector3(target.x - body.global_position.x, 0, target.z - body.global_position.z)
		if flat.length() < 0.3:
			reached += 1
			continue
		var v: Vector3 = flat.normalized() * SPEED
		v.y = 0.0 if body.is_on_floor() else body.velocity.y - 9.8 * dt
		body.velocity = v
		body.move_and_slide()
		min_y = minf(min_y, body.global_position.y)
		if body.global_position.distance_to(last_pos) > 0.05:
			last_pos = body.global_position
			last_move = steps
		elif steps - last_move > 2 * Engine.physics_ticks_per_second:
			break
	var end: Vector3 = body.global_position
	var arrived: bool = reached == points.size() - 1 and absf(end.y - (points[-1] as Vector3).y) < 0.15
	body.queue_free()
	return {"radius_m": r, "of": points.size(), "reached": reached + 1, "end": [end.x, end.y, end.z],
		"min_y": min_y, "seconds": steps * dt, "arrived": arrived, "stuck": [last_pos.x, last_pos.y, last_pos.z]}


# --- pictures ------------------------------------------------------------------------------------------------------
## The night: the star sky (night_sky.gdshader), the look of godot/showroom/look_presets.json's High preset (AgX,
## SSAO 0.6 / 1.5) at ship.toml [light] exposure (1.0) for a night exterior, glow for the emissive strips, SSIL, a thin blue distance fog,
## the moonlight and the layout's lamps.
func _environment() -> void:
	var light: Dictionary = _req["light"]
	var env: Environment = Environment.new()
	_env = env
	var sky: Sky = Sky.new()
	var sm: ShaderMaterial = ShaderMaterial.new()
	_sky_mat = sm
	sm.shader = load("res://ship/night_sky.gdshader") as Shader
	sky.sky_material = sm
	sm.set_shader_parameter("horizon", Vector3(0.04, 0.06, 0.12) * _lk("sky_horizon", 1.0))
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.13, 0.155, 0.24)
	env.ambient_light_energy = _lk("ambient_energy", 0.9)
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = _lk("exposure", 1.2)
	env.glow_enabled = true
	env.glow_intensity = 0.6
	env.glow_bloom = 0.03
	env.glow_hdr_threshold = 1.0
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	env.ssao_enabled = true
	env.ssao_radius = 0.6
	env.ssao_intensity = 1.5
	env.ssil_enabled = true
	env.ssil_intensity = _lk("ssil_intensity", 1.0)  # SSIL threw the hall's lamp ring onto the centre disc
	env.fog_enabled = true
	env.fog_light_color = Color(0.05, 0.07, 0.12)
	env.fog_density = 0.0045
	env.fog_sky_affect = 0.0
	var we: WorldEnvironment = WorldEnvironment.new()
	we.environment = env
	root.add_child(we)
	var moon: DirectionalLight3D = DirectionalLight3D.new()
	moon.light_color = Color(0.62, 0.72, 1.0)
	moon.light_energy = float(light["moon_energy"])
	moon.shadow_enabled = true
	moon.directional_shadow_max_distance = 90.0
	moon.rotation_degrees = Vector3(float(light["moon_dir_deg"][0]), float(light["moon_dir_deg"][1]), 0)
	root.add_child(moon)
	_night_lights.append(moon)
	if light.has("key_dir_deg"):  # hull 3-2: a cool key from the cameras' side, so the silver facets catch light
		var key: DirectionalLight3D = DirectionalLight3D.new()
		var kc: Array = light.get("key_color", [0.78, 0.84, 1.0])
		key.light_color = Color(float(kc[0]), float(kc[1]), float(kc[2]))
		key.light_energy = float(light.get("key_energy", 0.6))
		key.light_specular = float(light.get("key_specular", 1.0))
		key.shadow_enabled = true
		key.directional_shadow_max_distance = 90.0
		key.rotation_degrees = Vector3(float(light["key_dir_deg"][0]), float(light["key_dir_deg"][1]), 0)
		root.add_child(key)
		_night_lights.append(key)
	for l: Array in light["lamps"]:  # [x, h, y, energy, range, r, g, b, (group), (shadow), (spot angle)]
		var omni: Light3D
		if l.size() > 10 and float(l[10]) > 0.0:  # light layer: a spot pointing straight down (landing, edge pools)
			var spot: SpotLight3D = SpotLight3D.new()
			spot.spot_range = float(l[4])
			spot.spot_angle = float(l[10])
			spot.spot_angle_attenuation = 0.6
			spot.spot_attenuation = 1.2
			spot.rotation_degrees = Vector3(-90, 0, 0)
			omni = spot
		else:
			var o: OmniLight3D = OmniLight3D.new()
			o.omni_range = float(l[4])
			o.omni_attenuation = 1.4
			omni = o
		omni.position = Vector3(float(l[0]), float(l[1]), float(l[2]))
		var scale: float = _lk("lamp_scale", 1.0)
		if l.size() > 8:  # a room's lamps scale by its own number, "<group>_lamp" (ship.toml [light])
			scale = _lk(str(l[8]) + "_lamp", scale)
		omni.light_energy = float(l[3]) * scale
		omni.light_color = Color(float(l[5]), float(l[6]), float(l[7]))
		omni.shadow_enabled = bool(l[9]) if l.size() > 9 else true
		if l.size() > 8 and str(l[8]) == "flank":  # join: the wing tips' outer faces, outside pieces only
			omni.light_cull_mask = OUTSIDE_LAYER
		if l.size() > 8 and str(l[8]) in ["nav", "nav_tail"]:
			_nav.append([omni, omni.light_energy, str(l[8]) == "nav_tail"])
		root.add_child(omni)


## A look number from the request's light table (ship.toml [light]), else its default.
func _lk(key: String, default: float) -> float:
	return float((_req["light"] as Dictionary).get(key, default))


## The shared metal for a library material name (one ShaderMaterial per name, shared by every piece).
func _metal(name: String) -> Material:
	if not _metals.has(name):
		var m: Array = METALS[name]
		var sm: ShaderMaterial = ShaderMaterial.new()
		sm.shader = load("res://ship/metal.gdshader") as Shader
		var c: Color = m[0]
		sm.set_shader_parameter("base_color", Vector3(c.r, c.g, c.b))
		for i: int in METAL_KEYS.size():
			sm.set_shader_parameter(METAL_KEYS[i], float(m[i + 1]))
		if name in ["hull_silver", "ext_silver_b", "ext_silver_c"]:  # the moonlit wing plates (exterior-2, open 5)
			sm.set_shader_parameter("roughness", minf(float(m[2]) + _lk("hull_rough_add", 0.0), 0.95))
		_metals[name] = sm
	return _metals[name]


## The look: the library metal on every surface whose glTF material is one; an omni light for every cell of emissive
## surfaces (the lamp and strip pieces light the ship). Returns the number of lights it added.
func _dress(ship: Node3D) -> int:
	var cells: Dictionary = {}
	var seen: Dictionary = {}
	var mats: Dictionary = (_req["light"] as Dictionary).get("mats", {})
	var stack: Array = [ship]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		stack.append_array(n.get_children())
		if not (n is MeshInstance3D) or (n as MeshInstance3D).mesh == null:
			continue
		var mi: MeshInstance3D = n
		for i: int in mi.mesh.get_surface_count():
			var mat: Material = mi.mesh.surface_get_material(i)
			if mat == null:
				continue
			if METALS.has(mat.resource_name):
				mi.set_surface_override_material(i, _metal(mat.resource_name))
			elif mat is BaseMaterial3D and not seen.has(mat) and not (mat as BaseMaterial3D).emission_enabled:
				seen[mat] = 0.0
				_by_name[mat.resource_name] = _by_name.get(mat.resource_name, []) + [mat]
				_look(mat, _entry(mats, mat.resource_name))
			elif mat is BaseMaterial3D and (mat as BaseMaterial3D).emission_enabled:
				var bm: BaseMaterial3D = mat
				if not seen.has(bm):  # a shared glTF material is scaled once; its strip light keeps the original
					var look: Dictionary = _entry(mats, bm.resource_name)
					seen[bm] = minf(bm.emission_energy_multiplier, 6.0) * float(look.get("l", 1.0))  # its lights' strength
					_look(bm, look)
					if bm.resource_name.begins_with("glow_nav_"):  # light layer: the nav lenses blink with their lights
						_nav.append([bm, bm.emission_energy_multiplier, bm.resource_name == "glow_nav_white"])
				var box: AABB = _placed(mi) * mi.mesh.get_aabb()
				var area: float = maxf(box.size.x * box.size.z, maxf(box.size.x * box.size.y, box.size.y * box.size.z))
				var c: Vector3 = box.get_center()
				var inside: bool = mi.layers != OUTSIDE_LAYER
				var key: String = "%d_%d_%d_%s_%s" % [floori(c.x / LIGHT_CELL_M), floori(c.y / LIGHT_CELL_M),
					floori(c.z / LIGHT_CELL_M), bm.emission.to_html(false), inside]
				if not cells.has(key):
					cells[key] = [Vector3.ZERO, 0.0, bm.emission, 0.0, float(_entry(mats, bm.resource_name).get("rr", 1.0)),
						inside or _entry(mats, bm.resource_name).get("cull", "") == "inside"]
				var cell: Array = cells[key]
				cell[0] = (cell[0] as Vector3) + c * area
				cell[1] = float(cell[1]) + area
				cell[3] = maxf(float(cell[3]), float(seen[bm]))
	var list: Array = cells.values()
	list.sort_custom(func(a: Array, b: Array) -> bool: return float(a[1]) > float(b[1]))
	list = list.filter(func(c: Array) -> bool: return float(c[3]) > 0.0)  # "l" 0: the surface glows, lights nothing
	var dump: Array = []
	for cell: Array in list.slice(0, MAX_LIGHTS):
		var omni: OmniLight3D = OmniLight3D.new()
		omni.position = (cell[0] as Vector3) / maxf(float(cell[1]), 1e-6) + Vector3(0, 0.12, 0)
		omni.light_color = (cell[2] as Color).lightened(_lk("strip_whiten", 0.15))
		omni.light_energy = clampf(sqrt(float(cell[1])) * 0.9 * float(cell[3]) / 3.0, 0.08, 1.6 * maxf(float(cell[3]) / 6.0, 1.0)) * _lk("strip_light_scale", 1.0)
		omni.omni_range = clampf(2.2 + sqrt(float(cell[1])) * 2.0, 2.2, 5.0) * float(cell[4])
		omni.omni_attenuation = 1.6
		if bool(cell[5]):  # an inside strip lights only the inside (it shone through the smooth skin's top, inside-2)
			omni.light_cull_mask = INSIDE_LAYER
		root.add_child(omni)
		dump.append([_r3(omni.position), snappedf(omni.light_energy, 0.001), snappedf(omni.omni_range, 0.001),
			omni.light_color.to_html(false)])
	_write("lights.json", {"cells": list.size(), "strip_lights": dump})  # where the emissive cells' lights stand (the hall disc's spot, inside-3)
	# vents-b2: the vents' well lights, children of their glow panels; calm by default (the heat panel and its lights
	# hidden; ship --shoot's problem state shows them, _stations)
	var vents: int = VentGlow.add(ship, _lk("vent_well_scale", 1.0))
	for n: Node in ship.find_children("station_vent_*_heat", "Node3D", true, false):
		(n as Node3D).visible = false
	return mini(list.size(), MAX_LIGHTS) + vents


## Every mesh under n on the render layers bits.
func _set_layers(n: Node, bits: int) -> void:
	if n is VisualInstance3D:
		(n as VisualInstance3D).layers = bits
	for c: Node in n.get_children():
		_set_layers(c, bits)


## A mesh's transform in the scene, composed up its parents. mi.global_transform gave each piece's own frame here (every
## strip light of a kind stood at the hall's centre: the disc's warm spot and the dark corridors, inside-3).
func _placed(n: Node) -> Transform3D:
	var xf: Transform3D = Transform3D.IDENTITY
	while n != null and n is Node3D:
		xf = (n as Node3D).transform * xf
		n = n.get_parent()
	return xf


func _r3(v: Vector3) -> Array:
	return [snappedf(v.x, 0.001), snappedf(v.y, 0.001), snappedf(v.z, 0.001)]


## A material's [light.mats] entry: its own, else (details 3b) its family's, the part of its name before "__" (the
## portholes' glow bands ext_porthole__gNN share ext_porthole's).
func _entry(mats: Dictionary, mat_name: String) -> Dictionary:
	if mats.has(mat_name):
		return mats[mat_name]
	if "__" in mat_name:
		return mats.get(mat_name.get_slice("__", 0), {})
	return {}


## One glTF material's night look from ship.toml [light.mats] (the room-by-room light grid, inside-1): "v" base
## colour x, "r" roughness +, "m" metallic, "c" [r, g, b] colour (and emission colour), "e" emission x (else
## emission_scale), "a" alpha, "l" its strip lights x, "rr" their range x (both read by _dress). Without an entry the int_silver_* metals keep
## int_value / int_rough_add and the emissive ones emission_scale.
func _look(bm: BaseMaterial3D, look: Dictionary) -> void:
	if look.is_empty() and bm.resource_name.begins_with("int_silver"):
		look = {"v": _lk("int_value", 1.0), "r": _lk("int_rough_add", 0.0)}
	var a: float = bm.albedo_color.a
	if look.has("c"):
		var c: Array = look["c"]
		bm.albedo_color = Color(float(c[0]), float(c[1]), float(c[2]))
		if bm.emission_enabled:
			bm.emission = bm.albedo_color
	bm.albedo_color = bm.albedo_color * float(look.get("v", 1.0))
	bm.albedo_color.a = float(look.get("a", a))
	bm.roughness = clampf(bm.roughness + float(look.get("r", 0.0)), 0.0, 0.95)
	if look.has("m"):
		bm.metallic = float(look["m"])
	if look.has("s"):  # s: specular (polish 4: the ground's grazing sky reflection)
		bm.metallic_specular = float(look["s"])
	if bm.emission_enabled:
		bm.emission_energy_multiplier *= float(look.get("e", _lk("emission_scale", 1.0)))


## A reflection probe per room (the request's rooms: [id, centre [x, h, y], size [x, h, y], interior]).
func _probes() -> void:
	for r: Array in _req.get("rooms", []):
		var probe: ReflectionProbe = ReflectionProbe.new()
		probe.position = _v(r[1])
		probe.size = _v(r[2])
		probe.box_projection = true
		probe.interior = bool(r[3])
		probe.update_mode = ReflectionProbe.UPDATE_ONCE
		probe.intensity = _lk("probe_" + str(r[0]), _lk("probe_intensity", 1.0) if bool(r[3]) else 1.0)
		root.add_child(probe)


func _shoot() -> void:
	_environment()
	var ship: Node3D = _build()
	var lights: int = _dress(ship)
	_stations(ship)
	_probes()
	print("SHIP look: %d emissive lights" % lights)
	if nav_blink:
		process_frame.connect(_nav_tick)
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.far = 500.0
	root.add_child(_camera)
	_camera.make_current()
	var layer: CanvasLayer = CanvasLayer.new()
	_label = Label.new()
	_label.position = Vector2(20, 12)
	_label.add_theme_font_size_override("font_size", 40)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 8)
	layer.add_child(_label)
	root.add_child(layer)
	var shots: Dictionary = {}
	var images: Dictionary = {}
	for v: Array in _req["views"]:
		_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
		_camera.fov = float(v[4])
		_camera.look_at_from_position(_v(v[2]), _v(v[3]), UP)
		_ab(v[5] if v.size() > 5 else {})
		images[v[0]] = await _shot(v[0], v[1], shots)
		_ab({})
	if _req.has("top"):  # (a --views prefix set alone has no plan view)
		var top: Dictionary = _req["top"]
		_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
		_camera.size = float(top["size_m"])
		_camera.keep_aspect = Camera3D.KEEP_WIDTH
		# looking straight down with +z (south) up the picture: east falls on the left, as plan-3.jpg
		_camera.look_at_from_position(Vector3(0, 60, 0), Vector3.ZERO, Vector3(0, 0, 1))
		images[top["name"]] = await _shot(top["name"], top["title"], shots)
	if _req.has("top_full"):  # the whole ship from straight above, nose to nozzles, framed by its height
		var full: Dictionary = _req["top_full"]
		_camera.size = float(full["size_m"])
		_camera.keep_aspect = Camera3D.KEEP_HEIGHT
		var c: Vector3 = _v(full["centre"])
		_camera.look_at_from_position(c + Vector3(0, 60, 0), c, Vector3(0, 0, 1))
		images[full["name"]] = await _shot(full["name"], full["title"], shots)
		if full.has("day_name"):  # the same frame by day: a sun, a pale sky and daylight ambient
			_day()
			images[full["day_name"]] = await _shot(full["day_name"], full["day_title"], shots)
	var day_views: Array = _req.get("day_views", [])
	if not day_views.is_empty():  # details 1: perspective views by day, after the night's
		if _night_lights.is_empty() or (_night_lights[0] as Light3D).visible:
			_day()
		_camera.projection = Camera3D.PROJECTION_PERSPECTIVE
		_camera.keep_aspect = Camera3D.KEEP_HEIGHT
		for v: Array in day_views:
			_camera.fov = float(v[4])
			_camera.look_at_from_position(_v(v[2]), _v(v[3]), UP)
			images[v[0]] = await _shot(v[0], v[1], shots)
	var rows: Array = []
	for c: Array in _req["compare"]:
		var ref: Image = Image.load_from_file(c[1])
		if ref == null:
			_fail("cannot load %s" % c[1])
			return
		ref.convert(Image.FORMAT_RGB8)
		var pair: Image = _sheet([[ref, images[c[0]]]])
		_save(pair, _out.path_join("compare_%s.png" % c[0]))
	var names: Array = images.keys()
	for i: int in range(0, names.size(), 3):
		rows.append(names.slice(i, i + 3).map(func(n: String) -> Image: return images[n]))
	_save(_sheet(rows), _out.path_join("sheet.png"))
	_write("shots.json", {"shots": shots})
	print("SHIP saved %s" % _out)
	quit(0)


## The stations' states for the shots (station 1, the vents; ship --shoot --vent-states): the request's "stations"
## {piece: {"slats": t, "show": [suffix], "hide": [suffix], "dim": [suffix]}} and "open_rad": each placed piece's leaves `<piece>_slat<k>`
## turned to rotation.x = -open_rad * t, its `<piece>_<suffix>` nodes hidden (the calm glow `cool` for the problem) or
## dimmed (a lamp's glow at a tenth, calm; "<part>:<material suffix>" one surface), as the game drives them.
func _stations(ship: Node3D) -> void:
	var states: Dictionary = _req.get("stations", {})
	for node: Node in ship.get_children():
		var pid: String = String(node.name).rsplit("_", true, 1)[0]
		if not states.has(pid):
			continue
		var st: Dictionary = states[pid]
		for leaf: Node in node.find_children("%s_slat*" % pid, "Node3D", true, false):
			(leaf as Node3D).rotation.x = -float(_req["open_rad"]) * float(st.get("slats", 0.0))
		for suffix: String in st.get("show", []):   # vents-b2: the problem shows the heat panel and its lights
			for n: Node in node.find_children("%s_%s" % [pid, suffix], "Node3D", true, false):
				(n as Node3D).visible = true
		for suffix: String in st.get("hide", []):
			for n: Node in node.find_children("%s_%s" % [pid, suffix], "Node3D", true, false):
				(n as Node3D).visible = false
		for spec: String in st.get("dim", []):
			# "<part>" dims every surface of the part; "<part>:<material suffix>" only the surfaces whose material
			# ends with it (way A: the lamp is the body's `vent_a_body__lamp` surface, "body:__lamp")
			var suffix: String = spec.get_slice(":", 0)
			var mat_suffix: String = spec.get_slice(":", 1) if spec.contains(":") else ""
			for n: Node in node.find_children("%s_%s" % [pid, suffix], "MeshInstance3D", true, false):
				var mi: MeshInstance3D = n
				for i: int in mi.mesh.get_surface_count():
					var src: Material = mi.mesh.surface_get_material(i)
					if src == null or (mat_suffix != "" and not src.resource_name.ends_with(mat_suffix)):
						continue
					var m: BaseMaterial3D = (src as BaseMaterial3D).duplicate()
					m.emission_energy_multiplier *= 0.1
					mi.set_surface_override_material(i, m)


## The engineer's walk (mode "play"): an on-screen window of its own (the project opens every window borderless and
## unfocused for the off-screen reviews), the night scene and the first-person capsule.
func _play(test: bool) -> void:
	if not test:
		root.borderless = false
		root.unfocusable = false
		root.title = "prime-game-art: the ship (P screenshot, H help, Ctrl+Q quit)"
		root.size = Vector2i(1600, 900)
		root.move_to_center()
		root.grab_focus()
	_environment()
	var lights: int = _dress(_build())
	_probes()
	if nav_blink:
		process_frame.connect(_nav_tick)
	var w: Dictionary = _req["walk"]
	var p = Player.new()  # untyped: player.gd's own fields (test, shots, shot())
	p.test = test
	p.setup(float(w["r"]), float(w["h"]), _out)
	root.add_child(p)
	p.global_position = _v(_req["spawn"]) + Vector3(0, 0.05, 0)
	p.rotation_degrees.y = float(_req.get("spawn_yaw", 180.0))
	print("SHIP play ready: %d emissive lights, shots into %s" % [lights, _out])
	if not test:
		return
	for i: int in 30:
		await physics_frame
	var start: Vector3 = p.global_position
	var key: InputEventKey = InputEventKey.new()
	key.physical_keycode = KEY_W
	key.keycode = KEY_W
	key.pressed = true
	Input.parse_input_event(key)
	for i: int in 2 * Engine.physics_ticks_per_second:
		await physics_frame
	key = key.duplicate()
	key.pressed = false
	Input.parse_input_event(key)
	for i: int in 5:
		await physics_frame
	await p.shot()
	var end: Vector3 = p.global_position
	_write("play.json", {"start": _r3(start), "end": _r3(end), "moved_m": snappedf(start.distance_to(end), 0.001),
		"on_floor": p.is_on_floor(), "shots": p.shots})
	print("SHIP play test saved %s" % _out)
	quit(0)


## The nav lamps' blink (light layer): the white tail lamp a short flash once a second (0.12 s), red and green a soft
## pulse (0.55..1.0 over 2 s).
func _nav_tick() -> void:
	var t: float = Time.get_ticks_msec() / 1000.0
	var flash: float = 1.0 if fmod(t, 1.0) < 0.12 else 0.04
	var pulse: float = 0.775 + 0.225 * sin(t * PI)
	for n: Array in _nav:
		var k: float = flash if bool(n[2]) else pulse
		if n[0] is Light3D:
			(n[0] as Light3D).light_energy = float(n[1]) * k
		else:
			(n[0] as BaseMaterial3D).emission_energy_multiplier = float(n[1]) * k


## Day for the top_full_day shot and the day views: a warm sun high in the south-west, a pale sky colour, daylight
## ambient; the moon and the key hidden and the sun unshadowed (details 1: a clean day, no night light left over).
func _day() -> void:
	for l: Light3D in _night_lights:
		l.visible = false
	_env.background_mode = Environment.BG_COLOR
	_env.background_color = Color(0.55, 0.68, 0.85)
	_env.ambient_light_color = Color(0.62, 0.68, 0.78)
	_env.ambient_light_energy = 1.0
	_env.fog_enabled = false
	_env.tonemap_exposure = 1.0
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.light_color = Color(1.0, 0.96, 0.9)
	sun.light_energy = 2.2
	sun.shadow_enabled = false
	sun.directional_shadow_max_distance = 90.0
	sun.rotation_degrees = Vector3(-58, -35, 0)
	root.add_child(sun)


## The walk-through: the night scene as shoot dresses it, the camera at eye height through the keys, every frame
## saved as a PNG (the runner encodes them with Blender's FFmpeg).
func _video() -> void:
	_environment()
	var lights: int = _dress(_build())
	_probes()
	var v: Dictionary = _req["video"]
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.far = 500.0
	_camera.fov = float(v["fov"])
	root.add_child(_camera)
	_camera.make_current()
	var keys: Array = v["keys"]
	var times: Array = [0.0]
	for i: int in range(1, keys.size()):
		times.append(float(times[-1]) + float(keys[i][2]))
	var fps: float = float(v["fps"])
	var count: int = int(float(times[-1]) * fps) + 1
	var dir: String = _out.path_join("frames")
	DirAccess.make_dir_recursive_absolute(dir)
	_camera.look_at_from_position(_v(keys[0][0]), _v(keys[0][1]), UP)
	for i: int in 30:  # the probes, SSAO and glow settle
		await process_frame
	var started: int = Time.get_ticks_msec()
	var k: int = 0
	for f: int in count:
		var t: float = minf(f / fps, float(times[-1]))
		while k < keys.size() - 2 and t > float(times[k + 1]):
			k += 1
		var gap: float = float(times[k + 1]) - float(times[k])
		var w: float = (t - float(times[k])) / gap if gap > 0.0 else 1.0
		_camera.look_at_from_position(_key(keys, times, k, w, 0), _key(keys, times, k, w, 1), UP)
		await RenderingServer.frame_post_draw
		var image: Image = root.get_texture().get_image()
		image.convert(Image.FORMAT_RGB8)
		_save(image, dir.path_join("%05d.png" % f))
	_write("video.json", {"frames": count, "fps": fps, "seconds": times[-1], "lights": lights,
		"render_s": (Time.get_ticks_msec() - started) / 1000.0})
	print("SHIP video %d frames" % count)
	quit(0)


## vents-anim1: one vent's animation in place at night (the game's look), from a still camera at the player's eye:
## the controller (vent_anim.gd) steps 1 / fps per frame through VentAnim.demo; the demo's key moments are shot again
## with their label (the clip's frames have none) for the sheet.
func _vent_anim() -> void:
	_environment()
	var ship: Node3D = _build()
	var lights: int = _dress(ship)
	_probes()
	var a: Dictionary = _req["anim"]
	var piece: Node3D = null
	for n: Node in ship.get_children():
		if String(n.name).begins_with(String(a["piece"]) + "_") or String(n.name) == String(a["piece"]):
			piece = n
			break
	if piece == null:
		_fail("no placed %s" % a["piece"])
		return
	var anim: Node = VentAnim.new()
	anim.manual = true
	piece.add_child(anim)
	anim.setup(piece, String(a["piece"]), float(a["mark_travel"]))
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.far = 500.0
	_camera.fov = float(a["fov"])
	root.add_child(_camera)
	_camera.make_current()
	_camera.look_at_from_position(_v(a["eye"]), _v(a["look"]), UP)
	var layer: CanvasLayer = CanvasLayer.new()
	_label = Label.new()
	_label.position = Vector2(16, 10)
	_label.add_theme_font_size_override("font_size", 30)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 8)
	layer.add_child(_label)
	root.add_child(layer)
	for i: int in 30:  # the probes, SSAO and glow settle
		await process_frame
	var fps: float = float(a["fps"])
	var count: int = int(VentAnim.DEMO_S * fps)
	var dir: String = _out.path_join("frames")
	DirAccess.make_dir_recursive_absolute(dir)
	DirAccess.make_dir_recursive_absolute(_out.path_join("keys"))
	var keys: Array = VentAnim.demo_keys()
	var key_frames: Dictionary = {}
	for kv: Array in keys:
		key_frames[int(round(float(kv[0]) * fps))] = kv[1]
	var tiles: Array = []
	var started: int = Time.get_ticks_msec()
	var states: Array = []
	for f: int in count:
		var inp: Array = VentAnim.demo(f / fps)
		anim.problem = inp[0]
		anim.hold = inp[1]
		anim.step(1.0 / fps)
		await RenderingServer.frame_post_draw
		var image: Image = root.get_texture().get_image()
		image.convert(Image.FORMAT_RGB8)
		_save(image, dir.path_join("%05d.png" % f))
		if states.is_empty() or states[-1][1] != anim.state:
			states.append([snappedf(f / fps, 0.01), anim.state])
		if key_frames.has(f):
			_label.text = "%.2f s  %s" % [f / fps, key_frames[f]]
			await RenderingServer.frame_post_draw
			var shot: Image = root.get_texture().get_image()
			shot.convert(Image.FORMAT_RGB8)
			_save(shot, _out.path_join("keys/%05d.png" % f))
			shot.resize(320, 180, Image.INTERPOLATE_LANCZOS)
			tiles.append(shot)
			_label.text = ""
	var sheet: Image = Image.create(1280, 180 * ceili(tiles.size() / 4.0), false, Image.FORMAT_RGB8)
	for i: int in tiles.size():
		sheet.blit_rect(tiles[i], Rect2i(0, 0, 320, 180), Vector2i((i % 4) * 320, (i / 4) * 180))
	_save(sheet, _out.path_join("keys_sheet.png"))
	_write("anim.json", {"frames": count, "fps": fps, "seconds": VentAnim.DEMO_S, "lights": lights, "states": states,
		"render_s": (Time.get_ticks_msec() - started) / 1000.0})
	print("SHIP vent_anim %d frames" % count)
	quit(0)


## Key j (0 eye, 1 look) between keys k and k + 1 at weight w, cubic in time through the neighbouring keys.
func _key(keys: Array, times: Array, k: int, w: float, j: int) -> Vector3:
	var a: Vector3 = _v(keys[k][j])
	var b: Vector3 = _v(keys[k + 1][j])
	var span: float = float(times[k + 1]) - float(times[k])
	if span <= 0.0:  # two keys at one time (a 0 s key): no curve to follow
		return b
	var pre: Vector3 = _v(keys[k - 1][j]) if k > 0 else a
	var pre_t: float = float(times[k - 1]) - float(times[k]) if k > 0 else -span
	var post: Vector3 = _v(keys[k + 2][j]) if k + 2 < keys.size() else b
	var post_t: float = float(times[k + 2]) - float(times[k]) if k + 2 < keys.size() else 2.0 * span
	return a.cubic_interpolate_in_time(b, pre, post, w, span, pre_t, post_t)


## fix 2: a view's A/B switch ({"ssil"|"ssao"|"glow"|"shadows": false}, ship.py --views): those parts of the night
## look off for the shot; {} puts back what the environment had (the directional lights' shadows: the moon and the
## key). A row's "mats" ({glTF material name: {"roughness", "metallic", "specular"}}) sets those values on that
## material's glTF copies (not the METALS) for that one shot; _ab({}) puts them back.
func _ab(off: Dictionary) -> void:
	if _ab_env.is_empty():
		_ab_env = {"ssil": _env.ssil_enabled, "ssao": _env.ssao_enabled, "glow": _env.glow_enabled,
			"shadows": [] as Array}
		for l: Node in _night_lights:
			(_ab_env["shadows"] as Array).append((l as DirectionalLight3D).shadow_enabled)
	for bm: BaseMaterial3D in _ab_saved:
		var was: Array = _ab_saved[bm]
		bm.roughness = was[0]
		bm.metallic = was[1]
		bm.metallic_specular = was[2]
	_ab_saved.clear()
	var mats: Dictionary = off.get("mats", {})
	for mat_name: String in mats:
		for bm: BaseMaterial3D in _by_name.get(mat_name, []):
			var want: Dictionary = mats[mat_name]
			_ab_saved[bm] = [bm.roughness, bm.metallic, bm.metallic_specular]
			bm.roughness = float(want.get("roughness", bm.roughness))
			bm.metallic = float(want.get("metallic", bm.metallic))
			bm.metallic_specular = float(want.get("specular", bm.metallic_specular))
	_env.ssil_enabled = bool(off.get("ssil", _ab_env["ssil"]))
	_env.ssao_enabled = bool(off.get("ssao", _ab_env["ssao"]))
	_env.glow_enabled = bool(off.get("glow", _ab_env["glow"]))
	for i: int in _night_lights.size():
		var had: bool = (_ab_env["shadows"] as Array)[i]
		(_night_lights[i] as DirectionalLight3D).shadow_enabled = bool(off.get("shadows", had)) and had


func _shot(name: String, title: String, shots: Dictionary) -> Image:
	_label.text = title
	for i: int in 30:
		await process_frame
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	image.convert(Image.FORMAT_RGB8)
	_save(image, _out.path_join("%s.png" % name))
	shots[name] = {"draw_calls": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		"primitives": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)}
	return image


## Each row's tiles side by side over SHEET_W (each tile scaled to the row's first tile's height), rows stacked.
func _sheet(rows: Array) -> Image:
	var scaled: Array = []
	var height: int = 0
	for row: Array in rows:
		var h0: float = float((row[0] as Image).get_height())
		var widths: Array = row.map(func(img: Image) -> float: return img.get_width() * h0 / img.get_height())
		var total: float = 0.0
		for w: float in widths:
			total += w
		var k: float = (SHEET_W - (row.size() - 1) * GAP) / total
		var tiles: Array = []
		for i: int in row.size():
			var img: Image = (row[i] as Image).duplicate() as Image
			img.resize(maxi(1, int(widths[i] * k)), maxi(1, int(h0 * k)), Image.INTERPOLATE_LANCZOS)
			tiles.append(img)
		scaled.append(tiles)
		height += int(h0 * k) + GAP
	var sheet: Image = Image.create_empty(SHEET_W, maxi(1, height - GAP), false, Image.FORMAT_RGB8)
	sheet.fill(Color(0.97, 0.97, 0.97))
	var y: int = 0
	for tiles: Array in scaled:
		var x: int = 0
		for img: Image in tiles:
			sheet.blit_rect(img, Rect2i(Vector2i.ZERO, img.get_size()), Vector2i(x, y))
			x += img.get_width() + GAP
		y += (tiles[0] as Image).get_height() + GAP
	return sheet


func _v(a: Variant) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))


func _save(image: Image, path: String) -> void:
	var error: Error = image.save_png(path)
	if error != OK:
		_fail("cannot save %s: %s" % [path, error_string(error)])


func _write(name: String, data: Dictionary) -> void:
	var f: FileAccess = FileAccess.open(_out.path_join(name), FileAccess.WRITE)
	f.store_string(JSON.stringify(data, " "))
	f.close()


func _fail(why: String) -> void:
	printerr("SHIP error %s" % why)
	quit(1)
