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
     px, selected to active). The bake's reach is `--ray` (0.03 m, half outside and half inside; B's 4 cm inward
     reached the denim beside the arm and smeared the inner right sleeve, 1 cm left black holes); the baked roughness is floored at `--rough-floor` (0.85) and the
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
   - first the garment's edges longer than `--max-edge` (0.04 m) are split at their middles (`long_edges`, a few
     rounds, then triangulated; flat faces split flat, so the surface and the baked texture's UVs stay): a coarse
     sleeve's flat faces cut chords through the arm, and the arm showed through between their vertices however far
     they were pushed out (C1b's r6: the left elbow 47 mm through at rest); with 4 cm edges the chord's sag on the
     arm stays under 4 mm, inside the sleeve's clearance;
   - the fit on the posed body: per garment vertex its signed distance s from the body becomes `fit_distance(s)`:
     offset + keep x (s - offset) beyond the offset (`--offset` 0.010 m, `--keep` 0.30), s itself between the floor
     and the offset, the floor (`--floor` 0.005 m) when closer or inside; where the cloth bridges (s past `--bridge`
     0.045..0.09 m: the crotch, under the arms) more of the looseness is kept, up to all of it; the moves are
     smoothed over the cloth's edges, then every vertex is put outside the floor. Every push out of the body
     (here, the shoes, the clearance and the female fit) takes a cloth point that is inside the body out along the
     cloth's own outward normal, to where that ray leaves the body (`first_exit`), when the way is short
     (`deep_exit`: at most twice the plain push's depth plus 3 cm, never over 5 cm) and the point is over 5 cm from
     an opening (`boundary_verts`; the collar folds there); else along the nearest body face's normal. A point deeper
     than half the arm has its nearest face on the arm's far side, and the plain push carried the sleeve's front
     through the elbow (C1b's r7: 37 mm through at rest; r8 without the bounds left shards at the collar and hems). Each shoe moves onto its posed
     foot and is only pushed out where the foot pokes through;
   - the weights: per cloth vertex the body's weights at its nearest posed body point that faces the same way as
     the cloth (`pick_facing`: the inner sleeve takes the arm, not the torso beside it; an inner trouser leg its own
     thigh), barycentric over that face, lightly smoothed everywhere and strongly only where the cloth bridges (past
     `--bridge`), four bones at most; a loose sleeve smoothed across the shoulder and elbow let the arm poke through
     (C1's r3). The shoes are stiff: Foot and Toes only (`rigid`), never the shin;
   - the rest pose: each vertex's linear blend skinning is undone (`unskin`), so the cloth's bind pose is the body's
     rest pose; the armature modifier re-poses it and the error goes into `fit.json` (`reskin_error_mm`);
   - the clearance in both poses (`--clear-iters` 3 rounds): the rested cloth pushed out of the rest body, then
     re-posed and pushed out of the fitted body (the push unskinned back); the floor is `--floor-arm` (0.008 m) on
     the sleeves, `--floor` elsewhere;
   - the female fit: each cloth vertex follows the body's per-vertex difference (base to f2) at its nearest rest
     body point, smoothed, then is pushed out of f2 where needed: the same cloth, wider at the hips and over the
     chest, no hand edit. Then the bib and the top hug her chest: where the body's difference at the nearest f2
     point goes forward (`hug_weight`: 3 mm none, 10 mm full) the cloth comes in to `--hug` (0.006 m) from f2,
     lightly smoothed (4 passes; 8 passes and 10 mm left the pull at 7.6 mm), so the chest reads through the bib (a flat bib hid it in C1's r3). Out: `fit_base.blend`, `fit_body_f2.blend`, `fit.json`.
8. **The dressed game builds.** `tools/blender/clothes_dress.py -- --char <char>_char.blend --fit fit_*.blend
   --name <char> --out DIR [--body-from F1.blend --body-to F2.blend]`: on a game build's character (the loco set's
   31 clips) the cloth goes on as separate skinned meshes on its armature (the fit's rest must equal the
   character's); a character built on f1 moves to f2 vertex by vertex (each character vertex on an f1 vertex takes
   that vertex's difference; the head and the neck weld stay); the body faces the cloth fully covers are removed in
   this build only (five rays from each vertex hit the cloth within 0.12 m; a vertex up to `--outside` 0.03 m
   outside the cloth, the cloth behind it no nearer than `--opening` 0.04 m to an opening, is tested from just inside
   the cloth; the foot inside a shoe always goes: a mostly Foot and Toes vertex below its own shoe's top opening less
   `--shoe-margin` (`shoe_top`, per side), or with that shoe straight above it (the toes under the toe box; the ankle
   seen through the opening has none), or mostly on Toes (a closed shoe's toe box hides the toes, also
   where they bulge through its coarse faces; `in_shoe`), or below the opening's rim where it stands (`local_rim`:
   the rim points within `--rim-reach` 0.03 m across the floor, less `--rim-margin` 0.004 m; the rim dips on the
   sides and rises at the heel and the tongue), or through the shoe's wall (`through_shoe`: 1 to 30 mm outside it,
   its nearest shoe point over 1 cm from the rim), and a face of such a vertex goes when all its vertices are on the
   foot below the rim's high point (`shoe_face`; r12 to r15 showed a teal triangle on each shoe's outer side); a
   body vertex inside the cloth at rest, over `--away` 0.08 m from every real opening (C1h, `clothes_open.py`: the
   top's collar and cuffs, the trousers' hems, the shoes' tops; no strap, panel or cut edge) and on no neck, head or hand bone,
   always goes too (`under_cloth`: the rays miss some on the upper back and the crotch, and a crouch or a strafe
   moved them out through the cloth); one ring of erosion keeps the rays' cut under the cloth, the certain cuts
   (the shoes, `under_cloth`) skip it); on the Shoulder bones the limit is `--away-shoulder` 0.04 m (the skin under
   the straps' base, near the collar). The cloth's maps (`clothes_texture.py`): the cleaner's bake leaves about 60 % of the garment's
   2048 px maps black between its small UV islands, and a game camera's mipmaps bled it into thin pieces (the
   straps); `fill` grows each map's islands into the empty texels (push-pull, `--no-fill` keeps them black). The
   bake's denim was near-black (the legs' stored sRGB median 23, 31, 45; Godot's frame 28, 36, 50 against the
   sketch's 44, 55, 73), and with a little specular it read as wet leather: `--denim-gain R,G,B` scales the denim's
   linear colour (`shift`, weighted by `denim_weight`: blue over red and green; the stripes and the orange stitching
   keep theirs). C1d's 2.15, 2.15, 2.1 (Godot's frame over the sketch's, per channel) brought Godot's legs to 42, 54,
   72. Blender's `Image.pixels` of an 8-bit map are its stored sRGB values, not linear. The top is left out of this
   fill: `clothes_top.py` fills its own maps and then wraps its back seam, which a second fill would undo (C1h). The
   dropped route (C1e; its code went in C1h): `--straps` (
   `clothes_strap.py`): the Meshy straps break into folded flaps over the shoulders (3 to 8 layers within 4 cm), so
   each strap's path is found from its own UV column (u 0.476 to 0.511) binned by angle around the shoulder axis
   (`--strap-axis` y 0.04, z 1.18; `--strap-arc` -70 to 100 degrees), followed down the back along the nearest denim
   run until it reaches the back bib (`--strap-run`), and the garment's faces in a corridor along it go: those under
   the strip, and the outer layers and far flaps within 2.5 cm of its edges (unless the body under them would then
   show); a clean strip `--strap-width` 0.035 m wide, `--strap-off` 6 mm off the body with 3 mm lips toward it, lies
   there, mapped onto a plain denim rectangle of the map (`--strap-uv`, mirrored along the strap) and weighted from
   the nearest body point. `--sleeve-smooth N`: N smoothing steps on the arm-weighted vertices along each vertex's
   normal only (an umbrella step along the surface zig-zagged the stripes, C1d r19), each move at most
   `--sleeve-max` 0.01 m and never nearer the body than min(its old distance, `--sleeve-floor` 4 mm); see below for
   why the hybrid route replaced both. The GLB with `export_glb.py`'s
   fixed textured options. Then glTF-Validator and
   `tools/run.sh godot-check <glb> --profile alien --strict-contract --textured`.
9. **The proof.** `tools/blender/clothes_proof.py -- --blend <char>_char.blend --name <char> --out DIR`: per clip
   (Idle, Walk, Jog_Fwd, Sprint_Fwd, Strafe_Left, Crouch_Fwd, Jump_Start, Jump_Air, Talk_Upper) the poke-through
   (the body vertices the cloth hides at rest, within 0.06 m of it and over `--opening` 4 cm from a real opening:
   `clothes_open.opening_points`, per piece the long boundary loop at its joints, the top's collar and cuffs at the
   Neck and the Hands, the trousers' hems and the shoes' tops at the Feet, `clothes_shell.pick_openings`; until C1h
   every boundary counted, the straps', panels' and cut edges and the hidden-face holes too, which left about 96 % of
   the near-cloth body out; inside it or already
   outside it, `outside_cloth_at_rest`; followed through every frame: those outside the cloth by more than 1 mm,
   the frame maximum, `poke.json`; a vertex over `--exposed` 0.02 m outside whose nearest cloth face lies above the
   chest, the UpperChest bone's head, and is turned up is the neck over the collar's roll, exposed skin, counted
   apart as `exposed_skin_max`: `exposed_skin`); with a top, the top's vertices under the garment at rest (their
   normal meets it within `--panel-reach` 4 cm) followed against the garment alone, `top_under_panels` per clip
   (its nearest face can switch in motion, to a strap's folded lip or the bib's edge rim, and read a poke where the
   top stays under its panel; so each is also followed against its own panel point, where its normal met the
   garment at rest, the same barycentric point of that face in every frame, `top_under_panels_tracked`, with the
   room at rest; C1i; a garment face thinner than `--track-min-alt` 1.5 mm, a sliver, or folded back against its
   neighbours carries no tracked point and the ray goes on past it, `clothes_shell.track_face_ok`, C1j);
   the gaps (C1k): the body vertices step 8 removed under the cloth (kept in the blend as `body_removed`, on the
   body's weights, not parented to the armature, so the GLB leaves it out) followed through every frame, a frame
   counting those whose normal meets no cloth within `--gap-reach` 8 cm, nor behind them within `--gap-back` 3 cm (a gap between pieces, the hem and the
   trousers or a band's end and a panel, shows the hollow inside), those uncovered at rest or by an opening counted
   apart (`poke.json` `gaps`, per clip `gaps` with `where`);
   and a contact sheet (front, side, back at two moments); the close-ups at
   0.8 m (collar and neck, cuffs and hands, crotch, hems and shoes); then `tools/run.sh render <glb> --pose
   "CharacterArmature|Idle_Loop" --no-outline`, a Godot frame sheet (`tools/run.sh frames <glb> --clips Idle
   --compare ""`: the denim's matte look is judged there, Workbench ignores roughness) and a defect hunt. For the
   engineer: the sketch beside Godot's front, side and back (`frames --clips Idle --compare "" --yaw 0`, `-90`,
   `180`; each sheet's first cell), one row about 1280 px wide, `look/<rN>/<char>_vs_sketch.png`.

## The hybrid route: our own top, Meshy's trousers (C1f)
Four builders (C1b to C1e) patched the Meshy garment's upper body and it kept getting worse: the shoulders and the
straps' bases were 3 to 8 folded layers, removing them bared holes, the sleeves were crumpled and bulky, and Crouch's
poke-through doubled (r20). A fitted top is better made from the body itself. The loose lower parts (trousers,
pockets, hems; the shoes until S1) stay Meshy's, because they read right and match the sketch.
`clothes_dress.py --shell`
(`clothes_top.py` inside Blender, the maths in `clothes_shell.py`; it replaced `--straps` and `--sleeve-smooth`):

10. **The garment cut** (`cut_garment`). The Meshy garment keeps:
    - everything below `--waist` 1.0 m;
    - the bib at the front (|x| under 0.105 m, below 1.195 m: `--bib`);
    - the back panel inside its V (`--back`: from 0.12 m half width at the waist to 0.03 m at the 1.12 m apex).

    Their edges are cut by planes (`bmesh.ops.bisect_plane`), so they are straight lines, not a row of whole faces.
    The waist is cut first, all round; the bib's and the V's planes then cut only the faces above it. No cut clears
    anything (C1k): `bisect_plane`'s clear kills vertices, and a killed vertex takes every face round it, so the
    bib's and the V's clears took the waist line's vertices beside the panels and with them the trousers' faces under
    them (a sawtooth up to 4 cm low, hidden by the band's removal down to about 0.96 m). The only deletion is
    `keep_face` by face centres (`_bisect` with a clearing side deletes the cut faces by their centres too,
    `clothes_shell.cleared`; the top's hem, cuffs and neck). With `--waistband 0,0` the trousers' top edge beside the
    panels reads 0.999 to 1.000 m on the chameleon (`garment cut`'s `waist_edge_z_min_max`).

    Beside the bib and the back panel the Meshy waistband went too (C1i): its layered side opening tore into dark
    shards and spikes over the tucked stripes whatever the cut. The faces from `--waistband`'s height less its lap
    (3.8 - 0.6 = 3.2 cm) below the waist line up to it, outside the bib (|x| 0.105 m) and the back panel (0.12 m at
    the waist), go (`in_waist_band`), cut straight up and down at those two edges first; and from the band up to
    `--band-flaps` 10 cm above the waist, the faces within 2.5 cm of the bib's side edge or the back panel's whose
    normal points toward the body go too (`inward_flap`: Meshy's layered edge flaps, seen as dark shards). Step 13b
    builds the band in their place.

10b. **The edge peel** (`peel_edges`, C1j). Along the bib's and the back panel's side edges, within `--edge-zone`
    2 cm either side of the cut, from the band's foot up to `--band-flaps` above the waist (r27 peeled up to the
    bib's top and opened the bib over the chest), Meshy's layered side opening leaves wedges, flaps and slivers:
    - the faces mostly of the shirt Meshy baked into the denim (`shirt_texel`: light and grey) go, but only those
      reached from an open edge through such faces (`flood`, C1k): the bib's own light stitching inside the cloth
      stays, no hole opens;
    - then `--edge-peel` 3 passes peel the faces on an open edge that face the body (their normal's way out under
      `--edge-inward` -0.1), slivers (under 1 mm), crumbs (under 2 mm2) or faces folded back (`edge_defect`);
    - then loose bits of `--edge-island` 12 faces or fewer, all in the zone.
11. **The striped top** (`shell`). A copy of the character's body after the f2 move, its faces on the torso and arm
    bones only.
    - The clearance: each vertex moves out along its normal by `--shell-off` 6 mm. Where a kept panel lies nearer
      along the normal, it moves less (`clearance`: 3 mm inside the panel, at least 2 mm). It tapers to 2 mm at the
      `--shell-hem` 0.95 m, which stays tucked under the trousers (`taper`).
    - The cuts: planes at the hem, the cuffs (|x| = `--cuff-x` 0.625 m in the T-pose rest) and a round crew neck
      (`--neck`: the plane through its front and back points, cutting only within `--neck-r` of the neck).
    - The edges: the collar and cuffs fold in toward the body by `--shell-lip` 4.5 mm, a rolled edge rather than a
      paper one.
    - The hidden part: the faces under the bib and the back panel go (step 14: per face its normal and four tilted
      rays within `--shell-hide` 6 cm, `--shell-hide-rings` 1 ring in from the panels' edges).
    - Under the panels (C1i): above the waist each vertex whose five rays meet the garment within `--shell-hide` is
      pulled in toward `--shell-under` 1.5 mm off the body by their share (`ray_share`, `under_offset`): 1 deep
      under the bib, partial at its edge, so the visible top beside the edge keeps its 6 mm and the bib gets room.
    - The weights are the body's own (same vertices). The body under the top is then cut as under any cloth, so no
      clip can push it through. Under the garment (the bib, the back panel, the trousers' waist) each vertex's weights
      blend toward the garment's at its nearest point by the share of five rays that meet it within `--shell-follow`
      4 cm (`follow_panels`, `follow_row`; C1h): with the body's weights alone the top poked through the bib's sides
      by up to 10 mm in the clips (the proof's `top_under_panels`).
12. **The top's UVs and maps.**
    - The UVs: the torso is a cylinder round the vertical axis (v by height, the seam at the back centre), each arm a
      cylinder round its T-pose axis (v along the arm, the seam underneath), all at `--shell-per-m` 1.29 UV units
      per metre in v. A set-in sleeve's seam at |x| = `--seam-x` 0.165 m above `--arm-z` 1.18 m divides them; the
      top is cut along it (and at `--arm-z` beyond it) before the UVs, so the faces' centres put each wholly on one
      side and the seam runs straight (C1k; it zig-zagged along whole faces before).
    - The stripes: one stripe is one image row (`stripe_cover`, box-filtered). They are navy and white of one width
      from the collar down and from each cuff up: `--stripe` 3.2 cm period on the chameleon, 2.6 cm on the axolotl,
      as their sketches draw them. The colours are the Meshy sleeves' own medians (sRGB 29, 38, 53 and 250, 251, 248).
    - The shading: a Cycles AO bake at rest (`--shell-ao` 0.45 strength, 6 cm, 24 samples) darkens the armpits and
      the panels' edges. The 2048x1024 normal map carries fine knit ribs and the AO as a soft height.
    - The material: roughness 0.9.
13. **The straps** (`straps`). Two strips `--strap-width` 3.5 cm wide with 3 mm lips, from the bib's top corners
    over the shoulders down into the back's V.
    - The path: each strap's |x| is piecewise linear in the angle round `--strap-axis` (`--shell-strap-t` -118, 20,
      134 degrees; `--shell-strap-x` 0.078, 0.10, 0.015 m), a station every `--shell-strap-step` 6 degrees,
      `--shell-strap-lats` 5 vertices across (C1g). The front ends reach down over the Meshy buckle hardware, the back
      ends 1 cm into the back panel, so no shirt shows at the V's tip.
    - The height: at least `--shell-strap-off` 10 mm off the body, and 2 mm over the outermost kept surface within
      `--shell-strap-reach` 4 cm (the Meshy hardware lies in layers). The left strap sits 1.5 mm higher, so the two
      do not flicker where they meet.
    - The texture (C1g): a free patch of the garment's texture (no island within 6 texels) takes a copy of the plain
      denim rectangle `--strap-uv` (albedo, normal, roughness), and two dashed stitch lines along it, `--stitch` 3 mm in
      from each edge (3 mm dashes, 2 mm gaps) in `--stitch-colour`, the sketch's orange. The Meshy bib's own
      stitching is light grey, not orange: the two differ.
    - The weights come from the nearest body point.
    - Under the first `--strap-front` 9 cm of each strap the Meshy bib goes where the strap covers it (2 mm inside its
      edges): the broken buckle hardware lay there. Beside it the hardware's warm or near-black faces take the patch's
      plain denim.
    - **The buckles** (C1g): at each front end a bronze rectangular ring over the strap (`--buckle` 3.6 cm from the
      end; `--buckle-size`: 4 mm past the strap, 2.2 cm long, 4 mm bars, 3.5 mm high, chamfered corners) and a domed
      button at the tab's end (1 cm; `--button-size` radius 6.5 mm), 188 triangles for both. Real geometry on their
      own material `buckle_bronze` (`--bronze`: sRGB 0.60, 0.42, 0.20, metallic 0.85, roughness 0.38, no texture;
      the sixth surface), every vertex of a piece weighted like the body under its strap station, so it rides rigid
      with the strap.
13b. **The waistband** (`waistband`, C1i). Per side a denim strip `--waistband` 3.8 cm tall, from 3 cm under the
    bib's side edge round the hip to 3 cm under the back panel's (`--band-over` 0.03; C1j, 1.2 cm before: the band
    started at the bib's cut edge with no overlap and the top showed through), a station every `--band-step`
    3 degrees round the waist's centre (y `--band-axis-y` 0.015 m); 27 stations, 14.3 cm, per side on the
    chameleon (the bib covers almost the whole front).
    - Each column lies on the body (a ray from the centre at each lat's height) offset out
      (`band_lats`, `band_offset`): at the lower edge the trousers' own clearance 8 mm under it plus 1.5 mm (14 to
      19 mm), the edge lapping 6 mm over the trousers' cut edge with a `--band-lip` 3 mm lip folded onto them; at
      the upper edge cinched to `--band-cinch` 6 mm out of the tucked top, then rolled in to 1 mm out of it (the
      ledge), so neither edge shows a gap. At the ends the strip stays 2 mm inside the Meshy panel it runs under,
      never under 0.5 mm off the body (`band_end`, C1k; before, a floor 1 mm outside the top put an end on or
      outside the panel wherever the panel lay nearer); `waistband`'s report counts the end points pulled inside the
      top's offset and those the floor leaves on the panel.
    - The UVs are the straps' stitched patch across its height (the two orange top-stitch lines run along it), the
      weights the trousers' four nearest vertices under the band by inverse distance (`blend_rows`), and a bronze
      button (the buckles' `--button-size` and material) sits on it `--band-button` 1.2 cm beyond each bib edge.
14. **The budget** (C1g). The axolotl's body alone is 41k triangles (head and gills), so the top pays:
    - its faces under the bib and the back panel go when their normal and four rays tilted round it
      (`--shell-hide-tilt` 0.6) all meet the panel within `--shell-hide` 6 cm, one ring in from the panel's edges.
      Cutting more does not pay: the body under a hole is no longer covered, so it stays;
    - the rest is decimated (Blender's collapse, mirrored in x) to `--shell-decimate` 0.32 of the arms' and 0.22 of
      the torso's faces, away from the openings (`--shell-protect`: 3.5 cm from the cuffs, 3 cm from the neck cut,
      2 cm above the hem) and from the UV seams (the torso's back centre and the sleeves' undersides, 6 % of the
      island; the set-in sleeve seam, 2.5 cm), where a big face would take the next island's stripes. Each
      decimated vertex then takes the body's weights under it.
    - The AO bake is black outside the islands: it is filled from them, and across the torso's back seam each
      margin column takes the other side's texels, so the mips and the normal map show no hairline there.
15. **The proof's close-ups in Godot.** `frames --closeups 'label@x,y,z[~Bone]/size/yaw[/pitch];...'` (Godot's
    frame: y up, the character facing +z) adds `sheets/closeups.png`, two shots per row; with `~Bone` the rest point
    moves with that bone into the pose shot (`--closeup-clip`, `--closeup-time`: a clip's worst frame, C1j). Each shot is orthographic, the view's
    height is the size, and the studio light turns with each shot's yaw. The proof's `poke.json` now names up to six
    poking vertices per clip (`where`: rest place, bone, depth).

## Our own sneakers (S1)
The Meshy shoes were about 1,600 lumpy, crooked triangles for the pair, weighted to Foot and Toes all over: in
Crouch_Fwd the Toes bone bent the toe box into folds whose light changed (it read as the texture changing).
`clothes_dress.py --sneakers` (`auto`, the default: on with `--shell`, the dungarees; `on`, `off`) builds a clean
low-top canvas pair from code in their place (`sneaker_build.py` inside Blender, the maths in `sneaker_geom.py`,
tested by `test_sneaker_geom.py`), named `shoes`, so the foot cut (step 8), the openings and the proof treat it as
before.

16. **Parametric to the foot.** Every size comes from the build's own body after the f2 move: each foot's vertices
    mostly on Foot and Toes (weights 0.5 and over) and the two bones' heads at rest. The foot's frame: u along the
    foot from its hindmost point (the Foot head toward the Toes head, flat), v out from the body's middle, z up;
    the right shoe is the left one in its mirrored frame, both built from both feet's points (`merge`), so the pair
    is symmetric. A body with other feet (a body B, a heavier build) gets its own pair from the same code. Both
    current bodies have the same feet: 25.4 cm long, 15.3 cm wide, the ball (Toes head) 22.3 cm from the heel, the
    ankle (Foot head) at 11.5 cm.
17. **The shape** (`build`, `Params`).
    - The outline: the foot's plan hull offset by `clear` 4 mm, the toes given `toe_room` 12 mm, smoothed, 30
      columns, denser at the ball.
    - The rim: the slot between the eyelet stays (`gap` 2.6 cm) from in front of the leg (`slot_rear`: the front of
      the foot's points at the stays' cap height, `stay_cap` 0.92 x the ankle's, plus `collar_clear`) to `throat`
      3.5 cm before the ball, its height the instep's top plus `instep_clear` 7 mm; round the heel the collar on
      the foot's own section at its height (the hull of the points from 8 mm under to 2 cm over it, hit from the
      section's middle toward the column, plus `collar_clear` 7 mm and `heel_clear` 4 mm more at the back), from
      `heel_collar` 0.62 x the ankle's height at the back dipping to `side_collar` 0.53 at the sides and rising to
      the stays. Each outline column meets the rim: behind the slot its section point, the others the slot's curve
      by arc length.
    - One ring grid per column: the rubber sole (a rounded bottom edge, the foxing band raised 0.8 mm at 8.5 to
      10.5 mm with its dark stripe, the top at `sole_top` 1.7 cm rising to `cap_top` 3.8 cm at the toe, the toe
      cap), a 2 mm step in to the canvas upper, 6 rows up to the rim on a quarter ellipse (`fullness` 0.8), the
      padded collar's swell, the roll over the rim and a 12 mm lining; the bottom zipped heel to toe. The tongue
      under the stays rises 1.4 cm past the top eyelets; 5 eyelets a side (6-sided rings), 9 criss-cross flat laces
      and a bow. 1,460 triangles a shoe, 2,920 the pair.
    - The texture: one surface `sneaker_canvas`, a 2048x1024 atlas painted by UV rows (the shell's v by arc length
      from the sole's join, square texels): the canvas (sRGB 226, 221, 204) with a 1.6 mm plain weave, the whiter
      rubber, the foxing stripe, two dashed cream stitch rows over the sole and one under the collar, the tread on
      the bottom, white laces, silver eyelets; a normal map from the same heights; roughness 0.85.
18. **The bend.** Behind the ball the shoe is rigid on Foot, past it on Toes, a smoothstep across `blend` 2.5 cm at
    the ball (`toes_weight`), so the toe box never folds: the sole creases at the ball. The clips' Toes bend is
    capped: `anim_sets/alien_loco.toml`'s `[toes_cap]` (bones, `max_deg` 32, `knee_deg` 6); `clothes_dress.py
    --toes-cap alien_loco` (with the sneakers) turns every Toes key about its own axis to `soft_cap_deg` (bends
    under 26 degrees stay, larger ones ease into 32). Measured on the loco build: 57.5 degrees at most
    (Jog_Bwd__s4b), Crouch_Idle 56.4, Crouch_Fwd 40.5, Jog_Fwd and the strafes 39.7; after the cap 32.0. The arms
    and every other bone are untouched; `dress.json`'s `toes_cap` lists each clip's largest bend before and after.
    The body's toes inside the shoe stay cut (step 8).
19. **The report.** `dress.json`'s `sneakers`: the triangles, the foot's measures, the rim's heights, the slot and the
    foot's clearance (each foot vertex's signed distance to the shoe along its normal: those over the rim, the
    ankle, count as outside).

S1's raw output is under `D:/prime-art-raw/2026-10-28-alien-clothes-m1/s1/` (`r<n>/dress`, `proof`, `godot`,
`render`).

C1's raw output is under `D:/prime-art-raw/2026-10-28-alien-clothes-m1/c1/` (`cloth/`, `body_f2/`, `fit/`, `dress/`,
`proof/`).
