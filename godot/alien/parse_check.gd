extends SceneTree
## M13b (art #196, PR #248's review minor 7): the alien kit's Godot sources parse in Godot 4.7.2, headless: every
## shader under res://alien/ (its uniforms listed through the dummy renderer's parser) and the scripts alien.gd and
## alien_talk.gd (loaded and reloaded). One line "PARSE {...}" for tools/tests/test_alien_parse_godot.py; Godot's own
## error lines ("SHADER ERROR", "Parse Error") go to the log too.
##     godot --headless --path godot -s res://alien/parse_check.gd

const SCRIPTS: Array[String] = ["res://alien/alien.gd", "res://alien/alien_talk.gd"]


## M14 (PR #250's review): with the user argument "broken" it parses one deliberately broken shader instead and
## prints "PARSE_BROKEN {...}" (its uniform count), so the test knows a parse error does show as no uniforms and a
## "SHADER ERROR" line (the check would otherwise only ever see good shaders).
const BROKEN := "shader_type spatial;
uniform float amount = 1.0;
void fragment() { ALBEDO = vec3(not_declared); }
"


## PR #251's review: alien.gd's has_jaw_weight on three made meshes: no vertex colours, alpha 1 everywhere (an
## M13 kit), one vertex below 1 (a jaw weight); and its cache (the same mesh asked twice).
func _jaw_weight_cases() -> Dictionary:
	var A: GDScript = load("res://alien/alien.gd")
	var res := {}
	for case: String in ["none", "alpha_one", "weighted"]:
		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = PackedVector3Array([Vector3.ZERO, Vector3.RIGHT, Vector3.UP])
		if case != "none":
			var c := PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 1), Color(1, 1, 1, 1)])
			if case == "weighted":
				c[2] = Color(1, 1, 1, 0.4)
			arrays[Mesh.ARRAY_COLOR] = c
		var m := ArrayMesh.new()
		m.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		res[case] = [A.has_jaw_weight(m), A.has_jaw_weight(m)]
	res["null"] = A.has_jaw_weight(null)
	return res


func _init() -> void:
	if OS.get_cmdline_user_args().has("broken"):
		var bad := Shader.new()
		bad.code = BROKEN
		print("PARSE_BROKEN ", JSON.stringify({"uniforms": bad.get_shader_uniform_list().size()}))
		quit(0)
		return
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
	out["jaw_weight"] = _jaw_weight_cases()
	print("PARSE ", JSON.stringify(out))
	quit(0)
