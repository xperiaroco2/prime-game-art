extends SceneTree
## M16 (art #196, brief UPDATE 29): the pout at rest in Godot, headless. Loads a kit's character (-- <res://..glb>),
## sets the rig up (alien.gd, the s5 look) with the pout shown at rest, the skeleton in its rest pose, and prints one
## line "POUT_REST {json}":
## - per closed piece (rest, M, small) the largest distance (mm) from a vertex's mirror across the body's centre plane
##   (global x -> -x) to the nearest vertex of the same piece ("mirror_mm"), and its vertex count;
## - the shown piece and its motion uniforms at rest (lip_drop, pucker, jaw_thrust: all 0);
## - the talk at rest (alien_talk.gd sample() before LINE and 2 s after its end: the piece, drop and pucker).
## tools/tests/test_alien_pout_rest_godot.py reads it.

const AlienRig := preload("res://alien/alien.gd")
const AlienTalk := preload("res://alien/alien_talk.gd")


func _mirror_mm(mi: MeshInstance3D) -> Dictionary:
	var pts := PackedVector3Array()
	var xf: Transform3D = mi.global_transform
	for s: int in mi.mesh.get_surface_count():
		var v: PackedVector3Array = mi.mesh.surface_get_arrays(s)[Mesh.ARRAY_VERTEX]
		for p: Vector3 in v:
			pts.append(xf * p)
	# a grid of 2 mm cells for the nearest-vertex search
	var cells := {}
	for i: int in pts.size():
		var key := Vector3i((pts[i] / 0.002).floor())
		if not cells.has(key):
			cells[key] = PackedInt32Array()
		cells[key].append(i)
	var worst := 0.0
	for p: Vector3 in pts:
		var m := Vector3(-p.x, p.y, p.z)
		var c := Vector3i((m / 0.002).floor())
		var best := INF
		for dx: int in range(-1, 2):
			for dy: int in range(-1, 2):
				for dz: int in range(-1, 2):
					var key := c + Vector3i(dx, dy, dz)
					if cells.has(key):
						for j: int in cells[key]:
							best = minf(best, pts[j].distance_to(m))
		worst = maxf(worst, best)
	return {"mirror_mm": snappedf(worst * 1000.0, 0.0001), "verts": pts.size()}


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var out := {"pieces": {}}
	var packed: PackedScene = load(args[0]) as PackedScene
	if packed == null:
		print("POUT_REST " + JSON.stringify({"error": "cannot load %s" % args[0]}))
		quit(1)
		return
	var ch: Node3D = packed.instantiate()
	root.add_child(ch)
	var ap: AnimationPlayer = ch.find_child("AnimationPlayer", true, false)
	if ap != null:
		ap.stop()
	for sk: Node in ch.find_children("*", "Skeleton3D", true, false):
		(sk as Skeleton3D).reset_bone_poses()
	var rig: Node = AlienRig.new()
	ch.add_child(rig)
	rig.setup(ch)
	rig.auto_blink = false
	rig.set_mouth_design("pout")
	rig.show_mouth("rest")
	rig.set_mouth_motion(0.0, 0.0)
	await process_frame
	await process_frame
	for s: String in ["rest", "M", "small"]:
		var n: Node3D = rig.node("mouth_pout_%s" % s)
		if n == null:
			continue
		var mis: Array = n.find_children("*", "MeshInstance3D", true, false)
		if n is MeshInstance3D:
			mis.push_front(n)
		if not mis.is_empty():
			out["pieces"][s] = _mirror_mm(mis[0] as MeshInstance3D)
	var r := rig.node("mouth_pout_rest") as GeometryInstance3D
	out["shown"] = r != null and r.visible
	if r != null:
		out["uniforms"] = {}
		for u: String in ["lip_drop", "pucker", "jaw_thrust"]:
			out["uniforms"][u] = float(r.get_instance_shader_parameter(u))
	var segs: Array = AlienTalk.segments(AlienTalk.LINE)
	var talk := {}
	for t: float in [0.0, float(segs[-1][1]) + 2000.0]:
		var sm: Dictionary = AlienTalk.sample("pout", segs, t)
		talk[str(int(t))] = {"piece": sm["piece"], "drop": sm["drop"], "pucker": sm["pucker"]}
	out["talk"] = talk
	print("POUT_REST " + JSON.stringify(out))
	quit(0)
