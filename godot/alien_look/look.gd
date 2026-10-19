extends SceneTree
## The alien's plasticine look in Godot 4.7.2 at game distance (art #196, step G3). Runs in a real window kept
## off-screen (godot/lib/offscreen.gd, #214; never headless, never minimized). No runner command starts it yet: a run
## goes through the runner's _godot.window() (docs/godot.md, "The off-screen window"), which adds
## `--position 30000,30000 --resolution 1x1` and `PRIME_WINDOW=<w>x<h>`, with the arguments
##   --path godot -s res://alien_look/look.gd -- <spec.json>
## Modes: "shots", "bench", "grid" (G3's tuning grid of the micro-detail's gain), "calib", "cells", "sheets_b".
## The spec names the staged character GLB (res://), its 4096 clay sheets per clay strength (head and body, base colour
## and normal; loaded at run time, halved to the game's 2048, mipmapped and VRAM-compressed as the game imports them),
## the tiling micro-detail (normal and height) and the mode:
## - "shots": a present-day living-room box (a warm lamp, a cool window light, the approved look's AgX, sky ambient and
##   eye catch light, SSAO, soft shadows, SSS) and the face and body shots per material option and clay strength,
##   composed into face.png and body.png beside the target frames (spec "f2a", "f1a");
## - "bench": the bench stage of godot/bench/bench.gd (10 copies in a meeting ring playing Idle, a sun with 4 shadow
##   splits, a shadowed omni lamp, 1920x1080) and the median GPU and CPU ms per material option, in rounds.
## The material options (OPTIONS): "A" the export's StandardMaterial3D as imported; "B" a tuned StandardMaterial3D
## (roughness, a low specular, rim, SSS in skin mode; no micro-detail: StandardMaterial3D's detail map has no tiling
## of its own); "C" alien_clay.gdshader (the micro-detail tiled in UV space); "D" alien_clay_tri.gdshader (triplanar
## in model space). B to D give the eyes a StandardMaterial3D at roughness 0.3 with a clear coat for a sharp glint.
## Step G3b adds (art #196): option "C2" (alien_clay_mix.gdshader, the tile's repetition broken; the recommended one) and
## three modes, all under the approved look (exposure 0.9, no saturation adjustment):
## - "calib": the base colour's per-region (teal, pale, coral) correction, found by rendering the face at 0.6 m with the
##   calibration shader (a linear colour matrix) until each region's lit-half mean matches f2a's; region masks come from
##   an ID render (the matrix mapping the palette to red, green and blue) against the empty room; calib.json, calib.png;
## - "cells": G3's 0.6 m 3/4 camera zoomed onto one pixel (the lid-corner fringe), one cell per override set;
## - "sheets_b": before (G3's C at clay 2) against after (C2 on the corrected sheets) beside f2a and f1a, face_b.png,
##   body_b.png and the region means against both targets, sheets_b.json.
## Prints LOOK saved <path>, or LOOK error <why> and exits 1.

const Character = preload("res://lib/character.gd")
const Offscreen = preload("res://lib/offscreen.gd")
const SHADER_UV: Shader = preload("res://alien_look/alien_clay.gdshader")
const SHADER_TRI: Shader = preload("res://alien_look/alien_clay_tri.gdshader")
const SHADER_MIX: Shader = preload("res://alien_look/alien_clay_mix.gdshader")  # G3b: C with the tile mixed (C2)
const SHADER_CAL: Shader = preload("res://alien_look/alien_clay_cal.gdshader")  # G3b: C2 with a colour matrix
const REGION_NAMES: Array[String] = ["", "teal", "pale", "coral"]
const STEP: int = 2  # the region means read every second pixel
const WATCHDOG_S: float = 900.0
const EYE_LAYER: int = 1 << 19  # render layer 20: the eyes, the only thing the catch light lights (as the showroom)
const OPTIONS: Array[String] = ["A", "B", "C", "D"]
const OPTION_NAMES: Dictionary = {"A": "A import", "B": "B standard", "C": "C shader UV", "D": "D shader tri",
		"C2": "C2 UV mixed"}
const CELL: Vector2i = Vector2i(256, 320)

var _spec: Dictionary = {}
var _tex: Dictionary = {}  # "<clay>/<sheet>_<col|nrm>" -> Texture2D
var _micro_n: Texture2D
var _micro_h: Texture2D
var _imported: Dictionary = {}  # material name -> the imported BaseMaterial3D
var _copies: Array[Node3D] = []
var _env: Environment
var _label: Label
var _target_rect: TextureRect
var _camera: Camera3D
var _sun: DirectionalLight3D
var _lamp: OmniLight3D
var _fill: DirectionalLight3D
var _fix: Basis = Basis.IDENTITY  # G3b: the calibration shader's colour matrix (linear light)
var _white: Texture2D


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var placed: String = Offscreen.place()  # first: Godot opened the window at the screen's corner (#214)
	if placed != "":
		_fail(placed)
		return
	if args.size() < 1:
		_fail("usage: -- <spec.json>")
		return
	create_timer(WATCHDOG_S).timeout.connect(_fail.bind("not done within %d s" % WATCHDOG_S))
	var spec: Variant = Character.read_json(args[0])
	if not (spec is Dictionary and spec.has("mode") and spec.has("scene") and spec.has("tex")):
		_fail("%s is not a look spec" % args[0])
		return
	_spec = spec
	_run()


func _run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	await process_frame  # the root enters the tree only after _initialize: look_at needs it
	var t0: int = Time.get_ticks_msec()
	if not _load_textures():
		return
	print("LOOK textures loaded in %d ms" % (Time.get_ticks_msec() - t0))
	var packed: PackedScene = load(_spec["scene"]) as PackedScene
	if packed == null:
		_fail("cannot load %s" % _spec["scene"])
		return
	var out: String = _spec["out"]
	DirAccess.make_dir_recursive_absolute(out + "/shots")
	if _spec["mode"] == "bench":
		await _bench(packed, out)
	elif _spec["mode"] == "grid":
		await _grid(packed, out)
	elif _spec["mode"] == "calib":
		await _calib(packed, out)
	elif _spec["mode"] == "cells":
		await _cells(packed, out)
	elif _spec["mode"] == "sheets_b":
		await _sheets_b(packed, out)
	else:
		await _shots(packed, out)


# ------------------------------------------------------------------ textures and materials

func _image(path: String, normal: bool, half: bool) -> Texture2D:
	var img: Image = Image.load_from_file(path)
	if img == null or img.is_empty():
		return null
	img.convert(Image.FORMAT_RGB8)
	if half:
		img.shrink_x2()
	img.generate_mipmaps(normal)
	if normal:
		img.compress(Image.COMPRESS_S3TC, Image.COMPRESS_SOURCE_NORMAL)  # RG: BC5 (RGTC), as the import
	else:
		img.compress(Image.COMPRESS_S3TC, Image.COMPRESS_SOURCE_SRGB)
	return ImageTexture.create_from_image(img)


func _load_textures() -> bool:
	var half: bool = bool(_spec.get("half", true))
	for clay: String in (_spec["tex"] as Dictionary).keys():
		for key: String in (_spec["tex"][clay] as Dictionary).keys():
			var t: Texture2D = _image(_spec["tex"][clay][key], key.ends_with("nrm"), half)
			if t == null:
				_fail("cannot load %s" % _spec["tex"][clay][key])
				return false
			_tex["%s/%s" % [clay, key]] = t
	_micro_n = _image(_spec["micro_nrm"], true, false)
	_micro_h = _image(_spec["micro_height"], false, false)
	if _micro_n == null or _micro_h == null:
		_fail("cannot load the micro-detail textures")
		return false
	return true


