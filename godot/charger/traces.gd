extends RefCounted
## The charger traces (art#263, prime-game#1095 c6468773545): the cyan circuit traces on a lens alcove's back panel,
## lit by its charger's charge. They belong to the ship piece lens_alcove (material lens_trace, built by
## tools/blender/ship_interior_lens.py trace_parts), not to the charger package, so this script stays out of
## charger.gd (whose copy ships in assets/prop/crystal_charger). ship.gd puts one idle traces.gdshader on every
## lens_trace surface; bind() gives the traces near one charger their own copy, kept in its charger.gd look.
## Use with preload (no class cache in a `-s` script):
##
##   const Traces = preload("res://charger/traces.gd")
##   Traces.bind(look, ship)                    # look: Charger.apply()'s; the alcove's traces near its crystal
##   Traces.set_panel(look, fill, flare, lit)   # each frame: the fill front, the ring's flare, the fade

const SHADER := preload("res://charger/traces.gdshader")
const TRACE_MAT := "lens_trace"
const PANEL_REACH := 1.2   # m: a lens_trace mesh whose box centre is this near the crystal's middle is this charger's


## Finds a charger's alcove traces: every surface in material lens_trace under `scene` whose mesh's box centre lies
## within PANEL_REACH of the crystal's middle (the charger look's glow light), and gives them one ShaderMaterial of
## their own (idle), kept as look["panel"]. Returns the surfaces bound (3 in a lens alcove: lines, dots, ring).
static func bind(look: Dictionary, scene: Node) -> int:
	var centre: Vector3 = _world(look["glow"]).origin
	var mat := ShaderMaterial.new()
	mat.shader = SHADER
	var count := 0
	for m: MeshInstance3D in scene.find_children("*", "MeshInstance3D", true, false):
		if m.mesh == null:
			continue
		if (_world(m) * m.mesh.get_aabb().get_center()).distance_to(centre) > PANEL_REACH:
			continue
		for i: int in m.mesh.get_surface_count():
			var src: Material = m.mesh.surface_get_material(i)
			if src != null and src.resource_name == TRACE_MAT:
				m.set_surface_override_material(i, mat)
				count += 1
	look["panel"] = mat
	set_panel(look, 0.0)
	return count


## The traces: fill 0 (idle: every line dim) .. 1 (every line full, the fronts on the ring), the charge fraction while
## charging (a bright front with a small head runs from each line's outer end to the ring); flare 0..1 the ring's
## white-cyan flare (a short pulse when the charge is full); lit 1 .. 0 fades what the fill lit back to dim (the
## crystal taken out, over about 0.5 s). No-op before bind().
static func set_panel(look: Dictionary, fill: float, flare: float = 0.0, lit: float = 1.0) -> void:
	var m: ShaderMaterial = look.get("panel")
	if m == null:
		return
	m.set_shader_parameter("fill", clampf(fill, 0.0, 1.0))
	m.set_shader_parameter("flare", clampf(flare, 0.0, 1.0))
	m.set_shader_parameter("lit", clampf(lit, 0.0, 1.0))


## A node's transform up its Node3D parents (the shots build the scene in _initialize, before the tree is entered:
## global_transform is not there yet).
static func _world(n: Node) -> Transform3D:
	var t := Transform3D.IDENTITY
	while n != null:
		if n is Node3D:
			t = (n as Node3D).transform * t
		n = n.get_parent()
	return t
