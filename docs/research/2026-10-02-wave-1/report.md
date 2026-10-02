# Art track, wave 1: research report (#165)

Date: 2026-10-02. Written by the art department's manager session from six research lenses, a synthesis, a
completeness critic and three gap checks. Sources, with one line each and a licence table, are in the next comment
("Wave 1 sources"). `[unconfirmed]` marks a claim that rests on memory, a search snippet, a single weak source or an
inference. Nothing was downloaded, bought or generated, and no game code was touched.

**Headline: Godot 4.7.2 already has everything the characters need, with no addon. Build one shared humanoid
skeleton, put all variety in colour, pattern, face and rigid add-ons, and bake every animation onto that skeleton
offline. Meshy is a source of raw models, never a dependency. Three probes decide whether the plan holds: converting
a Meshy rig to our skeleton, rendering from headless Blender on this PC, and a Jolt partial ragdoll.**

Summary in ten lines:
1. One skeleton for everyone: the 56 bones of Godot's `SkeletonProfileHumanoid`, T-pose, 1 unit = 1 m.
2. Customization in v1 = colour, pattern, face and rigid hats, masks and back items on sockets; fitted clothing is v2 Blender work.
3. AI generators (Meshy first) are good at bodies, rigid accessories and props; none makes clothing that fits another body.
4. Animations: Quaternius (CC0, free tier) covers about 11 of our 20 actions; emotes, crawl, downed and carry need Meshy clips, keying or Quaternius Pro.
5. Big-head toy proportions break contact clips (clap, facepalm, two-handed carry), so clips get fixed once in Blender, plus runtime hand IK for held items.
6. A headless Blender 5.2.2 LTS pipeline normalizes every model, checks budgets, recolours to one palette and renders 8-view sheets for your phone.
7. A human (the designer for the look) approves every asset in the private art repo; only approved, licence-checked assets enter the public game repo by PR.
8. The public game repo takes only CC0 or owned paid outputs; Mixamo, store packs and raw Meshy library motions stay out of it.
9. Meshy Pro is paid by card through Stripe (no PayPal listed); paid outputs are yours and stay yours after you cancel.
10. Sixteen decisions below are yours (and the designer's): look, faces, money, legal exposure. Everything technical is decided and listed after them.

## 1. Recommendations

1. **Adopt the character contract (section 6)** as a Proposed ADR in the game repo, with the style section left open
   for your and the designer's answers.
2. **Keep the look decisions with both humans.** The look is the designer's area (@SwiftySinister, `docs/GDD.md`).
   Please relay H1 to H11 to the designer, or answer them together. The art repo's approval rule names the designer as
   the required look approver.
3. **Recommended look (yours to decide):** a "squishy toy crew": a big head, short thick limbs, mitten hands with a
   thumb, smooth toon shading, saturated characters on muted levels, a voice-driven mouth. It reads best at 20 m, is
   the cheapest to make, and is goofy without being macho.
4. **One generator-agnostic pipeline.** Any GLB goes in and is normalized in Blender, so changing the generator later
   costs nothing. Meshy goes first because #165 already covers it.
5. **Bake animations offline.** Retarget every clip once in Blender onto the contract rig, fix contact clips there,
   and ship baked clips. At runtime only `TwoBoneIK3D` places the hands on held items.
6. **Start with probes, not production.** In order: the Blender headless probe, the Meshy trial, the rig conversion
   of its output, then the game-side spikes (a part GLB on a body, the ragdoll, spring bones).
7. **Spend almost nothing now.** Meshy Pro for one month and Quaternius Standard (free). Everything else waits until
   a probe shows a gap.
8. **Separate repos keep the public repo clean.** Drafts, raw motions and restricted files stay on your disk or in the
   private art repo. LFS storage can never be freed short of deleting a repo, and all your repos share 10 GiB.
9. **Engine-side work becomes game-repo issues** (section 7.2), done by the game's own task workflows. The art track
   does not edit game code.
10. **Ship the talking mouth after voice playback exists.** `voice/` holds only a CLAUDE.md today (live check), so the
    per-speaker level the mouth needs is an engine request for M5 or later.

## 2. Recommended pipeline

```
[human, paid service, one approved batch at a time]
 1 Style sheet  one reference image per asset family (who makes it: H11)
 2 Generate     Meshy Pro: image or text to 3D, T-pose, Smart Topology, body 3-5k / accessory 300-2,000 /
                prop 500-1,500 faces, auto-rig on bodies only. No game or character names in prompts.
                Files -> a raw folder outside both repos; a log row per generation (section 8).
[agent, art repo, blender -b --factory-startup --python-exit-code 1, one invocation shape]
 3 import       GLB in; assert the pinned Blender version; every operator through op() that raises unless FINISHED
 4 check_mesh   triangles, vertices, n-gons, loose and degenerate parts, non-manifold, UVs, applied transforms,
                height, feet at 0, front -Y in Blender (= +Z in glTF)
 5 decimate     only if over budget, then re-check
 6 rig          rename to the profile names from contract/humanoid.json (generated by the pinned Godot), add the
                missing profile bones unweighted, re-pose A to T and apply as rest if needed, check_rig
 7 weights      4 influences, normalized, drop weights below 0.01; skinned parts get weights from the base body (v2)
 8 palette      drop the AI texture; per-face colour snapped to the shared palette; face and logo decals by hand
 9 animations   bake each source clip onto the contract rig; fix contacts (arm reach, hands meet); retime for feel
10 export_glb   fixed export options; then Khronos glTF-Validator (pinned exe) -> report.json
11 render       8 views at 45 degrees in a 4x2 sheet with a caption strip; 8-frame sheets per clip; one lit hero image
[human]
12 approve      art-repo PR with the sheets; the designer approves the look, the engineer the tech; a human merges;
                the manifest records approved_by, approved_at, approval_pr
[agent, game repo, task branch]
13 bring in     .glb (LFS) + .import (shared BoneMap) + docs/credits/<slug>.md with the public provenance fields
14 check        tools\run.cmd check, a GdUnit4 tests/assets suite, a 20-body smoke scene logging draw calls
15 snapshot     tools\run.cmd shot at 2, 10 and 20 m, lit and dim, plus a deuteranopia view; PNGs in the PR only
16 merge        a human merges into main (or the stage manager into release/m<k>)
```

Animation-driven sounds (footsteps, landings, ragdoll thuds) are out of the art track's scope. Clips keep named
markers (`foot_l`, `foot_r`, `land`) so the game can add method tracks later.

## 3. Risks and mitigations

| # | Risk | Mitigation |
|---|---|---|
| 1 | A Meshy rig may not convert by renaming: non-standard spine and clavicle names and hip weights 5 to 15 cm off are reported by one blog [unconfirmed]. The Meshy-first plan rests on this. | Probe the trial output first (A10). Fallbacks: AccuRIG 2 run by a human [terms unconfirmed], or one well-made base body reused for every character. |
| 2 | Toy proportions break shared clips: rotations carry over, reach does not. Claps miss, a facepalm stops in front of the face, two-handed holds drift (Godot retargeting docs: Fix Silhouette "cannot fix silhouettes which are too different"). | A contract rule on arm reach; per-clip fixes baked in Blender; runtime `TwoBoneIK3D` for hands on items in v1. Godot issue 112964: the IK end bone ignores the target's rotation, so hand rotation needs a second modifier. |
| 3 | Blender is not installed and `blender -b` rendering on Windows is unproven: no review sheets. | The first art-repo task is a render probe (A3); `tools\run.cmd shot` in the game repo is the fallback renderer. |
| 4 | A licence trap reaches the public repo (Mixamo, store packs, Meshy library motions of undisclosed origin, free-plan outputs). LFS history cannot be cleaned without deleting the repo. | `public_repo_ok` in every manifest and credits entry; `check` refuses a licence outside an allowlist; raw motions stay private; only baked, approved GLBs go public. |
| 5 | The 10 GiB LFS quota (storage, plus 10 GiB/month bandwidth, for the whole account) runs out through drafts, renders or CI. | Raw drafts never enter git; review PNGs go as PR attachments; CI skips pointer files by default; an alert at 5 GiB. |
| 6 | Cosmetics leak hidden information: a mouth moving for a voice the listener cannot hear, or a role-tied cosmetic. | The mouth reads only the level of audio this listener actually plays (G7); no cosmetic depends on role (H7). |
| 7 | A Jolt partial ragdoll jitters or drifts from the host's body position (one blog on pyramid limits; open Godot issues 96202 and 107461). | Few bones, tight limits, hips animated, settle then freeze; a headless probe (G4); canned falls as the fallback. |
| 8 | Separately imported part GLBs misalign with the body after the BoneMap [unconfirmed inference]. | A spike with 8-side shots (G3); at first, all parts of a body in one GLB. |
| 9 | Readability fails with 10 colours, dim rooms and colour-blind players. | A second cue per player (silhouette accessory or big pattern, plus colour and name on aim); rim and emissive accents; dim-room and deuteranopia shots. |
| 10 | Budget misses: Meshy overshoots polycounts (one test: 15k asked, about 31k given), flat shading multiplies vertices, the laptop iGPU (860M) is unmeasured. | Automatic budget checks, decimation, and the 20-body smoke scene run on that laptop. |
| 11 | Style drift across 30+ assets. A palette fixes colour only, not silhouette, proportions or face style [no source]. | One style sheet per family, a proportion check (head-to-body ratio, arm reach) in check_rig, side-by-side turnaround review. |
| 12 | Vendor churn: CSM acquired by Google [unconfirmed], Luma Genie sunset [unconfirmed], Tripo API V2 retired on 2026-11-01 (confirmed), Ready Player Me shut down [date unconfirmed]. | The generator-agnostic pipeline; download everything before cancelling a plan. |
| 13 | The private art repo cannot protect main on GitHub Free (confirmed: protected branches on private repos need Pro), so an agent could push to main. | The same pre-push hook and agent rules as the game repo. GitHub Pro is a money option (H12). |
| 14 | Look-alike perception: the bean or crewmate silhouette. | Our own silhouette (a legged, neckless body with hands), no other games' names in prompts, a side-by-side silhouette review before approval. |
| 15 | Import cost grows with dozens of GLBs: re-import time and the `.godot/imported` cache in `check` and CI [not measured]. | The part spike (G3) measures import time per GLB; CI skips LFS content by default; one path-filtered asset job. |
| 16 | Meshy's own wording conflicts: the terms say free output is CC BY 4.0, the library page says "personal and evaluation use"; the terms allow training on non-Enterprise content (section 2.9), the pricing FAQ says no training use without consent. | Never use free-plan output; treat uploads as possibly used for training (H13). |

## 4. Decisions for the engineer (and the designer)

These are about the look, money, subscriptions and legal exposure. The look belongs to both of you: please relay H1
to H11 to @SwiftySinister or answer together. Each has a recommendation; "yes to all recommendations" is a valid
answer.

**H1. Overall look.** What do the characters look like?
(a) A squishy toy crew: a big head (head to body about 1:2), short thick limbs, no neck, mitten hands, bright colours.
(b) A workwear crew with screen faces (coveralls, a helmet whose visor shows an emoticon).
(c) Wobbly blank mannequins whose comedy comes from floppy physics.
*Recommendation: (a), optionally with (b)'s idea of a face you pick.* It reads best from 20 m away, is the cheapest
to make, and is goofy and welcoming for a mixed audience. (b) is the most copied look since 2023 and leans grim; (c)
looks like a placeholder without hats. The cost of (a): ready-made animations are made for normal proportions, so
claps, a facepalm and the two-handed carry need fixing once per clip in Blender (agent work, no money). Money: none.

**H2. Faces and showing who talks.**
(a) Cartoon eyes plus a mouth that moves with the voice you hear, and a small head nod.
(b) A screen face showing an emoticon you choose.
(c) No face.
*Recommendation: (a), with a few face styles to choose from.* You see who is talking, which a first-person game
otherwise lacks, and it is funny and cheap. Also in the face set: blinking, X-eyes for DEAD, dizzy eyes for DOWNED,
and a face for each emote (laugh, shrug, facepalm). Eyes may follow where the player looks, because the look pitch is
already sent. The talking mouth can only ship after voice playback exists (M5 or later). Money: none.

**H3. Smooth or faceted.**
(a) Smooth, rounded toy shading.
(b) Faceted, flat-shaded low poly (visible triangles).
*Recommendation: (a).* It fits look (a), and faceted shading splits vertices (up to about 3 per triangle), so a
faceted body must drop to about 4,000 triangles to stay inside the budget. An outline works either way: with our own
shader a faceted model can still get a gap-free outline [unconfirmed until tried]. Money: none.

**H4. Colours and telling ten players apart.**
(a) Saturated characters on muted levels, from one shared palette.
(b) Everything saturated.
(c) Muted everything plus a lo-fi filter.
*Recommendation: (a), plus a second cue for every player besides colour:* a big silhouette accessory or a big body
pattern, and the colour name and player name shown when you aim at someone. No set of ten colours is safe for
colour-blind players (Among Us had to add colour names later). The name label is UI: the designer decides its look
(G12). Money: none.

**H5. Body height and shape.** The game's capsule is 1.8 m with the eyes at 1.6 m (`content/modes/base_mode.tres`,
the designer's file).
(a) One body shape about 1.75 m tall; the toy feel comes from proportions.
(b) A shorter, squat body (about 1.4 to 1.6 m), which also needs a lower eye height and capsule: a gameplay change.
(c) Body sliders.
*Recommendation: (a).* A body shorter than the eye height puts the remote head below where its owner actually looks,
so "who is looking at me" lies. Funny bone scaling (a bigger head, wider hips, within plus or minus 10%) can come
later and stays cosmetic. Money: none.

**H6. Hands.**
(a) A mitten with a thumb.
(b) Five fingers.
*Recommendation: (a).* It holds a knife or a package readably at a distance and is cheaper to make. The skeleton keeps
all finger bones either way, so pointing still works and we can change our minds. Money: none.

**H7. What players can customize in v1, and the rules around it.**
(a) Six slots: colour, pattern, face, hat, face accessory (mask, glasses), back item.
(b) (a) plus fitted outfits (shirts, trousers).
(c) Colour only.
*Recommendation: (a) now, outfits in v2.* Outfits need Blender weight work per piece. Three designer rules, with
recommended answers: is every cosmetic available to every player from the start (yes, for v1)? Is the loadout public
and changeable only in the lobby (yes)? Can a cosmetic ever depend on the role (no; a future disguise mechanic would be
a new design). Players also need to see themselves: *recommendation: a third-person "dressing" camera or a turntable
in the lobby customization screen*, with a lobby mirror as an optional fun prop later (a mirror re-renders the scene,
so it costs more). Money: none.

**H8. Deaths and knockdowns.**
(a) A floppy ragdoll after a short fall clip.
(b) A canned cartoon animation only.
(c) Both: the clip, then floppy limbs.
*Recommendation: (c).* Floppy failure is the core of the genre's comedy. The body always stays exactly where the game
put it, so nothing changes in gameplay. If the ragdoll probe shows jitter, (b) is the fallback. Money: none.

**H9. Animation feel.**
(a) Cartoony and exaggerated.
(b) Realistic motion capture.
*Recommendation: (a).* What (a) means in practice: the free clip base (Quaternius) is fairly neutral, mocap-like
motion, so "cartoony" comes from agent scripts that exaggerate and retime those clips (bigger arcs, holds,
overshoot), plus hand-keyed or Meshy emotes. No free pack has clap, cheer, shrug, point, laugh and facepalm. Money:
none, unless H12 adds a pack.

**H10. What you see in first person, and what a dead spectator sees.**
(a) Looking down you see only your arms and your shadow (no own legs or body).
(b) You see your full body when looking down.
For spectating a living player: (i) through their eyes, as built in #168 (their arms and hand item, as on their own
screen); (ii) also a third-person view that shows off their cosmetics.
*Recommendation: (a) and (i) now, (ii) as a later option.* (b) needs camera-specific animations and clipping fixes.
Your arms wear your colour and gloves in every case. Money: none.

