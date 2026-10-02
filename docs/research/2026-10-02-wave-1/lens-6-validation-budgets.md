# Lens 6: validation, budgets, storage and the path into the game

Research agent, art track (xperiaroco2/prime-game#165), 2026-10-02. All web pages read on 2026-10-02.
Read-only: nothing downloaded, installed or generated. `[unconfirmed]` = no primary source opened (forum, third-party
blog, search snippet only, memory or inference).

## 0. Facts from the repo (read live)

- The body's origin is at the feet: `remote_player_body.gd:116` puts the capsule centre at `global_position + UP *
  capsule_height_m * 0.5`. Rules: `capsule_height_m = 1.8`, `capsule_radius_m = 0.4`, `eye_height_m = 1.6`
  (`content/modes/base_mode.tres:336-338`). Greybox attach points: `HAND_POINT (0.45, 0.95, -0.15)`,
  `BELT_POINT (-0.48, 0.85, 0)`, `CARRY_POINT (0, 0.8, -0.72)` (`remote_player_body.gd:31-33`). The character contract
  must fit inside a 1.8 m tall, 0.8 m wide capsule with the eyes at 1.6 m, and face -Z (the greybox puts the hand at
  -Z, i.e. Godot forward).
- `.gitattributes` routes `glb gltf fbx obj blend png jpg webp tga exr hdr ktx ktx2 psd kra zip ...` through LFS;
  `addons/**` is excluded. `.import` files are text (LF), not LFS. Only one credits entry exists today
  (`docs/credits/gdunit4.md`). `tools/runner/credits.py` fails `check` for any LFS asset outside `addons/` without a
  `docs/credits/<slug>.md` entry.
- LFS ADR `docs/decisions/2026-09-29-git-lfs-for-binary-assets.md`: CI checks out with `lfs: false`; open question
  "either enable LFS in CI (uses the LFS bandwidth quota) or teach `check` to skip LFS pointer files in CI".
- Blender is not pinned in `tools/runner/pins.py` (Godot 4.7.2 is).
- Godot 4.7.2 API names used below were grepped in `tools/out/godot-api/4.7.2/extension_api.json`:
  `Skeleton3D.get_bone_count/find_bone/get_bone_name/get_bone_parent/get_bone_rest/get_bone_global_rest`,
  `Skin.get_bind_count/get_bind_name`, `Mesh.get_surface_count/get_aabb/surface_get_arrays/surface_get_material`,
  `ArrayMesh.surface_get_array_index_len/surface_get_format/get_blend_shape_count`, `ImporterMesh.get_surface_lod_count`
  (LOD count is visible only on `ImporterMesh`, i.e. in an import script, not on the imported `ArrayMesh`),
  `MeshInstance3D.mesh/skin/skeleton/get_active_material`, `GeometryInstance3D.cast_shadow/lod_bias/
  visibility_range_begin/visibility_range_end/visibility_range_fade_mode`, `BoneAttachment3D.bone_name/bone_idx/
  override_pose/use_external_skeleton/external_skeleton`, `SkeletonProfileHumanoid` (56 bones, groups Body, Face,
  LeftHand, RightHand), `Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS`, `Vector3.MODEL_FRONT` and `use_model_front`
  (look_at), `RenderingServer.get_rendering_info` with `RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME`,
  `RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME`, `RENDERING_INFO_VIDEO_MEM_USED`, `RENDERING_INFO_TEXTURE_MEM_USED`,
  `Viewport` `RENDER_INFO_DRAW_CALLS_IN_FRAME`, `AnimationTree` with `callback_mode_process`, `PhysicalBoneSimulator3D`.

## 1. Engine facts that set the budgets

- **Skinning runs on the GPU in a compute shader** in the RenderingDevice renderers (Forward+): 64 threads per group,
  bone indices packed as 16-bit, 4 weights per set, with a second set at `skin_weight_offset` for 8-weight meshes.
  Blend shapes are evaluated in the same pass by looping over every blend shape for every vertex, each frame, when
  the mesh has blend shapes. Source: `servers/rendering/renderer_rd/shaders/skeleton.glsl` at tag `4.7.2-stable`
  (https://github.com/godotengine/godot/blob/4.7.2-stable/servers/rendering/renderer_rd/shaders/skeleton.glsl), read
  through `gh api`. Consequences (inference, [unconfirmed] as numbers): skinning cost scales with **vertices**, not
  triangles; blend-shape cost scales with vertices x shapes, so face shapes belong on a small head mesh, not on the
  whole body; the skinned result is reused by the shadow and depth passes (inferred from the compute pre-pass design).
- **Automatic mesh LOD** is generated at import (`meshes/generate_lods`), selected by screen-space error
  (`mesh_lod_threshold`, default 1 pixel, "perceptually lossless"), tuned per instance by `lod_bias`. The docs warn it
  "may occasionally introduce rendering issues (especially in skinned meshes)", which implies it does apply to skinned
  meshes. It reduces primitives, not draw calls. For hand-made LODs, use visibility ranges (HLOD).
  https://docs.godotengine.org/en/latest/tutorials/3d/mesh_lod.html (confirmed for the text; whether our skinned
  low-poly meshes look right after auto LOD is [unconfirmed] until a `shot` at distance).
- Import options: `meshes/generate_lods`, `meshes/create_shadow_meshes`, `meshes/light_baking`,
  `skins/use_named_skins`, `animation/import`, `animation/fps`, `animation/trimming`,
  `animation/remove_immutable_tracks`, `root_scale`/`apply_root_scale`, `import_script/path` (an `EditorScenePostImport`
  run after import). https://docs.godotengine.org/en/latest/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html
- Optimization guide: "Animation and vertex animation such as skinning and morphing can be very expensive on some
  platforms"; lower the animation rate for distant or occluded meshes, pause them with `VisibleOnScreenEnabler3D` /
  `VisibleOnScreenNotifier3D`; HLOD via visibility ranges; transparent parts in their own surface. No numbers given.
  https://docs.godotengine.org/en/latest/tutorials/performance/optimizing_3d_performance.html
- AnimationTree cost: a developer reports about 100 AI characters with AnimationPlayer + AnimationTree at 60 FPS,
  3 to 4 times more with them disabled; 200+ with off-screen culling. Forum, [unconfirmed].
  https://forum.godotengine.org/t/performance-of-crowds-of-animated-rigged-characters-in-3d/130409 ; tracker issues on
  AnimationTree cost: https://github.com/godotengine/godot/issues/92693 , https://github.com/godotengine/godot/issues/65199
- Shipped reference: the Lethal Company player model is about 8,000 triangles / 3,900 vertices (a game rip on
  Sketchfab, [unconfirmed]). https://sketchfab.com/3d-models/lethal-company-scavenger-model-game-rip-dbcd1bbe54e7485fb13d86b4b5cbaf6b

## 2. Recommended performance budget (10 players)

Worst case on screen: 9 remote bodies + up to 9 corpses (DEAD leaves a body, no avatar) + the own first-person hand =
about **20 skinned characters**. Spectators are dead players, so they add cameras, not bodies. These numbers are the
manager's technical choice; inferences are marked.

| Item | Budget (fail above) | Why |
|---|---|---|
| Assembled character LOD0 (body + all worn parts) | **8,000 triangles target, 12,000 hard cap** | Lethal Company ~8k [unconfirmed]; 20 x 12k = 240k tris, x ~3 passes (depth, colour, shadow) < 1M: easy on an RTX 4060 and expected fine on a Radeon 860M iGPU [unconfirmed, measure] |
| Base body LOD0 | 5,000 tris | leaves ~3k for head, hand, belt, back parts |
| Head accessory / mask | 800 tris each | rigid, on the head bone |
| Hand item (third person) | 1,500 tris; first-person hand item 3,000 | the own hand item is seen up close |
| Belt / back item | 800 tris each | small on screen |
| Skinned **vertices** per assembled character | **12,000** | flat shading splits normals, so vertices can reach ~3x triangles [inference]; the compute skinning cost is per vertex |
| LOD1 / LOD2 | auto mesh LOD, check it reaches ~50% / ~25% of LOD0 | `meshes/generate_lods` on; verify with a distance `shot`; hand-made LODs only if auto LOD breaks the skinned mesh |
| Skeleton | **<= 64 deform bones, <= 80 bones total** (incl. attach/helper bones) | `SkeletonProfileHumanoid` is 56; Mixamo-style rigs are ~65 with fingers [unconfirmed]; mitten hands could drop 30 finger bones |
| Weights per vertex | **<= 4, normalized, none below 0.01** | 4 is the default path in the compute shader; the 8-weight path costs a second set |
| Blend shapes | 0 on the body; **<= 12 on the head/face mesh** | each shape is looped per vertex per frame |
| Surfaces (= draw calls per pass) per assembled character | **<= 8** (body 1, head 1, face 1, each part 1) | 20 x 8 x 3 passes ~ 480 draws per frame, comfortable [inference]; Godot does not batch skinned meshes [unconfirmed] |
| Materials | one shared palette material for most parts; <= 1 unique material per part; no transparency except where it must be (its own surface) | docs: transparent parts in a separate surface |
| Textures | shared palette atlas **256x256**; a character-specific texture **<= 1024x1024**, an accessory **<= 512x512**; power of two; PNG source; Godot VRAM-compressed; no normal maps by default (flat look) | BC7 1024^2 with mips ~1.4 MB, 512^2 ~0.35 MB [arithmetic] |
| Texel density | **~256 px/m (+-50%)** shared across body and accessories | consistent pixel size across mixed parts [inference; a style call, confirm with the designer] |
| Character texture VRAM, all characters loaded | <= 64 MB | the iGPU shares system RAM [inference] |
| AnimationTree | one per living body; none on corpses (frozen pose or a settled ragdoll); process off when not visible (`VisibleOnScreenEnabler3D`) | ~100 trees at 60 FPS in the forum report [unconfirmed]; we need <= 10 |
| Shadows | bodies cast; parts smaller than ~10 cm `cast_shadow` off | each caster adds a shadow pass draw |
| Files | character `.glb` <= 5 MB; accessory <= 1 MB; shared animation library <= 10 MB | keeps LFS and clone size small |
| Frame budget gate | the 10-body test scene: <= 4 ms GPU on the 4060 and 60 FPS at 1080p on the 860M | measured with `RenderingServer.get_rendering_info` and the frame time in an `--offscreen` run [the numbers are targets, unconfirmed] |

## 3. The check list (automatic)

### 3a. In Blender (`blender -b --python check_asset.py`, before export; lens 5 builds the scripts)
1. Units metric, scale 1.0, applied transforms (location, rotation, scale) on mesh and armature.
2. Height of the A/T rest pose: 1.6 to 1.8 m (fits the 1.8 m capsule), width within 0.8 m; origin at the feet
   centre (0, 0, 0); faces -Y in Blender, which becomes +Z in glTF ([unconfirmed] axis mapping; verify in Godot with
   `Vector3.MODEL_FRONT`, see 3b) and then rotate in the scene so the body faces Godot -Z like the greybox.
3. Triangle and vertex count per mesh and per LOD against the table; no n-gons above 4 sides after triangulate; no
   loose vertices, no zero-area faces, manifold where expected; UVs present, inside 0..1 for the palette.
4. Bone names exactly the contract list (or mapped by the BoneMap), one root, the expected hierarchy, deform flag only
   on deform bones, no duplicate names (the godot#106073 rename).
5. Vertex groups: every group matches a deform bone; `vertex_group_limit_total` to 4 then normalize; no vertex with
   zero total weight.
6. Materials and slots <= budget; images power of two, <= size budget, PNG; no packed or missing images.
7. Attachment bones/empties present: `head`, `hand_r` (and `hand_l` if used), `belt` (hip), `back` (chest).
8. glTF export settings: GLB, +Y up, apply modifiers, rest position armature, 4 bone influences, deform bones only.
   Option labels confirmed in the 5.2 LTS manual ("Bone influences", "Include All Bone Influences", "Use Rest Position
   Armature") https://docs.blender.org/manual/en/latest/addons/scene_gltf2.html ; the Python parameter names
   (`export_influence_nb`, `export_all_influences`, `export_rest_position_armature`, `export_def_bones`, `export_yup`)
   are [unconfirmed] (the API page did not render).
9. Write a JSON report next to the asset (counts, bounds, bone list, material list, texture list) that 3c compares.

### 3b. In Godot after a headless import (a GdUnit4 suite in the game repo, `tests/assets/`, run by `test`)
Load each approved character or part scene (`load(path).instantiate()`, freed after; orphans fail) and assert:
- **Skeleton:** exactly one `Skeleton3D`; `get_bone_count()` <= 80; every contract bone found by `find_bone()`;
  parents by `get_bone_parent()`; rest pose sane (`get_bone_global_rest()` of Head above Hips, feet near y = 0).
- **Skin:** `MeshInstance3D.skin.get_bind_count()` <= 64 and every `get_bind_name()` in the skeleton.
- **Weights:** `surface_get_arrays(i)[Mesh.ARRAY_WEIGHTS]` has 4 per vertex (format lacks
  `ARRAY_FLAG_USE_8_BONE_WEIGHTS`), each vertex sums to ~1.0.
- **Size and origin:** the merged `get_aabb()` (transformed to the root) is 1.6 to 1.8 m tall, <= 0.8 m wide,
  min y in -0.02..0.02, centred on x/z within 0.1 m.
- **Facing:** a marker bone or the nose/visor point lies at negative z (Godot forward), like the greybox hand point.
- **Counts:** triangles = `surface_get_array_index_len(i) / 3` summed <= budget; vertices from
  `surface_get_array_len(i)`; `get_surface_count()` <= budget; `get_blend_shape_count()` within budget.
- **Materials and textures:** each `surface_get_material(i)` is a `BaseMaterial3D`/`ShaderMaterial` from the shared
  set; texture sizes from `get_width()/get_height()`; power of two.
- **Attachment points:** `BoneAttachment3D` (or named bones) for head, hand, belt, back exist and resolve
  (`bone_idx >= 0`).
- **Animations:** the shared library has the contract's names (idle, walk, run, crouch walk, crawl, fall, get up,
  carry, emotes); each track path resolves on the contract skeleton.
- **LOD:** only an import script sees `ImporterMesh.get_surface_lod_count()`; record it in the import report instead of
  the test.
- **Performance smoke:** a scene with 20 characters runs `run --offscreen --seconds 10` and logs
  `RenderingServer.get_rendering_info(RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)`, primitives and video memory; a test
  fails above the budget (draw calls, primitives); frame time is reported, not asserted (machines differ).
- In CI (no LFS content) these tests must skip assets that are pointer files (see 6).

### 3c. Review loop with rendered snapshots and a recorded approval
- The art repo renders 8 turnaround views + an animation contact sheet (lens 5) per asset into `review/<asset>/<rev>/`;
  the game repo renders the imported asset with `tools\run.cmd shot <scene>` (front, side, in the 10-body scene, at
  10 m and 30 m to see LOD) so the human sees the engine's version, not Blender's.
- The approval is a PR review in the art repo by the human (the designer for the look, the engineer for the rest),
  and `approved_by`, `approved_at` and the PR URL are written into the asset's manifest; the export PR into the game
  repo links that PR. No approval field = the gate in the game repo refuses the asset.

## 4. Git LFS and GitHub limits (October 2026)

- **LFS on GitHub Free personal account: 10 GiB storage and 10 GiB bandwidth per month**, for the account, counted the
  same way for public and private repos; storage counts **every version** ever pushed; Actions downloads count against
  the owner's bandwidth (a 500 MB file fetched by Actions uses 500 MB); forks count against the parent.
  https://docs.github.com/en/billing/concepts/product-billing/git-lfs (confirmed). So the public game repo and the
  private art repo **share one 10 GiB + 10 GiB quota**.
- **Past the quota without a payment method:** clones get only pointer files, pushes of new LFS files fail; over
  bandwidth, LFS is disabled until next month (same page, confirmed). With a payment method: metered, about **$0.07 per
  GiB-month storage and $0.0875 per GiB bandwidth** (third-party summaries,
  https://pricingsaas.com/news/github/20251118/ , [unconfirmed]; the official page sends you to
  https://github.com/pricing/calculator).
- **LFS objects can only be removed by deleting and recreating the repository** (or asking support).
  https://docs.github.com/en/repositories/working-with-files/managing-large-files/removing-files-from-git-large-file-storage
  (confirmed). This is the strongest reason not to push raw generations into LFS: drafts would eat the shared
  10 GiB for good.
- Max LFS file size on Free: 2 GB. https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage
- **Actions on GitHub Free:** public repos free on standard runners; **private repos 2,000 minutes/month and 500 MB
  artifact storage**; Windows minutes cost more (Windows $0.010/min vs Linux $0.006/min); without a payment method usage
  is blocked at the quota; cache 10 GB per repo.
  https://docs.github.com/en/billing/concepts/product-billing/github-actions (confirmed). An art-repo CI that runs
  Blender headless on Linux runners for ~3 min per push gives ~600 pushes/month; keep it off Windows/macOS runners.
- **Protected branches on GitHub Free exist only in public repos**; private repos need Pro/Team. Source:
  docs.github.com "About protected branches" (search snippet of the docs page, the page itself did not show the
  sentence on fetch, [unconfirmed]) https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches .
  So in the private art repo "only the human merges into main" cannot be enforced by GitHub on Free; reuse the game
  repo's pre-push hook (no push to main) and the agents' rules.

### Storage options for raw files (keep them out of git)
1. **Recommended:** raw generations, Meshy downloads and `.blend` work files live **outside git** on the human's disk,
   synced by a cloud drive the humans already have (a money question only if they have none); the art repo commits a
   **manifest** per asset (service, plan, task id, prompt, date, SHA-256 of the raw file, local path) and only
   **curated sources and approved exports** go into LFS.
2. LFS for everything in the art repo: simplest, but each draft is permanent in the shared quota (see above).
3. Object storage (Cloudflare R2, Backblaze B2) with a free tier: needs an account and a card; [unconfirmed], a money
   decision.

Size estimate [inference]: an approved low-poly character `.glb` with a 1024^2 texture ~1-3 MB; 30 characters +
100 parts + an animation library ~ 150-300 MB in the game repo; one CI run with LFS on would fetch all of it, so 40
runs/month ~ 10 GiB: **CI must not fetch LFS without a cache**.

## 5. From the private art repo into the public game repo

What travels (one PR per approved asset or batch, by an agent, approved by a human):
- `assets/characters/<name>/<name>.glb` (or the part), its textures (PNG, LFS) if not embedded, and the Godot
  `.import` files (text, generated by `check`'s headless import, committed so the import settings are reviewed);
- a `docs/credits/<slug>.md` entry (author, source, license), enforced by `check`;
- provenance: the manifest fields below copied into the credits entry (no prompt text if it is long; link to the art
  repo commit instead; the art repo is private, so the public record holds service, plan, date, task id, license);
- the `shot` PNGs only in the PR description (not committed).

Manifest per asset (`assets/<kind>/<name>/manifest.toml` in the art repo):
`id, kind (character|part|prop|animation), slot (head|hand|belt|back|body), source_service (meshy|mixamo|hand|...),
plan (e.g. Meshy Pro), generated_at, task_ids, prompt, raw_sha256, raw_location, tools (Blender x.y, scripts rev),
license, license_url, commercial_ok, attribution, public_repo_ok, ai_generated (pre-generated: yes/no),
budgets_report (path), approved_by, approved_at, approval_pr, exported_to (game repo PR)`.

Licenses that matter for a PUBLIC repo:
- **Meshy paid plan:** the customer owns the output (#165, already researched); a public repo is then fine. Free-plan
  output is CC BY 4.0 owned by Meshy: commercial use with credit, redistribution allowed by CC BY [inference from the
  CC BY terms]. Use paid-plan output only (as #165 says).
- **Mixamo:** royalty-free for commercial and non-commercial use, no credit needed, but **no free distribution of the
  raw character or animation files**, nor templates/asset packs that redistribute them (Mixamo FAQ, quoted via a search
  snippet; https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html returned 403 to the fetcher, [unconfirmed]).
  A public git repo is a free distribution of the raw files, so **Mixamo FBX/animations must not sit in the public game
  repo**; keep them in the private art repo; the game ships only baked results inside its own resources
  [legal reading, unconfirmed]. Same caution for any Meshy animation that is a Mixamo-derived clip.
- **Fab Standard License / store packs:** sharing via "a private repository ... with your collaborators" is allowed,
  standalone redistribution (free or paid) is not (search snippet of https://www.fab.com/eula, page 403,
  [unconfirmed]). Unity Asset Store EULA is similar [unconfirmed, not opened]. Rule: **store-licensed assets never enter
  the public repo**; only CC0 / CC BY / owned outputs do.
- **CC0 (e.g. Kenney, Quaternius):** public repo fine [memory, unconfirmed; check each pack's license file].

Steam AI-generated content disclosure (primary, Steamworks docs, confirmed):
https://partner.steamgames.com/doc/gettingstarted/contentsurvey — the Content Survey has a Generative AI section with
**Pre-Generated** ("content that ships with your game and is consumed by players that is created with the help of AI
tools during development") and **Live-Generated** (created while the game runs; requires describing guardrails).
Efficiency tools used in development are not the focus. prime-game with Meshy characters = **Pre-Generated: must be
disclosed** and described; the manifest's `ai_generated` field makes the list trivial. A January 2026 revision that
explicitly exempts dev tools and concept art that does not ship is reported by third parties
(https://tech-insider.org/steam-ai-disclosure-2026/ , https://blog.promise.legal/ai-game-assets-copyright-steam-disclosure-2026/ ,
[unconfirmed]). Valve's 2024 news post (https://store.steampowered.com/news/group/4145017/view/3862463747997849618)
did not render.

## 6. LFS pointer files in CI (context for the open ADR question)

Without LFS content a `.glb` in CI is a ~130-byte text file starting `version https://git-lfs.github.com/spec/v1`;
Godot's importer would fail on it and `check` fails on any `ERROR:` line. Options:
- **A. `check` treats pointer files as absent in CI:** detect the pointer header, exclude those paths from the headless
  import (e.g. a temporary `.gdignore`-free approach: pass the list to the import step, or skip the import and only
  load scripts), and asset tests `skip` when their file is a pointer. Zero bandwidth; CI does not test assets.
- **B. LFS in CI with a cache:** `actions/checkout` with `lfs: false`, then `git lfs ls-files -l` -> a hash key file ->
  `actions/cache` the `.git/lfs` folder -> `git lfs pull` only on a cache miss (common pattern, [unconfirmed], not
  opened). Bandwidth only when assets change; cache storage is 10 GB per repo, separate from LFS.
- **C. Hybrid (recommended):** A on every push/PR (fast, free); B in one job that runs only when files under
  `assets/` change (path filter), so asset PRs get the asset tests and the snapshot render. The public repo's Actions
  minutes are free; only LFS bandwidth matters.

## 7. Recommended art-repo layout (xperiaroco2/prime-game-art, private)

```
CLAUDE.md                     rules: no drafts in git beyond the manifest, budgets, the export path
docs/contract.md              the character contract (bone list, attach points, budgets, style refs) mirrored from
                              the game ADR (the ADR in the game repo is the source of truth)
tools/                        runner (pins Blender version + SHA), blender/ scripts: check, export, render
assets/<kind>/<name>/
  manifest.toml               provenance + license + approval (section 5)
  source/<name>.blend         curated source only (LFS)
  export/<name>.glb           the candidate export (LFS)
  report.json                 the Blender check report (text)
review/<name>/<rev>/*.png     8-view turnaround + animation sheets (LFS; or PR attachments only, to save quota)
raw/                          .gitignored; local raw downloads; the manifest's raw_sha256 points at them
.gitattributes                LFS for blend, glb, fbx, png; LF for text
```
Review PNGs: prefer attaching them to the PR (GitHub user-content, not LFS) or keep only the last approved rev,
to save the shared quota [inference].

## 8. Licenses (of what we would use)

| Thing | License | Commercial | Attribution | Public repo | URL |
|---|---|---|---|---|---|
| Godot 4.7.2 | MIT | yes | license notice in the game | yes | https://godotengine.org/license/ |
| Blender (tool) | GPL-2.0-or-later; outputs are yours | yes | no (for outputs) | the tool is not in the repo | https://www.blender.org/about/license/ [memory, unconfirmed] |
| Meshy paid output | owned by the customer | yes | no | yes | https://www.meshy.ai/terms-of-use (#165) |
| Meshy free output | CC BY 4.0, Meshy owns | yes | yes | yes, with credit | #165 |
| Mixamo characters/animations | Adobe terms, royalty-free | yes | no | **no** (no free distribution of raw files) | https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html [403, unconfirmed] |
| Fab Standard License assets | Fab EULA | yes | no | **no** (private repo with collaborators only) | https://www.fab.com/eula [403, unconfirmed] |
| GdUnit4 (tests) | MIT | yes | notice | yes (already in addons/) | docs/credits/gdunit4.md |
| GitHub LFS / Actions | GitHub terms, metered | n/a | n/a | n/a | the docs pages in section 4 |
