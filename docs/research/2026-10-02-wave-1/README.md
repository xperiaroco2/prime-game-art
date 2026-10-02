# Art research, wave 1 (2026-10-02)

The research notes of the art track's first wave (xperiaroco2/prime-game#165), copied as text from the art manager
session's scratchpad on 2026-10-02. They are a snapshot: later decisions on #165 override them, and the current
pipeline is `docs/pipeline.md`. `[unconfirmed]` marks a claim with no primary source opened. No images.

| File | What it is |
|---|---|
| [report.md](report.md) | The final report: recommendations, the pipeline (section 2), risks, the decisions asked, the manager's technical decisions, the ADR sketch of the character contract, proposed issues, the Meshy trial checklist |
| [sources.md](sources.md) | Every source with one line each and a licence table |
| [synthesis.md](synthesis.md) | The integrated synthesis of the six lenses, before the critic and the gap checks |
| [lens-1-art-direction.md](lens-1-art-direction.md) | Art direction: what makes low-poly party games look funny |
| [lens-2-customization.md](lens-2-customization.md) | Modular characters on one skeleton in Godot 4.7.2 |
| [lens-3-animation.md](lens-3-animation.md) | AnimationTree, falls and ragdolls, clip libraries and their licences |
| [lens-4-ai-generators.md](lens-4-ai-generators.md) | AI 3D generators other than Meshy |
| [lens-5-blender-pipeline.md](lens-5-blender-pipeline.md) | A headless Blender pipeline driven by Python |
| [lens-6-validation-budgets.md](lens-6-validation-budgets.md) | Asset checks, budgets for 10 players, Git LFS and the path into the game |
| [gap-1.md](gap-1.md) | Gap check: money, licence and platform before the Meshy trial |
| [gap-2.md](gap-2.md) | Gap check: toy proportions, game-specific clips, style consistency |
| [gap-3.md](gap-3.md) | Gap check: first person, spectating, self-view and outlines |

What changed after this wave (the engineer's answers on #165, 2026-10-02): the direction follows How to Fish's
characters with five fingers instead of the report's "squishy toy crew" with mittens; clothing comes in pieces in v1;
eyes and mouth are changeable slots; falls are animations only, no ragdoll. See `docs/pipeline.md` and
`docs/decisions/2026-10-02-art-repo-foundation.md`. The reference board that led to the direction is summarized in
`docs/research/2026-10-02-moodboard.md`.
