# The Ultimate Modular assembler

Characters are assembled from Quaternius' **Ultimate Modular Men and Women** packs (CC0; source records in
`sources/quaternius_ultimate_modular_men.toml` and `_women.toml`): one 62-bone armature `CharacterArmature` with
five-finger chains and 24 actions, and per pack character four parts, `<Name>_Head`, `<Name>_Body` (top),
`<Name>_Legs` or `_Pants` (bottom) and `<Name>_Feet` (shoes), with flat material colours and no textures. The engineer
chose this base on xperiaroco2/prime-game#165 after the final character test
(`D:/prime-art-raw/research/2026-10-03-art-research/final-character-test/`); art #17 ported that test's scripts into
`tools/blender/um/` with the behaviour unchanged. Every later task (the glTF export, the parts catalogue, the face kit,
the production of parts) builds on this one implementation.

A character is five pack parts from source characters of its own body type (a head stripped to bald skin, a
hairstyle split off another head, a top, a bottom and shoes; extras such as a moustache are more head regions), each
rebound to the skeleton file's rest pose and parented to its armature, plus our scripted eyes, brows and mouth.
Clothing (top, bottom, shoes) stays per body type; heads, hair and face parts cross body types (the Head and Neck bones
are identical, Head bone rest `[-0.0003, -0.0431, 1.5873]` for both; the women's hips sit 0.108 m higher and their
shoulders 0.036 m narrower per side).

## The command

```
tools/run.py assemble <recipe> [--ids m1_rex,w1_ivy] [--modes chars,face,...|none] [--out DIR] [--blend]
                               [--res PERCENT] [--compare REPORT]
```

Windows: `tools\run.cmd assemble um_final_test --blend`. `<recipe>` is a file or a name in `recipes/`. The command
validates the recipe against the packs in the raw folder (`ART_RAW_DIR`, default `D:/prime-art-raw`) before Blender
starts, then runs `tools/blender/assemble_characters.py` in background Blender and prints one line per character.

