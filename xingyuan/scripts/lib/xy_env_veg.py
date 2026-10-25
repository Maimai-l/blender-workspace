# Xingyuan - planting of the garden: trees (per template one instancer), far tree ring, shrubs and hedge,
# bank plants, lotus, shore rocks, lawn grass. Positions come from env/make_env.py (aerial-based zones);
# heights from the terrain. Lawn grass is scattered here from the lawn weight and the fine paving mask.
import bpy, math, random, zlib
import numpy as np
from mathutils import Vector
import xy_core as C, xy_env_data as ED, xy_terrain as TR, xy_plants as P, xy_env_struct as ST

WL = ED.WL
ZP = ED.ZP

def _h(s):
    return zlib.crc32(s.encode('utf-8'))

def _clear(coll):
    for o in list(coll.objects):
        me = o.data if o.type == 'MESH' else None
        bpy.data.objects.remove(o, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)

def trees(coll, T, planters):
    """All trees. Specimens in the terrace planters stand on the planter soil."""
    groups = {}
    pl_soil = {(round(c[0], 2), round(c[1], 2)): zs for (c, ang, size, zs) in planters}
    for k, (sp, x, y, s, rot) in enumerate(ED.TREES):
        lst = T[sp]
        tm = lst[_h('%s%.2f%.2f' % (sp, x, y)) % len(lst)]
        z = pl_soil.get((round(x, 2), round(y, 2)))
        if z is None:
            z = TR.height(x, y) - 0.04
        groups.setdefault(tm.name, []).append(((x, y, z), (0.0, 0.0, rot), s))
    for k, (sp, x, y, s, rot) in enumerate(ED.FAR_TREES):
        lst = T[sp]
        tm = lst[_h('%s%.1f%.1f' % (sp, x, y)) % len(lst)]
        groups.setdefault(tm.name, []).append(((x, y, TR.height(x, y) - 0.05), (0.0, 0.0, rot), s))
    out = []
    for nm, tr in sorted(groups.items()):
        out.append(C.instancer('环境树_' + nm, bpy.data.objects[nm], tr, coll))
    return out, sum(len(v) for v in groups.values())

def shrubs(coll, T, planters, mask):
    groups = {}
    def add(tm, x, y, z, s, rot):
        groups.setdefault(tm.name, []).append(((x, y, z), (0.0, 0.0, rot), s))
    for (x, y, s, rot) in ED.SHRUBS:
        if mask.test(x, y):
            continue
        (scx, scy), scr = ED.SCULPT_PLAZA
        near_plaza = (x - scx) ** 2 + (y - scy) ** 2 < (scr + 4.0) ** 2
        key = 'shrubr' if (_h('s%.2f%.2f' % (x, y)) % 10 < 1 and not near_plaza) else 'shrub'
        lst = T[key]
        add(lst[_h('%.2f%.2f' % (x, y)) % len(lst)], x, y, TR.height(x, y) - 0.03, s, rot)
    for (x, y, s, rot) in ED.HEDGE:
        if mask.test(x, y):
            continue
        lst = T['hedge']
        add(lst[_h('h%.2f%.2f' % (x, y)) % len(lst)], x, y, TR.height(x, y) - 0.03, s * 0.9, rot)
    # boxwood around the small trees in the terrace planters (not the lawn planter)
    rng = random.Random(12)
    for (c, ang, (w, d), zs) in planters[:len(ED.PLANTERS)]:
        a = math.radians(ang)
        dx, dy = math.cos(a), math.sin(a)
        for s1, s2 in ((-1, -1), (1, -1), (1, 1), (-1, 1), (0, -1), (0, 1)):
            u, v = s1 * (w / 2 - 0.35), s2 * (d / 2 - 0.32)
            x = c[0] + dx * u - dy * v; y = c[1] + dy * u + dx * v
            add(T['shrub'][rng.randrange(len(T['shrub']))], x, y, zs - 0.02, rng.uniform(0.55, 0.7), rng.uniform(0, 6.28))
    out = []
    for nm, tr in sorted(groups.items()):
        out.append(C.instancer('环境灌木_' + nm, bpy.data.objects[nm], tr, coll))
    return out

