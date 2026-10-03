# The parts catalogue

Every part of Quaternius' **Ultimate Modular Men and Women** packs (CC0; `sources/quaternius_ultimate_modular_*.toml`)
inventoried, every head split into what a customization menu can offer, and compatibility measured pair by pair with
the assembler's own library (`tools/blender/um/`, `docs/assembly.md`). The data is `catalogue/ultimate_modular.json`;
it is the base of the game menu's compatibility rules (a later game task) and of our parts production. Art #19 built it
on the final character test's `catalog.py` and `fitcheck.py`
(`D:/prime-art-raw/research/2026-10-03-art-research/final-character-test/`).

## The command

```
tools/run.py catalogue [--check] [--renders sheets,matrices,confirm] [--out DIR] [--res PERCENT]
```

| Option | What it does |
|---|---|
| (none) | Regenerates `catalogue/ultimate_modular.json` in headless Blender (about 1.5 minutes) and prints its summary |
| `--check` | Regenerates into `tools/out/catalogue/check.json` and fails when it differs from the committed file: the determinism and drift check (`tools/tests/test_catalogue_blender.py` runs it) |
| `--renders` | Also renders into `--out` (default `tools/out/catalogue/`): `sheets/`, `matrices/`, `confirm/` (below; about 10 more minutes for all three, most of it the confirmation renders) |
| `--res` | Render size in percent (default 100) |

The packs are read from the raw folder (`ART_RAW_DIR`, default `D:/prime-art-raw`, `refs/Ultimate_Modular_*_Pack/`).
The file is written with sorted keys and every number rounded (metres to 4 decimals, millimetres to 1), so two runs
give identical bytes; review pictures go outside git (`D:/prime-art-raw/review/...`), never into the repo.

Code: `tools/blender/catalogue.py` (the entry script, the file section, the summary), `catalogue_parts.py` (loading,
the parts inventory and seam heights), `catalogue_heads.py` (heads split into items), `catalogue_rules.py` (the
compatibility measurements and verdicts), `catalogue_render.py` (the pictures); the runner's
`tools/runner/commands/catalogue.py` and `_catalogue.py` (the schema check, the summary, the comparison).

## How many characters

The men's pack folder holds 11 GLB files and the women's 10: **21 characters**. The women's two "Animated Woman" files
are different characters, not duplicates or variants: `Animated Woman.glb` is the Casual character (`Casual_Head`,
`_Body`, `_Legs`, `_Feet`) and `Animated Woman-nIItLV9nxS.glb` the Formal one (`Formad_Head`, `Formal_Body`, `_Legs`,
`_Feet`); none of their mesh positions are equal. They share the skeleton (equal inverse bind matrices) and the 24
animations byte for byte, as every women's file does; all men's files likewise share one animation set (which differs
from the women's). Pack files also carry props that are not parts: the men's Adventurer `Backpack`, the women's
Medieval `Sword` and Sci Fi `Pistol`.

## The method

All parts of a body type are rebound (`um/rebind.py`) onto that body type's skeleton file (Business Man for the men,
Suit for the women) and measured in its rest pose: world metres, +Z up, the face toward -Y, +X the character's left.
Heads cross body types (identical Head and Neck bones), so each head is rebound onto both rigs.

**Heads** are split into connected pieces per material (faces joined by shared positions, since flat-shaded imports
split every vertex) and each piece is classified by its material's role and its position: a skull (`Skin`, the painted
stubble `Skin_Darker`, and the neck's closing ring `Black` of the women's Medieval, Punk and Sci Fi heads), eyes (men
`Eye`; women `Brown` below the brows), brows (men `Eyebrows`; women's `Brown` above the eyes on Formal and Medieval;
small pieces inside `um/zones.py`'s brow box in a hair material), facial hair (pieces of a hair material in the
facial-hair box: below the cheekbones, in front of the jaw; the upper-lip piece is a moustache, chin-only pieces a
goatee, the rest a beard), headwear and accessories (by a short per-head table read off the pack renders: the Farmer
hat, the King's crown, the hard hats, the witch hat, the Medieval hood, the Astronaut and Swat helmets that are the
whole head, the Sci Fi headset, the Punk nose ring, `Earrings`), and hair (everything else of a hair material, such as
the men's Farmer and Worker scalp caps in `Eyebrows` and the Punk's shaved scalp `Red_Dark`).

