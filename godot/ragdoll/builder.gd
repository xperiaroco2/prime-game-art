extends RefCounted
## The reference ragdoll builder (art #115; docs/contract.md, "Ragdoll"): turns a character's ragdoll data (the
## `<id>.ragdoll.json` beside its GLB, written by `tools/run.py ragdoll`) into PhysicalBone3D nodes under a
## PhysicalBoneSimulator3D on the character's Skeleton3D, and starts the fall. The game may copy this file as it is.
## Loaded with preload(), not a class_name, so that a script run with -s works without the editor's class cache.
##
##   var sim := Builder.build(skeleton, data)        # once, at import or spawn; nothing simulates yet
##   Builder.start(sim, data, avatar_velocity)       # the knockdown: from the current (standing) pose
##   Builder.stop(sim)                               # the revive: the animation takes the bones back
##
## Every Godot name is in 4.7.2's API. The joints are Joint3D nodes made at the start, not the PhysicalBone3D's own
## joint: the rig's feet hang from Root (an IK-style rig), so a PhysicalBone3D joint, which links a bone to its nearest
## simulated skeleton ancestor, would leave them free; the data names each body's physical parent instead.

## The joints' frames from the data's (positive flexion about the axis); measured on Jolt Physics 4.7.2.
const HINGE_SIGN: float = -1.0


static func _layer_bits(layers: Array) -> int:
	var bits: int = 0
	for layer: Variant in layers:
		bits |= 1 << (int(layer) - 1)
	return bits


static func _v3(a: Array) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))


static func _quat(a: Array) -> Quaternion:
	return Quaternion(float(a[0]), float(a[1]), float(a[2]), float(a[3])).normalized()


## The body's transform in its bone's frame: the shape's offset and rotation.
static func body_offset(bone: Dictionary) -> Transform3D:
	return Transform3D(Basis(_quat(bone.get("rotation", [0, 0, 0, 1]))), _v3(bone["offset"]))


static func shape_of(bone: Dictionary) -> Shape3D:
	if bone["shape"] == "box":
		var box: BoxShape3D = BoxShape3D.new()
		box.size = _v3(bone["size"])
		return box
	var capsule: CapsuleShape3D = CapsuleShape3D.new()
	capsule.radius = float(bone["radius"])
	capsule.height = float(bone["height"])
	return capsule


## Builds the simulator and one PhysicalBone3D per listed bone (named after the bone); returns the simulator, a child
## of skeleton. Bones the data does not list follow their parent as the skeleton poses them.
static func build(skeleton: Skeleton3D, data: Dictionary) -> PhysicalBoneSimulator3D:
	var sim: PhysicalBoneSimulator3D = PhysicalBoneSimulator3D.new()
	sim.name = "Ragdoll"
	skeleton.add_child(sim)
	var layer: int = _layer_bits([data["collision"]["layer"]])
	var mask: int = _layer_bits(data["collision"]["mask"])
	var material: Dictionary = data.get("material", {})
	var total: float = float(data["total_mass_kg"])
	for bone: Dictionary in data["bones"]:
		if skeleton.find_bone(bone["bone"]) < 0:
			push_error("ragdoll: no bone %s in %s" % [bone["bone"], skeleton.name])
			continue
		var pb: PhysicalBone3D = PhysicalBone3D.new()
		pb.name = String(bone["bone"]).validate_node_name()  # "UpperArm.L" becomes "UpperArm_L"
		pb.bone_name = String(bone["bone"])
		pb.joint_type = PhysicalBone3D.JOINT_TYPE_NONE
		pb.body_offset = body_offset(bone)
		pb.mass = maxf(0.05, float(bone["mass_share"]) * total)
		pb.friction = float(material.get("friction", 0.8))
		pb.bounce = float(material.get("bounce", 0.0))
		pb.linear_damp = float(material.get("linear_damp", 0.1))
		pb.angular_damp = float(material.get("angular_damp", 3.0))
		pb.collision_layer = layer
		pb.collision_mask = mask
		var shape: CollisionShape3D = CollisionShape3D.new()
		shape.name = "Shape"
		shape.shape = shape_of(bone)
		pb.add_child(shape)
		sim.add_child(pb)
	return sim


