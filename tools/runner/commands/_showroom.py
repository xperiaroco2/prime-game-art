"""Helpers for the showroom command (docs/godot.md, "Showroom and recommended look settings", art #140): the look
variants godot/showroom/showroom.gd renders on one character, the spec it reads, the GPU-time table, and the
recommended look per graphics preset (Low / Medium / High / Ultra) the game side can copy. Pure standard library."""

from __future__ import annotations

from typing import Any

from .. import common

OUT = common.OUT / "showroom"
SCRIPT = "res://showroom/showroom.gd"
WINDOW = (640, 800)  # each shot; scaled down into its sheet cell
FACE_CELL = (256, 320)  # 4 columns: about 1040 x 1340 px with the title
BODY_CELL = (320, 400)  # 3 columns: about 980 x 860 px
FACE_YAWS = (0.0, -35.0)  # front and three-quarter from the character's right, as the faces sheets
BODY_YAW = 35.0
BODY_PITCH = 8.0
FOV_DEG = 22.0  # a long portrait lens, close to an orthographic look without its flatness
TIMING_SIZE = (1920, 1080)  # GPU time is measured with the window at this size
TIMING_FRAMES = 30  # averaged after SETTLE_FRAMES (the GPU timer lags a frame or two; the sky's radiance updates)
SETTLE_FRAMES = 6
TIMING_ROUNDS = 3  # every variant measured in turn, this many rounds after a warm-up; the median round counts
WARMUP_FRAMES = 120
HDRI = "env/polyhaven/studio_small_09/studio_small_09_2k.hdr"  # CC0, sources/polyhaven_hdris_2k.toml
# The approved faces sheet of round 4 (art #116), m1's row: the crops of its two right-hand (approved) cells
APPROVED_RECTS = [[218, 0, 214, 258], [668, 0, 214, 258]]

# Every variant sets every key: the order of the grid does not matter. The first run (2026-10-12) lit the sky variants
# with the studio sky at ambient energy 1.0 and the stand's key light: washed out, no shading on the face, no glint in
# the eyes; from the third variant on the sky is dimmer, the key light stronger, and a catch light gives the eyes their
# highlight. The second run's catch light (a directional light, energy 0.1, specular 4.0) left no glint: a sun's
# highlight on eyes of roughness 0.17 is under a pixel. The catch light is now a small spherical area light (an
# OmniLight3D with light_size) on the camera that lights the eye meshes alone (its cull mask, the eye layer). One grid
# (size 0.1, 0.2, 0.35 m by energy 0.3, 1.0, specular 16) chose size 0.2 at energy 0.3: a clear glint on the pupil;
# energy 1.0 blows out the whites.
CATCH = {"catch_energy": 0.3, "catch_specular": 16.0, "catch_size": 0.2}
_STAND = {"tonemap": "linear", "exposure": 1.0, "ambient": "color", "ambient_energy": 0.55, "reflections": False,
          "key_energy": 1.05, "key_specular": 0.15, "catch_light": False, **CATCH, "ssao": False,
          "soft_shadows": False, "sss": False}
_LIT = {**_STAND, "tonemap": "agx", "exposure": 1.0, "ambient": "sky", "ambient_energy": 0.4, "reflections": True,
        "key_energy": 2.0, "key_specular": 0.6, "catch_light": True}
VARIANTS: list[dict[str, Any]] = [
    {"id": "stand", "label": "1 frames stand", **_STAND},
    {"id": "agx", "label": "2 AgX", **{**_STAND, "tonemap": "agx", "exposure": 1.2}},
    {"id": "refl", "label": "3 AgX+sky+catch", **_LIT},
    {"id": "ssao", "label": "4 +SSAO", **{**_LIT, "ssao": True}},
    {"id": "soft", "label": "5 +soft shadows", **{**_LIT, "ssao": True, "soft_shadows": True}},
    {"id": "sss", "label": "6 +SSS clay", **{**_LIT, "ssao": True, "soft_shadows": True, "sss": True}},
]
KEYS = tuple(_STAND)
EFFECTS = ("reflections", "catch_light", "ssao", "soft_shadows", "sss")


def variants(only: str = "") -> list[dict[str, Any]]:
    """The variants named in a comma list of ids (all when empty), in grid order; ValueError on an unknown id."""
    wanted = [v for v in only.split(",") if v]
    ids = [v["id"] for v in VARIANTS]
    unknown = [v for v in wanted if v not in ids]
    if unknown:
        raise ValueError(f"unknown variants {', '.join(unknown)}; known: {', '.join(ids)}")
    return [v for v in VARIANTS if not wanted or v["id"] in wanted]


