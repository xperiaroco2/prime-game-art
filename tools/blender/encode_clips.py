"""Short looping MP4 (H.264) clips from PNG frame folders, with Blender's own FFmpeg in the background
(`tools/run.py frames --video`, docs/godot.md):

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/encode_clips.py -- \
      --frames <folder with 0000.png ...> [<folder> ...] --out <folder> --fps 24 --repeat 3

Each folder becomes <out>/<folder name>.mp4: its frames in name order, played --repeat times (a page loops the video;
the repeats are for players that do not), at the frames' size, constant-quality H.264 in an MP4 container.
"""

import argparse
import os
import sys

import bpy


def strips(se):
    """The sequencer's strip collection (Blender 5 calls it strips, earlier versions sequences)."""
    return se.strips if hasattr(se, "strips") else se.sequences


def encode(folder, out, fps, repeat):
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".png"))
    if not files:
        raise SystemExit(f"{folder}: no PNG frames")
    scene = bpy.data.scenes.new("clip_" + os.path.basename(folder))
    se = scene.sequence_editor_create()
    first = bpy.data.images.load(os.path.join(folder, files[0]))
    width, height = first.size
    bpy.data.images.remove(first)
    start = 1
    for _ in range(repeat):
        strip = strips(se).new_image(name="frames", filepath=os.path.join(folder, files[0]), channel=1, frame_start=start)
        for name in files[1:]:
            strip.elements.append(name)
        strip.frame_final_duration = len(files)
        start += len(files)
    r = scene.render
    r.fps = fps
    r.resolution_x, r.resolution_y, r.resolution_percentage = width, height, 100
    scene.frame_start, scene.frame_end = 1, start - 1
    scene.view_settings.view_transform = "Standard"
    im = r.image_settings
    if hasattr(im, "media_type"):
        im.media_type = "VIDEO"
    im.file_format = "FFMPEG"
    r.ffmpeg.format = "MPEG4"
    r.ffmpeg.codec = "H264"
    r.ffmpeg.constant_rate_factor = "HIGH"
    r.ffmpeg.ffmpeg_preset = "GOOD"
    r.ffmpeg.audio_codec = "NONE"
    r.filepath = out
    r.use_file_extension = False
    bpy.ops.render.render(animation=True, scene=scene.name)
    print("ENCODED", out, width, "x", height, len(files) * repeat, "frames")


def main():
    p = argparse.ArgumentParser(prog="encode_clips.py")
    p.add_argument("--frames", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--repeat", type=int, default=3)
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    os.makedirs(args.out, exist_ok=True)
    for folder in args.frames:
        encode(folder, os.path.join(args.out, os.path.basename(os.path.normpath(folder)) + ".mp4"), args.fps, args.repeat)


if __name__ == "__main__":
    main()