def ground_plants(coll, sets, mask):
    rng = random.Random(3)
    pts = [((x, y, WL - 0.01), (0.0, 0.0, rot), s, _h('l%.2f%.2f' % (x, y)) % 3) for (x, y, s, rot) in ED.LOTUS]
    P.scatter('环境_荷叶', coll, pts, 'lotus', sets, frac=0.35)
    pts = []
    for (x, y, s, rot) in ED.BANK:
        if mask.test(x, y):
            continue
        z = TR.height(x, y)
        if z < WL - 0.05:
            z = WL - 0.02
        pts.append(((x, y, z - 0.02), (0.0, 0.0, rot), s, _h('b%.2f%.2f' % (x, y)) % 3))
    P.scatter('环境_岸边植物', coll, pts, 'bank', sets, frac=0.3)
    pts = []
    for (x, y, s, rot) in ED.ROCKS:
        if mask.test(x, y):
            continue
        z = TR.height(x, y) - 0.12 * s
        pts.append(((x, y, z), (rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), rot), s, _h('r%.2f%.2f' % (x, y)) % 6))
    P.scatter('环境_置石', coll, pts, 'rock', sets, frac=1.0)
    return len(ED.LOTUS), len(pts)

def forest_cover(coll, sets, mask, density=0.35, seed=7):
    """Sparse low ground cover under the tree canopies (forest floor)."""
    g = TR.grids()
    wf = g['WF']
    ny, nx = wf.shape
    r = np.random.default_rng(seed)
    cand = np.argwhere(wf > 0.5)
    n = int(len(cand) * TR.EG.GRES ** 2 * density)
    pick = cand[r.integers(0, len(cand), n)]
    X = TR.EG.GX0 + (pick[:, 1] + 0.5 + r.uniform(-0.5, 0.5, n)) * TR.EG.GRES
    Y = TR.EG.GY1 - (pick[:, 0] + 0.5 + r.uniform(-0.5, 0.5, n)) * TR.EG.GRES
    ok = ~mask.test_many(X, Y) & ~g['WATER'][pick[:, 0], pick[:, 1]]
    X, Y = X[ok], Y[ok]
    Zs = TR.heights(X, Y) - 0.03
    rot = r.uniform(0, 6.283, len(X)); scl = r.uniform(0.55, 0.95, len(X)); kind = r.integers(0, 3, len(X))
    pts = [((float(X[i]), float(Y[i]), float(Zs[i])), (0.0, 0.0, float(rot[i])), float(scl[i]), int(kind[i])) for i in range(len(X))]
    P.scatter('环境_林下地被', coll, pts, 'bank', sets, frac=0.1)
    return len(pts)

def lawn(coll, sets, mask, planters, density=48.0, seed=11, clear=0.06):
    """Lawn grass clumps: accepted with the lawn weight, kept off paving (fine mask, + `clear` m) and water."""
    g = TR.grids()
    WF, WB, WK, WM = g['WF'], g['WB'], g['WK'], g['WM']
    lawnw = np.clip(1.0 - (WF + WB + WK + WM), 0, 1) * (~g['WATER'])
    ny, nx = lawnw.shape
    r = np.random.default_rng(seed)
    cells = np.argwhere(lawnw > 0.02)
    cnt = r.poisson(density * TR.EG.GRES ** 2, len(cells))
    rep = np.repeat(np.arange(len(cells)), cnt)
    cj, ci = cells[rep, 0], cells[rep, 1]
    fx = r.uniform(-0.5, 0.5, len(rep)); fy = r.uniform(-0.5, 0.5, len(rep))
    X = TR.EG.GX0 + (ci + 0.5 + fx) * TR.EG.GRES
    Y = TR.EG.GY1 - (cj + 0.5 + fy) * TR.EG.GRES
    # bilinear lawn weight at the exact spot -> acceptance
    fi = np.clip((X - TR.EG.GX0) / TR.EG.GRES - 0.5, 0, nx - 1.001); fj = np.clip((TR.EG.GY1 - Y) / TR.EG.GRES - 0.5, 0, ny - 1.001)
    i0 = fi.astype(int); j0 = fj.astype(int); a = fi - i0; b = fj - j0
    w = (lawnw[j0, i0] * (1 - a) * (1 - b) + lawnw[j0, i0 + 1] * a * (1 - b) + lawnw[j0 + 1, i0] * (1 - a) * b +
         lawnw[j0 + 1, i0 + 1] * a * b)
    keep = r.uniform(0, 1, len(X)) < w
    # stay off paving / kerbs, with a small clearance
    for dx, dy in ((0, 0), (clear, 0), (-clear, 0), (0, clear), (0, -clear)):
        keep &= ~mask.test_many(X + dx, Y + dy)
    X, Y = X[keep], Y[keep]
    Zs = TR.heights(X, Y) - 0.004
    # keep grass out of the water (shore heights below the water line)
    dry = Zs > WL + 0.03
    X, Y, Zs = X[dry], Y[dry], Zs[dry]
    # lawn planter on the terrace
    (lc, (lw, ld)) = ED.LAWN_PLANTER
    zs = [p[3] for p in planters if abs(p[0][0] - lc[0]) < 1e-6 and abs(p[0][1] - lc[1]) < 1e-6]
    if zs:
        m = int((lw - 0.2) * (ld - 0.2) * density * 1.4)
        px = lc[0] + r.uniform(-(lw / 2 - 0.12), lw / 2 - 0.12, m); py = lc[1] + r.uniform(-(ld / 2 - 0.12), ld / 2 - 0.12, m)
        X = np.concatenate([X, px]); Y = np.concatenate([Y, py]); Zs = np.concatenate([Zs, np.full(m, zs[0] - 0.004)])
    n = len(X)
    rot = r.uniform(0, 6.283, n); scl = r.uniform(0.8, 1.3, n); kind = r.integers(0, 4, n)
    pts = [((float(X[i]), float(Y[i]), float(Zs[i])), (0.0, 0.0, float(rot[i])), float(scl[i]), int(kind[i])) for i in range(n)]
    P.scatter('环境_草坪', coll, pts, 'grass', sets, frac=0.01)
    return n


