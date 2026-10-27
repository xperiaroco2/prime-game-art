extends "res://alien/char_shots.gd"
## The photo poses' review pictures (art #196): tools/blender/alien_poses_run.py --shots writes the job (the head's
## entry as char_shots.gd's, the legs, arms and starting pairs) and runs this in the runner's off-screen window. The
## character in the game's look (char_shots.gd's _setup and studio), posed by pose_layers.gd (the reference the game
## copies), standing at the origin; the photographer's camera: 1.5 m high, 7 m away, level turn only (FOV 19, the
## whole body framed). Facings are where the camera stands: front (+Z, the character faces it), left (the
## character's left, +X), right, back; the three-quarter view from front-left (35 deg). Outlines: every mesh drawn
## flat black on white. Into <out>/, per character <c>:
## - starting_<c>.png: the 6 starting pairs (rows) x front, left, right, back rendered, then the same four outlines;
## - grid_front_<c>.png, grid_34_<c>.png: all 48 pairs, rows the legs, columns the arms, each cell labelled;
## - grid_outline_<facing>_<c>.png: the 48 outlines per facing;
## - close_arms_<c>.png: the arms where hands meet or touch (HandsOnHips, Heart, FingerUp, HandsBehindHead, Salute;
##   on Stand) and PalmsOut, close on the upper body from the front, the left and the three-quarter;
## - close_legs_<c>.png: every legs pose (with HandsOnHips) close on the lower body, front, left, three-quarter;
## - a *_1280.png copy of every sheet wider than 1280 px; shots_<c>.json: what each shows.
## Args after "--": <job.json>

const PoseLayers = preload("res://alien/pose_layers.gd")
const FACINGS := {"front": 0.0, "left": 90.0, "right": -90.0, "back": 180.0}
const VIEW_34 := 35.0
const CAM_H := 1.5
const CAM_D := 7.0
const FRAME_C := Vector3(0.0, 0.92, 0.0)
const FRAME_H := 2.7  # the far shots' framed height (m): Plane's span fits the cell
const START_CELL := Vector2i(220, 330)
const GRID_CELL := Vector2i(200, 300)
const CLOSE_CELL := Vector2i(300, 300)
const CLOSE_ARMS := ["HandsOnHips", "Heart", "FingerUp", "HandsBehindHead", "Salute", "PalmsOut"]

var _ch: Node3D
var _sk: Skeleton3D
var _layers
var _label: Label
var _ground: MeshInstance3D
var _meshes: Array[MeshInstance3D] = []
var _keep := {}
var _black: StandardMaterial3D
var _white_env: Environment


func _run() -> void:
	var job: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	_stage(job["hdri"])
	_apply_fix(job.get("fix", {}))
	_ground = MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(30.0, 30.0)
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.5, 0.51, 0.53)
	gm.roughness = 0.9
	plane.material = gm
	_ground.mesh = plane
	root.add_child(_ground)
	var h: Dictionary = job["head"]
	_ch = (load(h["char"]) as PackedScene).instantiate()
	root.add_child(_ch)
	_setup(_ch, h, true)
	_sk = _ch.find_children("*", "Skeleton3D", true, false)[0]
	var ap: AnimationPlayer = _ch.find_children("*", "AnimationPlayer", true, false)[0]
	ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	_layers = PoseLayers.new()
	_ch.add_child(_layers)
	_layers.setup(ap)
	for mi: Node in _ch.find_children("*", "MeshInstance3D", true, false):
		_meshes.append(mi)
		_keep[mi] = (mi as MeshInstance3D).material_override
	_black = StandardMaterial3D.new()
	_black.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_black.albedo_color = Color.BLACK
	_black.cull_mode = BaseMaterial3D.CULL_DISABLED
	_white_env = Environment.new()
	_white_env.background_mode = Environment.BG_COLOR
	_white_env.background_color = Color.WHITE
	_white_env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var ui := CanvasLayer.new()
	root.add_child(ui)
	_label = Label.new()
	_label.add_theme_font_size_override("font_size", 34)
	_label.add_theme_color_override("font_color", Color.WHITE)
	_label.add_theme_color_override("font_outline_color", Color.BLACK)
	_label.add_theme_constant_override("outline_size", 5)
	ui.add_child(_label)
	_cam.projection = Camera3D.PROJECTION_PERSPECTIVE
	var c: String = job["char_name"]
	var out: String = job["out"]
	var report := {"char": h["char"], "camera": {"height_m": CAM_H, "distance_m": CAM_D, "fov_deg": 19.0},
		"facings": FACINGS, "three_quarter_deg": VIEW_34}
	# the 6 starting pairs: four facings rendered, then their four outlines
	var cells: Array[Image] = []
	for p: Array in job["starting"]:
		_pose(p[0], p[1])
		for mask: bool in [false, true]:
			for f: String in FACINGS:
				_label.text = "%s
