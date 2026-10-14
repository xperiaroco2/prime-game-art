extends SceneTree
## The ragdoll proof (art #115, `tools/run.py ragdoll --fall`): a character GLB with its ragdoll data built by
## builder.gd, started from the Idle pose with a forward velocity, falls on a floor. Headless (`check`) it asserts:
## no NaN, every joint inside its limits and holding together, no bone faster than a bound after 0.5 s, the body at rest
## on the floor within a few seconds, the parts on the `downed` layer colliding with the world only (a player box on
## the `living_players` layer stands in the fall and is passed through), and the sockets (a hat on Head, the package
## on the chest) following their simulated bones. In an off-screen window (`shots`) it also shoots the fall front and
## side, and the shapes over the body. Arguments after --: <glb res path> <data json> <out dir> <check|shots>.

const Builder = preload("res://builder.gd")

const STEP_S: float = 1.0 / 60.0
const RUN_S: float = 4.0
const FORWARD_M_S: float = 3.0  # the avatar's velocity at the knockdown: a run's speed, forwards
const START_UP_M: float = 0.02
const SPEED_MAX_M_S: float = 12.0  # after 0.5 s no part moves faster (a 1.8 m fall reaches about 6 m/s)
const REST_SPEED_M_S: float = 0.15
const REST_BY_S: float = 3.5
const LIE_MAX_Y_M: float = 0.45  # at rest every body lies below this (none on the player box, 0.9 m tall)
const FLOOR_MIN_Y_M: float = -0.03
# Two tiers. In the fall a soft-constraint overshoot past a limit is allowed for an instant (the landing's impact);
# over the last REST_TIER_S at rest every joint lies within its limit plus a small slack and holds together.
# Measured (Jolt, slice_m1, 3 m/s, a grid of 11 settings; art #115): in the fall the worst joint passes its limit by
# about 21 deg (the feet, dragged along the floor) and opens by about 23 mm; at rest, pressed on the floor by the body,
# a joint lies 6 to 12 deg past its limit (the ankle, the spine or a shoulder, varying with the landing) and the
# ankles open by about 20 mm. A wrong axis or a lost joint shows as 30 degrees and more.
const OVER_MAX_DEG: float = 25.0
const ANCHOR_MAX_M: float = 0.04
const REST_TIER_S: float = 0.5
const REST_OVER_MAX_DEG: float = 12.0
const REST_ANCHOR_MAX_M: float = 0.025
const SOCKET_MAX_M: float = 0.002
const SHOT_TIMES: Array[float] = [0.0, 0.2, 0.4, 0.6, 0.85, 1.2, 2.0, 3.5]
const CELL: Vector2i = Vector2i(160, 200)

var data: Dictionary
var out_dir: String
var shots_mode: bool = false
var character: Node3D
var skeleton: Skeleton3D
var sim: PhysicalBoneSimulator3D
var pbs: Dictionary = {}  # bone -> PhysicalBone3D
var start_bone: Dictionary = {}  # bone -> Transform3D at the start
var follow: Dictionary = {}  # socket bone -> its pose on its simulated body, taken at the start
var sockets: Array = []  # [marker, bone name, local offset]
var cams: Array[SubViewport] = []
var shape_meshes: Array[MeshInstance3D] = []
var t: float = 0.0
var step: int = 0
var step_n: int = 0
var started: bool = false
var failures: PackedStringArray = PackedStringArray()
var worst: Dictionary = {"cone_over_deg": 0.0, "hinge_over_deg": 0.0, "anchor_m": 0.0, "speed_after_05_m_s": 0.0,
		"rest_over_deg": -INF, "rest_anchor_m": 0.0, "socket_m": 0.0, "hinge_min_deg": {},
		"hinge_max_deg": {}, "nan": false}
