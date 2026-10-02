# Art track, wave 1: sources and licences (#165)

Appendix to the wave 1 report comment. Every source below was read on 2026-10-02 unless marked otherwise; one line
each: the URL and what it supports. `[u]` = unconfirmed (a search snippet, a summarizer, a 403 page, a third party or
memory). Local sources are paths in the game repo, checked live on 2026-10-02.

## Live repo checks (2026-10-02)

- `D:/prime-game/tools/out/godot-api/4.7.2/extension_api.json`: every Godot class, method and constant named in the ADR sketch (grep, count of 1 or more each); the import option names are not in it.
- `client/player/remote_player_body.gd`: hand `(0.45, 0.95, -0.15)`, carry `(0, 0.8, -0.72)`, belt `(-0.48, 0.85, 0)` on the left hip; the body faces -Z.
- `content/modes/base_mode.tres`: capsule 1.8 m, radius 0.4 m, `eye_height_m = 1.6`.
- `client/CLAUDE.md`: spectating through a living target's eyes hides its body and shows its hand item in the first-person hand (#168).
- `voice/` holds only CLAUDE.md; `core/voice/` has ProximityVoice, RoundVoice, SilentVoice: no played-level primitive yet.
- `gh api users/xperiaroco2`: type User (personal Free plan rules apply).
- Issue #165 body: the Meshy research this wave builds on.

## Lens 1: art direction and references

- https://blog.playstation.com/2020/05/25/creating-the-character-designs-of-fall-guys-out-on-ps4-this-summer/ : Fall Guys' bean design intent (developer blog).
- https://www.gamesradar.com/fall-guys-interview/ : Fall Guys proportions and silliness [u].
- https://designtaxi.com/news/411684/ : Fall Guys design commentary [u].
- https://mcvuk.com/business-news/when-we-first-started-we-didnt-really-know-what-we-were-doing-how-gang-beasts-became-an-international-success/ : Gang Beasts' origins and floppy-body comedy.
- https://thenvm.org/games/gang-beasts/ : Gang Beasts' gelatinous bodies and oversized heads (museum page).
- https://en.wikipedia.org/wiki/Human:_Fall_Flat : Human: Fall Flat's blank wobbly character [u].
- https://www.thegamer.com/human-fall-flat-interview-tomas-sakalauskas/ : HFF developer on physics comedy.
- https://news.xbox.com/en-us/2016/03/17/gdc-2016-human-fall-flat-xbox-one/ : HFF at GDC 2016 [u].
- https://80.lv/articles/how-to-achieve-lethal-company-s-graphics-with-unity-hdrp : Lethal Company's lo-fi post look [u].
- https://lethal-company.fandom.com/wiki/Suits : Lethal Company suit customization [u].
- https://www.thegamer.com/lethal-company-all-suits-guide/ : Lethal Company suits [u].
- https://landfall.se/content-warning-press-kit : Content Warning's visor faces and physics-animated monsters (press kit).
- https://en.wikipedia.org/wiki/Content_Warning : Content Warning background.
- https://repogame.fandom.com/wiki/Semibots : R.E.P.O.'s voice-flapping heads [u].
- https://en.wikipedia.org/wiki/R.E.P.O. : R.E.P.O. background [u].
- https://store.steampowered.com/app/3241660/REPO/ : R.E.P.O. proximity voice and physics grabbing.
- https://en.wikipedia.org/wiki/Totally_Accurate_Battle_Simulator : TABS' deliberately clumsy wobble.
- https://shapes.inc/fandom/totally-accurate-battle-simulator/deep-dive : TABS art analysis [u].
- https://cliqist.com/2014/03/06/armin-ibrisagic-talks-goat-simulator/ : Goat Simulator's "bugs are funny" (developer interview).
- https://news.xbox.com/en-us/2015/04/21/games-chatting-about-purgatory-and-glitches-too-good-to-remove-in-goat-simulator/amp/ : Goat Simulator keeping glitches.
- https://www.gamedeveloper.com/business/peak-co-developer-aggro-crab-shares-lessons-in-friendslop : PEAK's eyes following players and speaking mouths.
- https://www.pcgamer.com/games/adventure/peaks-success-helped-aggro-crab-commit-to-co-op-says-studio-head-we-thought-we-were-a-character-action-studio/ : PEAK's success context.
- https://en.wikipedia.org/wiki/Party_Animals_(video_game) : Party Animals background.
- https://goombastomp.com/party-animals-interview/ : Party Animals soft-body look.
- https://schellgames.com/portfolio/among-us-3d : first-person social deduction with proximity voice.
- https://innersloth.itch.io/among-us/devlog/181107/the-future-of-among-us : Among Us adding non-colour identifiers for colour-blind players.
- https://among-us.fandom.com/wiki/Colors : Among Us colour list [u].
- https://store.steampowered.com/app/2780980/LOCKDOWN_Protocol/ : obstacle-aware proximity voice in a social deduction game.
- https://screenrant.com/lockdown-protocol-gameplay-mystery-party-game/ : LOCKDOWN Protocol's gritty look [u].
- https://www.dexerto.com/uncategorized/chaotic-pvp-wizard-game-lets-you-cast-spells-by-shouting-into-your-mic-3231435/ : voice as a mechanic in party games.
- https://docs.godotengine.org/en/4.7/tutorials/3d/standard_material_3d.html : DIFFUSE_TOON, rim, stencil outline (needs shared vertices), grow.
- https://jfly.uni-koeln.de/color/ : Okabe-Ito colour-blind-safe palette (not opened) [u].
- https://conceptviz.app/blog/okabe-ito-palette-hex-codes-complete-reference : Okabe-Ito hex values [u].
- https://www.gamedeveloper.com/business/clone-wars-the-five-most-important-cases-every-game-developer-should-know : copyright protects expression, not genre ideas (attorney summary).
- https://en.wikipedia.org/wiki/Spry_Fox,_LLC_v._Lolapps,_Inc. : a look-alike clone case.
- https://godotengine.org/license/ : Godot MIT licence.

