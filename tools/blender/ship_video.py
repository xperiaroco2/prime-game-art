"""The ship's walk-through MP4 from its PNG frames (`tools/run.py ship --walk`, art #263, docs/ship.md), in headless
Blender's own FFmpeg, by encode_clips.py's route (an image strip in the sequencer, H.264 in MP4, its `strips` helper),
played once, at an average bit rate that fits the file under --max-mb (88% of it over the clip's length; the night's
SSAO grain and the stars make constant quality too large: 20 MB for 90 s even at its lowest), the slower x264 preset
and a 4 s keyframe interval:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/ship_video.py -- \
      --frames <folder with 00000.png ...> --out <file.mp4> --fps 24 --max-mb 15
"""

import argparse
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import encode_clips  # noqa: E402

def encode(folder, out, fps, max_mb):
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".png"))
    if not files:
        raise SystemExit(f"{folder}: no PNG frames")
    scene = bpy.data.scenes.new("walk")
    se = scene.sequence_editor_create()
    first = bpy.data.images.load(os.path.join(folder, files[0]))
    width, height = first.size
    bpy.data.images.remove(first)
    strip = encode_clips.strips(se).new_image(name="frames", filepath=os.path.join(folder, files[0]), channel=1,
                                              frame_start=1)
    for name in files[1:]:
        strip.elements.append(name)
    strip.frame_final_duration = len(files)  # as encode_clips.py (Blender 5.2 warns it goes in 6.0)
    r = scene.render
    r.fps = fps
    r.resolution_x, r.resolution_y, r.resolution_percentage = width, height, 100
    scene.frame_start, scene.frame_end = 1, len(files)
    scene.view_settings.view_transform = "Standard"
    im = r.image_settings
    if hasattr(im, "media_type"):
        im.media_type = "VIDEO"
    im.file_format = "FFMPEG"
    r.ffmpeg.format = "MPEG4"
    r.ffmpeg.codec = "H264"
    kbps = int(max_mb * 0.88 * 8 * 1024 / (len(files) / fps))
    r.ffmpeg.constant_rate_factor = "NONE"
    r.ffmpeg.video_bitrate = kbps
    r.ffmpeg.minrate = 0
    r.ffmpeg.maxrate = 2 * kbps
    r.ffmpeg.buffersize = 2 * kbps
    r.ffmpeg.gopsize = 4 * fps
    r.ffmpeg.ffmpeg_preset = "BEST"
    r.ffmpeg.audio_codec = "NONE"
    r.filepath = out
    r.use_file_extension = False
    bpy.ops.render.render(animation=True, scene=scene.name)
    return len(files), width, height, kbps


def main():
    p = argparse.ArgumentParser(prog="ship_video.py")
    p.add_argument("--frames", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--max-mb", type=float, default=15.0)
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    n, w, h, kbps = encode(args.frames, args.out, args.fps, args.max_mb)
    mb = os.path.getsize(args.out) / 2 ** 20
    print(f"ENCODED {args.out} {w}x{h} {n} frames {kbps} kbit/s {mb:.1f} MB")
    if mb > args.max_mb:
        raise SystemExit(f"{args.out}: {mb:.1f} MB, over {args.max_mb} MB")


if __name__ == "__main__":
    main()
