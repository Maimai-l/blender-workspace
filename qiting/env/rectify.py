#!/usr/bin/env python3
"""rectify.py <cal name> <image> <z> <x0> <y0> <x1> <y1> <res m/px> <out.png> [--dwg]
Ortho-rectify a calibrated photo onto the horizontal plane Z = z (model metres) over the box [x0,x1] x [y0,y1],
with a labelled 5 m grid; --dwg blends in the DWG lines (red) for comparison."""
import sys, json, math, os
import numpy as np, cv2
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import edgefit as EF

args = [a for a in sys.argv[1:] if not a.startswith('--')]
name, img_path = args[0], args[1]
z, x0, y0, x1, y1, res = map(float, args[2:8])
out = args[8]
J = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'cal', name + '_sol.json')))
d = np.array(J['target']) - np.array(J['loc'])
p = list(J['loc']) + [math.atan2(d[0], d[1]), math.atan2(d[2], math.hypot(d[0], d[1])), J['roll'], J['f_px']]
EF.KY[0] = J.get('ky', 1.0); EF.K1[0] = J.get('k1', 0.0)
img = cv2.imread(img_path)
H, W = img.shape[:2]
xs = np.arange(x0, x1, res); ys = np.arange(y1, y0, -res)
X, Y = np.meshgrid(xs, ys)
P = np.stack([X.ravel(), Y.ravel(), np.full(X.size, z)], 1)
uv, zc = EF.project(p, P, W, H)
mapx = uv[:, 0].reshape(X.shape).astype(np.float32)
mapy = uv[:, 1].reshape(X.shape).astype(np.float32)
mapx[zc.reshape(X.shape) < 0.5] = -1
o = cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderValue=(40, 40, 40))
if '--dwg' in sys.argv:
    CX, CY, S = 596.26, 597.08, 0.245
    dw = cv2.imread('/root/.cache/qiting/ref/photos/2390cc8d040e61ce45ed5e0b64655b0b.jpg')
    dmx = (CX + X / S).astype(np.float32); dmy = (CY - Y / S).astype(np.float32)
    dd = cv2.remap(dw, dmx, dmy, cv2.INTER_NEAREST, borderValue=(0, 0, 0))
    wmask = dd.min(axis=2) > 125
    o[wmask] = (0.35 * o[wmask] + np.array([0, 0, 165])).astype(np.uint8)
k = 1
for gx in np.arange(math.ceil(x0 / 5) * 5, x1, 5):
    u = int((gx - x0) / res)
    cv2.line(o, (u, 0), (u, o.shape[0]), (255, 255, 0) if gx % 10 == 0 else (120, 120, 0), 1)
    if gx % 10 == 0:
        cv2.putText(o, '%d' % gx, (u + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1)
for gy in np.arange(math.ceil(y0 / 5) * 5, y1, 5):
    v = int((y1 - gy) / res)
    cv2.line(o, (0, v), (o.shape[1], v), (255, 0, 255) if gy % 10 == 0 else (120, 0, 120), 1)
    if gy % 10 == 0:
        cv2.putText(o, '%d' % gy, (2, v - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1)
cv2.imwrite(out, o)
print(out, o.shape)
