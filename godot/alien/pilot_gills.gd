extends RefCounted
## The axolotl pilot's living gills (art #196, step 2b-2): one SpringBoneSimulator3D (Godot 4.7.2) setting per gill
## chain, `<Left|Right>Gill<n>_1` to `_3` (alien_pilot_rig.py's three bones per stalk), the end bone extended along
## its parent by one segment, no gravity (the stalks keep their fanned rest), stiffness and drag from the 2b-2 grid
## (pilot_sheet.gd "gills"). Reusable: `PilotGills.attach(skeleton)` on any skeleton with such chains.
##     const PilotGills = preload("res://alien/pilot_gills.gd")
##     var sim := PilotGills.attach(skeleton)

const STIFFNESS := 1.0  # picked from the 2b-2 grid (see docs/godot.md, "The pilot's living gills")
const DRAG := 0.4
const BONE_DIRECTION_FROM_PARENT := 6  # SkeletonModifier3D.BoneDirection: +X..-Z are 0..5


static func chains(skeleton: Skeleton3D) -> PackedStringArray:
	var roots := PackedStringArray()
	var re := RegEx.create_from_string("^(Left|Right)Gill\\d+_1$")
	for i: int in skeleton.get_bone_count():
		if re.search(skeleton.get_bone_name(i)) != null:
			roots.append(skeleton.get_bone_name(i))
	return roots


static func attach(skeleton: Skeleton3D, stiffness: float = STIFFNESS, drag: float = DRAG) -> SpringBoneSimulator3D:
	var sim := SpringBoneSimulator3D.new()
	sim.name = "GillSprings"
	var roots := chains(skeleton)
	sim.set_setting_count(roots.size())
	for k: int in roots.size():
		var stem: String = roots[k].trim_suffix("_1")
		var mid := skeleton.find_bone(stem + "_2")
		var end := skeleton.find_bone(stem + "_3")
		var seg := skeleton.get_bone_global_rest(end).origin.distance_to(skeleton.get_bone_global_rest(mid).origin)
		sim.set_root_bone_name(k, roots[k])
		sim.set_end_bone_name(k, stem + "_3")
		sim.set_extend_end_bone(k, true)
		sim.set_end_bone_direction(k, BONE_DIRECTION_FROM_PARENT)
		sim.set_end_bone_length(k, seg)
		sim.set_stiffness(k, stiffness)
		sim.set_drag(k, drag)
		sim.set_gravity(k, 0.0)
		sim.set_radius(k, seg * 0.15)
	skeleton.add_child(sim)
	return sim