var expected: Array = []  # per socket, the point its marker should be at after the last skeleton update
var rest_s: float = -1.0
var shots: Dictionary = {"front": [], "side": []}
var done: bool = false


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 4:
		_fail("usage: <glb res path> <data json> <out dir> <check|shots>")
		return
	data = JSON.parse_string(FileAccess.get_file_as_string(args[1]))
	out_dir = args[2]
	shots_mode = args[3] == "shots"
	if args.size() > 4:  # a tuning grid's overrides: {"foot_kg", "hand_kg", "angular_damp", "friction"}
		_override(JSON.parse_string(args[4]))
	DirAccess.make_dir_recursive_absolute(out_dir)
	var watchdog: SceneTreeTimer = create_timer(120.0)
	watchdog.timeout.connect(func() -> void: _fail("watchdog: no result in 120 s"))
	_stage(args[0])


func _override(o: Dictionary) -> void:
	var total: float = float(data["total_mass_kg"])
	for bone: Dictionary in data["bones"]:
		var n: String = bone["bone"]
		if o.has("foot_kg") and n.begins_with("Foot."):
			bone["mass_share"] = float(o["foot_kg"]) / total
		if o.has("hand_kg") and n.begins_with("Wrist."):
			bone["mass_share"] = float(o["hand_kg"]) / total
	for key: String in ["angular_damp", "friction", "linear_damp"]:
		if o.has(key):
			data["material"][key] = float(o[key])
	data["overrides"] = o


func _stage(glb: String) -> void:
	var world: Node3D = Node3D.new()
	root.add_child(world)
	var floor_body: StaticBody3D = StaticBody3D.new()
	floor_body.collision_layer = 1
	floor_body.collision_mask = 0
	var floor_shape: CollisionShape3D = CollisionShape3D.new()
	var box: BoxShape3D = BoxShape3D.new()
	box.size = Vector3(20, 1, 20)
	floor_shape.shape = box
	floor_shape.position = Vector3(0, -0.5, 0)
	floor_body.add_child(floor_shape)
	world.add_child(floor_body)
	# A player standing where the body falls: on living_players (layer 2), which the ragdoll's mask leaves out.
	var player: StaticBody3D = StaticBody3D.new()
	player.collision_layer = 2
	player.collision_mask = 2
	var player_shape: CollisionShape3D = CollisionShape3D.new()
	var pbox: BoxShape3D = BoxShape3D.new()
	pbox.size = Vector3(1.2, 0.9, 0.5)
	player_shape.shape = pbox
	player_shape.position = Vector3(0, 0.45, 1.1)
	player.add_child(player_shape)
	world.add_child(player)
	if shots_mode:
		_scenery(world)
	var scene: PackedScene = load(glb) as PackedScene
	if scene == null:
		_fail("cannot load " + glb)
		return
	character = scene.instantiate() as Node3D
	character.position.y = START_UP_M
	world.add_child(character)
	var found: Array[Node] = character.find_children("*", "Skeleton3D", true, false)
	if found.is_empty():
		_fail("no Skeleton3D")
		return
	skeleton = found[0] as Skeleton3D
	var players: Array[Node] = character.find_children("*", "AnimationPlayer", true, false)
	if not players.is_empty():
		var ap: AnimationPlayer = players[0] as AnimationPlayer
		if ap.has_animation("Idle"):
			ap.play("Idle")
			ap.seek(0.0, true)
			ap.pause()
	sim = Builder.build(skeleton, data)
	pbs = Builder.bodies(sim)
	_sockets()
	skeleton.skeleton_updated.connect(_on_skeleton_updated)
	if shots_mode:
		for pb: PhysicalBone3D in pbs.values():
			_shape_mesh(pb)


