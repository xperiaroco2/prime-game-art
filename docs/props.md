# Props of the House map

Two procedural prop sets share `props/` and this page: the task-station props (`props/tasks.toml`, the `props`
command, art #82) and the dressing library (`props/library.toml`, the `props-library` command, art #87). The
library's `tools/blender/prop_lib.py` is meant as the shared prop helper (materials, paint by role, pivot, UV2,
collision, one GLB per prop); the task props keep their own `props_task.py` for now.

## World look rules

The House's look is C2-white from the kitchen pilot (ADR `docs/decisions/2026-10-13-house-world-look.md`, #143).
Every room's props follow these rules; the numbers are data in `props/library.toml` and `props-library` checks them.

1. **Not plasticine, never worn.** Only the characters are plasticine. The world is a present-day, well-made home:
   no wear, chips, dirt or grime. Richness comes from parts, materials and density, not damage.
2. **Real parts, one style per room** (`[style]`): bodies, fronts, plinths, tops and hardware are separate parts;
   bevels of 10 mm on bodies and slabs and 3 mm on fronts and small parts; one bar handle (7 mm round bar on two
   30 mm standoffs), one plinth (0.1 m, set back 75 mm) and one worktop line (0.9 m, 30 mm thick) per room; a soft
   shade toward the floor (x0.82 at the floor, none from 0.25 m up).
