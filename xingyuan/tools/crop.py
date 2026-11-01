# usage: python3 -I crop.py <img_no> <x0> <y0> <x1> <y1> <out_name> [out_width]
# coordinates are given in the 1800-px-wide preview space
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sys
from PIL import Image
from xyp import S, font as _xyfont
no, x0, y0, x1, y1, out = sys.argv[1], *map(float, sys.argv[2:6]), sys.argv[6]
ow = int(sys.argv[7]) if len(sys.argv) > 7 else 1600
im = Image.open(f'{S}/ref/xingyuan-images/杏园介绍-01_{no}.jpg')
s = im.size[0] / 1800.0
box = tuple(int(round(v * s)) for v in (x0, y0, x1, y1))
c = im.crop(box)
r = ow / c.size[0]
c = c.resize((ow, int(c.size[1] * r)), Image.LANCZOS)
c.save(f'{S}/crops/{out}.jpg', quality=90)
print(out, box, c.size)
