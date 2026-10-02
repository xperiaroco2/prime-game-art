# Art track, wave 1: integrated synthesis (draft)

Issue: xperiaroco2/prime-game#165. Date: 2026-10-02. Inputs: lens notes `lens-1` to `lens-6` in this folder.
This draft is evidence and recommendations only. `[unconfirmed]` marks a claim that rests on memory, a summary, a
single weak source or an inference. Live checks made by the synthesis agent are marked "(synthesis check)".

## 0. One-paragraph picture

Everything needed is already in Godot 4.7.2 with no addon. Use one humanoid skeleton with the bone names of
`SkeletonProfileHumanoid`. Variety comes from colour, pattern and face on one shared material, plus rigid
accessories on sockets. In-place animation clips from one shared `AnimationLibrary` drive a layered `AnimationTree`.
Downed and dead bodies get a cosmetic partial ragdoll whose hips stay where the host put the body. The art comes from
a pipeline that does not depend on one generator. Meshy goes first, and a human runs it batch by batch. A headless
Blender 5.2.2 LTS then normalizes every model to our skeleton, budgets and palette. Automatic checks run twice: in
Blender and again in Godot. A human approves rendered sheets in the private art repo before an asset can enter the
public game repo through a PR. AI is good for base bodies, rigid accessories and props. It cannot make clothing that
fits another body, so skinned outfits are a v2 Blender job. The three biggest unknowns can only be settled by
probes: how well a Meshy rig converts to our skeleton, whether a Jolt partial ragdoll is stable, and whether
`blender -b` renders on this Windows PC.

## 1. Where the lenses agree

- **One skeleton, profile names.** Lenses 2, 3, 4 and 5 all choose `SkeletonProfileHumanoid` names (56 bones), with
  every vendor rig converted to them. Lens 5 renames in Blender, so Godot's `BoneMap` becomes an identity mapping.
  Lens 2 keeps the shared BoneMap as a safety net. Sources: docs.godotengine.org/en/4.7 class_skeletonprofilehumanoid
  and retargeting_3d_skeletons; the 4.7.2 API dump.
- **Vendor animation libraries are rig-locked.** Meshy's library works only on Meshy rigs (#165). Tripo's presets
  work only on its `tripo` rig spec (lens 4, one GitHub PR, [unconfirmed]). So vendor libraries can only be a source
  of motions to retarget. They must not be a dependency.
- **Rigid accessories are AI's strength. Skinned clothing is not** (lenses 2 and 4, plus #165). Part segmentation in
  Tripo, Rodin, Hunyuan, CSM and Meshy cuts one fused mesh into pieces. It does not make a garment layer.
- **Cosmetics stay cosmetic** (lenses 1, 2 and 3). Ragdolls, jiggle, talking faces and loadouts run on each client.
  They never depend on role, and a ragdoll never moves the host's body position.
- **The public repo gets CC0 or owned outputs only** (lenses 3, 4 and 6). Mixamo, Rokoko, ActorCore, Unity Asset
  Store, Fab and Synty raw files are traps for a public repo. Free-plan generator outputs never enter the game.
- **Two checks, then a human.** Lens 5 runs a Blender JSON report, lens 6 a Godot GdUnit4 asset suite, and lenses
  1, 5 and 6 all want rendered sheets that a human approves.

## 2. Contradictions and how they resolve

1. **Facing: +Z or -Z?** Lenses 2 and 5 say the character faces +Z. Lens 6's summary says the front is at -Z.
   *Resolution: both are right, at different levels.* In the asset, the front is +Z: `Vector3.MODEL_FRONT =
   Vector3(0, 0, 1)` in the 4.7.2 dump (synthesis check), and this is the SkeletonProfileHumanoid reference. The
   gameplay body faces Godot forward -Z: `remote_player_body.gd` has `HAND_POINT (0.45, 0.95, -0.15)` and
   `CARRY_POINT (0, 0.8, -0.72)` (synthesis check). Lens 6's own check list says the same thing: the asset faces -Y
   in Blender, which is +Z in glTF, and the character scene rotates the model 180 degrees around Y. Contract: asset
   +Z, scene rotation 180 degrees.
2. **Belt side.** Lens 2's draft puts `Socket_Belt` on the right hip. The repo puts the belt item at the **left** hip
   (`BELT_POINT (-0.48, 0.85, 0)` and the doc comment "the belt item at the left hip", synthesis check). The repo
   wins: the belt goes on the left hip, so it stays clear of the right-hand item.
3. **The missing socket.** No lens listed the two-handed **carry** point, but the repo has one (`CARRY_POINT`, the
   package held in front with both hands). The contract adds `Socket_Carry`.
4. **Attach bones in the rig.** Lens 6's Blender check list asks for "attachment bones/empties head, hand_r, belt,
   back". Lens 2 says no extra bones go in the body rig, and that sockets are `Marker3D` under `BoneAttachment3D` in
   the engineer's character scene. Lens 5 warns that glTF children of joints may not import as `BoneAttachment3D`.
   *Lens 2 wins.* Extra bones are not in the profile and would be dropped by the BoneMap. The Blender check verifies
   only that the parent bones (Head, RightHand, LeftHand, Hips, UpperChest) exist.
