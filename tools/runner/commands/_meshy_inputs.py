"""Inputs of the image modes: local image files (sent as base64 data URIs) and other items' outputs (`from`).

A batch names an input as a table in an item's `images` list (docs/meshy.md):

    { file = "raw:mannequin/lanky/front.png", provenance = "own work: Blender render (art #11)", sha256 = "..." }
    { from = "c1-concept", pick = 0 }

`file` is a path relative to the raw folder (`raw:` prefix), absolute, or relative to the repository root. `sha256`
is optional; when set, the run refuses a file whose content changed since the approval. `from` names an earlier
image item of the batch; `pick` is a 0-based index into that item's `image_urls` (a multi-view set has three), and
without `pick` every image of the source is used, in Meshy's order.
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import common

# help.meshy.ai "How to Use Meshy Image to 3D" (read 2026-10-03): .png, .jpg, .jpeg (and .webp in the web app, not in
# the API docs), at most 20 MB. The API pages state no size limit, so the web app's limit is used for every image.
IMAGE_MAX_BYTES = 20 * 1024 * 1024
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
MAGIC = {"image/png": b"\x89PNG\r\n\x1a\n", "image/jpeg": b"\xff\xd8\xff"}
MODEL_TYPES = {".glb": "model/gltf-binary"}
RAW_PREFIX = "raw:"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DATA_URI = re.compile(r"^data:([^;,]+);base64,")


@dataclass
class Input:
    """One input as the batch wrote it: a local file or another item's output."""

    file: str = ""
    provenance: str = ""
    sha256: str = ""
    from_item: str = ""
    pick: int | None = None

    def describe(self) -> str:
        if self.from_item:
            return f"from {self.from_item}" + (f" image {self.pick}" if self.pick is not None else " (all its images)")
        return self.file


def parse(value: Any, where: str, errors: list[str]) -> list[Input]:
    """The `images` list of an item; problems go to errors."""
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"{where}: 'images' must be a list of tables like {{ file = ..., provenance = ... }}")
        return []
    out: list[Input] = []
    for n, raw in enumerate(value):
        at = f"{where}: images[{n}]"
        if not isinstance(raw, dict):
            errors.append(f"{at} must be a table with 'file' and 'provenance', or 'from' (and 'pick')")
            continue
        unknown = sorted(set(raw) - {"file", "provenance", "sha256", "from", "pick"})
        if unknown:
            errors.append(f"{at}: unknown key(s) {', '.join(unknown)}")
        file, source = raw.get("file"), raw.get("from")
        if (file is None) == (source is None):
            errors.append(f"{at}: set exactly one of 'file' and 'from'")
            continue
        if file is not None:
            provenance, sha = raw.get("provenance"), raw.get("sha256", "")
            if not isinstance(file, str) or not file.strip():
                errors.append(f"{at}: 'file' must be a non-empty path")
                continue
            if Path(file).suffix.lower() not in IMAGE_TYPES:
                errors.append(f"{at}: {file} is not a .png, .jpg or .jpeg file (the formats Meshy takes)")
            if not isinstance(provenance, str) or not provenance.strip():
                errors.append(f"{at}: 'provenance' must say where the image comes from, for example "
                              "\"own work: Blender render of the mannequin\"")
                provenance = ""
            if not isinstance(sha, str) or (sha and not SHA256.match(sha)):
                errors.append(f"{at}: 'sha256' must be 64 lower-case hex digits")
                sha = ""
            if "pick" in raw:
                errors.append(f"{at}: 'pick' goes with 'from' only")
            out.append(Input(file=file.strip(), provenance=provenance.strip(), sha256=sha))
        else:
            pick = raw.get("pick")
            if not isinstance(source, str) or not source.strip():
                errors.append(f"{at}: 'from' must name an earlier item")
                continue
            if pick is not None and (not isinstance(pick, int) or isinstance(pick, bool) or pick < 0):
                errors.append(f"{at}: 'pick' must be an image index 0, 1, 2, ...")
                pick = None
            for key in ("provenance", "sha256"):
                if key in raw:
                    errors.append(f"{at}: '{key}' goes with 'file' only (a 'from' input records its source)")
            out.append(Input(from_item=source.strip(), pick=pick))
    return out


def resolve(ref: str) -> Path:
    """The path of a `file` input: raw:<relative> under the raw folder, an absolute path, or repository-relative."""
    if ref.startswith(RAW_PREFIX):
        return common.raw_dir() / ref[len(RAW_PREFIX):].lstrip("/\\")
    path = Path(ref)
    return path if path.is_absolute() else common.ROOT / path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def media_type(path: Path) -> str:
    """The image's media type from its first bytes; raises Failure when it is not a PNG or JPEG that fits."""
    kind = IMAGE_TYPES.get(path.suffix.lower())
    if kind is None:
        raise common.Failure(f"{path.name} is not a .png, .jpg or .jpeg file")
    if not path.is_file():
        raise common.Failure(f"{path} does not exist")
    size = path.stat().st_size
    if size > IMAGE_MAX_BYTES:
        raise common.Failure(f"{path.name} has {size} bytes; Meshy takes images of at most {IMAGE_MAX_BYTES} bytes "
                             "(20 MB)")
    found = sniff(path)
    if found is None:
        raise common.Failure(f"{path.name} is not a PNG or JPEG image (its first bytes say otherwise)")
    if found != kind:
        raise common.Failure(f"{path.name} is a {found} file with a {path.suffix} name; rename it")
    return found


def sniff(path: Path) -> str | None:
    """image/png or image/jpeg from the file's first bytes, else None."""
    with path.open("rb") as f:
        head = f.read(8)
    return next((name for name, magic in MAGIC.items() if head.startswith(magic)), None)


def file_problems(inp: Input) -> list[str]:
    """Why a `file` input cannot be sent now: missing, wrong format, too big, or not the approved sha256."""
    path = resolve(inp.file)
    try:
        media_type(path)
    except common.Failure as exc:
        return [f"{inp.file}: {exc}"]
    if inp.sha256 and sha256(path) != inp.sha256:
        return [f"{inp.file}: its sha256 is {sha256(path)}, the batch approved {inp.sha256}"]
    return []


def data_uri(path: Path, kind: str) -> str:
    return f"data:{kind};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def record(path: Path, kind: str, **extra: Any) -> dict[str, Any]:
    """What generation.json keeps of one sent input: where it came from, its size and sha256 (never its bytes)."""
    return {**extra, "path": str(path), "media_type": kind, "bytes": path.stat().st_size, "sha256": sha256(path)}


def note(n: int, rec: dict[str, Any]) -> str:
    """The stand-in for input n's data URI in a recorded request."""
    return f"<data URI of input {n}: {rec['media_type']}, {rec['bytes']} bytes, sha256 {rec['sha256']}>"


def scrub(value: Any, notes: dict[str, str]) -> Any:
    """A request body with every data URI replaced by its note (uri -> note), for generation.json."""
    if isinstance(value, str) and DATA_URI.match(value):
        return notes.get(value, f"<data URI, {len(value)} characters>")
    if isinstance(value, dict):
        return {k: scrub(v, notes) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, notes) for v in value]
    return value