The **skull type** is measured: full when the skin reaches the body type's highest skull top (within 5 mm; men
1.826 m, women 1.789 m), open-top when it stops lower (men 1.764 m, women 1.761 m: the top belongs to the hair or
hat), none for the helmets. A hair item's style follows its source skull: **cap** (from an open-top head) or **shell**
(from a full one).

**Seams** are measured the way the assembler builds them. Each bottom first goes through `um/fit.py`'s `tuck_cull`
with the shoes (a copy per pair), then rays are cast as `um/fit.py`'s `probe()` does: at the bone axis (LowerLeg for
the ankles, the spine bones for the waist, Neck for the neck) every 4 mm in 36 directions through the seam band, in
the rest pose and in a walking pose (`Walk` frame 6). A ray that misses or first hits a back face looks through
(**see-through**). Where the two parts lie in layers on a ray (the second surface within 15 mm of the first), the part
hit first is the outer layer there; the outer part is the one most rays agree on (or, at a tucked ankle, the shoe),
and a layered ray whose first hit is the other part is a **poke-through**. Second hits farther away (the far side of
the body) are not layers.

**Hair x skull** is measured with rays from outside toward the skull centre (`um/zones.py` `SKULL_CENTRE`), every 10
degrees round and 5 degrees up from 30 below the centre to the crown: **hole** (from 20 degrees up, no skull front
face and no hair in front: a look into an open top), **poke** (the skull in front of hair lying within 30 mm behind
it: the skull cuts through), **z-fight** (hair and skull within 0.5 mm).

**References.** The pack's own characters show a few see-through and poke-through rays at their seams too (grazing
rays, authored overlaps, skinning in motion; the men's Worker trousers with Worker boots show 70 poke rays at rest).
So a pair passes the rays when, in each state, its counts are no higher than those of its references plus 2 rays. The
references of a pair are the pack originals its parts belong to: bottom x shoes, the bottom with its own shoes and the
shoes with their own bottom; top x bottom likewise; head x top, the skull with its own top and the top with its own
skull; hair x skull, the hair on its own skull. Parts with the same mesh (`same_geometry_as`, e.g. the men's
Adventurer and Worker trousers) pool their references, so equal parts get equal verdicts. A pack original is its own
reference and always passes.

**Ankles are judged at rest.** In the walking pose the probe's rays follow the shin while the shoe turns with the
foot, so the pack originals themselves show 10 to 110 see-through rays at the ankles in motion; the walk counts are
recorded (`walk_within_references`), but the ankle verdict uses the rest pose. The waist and the neck are judged in
both states.

**Fixes are tried and measured.** A seam with a vertical gap of up to 30 mm, or see-through rays above its
references, gets `um/fit.py`'s `extend_edge` on a copy of the part whose edge should come down (the bottom's hem at
the ankle, the top's hem at the waist, the head's neck): the gap plus 10 mm, then 10 mm more, up to three tries, each
probed like the pair itself. Hair that pokes or z-fights gets `um/heads.py`'s `inflate` (0.006, the final test's value)
and is measured again.

## The rules (plain conditions)

| Rule | Condition | Verdicts |
|---|---|---|
| bottom x shoes (the ankle) | On each leg the bottom's lower edge is below the shoes' top edge: `overlap_mm = collar top - bottom lower edge >= 0`; the bottom is tucked when most of its shin just under the collar is inside the shoe | `ok_tucked`, `ok_over`, `needs_fix` (extend_edge on the bottom), `gap`, `poke` |
| top x bottom (the waist) | The top's lower edge is below the bottom's upper edge: `overlap_mm = bottom upper edge - top lower edge >= 0`, and no ray sees through | `ok_over` (the top over the bottom), `ok_tucked` (the top inside it), `needs_fix` (extend_edge on the top), `gap`, `poke` |
| head x top (the neck) | The top's neck ring reaches above the head's lowest ring: `overlap_mm = neck ring top - head bottom >= 0`, and no ray sees through | `ok`, `needs_fix` (extend_edge on the head), `gap`, `poke` |
| hair x skull (the scalp) | The hair covers the skull's open top (no hole rays) and the skull never comes out through the hair or lies on it (no poke or z-fight rays) | `ok`, `needs_fix` (inflate), `gap` (the open top shows), `poke` |

In words: **gap** means the parts do not meet (an opening; more than 30 mm apart, or no extend_edge closes it);
**poke** means one part shows through the other and no assembler fix removes it; **needs_fix** names the fix that was
tried and closed it. For the menu: offer a pair when its verdict is `ok`, `ok_tucked` or `ok_over`, or `needs_fix`
with the fix applied at assembly.

