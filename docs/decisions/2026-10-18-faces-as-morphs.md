# Faces as morphs on one template head

- Status: accepted (the engineer, 2026-10-18, in chat with the art manager: his yes to question 2 of the art#196
  report)
- Issue: [#200](https://github.com/xperiaroco2/prime-game-art/issues/200); the question:
  [art#196 comment](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6242847632), "For you" 2.
- Changes: the character contract (`contract/contract.toml`, `docs/contract.md`), written in 2026-10-02's ADR
  (`2026-10-02-art-repo-foundation.md`).
- Superseded in part by: [`2026-10-19-alien-overlaid-face-four-fingers.md`](2026-10-19-alien-overlaid-face-four-fingers.md)
  (the engineer, 2026-10-19, art#221). For the alien the face is overlaid rigid parts (eyeballs with lid shells,
  replacement mouth pieces) on the Head bone's sockets, never morphs, so the face part of this ADR no longer applies
  to it. The no-body-shape-morphs rule stands.

## Context

The character contract of 2026-10-02 had two forms for the `eyes` and `mouth` slots, until the style decided: frames in
a layer of a face texture array that a shader swaps, or small rigid pieces laid on the face on `Socket_Face`. It said
"eye and mouth frames are texture frames swapped at runtime, not bones or blend shapes", and `check` failed a body
that carried any shape key. The face kit (`docs/faces.md`) built the rigid form, and already added a few shape keys
to the head (mouth states, blinks, ear tucks) that the contract text did not allow.

The base alien character (art#196) changed the picture. In its 2D concepts the mouths and eyes look like a modified
version of the head itself, not overlays: the lips, lids and the frog mouth are part of the head's surface, and the
face deforms with that surface. The engineer asked whether a game can do that without a copy of every model for each
combination of parts. The art manager's answer, which he approved:
- one template head whose face variants and expressions are morphs (blend shapes, glTF morph targets);
- separate attached meshes only for what truly is separate: eyeballs, teeth, tusks, hair, crests and clothes;
- every head shape wrapped onto the same template topology, so each mouth and eye morph works on every head;
- N heads plus M mouths plus K eyes cost N + M + K pieces, not N x M x K.

## Decision

1. **Faces are morphs on one template head.** An `eyes` or `mouth` piece is a set of morphs of the head's own
   surface: the shape of the eyes, lids, mouth and lips, and every expression the slot lists (blink, talk, emotes) as
   a morph over it. The game sets their weights at runtime; no mesh changes, no bones.
2. **What stays separate.** Eyeballs, teeth and tusks stay their own meshes (rigid on `Socket_Face`, judged with
   `check --kind accessory`), and so do hair, crests, hats and clothes in their slots. The eyeballs may carry their
   own look morphs, as the face kit's do: the `eyes` slot's `part_morphs` pass under `check --slot eyes` (#202).
3. **No body-shape morphs.** Morphs are allowed only where the head bones carry the skin (`Head`, `Jaw`, `LeftEye`,
   `RightEye`: the contract's `face.morph_bones`). A morph that moves skin weighted to any other bone is still a
   body-shape morph and fails, for the old reason: every skinned outfit would have to carry the same keys or the body
   would poke through it. Settled in #202: a vertex tied between a head bone and another bone counts as on the head;
   a soft jaw or chin morph may move `Neck` skin by at most 2 mm (`face.edge_bones`, `face.edge_mm`, provisional and
   measured again on the first template head), a shift a collar fitted to the neck hides, while a 2 mm change
   anywhere else on the body still fails; the edge counts only in a key that also moves head skin and only on skin
   tied to edge bones alone (a `Chest`-`Neck` tie is body skin; #205); only vertex groups that are armature bones
   decide a vertex's bone.
4. **The face texture form and the rigid face form are gone.** Their rules (frames in a texture array, rigid eyes or
   mouths laid on the face, "never blend shapes") leave the contract.

## What changes

- `contract/contract.toml`: a `[face]` table (the rule, the morph bones, the template, the separate parts); the `eyes`
  and `mouth` slots get the `morph` form and their separate parts; `[animation].face` says expressions are morphs;
  `[budgets.limits]` keeps `blend_shapes_body = 0` for body-shape morphs and adds `face_morphs_target`, a provisional
  per-mesh warning.
- `check` measures, for each shape key, the bone that carries each vertex it moves (`check_model.py`); for a body,
  keys that move only skin on the morph bones are face morphs and pass (a warning above `face_morphs_target`), any
  other key fails. Clothing, accessories and props keep the old warning for any shape key.
- `contract --check` refuses a `face.morph_bones` entry that is not a profile bone.
- `docs/contract.md`, `docs/faces.md` follow.

## Consequences

- **Every head shape shares one template topology.** A new head is a wrap of the template (the same vertices in the
  same order), never a free mesh, or the eye and mouth morphs will not fit it. Generated or sculpted heads (Meshy, the
  base alien) need a retopology or wrap onto the template before they can carry faces.
- Each eye and mouth part is made once and works on every head: N + M + K pieces.
- The head GLB carries morph targets: the textured export already keeps them (`export --textured`, `export_morph`
  on); `godot-check` has no morph rule. The morph data counts against the character GLB's 5 MB (`glb_character_mb`;
  raised to 40 MB by the character-budgets ADR, `2026-10-18-character-budgets.md`):
  the textured export writes every morph for every vertex of its mesh (`export_try_sparse_sk` off), so the first
  template head with its full set of morphs has its file size measured before more parts are made.
- The face kit's rigid decals become the old form: its shape keys are the new form's start, its rigid mouth and eye
  meshes are not. Nothing in the game uses either yet.
- The full expression lists of the slots still wait for the style answers (H2).
