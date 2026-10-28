# geo2d.py - 2D noise, signed distance fields and contour tracing (ported from pp_lib.py, no Blender)
import numpy as np

# ------------------------------------------------------------------ noise (value noise, numpy)
_GRIDS = {}


def _grid(seed):
    g = _GRIDS.get(seed)
    if g is None:
        g = np.random.default_rng(int(seed) % (2 ** 31)).random((256, 256))
        _GRIDS[seed] = g
    return g


def vnoise(x, y, seed=0):
    g = _grid(seed)
    xf0 = np.floor(x); yf0 = np.floor(y)
    xf = x - xf0; yf = y - yf0
    xi = xf0.astype(np.int64) & 255; yi = yf0.astype(np.int64) & 255
    x1 = (xi + 1) & 255; y1 = (yi + 1) & 255
    u = xf * xf * (3 - 2 * xf); v = yf * yf * (3 - 2 * yf)
    a = g[yi, xi]; b = g[yi, x1]; c = g[y1, xi]; d = g[y1, x1]
    return (a + (b - a) * u) * (1 - v) + (c + (d - c) * u) * v


def fbm(x, y, seed=0, octaves=4, lac=2.03, gain=0.5):
    s = np.zeros_like(x, dtype=float); amp = 1.0; f = 1.0; norm = 0.0
    for o in range(octaves):
        s = s + amp * (vnoise(x * f + o * 31.7, y * f - o * 17.3, seed + o) * 2 - 1)
        norm += amp; amp *= gain; f *= lac
    return s / norm


def cut_edge(F, X, Y, seed, amp=0.012, freq=9.0, fine=0.004, fine_freq=40.0):
    """Hand-cut irregularity: a slow wobble plus fine tremor along every edge."""
    return F + amp * fbm(X * freq, Y * freq, seed, 3) + fine * fbm(X * fine_freq, Y * fine_freq, seed + 50, 2)


# ------------------------------------------------------------------ 2D signed distances
def sd_circle(X, Y, cx, cy, r):
    return np.hypot(X - cx, Y - cy) - r


def sd_ellipse(X, Y, cx, cy, rx, ry):
    return (np.hypot((X - cx) / rx, (Y - cy) / ry) - 1.0) * min(rx, ry)


def sd_capsule(X, Y, ax, ay, bx, by, ra, rb=None):
    rb = ra if rb is None else rb
    pax = X - ax; pay = Y - ay; bax = bx - ax; bay = by - ay
    h = np.clip((pax * bax + pay * bay) / (bax * bax + bay * bay + 1e-12), 0, 1)
    return np.hypot(pax - bax * h, pay - bay * h) - (ra + (rb - ra) * h)


def sd_box(X, Y, cx, cy, hx, hy, r=0.0):
    qx = np.abs(X - cx) - hx + r; qy = np.abs(Y - cy) - hy + r
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def sd_poly(X, Y, pts):
    v = np.asarray(pts, float); n = len(v)
    d = (X - v[0, 0]) ** 2 + (Y - v[0, 1]) ** 2
    s = np.ones_like(X, dtype=float)
    j = n - 1
    for i in range(n):
        ex = v[j, 0] - v[i, 0]; ey = v[j, 1] - v[i, 1]
        wx = X - v[i, 0]; wy = Y - v[i, 1]
        t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey + 1e-12), 0, 1)
        bx = wx - ex * t; by = wy - ey * t
        d = np.minimum(d, bx * bx + by * by)
        c1 = Y >= v[i, 1]; c2 = Y < v[j, 1]; c3 = ex * wy > ey * wx
        s = np.where((c1 & c2 & c3) | (~c1 & ~c2 & ~c3), -s, s)
        j = i
    return s * np.sqrt(d)


def sd_polyline(X, Y, pts, r):
    d = np.full(X.shape, np.inf)
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        bax = bx - ax; bay = by - ay
        L2 = bax * bax + bay * bay
        if L2 < 1e-12:
            continue
        pax = X - ax; pay = Y - ay
        h = np.clip((pax * bax + pay * bay) / L2, 0, 1)
        d = np.minimum(d, np.hypot(pax - bax * h, pay - bay * h))
    return d - r


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def umin(*ds):
    out = ds[0]
    for d in ds[1:]:
        out = np.minimum(out, d)
    return out


