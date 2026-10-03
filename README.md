# prime-game-art

The private art repository of [prime-game](https://github.com/xperiaroco2/prime-game): character, clothing,
accessory, prop and animation sources, the headless Blender pipeline that checks them, and the provenance manifests
that say where each asset came from and under which licence. Approved assets enter the public game repo through a
game-repo pull request under the character contract; nothing here is shipped directly.

- How agents work here: [CLAUDE.md](CLAUDE.md)
- The pipeline from a raw generation to an approved asset: [docs/pipeline.md](docs/pipeline.md)
- The asset manifest and source records: [docs/manifest.md](docs/manifest.md)
- The character route: [docs/assembly.md](docs/assembly.md), [docs/catalogue.md](docs/catalogue.md),
  [docs/faces.md](docs/faces.md), [docs/animations.md](docs/animations.md), [docs/godot.md](docs/godot.md)
- Decisions: [docs/decisions/](docs/decisions/); research: [docs/research/](docs/research/)
- Plan and reports: [xperiaroco2/prime-game#165](https://github.com/xperiaroco2/prime-game/issues/165) and the stage plan
  issues here (stage 1: [#16](https://github.com/xperiaroco2/prime-game-art/issues/16))

## Quick start (Windows, PowerShell)

```powershell
cd D:\prime-game-art
git lfs install --skip-repo   # once per PC, if doctor asks for it
tools\run.cmd doctor          # checks the tools and sets core.hooksPath to tools/githooks
tools\run.cmd verify          # the tests and the manifest check
```

`doctor` needs Python 3.11 or newer (`PYTHON_BIN`, else the `py` launcher), git with Git LFS, Blender 5.2.2 LTS at
`D:/tools/blender/5.2.2` (or `BLENDER_BIN`), Khronos glTF-Validator at `D:/tools/gltf-validator/2.0.0-dev.3.10` (or
`GLTF_VALIDATOR_BIN`), the game's Godot 4.7.2 console exe in `GODOT_BIN`, the raw folder `D:/prime-art-raw` and its
backup `%OneDrive%\prime-art-raw`, and the GitHub CLI logged in. It reports whether `MESHY_API_KEY` is set without ever
printing it. `tools\run.cmd pins` lists the pinned versions and paths.

Raw generations never enter git, and review images are shown through private pages, not committed. The art manager
merges PRs into `main` after the gate; the engineer decides taste, money and large or hard-to-reverse questions
([the trust model](docs/decisions/2026-10-03-trust-model.md)).
