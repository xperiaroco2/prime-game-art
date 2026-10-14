"""The task props in the world look (art #82; docs/props.md "Task props in the world look"): fine builders for the
task-station props of props/tasks.toml with `look = "fine"`, on the dressing library's fine pack, paints and [style]
(docs/decisions/2026-10-13-house-world-look.md). Plain Python, like props_task.py, whose primitives it uses.

Two routes:
- RECOLOURED types: the type's own builder (its parts, sizes, lids, states and colliders, checked since #82a) runs,
  then every face's prop or kit paint becomes its fine paint by the spec's `[fine_paint]` (data), and a few parts
  are added (labels, tags, pins) inside the same bounds.
- Own builders where the old piece read as old or as a placeholder: the generator (a present-day canopy genset with
  its on and off state meshes), the computer (a flat monitor instead of a CRT) and the boards other than chalk (the
  pose screen's display, the photo board's cork).
"""

from __future__ import annotations

import props_task as pt
import prop_geom as pg
from kit_geom import Piece

FINE_MATERIALS = (pg.FINE, "glass_tint", pt.SURFACE_MATERIAL)  # the paints a fine prop may use


def recolour(pc: Piece, spec: dict) -> None:
    """Every face's paint through the spec's [fine_paint] (a paint not in it stays: a fine one already)."""
    mapping = spec.get("fine_paint", {})
    for m in pc.meshes:
        m.roles = [mapping.get(r, r) for r in m.roles]


def off_roles(roles, spec: dict) -> list[str]:
    """The paints among roles outside the fine pack, the tinted glass and the game surface (none for a fine prop)."""
    def material(r):
        return spec["roles"].get(r, {}).get("material")
    return sorted(r for r in set(roles) if material(r) not in FINE_MATERIALS
                  and spec["materials"].get(material(r), {}).get("pack") != pg.FINE)


def check_paints(spec: dict) -> list[str]:
    """The spec's [fine_paint]: each paint maps to a fine one."""
    return [f"fine_paint {a}: {b} is not a fine paint" for a, b in sorted(spec.get("fine_paint", {}).items())
            if off_roles([b], spec) or b not in spec["roles"]]


# --- recoloured types: the builder, the paints, a few parts ----------------------------------------------------------
def _box_stack(pc: Piece, p: dict, spec: dict) -> None:
    """Delivery boxes on a clean pallet: kraft boxes with tape and, on the front row of the two lower layers, a white
    delivery label with the burger kitchen's round mark and an orange stripe (the game's own deliveries)."""
    pt.build_box_stack(pc, p, spec)
    recolour(pc, spec)
    m = pc.mesh
    w, d, h = pt._dims(p)
    y = 0.15
    for li, (s, bh) in enumerate(((0.02, 0.42), (0.06, 0.4))):  # the builder's first two layers
        cw = (w - 2 * s) / 2
        for ix in range(2):
            j = ((ix * 7 + 3 + li * 5) % 5 - 2) * 0.006  # the builder's jitter of the front row (iz 1)
            x0 = -w / 2 + s + ix * cw + 0.008 + j
            zf = d / 2 - s - 0.008 - j  # the box's front face
            lx, ly = x0 + 0.06, y + bh * 0.45
            pg.box(m, (lx, ly, zf), (lx + 0.16, ly + 0.11, zf + 0.002), "art_white", "+z")
            pg.box(m, (lx + 0.01, ly + 0.012, zf + 0.002), (lx + 0.15, ly + 0.026, zf + 0.003), "art_terracotta", "+z")
            pg.cyl(m, "z", (lx + 0.04, ly + 0.07), 0.022, zf + 0.002, zf + 0.003, "art_bun", 8, caps=(False, True))
        y += bh


