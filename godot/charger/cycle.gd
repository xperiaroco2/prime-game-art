extends "res://charger/room.gd"
## One full cycle of the east crystal charger in lens room C at night (art#263), for the engineer's look at its motion:
## charger/room.gd's ship (ship.gd's night look, the chargers in charger.gd's look, a crystal on the east charger's
## anchor in crystal.gd's look) seen from a still camera at the player's eye; the beats on a fixed clock (step(dt) at
## 1 / fps per frame, every value a pure function of the time, eased, never linear), one PNG per frame and the beats'
## key moments again with their label for the sheet. Only what the charger and the crystal have: Charger.set_state,
## set_carrier, set_ring, set_pressed (eased in by a fraction of its TRAVEL), Crystal.set_charge. Two stand-ins, as
## the game has no hand yet: the crystal's way into the cup and out of it (an eased path on the anchor's axis).
## The electricity (prime-game#1095 "some electricity there", Zap.step on the cycle's clock): arcs from the inner
## prongs' electrodes into the crystal and sparks at their hits while the charge runs, pulses up the four conduits,
## one big flash with the ring's flare (FLASH), then quiet: the conduits steady, the crystal glowing.
## The back panel's traces (prime-game#1095 c6468773545, Traces.set_panel): dim until the charge starts, then a
## bright front runs along every trace from its outer end to the ring at the charge fraction; at full the ring flares
## once (FLARE) and the pattern holds full while the crystal waits; once the crystal leaves the cup it fades to dim
## over FADE s.
## Started by `ship --charger-cycle DIR` (tools/runner/commands/ship.py charger_cycle) through `_godot.window()`, in
## ship.gd's "shoot" mode (the off-screen window), with the request's "cycle": {"eye", "look", "fov", "fps"}:
##   godot <_godot.window() flags> -s res://charger/cycle.gd -- <request.json> <out>
## Writes <out>/frames/%05d.png, <out>/keys/%05d.png (labelled), <out>/keys_sheet.png (1280 px) and <out>/cycle.json.
## With the request's "cycle" "close": {"eye", "look"} (zap-4: a second camera about 1 m from the charger, for the
## engineer) every frame is drawn again from it into <out>/close/frames/%05d.png and its key shots into
## <out>/close/keys_sheet.png. <out>/zoom_sheet.png: the main camera's ZOOM frames cropped round the crystal (2x), a
## 2x2 sheet to judge the electricity from the player's distance.

const SECONDS := 24.0
const TURNS := 4.0          # the carrier's whole turns while charging (ending on a whole turn: no jump at "charged")
const RING_TURNS := -3.0    # the track ring the other way
## The crystal's stand-in path in the anchor's frame (m; +Y up the axis, +Z out of the charger toward the player):
## a cubic Bezier from above the player's hand, out of the frame, to the cup, its last leg straight down the axis.
const PATH := [Vector3(0.0, 1.0, 1.2), Vector3(0.0, 0.9, 0.0), Vector3(0.0, 0.5, 0.0), Vector3.ZERO]
## The beats (s): [from, to] per motion.
const INSERT := [2.0, 4.6]
const PRESS_IN := [5.6, 5.75]
const PRESS_OUT := [6.15, 6.3]
const CHARGING_AT := 5.9
const RISE_UP := [6.4, 7.6]
const SPIN := [6.9, 15.6]
const RING := [6.6, 15.8]
const CHARGE := [7.4, 15.4]
const RISE_DOWN := [15.8, 17.0]
const TAKE := [20.0, 22.4]
const FLARE := [15.4, 15.7]   # the ring's flare as the fronts reach it (CHARGE's end), about 0.3 s
const FADE := 0.5             # the traces back to dim once the crystal is out of the cup
const FLASH := [15.4, 15.62]  # the full charge's last big arc burst and light pop (zap.gd), with the flare
const KEYS := [[1.0, "1 idle, empty"], [3.4, "2 crystal put in (stand-in path)"], [5.0, "2 seated, spent"],
	[5.8, "3 button pressed"], [7.6, "4 charging: carrier up"], [9.0, "4 charging: the traces fill"],
	[11.0, "4 charging: carrier and ring turn"], [12.6, "4 charging: the arcs"],
	[15.0, "4 charging: nearly full"], [15.5, "5 full: the big flash, the ring flares"], [18.5, "5 charged, waiting"],
	[20.5, "6 lifted: the traces fade"], [20.9, "6 taken out (stand-in path)"],
	[23.5, "6 back to idle"]]

