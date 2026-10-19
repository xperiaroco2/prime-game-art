shader_type spatial;
// Calibration only (art #196 G3b): option C2 with a linear colour matrix on the base colour, used by look.gd's
// "calibrate" mode to find the colour correction that is then baked into the base colour sheets.
#define MICRO_MIX
#define ALBEDO_FIX
#include "res://alien_look/alien_clay.gdshaderinc"
