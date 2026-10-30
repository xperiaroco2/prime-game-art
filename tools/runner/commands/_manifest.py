"""The asset manifest schema (docs/manifest.md): every assets/<kind>/<id>/manifest.toml is checked by validate(), every
source record sources/<id>.toml (a downloaded pack or library that assets are made from) by validate_source(). A set
manifest (a kit's pieces, a prop library, an outdoor package) adds a per-file table, [[files]], checked against the
source records its pack-made files name."""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

# Which slots each kind may fill; "" means the asset fills no cosmetic slot. The slot names follow the character
# contract (contract/, issue #4): clothing in pieces (top, bottom, shoes), a hat or a hairstyle (hair_or_hat), eyes
# and mouth as changeable face slots, a face accessory (face_accessory) and a back item (back_item).
KIND_SLOTS: dict[str, frozenset[str]] = {
    "body": frozenset({""}),
    # A game-ready character (art #42 part C): body, outfit, face and its clips in one GLB, one asset.
    "character": frozenset({""}),
    "clothing": frozenset({"top", "bottom", "shoes"}),
    "hair": frozenset({"hair_or_hat"}),
    "face": frozenset({"eyes", "mouth"}),
    "accessory": frozenset({"hair_or_hat", "face_accessory", "back_item"}),
    "item": frozenset({""}),
    "prop": frozenset({""}),
    "animation": frozenset({""}),
    # The House (#118): a modular kit's pieces, a room scene, an outdoor or garden package.
    "kit": frozenset({""}),
    "room": frozenset({""}),
    "environment": frozenset({""}),
}
# Kinds whose manifest may hold a set of shipped files ([[files]]) rather than one asset.
SET_KINDS = frozenset({"kit", "room", "environment", "prop"})
# Licences an asset may carry; only the first four may ever reach the public game repo.
PUBLIC_LICENCES = frozenset({"CC0-1.0", "CC-BY-4.0", "NASA-PD", "owned-paid-output", "own-work"})
# Licences whose records must carry `credit` (the attribution line).
CREDIT_LICENCES = frozenset({"CC-BY-4.0", "NASA-PD"})
LICENCES = PUBLIC_LICENCES | {"restricted"}

TOP_REQUIRED = (
    "id", "kind", "slot", "source", "raw", "tools", "licence", "licence_url",
    "public_repo_ok", "ai_generated", "approved_by", "approved_at", "approval_pr",
)  # fmt: skip
TOP_OPTIONAL = ("title", "notes", "credit", "files", "clips")
# Kinds whose manifest may list the animation clips they carry ([[clips]]), each with its own provenance.
CLIP_KINDS = frozenset({"character", "animation"})
# One clip: its name in the export, whether it loops, its source clip key (ual:Idle_Loop, tm:package-lift), its record
# (a source record id, or the Meshy batch file batches/<id>.toml), its licence and flags; a Meshy clip's task id.
CLIP_REQUIRED = ("name", "loop", "source", "record", "licence", "licence_url", "public_repo_ok", "ai_generated")
CLIP_OPTIONAL = ("task_id",)
SOURCE_REQUIRED = ("service", "plan", "model_version", "task_ids", "generated_at")
SOURCE_OPTIONAL = ("url",)
RAW_REQUIRED = ("file", "sha256")
# One shipped file of a set: its path inside the set's export/ folder, where it was built in the raw folder, its sha256,
# and for a file made from a pack, the source record (sources/<id>.toml) and that record's raw files it was made from.
FILE_REQUIRED = ("name", "file", "sha256")
FILE_OPTIONAL = ("source", "from")
# A source record: one download (a pack, a library) with its licence and the hashes of its raw files.
SOURCE_RECORD_REQUIRED = (
    "id", "title", "author", "url", "licence", "licence_url", "public_repo_ok", "ai_generated", "downloaded_at", "raw",
)  # fmt: skip
SOURCE_RECORD_OPTIONAL = ("credit", "notes")

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
URL_RE = re.compile(r"^https?://\S+$")
PR_RE = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/pull/[0-9]+$")
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")


