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
ap.add_argument('--thin', action='store_true', help='leave out planting and lamps between the camera and the building '
                '(photos older than the 2026 aerials, taken before the trees grew)')
a = ap.parse_args()

sol = json.load(open(os.path.join(xyp.TOOLS, 'cal', a.name + '_sol.json')))
W, H = sol['W'], sol['H']
rw, rh = int(round(W * a.scale)), int(round(H * a.scale))
rname = 'cmp_' + a.name
view = {'name': rname, 'loc': tuple(sol['loc']), 'target': tuple(sol['target']), 'lens': sol['lens'],
        'roll': sol['roll'], 'res': (rw, rh), 'samples': a.samples, 'shift': tuple(sol.get('shift', (0.0, 0.0))), 'ky': sol.get('ky', 1.0),
        'defer': True}
extra = ''
if a.extra:
    extra = a.extra
if a.thin:
    # convex hull of the camera's surroundings (10 m) and the building's footprint (podium r 12 m, north stair to y 23 m)
    import math as _m
    cx_, cy_ = sol['loc'][:2]
    pts = ([(cx_ + 10 * _m.cos(t), cy_ + 10 * _m.sin(t)) for t in [k * _m.pi / 8 for k in range(16)]] +
           [(12.5 * _m.cos(t), 12.5 * _m.sin(t)) for t in [k * _m.pi / 12 for k in range(24)]] + [(-2.5, 23.5), (2.5, 23.5)])
    pts = sorted(set(pts))
    def _cross(o, a_, b_):
        return (a_[0] - o[0]) * (b_[1] - o[1]) - (a_[1] - o[1]) * (b_[0] - o[0])
    lo, hi = [], []
    for p_ in pts:
        while len(lo) >= 2 and _cross(lo[-2], lo[-1], p_) <= 0: lo.pop()
        lo.append(p_)
    for p_ in reversed(pts):
        while len(hi) >= 2 and _cross(hi[-2], hi[-1], p_) <= 0: hi.pop()
        hi.append(p_)
    view['thin'] = [(round(x, 2), round(y, 2)) for x, y in lo[:-1] + hi[:-1]]
code_pre = 'VIEW = %r\n%s\nVIEW.update(globals().get("VX", {}))' % (view, extra)
remote = xyp.PC_ROOT + '\\renders\\' + rname + '.jpg'
local = os.path.join(xyp.S, 'renders', rname + '.jpg')
if not a.norender:
    out = bmcp.text_of(bmcp.call('execute_blender_code', {'code': code_pre + '\n' + open(os.path.join(xyp.PROJ, 'scripts', 'render_view.py'), encoding='utf-8').read()}))
    print(out.strip().splitlines()[-2:] if out.strip() else out)
    if 'deferred' in out:            # the render runs from a timer in Blender; wait for its marker through exec
        msg = pcx.wait_file(remote + '.done')
        print(msg)
        if msg.startswith('FAILED'):
            sys.exit(1)
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