func _sockets() -> void:
	# Socket_Head (Head): a hat; Socket_Carry (the contract's Chest, the rig's Torso): the package, 0.72 m in front
	# at 0.8 m in the character scene, here in model space (front +Z).
	var specs: Array = [["Socket_Head", "Head", Vector3(0, 0.25, 0), Vector3(0.3, 0.12, 0.3)],
			["Socket_Carry", "Torso", Vector3(0, 0.8, 0.72), Vector3(0.4, 0.3, 0.3)]]
	for s: Array in specs:
		var attach: BoneAttachment3D = BoneAttachment3D.new()
		attach.name = String(s[0]) + "_Attach"
		attach.bone_name = s[1]
		skeleton.add_child(attach)
		var marker: Marker3D = Marker3D.new()
		marker.name = s[0]
		attach.add_child(marker)
		var bone_rest: Transform3D = skeleton.get_bone_global_rest(skeleton.find_bone(s[1]))
		var point: Vector3 = s[2]
		if s[1] == "Head":
			point = bone_rest.origin + Vector3(0, 0.25, 0)
		marker.position = bone_rest.affine_inverse() * point
		var mesh: MeshInstance3D = MeshInstance3D.new()
		var bm: BoxMesh = BoxMesh.new()
		bm.size = s[3]
		mesh.mesh = bm
		var mat: StandardMaterial3D = StandardMaterial3D.new()
		mat.albedo_color = Color(0.85, 0.55, 0.15) if s[0] == "Socket_Carry" else Color(0.2, 0.35, 0.8)
		mesh.material_override = mat
		marker.add_child(mesh)
		sockets.append([marker, s[1], marker.position])


func _shape_mesh(pb: PhysicalBone3D) -> void:
	var shape: Shape3D = (pb.get_node("Shape") as CollisionShape3D).shape
	var mesh: MeshInstance3D = MeshInstance3D.new()
	if shape is BoxShape3D:
		var bm: BoxMesh = BoxMesh.new()
		bm.size = (shape as BoxShape3D).size
		mesh.mesh = bm
	else:
		var cm: CapsuleMesh = CapsuleMesh.new()
		cm.radius = (shape as CapsuleShape3D).radius
		cm.height = (shape as CapsuleShape3D).height
		mesh.mesh = cm
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.albedo_color = Color(0.1, 0.9, 0.4, 0.45)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.no_depth_test = true
	mesh.material_override = mat
	pb.add_child(mesh)
	shape_meshes.append(mesh)


func _scenery(world: Node3D) -> void:
	var env: WorldEnvironment = WorldEnvironment.new()
	var e: Environment = Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.32, 0.34, 0.38)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.6, 0.6, 0.65)
	env.environment = e
	world.add_child(env)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 30, 0)
	sun.shadow_enabled = true
	world.add_child(sun)
	var ground: MeshInstance3D = MeshInstance3D.new()
	var pm: PlaneMesh = PlaneMesh.new()
	pm.size = Vector2(12, 12)
	ground.mesh = pm
	world.add_child(ground)
	var ghost: MeshInstance3D = MeshInstance3D.new()
	var gm: BoxMesh = BoxMesh.new()
	gm.size = Vector3(1.2, 0.9, 0.5)
	ghost.mesh = gm
	ghost.position = Vector3(0, 0.45, 1.1)
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.albedo_color = Color(0.9, 0.2, 0.2, 0.25)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	ghost.material_override = mat
	world.add_child(ghost)
	for view: Array in [["front", Vector3(0.0, 1.2, 4.8), Vector3(0, 0.6, 0.6)],
			["side", Vector3(4.6, 1.2, 0.8), Vector3(0, 0.6, 0.8)]]:
		var vp: SubViewport = SubViewport.new()
		vp.name = view[0]
		vp.size = CELL * 2
		vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		root.add_child(vp)
		var cam: Camera3D = Camera3D.new()
		cam.fov = 45
		vp.add_child(cam)
		cam.look_at_from_position(view[1], view[2], Vector3.UP)
		cams.append(vp)


func _bone_global(name: String) -> Transform3D:
	var pb: PhysicalBone3D = pbs[name]
	return pb.global_transform * pb.body_offset.affine_inverse()


