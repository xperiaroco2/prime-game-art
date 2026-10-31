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
    - the bib at the front (|x| under 0.105 m, below 1.166 m: `--bib`);
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

### The sneaker as on the concept (E1j)
S1's pair read as flat slippers or clogs with a tiny bow (the fresh critic and the engineer). The cause was the shape,
not the parts: the stays' rim followed the mitten foot's own instep (flat and tall), the slot was clamped to 4 cm
behind the throat, so the five eyelets sat in 1.8 cm under the bow, and the toe box was a flat roof at the instep's
height. The concept (`2026-10-28-alien-clothes-s1/ax_overall`, `s1b/ch_overall`) is a classic low-top canvas
sneaker. What changed (`Params`; the S1 values above are superseded where they differ):
- **The lace line.** The stays' rim no longer follows the foot (`stay_z`): it is a straight `lace_line` from
  `throat_rise` 3.2 cm over the toe cap's top at the throat to the collar's front corners (`stay_cap` 1.04 x the
  ankle's height plus 7 mm). The foot's skin under the collar's plane is removed by the dress anyway, and the toes
  that poke through a lower vamp are cut by the dress's through-the-wall rule (step 8), so the shoe's shape no longer
  has to wrap the foot's tall mitten toes.
- **The slot** starts `throat` 6 mm before the ball (the lacing reaches the toe cap's back) and is at least
  `slot_min` 5.5 cm long; `gap` 3 cm; 5 eyelets a side from 7 mm behind its front to 10 mm before its rear, each
  lace leaving its eyelet on the hole's slot side so the dark ring shows; laces 5.2 x 2.6 mm; a larger bow with
  four-point tails.
- **The collar** higher, the hem's turn-up sitting on it: `heel_collar` 0.95, `side_collar` 0.82; padding `pad`
  6 mm.
- **The sole** thicker: `sole_top` 2.8 cm, the foxing band at 13.5 to 18.5 mm with a 2.4 mm navy stripe (sRGB 33,
  43, 84), a grey outsole edge under it and a fine grey line along the rubber's top edge; `toe_spring` 7 mm (the sole's
  front lifted off the floor, `toe_spring`).
- **The rubber toe cap** is painted over the upper's front (`toe_cap_arc`, `Params.toe_cap`): its edge 4 cm up the
  upper at the tip, a U from above reaching 7.5 cm back along the sides, the rubber white with a grey edge line and
  a lip in the normal map; the sole's own rise at the tip `cap_top` 4 cm.
- **The last:** the toe narrower than the ball (`taper` 0.3: v x (1 - 0.3 s^1.5) ahead of the ball, s 0 at the ball,
  1 at the tip); `fullness` 0.75.
- **Colours:** canvas cream sRGB 227, 219, 196, rubber 251, 251, 249, dark eyelets 51, 54, 61 (they read as dots, as
  on the concept), laces 244, 241, 235; the eyelet stays' stitched edge 13 mm under the slot's rim.

The topology is S1's (1,476 triangles a shoe, 2,952 the pair). The shoe sheet (`tools/out/dress/e1j/shoe_sheet.py`, a
Blender script: per character the concept's shoes over six Cycles views of the left shoe alone, built on the loco
build's feet) is the quick loop: about a minute for both characters.

### Crisper and fitted clean (E1j2)
E1j's sneaker still read as a soft, inflated blob beside the concept, and skin showed at the throat and through the
vamp. The shoe no longer grows round the mitten foot: the dress makes room inside instead.
- **Room inside (the dress, `clothes_dress.py`).** After the collar's plane cut (E1e), the foot's skin ahead of the
  tongue's back (the instep under the laces, the ball under the vamp) is flattened onto that vertical plane, under
  the tongue's top, easing out over `--collar-band` above it (`collar.flattened_front` in `dress.json`). The plane
  comes from the shoe: `sneaker_geom.tongue_back_u` less `FRONT_CLEAR` 3 mm, stored per side on the `shoes` object
  (`front_Left`, `fwd_Left`, `front_top_z`). The leg's skin left is then shrunk inside the walls as before, the
  shrink easing out over `--collar-band` 3 cm over the rim (1.5 cm left the leg wider than the collar just over it:
  teal shards over the collar's top edge, d32).
- **A slimmer last.** `slim` 0.8: the plan's width about its middle line per u (`slim`), from x 1 at the ankle
  (the heel cup keeps the leg's room) to x 0.8 at the ball and on, the length kept; `taper` 0.34, `toe_room` 8 mm. The collar's rim is kept `rim_in` 5 mm inside the outline (`inside_by`), so the
  walls never flare out over the leg; the leg is shrunk inside instead.
- **Crisper upper.** `fullness` 1 (no inflated toe box); the collar's padding only round the collar, easing off over
  2.5 cm before the slot's rear end, so the stays stay flat and the edge at the laces is crisp.
- **Tall foxing, two navy lines.** `sole_top` 3.6 cm, `cap_top` 4.6 cm; the lower navy line on the band at 9.5 to
  14.5 mm, the upper one 6 mm under the rubber's top (`STRIPE_HI_MM`).
- **A defined toe cap.** The upper's first row lies on the cap's edge wherever the cap reaches past a tenth of a row
  (`row_ks`), so the edge is a mesh edge (no zigzag of a painted curve across big quads), stands `cap_lip` 1.2 mm
  proud and is painted a darker grey line.
- **Panels.** The vamp's seam with the quarters (`seam_cols`, `seam_back` 4 mm behind the slot's front): a shadow
  line and a stitch row, foot line to rim.
- **The tongue and laces.** `gap` 3.4 cm; the tongue just under the stays' rim (it shows between the laces), rising
  `tongue_rise` 1.6 cm over the top eyelets and leaning back `tongue_lean` 0.3 of that; the laces 3.6 x 3.2 mm cords
  arching `lace_arch` 4 mm over the tongue.
- **Heights.** `heel_collar` 1.12, `side_collar` 1.02, `stay_cap` 1.10 (x the ankle's height: the trouser hem's
  turn-up rests on the collar, as on the concept), `throat_rise` 3.6 cm.

Same topology, 2,952 triangles the pair. Raw output: `2026-10-30-alien-dress-e1/d32/` (`sheet/s7`, `s8`, `dress/`,
`proof/`, `look/`, `side/`) and `d33/` (the final: `sheet/s9`, the same folders); drivers `tools/out/dress/e1j2/` (`sheet.sh`, `dress.sh`, `closeout.sh`, `chain.sh`: sheet, dress and
close-out in one background run).

### The last polish (E1j3)
E1j2's sneaker read as the concept's up close, but a teal band showed between the chameleon's collar and turn-up
(jagged at the front corner), the heel was a square box from behind, the toe box flat on top, the sole's outline
faceted at the toe and heel, and at full-body distance the shoe was one pale blob.
- **The turn-up rests on the collar (the dress).** `--hem-rest` m (the drivers pass 4 mm): round each trouser leg,
  in 24 angle bins about the hem's middle, the hem's lowest point goes down to the shoe's highest point in that
  direction (the collar at the back and sides, the tongue in front) less `--hem-rest`; never up, at most 4 cm, a
  missing bin taking its neighbour's, smoothed round the circle (`clothes_fit_geom.hem_drops`). The hem was higher
  at the front and outside than at the back, so one drop by its lowest point (d34) closed nothing. Each garment
  vertex moves by its angle's drop: the whole turn-up up to 7 cm over the hem's lowest point, easing to no move over
  the next 15 cm up the shin (`hem_shift`). `dress.json`'s `hem_rest` holds each side's hem height and drops;
  `heel_rim_z` (the collar at the heel's back) is stored on the `shoes` object. The collar's side dip is shallower
  (`side_collar` 1.02 to 1.05).
- **A round heel cup.** The collar's rim round the heel is pulled in `heel_in` 1.2 cm (easing out toward the slot's
  rear end; the dress shrinks the ankle inside it, as for the slim last), the heel's walls lean in from low
  (`heel_wall` 0.5) and the plan narrows to `heel_slim` 0.82 at the heel's back (`slim`'s `heel`); the collar's
  dip now starts at the heel's back, not at the ankle. From behind the heel tapers up instead of a box.
- **Rounder walls, a domed toe box.** `wall` 1 to 0.85 (the walls lean in lower: no vertical sides under a flat top from
  the front; 0.72 let the chameleon's right foot through the side wall by 29 mm in Jump_Start, d34); the toe box's rows ahead of the ball are raised up to `dome` 1.2 cm at mid-height
  (`column_shape`, `_ring_point`'s `dome`: none at the join and the rim, so the toe cap and the laces stay).
- **No facets.** `around` 30 to 40 columns, spent where the outline turns: `resample`'s `bend` 1.5 weights the
  arc length by the curvature (`curvature`, x 3 cm, at most x 3), so the toe and the heel get the new columns. The
  outsole's bottom edge is rounded `sole_round` 5 mm.
- **Reading at full-body distance.** The canvas a touch greyer (sRGB 214, 207, 186), the rubber white as before;
  the navy lines darker and bolder (`STRIPE_MM` 3.4, the upper line 3.2 mm); the rubber's top edge line darker;
  the laces whiter and the eyelets darker.

3,532 triangles the pair (+580, all in the visible columns). Raw output: `2026-10-30-alien-dress-e1/d34/`
(`sheet/s10` to `s12`, a first dress) and `d35/` (the final: `dress/`, `proof/`, `look/`, `side/`); drivers `tools/out/dress/e1j3/` (`HR` sets
`--hem-rest`).

### The low collar (E1k)
A fresh critic on d35 found a dark wedge on the upper thigh in Walk, a shoe that read as a tall block against the
concept (its collar high at the heel and sides, into the turn-up), small eyelets and thin laces at game distance, a
throat tear in Crouch and teal skin at the ankle.
- **The thigh wedge is the arm's shadow, not the garment.** A ray probe on d35 in Walk (`tools/out/dress/e1k/
  wedge_probe.py`: from three cameras in front of the hips, the first hit per ray) finds almost no back faces
  (0 to 5 of about 3,800 trouser hits per view, none on the thigh), so no inside or crumpled face of the side opening
  shows. A shadow ray from each trouser hit toward the approved key light (`look_presets.json`, at (-2, 3.2, 3)) is
  blocked by the body (the swinging hand and forearm) for 300 to 480 hits in Walk f5 and f27 and none in the bind
  pose. A Cycles render with one sun at the key's direction (`sun_probe.py`, `d36/sun/`) draws the same wedge.
  With the key at 3.0 and the fill and ambient at 0.12, that shadow on dark denim is near black: a look question
  (the fill or the shadow's softness), not a fit fix.
- **The low collar.** `heel_collar` 1.12 to 0.96 (the heel tab), `side_collar` 1.05 to 0.84 (under the ankle bone),
  `stay_cap` 1.10 to 0.95 (the collar's front corners). The turn-up stays at the fit's own height (`--hem-rest` is
  off again), so a band of ankle shows between the collar and the turn-up all round, as on the concept. d36 tried
  0.90 / 0.76 / 0.92: the rim then sat where the ankle widens toward the heel, and the skin eased out over it in
  teal fins.
- **The ankle over the low collar.** `--collar-keep` 6 to 9 cm (the plane rule owns the skin up to this far over
  the rim's top, so it still reaches into the turn-up and its cut edge stays hidden there; at 6 cm over the lower
  rim the skin's top edge showed jagged inside the turn-up, d36) and `--collar-band` 3 to 4.5 cm (the shrink into
  the collar eases out over more).
- **Eyelets and laces read at game distance.** `eyelet_r` 3.3 / 1.7 / 0.9 mm to 4.6 / 2.4 / 1.2 mm (`eyelet_in`
  7.5 mm), `lace` 3.6 x 3.2 mm to 5.2 x 4.0 mm.
- **The axolotl's "R top" close-up** looked from between the legs (yaw 20, pitch 60); it now looks from the front
  outside (yaw -40, pitch 50; `tools/out/dress/e1k/frames.sh`).

Raw output: `2026-10-30-alien-dress-e1/d36/` (the probes, `sheet/s13`, the first low-collar dress) and `d37/` (the
final); drivers `tools/out/dress/e1k/`.

### The close-up leftovers (E1l)
- **Specks on the collar (partly fixed).** Skin with the shoe's wall beside it at its own height (a horizontal ray
  from the leg's axis meets the shoe) now counts as under the rim, wherever its nearest rim point in xy lies
  (`--collar-beside`, on by default). The collar's height changes fast between the heel and the side, and that skin
  was eased out through the padding. The speck probe (`tools/out/dress/e1l/speck_probe.py`) found 20 face points
  per leg on the chameleon, 13 on the axolotl, at z 0.10 to 0.11; the d39 close-ups show the outside clean and small
  remnants at the back.
- **The ankle's front edge (not fixed).** Two leads were tried and neither moved it:
  - the collar region also takes the ankle's skin within `--collar-ankle` (8 cm) of the leg's axis. The rim's xy
    reach (12 to 13 cm) already held all of it: 0 vertices added;
  - the instep's flattening onto the tongue's back now eases out over `--front-band` (1.5 cm, was the 4.5 cm
    `collar_band`) with a soft ramp across the plane (`clothes_fit_geom.soft_flat`, `--front-soft` 1 cm).

  The probes (`fold_probe.py`, `front_probe.py`) find no open edge and no inverted face on the ankle between the
  collar and the turn-up, and from the front they meet only the shoe up to z 0.12 and the skin from 0.12 to the
  turn-up. So the vertical edge in the L front close-up is probably the turn-up's inside beside the ankle, not a cut
  in the skin. That is not proven.
- **The toe crease ahead of the lacing (no visible change).** The shoe's Toes weight's blend now starts
  `crease_gap` (3 mm) ahead of the throat's front end (`sneaker_geom.crease_u`), never behind the ball, so the
  lacing stays on Foot. The Crouch tear beside the laces and the crumpled laces still show in d39.

Raw output: `2026-10-30-alien-dress-e1/d38/` (the specks and the region) and `d39/` (the final); drivers and probes
`tools/out/dress/e1l/`.

C1's raw output is under `D:/prime-art-raw/2026-10-28-alien-clothes-m1/c1/` (`cloth/`, `body_f2/`, `fit/`, `dress/`,
`proof/`).

## Bodies by drawing (D2, art #196)
Bodies A and B are drawn in mm from their approved concepts before any 3D (the crystal's route, `docs/props.md`):
`tools/blender/body_dims_probe.py` (headless Blender, read only) dumps body A's rest; `body_dims_measure.py` (plain
Python, `body_dims_geom.py`) measures each concept's front, side and back per pixel row into
`tools/blender/body_dims/<A|B>.toml` (the trunk every 10 mm of height, 5 mm across the neck, chest and crotch; the
arms and legs on their own axes; hands, feet, B's chest rounds; the neck ring); `body_drawing.py` draws the sheets.
The scale puts the concept's neck-ring line at the body's ring and the sole at 0; one height map pins the crotch to
the body's. The side view is aligned on its edges as drawn at the crotch + 60 mm onto body A's mid-depth there.
Where a hanging limb forms the side view's edge, the tables write "-", never an interpolated or a limb's value: the
hand at the front (`front_y` and `depth` over `body.side_hidden_z`) and, from under the armpits down to where the seat
comes out behind it, the arm at the back (`back_y` and `depth` over `body.side_back_hidden_z`; `back_hidden` finds it
by the crease the back shows behind the arm). A key depth there is drawn at the nearest measured height within
20 mm, labelled "AT", or written "-". The standard neck ring: `docs/decisions/2026-10-29-neck-ring.md`.

## Bodies built to the drawing (D3, art #196)
The smooth body (S4b) is deformed station by station to its table, keeping its surface, topology, weights and
four-digit hands: `body_fit_blend.py dump` (headless Blender) writes the body's vertices, weights, edges, bones and
open loops; `body_fit_run.py` (plain Python, `body_fit_geom.py`) fits body A to `A.toml` and writes B's rest skeleton
from `fit.toml`; `body_fit_blend.py apply` saves the fitted `.blend` (`--foot-table`: the new forefoot) and proves it
(`apply.json`, with every bone's rest turn against A's held to the contract's `rest_turn_max_deg`);
`body_fit_review.py` draws the whole-body gate's sheets (four sides with the concept's outline, and the close-ups).
The rules, in `body_fit_geom.py`'s docstring:
- the trunk's x scales about the midline to the front width, the front half of y to `front_y` and the back half to
  `back_y`; above the armpit x stays (the T arms) up to the neck, whose widths come back from 75 to 60 mm under the
  ring; the 30 mm under the ring blend back to the body and the ring's 24 vertices stay exact;
- the legs per height about each leg's own middle (our legs stay vertical; the concept's splay is not copied); the
  arms along |x| on the T rest, eased in past the arm's root (the 10 to 70 mm past our armpit, whose stations are not
  comparable with the concept's hanging arm); the hands and feet as they are;
- the targets and ratios are smoothed along the body (20 mm; 6 mm over the neck and under the armpit), because the
  tables step in whole pixels and per-station ratios ripple the surface in bands;
- `fit.toml`'s `keep_front` zones keep the body's own front where the concept's side view shows the hand, not the
  body (A: z 640 to 1000, easing over 60 mm at the ends).

The check is the overlay error per station, built minus table (`errors.md` beside each fit): within 5 mm on the
trunk and 3 mm on the limbs; stations left alone by rule are listed with their rule, not counted.

Body B (D3b) is A's fitted mesh on B's rest (B1's `deform` with `fit.toml`'s joints), then:
- the hands and feet: A's (our size, the engineer's answer) scaled per axis by the two tables' B/A ratios
  (`body_fit_run.limb_scales`: hand 0.960 long and 0.878 wide along and across the Hand bone, foot 0.850 long and
  0.911 wide about the ankle), never set by hand; the mesh per axis, the bones only along their own directions
  (`keep_directions`: the heads where the mesh's joints go, each bone keeping A's direction, so none turns);
- the fit to `B.toml` with her chest rounds (`chest_of`) and the neck base: her concept's shoulder line is 8 mm under
  the ring, so above the armpit her widths stay the body's up to the ring and the 60 mm under the standard ring widen
  into a smooth slope (`fit.toml`'s `neck_base`; right under the ring `neck_tangent` sets the outline since D3f, see
  below); the ring row down to the shoulder line is left out of the error table by rule;
- our armpit is the table's but at least 25 mm under the arm's lowest vertex (`ARMPIT_GAP`): B's concept armpit sits
  higher than our arm's root on her rest, and the widths between are marked "arm root", not counted.

A table's "-" (a hanging limb forms the side edge) is never a value: there the fit keeps the body's own shape, moved by
the error at the band's measured ends (`fill_gaps`).

D3c replaced the toes: projecting them onto their hull (D3b's `--round-toes`, removed) left slits, flaps and holes
twice, so `apply --foot-table
<body_dims/X.toml>` cuts each foot along one plane 30 mm behind its Toes head (moved back in 5 mm steps until the cut
is one loop) and grows a new closed mitten front from the cut's own vertex loop (`body_feet_geom.forefoot`): rings
scaled from the cut's section to the table's foot length (from the kept heel), width and toe height, rounded as a
superellipse in top and side view, the sole flat until the front turns it up, a fan to one tip vertex; the cut's
loop is shared (no seam), weights from the old toes' nearest vertex (Foot and Toes only). A Taubin smoothing evens the
front and 45 mm behind the cut, a plain one fills the ankle front's fold (S4b's own). The bone rest is applied first,
so B's cut sits at her Toes. The topology changes under 0.25 m only: `apply.json` proves every vertex above it is the
fit's (`off_feet_verts`, `fit_vs_built_off_toes_max_m`), the ring found again by position.

The neck base (D3c): the fit's front and back met the ring's only inside the 30 mm lock and drew a collar ridge with a
step at the ring. Over the 60 mm under the ring (`NECK_JOIN`) they now follow one cubic slope from the fit's value
and slope to the ring's own front and back (`neck_join`, clamped so it never overshoots); these stations are "neck
taper" in the error table. Since D3f the outline right under the ring is `neck_tangent`'s (below): body and head meet
at the heads' flare angles, not vertically (`docs/decisions/2026-10-29-neck-ring.md`, "Join"). Under the armpit the front and back are smoothed over 12 mm
(`SIGMA_FB_ARMPIT`), not 6 like the widths (the chest line at the armpit's height), and B's chest rounds' depth is
smoothed along z over 15 mm (`CHEST_SIGMA`; its kink at the crease drew a line under the rounds).

### D3d to D3g: B's shoulders, the neck join, the feet
`body_fit_run.run_fit` runs, after the two station passes, each step `fit.toml` names for a body:
- `arm_follow` (B, D3d): her concept sets the chest up to 50 mm ahead of A's on the same ring, so each pass moves the
  arms by the trunk's centre shift over the armpit (`body_fit_geom.arm_dy`); the shoulder chains (the Shoulder to
  the fingertips) then move rigidly in y by the arms' mesh move, every pass and refit together (`arm_shift_mm`,
  `arms_moved`), so her arm mesh sits on its bones as A's does (`arm_offsets`, within 1 mm in y);
- `girdle` (B, D3g): the trunk outside |x| 60 mm takes the arms' move too, easing to all of it at the shoulder joint
  and from 60 mm under the armpit up (`girdle_share`): the trunk no longer shears past the arm root (the diagonal
  crease from the neck base to each armpit);
- `shoulder_lift` (B, D3d and D3e): her shoulder tops raised half way to her concept's slope against a smoothed
  envelope, then Taubin rounds over the band;
- `relax` (both, D3f): the fit's moves diffused over the mesh (`relax_moves`; the ring, hands and feet keep theirs),
  where the station maps meet; then `refits` rounds of one pass and a shorter diffusion;
- `neck_tangent` (both, D3f and D3g): the body leaves the ring at the heads' flare angles (22 side, 17 front, 18.5
  back degrees) over 10 mm, then eases into the trapezius over 35 mm; the head side flares into the ring over 70 mm
  (`neck_flare_morph`), one continuous neck (the ring ADR's "Join");
- `shoulder_round` (B, D3g): 12 plain Laplacian rounds on her girdle's front corner (`shoulder_share`);
- `chest_trim` (B, D3e): the chest rounds' apex brought to the table.

The feet (D3g): `apply`'s new forefoot (`body_feet_geom`) also gets an instep, the mid-foot lifted 7 mm and 8 %
narrower halfway between the cut and the ankle (`body_feet_geom.midfoot`; `fit.toml` `[feet]` `instep_lift`,
`midfoot_narrow`); D3f raised the sole's outer edge by up to `sole_round` mm (`sole_edge_lift`). B's rest: each bone
keeps A's rest direction (`rest_turns`: B's largest turn is the Neck's, 0.38 degrees, from the ring's height);
`body_fit_run.py` exits 1 above the contract's `[body_types.B] rest_turn_max_deg` or an arm offset over 1 mm, `apply`
above it again from Blender's rest matrices.

## Dressing D3's bodies (E1 to E1i2, art #196)
- **The heads** (E1): `alien_char_build.py --neck-band flare` (from `alien_char_run.py --neck-band flare`) flares the
  head's neck into D3's ring over 70 mm with `body_fit_geom.neck_flare_morph`, then the 8 mm bridge and the seam
  smoothing; the 30 mm smoothstep band stays the default for the old bodies.
- **Per-body fits** (E1): A11 and B13 differ in topology (the feet's cut), so each gets its own
  `clothes_fit.py --body` base fit (no `--female`; her fit has no chest hug). `pick_facing` skips zero normals.
- **The cut planes from the bones** (E1b): `clothes_dress.py --planes bones` sets the top's and the garment's planes
  from the character's own bones (`clothes_shell.body_planes`): heights (`--waist`, the bib's top, the back's apex,
  the crew neck, `--arm-z`) mapped linearly from the old body A's torso (Chest 1.028 m to Neck 1.339 m) to the
  body's, `--seam-x` moved with the upper arm's root, `--arm-axis` through the upper arm's head, and the cuffs
  `--cuff-back` (35 mm) in from the hand bone's head. The old fixed planes (`--planes fixed`, the default) put B13's
  cuff past her wrist (her sleeve covered the hand, the proof's 64 mm pokes) and A11's on the thumb's root.
- **A garment's own waist** (M2c): `--waist-z` puts the waist plane at that height instead of the bones' (the other
  planes stay from the bones). The m2 dungarees' band edge on B13 sits at 0.896 to 0.932 m, under her bones' 0.954 m:
  between the two the Meshy shirt texels stayed beside the bib (a grey crumpled shard by the hip button). With
  `--waist-z 0.93` the built band covers 0.898 to 0.93 m; the top's hem goes down with it (`--shell-hem 0.92`), or the
  body shows between the band and the hem. The m2 map's plain denim for the straps and the `--plain` boxes is
  `--strap-uv 0.5957,0.6172,0.5425,0.5879` (a 44 x 93 texel window inside a leg island, sRGB std 0.002; the default
  rectangle lies on an island's edge there: the straps' black hexagons). Its turn-ups' grey herringbone texels and
  the hips' side openings, front and back, get plain denim from `--plain` boxes (`0,0.3,-0.3,0.3,0,0.19`,
  `0.108,0.25,-0.25,0.05,0.82,0.95` and `0.12,0.25,0.05,0.25,0.82,0.95`); `--waistband 0.038,0.015` laps the band
  further over the trousers' ragged top. Its denim is already a dark indigo (legs sRGB 0.066, 0.125, 0.198): E1's
  `--denim-gain 2.15,2.15,2.1`, tuned for the old near-black bake, made it a light mid blue; `1.05,1.3,1.25` brings
  the High look's legs to the turnaround's (measured on the comparison sheets: render/turnaround in linear light).
- **The skin the garment hides follows it** (M2d): `--skin-follow lo,hi,clear,reach` (m; d47 on: `0.015,0.035,0.004,0.04`)
  takes every body vertex under the waist whose nearest cloth is the garment (within reach) and, by its distance
  from the nearest opening (none within lo, all from hi on, `clothes_fit_geom.follow_share`), first pulls it in
  along the nearest garment face's normal until it lies clear inside (`pull_in`; skin more than 15 mm outside is no
  poke and stays), before the cover test, then gives the kept ones the garment face's weights (`blend_rows`, the
  corners by nearness). Traced per vertex in M2d: her right ankle front inside the turn-up lay
  6 to 9 mm outside the cloth at rest, 44 mm from the hem, and no rule cut it (its tilted cover rays leave by the hem);
  the crotch's skin (Hips and both UpperLegs) lay 3 to 9 mm inside the seat, within under_cloth's 1 mm once the fit
  shifted a vertex, and its weights differ from the garment's (mostly one UpperLeg), so it left the cloth in motion.
- **The flat back panel** (M2d): `--flat-back blend,radius,band,clear` (d47 on: `0.06,0.05,0.012,0.008`) gives every
  back vertex over the waist the depth of `clothes_shell.panel_fit` (a quadratic across, from the vertices within
  radius in x and band in z, less all layers' mean within 1 cm) eased in over blend above the waist, never nearer the
  body's back than clear, and its weights along `--bib-chain`: Meshy's panel had a vertical fold at its apex.
- **The straps' back ends on the panel** (M2e): the panel's "crumpled top" in Jog was not the panel. The built straps
  reach `--strap-back-below` under its apex 12 to 15 mm off it, with the body's weights under them (UpperChest, the
  shoulders), while the panel has the spine chain's; in motion their square ends stood off it as loose flaps over
  its top. `--back-join blend,gap` (d50: `0.03,0.002`; `clothes_top.back_join`) lays each strap row with the panel
  under it (a ray in along the row's normal) gap outside it, its lips and the left strap's 1.5 mm over the right
  kept, gives it the panel face's weights and eases the rows in front out over blend along the strap
  (`clothes_shell.join_rows`). The panel's apex tip between the straps still shows as a small dark triangle.
- **The top's rows under the built band** (M2e): the top follows the garment's weights by its rays' share
  (`follow_panels`) before `straps()` builds the waistband, and `cut_garment` had cut Meshy's band at the hip
  sides, so the top's rows at z 0.90 to 0.92 there kept the body's Spine weights and came out through the band by
  10 to 23 mm in Jog and Crouch (`--shell-hem` moves only the hem, 3 cm under). `--band-follow H` runs the follow
  again after the band, for the top up to H over the waist (d50: 0.02): Jog's worst 15.1 to 7.8 mm (tracked 22.2 to
  14.9, one vertex at the right hip, z 0.904).
- **The built back bib** (M2f): Meshy's back panel ended at the shoulder blades' foot (z 1.067) and the straps met
  in a lump at the waistband, so from behind she read as jeans with suspenders. `--back-bib
  z_c,z_v,hw_b,hw_t,x_v,off,border` (d53: `1.15,1.10,0.08,0.103,0.062,0.010,0.012`, measured off the approved
  turnaround's back view scaled by the waist and floor; `clothes_top.back_bib`, the grid
  `clothes_shell.back_bib_grid`) deletes Meshy's panel over the waist and builds the turnaround's outline: sides
  from half width hw_b at the waist to hw_t at the top corners (z_c), a V top down to z_v; each row one quadratic
  across from rays at the body's back (the spine's groove bridged), at least off clear, the rows under the waist
  tucked 2 mm under Meshy's back band, the outline folded `--strap-lip` toward the body; weights by
  `clothes_shell.chain_row` along `--bib-chain`. It runs before the top, so `shell()` hides and follows the top
  under it. Its border (width border) gets the straps' stitched patch after `straps()` (`back_bib_uv`); its inner
  faces plain texels from a `--plain` box (`0,0.14,0.02,0.3,0.9305,1.2`). The straps' back ends are aimed at its top
  corners (`strap_back_z` = z_c less `--strap-back-below`; their back |x| in `--shell-strap-x` kept inside hw_t, or
  `--back-join` finds no panel under the outer lip and glues nothing, d52).
- **The turn-ups' light cuff** (M2f): a `--plain` box takes a 7th value, its mix toward `--light-denim` (sRGB,
  default `0.60,0.70,0.82`, the denim's reverse side): the box's faces go into their own window, its diffuse the
  plain denim blended toward that colour with its grain kept. d53: the ankle box split at z 0.163 (the turn-up's
  fold), `0,0.3,-0.3,0.3,0,0.163,0.75` under it.
- **The turn-ups' cut by texel row, the back bib's gain** (M2g): split by face centres, the cuff's light/dark line
  followed the faces (dark teeth over the light). A `--plain` box's 8th value is a height: the box's regions are laid
  on one height scale in their window and the tint applies to the texel rows under it (a 2 mm blend,
  `clothes_shell.cut_ramp`), so the line is straight on the cloth whatever the faces; d55:
  `0,0.3,-0.3,0.3,0,0.19,0.75,0.163` (one box, -1: no cut). Its 9th value multiplies the window's diffuse: the back
  bib's panel uses the straps' own texels (medians equal) but faces away from the light and read darker; d56: 1.35.
- **The striped walls beside the buckle** (M2g): the shard under the buckle was Meshy's bib side wall (|x| 0.100 to
  0.105, 3 to 5 cm behind the bib's face, z 1.03 to 1.11), its UVs on the shirt Meshy baked into the denim (stripes),
  over the edge peel's zone (`--band-flaps`: up to 1.035). `--shirt-top` (m over the waist) raises the baked-shirt
  test alone to the bib's top, and `--shirt-min` (share of up to 13 samples per face, `clothes_shell.face_samples`)
  catches a striped face that the old five samples (nearly all white) missed; d55: `--shirt-top 0.19 --shirt-min 0.2`
  peeled 38 faces (0 before), from the open edge inward only.
- **The crumbs beside the buckle, the turn-ups' relax** (M2h): `--island-top` (m over the waist) removes the
  garment's loose denim bits (`--edge-island` faces or fewer) up to that height, the bib side wall's crumbs; d58:
  `0.19`, 8 pieces, 15 faces. `--turnup-relax z_top,rounds,alpha[,outward]` levels each leg's hem and relaxes the
  turn-up's radius under z_top (`clothes_top.turnup_relax`); off by default. Tried in M2h (d59 to d61) and M2i (d64,
  d67): the cuff's teeth hardly change in the close-ups, and the proof reports 13 to 26 mm at the back of the calf
  (z 0.162) at rest and in motion. A probe of d67's blend found that skin 24 to 27 mm inside the cuff along its
  normal, the nearest face being the fold's inner layer: probably the proof's single-face sign at the double layer,
  not visible skin. Not used. `outward` (4th value 1) never moves a vertex in toward the leg's axis.
- **The cloth's side from every tied face** (M2i, `--tie-side`, default 1): the under-cloth test and the skin pull
  took the side of the cloth from the one face a BVH nearest query returned. At the seat's seam the nearest point lies
  on an edge whose two faces point different ways, so any garment change elsewhere (M2h's crumbs removed early, the
  cuff's relax early) moved the tree's face order, flipped the side and kept a 12-vertex crotch patch (9 to 14 mm
  pokes in motion). Now the side comes from the tied faces' pseudo-normal (`clothes_fit_geom.tie_side`, angle-weighted
  at a vertex) and the skin pull moves along it; `--cosmetic-early 1` runs the crumbs and the relax before the cover
  test. d65 (d58's args) and d66 (the crumbs early) give the same body (42,688 tris) and pokes, better than d58.
  `--collar-keep 0.09` (d68, with the relax) kept 212 more body tris and 11 points at rest: not used.
- **The proof's side from every tied face** (M2j): `clothes_proof.py` measures a body point's side with the dress's
  `clothes_side.ClothSide` (`--tie-side`, default 1). On d65 it moved Jog and Strafe to 0 and Sprint and Jump_Start
  to 19 and 12 mm (one or two right-calf points at z 0.162); d67's 24 to 27 mm calf points stayed, so they were the
  fold's inward faces, not a tie.
- **The built cuff ring** (M2j, `--cuff-ring z_top,height,thick,clear,stations[,lap[,most]]`, `clothes_top.cuff_ring`):
  each turn-up a closed rolled band (`clothes_shell.cuff_profile`, 10 points per station) in place of Meshy's folded
  band. The Meshy leg is bisected on one plane lap under z_top; its outer wall lies thick out of the leg's cloth just
  above (pushed out of the shoe by at most `most`), its opening narrows to `clear` off the ankle, its weights are the
  cut leg's nearest four vertices', and `plain_denim` tints it (the box's cut height at z_top). `--ankle-top z` cuts the
  kept ankle skin on one level plane inside it. d70 (`0.165,0.05,0.008,0.003,32,0.008`, `--ankle-top 0.128`): clean
  rings, 0 pokes in every clip, but 60,558 triangles; d71 at 24 stations is the cap's build. The teal ankle between the
  ring and the shoe still shows the collar's shards in Jog: the ring's bottom should reach the collar next.
- **The ring down to the collar** (M2k): d71's ring bottom (z 0.115) floated 1 to 1.5 cm over the sneaker's collar
  (rim top 0.099, heel rim 0.105). d73 lowers the whole ring, level: `--cuff-ring 0.158,0.062,...` (bottom 0.096),
  the plain box's cut at 0.159, `--ankle-top 0.120`; 59,847 triangles, 0 pokes in every clip. At Jog 0.3 s the
  planted foot's ring meets its collar with no teal; the lifted, pointed foot still shows a small teal sliver at
  the back of its collar. A per-angle bottom (following the collar) is the next step if that sliver matters.
- **The back bib's stand-off** (M2k probe, `back bib` report `off_body_worst_x_z_mm`): the 23.6 mm is the row under
  the band at the spine (z 0.922, hidden by the band); the next are the V's tip over the spine groove (21 to 22 mm at
  z 1.09 to 1.10, the row's quadratic bridging the groove between the shoulder blades) and a top corner (20 mm). The
  panel's edges fold `strap_lip` in, so the visible gap at the V is about 1 cm. Not changed.
- **The back straps' kink** (M2k): in Jog the straps bent in an S just over the back bib's top corners, where
  `back_join` hands them from the panel's spine-chain weights to the body's shoulder weights over only `blend` 3 cm.
  `--back-join 0.14,0.002` eases that over 14 cm (14 rows a side instead of 4): at Jog 0.3 s the left strap runs
  straight and the right one bends softly (d75); 0.08 (d74) is between. d76 = d73's ring with the 14 cm ease.
- **The back bib on the legs' own denim** (M2l): d76's back bib, on the straps' plain rectangle with a 1.35 gain,
  rendered lighter and bluer than the legs (High look, back view: bib sRGB about 53/80/107 against the legs'
  46/63/82) and smooth, a plastic patch at game distance. A `--plain` box's 10th value 1 now takes the diffuse and
  roughness from `--plain-src`, the garment's own texels; `auto[,w,h]` (default 96 x 160) picks the plainest
  rectangle wholly inside the UV islands (`clothes_texture.clean_rect`). A rectangle read off the GLB's map does not
  do: that map is filled between the islands, and d77's hand-picked leg rectangle lay partly outside them (black
  wedges on the bib). The normal map stays the plain rectangle's twill: the legs' normals carry their folds. With
  gain 1 the bib measures as the legs (d77: 45/61/80).
- **The cuff on its leg's own axis** (M2l): the cuff ring's plain texels were laid on a cylinder round the waist's
  axis, so each cuff's front and back shared texels and its sides stretched: a smooth sky-blue tube. A `--plain`
  box's 11th value 1 lays each region on its own vertical axis instead, the seam on the leg's inner side (a face
  across it unwrapped by `clothes_shell.seam_unwrap`). The ring is now thinner and higher, over a strip of ankle as on
  the concept: `--cuff-ring 0.172,0.046,0.004,0.003,24,0.008,0.004` (bottom 0.126, the collar's top 0.099 to
  0.105), `--ankle-top 0.140`, the box's cut 0.172, `--light-denim 0.58,0.64,0.72` (greyer) and
  `--cuff-fold 0.003,0.6` (the box's rows 3 mm under its cut darkened: the roll's fold line).
- **The off-body report after the lip** (M2l): `off_body_mm_min_max` and `off_body_worst_x_z_mm` now measure the
  panel as built, its edge folded `strap_lip` in (d78: 2.0 to 23.6 mm; the V's tip 18.9 mm).
- **The shoe collar** (E1, E1b): the sneaker's rim and collar come from every vertex with any Foot, Toes or LowerLeg
  weight under 0.2 m (`sneaker_geom` `SECT_Z`); the dress keeps the ankle's skin from the opening's nearest rim point
  up to `--ankle-keep` (40 mm) over it (`clothes_fit_geom.ankle_kept`): the cover rays' tilted rays met the trousers'
  hem above and the shoe below and cut ragged holes into the open ankle over the collar (the teal shards). The
  dress's `collar_probe` counts kept skin under the rim (within 20 mm) outside the shoe's surface, at rest only
  (it read 0 while the shards showed: they come in the clips' pose). The shards' cause: the shin's tilt in Idle and
  Crouch carries the ankle skin under the collar (weighted to LowerLeg) out through the rigid shoe; `--ankle-ride`
  hands that skin's LowerLeg weight to the Foot from 5 mm under the rim's nearest point down, easing out over 30 mm
  above (`clothes_fit_geom.ankle_ride`). That did not move the shards: they are static.
- **The collar's clean cut** (E1c): the shards' real cause was the rim itself. The shoe's boundary includes the
  eyelets' and laces' small islands (z 0.083 to 0.109 on the instep), so the "rim" the cut measured against sat on
  the instep, and the per-face cut left a staircase of skin over and outside the collar. Now the opening's rim is the
  boundary of each shoe's main island (100 vertices or more, over 0.05 m, the points 25 mm under the median dropped);
  `clothes_fit_geom.rim_plane` fits a plane through it (least squares, so it tilts with the collar) and lowers it
  `--collar-cut` (12 mm) under its lowest point; the ankle's faces between that plane and the rim's top come back
  (only where no shoe face lies over them, so not the instep under the vamp, and up to `--collar-over`, 15 mm, over the top: the notch the old rim cut), the skin
  under the plane near the shoe is bisected away, and each kept vertex under its nearest rim point whose ray outward
  across the floor meets no shoe face (`outside_shell`: outside the outer shell) is pulled back toward the rim's
  centre, `--collar-clear` (3 mm) inside the innermost wall on its way (`pull_in`). `dress.json` reports `collar`
  (the planes, faces back, pulled) and `collar_shell_probe` (that count after the pull: 0 on both). The old
  `collar_probe` (the nearest face's normal) still counts the lining's side and reads high; do not trust it.
- **The collar in motion** (E1d): E1c's main-island rim fed only the plane; every other rim rule (the shoe's top,
  `local_rim`, `through_shoe`, `ankle_kept`, `--ankle-ride`) still used the whole boundary with the laces' points over
  the instep, and cut holes into the ankle's front (the dark teal blocks: the leg's far side seen through them). Now
  all of them use the main island's rim. The faces that come back are the ankle's column: inside the opening's outline
  across the floor (`clothes_fit_geom.in_opening`, the rim's radius round its centre interpolated by angle, grown
  `--collar-grow`, 10 mm), up to `--collar-keep` (60 mm) over the rim's top, each face with a vertex over the plane (so
  the faces crossing it come back and the bisect cuts them: no holes at the ring); the rule "no shoe face over it" is
  gone. The foot's skin outside the outline, under its nearest rim point and with the shoe over it or within
  `--collar-vamp` (30 mm) under it, is the instep and toes under the vamp: it goes (`collar.vamp_faces_removed`; the
  teal patches through the vamp). `collar.faces_cut` reads 0 by construction (each crossing face splits in two and
  loses its lower half). Where the ankle is wider than the opening, the kept skin under each vertex's nearest rim
  point hung over the collar as teeth: every such vertex is tucked inside the outline, `--collar-clear` (3 mm) in,
  easing out over `--collar-band` (10 mm) above the rim (`clothes_fit_geom.collar_clamp`; `collar.tucked_in`: 83 and
  78 vertices, at most 12.7 and 28 mm on A and B).
- **The collar by one plane** (E1e, the route that worked; it replaces E1c's pull-in and E1d's column, vamp and
  tuck): the bind pose (no clip) showed E1d's teeth over the collar exactly as in Idle, so they were geometry, not
  skinning. Every rule that deletes faces one by one near a visible edge (the cover rays, in-shoe, through-wall,
  column, vamp) leaves a sawtooth there, and bringing faces back or tucking vertices afterwards never smooths it. Now
  the plane alone decides the leg's and foot's skin near each shoe (up to `--collar-keep`, 60 mm, over the rim's top,
  within the rim's reach): a face goes only when it lies wholly under the plane (`--collar-cut`, 12 mm under the rim's
  lowest point); every face with a vertex over it stays and the bisect cuts the crossing ones into one edge loop
  inside the shoe (`collar.faces_back`, `faces_under_plane_removed`). The kept skin is then **shrunk toward the leg's
  own axis** (the LowerLeg bone's line, extended down): a ray from the axis out toward each vertex at its own height
  finds the shoe's inner wall, and the vertex comes in to `--collar-clear` (3 mm) inside it, easing out over
  `--collar-band` (15 mm) over its nearest rim point (`clothes_fit_geom.collar_clamp`; over the rim the wall is
  measured just under the rim, so no step). Skin with the shoe over it, or within 12 mm under it (the instep under or
  2 mm through the vamp, where the nearest rim point is the throat's low slot), counts as under the rim: without that
  the instep showed as teal patches through the vamp. That skin, up to `--collar-weights` (30 mm) over the rim, takes
  its nearest shoe vertex's weights, blended back to its own over that band (`clothes_fit_geom.mix_rows`), so the
  ankle and the shoe move as one; E1b's `--ankle-ride` is off with the plane. `collar.shrunk` (d14: 253 and 159
  vertices, at most 113 and 29 mm, the most on A's instep) and `collar.shoe_weights` report it.
- **The bib's top by a lower plane** (E1f): the bind pose (`tools/out/dress/e1f/fit_bind.py`, textured and by
  object) showed the ragged top edge and the white and dark slits beside the bib as geometry: Meshy's layered top hem,
  about 30 mm deep, opened by the old plane at 1.195 m (A's reference) into crumpled folds with the shirt baked into
  their texels. The plane now sits under that hem, on the stitched band's top: `--bib 0.105,1.166` and
  `clothes_shell.body_planes`' reference bib top 1.166 (mapped per body with `--planes bones`); the straps' fronts and
  buckles follow it. One cut, no peel.
- **The seat re-laid on the body** (E1f): the dark shards at the back waist were bind-pose geometry too: B's female
  fit folds the cloth over her seat into flared flaps round the back pockets (open edges 70 to 140 mm under the
  waist, outer layers 6 mm and more off the cloth under them). `clothes_top.seat_wrap` (before the cut) puts each
  garment vertex behind the side seams (y over -0.02), from 10 mm under the waist down `--seat-wrap` (0.24 m), on its
  nearest body point plus a smoothed offset (its own, clamped to `--seat-clear` 4 to 30 mm, `--seat-smooth` rounds),
  and relaxes the cloth along the body only round its folds (faces turned off the body's normal by more than
  `--seat-fold`, two rings out; `--seat-relax` rounds): relaxing smooth cloth smeared its texture (d15).
  `clothes_fit_geom.seat_weight` eases it out over 30 mm at every border and where the cloth bridges (over 60 to
  90 mm off the body: the crotch). No face goes and no vertex is added, so the weights stay the fit's.
- **The seat's texture** (E1g): the E1f relax over every fold slid Meshy's relief along the body and smeared the
  stitches into wavy streaks. Now a seat vertex off the relax moves along the body's normal only, so its UVs keep their
  layout. The chameleon's back seat is no longer re-laid at all (its d14 look); `--seat-y0 -1 --seat-y1 -0.03
  --seat-relax 0` re-lays only its front, along the normal. The axolotl (`--seat-y0 -0.08 --seat-fold 0.0`) still
  needs the relax: her flared pocket flaps are closed folds, not open edges, so gating the relax to open edges'
  rings (`--seat-open-rings`, d17 and d18) brought the flaps back; with the relax (d20, `-0.3` in d20b alike) the
  flaps are gone but the pockets' stitched texels stay stretched over the seat. A clean seat needs new texels there
  (a re-projected bake), not another vertex rule.
- **Plain denim texels** (E1h): Meshy's layered side opening under the hips' side buttons is baked as a light,
  streaked, crumpled patch (a dark stain on the hip at game distance, a chrome-like hollow in Crouch), and the
  axolotl's re-laid seat and front pockets carry stretched stitch texels. These are texel faults, so
  `clothes_top.plain_denim` (after the straps) gives them new texels without moving a vertex: each `--plain` box
  (`x0,x1,y0,y1,z0,z1` for |x|, bind pose; `;` between boxes) on each side is a region of denim faces (the straps'
  and band's patch and the bronze left out), re-laid in UV on a vertical cylinder round the waist's axis
  (`--band-axis-y`; `clothes_shell.cyl_coords`) at the garment's median texel density (about 1,100 texels per metre;
  `--plain-density` scales it). The regions of one (tint, cut, gain, source) group share one free window of the maps
  filled with the straps' plain denim rectangle (`--strap-uv`) repeated mirrored (`clothes_shell.mirror_tile`; the normal map's x or y turned over in a
  mirrored copy), in the diffuse, roughness and normal maps alike; with no window free the density steps down by
  15% up to three times. The boxes: the chameleon `0.11,0.25,-0.07,0.09,0.74,0.99` (the hip sides); the axolotl
  the hip sides `0.11,0.25,-0.04,0.05,0.72,0.975`, the seat `0,0.25,0.05,0.25,0.72,0.975` and the front pockets
  `0.05,0.25,-0.25,-0.04,0.80,0.975`. Her back and front pockets' outlines go with it: they could not be kept clean.
  The Meshy side buttons become denim bumps; the side's crumpled geometry stays. The mirrored repeat of the small
  plain rectangle (44 x 93 texels) shows as a faint zigzag moire over her seat in Godot (Crouch, d23): a larger plain
  source would remove it.
- **The bib pocket's white holes in Jog** (E1h, not fixed): two white teardrops at the chameleon's bib pocket bottom
  in Godot's Jog at 0 s. `--shell-hide-above` (the top's faces under the panels may go from that height over the
  waist, not only above `--shell-full`) was tried in d23 and changed nothing there, while it raised the axolotl's
  body pokes in Jog, Sprint and Strafe (2 to 8 vertices, up to 6 mm); it stays off. The white is most likely the
  background through open holes in Meshy's layered pocket bottom, with the top and the body removed under the bib;
  `fill_holes` only works under the waist. Next: fill those loops above the waist, or keep the top under that spot.
- **Her bib flat, as on the concept** (E1i, the axolotl only; the chameleon's bib is not touched): her fit made the
  bib follow each breast, and its top (1.110 m) sat under her bust (apex about 1.15 m), so the denim cupped under the
  chest. The flat bib rule: the bib is a stiff panel that rests on the chest's most forward points and falls straight
  to the waistband; the shirt carries the chest's shape at its sides. `clothes_top.flat_bib` (after the cut, before
  the top and the straps; `--flat-bib blend,curve,radius,clear`, `--bib-raise dz,b0,b1`):
  - `--bib-raise` lifts everything over waist + b1 by dz and stretches the band waist + b0 to waist + b1; that band's
    texels are re-laid plain (a `--plain` box is added); the bib's top and the straps' fronts follow (`straps` turns
    its front angle until the front end is dz higher);
  - every bib vertex moves forward only, by the offset from the bib's smoothed surface (every layer's mean, so the
    pocket keeps its layer) to a cylinder `hull(z) + c x^2` (c fitted to the belly's rows with `curve < 0`); hull is
    the front hull (`clothes_shell.front_hull`) of the bib and of the body's front less `clear`: the taut line from
    the waistband over the bust; the move eases in over `blend` above the waist;
  - the moved vertices' weights blend toward their 3 cm row's mean of the body's weights under the panel.
  d27 (`--flat-bib 0.05,-1,0.02,0.014 --bib-raise 0.06,0.012,0.035`): bib top 1.170 m, c 4.7 1/m, hull from -0.129 m
  at the waist to -0.164 m at the bust. At rest and in the turnaround it reads as the concept's bib. Still wrong: in
  Jog its top folds down under the bust (the weights), the body pokes rose (Idle 4/3.1 mm, Jump_Start 5/8.1 mm against
  d23b's 0/0 and 1/3.6), and a teal patch shows at her left bib side at rest (the top's hidden faces, 51 against 38).
- **Her flat bib in motion** (E1i2): in Jog the bones pitch far (UpperChest about 38 degrees, Chest 27) and the body's
  front under the bib compresses (its front at 1.16 m drops 120 mm, at 0.96 m 28 mm). A panel weighted like that
  body, by the rows' means (d27) or bone by bone up to UpperChest (d28), squashes the same way and folds under the
  bust. The rule: a stiff panel rides one bone. `--bib-chain Hips,Spine,Chest` weights it by height alone
  (`clothes_shell.chain_row` over the bones' bind-pose mid heights, the same across its width, eased from the
  band's own weights over `blend`), so above Chest's mid (1.04 m) it is rigid with Chest. d29: flat in Jog, Crouch,
  Walk and Jump_Start. `--shell-hide 0.02` keeps the top under the stood-off bib (2 faces hidden, not 51): the teal
  patch and the chest pokes are gone (Idle 0/0). Her close-up cameras aim at the raised bib (`e1i2/frames.sh`).
- **Holes over the waist** (E1i2, off by default): `--fill-holes-above` lets `fill_holes` work up to that height
  over the waist and reports the loops it filled there. On the chameleon (d30) it filled two at the back and side,
  none at the bib pocket: the pocket's white holes are not small closed loops, so they stay open.
- **The hips' spikes** (E1g): `clothes_top.despike` moves a garment vertex under the waist that stands over
  `--despike` (15 mm) out of its neighbours' mean, along the body's normal, to that mean (`clothes_fit_geom.spike_out`;
  the axolotl's front-hip spike, d16).
- **Meshy's small holes** (E1g): `clothes_top.fill_holes` fills the garment's closed open-edge loops of at most
  `--fill-holes` (12) edges under the waist, each new corner with its vertex's UV from the cloth round it; loose bits
  of 4 faces or fewer there go first (the flood must cover a whole component: a partial one made pieces of large
  components look loose and opened 160 holes, d19).
- **The strap fronts' notch** (E1g): `clear_strap_fronts` first cuts along each strap front's side lines (half the
  strap less 2 mm) and its end, so the faces under the strap go to a straight edge.
- **The instep's clearance** (E1f): skin with the shoe over it is shrunk to `--collar-clear-under` (6 mm) inside the
  shoe's wall instead of `--collar-clear` (3 mm): the vamp's teal specks in motion.
- **The straps' back ends** (E1d): with `--planes bones` the straps sweep on past `--shell-strap-t`'s back angle until
  their back end lies `--strap-back-below` (32 mm) under the back panel's apex (`straps.back_angle_deg`); the shorter
  body B's straps met 50 mm over her apex (a flat bar of shirt and panel under their V). A's stay at 134 degrees.
- **The fit's strays** (E1b): garment vertices over `--stray` (80 mm) from the body go with their faces (two on A11
  made dark spikes out of the hips).
- **The proof's openings** (E1b): a body vertex "inside" by an opening's inward-folded lip whose nearest cloth point
  is that opening (the thumb's root 55 mm past the cuff) is left out like one by the opening.
- **The game's look** (E1b): `frames --look high` renders under `look_presets.json`'s High preset (AgX 0.9, the
  studio sky's ambient and reflections, SSAO, soft shadows, MSAA 4x, the approved lights); the default `studio` is
  the linear review light.

## Specs: a garment's numbers before its build (Gate 1, art #196)
Every garment is specified before it is built (the pipeline approved 2026-10-31: concept, spec and drawing, then the
build). `specs/<garment>_dims.toml` holds every size in cm on the body it is made for and as a ratio to that body's
landmarks (sole, ankle, knee, crotch, waist, bust, armpit, collarbone, shoulder_top; widths waist_w, hip_w, bust_w,
chest_w, thigh_w, knee_w, ankle_w ...), a tolerance per size, which concept view wins, the concept's own landmark
rows, and each part's behaviour (flat, bends, moves with which bones). `tools/blender/garment_spec.py` (plain Python)
loads it and refuses a file whose cm and ratio disagree by more than 0.1 cm; it also measures the landmarks on a rest
dump (`body_landmarks`: triangle-connected plane sections). `garment_spec_probe.py` (headless Blender, read only)
dumps a character's rest meshes and bones; `garment_drawing.py` draws one sheet per view (the concept | the spec over
the concept, placed by its landmark rows | the spec over a flat-shaded render of her body at 5 px/cm) and, with
`--build`, measures a dressed build against the spec (`spec_vs_<tag>.md/.json/.png`):

```
blender.run_script("garment_spec_probe.py", ["--blend", <char.blend>, "--out", <probe.json>])
cd tools/blender && $PYTHON_BIN garment_drawing.py --spec ../../specs/dungarees_dims.toml --body <char probe>
    --out DIR [--build <dressed probe> --dress <dress.json> --tag d79]
```

- **The dungarees** (`specs/dungarees_dims.toml`, on B13): bib top 119.95 cm (0.78 of her waist->collarbone, the
  concept's 336 px exactly), 22.0 wide at the top, 21.0 at the band; pocket 115.9-102.0, 14.5 wide; straps 3.8 wide,
  vertical at 9.5 cm from her centre, buckles at 118.0; waistband 99.8-95.8 (her waist; d79's at 93.3), 24.5 wide;
  side buttons 97.1; back panel top 118.7 (a shallow U between the straps, as on the concept), 24.1 / 21.7 wide;
  legs 18.65 / 13.0 / 11.5 at thigh, knee and turn-up; turn-up 17.8-23.3; a 6.7 cm bare ankle over the sneaker rim.
  The bib's lean is the taste point: (A) a rigid plane on the band and the bust peak leans 8.7 deg, its top 4.5 cm
  off her upper chest (d80-d82's board); (B, the spec's choice) straight across with one smooth side-view bend over
  the bust, the top edge 0.8 cm off the shirt. The d79 build is off in 14 of 21 measured sizes (bib top -8.9 cm,
  band -6.5, hem -5.2). Her rest is a T-pose: her armpit landmark is a T-pose armpit, higher than an A-pose one.

## Gate 2: the build's automatic checks and its review page (art #196)
The ADR `docs/decisions/2026-10-31-asset-pipeline-gates.md` lets no garment pass Gate 2 without these numbers. They are
general for any garment with a spec: the spec's `[gate2]` section (`specs/dungarees_dims.toml`) names the clips, the
parts, the joins, the flat and stiff parts, the stations and every tolerance; heights and boxes may name a measure
(the build's measured value of a spec size, else the spec's cm, else her landmark; `spec:NAME` always the spec's).

```
tools/run.sh frames <build.glb> --clips Walk,Jog_Fwd --video Walk,Jog_Fwd --compare '' --look high
    --video-camera 'torso@0,1.06,0~Chest/0.55/0' --out <raw>/.../video
tools/run.sh gate2 --spec specs/dungarees_dims.toml --body <undressed probe.json> --blend <build .blend>
    --dress <dress.json> --poke <clothes_proof poke.json> --video <raw>/.../video --out <raw>/.../gate2 --tag dNN
    [--probe <build probe.json>] [--motion <motion.json>]
```

- **Spec numbers** (`garment_drawing.measure_build`): every spec size on the build against its `tol_cm`. The
  hardware and the pocket are measured on the mesh (`garment_drawing.mesh_hardware`): a button is a connected piece of
  at most `hardware_max_verts` vertices and 3 cm across, its diameter the disc's (`garment_spec.disc_size`: the
  widest width across its thinnest direction); the buckle buttons sit in front over the band's top + 5 cm, the side
  buttons over 6 cm off the centre near the band's top; the pocket is a `*pocket*` material's triangles, else a
  piece on the bib's front. A part looked for and not there (d79's pocket is texture only; its bib ends under her
  bust, so no bust stand-off) is **absent**, a failure; a size with no measure written counts as unmeasured, and
  Gate 2 does not pass with either. `measure_build` still reads some sizes from `dress.json` (the cuff ring, the
  band's height, the back panel's outline): a new build route must write them or they must be measured on the mesh.
- **Silhouettes** (`garment_gate2.py`, plain Python): per view the build's garment as seen (z-buffered against her
  body, the shirt and the shoes), drawn at the concept's scale by her landmark rows (`garment_drawing.concept_map`; in
  front and back the legs moved onto the concept's leg lines, as the drawing does), against the concept's garment
  mask (`garment_gate2_geom.concept_mask`: blue over red and green, an opening of 4 rows that drops the shirt's navy
  stripes, a closing, the large pieces, the holes filled; `concept_mask_<view>.png`; a hand mask `mask_<view>` in
  `[gate2]` replaces it). The overlap is the intersection over union (`overlap_min` per view; the side view's over
  the trunk only, `overlap_z`, as the concept's side legs stride). `overlay_<view>.png`: green both, blue the concept
  only, red the build only. The stations' table: per station the concept's, the spec's and the build's cm and the
  error in mm against the spec (against the concept where the spec has no size), only where both pictures show the
  garment plainly (the concept's side arm hides the back at the bust; its bib is narrower than the spec's).
- **Motion** (`garment_motion.py`, headless Blender, every frame of each clip, measured from `reference_clip`'s first
  frame, the stand; from the T-pose rest every panel moves as the arms come down): the garment's pieces are classed as
  `strap` (over the collarbone with points in front and behind), `hardware` (at most 60 vertices) or `panel`; a part
  is those classes inside a box. Slip at a join is clothes_bibmove's (each moving vertex tied at rest to its nearest
  point on the other part, turned back by that part's best fit), flatness the largest distance from the part's own
  rest shape moved rigidly onto it (change from rest: lean B's drawn bend is the rest shape, only a new bend counts),
  stretch the edges' |length / rest - 1|, judged on the 95th percentile (the largest beside it: one torn edge). Pokes come from `clothes_proof.py`'s
  `poke.json` (`--poke`; run clothes_proof first).
- **The page** (`index.html` in OUT, with `gate2.json`, `numbers.png`): per view concept | the spec drawn over the
  concept | the build with the spec's lines at 5 px/cm (`garment_drawing.view_sheet` on the build's probe), the
  overlays, the tables, and the front close-up Walk and Jog videos (`frames --video-camera`, copied in as
  `closeup_<clip>.mp4`). The verdict is PASS only with every number measured and within tolerance and both videos.
