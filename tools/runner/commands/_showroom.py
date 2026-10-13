"""Helpers for the showroom command (docs/godot.md, "Showroom and recommended look settings", art #140): the look
variants godot/showroom/showroom.gd renders on one character, the spec it reads, the GPU-time table, and the
recommended look per graphics preset (Low / Medium / High / Ultra) the game side can copy. Pure standard library."""

from __future__ import annotations

import math
from typing import Any

from .. import common

OUT = common.OUT / "showroom"
SCRIPT = "res://showroom/showroom.gd"
WINDOW = (640, 800)  # each shot; scaled down into its sheet cell
FACE_CELL = (256, 320)  # 4 columns: about 1040 x 1340 px with the title
BODY_CELL = (320, 400)  # 3 columns: about 980 x 860 px
FACE_CELL_WIDE = (208, 260)  # 6 columns, for more than 14 face shots: about 1280 x 850 px with 3 rows
BODY_CELL_WIDE = (304, 380)  # 4 columns, for more than 6 variants: about 1240 x 830 px
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
AGX_WHITE = 16.29  # Godot 4.7.2's Environment defaults (tonemap_agx_white, tonemap_agx_contrast)
AGX_CONTRAST = 1.25
MAX_VARIANTS = 8
# Step 2's grid (TUNING, T6) made the glint sharp: eye roughness 0.05 (fb_eye exports 0.17), the light 0.06 m at
# energy 0.6, a small bright dot on the pupil like the Blender sheet's instead of a soft blob.
CATCH_STEP1 = {"catch_energy": 0.3, "catch_specular": 16.0, "catch_size": 0.2}
CATCH = {"catch_energy": 0.6, "catch_specular": 16.0, "catch_size": 0.06}
EYE_ROUGHNESS = 0.05
_STAND = {"tonemap": "linear", "exposure": 1.0, "agx_white": AGX_WHITE, "agx_contrast": AGX_CONTRAST,
          "ambient": "color", "ambient_energy": 0.55, "ambient_color": [1.0, 1.0, 1.0], "sky_contribution": 1.0,
          "reflections": False, "key_energy": 1.05, "key_kelvin": 0, "key_specular": 0.15, "clay_specular": 0.5,
          "eye_roughness": -1.0, "catch_light": False, **CATCH, "ssao": False, "soft_shadows": False, "sss": False}
# The sky-lit look of step 1 (2026-10-12): the base of step 2's tuning grid.
_LIT_STEP1 = {**_STAND, "tonemap": "agx", "exposure": 1.0, "ambient": "sky", "ambient_energy": 0.4, "reflections": True,
              "key_energy": 2.0, "key_specular": 0.6, "catch_light": True, **CATCH_STEP1}
# The sky-lit look since step 2 (the recommendation, still a proposal): step 1's with the grid's T3 (sky ambient 0.15,
# the clay's specular 0.1) and T6's eye glint; see TUNING and docs/godot.md. At sky_contribution 1.0 Godot ignores
# ambient_energy (and ambient_color): the sky lights at its own radiance whatever the energy says.
_LIT = {**_LIT_STEP1, "ambient_energy": 0.15, "clay_specular": 0.1, "eye_roughness": EYE_ROUGHNESS, **CATCH}
VARIANTS: list[dict[str, Any]] = [
    {"id": "stand", "label": "1 frames stand", **_STAND},
    {"id": "agx", "label": "2 AgX", **{**_STAND, "tonemap": "agx", "exposure": 1.2}},
    {"id": "refl", "label": "3 AgX+sky+catch", **_LIT},
    {"id": "ssao", "label": "4 +SSAO", **{**_LIT, "ssao": True}},
    {"id": "soft", "label": "5 +soft shadows", **{**_LIT, "ssao": True, "soft_shadows": True}},
    {"id": "sss", "label": "6 +SSS clay", **{**_LIT, "ssao": True, "soft_shadows": True, "sss": True}},
]

