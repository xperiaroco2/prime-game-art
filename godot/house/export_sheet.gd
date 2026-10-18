extends SceneTree
## The House export's review sheet (art #119, docs/house.md "The export"): runs in an off-screen window (a headless
## Godot draws nothing) inside the export folder, opened as its own Godot project. Loads each named room scene from
## the package as the game would and shoots it from two eye-height cameras: from the middle of its front side
## (z = 0) along its depth, and from the middle of its left side (x = 0) across its width. Only the room's own lights
## and a dim review ambient light it; the tiles go into one sheet.
##   -s res://_check/export_sheet.gd -- rooms=<res:// folder> names=kitchen,storage,attic out=<abs dir> tile=640x360

const Offscreen = preload("res://lib/offscreen.gd")
const EYE := 1.5
const INSET := 0.4


func _initialize() -> void:
	var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
	if placed != "":
		printerr("OFFSCREEN error ", placed)
		quit(1)
		return
	_run.call_deferred()


func _run() -> void:
	var a := {}
	for s in OS.get_cmdline_user_args():
		var kv := s.split("=", true, 1)
		a[kv[0]] = kv[1]
	var names: PackedStringArray = String(a["names"]).split(",")
	var out: String = a["out"]
	var t: PackedStringArray = String(a.get("tile", "640x360")).split("x")
	var tw := int(t[0])
	var th := int(t[1])
	DirAccess.make_dir_recursive_absolute(out)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.05, 0.05, 0.07)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color(0.75, 0.75, 0.8)
	env.environment.ambient_light_energy = 0.45
	env.environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	root.add_child(env)
	var sheet := Image.create(tw * 2, th * names.size(), false, Image.FORMAT_RGB8)
	var stats := []
	for ri in names.size():
		var path: String = String(a["rooms"]).path_join(names[ri] + ".tscn")
		var ps := load(path) as PackedScene
		if ps == null:
			print("SHEET missing ", path)
			quit(1)
			return
		var sc: Node3D = ps.instantiate()
		root.add_child(sc)
		var size: Vector2i = sc.get_meta("size_m")
		var w := float(size.x)
		var d := float(size.y)
		var cams := [[Vector3(w / 2, EYE, INSET), Vector3(w / 2, 0.9, d - INSET)],
			[Vector3(INSET, EYE, d / 2), Vector3(w - INSET, 0.9, d / 2)]]
		var cam := Camera3D.new()
		cam.fov = 75
		sc.add_child(cam)
		cam.current = true
		for ci in cams.size():
			cam.position = cams[ci][0]
			cam.look_at(cams[ci][1])
			for i in 16:
				await process_frame
			var img := root.get_texture().get_image()
			img.convert(Image.FORMAT_RGB8)
			img.save_png("%s/%s_%d.png" % [out, names[ri], ci])
			stats.append({"room": names[ri], "cam": ci, "root": String(sc.name), "size_m": [size.x, size.y],
				"draw_calls": Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
				"lights": sc.find_children("*", "Light3D", true, false).size()})
			img.resize(tw, th, Image.INTERPOLATE_LANCZOS)
			sheet.blit_rect(img, Rect2i(0, 0, tw, th), Vector2i(ci * tw, ri * th))
		root.remove_child(sc)
		sc.free()
	sheet.save_png(out + "/sheet.png")
	var f := FileAccess.open(out + "/sheet.json", FileAccess.WRITE)
	f.store_string(JSON.stringify({"shots": stats}, " "))
	f.close()
	print("SHEET ok ", stats.size())
	quit(0)