func _sheet_of(mat_name: String) -> String:
	if mat_name.contains("head"):
		return "head"
	if mat_name.contains("skin") or mat_name.contains("body"):
		return "body"
	if mat_name.contains("eye"):
		return "eye"
	return ""


func _collect_imported(node: Node) -> void:
	for mi: MeshInstance3D in Character.meshes(node):
		for s: int in mi.mesh.get_surface_count():
			var m: Material = mi.mesh.surface_get_material(s)
			if m is BaseMaterial3D and not _imported.has(m.resource_name):
				_imported[m.resource_name] = m


## The material of one sheet ("head", "body", "eye") for an option and a clay strength.
func _material(sheet: String, option: String, clay: String) -> Material:
	var c: Dictionary = _spec["clay"][clay]
	var col: Texture2D = _tex.get("%s/%s_col" % [clay, sheet])
	var nrm: Texture2D = _tex.get("%s/%s_nrm" % [clay, sheet])
	var source: BaseMaterial3D = null
	for n: String in _imported.keys():
		if _sheet_of(n) == sheet:
			source = _imported[n]
	if sheet == "eye":
		if option == "A":
			return source
		var eye: StandardMaterial3D = StandardMaterial3D.new()
		eye.resource_name = "look_eye"
		eye.albedo_texture = source.albedo_texture if source != null else null
		eye.roughness = float(_spec["eye_roughness"])
		eye.metallic_specular = 0.5
		eye.clearcoat_enabled = true
		eye.clearcoat = 1.0
		eye.clearcoat_roughness = float(_spec["eye_clearcoat_roughness"])
		return eye
	if option == "A":
		var a: BaseMaterial3D = source.duplicate() as BaseMaterial3D
		a.albedo_texture = col
		a.normal_texture = nrm
		return a
	if option == "B":
		var b: StandardMaterial3D = StandardMaterial3D.new()
		b.resource_name = "look_%s_clay" % sheet
		b.albedo_texture = col
		b.normal_enabled = true
		b.normal_texture = nrm
		b.roughness = float(c["rough"])
		b.metallic_specular = float(_spec["specular"])
		b.rim_enabled = true
		b.rim = float(_spec["rim"])
		b.rim_tint = float(_spec["rim_tint"])
		b.subsurf_scatter_enabled = true
		b.subsurf_scatter_strength = float(_spec["sss"])
		b.subsurf_scatter_skin_mode = true
		b.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
		return b
	var sm: ShaderMaterial = ShaderMaterial.new()
	var shaders: Dictionary = {"C": SHADER_UV, "C2": SHADER_MIX, "CAL": SHADER_CAL, "CALW": SHADER_CAL}
	sm.shader = shaders.get(option, SHADER_TRI)
	if option == "CAL" or option == "CALW":
		var fx: Basis = _fix if option == "CAL" else Basis.IDENTITY
		sm.set_shader_parameter("fix_c0", fx.x)
		sm.set_shader_parameter("fix_c1", fx.y)
		sm.set_shader_parameter("fix_c2", fx.z)
	sm.set_shader_parameter("albedo_tex", col)
	sm.set_shader_parameter("normal_tex", nrm)
	sm.set_shader_parameter("micro_normal", _micro_n)
	sm.set_shader_parameter("micro_height", _micro_h)
	sm.set_shader_parameter("micro_uv_scale", float(_spec["uv_scale"][sheet]))
	sm.set_shader_parameter("micro_per_m", 1.0 / float(_spec["tile_m"]))
	sm.set_shader_parameter("micro_strength", float(c["micro"]) * float(_spec["micro_gain"]))
	sm.set_shader_parameter("roughness_base", float(c["rough"]))
	sm.set_shader_parameter("cavity", float(_spec["cavity"]))
	sm.set_shader_parameter("specular_level", float(_spec["specular"]))
	sm.set_shader_parameter("rim_amount", float(_spec["rim"]))
	sm.set_shader_parameter("rim_tint_amount", float(_spec["rim_tint"]))
	sm.set_shader_parameter("sss_strength", float(_spec["sss"]))
	sm.set_shader_parameter("normal_depth", float(_spec.get("normal_depth", 1.0)))
	if option == "CALW":  # the fringe check: a flat grey head and body, the shading and the geometry alone
		if _white == null:
			var wi: Image = Image.create(4, 4, false, Image.FORMAT_RGB8)
			wi.fill(Color(0.8, 0.8, 0.8))
			_white = ImageTexture.create_from_image(wi)
		sm.set_shader_parameter("albedo_tex", _white)
	return sm


## Puts one option at one clay strength on every copy: one material per sheet, shared by all copies.
func _apply(option: String, clay: String) -> void:
	var mats: Dictionary = {}
	for sheet: String in ["head", "body", "eye"]:
		mats[sheet] = _material(sheet, option, clay)
	RenderingServer.sub_surface_scattering_set_quality(RenderingServer.SUB_SURFACE_SCATTERING_QUALITY_DISABLED
			if option == "A" else RenderingServer.SUB_SURFACE_SCATTERING_QUALITY_MEDIUM)
	for node: Node3D in _copies:
		for mi: MeshInstance3D in Character.meshes(node):
			var eyes: bool = false
			for s: int in mi.mesh.get_surface_count():
				var src: Material = mi.mesh.surface_get_material(s)
				var sheet: String = _sheet_of(src.resource_name if src != null else "")
				if sheet != "":
					mi.set_surface_override_material(s, mats[sheet])
				eyes = eyes or sheet == "eye"
			if eyes:
				mi.layers |= EYE_LAYER


# ------------------------------------------------------------------ the character

func _add_copy(packed: PackedScene, at: Vector3, face_to: Vector3) -> Node3D:
	var node: Node3D = packed.instantiate() as Node3D
	node.position = at
	root.add_child(node)
	if face_to != at:
		node.look_at(face_to, Vector3.UP, true)  # the model's front is +Z
	_copies.append(node)
	if _imported.is_empty():
		_collect_imported(node)
	return node


func _player(node: Node) -> AnimationPlayer:
	var players: Array[Node] = Character.nodes_of(node, "AnimationPlayer")
	return players[0] as AnimationPlayer if players.size() > 0 else null


func _clip(player: AnimationPlayer, want: String) -> String:
	if player.has_animation(want):
		return want
	for n: StringName in player.get_animation_list():
		if want.to_lower() in String(n).to_lower():
			return n
	return ""


func _pose(node: Node3D, want: String, frac: float) -> void:
	var player: AnimationPlayer = _player(node)
	var skel: Skeleton3D = Character.nodes_of(node, "Skeleton3D")[0] as Skeleton3D
	var clip: String = _clip(player, want)
	Character.pose_at(player, skel, clip, player.get_animation(clip).length * frac)


func _eyes_centre(node: Node3D) -> Vector3:
	var sum: Vector3 = Vector3.ZERO
	var n: int = 0
	for mi: MeshInstance3D in Character.meshes(node):
		if not String(mi.name).to_lower().contains("eye"):
			continue
		for p: Vector3 in Character.skinned_points(mi, 4):
			sum += p
			n += 1
	return sum / maxf(n, 1)


