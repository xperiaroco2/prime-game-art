"""`refs` (Gate R's reference board): the Steam store data and HLS playlists parsed without the network."""

import tomllib
import unittest

from runner import common
from runner.commands import refs

MASTER = """#EXTM3U
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",URI="hls_264_4_audio.m3u8"
#EXT-X-STREAM-INF:BANDWIDTH=5800000,RESOLUTION=1920x1080,FRAME-RATE=30,AUDIO="audio"
hls_264_0_video.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2600000,RESOLUTION=1280x720,FRAME-RATE=30,AUDIO="audio"
hls_264_1_video.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=1000000,RESOLUTION=640x360,FRAME-RATE=30,AUDIO="audio"
hls_264_3_video.m3u8
"""

MEDIA = """#EXTM3U
#EXT-X-TARGETDURATION:3
#EXT-X-MAP:URI="dash_h264/init-stream1.m4s"
#EXTINF:3
dash_h264/chunk-stream1-00001.m4s
#EXTINF:3
dash_h264/chunk-stream1-00002.m4s
#EXT-X-ENDLIST
"""


class RefsParse(unittest.TestCase):
    def test_variant_at_or_below_height(self):
        self.assertEqual(refs.pick_variant(MASTER, 720), "hls_264_1_video.m3u8")
        self.assertEqual(refs.pick_variant(MASTER, 1080), "hls_264_0_video.m3u8")
        self.assertEqual(refs.pick_variant(MASTER, 200), "hls_264_3_video.m3u8")   # none below: the smallest
        with self.assertRaises(common.Failure):
            refs.pick_variant("#EXTM3U\n", 720)

    def test_media_playlist(self):
        init, segs = refs.parse_media(MEDIA)
        self.assertEqual(init, "dash_h264/init-stream1.m4s")
        self.assertEqual(segs, ["dash_h264/chunk-stream1-00001.m4s", "dash_h264/chunk-stream1-00002.m4s"])
        with self.assertRaises(common.Failure):
            refs.parse_media("#EXTM3U\n#EXT-X-ENDLIST\n")
        for tag in ("#EXT-X-BYTERANGE:1000@0", '#EXT-X-KEY:METHOD=AES-128,URI="k"'):   # not read: refused
            with self.assertRaises(common.Failure):
                refs.parse_media(MEDIA.replace("#EXTINF:3\ndash_h264/chunk-stream1-00002", f"{tag}\n#EXTINF:3\nx", 1))

    def test_join_keeps_the_stamp(self):
        base = "https://v.example/t/1/hls_264_master.m3u8?t=17"
        self.assertEqual(refs.join(base, "hls_264_1_video.m3u8"), "https://v.example/t/1/hls_264_1_video.m3u8?t=17")
        self.assertEqual(refs.join(base, "a/b.m4s?x=1"), "https://v.example/t/1/a/b.m4s?x=1")

    def test_store_details(self):
        d = {"screenshots": [{"path_full": "https://s/a.1920x1080.jpg?t=1"}, {"id": 2}],
             "movies": [{"name": "teaser", "hls_h264": "https://m/1.m3u8"},
                        {"name": "gameplay", "hls_h264": "https://m/2.m3u8", "highlight": True},
                        {"name": "no hls"}]}
        self.assertEqual(refs.screenshots(d), ["https://s/a.1920x1080.jpg?t=1"])
        self.assertEqual(refs.movie_masters(d), [("gameplay", "https://m/2.m3u8"), ("teaser", "https://m/1.m3u8")])
        self.assertEqual(refs.file_name("https://s/a.1920x1080.jpg?t=1"), "a.1920x1080.jpg")

    def test_refs_toml_reads_back_private(self):
        text = refs.refs_toml("2780980", 'A "game"', "2026-11-12T12:00Z",
                              [{"path": "ss_00.jpg", "kind": "screenshot", "url": "https://s/a.jpg", "sha256": "ab"},
                               {"path": "trailer_00/t0002.0.jpg", "kind": "frame", "of": "trailer_00.mp4", "t": 2.0,
                                "sha256": "cd"}])
        t = tomllib.loads(text)
        self.assertEqual(t["name"], 'A "game"')
        self.assertFalse(t["public_repo_ok"])
        self.assertFalse(t["ai_prompt_ok"])
        self.assertFalse(t["ai_generated"])
        self.assertEqual(t["licence_url"], "https://store.steampowered.com/app/2780980/")
        self.assertEqual([f["kind"] for f in t["file"]], ["screenshot", "frame"])
        self.assertEqual(t["file"][1]["t"], 2.0)


if __name__ == "__main__":
    unittest.main()
