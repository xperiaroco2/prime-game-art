# The vault's plush alien: handoff

The easter egg the ship's vault holds (xperiaroco2/prime-game#1040; art#297). It does nothing: players carry, hug
and throw it. Out of scope here: the vault room (it comes with the diamond hull) and any behaviour.

## Files

| File | What |
|---|---|
| `export/vault_plush.glb` | The mesh: one surface, 3,999 triangles, 0.300 m tall, front +Z, origin on the floor under its middle. Its material is a plain PBR fallback (albedo and normal 1024 px, roughness 1, metallic 0) |
| `export/vault_plush_mask.png` | The plush shader's mask, 1024 px, linear (import it without sRGB): R the orange fur, G the brown velour, B the glossy eyes |
| `export/plush.gdshader` | The surface: Burley diffuse, roughness 1 on the fabric, a fine pile normal in model space, the sheen as a fabric-tinted rim, glossy eyes |
| `export/plush_shell.gdshader` | One shell of the pile: the mesh drawn again, pushed out along its normals, cut into tapering strands; nothing past 6 m |
| `export/plush.gd` | `apply(root, albedo, normal, mask, pile, shells)`: puts the surface material with 12 shells chained as next passes on every mesh under `root`; `pile_texture()` makes the pile's noise normal map (await its `changed`). It preloads the two shaders from its own folder |
| `source/vault_plush.blend` | The game mesh with its three maps packed |

The albedo and normal maps are inside the GLB; the material script takes them from the imported material (or from
extracted files) together with the mask.

## In the game

- Size: real size, no scaling; carried in one hand.
- Look: under the recommended look (`godot/showroom/look_presets.json`, AgX 0.9) its orange, velour and eyes match the
  concept's medians within a few steps (`report.json`). The fur shells cost 0.14 ms of GPU in the hand view
  (0.58 to 0.72 ms, 1280x720, this PC); with the surface material alone it still reads as plush at a distance.
- Collision: none made here; a capsule or a box of 0.21 x 0.30 x 0.30 m fits it.
- The smile lies in the seam under the muzzle: seen from below or level it reads in full, from above mostly its
  corners (the engineer kept it so, 2026-10-23).

## Provenance

`manifest.toml`: the approved concept, the OpenAI turnaround (batch `2026-10-22-vault-plush-turn`), the Meshy model
(batch `2026-10-22-vault-plush-3d-2`), our own cleanup, mouth, paint and bake. AI generated on paid plans, outputs
owned; public repo ok.