## The data file: `catalogue/ultimate_modular.json`

| Key | What |
|---|---|
| `schema` | `prime-game-art/catalogue/ultimate-modular/1` |
| `generated_by`, `sources` | The command; per body type the pack folder (in the raw folder), its source record and the skeleton file |
| `conventions` | Space, units and id rules (below) |
| `thresholds` | `ray_slack` (2), `gap_mm` (5: a "gap" in the counts, in whole millimetres as the final test reported), `fixable_mm` (30), `poke_behind_m` (0.015), `hair_inflate` (0.006), `zfight_m` (0.0005), `states` |
| `characters` | Counts per body type and in total, `animated_woman` (the two files compared: hashes, objects, equal mesh positions, equal animations and skin, the verdict), `animation_sets_per_body_type`, `skeletons_per_body_type` (distinct inverse bind matrix sets) |
| `files[]` | Per pack file: `body_type`, `file`, `character` (the id name), `sha256`, `parts` (`{slot: {id, object}}`), `props`, `animations` (24), `animation_set` (a hash), `skin` |
| `parts{id}` | Tops, bottoms and shoes: `slot`, `body_type`, `triangles`, `vertices`, `materials[]` (`name`, `rgb`: the GLB's linear `baseColorFactor`, `triangles`), `bounds` (`min_m`, `max_m`), `same_geometry_as` (only when an equal mesh exists, found with a 0.5 mm point test; no clothing twins exist today), `seams` (below) |
| `parts{id}.seams` | Top: `upper_edge_m`, `lower_edge_m` (torso column), `neck_ring_top_m` (its highest vertex within 0.10 m of the Neck bone); bottom: `upper_edge_m`, `lower_edge_m`, `leg_lower_edge_m` (`L`, `R`: within 0.13 m of each Foot bone); shoes: `top_edge_m`, `collar` (`L`, `R`: `min_m`, `max_m`, `sectors_m` the collar height in 16 sectors round the foot, from `um/fit.py`) |
| `heads{id}` | Per pack head: `source`, `skull_type` (`full`, `open_top`, `none`), `skin_top_m`, `neck_bottom_m`, `materials[]` (`name`, `rgb`, `triangles`, as for parts), `triangles`, `bounds`, `regions[]` (`kind`, `subkind`, `material`, `pieces`, `triangles`), `items` (its item ids) |
| `items{id}` | What a menu can offer: `kind` (`skull`, `hair`, `brows`, `facial_hair`, `headwear`, `earrings`, `accessory`), `subkind` (`moustache`, `beard`, `goatee`, `stubble`), `head`, `source`, `materials` (names), `colours[]` (`name`, `rgb`), `pieces`, `triangles`, `bounds`, `geometry`, `same_geometry_as`, `recipe`, `recipe_check`; skulls also `skull_type`, `skin_top_m`, `neck_bottom_m`; hair `source_skull_type` and `style` (`cap`, `shell`); stubble `painted` |
| `items{id}.recipe` | The assembler's terms (`docs/assembly.md`): a skull is a `head` spec (`file`, `object`, `keep`, `eye_materials`, `as_skin`, `straighten`); other items a `hair` or `extras` spec (`role`, `file`, `object`, `materials`, `cut`) |
| `items{id}.recipe_check` | `faces` (the item's), `mismatch_by_face` (faces today's assembler keeps differently: its zones test single face centres), `mismatch_by_piece` (the same zones tested on whole pieces: 0 for every item), `proposed_zones` (zones the recipe needs that `um/zones.py` lacks) |
| `proposed_zones` | Cut zones defined in `catalogue_heads.py` and proposed for `um/zones.py`: `facial_hair`, `moustache`, `brows` (the brow box above z 1.698, where the women's `Brown` brows sit over the eyes), their `not_` complements, `not_chin_tuft`, `not_brow_zone`. Tested on pieces, the brow zones also ask for a brow's size (at most 64 triangles; brows have 12 to 40, a fringe piece whose centre falls in the box hundreds) |
| `rules[]` | `id`, `seam`, `condition`, `verdicts` (the table above, in words) |
| `matrices{rule}{M,W}` | `rows`, `cols` (sorted ids) and `cells[]` in row-major order (below). Bottom x shoes and top x bottom: the body type's own parts; head x top: every skull of unique geometry on that body type's rig; hair x skull: every hair of unique geometry on that body type's skulls |
| `cells[]` | `a`, `b` (row and column ids), `verdict`; seams: `overlap_mm`, `outer`, `probe` (`rest`, `walk`: `rays`, `see_through`, `poke`), `allowance` (per state the references' counts plus 2), `references`, `fix_tried` (`fix`, `part`, `drop_m`, `vertices_moved`, `probe`, `closes`), `fix` (when `needs_fix`); ankles also `legs` (`L`, `R`: `bottom_lower_edge_m`, `collar_min_m`, `collar_max_m`, `overlap_mm`, `tucked`, `inside_fraction`), `faces_removed_by_tuck`, `walk_within_references`; waist `top_lower_edge_m`, `bottom_upper_edge_m`; neck `head_bottom_m`, `top_neck_ring_m`; hair: `rays` (`rays`, `covered`, `zfight`, `poke`, `hole`, `bare`), `own_skull`, `allowance`, `fix_tried` (`fix`, `amount`, `rays`, `closes`), `fix` |
| `summary{rule}{M,W}` | `pairs`, `verdicts` (counts), and for the seams `gap_over_5mm` (whole millimetres) and `gap_over_5mm_exact` |

**Ids.** Pack parts: `<slot>_<m|w>_<character>` (`top_m_hoodie`, `shoes_w_soldier`). Head items:
`<kind>_<m|w>_<character>[_<descriptor>]` (`hair_m_punk_mohawk`, `headwear_w_witch_hat`, `beard_m_king`); facial hair
uses its subkind as the kind. `m` or `w` names the source pack, not a restriction: heads, hair and face items cross
body types. Ids are stable as long as the packs' file names are (`catalogue_parts.CHARACTER` maps each file to its name
and refuses an unknown file).

**Colours** come from the GLB (`baseColorFactor`, linear), not from Blender: on meshes with a `COLOR_0` attribute
(white everywhere in these packs) the glTF importer feeds the base colour from the attribute and leaves the viewport
colour and the base colour's default at 0.8 grey (the men's Business and Casual trousers). `um/` reads
`diffuse_color` too, so assembled characters with those trousers come out light grey until #17's code reads the GLB.

## Pictures for the review page

Rendered only to files, in headless Blender (Workbench, specular off), into `--out`:

- `sheets/sheet_top.png`, `_bottom.png`, `_shoes.png`: every pack part alone by slot, a row per body type, in the
  neutral pose; `sheet_skulls.png`, `_hair.png`, `_face.png` (facial hair and brows), `_headwear.png` (with earrings
  and accessories): every head item alone, turned 30 degrees, labelled with its id, style or type, triangles and twin.
- `matrices/matrix_<rule>_<m|w>.png`: each matrix as a grid; the cell's colour is its verdict's status colour (ok
  green, fix amber, poke orange, gap red) and it always carries the verdict's word and its number (the overlap in mm,
  the fix's drop, or the hair's hole, poke and z-fight rays), so colour is never the only cue.
