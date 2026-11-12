# References: Gate R's boards and the basics per domain

Anything that shipped games or real life already show (a pose, grip, hold, first-person hands, motion, prop type,
material, framing) starts from references the engineer picks. It is never invented as numbers, and never taken from
an AI image. The decision: `docs/decisions/2026-11-12-reference-first.md`; the gate's place: `docs/pipeline.md`
(Gate R).

## Making a board
1. **List the moments.** For the hands: rest, run, punch windup, punch contact, holding the crystal, hitting with it.
   For a prop: its views and states. For motion: its key poses.
2. **Fetch 6 to 10 games** that show those moments well. Shipped games first, the engineer's named references first
   (Lockdown Protocol, PEAK):

   ```
   tools/run.sh refs steam <appid> <appid> ... --board <name> [--movies 3] [--every 2]
   ```

   This puts each game's official store screenshots, frames from its trailers (one every 2 s) and contact sheets
   (`sheet_NN.jpg`, 24 tiles of 320 px, 1280 px wide) into `<raw>/refs/<name>/<appid>/`, with `refs.toml`.
   `refs.toml` stands in for `sources/<id>.toml` for a private reference. It holds the store URL, `licence_url`, each
   file's sha256, `public_repo_ok = false`, `ai_prompt_ok = false` and `ai_generated = false`.
   - Find a game's app id with `https://store.steampowered.com/api/storesearch/?term=<name>&cc=us`.
   - Run it in the background, with its log under `tools/out/`: Blender reads the trailers for minutes.
   - A game's folder that already has files is refused; use a new board name, or `--overwrite`.
3. **Add real-life references** where a game shows none: stock or anatomy references, or a photo the engineer
   sends. They go into `<raw>/refs/<name>/real/`, with a hand-written `real/refs.toml` holding a game's fields.
4. **Pick per moment.** Look at every sheet, then pick 3 to 8 frames per moment that show it clearly. Copy them into
   `<raw>/refs/<name>/picks/<moment>/` as `<appid or real>_<original name>`, so each leads back to its record.
5. **Show the board.** One private artifact page: per moment, the frames side by side with a one-line note on what
   each does (for example "thumb along the index, tip at its middle joint"), the agent's pick first. Ask through
   AskUserQuestion. The engineer picks "like this one".
6. **Write the reference card** into the asset's spec, `[reference]`:
   - `board`: the board's folder;
   - `picks`: the picked file per moment;
   - `card`: per moment, in words, what sits where and the place in frame in %.

   Numbers come after the words.
7. **Judge beside the reference.** Gates 2 and 4 put our frame beside the pick at a matching camera. The critic
   answers "what differs from the reference?" first.

References stay private:
- never committed and never shipped;
- never in an AI prompt;
- we copy the idea (a pose, grip or framing), never the art: no meshes, textures or traced images.

Steam store media are the games' official media, so fetching them falls under the standing yes for free downloads
from official sources. Any other source needs the engineer's yes.

## Boards
| Board | For | Games | State |
|---|---|---|---|
| `fp-hands` | the first-person hands' moments (art #136) | Lockdown Protocol and others with hands in view | being collected (2026-11-12) |

## The basics
Each line is something a reference shows and a build must not miss. A mistake the engineer had to point out goes
here in the same PR that fixes it.

### Hands (first person)
- **Relaxed hand.** The fingers are softly curled, each a little more than the one before it, from the index to the
  little finger. The thumb lies along the index's side, below it and nearly parallel, its tip at about the index's
  middle joint, with a small gap. It never sticks out sideways and is never tucked under the palm (the engineer's
  photo, 2026-11-12, art #136).
- **Fist.** The first phalanges are half bent and the middle ones are the fist's front. The thumb crosses the front
  of the index and middle fingers' middle phalanges, or lies down the index's side. The knuckles read as a row of
  bumps with valleys between them.
- **Wrist.** Near straight in every view-model pose; a bend shows only in motion.
- **Holding an item.** The item sits in the palm with the fingers round its back and the thumb along or over it, as
  one holds a torch. It never sits on the fingertips, and the hand never sinks into it.
- **Two hands on one item.** Each hand holds the item as one hand would, with no crossed or twisted wrists.
- **In view.** The hand's back faces the eye at rest. The hand sits low in a corner of the frame (the picked
  reference gives the % of the frame).
