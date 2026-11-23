extends SceneTree
## The mug package's check, headless (tools/blender/mug_lab_package.py --check): loads the package folder as the game
## would (its GLB and its own mug_look.gd, which preloads the shaders beside it), puts the look on, and checks:
## - the nodes the contract names: Mug (mesh), Beer (holding Liquid and Foam), Grip (a node with +Y up the handle
##   and -Z toward the mug's axis);
## - the glass's baked map reached the look (baked = 1);
## - set_fill(1, 0.5, 0): Beer shown, shown, hidden; the foam's crown 1 full, 0 at half;
## - the triangles per mesh, the bounds, the Grip's place.
## Prints one line "PKGCHECK <json>" and quits 0 when every check holds, 1 otherwise.
## Args after "--": <res:// package folder>

func _initialize() -> void:
	var dir: String = OS.get_cmdline_user_args()[0]
	var out := {"problems": []}
	var scene: PackedScene = load(dir.path_join("mug.glb"))
	var look_script: Script = load(dir.path_join("mug_look.gd"))
	if scene == null or look_script == null:
		print("PKGCHECK " + JSON.stringify({"problems": ["cannot load mug.glb or mug_look.gd from %s" % dir]}))
		quit(1)
		return
	var model: Node3D = scene.instantiate()
	root.add_child(model)
	var tris := {}
	for name: String in ["Mug", "Liquid", "Foam"]:
		var mi := model.find_child(name, true, false) as MeshInstance3D
		if mi == null:
			out["problems"].append("no mesh %s" % name)
			continue
		var n := 0
		for s: int in mi.mesh.get_surface_count():
			var arr: Array = mi.mesh.surface_get_arrays(s)
			var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
			n += idx.size() / 3 if idx.size() > 0 else (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
		tris[name] = n
	out["triangles"] = tris
	out["triangles_total"] = tris.values().reduce(func(a, b): return a + b, 0)
	var beer := model.find_child("Beer", true, false) as Node3D
	if beer == null or beer.find_child("Liquid", true, false) == null or beer.find_child("Foam", true, false) == null:
		out["problems"].append("Beer must hold Liquid and Foam")
	var grip := model.find_child("Grip", true, false) as Node3D
	if grip == null:
		out["problems"].append("no Grip")
	else:
		var g: Transform3D = grip.transform   # its parent is the scene root (global transforms are not ready in _initialize)
		out["grip_cm"] = [snappedf(g.origin.x * 100, 0.01), snappedf(g.origin.y * 100, 0.01), snappedf(g.origin.z * 100, 0.01)]
		out["grip_up"] = [snappedf(g.basis.y.x, 0.001), snappedf(g.basis.y.y, 0.001), snappedf(g.basis.y.z, 0.001)]
		out["grip_minus_z"] = [snappedf(-g.basis.z.x, 0.001), snappedf(-g.basis.z.y, 0.001), snappedf(-g.basis.z.z, 0.001)]
		if g.basis.y.y < 0.99:
			out["problems"].append("Grip +Y is not up the handle")
		if -g.basis.z.x > -0.99:
			out["problems"].append("Grip -Z does not point toward the mug's axis (-x)")
	var look: Dictionary = look_script.apply(model, {"floor": 2.2, "full": 12.6, "rim": 15.0, "inner_r": 3.62,
			"rim_r": 4.5, "head_top": 18.2})
	out["baked"] = look.get("baked", false)   # the approved look (round 14) is the unbaked one: reported, not required
	var states := {}
	for f: float in [1.0, 0.5, 0.0]:
		look_script.set_fill(look, f)
		var fm: ShaderMaterial = look["foam_mat"]
		states[str(f)] = {"beer_visible": beer.visible, "crown": fm.get_shader_parameter("crown")}
	out["states"] = states
	if not (states["1.0"]["beer_visible"] and states["0.5"]["beer_visible"] and not states["0.0"]["beer_visible"]):
		out["problems"].append("Beer must show at 1 and 0.5 and hide at 0")
	if float(states["1.0"]["crown"]) < 0.99 or float(states["0.5"]["crown"]) > 0.01:
		out["problems"].append("the foam's crown must be 1 full and 0 at half")
	var box := AABB()
	var first := true
	for mi: Node in model.find_children("*", "MeshInstance3D", true, false):
		if mi.name == "Foam":
			continue   # its mesh is a canonical unit; the shader places it
		var b: AABB = (mi as MeshInstance3D).global_transform * (mi as MeshInstance3D).get_aabb()
		box = b if first else box.merge(b)
		first = false
	out["bounds_cm"] = {"min": [snappedf(box.position.x * 100, 0.01), snappedf(box.position.y * 100, 0.01), snappedf(box.position.z * 100, 0.01)],
			"max": [snappedf(box.end.x * 100, 0.01), snappedf(box.end.y * 100, 0.01), snappedf(box.end.z * 100, 0.01)]}
	print("PKGCHECK " + JSON.stringify(out))
	quit(0 if (out["problems"] as Array).is_empty() else 1)