func _hips(node: Node3D) -> Vector3:
	var skel: Skeleton3D = Character.nodes_of(node, "Skeleton3D")[0] as Skeleton3D
	var b: int = skel.find_bone("Hips")
	return (skel.global_transform * skel.get_bone_global_pose(maxi(b, 0))).origin


# ------------------------------------------------------------------ shots

## The room's light settings from d (the spec, or one entry of the spec's light grid); a key it lacks keeps the spec's.
func _lights(d: Dictionary) -> void:
	var g: Dictionary = _spec.duplicate()
	g.merge(d, true)
	_env.tonemap_exposure = float(g["exposure"])
	_env.ambient_light_energy = float(g.get("ambient_energy", 0.12))
	_env.ambient_light_sky_contribution = float(g.get("sky_contribution", 0.5))
	if _sun != null:
		_sun.light_energy = float(g["window_energy"])
		var wc: Array = g.get("window_color", [0.80, 0.88, 1.0])
		_sun.light_color = Color(float(wc[0]), float(wc[1]), float(wc[2]))
	if _lamp != null:
		_lamp.light_energy = float(g["lamp_energy"])
	if _fill != null:
		_fill.light_energy = float(g.get("fill_energy", 0.0))
	var sat: float = float(g.get("saturation", 1.0))
	_env.adjustment_enabled = not is_equal_approx(sat, 1.0)
	_env.adjustment_saturation = sat


## The mean colour (the PNG's sRGB) of an image's teal pixels and of its pale (mint) pixels, with their counts.
func _palette(img: Image) -> Dictionary:
	var small: Image = img.duplicate() as Image
	small.convert(Image.FORMAT_RGB8)
	small.resize(128, 160, Image.INTERPOLATE_BILINEAR)
	var sums: Dictionary = {"teal": [Vector3.ZERO, 0], "pale": [Vector3.ZERO, 0]}
	for y: int in small.get_height():
		for x: int in small.get_width():
			var c: Color = small.get_pixel(x, y)
			var h: float = c.h * 360.0
			var key: String = ""
			if h > 150.0 and h < 200.0 and c.s > 0.3 and c.v > 0.15:
				key = "teal"
			elif h > 60.0 and h < 170.0 and c.s > 0.06 and c.s < 0.35 and c.v > 0.55:
				key = "pale"
			if key != "":
				sums[key][0] += Vector3(c.r, c.g, c.b)
				sums[key][1] += 1
	var out: Dictionary = {}
	for key: String in sums.keys():
		var n: int = sums[key][1]
		var m: Vector3 = sums[key][0] / maxf(n, 1)
		out[key] = [snappedf(m.x, 0.001), snappedf(m.y, 0.001), snappedf(m.z, 0.001), n]
	return out


## The light grid: per entry of the spec's "light_grid" the face at 0.6 m (3/4) and the body at 3 m, the best option
## at the middle clay strength, with the teal and pale means against f2a's and f1a's.
func _grid(packed: PackedScene, out: String) -> void:
	_room()
	var node: Node3D = _add_copy(packed, Vector3.ZERO, Vector3.ZERO)
	await process_frame
	_pose(node, "Idle", 0.0)
	await process_frame
	var face_at: Vector3 = _eyes_centre(node) + Vector3(0, -0.03, 0)
	var mid: String = str(int(_spec["mid_clay"]))
	_apply(_spec["best_option"], mid)
	var shots: Array[Image] = []
	var f2a: Image = await _target_shot(_spec["f2a"], [], "f2a target")
	var f1a: Image = await _target_shot(_spec["f1a"], _spec.get("f1a_region", []), "f1a target")
	var record: Dictionary = {"f2a": _palette(f2a), "f1a": _palette(f1a), "grid": []}
	shots.append(f2a)
	shots.append(f1a)
	var grid: Array = _spec["light_grid"]
	for i: int in grid.size():
		_lights(grid[i])
		_look(face_at, -30.0, 4.0, 0.6, float(_spec["face_fov"]))
		var fs: Image = await _shot("L%d face" % i)
		_look(Vector3(0, 0.93, 0), -25.0, 6.0, 3.0, 40.0)
		var bs: Image = await _shot("L%d body" % i)
		shots.append(fs)
		shots.append(bs)
		record["grid"].append({"light": grid[i], "face": _palette(fs), "body": _palette(bs)})
		print("LOOK grid L%d face %s body %s" % [i, record["grid"][i]["face"], record["grid"][i]["body"]])
	print("LOOK targets f2a %s f1a %s" % [record["f2a"], record["f1a"]])
	_save(_sheet(shots, 6), out + "/grid.png")
	Character.write_json(out + "/grid.json", record)
	print("LOOK saved ", out + "/grid.json")
	quit(0)