def find(root: Path) -> tuple[list[Path], list[str]]:
    """Every manifest under root/assets, and an error for each asset folder without one or misplaced manifest."""
    assets = root / "assets"
    errors: list[str] = []
    if not assets.is_dir():
        return [], errors
    manifests = sorted(assets.rglob("manifest.toml"))
    for path in manifests:
        if len(path.relative_to(assets).parts) != 3:
            where = path.relative_to(root).as_posix()
            errors.append(f"{where}: a manifest belongs at assets/<kind>/<id>/manifest.toml")
    for kind_dir in sorted(p for p in assets.iterdir() if p.is_dir()):
        for asset_dir in sorted(p for p in kind_dir.iterdir() if p.is_dir()):
            if not (asset_dir / "manifest.toml").is_file():
                errors.append(f"{asset_dir.relative_to(root).as_posix()}: no manifest.toml")
    return [p for p in manifests if len(p.relative_to(assets).parts) == 3], errors


def load(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle), None
    except tomllib.TOMLDecodeError as exc:
        return None, f"not valid TOML: {exc}"
    except OSError as exc:
        return None, f"cannot read: {exc}"


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_when(value: Any) -> bool:
    return isinstance(value, (dt.date, dt.datetime))


def _keys(table: dict[str, Any], required: tuple[str, ...], optional: tuple[str, ...], where: str) -> list[str]:
    errors = [f"{where}missing key {key!r}" for key in required if key not in table]
    allowed = set(required) | set(optional)
    errors += [f"{where}unknown key {key!r}" for key in table if key not in allowed]
    return errors