var _t: float = 0.0
var _pair: Dictionary = {}
var _dt: float = 0.0
## zap-4: the charging frames (s) of zoom_sheet.png and the crop round the crystal (px of the 1280x720 frame)
const ZOOM := [9.6, 11.4, 13.2, 14.6]
const ZOOM_CROP := Vector2i(320, 180)
var _arc_frames: int = 0
var _zap_bad: int = 0


## The cycle's values at time t: {"state", "rise", "carrier", "ring", "press", "charge", "crystal" (anchor-frame
## position), "shown", the traces' "fill", "flare", "lit" (Traces.set_panel) and the electricity's "flash" (Zap.step)}.
static func at(t: float) -> Dictionary:
	var state := "idle"
	if t >= CHARGING_AT and t < RISE_DOWN[1]:
		state = "charging"
	elif t >= RISE_DOWN[1] and t < _out_of_cup():
		state = "charged"
	var rise := _ss(RISE_UP, t) * (1.0 - _ss(RISE_DOWN, t))
	var press := _ss(PRESS_IN, t) * (1.0 - _ss(PRESS_OUT, t))
	var s := 1.0   # the crystal seated: 0 out of the frame, 1 in the cup
	if t < INSERT[1]:
		s = _ss(INSERT, t)
	elif t >= TAKE[0]:
		s = 1.0 - _ss(TAKE, t)
	var out: float = _out_of_cup()
	var fill: float = _ss(CHARGE, t) if t < out else (1.0 if t < out + FADE else 0.0)
	var flare: float = sin(PI * _u(FLARE, t)) if t > FLARE[0] and t < FLARE[1] else 0.0
	var lit: float = 1.0 - smoothstep(out, out + FADE, t)
	var flash: float = sin(PI * _u(FLASH, t)) if t > FLASH[0] and t < FLASH[1] else 0.0
	return {"state": state, "rise": rise, "carrier": TURNS * TAU * _glide(_u(SPIN, t), 0.2),
		"ring": RING_TURNS * TAU * _glide(_u(RING, t), 0.25), "press": press,
		"charge": _ss(CHARGE, t), "crystal": _bezier(s), "shown": t >= INSERT[0] and t < TAKE[1],
		"fill": fill, "flare": flare, "lit": lit, "flash": flash}


## The moment the crystal's tip leaves the cup on its way out (the charger goes back to idle).
static func _out_of_cup() -> float:
	for i: int in 200:
		var t: float = lerpf(TAKE[0], TAKE[1], i / 200.0)
		if _bezier(1.0 - _ss(TAKE, t)).y > 0.05:
			return t
	return TAKE[1]


static func _u(span: Array, t: float) -> float:
	return clampf((t - float(span[0])) / (float(span[1]) - float(span[0])), 0.0, 1.0)


static func _ss(span: Array, t: float) -> float:
	return smoothstep(float(span[0]), float(span[1]), t)


## A turn's share at u (0..1): the speed eases up over the first r, holds, eases down over the last r (smoothstep
## ramps, integrated), so the turn starts and stops softly and ends exactly on 1.
static func _glide(u: float, r: float) -> float:
	var x: float
	var p: float
	if u < r:
		x = u / r
		p = r * (x * x * x - 0.5 * x * x * x * x)
	elif u > 1.0 - r:
		x = (1.0 - u) / r
		p = (1.0 - r) - r * (x * x * x - 0.5 * x * x * x * x)
	else:
		p = 0.5 * r + (u - r)
	return p / (1.0 - r)


## The stand-in path at w (0 out of the frame, 1 seated).
static func _bezier(w: float) -> Vector3:
	var s: float = 1.0 - w
	return PATH[0] * s * s * s + PATH[1] * 3.0 * s * s * w + PATH[2] * 3.0 * s * w * w + PATH[3] * w * w * w


## One clock tick: the time moves on by dt and the charger and the crystal take the cycle's values.
func step(dt: float) -> void:
	_t += dt
	_dt = dt
	_apply(at(_t))


