extends RefCounted
## The energy crystal's look (art#263's station props; the cartridge of prime-game#1033): puts the shell, core,
## metal and light materials on an imported energy_crystal.glb by its glTF material names, and adds a small cyan
## OmniLight3D inside, so a charged crystal lights what is near it. One charge value drives the two states: 1
## charged (cyan, glowing), 0 spent (grey stone, no glow, the cap's lights dimmed); values between fade.
## Use with preload (no class cache in a `-s` script); every apply() makes the crystal its own materials.
##
##   const Crystal = preload("crystal.gd")
##   var look: Dictionary = Crystal.apply(model)
##   Crystal.set_charge(look, 0.0)   # spent

const SHELL := preload("crystal_shell.gdshader")  # relative: the same file works where the game keeps it
const CORE := preload("crystal_core.gdshader")
const METAL := preload("crystal_metal.gdshader")

const LIGHT_COLOUR := Color(0.0, 0.72, 1.0)
const LIGHT_ENERGY := 2.2       # the cap's windows and lens at full charge (HDR: they bloom; more bleaches them white)
const LIGHT_SPENT := 0.22       # the share they keep when spent: a dim glow, never dark
const OMNI_ENERGY := 1.2        # the crystal's own light at full charge
const OMNI_RANGE := 1.6


## Puts the crystal's materials on every surface under root; returns the look: {"shell", "core", "light"
## (StandardMaterial3D), "omni" (OmniLight3D), "charge"}.
static func apply(root: Node3D) -> Dictionary:
	var shell := ShaderMaterial.new()
	shell.shader = SHELL
	var core := ShaderMaterial.new()
	core.shader = CORE
	var bronze := ShaderMaterial.new()
	bronze.shader = METAL
	var graphite := ShaderMaterial.new()
	graphite.shader = METAL
	graphite.set_shader_parameter("base_color", Color(0.305, 0.305, 0.318))  # sRGB of the Blender look's linear
	graphite.set_shader_parameter("worn_color", Color(0.68, 0.665, 0.645))
	graphite.set_shader_parameter("metallic", 0.8)
	graphite.set_shader_parameter("roughness", 0.42)
	var light := StandardMaterial3D.new()
	light.albedo_color = Color(0.02, 0.05, 0.06)
	light.roughness = 0.2
	light.emission_enabled = true
	light.emission = LIGHT_COLOUR
	var by_name := {"crystal_shell": shell, "crystal_core": core, "crystal_bronze": bronze,
		"crystal_graphite": graphite, "crystal_light": light}
	var omni := OmniLight3D.new()
	omni.light_color = LIGHT_COLOUR
	omni.omni_range = OMNI_RANGE
	omni.omni_attenuation = 1.6
	omni.shadow_enabled = false
	var box := AABB()
	var first := true
	for m: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i: int in m.mesh.get_surface_count():
			var src: Material = m.mesh.surface_get_material(i)
			var key: String = src.resource_name if src != null else ""
			if by_name.has(key):
				m.set_surface_override_material(i, by_name[key])
			else:
				push_warning("crystal.gd: no look for surface material '%s'" % key)
		var b: AABB = m.transform * m.get_aabb()
		box = b if first else box.merge(b)
		first = false
	root.add_child(omni)
	omni.position = box.get_center() - Vector3(0.0, box.size.y * 0.12, 0.0)  # in the crystal, under the cap
	var look := {"shell": shell, "core": core, "light": light, "omni": omni, "charge": 1.0}
	set_charge(look, 1.0)
	return look


## The crystal's state: 1 charged, 0 spent.
static func set_charge(look: Dictionary, charge: float) -> void:
	var c := clampf(charge, 0.0, 1.0)
	(look["shell"] as ShaderMaterial).set_shader_parameter("charge", c)
	(look["core"] as ShaderMaterial).set_shader_parameter("charge", c)
	(look["light"] as StandardMaterial3D).emission_energy_multiplier = LIGHT_ENERGY * lerpf(LIGHT_SPENT, 1.0, c)
	var omni: OmniLight3D = look["omni"]
	omni.light_energy = OMNI_ENERGY * c
	omni.visible = c > 0.001
	look["charge"] = c
