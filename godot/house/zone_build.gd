extends SceneTree
## The House's zone bake scene (#83, from #83a's spike; docs/house.md "Light"), run by `house --bake`: from
## res://import/house/zones/<zone>.tscn (the `house` command's output) every kit and prop mesh flattened under one root
## with gi_mode Static and a lightmap_size_hint of texel / uv2_per_m (the kit's UV2 density, uv2=<json>; props: their
## imported UV2 scaled from 5 texels/m), meshes without UV2 Dynamic (lit by the probes), the zone's lights, a
## LightmapGI with bake=<json>'s settings and a night WorldEnvironment; saved as res://import/house/bake/<zone>_<tag>.scn.
## The level above (group Above, the zone's ceiling slabs) stays in the bake as occluders at a tenth of the texels.
## #83: the Above pieces that are floors (floor_*, ceiling_*) bake at the full texel (they are the zone's
## ceiling; at a tenth they gave one texel per tile: per-tile seams and no lamp pools); above=0.1 keeps #83a's rule.
## Overrides of bake.json: denoiser=0|1 energy=<f>; merge=1 welds each room level's floor tiles into one mesh and
## unwraps it (lightmap_unwrap) so the floor has one lightmap island instead of one per tile and face.
##   godot --headless --path godot -s res://house/zone_build.gd -- zone=ground tag=high texel=12 uv2=<abs> bake=<abs>

func _piece(n: Node) -> String:
	while n != null:
		if n.scene_file_path.begins_with("res://import/kit_") or n.scene_file_path.begins_with("res://import/prop_"):
			return n.scene_file_path.get_file().get_basename()
		n = n.get_parent()
	return ""


func _initialize() -> void:
	var a := {}
	for s in OS.get_cmdline_user_args():
		var kv := s.split("=", true, 1)
		a[kv[0]] = kv[1] if kv.size() > 1 else ""
	var zone: String = a["zone"]
	var texel := float(a["texel"])
	var tag: String = a["tag"]
	var uv2: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(a["uv2"]))
	var bake: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(a["bake"]))
	if a.has("denoiser"):
		bake["denoiser"] = a["denoiser"] == "1"
	if a.has("energy"):
		bake["bounce_indirect_energy"] = float(a["energy"])
	var above_k := float(a.get("above", "1.0"))
	var merge: bool = a.get("merge", "0") == "1"
	var groups := {}
	var src: Node3D = (load("res://import/house/zones/%s.tscn" % zone) as PackedScene).instantiate()
	root.add_child(src)
	var out := Node3D.new()
	out.name = "ZoneBake_" + zone
	var meshes := Node3D.new()
	meshes.name = "Meshes"
	out.add_child(meshes)
	meshes.owner = out
	var cache := {}
	var stats := {"zone": zone, "tag": tag, "texel_per_m": texel, "meshes": 0, "above": 0, "texels": 0, "no_uv2": [],
		"dynamic": 0, "merged": 0, "bake": bake, "above_k": above_k}
	var k := 0
	var box := AABB()
	for mi: MeshInstance3D in src.find_children("*", "MeshInstance3D", true, false):
		if mi.mesh == null:
			continue
		var pid := _piece(mi)
		var above := str(src.get_path_to(mi)).begins_with("Above")
		var flat := pid.begins_with("kit_floor_") or pid.begins_with("kit_ceiling_") or pid == "kit_cover"
		var k_texel := 1.0  # the zone's own pieces at the full texel; Above: floors at above_k, the rest at a tenth
		if above:
			k_texel = above_k if flat else 0.1
		var xf := _xf(mi, src)
		if merge and flat and not above and pid.begins_with("kit_floor_"):
			var gk := "%s|%.2f" % [pid.get_slice("_", 2), xf.origin.y]
			if not groups.has(gk):
				groups[gk] = []
			groups[gk].append([mi.mesh, xf])
			continue
		var key := pid + "|%.2f" % k_texel
		var hint := 0
		if not cache.has(key):
			var m: ArrayMesh = mi.mesh.duplicate()
			if pid.begins_with("kit_"):
				var per := float(uv2.get(pid.substr(4), 0.25))
				if not uv2.has(pid.substr(4)) and pid not in stats["no_uv2"]:
					stats["no_uv2"].append(pid)
				hint = maxi(4, int(ceil(texel * k_texel / per)))
			else:  # a prop: UV2 from the import (light_baking=2, lightmap_texel_size 0.2 m = 5 texels/m)
				hint = maxi(4, int(ceil(m.lightmap_size_hint.x * texel / 5.0)))
			m.lightmap_size_hint = Vector2i(hint, hint)
			cache[key] = m
		var mesh: ArrayMesh = cache[key]
		var has_uv2 := (mesh.surface_get_format(0) & Mesh.ARRAY_FORMAT_TEX_UV2) != 0
		hint = mesh.lightmap_size_hint.x
		var n := MeshInstance3D.new()
		n.mesh = mesh
		n.transform = xf
		box = n.transform * mesh.get_aabb() if stats["meshes"] == 0 else box.merge(n.transform * mesh.get_aabb())
		n.gi_mode = GeometryInstance3D.GI_MODE_STATIC if has_uv2 else GeometryInstance3D.GI_MODE_DYNAMIC
		stats["dynamic"] += 0 if has_uv2 else 1
		n.name = "%s_%d" % [pid, k]
		k += 1
		meshes.add_child(n)
		n.owner = out
		stats["meshes"] += 1
		stats["above"] += 1 if above else 0
		stats["texels"] += hint * hint if has_uv2 else 0
	for gk in groups:
		var mm := _merged(groups[gk], texel)
		if mm == null:
			stats["merge_failed"] = gk
			continue
		var n := MeshInstance3D.new()
		n.mesh = mm
		n.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		n.name = "merged_%d" % k
		k += 1
		meshes.add_child(n)
		n.owner = out
		stats["merged"] += (groups[gk] as Array).size()
		stats["texels"] += mm.lightmap_size_hint.x * mm.lightmap_size_hint.y
	var lights := Node3D.new()
	lights.name = "Lights"
	out.add_child(lights)
	lights.owner = out
	var nl := 0
	for l: Light3D in src.find_children("*", "Light3D", true, false):
		var c: Light3D = l.duplicate()
		c.transform = _xf(l, src)
		lights.add_child(c)
		c.owner = out
		nl += 1
	stats["lights"] = nl
	stats["box"] = [box.position.x, box.position.y, box.position.z, box.size.x, box.size.y, box.size.z]
	var lm := LightmapGI.new()
	lm.name = "LightmapGI"
	lm.quality = {"low": 0, "medium": 1, "high": 2, "ultra": 3}[bake["quality"]]
	lm.bounces = int(bake["bounces"])
	lm.bounce_indirect_energy = float(bake["bounce_indirect_energy"])
	lm.use_denoiser = bool(bake["denoiser"])
	lm.directional = bool(bake["directional"])
	lm.interior = bool(bake["interior"])
	lm.environment_mode = LightmapGI.ENVIRONMENT_MODE_DISABLED
	out.add_child(lm)
	lm.owner = out
	var we := WorldEnvironment.new()
	we.name = "WorldEnvironment"
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.02, 0.03, 0.06)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.0, 0.0, 0.0)
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 1.3
	we.environment = env
	out.add_child(we)
	we.owner = out
	DirAccess.make_dir_recursive_absolute("res://import/house/bake")
	var ps := PackedScene.new()
	ps.pack(out)
	var path := "res://import/house/bake/%s_%s.scn" % [zone, tag]
	var err := ResourceSaver.save(ps, path)
	stats["saved"] = path
	stats["err"] = err
	var f := FileAccess.open("res://import/house/bake/%s_%s_build.json" % [zone, tag], FileAccess.WRITE)
	f.store_string(JSON.stringify(stats, " "))
	f.close()
	print("ZONEBUILD ", JSON.stringify(stats))
	quit(0 if err == OK else 1)


