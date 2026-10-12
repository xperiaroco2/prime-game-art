"""The slice character's pure side (art #42 part C; docs/godot.md, "The slice character"): which clips of an animation
set go on the character and why the others stay off, each clip's provenance from its source record or Meshy batch, and
the asset folder's texts (manifest.toml, package.json, HANDOFF.md). Blender and Godot run in `slice`; this module
needs neither, so the tests cover it whole."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

from .. import common
from . import _godot

SETTINGS = common.ROOT / "recipes" / "slice_character.toml"
SOURCES = common.ROOT / "sources"
BATCHES = common.ROOT / "batches"
GAME_LICENCE_URL = "https://github.com/xperiaroco2/prime-game"
# prime-game docs/ARCHITECTURE.md section 11.1: a character lands as assets/characters/<id>/<id>.glb.
GAME_CHARACTERS = "assets/characters"

# A clip key's library -> the source record of its raw files (`pack` per body type: the Ultimate Modular pack's own
# actions). `tm` clips come from Meshy batches instead (their batch file and generation.json).
RECORDS = {
    "ual": "quaternius_ual1_standard",
    "ual2": "quaternius_ual2_standard",
    "pack:men": "quaternius_ultimate_modular_men",
    "pack:women": "quaternius_ultimate_modular_women",
}
SETTINGS_KEYS = {"cast", "recipe", "set", "review_clips", "exclude"}


def load_settings(path: Path = SETTINGS) -> dict[str, Any]:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def check_settings(settings: dict[str, Any], set_data: dict[str, Any]) -> list[str]:
    """Every problem with the settings against the set they name."""
    errors = [f"unknown key {k!r}" for k in sorted(set(settings) - SETTINGS_KEYS)]
    for key in ("cast", "recipe", "set"):
        if not (isinstance(settings.get(key), str) and settings[key]):
            errors.append(f"{key} must be a non-empty string")
    exported = exported_names(set_data)
    exclude = settings.get("exclude", {})
    if not isinstance(exclude, dict):
        return errors + ["exclude must be a table of clip = reason"]
    for name, reason in exclude.items():
        if name not in exported:
            errors.append(f"exclude: {name} is no exported clip of the set")
        if not (isinstance(reason, str) and reason):
            errors.append(f"exclude: {name} needs a reason")
    for name in settings.get("review_clips", []):
        if name not in exported or name in exclude:
            errors.append(f"review_clips: {name} is not on the character")
    return errors


def exported_names(set_data: dict[str, Any]) -> list[str]:
    return [c["name"] for c in set_data["clips"] if c.get("export", True)]


def selection(set_data: dict[str, Any], exclude: dict[str, str]) -> tuple[list[str], list[tuple[str, str]]]:
    """The set's clips the character carries, in the set's order, and every clip left off with its reason."""
    kept, left = [], []
    for clip in set_data["clips"]:
        name = clip["name"]
        if not clip.get("export", True):
            left.append((name, "a review candidate the set does not export (export = false)"))
        elif name in exclude:
            left.append((name, exclude[name]))
        else:
            kept.append(name)
    return kept, left


def root_source(set_data: dict[str, Any], name: str) -> str:
    """The source clip key a clip is built from, following `from` (Turn_Right -> Turn_Left -> tm:turn-left-90)."""
    table = {c["name"]: c for c in set_data["clips"]}
    seen = set()
    while "source" not in table[name]:
        if name in seen:
            raise ValueError(f"{name}: a `from` cycle")
        seen.add(name)
        name = table[name]["from"]
    return table[name]["source"]


def tm_batch(raw_path: str) -> str:
    """The batch id of a text-to-motion clip from its raw path (`2026-10-b5-anim-mvp/package-lift/...fbx`)."""
    return raw_path.replace("\\", "/").split("/", 1)[0]


def provenance(key: str, body: str, records: dict[str, dict], batches: dict[str, dict],
               tm_files: dict[str, str], generations: dict[str, dict] | None = None) -> dict[str, Any]:
    """A source clip key's provenance: its record (a source id, or the Meshy batch file), licence, licence URL,
    public_repo_ok, ai_generated, and for a Meshy clip its task id and raw file with its SHA-256 (from the run's
    generation.json, when given)."""
    lib, _, clip = key.partition(":")
    if lib == "tm":
        if clip not in tm_files:
            raise ValueError(f"{key}: no raw file in the review settings' [libraries.tm.clips]")
        batch_id = tm_batch(tm_files[clip])
        batch = batches.get(batch_id)
        if batch is None:
            raise ValueError(f"{key}: no batch file batches/{batch_id}.toml")
        out = {"record": f"batches/{batch_id}.toml", "licence": "owned-paid-output",
               "licence_url": batch["terms_url"], "public_repo_ok": True, "ai_generated": True,
               "plan": batch["plan"], "raw": tm_files[clip]}
        gen = (generations or {}).get(clip)
        if gen:
            out["task_id"] = gen["tasks"]["text_to_motion"]["id"]
            files = {f["name"]: f for f in gen.get("files", [])}
            name = tm_files[clip].rsplit("/", 1)[-1]
            if name in files:
                out["raw_sha256"] = files[name]["sha256"]
        return out
    rec_id = RECORDS.get(f"{lib}:{body}" if lib == "pack" else lib)
    if rec_id is None:
        raise ValueError(f"{key}: no source record for the library {lib!r}")
    rec = records.get(rec_id)
    if rec is None:
        raise ValueError(f"{key}: no source record sources/{rec_id}.toml")
    return {"record": rec_id, "licence": rec["licence"], "licence_url": rec["licence_url"],
            "public_repo_ok": rec["public_repo_ok"], "ai_generated": rec["ai_generated"],
            "credit": rec.get("credit", "")}


def clip_rows(set_data: dict[str, Any], kept: list[str], body: str, records: dict, batches: dict,
              tm_files: dict[str, str], generations: dict | None = None,
              lengths: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """One row per kept clip: set name, Godot name, loop, layer, speed, the needs it serves, its source key and
    provenance."""
    table = {c["name"]: c for c in set_data["clips"]}
    rows = []
    for name in kept:
        clip = table[name]
        key = root_source(set_data, name)
        gname, _ = _godot.godot_name(name)
        needs = clip.get("needs", [])
        row = {"name": name, "godot_name": gname, "loop": bool(clip["loop"]),
               "layer": needs[0]["layer"] if needs else "full", "speed_m_s": clip.get("speed_m_s"),
               "serves": [n["need"] for n in needs], "source": key,
               "from": clip.get("from", ""), **provenance(key, body, records, batches, tm_files, generations)}
        if lengths and name in lengths:
            row["seconds"] = lengths[name]
        rows.append(row)
    return rows


def split_public(rows: list[dict[str, Any]]) -> tuple[list[dict], list[tuple[str, str]]]:
    """Rows whose source may reach the public game repo, and the others left off with the reason."""
    ok = [r for r in rows if r["public_repo_ok"] is True]
    off = [(r["name"], f"its source {r['record']} is not public_repo_ok") for r in rows if r["public_repo_ok"] is not True]
    return ok, off


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _q(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def manifest_toml(asset_id: str, cast: str, recipe: str, rows: list[dict], raw: list[tuple[str, str]],
                  tools: list[str], generated_at: str, left: list[tuple[str, str]],
                  body_credits: tuple[str, ...] = ()) -> str:
    """manifest.toml of the character (kind `character`, docs/manifest.md): own work made from CC0 packs and Meshy's
    paid-plan clips, one [[clips]] table per clip with its own provenance, approval empty; `body_credits` (the body
    pack's credit) lead the credit line."""
    ai = any(r["ai_generated"] for r in rows)
    tasks = sorted({r["task_id"] for r in rows if r.get("task_id")})
    clip_credits = {r["credit"] for r in rows if r.get("credit")} - set(body_credits)
    credits = list(dict.fromkeys(body_credits)) + sorted(clip_credits)
    left_text = "; ".join(f"{n} ({why})" for n, why in left)
    lines = [
        f"# Written by `tools/run.py slice` (art #42 part C); a rebuild changes the hashes below.",
        f"id = {_q(asset_id)}",
        'kind = "character"',
        'slot = ""',
        f"title = {_q(f'The slice character: cast {cast} of {recipe} in the clay look with its clips')}",
        f"notes = {_q('The game M6.2 slice body (#42 part C): the Ultimate Modular men or women pack pieces of the cast recipe, the clay look baked into textures and the clay face kit (own work), with the animation set clips listed below. Left off: ' + left_text + '.')}",
        f"tools = [{', '.join(_q(t) for t in tools)}]",
        'licence = "own-work"',
        f"licence_url = {_q(GAME_LICENCE_URL)}",
        f"credit = {_q('; '.join(credits))}",
        "public_repo_ok = true",
        f"ai_generated = {'true' if ai else 'false'}",
        "approved_by = []",
        'approved_at = ""',
        'approval_pr = ""',
        "",
        "[source]",
        'service = "own"',
        'plan = "own-work; Meshy Pro (monthly) for the text-to-motion clips"',
        f"model_version = {_q('meshy text-to-motion (prime)' if ai else '')}",
        f"task_ids = [{', '.join(_q(t) for t in tasks)}]",
        f"generated_at = {generated_at}",
        'url = "https://github.com/xperiaroco2/prime-game-art"',
    ]
    for file, digest in raw:
        lines += ["", "[[raw]]", f"file = {_q(file)}", f"sha256 = {_q(digest)}"]
    for r in rows:
        lines += ["", "[[clips]]", f"name = {_q(r['name'])}", f"loop = {'true' if r['loop'] else 'false'}",
                  f"source = {_q(r['source'])}", f"record = {_q(r['record'])}", f"licence = {_q(r['licence'])}",
                  f"licence_url = {_q(r['licence_url'])}",
                  f"public_repo_ok = {'true' if r['public_repo_ok'] else 'false'}",
                  f"ai_generated = {'true' if r['ai_generated'] else 'false'}"]
        if r.get("task_id"):
            lines.append(f"task_id = {_q(r['task_id'])}")
    return "\n".join(lines) + "\n"


def game_dir(asset_id: str) -> str:
    """Where the character lands in prime-game: its docs/ARCHITECTURE.md section 11.1, `assets/characters/<id>/`."""
    return f"{GAME_CHARACTERS}/{asset_id}"


PACK_RECORDS = {"M": "quaternius_ultimate_modular_men", "W": "quaternius_ultimate_modular_women"}


def source_credit(record: dict[str, Any]) -> str:
    """A source record's credit line: its `credit`, else "<title> by <author> (<licence>)"."""
    if record.get("credit"):
        return record["credit"]
    return f"{record.get('title', record.get('id', '?'))} by {record.get('author', '?')} ({record.get('licence', '?')})"


def package_json(asset_id: str, files: dict[str, Path], game_dir: str) -> dict[str, Any]:
    """The House packages' file list (name, bytes, SHA-256) with the game folder they land in."""
    return {"asset": asset_id, "game_dir": game_dir,
            "files": [{"name": n, "bytes": p.stat().st_size, "sha256": sha256(p)} for n, p in sorted(files.items())]}


def clip_table(rows: list[dict]) -> str:
    """The Markdown clip table of HANDOFF.md and the PR."""
    out = ["| Godot name | Set name | Loop | Layer | s | Source | Licence | ai_generated | Serves |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        src = r["source"] + (f" (from {r['from']})" if r.get("from") else "")
        out.append(f"| `{r['godot_name']}` | `{r['name']}` | {'LINEAR' if r['loop'] else 'none'} | {r['layer']} | "
                   f"{r.get('seconds', '')} | `{src}` | {r['licence']} | {str(r['ai_generated']).lower()} | "
                   f"{'; '.join(r['serves'])} |")
    return "\n".join(out)
