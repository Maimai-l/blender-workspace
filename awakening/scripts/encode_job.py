"""Encode a PNG sequence to MP4 with Blender's sequencer:
blender -b --factory-startup -P encode_job.py -- <framedir> <out.mp4> [fps] [audio.wav]"""
import bpy, sys, os
argv = sys.argv[sys.argv.index('--') + 1:]
framedir, out = argv[0], argv[1]
fps = int(argv[2]) if len(argv) > 2 else 24
audio = argv[3] if len(argv) > 3 else None
files = sorted(f for f in os.listdir(framedir) if f.startswith('f_') and f.endswith('.png'))
sc = bpy.context.scene
sc.render.fps = fps
try:
    sc.view_settings.view_transform = 'Standard'
except TypeError:
    pass
sc.view_settings.look = 'None'
sc.view_settings.exposure = 0; sc.view_settings.gamma = 1
sc.sequencer_colorspace_settings.name = 'sRGB'
sc.render.resolution_x = 1920; sc.render.resolution_y = 1080; sc.render.resolution_percentage = 100
import bpy.types
# probe the first frame's size
img = bpy.data.images.load(os.path.join(framedir, files[0]))
sc.render.resolution_x, sc.render.resolution_y = img.size
bpy.data.images.remove(img)
se = sc.sequence_editor_create()
strips = se.strips if hasattr(se, 'strips') else se.sequences
strip = strips.new_image('frames', os.path.join(framedir, files[0]), 1, 1)
for f in files[1:]:
    strip.elements.append(f)
sc.frame_start = 1; sc.frame_end = len(files)
if audio and os.path.exists(audio):
    strips.new_sound('audio', audio, 2, 1)
r = sc.render
if hasattr(r.image_settings, 'media_type'):
    r.image_settings.media_type = 'VIDEO'
r.image_settings.file_format = 'FFMPEG'
r.ffmpeg.format = 'MPEG4'
r.ffmpeg.codec = 'H264'
r.ffmpeg.constant_rate_factor = 'HIGH'
r.ffmpeg.ffmpeg_preset = 'GOOD'
r.ffmpeg.gopsize = 12
r.ffmpeg.audio_codec = 'AAC' if audio and os.path.exists(audio) else 'NONE'
r.ffmpeg.audio_bitrate = 192
r.filepath = out
bpy.ops.render.render(animation=True)
print('ENCODED', len(files), 'frames ->', out)
