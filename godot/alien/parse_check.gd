extends SceneTree
## M13b (art #196, PR #248's review minor 7): the alien kit's Godot sources parse in Godot 4.7.2, headless: every
## shader under res://alien/ (its uniforms listed through the dummy renderer's parser) and the scripts alien.gd and
## alien_talk.gd (loaded and reloaded). One line "PARSE {...}" for tools/tests/test_alien_parse_godot.py; Godot's own
## error lines ("SHADER ERROR", "Parse Error") go to the log too.
##     godot --headless --path godot -s res://alien/parse_check.gd

const SCRIPTS: Array[String] = ["res://alien/alien.gd", "res://alien/alien_talk.gd"]


func _init() -> void:
	var out := {"shaders": {}, "scripts": {}}
	for f: String in DirAccess.get_files_at("res://alien"):
		if not f.ends_with(".gdshader"):
			continue
		var sh: Shader = load("res://alien/" + f)
		var u: Array = sh.get_shader_uniform_list() if sh != null else []
		out["shaders"][f] = {"loaded": sh != null, "uniforms": u.size(), "mode": sh.get_mode() if sh != null else -1}
	for p: String in SCRIPTS:
		var s: GDScript = load(p)
		var err: int = s.reload(true) if s != null else -1
		out["scripts"][p] = {"loaded": s != null, "reload": err, "can_instantiate": s != null and s.can_instantiate()}
	print("PARSE ", JSON.stringify(out))
	quit(0)