func _room() -> void:
	root.msaa_3d = Viewport.MSAA_4X
	_env = Environment.new()
	var sky: Sky = Sky.new()
	var psky: ProceduralSkyMaterial = ProceduralSkyMaterial.new()
	sky.sky_material = psky
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	_env.background_mode = Environment.BG_SKY
	_env.sky = sky
	_env.tonemap_mode = Environment.TONE_MAPPER_AGX
	_env.tonemap_exposure = float(_spec["exposure"])
	_env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	_env.ambient_light_sky_contribution = 0.5
	_env.ambient_light_color = Color(1.0, 0.8, 0.62)
	_env.ambient_light_energy = 0.12
	_env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	_env.ssao_enabled = true
	_env.ssao_radius = 0.6
	_env.ssao_intensity = 1.5
	_env.ssao_light_affect = 0.2
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = _env
	root.add_child(world)
	RenderingServer.directional_soft_shadow_filter_set_quality(RenderingServer.SHADOW_QUALITY_SOFT_HIGH)
	RenderingServer.positional_soft_shadow_filter_set_quality(RenderingServer.SHADOW_QUALITY_SOFT_HIGH)
	# the room: a 7 x 6 m box open at the camera's side, 2.7 m high; walls a warm off-white, a wooden floor, a rug
	_box(Vector3(0, -0.05, 0), Vector3(7, 0.1, 7), Color(0.42, 0.29, 0.19), 0.55, true)
	_box(Vector3(0, 0.005, 0.2), Vector3(2.8, 0.012, 2.0), Color(0.42, 0.38, 0.33), 1.0, true)
	_box(Vector3(0, 1.35, -3.0), Vector3(7, 2.7, 0.1), Color(0.62, 0.58, 0.53), 0.9, false)
	_box(Vector3(-3.5, 1.35, 0), Vector3(0.1, 2.7, 6), Color(0.60, 0.56, 0.51), 0.9, false)
	_box(Vector3(0, 2.75, 0), Vector3(7, 0.1, 6), Color(0.66, 0.64, 0.61), 0.9, false)
	# the right wall with a 2 x 1.5 m window (sill at 0.8 m) the cool daylight comes through
	_box(Vector3(3.5, 0.4, 0), Vector3(0.1, 0.8, 6), Color(0.60, 0.56, 0.51), 0.9, false)
	_box(Vector3(3.5, 2.5, 0), Vector3(0.1, 0.4, 6), Color(0.60, 0.56, 0.51), 0.9, false)
	_box(Vector3(3.5, 1.5, -2.0), Vector3(0.1, 1.4, 2.0), Color(0.60, 0.56, 0.51), 0.9, false)
	_box(Vector3(3.5, 1.5, 2.0), Vector3(0.1, 1.4, 2.0), Color(0.60, 0.56, 0.51), 0.9, false)
	# furniture blocks for depth: a sofa at the back left, a low cabinet at the right
	_box(Vector3(-1.6, 0.4, -2.3), Vector3(2.2, 0.8, 0.9), Color(0.55, 0.53, 0.50), 1.0, true)
	_box(Vector3(2.2, 0.35, -2.5), Vector3(1.4, 0.7, 0.45), Color(0.45, 0.30, 0.18), 0.6, true)
	# the cool window light: the key, from the window (right, front, up)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	_sun = sun
	root.add_child(sun)
	sun.look_at_from_position(Vector3(3.0, 2.6, 2.2), Vector3(0, 1.0, 0))
	sun.light_color = Color(0.80, 0.88, 1.0)
	sun.light_energy = float(_spec["window_energy"])
	sun.light_specular = 0.6
	sun.shadow_enabled = true
	sun.light_angular_distance = 1.5
	sun.directional_shadow_max_distance = 12.0
	# the warm lamp: a floor lamp at the front left with a glowing shade
	var lamp: OmniLight3D = OmniLight3D.new()
	_lamp = lamp
	lamp.position = Vector3(-1.5, 1.55, 1.1)
	lamp.light_color = Color(1.0, 0.70, 0.45)
	lamp.light_energy = float(_spec["lamp_energy"])
	lamp.omni_range = 7.0
	lamp.omni_attenuation = 1.0
	lamp.light_size = 0.2
	lamp.light_specular = 0.5
	lamp.shadow_enabled = true
	root.add_child(lamp)
	var shade: MeshInstance3D = MeshInstance3D.new()
	var cyl: CylinderMesh = CylinderMesh.new()
	cyl.top_radius = 0.18
	cyl.bottom_radius = 0.22
	cyl.height = 0.3
	var sm: StandardMaterial3D = StandardMaterial3D.new()
	sm.albedo_color = Color(1.0, 0.9, 0.75)
	sm.emission_enabled = true
	sm.emission = Color(1.0, 0.72, 0.45)
	sm.emission_energy_multiplier = 2.0
	cyl.material = sm
	shade.mesh = cyl
	shade.position = lamp.position
	shade.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(shade)
	# a weak warm rim from behind, as the approved look's rim light
	var rim: DirectionalLight3D = DirectionalLight3D.new()
	root.add_child(rim)
	rim.look_at_from_position(Vector3(-0.5, 2.5, -3.0), Vector3(0, 0.9, 0))
	rim.light_color = Color(1.0, 0.85, 0.7)
	rim.light_energy = 0.3
	rim.light_specular = 0.0
	# a soft neutral fill from the camera's left (the room's bounce light)
	_fill = DirectionalLight3D.new()
	root.add_child(_fill)
	_fill.look_at_from_position(Vector3(-2.5, 1.8, 2.5), Vector3(0, 1.0, 0))
	_fill.light_energy = 0.0
	_fill.light_specular = 0.0
	_lights(_spec)
	_camera = Camera3D.new()
	_camera.near = 0.03
	_camera.far = 60.0
	root.add_child(_camera)
	_camera.make_current()
	var catch: OmniLight3D = OmniLight3D.new()  # the approved look's eye catch light
	_camera.add_child(catch)
	catch.position = Vector3(-0.25, 0.3, 0.0)
	catch.light_cull_mask = EYE_LAYER
	catch.omni_range = 50.0
	catch.omni_attenuation = 0.0
	catch.light_size = 0.06
	catch.light_energy = 0.6
	catch.light_specular = 16.0
	_overlay()


func _overlay() -> void:
	var layer: CanvasLayer = CanvasLayer.new()
	root.add_child(layer)
	_target_rect = TextureRect.new()
	_target_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_target_rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_target_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	_target_rect.visible = false
	layer.add_child(_target_rect)
	_label = Label.new()
	_label.position = Vector2(12, 8)
	_label.add_theme_font_size_override("font_size", 34)
	_label.add_theme_color_override("font_color", Color(1, 1, 1))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 8)
	layer.add_child(_label)


func _box(at: Vector3, size: Vector3, colour: Color, rough: float, casts: bool) -> void:
	var mi: MeshInstance3D = MeshInstance3D.new()
	var bm: BoxMesh = BoxMesh.new()
	bm.size = size
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.albedo_color = colour
	m.roughness = rough
	bm.material = m
	mi.mesh = bm
	mi.position = at
	mi.cast_shadow = (GeometryInstance3D.SHADOW_CASTING_SETTING_ON if casts
			else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF)
	root.add_child(mi)


func _look(target: Vector3, yaw_deg: float, pitch_deg: float, dist: float, fov: float) -> void:
	var yaw: float = deg_to_rad(yaw_deg)
	var pitch: float = deg_to_rad(pitch_deg)
	var back: Vector3 = Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch))
	_camera.fov = fov
	_camera.look_at_from_position(target + back * dist, target, Vector3.UP)


func _shot(text: String) -> Image:
	_label.text = text
	for _i: int in 4:
		await process_frame
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	return root.get_texture().get_image()


func _target_shot(path: String, region: Array, text: String) -> Image:
	var img: Image = Image.load_from_file(path)
	if img == null or img.is_empty():
		return Image.create(CELL.x, CELL.y, false, Image.FORMAT_RGB8)
	var tex: Texture2D = ImageTexture.create_from_image(img)
	if region.size() == 4:
		var at: AtlasTexture = AtlasTexture.new()
		at.atlas = tex
		at.region = Rect2(region[0], region[1], region[2], region[3])
		tex = at
	_target_rect.texture = tex
	_target_rect.visible = true
	var shot: Image = await _shot(text)
	_target_rect.visible = false
	return shot