func _apply(v: Dictionary) -> void:
	var look: Dictionary = _pair["charger"]
	if look["state"] != v["state"]:
		Charger.set_state(look, v["state"])
	if v["state"] == "charging":
		Charger.set_carrier(look, v["rise"], v["carrier"])
	Charger.set_ring(look, v["ring"])
	Traces.set_panel(look, v["fill"], v["flare"], v["lit"])
	var k: float = v["press"]
	if k <= 0.0 or k >= 1.0:
		Charger.set_pressed(look, k >= 1.0)
	else:   # on its way: the same travel as set_pressed, a share of it
		(look["button"] as Node3D).position = (look["button_rest"] as Vector3) - Vector3(0.0, 0.0, Charger.TRAVEL * k)
	var crystal: Node3D = _pair["crystal"]
	crystal.visible = v["shown"]
	crystal.position = v["crystal"]
	Crystal.set_charge(_pair["crystal_look"], v["charge"])
	var omni: OmniLight3D = _pair["crystal_look"]["omni"]
	omni.visible = omni.visible and crystal.visible
	Zap.step(look, _dt, v["charge"], v["flash"], v["lit"])
	if bool(look["zap"]["active"]):
		_arc_frames += 1
		_check_ends(look)


## The arcs leave the electrodes and land on the crystal: each start within its electrode's radius + 2 mm of an
## electrode's centre, each hit within 1 cm of the crystal's axis-to-surface (in the crystal's frame). Fails the run.
func _check_ends(look: Dictionary) -> void:
	var z: Dictionary = look["zap"]
	var model: Node3D = z["model"]
	var ct: Transform3D = Zap._rel(z["crystal"], model)
	for ends: Array in Zap.endpoints(look):
		var best := INF
		for i: int in (z["locals"] as Array).size():
			var e: Vector3 = Zap._rel(z["ring"], model) * (z["locals"][i] as Vector3)
			best = minf(best, absf((ends[0] as Vector3).distance_to(e) - float(z["radii"][i])))
		var hc: Vector3 = ct.affine_inverse() * (ends[1] as Vector3)
		var r: float = Zap._radius(z["profile"], hc.y)
		var off: float = absf(Vector2(hc.x, hc.z).length() - r * 0.97)
		if best > 0.002 or off > 0.01:
			_zap_bad += 1