def catmull(pts, n=12):
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = (np.array(P[i - 1], float), np.array(P[i], float), np.array(P[i + 1], float), np.array(P[i + 2], float))
        for k in range(n):
            t = k / n; t2 = t * t; t3 = t2 * t
            out.append(tuple(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)))
    out.append(tuple(map(float, pts[-1])))
    return out


# ------------------------------------------------------------------ marching squares
_SEG = {1: ((3, 0),), 2: ((0, 1),), 3: ((3, 1),), 4: ((1, 2),), 6: ((0, 2),), 7: ((3, 2),),
        8: ((2, 3),), 9: ((0, 2),), 11: ((1, 2),), 12: ((1, 3),), 13: ((0, 1),), 14: ((3, 0),)}


def trace(F, x0, y0, step):
    """Closed zero-contours of F (inside < 0) as lists of (x, y). F's border must be outside."""
    ny, nx = F.shape
    a = (F < 0).astype(np.int16)
    idx = a[:-1, :-1] + 2 * a[:-1, 1:] + 4 * a[1:, 1:] + 8 * a[1:, :-1]
    H = ny * nx
    adj = {}

    def key(e, i, j):
        if e == 0: return i * nx + j
        if e == 1: return H + i * nx + j + 1
        if e == 2: return (i + 1) * nx + j
        return H + i * nx + j

    for i, j in np.argwhere((idx != 0) & (idx != 15)):
        c = int(idx[i, j])
        if c in (5, 10):
            centre = (F[i, j] + F[i, j + 1] + F[i + 1, j + 1] + F[i + 1, j]) * 0.25
            if c == 5:
                segs = ((0, 1), (2, 3)) if centre < 0 else ((3, 0), (1, 2))
            else:
                segs = ((3, 0), (1, 2)) if centre < 0 else ((0, 1), (2, 3))
        else:
            segs = _SEG[c]
        for ea, eb in segs:
            ka = key(ea, i, j); kb = key(eb, i, j)
            adj.setdefault(ka, []).append(kb)
            adj.setdefault(kb, []).append(ka)

    def pos(k):
        if k < H:
            i, j = divmod(k, nx)
            f0, f1 = F[i, j], F[i, j + 1]
            t = f0 / (f0 - f1)
            return (x0 + (j + t) * step, y0 + i * step)
        i, j = divmod(k - H, nx)
        f0, f1 = F[i, j], F[i + 1, j]
        t = f0 / (f0 - f1)
        return (x0 + j * step, y0 + (i + t) * step)

    loops, seen = [], set()
    for start in adj:
        if start in seen:
            continue
        loop = [start]; seen.add(start)
        prev, cur = None, start
        while True:
            nb = adj[cur]
            nxt = nb[0] if nb[0] != prev else (nb[1] if len(nb) > 1 else None)
            if nxt is None or nxt == start or nxt in seen:
                break
            loop.append(nxt); seen.add(nxt)
            prev, cur = cur, nxt
        if len(loop) > 3:
            loops.append([pos(k) for k in loop])
    return loops


def loop_area(lp):
    P = np.asarray(lp)
    x, y = P[:, 0], P[:, 1]
    return 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def resample(lp, seg):
    P = np.asarray(list(lp) + [lp[0]], float)
    d = np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))
    L = float(d.sum())
    n = max(8, int(L / seg))
    s = np.concatenate([[0.0], np.cumsum(d)])
    t = np.linspace(0, L, n, endpoint=False)
    return list(zip(np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])))


def shape_loops(fn, bounds, step, seg=None, min_area=None):
    """Sample fn(U, V) over bounds = (u0, v0, u1, v1) and return the traced outline loops."""
    u0, v0, u1, v1 = bounds
    us = np.arange(u0 - step, u1 + 2 * step, step)
    vs = np.arange(v0 - step, v1 + 2 * step, step)
    U, V = np.meshgrid(us, vs)
    F = np.asarray(fn(U, V), float)
    F[0, :] = F[-1, :] = 1.0
    F[:, 0] = F[:, -1] = 1.0
    F = np.where(np.abs(F) < 1e-9, 1e-9, F)
    min_area = (step * step * 6) if min_area is None else min_area
    out = []
    for lp in trace(F, us[0], vs[0], step):
        if abs(loop_area(lp)) >= min_area:
            out.append(resample(lp, seg or step * 0.85))
    return out


