extends SceneTree
## Checks the alien skin's rest-pose channel (art #196, S9b), headless: loads the character scene, finds the skin (the
## surface with CUSTOM0) and prints REST <json>: whether CUSTOM0 is RGBA float, and its largest difference from the
## mesh's own rest VERTEX (xyz) and NORMAL.z (w - 2), which alien_hue.gdshader relies on. Arguments: -- <res://..glb>.


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var packed: PackedScene = load(args[0]) as PackedScene
	var out := {"skins": 0}
	if packed != null:
		var root_node: Node = packed.instantiate()
		for n: Node in root_node.find_children("*", "MeshInstance3D", true, false):
			var mesh: Mesh = (n as MeshInstance3D).mesh
			if mesh == null:
				continue
			for s: int in mesh.get_surface_count():
				var fmt: int = mesh.surface_get_format(s)
				if not fmt & Mesh.ARRAY_FORMAT_CUSTOM0:
					continue
				var cf: int = (fmt >> Mesh.ARRAY_FORMAT_CUSTOM0_SHIFT) & Mesh.ARRAY_FORMAT_CUSTOM_MASK
				var arr: Array = mesh.surface_get_arrays(s)
				var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
				var nr: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
				var c: PackedFloat32Array = arr[Mesh.ARRAY_CUSTOM0]
				var dp := 0.0
				var dn := 0.0
				for i: int in v.size():
					dp = maxf(dp, Vector3(c[4 * i], c[4 * i + 1], c[4 * i + 2]).distance_to(v[i]))
					dn = maxf(dn, absf(c[4 * i + 3] - 2.0 - nr[i].z))
				out["skins"] += 1
				out[n.name] = {"custom0_rgba_float": cf == Mesh.ARRAY_CUSTOM_RGBA_FLOAT, "vertices": v.size(),
					"max_pos_diff_m": dp, "max_normal_z_diff": dn}
		root_node.free()
	print("REST ", JSON.stringify(out))
	quit(0)
