# Lens 5: a headless Blender pipeline driven by Python (no window)

Read on 2026-10-02. `[unconfirmed]` = no primary source opened (memory, a forum post, an inference); everything
else cites the vendor's docs, release index or source code. Blender is not installed on this PC, so no claim below was
run; every API name marked "probe" must be checked by the first script run (`bpy.ops.<op>.get_rna_type().properties`).

## 1. Which Blender to pin

| Fact | Source |
|---|---|
| Maintained LTS series today: **5.2 LTS** (latest 5.2.2, 2026-09-15) and **4.5 LTS** (latest 4.5.14, 2026-09-15); LTS = critical fixes for 2 years | https://www.blender.org/download/lts/ |
| 5.2 LTS released 2026-07-14, supported **until July 2028**; 4.5 LTS released 2025-07-15, supported **until July 2027**; 5.3 is in alpha | https://developer.blender.org/docs/release_notes/ , https://developer.blender.org/docs/release_notes/5.2/ |
| Windows x64 files of 5.2.2: `blender-5.2.2-windows-x64.zip` (404,453,484 B), `.msi`, `.msix`, plus `blender-5.2.2.sha256` | https://download.blender.org/release/Blender5.2/ |
| SHA-256 of `blender-5.2.2-windows-x64.zip` = `3849d17a682cba006075aaa3f3597ecb5c9c30ec31035b2e092c53e40679b535`; Linux `blender-5.2.2-linux-x64.tar.xz` = `84098912789dc450e95697c4184fb8a90acbe5111c2ba4aede3fecb57806a168` (read through a summarizing fetcher: re-copy from the .sha256 file when pinning) | https://download.blender.org/release/Blender5.2/blender-5.2.2.sha256 |
| `bpy` (Blender as a Python module) 5.2.2 on PyPI, Windows x64, **Python 3.13 only**, GPL-3.0 | https://pypi.org/project/bpy/ |

**Breaking Python API changes 4.5 -> 5.x** (why we start on 5.2 rather than learn 4.5 idioms that are already gone):
- 5.0: EEVEE engine id `BLENDER_EEVEE_NEXT` -> `BLENDER_EEVEE`; `scene.node_tree` (compositor) removed, use
  `scene.compositing_node_group`; `ImageFormatSettings.media_type` must be set before `file_format`; the legacy Action
  API (`action.fcurves`, `action.groups`) removed in favour of slots/channelbags
  (`bpy_extras.anim_utils.action_ensure_channelbag_for_slot`); bpy.props no longer share storage with custom properties;
  UV selection layers changed; bone `select` moved to pose bones. https://developer.blender.org/docs/release_notes/5.0/python_api/
- 5.0 platform: NVIDIA minimum sm_50 (GeForce 900), blend-file compression on by default, Intel Mac dropped.
  https://developer.blender.org/docs/release_notes/5.0/
- 5.2: Geometry Nodes modifier property API restructured; `gpu.init()` added "for initializing GPU backend in background
  mode"; `imbuf` gained file read/write and buffer methods; `bpy.data.all_ids`; WindowManager reports exposed as a list.
  https://developer.blender.org/docs/release_notes/5.2/python_api/
- 5.2 glTF: exporter adds EXT/KHR_meshopt_compression, iridescence/dispersion, faster animation export; no option renames
  listed. https://developer.blender.org/docs/release_notes/5.2/pipeline_io/

**Recommendation: pin Blender 5.2.2 LTS, the portable Windows zip.** 4.5 dies a year earlier and every tutorial-era
idiom that differs (scene.node_tree, BLENDER_EEVEE_NEXT, action.fcurves) is removed in 5.x; we have no legacy scripts.
Bump inside 5.2.x freely (a pin + SHA change); jump to the next LTS (5.6? `[unconfirmed]` naming) by ADR.

Zip versus installer: the zip needs no admin, lives side by side with other versions, has a fixed path for
`BLENDER_BIN`, and its SHA-256 is published; the MSI installs into Program Files and associates `.blend` files; MSIX is
the Store-style package. (File list above; the ergonomics are `[unconfirmed]` inference.) `blender.exe` in the zip is
the console executable whose stdout we can capture; `blender-launcher.exe` hides the console `[unconfirmed]`.

