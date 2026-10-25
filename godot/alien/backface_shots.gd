extends "res://alien/char_shots.gd"
## The back-face test (art #196, R2): any line of sight into the hollow head shows. Every mesh of the character is
## drawn unshaded with culling off: front faces grey (lit by their view-space normal), the head mesh's back faces flat
## red, every other mesh's back faces orange, the background pure blue. The head mesh is closed (no open edges), so a
## gap between a lid and its eyeball, or a fold, shows red, never daylight. Per head, gazes rest, up, down, left, right
## (eye_mode "free", the head held) and "lead" (eye_mode lead, the head following a 40 degree turn, 8 frames in) and "jog" (Jog_Fwd under the controller, its
## springs and skin, 10 frames in), each
## from the front, both three-quarters, both sides, 25 degrees above and below, framed on the eyes at FRAME_H and
## on each eye at EYE_H; the red (and orange) pixels counted in the three full 1280x720 frames. tools/blender/alien_clip_run.py --backface writes
## the job (clip_reels.gd's).
## backface_<head>.jpg: the cells (rows the gazes, columns the views; a yellow frame where red shows, the count under
## each cell); <head>_4x/<gaze>_<view>.png: 4x (nearest) round the red pixels' middle where red shows;
## backface.json: per head, gaze and view {"red", "orange"} (and the red middle "cx", "cy" in pixels).
## Args after "--": <job.json>

const BF_CELL := Vector2i(180, 180)
const FRAME_H := 0.42  # m: the cells' framing, the whole head round the eyes' middle
const EYE_H := 0.14  # m: the counting close-ups, each eye (the rim shots' height): a one-pixel sliver at the head's framing shows here
## views: (name, yaw degrees toward the head's left, pitch degrees from above)
const VIEWS := [["front", 0.0, 0.0], ["q_left", 45.0, 0.0], ["left", 90.0, 0.0], ["q_right", -45.0, 0.0],
	["right", -90.0, 0.0], ["above", 0.0, 25.0], ["below", 0.0, -25.0]]
const BF_GAZES := [["rest", Vector3(0.0, 0.0, 3.0)], ["up", Vector3(0.0, 2.5, 2.0)], ["down", Vector3(0.0, -2.5, 2.0)],
	["left", Vector3(3.0, 0.0, 2.0)], ["right", Vector3(-3.0, 0.0, 2.0)], ["lead", Vector3(0.0, 0.0, 0.0)], ["jog", Vector3(0.0, 0.0, 0.0)]]
