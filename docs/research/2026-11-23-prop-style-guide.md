# The prop style guide (v1, 2026-11-23)

**Status:** approved with the hero-prop pipeline, the engineer's "Так, приймаємо" of 2026-11-24
(`docs/decisions/2026-11-23-hero-prop-pipeline.md`). Changes to the palette or the shape rules are his taste: ask.

One page of rules every prop, held item and later weapon follows, so agents building one piece at a time make a set
that belongs together and belongs in the ship and the lobby. It writes down what the engineer has already approved:
- the lobby's S4 scheme (two-tone teal-grey, cold steel, orange strips, no copper);
- the ship's steel;
- the concept prompts' wording;
- his picks so far (the stein, the crystal, the pinball, the console).

The critic's rubric item 8 ("style fit") is judged against this page and the prop's approved concept
(`docs/research/2026-11-23-prop-critic-rubric.md`).

## 1. Shape language
- **Clean, bold, readable.** These are the concept prompts' words, and the engineer approved them:
  - clean bold readable shapes, slightly exaggerated proportions, crisp bevels;
  - rich materials, cool and stylish, never childish;
  - made by an advanced civilisation, but its use is obvious at a glance.
- **Silhouette first.** Shrunk to 64 px and filled black, the prop must still say what it is. One dominant mass, one
  or two secondary masses (a handle, a head), small details last.
- **Proportions: 60/30/10.** Big, medium and small forms take about 60, 30 and 10 % of the surface. Avoid evenly
  sized parts and long thin bits that alias at distance.
- **Panels and facets** are the house motif: the lobby's panelled walls, the stein's pillow panels, the crystal's
  facets. Panels have rounded ends and grooves, never sharp knife edges.
- **Bevels on every silhouette edge** in the geometry, by scale:

  | Scale | Bevel |
  |---|---|
  | Hand props | 1.5–3 mm |
  | Furniture | 5–10 mm |
  | Architecture | 15–30 mm |

  Smaller detail goes into the baked maps.
- **No text, no logos, no brands** on any prop.

## 2. Palette (linear RGB as the builds use it; from `layouts/lobby/hall.toml` S4)

| Role | Colour | Where |
|---|---|---|
| Panel | teal-grey 0.35, 0.42, 0.42 | Large painted surfaces |
| Frame | graphite-teal 0.25, 0.30, 0.31 | Frames, housings, handles' cores |
| Trim | cold steel 0.60, 0.64, 0.66, metallic 0.85 | Bands, rims, bolts, functional metal |
| Dark | 0.06-0.09 neutral | Rubber, polymer grips, channels |
| Warm light | orange 1.0, 0.52, 0.26 (emissive 1.5-2) | Ambient and structure light: strips, status at rest |
| Energy | cyan 0.15, 0.85, 1.0 (emissive 1.5-2.5) | Power and interaction: crystals, charge, active tools |
| Hazard | yellow-black stripes | Danger edges only |
| Alarm | red 1.0, 0.08, 0.04 | Alarm and stop lamps only |
| Liquids | amber beer 0.34-0.95 gold (measured on the approved stein) | Drinks |

Rules:
- **No copper or bronze.** The engineer called them retro (2026-11-23); warm metals are gone from the set.
- **Colour is functional.** Orange means structure and ambience; cyan means energy and interaction; red means alarm.
  A prop's emissive colour says which it is.
- **Values stay in range.** Base colours stay between 0.04 and 0.9; no pure black and no pure white. A prop reads
  in the lobby's warm pendants and in the window's cold light alike.
- **Saturation** is reserved for emissives, liquids and the hazard/alarm colours. Painted surfaces stay at
  saturation 0.1-0.25.

## 3. Materials (the shared library: Blender node materials for opaque props, Godot shaders for glass, liquids, foam)

