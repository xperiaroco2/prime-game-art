extends SceneTree
## The House's bake review (#83, from #83a; `house --bake`): pictures of the baked zones in an off-screen window (labrun.py godot --window). Each row of the jobs file
## is one bake scene in one mode seen from
## the row's cameras; the tiles go into one sheet. Modes (#83b, house_bake.MODES): baked (its LightmapGI data);
## realtime (no lightmap, the lights dynamic, unshadowed as the light kit writes them); realtime_shadow (the same with
## shadows); hybrid (its lightmap, baked with lights=dynamic, and the lights dynamic with shadows); a mode ending in
## _nospec also sets light_specular 0 (diffuse only, what a lightmap holds). A row with `sheen` (#83c,
## house_bake.sheen_mode) is baked plus: lm_specular (LightmapGI.specular_intensity, a directional bake), probes (one
## ReflectionProbe per box of `probes`), n (the nearest n lights of `glow_types` as specular-only real-time lights on a
## black additive copy of the lightmapped meshes, render layer 2), shadow (those lights shadowed). Per shot: draw
## calls, the lights whose range reaches the camera, the real-time and shadowed lights on lightmapped meshes. The sheet
## tile of a row's first camera carries the row's label; the measured frame has none.
##   -s res://house/bake_shots.gd -- jobs=<abs json> out=<abs dir>  (an off-screen window; a headless Godot draws nothing)

const SHEEN_LAYER := 2  # render layer bit 2 (value 2): the overlay copies and the sheen lights' cull mask


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var a := {}
	for s in OS.get_cmdline_user_args():
		var kv := s.split("=", true, 1)
		a[kv[0]] = kv[1]
	var jobs: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(a["jobs"]))
	var out: String = a["out"]
	DirAccess.make_dir_recursive_absolute(out)
	var tw := int(jobs["tile"][0])
	var th := int(jobs["tile"][1])
	var rows: Array = jobs["rows"]
	var ncol := 0
	for r in rows:
		ncol = maxi(ncol, (r["cams"] as Array).size())
	var per := int(jobs.get("per_line", 1))  # rows side by side on one sheet line
	var lines := int(ceil(rows.size() / float(per)))
	var sheet := Image.create(tw * ncol * per, th * lines, false, Image.FORMAT_RGB8)
	var stats := []
	var tag_layer := CanvasLayer.new()
	var tag := Label.new()
	tag.position = Vector2(16, 8)
	tag.add_theme_font_size_override("font_size", 72)
	tag.add_theme_constant_override("outline_size", 12)
	tag.add_theme_color_override("font_outline_color", Color.BLACK)
	tag_layer.add_child(tag)
	tag_layer.visible = false
	root.add_child(tag_layer)
	for ri in rows.size():
		var row: Dictionary = rows[ri]
		var ps := load(row["scene"]) as PackedScene
		if ps == null:
			print("SHOTS missing ", row["scene"])
			continue
		var sc: Node3D = ps.instantiate()
		if row.has("scene2"):  # a second zone's bake beside the first: do separate bakes blend at the seam?
			var s2: Node3D = (load(row["scene2"]) as PackedScene).instantiate()
			s2.get_node("WorldEnvironment").free()
			sc.add_child(s2)
		var lm: LightmapGI = sc.get_node_or_null("LightmapGI")
		var lights: Array = sc.find_children("*", "Light3D", true, false)
		var mode: String = row["mode"]
		var sh: Dictionary = row.get("sheen", {})
		if mode.begins_with("realtime") and lm:
			lm.light_data = null
			lm.visible = false
		if mode != "baked" and sh.is_empty():
			for l: Light3D in lights:
				l.light_bake_mode = Light3D.BAKE_DYNAMIC
				l.shadow_enabled = mode != "realtime"
				if mode.ends_with("nospec"):
					l.light_specular = 0.0
		var spec_info := ""
		if not sh.is_empty():
			if lm and float(sh["lm_specular"]) > 0.0:
				if lm.get("specular_intensity") == null:
					spec_info = "no specular_intensity"
				lm.set("specular_intensity", float(sh["lm_specular"]))
			if sh["probes"]:
				for b: Dictionary in row["probes"]:
					var p := ReflectionProbe.new()
					p.name = "Probe_" + str(b["room"])
					p.position = Vector3(b["center"][0], b["center"][1], b["center"][2])
					p.size = Vector3(b["size"][0], b["size"][1], b["size"][2])
					p.update_mode = ReflectionProbe.UPDATE_ONCE
					p.interior = true
					p.box_projection = true
					p.ambient_mode = ReflectionProbe.AMBIENT_DISABLED
					p.cull_mask = 1  # the rooms, not the sheen overlay
					sc.add_child(p)
			if int(sh["n"]) > 0:
				_overlay(sc)
				for l: Light3D in lights:  # the baked lamps would light the copies (no lightmap) in real time
					l.light_cull_mask &= ~SHEEN_LAYER
		root.add_child(sc)
		var cam := Camera3D.new()
		cam.fov = 70
		sc.add_child(cam)
		cam.current = true
		for ci in (row["cams"] as Array).size():
			var c: Array = row["cams"][ci]
			cam.position = Vector3(c[0], c[1], c[2])
			cam.look_at(Vector3(c[3], c[4], c[5]))
			var added := []
			if int(sh.get("n", 0)) > 0:
				added = _sheen_lights(lights, cam.position, int(sh["n"]), bool(sh["shadow"]), row["glow_types"])
			for i in 16:
				await process_frame
			var img := root.get_texture().get_image()
			img.convert(Image.FORMAT_RGB8)
			img.save_png("%s/%s_%d.png" % [out, row["label"], ci])
			var draws := Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
			var near := 0
			for l: Light3D in lights:
				var rng: float = l.get("omni_range") if l is OmniLight3D else l.get("spot_range")
				if l.global_position.distance_to(cam.global_position) < rng:
					near += 1
			var rt := 0 if mode == "baked" else near
			var shadowed := 0 if mode in ["baked", "realtime"] else near
			if not sh.is_empty():
				rt = added.size()
				shadowed = added.size() if bool(sh["shadow"]) else 0
			if ci == 0:  # the sheet's tile carries the row's label; the measured frame above has none
				tag.text = str(row["label"]).trim_prefix(str(row.get("zone", "")) + "_")
				tag_layer.visible = true
				for i in 2:
					await process_frame
				img = root.get_texture().get_image()
				img.convert(Image.FORMAT_RGB8)
				tag_layer.visible = false
			for l in added:
				(l as Node).queue_free()
			img.resize(tw, th, Image.INTERPOLATE_LANCZOS)
			sheet.blit_rect(img, Rect2i(0, 0, tw, th), Vector2i(((ri % per) * ncol + ci) * tw, (ri / per) * th))
			stats.append({"row": row["label"], "cam": ci, "draw_calls": draws, "lights_reaching_camera": near,
				"rt_lights": rt, "shadowed": shadowed, "note": spec_info})
		root.remove_child(sc)
		sc.free()
	sheet.save_png(out + "/sheet.png")
	var f := FileAccess.open(out + "/shots.json", FileAccess.WRITE)
	f.store_string(JSON.stringify({"rows": rows.map(func(r): return r["label"]), "shots": stats}, " "))
	f.close()
	print("SHOTS ok ", stats.size())
	quit(0)


