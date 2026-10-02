# Gap agent 2: toy proportions, game-specific clips, style consistency

Read on 2026-10-02. Read-only research, 25-tool-call budget; nothing was downloaded. Every claim has a source.
[unconfirmed] means I could not open a primary source for it.

## 1. Quaternius UAL 1 and UAL 2: what exists, Standard and Pro

### Tiers, prices, root motion (primary: the vendor's itch.io pages)
- UAL 1: Standard (free) **45 animations**, Pro **$9.99+** (120+ clips in FBX and GLB), Source **$14.99+** (adds .blend).
  "Two versions, one with full Root Motion and one with Root Motion disabled". v3.0 "added root motion to all
  locomotion and movement animations". CC0. https://quaternius.itch.io/universal-animation-library
- UAL 2: Standard (free) **42 animations**, Source **$14.99 minimum** (110+/130+ clips plus .blend). Same two root-motion
  versions. CC0. https://quaternius.itch.io/universal-animation-library-2
- quaternius.com says, as a site-wide line, Standard is "60-70%" of a pack
  (https://quaternius.com/packs/universalanimationlibrary.html). For these two packs that is wrong: 45/120+ = about 37%
  and 42/130+ = about 32%. digitalproduction.com's "about 70% free" is also wrong for UAL 2.
- UAL 1 v2.0 (2026-01-23) "Updated to new rig naming scheme (same as modular outfits / base chars kit)" and fixed a
  double root. The rig is the same as Quaternius's base-character and modular-outfit kits, which matters for lens 2.
  https://quaternius.itch.io/universal-animation-library/devlog/1326702/updated-files-v20-new-animation-library
- A Godot Asset Store reviewer says "UpperChest's bones are bent too much, which looks bad on other characters"
  [unconfirmed, user review]. https://store.godotengine.org/asset/quaternius/universal-animation-library/

### Exact clip names
UAL 1 Standard has 45 clips. Defold's official example lists every clip in the file it uses, so this is a primary list
for that file version. Names may differ after the v2/v3 updates [unconfirmed].
https://defold.com/llms/examples/animation/3d_animations/
A_TPose, Crouch_Fwd_Loop, Crouch_Idle_Loop, Dance_Loop, Death01, Driving_Loop, Fixing_Kneeling, Hit_Chest, Hit_Head,
Idle_Loop, Idle_Talking_Loop, Idle_Torch_Loop, Interact, Jog_Fwd_Loop, Jump_Land, Jump_Loop, Jump_Start, PickUp_Table,
Pistol_Aim_Down/Neutral/Up, Pistol_Idle_Loop, Pistol_Reload, Pistol_Shoot, Punch_Cross, Punch_Jab, Push_Loop, Roll,
Roll_RM, Sitting_Enter/Exit/Idle_Loop/Talking_Loop, Spell_Simple_Enter/Exit/Idle_Loop/Shoot, Sprint_Loop,
Swim_Fwd_Loop, Swim_Idle_Loop, Sword_Attack, Sword_Attack_RM, Sword_Idle, Walk_Formal_Loop, Walk_Loop.

UAL 2 Standard: the itch.io page image shows CHEST_OPEN, CLIMB_UP_1M, COUGHING, HARVEST, PLANT_SEED, **WAVE**, KNOCKBACK,
MELEE_HOOK, MELEE_HOOK_REC, SWORD_DASH, SWORD_REGULAR_A, NINJUMP_SLASH, ZOMBIE_SCRATCH, IDLE_TALKING_PHONE and idles.
The fetch only partly read that image [partly unconfirmed]. UAL 2 has "3 and 4 hit combos, split into separate hits
with their recoveries". The UAL 2 gestures named by digitalproduction.com are surprised, thumbs up, crossed arms and
"no" [unconfirmed, tier unknown]. https://digitalproduction.com/2026/02/10/130-animations-one-rig-zero-drama/
The Pro clip names are not public: the Patreon post returned 403 and no page lists them. UAL 1 Pro covers "crawling",
"death animations" and 8-direction locomotion by category only.

### Our actions mapped to clips
| Action | Clip, tier | Status |
|---|---|---|
| idle | Idle_Loop (UAL1 Std) | confirmed |
| walk | Walk_Loop (UAL1 Std) | confirmed |
| sprint | Sprint_Loop, Jog_Fwd_Loop (UAL1 Std) | confirmed |
| jump / fall / land | Jump_Start, Jump_Loop, Jump_Land (UAL1 Std) | confirmed |
| crawl (DOWNED, 1 m/s) | category "crawling" in UAL1, not in Std, so Pro | name [unconfirmed]; Crouch_Fwd_Loop is a Std stand-in |
| downed / lying idle | none found | hand-key, or the last frame of Death01 plus breathing |
| get up | none found (Sitting_Exit is the nearest) | hand-key [unconfirmed for Pro] |
| kneel (raise a downed player) | Fixing_Kneeling (UAL1 Std) | confirmed |
| pick up | PickUp_Table, Interact (UAL1 Std) | confirmed (a table-height pick-up) |
| two-handed carry (package) | none; Push_Loop is the nearest | an upper-body pose plus IK |
| one-handed stab (knife) | Punch_Jab (UAL1 Std) as a thrust; Sword_Attack (slash); UAL2 SWORD_DASH, MELEE_HOOK | no dagger stab found |
| death | Death01, Hit_Chest, Hit_Head (UAL1 Std) | confirmed |
| wave | WAVE (UAL2 Std) | confirmed (image) |
| dance | Dance_Loop (UAL1 Std) | confirmed |
| clap, cheer, shrug, point, laugh, facepalm | none found in either pack | hand-key or another source |
| extras | thumbs up, "no", surprised, crossed arms (UAL2) | [unconfirmed] |

Result: the free Standard packs cover about 11 of the 20 actions. Pro adds crawl and probably more deaths and gestures.
It does not fill the six cartoony emotes (clap, cheer, shrug, point, laugh, facepalm), downed idle, get up or the
two-handed carry. Pro costs about $25 for both packs ("name your price" minimums), CC0. Buying is the humans' money
decision; my recommendation is yes, because it is cheap and makes the DOWNED crawl less work.

## 2. Retargeting onto toy proportions (big head, short arms)
- Godot's retargeting (BoneMap to SkeletonProfileHumanoid) unifies bone names and rests and normalises position tracks
  by height. The docs say Fix Silhouette "cannot fix silhouettes which are too different" and may not fix bone roll.
  Its options are a filter array and base-height adjustment. It does nothing for arm length or contacts.
  https://docs.godotengine.org/en/latest/tutorials/assets_pipeline/retargeting_3d_skeletons.html
- Retargeting copies rotations, so joint angles transfer but reach does not. With short arms, a clap misses, a
  facepalm stops in front of a big head, and two-handed holds drift apart. This follows from the docs; there is no
  Godot page about chibi characters [inference].
- Godot 4.6 brought IK back as SkeletonModifier3D nodes: IKModifier3D, TwoBoneIK3D, ChainIK3D/SplineIK3D, and
  IterateIK3D/FABRIK3D/CCDIK3D/JacobianIK3D. TwoBoneIK3D and SplineIK3D are deterministic, and
  LimitAngularVelocityModifier3D smooths them. https://godotengine.org/article/inverse-kinematics-returns-to-godot-4-6/ ,
  https://docs.godotengine.org/en/latest/classes/class_twoboneik3d.html (target_node, pole_node, pole_direction,
  root/middle/end bone, setting_count). All of these, plus ModifierBoneTarget3D, CopyTransformModifier3D,
  AimModifier3D, LookAtModifier3D, RetargetModifier3D and SpringBoneSimulator3D, are in the local 4.7.2
  extension_api.json (grep). SkeletonIK3D is still there but legacy.