# The tuning grid of step 2 (2026-10-13): on variant 4 (sky-lit, SSAO, hard shadows), each row changes only what the
# step-1 findings point at, named in its label: the sky's ambient energy, the clay's specular (its sky reflections),
# a warm and stronger key, AgX's contrast, a glint the eyes catch, a warm ambient, the sky reflections off.
# T2 changed nothing (found after the run): at sky_contribution 1.0 Godot ignores ambient_energy; T7 is the only row
# that lowers the sky's share. Kept as run, so the table matches its sheets.
_T2 = {**_LIT_STEP1, "ssao": True, "ambient_energy": 0.15}
_T3 = {**_T2, "clay_specular": 0.1}
_T4 = {**_T3, "key_kelvin": 4000, "key_energy": 3.0}
_T5 = {**_T4, "agx_contrast": 1.6}
_T6 = {**_T5, "eye_roughness": EYE_ROUGHNESS, **CATCH}
TUNING: list[dict[str, Any]] = [
    {"id": "t1", "label": "T1 base (4 +SSAO)", **{**_LIT_STEP1, "ssao": True}},
    {"id": "t2", "label": "T2 ambient 0.15", **_T2},
    {"id": "t3", "label": "T3 +clay spec 0.1", **_T3},
    {"id": "t4", "label": "T4 +key 4000K x3", **_T4},
    {"id": "t5", "label": "T5 +AgX contrast 1.6", **_T5},
    {"id": "t6", "label": "T6 +eye glint", **_T6},
    {"id": "t7", "label": "T7 T6+warm ambient", **{**_T6, "ambient_color": [1.0, 0.78, 0.6], "sky_contribution": 0.4,
                                                    "ambient_energy": 0.25}},
    {"id": "t8", "label": "T8 T6 sky refl. off", **{**_T6, "reflections": False}},
]
GRIDS = {"ladder": VARIANTS, "tune": TUNING}
KEYS = tuple(_STAND)
EFFECTS = ("reflections", "catch_light", "ssao", "soft_shadows", "sss")


def variants(only: str = "", grid: str = "ladder") -> list[dict[str, Any]]:
    """The variants of a grid (ladder or tune) named in a comma list of ids (all when empty), in grid order; ValueError
    on an unknown grid or id."""
    if grid not in GRIDS:
        raise ValueError(f"unknown grid {grid}; known: {', '.join(GRIDS)}")
    wanted = [v for v in only.split(",") if v]
    ids = [v["id"] for v in GRIDS[grid]]
    unknown = [v for v in wanted if v not in ids]
    if unknown:
        raise ValueError(f"unknown variants {', '.join(unknown)}; known: {', '.join(ids)}")
    return [v for v in GRIDS[grid] if not wanted or v["id"] in wanted]


def kelvin_rgb(kelvin: float) -> list[float]:
    """A light colour (sRGB, 0 to 1) for a colour temperature in kelvin (Tanner Helland's fit of the black body, good
    from 1000 to 40000 K); 0 is plain white."""
    if kelvin <= 0:
        return [1.0, 1.0, 1.0]
    t = min(max(kelvin, 1000.0), 40000.0) / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
    else:
        r = 329.698727446 * (t - 60) ** -0.1332047592
        g = 288.1221695283 * (t - 60) ** -0.0755148492
    if t >= 66:
        b = 255.0
    elif t <= 19:
        b = 0.0
    else:
        b = 138.5177312231 * math.log(t - 10) - 305.0447927307
    return [round(min(max(c, 0.0), 255.0) / 255.0, 4) for c in (r, g, b)]


def layout(cells: int, face: bool) -> tuple[int, list[int]]:
    """The columns and cell size of a sheet of `cells` shots: step 1's 4 face or 3 body columns while they fit (14
    face cells, 6 body cells), else 6 face or 4 body narrower columns: a sheet stays about 1280 px on its long side."""
    if face:
        return (4, list(FACE_CELL)) if cells <= 14 else (6, list(FACE_CELL_WIDE))
    return (3, list(BODY_CELL)) if cells <= 6 else (4, list(BODY_CELL_WIDE))


