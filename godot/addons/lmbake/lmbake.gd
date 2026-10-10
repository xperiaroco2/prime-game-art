@tool
extends EditorPlugin
## `house --bake` (#83; from the lab, art#34). `godot --editor --path godot -- lmbake=res://import/house/bake/x.scn`: opens the scene, selects its
## LightmapGI, presses the editor's bake button, answers the file dialog with <scene>.lmbake, saves and quits.
## Without the lmbake arg it does nothing (so --import runs are unaffected). Needs a real window (off-screen):
## a headless editor reports "lightmap baking is not supported on this GPU".

var scene := ""
var log_path := ""


func _log(s: String) -> void:
	print("LMBAKE ", s)
	if log_path != "":
		var f := FileAccess.open(log_path, FileAccess.READ_WRITE if FileAccess.file_exists(log_path) else FileAccess.WRITE)
		f.seek_end()
		f.store_line(s)
		f.close()


func _enter_tree() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("lmbake="):
			scene = a.substr(7)
	if scene == "":
		return
	log_path = scene.get_basename() + "_bake_log.txt"
	_log("start %s; display %s; adapter %s" % [scene, DisplayServer.get_name(), RenderingServer.get_video_adapter_name()])
	var t := Timer.new()
	t.one_shot = true
	t.wait_time = 4.0
	t.timeout.connect(_go)
	add_child(t)
	t.start()


func _collect(n: Node, cls: String, out: Array) -> void:
	if n.is_class(cls):
		out.append(n)
	for c in n.get_children():
		_collect(c, cls, out)


func _go() -> void:
	EditorInterface.open_scene_from_path(scene)
	await get_tree().create_timer(3.0).timeout
	var root := EditorInterface.get_edited_scene_root()
	var lm: LightmapGI = root.find_children("*", "LightmapGI", true, false)[0]
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(lm)
	EditorInterface.edit_node(lm)
	await get_tree().create_timer(1.5).timeout
	var icon: Texture2D = EditorInterface.get_editor_theme().get_icon("Bake", "EditorIcons")
	var buttons: Array = []
	_collect(EditorInterface.get_base_control(), "Button", buttons)
	var target: Button = null
	for b in buttons:
		if (b as Button).icon == icon and (b as Button).is_visible_in_tree() and not (b as Button).disabled:
			target = b
	if target == null:
		_log("no enabled bake button")
		get_tree().quit(4)
		return
	target.pressed.emit()
	await get_tree().create_timer(1.0).timeout
	var dialogs: Array = []
	_collect(get_tree().root, "EditorFileDialog", dialogs)
	var t0 := Time.get_ticks_msec()
	for d in dialogs:
		if d.visible:
			d.hide()
			d.emit_signal("file_selected", scene.get_basename() + ".lmbake")
	var ms := Time.get_ticks_msec() - t0
	await get_tree().create_timer(1.0).timeout
	_log("bake returned after %d ms; light_data=%s" % [ms, str(lm.light_data.resource_path if lm.light_data else "none")])
	if lm.light_data:
		var data: LightmapGIData = lm.light_data
		var tex = data.get("lightmap_textures")
		_log("lightmap_textures: " + str(tex))
		if tex is Array:
			for x in tex:
				if x is TextureLayered:
					_log("  layers=%d size=%dx%d format=%d" % [x.get_layers(), x.get_width(), x.get_height(), x.get_format()])
	EditorInterface.save_scene()
	await get_tree().create_timer(1.0).timeout
	get_tree().quit()
