# Lens 4: AI 3D generators other than Meshy (read on 2026-10-02)

Scope: what the prime-game art track needs from a generator: a stylized low-poly "cringe-fun" look, polygon control,
clean topology, UVs and a palette, separate parts for customization, a humanoid rig on one shared skeleton, a
consistent set from a style sheet, an API, an output license fit for a sold game and a public repo, and the price
per usable asset. Meshy is the baseline from #165 and is not re-researched. Nothing was signed up for, downloaded or
generated. Every price and term below was read on 2026-10-02 and changes fast.

Marking: **[unconfirmed]** = no primary source opened (vendor page or docs); the claim rests on a search snippet, a
third-party blog, a reseller page or inference.

## 0. The one finding that matters most for customization

No generator researched makes **clothing fitted as a separate layer over a given body**. What exists is
**part segmentation of one generated mesh**: Tripo `generate_parts` / mesh segmentation + mesh completion, Rodin
"BANG to Parts", Hunyuan3D-Part (P3-SAM + X-Part), CSM "Image to Kit", Meshy "Auto Split" (aimed at 3D printing).
These cut a fused model into semantic pieces (head, torso, arm, weapon) and fill the cut holes. A "shirt" cut out of
a fused character is a solid chunk of torso, not a garment over a body, so it cannot be swapped onto another body
**[unconfirmed: inference from the vendors' descriptions; no test]**.
Consequence for the character contract:
- **Rigid accessories** (hats, masks, glasses, helmets, backpacks, belt items, hand items) are the sweet spot for AI:
  generate each as its own prop from an image, low poly, attach to a bone (`BoneAttachment3D`, present in 4.7.2's
  `extension_api.json`). Every tool below can do this.
- **Body variety** = a few AI-generated base bodies rigged to the one shared skeleton.
- **Skinned clothing** (shirts, trousers) = made in Blender from the base body (lens 2 and 5), not by a generator.
  Segmentation is at best a source of shapes to rework.

## 1. Tools

### Tripo (Tripo3D, VAST) - the strongest alternative to Meshy
- **Low poly:** `smart_low_poly` with a face limit 1,000 to 20,000 (500 to 10,000 with quad); quad output option; a
  post-process "Smart low poly" task (30 credits) that reduces an existing mesh and bakes detail into the texture.
  Sources: API pricing [docs.tripo3d.ai/get-started/pricing.html](https://docs.tripo3d.ai/get-started/pricing.html)
  (primary, lists Smart low poly and Quad as H2/H3 add-ons); the face-limit ranges come from a reseller's API page
  [runware.ai/docs/models/tripo-v3-1](https://runware.ai/docs/models/tripo-v3-1) and a search snippet of
  platform.tripo3d.ai (certificate expired, not readable) **[unconfirmed]**.
- **Parts:** `generate_parts` (+20 credits on H2/H3, requires texture off), mesh segmentation (40), mesh completion
  (50) [pricing](https://docs.tripo3d.ai/get-started/pricing.html). Generated parts need texture=false
  **[unconfirmed, search snippet of platform docs]**.
- **Rig and animation:** Auto Rig endpoint: `rig_type` biped, quadruped, hexapod, octopod, avian, serpentine, aquatic;
  `spec` `tripo` (native names) or `mixamo` (Mixamo-compatible names); model `v1.0-20240301` biped only, "90+
  animation presets"; output GLB or FBX; max 150 MB input
  [developers.tripo3d.ai/en/docs/animations-rig](https://developers.tripo3d.ai/en/docs/animations-rig) (primary).
  Rig 25 credits, retarget 10 credits per animation [pricing](https://docs.tripo3d.ai/get-started/pricing.html).
  Gotcha: retarget of Tripo presets reportedly fails (error 1004) on a `mixamo`-spec rig and works only on the
  `tripo` spec ([community PR](https://github.com/nvdtf/riptide-kitty/pull/1)) **[unconfirmed]** - the same lock-in
  as Meshy's library (works only on Meshy rigs, #165).
- **Rig quality:** a third-party UE5 test calls Tripo fastest with a standard biped and recognizable bone names but
  "over-smoothed" shoulder and chest weights
  ([strayspark.studio](https://www.strayspark.studio/blog/ai-auto-rigging-showdown-2026-tripo-meshy-cascadeur-mixamo))
  **[unconfirmed]**. The same post says Meshy's rig has non-standard spine and clavicle names and inconsistent hip
  weights (pivot 5 to 15 cm off) - relevant to #165's BoneMap step **[unconfirmed]**.
- **Style consistency:** text, image and multiview-to-model; a stylization task (Lego, voxel, Voronoi, Minecraft) is
  not our look [overview](https://docs.tripo3d.ai/get-started/overview.html).
- **API:** REST; **V2 is retired on 2026-11-01, use V3** (`https://openapi.tripo3d.ai/v3/`)
  [overview](https://docs.tripo3d.ai/get-started/overview.html),
  [migration](https://developers.tripo3d.ai/en/docs/migration-v2-to-v3). Concurrency: 10 standard generations,
  5 P1, 10 animation tasks [rate limits](https://docs.tripo3d.ai/get-started/rate-limits.html). API billing is
  separate from Studio subscriptions: **$1 = 100 credits**; image-to-model H2/H3 20 (30 textured), P1 40 (50);
  texture quality +10/+20/+30 [pricing](https://docs.tripo3d.ai/get-started/pricing.html).
- **Studio plans:** Basic free 200 credits/month; Professional $19.9/month 3,000 credits; Advanced $49.9 8,000;
  Premium $139.9 25,000 ([MakerStack](https://makerstack.co/reviews/tripo-3d-review/), search snippets)
  **[unconfirmed: tripo3d.ai/pricing returned 403]**.
- **License:** free plan: Tripo retains the rights to free users' inputs and outputs (ToS 5.2.1), models public under
  CC BY 4.0; paid plans: private models, full commercial rights, user grants Tripo a licence to use content to provide
  the service (search snippets of [terms](https://www.tripo3d.ai/terms) and
  [help](https://www.tripo3d.ai/help/privacy-policy/how-to-use-tripo-models-commercially))
  **[unconfirmed: both pages returned 403]**. Training on paid users' content: not found. Note: one snippet says the
  free plan is "CC BY 4.0, non-commercial", which is self-contradictory (CC BY allows commercial use) - read the ToS
  before relying on it.
- **Price per usable asset (estimate, API):** character = image-to-model textured 30 + smart low poly 10 + quad 5 +
  rig 25 + 5 animations x 10 = 120 credits = **$1.20 per attempt**, about **$2.50 to $4** per usable character at 2
  to 3 attempts; prop = 30 + 10 = 40 credits = **$0.40 per attempt, about $1 usable**. Inference from the primary
  price list; attempts per usable asset are a guess.

### Rodin (Hyper3D, Deemos)
- **Mesh:** Gen-2 / Gen-2.5; quad or raw triangle mesh; quad 1,000 to 200,000 faces (third-party API docs
  [wavespeed.ai](https://wavespeed.ai/docs/docs-api/hyper3d/hyper3d-rodin-v2-image-to-3d)) **[unconfirmed]**. Strength
  is high-detail and photoreal; reviewers call it less versatile for general game assets
  ([3daistudio blog](https://www.3daistudio.com/blog/best-ai-3d-character-and-avatar-generators-2026)) **[unconfirmed]**.
- **Parts:** "BANG to Parts" splits a Rodin asset into sub-models with a strength parameter
  ([80.lv](https://80.lv/articles/how-hyper3d-rodin-gen-2-5-is-bringing-production-level-control-to-ai-3d-generation),
  API page developer.hyper3d.ai/api-specification/bang_reset_v redirects to [docs.hyper3d.ai](https://docs.hyper3d.ai/))
  **[unconfirmed details]**.
- **Rig:** no humanoid auto-rig found in the docs index **[unconfirmed]**. T/A-pose option reported **[unconfirmed]**.
- **API:** REST `https://api.hyper3d.com/api/v2`, Bearer auth [docs.hyper3d.ai](https://docs.hyper3d.ai/) (primary);
  API only on Business **$120/month** ($96 yearly), 120 to 240 RPM [pricing](https://hyper3d.ai/pricing) (primary).
- **Plans:** Free: generate free, pay per download $1.50/credit, max 10 private assets, no commercial rights;
  Creator $30/month (~60 models, no API); Business $120/month (~416 models)
  [pricing](https://hyper3d.ai/pricing) (primary).
- **License:** for Rodin output "we will not limit your use of such Output"; Deemos may use prompts and outputs "to
  provide, maintain and improve our services, and conduct and support research", **no opt-out described**; outputs
  may be shown to others unless set private; no warranty of copyrightability [terms](https://hyper3d.ai/legal/terms)
  (primary). Free outputs fall under a Creative Commons licence, personal use [terms] (primary, the clause is written
  for ChatAvatar; its reach to Rodin free output is unclear).
- **Price per usable asset:** Creator ~$0.50 per model; character needs an external rig (Meshy, Tripo, AccuRIG).

### Hunyuan3D (Tencent): hosted and open weights
- **Hosted (Tencent Cloud "HY 3D Global" API and the web app 3d.hunyuanglobal.com):** per-call credits: Normal 25,
  Geometry 15, **LowPoly 30**, Sketch 25, multiview +10; Express 15 (+10 PBR); value-added: Smart Topology 50,
  **Auto Rigging 10**, UV Unfold 10, **3D Part Generation 30**, texture edit 30, convert 5. Postpaid $0.02/credit;
  prepaid 1,000 credits $15 up to 100,000 for $1,350; 200 free credits; doc updated 2026-05-08
  [tencentcloud.com/document/product/1284/75281](https://www.tencentcloud.com/document/product/1284/75281) (primary).
  Concurrency add-on $5,000 per concurrency per month (same page), so default concurrency is low.
- **Quality:** Hunyuan3D Studio paper describes PolyGen low-poly retopology, semantic UVs, segmentation and humanoid
  rigging ([arXiv 2509.12815](https://arxiv.org/html/2509.12815v1)); how much of that the Global API exposes beyond
  the price list: **[unconfirmed]**. Rig bone names: not found **[unconfirmed]**.
- **Open weights (Hunyuan3D 2.1, Hunyuan3D-Part):** "Tencent Hunyuan 3D 2.1 Community License": territory is
  worldwide **excluding the EU, UK and South Korea** ("DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH
  KOREA"); products over **1 million MAU** must request a licence; "Tencent claims no rights in Outputs"; outputs must
  not be used to improve other AI models; "Powered by Tencent Hunyuan" encouraged; NOTICE file required for
  distribution [LICENSE](https://raw.githubusercontent.com/Tencent-Hunyuan/Hunyuan3D-2.1/main/LICENSE) (primary).
  Hunyuan3D-Part uses the same template ([GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-Part)) **[unconfirmed]**.
  Running weights locally needs an install and a large GPU: out of scope now.
- **Hosted terms (ownership, training, territory):** not found on a Tencent page **[unconfirmed]**. Warning:
  hunyuan-3d.org and hunyuan3d.net are **third-party sites, not Tencent**; their "Basic/Plus/Pro" plans are not
  Tencent's.
- **Price per usable asset (estimate):** character LowPoly 30 + rig 10 = 40 credits = **$0.60 per attempt**
  (prepaid), no animation library; prop 30 credits = **$0.45**. Cheapest pay-as-you-go option found.

### CSM (Common Sense Machines)
- Plans: free 10 credits CC BY 4.0; Maker $20/month 100 credits, private, customer-owned, "Image to Kit" (parts-based);
  Creative Pro $60; Prime $111 ([creati.ai](https://creati.ai/ai-tools/csm/) and other aggregators) **[unconfirmed]**.
- **Acquired by Google, closed 2026-01-24; the team joins DeepMind**
  ([mgmtboston.com](https://mgmtboston.com/common-sense-machines-acquired-by-google/),
  [X post](https://x.com/WesRoth/status/2015711318024536273)) **[unconfirmed]**. Service continuity is unknown:
  **do not build on CSM**.

### Sloyd
- Template/parametric generator plus AI text/image-to-3D; strong at clean, game-ready props and hard-surface objects
  **[unconfirmed for quality; no test]**.
- Plans: Guest free (1 generation/day, personal use only); Plus $12.50/month yearly ($150/year), unlimited
  text/image-to-3D, 50 credits, commercial use, 1 custom art style; Pro $41.67/month yearly ($500/year), unlimited art
  styles, commercial use plus redistribution/reselling; AI rigging and animation, retexture; GLB/OBJ/FBX; API billed
  separately as prepaid credits [sloyd.ai/pricing](https://www.sloyd.ai/pricing) (primary). Terms of service not read
  **[unconfirmed: ownership and training]**.
- "Custom art style" is relevant for a consistent prop set **[unconfirmed how it works]**.

### TRELLIS.2 (Microsoft, open weights)
- **MIT licence** for code and weights; dependencies nvdiffrast and nvdiffrec have **their own licences** (my memory:
  NVIDIA source-code licences with non-commercial clauses **[unconfirmed]**); GLB with PBR up to 4K; default
  decimation target 1,000,000 faces; no parts, no rig; **NVIDIA GPU with 24 GB+**, tested on Linux only
  [github.com/microsoft/TRELLIS.2](https://github.com/microsoft/TRELLIS.2) (primary).
  Verdict: dense photoreal meshes, a local install; not for this track now.

### Stability SF3D / SPAR3D
- Stability AI Community License: free commercial use under **$1M annual revenue**; "You own any outputs"; must show
  "Powered by Stability AI"; outputs may not be used to build a foundation model
  [stability.ai/community-license-agreement](https://stability.ai/community-license-agreement) (primary). Whether
  SF3D/SPAR3D are on that licence: **[unconfirmed]** (the agreement points to the Core Models page). Single-object,
  fast, UV-unwrapped meshes; no rig or parts **[unconfirmed]**. Local install needed: not now.

### Hitem3D (Hi3D, Math Magic; Sparc3D research)
- Very high detail (1536^3, up to 2M faces), image-to-3D, aimed at 3D printing; free plan CC BY 4.0 public, paid
  private and commercial, "Created with Hitem3D" credit asked; Pro ~$19.90/month 1,000 credits; API $0.02/credit,
  $0.30 to $0.90 per model ([terms](https://docs.hitem3d.ai/en/api/resources/terms-of-use) via search snippet,
  [empiriolabs](https://empiriolabs.ai/models/hitem3d-2-0)) **[unconfirmed]**. Wrong tool for low poly.

### Others, briefly
- **Luma Genie:** sunset on 2026-01-01 ([gptprompts.ai](https://gptprompts.ai/luma-ai-guide), App Store history per
  snippet) **[unconfirmed]**. Drop.
- **Kaedim:** human-in-the-loop clean meshes, Indie $400/month (20 credits), Pro $1,200
  ([knowara](https://knowara.com/ai-tools/image/kaedim-review/)) **[unconfirmed]**. Too expensive for a hobby project.
- **Masterpiece X:** pay-as-you-go GenAI API and SDK under Developer Tools Terms
  ([docs](https://docs.masterpiecex.com/docs/getting-started)) **[unconfirmed quality and current status]**. Drop.
- **3D AI Studio, Scenario, fal, WaveSpeed, Atlas Cloud, Runware:** resellers of Tripo/Rodin/Hunyuan/Meshy models;
  a reseller adds its own terms on top of the model vendor's. Avoid: one vendor, one licence chain.
- **Anything World:** not researched (budget).
- **AccuRIG 2 (Reallusion):** free for personal and commercial use under the Reallusion Software EULA; export FBX and
  USD; full body and finger rig; **a free ActorCore account is required to export**; A-pose mesh; humanoid only
  ([ActorCore FAQ](https://actorcore.reallusion.com/learn-and-support/faq/accurig) via snippet,
  [CG Channel](https://www.cgchannel.com/2025/07/rig-and-animate-3d-characters-for-free-with-accurig-2-0/))
  **[unconfirmed]**. Rated cleanest pure-rigging output with tight weights
  ([strayspark](https://www.strayspark.studio/blog/ai-auto-rigging-showdown-2026-tripo-meshy-cascadeur-mixamo))
  **[unconfirmed]**. It is a desktop GUI (a human runs it; no headless mode found **[unconfirmed]**). Good fallback
  rigger for the one shared base skeleton; bundled sample characters fall under the separate Content EULA.

## 2. Meshy claims from #165, checked through this lens
- **Contradicted/updated:** #165 says "the faceted look comes from flat shading in the engine, not from Meshy". Meshy's
  own page now says Smart Topology "generates the mesh at a low polygon budget from the start", presets 3K/10K/30K/
  100K and "as low as 100 faces", and that "Low Poly Mode" was renamed Smart Topology
  ([meshy.ai/features/low-poly](https://www.meshy.ai/features/low-poly), primary, marketing page). So Meshy does
  shape for the budget; flat shading in Godot is still what makes it look faceted (both true).
- **Extended:** Meshy has an "Auto Split" into parts (aimed at printing)
  ([tutorial](https://www.meshy.ai/tutorials/auto-split-3d-model-into-parts)) **[unconfirmed for game use]**; it
  does not change "clothing fused to the body".
- **Consistent:** rig-locked animation libraries are the norm (Meshy and Tripo both).

## 3. Comparison table

| | Meshy (#165) | Tripo | Rodin | Hunyuan3D hosted | Sloyd | CSM |
|---|---|---|---|---|---|---|
| Low-poly control | Smart Topology 100-15k (300k max) | smart_low_poly 1k-20k (quad 500-10k) [u] | quad 1k-200k [u] | LowPoly mode 30 cr; Smart Topology 50 cr | parametric props [u] | AI retopo [u] |
| Quad option | yes | yes (+5 cr) | yes | [u] | [u] | [u] |
| Separate parts | Auto Split (print) [u] | generate_parts, segmentation, completion | BANG to Parts | 3D Part Generation 30 cr | - | Image to Kit [u] |
| Humanoid auto-rig | yes, Mixamo-style names | yes, `tripo` or `mixamo` spec | no [u] | Auto Rigging 10 cr, names [u] | "AI rigging" [u] | [u] |
| Animation library | 591, Meshy rigs only | 90+ presets, `tripo` spec only [u] | - | - | yes [u] | - |
| API | yes (Pro) | REST V3, $1 = 100 cr, separate billing | Business $120/mo only | Tencent Cloud, $0.015-0.02/cr | separate prepaid | [u] |
| Paid output | owned, commercial | owned, commercial [u] | "will not limit your use" | [u] (open weights: Tencent claims none) | commercial; resale on Pro | customer-owned [u] |
| Trains on content | may (non-Enterprise) | not found | yes, no opt-out | [u] | [u] | [u] |
| Free output | Meshy-owned, CC BY 4.0 | Tripo-owned, CC BY 4.0 [u] | CC, personal use | 200 free credits | personal use only | CC BY 4.0 [u] |
| Territory limits | none found | none found | none found | open weights: not EU/UK/KR; >1M MAU | none found | Google acquisition |
| Entry price | Pro ~$20/mo | Pro $19.9/mo [u]; API pay-as-you-go | Creator $30/mo | prepaid $15/1,000 cr | Plus $150/yr | Maker $20/mo [u] |
| ~$ per usable character | ~$1/attempt (50 cr) | ~$1.20/attempt, $2.5-4 usable | ~$0.50 + external rig | ~$0.60/attempt, no anims | [u] | - |
| ~$ per prop | ~$0.30 | ~$0.40/attempt | ~$0.50 | ~$0.45 | flat (unlimited) | - |

[u] = unconfirmed. "cr" = credits. Per-asset dollars are my estimates from the price lists.

## 4. Recommendations
- **Characters (base bodies):** primary **Meshy** (already chosen for the trial, rig + animation library, native
  low-poly). Fallback **Tripo** (API V3, smart_low_poly + quad + rig with `mixamo` spec, cheap per call). Either way
  the shipped rig is **our one skeleton**: re-rig every body to it (Meshy rig, or AccuRIG 2 by a human) and retarget
  animations via `BoneMap` to `SkeletonProfileHumanoid` (both classes present in 4.7.2's API dump).
- **Accessories (rigid, on bones):** primary **Meshy** image-to-3D with Smart Topology 300 to 2,000 faces from a
  style-sheet image per item; fallback **Tripo** image-to-model + smart_low_poly. Hunyuan hosted LowPoly is the
  cheapest pay-as-you-go option if the hosted terms check out.
- **Props:** primary **Meshy** (same subscription); fallback **Sloyd** Plus for generic hard-surface props (crates,
  furniture, packages) where parametric templates give the cleanest low poly; Tripo as second fallback.
- **Skinned clothing:** not from a generator; Blender from the base body (lens 2/5).
- **Not now:** Rodin (API needs $120/month, trains on outputs with no opt-out), CSM (acquired), Hitem3D (print
  detail), TRELLIS.2/SF3D/Hunyuan weights (local install, big GPU), Kaedim (price), Luma Genie (sunset).
- **Style consistency regardless of tool:** generate from one style-sheet image per item with the same prompt prefix,
  then **discard the AI texture** and recolour with a shared palette (one palette texture or vertex colours) in the
  Blender pipeline; that keeps a set consistent across tools and makes the generator swappable **[inference]**.
- **Licence records:** each asset's `docs/credits/` entry names tool, model version, plan (paid), date, and the terms
  URL; free-plan outputs never enter the game (Meshy/Tripo/CSM/Hitem3D free = vendor-owned or CC BY).
