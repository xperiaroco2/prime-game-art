"""The alien parts kit's face constants in one place (art #196, PR #222 review): the face materials, the visemes, the
eyeballs' inward aim and the blink timing. Plain Python (no bpy), read by alien_parts.py and alien_assemble.py inside
Blender and by tools/tests/test_alien_face_constants.py, which checks godot/alien/alien.gd's copies against them.

Colours are sRGB triples; each material is (colour, roughness, specular).
"""
from __future__ import annotations

LIP = (0.82, 0.44, 0.37)  # S9: rf2's warmer coral lips and lid domes (S5: e2's dusty salmon (0.76, 0.45, 0.40))
LIP_ROUGH = 0.6
INNER = (0.25, 0.11, 0.14)  # the open mouths' dark inner cup
TEETH = (0.96, 0.95, 0.90)
# The face materials by their glTF names (alien.gd's FACE): colour, roughness, specular.
FACE = {
    "alien_lip": (LIP, LIP_ROUGH, 0.3),
    "alien_mouth_inner": (INNER, 0.9, 0.08),
    "alien_teeth": (TEETH, 0.4, 0.3),
}
EYE_WHITE = (0.95, 0.93, 0.86)
EYE_SHADE = (0.86, 0.72, 0.64)  # the warm tint the white goes toward in its corners and under the lids
EYE_ROUGH = 0.38
ACCENT = (0.89, 0.42, 0.36)  # knees, elbows, knuckles (S9: the value alien_assemble and alien_hue.gdshader use; it was (0.85, 0.40, 0.36) here)
VISEMES = ("rest", "M", "small", "A", "E", "O")
EYE_AIM_IN = 11.5  # degrees: each eyeball turned inward about its socket's up axis (S5; alien.gd aim_in_deg)
BLINK_MS = {"close": 60.0, "hold": 40.0, "open": 100.0}
BLINK_EVERY_S = (2.0, 6.0)
