# Return an orthorectified RGB array of the aerial photo on plane z=Zg, plus a validity mask.
import json, sys
import numpy as np
from PIL import Image
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calib
from xyp import S, font as _xyfont
_P = json.load(open(S + '/cal/aerial_p.json'))['p']
_IMG = None
def cam():
    return _P
def project(X, Y, Z):
    cx, cy, cz, yaw, pitch, roll, f = _P
    fwd, right, up = calib.rot(yaw, pitch, roll)
    W, H = 1400, 644
    fpx = f / 36.0 * W
    d = np.stack([np.asarray(X) - cx, np.asarray(Y) - cy, np.asarray(Z) - cz], axis=-1)
    z = d @ fwd; xr = d @ right; yr = d @ up
    u = W / 2 + fpx * xr / z; v = H / 2 - fpx * yr / z
    return u / 0.32044, (v + 71.556) / 0.32044, z
def image():
    global _IMG
    if _IMG is None:
        _IMG = np.asarray(Image.open(S + '/ref/xingyuan-images/杏园介绍-01_10.jpg').convert('RGB')).astype(np.float32)
    return _IMG
def ortho(Zg, x0, x1, y0, y1, res):
    img = image()
    Hf, Wf = img.shape[:2]
    nx = int(round((x1 - x0) / res)); ny = int(round((y1 - y0) / res))
    X = x0 + (np.arange(nx) + 0.5) * res
    Y = y1 - (np.arange(ny) + 0.5) * res
    XX, YY = np.meshgrid(X, Y)
    ZZ = np.full_like(XX, Zg) if np.isscalar(Zg) else Zg
    xf, yf, z = project(XX, YY, ZZ)
    valid = (z > 0) & (xf >= 0) & (xf < Wf - 1) & (yf >= 218) & (yf < 2231)
    x0i = np.clip(np.floor(xf).astype(int), 0, Wf - 2); y0i = np.clip(np.floor(yf).astype(int), 0, Hf - 2)
    fx = (xf - x0i)[..., None]; fy = (yf - y0i)[..., None]
    c = (img[y0i, x0i] * (1 - fx) * (1 - fy) + img[y0i, x0i + 1] * fx * (1 - fy) + img[y0i + 1, x0i] * (1 - fx) * fy
         + img[y0i + 1, x0i + 1] * fx * fy)
    return c, valid, XX, YY