## Lens 2: customization architecture

- https://raw.githubusercontent.com/godotengine/godot/4.6-stable/scene/3d/skeleton_3d.cpp : named Skin binds resolve by bone name; a miss prints an ERROR and falls back to bone 0.
- https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html : import options (named skins, LOD generation).
- https://docs.godotengine.org/en/4.7/classes/class_meshinstance3d.html : `skeleton` defaults to an empty path since 4.6.
- https://docs.godotengine.org/en/4.7/classes/class_boneattachment3d.html : `override_pose` conflicts with SkeletonModifier3D.
- https://docs.godotengine.org/en/4.7/classes/class_skeletonprofilehumanoid.html : the 56-bone humanoid profile, T-pose, +Z front.
- https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/retargeting_3d_skeletons.html : BoneMap retargeting, Fix Silhouette.
- https://github.com/godotengine/godot/pull/97824 : RetargetModifier3D added in 4.4.
- https://docs.godotengine.org/en/4.7/classes/class_retargetmodifier3d.html : realtime retargeting behaviour.
- https://godotengine.org/releases/4.4/ , https://godotengine.org/releases/4.5/ , https://godotengine.org/releases/4.6/ , https://godotengine.org/releases/4.7/ : skeleton features by version; 4.7 adds none.
- https://godotengine.org/article/inverse-kinematics-returns-to-godot-4-6/ : the 4.6 IK modifier family.
- https://github.com/godotengine/godot/pull/101409 : SpringBoneSimulator3D.
- https://github.com/godotengine/godot/pull/100984 : BoneConstraint3D.
- https://docs.blender.org/manual/en/latest/modeling/modifiers/modify/data_transfer.html : weight transfer to clothing (Nearest Face Interpolated).
- https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html : glTF bone influences other than 4 or 8 display wrongly [u].
- https://syntystore.com/products/sidekick-modular-characters-starter-pack : modular body segments per slot.
- https://syntystore.com/pages/one-time-purchase-licence : Synty forbids sharing source files outside the team.
- https://docs.godotengine.org/en/4.7/tutorials/shaders/shader_reference/shading_language.html : at most 16 instance uniforms, no textures.
- https://docs.godotengine.org/en/4.7/tutorials/performance/optimizing_3d_performance.html : draw calls per surface; skinning cost.
- https://among-us.fandom.com/wiki/Innersloth_Cosmicube : Among Us cosmetic slots [u].
- https://fallguysultimateknockout.fandom.com/wiki/Customization : Fall Guys slots [u].
- https://thunderstore.io/c/lethal-company/p/x753/More_Suits/dependants/ : Lethal Company suits as texture swaps [u].
- https://dev.epicgames.com/documentation/en-us/unreal-engine/working-with-modular-characters-in-unreal-engine : modular characters in Unreal (not opened) [u].
- https://variety.com/2025/digital/news/netflix-acquires-ready-player-me-games-avatar-creation-1236612915/ : Netflix bought Ready Player Me.
- https://avatarsdk.com/blog/2026/01/15/switch-from-ready-player-me-to-avatar-sdk-fast-familiar-production-ready/ : Ready Player Me shutdown date (competitor blog) [u].
- https://www.blender.org/about/license/ : Blender licence; outputs are the user's.