def spec(character: str, clip: str, hdri: str, chosen: list[dict[str, Any]], beside: str = "",
         rects: list[list[int]] | None = None) -> dict[str, Any]:
    """What showroom.gd renders: per variant the face front and three-quarter and the full body at time 0 of clip,
    then each variant's GPU time; the approved sheet's crops lead the face sheet."""
    if beside and not rects:
        raise ValueError("an approved sheet needs its crop rectangles")
    if not chosen:
        raise ValueError("no variants")
    if len(chosen) > MAX_VARIANTS:
        raise ValueError(f"at most {MAX_VARIANTS} variants in one grid")
    chosen = [{**v, "key_color": kelvin_rgb(v["key_kelvin"])} for v in chosen]
    face_cols, face_cell = layout(2 * len(chosen) + (len(rects or []) if beside else 0), True)
    body_cols, body_cell = layout(len(chosen), False)
    face_title = f"{character}   face at {clip} 0.00 s   {len(chosen)} Godot look variants, front and 3/4"
    if beside:
        face_title += "   (first: the approved Blender sheet)"
    return {"character": character, "clip": clip, "hdri": hdri, "variants": chosen, "window": list(WINDOW),
            "fov_deg": FOV_DEG, "face_yaws": list(FACE_YAWS), "body_yaw": BODY_YAW, "body_pitch": BODY_PITCH,
            "face_cell": face_cell, "face_cols": face_cols, "body_cell": body_cell, "body_cols": body_cols,
            "beside": beside,
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


# The numeric check against Blender (step 2): the face shots' warm pixels (hue 20 to 85 degrees, chroma 5 or more;
# not the grey background, the eye whites or the olive shirt) split into hair (dark, or mid and saturated: brown) and
# skin; per shot the skin's mean L* and chroma, its shading (L* p90 - p10: how much the key light models the face)
# and the hair's mean L*. A guide beside the eye, not a judge: framing and pose differ a little between the sheets.
MEASURES = ("skin_L", "skin_C", "shade", "hair_L")


def tone(lum: float, a: float, b: float) -> str:
    """'hair', 'skin' or '' (not counted) for a CIELAB pixel."""
    chroma = math.hypot(a, b)
    hue = math.degrees(math.atan2(b, a))
    if chroma < 5 or not 20 <= hue <= 85:
        return ""
    return "hair" if lum < 50 or (lum < 65 and chroma > 18) else "skin"


def face_measures(width: int, height: int, px: list[tuple[int, int, int]], lab, grid: int = 160) -> dict[str, float]:
    """MEASURES of one face shot (8-bit RGB pixels) on a grid of about `grid` pixels across; `lab` converts sRGB to
    CIELAB. Shades with fewer than 20 samples count as missing (nan)."""
    step = max(1, width // grid)
    skin: list[float] = []
    chroma: list[float] = []
    hair: list[float] = []
    for y in range(step // 2, height, step):
        for x in range(step // 2, width, step):
            lum, a, b = lab(*px[y * width + x])
            kind = tone(lum, a, b)
            if kind == "skin":
                skin.append(lum)
                chroma.append(math.hypot(a, b))
            elif kind == "hair":
                hair.append(lum)
    nan = float("nan")
    skin.sort()
    out = {"skin_L": nan, "skin_C": nan, "shade": nan, "hair_L": nan}
    if len(skin) >= 20:
        out.update(skin_L=sum(skin) / len(skin), skin_C=sum(chroma) / len(chroma),
                   shade=skin[int(0.9 * len(skin))] - skin[int(0.1 * len(skin))])
    if len(hair) >= 20:
        out["hair_L"] = sum(hair) / len(hair)
    return {k: round(v, 1) for k, v in out.items()}


def mean_measures(shots: list[dict[str, float]]) -> dict[str, float]:
    """The mean of each measure over shots (front and three-quarter)."""
    return {k: round(sum(m[k] for m in shots) / len(shots), 1) for k in MEASURES}


def distance(m: dict[str, float], ref: dict[str, float]) -> float:
    """How far a variant's measures are from Blender's: the sum of the absolute differences (L* and C* units)."""
    return round(sum(abs(m[k] - ref[k]) for k in MEASURES), 1)


def look_table(blender: dict[str, float], rows: list[tuple[str, dict[str, float]]]) -> list[str]:
    """A markdown table: Blender's measures, then per variant its measures, their differences and the distance."""
    lines = ["| Shots | skin L* | skin C* | shade (L* p90-p10) | hair L* | distance |",
             "|---|---:|---:|---:|---:|---:|"]
    lines.append("| Blender (approved) | " + " | ".join(f"{blender[k]:.1f}" for k in MEASURES) + " | 0 |")
    for label, m in rows:
        cells = [f"{m[k]:.1f} ({m[k] - blender[k]:+.1f})" for k in MEASURES]
        lines.append(f"| {label} | " + " | ".join(cells) + f" | {distance(m, blender):.1f} |")
    return lines


# Godot's soft shadow filter levels (RenderingServer.ShadowQuality, the project setting's values) by index.
STATUS = ("PROPOSAL, NOT CHOSEN: the engineer has not approved the look (art #140). Step 2's tuning grid recommends "
          "the clay's specular 0.1 (darker, richer hair) and a sharp eye glint; the face is still brighter and flatter "
          "than the Blender sheet (skin L* +9, shading -7). Do not copy into the game until this says chosen.")
SHADOW_FILTER = ("hard", "very low", "low", "medium", "high", "ultra")
SHADOW_FILTER_SETTING = "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality"

# The proposed look per graphics preset, not chosen yet (STATUS): what the game will copy once the engineer says yes
# (godot/showroom/look_presets.json, written by `showroom --write-presets`). Each preset turns on everything the one
# before it does.
LOOK_ENVIRONMENT = {
    "background_mode": "BG_COLOR or BG_SKY (the map's choice; the sky below lights it either way)",
    "sky": "PanoramaSkyMaterial on a studio or the map's HDRI, energy_multiplier 1.0, radiance_size 256",
    "tonemap_mode": "TONE_MAPPER_AGX",
    "tonemap_exposure": 1.0,
    "ambient_light_source": "AMBIENT_SOURCE_SKY",
    "ambient_light_energy": 0.15,
    "ambient_light_sky_contribution": 1.0,
    "reflected_light_source": "REFLECTION_SOURCE_SKY",
    "why": "at ambient_light_sky_contribution 1.0 Godot ignores ambient_light_energy and ambient_light_color: the sky "
           "lights at its own radiance (step 2's T2, energy 0.4 to 0.15, changed nothing); a weaker sky ambient is "
           "untested",
}
LOOK_LIGHTS = {
    "key": {"type": "DirectionalLight3D", "energy": 2.0, "specular": 0.6, "shadow": True},
    "fill": {"type": "DirectionalLight3D", "energy": 0.35, "specular": 0.0, "shadow": False},
    "rim": {"type": "DirectionalLight3D", "energy": 0.30, "specular": 0.0, "shadow": False},
    "catch": {"type": "OmniLight3D, a child of the camera at (-0.25, 0.3, 0) (up-left of the view)",
              "energy": CATCH["catch_energy"], "specular": CATCH["catch_specular"],
              "light_size": CATCH["catch_size"], "omni_range": 50.0, "omni_attenuation": 0.0, "shadow": False,
              "light_cull_mask": "the eye layer alone (render layer 20); the eye meshes (material *_eye) on it too",
              "why": "the eyes' glint (fb_eye at roughness 0.05, see LOOK_MATERIALS): a small spherical area "
                     "light, so the glint is a small sharp dot; it lights nothing but the eyes"},
}
LOOK_MATERIALS = {
    "clay_metallic_specular": 0.1,
    "eye_roughness": EYE_ROUGHNESS,
    "why": "the clay's specular at Godot's default 0.5 lays the key light's sheen and the sky's reflections over the "
           "roughness-0.8 clay (the hair turns pale brown); 0.1 keeps it matte as in Blender. The eyes (materials *_eye, "
           "exported at roughness 0.17) at 0.05 take the catch light as a sharp glint",
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
        "about": "The proposed character look per graphics preset (see status), from the showroom "
                 "(prime-game-art #140, docs/godot.md 'Showroom and recommended look settings'). Godot 4.7.2, "
                 "Forward+. Property names are "
                 "Environment, DirectionalLight3D, StandardMaterial3D and ProjectSettings names; 'clay' materials are "
                 "the character materials whose name ends in _clay.",
        "environment": LOOK_ENVIRONMENT,
        "lights": LOOK_LIGHTS,
        "materials": LOOK_MATERIALS,
        "presets": PRESETS,
    }
    if timing:
        doc["measured_gpu_ms"] = {row["id"]: round(float(row["gpu_ms"]), 3) for row in timing}
    return doc
