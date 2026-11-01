# Build a north-up world-coordinate version of the floor plan with a metric grid.
# world: x_e (east, m) = 70.33 - (yv-182.7)/9.362 ; y_n (north, m) = (1119.8 - xv)/9.362  (v = 1800-wide preview coords)
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sys
from PIL import Image, ImageDraw, ImageFont
from xyp import S, font as _xyfont
im = Image.open(f'{S}/ref/xingyuan-images/杏园介绍-01_11.jpg').convert('RGB')
s = im.size[0] / 1800.0
PPM = 9.362 * s   # full-res px per metre
def full_from_world(xe, yn):
    yv = 182.7 + (70.33 - xe) * 9.362
    xv = 1119.8 - yn * 9.362
    return xv * s, yv * s
# world window
X0, X1, Y0, Y1 = -6, 76, -10, 62
out_ppm = float(sys.argv[1]) if len(sys.argv) > 1 else 40.0
W = int((X1 - X0) * out_ppm); H = int((Y1 - Y0) * out_ppm)
# rotate: north-up means image row increases as y_n decreases; full image: xv decreases as y_n increases.
# Build via affine transform: for each output pixel (u,v): xe = X0 + u/out_ppm ; yn = Y1 - v/out_ppm
# full x = s*(1119.8 - yn*9.362) ; full y = s*(182.7 + (70.33-xe)*9.362)
# PIL affine maps output (u,v) -> input (x,y) = (a*u + b*v + c, d*u + e*v + f)
k = 9.362 * s / out_ppm
a, b, c = 0.0, k, s * (1119.8 - Y1 * 9.362)
d, e, f = -k, 0.0, s * (182.7 + (70.33 - X0) * 9.362)
out = im.transform((W, H), Image.AFFINE, (a, b, c, d, e, f), resample=Image.BICUBIC, fillcolor=(255, 255, 255))
dr = ImageDraw.Draw(out, 'RGBA')
try:
    fnt = _xyfont('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', max(10, int(out_ppm * 0.45)))
except Exception:
    fnt = ImageFont.load_default()
for xe in range(X0, X1 + 1):
    u = (xe - X0) * out_ppm
    major = xe % 5 == 0
    dr.line([(u, 0), (u, H)], fill=(0, 120, 255, 120 if major else 40), width=1)
    if major:
        for yy in range(0, H, int(10 * out_ppm)):
            dr.text((u + 2, yy + 2), str(xe), fill=(0, 70, 220, 255), font=fnt)
for yn in range(Y0, Y1 + 1):
    v = (Y1 - yn) * out_ppm
    major = yn % 5 == 0
    dr.line([(0, v), (W, v)], fill=(255, 0, 90, 120 if major else 40), width=1)
    if major:
        for xx in range(0, W, int(10 * out_ppm)):
            dr.text((xx + 2, v + 2), str(yn), fill=(220, 0, 60, 255), font=fnt)
out.save(f'{S}/crops/worldplan.png')
print(out.size)
