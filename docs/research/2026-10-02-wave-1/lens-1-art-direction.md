# Lens 1: art direction and references (prime-game art track, #165)

Researched 2026-10-02 by a read-only web agent. Every claim has a source. `[unconfirmed]` = no primary source
opened (fan wiki, third-party blog, video summary, memory or inference). Budget: ~35 tool calls; breadth on minor
games was dropped first (Lockdown Protocol and Mage Arena have thin primary material).

## 1. Reference games

### Fall Guys (Mediatonic)
- Origin: the body came from "a chunky little yeti-shaped vinyl toy"; characters are deliberately small on screen
  because many are shown at once, so "little details can get lost" and designs are simplified; the team pushes even
  pastels to strong saturation and recommends "testing designs at distance". Source (developer post):
  https://blog.playstation.com/2020/05/25/creating-the-character-designs-of-fall-guys-out-on-ps4-this-summer/
- Costumes double as identification: patterns and costumes "help you see your Fall Guy" in a crowd; a good costume
  looks "both ridiculous when they win and hilarious when they fail". Same source.
- The bean shape: "a humanoid form felt too aggressive, a circle too simple"; the bean was "funny when it fell".
  Source: https://www.gamesradar.com/fall-guys-interview/ (third-party interview, via search summary) [unconfirmed]
- Anatomy joke art (dangling eyeballs inside the suit) by concept artist Tudor Morris:
  https://designtaxi.com/news/411684/ [unconfirmed]
- Proportions (my reading of the shape): a single head-body capsule, head and body fused (1:1 "bean"), tiny stub
  arms and legs, mitten hands, two simple eyes and a mouth. Customization: colour, pattern, face plate, full-body
  costumes, upper and lower costume halves. [unconfirmed: memory]

### Gang Beasts (Boneloaf)
- Animation is physics because "we don't have an animator"; "we messed around with the physics, and just slowly
  evolved the character from that". Short legs because an invisible ball between them moves the body and handles
  ground collision; no feet (they caught on geometry); solid colours were placeholder art the audience embraced;
  white eyes exist to show the facing direction; no neck. Source (developer interview, MCV):
  https://mcvuk.com/business-news/when-we-first-started-we-didnt-really-know-what-we-were-doing-how-gang-beasts-became-an-international-success/
- "Gelatinous" bodies, oversized heads, slapstick: https://thenvm.org/games/gang-beasts/ (museum page)
- Customization: costumes and colours on the same blob body. [unconfirmed: memory]
- Lesson for us: the "eyes show facing" detail matters in a first-person game where look direction is relayed.

### Human: Fall Flat (No Brakes Games)
- Bob: a white, featureless, semi-amorphous humanoid; players paint him and dress him in costumes.
  https://en.wikipedia.org/wiki/Human:_Fall_Flat [unconfirmed: wiki]
- The fun was found by watching a child ignore the puzzles and "parkour or walk around" laughing; "multiplayer was
  actually when the game exploded". Source (developer interview):
  https://www.thegamer.com/human-fall-flat-interview-tomas-sakalauskas/
- Physics-driven arms with independent control; each movement sways and tumbles:
  https://news.xbox.com/en-us/2016/03/17/gdc-2016-human-fall-flat-xbox-one/ (platform blog, via search) [unconfirmed]
- Look: soft, plasticine-like body, simple flat-ish lit materials, blank face. The blank body is a canvas.

### Lethal Company (Zeekerss)
- Look: low-poly models plus modern effects; renders at a fixed low resolution (about 860x520), deferred PBR
  lighting, volumetric fog, a custom posterization filter, dual edge detection (outlines), depth of field, bloom and
  grading; the visor seen in first person is a separate 3D model. Source: Acerola's breakdown summarised by 80.lv:
  https://80.lv/articles/how-to-achieve-lethal-company-s-graphics-with-unity-hdrp [unconfirmed: third-party analysis]
