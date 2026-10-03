extends SceneTree
## Describes an imported character for `tools/run.py godot-check` (docs/godot.md); the runner makes the assertions.
## Headless:
##   godot --headless --path godot -s res://check/inspect.gd -- <res://import/x.glb> <out.json> [request.json]
## request.json (optional): {"poses": {"<animation>": [seconds, ...]}}: every joint's world position at those times.
## Writes out.json: the scene's nodes; each Skeleton3D (bones, parents, world rest joints); each MeshInstance3D (its
## skeleton, skin binds, surfaces, materials, rest-pose bounds deformed by Godot's skinning); each AnimationPlayer (its
## animations: length, tracks, the tracks that do not resolve, how far the bones move between samples at 0, 1/3 and
## 2/3 of the length); the requested poses. Prints INSPECT saved <path>, or INSPECT error <why> and exits 1.

const Character = preload("res://lib/character.gd")
const WATCHDOG_S: float = 240.0


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 2:
		_fail("usage: -- <res://import/x.glb> <out.json> [request.json]")
		return
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	_run(args)


func _run(args: PackedStringArray) -> void:
	var request: Variant = Character.read_json(args[2] if args.size() > 2 else "")
	var scene: Node = Character.instance(args[0], root)
	if scene == null:
		_fail("cannot load %s as a PackedScene" % args[0])
		return
	# The meshes register their skins with the skeleton once the tree runs; Godot's skinning needs that.
	await process_frame
	var out: Dictionary = {
		"godot": Engine.get_version_info()["string"],
		"scene": args[0],
		"root": {"name": str(scene.name), "class": scene.get_class()},
		"nodes": _nodes(scene),
		"skeletons": [],
		"meshes": [],
		"players": [],
		"poses": {},
	}
	var skeletons: Array[Node] = Character.nodes_of(scene, "Skeleton3D")
	for node: Node in skeletons:
		var skeleton: Skeleton3D = node as Skeleton3D
		skeleton.reset_bone_poses()
		out["skeletons"].append(_skeleton(scene, skeleton))
	for mesh: MeshInstance3D in Character.meshes(scene):
		out["meshes"].append(_mesh(scene, mesh))
	var skeleton0: Skeleton3D = skeletons[0] as Skeleton3D if skeletons.size() == 1 else null
	for node: Node in Character.nodes_of(scene, "AnimationPlayer"):
		out["players"].append(_player(scene, node as AnimationPlayer, skeleton0))
	if skeleton0 != null and not out["players"].is_empty():
		var player: AnimationPlayer = Character.nodes_of(scene, "AnimationPlayer")[0] as AnimationPlayer
		var poses: Dictionary = request.get("poses", {}) if request is Dictionary else {}
		for anim: String in poses:
			if not player.has_animation(anim):
				continue
			out["poses"][anim] = {}
			for t: float in poses[anim]:
				Character.pose_at(player, skeleton0, anim, t)
				out["poses"][anim][str(t)] = Character.joints(skeleton0)
		player.stop()
		skeleton0.reset_bone_poses()
	if not Character.write_json(args[1], out):
		_fail("cannot write %s" % args[1])
		return
	print("INSPECT saved ", args[1])
	quit(0)


func _nodes(scene: Node) -> Array:
	var out: Array = []
	for node: Node in scene.find_children("*", "", true, false):
		out.append({"path": str(scene.get_path_to(node)), "class": node.get_class()})
	return out


func _skeleton(scene: Node, skeleton: Skeleton3D) -> Dictionary:
	var names: Array = []
	var parents: Array = []
	for i: int in skeleton.get_bone_count():
		names.append(skeleton.get_bone_name(i))
		parents.append(skeleton.get_bone_parent(i))
	return {
		"path": str(scene.get_path_to(skeleton)),
		"bones": names,
		"parents": parents,
		"rest_joints": Character.joints(skeleton),
		"transform_origin": Character.vec(skeleton.global_transform.origin),
		"transform_basis_identity": skeleton.global_transform.basis.is_equal_approx(Basis.IDENTITY),
	}