def spec(character: str, clip: str, hdri: str, chosen: list[dict[str, Any]], beside: str = "",
         rects: list[list[int]] | None = None) -> dict[str, Any]:
    """What showroom.gd renders: per variant the face front and three-quarter and the full body at time 0 of clip,
    then each variant's GPU time; the approved sheet's crops lead the face sheet."""
    if beside and not rects:
        raise ValueError("an approved sheet needs its crop rectangles")
    if not chosen:
        raise ValueError("no variants")
    if len(chosen) > 6:
        raise ValueError("at most 6 variants in one grid")
    face_title = f"{character}   face at {clip} 0.00 s   {len(chosen)} Godot look variants, front and 3/4"
    if beside:
        face_title += "   (first: the approved Blender sheet)"
    return {"character": character, "clip": clip, "hdri": hdri, "variants": chosen, "window": list(WINDOW),
            "fov_deg": FOV_DEG, "face_yaws": list(FACE_YAWS), "body_yaw": BODY_YAW, "body_pitch": BODY_PITCH,
            "face_cell": list(FACE_CELL), "body_cell": list(BODY_CELL), "beside": beside,
            "beside_rects": (rects or []) if beside else [], "face_title": face_title,
            "body_title": f"{character}   full body at {clip} 0.00 s   {len(chosen)} Godot look variants",
            "timing_size": list(TIMING_SIZE), "timing_frames": TIMING_FRAMES, "settle_frames": SETTLE_FRAMES,
            "timing_rounds": TIMING_ROUNDS, "warmup_frames": WARMUP_FRAMES}


def gpu_table(record: dict[str, Any]) -> list[str]:
    """A markdown table of the GPU time per variant (ms, averaged over drawn frames), with the step from the one
    before it and the effects it turns on."""
    rows = record.get("timing", [])
    size = record.get("timing_window", ["?", "?"])
    lines = [f"| Variant | Effects | GPU ms ({size[0]}x{size[1]}) | Step ms |", "|---|---|---:|---:|"]
    previous: float | None = None
    for row in rows:
        ms = float(row["gpu_ms"])
        step = "" if previous is None else f"{ms - previous:+.2f}"
        on = [k for k in EFFECTS if row.get(k)] + ([row["tonemap"]] if row.get("tonemap") else [])
        lines.append(f"| {row['label']} | {', '.join(on) or '-'} | {ms:.2f} | {step} |")
        previous = ms
    return lines


# Godot's soft shadow filter levels (RenderingServer.ShadowQuality, the project setting's values) by index.
STATUS = ("PROPOSAL, NOT CHOSEN: the engineer has not picked a variant (art #140). Variants 3 to 6 still look washed "
          "out next to the approved Blender face (pale hair, little key-light shading); the sky's ambient energy and "
          "the key light are open. Do not copy into the game until this says chosen.")
SHADOW_FILTER = ("hard", "very low", "low", "medium", "high", "ultra")
SHADOW_FILTER_SETTING = "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality"

