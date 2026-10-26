extends "res://alien/char_shots.gd"
## The alien's locomotion set on a treadmill (art #196, option A step 3): tools/blender/alien_loco.py --reels writes
## the job (the head's entry as char_shots.gd's, the set's per-clip numbers, the reel plan with each clip's rate,
## direction and timeline from alien_loco_math.reel_timeline) and runs this in the runner's off-screen window.
## Per reel the character stays in place (the hips' travel per loop taken off the node), the floor's stripes move
## under it at the slot's speed against the travel, the clip plays at rate = speed / v0 as the game's TimeScale does;
## a disc flashes under each foot at its contact (left blue, right orange) and the timeline at the bottom marks the
## game's footstep beat (white ticks, the clip's own contacts as yellow ticks under them) beside each foot's contacts,
## a red playhead running over it. Side view (from the character's left), strafes from the front.
## - <frames>/<reel>/0000.png...: 1280x720 at 24 fps; a pair (the game's clip beside its speed variant) is two 640 px
##   halves;
## - <out>/<reel>.png: the key-frame sheet, 8 frames over one cycle per clip (a row each, 1280 px); the grid reel
##   (no video): a 2x3 sheet of its clips, 4 phases each (both contacts and the passes between);
## - Idle_to_Jog_Fwd: the idle, then the jog at its speed with the game's cross-fade, played by the mixer itself;
##   its sheet: 8 frames from 0.25 s before the switch to 0.8 s after (START_KEYS);
## - <out>/reels.json: per reel its clips, rate, speed, contacts and beats shown, frames written.
## Args after "--": <job.json>

const SHEET_CROP := Vector2i(400, 720)
const CELL8 := Vector2i(160, 288)
const CELL4 := Vector2i(106, 191)
const STRIPE_M := 0.5
const FLASH_S := 0.12
const L_COL := Color(0.25, 0.55, 1.0)
const R_COL := Color(1.0, 0.55, 0.15)
const CONTACT_TICK := Color(1.0, 0.9, 0.1)
const START_KEYS := [-0.25, -0.1, 0.05, 0.2, 0.35, 0.5, 0.65, 0.8]  # the start's sheet: seconds from the switch

var _ch: Node3D
var _sk: Skeleton3D
var _ap: AnimationPlayer
var _names := {}
var _stripes: Node3D
var _discs := {}
var _ui: CanvasLayer
var _title: Label
var _lane: Control


func _run() -> void:
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	_stage(job["hdri"])
	_apply_fix(job.get("fix", {}))
	_floor()
	var h: Dictionary = job["head"]
	_ch = (load(h["char"]) as PackedScene).instantiate()
	root.add_child(_ch)
	_setup(_ch, h, true)
	_sk = _ch.find_children("*", "Skeleton3D", true, false)[0]
	_ap = _ch.find_children("*", "AnimationPlayer", true, false)[0]
	_ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	for n: String in _ap.get_animation_list():
		_names[n.get_slice("|", n.get_slice_count("|") - 1).trim_suffix("_Loop")] = n
	for side: String in ["Left", "Right"]:
		var d := MeshInstance3D.new()
		var cyl := CylinderMesh.new()
		cyl.top_radius = 0.1
		cyl.bottom_radius = 0.1
		cyl.height = 0.01
		var m := StandardMaterial3D.new()
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.albedo_color = L_COL if side == "Left" else R_COL
		cyl.material = m
		d.mesh = cyl
		root.add_child(d)
		_discs[side] = d
	_ui = CanvasLayer.new()
	root.add_child(_ui)
	_title = Label.new()
	_title.add_theme_font_size_override("font_size", 18)
	_title.add_theme_color_override("font_color", Color.WHITE)
	_title.add_theme_color_override("font_outline_color", Color.BLACK)
	_title.add_theme_constant_override("outline_size", 4)
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_ui.add_child(_title)
	_cam.projection = Camera3D.PROJECTION_PERSPECTIVE
	_cam.fov = 30.0
	var report := {}
	for reel: Dictionary in job["reels"]:
		report[reel["name"]] = await _reel(reel, job)
	FileAccess.open(job["out"].path_join("reels.json"), FileAccess.WRITE).store_string(JSON.stringify(report, " "))
	quit(0)


func _floor() -> void:
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(60.0, 60.0)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.5, 0.51, 0.53)
	gm.roughness = 0.9
	plane.material = gm
	ground.mesh = plane
	root.add_child(ground)
	_stripes = Node3D.new()
	root.add_child(_stripes)
	var sm := StandardMaterial3D.new()
	sm.albedo_color = Color(0.16, 0.17, 0.19)
	sm.roughness = 0.9
	for i: int in 41:
		var s := MeshInstance3D.new()
		var b := BoxMesh.new()
		b.size = Vector3(0.07, 0.004, 8.0)
		b.material = sm
		s.mesh = b
		s.position = Vector3((i - 20) * STRIPE_M, 0.002, 0.0)
		_stripes.add_child(s)