%s
%s" % [p[0], p[1], f] if f == "front" else f
				cells.append(await _shot(FACINGS[f], _centre(), FRAME_H, START_CELL, mask))
	_save(cells, START_CELL, 8, out.path_join("starting_%s.png" % c))
	report["starting"] = {"rows": job["starting"], "cols": ["front", "left", "right", "back", "outline front", "outline left", "outline right", "outline back"]}
	# the 48 pairs: front and three-quarter rendered, then one outline grid per facing
	for g: Array in [["front", 0.0, false], ["34", VIEW_34, false], ["outline_front", 0.0, true],
			["outline_left", 90.0, true], ["outline_right", -90.0, true], ["outline_back", 180.0, true]]:
		cells = []
		for lg: String in job["legs"]:
			for am: String in job["arms"]:
				_pose(lg, am)
				_label.text = "%s\n%s" % [lg, am]
				cells.append(await _shot(g[1], _centre(), FRAME_H, GRID_CELL, g[2]))
		_save(cells, GRID_CELL, job["arms"].size(), out.path_join("grid_%s_%s.png" % [g[0], c]))
	report["grids"] = {"rows": job["legs"], "cols": job["arms"]}
	# close-ups: the arms where hands meet or touch (on Stand), the legs' contacts (with HandsOnHips)
	cells = []
	for am: String in CLOSE_ARMS:
		_pose("Stand", am)
		for v: float in [0.0, 90.0, VIEW_34]:
			_label.text = "%s
%s" % [am, {0.0: "front", 90.0: "left", VIEW_34: "3/4"}[v]]
			cells.append(await _shot(v, _bone("Neck") + Vector3(0.0, 0.02, 0.0), 1.25, CLOSE_CELL, false))
	_save(cells, CLOSE_CELL, 3, out.path_join("close_arms_%s.png" % c))
	cells = []
	for lg: String in job["legs"]:
		_pose(lg, "HandsOnHips")
		for v: float in [0.0, 90.0, VIEW_34]:
			_label.text = "%s
%s" % [lg, {0.0: "front", 90.0: "left", VIEW_34: "3/4"}[v]]
			cells.append(await _shot(v, Vector3(0.0, 0.45, 0.0), 1.15, CLOSE_CELL, false))
	_save(cells, CLOSE_CELL, 3, out.path_join("close_legs_%s.png" % c))
	report["close_arms"] = {"rows": CLOSE_ARMS, "legs": "Stand", "cols": ["front", "left", "3/4"]}
	report["close_legs"] = {"rows": job["legs"], "arms": "HandsOnHips", "cols": ["front", "left", "3/4"]}
	FileAccess.open(out.path_join("shots_%s.json" % c), FileAccess.WRITE).store_string(JSON.stringify(report, " "))
	quit(0)


func _pose(lg: String, am: String) -> void:
	if not _layers.play_pair(lg, am):
		printerr("ERROR pose %s+%s missing" % [lg, am])


func _bone(b: String) -> Vector3:
	return _sk.global_transform * _sk.get_bone_global_pose(_sk.find_bone(b)).origin


## The far shots' centre: the scale is fixed (FRAME_H), the centre follows the pose: half the head's height (a
## seated pose is not left in the cell's lower half) and half the hips' sideways shift (the lunge stays in the cell).
func _centre() -> Vector3:
	var hips := _bone("Hips")
	return Vector3(hips.x * 0.5, maxf(0.62, minf(FRAME_C.y, (_bone("Head").y + 0.3) * 0.5)), hips.z * 0.5)


## The photographer's camera at yaw (degrees, where it stands) and CAM_H toward c, framing height h (the far shots);
## a close-up (h under 1.5 m) stands nearer, level with c.
func _shot(yaw_deg: float, c: Vector3, h: float, size: Vector2i, mask: bool) -> Image:
	for mi: MeshInstance3D in _meshes:
		mi.material_override = _black if mask else _keep[mi]
	_ground.visible = not mask
	_cam.environment = _white_env if mask else null
	var yaw := deg_to_rad(yaw_deg)
	var far: bool = h > 1.5
	var d: float = CAM_D if far else 2.6
	_cam.fov = rad_to_deg(2.0 * atan(h * 0.5 / d))
	_cam.position = Vector3(c.x + sin(yaw) * d, CAM_H if far else c.y + 0.1, c.z + cos(yaw) * d)  # moved with c: no turn
	_cam.look_at(c)
	_label.position = Vector2(406.0, 4.0)
	return await _grab(size)


func _save(cells: Array[Image], size: Vector2i, cols: int, path: String) -> void:
	var rows: int = (cells.size() + cols - 1) / cols
	var img := Image.create(cols * (size.x + 4) - 4, rows * (size.y + 4) - 4, false, Image.FORMAT_RGB8)
	img.fill(Color(0.2, 0.2, 0.2))
	for i: int in cells.size():
		img.blit_rect(cells[i], Rect2i(Vector2i.ZERO, size), Vector2i((i % cols) * (size.x + 4), (i / cols) * (size.y + 4)))
	img.save_png(path)
	if img.get_width() > 1280:
		img.resize(1280, img.get_height() * 1280 / img.get_width(), Image.INTERPOLATE_LANCZOS)
		img.save_png(path.trim_suffix(".png") + "_1280.png")
	print("SHOT %s %d cells" % [path.get_file(), cells.size()])
