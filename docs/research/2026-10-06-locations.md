# The world's look for the clay characters, and a first map (art #34, 2026-10-06)

Stage 0 of the locations track: which world look suits the plasticine characters (lumpy baked clay, bead eyes, a
potato nose, warm matte colours, on Ultimate Modular bodies), and which first map to propose. The engineer
(2026-10-06): the world can be 3D in another style, because characters and environments in different looks often
combine well. **Nothing here is decided.** The look, the map, the mood and the palette are the engineer's and the
designer's (@SwiftySinister); this page records the findings and a recommendation pending their answers.

Updated 2026-10-07 after a completeness check of the first synthesis: the recommended hybrid has since been built and
measured, the readability lead has been checked on held-out positions, and a production split by source (with Meshy
on paper) and the runner-up's missing MVP pieces have been added.

The research, the lab and the scripts are outside git in `D:/prime-art-raw/research/2026-10-06-locations/`
(`principles.md`, `styles.md`, `godot_tech.md`, `cc0_kits.md`, `objects.md`, `specs/`, `judges/`, `maps/`, `gaps/`);
the review renders in `D:/prime-art-raw/review/locations/` (one folder per prototype, `hybrid/`, `pastel_soft_extra/`,
`maps/`, `kits/`). All Godot work used Godot 4.7.2 Forward+ (Vulkan, RTX 4060) in lab projects, headless or in an
off-screen window; Blender ran in the background only. Memory is given in MiB (2^20 bytes); the lab's notes mix
decimal MB and MiB, and the figures below are converted from the bytes in each `perf.json`.

## Summary

- **Four world styles were prototyped** on one shared test scene (a room and a yard, seven cameras, the baked clay man
  and woman), each judged by two critics and revised once, then scored by three judges (readability, cohesion and
  appeal, production): a clay world (the control), a handmade stop-motion set, pastel soft modern, and a paper and card
  diorama. Nine more styles were scored on paper.
- **Recommendation (pending the engineer and the designer): the handmade stop-motion set**, built as a hybrid with
  pastel soft modern's production pipeline. It scored highest for readability (7.5 of 10) and for cohesion (7.5), the
  two lenses that answer the stage-0 question; it is the dearest of the four to build after papercraft (production
  5.0). Runner-up: pastel soft modern (production 8.0, cohesion 4.0).
- **The readability lead holds on positions nobody tuned on.** On 16 new seeded positions the light-skinned man passes
  15 of 16 in the stop-motion set (clay world 13, pastel 12, papercraft 1), and its dE00 is higher in all 32 paired
  views against each other style. The lead comes from the people rendering darker under its light, not from a calmer
  background.
- **The hybrid was built and measured** as a fifth style on the same scene: it reads like the stop-motion set (ring
  median 45.7 dE00 without the character outline, 50.9 with it, against 46.7) and stays warm without GI, with 3
  materials and one shader instead of 17, at 3.06 ms GPU in its worst view including the outline pass. Its room still
  lacks the set's craft pieces (floorboards, curtains, turned legs), and its yard is paler than the set's.
- **Three decisions matter more than the choice of world**, because all four prototypes failed them the same way: a
  2 px character outline or rim (with it the light-skinned man passes all 32 held-out views in every world); white out
  of the delivery palette (navy measured best); an anti-aliasing mode (SMAA and MSAA 4x fail almost every edge check;
  the checklist assumes none, as the game runs today).
- **First map, a proposal for the designer: Post Office No. 7 and its yard** (54 x 45 m, 1,843 m² walkable), with a
  courtyard concept as runner-up.
