# Lens 3: animation (art track, #165, wave 1)

Read on 2026-10-02. API names below were checked against
`D:/prime-game/tools/out/godot-api/4.7.2/extension_api.json` (a local script printed members of each class).
"[unconfirmed]" = no primary source opened (forum, third-party blog, search-result summary or memory).

## 1. Godot 4.7.2 API facts (checked in extension_api.json)

- `AnimationTree` inherits `AnimationMixer`. Mixer props: `deterministic`, `root_motion_track`, `root_motion_local`,
  `callback_mode_process` (PHYSICS/IDLE/MANUAL), `reset_on_save`; methods `add_animation_library`, `capture(name,
  duration, trans_type, ease_type)`, `advance`, `get_root_motion_position` and accumulators. Tree props: `tree_root`,
  `advance_expression_base_node`, `anim_player`.
- `AnimationNodeStateMachine` props `state_machine_type` (ROOT/NESTED/GROUPED), `allow_transition_to_self`,
  `reset_ends`. Playback (`AnimationNodeStateMachinePlayback`): `travel(to_node, reset_on_teleport=true)`, `start`,
  `next`, `stop`, `get_current_node`, `get_travel_path`; signals `state_started`, `state_finished`.
- `AnimationNodeStateMachineTransition`: `xfade_time`, `xfade_curve`, `break_loop_at_end`, `reset`, `priority`,
  `switch_mode` (IMMEDIATE/SYNC/AT_END), `advance_mode` (DISABLED/ENABLED/AUTO), `advance_condition`,
  `advance_expression`.