- Known gap: godot#112964, "New IK System (TwoBoneIK3D, FABRIK3D) End Bone Ignores Target Rotation". Hand rotation needs
  a second modifier (CopyTransformModifier3D or AimModifier3D) [unconfirmed whether 4.7 fixed it].
  https://github.com/godotengine/godot/issues/112964
- I found no primary source naming "the usual fix" in Godot 4.6/4.7 for stylized proportions [unconfirmed]. Games
  usually hand-author emotes for their own proportions and use runtime hand IK for item holds [unconfirmed, general
  practice].

**Recommendation (technical):** all players share one contract skeleton and one proportion set. So retarget once,
offline, in Blender: bake each UAL clip onto the contract rig, fix contact clips there (clap, facepalm, two-handed carry)
with per-clip offsets or a baked IK pass, and ship baked clips. Godot then needs no runtime retargeting. Use runtime
TwoBoneIK3D (client-side, cosmetic) only for hands on items (the two-handed package carry, a knife grip) and its
influence blended from AnimationTree. Rule for the contract: the arms must reach the top of the head and the opposite
hand at chest height. That keeps the toy look and stops most emotes from needing rework.

## 3. Style-sheet or concept image tools and their terms
- Midjourney: "You own all Assets You create ... to the fullest extent possible". Companies above $1M/year revenue need
  Pro or Mega to own their outputs. Images are public unless you use Stealth Mode, which is Pro/Mega only. The ToS page
  returned 403, so this rests on search snippets [unconfirmed].
  https://docs.midjourney.com/hc/en-us/articles/32083055291277-Terms-of-Service
- OpenAI (ChatGPT/DALL-E, gpt-image): "We hereby assign to you all our right, title, and interest, if any, in and to
  Output". No plan threshold. The page returned 403 [unconfirmed]. https://openai.com/policies/row-terms-of-use/
