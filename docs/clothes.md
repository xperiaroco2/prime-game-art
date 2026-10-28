# Clothes from Meshy (art #196)

The engineer's route (art #196 comment 6469797321): the aliens are always clothed; our own shared body stays the
base; Meshy makes only the clothes. Each outfit is one set (garment and shoes) worn by both characters. Builder B made
the raw cloth (steps 1 to 5); C1 fitted the dungarees onto both bodies and built the two dressed characters (steps 6
to 9). One piece at a time: C2 runs the tracksuit through the same steps.

## The route
1. **Views.** The outfit's concept is a 1536x1024 front / left / back turnaround drawn on the chameleon base body
   (OpenAI, batch `2026-10-28-alien-clothes-s1b`). `tools/blender/clothes_views.py` cuts it into one square PNG per
   view: the figures found as runs of columns that differ from the sheet's grey, every view in one square of the same
   side, each figure centred across with its bottom on one ground line, padded with the sheet's grey.
2. **Meshy.** Batch `batches/2026-10-28-alien-clothes-m1.toml`: `multi_image_to_3d` on `meshy-7.1`, the front view
   first, 2k geometry, textured (4k, PBR, lighting removed), Meshy's remesh to 30,000 triangles with the dense
   original kept: 35 credits an outfit. The model is the whole figure, head and hands included, one fused skin.
3. **Cloth and shoes only.** `tools/blender/clothes_clean.py MODEL.glb OUT_DIR --height 1.80`:
   - scales the figure to the base character's height (the S4b character is 1.795 m to the top of the head,
     1.828 m to the crest), feet on z = 0, footprint centred, facing -Y as imported;
   - welds the UV seams first (glTF splits the vertices at every seam, so without it every UV island is its own
     piece and the speck rules eat the garment);
   - per triangle, four texel samples of the base colour; skin when most are teal or mint
     (`clothes_geom.is_skin`: hue 115-196, saturation at least 0.10, value at least 0.30; the dark denim reaches hue
     200 at value 0.12-0.23, so the value floor is what keeps it);
   - skin specks under 0.4 % of the faces become cloth; cloth specks under 2 % become skin (the eye whites and pupils,
     about 1 % each); the skin is deleted with the loose vertices; nothing is filled, so the collar, cuffs and hems
     stay open;
   - the pieces: the shoes are the parts below 12 % of the height when a skin band at the ankles separates them;
     when the hems sit on the shoes (the tracksuit), the shoes are the pale faces below 11 % of the height (the hems
     are saturated denim or burgundy), the pieces of them of at least 2 % of the faces; `--split-z` cuts the garment
     into a top and a bottom;
   - the openings' spikes go (a boundary tip sharper than `--spike-deg`, 40 degrees, with at most two faces: a few
     rounds) and small holes are filled (`--hole-sides`, 10 edges; UVs from the faces beside);
   - per piece over its target (`--garment-tris`, `--shoe-tris`): Blender's collapse decimation of a copy, fresh UVs
     (Smart UV Project) and the full piece's base colour, roughness and normal baked onto it in Cycles (`--bake`
     px, selected to active). The bake's reach is `--ray` (0.01 m; B's 0.04 m reached the denim beside the
     arm and smeared the inner right sleeve); the baked roughness is floored at `--rough-floor` (0.85) and the
     specular lowered to 0.3, so denim reads as matte fabric, not leather; Decimating Meshy's UVs in place garbled the shirt's stripes and the shoes' laces
     (texels pulled across islands; seen on the first try), so the low mesh never keeps them;
   - writes `cloth.blend` (images packed), `cloth.glb` and `cloth.json` (per piece its triangles and box, what was
     dropped).
4. **Defect hunt.** `tools/run.sh render <cloth.glb>` for the 8-view sheet;
   `tools/blender/clothes_closeups.py CLOTH.blend OUT.png` for the close-ups (collar, chest, both cuffs, crotch,
   back, shoes front and side; flat textured Workbench light so specks and smears show).
5. **Against the body.** `tools/blender/clothes_measure.py CLOTH.blend BODY.blend OUT_DIR`: the body's lines from
   its armature (neck, shoulders, hips, wrists, ankles), both meshes' widths at those heights, every opening of the
   cloth (boundary loops: centre and size), `fit.json`, and a see-through front and side overlay `overlay.png`.

