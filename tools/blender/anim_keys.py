"""The clip keys of the animation review (docs/animations.md, "Clip keys"): pure Python (no bpy), so the unit tests read
it with the system Python and Blender's Python reads it the same way.

- A clip key is "<source>:<clip>": "pack:Walk", "ual:Walk_Loop" (UAL1), "ual2:Walk_Carry_Loop" (UAL2, art #24) or any
  other library of the review settings' [libraries].
- A layered clip is "<base>|<upper>": the base clip's hips and legs under the upper clip's upper body (the settings'
  [layer] bone and every bone below it), the way an engine layers an upper-body clip with a bone filter.
- A rates lane is a clip key or "blend:<A>+<B>" (two clips of a library, cycle-synced; a name without a source is
  UAL1's), either one optionally followed by "|<upper clip key>".
"""

from __future__ import annotations

RESERVED = {"pack", "blend", "layer"}  # not library names


def split(key: str) -> tuple[str, str]:
    """A clip key's source and clip name; raises ValueError for anything else."""
    source, sep, name = key.partition(":")
    if not sep or not source or not name or "|" in key or "+" in name and source != "blend":
        raise ValueError(f"not a clip key: {key!r} (expected <source>:<clip>)")
    return source, name


def layer(key: str) -> tuple[str, str | None]:
    """A key's base and its upper-body layer (None without one)."""
    base, sep, upper = key.partition("|")
    if sep and (not upper or "|" in upper):
        raise ValueError(f"a layered key is <base>|<upper clip>: {key!r}")
    if sep:
        split(upper)
    return base, (upper if sep else None)


def blend_parts(base: str) -> list[str] | None:
    """The two clip keys of "blend:A+B" (a name without a source is UAL1's), or None when base is no blend."""
    if not base.startswith("blend:"):
        return None
    parts = base[len("blend:"):].split("+")
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"a blend is blend:<A>+<B>: {base!r}")
    out = [p if ":" in p else f"ual:{p}" for p in parts]
    for p in out:
        split(p)
    return out


def needs(key: str) -> list[str]:
    """The plain clip keys a clip, layered clip or rates lane plays, in order and without repeats."""
    base, upper = layer(key)
    parts = blend_parts(base)
    if parts is None:
        split(base)
        parts = [base]
    out = parts + ([upper] if upper else [])
    return list(dict.fromkeys(out))


def sources_of(key: str) -> set[str]:
    return {split(k)[0] for k in needs(key)}


def pairs(cfg: dict) -> list[dict]:
    """The [[pairs]] of the review settings as {"name", "clips"}: either a pack clip against UAL1 clips (`pack`, `ual`;
    named after the pack clip) or a `name` and any clip keys (`clips`)."""
    out = []
    for i, p in enumerate(cfg.get("pairs", [])):
        if "clips" in p:
            if not p.get("name") or set(p) - {"name", "clips", "note"}:
                raise ValueError(f"pairs[{i}]: a pair with clips takes a name, clips and an optional note")
            clips = list(p["clips"])
        else:
            if set(p) - {"pack", "ual"} or not p.get("pack") or not p.get("ual"):
                raise ValueError(f"pairs[{i}]: give pack and ual, or name and clips")
            clips = [f"pack:{p['pack']}"] + [f"ual:{u}" for u in p["ual"]]
        if not clips:
            raise ValueError(f"pairs[{i}]: no clips")
        for k in clips:
            needs(k)
        out.append({"name": p.get("name") or p["pack"], "clips": clips})
    names = [p["name"] for p in out]
    if len(set(names)) != len(names):
        raise ValueError(f"two pairs share a name: {sorted(n for n in names if names.count(n) > 1)}")
    return out


def selected(keys: list[str], sources: set[str] | None) -> bool:
    """Whether a pair or rates row with these keys plays a clip of one of the sources (None: every row)."""
    return sources is None or any(sources_of(k) & sources for k in keys)


def parse_sources(text: str, known: set[str]) -> set[str] | None:
    """A comma-separated source list ("" or "all": None, every source); raises ValueError on an unknown one."""
    if text in ("", "all"):
        return None
    out = {s.strip() for s in text.split(",") if s.strip()}
    unknown = out - known
    if unknown or not out:
        raise ValueError(f"unknown sources {sorted(unknown)}; known: {sorted(known)}")
    return out