## The node's transform relative to top, from the local transforms (global_transform in _initialize gave identity).
func _xf(n: Node, top: Node) -> Transform3D:
	var t := Transform3D()
	while n != null and n != top:
		if n is Node3D:
			t = (n as Node3D).transform * t
		n = n.get_parent()
	return t


## The tiles of one floor kind at one height as one mesh: per surface (material) appended with their transforms, UV0
## replaced by the world plane (the kit's UV0 is a box projection in metres, so the look stays), welded, unwrapped.
func _merged(items: Array, texel: float) -> ArrayMesh:
	var out := ArrayMesh.new()
	var mats := {}
	for it in items:
		var m: Mesh = it[0]
		for s in m.get_surface_count():
			var mat := m.surface_get_material(s)
			if not mats.has(mat):
				mats[mat] = SurfaceTool.new()
				(mats[mat] as SurfaceTool).begin(Mesh.PRIMITIVE_TRIANGLES)
			(mats[mat] as SurfaceTool).append_from(m, s, it[1])
	for mat in mats:
		var arr: Array = (mats[mat] as SurfaceTool).commit_to_arrays()
		var pos: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var nor: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
		var uv := PackedVector2Array()
		uv.resize(pos.size())
		for i in pos.size():
			var nn := nor[i].abs()
			uv[i] = Vector2(pos[i].x, pos[i].z) if nn.y >= nn.x and nn.y >= nn.z else (
				Vector2(pos[i].z, pos[i].y) if nn.x >= nn.z else Vector2(pos[i].x, pos[i].y))
		arr[Mesh.ARRAY_TEX_UV] = uv
		arr[Mesh.ARRAY_TEX_UV2] = null
		var st := SurfaceTool.new()
		st.create_from_arrays(arr)
		st.index()
		st.commit(out)
		out.surface_set_material(out.get_surface_count() - 1, mat)
	if out.lightmap_unwrap(Transform3D.IDENTITY, 1.0 / texel) != OK:
		return null
	return out