def understory(coll, T, mask, density=0.045, seed=21, keep_off=14.0):
    """Shrub layer under the tree canopies (1-2.5 m), away from the complex, paths and water; closes the
    long views between trunks the way a park's understory does."""
    g = TR.grids()
    wf = g['WF']
    r = np.random.default_rng(seed)
    cand = np.argwhere(wf > 0.6)
    n = int(len(cand) * TR.EG.GRES ** 2 * density)
    pick = cand[r.integers(0, len(cand), n)]
    X = TR.EG.GX0 + (pick[:, 1] + 0.5 + r.uniform(-0.5, 0.5, n)) * TR.EG.GRES
    Y = TR.EG.GY1 - (pick[:, 0] + 0.5 + r.uniform(-0.5, 0.5, n)) * TR.EG.GRES
    ok = ~g['WATER'][pick[:, 0], pick[:, 1]]
    for dx, dy in ((0, 0), (3.0, 0), (-3.0, 0), (0, 3.0), (0, -3.0), (2.1, 2.1), (-2.1, 2.1), (2.1, -2.1), (-2.1, -2.1)):
        ok &= ~mask.test_many(X + dx, Y + dy)
    # keep the near surroundings of the complex open (lawns and paths as in the aerial)
    cx, cy = 35.0, 22.0
    ok &= ((X - cx) / 1.0) ** 2 + ((Y - cy) / 1.0) ** 2 > (keep_off + 38.0) ** 2
    trunks = np.array([(t[1], t[2]) for t in ED.TREES])
    X, Y = X[ok], Y[ok]
    if len(trunks):
        from math import hypot
        d2 = ((X[:, None] - trunks[None, :, 0]) ** 2 + (Y[:, None] - trunks[None, :, 1]) ** 2).min(axis=1)
        keep = d2 > 1.2 ** 2
        X, Y = X[keep], Y[keep]
    groups = {}
    lst = T['under']
    for i in range(len(X)):
        tm = lst[_h('u%.2f%.2f' % (X[i], Y[i])) % len(lst)]
        z = TR.height(float(X[i]), float(Y[i])) - 0.05
        groups.setdefault(tm.name, []).append(((float(X[i]), float(Y[i]), z), (0.0, 0.0, float(r.uniform(0, 6.28))), float(r.uniform(0.8, 1.3))))
    out = []
    for nm, tr in sorted(groups.items()):
        out.append(C.instancer('环境灌木_' + nm, bpy.data.objects[nm], tr, coll))
    return sum(len(v) for v in groups.values())

def far_understory(coll, T, seed=23):
    """Low trees / big shrubs between the far ring trees (a closed tree line on the horizon)."""
    r = random.Random(seed)
    groups = {}
    lst = T['under']
    for (sp, x, y, s, rot) in ED.FAR_TREES:
        for k in range(2):
            a = r.uniform(0, 6.283); d = r.uniform(3.5, 6.0)
            xx, yy = x + d * math.cos(a), y + d * math.sin(a)
            tm = lst[r.randrange(len(lst))]
            groups.setdefault(tm.name, []).append(((xx, yy, TR.height(xx, yy) - 0.05), (0.0, 0.0, r.uniform(0, 6.28)), r.uniform(1.3, 1.9)))
    for nm, tr in sorted(groups.items()):
        C.instancer('环境远景灌木_' + nm, bpy.data.objects[nm], tr, coll)
    return sum(len(v) for v in groups.values())