func _physics_process(_delta: float) -> bool:
	if done or skeleton == null:
		return false
	if not started:
		step += 1
		if step == 3 and shots_mode:
			_capture("shapes")
		if step < (6 if shots_mode else 2):
			return false
		for mesh: MeshInstance3D in shape_meshes:
			mesh.visible = false
		var forward: Vector3 = character.global_transform.basis * Vector3(0, 0, 1)  # the model's front, +Z
		Builder.start(sim, data, forward * FORWARD_M_S)
		started = true
		t = 0.0
		return false
	if start_bone.is_empty():
		for name: String in pbs:  # the joints are made now, one step after the start (Builder.start)
			start_bone[name] = _bone_global(name)
		return false
	t += STEP_S
	_measure()
	if shots_mode and not SHOT_TIMES.is_empty() and shots["front"].size() < SHOT_TIMES.size() \
			and t + 1e-6 >= SHOT_TIMES[shots["front"].size()]:
		_capture("fall")
	if t >= RUN_S and (not shots_mode or shots["front"].size() >= SHOT_TIMES.size()):
		_finish()
	return false


func _measure() -> void:
	step_n += 1
	var fastest: float = 0.0
	var lowest: float = INF
	var highest: float = -INF
	for name: String in pbs:
		var pb: PhysicalBone3D = pbs[name]
		var p: Vector3 = pb.global_position
		if not p.is_finite():
			worst["nan"] = true
			return
		fastest = maxf(fastest, pb.linear_velocity.length())
		lowest = minf(lowest, p.y)
		highest = maxf(highest, p.y)
	if t > 0.5:
		worst["speed_after_05_m_s"] = maxf(worst["speed_after_05_m_s"], fastest)
	if fastest < REST_SPEED_M_S:
		if rest_s < 0:
			rest_s = t
	else:
		rest_s = -1.0
	worst["lowest_y_m"] = lowest
	worst["highest_y_m"] = highest
	for bone: Dictionary in data["bones"]:
		if bone.get("parent") == null:
			continue
		var c: String = bone["bone"]
		var p: String = bone["parent"]
		var j: Dictionary = bone["joint"]
		var rel0: Basis = start_bone[p].basis.inverse() * start_bone[c].basis
		var now: Basis = _bone_global(p).basis.inverse() * _bone_global(c).basis
		var delta: Quaternion = Quaternion((rel0.inverse() * now).orthonormalized())
		var anchor: Vector3 = Vector3(j["anchor"][0], j["anchor"][1], j["anchor"][2])
		var from_child: Vector3 = _bone_global(c) * anchor
		var from_parent: Vector3 = _bone_global(p) * (start_bone[p].affine_inverse() * (start_bone[c] * anchor))
		var gap: float = from_child.distance_to(from_parent)
		worst["anchor_m"] = maxf(worst["anchor_m"], gap)
		_per_joint(c, "anchor_m", gap)
		var at_rest: bool = t >= RUN_S - REST_TIER_S
		if at_rest:
			worst["rest_anchor_m"] = maxf(worst["rest_anchor_m"], gap)
			_per_joint(c, "rest_anchor_m", gap)
		if j["type"] == "cone":
			var swing: float = rad_to_deg((delta * Vector3.UP).angle_to(Vector3.UP))
			worst["cone_over_deg"] = maxf(worst["cone_over_deg"], swing - float(j["swing_deg"]))
			_per_joint(c, "over_deg", swing - float(j["swing_deg"]))
			if at_rest:
				worst["rest_over_deg"] = maxf(worst["rest_over_deg"], swing - float(j["swing_deg"]))
				_per_joint(c, "rest_over_deg", swing - float(j["swing_deg"]))
		elif j["type"] == "hinge":
			var axis: Vector3 = Vector3(j["axis"][0], j["axis"][1], j["axis"][2])
			var ang: float = rad_to_deg(2.0 * atan2(Vector3(delta.x, delta.y, delta.z).dot(axis), delta.w))
			ang = wrapf(ang, -180.0, 180.0)
			worst["hinge_min_deg"][c] = minf(worst["hinge_min_deg"].get(c, 0.0), ang)
			worst["hinge_max_deg"][c] = maxf(worst["hinge_max_deg"].get(c, 0.0), ang)
			var over: float = maxf(float(j["min_deg"]) - ang, ang - float(j["max_deg"]))
			worst["hinge_over_deg"] = maxf(worst["hinge_over_deg"], over)
			_per_joint(c, "over_deg", over)
			if at_rest:
				worst["rest_over_deg"] = maxf(worst["rest_over_deg"], over)
				_per_joint(c, "rest_over_deg", over)


