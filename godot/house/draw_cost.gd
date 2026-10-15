extends RefCounted
## A view's draw-call cost, one code path for `house --bake ZONES --count` (bake_shots.gd) and `house --walk` (walk.gd)
## (#107, #185): the High preset's sheen overlay (a black additive copy of the lightmapped meshes on SHEEN_LAYER that
## the sheen lights alone reach) and the measure itself, `cost`.

const SHEEN_LAYER := 2  # render layer bit 2 (value 2): the overlay copies and the sheen lights' cull mask


## A black, additive, ambient-free copy of every mesh of `meshes` with gi_mode Static on SHEEN_LAYER, beside its
## original: the sheen lights reach only these copies, so they add their specular and nothing else (black albedo: no
## diffuse; no ambient: the lightmap and the probes are not added twice). The originals stay on layer 1, outside the
## sheen lights' cull mask. Returns the copies.
static func overlay(meshes: Array) -> Array:
	var mats := {}
	var out := []
	for mi: MeshInstance3D in meshes:
		if mi.gi_mode != GeometryInstance3D.GI_MODE_STATIC or mi.mesh == null:
			continue
		var o := MeshInstance3D.new()
		o.mesh = mi.mesh
		o.transform = mi.transform
		o.layers = SHEEN_LAYER
		o.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		o.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
		for s in mi.mesh.get_surface_count():
			var m: Material = mi.get_surface_override_material(s)
			if m == null:
				m = mi.mesh.surface_get_material(s)
			if not mats.has(m):
				mats[m] = sheen_material(m)
			o.set_surface_override_material(s, mats[m])
		mi.get_parent().add_child(o)
		out.append(o)
	return out


static func sheen_material(m: Material) -> Material:
	var s: BaseMaterial3D
	if m is BaseMaterial3D:
		s = (m as BaseMaterial3D).duplicate()
	else:
		s = StandardMaterial3D.new()
		s.roughness = 0.6
	s.albedo_color = Color.BLACK
	s.albedo_texture = null
	s.metallic = 0.0
	s.emission_enabled = false
	s.next_pass = null
	s.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
	s.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	s.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	s.disable_ambient_light = true
	s.disable_fog = true
	return s


## A shot's cost, the same way for every caller: the real-time lights `rt` (all, and in view: the range sphere meets
## the camera's frustum) and their shadowed share; then per frame, averaged over 8 drawn frames, the draw calls, shadow
## draw calls and GPU ms with the shadows cached ("cached"), and again with every shadowed light nudged 1 mm each frame
## ("redrawn": every shadow re-rendered, the worst case of a player moving in each lamp's range). `vp` is the viewport
## the camera draws (the root window).
static func cost(vp: Viewport, cam: Camera3D, rt: Array) -> Dictionary:
	var planes := cam.get_frustum()
	var c := {"rt_lights": rt.size(), "rt_in_view": 0, "shadowed": 0, "shadowed_in_view": 0}
	for l: Light3D in rt:
		var rng: float = l.get("omni_range") if l is OmniLight3D else l.get("spot_range")
		var seen := true
		for p: Plane in planes:
			if p.distance_to(l.global_position) > rng:
				seen = false
				break
		c["rt_in_view"] += int(seen)
		c["shadowed"] += int(l.shadow_enabled)
		c["shadowed_in_view"] += int(seen and l.shadow_enabled)
	var rid := vp.get_viewport_rid()
	for phase in ["cached", "redrawn"]:
		var sum := [0.0, 0.0, 0.0]
		for i in 10:  # the first 2 frames settle (the GPU timer lags a frame or two)
			if phase == "redrawn":
				for l: Light3D in rt:
					if l.shadow_enabled:
						l.position.y += 0.001 if i % 2 == 0 else -0.001
			await RenderingServer.frame_post_draw
			if i >= 2:
				sum[0] += vp.get_render_info(Viewport.RENDER_INFO_TYPE_VISIBLE, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME)
				sum[1] += vp.get_render_info(Viewport.RENDER_INFO_TYPE_SHADOW, Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME)
				sum[2] += RenderingServer.viewport_get_measured_render_time_gpu(rid)
		c["draw_calls_" + phase] = sum[0] / 8
		c["shadow_draw_calls_" + phase] = sum[1] / 8
		c["gpu_ms_" + phase] = sum[2] / 8
	return c