**H11. Who makes the style reference image.** Every generation starts from one reference image so 30+ assets look
like one family.
(a) A human draws it or paints over a generated one.
(b) Meshy's own text-to-image, inside the Meshy plan [unconfirmed that it is included and owned like 3D output].
(c) Another image generator: Midjourney (you own outputs; a company earning over $1M a year needs Pro or Mega; images
are public unless Stealth Mode) or OpenAI (output assigned to you). Both terms pages returned 403 [unconfirmed].
*Recommendation: (b) for the trial, then (a), a human paint-over of the chosen image, for the final sheet.* One tool
and one set of terms, and a human-touched reference is the strongest style anchor. Purely AI images may not be
copyrightable [unconfirmed]; that does not stop us using them. Money: (c) is another subscription.

**H12. Money and subscriptions.** Prices read 2026-10-02; they change fast.
(a) Meshy Pro for one month: about $20/month ($16/month billed yearly) [unconfirmed: third-party pages; the official
price cards did not render], 50% off the first month for new users on monthly plans (confirmed). 1,000 credits a
month; a rigged, textured character with five animations costs about 50 credits, a prop about 15 (#165).
(b) Quaternius animations: Standard free (CC0); UAL1 Pro $9.99+ adds crawl and more; UAL2 Source $14.99+; about $25
for both, one-off, CC0.
(c) Fallbacks only if Meshy disappoints: Tripo Professional $19.9/month [unconfirmed: page 403] or its API at $1 =
100 credits (about $1.20 per character attempt; paid output is yours, no training on it, Hong Kong law); Sloyd Plus
$150/year for generic props.
(d) GitHub Pro for branch protection on the private repo [price not checked], or paid LFS storage.
(e) A video-to-motion service (about $15/month or more [unconfirmed]) or a Synty pack (its licence forbids a public
repo).
*Recommendation: (a) for one month plus the free part of (b); buy Quaternius Pro only if the probes show we need its
crawl and extra clips. No (c), (d) or (e) now; GitHub stays Free.* Paying from Ukraine: Meshy uses Stripe (cards,
Apple Pay, Link; no PayPal listed) and its terms name no blocked country; whether your card passes and whether VAT is
added shows only at checkout, so read the total before confirming. itch.io (Quaternius) takes card or PayPal; the
known Ukraine problems there affect sellers, not buyers.

**H13. AI training and legal exposure.**
Meshy may train on non-Enterprise inputs and outputs (terms section 2.9); AI output may not be copyrightable and comes
with no non-infringement warranty; Steam requires disclosing shipped content "created with the help of AI tools during
development" (Steam's content survey page).
(a) Accept all three for a hobby project, with rules.
(b) Avoid AI generation and hand-model everything (far slower; no one on the team models by hand).
*Recommendation: (a).* Rules: never upload unreleased key art or personal photos; never use another game's or
character's name or screenshots in prompts; record `ai_generated` per asset so the Steam disclosure is a lookup.
Money: none.

**H14. Where raw drafts live.** The rule is decided (T8): raw generations never go into git LFS, because LFS storage
can never be freed and all your repos share 10 GiB.
(a) Your PC plus a cloud drive you already have (which one?).
(b) Paid object storage.
*Recommendation: (a); tell me the folder.* Money: none for (a).

**H15. Where approved character assets live in the game repo, and who owns that folder.** CLAUDE.md lists no assets
folder; `content/` is the designer's, `client/` the engineer's.
(a) A new engineer-owned top-level `assets/characters/` for GLBs and import settings, with the character scene in
`client/`; the designer approves the look in the art-repo PR.
(b) Under `content/` (designer-owned).
*Recommendation: (a).* Import settings, the BoneMap and the checks are engine work; the look approval already happens
upstream. Money: none.

**H16. Create the private repo `xperiaroco2/prime-game-art`.** (Already in your request: a separate yes.)
(a) Yes, private, on your personal account (a User account, live check). (b) Not yet.
*Recommendation: (a) once you have read this report.* Money: none (private repos are free; the LFS quota is shared).

## 5. Decisions by the manager (technical, announced, revertible)

Art-repo and pipeline choices:
- **T1. Generator-agnostic pipeline.** Any GLB in, normalized in Blender. Meshy first. Any other generator is only a
  money option (H12), not an announced choice. Skip Rodin (API needs $120/month; trains on outputs with no opt-out),
  CSM, Hitem3D, Luma Genie, Kaedim, hosted Hunyuan and local open weights. *Why:* vendor churn is high.
- **T2. Skeleton.** Every body is renamed and re-rigged in Blender to the 56 `SkeletonProfileHumanoid` bones, from a
  contract JSON generated by the pinned Godot (never typed by hand). A shared `BoneMap` stays as the import safety
  net. *Why:* one skeleton means one animation set for all.
- **T3. Rest pose and axes.** T-pose rest, asset front +Z (glTF), a 180-degree turn in the character scene, in-place
  clips only. *Why:* the profile's reference pose; the gameplay body faces -Z (`remote_player_body.gd`).
- **T4. Sockets.** `Marker3D` under `BoneAttachment3D` in the character scene, and a `Grip` marker in every item. No
  socket or jiggle bones in the body. *Why:* extra bones would break the identical skeleton.
- **T5. Animations are baked offline.** Retarget once in Blender onto the contract rig, fix contact clips there, ship
  baked clips; runtime `TwoBoneIK3D` only places hands on held items (the two-handed carry in v1). Rule: the hands
  reach the top of the head and meet at chest height. *Why:* every player shares one rig, so runtime retargeting buys
  nothing, and reach must be fixed per clip anyway (gap 2).
- **T6. Base clip source.** Quaternius UAL 1 and 2 Standard (CC0) first. Meshy library clips only from your paid
  plan, retargeted offline from a Meshy-rigged body [unconfirmed that this works: A10], and kept raw only in the
  private repo. Small clips (hand-to-belt swap, talk nod, hold poses, downed idle) are keyed by Blender Python.
  Never: Mixamo, Rokoko, ActorCore, and non-commercial data (Bandai Namco, AMASS, HumanML3D and models trained on
  them). The feel itself is H9.
- **T7. Review sheets: both kinds.** A flat 8-view sheet for every draft and one lit hero image for style approval.
  (A question in the synthesis; it costs nothing, so it is decided.)
- **T8. Raw drafts never enter LFS.** Only a manifest with hashes is committed; the drive is H14.
- **T9. Blender pin.** Blender 5.2.2 LTS (supported to July 2028), the portable Windows zip with its SHA-256 re-copied
  from the official `.sha256` file, a `BLENDER_BIN` variable and a doctor check in the art repo. No Blender in CI at
  first (pip `bpy` 5.2.2, Python 3.13 only, is the later option). The download needs your yes.
- **T10. Renderer.** Workbench for sheets, EEVEE for the hero frame, Cycles CPU as the fallback; sheets composed with
  Pillow. `tools\run.cmd shot` stays the in-game truth.
- **T11. Validation.** Khronos glTF-Validator (Apache-2.0) as a pinned native exe; a non-zero exit fails.
- **T12. Palette recolour.** A Blender script samples the AI texture per face, averages it, snaps it to the nearest
  palette entry in OKLab and writes UVs into a shared 16x16 palette atlas (one material, one tiny texture for every
  player). Faces, eyes and logos use a small hand-made decal texture. No turnkey method exists, so it starts as a probe
  (A8).
- **T13. Approval.** An art-repo PR approved by the designer (look) and the engineer (tech), merged by a human; the
  manifest records `approved_by`, `approved_at`, `approval_pr`. The game repo refuses an asset with no `approval_pr`.
- **T14. Art repo layout and guard.** `assets/<kind>/<name>/{manifest.toml, source/, export/, report.json}`, `raw/`
  gitignored, review PNGs as PR attachments. Main is guarded by the game repo's pre-push hook, since Free has no
  branch protection on private repos.
- **T15. Provenance.** Every manifest and credits entry records the tool, model version, plan, generation date, task
  id, terms URL, licence, `public_repo_ok` and `ai_generated`. Meshy paid output enters the game as "Meshy paid
  output, owned, all rights reserved".
- **T16. Budgets** as in the ADR (section 6), set from lens 6; the laptop smoke scene sets the final caps.
- **T17. Outline.** Optional, added only if the distance shots show poor separation. Our own shader can do an inverted
  hull (opaque) or a stencil `next_pass`; stencil-writing materials always draw in the transparent pass and stencil
  support is marked experimental, so the inverted hull is the first choice [unconfirmed until tried].

Game-side choices are **proposals in the ADR**, carried out by the game's own task workflows through the issues in
section 7.2 (the art track does not edit game code): the shared character shader with instance uniforms, the layered
`AnimationTree`, the partial ragdoll, runtime part swap by a new `MeshInstance3D` with an explicit skeleton path,
`tests/assets` and the smoke scene, the LFS pointer skip in CI, and:
- **T18. First-person arms (proposal; reverses lens 2).** Lens 2 kept the separate greybox hand rig. This report
  proposes arm meshes cut from the body, skinned to the same bone names, on a second `Skeleton3D` under the camera with
  a first-person clip set, drawn with `use_z_clip_scale` and `z_clip_scale` (and `use_fov_override` if needed) so they
  never pass through walls (an engine feature since 4.5, PR 93142). *Why:* since #168 a dead spectator renders the
  target's first-person hand, so the arms must be buildable for any peer from public data, and shared bone names let
  gloves and sleeves reuse. The first-person knife may use its 3,000-triangle budget against 1,500 in third person.
  What the player sees is H10.

## 6. ADR sketch: Character contract and art pipeline

**Status:** Proposed (2026-10-02, art track wave 1, #165). Decided by the engineer with the designer. The style
section waits for H1 to H11.

**Context.** prime-game needs third-person bodies for 4 to 10 players, first-person arms, downed and dead bodies,
lobby gestures and customization, made by agents and AI generators and approved by humans who write no code. Remote
players are greybox capsules with points for the hand, carry and belt items (`remote_player_body.gd`: hand
`(0.45, 0.95, -0.15)`, carry `(0, 0.8, -0.72)`, belt `(-0.48, 0.85, 0)` on the left hip; the body faces -Z). The
capsule is 1.8 m, radius 0.4 m, eyes at 1.6 m (`content/modes/base_mode.tres`). The host owns positions; cosmetics run
on each client and must not change gameplay or reveal hidden information. The game repo is public; the art repo will
be private. Every API name below was found in `tools/out/godot-api/4.7.2/extension_api.json`, except the import
option names, marked [unconfirmed until a probe `.import`].

**Decision.**

1. *Skeleton.* One `Skeleton3D` node named `Skeleton3D`, marked Unique Node [unconfirmed option name], with all 56
   bones of `SkeletonProfileHumanoid`, exactly its names and parents: Root, Hips, Spine, Chest, UpperChest, Neck,
   Head, Jaw, LeftEye, RightEye, and per side (Left and Right prefixes) Shoulder, UpperArm, LowerArm, Hand, the Thumb
   chain (Metacarpal, Proximal, Distal), the Index, Middle, Ring and Little chains (Proximal, Intermediate, Distal),
   UpperLeg, LowerLeg, Foot, Toes. The list is generated from the pinned Godot (`get_bone_count`, `get_bone_name`,
   `get_bone_parent`), never typed.
   - Root: present, on the ground between the feet, **no skin weights**.
   - Weighted (22): Hips, Spine, Chest, UpperChest, Neck, Head, and per side Shoulder, UpperArm, LowerArm, Hand,
     UpperLeg, LowerLeg, Foot, Toes.
   - Present, weights optional: Jaw, the eyes, the finger chains. A mitten mesh is weighted to Hand plus the Thumb
     chain.
   - No extra bones in the body: no sockets, jiggle or helpers. No duplicate names (godot#106073). Vendor rigs are
     renamed in Blender; one shared `BoneMap` with Overwrite Axis [unconfirmed option name] stays as the safety net.
2. *Rest pose.* T-pose, arms horizontal, palms down. A-pose sources are re-posed and applied as rest in Blender.
3. *Axes and scale.* glTF Y-up, 1 unit = 1 m, front +Z (`Vector3.MODEL_FRONT`; -Y in Blender). Feet at y = 0, origin
   between the feet, transforms applied. Height 1.7 to 1.8 m, eyes at about 1.6 m, inside the 0.4 m-radius capsule
   (pending H5). The character scene turns the model 180 degrees about Y to face -Z like the greybox. Clips are in
   place; `root_motion_track` stays empty. Proportion rule: the hands reach the top of the head and meet at chest
   height.
4. *Attachment points.* Each is a `Marker3D` under a `BoneAttachment3D` in the character scene, never with
   `override_pose`. Every item or accessory scene has a `Grip` `Marker3D` that lands on the socket. Start positions
   are in the character scene (facing -Z) and are re-measured on the first base body from 8-side shots.

   | Socket | Bone | Start position | Used by |
   |---|---|---|---|
   | `Socket_Head` | Head | top of the skull | hats |
   | `Socket_Face` | Head | front of the face, at eye height | masks, glasses (pending H7) |
   | `Socket_HandR` | RightHand | palm centre, grip axis along the fingers; greybox `(0.45, 0.95, -0.15)` | the hand item |
   | `Socket_HandL` | LeftHand | palm centre | IK target for two-handed holds |
   | `Socket_Carry` | Chest | in front at chest height; greybox `(0, 0.8, -0.72)` | the two-handed package |
   | `Socket_Belt` | Hips | left hip; greybox `(-0.48, 0.85, 0)` | the belt item |
   | `Socket_Back` | UpperChest | between the shoulder blades, behind the body | backpacks, capes (pending H7) |

5. *Customization slots (pending H7).* v1: `color` (palette index), `pattern` (index), `face` (atlas index), and the
   rigid slots `head`, `face_acc`, `back`. Hand and belt items are gameplay items, not cosmetics. v2: skinned `upper`
   and `lower` outfits replacing body segments, so the body is modelled in segments from day one (head, torso, upper
   arms, lower arms with hands, hips, legs with feet). Technical safety default: the loadout is public data and no
   cosmetic is derived from the role; when it may change is the designer's rule (H7).
6. *Per-part rules.* Rigid parts: no skin, one surface, origin at `Grip`, within budget, the shared character
   material. Skinned parts: bound only to profile bones, at most 4 normalized influences, weights transferred from the
   base body, one surface, the shared material. No blend shapes on the body. Runtime swap: a new `MeshInstance3D`
   with mesh, `Skin` and an explicit skeleton path (`set_skeleton_path`; the default is empty since 4.6). No runtime
   mesh merge.
7. *Material.* One shared character shader on smooth normals (pending H3) with toon lighting (as `DIFFUSE_TOON`), rim
   and an emissive accent for dim rooms. Instance uniforms (at most 16, scalars and vectors only) set with
   `set_instance_shader_parameter`: `player_color`, `pattern_index`, `face_index`, `mouth_frame`, `talk_level`. A
   256x256 palette texture plus texture arrays for patterns and faces. Face atlas: 256 px cells; frames for eyes
   open, blink, closed, X (dead), dizzy (downed), one per emote, and four mouth shapes [frame list pending H2].
   Outline optional (T17; `STENCIL_MODE_OUTLINE` is the built-in reference, not used directly by a custom shader).
8. *Animation.* One shared `AnimationLibrary` on the contract skeleton; fixed clip names with `_loop` on looping
   clips; markers `foot_l`, `foot_r`, `land`. Proposed remote tree: an `AnimationTree` with a Body
   `AnimationNodeStateMachine` (Ground `AnimationNodeBlendSpace2D`, Air, Downed `AnimationNodeBlendSpace1D`,
   BeingRaised, Raising, Knockdown, Dead), then UpperBody `AnimationNodeBlend2` (hold), Action and Emote
   `AnimationNodeOneShot`, Talk `AnimationNodeAdd2`; 0.15 to 0.25 s crossfades; `travel` for host events. Then the
   modifiers `LookAtModifier3D` (pitch), `TwoBoneIK3D` (hands on items), `SpringBoneSimulator3D` (accessories, on
   their own skeleton, center `CENTER_FROM_WORLD_ORIGIN` [unconfirmed: G5]) and `PhysicalBoneSimulator3D`
   (`physical_bones_start_simulation` on about 11 bones, hips animated, `influence` tweened; `JOINT_TYPE_CONE` for
   shoulders, hips and neck, `JOINT_TYPE_HINGE` for elbows and knees).
9. *Own view and spectating.* The own full body is `SHADOW_CASTING_SETTING_SHADOWS_ONLY`; a light at the eye uses
   `shadow_caster_mask` to skip it. First-person arms per T18 (pending H10). A spectator of a living target draws the
   target's first-person arms and hand item from public data and hides the target's body (#168).
10. *Budgets* (10 players; worst case about 20 skinned bodies with corpses).

    | Item | Target | Hard cap |
    |---|---|---|
    | Assembled character LOD0 | 8,000 tris | 12,000 tris |
    | Base body | 5,000 tris | 6,000 |
    | Hat, mask, back or belt item | 800 tris | 1,200 |
    | Hand item, third / first person | 1,500 / 3,000 tris | 2,000 / 4,000 |
    | Prop | 500 to 1,500 tris | 2,000 |
    | Skinned vertices per character | 8,000 | 12,000 (faceted look: about 4k tris to stay inside) |
    | Bones | 56 | 64 deform, 80 total |
    | Weights per vertex | 4, normalized, none below 0.01 | 4 |
    | Blend shapes | 0 on the body | 12 on a separate head mesh (v1: none) |
    | Surfaces per character | 6 | 8 |
    | Textures | palette 256; arrays 256 per layer | character 1024, accessory 512, power of two, VRAM-compressed, no normal maps |
    | Character textures in VRAM | | 64 MB |
    | LOD | auto LOD (`generate_lods`), checked by shots at 10 and 30 m | off per mesh if it tears (docs: "especially in skinned meshes") |
    | Files | | character .glb 5 MB, accessory 1 MB, animation library 10 MB |
    | Runtime | `AnimationTree` off for settled corpses and off-screen bodies; parts under 10 cm cast no shadow | |
    | Smoke scene (20 bodies) | log `get_rendering_info` (`RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME`, `RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME`) and frame time | fail above 600 draws or 1M primitives |
    | Readability | about 86 px tall at 20 m at 1080p | two identifiers per player |
    | LFS | approved exports only | alert at 5 GiB of 10 GiB |

11. *Style (placeholder for H1 to H11).* Look: ___. Faces: ___. Shading: ___. Palette: ___ (ten player colours varied
    in lightness, checked in a deuteranopia shot). Hands: ___. Animation feel: ___. Style reference: ___. Prompts never
    name other games or characters.
12. *Review loop.* Art repo: the Blender check report and the validator pass; an 8-view sheet (45-degree steps,
    orthographic, 512 px cells, 4x2, a caption with asset, hash, triangles, vertices, bones, materials, texture size,
    height, verdict); an 8-frame contact sheet per clip; a lit hero image; a PR approved by the designer (look) and
    the engineer (tech), merged by a human; the approval recorded in the manifest. Game repo: `check`, the asset
    tests, `shot` at 2, 10 and 20 m lit and dim plus deuteranopia, PNGs in the PR; a human merges.
13. *Provenance and licences.* A manifest per asset: id, kind, slot, source service, plan, generated_at, task ids,
    raw sha256, tools, licence, licence URL, `public_repo_ok`, `ai_generated`, approved_by, approved_at,
    approval_pr. Allowed in the public repo: CC0, CC BY (with credit), owned paid output, our own work. Never:
    free-plan output, Mixamo, Fab, Unity Asset Store, Synty, ActorCore or Rokoko raw files, raw Meshy library motions,
    non-commercial data.
14. *Entering prime-game.* An agent copies the approved export into a game-repo task branch: the `.glb` (LFS), its
    `.import` with the shared `BoneMap` and Use Named Skins on [unconfirmed option name], and
    `docs/credits/<slug>.md` with the public fields. `check` refuses a missing credit, a licence outside the allowlist
    or a missing `approval_pr`. A human merges.

**Alternatives considered.** Each vendor's own rig with runtime retargeting (`RetargetModifier3D`): rejected, one rig
is simpler and contacts need per-clip fixes anyway. Runtime skinned mesh merge: no engine API, not worth it at 10
players. Synty Sidekick modular characters: its licence forbids a public repo. Skinned outfits in v1: AI cannot make
them; v2. A full-body first-person view: camera-specific clips and clipping fixes (H10). Socket bones in the rig:
dropped by the BoneMap. Body-shape blend shapes: every outfit would need the same shape keys.

**Consequences.** One animation set and one material serve every character; any generator can be swapped; the public
repo holds only clean licences. Costs: a Blender pipeline to build and pin, per-clip contact fixes for toy
proportions, a probe before each risky feature, and talking mouths waiting for voice playback. Easy to revert: the
budgets, the outline, the generator, the clip sources. Hard to revert once assets exist: the bone names and axes.

## 7. Proposed issues

### 7.1 Private art repo `xperiaroco2/prime-game-art` (after H16)

| Id | Title | Goal | Acceptance | Depends | Human |
|---|---|---|---|---|---|
| A1 | Bootstrap the art repo | CLAUDE.md, layout (T14), `.gitattributes` for LFS, `raw/` ignored, the pre-push hook, the manifest schema | Repo private; a push to main is refused by the hook; the schema validates a sample manifest | H16 | yes: create; `.claude/` edits only with you present |
| A2 | Pin Blender 5.2.2 LTS | Portable zip, SHA-256 from the official file, `BLENDER_BIN`, a doctor check | doctor passes with the pinned version and fails on another | A1, your yes to download | yes: download approval |
| A3 | Blender headless probe | Prove `blender -b` on this PC: the bundled glTF exporter's option names, one Workbench and one EEVEE frame | Two PNGs and the option list in report.json, exit 0; or a written fallback to Godot `shot` | A2 | no |
| A4 | Contract JSON from the pinned Godot | `contract/humanoid.json`: 56 names, parents, sockets, budgets | Generated by a script calling the game repo's pinned Godot; identical on rerun | A1 | no |
| A5 | check_mesh, check_rig, rename_bones | Pipeline steps 4 and 6, including the proportion rule | Pass and fail cases on a generated fixture rig; JSON report | A3, A4 | no |
| A6 | export_glb and glTF-Validator | Fixed export options; pinned validator | A fixture exports, validates with 0 errors and imports in the game's `check` with no ERROR lines | A5, your yes to download the validator | yes: download approval |
| A7 | Review sheets | render_views, render_anim_sheet, the Pillow composer | An 8-view sheet and a clip sheet of the fixture, readable on a phone | A3 | no |
| A8 | Probe: palette recolour (T12) | AI texture to the palette atlas | Before and after sheets of one trial model; face decal kept | A5, A11 | no |
| A9 | Clip bake: Quaternius Standard | Bake the free clips onto the contract rig; contact fixes; one retimed cartoony variant | Contact sheets for idle, walk, sprint, jump, kneel, punch-as-stab, death, wave; a clap whose hands meet | A5, A7, your yes to download Quaternius | yes: download approval |
| A10 | Probe: Meshy rig to contract | Convert the trial body; retarget one Meshy library clip offline | check_rig passes; 8-view and clip sheets; a written verdict on hips and spine | A5, A11 | no |
| A11 | Human: the Meshy trial evening | Section 8 | The raw folder and the log handed over | H12 | yes |
| A12 | Human: the style reference sheet | One image per family (H11) | Approved by the designer and the engineer | H1, H11 | yes |

### 7.2 Game repo `xperiaroco2/prime-game` (engine side, by the game's own task workflows)

| Id | Title | Goal | Acceptance | Depends | Human |
|---|---|---|---|---|---|
| G1 | ADR: character contract and art pipeline | Record section 6 in `docs/decisions/` | Merged with the style section filled from H1 to H11 | H1-H11, H15 | yes: both humans approve |
| G2 | Asset folder and ownership | Add the folder from H15 to the CLAUDE.md ownership list | `lint` passes; the ownership row is present | H15 | yes |
| G3 | Spike: body plus a separate part GLB | One BoneMap, both imports aligned; confirm the import option names from the `.import`; measure import time | 8-side `shot` PNGs, no ERROR lines, times logged | A6, G2 | no |
| G4 | Spike: Jolt partial ragdoll | `physical_bones_start_simulation` with the hips animated; settle and freeze at the host's position | Headless test: hips within 1 cm of the set position after settling; no jitter over 10 s | G3 | no |
| G5 | Spike: spring bones on an accessory skeleton | `SpringBoneSimulator3D` under a `BoneAttachment3D` reacts to body motion | A headless test measures tip displacement when the body moves | G3 | no |
| G6 | Shared character shader | Instance uniforms, palette, pattern and face arrays, rim, emissive; optional inverted-hull outline | 10 bodies on one material; `shot` lit, dim and deuteranopia | G1 | no |
| G7 | Engine request: per-speaker played voice level | A level per speaker from the audio this listener actually plays, for the mouth and the nod | Spec in the issue; zero for a speaker the listener cannot hear | M5 voice playback | no |
| G8 | tests/assets suite and 20-body smoke scene | The checks in pipeline step 14 | The suite runs in `verify`; the smoke scene logs draws and primitives | G3 | no |
| G9 | `check`: LFS pointer skip and licence allowlist | Skip pointer files in CI; refuse a credit without `public_repo_ok`, an allowed licence or `approval_pr` | A test for each refusal | G1 | no |
| G10 | First-person arms on the contract skeleton | T18 with z clip scale; spectating draws the target's arms from public data | Tests: no private field read; a `shot` near a wall shows no clipping | G1, G3, H10 | no |
| G11 | Lobby self-view | A dressing camera or a turntable `SubViewport` with its own world | `shot` of the lobby screen | H7, G6 | yes: the designer's look |
| G12 | Name and colour on aim | The second identity cue (UI) | The designer's spec; `shot` | H4 | yes: the designer's look |

## 8. Meshy trial evening: the engineer's checklist

You do this yourself; agents never generate on a paid service. Plan two to three hours.

1. **Make the raw folder outside both repos**, for example `D:\prime-art-raw\2026-10-meshy-trial\` (or a folder on the
   cloud drive from H14). Never inside `D:\prime-game`.
2. **Make a log** (a spreadsheet or `log.csv` in that folder) with one row per generation: date and time, plan (Pro
   monthly), task or model id, mode (text-to-3D, image-to-3D, rig, animation), the exact prompt, the image used (file
   name), model version, target polycount, topology (triangle or quad), pose, symmetry, texture on or off, credits
   before and after, the downloaded file names, and a one-line verdict.
3. **Buy Meshy Pro monthly** at meshy.ai/pricing. Check the 50% first-month discount and the total with any VAT before
   confirming. Write the price paid, the date and the renewal date in the log. Screenshot the terms page with its date
   (last updated 2026-09-19 when we read it).
4. **Keep every model private** (do not publish to the community gallery).
5. **Body, 3 to 4 attempts.** Text-to-3D (or image-to-3D from your style image), latest model, Smart Topology on,
   target 5,000 faces, triangles (one attempt with quad, to compare), **T-pose** (not A-pose: this corrects #165),
   symmetry on, texture on. A starting prompt with no game names: "stylized low-poly vinyl toy figure, big round head,
   short thick arms and legs, mitten hands with a thumb, no neck, simple smooth clothing, standing in a T-pose, arms
   straight out, palms down, symmetrical, plain colours". Note the face count Meshy reports for each.
6. **Pick the best body** and write why in the log.
7. **Auto-rig it** (humanoid). Download the rigged GLB, and also the FBX with the Mixamo naming template if offered.
8. **Animations on that body** (about 3 credits each): idle, walk, run, crouch walk, crawl, a fall, a stand up, a
   kneel, wave, clap, cheer, shrug, one dance. Download each as GLB. Note the library's id and name for each clip.
9. **A second body**, rigged, with two of the same animations, to see whether the clips carry over.
10. **Accessories**, no rig: a hat, a mask, a backpack; Smart Topology target 800 faces.
11. **Props**, no rig: a package, a crate, a knife; target 1,000 faces.
12. **Note the total credits used** and the balance left.
13. **Hand over**: tell the art session the folder path. Agents read the files from there.

What not to do:
- Do not use the free plan or keep any free-plan output (Meshy-owned, CC BY 4.0).
- Do not put any file into `D:\prime-game`, commit it, or import it into the game's Godot project.
- Do not name other games or characters, or upload their screenshots, in prompts or images.
- Do not upload unreleased key art or personal photos (Meshy may train on non-Enterprise uploads).
- Do not buy extra credit packs, a yearly plan or another service without a decision (H12).
- If you cancel later, download everything first; ownership stays yours after cancelling (Meshy help article,
  updated 2026-08-27).

## 9. Still unconfirmed

- Converting a Meshy rig to the contract skeleton by renaming plus added bones; the "hip weights 5 to 15 cm off" claim
  (one blog). Probe A10.
- Whether a Meshy library clip retargets offline from a Meshy rig onto ours, whether library motions count as owned
  output on their own, and where Meshy's motions come from (not disclosed). The library now lists 631 clips, not 591.
- Meshy Pro's monthly price (third-party only), VAT, and whether a Ukrainian card passes Stripe checkout.
- Mixamo's terms on raw redistribution (the Adobe FAQ returned 403); Fab, Rokoko and ActorCore terms (403 or snippets).
- Tripo's Studio prices (page 403); Sloyd's terms (not read); whether Sloyd and Tripo accept Ukrainian payment.
- `blender -b` rendering Workbench and EEVEE on this Windows PC; the glTF exporter option names of Blender 5.2's
  bundled add-on (read from main); the Blender 5.2.2 SHA-256 (read through a summarizer: re-copy it).
- Godot import option names (Use Named Skins, Overwrite Axis, Fix Silhouette, Unique Node): not in the API dump;
  confirm from a probe `.import` (G3).
- Separately imported part GLBs aligning with the body (G3); spring bones on an accessory skeleton under a
  `BoneAttachment3D` (G5; the default `center_from` is not documented).
- A Jolt partial ragdoll with pyramid limits (one blog; open issues 96202, 107461).
- The palette recolour method (no turnkey source), and whether one style sheet plus a palette keeps 30+ assets
  consistent.
- A custom-shader outline on faceted meshes using a smoothed normal stored in a vertex attribute (inference).
- Quaternius Pro clip names (the crawl clip; UAL2 gestures such as thumbs up); whether names changed in the v2 and v3
  updates.
- A planar mirror's cost in Forward+ (third-party sources, not measured).
- Rulesets on private Free repos (memory); GitHub Pro's price (not checked).
- Midjourney and OpenAI image terms (403, snippets); Meshy text-to-image ownership.
- Budget anchors that are not evidence: Lethal Company at about 8k triangles (a game rip) and 100 AnimationTrees at
  60 FPS (a forum post); whether a settled corpse can be frozen to skip skinning.
- Lethal Company's third-person spectator (fan wiki); CS2 and Valorant spectator viewmodels (memory).
- Trademark registers for the Fall Guys bean and the Among Us crewmate silhouettes (not checked).
- The CSM acquisition, the Luma Genie sunset and the Ready Player Me shutdown date (third-party reports).