## Lens 3: animation

- https://docs.godotengine.org/en/latest/tutorials/animation/animation_tree.html : AnimationTree, state machines, `travel()`.
- https://godotengine.org/article/design-of-the-skeleton-modifier-3d/ : SkeletonModifier3D processing order.
- https://docs.godotengine.org/en/latest/tutorials/physics/ragdoll_system.html : physical bones, partial ragdoll.
- https://docs.godotengine.org/en/latest/tutorials/physics/using_jolt_physics.html : Jolt built in since 4.4.
- https://www.strayspark.studio/blog/godot-46-jolt-physics-migration-guide : Jolt joint limits are pyramid-shaped [u].
- https://github.com/godotengine/godot/issues/96202 : PhysicalBone not following animation (open).
- https://github.com/godotengine/godot/issues/102638 : Jolt warnings for PhysicalBone3D on a physics thread.
- https://github.com/godotengine/godot/issues/107461 : 6DOF velocity-dependent movement (open).
- https://forum.godotengine.org/t/active-ragdoll-in-godot-4-5-how-to-achieve-good-results/128728 : active ragdolls are hard in Godot [u].
- https://bugnet.io/blog/fix-godot-animationtree-blend-not-transitioning : crossfade tuning [u].
- https://medium.com/@jacasch/balancing-of-active-ragdolls-in-games-367f146b25fb : active ragdoll balancing [u].
- https://jacasch.itch.io/real-guys-wear-ties/devlog/85804/active-ragdoll-system : active ragdoll example [u].
- https://docs.meshy.ai/en/api/animation-library : Meshy library clip ids (via a summarizer) [u].
- https://quaternius.com/packs/universalanimationlibrary.html : UAL tiers, CC0.
- https://quaternius.itch.io/universal-animation-library : UAL1: 120+ clips, CC0, root-motion and in-place versions, prices.
- https://quaternius.itch.io/universal-animation-library-2 : UAL2: 130+ clips, melee, CC0.
- https://jettelly.com/blog/universal-animation-library-2-a-cross-engine-animation-pack-with-a-universal-humanoid-rig : UAL2 overview.
- https://store.godotengine.org/asset/quaternius/universal-animation-library/ : UAL on the Godot Asset Store.
- https://huggingface.co/datasets/jasongzy/Mixamo : about 2,300 Mixamo clips [u].
- https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html : Mixamo terms (403) [u].
- https://www.cgchannel.com/2020/03/get-150-free-mocap-moves-from-rokokos-motion-library/ : Rokoko free library terms [u].
- https://www.re3data.org/repository/r3d100012183 : CMU mocap terms [u].
- https://actorcore.reallusion.com/eula : ActorCore content EULA [u].
- https://unity.com/legal/as-terms : Unity Asset Store redistribution limits (via a summarizer).
- https://github.com/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset : CC BY-NC 4.0 motion data.
- https://github.com/nghorbani/amass : AMASS research-only [u].
- https://github.com/EricGuo5513/HumanML3D : HumanML3D derived from AMASS, academic only.
- https://replicate.com/daanelson/motion_diffusion_model/readme : MDM text-to-motion, trained on HumanML3D.
- https://www.deepmotion.com/terms-of-use : DeepMotion output rights [u].
- https://docs.move.ai/knowledge/move-one-pricing : Move One pricing [u].
- https://plask.ai/en-US/pricing : Plask pricing [u].
- https://www.cgchannel.com/2026/04/autodesk-acquires-core-tech-of-ai-motion-capture-firm-radical/ : Radical shut down [u].

