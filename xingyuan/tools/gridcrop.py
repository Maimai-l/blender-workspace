# Crop a region of a reference image (full-res pixel coords) and overlay a metric grid.
# usage: gridcrop.py img_no x0 y0 x1 y1 out px_per_m x_datum y_datum [step_m] [out_w]
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sys
from PIL import Image, ImageDraw, ImageFont
from xyp import S, font as _xyfont
no = sys.argv[1]
x0, y0, x1, y1 = map(int, sys.argv[2:6])
out = sys.argv[6]
ppm = float(sys.argv[7]); xd = float(sys.argv[8]); yd = float(sys.argv[9])
step = float(sys.argv[10]) if len(sys.argv) > 10 else 0.5
ow = int(sys.argv[11]) if len(sys.argv) > 11 else 1800
im = Image.open(f'{S}/ref/xingyuan-images/杏园介绍-01_{no}.jpg').convert('RGB')
c = im.crop((x0, y0, x1, y1))
r = ow / c.size[0]
c = c.resize((ow, int(c.size[1] * r)), Image.LANCZOS)
d = ImageDraw.Draw(c, 'RGBA')
try:
    f = _xyfont('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
except Exception:
    f = ImageFont.load_default()
import math
# vertical lines (x in metres from xd)
m0 = math.floor((x0 - xd) / ppm / step) * step
m = m0
while xd + m * ppm <= x1:
    px = (xd + m * ppm - x0) * r
    if px >= 0:
        major = abs(m / (step * 2) - round(m / (step * 2))) < 1e-6
        d.line([(px, 0), (px, c.size[1])], fill=(0, 120, 255, 110 if major else 50), width=1)
        if major:
            d.text((px + 2, 2), f'{m:.1f}', fill=(0, 80, 220, 255), font=f)
    m += step
m = math.floor((yd - y1) / ppm / step) * step
while yd - m * ppm >= y0:
    py = (yd - m * ppm - y0) * r
    if py <= c.size[1]:
        major = abs(m / (step * 2) - round(m / (step * 2))) < 1e-6
        d.line([(0, py), (c.size[0], py)], fill=(255, 0, 80, 110 if major else 50), width=1)
        if major:
            d.text((2, py + 1), f'{m:.1f}', fill=(220, 0, 60, 255), font=f)
    m += step
c.save(f'{S}/crops/{out}.jpg', quality=90)
print(out, c.size)