func _shots(packed: PackedScene, out: String) -> void:
	_room()
	var node: Node3D = _add_copy(packed, Vector3.ZERO, Vector3.ZERO)
	await process_frame
	var face: Array[Image] = []
	var body: Array[Image] = []
	var clays: Array = _spec["clays"]
	var best: String = _spec["best_option"]
	var mid: String = str(int(_spec["mid_clay"]))
	# Idle at its start for every face and body shot
	_pose(node, "Idle", 0.0)
	await process_frame
	var eyes: Vector3 = _eyes_centre(node)
	var face_at: Vector3 = eyes + Vector3(0, float(_spec.get("face_lift", 0.0)), 0)
	print("LOOK eyes centre ", eyes)
	# face row 1: f2a, then every option at the middle clay strength, 0.6 m, 3/4
	face.append(await _target_shot(_spec["f2a"], [], "f2a target"))
	for opt: String in OPTIONS:
		_apply(opt, mid)
		_look(face_at, -30.0, 4.0, 0.6, float(_spec["face_fov"]))
		face.append(await _shot("%s c%s 0.6m" % [OPTION_NAMES[opt], mid]))
	# face rows 2-4: the best option at each clay strength
	for clay: Variant in clays:
		var cs: String = str(int(clay))
		_apply(best, cs)
		var views: Array = [[face_at, 0.0, 4.0, 0.6, float(_spec["face_fov"]), "0.6m front"],
				[face_at, -30.0, 4.0, 0.6, float(_spec["face_fov"]), "0.6m 3/4"],
				[face_at + Vector3(0, -0.2, 0), 0.0, 3.0, 1.5, 40.0, "1.5m front"],
				[face_at + Vector3(0, -0.2, 0), -30.0, 3.0, 1.5, 40.0, "1.5m 3/4"],
				[eyes + Vector3(-0.05, -0.06, 0.05), -35.0, 6.0, 0.5, 22.0, "0.5m close"]]
		for v: Array in views:
			_look(v[0], v[1], v[2], v[3], v[4])
			var img: Image = await _shot("%s c%s %s" % [best, cs, v[5]])
			face.append(img)
			if cs == mid and v[5] == "0.5m close":
				img.save_png(out + "/shots/face_close_c%s.png" % cs)
			if cs == mid and v[5] == "0.6m 3/4":
				img.save_png(out + "/shots/face_06_c%s.png" % cs)
	# the micro-detail's gain at the middle clay strength (spec "gain_row"), 0.6 m 3/4, the last also at 0.5 m
	var keep_gain: float = float(_spec["micro_gain"])
	var gains: Array = _spec.get("gain_row", [])
	for i: int in gains.size():
		_spec["micro_gain"] = float(gains[i])
		_apply(best, mid)
		_look(face_at, -30.0, 4.0, 0.6, float(_spec["face_fov"]))
		face.append(await _shot("%s c%s gain %.1f 0.6m" % [best, mid, float(gains[i])]))
		if i == gains.size() - 1:
			_look(eyes + Vector3(-0.05, -0.06, 0.05), -35.0, 6.0, 0.5, 22.0)
			face.append(await _shot("%s c%s gain %.1f 0.5m" % [best, mid, float(gains[i])]))
	_spec["micro_gain"] = keep_gain
	_save(_sheet(face, 5), out + "/face.png")
	# body: f1a, the best option at each clay strength, the other options at the middle one; 3 m, 3/4, Idle
	var f1a_region: Array = _spec.get("f1a_region", [])
	body.append(await _target_shot(_spec["f1a"], f1a_region, "f1a target"))
	var body_at: Vector3 = Vector3(0, 0.93, 0)
	for clay: Variant in clays:
		_apply(best, str(int(clay)))
		_look(body_at, -25.0, 6.0, 3.0, 40.0)
		body.append(await _shot("%s c%d 3m Idle" % [best, int(clay)]))
	for opt: String in OPTIONS:
		if opt == best:
			continue
		_apply(opt, mid)
		_look(body_at, -25.0, 6.0, 3.0, 40.0)
		body.append(await _shot("%s c%s 3m Idle" % [OPTION_NAMES[opt], mid]))
	_apply(best, mid)
	_look(body_at, 0.0, 6.0, 3.0, 40.0)
	body.append(await _shot("%s c%s 3m front Idle" % [best, mid]))
	_pose(node, "Idle", 0.5)
	await process_frame
	_look(body_at, -25.0, 6.0, 3.0, 40.0)
	body.append(await _shot("%s c%s Idle 50%%" % [best, mid]))
	_pose(node, "Jog", 0.3)
	await process_frame
	var hips: Vector3 = _hips(node)
	_look(Vector3(hips.x, 0.93, hips.z), -25.0, 6.0, 3.0, 40.0)
	var jog: Image = await _shot("%s c%s Jog_Fwd 30%%" % [best, mid])
	body.append(jog)
	_save(_sheet(body, 5), out + "/body.png")
	print("LOOK saved ", out + "/face.png")
	quit(0)


func _sheet(shots: Array[Image], cols: int) -> Image:
	var rows: int = ceili(shots.size() / float(cols))
	var sheet: Image = Image.create(CELL.x * cols, CELL.y * rows, false, Image.FORMAT_RGB8)
	sheet.fill(Color(1, 1, 1))
	for i: int in shots.size():
		var img: Image = shots[i].duplicate() as Image
		img.convert(Image.FORMAT_RGB8)
		img.resize(CELL.x, CELL.y, Image.INTERPOLATE_LANCZOS)
		sheet.blit_rect(img, Rect2i(Vector2i.ZERO, CELL), Vector2i((i % cols) * CELL.x, (i / cols) * CELL.y))
	return sheet


func _save(img: Image, path: String) -> void:
	if img.save_png(path) != OK:
		_fail("cannot write %s" % path)


# ------------------------------------------------------------------ G3b: colour calibration, region means, fringe

func _lin(c: float) -> float:
	return c / 12.92 if c <= 0.04045 else pow((c + 0.055) / 1.055, 2.4)


## The bake's palette (spec "palette", sRGB: teal, pale, coral) in linear light.
func _palette_lin() -> Array[Vector3]:
	var out: Array[Vector3] = []
	for k: String in ["teal", "pale", "coral"]:
		var c: Array = _spec["palette"][k]
		out.append(Vector3(_lin(float(c[0])), _lin(float(c[1])), _lin(float(c[2]))))
	return out


## The colour matrix (linear light) that takes the palette to the palette times the per-region multipliers.
func _fix_matrix(mult: Array) -> Basis:
	var p: Array[Vector3] = _palette_lin()
	var src: Basis = Basis(p[0], p[1], p[2])
	return Basis(p[0] * (mult[0] as Vector3), p[1] * (mult[1] as Vector3), p[2] * (mult[2] as Vector3)) * src.inverse()


## The region ID matrix: teal to red, pale to green, coral to blue (each 0.6).
func _id_matrix() -> Basis:
	var p: Array[Vector3] = _palette_lin()
	return Basis(Vector3(0.6, 0, 0), Vector3(0, 0.6, 0), Vector3(0, 0, 0.6)) * Basis(p[0], p[1], p[2]).inverse()


func _eyes_black(node: Node3D) -> void:
	var black: StandardMaterial3D = StandardMaterial3D.new()
	black.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	black.albedo_color = Color(0, 0, 0)
	for mi: MeshInstance3D in Character.meshes(node):
		for s: int in mi.mesh.get_surface_count():
			var src: Material = mi.mesh.surface_get_material(s)
			if _sheet_of(src.resource_name if src != null else "") == "eye":
				mi.set_surface_override_material(s, black)


func _eyes_shown(node: Node3D, on: bool) -> void:
	for mi: MeshInstance3D in Character.meshes(node):
		if String(mi.name).to_lower().contains("eye"):
			mi.visible = on


## One eye's centre: the eye mesh's points on the side sgn (+1: the character's left, +X).
func _eye_side(node: Node3D, sgn: float) -> Vector3:
	var sum: Vector3 = Vector3.ZERO
	var n: int = 0
	for mi: MeshInstance3D in Character.meshes(node):
		if not String(mi.name).to_lower().contains("eye"):
			continue
		for p: Vector3 in Character.skinned_points(mi, 2):
			if p.x * sgn > 0.0:
				sum += p
				n += 1
	return sum / maxf(n, 1)


## Per view (an array of _look arguments) the region of each pixel (0 none, 1 teal, 2 pale, 3 coral) from an ID
## render (the calibration shader with the ID matrix on clay's sheets, the eyes black) against the empty room.
func _view_regions(node: Node3D, views: Array, clay: String) -> Array:
	var out: Array = []
	var keep: Basis = _fix
	_fix = _id_matrix()
	for v: Array in views:
		_look(v[0], v[1], v[2], v[3], v[4])
		node.visible = false
		var empty: Image = await _shot("")
		node.visible = true
		_apply("CAL", clay)
		_eyes_black(node)
		var idi: Image = await _shot("")
		var w: int = idi.get_width()
		var reg: PackedByteArray = PackedByteArray()
		reg.resize(w * idi.get_height())
		reg.fill(0)
		for y: int in range(0, idi.get_height(), STEP):
			for x: int in range(0, w, STEP):
				var c: Color = idi.get_pixel(x, y)
				var e: Color = empty.get_pixel(x, y)
				if absf(c.r - e.r) + absf(c.g - e.g) + absf(c.b - e.b) < 0.06:
					continue
				var hi: float = maxf(c.r, maxf(c.g, c.b))
				if hi < 0.08:
					continue
				if c.r == hi and c.r > 1.4 * maxf(c.g, c.b):
					reg[y * w + x] = 1
				elif c.g == hi and c.g > 1.4 * maxf(c.r, c.b):
					reg[y * w + x] = 2
				elif c.b == hi and c.b > 1.4 * maxf(c.r, c.g):
					reg[y * w + x] = 3
		out.append(reg)
	_fix = keep
	return out