## Lens 4: AI 3D generators other than Meshy

- https://docs.tripo3d.ai/get-started/pricing.html : Tripo API credit prices, smart low poly, quad, parts, rig, retarget.
- https://runware.ai/docs/models/tripo-v3-1 : Tripo face-limit ranges (reseller) [u].
- https://developers.tripo3d.ai/en/docs/animations-rig : Tripo auto-rig types and `tripo`/`mixamo` specs.
- https://github.com/nvdtf/riptide-kitty/pull/1 : Tripo presets fail on a `mixamo`-spec rig [u].
- https://www.strayspark.studio/blog/ai-auto-rigging-showdown-2026-tripo-meshy-cascadeur-mixamo : rig quality comparison; Meshy hip weights off [u].
- https://docs.tripo3d.ai/get-started/overview.html : Tripo modes; V2 retirement.
- https://developers.tripo3d.ai/en/docs/migration-v2-to-v3 : V2 to V3 migration.
- https://docs.tripo3d.ai/get-started/rate-limits.html : Tripo concurrency.
- https://makerstack.co/reviews/tripo-3d-review/ : Tripo Studio plan prices [u].
- https://www.tripo3d.ai/terms , https://www.tripo3d.ai/help/privacy-policy/how-to-use-tripo-models-commercially : Tripo licence (403) [u].
- https://wavespeed.ai/docs/docs-api/hyper3d/hyper3d-rodin-v2-image-to-3d : Rodin face ranges (reseller) [u].
- https://www.3daistudio.com/blog/best-ai-3d-character-and-avatar-generators-2026 : Rodin less versatile for game assets [u].
- https://80.lv/articles/how-hyper3d-rodin-gen-2-5-is-bringing-production-level-control-to-ai-3d-generation : Rodin BANG to Parts [u].
- https://docs.hyper3d.ai/ : Rodin API.
- https://hyper3d.ai/pricing : Rodin plans; API only on Business $120/month.
- https://hyper3d.ai/legal/terms : Rodin may use outputs to improve services, no opt-out.
- https://www.tencentcloud.com/document/product/1284/75281 : Hunyuan hosted API credit prices.
- https://arxiv.org/html/2509.12815v1 : Hunyuan3D Studio paper (low poly, rigging).
- https://raw.githubusercontent.com/Tencent-Hunyuan/Hunyuan3D-2.1/main/LICENSE : Hunyuan community licence excludes the EU, UK and South Korea.
- https://github.com/Tencent-Hunyuan/Hunyuan3D-Part : Hunyuan part generation [u].
- https://creati.ai/ai-tools/csm/ : CSM plans [u].
- https://mgmtboston.com/common-sense-machines-acquired-by-google/ : CSM acquired by Google [u].
- https://x.com/WesRoth/status/2015711318024536273 : CSM acquisition [u].
- https://www.sloyd.ai/pricing : Sloyd plans and commercial rights.
- https://github.com/microsoft/TRELLIS.2 : TRELLIS.2 MIT, needs a 24 GB GPU.
- https://stability.ai/community-license-agreement : Stability community licence terms.
- https://docs.hitem3d.ai/en/api/resources/terms-of-use : Hitem3D terms [u].
- https://empiriolabs.ai/models/hitem3d-2-0 : Hitem3D pricing [u].
- https://gptprompts.ai/luma-ai-guide : Luma Genie sunset [u].
- https://knowara.com/ai-tools/image/kaedim-review/ : Kaedim pricing [u].
- https://docs.masterpiecex.com/docs/getting-started : Masterpiece X API [u].
- https://actorcore.reallusion.com/learn-and-support/faq/accurig : AccuRIG 2 free, A-pose input, account needed [u].
- https://www.cgchannel.com/2025/07/rig-and-animate-3d-characters-for-free-with-accurig-2-0/ : AccuRIG 2 release [u].
- https://www.meshy.ai/features/low-poly : Meshy Smart Topology generates low poly from the start.
- https://www.meshy.ai/tutorials/auto-split-3d-model-into-parts : Meshy Auto Split [u for game use].