def _wine_rack(pc: Piece, p: dict, spec: dict) -> None:
    """The oak cubby rack of green bottles with red foil, necks out (the builder's), and a white tag on each column."""
    pt.build_wine_rack(pc, p, spec)
    recolour(pc, spec)
    m = pc.mesh
    w, d, h = pt._dims(p)
    body_d = p.get("body_d", d)
    t = 0.035
    cols, _rows = p.get("cubbies", [4, 4])
    zf = body_d / 2
    for i in range(cols):  # a tag on the top rail per column (the year, a white card)
        cx = -w / 2 + t + (i + 0.5) * (w - t) / cols - t / 2
        pg.box(m, (cx - 0.05, h - t + 0.006, zf), (cx + 0.05, h - 0.006, zf + 0.002), "art_white", "+z")


def _bun_shelf(pc: Piece, p: dict, spec: dict) -> None:
    """Boltless steel shelving (black posts, warm steel shelves) with blue bakery crates of buns and a white tag per
    shelf on its front edge."""
    pt.build_bun_shelf(pc, p, spec)
    recolour(pc, spec)
    m = pc.mesh
    w, d, h = pt._dims(p)
    for y in (0.15, 0.68, 1.21):
        pg.box(m, (-0.14, y - 0.026, d / 2 - 0.005), (0.14, y - 0.004, d / 2 - 0.002), "art_white", "+z")


def _parts_shelf(pc: Piece, p: dict, spec: dict) -> None:
    """The car parts on boltless steel shelving: tyres, a battery, a brake disc, oil cans, a headlamp, boxes and an
    exhaust pipe (the builder's), and a white tag per shelf."""
    pt.build_parts_shelf(pc, p, spec)
    recolour(pc, spec)
    m = pc.mesh
    w, d, h = pt._dims(p)
    for y in (0.12, 0.62, 1.12, 1.62):
        pg.box(m, (0.2, y - 0.026, d / 2 - 0.005), (0.46, y - 0.004, d / 2 - 0.002), "art_white", "+z")


def _recoloured(builder):
    def build(pc: Piece, p: dict, spec: dict) -> None:
        builder(pc, p, spec)
        recolour(pc, spec)
    build.__doc__ = f"{builder.__name__} on the fine pack ([fine_paint])."
    return build