- Docs (primary, https://docs.godotengine.org/en/latest/tutorials/animation/animation_tree.html): `travel()` uses A*
  over transitions whose advance mode is Enabled or Auto, and teleports if no path; advance expressions are evaluated
  against `advance_expression_base_node`; OneShot fired by
  `tree["parameters/<OneShot>/request"] = AnimationNodeOneShot.ONE_SHOT_REQUEST_FIRE`, `parameters/<OneShot>/active`
  readable; Blend2 filters allow layering; deterministic blending needs a RESET animation for initial values.
- `AnimationNodeOneShot`: `mix_mode` (BLEND/ADD), `fadein_time`, `fadeout_time`, fade curves, `break_loop_at_end`,
  `abort_on_reset`, `autorestart*`; request enum NONE/FIRE/ABORT/FADE_OUT.
- `AnimationNodeBlendSpace1D/2D`: `blend_mode` (INTERPOLATED/DISCRETE/DISCRETE_CARRY), `sync`, `sync_mode`
  (NONE/INDEPENDENT/CYCLIC_MUTABLE/CYCLIC_CONSTANT), `cyclic_length`; 2D has `auto_triangles`. The cyclic sync modes
  keep walk/run cycles phase-aligned when blending (good against foot pops).
- Also present: `AnimationNodeBlend2/3`, `Add2/3`, `Sub2`, `TimeScale`, `TimeSeek`, `Transition`, `BlendTree`,
  `AnimationNodeAnimation` (`loop_mode`, `use_custom_timeline`, `stretch_time_scale`, `start_offset`),
  `AnimationNodeExtension`. Filters live on `AnimationNode` (`filter_enabled`, `set_filter_path`).
- Skeleton modifiers (all inherit `SkeletonModifier3D`, props `active`, `influence`; run after the AnimationMixer
  result each frame): `PhysicalBoneSimulator3D`, `SpringBoneSimulator3D` (+ `SpringBoneCollisionSphere3D/Capsule3D/
  Plane3D`), `LookAtModifier3D`, `AimModifier3D`, `CopyTransformModifier3D`, `ConvertTransformModifier3D`,
  `BoneConstraint3D`, `BoneTwistDisperser3D`, `LimitAngularVelocityModifier3D`, `RetargetModifier3D`,
  `ModifierBoneTarget3D`, `XRBodyModifier3D`, the IK family `IKModifier3D` → `TwoBoneIK3D`, `ChainIK3D`,
  `SplineIK3D`, `IterateIK3D`, `FABRIK3D`, `CCDIK3D`, `JacobianIK3D`; legacy `SkeletonIK3D` still exists.
- IK history (primary): IK returned in 4.6 as `IKModifier3D` with 7 solvers; `TwoBoneIK3D` and `SplineIK3D` are
  deterministic, `IterateIK3D` optionally deterministic (good for online), `BoneTwistDisperser3D` and
  `LimitAngularVelocityModifier3D` added alongside. https://godotengine.org/article/inverse-kinematics-returns-to-godot-4-6/
  `TwoBoneIK3D` has `set_pole_node`/`set_pole_direction` in 4.7.2 (API dump), so a pole target exists for knees/elbows.
- 4.7 release notes list no animation, skeleton, IK, ragdoll or Jolt changes beyond editor track collapsing and
  `Tween.tween_await()`. https://godotengine.org/releases/4.7/ So the 4.6 system is current.
- `SkeletonModifier3D` (since 4.3) runs after the AnimationMixer, with signal `mixer_applied` on the mixer and
  `modification_processed` on the modifier. https://godotengine.org/article/design-of-the-skeleton-modifier-3d/
  (primary, title read in search; body not fetched).
- `PhysicalBone3D.JointType`: NONE, PIN, CONE, HINGE, SLIDER, 6DOF; props `joint_offset`, `joint_rotation`,
  `body_offset`, `mass`, `friction`, `bounce`, `gravity_scale`, damping, `linear_velocity`, `can_sleep`;
  `apply_impulse`, `apply_central_impulse`. `PhysicalBoneSimulator3D.physical_bones_start_simulation(bones:
  Array[StringName] = [])` (empty = all; a list = partial ragdoll), `physical_bones_stop_simulation`,
  `physical_bones_add_collision_exception`.
- Ragdoll docs (primary, https://docs.godotengine.org/en/latest/tutorials/physics/ragdoll_system.html): "Create
  Physical Skeleton" makes PIN joints by default (crumpling); use HINGE for elbows/knees, CONE for shoulders, hips,
  neck; remove small bones; partial ragdoll by passing bone names; `influence` 1.0 = full override, lower blends with
  animation; set collision layers so the character's own capsule does not hit its ragdoll.
- Jolt (primary, https://docs.godotengine.org/en/latest/tutorials/physics/using_jolt_physics.html): built in since 4.4
  and the default for new projects; ignored joint params: PinJoint `bias/damping/impulse_clamp`, Hinge
  `bias/softness/relaxation`, ConeTwist `bias/relaxation/softness`, 6DOF limit softness/restitution/damping/ERP
  (warning if non-default); single-body joints invert (setting `physics/jolt_physics_3d/joints/world_node`). The doc
  says nothing specific about PhysicalBone3D.
- [unconfirmed] Jolt 6DOF/ConeTwist angular limits are pyramid-shaped and enforced more strictly than Godot Physics,
  so ragdoll limits must be anatomically tight (third-party blog
  https://www.strayspark.studio/blog/godot-46-jolt-physics-migration-guide). Open issues to watch:
  https://github.com/godotengine/godot/issues/96202 (PhysicalBone not following animation),
  https://github.com/godotengine/godot/issues/102638 (Jolt warnings for PhysicalBone3D on a physics thread),
  https://github.com/godotengine/godot/issues/107461 (6DOF velocity-dependent movement).
- Partial ragdoll hit reaction by tweening `influence` 0.8 → 0 over 0.5 s [unconfirmed, forum/third party]:
  https://forum.godotengine.org/t/active-ragdoll-in-godot-4-5-how-to-achieve-good-results/128728

## 2. In-place versus root motion (host-authoritative)

Remote bodies are placed by interpolated host snapshots; the own player moves by its controller. Root motion would
fight both. Use in-place clips everywhere and leave `root_motion_track` empty. Match visual cadence to real speed
with a `TimeScale` node (speed / clip_native_speed) and BlendSpace cyclic sync. Quaternius UAL ships both
root-motion and in-place versions (vendor page, https://quaternius.itch.io/universal-animation-library); Meshy's docs
do not say [unconfirmed]. Root-motion clips can still be converted to in-place at import by picking the root bone as
`root_motion_track` and ignoring the extracted motion (docs above), but that only cancels the root bone, so a clip
that moves the hips forward still drifts: prefer in-place sources.

## 3. Shared AnimationLibrary

All characters share one skeleton (the character contract) and import through `BoneMap` → `SkeletonProfileHumanoid`
(both in 4.7.2), so every track path is `Skeleton3D:<HumanoidBoneName>`. One `AnimationLibrary` resource (e.g.
`humanoid.res`) is added to every character's AnimationTree with `add_animation_library("", lib)`, or set once in a
shared scene. Animations from different sources (Quaternius, Meshy, Mixamo) become interchangeable after the same
retarget at import (the #165 BoneMap plan). This is the main reason to fix the skeleton first. [unconfirmed: retarget
quality across sources with different rest poses; needs the Wave-2 probe with "Fix Silhouette" and rest-fixer options.]

## 4. Recommended AnimationTree layout

### Remote players (third person), `tree_root` = `AnimationNodeBlendTree`
```
Body (StateMachine, ROOT)                                   ← travel() from life state events
 ├ Ground: BlendSpace2D (x = local strafe m/s, y = local forward m/s; idle at 0,0; walk ring; sprint ring;
 │          sync_mode CYCLIC_*) → TimeScale
 ├ Air: StateMachine NESTED: JumpStart → FallLoop → Land (AT_END / auto on is_on_floor)
 ├ Downed: BlendSpace1D (0 = downed_idle, 1 m/s = crawl)
 ├ BeingRaised (downed → get-up driven by TimeSeek from the 3 s progress), Raising (kneel loop)
 ├ Knockdown (one-shot fall clip, then partial ragdoll, see §5) → Downed
 └ Dead (death clip end pose held; ragdoll limbs)
→ UpperBody Blend2 (filter: Spine*, Chest, UpperChest, Neck, shoulders, arms, hands; amount 0/1 smoothed):
     input = Hold StateMachine (empty / carry_package / hold_knife; Blend2 per item pose)
→ Action OneShot (same upper-body filter): knife strike, pick up, put down, swap hand/belt, point
→ Emote OneShot (no filter, full body): wave, dance, laugh, facepalm, shrug, cheer — lobby and alive only
→ Talk Add2 (filter: Head, Neck, Jaw): additive nod/jaw clip, amount = smoothed voice level
→ Output
then SkeletonModifier3D children of Skeleton3D, in order:
  LookAtModifier3D or AimModifier3D (head/neck pitch from the relayed look pitch, clamped),
  SpringBoneSimulator3D (cosmetic jiggle bones), PhysicalBoneSimulator3D (influence 0 until needed).
```
- Transitions: `xfade_time` 0.15 to 0.25 s with an ease `xfade_curve`; `advance_mode` AUTO with
  `advance_expression` against a small "AnimState" script node (`on_floor`, `life_state`, `speed`) set as
  `advance_expression_base_node`; discrete host events (downed, raised, died) call `playback.travel()` (or `start()`
  for teleports such as a late joiner).
- Velocity for the blend space: differentiate the interpolated position each render frame, rotate into the body's
  local frame, and low-pass it (lerp toward target, ~10/s) so 20 Hz snapshot steps do not jitter the blend.
  [inference] Smoothing guidance from a third-party fix note: https://bugnet.io/blog/fix-godot-animationtree-blend-not-transitioning
- Talking: an Add2 on head/jaw is cheap; if the character has no jaw bone, drive a blend shape or a head-bob bone
  directly from code instead. [unconfirmed] exact Add2 additive reference (rest vs RESET) in Godot 4: test in Wave 2.
- Everything is client-side cosmetic and read from data the client already has (snapshot position, life state,
  look pitch, voice level). Nothing feeds back into gameplay, so no hidden information leaks.

### Own first-person arms
Same skeleton and the same AnimationLibrary, with only an arms mesh visible (or the full body with head/torso hidden
via a cull layer) and a small tree: `Hold` StateMachine (empty, package, knife) → Action OneShot (strike, pick up,
put down, swap) → procedural bob/sway in code from the controller's velocity. Benefit: one strike clip serves both
views, so what you do and what others see match. [inference, medium confidence] Typical FPS games author separate
FP arm clips because full-body clips look wrong from the camera; budget a few FP-specific clips (hold poses, strike)
keyed by Blender Python scripts if the shared ones read poorly in `shot` renders.

## 5. Funny physical falls

- Recommended (cheap, consistent): play a cartoony fall clip (Knockdown or Death) whose end pose lies at the host's
  body position, then `physical_bones_start_simulation(limbs_head_spine)` excluding Hips, with an impulse from the
  hit direction (`apply_central_impulse`), `influence` 1 → hold → tween back toward the lying pose. Hips stay
  animated, so the body cannot slide away from where the host put it. For DOWNED, tween `influence` to 0 and travel
  to Downed; for DEAD, let it settle (~1.5 s) then keep simulation frozen (bodies sleep) or snapshot the pose.
- Full ragdoll (all bones): funnier but the hips drift; re-centre the visual root on the host position after settling
  or pin the hips bone. Collision layers per the docs, and exclude other players' capsules to avoid ragdoll fights.
- Active ragdoll (Gang Beasts, Human: Fall Flat): a physical body driven toward an animated target pose by joint
  torques plus external balance forces (HFF pulls the chest up) [unconfirmed, third-party write-ups:
  https://medium.com/@jacasch/balancing-of-active-ragdolls-in-games-367f146b25fb,
  https://jacasch.itch.io/real-guys-wear-ties/devlog/85804/active-ragdoll-system]. Not recommended: movement would
  become physics-driven, which conflicts with client-side movement + host checks (invariant 7) and first-person
  control, and costs a lot to tune.
- Procedural wobble without physics: `SpringBoneSimulator3D` on optional cosmetic bones (ears, antennae, hats,
  hair, backpack, belly) with collision spheres; plus code-driven lean on acceleration and a tiny squash on landing.
  This gives most of the "cringe-fun" jiggle at almost no cost. The contract should reserve optional jiggle chains.
- Jolt specifics: use CONE for shoulders/hips/neck and HINGE for elbows/knees; do not rely on softness/bias params
  (ignored); probe stability headless in 4.7.2 early (issues above).

## 6. Animation set and where each clip can come from

Legend: Q = Quaternius UAL 1/2 (CC0), M = Meshy library (paid, Meshy rigs only, #165), X = Mixamo (free, raw
redistribution banned), K = Kenney (CC0, list not verified). Meshy IDs from https://docs.meshy.ai/en/api/animation-library
(page read through a summarizer; IDs not individually verified).

| Clip | Q | M | X | Note |
|---|---|---|---|---|
| idle, walk, sprint | yes (8-dir loco, jog, sprint) | yes (Idle 0, Walking_Woman 1, Run_02/03, RunFast) | yes [unconfirmed] | |
| jump, fall loop, land | likely [unconfirmed] | Regular_Jump 466, Fall1-4 502-505 | yes [unconfirmed] | |
| crawl, downed idle | crawl yes | crawl per #165 | yes [unconfirmed] | downed idle may need a keyed pose |
| get up / being raised | [unconfirmed] | Stand_Up1-10 344-353, Kneel_on_One_Knee_and_Stand 365 | yes [unconfirmed] | |
| raising someone (kneel loop) | [unconfirmed] | kneel 365 | yes [unconfirmed] | |
| knife strike | combat/melee (UAL2) | Left_Slash 97, Attack 4, sword 191-221 | yes [unconfirmed] | one-handed stab may need keying |
| pick up / put down / carry | [unconfirmed] | pick-up variations 273-284, carry per #165 | yes [unconfirmed] | carry = upper-body pose |
| swap hand/belt | no | no | no | key by script (simple) |
| knockdown, death | death yes | Dead 8, death/knockdown 180-190 | yes [unconfirmed] | |
| wave, dance, cheer, clap | emotes yes (names unverified) | Big_Wave_Hello 28, Wave_One_Hand 290, FunnyDancing 22-24, Cheer 298-306, clap 299 | yes [unconfirmed] | |
| shrug | [unconfirmed] | Shrug 317 | yes [unconfirmed] | |
| point, laugh, facepalm | [unconfirmed] | not found in summary | yes [unconfirmed] | likely keyed or AI |
| talking layer | no | no | no | key a 1 s additive nod/jaw clip |

Sources: Quaternius vendor pages https://quaternius.com/packs/universalanimationlibrary.html and
https://quaternius.itch.io/universal-animation-library (120+ animations, CC0, root-motion and in-place versions;
tier details contradict: quaternius.com says Standard and Pro are free, itch.io says Standard free 45 clips, Pro
$9.99+, Source $14.99+ with .blend). UAL 2 (130+, melee combos, parkour, zombie locomotion, CC0):
https://quaternius.itch.io/universal-animation-library-2,
https://jettelly.com/blog/universal-animation-library-2-a-cross-engine-animation-pack-with-a-universal-humanoid-rig.
Listed on the official Godot Asset Store: https://store.godotengine.org/asset/quaternius/universal-animation-library/
Mixamo has about 2,300 clips [unconfirmed, https://huggingface.co/datasets/jasongzy/Mixamo]; the site is behind
login and was not browsed.

## 7. Libraries and licenses (traps marked)

- **Quaternius UAL 1/2**: CC0 1.0. Commercial yes, attribution no, public repo yes. Safest base.
- **Kenney** animated characters: CC0 per Kenney's standard terms [unconfirmed: the pack page 404'd].
- **Meshy animation library**: paid plan → we own outputs (per #165); works only on Meshy rigs. Public repo: yes if
  owned [unconfirmed: check Meshy terms for a "no redistribution of library motions" clause; #165 did not cover it].
- **Mixamo (TRAP for the public repo)**: royalty-free in games, film, commercial; but characters and animations
  "cannot be redistributed as standalone assets", and no templates or asset packages that redistribute raw files.
  Adobe helpx pages returned 403; terms taken from search snippets of
  https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html [unconfirmed]. Raw FBX/GLB or an AnimationLibrary .res
  in a public GitHub repo is downloadable standalone data: treat as not allowed. Use only in the private art repo for
  prototyping, or ship baked inside the exported game (pck) without committing to the public repo.
- **Rokoko free motion library (TRAP)**: commercial use in projects allowed, raw file redistribution or resale not
  allowed [unconfirmed: from https://www.cgchannel.com/2020/03/get-150-free-mocap-moves-from-rokokos-motion-library/
  and search summary; Rokoko pages 403/404]. Realistic mocap, not cartoony.
- **CMU mocap**: "free for all uses", may be included in commercial products, may not be resold even converted
  [unconfirmed: mocap.cs.cmu.edu TLS failed; quoted via https://www.re3data.org/repository/r3d100012183 and search].
  Public repo is probably fine (no resale) but realistic, noisy, needs cleanup. Low value for us.
- **ActorCore / Reallusion (TRAP)**: motions may be used in games and distributed only embedded in games; raw
  redistribution prohibited (Content EULA updated 2025-08-01) [unconfirmed: search summary of
  https://actorcore.reallusion.com/eula]. Paid.
- **Unity Asset Store (TRAP for public repo)**: non-restricted assets may be used in other engines when embedded in a
  product with substantial original content (§2.2.1(a)); redistribution of the asset itself is not licensed (§3.5).
  Source: https://unity.com/legal/as-terms (read through a summarizer). Raw files in a public repo = violation.
- **Bandai Namco Research Motion Dataset (TRAP)**: CC BY-NC 4.0, non-commercial; BVH, 17 + 10 content types with
  styles. https://github.com/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset
- **AMASS (TRAP)**: non-commercial scientific research only; commercial via ps-licensing@tue.mpg.de.
  https://github.com/nghorbani/amass [unconfirmed: license page not opened]. **HumanML3D (TRAP)**: derived from AMASS,
  academic only. https://github.com/EricGuo5513/HumanML3D
- **MDM** code MIT, but trained on HumanML3D/AMASS and uses SMPL (own non-commercial license) → outputs of the
  pretrained weights are legally unclear for a commercial game. MotionGPT similar [inference]. Avoid for shipped clips.
  https://replicate.com/daanelson/motion_diffusion_model/readme

## 8. AI animation services

| Service | Kind | Price (read 2026-10-02) | Rights | Fit |
|---|---|---|---|---|
| Meshy | text/library on Meshy rigs | in Meshy plan, 3 credits per action (#165) | owned on paid plan | best fit if Meshy is chosen |
| DeepMotion SayMotion | text-to-motion | free 25 credits/mo non-commercial; paid ~$15/mo (50 cr) to $300/mo [unconfirmed: pricing page did not render, figures from search summary] | paid: you own outputs; free: non-commercial [unconfirmed] https://www.deepmotion.com/terms-of-use | custom character upload FBX/GLB; exports FBX, BVH, GLB; realistic bias |
| DeepMotion Animate 3D | video-to-motion | same plans | same | good for acting out an emote on a phone video |
| Rokoko Vision | video-to-motion | free tier exists [unconfirmed] | terms page 403 | |
| Move.ai Move One | single-camera video | $18 to $490/mo [unconfirmed] https://docs.move.ai/knowledge/move-one-pricing | not read | |
| Plask | video-to-motion | free, $18/mo, $50/mo (yearly) [unconfirmed] https://plask.ai/en-US/pricing | not read | |
| Radical | video mocap | shut down: Autodesk acquired the tech, portal closing, data download until 2026-07-06 [unconfirmed, cgchannel 2026-04] https://www.cgchannel.com/2026/04/autodesk-acquires-core-tech-of-ai-motion-capture-firm-radical/ | — | do not use |
| Cascadeur | desktop animation app with AI posing/inbetweening/AutoPhysics | Indie $19/mo or $8/mo yearly (< $100k revenue), Pro $49/mo [unconfirmed, third-party pricing summaries] | own work | needs a human in a GUI: conflicts with "no windows, humans write no code" pipeline |

Quality for cartoony motion: video-to-motion reproduces what a person acts, so exaggerated emotes are possible if a
human over-acts on camera; text-to-motion models are trained on realistic mocap and tend to produce plain motion
[inference]. Neither produces squash-and-stretch; exaggeration comes from proportions, timing (TimeScale), spring
bones and ragdoll.

## 9. Recommendations

1. In-place clips only; no root motion.
2. One humanoid skeleton (SkeletonProfileHumanoid names) and one shared AnimationLibrary for all characters and the
   own FP arms.
3. Base set from Quaternius UAL 1+2 (CC0, public-repo safe); fill gaps (shrug, wave variants, kneel, stand up,
   pick-up) from the Meshy library only if the humans pick Meshy characters and its terms allow public files;
   script-key the small clips (swap, talk nod, hold poses, downed idle) with Blender Python.
4. Mixamo, Rokoko, ActorCore, Unity Asset Store: never in the public game repo. Bandai Namco, AMASS, HumanML3D and
   models trained on them: never.
5. AnimationTree as in §4; LookAtModifier3D for pitch; SpringBoneSimulator3D for jiggle; partial ragdoll with hips
   animated for falls; no active ragdoll.
6. Wave-2 probes (headless + `shot`): retarget a Quaternius clip and a Meshy clip onto one test skeleton; a Jolt
   partial ragdoll settling at a fixed hips position; frame-sheet renders of each clip for review.
