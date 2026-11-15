"""Site design around the cafe, as data + height functions (pure numpy: used by the terrain mesh builder outside
Blender and by the wall / paving / scatter builders inside it).

Local frame of the building: u along its short axis (towards the track, ENE), v along its long axis (NNW);
world = R(24.9527 deg) local. Heights are relative to the cafe slab top (z = 0).
"""
import math
import numpy as np

ROT = math.radians(24.952690821219857)
_C, _S = math.cos(ROT), math.sin(ROT)

Z_T = 0.0            # terrace paving level = top of the building's own base slab
PARAPET = 0.42       # dry-stone parapet above the terrace
WALL_T = 0.55        # wall thickness

# building (as modelled, never changed): shell u -6.90..3.30, v -9.54..9.66; base slab u -5.0..8.1, v -8.39..8.66
SHELL = (-6.901, -9.543, 3.298, 9.658)
SLAB = (-5.0, -8.39, 8.1, 8.66)
DOOR_V = (1.71, 3.21)          # door / boardwalk on the east wall


def to_world(u, v):
    return u * _C - v * _S, u * _S + v * _C


def to_local(x, y):
    return x * _C + y * _S, -x * _S + y * _C


def chaikin(pts, n=2, closed=True):
    p = np.asarray(pts, float)
    for _ in range(n):
        q = np.roll(p, -1, 0) if closed else p[1:]
        a = p if closed else p[:-1]
        new = np.empty((len(a) * 2, 2))
        new[0::2] = 0.75 * a + 0.25 * q
        new[1::2] = 0.25 * a + 0.75 * q
        p = new if closed else np.vstack([p[:1], new, p[-1:]])
    return p


# hard ground: the slab apron on the east, the seating terrace north of the gable, a narrow strip round the south gable
_TERRACE_CTRL = [
    (8.1, -9.6), (8.1, 8.9), (8.5, 12.6), (8.3, 16.3), (6.6, 18.9), (2.6, 19.9), (-2.2, 19.7), (-6.0, 18.5),
    (-8.4, 16.0), (-8.9, 12.7), (-8.2, 10.6), (-6.95, 9.9), (-6.95, 9.0), (-5.6, 8.9), (-5.6, -8.9), (-5.2, -10.6),
    (-2.5, -11.2), (3.6, -11.2), (7.2, -10.7),
]
TERRACE = chaikin(_TERRACE_CTRL, 2)

# gravel track (centre line, local), following the road of the master plan past the east side of the cafe
TRACK = np.array([(16.4, -110.0), (15.0, -74.0), (12.6, -58.0), (11.4, -45.0), (11.6, -30.0), (11.6, -18.0), (11.5, -8.0),
                  (11.4, 0.0), (11.5, 6.0), (12.0, 11.0), (13.6, 15.5), (16.6, 19.3), (21.5, 22.6), (29.0, 25.0),
                  (38.0, 27.0), (57.0, 30.0), (75.0, 42.0), (110.0, 75.0)])
TRACK_W = 3.9
# level of the track along its centre line: (v-ish station index, z); between, the smoothed natural ground is used
TRACK_PIN = {5: 0.52, 6: 0.50, 7: 0.47, 8: 0.45, 9: 0.30, 10: -0.05}


def polyline_resample(p, step):
    p = np.asarray(p, float)
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.r_[0, np.cumsum(seg)]
    t = np.arange(0, s[-1], step)
    return np.c_[np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], t


def smooth_polyline(p, step=0.5, sigma=3.0):
    q, t = polyline_resample(p, step)
    k = int(sigma / step * 3)
    w = np.exp(-0.5 * (np.arange(-k, k + 1) * step / sigma) ** 2)
    w /= w.sum()
    pad = np.vstack([np.repeat(q[:1], k, 0), q, np.repeat(q[-1:], k, 0)])
    return np.c_[np.convolve(pad[:, 0], w, 'valid'), np.convolve(pad[:, 1], w, 'valid')]


def seg_dist(px, py, a, b):
    """Distance from points to segments a[i]->b[i]; returns (dist, index of nearest segment, t along it)."""
    best = np.full(px.shape, 1e9)
    bi = np.zeros(px.shape, np.int32)
    bt = np.zeros(px.shape)
    for i in range(len(a)):
        ax, ay = a[i]
        dx, dy = b[i][0] - ax, b[i][1] - ay
        L2 = dx * dx + dy * dy
        t = np.clip(((px - ax) * dx + (py - ay) * dy) / max(L2, 1e-12), 0, 1)
        d = np.hypot(px - (ax + t * dx), py - (ay + t * dy))
        m = d < best
        best = np.where(m, d, best)
        bi = np.where(m, i, bi)
        bt = np.where(m, t, bt)
    return best, bi, bt


