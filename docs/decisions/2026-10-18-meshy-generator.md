# Meshy is the generator: GPT Image concepts, Meshy 3D, the agents' finish

- Status: accepted (the engineer, 2026-10-18, in chat with the art manager, on art#196)
- Issue: [#203](https://github.com/xperiaroco2/prime-game-art/issues/203); the question: the three-generator showcase,
  [art#196 comment](https://github.com/xperiaroco2/prime-game-art/issues/196#issuecomment-6243620472), "For you" 1.
- Changes: `docs/pipeline.md` ("Meshy makes items and props only", 2026-10-03), the open generator choice in the
  release-quality ADR (`2026-10-17-release-quality.md`: "the method decided on one head").

## Context

Code-built aliens were judged ugly (art#196), and headless Blender cannot sculpt soft forms: scripted sculpting fails
in Blender 5.2.2. The tools research of 2026-10-17 (`D:/prime-art-raw/research/2026-10-17-art-tools/recommendation.md`)
recommended its pipeline B: concept images, then an AI 3D generator, then a finish by agents. It named Meshy 7.1
multi-image to 3D as the primary generator, Hyper3D Rodin Gen-2.5 as the challenger and Tripo for part splitting. For
concepts it named nano-banana-pro and GPT Image, both through our Meshy client.

The showcase built the alien base character from the same turnaround with all three generators; Tripo got its front
view only:
| | Meshy 7.1 | Tripo v3.1 | Rodin Gen-2.5 |
|---|---|---|---|
| Input | the three turnaround views | the front view only | the three views, run by the engineer by hand |
| Raw tris | 202,696 | 1,988,564 | 1,000,000 |
| Cost | 35 Meshy credits (API) | 60 Tripo credits (API) | the engineer's trial plan (web) |

Tripo's content filter refused the multi-view input on all four create calls (HTTP 400, code 2008, "violation of
content policy"; no credits charged), with the views on transparent and on white backgrounds alike. The likely trigger
is an unclothed full-body figure; a head-only input had passed the day before
(`D:/prime-art-raw/research/2026-10-18-alien-tripo/record.md`).

## Decision

1. **Meshy is the 3D generator.** In the engineer's words, its model "looks like our version: the texture is soft,
   nothing extra, juicy from every side". Tripo is out: its filter refuses unclothed multi-view input, which every base
   body is. Rodin was not chosen.
2. **The pipeline:**
   1. **Concepts:** GPT Image through Meshy's API (`ai_model = "gpt-image-2-5-sunburst"`, text to image or image to
      image). nano-banana-pro is set aside.
   2. **3D:** Meshy multi-image to 3D (`meshy-7.1`) from the chosen concept's turnaround views.
   3. **Finish:** agents in headless Blender by route R3 (art#196): keep the sculpt's own surface, collapse decimate
      to the budget, our clay material, bead eyes, the game skeleton and weights, face morphs on the template head
      (`2026-10-18-faces-as-morphs.md`); then `export`, `godot-check`, `frames`.
3. **The engineer buys Meshy's top subscription.** Agents never enter keys or payment details.

## Why

- Meshy kept the design closest to the turnaround from every side, the look the engineer chose.
- It is already in our client: API, batch files with `approval_ref`, credit estimates and caps, provenance in
  `generation.json`. One vendor makes both the concepts and the models, so no new client, key or account.
- It accepts base-body input. Rodin's API would need a second paid plan (Business) and a new client.

## Still open

- The release bar for the finished base character: the finish (R3 with eyes, clay, skeleton and morphs) is being
  proven on the Meshy model; the engineer judges the look.
- How generated heads are wrapped onto the template head's topology (the faces-as-morphs ADR), and how hair, ears and
  outfits are split or generated one part at a time.
- Rodin stays a challenger only if the Meshy route fails the bar; any other paid service still needs the engineer's
  yes (root `CLAUDE.md`).

## Consequences

- **Credits.** Every generation is a Meshy batch file (`docs/meshy.md`) with its `approval_ref`. Concepts cost 9
  credits per image or three-view set from text, 12 from images; a meshy-7.1 multi-image model costs 20 for the mesh,
  +5 for `geometry_resolution = "2k"`, +10 for a texture (the showcase: 35). Generation within the plan's credits runs
  under the standing permission; the spend goes into the plan issue's reports.
- **Terms.** On a paid plan the customer owns the output and Meshy keeps a licence to provide the service (terms of
  use, section 3.2). The research read that Meshy may train on data below Enterprise. When the new subscription
  starts, the batches' `plan`, `terms_url` and `licence` are rewritten from the terms page read that day, as
  `docs/meshy.md` asks when the plan changes.
- **Provenance.** Every asset made this way records `ai_generated = true`, `source.service = "meshy"`, the model
  versions (the concept model and `meshy-7.1`) and the task ids (`docs/manifest.md`). Raw generations stay in
  `D:/prime-art-raw`, never in git; `public_repo_ok` follows the paid plan's licence for finished exports, as in
  `docs/manifest.md`'s example.
- The Tripo and Rodin files of the showcase stay in the raw folder as records; no client for either is added.
