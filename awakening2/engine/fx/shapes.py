"""shapes.py - designed silhouettes for debris and leaves (unit-size local polygons).

Every generator takes a numpy Generator and returns polygons in local units (about
-1..1), drawn by `PolyBatch` after rotate / scale / translate.  Debris pieces return a
list of parts: (polygon, role) where role picks the colour set ('main', 'cap', 'grain').
"""
import math

import numpy as np

from .core import chaikin, stroke_poly

TAU = 2 * math.pi


def blob(g, n=9, rmin=0.62, rmax=1.0, smooth=1, stretch=1.0):
    a = np.sort(g.uniform(0, TAU, n))
    a = (np.arange(n) + g.uniform(-0.3, 0.3, n)) * (TAU / n)
    r = g.uniform(rmin, rmax, n)
    p = np.stack([np.cos(a) * r * stretch, np.sin(a) * r], 1)
    if smooth:
        p = chaikin(p, smooth, closed=True)
    return p


def clod(g):
    """Soil clod: lumpy, partly angular."""
    p = blob(g, n=int(g.integers(7, 10)), rmin=0.6, rmax=1.0, smooth=1, stretch=g.uniform(1.0, 1.35))
    return [(p, 'main')]


def crumb(g):
    p = blob(g, n=int(g.integers(5, 7)), rmin=0.55, rmax=1.0, smooth=0, stretch=g.uniform(1.0, 1.5))
    return [(p, 'main')]


def pebble(g):
    """Pebble: an irregular flat-faceted stone - 5-8 straight sides, a little longer than high.
    (The hard light/shadow split is cut at draw time, see debris.add_piece.)"""
    n = int(g.integers(5, 9))
    a = (np.arange(n) + g.uniform(-0.28, 0.28, n)) * (TAU / n) + g.uniform(0, TAU)
    r = g.uniform(0.78, 1.0, n)
    p = np.stack([np.cos(a) * r * g.uniform(1.1, 1.45), np.sin(a) * r * g.uniform(0.78, 0.95)], 1)
    return [(p, 'main')]


def mossy_pebble(g):
    """A faceted stone with a small moss cushion on one face."""
    parts = pebble(g)
    p = parts[0][0]
    top = p[np.argsort(p[:, 1])[:3]]                     # the three highest corners
    c = top.mean(0) * 0.55
    ang = np.linspace(math.pi * 1.05, math.pi * 1.95, 7)
    w = g.uniform(0.45, 0.7)
    cap = np.concatenate([np.stack([c[0] + np.cos(ang) * w, c[1] + np.sin(ang) * w * 0.55], 1),
                          [[c[0] + w * 0.9, c[1] + 0.12], [c[0] - w * 0.9, c[1] + 0.12]]], 0)
    parts.append((chaikin(cap, 1, closed=True), 'cap'))
    return parts


def moss_chunk(g):
    """Soil underside with a lumpy moss cap on top (local up = -y)."""
    soil = blob(g, n=8, rmin=0.65, rmax=0.95, smooth=1, stretch=1.2)
    soil[:, 1] = soil[:, 1] * 0.8 + 0.2
    nb = int(g.integers(2, 4))
    ang = np.linspace(math.pi * 1.02, math.pi * 1.98, 9)
    cap = []
    xs = np.sort(g.uniform(-0.8, 0.8, nb))
    for k in range(nb):
        rr = g.uniform(0.38, 0.55)
        cap.append(np.stack([xs[k] + np.cos(ang) * rr, -0.15 + np.sin(ang) * rr * g.uniform(0.8, 1.1)], 1))
    cap = np.concatenate(cap, 0)
    cap = cap[np.argsort(cap[:, 0])]
    cap = np.concatenate([[[-1.15, 0.1]], cap, [[1.15, 0.1], [0.5, 0.32], [-0.5, 0.3]]], 0)
    return [(soil, 'main'), (chaikin(cap, 1, closed=True), 'cap')]


def _curve(g, n=7, length=2.6, bend=0.6):
    t = np.linspace(-0.5, 0.5, n) * length
    k1, k2 = g.uniform(-bend, bend, 2)
    y = k1 * (t / length * 2) ** 2 + k2 * np.sin(t / length * math.pi * 1.5) * 0.4
    return np.stack([t, y], 1)


def root(g):
    """Root fragment: thin, S-curved, tapered at both ends, with a rootlet or two."""
    L = g.uniform(2.2, 3.2)
    t = np.linspace(-0.5, 0.5, 11) * L
    k1, k2 = g.uniform(-0.5, 0.5, 2)
    y = k1 * np.sin(t / L * math.pi * 1.6) * 0.5 + k2 * (t / L) ** 2 * 1.2
    c = np.stack([t, y], 1)
    q = np.linspace(0, 1, len(c))
    w = g.uniform(0.26, 0.36) * np.sin(np.clip(q * 1.05, 0, 1) * math.pi) ** 0.7 * (1.1 - 0.5 * q) + 0.02
    parts = [(stroke_poly(c, w), 'main')]
    for _ in range(int(g.integers(1, 3))):
        kk = int(g.integers(3, 8))
        d = np.array([g.uniform(-0.1, 0.4), g.choice([-1, 1]) * g.uniform(0.5, 0.9)])
        bb = np.stack([c[kk] + d * s_ for s_ in np.linspace(0, 1, 5)], 0)
        bb[:, 0] += np.linspace(0, 0.25, 5) ** 2
        parts.append((stroke_poly(bb, np.linspace(w[kk] * 0.5, 0.02, 5)), 'main'))
    return parts


