# ortho_grid.py name Zg x0 x1 y0 y1 res  -> crops/og_<name>.jpg with 1 m minor / 5 m major grid and labels
import sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ortho_arr as OA
name = sys.argv[1]; Zg = float(sys.argv[2]); x0, x1, y0, y1, res = map(float, sys.argv[3:8])
c, valid, XX, YY = OA.ortho(Zg, x0, x1, y0, y1, res)
c[~valid] = 255
im = Image.fromarray(c.astype(np.uint8))
d = ImageDraw.Draw(im, 'RGBA')
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 15)
W, H = im.size
for gx in range(int(math.ceil(x0)), int(x1) + 1):
    px = (gx - x0) / res
    major = gx % 5 == 0
    d.line([(px, 0), (px, H)], fill=(0, 200, 255, 150 if major else 45), width=1)
    if major:
        for yy in range(0, H, 200):
            d.text((px + 2, yy + 2), str(gx), fill=(0, 230, 255, 255), font=f)
for gy in range(int(math.ceil(y0)), int(y1) + 1):
    py = (y1 - gy) / res
    major = gy % 5 == 0
    d.line([(0, py), (W, py)], fill=(255, 60, 160, 150 if major else 45), width=1)
    if major:
        for xx in range(0, W, 200):
            d.text((xx + 2, py + 2), str(gy), fill=(255, 120, 200, 255), font=f)
im.save(S + '/crops/og_%s.jpg' % name, quality=90)
print(name, im.size)