| Option | What it does |
|---|---|
| `--ids` | Build only these characters (default: all) |
| `--modes` | `chars` (front and three-quarter), `face` (head close-ups), `hands` (the recipe's hand shots), `lineup` (all at one scale), `crossgender` (the clothing-across-body-types test), `qa` (back and side), `ankles` (each shoe collar from four sides), or `none` (build and measure, no renders; `crossgender` alone builds no character). Default: the recipe's `modes`, else `chars,face,hands,lineup,crossgender` |
| `--out` | Output folder, default `tools/out/assemble/<recipe>/` |
| `--blend` | Also save `blend/<id>.blend` and `blend/<id>.json` per character (below) |
| `--res` | Render size in percent (default 100); the framing does not change. The tests use 10 |
| `--compare` | A reference `build_report.json` (or an extract of one): fail on any difference outside the tolerances (below) |

Output: `build_report.json` (per character: each part's source, rebind move, faces kept and fixes; the skin and
recolours; eye centres; seam overlaps; the seam probe in the rest pose and in the pose; heights; triangles; objects),
`characters/<id>_front.png`, `_threequarter.png`, `_face.png`, `_hands.png`, `lineup.png`, `crossgender.png` and
`work/` (the single views). The four final-test characters with every mode and `--blend` take about 60 s, without
renders (`--modes none`) about 14 s; one character about 9 s.

## Recipes

A recipe is JSON in `recipes/`: `um_final_test.json` (the final test's four characters) and
`um_final_test_neutral.json` (the same in the neutral pose). Pack paths are relative to the raw folder.

| Top-level key | What |
|---|---|
| `packs` | `{"M": "refs/Ultimate_Modular_Men_Pack", "W": "refs/Ultimate_Modular_Women_Pack"}` |
| `skeleton` | The file whose armature and actions each body type uses: `{"M": "Business Man.glb", "W": "Suit.glb"}` |
| `head_bone_rest` | The Head bone's rest position the world-space zones assume; every build asserts it (2 mm) |
| `face_shading` | `flat` (matches the faceted pack meshes) or `smooth` |
| `face` | Per body type `mouth_dz`: the mouth's height below the eye centres |
| `characters` | The characters (below) |
| `hands`, `crossgender`, `modes`, `description` | Optional: hand shots `[side, view, pitch?]` per id; the cross-gender test; default modes; a note |

| Character key | What |
|---|---|
| `id`, `gender` | Lowercase id; `M` or `W` (the body type) |
| `head` | `file`, `object`, `keep` (materials kept as bald skin), `eye_materials` (where the eye centres are read); optional `as_skin` (more materials painted with the skin), `straighten` (a collar ring made a straight neck), `tuck_ears` (flatten the ears at this half-width, m), `cut` (zones) |
| `hair`, `extras[]` | `file`, `object`, `materials` (the head regions taken); optional `cut`, `inflate` (scale about the skull centre, e.g. 0.006); an extra also has `role` (its slot name, e.g. `moustache`) |
| `top`, `bottom`, `shoes` | `file`, `object` |
| `eyes`, `brows`, `mouth` | Face-kit `style`; eyes `iris`, `lash`; brows `rgb`; mouth `lip`, `dz` |
| `skin` | `null` (the head's own skin) or `[r, g, b]` |
| `recolor[]` | `part`, `material`, `rgb`, optional `was` |
| `extend[]` | `part`, `drop` (m): lower the part's lowest ring; optional `why` |
| `notes` | Optional text |
| `pose` | `{"action": "Wave", "frame": 20}` or `{"neutral": {"down_deg": 70}}`, either with an optional `curl` `{"Middle.R": [60, 70, 40]}` (degrees per joint from the finger's base) |

A colour (`rgb`, brows, recolours) is `[r, g, b]` (linear, 0 to 1) or `{"from_part": "hair", "material": "Hair"}`:
that part's material colour (to match hair, moustache and brows). Cut zones (`tools/blender/um/zones.py`):
`chin_tuft` (Punk's goatee), `over_ears` (hair crossing the ears), `ears`.

A variant names a base recipe in `extends`, overrides top-level keys and merges `every_character` into each
character: `um_final_test_neutral.json` is `{"extends": "um_final_test.json", "modes": ["chars", "lineup"],
"every_character": {"pose": {"neutral": {"down_deg": 70.0}}}}`.

Validation (`um/recipe.py`, pure Python, run by the command and again inside Blender) reports every problem at once,
each naming what exists, from the GLBs' own table of contents (`um/glb.py` reads the JSON chunk): an unknown file
lists the pack's files, an unknown object the file's objects, an unknown material the object's materials, an unknown
action the skeleton file's actions. Face-kit styles are checked inside Blender before anything is built.

## The modules

| Module | Concern |
|---|---|
| `um/glb.py`, `zones.py`, `recipe.py` | Pure Python: a GLB's objects, materials and actions; the rest-pose world-space zones; recipes |
| `um/packs.py` | Loading a pack GLB: the stray Icosphere left out, the file's action set remembered, every pose bone reset; placing a character through its root |
| `um/rebind.py` | `rebind()`: a part re-expressed from its file's rest pose in the skeleton's |
| `um/heads.py` | Material-region filters, cut zones, `tuck_ears`, `straighten_ring`, `inflate`, eye centres |
| `um/fit.py` | `tuck_cull`, `extend_edge`, shoe collar heights, the seam `probe()`, seam overlaps and gaps |
| `um/poses.py` | The pack action at a frame (after a full reset), the neutral pose, the finger `curl`; `apply()` is the one code path |
| `um/materials.py` | Flat colours: recolours, colour references, the Principled base colour kept equal to the viewport colour |
| `um/facekit.py` | Our eyes, brows and mouths, built on the bald head's surface (the face kit task, art #21, owns its styles) |
| `um/render.py` | Workbench, specular off; the fitted orthographic camera; labels; composing PNGs |
| `um/assemble.py` | `build_character`, `pose_character`, the cross-gender test |
| `um/blendfile.py` | Saving one clean `.blend` per character; inspecting a saved one |
| `tools/blender/assemble_characters.py` | The entry script; `-- --inspect <file.blend> --json <out.json>` describes a saved file |

## The saved character (`--blend`): the input of the glTF export

`blend/<id>.blend` holds one scene named after the character and nothing else:

- the armature `<id>_rig` (62 bones) and one mesh object per slot, `<id>_head`, `_hair`, `_top`, `_bottom`,
  `_shoes`, `_eyes`, `_brows`, `_mouth` and the extras (`_moustache`), each parented to the armature with one
  Armature modifier on it; pack parts keep their 62 vertex groups, the face parts one (`Head`, weight 1.0);
- the body type's 24 own actions under their original names (`CharacterArmature|Wave`, ...; the women's differ from
  the men's), with a fake user, none assigned, no NLA tracks; no `.001` copies and no other import's actions;
- every pose bone at identity: the rest pose (the T-pose);
- no RootNode, no `_end` empties, no Icosphere, camera, light or world; flat colours, the Principled base colour
  equal to the viewport colour (Workbench reads one, the exporter the other).

**Transforms: applied when saving.** The importer gives the armature (and its parts) a -90 degree X rotation and a
world scale of 100: in armature space a bone's position
or a pose-bone location reads a hundredth of its size in metres. Saving bakes the armature's world matrix into the bones
and each part's world matrix into its mesh, so every object has the identity transform, 1 Blender unit = 1 m, +Z up,
front -Y, the feet at z = 0 (the lowest vertex is within 1.4 mm of it: -1.4 mm on m1_rex and m2_walt, +0.1 mm on
w2_nova, a pack detail). A pose bone's location is measured in armature units, so the actions' location keys are
multiplied by the same 100. The save checks itself: bone positions and deformed vertices at Idle f10, Walk f6 and
Death f20 agree before and after within 0.1 mm (measured: 0.0027 mm), and each saved file is reopened and inspected.

**What the export (art #18) applies: nothing.** Blender's glTF exporter with its defaults (`+Y up`, animation mode
`ACTIONS`) writes 24 animations, one skin of 62 joints, one node per part, identity node transforms and positions in
metres (checked once by hand on `w1_ivy.blend`: vertex y from -0.0005 to 1.8445 m). The animation names keep the
pack's `CharacterArmature|` prefix; whether the game strips it is the export's and the contract's choice.

`blend/<id>.json`, the sidecar: `body_type`, `units`, `fps` (24), the armature (object, bones, source),
`transform_check_max_error_m`, bounds, `height_m`, `feet_z_m`, per part the object, triangles, vertices, vertex
groups, source and materials with colours, `triangles_total`, the actions with their frame ranges, and `inspected`:
what the reopened file holds, with `problems` (empty, or the command fails).

## Pipeline rules learned in the final test

1. **Rebind.** Rest poses differ between pack files: the men's Adventurer is bound 180 degrees off (its parts land at
   z -3.8 m if parented raw; `rebind()` moves Adventurer_Body 5.59 m) and Hoodie Character's rest is 6 to 7 mm lower.
   Every part is rebound from its file's rest to the skeleton's (linear blend skinning with the target rest as the
   pose; exact when the rests match).
2. **Skull types.** Full skulls: men Adventurer, Beach, Business, Casual, Hoodie, King; women Animated Woman, Formal,
   Medieval, Sci Fi, Suit, Witch. Open-top skulls (the top belongs to the hair or hat material): men Farmer, Punk,
   Worker; women Adventurer, Punk, Soldier, Worker. Cap-style hair (Punk's) goes only on its own skull type; shell
   hairstyles fit full skulls with a 0.6 % inflate.
3. **Head materials.** Men's eyes are `Eye`; women's eyes are `Brown` (on Formal and Medieval it also holds the
   brows; eye centres take only faces below 1.712 m). Women's brows are otherwise in `Hair_Brown` or inside the hair,
   so hair is split with a brow-box cut. Punk `Red` includes a chin goatee (cut `chin_tuft`); King and men's
   Adventurer hair include beards; Casual Character `Skin_Darker` is stubble painted on the skin.
4. **Fit.** A bottom's lower edge must be below the shoes' top edge and a top's lower edge below the bottom's upper
   edge (knee-length bottoms over low shoes leave 5 to 25 cm gaps; the women's Worker top leaves up to 21 mm at the
   waist). **Tucked bottoms:** per leg, if most of the bottom's shin vertices 1 to 6 cm below the shoe's collar are
   inside the shoe, the faces below the collar minus 12 mm are deleted and what stays below is pulled 6 mm inside.
   The collar is measured in 16 sectors from points along the shoe's edges (a low-poly shaft has 6 to 8 vertices).
5. **Rays for seams.** Seams are checked with rays aimed at the Neck, spine and LowerLeg bone axes every 4 mm in 36
   directions, in the rest pose and in the pose: a miss or a first back-face hit is see-through; at a tucked ankle,
   the bottom hit first with the shoe within 15 mm behind is poke-through. The z-extent overlaps alone cannot see
   gaps or poke-through.
6. **Flatten ears, do not cut them** (`tuck_ears`): no holes; the hair must still cover the sides of the head.
7. **Close a thin seam by extending the outer part's edge** (`extend`): w1_ivy's jacket hem 20 mm, w2_nova's neck
   15 mm.
8. **Colour references**: a colour may name another part's material (Walt's moustache and brows take his hair's).
9. **Finger curl** on top of an action, about the bones' local -X (the pack's own curl axis): Walt's pointing hand.

## Gotchas

- Each import duplicates the 24 actions with a `.001`, `.002`, ... suffix and puts all 24 on NLA tracks; the
  importer leaves the rig in its first action (Death). Use the skeleton file's own actions (`packs.own_actions`) and
  reset every pose bone before applying one. `packs.discard` removes a discarded import's 24 actions with its rig (in
  one `batch_remove`: one remove per action made the run 60 % slower); `build_report.json` counts what is left
  (`actions_in_session`: 24 per rig still in the scene).
- Imported objects use quaternion rotation, so `rotation_euler` does nothing: move and turn a character through its
  root's `matrix_world` (`packs.place`). The RootNode empty itself has the identity transform; the -90 degree X
  rotation and the scale of 100 sit on `CharacterArmature` (FBX2glTF's node transform).
- After setting a new object's scale, call `view_layer.update()` before copying `matrix_world` for parenting.
- Every pack file carries a stray 80-triangle Icosphere and 17 `<bone>_end` empties (at the fingertips, feet, head,
  shins and PT bones): neither is ever a part.
- The world-space constants (`um/zones.py`: cut zones, the ear box, the brow box, the skull centre, the eye height)
  hold only for the standard rest pose; `build_character` asserts the Head bone position first.
- Judge animations in motion: single frozen frames of the pack's Idle and Walk look twisted (the pack originals show
  the same stance); the neutral pose shows the assembly is straight.
- Workbench renders read better with specular off; a transparent PNG needs compositing onto white before JPEG.
- Blender writes the render time and file path into each PNG: compare renders by pixels, not by bytes.
- `facekit.material()` reuses a material by name (`iris_<style>`, `lip_<style>`, `brow_<style>`): two characters
  with the same style but different colours in one run would share the last colour. The final test's four use four
  different styles each, so it never showed; the face kit (art #21) should name colours per character.
- The saved `.blend` is written with `bpy.data.libraries.write` and `fake_user=True`; without the fake user, a later
  save of the file drops the unassigned actions.

## Regression against the final test

`tools/run.py assemble um_final_test --modes chars,face,hands,lineup,crossgender,qa,ankles --blend --compare
D:/prime-art-raw/research/2026-10-03-art-research/final-character-test/work/build_report.json` rebuilds the four
characters and compares. On 2026-10-03 the whole report equalled the final test's in every value (triangles, heights
rest and posed, seam overlaps, every probe count and sample, the cross-gender numbers); the only differences are the
names (`shoes` for the final test's `feet`, the `pose` format of the neutral variant) and the added `recipe` key. All
103 renders the port makes are pixel-identical to the final test's (their PNG bytes differ only in the embedded
render time); the neutral variant likewise (its report and 9 renders).

The tolerances `--compare` and the test allow, in case a Blender or driver update moves a grazing ray: triangles
exact; heights 1 mm; seam overlaps 0.2 mm; each probe band's see-through and poke-through counts 2 rays; the number
of rays cast exact. `tools/tests/test_assembly_blender.py` rebuilds the four characters at 10 % resolution against
`tools/tests/fixtures/assembly/final_test_reference.json` (the final test's numbers) and checks their saved files, in
one Blender run of about 25 s; it skips when Blender or the packs are missing.