def vine(g):
    """Vine fragment: thin green stroke with one or two small leaves."""
    c = _curve(g, n=9, length=g.uniform(2.8, 3.8), bend=0.9)
    w = np.linspace(0.22, 0.12, len(c))
    parts = [(stroke_poly(c, w), 'main')]
    for k in g.choice(np.arange(2, len(c) - 1), size=int(g.integers(1, 3)), replace=False):
        side = g.choice([-1, 1])
        lf = leaf_outline('ovate', g, n=12) * np.array([0.55, 0.32])
        ang = side * g.uniform(0.6, 1.2)
        ca, sa = math.cos(ang), math.sin(ang)
        lf = lf + np.array([0.55, 0])
        lf = np.stack([lf[:, 0] * ca - lf[:, 1] * sa, lf[:, 0] * sa + lf[:, 1] * ca], 1) + c[k]
        parts.append((lf, 'cap'))
    return parts


def bark(g):
    """Bark: a curled, irregular sliver tapered at both ends, with one grain line."""
    L = g.uniform(1.4, 2.0)
    t = np.linspace(-1, 1, 12)
    bend = g.uniform(0.25, 0.55) * g.choice([-1, 1])
    mid = np.stack([t * L * 0.5, bend * (t ** 2 - 0.4)], 1)
    q = (t + 1) / 2
    w = g.uniform(0.32, 0.46) * np.sin(q * math.pi) ** 0.8 * (1 + 0.25 * np.sin(q * 7 + g.uniform(0, 6)))
    n = np.stack([-np.gradient(mid[:, 1]), np.gradient(mid[:, 0])], 1)
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
    jag = g.uniform(-0.05, 0.05, (len(t), 2))
    top = mid + n * (w[:, None] * 0.5) + jag[:, :1] * n
    bot = mid - n * (w[:, None] * 0.5) * g.uniform(0.6, 1.0) + jag[:, 1:] * n
    p = np.concatenate([top, bot[::-1]], 0)
    ln = mid[2:-2] + n[2:-2] * 0.04
    return [(p, 'main'), (stroke_poly(ln, np.full(len(ln), 0.06)), 'grain')]


KINDS = {'clod': clod, 'crumb': crumb, 'pebble': pebble, 'mossy_pebble': mossy_pebble, 'moss': moss_chunk, 'root': root,
         'vine': vine, 'bark': bark}


# --------------------------------------------------------------------------- leaves
def leaf_outline(kind, g, n=24):
    if kind in ('serrate', 'lobed', 'birch'):
        n = 40
    """Leaf outline, tip at +x, stem end at -x, length 2 (x in -1..1)."""
    t = np.linspace(0, math.pi, n)
    x = -np.cos(t)
    if kind == 'ovate':
        wd = np.sin(t) ** 0.9 * (1 - 0.25 * x) * 0.48
    elif kind == 'lance':
        wd = np.sin(t) ** 1.1 * (1 - 0.15 * x) * 0.27
    elif kind == 'round':
        wd = np.sin(t) ** 0.7 * 0.6
    elif kind == 'serrate':
        wd = np.sin(t) ** 0.9 * (1 - 0.2 * x) * 0.45
        wd = wd * (1 + 0.2 * (np.arange(n) % 2) * (np.sin(t) > 0.2))
    elif kind == 'willow':
        wd = np.sin(t) ** 1.3 * (1 - 0.3 * x) * 0.17
    elif kind == 'birch':
        wd = np.sin(t) ** 0.75 * (1 - 0.35 * x) * 0.62
        wd = wd * (1 + 0.1 * (np.arange(n) % 2) * (np.sin(t) > 0.3))
    elif kind == 'heart':
        wd = np.sin(t) ** 0.6 * (1 - 0.45 * x) * 0.55 + 0.12 * np.exp(-((x + 0.85) / 0.12) ** 2)
    elif kind == 'lobed':
        wd = np.sin(t) ** 0.8 * (1 - 0.15 * x) * 0.46
        wd = wd * (0.74 + 0.26 * np.abs(np.sin((x + 1) * math.pi * 2.6)))
    else:
        wd = np.sin(t) * 0.45
    wd = wd * g.uniform(0.9, 1.1)
    top = np.stack([x, -wd], 1)
    bot = np.stack([x[::-1], wd[::-1]], 1)
    p = np.concatenate([top, bot[1:-1]], 0)
    return p


def maple_outline(g, n_lobes=5):
    """Palmate (maple-like) leaf from a polar profile: 5 pointed lobes, toothed, tip at +x."""
    th = np.linspace(-math.pi, math.pi, 120, endpoint=False)
    lobes = [(0.0, 1.0), (0.95, 0.82), (-0.95, 0.82), (1.85, 0.55), (-1.85, 0.55)][:n_lobes]
    r = np.full_like(th, 0.3)
    for ang, L in lobes:
        dlt = np.abs((th - ang + math.pi) % (2 * math.pi) - math.pi)
        r = np.maximum(r, 0.3 + (L - 0.3) * np.clip(1 - dlt / 0.42, 0, 1) ** 1.5)
    r = r * (1 + 0.06 * np.abs(np.sin(th * 13))) * g.uniform(0.95, 1.05)
    p = np.stack([np.cos(th) * r, np.sin(th) * r], 1)
    return p


LEAF_KINDS = ('ovate', 'lance', 'round', 'serrate', 'maple', 'willow', 'birch', 'heart', 'lobed')


def leaf(kind, g):
    if kind == 'maple':
        p = maple_outline(g)
        lo, hi = p[:, 0].min(), p[:, 0].max()
        p = (p - np.array([(lo + hi) / 2, 0])) * (2.0 / (hi - lo))
        return p
    return leaf_outline(kind, g)
