"""The composed landscape: the real ground around the cafe out to 3 km, the real Yading massif (moved closer, see
below) beyond 6 km, and a smooth blend of the two in between. One continuous height field in the scene frame.

Far transform: real point p -> scene point q = R(delta) (p - P_REAL) + p_t, p_t = D (cos az_t, sin az_t),
delta = az_t - azimuth(P_REAL): the massif keeps the aspect it has from the real Manachajin, 30 km away, but stands
D metres from the cafe at azimuth az_t.
"""
import os, sys, math, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_lib as tl
from far_build import OUT

P_REAL = (-22470.0, -5360.0)          # Chanadorje (5958 m) in the real scene frame
CAM = (9.6, 32.79, 11.76)             # sketch camera; centre of the polar grid and of the blend
CAM_VIEW = (15.0, 41.0, 13.5)         # the picture's camera (lib/mc_light.CAMERA): used for visibility tests
LAYOUT = dict(az_t=-146.5, D=10800.0, dz=0.0, blend=(3000.0, 6000.0), seam=2500.0)
KEYS = ('slope', 'north', 'curv', 'flow', 'rocky')


def catmull(a, r, c):
    """Bicubic (Catmull-Rom) sample of a[r, c] at float indices; clamps at the border."""
    r0 = np.floor(r).astype(np.int64)
    c0 = np.floor(c).astype(np.int64)
    fr = (r - r0).astype(np.float32)
    fc = (c - c0).astype(np.float32)

    def w(t):
        t2 = t * t
        t3 = t2 * t
        return (-0.5 * t3 + t2 - 0.5 * t, 1.5 * t3 - 2.5 * t2 + 1.0, -1.5 * t3 + 2.0 * t2 + 0.5 * t, 0.5 * t3 - 0.5 * t2)
    wr = w(fr)
    wc = w(fc)
    out = np.zeros(r.shape, np.float32)
    H, W = a.shape
    for i in range(4):
        rr = np.clip(r0 - 1 + i, 0, H - 1)
        row = np.zeros(r.shape, np.float32)
        for j in range(4):
            cc = np.clip(c0 - 1 + j, 0, W - 1)
            row += a[rr, cc] * wc[j]
        out += row * wr[i]
    return out


def bilin(a, r, c):
    H, W = a.shape
    r = np.clip(r, 0, H - 1.001)
    c = np.clip(c, 0, W - 1.001)
    r0 = r.astype(np.int64)
    c0 = c.astype(np.int64)
    fr = (r - r0).astype(np.float32)
    fc = (c - c0).astype(np.float32)
    return (a[r0, c0] * (1 - fr) * (1 - fc) + a[r0 + 1, c0] * fr * (1 - fc) + a[r0, c0 + 1] * (1 - fr) * fc +
            a[r0 + 1, c0 + 1] * fr * fc).astype(np.float32)


class Raster:
    def __init__(self, name):
        self.h = np.load(os.path.join(OUT, name + '_h.npy'))
        m = np.load(os.path.join(OUT, name + '_masks.npz'))
        self.x0, self.y0, self.cell, self.nx, self.ny = m['box']
        self.m = {k: m[k].astype(np.float32) for k in ('slope', 'nx', 'ny', 'curv', 'flow', 'rocky')}

    def rc(self, x, y):
        return (y - self.y0) / self.cell, (x - self.x0) / self.cell

    def inside(self, x, y, margin):
        r, c = self.rc(x, y)
        d = np.minimum(np.minimum(r, self.ny - 1 - r), np.minimum(c, self.nx - 1 - c)) * self.cell
        return np.clip(d / margin, 0.0, 1.0)

    def sample(self, x, y):
        r, c = self.rc(x, y)
        out = {k: bilin(self.m[k], r, c) for k in self.m}
        out['z'] = catmull(self.h, r, c)
        return out


class Composite:
    def __init__(self, layout=None, need=('near', 'far')):
        self.L = dict(LAYOUT)
        self.L.update(layout or {})
        self.near = Raster('near') if 'near' in need else None
        self.hi = Raster('far_hi') if 'far' in need else None
        self.lo = Raster('far_lo') if 'far' in need else None
        az_r = math.atan2(P_REAL[1], P_REAL[0])
        self.delta = math.radians(self.L['az_t']) - az_r
        self.cd, self.sd = math.cos(self.delta), math.sin(self.delta)
        a = math.radians(self.L['az_t'])
        self.pt = (self.L['D'] * math.cos(a), self.L['D'] * math.sin(a))

    def info(self):
        return dict(self.L, delta_deg=math.degrees(self.delta), pt=self.pt, cam=CAM, p_real=P_REAL)

    def far(self, qx, qy):
        ux = qx - self.pt[0]
        uy = qy - self.pt[1]
        px = self.cd * ux + self.sd * uy + P_REAL[0]
        py = -self.sd * ux + self.cd * uy + P_REAL[1]
        w = self.hi.inside(px, py, 400.0)
        w = w * w * (3 - 2 * w)
        a = self.lo.sample(px, py)
        b = self.hi.sample(px, py)
        o = {k: a[k] * (1 - w) + b[k] * w for k in a}
        o['north'] = self.sd * o['nx'] + self.cd * o['ny']      # scene-north component of the normal
        o['z'] = o['z'] + self.L['dz']
        return o

    def sample(self, qx, qy):
        """Scene points -> dict z, slope, north, curv, flow, rocky, wfar (0 = real near ground, 1 = massif layer)."""
        qx = np.asarray(qx, np.float64)
        qy = np.asarray(qy, np.float64)
        r = np.hypot(qx - CAM[0], qy - CAM[1])
        ra, rb = self.L['blend']
        w = np.clip((r - ra) / (rb - ra), 0, 1)
        w = (w * w * (3 - 2 * w)).astype(np.float32)
        out = {k: np.zeros(qx.shape, np.float32) for k in KEYS + ('z',)}
        mn = w < 1
        mf = w > 0
        if mn.any():
            a = self.near.sample(qx[mn], qy[mn])
            a['north'] = a['ny']
            for k in out:
                out[k][mn] += a[k] * (1 - w[mn])
        if mf.any():
            b = self.far(qx[mf], qy[mf])
            for k in out:
                out[k][mf] += b[k] * w[mf]
        out['wfar'] = w
        return out
