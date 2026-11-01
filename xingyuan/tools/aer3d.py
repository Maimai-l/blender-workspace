# Helpers on the calibrated aerial camera: pixel (full-res) <-> world.
import json, sys, math
import numpy as np
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calib
from xyp import S, font as _xyfont
P = json.load(open(S + '/cal/aerial_p.json'))['p']
cx, cy, cz, yaw, pitch, roll, f = P
fwd, right, up = calib.rot(yaw, pitch, roll)
W, H = 1400, 644
fpx = f / 36.0 * W
K = 0.32044; OY = 71.556
def to_full(u, v):
    return u / K, (v + OY) / K
def to_ref(xf, yf):
    return xf * K, yf * K - OY
def ray(xf, yf):
    u, v = to_ref(xf, yf)
    d = fwd + right * (u - W / 2) / fpx - up * (v - H / 2) / fpx
    return np.array([cx, cy, cz]), d / np.linalg.norm(d)
def ground(xf, yf, z=-0.6):
    o, d = ray(xf, yf)
    t = (z - o[2]) / d[2]
    return o + d * t
def project(X):
    u, v = calib.project(P, X, W, H)
    return to_full(u, v)
def height_above(base_xy, top_xf, top_yf, z0=-0.6):
    best = None
    for z in np.arange(z0, z0 + 40, 0.02):
        px, py = project((base_xy[0], base_xy[1], z))
        e = math.hypot(px - top_xf, py - top_yf)
        if best is None or e < best[0]:
            best = (e, z)
    return best[1] - z0, best[0]
