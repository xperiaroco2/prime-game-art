# Body types A and B for the alien (art #196)

Date: 2026-10-29. Status: accepted as a trial (the engineer's yes, below). Supersedes, for the alien, the contract's
"one neutral body in v1" and the female variants f1 and f2 (one skeleton, moved vertices).

## Context
The female alien was the shared body with a few cm moved at the chest, hips and seat (f1, f2;
`tools/blender/alien_female_geom.py`), on body A's skeleton. In the dungarees she read too close to him
(`D:/prime-art-raw/2026-10-28-alien-clothes-m1/c1/look/r28/axolotl_vs_sketch.png`): same shoulders, same height, same
limbs. Her 2D target, `2026-10-29-alien-female-body-2d-r2/d` with f's front numbers (batch
`batches/2026-10-29-alien-female-body-2d-r2.toml`), asks B over A for shoulders about 0.82, waist 0.78, hips 1.10 to
1.13, forearms, wrists and calves 0.85 and a body 5 to 8 cm shorter. Shoulders, height and limb length move joints, so
they cannot be vertex moves on A's skeleton.

The research (R1, `D:/prime-art-raw/manager/clothes/research-body-types.md`) compared one mesh with shape keys, one
mesh per body with every garment made per body, and the hybrid most games use now: a few base bodies, each garment
authored once and refit per base by a script, builds within a type as shape keys.

The engineer, 2026-10-29 about 14:20 UTC, in chat, after reading the research page: "мені підходить два тіла зараз,
просто щоб вони були обидва гарно зроблені … І вже одяг робити. Ну, твій змішаний, наче непогано звучить. Треба
спробувати." (Two bodies suit me for now, as long as both are well made ... and then make the clothes. Your mixed one
sounds fine. We have to try it.) Changing the character contract to body types was approved as a trial.

## Decision
- **Two body types, A (male) and B (female).** Both well made; no builds (shape keys within a type) yet.
- **One topology.** B is A's mesh, the same vertices in the same order, the same faces, weights and UVs, with its own
  vertex positions: a real body, not a few moved cm (`tools/blender/alien_body_b_geom.py`, the target
  `tools/blender/alien_body_types/b3.toml`, `alien_body_b.py` in Blender). Anything that works per vertex on A (the
  weld, the colour maps, the cloth fit's per-vertex difference) works on B.
- **Own rest skeletons, the same names, parents and rest orientations.** B's bones sit at B's joints (the shoulders
  in, the hip joints out a little, everything below the neck ring 0.953 times A's height); each bone keeps A's rest
  direction and roll, so a bone-local rotation means the same on both. `rest_turn_max_deg` is measured on every build
  of B (0.0 on b3) and held by the contract's `[body_types.B]` (0.5 degrees).
- **Shared clips.** Every clip is made once on A's rig and carried to B with its Root and Hips location keys scaled by
  the leg length (the `slice --own-proportions` rule: `alien_char_build.py --leg-fit`, `alien_leg_fit.py`) and the
  feet's lowest point matched per frame; the loco set (`alien_loco.py`) then edits each clip on B's own skeleton.
- **Garments fitted once per body type.** `clothes_fit.py` runs on each body type's own posed body; a garment is not
  carried from A to B by a key (the bones move, and stiff pieces such as shoes and buckles must not bend).
- **Heads later get a standard neck ring.** For now each head is welded on the body's ring (`alien_char_build.py`); B
  keeps A's ring (its x and y; only its height drops), so every head fits both bodies unchanged. A separate head mesh
  with a standard ring is a later step.
- **The contract** (`contract/contract.toml`, `docs/contract.md`, "Body types"): `[body_types.A]` and `[body_types.B]`,
  each with `height_min_m` and `rest_turn_max_deg`; `godot-check --profile alien --body-type B` holds a character to
  B's minimum height (1.62 m; the axolotl on B stands 1.694 m, under A's 1.70 m). Nothing else in the contract changes:
  the bone set, the weights, the budgets, the head top and the spring bones are the same for both.

## Consequences
- Every garment costs one fit per body type (two runs of the same script), not one sculpt per type.
- B's eyes sit lower: the axolotl on B has them at 1.478 m against the camera's 1.6 m (`contract_eye_height` warns,
  as `[kinds.alien] eyes = "warn"` allows). Whether the game's first-person camera follows the body type is a
  game-design question for the engineer and the game repo; nothing here changes it.
- Feet can slide a little more on B where a clip's foot placement depends on more than the leg length (B's hip joints
  are 8 mm further out); the loco set's own stride edits measure it per clip.
- The f1 and f2 targets stay for the record; new female work builds on B.