def in_poly(px, py, poly):
    inside = np.zeros(px.shape, bool)
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        c = ((y0 > py) != (y1 > py)) & (px < (x1 - x0) * (py - y0) / (y1 - y0 + 1e-30) + x0)
        inside ^= c
    return inside


def terrace_sdf(u, v):
    """Signed distance to the terrace outline (negative inside), local coordinates."""
    d, _, _ = seg_dist(u, v, TERRACE, np.roll(TERRACE, -1, 0))
    return np.where(in_poly(u, v, TERRACE), -d, d)


class Site:
    """Graded ground. nat(x, y) -> natural height (world coordinates, vectorised)."""

    def __init__(self, nat):
        self.nat = nat
        self.track = smooth_polyline(TRACK, 0.5, 2.5)
        tu, tv = self.track[:, 0], self.track[:, 1]
        x, y = to_world(tu, tv)
        zn = nat(x, y)
        # pinned levels near the boardwalk; elsewhere the natural ground smoothed along the track
        k = 24
        w = np.hanning(2 * k + 1)
        w /= w.sum()
        zs = np.convolve(np.r_[np.repeat(zn[:1], k), zn, np.repeat(zn[-1:], k)], w, 'valid')
        ctrl = smooth_polyline(TRACK, 0.5, 2.5)
        # station of each control point of TRACK along the resampled line
        pin_s, pin_z = [], []
        for i, z in TRACK_PIN.items():
            j = int(np.argmin(np.hypot(tu - TRACK[i][0], tv - TRACK[i][1])))
            pin_s.append(j)
            pin_z.append(z)
        pin_s = np.array(pin_s)
        pin_z = np.array(pin_z)
        idx = np.arange(len(tu))
        zp = np.interp(idx, pin_s, pin_z)
        wpin = np.clip(1.0 - np.maximum(pin_s.min() - idx, idx - pin_s.max()) / 60.0, 0, 1)   # fades over 30 m
        wpin = wpin * wpin * (3 - 2 * wpin)
        self.track_z = zs * (1 - wpin) + zp * wpin

    def track_field(self, u, v):
        """(distance to the centre line, track level there) for local points near the site."""
        a = self.track[:-1]
        b = self.track[1:]
        best = np.full(u.shape, 1e9)
        zt = np.zeros(u.shape)
        # coarse-to-fine: chunks of the line
        for s in range(0, len(a), 40):
            aa, bb = a[s:s + 40], b[s:s + 40]
            lo = np.minimum(aa.min(0), bb.min(0)) - 12
            hi = np.maximum(aa.max(0), bb.max(0)) + 12
            m = (u > lo[0]) & (u < hi[0]) & (v > lo[1]) & (v < hi[1])
            if not m.any():
                continue
            d, i, t = seg_dist(u[m], v[m], aa, bb)
            z = self.track_z[s + i] * (1 - t) + self.track_z[np.minimum(s + i + 1, len(self.track_z) - 1)] * t
            upd = d < best[m]
            bm = best[m]
            zm = zt[m]
            bm[upd] = d[upd]
            zm[upd] = z[upd]
            best[m] = bm
            zt[m] = zm
        return best, zt

    def height(self, x, y):
        """Ground height and masks at world points: returns (z, m_track, m_terrace, sdf_terrace)."""
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        z = np.asarray(self.nat(x, y), float).copy()
        u, v = to_local(x, y)
        near = (np.abs(u) < 150) & (np.abs(v) < 150)
        m_track = np.zeros(z.shape, np.float32)
        m_terr = np.zeros(z.shape, np.float32)
        sdf = np.full(z.shape, 99.0, np.float32)
        if not near.any():
            return z, m_track, m_terr, sdf
        un, vn, zn = u[near], v[near], z[near]
        d = terrace_sdf(un, vn)
        sdf[near] = np.clip(d, -99, 99)
        # 1. the knoll: ground meets the wall foot 0.85 m below the terrace and eases into the natural slope
        L = 26.0
        w = np.clip(d / L, 0, 1)
        w = w * w * (3 - 2 * w)
        z_edge = Z_T - 0.85 + 0.25 * np.sin(un * 0.31) * np.cos(vn * 0.27)
        z1 = z_edge * (1 - w) + zn * w
        # 2. the track
        dc, zt = self.track_field(un, vn)
        half = TRACK_W / 2
        wt = 1.0 - np.clip((dc - half) / 3.2, 0, 1)
        wt = wt * wt * (3 - 2 * wt)
        crown = 0.05 * np.clip(1 - (dc / half) ** 2, 0, 1)          # slight crown of a worn gravel track
        z2 = z1 * (1 - wt) + (zt + crown) * wt
        # 3. under the paving and the slab
        z2 = np.where(d < 0, Z_T - 0.30, z2)
        z[near] = z2
        m_track[near] = np.clip(1.0 - (dc - half + 0.25) / 0.5, 0, 1) * (d > 0.2)
        m_terr[near] = (d < 0)
        return z, m_track, m_terr, sdf
