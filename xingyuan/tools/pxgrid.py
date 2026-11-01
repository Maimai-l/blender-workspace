# pxgrid.py name x0 y0 x1 y1 scale [step]: crop of the full-res aerial with a pixel grid (labels in full-res px)
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sys
from PIL import Image, ImageDraw, ImageFont
from xyp import S, font as _xyfont
name = sys.argv[1]; x0, y0, x1, y1 = map(int, sys.argv[2:6]); sc = float(sys.argv[6]); step = int(sys.argv[7]) if len(sys.argv) > 7 else 10
im = Image.open(S + '/ref/xingyuan-images/杏园介绍-01_10.jpg').convert('RGB').crop((x0, y0, x1, y1))
im = im.resize((int((x1 - x0) * sc), int((y1 - y0) * sc)), Image.LANCZOS)
d = ImageDraw.Draw(im, 'RGBA')
f = _xyfont('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 13)
for x in range((x0 // step + 1) * step, x1, step):
    px = (x - x0) * sc
    mj = x % (step * 5) == 0
    d.line([(px, 0), (px, im.size[1])], fill=(255, 255, 0, 130 if mj else 40), width=1)
    if mj:
        d.text((px + 2, 2), str(x), fill=(255, 255, 0, 255), font=f)
for y in range((y0 // step + 1) * step, y1, step):
    py = (y - y0) * sc
    mj = y % (step * 5) == 0
    d.line([(0, py), (im.size[0], py)], fill=(0, 255, 255, 130 if mj else 40), width=1)
    if mj:
        d.text((2, py + 2), str(y), fill=(0, 255, 255, 255), font=f)
im.save(S + '/crops/px_%s.jpg' % name, quality=92)
print(name, im.size)