## Per joint: the worst value of key and when (seconds after the start).
func _per_joint(bone: String, key: String, value: float) -> void:
	var rec: Dictionary = worst.get("per_joint", {})
	worst["per_joint"] = rec
	var r: Dictionary = rec.get(bone, {})
	rec[bone] = r
	if value > float(r.get(key, -INF)):
		r[key] = value
		r[key + "_at_s"] = snappedf(t, 0.001)


## The sockets, read when the skeleton has applied the simulation (its skeleton_updated signal; the BoneAttachment3Ds
## update on it; outside the signal the skeleton reports its unmodified pose).
func _on_skeleton_updated() -> void:
	if started and not done:
		_check_sockets()


func _check_sockets() -> void:
	if start_bone.is_empty():
		return
	expected.resize(sockets.size())
	for i: int in sockets.size():
		var s: Array = sockets[i]
		var bone: String = s[1]
		var owner_name: String = bone if pbs.has(bone) else String(data["followers"].get(bone, ""))
		var bone_now: Transform3D = skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone(bone))
		if not follow.has(bone):  # the first check after the start: the bone's pose on its body
			follow[bone] = _bone_global(owner_name).affine_inverse() * bone_now
			continue
		var expect: Transform3D = _bone_global(owner_name) * (follow[bone] as Transform3D)
		worst["socket_bone_m"] = maxf(worst.get("socket_bone_m", 0.0), bone_now.origin.distance_to(expect.origin))
		expected[i] = expect * (s[2] as Vector3)


## The markers after the frame: their BoneAttachment3Ds update on the same skeleton_updated signal, after this
## script's handler (measured: compared inside the handler they lag by one update, about 0.1 m).
func _process(_delta: float) -> bool:
	if started and not done:
		for i: int in mini(expected.size(), sockets.size()):
			if expected[i] != null:
				var marker: Marker3D = sockets[i][0]
				worst["socket_m"] = maxf(worst["socket_m"], marker.global_position.distance_to(expected[i]))
	return false


func _capture(kind: String) -> void:
	await RenderingServer.frame_post_draw
	for vp: SubViewport in cams:
		var img: Image = vp.get_texture().get_image()
		if kind != "shapes":  # the shapes keep the viewport's full size (two cells of 320x400, a 640x400 pair)
			img.resize(CELL.x, CELL.y, Image.INTERPOLATE_LANCZOS)
		if kind == "shapes":
			img.save_png(out_dir.path_join("shapes_%s.png" % vp.name))
			shots[vp.name + "_shapes"] = img
		else:
			shots[vp.name].append(img)


func _sheet() -> void:
	var cols: int = SHOT_TIMES.size()
	var sheet: Image = Image.create(CELL.x * cols, CELL.y * 2, false, Image.FORMAT_RGBA8)
	for r: int in 2:
		var row: Array = shots["front" if r == 0 else "side"]
		for i: int in row.size():
			var img: Image = row[i]
			img.convert(Image.FORMAT_RGBA8)
			sheet.blit_rect(img, Rect2i(Vector2i.ZERO, CELL), Vector2i(i * CELL.x, r * CELL.y))
	sheet.save_png(out_dir.path_join("fall_sheet.png"))
	var big: Vector2i = CELL * 2
	var pair: Image = Image.create(big.x * 2, big.y, false, Image.FORMAT_RGBA8)
	for i: int in 2:
		var img: Image = shots.get(("front" if i == 0 else "side") + "_shapes")
		if img != null:
			img.convert(Image.FORMAT_RGBA8)
			pair.blit_rect(img, Rect2i(Vector2i.ZERO, big), Vector2i(i * big.x, 0))
	pair.save_png(out_dir.path_join("shapes_sheet.png"))


