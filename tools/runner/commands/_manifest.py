"""The asset manifest schema (docs/manifest.md): every assets/<kind>/<id>/manifest.toml is checked by validate()."""

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
    "clothing": frozenset({"top", "bottom", "shoes"}),
    "hair": frozenset({"hair_or_hat"}),
    "face": frozenset({"eyes", "mouth"}),
    "accessory": frozenset({"hair_or_hat", "face_accessory", "back_item"}),
    "item": frozenset({""}),
    "prop": frozenset({""}),
    "animation": frozenset({""}),
}
# Licences an asset may carry; only the first four may ever reach the public game repo.
PUBLIC_LICENCES = frozenset({"CC0-1.0", "CC-BY-4.0", "owned-paid-output", "own-work"})
LICENCES = PUBLIC_LICENCES | {"restricted"}

TOP_REQUIRED = (
    "id", "kind", "slot", "source", "raw", "tools", "licence", "licence_url",
    "public_repo_ok", "ai_generated", "approved_by", "approved_at", "approval_pr",
)  # fmt: skip
TOP_OPTIONAL = ("title", "notes", "credit")
SOURCE_REQUIRED = ("service", "plan", "model_version", "task_ids", "generated_at")
SOURCE_OPTIONAL = ("url",)
RAW_REQUIRED = ("file", "sha256")

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


def validate(data: dict[str, Any], kind_dir: str | None = None, id_dir: str | None = None) -> list[str]:
    """Every problem in one parsed manifest, as readable lines; empty when it is valid. kind_dir and id_dir are the
    folder names it was found in (assets/<kind_dir>/<id_dir>/), checked against kind and id."""
    errors = _keys(data, TOP_REQUIRED, TOP_OPTIONAL, "")

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

    tools = data.get("tools")
    if "tools" in data and not (isinstance(tools, list) and tools and all(_is_text(t) for t in tools)):
        errors.append("tools must be a non-empty list of strings (the generator and every tool that changed the asset)")

    licence = data.get("licence")
    if "licence" in data and (not isinstance(licence, str) or licence not in LICENCES):
        errors.append(f"licence {licence!r} is not one of {', '.join(sorted(LICENCES))}")
    if "licence_url" in data and not (isinstance(data["licence_url"], str) and URL_RE.fullmatch(data["licence_url"])):
        errors.append("licence_url must be an http(s) URL to the licence or terms that apply")
    if licence == "CC-BY-4.0" and not _is_text(data.get("credit")):
        errors.append("a CC-BY-4.0 asset needs credit (the attribution line)")
    if "credit" in data and not isinstance(data["credit"], str):
        errors.append("credit must be a string")

    public = data.get("public_repo_ok")
    if "public_repo_ok" in data:
        if not isinstance(public, bool):
            errors.append("public_repo_ok must be true or false")
        elif public and isinstance(licence, str) and licence in LICENCES and licence not in PUBLIC_LICENCES:
            errors.append(f"public_repo_ok is true but licence {licence!r} may never reach the public game repo")

    errors += _approval(data)
    for key in ("title", "notes"):
        if key in data and not isinstance(data[key], str):
            errors.append(f"{key} must be a string")
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
    """Each [[raw]] file exists under raw_dir and has its recorded sha256."""
    errors: list[str] = []
    for index, entry in enumerate(data.get("raw") or []):
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            continue
        path = raw_dir / entry["file"]
        if not path.is_file():
            errors.append(f"raw[{index}]: {path.as_posix()} is missing")
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        if digest.hexdigest() != entry.get("sha256"):
            errors.append(f"raw[{index}]: {path.as_posix()} has sha256 {digest.hexdigest()}, not the recorded one")
    return errors