func _aim(view: String) -> void:
	var at := Vector3(0.0, 0.85, 0.0)
	_cam.position = Vector3(0.0, 1.3, 5.4) if view == "front" else Vector3(5.4, 1.3, 0.0)
	_cam.look_at(at)


## The timeline lane: the reel's seconds across [x0, x1], the beats as white ticks, each foot's contacts on its row.
func _lane_for(tl: Dictionary, seconds: float, x0: float, x1: float) -> void:
	if _lane != null:
		_lane.queue_free()
	_lane = Control.new()
	_ui.add_child(_lane)
	var y := 668.0
	var bg := ColorRect.new()
	bg.color = Color(0.0, 0.0, 0.0, 0.55)
	bg.position = Vector2(x0 - 6.0, y - 6.0)
	bg.size = Vector2(x1 - x0 + 12.0, 46.0)
	_lane.add_child(bg)
	var mk := func(t: float, row: int, c: Color, w: float) -> void:
		var r := ColorRect.new()
		r.color = c
		r.position = Vector2(x0 + (x1 - x0) * t / seconds - w * 0.5, y + row * 12.0)
		r.size = Vector2(w, 10.0 if row else 10.0)
		_lane.add_child(r)
	# the clip's own contacts (both feet) as yellow ticks on the beat's row, under the white beats: a footstep clock
	# that does not match the feet shows as ticks that drift apart (step 4b)
	for side: String in ["Left", "Right"]:
		for t: float in tl["contacts"][side]:
			mk.call(t, 0, CONTACT_TICK, 2.0)
	for t: float in tl["beats"]:
		mk.call(t, 0, Color.WHITE, 3.0)
	for t: float in tl["contacts"]["Left"]:
		mk.call(t, 1, L_COL, 6.0)
	for t: float in tl["contacts"]["Right"]:
		mk.call(t, 2, R_COL, 6.0)
	var head := ColorRect.new()
	head.name = "head"
	head.color = Color(1.0, 0.15, 0.15)
	head.size = Vector2(2.0, 40.0)
	head.position = Vector2(x0, y - 3.0)
	_lane.add_child(head)
	_lane.set_meta("x", [x0, x1, seconds])


func _flash(tl: Dictionary, t: float) -> void:
	for side: String in ["Left", "Right"]:
		var on := false
		for e: float in tl["contacts"][side]:
			if t >= e and t - e < FLASH_S:
				on = true
		var d: MeshInstance3D = _discs[side]
		d.visible = on
		var p: Vector3 = _sk.global_transform * _sk.get_bone_global_pose(_sk.find_bone(side + "Foot")).origin
		d.global_position = Vector3(p.x, 0.006, p.z)
	var xs: Array = _lane.get_meta("x")
	(_lane.get_node("head") as ColorRect).position.x = xs[0] + (xs[1] - xs[0]) * t / xs[2] - 1.0


## The hips' horizontal travel over one loop (the node at the origin).
func _travel(anim: String, length: float) -> Vector3:
	_ch.position = Vector3.ZERO
	_ap.play(anim)
	var hb: int = _sk.find_bone("Hips")
	_ap.seek(0.0, true)
	var a: Vector3 = _sk.global_transform * _sk.get_bone_global_pose(hb).origin
	_ap.seek(length, true)
	var b: Vector3 = _sk.global_transform * _sk.get_bone_global_pose(hb).origin
	return Vector3(b.x - a.x, 0.0, b.z - a.z)


func _place(tl: Dictionary, anim: String, length: float, d: Vector3, t: float, move_t: float) -> void:
	var ct: float = maxf(0.0, move_t) * float(tl["rate"])
	_ap.seek(fposmod(ct, length), true)
	_ch.position = -d * (ct / length)
	_ground(tl, move_t)


func _ground(tl: Dictionary, move_t: float) -> void:
	var dir := Vector3(tl["dir"][0], 0.0, tl["dir"][1])
	_stripes.rotation.y = atan2(-dir.z, dir.x)
	_stripes.position = dir * fposmod(float(tl["speed"]) * maxf(0.0, move_t), STRIPE_M)


func _shot() -> Image:
	for _i: int in 2:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	img.convert(Image.FORMAT_RGB8)
	return img


func _crop(img: Image, size: Vector2i, cell: Vector2i) -> Image:
	var c: Image = img.get_region(Rect2i((img.get_width() - size.x) / 2, 0, size.x, size.y))
	c.resize(cell.x, cell.y, Image.INTERPOLATE_LANCZOS)
	return c


