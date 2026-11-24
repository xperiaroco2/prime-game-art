# The M8 clearing's ground: handoff

The ground of the M8 round's clearing (prime-game#1704, art #263): the **landing pad** the engineer picked on
2026-11-24 ("Так, майданчик") from the review page's four looks. A round pad of dark cold-steel plates round the ship,
with seams and four bolts per plate, a 0.5 m trim band with a thin teal light ring at 18 m, four yellow hazard
chevrons before the ramp's foot, and dark blue-grey regolith with gravel beyond. It is one procedural shader with no
textures, as shown on the page; nothing about the look changed for the package.

Tag: **`clearing_ground/v1`** (this folder on the art repo's `main`).

## Files

| File | Game path | What |
|---|---|---|
| `export/clearing_ground.gdshader` | `res://assets/environment/clearing/clearing_ground.gdshader` | The spatial shader: world xz drives everything, so any mesh whose top is the ground plane works; no UVs, no texture reads |
| `export/clearing_ground.tres` | `res://assets/environment/clearing/clearing_ground.tres` | The `ShaderMaterial`: `pad = true`, `centre = Vector2(116, 72)` (the ship's origin in `levels/clearing/clearing.tscn`); every other uniform at the shader's default |
| `package.json` | | The two files, what they replace, the pad's numbers |
| `report.json` | | GPU ms and draw calls per view against today's greybox, the package's shots against the review page's, the files' hashes |

## In the game

- **Copy** both files to `res://assets/environment/clearing/`. The `.tres` refers to the shader by that path; Godot
  writes the `.uid` files on import.
- **Swap:** in `levels/clearing/rooms/ground.tscn`, replace the `Material` ext_resource (today
  `uid="uid://d1t1jgv22rrqu" path="res://levels/kit/greybox_floor_garden.tres"`) with one for
  `res://assets/environment/clearing/clearing_ground.tres`, **uid included**: Godot resolves an ext_resource by its
  uid before its path, so editing the path alone keeps the greybox. Either reassign the mesh's material in the editor
  and save, or write `[ext_resource type="Material" path="res://assets/environment/clearing/clearing_ground.tres"
  id="1_garden"]` with the `.tres`'s own uid once Godot has imported it (or no uid). The `BoxMesh` 200 x 1 x 200 m,
  its transform (top at y 0) and the `BoxShape3D` collider stay as they are. Leave `greybox_floor_garden.tres` itself
  alone: `levels/estate/rooms/plot.tscn` uses it too.
- **Place:** the pad is drawn at the shader's `centre`, world x 116, z 72, where `clearing.tscn` puts `Ship` and
  `Ground`. If the ship moves, set `centre` to its new world xz. The chevrons assume the ship unrotated, its ramp
  toward -z (its foot 12.6 m in front of the centre, `ramp_foot`). In `markers.tscn` the ten RoundPlayer markers lie 11.9 to
  15.2 m from the centre and Respawn1 and 2 at 16.0 m, all on the pad (`pad_r` 18 m); the four Knife markers, 28.3 m
  out, stand on the regolith beyond.
- **Light and fog:** made for `levels/clearing/rooms/sky.tscn` as it is (background (0.42, 0.45, 0.5), fog density
  0.035, no light of its own). The teal ring is emissive (energy 1.6); it adds no light.
- **No collision change:** the material only draws; the plates have no relief.

## Cost

Measured in an off-screen Godot 4.7.2 window at 1280 x 720, the art ship package v12 (`ship/v5/export/v12`) with the
game's frees, the median of 20 frames per view:

| View | Today (greybox) | Landing pad | Difference |
|---|---|---|---|
| Round start, RoundPlayer01 | 2.56 | 2.22 | -0.34 (noise) |
| Round start, RoundPlayer02 (the validator's) | 2.41 | 2.70 | +0.29 |
| Behind the spawn rows | 2.51 | 2.52 | +0.01 |
| The ship, 22 m out and 6 m up | 2.48 | 2.87 | +0.39 |
| The ground at the ramp, looking down | 3.31 | 3.90 | +0.59 |

GPU ms on this machine (`report.json`). The review page's own run the day before (not in `report.json`) measured +0.26 ms at the round start and +1.03 ms at the ramp's
ground, so count on **about +0.3 ms in a normal view and up to about +1 ms when the ground fills the screen**. The
numbers are noisy at this size; a frame's own spread is about 0.3 ms.

The draw calls do not change (the same one box, one material). The shader has no texture reads; its cost is the
regolith's noise and stone cells on every ground pixel, which is why the close view at the ramp, mostly ground,
costs the most.

## Proof

`tools/review/clearing_ground_looks.py --package` stages these two files into the art repo's Godot project with
their game paths rewritten, puts the `.tres` on a `BoxMesh` exactly like `ground.tscn`'s, and shoots it from the
review page's views beside the page's own pad look. The mean pixel difference is 0.000 of 255 in four views and 0.006 in
the fifth, so the package draws what the engineer picked. The shots are in
`<raw>/clearing/ground/v1/` (`package/round_start_p02.png` is the validator's round-start view from RoundPlayer02).

## Provenance

`manifest.toml`: own work, written as code (the shader) in this repo; no AI generation, no download, no texture.
Public repo ok.
