# The ship's crystal charger: handoff to the game

The charger where a player recharges a spent energy crystal (art#263's stations), one in each lens room's alcove on
the aft wall: a faceted bronze pedestal set into the alcove under the head the engineer picked on 2026-10-25
(prime-game#1095 comment 6401197371). Not yet approved by the engineer: the new pedestal's look waits for his yes.

## What changed (antennas round 2 and 2b, 2026-10-29, build `<raw>/ship/v5/charger-antennas/r2b/final2`)

The engineer's note on antennas-1 was "polish the bend and the tip". The outer antennas now rise to 142 (was 139.7)
and turn inward in a smooth arc of 18 thinner chamfered bronze plates (radius 14; antennas-1 had a tight elbow).
Their cyan-lit gaps are even along the arc and glow brighter toward the tip. The last three plates taper, and the tip
ends in a closed lit slot across its end face toward the crystal (no lit square). The inner prongs lost their hook
heads: each now ends in a slim wedge cap that slopes down toward the crystal (top 120), with a lit slot near its
crystal end. The tip electrode sits half sunk in the cap's inner face inside a bronze socket. The electrodes
(`charger_dims.toml` `[inner] electrodes`, `zap.gd` `ELECTRODES`) are now `[14.84, 117.0, 0.9]` (the tip, on the
cap) and `[16.8, 101.0, 1.0]` (the column). A game copy of `zap.gd` must take this version, or its arcs start in
the air where the old hook was.

For the game, nothing else changes: the node names, pivots, leaves, collider names and `charger.gd` are the same.
The glow is `charger_cyan`, so `charger.gd`'s states drive it. 39,896 triangles (`report.json`; antennas-1 had
36,240). Not approved yet: the antennas changed after the 2026-10-28 approval and await the engineer's yes.

## What changed (antennas-1, 2026-10-28, build `lens4`; superseded by round 2 above)

The four prongs (the two outer antennas and the inner pair on the track ring) became stacks of chamfered bronze
plates with thin cyan-lit gaps (the engineer's pick, concept b_fins), and the flat cyan and amber strips on them went.
The ring's surfaces no longer include `charger_graphite` or `charger_amber` (the strips' bezels and light).

## What changed (lens room C, 2026-10-28)

The stepped dome on four legs is gone; the head is unchanged (the slot, the carrier, the track ring, the four
prongs, the Ø 8 button at h 75.9, the deck at 99.1). The pedestal is the lens room's drawing's (prime-game-design
7f335c2, `ideas/ship-components/lens-room/drawing/drawing.js`, `C.ped`): in plan its back u ±44 on the alcove's back
panel at d 10, its sides to d 46, chamfers to the front face u ±22 at d 68; a graphite plinth h 0..10 and a bronze
deck slab h 86..99.1 overhanging the body (1.5 on the sides, 3 on the chamfers, 2 at the front). For the game:

- the crystal's axis moved from 53.5 to **38 cm** out of the wall: the `carrier` and `track_ring` pivots and the
  crystal's anchor moved with it (their heights are unchanged); the `button` pivot is now at d 69.8 (was 99.07);
- the charger reaches **70 cm** into the room (was 105.3): the spots' `depth_m` is 0.70;
- the colliders are `crystal_charger_col0..2` (the pedestal and the two outer prongs; the four legs' are gone);
- `charger_steel` is no longer in the GLB (it was the legs' piston rods); `charger.gd` still knows it, harmlessly;
- `charger.gd`'s own cyan light (`look["glow"]`) sits on the new axis (0, 1.13, 0.38).

Step 3 (lens C, 2026-10-28, build `lens2`): the pedestal's detail after the lens room's `a_power.jpg`, inside the
same plan and heights (the head, the pivots, the colliders and the reach 70 unchanged):

- the plates in three courses: h 10..46, a **recessed band** h 46..52 (the graphite core 1.9 behind the plates, a
  thin cyan line on every plate), 52..66, a seam, the frieze 66..86; the chamfers' cyan strips split per course
  (h 18..42 and 56..82);
- the plinth has a toe set back 1 cm at h 0..1.5 and its top bevelled back to the plates over h 7..10;
- the plates are a new surface, **`charger_bronze2`**: a darker, rougher bronze (`charger.gd` `BRONZE2`,
  `BRONZE2_FINISH`), so the big faces hold under the lens room's warm lamp; the deck slab and the head keep
  `charger_bronze`. A game copy of `charger.gd` must take this version (an older one warns "no look for surface
  material 'charger_bronze2'" and leaves the plates on the GLB's plain fallback);
- 30,520 triangles (was 29,080; 39,896 since antennas 2b).

Node names, the leaves, `charger.gd`'s functions and the render layer are unchanged.

## Files

| File | What |
|---|---|
| `export/crystal_charger.glb` | The body `crystal_charger` (one mesh: `charger_bronze`, `charger_graphite`, `charger_amber`, `charger_cyan`) and its leaves: `carrier` (the bronze cup under the crystal, its cyan ring), `track_ring` (bronze, the cyan channel, the inner prong pair and their electrodes), `button` (`charger_lens`), the empty `crystal_anchor` under `carrier`. Convex colliders `crystal_charger_col0..2-convcolonly` (the pedestal, the two outer prongs; Godot makes them static bodies) and `track_ring_col0..1-convcolonly` (the inner prongs, turning with the ring). Front +Z (out of the wall), Y up, metres. Origin on the floor at the spot's vertex (the wall's face behind the alcove's back panel), on the crystal's axis's line. Its materials are a plain-PBR fallback |
| `export/charger.gd` | The look and the moving parts: `apply(model)`, `set_state`, `set_carrier`, `set_ring`, `set_pressed`, `seat_crystal` |
| `export/console_metal.gdshader` | The bronze and graphite: the start console's shader, the same file (keep one copy beside both scripts) |
| `source/crystal_charger.blend` | The built model (rebuilt from code: `tools/blender/charger_run.py`) |
| `report.json` | Size, triangles per object, pivots, the anchor, colliders, the clearance checks, glTF-Validator, GPU cost |

## Placement: the two spots

`layouts/ship/ship.toml` `[[stations.spot]]` `renewer_e`, `renewer_w`: `at` is the point on the lens room's wall
(plan x, y; Godot x, z), on a vertex of its 12-sided wall, and `normal` the direction into the room. Put the charger's
origin at `(at.x, floor_h, at.y)` (the deck, `floor_h` 1.2 m) and turn it `rotation.y = atan2(normal.x, normal.y)`:

| Spot | at | normal | yaw (deg) |
|---|---|---|---|
| `renewer_e` | (10.2686, 3.2369) | (0.1129, -0.9936) | 173.52 |
| `renewer_w` | (-10.2686, 3.2369) | (-0.1129, -0.9936) | -173.52 |

The charger stands in the alcove (`tools/blender/ship_interior_lens.py` `lens_alcove`, a ship piece): its back on the
alcove's back panel (d 10), its plinth and slab 0.5 cm inside the opening's cheeks (u ±46 at d 10 splaying to ±50 at
d 46). The crystal's axis is 38 cm out; the track ring clears the back panel by 4.4 cm on its full turn. It reaches
70 cm into the room (the plinth's and the slab's front lips; the button's lens 69.95), the spots' `depth_m` 0.70 (the
layout's own stand check).

## The leaves

| Node | Pivot (model frame, m) | Moves |
|---|---|---|
| `carrier` | (0, 0.974, 0.38): the middle of the cup's rim, on the crystal's axis | up `RISE` 0.06 and round its Y axis: `set_carrier(look, rise01, angle)` |
| `crystal_anchor` | under `carrier`, 2.3 cm below its rim, in the cup's pit: the crystal's tip | parent the crystal here with an identity transform (`seat_crystal`) |
| `track_ring` | (0, 0.94, 0.38): the well's floor (the deck at 0.991 round it) on the crystal's axis | round its Y axis: `set_ring(look, angle)`; 0 = the inner prongs left and right |
| `button` | (0, 0.759, 0.698): the lens's face | 1 cm in along -Z: `set_pressed(look, on)` |

The outer prongs and the pedestal are part of the body. The lightning (arcs from the inner prongs' electrodes into the
crystal while it charges) and the crystal's glow are the game's; the art repo's reference for the lightning is
`godot/charger/zap.gd` with `arc.gdshader` (shipped with the ship package as `charger_arc.gdshader`): arcs from the
four electrodes (`charger_dims.toml` `[inner] electrodes`: per inner prong one half sunk in the wedge cap's inner
face at r 14.84, h 117, one on the column at r 16.8, h 101), sparks at the hits, a flash at full charge (`docs/ship.md`, "The charger's
electricity").

## The crystal

```gdscript
const Charger = preload("charger.gd")
const Crystal = preload("crystal.gd")
var look: Dictionary = Charger.apply(charger)
var crystal_look: Dictionary = Crystal.apply(crystal)
Charger.seat_crystal(look, crystal, crystal_look)  # on the anchor; its light skips the charger
Charger.set_state(look, "charging")                # then each frame: set_carrier(look, rise01, a), set_ring(look, b)
Charger.set_state(look, "charged")                 # the carrier back down, the cyan full
Charger.set_state(look, "idle")                    # no crystal or not charging
```

The charger's meshes draw on render layer 20 alone (`charger.gd` `CHARGER_LAYER`): `seat_crystal` leaves that layer out
of the crystal's light's cull mask, which a few centimetres away burns the bronze white. The socket uses the same
layer for the same reason; keep layer 20 free for these, or change both. While charging, the charger's own soft cyan
light (`look["glow"]`) lights the deck and prongs instead.