func _reel(reel: Dictionary, job: Dictionary) -> Dictionary:
	var seconds: float = reel.get("seconds", job["seconds"])
	var n: int = int(round(seconds * FPS))
	var clips: Array = reel["clips"]
	var pair: bool = clips.size() == 2 and reel["video"]
	var grid: bool = not reel["video"]
	var dir_out: String = job["frames"].path_join(reel["name"])
	if reel["video"]:
		DirAccess.make_dir_recursive_absolute(dir_out)
	_aim(reel["view"])
	var rows: Array[Image] = []
	var halves: Array[Image] = []
	var info := {"clips": []}
	for ci: int in clips.size():
		var c: Dictionary = clips[ci]
		var tl: Dictionary = c["timeline"]
		var anim: String = _names[c["clip"]]
		var length: float = _ap.get_animation(anim).length
		var d := _travel(anim, length)
		var x0 := 330.0 if pair else 40.0
		var x1 := 950.0 if pair else 1240.0
		_lane_for(tl, seconds, x0, x1)
		_title.text = "%s\n%.2f m/s  rate %.2f  beat %.3f s" % [c["clip"], tl["speed"], tl["rate"], tl["beat_s"]]
		_title.position = Vector2(x0, 14.0)
		_title.size = Vector2(x1 - x0, 50.0)
		var cyc: float = length / float(tl["rate"])
		var keys := {}
		var nk: int = 4 if grid else 8
		var start: Dictionary = reel.get("start", {})
		for k: int in nk:
			if start.is_empty():
				keys[int(round(cyc * k / nk * FPS))] = k
			else:
				keys[int(round((float(start["at"]) + START_KEYS[k]) * FPS))] = k
		var row: Array[Image] = []
		row.resize(nk)
		if not start.is_empty():
			_ap.play(_names[start["from"]])
			_ap.seek(0.0, true)
			_ch.position = Vector3.ZERO
		var switched := false
		var moved := Vector3.ZERO
		for f: int in n:
			var t: float = f / FPS
			if grid and not keys.has(f):
				continue
			if start.is_empty():
				_place(tl, anim, length, d, t, t)
			else:
				if f > 0:
					if not switched and t >= float(start["at"]):
						_ap.play(anim, float(start["fade"]), float(tl["rate"]))
						switched = true
					_ap.advance(1.0 / FPS)
				if switched:
					moved += d / length * float(tl["rate"]) / FPS
				_ch.position = -moved
				_ground(tl, t - float(start["at"]))
			_flash(tl, t)
			var img: Image = await _shot()
			if keys.has(f):
				row[keys[f]] = _crop(img, SHEET_CROP, CELL4 if grid else CELL8)
			if not reel["video"]:
				continue
			if pair and ci == 0:
				halves.append(img.get_region(Rect2i(320, 0, 640, 720)))
			elif pair:
				var both := Image.create(1280, 720, false, Image.FORMAT_RGB8)
				both.blit_rect(halves[f], Rect2i(0, 0, 640, 720), Vector2i(0, 0))
				both.blit_rect(img, Rect2i(320, 0, 640, 720), Vector2i(640, 0))
				both.save_png(dir_out.path_join("%04d.png" % f))
			else:
				img.save_png(dir_out.path_join("%04d.png" % f))
		rows.append(_strip(row))
		info["clips"].append({"clip": c["clip"], "speed": tl["speed"], "rate": tl["rate"], "beat_s": tl["beat_s"],
			"beats": tl["beats"].size(), "contacts": tl["contacts"]["Left"].size() + tl["contacts"]["Right"].size(),
			"travel_per_loop_m": snappedf(d.length(), 0.001), "length_s": snappedf(length, 0.001)})
	if not rows.is_empty():
		_sheet_of(rows, 3 if grid else 1).save_png(job["out"].path_join(reel["name"] + ".png"))
	info["frames"] = n if reel["video"] else 0
	print("REEL %s %s" % [reel["name"], JSON.stringify(info["clips"])])
	return info


func _strip(cells: Array[Image]) -> Image:
	var w: int = cells[0].get_width()
	var out := Image.create(w * cells.size(), cells[0].get_height(), false, Image.FORMAT_RGB8)
	for i: int in cells.size():
		out.blit_rect(cells[i], Rect2i(Vector2i.ZERO, cells[i].get_size()), Vector2i(i * w, 0))
	return out


func _sheet_of(rows: Array[Image], cols: int) -> Image:
	var w: int = rows[0].get_width()
	var hh: int = rows[0].get_height()
	var nr: int = ceili(rows.size() / float(cols))
	var out := Image.create(w * cols + 4 * (cols - 1), hh * nr + 4 * (nr - 1), false, Image.FORMAT_RGB8)
	out.fill(Color.WHITE)
	for i: int in rows.size():
		out.blit_rect(rows[i], Rect2i(Vector2i.ZERO, rows[i].get_size()), Vector2i((i % cols) * (w + 4), (i / cols) * (hh + 4)))
	return out