## Lens 5: headless Blender pipeline

- https://www.blender.org/download/lts/ : 5.2 LTS and 4.5 LTS series, latest 5.2.2.
- https://developer.blender.org/docs/release_notes/ , https://developer.blender.org/docs/release_notes/5.2/ : 5.2 LTS supported to July 2028.
- https://download.blender.org/release/Blender5.2/ : 5.2.2 Windows zip and the `.sha256` file.
- https://download.blender.org/release/Blender5.2/blender-5.2.2.sha256 : the published hash (read via a summarizer) [u].
- https://pypi.org/project/bpy/ : bpy 5.2.2, Python 3.13 only, GPL-3.0.
- https://developer.blender.org/docs/release_notes/5.0/python_api/ , https://developer.blender.org/docs/release_notes/5.0/ : 5.0 Python API changes.
- https://developer.blender.org/docs/release_notes/5.2/python_api/ , https://developer.blender.org/docs/release_notes/5.2/pipeline_io/ : 5.2 API and I/O changes.
- https://projects.blender.org/blender/blender-manual/raw/branch/main/manual/advanced/command_line/arguments.rst : `-b`, `--factory-startup`, `--python-exit-code`.
- https://raw.githubusercontent.com/KhronosGroup/glTF-Blender-IO/main/addons/io_scene_gltf2/__init__.py : exporter option names (main, not 5.2's bundled version) [u].
- https://raw.githubusercontent.com/blender/blender/blender-v5.2-release/source/blender/python/bmesh/bmesh_py_types.cc : bmesh API for mesh checks.
- https://projects.blender.org/blender/blender-manual/raw/branch/main/manual/modeling/modifiers/generate/decimate.rst : Decimate modifier.
- https://docs.blender.org/api/3.4/bpy.types.DataTransferModifier.html : DataTransfer defaults.
- https://developer.blender.org/T61255 : generate data layers before a weight transfer.
- https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html : glTF in Godot.
- https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/importing_3d_scenes/node_type_customization.html : import name hints.
- https://surf-visualization.github.io/blender-course/basics/rendering_lighting_materials/gpu_rendering/ : headless rendering notes [u].
- https://github.com/HaiyiMei/blender-docker-headless : headless EEVEE example [u].
- https://github.com/KhronosGroup/glTF-Validator : validator, Apache-2.0, native exe.
- https://github.com/donmccurdy/glTF-Transform , https://gltf-transform.dev/cli : glTF Transform, MIT.
- https://studio.blender.org/tools/ : Blender Studio pipeline (not readable) [u].
- https://github.com/Cuvara/web-game-factory/pull/15 , https://github.com/acoliver/gone/issues/45 , https://github.com/larvuz2/poolpanic/pull/14 : prior art for agent-driven Blender pipelines [u].

## Lens 6: validation and budgets

