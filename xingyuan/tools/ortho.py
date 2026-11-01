# Orthorectify the calibrated aerial photo onto a horizontal plane z = Zg (plan metres).
# usage: ortho.py Zg x0 x1 y0 y1 res out.png [grid_step]
import sys, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calib
from xyp import S, font as _xyfont
Zg = float(sys.argv[1]); x0, x1, y0, y1, res = map(float, sys.argv[2:7]); out = sys.argv[7]
step = float(sys.argv[8]) if len(sys.argv) > 8 else 10.0
J = json.load(open(S + '/cal/aerial.json'))
p, loc, tgt, r = calib.solve(J['W'], J['H'], J['pts'], J['init'])
json.dump({'p': list(map(float, p))}, open(S + '/cal/aerial_p.json', 'w'))
cx, cy, cz, yaw, pitch, roll, f = p
fwd, right, up = calib.rot(yaw, pitch, roll)
W, H = J['W'], J['H']
fpx = f / 36.0 * W
img = np.asarray(Image.open(S + '/ref/xingyuan-images/杏园介绍-01_10.jpg').convert('RGB')).astype(np.float32)
Hf, Wf = img.shape[:2]
k = 0.32044   # refc px per full-res px
nx = int((x1 - x0) / res); ny = int((y1 - y0) / res)
X = x0 + (np.arange(nx) + 0.5) * res
Y = y1 - (np.arange(ny) + 0.5) * res
XX, YY = np.meshgrid(X, Y)
d = np.stack([XX - cx, YY - cy, np.full_like(XX, Zg - cz)], axis=-1)
z = d @ fwd; xr = d @ right; yr = d @ up
u = W / 2 + fpx * xr / z; v = H / 2 - fpx * yr / z
xf = u / k; yf = (v + 71.556) / k
valid = (z > 0) & (xf >= 0) & (xf < Wf - 1) & (yf >= 218) & (yf < 2231)
x0i = np.clip(np.floor(xf).astype(int), 0, Wf - 2); y0i = np.clip(np.floor(yf).astype(int), 0, Hf - 2)
fx = (xf - x0i)[..., None]; fy = (yf - y0i)[..., None]
c = (img[y0i, x0i] * (1 - fx) * (1 - fy) + img[y0i, x0i + 1] * fx * (1 - fy) + img[y0i + 1, x0i] * (1 - fx) * fy + img[y0i + 1, x0i + 1] * fx * fy)
c[~valid] = 255
o = Image.fromarray(c.astype(np.uint8))
dr = ImageDraw.Draw(o, 'RGBA')
fnt = _xyfont('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', max(11, int(1.2 / res)))
gx = math.ceil(x0 / step) * step
while gx <= x1:
    px = (gx - x0) / res
    dr.line([(px, 0), (px, ny)], fill=(0, 140, 255, 140), width=1)
    for yy in range(0, ny, int(step * 3 / res)):
        dr.text((px + 3, yy + 3), '%d' % gx, fill=(0, 90, 255, 255), font=fnt)
    gx += step
gy = math.ceil(y0 / step) * step
while gy <= y1:
    py = (y1 - gy) / res
    dr.line([(0, py), (nx, py)], fill=(255, 0, 100, 140), width=1)
    for xx in range(0, nx, int(step * 3 / res)):
        dr.text((xx + 3, py + 3), '%d' % gy, fill=(230, 0, 80, 255), font=fnt)
    gy += step
o.save(out, quality=90)
print(out, o.size, 'valid fraction', round(float(valid.mean()), 3))
