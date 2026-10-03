# The face kit

Faces are our own parts: eyes, brows and mouths, shared by both body types (the Head and Neck bones are identical) and
designed as one consistent set (the engineer's decision on xperiaroco2/prime-game#165). The face kit (art #21) makes
several **style families** to choose from: each one design language (line weight, curvature, depth, colours, size
against the head) with every expression the game needs, shown on four bald pack heads in two skin tones, close up and
at game distance. The engineer and the designer (@SwiftySinister) choose the style on a review page; the kit does not
choose. The generator is `tools/blender/um/facekit.py` (art #21 owns it since art #17 ported it; `docs/assembly.md`).

## The command

```
tools/run.py faces [--families f3_almond,f6_painted] [--expressions neutral,closed]
                   [--sheets close,distance,overview,strip,beards|none] [--out DIR] [--res PERCENT]
                   [--styles faces/styles.json] [--review faces/review.json] [--check]
```

Windows: `tools\run.cmd faces --out D:/prime-art-raw/review/stage1/21`. It checks `faces/styles.json`,
`faces/review.json` and the heads recipe (with the packs in the raw folder) before Blender starts; `--check` stops
there. Then `tools/blender/faces_render.py` runs in background Blender: it builds the four review heads with the
assembler (`um/assemble.py`), removes the final test's face parts, and for every family and expression puts our parts
on every head, measures them, and renders. The command prints one line per family and fails when a part is not weighted
to the Head bone alone, a decal sits closer than 0.2 mm to the skin, or the face moves in the Head bone's space during
the frame strip. A full run (7 families, 9 expressions, every sheet) takes about 6 minutes; review images go outside
git (`D:/prime-art-raw/review/...`), never into the repo.

| Output | What |
|---|---|
| `<family>_front.jpg`, `_threequarter.jpg` | Rows: the expressions; columns: the four heads in the light, then the dark skin tone |
| `<family>_hero.jpg` | The neutral face large: a man (light) and a woman (dark), front and three-quarter |
| `<family>_distance.png` | The face as a player sees it at 2, 5 and 10 m (below), enlarged with nearest neighbour |
| `overview.jpg` | Every family side by side, neutral, on the four heads (both skin tones) |
| `strip_<head>_<family>.jpg`, `clip_<head>_<family>.mp4` | Eight frames and an H.264 clip of the pack's Walk, three-quarter, fixed camera: the face stays on the head |
| `facial_hair.jpg` | The men's pack moustaches and beards on a man's and a woman's head (input for an open question, not a decision) |
| `faces_report.json` | Per family: the distinct meshes per part; per expression and head: triangles, materials, skin clearance, vertex groups; the distance pixel sizes; the strip's head-follow check |
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
| eyes | `kind` (`dot`, `ball`, `toon`, `almond`, `painted`), `shape` (`ellipse` or `almond`), `w`, `h`; dome eyes `depth` and `protrude` (the apex in front of the skin; the dome sinks into the skin at its rim); almond `top`, `bottom` (fractions of `h`), `slant`, `top_pow`, `bottom_pow`; `rest_open` (heavy lids), `lid_scale` (how far the skin lid stands off the eyeball), `iris`, `pupil` (radii), `iris_v`, `highlights` ([dx, dz, radius]: dx toward the character's left on both eyes, so the light comes from one side), `lash`, `lash_grow`, `flick`, `closed` and `happy` (`lid` or `arc`: a skin lid, or a stroke on the skin), `arc` (stroke half-width) |
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
label and its iris and brow colours, the two `skins` (the final test's light `[0.78, 0.55, 0.42]` and dark
`[0.22, 0.12, 0.065]`), the `overview_skins`, the `game_camera`, the `distances_m`, the `distance_sheet` heads and
expressions, the `strip` (action, frames, rows of head, skin and family) and the `facial_hair` parts.

**`faces/review_heads.json`**: the four heads, each bald (skin only: no eyes, brows or facial hair) with a hairstyle,
in the neutral pose, wearing the final test's outfits: `m_full` (Beach Character's full skull, Business Man's hair),
`m_open` (Punk's open-top skull with its own cap-style hair, the goatee cut off), `w_full` (Witch's full skull, ears
flattened, Animated Woman's Formal hair), `w_open` (Soldier's open-top skull with its own hair). The same hairstyles
appear in every family, so only the face changes.

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

The camera comes from the game repo (read only; `D:/prime-game` at `c43c0e1`): `client/player/player.tscn` has a
`Camera3D` with no `fov` set, so Godot's default 75 degrees vertical (`keep_aspect` keeps the height);
`content/modes/base_mode.tres` sets `eye_height_m = 1.6`; `project.godot` sets no anti-aliasing (MSAA and screen-space
AA off by default). On a 1920 x 1080 screen one metre at distance d covers 1080 / (2 d tan 37.5) pixels: 352 px at
2 m, 141 px at 5 m, 70 px at 10 m. The distance sheet renders the game's view (a perspective camera at 1.6 m looking
at the face, 1920 x 1080, no anti-aliasing), crops a 0.32 m window around the head (113, 45 and 23 px tall) and
enlarges it with nearest neighbour. An eye 3 cm wide is 10, 4 and 2 px wide at 2, 5 and 10 m.

## Checks

`faces_report.json` holds, per family, expression, head and part: triangles, materials (draw calls), the vertex
groups and the Armature modifier, and the **skin clearance**: the signed distance of every vertex and face centre from
the nearest skin along the skin's outward normal (`clearance_min_mm`, `under_skin`). Decals (`decal: true`) must stay
0.2 mm or more off the skin, or they flicker; dome eyes sink into the skin by design. The frame strip checks the face
is rigid on the head: every face vertex, in the Head bone's space, at every strip frame, against the first frame
(`face_in_head_space_max_move_mm`, 0 within float precision). `tools/tests/test_faces_*.py` cover the data checks,
the command's refusals and report checks, and one low-resolution Blender run (about 25 s, skipped without Blender or
the packs).

## Rigid parts or a face texture (the contract's two forms)

The contract (`contract/contract.toml`, slots `eyes` and `mouth`) allows two forms: **rigid** pieces on the face, or
**frames in a face texture** that a shader swaps. The kit makes the rigid form. Measured on the review heads
(`faces_report.json`; the numbers of a full run are in art #21's PR):

| | Rigid parts (the kit) | Face texture with frames |
|---|---|---|
| Triangles | Per face 230 (dots) to about 900 (almond: eyes 660, brows 128, mouth 92 to 182) on a head of 300 to 450 and a character of 6,000 to 8,500 | 0 extra; the head's own faces |
| Draw calls | One per material per visible part: 5 to 11 per face (eyes 3 to 6, brows 1, mouth 1 to 4); 1 to 3 if the export bakes the flat colours into vertex colours with one face material | 0 extra if the face is a layer of the skin material |
| Depth | Real: domes, lids that stand out, slab brows, readable in three-quarter view and with the pack's faceted light | Flat: only the painted family looks the same |
| Z-fighting | Decals are lifted about 0.4 to 1.5 mm off the skin (the measured minimum is in the report); Godot has used a reversed-Z depth buffer since 4.3 (godotengine.org, "Introducing Reverse Z"), which keeps depth error far below a millimetre at 10 m, so depth precision is not the risk; the risk is a lift too small for the faceted skin between draped vertices, which the clearance check measures | None (on the surface) |
| UVs | None needed | The pack heads have no usable UVs (every face vertex of the four review heads sits at UV (0, 0)): each head needs a face projection anchored at its eye centres (they differ by 2 to 6 mm between the body types) |
| Blink and talk | Each expression is its own set of meshes (per family 6 eyes, 5 brows, 8 mouths): the game shows one and hides the rest, or swaps the `mesh` of one `MeshInstance3D`; no bones or blend shapes (the contract forbids them for faces) | Instance uniforms pick the frame of each slot in a texture array; one material, no mesh change, matches the contract's "every piece draws the listed frames" literally |
| At distance | Small features are geometry: without anti-aliasing a 1 to 2 px eye at 10 m can shimmer as the head moves | Mipmaps average a far face into a soft blur: steadier, but the eyes vanish into the skin colour sooner |
| Mixing | Any family on any head of either body type without new UVs | A new face means a new texture layer; hair or hats over the face need no change |

**Recommendation: rigid parts**, the kit's form, for the families with depth (F1 to F5, F7), switched per expression by
visibility in the game, with the flat colours baked into one vertex-coloured material per part at export (one draw
call per part). They keep the pack's faceted, lit look, need no UV work on 21 heads, cross body types for free and
cost about 1,000 triangles per face, well inside the character budget. A face texture only pays off for the painted
family (F6), and then only with a UV projection per head and a shader; if the engineer picks F6, the same drawings can
be baked into a texture later. The contract text "eyes and mouth animate by texture frames" would change to "by
switching rigid pieces" (the contract ADR with the designer, a later wave).

## Gotchas

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