func _collect(img: Image, reg: PackedByteArray, cols: Array, lum: Array) -> void:
	var w: int = img.get_width()
	for y: int in range(0, img.get_height(), STEP):
		for x: int in range(0, w, STEP):
			var k: int = reg[y * w + x]
			if k == 0:
				continue
			var c: Color = img.get_pixel(x, y)
			cols[k].append(Vector3(c.r, c.g, c.b))
			lum[k].append(0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b)


## Per region the mean sRGB colour of all its pixels and of its lit half (luma above the region's median), with counts.
func _summarise(cols: Array, lum: Array) -> Dictionary:
	var out: Dictionary = {}
	for k: int in range(1, 4):
		var n: int = cols[k].size()
		if n == 0:
			out[REGION_NAMES[k]] = {"all": [0, 0, 0, 0], "lit": [0, 0, 0, 0]}
			continue
		var sorted: Array = (lum[k] as Array).duplicate()
		sorted.sort()
		var med: float = sorted[n / 2]
		var sa: Vector3 = Vector3.ZERO
		var sl: Vector3 = Vector3.ZERO
		var nl: int = 0
		for i: int in n:
			var v: Vector3 = cols[k][i]
			sa += v
			if float(lum[k][i]) >= med:
				sl += v
				nl += 1
		sa /= n
		sl /= maxi(nl, 1)
		out[REGION_NAMES[k]] = {"all": [snappedf(sa.x, 0.001), snappedf(sa.y, 0.001), snappedf(sa.z, 0.001), n],
				"lit": [snappedf(sl.x, 0.001), snappedf(sl.y, 0.001), snappedf(sl.z, 0.001), nl]}
	return out


func _views_means(views: Array, regs: Array) -> Dictionary:
	var cols: Array = [[], [], [], []]
	var lum: Array = [[], [], [], []]
	for i: int in views.size():
		var v: Array = views[i]
		_look(v[0], v[1], v[2], v[3], v[4])
		_collect(await _shot(""), regs[i], cols, lum)
	return _summarise(cols, lum)


## A target frame's region means, by hue (teal, pale mint, coral) inside its region and left of x_max (a fraction).
func _target_means(path: String, region: Array, x_max: float) -> Dictionary:
	var img: Image = Image.load_from_file(path)
	img.convert(Image.FORMAT_RGB8)
	if region.size() == 4:
		img = img.get_region(Rect2i(int(region[0]), int(region[1]), int(region[2]), int(region[3])))
	var cols: Array = [[], [], [], []]
	var lum: Array = [[], [], [], []]
	for y: int in range(0, img.get_height(), STEP):
		for x: int in range(0, int(img.get_width() * x_max), STEP):
			var c: Color = img.get_pixel(x, y)
			var h: float = c.h * 360.0
			var k: int = 0
			if h > 150.0 and h < 215.0 and c.s > 0.25 and c.v > 0.15:
				k = 1
			elif h > 60.0 and h < 175.0 and c.s > 0.06 and c.s < 0.38 and c.v > 0.45:
				k = 2
			elif (h < 20.0 or h > 340.0) and c.s > 0.35 and c.v > 0.4:
				k = 3
			if k > 0:
				cols[k].append(Vector3(c.r, c.g, c.b))
				lum[k].append(0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b)
	return _summarise(cols, lum)


func _face_views(face_at: Vector3) -> Array:
	var fov: float = float(_spec["face_fov"])
	return [[face_at, -30.0, 4.0, 0.6, fov], [face_at, 0.0, 4.0, 0.6, fov]]


## The colour calibration (spec "iterations"): the calibration shader's per-region multipliers are moved until the face
## at 0.6 m (3/4 and front) matches f2a's lit-half region means under the approved look; then the fringe checks.
func _calib(packed: PackedScene, out: String) -> void:
	_room()
	var node: Node3D = _add_copy(packed, Vector3.ZERO, Vector3.ZERO)
	await process_frame
	_pose(node, "Idle", 0.0)
	await process_frame
	var eyes: Vector3 = _eyes_centre(node)
	var face_at: Vector3 = eyes + Vector3(0, float(_spec.get("face_lift", 0.0)), 0)
	var mid: String = str(int(_spec["mid_clay"]))
	var views: Array = _face_views(face_at)
	var regs: Array = await _view_regions(node, views, mid)
	var tgt: Dictionary = _target_means(_spec["f2a"], [], float(_spec.get("f2a_xmax", 0.85)))
	var record: Dictionary = {"target_f2a": tgt, "iterations": []}
	_apply("C", mid)
	record["before"] = await _views_means(views, regs)
	print("LOOK before %s" % [record["before"]])
	print("LOOK target %s" % [tgt])
	var mult: Array = [Vector3.ONE, Vector3.ONE, Vector3.ONE]
	var p: Array[Vector3] = _palette_lin()
	var iters: int = int(_spec.get("iterations", 6))
	for it: int in iters:
		_fix = _fix_matrix(mult)
		_apply("CAL", mid)
		var m: Dictionary = await _views_means(views, regs)
		var row: Dictionary = {"mult": [], "means": m}
		for k: int in 3:
			var mv: Vector3 = mult[k]
			row["mult"].append([snappedf(mv.x, 0.0001), snappedf(mv.y, 0.0001), snappedf(mv.z, 0.0001)])
		record["iterations"].append(row)
		print("LOOK iter %d mult %s lit teal %s pale %s coral %s" % [it, row["mult"], m["teal"]["lit"], m["pale"]["lit"],
				m["coral"]["lit"]])
		if it == iters - 1:
			break
		for k: int in 3:
			var r: Array = m[REGION_NAMES[k + 1]]["lit"]
			var t: Array = tgt[REGION_NAMES[k + 1]]["lit"]
			if int(r[3]) < 50 or int(t[3]) < 50:
				continue
			var f: Vector3 = Vector3(_lin(t[0]) / maxf(_lin(r[0]), 1e-4), _lin(t[1]) / maxf(_lin(r[1]), 1e-4),
					_lin(t[2]) / maxf(_lin(r[2]), 1e-4)).clamp(Vector3.ONE * 0.5, Vector3.ONE * 2.0)
			var nm: Vector3 = (mult[k] as Vector3) * f
			for ch: int in 3:
				nm[ch] = minf(nm[ch], 0.92 / maxf(p[k][ch], 1e-4))
			mult[k] = nm
	var last: Array = record["iterations"][-1]["mult"]
	var fin: Array = []
	for k: int in 3:
		fin.append(Vector3(float(last[k][0]), float(last[k][1]), float(last[k][2])))
	var fx: Basis = _fix_matrix(fin)
	var newpal: Dictionary = {}
	for k: int in 3:
		var c: Vector3 = p[k] * (fin[k] as Vector3)
		newpal[REGION_NAMES[k + 1]] = [c.x, c.y, c.z]
	record["final"] = {"mult": last, "matrix_columns_linear": [[fx.x.x, fx.x.y, fx.x.z],
			[fx.y.x, fx.y.y, fx.y.z], [fx.z.x, fx.z.y, fx.z.z]], "palette_linear": newpal}
	# the sheet: f2a, before, after; the fringe at the left eye's inner corner (normal, a flat grey skin, eyes hidden)
	var shots: Array[Image] = []
	shots.append(await _target_shot(_spec["f2a"], [], "f2a target"))
	_apply("C", mid)
	_look(face_at, -30.0, 4.0, 0.6, float(_spec["face_fov"]))
	shots.append(await _shot("G3 C c2 exp 0.9"))
	_fix = fx
	_apply("CAL", mid)
	shots.append(await _shot("calibrated c2"))
	var el: Vector3 = _eye_side(node, 1.0)
	var er: Vector3 = _eye_side(node, -1.0)
	record["eye_centres"] = [[el.x, el.y, el.z], [er.x, er.y, er.z]]
	var corner: Array = _spec.get("corner", [-0.04, -0.015, 0.035])
	var cl: Vector3 = el + Vector3(float(corner[0]), float(corner[1]), float(corner[2]))
	var cr: Vector3 = er + Vector3(-float(corner[0]), float(corner[1]), float(corner[2]))
	var cells: Array = [["CAL", true, cl, -30.0, "L corner"], ["CALW", true, cl, -30.0, "L flat grey"],
			["CAL", false, cl, -30.0, "L eyes hidden"], ["CAL", true, cl, 0.0, "L corner front"],
			["CAL", true, cr, 30.0, "R corner mirror"]]
	for c: Array in cells:
		_apply(c[0], mid)
		_eyes_shown(node, c[1])
		_look(c[2], c[3], 4.0, float(_spec.get("corner_dist", 0.25)), 30.0)
		var img: Image = await _shot(c[4])
		img.save_png(out + "/shots/%s.png" % String(c[4]).replace(" ", "_"))
		shots.append(img)
		_eyes_shown(node, true)
	_save(_sheet(shots, 4), out + "/calib.png")
	Character.write_json(out + "/calib.json", record)
	print("LOOK saved ", out + "/calib.json")
	quit(0)