# The proposed look per graphics preset, not chosen yet (STATUS): what the game will copy once the engineer says yes (godot/showroom/look_presets.json, written by
# `showroom --write-presets`). Each preset turns on everything the one before it does.
LOOK_ENVIRONMENT = {
    "background_mode": "BG_COLOR or BG_SKY (the map's choice; the sky below lights it either way)",
    "sky": "PanoramaSkyMaterial on a studio or the map's HDRI, energy_multiplier 1.0, radiance_size 256",
    "tonemap_mode": "TONE_MAPPER_AGX",
    "tonemap_exposure": 1.0,
    "ambient_light_source": "AMBIENT_SOURCE_SKY",
    "ambient_light_energy": 0.4,
    "reflected_light_source": "REFLECTION_SOURCE_SKY",
}
LOOK_LIGHTS = {
    "key": {"type": "DirectionalLight3D", "energy": 2.0, "specular": 0.6, "shadow": True},
    "fill": {"type": "DirectionalLight3D", "energy": 0.35, "specular": 0.0, "shadow": False},
    "rim": {"type": "DirectionalLight3D", "energy": 0.30, "specular": 0.0, "shadow": False},
    "catch": {"type": "OmniLight3D, a child of the camera at (-0.25, 0.3, 0) (up-left of the view)",
              "energy": CATCH["catch_energy"], "specular": CATCH["catch_specular"],
              "light_size": CATCH["catch_size"], "omni_range": 50.0, "omni_attenuation": 0.0, "shadow": False,
              "light_cull_mask": "the eye layer alone (render layer 20); the eye meshes (material *_eye) on it too",
              "why": "the eyes' glint (fb_eye, roughness 0.17): a small spherical area light, so the glint is a few "
                     "pixels wide; it lights nothing but the eyes"},
}
PRESETS: dict[str, dict[str, Any]] = {
    "Low": {
        "effects": ["agx", "sky_ambient", "sky_reflections", "catch_light"],
        "environment": {"ssao_enabled": False},
        "key_light": {"light_angular_distance": 0.0, "shadow_blur": 1.0},
        "materials": {"clay_subsurf_scatter_enabled": False},
        "project_settings": {
            "rendering/lights_and_shadows/directional_shadow/size": 2048,
            SHADOW_FILTER_SETTING: SHADOW_FILTER.index("low"),  # what variants 1 to 4 measured
            "rendering/environment/subsurface_scattering/subsurface_scattering_quality": 0,
            "rendering/anti_aliasing/quality/msaa_3d": 0,
            "rendering/reflections/sky_reflections/roughness_layers": 6,
        },
    },
    "Medium": {
        "effects": ["agx", "sky_ambient", "sky_reflections", "catch_light", "ssao"],
        "environment": {"ssao_enabled": True, "ssao_radius": 0.6, "ssao_intensity": 1.5},
        "key_light": {"light_angular_distance": 0.0, "shadow_blur": 1.0},
        "materials": {"clay_subsurf_scatter_enabled": False},
        "project_settings": {
            "rendering/lights_and_shadows/directional_shadow/size": 4096,
            SHADOW_FILTER_SETTING: SHADOW_FILTER.index("medium"),
            "rendering/environment/ssao/quality": 1,
            "rendering/environment/ssao/half_size": True,
            "rendering/environment/subsurface_scattering/subsurface_scattering_quality": 0,
            "rendering/anti_aliasing/quality/msaa_3d": 1,
            "rendering/reflections/sky_reflections/roughness_layers": 8,
        },
    },
    "High": {
        "effects": ["agx", "sky_ambient", "sky_reflections", "catch_light", "ssao", "soft_shadows"],
        "environment": {"ssao_enabled": True, "ssao_radius": 0.6, "ssao_intensity": 1.5},
        "key_light": {"light_angular_distance": 1.5, "shadow_blur": 1.0},
        "materials": {"clay_subsurf_scatter_enabled": False},
        "project_settings": {
            "rendering/lights_and_shadows/directional_shadow/size": 4096,
            SHADOW_FILTER_SETTING: SHADOW_FILTER.index("high"),  # what variant 5 measured
            "rendering/environment/ssao/quality": 2,
            "rendering/environment/ssao/half_size": False,
            "rendering/environment/subsurface_scattering/subsurface_scattering_quality": 0,
            "rendering/anti_aliasing/quality/msaa_3d": 2,
            "rendering/reflections/sky_reflections/roughness_layers": 8,
        },
    },
    "Ultra": {
        "effects": ["agx", "sky_ambient", "sky_reflections", "catch_light", "ssao", "soft_shadows", "sss"],
        "environment": {"ssao_enabled": True, "ssao_radius": 0.6, "ssao_intensity": 1.5},
        "key_light": {"light_angular_distance": 1.5, "shadow_blur": 1.0},
        "materials": {"clay_subsurf_scatter_enabled": True, "clay_subsurf_scatter_strength": 0.25,
                      "head_subsurf_scatter_skin_mode": True},
        "project_settings": {
            "rendering/lights_and_shadows/directional_shadow/size": 4096,
            SHADOW_FILTER_SETTING: SHADOW_FILTER.index("high"),  # ultra (5) is not measured
            "rendering/environment/ssao/quality": 3,
            "rendering/environment/ssao/half_size": False,
            "rendering/environment/subsurface_scattering/subsurface_scattering_quality": 2,
            "rendering/anti_aliasing/quality/msaa_3d": 2,
            "rendering/reflections/sky_reflections/roughness_layers": 8,
        },
    },
}


def preset_problems(presets: dict[str, dict[str, Any]] | None = None) -> list[str]:
    """What is wrong with the presets: the four names in order, each turning on at least the effects of the one before
    it, and soft shadow filter levels that are Godot's (0 to 5) and do not go down."""
    presets = PRESETS if presets is None else presets
    problems = []
    if list(presets) != ["Low", "Medium", "High", "Ultra"]:
        problems.append(f"presets {list(presets)}, not Low, Medium, High, Ultra")
    names = list(presets)
    levels = [presets[n].get("project_settings", {}).get(SHADOW_FILTER_SETTING) for n in names]
    for name, level in zip(names, levels):
        if level is not None and level not in range(len(SHADOW_FILTER)):
            problems.append(f"{name}: soft shadow filter {level} is not one of 0 to {len(SHADOW_FILTER) - 1}")
    for (lower, a), (upper, b) in zip(zip(names, levels), zip(names[1:], levels[1:])):
        if isinstance(a, int) and isinstance(b, int) and b < a:
            problems.append(f"{upper}'s soft shadow filter {b} is below {lower}'s {a}")
    for lower, upper in zip(names, names[1:]):
        missing = set(presets[lower]["effects"]) - set(presets[upper]["effects"])
        if missing:
            problems.append(f"{upper} drops {', '.join(sorted(missing))} that {lower} turns on")
    return problems


def presets_document(timing: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The JSON the game side copies: the shared environment and lights, then the presets."""
    doc: dict[str, Any] = {
        "status": STATUS,
        "about": "The proposed character look per graphics preset (see status), from the showroom (prime-game-art #140, "
                 "docs/godot.md 'Showroom and recommended look settings'). Godot 4.7.2, Forward+. Property names are "
                 "Environment, DirectionalLight3D, StandardMaterial3D and ProjectSettings names; 'clay' materials are "
                 "the character materials whose name ends in _clay.",
        "environment": LOOK_ENVIRONMENT,
        "lights": LOOK_LIGHTS,
        "presets": PRESETS,
    }
    if timing:
        doc["measured_gpu_ms"] = {row["id"]: round(float(row["gpu_ms"]), 3) for row in timing}
    return doc