- Identity: everyone starts in the same orange suit; purchasable suits (brown, green, purple, hazard, bee, bunny,
  pajama) are shared through the ship wardrobe; colours are used to tell crewmates apart in dark facilities.
  https://lethal-company.fandom.com/wiki/Suits , https://www.thegamer.com/lethal-company-all-suits-guide/ [unconfirmed]
- Humour comes from voice and failure (a friend's voice cut off mid-sentence, the ragdoll left behind), not from a
  funny body; the body is a plain adult worker in a suit. [unconfirmed: inference]

### Content Warning (Landfall; five developers, about three months)
- Players wear identical diving suits; the face is a visor showing up to three typed characters (ASCII emoticon),
  with a visor colour from a preset palette, rotation and size. Humour: "your friends looking and acting silly",
  "physics-animated monsters". Sources: https://landfall.se/content-warning-press-kit (publisher press kit),
  https://en.wikipedia.org/wiki/Content_Warning
- Lesson: a "screen for a face" is the cheapest expressive face: one material parameter or a small texture, no
  facial rig, endlessly customizable by players, readable at mid range.

### R.E.P.O. (semiwork)
- Semibots: small robots, a semicircular head split in two with the top hinged at the back; the top bounces when
  the player speaks into the mic; big googly eyes with tiny pupils; colour variants; typed chat becomes
  word-by-word TTS. Sources: https://repogame.fandom.com/wiki/Semibots ,
  https://en.wikipedia.org/wiki/R.E.P.O. [unconfirmed: the Steam page does not describe the mouth;
  https://store.steampowered.com/app/3241660/REPO/ confirms proximity voice, physics grabbing and "player
  customization"]
- Lesson: the voice-driven hinged head is THE reference for "who is talking" at a glance; googly eyes add free
  secondary motion.

### Totally Accurate Battle Simulator (Landfall)
- Active ragdoll units: behaviour emerges from centre of mass and joint torques; small units are top-heavy on
  purpose to look clumsy. https://en.wikipedia.org/wiki/Totally_Accurate_Battle_Simulator ;
  https://shapes.inc/fandom/totally-accurate-battle-simulator/deep-dive [unconfirmed]
- Look: chunky simple bodies, big round heads, dot eyes, flat colours, faction colours for readability. [unconfirmed]

### Goat Simulator (Coffee Stain)
- Kept every funny physics bug; fixed only crashes and gameplay-breaking ones: "We're not removing any bugs that
  are funny". Source (developer interview): https://cliqist.com/2014/03/06/armin-ibrisagic-talks-goat-simulator/ ;
  https://news.xbox.com/en-us/2015/04/21/games-chatting-about-purgatory-and-glitches-too-good-to-remove-in-goat-simulator/amp/
- Lesson: the comedy of a stiff, realistic-ish body doing physically absurd things (the long goat tongue, ragdoll
  flights). For us only cosmetic ragdolls are allowed (the host owns positions).

### Added: PEAK (Aggro Crab with Landfall)
- Developer statement: first-person cameras "push players to really embody their characters", and the game
  "enhances the impact of proximity chat—with eyes following players and mouths animating with speech"; dead players
  stay in voice as ghosts. Source (developer talk, Game Developer):
  https://www.gamedeveloper.com/business/peak-co-developer-aggro-crab-shares-lessons-in-friendslop ;
  https://www.pcgamer.com/games/adventure/peaks-success-helped-aggro-crab-commit-to-co-op-says-studio-head-we-thought-we-were-a-character-action-studio/
- Look: big-headed "scout" kids-camp characters, simple faces, bright colours, floppy climbing ragdolls.
  [unconfirmed: memory]

### Added: Party Animals (Recreate Games)
- Inspired by Human: Fall Flat and Gang Beasts; punches resolve by position, speed and stamina; fur meant to look
  like a small real animal, not a stuffed toy; some animals were cut for clashing styles.
  https://en.wikipedia.org/wiki/Party_Animals_(video_game) ; https://goombastomp.com/party-animals-interview/
  [unconfirmed: summary]
- Lesson: fur shading is expensive and off-brand for "cheap low poly"; skip.

### Added: Among Us 3D (Schell Games with Innersloth) and Among Us
- First-person social deduction with native proximity voice on PC and VR: https://schellgames.com/portfolio/among-us-3d
- Innersloth on colour: expanding the palette was impossible because players got hard to tell apart; they planned
  "other identifiers for players" for colour-blind support: https://innersloth.itch.io/among-us/devlog/181107/the-future-of-among-us
  (developer devlog). A "Colorblind Text" setting (2022) shows colour names over characters, in chat and meetings:
  https://among-us.fandom.com/wiki/Colors [unconfirmed: wiki; the official help page returned 403]
- Lesson: in social deduction, the player colour is a NAME players say out loud ("Red is sus"). It must be nameable,
  so each colour needs a short spoken name and a non-colour backup.

### Added: Lockdown Protocol (Mirage Creative Lab) and Mage Arena (jrsjams)
- Lockdown Protocol: first-person social deduction for 1 to 16 players, continuous (no static meetings), proximity
  voice that accounts for obstacles and distance: https://store.steampowered.com/app/2780980/LOCKDOWN_Protocol/ ;
  the look is "gritty sci-fi" (third-party) https://screenrant.com/lockdown-protocol-gameplay-mystery-party-game/
  [unconfirmed]. The nearest genre competitor: a grim look leaves the goofy space open.
- Mage Arena: spells cast by speaking into the mic, proximity voice is "the heart of the experience":
  https://www.dexerto.com/uncategorized/chaotic-pvp-wizard-game-lets-you-cast-spells-by-shouting-into-your-mic-3231435/
  [unconfirmed]

## 2. What makes these games funny to look at (synthesis)
1. A body that fails visibly: physics or floppy limbs reacting to failure (Gang Beasts, HFF, TABS, Goat Sim).
   Comedy needs a readable silhouette so the fall reads at distance.
2. Childlike toy proportions: big head, short limbs, no neck, mitten hands (Fall Guys, Gang Beasts, TABS, PEAK).
   They read as harmless, so violence and death read as slapstick rather than gore; this suits a mixed audience.
3. A face that reacts to the real person: voice-driven mouths (R.E.P.O., PEAK), eyes that show facing (Gang Beasts),
   player-authored faces (Content Warning).
4. The costume contrast: a silly costume during a dramatic moment (Fall Guys "ridiculous when they win").
5. Plain colour identity (Gang Beasts, Among Us, Lethal Company suits).
6. Lo-fi charm (Lethal Company, Content Warning): low resolution, posterization and outlines make cheap assets look
   intentional.

## 3. Distance maths for prime-game (inference)
At 1080p with a 90° horizontal FOV (about 59° vertical at 16:9), the visible height at 20 m is about
2 × 20 × tan(29.5°) ≈ 22.6 m, so a 1.8 m character is about 86 px tall and its head 20 to 30 px. At 20 m only body
colour, large silhouette features (a hat, a big head, a backpack) and big shapes read; faces, patterns under 10 cm
and thin outlines do not. A dim room removes hue before brightness: identity needs a light or emissive accent or a
rim term. [unconfirmed: my calculation]

## 4. Three candidate style directions

### A. "Squishy toy crew" (Fall Guys + Gang Beasts + PEAK/R.E.P.O. faces)
Chunky vinyl-toy people: a big head (head to body about 1:2), a soft rounded torso, short thick limbs, mitten hands
with a thumb (so a held knife or package reads), no neck. Face = two big eyes plus a mouth that opens with the
player's voice level; eyes look where the player looks (pitch is already relayed). Identity = one strong body
colour per player plus one big silhouette accessory (hat, mask, backpack).
- Godot 4.7 Forward+ recipe: low-poly mesh with smooth normals on the body (toy look); one shared palette texture
  (e.g. 16×16 swatches) with UVs snapped into swatches, or vertex colours (`vertex_color_use_as_albedo`); player
  colour as a per-instance shader parameter that tints a mask channel; `diffuse_mode = DIFFUSE_TOON` (a hard light
  cut, smoothed by roughness) plus `rim` for separation in dim rooms; optional `stencil_mode = STENCIL_MODE_OUTLINE`
  (needs connected faces with shared vertices) or an inverted-hull `next_pass` with `grow`. A coloured ramp needs a
  small custom spatial shader `light()`. Docs: https://docs.godotengine.org/en/4.7/tutorials/3d/standard_material_3d.html ;
  names checked in tools/out/godot-api/4.7.2/extension_api.json (DIFFUSE_TOON, STENCIL_MODE_OUTLINE,
  stencil_outline_thickness, grow_amount, next_pass, rim_tint, FLAG_ALBEDO_FROM_VERTEX_COLOR, set_blend_shape_value).
- 20 m: best of the three (big colour mass, big head silhouette). Dim room: good with rim plus an emissive accent
  (eyes or a name badge).
- Cost: lowest. Simple closed shapes are what AI generators and decimation handle best; one base body, the face
  is a texture plus one blend shape or a jaw bone; costumes are rigid head and back attachments.
- Asset-flip risk: medium. "Bean with eyes" is crowded (Fall Guys, Among Us). Mitigation: a distinct silhouette of
  our own (a real neck-less but legged body with hands, not a bean), our own face language, never prompting
  generators with other games' names.
- Tone: goofy, cute, gender-neutral; violence reads as slapstick.

### B. "Workwear crew with screen faces" (Lethal Company + Content Warning + Among Us 3D)
Adult-ish workers in coveralls or suits with a helmet whose visor shows a player-chosen emoticon face (the face
animates with voice). Head to body about 1:4 to 1:5, slightly oversized helmet and gloves. Identity = suit colour,
visor colour and face, helmet decals.
- Godot recipe: flat or PBR-lite albedo from a palette texture, standard lighting with posterization or a reduced
  internal resolution (`Viewport.scaling_3d_scale`) as a post look, an outline post pass, an unshaded or emissive
  visor (`SHADING_MODE_UNSHADED`) so faces glow in the dark.
- 20 m: good (suit colour), and the glowing visor reads in a dim room. Close: the face screen reads very well.
- Cost: low to medium. One base body; the face is a texture, no facial rig. Clothes are the body.
- Asset-flip risk: high. "Orange suit, visor, friendslop" is the most copied look since 2023; it also leans
  horror/grim and more "guy" than our audience target.

### C. "Wobbly mannequins" (Human: Fall Flat + TABS + Goat Simulator)
Smooth, nearly blank soft-clay humanoids (head to body about 1:3), little or no face, the body painted by the
player; the comedy comes from floppy secondary motion and cosmetic ragdolls (downed and dead bodies).
- Godot recipe: `DIFFUSE_TOON` or default lambert with high roughness, flat colour per part, soft AO; physical
  bones for downed/dead (cosmetic only).
- 20 m: good silhouette, but identical blank bodies are hard to tell apart without hats; no face for voice.
- Cost: medium. Cheap meshes, but the comedy rests on physics animation work (the most engineering-heavy part).
- Asset-flip risk: medium; can look like a placeholder mannequin.

### Recommendation (the look is the humans' call)
A, "Squishy toy crew", with B's best idea borrowed as an option: the face is a texture-driven face (eyes plus mouth
as a small atlas or a screen-like face plate) so faces are cheap, customizable and voice-reactive. Reasons:
the 20 m readability, the lowest production cost, the goofy inclusive tone, and the voice-reactive mouth that shows
who is speaking (a social deduction feature, not only a joke). Use C's cosmetic ragdoll only for DOWNED and DEAD
bodies, settled where the host placed the body. Avoid B as the main look (crowded, grim).