- Meshy's text-to-image: its output terms follow Meshy's plan rules already in #165 (a paid plan for ownership)
  [unconfirmed, not re-read].
- Caveat: purely AI-generated images may not be copyrightable in the US (the Thaler line). A style sheet then protects
  nothing, but it does not stop us using it [unconfirmed, third-party: https://terms.law/ai-output-rights/midjourney/].
- Option without any of this: a human-drawn or paint-over style sheet. Which tool to use is a money and style decision
  for the humans.

## 4. Headless palette recolour in Blender
- I found no documented turnkey method [unconfirmed that none exists]. The parts are documented. Cycles baking can
  write to the active Color Attribute (https://docs.blender.org/manual/en/latest/render/cycles/baking.html), and
  scripts run with `blender -b -P script.py` (example:
  https://github.com/jiegec/blender-scripts/blob/master/bake_vertex_colors_to_texture_image.py).
- Plan [inference]: a script of about 100 lines. For each face, sample the base-colour image at its loop UVs
  (Image.pixels), average the samples, snap to the nearest palette entry in OKLab, then write either (a) a face-corner
  colour attribute (glTF COLOR_0; in Godot, use the material's vertex colour as albedo: check the property name in the
  API dump), or (b) UVs set to texel centres of a shared palette texture of 16x16 or so. Option (b) keeps one material
  and one tiny texture for all characters, which helps the 10-player budget. Thin details such as eyes and logos turn
  into mush at face level, so keep a small hand-painted decal texture for faces.

## 5. CC0 or cheap cartoony emote sources
- Quaternius UAL 1 and 2: CC0, the best fit (above).
- Gobkit Free Minions: CC0, but only idle, attack and dead clips [unconfirmed, vendor itch page via search].
  https://gobkit.itch.io/gobkit-free-minions
- Kenney: CC0 characters with basic clips only [unconfirmed]. https://kenney.nl
- Mixamo: free, but its terms do not allow redistributing the raw files, so they cannot sit in the public repo
  [unconfirmed, from memory; not opened].
- I found no CC0 pack with clap, cheer, shrug, point, laugh and facepalm. Options for "cartoony": exaggerate and retime
  the UAL clips in Blender (bigger arcs, holds, overshoot; a scripted per-bone rotation scale is cheap [inference]), plus
  hand-keyed or AI text-to-motion emotes on the contract rig (lens 3). The Meshy library works only on Meshy rigs (#165).

## Claim verdicts
1. "UAL ships root-motion and in-place versions": **confirmed** on both itch.io pages. Std even has Roll/Roll_RM and
   Sword_Attack/Sword_Attack_RM pairs. Whether both versions ship in every tier is [unconfirmed].
2. "UAL 2 includes melee and combat clips usable for a one-handed knife strike": **unconfirmed**. Melee clips exist
   (MELEE_HOOK, SWORD_REGULAR_A, SWORD_DASH, combos), but none is a dagger stab. UAL1 Std Punch_Jab is the closest thrust.
3. "Standard is 60-70%, Pro 30-40%": **refuted** for these packs. UAL1 Std is 45 of 120+ (about 37%) and UAL2 Std is 42
   of 130+ (about 32%). The 60-70% line is quaternius.com's generic text.
4. "Fix Silhouette handles differing proportions acceptably": **refuted**. The docs say it cannot fix silhouettes that
   are too different. It aligns rest poses (A-pose to T-pose); it does not fix reach or contacts. Rotation retargeting
   keeps locomotion acceptable, but contact clips need IK or baked fixes.
5. "One style sheet plus palette recolour keeps a multi-tool set consistent": **unconfirmed** (inference). A palette
   fixes colour only. Silhouette, proportions, edge sharpness, face style and poly density still differ between tools.
   The contract also needs proportion checks (head-to-body ratio, arm reach) and rendered turnaround review.

## Licenses
| Thing | License | Commercial | Attribution | Public repo |
|---|---|---|---|---|
| Quaternius UAL 1 (Std/Pro/Source) | CC0 1.0 | yes | no | yes (CC0) |
| Quaternius UAL 2 | CC0 1.0 | yes | no | yes |
| Godot IK modifiers | MIT (engine) | yes | engine notice | n/a |
| Midjourney outputs | ToS; owner if paid; >$1M company needs Pro | yes | no | yes if owned [unconfirmed] |
| OpenAI image outputs | ToS assigns output to user | yes | no | yes [unconfirmed] |
| Mixamo | Adobe terms | yes in games | no | no raw files [unconfirmed] |
| Gobkit Free Minions | CC0 | yes | no | yes [unconfirmed] |
| Blender | GPL (tool); outputs are ours | yes | no | n/a |
