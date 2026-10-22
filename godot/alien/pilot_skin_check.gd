extends SceneTree
## The pilot character's rest skinning check (art #196, step 2b-3), headless: loads the imported GLB, lets the tree run
## a few frames (any AnimationPlayer, RESET or modifier applies), then skins every MeshInstance3D's vertices on the CPU
## the way the GPU does (the skin's bind poses, the skeleton's current global poses, ARRAY_BONES and ARRAY_WEIGHTS) and
## prints SKIN <json>: per mesh the largest vertex move from its bind shape and the bones behind the worst vertices,
## and the bones whose current pose differs from their rest. A clean import moves nothing at rest.
## Arguments: -- <res://..glb>

var model: Node


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var packed: PackedScene = load(OS.get_cmdline_user_args()[0]) as PackedScene
	model = packed.instantiate()
	root.add_child(model)
	for _i: int in 4:
		await process_frame
	var skel: Skeleton3D = model.find_children("*", "Skeleton3D", true, false)[0]
	var out := {"posed_bones": [], "meshes": {}}
	for b: int in skel.get_bone_count():
		var d := skel.get_bone_pose(b).origin.distance_to(skel.get_bone_rest(b).origin)
		var q := skel.get_bone_pose(b).basis.get_rotation_quaternion().angle_to(
				skel.get_bone_rest(b).basis.get_rotation_quaternion())
		if d > 1e-4 or q > 1e-3:
			out["posed_bones"].append([skel.get_bone_name(b), snappedf(d, 1e-4), snappedf(rad_to_deg(q), 0.01)])
	for mi: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		if mi.mesh == null or mi.skin == null:
			continue
		var skin: Skin = mi.skin
		var mats: Array[Transform3D] = []
		var names := PackedStringArray()
		for i: int in skin.get_bind_count():
			var bone := skin.get_bind_bone(i)
			if bone < 0:
				bone = skel.find_bone(skin.get_bind_name(i))
			names.append(skel.get_bone_name(bone))
			mats.append(skel.get_bone_global_pose(bone) * skin.get_bind_pose(i))
		var worst := 0.0
		var culprits := {}
		for s: int in mi.mesh.get_surface_count():
			var arr: Array = mi.mesh.surface_get_arrays(s)
			var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			var bones: PackedInt32Array = arr[Mesh.ARRAY_BONES]
			var w: PackedFloat32Array = arr[Mesh.ARRAY_WEIGHTS]
			var n := bones.size() / maxi(v.size(), 1)
			for k: int in v.size():
				var p := Vector3.ZERO
				var top := 0
				for c: int in n:
					var wt := w[k * n + c]
					if wt > 0.0:
						p += (mats[bones[k * n + c]] * v[k]) * wt
						if wt > w[k * n + top]:
							top = c
				var dist := p.distance_to(v[k])
				worst = maxf(worst, dist)
				if dist > 0.002:
					var nm: String = names[bones[k * n + top]]
					culprits[nm] = maxf(culprits.get(nm, 0.0), dist)
		out["meshes"][String(mi.name)] = {"max_move_m": snappedf(worst, 1e-5), "binds": skin.get_bind_count(),
			"bad_bones": culprits}
	print("SKIN ", JSON.stringify(out))
	quit(0)
