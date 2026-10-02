# Gap agent 3: first-person, spectator and self-view rendering; outline on a custom shader

Read on 2026-10-02. API names checked against `D:/prime-game/tools/out/godot-api/4.7.2/extension_api.json`
(found: `STENCIL_MODE_OUTLINE/XRAY/CUSTOM`, `stencil_mode`, `stencil_outline_thickness`, `FLAG_USE_Z_CLIP_SCALE`,
`FLAG_USE_FOV_OVERRIDE`, `use_z_clip_scale`, `z_clip_scale`, `use_fov_override`, `fov_override`,
`SHADOW_CASTING_SETTING_SHADOWS_ONLY`, `cast_shadow`, `Light3D.shadow_caster_mask`, `BoneAttachment3D.use_external_skeleton`
/ `external_skeleton`, `SpringBoneSimulator3D`, `CENTER_FROM_WORLD_ORIGIN/NODE/BONE`, `no_depth_test`).
Budget: 22 tool calls of 25.

## 1. First-person arms in Godot 4.5-4.7

- **Engine feature (primary):** PR godotengine/godot#93142 (clayjohn), merged 2025-05-22 for **4.5**, adds to
  BaseMaterial3D `use_z_clip_scale`/`z_clip_scale` and `use_fov_override`/`fov_override`, and the spatial-shader vertex
  built-ins `Z_CLIP_SCALE` and `IN_SHADOW_PASS`. Z clip scale "scales the vertex towards the camera to avoid clipping
  into things like walls. Lighting and shadows will continue to work correctly ... but screen-space effects like SSAO
  and SSR may break with lower scales. Try to keep this value as close to 1.0 as possible."
  https://github.com/godotengine/godot/pull/93142 ,
  https://docs.godotengine.org/en/4.7/tutorials/shaders/shader_reference/spatial_shader.html
  -> This is the current engine-native answer to wall clipping and a separate viewmodel FOV, replacing the old
  "second SubViewport/camera for the gun" trick (https://github.com/godotengine/godot-proposals/discussions/8941).
- **ShaderMaterial:** `Z_CLIP_SCALE` is a shader built-in, so a custom shader gets anti-clipping. No FOV built-in is
  documented; the FOV override in a custom shader would mean writing `PROJECTION_MATRIX` in `vertex()` ourselves
  [unconfirmed: not checked in the docs or material.cpp].
- **Separate arms rig vs full body with hidden head:** no official Godot doc or demo recommends either
  [unconfirmed: none found]. Community prior art (https://github.com/benjr70/space-pirates/issues/30,
  https://godotshaders.com/shader/first-person-view-model-shader/) uses separate arms meshes [unconfirmed].
  Inference for the contract: arms cut from the same body mesh and **skinned to the same contract skeleton** (same bone
  names, same glove/sleeve cosmetics), but a **second Skeleton3D instance under the camera** playing a first-person
  animation set (full-body walk cycles look wrong from the eye). The own full body stays as `SHADOWS_ONLY` playing the
  third-person set. This backs Technical decision 7 with an engine mechanism, not with a source that games do it.
- **Near plane:** Z_CLIP_SCALE plus a small `Camera3D.near` handles it; the arms need `cast_shadow` off or they shadow
  the world strangely when z-scaled? [unconfirmed: the PR says shadows keep working].

## 2. Spectating through another player's eyes

- **prime-game today (live repo, client/CLAUDE.md lines 47-52, #168/PR #173):** the spectator's own client draws the
  target from the public snapshot; from a living target's eyes the target's body and the item views at it are hidden,
  and its hand item shows in the spectate camera's first-person hand. So the first-person arms are already a
  spectator-visible thing. Consequence for the contract: **the FP arms rig must be buildable for any peer from public
  data only** (the target's public cosmetic loadout, look pitch, hand item, public strike/use events). Its animations
  arrive at the 20 Hz snapshot rate plus events, so FP gestures seen by a spectator lag the target's own view slightly.
  Cosmetics are public, so no leak (invariant 2) as long as no role-specific arm visuals exist.
- **Other games:** Lethal Company spectators watch the living employee **in third person** (over the shoulder)
  [unconfirmed: fan wiki https://lethal.miraheze.org/wiki/Spectator , Unreal forum
  https://forums.unrealengine.com/t/controllable-third-person-camera-spectating-system-like-in-lethal-company/2213924].
  Competitive shooters (CS2, Valorant) show the target's first-person viewmodel [unconfirmed: memory, no source opened].
  Option for later: a third-person spectate variant would show the full body and cosmetics (more fun for a party game)
  and avoid the FP-arms-for-everyone requirement; current decision (#168) is first-person.

## 3. Seeing your own cosmetics

- Godot primitives (primary, https://docs.godotengine.org/en/4.7/tutorials/rendering/viewports.html): a SubViewport
  can have its **Own World3D** ("useful when you want to instance 3D characters"), Transparent BG, and update modes
  Never/Once/Always/When Parent Visible; "Once" renders one frame then stops ("render an image once and then use the
  texture without incurring the cost of rendering every frame"). A turntable preview in its own small World3D renders
  only the character plus a light: cheap.
- **Mirror cost:** a planar mirror is a second Camera3D rendering the same world into a SubViewport, so roughly a
  second full scene render at the SubViewport's resolution [unconfirmed: third-party
  https://uhiyama-lab.com/en/notes/godot/subviewport-techniques/ ; asset Mirror3D
  https://godotengine.org/asset-library/asset/3983 , license not checked, not to be used without review]. Shadows in a
  SubViewport need `positional_shadow_atlas_size > 0` (official doc). Mitigation: half resolution, `When Parent
  Visible`, a cull mask that drops level clutter, only in the lobby.
- **Recommendation:** lobby customization uses a third-person "dressing" camera or an own-World3D turntable
  SubViewport (cheap, deterministic, also reusable by `tools\run.cmd shot` for review snapshots); a lobby mirror is a
  fun optional prop, lobby only, half resolution. Which party games use a mirror vs a turntable: not researched
  (dropped for budget).

## 4. Outline on a custom ShaderMaterial (stencil)

- **Built-in outline needs shared vertices (primary, StandardMaterial3D docs 4.7):** "Like with the Grow property, for
  the stencil outline to work as expected, the mesh must have connected faces with shared vertices, or 'smooth
  shading'. If the mesh has disconnected faces with unique vertices, or 'flat shading', the mesh will appear to have
  gaps when using a stencil outline." Also: "Materials that write to the stencil buffer are always drawn in the
  transparent pass, so they are subject to the usual transparency limitations."
  https://docs.godotengine.org/en/4.7/tutorials/3d/standard_material_3d.html
- **ShaderMaterial can do it:** `stencil_mode` is a spatial shading-language declaration (modes `read`, `write`,
  `write_if_depth_fail`, `compare_always/equal/not_equal/less/less_or_equal/greater/greater_or_equal` plus a reference
  integer). BaseMaterial3D itself just generates shader text `"stencil_mode read, write, compare_always, %s;\n"` and
  grows the outline pass with `"VERTEX += NORMAL * grow;"` (godot master scene/resources/material.cpp,
  https://raw.githubusercontent.com/godotengine/godot/master/scene/resources/material.cpp). So a custom shader writes
  the stencil in its main pass and puts a second ShaderMaterial in `next_pass` that extrudes and draws where the
  stencil is not equal. Third-party example: https://godotshaders.com/shader/stencil-based-silhouette/ (main:
  `stencil_mode write, compare_always, 1;` next pass: `stencil_mode read, write, compare_not_equal, 1;`) [unconfirmed
  as to exact syntax; license of that snippet not checked; write our own].
  Caveats (primary, spatial_shader docs): "Stencil support is experimental, use at your own risk ... may change in the
  next minor version"; stencil can only be read in the transparent pass.
- **Shared vertices with a custom shader:** the gap problem comes from extruding along the per-vertex NORMAL. A custom
  shader can extrude along a **separately baked smoothed normal** (stored in vertex COLOR, UV2 or CUSTOM0 by the Blender
  export script) while lighting uses the faceted normal; this keeps a faceted look with a gap-free outline [unconfirmed:
  inference + common toon practice, not tested in Godot]. Alternatives: inverted hull (`cull_front`, opaque next pass,
  no stencil, same normal caveat) or a screen-space (depth/normal) outline pass (no mesh requirement, one extra
  full-screen pass, outlines everything). So D3 "smooth vs faceted" is **not forced** by the outline if we own the shader.
- Transparent-pass caveat matters for the character body: if the body material writes the stencil it moves to the
  transparent pass (sorting, no SSAO/SSR on it). The inverted-hull or smoothed-normal outline without stencil keeps the
  body opaque [inference].

## 5. SpringBoneSimulator3D on an accessory skeleton under a BoneAttachment3D

- Primary (https://docs.godotengine.org/en/4.7/classes/class_springbonesimulator3d.html): "Bone movement is calculated
  based on the difference in relative distance between center and bone in the previous and next frames ... if the
  parent Skeleton3D is used as the center, the bones are considered to have not moved if the Skeleton3D moves in the
  world." CenterFrom: `CENTER_FROM_WORLD_ORIGIN` (enum 0), `CENTER_FROM_NODE`, `CENTER_FROM_BONE`. `external_force`
  "is equal to the result when the parent Skeleton3D moves at this speed in the opposite direction". Warning: a
  scaled simulator/skeleton misbehaves.
- Inference: an accessory Skeleton3D under a BoneAttachment3D moves in world space with the body bone, so with the
  world origin as center its spring chains get inertia from the body's motion (they react); with the accessory
  skeleton as center they would not. Default value of `center_from` not stated in the docs [unconfirmed]. Leads, not
  read: godot#110975 jitter with SpringBoneSimulator3D on a physics-interpolated CharacterBody3D
  (https://github.com/godotengine/godot/issues/110975), godot#105616 BoneAttachment3D snapping
  (https://github.com/godotengine/godot/issues/105616). Remote players here are snapshot-interpolated, so jitter risk
  should be probed with a headless test. Simpler alternative: put the spring bones in the body skeleton itself
  (accessory bones as extra bones of the contract skeleton).

## Claim verdicts

1. "Built-in stencil outline needs connected faces and shared vertices" - **confirmed** (StandardMaterial3D docs 4.7,
   quote above). Note it applies equally to Grow and any normal-extrusion outline.
2. "SHADOWS_ONLY on the own body gives a shadow with no head clipping" - **confirmed** for the mechanism: the docs say
   "the actual mesh will not be visible, only the shadows casted from the mesh will be"
   (https://docs.godotengine.org/en/4.7/classes/class_geometryinstance3d.html). Gotcha [inference]: a shadowed light
   at the eye (a flashlight) would be blocked by the invisible head's shadow; `Light3D.shadow_caster_mask` (exists in
   4.7.2 API) plus a dedicated layer for the own body solves it.
3. "Instance uniforms are limited to 16 per shader, with no textures" - **confirmed**: "There is a practical maximum
   limit of 16 instance uniforms per shader"; "Per-instance uniforms do not support textures or arrays, only regular
   scalar and vector types"; `instance_index` 0-15
   (https://docs.godotengine.org/en/4.7/tutorials/shaders/shader_reference/shading_language.html).
4. "Auto mesh LOD on skinned meshes 'may cause issues'" - **confirmed** (wording differs): "The mesh LOD generation
   process is not perfect, and may occasionally introduce rendering issues (especially in skinned meshes)." LOD is
   generated on import for glTF by default (https://docs.godotengine.org/en/4.7/tutorials/3d/mesh_lod.html).

## Licenses (things we might use)

- Godot engine features (Z clip scale, stencil, SpringBoneSimulator3D, SubViewport): MIT, https://godotengine.org/license ,
  commercial yes, attribution: the Godot license notice, public repo ok.
- godotshaders.com snippets / Mirror3D asset: license per item, not checked; use as reading only, write our own.
