extends RefCounted
## The approved look's directional lights (light D since 2026-10-19, art #196: key 3.0, fill, back, a back rim), read
## from look_presets.json's "lights" (written by `showroom --write-presets` from _showroom.LOOK_LIGHTS), so every
## alien proof renders under the approved look. Each entry: {"name", "at": [x, y, z], "look_at": [x, y, z], "energy",
## "specular", "shadow"}, in the character's model space (front +Z); hero_shots.gd's "lights" spec takes the same form.

const PRESETS_PATH: String = "res://showroom/look_presets.json"


static func directional() -> Array:
	var text: String = FileAccess.get_file_as_string(PRESETS_PATH)
	var doc: Variant = JSON.parse_string(text)
	var out: Array = []
	if not doc is Dictionary:
		push_error("look_lights: cannot read %s" % PRESETS_PATH)
		return out
	var lights: Dictionary = (doc as Dictionary).get("lights", {})
	for name: String in lights:
		var l: Variant = lights[name]
		if l is Dictionary and str((l as Dictionary).get("type", "")) == "DirectionalLight3D":
			var d: Dictionary = (l as Dictionary).duplicate()
			d["name"] = name
			out.append(d)
	return out