- https://github.com/godotengine/godot/blob/4.7.2-stable/servers/rendering/renderer_rd/shaders/skeleton.glsl : GPU skinning per vertex, blend shapes per vertex per frame.
- https://docs.godotengine.org/en/latest/tutorials/3d/mesh_lod.html : auto LOD on skinned meshes may cause issues.
- https://docs.godotengine.org/en/latest/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html : import-time LOD generation.
- https://docs.godotengine.org/en/latest/tutorials/performance/optimizing_3d_performance.html : draw calls, instancing.
- https://forum.godotengine.org/t/performance-of-crowds-of-animated-rigged-characters-in-3d/130409 : 100 AnimationTrees at 60 FPS (forum, not evidence) [u].
- https://github.com/godotengine/godot/issues/92693 , https://github.com/godotengine/godot/issues/65199 : AnimationTree cost.
- https://sketchfab.com/3d-models/lethal-company-scavenger-model-game-rip-dbcd1bbe54e7485fb13d86b4b5cbaf6b : Lethal Company at about 8k tris (a game rip, not evidence) [u].
- https://docs.blender.org/manual/en/latest/addons/scene_gltf2.html : glTF exporter options.
- https://docs.github.com/en/billing/concepts/product-billing/git-lfs : 10 GiB storage and 10 GiB/month bandwidth on Free.
- https://pricingsaas.com/news/github/20251118/ , https://github.com/pricing/calculator : LFS pricing [u].
- https://docs.github.com/en/repositories/working-with-files/managing-large-files/removing-files-from-git-large-file-storage : LFS storage is freed only by deleting the repo.
- https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage : 2 GB file limit on Free.
- https://docs.github.com/en/billing/concepts/product-billing/github-actions : 2,000 Actions minutes for private repos.
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches : protected branch availability.
- https://www.fab.com/eula : Fab standard licence (403) [u].
- https://partner.steamgames.com/doc/gettingstarted/contentsurvey : Steam AI disclosure.
- https://tech-insider.org/steam-ai-disclosure-2026/ , https://blog.promise.legal/ai-game-assets-copyright-steam-disclosure-2026/ : 2026 Steam AI update [u].
- https://store.steampowered.com/news/group/4145017/view/3862463747997849618 : Valve's 2024 AI post.
- https://www.meshy.ai/terms-of-use : Meshy ownership terms.

## Gap 1: money, licence and platform

- https://www.meshy.ai/pricing : Stripe, cards, no PayPal listed; 50% off the first month; price cards did not render.
- https://www.meshy.ai/terms-of-use : section 3.2 paid output owned; 2.6 limits; 2.9 training; updated 2026-09-19; no country clause.
- https://www.meshy.ai/animation-library : 631 clips, 22 free; "Animated exports follow your plan's license"; motion source not disclosed.
- https://help.meshy.ai/en/articles/9992023-if-i-cancel-my-subscription-will-all-my-models-revert-to-a-cc-by-4-0-license : ownership kept after cancelling (updated 2026-08-27).
- https://developers.tripo3d.ai/en/terms : Tripo paid output owned, no training on paid content, Hong Kong law, Stripe.
- https://docs.tripo3d.ai/get-started/introduction.html : Tripo V2 unmaintained from 2026-10-01, retired 2026-11-01.
- https://github.com/tryAGI/Tripo : V3 endpoint (third-party SDK) [u].
- https://itch.io/docs/creators/payments : itch.io pays through the seller's PayPal or Stripe.
- https://itch.io/t/3122625/unable-to-buy-game-i-think-because-the-developer-is-in-ukraine-any-workaround : the Ukraine issue concerns sellers.
- https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html : Mixamo terms (403) [u].
- https://docs.github.com/en/get-started/learning-about-github/githubs-plans : protected branches on private repos need Pro.
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets : rulesets availability [u].
- https://partner.steamgames.com/doc/gettingstarted/contentsurvey : Pre-Generated and Live-Generated AI disclosure.
- https://respawn.outlookindia.com/gaming/gaming-news/valve-clarifies-steam-ai-policy-focus-shifts-to-content-consumed : the January 2026 update [u].

## Gap 2: toy proportions, clips and style