- `confirm/c<nn>_<a>_<b>.png`: sample pairs assembled with `um/assemble.py`'s `build_character` (the other slots filled
  with parts whose own seams are ok, so only the pair under test can show a defect): full front and side at rest, then
  the seam close up from the front and the side at rest and walking (hair: front and from above-behind). A
  `needs_fix` pair is rendered as is and with its fix. `confirm.json` lists each image with its pair, verdict, outfit
  and the build's own probe numbers.

## Known limits

- The face kit (`um/facekit.py`) and the eyes are not catalogue items: our own eyes, mouths and brows replace the
  pack's (art #21). Pack brows are listed because a menu may still offer them.
- Hair floating above a smaller skull (men's hair on women's skulls) passes the scalp rule (no hole, no poke); a
  visible gap at the hairline is a look question, not measured.
- The rays look at seams horizontally (at the bone axes); a gap seen only from above or below (into a wide collar)
  is not measured.
- `headwear x hair` is not measured in this version.
- Today's assembler cuts zones face by face: for 23 hair, brow and facial-hair items the zones also catch faces of
  neighbouring pieces (fringe faces inside the brow box: 7 to 60 per hairstyle; beard strands crossing the
  facial-hair box: 130 to 166 faces for the Adventurer's and the King's hair and beards), counted in
  `mismatch_by_face`. Testing zones on whole pieces (`mismatch_by_piece`, 0 for every item) makes every recipe exact;
  that is a proposed change to `um/heads.py` and `um/zones.py`.
