extends CharacterBody3D
## The engineer's walk round the ship (`tools/run.py ship --play`, art #263, docs/ship.md "Walking it yourself"): a
## first-person capsule with the game's size (ship.toml [player]) on the built pieces' colliders, and a key that saves
## a screenshot with where it was taken. ship.gd adds it in mode "play"; its `test` runs it alone off-screen.
##   W A S D walk, Shift run, Space jump, mouse look, F fly through walls (Q down, E up), P or F12 a screenshot,
##   F11 full screen, H the help, Esc frees the mouse (a click takes it back), Ctrl+Q quits.

const WALK: float = 3.0
const RUN: float = 6.0
const FLY: float = 5.0
const JUMP: float = 4.2
const GRAVITY: float = 9.8
const LOOK: float = 0.0025

var out: String = ""
var test: bool = false   # the runner's off-screen test: never takes the mouse
var eye_h: float = 1.6
var shots: int = 0
var flying: bool = false
var camera: Camera3D
var _pitch: float = 0.0
var _hud: Label
var _note: Label
var _note_left: float = 0.0
var _shape: CollisionShape3D


func setup(radius: float, height: float, out_dir: String) -> void:
	out = out_dir
	eye_h = height - 0.2
	_shape = CollisionShape3D.new()
	var cap: CapsuleShape3D = CapsuleShape3D.new()
	cap.radius = radius
	cap.height = height
	_shape.shape = cap
	_shape.position.y = height / 2.0
	add_child(_shape)
	floor_snap_length = 0.3
	camera = Camera3D.new()
	camera.position.y = eye_h
	camera.near = 0.05
	camera.far = 500.0
	camera.fov = 75.0
	add_child(camera)
	var layer: CanvasLayer = CanvasLayer.new()
	_hud = _label(Vector2(16, 10), 18)
	_note = _label(Vector2(16, 40), 26)
	layer.add_child(_hud)
	layer.add_child(_note)
	add_child(layer)
	_note.text = "W A S D walk, Shift run, Space jump, F fly (Q/E), P screenshot, F11 full screen, H help, Esc mouse"
	_note_left = 12.0


func _label(at: Vector2, size: int) -> Label:
	var l: Label = Label.new()
	l.position = at
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", Color(1, 1, 1))
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	l.add_theme_constant_override("outline_size", 6)
	return l


func _ready() -> void:
	camera.make_current()
	if not test:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var m: InputEventMouseMotion = event
		rotate_y(-m.relative.x * LOOK)
		_pitch = clampf(_pitch - m.relative.y * LOOK, -1.5, 1.5)
		camera.rotation.x = _pitch
	elif event is InputEventMouseButton and (event as InputEventMouseButton).pressed and not test:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event is InputEventKey and (event as InputEventKey).pressed and not (event as InputEventKey).echo:
		var k: InputEventKey = event
		match k.keycode:
			KEY_ESCAPE:
				Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
			KEY_P, KEY_F12:
				shot()
			KEY_F:
				flying = not flying
				_shape.disabled = flying
				velocity = Vector3.ZERO
				_say("fly through walls: " + ("on (Q down, E up)" if flying else "off"))
			KEY_F11:
				var w: Window = get_window()
				w.mode = Window.MODE_WINDOWED if w.mode == Window.MODE_FULLSCREEN else Window.MODE_FULLSCREEN
			KEY_H:
				_say("W A S D walk, Shift run, Space jump, F fly (Q/E), P screenshot, F11 full screen, Esc mouse, Ctrl+Q quit")
			KEY_Q:
				if k.ctrl_pressed:
					get_tree().quit(0)


func _physics_process(delta: float) -> void:
	var dir: Vector2 = Vector2(
		float(Input.is_physical_key_pressed(KEY_D)) - float(Input.is_physical_key_pressed(KEY_A)),
		float(Input.is_physical_key_pressed(KEY_S)) - float(Input.is_physical_key_pressed(KEY_W)))
	var speed: float = RUN if Input.is_physical_key_pressed(KEY_SHIFT) else WALK
	if flying:
		var look: Basis = camera.global_transform.basis
		var v: Vector3 = (look.x * dir.x + look.z * dir.y)
		v.y += float(Input.is_physical_key_pressed(KEY_E)) - float(Input.is_physical_key_pressed(KEY_Q))
		global_position += v.normalized() * (FLY if speed == WALK else FLY * 2.0) * delta if v.length() > 0.01 else Vector3.ZERO
	else:
		var flat: Vector3 = (global_transform.basis.x * dir.x + global_transform.basis.z * dir.y)
		flat.y = 0.0
		flat = flat.normalized() * speed if flat.length() > 0.01 else Vector3.ZERO
		var vy: float = velocity.y
		if is_on_floor():
			vy = JUMP if Input.is_physical_key_pressed(KEY_SPACE) else 0.0
		else:
			vy -= GRAVITY * delta
		velocity = Vector3(flat.x, vy, flat.z)
		move_and_slide()
	_hud.text = "x %.2f  y %.2f  h %.2f   facing %d°%s" % [global_position.x, global_position.z, global_position.y,
		posmod(roundi(rad_to_deg(-rotation.y)), 360), "   FLY" if flying else ""]
	if _note_left > 0.0:
		_note_left -= delta
		if _note_left <= 0.0:
			_note.text = ""


## Saves <out>/shot_NNN.png (the HUD with the position is in it) and a line in <out>/shots.txt: the plan position
## (x, y, h as ship.toml writes them), the eye, the look direction and the time.
func shot() -> void:
	shots += 1
	var stamp: String = Time.get_datetime_string_from_system().replace(":", "-")
	var name: String = "shot_%s_%03d.png" % [stamp, shots]
	await RenderingServer.frame_post_draw
	var img: Image = get_viewport().get_texture().get_image()
	img.save_png(out.path_join(name))
	var eye: Vector3 = camera.global_position
	var fwd: Vector3 = -camera.global_transform.basis.z
	var line: String = "%s  plan x %.3f y %.3f h %.3f  eye h %.3f  look [%.3f, %.3f, %.3f]  %s%s\n" % [name,
		global_position.x, global_position.z, global_position.y, eye.y, fwd.x, fwd.z, fwd.y,
		Time.get_datetime_string_from_system(), "  fly" if flying else ""]
	var path: String = out.path_join("shots.txt")
	var f: FileAccess = FileAccess.open(path, FileAccess.READ_WRITE if FileAccess.file_exists(path) else FileAccess.WRITE)
	f.seek_end()
	f.store_string(line)
	f.close()
	print("SHIP play shot %s" % out.path_join(name))
	_say("saved " + name)


func _say(text: String) -> void:
	_note.text = text
	_note_left = 3.0
