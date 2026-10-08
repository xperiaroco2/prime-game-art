# The art pipeline

From a raw generation or download to an approved asset in the game. Based on section 2 of the wave 1 report
(`docs/research/2026-10-02-wave-1/report.md`), updated with the engineer's answers on xperiaroco2/prime-game#165
(2026-10-02). Where the report and this page differ, this page wins; where #165 and this page differ, fix this page.

## Since 2026-10-03: the character base and who decides

The direction below changed on 2026-10-03 (xperiaroco2/prime-game#165, stage 1 plan #16). Where they differ, this
section wins:
- **Characters are assembled, not generated.** The base is Quaternius' Ultimate Modular Men and Women (CC0): one
  armature with five-finger chains, plus the toe bones being added in #25. The player chooses a body type. Tops, bottoms and
  shoes are per body type; heads, hair, hats, accessories and our face parts are shared.
- **The character route:**
  - `assemble` builds characters from recipes (`docs/assembly.md`);
  - `catalogue` holds the parts and their compatibility rules (`docs/catalogue.md`);
  - `faces` holds our eyes, brows and mouths (`docs/faces.md`);
  - `retarget` and `anim-review` bake and judge the clips (`docs/animations.md`);
  - `export`, `godot-check` and `frames` carry a character into Godot 4.7.2 (`docs/godot.md`).
- **Meshy makes items and props only.** It is also tried for animations (#25); characters do not come from it.
- **Who decides:** the trust model (`docs/decisions/2026-10-03-trust-model.md`).
  - The engineer, who acts as the designer, decides taste; the engineer alone decides money and large or hard-to-reverse
    changes.
  - The art manager decides the rest and merges PRs into `main` after the gate.
  - Meshy within the plan's credits and free official downloads run under standing permissions.

## Direction (the engineer's decisions, 2026-10-02)

| Topic | Decision |
|---|---|
| Look | Orient on How to Fish's characters (near-human proportions, flat colours, soft light), then **generate variants and compare**: V1 like How to Fish, V2 a little more cartoony, V3 a painted face, V4 the CC0 Quaternius base for comparison. The best variant becomes the style reference; there is no separate style sheet. The report's "squishy toy crew" with mitten hands is withdrawn |
| Hands | **Five fingers**, so players can make hand gestures. If a generator's rig has no finger bones, agents add them in headless Blender; AccuRIG is the fallback |
| Body | **One neutral body in v1**, about 1.75 m (eyes near the game's 1.6 m), modelled in segments so clothing can replace parts. Variety comes from clothing, hair, face and skin colour |
| Clothing | **Pieces in v1:** `top`, `bottom`, `shoes` (skinned, weights transferred from the body), plus a hat or hair (`hair_or_hat`), a face accessory (`face_accessory`) and a back item (`back_item`), rigid on sockets. **Sets are saved presets of pieces**, not separate meshes |
| Face | **Eyes and mouth are changeable slots, like the hairstyle** (`eyes`, `mouth`). V1 (separate eyeballs) and V3 (a painted face) decide how they are built |
| Colour | Every piece is **recoloured from one shared palette**; flat colours with no textures, soft light and shadows, no outline by default (compared in renders) |
| Motion | **Animations only.** Falls and knockdowns are canned animations; no ragdoll and no physical wobble |
| First person | **Hands with forearms in the sleeves of your top**, running off the screen edge, plus your own shadow; never floating hands. A true first-person body may come later |
| Names | A player's name shows only when you aim at them up close. A game rule, built in the game repo; the engineer, as the designer, may object on #165 |
| AI rules | Never name How to Fish or any other game or character in a prompt, never upload their screenshots, no personal photos; `ai_generated` recorded per asset; never free-plan output |
| Raw files | `D:/prime-art-raw` on the engineer's PC; chosen originals copied to `OneDrive/prime-art-raw`; never in git |
| Who generates | An agent, through the Meshy API, from the start; each batch only after the engineer's yes to its prompts, count and credits (since 2026-10-03: the standing permission within the plan's credits, see the section above). The engineer buys the plan (Meshy Pro, one month) and sets `MESHY_API_KEY`; agents never enter keys or payment details |

The look is decided by the engineer, who acts as the designer (@SwiftySinister is not active); the art track proposes and renders,
it does not choose.

## Steps

```
[agent, one batch at a time; Meshy within the plan's credits under the standing permission, approval_ref in batches/]
 1 batch        prompts, count and credits written in a batch file with its approval_ref
 2 generate     Meshy API (text or image to 3D, about 30 credits per textured body): T-pose, five spread fingers,
                6,000-8,000 faces per body, accessories and props smaller; no game or character names in prompts.
                Files -> D:/prime-art-raw/<batch>/ with a log row per task; chosen originals -> OneDrive (raw-backup)
[agent, this repo, blender -b --factory-startup --python-exit-code 1, never a window]
 3 import       GLB in; assert the pinned Blender (5.2.2); every operator must finish
 4 check        triangles, vertices, n-gons, loose and degenerate parts, non-manifold, UVs, applied transforms,
                height, feet at 0, front -Y in Blender (+Z in glTF); budgets from the contract
 5 decimate     only if over budget, then check again
 6 rig          rename bones to the contract's humanoid names (generated by the pinned Godot), add missing bones
                (fingers included) unweighted or weighted, A-pose to T-pose applied as rest if needed
 7 weights      4 influences, normalized, none below 0.01; clothing pieces get weights transferred from the body
 8 palette      drop the AI texture; per-face colour snapped to the shared palette; face decals by hand
 9 animations   bake each source clip onto the contract rig (falls and knockdowns included); fix contacts
                (hands meet, reach the head); retime for feel; first-person arm clips for the hands-in-sleeves view
10 export       export: fixed glTF export options; Khronos glTF-Validator (pinned) -> report.json; a non-zero exit
                fails; then godot-check (headless import into godot/) and frames (off-screen Godot sheets)
11 render       8 views at 45 degrees in a 4x2 sheet with a caption; 8-frame sheets per clip; a lit hero image;
                variants side by side. Shown to the engineer as a private artifact page, never committed
[the engineer for the look; the art manager merges after the gate]
12 approve      a PR in this repo: the engineer approves the look on the review page; the art manager merges after
                the gate (trust model); the manifest gets approved_by, approved_at, approval_pr (docs/manifest.md)
[agent, game repo xperiaroco2/prime-game, its own task workflow]
13 bring in     the approved .glb (LFS), its .import, and a credits entry with the public provenance fields
14 check        the game's tools\run.cmd check and its asset tests
15 snapshot     tools\run.cmd shot at 2, 10 and 20 m, lit and dim; images in the PR
16 merge        a human merges
```

Commands by step:
- steps 1 and 2: `meshy` and `raw-backup` (`docs/meshy.md`);
- steps 3 and 11: `probe` and `render` (`docs/blender.md`);
- steps 4 and 6: `contract`, `check` and `rename-bones` (`docs/contract.md`);
- step 9: `retarget` and `anim-review` (`docs/animations.md`);
- step 10: `export`, `godot-check` and `frames` (`docs/godot.md`);
- every step: `manifest-check`, for the manifests and `sources/` records.

Characters come from `assemble` (`docs/assembly.md`) with parts from `catalogue` (`docs/catalogue.md`) and faces from
`faces` (`docs/faces.md`). Decimation, weight transfer and the palette recolour are later issues.

## What is committed
Per asset, `assets/<kind>/<id>/`: `manifest.toml`, `source/` (the working .blend), `export/` (the .glb), `report.json`.
Never: raw generations or downloads, review renders, keys. Every binary goes through Git LFS; the account's repos share
10 GiB, so drafts stay in the raw folder.

## Licences
Allowed into the public game repo (`public_repo_ok = true`): CC0, CC BY with credit, owned paid output (Meshy Pro
output: "owned, all rights reserved"), our own work. Private only (`restricted`): Mixamo, store packs, raw Meshy
library motions, anything unclear. Never: free-plan AI output, non-commercial data.

## Open (decided later, on #165)
- How eyes and mouth are built (separate eyeballs or a painted face), after the V1 and V3 renders.
- The final budgets and socket positions, measured on the first approved body (the contract, #4).
- Whether Meshy's auto-rig has finger bones (the first rigged body settles it).
- The talking mouth waits for voice playback in the game (an engine request).
