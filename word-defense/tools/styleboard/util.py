# util.py - placement helpers shared by the scenes: ribbons on the floor, SDF cards, glows, arcs.
import math
import numpy as np
from eng import h2c, c2h, mix, mul, path_d, fmt
from geo2d import catmull, shape_loops, fbm, vnoise


def smooth(pts, n=10):
    return np.array(catmull([tuple(p) for p in pts], n))


def arclen(P):
    d = np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))
    return np.concatenate([[0.0], np.cumsum(d)])


def at(P, s):
    """Point and unit tangent at fraction s along polyline P."""
    L = arclen(P)
    t = s * L[-1]
    i = int(np.clip(np.searchsorted(L, t) - 1, 0, len(P) - 2))
    f = (t - L[i]) / max(1e-9, L[i + 1] - L[i])
    p = P[i] + (P[i + 1] - P[i]) * f
    d = P[i + 1] - P[i]
    d = d / (np.linalg.norm(d) + 1e-12)
    return p, d


def ribbon(P, width, seed=0, wobble=0.0, wf=1.5):
    """Closed outline (x, y) of a band of the given width (scalar or per-point array) around centreline P."""
    P = np.asarray(P, float)
    w = np.broadcast_to(np.asarray(width, float), (len(P),)).copy()
    T = np.gradient(P, axis=0)
    T /= (np.linalg.norm(T, axis=1, keepdims=True) + 1e-12)
    N = np.stack([-T[:, 1], T[:, 0]], 1)
    s = arclen(P)
    if wobble:
        w = w * (1 + wobble * fbm(s * wf, np.full(len(s), 0.5 + seed), seed, 3))
    L = P + N * (w[:, None] / 2)
    R = P - N * (w[:, None] / 2)
    if wobble:
        L = L + N * (wobble * 0.3 * w[:, None] * fbm(s * wf * 2.3, np.full(len(s), 3.1 + seed), seed + 1, 2)[:, None])
        R = R - N * (wobble * 0.3 * w[:, None] * fbm(s * wf * 2.1, np.full(len(s), 7.7 + seed), seed + 2, 2)[:, None])
    return np.concatenate([L, R[::-1]])


def offset_line(P, d):
    P = np.asarray(P, float)
    T = np.gradient(P, axis=0)
    T /= (np.linalg.norm(T, axis=1, keepdims=True) + 1e-12)
    N = np.stack([-T[:, 1], T[:, 0]], 1)
    return P + N * d


def dist_to_poly(px, py, P):
    """Distance from point to polyline P."""
    P = np.asarray(P)
    A = P[:-1]
    B = P[1:]
    AB = B - A
    AP = np.array([px, py]) - A
    t = np.clip((AP * AB).sum(1) / ((AB * AB).sum(1) + 1e-12), 0, 1)
    C = A + AB * t[:, None]
    return float(np.min(np.hypot(C[:, 0] - px, C[:, 1] - py)))


def sdf_card(cv, fn, bounds, origin, fill, step=0.012, rot=0.0, depth=None, cast=True, flip=False, scale=1.0, band=None, **kw):
    """Trace an SDF silhouette and stand it up as a card at origin (x, y, z)."""
    loops = shape_loops(fn, bounds, step)
    if not loops:
        return None
    if flip or scale != 1.0:
        loops = [[((-u if flip else u) * scale, v * scale) for u, v in lp] for lp in loops]
    it, L3 = cv.card(loops, origin, fill, rot=rot, depth=depth, cast=cast, band=band, **kw)
    return it


def sdf_loops3(cv, fn, bounds, origin, step=0.012, rot=0.0, flip=False, scale=1.0):
    loops = shape_loops(fn, bounds, step)
    if flip or scale != 1.0:
        loops = [[((-u if flip else u) * scale, v * scale) for u, v in lp] for lp in loops]
    return cv.card_loops3(loops, origin, rot)


def glow(cv, P, r_world, col, op=0.8, layer='fx', squash=1.0, core=None):
    if cv.cam.depth(np.asarray(P, float)) < 0.3:
        return
    c = cv.cam.p(np.asarray(P, float))
    r = r_world * cv.cam.scale(np.asarray(P, float))
    g = cv.radgrad(c, (r, r * squash), [(0, col, op), (0.35, col, op * 0.45), (1, col, 0.0)])
    cv.add(layer, '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="%s" style="mix-blend-mode:screen"/>'
           % (fmt(c[0]), fmt(c[1]), fmt(r), fmt(r * squash), g))
    if core:
        cv.add(layer, '<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (fmt(c[0]), fmt(c[1]), fmt(max(0.6, r * 0.12)), core))


def arc3(a, b, h, n=40):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    t = np.linspace(0, 1, n)[:, None]
    P = a + (b - a) * t
    P[:, 2] += 4 * h * t[:, 0] * (1 - t[:, 0])
    return P


def scatter_points(rng, n, box, avoid=(), min_d=0.0, tries=4000):
    x0, y0, x1, y1 = box
    out = []
    k = 0
    while len(out) < n and k < tries:
        k += 1
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        ok = True
        for (P, d) in avoid:
            if callable(P):
                if not P(x, y):
                    ok = False
                    break
            elif dist_to_poly(x, y, P) < d:
                ok = False
                break
        if ok and min_d:
            for (ox, oy) in out:
                if math.hypot(ox - x, oy - y) < min_d:
                    ok = False
                    break
        if ok:
            out.append((x, y))
    return out


class Stack:
    """Layered cards of one object, drawn strictly in the order they are added (back to front)."""

    def __init__(s, cv):
        s.cv = cv
        s.d0 = None
        s.k = 0

    def card(s, fn, bounds, origin, fill, **kw):
        if s.d0 is None:
            it = sdf_card(s.cv, fn, bounds, origin, fill, **kw)
            if it is not None:
                s.d0 = it.depth
            return it
        s.k += 1
        return sdf_card(s.cv, fn, bounds, origin, fill, depth=s.d0 - 0.004 * s.k, **kw)