func _mesh(scene: Node, mesh: MeshInstance3D) -> Dictionary:
	var target: Node = mesh.get_node_or_null(mesh.skeleton) if not mesh.skeleton.is_empty() else null
	var skin: Skin = mesh.skin
	var binds: Array = []
	var bad_binds: Array = []
	if skin != null:
		for i: int in skin.get_bind_count():
			var bind_name: String = str(skin.get_bind_name(i))
			var bone: int = skin.get_bind_bone(i)
			binds.append(bind_name if not bind_name.is_empty() else str(bone))
			if target is Skeleton3D:
				var sk: Skeleton3D = target as Skeleton3D
				var found: int = sk.find_bone(bind_name) if not bind_name.is_empty() else bone
				if found < 0 or found >= sk.get_bone_count():
					bad_binds.append(bind_name if not bind_name.is_empty() else str(bone))
	var materials: Array = []
	var vertices: int = 0
	if mesh.mesh != null:
		for s: int in mesh.mesh.get_surface_count():
			vertices += mesh.mesh.surface_get_array_len(s)
			var mat: Material = mesh.get_active_material(s)
			var entry: Dictionary = {"name": mat.resource_name if mat != null else ""}
			if mat is BaseMaterial3D:
				var base: BaseMaterial3D = mat as BaseMaterial3D
				var c: Color = base.albedo_color
				entry["albedo"] = [snappedf(c.r, 0.0001), snappedf(c.g, 0.0001), snappedf(c.b, 0.0001)]
				entry["metallic"] = snappedf(base.metallic, 0.001)
				entry["roughness"] = snappedf(base.roughness, 0.001)
				entry["textured"] = base.albedo_texture != null
			materials.append(entry)
	return {
		"name": str(mesh.name),
		"path": str(scene.get_path_to(mesh)),
		"skeleton": str(scene.get_path_to(target)) if target != null else "",
		"skeleton_is_skeleton3d": target is Skeleton3D,
		"skin": skin != null,
		"binds": binds,
		"unresolved_binds": bad_binds,
		"surfaces": mesh.mesh.get_surface_count() if mesh.mesh != null else 0,
		"vertices": vertices,
		"materials": materials,
		"rest_bounds": Character.bounds(Character.skinned_points(mesh)),
	}


func _player(scene: Node, player: AnimationPlayer, skeleton: Skeleton3D) -> Dictionary:
	var anim_root: Node = player.get_node_or_null(player.root_node)
	var anims: Dictionary = {}
	for name: StringName in player.get_animation_list():
		var anim: Animation = player.get_animation(name)
		var unresolved: Array = []
		var kinds: Dictionary = {}
		var moved: Array = []
		for i: int in anim.get_track_count():
			var path: NodePath = anim.track_get_path(i)
			var kind: String = str(anim.track_get_type(i))
			kinds[kind] = kinds.get(kind, 0) + 1
			if anim.track_get_type(i) == Animation.TYPE_POSITION_3D:
				moved.append(str(path.get_concatenated_subnames()))
			if not _resolves(anim_root, path):
				unresolved.append(str(path))
		anims[str(name)] = {
			"length": snappedf(anim.length, 0.00001),
			"loop_mode": anim.loop_mode,
			"tracks": anim.get_track_count(),
			"track_types": kinds,
			"position_tracks": moved,
			"unresolved": unresolved,
			"motion": _motion(player, skeleton, str(name), anim.length) if skeleton != null else {},
		}
	player.stop()
	return {
		"path": str(scene.get_path_to(player)),
		"root_node": str(player.root_node),
		"libraries": player.get_animation_library_list().map(func(n: StringName) -> String: return str(n)),
		"animations": anims,
	}


## A track resolves when its node exists under the player's root and, for a bone track, the bone exists.
func _resolves(anim_root: Node, path: NodePath) -> bool:
	if anim_root == null:
		return false
	var node: Node = anim_root.get_node_or_null(NodePath(path.get_concatenated_names()))
	if node == null:
		return false
	var sub: String = str(path.get_concatenated_subnames())
	if sub.is_empty():
		return true
	if node is Skeleton3D:
		return (node as Skeleton3D).find_bone(sub) >= 0
	return sub in node


## How far the bones move between the poses at 0, 1/3 and 2/3 of the length: the largest rotation (degrees) and
## translation (m) of any bone between any two samples, and the bone that moved most.
func _motion(player: AnimationPlayer, skeleton: Skeleton3D, name: String, length: float) -> Dictionary:
	var times: Array[float] = [0.0, length / 3.0, length * 2.0 / 3.0]
	var samples: Array = []
	for t: float in times:
		Character.pose_at(player, skeleton, name, t)
		var pose: Array = []
		for b: int in skeleton.get_bone_count():
			pose.append([skeleton.get_bone_pose_rotation(b), skeleton.get_bone_pose_position(b)])
		samples.append(pose)
	var max_deg: float = 0.0
	var max_m: float = 0.0
	var top: String = ""
	for a: int in samples.size():
		for c: int in range(a + 1, samples.size()):
			for b: int in skeleton.get_bone_count():
				var qa: Quaternion = samples[a][b][0]
				var qc: Quaternion = samples[c][b][0]
				var deg: float = rad_to_deg(qa.angle_to(qc))
				var dist: float = (samples[a][b][1] as Vector3).distance_to(samples[c][b][1])
				if deg > max_deg:
					max_deg = deg
					top = skeleton.get_bone_name(b)
				max_m = maxf(max_m, dist)
	return {"times": times, "max_rotation_deg": snappedf(max_deg, 0.001), "max_translation_m": snappedf(max_m, 0.00001),
			"most_moved_bone": top}


func _fail(why: String) -> void:
	print("INSPECT error ", why)
	quit(1)