## Step G3b's sheets: before (spec "before": [option, clay key], G3's C at clay 2) against after (spec "after") under
## the approved look, beside f2a and f1a, with the region means (lit half and all) against the targets.
func _sheets_b(packed: PackedScene, out: String) -> void:
	_room()
	var node: Node3D = _add_copy(packed, Vector3.ZERO, Vector3.ZERO)
	await process_frame
	_pose(node, "Idle", 0.0)
	await process_frame
	var eyes: Vector3 = _eyes_centre(node)
	var face_at: Vector3 = eyes + Vector3(0, float(_spec.get("face_lift", 0.0)), 0)
	var bef: Array = _spec["before"]
	var aft: Array = _spec["after"]
	var id_clay: String = str(bef[1])
	var fviews: Array = _face_views(face_at)
	var body_at: Vector3 = Vector3(0, 0.93, 0)
	var bviews: Array = [[body_at, -25.0, 6.0, 3.0, 40.0]]
	var fregs: Array = await _view_regions(node, fviews, id_clay)
	var bregs: Array = await _view_regions(node, bviews, id_clay)
	var record: Dictionary = {"f2a": _target_means(_spec["f2a"], [], float(_spec.get("f2a_xmax", 0.85))),
			"f1a": _target_means(_spec["f1a"], _spec.get("f1a_region", []), 1.0)}
	for pair: Array in [["before", bef], ["after", aft]]:
		_apply(str(pair[1][0]), str(pair[1][1]))
		record[pair[0]] = {"face": await _views_means(fviews, fregs), "body": await _views_means(bviews, bregs)}
		print("LOOK %s %s" % [pair[0], record[pair[0]]])
	print("LOOK targets f2a %s f1a %s" % [record["f2a"], record["f1a"]])
	var el: Vector3 = _eye_side(node, 1.0)
	var corner: Array = _spec.get("corner", [-0.04, -0.015, 0.035])
	var cl: Vector3 = el + Vector3(float(corner[0]), float(corner[1]), float(corner[2]))
	var fov: float = float(_spec["face_fov"])
	var close: Vector3 = eyes + Vector3(-0.05, -0.06, 0.05)
	var face_cells: Array = [[face_at, -30.0, 4.0, 0.6, fov, "0.6m 3/4"], [face_at, 0.0, 4.0, 0.6, fov, "0.6m front"],
			[close, -35.0, 6.0, 0.5, 22.0, "0.5m close"], [cl, -30.0, 4.0, 0.25, 30.0, "lid corner"],
			[face_at + Vector3(0, -0.2, 0), -30.0, 3.0, 1.5, 40.0, "1.5m 3/4"],
			[eyes + Vector3(0.07, 0.07, -0.02), -60.0, 10.0, 0.35, 30.0, "tile 0.35m crest"],
			[Vector3(0, 1.3, 0.08), -15.0, 4.0, 0.4, 35.0, "tile 0.4m chest"]]
	var face: Array[Image] = [await _target_shot(_spec["f2a"], [], "f2a target")]
	var blank: Image = Image.create(CELL.x, CELL.y, false, Image.FORMAT_RGB8)
	blank.fill(Color(1, 1, 1))
	face.append(blank)
	for c: Array in face_cells:
		for pair: Array in [["before", bef], ["after", aft]]:
			_apply(str(pair[1][0]), str(pair[1][1]))
			_look(c[0], c[1], c[2], c[3], c[4])
			var img: Image = await _shot("%s %s" % [pair[0], c[5]])
			face.append(img)
			if c[5] == "0.6m 3/4" or c[5] == "lid corner" or String(c[5]).begins_with("tile"):
				img.save_png(out + "/shots/%s_%s.png" % [pair[0], String(c[5]).replace(" ", "_").replace("/", "")])
	_save(_sheet(face, 4), out + "/face_b.png")
	var body: Array[Image] = [await _target_shot(_spec["f1a"], _spec.get("f1a_region", []), "f1a target")]
	for pair: Array in [["before", bef], ["after", aft]]:
		_apply(str(pair[1][0]), str(pair[1][1]))
		_look(body_at, -25.0, 6.0, 3.0, 40.0)
		body.append(await _shot("%s 3m 3/4 Idle" % pair[0]))
	_look(body_at, 0.0, 6.0, 3.0, 40.0)
	body.append(await _shot("after 3m front Idle"))
	_pose(node, "Idle", 0.5)
	await process_frame
	_look(body_at, -25.0, 6.0, 3.0, 40.0)
	body.append(await _shot("after Idle 50%"))
	_pose(node, "Jog", 0.3)
	await process_frame
	var hips: Vector3 = _hips(node)
	_look(Vector3(hips.x, 0.93, hips.z), -25.0, 6.0, 3.0, 40.0)
	body.append(await _shot("after Jog_Fwd 30%"))
	_save(_sheet(body, 3), out + "/body_b.png")
	Character.write_json(out + "/sheets_b.json", record)
	print("LOOK saved ", out + "/sheets_b.json")
	quit(0)