## A black, additive, ambient-free copy of every lightmapped mesh on SHEEN_LAYER: the sheen lights reach only these
## copies, so they add their specular and nothing else (black albedo: no diffuse; no ambient: the lightmap and the
## probes are not added twice). The lightmapped originals stay on layer 1, outside the sheen lights' cull mask.
func _overlay(sc: Node3D) -> void:
	var mats := {}
	for mi: MeshInstance3D in sc.get_node("Meshes").get_children():
		if mi.gi_mode != GeometryInstance3D.GI_MODE_STATIC or mi.mesh == null:
			continue
		var o := MeshInstance3D.new()
		o.mesh = mi.mesh
		o.transform = mi.transform
		o.layers = SHEEN_LAYER
		o.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		o.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
		for s in mi.mesh.get_surface_count():
			var m: Material = mi.get_surface_override_material(s)
			if m == null:
				m = mi.mesh.surface_get_material(s)
			if not mats.has(m):
				mats[m] = _sheen_material(m)
			o.set_surface_override_material(s, mats[m])
		sc.get_node("Meshes").add_child(o)


func _sheen_material(m: Material) -> Material:
	var s: BaseMaterial3D
	if m is BaseMaterial3D:
		s = (m as BaseMaterial3D).duplicate()
	else:
		s = StandardMaterial3D.new()
		s.roughness = 0.6
	s.albedo_color = Color.BLACK
	s.albedo_texture = null
	s.metallic = 0.0
	s.emission_enabled = false
	s.next_pass = null
	s.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
	s.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	s.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	s.disable_ambient_light = true
	s.disable_fog = true
	return s


## The nearest n lights of the glow types to `at` as real-time copies (bake mode Disabled, cull mask SHEEN_LAYER,
## the lamp's own energy, range and light_specular), shadowed or not; returns them.
func _sheen_lights(lights: Array, at: Vector3, n: int, shadow: bool, types: Array) -> Array:
	var cand := []
	for l: Light3D in lights:
		for t in types:
			if ("_%s_" % t) in str(l.name):
				cand.append(l)
				break
	cand.sort_custom(func(p, q): return p.global_position.distance_to(at) < q.global_position.distance_to(at))
	var out := []
	for l: Light3D in cand.slice(0, n):
		var d: Light3D = l.duplicate()
		d.light_bake_mode = Light3D.BAKE_DISABLED
		d.light_cull_mask = SHEEN_LAYER
		d.shadow_enabled = shadow
		l.get_parent().add_child(d)
		out.append(d)
	return out
