extends RefCounted
## Helpers shared by check/inspect.gd and frames/frames.gd (docs/godot.md): the nodes of an imported character, its
## skinned vertices as Godot itself deforms them, and JSON output. Loaded with preload(), not a class_name, so that a
## script run with -s works without the editor's global class cache.

const AXIS_LEVER: float = 0.1


## Instantiates the PackedScene at path under parent; null when it does not load.
static func instance(path: String, parent: Node) -> Node:
	var scene: PackedScene = load(path) as PackedScene
	if scene == null:
		return null
	var node: Node = scene.instantiate()
	parent.add_child(node)
	return node


static func nodes_of(root: Node, cls: String) -> Array[Node]:
	return root.find_children("*", cls, true, false)


## Every MeshInstance3D under root, sorted by name.
static func meshes(root: Node) -> Array[MeshInstance3D]:
	var out: Array[MeshInstance3D] = []
	for node: Node in nodes_of(root, "MeshInstance3D"):
		out.append(node as MeshInstance3D)
	out.sort_custom(func(a: MeshInstance3D, b: MeshInstance3D) -> bool: return a.name < b.name)
	return out


## The world positions of mesh's vertices in the skeleton's current pose, every stride-th vertex: linear blend
## skinning as Godot's renderer does it (bone global pose times the skin's bind pose, weighted). Computed on the CPU
## because MeshInstance3D.bake_mesh_from_current_skeleton_pose() needs a rendering server that keeps skeletons, which
## a headless Godot does not ("The source mesh must have a valid skin").
static func skinned_points(mesh: MeshInstance3D, stride: int = 1) -> PackedVector3Array:
	var out: PackedVector3Array = PackedVector3Array()
	if mesh.mesh == null:
		return out
	var skin: Skin = mesh.skin
	var skeleton: Skeleton3D = mesh.get_node_or_null(mesh.skeleton) as Skeleton3D if not mesh.skeleton.is_empty() else null
	var xf: Transform3D = mesh.global_transform
	var binds: Array[Transform3D] = []
	if skin != null and skeleton != null:
		skeleton.force_update_all_bone_transforms()
		# Godot renders a skinned mesh with its own transform on top of the skin's (skeleton-relative) transforms.
		var to_mesh: Transform3D = mesh.global_transform.affine_inverse() * skeleton.global_transform
		for j: int in skin.get_bind_count():
			var bind_name: StringName = skin.get_bind_name(j)
			var bone: int = skeleton.find_bone(bind_name) if not str(bind_name).is_empty() else skin.get_bind_bone(j)
			binds.append(to_mesh * skeleton.get_bone_global_pose(bone) * skin.get_bind_pose(j) if bone >= 0 else Transform3D())
	for s: int in mesh.mesh.get_surface_count():
		var arrays: Array = mesh.mesh.surface_get_arrays(s)
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES] if arrays[Mesh.ARRAY_BONES] != null else PackedInt32Array()
		var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS] if arrays[Mesh.ARRAY_WEIGHTS] != null else PackedFloat32Array()
		var per: int = bones.size() / verts.size() if not binds.is_empty() and verts.size() > 0 else 0
		for i: int in range(0, verts.size(), stride):
			var v: Vector3 = verts[i]
			if per == 0:
				out.append(xf * v)
				continue
			var p: Vector3 = Vector3.ZERO
			for k: int in per:
				var w: float = weights[i * per + k]
				if w > 0.0:
					p += (binds[bones[i * per + k]] * v) * w
			out.append(xf * p)
	return out


## The name of the bone with the largest skin weight at each of mesh's vertices, in skinned_points(mesh)'s order; ""
## for a vertex without weights; empty when the mesh has no skin bound to a skeleton.
static func dominant_bones(mesh: MeshInstance3D) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	var skin: Skin = mesh.skin
	var skeleton: Skeleton3D = mesh.get_node_or_null(mesh.skeleton) as Skeleton3D if not mesh.skeleton.is_empty() else null
	if mesh.mesh == null or skin == null or skeleton == null:
		return out
	var names: PackedStringArray = PackedStringArray()
	for j: int in skin.get_bind_count():
		var bind_name: StringName = skin.get_bind_name(j)
		var bone: int = skeleton.find_bone(bind_name) if not str(bind_name).is_empty() else skin.get_bind_bone(j)
		names.append(skeleton.get_bone_name(bone) if bone >= 0 and bone < skeleton.get_bone_count() else "")
	for s: int in mesh.mesh.get_surface_count():
		var arrays: Array = mesh.mesh.surface_get_arrays(s)
		var count: int = (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()
		var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES] if arrays[Mesh.ARRAY_BONES] != null else PackedInt32Array()
		var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS] if arrays[Mesh.ARRAY_WEIGHTS] != null else PackedFloat32Array()
		var per: int = bones.size() / count if count > 0 else 0
		for i: int in count:
			var best: String = ""
			var most: float = 0.0
			for k: int in per:
				var w: float = weights[i * per + k]
				var b: int = bones[i * per + k]
				if w > most and b >= 0 and b < names.size():
					most = w
					best = names[b]
			out.append(best)
	return out


