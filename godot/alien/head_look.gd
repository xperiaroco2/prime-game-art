extends SkeletonModifier3D
## The head follows the player's aim (art #196, H1): the reference modifier the game copies, like
## godot/ragdoll/builder.gd. A child of the character's Skeleton3D; Godot runs every SkeletonModifier3D after the
## AnimationMixer's playback, so it turns the trunk, neck and head on top of whatever clip plays. Only bones turn: the
## head's mesh stays as it is (no face rig, no morphs).
##
## Inputs: aim_yaw (radians, the aim's turn relative to the body, + to the character's left, i.e. counter-clockwise
## seen from above) and aim_pitch (radians, + up). Each is clamped (yaw_limit, pitch_down, pitch_up), smoothed toward
## its target with the time constant smoothing_s (0: at once), then split over the chain: each bone of yaw_split and
## pitch_split takes its share, so the head bone, the chain's last, ends turned by the whole aim. The turn is about the
## skeleton space's up (UP) and, for the pitch, about the yawed right axis: the head's facing reaches the asked yaw and
## pitch exactly on the rest pose, and on a clip it is the clip's own facing turned by them.
##
## The body-lag rule (a demo, the game-design call is the engineer's): body_follow() keeps the body's yaw while the
## aim is within a dead zone of it and turns the body just enough to keep the aim at the zone's edge beyond it; the
## modifier's aim_yaw is then the aim relative to the new body yaw (at most the dead zone).

const UP := Vector3.UP
const FORWARD := Vector3.BACK  # the GLB's character faces +Z in skeleton space (glTF's forward)

## The aim's turn relative to the body (radians): + to the character's left, - to its right.
@export var aim_yaw := 0.0
## The aim's pitch (radians): + up, - down.
@export var aim_pitch := 0.0
## The clamps (degrees): the largest yaw either way, the largest pitch down and up. H1's recommendation for both
## aliens: down to 35 (at 50 the face hides under the crown from the front and the jaw sinks into the chest, worst at
## full yaw and on the jog's forward lean).
@export var yaw_limit_deg := 70.0
@export var pitch_down_deg := 35.0
@export var pitch_up_deg := 40.0
## The smoothing's time constant (seconds): the applied angles close 63 % of their gap to the target in this time.
@export var smoothing_s := 0.05
## The split: bone name -> share of the yaw (or the pitch). Shares are normalised to sum 1; missing bones are skipped.
## H1's "trunk" split: more of the turn in the trunk and less in the head bone than R1's proposal (Spine 10 / Chest 15
## / UpperChest 15 / Neck 25 / Head 35; pitch UpperChest 15 / Neck 35 / Head 50), so the neck's skin twists less.
@export var yaw_split := {"Spine": 0.15, "Chest": 0.20, "UpperChest": 0.20, "Neck": 0.25, "Head": 0.20}:
	set(v):
		yaw_split = v
		_chain.clear()  # rebuilt on the next modification
@export var pitch_split := {"Chest": 0.10, "UpperChest": 0.20, "Neck": 0.35, "Head": 0.35}:
	set(v):
		pitch_split = v
		_chain.clear()

var _yaw := 0.0  # the applied (smoothed, clamped) angles, radians
var _pitch := 0.0
var _started := false
var _chain: Array[int] = []  # bone indices, parent first, a contiguous run down to the last split bone
var _wy: PackedFloat32Array = []  # per chain bone its share of the yaw, of the pitch
var _wp: PackedFloat32Array = []


## The clamped target (radians): Vector2(yaw, pitch).
func target() -> Vector2:
	return Vector2(clampf(aim_yaw, -deg_to_rad(yaw_limit_deg), deg_to_rad(yaw_limit_deg)),
		clampf(aim_pitch, -deg_to_rad(pitch_down_deg), deg_to_rad(pitch_up_deg)))


## The applied angles after smoothing (radians): Vector2(yaw, pitch).
func applied() -> Vector2:
	return Vector2(_yaw, _pitch)


