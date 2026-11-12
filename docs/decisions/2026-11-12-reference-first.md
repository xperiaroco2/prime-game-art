# Reference first: what shipped games and real life already show is copied from a reference, not invented

- Date: 2026-11-12
- Status: accepted (the engineer, 2026-11-12, in chat with the session building the first-person hand, art #136:
  "it needs fixing somewhere ... so in future we do it right", then "I give my yes to all of it" for the
  pipeline proposed here; recorded on art #136).
- Applies from now on to anything in the 3D work that shipped games or real life already show (an asset type, a
  pose, grip, hold, animation, camera framing or view-model moment), on every track (characters, clothes, props,
  locations, hands). It comes before Gate 0 of the asset
  gates (`2026-10-31-asset-pipeline-gates.md`) and does not replace them, the release-quality ADR or the trust model.

## Context

3D is the hardest part of the game for AI to make. The engineer plans much more of it. The first-person hands
(art #136, xperiaroco2/prime-game#1587) showed the pattern that makes it slow and expensive:
- **v1 (art #378)** was judged "full shit": a twisted wrist, the crystal sunk into the hands, a hold no person would
  use. **t10** was still horrible.
- **The detailed hand (art #379)** got the shape right and the fist after a route change. Its resting thumb then stuck
  out sideways like a separate sausage, and the engineer had to send a photo of his own relaxed hand. Any shipped
  first-person game, and any real hand, shows that the thumb lies along the index finger.

The engineer's words: first-person hands, relaxed, in a fist, holding an item, exist in a great many games; "this is
the base"; we do not invent anything new. Lockdown Protocol even shows an item held in the hand. So why invent it,
and why does he have to point at basic mistakes?

The root causes:
1. **Poses were invented as numbers.** Joint angles (`Thumb = [6, 14, 10]`, a crystal hold solved against a
   surface) were typed or searched for with no picture of the result in a real game or a real hand.
2. **The targets were AI images.** gpt-image frames were treated as truth for a pose and a hold, although the image
   model invents holds and hides the arm in a sleeve. Fitting to them made the punch's refit worse (skin overlap 0.19
   against 0.37).
3. **The checks measured the easy things.** Tears, silhouette overlap with a concept, `problems []`, GPU ms all
   passed while the hand looked wrong. None asked whether it looks like a hand in a game players know.
4. **The critics compared against the wrong things**: the concept and earlier steps, never a real reference. Basic
   anatomy and common sense were left for the engineer to catch.
5. **Each mistake cost a full round**: a rebuild, a Godot run, a page, his look. That repeated, instead of a few
   minutes spent on references first.

## Decision

**Reference first.** Anything that shipped games or real life already show starts from references the engineer
picks, never from numbers or an AI image. That covers:
- a pose, a grip, holding or swinging an item;
- first-person hands, a walk or run, a door;
- a prop type, a material, a framing.

1. **The reference board (Gate R, before Gate 0).** For each moment of the thing (for the hands: rest, run, punch
   windup and contact, holding the crystal, hitting with it), the agent collects 3 to 8 references:
   - frames from shipped games: official store screenshots and trailers through `refs` (`docs/references.md`), and
     press kits;
   - real photos and video of the action (stock and anatomy reference sites, a photo the engineer sends).

   One private page shows each moment's references side by side, with a one-line note on what each does and the
   agent's pick first. The engineer picks "like this one" per moment. A moment with an obvious answer still gets its
   reference; the agent then decides and says so.
2. **The reference card.** From the picked reference the agent writes what sits where, in words first:
   - "the thumb under the index, its tip at the index's middle joint, a small gap";
   - "the wrist straight; the item in the palm, the fingers round its back";
   - the hand's place in the frame in %.

   Numbers come after. The card goes into the asset's spec (`<asset>_dims.toml`, a `[reference]` section: the board,
   the picked file, the card). Every brief, build and critic cites it.
3. **The basics list.** Before a build, the agent writes the domain's basics into `docs/references.md` (for a hand:
   the relaxed thumb lies along the index, a fist's thumb crosses the front, a held item sits in the palm and not on
   the fingertips, the wrist stays near straight). A mistake the engineer has to point out goes into that list in the
   same PR that fixes it. The list grows, and the next build starts from it.
4. **Judged beside the reference.** Gate 2 and Gate 4 put our frame beside the picked reference at a matching camera
   and framing. A fresh critic gets the reference and the card, not only the concept, and answers one question first:
   "what differs from the reference?". A difference that our style does not explain is a defect. The engineer sees a
   step only after that comparison has passed.
5. **AI images are concepts, not truth.** gpt-image can set the look and style (Gate 0). A pose, hold, motion or
   framing comes from a shipped game or a real reference. A target frame for a fit is a reference frame, or one
   checked against a reference.
6. **Metrics are necessary, not sufficient.** `problems []`, a high overlap, no tears: none of these means "looks
   right". A handoff reports the comparison with the reference beside its numbers.
7. **References stay private.** Frames from games live in `<raw>/refs/<board>/` with `refs.toml`: the source URL, the
   game, the date and the sha256 of each file.
   - They are never committed and never shipped.
   - They are never put in an AI prompt (the AI rules in `CLAUDE.md`).
   - We copy the idea (a pose, a grip, a framing), never the art: no meshes, textures or traced images.
   - Store screenshots and trailers are the games' official media on their store pages. The engineer's yes of
     2026-11-12 ("I give my yes to all of it", for this pipeline, whose proposal named Steam pages and trailers)
     covers fetching them for private reference. Any other source still needs his yes, and he can narrow this one.

## Consequences

- One reference page per moment comes before any build: a look earlier than the asset gates' three
  (`2026-10-31-asset-pipeline-gates.md`, amended to say so). The engineer's picks replace the rounds in which he
  pointed out basics; a pick is one click, a round is a rebuild.
- `refs` (`tools/run.py refs steam <appid>... --board <name>`) fetches a game's store screenshots and trailer frames
  into a board, with `refs.toml` and a contact sheet per game. It needs nothing new to install: Blender's own decoder
  reads the trailers.
- `docs/references.md` holds the boards made so far, their picks, and the basics list per domain.
- Every spec gets a `[reference]` section, and critics get the reference. Briefs cite it (`docs/agents.md`, "Briefs
  under the asset gates").
- The first board is the first-person hands' (art #136): every moment, Lockdown Protocol first. The crystal hold is
  rebuilt from its pick.
