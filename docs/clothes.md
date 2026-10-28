# Clothes from Meshy (art #196)

The engineer's route (art #196 comment 6469797321): the aliens are always clothed; our own shared body stays the
base; Meshy makes only the clothes. Each outfit is one set (garment and shoes) worn by both characters. Step 2 makes
the raw cloth; the fit, the weights and the rig onto the base body are the next step's, not this one's.

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
   - per piece over its target (`--garment-tris`, `--shoe-tris`): Blender's collapse decimation of a copy, fresh UVs
     (Smart UV Project) and the full piece's base colour, roughness and normal baked onto it in Cycles (`--bake`
     px, selected to active). Decimating Meshy's UVs in place garbled the shirt's stripes and the shoes' laces
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
