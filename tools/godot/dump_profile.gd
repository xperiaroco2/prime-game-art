# Dumps SkeletonProfileHumanoid from the running Godot to a JSON file: every bone's name, parent, reference pose,
# group, tail and handle data, plus the profile's groups. The runner's `contract` command sorts and formats it into
# contract/humanoid.json. Usage (headless, quits by itself):
#   godot --headless --path tools/godot --script res://dump_profile.gd -- <out.json>
extends SceneTree

const TAIL_DIRECTIONS: Array[String] = ["average_children", "specific_child", "end"]


func _init() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() != 1:
		printerr("dump_profile.gd: expected one argument after --, the output JSON path")
		quit(2)
		return
	var file := FileAccess.open(args[0], FileAccess.WRITE)
	if file == null:
		printerr("dump_profile.gd: cannot write %s (error %d)" % [args[0], FileAccess.get_open_error()])
		quit(1)
		return
	file.store_string(JSON.stringify(_dump(SkeletonProfileHumanoid.new()), "", true, true))
	file.close()
	quit(0)


func _dump(profile: SkeletonProfile) -> Dictionary:
	var groups: Array[Dictionary] = []
	for group_idx: int in profile.get_group_size():
		groups.append({"index": group_idx, "name": String(profile.get_group_name(group_idx))})
	var bones: Array[Dictionary] = []
	for bone_idx: int in profile.get_bone_size():
		var offset: Vector2 = profile.get_handle_offset(bone_idx)
		bones.append(
			{
				"index": bone_idx,
				"name": String(profile.get_bone_name(bone_idx)),
				"parent": String(profile.get_bone_parent(bone_idx)),
				"reference_pose": _transform(profile.get_reference_pose(bone_idx)),
				"group": String(profile.get_group(bone_idx)),
				"tail_direction": TAIL_DIRECTIONS[profile.get_tail_direction(bone_idx)],
				"tail": String(profile.get_bone_tail(bone_idx)),
				"handle_offset": [offset.x, offset.y],
				"required": profile.is_required(bone_idx),
			}
		)
	var version: Dictionary = Engine.get_version_info()
	return {
		"godot_version": "%s.%s.%s.%s" % [version.major, version.minor, version.patch, version.status],
		"profile": "SkeletonProfileHumanoid",
		"root_bone": String(profile.get_root_bone()),
		"scale_base_bone": String(profile.get_scale_base_bone()),
		"groups": groups,
		"bones": bones,
	}


func _transform(t: Transform3D) -> Dictionary:
	return {
		"basis_x": [t.basis.x.x, t.basis.x.y, t.basis.x.z],
		"basis_y": [t.basis.y.x, t.basis.y.y, t.basis.y.z],
		"basis_z": [t.basis.z.x, t.basis.z.y, t.basis.z.z],
		"origin": [t.origin.x, t.origin.y, t.origin.z],
	}