## 5. Voice-driven faces and bodies
- R.E.P.O.: the hinged top of the head flaps with mic level (fan wiki) [unconfirmed].
- PEAK: "eyes following players and mouths animating with speech" (developer statement, primary).
- Content Warning: player-typed emoticon faces on a visor (primary); voice-driven animation not confirmed.
- Why it is funny: the avatar becomes a puppet of the real voice; shouting makes a huge mouth; a whisper is a tiny
  twitch; it also tells you WHO is talking in a crowd, which a first-person game otherwise lacks.
- Implementation sketch (engineering; inference): each listener computes the RMS of the voice frames it actually
  plays for each speaker and drives a mouth blend shape (`MeshInstance3D.set_blend_shape_value`), a jaw bone, or a
  face-atlas frame, smoothed (attack about 30 ms, release about 120 ms). Hidden-information rule: drive it from audio
  the listener HEARS, never from a host-wide "is speaking" flag, or a mouth moving on a channel you cannot hear
  (for example a private impostor channel, if one exists) leaks information (architecture invariant 2 and 6).

## 6. Readability and inclusivity
- Colour-blind safe base: Okabe-Ito, eight colours: #E69F00 orange, #56B4E9 sky blue, #009E73 bluish green, #F0E442
  yellow, #0072B2 blue, #D55E00 vermillion, #CC79A7 reddish purple, #000000 black. Primary: https://jfly.uni-koeln.de/color/
  (not opened; hex values from https://conceptviz.app/blog/okabe-ito-palette-hex-codes-complete-reference) [unconfirmed].
  Ten players exceed any safe hue set: Among Us hit exactly this wall (devlog above).
- Therefore every player needs a second, non-colour identifier: (1) a big silhouette accessory (hat, ears, mask),
  (2) a large pattern on the body (stripes, dots, checks), (3) a colour name and player name shown on aim, as
  Among Us's "Colorblind Text". Also vary luminance across the ten colours (light, mid, dark) so they differ in
  greyscale; check the set with a deuteranopia/protanopia simulation of a `shot` render.
- Body variety: offer body shapes (round, tall, small) and heights as cosmetic variation within one shared
  collision capsule (gameplay stays identical); no gendered defaults, all items available to all bodies; avoid
  macho proportions (the toy body is neutral). [inference]
- Goofy, not macho: emotes and failure animations should be self-deprecating (fall flat, wave, flop), not taunts.

## 7. Legal: "in the style of"
- Copyright protects expression (artwork, specific character designs, code, music), not ideas, rules or genre
  conventions (scènes à faire). Stereotyped characters were filtered out (Street Fighter II v. Fighter's History),
  but a clone whose look was "so similar as to be easily confused" infringed (Tetris v. Mino/Xio). Source: an IP
  attorney's summary, https://www.gamedeveloper.com/business/clone-wars-the-five-most-important-cases-every-game-developer-should-know ;
  https://en.wikipedia.org/wiki/Spry_Fox,_LLC_v._Lolapps,_Inc.
- May take: general ideas (big heads, short limbs, saturated colours, toon shading, a visor face, a voice-flapping
  mouth, ragdolls).
- Must not take: a recognisable character's specific design (the Fall Guys bean with its face, the Among Us
  crewmate's bean-with-visor-and-backpack silhouette, Semibots' hinged half-dome with googly eyes as a whole),
  names, logos, costume designs, or UI. Trademark/trade dress on those silhouettes is likely [unconfirmed: not
  checked in trademark registers]. Not legal advice.
- Production rules: never prompt an AI generator with another game's or character's name; keep a reference board
  of real objects (vinyl toys, workwear) rather than screenshots for generation; review every new character
  silhouette side by side with the reference games before approval.

## 8. Licenses touched
- Godot built-in materials and shaders: MIT, https://godotengine.org/license/ , commercial yes, attribution in
  credits/license text, public repo yes.
- Okabe-Ito colour values: colour values are facts; free to use [unconfirmed: no license page opened];
  https://jfly.uni-koeln.de/color/
- No third-party asset is recommended by this lens.