func _finish() -> void:
	done = true
	if worst["nan"]:
		failures.append("a body's position became NaN")
	if worst["cone_over_deg"] > OVER_MAX_DEG:
		failures.append("a cone joint swung %.1f deg past its limit in the fall" % worst["cone_over_deg"])
	if worst["hinge_over_deg"] > OVER_MAX_DEG:
		failures.append("a hinge bent %.1f deg past its limit in the fall" % worst["hinge_over_deg"])
	if worst["anchor_m"] > ANCHOR_MAX_M:
		failures.append("a joint came apart by %.3f m in the fall" % worst["anchor_m"])
	if worst["rest_over_deg"] > REST_OVER_MAX_DEG:
		failures.append("at rest a joint lies %.1f deg past its limit" % worst["rest_over_deg"])
	if worst["rest_anchor_m"] > REST_ANCHOR_MAX_M:
		failures.append("at rest a joint is apart by %.3f m" % worst["rest_anchor_m"])
	if worst["speed_after_05_m_s"] > SPEED_MAX_M_S:
		failures.append("a body moved at %.1f m/s after 0.5 s" % worst["speed_after_05_m_s"])
	if rest_s < 0 or rest_s > REST_BY_S:
		failures.append("not at rest by %.1f s (rest from %.2f s)" % [REST_BY_S, rest_s])
	if worst.get("lowest_y_m", 0.0) < FLOOR_MIN_Y_M:
		failures.append("a body rests through the floor (y %.3f)" % worst["lowest_y_m"])
	if worst.get("highest_y_m", 9.0) > LIE_MAX_Y_M:
		failures.append("a body rests %.2f m up: not lying on the floor (the player box?)" % worst["highest_y_m"])
	if worst["socket_m"] > SOCKET_MAX_M:
		failures.append("a socket lagged its bone by %.4f m" % worst["socket_m"])
	if worst.get("socket_bone_m", 0.0) > 0.01:
		failures.append("a socket's bone lagged its simulated body by %.4f m" % worst["socket_bone_m"])
	for pb: PhysicalBone3D in pbs.values():
		if pb.collision_layer != 4 or pb.collision_mask != 1:
			failures.append("%s: layer %d mask %d, want 4 (downed) and 1 (world)" % [pb.name, pb.collision_layer, pb.collision_mask])
			break
	var report: Dictionary = {"godot": Engine.get_version_info().string,
			"physics_engine": ProjectSettings.get_setting("physics/3d/physics_engine"),
			"bodies": pbs.size(), "joints": sim.get_children().filter(func(n: Node) -> bool: return n is Joint3D).size(),
			"rest_s": rest_s, "run_s": RUN_S, "overrides": data.get("overrides", {}), "forward_m_s": FORWARD_M_S, "worst": worst, "failures": failures,
			"rest_positions": {}}
	for name: String in pbs:
		var p: Vector3 = (pbs[name] as PhysicalBone3D).global_position
		report["rest_positions"][name] = [snappedf(p.x, 0.001), snappedf(p.y, 0.001), snappedf(p.z, 0.001)]
	if shots_mode:
		_sheet()
	var f: FileAccess = FileAccess.open(out_dir.path_join("fall.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, " "))
	f.close()
	print("RAGDOLL result %s" % ("ok" if failures.is_empty() else "fail"))
	for line: String in failures:
		print("RAGDOLL failure " + line)
	quit(0 if failures.is_empty() else 1)


func _fail(why: String) -> void:
	print("RAGDOLL error " + why)
	done = true
	quit(2)