def validate(
    data: dict[str, Any],
    kind_dir: str | None = None,
    id_dir: str | None = None,
    sources: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Every problem in one parsed manifest, as readable lines; empty when it is valid. kind_dir and id_dir are the
    folder names it was found in (assets/<kind_dir>/<id_dir>/), checked against kind and id. sources maps each source
    record's id to its parsed record; given, a set's pack-made files are checked against it."""
    # A set's [[files]] are its raw files, so a set may leave out [[raw]].
    required = tuple(key for key in TOP_REQUIRED if not (key == "raw" and "files" in data))
    errors = _keys(data, required, TOP_OPTIONAL, "")

    asset_id = data.get("id")
    if "id" in data:
        if not (isinstance(asset_id, str) and ID_RE.fullmatch(asset_id)):
            errors.append("id must be lowercase letters, digits and underscores")
        elif id_dir is not None and asset_id != id_dir:
            errors.append(f"id {asset_id!r} differs from its folder name {id_dir!r}")

    kind = data.get("kind")
    if "kind" in data:
        if not isinstance(kind, str) or kind not in KIND_SLOTS:
            errors.append(f"kind {kind!r} is not one of {', '.join(sorted(KIND_SLOTS))}")
        elif kind_dir is not None and kind != kind_dir:
            errors.append(f"kind {kind!r} differs from its folder assets/{kind_dir}/")
    if "slot" in data and isinstance(kind, str) and kind in KIND_SLOTS:
        slot = data["slot"]
        allowed = KIND_SLOTS[kind]
        if not isinstance(slot, str) or slot not in allowed:
            shown = ", ".join(repr(s) for s in sorted(allowed))
            errors.append(f"slot {slot!r} is not allowed for kind {kind!r} (allowed: {shown})")

    ai_generated = data.get("ai_generated")
    if "ai_generated" in data and not isinstance(ai_generated, bool):
        errors.append("ai_generated must be true or false")

    source = data.get("source")
    if "source" in data:
        if not isinstance(source, dict):
            errors.append("source must be a table ([source])")
        else:
            errors += _keys(source, SOURCE_REQUIRED, SOURCE_OPTIONAL, "source: ")
            for key in ("service", "plan"):
                if key in source and not _is_text(source[key]):
                    errors.append(f"source.{key} must be a non-empty string")
            if "model_version" in source and not isinstance(source["model_version"], str):
                errors.append("source.model_version must be a string")
            task_ids = source.get("task_ids")
            if "task_ids" in source and not (isinstance(task_ids, list) and all(_is_text(t) for t in task_ids)):
                errors.append("source.task_ids must be a list of non-empty strings")
            if "generated_at" in source and not _is_when(source["generated_at"]):
                errors.append(
                    "source.generated_at must be a TOML date or date-time (2026-10-02 or 2026-10-02T18:00:00Z)"
                )
            if "url" in source and not (isinstance(source["url"], str) and URL_RE.fullmatch(source["url"])):
                errors.append("source.url must be an http(s) URL")
            if ai_generated is True:
                if not _is_text(source.get("model_version")):
                    errors.append("an AI-generated asset needs source.model_version")
                if not (isinstance(task_ids, list) and task_ids):
                    errors.append("an AI-generated asset needs at least one source.task_ids entry")
                if isinstance(source.get("plan"), str) and "free" in source["plan"].lower():
                    errors.append("free-plan AI output is never used (docs/pipeline.md, AI rules)")

    errors += _raw_errors(data)
    if "files" in data:
        if isinstance(kind, str) and kind in KIND_SLOTS and kind not in SET_KINDS:
            errors.append(f"kind {kind!r} cannot be a set ([[files]] is for {', '.join(sorted(SET_KINDS))})")
        errors += _files_errors(data, sources)

    if "clips" in data:
        if isinstance(kind, str) and kind in KIND_SLOTS and kind not in CLIP_KINDS:
            errors.append(f"kind {kind!r} carries no clips ([[clips]] is for {', '.join(sorted(CLIP_KINDS))})")
        errors += _clips_errors(data, sources)

    tools = data.get("tools")
    if "tools" in data and not (isinstance(tools, list) and tools and all(_is_text(t) for t in tools)):
        errors.append("tools must be a non-empty list of strings (the generator and every tool that changed the asset)")

    errors += _licence_errors(data, "asset")

    errors += _approval(data)
    for key in ("title", "notes"):
        if key in data and not isinstance(data[key], str):
            errors.append(f"{key} must be a string")
    return errors


def _raw_errors(data: dict[str, Any]) -> list[str]:
    """[[raw]]: one or more tables, each a relative path inside the raw folder and its sha256, no file twice."""
    errors: list[str] = []
    raw = data.get("raw")
    if "raw" in data:
        if not (isinstance(raw, list) and raw and all(isinstance(r, dict) for r in raw)):
            errors.append("raw must be one or more [[raw]] tables with file and sha256")
        else:
            for index, entry in enumerate(raw):
                where = f"raw[{index}]: "
                errors += _keys(entry, RAW_REQUIRED, (), where)
                file = entry.get("file")
                if "file" in entry:
                    pure = PurePosixPath(file) if isinstance(file, str) else None
                    if (
                        pure is None
                        or not file.strip()
                        or "\\" in file
                        or pure.is_absolute()
                        or ":" in file
                        or ".." in pure.parts
                    ):
                        errors.append(f"{where}file must be a relative path inside the raw folder, with / separators")
                digest = entry.get("sha256")
                if "sha256" in entry and not (isinstance(digest, str) and SHA256_RE.fullmatch(digest)):
                    errors.append(f"{where}sha256 must be 64 lowercase hex digits")
            files = [e.get("file") for e in raw if isinstance(e.get("file"), str)]
            for file in sorted({f for f in files if files.count(f) > 1}):
                errors.append(f"raw file {file!r} is listed twice")
    return errors


def _relative_path(value: Any) -> bool:
    """A relative path with / separators and no drive, root or .. part."""
    if not (isinstance(value, str) and value.strip()) or "\\" in value or ":" in value:
        return False
    pure = PurePosixPath(value)
    return not pure.is_absolute() and ".." not in pure.parts


def _files_errors(data: dict[str, Any], sources: dict[str, dict[str, Any]] | None) -> list[str]:
    """[[files]]: a set's shipped files, each named once and built once; a pack-made file names its source record and
    the record's raw files it was made from. With sources, the record must exist, list those files and be at least as
    public as the set."""
    files = data["files"]
    if not (isinstance(files, list) and files and all(isinstance(f, dict) for f in files)):
        return ["files must be one or more [[files]] tables with name, file and sha256"]
    errors: list[str] = []
    public = data.get("public_repo_ok") is True
    for index, entry in enumerate(files):
        where = f"files[{index}]: "
        errors += _keys(entry, FILE_REQUIRED, FILE_OPTIONAL, where)
        if "name" in entry and not _relative_path(entry["name"]):
            errors.append(f"{where}name must be a relative path inside the set's export/ folder, with / separators")
        if "file" in entry and not _relative_path(entry["file"]):
            errors.append(f"{where}file must be a relative path inside the raw folder, with / separators")
        if "sha256" in entry and not (isinstance(entry["sha256"], str) and SHA256_RE.fullmatch(entry["sha256"])):
            errors.append(f"{where}sha256 must be 64 lowercase hex digits")
        source_id, made_from = entry.get("source"), entry.get("from")
        if "from" in entry:
            if "source" not in entry:
                errors.append(f"{where}from needs source (the record whose raw files it names)")
            if not (isinstance(made_from, list) and made_from and all(_relative_path(f) for f in made_from)):
                errors.append(f"{where}from must be a non-empty list of raw paths of the source record")
        if "source" not in entry:
            continue
        if not (isinstance(source_id, str) and ID_RE.fullmatch(source_id)):
            errors.append(f"{where}source must be a source record id (sources/<id>.toml)")
            continue
        if sources is None:
            continue
        record = sources.get(source_id)
        if record is None:
            errors.append(f"{where}source {source_id!r} has no record sources/{source_id}.toml")
            continue
        listed = {r.get("file") for r in record.get("raw") or [] if isinstance(r, dict)}
        for path in made_from if isinstance(made_from, list) else []:
            if isinstance(path, str) and path not in listed:
                errors.append(f"{where}{path!r} is not a [[raw]] file of sources/{source_id}.toml")
        if public and not (record.get("public_repo_ok") is True and record.get("licence") in PUBLIC_LICENCES):
            errors.append(
                f"{where}the set is public_repo_ok but source {source_id!r} may not reach the public game repo"
            )
    for key in ("name", "file"):
        values = [f.get(key) for f in files if isinstance(f.get(key), str)]
        for value in sorted({v for v in values if values.count(v) > 1}):
            errors.append(f"files: {key} {value!r} is listed twice")
    return errors


def _clips_errors(data: dict[str, Any], sources: dict[str, dict[str, Any]] | None) -> list[str]:
    """[[clips]]: each clip's keys, licence and flags; names once; a public asset carries only public clips, and an
    asset with an AI-generated clip is AI-generated itself; a record that is not a batch file names a source record."""
    clips = data["clips"]
    if not (isinstance(clips, list) and clips and all(isinstance(c, dict) for c in clips)):
        return ["clips must be one or more [[clips]] tables"]
    errors: list[str] = []
    names: set[str] = set()
    for i, clip in enumerate(clips):
        where = f"clips[{i}] ({clip.get('name', '?')})"
        errors += _keys(clip, CLIP_REQUIRED, CLIP_OPTIONAL, f"{where}: ")
        name = clip.get("name")
        if not _is_text(name):
            errors.append(f"{where}: name must be a non-empty string")
        elif name in names:
            errors.append(f"{where}: the name is listed twice")
        else:
            names.add(name)
        for key in ("loop", "ai_generated"):
            if key in clip and not isinstance(clip[key], bool):
                errors.append(f"{where}: {key} must be true or false")
        for key in ("source", "record"):
            if key in clip and not _is_text(clip[key]):
                errors.append(f"{where}: {key} must be a non-empty string")
        errors += [f"{where}: {e}" for e in _licence_errors(clip, "clip")]
        record = clip.get("record")
        if sources is not None and _is_text(record) and not record.startswith("batches/") and record not in sources:
            errors.append(f"{where}: record {record!r} is no source record (sources/<id>.toml) or batches/ file")
        if data.get("public_repo_ok") is True and clip.get("public_repo_ok") is not True:
            errors.append(f"{where}: the asset is public_repo_ok but the clip is not")
        if clip.get("ai_generated") is True and data.get("ai_generated") is not True:
            errors.append(f"{where}: an AI-generated clip makes the asset ai_generated")
        if clip.get("ai_generated") is True and "task_id" not in clip:
            errors.append(f"{where}: an AI-generated clip needs its task_id")
    return errors


def _licence_errors(data: dict[str, Any], what: str) -> list[str]:
    """licence, licence_url, credit (required for CC-BY-4.0 and NASA-PD) and public_repo_ok (never private)."""
    errors: list[str] = []
    licence = data.get("licence")
    if "licence" in data and (not isinstance(licence, str) or licence not in LICENCES):
        errors.append(f"licence {licence!r} is not one of {', '.join(sorted(LICENCES))}")
    if "licence_url" in data and not (isinstance(data["licence_url"], str) and URL_RE.fullmatch(data["licence_url"])):
        errors.append("licence_url must be an http(s) URL to the licence or terms that apply")
    if isinstance(licence, str) and licence in CREDIT_LICENCES and not _is_text(data.get("credit")):
        errors.append(f"a {licence} {what} needs credit (the attribution line)")
    if "credit" in data and not isinstance(data["credit"], str):
        errors.append("credit must be a string")

    public = data.get("public_repo_ok")
    if "public_repo_ok" in data:
        if not isinstance(public, bool):
            errors.append("public_repo_ok must be true or false")
        elif public and isinstance(licence, str) and licence in LICENCES and licence not in PUBLIC_LICENCES:
            errors.append(f"public_repo_ok is true but licence {licence!r} may never reach the public game repo")
    return errors


def find_sources(root: Path) -> list[Path]:
    """Every source record, root/sources/*.toml."""
    folder = root / "sources"
    return sorted(folder.glob("*.toml")) if folder.is_dir() else []


def validate_source(data: dict[str, Any], stem: str | None = None) -> list[str]:
    """Every problem in one parsed source record (docs/manifest.md, "Source records"); stem is its file name without
    .toml, checked against id."""
    errors = _keys(data, SOURCE_RECORD_REQUIRED, SOURCE_RECORD_OPTIONAL, "")
    source_id = data.get("id")
    if "id" in data:
        if not (isinstance(source_id, str) and ID_RE.fullmatch(source_id)):
            errors.append("id must be lowercase letters, digits and underscores")
        elif stem is not None and source_id != stem:
            errors.append(f"id {source_id!r} differs from its file name {stem}.toml")
    for key in ("title", "author"):
        if key in data and not _is_text(data[key]):
            errors.append(f"{key} must be a non-empty string")
    if "url" in data and not (isinstance(data["url"], str) and URL_RE.fullmatch(data["url"])):
        errors.append("url must be the http(s) page the source was downloaded from")
    if "ai_generated" in data and not isinstance(data["ai_generated"], bool):
        errors.append("ai_generated must be true or false")
    if "downloaded_at" in data and not _is_when(data["downloaded_at"]):
        errors.append("downloaded_at must be a TOML date or date-time (2026-10-03 or 2026-10-03T13:46:00Z)")
    if "notes" in data and not isinstance(data["notes"], str):
        errors.append("notes must be a string")
    errors += _raw_errors(data)
    errors += _licence_errors(data, "source")
    return errors


def _approval(data: dict[str, Any]) -> list[str]:
    """approved_by, approved_at and approval_pr are all empty (not approved yet) or all set."""
    if not all(key in data for key in ("approved_by", "approved_at", "approval_pr")):
        return []
    by, at, pr = data["approved_by"], data["approved_at"], data["approval_pr"]
    errors: list[str] = []
    if not (isinstance(by, list) and all(isinstance(b, str) and LOGIN_RE.fullmatch(b) for b in by)):
        errors.append("approved_by must be a list of GitHub logins ([] until approved)")
    if not (at == "" or _is_when(at)):
        errors.append('approved_at must be a TOML date or date-time ("" until approved)')
    if not (pr == "" or (isinstance(pr, str) and PR_RE.fullmatch(pr))):
        errors.append('approval_pr must be a GitHub pull request URL ("" until approved)')
    if not errors:
        filled = [bool(by), at != "", pr != ""]
        if any(filled) and not all(filled):
            errors.append("approval is all or nothing: set approved_by, approved_at and approval_pr together")
    return errors


def check_raw_hashes(data: dict[str, Any], raw_dir: Path) -> list[str]:
    """Each [[raw]] file and each set's [[files]] file exists under raw_dir and has its recorded sha256."""
    errors: list[str] = []
    for table in ("raw", "files"):
        entries = data.get(table)
        for index, entry in enumerate(entries if isinstance(entries, list) else []):
            if isinstance(entry, dict) and isinstance(entry.get("file"), str):
                errors += _hash_errors(raw_dir / entry["file"], entry.get("sha256"), f"{table}[{index}]: ")
    return errors


def check_export_hashes(data: dict[str, Any], asset_dir: Path) -> list[str]:
    """Each set file already exported (assets/<kind>/<id>/export/<name>) has its recorded sha256; a file not exported
    yet is skipped (a set is built in the raw folder first and committed once approved)."""
    errors: list[str] = []
    entries = data.get("files")
    for index, entry in enumerate(entries if isinstance(entries, list) else []):
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            path = asset_dir / "export" / entry["name"]
            if path.is_file():
                errors += _hash_errors(path, entry.get("sha256"), f"files[{index}]: ")
    return errors


def _hash_errors(path: Path, recorded: Any, where: str) -> list[str]:
    """One line if path is missing or its sha256 differs from recorded."""
    if not path.is_file():
        return [f"{where}{path.as_posix()} is missing"]
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    if digest.hexdigest() != recorded:
        return [f"{where}{path.as_posix()} has sha256 {digest.hexdigest()}, not the recorded one"]
    return []