- https://quaternius.itch.io/universal-animation-library : Standard free (45 clips); Pro $9.99+; Source $14.99+; CC0; both root-motion versions.
- https://quaternius.itch.io/universal-animation-library-2 : UAL2 Standard 42 clips; Source $14.99+; CC0.
- https://defold.com/llms/examples/animation/3d_animations/ : exact UAL Standard clip names.
- https://quaternius.itch.io/universal-animation-library/devlog/1326702/updated-files-v20-new-animation-library : v2 update renamed bones.
- https://digitalproduction.com/2026/02/10/130-animations-one-rig-zero-drama/ : UAL2 coverage.
- https://quaternius.com/packs/universalanimationlibrary.html : generic "60-70%" tier line (refuted by the clip counts).
- https://store.godotengine.org/asset/quaternius/universal-animation-library/ : UAL on the Godot Asset Store.
- https://docs.godotengine.org/en/latest/tutorials/assets_pipeline/retargeting_3d_skeletons.html : retargeting copies rotations; Fix Silhouette limits.
- https://godotengine.org/article/inverse-kinematics-returns-to-godot-4-6/ : TwoBoneIK3D and the 4.6 IK family.
- https://docs.godotengine.org/en/latest/classes/class_twoboneik3d.html : TwoBoneIK3D properties.
- https://github.com/godotengine/godot/issues/112964 : the IK end bone ignores the target rotation.
- https://docs.midjourney.com/hc/en-us/articles/32083055291277-Terms-of-Service : Midjourney ownership (403) [u].
- https://openai.com/policies/row-terms-of-use/ : OpenAI output assignment (403) [u].
- https://terms.law/ai-output-rights/midjourney/ : AI image copyrightability [u].
- https://docs.blender.org/manual/en/latest/render/cycles/baking.html : bake to a colour attribute.
- https://github.com/jiegec/blender-scripts/blob/master/bake_vertex_colors_to_texture_image.py : vertex colour baking script.
- https://gobkit.itch.io/gobkit-free-minions : CC0 basic clips [u].
- https://kenney.nl : Kenney CC0 assets.

## Gap 3: first person, spectating, self-view and outline

- https://github.com/godotengine/godot/pull/93142 : z clip scale and FOV override in materials (4.5).
- https://docs.godotengine.org/en/4.7/tutorials/shaders/shader_reference/spatial_shader.html : Z_CLIP_SCALE, IN_SHADOW_PASS, stencil_mode in shaders.
- https://github.com/godotengine/godot-proposals/discussions/8941 : first-person viewmodel approaches [u].
- https://github.com/benjr70/space-pirates/issues/30 : community first-person arms prior art [u].
- https://godotshaders.com/shader/first-person-view-model-shader/ : viewmodel shader example [u].
- https://lethal.miraheze.org/wiki/Spectator : Lethal Company spectator view [u].
- https://forums.unrealengine.com/t/controllable-third-person-camera-spectating-system-like-in-lethal-company/2213924 : third-person spectating [u].
- https://docs.godotengine.org/en/4.7/tutorials/rendering/viewports.html : SubViewport own world, update modes.
- https://uhiyama-lab.com/en/notes/godot/subviewport-techniques/ : mirror cost [u].
- https://godotengine.org/asset-library/asset/3983 : Mirror3D add-on (licence not checked).
- https://docs.godotengine.org/en/4.7/tutorials/3d/standard_material_3d.html : stencil outline needs shared vertices; stencil materials draw in the transparent pass.
- https://raw.githubusercontent.com/godotengine/godot/master/scene/resources/material.cpp : how BaseMaterial3D emits the stencil outline.
- https://godotshaders.com/shader/stencil-based-silhouette/ : stencil example (licence not checked) [u].
- https://docs.godotengine.org/en/4.7/classes/class_springbonesimulator3d.html : spring bone center modes.
- https://github.com/godotengine/godot/issues/110975 : spring bone jitter on an interpolated body (unread).
- https://github.com/godotengine/godot/issues/105616 : BoneAttachment3D snapping (unread).
- https://docs.godotengine.org/en/4.7/classes/class_geometryinstance3d.html : SHADOWS_ONLY casting.
- https://docs.godotengine.org/en/4.7/tutorials/shaders/shader_reference/shading_language.html : 16 instance uniforms.
- https://docs.godotengine.org/en/4.7/tutorials/3d/mesh_lod.html : LOD on skinned meshes.

## Licence table

"Public repo ok" means a raw file may sit in the public game repo. "Owned" = the paying customer owns the output.

