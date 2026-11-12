"""`refs`: Gate R's reference board (docs/references.md, docs/decisions/2026-11-12-reference-first.md).

`refs steam <appid>... --board NAME` fetches each game's official store media from Steam: the screenshots, and frames
from its trailers every `--every` seconds (the 720p HLS stream's fragments joined into one MP4, read by headless
Blender's own decoder, tools/blender/refs_frames.py). Into `<raw>/refs/<board>/<appid>/`: the files, `refs.toml`
(source URL, sha256, date per file; it stands in for `sources/<id>.toml` for a private reference) and `sheet_NN.jpg`,
contact sheets of 24 tiles. Private: never committed, never put in an AI prompt. A game that fails is reported and
skipped; the run then exits 1. Runs for minutes: start it in the background.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.client
import json
import re
import time
import urllib.error
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
    parser.add_argument("--overwrite", action="store_true",
                        help="write into a game's folder that already has files (files no longer listed stay)")


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
        if line.startswith(("#EXT-X-BYTERANGE", "#EXT-X-KEY")):
            raise common.Failure(f"the trailer's HLS playlist uses {line.split(':')[0]}, which refs does not read")
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
    store = STORE.format(app=app)
    out = [f"app = {toml_str(app)}", f"name = {toml_str(name)}", f"store = {toml_str(store)}",
           f"fetched = {toml_str(fetched)}", f"licence = {toml_str(NOTE)}", f"licence_url = {toml_str(store)}",
           "public_repo_ok = false", "ai_prompt_ok = false", "ai_generated = false", ""]
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
        except urllib.error.HTTPError as e:
            if e.code < 500 or k == tries - 1:   # a 4xx will not change on a retry
                raise common.Failure(f"could not fetch {url}: HTTP {e.code}") from e
            time.sleep(2 * (k + 1))
        except (OSError, http.client.HTTPException) as e:
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
def fetch_app(app: str, board: Path, fetched: str, args: argparse.Namespace) -> str:
    """One game into <board>/<app>/; returns its summary line. Raises common.Failure."""
    data = json.loads(get(DETAILS.format(app=app)).decode("utf-8")).get(str(app), {})
    if not data.get("success"):
        raise common.Failure(f"Steam has no store page data for app {app} (an id, age gate or region)")
    d = data["data"]
    name = d.get("name", "")
    out = board / str(app)
    if out.is_dir() and any(out.iterdir()) and not args.overwrite:
        raise common.Failure(f"{out} already has files: use another --board, or --overwrite")
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    index = out / "refs.toml"

    def write_index() -> None:   # after every step, so no fetched file is ever left without its record
        index.write_text(refs_toml(str(app), name, fetched, rows), encoding="utf-8")

    for k, url in enumerate(screenshots(d)):
        body = get(url)
        f = out / f"ss_{k:02d}{Path(file_name(url)).suffix or '.jpg'}"
        f.write_bytes(body)
        rows.append({"path": f.name, "kind": "screenshot", "url": url, "sha256": sha(body)})
    write_index()
    videos = []
    if not args.no_movies:
        for k, (title, master) in enumerate(movie_masters(d)[: args.movies]):
            mp4 = out / f"trailer_{k:02d}.mp4"
            var = fetch_trailer(master, args.height, mp4)
            rows.append({"path": mp4.name, "kind": "trailer", "title": title, "url": var,
                         "sha256": sha(mp4.read_bytes())})
            videos.append(mp4)
            write_index()
    images = [out / r["path"] for r in rows if r["kind"] == "screenshot"]
    if not images and not videos:
        raise common.Failure(f"{app} {name}: the store page has no screenshots or trailers")
    res = blender.run_script(SCRIPT, ["--out", str(out), "--every", str(args.every), "--sheet", str(out / "sheet"),
                                      "--images", *map(str, images), "--videos", *map(str, videos)], timeout=900)
    per_video = dict.fromkeys((v.name for v in videos), 0)
    for line in (res.stdout or "").splitlines():
        if line.startswith("REFS_FRAME "):
            fr = json.loads(line[len("REFS_FRAME "):])
            p = Path(fr["path"])
            per_video[Path(fr["video"]).name] += 1
            rows.append({"path": p.relative_to(out).as_posix(), "kind": "frame", "of": Path(fr["video"]).name,
                         "t": fr["t"], "sha256": sha(p.read_bytes())})
    write_index()
    empty = [v for v, n in per_video.items() if not n]
    if empty:
        raise common.Failure(f"{app} {name}: Blender read no frames from {', '.join(empty)}")
    n = {k: sum(r["kind"] == k for r in rows) for k in ("screenshot", "trailer", "frame")}
    return (f"{app} {name}: {n['screenshot']} screenshots, {n['trailer']} trailers, {n['frame']} frames -> {out} "
            "(sheet_NN.jpg)")


def run(args: argparse.Namespace) -> int:
    if args.every < 0.5:
        raise common.Failure("--every is at least 0.5 s")
    board = common.raw_dir() / "refs" / args.board
    fetched = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    failed = []
    for app in args.apps:
        try:
            common.ok(fetch_app(str(app), board, fetched, args))
        except common.Failure as e:
            common.bad(f"{app}: {e}")
            failed.append(app)
    common.say(f"refs: board {board}" + (f"; failed: {' '.join(failed)}" if failed else ""))
    return 1 if failed else 0
