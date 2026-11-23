extends SceneTree
## Prints colour profiles of an image: a horizontal line across the beer at a height (share of the mug's box) and a
## vertical line down its middle, as sRGB 0..255 and HSV, sampled at 11 points. Args: <png> <x0> <x1> <y_row> <y0> <y1>
func _initialize() -> void:
	var a := OS.get_cmdline_user_args()
	var img := Image.load_from_file(a[0])
	var x0 := int(a[1]); var x1 := int(a[2]); var yr := int(a[3]); var y0 := int(a[4]); var y1 := int(a[5])
	var row := []
	for i in 11:
		var c := img.get_pixel(x0 + (x1 - x0) * i / 10, yr)
		row.append("%d,%d,%d h%.2f s%.2f v%.2f" % [c.r8, c.g8, c.b8, c.h, c.s, c.v])
	print("PROBE row ", " | ".join(row))
	var col := []
	for i in 11:
		var c := img.get_pixel((x0 + x1) / 2, y0 + (y1 - y0) * i / 10)
		col.append("%d,%d,%d h%.2f s%.2f v%.2f" % [c.r8, c.g8, c.b8, c.h, c.s, c.v])
	print("PROBE col ", " | ".join(col))
	quit(0)
