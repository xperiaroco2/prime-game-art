extends RefCounted
## Keeps a review window off every screen (art #214). Call `place()` first thing in a window script's _initialize.
##
## Godot 4.7.2 on Windows ignores `--position -30000,-30000` for a new window: DisplayServerWindows::_create_window
## takes the primary screen when the requested rect is on no screen and clamps a windowed window's position into that
## screen's usable area, so the window opens at the screen's top-left corner. Only a runtime
## DisplayServer.window_set_position moves a window without that clamp. So the runner (`_godot.window()`) opens the
## window borderless and unfocused (the project's display/window/size/borderless and no_focus) at 1x1 px
## (`--resolution 1x1`) and passes the size it wants in the PRIME_WINDOW environment variable; place() moves the
## window to POSITION, then grows it, and prints one line the runner checks before it accepts the run:
##   OFFSCREEN window <x>,<y> <w>x<h> screens <x>,<y>,<w>,<h>[;...] ticks <ms since start>
## Measured (#214): the 1x1 px window sits at the screen's corner for about 0.6 s before place() runs; nothing larger
## is ever on screen. Returns "" when placed, else why not (the caller fails with it).
##   const Offscreen = preload("res://lib/offscreen.gd")
##   var err := Offscreen.place()
##   if err != "": _fail(err); return

const POSITION := Vector2i(-30000, -30000)
const ENV := "PRIME_WINDOW"


## The window size the runner asked for (PRIME_WINDOW=<w>x<h>), or ZERO.
static func wanted() -> Vector2i:
	var parts := OS.get_environment(ENV).split("x")
	if parts.size() != 2 or not parts[0].is_valid_int() or not parts[1].is_valid_int():
		return Vector2i.ZERO
	return Vector2i(int(parts[0]), int(parts[1]))


## Moves the main window off-screen, then sizes it (size, else PRIME_WINDOW); "" when it is off every screen.
static func place(size := Vector2i.ZERO) -> String:
	if DisplayServer.get_name() == "headless":
		return "running headless; this script needs a real window (off-screen)"
	var want := size if size != Vector2i.ZERO else wanted()
	if want.x <= 0 or want.y <= 0:
		return "no window size: the runner sets %s=<w>x<h> (tools/runner/commands/_godot.py window())" % ENV
	DisplayServer.window_set_position(POSITION)
	DisplayServer.window_set_size(want)
	return report(want)


## Prints the OFFSCREEN line for the window as it is now; "" when it is off every screen and has the wanted size.
static func report(want := Vector2i.ZERO) -> String:
	var rect := Rect2i(DisplayServer.window_get_position_with_decorations(), DisplayServer.window_get_size_with_decorations())
	var screens := PackedStringArray()
	var on := PackedStringArray()
	for i in DisplayServer.get_screen_count():
		var s := Rect2i(DisplayServer.screen_get_position(i), DisplayServer.screen_get_size(i))
		screens.append("%d,%d,%d,%d" % [s.position.x, s.position.y, s.size.x, s.size.y])
		if s.intersects(rect):
			on.append(str(i))
	var inner := DisplayServer.window_get_size()
	print("OFFSCREEN window %d,%d %dx%d screens %s ticks %d" % [rect.position.x, rect.position.y, rect.size.x,
			rect.size.y, ";".join(screens), Time.get_ticks_msec()])
	if not on.is_empty():
		return "the window %s is on screen %s, not off-screen" % [rect, ",".join(on)]
	if want != Vector2i.ZERO and inner != want:
		return "the window is %s, not the %s asked for" % [inner, want]
	return ""
