#!/usr/bin/env python3
"""Check the planes of a render against the depth pass (scripts/depth_pass.py).

    depthcheck.py <render.jpg|png> [depth name = depth] [--ref photo.jpg]

Prints, for each band of real view distance: mean colour, luminance at the 5th / 50th / 95th percentile (shadows,
midtones, highlights), blue/red ratio of the shadows and the band's share of the frame. A picture with depth has
shadows that rise and turn bluer from band to band while the highlights hold."""
import os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xyp, pcx
a = [x for x in sys.argv[1:] if not x.startswith('--')]
img = a[0]
name = a[1] if len(a) > 1 else 'depth'
local = os.path.join(xyp.S, 'renders', name + '.npz')
if not os.path.exists(local) or '--fetch' in sys.argv:
    pcx.fetch(xyp.PC_ROOT + '\\renders\\_dbg\\%s.npz' % name, local)
D = np.load(local)
d, z, r, al = D['d'], D['z'], D['r'], D['a'].astype(np.float32)
H, W = d.shape
im = np.asarray(Image.open(img).convert('RGB').resize((W, H), Image.LANCZOS)).astype(np.float32)
lum = im @ np.array([0.2126, 0.7152, 0.0722], np.float32)
ok = al > 0.5
BANDS = [('foreground <120 m', 0, 120), ('ridge 120-700 m', 120, 700), ('slopes 0.7-3.5 km', 700, 3500),
         ('valley 3.5-7 km', 3500, 7000), ('massif >7 km', 7000, 1e9)]
print('%-20s %5s  %-15s %-14s %5s %5s' % ('band', 'share', 'mean RGB', 'lum 5/50/95', 'B/R', 'B/R lo'))
rows = []
for nm, lo, hi in BANDS:
    m = ok & (d >= lo) & (d < hi)
    if m.sum() < 50:
        continue
    p = im[m]
    l = lum[m]
    q = np.percentile(l, [5, 50, 95])
    sh = p[l <= np.percentile(l, 25)].mean(0)
    rows.append((nm, q))
    print('%-20s %4.1f%%  %-15s %-14s %5.2f %5.2f' % (nm, 100 * m.mean(), str(p.mean(0).round().astype(int).tolist()),
          str(q.round().astype(int).tolist()), p[:, 2].mean() / max(p[:, 0].mean(), 1), sh[2] / max(sh[0], 1)))
m = ~ok
p = im[m]
print('%-20s %4.1f%%  %-15s %-14s %5.2f' % ('sky', 100 * m.mean(), str(p.mean(0).round().astype(int).tolist()),
      str(np.percentile(lum[m], [5, 50, 95]).round().astype(int).tolist()), p[:, 2].mean() / p[:, 0].mean()))
print('shadow (5th pct) by band:', ' < '.join('%d' % q[0] for _, q in rows), '| midtone:', ' '.join('%d' % q[1] for _, q in rows))