- **CC0:** 41 free packs downloaded (all CC0-1.0); 41 source records in `sources/` (45 with the character track's);
  `manifest-check --hashes` passes. No Meshy, no purchases, no installs. Meshy is costed on paper only: the hybrid's
  3-5 organic props would take 201-335 credits by the planning figure, against a pool of at most 215 that belongs to
  the character track.

## The principles

From references where character and world differ yet hold together (Team Fortress 2, Valorant, Fall Guys, Human Fall
Flat, Lockdown Protocol, It Takes Two, Harold Halibut, the Aardman films) and where they clash (Sonic Frontiers, Babylon's
Fall, Gang Beasts' docks), measured on our characters (light skin albedo L* 71, rendered figures at L* 44-52, clay lumps
about 1 mm per texel):

| # | Principle | Target used for the prototypes |
|---|---|---|
| P1 | Value: a compressed mid-to-light world behind players, a lighter far background | walls behind players render L* >= 65, floors >= 68; ring dL* >= 15 at 10-30 m |
| P2 | Chroma: the world below the clay; saturation reserved for gameplay | large surfaces C* <= 12 |
| P3 | Texture frequency: the clay is the noisiest surface near players | HF(ring)/HF(core) <= 0.7; texture L* std <= 4 |
| P4 | Shape: figure and ground differ in shape class | bevels >= 1 cm on reachable edges |
| P5 | Scale cues from model-scale materials, never depth of field | features >= 8 mm, DOF off in first person |
| P6 | One light over characters and world | clay-ball test within 3 L*; contact shadow >= 5 L* |
| P7 | No ink lines on the world; outlines only for gameplay states | no world outline |
| P8 | No warm-on-warm behind faces; cool shadows, never black | grey sphere shadow L* >= 15, b* -8..-1 |
| P9 | Detail above 2.4 m; floors the calmest | band HF <= 0.7 x HF above 2.4 m |

A lesson every prototype repeated: each world went paler and lost warmth when it was made readable for the
light-skinned man. A character outline or rim would let any world carry more colour.

## The prototypes

| | Clay world (v2) | Handmade stop-motion set (rev 1) | Pastel soft modern (v2) | Paper and card diorama (rev 2) |
|---|---|---|---|---|
| Bet | same material, separated by lump scale and value | material contrast, warm film-set light | no texture, high key | shape contrast, hard sun |
| Ring metric, 24 shared character regions, median / min dE00 | 38.1 / 19.5 | **46.7 / 22.3** | 33.8 / 20.8 | 33.6 / 15.9 |
| Light-skinned man standing (checklist method, no AA) | 6 of 13 at 10 m; with the outline 13 of 13 | 10 of 14 outdoor positions (greybox 4) | 11 of 17; with the outline 17 of 17 | the 25 m figure fails in every configuration |
| Light-skinned man, 16 held-out positions | 13 of 16 | **15 of 16** | 12 of 16 | 1 of 16 |
| Packages on floors | 48 of 50 | 41 of 48 | 49 of 50 (navy for white) | 32 of 50 |
| Invulnerability | white shell 0 of 4; magenta 4 of 4 | gold outline + dark line 10 of 10 | shell fails | gold + dark line fails indoors |
| Yard world C* / b* | 6.3-7.9 / +4.3..+5.9 | **12.7-15.3 / +9.6..+14.0** | 2.4-4.1 / -0.3..+1.7 | 6.4-7.8 / +4.2..+6.0 |
| Worst GPU, median (RTX 4060) | 2.85 ms | 2.92 ms (players moving) | 3.35 ms (MSAA 4x) | 2.44 ms (MSAA 4x) |
| Draw calls, worst view | 451 | 744 | 538 (683 walking) | 557 |
| Video memory | 278 MiB | 336 MiB | 502 MiB | 439 MiB |
| World materials | 9 | 17 | 3-4 | 6 |
| First map, agent-days (builder's revised estimate) | 8-14 | 11-15 (14-20 with a lightmap) | 7-10 | 19-30 |
| Judges: readability / cohesion / production | 6.0 / 4.5 / 6.0 | **7.5 / 7.5** / 5.0 | 7.0 / 4.0 / **8.0** | 5.0 / 6.5 / 4.5 |

No style has a LightmapGI bake: the only bake route in 4.7.2 is an editor run, which the lab does not allow. Every
interior is a no-GI stand-in (room ReflectionProbes with an ambient colour, lamps).

Paper-only styles, judges' scores (readability / cohesion / production): flat low-poly 6.5 / 3.5 / 8.5, cel-shaded with
outlines 6.5 / 3 / 6.5, painted wooden toys 6 / 6 / 6, plastic toys 4 / 4.5 / 6, painterly 4 / 4 / 3, gouache storybook
3.5 / 4 / 3.5, soft realistic miniature 3 / 4.5 / 3, felt 2.5 / 4 / 3, PS1 low-fi 1.5 / 1 / 6.

## The held-out readability check

The stop-motion revision tuned its light on the readability critic's 14 positions, so its lead needed a test it was
not tuned on. Sixteen standing positions were drawn with a fixed seed and written down before the first render: 6 at
3-8 m (3 indoors), 6 at 10 m and 4 at 21-23 m in the yard, each at least 1.5 m from every position the critics and the
builders used. Every style's own project was copied and rendered off-screen with both people, and scored by the
checklist method (renders with and without the figure, no AA; a pass needs dE00 >= 20, edge dL >= 20 and edge share
>= 0.8). The same script reproduced the stop-motion builder's published rows exactly on the critic's positions.

| Style | Light-skinned man | Dark-skinned woman | Median dE00, both / man | With a 2 px outline |
|---|---|---|---|---|
| Stop-motion set | 15 of 16 | 16 of 16 | 49.3 / 38.4 | 32 of 32 |
| Clay world | 13 of 16 | 16 of 16 | 35.0 / 23.9 | 32 of 32 (its real rendered outline also 32 of 32) |
| Pastel soft | 12 of 16 | 16 of 16 | 37.2 / 26.2 | 32 of 32 |
| Papercraft | 1 of 16 | 16 of 16 | 32.7 / 23.0 | 32 of 32 |

- The stop-motion set has the higher dE00 and edge contrast in every one of the 32 paired views against each other
  style (sign test p = 4.7e-10 per pair).
- Its margin for the man is larger on the held-out positions than on the tuned ones: over the clay world +5.0 to
  +13.0 dE00, over pastel +4.6 to +10.3, over papercraft +12.2 to +14.1. There is no sign of overfitting.
- The backgrounds are about equally light in the clay world, pastel and the set (L* about 75). The lead comes from the
  people: the man renders at a mean L* 37.9 under the set's light against 46.8-49.0 in the other worlds, and his face
  goes dark brown in back-lit yard views. Whether that suits the plasticine look is the designer's call.
- The outline erases the difference between worlds.
- Limits: one pose per person, standing figures only, 16 positions (pass counts of the clay world, pastel and the set
  are 1-3 views apart; the paired result is not marginal). The hybrid was built in parallel and is not in this test.

## Recommendation (pending the engineer and the designer)

**The handmade stop-motion set**, because:
- it is the pairing every clay film uses, and the only world where the people look at home (one warm light, the people
  leading by value and chroma);
- it is the most readable of the four on the same cameras, with the best body read, the only mid-value ground and the
  only invulnerability effect that passes, and the lead holds on held-out positions;
- it stays warm with no real-time GI, the minimum-spec configuration;
- its everyday-set vocabulary (post office, terraced street, kitchen) gives the next maps an identity.

Its costs: 17 materials (budget 12), generators without lightmap UV2, a "set fill" emission term a lightmap would not
reproduce, people rendered darker than in the other worlds, and a pale, whitewashed set behind players.

**Built as a hybrid, "the model-maker's set on a pastel skeleton":**
- from the stop-motion set: the light and value structure (no GI, warm per-room probe ambient, the set-fill term, a warm
  green lawn, pale verticals in the 0.3-2.2 m band, no slats behind gameplay spots), the material families as palette
  roles with one low-strength detail tap on big surfaces, hero props;
- from pastel soft modern: one world shader with a palette strip, instanced modular pieces, rounded CC0 kits (KayKit,
  Tiny Treats) through one atlas, per-piece AO, 3-6 materials, and its item kit (a dark post with an upright
  camera-facing sign, piped packages, navy instead of white);
- from the paper diorama: craft jokes kept above 2.4 m (bunting, clouds on strings, giant craft props as landmarks).

Rough cost: about 9-13 agent-days for a first map without a lightmap, 3-4 more with one (derived from the prototypes'
estimates).

**Runner-up: pastel soft modern**, if the lowest cost and risk weigh more than warmth: the only prototype already built
from shared instanced pieces (81 nodes share 25 meshes), with a measured Low preset; the coolest and greyest world
measured.

## The hybrid, built

Built on the shared test scene as a fifth style: a copy of pastel soft modern's Blender build with the stop-motion
set's revision-1 colours on its palette strip, a second strip that drives one detail tap per pixel on big surfaces (the
set's four detail maps packed into one BC7 texture), the set's light rig without GI (warm room probes that light the
characters too, unshadowed fills, the 0.14 set fill in the shader, AgX contrast 1.5, SMAA) and its invulnerability
effect, pastel soft's item kit with navy for white, and the paper diorama's bunting (lowest flag tip 2.455 m), clouds on
threads, a giant pencil, a postage-stamp landmark and cut-out hills, none of which cast shadows. The 2 px character
outline is a post-process: a characters-only depth view and one full-screen depth-compare pass, a game-side proposal
rather than part of the world.

| | Hybrid | Stop-motion set | Pastel soft |
|---|---|---|---|
| Ring metric, 24 shared regions, median / min dE00 | 50.9 / 22.3 (outline off: 45.7 / 21.5) | 46.7 / 22.3 | 33.8 / 20.8 |
| Step from the 1-3 px band to the 4-8 px band at the silhouette, median | 44.1 L* (the outline) | 2.4 L* | 1.1 L* |
| Invulnerable player, dE00 | 35.6-46.9 | 45.9-48.3 | 6.4-9.1 |
| World materials | 3 in the GLB, 4 at run time, one shader | 17, one shader | 3-4 |
| GPU median, worst view E1, players animated | 3.06 ms (2.86 + 0.20 outline pass); 2.60 without the outline | 2.92 ms | 3.35 ms (MSAA 4x) |
| Draw calls, eye views | 249-758 (214-674 without the outline) | 161-744 | 173-683 |
| Video memory | 431 MiB (339 without the outline) | 336 MiB | 502 MiB |
| Yard world C* / b*; pale share | 9.8-13.4 / +6.9..+11.5; 15-43 % | 12.7-15.3 / +9.6..+14.0; 2-17 % | 2.4-4.1 / -0.3..+1.7; 81-99 % |
| Room E1 C* / b* | 9.7 / +9.2 | 9.5 / +7.8 | 4.1 / -1.9 |

- The world alone reads like the set and far better than pastel, with no region under 20 dE00. The outline adds a dark
  step of 24-51 L* round every figure; it costs 0.43-0.48 ms per view, 35-106 draw calls and 93 MiB, more than the
  bench's +0.22 ms for a whole-scene outline, which cannot pick out characters. Everything stays inside the proposed
  minimum-spec budget. The detail tap costs 0.01-0.03 ms.
- The yard is paler than the set's because it keeps pastel soft's paved terrace and pale backdrop houses; a palette and
  layout change, not a pipeline change.
- Seen beside the set, the hybrid's room lacks the set pieces that made the set's room the stage's most convincing
  picture (floorboards, curtains, turned table legs, lolly-stick chairs): it inherited pastel soft's geometry. Bringing
  them in as shared meshes on the palette strip is unmeasured work.
- Its respawn pad (a gold ring between dark keylines, a gold chevron) breaks the objects rule that a respawn point has
  no gold and must not look like invulnerability; pastel soft's slate pad (below) follows the rule.
- Not built or not measured: the thimble and push pins, a recoloured kit atlas, new instancing, the checklist method
  (with and without each subject), a contact blob and a raised knife pose, LightmapGI.

## The runner-up's missing MVP pieces

Pastel soft modern's lineup lacked a respawn point, a round-start area, spawn dressing and landmarks; they were built in
its own pipeline (one world material, the unchanged palette strip, per-piece AO; 13 pieces, 40,730 triangles) and
measured with the checklist's mask method in its light, on the outdoor paving.
- **Respawn pad:** a 1.2 m slate field with pale footprints reads at 10 m only with a 12 cm near-black border (dE00
  15.9-16.1, edge dL 15.2-17.6, 88 x 15 px); with a 7 cm border it failed (11.1 / 10.7). It sits 36.5-37.1 dE00 from the
  invulnerability gold, but only 6.8 from the mean of a whole cyan ring, so shape (square and flat against round with a
  post) keeps them apart. It does not hurt a downed player lying on it.
- **Landmarks** (water tower 5.9 m, windmill 4.9 m, lighthouse 5.0 m, giant post box 2.7 m): distinct silhouettes at
  25 m (95-205 px tall) but weak value contrast (dE00 7.9-18.5 against their background); darker tops above 2.2 m
  helped, and the windmill (10.1) and the house-outline start gateway (7.9) stay under 15.
- **Round start and spawn dressing:** a 20 m plaza with 10 markers 2 m apart and a 4.7 m gateway; a parcel cart and a
  pallet for packages; a work bench with an empty pegboard for the knife. Looked at, not measured.

## Where each piece would come from

Per object and level piece of `objects.md` and per style (`gaps/production_split.md`, checked by
`gaps/production_split_check.py`: 18 cited source records and 34 cited pack-object pairs, 0 problems):
- **CC0 kits** carry furniture, kitchen, lamps, plants, fences and street props in the clay world, the stop-motion set,
  pastel soft and the hybrid; papercraft uses ambientCG normals only.
- **Blender, in every style:** the package, the knife, the delivery circle, the respawn pad, the house shell, the
  post-office set pieces and the landmarks.
- **The character track or Godot shaders:** the downed player, the body and the invulnerability effect.
- **Meshy, on paper only:** organic hero props and landmarks, never modular pieces or gameplay items.

| Style | Meshy props | Credits, planning figure (range) | First map, agent-days |
|---|---|---|---|
| Clay world | 8-10 | 536-670 (312-870) | 8-14 plus the bake |
| Stop-motion set | 5-7 | 335-469 (195-609) | 11-15; 14-20 with LightmapGI |
| Pastel soft | 3-5 | 201-335 (117-435) | 7-10 |
| Papercraft | 0-2 | 0-134 (0-174) | 19-30 |
| Hybrid | 3-5 (cotton-wool clouds, wool and felt landmarks) | 201-335 (117-435) | 9-13; +3-4 with LightmapGI |

Prices are from `docs/meshy.md` and match what the character track's batches were charged: 39 credits per prop for one
concept and one textured try, 67 as the planning figure (3 concepts, 2 untextured tries, since every style recolours
the mesh), 87 at most. The plan issue gives a balance of 245 with 30 reserved for #33, so at most 215, and those
credits stay with the character track. Every Meshy asset would record `ai_generated = true`, and `public_repo_ok = true`
only for paid-plan output. Meshy does not lower the agent-days: cleaning up one prop (rescaling from the normalised
1.9 m bound, recolouring, collider, LOD, manifest) is estimated at 0.2-0.3 agent-days, about the cost of a scripted
prop. No Meshy call was made.

## Godot budgets for the first map (proposed)

| Item | Minimum spec (GTX 1050 Ti class, 1080p x 0.67-0.77) | Recommended |
|---|---|---|
| GPU, worst eye-level view | <= 4 ms on an RTX 4060 (about 12 ms on a 1050 Ti, a x3.1 PassMark guess) | <= 8 ms on the recommended GPU |
| Draw calls, all passes, 10 moving players | <= 1,200 | <= 2,000 |
| Visible world triangles | <= 400k | <= 1M |
| World materials | <= 6 | <= 12 |
| World texture memory | <= 64 MiB | <= 128 MiB |
| Shadowed lights | sun PSSM 2 + <= 2 shadowed spots; no shadowed omni lights | sun PSSM 4 + <= 4 spots |
| GI | none: one ReflectionProbe per room, `reflection_count` set explicitly | optional LightmapGI; never SDFGI at minimum |
| Character outline | a post-process outline of the characters only (measured in the hybrid: 0.43-0.48 ms, up to 106 draws, 93 MiB) rather than an inverted hull (+1 ms) | same |

Measured traps: shadowed omni fills reached 1,262-1,455 draws once players moved; the default 64-slot reflection atlas
adds about 500 MiB; a command-line GLB import keeps Lossless textures (VRAM compression must be set explicitly).

## The first-map concepts (proposals for the designer)

Each concept is one layout file feeding a plan, a standard-library analysis of the game's rules (put-down and pickup
reach, running jumps, escapes, voice radius, overlooks) and a background-Blender blockout. After two adversarial checks
and a revision, all three have 0 escaping jumps, 0 dead spots, 0 jump-only pickups and every knife at least 20 m from
and out of sight of every spawn.

| | A Post office | B Courtyard | C Dacha co-op |
|---|---|---|---|
| Site / walkable | 54 x 45 m / 1,843 m² | 72 x 58 m / 2,456 m² | 76 x 48 m / 2,843 m² |
| Farthest point from the start, walking | 50.9 m, 11.3 s | 58.2 m, 12.9 s | 84.4 m, 18.8 s |
| Package to circle, mean / max | 31.1 / 62.3 m | 39.6 / 77.5 m | 43.3 / 94.9 m |
| Downed player seen by standing viewers | 93 % | 79 % | 73 % |
| Best overlook | 33 % | 39 % | 66 % |

Proposal: A, because the setting explains the task, it is the most compact, and it stages every mechanic (rooms longer
than the 8 m voice radius, muffling walls, wide doorways, levels by steps only). Design rules found: low props flush
with a wall or with 1.2 m of standing room behind them; no perch only a jumper reaches; invisible boundary colliders;
door tiers 1.4 / 2 / 2.4 m. Engine requests these maps need (game repo, not filed from here): a real level in the
content test and the bot scenarios, a respawn for a player who falls out, markers by player count, moving props.

## Licences

All 41 packs are CC0-1.0, read on each official page and in each archive (`License.txt`; ambientCG and Poly Haven by
their licence pages). Records: `sources/<id>.toml` with `licence = "CC0-1.0"`, `public_repo_ok = true`,
`ai_generated = false`. Not taken: Poly Pizza's CC-BY-3.0 models (outside the allowlist), the paid Tiny Treats sets and
MegaKit tiers. itch.io free tiers came through the free-download flow with no account or payment details. The hybrid
and the runner-up's extra pieces downloaded nothing new.

## Questions for the engineer and the designer

1. The world look: the hybrid (recommended), the stop-motion set as built, pastel soft modern, the paper diorama or
   the clay world?
2. How much handwork shows: one low-strength detail tap plus the set's craft pieces in rooms (recommended), the tap
   only (as the hybrid prototype has it), the full material library, or none? The game's `levels/CLAUDE.md` says
   "Stylized low-poly, no texture-heavy art", written before the clay characters.
3. Mood and light: a warm late afternoon (recommended; the people render darker under it, with dark faces when
   back-lit), a hazy noon, or a crisp hard sun?
4. Adopt a 2 px character outline (recommended), keep the set pale behind players, or a rim light only?
5. Jokes in the world: craft jokes above 2.4 m (recommended), hero props only, or none?
6. The first map: the post office (recommended), the courtyard, the dacha co-op, or a post office and courtyard hybrid?
7. The delivery palette: navy replaces white with a symbol per colour (recommended), charcoal, or keep white?
8. The invulnerability look: gold with a dark outer line (recommended), a magenta shell, or an iridescent effect?

For the engineer alone: the anti-aliasing mode for the game and the checklist; the LightmapGI bake route; whether any
world prop may use Meshy credits (recommended: not in stage 1).

## Next stage

Stage 1 would build a kit for the chosen look. It starts by finishing the hybrid: the set's craft pieces in the room,
lawn instead of the pale terrace, deeper backdrop tints, a recoloured kit atlas and a respawn pad without gold, then a
room and a yard corner from instanced pieces measured with both characters, with and without the outline, by the
checklist method on the critics' and held-out positions, with ten moving players. Then a modular shell kit, kit
integration, the setting's set pieces and landmarks, the gameplay item looks as proposals, a light kit with Low and
High presets, and the readability and perf checks on the full map. About 12 agent-days before the designer's review
rounds.