| Class | Metallic | Roughness | Notes |
|---|---|---|---|
| Painted metal | 0.3-0.5 | 0.4-0.6 | Edges a touch lighter and smoother (worn paint) from the baked edge mask; cavities darker from baked AO |
| Brushed steel | 0.85-1.0 | 0.25-0.45 | A faint directional brush; brightest on edges |
| Polymer / rubber | 0 | 0.6-0.85 | Grips and bumpers, dark; a fine grain or knurl in the normal map |
| Glass | (shader) | 0.02-0.05 | `godot/mug_lab/glass.gdshader`: refraction, edge darkening, studio reflections |
| Emissive | 0 | 0.3-0.4 | Only the front face glows; the housing is dark |
| Liquid, foam | (shaders) | | `beer.gdshader`, `foam.gdshader`: states are uniforms |

- **Wear:** restrained and logical. This is a clean, advanced station: no rust, no grime, no decals. Wear is the
  paint's edges a little lighter and smoother, and the cavities darker. Both come from the Cycles bake of AO and edges
  (`tools/blender/mug_lab_bake.py` shows the method).
- **States** (full/empty, charged/spent, on/off) are shader or material parameters on one model, never separate
  models.

## 4. Level of detail
- **Triangles:**

  | Class | Triangles |
  |---|---|
  | Held hero items (in the first-person hand) | up to 10k |
  | Small world props | up to 3k |
  | Furniture | up to 15k |

  Godot's automatic LODs serve other players' copies; turn them off for shader-shaped meshes.
- **Textures:** 1024 px for held items (seen at 30-40 cm), 512 px for world props, one texture set per prop.
- **Three detail layers.** Primary forms in the geometry, secondary panels and grooves in the geometry or the
  normal map, tertiary bolts and grain in the baked maps only.

## 5. Light and the review stage
- Lookdev happens in the lobby's light: warm pendants (1.0, 0.68, 0.42), the cold window (0.55, 0.7, 1.0) and the
  orange strips. Tone mapping is AgX, as in the game.
- Every prop is checked at first-person distance (the 50 degree viewmodel lens) and on its surface at eye height.
- A bright, high-key stage hides dark-material problems and a black stage exaggerates them. Review in the lobby's
  own mid-key light.

## 6. Fitting the ship and the lobby
- The same trim steel and the same teal-grey family as the walls. Props are a step more saturated and a step lighter
  than the walls, so they read against them.
- Emissive accents follow the functional colours: a prop the player uses glows cyan when active and stays dark or
  dim orange at rest.
- Scale is real: the stein is 15 cm, the crystal 34.9 cm. Hands are the alien's real size (`fp_hands`).

## 7. How an agent applies it
1. The concept prompt starts with the house preamble, as in `batches/2026-11-23-lobby-mug-concepts.toml`: "a
   stylised 3D game-art concept render ... clean bold readable shapes ...".
2. The spec takes its colours from the palette table, by role.
3. The build takes its materials from the library classes and its bevels from the scale table.
4. Scripts measure the render against the concept and the palette (`godot/mug_lab/_probe.gd`): hue, saturation and
   value per material.
5. The critic judges item 8 against this page and the concept.

## 8. What the work-light trial added (trial 2, 2026-11-23)
The first prop built to this page (`docs/research/2026-11-23-ai-prop-pipeline.md`, "The opaque prop") showed where
the rules were too soft:
- **Edge wear must read at hand distance.** A′2's baked wear was invisible to both critics ("flat paint"). The edge
  mask for hand props: 2-4 mm wide, value +0.08 over the paint and roughness -0.15; cavities AO 0.6 at the collars.
- **Lights and lenses have structure.** A lit lens is a reflector cup, an emitter at its centre and a clear cover
  under a bezel lip; the emission stays in the emitter (2-3) with a soft falloff, never a flat white disc.
- **Controls sit in panels.** A switch is recessed into a rounded-end panel with a groove, in dark polymer, its
  indicator a small inset lens; nothing is glued onto a surface or runs into a collar.
- **Generators break the palette.** Meshy painted the work light bronze, mint and pale blue under a prompt that named
  teal-grey and steel; its colours are never kept.
