extends SceneTree
## The House's bake review (#83, from #83a; `house --bake`): pictures of the baked zones in an off-screen window (labrun.py godot --window). Each row of the jobs file
## is one bake scene in one mode (baked: its LightmapGI data; realtime: no lightmap, the lights dynamic) seen from
## the row's cameras; the tiles go into one sheet. Per shot: draw calls and the lights whose range reaches the camera.
##   -s res://house/bake_shots.gd -- jobs=<abs json> out=<abs dir>  (an off-screen window; a headless Godot draws nothing)

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
		if row["mode"] == "realtime":
			if lm:
				lm.light_data = null
				lm.visible = false
			for l: Light3D in lights:
				l.light_bake_mode = Light3D.BAKE_DYNAMIC
		root.add_child(sc)
		var cam := Camera3D.new()
		cam.fov = 70
		sc.add_child(cam)
		cam.current = true
		for ci in (row["cams"] as Array).size():
			var c: Array = row["cams"][ci]
			cam.position = Vector3(c[0], c[1], c[2])
			cam.look_at(Vector3(c[3], c[4], c[5]))
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
			img.resize(tw, th, Image.INTERPOLATE_LANCZOS)
			sheet.blit_rect(img, Rect2i(0, 0, tw, th), Vector2i(((ri % per) * ncol + ci) * tw, (ri / per) * th))
			stats.append({"row": row["label"], "cam": ci, "draw_calls": draws, "lights_reaching_camera": near})
		root.remove_child(sc)
		sc.free()
	sheet.save_png(out + "/sheet.png")
	var f := FileAccess.open(out + "/shots.json", FileAccess.WRITE)
	f.store_string(JSON.stringify({"rows": rows.map(func(r): return r["label"]), "shots": stats}, " "))
	f.close()
	print("SHOTS ok ", stats.size())
	quit(0)