# --- own builders ----------------------------------------------------------------------------------------------------
def build_generator(pc: Piece, p: dict, spec: dict) -> None:
    """The generator, a present-day canopy genset: a black skid, a safety-yellow canopy with two doors and louvred
    grilles, the control panel (a dark display, start key, an emergency stop on its collar), radiator slats on the
    -X end, lifting eyes, a fuel cap and a warm-steel exhaust stack with a rain cap. Its state: `<id>_on` (the
    status bar across the front and the beacon on top green) and `<id>_off` (both red); the game shows one."""
    m = pc.mesh
    w, d, h = pt._dims(p)
    sk, top = 0.12, 1.28
    for sz in (-1, 1):  # the skid's rails and deck
        z0 = sz * d / 2 - (0.12 if sz > 0 else 0)
        pt.cbox(m, (-w / 2, 0, z0), (w / 2, sk, z0 + 0.12), "steel_black", 0.012)
    pg.box(m, (-w / 2 + 0.04, sk - 0.03, -d / 2 + 0.12), (w / 2 - 0.04, sk, d / 2 - 0.12), "steel_black", "+y")
    cx0, cx1, cz = -w / 2 + 0.05, w / 2 - 0.05, d / 2 - 0.05
    pt.cbox(m, (cx0, sk, -cz), (cx1, top, cz), "safety_yellow", 0.035)
    pg.box(m, (cx0 + 0.02, sk, -cz - 0.004), (cx1 - 0.02, sk + 0.05, cz + 0.004), "rubber_black", "+x-x+z-z")
    zf = cz
    for x in (-0.42, 0.42):  # the doors' seams and hinges
        pg.box(m, (x - 0.005, sk + 0.08, zf), (x + 0.005, top - 0.12, zf + 0.003), "steel_black", "+z+x-x")
    for x0, x1 in ((cx0 + 0.12, -0.52), (-0.32, 0.32)):  # louvred grilles on the left door and the middle
        for i in range(7):
            y = sk + 0.3 + i * 0.085
            pt.cbox(m, (x0, y, zf - 0.004), (x1, y + 0.04, zf + 0.022), "steel_black", 0.006)
    for x in (-0.6, 0.12):  # flush door handles
        pg.box(m, (x, 0.62, zf), (x + 0.12, 0.66, zf + 0.018), "chrome", "+x-x+y-y+z")
    px0, px1, py0, py1 = 0.52, cx1 - 0.08, 0.5, 1.08  # the control panel
    pt.cbox(m, (px0, py0, zf - 0.004), (px1, py1, zf + 0.018), "steel_black", 0.008)
    pg.box(m, (px0 + 0.06, py1 - 0.2, zf + 0.018), (px1 - 0.06, py1 - 0.06, zf + 0.022), "glass_dark", "+x-x+y-y+z")
    pc_x = (px0 + px1) / 2
    pg.cyl(m, "z", (pc_x - 0.12, py0 + 0.16), 0.04, zf + 0.018, zf + 0.03, "chrome", 8)  # the start key
    pg.box(m, (pc_x - 0.124, py0 + 0.13, zf + 0.03), (pc_x - 0.116, py0 + 0.19, zf + 0.036), "steel_black")
    pg.cyl(m, "z", (pc_x + 0.12, py0 + 0.16), 0.075, zf + 0.018, zf + 0.026, "safety_yellow", 10)  # the e-stop
    pg.cyl(m, "z", (pc_x + 0.12, py0 + 0.16), 0.05, zf + 0.026, zf + 0.045, "paint_red", 10, r1=0.042)
    for i in range(3):  # gauges under the display
        pg.cyl(m, "z", (px0 + 0.12 + i * 0.1, py1 - 0.28), 0.03, zf + 0.018, zf + 0.026, "porcelain_white", 8)
    for i in range(9):  # radiator slats on the -X end
        y = sk + 0.12 + i * 0.1
        pg.box(m, (-w / 2, y, -cz + 0.12), (cx0, y + 0.05, cz - 0.12), "steel_black", "+y-y-x+z-z")
    for i in range(6):  # the air outlet on the +X end
        y = sk + 0.4 + i * 0.09
        pg.box(m, (cx1, y, -cz + 0.2), (w / 2 - 0.02, y + 0.045, cz - 0.2), "steel_black", "+y-y+x+z-z")
    for sx in (-1, 1):  # lifting eyes on the roof
        for sz in (-1, 1):
            x, z = sx * (w / 2 - 0.25), sz * (cz - 0.15)
            pt.cbox(m, (x - 0.04, top, z - 0.012), (x + 0.04, top + 0.06, z + 0.012), "steel_black", 0.004)
    pg.cyl(m, "y", (0.3, -0.2), 0.06, top, top + 0.04, "chrome", 8)  # the fuel cap
    sx_, sz_ = -0.7, -0.15  # the exhaust stack and its rain cap
    pg.cyl(m, "y", (sx_, sz_), 0.1, top, top + 0.03, "steel_black", 10)
    pg.cyl(m, "y", (sx_, sz_), 0.065, top + 0.03, h - 0.06, "steel_warm", 10, caps=(False, False))
    pg.cyl(m, "y", (sx_, sz_), 0.1, h - 0.06, h, "steel_warm", 10, r1=0.03)
    for state, role in (("on", "signal_green"), ("off", "signal_red")):
        s = pc.leaf(state, (0.0, 0.0, 0.0))
        pt.cbox(s, (-0.36, top - 0.1, zf), (0.36, top - 0.045, zf + 0.02), role, 0.006)  # the status bar
        pg.cyl(s, "y", (0.75, 0.2), 0.06, top, top + 0.11, role, 10, r1=0.05)  # the beacon
    pg.cyl(m, "y", (0.75, 0.2), 0.075, top, top + 0.012, "steel_black", 10)  # the beacon's base
    pc.collide_box((-w / 2, 0, -d / 2), (w / 2, top, d / 2))
    pc.collide_box((sx_ - 0.1, top, sz_ - 0.1), (sx_ + 0.1, h, sz_ + 0.1))


