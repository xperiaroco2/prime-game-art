# Character budgets for quality, measured

- Status: accepted (the engineer, 2026-10-18, in chat on art#196: quality over low-end hardware); the numbers below
  are the art manager's recommendation measured with `tools/run.py bench`
- Issue: [#212](https://github.com/xperiaroco2/prime-game-art/issues/212)
- Changes: the character contract's budgets (`contract/contract.toml`, `docs/contract.md`), sketched in section 7 of
  `2026-10-02-art-repo-foundation.md`

## Context

The contract's character budgets were never measured. They were the foundation ADR sketch's starting guess, sized
for the low-poly pack characters: the assembled character 8,000 triangles target and 12,000 cap, the body 6,000 /
8,000, textures 1,024 px, a GLB cap of 5 MB. That guess forced the alien base from its 200k Meshy sculpt down to 11.7k
triangles: the decimate left a pole on the belly and lost much of the face's detail in the morph transfer (art#196,
comment 6248743378), and the 1,024 cap softened the eyes and lips the 2,048 bake had (finish step 1b's handoff).

The engineer (2026-10-18): "Quality matters far more to me than whether the game runs on someone's ancient laptop."
The target hardware is a mid-range gaming PC (RTX 3060/4060 class); the Low preset is no longer the bar for character
detail.

## Decision

For the assembled character, about 20 skinned bodies on screen (10 players plus corpses):

| What | Before | Now |
|---|---|---|
| Character LOD0 triangles (target / cap) | 8,000 / 12,000 | 40,000 / 60,000 (vertices 30,000 / 45,000) |
| Body, head included | 6,000 / 8,000 | 22,000 / 30,000 (vertices 16,000 / 24,000) |
| Template head (new; the only mesh with face morphs) | | 12,000 / 15,000 (vertices 7,000 / 9,000) |
| Clothing piece | 1,200 / 2,000 | 3,000 / 5,000 |
| Hair or hat | 800 / 1,200 | 3,000 / 4,500 |
| Accessory, eye and mouth parts | 800 / 1,200 | 1,500 / 2,500 |
| LOD1 / LOD2 / LOD3 (optional) | | 15,000 / 6,000 / 2,000 from about 4 / 10 / 25 m |
| Character textures | 1,024 | 2,048, at most 3 maps (base colour, normal, ORM or roughness), VRAM Compressed; 1,024 for LODs and small parts |
| GLB cap, character / accessory | 5 MB / 1 MB | 40 MB / 4 MB |
| Face morphs | 64 target | unchanged: 52 to 64, on the separate head mesh only |
| Surfaces, bones per vertex | 6 / 8, 4 | unchanged |

The pieces add up: the body plus one piece per slot at their targets (22,000 + 3 x 3,000 + 3,000 + 4 x 1,500) is the
character's 40,000, at their caps 59,500. The piece budgets are the old ones times 2 to 4, chosen so they add up;
the first real pieces revise them. Godot's automatic import LODs stay on. Hand-made LOD meshes under visibility
ranges and a low-poly shadow caster (`SHADOWS_ONLY`, the drawn meshes' shadows off) are optional, for when a profile
shows their cost: in the measured scene (a small meeting ring) neither saved anything on top of the automatic LODs.

## The measurement

`tools/run.py bench --proxy-from D:/prime-art-raw/review/char/alien-base-3d/finish1b/alien_base.blend --copies 10,20
--out D:/prime-art-raw/review/char/bench-212` (docs/godot.md, "Bench"). The stand-in: finish step 1b's alien base
subdivided and decimated to 40,000 triangles (body 20,618, head 17,660 with 8,922 vertices, eyes 1,722), a 7,000
triangle shadow copy, the 2,048 bakes, and 0, 32 or 64 head morphs (GLB 7.5, 18.6 and 29.6 MB). Its body with
the head (20,618 + 17,660 = 38,278 triangles) is over the new body cap (30,000), and its head (17,660) over the head
cap (15,000; its 8,922 vertices just inside the 9,000), so the numbers below are conservative for a character within
the budgets. N copies in a meeting ring play Idle with every morph weighted, seen from behind the ring at eye height;
a directional light with 4 shadow splits and a shadowed omni lamp at the centre; AgX, SSAO, sky; 1920x1080, an off-screen window, vsync off; the median
of 300 frames. Machine: NVIDIA GeForce RTX 4060, Vulkan Forward+, Godot 4.7.2. The empty stage costs 0.67 ms of GPU;
"chars" is each row minus it. The CPU ms is the viewport's render time only
(`viewport_get_measured_render_time_cpu`): the animation players and skeleton updates are not in it. `bench` records
them since (process ms, `Performance.TIME_PROCESS`, and whole frame ms); this table predates those fields and was not
re-measured. The ring is small: its far side is 7.1 m from the camera at 10 bodies and 10.9 m at 20, so the
"hand LOD2 from 10 m" column switches no body at 10 and 5 of 20 at 20.

| Characters' GPU ms (CPU ms) | LOD auto, full shadows | LOD auto, shadow proxy | LOD0 only, full shadows | LOD0 only, shadow proxy | hand LOD2 from 10 m |
|---|---|---|---|---|---|
| 10 x 0 morphs | 0.29 (0.17) | 0.27 (0.14) | 0.66 (0.16) | 0.38 (0.13) | 0.32 (0.20) |
| 10 x 32 morphs | 0.36 (0.17) | 0.33 (0.14) | 0.72 (0.16) | 0.46 (0.13) | 0.38 (0.19) |
| 10 x 64 morphs | 0.42 (0.17) | 0.40 (0.14) | 0.79 (0.16) | 0.50 (0.13) | 0.45 (0.20) |
| 20 x 0 morphs | 0.41 (0.26) | 0.37 (0.21) | 1.19 (0.25) | 0.66 (0.21) | 0.44 (0.29) |
| 20 x 32 morphs | 0.52 (0.26) | 0.49 (0.21) | 1.32 (0.24) | 0.77 (0.20) | 0.55 (0.30) |
| 20 x 64 morphs | 0.64 (0.26) | 0.61 (0.21) | 1.44 (0.24) | 0.89 (0.20) | 0.68 (0.28) |

20 bodies drew 876,002 primitives in 307 draw calls with the automatic LODs and full shadows, 4,192,688 at LOD0 only
(the shadow passes draw every caster about four more times). Memory: each copy adds 0.54 MB of buffers (its skinned
vertices), the same with 0, 32 or 64 morphs; the mesh data is loaded once per unique mesh: 1.7 MB without morphs,
7.6 MB with 32, 13.4 MB with 64, so 64 morphs on an 8,900-vertex head cost 11.7 MB per unique head (about 20 bytes
per head vertex per morph; Godot keeps morphs dense). The two 2,048 textures take 8.0 MB VRAM Compressed (42.7 MB
uncompressed, as a headless import leaves them).

**Verdict:** the 40k budget fits with a wide margin. 20 bodies with 64 morphs cost 0.64 ms of GPU with the automatic
LODs and 1.44 ms in the worst case (every body at LOD0, full shadows), against the 4 ms the brief allowed; the 60k cap
scales to about 2.2 ms in that worst case. The render CPU stays at 0.2 to 0.3 ms (animation and skeleton time not
measured). Nothing here asks for lower numbers.

What the measurement confirmed and did not:
- The automatic LODs halve the characters' GPU time (1.44 to 0.64 ms at 20 bodies) and take the shadow passes down
  with them; with them on, the shadow proxy saved 0.03 ms. With LOD0 only it saved 0.55 ms.
- The hand-made LOD2 beyond 10 m saved nothing on top of the automatic LODs here, which says little: no body was
  beyond 10 m at 10 copies and only 5 of the 20 at 20; a spread-out crowd (3 to 30 m) was not measured. That the
  automatic LODs keep skinning and morphs over every LOD0 vertex is Godot's design; the bench does not isolate the
  skinning cost, and at well under 1 ms of GPU it is not a bottleneck there; the CPU side of animation was not
  measured.
- Measured at 1080p, not 1440p: the characters' vertex work does not grow with the resolution; the scene's pixel
  work does.

## Consequences

- The alien base can be rebuilt from its sculpt at 30 to 40k triangles with the 2,048 bakes (art#196's next step), and
  its head kept as its own mesh for the face morphs.
- `export --textured` and `godot-check --textured` read `texture_character_px` (now 2,048) from the contract;
  `check` reads every budget from it; the contract tests read them too.
- The GLB cap is not checked by any command yet (it never was); a dense 64-morph head of 9,000 vertices alone is
  about 22 MB in the GLB.
- The game repo's copy of the contract (xperiaroco2/prime-game) is synced later through a game-repo task; nothing in
  the game changes here.
- `bench` is the tool to re-measure: on the first real 40k character, at 1440p, and on a weaker GPU when one is
  available.
