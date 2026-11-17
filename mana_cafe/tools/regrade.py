#!/usr/bin/env python3
"""Re-save the last render ('Render Result') with other display settings, without rendering again.

    regrade.py <name> "<python: vs = scene.view_settings; curve(points) sets the combined curve>"

Fetches renders\\_dbg\\<name>.jpg and prints tone statistics of a few picture regions."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xyp, bmcp, pcx
name, pre = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else '')
remote = xyp.PC_ROOT + '\\renders\\_dbg\\%s.jpg' % name
code = '''
import bpy
sc = bpy.context.scene
vs = sc.view_settings
def curve(pts):
    vs.use_curve_mapping = True
    cm = vs.curve_mapping; cv = cm.curves[3]
    while len(cv.points) > 2: cv.points.remove(cv.points[1])
    cv.points[0].location = pts[0]; cv.points[1].location = pts[-1]
    for p in pts[1:-1]: cv.points.new(p[0], p[1])
    cm.update()
def look(n):
    try:
        vs.look = n
    except TypeError as e:
        print('look not set:', str(e)[-300:])
%s
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 93
bpy.data.images['Render Result'].save_render(%r, scene=sc)
print('look', vs.look, 'exposure', round(vs.exposure, 2), 'gamma', vs.gamma, 'curves', vs.use_curve_mapping)
''' % (pre, remote)
print(bmcp.text_of(bmcp.call('execute_blender_code', {'code': code})).strip()[-400:])
local = os.path.join(xyp.S, 'renders', name + '.jpg')
pcx.fetch(remote, local)
from PIL import Image
import numpy as np
a = np.asarray(Image.open(local).convert('RGB')).astype(float)
H, W = a.shape[:2]
def st(x0, y0, x1, y1):
    p = a[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)].reshape(-1, 3)
    return p.mean(0).round().astype(int).tolist(), np.percentile(p.mean(1), [5, 50, 95]).round().astype(int).tolist()
for k, r in (('sky', (0.78, 0.07, 0.94, 0.15)), ('snow lit', (0.74, 0.21, 0.766, 0.24)), ('snow shade', (0.72, 0.28, 0.74, 0.305)),
             ('left mtn', (0.16, 0.37, 0.26, 0.46)), ('meadow', (0.60, 0.74, 0.73, 0.83)), ('gravel', (0.36, 0.83, 0.47, 0.88)),
             ('corten', (0.18, 0.70, 0.26, 0.76)), ('valley cloud', (0.86, 0.70, 0.96, 0.80))):
    print('%-13s' % k, st(*r))
hsv = np.asarray(Image.fromarray(a.astype(np.uint8)).convert('HSV')).astype(float)
print('mean', a.mean((0, 1)).round(), 'sat', hsv[..., 1].mean().round(1), 'lum pct 1/10/50/90/99', np.percentile(a.mean(2), [1, 10, 50, 90, 99]).round())
print(local)