5. **Jiggle bones.** Lens 3 suggests reserving optional jiggle chains in the character contract. Lens 2 puts them on
   accessory-local skeletons (`SpringBoneSimulator3D`) attached rigidly, so the body stays pure profile. *Lens 2
   wins.* It keeps one identical body skeleton. Whether spring bones react to motion inherited through a
   `BoneAttachment3D` needs a spike.
6. **Flat-shaded faceted look vs the vertex budget vs the outline.** #165 and lens 4 assume a faceted, flat-shaded
   look. Lens 6 caps skinned vertices at 12,000 and notes that flat shading splits vertices up to about 3x the
   triangle count: 8k triangles flat-shaded is about 24k vertices, which breaks the cap. Lens 1's built-in stencil
   outline "needs a mesh with connected faces and shared vertices" (4.7 StandardMaterial3D docs), which flat shading
   breaks. *Resolution:* the budget in §6 assumes smooth normals with toon shading (`DIFFUSE_TOON` plus rim). This
   also fits lens 1's recommended "squishy toy" style, which is rounded and not faceted. If the humans choose a
   faceted look, the triangle target drops to about 4k, or the vertex cap rises to about 20k. That is a style
   decision (§7, D3).
7. **Rest pose: A or T?** #165's trial plan says "a-pose" for Meshy. Lens 2 and lens 5 want a T-pose in the shipped
   GLB (the profile reference, so "Fix Silhouette" is not needed). Lens 4 notes that AccuRIG needs an A-pose input.
   *Resolution:* ship a T-pose. Ask Meshy for a T-pose, which #165 confirms it offers ("a-pose or t-pose"). An A-pose
   source is re-posed to T in Blender and applied as rest, or imported with Fix Silhouette only if the snapshot
   review passes. Update the #165 trial list to say T-pose.
8. **Talking indicator.** Lens 1 wants a mouth from a face atlas or one blend shape. Lens 3 wants a head nod plus a
   jaw bob through an `Add2` layer. Lens 6 forbids body blend shapes and allows at most 12 on a separate head mesh.
   *Merged:* a face-atlas mouth frame chosen by an instance uniform (no blend shape, no jaw weights) plus a small
   additive head nod. Both are driven by the voice level the listener actually plays (lens 1's leak rule).
9. **Fingers.** Lens 2 wants mitten hands with fewer bones. Lens 6 wants to keep finger bones because the libraries
   expect them. *Resolution:* the skeleton always holds all 56 profile bones. Unweighted bones cost only transform
   updates, while skinning cost is per vertex (skeleton.glsl at 4.7.2-stable, lens 6). The mesh may be a mitten
   weighted to Hand plus a thumb chain. The hand shape stays a look decision.
10. **Draw-call estimates.** Lens 2 counts 60 to 80 draws (10 players, one pass). Lens 6 counts about 480 (20 bodies,
    including corpses, times 8 surfaces times 3 passes). These do not conflict: lens 6 counts the worst case and is
    the one to budget against.
11. **Blender licence.** Lens 5 says GPL-3.0-or-later. Lens 6 says GPL-2.0-or-later. *Settled* (synthesis web check,
    blender.org/about/license): the source is "GNU GPL Version 2 or later", and binaries are distributed under "GPL
    Version 3 or later". Outputs, including .blend files, are "your sole property". Published bpy scripts must be
    GPL-compatible. Both lenses were partly right, and the consequence is the same: keep the art repo private, or
    license its scripts GPL-3.0-or-later if it is ever made public.
12. **Quaternius tiers.** Lens 3 read quaternius.com as saying Pro is free and itch.io as charging for it. *Settled*
    (synthesis web check, quaternius.com UAL page): Standard is free and is "60-70%" of the pack. Pro is "an extra
    30-40%". Source adds .blend files. All tiers are "free to use in personal, educational and commercial projects"
    (CC0). "Free to use" is about the licence, not the price. The itch.io prices (Pro $9.99+, Source $14.99+) stand
    [unconfirmed: prices were shown as images].
13. **Meshy low poly.** #165 says the faceted look comes only from flat shading, not from Meshy. Lens 4 found that
    Meshy's page now says Smart Topology "generates the mesh at a low polygon budget from the start" (meshy.ai/features/low-poly).
    Lens 4 is newer and primary, so update #165. The overshoot risk (a 15k request gave about 31k, a single
    independent test) still stands.
14. **Height.** Lens 1's toy proportions and lens 2's option "shorter, squat, 1.4 to 1.6 m" conflict with the repo:
    a 1.8 m capsule with the eye height at 1.6 m (`content/modes/base_mode.tres`, lens 6). A body shorter than the eye
    height puts the remote head below where its owner's camera is, so the aim pitch and the "who is looking at me"
    read lie. *Resolution:* the body stays 1.7 to 1.8 m with the eyes at about 1.6 m. The toy feel comes from
    proportions (a big head, short limbs), not from height, unless the designer changes the eye height and the
    capsule, which is a gameplay change.