## Per bone, the bounds of mesh's skinned rest points whose largest weight is that bone's: {"<bone>": {"min", "max"}}.
## godot-check's facing_plus_z measures a barefoot body's feet with it (the foot and toe bones' skin).
static func bone_bounds(mesh: MeshInstance3D) -> Dictionary:
	var owners: PackedStringArray = dominant_bones(mesh)
	var points: PackedVector3Array = skinned_points(mesh)
	var lows: Dictionary = {}
	var highs: Dictionary = {}
	if owners.size() != points.size():
		return {}
	for i: int in points.size():
		var bone: String = owners[i]
		if bone.is_empty():
			continue
		if lows.has(bone):
			lows[bone] = (lows[bone] as Vector3).min(points[i])
			highs[bone] = (highs[bone] as Vector3).max(points[i])
		else:
			lows[bone] = points[i]
			highs[bone] = points[i]
	var out: Dictionary = {}
	for bone: String in lows:
		out[bone] = {"min": vec(lows[bone]), "max": vec(highs[bone])}
	return out


## {"min": [x, y, z], "max": [x, y, z]} of points; empty when there are none.
static func bounds(points: PackedVector3Array) -> Dictionary:
	if points.is_empty():
		return {}
	var lo: Vector3 = points[0]
	var hi: Vector3 = points[0]
	for p: Vector3 in points:
		lo = lo.min(p)
		hi = hi.max(p)
	return {"min": vec(lo), "max": vec(hi)}


static func vec(v: Vector3) -> Array:
	return [snappedf(v.x, 0.00001), snappedf(v.y, 0.00001), snappedf(v.z, 0.00001)]


## Every bone's world position (its joint) in the skeleton's current pose.
static func joints(skeleton: Skeleton3D) -> Dictionary:
	skeleton.force_update_all_bone_transforms()
	var out: Dictionary = {}
	for i: int in skeleton.get_bone_count():
		out[skeleton.get_bone_name(i)] = vec(skeleton.global_transform * skeleton.get_bone_global_pose(i).origin)
	return out


## Two points per bone, AXIS_LEVER from its joint along world +X and +Y in the rest pose, carried by the bone's pose
## ("<bone>+x", "<bone>+y"): they turn with the bone, so a comparison sees the rotation of a bone no other joint
## shows (Head, Foot, the fingertips). Blender computes the same points (tools/blender/compare_frames.py).
static func axis_points(skeleton: Skeleton3D, lever: float = AXIS_LEVER) -> Dictionary:
	skeleton.force_update_all_bone_transforms()
	var to_world: Transform3D = skeleton.global_transform
	var to_skeleton: Transform3D = to_world.affine_inverse()
	var out: Dictionary = {}
	for i: int in skeleton.get_bone_count():
		var rest: Transform3D = skeleton.get_bone_global_rest(i)
		var moved: Transform3D = skeleton.get_bone_global_pose(i) * rest.affine_inverse()
		var head: Vector3 = to_world * rest.origin
		for axis: String in ["x", "y"]:
			var offset: Vector3 = Vector3(lever, 0, 0) if axis == "x" else Vector3(0, lever, 0)
			out["%s+%s" % [skeleton.get_bone_name(i), axis]] = vec(to_world * (moved * (to_skeleton * (head + offset))))
	return out


## Plays animation name on player at time seconds and applies it at once.
static func pose_at(player: AnimationPlayer, skeleton: Skeleton3D, name: String, seconds: float) -> void:
	if player.current_animation != name:
		player.play(name)
		player.pause()
	player.seek(seconds, true)
	skeleton.force_update_all_bone_transforms()


static func write_json(path: String, data: Variant) -> bool:
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(JSON.stringify(data, " "))
	file.close()
	return true


static func read_json(path: String) -> Variant:
	if path.is_empty() or not FileAccess.file_exists(path):
		return {}
	return JSON.parse_string(FileAccess.get_file_as_string(path))
