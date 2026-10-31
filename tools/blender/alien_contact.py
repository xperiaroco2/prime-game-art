"""The alien clips' contact table (art #196, B1-B1d), plain Python: from alien_contact_measure.py's JSONs (per clip
and frame the Hips' world z and each skinned mesh's lowest point, mm), per clip and stage the ground (the shoes'
lowest, else every mesh's) min and max, the frames floated over 5 mm outside real flight, the frames under -2 mm and
the Hips' largest one-frame step.

Flight: a frame where the bare loco body's lowest is over 5 mm, but only in a clip that can leave the ground. B1d: a
gait with a foot always down (NO_FLIGHT: the walk, the crouches, the idles, the talk; B1i: not the crouch run) has no
flight, so a frame with both feet up counts as floated there. Before, the crouch's float (her shoes 29-32 mm up, the bare body too) passed
as flight.

Usage: alien_contact.py OUT.md LABEL=bare.json,stage1.json,stage2.json,... ...
"""
from __future__ import annotations

import json
import sys

NO_FLIGHT = ("Walk", "Crouch", "Idle", "Talk")
FLIGHT = ("Crouch_Run",)  # B1i: a run, though crouched: its source leaves the ground (his shoes 19 mm up, B1d)
FLOAT_MM, UNDER_MM = 5.0, -2.0


def can_fly(clip: str) -> bool:
    """Whether the clip has frames with both feet up (a run, a jump): not a NO_FLIGHT gait. B1i (art #196, the
    review's major 1): Crouch_Run (and its variants) can fly: as a NO_FLIGHT crouch, foot_plant lowered its trailing
    toe onto the floor in the run's own flight while it still moved (a skid)."""
    return clip.startswith(FLIGHT) or not clip.startswith(NO_FLIGHT)


def flight(clip: str, bare_ground: list[float]) -> list[bool]:
    """Per frame whether it is real flight: the bare body over FLOAT_MM, in a clip that can fly."""
    fly = can_fly(clip)
    return [fly and g > FLOAT_MM for g in bare_ground]


def floated(clip: str, ground: list[float], bare_ground: list[float]) -> int:
    """The frames whose ground is over FLOAT_MM outside real flight."""
    if len(ground) != len(bare_ground):
        raise ValueError(f"{clip}: {len(ground)} frames against the bare body's {len(bare_ground)}")
    return sum(g > FLOAT_MM and not fl for g, fl in zip(ground, flight(clip, bare_ground)))


def rows_of(js: dict, clip: str):
    rows = js["clips"].get(clip)
    if rows is None:
        return None
    return rows[:-1] if clip.endswith("_Loop") else rows  # a loop's last frame repeats its first


def ground(js: dict, rows: list) -> list[float]:
    use = [m for m in js["meshes"] if m == "shoes"] or list(js["meshes"])
    return [min(r[m] for m in use if r.get(m) is not None) for r in rows]


def hip_step(rows: list, loop: bool) -> float:
    h = [r["hips"] for r in rows]
    n = len(h)
    return max(abs(h[(i + 1) % n] - h[i]) for i in range(n if loop else n - 1))


def table(groups: list[tuple[str, dict, list[dict]]]) -> list[str]:
    """groups: (label, the bare loco body's JSON, the stages' JSONs); returns the markdown lines."""
    lines = ["| clip | char | bare hips step | ground min mm (stages) | ground max mm | floated >5 mm (not flight) |"
             " under -2 mm frames | hips max step mm |", "|---|---|---|---|---|---|---|---|"]
    for label, bare, stages in groups:
        for clip in sorted(bare["clips"]):
            loop = clip.endswith("_Loop")
            rb = rows_of(bare, clip)
            gb = ground(bare, rb)
            cells = {k: [] for k in ("min", "max", "float", "under", "step")}
            for js in stages:
                rows = rows_of(js, clip)
                if rows is None or len(rows) != len(rb):
                    for k in cells:
                        cells[k].append("-")
                    continue
                g = ground(js, rows)
                cells["min"].append(f"{min(g):.1f}")
                cells["max"].append(f"{max(g):.1f}")
                cells["float"].append(str(floated(clip, g, gb)))
                cells["under"].append(str(sum(x < UNDER_MM for x in g)))
                cells["step"].append(f"{hip_step(rows, loop):.1f}")
            name = clip if can_fly(clip) else clip + " (no flight)"
            lines.append(f"| {name} ({len(rb)} f) | {label} | {hip_step(rb, loop):.1f} | " +
                         " | ".join(" / ".join(cells[k]) for k in ("min", "max", "float", "under", "step")) + " |")
    return lines


def main(argv: list[str]) -> int:
    out, groups = argv[0], []
    for a in argv[1:]:
        label, files = a.split("=", 1)
        bare, *stages = [json.load(open(p, encoding="utf-8")) for p in files.split(",")]
        groups.append((label, bare, stages))
    lines = table(groups)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("TABLE wrote", out, len(lines) - 2, "rows")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
