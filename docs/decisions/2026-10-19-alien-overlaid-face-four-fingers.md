# The alien's overlaid face and four fingers

- Status: accepted (the engineer, 2026-10-19, in chat with the art manager, restated in art#196 comments)
- Issue: [#221](https://github.com/xperiaroco2/prime-game-art/issues/221); the stage: art#196
- Changes: the character contract for the alien (`docs/contract.md`; `contract/contract.toml` follows, see
  "Consequences"). Supersedes the face part of `2026-10-18-faces-as-morphs.md` for the alien.

## Context

`2026-10-18-faces-as-morphs.md` made faces morphs on one template head: lips, lids and mouths deform the head's own
surface, and only eyeballs, teeth, tusks, hair, crests and clothes stay separate. It needs every head to be a wrap of
one template, and a morph set for every eye and mouth design.

Two things moved on in art#196:
- **The face.** The plasticine direction was set aside on 2026-10-19
  ([comment 6265906919](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6265906919)): the target
  is the liked 2D part sheets, a smooth, soft-matte toy look. The parts kit (PR #220, the first test; PR #222, the
  second test) built the eyes and mouths as separate objects instead. The engineer likes the eyes and lips as
  separate animated objects, and his standing order is: eyes and mouths are overlaid parts, never mesh deformation
  ([handover 6267553156](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6267553156)). On the
  second test he called the eyes "super, no problems" and the mouths "super"
  ([comment 6269113887](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6269113887)).
- **The hands.** S1c's hands kept the old realistic, three-times-smoothed topology and looked crooked. He asked
  whether four fingers cause it, or whether to keep five and make four a separate task. The art manager's reading:
  the topology causes it, not the count, and the rig is the same either way. He answered on 2026-10-19: "Four
  fingers", hands rebuilt clean
  ([comment 6269178628](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6269178628)).

## Decision

1. **An overlaid face.** On the alien, eyes and mouths are rigid parts on sockets that are children of the `Head`
   bone, never morphs and never mesh deformation:
   - an eye is an eyeball plus rotating lid shells (`Eye_L`, `Eye_R`); a blink is a lid shell's rotation;
   - a mouth is a set of replacement pieces snapped onto the face (`Mouth`), one per talk shape; talking swaps the
     piece, and a flipbook shell is only a test form;
   - crests and hair stay rigid parts on their own sockets (`Crest`), as before.

   Godot imports the sockets under `BoneAttachment3D`, three.js under the Head bone (`docs/godot.md`, "The alien
   parts kit").
2. **Four fingers.** The alien has four fingers per hand: Index, Middle, Ring and Thumb. The Little finger's three
   bones stay in the skeleton and carry no weights. The 56-bone contract skeleton and every clip are unchanged.
3. **Scope.** Both decisions are for the alien. The human characters, the pack bodies and the face kit's stage-1
   heads keep the contract as written until the engineer decides otherwise.

## Consequences

- **Faces-as-morphs is superseded in part.** For the alien, its decision 1 (faces are morphs on one template head),
  decision 4's removal of the rigid face form, and its template-topology rule no longer apply: a head needs no wrap of
  a template, and no face morphs. Its decision 3 (no body-shape morphs) stands. That ADR keeps a "Superseded in part
  by" note.
- **N + M + K still holds.** Heads, eyes and mouths are separate pieces, so the parts stay interchangeable without a
  copy of each combination. Each mouth design costs a piece per talk shape (six now), not a morph set.
- **The cost moves to fitting.** Each mouth and eye piece must fit the head's rigid surface. A head that changes shape
  needs its pieces checked again, and the face has a fixed shape: no soft lips or cheeks. Mouth pieces are measured
  from the talk-shape sheets and squeezed to the face (`tools/blender/alien_mouths.py`).
- **No head morphs, so the morph budgets do not apply to the alien.** The face parts count under the
  eye-and-mouth-parts budget of `2026-10-18-character-budgets.md` (1,500 / 2,500 triangles per piece).
- **`check --kind body` would fail an unweighted Little finger.** `contract/contract.toml` has `fingers = "fail"` and
  `fingers_weighted = true`, and `tools/runner/commands/_checks.py` wants every finger bone weighted. The contract
  text still says that five fingers per hand are present and weighted. This docs task changes neither. A follow-up
  task gives the alien its own check rule (the Little chain present and unweighted, the other four weighted) before
  an alien asset is checked against the contract for the game. Done in art#223: `check --kind alien`
  (`[kinds.alien]`, `fingers_unweighted = ["Little"]`; `docs/contract.md`).
- **Gestures use four fingers.** Clips that pose the Little finger show nothing on the alien; they need no change.
  Moving to five fingers later means weighting the Little bones, with no skeleton or clip change.
- **Reversible.** Neither decision touches the skeleton, so either can be revisited cheaply.

## Links

- The engineer's words and the stage, art#196 comments:
  [6265906919](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6265906919) (plasticine set aside),
  [6267553156](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6267553156) (both listed as
  approved),
  [6269113887](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6269113887) (the second test's
  verdict, the finger question),
  [6269178628](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6269178628) ("Four fingers").
- `2026-10-18-faces-as-morphs.md` (superseded in part), `2026-10-18-character-budgets.md`,
  `2026-10-02-art-repo-foundation.md`.
- `docs/contract.md`, `docs/godot.md` ("The alien parts kit").
