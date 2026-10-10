# The face kit

Faces are our own parts: eyes, brows and mouths, shared by both body types (the Head and Neck bones are identical) and
designed as one consistent set (the engineer's decision on xperiaroco2/prime-game#165). The face kit (art #21) makes
several **style families** to choose from: each one design language (line weight, curvature, depth, colours, size
against the head) with every expression the game needs, shown on four bald pack heads in two skin tones, close up and
at game distance. The engineer (who acts as the designer) chooses the style on a review page; the kit does not
choose. The generator is `tools/blender/um/facekit.py` (art #21 owns it since art #17 ported it; `docs/assembly.md`).

## The command

```
tools/run.py faces [--families f3_almond,f6_painted] [--expressions neutral,closed]
                   [--sheets close,distance,overview,strip,spacing,beards|none] [--out DIR] [--res PERCENT]
                   [--styles faces/styles.json] [--review faces/review.json] [--check]
```

Windows: `tools\run.cmd faces --out D:/prime-art-raw/review/stage1/21`. It checks `faces/styles.json`,
`faces/review.json` and the heads recipe (with the packs in the raw folder) before Blender starts; `--check` stops
there. Then `tools/blender/faces_render.py` runs in background Blender: it builds the four review heads with the
assembler (`um/assemble.py`), removes the final test's face parts, gives the face skin to the Head bone alone (below),
and for every family and expression puts our parts on every head, measures them, and renders. The command prints one
line per family and fails when a part is not weighted to the Head bone alone, a decal sits closer than 0.2 mm to the
skin at rest or in the motion actions, the hair hides more than 40 % of a face part from the front, or the face moves in
the Head bone's frame during the strip (see Checks). A full run (7 families, 9 expressions, every sheet: 801 renders and
two clips) took 494 s before the review fixes added the motion measure and the spacing sheet. Review images go outside
git (`D:/prime-art-raw/review/...`), never into the repo.

The seven families of `faces/styles.json` (the choice is the engineer's):

| Family | From the final test | Eyes | Brows | Mouth |
|---|---|---|---|---|
| `f1_dots` Dots | `dots` reworked | Small dark ovals, one highlight; closed and happy eyes are strokes | Short thin strokes | A line; small open shapes |
| `f2_googly` Googly | `googly` reworked | Big white balls standing out 8.5 mm, black pupils, skin lids | Thick blocks (2 mm deep) | A line; open with a lip rim, teeth, tongue |
| `f3_almond` Almond | new | Near-human almond on a shallow eyeball, coloured iris and pupil cut by skin lids, thin lash line and flick | Thin arches | Upper and lower lips with a line |
| `f4_toon` Cartoon iris | `cartoon` reworked | Larger, taller domes, a big coloured iris, two highlights, a bold lash band and flick | Expressive, arched | Open cartoon shapes with teeth and tongue |
| `f5_lidded` Heavy-lidded | `sleepy` reworked | The almond half-closed under a heavy skin lid that stands out | Straight, low | Thin, calm lips |
| `f6_painted` Painted | new | The almond drawn flat on the skin (decals, no depth), bold lash stroke; strokes for closed and happy | Thin flat strokes | Drawn lips |
| `f7_button` Button | new | Bold glossy vertical ovals, no whites, two highlights | Short rounded blocks | Small and simple |

The final test's four styles (`facekit.EYE_STYLES`: googly, dots, sleepy, cartoon) stay in the kit unchanged for art
#17's recipes; the families above rework them as F2, F1, F5 and F4. Reading the sheets, two pairs are close: F6 is F3
drawn flat (from the front they look almost the same; three-quarter shows the difference, and F6 is the texture route),
and F7 is a bolder F1 (dark ovals without whites). In practice the choice is between about five looks.

What a run writes into `--out` (default `tools/out/faces/`):

| Output | What |
|---|---|
| `<family>_front.jpg`, `_threequarter.jpg` | Rows: the expressions; columns: the four heads in the light, then the dark skin tone |
| `<family>_hero.jpg` | The neutral face large, front and three-quarter, on the distance sheet's heads (`distance_sheet.heads`: a man light, a woman dark) |
| `<family>_distance.png` | The face as a player sees it at 2, 5 and 10 m (below), enlarged with nearest neighbour |
| `overview.jpg` | Every family side by side, neutral, on the four heads (both skin tones) |
| `spacing.jpg` | F3 and F4 neutral with the eyes and brows moved 0, 6 and 10 mm toward the midline (`eyes.inset`), the four heads front and three-quarter |
| `strip_<head>_<family>.jpg`, `clip_<head>_<family>.mp4` | Eight frames and an H.264 clip of the pack's Walk, three-quarter, fixed camera: the face stays on the head |
| `facial_hair.jpg` | The men's pack moustaches and beards on a man's and a woman's head (input for an open question, not a decision) |
| `faces_report.json` | Per family: the distinct meshes per part; per expression, head and part: triangles, materials, skin clearance at rest and in motion, the share the hair leaves visible, vertex groups; the face skin given to the Head bone per head; the distance pixel sizes; the spacing variants; the strip |
| `work/` | The single renders the sheets are cut from |

`--sheets none` builds and measures without rendering. `--res` scales every render (the tests use 10 %); the distance
sheet is only true to the game at 100.

## The data

**`faces/styles.json`**: the shared `expressions` and the `families`. A family id is `f<number>_<name>`; each has a
`name`, a one-paragraph `summary`, `eyes`, `brows`, `mouth`, `lip_tint` (the lip colour is the skin times this), the
family's fixed `colors` (white, pupil, highlight, lash, line, dark, teeth, tongue, dot; linear RGB) and optional
`expressions` overrides, merged key by key over the shared ones. Units are metres; eye shapes are normalized to the
eye's half-width `w` and half-height `h`. `tools/blender/faces_styles.py` checks everything (pure Python, every problem
at once, naming what is allowed).

| Part | Keys |
|---|---|
| eyes | `kind` (`dot`, `ball`, `toon`, `almond`, `painted`), `shape` (`ellipse` or `almond`), `w`, `h`; dome eyes `depth` and `protrude` (the apex in front of the skin; the dome sinks into the skin at its rim); almond `top`, `bottom` (fractions of `h`), `slant`, `top_pow`, `bottom_pow`; `rest_open` (heavy lids), `lid_scale` (how far the skin lid stands off the eyeball), `iris`, `pupil` (radii), `iris_v`, `highlights` ([dx, dz, radius]: dx toward the character's left on both eyes, so the light comes from one side), `lash`, `lash_grow`, `flick`, `closed` and `happy` (`lid` or `arc`: a skin lid, or a stroke on the skin), `arc` (stroke half-width), `dx` (the eye alone outward), `inset` (both eyes and their brows toward the midline, metres) |
| brows | `pts` ([x outward, z above the eye centre], inner end first), `w` (half-widths per point), `thick` (0: a flat decal; more: a slab with side walls), `lift` |
| mouth | `w` (half-width), `lips` (`none`: a line; `rim`: a lip rim round open mouths; `full`: upper and lower lips), `line`, `rim`, `lip_up`, `lip_lo`, `teeth` (height of the upper teeth band; 0 none), `tongue`, `corner` (the resting corner height), `line_color` |

| Expression key | Part | Meaning |
|---|---|---|
| `open` | eyes | Lid openness, a factor on the family's `rest_open`; 0 closes the eye (a closed lid, or a stroke) |
| `tilt` | eyes | Lid slope: positive closes the inner corner more (angry) |
| `lower` | eyes | The lower lid rises in the middle (happy squint); with `happy: arc` the eye becomes an upward stroke |
| `scale`, `pupil`, `look` | eyes | Eye size, pupil size, gaze offset [x toward the character's left, y up] |
| `raise`, `inner`, `arch` | brows | Lift the brow, the inner end, the middle |
| `w`, `mid`, `corner`, `side`, `shift` | mouth | Width factor, centre and corner heights, a one-sided tilt, a sideways shift |
| `gap`, `skew`, `round`, `teeth` | mouth | Opening height (0: closed), where it opens (-1 down, +1 up), roundness, teeth shown |

Eyes and brows take `_l` / `_r` suffixes for one side (suspicious: `open_l`, `raise_l`). The shared expressions are
`neutral`, `happy`, `talk_a`, `talk_o`, `talk_e` (three talking mouth frames), `surprised`, `angry`, `suspicious` and
`closed` (a blink: lid parts, not a scale to zero). Expressions whose values for a part are equal share one mesh: per
family 6 eye meshes, 5 brow meshes and 8 mouths (`variants` in the report).

**`faces/review.json`**: what the sheets show: `heads_recipe` (an assembler recipe, `review_heads.json`), per head a
label, its iris and brow colours and `brow_by_skin` (a darker brow on the dark skin), the two `skins` (the final test's
light `[0.78, 0.55, 0.42]` and dark `[0.22, 0.12, 0.065]`), the `overview_skins`, the `game_camera` (with Godot's
`default_window`), the `distances_m`, the `distance_sheet` heads and expressions, the `strip` (action, frames, rows of
head, skin and family), `motion` (the pack actions and frames per action in which the decals' clearance is measured),
the `spacing_sheet` (families and insets in mm) and the `facial_hair` parts. The check refuses brows with a WCAG
contrast below 3 against any skin (the review would hide the brow-led expressions); the final brow and lip colours
belong to the palette wave.

**`faces/review_heads.json`**: the four heads, each bald (skin only: no eyes, brows or facial hair) with a hairstyle,
in the neutral pose, wearing the final test's outfits: `m_full` (Beach Character's full skull, Business Man's hair),
`m_open` (Punk's open-top skull with its own cap-style hair, the goatee cut off), `w_full` (Witch's full skull, ears
flattened, Medieval's long dark brown hair), `w_open` (Soldier's open-top skull with its own hair). The same hairstyles
appear in every family, so only the face changes. `w_full` first wore the Formal hair of the final test's w1_ivy: its
fringe reaches 1.4 cm above the eye centre and hid 42 to 62 % of the high brows (F2, F4, F7), and its side lock crossed
the near eye in three-quarter view. Ray tests of the six women's full-skull hairstyles on the Witch skull: only
Medieval's leaves the brow zone and the eyes free from the front and at 35 degrees either way.

## How the parts are built

Everything is built in world space on the bald head in its rest pose, then stored in the head's local space as three
mesh objects per face (`<id>_eyes`, `_brows`, `_mouth`), each weighted 1.0 to the Head bone with an Armature modifier
on the rig: rigid on the head. Two surfaces carry the parts:

- **Dome** (dot, ball, toon and almond eyes): the front of an ellipsoid at the eye centre read from the source head's
  eye material, standing `protrude` out of the skin and sunk into it at the rim. The visible opening is a pair of
  curves; skin-coloured lids (the character's skin material, so they follow the skin tone) cover the rest of the dome
  slightly larger (`lid_scale`), the iris and pupil are cut by the same curves, and the lash line follows the upper lid.
  A closed eye is a full skin lid with the lash line low on it.
- **Drape** (brows, mouths, painted eyes, eye strokes): points projected onto the head along -Y and lifted off the skin
  along a normal blended with -Y. Brows are slabs (a top and side walls) unless `thick` is 0.

Materials are named per family (`f3_almond_white`) and per character (`m_full_f3_almond_iris`), so faces with different
colours never share one (the final test's `material()` reuses a material per style name; its four styles stay as they
were for art #17's recipes and tests).

## Game distance

The camera comes from the game repo (read only; `D:/prime-game` at `c43c0e1`, unchanged at `d9dec50`): `client/player/player.tscn` has a
`Camera3D` with no `fov` set, so Godot's default 75 degrees vertical (`keep_aspect` keeps the height);
`content/modes/base_mode.tres` sets `eye_height_m = 1.6`; `project.godot` sets no anti-aliasing (MSAA and screen-space
AA off by default). On a 1920 x 1080 screen one metre at distance d covers 1080 / (2 d tan 37.5) pixels: 352 px at
2 m, 141 px at 5 m, 70 px at 10 m. The distance sheet renders the game's view (a perspective camera at 1.6 m looking
at the face, 1920 x 1080, no anti-aliasing), crops a 0.32 m window around the head (113, 45 and 23 px tall) and
enlarges it with nearest neighbour. An eye 3 cm wide is 10, 4 and 2 px wide at 2, 5 and 10 m.

1920 x 1080 is an assumption, the fullscreen 1080p target: `project.godot` sets no window size (only
`window/stretch/mode = "canvas_items"` and `aspect = "expand"`), so Godot opens its default 1152 x 648 window and draws
3D at that size. There every length in pixels is 0.6 times as large and every pixel count about 0.36 times
(`default_window_scale` in the report): 113 / 45 / 23 px become about 68 / 27 / 14.

The sheet also counts the face's **screen pixels**: those whose colour differs from the same head rendered without face
parts (by more than 0.1 in any channel), and how many change when the face blinks (neutral against closed) or talks
(neutral against talk (a)). Measured on 2026-10-03 (`face_pixels` in the report; M full skull light /
W full skull dark):

| Family | Neutral face, px at 2 / 5 / 10 m | Blink changes | Talk changes |
|---|---|---|---|
| F1 dots | 52 / 8 / 2; 61 / 6 / 0 | 28 / 4 / 0; 27 / 4 / 0 | 24 / 2 / 2; 20 / 4 / 0 |
| F2 googly | 190 / 31 / 5; 206 / 30 / 12 | 121 / 18 / 4; 134 / 20 / 6 | 34 / 6 / 2; 26 / 6 / 0 |
| F3 almond | 139 / 22 / 8; 131 / 15 / 4 | 90 / 10 / 4; 73 / 10 / 4 | 53 / 8 / 2; 30 / 8 / 0 |
| F4 cartoon iris | 165 / 26 / 6; 189 / 28 / 6 | 138 / 23 / 6; 143 / 19 / 5 | 36 / 6 / 2; 28 / 8 / 0 |
| F5 heavy-lidded | 128 / 17 / 4; 120 / 16 / 6 | 82 / 12 / 4; 62 / 10 / 0 | 48 / 6 / 2; 30 / 8 / 0 |
| F6 painted | 133 / 22 / 6; 134 / 16 / 4 | 104 / 18 / 4; 104 / 16 / 4 | 46 / 6 / 2; 32 / 8 / 0 |
| F7 button | 93 / 12 / 6; 102 / 18 / 4 | 59 / 7 / 2; 64 / 9 / 4 | 18 / 2 / 2; 18 / 4 / 0 |

At 10 m every face is a handful of pixels and talking is nearly invisible; at 5 m blinks still read for the families
with whites (F2 to F6). Dark features on the dark skin tone fade first (F1 at 10 m: 0 px). The woman's F2 and F4 counts
grew (from 178 / 24 / 10 and 175 / 26 / 6) when the review head's new hair uncovered their brows.

## Checks

`faces_report.json` holds, per family, expression, head and part: triangles, materials (draw calls), the vertex
groups and the Armature modifier, and:

- **Skin clearance at rest**: the signed distance of every vertex and face centre from the nearest skin along the
  skin's outward normal (`clearance_min_mm`, `under_skin`). Decals (`decal: true`) must stay 0.2 mm or more off the
  skin, or they may flicker; dome eyes sink into the skin by design.
- **Skin clearance in motion** (decals): the same distance against the head skin as the actions of `motion` deform it
  (Idle, Walk, Run, Interact, Punch_Left; 8 frames each), measured in the Head bone's frame where the rigid parts do not
  move (`clearance_motion_min_mm`, `clearance_motion_where`); the same 0.2 mm limit. This is what shows whether the face
  stays on the head: the pack heads weight part of the lower face to Neck as well (up to 30 % near the chin, up to 15 %
  around the mouth), so the skin slides under a rigid mouth when the neck moves. With the pack weights 26 of 548 decal
  parts came closer than 0.2 mm (down to 0.08 mm, open mouths in Punch_Left and Run; `faces_render.py --pack-weights`
  measures it). The kit therefore gives the face skin to the Head bone alone (`facekit.rigid_face_skin`: in front of
  y = -0.07, fully from 2 cm below the mouth centre up, fading out to 5 cm below it so the jaw still blends into the
  neck): 148 to 182 vertices per review head. Since then every decal keeps its rest clearance within 0.2 mm in motion
  (the minimum is F6's 0.38 mm, at rest as in motion).
- **Hair over the face** (`visible_front`): the share of a part's points that the hair (or anything but the head
  skin) does not hide from the front camera; at least 60 %. The new w_full hair leaves at most 32 % of a part hidden
  (F2's raised brows under w_open's hair band in surprised); the old Formal hair hid up to 62 %.
- The frame strip compares every face vertex in the Head bone's frame at every strip frame with the first
  (`face_in_head_space_max_move_mm`). With parts weighted 1.0 to Head this holds by construction (it catches a part
  bound to another rig or bone); the motion clearance above is the meaningful check.

`tools/tests/test_faces_*.py` cover the data checks, the command's refusals and report checks, and one
low-resolution Blender run (close, distance and strip sheets, about 25 s, skipped without Blender or the packs).

## Eye spacing

Every family puts its eyes at the source head's eye-material centres: 88.6 mm apart on the men's review heads and
92.4 mm on the women's, about 0.51 of the face width at eye height on both (a human face is nearer 0.41). With F3's
34 mm eye the gap between the inner corners is about 1.6 eye widths (a human's is about 1), and in three-quarter view
the far eye sits near the silhouette. `eyes.inset` moves both eyes and their brows toward the midline;
`spacing.jpg` shows F3 and F4 at 0, 6 and 10 mm (76.6 / 80.4 mm and 68.6 / 72.4 mm apart). The spacing is one number
per family, tuned after the style choice; every family on the other sheets keeps inset 0, so the comparison between
families is fair.

## Rigid parts or a face texture (the contract's two forms)

The contract (`contract/contract.toml`, slots `eyes` and `mouth`) allows two forms: **rigid** pieces on the face, or
**frames in a face texture** that a shader swaps. The kit makes the rigid form. Measured on the review heads
(`faces_report.json`; the numbers of a full run are in art #21's PR):

| | Rigid parts (the kit) | Face texture with frames |
|---|---|---|
| Triangles | Per face, neutral: F1 356, F7 376, F2 428, F6 528, F4 620, F5 864, F3 880 (208 to 970 over all expressions; almond eyes 660, brows 128, mouth 92 to 182), on a bald head of 300 to 450 and a character of 6,000 to 8,500 | 0 extra; the head's own faces |
| Draw calls | One per material per visible part: 3 to 11 per face (eyes 1 to 6, brows 1, mouth 1 to 4); 3 if the export bakes the flat colours into vertex colours with one material per part | 0 extra if the face is a layer of the skin material |
| Depth | Real: domes, lids that stand out, slab brows, readable in three-quarter view and with the pack's faceted light | Flat: only the painted family looks the same |
| Z-fighting | Decals are lifted about 0.4 to 1.5 mm off the skin (measured minimum 0.38 mm, the painted eyes; every other family 0.65 mm or more), at rest and in the motion actions; Godot has used a reversed-Z depth buffer since 4.3 (godotengine.org, "Introducing Reverse Z"), which keeps depth error far below a millimetre at 10 m, so depth precision is not the risk; the risks are a lift too small for the faceted skin between draped vertices and skin that slides under a rigid part. The clearance checks measure both; the second needs every production head's face skin given to the Head bone (`rigid_face_skin`), as the pack weights part of the lower face to Neck | None (on the surface) |
| UVs | None needed | The pack heads have no usable UVs (every face vertex of the four review heads sits at UV (0, 0)): each head needs a face projection anchored at its eye centres (they differ by 2 to 6 mm between the body types) |
| Blink and talk | Each expression is its own set of meshes (per family 6 eyes, 5 brows, 8 mouths): the game shows one and hides the rest, or swaps the `mesh` of one `MeshInstance3D`; no bones or blend shapes (the contract forbids them for faces) | Instance uniforms pick the frame of each slot in a texture array; one material, no mesh change, matches the contract's "every piece draws the listed frames" literally |
| At distance | Small features are geometry: without anti-aliasing a 1 to 2 px eye at 10 m can shimmer as the head moves (the screen-pixel table above) | Mipmaps average a far face into a soft blur: steadier, but the eyes vanish into the skin colour sooner |
| Mixing | Any family on any head of either body type without new UVs | A new face means a new texture layer; hair or hats over the face need no change |

**Recommendation: rigid parts**, the kit's form, for the families with depth (F1 to F5, F7), switched per expression by
visibility in the game, with the flat colours baked into one vertex-coloured material per part at export (one draw
call per part). They keep the pack's faceted, lit look, need no UV work on 21 heads, cross body types for free and
cost about 1,000 triangles per face, well inside the character budget. A face texture only pays off for the painted
family (F6), and then only with a UV projection per head and a shader; if the engineer picks F6, the same drawings can
be baked into a texture later. The contract text "eyes and mouth animate by texture frames" would change to "by
switching rigid pieces" (the contract ADR with the engineer, a later wave).

## The clay face kit (art #42 part B)

The clay look's faces (the plasticine style the engineer chose on 2026-10-06) come from the faces lab's round E kit
(`D:/prime-art-raw/research/2026-10-05-faces/lab/clay_e/clay_face_b.py`), ported into `tools/blender/um/clayface/`:

| Module | What |
|---|---|
| `kit.py` | Pure Python: loads `faces/clay_kit.json` (eyes, brows, noses, ears, mouths, facial hair, pick weights and rules, colours, the mask) and `faces/clay_hair.json` (the hair items with their face flags); random and default picks, a recipe's `face_kit` picks (`check_picks`, `picks_for`), the hair flags (`hair_flags`, `ear_state`, `hair_brow_ok`), `DATA_SHA` |
| `mesh.py`, `eyes.py`, `brows.py`, `nose.py`, `mouth.py`, `fhair.py`, `ears.py` | The pieces, built on the head's surface (`Ctx`) |
| `face.py` | `build_face`: every piece with its keys; `Face` states (mouth, blink, look, ears); the mask UV; `game_mesh` |
| `adapter.py` | The kit on an assembled character (`assemble.build_character(face="kit")`) |
| `checks.py`, `survey.py` | The measures and the many-face check (`faces --kit-check`) |

`faces/clay_kit.json` records the lab file it was ported from (`lab_source`: path and SHA-256); a test compares the
data with the lab's tables when the raw folder is there. Change the data there, not in the modules.

**Per-hair flags.** Each hair item of `faces/clay_hair.json` carries `ears_free` (ears free where they are, ears free
when tucked) and `brow_tuck`; the
game applies them from the worn hair (and headwear) as the kit does (`kit.hair_flags`): the ears `free`, `tuck` (the
`ears_tuck` key) or `hide` (`ears_hide`, under covering hair), and the brows pressed into the forehead where a lock
covers them (full length kept; `brow_tuck` false for the hairs that must not tuck). The e5 brow pad cap was rejected
(2026-10-10): the kit keeps the e4 brow behaviour.

**Brows stay above the eyes** (art #42 round 3: w3's brows sank behind the eyes under `hair_w_formal_updo`). The tuck
lowers a brow strand only while the strand's top stays within `brows.BROW_STRAND_TOP_R` (1.2 of its radius; it was
0.5, which pushed w3's whole brow 17 mm into the lids). `checks.brow_visibility` measures per side the share of brow
vertices seen from straight in front (no head, hair, eye, lid or nose in the way; at least `BROW_SEEN_MIN` 0.25) and
the brow-to-eye clearance (the lowest front brow point over an eye above that eye's resting upper lid top). The limit
is per brow style (`kit.brow_clear_min_mm`): -3 mm for every style but the angry V, and -10.5 mm for the angry V,
whose inner ends dip in front of the lid over big eyes by design (-9.2 mm men, -9.99 mm women in the 320-face run).
w3's fixed brows read -2.46 mm, and its sunk ones -17.4 mm. The clearance compares heights only. A brow inside an
eyeball is its own failure (`checks.brow_in_white`), and a brow on a pupil is a collision. `faces --kit-check` prints
each style's lowest clearance. The cast's `build_report.json` holds it under `face_kit.brows.visibility`, and the
many-face check fails any face that misses it.

The lab measured `ears_free` on its one head; the repo's heads measure some hairs otherwise (`faces --kit-check` on
`clay_round_d`'s man, 2026-10-10), and there the repo's value wins and `lab_ears_free` keeps the lab's (the parity test
compares that). On m1 the free ear's top 5 mm (of 40) reach into `hair_m_hoodie`'s side: it tucks (0 overlaps). The
tucked ear still meets `hair_m_casual` (42 triangle pairs) and `hair_m_king_long` (16), whose hair covers the ear's
upper two thirds (casual) or all of it (king): both hide the ear (0 overlaps). A deeper `EAR_TUCK` would also clear them
(scale 0.6 to 0.7, 16 mm back, 25 mm down: 0 overlaps) but changes the tuck the women's mohawk and updo were tuned to.

**The moustache's ends.** The moustache stations keep the lip outline's top clear, not the lip's own thickness at a
raised corner beyond them: on m1 a loud brush met the smirk's raised corner in state `e` (26 mm out from the middle).
`fhair.lift_moustache` lifts the touching side's end in 0.5 mm steps (a ramp over 8 mm, at most 4 mm) until no state
touches, as `settle_goatee` lowers the goatee; `meta["moustache_lift_mm"]` records it. The moustache seat (variant a,
the nose ball on the moustache) raises the nose until it clears the moustache by `moustache_clear` (0.8 mm, unscaled):
the check's least nose clearance (0.91 mm on m1, droopy with the long nose) is that floor, not a fault; the lab's
2.75 mm came from its own head's nose and lip heights.

**The noses.** Three styles (`faces/clay_kit.json` "noses"; the engineer's three types, art #42 round 3): `bulb`
(BALL: the ball, the base nose, on every face of the cast, pick weight 1.6), `long` (BEAN: the lab's bean that sits on
the face and droops down, at scale 0.8, weight 1.0) and `pinocchio` (a closed clay capsule, its straight part 28 mm
(`capsule`; 12 mm read as a short sausage, little longer than the ball), pointing forward and about 10 degrees down, tapering 1.15 to 0.72 to a rounded tip, seated low over the mouth, weight 0.5; where its top
would touch an eye or a lid, `nose.clear_strict_nose` squashes it vertically about its lowest point). The old "Pinocchio"
of PR #102 was the pack head's own nose under the kit's ball; the bean head replaced it, so it is a real shape now.
`kit.STRICT_NOSES` (the pinocchio) must also clear the eyes and lids in `checks.collisions`, and `meta.nose.reach_mm`
records how far it reaches. PR #106's forward `cone` is gone (art #42, 2026-10-10): it treated the symptom of the
missing bean head below.

**The bean head.** The engineer approved the lab's faces, which are two layers: the lab's own head, every pack head
reshaped into an egg-like "bean" (`lab/lab_base.py` `bean_warp`, `params_r2.json`), and the clay kit's features on it.
The first ports had only the features, so every face sat on the narrow, flat pack head: pressed in, the features glued
on, the noses barely different (the pack nose dominated). `faces/clay_head.json` holds the lab's numbers and order;
`clayface/adapter.build` runs, before the face is built (so the cast and `faces --kit-check` both get it):

1. `heads.flatten_nose` and `smooth_patch` (`nose_flatten`): the pack heads carry their own nose about 17 mm out of
   the face; inside a box from the eye height + `top_dz` down to the pack's mouth centre (the recipe's `face`
   `mouth_dz`, as the lab's heads) + `bottom_dz`, every skin vertex in front of a smooth cheek surface moves back onto
   it (without it the kit's ball sat on the pack nose's tip: the "Pinocchio" of PR #102's cast);
2. `heads.bean_warp` (`bean`): every head vertex moves by `strength` toward a superellipsoid (radii `ax`, `ay`,
   `az_top`, `az_bottom`, power `power`) centred at the eye height + `centre_dz`, y `centre_y`, fading out below the
   chin over `fade_z` so the neck stays; the hair and every head extra (a beard, a hat, an earring) move with their
   `hair_k` nearest head vertices (inverse distance), so they still sit on the head (the report's `bean_head`);
   The clay head runs the bean as the lab's round B clay head did (`bean_clay`: strength 1.0, power 2.5 over
   `params_r2.json`'s 0.85 and 2.3; `clay_parts.py` `dict(P["bean"], strength=1.0, power=2.5)`), steps 2 and 4 alike;
3. `facekit.rigid_face_skin` down to `rigid_full_z` (`rigid_margin` under the kit's lowest mouth point);
4. `heads.clean_head` (`clean_head`, the lab's round B clay head, `clay_b/clay_parts.py` `build_head`): the warp alone
   is not the lab's head (step 2's IoU against the lab's own renders: the women 0.45-0.70; the warped pack heads keep
   the pack's sockets at 15 %, and the women's and m3's leave the crown and the back of the skull to the hair). The
   warped head is welded, cut `neck_dz` above the bean's bottom, united with a sphere put onto the bean, voxel
   remeshed (`voxel_m`), decimated (`tris`), snapped onto the bean within `snap_tol`, the neck crease softened; the
   pack's weights below the cut, the Head bone alone above it; one skin material (the report's `clean_head`).
   The pack's neck below the cut is not kept: `heads.neck_tube` (`neck_tube`) puts the lab cast's ONE head's neck
   into the union instead, for every body (round B's men's long neck down to z ~1.44, its `NECK_TAPER` and its
   `clay_fit.fit_inside` every top of both body types already in it; the women's pack necks end at z ~1.53 and left
   a gap over the top: w4's neck seam -17.3 mm, its Punk choker floating). `profile` is that head's radius about the
   bean centre's vertical axis per `dz` (4 mm steps from `bottom_dz` up to `top_dz`, just above the cut) and azimuth
   (7.5 degrees), unscaled, sampled once from `head_clay.blend` (`source`; the sampler
   `D:/prime-art-raw/clay-bean/lab/neck_profile.py`); a closed tube, one ring per level. Its weights still come from
   the nearest pack-head point (the report's `clean_head.neck_tube`). w3 and w4 after it: neck seams +111/+110 mm
   (into the top), see-through rays at rest 22/95 -> 2/0, poke-through 0;
5. `heads.morph_jaw` (`jaw_morph`): the lab cast's head is round C's ONE head (`clay_c/clay_head_c.py` `build_one`):
   round B's men's clean head for every body, its jaw grown out radially toward the women's clean head in `JAW_BAND`
   (`morph_jaw`: z 1.565/1.600/1.632 at the lab's x1.3 about the head pivot z 1.5873, `band_dz` -0.120/-0.093/-0.068
   from the bean centre unscaled; reach 3 cm). The repo's clean head keeps each pack head's jaw, which sat behind the
   jaw check's 3/4 line (y -0.077 against -0.08, all eight, 2026-10-10) while the lab's one head passes the same rays
   (-0.086). So the lab head's own jaw is the target: `profile` is that head's radius about the bean centre's vertical
   axis per `dz` from the bean centre (2 mm steps) and azimuth (7.5 degrees, from -Y toward +X), unscaled, sampled
   once from `head_clay.blend` (`jaw_source`: its SHA-256 and face frame; the sampler
   `D:/prime-art-raw/clay-bean/lab/jaw_profile.py`). Every vertex in the band whose radius is below the profile by
   less than `reach` moves out by the difference x the smoothstep bump, never in (the report's `jaw_morph`). w3 and w4
   after it: 3/4 at 30 mm y -0.0855/-0.086 (the lab head -0.0857/-0.0859), front -0.091 (-0.089);
6. `heads.lift_grid`, `lift_by` (`scalp_lift`) and `heads.push_out` (`push_out`): the hair's shell lifted off the
   clean head per direction from the bean centre, a hat following its hair's lift; then the hair and every head extra
   that sinks into the closed bean or lies within `clear` of it moves out along the head's normal (deeper than `reach`
   stays hidden), per welded position (the lab's 4 mm hair and hat clearance; the report's `scalp_lift`, `push_out`).

The clay library's piece keys carry the head data (`kit.DATA_SHA` for the head and the face, `kit.HEAD_SHA` and the
head for the hair and the extras that follow it).

**Whole heads and own extras.** The recipe validation refuses a head that drops part of its catalogue skull (m4's jaw)
and an extra that is not a whole item of the character's body type (m1's blue strip), and the cast build measures each
character's jaw on its geometry and fails on one cut open or covered (`um/jaw.py`): `docs/assembly.md`, "The
command".

**A recipe character's face.** A clay recipe character may carry `face_kit`: any of the picks (`kit.PICK_KEYS`:
mouth, nose, eye_size, pupil, lid, brows, ears, facial_hair, teeth, asym, loud) and `brow_rgb`; the rest are the kit's
defaults for the body type. `assemble --look clay` builds the kit's face instead of the scripted pack face
(`docs/assembly.md`, "The clay look").

### The head shader contract (what the game gets)

The character contract's file does not change for the kit (a v2 of the contract is the engineer's call). A clay
character's face arrives as:

- **The head** (`<id>_head`): the bald pack head with the kit's lids, brows, nose, mouth, teeth, ears and facial hair
  joined into it (`claylook.JOIN_INTO_HEAD`); one baked clay material: colour and normal atlas on the UV layer `bake`
  (glTF `TEXCOORD_0`; sizes in the piece's `piece.json`, `colour_px` and `normal_px`), the mouth cavity baked as clay.
  The teeth keep a glossy material of their own on the head (`claylook.GLOSSY`). A second UV layer `mask`
  (`TEXCOORD_1`) marks the parts the game may tint: brows at (1, 0), facial hair at (0, 1), the rest at (0, 0).
- **The eyes** (`<id>_eyes`): the whites and the pupils, glossy, not baked, as ONE material `fb_eye` (one surface;
  the manager's call of 2026-10-10 to keep the character within the contract's 8): its base colour is the colour
  attribute `eye_rgb` (corner domain, linear; glTF `COLOR_0`, which Godot's importer multiplies into the albedo), the
  kit's white or pupil colour per face; roughness the white's (0.17; the lab's pupil had 0.3). The part godot-check
  finds the eyes by.
- **Shape keys** (glTF morph targets): on the head `mouth_a`, `mouth_e`, `mouth_o`, `mouth_closed` (the mouth states
  over the rest mouth), `blink_half`, `blink`, `ears_tuck`, `ears_hide`; on the eyes `look_l`, `look_r`, `look_u`,
  `look_d` (yaw and pitch combine; the check proves no pupil sinks into the white at any blend). The ear keys are set
  from the hair after the bake; the game sets them again when the hair changes.
- Every face part is skinned 100 % to the Head bone; the head's face skin in front of the kit follows the Head bone
  alone (`facekit.rigid_face_skin`), fading back to the pack weights below it.

A character with an extra therefore has 8 surfaces: the head (baked clay and the glossy teeth), the eyes, hair,
accessory, top, bottom and shoes (before the one eye material, m1 of `clay_round_d` had 9).

### The many-face check: `faces --kit-check [N]`

`tools/run.sh faces --kit-check 320` builds N random faces (default 320) per body type on the heads of `--recipe`
(default `recipes/clay_round_d.json`: its first man and woman), each under a random hair item of that body type, with
the lab's seeds (500 for M, 501 for W) and its draw order, so the numbers compare with the lab's check. Per face it
measures, in the rest pose at head scale 1: collisions between pieces that must never touch (every mouth state and
blink step), brow vertices in the visible white, visible brow pokes (a brow point with no hair in front and visible
hair right behind it; the lab's e5 test, at every vertex and every triangle's centre and edge midpoints), the ears
against the hair in the item's ear state, the nose's clearance above the mouth and the moustache, noses meeting a
pupil, the brows' visibility and brow-to-eye clearance (`brow_hidden_faces`), the look's sag and triangles. It writes `kit_check.json` (with the worst faces and the formal-updo list) under
`--out` (default `tools/out/faces_kit/`) and exits non-zero on any failure (`faces.kit_problems`).

## Gotchas

- The clay kit's eyes paint the white, iris and pupil as vertex colours (`adapter.eye_material`). Workbench, in
  `MATERIAL` or `TEXTURE` colour mode (the assembler's `um/render.py`), draws none of them: the eyes come out as pale
  balls with a lid ring and at most a dark dot, which read as flat glasses with the pupils lost (PR #102's cast sheet on m1 and m2,
  art #42 point 4). Judge kit faces in Eevee (or Cycles), never from the assembler's Workbench views.
- `(1 - u * u) ** 0.8` with `u` slightly beyond 1 is a complex number in Python: clamp with `max(0, ...)` before a
  fractional power (a stroke runs to `u = 1.05`).
- Turning a head for the three-quarter view moves its face sideways (it turns about the feet, the face is 15 cm in
  front of the axis): cells are cut around each face's turned position, and faces are generated only while the heads
  face -Y (the ray casts assume it).
- Blender 5 writes video only with `image_settings.media_type = "VIDEO"` before `file_format = "FFMPEG"`.
- Blender's default font draws no underscore at label sizes: the sheets show `talk (a)`, not `talk_a`.
- The pack's beards are cut around the pack's own mouth height, about 1 to 2 cm above our mouths: with a beard the
  mouth hides behind it (see `facial_hair.jpg`); facial hair as a slot would need the beard's opening moved or the
  mouth placed by the beard.
- The pack heads carry no usable UVs (all (0, 0)): any texture on a head needs a projection first.
- The pack heads weight part of the lower face to Neck: rigid face parts need `facekit.rigid_face_skin` on the head
  (the assembler should apply it to every head that gets kit faces), or the mouth sinks toward the skin in motion.
- Measure in the Head bone's frame without its scale: the imported rig carries a world scale of 100, so
  `(arm.matrix_world @ pose_bone.matrix).inverted()` shrinks distances a hundredfold (`faces_render.head_space` drops
  the scale).
- Hairstyles with a low fringe (Formal, Witch, Animated Woman, Suit, Sci Fi on the women's full skulls) cover high or
  raised brows, and long side locks can cross the eyes in three-quarter view: a compatibility rule for the parts
  catalogue (art #19), between a hairstyle's fringe height and the face family's brow height.