3. **Materials: the fine pack.** Opaque paints sit on one shared material, `fine`, each role on a layer (`[fine]`):
   textured wood fronts (Wood092), worktop wood (Wood049), stone (Concrete034) and tile (Tiles107); flat enamel,
   warm steel, chrome, dark gloss and paint; the living room's soft goods (#150): textured fabric (Fabric036, linen
   upholstery), weave (Fabric061, cushions and throws) and carpet (Carpet016, rugs). Glass is `glass_tint`. A new
   paint is a role with a `layer` and a hex; a new texture is a `[fine]` layer from a recorded CC0 source, appended
   at the end so the built GLBs keep their layer indices (at most 8 textured layers: a textured layer's slot is its
   place among the textured ones; `fine_d.png` and `fine_d1.png` hold four slots' detail each, `fine_n0.png` to
   `fine_n3.png` two slots' normals each, and a build writes only the files its slots need). A prop has at most two
   surfaces (fine, glass).
4. **Shared textures, two tiers.** The GLB has no textures; Godot maps `kit_fine` to one ShaderMaterial with one
   texture set per tier (High 1024 px, Low 512 px, from the same sources), VRAM-compressed on import.
5. **Classes.** `hero` (1,200 to 4,000 triangles) for the pieces players look at up close (appliances, a room's
   centre piece); `room` (400 to 1,500) for the rest of the furniture; `clutter` for the small things.
6. **Base and detail layers** (`layer`, default by class in `[layers]`): the base layer alone makes the room read
   clean on Low; small props and fine decor are `detail` (clutter by default), which High and Ultra add. A detail
   prop has no collider.
7. **Shared builders** (`prop_geom.py`, "the world look"): `Style` (from `[style]`), `front` (a bevelled door or
   drawer front, raised panel or framed glass, with its handle and hinges), `bar_handle`, `plinth`, `worktop`,
   `backsplash`, `burner` and `burner_grate`, `tap`, `rslab` (soft vertical edges). Fronts and handles stay inside
   `size_m`; a builder may name its own collider boxes (the stove's body and hood leave the gap over the hob open).
   The kitchen's `kitchen_counter` (with `sink`), `kitchen_upper`, `stove`, `fridge` and the backsplash runs
   (`backsplash_l`, `backsplash_r`: shape `backsplash`, wall pivot, no collider) are built from them; so are the
   task props `assembly_island` and `order_board` (`props/tasks.toml`, `look = "fine"`). The living room's pieces
   (#150) add upholstered seats with cushions (`sofa`, its armchair variant), shelving with books (`bookcase`), a
   mantel surround with a stone hearth (`mantel_fireplace`), a TV unit with its TV (`tv_unit`), `coffee_table`,
   `sideboard` (the sideboard and the dresser), `side_table` and `carpet_rug`, and six clutter-class detail props for
   the living room's detail layer: `living_tray`, `magazine_fan`, `mantel_clock`, `standing_frame`, `throw_basket`,
   `candle_pair` (12 to 400 triangles each, no collider). Round 2 adds 16 more: five pieces of wall art drawn
   procedurally (`art_abstract`, `art_city`, `art_burger`, `art_photos`, `art_score`), ten detail props (`board_games`,
   `candle_jars`, `coffee_books`, `deco_bowl`, `deco_vase`, `game_console`, `laptop`, `side_lamp`, `slippers`,
   `table_plant`) and `floor_plant` (its pot the only collider): 22 new living-room props and 10 rebuilt ones.
   The dining room (#153) adds `dining_chair` (an oak frame with an upholstered seat; two collider boxes, seat and
   back), `pendant_trio` (three shades on a ceiling bar; the `chandelier` id, one light anchor), `display_cabinet`
   (hero: glazed upper doors over a closed base; one collider box), the slate `dining_rug` (`carpet_rug`, paint
   `carpet_slate`), the base-layer still life `art_still_life` and the detail-layer `art_delivery` and
   `art_gazebo` (`framed_art` kinds `still_life`, `delivery`, `gazebo`: a delivery route on the House's street
   map and a photo strip from the gazebo), and the
   detail props `place_setting`, `serving_board`, `fruit_dish`, `tulip_vase`, `bottle_rack` (shape `wine_rack`;
   dressing class for its six bottles), `homework` and `mail_stack`; the task prop `dining_table` is the oiled-oak
   `table` on tapered legs (`look = "fine"`, `props_task.build_table_fine`). `tools/tests/test_props_dining.py`
   checks their sizes, pivots, budgets and colliders and that the table-top items stand on the top and keep a
   0.6 m band round the `DiningTable` station (x 6.0 m, the delivery chain's drop-off) clear.
   The hallway (#156) adds `hall_console` (an oak console with two drawers over a basket shelf; one collider box),
   `hall_mirror` (an arched mirror; its pane the gloss-layer paint `mirror_glass`), `coat_hooks` (a wall rail with coats
   and a scarf; one box collider), `hall_bench` (a seat pad, a shoe shelf with shoes), the navy `hall_runner`
   (`carpet_rug`, paint `carpet_navy`), `umbrella_stand` and the base-layer `art_blueprint` (`framed_art` kind
   `blueprint`: the generator's blueprint), and the detail props `hall_doormat` (coir), `key_bowl`, `parcels` (kraft
   boxes with tape), `shoe_pairs` (`_shoe_pair`), `sports_bag`, `wall_calendar` (kind `calendar`) and `photo_row` (three
   small frames: family portraits of plasticine people and holiday photos, `_art` kind `family`; dressing class);
   `framed_art` draws through the shared `_framed` helper. The far wall's large piece is `gallery_wall` (six frames
   hung salon-style from the `GALLERY` table, class `room` for its triangles, no collider).
   `tools/tests/test_props_hallway.py` checks their sizes, pivots, budgets and colliders, that the console's things
   stand on its top without touching, that the room has no station, spawn or task prop (by design; a new one fails the
   test until the dressing is checked against it), that the dressing keeps 0.3 m from every station and spawn in the
   room (read from `layouts/house/ground.toml` and `props/tasks.toml`) and that the fronts of its four doors (1.4 m by
   0.8 m) stay clear.
   The ground floor's small rooms (#158) add the WC's `wc_toilet` (a close-coupled porcelain toilet), `wc_vanity`
   (oak drawers, a stone top, a sit-on basin and the pillar `tap`), `mirror_cabinet`, `washer` and `tumble_dryer`
   (shape `washing_machine`), the tiled lower wall `wc_tiles` (shape `backsplash`, class room on the base layer,
   like the kitchen's backsplash) and the joke print `art_wash` (`framed_art` kind `wash`: a plasticine person in
   suds, rated five stars), with the
   detail props `towel_ring`, `roll_holder`, `pedal_bin`, `toilet_brush` and `reed_diffuser`; the pantry's
   `pantry_shelf` and `pantry_shelf_buns` (hero: one `pantry_shelf` builder stocked shelf by shelf from `stock`,
   `_stock`'s jars, tins, cereal boxes, sauces, bags of burger buns and baskets of potatoes and onions), `veg_rack`,
   `drink_crates`, `step_stool` and `broom_set`; and the stairs' `stair_runner` (a navy runner over every tread and
   riser of the kit's half flight, its numbers from `kit_geom.stair_numbers`; one per flight), `stair_gallery` (five
   family photos stepping up at the flight's pitch, `STAIR_FRAMES`) and `landing_plant` (no collider: the landing
   stays walkable). The three rooms are hand-placed (their clutter rules are empty) and reuse the hallway's console,
   mirror, bench and runner by the stairs. `tools/tests/test_props_small_rooms.py` checks the new props' sizes,
   pivots, budgets and colliders, that the runner fits the kit's flight, that the rooms have no station, spawn or
   task prop today and the dressing keeps 0.3 m from any, and that their doors stay clear.
   The upper floor's landing and bathroom (#162, library v7): `bath_tub` (a built-in bath with a slide-rail shower,
   a hinged `glass_tint` screen, bottles and a rubber duck; its collider is the tub only), `bath_vanity` (the WC's
   vanity builder at 0.9 m), `towel_rail` (a heated ladder rail with two towels), `bath_shelf` (an open oak unit with
   towels, a basket, bottles and a plant), `bath_mat`, the white tiled walls `bath_tiles`, `bath_tiles_short` and
   `bath_tiles_shower` (2 m behind the shower; layer base like `wc_tiles`), the joke print `art_bubbles` and the
   `landing_runner` (terracotta wool with a deep rust border in the same tone and a soft square motif down the
   middle, `carpet_rug`'s `motif`: never high-contrast lines along its 8.5 m, round 2). Both rooms are hand-placed (their clutter rules are empty) and reuse the hallway's
   consoles, bench and lamps, the living room's bookcases and plants and the WC's toilet, mirror cabinet and detail
   layer. `tools/tests/test_props_upper_rooms.py` checks the new props as above, the stations and spawns (none
   today), the doors, the attic ladder's and the stairs' walk ways, each room's prop count against its count before
   the pass and that the `Name` label sits in no piece.
   The upper floor's bedroom and guest room (#164, library v9): `bedroom_bed` (`made_bed`: an oak frame, a padded
   linen headboard, white bedding, a duvet, scatter cushions and a throw) and `guest_bed` (the same builder as a
   single bed with an oak headboard), `bedroom_wardrobe` and `guest_wardrobe` (`wardrobe_modern`: white doors, an
   oak plinth and top, the bedroom's with a mirror door), `bedside_table` and its detail-layer `bedside_set` (a glass
   of water, a phone on its cable, a paperback), `dresser_set` and `dresser_mirror`, `curtains` (floor-length on a
   black rod, one per window), `bedroom_rug` and `guest_rug`, `bed_bench`, and the guest's `suitcase`, `towel_stack`,
   `storage_boxes` and `clothes_rail`. Both rooms are hand-placed (their clutter rules are empty), as many props as
   before; `double_bed`, `single_bed` and `nightstand` are no longer placed. `test_props_upper_rooms.py` covers them
   as it covers the landing and the bathroom (the spawns Circle07 and Circle09 keep 0.3 m clear).
   The upper floor's kids' room and study (#166, library v10): the kids' room's `kids_bed` (`made_bed` with `spots`:
   a single oak bed, a starry navy duvet, a folded yellow blanket), `kids_wardrobe` (`wardrobe_modern`, two white
   doors), `kids_bookcase` (white shelves of books and toys), `toy_cubby` (a low cube unit with coloured bins and
   books), `play_rug` (a teal play mat with a yellow road border), the wall art `art_rocket`, `art_dino` and
   `art_drawing` (`framed_art`'s motifs `rocket`, `dino`, `drawing`: a child's burger drawing) and the detail-layer
   `toy_set` (a toy rocket, a truck and a ball); the study's `study_bookcase` (an oak bookcase full of books over a
   cupboard), `study_rug` (terracotta, a cream border), `pin_board` (a cork board with the generator's blueprint and
   a delivery schedule), `monitor_set` (a monitor, keyboard, mouse and a mug) and `art_certificate` (`framed_art`'s
   `certificate`). Both rooms are hand-placed (their clutter rules are empty), never emptier than before (65 and 64
   props, main 64 and 63); `bunk_bed`, `wardrobe` and `laundry_pile` are no longer placed. `test_props_upper_rooms.py`
   covers them (the spawns Circle08 and Circle10 and the Printer station's points keep 0.3 m clear; the task props
   boxed from `props/tasks.toml`; the `Name` label in no piece and on no light fixture).
   The attic (#168, library v11), a well-kept family attic: `attic_shelving` and `attic_shelving_b`
   (`storage_shelving`: steel shelving loaded with labelled boxes and crates), `storage_box` (`lidded_box`, a labelled
   cardboard box) and `storage_crate` (`plastic_tub`, a lidded plastic crate) in place of the placeholder boxes and
   crates, `sheeted_sofa` and `sheeted_dresser` (`sheeted_form`: furniture under dust sheets), `leaning_frames`
   (framed pictures leaning on the knee wall), `holiday_decor` (a boxed tree and garlands), `rocking_horse`,
   `mannequin` (`dress_form`; both were hero-class skips before), `sports_kit`, and the game's own world:
   `burger_sign` (signage kept from a burger stall), `delivery_bag` (a retired delivery bag) and `generator_part`;
   `old_wardrobe` (now `wardrobe_modern`, white), `sheeted_furniture`, `old_bicycle` (`city_bike`) and `trunk` are
   rebuilt in the present-day look. The pieces are placed by the attic's data
   (`layouts/house/dressing/attic_roof/attic.toml`, 63 items, main 44); the twelve hiding spots, the pick-ups and the
   clear areas stay. `tools/tests/test_props_attic.py` checks the pieces' size against `size_m`, pivot, budget and
   collider, the spots, stations and clear areas, the item count and the `Name` label.
   The basement's storage room, darkroom and corridor (#170, library v12) are functional, not homely: clean,
   well-organised, present-day working rooms on the kit's concrete under bright work lights (never derelict, wet or
   creepy), the fun from the game's own world. The storage: `store_shelving` and `store_shelving_b` (steel shelving
   with labelled crates, boxes and the burger kitchen's stock), `bread_rack` (the buns' rack by the bun shelf),
   `loaded_pallet` (a wrapped delivery pallet) with its `pallet_jack`, `store_workbench`, `step_ladder`, `hand_trolley`
   (the delivery trolley), the floor markings `floor_bay`, `floor_lane` and `floor_hatch` (flat paint, no collider),
   the signs `aisle_sign_1` to `aisle_sign_3`, `sign_staff`, `sign_buns`, `sign_meat`, `sign_wine`, `sign_parts`,
   `sign_deliveries` and `sign_way_out`, and the detail-layer `clipboard` (delivery notes); its twelve bare bulbs are
   `fluorescent_tube` fixtures now. The darkroom: `lab_sink`, `chem_shelf` (chemicals and paper boxes), `light_table`
   (a fixture with a light anchor), `print_line` and `print_line_b` (drying lines of clipped party and gazebo prints)
   and `sign_darkroom`, beside main's enlargers, tray tables, safelights and PhotoBoard. The corridor: `rubber_runner`
   (rubber matting), `work_hooks` (work jackets on hooks), `fire_extinguisher` and `fuse_box`. The three rooms are
   hand-placed (`layouts/house/dressing/{storage,darkroom,corridor}.toml`; their clutter rules are empty), never
   emptier than before (157, 93 and 49 props, main 155, 92 and 49); flat floor markings and wall signs are
   dressing, never clutter. `tools/tests/test_props_basement.py` checks the pieces' size against `size_m`, pivot,
   budget and collider, 0.3 m around every station and spawn, the task props, the doors' openings, the counts and
   the `Name` label (in no piece and on no light fixture).
   The plant rooms, the passage and the darkroom's island (#172, library v13) finish the basement in the same
   rules. The generator hall keeps the Generator and its station point clear inside `floor_gen_zone` (yellow and
   black keep-clear blocks); round it `cable_tray` runs and `isolator`s on the walls, the `control_desk` (three
   screens, a phone, a logbook), `drum_bund` and `drum_bund_b` (drums on yellow spill bunds), `fire_point`
   (extinguishers, a fire blanket, a sand bucket), `tool_chest`, `parts_shelving` (the generator's spares) and
   `gen_log` (the daily check board with a burger doodle). The boiler room: `wall_boiler`, `hw_cylinder`,
   `insulated_pipes`, `valve_panel`, `expansion_vessel`, `water_softener` and `mop_sink`. The pump room: `pump_set`
   and `pump_set_b` on plinths, `sump_cover`, `wall_hose_reel` and `pump_chart`. The switch room: `elec_cabinet`,
   `elec_cabinet_b`, `meter_panel`, `switch_mat`, `first_aid_box` and `lectern` (the logbook). The darkroom's island:
   `dev_bench` (trays, tongs, a timer) and `cutting_table` (a trimmer and party prints) with stools. The signs
   `sign_ear`, `sign_volt`, `sign_no_smoking`, `sign_generator`, `sign_plant`, `sign_first_aid`, `sign_boiler`,
   `sign_pump` and `sign_switch` are clutter, the detail layer, so the base layer reads clean on Low. The boiler
   room's and the switch room's bare bulbs are `fluorescent_tube` fixtures now. The six rooms are hand-placed
   (`layouts/house/dressing/{generator_hall,boiler_room,pump_room,switch_room,passage,darkroom}.toml`; the clutter
   rules of the five plant rooms are empty), never emptier than before (142, 107, 72, 60, 46 and 99 props, main 140,
   105, 71, 60, 45 and 93), and nothing derelict stays (no pipe runs, jerrycans, barrels, crates, cardboard boxes or
   metal shelving). `tools/tests/test_props_basement.py` checks all eight rooms the same way.
   **The garage** (#79, package P6, library v14; `layouts/house/dressing/garage.toml`). The car and its lift are
   separate pieces so the game can drop the car: `garage_car` (a present-day five-door hatchback, no badge, hero,
   `car_body` enamel blue; two collider boxes: the body from the sills at 0.16 m and the cabin), `lift_posts`
   (static: two posts, the power unit, the floor cover plate) and `lift_arms` (the two carriages and four swing
   arms, the pads' tops at the sills); the game raises `lift_arms` and `garage_car` together by 1.24 m (the sills
   from 0.16 m to the car repair ADR's 1.4 m, RD2). `lift_panel` (the control pedestal) stands 0.25 m in front of
   the LiftPanel marker; its blind side is a closed-back `tyre_rack` and two `steel_cupboard`s between it and the
   car. `part_picture` is the wall frame the game draws the needed part on (`prop_geom.part_surface`). The dressing:
   `pegboard_tools`, `air_compressor`, `garden_tool_rack`, `floor_lift_zone` and the stock `store_shelving`,
   `storage_boxes`, `old_bicycle` (the sage city bike), `fridge`, `tool_chest`, `parts_shelving`, `drum_bund_b`,
   `wall_hose_reel`, `fire_point`; the light is lights.toml's six fluorescent tubes. `tools/tests/test_props_garage.py`
   checks the pieces' size, pivot, budget and colliders, the car/lift separation, the stations and spawns clear,
   that the dressing's `blocks` are the lift's real colliders, and casts rays from the panel's eye points to the
   space under the raised car (none may reach it).
8. **Route.** Hard-surface props are code (the shared builders, `prop_geom.py`'s `Style`). Meshy only for organic
   one-offs (food, soft goods, plants) at a hero budget, as a recorded batch (`docs/meshy.md`).

## Procedural props: the House map's task stations

The House map (request #73) needs props where the five task chains happen (design doc §6; the plan's
`inventory.md` §7) and a few room-defining pieces no pack has. Art #82 builds them as repo code in the House kit's
way (`docs/kit.md`): a spec (`props/tasks.toml`), a pure-Python geometry module (`tools/blender/props_task.py`), a
headless Blender builder (`props_task_build.py`, which reuses the kit's `kit_build.py` for objects, materials and the
export) and the `props` command. The GLBs stay in the raw folder (`D:/prime-art-raw/props/task/v3/`: v2 with #82's
19 task-chain props rebuilt over it; v2 is v1 with #153's dining table rebuilt over it) until the
engineer approves the look; then they come into the repo with their manifests.

**The task props in the world look (#82, task v3).** Every task-chain prop (the five chains' 22 props) is built
on the dressing library's fine pack (`look = "fine"`); the 12 room-defining props (boiler, pump, water_tank,
switchboard, cable_drum, enlarger, tray_table, toy_chest, utility_pole, birdbath, bulkhead_stairs, music_speaker)
keep the kit paint. `tools/blender/props_task_fine.py` holds the fine builders (`FINE_BUILDERS`): the types in
`RECOLOURED` (box_stack, wine_rack, bun_shelf, parts_shelf with labels or tags; potting_bench, workbench,
chest_freezer, grill, herb_bed, switch, printer) keep their kit geometry and swap every kit paint for its fine paint
through `props/tasks.toml`'s `[fine_paint]` map (old paint -> fine paint, the fine paints in `props/library.toml`);
the generator (a canopy genset), the computer (a flat monitor) and the screen and cork boards have builders of their
own, the chalk board stays `props_task.build_board_fine`. `check_spec` and `check_prop` refuse a fine prop with a paint
off the fine pack. States: each wall switch and the generator carry two state meshes in one GLB (`<id>_on` with
`signal_green`, `<id>_off` with `signal_red`; the generator's a status bar and a beacon, `nodes = ["on", "off"]`); the
game shows one and hides the other. The printer keeps `photo_printer_photo`, the freezer and the grill their `_lid`
leaves, the boards and the computer their `surface_game` surface. Sizes, pivots, fronts and colliders are unchanged
(`tools/tests/test_props_task_fine.py`).

### The command

```
tools/run.sh props [--spec props/tasks.toml] [--out DIR] [--only id,...] [--no-build] [--no-godot] [--review DIR]
```

| Option | What it does |
|---|---|
| (none) | Checks the spec and every prop's geometry, builds every prop in headless Blender, checks every GLB (glTF-Validator, nodes, UV2, vertex colours, the game surface's material) and imports them all into `godot/` headless (the kit's `godot/check/kit.gd`) |
| `--out` | Output folder (default `<raw>/props/task/v<version>`) |
| `--only` | Only these props |
| `--no-build` | Checks the GLBs already in `--out` |
| `--no-godot` | Skips the Godot import |
| `--review DIR` | Also renders the line-up sheets `lineup_<group>.png` (1280 px wide: each prop from the front and from 3/4, orthographic, with a 1.8 m grey capsule; Workbench with the vertex paint) , `switch_8m.png` (the post switch on and off from 8 m at a 1.6 m eye, 75 degree field of view) and `states.png` (the switches and the generator, on and off side by side, #82) |

It takes the heavy-run lock (Blender, Godot): run it in the background with its log under `tools/out/` and check it
with `tools/run.sh wait`. It writes into `--out`: `<id>.glb`, `textures/`, `build.json`, `reports/<id>.json`,
`godot.json` and the prop table `props.md` / `props.json` (chain, station, room, count, triangles against the
budget, size, colliders, game surface, extra nodes).

### The spec: `props/tasks.toml`

Every value is the engineer's to change (sizes, paints, mounts), as data:

- `kit`: the kit whose materials, packs and roles the props use (`kits/house.json`); a prop role may not redefine a
  kit role.
- `budget_tris`: `hero` 4,000 (task-critical pieces players use) and `room` 1,500 (room-defining), the plan's
  `look.md` §6.
- `materials.surface_game`: the game's writable surface, a material of its own that only the boards and the computer
  use.
- `roles`: the prop paints (a material and a hex colour each).
- `library`: the dressing library (`props/library.toml`) whose fine pack, fine-pack paints and `[style]` join the
  spec, for the props in the world look ("World look rules"); a fine paint may not share a name with a kit or prop
  role.
- `[[props]]`: `id`, `type` (the builder), `kind` (the budget), `w`, `d`, `h` (the built bounds, width along X,
  depth along Z, height along Y, within 1 cm), `chain`, `station` (the game's marker under `Stations`), `room`,
  `count`, and per type: `mount` (`wall`, `floor`, `post`, `stand`, `table`), `surface`, `nodes`, `board`, `style`,
  `plan_size` (the plan's size where a stand or fitting adds to it) and `notes`; `look = "fine"` builds the prop
  with its type's fine builder (`props_task.FINE_BUILDERS`: `board` on a stand, `island`) on the library's fine pack,
  and `check_spec` refuses it for a type without one or a spec without `library`.

### Conventions

- **Pivot and front**: the pivot is on the floor at the game's marker (a table-top prop's on the desk top), the
  footprint centred on it; the one front faces +Z. Godot's axes, metres.
- **Paint and materials**: as the kit's (`docs/kit.md`, "Paint"): one role per face, sRGB-encoded vertex colours,
  materials named `kit_<name>-vcol` (kit v2: plaster, wood and concrete export as one `kit_set-vcol`, the vertex
  colour's alpha picking the layer); the game surface is `surface_game-vcol`.
- **Game surface**: one flat quad facing +Z with UV0 0..1 over it (u along +X, v up), on the `surface_game`
  material, so the game can draw icons and text on it: the order board, the herb board, the pose screen, the photo
  board and the computer's screen.
- **Moving parts** are leaves with their hinge as origin and their collider parented to them: the freezer's, the
  grill's and the toy chest's `<id>_lid`.
- **States** are separate meshes the game shows or hides: a switch's `<id>_on` (lever up, green lamp, green knob)
  and `<id>_off` (lever down, red lamp, red knob); the printer's `<id>_photo` (the print in the output tray). The
  switch's state must read from 8 m (#82b), where its 0.3 x 0.45 m box is about 17 x 26 px at 720 px: the lamp is a
  window across the box's whole top (0.24 m) and the lever's crossbar is as wide, so the state reads as a band of
  colour at the top (on) or at the top and the foot (off). The lamps are paint, not emissive: in a dark room the game
  may give `<id>_on`'s `lamp_green` and `<id>_off`'s `lamp_red` faces an emissive override.
- **Collision**: closed convex boxes or prisms, `<id>_col<k>-convcolonly`, roughly the prop's volume (a table blocks
  sight under it); checked in Godot by one ray per collider.
- **The clay look**: every box over a few centimetres has chamfered edges (`cbox`), cylinders and lathed shapes are
  8 to 12 sided with chamfered rims, and the detail is hand-placed parts (louvres, gauges, bolts, tape, labels).
  One paint per face: there is no edge-wear or dirt vertex-colour pass yet (the house plan's look.md section 5); it is
  left to the clay look (#42a), so the kit and the props wear the same way.

### The checks

1. **Spec** (`props_task.check_spec`, `check_prop`): ids unique, roles on known materials, every prop's bounds equal
   its `w`, `d`, `h`, its lowest point on the floor and its footprint centred, within the budget, colliders not
   flat, UV2 on every face inside 0..1, a game surface exactly where `surface = true`, the `nodes` present.
2. **GLB** (the kit's `_kit.check_glb` and `props.check_surface_material`): every mesh node has UV0, UV2, COLOR_0
   and normals, every collider its node, at most the exported materials (`set`, `metal`, `glass`,
   `surface_game`), all `-vcol`; glTF-Validator has no errors.
3. **Godot** (`godot/check/kit.gd`, `_kit.evaluate`): bounds equal the spec's within 2 mm, the triangle count, UV2
   and sRGB vertex colours on every surface, one closed convex body per collider, and a ray hits each.

## The zone props: `props/zones.toml`

Art #81b adds the chill zone's and the photo gazebo's props as a second spec beside `tasks.toml`, built by the same
command: `tools/run.sh props --spec props/zones.toml [--review DIR]`. Their builders are in
`tools/blender/props_zone.py` (registered into `props_task.BUILDERS`); the spec's `out_dir = "zones"` sends the GLBs
to `D:/prime-art-raw/props/zones/v1/`, and its `label` heads the line-up sheet `lineup_zones.png`.

- Props: `deckchair`, `fire_pit`, `bean_bag`, `cooler_box`, `photo_backdrop`, `tripod_camera`, `lantern`, and two
  string-light sets: `string_lights_set` (a 5 m strand between two weighted poles, for open ground) and
  `string_lights_gazebo` (a strand hung between two of the kit gazebo's posts).
- Budgets add `dressing` 600 and `fixture` 400 triangles (the plan's `look.md` section 6).
- **Light fixtures** carry their bulbs (and the fire pit its embers) on an `emissive` material (`kit_emissive-vcol`,
  emission lamp c2 `#ffd9ad`; the vertex colour keeps each bulb's tint) and name their light anchors as sockets
  `light_<k>` in `build.json`'s describe output: the assembly puts the baked light there. Lights are fixtures, never
  free-floating lights (the plan's inventory section 8).
- `mount = "hang"`: a strand hung from two hooks has its pivot in the middle of the hook line and hangs below it
  (y from -h to 0); the floor check becomes "the highest point at y 0".
- The builders aim at the spec's bounds and `props_zone.fit` absorbs the rest (bars' slant, lathe facets) by at most
  6 % per axis; a bigger miss fails the build.
- A zone prop has `chain = "zone"` and `station = "-"`; the stations themselves (the grill, the speaker, the pose
  screen) stay in `tasks.toml`. Where they stand is the zones' layout data (`docs/zones.md`).

## The House dressing library

Art #87 (map request #73) makes one shared library of generic props (furniture, dressing, light fixtures, outdoor
things) so that every room package places furniture instead of making it. Task props (#82a, #82b), the car and its
lift (#79), vegetation (#80), the gazebo (#81b) and kit pieces are made elsewhere; `[skip]` in the mapping file names
who makes each. The plan is `D:/prime-art-raw/research/2026-10-10-house-plan/` (`props.md`, `inventory.md` §9,
`look.md` §5 and §6). The GLBs stay in the raw folder (`D:/prime-art-raw/props/library/v14/`: v13 with
#79's garage; v13 v12 with
#172's plant rooms and the darkroom's island; v12 v11 with
#170's basement working rooms; v11 v10 with #168's attic; v10 v9 with #166's kids' room and study; v9 v8 with #164's bedroom and guest room; v8 v7 with #162's rebuilt landing runner; v7 v6 with #162's landing and bathroom built over it; v6 v5 with #158's WC, pantry and stairs; v5 v4 with #156's hallway; v4 v3 with #153's dining room; v3 is v2 with #152's
cream sofa and armchairs, v2 v1 with #150's living room, v1 the version-1 build) until the engineer approves the look
on a review page; then they come into the repo under `assets/prop/<id>/` with their manifests.

### The mapping file: `props/library.toml`

The library is data: a paint, a size, a source file or a shape changes without a code change.

| Field | What |
|---|---|
| `[materials]` | Library material name to the kit's material (`kits/house.json`). The **one place** that names materials: when kit v2 (#86) merges plaster, wood and concrete into one `set` material, re-point the lines here. At most `max_materials` (8) targets; a target the kit lacks must be in `new_materials` (`emissive`, `fine`, `glass_tint`). |
| `[material_props]` | Roughness, metallic and alpha of a new material that is no kit material (`glass_tint`). |
| `[budgets]` | Triangles by class, `[min, max]` (`look.md` §6): `dressing` 150 to 600, `room` 400 to 1,500, `fixture` 100 to 400, `vehicle` 400 to 3,000 (the parked cars), `clutter` 12 to 400 (the small lived-in props of #104: books, cups, plates, bottles, pots, papers, frames' kin, baskets, shoes, toys; all `collision = "none"`, batch 3, placed by `house --clutter`, docs/house.md "Clutter"), `hero` 1,200 to 4,000 (the pieces players look at up close: the stove, the fridge). |
| `[layers]` | The layer by preset (`base` or `detail`) per class, and the `default`: `clutter` is `detail`. A prop's own `layer` overrides it; a detail prop must have `collision = "none"`. |
| `[style]` | The world look's measures (bevels, segments, the handle, front gap and thickness, plinth, worktop line, `floor_shade`) and the direction's `paints`; the shared builders read them ("World look rules"). |
| `[fine]` | The fine pack: `source` (the CC0 record of its textures), `tiers` (px per tier, High over Low) and `layers` in order (at most 16, at most 8 of them textured; a new layer goes at the end): a textured layer has `source`, `roughness`, `normal_strength`; a flat one `metallic` and `roughness`. |
| `[roles]` | The props' paints: a library material and an sRGB hex (the D1 palette, `look.md` §7). A role on the fine pack also names its `layer`. A prop may also name the kit's roles (`trim`, `fence`, `lino`, `glass` ...). |
| `[skip]` | Inventory ids this library does not make, with the package that does. |
| `script` | The Blender build script (default `prop_build.py`); another mapping file in this format names its own, such as `props/plants.toml`'s `plant_build.py` (the garden's plants, `docs/house-garden.md`). |
| `[[prop]]` | One prop: `id`, `batch` (the build order: 1 indoor furniture and dressing, 2 outdoor, fixtures and vehicles), `name`, `class`, `size_m` (the inventory's L x W x H: along X, along Z, up), `count` (placements), `route` (`pack` or `proc`), `roles`, `pivot`, `collision`, optional `layer` and `built_size_m` (the built box when fixed parts reach past the inventory's: the stove's hood, the sink's tap; the size checks use it). |
| pack props | `source` (a `sources/<id>.toml` record), `files` (relative to `<raw>/env`; several are stacked, the next on top of the one before), `src_size` and `src_triangles` (measured from the glTF), `yaw_deg` (a turn about +Y that brings the front to +Z), `scale` (uniform), `stretch` (fit the box per axis), `decimate` (the source is over the class's budget), `pack_size_m` (the part the pack supplies when `extras` add the rest), `extras` (procedural additions such as a wall mirror), `paint` (the roles of the source's colour clusters, dark to light, when the luminance order paints a prop wrong). |
| proc props | `shape` (a builder) and `params`. Generic builders cover most furniture: `cabinet` (doors, drawers, plinth or legs, top, cornice, sink), `table` (legs, top, shelf), `shelving` (shelves, items), `bench` (back, slats, cushion); the rest are one builder per prop. |

### Conventions

- **Axes**: Godot's, metres, +Y up; the front faces **+Z**.
- **Pivot**: `floor` at the footprint's centre on y = 0; `wall` with the back on the wall plane z = 0, centred on X,
  the bottom at y = 0 (the layout gives the height); `ceiling` with the top at y = 0, centred on X and Z.
- **Paint**: the kit's route (`docs/kit.md`, "Paint"): the pack's own material and atlas are dropped; the source's
  colours are clustered into as many groups as the prop has roles; the clusters, dark to light, take the roles, dark
  to light; the paint is written as sRGB vertex colours on `-vcol` materials.
- **Collision**: `box` (one box), `boxes` (several, for an L shape), `hull` (one convex hull) or `none` (rugs,
  decals, small fixtures above head height); closed, it stops line-of-sight rays, as the kit's check proves.
- **UV0** in metres for the detail textures; **UV2** packed for the lightmap bake, as the kit does.
- **Fixtures** carry their bulb as an `emissive` part; the light itself is a Godot node the map places.

### Scale: why many props are procedural

The plan expected about 80 pack props. Fitting the packs to the inventory's real sizes showed that the rounded toy
families (KayKit, Tiny Treats) are chunky: their counters, cabinets, wardrobes and benches are low and deep, and a
fit distorts them by more than 1.5 times between axes. Simple boxy furniture is cheap and exact as a procedural
build in the kit's materials, so version 1 has 32 pack props and 99 procedural ones (77 at first, then the
clutter of art #104 and its story pieces: `laundry_basket`, `drying_rack`, `open_box`, `radiator`,
`laundry_pile`, `boots`, `toy_spill`; docs/house.md "Fill"). The check (`_props.check`):

- without `stretch`, the uniformly scaled source is within 10 % of the inventory size on every axis;
- with `stretch`, the largest axis factor over the smallest is at most 1.5;
- a source over its class's budget needs `decimate = true`; every source is CC0 with `public_repo_ok = true`.

### The build

`tools/run.sh props-library --build [--batch 1|2] [--only id,...]` builds the props in one headless Blender run
(`tools/blender/prop_build.py`) into the mapping file's `out`,
`D:/prime-art-raw/props/library/v14/`: one `<id>.glb` per prop, `textures/`
(the kit's detail maps), `build.json` (what each GLB holds; batches accumulate) and `props.md` (the build table); then
it checks every GLB: the mesh and collider nodes, UV2 and vertex colours, at most `max_materials` materials all named
`-vcol`, glTF-Validator, the class's maximum triangles, a collider unless `none`, a fixture's light anchor. Under the
class's minimum is a note, not a problem: simple props are cheap. `--no-blender` checks the files already built.

The code is in three files:

| File | What |
|---|---|
| `tools/blender/prop_geom.py` | Pure Python (tested without Blender, `tools/tests/test_props_geom.py`): the primitives (a soft box with 4 mm chamfers, cylinders and frustums, tubes, ellipsoids, beams and rods at any angle, slabs, lofts), one builder per `shape`, the pack paint (k-means of the faces' colours, dark to light onto the roles, dark to light), the pivot, the collider and the light anchor, the description the export uses. |
| `tools/blender/prop_lib.py` | **The shared Blender helper for props** (the task props of #82 use it too): the materials (`materials`), a pack file's import with its face colours and the decimation (`import_pack`), one prop's export (`export_prop`). |
| `tools/blender/prop_build.py` | The entry the runner calls; a prop that fails is recorded in `build.json` with its error and the run goes on. |

Every builder works in the floor frame (x across L, y up to H, z across W, the front at +z) and takes the prop's roles
by position (`R[0]` the body, the last one usually the hardware); `finish` then moves it to its pivot. A pack prop's
files are stacked, turned by `yaw_deg`, scaled (`scale`, or fitted per axis with `stretch` to `size_m` or
`pack_size_m`), decimated to 85 % of the class's maximum when `decimate` is set, and painted; `extras` (`wall_mirror`,
`hood`) add procedural parts around it. Every GLB carries:

- one mesh `<id>` with UV0 (metres) and UV2 (one island per face, margin 2 % of the prop's size), sRGB vertex colours;
- its colliders `<id>_col<n>-convcolonly` (closed convex: a box, or the hull of the mesh);
- a fixture's `LightAnchor` empty at the centre of its emissive faces, where the map puts its light;
- materials `kit_<name>-vcol`; the emissive one glows in the prop's emissive paint (`bulb`, `tube`, `safelight`).
  Kit v2 (#86) packs plaster, wood and concrete into one `kit_set-vcol` material (the layer in the vertex colour's
  alpha): `prop_geom.lib_spec` carries the kit's `packs`, so props export the same materials as the kit pieces, and
  the build's `textures/` holds the packed `set_d.png`, `set_n0.png` and `set_n1.png` for Godot's set shader.

### The Godot check and the line-up sheets

After the GLB checks, `--build` (also with `--no-blender`) imports every prop into `godot/` as `prop_<id>` and runs
the kit's headless describer (`godot/check/kit.gd`) on them: the mesh, its triangles, UV2, sRGB vertex colours, one
static body per collider with a closed convex shape that stops a ray (the collider's points are read from the GLB),
the bounds against the size and the pivot (`floor`: the base's centre at the origin; `wall`: the back's bottom centre,
the prop in +Z; `ceiling`: the top's centre) and Y up, and the `LightAnchor` of a fixture where `build.json` put it
(no other prop has one). The describer's output goes to `<out>/godot.json`. `--no-godot` skips it.

`--sheets DIR` then shoots the line-up from an off-screen Godot window (`godot/props/lineup.gd`): the props in
library order cut into 4 sheets (`_props.sheet_plan`), on each sheet tallest first in rows of 7, each row beside a
1.8 m capsule and labelled with the ids, shot orthographic from the front-right and above, the kit's set shader on
the `kit_set` surfaces and a small warm light at each LightAnchor. Out: `DIR/lineup_<n>.png` (1280 px wide) and
`DIR/lineup.json` (the rows and the anchors Godot found). Review pictures only: the raw GLBs are not committed.
The line-up puts the fine pack's ShaderMaterial (`godot/props/prop_materials.gd`, the High tier) on the `kit_fine`
surfaces.

`--fine-compare DIR` (with `--build`) runs `godot/props/fine_check.gd` headless on the built props: per prop its
surfaces, images and texture bytes, that every `kit_fine` surface gets the same shared texture resources, and the
fine textures' memory per tier (BPTC with mipmaps); DIR holds GLBs to measure against (the kitchen pilot's), compared
prop by prop. Out: `<out>/fine_check.json`.

### The command

```
tools/run.sh props-library [--measure] [--table FILE] [--build [--batch N] [--only IDS] [--out DIR] [--no-blender]
                  [--no-godot] [--sheets DIR] [--fine-compare DIR]]
```

It checks the mapping file (no raw file needed); `--measure` reads every pack file in `<raw>/env` again (a pure
Python glTF reader: the accessors' bounds through the node transforms, the triangles) and compares them with the
record; `--table` writes the prop table as markdown. The tests are `tools/tests/test_props_library.py`,
`test_props_geom.py` and `test_props_godot.py`.

## A hero prop from a concept: the vault's plush alien (art#297)

`assets/prop/vault_plush/`: the easter egg the ship's vault holds (prime-game#1040), made from the engineer's approved
concept in four steps, each shown to him before the next.

1. **Turnaround.** An OpenAI edit of the concept (`batches/2026-10-22-vault-plush-turn.toml`, high, 2560x1024, one
   image): five views in a row at one scale. His note on the first sheet's model: no seams anywhere and the
   concept's soft fur, so item `turn5b` edits the sheet with the concept as the fur reference.
2. **Model.** Meshy `multi_image_to_3d` (meshy-7.1, 2k geometry) from four views cut from the sheet, each padded
   to a square on the sheet's own grey (`batches/2026-10-22-vault-plush-3d-2.toml`, 35 credits).
3. **Paint and material**, `tools/blender/plush_run.py` (the driver, outside Blender), each step a headless Blender
   script:
   - `plush_clean.py`: welds Meshy's GLB (it arrives split at every UV seam: 2,938 loose patches), scales it to
     0.30 m with its lowest point on the floor and its footprint centred;
   - `plush_mouth.py`: finds the crease under the muzzle from the shape (the most concave vertex per angle around
     the nose's axis), relaxes its concave vertices within 7 mm into a shallow seam and writes the smile's line along
     the seam (`smile.json`: one symmetric curve, the distance and depth as even quartics of the angle, out to the
     nose's middle height);
   - `plush_paint.py`: repaints the **full** model to the concept. Orange or brown is decided per face in 3D (the
     brown share diffused over the surface, cut at a half, islands under 200 faces merged), never per texel; the tail's
     stalk orange and the antenna balls and pompom brown per texel from each texel's 3D point; the eyes painted
     afresh (pink, a soft red rim, a round pupil, a catch light); the smile drawn from `smile.json`; Meshy's marks
     elsewhere are fur again. Writes the albedo and the shader's mask (R fur, G velour, B eyes);
   - `plush_bake.py`: decimates a welded copy to 4,000 triangles (`hero`) with a fresh Smart UV layout and bakes the
     painted full model onto it (albedo and mask as emission, the normal in tangent space), `--size` px.

   **Why paint full, then bake:** decimating Meshy's GLB in place keeps its many small UV islands but moves their
   corners, so triangles sample the next island's texels: black specks by an eye and on the belly (the engineer's
   review, 2026-10-23; the same paint on the 31k model had none). Growing a painted region in UV space spills into the
   island packed beside it for the same reason; the paint never grows regions, it pads island edges instead.

   The material is `godot/plush/`: `plush.gdshader` (Burley, roughness 1 on the fabric, a model-space pile normal
   since the atlas is all islands, a fabric-tinted rim as the sheen, glossy eyes with a flat normal),
   `plush_shell.gdshader` (12 shells of jittered strands for the fuzzy silhouette, thicker and flatter with distance,
   none past 6 m) and `plush.gd` (applies them; it preloads the shaders by relative path, so the same file ships).
   `shots.gd` renders the views, close-ups of the face, eyes, mouth, antennae, belly, back, tail and feet, the smile
   from four elevations, the hand view and the 1 m stand at 3 and 5 m under the recommended look, and measures the
   shells' GPU cost (0.14 ms in the hand view).
4. **Export.** `plush_run.py --size 1024 --tag=_final --blend <raw>/.../vault_plush.blend`: the GLB (3,999
   triangles, 0.300 m, glTF-Validator clean), the mask, the `.blend`; the asset folder holds them with the material
   files, `report.json` and `HANDOFF.md`. `tools/tests/test_props_vault_plush.py` checks the committed asset.

Lessons for the next hero prop: shoot 720 px close-ups of every part and give them to a fresh critic before calling a
step done; decide colours in 3D, not per texel; check a feature that sits in a crease from above and below (the smile
reads in full from 10 degrees below, mostly its corners from above, where the player usually stands).

## A hero prop from code: the ship engine's energy crystal (art#263)

`assets/prop/energy_crystal/`: the cartridge of the ship's engine (prime-game#1033, the engineer's comment
6361383461): a faceted energy crystal in a bronze and graphite cap with a hexagonal carry loop. Players pull a spent
one from its socket, recharge it at a charger and put it back; the sockets and chargers are built later to fit it.
The concept is prime-game-design's `ideas/ship-components/cartridge-v2/`: `crystal-views.jpg`, the straight views
of the crystal alone, charged and spent (front, side, top, 3/4), made for this build; `socket-claws.jpg` and
`charge.jpg` show it in its socket and charger (the spent crystal's cracks there are not wanted). They are copied to
`<raw>/energy-crystal/ref/`.

**Drawing first, then the model** (the engineer, 2026-10-24: "like engineering drawings at university: the part
from different sides, in centimetres, everything exact"):

1. **Measure.** `tools/blender/crystal_dims.toml` holds every size in centimetres: the crystal's corners at its top
   and point rings, the point's length, the body, the shoulder, the skirt, rim, groove, band, windows, notches, dome,
   disc, lens and the loop's size, bar and depth. They were read off `crystal-views.jpg`'s spent front view (the
   silhouette's width per pixel row; the charged views glow, which widens them), the cap's plan from its top view and
   the loop's depth from its side view, scaled so that the whole is 35 cm. The sheet's views disagree in places (its
   side view draws the band 20 % narrower; its top view puts the windows on the side faces, the other views on the
   diagonal ones): the front view wins, and the file says so. A hexagon's front-view width is across its corners,
   an octagon's (a flat to the front) across its flats.
2. **Build from the numbers.** `tools/blender/crystal_build.py` reads the file and builds every part from it in
   headless Blender. Before the chamfers it writes `features.json`, the model's own edges (the folds and open
   edges, each with its faces' normals).
3. **Draw.** `tools/blender/crystal_drawing.py` (plain Python) projects those edges into the front, side and top
   views and dimensions them from the same file: `drawing/drawing.svg` on paper, `drawing_concept.svg` over the
   concept's views and `drawing_model.svg` over the model's orthographic renders. The frames match
   `crystal_build.py`'s `ORTHO` frames at 16 px per cm, and the concept's views are cut to the same frames from
   the points they were measured at. So the drawing lies exactly over both, and a size that is wrong shows as a
   line off the picture.

`tools/blender/crystal_run.py` (the driver) runs the build, glTF-Validator, the drawing and the Godot shots:

```
$PYTHON_BIN tools/blender/crystal_run.py [--tag drawn] [--res 900] [--samples 64] [--no-build] [--no-shots]
    [--asset assets/prop/energy_crystal]
```

- **The crystal** is a hexagonal column whose corners run straight up and narrow a little toward the point; each
  face holds a column of long diamonds (the face's middle line has a vertex every other step, 12 % outside the flat
  face, so the facets fold and catch the light). Neighbouring faces are staggered by a step, so the diamonds' sides
  run on across the corners. Below is a point of twelve facets, above a shoulder into the skirt. Every facet edge
  has a 0.6 mm chamfer, the visible line. The chamfer blunts the point a little: the model's origin stays at the
  drawing's tip, a few millimetres below the lowest vertex.
- **The core**, a slimmer copy turned 30 degrees inside it, is what the charged crystal glows from: seen through
  the translucent shell it gives the depth and the second set of lines the concept paints.
- **The cap** is an octagon with a flat to the front. Over the crystal's shoulder sit a bronze lip and a graphite
  hexagonal skirt with inset panels. Then a bronze rim, a dark groove, and the upright bronze band, with four cyan
  windows on its diagonal faces and a graphite notch at the foot of each straight face. On top are a bevelled
  bronze dome, the graphite top disc with a cyan lens, and the hexagonal carry loop, a chunky bar. Metal edges over
  30 degrees get a 1.2 mm chamfer (0.8 mm on the small parts, 2 mm on the loop).
- **UV0 carries data, not a layout**: u = 1 on every chamfer face (the materials brighten them: the bronze's worn
  edges, the crystal's glinting edges), v = a per-facet random value (the facet-by-facet shade). No textures.
- **Two states, one mesh**: the charge. Blender's look reads the node group `crystal_charge` (the `.blend` keeps it
  at 1); the game's look is `godot/crystal/crystal.gd` (`apply(model)` puts `crystal_shell.gdshader`,
  `crystal_core.gdshader`, `crystal_metal.gdshader` and the lights' material on the surfaces by their glTF names and
  adds a small cyan OmniLight3D; `set_charge(look, c)`): 1 a translucent cyan gem glowing from inside, 0 a matte
  grey stone, opaque, no glow, the cap's lights at 22 %. The GLB's own materials are a plain-PBR fallback of the
  charged state.
- **Colours across the two looks**: Blender's Principled colours are linear; Godot's `source_color` uniforms are
  sRGB, so the Godot metal holds the sRGB of Blender's numbers (bronze (0.42, 0.29, 0.17) linear is (0.68, 0.578,
  0.454)). Passing the linear numbers made the Godot bronze nearly black. AgX bleaches bright pale cyan to white:
  keep the glow colours saturated ((0, 0.72..0.78, 1)) and the emissive strengths moderate.

`godot/crystal/shots.gd` shoots both states in an off-screen window under the ship interior's night light rebuilt
from `godot/ship/ship.gd` and `layouts/ship/ship.toml` (AgX 1.0, the dark blue ambient, the glow settings, SSAO,
SSIL, a warm interior lamp, the cool night key, a cyan strip's rim): the 3/4, front and top views, close-ups of the
cap, loop and facets, the crystal on a 1 m post seen from 1 m (its glow on the wall) and carried in the first-person
view, and `sheet.png`, the concept beside Blender's and Godot's views. `tools/tests/test_props_energy_crystal.py`
checks the committed asset.

## A station from its drawing: the ship engine's start console (art#263)

`assets/prop/start_console/`: the console in the middle of the ship's hall where a player presses the start button
and, while breakers are tripped, the hologram plays the order to switch them back on, one lamp at a time. The
engineer picked the concept on 2026-10-24 (prime-game-design `ideas/ship-components/stations-final/console-final.jpg`,
the hologram in the style of `holo14-diamond-2.jpg`) and had its drawing made in cm (`console-drawing/`: the
concept's straight views and `drawing.js`, whose numbers stretch the body 40 cm so the button sits at hip height).
They are copied to `<raw>/start-console/ref/`.

1. **The numbers.** `tools/blender/console_dims.toml` holds every size in cm: the drawing's own (the plinth, the
   body, the rim, the button, the strips, the emitter, the hologram's span, height and tilt) and the smaller ones read
   off the same views at the drawing's scale (the blocks' bevels, the bezels, the emitter's steps).
2. **Build from the numbers.** `tools/blender/console_build.py` (headless Blender): the plinth, the body and the rim
   are rings of bronze blocks round a graphite drum, each block a profile swept straight between two angles, so its
   faces are flat chords; the body's front block is one wide flat face for the button, a cyan channel either side.
   The drum must stay inside the front block's chord (47.9 cm from the axis at the top): a 51 cm drum first poked
   through its middle as a dark column. Every block edge over 30 degrees gets a 9 mm chamfer marked in UV0 u, which
   the metal brightens (the concept's bright edges).
3. **The hologram from the ship's own mesh.** The built hull pieces (`skin_top`, `skin_belly`, `skin_mouth`,
   `skin_cheeks`, the three nozzle pods; `<raw>/<ship.toml raw_dir>/pieces/`, since v5 built on the raised
   deck: `console_run.py` passes `[deck] lift_m` and the build lowers them back by it) are joined, turned so the nose points at the
   button, scaled to 1:16.3 (the 26.1 m span to the drawing's 159.8 cm), the hall's centre put over the core at
   145.7 cm and leaned 12 degrees nose down. **Its plates' own edges do not make a hologram**: the hull is built of
   separate plates, so its open and creased edges are a dense grid that read as white noise (the first trial,
   78,900 triangles of lines). The lines are cut from the mesh instead: a level cut through the widest edge (the
   outline), contour cuts over the top, the keel's profile, the long creases inside the plates, a section grid over
   the top every 1.62 m (two module lines), rings and lengthwise cuts on the pods; and the rooms with the concept's
   elements as one flat plan at the deck inside the hull: the hall's disc with a dashed ring, the entrance channel to
   the nose, the bands to the tip discs with the eight order lamps. Laid on the curved top by rays
   from above (the first try), the disc sat over the hull and the rooms climbed its hump (the engineer's review,
   2026-10-24). Each line is a three-sided tube (it reads from every side), its brightness in UV0 v; a faint additive
   shell gives the volume.
4. **The states** are values, not meshes: the stage strips' and lamps' indices sit in UV0 v and
   `godot/console/console_signal.gdshader` lights them from `passed`, `lit` and `order` (`console.gd` `set_state`,
   `set_passed`, `set_lit`). The hologram and the light column are additive, both sides, no depth write
   (`console_holo.gdshader`).
5. **Check against the concept.** `tools/blender/console_run.py` renders the states in Blender, the orthographic
   views at 4 px per cm and the concept's straight views cut and stretched as the drawing stretches them;
   `console_drawing.py` draws the model's edges and the sizes over both (`<tag>/drawing/*.svg`). The Godot shots are
   taken in the ship's hall itself: `godot/console/hall.gd` extends `godot/ship/ship.gd`'s shoot mode, adds the
   console to the built ship on its station spot (`ship.toml`: (0, 0.6); yaw 180, the button to the mouth), keeps it
   out of `ship.gd`'s dressing pass (that pass would give the GLB's plain emissive fallbacks strip lights the game
   never has) and puts `console.gd`'s look and each view's state on it; `godot/console/sheet.gd` makes the sheet
   beside the concept and measures the GPU cost.

   ```bash
   $PYTHON_BIN tools/blender/console_run.py --tag <tag> --res 900 --samples 64 --asset assets/prop/start_console
   ```

6. **The engine's spin-up** (step 1; prime-game#1095 c6392050112): four parts on the hologram, each a surface on
   `console_holo.gdshader`'s modes 3 to 6 with its ids in UV0 (`console_dims.toml` `[spinup]`): the pods' lines and a
   fan at each pod's front (`console_holo_turbine`: u the angle round the pod, the fans u 5, turned in the vertex
   shader round their centre, `console.gd` `FAN_CENTRES` and `FAN_AXIS` from `build.json`), the wiring
   (`console_holo_wire`: v the station's index in `STATIONS`, 8 the manifold; u the distance along the line toward the
   turbines in dm, the points -1, their halos -2), the charge ring where the dashed ring was (`console_holo_ring`: u
   the bar's share, v foot 0 and top 1) and the countdown (`console_holo_digit`: v digit x 10 + segment, turned to the
   eye about the console's axis). The strips' UV0 u is their fill's share across, so the three fill as one bar. The
   stations' lines run in one lane each (`[spinup.lanes]`: a radius round the hall's centre and an x for the run aft),
   ordered so none crosses another: a back socket on the outermost lane, a vent on the innermost; a breaker comes in
   along its corridor beside the order lamps, a vent along the throat's wall. The time is the console's own clock (a
   tween on a uniform, so the game can read the call's phase for its beep and the fans keep their angle through a
   change of rate). `console_run.py --spinup` shoots the four states from the console's front, the throat and both
   corridors' mouths and the close-ups on the current pieces (it refuses a deck other than 1.2 m), the before/after
   against the shipped build2 GLB with the spin-up hidden (`console_diff.py`, numpy in headless Blender) and the
   scripted round's MP4 (`hall.gd`'s video mode). The API: `assets/prop/start_console/HANDOFF.md`.
7. **The spin-up read from the hall** (step 2): what reads at 6 m is light that grows, not lines that change colour.
   The call floods the turbines (brighter, the lines swelling along their normals, in `call_colour`: the sRGB
   `orange` is nearly red in linear and reads pink under AgX) with a camera-facing glow sprite round each pod and a
   wash over the shell; a broken point adds a big red bead (a sprite) and a red pillar turned about the vertical to
   the eye, both blinking at its rate. The sprites and pillars are tiny quads in the GLB (`fx_w0`, their corners
   `FX_SPREAD` off their ids in UV0) that the vertex stage sizes, or folds onto their centre while off: no pixels.
   The charge ring's band is built twice as tall (`ring_h_tall`) and the shader draws a share (`band_top`); the
   same bar runs again as a ring on the emitter deck (`deck_ring`, v 2..3), leaning out so it is seen from every
   side. `console.gd` `set_ring_style` ("band", "deck", "both", "step1") and `set_fill` ("cyan", "green") keep the
   choices open; `console_run.py --spinup` shoots their grid (`<tag>/grid/`) and step 1's throat stills beside
   step 2's (`before_after.png`, `console_diff.py --pairs`). A NaN in an additive shader (a `pow` of a negative
   behind a zero factor) blooms the whole frame black: clamp before `pow`.

`tools/tests/test_props_start_console.py` checks the drawing's numbers in the dims file, the committed asset, the
spin-up's ids in UV0, the report's stations against `ship.toml` and `console.gd`'s API and constants.

## A wall station from its drawing: the ship's crystal socket (art#263)

`assets/prop/crystal_socket/`: the wall socket that holds one energy crystal, four of them on the ship's hall walls
(`layouts/ship/ship.toml` spots `socket_e`, `socket_w`, `socket_fe`, `socket_fw`). The engineer picked the sheet on
2026-10-25 (prime-game-design `ideas/ship-components/stations-final/socket.jpg`: charged, spent with the lamp lit,
side) and had its drawing made in cm (`socket-drawing/` at ea27a81: the sheet's straight views and `drawing.js`).
They are copied to `<raw>/ship/v4/socket/ref/`. Built the start console's way, file for file:

1. **The numbers.** `tools/blender/socket_dims.toml`: the drawing's polygons (the outline, the bay along the cyan
   strip, the claws, the collar, the slots) and depths (back plate 6.7, middle layer 12.2, frame face 21.1, claw tips
   22.2, the bay's floor 9.5, the crystal's axis 17.0), plus the smaller sizes read off the views. **Every h is drawn
   at `[mount] drawn_at`; `[mount] h` (MOUNT, the crystal's middle, 140) is the one number that moves the socket**
   (`socket_drawing.load` shifts them all; the engineer may lower it to 120).
2. **Build from the numbers.** `tools/blender/socket_build.py` (headless Blender): each layer a polygon, or a polygon
   with a hole, extruded between two depths, its front edges bevelled twice (socket-2, `bevel2`: a broad chamfer,
   then a fine bevel on both its edges), marked in UV0 u (0 flat, 0.5 the broad chamfer, 1 the fine bevels: the
   console's metal wears them brighter, so each block reads as machined bronze with bright edges). The outer frame
   is separate blocks (`[outline] seams`: the matched ring cut on rays from the bay's middle, each block pulled back
   `seam / 2` square to its ray, the graphite plate dark in the gaps and round the edge); a raised inner bezel round
   the bay carries the cyan strip (1.2 wide, proud of the ring's rim); the amber windows sit sunk in bronze bezels;
   the neck, the lamp's collar and the crystal's cup are turned (16 sides, grooves and bevelled rims). The claws fit the
   **built** crystal, not the concept's: its cap measures 13.62 across at its band (its bronze rims), so the jaws sit
   at u 6.84 and reach down to 148.0 (the drawing's 149.0 held only 0.4 cm of the band). Convex colliders
   `crystal_socket_col<n>-convcolonly` leave the crystal's room and the lamp free; the `crystal_anchor` empty sits at
   the crystal's pivot (its tip: MOUNT minus 17.45) on its axis with no rotation, so the game parents
   `energy_crystal.glb` there and slides it out along +Z.
   **The claws open** (socket-3; the engineer's decision of 2026-10-25, prime-game#1095 comment 6392150248; the
   drawing's `HINGE`, `OPEN`, `PULL` at prime-game-design 1df9a42): each claw is its own object (`claw_leaf`:
   `claw_r`, `claw_l`) with its origin on its hinge (u +-5.37, h 162.79) and its collider parented, turning in the
   wall's plane round its local glTF +Z. A moving part must not pass through the frame, so the claw is a plate in
   front of the lip (`[depth] claw_plate` 20.15 .. 22.2, the drawing's outline cut in two knuckled segments, a barrel
   round the hinge on a graphite pin) and only a small jaw finger reaches back beside the cap; the header became a
   narrow neck block between the hinges (a dark gap to each claw: two arms, not one hoop). The swing check turns the
   claws 0 .. 40 degrees and counts their triangles against the body's: the finger cuts the bay's lip past
   28 (it touches at 29), so `[claw] open` is 25 (the drawing's 35 was a placeholder).
3. **The checks with the crystal.** The build imports the crystal onto the anchor and measures what a picture
   hides: the claws' gap to the cap, the tip over the collar, triangle overlaps of the crystal with the socket and
   its colliders at rest and pulled out in 2 cm steps, parts touching no other part, open edges, and coplanar faces
   of two parts facing the same way (z-fighting); socket-3: the claws' swing per degree, the open claws' gap to the
   body and the crystal pulled out past the open claws. They go into `build.json` and the asset's `report.json`.
4. **The look and the states.** `godot/socket/socket.gd`: the console's bronze and graphite
   (`socket_metal.gdshader` is `console_metal.gdshader`, extended by socket-3 with parameters that default to the
   console's look; the socket's values are `socket.gd` `BRONZE_FINISH`; socket-2 set the bronze darker and more metallic
   than the console's, a greyer gold at metallic 0.75 and roughness 0.32, picked from the studio's variant grids (0.9 read near-black in the hall): the console's 0.35 read
   as matte brown plastic beside the sheet), cyan and amber glow, the red dome
   `socket_lamp` with its own light; `set_state(look, "charged" | "spent" | "empty")` lights the lamp for spent and
   empty, and the bay's floor (`socket_bay.gdshader`) glows cyan round a charged crystal; `set_claws(look, 0..1)`
   opens the claws. socket-3 gave the shared metal shader parameters whose defaults keep the console's pixels (the
   colour's mottle and grain, the roughness's, the worn edges' polish, and off by default: `shade`, faces lighter or
   darker by their facing, and `dent` / `wave`, a hammered and a broad bend of the normal; the fix pass made their
   height field a smooth 3D gradient noise in a turned model space, each slope behind its own `if`: the value noise
   before drew square tone patches on the big flat faces of all three stations, and the console's pixels stay the
   same, 0 of 409,600 differ; every copy of the shader is the same bytes, `tools/tests/test_props_metal_shader.py`); `socket.gd`
   `BRONZE_FINISH` holds the socket's values, the ones the other stations' bronze matches. `seat_crystal(crystal_look)` keeps the crystal's own light off the socket (the socket draws on render
   layer 20 alone, the crystal's light leaves that layer out of its cull mask): in the niche it burned the frame
   white-cyan, and moved 30 cm out it washed the whole face mint (the hall shots b2 and b4).
5. **Check against the drawing and in the hall.** `tools/blender/socket_run.py` renders the front and side
   orthographic views with the crystal, cuts the drawing's straight views to the same frames and draws the built
   numbers over both (`renders/overlay.png`; `socket_drawing.py` the same as an SVG). `godot/socket/hall.gd` extends
   `ship.gd`'s shoot mode: a socket on each of the four spots (yaw `atan2(normal x, normal y)`), the crystal on each
   anchor, the hall views and the sheet beside `socket.jpg` (`<tag>/hall/`), the close-ups of every edge and seam
   (`<tag>/close/`). `godot/socket/studio.gd` then shoots the socket on a neutral backdrop at the sheet's
   three-quarter angle beside `socket.jpg` (`<tag>/compare_sheet.png`; the claws open and the crystal pulled out:
   `studio/studio_open.png`); `--grid FILE` adds one render per variant of the look's materials
   (`[{"title", "bronze": {shader parameter: value}, "amber": {property: value}}]`, `<tag>/studio/grid.png`);
   `--studio-only` shoots only that from an existing build.

   ```bash
   $PYTHON_BIN tools/blender/socket_run.py --tag <tag> [--grid FILE] --asset assets/prop/crystal_socket
   ```

`tools/tests/test_props_crystal_socket.py` checks the drawing's numbers, the one-number MOUNT, the claws against the
built cap, the claws' hinge, angle and pull against the drawing and `socket.gd`, and the committed asset (anchor,
the claws' nodes and colliders, the report's checks).

## A station with moving leaves: the ship's breaker board, the shells (art#263)

`assets/prop/breaker_board/`: the board on each corridor's front wall (`breaker_e`, `breaker_w`) where a tripped
breaker is switched back on by lifting its shell. The engineer picked variant 3, the shells, on 2026-10-25
(prime-game-design `ideas/ship-components/stations-final/board-variants/v3-shell-final.jpg`) and its drawing in cm
(`board-drawing/`: the sheet's straight views and `drawing.js`, at commit 6b0e83e). They are copied to
`<raw>/ship/v4/board/ref/`. The way is the console's, file for file; what differs:

1. **The numbers.** `tools/blender/board_dims.toml`: the drawing's own (160 wide, the frame h 52 to 131.4, the beacon's
   top 140.4 under the wall's slant at 145, the bays at u +-16.8 and +-50.4, the shell 20.4 wide and 37.2 from its
   hinge axis at h 67.7, d 25, the trip of 110 degrees, the core 10.3 x 17.4 at h 87.2, d 18) and the smaller ones read
   off the straight views at 7.75 px per cm (the border's widths, the seams, the knuckles, the facets, the couplings).
   Two numbers had to move: the core is flattened to 6.8 deep (round, its 10.3 would cross the closed shell's back at
   d 22), and the shell's flat top facet runs only from 9 to 24 cm up its length, because the drawing's face is a
   dome (26 + 5 sin(pi s / 37.2)); a table to the top dropped the tripped shell's lowest point to h 51.1 against the
   drawing's 53.9.
2. **Build from the numbers.** `tools/blender/board_build.py` (headless Blender) cuts the octagon into convex blocks
   (clipped polygons extruded in d) with half-centimetre joints over a graphite slab, so the border and the inner
   panel read as the sheet's bronze blocks; each bay's surround is eight trapezoids, its bottom rail open in the
   middle where the hinge sits. Each **leaf is its own object with its origin on its hinge axis** (local X rotation,
   0 closed, +110 degrees tripped: the top out of the wall and down), its convex collider its child; the cores, the
   lamps' lenses and the beacon are their own objects, so the game can light each alone. The leaf's body starts 3.3
   cm over the axis and a lug carries it down to its own knuckle, which leaves 0.3 cm to the fixed knuckles either
   side: a body down to the axis crossed them on the way.
3. **The sweep check.** The build turns every shell through its trip in tenths and counts the triangles it crosses
   on the body, the cores, the lamps and its neighbours (`build.json` `sweep_check`; empty is clean, and the test holds
   it). It checks 11 poses 11 degrees apart and triangle crossings only, not volumes: a thin part that passes wholly
   between two poses, or a shell that sits inside another part without one triangle crossing, would not count (at the
   shell's top, about 40 cm from its axis, one step moves it about 7 cm). Finer steps need a rebuild of the asset's
   report; the Godot sweep shots (0, 1/4, 1/2, 3/4, 1) are the eye's check between the poses. `board_drawing.py` compares 23 of the drawing's numbers with the model's (`drawing/compare.json`, 0.5 cm
   tolerance): 20 measured off its own vertices, 3 set (the lamp ring from the dims, the hinge's h and d from the
   leaves' pivots; `board_drawing.SET`) and `drawing_front.png` and `drawing_side.png` show the model's ink and outlines over the
   straight views at the drawing's scale.
4. **The states** are node rotations and material values: `godot/board/board.gd` `set_shell(look, i, open01)`,
   `set_on` / `set_lamp` (dark, yellow, green), `set_problem` (the beacon and its red light), `set_core`; the cores'
   shader is kin to the energy crystal's core (`board_core.gdshader`), the metal is the console's (a byte-identical copy, so the
   board's files stand alone). The sparks and smoke at a tripped core are the game's.
5. **The shots** are taken in the east corridor itself: `godot/board/corridor.gd` extends `ship.gd`'s shoot mode, puts
   a board on both spots (yaw from the spot's normal), keeps them out of the dressing pass and sets each view's state;
   the views are the sheet's (all on, yellow and green tripped, `compare_*.png` beside the sheet), the yellow shell
   at 0, 1/4, 1/2, 3/4 and 1, and close-ups of every edge and seam.

   `godot/board/studio.gd` then shoots the board on a neutral backdrop at the sheet's hero angle, `compare_sheet.png`
   beside the sheet (the socket's studio).

   ```bash
   $PYTHON_BIN tools/blender/board_run.py --tag <tag> [--pieces DIR] --asset assets/prop/breaker_board
   ```
6. **The wall (board-2).** Shoot on a ship build with the raised deck: `--pieces` defaults to `ship.toml`'s
   `raw_dir` pieces (`<raw>/ship/v5/pieces/` since the fix pass; board-2 and -3 shot on the vents' b5b build,
   `<raw>/ship/v4/vents-b/pieces_b5b`, the same bytes), and the run refuses pieces whose corridor deck (the grate's
   top, read from the GLB) is not `floor_h`. The old `raw_dir` pieces (`<raw>/ship/v3/pieces/`) predate the raise
   (deck 0.6): step 1 shot the board on them, 0.6 m above their deck, and its beacon stood in the slanted upper wall. Rays on the
   b5b build at both spots: the deck at 1.200; the wall's face plane through the spot's `at` (its seams at d 0); its
   pillow panels 4.4 .. 7.0 cm proud of it inside the board's outline; vertical to 2.65 (1.45 over the deck), slanting
   above. So the board's d 0 stands `[mount] d` (7.0 cm) out of the face plane on the panels' crowns, and a graphite
   mount block inside the plate's outline (and the cable clamps) reaches back 0.5 cm into the wall's body: no gap.
   Its h 0 is the deck.
7. **The look (board-2).** The bronze and graphite are the crystal socket's values (socket-2), the bays' surrounds
   are thickened from the drawing's 1.15 cm sides to 3.0 (the sheet's chunky bezels, a look call), the shells' bronze
   lips carry the bright-edge mark, the beacon's light reaches 0.45 m at 0.6 energy (at 1.6 m and 0.9 it streaked the wall's panel seams red).
8. **The look (board-3), toward the sheet.**
   - The bronze is the socket's step 3 (`socket.gd` `BRONZE`, `BRONZE_FINISH`) on the shared metal shader:
     `board_metal.gdshader` is the console's `console_metal.gdshader` byte for byte, as the socket's copy is.
   - The inner panel behind the shells is a seventh body surface, `board_panel`: the same finish in a darker bronze.
   - The border is a ring of mitred blocks between the outline and the inner panel's octagon: the four big cut
     corners are blocks of their own, the bottom and top cut again at u +-47.5, the beacon's seat at the notch;
     their bevel is `[frame] border_chamfer` (1.8 cm). The broad bevels are marked u 0.35 (0.55 went cream).
   - The hinge knuckles are turned (`[hinge] turned`, `leaf_turned`: lathe profiles with grooves and a big end cap).
     The shell's bottom edge stands 3.3 cm over the axis only in its middle, so the barrels grow past |u| 6.6.
   - The cores are cut gems: three rings, the middle one turned half a facet; deep blue with bright cyan edges.
   - The strips stand 1 cm proud in raised graphite frames, the lamps are saturated green on a coloured lens.
   - The beacon's light is a spot out of the wall and 25 degrees down (55 degree cone, 0.9 m). The omni lit the
     corridor's slanted wall right above the dome red at close range; the spot leaves the wall above and behind it
     dark.

`tools/tests/test_props_breaker_board.py` checks the drawing's numbers, the leaves' pivots and colliders, the clean
sweep, the mount and the committed asset.

## A station from its drawing: the ship's crystal charger (art#263)

`assets/prop/crystal_charger/`: two of them, one on each lens room's aft wall (`layouts/ship/ship.toml`
`[[stations.spot]]` `renewer_e`, `renewer_w`), where a player recharges a spent energy crystal. The engineer's pick of
2026-10-25 (prime-game#1095 comment 6401197371): the squat base raised on four long legs like the ship's own
(prime-game-design `ideas/ship-components/stations-final/charger-legs.jpg`) and its drawing in cm
(`charger-drawing/drawing.js` at commit a53ce6f over `front-ortho.jpg` and `top-ortho.jpg`; the generated side view
was wrong and is not used: the charger is round). They are copied to `<raw>/ship/v4/charger/ref-legs/` (`ref/` keeps
the first drawing's, b4's). Build b4 (a tall drum on three feet, cut flat at the back) is history.

**Lens room C (2026-10-28): the pedestal in the wall's alcove.** The engineer's look C for the lens rooms sets the
charger into an alcove in the aft wall (`docs/ship.md`, "Lens room C"). The head is unchanged; the dome on four legs
is replaced by the lens room drawing's faceted pedestal (prime-game-design 7f335c2,
`ideas/ship-components/lens-room/drawing/drawing.js` `C.ped`, copied with `c_lounge.jpg` to
`<raw>/ship/v4/charger/ref-lens/`). In `charger_dims.toml` `[frame]` and `[base]` (cm, the spot's vertex the origin):

| Part | Numbers |
|---|---|
| Plan | back u ±44 at d 10 (on the alcove's back panel), sides to d 46, chamfers (±44, 46) -> (±22, 68), front face u ±22 at d 68 |
| Plinth | graphite, h 0..10, overhanging 1.5 (sides), 3 (chamfers), 2 (front) |
| Body | five bronze plates (2 cm) in two courses (joint at h 48) on a graphite core, 0.55 seams; h 10..86 |
| Deck slab | bronze, h 86..99.1, the plinth's overhang; the well r 24.2 down to 94 round the slot |
| Crystal axis | d 38 (was 53.5): the track ring (r 23.6) clears the back panel by 4.4 |
| Button | Ø 8 at h 75.9 on the front plate; its lens's face d 69.8 |
| Lights | cyan up each chamfer (h 22..80), an amber pair on the front (u ±16, h 18..44), amber along each side (d 18..40, h 80) |

The drawing's lip is 3 all round; the sides keep 1.5 so the plinth and slab clear the opening's cheeks (u ±46 at the
back panel) by 0.5, the front 2 so nothing passes the reach 70 (the drawing's own "виступ 70"). `build.json`'s
checks: `wall_min_cm_body` (to the back panel, 0: it stands on it), `cheek_min_cm_body`, `reach_cm`, the ring's turn.
The legs' charger's renders and shots stay in `<raw>/ship/v4/charger/b6/`; the pedestal's build is `lens1/`.
`tools/run.sh ship --shoot DIR --charger` places this GLB (and a crystal) on both renewer spots for the look review.

1. **The numbers.** `tools/blender/charger_dims.toml`: the drawing's own (the deck at its "base top" 99.1, the widest
   Ø 100.4 at 72.8, the upper tier's top edge Ø 82, the slot at 95.7, the button Ø 8 at 75.9, the outer prongs to
   139.7 at u 23.9.., the inner pair to 123.1 on the track ring of r 19, the legs lengthened 27 cm in their pistons)
   and the smaller ones
   read off the sheet (block angles, seams, bevels, bezels, strip widths, the legs' joints). **The wall is not flat
   there**: the spot sits on a vertex of the lens room's 12-sided wall, whose facets fold toward the room by 10.98
   degrees either side. The round base stands clear of it (the axis 53.5 cm out, the widest circle 2.3 cm off the
   facets); the back legs turn to 120 degrees and tuck in to r 52 so their pads stay 3 cm off (at 135 they would
   stand in the wall). Step 3 (build b6) made the base heavy, as on the sheet (b5, its deck at 94 and its underside at
   the drawing's 64.8, read as a thin table on stilts): the deck at 99.1 with the slot sunk in a well whose floor is
   b5's deck (94: the track ring, the slot ring, the collar's foot; the well's wall is the deck ring's inner chords);
   the lower tier taller (a skirt down to 60, 4.8 under the drawing's underside, so the legs read as struts under
   it; its band to 83) and broader (the underside's edge r 45, the upper tier r 43). The slot, the button, the prongs'
   tops, the footprint and the clearances are unchanged.
2. **Build from the numbers.** `tools/blender/charger_build.py` (headless Blender): each tier is a ring of bronze
   blocks, a profile swept straight between two angles (flat chord faces), thin dark seams onto a graphite core, two
   bevels per block (a broad chamfer, UV0 u 0.45, and a small bright bevel on its folds, u 1:
   `console_metal.gdshader` brightens both). The front block's pieces (strips and wedges round the button's
   trapezoid facet) lie on the block's own chords, one planar prism per band of the profile, so nothing juts out of
   its neighbours (b4's panels did). The prongs are (r, h) claw profiles swept round the crystal's axis over a few
   degrees (their end faces toward the room carry the strips); the legs are octagonal prisms along each leg's axis
   (strut, glands, the steel rod, the ankle sleeve) on a faceted pad. Lights sit in graphite bezels, inset, unbevelled
   (the bevels on 70 small boxes cost 11k triangles). The leaves are their own objects, pivots on their axes, children
   of the body: `carrier` (the cup with the pit for the crystal's point; the empty `crystal_anchor` at the tip),
   `track_ring` (with the inner prongs and their electrodes), `button`. Convex colliders (`*-convcolonly`): the base,
   the outer prongs, each leg, and the inner prongs on the ring. The build checks the clearances numerically
   (`build.json` `checks`): every vertex in front of the wall's facets, the ring's full turn in 5 degree steps against
   the body (BVH overlaps), the carrier's rise in 1 cm steps, the button pressed, the crystal at rest and risen.
3. **The look in Godot**: `godot/charger/charger.gd` (`apply`, `set_state` idle / charging / charged, `set_carrier`,
   `set_ring`, `set_pressed`, `seat_crystal`). The bronze and graphite are the console's `console_metal.gdshader`,
   shared (the asset's `export/` carries the same file; the test checks it is byte-identical). The charger draws on
   render layer 20 alone and `seat_crystal` takes that layer off the crystal's own light, which otherwise burns the
   bronze white a few centimetres away (the socket's way); a soft cyan light of the charger's own stands in while
   charging. The bronze is the socket's step 3 (`BRONZE`, `BRONZE_FINISH`: the same numbers as `socket.gd`), so the
   stations match. The Blender review render is a darker studio under AgX Punchy (the plain AgX and a bright studio
   paled the amber to cream and the bronze to tan).
4. **The shots**: `godot/charger/room.gd` extends `godot/ship/ship.gd`'s shoot mode with the charger on `renewer_e`
   and the crystal seated, on the ship's current build (`--pieces`, default `ship.toml`'s `raw_dir` pieces,
   `<raw>/ship/v5/pieces/`; steps 2 and 3 shot on the same bytes in `<raw>/ship/v4/vents-b/pieces_b5b`; the run
   refuses pieces whose lens room floor, `tip_floor_rim`'s top through its nodes' transforms, is not at `floor_h`); `godot/charger/sheet.gd` makes `compare_sheet.png` (the sheet's hero view, Blender's
   neutral render at its angle, Godot in the room), `room_sheet.png` (the states, a player's view, the pass behind
   them, the straight views, the back toward the wall, the legs, the ring's turn from above) and `closeups.png`
   (Blender's close-ups of the seams: the prongs' roots and caps, the hips, knees and feet, the slot, the button), and
   measures the GPU cost.

   ```bash
   $PYTHON_BIN tools/blender/charger_run.py --tag <tag> --res 900 --samples 64 --asset assets/prop/crystal_charger
   ```

`tools/tests/test_props_crystal_charger.py` checks the drawings' numbers, the pedestal inside the alcove (the ring's
gap to the back panel, the lips inside the cheeks and the reach, the alcove's `AXIS_D` and `REACH`), the wall's fold
against the ship's layout and the committed asset (its reach at most 70 cm, the spots' `depth_m` 0.70).

## What the stations' bronze costs (art#263, fix pass 2; option A shipped)

The shared metal shader's `dent` and `wave` slopes (fix1's smooth gradient noise) are measured, not guessed:
`tools/blender/metal_cost_run.py` places the four approved exports in the built ship at night as their own drivers do
(no crystals) and runs `godot/ship/metal_cost.gd` (ship.gd's shoot mode, `_godot.window()`, 1920x1080, vsync off).
Per view (each station's own close view, its player's view and a close-up where bronze fills the frame) it takes the
median GPU ms of 3 alternating rounds of 120 frames with the shader as shipped, with `dent` = `wave` = 0, with one
octave, with the slope as it shipped before option A (`metal_cost.gd` `FINITE`, the forward difference) and with that
view's station hidden. It saves each variant's frame, a before/after strip per view (`<view>__compare.png`: before
option A | shipped | difference x8, the whole frame; `<view>__compare_crop.png`: the frame's middle 640x360 at 1:1)
and, per console view, the console alone before and after (`<view>__solo_compare.png`) with `solo_identical` in
`cost.json`.

Fix pass 2 measured the slope as fix1 shipped it (`<raw>/ship/v4/stations-fix2/cost3/`, RTX 4060): a forward
difference of the two-octave field, four field() calls of 16 hashes, 64 hashes per slope. The stations ship `wave` 0.3
and `dent` 0, so one slope runs on their bronze: 0.35 (board) and 0.46 ms (charger) in the player's views, 1.3 to 1.6
ms when bronze fills the frame.

**Option A** (the engineer, 2026-10-26: "the same noise through the exact derivative, a quarter of the cost"): slope()
now takes the gradient noise's analytic derivative, `gnoised()`, one pass over the cell's 8 corners per octave, 16
hashes per slope; same lattice, hashes, quintic fade, turns, octaves, strengths, parameters, defaults and guards. The
gradient is taken at the old forward difference's midpoint (`p + 0.15 / s`), so most glints stay near where they were,
but the exact slope is not the forward difference's smoothed one: the glints move and change shape, visibly in close-ups (a mean pixel change up to 8/255, about as much as switching
the bend off; `cost.md`), the same at a player's distance (accepted by the engineer, 2026-10-26).
The console (`dent` = `wave` = 0) skips the slope and stays pixel-identical (`console_*__solo_compare.png`, max 0).
Measured once (2026-10-26, `<raw>/ship/v4/bronze-a/cost/cost.md`, RTX 4060), GPU ms before -> after: board player's
view 4.849 -> 4.641 (-0.21), charger player's view 4.932 -> 4.688 (-0.24), the bronze-filled close-ups -0.59 (socket),
-0.84 (board) and -1.04 (charger). This run's noise reaches about 0.5 ms (the GPU clock drifted between rounds: the
console control's views, where both shaders draw the same pixels, read the new one 0.47 ms slower and 0.21 ms faster), so a single row under
about 0.3 ms is noise; the player's-view savings (0.21 board, 0.24 charger) are consistent, within that noise, with fix pass 2's
prediction (0.26 and 0.34 ms).
