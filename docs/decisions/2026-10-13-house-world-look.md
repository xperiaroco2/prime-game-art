# The House's world look: C2-white, the fine pack, base and detail layers

- Status: accepted (the direction: the engineer, 2026-10-12; the mechanisms: the art manager, #143)
- Issue: #143; the notes: #34 [6122437565](https://github.com/xperiaroco2/prime-game-art/issues/34#issuecomment-6122437565)
  (the kitchen pilot's result) and [6124431104](https://github.com/xperiaroco2/prime-game-art/issues/34#issuecomment-6124431104)
  (his decision on round 2: "everything per the recommendations"); the presets: #140 item 4.
- Lab (not committed): `D:/prime-art-raw/research/2026-10-12-kitchen-pilot/round2` (`out/handoff-step-1.md`,
  `scripts/kp_r2_build.py`).

## Context

The kitchen pilot rebuilt eight kitchen props in three directions and, in round 2, two versions of the rich one with
real material textures. The engineer chose **C2-white**: direction C ("rich realistic": wood fronts, a wood island
worktop, stone counter tops, a tiled backsplash, tinted glass uppers, warm brushed steel, chrome handles) with a
warm-white enamel fridge. Every room after the kitchen is built the same way, so the lab's choices become rules,
data and shared code here. His standing notes: the world and its items are **not plasticine** (only the characters
are); a present-day, well-made home, never old or worn; dense and detailed, easter eggs later; each room's base looks
clean on the Low preset and the small things are a separate detail layer that High and Ultra add.

The lab paid for its look in two ways the game cannot: one material per textured role split every prop's surfaces
(C2: 141-142 draw calls in the kitchen's view against C's 119), and every GLB embedded its own 1024 px texture
copies (+112 MB of texture memory for the kitchen).

## Decision

1. **Direction.** C2-white for the kitchen; for every room the same recipe: real part breakdown (bodies, fronts,
   plinths, tops, hardware as separate parts), crisp small bevels, one handle, one plinth height and one worktop
   line per room, real material textures on wood, stone and tile, flat finishes for enamel, steel, chrome and paint.
   No wear, dirt, chips or grime on anything. The measures are data: `props/library.toml` `[style]`.
2. **Materials: the fine pack.** One shared opaque material, `kit_fine-vcol`, for the world look's props, made
   the way the kit's `set` pack is (`docs/kit.md`, "Materials"). The paint is the vertex colour; its alpha picks
   one of up to 16 layers (`1 - k/16`); each layer is either textured (a grey detail and a normal map from one
   ambientCG source) or a flat finish (metallic and roughness). The layers and their values are data
   (`[fine]`): wood fronts Wood092, worktop Wood049, stone Concrete034, tile Tiles107, enamel, warm steel
   (metallic 0.6, roughness 0.42), chrome (0.8, 0.2), dark gloss, paint. Tinted glass is the one other material,
   `glass_tint` (#86918b, alpha 0.38, metallic 0.15, roughness 0.05: the round-2 values that read as glass).
   So a kitchen prop has one or two surfaces, not one per role.
3. **Shared textures, the game maps the material by name.** The GLB carries the plain white stand-in, as the kit
   does; the textures are not embedded. One texture set (`fine_d.png`: four layers' detail in RGBA;
   `fine_n0.png`, `fine_n1.png`: two layers' normal XY each) lives in one shared folder per tier, and Godot puts
   one ShaderMaterial (`godot/props/prop_fine.gdshader`, `prop_materials.gd`) on every surface named `kit_fine`.
   Every prop therefore shares the same image resources. We chose this over glTF with external images because
   our export is GLB (which embeds images), the kit already works this way, and a preset can swap the tier for
   the whole house in one place.
4. **Texture tiers.** Two tiers from the same sources: High 1024 px, Low 512 px (`[fine].tiers`). The game imports
   them VRAM-compressed with mipmaps. A third tier needs no code: a new entry in `tiers`.
5. **Classes.** `hero` [1200, 4000] triangles joins the budgets for the pieces players look at up close
   (appliances, room centres: the stove and the fridge); `room` stays [400, 1500].
6. **Layers by preset.** Every library prop is `base` or `detail` (`layer`, default by class in `[layers]`:
   `clutter` is detail, the rest base). Low shows the base layer only, and the room must read clean with it; High
   and Ultra add the detail layer. A detail prop has no collider: the presets never change what blocks a player or
   a line of sight. The game's room packages put the two layers under separate nodes (follow-up).
7. **The route per prop.** Hard-surface props (appliances, furniture, fittings) are code: the shared builders in
   `tools/blender/prop_geom.py` with a `Style`. Meshy only for organic one-offs (food, soft goods, plants) at a
   hero budget, as a recorded batch: the pilot's Meshy stove needed scale, pivot and collider work, carried its own
   2K texture and broke up at the clutter budget.

## Measured (#143)

`props-library --build --only fridge,stove,kitchen_counter,kitchen_sink,kitchen_upper --fine-compare <lab C2w GLBs>`
runs `godot/props/fine_check.gd` headless in Godot 4.7.2 (`<raw>/review/house/143/fine_check.json`):

| | the lab's C2w GLBs | the repo (fine pack) |
|---|---|---|
| surfaces of the five props (a draw call each per view) | 38 (7 to 8 per prop) | 7 (1 per prop, 2 with glass: the uppers and the stove) |
| texture memory | 69.3 MB embedded in the five GLBs (RGBA8 with mipmaps; +112 MB for the whole pilot kitchen) | 4.0 MB High (1024 px) or 1.0 MB Low (512 px), BPTC with mipmaps, for the whole house |
| textures shared | no: each GLB its own copies | yes: every `kit_fine` surface has the same three image resources |

The lab counted 141-142 draw calls for the whole kitchen view (with the walls, the dressing and the lights); the
five props' share drops from 38 surfaces to 7 per placement, so the kitchen's count falls by about 31 per set of
the five. The task props `assembly_island` (1,210 triangles, `room`) and `order_board` (734, `hero`) are on the
fine pack too, with the game surface as the board's second surface. The plain enamel fridge is 1,296 triangles,
under the brief's "about 1,500": the hero class's floor is 1,200 so it fits without padding.

## Consequences

- New rooms reuse the `[style]`, the fine pack's roles and the shared builders; a taste change is a hex, a layer
  value or a measure in `props/library.toml`, checked by `props-library`.
- The GLB alone shows the plain vertex paint (any viewer, and Godot without `prop_materials.gd`); the look needs
  the game to apply the fine material, as it already does for the kit's `set`.
- Draw calls per prop drop to one or two surfaces; texture memory is one texture set per tier for the whole
  house instead of one per prop. #143's PR measures both against the lab's C2 numbers.
- The baked light, the package sheet's ceilings and the detail layer's room nodes are separate tasks (#83, #144,
  #140).