**How to pin like Godot** (the game repo pattern: `tools/runner/pins.py` constants + `GODOT_BIN` in
`MACHINE_VARS` of `tools/runner/machine_env.py`, filled from `~/.claude/settings.json` env; `check_godot_version` in
`tools/runner/common.py` matches a version prefix). For the art repo:
- `pins.py`: `BLENDER = "5.2.2"`, `BLENDER_WINDOWS_ZIP = "blender-5.2.2-windows-x64.zip"`,
  `BLENDER_WINDOWS_URL = "https://download.blender.org/release/Blender5.2/blender-5.2.2-windows-x64.zip"`,
  `BLENDER_WINDOWS_SHA256 = "3849d17a…b535"`, and the Linux tar.xz + SHA for CI if CI ever runs Blender.
- `BLENDER_BIN` machine var (absolute path to `blender.exe`), set once in user settings like `GODOT_BIN`.
- `doctor`: run `"%BLENDER_BIN%" -b --factory-startup --python-expr "import bpy,sys;print(bpy.app.version_string);sys.exit(0)"`
  (or `--version`, first line `Blender 5.2.2`), compare with the pin; print the URL, the SHA and the PowerShell command
  `Get-FileHash -Algorithm SHA256 <zip>` as the fix. The human downloads; agents never do.
- Alternative: `pip install bpy==5.2.2` in a dedicated Python 3.13 venv (no exe at all, pinned by pip). Downsides: a
  second Python version next to the project's (PYTHON_MIN 3.11), ~GPU/render parity with the app is not documented,
  and no GUI for the human to open a file. Keep it as the CI option, not the default.

## 2. Running it

Flags from the manual source (https://projects.blender.org/blender/blender-manual/raw/branch/main/manual/advanced/command_line/arguments.rst):
`-b/--background` "Run in background (often used for UI-less rendering)"; `--factory-startup` skips the user's
startup.blend (isolates from personal prefs); `--python-exit-code <n>` "exit if a Python exception is raised (only for
scripts executed from the command line)"; `-P/--python <file>`; `-noaudio`; `--offline-mode` "Disallow internet access";
`--log`, `--log-level`, `--log-file`; `--debug-python`; `-E/--engine`; `-t/--threads`; `--` "End option processing,
following arguments passed unchanged. Access via Python's sys.argv"; `-Y` (default) disables auto-run of scripts inside
.blend files; `--python-use-system-env` is OFF by default (Blender ignores PYTHONPATH/user site-packages, good).

Canonical call (arguments are processed in order: a .blend to open goes before `--python`):
```
"%BLENDER_BIN%" -b [in.blend] --factory-startup -noaudio --offline-mode --python-exit-code 1 ^
  --python tools/blender/check_mesh.py -- --in work/x.glb --report out/x.report.json
```
Failing on errors (design, partly `[unconfirmed]`):
- `--python-exit-code 1` turns an uncaught exception into exit 1; without it Blender exits 0 after a traceback.
- Operators do not raise on failure; they return `{'CANCELLED'}` and push a report. Wrap every op:
  `res = bpy.ops.x.y(**kw); if res != {'FINISHED'}: raise RuntimeError(...)`. Probe operator kwargs with
  `get_rna_type()` so a renamed option fails loudly instead of silently being ignored (an unknown kwarg raises TypeError).
- Each script writes a machine-readable `*.report.json` (stats, errors, warnings) and prints one summary line; the
  runner's verdict is the exit code + the report, as with GdUnit's results.xml. Use `print(..., flush=True)`.
- Guard the version at the top of every script: `assert bpy.app.version[:3] == (5, 2, 2)` (or major.minor).
- The runner adds a timeout and fails on `Error:`/`Traceback` lines, like `run` does for Godot.

## 3. Import

