# Lens 2: customization architecture (modular characters on one skeleton, Godot 4.7.2)

Research agent, art track of prime-game (#165), read-only web research on 2026-10-02. All pages read on 2026-10-02.
API names were checked against `D:/prime-game/tools/out/godot-api/4.7.2/extension_api.json` (grep). `[unconfirmed]`
marks claims resting on memory, a forum, a third-party blog or an inference, not on a primary source I opened.

## 0. API names verified in the 4.7.2 dump

Classes present: `Skeleton3D`, `Skin`, `SkinReference`, `MeshInstance3D`, `BoneAttachment3D`, `BoneMap`,
`SkeletonProfileHumanoid`, `SkeletonModifier3D`, `RetargetModifier3D`, `SpringBoneSimulator3D`, `LookAtModifier3D`,
`BoneConstraint3D`, `AimModifier3D`, `CopyTransformModifier3D`, `ConvertTransformModifier3D`, `IKModifier3D`,
`ChainIK3D`, `TwoBoneIK3D`, `FABRIK3D`, `CCDIK3D`, `JacobianIK3D`, `SplineIK3D`, `BoneTwistDisperser3D`,
`LimitAngularVelocityModifier3D`, `ModifierBoneTarget3D`, `PhysicalBoneSimulator3D`, `XRBodyModifier3D`,
`SkeletonIK3D` (deprecated-era node, still present).

Properties/methods/enums present: `MeshInstance3D.mesh/skin/skeleton`, `BoneAttachment3D.bone_name/bone_idx/override_pose/use_external_skeleton/external_skeleton`,
`RetargetModifier3D.profile/use_global_pose/enable`, `BoneMap.profile`, `ModifierBoneTarget3D.bone_name/bone`,
`SpringBoneSimulator3D.external_force/mutable_bone_axes/setting_count`, `GeometryInstance3D.cast_shadow` with
`SHADOW_CASTING_SETTING_SHADOWS_ONLY`, `set_instance_shader_parameter`/`get_instance_shader_parameter`,
`MeshInstance3D.set_blend_shape_value`, `find_blend_shape_by_name`, `set_surface_override_material`,
`bake_mesh_from_current_skeleton_pose`, `bake_mesh_from_current_blend_shape_mix`, `material_overlay`,
`Skeleton3D.create_skin_from_rest_transforms`, `register_skin`, `set_bone_meta`/`get_bone_meta`,
`modifier_callback_mode_process`, `set_bone_pose_rotation`, `get_bone_global_pose`, `Animation.TYPE_BLEND_SHAPE`,
`Mesh.BLEND_SHAPE_MODE_NORMALIZED/RELATIVE`, `VisualInstance3D.layers`, `set_layer_mask_value`, `Camera3D.cull_mask`.
Not present: a runtime "merge meshes" API (no `merge_meshes`).

## 1. One shared Skeleton3D, several skinned parts

- **How skin binds resolve (confirmed, engine source).** `Skeleton3D` resolves each `Skin` bind by **bone name** when
  the bind has a name, else by index; a missing name prints `ERROR: Skin bind #i contains named bind '<x>' but
  Skeleton3D has no bone by that name.` and falls back to bone 0.
  Source: https://raw.githubusercontent.com/godotengine/godot/4.6-stable/scene/3d/skeleton_3d.cpp (NOTIFICATION_UPDATE_SKELETON).
  Consequence: a clothing part exported separately binds to the shared body skeleton **if its bone names match**,
  and a mismatch produces an `ERROR:` line, which `tools\run.cmd run` already fails on: a free automatic contract check.
- **Import option "Use Named Skins"** decides whether imported skins reference bones by name or by index (confirmed:
  https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html). Keep it on.
- **`MeshInstance3D.skeleton` default changed in 4.6** to an empty NodePath; the old parent default (`..`) needs
  `ProjectSettings.animation/compatibility/default_parent_skeleton_in_mesh_instance_3d` (confirmed:
  https://docs.godotengine.org/en/4.7/classes/class_meshinstance3d.html). prime-game's project.godot does not set it
  (grep). **Gotcha:** a part MeshInstance3D created at runtime must set `skeleton` explicitly or it renders unskinned
  (bind pose). Many pre-4.6 tutorials omit this.
- **A GLB with several meshes on one armature** imports as one `Skeleton3D` with one `MeshInstance3D` child per mesh,
  each with its own `Skin` resource (glTF has one skin per skinned mesh node) [unconfirmed: from experience with the
  glTF importer; verify in the spike with `shot`]. The Advanced Import Settings can save meshes to files.
- **Swapping a part at runtime (recommended pattern):** keep one character scene with `Skeleton3D` (bone names of
  the humanoid profile). For each slot, instantiate a `MeshInstance3D`, set `mesh` and `skin` from the part's
  resources, set `skeleton` to the shared skeleton path. Remove the old one with `queue_free()`. No re-import, no
  second skeleton, animations untouched. [unconfirmed: standard practice; one test in the spike proves it on 4.7.2]
- **Every part GLB must be imported with the same `BoneMap` resource and the same Rest Fixer options**, so that all
  rests and inverse-bind matrices agree after "Overwrite Axis" rewrites the rests [inference, unconfirmed]. The safest
  start is Synty's way: all parts of one body type in one GLB on one armature (see §7), split later once a test shows
  separately imported parts line up.

## 2. Rigid accessories: BoneAttachment3D and sockets

- `BoneAttachment3D` "dynamically copies or overrides the 3D transform of a bone in its parent Skeleton3D";
  `use_external_skeleton` + `external_skeleton` let it live outside the skeleton's children; `override_pose` "may
  cause unintended behavior when used at the same time with SkeletonModifier3D" (confirmed:
  https://docs.godotengine.org/en/4.7/classes/class_boneattachment3d.html). **Rule: never use `override_pose`**.
- **Sockets as Marker3D under BoneAttachment3D, not as extra bones in the rig.** Extra socket bones must exist in
  every source rig (Meshy, Mixamo, hand-made), are not in `SkeletonProfileHumanoid`, and would be dropped or need
  hand mapping in every BoneMap; markers live once in the engineer's character scene and are versioned with the code
  [inference]. Each item scene carries its own `Grip` Marker3D (the point that goes onto the socket), so the per-item
  offset is item data, not character data.
- Rigid accessories cost one draw call each, need no weights, never poke through when they bend, and work on any
  body: the right v1 for masks, hats, glasses, backpacks, the hand item and the belt item (matches #165's proposal).

## 3. Retargeting onto one profile

- `SkeletonProfileHumanoid`: 56 bones in 4 groups (Body, Face, LeftHand, RightHand): `Root, Hips, Spine, Chest,
  UpperChest, Neck, Head, Jaw, LeftEye, RightEye, LeftShoulder, LeftUpperArm, LeftLowerArm, LeftHand, ...fingers,
  LeftUpperLeg, LeftLowerLeg, LeftFoot, LeftToes`, and the Right mirror (confirmed:
  https://docs.godotengine.org/en/4.7/classes/class_skeletonprofilehumanoid.html).
- Import-time retarget: a `BoneMap` with the humanoid profile auto-maps by name patterns; "Overwrite Axis" is "the
  most important option for sharing animations in Godot 4"; "Fix Silhouette" is needed for A-pose models, not for
  T-pose; "Normalize Position Tracks" scales root motion by height; the "Unique Node" skeleton name unifies track
  paths; the profile's reference is a T-pose facing **+Z**, right-handed, Y-up (confirmed:
  https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/retargeting_3d_skeletons.html).
- `RetargetModifier3D` (added in **4.4**, PR https://github.com/godotengine/godot/pull/97824): realtime retarget that
  **keeps the original rests** (overwriting rests "discards the bone rest set in the DCC"); a parent skeleton animated
  in profile space drives child skeletons; `use_global_pose` false allows different body shapes, true requires
  matching bone lengths (confirmed: https://docs.godotengine.org/en/4.7/classes/class_retargetmodifier3d.html).
  Use it as the fallback if Overwrite Axis distorts a Meshy rig or a hand-made rig.
- The duplicate-bone rename (godot#106073) is in #165; I did not re-check it.

### SkeletonModifier3D family and what changed by version
| Version | Added | Use for prime-game |
|---|---|---|
| 4.3 | `SkeletonModifier3D` base, `PhysicalBoneSimulator3D` split out [unconfirmed version detail] | ragdoll (lens 3) |
| 4.4 | `LookAtModifier3D` (angle limits, forward axis), `SpringBoneSimulator3D` (VRM-style wiggle), `RetargetModifier3D` | head and neck follow the relayed pitch; ears, antennae, hair, tails jiggle |
| 4.5 | `BoneConstraint3D` + `AimModifier3D`, `CopyTransformModifier3D`, `ConvertTransformModifier3D` | corrective twist bones, a shoulder pad following a bone |
| 4.6 | IK returns: `IKModifier3D`, `TwoBoneIK3D`, `SplineIK3D`, `ChainIK3D`, `FABRIK3D`, `CCDIK3D`, `JacobianIK3D`, `BoneTwistDisperser3D`, `LimitAngularVelocityModifier3D`; targets can be 3D nodes | left hand onto a carried package, feet on stairs later |
| 4.7 | nothing new for skeletons/characters per the release page (collapsible animation track groups) | — |

Sources: https://godotengine.org/releases/4.4/, https://godotengine.org/releases/4.5/,
https://godotengine.org/releases/4.6/, https://godotengine.org/article/inverse-kinematics-returns-to-godot-4-6/,
https://godotengine.org/releases/4.7/, PRs https://github.com/godotengine/godot/pull/101409 (SpringBone),
https://github.com/godotengine/godot/pull/100984 (BoneConstraint3D). The 4.5 release page I fetched did not mention
SpringBoneSimulator3D; the 4.4 page lists it as new (confirmed 4.4).

**Jiggly accessories:** give a jiggly accessory (bunny ears, antenna, ponytail) its **own small Skeleton3D +
`SpringBoneSimulator3D`** inside the accessory scene, attached rigidly through `BoneAttachment3D`, so the base
skeleton stays exactly the profile [inference; that spring bones react to the parent's global motion when the
skeleton moves via an attachment is unconfirmed; spike it]. Cosmetic only, runs on each client.

## 4. Clothing that bends, hiding the body, blend shapes

- **Weights:** Blender's Data Transfer modifier, Vertex Data > Vertex Groups, mapping "Nearest Face Interpolated"
  (interpolates the nearest source face's vertex values) copies body weights to clothing
  (https://docs.blender.org/manual/en/latest/modeling/modifiers/modify/data_transfer.html, Blender 5.2 LTS manual;
  the mapping sentence confirmed via search snippet). Generate the destination vertex groups first, then apply
  [unconfirmed detail]. Limit 4 influences per vertex (glTF default; the exporter's "Bone influences" setting warns
  that values other than 4 or 8 display wrongly in many viewers:
  https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html, from search snippet).
- **Hiding the body under clothes (options):**
  1. *Split body segments per slot* (head, torso, arms, hands, legs, feet as separate skinned meshes); an outfit part
     declares which segments it replaces. Zero shader cost, no poke-through, the standard modular approach
     (Synty Sidekick ships torso, upper arms, lower arms, hands, hips, legs, feet as separate parts:
     https://syntystore.com/products/sidekick-modular-characters-starter-pack). **Recommended.**
  2. *Delete-under-clothing per outfit* (a body variant per outfit): many meshes, combinatorial. Avoid.
  3. *Shader mask* (a per-instance bitmask uniform; body vertices tagged by vertex colour or UV region are discarded):
     one body mesh, but `discard` makes the body alpha-scissor-like (depth prepass cost) and needs careful seams
     [inference]. Keep as fallback.
- **Poke-through and z-fighting:** clothing pushed out ~1 to 2 cm, same weights as the body under it, no stretchy
  extreme poses; and option 1 removes most of it [practice, unconfirmed].
- **Blend shapes:** glTF morph targets import as mesh blend shapes, exposed as `blend_shapes/<name>` on
  `MeshInstance3D` and animated with `Animation.TYPE_BLEND_SHAPE` tracks (enum confirmed in the dump; the property
  path is from experience [unconfirmed]); set with `set_blend_shape_value(find_blend_shape_by_name(...), w)`.
  Blender cannot apply modifiers to a mesh that has shape keys at export time [unconfirmed: well-known exporter
  limitation]. Body-shape blend shapes force every skinned outfit to carry the same shape keys, or it pokes through:
  **no body-shape blend shapes in v1**. Variety instead from colour, accessories, and (fun, cheap) per-character bone
  scale on `Head` or `Hips` applied by a small client-side modifier [design option for the designer].
  Faces: a texture atlas index (Fall Guys-style faceplates) is cheaper than facial blend shapes; a few mouth/eye
  shapes for emotes are fine later.

## 5. Colour and pattern without new meshes; draw calls

- **Per-instance uniforms:** same material, a different value per `GeometryInstance3D`, set with
  `set_instance_shader_parameter()`; "a practical maximum limit of 16 instance uniforms per shader"; scalars and
  vectors only, no textures/arrays (use a texture array as a normal uniform plus an instance index) (confirmed:
  https://docs.godotengine.org/en/4.7/tutorials/shaders/shader_reference/shading_language.html).
- **Recommended:** one shared character shader for all parts: base colour from a **palette texture** (a row per
  palette, UV or vertex-colour channel picks a "zone"), pattern from a texture array, both chosen by instance
  uniforms `palette_index`, `pattern_index`, `tint`. All players share one material, so Godot's sort by material and
  shader still helps (https://docs.godotengine.org/en/4.7/tutorials/performance/optimizing_3d_performance.html).
- **Draw calls:** each surface of each MeshInstance3D is drawn separately (plus shadow passes); automatic instancing
  exists only in Forward+ and only for identical meshes (same doc). A 6-to-8-part character x 10 players = 60 to 80
  opaque draws plus shadows: small for a desktop Forward+ game [inference]. The doc warns skinning and morphing "can be
  very expensive on some platforms" and suggests fewer polygons and fewer animated meshes on screen.
- **Merging parts into one mesh at runtime:** no built-in skinned merge in Godot (no API in the dump); it would be
  custom SurfaceTool code plus a texture atlas (Unreal's "skeletal mesh merge" and UMA do this)
  [unconfirmed for UE/UMA]. **Not worth it** at 10 players: one part per slot, one surface per part.

## 6. First-person view

- Own body: all own `MeshInstance3D` parts (and head accessories) with `cast_shadow =
  SHADOW_CASTING_SETTING_SHADOWS_ONLY` (enum confirmed), so the player sees their own shadow but no head clipping in
  the camera. First-person arms and the held item stay the existing separate rig (`client/player/first_person_hand.gd`),
  on their own visual layer if needed (`VisualInstance3D.layers`, `Camera3D.cull_mask`).
- Full-body first-person camera (true body awareness) needs a hidden head, animations authored for the camera,
  fixes for clipping and sprint bob: costlier; skip [practice, unconfirmed].
- The spectator camera of a DEAD player and the downed third-person camera see the full body normally.

## 7. How known games do it (what each gives up)

| Game / system | Slots | Technique | What it gives up | Source |
|---|---|---|---|---|
| Among Us | colour, hat, visor, skin, pet, nameplate | 2D layers on one body; colour by palette | no shape variety; everything rigid on one silhouette | https://among-us.fandom.com/wiki/Innersloth_Cosmicube [unconfirmed: wiki] |
| Fall Guys | colour, pattern, face(plate), upper, lower | one bean body, upper/lower costumes, colour+pattern as material params | one body shape; costumes must fit the bean | https://fallguysultimateknockout.fandom.com/wiki/Customization [unconfirmed: wiki; Epic help page 403] |
| Lethal Company | suit | texture swap on one model (mods add suits as PNG files) | almost no shape variety, but zero risk | https://thunderstore.io/c/lethal-company/p/x753/More_Suits/dependants/ [unconfirmed: mod pages] |
| Gang Beasts, Party Animals | head, upper, lower costume parts on one squishy body | rigid-ish parts over a soft body | [unconfirmed: memory only] | — |
| Fortnite / Unreal | head, body, back bling, face accessories | modular skeletal meshes following a leader pose, or merged | needs one rig standard and a strict body-hiding scheme | https://dev.epicgames.com/documentation/en-us/unreal-engine/working-with-modular-characters-in-unreal-engine [unconfirmed: not opened] |
| Synty Sidekick | head, hair, eyebrows, torso, upper/lower arms, hands, hips, legs, feet, attachments (head, face, back, shoulder, elbow, knee, hip) | all parts on one Unity Humanoid rig, toggled; body blend shapes (masc/fem, skinny/heavy, muscular), facial blend shapes; runtime API Unity-only; no Godot support listed | licence forbids sharing source files outside the team: **cannot sit in our public repo** | https://syntystore.com/products/sidekick-modular-characters-starter-pack, https://syntystore.com/pages/one-time-purchase-licence |
| UMA (Unity) | full DNA-driven body + wardrobe | runtime mesh merge + texture atlas | Unity-only, complex | [unconfirmed: memory] |
| Ready Player Me | full avatar service | hosted avatar API | **shut down 31 Jan 2026** after Netflix bought it (Dec 2025); exported GLBs still work | https://variety.com/2025/digital/news/netflix-acquires-ready-player-me-games-avatar-creation-1236612915/ (acquisition); shutdown date from a competitor's blog https://avatarsdk.com/blog/2026/01/15/switch-from-ready-player-me-to-avatar-sdk-fast-familiar-production-ready/ [unconfirmed] |

Lesson: the party games that read best (Among Us, Fall Guys) fix **one body silhouette** and put all variety in
colour, pattern, face and rigid or upper/lower add-ons. That is also the cheapest and the safest for an AI pipeline
(Meshy fuses clothing to the body, #165).

## 8. Networking the loadout

- A loadout is a few small ints: `{color, pattern, face, head, back, upper?, lower?}`, chosen in the lobby, sent as an
  intent (`SetCosmetics(loadout)`), validated by the host, then broadcast to all: cosmetics are **public**, no per-peer
  filtering.
- Host validates: every id exists in the cosmetic catalog (a content Resource list), the id belongs to that slot,
  only in Lobby (or allowed phases), rate limit; unknown id → reject (keep the previous loadout), never crash.
  Clients resolve ids locally; an id missing on a client (version skew) → a default part and a warning.
- Invariant 2 caution: no cosmetic may depend on the role; if a future mode lets a role disguise as another
  player, the *displayed* loadout becomes host-owned gameplay state sent like any other filtered event [inference].
- DOWNED/DEAD bodies keep the loadout (the dead body must be recognisable).

## 9. Licences

| Thing | Licence | Commercial | Attribution | Public repo |
|---|---|---|---|---|
| Godot 4.7.2 (all nodes above) | MIT, https://godotengine.org/license/ | yes | licence notice in the game | yes |
| Blender (tool) | GPL v3+, https://www.blender.org/about/license/ ; your outputs are yours [unconfirmed: not re-read today] | yes | no | yes (outputs) |
| Synty Sidekick / Synty packs | Synty EULA, https://syntystore.com/pages/one-time-purchase-licence | yes, inside a product | no, but no claim of authorship | **no**: "must not share the source files of any Assets outside your team" |
| Ready Player Me | service shut down | — | — | — |
| Meshy outputs | see #165 | paid plan: yes | free plan CC BY | yes on a paid plan (per #165) |

## 10. Draft character contract (for the ADR)

1. **Skeleton:** the shipped skeleton uses `SkeletonProfileHumanoid` bone names (Root, Hips, Spine, Chest,
   UpperChest, Neck, Head, Left/RightShoulder, UpperArm, LowerArm, Hand, UpperLeg, LowerLeg, Foot, Toes); fingers
   optional (fists are fine for low-poly; if present: thumb + one merged finger chain allowed, mapped to Index).
   Source rigs may use Mixamo names; the rename happens at import through one shared `BoneMap` resource in the game
   repo (`res://.../humanoid_bone_map.tres`). No extra bones in the body rig. Skeleton node name unique: `Skeleton3D`
   with "Unique Node" set, so animation track paths are identical for all characters.
2. **Rest pose:** T-pose in the shipped GLB (the profile reference; avoids "Fix Silhouette"). Sources in A-pose are
   allowed only if the import with Fix Silhouette passes the snapshot review.
3. **Axes and scale:** glTF Y-up, character faces **+Z** (the profile's convention), 1 unit = 1 m, feet at y = 0,
   origin between the feet. Height: the designer's call; proposal 1.6 to 1.8 m to match the current capsule
   (the capsule size in `remote_player_body.tscn` must be checked when the ADR is written).
4. **Sockets (Marker3D under BoneAttachment3D, in the engineer's character scene):**
   - `Socket_Head` on `Head`: top of skull, for hats; `Socket_Face` on `Head`: front of face for masks/glasses.
   - `Socket_HandR` on `RightHand`: palm centre, hand item (grip axis along the fingers); `Socket_HandL` on
     `LeftHand`: reserved for two-handed holds and IK later.
   - `Socket_Belt` on `Hips`: right hip, the belt item.
   - `Socket_Back` on `UpperChest` (or `Chest` if the rig lacks it): between the shoulder blades, backpacks/capes.
   Every item and accessory scene has a `Grip` Marker3D placed on the socket. Exact offsets are measured on the
   first base body in the spike (shot from 8 sides).
5. **Slots v1:** `color` (palette index), `pattern` (index), `face` (atlas index), `head` (rigid), `face_acc` (rigid),
   `back` (rigid). **v2:** `upper` and `lower` skinned outfits replacing body segments (requires a segmented body).
6. **Per-part rules:** rigid parts: no skin, ≤ 1 surface, ≤ ~500 to 1,500 triangles, origin at `Grip`. Skinned parts:
   bound only to profile bones, ≤ 4 influences per vertex, weights transferred from the base body, normalized,
   ≤ 1 surface, use the shared character material (no unique materials), triangle budgets per lens 6.
   Body: segmented by slot from day one even in v1 (cheap now, enables v2).
7. **Materials:** one shared character shader; colour/pattern/face via instance uniforms (≤ 16 per shader) and a
   palette texture + texture arrays; flat-shaded look per lens 1.
8. **Customization runtime:** parts swapped by creating MeshInstance3D with `mesh`, `skin` and an explicit `skeleton`
   path; never `override_pose`; jiggle on accessory-local skeletons with SpringBoneSimulator3D; head and neck follow
   the relayed pitch with LookAtModifier3D (cosmetic, client side).
9. **Review loop:** the import of every new part runs `check`/`run` (a named-bind miss is an ERROR line) and a
   `shot` of the base body with the part in T-pose and in two animation frames from 8 sides.

### Open choices and recommendation
- Bone names in the shipped GLB: profile names (rec.) vs Mixamo names. Profile: one name set for all sources,
  BoneMap-native; Mixamo: matches Meshy output with no rename, but every non-Mixamo source needs mapping anyway.
- Rest pose: T (rec.) vs A (better shoulder deformation for clothing; needs Fix Silhouette).
- Retarget: import-time BoneMap + Overwrite Axis (rec.) vs RetargetModifier3D at runtime (fallback; one extra
  skeleton per character).
- Sockets: Marker3D in the character scene (rec.) vs socket bones in the rig.
- Body hiding: segmented body (rec.) vs shader mask.
- Body shape variety: none in v1 (rec.), bone scale variety (designer's fun option), blend shapes (v3, costly).
- Fingers: fist + thumb (rec. for low-poly, fewer bones) vs full 5-finger hands (needed for some emotes like
  pointing, thumbs-up): **a look decision for the humans**.
- Runtime mesh merging: no (rec.).