## Jumps the smoothing to the target (a teleport, a respawn, a test).
func snap() -> void:
	var t := target()
	_yaw = t.x
	_pitch = t.y
	_started = true


## The body-lag rule: the body's new yaw (radians, world) for an aim yaw (radians, world) and a dead zone (radians).
## Within the zone the body keeps its yaw; beyond it the body turns so the aim sits on the zone's edge.
static func body_follow(body_yaw: float, aim_world_yaw: float, dead_zone: float) -> float:
	var rel := wrapf(aim_world_yaw - body_yaw, -PI, PI)
	if absf(rel) <= dead_zone:
		return body_yaw
	return wrapf(aim_world_yaw - signf(rel) * dead_zone, -PI, PI)


## The turn of the aim (yaw, then pitch about the yawed right axis) in skeleton space; + pitch lifts FORWARD up.
static func aim_turn(yaw: float, pitch: float) -> Quaternion:
	return Quaternion(UP, yaw) * Quaternion(Vector3.RIGHT, -pitch)


func _validate_bone_names() -> void:
	_build_chain()


func _skeleton_changed(_old: Skeleton3D, _new: Skeleton3D) -> void:
	_build_chain()


func _build_chain() -> void:
	_chain.clear()
	_wy.clear()
	_wp.clear()
	var sk := get_skeleton()
	if sk == null:
		return
	var deepest := -1
	var depth := -1
	for n: String in yaw_split.keys() + pitch_split.keys():
		var i: int = sk.find_bone(n)
		if i < 0:
			continue
		var d := 0
		var p: int = sk.get_bone_parent(i)
		while p >= 0:
			d += 1
			p = sk.get_bone_parent(p)
		if d > depth:
			depth = d
			deepest = i
	if deepest < 0:
		return
	var first := deepest  # walk up to the shallowest split bone: the chain is every bone between, parent first
	var b := deepest
	while b >= 0:
		var name: String = sk.get_bone_name(b)
		if yaw_split.has(name) or pitch_split.has(name):
			first = b
		b = sk.get_bone_parent(b)
	b = deepest
	while b >= 0:
		_chain.push_front(b)
		if b == first:
			break
		b = sk.get_bone_parent(b)
	var sy := 0.0
	var sp := 0.0
	for i: int in _chain:
		var name: String = sk.get_bone_name(i)
		_wy.append(float(yaw_split.get(name, 0.0)))
		_wp.append(float(pitch_split.get(name, 0.0)))
		sy += _wy[-1]
		sp += _wp[-1]
	for k: int in _chain.size():
		_wy[k] = _wy[k] / sy if sy > 0.0 else 0.0
		_wp[k] = _wp[k] / sp if sp > 0.0 else 0.0


func _process_modification_with_delta(delta: float) -> void:
	var sk := get_skeleton()
	if sk == null:
		return
	if _chain.is_empty():
		_build_chain()
		if _chain.is_empty():
			return
	var t := target()
	if not _started or smoothing_s <= 0.0:
		snap()
	elif delta > 0.0:
		var k := 1.0 - exp(-delta / smoothing_s)
		_yaw += (t.x - _yaw) * k
		_pitch += (t.y - _pitch) * k
	# the animated global rotations first (the chain's parent's and each chain bone's), then the turned ones
	var parent: int = sk.get_bone_parent(_chain[0])
	var g_parent: Quaternion = sk.get_bone_global_pose(parent).basis.get_rotation_quaternion() if parent >= 0 \
			else Quaternion.IDENTITY
	var g := g_parent
	var new_parent := g_parent
	var cy := 0.0
	var cp := 0.0
	for k: int in _chain.size():
		var i: int = _chain[k]
		var local: Quaternion = sk.get_bone_pose_rotation(i)
		g = g * local  # this bone's animated global rotation
		cy += _wy[k] * _yaw
		cp += _wp[k] * _pitch
		var turned: Quaternion = aim_turn(cy, cp) * g
		sk.set_bone_pose_rotation(i, (new_parent.inverse() * turned).normalized())
		new_parent = turned
