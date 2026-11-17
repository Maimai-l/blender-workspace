#!/usr/bin/env python3
"""Render the scene camera from a Blender timer, fetch the JPG, print its local path.

    rr.py <name> [--scale 50] [--samples 64] [--cam CAM] [--border x0 y0 x1 y1] [--res 3840x2160]
          [--pre "python code"] [--png] [--timeout 3600]

--border: fractions of the frame (0..1, origin top-left, like image coordinates); renders only that region at the
given scale and crops to it. Output on the PC: renders\\_dbg\\<name>.jpg ; here: ~/.cache/mana_cafe/renders/<name>.jpg"""
import argparse, os, sys, uuid, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xyp, bmcp, pcx

ap = argparse.ArgumentParser()
ap.add_argument('name')
ap.add_argument('--scale', type=int, default=50)
ap.add_argument('--samples', type=int, default=64)
ap.add_argument('--cam', default='')
ap.add_argument('--border', type=float, nargs=4)
ap.add_argument('--res', default='')
ap.add_argument('--pre', default='')
ap.add_argument('--png', action='store_true')
ap.add_argument('--timeout', type=int, default=3600)
ap.add_argument('--nofetch', action='store_true')
a = ap.parse_args()
ext = 'png' if a.png else 'jpg'
remote = xyp.PC_ROOT + '\\renders\\_dbg\\%s.%s' % (a.name, ext)
job = xyp.PC_ROOT + '\\renders\\_dbg\\job_%s.txt' % uuid.uuid4().hex[:8]
code = '''
import bpy, time, os, sys
LIB = r'D:\\Blender\\Projects\\mana_cafe\\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
sc = bpy.context.scene
%(pre)s
cam = %(cam)r
if cam: sc.camera = bpy.data.objects[cam]
res = %(res)r
if res:
    sc.render.resolution_x, sc.render.resolution_y = [int(v) for v in res.split('x')]
sc.render.resolution_percentage = %(scale)d
sc.cycles.samples = %(samples)d
b = %(border)r
sc.render.use_border = bool(b)
sc.render.use_crop_to_border = bool(b)
if b:
    sc.render.border_min_x, sc.render.border_max_x = b[0], b[2]
    sc.render.border_min_y, sc.render.border_max_y = 1 - b[3], 1 - b[1]
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = %(fmt)r
if %(fmt)r == 'JPEG': sc.render.image_settings.quality = 93
else: sc.render.image_settings.color_depth = '8'
sc.render.filepath = %(remote)r
os.makedirs(os.path.dirname(%(remote)r), exist_ok=True)
t0 = time.time()
bpy.ops.render.render(write_still=True)
sc.render.use_border = False
print('rendered %%s %%dx%%d@%%d%%%% %%d spp in %%.1fs' %% (%(remote)r, sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage, sc.cycles.samples, time.time() - t0))
''' % dict(pre=a.pre, cam=a.cam, res=a.res, scale=a.scale, samples=a.samples, border=a.border,
           fmt='PNG' if a.png else 'JPEG', remote=remote)
wrapper = '''
import bpy, io, os, contextlib, traceback
_JOB = %r
_CODE = %r
def _run_job():
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(_CODE, 'render_job', 'exec'), {'__name__': '__main__', 'bpy': bpy})
    except BaseException:
        buf.write('\\nFAILED\\n' + traceback.format_exc())
    os.makedirs(os.path.dirname(_JOB), exist_ok=True)
    with open(_JOB + '.tmp', 'w', encoding='utf-8') as fh:
        fh.write(buf.getvalue())
    os.replace(_JOB + '.tmp', _JOB)
    return None
bpy.app.timers.register(_run_job, first_interval=0.3)
print('deferred', _JOB)
''' % (job, code)
out = bmcp.text_of(bmcp.call('execute_blender_code', {'code': wrapper}))
if 'deferred' not in out:
    sys.exit(out)
txt = pcx.wait_file(job, timeout_s=a.timeout)
print(txt.strip())
if 'FAILED' in txt or a.nofetch:
    sys.exit(0)
local = os.path.join(xyp.S, 'renders', a.name + '.' + ext)
pcx.fetch(remote, local)
print(local)