## 3. Load-bearing claims

| # | Claim | Confirmed | Sources | What depends on it |
|---|---|---|---|---|
| 1 | `SkeletonProfileHumanoid` has 56 bones (Root, Hips, Spine, Chest, UpperChest, Neck, Head, Jaw, eyes, arms, legs, fingers); a T-pose reference facing +Z, Y-up | yes | 4.7 class docs; API dump | The whole skeleton contract |
| 2 | `Vector3.MODEL_FRONT = (0,0,1)`; the greybox body faces -Z | yes (synthesis check) | API dump; `remote_player_body.gd` | Axes and the 180-degree scene rotation |
| 3 | Skeleton3D binds named Skin binds by bone name; a missing name prints `ERROR: Skin bind #i ...` and falls back to bone 0 | yes | skeleton_3d.cpp at 4.6-stable (lens 2) | The free contract check through `run` and `check` |
| 4 | Since 4.6, `MeshInstance3D.skeleton` defaults to an empty NodePath, so runtime parts must set it | yes | 4.7 MeshInstance3D docs | The part-swap code |
| 5 | `BoneAttachment3D.override_pose` misbehaves alongside `SkeletonModifier3D` | yes | 4.7 docs | The socket rule |
| 6 | 4.4 to 4.6 added LookAtModifier3D, SpringBoneSimulator3D, RetargetModifier3D, BoneConstraint3D, the IK family and TwoBoneIK3D; 4.7 adds nothing for skeletons | yes | release pages; API dump | Head pitch, jiggle, IK later |
| 7 | `PhysicalBoneSimulator3D.physical_bones_start_simulation(bones)` gives a partial ragdoll; it has `influence` | yes | API dump; ragdoll docs | Funny falls without moving the body |
| 8 | Jolt ragdoll limits are pyramid-shaped and strict; open issues #96202, #107461 | no (one blog plus open issues) | strayspark blog; GitHub issues | Ragdoll quality; needs a probe |
| 9 | Forward+ skins on the GPU in a compute shader, 4 weights per set, and every blend shape per vertex each frame | yes | skeleton.glsl at 4.7.2-stable | Vertex and blend-shape budgets |
| 10 | Instance uniforms: at most 16 per shader, no textures | yes | 4.7 shading language docs | Colour, pattern and face on one material |
| 11 | Auto mesh LOD applies to skinned meshes but "may cause issues" there | yes | mesh_lod docs | The LOD plan; distance shots |
| 12 | Meshy paid plan: the customer owns the output; free plan: CC BY 4.0, owned by Meshy | yes (#165) | meshy.ai terms and help | Meshy outputs in a public repo |
| 13 | Meshy Smart Topology generates low poly from the start, 100 to 15k; output can overshoot (15k gave 31k) | yes / no (overshoot is a single test) | meshy.ai/features/low-poly; #165 | Decimation step |
| 14 | Meshy and Tripo animation presets work only on their own rigs | Meshy yes (#165); Tripo no (one PR) | docs.meshy.ai; GitHub PR | A generator-agnostic skeleton |
| 15 | No generator makes a fitted clothing layer | no (an absence across several vendor pages) | lens 4 | Outfits are v2 work in Blender |
| 16 | Quaternius UAL 1 and 2 are CC0; Standard is free (60-70%), Pro and Source are paid | yes (synthesis web check for tiers) | quaternius.com; itch.io | Base animation set in a public repo |
| 17 | Mixamo forbids redistributing raw files | no (Adobe pages 403; search snippets) | helpx.adobe.com Mixamo FAQ | Mixamo stays out of the public repo |
| 18 | GitHub Free LFS: 10 GiB storage plus 10 GiB/month bandwidth per account; every version counts; only deleting the repo frees it | yes | docs.github.com billing for Git LFS; removing files | Drafts stay out of git; CI pointer skip |
| 19 | Private repos on Free: 2,000 Actions minutes; no branch protection | minutes yes; protection no [unconfirmed] | docs.github.com | The art repo's CI and its main-branch guard |
| 20 | Blender 5.2.2 LTS (supported to July 2028); the SHA-256 is published | yes (hash read via a summarizer: re-copy it) | blender.org/download/lts; download.blender.org | The Blender pin |
| 21 | `blender -b` renders Workbench or EEVEE off-screen on this Windows PC | no | third party only | Review sheets from Blender |
| 22 | Blender source is GPL-2.0-or-later, binaries GPL-3.0-or-later; outputs are the user's | yes (synthesis web check) | blender.org/about/license | Art repo privacy and script licence |
| 23 | Steam requires disclosing Pre-Generated AI content | yes | partner.steamgames.com contentsurvey | `ai_generated` in the manifest |
| 24 | Khronos glTF-Validator: Apache-2.0, native exe, non-zero exit on errors | yes | GitHub KhronosGroup/glTF-Validator | Independent GLB check |
| 25 | glTF exporter Python names (`export_def_bones`, `export_influence_nb`, `export_rest_position_armature`, ...) match Blender 5.2's bundled add-on | no (main-branch add-on 5.3.36; 5.2 bundles an older one) | glTF-Blender-IO `__init__.py` | The export script; needs a probe |
| 26 | Separately imported part GLBs line up with the body after Overwrite Axis with the same BoneMap | no (inference) | lens 2 | Separate part files; spike first |

## 4. Recommended end-to-end pipeline

```
[human, paid service, per approved batch]
 1 Generate      Meshy Pro (Tripo as fallback): style-sheet image + fixed prompt prefix, T-pose, Smart Topology
                 3-5k (body) / 300-2,000 (accessory), auto-rig (body only). No game or character names in prompts.
                 Raw download -> local raw/ folder (gitignored); manifest records sha256, service, plan, date, task id.
[agent, art repo, blender -b --factory-startup -noaudio --offline-mode --python-exit-code 1]
 2 import_asset  GLB/FBX in; assert the pinned version; every operator via op() that raises unless FINISHED.
 3 check_mesh    bmesh: triangles, vertices, n-gons, loose, degenerate, non-manifold, UVs, scale, applied transforms,
                 height 1.7-1.8 m, origin at the feet, front -Y (glTF +Z).
 4 decimate      Collapse only if over budget; re-check (UV seams [unconfirmed]).
 5 rig           rename to the profile names (contract/humanoid.json generated by the pinned Godot); add missing
                 profile bones unweighted; re-pose A->T and apply as rest if needed; check_rig against the contract.
 6 weights       limit to 4, normalize, clean < 0.01; for skinned parts DataTransfer from the base body (v2).
 7 palette       drop the AI PBR texture; recolour to the shared palette (method still open: see gaps).
 8 export_glb    fixed contract options: GLB, +Y up, apply modifiers, skins, deform bones only, 4 influences,
                 actions with "_loop" suffix where looping, no leaf bones, no cameras or lights.
 9 validate      Khronos glTF-Validator (exe pinned by SHA) -> report.json; non-zero exit fails.
10 render        Workbench, orthographic, Standard view transform: 8 views at 45 deg, 512 px cells, 4x2 sheet with a
                 caption strip (asset, sha, tris, verts, bones, materials, texture px, height, verdict); animation
                 sheets of 8 frames per clip; one lit EEVEE hero image for style approval. Composed with Pillow.
[human]
11 Approve       art-repo PR with the sheets attached; the designer (look) and the engineer review; the human merges.
                 Manifest gets approved_by, approved_at, approval_pr.
[agent, game repo, task branch]
12 Bring in      .glb (LFS) + .import (shared BoneMap, Use Named Skins on, generate_lods) + docs/credits/<slug>.md
                 (service, plan, date, task id, licence, public_repo_ok, ai_generated, approval_pr).
13 Check         tools\run.cmd check (named-bind misses are ERROR lines) + a GdUnit4 tests/assets suite: bone list
                 and parents, binds, weights <= 4, AABB, facing, surfaces, triangles, vertices, blend shapes,
                 materials, sockets resolve in the character scene, animation names; a 20-body smoke scene logging
                 get_rendering_info. CI: pointer files skipped by default; a path-filtered job pulls LFS with a cache.
14 Snapshot      tools\run.cmd shot: the character at 2, 10 and 20 m, lit and dim rooms, plus a deuteranopia filter;
                 PNGs in the PR description only (not committed).
15 Merge         a human merges into main (or the stage manager into release/m<k>).
```

## 5. Draft character contract (for the foundation ADR)

1. **Skeleton.** The node is named `Skeleton3D` and marked "Unique Node", so track paths are the same for every
   character. It holds all **56 `SkeletonProfileHumanoid` bones**, with exactly the profile's names and parents.
   The list is generated from the pinned Godot with `get_bone_name` and `get_bone_parent`, never typed by hand.
   - **Required with weights (23):** Root, Hips, Spine, Chest, UpperChest, Neck, Head, and Left/Right Shoulder,
     UpperArm, LowerArm, Hand, UpperLeg, LowerLeg, Foot, Toes.
   - **Present, weights optional:** Jaw, LeftEye, RightEye and the finger chains. A mitten mesh is weighted to Hand
     plus the Thumb chain, and optionally one merged chain on Index.
   - No extra bones in the body rig: no sockets, no jiggle, no helpers. At most 64 deform bones and 80 in all (the
     budget).
   - Vendor rigs (Meshy and Tripo, with Mixamo-style names) are renamed in Blender. One shared `BoneMap` resource in
     the game repo, with "Overwrite Axis" on, stays as the import safety net. Duplicate bone names are forbidden
     (godot#106073).
2. **Rest pose.** The shipped GLB is in a T-pose, arms horizontal, palms down. Generate in a T-pose. An A-pose source
   is re-posed in Blender, or imported with Fix Silhouette only if the review passes.
3. **Axes and scale.** glTF Y-up, 1 unit = 1 m. The model front is **+Z** (`Vector3.MODEL_FRONT`), which is -Y in
   Blender. Feet at y = 0, origin at the centre between the feet. Height 1.7 to 1.8 m. The eyes sit at about 1.6 m,
   matching `eye_height_m`. The body fits the capsule: 1.8 m tall, radius 0.4 m. The character scene rotates the
   model 180 degrees around Y so the body faces Godot forward -Z, like the greybox. Apply all transforms. All
   animation clips are in place, with no root motion.
4. **Sockets.** Each socket is a `Marker3D` under a `BoneAttachment3D` in the engineer's character scene, never with
   `override_pose`. Every item or accessory scene has its own `Grip` Marker3D that lands on the socket.

   | Socket | Bone | Where | Used by |
   |---|---|---|---|
   | `Socket_Head` | Head | top of the skull | hats |
   | `Socket_Face` | Head | front of the face | masks, glasses |
   | `Socket_HandR` | RightHand | palm centre, grip axis along the fingers | the hand item (knife, ...) |
   | `Socket_HandL` | LeftHand | palm centre | reserved: two-hand IK later |
   | `Socket_Carry` | Chest (or the body root) | in front at chest height (greybox `(0, 0.8, -0.72)`) | two-handed carry (package) |
   | `Socket_Belt` | Hips | **left** hip (greybox `(-0.48, 0.85, 0)`) | the belt item |
   | `Socket_Back` | UpperChest | between the shoulder blades | backpacks, capes |

   Exact offsets are measured on the first base body, from 8-side shots.
5. **Customization slots.** v1: `color` (a palette index), `pattern` (an index), `face` (an atlas index), and three
   rigid slots, `head`, `face_acc` and `back`. The hand and belt items are gameplay items, not cosmetics. v2: skinned
   `upper` and `lower` outfits that replace body segments. That is why the body is modelled in segments from day
   one: head, torso, upper arms, lower arms with hands, hips, legs with feet. A loadout is a few slot ints sent as a
   lobby intent and validated by the host. It is public. No cosmetic may depend on role. A future disguise mechanic
   would make the displayed loadout host-owned filtered state.
6. **Per-part rules.** Rigid parts: no skin, one surface, origin at `Grip`, within their triangle budget (§6), the
   shared character material. Skinned parts: bound only to profile bones, at most 4 normalized influences, weights
   transferred from the base body, one surface, the shared material. No blend shapes on the body.
7. **Material and style.** One shared character shader on smooth normals: `DIFFUSE_TOON`, rim, and an emissive
   accent for dim rooms. It uses instance uniforms (at most 16): `player_color`, `pattern_index`, `face_index`,
   `mouth_frame`, `talk_level`. It reads a 256x256 palette texture plus texture arrays for patterns and faces. An
   outline (stencil or inverted hull) is optional and only added if the shots show poor separation. The style
   itself (A, B or C, flat or faceted) is the humans' decision (§7).
8. **Animation contract.** One shared `AnimationLibrary` on the contract skeleton. Clip names come from a fixed list
   (§8), with `_loop` on looping clips. The remote tree: a Body state machine (Ground BlendSpace2D, Air, Downed
   BlendSpace1D, BeingRaised, Raising, Knockdown, Dead), then an UpperBody `Blend2` (Hold), an Action `OneShot`, an
   Emote `OneShot`, and a Talk `Add2`, followed by the modifiers `LookAtModifier3D` (pitch),
   `SpringBoneSimulator3D` (accessories) and `PhysicalBoneSimulator3D` (partial ragdoll, hips animated).
9. **Review loop.** Blender check report plus validator, then the 8-view and animation sheets with a human approval
   in the art repo. In the game repo: `check`, the asset tests, and shots at 2, 10 and 20 m, lit and dim, plus
   deuteranopia, with the PNGs in the PR. A human merges.
10. **Provenance.** Every asset has a manifest: id, kind, slot, source_service, plan, generated_at, task_ids,
    raw_sha256, tools, license, license_url, public_repo_ok, ai_generated, approved_by, approved_at and approval_pr.
    The game's `docs/credits/<slug>.md` copies the public fields. Free-plan outputs and restricted-licence files never
    enter the game repo.

## 6. Draft budgets (10 players; worst case about 20 skinned bodies on screen)

| Item | Target | Hard cap |
|---|---|---|
| Assembled character, LOD0 (body plus worn parts) | 8,000 tris | 12,000 tris |
| Base body | 5,000 tris | 6,000 |
| Head accessory or mask, back item, belt item | 800 tris each | 1,200 |
| Hand item, third person / first person | 1,500 / 3,000 tris | 2,000 / 4,000 |
| Prop (crate, package) | 500 to 1,500 tris | 2,000 |
| Skinned vertices per assembled character | 8,000 | 12,000 (with smooth shading; faceted look: see §2, item 6) |
| Bones | 56 (the profile) | 64 deform, 80 total |
| Weights per vertex | 4, normalized, none below 0.01 | 4 |
| Blend shapes | 0 on the body | 12 on a separate head mesh (v1 uses none: the face is an atlas) |
| Surfaces per assembled character | 6 | 8 |
| Materials | 1 shared character material | 1 unique per part |
| Textures | 256 palette; pattern and face arrays at 256 per layer | character 1024, accessory 512, power of two, VRAM-compressed, no normal maps |
| All character textures in VRAM | | 64 MB |
| LOD | auto LOD at about 50% and 25%, checked by shots at 10 and 30 m | turn it off per mesh if it tears |
| Files | | character .glb 5 MB, accessory 1 MB, animation library 10 MB |
| Runtime | AnimationTree off for corpses and off-screen bodies; parts under 10 cm cast no shadow | |
| Frame gate (20-body smoke scene) | report draw calls, primitives and frame time | fail above about 600 draws or 1M primitives; frame time is reported, not asserted |
| Readability | a character reads at 20 m at 1080p (about 86 px tall) | 2 identifiers per player: colour plus a silhouette or pattern cue |
| LFS | curated sources and approved exports only | alert at 5 GiB of the 10 GiB shared quota |

The numbers are the manager's technical choice, set from lens 6. The 860M iGPU figure is unmeasured: the smoke scene
on that laptop sets the final cap.

## 7. Decisions for the humans (merged, plain words)

- **D1. Overall look.** A: squishy toy crew (big head, short limbs, bright colours). B: workwear crew with screen
  faces. C: wobbly blank mannequins. *Recommendation: A, optionally with B's customizable face plate.* It reads best
  from far away, is the cheapest to produce, and is goofy and welcoming for a mixed audience.
- **D2. Faces and showing who talks.** Fixed cartoon eyes plus a talking mouth; a screen face with a chosen
  emoticon; no face. *Recommendation: cartoon eyes and a mouth that moves only with the voice you actually hear,
  plus a small head nod, with face styles to pick from.* You can see who is talking, it is funny, and it costs
  little.
- **D3. Smooth or faceted.** Smooth rounded toy shading (with an optional outline later); faceted, flat-shaded low
  poly. *Recommendation: smooth.* It fits look A, halves the vertex cost, and keeps the cheap built-in outline
  possible.
- **D4. Colours.** Saturated characters on muted levels; everything saturated; muted plus a lo-fi filter.
  *Recommendation: saturated characters on muted levels, from one shared palette, with every player also getting a
  second cue besides colour (a big accessory or a pattern, plus colour and name shown on aim).* Ten players is more
  than any colour-blind-safe set of colours. Among Us had to add this later.
- **D5. Body shape and height.** One body shape with variety from colour, pattern, face and add-ons; plus funny
  proportions by bone scaling later; body sliders. And the height: about 1.75 m with toy proportions, or a shorter
  squat body, which would also mean a lower eye height and capsule (a gameplay change). *Recommendation: one shape at
  about 1.75 m; toy feel from proportions; bone-scale fun later within plus or minus 10% so the hitbox still looks
  fair.*
- **D6. Hands.** Mitten with a thumb, or five fingers. *Recommendation: mitten with a thumb.* The skeleton keeps the
  finger bones either way, so gestures like pointing still work if we change our minds.
- **D7. v1 customization.** Colour, pattern, face, hat, face accessory, back; plus skinned outfits; colour only.
  *Recommendation: the six rigid and material slots now; outfits in v2.*
- **D8. Deaths and knockdowns.** A floppy ragdoll after a short fall clip; a canned cartoon animation only; both.
  *Recommendation: both.* A canned fall, then floppy limbs. The body stays exactly where the game put it.
- **D9. Animation feel.** Cartoony and exaggerated, or realistic mocap. *Recommendation: cartoony.*
- **D10. Money and subscriptions.**
  - Meshy Pro: about $20 a month, 50% off the first month, for the trial evening.
  - Tripo: only if Meshy disappoints, about $19.9 a month.
  - Quaternius animations: Standard is free; Pro is about $10 once; Source is about $15 once.
  - No video-to-motion service (about $15 a month or more), no Synty pack.
  - GitHub stays on Free.
  - *Recommendation:* Meshy Pro for one month. Quaternius Standard first, and Pro only if a needed clip is missing.
    Nothing else for now.
- **D11. AI training and legal exposure.** Meshy (below Enterprise) and Rodin may train on uploads and outputs. AI
  output may not be copyrightable, and there is no non-infringement warranty. Steam requires disclosing AI-made
  content that ships. *Recommendation: accept all three for a hobby project.* Keep unreleased key art out of uploads.
  Never put another game's or character's name in a prompt. Record `ai_generated` per asset so the Steam disclosure
  is easy.
- **D12. Where raw drafts live.** Your own disk plus a cloud drive you already have; art-repo LFS; paid object
  storage. *Recommendation: your disk plus an existing cloud drive, with only a manifest in git.* LFS storage can
  never be freed, and both repos share 10 GiB.
- **D13. What review sheets look like on the phone.** Flat 8-view sheets; lit renders; both. *Recommendation: both.*
  Flat 8-view sheets for every draft, plus one lit hero image for style approval.
- **D14. (Already in your request.)** Create the private repo `xperiaroco2/prime-game-art` only with your separate
  "yes".

## 8. Technical decisions (manager; announced, not asked)

1. The generator-agnostic pipeline of §4. Meshy first, Tripo as the fallback (API V3 only), Sloyd as the props
   fallback. Skip Rodin, CSM, Hitem3D, Genie, Kaedim, Hunyuan and local weights for now.
2. Re-rig and rename every body to the contract's 56 profile bones in Blender. The shared BoneMap is a safety net.
3. T-pose rest; asset +Z; a 180-degree scene rotation; in-place clips; `root_motion_track` empty.
4. Sockets are `Marker3D` under `BoneAttachment3D`, with a `Grip` marker on each item. No `override_pose`. No
   socket or jiggle bones in the body rig.
5. Runtime part swap: a new `MeshInstance3D` with mesh, skin and an explicit skeleton path. No runtime mesh merge.
6. One shared character shader with instance uniforms, a palette texture and texture arrays.
7. Own body: a full-body instance set to shadows only, plus first-person arms on the same skeleton and library
   (arms-only visible), replacing the current greybox hand over time.
8. Layered AnimationTree (§5.8), 0.15 to 0.25 s crossfades, `travel()` for host events. Head pitch through
   `LookAtModifier3D`. Jiggle through `SpringBoneSimulator3D` on accessory-local skeletons. TwoBoneIK3D later for
   two-handed holds.
9. Partial ragdoll with the hips animated. CONE joints for shoulders, hips and neck; HINGE for elbows and knees.
   About 11 bones. `influence` tweened back for DOWNED; settle, then freeze for DEAD. No active ragdoll.
10. Animation base: Quaternius UAL 1 and 2 (CC0). The Meshy library fills gaps only on owned paid outputs after its
    terms are checked. Small clips are keyed by Blender Python. Mixamo is for private prototyping only.
11. Pin Blender 5.2.2 LTS as the portable zip, with SHA-256, a `BLENDER_BIN` machine variable and a doctor check, in
    the art repo. One invocation shape. `op()` raises unless FINISHED. A JSON report per script. No Blender in CI at
    first. bpy from PyPI is the later CI option.
12. Review renders in Workbench, plus one optional EEVEE hero frame; Cycles CPU as the fallback. Sheets composed with
    Pillow.
13. Khronos glTF-Validator as a pinned native exe. gltf-transform is optional later.
14. Checks run in both Blender and Godot (a GdUnit4 `tests/assets` suite).
15. LFS in CI: option C (skip pointer files by default; a path-filtered job with a cached LFS pull).
16. Auto mesh LOD, verified by distance shots. Visibility-range LODs only as a fallback.
17. Approval is recorded through an art-repo PR review plus manifest fields. The game-repo gate refuses an asset with
    no `approval_pr`.
18. Art repo layout: `assets/<kind>/<name>/{manifest.toml, source/, export/, report.json}`, with `raw/` gitignored.
    Review PNGs go as PR attachments, or only the last approved revision is kept.
19. Every credits entry records the tool, model version, paid plan, date, terms URL and `public_repo_ok`. `check`
    refuses a licence outside an allowlist (CC0, CC BY, owned paid output, MIT/Apache tools).

## 9. Top risks

1. **Meshy rig to contract conversion.** Non-standard spine and clavicle names and hip weights 5 to 15 cm off (one
   blog) could mean a manual re-rig per body. *Mitigation:* a probe in the first wave on the trial output. AccuRIG
   2, run by a human, is the fallback, and one well-made base body is reused for all characters.
2. **Blender is not installed, and headless rendering on Windows is unproven.** No sheets means no review loop.
   *Mitigation:* the first art-repo task is a probe of operator kwargs plus one Workbench and one EEVEE frame. The
   Godot `shot` is the fallback sheet renderer.
3. **A licence trap enters the public repo** (Mixamo, store packs, Meshy clips of unclear origin, free-plan
   outputs). History rewrites are impossible for LFS short of deleting the repo. *Mitigation:* `public_repo_ok` in
   the manifest and in credits, an allowlist enforced by `check`, and restricted sources kept in the private repo.
4. **The shared 10 GiB LFS quota runs out** through drafts, renders or CI bandwidth, and the game repo then cannot
   push assets. *Mitigation:* raw/ stays out of git, renders go as PR attachments, CI skips pointer files, and an
   alert fires at 5 GiB.
5. **Hidden information leaks through cosmetics.** A mouth moving for a voice the listener cannot hear, or a cosmetic
   tied to role. *Mitigation:* drive the mouth only from the audio the listener actually plays. Loadouts never depend
   on role.
6. **Jolt partial-ragdoll jitter, or drift away from the host's position.** *Mitigation:* tight limits, few bones,
   hips animated, a headless probe, and canned falls as the fallback.
7. **Separately imported parts misalign after Overwrite Axis.** *Mitigation:* rename in Blender so the map is an
   identity, start with all parts of a body in one GLB, and spike with 8-side shots.
8. **Readability failures.** Ten colours, dim rooms, colour-blind players. *Mitigation:* a second identifier, rim
   and emissive accents, dim-room and deuteranopia shots.
9. **Look-alike or asset-flip perception** (the bean or crewmate silhouette). *Mitigation:* a body shape of our own,
   no game names in prompts, and a side-by-side silhouette review.
10. **Budget misses.** Meshy overshoots polycount, flat shading triples vertices, and the 860M iGPU is unmeasured.
    *Mitigation:* automatic budget checks, decimation, and the 20-body smoke scene on the laptop.
11. **Vendor churn** (CSM bought, Genie shut, Tripo V2 retiring on 2026-11-01). *Mitigation:* the generator-agnostic
    pipeline.
12. **The private art repo has no branch protection on Free** [unconfirmed], so an agent could push to main.
    *Mitigation:* reuse the game repo's pre-push hook and agent rules there.

## 10. Suspected gaps (no lens answered, or one weak source)

- **Recolouring an AI texture to the palette headlessly.** Lens 4 and §4 step 7 require it, and no lens gave a
  method (for example a per-face average colour snapped to the nearest palette entry and written as palette UVs or
  vertex colours). It needs a probe.
- **AnimationMixer and missing bones.** If a clip has tracks for bones a skeleton lacks, Godot may print an `ERROR:`
  line, which would fail `run`. The 56-bone rule avoids this, but it is untested.
- **Adding missing profile bones in Blender at sensible default positions** (for a vendor rig without fingers) is an
  inference.
- **Game-specific clips.** No lens confirmed by name: crawl at 1 m/s, being raised and raising (a 3 s hold), the
  two-handed package carry, the knife strike, a hand-to-belt swap. Quaternius clip names were not listed.
- **Voice level at the listener.** Whether `voice/` exposes a per-speaker level of the frames actually played was not
  checked in the code. Whether any role-only voice channel exists or is planned was also not checked (lens 1).
- **Where character assets live in the game repo, and who owns that folder.** `CLAUDE.md` ownership lists no
  `assets/` folder. `content/` is the designer's and `client/` the engineer's. This is an ownership and architecture
  boundary, so ask the humans before the first asset PR.
- **Whether `xperiaroco2` is a user account or an organization.** The LFS quota, Actions minutes and branch
  protection rules differ.
- **Seeing your own customization.** The first-person player never sees their own body: a lobby mirror or monitor
  may be needed (lens 1).
- **Meshy library provenance.** Whether any Meshy library clips are Mixamo-derived, and whether Meshy terms allow
  library-motion files in a public repo.
- **Tripo terms** (pages returned 403) and **Hunyuan hosted terms** (not read). Neither matters while both stay
  unused.
- **Single weak sources:** Lethal Company at about 8k triangles (a game rip); Tripo rig lock-in (one PR); Meshy hip
  weights off (one blog); Jolt pyramid limits (one blog); the Ready Player Me shutdown date (a competitor's blog);
  the forum figure of 100 AnimationTrees at 60 FPS; the Mixamo, Fab and Rokoko terms (403 pages); GitHub private
  branch protection.
- **Trademark registers** for the Among Us crewmate and the Fall Guys bean silhouette were not checked.
- **Hand IK for the two-handed carry** with mitten hands: whether TwoBoneIK3D is needed in v1.
- **The Blender SHA-256** was read through a summarizer. Re-copy it from the `.sha256` file when pinning.

## 11. Proposed issues (first slice, for the manager to file)

Art repo (after the human's "yes" to create it):
1. Bootstrap the art repo: CLAUDE.md, layout, `.gitattributes` (LFS), gitignored `raw/`, the pre-push hook, the
   manifest schema.
2. Pin Blender 5.2.2 LTS: pins, a doctor check, `BLENDER_BIN`.
3. Blender probe: operator kwargs through `get_rna_type()`, a Workbench and an EEVEE frame under `-b`, numpy.
4. Generate `contract/humanoid.json` from the pinned Godot.
5. Scripts: `check_mesh`, `check_rig`, `rename_bones` (with tests on a generated fixture rig).
6. `export_glb` plus the glTF-Validator pin.
7. `render_views` and `render_anim_sheet` plus the Pillow sheet composer.
8. Probe: recolour an AI texture to the palette.
9. Human step: the Meshy trial evening checklist (T-pose, Smart Topology, the list from #165, corrected).

Game repo:
10. ADR: the character contract and budgets. Also decide the asset folder and its owner.
11. Spike: a base body plus a separately imported part with the same BoneMap; 8-side shots; no ERROR lines.
12. Spike: Jolt partial ragdoll with the hips animated; settle and freeze; headless.
13. Spike: retarget a Quaternius clip onto the contract skeleton; animation frame sheet.
14. The shared character shader with instance uniforms (colour, pattern, face, mouth).
15. `tests/assets` GdUnit4 suite plus the 20-body smoke scene.
16. `check`: LFS pointer skip plus a credits licence allowlist with `public_repo_ok`.