def build_computer(pc: Piece, p: dict, spec: dict) -> None:
    """The study's computer, present-day: a flat monitor on a steel stand (its screen the game surface, the photo to
    print), a white keyboard with dark keys, a mouse and a red mug."""
    m = pc.mesh
    w, d, h = pt._dims(p)
    zb = -d / 2
    pt.cbox(m, (-0.13, 0, zb), (0.13, 0.014, zb + 0.18), "steel_black", 0.004)  # the stand's foot
    pg.box(m, (-0.03, 0.014, zb + 0.005), (0.03, 0.22, zb + 0.03), "steel_warm")  # its neck
    z0, z1 = zb + 0.03, zb + 0.058  # the panel
    y0, y1 = 0.09, h
    pt.cbox(m, (-0.28, y0, z0), (0.28, y1, z1), "rubber_black", 0.006)
    pg.box(m, (-0.268, y0 + 0.022, z1), (0.268, y1 - 0.012, z1 + 0.002), "glass_dark", "+x-x+y-y")
    pt.surface(m, -0.262, 0.262, y0 + 0.028, y1 - 0.018, z1 + 0.002)
    pg.box(m, (0.22, y0 + 0.006, z1), (0.24, y0 + 0.012, z1 + 0.002), "signal_green", "+z")  # the power lamp
    kz0 = 0.03
    pt.cbox(m, (-0.22, 0, kz0), (0.2, 0.022, kz0 + 0.15), "porcelain_white", 0.006)
    for r in range(4):
        pg.box(m, (-0.205, 0.022, kz0 + 0.015 + r * 0.032), (0.185, 0.03, kz0 + 0.04 + r * 0.032), "rubber_black",
               "+x-x+y+z-z")
    pt.cbox(m, (0.235, 0, d / 2 - 0.1), (w / 2, 0.03, d / 2), "porcelain_white", 0.012)  # the mouse
    pg.cyl(m, "y", (-0.264, 0.05), 0.036, 0.0, 0.1, "paint_red", 10)  # the mug
    pc.collide_box((-0.28, 0, zb), (0.28, h, z1 + 0.002))
    pc.collide_box((-w / 2, 0, z1 + 0.002), (w / 2, 0.07, d / 2))