Each script runs in headless Blender (`blender -b --factory-startup --python <script> -- <args>`); the pure maths is
`tools/blender/clothes_geom.py`, tested by `tools/tests/test_clothes_geom.py`. Raw output goes under
`D:/prime-art-raw/2026-10-28-alien-clothes-m1/` (`views/`, the Meshy items, `cloth/<item>/`).

## The fit and the dressed characters (C1)
6. **The female body.** `tools/blender/alien_body_female.py --target tools/blender/alien_female_targets/f2.toml`:
   f2 is the shape that reads in clothes (chest 3.0 cm forward at the centres of the two rounds, hips 2.6 cm a side,
   seat 2.2 cm; f1 was 2.0 / 2.2 / 1.8), the same topology, proven as for f1 (`female.json`, `all_same`).
7. **The fit, once, on the base body.** `tools/blender/clothes_fit.py -- --cloth CLOTH.blend --body BASE.blend
   --female F2.blend --out DIR` (the maths in `clothes_fit_geom.py`, tested by `test_clothes_fit_geom.py`):
   - the pose: the body rests in a T-pose, the cloth is drawn arms down; the armature swings each upper arm until
     the wrist points at its sleeve's cuff (the cloth's lowest side boundary loop), each upper leg until the ankle
     points at its hem, the feet kept flat; the garment moves front to back onto the body's torso centre; the
     cloth's front comes from its shoes (the ankle opening sits toward the heel);
   - the fit on the posed body: per garment vertex its signed distance s from the body becomes `fit_distance(s)`:
     offset + keep x (s - offset) beyond the offset (`--offset` 0.010 m, `--keep` 0.30), s itself between the floor
     and the offset, the floor (`--floor` 0.005 m) when closer or inside; where the cloth bridges (s past `--bridge`
     0.045..0.09 m: the crotch, under the arms) more of the looseness is kept, up to all of it; the moves are
     smoothed over the cloth's edges, then every vertex is put outside the floor. Each shoe moves onto its posed
     foot and is only pushed out where the foot pokes through;
   - the weights: per cloth vertex the body's weights at its nearest posed body point (barycentric over that face),
     lightly smoothed everywhere and strongly where the cloth bridges, four bones at most;
   - the rest pose: each vertex's linear blend skinning is undone (`unskin`), so the cloth's bind pose is the body's
     rest pose; the armature modifier re-poses it and the error goes into `fit.json` (`reskin_error_mm`);
   - the female fit: each cloth vertex follows the body's per-vertex difference (base to f2) at its nearest rest
     body point, smoothed, then is pushed out of f2 where needed: the same cloth, wider at the hips and over the
     chest, no hand edit. Out: `fit_base.blend`, `fit_body_f2.blend`, `fit.json`.
8. **The dressed game builds.** `tools/blender/clothes_dress.py -- --char <char>_char.blend --fit fit_*.blend
   --name <char> --out DIR [--body-from F1.blend --body-to F2.blend]`: on a game build's character (the loco set's
   31 clips) the cloth goes on as separate skinned meshes on its armature (the fit's rest must equal the
   character's); a character built on f1 moves to f2 vertex by vertex (each character vertex on an f1 vertex takes
   that vertex's difference; the head and the neck weld stay); the body faces the cloth fully covers are removed in
   this build only (five rays from each vertex hit the cloth within 0.12 m; one ring of erosion keeps the cut under
   the cloth); the GLB with `export_glb.py`'s fixed textured options. Then glTF-Validator and
   `tools/run.sh godot-check <glb> --profile alien --strict-contract --textured`.
9. **The proof.** `tools/blender/clothes_proof.py -- --blend <char>_char.blend --name <char> --out DIR`: per clip
   (Idle, Walk, Jog_Fwd, Sprint_Fwd, Strafe_Left, Crouch_Fwd, Jump_Start, Jump_Air, Talk_Upper) the poke-through
   (the body vertices under the cloth at rest, followed through every frame: those outside the cloth by more than
   1 mm, the frame maximum, `poke.json`) and a contact sheet (front, side, back at two moments); the close-ups at
   0.8 m (collar and neck, cuffs and hands, crotch, hems and shoes); then `tools/run.sh render <glb> --pose
   "CharacterArmature|Idle_Loop" --no-outline` and a defect hunt.

C1's raw output is under `D:/prime-art-raw/2026-10-28-alien-clothes-m1/c1/` (`cloth/`, `body_f2/`, `fit/`, `dress/`,
`proof/`).
