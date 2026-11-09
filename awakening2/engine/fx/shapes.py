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
    p = blob(g, n=int(g.integers(9, 12)), rmin=0.85, rmax=1.0, smooth=2, stretch=g.uniform(1.15, 1.5))
    return [(p, 'main')]


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
    """Root fragment: curved tapered stroke, sometimes with a side rootlet."""
    c = _curve(g, n=9, length=g.uniform(2.6, 3.6), bend=0.7)
    w = np.linspace(g.uniform(0.45, 0.6), g.uniform(0.08, 0.14), len(c))
    parts = [(stroke_poly(c, w), 'main')]
    if g.random() < 0.6:
        k = int(g.integers(2, 5))
        d = np.array([g.uniform(-0.2, 0.3), g.choice([-1, 1]) * g.uniform(0.7, 1.1)])
        b = np.stack([c[k] + d * s for s in np.linspace(0, 1, 5)], 0)
        b[:, 0] += np.linspace(0, 0.3, 5) ** 2
        parts.append((stroke_poly(b, np.linspace(w[k] * 0.55, 0.05, 5)), 'main'))
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
    """Bark chip: elongated, jagged ends, two grain lines."""
    L = g.uniform(1.6, 2.2)
    Wd = g.uniform(0.45, 0.65)
    top = np.stack([np.linspace(-L, L, 6), -Wd + g.uniform(-0.08, 0.08, 6)], 1)
    bot = np.stack([np.linspace(L, -L, 6), Wd + g.uniform(-0.08, 0.08, 6)], 1)
    endr = np.array([[L + g.uniform(0.05, 0.3), g.uniform(-0.3, 0.3)]])
    endl = np.array([[-L - g.uniform(0.05, 0.3), g.uniform(-0.3, 0.3)]])
    p = np.concatenate([top, endr, bot, endl], 0)
    parts = [(p, 'main')]
    for yy in (-0.15, 0.2):
        ln = np.stack([np.linspace(-L * 0.75, L * 0.7, 6), yy + g.uniform(-0.05, 0.05, 6)], 1)
        parts.append((stroke_poly(ln, np.full(6, 0.09)), 'grain'))
    return parts


KINDS = {'clod': clod, 'crumb': crumb, 'pebble': pebble, 'moss': moss_chunk, 'root': root,
         'vine': vine, 'bark': bark}


# --------------------------------------------------------------------------- leaves
def leaf_outline(kind, g, n=24):
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
        wd = wd * (1 + 0.12 * (np.arange(n) % 2) * (np.sin(t) > 0.25))
    else:
        wd = np.sin(t) * 0.45
    wd = wd * g.uniform(0.9, 1.1)
    top = np.stack([x, -wd], 1)
    bot = np.stack([x[::-1], wd[::-1]], 1)
    p = np.concatenate([top, bot[1:-1]], 0)
    return p


def maple_outline(g, n_lobes=5):
    """Palmate (maple-like) leaf, tip at +x."""
    pts = []
    lobes = np.array([-0.95, -0.5, 0.0, 0.5, 0.95])[:n_lobes] * 1.35
    lens = np.array([0.55, 0.85, 1.0, 0.85, 0.55])[:n_lobes]
    for k, (a, L) in enumerate(zip(lobes, lens)):
        ca, sa = math.cos(a), math.sin(a)
        # notch between lobes
        if k > 0:
            am = 0.5 * (a + lobes[k - 1])
            pts.append((math.cos(am) * 0.35, math.sin(am) * 0.35))
        side = 0.16 * L
        pts.append((ca * L * 0.55 - sa * side, sa * L * 0.55 + ca * side))
        pts.append((ca * L, sa * L))
        pts.append((ca * L * 0.55 + sa * side, sa * L * 0.55 - ca * side))
    pts.append((-0.25, 0.12))
    pts.append((-0.25, -0.12))
    p = np.array(pts)
    p[:, 0] -= 0.3
    return p * g.uniform(0.9, 1.05)


LEAF_KINDS = ('ovate', 'lance', 'round', 'serrate', 'maple')


def leaf(kind, g):
    if kind == 'maple':
        p = maple_outline(g)
        lo, hi = p[:, 0].min(), p[:, 0].max()
        p = (p - np.array([(lo + hi) / 2, 0])) * (2.0 / (hi - lo))
        return p
    return leaf_outline(kind, g)