## The fringe check (spec "cells"): G3's 0.6 m 3/4 camera turned to a pixel of its shot (spec "zoom_px", "zoom_fov"),
## one cell per entry: option, sheets (the clay key), and overrides (exposure, saturation, normal_depth, micro_gain, ssao, eyes, fix).
func _cells(packed: PackedScene, out: String) -> void:
	_room()
	var node: Node3D = _add_copy(packed, Vector3.ZERO, Vector3.ZERO)
	await process_frame
	_pose(node, "Idle", 0.0)
	await process_frame
	var face_at: Vector3 = _eyes_centre(node) + Vector3(0, float(_spec.get("face_lift", 0.0)), 0)
	var fov: float = float(_spec["face_fov"])
	_look(face_at, -30.0, 4.0, 0.6, fov)
	var zp: Array = _spec["zoom_px"]  # a pixel of the 640 x 800 shot
	var t: float = tan(deg_to_rad(fov * 0.5))
	var b: Basis = _camera.global_transform.basis
	var dir: Vector3 = (-b.z + b.x * ((float(zp[0]) - 320.0) / 400.0 * t) + b.y * ((400.0 - float(zp[1])) / 400.0 * t))
	var cam: Vector3 = _camera.global_position
	var shots: Array[Image] = []
	var base: Dictionary = _spec.duplicate(true)
	for c: Dictionary in _spec["cells"]:
		_spec = base.duplicate(true)
		_spec.merge(c, true)
		_lights(_spec)
		_env.ssao_enabled = bool(c.get("ssao", true))
		if c.has("fix"):
			var fc: Array = c["fix"]
			_fix = Basis(Vector3(fc[0][0], fc[0][1], fc[0][2]), Vector3(fc[1][0], fc[1][1], fc[1][2]),
					Vector3(fc[2][0], fc[2][1], fc[2][2]))
		_apply(str(c["option"]), str(c["sheets"]))
		_eyes_shown(node, bool(c.get("eyes", true)))
		_camera.fov = float(c.get("zoom_fov", _spec.get("zoom_fov", 8.0)))
		_camera.look_at_from_position(cam, cam + dir, Vector3.UP)
		var img: Image = await _shot(str(c["label"]))
		img.save_png(out + "/shots/%s.png" % str(c["label"]).replace(" ", "_"))
		shots.append(img)
		_eyes_shown(node, true)
	_spec = base
	_save(_sheet(shots, 4), out + "/cells.png")
	print("LOOK saved ", out + "/cells.png")
	quit(0)


# ------------------------------------------------------------------ bench

func _bench_stage() -> void:  # godot/bench/bench.gd's _stage, unchanged in substance
	var env: Environment = Environment.new()
	var sky: Sky = Sky.new()
	sky.sky_material = ProceduralSkyMaterial.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	var world: WorldEnvironment = WorldEnvironment.new()
	world.environment = env
	root.add_child(world)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50.0, 35.0, 0.0)
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_max_distance = 60.0
	root.add_child(sun)
	var lamp: OmniLight3D = OmniLight3D.new()
	lamp.position = Vector3(0.0, 2.6, 0.0)
	lamp.omni_range = 9.0
	lamp.light_energy = 1.5
	lamp.shadow_enabled = true
	lamp.omni_shadow_mode = OmniLight3D.SHADOW_CUBE
	root.add_child(lamp)
	var ground: MeshInstance3D = MeshInstance3D.new()
	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(60.0, 60.0)
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.albedo_color = Color(0.55, 0.56, 0.58)
	plane.material = mat
	ground.mesh = plane
	root.add_child(ground)
	_camera = Camera3D.new()
	root.add_child(_camera)
	_overlay()


func _bench(packed: PackedScene, out: String) -> void:
	_bench_stage()
	var copies: int = int(_spec["copies"])
	var r: float = maxf(2.2, copies * 1.3 / TAU)
	for i: int in copies:
		var a: float = TAU * i / copies
		var node: Node3D = _add_copy(packed, Vector3(sin(a) * r, 0.0, cos(a) * r), Vector3.ZERO)
		var player: AnimationPlayer = _player(node)
		var clip: String = _clip(player, "Idle")
		player.play(clip)
		player.seek(fmod(i * 0.37, maxf(0.01, player.get_animation(clip).length)), true)
	_camera.fov = 75.0
	_camera.position = Vector3(0.0, 1.6, r + 2.5)
	_camera.look_at(Vector3(0.0, 1.0, 0.0))
	_camera.make_current()
	var vp: RID = root.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	var clay: String = str(int(_spec["mid_clay"]))
	var record: Dictionary = {"window": [root.get_visible_rect().size.x, root.get_visible_rect().size.y],
			"adapter": RenderingServer.get_video_adapter_name(), "godot": Engine.get_version_info()["string"],
			"copies": copies, "clay": clay, "frames": _spec["frames"], "rounds": [], "median": {}}
	var options: Array[String] = []
	for o: Variant in _spec.get("options", OPTIONS):
		options.append(str(o))
	var ids: Array[String] = ["empty"]
	ids.append_array(options)
	for opt: String in options:  # compile every option's pipelines before measuring
		_apply(opt, clay)
		for _f: int in 60:
			await RenderingServer.frame_post_draw
	for round_i: int in int(_spec["rounds"]):
		var rows: Dictionary = {}
		for id: String in ids:
			for node: Node3D in _copies:
				node.visible = id != "empty"
			if id != "empty":
				_apply(id, clay)
			rows[id] = await _measure(vp)
			print("LOOK round %d %s gpu %.3f ms cpu %.3f ms" % [round_i, id, rows[id]["gpu_ms"], rows[id]["cpu_ms"]])
			if round_i == 0 and id != "empty":
				var img: Image = await _shot("%s, %d copies, clay %s" % [OPTION_NAMES.get(id, id), copies, clay])
				_label.text = ""
				img.save_png(out + "/shots/bench_%s.png" % id)
		record["rounds"].append(rows)
	for id: String in ids:
		var g: Array = []
		var c: Array = []
		for rows: Dictionary in record["rounds"]:
			g.append(rows[id]["gpu_ms"])
			c.append(rows[id]["cpu_ms"])
		g.sort()
		c.sort()
		record["median"][id] = {"gpu_ms": g[g.size() / 2], "cpu_ms": c[c.size() / 2]}
	if not Character.write_json(out + "/bench.json", record):
		_fail("cannot write bench.json")
		return
	print("LOOK saved ", out + "/bench.json")
	quit(0)


func _measure(vp: RID) -> Dictionary:
	for _f: int in int(_spec["settle"]):
		await RenderingServer.frame_post_draw
	var gpu: Array[float] = []
	var cpu: Array[float] = []
	var draws: Array[float] = []
	for _f: int in int(_spec["frames"]):
		await RenderingServer.frame_post_draw
		gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(vp))
		cpu.append(RenderingServer.viewport_get_measured_render_time_cpu(vp))
		draws.append(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
	gpu.sort()
	cpu.sort()
	draws.sort()
	return {"gpu_ms": snappedf(gpu[gpu.size() / 2], 0.001), "gpu_p95": snappedf(gpu[int(gpu.size() * 0.95)], 0.001),
			"cpu_ms": snappedf(cpu[cpu.size() / 2], 0.001), "draw_calls": int(draws[draws.size() / 2])}


func _fail(why: String) -> void:
	push_error("LOOK error " + why)
	print("LOOK error ", why)
	quit(1)