| Tool, service, library or asset source | Licence | Commercial | Attribution | Public repo ok |
|---|---|---|---|---|
| Godot 4.7.2 (all nodes named) | MIT | yes | licence notice in the game | yes |
| GdUnit4 | MIT | yes | notice | yes (already in addons/) |
| Blender 5.2.2 | GPL-2.0-or-later source, GPL-3.0-or-later binaries; outputs are yours | yes | no (outputs) | outputs yes; do not commit binaries; published bpy scripts must be GPL-compatible |
| bpy (PyPI) | GPL-3.0 | yes | no | do not vendor |
| Khronos glTF-Validator | Apache-2.0 | yes | notice if redistributed | tool not committed |
| glTF Transform | MIT | yes | notice | tool not committed |
| Pillow | HPND (MIT-like) [u: memory] | yes | notice | tool not committed |
| Meshy paid output (models, rigs, animated exports) | owned (terms 3.2); Meshy keeps a service licence and may train (2.9) | yes | no | baked GLBs yes; raw library motions keep private |
| Meshy free output | CC BY 4.0 per terms; "personal and evaluation use" per library page | disputed | yes | never use |
| Tripo paid output | owned; no training on paid content | yes | no | yes |
| Tripo free output | Tripo keeps all rights | no | n/a | no |
| Rodin (Hyper3D) output | "will not limit your use"; trains, no opt-out | yes | no | yes [u] |
| Hunyuan3D 2.1 open weights | Tencent community licence; not EU/UK/KR; >1M MAU needs a licence | yes, restricted | NOTICE | outputs yes [u] |
| Hunyuan3D hosted API | terms not found | [u] | [u] | [u] |
| Sloyd Plus / Pro | commercial; resale on Pro; terms not read | yes | [u] | [u] |
| CSM | customer-owned on paid plans [u]; acquired | [u] | [u] | do not use |
| TRELLIS.2 | MIT (dependencies have own licences [u]) | yes [u] | notice | not used |
| Stability SF3D / SPAR3D | community licence, under $1M revenue, "Powered by Stability AI" [u] | yes, restricted | yes | not used |
| Hitem3D | paid private and commercial; free CC BY 4.0 [u] | yes (paid) | credit asked | not used |
| AccuRIG 2 (Reallusion) | Reallusion software EULA; free [u] | yes [u] | no | rig outputs yes [u]; sample characters no |
| Quaternius UAL 1 and 2 (Standard, Pro, Source) | CC0 1.0 | yes | no | yes |
| Kenney | CC0 [u] | yes | no | yes |
| Gobkit Free Minions | CC0 [u] | yes | no | yes |
| Adobe Mixamo | Adobe terms, royalty-free in games [u] | yes [u] | no | no for raw files [u] |
| Rokoko free library | commercial in projects; no raw redistribution [u] | yes | no | no |
| CMU mocap | free for all uses; no resale [u] | yes | no | probably [u] |
| ActorCore | content EULA; embedded only [u] | yes | no | no |
| Unity Asset Store | Asset Store EULA; no redistribution | yes, embedded | no | no |
| Fab (Epic) standard licence | Fab EULA [u] | yes | no | no |
| Synty (Sidekick and packs) | Synty EULA; no sharing source files outside the team | yes, embedded | no | no |
| Bandai Namco Research Motion Dataset | CC BY-NC 4.0 | no | yes | never |
| AMASS, HumanML3D, models trained on them (MDM) | research only [u] | no | n/a | never |
| DeepMotion | paid outputs owned; free non-commercial [u] | paid yes [u] | no | [u] |
| Move.ai, Plask, Rokoko Vision | terms not read | [u] | [u] | [u] |
| Cascadeur | indie/pro licence; your work is yours [u] | yes [u] | no | outputs yes [u] |
| Midjourney outputs | you own; over $1M revenue needs Pro or Mega [u] | yes (paid) | no | yes [u] |
| OpenAI image outputs | assigned to the user [u] | yes | no | yes [u] |
| Okabe-Ito colour values | facts, free to use [u] | yes | no | yes |
| godotshaders.com snippets | per item, not checked | [u] | [u] | write our own |
| Mirror3D add-on | not checked | [u] | [u] | not used |
| GitHub Free (LFS, Actions) | service terms; 10 GiB LFS, 2,000 private minutes | n/a | n/a | n/a |
| Steam | AI content disclosure required for shipped AI content | n/a | n/a | n/a |