- glTF: `bpy.ops.import_scene.gltf(filepath=..., import_shading='NORMALS', bone_heuristic='BLENDER'|'TEMPERANCE'|'FORTUNE', guess_original_bind_pose=True, merge_vertices=False)` (defaults from the add-on source; add-on version on main is 5.3.36:
  https://raw.githubusercontent.com/KhronosGroup/glTF-Blender-IO/main/addons/io_scene_gltf2/__init__.py). For Meshy GLB
  `bone_heuristic='TEMPERANCE'` usually gives cleaner bone tails `[unconfirmed]`; the rest pose matters, not the tails.
- FBX: `bpy.ops.import_scene.fbx(filepath=..., automatic_bone_orientation=..., ignore_leaf_bones=True)` `[unconfirmed]`
  (probe). Mixamo/Meshy FBX adds `_end` leaf bones; ignore them.
- OBJ: `bpy.ops.wm.obj_import(filepath=...)` (the old `import_scene.obj` is gone since 4.0) `[unconfirmed]`, probe.
- Always import into an empty scene (`bpy.ops.wm.read_factory_settings(use_empty=True)` `[unconfirmed]` probe), then
  save a `.blend` working file next to the source in the private art repo.

## 4. Topology and contract checks (bmesh)

bmesh attributes confirmed in Blender 5.2 source `source/blender/python/bmesh/bmesh_py_types.cc`
(https://raw.githubusercontent.com/blender/blender/blender-v5.2-release/source/blender/python/bmesh/bmesh_py_types.cc):
`BMEdge.is_manifold` ("True when this edge is manifold"), `is_boundary`, `is_wire` ("not connected to any faces"),
`is_contiguous`; `BMVert.is_manifold`, `is_wire`, `is_boundary`; `BMFace.normal`, `calc_area`, `verts`, `loops`;
`BMesh.from_mesh`, `from_object`, `calc_loop_triangles`, `to_mesh`, `normal_update`, `free`.

Check list (one function each in `check_mesh.py`; thresholds come from the contract JSON, not the script):
| Check | How |
|---|---|
| triangle count (after modifiers) | `ob.evaluated_get(depsgraph).to_mesh()`, then `len(bm.calc_loop_triangles())`; total per character vs budget |
| non-manifold | edges with `not e.is_manifold and not e.is_boundary` (3+ faces), boundary edges reported separately (open eyelids/collars may be fine) |
| loose geometry | `v.is_wire` / no `link_faces`; `e.is_wire` |
| n-gons | `len(f.verts) > 4` (glTF triangulates anyway; warn only) |
| degenerate faces | `f.calc_area() < 1e-8` |
| flipped normals | copy the bmesh, `bmesh.ops.recalc_face_normals(bm, faces=bm.faces)` `[unconfirmed]` probe, count faces whose normal dot with the original < 0 |
| UVs present / in 0..1 | `me.uv_layers` non-empty; read `uv_layers.active.uv` via `foreach_get('vector', arr)` into numpy (`[unconfirmed]` attribute path, probe); warn outside [0,1] (tiling may be intended) |
| unapplied transforms | `ob.matrix_world` == identity for mesh and armature; scale exactly 1 |
| origin at the feet / height | world bbox min Z ~ 0 and the object origin at (0,0,0); height = bbox max Z in metres vs contract range |
| materials / textures | material slot count, `image.size` (power of two, <= contract px), images packed or relative |
| skin | per vertex count of groups with weight > 0 (<= 4), weight sum ~ 1, unweighted vertices, vertex groups with no bone |
| shape keys | `me.shape_keys.key_blocks` names vs the contract (blend shapes for faces, if any) |

## 5. Decimation to a budget

Decimate modifier RNA in 5.2 (`rna_modifier.cc`, blender-v5.2-release): `decimate_type`, `ratio` (Collapse),
`iterations` (Un-Subdivide), `angle_limit`, `delimit`, `use_dissolve_boundaries` (Planar/DISSOLVE),
`use_collapse_triangulate`, `use_symmetry`, `symmetry_axis` (Collapse), `vertex_group`, `vertex_group_factor`,
read-only `face_count`. Manual (https://projects.blender.org/blender/blender-manual/raw/branch/main/manual/modeling/modifiers/generate/decimate.rst):
"triangles are used when calculating the ratio"; **Delimit (Normal, Material, Seam, Sharp, UVs) applies only to
Planar, not Collapse**; Collapse has Symmetry, Triangulate and a vertex-group factor.

Recipe: Collapse, `ratio = budget_tris / current_tris`, `use_symmetry=True, symmetry_axis='X'`, a `vertex_group`
weighting the face/hands up so they keep detail; iterate once if `face_count` misses the budget by > 5 %. Collapse
interpolates UVs and tries to keep seams but can smear them `[unconfirmed]`; check UV islands after. Planar with
`delimit={'SEAM','UV','MATERIAL'}` is the tool for flat props (cheap, keeps seams). Gotcha: a modifier cannot be
applied to a mesh with shape keys `[unconfirmed]`: decimate before shape keys and before weights (or re-transfer
weights after). Flat shading for the low-poly look: `Mesh.shade_flat()` `[unconfirmed]` (4.1+); export normals so Godot
keeps it. In practice Meshy's Smart Topology already sets the count; Blender decimation is the fallback, and Godot
generates mesh LODs on import itself `[unconfirmed]` (so no hand LODs).

## 6. Bones: rename and check against the contract

Target names: the game uses Godot's `SkeletonProfileHumanoid` (56 bones, groups Body/Face/LeftHand/RightHand),
verified in the pinned API dump `D:/prime-game/tools/out/godot-api/4.7.2/extension_api.json` (class description):
Root > Hips > {Left|Right}UpperLeg > LowerLeg > Foot > Toes; Hips > Spine > Chest > UpperChest > {Neck > Head > Jaw,
LeftEye, RightEye; {Left|Right}Shoulder > UpperArm > LowerArm > Hand > Thumb{Metacarpal,Proximal,Distal},
{Index,Middle,Ring,Little}{Proximal,Intermediate,Distal}}. Godot's retarget doc: bones point +Y parent->child,
"The humanoid is facing +Z in the Right-Handed Y-UP Coordinate System", T-pose preferred; Rest Fixer has Overwrite
Axis, Fix Silhouette, Apply Node Transform, Normalize Position Tracks
(https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/retargeting_3d_skeletons.html). Blender's -Y forward,
Z up exported with `export_yup=True` lands as glTF +Z forward, Y up `[unconfirmed]` inference, check in the first shot.

**Recommendation:** rename in Blender to the humanoid names, so in Godot the BoneMap is identity and every
character shares one Skeleton3D layout. `rename_bones.py` reads a mapping JSON:
`mixamorig:Hips->Hips, Spine->Spine, Spine1->Chest, Spine2->UpperChest, Neck, Head, LeftShoulder, LeftArm->LeftUpperArm,
LeftForeArm->LeftLowerArm, LeftHand, LeftUpLeg->LeftUpperLeg, LeftLeg->LeftLowerLeg, LeftFoot, LeftToeBase->LeftToes,
LeftHandThumb1..3->LeftThumbMetacarpal/Proximal/Distal, LeftHandIndex1..3->LeftIndexProximal/Intermediate/Distal`
(Mixamo names `[unconfirmed]`, memory; the Meshy report in #165 says its rig uses Mixamo-style names), drops `*_End`
/ `HeadTop_End` leaf bones. Setting `bone.name` through RNA also renames vertex groups and animation paths
`[unconfirmed]` (verify on the first rig: a renamed rig must still deform and play). The authoritative humanoid name
list can be printed by the pinned Godot itself (`SkeletonProfileHumanoid.new()` + `get_bone_name(i)`,
`get_bone_parent(i)`, both in the API dump), so the contract JSON is generated, not typed.

`check_rig.py`: required bones present (contract: the 22-ish body bones; fingers optional), parent of each equals the
profile's parent, total bone count <= budget, all deform bones have `use_deform`, no scale on pose bones, rest pose is
a T-pose (upper-arm direction within N degrees of +-X), armature at origin with scale 1, one armature per character.

## 7. Weights for clothing; rigid accessories

DataTransfer modifier RNA (5.2 source above): `object`, `use_object_transform`, `use_vert_data`, `data_types_verts`,
`vert_mapping`, `layers_vgroup_select_src`, `layers_vgroup_select_dst`, `mix_mode`, `mix_factor`, `use_max_distance`,
`max_distance`. Enum items from the API page (3.4, stable since 2.74): `data_types_verts={'VGROUP_WEIGHTS'}`,
src default `'ALL'`, dst default `'NAME'` (https://docs.blender.org/api/3.4/bpy.types.DataTransferModifier.html);
`vert_mapping='POLYINTERP_NEAREST'` (nearest face, interpolated) `[unconfirmed]` for 5.2, probe. Known pitfall: with
"All Layers" and no generated layers nothing transfers unless the target already has every group
(https://developer.blender.org/T61255), so call the "Generate Data Layers" operator first.

```python
m = cloth.modifiers.new("wt", 'DATA_TRANSFER'); m.object = body
m.use_vert_data = True; m.data_types_verts = {'VGROUP_WEIGHTS'}
m.vert_mapping = 'POLYINTERP_NEAREST'; m.layers_vgroup_select_src = 'ALL'; m.layers_vgroup_select_dst = 'NAME'
with bpy.context.temp_override(object=cloth, active_object=cloth, selected_objects=[cloth]):
    op(bpy.ops.object.datalayout_transfer, modifier=m.name)      # create the groups
    op(bpy.ops.object.modifier_apply, modifier=m.name)
    op(bpy.ops.object.vertex_group_clean, group_select_mode='ALL', limit=0.01)
    op(bpy.ops.object.vertex_group_limit_total, group_select_mode='ALL', limit=4)
    op(bpy.ops.object.vertex_group_normalize_all, group_select_mode='ALL', lock_active=False)
arm_mod = cloth.modifiers.new("Armature", 'ARMATURE'); arm_mod.object = rig   # use_vertex_groups (confirmed RNA)
```
(operator names and kwargs `[unconfirmed]`, probe.) The glTF exporter also caps at `export_influence_nb=4` unless
`export_all_influences=True` (add-on source), but limit + normalize in Blender so what we review is what ships.

Rigid accessories (masks, hats, hand items for review): two options. (a) Parent the object to a bone:
`ob.parent = rig; ob.parent_type = 'BONE'; ob.parent_bone = 'Head'` then restore `ob.matrix_world` (Blender parents to
the bone's **tail**, a classic offset gotcha `[unconfirmed]`); glTF exports it as a child node of the joint, which
Godot's importer turns into a BoneAttachment3D `[unconfirmed]`, check on the first import. (b) Rigid skinning: one
vertex group = the bone, weight 1.0, merged into the skinned mesh. For swappable cosmetics in the game, (a) as separate
GLBs plus Godot `BoneAttachment3D` (exists in 4.7.2 API) on the contract bones is simpler; lens 2 decides.

## 8. Export glTF for Godot 4.7

Exporter properties and defaults from the add-on source (glTF-Blender-IO main, 5.3.36; the 5.2 bundled add-on is one
minor older, probe): `export_format` 'GLB'|'GLTF_SEPARATE' (default GLB), `export_yup` True, `export_apply` False,
`export_skins` True, `export_def_bones` False, `export_influence_nb` 4, `export_all_influences` False,
`export_morph` True, `export_morph_normal` True, `export_morph_tangent` False, `export_animations` True,
`export_animation_mode` 'ACTIONS'|'ACTIVE_ACTIONS'|'BROADCAST'|'NLA_TRACKS'|'SCENE', `export_optimize_animation_size`
True, `export_force_sampling` True, `export_leaf_bone` False, `export_rest_position_armature` True,
`export_reset_pose_bones` True, `export_materials` 'EXPORT', `export_image_format` 'AUTO'|'JPEG'|'WEBP'|'NONE',
`export_cameras`/`export_lights` False, `use_selection`/`use_visible` False, `export_extras` False,
`export_vertex_color` 'MATERIAL', `export_attributes` False, `export_hierarchy_flatten_bones` False,
`export_armature_object_remove` False, `export_anim_slide_to_zero` False, `export_merge_animation` 'ACTION'.

Contract call:
```python
op(bpy.ops.export_scene.gltf, filepath=out, export_format='GLB', use_selection=True, export_yup=True,
   export_apply=True, export_skins=True, export_def_bones=True, export_influence_nb=4,
   export_morph=True, export_morph_normal=True, export_animations=True, export_animation_mode='ACTIONS',
   export_optimize_animation_size=True, export_force_sampling=True, export_leaf_bone=False,
   export_cameras=False, export_lights=False, export_extras=True, export_image_format='AUTO')
```
`export_def_bones=True` matches Godot's advice "Data > Armature > Export Deformation Bones Only needs to be configured to
Enabled" (https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html).
`export_apply=True` is skipped for meshes with shape keys `[unconfirmed]`: apply modifiers in the script first.
One GLB per character body, one per cosmetic piece; animations either in the body GLB or a shared animation-only GLB
on the same skeleton (lens 3).

Godot import hints (https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/importing_3d_scenes/node_type_customization.html):
`-noimp` (dropped), `-col`, `-convcol`, `-colonly`, `-convcolonly`, `-occ`, `-occonly`, `-navmesh`, `-rigid`,
`-vehicle`, `-wheel`; animation names that "start or end with the token loop or cycle" import with loop on; materials
`-alpha`, `-vcol`. Convention: actions `walk_loop`, `idle_loop`, `fall` (one-shot).

Why GLB, not `.blend` in the game repo: Godot's .blend import needs Blender 3.0+ installed on every machine
("using .blend files in your project will require all team members to have Blender installed", same page), and in CI;
glTF 2.0 is Godot's "recommended" format; GLB is one LFS file. FBX imports via ufbx since 4.3 but we gain nothing.

## 9. Review renders without a window

Facts: EEVEE needs a GPU (OpenGL/Vulkan) context; a SURF course (Blender 4.5) says "EEVEE doesn't support headless
rendering on Windows and macOS (and only Linux since 3.4)"
(https://surf-visualization.github.io/blender-course/basics/rendering_lighting_materials/gpu_rendering/, third party,
`[unconfirmed]`). "Headless" there means no display at all; `blender -b` on a logged-in Windows desktop with an NVIDIA
GPU renders EEVEE and Workbench off-screen without a window `[unconfirmed]`, prove with a probe on first install. 5.2
added `gpu.init()` for the GPU backend in background mode (5.2 python_api notes). Cycles on CPU runs anywhere
(CI included) but is slow; Linux CI without GPU can run EEVEE/Workbench only via EGL + Mesa llvmpipe
(https://github.com/HaiyiMei/blender-docker-headless, third party `[unconfirmed]`).

**Recommendation:**
- **Workbench** for the review sheets: deterministic, under a second per view, flat studio light shows silhouette,
  proportions and palette honestly. Settings: `scene.render.engine='BLENDER_WORKBENCH'`,
  `scene.display.shading.light='STUDIO'`, `color_type='MATERIAL'` (or `'TEXTURE'`), `show_object_outline=True`,
  `scene.view_settings.view_transform='Standard'` (AgX would shift the palette), `scene.render.film_transparent=True`,
  `image_settings.media_type='IMAGE'` then `file_format='PNG'`, `color_mode='RGBA'` (5.0 order rule) `[unconfirmed]`
  names except media_type, probe.
- **8 views**: an orthographic camera on an empty at the model's mid-height, empty rotated 0, 45 ... 315 degrees;
  `ortho_scale` = contract max height x 1.1 so every character is drawn at the same scale (proportions comparable
  across assets and versions); 512x512 each.
- **Animation sheets**: per action, 8 evenly spaced frames from the 3/4 front view, one row per action; optional short
  MP4 turntable later.
- **Composition**: Blender bundles numpy `[unconfirmed]`; tile in Blender, or (better, labels) Pillow in the art repo's
  own runner (Pillow, MIT-CMU licence `[unconfirmed]`, a new dependency of the art repo only). Sheet = 4x2 grid,
  2048x1024 PNG + a caption strip: asset, version, git sha, tris, bones, materials, texture px, height m, check verdict.
  Phone-readable, diffable between versions.
- **Final truth in Godot**: the PR into prime-game also shows `tools\run.cmd shot` of a review scene with the imported
  GLB (what players actually see: Forward+, Godot materials). Blender sheets are for iterating drafts in the art repo.
- CI: no Blender renders in CI at first (private repo Actions minutes cost; GPU absent); CI runs the validators.

## 10. Validators outside Blender

- **Khronos glTF-Validator**: Apache-2.0; npm `gltf-validator`, web tool, prebuilt Dart executables for Windows/Linux;
  checks JSON/GLB format, references, accessor bounds and values, images, extensions; writes
  `<asset>.report.json`; "Shell return code will be non-zero if at least one error was found"
  (https://github.com/KhronosGroup/glTF-Validator). Recommend the native exe pinned by SHA (no Node needed).
- **glTF Transform** (`@gltf-transform/cli`): MIT (https://github.com/donmccurdy/glTF-Transform); commands `inspect`
  (geometry/texture/draw-call heaviness), `validate`, `dedup`, `prune`, `weld`, `simplify`, `quantize`, `resize`,
  `meshopt`, `draco` (https://gltf-transform.dev/cli). Needs Node; optional, later (`inspect` as a budget cross-check).

## 11. References (others' pipelines, references only)

- Blender Studio's open pipeline docs https://studio.blender.org/tools/ (content not readable by the fetcher).
- Small open repos doing exactly "pinned headless Blender + GLB validation" (quality unknown, references only):
  https://github.com/Cuvara/web-game-factory/pull/15 , https://github.com/acoliver/gone/issues/45 ,
  https://github.com/larvuz2/poolpanic/pull/14 (rig, walk cycle, turntable preview, glTF).

## 12. Licences

| Thing | Licence | Commercial | Attribution | Public repo |
|---|---|---|---|---|
| Blender 5.2.2 | GPL-3.0-or-later; "What you create with Blender is your sole property" (https://www.blender.org/about/license/) | yes | no (for outputs) | binaries: may be redistributed, but do not commit them; outputs: yes |
| Our bpy scripts | GPL applies **when published** (same page) | yes | n/a | private art repo: fine; if ever public, license them GPL-3.0-or-later |
| glTF-Blender-IO (bundled) | Apache-2.0 `[unconfirmed]` | yes | no | n/a (ships inside Blender) |
| `bpy` PyPI module | GPL-3.0 (https://pypi.org/project/bpy/) | yes | no | do not vendor |
| Khronos glTF-Validator | Apache-2.0 | yes | keep NOTICE if redistributed | yes |
| glTF Transform | MIT | yes | keep notice if redistributed | yes |
| Pillow | MIT-CMU `[unconfirmed]` | yes | keep notice | yes |

## 13. Recommended script set (art repo `tools/blender/`, each `blender -b ... --python <x>.py -- args`)

1. `bl_common.py` - argv after `--`, version guard, `op()` that raises unless FINISHED, JSON report, logging.
2. `import_asset.py` - GLB/FBX/OBJ into an empty scene, apply transforms, origin to feet, save a working .blend.
3. `check_mesh.py` - bmesh topology, UVs, transforms, height, materials, textures, budgets -> report.json, exit 1 on fail.
4. `check_rig.py` - bones vs the contract JSON (names, parents, count, deform, T-pose), weights (<= 4, normalized, no orphans).
5. `rename_bones.py` - mapping JSON (mixamorig -> SkeletonProfileHumanoid), drop leaf `_End` bones.
6. `decimate.py` - Collapse to a triangle budget with symmetry and a protect group; Planar for props; flat shading.
7. `transfer_weights.py` - body -> clothing DataTransfer, clean, limit 4, normalize, Armature modifier.
8. `attach_rigid.py` - parent an accessory to a contract bone (or rigid-skin it) keeping its world transform.
9. `export_glb.py` - the contract export call above; then the Khronos validator on the result.
10. `render_views.py` - 8 orthographic Workbench views, transparent PNGs.
11. `render_anim_sheet.py` - N frames per action from the 3/4 view.
12. runner `sheet` (Pillow) - composes the 4x2 view sheet and animation rows with the caption strip.
Plus `contract/humanoid.json` generated by a pinned-Godot headless script from `SkeletonProfileHumanoid`.

Review render format: `<asset>@<sha>_views.png` (4x2, 2048x1024, Workbench, ortho, Standard view transform, transparent
cells on a neutral grey board), `<asset>@<sha>_anim_<action>.png` (8 frames per row), `<asset>.report.json`, and for the
game PR a Godot `shot` PNG.