const BF_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled;
uniform vec3 back_colour = vec3(1.0, 0.0, 0.0);
void fragment() {
	if (FRONT_FACING) {
		ALBEDO = vec3(0.25 + 0.5 * clamp(NORMAL.z, 0.0, 1.0));
	} else {
		ALBEDO = back_colour;
	}
}
"""

var _label: Label


func _run() -> void:
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	var out: String = job["sheet_out"]
	_stage(job["hdri"])
	_env.background_mode = Environment.BG_COLOR
	_env.background_color = Color(0.0, 0.0, 1.0)
	_env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	_env.tonemap_exposure = 1.0
	_env.adjustment_enabled = false
	_env.ssao_enabled = false
	_env.glow_enabled = false
	var layer := CanvasLayer.new()
	root.add_child(layer)
	_label = Label.new()
	_label.add_theme_font_size_override("font_size", 64)
	_label.add_theme_color_override("font_color", Color(1.0, 1.0, 0.0))
	_label.position = Vector2(300, 620)
	_label.visible = false
	layer.add_child(_label)
	var shader := Shader.new()
	shader.code = BF_SHADER
	var report := {}
	for name: String in (job["heads"] as Dictionary):
		var h: Dictionary = job["heads"][name]
		var ch: Node3D = (load(h["char"]) as PackedScene).instantiate()
		root.add_child(ch)
		var lively: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(h["lively"]))
		var mats := _setup(ch, h, true)
		var live = Lively.new(ch, mats, lively, _texture(h["sclera"]))
		var sk: Skeleton3D = ch.find_children("*", "Skeleton3D", true, false)[0]
		var mid: Vector3 = (Lively._v(lively["eyes"]["left"]["centre"]) + Lively._v(lively["eyes"]["right"]["centre"])) * 0.5
		for mi: MeshInstance3D in ch.find_children("*", "MeshInstance3D", true, false):
			var m := ShaderMaterial.new()
			m.shader = shader
			m.set_shader_parameter("back_colour", Vector3(1.0, 0.0, 0.0) if mi == live.mesh else Vector3(1.0, 0.5, 0.0))
			mi.material_override = m
		live.on_clip = false
		live.breathing = 0.0
		var cells: Array[Image] = []
		var rep := {}
		var crops := out.path_join("%s_4x" % name)
		DirAccess.make_dir_recursive_absolute(crops)
		for g: Array in BF_GAZES:
			live.reset_motion()
			live.reset_springs()
			live.reset_eyes()
			live.on_clip = g[0] == "jog"
			if g[0] == "jog":  # the springs and the skin under a clip: Jog_Fwd 0.4 s in, the head following a turn
				var ap: AnimationPlayer = _anim(ch)
				if ap != null and ap.has_animation("Jog_Fwd"):
					ap.play("Jog_Fwd")
				live.eye_mode = "lead"
				live.head_follow = 1.0
				live.target = sk.global_transform * (mid + Vector3(sin(deg_to_rad(-30.0)), 0.1, cos(deg_to_rad(-30.0))) * 2.5)
				for i: int in 10:
					if ap != null:
						ap.seek(i / 24.0, true)
					live.step(1.0 / 24.0)
			elif g[0] == "lead":
				live.eye_mode = "lead"
				live.head_follow = 1.0
				live.target = sk.global_transform * (mid + Vector3(sin(deg_to_rad(40.0)), 0.0, cos(deg_to_rad(40.0))) * 2.5)
				for i: int in 8:
					live.step(1.0 / 24.0)
			else:
				live.eye_mode = "free"
				live.head_follow = 0.0
				live.target = sk.global_transform * (mid + (g[1] as Vector3))
				for i: int in 30:
					live.step(1.0 / 24.0)
			var c: Vector3 = live.mesh.global_transform * ((live.eye_centre("left") + live.eye_centre("right")) * 0.5)
			var row := {}
			for v: Array in VIEWS:
				var yaw := deg_to_rad(float(v[1]))
				var pitch := deg_to_rad(float(v[2]))
				var dist: float = FRAME_H * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
				_cam.projection = Camera3D.PROJECTION_PERSPECTIVE
				_cam.position = c + Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch)) * dist
				_cam.look_at(c)
				_label.visible = false
				for _i: int in 4:
					await process_frame
				await RenderingServer.frame_post_draw
				var img: Image = root.get_texture().get_image()
				img.convert(Image.FORMAT_RGB8)
				var n := _count(img)
				var per := {"head": n["red"]}
				var cam_head: Transform3D = _cam.global_transform
				for side: String in ["left", "right"]:
					var e: Vector3 = live.mesh.global_transform * live.eye_front(side)
					var ef: Vector3 = (live.mesh.global_transform.basis * (live.eye_front(side) - live.eye_centre(side))).normalized()
					per[side] = 0
					if ef.dot(Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch))) < 0.0:
						continue  # the eye on the head's far side: its close-up camera sits inside the head
					var de: float = EYE_H * 0.5 / tan(deg_to_rad(_cam.fov * 0.5))
					_cam.position = e + Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch)) * de
					_cam.look_at(e)
					for _i: int in 4:
						await process_frame
					await RenderingServer.frame_post_draw
					var im2: Image = root.get_texture().get_image()
					im2.convert(Image.FORMAT_RGB8)
					var n2 := _count(im2)
					per[side] = n2["red"]
					n["orange"] += n2["orange"]
					if n2["red"] > n["red"] or (n["red"] == 0 and n2["red"] > 0):
						n["cx"] = n2["cx"]
						n["cy"] = n2["cy"]
						img = im2
				n["red"] = per["head"] + per["left"] + per["right"]
				_cam.global_transform = cam_head
				row[v[0]] = {"red": n["red"], "orange": n["orange"], "cx": int(n["cx"]), "cy": int(n["cy"]), "per": per}
				if n["red"] > 0:
					var cx: int = clampi(int(n["cx"]), 80, img.get_width() - 80)
					var cy: int = clampi(int(n["cy"]), 45, img.get_height() - 45)
					var z: Image = img.get_region(Rect2i(cx - 80, cy - 45, 160, 90))
					z.resize(640, 360, Image.INTERPOLATE_NEAREST)
					z.save_png(crops.path_join("%s_%s.png" % [g[0], v[0]]))
				_label.text = "%s %s  red %d" % [g[0], v[0], n["red"]]
				_label.visible = true
				var cell: Image = await _grab(BF_CELL)
				if n["red"] > 0:
					for k: int in 3:
						for t: int in BF_CELL.x:
							for e: int in [k, BF_CELL.y - 1 - k]:
								cell.set_pixel(t, e, Color(1.0, 1.0, 0.0))
								cell.set_pixel(e, t, Color(1.0, 1.0, 0.0))
				cells.append(cell)
				print("BACKFACE %s %s %s %s" % [name, g[0], v[0], JSON.stringify({"red": n["red"], "orange": n["orange"]})])
			rep[g[0]] = row
		_label.visible = false
		_sheet(cells, BF_CELL, VIEWS.size()).save_jpg(out.path_join("backface_%s.jpg" % name), 0.92)
		report[name] = rep
		ch.queue_free()
		await process_frame
	var f := FileAccess.open(out.path_join("backface.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, " "))
	f.close()
	print("BACKFACE done")
	quit(0)


## Red (the head's back faces), orange (another mesh's) and the red pixels' middle in img.
static func _count(img: Image) -> Dictionary:
	var red := 0
	var orange := 0
	var sx := 0.0
	var sy := 0.0
	var data: PackedByteArray = img.get_data()
	var w: int = img.get_width()
	for i: int in range(0, data.size(), 3):
		var r: int = data[i]
		var g: int = data[i + 1]
		var b: int = data[i + 2]
		if r > 100 and r * 2 > g * 5 and r * 2 > b * 5:
			red += 1
			var p: int = i / 3
			sx += p % w
			sy += p / w
		elif r > 150 and g * 10 > r * 3 and g * 10 < r * 7 and b * 5 < r:
			orange += 1
	return {"red": red, "orange": orange, "cx": sx / maxf(1.0, red), "cy": sy / maxf(1.0, red)}
