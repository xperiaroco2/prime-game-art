extends RefCounted
## The vault plush's material (art#297, step 3): plush.gdshader on every mesh of the plush, with `shells` shells of
## plush_shell.gdshader chained as its next passes (0: the surface alone). The pile normal is a seamless noise normal
## map made here, so no texture file travels with it. Use with preload (no class cache in a `-s` script).

const SURFACE := preload("plush.gdshader")  # relative: the same file works where the game keeps it
const SHELL := preload("plush_shell.gdshader")


## A seamless fine-noise normal map for the pile; await its `changed` before the first frame.
static func pile_texture() -> NoiseTexture2D:
	var noise := FastNoiseLite.new()
	noise.noise_type = FastNoiseLite.TYPE_SIMPLEX
	noise.frequency = 0.09
	noise.fractal_octaves = 3
	noise.seed = 297
	var tex := NoiseTexture2D.new()
	tex.width = 512
	tex.height = 512
	tex.seamless = true
	tex.as_normal_map = true
	tex.bump_strength = 6.0
	tex.generate_mipmaps = true
	tex.noise = noise
	return tex


## Puts the plush material on every MeshInstance3D under root; returns [surface, shell 1, ...].
static func apply(root: Node, albedo: Texture2D, normal: Texture2D, mask: Texture2D, pile: Texture2D,
		shells: int) -> Array[ShaderMaterial]:
	var surface := ShaderMaterial.new()
	surface.shader = SURFACE
	surface.set_shader_parameter("albedo_tex", albedo)
	surface.set_shader_parameter("normal_tex", normal)
	surface.set_shader_parameter("mask_tex", mask)
	surface.set_shader_parameter("pile_tex", pile)
	var mats: Array[ShaderMaterial] = [surface]
	var last: ShaderMaterial = surface
	for i: int in shells:
		var shell := ShaderMaterial.new()
		shell.shader = SHELL
		shell.set_shader_parameter("albedo_tex", albedo)
		shell.set_shader_parameter("mask_tex", mask)
		shell.set_shader_parameter("layer", float(i + 1) / float(shells))
		shell.render_priority = i + 1
		last.next_pass = shell
		last = shell
		mats.append(shell)
	for m: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		m.material_override = surface
	return mats
