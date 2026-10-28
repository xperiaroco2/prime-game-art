extends Node
## The photo poses as two held layers (art #196; prime-game docs/GDD.md section 8 "Photo"): the reference the game
## copies, like head_look.gd. A pair is a legs pose (PoseLegs_<Name>: Root, Hips, Spine and both legs to the toes) and
## an arms pose (PoseArms_<Name>: Chest and everything under it: the neck, head, shoulders, arms, fingers), any of the
## 6 x 8. Each clip is a held loop of identical keys; each keys only its own layer's bones.
##
## The mechanism: an AnimationTree beside the character's AnimationPlayer, sharing its libraries, with one blend tree:
## legs -> Blend2.in, arms -> Blend2.blend, the Blend2's filter on every arms bone (Chest and its descendants, read off
## the skeleton, not a list) at amount 1. The unfiltered (legs) tracks pass from the legs clip; the filtered (arms)
## tracks come from the arms clip. While a pose plays the tree is active and the player is stopped (two mixers on one
## skeleton fight); stop() hands the skeleton back to the player.
##
## The game's rules (prime-game section 8): the pose holds while the player stands; turning on the spot keeps it (the
## character node turns, the clips do not change); a step drops it (the game calls stop() and plays its locomotion).
## The head look during a pose: docs/animations.md, "The photo poses (art #196)" (measured by pose_layers_check.gd).
##
## A per-legs variant of an arms pose, PoseArms_<Arms>__<Legs> (the hip hand solved over a legs pose whose raised thigh
## the hand would go into: Sit, Squat, Kneel, OneLeg), is played instead of PoseArms_<Arms> with those legs when the
## character has it (the game copies this rule); no other pair has its own clip.
##
## Use: var layers := PoseLayers.new(); character.add_child(layers); layers.setup(anim_player)
##      layers.play_pair("OneLeg", "Plane") ... layers.stop()

const LEGS_PREFIX := "PoseLegs_"
const VARIANT := "__"  # PoseArms_<Arms>__<Legs>: the arms pose solved over those legs
const ARMS_PREFIX := "PoseArms_"
const ARMS_ROOT := "Chest"  # the arms layer: this bone and every bone under it

var player: AnimationPlayer
var tree: AnimationTree
var legs := ""
var arms := ""
var _legs_node: AnimationNodeAnimation
var _arms_node: AnimationNodeAnimation
var _clips := {}  # "PoseLegs_Stand" -> the library's full name ("CharacterArmature|PoseLegs_Stand_Loop")


## Builds the tree for this player's character. The skeleton is the first Skeleton3D under the player's root node.
func setup(p: AnimationPlayer) -> void:
	player = p
	_clips.clear()
	for n: String in player.get_animation_list():
		var short: String = n.get_slice("|", n.get_slice_count("|") - 1).trim_suffix("_Loop")
		if short.begins_with(LEGS_PREFIX) or short.begins_with(ARMS_PREFIX):
			_clips[short] = n
	if tree != null:  # a second setup() replaces the first tree: out of the scene now (its name free), freed later
		if tree.get_parent() != null:
			tree.get_parent().remove_child(tree)
		tree.queue_free()
		tree = null
	var root: Node = player.get_node(player.root_node)
	var found: Array[Node] = root.find_children("*", "Skeleton3D", true, false)
	if found.is_empty():
		push_error("pose_layers: no Skeleton3D under the player's root node")
		return
	var sk: Skeleton3D = found[0]
	var bt := AnimationNodeBlendTree.new()
	_legs_node = AnimationNodeAnimation.new()
	_arms_node = AnimationNodeAnimation.new()
	var mix := AnimationNodeBlend2.new()
	mix.filter_enabled = true
	var sk_path: String = str(root.get_path_to(sk))
	var top: int = sk.find_bone(ARMS_ROOT)
	for b: int in sk.get_bone_count():
		var i := b
		while i >= 0 and i != top:
			i = sk.get_bone_parent(i)
		if i == top:
			mix.set_filter_path(NodePath("%s:%s" % [sk_path, sk.get_bone_name(b)]), true)
	bt.add_node("legs", _legs_node, Vector2(0, 0))
	bt.add_node("arms", _arms_node, Vector2(0, 200))
	bt.add_node("mix", mix, Vector2(300, 100))
	bt.connect_node("mix", 0, "legs")
	bt.connect_node("mix", 1, "arms")
	bt.connect_node("output", 0, "mix")
	tree = AnimationTree.new()
	tree.name = "PoseLayers"
	tree.tree_root = bt
	tree.active = false
	player.get_parent().add_child(tree)
	tree.root_node = tree.get_path_to(root)
	tree.anim_player = tree.get_path_to(player)
	tree.callback_mode_process = player.callback_mode_process
	tree.set("parameters/mix/blend_amount", 1.0)


## The pose names: {"legs": [...], "arms": [...]} (without the prefixes).
func poses() -> Dictionary:
	var out := {"legs": [], "arms": []}
	for short: String in _clips:
		if short.begins_with(LEGS_PREFIX):
			out["legs"].append(short.trim_prefix(LEGS_PREFIX))
		elif not short.contains(VARIANT):
			out["arms"].append(short.trim_prefix(ARMS_PREFIX))
	return out


## Holds the pair (any legs with any arms); false if either clip is missing.
func play_pair(legs_name: String, arms_name: String) -> bool:
	if tree == null:  # setup() found no skeleton
		return false
	var l: String = _clips.get(LEGS_PREFIX + legs_name, "")
	var a: String = _clips.get(ARMS_PREFIX + arms_name + VARIANT + legs_name,
			_clips.get(ARMS_PREFIX + arms_name, ""))
	if l == "" or a == "":
		return false
	legs = legs_name
	arms = arms_name
	_legs_node.animation = l
	_arms_node.animation = a
	player.stop()
	tree.active = true
	tree.advance(0.0)
	return true


## Hands the skeleton back to the AnimationPlayer (a step drops the pose).
func stop() -> void:
	if tree != null:
		tree.active = false
	legs = ""
	arms = ""


func is_posing() -> bool:
	return tree != null and tree.active
