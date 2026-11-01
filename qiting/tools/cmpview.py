#!/usr/bin/env python3
"""Render a calibrated view and compare it with its reference photo.

    cmpview.py <cal name> <reference image> [--scale 0.35] [--crop x0 y0 x1 y1] [--samples 48] [--extra "k=v; ..."]

Reads cal/<name>_sol.json (from calq.py), renders the camera in Blender at the photo's aspect (render_view.py),
fetches the JPG and writes renders/sbs_<name>.jpg (reference | render) and renders/ovl_<name>.jpg (50 % blend),
both cropped to the given box in reference-image pixels."""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xyp, bmcp, pcx
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument('name'); ap.add_argument('ref')
ap.add_argument('--scale', type=float, default=0.35)
ap.add_argument('--crop', type=float, nargs=4)
ap.add_argument('--samples', type=int, default=48)
ap.add_argument('--extra', default='')
ap.add_argument('--norender', action='store_true')
ap.add_argument('--label', default='')
a = ap.parse_args()

sol = json.load(open(os.path.join(xyp.TOOLS, 'cal', a.name + '_sol.json')))
W, H = sol['W'], sol['H']
rw, rh = int(round(W * a.scale)), int(round(H * a.scale))
rname = 'cmp_' + a.name
view = {'name': rname, 'loc': tuple(sol['loc']), 'target': tuple(sol['target']), 'lens': sol['lens'],
        'roll': sol['roll'], 'res': (rw, rh), 'samples': a.samples, 'shift': tuple(sol.get('shift', (0.0, 0.0)))}
if sol['loc'][2] < -4.9:            # photographer below the plaza (on the hillside, not modelled this round)
    view['hide'] = ('QT_stage_ground', 'QT_plaza')   # the hillside below the plaza is not modelled this round
extra = ''
if a.extra:
    extra = a.extra
code_pre = 'VIEW = %r\n%s\nVIEW.update(globals().get("VX", {}))' % (view, extra)
remote = xyp.PC_ROOT + '\\renders\\' + rname + '.jpg'
local = os.path.join(xyp.S, 'renders', rname + '.jpg')
if not a.norender:
    out = bmcp.text_of(bmcp.call('execute_blender_code', {'code': code_pre + '\n' + open(os.path.join(xyp.PROJ, 'scripts', 'render_view.py'), encoding='utf-8').read()}))
    print(out.strip().splitlines()[-2:] if out.strip() else out)
    pcx.fetch(remote, local)
ref = Image.open(a.ref).convert('RGB')
ren = Image.open(local).convert('RGB').resize((W, H), Image.LANCZOS)
box = [int(v) for v in a.crop] if a.crop else [0, 0, W, H]
rc = ref.crop(box)
nc = ren.crop(box)
h = 900
k = h / rc.size[1]
rc = rc.resize((int(rc.size[0] * k), h), Image.LANCZOS)
nc = nc.resize((int(nc.size[0] * k), h), Image.LANCZOS)
sbs = Image.new('RGB', (rc.size[0] * 2 + 12, h), (255, 255, 255))
sbs.paste(rc, (0, 0)); sbs.paste(nc, (rc.size[0] + 12, 0))
d = ImageDraw.Draw(sbs)
f = xyp.font('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 26)
d.text((10, 8), '参考 ' + a.label, fill=(255, 255, 0), font=f)
d.text((rc.size[0] + 22, 8), '渲染', fill=(255, 255, 0), font=f)
sbs.save(os.path.join(xyp.S, 'renders', 'sbs_%s.jpg' % a.name), quality=90)
ov = Image.blend(rc, nc, 0.5)
ov.save(os.path.join(xyp.S, 'renders', 'ovl_%s.jpg' % a.name), quality=90)
print('wrote sbs_%s.jpg ovl_%s.jpg' % (a.name, a.name), sbs.size)