## ship.gd's "shoot" mode runs the cycle instead of the views.
func _shoot() -> void:
	_environment()
	var ship: Node3D = _build()
	var lights: int = _dress(ship)
	_probes()
	for p: Dictionary in _pairs:
		if p["crystal"] != null:
			_pair = p
	if _pair.is_empty():
		_fail("no charger with a crystal")
		return
	var c: Dictionary = _req["cycle"]
	_camera = Camera3D.new()
	_camera.near = 0.05
	_camera.far = 500.0
	_camera.fov = float(c["fov"])
	root.add_child(_camera)
	_camera.make_current()
	_camera.look_at_from_position(_v(c["eye"]), _v(c["look"]), UP)
	var layer: CanvasLayer = CanvasLayer.new()
	_label = Label.new()
	_label.position = Vector2(16, 10)
	_label.add_theme_font_size_override("font_size", 30)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 8)
	layer.add_child(_label)
	root.add_child(layer)
	_t = 0.0
	_apply(at(0.0))
	for i: int in 30:  # the probes, SSAO and glow settle
		await process_frame
	var fps: float = float(c["fps"])
	var count: int = int(SECONDS * fps)
	var dir: String = _out.path_join("frames")
	DirAccess.make_dir_recursive_absolute(dir)
	DirAccess.make_dir_recursive_absolute(_out.path_join("keys"))
	var key_frames: Dictionary = {}
	for kv: Array in KEYS:
		key_frames[int(round(float(kv[0]) * fps))] = kv[1]
	var tiles: Array = []
	var close_tiles: Array = []
	var zooms: Array = []
	var zoom_frames: Array = []
	for z: float in ZOOM:
		zoom_frames.append(int(round(z * fps)))
	var close_cam: Camera3D = null
	if c.has("close"):
		close_cam = Camera3D.new()
		close_cam.near = 0.05
		close_cam.far = 500.0
		close_cam.fov = float(c["fov"])
		root.add_child(close_cam)
		close_cam.look_at_from_position(_v(c["close"]["eye"]), _v(c["close"]["look"]), UP)
		DirAccess.make_dir_recursive_absolute(_out.path_join("close/frames"))
	var states: Array = []
	var started: int = Time.get_ticks_msec()
	for f: int in count:
		if f > 0:
			step(1.0 / fps)
		await RenderingServer.frame_post_draw
		var image: Image = root.get_texture().get_image()
		image.convert(Image.FORMAT_RGB8)
		_save(image, dir.path_join("%05d.png" % f))
		if zoom_frames.has(f):
			zooms.append(_zoom(image))
		var state: String = _pair["charger"]["state"]
		if states.is_empty() or states[-1][1] != state:
			states.append([snappedf(f / fps, 0.01), state])
		if key_frames.has(f):
			_label.text = "%.1f s  %s" % [f / fps, key_frames[f]]
			await RenderingServer.frame_post_draw
			var shot: Image = root.get_texture().get_image()
			shot.convert(Image.FORMAT_RGB8)
			_save(shot, _out.path_join("keys/%05d.png" % f))
			shot.resize(640, 360, Image.INTERPOLATE_LANCZOS)
			tiles.append(shot)
			_label.text = ""
		if close_cam != null:
			close_cam.make_current()
			_label.text = ("%.1f s  %s" % [f / fps, key_frames[f]]) if key_frames.has(f) else ""
			await RenderingServer.frame_post_draw
			var near: Image = root.get_texture().get_image()
			near.convert(Image.FORMAT_RGB8)
			_save(near, _out.path_join("close/frames/%05d.png" % f))
			if key_frames.has(f):
				near.resize(640, 360, Image.INTERPOLATE_LANCZOS)
				close_tiles.append(near)
			_label.text = ""
			_camera.make_current()
	var sheet: Image = Image.create(1280, 360 * ceili(tiles.size() / 2.0), false, Image.FORMAT_RGB8)
	for i: int in tiles.size():
		sheet.blit_rect(tiles[i], Rect2i(0, 0, 640, 360), Vector2i((i % 2) * 640, (i / 2) * 360))
	_save(sheet, _out.path_join("keys_sheet.png"))
	if not close_tiles.is_empty():
		_save(_two_up(close_tiles), _out.path_join("close/keys_sheet.png"))
	if not zooms.is_empty():
		_save(_two_up(zooms), _out.path_join("zoom_sheet.png"))
	_write("cycle.json", {"frames": count, "fps": fps, "seconds": SECONDS, "lights": lights, "states": states,
		"trace_surfaces": _pair.get("traces", 0), "conduit_surfaces": _pair.get("conduits", 0),
		"arc_frames": _arc_frames, "arc_ends_off": _zap_bad,
		"keys": KEYS, "render_s": (Time.get_ticks_msec() - started) / 1000.0})
	print("CHARGER cycle %d frames" % count)
	quit(0)


## Tiles of 640x360 two to a row.
static func _two_up(tiles: Array) -> Image:
	var sheet: Image = Image.create(1280, 360 * ceili(tiles.size() / 2.0), false, Image.FORMAT_RGB8)
	for i: int in tiles.size():
		sheet.blit_rect(tiles[i], Rect2i(0, 0, 640, 360), Vector2i((i % 2) * 640, (i / 2) * 360))
	return sheet


## The frame cropped to ZOOM_CROP round the crystal's middle (its profile's mid height on its axis), scaled to 640x360.
func _zoom(image: Image) -> Image:
	var crystal: Node3D = _pair["crystal"]
	var p: Dictionary = Zap._profile(crystal)
	var mid: Vector3 = crystal.global_transform * Vector3(0.0, (float(p["min"]) + float(p["max"])) * 0.5, 0.0)
	var at: Vector2 = _camera.unproject_position(mid)
	var size: Vector2i = image.get_size()
	var x: int = clampi(int(at.x) - ZOOM_CROP.x / 2, 0, size.x - ZOOM_CROP.x)
	var y: int = clampi(int(at.y) - ZOOM_CROP.y / 2, 0, size.y - ZOOM_CROP.y)
	var crop: Image = image.get_region(Rect2i(Vector2i(x, y), ZOOM_CROP))
	crop.resize(640, 360, Image.INTERPOLATE_LANCZOS)
	return crop
