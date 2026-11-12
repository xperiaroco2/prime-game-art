"""`refs`: Gate R's reference board (docs/references.md, docs/decisions/2026-11-12-reference-first.md).

`refs steam <appid>... --board NAME` fetches each game's official store media from Steam: the screenshots, and frames
from its trailers every `--every` seconds (the 720p HLS stream's fragments joined into one MP4, read by headless
Blender's own decoder, tools/blender/refs_frames.py). Into `<raw>/refs/<board>/<appid>/`: the files, `refs.toml`
(source URL, sha256, date per file) and `sheet.jpg`, a contact sheet of everything. Private: never committed, never
put in an AI prompt.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .. import blender, common

NAME = "refs"
HELP = "Gate R: fetch games' official store screenshots and trailer frames into a private reference board"

DETAILS = "https://store.steampowered.com/api/appdetails?appids={app}&l=english"
STORE = "https://store.steampowered.com/app/{app}/"
UA = "prime-game-art-refs/1"
SCRIPT = "refs_frames.py"
NOTE = ("the game's official store media (Steam), fetched for internal reference only: never committed, never shipped, "
        "never put in an AI prompt; we copy the idea, never the art")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source", choices=["steam"], help="where the media comes from (Steam's store)")
    parser.add_argument("apps", nargs="+", help="Steam app ids")
    parser.add_argument("--board", required=True, help="the board's name, a folder under <raw>/refs/")
    parser.add_argument("--movies", type=int, default=3, help="trailers per game to sample (default 3)")
    parser.add_argument("--every", type=float, default=2.0, help="seconds between trailer frames (default 2)")
    parser.add_argument("--no-movies", action="store_true", help="screenshots only")
    parser.add_argument("--height", type=int, default=720, help="the trailer stream's height (default 720)")


# ------------------------------------------------------------------------------------------ parsing (pure)
def screenshots(details: dict) -> list[str]:
    return [s["path_full"] for s in details.get("screenshots", []) if s.get("path_full")]


def movie_masters(details: dict) -> list[tuple[str, str]]:
    """(name, HLS master URL) per trailer, highlighted ones first."""
    ms = sorted(details.get("movies", []), key=lambda m: not m.get("highlight"))
    return [(m.get("name", str(m.get("id"))), m["hls_h264"]) for m in ms if m.get("hls_h264")]


def pick_variant(master: str, height: int) -> str:
    """The variant playlist's URI whose height is the largest at or below `height` (else the smallest)."""
    rows, lines = [], master.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            m = re.search(r"RESOLUTION=\d+x(\d+)", line)
            uri = next((x.strip() for x in lines[i + 1:] if x.strip() and not x.startswith("#")), None)
            if m and uri:
                rows.append((int(m.group(1)), uri))
    if not rows:
        raise common.Failure("the trailer's HLS master lists no video stream")
    below = [r for r in rows if r[0] <= height]
    return (max(below) if below else min(rows))[1]


def parse_media(text: str) -> tuple[str | None, list[str]]:
    """(the init segment's URI or None, the segments' URIs) of an HLS media playlist."""
    init, segs = None, []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXT-X-MAP"):
            m = re.search(r'URI="([^"]+)"', line)
            init = m.group(1) if m else None
        elif line and not line.startswith("#"):
            segs.append(line)
    if not segs:
        raise common.Failure("the trailer's HLS playlist lists no segments")
    return init, segs


def join(base: str, uri: str) -> str:
    """A playlist entry against its playlist's URL, keeping the base's query (Steam's ?t= stamp) when it has none."""
    url = urllib.parse.urljoin(base, uri)
    q = urllib.parse.urlsplit(base).query
    return url if "?" in uri or not q else f"{url}?{q}"


def file_name(url: str) -> str:
    return Path(urllib.parse.urlsplit(url).path).name


def toml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def refs_toml(app: str, name: str, fetched: str, rows: list[dict]) -> str:
    out = [f"app = {toml_str(app)}", f"name = {toml_str(name)}", f"store = {toml_str(STORE.format(app=app))}",
           f"fetched = {toml_str(fetched)}", f"licence = {toml_str(NOTE)}", "public_repo_ok = false",
           "ai_prompt_ok = false", ""]
    for r in rows:
        out.append("[[file]]")
        for k, v in r.items():
            out.append(f"{k} = {toml_str(v) if isinstance(v, str) else json.dumps(v)}")
        out.append("")
    return "\n".join(out)


# ------------------------------------------------------------------------------------------- network
def get(url: str, tries: int = 3) -> bytes:
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except OSError as e:
            if k == tries - 1:
                raise common.Failure(f"could not fetch {url}: {e}") from e
            time.sleep(2 * (k + 1))
    raise AssertionError


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_trailer(master_url: str, height: int, dest: Path) -> str:
    """The trailer's stream at `height` as one MP4 (init + fragments); returns the variant playlist's URL."""
    var = join(master_url, pick_variant(get(master_url).decode("utf-8"), height))
    init, segs = parse_media(get(var).decode("utf-8"))
    parts = ([get(join(var, init))] if init else []) + [get(join(var, s)) for s in segs]
    dest.write_bytes(b"".join(parts))
    return var


# ------------------------------------------------------------------------------------------------ run
def run(args: argparse.Namespace) -> int:
    board = common.raw_dir() / "refs" / args.board
    fetched = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    for app in args.apps:
        data = json.loads(get(DETAILS.format(app=app)).decode("utf-8")).get(str(app), {})
        if not data.get("success"):
            raise common.Failure(f"Steam has no store page data for app {app}")
        d = data["data"]
        out = board / str(app)
        out.mkdir(parents=True, exist_ok=True)
        rows: list[dict] = []
        for k, url in enumerate(screenshots(d)):
            body = get(url)
            f = out / f"ss_{k:02d}{Path(file_name(url)).suffix or '.jpg'}"
            f.write_bytes(body)
            rows.append({"path": f.name, "kind": "screenshot", "url": url, "sha256": sha(body)})
        videos = []
        if not args.no_movies:
            for k, (title, master) in enumerate(movie_masters(d)[: args.movies]):
                mp4 = out / f"trailer_{k:02d}.mp4"
                var = fetch_trailer(master, args.height, mp4)
                rows.append({"path": mp4.name, "kind": "trailer", "title": title, "url": var,
                             "sha256": sha(mp4.read_bytes())})
                videos.append(mp4)
        cmd = ["--out", str(out), "--every", str(args.every), "--sheet", str(out / "sheet.jpg"),
               "--images", *[str(out / r["path"]) for r in rows if r["kind"] == "screenshot"],
               "--videos", *[str(v) for v in videos]]
        res = blender.run_script(SCRIPT, cmd, timeout=900)
        for line in (res.stdout or "").splitlines():
            if line.startswith("REFS_FRAME "):
                fr = json.loads(line[len("REFS_FRAME "):])
                p = Path(fr["path"])
                rows.append({"path": p.relative_to(out).as_posix(), "kind": "frame", "of": Path(fr["video"]).name,
                             "t": fr["t"], "sha256": sha(p.read_bytes())})
        (out / "refs.toml").write_text(refs_toml(str(app), d.get("name", ""), fetched, rows), encoding="utf-8")
        n = {k: sum(r["kind"] == k for r in rows) for k in ("screenshot", "trailer", "frame")}
        common.ok(f"{app} {d.get('name', '')}: {n['screenshot']} screenshots, {n['trailer']} trailers, "
                  f"{n['frame']} frames -> {out} (sheet.jpg)")
    common.say(f"refs: board {board}")
    return 0