def build_board(pc: Piece, p: dict, spec: dict) -> None:
    """A board the game writes on, in the world look: chalk (props_task.build_board_fine, the order and herb
    boards), screen (the pose screen: a slim black display on a black steel stand, a sound bar under it) or cork (the
    photo board: an oak frame and posts, a header with clips, a ledge with a box of pins)."""
    style = p.get("style", "chalk")
    if style == "chalk":
        pt.build_board_fine(pc, p, spec)
        return
    m = pc.mesh
    w, d, h = pt._dims(p)
    bw, bh = p["board"]
    fr, post, header = p.get("frame", 0.05), 0.07, p.get("header", 0.0)
    screen = style == "screen"
    frame_role, post_role = ("rubber_black", "steel_black") if screen else ("wood_front", "wood_front")
    x0, x1 = -bw / 2, bw / 2
    y1 = h - header
    y0 = y1 - bh
    zb, zf = -0.025, 0.03
    c = 0.006
    if screen:  # the display: a slim bezel round the glass, a black back housing
        pt.cbox(m, (x0, y0, zb), (x1, y1, zf - 0.012), "steel_black", c)
        for (a0, a1, b0, b1) in ((x0, x1, y0, y0 + fr), (x0, x1, y1 - fr, y1), (x0, x0 + fr, y0 + fr, y1 - fr),
                                 (x1 - fr, x1, y0 + fr, y1 - fr)):
            pt.cbox(m, (a0, b0, zf - 0.014), (a1, b1, zf), frame_role, 0.004)
        pg.box(m, (x1 - fr - 0.06, y0 + 0.018, zf), (x1 - fr - 0.03, y0 + 0.026, zf + 0.002), "signal_green", "+z")
        pt.cbox(m, (-0.6, y0 - 0.1, -0.03), (0.6, y0 - 0.02, 0.035), "rubber_black", 0.012)  # the sound bar
        pg.box(m, (-0.58, y0 - 0.09, 0.035), (0.58, y0 - 0.03, 0.037), "steel_black", "+z")
    else:
        for (a0, a1, b0, b1) in ((x0, x1, y0, y0 + fr), (x0, x1, y1 - fr, y1), (x0, x0 + fr, y0 + fr, y1 - fr),
                                 (x1 - fr, x1, y0 + fr, y1 - fr)):
            pt.cbox(m, (a0, b0, zb), (a1, b1, zf), frame_role, c)
        pg.box(m, (x0 + fr, y0 + fr, zb + 0.005), (x1 - fr, y1 - fr, 0.01), "cork", "+x-x+y-y-z")
        pt.cbox(m, (x0 + 0.1, y0 - 0.035, 0.0), (x1 - 0.1, y0, 0.07), "worktop_wood", c)  # the ledge
        pt.cbox(m, (x1 - 0.4, y0, 0.032), (x1 - 0.28, y0 + 0.04, 0.066), "paint_red", 0.004)  # a box of pins
        pg.box(m, (x0 + 0.3, y0, 0.032), (x0 + 0.52, y0 + 0.012, 0.066), "art_white")  # a stack of prints
    pt.surface(m, x0 + fr, x1 - fr, y0 + fr, y1 - fr, zf - 0.011 if screen else 0.01)
    for sx in (-1, 1):
        xa = sx * (w / 2 - post / 2)
        pt.cbox(m, (xa - post / 2, 0.012, -0.035), (xa + post / 2, h, 0.035), post_role, c)
        pt.cbox(m, (xa - post / 2, 0.012, -d / 2), (xa + post / 2, 0.06, d / 2), "steel_black", 0.008)
        for zz in (-d / 2 + 0.04, d / 2 - 0.04):  # rubber pads under the feet
            pg.cyl(m, "y", (xa, zz), 0.02, 0.0, 0.012, "rubber_black", 8, caps=(False, True))
        for yy in (y0 + 0.1, y1 - 0.1):  # bolts through the posts
            pg.cyl(m, "z", (xa, yy), 0.012, 0.035, 0.042, "steel_warm", 6, caps=(False, True))
    if header:
        pt.cbox(m, (-w / 2, h - header, -0.03), (w / 2, h, 0.03), "worktop_wood" if not screen else post_role, c)
        for x in (-1.0, -0.33, 0.33, 1.0):  # clips on the header for the prints
            if abs(x) < bw / 2 - 0.1:
                pg.box(m, (x - 0.025, y1 - 0.05, zf), (x + 0.025, y1 + 0.005, zf + 0.012), "steel_warm")
    pc.collide_box((-w / 2, 0, -d / 2), (-w / 2 + post, h, d / 2))
    pc.collide_box((w / 2 - post, 0, -d / 2), (w / 2, h, d / 2))
    pc.collide_box((-w / 2 + post, y0, zb), (w / 2 - post, y1, zf))


def build_table(pc: Piece, p: dict, spec: dict) -> None:
    """A drop-off table in the world look: the dining table (props_task.build_table_fine) or, style "terrace", the
    terrace's slatted oak top on a black steel frame (the builder's, recoloured)."""
    if p.get("style") == "terrace":
        pt.build_table(pc, p, spec)
        recolour(pc, spec)
    else:
        pt.build_table_fine(pc, p, spec)


RECOLOURED = {
    "box_stack": _box_stack, "wine_rack": _wine_rack, "bun_shelf": _bun_shelf, "parts_shelf": _parts_shelf,
    "potting_bench": _recoloured(pt.build_potting_bench), "workbench": _recoloured(pt.build_workbench),
    "chest_freezer": _recoloured(pt.build_chest_freezer), "grill": _recoloured(pt.build_grill),
    "herb_bed": _recoloured(pt.build_herb_bed), "switch": _recoloured(pt.build_switch),
    "printer": _recoloured(pt.build_printer),
}
FINE_BUILDERS = {**RECOLOURED, "table": build_table, "board": build_board, "generator": build_generator,
                 "computer": build_computer}