## The joint's frame in world space from the child's current body: at the anchor, for a cone its X (Godot's twist
## axis) along the bone, for a hinge its Z (Godot's hinge axis) along the data's axis.
static func joint_transform(pb: PhysicalBone3D, bone: Dictionary) -> Transform3D:
	var bone_global: Transform3D = pb.global_transform * pb.body_offset.affine_inverse()
	var joint: Dictionary = bone["joint"]
	var origin: Vector3 = bone_global * _v3(joint.get("anchor", [0, 0, 0]))
	var along: Vector3 = (bone_global.basis * Vector3.UP).normalized()
	var basis: Basis
	if joint["type"] == "hinge":
		var axis: Vector3 = (bone_global.basis * _v3(joint["axis"])).normalized()
		var x: Vector3 = (along - axis * along.dot(axis)).normalized()
		basis = Basis(x, axis.cross(x), axis)
	else:
		var side: Vector3 = (bone_global.basis * Vector3.RIGHT).normalized()
		var y: Vector3 = (side - along * side.dot(along)).normalized()
		basis = Basis(along, y, along.cross(y))
	return Transform3D(basis, origin)


## The simulator's bodies by bone name.
static func bodies(sim: PhysicalBoneSimulator3D) -> Dictionary:
	var out: Dictionary = {}
	for node: Node in sim.get_children():
		if node is PhysicalBone3D:
			out[String((node as PhysicalBone3D).bone_name)] = node
	return out


## Starts the simulation from the skeleton's current pose, links every body to its physical parent and gives them
## velocity (the avatar's). Call it on the frame of the knockdown.
## The joints are made on the next physics frame, once the physics server holds the bodies at the start pose (made at
## once, their frames came from node transforms the server had not taken yet, and the knees popped by 25 degrees).
static func start(sim: PhysicalBoneSimulator3D, data: Dictionary, velocity: Vector3 = Vector3.ZERO) -> void:
	sim.physical_bones_start_simulation()
	var by_bone: Dictionary = bodies(sim)
	for bone: Dictionary in data["bones"]:
		var pb: PhysicalBone3D = by_bone.get(String(bone["bone"])) as PhysicalBone3D
		if pb == null:
			continue
		pb.linear_velocity = velocity
	await sim.get_tree().physics_frame
	if not sim.is_simulating_physics():
		return
	for bone: Dictionary in data["bones"]:
		if bone.get("parent") == null:
			continue
		var child: PhysicalBone3D = by_bone.get(String(bone["bone"])) as PhysicalBone3D
		var parent: PhysicalBone3D = by_bone.get(String(bone["parent"])) as PhysicalBone3D
		if child == null or parent == null:
			continue
		var j: Dictionary = bone["joint"]
		var joint: Joint3D
		if j["type"] == "hinge":
			var hinge: HingeJoint3D = HingeJoint3D.new()
			hinge.set_flag(HingeJoint3D.FLAG_USE_LIMIT, true)
			var a: float = deg_to_rad(float(j["min_deg"])) * HINGE_SIGN
			var b: float = deg_to_rad(float(j["max_deg"])) * HINGE_SIGN
			hinge.set_param(HingeJoint3D.PARAM_LIMIT_LOWER, minf(a, b))
			hinge.set_param(HingeJoint3D.PARAM_LIMIT_UPPER, maxf(a, b))
			joint = hinge
		elif j["type"] == "cone":
			var cone: ConeTwistJoint3D = ConeTwistJoint3D.new()
			cone.set_param(ConeTwistJoint3D.PARAM_SWING_SPAN, deg_to_rad(float(j["swing_deg"])))
			cone.set_param(ConeTwistJoint3D.PARAM_TWIST_SPAN, deg_to_rad(float(j["twist_deg"])))
			joint = cone
		else:
			joint = PinJoint3D.new()
		joint.name = ("Joint_" + String(bone["bone"])).validate_node_name()
		sim.add_child(joint)
		joint.global_transform = joint_transform(child, bone)
		joint.exclude_nodes_from_collision = true
		joint.node_a = joint.get_path_to(parent)
		joint.node_b = joint.get_path_to(child)


## Ends the simulation (a revive): removes the joints; the animation poses the bones again.
static func stop(sim: PhysicalBoneSimulator3D) -> void:
	for node: Node in sim.get_children():
		if node is Joint3D:
			node.queue_free()
	sim.physical_bones_stop_simulation()
